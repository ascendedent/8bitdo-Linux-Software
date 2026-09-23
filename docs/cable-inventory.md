# USB cable inventory

2026-09-23. Controller on a USB-C cable, dongle unplugged. Mode switch was on Bluetooth so the pad would not join the receiver. Read from sysfs and `lsusb -v` only. No reports were sent.

`python3 tools/inventory.py` found one device.

| Field | Value |
| --- | --- |
| Name | 8BitDo Ultimate 2C Wireless Controller |
| VID:PID | `2dc8:310a` |
| bcdDevice | `1.14` |
| Serial string | ten ASCII zeros. Present, not unique. |
| Speed | Full speed, 12 Mbps |
| Power | Bus powered, 500 mA |
| Sysfs | `3-5.1` on bus 3, behind a hub. Device address was 19. Both change on replug. |
| Interfaces | 3 |

The vendor interface was silent during a 0.4 s read. Nothing comes out of it until something asks.

## Interfaces

| # | Class | Driver | Endpoints | Role |
| --- | --- | --- | --- | --- |
| 0 | `ff/5d/01` | `xpad` | EP 4 IN, 32 bytes, interval 1. EP 5 OUT, 32 bytes, interval 1. | XInput pad. No hidraw node. |
| 1 | `03/01/01` HID boot keyboard | `usbhid` + `hid-generic` | EP 2 IN, 16 bytes, interval 8. No OUT endpoint. | Keyboard, consumer control, and a small mouse collection. hidraw (was `hidraw18`). |
| 2 | `03/00/00` HID | `usbhid` + `hid-generic` | EP 3 IN, 64 bytes, interval 1. EP 6 OUT, 64 bytes, interval 1. | Vendor page `0xFF7A`. hidraw (was `hidraw19`). This is the config-channel candidate. |

The current user already has `rw` on both hidraw nodes through the seat ACL. The udev rule is not required for this login.

## Interface 1 descriptor

166 bytes. Standard pages only: generic desktop `0x0001`, keyboard `0x0007`, LED `0x0008`, button `0x0009`, consumer `0x000C`.

| Report ID | Direction | Contents |
| --- | --- | --- |
| `0x01` | Input, plus a 1-byte LED output | Boot keyboard: 8 modifier bits, reserved byte, 6 key bytes |
| `0x02` | Input | Consumer control, one 16-bit usage |
| `0x03` | Input | Pointer: 3 buttons, 5 bits padding, X and Y as 16-bit, wheel, and one consumer usage (AC Pan) |

No vendor page here. This is the keyboard-and-mouse interface from the public dmesg, and it is not the config channel.

## Interface 2 descriptor

33 bytes. Hex:

```
06 7a ff 09 01 a1 01
85 02 09 02 a1 00 09 03 15 00 25 ff 75 08 95 3f 81 02
85 81 09 05 91 02
c0 c0
```

| Report ID | Direction | Size | Usage |
| --- | --- | --- | --- |
| `0x02` | Input | 63 bytes | page `0xFF7A` usage `0x03`, inside a logical collection of usage `0x02` |
| `0x81` | Output | 63 bytes | page `0xFF7A` usage `0x05` |

Application collection is usage page `0xFF7A`, usage `0x01`.

A full transfer is 64 bytes: the report ID plus 63 bytes. That matches both interrupt endpoints.

## What this says about the Pro 2 hypothesis

The Pro 2 config writeup starts every host request with `0x81` and shows device replies starting with `0x02`, in chunks that fill a 64-byte buffer (3 byte header + 16 byte request + up to 45 bytes of data). This controller's vendor interface is an output report `0x81` of 63 bytes and an input report `0x02` of 63 bytes.

The report IDs line up. The command bytes, checksum, and config layout do not, until a capture shows them. Do not send a Pro 2 read to this pad on the strength of the descriptor alone.

## Wireshark, for the next session

Re-run `tools/inventory.py` after every replug. Last time the capture interface was `usbmon3` and the display filter was `usb.device_address == 19`.
