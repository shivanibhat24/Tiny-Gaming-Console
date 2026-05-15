"""
Sprites — pixel-art character and enemy rendering via pygame.draw primitives.
All sprites are drawn at a base size of 32x32 or 48x48 and cached as Surfaces.
"""

import pygame
from data import PAL


def _surf(w, h):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    return s


# ── Hero sprites (32x48) ──────────────────────────────────────────

def draw_warrior(color=None):
    color = color or PAL["orange"]
    s = _surf(32, 48)
    d = pygame.draw
    skin = PAL["tan"]
    dark = (max(0, color[0]-60), max(0, color[1]-60), max(0, color[2]-60))
    # helmet
    d.rect(s, color, (8, 2, 16, 10), border_radius=4)
    d.rect(s, dark,  (8, 2, 16, 3))
    # visor
    d.rect(s, PAL["dark_blue"], (10, 7, 12, 4))
    # head
    d.rect(s, skin, (10, 12, 12, 10))
    # body / armor
    d.rect(s, color, (6, 22, 20, 14), border_radius=2)
    d.rect(s, dark,  (10, 22, 12, 3))  # chest plate line
    d.rect(s, dark,  (6, 30, 20, 2))   # belt
    # pauldrons
    d.rect(s, dark, (2, 22, 5, 8), border_radius=2)
    d.rect(s, dark, (25, 22, 5, 8), border_radius=2)
    # arms
    d.rect(s, color, (3, 22, 5, 14))
    d.rect(s, color, (24, 22, 5, 14))
    # gloves
    d.rect(s, dark, (3, 34, 5, 4))
    d.rect(s, dark, (24, 34, 5, 4))
    # sword
    d.rect(s, PAL["light_gray"], (27, 14, 3, 22))
    d.rect(s, PAL["gold"],       (25, 20, 7, 3))
    # legs
    d.rect(s, dark, (8, 36, 7, 10), border_radius=2)
    d.rect(s, dark, (17, 36, 7, 10), border_radius=2)
    # boots
    d.rect(s, PAL["dark_brown"], (7, 43, 9, 5))
    d.rect(s, PAL["dark_brown"], (16, 43, 9, 5))
    return s


def draw_mage(color=None):
    color = color or PAL["purple"]
    s = _surf(32, 48)
    d = pygame.draw
    skin = PAL["tan"]
    dark = (max(0, color[0]-50), max(0, color[1]-50), max(0, color[2]-50))
    hat_tip = PAL["gold"]
    # hat
    pts = [(16, 0), (10, 12), (22, 12)]
    d.polygon(s, color, pts)
    d.rect(s, dark, (8, 11, 16, 4))
    # brim stars
    d.circle(s, hat_tip, (11, 8), 2)
    d.circle(s, hat_tip, (18, 5), 1)
    # head
    d.rect(s, skin, (10, 15, 12, 9))
    # robe body
    d.polygon(s, color, [(6,24),(26,24),(28,48),(4,48)])
    d.rect(s, dark, (6, 24, 20, 3))
    # robe trim
    d.line(s, hat_tip, (4,48),(28,48), 2)
    # collar
    d.rect(s, dark, (12, 24, 8, 4))
    # sleeves
    d.polygon(s, color, [(2, 26),(7, 24),(8, 36),(2, 38)])
    d.polygon(s, color, [(30,26),(25,24),(24,36),(30,38)])
    # hands
    d.rect(s, skin, (1, 36, 5, 4))
    d.rect(s, skin, (26, 36, 5, 4))
    # staff (left hand)
    d.rect(s, PAL["brown"], (0, 8, 3, 34))
    d.circle(s, PAL["light_blue"], (1, 8), 5)
    d.circle(s, PAL["white"], (1, 8), 2)
    # eyes
    d.rect(s, PAL["dark_blue"], (12, 18, 3, 2))
    d.rect(s, PAL["dark_blue"], (18, 18, 3, 2))
    return s


