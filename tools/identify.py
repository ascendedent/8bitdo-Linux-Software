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
}
# Pads the read tool may open, by product id. Anything else is refused.
PAD_PIDS = {
    0x310A: "Ultimate 2C Wireless (cable, or the dongle with the pad on)",
    0x6012: "Ultimate 2 Wireless, DInput",
    0x6013: "Ultimate 2 Wireless dongle",
    0x310B: "Ultimate 2 Wireless, XInput",
}

from packets import IDENTIFY_COMMANDS, IDENTIFY_GET_PID, IDENTIFY_INIT, pad_report

# Overridden by the tests, which build a fake tree.
SYSFS_ROOT = Path("/sys/bus/usb/devices")

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
    pages: set[int] = set()
    for desc in iface.rglob("report_descriptor"):
        data = desc.read_bytes()
        for i in range(len(data) - 2):
            if data[i] == 0x06 and data[i + 2] == 0xFF:
                pages.add(0xFF00 | data[i + 1])
    return pages


def descriptor_has_vendor_page(usb_name: str, interface: int) -> bool:
    return USAGE_PAGE in vendor_pages(usb_name, interface)


def hidraw_node(iface: Path) -> Path | None:
    for node in iface.rglob("hidraw*"):
        if node.is_dir() and node.name.startswith("hidraw") and node.name[6:].isdigit():
            return Path("/dev") / node.name
    return None


def find_vendor_interface(pid: int = CONTROLLER_PID, path: str | None = None) -> Path:
    """The hidraw node of the vendor-page interface of one attached pad.

    pid must be in PAD_PIDS. path is the sysfs device name (for example
    3-5.2.2.2, printed by tools/inventory.py) and is required when more
    than one matching device is attached, such as the pad on a cable and
    on its dongle at the same time.
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
        for iface in sorted(dev.glob(f"{dev.name}:1.*")):
            number = int(iface.name.rsplit(".", 1)[-1])
            pages = pages_under(iface)
            if not pages:
                continue
            node = hidraw_node(iface)
            if node is None:
                raise SystemExit(f"{dev.name} interface {number} has no hidraw node")
            matches.append((dev, node, min(pages)))
            break
    if len(matches) == 1:
        return matches[0][1]
    if len(matches) > 1:
        names = ", ".join(f"{d.name} ({n}, page 0x{p:04x})" for d, n, p in matches)
        raise SystemExit(f"more than one {pid:04x} with a vendor page: {names}. Pass --path.")
    raise SystemExit(
        f"no {pid:04x} interface with a vendor usage page"
        + (f" at {path}" if path else "")
        + f". present: {', '.join(present) or 'none'}. "
        "The idle dongle (301c) is not a substitute."
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

    ap = argparse.ArgumentParser(description="replay the two captured identify commands to a 310a")
    ap.add_argument("--path", help="sysfs device name from tools/inventory.py, when two 310a are attached")
    args = ap.parse_args()
    node = find_vendor_interface(CONTROLLER_PID, args.path)
    print(f"open {node} for 2dc8:310a usage page 0x{USAGE_PAGE:04x}")
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
