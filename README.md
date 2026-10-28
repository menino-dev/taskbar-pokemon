# Taskbar Pokémon

A nostalgic pixel-art Pokémon companion that lives, wanders, naps, and dances on your Windows 11 taskbar!

Supports **634 Pokémon** across Generations 1 to 5 (including Shiny variants), with full interactive physics, mood simulation, music-reactive dancing, and Pokéball play.

Based on [Taskbar Cat](https://github.com/viraj-rgb/windhawk-taskbar-cat) by [viraj-rgb](https://github.com/viraj-rgb) (MIT) with Pokémon sprite assets from [vscode-pokemon](https://github.com/jakobhoeg/vscode-pokemon) by [jakobhoeg](https://github.com/jakobhoeg) (MIT).

---

## ✨ Features

- **Multi-Pokémon Support (Full Party of up to 6!):**
  - Choose how many Pokémon companions roam your taskbar simultaneously (from 1 up to 6!).
  - Each Pokémon has its own independent mood, energy, personality, and position across the taskbar.
  - Interact with each Pokémon individually: hover to pet, drag & drop to relocate, or open its right-click menu.
- **634 Pokémon Across 5 Generations:**
  - **Gen 1 (Kanto):** 153 Pokémon (Bulbasaur, Charmander, Squirtle, Pikachu, Eevee, Mew, etc.)
  - **Gen 2 (Johto):** 132 Pokémon (Chikorita, Cyndaquil, Totodile, Umbreon, Espeon, Celebi, etc.)
  - **Gen 3 (Hoenn):** 138 Pokémon (Treecko, Torchic, Mudkip, Rayquaza, Lucario, etc.)
  - **Gen 4 (Sinnoh):** 142 Pokémon (Turtwig, Chimchar, Piplup, Gengar, Garchomp, etc.)
  - **Gen 5 (Unova):** 69 Pokémon (Victini, Snivy, Tepig, Oshawott, Zoroark, etc.)
- **Shiny Variants:** Toggle normal or shiny palette for any Pokémon in the mod settings.
- **Synchronized Music Dance:** When music or video is playing on your PC (Spotify, YouTube, games), ALL active Pokémon on your taskbar dance together in perfect synchronization to the beat in a continuous 3-pose sway loop (left ↔ center ↔ right) with music notes floating above!
- **Interactive Behaviors:**
  - **Hover:** Pet your Pokémon; hearts appear.
  - **Click:** Wake it up or give a friendly call.
  - **Double-Click:** Rolls over happily.
  - **Drag & Drop:** Pick it up by the scruff and drop it anywhere along the taskbar.
  - **Quick cursor sweep:** Crouch, wiggle, and pounce!
  - **Right-Click Menu:** Pet, treat, nap, wake up, stay here, or play with a Pokéball.
  - **Pokéball Toy:** Toss a Pokéball onto the taskbar for your Pokémon to chase and nudge.
- **Autonomous Moods & Day/Night Cycle:**
  - Energy, boredom, and curiosity drift dynamically for each companion.
  - Takes naps when tired (more often at night).
  - Sleeps when you leave the computer idle for 5 minutes.
  - Wears festive seasonal hats (Halloween, Christmas, New Year).

---

## 🚀 Installation via Windhawk

1. Download and install [Windhawk](https://windhawk.net/) (free, open source).
2. Open Windhawk and click on the **Advanced** tab.
3. Select **Mod Manager** -> **New Mod**.
4. Replace the editor contents with the code from [`taskbar-pokemon.wh.cpp`](taskbar-pokemon.wh.cpp).
5. Click **Compile Mod**.
6. Enjoy your Pokémon companions on the taskbar!

---

## ⚙️ Configuration

In Windhawk, open the **Details** / **Settings** tab of Taskbar Pokémon to customize:

- **Number of Pokémon:** Select how many Pokémon to display (1 to 6).
- **Pokémon 1:** Select Generation (Gen 1-5) and use dropdown, or type a custom name/ID. Set optional nickname.
- **Pokémon 2 to 6:** Configure each additional party member by typing any Pokémon name or ID (e.g. `charmander`, `squirtle`, `gengar`, `lucario`, `eevee`, `mewtwo`, etc.) with optional individual nicknames.
- **Walk Speed & Behavior:** Adjust walking pace, sleepiness, sound effects, and scale.

---

## 🛠️ Development & Pipeline

The project includes an end-to-end Python generation and validation pipeline:

- **`tools/generate_all_pokemon_mod.py`**: Compiles all 634 Pokémon sprite sheets into indexed ROM banks and emits the self-contained `taskbar-pokemon.wh.cpp`.
- **`tools/verify_pokemon_roundtrip.py`**: Decodes the C++ RLE byte stream back into pixel arrays and verifies 100% pixel-exact roundtrip fidelity (0 diffs).
- **`tests/pokemon_engine_tests.cpp`**: Unit test suite covering all animation frames, anchors, and state machine transitions (>300,000 checks).
- **`tools/run_pokemon_checks.ps1`**: Automated verification runner (roundtrip + preview generation + Clang++ compilation + unit tests).

To run all checks locally:
```powershell
powershell -ExecutionPolicy Bypass -File tools/run_pokemon_checks.ps1
```

---

## 📄 License & Credits

- Mod engine based on [Taskbar Cat](https://github.com/viraj-rgb/windhawk-taskbar-cat) by [viraj-rgb](https://github.com/viraj-rgb) (MIT License).
- Pokémon sprite sheets from [vscode-pokemon](https://github.com/jakobhoeg/vscode-pokemon) by [jakobhoeg](https://github.com/jakobhoeg) (MIT License).
- Pokémon is a registered trademark of Nintendo, Creatures Inc., and GAME FREAK Inc. This project is a non-commercial, fan-made open-source modification.
- Released under the [MIT License](LICENSE).

