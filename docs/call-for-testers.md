# Call for testers

Post text for r/8bitdo (or r/linux_gaming). Update the link if the repo moves.

---

**Title:** Linux + 8BitDo Ultimate 2 Wireless owners: 10 minutes to help build an open config tool (read-only, nothing gets written to your pad)

I've been reverse-engineering how 8BitDo's Ultimate Software talks to its pads, with the goal of a Linux tool that can do what the Windows app does (dead zones, trigger ranges, L4/R4 binds, profiles). Everything so far is in the open here: https://github.com/ascendedent/8bitdo-Linux-Software

Where it stands: I own an Ultimate 2C, and it turns out the 2C has **no** host-side config channel at all. I pulled its firmware from 8BitDo's update server and disassembled it: the only commands it answers over USB are the firmware updater, identify, rumble, and a radio-address get/set. The L4/R4 binds are stored in a 26-byte flash record that only the on-pad button combo can change. The dongle doesn't relay anything to the pad either. So the 2C is a dead end for a config tool, by design.

The **Ultimate 2 Wireless** (the one with the charging dock, `2dc8:6012`) is different: Ultimate Software reads and writes a 1592-byte config image on it, and I've already recovered that image's layout (profiles, stick/trigger/vibration records, button maps, macros) from the app's binaries. What I don't have is a single real image from a real pad to check it against.

If you have an Ultimate 2 and a Linux box, this is what I'm asking:

1. `git clone https://github.com/ascendedent/8bitdo-Linux-Software`, install the one udev rule from the README.
2. Plug the pad in on a cable in DInput mode.
3. Run `python3 tools/inventory.py` (walks sysfs, sends nothing) and `python3 tools/read_config.py --pid 6012 --summary`.
4. Open an issue with the three output files.

What the read tool sends is exactly the config **read** the official app sends every time the pad connects. Every packet goes through an allowlist in code before it leaves; writes, commits, firmware commands, and the bootloader IDs are refused, and there are tests for that. It does not change anything on the pad. You can read the whole tool before you run it; it's ~250 lines of Python with no dependencies.

Privacy note: the image contains your three profile names and your settings, and the transcript contains the pad's USB descriptors. The USB serial is never printed. If you'd rather not share the raw files, the `--summary` output alone is still useful.

Bonus if you also run the Windows app (or Wine): a usbmon capture of changing one setting and saving would let me confirm the write side too. Totally optional.

Happy to answer questions about the firmware findings; the docs in the repo go into a lot of detail.
