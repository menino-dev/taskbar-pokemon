import json
from pathlib import Path

map_file = Path(__file__).resolve().parent / "pokemon_map.json"
data = json.loads(map_file.read_text(encoding="utf-8"))

for a in data["anims"]:
    if a.get("name") == "dance":
        a["ms"] = 150
        a["frames"] = [
            "pikachu_dance_00",
            "pikachu_dance_01",
            "pikachu_dance_02",
            "pikachu_dance_03"
        ]

map_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("Updated pokemon_map.json successfully!")

