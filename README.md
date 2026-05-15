# 🎮 Tiny Gaming Console

A DIY handheld gaming console built around the **Seeed Studio XIAO ESP32-C3** microcontroller. The hardware acts as a serial gamepad; games run as Python/Pygame applications on a connected PC or laptop.

```
┌──────────────────────────────────────────────────────┐
│  XIAO ESP32-C3  ──USB Serial──►  PC / Laptop         │
│  5 tactile buttons              Python + Pygame game  │
└──────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
Tiny-Gaming-Console/
├── Firmware/
│   └── gamepad/
│       └── gamepad.ino        # Arduino firmware for the XIAO ESP32-C3
│
├── Games/
│   ├── CryptRunMaze/
│   │   ├── maze.py
│   │   └── README.md
│   ├── 2048/
│   │   ├── 2048.py
│   │   └── README.md
│   └── ...                    # More games follow the same pattern
│
└── README.md                  # ← You are here
```

---

## Hardware

### Components

| Part | Details |
|------|---------|
| Microcontroller | Seeed Studio XIAO ESP32-C3 |
| Buttons | 5× tactile push buttons (active LOW, pulled up internally) |
| Connection | USB-C to host PC |
| Power | Bus-powered via USB |

### Wiring

All buttons connect between the listed pin and **GND**.

| Button | Pin | GPIO |
|--------|-----|------|
| UP | D0 | GPIO 2 |
| DOWN | D1 | GPIO 3 |
| LEFT | D2 | GPIO 4 |
| RIGHT | D3 | GPIO 5 |
| OPTIONS | D4 | GPIO 6 |

---

## Firmware

The firmware lives in `Firmware/gamepad/gamepad.ino` and is flashed onto the XIAO ESP32-C3 using the Arduino IDE.

### Setup

1. Install the **Arduino IDE** (v2.x recommended).
2. Add the ESP32 board package — in Arduino IDE go to **File → Preferences** and add this URL to *Additional boards manager URLs*:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Open **Tools → Board → Boards Manager**, search for `esp32`, and install the Espressif package.
4. Select **XIAO_ESP32C3** under `Tools → Board → ESP32 Arduino`.
5. Open `Firmware/gamepad/gamepad.ino` and click **Upload**.

### Serial Protocol

The firmware communicates at **115 200 baud** and emits two types of lines:

| Line | Meaning |
|------|---------|
| `READY:XIAO_GAMEPAD_V1` | Sent once on boot |
| `PRESSED:UP` / `RELEASED:DOWN` | Verb events for each button (UP, DOWN, LEFT, RIGHT, OPTIONS) |
| `B10010` | Compact bitmask frame — 5 chars mapping to U D L R O (1 = pressed) |

A heartbeat bitmask frame is sent every second even if nothing changes, so the host can detect disconnects.

---

## Games

Each game is self-contained in its own subfolder inside `Games/` and has its own `README.md` with full setup and control instructions.

### Available Games

| Game | File | Description |
|------|------|-------------|
| Crypt-Run Maze | `Games/CryptRunMaze/maze.py` | Procedurally generated dungeon maze with fog of war, coins, keys, traps and 7 levels |
| 2048 Neon | `Games/2048/2048.py` | The classic tile-merging puzzle with neon-noir visuals, undo, and best-score tracking |

### Running Any Game

**Prerequisites — install once:**

```bash
pip install pygame pyserial
```

**Launch with auto-detected controller:**

```bash
python Games/CryptRunMaze/maze.py
python Games/2048/2048.py
```

**Specify a port explicitly (if auto-detection misses the device):**

```bash
python Games/2048/2048.py --port COM7          # Windows
python Games/2048/2048.py --port /dev/ttyUSB0  # Linux
python Games/2048/2048.py --port /dev/cu.usbmodem14101  # macOS
```

**List available serial ports:**

```bash
python Games/2048/2048.py --list-ports
```

If no controller is detected the game falls back to **keyboard-only mode** automatically — no flag needed.

---

## Adding a New Game

Every game in this repo follows the same pattern so the controller just works:

1. Create a folder `Games/YourGame/`.
2. Copy the `SerialController` and `Input` classes from any existing game — they are identical across all games and handle the full serial protocol.
3. Write your game loop. Call `self.inp.update(pg_events)` each frame and query `self.inp.jp("UP")` etc. for input.
4. Add a `README.md` inside `Games/YourGame/` describing controls and rules.

### Button Action Conventions

| Button | Typical role |
|--------|-------------|
| UP / DOWN / LEFT / RIGHT | Movement, cursor, menu navigation |
| OPTIONS (tap) | Restart / confirm / new game |
| OPTIONS (hold ~1 s) | Undo / back / pause |

### Good Candidates for Future Games

**Grid / turn-based (easy):** Snake, Sokoban, Minesweeper, Tic-Tac-Toe

**Real-time arcade (medium):** Tetris, Breakout, Space Invaders, Flappy Bird clone, Frogger

**Advanced:** Pac-Man, Roguelike dungeon crawler, Bomberman (single-player)

---

## Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `pygame` | Game rendering and input | `pip install pygame` |
| `pyserial` | Serial communication with the controller | `pip install pyserial` |

Python **3.8+** required. Both packages are optional at import time — if `pyserial` is missing the games run in keyboard-only mode.

---

## Keyboard Fallback

Every game supports full keyboard play when no controller is connected.

| Key | Action |
|-----|--------|
| Arrow keys or WASD | Directional input |
| R | Restart / new game |
| U | Undo (where supported) |
| Esc / Q | Quit |

---

## License

MIT — do whatever you like, attribution appreciated.

---

## Contributing

Pull requests welcome! If you add a game, please include a `README.md` in its folder and follow the `SerialController` / `Input` conventions so it works with the hardware out of the box.
