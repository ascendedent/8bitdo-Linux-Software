# Capture log

Fill one row per file. Leave the payload notes blank until the diff is done.

Host: Fedora, kernel `7.2.0-359.vanilla.fc44.x86_64`. Cable inventory on 2026-09-23 is in `cable-inventory.md`. No pcap yet.

| File | Date | Connection | VID:PID | Bus / address | V2 setting before | V2 setting after | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 00_baseline | 2026-09-23 | USB cable, mode switch on Bluetooth | `2dc8:310a` bcdDevice `1.14` | bus 3 addr 24 | unknown (firmware update had just finished) | no setting changed | V2 1.35 under Wine. Two probe commands on EP 6, two replies on EP 3, then silence. No config read. See `captures/exports/00_baseline.txt`. |
| 01_L4_A | | | | | | | |
| 02_L4_B | | | | | | | |
| 03_L4_clear | | | | | | | |
| 04_dz_10 | | | | | | | |
| 05_dz_20 | | | | | | | |
| 06_rdz_10 | | | | | | | |
| 07_vib_50 | | | | | | | |
| 08_trig | | | | | | | |
| 09_profile2 | | | | | | | |
| 10_macro | | | | | | | |
| 11_reset | | | | | | | |

## Feature list from V2

Write this down before the first capture, with the controller connected and no settings changed. This is the feature scope.

- [ ] Profiles (how many, how selected)
- [ ] Button remap, including L4 / R4
- [ ] Stick deadzone and curve, per stick
- [ ] Trigger range
- [ ] Vibration strength
- [ ] Macros
- [ ] Anything else the 2C page shows

## 03_reads, 2026-09-23 11:15 and 11:16

Not a V2 capture. `tools/read_config.py` sent read-only probes to the cable-connected 2C (`2dc8:310a`, bus 3 device 31, `/dev/hidraw21`, page `0xFF7A`) with the user's authorization. Transcripts are `captures/exports/03_reads.txt` and `03_reads_run2.txt`. `captures/03_reads.pcapng` is the second run, filtered to device 31.

| Sent | Times | Reply |
| --- | --- | --- |
| `81 05 00 21 01` | 2 | `02 22 6d 00 00 00 1b 30 01`, same as the baseline |
| `81 05 c1 00` | 2 | `02 05 00 00 c1 00`, then `08 34 84 00 f0 33 84 00 00 10` at offset 22, same as the baseline |
| Ultimate 2 chunked read, `81 3e 04 02 00 00 00 2d 00 00 00 38 06 00 00 00 00 00 00` plus 45 `cc` | 6 | Nothing. 800 ms timeout each time. |
| `custom_info` read, `81 3e 04 0c cc .. 2d cc 30 02 00 00 cc ..` | 6 | Nothing. |
| `readCRC`, `81 05 c3 00 00 00 0c 00 00 00` | 2 | `02 05 00 00 c3 00 0c 00 00 00`, then `ff ff` at offset 18 |

The pad kept answering the identify commands after the ignored reads, and still enumerates as `310a`. The section-`04` config reads are ignored. The class-`05` firmware-updater commands are answered.

## `04_probes`: three reply-only commands, 2026-09-23 13:05

Authorized, cable, `310a` at `3-5.2.2.2`, `tools/read_config.py --probes --skip crc`. Each command was checked in the 1.09 image first (`docs/firmware.md`): `81 05 00 31 01` only builds a reply with payload byte `0x32`; `81 00 66 aa 63` replies with the 5-byte radio address and version, then stores request byte 1 into a RAM mode flag, so byte 1 was sent as `00` to leave that flag at its boot value; class `05` command `0008` (`81 05 08 00`) fills a reply with `0x301b`. The tool refuses `66 aa 63` with any other byte 1, `66 aa 64`, `00 61 01`, `00 51 00`, `00 36`, and `00 38`. Transcript in `captures/exports/04_probes.txt`, radio address redacted there; the raw copy is gitignored.

| Sent | Replies | Reply |
| --- | --- | --- |
| `81 05 00 21 01`, `81 05 c1 00` | 1 each | Identical to the baseline and to `03_reads`. |
| `81 05 00 31 01` | 1 | `02 32`, rest zero. As predicted. |
| `81 00 66 aa 63` | 1 | `02 02 63`, five address bytes, `00 6d 00 00 00`, rest zero. The version is stored as a uint32 at payload offset 8, so there is a zero byte between the address and `6d`; the prediction had them adjacent. |
| `81 05 08 00` | 1 | `02 05 00 00 08 00 02 00 00 00 02 00`, then `1b 30` at offset 18. The class `05` reply frame: `02 05 00 00`, the command uint16, the header bytes from 4 on, and the 46-byte payload area from offset 18, the same frame `readCRC` used. |

The pad kept identifying afterwards. Three more handlers in the table are now confirmed against the wire, and the radio address the pad reports is a 5-byte value, matching the 5 bytes `66 aa 64` would write.

## `05_inventory_after_dongle_update`: read-only, 2026-09-23

The dongle's firmware was updated with V2 on 2026-09-23 (afternoon). `tools/inventory.py` afterwards, no HID reports sent, saved to `captures/exports/05_inventory_after_dongle_update.txt`:

- `3-5.1`: `301c` `IDLE`, bcdDevice `2.00`, one HID interface, 42-byte descriptor on page `0xffa0` with reports `02` and `81`. Same bcdDevice as before the update, and the descriptor is byte for byte the `0xFFA0` descriptor in the adapter 1.03 image.
- `3-5.2.2.2`: `310a` on the cable, bcdDevice `1.14`, the same three interfaces as `docs/cable-inventory.md`.

