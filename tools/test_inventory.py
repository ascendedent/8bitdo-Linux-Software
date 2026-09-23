"""The inventory tool against fake USB and Bluetooth sysfs trees. Opens nothing."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import inventory

VENDOR_DESC = bytes.fromhex("067aff0901a1018502090215002 5ff7508953f8102858109059102c0c0".replace(" ", ""))


class BluetoothInventory(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = (inventory.USB_DEVICES, inventory.HID_DEVICES)
        inventory.USB_DEVICES = root / "usb"
        inventory.HID_DEVICES = root / "hid"
        hid = inventory.HID_DEVICES / "0005:2DC8:301B.0009"
        hid.mkdir(parents=True)
        (hid / "report_descriptor").write_bytes(VENDOR_DESC)
        (hid / "uevent").write_text("HID_NAME=8BitDo Ultimate 2C Wireless Controller\n")
        (hid / "hidraw" / "hidraw9").mkdir(parents=True)
        (inventory.HID_DEVICES / "0003:2DC8:310A.0001").mkdir()  # USB bus entry, listed under USB instead

    def tearDown(self) -> None:
        inventory.USB_DEVICES, inventory.HID_DEVICES = self.saved
        self.tmp.cleanup()

    def test_bluetooth_pad_is_listed(self) -> None:
        devices = inventory.find_devices()
        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertEqual((dev["transport"], dev["pid"], dev["sysfs"]), ("bluetooth", "301b", "0005:2DC8:301B.0009"))
        self.assertTrue(dev["config_channel_candidate"])
        self.assertEqual(dev["interfaces"][0]["hid"][0]["hidraw"], "hidraw9")
        out = io.StringIO()
        with redirect_stdout(out):
            inventory.print_human(devices)
        text = out.getvalue()
        self.assertIn("0005:2DC8:301B.0009: 2dc8:301b", text)
        self.assertIn("btmon", text)
        self.assertIn("0xff7a", text)


if __name__ == "__main__":
    unittest.main()
