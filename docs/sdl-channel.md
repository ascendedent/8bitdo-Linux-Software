# What SDL already decoded

Source: [`SDL_hidapi_8bitdo.c`](https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_8bitdo.c) and [`usb_ids.h`](https://github.com/libsdl-org/SDL/blob/main/src/joystick/usb_ids.h) on `main`, read 2026-09-22.

This is the input channel on older and sibling controllers. It is recorded here so a capture of the 2C can be told apart from it. None of these commands are known to read or write deadzones, curves, macros, or profiles.

## Devices the driver actually claims

`USB_VENDOR_8BITDO` (`2dc8`) and one of:

| PID | SDL name | Note in `usb_ids.h` |
| --- | --- | --- |
| `6000` / `6100` | SF30 Pro | B + Start |
| `6001` / `6101` | SN30 Pro | B + Start |
| `6003` / `6006` | Pro 2 | mode switch to D |
| `6009` | Pro 3 | mode switch to D |
| `6012` | Ultimate 2 Wireless | mode switch to BT |
| `202f` | Ultimate 3 | mode switch to BT |

`310a` is absent. A capture that only shows Xbox-style interrupt IN traffic is the XInput pad, not this driver.

## Feature reports the driver reads

`ReadFeatureReport` is `GET_REPORT` of a feature report.

| Report ID | Who | What SDL uses it for |
| --- | --- | --- |
| `0x06` | Every supported device except Ultimate 2 Wireless and Ultimate 3 | Enable the enhanced SDL input report. On success, byte 13 equal to `0xAA` means the firmware sends a sensor timestamp. Bytes 5 through 10 are a Bluetooth MAC, stored as the serial, when byte 10 is non-zero and the report is at least 12 bytes. |
| `0x30` | Ultimate 3 only | Capability bits and a 6-byte serial at bytes 11 through 16. Byte 3 bit `0x02` means trigger rumble. A zero byte 3 disables rumble. A zero byte 4 disables sensors. |

Ultimate 2 Wireless (`6012`) takes neither report. SDL decides sensor and rumble support by whether an input packet is at least 34 bytes (v1.03 firmware) or 12 bytes (v1.02).

## Output report the driver writes

Rumble is a 5-byte output report, not a feature report:

```
05  LL  HH  TL  TR
```

`LL` and `HH` are the low and high frequency motors, high byte of the SDL 16-bit magnitude. `TL` and `TR` are trigger motors, and SDL only fills them on the Ultimate 3.

This is live rumble. The vibration strength saved by Ultimate Software is a different command, still undocumented.

## Input report IDs

| ID | Meaning in this driver |
| --- | --- |
| `0x03` | Firmware without enhanced mode |
| `0x04` | Enhanced mode, USB |
| `0x01` | Enhanced mode, Bluetooth |
| 9-byte packet, no recognized ID | Old SF30 / SN30 Pro USB firmware |

L4 and R4, on the controllers this driver supports, are bits 0 and 1 of byte 10 of the enhanced report. That layout is not evidence for the 2C's XInput interface.

## What to look for in a 2C capture

Traffic that matches report ID `0x05` (5 bytes) or feature report `0x06` / `0x30` is the input-side channel, or a cousin of it. Set it aside. The config channel is whatever is left once the controller is detected and a setting changes: expect a report ID or command byte, a length, a setting ID, a value, and possibly a checksum or sequence counter.
