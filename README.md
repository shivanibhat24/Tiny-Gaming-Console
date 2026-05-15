"""
╔══════════════════════════════════════════════════════════════╗
║                   2 0 4 8   ·   N E O N                     ║
║   Single-file Pygame 2048 — Xiao ESP32-C3 gamepad           ║
╚══════════════════════════════════════════════════════════════╝

Controls (keyboard):
  Arrow keys / WASD  → slide tiles
  R                  → new game
  U                  → undo (1 step)
  Esc / Q            → quit

Serial controller (Xiao ESP32-C3, gamepad.ino):
  UP / DOWN / LEFT / RIGHT → slide tiles
  OPTIONS (tap)            → new game
  OPTIONS (hold 1 s)       → undo

Run:
  python 2048.py
  python 2048.py --port COM7
  python 2048.py --port /dev/ttyUSB0
  python 2048.py --list-ports
"""

import sys
import os
import random
import math
import time
import argparse
import threading
import queue
import copy
from typing import Optional, List, Tuple

import pygame

# ── Optional PySerial ─────────────────────────────────────────
try:
    import serial
    import serial.tools.list_ports
    SERIAL_OK = True
except ImportError:
    SERIAL_OK = False


# ═════════════════════════════════════════════════════════════
#  CONSTANTS
# ═════════════════════════════════════════════════════════════

SCREEN_W = 520
SCREEN_H = 620
FPS      = 60

GRID_SIZE   = 4          # 4×4 board
GRID_PX     = 380        # pixel size of the board area
TILE_GAP    = 10
TILE_PX     = (GRID_PX - TILE_GAP * (GRID_SIZE + 1)) // GRID_SIZE
BOARD_X     = (SCREEN_W - GRID_PX) // 2
BOARD_Y     = 180

ANIM_SLIDE_FRAMES = 7    # frames for slide animation
ANIM_POP_FRAMES   = 10   # frames for merge pop animation

# ── Colour palette — deep neon-noir (matches maze.py) ─────────
C = {
    "bg":           (8,    8,   14),
    "board_bg":     (16,   18,   30),
    "board_border": (40,   48,   80),
    "empty":        (22,   26,   44),
    "ui_text":      (200, 210,  240),
    "ui_dim":       (80,   90,  120),
    "ui_gold":      (255, 200,   50),
    "ui_cyan":      (80,  210,  255),
    "ui_red":       (220,  60,   60),
    "ui_green":     (80,  220,  120),
    "white":        (240, 240,  255),
    "black":        (0,    0,    0),
    "shadow":       (4,    4,    8),
    # tile face colours keyed by power-of-2 (index = log2(value))
    "tiles": [
        (30,  34,  58),   # 0   (empty, unused)
        (50,  60, 100),   # 2
        (40,  90, 160),   # 4
        (30, 130, 200),   # 8
        (20, 170, 220),   # 16
        (60, 200, 160),   # 32
        (80, 220, 100),   # 64
        (180,220,  50),   # 128
        (240,190,  40),   # 256
        (255,150,  30),   # 512
        (255, 90,  40),   # 1024
        (220,  50, 80),   # 2048
        (200,  40,200),   # 4096
        (120,  60,220),   # 8192+
    ],
    "tile_text_dark":  (20,  24,  40),
    "tile_text_light": (240, 245, 255),
}


def tile_color(val: int) -> tuple:
    if val == 0:
        return C["empty"]
    idx = int(math.log2(val))
    idx = min(idx, len(C["tiles"]) - 1)
    return C["tiles"][idx]

def tile_text_color(val: int) -> tuple:
    if val == 0:
        return C["empty"]
    idx = int(math.log2(val))
    return C["tile_text_dark"] if idx >= 6 else C["tile_text_light"]


# ═════════════════════════════════════════════════════════════
#  SERIAL CONTROLLER  (identical pattern to maze.py)
# ═════════════════════════════════════════════════════════════

class SerialController:
    BTN = {0: "UP", 1: "DOWN", 2: "LEFT", 3: "RIGHT", 4: "OPTIONS"}

    def __init__(self, port: Optional[str] = None, baud: int = 115200):
        self.port    = port
        self.baud    = baud
        self._ser    = None
        self._thread = None
        self._stop   = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.connected = False
        self._state  = [False] * 5

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


# ═════════════════════════════════════════════════════════════
#  INPUT MANAGER
# ═════════════════════════════════════════════════════════════

