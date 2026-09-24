# Device IDs

Vendor ID for every 8BitDo device: `2dc8`.

IDs below are from public sources. Confirm each one with `tools/inventory.py` on the hardware before treating it as fact. Nothing in this table was read off a controller in this repo yet.

| PID | Name | Where it was reported | Status here |
| --- | --- | --- | --- |
| `310a` | Ultimate 2C Wireless, XInput. Same ID on the 2.4 GHz dongle and on a USB cable. | usb.ids note by hayleox (2025-08-25); `lsusb` in [SDL issue 12219](https://github.com/libsdl-org/SDL/issues/12219); linux-hardware.org | Seen on the cable and on the dongle with the controller on, 2026-09-23. bcdDevice `1.14`. Same three interfaces either way. On the dongle it is the receiver's own `310a` personality: identify through it answers with the receiver's version and `301c` (`docs/capture-log.md`, `07_dongle_probes`). |
| `301b` | Ultimate 2C Wireless, Bluetooth, DirectInput | [PCGamingWiki](https://www.pcgamingwiki.com/wiki/Controller:8BitDo_Ultimate_2_Controller) | Unverified. The identify reply contained this value. The dongle itself did not enumerate as `301b`. The 1.09 image plants `301b` in its identify reply and in its Bluetooth PnP record, and also carries a `301d` device descriptor for the wired DInput personality. |
| `301d` | Ultimate 2C Wired Controller, the DInput personality inside the 1.09 image. Identify reports it instead of `301b` while the DInput flag is set (B held at power-on). One HID interface, 145-byte report descriptor. | `docs/firmware.md` | Not seen on the bench. |
| `301c` | Dongle while the controller is off. USB product string is `IDLE`. bcdDevice `2.00`. One HID interface. | Seen 2026-09-23 for about six seconds after the dongle was plugged, then replaced by `310a` when the controller connected. | Seen. A serial string is present. It was not written down. |
| `310b` | Ultimate 2 Wireless, USB / dongle, XInput. Three interfaces exactly like the 2C's `310a`, including the page `0xFF7A` interface with reports `02`/`81`. V2 calls it `PID_Xinput` and does not configure on it. | PCGamingWiki; three testers on cable and dongle, 2026-09-24 | Seen. The pad image dispatches section-`04` reads on it once a host has claimed the device. |
| `6012` | Ultimate 2 Wireless, DInput. Two different personalities carry it: the pad on a cable (145-byte descriptor, reports `01`/`02`/`81`, config channel) and the dongle (113-byte descriptor, reports `01`/`05`, sensors and rumble, no config channel). | SDL `usb_ids.h`; testers andromalandro and kropop, 2026-09-24 (dongle) | Dongle personality seen by two testers. Cable personality not seen yet. |
| `6013` | Ultimate 2 Wireless receiver personality, `PID_Ultimate2RR` in V2, bcdDevice 2.00 in the receiver image | V2, receiver image | Not seen by any tester yet. The testers' dongles presented `6012` (DInput, 113-byte descriptor, no config reports) or `310b` (XInput, three interfaces). |
| `3107` | Ultimate 2 Wireless dongle while idle, product string `IDLE`, 37-byte descriptor on page `0x008c` | Tester ChibiChoko, 2026-09-24; V2 names it `USB2_IDLE` | Seen. Nothing is sent to it. |
| `3105` | `PID_USB_Ultimate2` in V2, used only for file paths and key tables | V2 | Not seen. |
| `3019` | N64 Bluetooth Controller on a cable, `PID_N64BT` in V2 (update type 78). Interface 0: 155-byte descriptor, reports `01`, `21`, `22`, `02`, `81`; interface 1: keyboard. V2 gives it calibration only. | Tester ChibiChoko, 2026-09-24 | Seen. Identify only. |
| `3004`, `9028`, `3021` | `PID_N64`, `PID_N64RR` (receiver; V2 flashes a 32 KB data block into it through `ReadN64RRData`/`WriteN64RRData`), `PID_N64JoySticks` | V2 | Not seen. |
| `3208` | Shared bootloader | Field notes | **Never send traffic.** |
| `5750` | Older 8BitDo bootloader | Public USB ID tables (devicekb) | **Never send traffic.** Not known to be the 2C's bootloader. |

## What Ultimate Software V2 1.35 calls these ids

Read from the `VIDPID` static constructor in the managed assembly embedded in the V2 1.35 exe (2026-09-23). The names are 8BitDo's own. `QINGCHUN` is the internal name for the 2C line.

| PID | V2 constant | Where V2 uses it |
| --- | --- | --- |
| `310a` | `PID_QINGCHUN2` | Platform selector and firmware update page only. `SelectPlatform.hideall` returns true for it, which hides every config page. No `Advance` (config) class references it. |
| `301c` | `PID_QINGCHUN2RR` | The 2C receiver. Same `hideall` treatment. Update page only. |
| `301a` | `PID_UltimateBT2C` | A Bluetooth 2C id. Update page only, and it is in the `dinputBoot` DFU-boot broadcast list. Not seen on this hardware. Its 1.01 firmware image (update type 108) is encrypted end to end, so its report set is unknown. |
| `301b` | not in the table | The id the 2C returns in its identify reply. V2 never compares against it. |
| `310b` | `PID_Xinput` | Generic XInput id. |
| `3109` | `PID_IDLE` | The older idle receiver. |
| `3208` | none, compared as a literal with `Boot.BootPID` | Bootloader. **Never send traffic.** |
| `5750` | `PID_NGCDIY` | **Never send traffic.** |
| `6012`, `6013` | `PID_Ultimate2`, `PID_Ultimate2RR` | Ultimate 2 pad and receiver. `Ultimate2_4Advance2UI` configures these with the 1592-byte image. |
| `600f`, `6011` | `PID_UltimateBT2`, `PID_UltimateBT2RR` | Ultimate BT2 pad and receiver, `0xad0`-byte image. |
| `6009`, `600a`, `600d` | `PID_Pro3`, `PID_Pro3USB`, `PID_Pro3DOCK` | Pro 3, `0x92c`-byte image. |
| `600b`, `600c` | `PID_HitBox`, `PID_HitBoxRR` | HitBox, `0x92c`-byte image. |
| `2062`, `2085` | `PID_HitBox2`, `PID_HitBox2Adapter` | HitBox 2, `0xa68`-byte image, two profiles. |
| `6003`, `3010`, `6006` | `PID_Pro2`, `PID_Pro2_Wired`, `PID_Pro2_CY` | Pro 2 family, `0x674`-byte image. |
| `6007`, `3106` | `PID_UltimateBT`, `PID_UltimateBTRR` | Ultimate BT, `0x914`-byte image. |
| `3011`, `3012`, `3013` | `PID_Ultimate_PC`, `PID_Ultimate2_4`, `PID_Ultimate2_4RR` | Ultimate wired and 2.4G, 20-key map profiles. |
| `2066`, `207d` | `PID_Ultimate3CPLUS`, `PID_Ultimate3CPLUSAdapter` | Ultimate 3C Plus. Not examined. |

So the 2C is known to this build by name, and the build deliberately routes it to firmware only. That is the whole answer to "does V2 1.35 configure the 2C": no, by design of the platform selector, not by a missing device id.

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
