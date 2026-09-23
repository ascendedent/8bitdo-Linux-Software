# Ultimate 2C config protocol

Status: **V2 1.35 does not configure the 2C.** It identifies `310a` and can update firmware. It does not read or write deadzones, triggers, vibration, maps, macros, or profiles. Bluetooth is not inventoried yet. Sent on 2026-09-23 with authorization, read-only: the Ultimate 2 chunked read and the `custom_info` read get no reply from the 2C; `readCRC` is answered. So the 2C's config channel, if it has one, is not the section-`04` reader this build uses for every other pad. See `docs/capture-log.md` under `03_reads`. The macOS Ultimate Software, checked 2026-09-23 on a Mac mini, also shows only Firmware for the 2C. Firmware 1.09, the image this pad is running, was disassembled the same day: its report-`81` dispatcher is the updater, tabulated in `docs/firmware.md`, and it has no settings-image read. 8BitDo does not offer host-side customization for this pad in any official app; the L4/R4 binds are done on the pad with button combos. The build names `310a` `PID_QINGCHUN2` and the idle receiver `301c` `PID_QINGCHUN2RR`. Both ids are referenced only by the platform selector and the update page, and `SelectPlatform.hideall` returns true for them, which hides every config page. No config class in the build references either id. See `docs/device-ids.md`. The image has no settings write either: the L4/R4 binds live in a 26-byte flash record that no host command reads or writes.

## Channel

Observed 2026-09-23 over a USB cable, PID `310a`, bcdDevice `1.14`. Full writeup in `docs/cable-inventory.md`.

| Question | Answer |
| --- | --- |
| Works over the 2.4 GHz dongle? | With the controller on, the dongle is `310a` and V2 sends the same identify probe as on the cable. With the controller off, the dongle is `301c` and V2 sends nothing. Report `81` never reaches the pad through the dongle: the receiver firmware answers identify (with its own id `301c`), RF address, and rumble itself, and the pad's report handler is only reached from its USB endpoints (`docs/firmware.md`). |
| Works over USB cable? | V2 1.35 sends the identify probe on interface 2. It does not follow that with a config read or write. |
| Works over Bluetooth? | Not tested. The machine's Bluetooth adapter is down until a reboot. Public reports say DirectInput is `2dc8:301b`, and the identify reply contains that ID. |
| Transport | Interrupt OUT and interrupt IN on interface 2. Not a feature report. `hid-generic` owns the interface. |
| Interface / usage page | Interface 2, usage page `0xFF7A`, application usage `0x01`. Interface 0 is XInput (`xpad`). Interface 1 is a boot keyboard plus consumer and mouse, standard pages only. |
| Report ID | Host to device: output report `0x81`, 63 bytes, EP 6 OUT, 64-byte packets. Device to host: input report `0x02`, 63 bytes, EP 3 IN, 64-byte packets. Idle read on the vendor interface returned nothing. |
| Separate commit / save-to-flash command? | None for settings. The firmware writes its own flash records when a bind is set on the pad. The only host-writable persistent values are the RF address (`66 aa 64`, which also wipes the binds) and the product-string selector (`00 61 01`). |
| Checksum | None in the four baseline packets. |
| Sequence counter | None in the four baseline packets. |

The report IDs match the Pro 2 config framing (`0x81` out, `0x02` in, 64-byte transfers). The baseline commands do not. See below.

## Baseline probe

Captured 2026-09-23 from Ultimate Software V2 1.35 under Wine, USB cable, after a firmware update. The USB revision was still `1.14`. V2 sent two interrupt OUT packets on endpoint 6 and read two replies on endpoint 3, then stopped. Full hex is in `captures/exports/00_baseline.txt`.

`getcurrentpid` in `8BitDoAdvance.dll` builds the first command itself, in `8BitDoFirmwareUpdaterTools/Advance.cpp`:

| Offset | Byte | Source |
| --- | --- | --- |
| 0 | `81` | Report ID, written into the 64-byte buffer |
| 1 | `05` | Command class for this product. The shared writer uses `06`, `45`, `85`, or `5e` for other product IDs. |
| 2 | `00` | Left zero |
| 3 | `21` | Command |
| 4 | `01` | Subcommand |

It writes 64 bytes and reads 64. The product id is the little-endian uint16 at reply offset 6. `301c` is logged as the wrong id. Any other value, including the `301b` this controller returns, is logged as the right id and the function returns success.

