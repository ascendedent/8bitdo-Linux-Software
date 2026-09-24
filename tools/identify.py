#!/usr/bin/env python3
"""Replay the two identify commands captured from Ultimate Software V2.

The first command is built by getcurrentpid: report 81, class 05, then
00 21 01. The reply's product id is the little-endian uint16 at offset 6.
The second command is initDevice: class 05, command word 0x00C1.

Sends only those bytes, and only to a 2dc8:310a interface whose report
descriptor contains usage page 0xFF7A. Refuses the bootloader and the idle
dongle. Does not write settings.

The identify reply is decoded from the 1.09 firmware's handler
(docs/firmware.md): byte 2 is the version, bytes 6-7 the product id the
firmware plants (301b, or 301d with the wired DInput flag set), bytes 8-9
the product-string selector persisted at flash 0x77000, byte 10 the
DInput flag itself.
"""

from __future__ import annotations

import os
import select
import sys
from pathlib import Path

VID = 0x2DC8
CONTROLLER_PID = 0x310A
USAGE_PAGE = 0xFF7A
REFUSE = {
    0x3208: "bootloader",
    0x5750: "older bootloader",
    0x301C: "idle dongle; the captured commands were not sent to this device",
    0x3107: "idle Ultimate 2 dongle; nothing is sent to it",
}
# Pads the read tool may open, by product id. Anything else is refused.
PAD_PIDS = {
    0x310A: "Ultimate 2C Wireless (cable, or the dongle with the pad on)",
    0x6012: "Ultimate 2 Wireless, DInput",
    0x6013: "Ultimate 2 Wireless dongle",
    0x310B: "Ultimate 2 Wireless, XInput",
    0x301B: "Ultimate 2C over Bluetooth (the id in its PnP record; not yet seen)",
    0x3105: "Ultimate 2 Wireless, cable DInput as V2 names it (PID_USB_Ultimate2); not yet seen",
    0x6013: "Ultimate 2 Wireless receiver personality V2 configures (PID_Ultimate2RR); not yet seen",
}
# Refused as a pad but listed when present.
IDLE_PIDS = {0x301C: "Ultimate 2C dongle, idle", 0x3107: "Ultimate 2 Wireless dongle, idle"}

from packets import IDENTIFY_COMMANDS, IDENTIFY_GET_PID, IDENTIFY_INIT, pad_report

# Overridden by the tests, which build fake trees.
SYSFS_ROOT = Path("/sys/bus/usb/devices")
# Bluetooth HID devices live here, not under the USB bus, named
# <bus>:<vid>:<pid>.<instance> with bus 0005 for Bluetooth.
HID_ROOT = Path("/sys/bus/hid/devices")
BLUETOOTH_BUS = "0005"

# Exact payloads from captures/exports/00_baseline.txt. pad_report extends
# each one to the 64-byte interrupt transfer V2 used.
COMMANDS = IDENTIFY_COMMANDS


def vendor_pages(usb_name: str, interface: int) -> set[int]:
    """Vendor usage pages (0xFF00-0xFFFF) declared by an interface's report descriptors.

    hidapi on this machine reports usage_page 0, so read the sysfs descriptor.
    A two-byte Usage Page item is 06 lo hi; a vendor page has hi = ff.
    """
    return pages_under(SYSFS_ROOT / f"{usb_name}:1.{interface}")


def pages_under(iface: Path) -> set[int]:
    """Vendor usage pages declared by the report descriptors below one interface directory."""
    return descriptor_facts(iface)[0]


def descriptor_facts(iface: Path) -> tuple[set[int], set[int]]:
    """(vendor usage pages, report ids) from the report descriptors below one interface.

    A two-byte Usage Page item is 06 lo hi with hi = ff for a vendor page.
    A one-byte Report ID item is 85 id. Both scans are over raw bytes, so a
    value byte that happens to equal 06 or 85 can add a false entry; that
    only widens the candidate set, it never drops the real one.
    """
    pages: set[int] = set()
    ids: set[int] = set()
    for desc in iface.rglob("report_descriptor"):
        data = desc.read_bytes()
        for i in range(len(data) - 1):
            if data[i] == 0x85:
                ids.add(data[i + 1])
            if data[i] == 0x06 and i + 2 < len(data) and data[i + 2] == 0xFF:
                pages.add(0xFF00 | data[i + 1])
    return pages, ids


CONFIG_REPORT_IDS = {0x81, 0x02}


