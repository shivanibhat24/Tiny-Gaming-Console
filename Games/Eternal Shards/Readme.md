# Eternal Shards 🗡️

A pixel-art RPG built with Pygame, playable with a keyboard or a physical
gamepad built around the **Seeed Xiao ESP32-C3** over USB serial.

---

## Project Structure

```
eternal-shards/
├── main.py              ← Game engine (this file)
├── src/
│   ├── __init__.py
│   ├── data.py          ← All game data (classes, enemies, maps, items…)
│   └── sprites.py       ← Pixel-art sprite renderer (pygame.draw primitives)
├── firmware/
│   └── gamepad/
│       └── gamepad.ino  ← Arduino sketch for Xiao ESP32-C3
└── README.md
```

---

## Requirements

### Python

| Package   | Version   | Notes                                   |
|-----------|-----------|-----------------------------------------|
| Python    | ≥ 3.10    |                                         |
| pygame    | ≥ 2.1     | `pip install pygame`                    |
| pyserial  | ≥ 3.5     | Optional — only needed for the gamepad  |

```bash
pip install pygame pyserial
```

### Hardware (optional)

- Seeed Xiao ESP32-C3
- 5 momentary push-buttons (tactile switches work fine)
- Breadboard + jumper wires

---

## Hardware Wiring

All buttons are wired **active-LOW** (button connects the pin to GND).
The firmware enables the internal pull-up resistor on each pin.

| Button  | Xiao Pin | GPIO |
|---------|----------|------|
| UP      | D0       | 2    |
| DOWN    | D1       | 3    |
| LEFT    | D2       | 4    |
| RIGHT   | D3       | 5    |
| OPTIONS | D4       | 6    |

```
Xiao D0 ──[BTN UP]── GND
Xiao D1 ──[BTN DOWN]── GND
Xiao D2 ──[BTN LEFT]── GND
Xiao D3 ──[BTN RIGHT]── GND
Xiao D4 ──[BTN OPTIONS]── GND
```

---

## Flashing the Firmware

1. Open **Arduino IDE** (≥ 2.x) or PlatformIO.
2. Add the Seeed XIAO ESP32-C3 board package:
   - Board manager URL: `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   - Search for **esp32** and install.
3. Select **Board → Seeed XIAO ESP32-C3**.
4. Open `firmware/gamepad/gamepad.ino` and upload.
5. Open the Serial Monitor at **115200 baud** — you should see:

   ```
   READY:XIAO_GAMEPAD_V1
   B00000
   ```

   Pressing a button should print lines like `PRESSED:UP` and `B10000`.

---

## Serial Protocol

The firmware speaks a minimal line-based ASCII protocol over USB-CDC at 115200 baud.

### Frames sent by the controller

| Line               | Meaning                                                  |
|--------------------|----------------------------------------------------------|
| `READY:XIAO_GAMEPAD_V1` | Sent on boot — handshake                           |
| `B<u><d><l><r><o>` | Full state frame. Each character is `0` (released) or `1` (pressed). Sent on any change **and** every 1 second as a heartbeat. |
| `PRESSED:<name>`   | Edge event — button just went down                       |
| `RELEASED:<name>`  | Edge event — button just went up                         |

Button order in the `B` frame: **U D L R O** (Up, Down, Left, Right, Options).

Example: `B10010` → Up pressed, Right pressed, all others released.

### Python side

`SerialController` runs a daemon thread that reads the port, parses every line,
updates its internal state array, and pushes `("PRESSED", name)` /
`("RELEASED", name)` tuples into a `queue.Queue`.

`InputManager` drains that queue once per frame and merges it with pygame keyboard
events, exposing a unified API:

```python
inp.just_pressed("UP")      # True for one frame after press
inp.held("RIGHT")           # True while held
inp.any_just_pressed()      # Any input this frame?
```

---

## Running the Game

### Auto-detect controller

```bash
python main.py
```

The engine scans serial ports for anything that looks like a CH340/CP210x/ESP32
and connects automatically. If nothing is found it falls back silently to
keyboard-only mode.

### Specify a port explicitly

```bash
# Linux / macOS
python main.py --port /dev/ttyUSB0
python main.py --port /dev/cu.usbmodem1101