class Input:
    KB = {
        "UP":      [pygame.K_UP,    pygame.K_w],
        "DOWN":    [pygame.K_DOWN,  pygame.K_s],
        "LEFT":    [pygame.K_LEFT,  pygame.K_a],
        "RIGHT":   [pygame.K_RIGHT, pygame.K_d],
        "NEW":     [pygame.K_r],
        "UNDO":    [pygame.K_u],
        "QUIT":    [pygame.K_ESCAPE, pygame.K_q],
    }
    SER_MAP = {
        "UP":    "UP",
        "DOWN":  "DOWN",
        "LEFT":  "LEFT",
        "RIGHT": "RIGHT",
    }
    OPTIONS_HOLD_SECS = 1.0   # hold OPTIONS this long → undo; tap → new game

    def __init__(self, ctrl: SerialController):
        self.ctrl = ctrl
        self._jp:   set  = set()
        self._held: set  = set()
        self._opt_press_time: Optional[float] = None

    def update(self, pg_events: list):
        self._jp.clear()

        # ── Serial events ──────────────────────────────────────
        for et, bn in self.ctrl.drain():
            if bn == "OPTIONS":
                if et == "PRESSED":
                    self._opt_press_time = time.time()
                elif et == "RELEASED":
                    if self._opt_press_time is not None:
                        held = time.time() - self._opt_press_time
                        self._jp.add("UNDO" if held >= self.OPTIONS_HOLD_SECS else "NEW")
                    self._opt_press_time = None
            else:
                act = self.SER_MAP.get(bn)
                if act:
                    if et == "PRESSED":
                        self._jp.add(act)
                        self._held.add(act)
                    else:
                        self._held.discard(act)

        # ── Keyboard events ────────────────────────────────────
        for ev in pg_events:
            if ev.type == pygame.KEYDOWN:
                for action, keys in self.KB.items():
                    if ev.key in keys:
                        self._jp.add(action)
                        self._held.add(action)
            if ev.type == pygame.KEYUP:
                for action, keys in self.KB.items():
                    if ev.key in keys:
                        self._held.discard(action)

    def jp(self, a: str) -> bool:
        return a in self._jp

    def any_dir(self) -> Optional[str]:
        for d in ("UP","DOWN","LEFT","RIGHT"):
            if d in self._jp:
                return d
        return None


# ═════════════════════════════════════════════════════════════
#  BOARD LOGIC
# ═════════════════════════════════════════════════════════════

Grid = List[List[int]]


def empty_grid() -> Grid:
    return [[0]*GRID_SIZE for _ in range(GRID_SIZE)]


def spawn_tile(grid: Grid, rng: random.Random) -> bool:
    empty = [(r, c) for r in range(GRID_SIZE)
             for c in range(GRID_SIZE) if grid[r][c] == 0]
    if not empty:
        return False
    r, c = rng.choice(empty)
    grid[r][c] = 4 if rng.random() < 0.1 else 2
    return True


def _slide_row_left(row: List[int]) -> Tuple[List[int], int, List[int]]:
    """
    Slide one row left.
    Returns (new_row, score_gained, merge_positions)
    merge_positions: column indices where a merge happened in the output row.
    """
    tiles  = [v for v in row if v != 0]
    merged = []
    score  = 0
    merges = []
    i = 0
    while i < len(tiles):
        if i+1 < len(tiles) and tiles[i] == tiles[i+1]:
            val = tiles[i] * 2
            merged.append(val)
            merges.append(len(merged) - 1)
            score += val
            i += 2
        else:
            merged.append(tiles[i])
            i += 1
    while len(merged) < GRID_SIZE:
        merged.append(0)
    return merged, score, merges


def _rotate_cw(grid: Grid) -> Grid:
    n = GRID_SIZE
    return [[grid[n-1-c][r] for c in range(n)] for r in range(n)]


def _rotate_ccw(grid: Grid) -> Grid:
    n = GRID_SIZE
    return [[grid[c][n-1-r] for c in range(n)] for r in range(n)]


