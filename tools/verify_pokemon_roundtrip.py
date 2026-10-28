"""Roundtrip verification for Taskbar Pokemon mod:
Reads taskbar-pokemon.wh.cpp directly, extracts kPalette, kFrameOffsets, kFrameData,
decodes every frame using the 2-byte RLE algorithm, and compares pixel-by-pixel.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "taskbar-pokemon.wh.cpp"
OUT = ROOT / "tools" / "out"
ROUNDTRIP_DIR = OUT / "pokemon_roundtrip"
ROUNDTRIP_DIR.mkdir(parents=True, exist_ok=True)
CELL = 32

sys.path.insert(0, str(ROOT / "tools"))
from pngio import write_png
import pokemon_to_cpp


def parse_cpp_mod():
    code = MOD.read_text(encoding="utf-8")

    m_pal = re.search(r"constexpr uint32_t kPalette\[\] = \{([^}]+)\};", code, re.DOTALL)
    if not m_pal:
        sys.exit("error: kPalette not found in mod")
    pal_hex = re.findall(r"0x([0-9A-Fa-f]{8})", m_pal.group(1))
    palette = [int(h, 16) for h in pal_hex]

    m_cnt = re.search(r"constexpr int kFrameCount = (\d+);", code)
    if not m_cnt:
        sys.exit("error: kFrameCount not found in mod")
    frame_count = int(m_cnt.group(1))

    m_off = re.search(r"constexpr uint16_t kFrameOffsets\[\] = \{([^}]+)\};", code, re.DOTALL)
    if not m_off:
        m_off = re.search(r"constexpr uint32_t kFrameOffsets\[\] = \{([^}]+)\};", code, re.DOTALL)
    if not m_off:
        sys.exit("error: kFrameOffsets not found in mod")
    offsets = [int(x.strip()) for x in m_off.group(1).replace("\n", "").split(",") if x.strip()]

    m_dat = re.search(r"constexpr uint8_t kFrameData\[\] = \{([^}]+)\};", code, re.DOTALL)
    if not m_dat:
        sys.exit("error: kFrameData not found in mod")
    data_hex = re.findall(r"0x([0-9A-Fa-f]{2})", m_dat.group(1))
    data = bytes([int(h, 16) for h in data_hex])

    return palette, frame_count, offsets, data


def decode_cpp_rle(data_slice, palette, pixel_count=CELL * CELL):
    assert len(data_slice) % 2 == 0, f"data size {len(data_slice)} is odd"
    pixels = []
    for i in range(0, len(data_slice), 2):
        run = data_slice[i] + 1
        idx = data_slice[i + 1]
        assert idx < len(palette), f"palette index {idx} out of range ({len(palette)})"
        argb = palette[idx]
        a = (argb >> 24) & 0xFF
        r = (argb >> 16) & 0xFF
        g = (argb >> 8) & 0xFF
        b = argb & 0xFF
        rgba = (r, g, b, a) if a > 0 else (0, 0, 0, 0)
        pixels.extend([rgba] * run)
    assert len(pixels) == pixel_count, f"decoded pixel count {len(pixels)} != {pixel_count}"
    return pixels


def main():
    palette, frame_count, offsets, data = parse_cpp_mod()
    print(f"Mod parsed: {frame_count} frames, {len(palette)} palette entries, {len(data)} data bytes")
    assert len(offsets) == frame_count + 1, f"offsets count {len(offsets)} != frame_count + 1"

    mapping = pokemon_to_cpp.json.loads(pokemon_to_cpp.MAP_FILE.read_text(encoding="utf-8"))["anims"]
    orig_cells, orig_anchors = pokemon_to_cpp.load_original_assets()
    processed, anim_infos = pokemon_to_cpp.process_frames(mapping, orig_cells, orig_anchors)
    assert len(processed) == frame_count, f"processed count {len(processed)} != frame_count {frame_count}"

    total_diff_pixels = 0
    for i in range(frame_count):
        begin = offsets[i]
        end = offsets[i + 1]
        decoded = decode_cpp_rle(data[begin:end], palette, CELL * CELL)
        expected = processed[i]["cell"]

        diffs = 0
        for p_idx in range(CELL * CELL):
            if decoded[p_idx] != expected[p_idx]:
                diffs += 1
        if diffs > 0:
            print(f"Frame {i} ({processed[i]['anim']}): {diffs} mismatching pixels!")
            total_diff_pixels += diffs
        else:
            write_png(ROUNDTRIP_DIR / f"frame_{i:02d}.png", CELL, CELL, decoded)

    print(f"Roundtrip comparison complete. Total pixel differences across all {frame_count} frames: {total_diff_pixels}")
    if total_diff_pixels == 0:
        print("RESULT: 100% PERFECT PIXEL-EXACT ROUNDTRIP (0 differences)")
    else:
        sys.exit(f"FAILED: {total_diff_pixels} pixel differences found!")


if __name__ == "__main__":
    main()

