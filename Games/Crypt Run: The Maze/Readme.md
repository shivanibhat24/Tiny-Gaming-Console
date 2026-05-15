# CRYPT-RUN — Maze Game 🗝️

A single-file, pixel-art dungeon maze game built with Pygame.
Navigate procedurally generated mazes, collect coins, find keys, dodge traps,
and reach the exit. Fully playable with a keyboard or the **Xiao ESP32-C3
serial gamepad** (same firmware as Eternal Shards).

---

## Quick Start

```bash
pip install pygame pyserial   # pyserial optional — only needed for controller
python maze.py
```

---

## File Layout

This is intentionally a **single self-contained file** — no imports from other
project modules. Drop `maze.py` anywhere and run it.

```
maze.py           ← entire game: serial, input, maze gen, rendering, game logic
firmware/
└── gamepad/
    └── gamepad.ino   ← shared with Eternal Shards — flash once, use for both
README_MAZE.md
```

---

## Requirements

| Package  | Purpose                            |
|----------|------------------------------------|
| Python ≥ 3.10 |                               |
| pygame ≥ 2.1  | `pip install pygame`          |
| pyserial ≥ 3.5 | Optional — controller only   |

---

## Hardware (same as Eternal Shards)

The maze game reuses the **same firmware** and wiring as the main RPG.
No re-flashing needed if already set up.

| Button  | Xiao Pin | GPIO |
|---------|----------|------|
| UP      | D0       | 2    |
| DOWN    | D1       | 3    |
| LEFT    | D2       | 4    |
| RIGHT   | D3       | 5    |
| OPTIONS | D4       | 6    |

All buttons → active-LOW (connect pin to GND, firmware uses INPUT_PULLUP).

See the [main README](README.md) for full flashing instructions.

**OPTIONS button** acts as **Restart** in the maze game.

---

## Running

```bash
# Auto-detect controller (falls back to keyboard if none found)
python maze.py

# Specify port explicitly
python maze.py --port /dev/ttyUSB0
python maze.py --port COM7

# List serial ports
python maze.py --list-ports

# Custom starting maze size (must be odd numbers)
python maze.py --cols 21 --rows 15

# Bigger, harder start
python maze.py --cols 31 --rows 21
```

---

## Controls

| Action         | Keyboard            | Controller        |
|----------------|---------------------|-------------------|
| Move           | Arrow keys / WASD   | UP DOWN LEFT RIGHT |
| Restart level  | R                   | OPTIONS            |
| Quit           | Esc / Q             | —                 |

Movement has a small built-in repeat rate when held, matching the firmware's
hardware debounce. The keyboard also supports key-repeat after a short hold delay.

---

## Gameplay

### Objective

Reach the **glowing green exit** on each level to advance.
Survive all **7 levels** to win.

### Elements

| Symbol / Color  | Description                                          |
|-----------------|------------------------------------------------------|
| 🔵 Blue circle  | Your player                                          |
| 🟢 Green pulse  | Exit — reach this to clear the level                |
| 🟡 Gold circle  | Coin — +10 pts (bonus per level)                    |
| 🟠 Orange ring  | Key — collect to unlock the door                    |
| 🟤 Brown block  | Door — blocks path until you have the key           |
| 🔴 Red spikes   | Trap — lose a life on contact                       |

### Scoring

| Event                    | Points                              |
|--------------------------|-------------------------------------|
| Collect a coin           | 10 + (level × 2)                   |
| Collect a key            | 50                                  |
| Unlock a door            | 30                                  |
| Reach the exit           | 100 + (remaining coins × 5) bonus  |

### Lives

You start with **3 lives**. Hitting a trap costs one life. Pressing R (Restart)
also costs a life (strategic suicide). Reach 0 lives → Game Over.

### Fog of War

Each level has limited visibility. Explored cells remain dimly visible on the
minimap. The fog radius **shrinks** as levels increase, making later floors
harder to navigate.

### Level Progression

| Feature           | Unlocks at level |
|-------------------|-----------------|
| Coins             | 1               |
| Fog of war        | 1 (always on)   |
| Key + Door        | 2               |
| Traps             | 3               |
| Maze grows each level by +2 cols and +2 rows |

Level 7 is the final floor. Reach its exit to win.

---

## Architecture (single file)

The game is organized into clear classes within `maze.py`:

```
SerialController   — background thread, parses B-frames and PRESSED/RELEASED lines
Input              — merges serial + keyboard, unified just_pressed / held API
Maze               — recursive-backtracker DFS generator, pixel-grid export
FogOfWar           — per-cell revealed/visible tracking with circular radius
Level              — wraps Maze, places start/exit/coins/key/door/traps
Particles          — spark / trail / pickup particle pool
Game               — main loop, tick, camera, renderer, HUD, overlays
```

### Maze Generation

Uses **recursive backtracker (DFS with backtracking)**:

1. Start at cell (0,0), mark visited.
2. Pick a random unvisited neighbour, carve a passage, recurse.
3. When stuck, backtrack.

This always produces a **perfect maze** — exactly one path between any two
cells, no loops, no isolated regions. Every maze is reproducible from its seed
(`level_num × 0xABCD + 0x1337`).

The cell grid is then converted to a **pixel grid** (each cell → one floor
pixel, walls encoded as pixel borders) where `TILE=20` pixels renders each
cell as a 20×20 block.

### Camera

The maze viewport is `SCREEN_W − 160` pixels wide (160px reserved for HUD).
The camera always centres on the player and is clamped to the maze bounds.
Screen shake on trap hits is applied as a random ±N pixel offset for 12 frames.

### Serial Protocol

Same protocol as the main game — see [main README § Serial Protocol](README.md).

The parser inside `SerialController._parse()` handles:
- `B<u><d><l><r><o>` compact state frames (primary source of input)
- `READY:XIAO_GAMEPAD_V1` handshake (logged to console)
- `PRESSED:`/`RELEASED:` verb lines (ignored — state derived from B-frames)

---

## Troubleshooting

| Symptom                       | Fix                                                              |
|-------------------------------|------------------------------------------------------------------|
| Blank screen / immediate crash | Ensure pygame is installed: `pip install pygame`               |
| No controller detected        | Run `python maze.py --list-ports`; pass found port with `--port` |
| Buttons unresponsive          | Check wiring; ensure firmware is flashed and Serial Monitor shows `B` frames |
| Maze too small / large        | Adjust `--cols` and `--rows` (odd numbers only)                |
| Fog too aggressive            | Start at level 1 — fog radius is `max(3, 7 − level)`           |
| Door won't open               | You need to pick up the orange key first                        |

---

## Extending

| Goal                    | Change in `maze.py`                                      |
|-------------------------|----------------------------------------------------------|
| More levels             | Change `MAX_LEVELS` constant                             |
| Different starting size | `--cols` / `--rows` CLI flags, or change defaults in `main()` |
| Add enemies             | Add an `Enemy` dataclass in `Level.__init__`, render in `_draw_specials`, check collision in `_check_tile` |
| New tile type           | Add to `Maze.to_pixel_grid()` encoding and `_draw_specials` |
| Change fog radius       | Edit `FogOfWar` radius formula in `Level.__init__`       |
| Add sound               | `pygame.mixer.Sound` on coin pickup / trap / clear events |
| High scores             | Write `score` to a `scores.json` file on game over/win   |

---

## License

MIT
