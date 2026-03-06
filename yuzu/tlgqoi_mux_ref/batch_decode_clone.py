#!/usr/bin/env python3
"""Batch decoder for TLGqoi+QHDR (QOICloneStream) multi-image files.

Scans a directory for TLGref files, groups them by container,
decodes each container once, and saves images with TLGref-based names.

Naming: ev104aa.tlg (idx=1, container=ev104__xxx.tlg) -> ev104_01_aa.png
"""
import struct
import sys
import os
import glob
import lz4.block
import numpy as np
from PIL import Image
from collections import defaultdict


def decode_leb128(buf, offset):
    result = 0
    shift = 0
    while offset < len(buf):
        b = buf[offset]; offset += 1
        result |= (b & 0x7f) << shift
        shift += 7
        if (b & 0x80) == 0:
            break
    return result, offset


class QOIStreamDecoder:
    def __init__(self):
        self.reset()

    def reset(self):
        self.index = [(0, 0, 0, 0)] * 64
        self.px = (0, 0, 0, 255)

    def decode_one(self, data, pos):
        b1 = data[pos]; pos += 1
        px = self.px
        if b1 == 0xFE:
            px = (data[pos], data[pos+1], data[pos+2], px[3]); pos += 3; count = 1
        elif b1 == 0xFF:
            px = (data[pos], data[pos+1], data[pos+2], data[pos+3]); pos += 4; count = 1
        elif (b1 & 0xC0) == 0x00:
            px = self.index[b1 & 0x3F]; count = 1
        elif (b1 & 0xC0) == 0x40:
            px = ((px[0]+((b1>>4)&3)-2)&0xFF, (px[1]+((b1>>2)&3)-2)&0xFF,
                  (px[2]+(b1&3)-2)&0xFF, px[3]); count = 1
        elif (b1 & 0xC0) == 0x80:
            b2 = data[pos]; pos += 1; dg = (b1 & 0x3F) - 32
            px = ((px[0]+dg+((b2>>4)&0xF)-8)&0xFF, (px[1]+dg)&0xFF,
                  (px[2]+dg+(b2&0xF)-8)&0xFF, px[3]); count = 1
        else:
            count = (b1 & 0x3F) + 1
        self.px = px
        self.index[(px[0]*3+px[1]*5+px[2]*7+px[3]*11) % 64] = px
        return px, count, pos


def decompress_lz4_chunks(data, offset, total_size):
    end = offset + total_size
    result = bytearray()
    prev_block = None
    while offset < end:
        header = struct.unpack_from('<I', data, offset)[0]; offset += 4
        input_size = (header >> 16) & 0xFFFF
        carryover = (header >> 15) & 1
        output_size = header & 0x7FFF
        if output_size == 0:
            output_size = 32768
        compressed = bytes(data[offset:offset + input_size]); offset += input_size
        if carryover and prev_block is not None:
            decompressed = lz4.block.decompress(compressed, uncompressed_size=output_size, dict=prev_block)
        else:
            decompressed = lz4.block.decompress(compressed, uncompressed_size=output_size)
        prev_block = decompressed
        result.extend(decompressed)
    return result


def decode_clone_container(filename):
    """Decode a TLGqoi+QHDR container. Returns list of numpy arrays (RGBA)."""
    with open(filename, 'rb') as f:
        data = f.read()

    if data[:11] != b'TLGqoi\x00raw\x1a':
        return None
    if data[20:24] != b'QHDR':
        return None

    width = struct.unpack_from('<I', data, 12)[0]
    height = struct.unpack_from('<I', data, 16)[0]
    qhdr_size = struct.unpack_from('<I', data, 24)[0]
    qhdr = data[28:28 + qhdr_size]

    num_images = struct.unpack_from('<I', qhdr, 4)[0]
    band_height = struct.unpack_from('<I', qhdr, 8)[0]
    num_bands = struct.unpack_from('<I', qhdr, 12)[0]
    total_qoi_bytes = struct.unpack_from('<Q', qhdr, 24)[0]

    data_start = 28 + qhdr_size

    # Find DTBL and RTBL
    dtbl_off = data.find(b'DTBL', data_start + total_qoi_bytes - 16)
    rtbl_off = data.find(b'RTBL', dtbl_off + 8)
    if dtbl_off < 0 or rtbl_off < 0:
        return None

    # Parse DTBL
    dtbl_size = struct.unpack_from('<I', data, dtbl_off + 4)[0]
    dtbl_data = data[dtbl_off + 8:dtbl_off + 8 + dtbl_size]
    off = 0
    dtbl_count, off = decode_leb128(dtbl_data, off)
    dtbl_vals = []
    for _ in range(dtbl_count):
        v, off = decode_leb128(dtbl_data, off)
        dtbl_vals.append(v)
    band_dist_sizes_needed = True

    # Parse RTBL
    rtbl_size = struct.unpack_from('<I', data, rtbl_off + 4)[0]
    rtbl_data = data[rtbl_off + 8:rtbl_off + 8 + rtbl_size]
    off = 0
    rtbl_count, off = decode_leb128(rtbl_data, off)
    band_dist_sizes = []
    for _ in range(rtbl_count):
        v, off = decode_leb128(rtbl_data, off)
        band_dist_sizes.append(v)

    dist_data_start = rtbl_off + 8 + rtbl_size

    images = [np.zeros((height, width, 4), dtype=np.uint8) for _ in range(num_images)]

    qoi = QOIStreamDecoder()
    qoi_pos = data_start + 8  # skip 8-byte prefix
    dist_pos = dist_data_start

    for band_idx in range(num_bands):
        band_y = band_idx * band_height
        band_h = min(band_height, height - band_y)
        total_interleaved = width * num_images * band_h

        dist_size = band_dist_sizes[band_idx]
        decompressed = decompress_lz4_chunks(data, dist_pos, dist_size)
        dist_pos += dist_size

        qoi.reset()
        _, _, qoi_pos = qoi.decode_one(data, qoi_pos)
        _, _, qoi_pos = qoi.decode_one(data, qoi_pos)
        dist_off = 0
        _, dist_off = decode_leb128(decompressed, dist_off)

        pixels = []
        runs = []
        total = 0
        while total < total_interleaved:
            px, qc, qoi_pos = qoi.decode_one(data, qoi_pos)
            mask, dist_off = decode_leb128(decompressed, dist_off)
            rc = mask + qc
            if total + rc > total_interleaved:
                rc = total_interleaved - total
            pixels.append(px)
            runs.append(rc)
            total += rc

        flat = np.empty((total_interleaved, 4), dtype=np.uint8)
        pos = 0
        for px, rc in zip(pixels, runs):
            flat[pos:pos+rc] = px
            pos += rc

        flat_reshaped = flat.reshape(band_h, width, num_images, 4)
        for img_idx in range(num_images):
            images[img_idx][band_y:band_y+band_h, :, :] = flat_reshaped[:, :, img_idx, :]

    return images


