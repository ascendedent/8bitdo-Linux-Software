# 8BitDo Linux Software

Toward a Linux tool that configures 8BitDo pads the way Ultimate Software does on Windows. So far: what Ultimate Software V2 actually sends to an 8BitDo Ultimate 2C Wireless, what the 2C's firmware answers, and read-only tools that also cover the Ultimate 2 Wireless, which is the first pad with a real config channel. Nothing here writes to a pad yet; `tools/u2_plan.py` shows what a write would be without sending it.

On 2026-09-23, V2 1.35 identified the controller and offered firmware. It did not read or write stick deadzones, trigger ranges, vibration, button maps, macros, or profiles. Those editors exist in this build for the Ultimate 2. The 2C has a product name and no profile data. L4 and R4 on this pad are the onboard Mapping button.

Details are in `spec/protocol.md`.

## What was observed

Cable and dongle, controller on, are the same device: `2dc8:310a`, firmware `1.14`.

| Interface | What it is |
| --- | --- |
| 0 | XInput, owned by `xpad` |
| 1 | Keyboard, consumer control, and a small mouse |
| 2 | Vendor page `0xFF7A`. Output report `81`, input report `02`. This is the channel V2 uses. |

V2 sent two commands and stopped:

| Direction | Payload |
| --- | --- |
| Out | `81 05 00 21 01` |
| In | `02 22 6d 00 00 00 1b 30 01` |
| Out | `81 05 c1 00` |
| In | `02 05 00 00 c1 00`, then later in the packet `08 34 84 00 f0 33 84 00 00 10` |

The first reply contains `1b 30`, little-endian `0x301b`. Holding B or X while plugging the cable did not change the USB identity. With the controller off, the dongle stays `2dc8:301c`, product `IDLE`, and V2 sends it nothing.

The Pro 2 config read (`81 3e 04`, looping `02 00` chunks) did not appear. Do not send those bytes.

## What the firmware says

The 1.09 image the pad is running was fetched from 8BitDo's update server and disassembled (`docs/firmware.md`). It settles most of the questions the captures left open:

