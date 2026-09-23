# Safety

The controller stores its config in flash, and it shares a bootloader product ID with other 8BitDo devices. The cost of a bad write is a pad that needs the official app to recover, or a pad that needs a reflash.

## Never

- Send any transfer to PID `3208` or PID `5750`.
- Replay firmware-update traffic, even if it showed up in a capture next to config traffic.
- Invent a packet from the Pro 2 spec and send it. That spec is a hypothesis until a 2C capture matches it.
- Change more than one captured byte at a time, and only inside a field that a differential capture already identified.

## Always

- Dump the full config before the first write experiment, and again after every write that the controller accepted.
- Replay a captured write exactly, power-cycle, and check the setting three ways: Ultimate Software V2, the dongle with no app running, Bluetooth with no app running.
- Keep V2 working in Wine or a Windows VM. That is the recovery path for a bad config and for a firmware reflash.
- Strip the USB serial before sharing a capture.

## What this repo will not do yet

`tools/inventory.py` is read-only. It walks sysfs and prints descriptors. There is no write path until capture `00_baseline` exists and a read command has been copied from it.