def parse_tlgref(filename):
    """Parse a TLGref file. Returns (container_name, idx, count) or None."""
    with open(filename, 'rb') as f:
        data = f.read()
    if data[:6] != b'TLGref':
        return None
    chunk_size = struct.unpack_from('<I', data, 24)[0]
    chunk = data[28:28 + chunk_size]
    idx = struct.unpack_from('<I', chunk, 4)[0]
    count = struct.unpack_from('<I', chunk, 8)[0]
    str_len = struct.unpack_from('<I', chunk, 12)[0]
    name = chunk[16:16 + str_len].decode('utf-16-le').rstrip('\x00')
    return name, idx, count


def batch_decode(input_dir, output_dir=None):
    if output_dir is None:
        output_dir = input_dir
    os.makedirs(output_dir, exist_ok=True)

    tlg_files = glob.glob(os.path.join(input_dir, '*.tlg'))

    # Classify files
    containers = {}   # container_basename -> full_path
    refs = defaultdict(list)  # container_basename -> [(ref_basename, idx)]

    for fn in tlg_files:
        sz = os.path.getsize(fn)
        basename = os.path.basename(fn)

        if sz < 200:
            result = parse_tlgref(fn)
            if result:
                cont_name, idx, count = result
                refs[cont_name].append((os.path.splitext(basename)[0], idx))
        else:
            with open(fn, 'rb') as f:
                header = f.read(24)
            if header[:11] == b'TLGqoi\x00raw\x1a' and header[20:24] == b'QHDR':
                containers[basename] = fn

    if not containers:
        print("No TLGqoi+QHDR containers found")
        return

    # Process each container
    for cont_basename, cont_path in sorted(containers.items()):
        prefix = cont_basename.split('__')[0]
        ref_list = sorted(refs.get(cont_basename, []), key=lambda x: x[1])

        print(f"\nDecoding: {cont_basename} ({len(ref_list)} refs)")
        images = decode_clone_container(cont_path)
        if images is None:
            print(f"  FAILED to decode")
            continue

        print(f"  Got {len(images)} images")

        # Determine index width (2 digits for <100, 3 for >=100)
        max_idx = max((idx for _, idx in ref_list), default=len(images)-1)
        idx_width = 3 if max_idx >= 100 else 2

        # Save images referenced by TLGref
        saved = set()
        for ref_base, idx in ref_list:
            if idx >= len(images):
                print(f"  WARNING: {ref_base} idx={idx} out of range")
                continue
            suffix = ref_base[len(prefix):]
            out_name = f"{prefix}_{idx:0{idx_width}d}_{suffix}.png"
            out_path = os.path.join(output_dir, out_name)
            Image.fromarray(images[idx], 'RGBA').save(out_path)
            print(f"  {ref_base}.tlg (idx={idx}) -> {out_name}")
            saved.add(idx)

        # Save any images without TLGref
        for idx in range(len(images)):
            if idx not in saved:
                out_name = f"{prefix}_{idx:0{idx_width}d}.png"
                out_path = os.path.join(output_dir, out_name)
                Image.fromarray(images[idx], 'RGBA').save(out_path)
                print(f"  (no ref) idx={idx} -> {out_name}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python batch_decode_clone.py <input_dir> [output_dir]")
        sys.exit(1)

    in_dir = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else None
    batch_decode(in_dir, out_dir)
