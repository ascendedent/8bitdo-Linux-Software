#!/usr/bin/env python3
"""Decode a 1592-byte Ultimate 2 config image into readable fields.

Offsets come from tools/ultimate2_image.py, which was read out of
Ultimate Software V2 1.35. The image is what tools/read_config.py saves
after a complete request-2 read from an Ultimate 2 (6012). Nothing here
opens a device.

    python3 tools/u2_summary.py captures/exports/6012_<time>_u2.bin
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ultimate2_image as u2  # noqa: E402
from packets import crc16_modbus  # noqa: E402

PROFILES = 3
MARKS = {u2.ENABLE_MARK: "enabled", u2.DISABLED_MARK: "not enabled"}
_VALUE_NAMES = {v: k for k, v in reversed(list(u2.MAP_ENTRY_VALUES.items()))}


def mark(value: int) -> str:
    return MARKS.get(value, f"{value:#010x}")


def map_entry_name(value: int) -> str:
    if value == u2.MAP_ENTRY_MISSING:
        return "missing"
    if value in _VALUE_NAMES:
        return _VALUE_NAMES[value]
    bits = [k for k, v in u2.MAP_ENTRY_VALUES.items() if v and v & value == v and bin(v).count("1") == 1]
    return "+".join(bits) if bits else f"{value:#010x}"


def profile_name(image: bytes, index: int) -> str:
    off, size = u2.field_at("file_name", index)
    raw = image[off : off + size]
    # V2 does not say whether the 32 bytes are UTF-16 or UTF-8. An ASCII
    # name in UTF-16LE has every odd byte zero; in UTF-8 it does not.
    if raw[0] and not any(raw[1:16:2]):
        text = raw.decode("utf-16le", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    return text.split("\x00", 1)[0]


def summarize(image: bytes) -> list[str]:
    if len(image) != u2.ULTIMATE2_SIZE:
        raise ValueError(f"expected {u2.ULTIMATE2_SIZE} bytes, got {len(image)}")
    out: list[str] = []
    flags = struct.unpack_from("<3I", image, 0)
    # flag[3], then crc_value, then gamepad_mode and cur_slot as uint16,
    # which is what puts file_name at 0x14.
    crc, mode, slot = struct.unpack_from("<IHH", image, 12)
    out.append("header flags: " + ", ".join(mark(f) for f in flags))
    out.append(f"crc_value {crc:#010x}, gamepad_mode {mode}, cur_slot {slot}")
    # V2 stores ANSI_CRC_16_Ultimate2(image), a CRC-16/MODBUS over all 1592
    # bytes as they were read, into crc_value. Which range the pad itself
    # checks is unknown, so print the candidates for the first real image.
    zeroed = bytearray(image)
    zeroed[12:16] = bytes(4)
    out.append(
        "crc16 candidates: whole image as stored "
        f"{crc16_modbus(image):#06x}, crc_value zeroed {crc16_modbus(bytes(zeroed)):#06x}, "
        f"bytes 16 on {crc16_modbus(image[16:]):#06x}"
    )
    for p in range(PROFILES):
        out.append(f"profile {p}: name {profile_name(image, p)!r}")
        for name in ("vibration", "stick", "trigger", "special", "x_rumble", "sixaxis"):
            off, size = u2.field_at(name, p)
            rec = image[off : off + size]
            flag = struct.unpack_from("<I", rec, 0)[0]
            out.append(f"  {name:9s} @{off:#05x}: {mark(flag):12s} {rec[4:].hex(' ')}")
        base = u2.MAP_BASE + p * u2.MAP_PROFILE_STRIDE
        map_flag = struct.unpack_from("<I", image, base - 4)[0]
        keys = []
        for b, button in enumerate(u2.MAP_KEY_NAMES):
            off, _ = u2.button_map_at(p, b)
            value = struct.unpack_from("<I", image, off)[0]
            if value != u2.MAP_ENTRY_VALUES.get(button, None):
                keys.append(f"{button}->{map_entry_name(value)}")
        out.append(f"  map       @{base - 4:#05x}: {mark(map_flag):12s} " + (", ".join(keys) if keys else "all keys at their own value"))
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    image = Path(argv[1]).read_bytes()
    for line in summarize(image):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
