"""The volunteer read path end to end against a fake Ultimate 2 on a socket pair.

No HID device. The fake pad answers request-2 chunks from a synthetic
image the way the DLL's reply parser expects, and checks that every
request carries the chunk CRC the Ultimate 2 requires.
"""

from __future__ import annotations

import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import packets
import read_config
import ultimate2_image as u2
from test_u2_summary import synthetic


class FakeUltimate2(threading.Thread):
    """Answers the chunked read. Records every request and any complaint."""

    def __init__(self, fd: int, image: bytes, *, answer: bool = True) -> None:
        super().__init__(daemon=True)
        self.fd = fd
        self.image = image
        self.answer = answer
        self.requests: list[bytes] = []
        self.complaints: list[str] = []

    def run(self) -> None:
        while True:
            try:
                packet = os.read(self.fd, 64)
            except OSError:
                return
            if not packet:
                return
            self.requests.append(packet)
            # The class-05 identify pair, which every pad answers (docs/firmware.md).
            if packet[:5] == packets.IDENTIFY_GET_PID:
                os.write(self.fd, bytes.fromhex("02226e0000001260000000") + bytes(53))
                continue
            if packet[:4] == packets.IDENTIFY_INIT:
                os.write(self.fd, bytes.fromhex("02050000c100") + bytes(58))
                continue
            # An Ultimate 2 takes 81 04 <body>; a size byte in between makes
            # its dispatcher drop the packet (docs/firmware.md).
            if packet[0] != 0x81 or packet[1] != 0x04:
                self.complaints.append(f"not an Ultimate 2 section-04 packet: {packet[:4].hex()}")
                continue
            body = packet[2:]
            request = int.from_bytes(body[0:2], "little")
            length_word = int.from_bytes(body[4:8], "little")
            length, crc = length_word & 0xFFFF, length_word >> 16
            total = int.from_bytes(body[8:12], "little")
            offset = int.from_bytes(body[12:16], "little")
            data = body[16 : 16 + length]
            if request != packets.PRO2_READ:
                self.complaints.append(f"request {request} is not a read")
                continue
            if total != len(self.image) or offset + length > total:
                self.complaints.append(f"bad window {offset}+{length} of {total}")
                continue
            if crc != packets.crc16_modbus(data):
                self.complaints.append(f"chunk CRC {crc:#06x} at {offset:#x} is wrong")
                continue
            if not self.answer:
                continue
            # A real pad streams its input reports on the same node; make the
            # tool skip one before every reply.
            os.write(self.fd, bytes([0x01, 0x0F, 0x7F, 0x7F, 0x7F, 0x7F]) + bytes(28))
            reply = bytearray(64)
            reply[0:2] = bytes([0x02, 0x04])
            reply[2:4] = (4).to_bytes(2, "little")
            reply[4:6] = packets.PRO2_READ.to_bytes(2, "little")
            # A CRC product answers with its own CRC-16 of the chunk in the high half.
            chunk = self.image[offset : offset + length]
            reply[6:10] = (length | packets.crc16_modbus(chunk) << 16).to_bytes(4, "little")
            reply[0x12 : 0x12 + length] = self.image[offset : offset + length]
            os.write(self.fd, bytes(reply))


class LoopbackRead(unittest.TestCase):
    def setUp(self) -> None:
        self.host, self.pad = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "6012_test.txt"

    def tearDown(self) -> None:
        self.host.close()
        self.pad.close()
        self.tmp.cleanup()

    def run_tool(self, extra: list[str]) -> int:
        argv = ["--pid", "6012", "--node", "loopback", "--log", str(self.log), "--timeout-ms", "500"] + extra
        with mock.patch.object(read_config.os, "open", lambda *a, **k: self.host.fileno()):
            with mock.patch.object(read_config.os, "close", lambda fd: None):
                return read_config.main(argv)

    def test_complete_read_assembles_the_image_and_summarizes(self) -> None:
        image = synthetic()
        fake = FakeUltimate2(self.pad.fileno(), image)
        fake.start()
        self.assertEqual(self.run_tool(["--summary"]), 0)
        out = self.log.with_name(self.log.stem + "_u2.bin")
        self.assertEqual(out.read_bytes(), image)
        self.assertEqual(fake.complaints, [])
        self.assertEqual(len(fake.requests), 36 + 2)
        transcript = self.log.read_text()
        self.assertIn("complete, 1592 bytes", transcript)
        self.assertIn("skipped 1 input report", transcript)
        self.assertIn("profile 0: name 'Racing'", transcript)
        # Identify goes to every pad; the 2C-only commands never went out on a 6012.
        self.assertIn("identify", transcript)
        self.assertNotIn("readCRC", transcript)
        self.assertNotIn("is_wired", transcript)

    def test_silent_pad_leaves_no_image(self) -> None:
        fake = FakeUltimate2(self.pad.fileno(), synthetic(), answer=False)
        fake.start()
        self.assertEqual(self.run_tool([]), 0)
        self.assertFalse(self.log.with_name(self.log.stem + "_u2.bin").exists())
        self.assertIn("nothing readable", self.log.read_text())
        self.assertEqual(fake.complaints, [])
        self.assertEqual(len(fake.requests), 3 + 2)

    def test_permission_denied_points_at_the_udev_rule(self) -> None:
        def denied(*a, **k):
            raise PermissionError(13, "Permission denied")

        with mock.patch.object(read_config.os, "open", denied):
            with self.assertRaises(SystemExit) as ctx:
                read_config.main(["--pid", "6012", "--node", "/dev/hidraw99", "--log", str(self.log)])
        self.assertIn("udev/71-8bitdo.rules", str(ctx.exception))

    def test_ultimate2_in_xinput_mode_gets_the_ultimate2_frame(self) -> None:
        image = synthetic()
        fake = FakeUltimate2(self.pad.fileno(), image)
        fake.start()
        with mock.patch.dict(read_config.identify.LAST_PRODUCT, {"loopback": "8BitDo Ultimate 2 Wireless Controller for PC"}):
            argv = ["--pid", "310b", "--node", "loopback", "--log", str(self.log), "--timeout-ms", "500"]
            with mock.patch.object(read_config.os, "open", lambda *a, **k: self.host.fileno()):
                with mock.patch.object(read_config.os, "close", lambda fd: None):
                    self.assertEqual(read_config.main(argv), 0)
        self.assertEqual(fake.complaints, [])
        self.assertEqual(self.log.with_name(self.log.stem + "_u2.bin").read_bytes(), image)
        self.assertIn("config protocol: 6012", self.log.read_text())

    def test_first_chunk_matches_the_dll_shape(self) -> None:
        first = packets.pro2_read_chunk(0, u2.ULTIMATE2_SIZE, **packets.frame_for(0x6012))
        self.assertEqual(first[:2], bytes([0x81, 0x04]))
        self.assertEqual(first[2:6], bytes([0x02, 0x00, 0x00, 0x00]))
        self.assertEqual(first[10:14], bytes([0x38, 0x06, 0x00, 0x00]))
        self.assertEqual(int.from_bytes(first[6:8], "little"), 0x2D)
        older = packets.pro2_read_chunk(0, u2.ULTIMATE2_SIZE, **packets.frame_for(0x310A))
        self.assertEqual(older[:3], bytes([0x81, 0x3E, 0x04]))


if __name__ == "__main__":
    unittest.main()
