"""
Eternal Shards — Main Engine
Pygame RPG with Xiao ESP32-C3 serial gamepad support.

Controls (keyboard fallback):
  Arrow keys / WASD  → movement
  Z / Enter          → confirm / interact
  X / Escape         → cancel / menu
  Shift              → OPTIONS (pause/menu)

Serial protocol (from firmware):
  "B<u><d><l><r><o>\\n"   compact state frame
  "PRESSED:<name>\\n"     edge event
  "RELEASED:<name>\\n"    edge event
  "READY:XIAO_GAMEPAD_V1" handshake
"""

import sys
import os
import threading
import queue
import random
import math
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional

import pygame

# ── Optional PySerial ──────────────────────────────────────────────
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# ── Project data ──────────────────────────────────────────────────
from data import (
    PAL, SCREEN_W, SCREEN_H, TILE, MAP_W, MAP_H, FPS,
    CLASSES, SKILLS, ITEMS, ENEMIES, START_ITEMS,
    WORLD_MAP, TILE_COLORS, TILE_WALKABLE, TILE_ENCOUNTER,
    TILE_ENCOUNTER_TABLE, TOWNS, DUNGEONS, BOSS_POS, BOSS_ENEMY, NPCS, STORY,
)
from sprites import get_sprite


# ═══════════════════════════════════════════════════════════════════
#  SERIAL CONTROLLER
# ═══════════════════════════════════════════════════════════════════

