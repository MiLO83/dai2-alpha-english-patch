#!/usr/bin/env python3
"""List host-to-local GS image uploads from an uncompressed PCSX2 GS dump."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


class GifParser:
    def __init__(self, path: int, report):
        self.path = path
        self.report = report
        self.buf = bytearray()
        self.tag = None

    def feed(self, data: bytes, event: int) -> None:
        self.buf.extend(data)
        while True:
            if self.tag is None:
                if len(self.buf) < 16:
                    return
                lo, hi = struct.unpack_from("<QQ", self.buf)
                del self.buf[:16]
                nloop = lo & 0x7FFF
                flg = (lo >> 58) & 3
                nreg = (lo >> 60) & 0xF or 16
                regs = [(hi >> (4 * i)) & 0xF for i in range(nreg)]
                units = nloop if flg in (2, 3) else nloop * nreg
                self.tag = [flg, regs, units, 0, bytearray(), event]
            flg, regs, units, pos, image, start_event = self.tag
            if flg in (2, 3):
                need = units * 16 - len(image)
                take = min(need, len(self.buf))
                image.extend(self.buf[:take])
                del self.buf[:take]
                if len(image) < units * 16:
                    return
                self.report.image(self.path, start_event, bytes(image))
                self.tag = None
                continue
            unit_size = 16 if flg == 0 else 8
            if len(self.buf) < unit_size:
                return
            unit = bytes(self.buf[:unit_size])
            del self.buf[:unit_size]
            reg = regs[pos % len(regs)]
            if flg == 0 and reg == 0xE:
                value, address = struct.unpack_from("<QQ", unit)
                self.report.register(address & 0xFF, value, start_event)
            pos += 1
            self.tag[3] = pos
            if pos == units:
                self.tag = None


class Reporter:
    def __init__(self):
        self.regs = {}
        self.register_events = []
        self.images = []

    def register(self, address: int, value: int, event: int) -> None:
        self.regs[address] = value
        self.register_events.append((event, address, value))

    def image(self, path: int, event: int, data: bytes) -> None:
        bb = self.regs.get(0x50, 0)
        pos = self.regs.get(0x51, 0)
        size = self.regs.get(0x52, 0)
        direction = self.regs.get(0x53, 0)
        dbp = (bb >> 32) & 0x3FFF
        dbw = (bb >> 48) & 0x3F
        dpsm = (bb >> 56) & 0x3F
        dsax = (pos >> 32) & 0x7FF
        dsay = (pos >> 48) & 0x7FF
        width = size & 0xFFF
        height = (size >> 32) & 0xFFF
        self.images.append((event, path, len(data), width, height, dpsm, dbp, dbw, dsax, dsay, direction))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump", type=Path)
    args = ap.parse_args()
    blob = args.dump.read_bytes()
    if struct.unpack_from("<I", blob, 0)[0] != 0xFFFFFFFF:
        raise SystemExit("Only new-format uncompressed dumps are supported")
    header_size = struct.unpack_from("<I", blob, 4)[0]
    state_size = struct.unpack_from("<I", blob, 12)[0]
    offset = 8 + header_size + state_size + 0x2000
    report = Reporter()
    parsers = {i: GifParser(i, report) for i in range(4)}
    event = 0
    while offset < len(blob):
        kind = blob[offset]
        offset += 1
        if kind == 0:
            path = blob[offset]
            size = struct.unpack_from("<I", blob, offset + 1)[0]
            offset += 5
            parsers[path].feed(blob[offset:offset + size], event)
            offset += size
        elif kind == 1:
            offset += 1
        elif kind == 2:
            offset += 4
        elif kind == 3:
            offset += 0x2000
        else:
            raise SystemExit(f"Bad event {kind} at 0x{offset - 1:X}")
        event += 1
    print("event path bytes   width height psm dbp   dbw x    y    dir")
    for row in report.images:
        print(f"{row[0]:5} {row[1]:4} {row[2]:7} {row[3]:5} {row[4]:6} {row[5]:3} {row[6]:04x} {row[7]:5} {row[8]:4} {row[9]:4} {row[10]:3}")


if __name__ == "__main__":
    main()
