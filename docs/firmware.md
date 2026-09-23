# Ultimate 2C firmware files

Fetched 2026-09-23 from 8BitDo's update server, the same way Ultimate Software V2 does, without touching the pad. Nothing here has been flashed. The files are in `vendor/firmware/`, which is gitignored.

## Where V2 gets them

`UpdatePage.ReadHttp` POSTs an empty `application/json` body to

```
https://support.8bitdo.cn/restapi/link/v1/client/firmware/select?firmware_type=<type>&beta=<0|1>
```

`UpdatePage.getType` maps the product id to the type: `310a` (`PID_QINGCHUN2`) is 75, `301c` (`PID_QINGCHUN2RR`, the receiver) is 76, `301a` (`PID_UltimateBT2C`) is 108. The reply is JSON with a `data` list of `Firmware` records: `file_version`, `fileSize`, `fileURL`, `md5`, `readme_en`, `beta`. The `md5` field for type 75 is wrong on the server (both versions list the same value, and neither matches its file).

| Type | Product | Version | Date | Size | File |
| --- | --- | --- | --- | --- | --- |
| 75 | Ultimate 2C | 1.06 | 2024-07-05 | 74780 | `u2c_1.06_1913.dat` |
| 75 | Ultimate 2C | 1.09 | 2025-03-13 | 74780 | `u2c_1.09_1948.dat` |
| 76 | Ultimate 2C Adapter | 1.00 | 2024-07-05 | 25116 | `u2c_adapter_1.00.dat` |
| 76 | Ultimate 2C Adapter | 1.03 | 2025-03-14 | 40988 | `u2c_adapter_1.03.dat` |
| 108 | Ultimate 2C Bluetooth (`301a`) | 1.01 | 2025-07-24 | 86044 | `u2_bt2c_1.01.dat` |

The pad on the bench reports bcdDevice `1.14`, which is the USB revision in its descriptor, not the firmware version. V2 reads the firmware version through its own identify path.

## File format

A 28-byte `FirmwareHeader` (the managed struct in V2) followed by the raw Telink image. No encryption: the strings and USB descriptors are in the clear, and the native write path has no byte transform.

| Offset | Field | 2C 1.09 | 2C 1.06 | Adapter 1.03 |
| --- | --- | --- | --- | --- |
| 0x00 | Version, uint32 | `0x6d` (109) | `0x6a` (106) | `0x67` (103) |
| 0x04 | FlashAddress | `0x6000` | `0x6000` | `0x6000` |
| 0x08 | Length | `0x12400` | `0x12400` | `0xa000` |
| 0x0c | Pid | `0x301b` | `0x301b` | `0x301c` |
| 0x10 | ChipText, 4 bytes | `c3dc20a4` | `61a4d2bb` | `e55cdb69` |
| 0x14 | Revision, uint16 | 0 | 0 | 0 |
| 0x16 | Reserved | 0 | 0 | 0 |

The header's `Pid` is `0x301b` for the pad, which is the value the pad puts at offset 6 of its identify reply, and `0x301c` for the receiver. So the identify reply carries the firmware's own product id, not the USB one.

## What the image is

Telink TC32 code for the Telink B80 (`$$$telink_b80_ble_2.4g_dual_mode_sdk_V3.0.0$$$` and `$$$pcode_S2$$$` at the end of the image, `Telink Remote` nearby). The image starts with the Telink boot header (`KNLT` at offset 8) and loads at flash `0x6000`, the OTA slot. TC32 is Telink's own 16-bit-instruction core, not ARM, so stock `objdump` cannot read it. The `flyskywhy/tc32` repository carries prebuilt `tc32-elf-objdump` binaries, and `rgov/Ghidra_TELink_TC32` is a Ghidra processor module.

Version 1.06 and 1.09 differ in 62387 of 74752 bytes, so a byte diff is not useful. The descriptor block and strings are at the same offsets in both.

## USB personalities in the 2C image

Three device descriptors, all VID `2dc8`, in the 1.09 image (payload offsets):

