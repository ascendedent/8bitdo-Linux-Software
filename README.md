# Ultimate 2C config protocol

Read and write the settings Ultimate Software V2 stores in an 8BitDo Ultimate 2C Wireless: stick deadzones and curves, trigger ranges, vibration strength, button maps, macros, profiles.

Input reports are already decoded elsewhere. This repo is the config channel, which is not.

The controller was not attached when this folder was created (2026-09-22, Fedora, kernel `7.2.0-359.vanilla.fc44`). The next real step needs the dongle or a cable.

## Start here when the controller is plugged in

```
python3 tools/inventory.py
```

That only reads sysfs. It prints every `2dc8` device, the interfaces, the hidraw node, and whether any report descriptor has a vendor usage page (`0xFF00` or higher). That page is the config-channel candidate. It also prints the usbmon interface and the Wireshark device-address filter for the capture.

Run it four times and keep the output:

1. Dongle plugged in, controller off.
2. Dongle, controller on, however it powers on by default.
3. USB cable.
4. After the Home+B power-on combo (reported as DInput on the 2.4 GHz link; not yet confirmed on this hardware).

Paste each run into `docs/capture-log.md`.

Then, before any capture, open Ultimate Software V2 and write down every setting it shows for the 2C. That list is the feature scope.

## What is already known

- `2dc8:310a` is the 2C in XInput, and public reports say the dongle and the cable share that ID. Bluetooth DirectInput is reported as `2dc8:301b`. Confirm both locally.
- In XInput the kernel's `xpad` driver takes interface 0. A second interface enumerates as a USB HID keyboard and mouse. That second interface is the first place to look. Details and sources are in `docs/device-ids.md`.
- SDL's 8BitDo driver does not claim `310a`. Its feature reports (`0x06`, `0x30`) and its rumble output (`0x05`) belong to other models. They are documented in `docs/sdl-channel.md` so a capture can be sorted into "input channel" and "everything else".
- The Pro 2 config protocol (report `0x81`, read command `02 00`, write `01 00`, finish `06` with subrequest `21`, 45-byte chunks) is the V1-era pattern to test against the baseline capture. It is a hypothesis. See `docs/v1-framing.md`. Do not send those bytes.

## What is not known

All of these are open until a capture answers them. The empty spec is `spec/protocol.md`.

- Does V2 configure the 2C over the dongle, or only over a cable?
- Feature reports on a vendor page, or interrupt reports on the second interface?
- A separate commit command, or does every write go straight to flash?
- Checksum, sequence counter, or both?
- Same framing as the Pro 2, or a V2 framing shared with the Ultimate 2 Wireless and the Pro 3?

## Layout

| Path | What it is |
| --- | --- |
| `docs/field-notes.md` | The original brief, including the capture plan and the prior art. |
| `docs/device-ids.md` | IDs, with the source and whether we have seen them. |
| `docs/sdl-channel.md` | Input-side commands from SDL, so they are not mistaken for config. |
| `docs/v1-framing.md` | Pro 2 packet shape as a hypothesis. |
| `docs/safety.md` | What does not get sent. |
| `docs/capture-log.md` | One row per capture. Empty. |
| `spec/protocol.md` | The spec. Empty on purpose. |
| `tools/inventory.py` | Read-only USB inventory. |
| `udev/71-8bitdo.rules` | hidraw `uaccess` for `2dc8`, excluding bootloader PIDs `3208` and `5750`. Not installed. |
| `captures/` | pcapng files. Gitignored, because descriptors can carry a serial. |

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
