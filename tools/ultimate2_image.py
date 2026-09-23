"""Where writeUltimate2* sends bytes inside the 1592-byte image.

Each writer issues one request-type-1 chunk. The offset below is the
image offset of index 0. The 2C does not call these writers. Nothing
here opens a device.

An 8-byte stick record is joy_params_record_t: a 4-byte flag, then left
start, left end, right start, right end. Clear writes 0, 128, 0, 128
into those four bytes. Axis flips and the dead-zone switch are bits in
the separate 8-byte special record, not in these eight bytes.

0x7F7F is the macro-step center (X 127, Y 127). getLeftStick returns it
when the step has no left-stick direction. It is not stored in the
analog stick record. Sensitivity and dead-zone compensation are the
sixaxis bytes at offsets 9 and 10 of that 12-byte record, and clear
writes 0 to both.
"""

from __future__ import annotations

import struct

ULTIMATE2_SIZE = 0x638

# Ultimate2_4Advance2UI stores these in the record flag when a save
# marks the field. 0x20200911 means enabled. 0x20190000 means not.
ENABLE_MARK = 0x20200911
DISABLED_MARK = 0x20190000

# name, base, stride, size
# button_map is profile * 0x5c + button * 4, not a single stride.
FIELDS = {
    # "name" is the 4-byte header flag the Name writer sends. The 32-byte
    # profile string is file_name.
    "name": (0x00, 4, 4),
    "file_name": (0x14, 0x20, 0x20),
    "vibration": (0x74, 0x0C, 0x0C),
    "stick": (0x98, 8, 8),
    "trigger": (0xB0, 8, 8),
    "special": (0xC8, 8, 8),
    # macro is record_macro_fun: 8-byte head, then four 52-byte steps.
    "macro": (0x1F4, 0xD8, 0xD8),
    "x_rumble": (0x47C, 8, 8),
    "sixaxis": (0x494, 0x0C, 0x0C),
    "dynamic": (0x4B8, 0x0C, 0x0C),
    "hotwheel": (0x4DC, 0x10, 0x10),
    "single": (0x50C, 0x64, 0x64),
}

MAP_BASE = 0xE4
MAP_PROFILE_STRIDE = 0x5C
MAP_ENTRY = 4


def field_at(name: str, index: int = 0) -> tuple[int, int]:
    """Return (offset, size) for one record."""
    if name == "button_map":
        raise ValueError("use button_map_at")
    try:
        base, stride, size = FIELDS[name]
    except KeyError as exc:
        raise ValueError(f"unknown field {name}") from exc
    if index < 0:
        raise ValueError("index is negative")
    offset = base + index * stride
    if offset < 0 or offset + size > ULTIMATE2_SIZE:
        raise ValueError(f"{name}[{index}] {offset:#x}+{size:#x} outside the image")
    return offset, size


# One profile is 0x5c bytes: a uint32 flag, then 22 uint32 key ids.
# readkey_map fills them in this order for the Ultimate 2. Slot 12 asks
# for S_ButtonKeyType 17 (Share) and stores KEY_MENU_MAP or a turbo
# value. Slots 18-21 are the four paddles. The all-default profile the
# save compares against has 0 (KEY_NULL_MAP) in those four slots and
# swaps A/B and X/Y when gamepad_mode is 0.
MAP_KEY_NAMES = (
    "A",
    "B",
    "X",
    "Y",
    "L1",
    "R1",
    "L2",
    "R2",
    "L3",
    "R3",
    "Select",
    "Start",
    "Menu",
    "Home",
    "Up",
    "Down",
    "Left",
    "Right",
    "P1",
    "P2",
    "P3",
    "P4",
)


def button_map_at(profile: int, button: int) -> tuple[int, int]:
    """One key dword. Index 0 is A at 0xe4. The profile flag is 4 bytes earlier."""
    if profile < 0 or profile >= 3 or button < 0 or button >= len(MAP_KEY_NAMES):
        raise ValueError(f"profile {profile} button {button}")
    offset = MAP_BASE + profile * MAP_PROFILE_STRIDE + button * MAP_ENTRY
    if offset + MAP_ENTRY > ULTIMATE2_SIZE:
        raise ValueError(f"map {profile}:{button} outside the image")
    return offset, MAP_ENTRY


