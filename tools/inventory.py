#!/usr/bin/env python3
"""Read-only inventory of attached 8BitDo USB devices.

Walks sysfs. Prints VID/PID, interfaces, hidraw nodes, and every HID
usage page in each report descriptor. Opens nothing for write, and
sends no HID reports.

Bootloader product IDs are printed and then skipped. See docs/safety.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VID = 0x2DC8

# Never open these, even for a future write path. Inventory still prints
# them so a bootloader being plugged in is obvious.
BOOTLOADER_PIDS = {
    0x3208: "shared bootloader from the field notes",
    0x5750: "older 8BitDo bootloader in public USB ID tables",
}

# Public reports. Confidence is not "seen on this machine".
KNOWN_PIDS = {
    0x310A: "Ultimate 2C Wireless, XInput (dongle and cable)",
    0x301B: "Ultimate 2C Wireless, Bluetooth DirectInput (PCGamingWiki, unverified)",
    0x310B: "Ultimate 2 Wireless, USB/dongle XInput (PCGamingWiki)",
    0x6012: "Ultimate 2 Wireless, DInput (SDL)",
    0x6013: "Ultimate 2 Wireless dongle (field notes, unverified)",
    0x301C: "Ultimate 2C dongle while idle, product string IDLE (seen)",
    0x301D: "Ultimate 2C wired DInput personality, from the 1.09 image",
    0x301A: "Ultimate 2C Bluetooth edition, V2 name PID_UltimateBT2C",
    0x600F: "Ultimate BT2 pad, 0xad0-byte config image in V2",
    0x6011: "Ultimate BT2 receiver",
}

USB_DEVICES = Path("/sys/bus/usb/devices")

# HID item types and the global tags we care about.
MAIN, GLOBAL, LOCAL = 0, 1, 2
TAG_USAGE_PAGE = 0
TAG_REPORT_SIZE = 7
TAG_REPORT_ID = 8
TAG_REPORT_COUNT = 9
TAG_USAGE = 0
TAG_COLLECTION = 0xA


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace").strip()
    except OSError:
        return ""


def parse_descriptor(data: bytes) -> dict:
    """Pull usage pages, report IDs, and collections out of a HID descriptor.

    Enough to answer "is there a vendor usage page?", not a full decoder.
    """
    usage_pages: list[int] = []
    report_ids: list[int] = []
    collections: list[dict] = []
    current_page = 0
    current_usage = 0
    i = 0
    n = len(data)

    while i < n:
        prefix = data[i]
        if prefix == 0xFE:
            if i + 3 > n:
                break
            size = data[i + 1]
            i += 3 + size
            continue
        size_code = prefix & 0x03
        size = (0, 1, 2, 4)[size_code]
        item_type = (prefix >> 2) & 0x03
        tag = (prefix >> 4) & 0x0F
        if i + 1 + size > n:
            break
        raw = data[i + 1 : i + 1 + size]
        value = int.from_bytes(raw, "little") if size else 0
        i += 1 + size

        if item_type == GLOBAL and tag == TAG_USAGE_PAGE:
            current_page = value
            if value not in usage_pages:
                usage_pages.append(value)
        elif item_type == GLOBAL and tag == TAG_REPORT_ID:
            if value not in report_ids:
                report_ids.append(value)
        elif item_type == LOCAL and tag == TAG_USAGE:
            current_usage = value
        elif item_type == MAIN and tag == TAG_COLLECTION:
            collections.append(
                {
                    "usage_page": current_page,
                    "usage": current_usage,
                    "vendor": current_page >= 0xFF00,
                }
            )

    return {
        "usage_pages": [f"0x{p:04x}" for p in usage_pages],
        "vendor_pages": [f"0x{p:04x}" for p in usage_pages if p >= 0xFF00],
        "report_ids": [f"0x{r:02x}" for r in report_ids],
        "collections": collections,
    }


def hidraw_nodes(interface: Path) -> list[Path]:
    found = []
    for node in interface.rglob("hidraw*"):
        if node.is_dir() and node.name.startswith("hidraw") and node.name[6:].isdigit():
            found.append(node)
    return found


def describe_interface(interface: Path) -> dict:
    number = read_text(interface / "bInterfaceNumber")
    klass = read_text(interface / "bInterfaceClass")
    subclass = read_text(interface / "bInterfaceSubClass")
    protocol = read_text(interface / "bInterfaceProtocol")
    descriptors = []
    for node in hidraw_nodes(interface):
        desc_path = node / "device" / "report_descriptor"
        if not desc_path.is_file():
            # hidrawN/device is a symlink; the descriptor sits beside the hid device
            alt = node / "device" / "report_descriptor"
            desc_path = alt
        blob = b""
        try:
            blob = desc_path.read_bytes()
        except OSError as exc:
            parsed = {"error": str(exc)}
        else:
            parsed = parse_descriptor(blob)
        name = read_text(node / "device" / "uevent")
        hid_name = ""
        for line in name.splitlines():
            if line.startswith("HID_NAME="):
                hid_name = line.split("=", 1)[1]
        descriptors.append(
            {
                "hidraw": node.name,
                "hid_name": hid_name,
                "descriptor_bytes": len(blob),
                **parsed,
            }
        )
    return {
        "interface": number,
        "class": klass,
        "subclass": subclass,
        "protocol": protocol,
        "hid": descriptors,
    }


def class_name(klass: str, subclass: str, protocol: str) -> str:
    if klass == "ff" and subclass == "5d":
        return "vendor, XInput-style (xpad claims ff/5d/01)"
    if klass == "03":
        return "HID"
    return "other"


def inventory_device(dev: Path) -> dict:
    pid = int(read_text(dev / "idProduct") or "0", 16)
    serial = read_text(dev / "serial")
    interfaces = []
    for child in sorted(dev.iterdir()):
        if (child / "bInterfaceClass").is_file():
            info = describe_interface(child)
            info["guess"] = class_name(info["class"], info["subclass"], info["protocol"])
            interfaces.append(info)
    vendor_pages = []
    for iface in interfaces:
        for hid in iface["hid"]:
            vendor_pages.extend(hid.get("vendor_pages") or [])
    return {
        "sysfs": dev.name,
        "vid": f"{VID:04x}",
        "pid": f"{pid:04x}",
        "known_as": KNOWN_PIDS.get(pid, "unknown 8BitDo product"),
        "bootloader": pid in BOOTLOADER_PIDS,
        "bootloader_note": BOOTLOADER_PIDS.get(pid, ""),
        "manufacturer": read_text(dev / "manufacturer"),
        "product": read_text(dev / "product"),
        "serial_present": bool(serial),
        "serial_is_zeros": bool(serial) and set(serial) <= {"0"},
        "bus": read_text(dev / "busnum"),
        "address": read_text(dev / "devnum"),
        "interfaces": interfaces,
        "config_channel_candidate": bool(vendor_pages),
    }


def find_devices() -> list[dict]:
    found = []
    if not USB_DEVICES.is_dir():
        return found
    for dev in sorted(USB_DEVICES.iterdir()):
        vid_text = read_text(dev / "idVendor")
        if vid_text.lower() != f"{VID:04x}":
            continue
        found.append(inventory_device(dev))
    return found


def print_human(devices: list[dict]) -> None:
    if not devices:
        print("No 8BitDo device (vid 2dc8) on USB.")
        print("Plug in the dongle with the controller on, then off, then the cable,")
        print("and run this again. Bluetooth will not show up here; check")
        print("/sys/class/hidraw for HID_ID containing 0002DC8 after pairing.")
        return
    for dev in devices:
        print(f"{dev['sysfs']}: {dev['vid']}:{dev['pid']}  {dev['product'] or dev['known_as']}")
        print(f"  known as: {dev['known_as']}")
        if dev["bootloader"]:
            print(f"  BOOTLOADER. Do not send anything. {dev['bootloader_note']}")
            continue
        print(f"  bus {dev['bus']} address {dev['address']}")
        if dev["serial_present"]:
            flag = " (all zeros)" if dev["serial_is_zeros"] else ""
            print(f"  serial string is present{flag}; not printed")
        print(
            f"  wireshark: usbmon{int(dev['bus']):01d}  "
            f"filter usb.device_address == {int(dev['address'])}"
        )
        if dev["config_channel_candidate"]:
            print("  vendor usage page present: config channel candidate")
        else:
            print("  no vendor usage page in the descriptors that were readable")
        for iface in dev["interfaces"]:
            print(
                f"  interface {iface['interface']}: "
                f"class {iface['class']}/{iface['subclass']}/{iface['protocol']}  {iface['guess']}"
            )
            if not iface["hid"]:
                print("    no hidraw node")
            for hid in iface["hid"]:
                print(
                    f"    {hid['hidraw']}: {hid.get('hid_name') or '(no HID_NAME)'}  "
                    f"{hid.get('descriptor_bytes', 0)} byte descriptor"
                )
                if hid.get("error"):
                    print(f"      descriptor unreadable: {hid['error']}")
                    continue
                print(f"      usage pages: {', '.join(hid['usage_pages']) or '(none)'}")
                if hid["vendor_pages"]:
                    print(f"      vendor pages: {', '.join(hid['vendor_pages'])}")
                if hid["report_ids"]:
                    print(f"      report ids: {', '.join(hid['report_ids'])}")
        print()


def self_test() -> int:
    """Parser checks against descriptors already on this machine.

    The 2C is not required. A failure here means the usage-page walk is wrong.
    """
    checked = 0
    for node in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        desc = node / "device" / "report_descriptor"
        if not desc.is_file():
            continue
        data = desc.read_bytes()
        parsed = parse_descriptor(data)
        if not parsed["usage_pages"]:
            print(f"FAIL {node.name}: descriptor is {len(data)} bytes and yielded no usage page")
            return 1
        checked += 1
    if checked == 0:
        print("FAIL: no hidraw descriptors were readable")
        return 1
    # Synthetic vendor-page descriptor: usage page 0xFF00, usage 0x01, collection.
    synthetic = bytes.fromhex("06 00 ff 09 01 a1 01 c0")
    parsed = parse_descriptor(synthetic)
    if parsed["vendor_pages"] != ["0xff00"]:
        print(f"FAIL synthetic vendor page: {parsed}")
        return 1
    print(f"ok: parsed {checked} local hidraw descriptors, vendor-page fixture matched")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the inventory as JSON")
    parser.add_argument("--self-test", action="store_true", help="parse local descriptors and exit")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    devices = find_devices()
    if args.json:
        json.dump(devices, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_human(devices)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
