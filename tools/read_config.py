#!/usr/bin/env python3
"""Read-only probes of the 2C's vendor interface. Authorized 2026-09-23.

Sends, in order: the two captured identify commands, with --probes the
three reply-only probes (00 31 01, 66 aa 63, class 05 command 0008), and
readCRC (class 05, command c3). The Ultimate 2 chunked read (request 2, total 0x638) and
the custom_info read (request 0x0c, total 0x230) are behind --unanswered:
both got silence on 2026-09-23, and the 1.09 image has no handler for
either (docs/firmware.md), so they are off by default. Every packet is
checked against an allowlist before it goes out, so no write (request 1),
commit (request 6), or initDevice1 can be sent from here. Only the pad
named by --pid is opened, on its vendor-page interface, and never a
bootloader or the idle dongle. Every byte in and out goes to the
transcript.

On an Ultimate 2 (--pid 6012) the class 05 commands are not sent; the
tool sends only the chunked config read V2 itself issues on connect
(request 2, total 0x638, checksummed), saves the 1592-byte image, and
with --summary decodes it.
"""

from __future__ import annotations

import argparse
import os
import select
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import packets  # noqa: E402
import identify  # noqa: E402
from identify import IDENTIFY_ONLY_PIDS, PAD_PIDS, choose_pid, config_family, find_vendor_interface  # noqa: E402

# Prefixes a packet must start with to be sent. Anything else is refused.
ALLOWED_PREFIXES = (
    bytes.fromhex("8105002101"),  # getcurrentpid, captured
    bytes.fromhex("8105c100" + "00" * 60),  # initDevice, captured, all zeros after
    bytes.fromhex("8105c30000000c000000"),  # readCRC
    # The three reply-only probes, exact 64-byte packets, so a different byte 1
    # on 66 aa 63 (which the pad would store as a mode flag) is refused.
    packets.pad_report(packets.PROBE_IS_WIRED),
    packets.pad_report(packets.PROBE_GET_RF_ADDRESS),
    packets.pad_report(packets.PROBE_GET_PID),
)


# Set only by --switch-to-dinput --yes; the allowlist refuses the packet otherwise.
SWITCH_ARMED = False


def allowed(packet: bytes) -> bool:
    if len(packet) != 64 or packet[0] != 0x81:
        return False
    if packet == packets.pad_report(packets.SWITCH_TO_DINPUT):
        return SWITCH_ARMED
    for prefix in ALLOWED_PREFIXES:
        if packet.startswith(prefix):
            return True
    if packet[2] == 0x04:
        body = packet[3:]
        if body[0] == packets.CUSTOM_INFO_REQUEST and body[1] == packets.STACK_FILL:
            return True  # custom_info read, zero-flag form
        if int.from_bytes(body[0:2], "little") == packets.PRO2_READ:
            return True  # chunked read, request 2, size-byte frame
    if packet[1] == 0x04 and int.from_bytes(packet[2:4], "little") == packets.PRO2_READ:
        return True  # chunked read, request 2, no-size-byte frame (Ultimate 2 and the other CRC products)
    return False