| Offset | PID | bcdDevice | Product string | Configuration |
| --- | --- | --- | --- | --- |
| `0x1197c` | `301d` | 1.00 | `8BitDo Ultimate 2C Wired Controller` | One HID interface, EP 84 IN and 05 OUT, 64 bytes, 145-byte report descriptor: DInput gamepad on report 1 plus vendor reports `02` in and `81` out in the same collection. |
| `0x11990` | `310a` | 1.14 | `8BitDo Ultimate 2C Wireless Controller` | Three interfaces: 0 is XInput (`ff/5d/01`, EP 84 IN, 05 OUT), 1 is HID with a 166-byte keyboard, consumer, and mouse descriptor (EP 82 IN), 2 is HID with the 33-byte page `0xFF7A` descriptor (EP 83 IN, 06 OUT). This is what the bench sees. `MSFT100` with vendor code `0x90` is the Microsoft OS string for the XInput interface. |
| `0x11af4` | `301b` | 1.00 | `8BitDo Ultimate 2C Wired (WUKONG)` | One `ff/5d/01` interface with a different XInput vendor descriptor (`10 21 10 01 ...`). |

The `0xFF7A` descriptor, byte for byte, is

```
06 7a ff  09 01  a1 01
  85 02  09 02  a1 00  09 03  15 00  25 ff  75 08  95 3f  81 02
  85 81  09 05  91 02
  c0 c0
```

one 63-byte input report `02` and one 63-byte output report `81`, both opaque. `81` is the only report a host can send on that interface, and the pad's firmware decides what the bytes mean.

A Bluetooth PnP ID record at `0x113c1` is `02 c8 2d 1b 30 01 00`: source USB-IF, VID `2dc8`, PID `301b`, version 1.00. So `301b` is also the Bluetooth product id, which matches the public reports.

The Ultimate 2 record marks `0x20200911` and `0x20190000` do not occur in the image. The pad does not carry the Ultimate 2 config record.

## The receiver image

The adapter image (`301c`) has two device descriptors: `310a` bcdDevice 1.14 with the same three-interface layout as the pad, which is what the receiver presents once the pad links, and `301c` bcdDevice 1.00 (`IDLE`) with a page `0xFFA0` descriptor:

```
06 a0 ff 09 01 a1 01
  85 02 15 00 26 ff 00 19 01 29 02 75 08 95 3f 81 02
  85 81 15 00 26 ff 00 19 01 29 02 75 08 95 3f 91 ...
```

The string ` current mode == USB_MODE_IDLE ` sits next to it. So the receiver has its own opaque `02` in and `81` out reports on page `0xFFA0` while idle. V2 sends it nothing, and nothing has been sent to it from here.

Adapter 1.03 still has its debug strings. They name the same updater operations as the DLL (`eraseFlash`, `writefirmware`, `readfirmware`, `flash_crc`, `savehead4K`, `saveCodeBlock`, `reset`, `get_pid`) and a separate set the pad image does not log: `CAL_JOY`, `CAL_JOY_SAVE`, `changePlatformCMD`, `getRFAddressCMD`, `setRFAddressCMD`, `changeBoot_Dinput`, `getVersion_Dinput`. Each of those names is tied to its command bytes in the adapter table below. Nothing has been sent to `301c`.

## The `301a` image

`u2_bt2c_1.01.dat` (type 108, fetched 2026-09-23) is not readable. Its 28-byte header says version `0x65` (1.01), flash address `0x1018000`, length `0x15000`, pid `0x301a`, and an all-zero chip text. The payload has no `KNLT` magic, no descriptor, and not one printable string; its byte entropy is 7.998 bits in every 4 KB block, so it is encrypted end to end, not just a different core. The server's md5 for it (`41417038c1cd1c9f84d42310c7455716`) does not match the file (`33081fd5c5414fcbc501127628f089aa`), the same server-side mistake as the type 75 entries. Nothing about that device's report set can be read from the file.

V2 1.35 does not help either: `PID_UltimateBT2C` is referenced only by the update page and the platform selector, the same firmware-only routing as `310a`. The `UltimateBTAdvance2` config page with the 2768-byte record belongs to `PID_UltimateBT2` (`600f`), a different product.

## Report `81` commands in firmware 1.09

