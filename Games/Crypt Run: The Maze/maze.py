#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║          C R Y P T - R U N   M A Z E                    ║
║  Single-file Pygame maze game — Xiao ESP32-C3 gamepad   ║
╚══════════════════════════════════════════════════════════╝

Controls (keyboard fallback):
  Arrow keys / WASD  → move
  R                  → restart current level
  Esc / Q            → quit

Serial controller (Xiao ESP32-C3, firmware: gamepad.ino):
  UP / DOWN / LEFT / RIGHT → move
  OPTIONS              → restart current level

Run:
  python maze.py                        # auto-detect controller
  python maze.py --port COM7            # explicit port
  python maze.py --port /dev/ttyUSB0
  python maze.py --list-ports
  python maze.py --cols 31 --rows 21    # custom maze size (must be odd)
"""

import sys
import os
import random
import time
import math
import argparse
import threading
import queue
from typing import Optional, List, Tuple

import pygame

# ── Optional PySerial ─────────────────────────────────────────────
try:
    import serial
    import serial.tools.list_ports
    SERIAL_OK = True
except ImportError:
    SERIAL_OK = False


# ═════════════════════════════════════════════════════════════════
#  CONSTANTS & PALETTE
# ═════════════════════════════════════════════════════════════════

SCREEN_W   = 640
SCREEN_H   = 480
FPS        = 60
TILE       = 20          # pixels per maze cell

# Palette — deep dungeon / neon-noir
C = {
    "bg":          (8,   8,  14),
    "wall":        (22,  26,  48),
    "wall_edge":   (50,  60, 110),
    "floor":       (14,  16,  28),
    "floor_alt":   (16,  18,  32),
    "player":      (80, 210, 255),
    "player_glow": (40, 120, 200),
    "exit":        (80, 255, 140),
    "exit_glow":   (20, 120,  60),
    "coin":        (255, 210,  40),
    "coin_glow":   (180, 140,  10),
    "key":         (255, 160,  40),
    "door":        (180,  80,  20),
    "trap":        (220,  50,  50),
    "trap_glow":   (120,  20,  20),
    "fog":         (8,    8,  14, 230),
    "ui_bg":       (12,  14,  24),
    "ui_border":   (60,  70, 130),
    "ui_text":     (200, 210, 240),
    "ui_dim":      (90, 100, 130),
    "ui_gold":     (255, 200,  50),
    "ui_cyan":     (80,  210, 255),
    "ui_red":      (220,  60,  60),
    "ui_green":    (80,  220, 120),
    "white":       (240, 240, 255),
    "black":       (0,    0,   0),
    "shadow":      (4,    4,   8),
}

# Particle types
PT_SPARK  = "spark"
PT_TRAIL  = "trail"
PT_PICKUP = "pickup"


# ═════════════════════════════════════════════════════════════════
#  SERIAL CONTROLLER
# ═════════════════════════════════════════════════════════════════

class SerialController:
    """Background-thread reader for Xiao ESP32-C3 gamepad firmware."""

    BTN = {0: "UP", 1: "DOWN", 2: "LEFT", 3: "RIGHT", 4: "OPTIONS"}

    def __init__(self, port: Optional[str] = None, baud: int = 115200):
        self.port   = port
        self.baud   = baud
        self._ser   = None
        self._thread = None
        self._stop  = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.connected = False
        self._state = [False] * 5

    @staticmethod
    def auto_detect() -> Optional[str]:
        if not SERIAL_OK:
            return None
        kw = ("xiao","esp32","ch340","ch341","cp210","usbmodem","ttyusb","ttyacm")
        for p in serial.tools.list_ports.comports():
            s = ((p.description or "") + (p.device or "")).lower()
            if any(k in s for k in kw):
                return p.device
        return None

    def start(self) -> bool:
        if not SERIAL_OK:
            return False
        port = self.port or self.auto_detect()
        if not port:
            print("[Serial] No controller found — keyboard-only mode.")
            return False
        try:
            self._ser = serial.Serial(port, self.baud, timeout=0.1)
            time.sleep(0.1)
            self._ser.reset_input_buffer()
            self.connected = True
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            print(f"[Serial] Connected → {port}")
            return True
        except Exception as e:
            print(f"[Serial] Cannot open {port}: {e}")
            return False

    def stop(self):
        self._stop.set()
        if self._ser and self._ser.is_open:
            try: self._ser.close()
            except: pass
        self.connected = False

    def drain(self) -> list:
        out = []
        while not self.events.empty():
            out.append(self.events.get_nowait())
        return out

    def _run(self):
        buf = b""
        while not self._stop.is_set():
            try:
                chunk = self._ser.read(64)
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    self._parse(line.decode(errors="ignore").strip())
            except Exception as e:
                if not self._stop.is_set():
                    print(f"[Serial] Error: {e}")
                break
        self.connected = False

    def _parse(self, line: str):
        if line.startswith("B") and len(line) == 6:
            ns = [c == "1" for c in line[1:6]]
            for i, (o, n) in enumerate(zip(self._state, ns)):
                if o != n:
                    self.events.put(("PRESSED" if n else "RELEASED", self.BTN[i]))
            self._state = ns
        elif line.startswith("READY:"):
            print(f"[Serial] Handshake: {line}")


# ═════════════════════════════════════════════════════════════════
#  INPUT MANAGER
# ═════════════════════════════════════════════════════════════════

class Input:
    KB = {
        "UP":      [pygame.K_UP,    pygame.K_w],
        "DOWN":    [pygame.K_DOWN,  pygame.K_s],
        "LEFT":    [pygame.K_LEFT,  pygame.K_a],
        "RIGHT":   [pygame.K_RIGHT, pygame.K_d],
        "RESTART": [pygame.K_r],
        "QUIT":    [pygame.K_ESCAPE, pygame.K_q],
    }
    SER = {"UP":"UP","DOWN":"DOWN","LEFT":"LEFT","RIGHT":"RIGHT","OPTIONS":"RESTART"}

    def __init__(self, ctrl: SerialController):
        self.ctrl = ctrl
        self._jp: set  = set()
        self._held: set = set()
        self._since: dict = {}
        self._repeat_delay = 0.20
        self._repeat_rate  = 0.09

    def update(self, events: list):
        self._jp.clear()
        for et, bn in self.ctrl.drain():
            a = self.SER.get(bn)
            if a:
                if et == "PRESSED":
                    self._jp.add(a); self._held.add(a); self._since[a] = time.time()
                else:
                    self._held.discard(a); self._since.pop(a, None)

        keys = pygame.key.get_pressed()
        now  = time.time()
        for action, ks in self.KB.items():
            for ev in events:
                if ev.type == pygame.KEYDOWN and ev.key in ks:
                    self._jp.add(action); self._held.add(action); self._since[action] = now
                if ev.type == pygame.KEYUP and ev.key in ks:
                    if not any(keys[k] for k in ks if k != ev.key):
                        self._held.discard(action); self._since.pop(action, None)
            if action in ("UP","DOWN","LEFT","RIGHT") and action in self._held:
                e = now - self._since.get(action, now)
                if e > self._repeat_delay:
                    phase = (e - self._repeat_delay) % self._repeat_rate
                    if phase < (1/FPS) * 1.5:
                        self._jp.add(action)

    def jp(self, a: str) -> bool: return a in self._jp
    def held(self, a: str) -> bool: return a in self._held
    def any_jp(self) -> bool: return bool(self._jp)


# ═════════════════════════════════════════════════════════════════
#  MAZE GENERATOR  (recursive backtracker / DFS)
# ═════════════════════════════════════════════════════════════════

class Maze:
    """
    Grid of cells.  Each cell is a bitmask of open walls:
      N=1  E=2  S=4  W=8
    Walls between cells are implicitly shared.
    """
    N, E, S, W = 1, 2, 4, 8
    OPP = {N: S, S: N, E: W, W: E}
    DIR = {N: (0,-1), E: (1,0), S: (0,1), W: (-1,0)}

    def __init__(self, cols: int, rows: int, seed: Optional[int] = None):
        # cols/rows must be odd for the pixel-wall grid
        self.cols = cols if cols % 2 == 1 else cols + 1
        self.rows = rows if rows % 2 == 1 else rows + 1
        self.cells: List[List[int]] = [[0]*self.cols for _ in range(self.rows)]
        self._rng  = random.Random(seed)
        self._generate()

    def _generate(self):
        visited = [[False]*self.cols for _ in range(self.rows)]
        stack   = [(0, 0)]
        visited[0][0] = True
        while stack:
            cx, cy = stack[-1]
            dirs = list(self.DIR.keys())
            self._rng.shuffle(dirs)
            moved = False
            for d in dirs:
                dx, dy = self.DIR[d]
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.cols and 0 <= ny < self.rows and not visited[ny][nx]:
                    self.cells[cy][cx] |= d
                    self.cells[ny][nx] |= self.OPP[d]
                    visited[ny][nx] = True
                    stack.append((nx, ny))
                    moved = True
                    break
            if not moved:
                stack.pop()

    def open_dirs(self, x: int, y: int) -> int:
        return self.cells[y][x]

    def can_go(self, x: int, y: int, d: int) -> bool:
        return bool(self.cells[y][x] & d)

    def to_pixel_grid(self) -> List[List[int]]:
        """Convert cell grid to a pixel grid (0=floor, 1=wall)."""
        pw = self.cols * 2 + 1
        ph = self.rows * 2 + 1
        g  = [[1]*pw for _ in range(ph)]
        for cy in range(self.rows):
            for cx in range(self.cols):
                px, py = cx*2+1, cy*2+1
                g[py][px] = 0
                if self.cells[cy][cx] & self.E and cx+1 < self.cols:
                    g[py][px+1] = 0
                if self.cells[cy][cx] & self.S and cy+1 < self.rows:
                    g[py+1][px] = 0
        return g


# ═════════════════════════════════════════════════════════════════
#  PARTICLE SYSTEM
# ═════════════════════════════════════════════════════════════════

class Particle:
    __slots__ = ("x","y","vx","vy","life","max_life","color","kind","r")

    def __init__(self, x,y,vx,vy,life,color,kind=PT_SPARK,r=2):
        self.x,self.y,self.vx,self.vy = x,y,vx,vy
        self.life = self.max_life = life
        self.color = color
        self.kind  = kind
        self.r     = r

    def update(self) -> bool:
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.06   # gravity (light)
        self.vx *= 0.92
        self.life -= 1
        return self.life > 0

    def draw(self, surf: pygame.Surface, ox: int, oy: int):
        frac = self.life / self.max_life
        alpha = int(255 * frac)
        r = max(1, int(self.r * frac))
        sx, sy = int(self.x) + ox, int(self.y) + oy
        if 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
            c = (*self.color[:3], alpha)
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, c, (r, r), r)
            surf.blit(s, (sx-r, sy-r))


class Particles:
    def __init__(self):
        self._pool: List[Particle] = []

    def emit(self, x, y, color, kind=PT_SPARK, n=6, speed=2.0, r=2, life=20):
        for _ in range(n):
            angle = random.uniform(0, math.tau)
            spd   = random.uniform(speed*0.4, speed)
            self._pool.append(Particle(
                x, y,
                math.cos(angle)*spd, math.sin(angle)*spd,
                life + random.randint(-4, 4),
                color, kind, r
            ))

    def update(self):
        self._pool = [p for p in self._pool if p.update()]

    def draw(self, surf: pygame.Surface, ox: int, oy: int):
        for p in self._pool:
            p.draw(surf, ox, oy)


# ═════════════════════════════════════════════════════════════════
#  FOG OF WAR
# ═════════════════════════════════════════════════════════════════

class FogOfWar:
    def __init__(self, pw: int, ph: int, radius: int = 5):
        self.pw = pw
        self.ph = ph
        self.radius = radius
        self.revealed = [[False]*pw for _ in range(ph)]
        self.visible  = [[False]*pw for _ in range(ph)]

    def update(self, px: int, py: int):
        # Clear visibility
        for row in self.visible:
            for i in range(len(row)):
                row[i] = False
        r = self.radius
        for dy in range(-r, r+1):
            for dx in range(-r, r+1):
                if dx*dx + dy*dy <= r*r:
                    nx, ny = px+dx, py+dy
                    if 0 <= nx < self.pw and 0 <= ny < self.ph:
                        self.visible[ny][nx]  = True
                        self.revealed[ny][nx] = True

    def is_visible(self, x, y) -> bool:
        if 0 <= x < self.pw and 0 <= y < self.ph:
            return self.visible[y][x]
        return False

    def is_revealed(self, x, y) -> bool:
        if 0 <= x < self.pw and 0 <= y < self.ph:
            return self.revealed[y][x]
        return False


# ═════════════════════════════════════════════════════════════════
#  LEVEL DATA
# ═════════════════════════════════════════════════════════════════

class Level:
    """
    Wraps a Maze, places the player/exit/coins/keys/doors/traps.
    px, py are pixel-grid coordinates (not cell coordinates).
    """
    def __init__(self, cols: int, rows: int, level_num: int, seed: Optional[int]=None):
        self.num  = level_num
        self.maze = Maze(cols, rows, seed=seed)
        self.grid = self.maze.to_pixel_grid()   # pixel grid
        self.pw   = len(self.grid[0])
        self.ph   = len(self.grid)

        # Floor cells (pixel coords)
        self._floors = [(x, y)
                        for y in range(self.ph)
                        for x in range(self.pw)
                        if self.grid[y][x] == 0]

        # Player start: top-left area
        self.start  = (1, 1)
        # Exit: bottom-right area
        ex = self.pw - 2
        ey = self.ph - 2
        # Walk to nearest floor
        while self.grid[ey][ex] != 0:
            ex -= 1
        self.exit = (ex, ey)

        # Coins
        n_coins = 8 + level_num * 2
        candidates = [p for p in self._floors if p not in (self.start, self.exit)]
        random.shuffle(candidates)
        self.coins: set = set(candidates[:n_coins])

        # Key & door (levels 2+)
        self.key_pos: Optional[Tuple] = None
        self.door_pos: Optional[Tuple] = None
        self.door_open = False
        if level_num >= 2 and len(candidates) > n_coins + 2:
            self.key_pos  = candidates[n_coins]
            # Place door on a bottleneck — just pick a floor tile near mid path
            self.door_pos = candidates[n_coins + 1]

        # Traps (levels 3+)
        self.traps: set = set()
        if level_num >= 3:
            n_traps = 3 + level_num
            trap_pool = candidates[n_coins + 2:]
            self.traps = set(trap_pool[:n_traps])

        # Fog of war
        self.fog = FogOfWar(self.pw, self.ph,
                            radius=max(3, 7 - level_num))

    def is_walkable(self, x: int, y: int) -> bool:
        if not (0 <= x < self.pw and 0 <= y < self.ph):
            return False
        if self.grid[y][x] == 1:
            return False
        if self.door_pos == (x, y) and not self.door_open:
            return False
        return True


# ═════════════════════════════════════════════════════════════════
#  RENDERER
# ═════════════════════════════════════════════════════════════════

def _font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont("monospace", size, bold=bold)

def _text(surf, txt, x, y, color, size=14, bold=False):
    f = _font(size, bold)
    s = f.render(txt, True, color)
    surf.blit(s, (x, y))
    return s.get_width()

def _panel(surf, x, y, w, h, col=None, border=True):
    c = col or C["ui_bg"]
    pygame.draw.rect(surf, c, (x, y, w, h))
    if border:
        pygame.draw.rect(surf, C["ui_border"], (x, y, w, h), 1)

def _glow_circle(surf, cx, cy, r, color, alpha=60):
    s = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color[:3], alpha), (r*2, r*2), r*2)
    surf.blit(s, (cx - r*2, cy - r*2), special_flags=pygame.BLEND_ALPHA_SDL2)


# ═════════════════════════════════════════════════════════════════
#  GAME
# ═════════════════════════════════════════════════════════════════

MAX_LEVELS = 7

class Game:
    def __init__(self, maze_cols: int = 15, maze_rows: int = 11,
                 serial_port: Optional[str] = None):
        pygame.init()
        pygame.display.set_caption("CRYPT-RUN  ·  Maze")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock  = pygame.time.Clock()
        self.running = True

        self.cols = maze_cols
        self.rows = maze_rows

        self.ctrl = SerialController(port=serial_port)
        self.ctrl.start()
        self.inp  = Input(self.ctrl)

        self.particles = Particles()
        self._tick_count = 0

        # Game state
        self.level_num    = 1
        self.score        = 0
        self.total_coins  = 0
        self.lives        = 3
        self.has_key      = False
        self.level: Optional[Level] = None
        self.px = self.py = 1          # pixel-grid position
        self.phase = "playing"         # playing | dead | level_clear | title | gameover | win

        self._move_cooldown = 0
        self._death_timer   = 0
        self._clear_timer   = 0
        self._blink         = 0
        self._cam_ox = self._cam_oy = 0   # camera offset (pixels)
        self._shake  = 0

        self._load_level(self.level_num)
        self.phase = "title"

    # ─── Level loading ────────────────────────────────────────────

    def _load_level(self, num: int):
        seed = num * 0xABCD + 0x1337
        c    = self.cols + (num-1)*2
        r    = self.rows + (num-1)*2
        c    = c if c % 2 == 1 else c + 1
        r    = r if r % 2 == 1 else r + 1
        self.level = Level(c, r, num, seed=seed)
        self.px, self.py = self.level.start
        self.has_key     = False
        self.level.fog.update(self.px, self.py)
        self._center_camera()

    # ─── Camera ───────────────────────────────────────────────────

    def _center_camera(self):
        lv = self.level
        map_w = lv.pw * TILE
        map_h = lv.ph * TILE
        # Maze viewport (left of HUD)
        vp_w = SCREEN_W - 160
        vp_h = SCREEN_H
        cx = self.px * TILE + TILE//2
        cy = self.py * TILE + TILE//2
        self._cam_ox = vp_w//2 - cx
        self._cam_oy = vp_h//2 - cy
        # Clamp
        self._cam_ox = min(0, max(vp_w - map_w, self._cam_ox))
        self._cam_oy = min(0, max(vp_h - map_h, self._cam_oy))

    # ─── Main loop ────────────────────────────────────────────────

    def run(self):
        while self.running:
            pg_events = pygame.event.get()
            for ev in pg_events:
                if ev.type == pygame.QUIT:
                    self.running = False
            self.inp.update(pg_events)
            self._tick(pg_events)
            self._draw()
            self.clock.tick(FPS)
        self.ctrl.stop()
        pygame.quit()

    # ─── Tick ─────────────────────────────────────────────────────

    def _tick(self, pg_events):
        self._tick_count += 1
        self._blink = (self._tick_count // 20) % 2

        if self.inp.jp("QUIT"):
            self.running = False
            return

        if self.phase == "title":
            if self.inp.any_jp():
                self.phase = "playing"
            return

        if self.phase == "gameover":
            if self.inp.any_jp():
                self._restart_game()
            return

        if self.phase == "win":
            if self.inp.any_jp():
                self._restart_game()
            return

        if self.phase == "dead":
            self._death_timer -= 1
            self.particles.update()
            if self._death_timer <= 0:
                if self.lives > 0:
                    self.px, self.py = self.level.start
                    self.has_key     = False
                    self.level.fog.update(self.px, self.py)
                    self._center_camera()
                    self.phase = "playing"
                else:
                    self.phase = "gameover"
            return

        if self.phase == "level_clear":
            self._clear_timer -= 1
            self.particles.update()
            if self._clear_timer <= 0:
                self.level_num += 1
                if self.level_num > MAX_LEVELS:
                    self.phase = "win"
                else:
                    self._load_level(self.level_num)
                    self.phase = "playing"
            return

        # ── playing ───────────────────────────────────────────────
        if self.inp.jp("RESTART"):
            self.lives -= 1
            if self.lives < 0:
                self.lives = 0
                self.phase = "gameover"
            else:
                self.px, self.py = self.level.start
                self.has_key     = False
                self.level.fog.update(self.px, self.py)
                self._center_camera()
            return

        moved = self._handle_move()
        if moved:
            self._check_tile()
            self._center_camera()
            self.level.fog.update(self.px, self.py)
            # Trail particles
            wx = self.px * TILE + TILE//2
            wy = self.py * TILE + TILE//2
            self.particles.emit(wx, wy, C["player_glow"],
                                kind=PT_TRAIL, n=3, speed=0.6, r=2, life=12)

        if self._shake > 0:
            self._shake -= 1

        self.particles.update()

    def _handle_move(self) -> bool:
        if self._move_cooldown > 0:
            self._move_cooldown -= 1
            return False
        dx = dy = 0
        if self.inp.jp("UP"):    dy = -1
        if self.inp.jp("DOWN"):  dy =  1
        if self.inp.jp("LEFT"):  dx = -1
        if self.inp.jp("RIGHT"): dx =  1
        if dx == 0 and dy == 0:
            return False
        nx, ny = self.px + dx, self.py + dy
        if self.level.is_walkable(nx, ny):
            self.px, self.py = nx, ny
            self._move_cooldown = 4
            return True
        # Wall bump particles
        wx = (self.px + (nx - self.px)*0.7) * TILE + TILE//2
        wy = (self.py + (ny - self.py)*0.7) * TILE + TILE//2
        self.particles.emit(wx, wy, C["wall_edge"], n=4, speed=1.5, life=10)
        return False

    def _check_tile(self):
        pos = (self.px, self.py)
        lv  = self.level

        # Coin
        if pos in lv.coins:
            lv.coins.discard(pos)
            self.score      += 10 + self.level_num * 2
            self.total_coins += 1
            wx = self.px * TILE + TILE//2
            wy = self.py * TILE + TILE//2
            self.particles.emit(wx, wy, C["coin"], kind=PT_PICKUP,
                                n=10, speed=2.5, r=3, life=22)

        # Key
        if lv.key_pos == pos:
            lv.key_pos = None
            self.has_key = True
            self.score   += 50
            wx = self.px * TILE + TILE//2
            wy = self.py * TILE + TILE//2
            self.particles.emit(wx, wy, C["key"], kind=PT_PICKUP,
                                n=14, speed=3.0, r=3, life=28)

        # Door — open if key held (already enforced by walkability, but consume key)
        if lv.door_pos == pos and self.has_key:
            lv.door_open = True
            self.has_key = False
            self.score   += 30

        # Trap
        if pos in lv.traps:
            self._trigger_trap()

        # Exit
        if pos == lv.exit:
            self.score       += 100 + len(lv.coins) * 5  # bonus for remaining coins
            self._clear_timer = 90
            self.phase        = "level_clear"
            wx = self.px * TILE + TILE//2
            wy = self.py * TILE + TILE//2
            for _ in range(4):
                self.particles.emit(wx, wy, C["exit"], kind=PT_PICKUP,
                                    n=10, speed=3.5, r=4, life=35)

    def _trigger_trap(self):
        self.lives -= 1
        self._shake = 12
        wx = self.px * TILE + TILE//2
        wy = self.py * TILE + TILE//2
        self.particles.emit(wx, wy, C["trap"], n=20, speed=3.5, r=4, life=30)
        if self.lives < 0:
            self.lives = 0
        self._death_timer = 80
        self.phase        = "dead"

    def _restart_game(self):
        self.level_num   = 1
        self.score       = 0
        self.total_coins = 0
        self.lives       = 3
        self.has_key     = False
        self.particles   = Particles()
        self._load_level(self.level_num)
        self.phase = "playing"

    # ─── Draw ─────────────────────────────────────────────────────

    def _draw(self):
        self.screen.fill(C["bg"])

        sx = random.randint(-self._shake, self._shake) if self._shake else 0
        sy = random.randint(-self._shake, self._shake) if self._shake else 0

        if self.phase == "title":
            self._draw_title()
        elif self.phase == "gameover":
            self._draw_maze(sx, sy)
            self._draw_hud()
            self._draw_overlay("GAME OVER", C["ui_red"],
                               sub=f"Score: {self.score}   Press any button")
        elif self.phase == "win":
            self._draw_maze(sx, sy)
            self._draw_hud()
            self._draw_overlay("YOU ESCAPED!", C["ui_gold"],
                               sub=f"Final Score: {self.score}   Press any button")
        elif self.phase == "dead":
            self._draw_maze(sx, sy)
            self._draw_hud()
            self._draw_overlay("TRAPPED!", C["ui_red"],
                               sub=f"Lives left: {self.lives}")
        elif self.phase == "level_clear":
            self._draw_maze(sx, sy)
            self._draw_hud()
            self._draw_overlay(f"LEVEL {self.level_num} CLEAR", C["ui_green"],
                               sub=f"Score: {self.score}")
        else:
            self._draw_maze(sx, sy)
            self._draw_hud()

        # Controller dot
        dot_c = C["ui_green"] if self.ctrl.connected else C["ui_dim"]
        pygame.draw.circle(self.screen, dot_c, (SCREEN_W - 8, SCREEN_H - 8), 4)
        pygame.display.flip()

    # ── Maze renderer ─────────────────────────────────────────────

    def _draw_maze(self, sx: int = 0, sy: int = 0):
        lv  = self.level
        ox  = self._cam_ox + sx
        oy  = self._cam_oy + sy

        # Clip to maze viewport
        vp_rect = pygame.Rect(0, 0, SCREEN_W - 160, SCREEN_H)
        self.screen.set_clip(vp_rect)

        # Draw tiles
        for ty in range(lv.ph):
            for tx in range(lv.pw):
                rx = tx * TILE + ox
                ry = ty * TILE + oy
                if rx + TILE < 0 or rx > vp_rect.w or ry + TILE < 0 or ry > SCREEN_H:
                    continue
                rev = lv.fog.is_revealed(tx, ty)
                vis = lv.fog.is_visible(tx, ty)
                if not rev:
                    continue
                dim_factor = 1.0 if vis else 0.35

                cell = lv.grid[ty][tx]
                if cell == 1:  # wall
                    wc = self._dim(C["wall"], dim_factor)
                    pygame.draw.rect(self.screen, wc, (rx, ry, TILE, TILE))
                    ec = self._dim(C["wall_edge"], dim_factor * 0.6)
                    pygame.draw.rect(self.screen, ec, (rx, ry, TILE, TILE), 1)
                else:          # floor
                    # Checkerboard subtle variation
                    fc = C["floor"] if (tx + ty) % 2 == 0 else C["floor_alt"]
                    fc = self._dim(fc, dim_factor)
                    pygame.draw.rect(self.screen, fc, (rx, ry, TILE, TILE))

        # Draw special tiles (only if visible or revealed)
        self._draw_specials(ox, oy, lv)

        # Particles
        self.particles.draw(self.screen, ox, oy)

        # Player
        if self.phase not in ("dead",):
            self._draw_player(ox, oy)

        self.screen.set_clip(None)

    def _draw_specials(self, ox, oy, lv):
        t = self._tick_count
        vis = lv.fog.is_visible
        rev = lv.fog.is_revealed

        # Exit
        ex, ey = lv.exit
        if vis(ex, ey):
            rx, ry = ex*TILE+ox, ey*TILE+oy
            pulse  = 0.7 + 0.3*math.sin(t * 0.08)
            pygame.draw.rect(self.screen, C["floor"], (rx, ry, TILE, TILE))
            r2 = int(TILE//2 * pulse)
            _glow_circle(self.screen, rx+TILE//2, ry+TILE//2, r2, C["exit_glow"], 80)
            pygame.draw.circle(self.screen, C["exit"],
                               (rx+TILE//2, ry+TILE//2), max(3, r2-2))
            if r2 > 4:
                pygame.draw.circle(self.screen, C["white"],
                                   (rx+TILE//2, ry+TILE//2), 2)

        # Coins
        for cx, cy in list(lv.coins):
            if not vis(cx, cy):
                continue
            rx, ry = cx*TILE+ox, cy*TILE+oy
            bob    = int(2*math.sin(t*0.12 + cx*0.7 + cy*0.5))
            cr     = TILE//2 - 3
            _glow_circle(self.screen, rx+TILE//2, ry+TILE//2+bob, cr, C["coin_glow"], 50)
            pygame.draw.circle(self.screen, C["coin"],
                               (rx+TILE//2, ry+TILE//2+bob), cr)
            pygame.draw.circle(self.screen, C["white"],
                               (rx+TILE//2-1, ry+TILE//2+bob-1), 1)

        # Key
        if lv.key_pos and vis(*lv.key_pos):
            kx, ky = lv.key_pos
            rx, ry = kx*TILE+ox, ky*TILE+oy
            bob    = int(2*math.sin(t*0.10))
            # Key shape: circle + line
            pygame.draw.circle(self.screen, C["key"],
                               (rx+TILE//2, ry+TILE//2-2+bob), 4)
            pygame.draw.circle(self.screen, C["floor"],
                               (rx+TILE//2, ry+TILE//2-2+bob), 2)
            pygame.draw.line(self.screen, C["key"],
                             (rx+TILE//2, ry+TILE//2+2+bob),
                             (rx+TILE//2, ry+TILE//2+7+bob), 2)
            pygame.draw.line(self.screen, C["key"],
                             (rx+TILE//2, ry+TILE//2+5+bob),
                             (rx+TILE//2+3, ry+TILE//2+5+bob), 2)

        # Door
        if lv.door_pos and not lv.door_open and rev(*lv.door_pos):
            dx, dy = lv.door_pos
            rx, ry = dx*TILE+ox, dy*TILE+oy
            dc     = C["door"] if vis(dx, dy) else self._dim(C["door"], 0.4)
            pygame.draw.rect(self.screen, dc, (rx+2, ry+1, TILE-4, TILE-2), border_radius=2)
            pygame.draw.rect(self.screen, self._dim(dc, 0.6),
                             (rx+2, ry+1, TILE-4, TILE-2), 1, border_radius=2)
            # Keyhole
            if vis(dx, dy):
                pygame.draw.circle(self.screen, C["wall"],
                                   (rx+TILE//2, ry+TILE//2-1), 2)
                pygame.draw.line(self.screen, C["wall"],
                                 (rx+TILE//2, ry+TILE//2+1),
                                 (rx+TILE//2, ry+TILE//2+4), 1)

        # Traps
        for tx2, ty2 in lv.traps:
            if not vis(tx2, ty2):
                continue
            rx, ry = tx2*TILE+ox, ty2*TILE+oy
            pulse  = 0.5 + 0.5*abs(math.sin(t*0.15))
            # Spike pattern
            for i in range(4):
                angle = i * math.pi/2 + t*0.03
                ex2   = rx+TILE//2 + int(math.cos(angle)*(TILE//2-3)*pulse)
                ey2   = ry+TILE//2 + int(math.sin(angle)*(TILE//2-3)*pulse)
                pygame.draw.line(self.screen, C["trap"],
                                 (rx+TILE//2, ry+TILE//2), (ex2, ey2), 1)
            pygame.draw.circle(self.screen, C["trap"],
                               (rx+TILE//2, ry+TILE//2), 2)

    def _draw_player(self, ox: int, oy: int):
        t  = self._tick_count
        rx = self.px * TILE + TILE//2 + ox
        ry = self.py * TILE + TILE//2 + oy
        # Glow
        _glow_circle(self.screen, rx, ry, 10, C["player_glow"], 70)
        # Body
        r = TILE//2 - 3
        pygame.draw.circle(self.screen, C["player"], (rx, ry), r)
        # Direction indicator (last move direction via tick)
        # Eyes
        ex1 = rx - 2
        ey1 = ry - 2
        pygame.draw.circle(self.screen, C["white"], (ex1, ey1), 2)
        pygame.draw.circle(self.screen, C["black"], (ex1, ey1), 1)
        pygame.draw.circle(self.screen, C["white"], (rx+2, ey1), 2)
        pygame.draw.circle(self.screen, C["black"], (rx+2, ey1), 1)
        # Pulse ring
        pulse_r = r + 2 + int(2*math.sin(t*0.15))
        pygame.draw.circle(self.screen, (*C["player_glow"], 120),
                           (rx, ry), pulse_r, 1)

    # ── HUD ───────────────────────────────────────────────────────

    def _draw_hud(self):
        hx = SCREEN_W - 158
        _panel(self.screen, hx, 0, 158, SCREEN_H)
        pygame.draw.line(self.screen, C["ui_border"], (hx, 0), (hx, SCREEN_H), 1)

        y = 10
        _text(self.screen, "CRYPT-RUN", hx+8, y, C["ui_gold"], 14, bold=True)
        y += 22
        pygame.draw.line(self.screen, C["ui_border"], (hx+4, y), (SCREEN_W-4, y), 1)
        y += 8

        _text(self.screen, f"LEVEL  {self.level_num}/{MAX_LEVELS}", hx+8, y, C["ui_cyan"], 12)
        y += 18
        _text(self.screen, f"SCORE  {self.score}", hx+8, y, C["ui_text"], 12)
        y += 18
        _text(self.screen, f"COINS  {self.total_coins}", hx+8, y, C["coin"], 12)
        y += 18

        # Lives
        _text(self.screen, "LIVES", hx+8, y, C["ui_dim"], 11)
        y += 14
        for i in range(3):
            col = C["player"] if i < self.lives else C["ui_border"]
            pygame.draw.circle(self.screen, col, (hx+14+i*18, y+6), 6)
            if i < self.lives:
                pygame.draw.circle(self.screen, C["player_glow"], (hx+14+i*18, y+6), 4)
        y += 22

        # Key indicator
        if self.has_key:
            _text(self.screen, "KEY ✦", hx+8, y, C["key"], 12, bold=True)
        else:
            _text(self.screen, "KEY  -", hx+8, y, C["ui_dim"], 12)
        y += 22

        pygame.draw.line(self.screen, C["ui_border"], (hx+4, y), (SCREEN_W-4, y), 1)
        y += 8

        # Minimap
        mm_w = 144
        mm_h = 100
        _panel(self.screen, hx+4, y, mm_w, mm_h)
        lv   = self.level
        sx   = mm_w / lv.pw
        sy2  = mm_h / lv.ph
        for ty in range(lv.ph):
            for tx in range(lv.pw):
                if not lv.fog.is_revealed(tx, ty):
                    continue
                c  = C["wall"] if lv.grid[ty][tx] == 1 else C["floor_alt"]
                if lv.grid[ty][tx] == 0 and lv.fog.is_visible(tx, ty):
                    c = C["floor"]
                mx = hx + 4 + int(tx * sx)
                my = y + int(ty * sy2)
                mw = max(1, int(sx))
                mh = max(1, int(sy2))
                pygame.draw.rect(self.screen, c, (mx, my, mw, mh))
        # Exit dot
        ex2, ey2 = lv.exit
        pygame.draw.rect(self.screen, C["exit"],
                         (hx+4+int(ex2*sx), y+int(ey2*sy2),
                          max(2,int(sx)), max(2,int(sy2))))
        # Player dot
        pygame.draw.rect(self.screen, C["player"],
                         (hx+4+int(self.px*sx), y+int(self.py*sy2),
                          max(2,int(sx)), max(2,int(sy2))))
        y += mm_h + 10

        pygame.draw.line(self.screen, C["ui_border"], (hx+4, y), (SCREEN_W-4, y), 1)
        y += 8

        # Controls reminder
        cmds = [("↑↓←→", "Move"), ("R / OPT", "Restart"), ("ESC/Q", "Quit")]
        for k, v in cmds:
            _text(self.screen, k, hx+8, y, C["ui_gold"], 10, bold=True)
            _text(self.screen, v, hx+64, y, C["ui_dim"], 10)
            y += 13

        # Objectives
        y += 6
        pygame.draw.line(self.screen, C["ui_border"], (hx+4, y), (SCREEN_W-4, y), 1)
        y += 6
        _text(self.screen, "OBJECTIVES", hx+8, y, C["ui_dim"], 10, bold=True)
        y += 14
        remaining = len(self.level.coins)
        _text(self.screen, f"Coins left: {remaining}", hx+8, y, C["coin"], 10)
        y += 12
        if self.level.key_pos:
            _text(self.screen, "Find the key!", hx+8, y, C["key"], 10)
            y += 12
        if self.level.door_pos and not self.level.door_open:
            col = C["ui_green"] if self.has_key else C["ui_red"]
            _text(self.screen, "Door: " + ("Unlocked!" if self.has_key else "Locked"),
                  hx+8, y, col, 10)
            y += 12
        _text(self.screen, "Reach the exit!", hx+8, y, C["exit"], 10)

    # ── Title screen ──────────────────────────────────────────────

    def _draw_title(self):
        self.screen.fill(C["bg"])
        t = self._tick_count

        # Starfield
        random.seed(99)
        for i in range(120):
            sx = random.randint(0, SCREEN_W)
            sy = random.randint(0, SCREEN_H)
            br = random.randint(40, 180)
            twinkle = abs(math.sin(t*0.04 + i*0.3))
            b2 = int(br * twinkle)
            if b2 > 20:
                self.screen.set_at((sx, sy), (b2, b2, b2+30))
        random.seed()

        # Draw a small animated maze preview in background
        lv = self.level
        scale = 8
        ox2 = SCREEN_W//2 - (lv.pw * scale)//2
        oy2 = SCREEN_H//2 - (lv.ph * scale)//2 + 40
        for ty in range(min(lv.ph, 20)):
            for tx in range(min(lv.pw, 40)):
                c = C["wall"] if lv.grid[ty][tx] == 1 else C["floor"]
                pygame.draw.rect(self.screen, self._dim(c, 0.4),
                                 (ox2+tx*scale, oy2+ty*scale, scale-1, scale-1))

        # Title text with glow effect
        title  = "CRYPT-RUN"
        sub    = "M A Z E"
        pulse  = 0.8 + 0.2*math.sin(t*0.07)
        tc     = tuple(int(c*pulse) for c in C["ui_gold"])
        f_big  = pygame.font.SysFont("monospace", 52, bold=True)
        f_sub  = pygame.font.SysFont("monospace", 20, bold=True)
        ts     = f_big.render(title, True, tc)
        ss     = f_sub.render(sub, True, C["ui_cyan"])
        tw, th = ts.get_size()
        self.screen.blit(ts, (SCREEN_W//2 - tw//2, 40))
        sw2    = ss.get_size()[0]
        self.screen.blit(ss, (SCREEN_W//2 - sw2//2, 100))

        # Info
        info = [
            f"Levels: {MAX_LEVELS}   Maze grows each floor",
            "Collect coins · Find keys · Avoid traps",
            "Reach the green exit to advance",
            "",
            "Press any button to start",
        ]
        for i, line in enumerate(info):
            col = C["white"] if i == len(info)-1 else C["ui_dim"]
            if not line:
                continue
            s2 = pygame.font.SysFont("monospace", 13).render(line, True, col)
            w2 = s2.get_size()[0]
            self.screen.blit(s2, (SCREEN_W//2 - w2//2, 148 + i*18))

        # Controller status
        dot_col = C["ui_green"] if self.ctrl.connected else C["ui_dim"]
        dot_txt = "Controller connected" if self.ctrl.connected else "Keyboard mode"
        pygame.draw.circle(self.screen, dot_col, (SCREEN_W//2 - 70, SCREEN_H - 28), 5)
        s3 = pygame.font.SysFont("monospace", 11).render(dot_txt, True, dot_col)
        self.screen.blit(s3, (SCREEN_W//2 - 60, SCREEN_H - 33))

    # ── Overlay ───────────────────────────────────────────────────

    def _draw_overlay(self, title: str, color, sub: str = ""):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        f1 = pygame.font.SysFont("monospace", 36, bold=True)
        f2 = pygame.font.SysFont("monospace", 14)
        s1 = f1.render(title, True, color)
        s2 = f2.render(sub, True, C["ui_dim"])
        w1, h1 = s1.get_size()
        w2, h2 = s2.get_size()
        self.screen.blit(s1, (SCREEN_W//2 - w1//2, SCREEN_H//2 - h1 - 6))
        if sub:
            self.screen.blit(s2, (SCREEN_W//2 - w2//2, SCREEN_H//2 + 8))

    # ── Utils ─────────────────────────────────────────────────────

    @staticmethod
    def _dim(color, factor: float):
        return tuple(max(0, int(c * factor)) for c in color[:3])


# ═════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="CRYPT-RUN Maze — Xiao ESP32-C3 gamepad")
    parser.add_argument("--port", default=None,
                        help="Serial port for controller (auto-detected if omitted)")
    parser.add_argument("--list-ports", action="store_true",
                        help="List available serial ports and exit")
    parser.add_argument("--cols", type=int, default=15,
                        help="Maze columns for level 1 (odd number, default 15)")
    parser.add_argument("--rows", type=int, default=11,
                        help="Maze rows for level 1 (odd number, default 11)")
    args = parser.parse_args()

    if args.list_ports:
        if not SERIAL_OK:
            print("pyserial not installed — run: pip install pyserial")
        else:
            ports = list(serial.tools.list_ports.comports())
            if ports:
                for p in ports:
                    print(f"  {p.device:20s}  {p.description}")
            else:
                print("No serial ports detected.")
        return

    c = args.cols if args.cols % 2 == 1 else args.cols + 1
    r = args.rows if args.rows % 2 == 1 else args.rows + 1

    game = Game(maze_cols=c, maze_rows=r, serial_port=args.port)
    game.run()


if __name__ == "__main__":
    main()
