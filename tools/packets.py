"""Packet bytes taken from 8BitDoAdvance.dll. Nothing here opens a device.

The identify commands were captured on the wire and then found in
getcurrentpid and initDevice. The custom_info read is from readUSBAdapter.
That read was not captured and this module does not send it.
"""

from __future__ import annotations

IDENTIFY_GET_PID = bytes.fromhex("8105002101")
IDENTIFY_INIT = bytes.fromhex("8105c100")
IDENTIFY_COMMANDS = (IDENTIFY_GET_PID, IDENTIFY_INIT)

# Reply-only probes, each checked against the 1.09 image in docs/firmware.md.
# 00 31 01 builds a reply whose payload byte is 0x32 and does nothing else.
# 66 aa 63 replies with the 5-byte radio address, waits 100 ms, then stores
# request byte 1 into a RAM mode flag; byte 1 is 0 here so the flag keeps its
# boot value. Class 05 command 0008 (get_pid) fills a reply with 0x301b.
PROBE_IS_WIRED = bytes.fromhex("8105003101")
PROBE_GET_RF_ADDRESS = bytes.fromhex("810066aa63")
PROBE_GET_PID = bytes.fromhex("81050800")
REPLY_PROBES = (
    ("is_wired", PROBE_IS_WIRED),
    ("rf_address", PROBE_GET_RF_ADDRESS),
    ("get_pid", PROBE_GET_PID),
)

CUSTOM_INFO_TOTAL = 0x230
CUSTOM_INFO_CHUNK = 0x2D
CUSTOM_INFO_REQUEST = 0x0C
STACK_FILL = 0xCC
ULTIMATE2_TOTAL = 0x638
PRO2_READ = 0x0002
PRO2_WRITE = 0x0001
PRO2_COMMIT = 0x0006
PRO2_COMMIT_ARG = 0x0123

# Product IDs whose chunk data is covered by CRC-16/MODBUS.
# 310a and 301c are not in this set.
CRC_PIDS = frozenset(
    {0x6006, 0x3010, 0x3011, 0x6007, 0x3109, 0x6009, 0x6012, 0x600F, 0x600B, 0x2062}
)