Disassembled with `tc32-elf-objdump` from the Telink image (the bytes after the 28-byte header). Addresses below are file offsets in that image. Relative branches and calls read correctly at those offsets, but the flash-resident text is linked at `0x6000` plus the offset: every absolute address in a literal pool, string pointer, or function pointer table is the file offset plus `0x6000`, and calls from flash text into the RAM-resident code at the front of the image show up in a plain sweep as huge negative targets (add `0x6000` to get the offset). The RAM-resident code, roughly the first `0x2500` bytes, is linked at 0. The same split holds for the adapter image. The bench pad is running this image: its captured identify reply carries version byte `0x6d`, and the `310a` descriptor in the file is bcdDevice `1.14`. Nothing below has been sent. The three commands already captured are marked.

Every handler starts from the same OUT buffer. Byte 0 is the report id `0x81`. Two shapes follow.

**Class `0x05`.** Byte 1 is `0x05`. The little-endian uint16 at byte 2 is the command, except when byte 2 is `0x0b`, which is the firmware chunk instead of a uint16. A shared reply builder writes `02 05`, echoes the command, and appends up to 46 payload bytes. That is the shape of the captured `c1` and `c3` replies.

| Command uint16 | Role in this image | Sent |
| --- | --- | --- |
| `0x00c1` | `initDevice1`. Builds the address block already in the capture, then replies. | yes, `81 05 c1 00` |
| `0x00c3` | `readCRC`. CRC of the flash range named in the report. Region `(0, 0)` answered `0xffff`. | yes |
| `0x0005` | Copies at most 46 bytes from a flash address into the reply. A firmware read, not a settings image. | no |
| `0x0008` | Reply only. The constant it plants is the product id `0x301b`. No flash call. | yes, `04_probes`: `02 05 00 00 08 00 02 00 00 00 02 00`, `1b 30` at offset 18 |
| `0x00c2` | Reply only. No flash call and no reset tail in this image. The DLL name is `SaveHead4K`. | no |
| `0x0002`, `0x0003` | Flash program. Both call the same write helper, and both refuse an address past `0x40000`. | no |
| `0x0004` | Flash erase family. Calls the erase helper, same address ceiling. | no |
| `0x000b` | Firmware chunk. Checksum over 59 bytes, then the write helper. | no |
| `0x00c4` | Flash control. Calls the helper the DLL names from `saveCodeBlock`. | no |
| `0x0007` | Replies, then the same reset tail as `81 05 00 51 00`. | no |

**Exact prefixes** matched by their own handlers, beside that switch:

| Bytes | What the handler does | Sent |
| --- | --- | --- |
| `81 05 00 21 01` | Identify. Reply payload `22`, version `6d 00 00 00`, product id `1b 30` (or `1d 30` when the wired DInput flag is set), the uint16 from flash `0x77000` at payload bytes 7-8 (default 1), then the DInput flag byte at payload byte 9. `tools/identify.py` decodes this. | yes |
| `81 05 00 31 01` | Replies with payload byte `0x32` and nothing else. | yes, `04_probes`: `02 32` |
| `81 05 00 38` | Replies with payload byte `0x39`, then samples four stick axes. | no |
| `81 05 00 36` | Sets a mode flag and clears a block of state. No reply in the handler. | no |
| `81 05 00 51 00` | Reset tail: the same two calls `0x0007` makes after its reply. | no |
| `81 05 00 61 01 vv vv` | Writes the uint16 at report bytes 5-6 to flash `0x77000` (the product-string selector, see the settings section), then replies with payload byte `0x62`. | no |
| `81 11 04 08 dd dd ll rr` | Rumble. The adapter's copy of this handler logs `timer left_vibration`: uint16 duration at bytes 5-6, left and right motor strength at bytes 7-8. The Ultimate 2 commit is `81 11 04 06`, and `06` is not compared anywhere in this image. | no |
| `81 ?? 66 aa 63` | Get RF address. Reply `02 63`, the 5-byte radio address derived from the chip id, a zero byte, then version `0x6d` as a uint32. After replying it stores request byte 1 into the RAM mode flag `0x843468`, so it is sent with byte 1 zero. Same command in the adapter (`getRFAddressCMD`). | yes, `04_probes`, as `81 00 66 aa 63` |
| `81 ?? 66 aa 64 a0 a1 a2 a3 a4` | Set RF address. Zeroes the whole 26-byte settings record in RAM, copies the 5 bytes into its bytes 0-4, saves the record to flash `0x73000`, replies `02 64` plus the 5 bytes. This wipes the L4/R4 binds (they reload as defaults). Same command in the adapter (`setRFAddressCMD`). | no |
| `81 ?? 66 aa 70` | Stores the byte at offset 1 and returns. | no |