def descriptor_has_vendor_page(usb_name: str, interface: int) -> bool:
    return USAGE_PAGE in vendor_pages(usb_name, interface)


def hidraw_node(iface: Path) -> Path | None:
    for node in iface.rglob("hidraw*"):
        if node.is_dir() and node.name.startswith("hidraw") and node.name[6:].isdigit():
            return Path("/dev") / node.name
    return None


def present_pads() -> list[tuple[int, str]]:
    """(pid, sysfs name) of every attached device with a pad id, USB then Bluetooth."""
    found: list[tuple[int, str]] = []
    if SYSFS_ROOT.is_dir():
        for dev in sorted(SYSFS_ROOT.iterdir()):
            vid = dev / "idVendor"
            if vid.is_file() and vid.read_text().strip().lower() == f"{VID:04x}":
                pid = int((dev / "idProduct").read_text().strip(), 16)
                if pid in PAD_PIDS:
                    found.append((pid, dev.name))
    if HID_ROOT.is_dir():
        for hid in sorted(HID_ROOT.iterdir()):
            parts = hid.name.split(":")
            if len(parts) == 3 and parts[0] == BLUETOOTH_BUS and parts[1].lower() == f"{VID:04x}":
                pid = int(parts[2].split(".")[0], 16)
                if pid in PAD_PIDS:
                    found.append((pid, hid.name))
    return found


def choose_pid(pid: int | None, path: str | None) -> int:
    """Resolve --pid auto: the one pad present, or the one at path."""
    if pid is not None:
        return pid
    pads = present_pads()
    if path is not None:
        pads = [p for p in pads if p[1] == path]
    ids = sorted({p for p, _ in pads})
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise SystemExit("no pad with a known id is attached; tools/inventory.py lists what is")
    raise SystemExit(
        "more than one pad id is attached: "
        + ", ".join(f"{p:04x} at {n}" for p, n in pads)
        + ". Pass --pid or --path."
    )


LAST_SELECTION: dict = {}


def find_vendor_interface(pid: int = CONTROLLER_PID, path: str | None = None) -> Path:
    """The hidraw node of the vendor-page interface of one attached pad.

    pid must be in PAD_PIDS. path is the sysfs device name (for example
    3-5.2.2.2, printed by tools/inventory.py) and is required when more
    than one matching device is attached, such as the pad on a cable and
    on its dongle at the same time. LAST_SELECTION records the report ids
    the chosen interface declares, so a caller can warn when 81 and 02
    are missing.
    """
    if pid not in PAD_PIDS:
        raise SystemExit(f"{pid:04x} is not a pad this tool opens")
    root = SYSFS_ROOT
    present = []
    matches: list[tuple[Path, Path, int]] = []
    if not root.is_dir():
        raise SystemExit("no usb sysfs")
    for dev in sorted(root.iterdir()):
        vid = (dev / "idVendor")
        if not vid.is_file() or vid.read_text().strip().lower() != f"{VID:04x}":
            continue
        found = int((dev / "idProduct").read_text().strip(), 16)
        present.append(f"{found:04x} at {dev.name}")
        if found in REFUSE or found != pid:
            continue
        if path is not None and dev.name != path:
            continue
        candidates: list[tuple[int, int, Path]] = []
        for iface in sorted(dev.glob(f"{dev.name}:1.*")):
            number = int(iface.name.rsplit(".", 1)[-1])
            pages, ids = descriptor_facts(iface)
            if not pages:
                continue
            node = hidraw_node(iface)
            if node is None:
                raise SystemExit(f"{dev.name} interface {number} has no hidraw node")
            # The config channel declares output 81 and input 02; prefer it.
            candidates.append((0 if CONFIG_REPORT_IDS <= ids else 1, min(pages), node, ids))
        if candidates:
            candidates.sort(key=lambda c: c[:2])
            matches.append((dev, candidates[0][2], candidates[0][1]))
            LAST_SELECTION[str(candidates[0][2])] = candidates[0][3]
    # Bluetooth: one HID device per pad, no USB interface directories.
    if HID_ROOT.is_dir():
        for hid in sorted(HID_ROOT.iterdir()):
            parts = hid.name.split(":")
            if len(parts) != 3 or parts[0] != BLUETOOTH_BUS or parts[1].lower() != f"{VID:04x}":
                continue
            found = int(parts[2].split(".")[0], 16)
            present.append(f"{found:04x} at {hid.name} (bluetooth)")
            if found in REFUSE or found != pid:
                continue
            if path is not None and hid.name != path:
                continue
            pages, ids = descriptor_facts(hid)
            if not pages:
                continue
            node = hidraw_node(hid)
            if node is None:
                raise SystemExit(f"{hid.name} has no hidraw node")
            matches.append((hid, node, min(pages)))
            LAST_SELECTION[str(node)] = ids
    if len(matches) == 1:
        return matches[0][1]
    if len(matches) > 1:
        names = ", ".join(f"{d.name} ({n}, page 0x{p:04x})" for d, n, p in matches)
        raise SystemExit(f"more than one {pid:04x} with a vendor page: {names}. Pass --path.")
    nodes = []
    for dev in sorted(root.iterdir()) if root.is_dir() else []:
        if (dev / "idProduct").is_file() and int((dev / "idProduct").read_text().strip(), 16) == pid:
            for iface in sorted(dev.glob(f"{dev.name}:1.*")):
                node = hidraw_node(iface)
                if node is not None:
                    nodes.append(str(node))
    raise SystemExit(
        f"no {pid:04x} interface with a vendor usage page"
        + (f" at {path}" if path else "")
        + f". present: {', '.join(present) or 'none'}. "
        "The idle dongle (301c) is not a substitute."
        + (
            f" This {pid:04x} has hidraw nodes without a vendor page: {', '.join(nodes)}. "
            "If tools/inventory.py shows report ids 0x81 and 0x02 on one of them, pass it with --node."
            if nodes
            else ""
        )
    )


