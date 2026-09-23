# Capture log

Fill one row per file. Leave the payload notes blank until the diff is done.

Host: Fedora, kernel `7.2.0-359.vanilla.fc44.x86_64` as of 2026-09-22. Controller was not attached when the repo was created.

| File | Date | Connection | VID:PID | Bus / address | V2 setting before | V2 setting after | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 00_baseline | | | | | | | |
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
