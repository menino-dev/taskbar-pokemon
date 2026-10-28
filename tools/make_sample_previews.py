from PIL import Image
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = Path(r"C:\Users\Menin\.gemini\antigravity\brain\62667122-f867-45b2-8caa-9180da6e7ffa")
CELL = 32
SCALE = 4

cpp = (ROOT / "taskbar-pokemon.wh.cpp").read_text(encoding="utf-8")

species = {}
for m in re.finditer(r'\{"([^"]+)",\s*"([^"]+)",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*\{([^}]+)\},\s*(\d+),\s*(\d+)\}', cpp):
    sid, sname, gen, ps, po, ro, rs, fo, ax, ay = m.groups()
    offsets = [int(x.strip()) for x in fo.split(",") if x.strip()]
    species[sid] = {
        "name": sname, "pal_size": int(ps), "pal_offset": int(po),
        "rle_offset": int(ro), "rle_size": int(rs), "offsets": offsets
    }

m_pal = re.search(r"constexpr uint32_t kBankPalettes\[\d+\] = \{([^}]+)\};", cpp, re.DOTALL)
pal_hex = re.findall(r"0x([0-9A-Fa-f]{8})", m_pal.group(1))
palettes = [int(h, 16) for h in pal_hex]

m_rle = re.search(r"constexpr uint8_t kBankRleData\[\d+\] = \{([^}]+)\};", cpp, re.DOTALL)
rle_hex = re.findall(r"0x([0-9A-Fa-f]{2})", m_rle.group(1))
rle_data = bytes([int(h, 16) for h in rle_hex])

def decode_frame(rle_slice, pal_slice):
    out = []
    i = 0
    n = len(rle_slice)
    while i < n:
        run = rle_slice[i] + 1
        idx = rle_slice[i+1]
        c = pal_slice[idx]
        a = (c >> 24) & 0xFF
        r = (c >> 16) & 0xFF
        g = (c >> 8) & 0xFF
        b = c & 0xFF
        out.extend([(r, g, b, a)] * run)
        i += 2
    return out

sample_species = ["charmander", "bulbasaur", "lucario", "gengar"]
for sid in sample_species:
    sp = species[sid]
    rle_sp = rle_data[sp["rle_offset"]:sp["rle_offset"] + sp["rle_size"]]
    pal_sp = palettes[sp["pal_offset"]:sp["pal_offset"] + sp["pal_size"]]
    
    # decode walk frames: 0 and 1
    w0_px = decode_frame(rle_sp[sp["offsets"][0]:sp["offsets"][1]], pal_sp)
    w1_px = decode_frame(rle_sp[sp["offsets"][1]:sp["offsets"][2]], pal_sp)
    
    img0 = Image.new("RGBA", (CELL, CELL))
    img0.putdata(w0_px)
    img1 = Image.new("RGBA", (CELL, CELL))
    img1.putdata(w1_px)
    
    # Scale 4x nearest neighbor
    img0_4x = img0.resize((CELL * SCALE, CELL * SCALE), Image.NEAREST)
    img1_4x = img1.resize((CELL * SCALE, CELL * SCALE), Image.NEAREST)
    
    out_path = ARTIFACTS / f"preview_{sid}_walk.gif"
    img0_4x.save(out_path, save_all=True, append_images=[img1_4x], duration=125, loop=0, disposal=2)
    print(f"Saved preview for {sid} walk -> {out_path}")

print("All samples generated successfully!")