class Session:
    def __init__(self, node: Path, log: Path, timeout_ms: int, *, fd: int | None = None) -> None:
        if fd is None:
            try:
                fd = os.open(node, os.O_RDWR)
            except PermissionError as exc:
                raise SystemExit(
                    f"cannot open {node}: {exc.strerror}. Install udev/71-8bitdo.rules "
                    "(see the README), replug the pad, and run again. Running as root also works "
                    "but is not needed."
                ) from exc
        self.fd = fd
        self.log = open(log, "a")
        self.timeout = timeout_ms / 1000
        self.note(f"open {node}")

    def note(self, text: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {text}"
        print(line)
        self.log.write(line + "\n")
        self.log.flush()

    def drain(self) -> None:
        while True:
            ready, _, _ = select.select([self.fd], [], [], 0)
            if not ready:
                return
            data = os.read(self.fd, 64)
            self.note(f"in  (pending) {len(data):3d} {data.hex()}")

    def exchange(self, packet: bytes, label: str) -> bytes:
        if not allowed(packet):
            raise SystemExit(f"refusing to send {packet.hex()}")
        self.drain()
        wrote = os.write(self.fd, packet)
        self.note(f"out {label:14s} {wrote:3d} {packet.rstrip(b'\\0').hex() or '81'}")
        deadline = time.monotonic() + self.timeout
        skipped = 0
        while True:
            left = deadline - time.monotonic()
            ready, _, _ = select.select([self.fd], [], [], max(left, 0))
            if not ready:
                if skipped:
                    self.note(f"    skipped {skipped} input report(s) that were not a reply")
                self.note(f"in  {label:14s} timeout")
                return b""
            data = os.read(self.fd, 64)
            # A reply to report 81 is input report 02. A pad in a gamepad
            # personality streams its own input reports (id 01 on the
            # Ultimate 2) on the same node; those are not replies.
            if data and data[0] != 0x02:
                skipped += 1
                if skipped == 1:
                    self.note(f"in  {label:14s} {len(data):3d} {data.hex()}  (input report id {data[0]:#04x}, not a reply; more like it are counted)")
                continue
            if skipped:
                self.note(f"    skipped {skipped} input report(s) that were not a reply")
            self.note(f"in  {label:14s} {len(data):3d} {data.hex()}")
            return data

    def close(self) -> None:
        os.close(self.fd)
        self.log.close()


def chunked_read(sess: Session, label: str, total: int, build, parse, out: Path, summary: bool = False) -> None:
    image = bytearray(total)
    offset = 0
    stalls = 0
    tries = 0
    # Enough sends for every chunk plus the stall allowance. The Ultimate 2
    # image needs 36 chunks of 45 bytes, so the custom_info cap of 30
    # would stop it short.
    max_tries = (total + packets.CUSTOM_INFO_CHUNK - 1) // packets.CUSTOM_INFO_CHUNK + 30
    while offset < total and tries < max_tries:
        tries += 1
        reply = sess.exchange(build(offset), f"{label}@{offset:#x}")
        try:
            chunk = parse(reply) if reply else b""
            reason = "" if chunk else ("timeout" if not reply else "empty chunk")
        except ValueError as exc:
            chunk, reason = b"", str(exc)
        if not chunk:
            stalls += 1
            sess.note(f"    {label}: no progress at {offset:#x} ({reason})")
            if stalls >= 3:
                break
            continue
        stalls = 0
        end = min(offset + len(chunk), total)
        image[offset:end] = chunk[: end - offset]
        offset += len(chunk)
    if offset >= total:
        out.write_bytes(bytes(image))
        sess.note(f"    {label}: complete, {total} bytes -> {out}")
        if summary and total == packets.ULTIMATE2_TOTAL:
            from u2_summary import summarize

            for line in summarize(bytes(image)):
                sess.note(f"    {line}")
    elif offset:
        out.with_suffix(".partial.bin").write_bytes(bytes(image[:offset]))
        sess.note(f"    {label}: stopped at {offset:#x} of {total:#x}, partial saved")
    else:
        sess.note(f"    {label}: nothing readable")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--pid",
        default="auto",
        choices=["auto"] + [f"{p:04x}" for p in PAD_PIDS],
        help="product id to open (default auto: the one pad attached). On the 2C the class 05 "
        "commands are sent; on any other pad only the chunked config read V2 sends on connect.",
    )
    ap.add_argument(
        "--switch-to-dinput",
        action="store_true",
        help="send V2's switch-to-DInput command (81 05 00 51 00) instead of reading. The pad reboots "
        "into its DInput personality; nothing else is sent. Requires --yes.",
    )
    ap.add_argument("--yes", action="store_true", help="confirm --switch-to-dinput")
    ap.add_argument("--path", help="sysfs device name from tools/inventory.py, when two match")
    ap.add_argument(
        "--node",
        help="open this hidraw node directly instead of finding it through sysfs. "
        "The bootloader and idle-dongle refusals do not apply; for tests and for a device sysfs cannot describe.",
    )
    ap.add_argument("--log", default=None, help="transcript path (default captures/exports/<pid>_<time>.txt)")
    ap.add_argument("--timeout-ms", type=int, default=800)
    ap.add_argument("--summary", action="store_true", help="after a complete Ultimate 2 read, print the decoded fields")
    ap.add_argument("--skip", nargs="*", default=[], choices=["identify", "u2", "custom", "crc"])
    ap.add_argument(
        "--probes",
        action="store_true",
        help="send the three reply-only probes from docs/firmware.md "
        "(00 31 01, 66 aa 63 with byte 1 zero, class 05 command 0008)",
    )
    ap.add_argument(
        "--unanswered",
        action="store_true",
        help="also send the Ultimate 2 chunked read and the custom_info read, "
        "which firmware 1.09 does not answer",
    )
    args = ap.parse_args(argv)
    pid = choose_pid(None if args.pid == "auto" else int(args.pid, 16), args.path)
    is_2c = pid == 0x310A
    if pid in IDENTIFY_ONLY_PIDS and not args.unanswered:
        # No chunked read exists for these in V2: the 2C ignores both
        # (docs/firmware.md) and the N64 Bluetooth pad only gets calibration.
        args.skip = list(args.skip) + ["u2", "custom"]
    if not is_2c:
        # Only the 2C gets readCRC and the probes. Every pad gets the class 05
        # identify, which V2 sends to each one on connect; pads with a config
        # channel get the read V2 sends them, framed for their family.
        args.skip = list(args.skip) + ["crc", "custom"]
        args.probes = False
    if args.log is None:
        # Under the repo's captures/exports/ whatever the working directory is.
        exports = Path(__file__).resolve().parent.parent / "captures" / "exports"
        args.log = str(exports / f"{args.pid}_{time.strftime('%Y%m%d_%H%M%S')}.txt")
    node = Path(args.node) if args.node else find_vendor_interface(pid, args.path)
    log = Path(args.log)
    log.parent.mkdir(parents=True, exist_ok=True)
    sess = Session(node, log, args.timeout_ms)
    sess.note(f"pad {pid:04x}: {PAD_PIDS.get(pid, '')}")
    family = config_family(pid, identify.LAST_PRODUCT.get(str(node), ""))
    if family is not None and family != pid:
        sess.note(f"    config protocol: {family:04x} (from the product string)")
    if family is None and pid not in IDENTIFY_ONLY_PIDS and "u2" not in args.skip:
        sess.note(f"    no config protocol is known for {pid:04x}; sending identify only")
        args.skip = list(args.skip) + ["u2"]
    ids = identify.LAST_SELECTION.get(str(node))
    if ids is not None and not {0x81, 0x02} <= ids:
        sess.note(
            f"    warning: this interface declares report ids {sorted(f'{i:#04x}' for i in ids)}, "
            "not 81 and 02. It has no config channel; on an Ultimate 2 through its dongle in DInput "
            "mode that is expected (docs/firmware.md). Use the cable, or the dongle in XInput mode."
        )
    if args.switch_to_dinput:
        if not args.yes:
            raise SystemExit("--switch-to-dinput reboots the pad into DInput mode; add --yes to send it")
        global SWITCH_ARMED
        SWITCH_ARMED = True
        try:
            sess.exchange(packets.pad_report(packets.SWITCH_TO_DINPUT), "switch_dinput")
            sess.note("    sent. The pad reboots; run tools/inventory.py in a few seconds to see its new id.")
        finally:
            SWITCH_ARMED = False
            sess.close()
        return 0
    try:
        if "identify" not in args.skip:
            for payload in packets.IDENTIFY_COMMANDS:
                sess.exchange(packets.pad_report(payload), "identify")
        if args.probes:
            for label, payload in packets.REPLY_PROBES:
                sess.exchange(packets.pad_report(payload), label)
        if "u2" not in args.skip:
            chunked_read(
                sess, "u2read", packets.ULTIMATE2_TOTAL,
                lambda off: packets.pad_report(
                    packets.pro2_read_chunk(off, packets.ULTIMATE2_TOTAL, **packets.frame_for(family or pid))
                ),
                lambda reply: packets.parse_pro2_read_reply(reply, checksum=(family or pid) in packets.CRC_PIDS),
                log.with_name(log.stem + "_u2.bin"), args.summary,
            )
        if "custom" not in args.skip:
            chunked_read(
                sess, "custom", packets.CUSTOM_INFO_TOTAL,
                lambda off: packets.pad_report(packets.custom_info_chunk(off)),
                packets.parse_custom_info_reply, log.with_name(log.stem + "_custom.bin"),
            )
        if "crc" not in args.skip:
            sess.exchange(packets.read_crc(), "readCRC")
    finally:
        sess.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
