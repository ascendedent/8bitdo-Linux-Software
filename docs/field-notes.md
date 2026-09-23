# Ultimate 2C config protocol: field notes

Original brief, kept as written apart from heading cleanup. Device IDs in here are community reports. The checked versions, with sources, live in `device-ids.md`.

Everything already public for running the 8BitDo Ultimate 2C on Linux, plus the plan for reverse engineering the one piece nobody has documented: how Ultimate Software V2 writes settings into the controller.

- Input report: already decoded in SDL and InputPlumber
- Config channel: undocumented, this project

## Where things stand

### Already solved

- Reading every input, including L4/R4, paddles, gyro and rumble, via 8BitDo's own SDL driver and InputPlumber's port of it.
- Binding L4/R4 on the controller itself with the button combo, no software needed.
- Out of the box dongle support on kernel 6.12 or newer.

### Still open

- Stick deadzones and curves, trigger ranges, vibration strength, macros and per-profile settings.
- All of these are written by Ultimate Software V2 over a proprietary channel. The 2C Wireless is on V2's supported device list, so the channel exists; it just is not documented.

## Cheat sheet: where to grab everything

### Official 8BitDo downloads

- [Ultimate Software V2](https://app.8bitdo.com/Ultimate-Software-V2/). The app to capture. Lists the Ultimate 2C Wireless as supported. Windows and macOS builds.
- [Ultimate 2C Wireless manual (PDF)](https://download.8bitdo.com/Manual/Controller/Ultimate/Ultimate-2C-Wireless-Controller.pdf). Official button combos, including onboard L4/R4 mapping.

### Input side reference code

- [SDL_hidapi_8bitdo.c](https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_8bitdo.c). Report parser contributed to SDL by 8BitDo. Read it for report layout, and check for any feature report calls.
- [InputPlumber PR #544](https://github.com/ShadowBlip/InputPlumber/pull/544). Rust UHID emulation of the Ultimate 2 Wireless (DInput mode), derived from the SDL file. Includes a working hidraw udev rule.

### Prior art on 8BitDo config protocols

- [TheJayMann/8bitdo-spec](https://github.com/TheJayMann/8bitdo-spec). HID config protocol for the Pro 2 and SN30 Pro+ (V1 era). Borrow its layout for the spec and use it as a first guess at framing.
- [Thoxy67/8bitult](https://github.com/Thoxy67/8bitult). Rust configurator for the 8BitDo Micro over BLE. The maintainer asks for captures of other devices, so this could be the home for 2C support instead of a new project.
- [goncalor/8bitdo-kbd-mapper](https://github.com/goncalor/8bitdo-kbd-mapper). Python tool plus udev rule that configures the Retro Mechanical Keyboard (a V2 era device) over USB HID. Template for CLI shape and permissions.
- [hughsie/8bitdo-firmware](https://github.com/hughsie/8bitdo-firmware). Linux firmware flashing for older 8BitDo devices. Useful mainly to recognize bootloader traffic so you know what to stay away from.

### Running the official app on Linux

- [archeYR: 8BitDo Firmware Updater in Wine](https://gist.github.com/archeYR/d687de5e484ce7b45d6a94415a04f3dc). Udev uaccess rules, disabling SDL in winebus, and the xpad caveat. Comments report V2 working, and one user fixed crashes by using Faugus Launcher with a CachyOS Proton prefix.
- [7pxvr: Run Ultimate Software V2 under Linux](https://gist.github.com/7pxvr/3921e097d0f8fb36f34a3d90a61d5e84). A second V2 writeup, with Lutris troubleshooting in the comments.
- Fallback: Windows VM with USB passthrough (VirtualBox or virt-manager). The Linux host's usbmon still sees passed-through traffic, so capture stays on the host either way.

### Capture and analysis tools

- [Wireshark](https://www.wireshark.org/) with the `usbmon` kernel module.
- [hid-tools](https://gitlab.freedesktop.org/libevdev/hid-tools). `hid-decode` reads report descriptors, `hid-recorder` logs raw reports. `pip install hid-tools`.
- [hidapi (Python)](https://pypi.org/project/hidapi/) or the [hidapi crate](https://crates.io/crates/hidapi). For replaying commands once a capture exists.
- [CRC RevEng](https://reveng.sourceforge.io/). Identifies checksum algorithms from a handful of sample packets.
- [ILSpy / ilspycmd](https://github.com/icsharpcode/ILSpy). V2 runs on .NET. Read the legal note before using this route. Capturing USB traffic is the path this repo is set up for.

### Community Linux notes

- [ammuench: 8BitDo Ultimate 2.4GHz on Linux](https://gist.github.com/ammuench/0dcf14faf4e3b000020992612a2711e2). Dongle setup notes. Comments include 2C Wireless specifics and the kernel 6.12 threshold.
- barraIhsan: `8BitDoUltimate2Wireless.md`. Gist summarizing mode switching on the Ultimate 2 Wireless (hold B for DInput, Y for Switch at power on). Search the name on gist.github.com.

## Controller facts to keep handy

| Fact | Value |
| --- | --- |
| Vendor ID | `2dc8` |
| 2C Wireless on dongle (XInput) | `2dc8:310a` in one user's `lsusb`. Confirm locally. |
| Ultimate 2 Wireless, for comparison | DInput `6012`, its dongle `6013` in these notes. Later public reports disagree; see `device-ids.md`. |
| Shared bootloader PID | `3208`. Never send anything to it. |
| Onboard L4/R4 binding | Hold L4 or R4 with the target button(s), then press Mapping. Repeat to clear. |
| Power on mode combos | B for DInput, Y for Switch on the Ultimate 2 Wireless. Unverified on the 2C. A later SDL comment says Home+B / Home+X for the 2C. |
| Known Linux caveat | In XInput mode the kernel xpad driver may not expose the extra HID interface the app uses to find the device. Try cable, DInput mode, or the VM route. |

## The reverse engineering plan

Do the capture work on the Fedora workstation, where installing Wireshark and friends is painless, and use the Bazzite box as the test target for the finished tool.

### 1. Inventory the device in every mode

Record what the controller exposes on the dongle (controller on and off), USB cable, and Bluetooth. Look for an interface with a vendor defined usage page (`0xFF00` or higher).

`tools/inventory.py` does the sysfs half of this. `hid-decode` is still worth running on any interface the script flags.

### 2. Get Ultimate Software V2 talking to it

Give your user hidraw access (`udev/71-8bitdo.rules`), disable SDL in winebus so the app gets raw HID, then run V2 in a Wine or Proton prefix (Faugus or Lutris).

```
wine reg add 'HKLM\System\CurrentControlSet\Services\winebus' \
  /v 'Enable SDL' /t REG_DWORD /d 0 /f
wineserver -k
```

Before touching anything, open V2 and write down every setting it offers for the 2C.

### 3. Capture a baseline

Start a capture, launch V2, let it detect the controller, change nothing, close it. This is the handshake and the read sequence.

```
sudo modprobe usbmon
python3 tools/inventory.py    # bus and device address
sudo wireshark                # capture on usbmonN
```

### 4. Differential captures

One change per file, and set the same setting to two different values. Names are in `captures/README.md` and the log is `docs/capture-log.md`.

### 5. Decode and write the spec

Export payloads and diff pairs. Expect some mix of a report ID or command byte, a length, a setting ID, the value, a trailing checksum, and possibly a sequence counter. Separate read, write, and commit. Write the result into `spec/protocol.md`, not into a guess.

```
tshark -r 04_dz_10.pcapng -Y 'usb.device_address == MMM' \
  -T fields -e frame.number -e usb.bmRequestType \
  -e usb.data_fragment -e usb.capdata > 04.txt
diff 04.txt 05.txt

reveng -w 16 -s <hex1> <hex2> <hex3>
```

### 6. Replay: read first, then one write

Start read only. Send a read command copied byte for byte from the capture, and confirm the reply matches what V2 received. Then replay one exact captured write, power cycle, and verify the setting stuck in V2, over the dongle, and over Bluetooth with no software running.

### 7. Build the tool

- CLI first: `dump` to a JSON backup, `restore`, `set` for individual settings, `profile` for slot selection.
- Hard refuse to talk to any bootloader PID, and require a fresh backup before the first write.
- Rust matches 8bitult and InputPlumber. Python is faster for the prototype.
- For Bazzite, ship as a Homebrew formula or a Flatpak, plus the udev rule.

### 8. Publish

- Spec repo in the 8bitdo-spec style, with sample captures. Strip the controller serial first.
- Tag the repo `8bitdo` on GitHub, open an issue on 8bitult offering the captures, and post in the Bazzite and SteamOS communities.
- Note which other V2 devices share the framing (Ultimate 2 Wireless, Pro 3).

## Rules that keep the controller alive

See `safety.md`. Short version: never talk to PID `3208`, dump before the first write, replay only exact captured writes until a field is mapped, keep the official app as the recovery path.

## Open questions

- Does V2 configure the 2C over the dongle, or only over a USB cable?
- Is the channel feature reports on a vendor page, or interrupt reports on a separate interface?
- Is there a separate commit command, or does every write go straight to flash?
- Checksum or sequence counter in the packets?
- Does the 2C share framing with the older Pro 2 protocol, or with newer V2 devices?

## Legal note

Reverse engineering for interoperability is generally protected (in the US under the DMCA's interoperability exemption, 17 U.S.C. 1201(f), and in the EU under Article 6 of the Software Directive). Capturing USB traffic between your own app and your own controller is the route this repo is set up for. Decompiling V2 may conflict with its license terms, so check the EULA first. This is general information, not legal advice.

Prepared September 2026.