No handler reads the 1592-byte Ultimate 2 image or the 560-byte `custom_info` block. The section-`04` reader is absent, which is why those two reads got silence. The L4/R4 binds are in the `0x73000` settings record described below, and no report-`81` handler reads that record back out; `66 aa 64` is the only one that writes into it, and it zeroes the binds.

## Report `81` commands in adapter 1.03

Disassembled the same way from `u2c_adapter_1.03.dat` (header pid `301c`). The debug strings are not inline in code: they are a plain rodata block at offsets `0x89d0`-`0x9820`, referenced from literal pools as `0x6000` plus the offset, so each string maps to exactly one function. Nothing here has been sent to `301c`.

Every OUT report reaches two dispatchers from the RAM-resident USB handler at offset `0x432`: the updater dispatcher at `0x7998` and the device-command dispatcher at `0x81fc`. Both get the same buffer, so the two sets below are matched in parallel.

**Updater dispatcher (`0x7998`).** Same shape as the pad: byte 0 `0x81`, byte 1 `0x05`. If byte 2 is `0x0b` the report is a firmware chunk. Otherwise it copies 16 bytes from report byte 2 as the `header` the strings mention: `header->cmd` is the uint16 at report bytes 2-3, `header->cmd_params` the uint16 at bytes 4-5. Every handler is called in turn and matches its own `cmd`. The set and the numbering are identical to the pad's class `05` table.

| Command uint16 | Debug string | Handler | What it does |
| --- | --- | --- | --- |
| `0x00c1` | `init_device`, `init.upgrade_addr : %x` | `0x71bc` | Init, builds the reply block. |
| `0x0004` | `eraseFlash ----> header->cmd_params` | `0x7230` | Sector erase at the address in the header. |
| `0x0003` | `writefirmware ----> header->cmd_params`, `crc != header` | `0x72e8` | Flash program with a CRC check against the header. Payload starts at report byte 18. |
| `0x0002` | `writefirmware`, then `boot_wirteFlash ----> offset` | `0x7424` | Flash program of the boot block, same CRC check. |
| `0x0005` | `readfirmware ----> header->cmd_params` | `0x7508` | Flash read into the reply. |
| `0x000b` (byte 2) | `multi_writeFlash`, `sum != multi_write.checksum` | `0x75d4` | Firmware chunk with a byte-sum check. |
| `0x00c3` | `flash_crc`, `crc_list.address/len/block_size` | `0x76d0` | CRC over a flash range. |
| `0x00c2` | `savehead4K ----> header->cmd_params` | `0x77e4` | Save-head step. |
| `0x00c4` | `saveCodeBlock`, `info: %x - %x` | `0x7838` | Save-code-block step. |
| `0x0007` | `reset ----> header->cmd_params` | `0x78dc` | Replies, then resets. |
| `0x0008` | `get_pid` | `0x7940` | Reply only. The constant it plants is the product id `0x301c`. |

**Device dispatcher (`0x81fc`).** Gated by the USB mode byte at RAM `0x843060`: when that byte is 2 or 3 every handler below runs, otherwise only `changeBoot_Dinput`. That byte is set to 2 by the XInput output report `01 03 nn` (the LED command every XInput host sends, handled at `0x7cd0` before the dispatchers run) and by the descriptor handler at `0x7ad4`-`0x7b02` when it serves the 42-byte or the 145-byte descriptor, so the full set is live once a host has claimed the device. Replies go through the same send helper (`0x7d7c`) as the updater, which also refuses to send unless the configured flag at `0x843061` is 2.

