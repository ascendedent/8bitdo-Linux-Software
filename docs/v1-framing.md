# V1 framing, as a hypothesis for the 2C

The Pro 2 and SN30 Pro+ config protocol is documented by [TheJayMann/8bitdo-spec](https://github.com/TheJayMann/8bitdo-spec). Those are Ultimate Software V1 devices. The 2C is on the V2 app's device list. Treat the layout below as the first pattern to test against a capture, not as the 2C protocol.

Summary of the Pro 2 writeup, paraphrased. Offsets and checksums need a capture before anyone sends them.

## Packet shape

A request is a 3-byte header, a 16-byte request, and up to 45 bytes of data.

Header:

| Offset | Pro 2 value | Role |
| --- | --- | --- |
| 0 | `0x81` | Report number |
| 1 | packet size, excluding the first byte | Length |
| 2 | `0x04` when the payload is config data | Section |

Request body, little endian:

| Field | Values called out for the Pro 2 |
| --- | --- |
| Request type, 2 bytes | `1, 0` write config. `2, 0` read config. `6, 21` finish the write. `7, 0` and `7, 1` observed, not required. |
| Data length, 2 bytes | Bytes in this chunk. Config reads come back in 45-byte chunks. |
| Checksum, 2 bytes | CRC-16/MODBUS of the data for PIDs `3010`, `3011`, `3109`, `6006`, `6007`. Other Pro 2-protocol devices send `0`. `FFFF` when there is no data, on the CRC variants. |
| Total size, 4 bytes | Full config blob length |
| Offset, 4 bytes | Offset of this chunk |

The Pro 2 config blob is a single image (profiles, button maps, stick and trigger curves, macros) with padding, not one USB transaction per setting. A V2 capture that instead shows a short packet per slider would mean the 2C does not share this framing.

## How a capture confirms or kills this hypothesis

On the baseline capture, after the app has identified the controller:

- Report ID `0x81` and a following `0x04` section byte means the framing survived into V2.
- A read loop with request type `02 00`, a stable total-size field, and a rising offset means the blob model survived too.
- A checksum that is `0000` on every read is the non-CRC Pro 2 variant. A checksum that changes with the payload is the CRC-16/MODBUS variant, which `reveng` can check.
- None of the above, on a vendor usage page or a feature report, means V2 grew a new framing and the Pro 2 map should not be used even as a template for writes.

Do not send a Pro 2 read or write to the 2C until a capture shows this header. The safety rule is exact captured bytes only.