`initDevice` sends the second command. It sets a command word of `0x00C1` and the shared writer puts the class byte `05` in front, which is the captured `05 c1 00`. A sibling of that function sends `0x00C1` with the next word set to `0x8000`. That sibling was not in the capture, and it has not been sent.

The `310a` comparisons in this library are in that firmware-updater path: open the HID handles, `getcurrentpid`, `initDevice`, `readCRC`. They are grouped with the idle dongle and with bootloader checks. None of them call `readUltimate2`, `readUltimateBT2`, or `readPro2`. The Ultimate 2 config image those readers move is 1592 bytes (`0x638`), which matches `ANSI_CRC_16_Ultimate2`. The 2C is not on that path.

## Firmware-path commands that were not captured

These are in the same updater. They have not been sent to the controller.

| Function | What it prepares | Seen on the wire |
| --- | --- | --- |
| `getcurrentpid` | `81 05 00 21 01` | Yes, baseline and `tools/identify.py` |
| `initDevice` | class `05`, command word `0x00C1` | Yes |
| `initDevice1` | command word `0x00C1`, following word `0x8000` | No |
| `readCRC` | command word `0x00C3`, length field `0x0C` | No |

`readUSBAdapter` reads a 560-byte (`0x230`) block the log calls `custom_info`. A BSS flag selects the body. The flag is zero when the process starts, and this DLL has no store to it, so the function takes the zero-flag path. The idle-dongle capture showed V2 never calling it.

That path clamps each chunk to 45 bytes (`0x2d`) and wraps it with the same three-byte header the Pro 2 config read uses. Report id `81`, then a size byte, then section `04`. For the first chunk the size byte is `3e` and the HID write is 64 bytes:

```
81 3e 04
0c CC CC CC CC CC CC CC
2d CC 30 02 00 00 CC CC
[45 bytes, also CC in this build]
```

| Wire offset | Value | Meaning |
| --- | --- | --- |
| 0 | `81` | Report id |
| 1 | `3e` | Bytes after the report id |
| 2 | `04` | Section, same as the Pro 2 config section |
| 3 | `0c` | Request byte for this path |
| 11 | `2d` | Chunk length |
| 13–14 | `30 02` | Total size `0x230`, little endian |
| 15–16 | `00 00` | Offset, little endian. Later chunks advance it |
| 4–10, 12, 17–18 | `CC` | Not stored. This build fills the stack frame with `CC` before writing the fields above |

The reply parser accepts a 64-byte read only when byte 0 is `02`, byte 1 is `04`, byte 2 is `04`, and the dword at offset 6 is `0x0c`. The chunk length is byte 10. The chunk bytes start at offset `0x12`. The reader writes that chunk at the current offset, adds the length to the offset, and tries again, up to 30 times, until the offset reaches `0x230`. A rejected reply or a zero length does not move the offset. It then copies the first 560 bytes out. `assemble_custom_info` in `tools/packets.py` does that join.

If that BSS flag were 1, the same wrapper would be used with a Pro 2 body. The first chunk is:

```
81 3e 04
02 00 00 00
2d 00 00 00
30 02 00 00
00 00 00 00
```

followed by 45 `CC` bytes. `02 00` is request type 2, the read. The length dword is `2d 00 00 00`. The total is `30 02 00 00`. The offset dword is 0. `310a` is not in the checksum list (`3010`, `3011`, `3109`, `6006`, `6007`, `6009`, `6012`, `600f`, `600b`, `2062`), so the high half of the length dword stays 0. A product in that list stores CRC-16/MODBUS of the chunk data there instead. The flag is 0 at startup, so this is not the packet `readUSBAdapter` sends. The reply parser for this form wants `02 04`, then uint16 `0004`, then uint16 `0002`, and takes the chunk from offset `0x12` for the dword length at offset 6.

`readUltimate2` calls this same reader with request type 2 and total `0x638` (1592 bytes). That is the Ultimate 2 config image. Its product `6012` is in the checksum list. The 2C's product is not passed to `readUltimate2`.