def draw_rogue(color=None):
    color = color or PAL["green"]
    s = _surf(32, 48)
    d = pygame.draw
    skin = PAL["tan"]
    dark = (max(0, color[0]-50), max(0, color[1]-50), max(0, color[2]-50))
    # hood
    d.circle(s, dark, (16, 10), 10)
    d.rect(s, dark, (6, 10, 20, 6))
    # face shadow
    d.ellipse(s, (30, 20, 10, 100), (10, 8, 12, 10))
    # eyes — glowing
    d.circle(s, PAL["yellow"], (13, 11), 2)
    d.circle(s, PAL["yellow"], (19, 11), 2)
    # body / cloak
    d.polygon(s, color, [(5,16),(27,16),(25,38),(7,38)])
    d.rect(s, dark, (5, 16, 22, 3))
    d.line(s, dark, (16, 16), (16, 38), 1)
    # belt
    d.rect(s, PAL["dark_brown"], (7, 29, 18, 4))
    d.rect(s, PAL["gold"], (14, 29, 4, 4))
    # legs
    d.rect(s, dark, (7, 38, 8, 10))
    d.rect(s, dark, (17, 38, 8, 10))
    # boots
    d.rect(s, PAL["dark_brown"], (6, 44, 10, 4))
    d.rect(s, PAL["dark_brown"], (16, 44, 10, 4))
    # daggers
    d.polygon(s, PAL["light_gray"], [(26,15),(28,30),(30,15)])
    d.rect(s, PAL["brown"], (26, 28, 4, 3))
    d.polygon(s, PAL["light_gray"], [(2,15),(4,30),(6,15)])
    d.rect(s, PAL["brown"], (2, 28, 4, 3))
    return s


# ── Enemy sprites (48x48) ─────────────────────────────────────────

def draw_slime(color=None):
    color = color or PAL["light_green"]
    s = _surf(48, 48)
    d = pygame.draw
    dark = (max(0,color[0]-40), max(0,color[1]-40), max(0,color[2]-40))
    # body blob
    d.ellipse(s, color, (4, 16, 40, 30))
    d.ellipse(s, dark,  (4, 16, 40, 30), 2)
    # top bubble
    d.ellipse(s, color, (14, 6, 20, 18))
    d.ellipse(s, dark,  (14, 6, 20, 18), 2)
    # shine
    d.ellipse(s, PAL["white"], (18, 8, 6, 4))
    # eyes
    d.circle(s, PAL["black"], (17, 22), 4)
    d.circle(s, PAL["black"], (31, 22), 4)
    d.circle(s, PAL["white"], (19, 21), 2)
    d.circle(s, PAL["white"], (33, 21), 2)
    # mouth
    pts = [(16,30),(32,30),(30,34),(18,34)]
    d.polygon(s, dark, pts)
    return s


def draw_goblin(color=None):
    color = color or PAL["green"]
    s = _surf(48, 48)
    d = pygame.draw
    skin = (100, 160, 80)
    dark = (30, 90, 30)
    # ears
    d.polygon(s, skin, [(6,8),(2,2),(10,10)])
    d.polygon(s, skin, [(42,8),(46,2),(38,10)])
    # head
    d.ellipse(s, skin, (10, 4, 28, 22))
    # eyes
    d.circle(s, PAL["yellow"], (17, 12), 4)
    d.circle(s, PAL["yellow"], (31, 12), 4)
    d.circle(s, dark, (17, 12), 2)
    d.circle(s, dark, (31, 12), 2)
    # nose
    d.ellipse(s, dark, (20, 18, 8, 5))
    # teeth
    d.rect(s, PAL["white"], (18, 22, 4, 4))
    d.rect(s, PAL["white"], (26, 22, 4, 4))
    # body
    d.rect(s, color, (12, 26, 24, 14), border_radius=3)
    d.rect(s, dark,  (14, 26, 20, 4))
    # arms
    d.rect(s, skin, (4, 26, 8, 12))
    d.rect(s, skin, (36, 26, 8, 12))
    # club (right hand)
    d.rect(s, PAL["brown"], (42, 18, 5, 20))
    d.ellipse(s, PAL["dark_brown"], (40, 14, 9, 9))
    # legs
    d.rect(s, dark, (14, 40, 8, 8))
    d.rect(s, dark, (26, 40, 8, 8))
    return s