Everything about the receiver that was captured before the update still matches from the outside. What the update changed is answered by `06` and `07` below: the receiver is on 1.03, the image `docs/firmware.md` analyses.

## `06_inventory_dongle_linked`: read-only, 2026-09-23 13:10

Cable unplugged, pad powered on wirelessly. The dongle at `3-5.1` re-enumerated as `310a`, bcdDevice `1.14`, product string `8BitDo Ultimate 2C Wireless Controller`, with the same three interfaces as the cable (XInput, 166-byte keyboard/consumer/mouse HID, 33-byte page `0xFF7A` HID). Saved to `captures/exports/06_inventory_dongle_linked.txt`. That is the `310a` personality inside the adapter image, not the pad.

## `07_dongle_probes`: identify and the three probes through the dongle, 2026-09-23 13:12

Same tool and packets as `04_probes`, `--path 3-5.1`. Every reply is the receiver's, as `docs/firmware.md` predicted from the adapter image; nothing reached the pad.

| Sent | Reply through the dongle | Reply on the cable (`04_probes`) |
| --- | --- | --- |
| `81 05 00 21 01` | `02 22 67 00 00 00 1c 30 00 00` | `02 22 6d 00 00 00 1b 30 01 00` |
| `81 05 c1 00` | `02 05 00 00 c1 00`, zeros, then `00 10` at offset 30 | same frame, but `08 34 84 00 f0 33 84 00` at offset 22 |
| `81 05 00 31 01` | `02 32` | `02 32` |
| `81 00 66 aa 63` | `02 02 63`, five address bytes, `00 67 00 00 00` | `02 02 63`, five different address bytes, `00 6d 00 00 00` |
| `81 05 08 00` | class-`05` frame, `1c 30` at offset 18 | same frame, `1b 30` at offset 18 |

So the receiver runs firmware 1.03 (version byte `0x67`, matching the `u2c_adapter_1.03.dat` header), identifies as `301c`, has no product-string selector (bytes 8-9 zero), and reports its own 5-byte radio address, which differs from the one the pad reports on the cable. The two address bytes are redacted in the committed transcripts. The retest list above is closed: the dongle's report set is the one tabulated in `docs/firmware.md`, and a host on the dongle path is talking to the receiver.

## Tester reports, 2026-09-23/24 (GitHub issues 1-6)

Three volunteers with an Ultimate 2 Wireless ("8BitDo Ultimate 2 Wireless Controller for PC") ran the read tool. None got a config reply, and the descriptors they posted, together with the pad and receiver firmware images fetched the next morning, explain every line:

| Issue | Connection | Id | Interfaces | What the tool did |
| --- | --- | --- | --- | --- |
| 1 (andromalandro), 4 (kropop) | dongle, DInput | `6012` | one HID, 113-byte descriptor, pages `0x01 0x02 0x09 0xff00 0x0f`, reports `01`, `05` | Opened it (vendor page `0xff00`), sent `81 3e 04 ...`, read the pad's 34-byte input reports back as "replies". No report `81` exists on this personality. |
| 2 (andromalandro) | cable, XInput | `310b` | XInput + 166-byte keyboard/mouse + 33-byte `0xff7a` (`02`/`81`) | Run with `--pid 6012`; refused because only `310b` was present. |
| 3 (kropop), 5 (ChibiChoko) | cable / dongle, XInput | `310b` | as above; ChibiChoko's dongle also showed idle `3107 IDLE` | Opened interface 2, sent `81 3e 04 ...` three times, silence. |
| 6 (ChibiChoko) | cable, XInput | `310b` | as above | Inventory pasted into both fields; no read. |

The pad image tests byte 1 of a report-`81` packet for `04` before dispatching section `04`; the DLL sends `81 04 <body>` to the Ultimate 2 and the size-byte form only to older products (`docs/firmware.md`). So the `310b` silence is the frame, and the `6012`-on-dongle result is the personality. The tool now builds the right frame per product id, picks the pad automatically, skips input reports while waiting for a reply, warns when the opened interface declares no `81`/`02`, and can send V2's switch-to-DInput command behind `--switch-to-dinput --yes`.

## Planned: Bluetooth, once the adapter is back

1. Pair the pad (`bluetoothctl`, it should appear as `8BitDo Ultimate 2C Wireless Controller`). `tools/inventory.py` then lists it as `0005:2DC8:301B.<n>` with its report descriptor; save that as `08_inventory_bluetooth.txt`.
2. If the descriptor carries a vendor page, `tools/identify.py --pid 301b`, then `tools/read_config.py --pid 301b --probes --skip crc`. The read tool does not yet accept `301b`; add it to `PAD_PIDS` in `tools/identify.py` when the inventory shows a vendor-page descriptor to send to.
3. Capture with `btmon -w captures/08_bluetooth.btsnoop` alongside, since usbmon does not see Bluetooth.

Expected from the 1.09 image: no reply. The pad's report-`81` dispatcher has two callers, both in its USB endpoint handler, and the Bluetooth HID path does not reach it.

## Wireshark filters

Replace `MMM` with the device address from `lsusb` (the number after `Device`).

```
usb.device_address == MMM
usb.bmRequestType == 0x21 || usb.bmRequestType == 0xa1
usb.transfer_type == 0x01 && usb.endpoint_address.direction == 0
```

Export:

```
tshark -r captures/04_dz_10.pcapng -Y 'usb.device_address == MMM' \
  -T fields -e frame.number -e usb.bmRequestType \
  -e usb.data_fragment -e usb.capdata > captures/exports/04.txt
```
