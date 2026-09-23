"""The Ultimate 2 image summary on a synthetic image. No HID device."""

from __future__ import annotations

import struct
import unittest

import ultimate2_image as u2
from u2_summary import map_entry_name, summarize


def synthetic() -> bytes:
    image = bytearray(u2.ULTIMATE2_SIZE)
    struct.pack_into("<3I", image, 0, u2.ENABLE_MARK, u2.DISABLED_MARK, u2.DISABLED_MARK)
    struct.pack_into("<IHH", image, 12, 0x1234, 1, 2)
    off, _ = u2.field_at("file_name", 0)
    image[off : off + 12] = "Racing".encode("utf-16le")
    off, _ = u2.field_at("stick", 0)
    image[off : off + 8] = struct.pack("<I", u2.ENABLE_MARK) + bytes([5, 120, 0, 128])
    for p in range(3):
        for b, button in enumerate(u2.MAP_KEY_NAMES):
            o, _ = u2.button_map_at(p, b)
            struct.pack_into("<I", image, o, u2.MAP_ENTRY_VALUES.get(button, 0))
    o, _ = u2.button_map_at(0, u2.MAP_KEY_NAMES.index("P1"))
    struct.pack_into("<I", image, o, u2.MAP_ENTRY_VALUES["A"])
    return bytes(image)


class SummaryTests(unittest.TestCase):
    def test_header_and_profile(self) -> None:
        lines = summarize(synthetic())
        self.assertEqual(lines[0], "header flags: enabled, not enabled, not enabled")
        self.assertEqual(lines[1], "crc_value 0x00001234, gamepad_mode 1, cur_slot 2")
        self.assertTrue(lines[2].startswith("crc16 candidates: whole image as stored 0x"))
        self.assertEqual(lines[3], "profile 0: name 'Racing'")
        stick = next(line for line in lines if line.strip().startswith("stick"))
        self.assertIn("enabled", stick)
        self.assertIn("05 78 00 80", stick)
        p0_map = next(line for line in lines[3:] if line.strip().startswith("map"))
        self.assertIn("P1->A", p0_map)

    def test_map_entry_names(self) -> None:
        self.assertEqual(map_entry_name(0), "N")
        self.assertEqual(map_entry_name(0x2000), "A")
        self.assertEqual(map_entry_name(0xFF), "missing")
        self.assertEqual(map_entry_name(0x2010), "X+A")

    def test_wrong_size_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            summarize(bytes(10))


if __name__ == "__main__":
    unittest.main()
