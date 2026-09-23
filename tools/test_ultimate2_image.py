"""Layout of the Ultimate 2 image. Does not open a HID device."""

from __future__ import annotations

import unittest

from packets import ULTIMATE2_TOTAL, crc16_modbus, pro2_write_chunk
from ultimate2_image import (
    DISABLED_MARK,
    ENABLE_MARK,
    FEATURE_BITS,
    FIELDS,
    MACRO_LEFT_KEY,
    MAP_KEY_NAMES,
    STICK_CLEAR_KEEP,
    button_map_at,
    field_at,
    macro_left,
    stick_record,
    trigger_byte,
    trigger_record,
    MACRO_STEP_FIELDS,
    SIXAXIS_FIELDS,
    macro_step,
    macro_step_at,
    key_map_for,
    BUTTON_KEY_TYPE,
    GETKEY_PRODUCT,
    JOY_KEY_BITS,
    MAP_ENTRY_VALUES,
    READKEY_MAP_LENGTH,
    PRODUCT_IMAGES,
    image_header_size,
    sixaxis_record,
    vibration_record,
    xinput_rumble_record,
)


class LayoutTests(unittest.TestCase):
    def test_index_zero_records_fit_and_do_not_overlap(self) -> None:
        spans = []
        for name in FIELDS:
            offset, size = field_at(name, 0)
            self.assertGreaterEqual(offset, 0)
            self.assertLessEqual(offset + size, ULTIMATE2_TOTAL)
            spans.append((offset, offset + size, name))
        spans.append((*button_map_at(0, 0), "button_map"))
        spans.sort()
        for (a0, a1, an), (b0, b1, bn) in zip(spans, spans[1:]):
            self.assertLessEqual(a1, b0, f"{an} overlaps {bn}")

    def test_known_bases(self) -> None:
        self.assertEqual(field_at("name", 0), (0x00, 4))
        self.assertEqual(field_at("name", 2), (0x08, 4))
        self.assertEqual(field_at("vibration", 1), (0x80, 0x0C))
        self.assertEqual(field_at("stick", 0), (0x98, 8))
        self.assertEqual(field_at("stick", 2), (0xA8, 8))
        self.assertEqual(field_at("trigger", 0), (0xB0, 8))
        self.assertEqual(field_at("special", 0), (0xC8, 8))
        self.assertEqual(button_map_at(0, 0), (0xE4, 4))
        self.assertEqual(button_map_at(1, 2), (0xE4 + 0x5C + 8, 4))
        self.assertEqual(len(MAP_KEY_NAMES), 22)
        self.assertEqual(4 + 4 * len(MAP_KEY_NAMES), 0x5C)
        self.assertEqual(MAP_KEY_NAMES[0], "A")
        self.assertEqual(MAP_KEY_NAMES[12], "Menu")
        self.assertEqual(MAP_KEY_NAMES[18:], ("P1", "P2", "P3", "P4"))
        self.assertEqual(field_at("macro", 0), (0x1F4, 0xD8))
        self.assertEqual(field_at("sixaxis", 0), (0x494, 0x0C))
        self.assertEqual(field_at("hotwheel", 1), (0x4EC, 0x10))
        self.assertEqual(field_at("x_rumble", 0), (0x47C, 8))
        self.assertEqual(field_at("x_rumble", 2)[0] + 8, field_at("sixaxis", 0)[0])
        self.assertEqual(field_at("file_name", 2)[0] + 0x20, field_at("vibration", 0)[0])
        self.assertEqual(field_at("macro", 2)[0] + 0xD8, field_at("x_rumble", 0)[0])
        self.assertEqual(8 + 4 * 52, 0xD8)
        self.assertEqual(macro_step_at(0, 0), (0x1F4 + 8, 52))
        self.assertEqual(macro_step_at(2, 3)[0] + 52, field_at("x_rumble", 0)[0])
        self.assertEqual(field_at("single", 2)[0] + 0x64, ULTIMATE2_TOTAL)

    def test_stick_write_places_eight_bytes_at_0x98(self) -> None:
        offset, size = field_at("stick", 0)
        data = bytes(range(size))
        packet = pro2_write_chunk(
            offset, ULTIMATE2_TOTAL, data, nbytes=size, checksum=True
        )
        self.assertEqual(packet[3:5], bytes.fromhex("0100"))
        self.assertEqual(int.from_bytes(packet[7:9], "little"), size)
        self.assertEqual(int.from_bytes(packet[15:19], "little"), 0x98)
        self.assertEqual(packet[19 : 19 + size], data)
        self.assertEqual(int.from_bytes(packet[9:11], "little"), crc16_modbus(data))

    def test_stick_record_is_flag_then_start_and_end(self) -> None:
        record = stick_record()
        self.assertEqual(len(record), field_at("stick", 0)[1])
        self.assertEqual(record, bytes.fromhex("00000000 00800080"))
        self.assertNotIn(macro_left(), record)
        held = stick_record(10, 20, 30, 40, flag=ENABLE_MARK)
        self.assertEqual(held[:4], ENABLE_MARK.to_bytes(4, "little"))
        self.assertEqual(held[4:], bytes((10, 20, 30, 40)))

    def test_macro_center_is_127_127_and_not_the_analog_record(self) -> None:
        self.assertEqual(macro_left(), bytes((127, 127)))
        self.assertEqual(int.from_bytes(macro_left(), "little"), 0x7F7F)
        self.assertEqual(MACRO_LEFT_KEY["center"], 38)
        self.assertEqual(macro_left("up"), bytes((0x7F, 0x00)))
        self.assertEqual(macro_left("left"), bytes((0x00, 0x7F)))
        self.assertEqual(macro_left("right_down"), bytes((0xFF, 0xFF)))

    def test_trigger_and_vibration_defaults(self) -> None:
        trigger = trigger_record()
        self.assertEqual(trigger[4:], bytes((0, 255, 0, 255)))
        switched = trigger_record(switch_trigger=True)
        self.assertEqual(switched[4:], bytes((77, 255, 77, 255)))
        self.assertEqual(trigger_byte(0), 0)
        self.assertEqual(trigger_byte(50), 127)
        self.assertEqual(trigger_byte(100), 255)
        rumble = vibration_record()
        self.assertEqual(len(rumble), field_at("vibration", 0)[1])
        self.assertEqual(rumble[:4], ENABLE_MARK.to_bytes(4, "little"))
        self.assertEqual(rumble[4:], bytes.fromhex("0000803f0000803f"))
        self.assertEqual(DISABLED_MARK, 0x20190000)
        xrumble = xinput_rumble_record()
        self.assertEqual(xrumble, bytes.fromhex("11092020 01640164"))
        self.assertEqual(len(xrumble), 8)
        self.assertNotEqual(xrumble[4:], rumble[4:])

    def test_macro_step_places_fields_around_the_pad(self) -> None:
        blank = macro_step()
        self.assertEqual(blank, bytes(52))
        step = macro_step(
            file_name=b"A",
            gamepad_mode=2,
            special_flag=3,
            max_steps=4,
            step_offset=5,
            key_map=0x11223344,
            cycles_num=6,
            interval_ms=7,
        )
        self.assertEqual(step[0:32], b"A" + bytes(31))
        self.assertEqual(step[32:38], bytes((2, 3, 4, 0, 5, 0)))
        self.assertEqual(step[38:40], b"\x00\x00")
        self.assertEqual(step[40:44], bytes.fromhex("44332211"))
        self.assertEqual(step[44:52], bytes.fromhex("06000000 07000000"))
        covered = []
        for name, (off, size) in MACRO_STEP_FIELDS.items():
            covered.append((off, off + size, name))
        covered.append((38, 40, "pad"))
        covered.sort()
        self.assertEqual(covered[0][0], 0)
        self.assertEqual(covered[-1][1], 52)
        for (a0, a1, an), (b0, b1, bn) in zip(covered, covered[1:]):
            self.assertEqual(a1, b0, f"{an} to {bn}")
        body = sixaxis_record(sensitivity=5, dead_compensate=6, flag=ENABLE_MARK)
        self.assertEqual(len(body), field_at("sixaxis", 0)[1])
        self.assertEqual(body[0:4], ENABLE_MARK.to_bytes(4, "little"))
        self.assertEqual(body[8:], bytes((0, 5, 6, 0)))
        self.assertEqual(sum(size for _off, size in SIXAXIS_FIELDS.values()), 12)
        self.assertEqual(key_map_for("START"), 1)
        self.assertEqual(key_map_for("A"), 1 << 13)
        self.assertEqual(key_map_for("L3"), 1 << 1)
        self.assertEqual(key_map_for("AS_P1"), 1 << 25)
        self.assertEqual(key_map_for("AS_P1", ultimate_bt2=True), 1 << 26)
        self.assertEqual(key_map_for("AS_P2", ultimate_bt2=True), 1 << 25)

    def test_dead_zone_is_a_special_bit_clear_sticks_removes(self) -> None:
        self.assertEqual(FEATURE_BITS["dead_zone"], 0x1000)
        self.assertEqual(FEATURE_BITS["left_x_flip"], 0x0001)
        self.assertEqual(STICK_CLEAR_KEEP & FEATURE_BITS["dead_zone"], 0)
        self.assertEqual(STICK_CLEAR_KEEP & FEATURE_BITS["left_x_flip"], 0)
        self.assertEqual(STICK_CLEAR_KEEP & FEATURE_BITS["trigger_swap"], FEATURE_BITS["trigger_swap"])

    def test_a_third_stick_is_the_last_that_fits_before_trigger(self) -> None:
        self.assertEqual(field_at("stick", 2)[0] + 8, field_at("trigger", 0)[0])
        self.assertEqual(field_at("vibration", 2)[0] + 0x0C, field_at("stick", 0)[0])
        self.assertEqual(field_at("trigger", 2)[0] + 8, field_at("special", 0)[0])