`writeUltimate2` uses the same chunked call with request type 1. The data pointer is the 1592-byte image plus the current offset, so each chunk carries the config bytes instead of the `CC` fill. The checksum is CRC-16/MODBUS of those bytes because `6012` is in the list. After the chunks, it sends a 16-byte body with no data: request `06 00`, argument `23 01` (`0x0123`). Wrapped, that commit is `81 11 04 06 00 23 01` and twelve zero bytes. The Pro 2 finish value in the older spec is `0x15`. This build sends `0x0123`. The 2C does not call `writeUltimate2`. None of these write or commit packets have been sent.

The per-field writers send one short request-1 chunk at a fixed offset. `tools/ultimate2_image.py` records the offsets and the stick, trigger, and vibration bytes.

| Writer | Index 0 | Stride | Size |
| --- | --- | --- | --- |
| header flag (`WriteUltimate2Name`) | `0x00` | 4 | 4 |
| profile name | `0x14` | `0x20` | `0x20` |
| vibration | `0x74` | `0x0c` | `0x0c` |
| stick | `0x98` | 8 | 8 |
| trigger | `0xb0` | 8 | 8 |
| special | `0xc8` | 8 | 8 |
| button map | `0xe0` flag, keys at `0xe4` | profile `0x5c`, entry 4 | 4 |
| macro | `0x1f4` | `0xd8` | `0xd8` |
| XInput rumble | `0x47c` | 8 | 8 |
| sixaxis | `0x494` | `0x0c` | `0x0c` |
| dynamic | `0x4b8` | `0x0c` | `0x0c` |
| hotwheel | `0x4dc` | `0x10` | `0x10` |
| single | `0x50c` | `0x64` | `0x64` |

The 1592 bytes are one `custom_config_record_t_u2`. The managed struct in the V2 assembly, laid out sequentially from its field signatures, is exactly `0x638` bytes, and every field lands where the native writers put it: `flag[3]` at `0x00`, `crc_value` at `0x0c`, `gamepad_mode` (uint16) at `0x10`, `cur_slot` (uint16) at `0x12`, then `file_name`, `rumble`, `joystick`, `trigger`, `special_feature`, `map_key`, `record_macro_fun`, `x_rumble`, `sixaxis`, `dynamic`, `hotwheel`, and `single`, three of each. So the three header dwords `WriteUltimate2Name` sends are the `flag` array, and the CRC slot at `0x0c` is separate from the per-chunk CRC-16. Three of each record fill the image through `0x638` with nothing left over. Three profile names fill `0x14` through `0x74`. Three vibration records fill `0x74` through `0x98`. Three stick records fill `0x98` through `0xb0`. Three trigger records fill `0xb0` through `0xc8`. Three specials fill `0xc8` through `0xe0`. Three map profiles fill `0xe0` through `0x1f4`. Three macros fill `0x1f4` through `0x47c`. One macro is 8 bytes of head (a flag, a count byte, three pad bytes) and four 52-byte steps. A step is a 32-byte name, `gamepad_mode`, `special_flag`, `max_steps`, `step_offset`, two pad bytes, then `key_map`, `cycles_num`, and `interval_ms`. Clear leaves a step as zeros. `key_map` is one button from `getKey`, not a chord. `getKey` takes an `S_ButtonKeyType` id and returns the `key_map` dword. Its only caller is `Handle_Macros_Ultimate`, which stores the macro's trigger button there. The full function, read from the IL at RVA `0x1a6ed0`:

| `S_ButtonKeyType` | id | `key_map` |
| --- | --- | --- |
| START | 16 | `0x00000001` (bit 0) |
| L3 | 5 | bit 1 |
| R3 | 6 | bit 2 |
| SELECT | 15 | bit 3 |
| X | 13 | bit 4 |
| Y | 14 | bit 5 |
| Right | 10 | bit 6 |
| Left | 9 | bit 7 |
| Down | 8 | bit 8 |
| Up | 7 | bit 9 |
| L | 1 | bit 10 |
| R | 2 | bit 11 |
| B | 12 | bit 12 |
| A | 11 | bit 13 |
| L2 | 3 | bit 14 |
| R2 | 4 | bit 15 |
| Share | 17 | bit 16 |
| switchHome | 22 | bit 17 |
| AS_P5 | 31 | bit 20 |
| AS_P3 | 29 | bit 21 |
| AS_P1 | 27 | bit 25 (bit 26 on `PID_UltimateBT2` `600f`) |
| AS_P2 | 28 | bit 26 (bit 25 on `PID_UltimateBT2`) |
| AS_P4 | 30 | bit 30 |
| Record | 40 | bit 19, only on `PID_Pro3` `6009` |
| LS_Left | 32 | bit 19, only on `PID_HitBox` `600b` |
| LS_Up | 34 | bit 20 (the AS_P5 bit), HitBox only |
| LS_Right | 33 | bit 28, HitBox only |
| LS_Down | 35 | bit 29, HitBox only |
| RS_Up | 38 | `0x08000001` (bit 27 plus Start), HitBox only |
| RS_Down | 39 | `0x08000002` (bit 27 plus L3), HitBox only |
| RS_Left | 36 | `0x08000004` (bit 27 plus R3), HitBox only |
| RS_Right | 37 | `0x08000008` (bit 27 plus Select), HitBox only |
| anything else | | 0 |