| Bytes | Debug string | Handler | What it does |
| --- | --- | --- | --- |
| `81 05 00 36` | ` CAL_JOY ` | `0x7ee0` | Logs and returns. No state change in this image. |
| `81 05 00 38` | `CAL_JOY_SAVE ` | `0x7f08` | Replies a 63-byte report whose first byte is `0x39`. |
| `81 05 00 51 00` | ` chanegBoot_Dinput - done ` | `0x7f74` | Clears bit 31 of the word at `0x800620`, clears it again in `0x7f50`, writes analog register `0x3c` = `0x5a`, then jumps to the RAM reset routine. This is a reboot into the other boot mode. |
| `81 05 ?? 51 nn` | `changePlatformCMD : %d` | `0x80f0` | Logs `nn` (report byte 4) and returns. Byte 2 is not checked. Print only in 1.03. |
| `81 05 00 21 01` | ` getVersion_Dinput - done ` | `0x7fb8` | Identify: reply `22`, version `67 00 00 00`, product id `1c 30`. Same shape as the pad's identify. |
| `81 05 00 31 01` | ` get_is_wiredGamepad - done ` | `0x802c` | Replies with payload byte `0x32`. |
| `81 11 04 08 dd dd ll rr` | `timer left_vibration : %x - %x - %x` | `0x8078` | Rumble: uint16 duration at bytes 5-6, left strength byte 7, right strength byte 8. Stores both, drives the motors through `0x6fac`, cancels any running stop timer and starts a new one. |
| `81 ?? 66 aa 63` | `getRFAddressCMD ` | `0x8114` | Reply `02 63`, 5 bytes from RAM `0x843124`, then version `0x67`. |
| `81 ?? 66 aa 64 a0..a5` | `setRFAddressCMD: ` | `0x8188` | Passes the 6 bytes at report offset 5 to `0x6eb4`, replies `02 64` plus 5 bytes from RAM `0x84308c`. |

`send_CAL_JOY: %d` and `usb_init`, `usb_stop`, `Flash_Erase_Config error` have no literal reference and are dead strings. The `81 ?? 66 aa 70` handler the pad has is not in the adapter.

## Over the radio

Report `81` does not cross the 2.4 GHz link in either direction. The receiver's USB handler at `0x36e`-`0x4c4` copies each OUT packet from the endpoint FIFO into a stack buffer, hands it to the XInput rumble and LED parser (`0x7cd0`) and then to its own two dispatchers, and returns; no radio transmit is called from that path, and the only handlers that touch the radio are rumble (through the motor driver) and the RF address commands. On the pad, the dispatcher at `0x9828` has exactly two callers, `0x4a34` and `0x4a6e`, both inside the USB handler that reads the endpoint FIFOs at `0x80011e` and `0x80011d`; the 2.4 GHz receive path never reaches it. So through the dongle a host is talking to the receiver's firmware (identify answers `301c`, version `0x67`), and the pad's settings record is out of reach.

## Where the pad keeps its settings (1.09)

There is no settings image. Persistent state is five small flash records, each in its own 4 KB sector, written by a module at offsets `0x5d00`-`0x5eb8` that erases the sector and rewrites the record through the flash write routine (called through a RAM function pointer at `0x842e3c`, which is why a call-graph sweep misses it). Reads go through the matching pointer at `0x842e50`. The addresses are built as `tmovs` plus `tshftls`, not literals.

