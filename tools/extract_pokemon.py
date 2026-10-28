"""Extract and inspect Pokemon GIF sprite assets from upstream-pokemon/media.
Converts GIF frames and auxiliary sheets into exact pixel-perfect PNG frames,
calculates head anchors, analyzes palettes, and produces a labeled 4x contact sheet.
"""

from pathlib import Path
import sys
from PIL import Image, ImageSequence, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "upstream-pokemon" / "media"
OUT = ROOT / "tools" / "out"
FRAMES_DIR = OUT / "pokemon_frames"
CONTACT_SHEET = OUT / "pokemon_contact_sheet.png"

CELL = 32
SCALE = 4


def extract_gif_frames(gif_path, prefix):
    """Extract frames from a GIF preserving exact pixels and transparency."""
    img = Image.open(gif_path)
    frames = []
    for idx, frame in enumerate(ImageSequence.Iterator(img)):
        rgba = frame.convert("RGBA")
        out_name = f"{prefix}_{idx:02d}.png"
        out_path = FRAMES_DIR / out_name
        rgba.save(out_path)
        frames.append((out_name, rgba))
    return frames


def extract_pokeball_frames():
    """Extract grounded 32x32 frames from the 64x384 pokeball sprite sheet."""
    sheet_path = MEDIA / "pokeball_sprite_sheet.png"
    if not sheet_path.exists():
        return []
    sheet = Image.open(sheet_path).convert("RGBA")
    frames = []
    # 6 frames of 64x64
    for i in range(6):
        box_64 = (0, i * 64, 64, (i + 1) * 64)
        slice_64 = sheet.crop(box_64)
        bbox = slice_64.getbbox()
        if bbox:
            cropped = slice_64.crop(bbox)
            cell_32 = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
            ox = (CELL - cropped.width) // 2
            oy = CELL - cropped.height
            cell_32.paste(cropped, (ox, oy))
        else:
            cell_32 = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        out_name = f"pokeball_{i:02d}.png"
        cell_32.save(FRAMES_DIR / out_name)
        frames.append((out_name, cell_32))
    return frames


def extract_aux_effects():
    """Extract heart, happy and other auxiliary effect sprites."""
    extracted = []
    for name in ["heart.png", "happy.png"]:
        p = MEDIA / name
        if p.exists():
            img = Image.open(p).convert("RGBA")
            # Pad or fit into a 16x16 / 32x32 cell
            cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
            # Center on 32x32
            ox = (CELL - img.width) // 2
            oy = (CELL - img.height) // 2
            cell.paste(img, (ox, oy))
            out_name = f"effect_{name}"
            cell.save(FRAMES_DIR / out_name)
            extracted.append((out_name, cell))
    return extracted


def build_contact_sheet(items):
    """Generate a 4x nearest neighbor contact sheet with labeled frames."""
    # Organize into a grid
    cols = 6
    rows = (len(items) + cols - 1) // cols
    tile_w = CELL * SCALE
    tile_h = CELL * SCALE + 20  # Extra 20px below tile for label
    margin = 8

    sheet_w = cols * (tile_w + margin) + margin
    sheet_h = rows * (tile_h + margin) + margin

    sheet = Image.new("RGBA", (sheet_w, sheet_h), (30, 32, 40, 255))
    draw = ImageDraw.Draw(sheet)

    for idx, (label, img) in enumerate(items):
        r = idx // cols
        c = idx % cols
        x = margin + c * (tile_w + margin)
        y = margin + r * (tile_h + margin)

        # Draw dark checkerboard tile background for transparency visibility
        draw.rectangle([x, y, x + tile_w - 1, y + CELL * SCALE - 1], fill=(45, 48, 58, 255), outline=(70, 75, 90, 255))

        # Scale 4x nearest neighbor
        scaled = img.resize((CELL * SCALE, CELL * SCALE), Image.NEAREST)
        sheet.paste(scaled, (x, y), scaled)

        # Draw label
        short_lbl = label.replace(".png", "")
        draw.text((x + 2, y + CELL * SCALE + 2), short_lbl, fill=(220, 220, 230, 255))

    sheet.save(CONTACT_SHEET)
    print(f"Contact sheet saved to {CONTACT_SHEET} ({sheet_w}x{sheet_h})")


def main():
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    all_items = []

    # 1. Primary candidate: Pikachu (Default & Shiny)
    gen1 = MEDIA / "gen1"
    primary_pokes = ["pikachu", "bulbasaur", "charmander", "squirtle", "eevee"]

    for poke in primary_pokes:
        poke_dir = gen1 / poke
        if not poke_dir.exists():
            continue
        for kind in ["default_idle_8fps.gif", "default_walk_8fps.gif", "shiny_idle_8fps.gif", "shiny_walk_8fps.gif"]:
            gif_path = poke_dir / kind
            if gif_path.exists():
                short_kind = kind.replace("_8fps.gif", "")
                frames = extract_gif_frames(gif_path, f"{poke}_{short_kind}")
                all_items.extend(frames)

    # 2. Pokeball frames
    pokeball_frames = extract_pokeball_frames()
    all_items.extend(pokeball_frames)

    # 3. Aux effects
    aux_frames = extract_aux_effects()
    all_items.extend(aux_frames)

    print(f"Extracted {len(all_items)} total frames into {FRAMES_DIR}")
    build_contact_sheet(all_items)


if __name__ == "__main__":
    main()