Every other id, including Home (18), turbo (19, 20, 25), screenshot (21), Swap (41), Macro1-4 (42-45), and Combo1-5 (46-50), stores 0. The product gates compare `VIDPID.PID_Current`, so on the Ultimate 2 (`6012`) the stick ids and Record store 0 too. Bit 27 is `KeyMap_Swap`. The HitBox right-stick values reuse the Start, L3, R3, and Select bits, and Pro 3 Record reuses the HitBox LS_Left bit, so a firmware that reads these must know its product. `key_map_for(button, product=...)` in `tools/ultimate2_image.py` reproduces the whole function.

The map-profile entries use a different but overlapping table, `AdvanceSuper.Mode.KeyMap`, through the `KEY_*_MAP` and `DIR_*_MAP` fields the save reads:

| `KeyMap` | value | | `KeyMap` | value |
| --- | --- | --- | --- | --- |
| Start | `0x1` | | Turbo | `0x10000` |
| L3 | `0x2` | | Home | `0x20000` |
| R3 | `0x4` | | BT_CON | `0x40000` |
| Select | `0x8` | | LS_LEFT (HitBox) | `0x80000` |
| X | `0x10` | | P5, LS_UP (HitBox) | `0x100000` |
| Y | `0x20` | | P3 | `0x200000` |
| Right | `0x40` | | ScreenShot | `0x400000` |
| Left | `0x80` | | Turbo_3 | `0x800000` |
| Down | `0x100` | | Turbo_Auto | `0x1000000` |
| Up | `0x200` | | P1 | `0x2000000` |
| L1 | `0x400` | | P2 | `0x4000000` |
| R1 | `0x800` | | Swap | `0x8000000` |
| B | `0x1000` | | RS up, down, left, right | `0x8000001`, `0x8000002`, `0x8000004`, `0x8000008` |
| A | `0x2000` | | LS up, down, left, right | `0x8000010`, `0x8000020`, `0x8000040`, `0x8000080` |
| L2 | `0x4000` | | LS_RIGHT (HitBox) | `0x10000000` |
| R2 | `0x8000` | | LS_DOWN (HitBox) | `0x20000000` |
| | | | P4 | `0x40000000` |

`BasicAdvanceUIData`'s constructor starts with R2 as `0x20000` and Home as `0x8000`. `AutoR2AndHome` then calls `changeKey`, which swaps them to the values above, for every product except an old SN30 Pro+ HID. So bits 0 through 17 of a map entry agree with `getKey`. The stick entries are bit 27 plus a nibble, right stick in bits 0-3 and left stick in bits 4-7, except on the HitBox, which uses the single bits its `getKey` tail stores. The Pro 2 macro record has its own one-byte stick field from `getJoyKey`, with the nibbles the other way round: left stick in bits 0-3 (up 1, down 2, left 4, right 8) and right stick in bits 4-7.

`readkey_map` builds 18 keys by default, 20 on Pro 2, Ultimate 2.4, Ultimate PC, and Ultimate BT, 22 on HitBox, Pro 3, Ultimate 2, and Ultimate BT2, and 24 on HitBox 2. Slots 18-19 are P1 and P2, 20-21 are P3 and P4, and the HitBox 2 adds P5 and screenshot. Three XInput rumble records fill `0x47c` through `0x494`. A map profile is `0x5c` bytes: a uint32 flag, then 22 uint32 key ids. `readkey_map` fills them as A, B, X, Y, L1, R1, L2, R2, L3, R3, Select, Start, Menu, Home, Up, Down, Left, Right, P1, P2, P3, P4. The Menu slot asks for `S_ButtonKeyType` 17 (Share) and stores `KEY_MENU_MAP` or a turbo value. P1 through P4 are the four paddles. The four null slots seen earlier belong to the all-default profile the save compares against, which also swaps A/B and X/Y when `gamepad_mode` is 0. The key writer addresses the first key at `0xe4`. Each entry is a `KeyMap` value (table below), 0 when the key is unmapped, `0xff` when the UI had no mapping row for that slot. `WriteUltimate2Name` sends 4 bytes at `0x00`, `0x04`, or `0x08`, which are the three header flags, not the 32-byte profile name.

