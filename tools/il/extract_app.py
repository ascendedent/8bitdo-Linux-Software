"""Copy the managed app assembly out of the single-file V2 1.35 exe.

The bundle holds the app PE at file offset 0x15d000. Its .text section
starts at raw 0x200 for RVA 0x2000, so file = 0x15d000 + 0x200 + (rva -
0x2000). The BSJB metadata root is at file 0x37a030. Nothing here talks
to a device.
"""
import sys

EXE = "vendor/8BitDo_Ultimate_Software_V2_Windows_V1.35/8BitDo Ultimate Software V2.exe"
BASE = 0x15D000
SIZE = 0x5F42400 + 0x200

out = sys.argv[1] if len(sys.argv) > 1 else "vendor/v2_app.dll"
with open(EXE, "rb") as f:
    f.seek(BASE)
    data = f.read(SIZE)
assert data[:2] == b"MZ", "no MZ at the bundle offset"
with open(out, "wb") as f:
    f.write(data)
print(out, len(data))