# Windows
python main.py --port COM7
```

### List available serial ports

```bash
python main.py --list-ports
```

---

## Keyboard Controls (fallback)

| Action     | Keys                           |
|------------|--------------------------------|
| Move       | Arrow keys  or  W A S D        |
| Confirm    | Z  /  Enter  /  Space          |
| Cancel     | X  /  Escape                   |
| Menu       | Shift  /  Tab                  |

---

## Gameplay

### Screens

| Screen       | Description                                              |
|--------------|----------------------------------------------------------|
| Intro        | Story prologue → name entry → class selection            |
| World Map    | Top-down tile map, real-time movement, random encounters |
| Town         | Shop + rest; fully navigable with controller             |
| Battle       | Turn-based with Fight / Skills / Items / Flee menus      |
| Game Over    | Any button restarts                                      |
| Victory      | Defeat the Dragon boss to win                            |

### Classes

| Class   | Strength                            | Weakness          |
|---------|-------------------------------------|-------------------|
| Warrior | High HP & DEF, physical powerhouse  | Low MP & MAG      |
| Mage    | Devastating AOE magic               | Fragile, low DEF  |
| Rogue   | Fastest, best crit (Shadow Strike)  | Average HP        |

### Towns

| Town       | Map Position | Shop Highlights                  |
|------------|-------------|----------------------------------|
| Alverton   | (11, 2)     | Basic consumables, Iron gear     |
| Brackwater | (5, 7)      | Antidotes, Chain Mail            |
| Goldhaven  | (18, 12)    | Hi-Potions, Ethers, Magic Staff  |

### Enemies

Common enemies inhabit the world map by tile type:

- **Sand / Grass:** Slimes, Goblins, Wolves
- **Forest:** Wolves, Orcs
- **Snow:** Wolves, Skeletons
- **Dungeon:** Skeletons, Orcs, Witches, **Dark Knight** (boss)

The **Dragon Malachar** guards the mountain peak at tile (22, 1) — the
final boss. Defeating it triggers the Victory screen.

### Battle System

- **Initiative:** Higher SPD acts first; ties broken randomly.
- **Damage formula:**  
  Physical: `max(1, ATK − DEF/2) ± 25%`  
  Magic: `POWER ± 33%`
- **Status effects:** Poison (DoT, 3 turns), Stun/Paralyze (skip turn),
  Slow (halve ATK on enemy turn), DEF-half (Berserker debuff).
- **Flee:** Success chance = `50% + (hero SPD − enemy SPD) × 5%`, capped 10–90%.
- **Level up:** Every time XP crosses the threshold
  `20 × level^1.4`, stats grow by class base rates + a random ±1.

---

## Controller Status Indicator

A small dot in the bottom-right corner of the screen shows connection status:

- **Green dot** — serial controller connected
- **Grey dot** — keyboard-only mode

---

## Extending the Game

| Goal                          | Where to edit               |
|-------------------------------|-----------------------------|
| Add enemies / bosses          | `src/data.py` → `ENEMIES`  |
| Add skills                    | `src/data.py` → `SKILLS`   |
| Add items / shop stock        | `src/data.py` → `ITEMS`, `TOWNS` |
| New character class           | `src/data.py` → `CLASSES`; add a `draw_*` function in `sprites.py` |
| Remap buttons on the firmware | Change `#define PIN_*` in `gamepad.ino` |
| Support more buttons (A/B/Start/Select) | Add pins in firmware, extend `BTN_MAP` in `SerialController`, add actions in `InputManager.SERIAL_MAP` |
| Change screen resolution      | `SCREEN_W`, `SCREEN_H` in `src/data.py` |

---

## Troubleshooting

| Symptom                          | Fix                                                               |
|----------------------------------|-------------------------------------------------------------------|
| No serial port detected          | Check USB cable (data-capable, not charge-only); install CH340 / CP210x drivers |
| `READY` never received           | Re-flash firmware; confirm baud is 115200 on both sides           |
| Buttons registering wrong inputs | Verify wiring matches `PIN_*` defines; swap D-pin assignments in `gamepad.ino` |
| Erratic inputs / double-fires    | Increase `DEBOUNCE_MS` in firmware (default 20 ms)                |
| `ModuleNotFoundError: pygame`    | `pip install pygame`                                              |
| `ModuleNotFoundError: serial`    | `pip install pyserial`                                            |
| Game runs but controller ignored | Run `python main.py --list-ports` to check the port name, then pass it with `--port` |

---

## License

MIT — do whatever you like with it.
