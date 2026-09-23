# Device IDs

Vendor ID for every 8BitDo device: `2dc8`.

IDs below are from public sources. Confirm each one with `tools/inventory.py` on the hardware before treating it as fact. Nothing in this table was read off a controller in this repo yet.

| PID | Name | Where it was reported | Status here |
| --- | --- | --- | --- |
| `310a` | Ultimate 2C Wireless, XInput. Same ID on the 2.4 GHz dongle and on a USB cable. | usb.ids note by hayleox (2025-08-25); `lsusb` in [SDL issue 12219](https://github.com/libsdl-org/SDL/issues/12219); linux-hardware.org | Expected primary target |
| `301b` | Ultimate 2C Wireless, Bluetooth, DirectInput | [PCGamingWiki](https://www.pcgamingwiki.com/wiki/Controller:8BitDo_Ultimate_2_Controller) | Unverified |
| `310b` | Ultimate 2 Wireless, USB / dongle, XInput | PCGamingWiki | Comparison device, not the 2C |
| `6012` | Ultimate 2 Wireless, DInput. SDL treats this as the Bluetooth-mode product. A macOS report also saw `6012` on the dongle in DInput. | SDL `usb_ids.h`; [SDL issue 14902](https://github.com/libsdl-org/SDL/issues/14902) | Comparison device |
| `6013` | Ultimate 2 Wireless dongle | Field notes, community report | Unverified. Conflicts with the `310b` / `6012` reports above until someone plugs one in. |
| `3208` | Shared bootloader | Field notes | **Never send traffic.** |
| `5750` | Older 8BitDo bootloader | Public USB ID tables (devicekb) | **Never send traffic.** Not known to be the 2C's bootloader. |

Kernel: `310a` is in `xpad` since Linux 6.12. This workstation is on `7.2.0-359.vanilla.fc44`, so the XInput interface should bind to `xpad` without a patch.

## What `310a` exposes in XInput

From the dmesg pasted in SDL issue 12219 (Arch, kernel 6.13, dongle or cable, XInput):

- Interface 0 is the XInput function. `xpad` claims it. Class `ff/5d/01`.
- Interface 1 is a USB HID device that `hid-generic` binds as both a keyboard and a mouse (`USB HID v1.11`).

SDL's own 8BitDo HIDAPI driver does **not** list `310a`. The decoded input reports in `SDL_hidapi_8bitdo.c` are for the Pro 2, Pro 3, Ultimate 2 Wireless (`6012`), and Ultimate 3. They are the wrong document for the 2C's XInput report, and they are not the config channel.

The interface 1 HID descriptor is the first thing `inventory.py` should print. A vendor-defined usage page (`0xFF00` or higher) on that interface is the config-channel candidate.

## Mode combos, still second-hand

| Combo | Claimed result | Source | Applies to |
| --- | --- | --- | --- |
| Hold Home+B while powering on | DInput over 2.4 GHz | Comment by jeffyl on [SDL PR 11415](https://github.com/libsdl-org/SDL/pull/11415) | Ultimate 2C. Unverified here. |
| Hold Home+X while powering on | XInput | Same comment | Ultimate 2C. Unverified here. |
| Hold B while powering on | DInput | Field notes | Ultimate 2 Wireless. Not claimed for the 2C. |
| Hold Y while powering on | Switch | Field notes | Ultimate 2 Wireless. Not claimed for the 2C. |
| Hold L4 or R4 with the target buttons, then Mapping | Onboard L4/R4 bind. Repeat to clear. | Official 2C manual | Ultimate 2C |

DInput mode is worth a separate inventory pass. XInput mode is the one where `xpad` can hide the interface Ultimate Software is looking for.
