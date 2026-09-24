#!/usr/bin/env python3
"""Plan an Ultimate 2 setting change without sending it.

Takes a 1592-byte image read from an Ultimate 2 (tools/read_config.py
--pid 6012), applies one change the way Ultimate Software V2 1.35 does,
and prints the exact packets V2 would send for it. It writes the planned
image next to the input. It opens no device, and no tool in this repo
sends a write; that stays out until a real image has confirmed the layout.

What V2 does, from 8BitDoAdvance.dll and the managed assembly
(spec/protocol.md, tools/ultimate2_image.py):

- A per-field writer (writeUltimate2Sticks, Trigger, Vibration, ...)
  sends one request-1 chunk holding just that record at its image
  offset, with the chunk CRC the Ultimate 2 requires, waits 100 ms, then
  sends request 6 with argument 0x123 (the commit). The record's flag is
  set to the enable mark.
- A full save (writeUltimate2) first stores ANSI_CRC_16_Ultimate2 of the
  image as read, a CRC-16/MODBUS over all 1592 bytes, into crc_value,
  then sends the whole image in 45-byte request-1 chunks, then commits.
- Button maps use the per-key writer, a 4-byte chunk per key plus the
  profile's 4-byte flag, then commit. That path is modelled on the
  writer table in spec/protocol.md and has not been traced end to end.

    python3 tools/u2_plan.py IMAGE --profile 0 --stick 5 128 5 128
    python3 tools/u2_plan.py IMAGE --profile 1 --trigger 0 255 0 255
    python3 tools/u2_plan.py IMAGE --profile 0 --vibration 0.5 0.5
    python3 tools/u2_plan.py IMAGE --profile 0 --map P1=A P2=B
    python3 tools/u2_plan.py IMAGE --full
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import packets  # noqa: E402
import ultimate2_image as u2  # noqa: E402

TOTAL = u2.ULTIMATE2_SIZE
PROFILES = 3
COMMIT_DELAY_MS = 100


@dataclass
class Plan:
    original: bytes
    image: bytearray
    steps: list[str] = field(default_factory=list)
    chunks: list[bytes] = field(default_factory=list)

    def changed(self) -> list[tuple[int, bytes, bytes]]:
        """Runs of (offset, old, new) that differ."""
        runs: list[tuple[int, bytes, bytes]] = []
        i = 0
        while i < TOTAL:
            if self.original[i] == self.image[i]:
                i += 1
                continue
            j = i
            while j < TOTAL and self.original[j] != self.image[j]:
                j += 1
            runs.append((i, self.original[i:j], bytes(self.image[i:j])))
            i = j
        return runs

    def packets(self) -> list[bytes]:
        """The chunks, then the commit, each as the 64-byte report V2 writes."""
        return [packets.pad_report(c) for c in self.chunks] + [packets.pad_report(packets.pro2_commit(size_byte=False))]


def load(path: Path) -> bytes:
    image = path.read_bytes()
    if len(image) != TOTAL:
        raise SystemExit(f"{path}: expected {TOTAL} bytes, got {len(image)}")
    return image


def _check_profile(profile: int) -> None:
    if not 0 <= profile < PROFILES:
        raise ValueError(f"profile {profile} is not 0..{PROFILES - 1}")


def _field_chunk(plan: Plan, name: str, profile: int, record: bytes, what: str) -> None:
    offset, size = u2.field_at(name, profile)
    if len(record) != size:
        raise ValueError(f"{name} record is {len(record)} bytes, field is {size}")
    plan.image[offset : offset + size] = record
    plan.chunks.append(packets.pro2_write_chunk(offset, TOTAL, record, nbytes=size, checksum=True, size_byte=False))
    plan.steps.append(f"{what}: one chunk of {size} bytes at {offset:#x}")


def plan_stick(plan: Plan, profile: int, ls: int, le: int, rs: int, re_: int) -> None:
    _check_profile(profile)
    _field_chunk(plan, "stick", profile, u2.stick_record(ls, le, rs, re_, u2.ENABLE_MARK), f"stick profile {profile}")


def plan_trigger(plan: Plan, profile: int, ls: int, le: int, rs: int, re_: int) -> None:
    _check_profile(profile)
    _field_chunk(plan, "trigger", profile, u2.trigger_record(ls, le, rs, re_, u2.ENABLE_MARK), f"trigger profile {profile}")


def plan_vibration(plan: Plan, profile: int, left: float, right: float) -> None:
    _check_profile(profile)
    if not (0.0 <= left <= 1.0 and 0.0 <= right <= 1.0):
        raise ValueError("vibration zoom is 0.0..1.0")
    _field_chunk(plan, "vibration", profile, u2.vibration_record(left, right, u2.ENABLE_MARK), f"vibration profile {profile}")


def plan_map(plan: Plan, profile: int, assignments: dict[str, str]) -> None:
    _check_profile(profile)
    flag_offset = u2.MAP_BASE - 4 + profile * u2.MAP_PROFILE_STRIDE
    for button, target in assignments.items():
        if button not in u2.MAP_KEY_NAMES:
            raise ValueError(f"unknown button {button}; one of {', '.join(u2.MAP_KEY_NAMES)}")
        if target not in u2.MAP_ENTRY_VALUES:
            raise ValueError(f"unknown target {target}; one of {', '.join(u2.MAP_ENTRY_VALUES)}")
    flag = u2.ENABLE_MARK.to_bytes(4, "little")
    plan.image[flag_offset : flag_offset + 4] = flag
    plan.chunks.append(packets.pro2_write_chunk(flag_offset, TOTAL, flag, nbytes=4, checksum=True, size_byte=False))
    plan.steps.append(f"map profile {profile}: flag chunk at {flag_offset:#x}")
    for button, target in assignments.items():
        offset, size = u2.button_map_at(profile, u2.MAP_KEY_NAMES.index(button))
        value = u2.MAP_ENTRY_VALUES[target].to_bytes(4, "little")
        plan.image[offset : offset + size] = value
        plan.chunks.append(packets.pro2_write_chunk(offset, TOTAL, value, nbytes=size, checksum=True, size_byte=False))
        plan.steps.append(f"map profile {profile}: {button} -> {target}, chunk at {offset:#x}")


def plan_full(plan: Plan) -> None:
    """writeUltimate2: crc_value from the image as read, then every chunk."""
    crc = packets.crc16_modbus(bytes(plan.image))
    struct.pack_into("<I", plan.image, 12, crc)
    plan.steps.append(f"crc_value <- CRC-16/MODBUS of the image as read, {crc:#06x}")
    image = bytes(plan.image)
    offset = 0
    n = 0
    while offset < TOTAL:
        length = min(packets.CUSTOM_INFO_CHUNK, TOTAL - offset)
        plan.chunks.append(packets.pro2_write_chunk(offset, TOTAL, image[offset:], checksum=True, size_byte=False))
        offset += length
        n += 1
    plan.steps.append(f"full image: {n} chunks of up to {packets.CUSTOM_INFO_CHUNK} bytes")


def describe(plan: Plan) -> list[str]:
    lines = ["Nothing was sent. No tool in this repo sends a write.", ""]
    lines += [f"step: {s}" for s in plan.steps]
    lines.append("")
    for offset, old, new in plan.changed():
        lines.append(f"bytes {offset:#05x}+{len(new)}: {old.hex(' ')} -> {new.hex(' ')}")
    lines.append("")
    lines.append(f"packets V2 would write, 64 bytes each, with {COMMIT_DELAY_MS} ms before the last (the commit):")
    for pkt in plan.packets():
        lines.append("  " + pkt.rstrip(b"\x00").hex(" "))
    return lines


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path, help="1592-byte image from read_config.py --pid 6012")
    ap.add_argument("--profile", type=int, default=0)
    ap.add_argument("--stick", nargs=4, type=int, metavar=("LS", "LE", "RS", "RE"))
    ap.add_argument("--trigger", nargs=4, type=int, metavar=("LS", "LE", "RS", "RE"))
    ap.add_argument("--vibration", nargs=2, type=float, metavar=("LEFT", "RIGHT"))
    ap.add_argument("--map", nargs="+", metavar="BUTTON=TARGET")
    ap.add_argument("--full", action="store_true", help="plan a full-image save instead of one field")
    ap.add_argument("--out", type=Path, help="where to write the planned image (default IMAGE.planned.bin)")
    args = ap.parse_args(argv[1:])
    chosen = [x for x in (args.stick, args.trigger, args.vibration, args.map, args.full) if x]
    if len(chosen) != 1:
        ap.error("pick exactly one of --stick, --trigger, --vibration, --map, --full")
    original = load(args.image)
    plan = Plan(original, bytearray(original))
    try:
        if args.stick:
            plan_stick(plan, args.profile, *args.stick)
        elif args.trigger:
            plan_trigger(plan, args.profile, *args.trigger)
        elif args.vibration:
            plan_vibration(plan, args.profile, *args.vibration)
        elif args.map:
            pairs = dict(item.split("=", 1) for item in args.map)
            plan_map(plan, args.profile, pairs)
        else:
            plan_full(plan)
    except ValueError as exc:
        ap.error(str(exc))
    out = args.out or args.image.with_suffix(".planned.bin")
    out.write_bytes(bytes(plan.image))
    for line in describe(plan):
        print(line)
    print(f"\nplanned image written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
