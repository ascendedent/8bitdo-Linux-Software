"""The read tool's allowlist. Does not open a device."""

from __future__ import annotations

import unittest

import packets
from read_config import allowed


class AllowlistTests(unittest.TestCase):
    def test_reads_pass(self) -> None:
        for packet in (
            packets.pad_report(packets.IDENTIFY_GET_PID),
            packets.pad_report(packets.IDENTIFY_INIT),
            packets.read_crc(),
            packets.pad_report(packets.pro2_read_chunk(0, packets.ULTIMATE2_TOTAL)),
            packets.pad_report(packets.pro2_read_chunk(0x62D, packets.ULTIMATE2_TOTAL)),
            packets.pad_report(packets.custom_info_chunk(0x21C)),
            packets.pad_report(packets.PROBE_IS_WIRED),
            packets.pad_report(packets.PROBE_GET_RF_ADDRESS),
            packets.pad_report(packets.PROBE_GET_PID),
        ):
            self.assertTrue(allowed(packet), packet.hex())

    def test_state_changing_prefixes_are_refused(self) -> None:
        for payload in (
            "810566aa63",  # byte 1 would be stored as a mode flag
            "810066aa64",  # set RF address, wipes the settings record
            "8105006101",  # product-string selector, flash write
            "8105005100",  # reboot
            "81050036",  # sets a mode flag
            "81050038",  # calibration reply, samples the sticks
            "8111040800",  # rumble
            "8105005100",  # switch to DInput, refused unless armed by --switch-to-dinput --yes
        ):
            self.assertFalse(allowed(packets.pad_report(bytes.fromhex(payload))), payload)

    def test_no_size_byte_read_frame_passes(self) -> None:
        self.assertTrue(allowed(packets.pad_report(packets.pro2_read_chunk(0, 0x638, **packets.frame_for(0x6012)))))

    def test_writes_commit_and_init1_are_refused(self) -> None:
        for packet in (
            packets.pad_report(packets.pro2_write_chunk(0, packets.ULTIMATE2_TOTAL, bytes(45))),
            packets.pad_report(packets.pro2_commit()),
            packets.init_device1(),
            packets.class05(bytes.fromhex("c40008")),
            packets.class05(bytes.fromhex("0400")),
            packets.class05(bytes.fromhex("0700")),
            bytes(64),
        ):
            self.assertFalse(allowed(packet), packet.hex())


if __name__ == "__main__":
    unittest.main()