def draw_wolf(color=None):
    color = color or PAL["gray"]
    s = _surf(48, 48)
    d = pygame.draw
    dark = (max(0,color[0]-40), max(0,color[1]-40), max(0,color[2]-40))
    light = (min(255,color[0]+40), min(255,color[1]+40), min(255,color[2]+40))
    # body
    d.ellipse(s, color, (4, 20, 36, 20))
    # legs
    d.rect(s, dark, (8,  38, 6, 10))
    d.rect(s, dark, (18, 38, 6, 10))
    d.rect(s, dark, (28, 38, 6, 10))
    # neck + head
    d.ellipse(s, color, (28, 10, 20, 16))
    d.polygon(s, color, [(38,10),(44,4),(48,12)])  # ear
    d.polygon(s, color, [(32,10),(28,4),(34,8)])   # ear2
    d.rect(s, color, (36, 22, 12, 8))              # snout base
    d.polygon(s, light, [(36,22),(48,22),(44,30),(36,30)])  # snout
    # eyes
    d.circle(s, PAL["yellow"], (35, 15), 3)
    d.circle(s, PAL["black"],  (35, 15), 1)
    # nose
    d.ellipse(s, PAL["black"], (42, 22, 5, 3))
    # tail
    pts = [(4,22),(0,16),(2,12),(8,18),(6,22)]
    d.polygon(s, dark, pts)
    return s


def draw_orc(color=None):
    color = color or PAL["dark_green"]
    s = _surf(48, 48)
    d = pygame.draw
    skin = (60, 120, 50)
    dark = (20, 60, 20)
    # head
    d.ellipse(s, skin, (12, 2, 24, 22))
    # tusks
    d.polygon(s, PAL["white"], [(16,20),(14,28),(18,26)])
    d.polygon(s, PAL["white"], [(32,20),(34,28),(30,26)])
    # eyes
    d.circle(s, PAL["red"], (19, 10), 4)
    d.circle(s, PAL["red"], (29, 10), 4)
    d.circle(s, dark, (19, 10), 2)
    d.circle(s, dark, (29, 10), 2)
    # armor body
    d.rect(s, color, (8, 24, 32, 16), border_radius=3)
    d.rect(s, dark, (8, 24, 32, 4))
    # pauldrons
    d.circle(s, dark, (8, 26), 7)
    d.circle(s, dark, (40, 26), 7)
    # arms
    d.rect(s, skin, (2, 26, 8, 16))
    d.rect(s, skin, (38, 26, 8, 16))
    # axe
    d.rect(s, PAL["brown"], (40, 4, 4, 28))
    d.polygon(s, PAL["gray"], [(40,4),(48,0),(48,16),(40,14)])
    # legs
    d.rect(s, dark, (12, 40, 10, 8))
    d.rect(s, dark, (26, 40, 10, 8))
    return s


def draw_witch(color=None):
    color = color or PAL["purple"]
    s = _surf(48, 48)
    d = pygame.draw
    skin = PAL["tan"]
    dark = (max(0,color[0]-50), max(0,color[1]-50), max(0,color[2]-50))
    # hat
    pts = [(24,0),(14,14),(34,14)]
    d.polygon(s, dark, pts)
    d.rect(s, color, (10, 13, 28, 5))
    # head
    d.ellipse(s, skin, (14, 18, 20, 18))
    # eyes — glowing
    d.circle(s, PAL["yellow"], (19, 24), 3)
    d.circle(s, PAL["yellow"], (29, 24), 3)
    # warts / features
    d.circle(s, (160,100,60), (23, 30), 3)
    # robe
    d.polygon(s, color, [(6,36),(42,36),(44,48),(4,48)])
    d.rect(s, dark, (6, 36, 36, 3))
    # sleeves
    d.polygon(s, color, [(2,34),(8,36),(8,44),(0,46)])
    d.polygon(s, color, [(46,34),(40,36),(40,44),(48,46)])
    # hands
    d.circle(s, skin, (3, 44), 4)
    d.circle(s, skin, (45, 44), 4)
    # orb
    d.circle(s, PAL["light_blue"], (4, 32), 6)
    d.circle(s, PAL["white"], (2, 30), 2)
    return s


