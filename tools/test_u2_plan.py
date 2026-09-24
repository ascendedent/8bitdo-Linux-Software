"""The Ultimate 2 write planner against a synthetic image. Nothing is sent."""

from __future__ import annotations

import struct
import unittest

import packets
import ultimate2_image as u2
from test_u2_summary import synthetic
from u2_plan import Plan, plan_full, plan_map, plan_stick, plan_trigger, plan_vibration


def fresh() -> Plan:
    image = synthetic()
    return Plan(image, bytearray(image))


class FieldPlans(unittest.TestCase):
    def test_stick_changes_eight_bytes_and_sends_one_chunk_then_commit(self) -> None:
        plan = fresh()
        plan_stick(plan, 1, 5, 128, 7, 120)
        offset, size = u2.field_at("stick", 1)
        expected = u2.stick_record(5, 128, 7, 120, u2.ENABLE_MARK)
        self.assertEqual(plan.changed(), [(offset, plan.original[offset : offset + size], expected)])
        self.assertEqual(
            plan.chunks, [packets.pro2_write_chunk(offset, u2.ULTIMATE2_SIZE, expected, nbytes=8, checksum=True, size_byte=False)]
        )
        pkts = plan.packets()
        self.assertEqual(len(pkts), 2)
        self.assertTrue(all(len(p) == 64 and p[0] == 0x81 for p in pkts))
        self.assertEqual(pkts[-1], packets.pad_report(packets.pro2_commit(size_byte=False)))
        # The chunk carries the record's own CRC, since 6012 is a CRC product.
        body = plan.chunks[0][2:]  # 81 04, then the 16-byte header
        self.assertEqual(int.from_bytes(body[0:2], "little"), packets.PRO2_WRITE)
        self.assertEqual(int.from_bytes(body[4:8], "little") >> 16, packets.crc16_modbus(expected))
        self.assertEqual(int.from_bytes(body[12:16], "little"), offset)

    def test_trigger_and_vibration(self) -> None:
        plan = fresh()
        plan_trigger(plan, 2, 10, 255, 10, 255)
        plan_vibration(plan, 0, 0.5, 0.25)
        offsets = [c[2 + 12 : 2 + 16] for c in plan.chunks]
        self.assertEqual(
            [int.from_bytes(o, "little") for o in offsets],
            [u2.field_at("trigger", 2)[0], u2.field_at("vibration", 0)[0]],
        )
        off = u2.field_at("vibration", 0)[0]
        self.assertEqual(struct.unpack_from("<ff", plan.image, off + 4), (0.5, 0.25))

    def test_map_sets_flag_and_keys(self) -> None:
        plan = fresh()
        plan_map(plan, 0, {"P1": "A", "P2": "Select"})
        flag_offset = u2.MAP_BASE - 4
        self.assertEqual(struct.unpack_from("<I", plan.image, flag_offset)[0], u2.ENABLE_MARK)
        p2, _ = u2.button_map_at(0, u2.MAP_KEY_NAMES.index("P2"))
        self.assertEqual(struct.unpack_from("<I", plan.image, p2)[0], u2.MAP_ENTRY_VALUES["Select"])
        self.assertEqual(len(plan.chunks), 3)
        with self.assertRaises(ValueError):
            plan_map(plan, 0, {"P9": "A"})
        with self.assertRaises(ValueError):
            plan_map(plan, 0, {"P1": "Fire"})

    def test_profile_range(self) -> None:
        with self.assertRaises(ValueError):
            plan_stick(fresh(), 3, 0, 128, 0, 128)


class FullPlan(unittest.TestCase):
    def test_full_save_seals_crc_and_covers_the_image(self) -> None:
        plan = fresh()
        plan_full(plan)
        self.assertEqual(struct.unpack_from("<I", plan.image, 12)[0], packets.crc16_modbus(plan.original))
        self.assertEqual(len(plan.chunks), 36)
        total = 0
        for chunk in plan.chunks:
            body = chunk[2:]
            length = int.from_bytes(body[4:8], "little") & 0xFFFF
            self.assertEqual(int.from_bytes(body[8:12], "little"), u2.ULTIMATE2_SIZE)
            self.assertEqual(int.from_bytes(body[12:16], "little"), total)
            self.assertEqual(body[16 : 16 + length], bytes(plan.image[total : total + length]))
            total += length
        self.assertEqual(total, u2.ULTIMATE2_SIZE)
        self.assertEqual(plan.packets()[-1], packets.pad_report(packets.pro2_commit(size_byte=False)))


if __name__ == "__main__":
    unittest.main()