Each 8-byte stick record is one profile's `joy_params_record_t`. Bytes 0-3 are the flag (`0x20200911` when a save marks it enabled, `0x20190000` when not). Bytes 4-7 are left start, left end, right start, right end. Clear writes `00 80 00 80` there (0 and 128) and does not change the flag. The trigger record at `0xb0` has the same shape. Clear writes `00 ff 00 ff`, then, only if `isSupportSwitchTrigger` is true, sets both starts to 77. Saving the percent sliders stores `percent * 255 / 100`, so 50 becomes 127 and 100 becomes 255. The 12-byte vibration record at `0x74` is a flag plus two little-endian floats. Clear sets the enable mark and both floats to 1.0. That is not the XInput rumble record. XInput rumble is 8 bytes at `0x47c`: the same enable flag, then left start, left end, right start, right end. Clear writes `01 64 01 64` (1 and 100). There is no separate writer for it. It travels only inside the 1592-byte image.

`0x7F7F` is not inside that stick record. `MacroStep.getLeftStick` returns it when the step contains no left-stick direction. The low byte is X and the high byte is Y: 0 is left or up, 127 is center, 255 is right or down. The matching key id is 38 (`S_DefineMapKey.N`). The eight directions use key ids 18 through 25 and the pairs `00 00`, `7F 00`, `FF 00`, `00 7F`, `FF 7F`, `00 FF`, `7F FF`, and `FF FF`.

Flips and the dead-zone switch live in the 8-byte special record at `0xc8`: a flag, then a feature dword. Bit 0 is left X flip, bit 1 left Y, bit 2 right X, bit 3 right Y, bit 4 stick swap, bit 12 (`0x1000`) dead zone. Clear-sticks keeps `0xFFFFCAE0`, which drops those stick bits and leaves trigger swap, vibration, and the rest. Sensitivity and dead-zone compensation are sixaxis bytes 9 and 10 of the 12-byte record at `0x494`. Clear writes 0 to both. None of these Ultimate 2 writers run for the 2C.

`initDevice1` and `readCRC` use the short class-`05` writer, not this wrapper. Neither was captured. `initDevice1` is `81 05 c1 00 00 80`. `readCRC` is `81 05 c3 00 00 00 0c 00 00 00`. The rest of each 64-byte report is zeros. `tools/packets.py` builds all of these. Nothing in that module sends them.

None of these `custom_info` packets have been sent. They are not the two identify commands. `tools/packets.py` builds a chunk and checks a reply. `tools/test_packets.py` covers the first chunk, the next offset, the short last chunk, and a made-up reply. The test does not open a HID device.

Both host packets start with report ID `81` and a second byte `05`.

| Dir | Payload |
| --- | --- |
| OUT | `81 05 00 21 01` |
| IN | `02 22 6d 00 00 00 1b 30 01` |
| OUT | `81 05 c1 00` |
| IN | `02 05 00 00 c1 00` then, at byte offset 22, `08 34 84 00 f0 33 84 00 00 10` |

The reply to the first command contains `1b 30`, little-endian `0x301b`. That is the product ID PCGamingWiki lists for this controller on Bluetooth. The reply to the second command echoes `05` and `c1`.

This is not the Pro 2 config read. That read uses a `81 3e 04` header and a `02 00` request type, and it loops. Neither showed up. `05` here behaves like a command opcode, not a length.