class SerialController:
    """
    Manages the Xiao ESP32-C3 serial gamepad in a background thread.
    Pushes press/release events into an event queue consumed by the game loop.
    """

    BTN_MAP = {0: "UP", 1: "DOWN", 2: "LEFT", 3: "RIGHT", 4: "OPTIONS"}

    def __init__(self, port: Optional[str] = None, baud: int = 115200):
        self.port = port
        self.baud = baud
        self._ser: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.connected = False
        self._state = [False] * 5   # UP DOWN LEFT RIGHT OPTIONS
        self._last_frame = "B00000"

    # ── Public API ─────────────────────────────────────────────────

    @staticmethod
    def auto_detect() -> Optional[str]:
        """Return the first port that looks like an Xiao / CH34x / CP210x."""
        if not SERIAL_AVAILABLE:
            return None
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            return None

        keywords = (
            "xiao", "esp32", "ch340", "ch341", "cp210",
            "usbmodem", "ttyusb", "ttyacm", "usb serial",
            "silicon labs", "prolific", "usb-uart", "arduino",
        )

        for p in ports:
            desc = (p.description or "").lower()
            dev  = (p.device or "").lower()
            if any(k in desc or k in dev for k in keywords):
                return p.device

        if len(ports) == 1:
            p = ports[0]
            print(f"[Serial] Auto-detected serial port {p.device} ({p.description})")
            return p.device

        print("[Serial] Auto-detect failed, available serial ports:")
        for p in ports:
            print(f"  {p.device:12}  {p.description}")
        return None

    @staticmethod
    def _debug_list_ports():
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("[Serial] No serial ports found.")
            return
        print("[Serial] Available serial ports:")
        for p in ports:
            print(f"  {p.device:12}  {p.description}")

    def start(self) -> bool:
        if not SERIAL_AVAILABLE:
            return False
        port = self.port or self.auto_detect()
        if not port:
            print("[Serial] No controller port found — running keyboard-only.")
            return False

        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                self._ser = serial.Serial(port, self.baud, timeout=0.1)
                time.sleep(0.1)
                self._ser.reset_input_buffer()
                self.connected = True
                self._stop_evt.clear()
                self._thread = threading.Thread(target=self._reader, daemon=True)
                self._thread.start()
                print(f"[Serial] Connected to {port} @ {self.baud} baud")
                return True
            except PermissionError as e:
                print(f"[Serial] Permission denied opening {port} (attempt {attempt}/{attempts}): {e}")
                if attempt < attempts:
                    time.sleep(0.3)
                    continue
                break
            except Exception as e:
                print(f"[Serial] Could not open {port}: {e}")
                break

        self._debug_list_ports()
        return False

    def stop(self):
        self._stop_evt.set()
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass
        self.connected = False

    def get_state(self) -> dict:
        """Return current debounced button state as a dict."""
        return {
            "UP":      self._state[0],
            "DOWN":    self._state[1],
            "LEFT":    self._state[2],
            "RIGHT":   self._state[3],
            "OPTIONS": self._state[4],
        }

    def drain_events(self) -> list:
        evts = []
        while not self.events.empty():
            evts.append(self.events.get_nowait())
        return evts

    # ── Background reader thread ───────────────────────────────────

    def _reader(self):
        while not self._stop_evt.is_set():
            try:
                if not self._ser.is_open:
                    break
                line = self._ser.readline()
                if not line:
                    continue
                self._parse(line.decode(errors="ignore").strip())
            except Exception as e:
                if not self._stop_evt.is_set():
                    print(f"[Serial] Reader error: {e}")
                break
        self.connected = False

    def _parse(self, line: str):
        if not line:
            return
        if line.startswith("B") and len(line) == 6:
            # Compact state frame
            new_state = [c == "1" for c in line[1:6]]
            for i, (old, new) in enumerate(zip(self._state, new_state)):
                if old != new:
                    name = self.BTN_MAP[i]
                    self.events.put(("PRESSED" if new else "RELEASED", name))
            self._state = new_state
            self._last_frame = line
        elif line.startswith("PRESSED:") or line.startswith("RELEASED:"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                evt_type = parts[0]
                name = parts[1].strip().upper()
                if name in self.BTN_MAP.values():
                    self.events.put((evt_type, name))
        elif line.startswith("READY:"):
            print(f"[Serial] Handshake: {line}")


# ═══════════════════════════════════════════════════════════════════
#  INPUT MANAGER  — merges keyboard + serial
# ═══════════════════════════════════════════════════════════════════

class InputManager:
    """
    Provides a unified input API regardless of whether the controller is
    connected.  Returns pressed / just_pressed / just_released for logical
    actions: UP, DOWN, LEFT, RIGHT, CONFIRM, CANCEL, MENU.
    """

    KEYBOARD_MAP = {
        "UP":      [pygame.K_UP,    pygame.K_w],
        "DOWN":    [pygame.K_DOWN,  pygame.K_s],
        "LEFT":    [pygame.K_LEFT,  pygame.K_a],
        "RIGHT":   [pygame.K_RIGHT, pygame.K_d],
        "CONFIRM": [pygame.K_z,     pygame.K_RETURN, pygame.K_SPACE],
        "CANCEL":  [pygame.K_x,     pygame.K_ESCAPE],
        "MENU":    [pygame.K_LSHIFT,pygame.K_RSHIFT, pygame.K_TAB],
    }

    # Map serial BTN names → logical actions
    SERIAL_MAP = {
        "UP":      "UP",
        "DOWN":    "DOWN",
        "LEFT":    "LEFT",
        "RIGHT":   "RIGHT",
        "OPTIONS": "MENU",
    }

    def __init__(self, controller: SerialController):
        self.ctrl = controller
        self._just_pressed: set  = set()
        self._just_released: set = set()
        self._held: set          = set()
        # For keyboard repeat on held directions
        self._held_since: dict = {}
        self._repeat_delay = 0.25   # seconds before repeat kicks in
        self._repeat_rate  = 0.08   # seconds between repeats

    def update(self, pygame_events: list):
        self._just_pressed.clear()
        self._just_released.clear()

        # ── Serial events ──────────────────────────────────────────
        for evt_type, btn_name in self.ctrl.drain_events():
            action = self.SERIAL_MAP.get(btn_name)
            if action:
                if evt_type == "PRESSED":
                    self._just_pressed.add(action)
                    self._held.add(action)
                elif evt_type == "RELEASED":
                    self._just_released.add(action)
                    self._held.discard(action)

        # ── Keyboard events ────────────────────────────────────────
        keys_down = pygame.key.get_pressed()
        now = time.time()

        for action, keycodes in self.KEYBOARD_MAP.items():
            any_pressed = any(keys_down[k] for k in keycodes)

            for ev in pygame_events:
                if ev.type == pygame.KEYDOWN and ev.key in keycodes:
                    self._just_pressed.add(action)
                    self._held.add(action)
                    self._held_since[action] = now
                if ev.type == pygame.KEYUP and ev.key in keycodes:
                    if not any(keys_down[k] for k in keycodes if k != ev.key):
                        self._just_released.add(action)
                        self._held.discard(action)
                        self._held_since.pop(action, None)

            # Key-repeat for directional actions
            if action in ("UP", "DOWN", "LEFT", "RIGHT") and action in self._held:
                since = self._held_since.get(action, now)
                elapsed = now - since
                if elapsed > self._repeat_delay:
                    phase = (elapsed - self._repeat_delay) % self._repeat_rate
                    if phase < (1 / FPS) * 1.5:
                        self._just_pressed.add(action)

    def just_pressed(self, action: str) -> bool:
        return action in self._just_pressed

    def held(self, action: str) -> bool:
        return action in self._held

    def any_just_pressed(self) -> bool:
        return bool(self._just_pressed)


# ═══════════════════════════════════════════════════════════════════
#  GAME STATE CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Hero:
    name: str
    cls:  str
    lv:   int = 1
    xp:   int = 0
    gold: int = 50
    hp:   int = 0
    mp:   int = 0
    max_hp: int = 0
    max_mp: int = 0
    atk: int = 0
    defense: int = 0
    mag: int = 0
    spd: int = 0
    skills: list = field(default_factory=list)
    inventory: dict = field(default_factory=dict)
    equipment: dict = field(default_factory=lambda: {"weapon": None, "armor": None})
    x: int = 11
    y: int = 2

    def __post_init__(self):
        c = CLASSES[self.cls]
        self.max_hp = c["hp"]; self.hp = self.max_hp
        self.max_mp = c["mp"]; self.mp = self.max_mp
        self.atk  = c["atk"]; self.defense = c["def"]
        self.mag  = c["mag"]; self.spd = c["spd"]
        self.skills = list(c["skills"])
        self.inventory = dict(START_ITEMS)

    def xp_to_next(self) -> int:
        return int(20 * (self.lv ** 1.4))

    def level_up(self) -> list:
        gains = []
        c = CLASSES[self.cls]
        self.lv += 1
        for stat, grow_key in [("max_hp","hp_grow"),("max_mp","mp_grow"),
                                ("atk","atk_grow"),("defense","def_grow"),
                                ("mag","mag_grow"),("spd","spd_grow")]:
            gain = c[grow_key] + random.randint(0, 1)
            setattr(self, stat, getattr(self, stat) + gain)
            gains.append((stat, gain))
        self.hp = min(self.hp + c["hp_grow"] * 2, self.max_hp)
        self.mp = min(self.mp + c["mp_grow"] * 2, self.max_mp)
        return gains

    def eff_atk(self) -> int:
        eq = self.equipment.get("weapon")
        bonus = ITEMS[eq].get("atk", 0) if eq else 0
        return self.atk + bonus

    def eff_def(self) -> int:
        eq = self.equipment.get("armor")
        bonus = ITEMS[eq].get("def", 0) if eq else 0
        return self.defense + bonus

    def eff_mag(self) -> int:
        eq = self.equipment.get("weapon")
        bonus = ITEMS[eq].get("mag", 0) if eq else 0
        return self.mag + bonus


@dataclass
class BattleEnemy:
    name: str
    hp:   int
    max_hp: int
    mp:   int
    atk:  int
    defense: int
    mag:  int
    spd:  int
    skills: list
    xp:   int
    gold: int
    loot: dict
    is_boss: bool = False
    status: Optional[str] = None   # "poison", "stun", "slow", "paralyzed"
    status_turns: int = 0
    atk_boost: int = 0
    atk_boost_turns: int = 0
    def_half: bool = False


class GamePhase(Enum):
    INTRO    = auto()
    WORLD    = auto()
    TOWN     = auto()
    BATTLE   = auto()
    GAMEOVER = auto()
    VICTORY  = auto()


# ═══════════════════════════════════════════════════════════════════
#  RENDERER HELPERS
# ═══════════════════════════════════════════════════════════════════

def _c(name: str):
    return PAL[name]

def draw_text(surf, text, x, y, color=None, size=14, bold=False):
    color = color or PAL["ui_text"]
    font = pygame.font.SysFont("monospace", size, bold=bold)
    rendered = font.render(text, True, color)
    surf.blit(rendered, (x, y))
    return rendered.get_width()

def draw_bar(surf, x, y, w, h, val, max_val, color, bg=None):
    bg = bg or PAL["ui_dark"]
    pygame.draw.rect(surf, bg, (x, y, w, h))
    if max_val > 0:
        fill = max(0, int(w * val / max_val))
        pygame.draw.rect(surf, color, (x, y, fill, h))
    pygame.draw.rect(surf, PAL["ui_border"], (x, y, w, h), 1)

def draw_panel(surf, x, y, w, h, border=True):
    pygame.draw.rect(surf, PAL["ui_panel"], (x, y, w, h))
    if border:
        pygame.draw.rect(surf, PAL["ui_border"], (x, y, w, h), 2)

def draw_window(surf, x, y, w, h, title=""):
    draw_panel(surf, x, y, w, h)
    if title:
        pygame.draw.rect(surf, PAL["ui_border"], (x, y, w, 18))
        draw_text(surf, title, x + 6, y + 2, PAL["ui_gold"], 12, bold=True)


# ═══════════════════════════════════════════════════════════════════
#  BATTLE SYSTEM
# ═══════════════════════════════════════════════════════════════════

class BattleSystem:
    """
    Turn-based battle.  Handles menus, animations, status effects, loot.
    Returns ("win", loot_dict) or ("lose",) or ("fled",).
    """

    MENU_ITEMS = ["Fight", "Skills", "Items", "Flee"]

    def __init__(self, hero: Hero, enemy_name: str, screen: pygame.Surface):
        self.hero    = hero
        self.screen  = screen
        self.enemy   = self._make_enemy(enemy_name)
        self.log: list[str] = []
        self.phase   = "player_menu"   # player_menu | skill_menu | item_menu | anim | enemy_turn | result
        self.result  = None
        self.cursor  = 0
        self.sub_cursor = 0
        self.anim_timer = 0
        self.shake   = 0
        self.flash_color: Optional[tuple] = None
        self.flash_timer = 0
        self._loot: dict = {}

    # ── Factory ────────────────────────────────────────────────────

    @staticmethod
    def _make_enemy(name: str) -> BattleEnemy:
        e = ENEMIES[name]
        return BattleEnemy(
            name=name, hp=e["hp"], max_hp=e["hp"], mp=e["mp"],
            atk=e["atk"], defense=e["def"], mag=e["mag"], spd=e["spd"],
            skills=list(e["skills"]), xp=e["xp"], gold=e["gold"],
            loot=dict(e.get("loot", {})), is_boss=e.get("boss", False),
        )

    # ── Public: step called once per frame ─────────────────────────

    def step(self, inp: InputManager) -> Optional[tuple]:
        if self.phase == "player_menu":
            self._handle_player_menu(inp)
        elif self.phase == "skill_menu":
            self._handle_skill_menu(inp)
        elif self.phase == "item_menu":
            self._handle_item_menu(inp)
        elif self.phase == "anim":
            self._tick_anim()
        elif self.phase == "enemy_turn":
            self._do_enemy_turn()
        elif self.phase == "result":
            if inp.just_pressed("CONFIRM") or inp.just_pressed("CANCEL"):
                return self.result
        return None

    # ── Input handlers ─────────────────────────────────────────────

    def _handle_player_menu(self, inp):
        if inp.just_pressed("UP"):
            self.cursor = (self.cursor - 1) % len(self.MENU_ITEMS)
        if inp.just_pressed("DOWN"):
            self.cursor = (self.cursor + 1) % len(self.MENU_ITEMS)
        if inp.just_pressed("CONFIRM"):
            choice = self.MENU_ITEMS[self.cursor]
            if choice == "Fight":
                self._player_attack_basic()
            elif choice == "Skills":
                self.phase = "skill_menu"
                self.sub_cursor = 0
            elif choice == "Items":
                self.phase = "item_menu"
                self.sub_cursor = 0
            elif choice == "Flee":
                flee_chance = 0.5 + (self.hero.spd - self.enemy.spd) * 0.05
                if random.random() < max(0.1, min(0.9, flee_chance)):
                    self.log = ["Got away safely!"]
                    self.phase = "result"
                    self.result = ("fled",)
                else:
                    self.log = ["Couldn't escape!"]
                    self.phase = "enemy_turn"

    def _handle_skill_menu(self, inp):
        skills = self.hero.skills
        if inp.just_pressed("UP"):
            self.sub_cursor = (self.sub_cursor - 1) % len(skills)
        if inp.just_pressed("DOWN"):
            self.sub_cursor = (self.sub_cursor + 1) % len(skills)
        if inp.just_pressed("CANCEL"):
            self.phase = "player_menu"
        if inp.just_pressed("CONFIRM"):
            sk_name = skills[self.sub_cursor]
            sk = SKILLS[sk_name]
            if self.hero.mp < sk["mp"]:
                self.log = [f"Not enough MP! ({sk['mp']} needed)"]
            else:
                self.hero.mp -= sk["mp"]
                self._apply_skill(sk_name, sk)
            self.phase = "player_menu"

    def _handle_item_menu(self, inp):
        usable = [(k, v) for k, v in self.hero.inventory.items()
                  if v > 0 and ITEMS.get(k, {}).get("type") in ("heal", "mp", "cure")]
        if not usable:
            self.log = ["No usable items!"]
            self.phase = "player_menu"
            return
        if inp.just_pressed("UP"):
            self.sub_cursor = (self.sub_cursor - 1) % len(usable)
        if inp.just_pressed("DOWN"):
            self.sub_cursor = (self.sub_cursor + 1) % len(usable)
        if inp.just_pressed("CANCEL"):
            self.phase = "player_menu"
        if inp.just_pressed("CONFIRM"):
            name, _ = usable[self.sub_cursor]
            self._use_item(name)
            self.phase = "player_menu"

    # ── Combat logic ───────────────────────────────────────────────

    def _player_attack_basic(self):
        dmg = self._calc_phys(self.hero.eff_atk(), self.enemy.defense)
        self.enemy.hp -= dmg
        self.log = [f"You attack for {dmg} damage!"]
        self.flash_color = PAL["ui_red"]
        self.flash_timer = 8
        self._check_enemy_dead()

    def _apply_skill(self, name: str, sk: dict):
        t = sk["type"]
        if t == "atk":
            dmg = self._calc_phys(int(self.hero.eff_atk() * sk["power"]), self.enemy.defense)
            self.enemy.hp -= dmg
            self.log = [f"{name}: {dmg} damage!"]
            self.flash_color = PAL["ui_red"]; self.flash_timer = 10
            if name == "Berserker":
                self.enemy.def_half = True
                self.log.append("Enemy DEF halved!")
            self._check_enemy_dead()
        elif t == "mag":
            dmg = self._calc_mag(int(self.hero.eff_mag() * sk["power"]))
            self.enemy.hp -= dmg
            self.log = [f"{name}: {dmg} magic damage!"]
            self.flash_color = PAL["light_blue"]; self.flash_timer = 10
            if name == "Thunder" and random.random() < 0.3:
                self.enemy.status = "paralyzed"; self.enemy.status_turns = 2
                self.log.append("Enemy paralyzed!")
            elif name == "Ice Lance":
                self.enemy.status = "slow"; self.enemy.status_turns = 3
                self.log.append("Enemy slowed!")
            self._check_enemy_dead()
        elif t == "stun":
            self.enemy.status = "stun"; self.enemy.status_turns = 1
            self.log = [f"{name}: Enemy stunned!"]
        elif t == "buff":
            self.hero.atk += 3  # simplified buff
            self.log = [f"{name}: ATK raised!"]
        elif t == "dot":
            if not self.enemy.status:
                self.enemy.status = "poison"; self.enemy.status_turns = 3
                self.log = [f"{name}: Enemy poisoned!"]
            else:
                self.log = [f"{name}: Misses — already afflicted."]
        elif t == "debuff":
            self.enemy.defense = max(0, self.enemy.defense - 2)
            self.log = [f"{name}: Enemy accuracy/def lowered!"]
        elif t == "heal":
            heal = int(self.hero.max_hp * 0.4)
            self.hero.hp = min(self.hero.max_hp, self.hero.hp + heal)
            self.log = [f"{name}: Recovered {heal} HP!"]

    def _use_item(self, name: str):
        item = ITEMS[name]
        if item["type"] == "heal":
            heal = item["value"]
            self.hero.hp = min(self.hero.max_hp, self.hero.hp + heal)
            self.log = [f"Used {name}: +{heal} HP"]
        elif item["type"] == "mp":
            self.hero.mp = min(self.hero.max_mp, self.hero.mp + item["value"])
            self.log = [f"Used {name}: +{item['value']} MP"]
        elif item["type"] == "cure":
            self.log = [f"Used {name}: Cured poison/status"]
        self.hero.inventory[name] -= 1
        if self.hero.inventory[name] == 0:
            del self.hero.inventory[name]
        self.phase = "enemy_turn"

    def _do_enemy_turn(self):
        e = self.enemy
        # Status tick
        if e.status == "stun" or e.status == "paralyzed":
            e.status_turns -= 1
            if e.status_turns <= 0:
                e.status = None
            self.log = [f"{e.name} is {e.status or 'free'} — skips turn!"]
            self.phase = "player_menu"
            return
        if e.status == "poison":
            pdmg = max(1, e.max_hp // 10)
            e.hp -= pdmg
            self.log = [f"{e.name} takes {pdmg} poison damage!"]
            e.status_turns -= 1
            if e.status_turns <= 0:
                e.status = None
            if e.hp <= 0:
                self._enemy_dead()
                return

        # Pick skill
        sk_name = random.choice(e.skills)
        sk = SKILLS[sk_name]
        t = sk["type"]
        if t in ("atk",):
            atk = e.atk if e.status != "slow" else e.atk // 2
            dmg = self._calc_phys(int(atk * sk["power"]), self.hero.eff_def())
            self.hero.hp -= dmg
            self.log.append(f"{e.name} uses {sk_name}: {dmg} damage!")
            self.shake = 6
        elif t == "mag":
            dmg = self._calc_mag(int(e.mag * sk["power"]))
            self.hero.hp -= dmg
            self.log.append(f"{e.name} casts {sk_name}: {dmg} magic!")
            self.shake = 4
        elif t == "heal":
            heal = int(e.max_hp * 0.2)
            e.hp = min(e.max_hp, e.hp + heal)
            self.log.append(f"{e.name} heals {heal} HP!")
        elif t in ("debuff", "dot", "stun"):
            self.log.append(f"{e.name} uses {sk_name}!")

        if self.hero.hp <= 0:
            self.hero.hp = 0
            self.log.append("You were defeated...")
            self.phase = "result"
            self.result = ("lose",)
        else:
            self.phase = "player_menu"

    def _check_enemy_dead(self):
        if self.enemy.hp <= 0:
            self.enemy.hp = 0
            self._enemy_dead()
        else:
            self.phase = "enemy_turn"

    def _enemy_dead(self):
        e = self.enemy
        self._loot = {"xp": e.xp, "gold": e.gold, "items": {}}
        for item, chance in e.loot.items():
            if random.random() < chance:
                self._loot["items"][item] = 1
        self.log = [f"{e.name} defeated!", f"+{e.xp} XP  +{e.gold} Gold"]
        if self._loot["items"]:
            self.log.append("Found: " + ", ".join(self._loot["items"]))
        self.phase = "result"
        self.result = ("win", self._loot)

    # ── Damage formulas ────────────────────────────────────────────

    @staticmethod
    def _calc_phys(atk: int, defense: int) -> int:
        base = max(1, atk - defense // 2)
        return max(1, base + random.randint(-base // 4, base // 4))

    @staticmethod
    def _calc_mag(power: int) -> int:
        return max(1, power + random.randint(0, power // 3))

    # ── Anim tick ─────────────────────────────────────────────────

    def _tick_anim(self):
        self.anim_timer -= 1
        if self.anim_timer <= 0:
            self.phase = "enemy_turn"

    # ── Render ─────────────────────────────────────────────────────

    def render(self, surf: pygame.Surface):
        surf.fill(PAL["ui_dark"])

        # Background gradient suggestion
        for row in range(SCREEN_H // 4):
            alpha = int(30 * row / (SCREEN_H // 4))
            pygame.draw.rect(surf, (10, 10, 20 + alpha), (0, row * 4, SCREEN_W, 4))

        ox = self.shake * random.choice([-1, 0, 1]) if self.shake > 0 else 0
        oy = self.shake * random.choice([-1, 0, 1]) if self.shake > 0 else 0
        if self.shake > 0: self.shake -= 1

        # Enemy sprite
        e_sprite = get_sprite(self.enemy.name, scale=2 if not self.enemy.is_boss else 1.5)
        ew, eh = e_sprite.get_size()
        ex = SCREEN_W * 2 // 3 - ew // 2 + ox
        ey = 60 + oy
        if self.flash_timer > 0:
            tinted = e_sprite.copy()
            tinted.fill(self.flash_color + (120,), special_flags=pygame.BLEND_RGBA_ADD)
            surf.blit(tinted, (ex, ey))
            self.flash_timer -= 1
        else:
            surf.blit(e_sprite, (ex, ey))

        # Enemy info panel
        draw_panel(surf, SCREEN_W // 2, 10, 220, 46)
        draw_text(surf, self.enemy.name, SCREEN_W // 2 + 6, 13,
                  PAL["ui_red"] if self.enemy.is_boss else PAL["ui_gold"], 13, bold=True)
        draw_bar(surf, SCREEN_W // 2 + 6, 28, 200, 10,
                 self.enemy.hp, self.enemy.max_hp, PAL["hp_red"])
        draw_text(surf, f"HP {self.enemy.hp}/{self.enemy.max_hp}",
                  SCREEN_W // 2 + 6, 40, PAL["ui_dim"], 11)
        if self.enemy.status:
            draw_text(surf, f"[{self.enemy.status.upper()}]",
                      SCREEN_W // 2 + 140, 40, PAL["yellow"], 11)

        # Hero sprite
        h_sprite = get_sprite(self.hero.cls, scale=2)
        hw, hh = h_sprite.get_size()
        surf.blit(h_sprite, (60 - hw // 2, SCREEN_H - hh - 60))

        # Hero stats panel
        draw_panel(surf, 6, SCREEN_H - 72, 210, 66)
        draw_text(surf, f"{self.hero.name} Lv{self.hero.lv}",
                  12, SCREEN_H - 70, PAL["ui_gold"], 12, bold=True)
        draw_bar(surf, 12, SCREEN_H - 56, 160, 9, self.hero.hp, self.hero.max_hp, PAL["hp_red"])
        draw_text(surf, f"HP {self.hero.hp}/{self.hero.max_hp}", 12, SCREEN_H - 46, PAL["ui_dim"], 10)
        draw_bar(surf, 12, SCREEN_H - 34, 160, 9, self.hero.mp, self.hero.max_mp, PAL["mp_blue"])
        draw_text(surf, f"MP {self.hero.mp}/{self.hero.max_mp}", 12, SCREEN_H - 24, PAL["ui_dim"], 10)

        # Battle menu
        menu_x, menu_y = 226, SCREEN_H - 72
        draw_panel(surf, menu_x, menu_y, 250, 66)

        if self.phase == "player_menu":
            for i, opt in enumerate(self.MENU_ITEMS):
                col = PAL["cursor"] if i == self.cursor else PAL["ui_text"]
                prefix = "▶ " if i == self.cursor else "  "
                draw_text(surf, prefix + opt, menu_x + 8 + (i % 2) * 118,
                          menu_y + 8 + (i // 2) * 22, col, 13)

        elif self.phase == "skill_menu":
            draw_text(surf, "SKILLS", menu_x + 8, menu_y + 4, PAL["ui_gold"], 11, bold=True)
            for i, sk_name in enumerate(self.hero.skills):
                sk = SKILLS[sk_name]
                col = PAL["cursor"] if i == self.sub_cursor else PAL["ui_text"]
                mp_col = PAL["mp_blue"] if self.hero.mp >= sk["mp"] else PAL["ui_red"]
                prefix = "▶ " if i == self.sub_cursor else "  "
                draw_text(surf, prefix + sk_name, menu_x + 8, menu_y + 18 + i * 14, col, 11)
                draw_text(surf, f"{sk['mp']}MP", menu_x + 185, menu_y + 18 + i * 14, mp_col, 10)

        elif self.phase == "item_menu":
            draw_text(surf, "ITEMS", menu_x + 8, menu_y + 4, PAL["ui_gold"], 11, bold=True)
            usable = [(k, v) for k, v in self.hero.inventory.items()
                      if v > 0 and ITEMS.get(k, {}).get("type") in ("heal", "mp", "cure")]
            for i, (nm, cnt) in enumerate(usable):
                col = PAL["cursor"] if i == self.sub_cursor else PAL["ui_text"]
                draw_text(surf, f"{'▶' if i==self.sub_cursor else ' '} {nm} x{cnt}",
                          menu_x + 8, menu_y + 18 + i * 14, col, 11)

        # Battle log
        log_y = 172
        draw_panel(surf, 6, log_y, SCREEN_W - 12, 52)
        for i, line in enumerate(self.log[-3:]):
            draw_text(surf, line, 12, log_y + 4 + i * 16, PAL["ui_text"], 12)

        # Result overlay
        if self.phase == "result":
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            surf.blit(overlay, (0, 0))
            if self.result and self.result[0] == "win":
                draw_text(surf, "VICTORY!", SCREEN_W // 2 - 50, SCREEN_H // 2 - 20,
                          PAL["ui_gold"], 22, bold=True)
            elif self.result and self.result[0] == "lose":
                draw_text(surf, "DEFEATED", SCREEN_W // 2 - 55, SCREEN_H // 2 - 20,
                          PAL["ui_red"], 22, bold=True)
            elif self.result and self.result[0] == "fled":
                draw_text(surf, "ESCAPED", SCREEN_W // 2 - 45, SCREEN_H // 2 - 20,
                          PAL["light_blue"], 22, bold=True)
            draw_text(surf, "Press Z / CONFIRM", SCREEN_W // 2 - 70, SCREEN_H // 2 + 14,
                      PAL["ui_dim"], 12)


# ═══════════════════════════════════════════════════════════════════
#  WORLD MAP
# ═══════════════════════════════════════════════════════════════════

class WorldMap:
    """
    Renders the tiled overworld, handles movement, encounters, town/dungeon entry.
    """

    CAMERA_MARGIN = 5  # tiles from edge before camera starts scrolling

    def __init__(self, hero: Hero, screen: pygame.Surface):
        self.hero   = hero
        self.screen = screen
        self.cam_x  = 0  # top-left tile of viewport
        self.cam_y  = 0
        self.step_count = 0
        self.message: Optional[str]  = None
        self.message_timer: int      = 0
        self._update_camera()

    # ── Viewport ───────────────────────────────────────────────────

    def _update_camera(self):
        vw = SCREEN_W // TILE
        vh = SCREEN_H // TILE
        self.cam_x = max(0, min(self.hero.x - vw // 2, MAP_W - vw))
        self.cam_y = max(0, min(self.hero.y - vh // 2, MAP_H - vh))

    # ── Movement & events ──────────────────────────────────────────

    def step(self, inp: InputManager):
        """Returns None or a scene transition tuple."""
        dx = dy = 0
        if inp.just_pressed("UP"):    dy = -1
        if inp.just_pressed("DOWN"):  dy =  1
        if inp.just_pressed("LEFT"):  dx = -1
        if inp.just_pressed("RIGHT"): dx =  1

        if dx != 0 or dy != 0:
            nx, ny = self.hero.x + dx, self.hero.y + dy
            if 0 <= nx < MAP_W and 0 <= ny < MAP_H:
                tile = WORLD_MAP[ny][nx]
                if TILE_WALKABLE.get(tile, False):
                    self.hero.x, self.hero.y = nx, ny
                    self._update_camera()
                    self.step_count += 1

                    # Town entry
                    pos = (nx, ny)
                    if pos in TOWNS:
                        return ("town", pos)

                    # Dungeon entry
                    if pos in DUNGEONS:
                        return ("dungeon", pos)

                    # Boss encounter
                    if (nx, ny) == BOSS_POS:
                        return ("battle", BOSS_ENEMY)

                    # NPC interaction check (adjacent on confirm handled below)
                    # Random encounter
                    if TILE_ENCOUNTER.get(tile, False):
                        enc_rate = 0.12 if tile == 8 else 0.08
                        if random.random() < enc_rate:
                            table = TILE_ENCOUNTER_TABLE.get(tile, ["Slime"])
                            return ("battle", random.choice(table))

        # NPC talk
        if inp.just_pressed("CONFIRM"):
            npc = NPCS.get((self.hero.x, self.hero.y)) or NPCS.get((self.hero.x, self.hero.y - 1))
            if npc:
                self.message = npc[0]
                self.message_timer = 180
                return None

        # Dismiss message
        if self.message_timer > 0:
            self.message_timer -= 1
            if self.message_timer == 0:
                self.message = None

        return None

    # ── Render ─────────────────────────────────────────────────────

    def render(self, surf: pygame.Surface):
        vw = SCREEN_W // TILE
        vh = SCREEN_H // TILE

        for ty in range(vh + 1):
            for tx in range(vw + 1):
                mx = self.cam_x + tx
                my = self.cam_y + ty
                if 0 <= mx < MAP_W and 0 <= my < MAP_H:
                    tile = WORLD_MAP[my][mx]
                    color = TILE_COLORS.get(tile, PAL["black"])
                    rect = (tx * TILE, ty * TILE, TILE, TILE)
                    pygame.draw.rect(surf, color, rect)

                    # Tile details
                    if tile == 7:  # town — draw a small house silhouette
                        cx, cy = tx * TILE + TILE // 2, ty * TILE + TILE // 2
                        pygame.draw.rect(surf, PAL["tan"], (cx - 4, cy - 1, 8, 6))
                        pygame.draw.polygon(surf, PAL["dark_brown"],
                                            [(cx - 5, cy - 1), (cx, cy - 7), (cx + 5, cy - 1)])
                    elif tile == 8:  # dungeon — dark archway
                        cx, cy = tx * TILE + TILE // 2, ty * TILE + TILE // 2
                        pygame.draw.rect(surf, PAL["black"], (cx - 3, cy - 3, 6, 6))
                        pygame.draw.arc(surf, PAL["gray"],
                                        (cx - 4, cy - 6, 8, 8), 0, math.pi, 2)
                    elif tile == 4:  # forest — tree dots
                        pygame.draw.circle(surf, PAL["green"],
                                           (tx * TILE + 6, ty * TILE + 6), 3)
                        pygame.draw.circle(surf, PAL["green"],
                                           (tx * TILE + 11, ty * TILE + 11), 3)
                    elif tile in (5, 6):  # mountain / snow — triangle
                        cx = tx * TILE + TILE // 2
                        c = PAL["white"] if tile == 6 else PAL["light_gray"]
                        pygame.draw.polygon(surf, c,
                                            [(cx, ty * TILE + 2),
                                             (tx * TILE + 2, ty * TILE + TILE - 2),
                                             (tx * TILE + TILE - 2, ty * TILE + TILE - 2)])

        # Hero sprite
        hx = (self.hero.x - self.cam_x) * TILE
        hy = (self.hero.y - self.cam_y) * TILE
        h_sprite = get_sprite(self.hero.cls, scale=0.5)
        hw, hh = h_sprite.get_size()
        surf.blit(h_sprite, (hx + TILE // 2 - hw // 2, hy + TILE // 2 - hh // 2))

        # HUD
        self._render_hud(surf)

        # Message
        if self.message:
            draw_panel(surf, 10, SCREEN_H - 40, SCREEN_W - 20, 30)
            draw_text(surf, self.message, 16, SCREEN_H - 34, PAL["ui_text"], 12)

        # Mini-map
        self._render_minimap(surf)

    def _render_hud(self, surf):
        draw_panel(surf, 4, 4, 160, 38)
        draw_text(surf, f"{self.hero.name}  Lv{self.hero.lv}", 8, 6, PAL["ui_gold"], 11, bold=True)
        draw_bar(surf, 8, 18, 140, 7, self.hero.hp, self.hero.max_hp, PAL["hp_red"])
        draw_text(surf, f"HP {self.hero.hp}/{self.hero.max_hp}", 8, 27, PAL["ui_dim"], 10)
        draw_bar(surf, 8, 27, 60, 4, self.hero.mp, self.hero.max_mp, PAL["mp_blue"])
        xp_needed = self.hero.xp_to_next()
        draw_bar(surf, 8, 33, 140, 4, self.hero.xp, xp_needed, PAL["xp_yellow"])

        draw_text(surf, f"G:{self.hero.gold}", SCREEN_W - 70, 6, PAL["ui_gold"], 11)

    def _render_minimap(self, surf):
        mm_x, mm_y = SCREEN_W - 66, 4
        mm_w, mm_h = 62, 42
        draw_panel(surf, mm_x, mm_y, mm_w, mm_h)
        scale_x = mm_w / MAP_W
        scale_y = mm_h / MAP_H
        for ty in range(MAP_H):
            for tx in range(MAP_W):
                tile = WORLD_MAP[ty][tx]
                c = TILE_COLORS.get(tile, PAL["black"])
                rx = int(mm_x + tx * scale_x)
                ry = int(mm_y + ty * scale_y)
                pygame.draw.rect(surf, c, (rx, ry, max(1, int(scale_x)), max(1, int(scale_y))))
        # Hero dot
        hx = int(mm_x + self.hero.x * scale_x)
        hy = int(mm_y + self.hero.y * scale_y)
        pygame.draw.rect(surf, PAL["white"], (hx, hy, 2, 2))


# ═══════════════════════════════════════════════════════════════════
#  TOWN SCREEN
# ═══════════════════════════════════════════════════════════════════

class TownScreen:
    MENU = ["Shop", "Rest (30G)", "Leave"]

    def __init__(self, hero: Hero, town_pos: tuple, screen: pygame.Surface):
        self.hero     = hero
        self.town     = TOWNS[town_pos]
        self.screen   = screen
        self.cursor   = 0
        self.sub_cursor = 0
        self.mode     = "main"   # main | shop
        self.message  = ""

    def step(self, inp: InputManager):
        if self.mode == "main":
            return self._main(inp)
        elif self.mode == "shop":
            return self._shop(inp)
        return None

    def _main(self, inp):
        if inp.just_pressed("UP"):
            self.cursor = (self.cursor - 1) % len(self.MENU)
        if inp.just_pressed("DOWN"):
            self.cursor = (self.cursor + 1) % len(self.MENU)
        if inp.just_pressed("CONFIRM"):
            choice = self.MENU[self.cursor]
            if choice == "Shop":
                self.mode = "shop"
                self.sub_cursor = 0
            elif choice.startswith("Rest"):
                if self.hero.gold >= 30:
                    self.hero.gold -= 30
                    self.hero.hp = self.hero.max_hp
                    self.hero.mp = self.hero.max_mp
                    self.message = "Rested! HP/MP fully restored."
                else:
                    self.message = "Not enough gold! (30G needed)"
            elif choice == "Leave":
                return ("world",)
        if inp.just_pressed("CANCEL"):
            return ("world",)
        return None

    def _shop(self, inp):
        items = self.town["shop"]
        if inp.just_pressed("UP"):
            self.sub_cursor = (self.sub_cursor - 1) % len(items)
        if inp.just_pressed("DOWN"):
            self.sub_cursor = (self.sub_cursor + 1) % len(items)
        if inp.just_pressed("CANCEL"):
            self.mode = "main"
        if inp.just_pressed("CONFIRM"):
            name = items[self.sub_cursor]
            item = ITEMS[name]
            price = item["price"]
            if self.hero.gold >= price:
                self.hero.gold -= price
                it = item.get("type")
                if it in ("heal", "mp", "cure", "key"):
                    self.hero.inventory[name] = self.hero.inventory.get(name, 0) + 1
                elif it == "weapon":
                    self.hero.equipment["weapon"] = name
                elif it == "armor":
                    self.hero.equipment["armor"] = name
                self.message = f"Bought {name}!"
            else:
                self.message = f"Need {price}G  (have {self.hero.gold}G)"
        return None

    def render(self, surf: pygame.Surface):
        surf.fill(PAL["ui_dark"])
        draw_window(surf, 10, 10, SCREEN_W - 20, SCREEN_H - 20, self.town["name"])

        if self.mode == "main":
            draw_text(surf, "Welcome, traveller!", 20, 30, PAL["ui_text"], 13)
            for i, opt in enumerate(self.MENU):
                col = PAL["cursor"] if i == self.cursor else PAL["ui_text"]
                draw_text(surf, ("▶ " if i == self.cursor else "  ") + opt,
                          30, 60 + i * 22, col, 13)
            # Hero stats
            draw_text(surf, f"HP {self.hero.hp}/{self.hero.max_hp}   Gold: {self.hero.gold}G",
                      20, SCREEN_H - 48, PAL["ui_dim"], 12)
            draw_text(surf, f"Equipped: {self.hero.equipment['weapon'] or 'none'} / "
                            f"{self.hero.equipment['armor'] or 'none'}",
                      20, SCREEN_H - 32, PAL["ui_dim"], 11)

        elif self.mode == "shop":
            draw_text(surf, "SHOP", 20, 30, PAL["ui_gold"], 13, bold=True)
            items = self.town["shop"]
            for i, name in enumerate(items):
                item = ITEMS[name]
                col = PAL["cursor"] if i == self.sub_cursor else PAL["ui_text"]
                pc = PAL["ui_red"] if self.hero.gold < item["price"] else PAL["ui_green"]
                draw_text(surf, ("▶ " if i == self.sub_cursor else "  ") + name,
                          30, 52 + i * 18, col, 12)
                draw_text(surf, f"{item['price']}G", 240, 52 + i * 18, pc, 12)
                if i == self.sub_cursor:
                    draw_text(surf, item["desc"], 30, 52 + i * 18 + 12, PAL["ui_dim"], 10)
            draw_text(surf, f"Gold: {self.hero.gold}G", 20, SCREEN_H - 30, PAL["ui_gold"], 12)

        if self.message:
            draw_panel(surf, 10, SCREEN_H - 52, SCREEN_W - 20, 24)
            draw_text(surf, self.message, 16, SCREEN_H - 48, PAL["ui_text"], 12)


# ═══════════════════════════════════════════════════════════════════
#  INTRO / CLASS SELECT
# ═══════════════════════════════════════════════════════════════════

class IntroScreen:
    def __init__(self, screen: pygame.Surface):
        self.screen      = screen
        self.stage       = "story"   # story | name | class_select
        self.story_idx   = 0
        self.story_timer = 0
        self._story_timer = 0
        self.name_chars  = list("Hero")
        self.name_cursor = len(self.name_chars)
        self.class_cursor = 0
        self.classes     = list(CLASSES.keys())
        self.done        = False
        self.result: Optional[Hero] = None
        self._alpha      = 0

    def step(self, inp: InputManager, pygame_events: list):
        if self.stage == "story":
            self._story_timer += 1 if hasattr(self, '_story_timer') else 0
            if inp.just_pressed("CONFIRM") or inp.just_pressed("CANCEL"):
                self.story_idx += 1
                if self.story_idx >= len(STORY):
                    self.stage = "name"

        elif self.stage == "name":
            for ev in pygame_events:
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_RETURN:
                        self.stage = "class_select"
                    elif ev.key == pygame.K_BACKSPACE:
                        if self.name_cursor > 0:
                            self.name_chars.pop(self.name_cursor - 1)
                            self.name_cursor -= 1
                    elif ev.unicode and ev.unicode.isprintable() and len(self.name_chars) < 10:
                        self.name_chars.insert(self.name_cursor, ev.unicode)
                        self.name_cursor += 1

        elif self.stage == "class_select":
            if inp.just_pressed("LEFT"):
                self.class_cursor = (self.class_cursor - 1) % len(self.classes)
            if inp.just_pressed("RIGHT"):
                self.class_cursor = (self.class_cursor + 1) % len(self.classes)
            if inp.just_pressed("CONFIRM"):
                name = "".join(self.name_chars).strip() or "Hero"
                cls  = self.classes[self.class_cursor]
                self.result = Hero(name=name, cls=cls)
                self.done   = True
            if inp.just_pressed("CANCEL"):
                self.stage = "name"

    def render(self, surf: pygame.Surface):
        surf.fill(PAL["dark_blue"])

        # Starfield
        random.seed(42)
        for _ in range(80):
            sx = random.randint(0, SCREEN_W)
            sy = random.randint(0, SCREEN_H)
            br = random.randint(100, 240)
            surf.set_at((sx, sy), (br, br, br))
        random.seed()

        if self.stage == "story":
            draw_text(surf, "ETERNAL SHARDS", SCREEN_W // 2 - 90, 40,
                      PAL["ui_gold"], 24, bold=True)
            if self.story_idx < len(STORY):
                txt = STORY[self.story_idx]
                # Word-wrap simple version
                words = txt.split()
                lines, line = [], ""
                for w in words:
                    if len(line) + len(w) + 1 < 48:
                        line += (" " if line else "") + w
                    else:
                        lines.append(line); line = w
                lines.append(line)
                for i, ln in enumerate(lines):
                    draw_text(surf, ln, 40, SCREEN_H // 2 - 20 + i * 22, PAL["ui_text"], 14)
            draw_text(surf, "Press Z / CONFIRM to continue",
                      SCREEN_W // 2 - 100, SCREEN_H - 40, PAL["ui_dim"], 12)

        elif self.stage == "name":
            draw_text(surf, "ENTER YOUR NAME", SCREEN_W // 2 - 80, 80,
                      PAL["ui_gold"], 16, bold=True)
            name_str = "".join(self.name_chars)
            nx = SCREEN_W // 2 - 80
            draw_panel(surf, nx - 4, 120, 200, 28)
            draw_text(surf, name_str, nx, 126, PAL["white"], 16)
            # Cursor blink
            if (pygame.time.get_ticks() // 500) % 2 == 0:
                cx = nx + self.name_cursor * 10
                pygame.draw.rect(surf, PAL["cursor"], (cx, 126, 2, 18))
            draw_text(surf, "Press ENTER when done", SCREEN_W // 2 - 80, 180, PAL["ui_dim"], 12)

        elif self.stage == "class_select":
            draw_text(surf, "CHOOSE YOUR CLASS", SCREEN_W // 2 - 95, 20,
                      PAL["ui_gold"], 16, bold=True)
            cw = 140
            total_w = len(self.classes) * cw + (len(self.classes) - 1) * 10
            start_x = SCREEN_W // 2 - total_w // 2
            for i, cls_name in enumerate(self.classes):
                cls  = CLASSES[cls_name]
                x    = start_x + i * (cw + 10)
                sel  = (i == self.class_cursor)
                col  = PAL["ui_gold"] if sel else PAL["ui_border"]
                draw_panel(surf, x, 50, cw, 200)
                pygame.draw.rect(surf, col, (x, 50, cw, 200), 2 if sel else 1)
                draw_text(surf, cls_name, x + cw // 2 - len(cls_name) * 4, 58,
                          cls["color"], 13, bold=sel)
                spr = get_sprite(cls_name, scale=2)
                sw, sh = spr.get_size()
                surf.blit(spr, (x + cw // 2 - sw // 2, 76))
                # Stats
                stats = [("HP", cls["hp"]), ("MP", cls["mp"]),
                         ("ATK", cls["atk"]), ("DEF", cls["def"]),
                         ("MAG", cls["mag"]), ("SPD", cls["spd"])]
                for si, (sn, sv) in enumerate(stats):
                    draw_text(surf, f"{sn}:{sv:2d}", x + 8, 170 + si * 12, PAL["ui_dim"], 10)
                # Description
                desc_words = cls["desc"].split()
                dl, dline = [], ""
                for w in desc_words:
                    if len(dline) + len(w) + 1 < 17:
                        dline += (" " if dline else "") + w
                    else:
                        dl.append(dline); dline = w
                dl.append(dline)
                for di, dln in enumerate(dl):
                    draw_text(surf, dln, x + 4, 236 + di * 11, PAL["ui_text"], 10)

            draw_text(surf, "◄ / ► to pick   Z to confirm",
                      SCREEN_W // 2 - 100, SCREEN_H - 28, PAL["ui_dim"], 12)


# ═══════════════════════════════════════════════════════════════════
#  MAIN GAME
# ═══════════════════════════════════════════════════════════════════

class Game:
    def __init__(self, serial_port: Optional[str] = None):
        pygame.init()
        pygame.display.set_caption("Eternal Shards")
        self.screen  = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock   = pygame.time.Clock()
        self.running = True

        # Controller
        self.ctrl = SerialController(port=serial_port)
        self.ctrl.start()
        self.inp  = InputManager(self.ctrl)

        # Screens / state
        self.phase: GamePhase = GamePhase.INTRO
        self.hero: Optional[Hero] = None
        self.intro   = IntroScreen(self.screen)
        self.world:  Optional[WorldMap]   = None
        self.town:   Optional[TownScreen] = None
        self.battle: Optional[BattleSystem] = None

        self._level_up_msgs: list = []
        self._lv_timer: int = 0

    # ── Run ────────────────────────────────────────────────────────

    def run(self):
        while self.running:
            pg_events = pygame.event.get()
            for ev in pg_events:
                if ev.type == pygame.QUIT:
                    self.running = False
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F4:
                    self.running = False   # Alt-F4 style

            self.inp.update(pg_events)
            self._tick(pg_events)
            self._draw()
            self.clock.tick(FPS)

        self.ctrl.stop()
        pygame.quit()

    # ── Tick ───────────────────────────────────────────────────────

    def _tick(self, pg_events):
        if self.phase == GamePhase.INTRO:
            self.intro.step(self.inp, pg_events)
            if self.intro.done:
                self.hero  = self.intro.result
                self.world = WorldMap(self.hero, self.screen)
                self.phase = GamePhase.WORLD

        elif self.phase == GamePhase.WORLD:
            result = self.world.step(self.inp)
            if result:
                self._handle_world_event(result)

        elif self.phase == GamePhase.TOWN:
            result = self.town.step(self.inp)
            if result and result[0] == "world":
                self.phase = GamePhase.WORLD

        elif self.phase == GamePhase.BATTLE:
            result = self.battle.step(self.inp)
            if result:
                self._handle_battle_result(result)

        elif self.phase == GamePhase.GAMEOVER:
            if self.inp.any_just_pressed():
                # Restart
                self.__init__()
                return

        elif self.phase == GamePhase.VICTORY:
            if self.inp.any_just_pressed():
                self.__init__()
                return

        # Level-up message timeout
        if self._lv_timer > 0:
            self._lv_timer -= 1

    def _handle_world_event(self, result: tuple):
        kind = result[0]
        if kind == "town":
            self.town  = TownScreen(self.hero, result[1], self.screen)
            self.phase = GamePhase.TOWN
        elif kind == "dungeon":
            d = DUNGEONS[result[1]]
            self.battle = BattleSystem(self.hero, d["boss"], self.screen)
            self.phase  = GamePhase.BATTLE
        elif kind == "battle":
            self.battle = BattleSystem(self.hero, result[1], self.screen)
            self.phase  = GamePhase.BATTLE

    def _handle_battle_result(self, result: tuple):
        if result[0] == "win":
            loot = result[1]
            self.hero.xp   += loot["xp"]
            self.hero.gold += loot["gold"]
            for item, cnt in loot.get("items", {}).items():
                self.hero.inventory[item] = self.hero.inventory.get(item, 0) + cnt

            # Level up loop
            while self.hero.xp >= self.hero.xp_to_next():
                self.hero.xp -= self.hero.xp_to_next()
                gains = self.hero.level_up()
                self._level_up_msgs = [f"Level Up! → Lv {self.hero.lv}"] + \
                                      [f"  {sn}: +{gn}" for sn, gn in gains]
                self._lv_timer = 180

            # Victory check
            if self.battle.enemy.name == BOSS_ENEMY:
                self.phase = GamePhase.VICTORY
            else:
                self.phase = GamePhase.WORLD

        elif result[0] == "lose":
            self.phase = GamePhase.GAMEOVER

        elif result[0] == "fled":
            self.phase = GamePhase.WORLD

    # ── Draw ───────────────────────────────────────────────────────

    def _draw(self):
        if self.phase == GamePhase.INTRO:
            self.intro.render(self.screen)

        elif self.phase == GamePhase.WORLD:
            self.world.render(self.screen)
            self._draw_level_up_overlay()

        elif self.phase == GamePhase.TOWN:
            self.town.render(self.screen)

        elif self.phase == GamePhase.BATTLE:
            self.battle.render(self.screen)

        elif self.phase == GamePhase.GAMEOVER:
            self.screen.fill(PAL["dark_red"])
            draw_text(self.screen, "GAME  OVER", SCREEN_W // 2 - 80, SCREEN_H // 2 - 30,
                      PAL["white"], 28, bold=True)
            draw_text(self.screen, "Press any button to restart",
                      SCREEN_W // 2 - 100, SCREEN_H // 2 + 20, PAL["ui_dim"], 13)

        elif self.phase == GamePhase.VICTORY:
            self.screen.fill(PAL["dark_blue"])
            draw_text(self.screen, "YOU WIN!", SCREEN_W // 2 - 70, SCREEN_H // 2 - 40,
                      PAL["ui_gold"], 30, bold=True)
            draw_text(self.screen, "The Dragon Malachar is slain.",
                      SCREEN_W // 2 - 110, SCREEN_H // 2, PAL["ui_text"], 14)
            draw_text(self.screen, "Press any button",
                      SCREEN_W // 2 - 64, SCREEN_H // 2 + 40, PAL["ui_dim"], 13)

        # Controller indicator (bottom-right, tiny)
        if self.ctrl.connected:
            pygame.draw.circle(self.screen, PAL["ui_green"],
                               (SCREEN_W - 8, SCREEN_H - 8), 4)
        else:
            pygame.draw.circle(self.screen, PAL["ui_dim"],
                               (SCREEN_W - 8, SCREEN_H - 8), 4)

        pygame.display.flip()

    def _draw_level_up_overlay(self):
        if self._lv_timer <= 0 or not self._level_up_msgs:
            return
        bx, by = SCREEN_W // 2 - 100, SCREEN_H // 2 - 20 - len(self._level_up_msgs) * 8
        bh = 20 + len(self._level_up_msgs) * 16
        draw_panel(self.screen, bx, by, 200, bh)
        pygame.draw.rect(self.screen, PAL["ui_gold"], (bx, by, 200, bh), 2)
        for i, msg in enumerate(self._level_up_msgs):
            col = PAL["ui_gold"] if i == 0 else PAL["ui_green"]
            draw_text(self.screen, msg, bx + 8, by + 4 + i * 16, col, 12, bold=(i == 0))


# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Eternal Shards RPG")
    parser.add_argument("--port", default=None,
                        help="Serial port for Xiao ESP32-C3 controller (auto-detected if omitted)")
    parser.add_argument("--list-ports", action="store_true",
                        help="List available serial ports and exit")
    args = parser.parse_args()

    if args.list_ports:
        if not SERIAL_AVAILABLE:
            print("pyserial not installed — `pip install pyserial`")
        else:
            ports = list(serial.tools.list_ports.comports())
            if ports:
                for p in ports:
                    print(f"  {p.device:20s}  {p.description}")
            else:
                print("No serial ports found.")
        return

    game = Game(serial_port=args.port)
    game.run()


if __name__ == "__main__":
    main()