def draw_skeleton(color=None):
    color = color or PAL["light_gray"]
    s = _surf(48, 48)
    d = pygame.draw
    dark = PAL["gray"]
    # skull
    d.ellipse(s, color, (14, 2, 20, 18))
    # jaw
    d.rect(s, color, (16, 16, 16, 8))
    d.rect(s, PAL["dark_blue"], (17, 16, 4, 6))   # eye L
    d.rect(s, PAL["dark_blue"], (27, 16, 4, 6))   # eye R
    d.rect(s, PAL["black"], (19, 22, 3, 4))        # teeth gaps
    d.rect(s, PAL["black"], (26, 22, 3, 4))
    # ribcage
    for i in range(3):
        y = 30 + i*5
        d.arc(s, color, (12, y, 10, 6), 0, 3.14, 2)
        d.arc(s, color, (26, y, 10, 6), 0, 3.14, 2)
    d.rect(s, color, (20, 28, 8, 14))  # spine
    # pelvis
    d.ellipse(s, color, (14, 40, 20, 8))
    # arms
    d.line(s, color, (14,28),(4,36), 3)
    d.line(s, color, (34,28),(44,36), 3)
    # sword arm
    d.line(s, color, (44,36),(42,46), 2)
    d.rect(s, PAL["light_gray"], (39, 26, 2, 22))  # sword
    d.line(s, PAL["gold"], (37,30),(43,30), 2)     # crossguard
    # legs
    d.line(s, color, (20,48),(16,38), 3)
    d.line(s, color, (28,48),(32,38), 3)
    return s


def draw_dragon(color=None):
    color = color or PAL["dark_red"]
    s = _surf(96, 80)
    d = pygame.draw
    dark = (max(0,color[0]-40), max(0,color[1]-40), max(0,color[2]-40))
    belly = PAL["orange"]
    # wings
    d.polygon(s, dark, [(20,10),(0,0),(10,36),(30,30)])
    d.polygon(s, dark, [(76,10),(96,0),(86,36),(66,30)])
    # body
    d.ellipse(s, color, (20, 28, 56, 36))
    # belly scales
    d.ellipse(s, belly, (28, 36, 40, 24))
    for i in range(4):
        d.arc(s, dark, (30+i*8, 38, 12, 8), 0, 3.14, 1)
    # neck
    d.polygon(s, color, [(46,28),(56,28),(60,14),(42,14)])
    # head
    d.ellipse(s, color, (44, 4, 30, 18))
    # horns
    d.polygon(s, dark, [(50,4),(45,-2),(52,10)])
    d.polygon(s, dark, [(66,4),(71,-2),(64,10)])
    # eyes — fire
    d.circle(s, PAL["yellow"], (52, 10), 4)
    d.circle(s, PAL["orange"], (52, 10), 2)
    d.circle(s, PAL["black"],  (52, 10), 1)
    d.circle(s, PAL["yellow"], (66, 10), 4)
    d.circle(s, PAL["orange"], (66, 10), 2)
    d.circle(s, PAL["black"],  (66, 10), 1)
    # snout / jaw
    d.polygon(s, color, [(55,18),(68,18),(72,24),(55,24)])
    d.polygon(s, belly, [(57,18),(67,18),(70,23),(56,23)])
    # teeth
    for tx in [58,62,66,70]:
        d.polygon(s, PAL["white"], [(tx,18),(tx+2,18),(tx+1,24)])
    # fire breath
    d.polygon(s, PAL["orange"], [(72,20),(96,16),(90,24),(72,26)])
    d.polygon(s, PAL["yellow"], [(72,21),(94,20),(88,23),(72,24)])
    # tail
    pts = [(20,50),(4,60),(8,72),(20,64),(30,56)]
    d.polygon(s, dark, pts)
    # legs
    d.polygon(s, color, [(28,60),(36,56),(38,72),(24,72)])
    d.polygon(s, color, [(58,60),(68,56),(70,72),(56,72)])
    # claws
    for cx in [24,28,32]:
        d.polygon(s, dark, [(cx,72),(cx+2,72),(cx+1,78)])
    for cx in [56,60,64]:
        d.polygon(s, dark, [(cx,72),(cx+2,72),(cx+1,78)])
    return s


