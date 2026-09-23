# Captures

One setting change per file. Numbers match the log in `docs/capture-log.md`.

| File | Change in Ultimate Software V2 | What it isolates |
| --- | --- | --- |
| `00_baseline` | Connect and close, no edits | Handshake, config read |
| `01_L4_A` | L4 bound to A | Button remap command |
| `02_L4_B` | L4 bound to B | Button code byte |
| `03_L4_clear` | Clear L4 | Unbind value |
| `04_dz_10` | Left stick deadzone to 10 | Stick setting ID |
| `05_dz_20` | Left stick deadzone to 20 | Value encoding |
| `06_rdz_10` | Right stick deadzone to 10 | Per-stick addressing |
| `07_vib_50` | Vibration to 50% | Rumble setting |
| `08_trig` | Trigger range change | Trigger setting |
| `09_profile2` | Same edit saved to profile 2 | Profile slot field |
| `10_macro` | Record a short macro | Multi-packet writes |
| `11_reset` | Reset to defaults | Factory reset command |
| `03_reads` | Not V2. `tools/read_config.py` probes, 2026-09-23 | Which read commands the 2C answers. See `docs/capture-log.md`. |

Store the pcapng here. `exports/` is for the `tshark` text dumps used when diffing.

Before a capture is committed or shared, confirm the USB serial string is gone. One public dmesg of this controller showed serial `0000000000`, which is still a descriptor field to strip.

pcapng files are gitignored. A redacted export can be committed once the framing is known.