| Flash | Bytes | Load | Save | Content |
| --- | --- | --- | --- | --- |
| `0x73000` | 26 | `0x5d78`, at boot from `0x7548` | `0x5d94`, via `0x7538` | The settings record: RF address, mode flags, and the L4/R4 binds. RAM copy at `0x843910`. |
| `0x74000` | 30 | none | `0x5d0e` | Writer `0x5046` has no caller in this image. Dead. |
| `0x75000` | 10 | read back and checksum-verified by `0x4ffc` | `0x5d44` from `0x4fd4` | Three uint32 plus a 16-bit checksum over the first 8 bytes. Written from the RAM-resident radio path (`0x334` inside the function at `0x242`), so most likely the link or pairing record. Not decoded further. |
| `0x76000` | 26 | `0x5dc0`, at boot from `0x76d8` | `0x5ddc` | The radio address. If bytes 0-5 are all `ff` or all `00` the pad generates one at `0x7698`: OUI `e4:17:d8` in bytes 5-3, the low three bytes XORed from the 6-byte chip id, and saves it. |
| `0x77000` | 2 | `0x5e08` | `0x5e24` | A uint16, forced to 1 at boot when it reads 0 or `ffff`. Value 2 selects the `(WUKONG)` product strings, anything else the plain `8BitDo Ultimate 2C Wired/Wireless Controller` strings. Set by `81 05 00 61 01 vv vv`, reported back at identify payload bytes 7-8. |
| `0x3f000` | 52 | none | `0x5ef0` from `0x8604` | A 48-byte block plus CRC32 with magic `0x0a0f0b0e` and a `0x40000` field, written after analog register `0x3c` is set to `0x5b`. `0x8604` has no caller in this image. This is the only writer below `0x40000`; the updater's write and erase helpers (`0x5ebc`, `0x5e9c`) refuse addresses outside `0x3f000`-`0x7f000`. |

**The `0x73000` record**, 26 bytes, RAM copy at `0x843910`:

| Bytes | Meaning |
| --- | --- |
| 0-4 | RF address override. Written only by `81 ?? 66 aa 64`, which first zeroes the whole record. |
| 5 | Pair selector for the binds, toggled by the button combination handled at `0x9014` (a LED sequence and a save). `0xff` reads as 0. |
| 6 | A boolean toggled by the combination handler at `0x6fa4` and applied through `0x4dd0` (stores it at `0x8433d6`). `0xff` reads as 0. |
| 7-8 | DInput-mode flags. `0x78e8` sets byte 7 to 1 when B (bit 12 of the live button word `0x84344c`) is held and clears bytes 7 and 8 when X (bit 4) is held, saves, then spins until the watchdog reboots the pad. The loader confirms byte 7 into byte 8 unless B is still held. The wired DInput flag `0x843470`, which makes identify report `301d` and selects the `301d` descriptor, follows it. This is the Home+B / Home+X power-on combo from the public reports. |
| 9-12 | Pair A, L4 mask (uint32 LE). |
| 13-16 | Pair A, R4 mask. |
| 17-20 | Pair B, L4 mask. |
| 21-24 | Pair B, R4 mask. |
| 25 | Unused by any reader found. |

Those four uint32 fields are the four paddle slots. The loader at `0x7548` accepts any value except 0, `0xfffffffe`, and `0xffffffff` (erased); an invalid slot is reset to its default, `0x00000002` for L4 and `0x00000004` for R4, and the record is saved again. The validated values are mirrored to RAM globals `0x84346c`, `0x843464`, `0x843460`, `0x843474`, and `0x77d4` writes them back into the record and saves it whenever one changed.

Which pair is live depends on the personality: `0x6172` uses pair A when the wired DInput flag byte `0x843470` is set and byte 5 is not 1, pair B when byte 5 is 1, and in the other personality falls back on bit 28 of `0x84342c`. The same flag byte is what makes identify report `301d` instead of `301b`.

**How a bind is applied.** `0x60d0` builds a 156-byte translation table at `0x843874`: 12 entries of 13 bytes, each `{uint32 input mask, uint32 output mask, 5 bytes}`, initialised with the output equal to the input. The input masks are bits 13, 12, 4, 5, 10, 11, 14, 15, 1, 2 of the pad's internal 32-bit button word for entries 0-9, and bits 25 (L4) and 26 (R4) for entries 10 and 11. After the table is built, the live pair's two masks from the record are written over the output masks of entries 10 and 11 (table bytes 134-137 and 147-150). So a bind is a 32-bit mask of internal button bits that L4 or R4 emits, and the defaults 2 and 4 mean bits 1 and 2.

