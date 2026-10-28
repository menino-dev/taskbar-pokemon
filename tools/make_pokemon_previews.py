"""Generate animated GIF previews for every animation of Taskbar Pokemon at 4x (nearest neighbor).
Saves to tools/out/preview_pokemon/<anim_name>.gif.
"""

import json
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = ROOT / "upstream"
OUT = ROOT / "tools" / "out"
PREVIEW_DIR = OUT / "preview_pokemon"
FRAMES = OUT / "pokemon_frames"
CELL = 32
SCALE = 4

PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "tools"))
from pngio import read_png

with open(ROOT / "tools" / "pokemon_map.json", encoding="utf-8") as f:
    MAP = json.load(f)["anims"]

cat_anims = json.loads((UPSTREAM / "art" / "animations.json").read_text())
w_sheet, h_sheet, px_sheet = read_png(UPSTREAM / "art" / "cat_sheet.png")
orig_cells = {}
for r_idx, a in enumerate(cat_anims):
    frames = []
    for c_idx in range(a["frames"]):
        cell = [px_sheet[(r_idx * CELL + y) * w_sheet + c_idx * CELL + x] for y in range(CELL) for x in range(CELL)]
        frames.append([p if p[3] else (0, 0, 0, 0) for p in cell])
    orig_cells[a["name"]] = frames

for anim in MAP:
    name = anim["name"]
    source = anim.get("source")
    ms = anim.get("ms", 125)
    loop = anim.get("loop", True)

    anim_cells = []
    if source == "original":
        anim_cells = orig_cells[name]
    else:
        mirror = anim.get("mirror", False)
        frame_ids = anim["frames"]
        for fid in frame_ids:
            png_path = FRAMES / f"{fid}.png"
            w, h, px = read_png(png_path)

            pts = [(x, y) for y in range(h) for x in range(w) if px[y * w + x][3] > 0]
            max_py = max(y for x, y in pts) if pts else h - 1

            airborne_anims = ("pounce", "dangle", "heart", "alert", "zzz", "butterfly", "note", "fish", "hat_witch", "hat_santa", "hat_party")
            if name not in airborne_anims:
                shift_y = (CELL - 1) - max_py
            else:
                shift_y = 0

            cell = [(0, 0, 0, 0)] * (CELL * CELL)
            for y in range(h):
                for x in range(w):
                    src_x = (w - 1 - x) if mirror else x
                    p = px[y * w + src_x]
                    if p[3] > 0:
                        dy = y + shift_y
                        if 0 <= dy < CELL and 0 <= x < CELL:
                            cell[dy * CELL + x] = p
            anim_cells.append(cell)

    # Render frames to PIL Images with dark background
    pil_frames = []
    bg = (40, 44, 52, 255)
    for cell in anim_cells:
        img = Image.new("RGBA", (CELL, CELL), bg)
        pixels = img.load()
        for y in range(CELL):
            for x in range(CELL):
                p = cell[y * CELL + x]
                if p[3] > 0:
                    pixels[x, y] = p
        scaled = img.resize((CELL * SCALE, CELL * SCALE), Image.NEAREST)
        pil_frames.append(scaled)

    out_path = PREVIEW_DIR / f"{name}.gif"
    if pil_frames:
        pil_frames[0].save(
            out_path,
            save_all=True,
            append_images=pil_frames[1:],
            duration=ms,
            loop=0 if loop else 1,
            disposal=2,
            optimize=False
        )

print(f"Generated {len(MAP)} preview GIFs in {PREVIEW_DIR}")

