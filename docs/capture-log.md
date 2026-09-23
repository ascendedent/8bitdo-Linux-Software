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

## `04_probes`: three reply-only commands, pending

Authorized 2026-09-23 (afternoon), cable, `310a`. Each was checked in the 1.09 image first (`docs/firmware.md`): `81 05 00 31 01` only builds a reply with payload byte `0x32`; `81 00 66 aa 63` replies with the 5-byte radio address and version, then stores request byte 1 into a RAM mode flag, so byte 1 is sent as `00` to leave that flag at its boot value; class `05` command `0008` (`81 05 08 00`) fills a reply with `0x301b`. `tools/read_config.py --probes` sends exactly those 64-byte packets and refuses `66 aa 63` with any other byte 1, `66 aa 64`, `00 61 01`, `00 51 00`, `00 36`, and `00 38`.

The run itself was blocked by the agent's permission layer, so it has not happened yet. To run it:

```
python3 tools/read_config.py --probes --skip crc --timeout-ms 1000 --log captures/exports/04_probes.txt
```

Expected, from the image: `02 32 ...`; `02 63 a0 a1 a2 a3 a4 6d ...` (the radio address, which is an identifier for this pad, so redact it before committing the log); `02 05 00 00 08 00 02 00 02 00 00 00 1b 30`.

## `05_inventory_after_dongle_update`: read-only, 2026-09-23

The dongle's firmware was updated with V2 on 2026-09-23 (afternoon). `tools/inventory.py` afterwards, no HID reports sent, saved to `captures/exports/05_inventory_after_dongle_update.txt`:

- `3-5.1`: `301c` `IDLE`, bcdDevice `2.00`, one HID interface, 42-byte descriptor on page `0xffa0` with reports `02` and `81`. Same bcdDevice as before the update, and the descriptor is byte for byte the `0xFFA0` descriptor in the adapter 1.03 image.
- `3-5.2.2.2`: `310a` on the cable, bcdDevice `1.14`, the same three interfaces as `docs/cable-inventory.md`.

Everything about the receiver that was captured before the update still matches from the outside. What the update changed can only be seen by talking to it, so these are the retests, all through the dongle with the pad on (the dongle then enumerates as `310a`; the tools never open the idle `301c`):

1. `tools/inventory.py` with the pad linked, to confirm the dongle presents `310a` with the same three interfaces as the cable.
2. `tools/identify.py --path <dongle sysfs name>` (or `tools/read_config.py --path ... --probes --skip crc`). Per `docs/firmware.md` the receiver answers identify itself: expect version byte `0x67` if it is now on 1.03 and product id `1c 30`, not the pad's `1b 30`. A different version byte means the server has a newer receiver build than the one in `vendor/firmware/`, in which case fetch it (`docs/firmware.md`, type 76) and re-run the adapter disassembly.
3. The `02_idle_dongle` observation (V2 sends nothing to `301c`) does not need repeating; it is about V2, not the dongle.

`--path` exists because the cable and the dongle can both be attached as `310a` at once; the tools refuse to guess.

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