def crc16_modbus(data: bytes) -> int:
    """CRC used when the open product is in CRC_PIDS. Init 0xFFFF, poly 0xA001."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def pad_report(payload: bytes) -> bytes:
    """64-byte interrupt transfer: report id plus 63 bytes."""
    if not payload or payload[0] != 0x81:
        raise ValueError("report id is 0x81")
    if len(payload) > 64:
        raise ValueError(f"payload is {len(payload)} bytes")
    return payload + bytes(64 - len(payload))


def _wrap_section(body: bytes) -> bytes:
    """Report 81, size, section 04, then the body. Same wrapper for both reads."""
    size = len(body) + 1
    packet = bytes([0x81, size, 0x04]) + body
    if len(packet) > 64:
        raise ValueError(f"packet is {len(packet)} bytes")
    return packet


def _chunk_length(offset: int, total: int) -> int:
    if offset < 0 or offset > total:
        raise ValueError(f"offset {offset} outside 0..{total}")
    return min(CUSTOM_INFO_CHUNK, total - offset)


def class05(tail: bytes) -> bytes:
    """Short command from the firmware writer. Class byte 05, then tail, zero padded."""
    return pad_report(bytes([0x81, 0x05]) + tail)


def init_device() -> bytes:
    """initDevice. Captured on the wire."""
    return class05(bytes.fromhex("c100"))


def init_device1() -> bytes:
    """initDevice1. Command 0x00C1, following word 0x8000. Not captured."""
    return class05(bytes.fromhex("c1000080"))


def read_crc() -> bytes:
    """readCRC. Command 0x00C3, length dword 0x0C. Not captured."""
    return class05(bytes.fromhex("c30000000c000000"))


def custom_info_chunk(offset: int) -> bytes:
    """One outbound custom_info read, the zero-flag path in readUSBAdapter.

    The DLL fills the stack frame with 0xCC, then stores the request byte,
    the chunk length, the total size, and the offset. Unset header bytes
    stay 0xCC. The data pointer is null, so the chunk body stays 0xCC too.
    """
    length = _chunk_length(offset, CUSTOM_INFO_TOTAL)
    body = bytearray([STACK_FILL] * 16)
    body[0] = CUSTOM_INFO_REQUEST
    body[8] = length
    body[0x0A : 0x0C] = CUSTOM_INFO_TOTAL.to_bytes(2, "little")
    body[0x0C : 0x0E] = offset.to_bytes(2, "little")
    body += bytes([STACK_FILL] * length)
    return _wrap_section(body)


def pro2_read_chunk(offset: int, total: int, *, checksum: bool = False) -> bytes:
    """Chunked read used when the custom_info flag is set, and by readUltimate2.

    Sixteen-byte body, then the chunk. Request uint16 is 2. The checksum is
    the high half of the length dword and stays 0 unless checksum is set.
    310a is not a CRC product. 6012, the Ultimate 2, is.
    """
    length = _chunk_length(offset, total)
    data = bytes([STACK_FILL] * length)
    body = bytearray(16 + length)
    body[:] = bytes([STACK_FILL] * (16 + length))
    body[0:2] = PRO2_READ.to_bytes(2, "little")
    body[2:4] = (0).to_bytes(2, "little")
    crc = crc16_modbus(data) if checksum else 0
    body[4:8] = (length | (crc << 16)).to_bytes(4, "little")
    body[8:12] = total.to_bytes(4, "little")
    body[12:16] = offset.to_bytes(4, "little")
    body[16:] = data
    return _wrap_section(body)


def pro2_write_chunk(
    offset: int,
    total: int,
    data: bytes,
    *,
    nbytes: int | None = None,
    checksum: bool = False,
) -> bytes:
    """One write chunk. Request uint16 is 1. data is the config slice for this offset.

    writeUltimate2 passes request 1, total 0x638, and the bytes at that offset
    in the 1592-byte image. 6012 checksums the chunk. 310a is not a CRC product.
    """
    natural = _chunk_length(offset, total)
    length = natural if nbytes is None else nbytes
    if length < 0 or length > natural:
        raise ValueError(f"length {length} outside 0..{natural}")
    if len(data) < length:
        raise ValueError(f"need {length} data bytes, got {len(data)}")
    chunk = data[:length]
    body = bytearray([STACK_FILL] * (16 + length))
    body[0:2] = PRO2_WRITE.to_bytes(2, "little")
    body[2:4] = (0).to_bytes(2, "little")
    crc = crc16_modbus(chunk) if checksum else 0
    body[4:8] = (length | (crc << 16)).to_bytes(4, "little")
    body[8:12] = total.to_bytes(4, "little")
    body[12:16] = offset.to_bytes(4, "little")
    body[16:] = chunk
    return _wrap_section(body)


def pro2_commit() -> bytes:
    """Command after the write chunks. Request 6, argument word 0x0123. No data."""
    body = bytearray(16)
    body[0:2] = PRO2_COMMIT.to_bytes(2, "little")
    body[2:4] = PRO2_COMMIT_ARG.to_bytes(2, "little")
    return _wrap_section(bytes(body))


def parse_custom_info_reply(reply: bytes) -> bytes:
    """Return the chunk from a custom_info reply, or raise ValueError.

    The DLL reads 64 bytes and accepts the buffer only when byte 0 is 0x02,
    byte 1 is 0x04, byte 2 is 0x04, and the little-endian dword at offset 6
    is 0x0c. Byte 10 is the chunk length. The chunk starts at offset 0x12.
    A length that runs past the 64-byte read is refused here. The DLL would
    copy that many bytes off the end of its stack buffer.
    """
    if len(reply) != 64:
        raise ValueError(f"reply is {len(reply)} bytes, the read is 64")
    if reply[0] != 0x02 or reply[1] != 0x04 or reply[2] != 0x04:
        raise ValueError(
            f"reply starts {reply[0]:02x} {reply[1]:02x} {reply[2]:02x}"
        )
    marker = int.from_bytes(reply[6:10], "little")
    if marker != CUSTOM_INFO_REQUEST:
        raise ValueError(f"dword at offset 6 is {marker:#x}")
    length = reply[10]
    end = 0x12 + length
    if end > len(reply):
        raise ValueError(f"chunk length {length} runs past the 64-byte read")
    return bytes(reply[0x12:end])


def parse_pro2_read_reply(reply: bytes) -> bytes:
    """Chunk from the flag-set reply parser.

    Byte 0 is 0x02, byte 1 is 0x04, the uint16 at offset 2 is 4, and the
    uint16 at offset 4 is the request type 2. The chunk length is the
    dword at offset 6. The chunk starts at offset 0x12.
    """
    if len(reply) != 64:
        raise ValueError(f"reply is {len(reply)} bytes, the read is 64")
    if reply[0] != 0x02 or reply[1] != 0x04:
        raise ValueError(f"reply starts {reply[0]:02x} {reply[1]:02x}")
    echoed = int.from_bytes(reply[2:4], "little")
    request = int.from_bytes(reply[4:6], "little")
    if echoed != 0x0004 or request != PRO2_READ:
        raise ValueError(f"reply words {echoed:#x} {request:#x}")
    length = int.from_bytes(reply[6:10], "little")
    end = 0x12 + length
    if length > CUSTOM_INFO_CHUNK or end > len(reply):
        raise ValueError(f"chunk length {length} does not fit")
    return bytes(reply[0x12:end])


def custom_info_requests() -> list[bytes]:
    """The outbound chunks for one full read, offsets 0, 45, 90, ... 

    The last chunk is the 20 bytes left after 12 full chunks of 45.
    """
    packets = []
    offset = 0
    while offset < CUSTOM_INFO_TOTAL:
        packets.append(custom_info_chunk(offset))
        offset += min(CUSTOM_INFO_CHUNK, CUSTOM_INFO_TOTAL - offset)
    return packets


def assemble_custom_info(replies: list[bytes]) -> bytes:
    """Join reply chunks the way readUSBAdapter does.

    Offset starts at 0. Each reply is one try. A reply the parser rejects,
    or a chunk of length 0, does not move the offset. Any other chunk is
    written at the current offset and the offset advances by its length.
    The read stops when the offset reaches 560 bytes. The 30th failed or
    partial try is the last one. The returned image is only the first 560
    bytes, which is what the DLL copies out.
    """
    image = bytearray(CUSTOM_INFO_TOTAL)
    offset = 0
    for tries, reply in enumerate(replies, start=1):
        if tries > 30:
            break
        try:
            chunk = parse_custom_info_reply(reply)
        except ValueError:
            chunk = b""
        if not chunk:
            continue
        end = offset + len(chunk)
        if offset < CUSTOM_INFO_TOTAL:
            write_end = min(end, CUSTOM_INFO_TOTAL)
            image[offset:write_end] = chunk[: write_end - offset]
        offset = end
        if offset >= CUSTOM_INFO_TOTAL:
            return bytes(image)
    raise ValueError(
        f"custom_info stopped at offset {offset} after {min(len(replies), 30)} tries"
    )