def _u8(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 255:
        raise ValueError(f"{name} {value}")
    return value


def stick_record(
    left_start: int = 0,
    left_end: int = 128,
    right_start: int = 0,
    right_end: int = 128,
    flag: int = 0,
) -> bytes:
    """Eight bytes. Clear leaves the flag alone and writes 0, 128, 0, 128."""
    body = bytes(
        (
            _u8("left_start", left_start),
            _u8("left_end", left_end),
            _u8("right_start", right_start),
            _u8("right_end", right_end),
        )
    )
    return int(flag).to_bytes(4, "little") + body


def trigger_record(
    left_start: int = 0,
    left_end: int = 255,
    right_start: int = 0,
    right_end: int = 255,
    flag: int = 0,
    switch_trigger: bool = False,
) -> bytes:
    """Eight bytes, same shape as a stick. Clear writes ends of 255.

    On a pad where isSupportSwitchTrigger is true, clear then sets both
    starts to 77. A save of the percent UI stores percent * 255 / 100.
    """
    if switch_trigger:
        left_start = 77
        right_start = 77
    return stick_record(left_start, left_end, right_start, right_end, flag)


def trigger_byte(percent: int) -> int:
    """Device byte for a 0-100 trigger slider: percent * 255 / 100."""
    if not isinstance(percent, int) or isinstance(percent, bool) or not 0 <= percent <= 100:
        raise ValueError(f"percent {percent}")
    return (percent * 255) // 100


def vibration_record(
    left: float = 1.0,
    right: float = 1.0,
    flag: int = ENABLE_MARK,
) -> bytes:
    """Twelve bytes. Clear sets the enable mark and both zoom floats to 1.0."""
    return int(flag).to_bytes(4, "little") + struct.pack("<ff", left, right)


# record_macro_fun_record_t. total_cnt is the byte at +4. Bytes 5-7 are
# alignment padding. Four steps follow at +8.
MACRO_HEAD = 8
MACRO_STEPS = 4
MACRO_STEP_SIZE = 52

# record_macro_content_t. Bytes 38-39 are alignment padding before key_map.
MACRO_STEP_FIELDS = {
    "file_name": (0, 32),
    "gamepad_mode": (32, 1),
    "special_flag": (33, 1),
    "max_steps": (34, 2),
    "step_offset": (36, 2),
    "key_map": (40, 4),
    "cycles_num": (44, 4),
    "interval_ms": (48, 4),
}


def macro_step_at(slot: int, step: int) -> tuple[int, int]:
    """Image offset of one 52-byte step. Slot 0..2, step 0..3."""
    if not 0 <= slot < 3 or not 0 <= step < MACRO_STEPS:
        raise ValueError(f"slot {slot} step {step}")
    base, _stride, size = FIELDS["macro"]
    offset = base + slot * size + MACRO_HEAD + step * MACRO_STEP_SIZE
    if offset + MACRO_STEP_SIZE > base + (slot + 1) * size:
        raise ValueError(f"step {slot}:{step} outside the macro")
    return offset, MACRO_STEP_SIZE


def macro_step(
    file_name: bytes = b"",
    gamepad_mode: int = 0,
    special_flag: int = 0,
    max_steps: int = 0,
    step_offset: int = 0,
    key_map: int = 0,
    cycles_num: int = 0,
    interval_ms: int = 0,
) -> bytes:
    """One cleared step, with the named fields written. Defaults are 0."""
    if len(file_name) > 32:
        raise ValueError("file_name longer than 32")
    buf = bytearray(MACRO_STEP_SIZE)
    buf[0 : len(file_name)] = file_name
    buf[32] = _u8("gamepad_mode", gamepad_mode)
    buf[33] = _u8("special_flag", special_flag)
    buf[34:36] = int(max_steps).to_bytes(2, "little")
    buf[36:38] = int(step_offset).to_bytes(2, "little")
    buf[40:44] = int(key_map).to_bytes(4, "little")
    buf[44:48] = int(cycles_num).to_bytes(4, "little")
    buf[48:52] = int(interval_ms).to_bytes(4, "little")
    return bytes(buf)


# sixaxis_params_record_t. Clear writes 0 into sensitivity and dead_compensate.
SIXAXIS_FIELDS = {
    "flag": (0, 4),
    "keys_map": (4, 4),
    "trigger_mode": (8, 1),
    "sensitivity": (9, 1),
    "dead_compensate": (10, 1),
    "mapping_type": (11, 1),
}


# S_ButtonKeyType. This is the argument of getKey and the "type" a
# readkey_map slot asks for. Ids 32-40 only mean something on the
# products listed in GETKEY_PRODUCT.
BUTTON_KEY_TYPE = {
    "N": 0,
    "L": 1,
    "R": 2,
    "L2": 3,
    "R2": 4,
    "L3": 5,
    "R3": 6,
    "Up": 7,
    "Down": 8,
    "Left": 9,
    "Right": 10,
    "A": 11,
    "B": 12,
    "X": 13,
    "Y": 14,
    "SELECT": 15,
    "START": 16,
    "Share": 17,
    "Home": 18,
    "turbo": 19,
    "turbo3": 20,
    "screenshot": 21,
    "switchHome": 22,
    "XinputHome": 23,
    "NULL": 24,
    "AutoTurbo": 25,
    "loadIniError": 26,
    "AS_P1": 27,
    "AS_P2": 28,
    "AS_P3": 29,
    "AS_P4": 30,
    "AS_P5": 31,
    "LS_Left": 32,
    "LS_Right": 33,
    "LS_Up": 34,
    "LS_Down": 35,
    "RS_Left": 36,
    "RS_Right": 37,
    "RS_Up": 38,
    "RS_Down": 39,
    "Record": 40,
    "Swap": 41,
    "Macro1": 42,
    "Macro2": 43,
    "Macro3": 44,
    "Macro4": 45,
    "Combo1": 46,
    "Combo2": 47,
    "Combo3": 48,
    "Combo4": 49,
    "Combo5": 50,
}

# getKey writes one S_ButtonKeyType into key_map as a single bit on
# every product. Bit numbers. Ultimate BT2 swaps AS_P1 and AS_P2.
KEY_MAP_BITS = {
    "START": 0,
    "L3": 1,
    "R3": 2,
    "SELECT": 3,
    "X": 4,
    "Y": 5,
    "Right": 6,
    "Left": 7,
    "Down": 8,
    "Up": 9,
    "L": 10,
    "R": 11,
    "B": 12,
    "A": 13,
    "L2": 14,
    "R2": 15,
    "Share": 16,
    "switchHome": 17,
    "AS_P5": 20,
    "AS_P3": 21,
    "AS_P1": 25,
    "AS_P2": 26,
    "AS_P4": 30,
}

# Product tails of getKey, gated on VIDPID.PID_Current. Values, not bit
# numbers, because the HitBox right-stick ids set two bits. They reuse
# bits the common table already owns: LS_Left is AS_P5's bit 20 shifted
# down to 19, LS_Up is AS_P5 itself, and RS_* are bit 27 (KeyMap_Swap)
# plus the Start, L3, R3, or Select bit. Pro 3 Record shares LS_Left's
# bit 19. The firmware for those products must read them together.
GETKEY_PRODUCT = {
    "ultimate_bt2": {"AS_P1": 1 << 26, "AS_P2": 1 << 25},
    "pro3": {"Record": 0x0008_0000},
    "hitbox": {
        "LS_Left": 0x0008_0000,
        "LS_Right": 0x1000_0000,
        "LS_Up": 0x0010_0000,
        "LS_Down": 0x2000_0000,
        "RS_Up": 0x0800_0001,
        "RS_Down": 0x0800_0002,
        "RS_Left": 0x0800_0004,
        "RS_Right": 0x0800_0008,
    },
}

# Product ids VIDPID compares against. 310a is not one of them.
PRODUCT_PIDS = {
    "pro2": 0x6003,
    "pro3": 0x6009,
    "hitbox": 0x600B,
    "ultimate_bt2": 0x600F,
    "ultimate2": 0x6012,
}

# Wire image per product UI class: (size, profiles, map keys per
# profile). Sizes are the managed custom_config_record_t structs laid
# out sequentially. Every size but the Pro 2 one also appears as an
# immediate in the native DLL. Only the Ultimate 2 layout is expanded
# in FIELDS. None of these has been sent to a device.
PRODUCT_IMAGES = {
    "pro2": (0x674, 3, 20),
    "ultimate2_4": (0x674, 3, 20),
    "ultimate_bt": (0x914, 3, 20),
    "pro3": (0x92C, 3, 22),
    "hitbox": (0x92C, 3, 22),
    "hitbox2": (0xA68, 2, 24),
    "ultimate2": (ULTIMATE2_SIZE, 3, 22),
    "ultimate_bt2": (0xAD0, 3, 22),
}

# Every image starts with flag[profiles], crc_value, gamepad_mode,
# cur_slot, then file_name[profiles]. The image header ends there.
def image_header_size(profiles: int) -> int:
    return 4 * profiles + 4 + 2 + 2


def key_map_for(button: str, ultimate_bt2: bool = False, product: str = "ultimate2") -> int:
    """Value getKey stores for one S_ButtonKeyType name.

    Buttons getKey does not test store 0, which is what the app writes
    for a macro with no trigger. That includes Home, turbo, screenshot,
    Swap, Macro*, Combo*, and the stick ids on any product but HitBox.
    """
    if button not in BUTTON_KEY_TYPE:
        raise ValueError(f"unknown button {button}")
    if ultimate_bt2:
        product = "ultimate_bt2"
    tail = GETKEY_PRODUCT.get(product, {})
    if button in tail:
        return tail[button]
    bit = KEY_MAP_BITS.get(button)
    return 0 if bit is None else 1 << bit


# AdvanceSuper.Mode.KeyMap. These are the values a button-map profile
# entry holds, from the KEY_*_MAP and DIR_*_MAP fields the save reads.
# Bits 0-17 agree with getKey after AutoR2AndHome runs changeKey, which
# every product but an old SN30 Pro+ HID gets. The stick entries are bit
# 27 (the Swap bit) plus a nibble: right stick in bits 0-3, left stick
# in bits 4-7. HitBox uses single bits 19, 20, 28, 29 for the left
# stick instead, the same values its getKey tail stores.
MAP_ENTRY_VALUES = {
    "N": 0,
    "Start": 0x0000_0001,
    "L3": 0x0000_0002,
    "R3": 0x0000_0004,
    "Select": 0x0000_0008,
    "X": 0x0000_0010,
    "Y": 0x0000_0020,
    "Right": 0x0000_0040,
    "Left": 0x0000_0080,
    "Down": 0x0000_0100,
    "Up": 0x0000_0200,
    "L1": 0x0000_0400,
    "R1": 0x0000_0800,
    "B": 0x0000_1000,
    "A": 0x0000_2000,
    "L2": 0x0000_4000,
    "R2": 0x0000_8000,
    "Turbo": 0x0001_0000,
    "Home": 0x0002_0000,
    "BT_CON": 0x0004_0000,
    "ScreenShot": 0x0040_0000,
    "Turbo_3": 0x0080_0000,
    "Turbo_Auto": 0x0100_0000,
    "P1": 0x0200_0000,
    "P2": 0x0400_0000,
    "P3": 0x0020_0000,
    "P4": 0x4000_0000,
    "P5": 0x0010_0000,
    "Swap": 0x0800_0000,
    "RS_Up": 0x0800_0001,
    "RS_Down": 0x0800_0002,
    "RS_Left": 0x0800_0004,
    "RS_Right": 0x0800_0008,
    "LS_Up": 0x0800_0010,
    "LS_Down": 0x0800_0020,
    "LS_Left": 0x0800_0040,
    "LS_Right": 0x0800_0080,
    "HitBox_LS_Left": 0x0008_0000,
    "HitBox_LS_Up": 0x0010_0000,
    "HitBox_LS_Right": 0x1000_0000,
    "HitBox_LS_Down": 0x2000_0000,
}

# mapKeyWith returns this when the UI has no mapping row for a slot.
MAP_ENTRY_MISSING = 0xFF

# How many uint32 keys readkey_map builds per product. The Ultimate 2
# profile record has room for 22.
READKEY_MAP_LENGTH = {
    "default": 18,
    "pro2": 20,
    "ultimate2_4": 20,
    "ultimate_pc": 20,
    "ultimate_bt": 20,
    "hitbox": 22,
    "pro3": 22,
    "ultimate2": 22,
    "ultimate_bt2": 22,
    "hitbox2": 24,
}

# Macro-step joystick byte from getJoyKey, used only by the Pro 2 macro
# record. Low nibble is the left stick, high nibble the right. The map
# profile stick entries above put the nibbles the other way round.
JOY_KEY_BITS = {
    "LS_Up": 0x01,
    "LS_Down": 0x02,
    "LS_Left": 0x04,
    "LS_Right": 0x08,
    "RS_Up": 0x10,
    "RS_Down": 0x20,
    "RS_Left": 0x40,
    "RS_Right": 0x80,
}


def sixaxis_record(
    sensitivity: int = 0,
    dead_compensate: int = 0,
    trigger_mode: int = 0,
    mapping_type: int = 0,
    keys_map: int = 0,
    flag: int = 0,
) -> bytes:
    """Twelve bytes. Clear zeroes the four tail bytes and keys_map."""
    buf = bytearray(12)
    buf[0:4] = int(flag).to_bytes(4, "little")
    buf[4:8] = int(keys_map).to_bytes(4, "little")
    buf[8] = _u8("trigger_mode", trigger_mode)
    buf[9] = _u8("sensitivity", sensitivity)
    buf[10] = _u8("dead_compensate", dead_compensate)
    buf[11] = _u8("mapping_type", mapping_type)
    return bytes(buf)


def xinput_rumble_record(
    left_start: int = 1,
    left_end: int = 100,
    right_start: int = 1,
    right_end: int = 100,
    flag: int = ENABLE_MARK,
) -> bytes:
    """Eight bytes at 0x47c. Clear writes ranges 1..100, not the float zoom."""
    return stick_record(left_start, left_end, right_start, right_end, flag)


# Bits of joy_trigger_special_feature_t.featrue. HandleSpecial_feature
# ORs these in. clearSticks clears the stick bits and leaves the rest.
FEATURE_BITS = {
    "left_x_flip": 0x0001,
    "left_y_flip": 0x0002,
    "right_x_flip": 0x0004,
    "right_y_flip": 0x0008,
    "stick_swap": 0x0010,
    "trigger_swap": 0x0080,
    "dpad_swap": 0x0100,
    "android": 0x0200,
    "right_stick_as_triggers": 0x0400,
    "motion": 0x0800,
    "dead_zone": 0x1000,
    "four": 0x2000,
    "trigger_sleep": 0x4000,
    "vibration": 0x8000,
    "upward": 0x10000,
    "front": 0x20000,
    "after": 0x40000,
}

# clearSticks keeps every bit set in this mask.
STICK_CLEAR_KEEP = 0xFFFFCAE0


# Macro-step left stick, from getLeftStick / S_DefineMapKey. The pair is
# (X, Y): 0, 127, 255. Center is what getLeftStick returns as 0x7F7F.
MACRO_LEFT = {
    "left_up": (0x00, 0x00),
    "up": (0x7F, 0x00),
    "right_up": (0xFF, 0x00),
    "left": (0x00, 0x7F),
    "right": (0xFF, 0x7F),
    "left_down": (0x00, 0xFF),
    "down": (0x7F, 0xFF),
    "right_down": (0xFF, 0xFF),
    "center": (0x7F, 0x7F),
}

MACRO_LEFT_KEY = {
    "left_up": 18,
    "up": 19,
    "right_up": 20,
    "left": 21,
    "right": 22,
    "left_down": 23,
    "down": 24,
    "right_down": 25,
    "center": 38,
}


def macro_left(direction: str = "center") -> bytes:
    """Two bytes, X then Y. Default is 127, 127."""
    try:
        x, y = MACRO_LEFT[direction]
    except KeyError as exc:
        raise ValueError(f"unknown direction {direction}") from exc
    return bytes((x, y))
