"""Losslessly refilter a 16-bit grayscale heightmap; never alter a height sample."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib
import numpy as np


def read_rows(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    offset = 8
    parts = []
    header = None
    while offset < len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        part = data[offset + 8 : offset + 8 + size]
        if (
            zlib.crc32(kind + part)
            != struct.unpack(">I", data[offset + 8 + size : offset + 12 + size])[0]
        ):
            raise ValueError("PNG CRC mismatch")
        if kind == b"IHDR":
            header = part
        elif kind == b"IDAT":
            parts.append(part)
        elif kind not in (b"IEND",):
            raise ValueError("unexpected heightmap PNG chunk")
        offset += size + 12
    width, height, depth, color, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", header
    )
    if (depth, color, compression, filter_method, interlace) != (16, 0, 0, 0, 0):
        raise ValueError("expected noninterlaced 16-bit grayscale PNG")
    encoded = np.frombuffer(zlib.decompress(b"".join(parts)), np.uint8).reshape(
        height, 1 + width * 2
    )
    rows = np.zeros((height, width * 2), np.uint8)
    for i, row in enumerate(encoded):
        if row[0] == 0:
            rows[i] = row[1:]
        elif row[0] == 2:
            rows[i] = row[1:] + (rows[i - 1] if i else 0)
        elif row[0] == 1:
            # Two independent cumulative byte streams, one per 16-bit byte.
            rows[i, 0::2] = np.cumsum(row[1::2], dtype=np.uint64).astype(np.uint8)
            rows[i, 1::2] = np.cumsum(row[2::2], dtype=np.uint64).astype(np.uint8)
        else:
            raise ValueError("only None/Sub/Up filters are supported")
    return header, rows


def compress_heightmap(path):
    path = Path(path)
    before = path.stat().st_size
    header, rows = read_rows(path)

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    options = []
    for mode in (0, 1, 2):
        encoded = rows.copy()
        if mode == 1:
            encoded[:, 2:] -= rows[:, :-2]
        if mode == 2:
            encoded[1:] -= rows[:-1]
        filtered = np.column_stack((np.full(len(rows), mode, np.uint8), encoded))
        compressed = zlib.compress(filtered.tobytes(), level=9)
        options.append((len(compressed), mode, compressed))
    _, mode, compressed = min(options, key=lambda item: (item[0], item[1]))
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )
    path.write_bytes(data)
    new_header, new_rows = read_rows(path)
    assert header == new_header and np.array_equal(rows, new_rows)
    return dict(
        before_bytes=before,
        after_bytes=len(data),
        png_filter=mode,
        decoded_height_samples_sha256=hashlib.sha256(rows.tobytes()).hexdigest(),
        samples_unchanged=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="16bit高さPNGの値を変えずに可逆圧縮する"
    )
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(json.dumps(compress_heightmap(args.path), indent=2))