Holding B or X while plugging the cable, tried 2026-09-23 08:26, disconnected and reconnected the same `2dc8:310a` device both times. The dongle with the controller on, tried 08:29, did the same: V2 flashed and returned to the controller outline and a Firmware button. With the controller on, the dongle is `2dc8:310a` bcdDevice `1.14`, the same three interfaces as the cable. For about six seconds before the controller linked, the dongle was `2dc8:301c`, product string `IDLE`, bcdDevice `2.00`, one HID interface. Left in that state with the controller off, the same identity stayed up. Its descriptor is usage page `0xFFA0`, input report `0x02` on EP 4 IN, output report `0x81` on EP 5 OUT. V2 was restarted against it and sent no output transfer. See `captures/exports/02_idle_dongle.txt`. V2 1.35 has profile data for the Ultimate 2 (`/ProfileData/Ultimate2`, `/ProfileData/UltimateBT2`) and only the product name for the 2C. With the controller on, the app identifies the pad and offers firmware. With the controller off, it does not talk to the receiver. It does not open a config editor in either state.

## Product images

Each product UI class nests its own `custom_config_record_t`. Sizes come from the managed field signatures, and each size (except the Pro 2 one) recurs as an immediate in the native DLL's read and write code, so these are the wire images. Nothing here has been sent. Every product but the Ultimate 2 needs an outside tester.

| Product class | PID | Image struct | Size | Profiles | Map keys per profile | Extra records |
| --- | --- | --- | --- | --- | --- | --- |
| Pro2Advance, Ultimate2_4Advance | `6003`, others | `custom_config_record_t` | `0x674` (1652) | 3 | 20 (`map_key_t_Pro2`) | `macro_fun` only |
| UltimateBTAdvance | | `custom_config_record_t` | `0x914` (2324) | 3 | 20 | `macro_fun`, `record_macro_fun`, `x_rumble` |
| Pro3Advance, HitBoxAdvance | `6009`, `600b` | `custom_config_record_t` | `0x92c` (2348) | 3 | 22 (`map_key_t_Pro3`) | `macro_fun`, `record_macro_fun`, `x_rumble` |
| HitBox2Advance | | `custom_config_record_t` | `0xa68` (2664) | 2 | 24 (`map_key_t_HitBox2`) | `macro_fun`, `record_macro_fun`, `x_rumble`, `rgb_config`, `combo` |
| Ultimate2_4Advance2 (Ultimate 2) | `6012` | `custom_config_record_t_u2` | `0x638` (1592) | 3 | 22 | `record_macro_fun`, `x_rumble`, `sixaxis`, `dynamic`, `hotwheel`, `single` |
| UltimateBTAdvance2 (Ultimate BT2) | `600f` | `custom_config_record_t_BTu2` | `0xad0` (2768) | 3 | 22 | `macro_fun`, `record_macro_fun`, `x_rumble`, `sixaxis` |

The `_all` and `_temp` variants of each struct are the INI and UI staging forms, not wire images. All of them share the same header: `flag[profiles]`, `crc_value`, `gamepad_mode`, `cur_slot`, then `file_name[profiles]` and the rumble, joystick, trigger, and special records, so the first `0xe0` bytes of every three-profile image have the same layout as the Ultimate 2 image. The `map_key` record is `4 + 4 * keys` bytes per profile. A 2C image, if one exists, is not in this build.

## What the V2 library exports

`8BitDoAdvance.dll` from V2 1.35 exports read and CRC functions for other products: `readUltimate2`, `readUltimate2_4`, `readUltimateBT2`, `readUltimateBT`, `readUltimate_PC`, `readPro2`, `readPro3`, `readConfigure`, and `ANSI_CRC_16_Ultimate2` plus the matching Ultimate 2 variants. There is no `read` or CRC export whose name contains the 2C. `readUSBAdapter` exists. The idle-dongle capture showed V2 sending that device nothing, so that export was not exercised.

`Pro2_GetVersionAndVerification` and `getDevicePID` are the version and product-id calls. They match the shape of the only exchange this controller answered: a short identify, then a product id in the reply.

## Commands