- Report `81` has an updater (the class `05` commands V2's DLL names), identify, rumble, RF address get and set, a product-string selector, and nothing else. There is no settings read and no settings write.
- The L4/R4 binds are four 32-bit button masks in a 26-byte record at flash `0x73000`, set only by the on-pad combo. No host command reads or writes them.
- The receiver (`301c`) answers report `81` itself and never relays it to the pad, so the dongle is not a way in either. Confirmed on the wire: through the dongle, identify returns the receiver's version and id, not the pad's.
- Firmware 1.06 has the same command set. The Bluetooth 2C (`301a`) image is encrypted, and V2 1.35 routes that id to firmware-only as well.
- The Ultimate 2 Wireless images (pad and receiver) are readable too, and unlike the 2C the pad implements the section-`04` config channel: read, write, and commit handlers over a 1592-byte image, framed `81 04 <body>`, live on the cable DInput personality and on `310b`, and relayed by the receiver.

## Still open

Bluetooth. Public reports call DirectInput mode `2dc8:301b`, and the 1.09 image plants that id in its identify reply and its Bluetooth PnP record. The workstation's MediaTek MT7925 Bluetooth USB device dropped off the bus on 2026-09-23 and needs a reboot before it can be inventoried. That is the last channel where the pad could have a different report set. The tools are ready for it: after pairing, `tools/inventory.py` lists the pad from the Bluetooth HID bus, and `tools/identify.py --pid 301b` sends the same two identify commands to it. The 1.09 disassembly says the pad's report-`81` handler is only reached from its USB endpoints, so the expected result is silence; an answer would be news.

## Help wanted: Ultimate 2 owners on Linux

The 2C turned out to have no host-side config channel at all, so this repo cannot grow into a general 8BitDo config tool on the 2C alone. The next device that matters is the **Ultimate 2 Wireless** (`2dc8:6012` in DInput, `310b`/`6013` on the dongle), because V2 reads and writes a 1592-byte config image on it and this repo already knows that image's layout from the V2 binaries. What is missing is one real image from a real pad. If you have one and run Linux, this takes about ten minutes and sends the pad nothing V2 does not send on every connect.

What the tools do and do not do:

- `tools/inventory.py` walks sysfs and prints descriptors. It sends nothing.
- `tools/read_config.py --pid 6012` sends only the config **read** V2 issues when the pad connects (request 2, in 45-byte chunks). Every packet is checked against an allowlist before it leaves; writes, commits, firmware commands, and the bootloader ids are refused in code, and there is a test for that.
- Nothing is written to the pad. Nothing is flashed. The pad's own settings are not changed.

Steps:

```
git clone https://github.com/ascendedent/8bitdo-Linux-Software
cd 8bitdo-Linux-Software
sudo cp udev/71-8bitdo.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger
# plug the pad in on its USB cable
python3 tools/inventory.py | tee inventory.txt
python3 tools/read_config.py --summary
```

The read tool picks the one pad it finds. Which connection works, from the Ultimate 2 firmware images (`docs/firmware.md`):

- **Cable, XInput (`310b`)**: the config channel is on interface 2. Try this first; it needs no mode change.
- **Cable, DInput (`6012`)**: the config channel is in the gamepad interface. If XInput gives no reply, `python3 tools/read_config.py --switch-to-dinput --yes` sends the one command Ultimate Software uses to reboot the pad into DInput mode, then run the read again. Home+X at power-on is the usual way back to XInput.
- **Dongle in XInput (`310b`)**: the receiver relays to the pad. Also fine.
- **Dongle in DInput (`6012`)**: no config channel; the tool warns and the pad only streams its input reports. Use the cable.

If the tool sees more than one pad, add `--pid` or `--path <name>` from the inventory. If it says it found no interface with a vendor usage page, pass the hidraw node whose report ids include `0x81` and `0x02` with `--node /dev/hidrawN`.

The first six tester reports (2026-09-23/24) were made with a tool that framed the read the way V2 frames it for older pads; the Ultimate 2 drops that frame, which is why they all got silence. Fixed the next day. Thank you to andromalandro, kropop and ChibiChoko for the descriptors and transcripts that showed it.

What to send back, as a GitHub issue or a pull request: `inventory.txt`, the transcript, and the `.bin`. Before you do, look at the `--summary` output: the image carries your three profile names and whatever you set in V2, and the transcript carries the pad's descriptors. The pad's USB serial is never printed. If any of that is private, say so and send just the summary.

If you also have a Windows machine or Wine with Ultimate Software V2, the second-most useful thing is a usbmon capture of V2 changing one setting (a stick dead zone, say) and saving; `docs/capture-log.md` has the Wireshark filters. That is optional.

## Where this is going

1. **Now:** read-only. Inventory, identify, and the probes on the 2C; the connect-time config read on an Ultimate 2. Every packet is allowlisted, and the tests pin the allowlist.
2. **Next, once one real Ultimate 2 image arrives:** check `u2_summary.py` against what the owner actually set, and settle which byte range the pad's `crc_value` covers (the summary prints the candidates).
3. **Then:** a send path for `u2_plan.py`, gated on that image matching. Per-field writes first (one chunk, commit), exactly as V2 does them, with a read-back to confirm. A full-image save last.
4. **Not planned:** anything that talks to a bootloader id, and any write to the 2C. The 2C has nothing to write to, and the receiver's updater commands are the only writes it accepts.

## Layout

| Path | What it is |
| --- | --- |
| `docs/field-notes.md` | The original brief and the capture plan. |
| `docs/device-ids.md` | IDs, with the source and whether we have seen them. |
| `docs/cable-inventory.md` | USB cable descriptors. |
| `docs/firmware.md` | The fetched firmware images, the report `81` command tables for the pad and the receiver, and where the pad stores its settings. |
| `docs/sdl-channel.md` | Input-side commands from SDL, so they are not mistaken for config. |
| `docs/v1-framing.md` | Pro 2 packet shape. Tested against the baseline and not what V2 sent. |
| `docs/safety.md` | What does not get sent. |
| `docs/capture-log.md` | Capture log. |
| `spec/protocol.md` | The spec. |
| `tools/inventory.py` | Read-only USB inventory. |
| `tools/identify.py` | Replays the two captured identify commands to `310a` only and decodes the reply. |
| `tools/read_config.py` | Allowlisted reads. On the 2C: identify, `--probes`, `readCRC`; the two chunked reads it ignores are behind `--unanswered`. On an Ultimate 2 (`--pid 6012`): the config read V2 sends on connect, saved as an image. |
| `tools/u2_summary.py` | Decodes a 1592-byte Ultimate 2 image into fields. No HID device. |
| `tools/u2_plan.py` | Plans one Ultimate 2 setting change the way V2 writes it and prints the packets. Sends nothing. |
| `tools/test_*.py` | The allowlist, device selection against a fake sysfs, the identify decoder, the image summary, and the planner. No HID device. Run with `cd tools && python3 -m unittest`; CI runs the same. |
| `docs/call-for-testers.md` | The post asking Ultimate 2 owners for a read. |
| `tools/packets.py` | Builds the identify commands, the `custom_info` reads, and the Ultimate 2 write and commit. Does not send them. |
| `tools/ultimate2_image.py` | Offsets of the stick, trigger, vibration, and other records in the 1592-byte image. |
| `tools/test_packets.py` | Checks those bytes. No HID device. |
| `udev/71-8bitdo.rules` | hidraw `uaccess` for `2dc8`, excluding bootloader PIDs `3208` and `5750`. Not installed. |
| `captures/exports/` | The payload notes. pcapng files are gitignored. |

## Udev

Install only when you are about to run V2 under Wine or open the device from a user tool:

```
sudo cp udev/71-8bitdo.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

The rule does not grant access to the bootloader IDs.

## Recovery

Keep Ultimate Software V2 installable. Wine notes from other people are linked in the field notes. A Windows VM with USB passthrough also works, and the Linux host's usbmon still sees the traffic.

PID `3208` and PID `5750` are bootloaders. Nothing in this repo talks to them.
