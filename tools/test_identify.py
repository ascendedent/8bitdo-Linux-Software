"""Decoding of the identify reply. Does not open a device."""

from __future__ import annotations

import unittest

import tempfile
from pathlib import Path

import identify
from identify import describe_identify, find_vendor_interface

CAPTURED = bytes.fromhex("02226d0000001b30010000") + bytes(53)

VENDOR_PAGE_DESC = bytes.fromhex("067aff0901a101" "8502090215002 5ff7508953f8102" "858109059102c0c0".replace(" ", ""))
KEYBOARD_DESC = bytes.fromhex("05010906a101c0")
# A vendor page with other report ids, like an XInput-style vendor collection.
OTHER_VENDOR_DESC = bytes.fromhex("0600ff0901a101" "8501090275089540 8102" "c0".replace(" ", ""))


def fake_device(root: Path, name: str, pid: int, interfaces: list[tuple[bytes, int | None]]) -> None:
    """One USB device with report descriptors and hidraw nodes per interface."""
    dev = root / name
    dev.mkdir()
    (dev / "idVendor").write_text("2dc8\n")
    (dev / "idProduct").write_text(f"{pid:04x}\n")
    for number, (descriptor, hidraw) in enumerate(interfaces):
        hid = dev / f"{name}:1.{number}" / f"0003:2DC8:{pid:04X}.000{number + 1}"
        hid.mkdir(parents=True)
        (hid / "report_descriptor").write_bytes(descriptor)
        if hidraw is not None:
            (hid / "hidraw" / f"hidraw{hidraw}").mkdir(parents=True)


def fake_bluetooth(hid_root: Path, pid: int, instance: int, descriptor: bytes, hidraw: int | None) -> str:
    """One Bluetooth HID device, as /sys/bus/hid/devices names it."""
    name = f"0005:2DC8:{pid:04X}.{instance:04X}"
    hid = hid_root / name
    hid.mkdir(parents=True)
    (hid / "report_descriptor").write_bytes(descriptor)
    if hidraw is not None:
        (hid / "hidraw" / f"hidraw{hidraw}").mkdir(parents=True)
    return name


class FindVendorInterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "usb"
        self.root.mkdir()
        self.hid_root = Path(self.tmp.name) / "hid"
        self.hid_root.mkdir()
        self.saved = (identify.SYSFS_ROOT, identify.HID_ROOT)
        identify.SYSFS_ROOT = self.root
        identify.HID_ROOT = self.hid_root

    def tearDown(self) -> None:
        identify.SYSFS_ROOT, identify.HID_ROOT = self.saved
        self.tmp.cleanup()

    def test_bluetooth_pad_is_found_under_the_hid_bus(self) -> None:
        name = fake_bluetooth(self.hid_root, 0x301B, 7, VENDOR_PAGE_DESC, 12)
        self.assertEqual(find_vendor_interface(0x301B), Path("/dev/hidraw12"))
        self.assertEqual(find_vendor_interface(0x301B, name), Path("/dev/hidraw12"))
        with self.assertRaises(SystemExit):
            find_vendor_interface(0x310A)

    def test_bluetooth_without_vendor_page_is_reported_not_opened(self) -> None:
        fake_bluetooth(self.hid_root, 0x301B, 1, KEYBOARD_DESC, 12)
        with self.assertRaises(SystemExit) as ctx:
            find_vendor_interface(0x301B)
        self.assertIn("301b at 0005:2DC8:301B.0001 (bluetooth)", str(ctx.exception))

    def test_picks_the_vendor_page_interface(self) -> None:
        fake_device(self.root, "3-5.2", 0x310A, [(KEYBOARD_DESC, 30), (VENDOR_PAGE_DESC, 31)])
        self.assertEqual(find_vendor_interface(0x310A), Path("/dev/hidraw31"))

    def test_ultimate2_by_pid(self) -> None:
        fake_device(self.root, "1-1", 0x6012, [(VENDOR_PAGE_DESC, 5)])
        fake_device(self.root, "1-2", 0x310A, [(VENDOR_PAGE_DESC, 6)])
        self.assertEqual(find_vendor_interface(0x6012), Path("/dev/hidraw5"))
        self.assertEqual(find_vendor_interface(0x310A), Path("/dev/hidraw6"))

    def test_refused_and_unknown_ids(self) -> None:
        fake_device(self.root, "1-1", 0x3208, [(VENDOR_PAGE_DESC, 5)])
        fake_device(self.root, "1-2", 0x301C, [(VENDOR_PAGE_DESC, 6)])
        for pid in (0x3208, 0x5750, 0x301C, 0x1234):
            with self.assertRaises(SystemExit):
                find_vendor_interface(pid)
        with self.assertRaises(SystemExit):
            find_vendor_interface(0x310A)

    def test_two_matches_need_a_path(self) -> None:
        fake_device(self.root, "3-5.1", 0x310A, [(VENDOR_PAGE_DESC, 31)])
        fake_device(self.root, "3-5.2.2.2", 0x310A, [(VENDOR_PAGE_DESC, 41)])
        with self.assertRaises(SystemExit):
            find_vendor_interface(0x310A)
        self.assertEqual(find_vendor_interface(0x310A, "3-5.1"), Path("/dev/hidraw31"))
        self.assertEqual(find_vendor_interface(0x310A, "3-5.2.2.2"), Path("/dev/hidraw41"))
        with self.assertRaises(SystemExit):
            find_vendor_interface(0x310A, "3-9")

    def test_auto_pid_picks_the_one_pad_present(self) -> None:
        fake_device(self.root, "1-1", 0x6012, [(VENDOR_PAGE_DESC, 5)])
        self.assertEqual(identify.choose_pid(None, None), 0x6012)
        fake_device(self.root, "1-2", 0x310A, [(VENDOR_PAGE_DESC, 6)])
        with self.assertRaises(SystemExit):
            identify.choose_pid(None, None)
        self.assertEqual(identify.choose_pid(None, "1-2"), 0x310A)
        self.assertEqual(identify.choose_pid(0x6012, None), 0x6012)
        fake_bluetooth(self.hid_root, 0x301B, 3, VENDOR_PAGE_DESC, 9)
        self.assertEqual(identify.choose_pid(None, "0005:2DC8:301B.0003"), 0x301B)

    def test_selection_records_the_report_ids(self) -> None:
        fake_device(self.root, "1-1", 0x6012, [(OTHER_VENDOR_DESC, 3)])
        node = find_vendor_interface(0x6012)
        self.assertEqual(identify.LAST_SELECTION[str(node)], {0x01})

    def test_no_vendor_page_is_not_opened_and_nodes_are_named(self) -> None:
        fake_device(self.root, "1-1", 0x6012, [(KEYBOARD_DESC, 5)])
        with self.assertRaises(SystemExit) as ctx:
            find_vendor_interface(0x6012)
        self.assertIn("/dev/hidraw5", str(ctx.exception))
        self.assertIn("--node", str(ctx.exception))

    def test_config_report_ids_win_over_another_vendor_page(self) -> None:
        fake_device(self.root, "1-1", 0x6012, [(OTHER_VENDOR_DESC, 3), (VENDOR_PAGE_DESC, 4)])
        self.assertEqual(find_vendor_interface(0x6012), Path("/dev/hidraw4"))
        fake_device(self.root, "1-2", 0x310B, [(OTHER_VENDOR_DESC, 8)])
        # With no better candidate the other vendor page is still opened.
        self.assertEqual(find_vendor_interface(0x310B), Path("/dev/hidraw8"))


class DescribeIdentifyTests(unittest.TestCase):
    def test_captured_reply(self) -> None:
        notes = describe_identify(CAPTURED)
        self.assertEqual(notes[0], "byte 2 is 0x6d: firmware 1.09")
        self.assertIn("0x301b", notes[1])
        self.assertIn("plain product strings", notes[2])
        self.assertEqual(notes[3], "byte 10 is 0x00: wired DInput flag")

    def test_dinput_and_wukong_variant(self) -> None:
        reply = bytearray(CAPTURED)
        reply[6:8] = b"\x1d\x30"
        reply[8:10] = b"\x02\x00"
        reply[10] = 1
        notes = describe_identify(bytes(reply))
        self.assertIn("0x301d", notes[1])
        self.assertIn("(WUKONG)", notes[2])
        self.assertEqual(notes[3], "byte 10 is 0x01: wired DInput flag")

    def test_other_replies_are_left_alone(self) -> None:
        self.assertEqual(describe_identify(b""), [])
        self.assertEqual(describe_identify(bytes.fromhex("020500")), [])
        self.assertEqual(describe_identify(bytes.fromhex("0205000000c100")), [])


if __name__ == "__main__":
    unittest.main()
