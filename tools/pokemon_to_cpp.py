"""Convert Pokemon assets into the generated sprites block and write taskbar-pokemon.wh.cpp.

CLI Options:
  --pokemon <name>   Pokemon species name (default: pikachu)
  --shiny            Use shiny sprite variant (default: false)

Reads:
  upstream-pokemon/media/gen* / <pokemon> /
  tools/out/pokemon_frames/*.png
  upstream/art/cat_sheet.png
  upstream/art/animations.json
  upstream/taskbar-cat.wh.cpp

Writes:
  taskbar-pokemon.wh.cpp (in repository root)
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = ROOT / "upstream"
MEDIA = ROOT / "upstream-pokemon" / "media"
MAP_FILE = ROOT / "tools" / "pokemon_map.json"
FRAMES_DIR = ROOT / "tools" / "out" / "pokemon_frames"
MOD_OUT = ROOT / "taskbar-pokemon.single.wh.cpp"
BEGIN = "// BEGIN GENERATED SPRITES"
END = "// END GENERATED SPRITES"
CELL = 32

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pngio import read_png
from extract_pokemon import extract_gif_frames, extract_pokeball_frames, extract_aux_effects


def argb_to_tuple(argb):
    a = (argb >> 24) & 0xFF
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    return (r, g, b, a)


def tuple_to_argb(rgba):
    return (rgba[3] << 24) | (rgba[0] << 16) | (rgba[1] << 8) | rgba[2]


def find_pokemon_dir(name):
    """Locate Pokemon directory across all generations."""
    name_clean = name.strip().lower()
    for gen in ["gen1", "gen2", "gen3", "gen4", "gen5"]:
        d = MEDIA / gen / name_clean
        if d.is_dir():
            return d
    return None


def ensure_pokemon_frames(name, shiny=False):
    """Ensure walk and idle frames for the specified Pokemon exist in FRAMES_DIR."""
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    poke_dir = find_pokemon_dir(name)
    if not poke_dir:
        raise ValueError(f"Pokemon '{name}' not found in {MEDIA}")

    variant = "shiny" if shiny else "default"
    walk_gif = poke_dir / f"{variant}_walk_8fps.gif"
    idle_gif = poke_dir / f"{variant}_idle_8fps.gif"

    if not walk_gif.exists():
        # Fallback to default if shiny missing
        walk_gif = poke_dir / "default_walk_8fps.gif"
    if not idle_gif.exists():
        idle_gif = poke_dir / "default_idle_8fps.gif"

    prefix_walk = f"{name}_{variant}_walk"
    prefix_idle = f"{name}_{variant}_idle"

    walk_frames = [p.stem for p in sorted(FRAMES_DIR.glob(f"{prefix_walk}_*.png"))]
    if not walk_frames:
        extracted = extract_gif_frames(walk_gif, prefix_walk)
        walk_frames = [f[0].replace(".png", "") for f in extracted]

    idle_frames = [p.stem for p in sorted(FRAMES_DIR.glob(f"{prefix_idle}_*.png"))]
    if not idle_frames:
        extracted = extract_gif_frames(idle_gif, prefix_idle)
        idle_frames = [f[0].replace(".png", "") for f in extracted]

    # Ensure dance frames exist
    prefix_dance = f"{name}_{variant}_dance"
    dance_frames = [p.stem for p in sorted(FRAMES_DIR.glob(f"{prefix_dance}_*.png"))]
    if len(dance_frames) < 4:
        from PIL import Image
        i0_img = Image.open(FRAMES_DIR / f"{idle_frames[0]}.png").convert("RGBA")
        pts = [(x, y) for y in range(CELL) for x in range(CELL) if i0_img.getpixel((x, y))[3] > 0]
        min_x = min(x for x, y in pts) if pts else 0
        max_x = max(x for x, y in pts) if pts else CELL - 1
        cx = (min_x + max_x) // 2

        flipped = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        for x, y in pts:
            nx = 2 * cx - x
            if 0 <= nx < CELL:
                flipped.putpixel((nx, y), i0_img.getpixel((x, y)))

        dx_left = 1 if min_x >= 1 else 0
        d0 = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        for x in range(CELL):
            for y in range(CELL):
                p = flipped.getpixel((x, y))
                if p[3] > 0 and x - dx_left >= 0:
                    d0.putpixel((x - dx_left, y), p)

        d1 = i0_img.copy()

        dx_right = 1 if max_x + 1 < CELL else 0
        d2 = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        for x in range(CELL):
            for y in range(CELL):
                p = i0_img.getpixel((x, y))
                if p[3] > 0 and x + dx_right < CELL:
                    d2.putpixel((x + dx_right, y), p)

        d3 = i0_img.copy()

        d0.save(FRAMES_DIR / f"{prefix_dance}_00.png")
        d1.save(FRAMES_DIR / f"{prefix_dance}_01.png")
        d2.save(FRAMES_DIR / f"{prefix_dance}_02.png")
        d3.save(FRAMES_DIR / f"{prefix_dance}_03.png")
        dance_frames = [f"{prefix_dance}_{i:02d}" for i in range(4)]

    # Ensure pokeball frames exist
    if not (FRAMES_DIR / "pokeball_00.png").exists():
        extract_pokeball_frames()

    # Ensure aux effects exist
    if not (FRAMES_DIR / "effect_heart.png").exists():
        extract_aux_effects()

    return walk_frames, idle_frames, dance_frames


def build_pokemon_mapping(name, walk_frames, idle_frames, dance_frames):
    """Build 31-anim mapping for the specified Pokemon."""
    w0 = walk_frames[0]
    w1 = walk_frames[1] if len(walk_frames) > 1 else walk_frames[0]
    i0 = idle_frames[0]
    i1 = idle_frames[1] if len(idle_frames) > 1 else idle_frames[0]

    return [
        {"name": "walk",      "ms": 125,  "loop": True,  "mirror": False, "frames": walk_frames},
        {"name": "sit",       "ms": 350,  "loop": True,  "mirror": False, "frames": idle_frames},
        {"name": "sit_tail",  "ms": 200,  "loop": False, "mirror": False, "frames": [i1, i0, i1]},
        {"name": "sleep",     "ms": 1000, "loop": True,  "mirror": False, "frames": [i0]},
        {"name": "wake",      "ms": 180,  "loop": False, "mirror": False, "frames": [i1, i0]},
        {"name": "loaf",      "ms": 1000, "loop": True,  "mirror": False, "frames": [i0]},
        {"name": "crouch",    "ms": 150,  "loop": True,  "mirror": False, "frames": [w0, w1]},
        {"name": "pounce",    "ms": 130,  "loop": False, "mirror": False, "frames": [w1]},
        {"name": "happy",     "ms": 120,  "loop": True,  "mirror": False, "frames": idle_frames},
        {"name": "meow",      "ms": 160,  "loop": False, "mirror": False, "frames": [i1]},
        {"name": "roll",      "ms": 180,  "loop": False, "mirror": False, "frames": [i0, w1], "upside_down": [1]},
        {"name": "belly",     "ms": 280,  "loop": True,  "mirror": False, "frames": [w1, i1], "upside_down": [0, 1]},
        {"name": "dangle",    "ms": 200,  "loop": True,  "mirror": False, "frames": [w1]},
        {"name": "heart",     "source": "original"},
        {"name": "alert",     "source": "original"},
        {"name": "stretch",   "ms": 250,  "loop": False, "mirror": False, "frames": [w0, i0]},
        {"name": "yawn",      "ms": 220,  "loop": False, "mirror": False, "frames": [i1]},
        {"name": "groom",     "ms": 200,  "loop": True,  "mirror": False, "frames": [i0, w0]},
        {"name": "scratch",   "ms": 100,  "loop": True,  "mirror": False, "frames": [i1, i0]},
        {"name": "knead",     "ms": 240,  "loop": True,  "mirror": False, "frames": [w0, w1]},
        {"name": "zzz",       "source": "original"},
        {"name": "bat",       "ms": 100,  "loop": False, "mirror": False, "frames": [w0, w1]},
        {"name": "butterfly", "source": "original"},
        {"name": "yarn",      "ms": 120,  "loop": True,  "mirror": False, "frames": ["pokeball_00", "pokeball_01"]},
        {"name": "gift",      "ms": 1000, "loop": True,  "mirror": False, "frames": ["pokeball_00"]},
        {"name": "dance",     "ms": 150,  "loop": True,  "mirror": False, "frames": dance_frames},
        {"name": "note",      "source": "original"},
        {"name": "fish",      "source": "original"},
        {"name": "hat_witch", "source": "original"},
        {"name": "hat_santa", "source": "original"},
        {"name": "hat_party", "source": "original"}
    ]


def load_original_assets():
    cat_anims = json.loads((UPSTREAM / "art" / "animations.json").read_text())
    w_sheet, h_sheet, px_sheet = read_png(UPSTREAM / "art" / "cat_sheet.png")
    cells = {}
    anchors = {}
    for r_idx, a in enumerate(cat_anims):
        frames = []
        for c_idx in range(a["frames"]):
            cell = [px_sheet[(r_idx * CELL + y) * w_sheet + c_idx * CELL + x] for y in range(CELL) for x in range(CELL)]
            frames.append([p if p[3] else (0, 0, 0, 0) for p in cell])
        cells[a["name"]] = frames
        anchors[a["name"]] = a.get("anchors")
    return cells, anchors


def process_frames(mapping, orig_cells, orig_anchors):
    processed = []
    anim_infos = []

    for anim in mapping:
        name = anim["name"]
        source = anim.get("source")
        ms = anim.get("ms", 125)
        loop = anim.get("loop", True)

        if source == "original":
            cells = orig_cells[name]
            a_list = orig_anchors[name] or [None] * len(cells)
            first_idx = len(processed)
            for i, c in enumerate(cells):
                anch = a_list[i]
                if anch is None:
                    anchor = (16, 8, False)
                else:
                    anchor = (anch[0], anch[1], bool(anch[2]))
                processed.append({
                    "anim": name,
                    "frame_idx": i,
                    "cell": c,
                    "anchor": anchor
                })
            anim_infos.append({
                "name": name,
                "first": first_idx,
                "count": len(cells),
                "ms": ms,
                "loop": loop
            })
        else:
            mirror = anim.get("mirror", False)
            frame_ids = anim["frames"]
            upside_down = anim.get("upside_down", [])
            first_idx = len(processed)

            for f_idx, fid in enumerate(frame_ids):
                png_path = FRAMES_DIR / f"{fid}.png"
                if not png_path.exists():
                    raise FileNotFoundError(f"Frame file not found: {png_path}")
                w, h, px = read_png(png_path)

                pts = [(x, y) for y in range(h) for x in range(w) if px[y * w + x][3] > 0]
                max_py = max(y for x, y in pts) if pts else h - 1

                # If grounded animation, shift down so lowest pixel touches row 31 (taskbar floor)
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

                cell_pts = [(x, y) for y in range(CELL) for x in range(CELL) if cell[y * CELL + x][3] > 0]
                is_upside_down = (f_idx in upside_down)

                if is_upside_down:
                    max_y = max(y for x, y in cell_pts) if cell_pts else 24
                    head_pts = [x for x, y in cell_pts if y >= max_y - 3]
                    anchor_x = round(sum(head_pts) / len(head_pts)) if head_pts else 16
                    anchor_y = max_y
                    anchor_upright = False
                elif name in ("yarn", "gift"):
                    anchor_x = 16
                    anchor_y = 8
                    anchor_upright = False
                else:
                    min_y = min(y for x, y in cell_pts) if cell_pts else 12
                    head_pts = [x for x, y in cell_pts if y <= min_y + 2]
                    anchor_x = round(sum(head_pts) / len(head_pts)) if head_pts else 16
                    # Ensure anchor_x >= 16 for head when facing right (effects follow head)
                    if anchor_x < 16:
                        anchor_x = 16
                    anchor_y = min_y
                    anchor_upright = True

                processed.append({
                    "anim": name,
                    "frame_idx": f_idx,
                    "fid": fid,
                    "cell": cell,
                    "anchor": (anchor_x, anchor_y, anchor_upright)
                })

            anim_infos.append({
                "name": name,
                "first": first_idx,
                "count": len(frame_ids),
                "ms": ms,
                "loop": loop
            })

    return processed, anim_infos


def build_palette(processed):
    palette = [(0, 0, 0, 0)]  # Index 0 is transparent
    seen = set()
    for item in processed:
        for p in item["cell"]:
            if p[3] > 0 and p not in seen:
                seen.add(p)
                palette.append(p)
    return palette


def encode_rle_2byte(indices):
    data = []
    i = 0
    n = len(indices)
    while i < n:
        idx = indices[i]
        run = 1
        while i + run < n and run < 256 and indices[i + run] == idx:
            run += 1
        data.append(run - 1)
        data.append(idx)
        i += run
    return data


def decode_rle_2byte(data, count):
    if len(data) % 2 != 0:
        raise ValueError("odd data length in 2-byte RLE")
    pixels = []
    for i in range(0, len(data), 2):
        run = data[i] + 1
        idx = data[i + 1]
        pixels.extend([idx] * run)
    if len(pixels) != count:
        raise ValueError(f"decode pixel count mismatch: {len(pixels)} != {count}")
    return pixels


def camel(name):
    return "".join(part.capitalize() for part in name.split("_"))


def render_sprites_block(processed, anim_infos, palette):
    p_lookup = {p: i for i, p in enumerate(palette)}

    all_data = []
    offsets = []
    for item in processed:
        indices = [p_lookup[p] for p in item["cell"]]
        enc = encode_rle_2byte(indices)
        assert decode_rle_2byte(enc, len(indices)) == indices, f"Roundtrip failed for {item['anim']}"
        offsets.append(len(all_data))
        all_data.extend(enc)
    offsets.append(len(all_data))

    offset_type = "uint32_t" if len(all_data) > 65535 else "uint16_t"

    lines = [
        BEGIN + " (tools/pokemon_to_cpp.py, do not edit by hand)",
        "namespace sprites {",
        "",
        "constexpr uint32_t kPalette[] = {"
    ]
    for p in palette:
        argb = tuple_to_argb(p)
        if p[3] == 0:
            lines.append("    0x00000000,  // transparent")
        else:
            lines.append(f"    0x{argb:08X},")
    lines.append("};")
    lines.append("")
    lines.append(f"constexpr int kFrameCount = {len(processed)};")
    lines.append("")
    lines.append("// One past the last frame is the end of the data.")
    lines.append(f"constexpr {offset_type} kFrameOffsets[] = {{")
    for i in range(0, len(offsets), 12):
        lines.append("    " + ", ".join(str(o) for o in offsets[i:i + 12]) + ",")
    lines.append("};")
    lines.append("")
    lines.append("constexpr uint8_t kFrameData[] = {")
    for i in range(0, len(all_data), 16):
        lines.append("    " + ", ".join(f"0x{b:02X}" for b in all_data[i:i + 16]) + ",")
    lines.append("};")
    lines.append("")
    lines.append("enum Anim {")
    for anim in anim_infos:
        lines.append(f"    k{camel(anim['name'])},")
    lines.append("    kAnimCount,")
    lines.append("};")
    lines.append("")
    lines.append("// Top of the head in each frame (sprite pixels), for effects and hats.")
    lines.append("constexpr cat::Anchor kFrameAnchors[kFrameCount] = {")
    for item in processed:
        ax, ay, upright = item["anchor"]
        up_str = "true" if upright else "false"
        tag = item.get("fid", f"orig_{item['frame_idx']}")
        lines.append(f"    {{{ax}, {ay}, {up_str}}},  // {item['anim']} ({tag})")
    lines.append("};")
    lines.append("")
    lines.append("// first frame, frame count, ms per frame, loops")
    lines.append("constexpr cat::AnimInfo kAnims[kAnimCount] = {")
    for anim in anim_infos:
        loop_str = "true" if anim["loop"] else "false"
        lines.append(f"    {{{anim['first']}, {anim['count']}, {anim['ms']}, {loop_str}}},  // {anim['name']}")
    lines.append("};")
    lines.append("")
    lines.append("}  // namespace sprites")
    lines.append(END)
    return "\n".join(lines), processed, palette


def generate_taskbar_pokemon(pokemon="pikachu", shiny=False):
    pokemon = pokemon.strip().lower()
    display_name = pokemon.capitalize()

    walk_frames, idle_frames, dance_frames = ensure_pokemon_frames(pokemon, shiny)
    mapping = build_pokemon_mapping(pokemon, walk_frames, idle_frames, dance_frames)

    # Save to MAP_FILE for tools like make_pokemon_previews and verify
    MAP_FILE.write_text(json.dumps({"pokemon": pokemon, "shiny": shiny, "anims": mapping}, indent=2), encoding="utf-8")

    orig_cells, orig_anchors = load_original_assets()
    processed, anim_infos = process_frames(mapping, orig_cells, orig_anchors)
    palette = build_palette(processed)

    block, processed, palette = render_sprites_block(processed, anim_infos, palette)

    # Read base source from upstream
    source = (UPSTREAM / "taskbar-cat.wh.cpp").read_text(encoding="utf-8")

    # Replace mod header metadata
    source = source.replace("// @id              taskbar-cat", "// @id              taskbar-pokemon")
    source = source.replace("// @name            Taskbar Cat", "// @name            Taskbar Pokémon")
    source = source.replace(
        "// @description     An orange pixel-art cat that lives on your Windows 11 taskbar: it wanders, naps, grooms, purrs when you hover, hunts butterflies, plays with yarn and reacts to you.",
        f"// @description     A nostalgic pixel-art Pokémon companion ({display_name}) that lives on your Windows 11 taskbar: wanders, naps, plays with a Pokéball and keeps you company."
    )
    source = source.replace("// @author          viraj-rgb", "// @author          menino-dev")
    source = source.replace("// @github          https://github.com/viraj-rgb", "// @github          https://github.com/menino-dev\n// @homepage        https://github.com/menino-dev/taskbar-pokemon")

    # Readme updates: Add attribution to jakobhoeg for vscode-pokemon & viraj-rgb for original mod
    readme_old = "# Taskbar Cat"
    readme_new = f"# Taskbar Pokémon ({display_name})\n\nA nostalgic pixel-art Pokémon companion that lives on the Windows 11 taskbar.\nBased on Taskbar Cat by viraj-rgb (MIT license).\nPokémon sprite assets from vscode-pokemon by jakobhoeg (MIT license)."
    source = source.replace(readme_old, readme_new)

    # Settings updates: default catName: display_name, seasonalHats: false
    source = source.replace("- catName: Mango", f"- catName: {display_name}")
    source = source.replace("$name: Cat's name", "$name: Pokémon's name")
    source = source.replace('.catName = L"Mango",', f'.catName = L"{display_name}",')
    source = source.replace("- seasonalHats: true", "- seasonalHats: false")
    source = source.replace(".seasonalHats = true,", ".seasonalHats = false,")

    # Disable seasonal hat overlays by default
    old_todays_hat = """cat::Hat TodaysHat(const CatWindow& c) {
    if (!c.settings.seasonalHats) {
        return cat::Hat::None;
    }
    SYSTEMTIME now;
    GetLocalTime(&now);
    int birthdayMonth = 0, birthdayDay = 0;
    if (Birthday(c) > 0 && LocalDay() - Birthday(c) >= 365) {
        cat::CivilMonthDay(Birthday(c), &birthdayMonth, &birthdayDay);
    }
    return cat::SeasonalHat(now.wMonth, now.wDay, birthdayMonth, birthdayDay);
}"""
    new_todays_hat = """cat::Hat TodaysHat(const CatWindow& c) {
    (void)c;
    return cat::Hat::None;
}"""
    assert old_todays_hat in source, "Could not find TodaysHat in source"
    source = source.replace(old_todays_hat, new_todays_hat)

    # Tooltip / action text updates
    cry_text = "pika!" if pokemon == "pikachu" else f"{pokemon}!"
    source = source.replace('case Activity::Purr: return L"purr";', 'case Activity::Purr: return L"happy";')
    source = source.replace('case Activity::Meow: return L"meow";', f'case Activity::Meow: return L"{cry_text}";')
    source = source.replace('const wchar_t* name = c.settings.catName[0] ? c.settings.catName : L"The cat";',
                            'const wchar_t* name = c.settings.catName[0] ? c.settings.catName : L"The Pokémon";')

    # Window titles / classes
    source = source.replace('L"Taskbar Cat"', 'L"Taskbar Pokémon"')
    source = source.replace('L"Taskbar Cat Toy"', 'L"Taskbar Pokémon Toy"')
    source = source.replace('L"TaskbarCatWindowClass"', 'L"TaskbarPokemonWindowClass"')
    source = source.replace('L"TaskbarCatToyWindowClass"', 'L"TaskbarPokemonToyWindowClass"')

    # Update DecodeRleFrame to 2-byte run implementation
    old_decoder = """inline bool DecodeRleFrame(const uint8_t* data, size_t size,
                           const uint32_t* palette, size_t paletteSize,
                           uint32_t* out, int pixelCount) {
    int filled = 0;
    for (size_t i = 0; i < size; i++) {
        size_t index = data[i] & 0x0F;
        int run = (data[i] >> 4) + 1;
        if (index >= paletteSize || filled + run > pixelCount) {
            return false;
        }
        uint32_t pixel = PremultiplyArgb(palette[index]);
        for (int j = 0; j < run; j++) {
            out[filled++] = pixel;
        }
    }
    return filled == pixelCount;
}"""

    new_decoder = """inline bool DecodeRleFrame(const uint8_t* data, size_t size,
                           const uint32_t* palette, size_t paletteSize,
                           uint32_t* out, int pixelCount) {
    if (size % 2 != 0) {
        return false;
    }
    int filled = 0;
    for (size_t i = 0; i < size; i += 2) {
        int run = (int)data[i] + 1;
        size_t index = data[i + 1];
        if (index >= paletteSize || filled + run > pixelCount) {
            return false;
        }
        uint32_t pixel = PremultiplyArgb(palette[index]);
        for (int j = 0; j < run; j++) {
            out[filled++] = pixel;
        }
    }
    return filled == pixelCount;
}"""
    assert old_decoder in source, "Could not find original DecodeRleFrame in source"
    source = source.replace(old_decoder, new_decoder)

    # Replace GENERATED SPRITES block
    start = source.find(BEGIN)
    end = source.find(END)
    assert start >= 0 and end >= 0, "Markers not found in source"
    end += len(END)
    source = source[:start] + block + source[end:]

    MOD_OUT.write_text(source, encoding="utf-8", newline="\n")
    print(f"Wrote {MOD_OUT.name} for {display_name} ({'Shiny' if shiny else 'Default'}): {len(processed)} frames, {len(palette)} palette entries")


def main():
    parser = argparse.ArgumentParser(description="Generate Taskbar Pokemon mod")
    parser.add_argument("--pokemon", default="pikachu", help="Pokemon species (default: pikachu)")
    parser.add_argument("--shiny", action="store_true", help="Use shiny variant")
    args = parser.parse_args()

    generate_taskbar_pokemon(args.pokemon, args.shiny)


if __name__ == "__main__":
    main()
