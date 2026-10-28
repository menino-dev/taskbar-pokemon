"""Generate complete all-in-one Taskbar Pokemon mod with all 634 Pokemon across Gen 1-5.
Includes YAML settings for selecting Generation, per-Gen dropdowns, and custom name override.
"""

from pathlib import Path
import json
import re
import sys
from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "upstream-pokemon" / "media"
UPSTREAM = ROOT / "upstream"
FRAMES_DIR = ROOT / "tools" / "out" / "pokemon_frames"
BASE_MOD = ROOT / "taskbar-pokemon.single.wh.cpp"
MOD_OUT = ROOT / "taskbar-pokemon.wh.cpp"
CELL = 32

GEN_NAMES = {
    "gen1": "Gen 1: Kanto (153 Pokémon)",
    "gen2": "Gen 2: Johto (132 Pokémon)",
    "gen3": "Gen 3: Hoenn (138 Pokémon)",
    "gen4": "Gen 4: Sinnoh (142 Pokémon)",
    "gen5": "Gen 5: Unova (69 Pokémon)",
}

GEN_DEFAULTS = {
    1: "pikachu",
    2: "chikorita",
    3: "treecko",
    4: "turtwig",
    5: "victini"
}


def norm_cell(f):
    if f.size == (64, 64):
        bbox = f.getbbox()
        c = f.crop(bbox) if bbox else f
        cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        if c.width > CELL or c.height > CELL:
            c.thumbnail((CELL, CELL), Image.NEAREST)
        cell.paste(c, ((CELL - c.width) // 2, CELL - c.height))
        return cell
    return f


def pick_two_frames(frames):
    f0 = frames[0]
    b0 = f0.tobytes()
    best_f = None
    max_diff = 0
    for f in frames[1:]:
        bf = f.tobytes()
        diff = sum(1 for a, b in zip(b0, bf) if a != b)
        if diff > max_diff:
            max_diff = diff
            best_f = f
    return f0, (best_f if best_f is not None else f0)


def process_single_pokemon(poke_dir, name, gen_num):
    w_p = poke_dir / "default_walk_8fps.gif"
    i_p = poke_dir / "default_idle_8fps.gif"
    if not w_p.exists() or not i_p.exists():
        return None

    w_frames = [norm_cell(f.copy().convert("RGBA")) for f in ImageSequence.Iterator(Image.open(w_p))]
    i_frames = [norm_cell(f.copy().convert("RGBA")) for f in ImageSequence.Iterator(Image.open(i_p))]

    w0, w1 = pick_two_frames(w_frames)
    i0, i1 = pick_two_frames(i_frames)
    raw_frames = [w0, w1, i0, i1]

    # Grounding: find max_y across all 4 frames
    max_y = 0
    for f in raw_frames:
        for y in range(CELL):
            for x in range(CELL):
                if f.getpixel((x, y))[3] > 0 and y > max_y:
                    max_y = y
    shift_y = 31 - max_y if max_y < 31 else 0

    grounded_frames = []
    for f in raw_frames:
        cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        for y in range(CELL):
            for x in range(CELL):
                p = f.getpixel((x, y))
                if p[3] > 0 and y + shift_y < CELL:
                    cell.putpixel((x, y + shift_y), p)
        grounded_frames.append(cell)

    # Build local palette (index 0 is transparent)
    pal = [(0, 0, 0, 0)]
    seen = {(0, 0, 0, 0): 0}
    rle_bytes = bytearray()
    frame_offsets = []

    for f in grounded_frames:
        frame_offsets.append(len(rle_bytes))
        indices = []
        for y in range(CELL):
            for x in range(CELL):
                p = f.getpixel((x, y))
                if p[3] > 0:
                    if p not in seen:
                        seen[p] = len(pal)
                        pal.append(p)
                    indices.append(seen[p])
                else:
                    indices.append(0)

        # 2-byte RLE encode
        i = 0
        n = len(indices)
        while i < n:
            idx = indices[i]
            run = 1
            while i + run < n and run < 256 and indices[i + run] == idx:
                run += 1
            rle_bytes.append(run - 1)
            rle_bytes.append(idx)
            i += run

    frame_offsets.append(len(rle_bytes))

    # Calculate head anchor from idle frame 0
    pts = [(x, y) for y in range(CELL) for x in range(CELL) if grounded_frames[2].getpixel((x, y))[3] > 0]
    min_y = min(y for x, y in pts) if pts else 12
    head_pts = [x for x, y in pts if y <= min_y + 2]
    anchor_x = round(sum(head_pts) / len(head_pts)) if head_pts else 16
    if anchor_x < 16:
        anchor_x = 16
    anchor_y = min_y

    disp_name = name.replace("_", " ").title()

    return {
        "id": name.lower(),
        "name": disp_name,
        "gen": gen_num,
        "palette": pal,
        "rle": bytes(rle_bytes),
        "frame_offsets": frame_offsets,
        "anchor_x": anchor_x,
        "anchor_y": anchor_y,
    }


def main():
    print("Collecting and processing all Pokemon from Gen 1 to Gen 5...")
    all_pokes = []
    gen_pokes = {1: [], 2: [], 3: [], 4: [], 5: []}

    for gen_num, gen_key in enumerate(["gen1", "gen2", "gen3", "gen4", "gen5"], 1):
        gdir = MEDIA / gen_key
        if not gdir.exists():
            continue
        for poke in sorted(gdir.iterdir()):
            if not poke.is_dir():
                continue
            data = process_single_pokemon(poke, poke.name, gen_num)
            if data:
                all_pokes.append(data)
                gen_pokes[gen_num].append(data)

    print(f"Total processed Pokemon: {len(all_pokes)}")

    # Ensure Pikachu is at index 0 for default
    pika_idx = next(i for i, p in enumerate(all_pokes) if p["id"] == "pikachu")
    if pika_idx != 0:
        all_pokes.insert(0, all_pokes.pop(pika_idx))

    # Build concatenated palettes and RLE data
    all_palettes = []
    all_rle = bytearray()
    species_entries = []

    for p in all_pokes:
        pal_off = len(all_palettes)
        all_palettes.extend(p["palette"])

        rle_off = len(all_rle)
        all_rle.extend(p["rle"])

        species_entries.append({
            "id": p["id"],
            "name": p["name"],
            "gen": p["gen"],
            "pal_size": len(p["palette"]),
            "pal_offset": pal_off,
            "rle_offset": rle_off,
            "rle_size": len(p["rle"]),
            "frame_offsets": p["frame_offsets"],
            "anchor_x": p["anchor_x"],
            "anchor_y": p["anchor_y"]
        })

    print(f"Total Palettes size: {len(all_palettes)} colors ({len(all_palettes) * 4 / 1024:.1f} KB)")
    print(f"Total RLE data size: {len(all_rle)} bytes ({len(all_rle) / 1024:.1f} KB)")

    # 1. Generate YAML Settings
    yaml_lines = [
        "- pokemonCount: \"1\"",
        "  $name: \"Number of Pokémon\"",
        "  $description: \"How many Pokémon companions to show on the taskbar (1 to 6)\"",
        "  $options:",
        "  - \"1\": \"1 Pokémon\"",
        "  - \"2\": \"2 Pokémon\"",
        "  - \"3\": \"3 Pokémon\"",
        "  - \"4\": \"4 Pokémon\"",
        "  - \"5\": \"5 Pokémon\"",
        "  - \"6\": \"6 Pokémon (Full Party)\"",
        "",
        "- pokemonGen: \"1\"",
        "  $name: \"Pokémon 1 - Generation\"",
        "  $description: \"Generation of Pokémon 1 to select from (Gen 1 to Gen 5)\"",
        "  $options:"
    ]
    for g_num in range(1, 6):
        yaml_lines.append(f'  - "{g_num}": "{GEN_NAMES[f"gen{g_num}"]}"')

    for g_num in range(1, 6):
        def_poke = GEN_DEFAULTS.get(g_num, gen_pokes[g_num][0]['id'])
        yaml_lines.append(f"- pokemonGen{g_num}: {def_poke}")
        yaml_lines.append(f'  $name: "Pokémon 1 - Gen {g_num} Selection"')
        yaml_lines.append(f'  $description: "Active for Pokémon 1 when Generation {g_num} is selected"')
        yaml_lines.append("  $options:")
        for p in gen_pokes[g_num]:
            yaml_lines.append(f"  - {p['id']}: \"{p['name']}\"")

    yaml_lines.extend([
        "- pokemonCustom: \"\"",
        "  $name: \"Pokémon 1 - Custom Name or ID\"",
        "  $description: \"Type any Pokémon name or ID to override Pokémon 1 (e.g. lucario, charizard, pikachu)\"",
        "- catName: \"\"",
        "  $name: \"Pokémon 1 - Custom Nickname\"",
        "  $description: \"Optional custom nickname for Pokémon 1 (leave empty to show species name)\"",
        "",
        "- pokemon2: \"charmander\"",
        "  $name: \"Pokémon 2 - Name or ID\"",
        "  $description: \"Active when count >= 2. Name or ID of Pokémon 2 (e.g. charmander, cyndaquil, torchic, chimchar, snivy, etc.)\"",
        "- pokemon2_name: \"\"",
        "  $name: \"Pokémon 2 - Nickname\"",
        "  $description: \"Optional nickname for Pokémon 2\"",
        "",
        "- pokemon3: \"squirtle\"",
        "  $name: \"Pokémon 3 - Name or ID\"",
        "  $description: \"Active when count >= 3. Name or ID of Pokémon 3 (e.g. squirtle, totodile, mudkip, piplup, oshawott, etc.)\"",
        "- pokemon3_name: \"\"",
        "  $name: \"Pokémon 3 - Nickname\"",
        "  $description: \"Optional nickname for Pokémon 3\"",
        "",
        "- pokemon4: \"bulbasaur\"",
        "  $name: \"Pokémon 4 - Name or ID\"",
        "  $description: \"Active when count >= 4. Name or ID of Pokémon 4 (e.g. bulbasaur, chikorita, treecko, turtwig, etc.)\"",
        "- pokemon4_name: \"\"",
        "  $name: \"Pokémon 4 - Nickname\"",
        "  $description: \"Optional nickname for Pokémon 4\"",
        "",
        "- pokemon5: \"eevee\"",
        "  $name: \"Pokémon 5 - Name or ID\"",
        "  $description: \"Active when count >= 5. Name or ID of Pokémon 5 (e.g. eevee, gengar, lucario, snorlax, etc.)\"",
        "- pokemon5_name: \"\"",
        "  $name: \"Pokémon 5 - Nickname\"",
        "  $description: \"Optional nickname for Pokémon 5\"",
        "",
        "- pokemon6: \"mew\"",
        "  $name: \"Pokémon 6 - Name or ID\"",
        "  $description: \"Active when count >= 6. Name or ID of Pokémon 6 (e.g. mew, celebi, jirachi, victini, etc.)\"",
        "- pokemon6_name: \"\"",
        "  $name: \"Pokémon 6 - Nickname\"",
        "  $description: \"Optional nickname for Pokémon 6\"",
        "- birthday: \"\"",
        "  $name: \"Birthday (YYYY-MM-DD)\"",
        "  $description: \"Day 1 of the Pokémon's life. Leave empty to use the day the mod first ran.\"",
        "- catSize: auto",
        "  $name: \"Pokémon size\"",
        "  $options:",
        "  - auto: Automatic (follows display scaling)",
        "  - \"1\": Small",
        "  - \"2\": Medium",
        "  - \"3\": Large",
        "  - \"4\": Huge",
        "- activityLevel: normal",
        "  $name: \"Activity level\"",
        "  $options:",
        "  - lazy: Lazy (naps a lot)",
        "  - normal: Normal",
        "  - hyper: Hyper (zoomies)",
        "- walkSpeed: 100",
        "  $name: \"Walk speed (%)\"",
        "  $description: \"25 to 400\"",
        "- roamZone: avoidTray",
        "  $name: \"Where the Pokémon can go\"",
        "  $options:",
        "  - avoidTray: The taskbar, except the system tray",
        "  - whole: The whole taskbar",
        "  - custom: Between the margins below",
        "- leftMargin: 0",
        "  $name: \"Left margin (px)\"",
        "  $description: \"Only used with Between the margins below\"",
        "- rightMargin: 0",
        "  $name: \"Right margin (px)\"",
        "  $description: \"Only used with Between the margins below\"",
        "- idleNapMinutes: 5",
        "  $name: \"Nap when I'm away for (minutes)\"",
        "  $description: \"0 = never\"",
        "- sleepierAtNight: true",
        "  $name: \"Sleepier at night (11 pm to 7 am)\"",
        "- reactToWindows: true",
        "  $name: \"React to new windows and flashing taskbar buttons\"",
        "- chaseCursor: true",
        "  $name: \"Pounce on a fast-moving cursor\"",
        "- toys: true",
        "  $name: \"Pokéball toy visits and gifts\"",
        "  $description: \"The Pokéball from the right-click menu works either way\"",
        "- danceToMusic: true",
        "  $name: \"Dance when music is playing\"",
        "  $description: \"Any sound counts, including videos, calls and games\"",
        "- mealtimes: true",
        "  $name: \"Mealtimes (asks for a treat around 8:00 and 19:00)\"",
        "- seasonalHats: false",
        "  $name: \"Seasonal hats\"",
        "- sounds: false",
        "  $name: \"Sounds (bips/cries)\"",
        "  $description: \"Quiet during Do Not Disturb and fullscreen apps\"",
        "- soundVolume: 50",
        "  $name: \"Sound volume (%)\"",
        "- showEffects: true",
        "  $name: \"Show hearts and other effects\"",
        "- ghost: false",
        "  $name: \"Ghost Pokémon\"",
        "  $description: \"Clicks pass straight through the Pokémon to the taskbar\"",
        "- stayStill: false",
        "  $name: \"Stay still\"",
        "  $description: \"Keep the Pokémon in one place\"",
    ])
    settings_yaml = "\n".join(yaml_lines)
    import yaml
    try:
        yaml.safe_load(settings_yaml)
        print("YAML Settings validation: SUCCESS (100% valid YAML)")
    except Exception as e:
        print(f"YAML Settings validation failed: {e}")
        raise

    # 2. Generate C++ Data Block
    cpp_lines = [
        "// BEGIN GENERATED POKEMON BANK (tools/generate_all_pokemon_mod.py)",
        "namespace pokemon_bank {",
        "",
        "struct PokemonSpecies {",
        "    const char* id;",
        "    const char* name;",
        "    uint8_t gen;",
        "    uint8_t paletteSize;",
        "    uint32_t paletteOffset;",
        "    uint32_t rleOffset;",
        "    uint16_t rleSize;",
        "    uint16_t frameOffsets[5];",
        "    uint8_t anchorX;",
        "    uint8_t anchorY;",
        "};",
        "",
        f"constexpr int kSpeciesCount = {len(species_entries)};",
        "constexpr PokemonSpecies kSpecies[kSpeciesCount] = {"
    ]

    for sp in species_entries:
        fo_str = ", ".join(str(o) for o in sp["frame_offsets"])
        cpp_lines.append(f'    {{"{sp["id"]}", "{sp["name"]}", {sp["gen"]}, {sp["pal_size"]}, {sp["pal_offset"]}, {sp["rle_offset"]}, {sp["rle_size"]}, {{{fo_str}}}, {sp["anchor_x"]}, {sp["anchor_y"]}}},')
    cpp_lines.append("};")
    cpp_lines.append("")

    # Concatenated Palettes
    cpp_lines.append(f"constexpr uint32_t kBankPalettes[{len(all_palettes)}] = {{")
    for i in range(0, len(all_palettes), 8):
        chunk = all_palettes[i:i + 8]
        hex_chunk = []
        for p in chunk:
            argb = (p[3] << 24) | (p[0] << 16) | (p[1] << 8) | p[2]
            hex_chunk.append(f"0x{argb:08X}")
        cpp_lines.append("    " + ", ".join(hex_chunk) + ",")
    cpp_lines.append("};")
    cpp_lines.append("")

    # Concatenated RLE Data
    cpp_lines.append(f"constexpr uint8_t kBankRleData[{len(all_rle)}] = {{")
    for i in range(0, len(all_rle), 32):
        chunk = all_rle[i:i + 32]
        cpp_lines.append("    " + ", ".join(f"0x{b:02X}" for b in chunk) + ",")
    cpp_lines.append("};")
    cpp_lines.append("")
    cpp_lines.append("}  // namespace pokemon_bank")
    cpp_lines.append("// END GENERATED POKEMON BANK\n")

    bank_block = "\n".join(cpp_lines)

    # 3. Read base code
    code = BASE_MOD.read_text(encoding="utf-8")

    # Replace Settings block
    start_settings = code.find("// ==WindhawkModSettings==\n/*")
    end_settings = code.find("*/\n// ==/WindhawkModSettings==", start_settings)
    assert start_settings >= 0 and end_settings >= 0, "Could not find WindhawkModSettings block"
    end_settings += len("*/\n// ==/WindhawkModSettings==")
    code = code[:start_settings] + f"// ==WindhawkModSettings==\n/*\n{settings_yaml}\n*/\n// ==/WindhawkModSettings==" + code[end_settings:]

    # Inject Pokemon Bank block right before GENERATED SPRITES
    sprites_idx = code.find("// BEGIN GENERATED SPRITES")
    assert sprites_idx >= 0, "Could not find BEGIN GENERATED SPRITES"
    code = code[:sprites_idx] + bank_block + "\n" + code[sprites_idx:]

    # Replace kFrameAnchors to make it mutable
    old_anchors = "constexpr cat::Anchor kFrameAnchors[kFrameCount] = {"
    new_anchors = "cat::Anchor kFrameAnchors[kFrameCount] = {"
    assert old_anchors in code, "Could not find kFrameAnchors definition"
    code = code.replace(old_anchors, new_anchors)

    # Replace struct Settings
    old_struct = """struct Settings {
    wchar_t catName[64];
    int birthday;  // days since 1970-01-01, 0 = the day the mod first ran
    int size;  // 0 = auto
    engine::ActivityLevel activityLevel;
    int walkSpeedPercent;
    cat::RoamZone roamZone;
    int leftMargin;
    int rightMargin;
    int idleNapMinutes;
    bool sleepierAtNight;
    bool reactToWindows;
    bool chaseCursor;
    bool toys;
    bool danceToMusic;
    bool mealtimes;
    bool seasonalHats;
    bool sounds;
    int soundVolume;
    bool showEffects;
    bool ghost;
    bool stayStill;
};"""

    new_struct = """struct Settings {
    int pokemonCount; // 1 to 6
    int gen;  // 1 to 5
    wchar_t genPokemon[6][64];  // gen 1..5
    wchar_t customPokemon[64];
    wchar_t catName[64];
    wchar_t extraPokemon[5][64];    // slots 2..6 species name or ID
    wchar_t extraNicknames[5][64];  // slots 2..6 nicknames
    int birthday;  // days since 1970-01-01, 0 = the day the mod first ran
    int size;  // 0 = auto
    engine::ActivityLevel activityLevel;
    int walkSpeedPercent;
    cat::RoamZone roamZone;
    int leftMargin;
    int rightMargin;
    int idleNapMinutes;
    bool sleepierAtNight;
    bool reactToWindows;
    bool chaseCursor;
    bool toys;
    bool danceToMusic;
    bool mealtimes;
    bool seasonalHats;
    bool sounds;
    int soundVolume;
    bool showEffects;
    bool ghost;
    bool stayStill;
};"""
    assert old_struct in code, "Could not find struct Settings"
    code = code.replace(old_struct, new_struct)

    # Replace kDefaultSettings
    old_def = """constexpr Settings kDefaultSettings = {
    .catName = L"Pikachu",
    .birthday = 0,
    .size = 0,
    .activityLevel = engine::ActivityLevel::Normal,
    .walkSpeedPercent = 100,
    .roamZone = cat::RoamZone::AvoidTray,
    .leftMargin = 0,
    .rightMargin = 0,
    .idleNapMinutes = engine::kIdleNapSeconds / 60,
    .sleepierAtNight = true,
    .reactToWindows = true,
    .chaseCursor = true,
    .toys = true,
    .danceToMusic = true,
    .mealtimes = true,
    .seasonalHats = false,
    .sounds = false,
    .soundVolume = 50,
    .showEffects = true,
    .ghost = false,
    .stayStill = false,
};"""

    new_def = """constexpr Settings kDefaultSettings = {
    .pokemonCount = 1,
    .gen = 1,
    .genPokemon = {{}, L"pikachu", L"chikorita", L"treecko", L"turtwig", L"victini"},
    .customPokemon = L"",
    .catName = L"",
    .extraPokemon = {L"charmander", L"squirtle", L"bulbasaur", L"eevee", L"mew"},
    .extraNicknames = {L"", L"", L"", L"", L""},
    .birthday = 0,
    .size = 0,
    .activityLevel = engine::ActivityLevel::Normal,
    .walkSpeedPercent = 100,
    .roamZone = cat::RoamZone::AvoidTray,
    .leftMargin = 0,
    .rightMargin = 0,
    .idleNapMinutes = engine::kIdleNapSeconds / 60,
    .sleepierAtNight = true,
    .reactToWindows = true,
    .chaseCursor = true,
    .toys = true,
    .danceToMusic = true,
    .mealtimes = true,
    .seasonalHats = false,
    .sounds = false,
    .soundVolume = 50,
    .showEffects = true,
    .ghost = false,
    .stayStill = false,
};"""
    assert old_def in code, "Could not find kDefaultSettings"
    code = code.replace(old_def, new_def)

    # Dynamic Pokemon Loader functions (placed after std::atomic<HWND> g_hwnd{nullptr};)
    loader_functions = """
// --- dynamic pokemon loader --------------------------------------------------

constexpr int kMaxPokemon = 6;
CatWindow g_cats[kMaxPokemon];
int g_activePokemonCount = 1;

CatWindow* FindCatByHwnd(HWND hwnd) {
    if (!hwnd) return nullptr;
    CatWindow* c = (CatWindow*)GetWindowLongPtr(hwnd, GWLP_USERDATA);
    if (c) return c;
    for (int i = 0; i < kMaxPokemon; i++) {
        if (g_cats[i].hwnd == hwnd || g_cats[i].toy.hwnd == hwnd) {
            SetWindowLongPtr(hwnd, GWLP_USERDATA, (LONG_PTR)&g_cats[i]);
            return &g_cats[i];
        }
    }
    return nullptr;
}

inline const wchar_t* GetPokemonKeyForSlot(const Settings& s, int slotIndex) {
    if (slotIndex == 0) {
        if (s.customPokemon[0]) return s.customPokemon;
        if (s.gen >= 1 && s.gen <= 5 && s.genPokemon[s.gen][0]) {
            return s.genPokemon[s.gen];
        }
        return L"pikachu";
    }
    int extraIdx = slotIndex - 1;
    if (extraIdx >= 0 && extraIdx < 5) {
        if (s.extraPokemon[extraIdx][0]) return s.extraPokemon[extraIdx];
        const wchar_t* const kDefaults[5] = {L"charmander", L"squirtle", L"bulbasaur", L"eevee", L"mew"};
        return kDefaults[extraIdx];
    }
    return L"pikachu";
}

inline const wchar_t* GetPokemonNicknameForSlot(const Settings& s, int slotIndex) {
    if (slotIndex == 0) {
        return s.catName;
    }
    int extraIdx = slotIndex - 1;
    if (extraIdx >= 0 && extraIdx < 5) {
        return s.extraNicknames[extraIdx];
    }
    return L"";
}

[[maybe_unused]] inline const wchar_t* GetCurrentPokemonKey(const Settings& s) {
    return GetPokemonKeyForSlot(s, 0);
}

static void NormalizeName(const char* in, char* out, size_t outSize) {
    size_t o = 0;
    for (size_t i = 0; in[i] && o + 1 < outSize; i++) {
        char ch = (char)tolower((unsigned char)in[i]);
        if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9')) {
            out[o++] = ch;
        }
    }
    out[o] = '\\0';
}

static void NormalizeWideName(const wchar_t* in, char* out, size_t outSize) {
    size_t o = 0;
    for (size_t i = 0; in[i] && o + 1 < outSize; i++) {
        wchar_t ch = towlower(in[i]);
        if ((ch >= L'a' && ch <= L'z') || (ch >= L'0' && ch <= L'9')) {
            out[o++] = (char)ch;
        }
    }
    out[o] = '\\0';
}

const pokemon_bank::PokemonSpecies* FindPokemonSpecies(const wchar_t* query) {
    if (!query || !query[0]) {
        return &pokemon_bank::kSpecies[0]; // Pikachu default
    }
    char normQuery[64] = {};
    NormalizeWideName(query, normQuery, sizeof(normQuery));
    if (!normQuery[0]) {
        return &pokemon_bank::kSpecies[0];
    }

    // 1. Normalized ID match
    for (int i = 0; i < pokemon_bank::kSpeciesCount; i++) {
        char normId[64] = {};
        NormalizeName(pokemon_bank::kSpecies[i].id, normId, sizeof(normId));
        if (strcmp(normId, normQuery) == 0) {
            return &pokemon_bank::kSpecies[i];
        }
    }

    // 2. Normalized display name match
    for (int i = 0; i < pokemon_bank::kSpeciesCount; i++) {
        char normName[64] = {};
        NormalizeName(pokemon_bank::kSpecies[i].name, normName, sizeof(normName));
        if (strcmp(normName, normQuery) == 0) {
            return &pokemon_bank::kSpecies[i];
        }
    }

    return &pokemon_bank::kSpecies[0];
}

void ApplyPokemonToAtlas(CatWindow& c, const pokemon_bank::PokemonSpecies* sp) {
    if (!sp) return;

    const uint32_t* pokePalette = pokemon_bank::kBankPalettes + sp->paletteOffset;

    uint32_t walk0[cat::kSpriteSize * cat::kSpriteSize] = {};
    uint32_t walk1[cat::kSpriteSize * cat::kSpriteSize] = {};
    uint32_t idle0[cat::kSpriteSize * cat::kSpriteSize] = {};
    uint32_t idle1[cat::kSpriteSize * cat::kSpriteSize] = {};

    const uint8_t* rle = pokemon_bank::kBankRleData + sp->rleOffset;
    cat::DecodeRleFrame(rle + sp->frameOffsets[0], sp->frameOffsets[1] - sp->frameOffsets[0],
                       pokePalette, sp->paletteSize, walk0, cat::kSpriteSize * cat::kSpriteSize);
    cat::DecodeRleFrame(rle + sp->frameOffsets[1], sp->frameOffsets[2] - sp->frameOffsets[1],
                       pokePalette, sp->paletteSize, walk1, cat::kSpriteSize * cat::kSpriteSize);
    cat::DecodeRleFrame(rle + sp->frameOffsets[2], sp->frameOffsets[3] - sp->frameOffsets[2],
                       pokePalette, sp->paletteSize, idle0, cat::kSpriteSize * cat::kSpriteSize);
    cat::DecodeRleFrame(rle + sp->frameOffsets[3], sp->frameOffsets[4] - sp->frameOffsets[3],
                       pokePalette, sp->paletteSize, idle1, cat::kSpriteSize * cat::kSpriteSize);

    auto copyFrame = [&](int targetFrame, const uint32_t* src) {
        memcpy(c.atlas[targetFrame], src, sizeof(uint32_t) * cat::kSpriteSize * cat::kSpriteSize);
    };

    copyFrame(0, walk0);
    copyFrame(1, walk1);
    copyFrame(2, idle0);
    copyFrame(3, idle1);
    copyFrame(4, idle1);
    copyFrame(5, idle0);
    copyFrame(6, idle1);
    copyFrame(7, idle0);
    copyFrame(8, idle1);
    copyFrame(9, idle0);
    copyFrame(10, idle0);
    copyFrame(11, walk0);
    copyFrame(12, walk1);
    copyFrame(13, walk1);
    copyFrame(14, idle0);
    copyFrame(15, idle1);
    copyFrame(16, idle1);
    copyFrame(17, idle0);
    copyFrame(18, walk1);
    copyFrame(19, walk1);
    copyFrame(20, idle1);
    copyFrame(21, walk1);
    copyFrame(26, walk0);
    copyFrame(27, idle0);
    copyFrame(28, idle1);
    copyFrame(29, idle0);
    copyFrame(30, walk0);
    copyFrame(31, idle1);
    copyFrame(32, idle0);
    copyFrame(33, walk0);
    copyFrame(34, walk1);
    copyFrame(37, walk0);
    copyFrame(38, walk1);

    // Synthesize 3-pose dance: esquerda (44), frontal (45), direita (46), frontal volta (47)
    int min_x = 32, max_x = -1;
    for (int y = 0; y < 32; y++) {
        for (int x = 0; x < 32; x++) {
            if (idle0[y * 32 + x] >> 24) {
                if (x < min_x) min_x = x;
                if (x > max_x) max_x = x;
            }
        }
    }
    if (min_x > max_x) { min_x = 0; max_x = 31; }
    int cx = (min_x + max_x) / 2;

    int dx_left = (min_x >= 1) ? 1 : 0;
    uint32_t danceLeft[cat::kSpriteSize * cat::kSpriteSize] = {};
    for (int y = 0; y < 32; y++) {
        for (int x = 0; x < 32; x++) {
            uint32_t p = idle0[y * 32 + x];
            if (p >> 24) {
                int nx = 2 * cx - x - dx_left;
                if (nx >= 0 && nx < 32) {
                    danceLeft[y * 32 + nx] = p;
                }
            }
        }
    }

    int dx_right = (max_x + 1 < 32) ? 1 : 0;
    uint32_t danceRight[cat::kSpriteSize * cat::kSpriteSize] = {};
    for (int y = 0; y < 32; y++) {
        for (int x = 0; x < 32; x++) {
            uint32_t p = idle0[y * 32 + x];
            if (p >> 24) {
                int nx = x + dx_right;
                if (nx >= 0 && nx < 32) {
                    danceRight[y * 32 + nx] = p;
                }
            }
        }
    }

    copyFrame(44, danceLeft);   // 1. esquerda
    copyFrame(45, idle0);       // 2. frontal
    copyFrame(46, danceRight);  // 3. direita
    copyFrame(47, idle0);       // 4. frontal volta

    // Initialize per-window head anchors
    memcpy(c.anchors, sprites::kFrameAnchors, sizeof(c.anchors));

    for (int i = 0; i < sprites::kFrameCount; i++) {
        if (i == 18 || i == 19 || i == 20) {
            c.anchors[i].x = sp->anchorX;
            c.anchors[i].y = 31;
            c.anchors[i].upright = false;
        } else if (i == 44) {
            c.anchors[i].x = (uint8_t)(sp->anchorX > dx_left ? sp->anchorX - dx_left : sp->anchorX);
            c.anchors[i].y = sp->anchorY;
            c.anchors[i].upright = true;
        } else if (i == 46) {
            c.anchors[i].x = (uint8_t)(sp->anchorX + dx_right < 32 ? sp->anchorX + dx_right : sp->anchorX);
            c.anchors[i].y = sp->anchorY;
            c.anchors[i].upright = true;
        } else if (i < 22 || (i >= 26 && i <= 34) || (i >= 37 && i <= 38) || i == 45 || i == 47) {
            c.anchors[i].x = sp->anchorX;
            c.anchors[i].y = sp->anchorY;
            c.anchors[i].upright = true;
        }
    }
}

[[maybe_unused]] bool DecodeAtlas(CatWindow& c, const wchar_t* selectedKey) {
    // 1. Decode base atlas (effects, toys, default frames)
    for (int i = 0; i < sprites::kFrameCount; i++) {
        uint16_t begin = sprites::kFrameOffsets[i];
        uint16_t end = sprites::kFrameOffsets[i + 1];
        if (!cat::DecodeRleFrame(sprites::kFrameData + begin, end - begin,
                                 sprites::kPalette, std::size(sprites::kPalette),
                                 c.atlas[i],
                                 cat::kSpriteSize * cat::kSpriteSize)) {
            return false;
        }
    }

    // 2. Resolve selected Pokemon species
    const pokemon_bank::PokemonSpecies* sp = FindPokemonSpecies(selectedKey);
    ApplyPokemonToAtlas(c, sp);
    return true;
}

[[maybe_unused]] bool DecodeAtlas(CatWindow& c) {
    return DecodeAtlas(c, GetPokemonKeyForSlot(c.settings, c.index));
}
"""

    hook_anchor = "std::atomic<HWND> g_hwnd{nullptr};"
    assert hook_anchor in code, "Could not find g_hwnd anchor"
    code = code.replace(hook_anchor, hook_anchor + "\n" + loader_functions)

    # Replace single CatWindow g_cat; with comment (g_cats is declared in loader_functions)
    assert "CatWindow g_cat;" in code, "Could not find CatWindow g_cat; in code"
    code = code.replace("CatWindow g_cat;", "// (CatWindow g_cats[kMaxPokemon] declared in dynamic loader above)")

    # Replace ReadWindhawkSettings
    old_read = """[[maybe_unused]] Settings ReadWindhawkSettings() {
    Settings s = kDefaultSettings;
    auto name = WindhawkUtils::StringSetting::make(L"catName");
    wcsncpy(s.catName, name, std::size(s.catName) - 1);
    s.catName[std::size(s.catName) - 1] = L'\\0';
    s.birthday = cat::ParseDate(WindhawkUtils::StringSetting::make(L"birthday"));

    constexpr const wchar_t* kSizes[] = {L"auto", L"1", L"2", L"3", L"4"};
    s.size = ReadChoice(L"catSize", kSizes, 0);
    constexpr const wchar_t* kLevels[] = {L"lazy", L"normal", L"hyper"};
    s.activityLevel = (engine::ActivityLevel)ReadChoice(L"activityLevel", kLevels, 1);
    constexpr const wchar_t* kZones[] = {L"avoidTray", L"whole", L"custom"};
    s.roamZone = (cat::RoamZone)ReadChoice(L"roamZone", kZones, 0);

    s.walkSpeedPercent = ClampInt(Wh_GetIntSetting(L"walkSpeed"), 25, 400);
    s.leftMargin = ClampInt(Wh_GetIntSetting(L"leftMargin"), 0, 4000);
    s.rightMargin = ClampInt(Wh_GetIntSetting(L"rightMargin"), 0, 4000);
    s.idleNapMinutes = ClampInt(Wh_GetIntSetting(L"idleNapMinutes"), 0, 240);
    s.sleepierAtNight = Wh_GetIntSetting(L"sleepierAtNight") != 0;
    s.reactToWindows = Wh_GetIntSetting(L"reactToWindows") != 0;
    s.chaseCursor = Wh_GetIntSetting(L"chaseCursor") != 0;
    s.toys = Wh_GetIntSetting(L"toys") != 0;
    s.danceToMusic = Wh_GetIntSetting(L"danceToMusic") != 0;
    s.mealtimes = Wh_GetIntSetting(L"mealtimes") != 0;
    s.seasonalHats = Wh_GetIntSetting(L"seasonalHats") != 0;
    s.sounds = Wh_GetIntSetting(L"sounds") != 0;
    s.soundVolume = ClampInt(Wh_GetIntSetting(L"soundVolume"), 0, 100);
    s.showEffects = Wh_GetIntSetting(L"showEffects") != 0;
    s.ghost = Wh_GetIntSetting(L"ghost") != 0;
    s.stayStill = Wh_GetIntSetting(L"stayStill") != 0;
    return s;
}"""

    new_read = """[[maybe_unused]] Settings ReadWindhawkSettings() {
    Settings s = kDefaultSettings;

    constexpr const wchar_t* kCounts[] = {L"1", L"2", L"3", L"4", L"5", L"6"};
    s.pokemonCount = ReadChoice(L"pokemonCount", kCounts, 0) + 1;

    constexpr const wchar_t* kGens[] = {L"1", L"2", L"3", L"4", L"5"};
    s.gen = ReadChoice(L"pokemonGen", kGens, 0) + 1;

    for (int g = 1; g <= 5; g++) {
        wchar_t key[32];
        swprintf_s(key, L"pokemonGen%d", g);
        auto val = WindhawkUtils::StringSetting::make(key);
        wcsncpy(s.genPokemon[g], val, std::size(s.genPokemon[g]) - 1);
        s.genPokemon[g][std::size(s.genPokemon[g]) - 1] = L'\\0';
    }

    auto custom = WindhawkUtils::StringSetting::make(L"pokemonCustom");
    wcsncpy(s.customPokemon, custom, std::size(s.customPokemon) - 1);
    s.customPokemon[std::size(s.customPokemon) - 1] = L'\\0';

    auto name = WindhawkUtils::StringSetting::make(L"catName");
    wcsncpy(s.catName, name, std::size(s.catName) - 1);
    s.catName[std::size(s.catName) - 1] = L'\\0';

    const wchar_t* const kDefaultExtras[5] = {L"charmander", L"squirtle", L"bulbasaur", L"eevee", L"mew"};
    for (int i = 0; i < 5; i++) {
        wchar_t keySpec[32], keyNick[32];
        swprintf_s(keySpec, L"pokemon%d", i + 2);
        swprintf_s(keyNick, L"pokemon%d_name", i + 2);
        auto specVal = WindhawkUtils::StringSetting::make(keySpec);
        if (specVal && specVal[0]) {
            wcsncpy(s.extraPokemon[i], specVal, std::size(s.extraPokemon[i]) - 1);
            s.extraPokemon[i][std::size(s.extraPokemon[i]) - 1] = L'\\0';
        } else {
            wcsncpy(s.extraPokemon[i], kDefaultExtras[i], std::size(s.extraPokemon[i]) - 1);
            s.extraPokemon[i][std::size(s.extraPokemon[i]) - 1] = L'\\0';
        }
        auto nickVal = WindhawkUtils::StringSetting::make(keyNick);
        if (nickVal && nickVal[0]) {
            wcsncpy(s.extraNicknames[i], nickVal, std::size(s.extraNicknames[i]) - 1);
            s.extraNicknames[i][std::size(s.extraNicknames[i]) - 1] = L'\\0';
        } else {
            s.extraNicknames[i][0] = L'\\0';
        }
    }

    s.birthday = cat::ParseDate(WindhawkUtils::StringSetting::make(L"birthday"));

    constexpr const wchar_t* kSizes[] = {L"auto", L"1", L"2", L"3", L"4"};
    s.size = ReadChoice(L"catSize", kSizes, 0);
    constexpr const wchar_t* kLevels[] = {L"lazy", L"normal", L"hyper"};
    s.activityLevel = (engine::ActivityLevel)ReadChoice(L"activityLevel", kLevels, 1);
    constexpr const wchar_t* kZones[] = {L"avoidTray", L"whole", L"custom"};
    s.roamZone = (cat::RoamZone)ReadChoice(L"roamZone", kZones, 0);

    s.walkSpeedPercent = ClampInt(Wh_GetIntSetting(L"walkSpeed"), 25, 400);
    s.leftMargin = ClampInt(Wh_GetIntSetting(L"leftMargin"), 0, 4000);
    s.rightMargin = ClampInt(Wh_GetIntSetting(L"rightMargin"), 0, 4000);
    s.idleNapMinutes = ClampInt(Wh_GetIntSetting(L"idleNapMinutes"), 0, 240);
    s.sleepierAtNight = Wh_GetIntSetting(L"sleepierAtNight") != 0;
    s.reactToWindows = Wh_GetIntSetting(L"reactToWindows") != 0;
    s.chaseCursor = Wh_GetIntSetting(L"chaseCursor") != 0;
    s.toys = Wh_GetIntSetting(L"toys") != 0;
    s.danceToMusic = Wh_GetIntSetting(L"danceToMusic") != 0;
    s.mealtimes = Wh_GetIntSetting(L"mealtimes") != 0;
    s.seasonalHats = Wh_GetIntSetting(L"seasonalHats") != 0;
    s.sounds = Wh_GetIntSetting(L"sounds") != 0;
    s.soundVolume = ClampInt(Wh_GetIntSetting(L"soundVolume"), 0, 100);
    s.showEffects = Wh_GetIntSetting(L"showEffects") != 0;
    s.ghost = Wh_GetIntSetting(L"ghost") != 0;
    s.stayStill = Wh_GetIntSetting(L"stayStill") != 0;
    return s;
}"""
    assert old_read in code, "Could not find ReadWindhawkSettings"
    code = code.replace(old_read, new_read)

    # Update tooltip species name display
    old_tooltip_name = """const wchar_t* name = c.settings.catName[0] ? c.settings.catName : L"The Pokémon";"""
    new_tooltip_name = """    const wchar_t* selectedKey = GetPokemonKeyForSlot(c.settings, c.index);
    const pokemon_bank::PokemonSpecies* currentSp = FindPokemonSpecies(selectedKey);
    wchar_t defaultNameBuf[64] = {};
    if (currentSp && currentSp->name) {
        MultiByteToWideChar(CP_UTF8, 0, currentSp->name, -1, defaultNameBuf, 63);
    } else {
        wcscpy_s(defaultNameBuf, L"Pokémon");
    }
    const wchar_t* name = c.settings.catName[0] ? c.settings.catName : defaultNameBuf;"""
    assert old_tooltip_name in code, "Could not find tooltip name line"
    code = code.replace(old_tooltip_name, new_tooltip_name)

    # Replace the window procedures and CatThread with our multi-window manager
    start_wndproc = code.find("LRESULT CALLBACK CatWndProc(HWND hwnd, UINT msg, WPARAM wParam,")
    end_wndproc = code.find("\n}  // namespace\n\nBOOL Wh_ModInit()", start_wndproc)
    assert start_wndproc >= 0 and end_wndproc >= 0, "Could not find CatWndProc..CatThread block"

    multi_window_impl = """void ResetWindows(CatWindow& c);
bool CreateCatWindow(CatWindow& c, HINSTANCE instance);
void DestroyCatWindow(CatWindow& c);
void ReloadAllPokemon(HINSTANCE instance);

void ReattachAllToTaskbar() {
    HWND taskbar = FindOwnTaskbar();
    for (int i = 0; i < g_activePokemonCount; i++) {
        g_cats[i].taskbar = taskbar;
#ifndef WH_STANDALONE
        if (taskbar && g_cats[i].hwnd) {
            SetWindowLongPtr(g_cats[i].hwnd, GWLP_HWNDPARENT, (LONG_PTR)taskbar);
            if (g_cats[i].toy.hwnd) {
                SetWindowLongPtr(g_cats[i].toy.hwnd, GWLP_HWNDPARENT, (LONG_PTR)taskbar);
            }
        }
#endif
    }
    Wh_Log(L"Taskbar recreated, reattached %d Pokémon", g_activePokemonCount);
}

void BroadcastShellHook(WPARAM code, HWND window) {
    for (int i = 0; i < g_activePokemonCount; i++) {
        OnShellHook(g_cats[i], code, window);
    }
}

void BroadcastSessionChange(WPARAM change) {
    for (int i = 0; i < g_activePokemonCount; i++) {
        OnSessionChange(g_cats[i], change);
    }
}

void DestroyCatWindow(CatWindow& c) {
    if (c.hwnd) {
        if (c.toy.hwnd) {
            DestroyWindow(c.toy.hwnd);
            c.toy.hwnd = nullptr;
        }
        KillTimer(c.hwnd, kTimerId);
        KillTimer(c.hwnd, kSaveTimerId);
        if (c.index == 0) {
            DeregisterShellHookWindow(c.hwnd);
            WTSUnRegisterSessionNotification(c.hwnd);
        }
        HWND h = c.hwnd;
        c.hwnd = nullptr;
        DestroyWindow(h);
    }
    ResetWindows(c);
}

void ReloadAllPokemon(HINSTANCE instance) {
    Settings newSettings = LoadSettings();
    int newCount = ClampInt(newSettings.pokemonCount, 1, kMaxPokemon);

    for (int i = 0; i < kMaxPokemon; i++) {
        CatWindow& c = g_cats[i];
        c.index = i;
        if (i < newCount) {
            c.settings = newSettings;
            const wchar_t* specKey = GetPokemonKeyForSlot(newSettings, i);
            const wchar_t* nick = GetPokemonNicknameForSlot(newSettings, i);
            if (nick && nick[0]) {
                wcsncpy_s(c.settings.catName, nick, 63);
            } else {
                c.settings.catName[0] = L'\\0';
            }
            if (!c.hwnd) {
                c.taskbar = g_cats[0].taskbar ? g_cats[0].taskbar : FindOwnTaskbar();
                DecodeAtlas(c, specKey);
                double defaultX = 100.0 + (i * 200.0);
                c.state = LoadCat(GetTickCount64(), i, defaultX);
                LoadLifeEvents(c, i);
                BuildSounds(c);
                if (CreateCatWindow(c, instance)) {
                    SetTimerInterval(c, kActiveIntervalMs);
                }
            } else {
                DecodeAtlas(c, specKey);
                c.renderedFrame = -1;
                if (!c.settings.sounds) {
                    StopSounds(c);
                }
                BuildSounds(c);
                ApplyGhostStyle(c);
                c.scale = 0;
            }
        } else {
            if (c.hwnd) {
                SaveCat(c.state, i);
                StopSounds(c);
                DestroyCatWindow(c);
            }
        }
    }
    g_activePokemonCount = newCount;
    if (g_cats[0].hwnd) {
        g_hwnd = g_cats[0].hwnd;
    }
}

LRESULT CALLBACK CatWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    CatWindow* c = FindCatByHwnd(hwnd);
    if (!c) {
        return DefWindowProc(hwnd, msg, wParam, lParam);
    }
    if (c->taskbarCreatedMsg && msg == c->taskbarCreatedMsg) {
        ReattachAllToTaskbar();
        return 0;
    }
    if (c->shellHookMsg && msg == c->shellHookMsg) {
        BroadcastShellHook(wParam, (HWND)lParam);
        return 0;
    }
    switch (msg) {
        case WM_NOTIFY:
            return OnNotify(*c, (NMHDR*)lParam);
        case WM_WTSSESSION_CHANGE:
            BroadcastSessionChange(wParam);
            return 0;
        case WM_TIMER:
            if (wParam == kTimerId) {
                Tick(*c);
            } else if (wParam == kSaveTimerId) {
                SaveCat(c->state, c->index);
            }
            return 0;
        case WM_MOUSEMOVE:
            OnMouseMove(*c);
            return 0;
        case WM_MOUSELEAVE:
            c->mouse.hovered = false;
            c->mouse.trackingLeave = false;
            return 0;
        case WM_LBUTTONDOWN:
            OnButtonDown(*c);
            return 0;
        case WM_LBUTTONUP:
            OnButtonUp(*c);
            return 0;
        case WM_LBUTTONDBLCLK:
            OnDoubleClick(*c);
            return 0;
        case WM_CAPTURECHANGED:
            EndDrag(*c);
            return 0;
        case WM_RBUTTONUP:
            ShowMenu(*c);
            return 0;
        case WM_SETCURSOR:
            SetCursor(LoadCursor(nullptr, IDC_HAND));
            return TRUE;
        case WM_MOUSEACTIVATE:
            return MA_NOACTIVATE;
        case WM_APP_RELOAD_SETTINGS: {
            HINSTANCE instance = nullptr;
            GetModuleHandleEx(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                                  GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                              (LPCWSTR)&CatWndProc, &instance);
            ReloadAllPokemon(instance);
            return 0;
        }
        case WM_CLOSE:
            for (int i = 0; i < kMaxPokemon; i++) {
                if (g_cats[i].hwnd) {
                    SaveCat(g_cats[i].state, i);
                    DestroyCatWindow(g_cats[i]);
                }
            }
            PostQuitMessage(0);
            return 0;
        case WM_DESTROY:
            return 0;
    }
    return DefWindowProc(hwnd, msg, wParam, lParam);
}

LRESULT CALLBACK ToyWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    CatWindow* c = FindCatByHwnd(hwnd);
    if (!c) {
        return DefWindowProc(hwnd, msg, wParam, lParam);
    }
    switch (msg) {
        case WM_LBUTTONUP:
            SetState(*c, engine::OnToyClicked(c->state, c->world, GetTickCount64()));
            return 0;
        case WM_RBUTTONUP:
            ShowToyMenu(*c, hwnd);
            return 0;
        case WM_SETCURSOR:
            SetCursor(LoadCursor(nullptr, IDC_HAND));
            return TRUE;
        case WM_MOUSEACTIVATE:
            return MA_NOACTIVATE;
    }
    return DefWindowProc(hwnd, msg, wParam, lParam);
}

HWND WaitForTaskbar() {
    for (;;) {
        if (FindWindow(L"Shell_TrayWnd", nullptr)) {
            return FindOwnTaskbar();
        }
        if (WaitForSingleObject(g_stopEvent, kTaskbarPollMs) == WAIT_OBJECT_0) {
            return nullptr;
        }
    }
}

void ResetWindows(CatWindow& c) {
    FreeSurface(c.surface);
    FreeSurface(c.toy.surface);
    c.toy = ToyWindow();
    c.hwnd = nullptr;
    c.tooltip = nullptr;
    c.scale = 0;
    c.renderedFrame = -1;
    c.renderedEffect = {-1, 0, 0};
    c.visible = false;
    c.timerInterval = 0;
    c.mouse = MouseState();
}

bool CreateCatWindow(CatWindow& c, HINSTANCE instance) {
    DWORD exStyle = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
    HWND owner = c.taskbar;
#ifdef WH_STANDALONE
    exStyle |= WS_EX_TOPMOST;
    owner = nullptr;
#endif
    c.hwnd = CreateWindowEx(exStyle, kWindowClass, L"Taskbar Pokémon", WS_POPUP, 0,
                            0, 1, 1, owner, nullptr, instance, nullptr);
    if (!c.hwnd) {
        Wh_Log(L"CreateWindowEx failed: %u", GetLastError());
        return false;
    }
    SetWindowLongPtr(c.hwnd, GWLP_USERDATA, (LONG_PTR)&c);
    ApplyGhostStyle(c);
    c.shellHookMsg = RegisterWindowMessage(L"SHELLHOOK");
    if (c.index == 0) {
        if (!RegisterShellHookWindow(c.hwnd)) {
            Wh_Log(L"RegisterShellHookWindow failed: %u", GetLastError());
        }
        if (!WTSRegisterSessionNotification(c.hwnd, NOTIFY_FOR_THIS_SESSION)) {
            Wh_Log(L"WTSRegisterSessionNotification failed: %u", GetLastError());
        }
    }
    CreateTooltip(c, instance);
    SetTimer(c.hwnd, kSaveTimerId, kSaveIntervalMs, nullptr);
    c.toy.hwnd = CreateWindowEx(exStyle, kToyWindowClass, L"Taskbar Pokémon Toy", WS_POPUP, 0, 0,
                                1, 1, owner, nullptr, instance, nullptr);
    if (c.toy.hwnd) {
        SetWindowLongPtr(c.toy.hwnd, GWLP_USERDATA, (LONG_PTR)&c);
    } else {
        Wh_Log(L"Toy window creation failed: %u", GetLastError());
    }
    ApplyGhostStyle(c);
    return true;
}

DWORD WINAPI CatThread(LPVOID) {
    HWND taskbar = WaitForTaskbar();
    if (!taskbar) {
        Wh_Log(L"No taskbar owned by this process, Pokémon stay home");
        return 0;
    }

    HINSTANCE instance = nullptr;
    GetModuleHandleEx(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                          GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                      (LPCWSTR)&CatWndProc, &instance);
    WNDCLASSEX wc = {sizeof(wc)};
    wc.style = CS_DBLCLKS;
    wc.lpfnWndProc = CatWndProc;
    wc.hInstance = instance;
    wc.lpszClassName = kWindowClass;
    wc.hCursor = LoadCursor(nullptr, IDC_HAND);
    if (!RegisterClassEx(&wc)) {
        Wh_Log(L"RegisterClassEx failed: %u", GetLastError());
        return 0;
    }
    WNDCLASSEX toyClass = {sizeof(toyClass)};
    toyClass.lpfnWndProc = ToyWndProc;
    toyClass.hInstance = instance;
    toyClass.lpszClassName = kToyWindowClass;
    toyClass.hCursor = LoadCursor(nullptr, IDC_HAND);
    if (!RegisterClassEx(&toyClass)) {
        Wh_Log(L"RegisterClassEx (toy) failed: %u", GetLastError());
    }

    UINT taskbarCreatedMsg = RegisterWindowMessage(L"TaskbarCreated");
    for (int i = 0; i < kMaxPokemon; i++) {
        g_cats[i].taskbarCreatedMsg = taskbarCreatedMsg;
    }

    StartAudioWatcher();

    while (WaitForSingleObject(g_stopEvent, 0) != WAIT_OBJECT_0) {
        if (!taskbar && !(taskbar = WaitForTaskbar())) {
            break;
        }

        Settings settings = LoadSettings();
        int count = ClampInt(settings.pokemonCount, 1, kMaxPokemon);
        g_activePokemonCount = count;

        for (int i = 0; i < count; i++) {
            CatWindow& c = g_cats[i];
            c.index = i;
            c.taskbar = taskbar;
            c.settings = settings;
            const wchar_t* specKey = GetPokemonKeyForSlot(settings, i);
            const wchar_t* nick = GetPokemonNicknameForSlot(settings, i);
            if (nick && nick[0]) {
                wcsncpy_s(c.settings.catName, nick, 63);
            } else {
                c.settings.catName[0] = L'\\0';
            }
            DecodeAtlas(c, specKey);
            double defaultX = 100.0 + (i * 200.0);
            c.state = LoadCat(GetTickCount64(), i, defaultX);
            LoadLifeEvents(c, i);
            BuildSounds(c);
            if (!CreateCatWindow(c, instance)) {
                break;
            }
        }
        if (g_cats[0].hwnd) {
            g_hwnd = g_cats[0].hwnd;
        }
        if (WaitForSingleObject(g_stopEvent, 0) == WAIT_OBJECT_0) {
            for (int i = 0; i < count; i++) {
                if (g_cats[i].hwnd) DestroyCatWindow(g_cats[i]);
            }
        } else {
            for (int i = 0; i < count; i++) {
                if (g_cats[i].hwnd) SetTimerInterval(g_cats[i], kActiveIntervalMs);
            }
            Wh_Log(L"%d Pokémon window(s) created", count);
        }

        MSG msg;
        while (GetMessage(&msg, nullptr, 0, 0) > 0) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }

        g_hwnd = nullptr;
        for (int i = 0; i < kMaxPokemon; i++) {
            if (g_cats[i].hwnd) {
                SaveCat(g_cats[i].state, i);
                StopSounds(g_cats[i]);
                DestroyCatWindow(g_cats[i]);
            }
        }
        taskbar = nullptr;
    }

    for (int i = 0; i < kMaxPokemon; i++) {
        ForceStopSounds(g_cats[i]);
    }
    StopAudioWatcher();
    for (int i = 0; i < kMaxPokemon; i++) {
        FreeSurface(g_cats[i].surface);
        FreeSurface(g_cats[i].toy.surface);
    }
    UnregisterClass(kWindowClass, instance);
    UnregisterClass(kToyWindowClass, instance);
    for (int i = 0; i < kMaxPokemon; i++) {
        g_cats[i].~CatWindow();
        new (&g_cats[i]) CatWindow();
    }
    return 0;
}
"""
    code = code[:start_wndproc] + multi_window_impl + code[end_wndproc:]

    # Update StartDance to set s.dir = 1
    old_start_dance = """inline CatState StartDance(CatState s, const World& w, uint64_t now) {
    s = Enter(s, Activity::Dance, sprites::kDance, false, now);
    s.playbackPercent = DancePercent(w.beatMs);
    s.effect = Effect::Notes;
    s.effectStartMs = now;
    return s;
}"""

    new_start_dance = """inline CatState StartDance(CatState s, const World& w, uint64_t now) {
    s = Enter(s, Activity::Dance, sprites::kDance, false, now);
    s.dir = 1;
    s.playbackPercent = DancePercent(w.beatMs);
    s.effect = Effect::Notes;
    s.effectStartMs = now;
    return s;
}"""
    assert old_start_dance in code, "Could not find StartDance"
    code = code.replace(old_start_dance, new_start_dance)

    # Update mod description
    code = code.replace(
        "A nostalgic pixel-art Pokémon companion (Pikachu) that lives on your Windows 11 taskbar",
        "A nostalgic pixel-art Pokémon companion (600+ Pokémon across Gen 1 to 5) that lives on your Windows 11 taskbar"
    )

    MOD_OUT.write_text(code, encoding="utf-8", newline="\n")
    print(f"Generated complete all-in-one mod in {MOD_OUT} ({MOD_OUT.stat().st_size / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    main()