**How a bind is set on the pad.** `0x6cc4`, called from the input scan at `0x7270`, takes the live button word (triggers past 32 are folded in as bits 14 and 15). It needs bit 27 held, exactly one of bit 25 (L4) or bit 26 (R4) held, and takes the new mask as the word masked with `0x0600ffff`, so bits 0-15 plus the two paddle bits. If that differs from the current output mask it writes it into the table entry, sets the entry's byte 11 as a custom flag, and calls `0x7880(pair, side, mask)`, which stores it in the global for that slot and, when the DInput flag is set, commits through `0x77d4` to the record and flash. Pressing the modifier with just the paddle, when a custom bind is set, stores the paddle's own bit (`0x02000000` or `0x04000000`) instead. This is the only path in the image that writes a paddle slot; no report `81` handler sets one.

**The button word.** The key scan at `0x67a4` drives four matrix rows through `0x6288`, reads five columns through `0x633c`, and ORs fixed bits into the word stored at `0x84342c` and `0x84344c`. Home is a GPIO (`0x800500` bit 4) with a ten-scan hold. L2 and R2 are analog and are folded in as bits 14 and 15 by the bind code. The numbering is the same as V2's `getKey` table in `spec/protocol.md`, which is how the names below are assigned; the four matrix keys V2 does not name are marked.

| Bit | Button | Scan | Bit | Button | Scan |
| --- | --- | --- | --- | --- | --- |
| 0 | Start | row 1, col 2 | 12 | B | row 3, col 1 |
| 1 | L3 | row 3, col 4 | 13 | A | row 4, col 1 |
| 2 | R3 | row 3, col 3 | 14 | L2 | trigger, folded |
| 3 | Select | row 3, col 2 | 15 | R2 | trigger, folded |
| 4 | X | row 2, col 1 | 16 | Share in V2's table | row 2, col 2 |
| 5 | Y | row 1, col 1 | 17 | Home | GPIO |
| 6 | Right | row 4, col 0 | 18 | unnamed | row 4, col 3 |
| 7 | Left | row 2, col 0 | 25 | L4 | row 1, col 3 |
| 8 | Down | row 3, col 0 | 26 | R4 | row 1, col 4 |
| 9 | Up | row 1, col 0 | 27 | bind modifier, unnamed | row 4, col 2 |
| 10 | L1 | row 2, col 4 | 28 | unnamed | row 4, col 4 |
| 11 | R1 | row 2, col 3 | | | |

So the slot defaults `0x00000002` and `0x00000004` are L3 and R3, a bind of `0x00002010` would be A plus X, and bit 27 is the button the manual calls Mapping (the star). Which shell buttons bits 16, 18, and 28 are was not determined; the 2C has more matrix keys than V2 names.

## Firmware 1.06

`u2c_1.06_1913.dat` has the same report-`81` set as 1.09. The two images have the same number of relative calls (1548), the handler region sits at `0x93bc`-`0x9c3c` in 1.06 versus `0x9380`-`0x9c00` in 1.09, and all twelve `0x81` prefix checks are there at the shifted addresses with the same compare sequence after each: the class `05` switch (`c1`, `c3`, `0005`, `0008`, `c2`, `0002`, `0003`, `0004`, `000b`, `c4`, `0007`) and the exact prefixes (`00 36`, `00 38`, `00 51 00`, `00 21 01`, `00 31 01`, `11 04 08`, `66 aa 63`, `66 aa 64`, `66 aa 70`, `00 61 01`). A diff of every compare immediate across the whole image differs in seven places, none in that region: 1.06 has extra checks in the boot init near `0x4326`-`0x43cc`, 1.09 adds three `#20` checks at `0x51e4`-`0x5238`, one clamp changes from 2 to 9 at `0x68e2`, and one constant from 84 to 79 at `0x7f3a`. The only differences inside the handler region are literal-pool RAM addresses shifted by `0x0c`. So 1.06 would answer the same commands and no others.

## What is still unknown

Whether Bluetooth (product id `301b`, after the adapter reboot) has a different report set. The cable image has no second config command to try, and guessing on `310a` is how the pad gets erased. The bind path in the image is button-combo only: nothing in either the pad or the adapter image reads or writes an L4/R4 mask from a host report.

Smaller gaps: which shell buttons sit on matrix bits 16, 18, and 28; what the 10-byte record at `0x75000` holds; and what the `301a` image contains, which needs the key the updater uses, not the file.
