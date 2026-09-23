"""Check packet bytes against the DLL layout. Does not open a HID device."""

from __future__ import annotations

import unittest

import packets

from packets import (
    CUSTOM_INFO_CHUNK,
    CUSTOM_INFO_TOTAL,
    IDENTIFY_COMMANDS,
    ULTIMATE2_TOTAL,
    assemble_custom_info,
    crc16_modbus,
    custom_info_chunk,
    custom_info_requests,
    init_device,
    init_device1,
    pad_report,
    parse_custom_info_reply,
    parse_pro2_read_reply,
    pro2_commit,
    pro2_read_chunk,
    pro2_write_chunk,
    read_crc,
)


def fake_reply(chunk: bytes) -> bytes:
    reply = bytearray(64)
    reply[0] = 0x02
    reply[1] = 0x04
    reply[2] = 0x04
    reply[6:10] = (0x0C).to_bytes(4, "little")
    reply[10] = len(chunk)
    reply[0x12 : 0x12 + len(chunk)] = chunk
    return bytes(reply)


FIRST_CHUNK = bytes.fromhex(
    "813e04"
    "0c cccccccc cccccc"
    "2d cc 3002 0000 cccc"
)
FIRST_CHUNK += bytes([0xCC] * 45)


class PacketTests(unittest.TestCase):
    def test_identify_matches_capture(self) -> None:
        self.assertEqual(
            tuple(command.hex() for command in IDENTIFY_COMMANDS),
            ("8105002101", "8105c100"),
        )
        for command in IDENTIFY_COMMANDS:
            padded = pad_report(command)
            self.assertEqual(len(padded), 64)
            self.assertEqual(padded[0], 0x81)
            self.assertEqual(padded[len(command) :], bytes(64 - len(command)))

    def test_first_custom_info_chunk(self) -> None:
        packet = custom_info_chunk(0)
        self.assertEqual(len(packet), 64)
        self.assertEqual(packet, FIRST_CHUNK)
        self.assertEqual(packet[11], CUSTOM_INFO_CHUNK)
        self.assertEqual(int.from_bytes(packet[13:15], "little"), CUSTOM_INFO_TOTAL)
        self.assertEqual(int.from_bytes(packet[15:17], "little"), 0)

    def test_second_chunk_advances_the_offset(self) -> None:
        packet = custom_info_chunk(CUSTOM_INFO_CHUNK)
        self.assertEqual(int.from_bytes(packet[15:17], "little"), 0x2D)
        self.assertEqual(packet[11], 0x2D)
        self.assertEqual(packet[1], 0x3E)

    def test_last_chunk_is_shorter(self) -> None:
        offset = (CUSTOM_INFO_TOTAL // CUSTOM_INFO_CHUNK) * CUSTOM_INFO_CHUNK
        length = CUSTOM_INFO_TOTAL - offset
        packet = custom_info_chunk(offset)
        self.assertEqual(length, 0x14)
        self.assertEqual(packet[11], 0x14)
        self.assertEqual(packet[1], 0x14 + 17)
        self.assertEqual(len(packet), 0x14 + 19)
        self.assertEqual(int.from_bytes(packet[15:17], "little"), offset)

    def test_reply_chunk_is_taken_from_offset_0x12(self) -> None:
        reply = bytearray(64)
        reply[0] = 0x02
        reply[1] = 0x04
        reply[2] = 0x04
        reply[6:10] = (0x0C).to_bytes(4, "little")
        reply[10] = 4
        reply[0x12 : 0x16] = b"\x10\x20\x30\x40"
        self.assertEqual(parse_custom_info_reply(bytes(reply)), b"\x10\x20\x30\x40")

    def test_reply_must_match_the_dll_checks(self) -> None:
        good = bytearray(64)
        good[0] = 0x02
        good[1] = 0x04
        good[2] = 0x04
        good[6:10] = (0x0C).to_bytes(4, "little")
        good[10] = 1
        parse_custom_info_reply(bytes(good))
        for mutate in (
            lambda r: r.__setitem__(0, 0x81),
            lambda r: r.__setitem__(1, 0x05),
            lambda r: r.__setitem__(2, 0x0C),
            lambda r: r.__setitem__(slice(6, 10), (0x02).to_bytes(4, "little")),
            lambda r: r.__setitem__(10, 60),
        ):
            broken = bytearray(good)
            mutate(broken)
            with self.assertRaises(ValueError):
                parse_custom_info_reply(bytes(broken))
        with self.assertRaises(ValueError):
            parse_custom_info_reply(bytes(good[:-1]))

    def test_reassembly_fills_560_bytes(self) -> None:
        requests = custom_info_requests()
        self.assertEqual(len(requests), 13)
        self.assertEqual(int.from_bytes(requests[1][15:17], "little"), 45)
        self.assertEqual(int.from_bytes(requests[-1][15:17], "little"), 540)
        self.assertEqual(requests[-1][11], 20)
        pieces = [bytes([n]) * (45 if n < 12 else 20) for n in range(13)]
        image = assemble_custom_info([fake_reply(piece) for piece in pieces])
        self.assertEqual(len(image), 560)
        self.assertEqual(image[:45], bytes(45))
        self.assertEqual(image[540:], bytes([12]) * 20)

    def test_a_rejected_reply_does_not_advance(self) -> None:
        good = fake_reply(b"\xab" * 45)
        bad = bytearray(good)
        bad[0] = 0x00
        pieces = [bytes([n + 1]) * 45 for n in range(12)] + [bytes([13]) * 20]
        replies = [fake_reply(piece) for piece in pieces]
        replies.insert(1, bytes(bad))
        image = assemble_custom_info(replies)
        self.assertEqual(image[:45], bytes([1]) * 45)
        self.assertEqual(image[45:90], bytes([2]) * 45)

    def test_thirty_empty_replies_stop_short(self) -> None:
        empty = fake_reply(b"")
        with self.assertRaises(ValueError):
            assemble_custom_info([empty] * 30)
        with self.assertRaises(ValueError):
            assemble_custom_info([fake_reply(b"\x01")] * 30)

    def test_short_commands(self) -> None:
        self.assertEqual(init_device()[:4], bytes.fromhex("8105c100"))
        self.assertEqual(init_device()[4:], bytes(60))
        self.assertEqual(init_device1()[:6], bytes.fromhex("8105c1000080"))
        self.assertEqual(init_device1()[6:], bytes(58))
        self.assertEqual(read_crc()[:10], bytes.fromhex("8105c30000000c000000"))
        self.assertEqual(len(init_device()), 64)
        self.assertEqual(len(read_crc()), 64)

    def test_pro2_style_custom_info_chunk(self) -> None:
        packet = pro2_read_chunk(0, CUSTOM_INFO_TOTAL)
        self.assertEqual(
            packet[:19],
            bytes.fromhex("813e04 02000000 2d000000 30020000 00000000"),
        )
        self.assertEqual(packet[19:], bytes([0xCC] * 45))
        self.assertEqual(crc16_modbus(b"123456789"), 0x4B37)
        signed = pro2_read_chunk(0, CUSTOM_INFO_TOTAL, checksum=True)
        crc = crc16_modbus(bytes([0xCC] * 45))
        self.assertEqual(int.from_bytes(signed[9:11], "little"), crc)
        self.assertEqual(signed[7:9], bytes.fromhex("2d00"))

    def test_ultimate2_write_and_commit(self) -> None:
        chunk = bytes(range(45))
        packet = pro2_write_chunk(0, ULTIMATE2_TOTAL, chunk, checksum=True)
        self.assertEqual(packet[3:5], bytes.fromhex("0100"))
        self.assertEqual(packet[19:64], chunk)
        self.assertEqual(int.from_bytes(packet[11:15], "little"), ULTIMATE2_TOTAL)
        self.assertEqual(int.from_bytes(packet[9:11], "little"), crc16_modbus(chunk))
        last_off = (ULTIMATE2_TOTAL // CUSTOM_INFO_CHUNK) * CUSTOM_INFO_CHUNK
        last_len = ULTIMATE2_TOTAL - last_off
        self.assertEqual(last_len, 17)
        tail = bytes([0xA5]) * last_len
        last = pro2_write_chunk(last_off, ULTIMATE2_TOTAL, tail, checksum=True)
        self.assertEqual(last[19:], tail)
        self.assertEqual(int.from_bytes(last[15:19], "little"), last_off)
        commit = pro2_commit()
        self.assertEqual(commit, bytes.fromhex("81110406002301") + bytes(12))
        plain = pro2_write_chunk(0, CUSTOM_INFO_TOTAL, b"\x11" * 45, checksum=False)
        self.assertEqual(plain[7:11], bytes.fromhex("2d000000"))

    def test_ultimate2_read_is_the_same_framing(self) -> None:
        packet = pro2_read_chunk(0, ULTIMATE2_TOTAL, checksum=True)
        self.assertEqual(int.from_bytes(packet[11:15], "little"), ULTIMATE2_TOTAL)
        self.assertEqual(packet[3:5], bytes.fromhex("0200"))

    def test_pro2_reply(self) -> None:
        reply = bytearray(64)
        reply[0] = 0x02
        reply[1] = 0x04
        reply[2:4] = (4).to_bytes(2, "little")
        reply[4:6] = (2).to_bytes(2, "little")
        reply[6:10] = (3).to_bytes(4, "little")
        reply[0x12:0x15] = b"\x01\x02\x03"
        self.assertEqual(parse_pro2_read_reply(bytes(reply)), b"\x01\x02\x03")
        reply[4] = 0
        with self.assertRaises(ValueError):
            parse_pro2_read_reply(bytes(reply))

    def test_offset_past_the_end_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            custom_info_chunk(CUSTOM_INFO_TOTAL + 1)
        with self.assertRaises(ValueError):
            custom_info_chunk(-1)


class ReadReplyCrc(unittest.TestCase):
    def reply(self, chunk: bytes, crc: int) -> bytes:
        reply = bytearray(64)
        reply[0:2] = b"\x02\x04"
        reply[2:4] = (4).to_bytes(2, "little")
        reply[4:6] = packets.PRO2_READ.to_bytes(2, "little")
        reply[6:10] = (len(chunk) | crc << 16).to_bytes(4, "little")
        reply[0x12 : 0x12 + len(chunk)] = chunk
        return bytes(reply)

    def test_length_is_the_low_half_and_crc_is_checked_for_crc_products(self) -> None:
        chunk = bytes(range(45))
        good = self.reply(chunk, packets.crc16_modbus(chunk))
        self.assertEqual(packets.parse_pro2_read_reply(good), chunk)
        self.assertEqual(packets.parse_pro2_read_reply(good, checksum=True), chunk)
        bad = self.reply(chunk, 0x1234)
        self.assertEqual(packets.parse_pro2_read_reply(bad), chunk)
        with self.assertRaises(ValueError):
            packets.parse_pro2_read_reply(bad, checksum=True)


class WriteAck(unittest.TestCase):
    def ack(self, request: int) -> bytes:
        reply = bytearray(64)
        reply[0:2] = b"\x02\x04"
        reply[2:4] = (4).to_bytes(2, "little")
        reply[4:6] = request.to_bytes(2, "little")
        return bytes(reply)

    def test_ack_echoes_the_request(self) -> None:
        packets.parse_write_ack(self.ack(packets.PRO2_WRITE), packets.PRO2_WRITE)
        packets.parse_write_ack(self.ack(packets.PRO2_COMMIT), packets.PRO2_COMMIT)
        with self.assertRaises(ValueError):
            packets.parse_write_ack(self.ack(packets.PRO2_WRITE), packets.PRO2_COMMIT)
        with self.assertRaises(ValueError):
            packets.parse_write_ack(bytes(64), packets.PRO2_WRITE)
        with self.assertRaises(ValueError):
            packets.parse_write_ack(self.ack(packets.PRO2_WRITE)[:63], packets.PRO2_WRITE)


if __name__ == "__main__":
    unittest.main()