def slide(grid: Grid, direction: str) -> Tuple[Grid, int, bool, list]:
    """
    Slide the board.
    Returns (new_grid, score, moved, merge_info)
    merge_info: list of (row, col) in new grid where merges occurred.
    """
    # Rotate so LEFT slide handles all directions
    rot = {"LEFT": 0, "RIGHT": 2, "UP": 3, "DOWN": 1}
    n_rot = rot[direction]
    g = copy.deepcopy(grid)
    for _ in range(n_rot):
        g = _rotate_cw(g)

    total_score = 0
    merges_rotated = []
    new_g = empty_grid()
    for r in range(GRID_SIZE):
        new_row, sc, merge_cols = _slide_row_left(g[r])
        new_g[r] = new_row
        total_score += sc
        for c in merge_cols:
            merges_rotated.append((r, c))

    moved = (new_g != g)

    # Un-rotate
    for _ in range((4 - n_rot) % 4):
        new_g = _rotate_cw(new_g)

    # Un-rotate merge positions
    def unrotate_pos(r, c, k):
        for _ in range(k):
            r, c = c, GRID_SIZE - 1 - r
        return r, c

    merges = [unrotate_pos(r, c, (4 - n_rot) % 4) for r, c in merges_rotated]

    return new_g, total_score, moved, merges


def is_game_over(grid: Grid) -> bool:
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if grid[r][c] == 0:
                return False
            if c+1 < GRID_SIZE and grid[r][c] == grid[r][c+1]:
                return False
            if r+1 < GRID_SIZE and grid[r][c] == grid[r+1][c]:
                return False
    return True


def has_won(grid: Grid) -> bool:
    return any(grid[r][c] >= 2048
               for r in range(GRID_SIZE)
               for c in range(GRID_SIZE))


# ═════════════════════════════════════════════════════════════
#  PARTICLE SYSTEM  (lightweight, same as maze.py pattern)
# ═════════════════════════════════════════════════════════════

class Particle:
    __slots__ = ("x","y","vx","vy","life","max_life","color","r")

    def __init__(self, x, y, vx, vy, life, color, r=2):
        self.x = x; self.y = y
        self.vx = vx; self.vy = vy
        self.life = self.max_life = life
        self.color = color; self.r = r

    def update(self) -> bool:
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.08
        self.vx *= 0.93
        self.life -= 1
        return self.life > 0

    def draw(self, surf: pygame.Surface):
        frac  = self.life / self.max_life
        alpha = int(255 * frac)
        r     = max(1, int(self.r * frac))
        sx, sy = int(self.x), int(self.y)
        if 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color[:3], alpha), (r, r), r)
            surf.blit(s, (sx-r, sy-r))


class Particles:
    def __init__(self):
        self._pool: list = []

    def emit(self, x, y, color, n=8, speed=2.5, r=3, life=24):
        for _ in range(n):
            angle = random.uniform(0, math.tau)
            spd   = random.uniform(speed * 0.4, speed)
            self._pool.append(Particle(
                x, y,
                math.cos(angle)*spd, math.sin(angle)*spd,
                life + random.randint(-4, 4),
                color, r
            ))

    def update(self):
        self._pool = [p for p in self._pool if p.update()]

    def draw(self, surf: pygame.Surface):
        for p in self._pool:
            p.draw(surf)


# ═════════════════════════════════════════════════════════════
#  TILE ANIMATOR
# ═════════════════════════════════════════════════════════════

class TileAnim:
    """Tracks a per-cell pop/scale animation after a merge."""
    def __init__(self):
        # (row, col) → frames_remaining
        self._pops: dict = {}

    def pop(self, r: int, c: int):
        self._pops[(r, c)] = ANIM_POP_FRAMES

    def update(self):
        dead = [k for k, v in self._pops.items() if v <= 0]
        for k in dead:
            del self._pops[k]
        for k in self._pops:
            self._pops[k] -= 1

    def scale(self, r: int, c: int) -> float:
        """Return draw scale factor for this cell (1.0 = normal)."""
        if (r, c) not in self._pops:
            return 1.0
        frac = self._pops[(r, c)] / ANIM_POP_FRAMES
        # Quick overshoot: grow to 1.25 then back
        return 1.0 + 0.25 * math.sin(frac * math.pi)


# ═════════════════════════════════════════════════════════════
#  DRAWING HELPERS
# ═════════════════════════════════════════════════════════════

def _font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont("monospace", size, bold=bold)