class GetKeyTailTests(unittest.TestCase):
    def test_every_named_button_has_an_id(self) -> None:
        self.assertEqual(BUTTON_KEY_TYPE["A"], 11)
        self.assertEqual(BUTTON_KEY_TYPE["Record"], 40)
        self.assertEqual(len(BUTTON_KEY_TYPE), 51)
        for name in GETKEY_PRODUCT["hitbox"]:
            self.assertIn(name, BUTTON_KEY_TYPE)

    def test_untested_ids_store_zero(self) -> None:
        for name in ("Home", "turbo", "screenshot", "Swap", "Macro1", "Combo5", "N"):
            self.assertEqual(key_map_for(name), 0, name)
        self.assertEqual(key_map_for("Record"), 0)
        self.assertEqual(key_map_for("LS_Left"), 0)
        with self.assertRaises(ValueError):
            key_map_for("not a button")

    def test_pro3_record_and_hitbox_sticks(self) -> None:
        self.assertEqual(key_map_for("Record", product="pro3"), 1 << 19)
        self.assertEqual(key_map_for("LS_Left", product="hitbox"), 1 << 19)
        self.assertEqual(key_map_for("LS_Up", product="hitbox"), key_map_for("AS_P5"))
        self.assertEqual(key_map_for("LS_Right", product="hitbox"), 1 << 28)
        self.assertEqual(key_map_for("LS_Down", product="hitbox"), 1 << 29)
        swap = 1 << 27
        self.assertEqual(key_map_for("RS_Up", product="hitbox"), swap | key_map_for("START"))
        self.assertEqual(key_map_for("RS_Down", product="hitbox"), swap | key_map_for("L3"))
        self.assertEqual(key_map_for("RS_Left", product="hitbox"), swap | key_map_for("R3"))
        self.assertEqual(key_map_for("RS_Right", product="hitbox"), swap | key_map_for("SELECT"))
        # The tails do not change the common buttons.
        self.assertEqual(key_map_for("A", product="hitbox"), key_map_for("A"))
        self.assertEqual(key_map_for("AS_P1", product="pro3"), 1 << 25)

    def test_map_entries_match_getkey_for_the_low_bits(self) -> None:
        for name, gk in (("Start", "START"), ("Select", "SELECT"), ("L1", "L"), ("R1", "R"),
                         ("A", "A"), ("R2", "R2"), ("Home", "switchHome"), ("Turbo", "Share"),
                         ("P1", "AS_P1"), ("P5", "AS_P5")):
            self.assertEqual(MAP_ENTRY_VALUES[name], key_map_for(gk), name)
        self.assertEqual(MAP_ENTRY_VALUES["RS_Up"], MAP_ENTRY_VALUES["Swap"] | MAP_ENTRY_VALUES["Start"])
        self.assertEqual(MAP_ENTRY_VALUES["LS_Right"], MAP_ENTRY_VALUES["Swap"] | 0x80)
        self.assertEqual(MAP_ENTRY_VALUES["HitBox_LS_Left"], GETKEY_PRODUCT["hitbox"]["LS_Left"])
        self.assertEqual(READKEY_MAP_LENGTH["ultimate2"], len(MAP_KEY_NAMES))
        self.assertEqual(READKEY_MAP_LENGTH["hitbox2"], 24)
        self.assertEqual(sum(JOY_KEY_BITS.values()), 0xFF)

    def test_product_images_agree_with_the_ultimate2_layout(self) -> None:
        size, profiles, keys = PRODUCT_IMAGES["ultimate2"]
        self.assertEqual(size, ULTIMATE2_TOTAL)
        self.assertEqual(profiles, 3)
        self.assertEqual(keys, len(MAP_KEY_NAMES))
        self.assertEqual(image_header_size(3), field_at("file_name", 0)[0])
        self.assertEqual(4 + 4 * keys, 0x5C)
        for name, (isize, iprof, ikeys) in PRODUCT_IMAGES.items():
            self.assertEqual(ikeys, READKEY_MAP_LENGTH[name], name)
            self.assertGreater(isize, image_header_size(iprof) + 0x20 * iprof + iprof * (4 + 4 * ikeys))


if __name__ == "__main__":
    unittest.main()
