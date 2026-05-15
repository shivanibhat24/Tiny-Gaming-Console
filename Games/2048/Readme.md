# 2048 · Neon

The classic tile-merging puzzle — slide numbered tiles to combine them and reach **2048**. Built in Python/Pygame with a neon-noir aesthetic that matches the rest of the console's game library.

---

## Preview

```
┌───────────────────────────────┐
│  2048          SCORE   BEST   │
│                 1240    3800  │
│  ┌─────┬─────┬─────┬─────┐   │
│  │     │   2 │   4 │   2 │   │
│  ├─────┼─────┼─────┼─────┤   │
│  │   4 │  16 │   8 │   4 │   │
│  ├─────┼─────┼─────┼─────┤   │
│  │  32 │   8 │   4 │   2 │   │
│  ├─────┼─────┼─────┼─────┤   │
│  │ 128 │  64 │  16 │   8 │   │
│  └─────┴─────┴─────┴─────┘   │
└───────────────────────────────┘
```

---

## How to Play

Slide all tiles in one direction. When two tiles with the **same number** collide they merge into their sum. A new tile (2 or 4) appears after every move. Reach **2048** to win — or keep going for a higher score!

The board is lost when no moves remain.

---

## Controls

### Hardware Controller (XIAO ESP32-C3)

| Button | Action |
|--------|--------|
| UP | Slide all tiles up |
| DOWN | Slide all tiles down |
| LEFT | Slide all tiles left |
| RIGHT | Slide all tiles right |
| OPTIONS (tap) | Start a new game |
| OPTIONS (hold ~1 s) | Undo last move |

### Keyboard Fallback

| Key | Action |
|-----|--------|
| Arrow keys or WASD | Slide tiles |
| R | New game |
| U | Undo last move |
| Esc / Q | Quit |

---

## Running the Game

### Prerequisites

```bash
pip install pygame pyserial
```

`pyserial` is optional — if it is not installed the game runs in keyboard-only mode.

### Launch

```bash
# From the repository root:
python Games/2048/2048.py

# With a specific serial port:
python Games/2048/2048.py --port COM7           # Windows
python Games/2048/2048.py --port /dev/ttyUSB0   # Linux
python Games/2048/2048.py --port /dev/cu.usbmodem14101  # macOS

# List available ports:
python Games/2048/2048.py --list-ports
```

The controller is auto-detected if no `--port` flag is given.

---

## Features

**Visual**
- Neon-noir colour palette — tiles shift from cool blue (low values) through cyan and gold to red/purple at 2048+
- Glow effects that intensify as tile values grow
- Per-tile pop/scale animation on every merge
- Floating `+N` score badges after each merge
- Starfield background and screen shake on invalid moves / game over

**Gameplay**
- 1-step undo — OPTIONS hold or press U to revert the last move
- Best score tracked for the session
- After reaching 2048 you can choose to keep playing or start fresh
- Skill label (Beginner → Legendary) updates in the header as your highest tile climbs

---

## Tile Colour Reference

| Value | Colour |
|-------|--------|
| 2 | Deep blue |
| 4 | Cobalt |
| 8 | Sky blue |
| 16 | Cyan |
| 32 | Teal green |
| 64 | Lime |
| 128 | Yellow-green |
| 256 | Gold |
| 512 | Amber |
| 1024 | Orange |
| 2048 | Red |
| 4096+ | Purple |

---

## File Overview

```
Games/2048/
├── 2048.py      # Complete single-file game
└── README.md    # This file
```

`2048.py` contains:

| Class / Section | Purpose |
|-----------------|---------|
| `SerialController` | Background-thread serial reader for the XIAO ESP32-C3 |
| `Input` | Unifies serial and keyboard input; handles OPTIONS tap vs. hold |
| Grid logic (`slide`, `spawn_tile`, …) | Pure functions — no Pygame dependency |
| `Particles` | Lightweight particle system for merge effects |
| `TileAnim` | Per-cell scale/pop animation on merge |
| `ScoreBadge` | Floating score popups |
| `Game` | Main loop, renderer, state machine |

---

## Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.8+ |
| pygame | 2.0+ |
| pyserial | 3.4+ (optional) |