def _text_centered(surf, txt, cx, cy, color, size=18, bold=False):
    f  = _font(size, bold)
    s  = f.render(txt, True, color)
    w, h = s.get_size()
    surf.blit(s, (cx - w//2, cy - h//2))
    return w, h


def _text(surf, txt, x, y, color, size=14, bold=False):
    f = _font(size, bold)
    s = f.render(txt, True, color)
    surf.blit(s, (x, y))
    return s.get_width()


def _rounded_rect(surf, color, rect, radius=10, border_color=None, border=2):
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border_color:
        pygame.draw.rect(surf, border_color, rect, border, border_radius=radius)


def _glow(surf, cx, cy, r, color, alpha=55):
    s = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color[:3], alpha), (r*2, r*2), r*2)
    surf.blit(s, (cx - r*2, cy - r*2), special_flags=pygame.BLEND_ALPHA_SDL2)


def cell_rect(row: int, col: int) -> pygame.Rect:
    x = BOARD_X + TILE_GAP + col * (TILE_PX + TILE_GAP)
    y = BOARD_Y + TILE_GAP + row * (TILE_PX + TILE_GAP)
    return pygame.Rect(x, y, TILE_PX, TILE_PX)


def draw_tile(surf, row, col, val, scale=1.0, alpha=255):
    base = cell_rect(row, col)
    if scale != 1.0:
        sw = int(base.width * scale)
        sh = int(base.height * scale)
        rect = pygame.Rect(
            base.centerx - sw//2,
            base.centery - sh//2,
            sw, sh
        )
    else:
        rect = base

    if val == 0:
        _rounded_rect(surf, C["empty"], rect, radius=8)
        return

    col_face  = tile_color(val)
    col_text  = tile_text_color(val)
    col_edge  = tuple(min(255, int(v * 1.4)) for v in col_face)

    # Glow on high tiles
    if val >= 64:
        _glow(surf, rect.centerx, rect.centery, TILE_PX//2, col_face,
              alpha=40 + min(60, int(math.log2(val)) * 5))

    # Face
    if alpha < 255:
        tile_surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(tile_surf, (*col_face, alpha),
                         (0, 0, rect.w, rect.h), border_radius=8)
        surf.blit(tile_surf, rect.topleft)
    else:
        _rounded_rect(surf, col_face, rect, radius=8, border_color=col_edge, border=2)

    # Inner highlight
    hi_rect = pygame.Rect(rect.x+3, rect.y+3, rect.w//2, rect.h//3)
    hi_surf = pygame.Surface((hi_rect.w, hi_rect.h), pygame.SRCALPHA)
    pygame.draw.rect(hi_surf, (255,255,255, 25), (0,0,hi_rect.w,hi_rect.h),
                     border_radius=5)
    surf.blit(hi_surf, hi_rect.topleft)

    # Value label
    label = str(val)
    sz = 28 if val < 100 else (22 if val < 1000 else (16 if val < 10000 else 12))
    _text_centered(surf, label, rect.centerx, rect.centery, col_text, size=sz, bold=True)


# ═════════════════════════════════════════════════════════════
#  SCORE BADGE
# ═════════════════════════════════════════════════════════════

class ScoreBadge:
    """Floating +N score popup."""
    def __init__(self, x, y, val, color):
        self.x = float(x)
        self.y = float(y)
        self.val = val
        self.color = color
        self.life = 50
        self.max_life = 50

    def update(self) -> bool:
        self.y -= 0.7
        self.life -= 1
        return self.life > 0

    def draw(self, surf):
        frac  = self.life / self.max_life
        alpha = int(255 * frac)
        f = _font(15, bold=True)
        s = f.render(f"+{self.val}", True, self.color)
        s.set_alpha(alpha)
        surf.blit(s, (int(self.x) - s.get_width()//2, int(self.y)))


# ═════════════════════════════════════════════════════════════
#  GAME
# ═════════════════════════════════════════════════════════════

class Game:
    def __init__(self, serial_port: Optional[str] = None):
        pygame.init()
        pygame.display.set_caption("2048  ·  NEON")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock  = pygame.time.Clock()
        self.running = True

        self.ctrl = SerialController(port=serial_port)
        self.ctrl.start()
        self.inp  = Input(self.ctrl)

        self.particles = Particles()
        self.tile_anim = TileAnim()
        self.badges: list = []

        self._tick = 0
        self._rng  = random.Random()

        self._phase      = "title"  # title | playing | won | gameover
        self._won_acked  = False    # player can continue after 2048
        self._shake      = 0

        self._grid:      Grid = empty_grid()
        self._prev_grid: Optional[Grid] = None   # for undo
        self._prev_score: int = 0
        self.score      = 0
        self.best       = 0

        self._new_game()
        self._phase = "title"

    # ─── Game state ───────────────────────────────────────────

    def _new_game(self):
        self._grid      = empty_grid()
        self._prev_grid = None
        self._prev_score = 0
        self.score      = 0
        self._won_acked = False
        self.particles  = Particles()
        self.tile_anim  = TileAnim()
        self.badges     = []
        spawn_tile(self._grid, self._rng)
        spawn_tile(self._grid, self._rng)
        self._phase = "playing"

    def _do_undo(self):
        if self._prev_grid is not None:
            self._grid  = copy.deepcopy(self._prev_grid)
            self.score  = self._prev_score
            self._prev_grid = None

    # ─── Main loop ────────────────────────────────────────────

    def run(self):
        while self.running:
            pg_events = pygame.event.get()
            for ev in pg_events:
                if ev.type == pygame.QUIT:
                    self.running = False
            self.inp.update(pg_events)
            self._update()
            self._draw()
            self.clock.tick(FPS)
        self.ctrl.stop()
        pygame.quit()

    # ─── Update ───────────────────────────────────────────────

    def _update(self):
        self._tick += 1

        if self.inp.jp("QUIT"):
            self.running = False
            return

        if self._phase == "title":
            if self.inp.any_dir() or self.inp.jp("NEW"):
                self._new_game()
            return

        if self._phase == "gameover":
            if self.inp.jp("NEW"):
                self._new_game()
            self.particles.update()
            return

        if self._phase == "won" and not self._won_acked:
            if self.inp.jp("NEW"):
                self._new_game()
                return
            if self.inp.any_dir():
                self._won_acked = True  # continue playing
            self.particles.update()
            self.tile_anim.update()
            for b in self.badges: b.update()
            self.badges = [b for b in self.badges if b.life > 0]
            return

        # ── playing (or won+acked) ─────────────────────────────
        if self.inp.jp("NEW"):
            self._new_game()
            return
        if self.inp.jp("UNDO"):
            self._do_undo()

        direction = self.inp.any_dir()
        if direction:
            self._prev_grid  = copy.deepcopy(self._grid)
            self._prev_score = self.score
            new_grid, gained, moved, merges = slide(self._grid, direction)
            if moved:
                self._grid  = new_grid
                self.score += gained
                if self.score > self.best:
                    self.best = self.score

                # Spawn tile & particles for each merge
                for r, c in merges:
                    val  = self._grid[r][c]
                    col  = tile_color(val)
                    rect = cell_rect(r, c)
                    self.particles.emit(rect.centerx, rect.centery,
                                        col, n=12, speed=3.0, r=3, life=28)
                    self.tile_anim.pop(r, c)
                    self.badges.append(ScoreBadge(
                        rect.centerx, rect.top - 5,
                        val, col
                    ))

                spawn_tile(self._grid, self._rng)

                if has_won(self._grid) and not self._won_acked:
                    self._phase = "won"
                elif is_game_over(self._grid):
                    self._phase = "gameover"
                    self._shake = 20
            else:
                # No move — small shake
                self._shake = max(self._shake, 5)

        if self._shake > 0:
            self._shake -= 1

        self.particles.update()
        self.tile_anim.update()
        for b in self.badges: b.update()
        self.badges = [b for b in self.badges if b.life > 0]

    # ─── Draw ─────────────────────────────────────────────────

    def _draw(self):
        self.screen.fill(C["bg"])
        self._draw_starfield()

        if self._phase == "title":
            self._draw_board(0, 0)
            self._draw_title_overlay()
        else:
            sx = random.randint(-self._shake, self._shake) if self._shake else 0
            sy = random.randint(-self._shake, self._shake) if self._shake else 0
            self._draw_header()
            self._draw_board(sx, sy)
            self.particles.draw(self.screen)
            for b in self.badges:
                b.draw(self.screen)
            self._draw_controls_hint()

            if self._phase == "gameover":
                self._draw_overlay("GAME OVER",
                                   C["ui_red"],
                                   f"Score: {self.score}",
                                   "R / NEW  to play again")
            elif self._phase == "won" and not self._won_acked:
                self._draw_overlay("YOU HIT 2048!",
                                   C["ui_gold"],
                                   f"Score: {self.score}",
                                   "R / NEW  new game    ↑↓←→  keep going")

        # Controller indicator dot
        dot = C["ui_green"] if self.ctrl.connected else C["ui_dim"]
        pygame.draw.circle(self.screen, dot, (SCREEN_W - 8, SCREEN_H - 8), 4)

        pygame.display.flip()

    def _draw_starfield(self):
        t = self._tick
        random.seed(42)
        for i in range(80):
            sx = random.randint(0, SCREEN_W)
            sy = random.randint(0, SCREEN_H)
            br = random.randint(30, 150)
            twinkle = abs(math.sin(t * 0.03 + i * 0.4))
            b2 = int(br * twinkle)
            if b2 > 15:
                self.screen.set_at((sx, sy), (b2, b2, b2 + 25))
        random.seed()

    def _draw_header(self):
        # Title
        _text(self.screen, "2048", 30, 18, C["ui_gold"], size=42, bold=True)

        # Score boxes
        for i, (label, val) in enumerate([("SCORE", self.score), ("BEST", self.best)]):
            bx = SCREEN_W - 160 + i * 82
            by = 14
            _rounded_rect(self.screen, C["board_bg"],
                          pygame.Rect(bx, by, 72, 50), radius=8,
                          border_color=C["board_border"], border=1)
            _text_centered(self.screen, label, bx+36, by+14, C["ui_dim"], size=10, bold=True)
            _text_centered(self.screen, str(val), bx+36, by+34, C["ui_text"], size=14, bold=True)

        # Divider
        pygame.draw.line(self.screen, C["board_border"],
                         (20, 80), (SCREEN_W-20, 80), 1)

        # Subtitle line
        sub = f"Level {self._level_label()}   ·   Tiles on board: {self._tile_count()}"
        _text(self.screen, sub, 28, 88, C["ui_dim"], size=11)

    def _level_label(self) -> str:
        mx = max((self._grid[r][c]
                  for r in range(GRID_SIZE)
                  for c in range(GRID_SIZE)), default=0)
        if mx >= 2048: return "LEGENDARY"
        if mx >= 1024: return "MASTER"
        if mx >= 512:  return "EXPERT"
        if mx >= 256:  return "ADVANCED"
        if mx >= 128:  return "SKILLED"
        return "BEGINNER"

    def _tile_count(self) -> int:
        return sum(1 for r in range(GRID_SIZE)
                   for c in range(GRID_SIZE) if self._grid[r][c] != 0)

    def _draw_board(self, sx: int = 0, sy: int = 0):
        # Board background
        board_rect = pygame.Rect(BOARD_X + sx - 2, BOARD_Y + sy - 2,
                                 GRID_PX + 4, GRID_PX + 4)
        _rounded_rect(self.screen, C["board_bg"], board_rect, radius=12,
                      border_color=C["board_border"], border=2)

        # Glow behind board
        _glow(self.screen,
              BOARD_X + sx + GRID_PX//2,
              BOARD_Y + sy + GRID_PX//2,
              GRID_PX//2, C["ui_cyan"], alpha=12)

        # Empty cell shadows
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                rect = cell_rect(r, c)
                rect.x += sx; rect.y += sy
                _rounded_rect(self.screen, C["empty"], rect, radius=8)

        # Tiles
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                val = self._grid[r][c]
                if val == 0:
                    continue
                scale = self.tile_anim.scale(r, c)
                base  = cell_rect(r, c)
                base.x += sx; base.y += sy
                # Rebuild offset cell for draw_tile (draw_tile re-derives position)
                # We pass the visual rect manually for scaled drawing
                if scale != 1.0:
                    sw = int(base.width * scale)
                    sh = int(base.height * scale)
                    rect = pygame.Rect(
                        base.centerx - sw//2,
                        base.centery - sh//2,
                        sw, sh
                    )
                else:
                    rect = base

                col_face = tile_color(val)
                col_text = tile_text_color(val)
                col_edge = tuple(min(255, int(v * 1.4)) for v in col_face)

                if val >= 64:
                    _glow(self.screen, rect.centerx, rect.centery,
                          TILE_PX//2, col_face,
                          alpha=35 + min(55, int(math.log2(val)) * 4))

                _rounded_rect(self.screen, col_face, rect, radius=8,
                              border_color=col_edge, border=2)

                # Inner highlight
                hi = pygame.Surface((rect.w//2, rect.h//3), pygame.SRCALPHA)
                pygame.draw.rect(hi, (255,255,255,22), (0,0,rect.w//2,rect.h//3),
                                 border_radius=4)
                self.screen.blit(hi, (rect.x+3, rect.y+3))

                # Label
                label = str(val)
                sz = 28 if val < 100 else (22 if val < 1000 else (16 if val < 10000 else 12))
                _text_centered(self.screen, label,
                               rect.centerx, rect.centery,
                               col_text, size=sz, bold=True)

    def _draw_controls_hint(self):
        y = BOARD_Y + GRID_PX + 18
        hints = [
            ("↑↓←→  /  WASD", "slide"),
            ("R  /  OPTIONS tap", "new game"),
            ("U  /  OPTIONS hold", "undo"),
        ]
        x = BOARD_X
        for key, desc in hints:
            w = _text(self.screen, key, x, y, C["ui_gold"], size=11, bold=True)
            _text(self.screen, f"  {desc}", x + w, y, C["ui_dim"], size=11)
            y += 16

    def _draw_title_overlay(self):
        # Darken board
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((4, 4, 10, 180))
        self.screen.blit(overlay, (0, 0))

        t = self._tick
        pulse = 0.85 + 0.15 * math.sin(t * 0.07)
        gold  = tuple(int(v * pulse) for v in C["ui_gold"])

        f1 = pygame.font.SysFont("monospace", 64, bold=True)
        f2 = pygame.font.SysFont("monospace", 18, bold=True)
        f3 = pygame.font.SysFont("monospace", 12)

        s1 = f1.render("2048", True, gold)
        s2 = f2.render("N E O N", True, C["ui_cyan"])
        self.screen.blit(s1, (SCREEN_W//2 - s1.get_width()//2, 155))
        self.screen.blit(s2, (SCREEN_W//2 - s2.get_width()//2, 232))

        lines = [
            "Slide tiles to merge matching numbers.",
            "Reach the 2048 tile to win!",
            "",
            "↑↓←→  or  WASD  to slide",
            "R  ·  new game     U  ·  undo",
            "",
            "Press any direction to start",
        ]
        for i, line in enumerate(lines):
            if not line:
                continue
            col = C["white"] if i == len(lines)-1 else C["ui_dim"]
            s = f3.render(line, True, col)
            self.screen.blit(s, (SCREEN_W//2 - s.get_width()//2, 280 + i*18))

        # Controller dot
        dot = C["ui_green"] if self.ctrl.connected else C["ui_dim"]
        dot_txt = "Controller connected" if self.ctrl.connected else "Keyboard mode"
        pygame.draw.circle(self.screen, dot, (SCREEN_W//2 - 72, SCREEN_H - 28), 5)
        s4 = pygame.font.SysFont("monospace", 11).render(dot_txt, True, dot)
        self.screen.blit(s4, (SCREEN_W//2 - 62, SCREEN_H - 33))

    def _draw_overlay(self, title: str, title_col, line1: str = "", line2: str = ""):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        # Panel
        pw, ph = 380, 150
        px = SCREEN_W//2 - pw//2
        py = SCREEN_H//2 - ph//2
        _rounded_rect(self.screen, C["board_bg"],
                      pygame.Rect(px, py, pw, ph), radius=14,
                      border_color=title_col, border=2)

        f1 = pygame.font.SysFont("monospace", 32, bold=True)
        f2 = pygame.font.SysFont("monospace", 13)
        f3 = pygame.font.SysFont("monospace", 11)

        s1 = f1.render(title, True, title_col)
        self.screen.blit(s1, (SCREEN_W//2 - s1.get_width()//2, py + 18))

        if line1:
            s2 = f2.render(line1, True, C["ui_text"])
            self.screen.blit(s2, (SCREEN_W//2 - s2.get_width()//2, py + 72))
        if line2:
            s3 = f3.render(line2, True, C["ui_dim"])
            self.screen.blit(s3, (SCREEN_W//2 - s3.get_width()//2, py + 96))


# ═════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="2048 NEON — Xiao ESP32-C3 gamepad")
    parser.add_argument("--port", default=None,
                        help="Serial port for controller (auto-detected if omitted)")
    parser.add_argument("--list-ports", action="store_true",
                        help="List available serial ports and exit")
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

    game = Game(serial_port=args.port)
    game.run()


if __name__ == "__main__":
    main()
