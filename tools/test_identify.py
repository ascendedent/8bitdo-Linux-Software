"""Decoding of the identify reply. Does not open a device."""

from __future__ import annotations

import unittest

from identify import describe_identify

CAPTURED = bytes.fromhex("02226d0000001b30010000") + bytes(53)


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