def draw_dark_knight(color=None):
    color = color or PAL["dark_blue"]
    s = _surf(48, 64)
    d = pygame.draw
    dark = (max(0,color[0]-20), max(0,color[1]-20), max(0,color[2]-20))
    glow = PAL["purple"]
    # helmet — full face
    d.rect(s, dark, (12, 2, 24, 22), border_radius=4)
    d.rect(s, color, (14, 4, 20, 18), border_radius=3)
    # visor slit — glowing eyes
    d.rect(s, PAL["dark_blue"], (14, 10, 20, 6))
    d.rect(s, glow, (15, 11, 8, 4))
    d.rect(s, glow, (25, 11, 8, 4))
    # helmet plume
    pts = [(24,2),(20,0),(16,4),(22,6),(26,6),(32,4),(28,0)]
    d.polygon(s, glow, pts)
    # neck
    d.rect(s, dark, (18, 24, 12, 4))
    # body armor
    d.rect(s, color, (8, 28, 32, 20), border_radius=2)
    d.rect(s, dark, (8, 28, 32, 4))
    d.rect(s, dark, (8, 38, 32, 2))
    # rune on chest
    d.circle(s, glow, (24, 36), 5, 2)
    d.line(s, glow, (24,31),(24,41), 1)
    d.line(s, glow, (19,36),(29,36), 1)
    # pauldrons
    d.rect(s, dark, (2, 26, 8, 12), border_radius=3)
    d.rect(s, dark, (38, 26, 8, 12), border_radius=3)
    # arms
    d.rect(s, color, (3, 28, 6, 16))
    d.rect(s, color, (39, 28, 6, 16))
    # gauntlets
    d.rect(s, dark, (3, 42, 6, 6))
    d.rect(s, dark, (39, 42, 6, 6))
    # greatsword
    d.rect(s, PAL["light_gray"], (42, 4, 4, 40))
    d.rect(s, dark, (38, 20, 12, 4))       # crossguard
    d.polygon(s, glow, [(44,4),(46,4),(45,0)])  # pommel
    d.polygon(s, PAL["light_gray"], [(42,4),(46,4),(44,0)])
    # legs
    d.rect(s, dark, (10, 48, 12, 14), border_radius=2)
    d.rect(s, dark, (26, 48, 12, 14), border_radius=2)
    # sabatons
    d.rect(s, color, (8, 58, 14, 6))
    d.rect(s, color, (24, 58, 14, 6))
    return s


ENEMY_SPRITES = {
    "Slime":      draw_slime,
    "Goblin":     draw_goblin,
    "Wolf":       draw_wolf,
    "Orc":        draw_orc,
    "Witch":      draw_witch,
    "Skeleton":   draw_skeleton,
    "Dragon":     draw_dragon,
    "Dark Knight":draw_dark_knight,
}

HERO_SPRITES = {
    "Warrior": draw_warrior,
    "Mage":    draw_mage,
    "Rogue":   draw_rogue,
}

_cache = {}

def get_sprite(name, scale=1):
    key = (name, scale)
    if key in _cache:
        return _cache[key]
    fn = ENEMY_SPRITES.get(name) or HERO_SPRITES.get(name)
    if not fn:
        s = _surf(32, 32)
        pygame.draw.rect(s, PAL["pink"], (4, 4, 24, 24))
        _cache[key] = s
        return s
    base = fn()
    if scale != 1:
        w, h = base.get_size()
        base = pygame.transform.scale(base, (int(w * scale), int(h * scale)))
    _cache[key] = base
    return base
