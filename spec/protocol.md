# Ultimate 2C config protocol

Status: **no capture yet.** Every section below is a slot. Do not fill one from the Pro 2 spec or from SDL. Fill it from a diff of two captures.

## Channel

| Question | Answer |
| --- | --- |
| Works over the 2.4 GHz dongle? | Unknown |
| Works over USB cable? | Unknown |
| Works over Bluetooth? | Unknown |
| Transport | Unknown. Candidates: feature report on a vendor usage page, interrupt OUT on a second interface, HID output report. |
| Interface / usage page | Unknown. First place to look is interface 1 of PID `310a`, which public dmesg shows as a keyboard+mouse HID function beside XInput. |
| Report ID | Unknown |
| Separate commit / save-to-flash command? | Unknown |
| Checksum | Unknown |
| Sequence counter | Unknown |

## Commands

| Name | Bytes | Seen in | Effect |
| --- | --- | --- | --- |
| Handshake / identify | | `00_baseline` | |
| Read config | | `00_baseline` | |
| Write setting | | `01` through `10` | |
| Commit | | if distinct from write | |
| Factory reset | | `11_reset` | |

## Settings

| Setting | ID or offset | Encoding | Evidence |
| --- | --- | --- | --- |
| L4 target button | | | `01` vs `02` vs `03` |
| L4 cleared | | | `03` |
| Left stick deadzone | | | `04` vs `05` |
| Right stick deadzone | | | `06` vs `04` |
| Vibration | | | `07` |
| Trigger range | | | `08` |
| Profile slot | | | `09` |
| Macro | | | `10` |

## Relation to other devices

| Device | Same framing? | Evidence |
| --- | --- | --- |
| Pro 2 / SN30 Pro+ (V1, 8bitdo-spec) | Unknown | See `docs/v1-framing.md` |
| Ultimate 2 Wireless | Unknown | |
| Pro 3 | Unknown | |