| Name | Bytes | Seen in | Effect |
| --- | --- | --- | --- |
| Handshake / identify | `81 05 00 21 01` then `81 05 c1 00` | `00_baseline`, replayed by `tools/identify.py` on 2026-09-23 | Device replies with the same bytes as the capture. No config blob follows. |
| Ultimate 2 chunked read | `81 3e 04 02 00 00 00 2d 00 00 00 38 06 00 00 00 00 00 00` plus 45 `cc` | `03_reads`, sent by `tools/read_config.py` | **No reply.** Three sends, 800 ms each, twice. The 2C ignores the request-2 reader. |
| `custom_info` read | `81 3e 04 0c` with the `cc` frame | `03_reads` | **No reply.** |
| `readCRC` | `81 05 c3 00 00 00 0c 00 00 00` | `03_reads` | Reply `02 05 00 00 c3 00 0c 00 00 00`, then `ff ff` at offset 18. The DLL takes the uint16 at the start of the returned payload as the device's CRC of the flash region named by the two dwords after the length field, and compares it with its own CRC of the firmware file. Region `(0, 0)` returned `0xffff`, the CRC-16/MODBUS initial value over zero bytes. |
| Reply-only probes | `81 05 00 31 01`, `81 00 66 aa 63`, `81 05 08 00` | `04_probes`, sent by `tools/read_config.py --probes` | Answered: `02 32`; `02 02 63` plus the 5-byte radio address, `00`, and version `6d`; the class-`05` frame with `1b 30` at offset 18. None of them changes state (`docs/firmware.md`). |
| Read config | none in firmware 1.09 | `docs/firmware.md` | The DLL's class-`05` callers match the image: `c1` and `c3` reply, `2`/`3`/`4`/`c4`/`0x0b` program or erase flash, `7` resets. The image also has a 46-byte flash read (`0x0005`) and a few exact prefixes (`00 31 01`, `00 38`, `66 aa`). None of them is the settings image. Uncaptured commands stay unsent. |
| Write setting | none in firmware 1.09 | `docs/firmware.md` | No report `81` handler writes a bind, stick, trigger, or vibration setting. The binds change only through the on-pad combo (Mapping plus L4 or R4 plus the targets). |
| Commit | none | `docs/firmware.md` | The firmware erases and rewrites its 4 KB record sectors itself. `81 11 04 06`, the Ultimate 2 commit, is not compared anywhere in the image. |
| Factory reset | `81 ?? 66 aa 64` is the nearest thing | `docs/firmware.md` | Set-RF-address zeroes the whole settings record, so the binds reload as defaults. It also changes the radio address. Not sent. |

## Settings

What the 1.09 image stores, from `docs/firmware.md`. None of it is readable or writable over report `81`.

| Setting | Where | Encoding | Evidence |
| --- | --- | --- | --- |
| L4 and R4 binds | flash `0x73000`, record bytes 9-24, RAM `0x843910` | Four uint32 button masks: pair A L4, pair A R4, pair B L4, pair B R4. Bits as in the `getKey` table above (bit 1 L3, bit 2 R3, bit 13 A, ...). Defaults `0x2` and `0x4`. | Loader `0x7548`, table builder `0x60d0`, combo handler `0x6cc4` |
| Which bind pair is live | record byte 5 | 0 or 1, toggled by a button combination | `0x9014` |
| DInput mode | record bytes 7-8 | Byte 7 set by holding B at power-on, cleared by X. Identify reports `301d` while set. | `0x78e8`, identify handler |
| Product strings | flash `0x77000` | uint16, 1 plain, 2 `(WUKONG)`. Host-settable with `81 05 00 61 01 vv vv`. | `0x88f8`, `00 61 01` handler |
| Radio address | flash `0x76000`, override in record bytes 0-4 | 6 bytes, OUI `e4:17:d8`, generated from the chip id | `0x7698`, `66 aa 63` / `66 aa 64` |
| Stick deadzones, trigger ranges, vibration strength, macros, profiles | not stored | The image has no record for any of these. | record map in `docs/firmware.md` |

## Relation to other devices

| Device | Same framing? | Evidence |
| --- | --- | --- |
| Pro 2 / SN30 Pro+ (V1, 8bitdo-spec) | Unknown | See `docs/v1-framing.md` |
| Ultimate 2 Wireless | Same chunked read and write as the flag-set path. Total `0x638`. Request 2 reads, request 1 writes, then request 6 with argument `0x0123`. Checksum because PID `6012` is in the CRC list. | `readUltimate2` / `writeUltimate2` in V2 1.35. Not sent. |
| Pro 3 | Same header as the Ultimate 2 image, then a `0x92c`-byte `custom_config_record_t` with 22-key map profiles, `macro_fun`, `record_macro_fun`, and `x_rumble`. `getKey` adds Record as bit 19. | Managed structs and `readkey_map` in V2 1.35. Not sent. |
| Ultimate 2C Bluetooth (`301a`) | Unknown. Firmware-only in V2 1.35 as well, and its 1.01 image is encrypted, so its report set cannot be read from the file. | `docs/firmware.md` |