def read_reply(fd: int, timeout_ms: int = 500) -> bytes:
    ready, _, _ = select.select([fd], [], [], timeout_ms / 1000)
    if not ready:
        return b""
    return os.read(fd, 64)


def describe_identify(reply: bytes) -> list[str]:
    """Name the bytes of an identify reply. Layout from docs/firmware.md."""
    notes: list[str] = []
    if len(reply) < 10 or reply[0] != 0x02 or reply[1] != 0x22:
        return notes
    version = reply[2]
    notes.append(f"byte 2 is {version:#04x}: firmware {version // 100}.{version % 100:02d}")
    pid = int.from_bytes(reply[6:8], "little")
    if pid == 0x301B:
        notes.append("bytes 6-7 are 1b 30: product id 0x301b, the radio id; DInput flag clear")
    elif pid == 0x301D:
        notes.append("bytes 6-7 are 1d 30: product id 0x301d; the wired DInput flag is set")
    else:
        notes.append(f"bytes 6-7: product id {pid:#06x}, not one the 1.09 firmware plants")
    selector = int.from_bytes(reply[8:10], "little")
    name = {1: "the plain product strings", 2: "the (WUKONG) product strings"}.get(
        selector, "no known string set"
    )
    notes.append(f"bytes 8-9 are {selector:#06x}: product-string selector, {name}")
    if len(reply) >= 11:
        notes.append(f"byte 10 is {reply[10]:#04x}: wired DInput flag")
    return notes


def explain(payload: bytes, reply: bytes) -> None:
    """Label the reply bytes the capture and the firmware image tied to a meaning."""
    if not reply:
        return
    print(f"  report id 0x{reply[0]:02x}")
    if payload == IDENTIFY_GET_PID:
        for note in describe_identify(reply):
            print(f"  {note}")
    if payload == IDENTIFY_INIT and len(reply) >= 5:
        if reply[1] == 0x05 and reply[4] == 0xC1:
            print("  byte 1 is 05 and byte 4 is c1, echoing the command")
        if len(reply) >= 32:
            tail = reply[22:32]
            if any(tail):
                print(f"  bytes 22-31 {tail.hex()}")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="replay the two captured identify commands to the 2C")
    ap.add_argument("--pid", default="310a", choices=["310a", "301b"], help="310a on USB (default), 301b over Bluetooth")
    ap.add_argument("--path", help="sysfs device name from tools/inventory.py, when two are attached")
    args = ap.parse_args()
    pid = int(args.pid, 16)
    node = find_vendor_interface(pid, args.path)
    print(f"open {node} for 2dc8:{pid:04x}")
    fd = os.open(node, os.O_RDWR)
    try:
        for payload in COMMANDS:
            packet = pad_report(payload)
            wrote = os.write(fd, packet)
            print(f"out {wrote:3d}  {payload.hex()}")
            reply = read_reply(fd)
            if not reply:
                print("in  timeout")
                return 1
            print(f"in  {len(reply):3d}  {reply.hex()}")
            explain(payload, reply)
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
