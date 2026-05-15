"""
Eternal Shards — Game Data
All stats, classes, items, enemies, maps, and dialogue.
"""

# ── Palette (NES-inspired) ─────────────────────────────────────────
PAL = {
    "black":      (10,  10,  15),
    "dark_blue":  (15,  20,  60),
    "blue":       (40,  80, 180),
    "light_blue": (100, 160, 240),
    "dark_green": (20,  60,  20),
    "green":      (50, 140,  50),
    "light_green":(120, 210, 100),
    "dark_brown": (60,  30,  10),
    "brown":      (120,  70,  20),
    "tan":        (200, 160, 100),
    "sand":       (230, 210, 150),
    "gray":       (120, 120, 130),
    "light_gray": (190, 190, 200),
    "white":      (240, 240, 250),
    "dark_red":   (100,  15,  15),
    "red":        (210,  40,  40),
    "orange":     (230, 130,  30),
    "yellow":     (240, 210,  40),
    "purple":     (120,  40, 180),
    "pink":       (220,  80, 160),
    "gold":       (200, 160,  20),
    "hp_red":     (200,  50,  50),
    "mp_blue":    (50,  100, 200),
    "xp_yellow":  (180, 160,  20),
    "ui_dark":    (20,  22,  35),
    "ui_panel":   (30,  34,  55),
    "ui_border":  (80,  90, 140),
    "ui_text":    (220, 220, 240),
    "ui_dim":     (140, 140, 160),
    "ui_gold":    (220, 190,  60),
    "ui_green":   (60,  200, 100),
    "ui_red":     (220,  80,  80),
    "cursor":     (255, 220,  60),
}

# ── Screen / tile constants ────────────────────────────────────────
SCREEN_W, SCREEN_H = 480, 320
TILE = 16
MAP_W, MAP_H = 30, 20        # tiles
FPS = 60

# ── Character classes ──────────────────────────────────────────────
CLASSES = {
    "Warrior": {
        "desc":    "Stalwart fighter, high HP and defense.",
        "color":   PAL["orange"],
        "hp":      30, "mp": 8,
        "atk":      8, "def":  6, "mag": 2, "spd": 4,
        "hp_grow":  5, "mp_grow": 1, "atk_grow": 2,
        "def_grow": 2, "mag_grow": 0, "spd_grow": 1,
        "skills":  ["Slash", "Shield Bash", "War Cry", "Berserker"],
        "sprite_color": PAL["orange"],
    },
    "Mage": {
        "desc":    "Arcane scholar, powerful spells and low HP.",
        "color":   PAL["purple"],
        "hp":      16, "mp": 24,
        "atk":      3, "def":  2, "mag": 10, "spd": 5,
        "hp_grow":  2, "mp_grow": 4, "atk_grow": 1,
        "def_grow": 1, "mag_grow": 3, "spd_grow": 1,
        "skills":  ["Fireball", "Ice Lance", "Thunder", "Arcane Nova"],
        "sprite_color": PAL["purple"],
    },
    "Rogue": {
        "desc":    "Swift assassin, high speed and critical hits.",
        "color":   PAL["green"],
        "hp":      22, "mp": 14,
        "atk":      6, "def":  3, "mag": 3, "spd": 9,
        "hp_grow":  3, "mp_grow": 2, "atk_grow": 2,
        "def_grow": 1, "mag_grow": 1, "spd_grow": 2,
        "skills":  ["Stab", "Poison Dart", "Smoke Screen", "Shadow Strike"],
        "sprite_color": PAL["green"],
    },
}

# ── Skills ─────────────────────────────────────────────────────────
SKILLS = {
    "Slash":         {"type": "atk",  "power": 1.2, "mp": 0,  "desc": "Basic sword slash."},
    "Shield Bash":   {"type": "stun", "power": 0.8, "mp": 4,  "desc": "Stun enemy 1 turn."},
    "War Cry":       {"type": "buff", "power": 1.5, "mp": 6,  "desc": "Raise ATK for 3 turns."},
    "Berserker":     {"type": "atk",  "power": 2.5, "mp": 10, "desc": "Massive damage, halve DEF."},
    "Fireball":      {"type": "mag",  "power": 1.8, "mp": 6,  "desc": "Fire damage all enemies."},
    "Ice Lance":     {"type": "mag",  "power": 1.4, "mp": 4,  "desc": "Ice damage, slow enemy."},
    "Thunder":       {"type": "mag",  "power": 2.0, "mp": 8,  "desc": "Lightning, may paralyze."},
    "Arcane Nova":   {"type": "mag",  "power": 3.0, "mp": 14, "desc": "Unleash arcane burst."},
    "Stab":          {"type": "atk",  "power": 1.1, "mp": 0,  "desc": "Quick stab attack."},
    "Poison Dart":   {"type": "dot",  "power": 0.6, "mp": 4,  "desc": "Poison for 3 turns."},
    "Smoke Screen":  {"type": "debuff","power":0.5, "mp": 5,  "desc": "Lower enemy accuracy."},
    "Shadow Strike": {"type": "atk",  "power": 2.8, "mp": 12, "desc": "Critical backstab."},
    "Attack":        {"type": "atk",  "power": 1.0, "mp": 0,  "desc": "Basic attack."},
    "Magic Bolt":    {"type": "mag",  "power": 1.5, "mp": 4,  "desc": "Magical projectile."},
    "Charge":        {"type": "atk",  "power": 1.6, "mp": 3,  "desc": "Charging strike."},
    "Venom Bite":    {"type": "dot",  "power": 0.8, "mp": 3,  "desc": "Venomous bite."},
    "Roar":          {"type": "debuff","power":0.5, "mp": 4,  "desc": "Terrifying roar."},
    "Dark Pulse":    {"type": "mag",  "power": 2.2, "mp": 8,  "desc": "Dark energy wave."},
    "Heal":          {"type": "heal", "power": 1.5, "mp": 5,  "desc": "Restore HP."},
}

# ── Items ──────────────────────────────────────────────────────────
ITEMS = {
    "Potion":       {"type": "heal",    "value": 20,  "price": 30,  "desc": "Restore 20 HP."},
    "Hi-Potion":    {"type": "heal",    "value": 50,  "price": 80,  "desc": "Restore 50 HP."},
    "Ether":        {"type": "mp",      "value": 15,  "price": 50,  "desc": "Restore 15 MP."},
    "Antidote":     {"type": "cure",    "value": 0,   "price": 20,  "desc": "Cure poison."},
    "Iron Sword":   {"type": "weapon",  "atk": 4,     "price": 100, "desc": "+4 ATK."},
    "Steel Sword":  {"type": "weapon",  "atk": 8,     "price": 250, "desc": "+8 ATK."},
    "Magic Staff":  {"type": "weapon",  "mag": 6,     "price": 200, "desc": "+6 MAG."},
    "Iron Shield":  {"type": "armor",   "def": 3,     "price": 80,  "desc": "+3 DEF."},
    "Chain Mail":   {"type": "armor",   "def": 5,     "price": 180, "desc": "+5 DEF."},
    "Key":          {"type": "key",     "value": 0,   "price": 0,   "desc": "Opens locked doors."},
}

# Starting inventory (item_name: count)
START_ITEMS = {"Potion": 3, "Ether": 1}

# ── Enemies ────────────────────────────────────────────────────────
ENEMIES = {
    "Slime": {
        "hp": 12, "mp": 0, "atk": 4, "def": 1, "mag": 0, "spd": 2,
        "xp": 8,  "gold": 5,
        "skills": ["Attack"],
        "color": PAL["light_green"],
        "loot": {"Potion": 0.3},
    },
    "Goblin": {
        "hp": 18, "mp": 4, "atk": 6, "def": 2, "mag": 1, "spd": 5,
        "xp": 15, "gold": 10,
        "skills": ["Attack", "Stab"],
        "color": PAL["green"],
        "loot": {"Potion": 0.2, "Antidote": 0.1},
    },
    "Wolf": {
        "hp": 22, "mp": 0, "atk": 8, "def": 3, "mag": 0, "spd": 8,
        "xp": 20, "gold": 12,
        "skills": ["Attack", "Charge"],
        "color": PAL["gray"],
        "loot": {},
    },
    "Orc": {
        "hp": 35, "mp": 5, "atk": 12, "def": 6, "mag": 0, "spd": 3,
        "xp": 35, "gold": 25,
        "skills": ["Attack", "Roar", "Charge"],
        "color": PAL["dark_green"],
        "loot": {"Iron Shield": 0.1, "Potion": 0.4},
    },
    "Witch": {
        "hp": 25, "mp": 30, "atk": 4, "def": 2, "mag": 12, "spd": 6,
        "xp": 40, "gold": 30,
        "skills": ["Magic Bolt", "Venom Bite", "Heal"],
        "color": PAL["purple"],
        "loot": {"Ether": 0.4, "Antidote": 0.2},
    },
    "Skeleton": {
        "hp": 28, "mp": 8, "atk": 9, "def": 5, "mag": 3, "spd": 4,
        "xp": 30, "gold": 20,
        "skills": ["Attack", "Dark Pulse"],
        "color": PAL["light_gray"],
        "loot": {"Potion": 0.2},
    },
    "Dragon": {
        "hp": 120, "mp": 40, "atk": 20, "def": 12, "mag": 15, "spd": 7,
        "xp": 200, "gold": 150,
        "skills": ["Attack", "Charge", "Dark Pulse", "Roar"],
        "color": PAL["dark_red"],
        "loot": {"Hi-Potion": 1.0, "Ether": 1.0},
        "boss": True,
    },
    "Dark Knight": {
        "hp": 80, "mp": 20, "atk": 16, "def": 10, "mag": 5, "spd": 5,
        "xp": 120, "gold": 80,
        "skills": ["Attack", "Charge", "Dark Pulse"],
        "color": PAL["dark_blue"],
        "loot": {"Steel Sword": 0.3, "Hi-Potion": 0.5},
        "boss": True,
    },
}

# ── World map ──────────────────────────────────────────────────────
# Tile types: 0=deep water, 1=water, 2=sand, 3=grass, 4=forest,
#             5=mountain, 6=snow, 7=town, 8=dungeon, 9=road
WORLD_MAP = [
    [0,0,0,0,0,1,1,1,1,2,2,2,3,3,3,3,3,3,3,4,4,4,5,5,5,5,0,0,0,0],
    [0,0,0,0,1,1,1,2,2,2,3,3,3,3,3,3,3,3,4,4,4,5,5,6,6,5,5,0,0,0],
    [0,0,0,1,1,2,2,2,3,3,3,7,3,3,9,3,3,3,4,4,5,5,6,6,6,5,5,0,0,0],
    [0,0,1,1,2,2,3,3,3,3,3,9,3,3,9,3,4,4,4,5,5,6,6,6,5,5,0,0,0,0],
    [0,1,1,2,2,3,3,3,3,3,3,9,9,9,9,3,4,4,5,5,5,6,6,5,5,0,0,0,0,0],
    [1,1,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,4,4,5,5,5,5,5,0,0,0,0,0,0],
    [1,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,4,4,5,5,5,0,0,0,0,0,0,0],
    [1,2,3,3,3,3,7,3,3,9,3,3,3,3,3,3,4,4,4,4,4,5,5,5,0,0,0,0,0,0],
    [2,2,3,3,3,3,9,3,3,9,9,9,9,9,3,3,4,4,3,3,4,4,5,0,0,0,0,0,0,0],
    [2,3,3,3,3,3,9,9,3,3,3,3,3,9,3,3,3,4,3,3,3,4,4,0,0,0,0,0,0,0],
    [2,3,3,3,3,3,3,3,3,3,3,3,3,9,9,3,3,3,3,3,4,4,4,5,0,0,0,0,0,0],
    [3,3,3,3,3,3,3,3,3,3,3,3,3,3,9,3,3,3,3,3,3,4,5,5,0,0,0,0,0,0],
    [3,3,3,4,4,3,3,3,3,3,3,3,3,3,9,9,9,9,7,9,3,4,5,5,5,0,0,0,0,0],
    [3,3,4,4,4,4,3,3,3,3,3,3,3,3,3,3,3,3,9,3,3,3,4,5,0,0,0,0,0,0],
    [3,4,4,4,4,4,4,3,3,3,3,3,3,3,3,3,3,3,9,3,3,3,3,4,4,0,0,0,0,0],
    [4,4,4,4,4,4,4,4,3,3,3,3,3,3,3,3,3,3,9,9,8,3,3,3,4,0,0,0,0,0],
    [4,4,4,4,4,4,4,4,4,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,0,0,0,0],
    [4,4,4,4,4,4,4,4,4,4,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,4,0,0,0,0],
    [5,4,4,4,4,4,4,4,4,4,4,3,3,3,3,3,3,3,3,3,3,3,4,4,4,5,0,0,0,0],
    [5,5,4,4,4,4,4,4,4,4,4,4,3,3,3,3,3,3,3,4,4,4,4,5,5,5,0,0,0,0],
]

TILE_COLORS = {
    0: PAL["dark_blue"],
    1: PAL["blue"],
    2: PAL["sand"],
    3: PAL["light_green"],
    4: PAL["dark_green"],
    5: PAL["gray"],
    6: PAL["white"],
    7: PAL["tan"],       # town
    8: PAL["dark_brown"],# dungeon
    9: PAL["brown"],     # road
}

TILE_WALKABLE = {0: False, 1: False, 2: True, 3: True,
                 4: True, 5: False, 6: True, 7: True,
                 8: True, 9: True}

TILE_ENCOUNTER = {0: False, 1: False, 2: True, 3: True,
                  4: True, 5: False, 6: True, 7: False,
                  8: True, 9: False}

TILE_ENCOUNTER_TABLE = {
    2: ["Slime", "Goblin"],
    3: ["Slime", "Goblin", "Wolf"],
    4: ["Wolf", "Goblin", "Orc"],
    6: ["Wolf", "Skeleton"],
    8: ["Skeleton", "Orc", "Witch", "Dark Knight"],
}

# Town positions (tile x, tile y): name
TOWNS = {
    (11, 2):  {"name": "Alverton",   "shop": ["Potion","Hi-Potion","Ether","Iron Sword","Iron Shield"]},
    (5,  7):  {"name": "Brackwater", "shop": ["Potion","Antidote","Chain Mail","Steel Sword"]},
    (18, 12): {"name": "Goldhaven",  "shop": ["Hi-Potion","Ether","Magic Staff","Chain Mail"]},
}

DUNGEONS = {
    (20, 15): {"name": "Shadow Crypt",  "boss": "Dark Knight"},
}

# Boss at dragon's lair (mountain area)
BOSS_POS = (22, 1)
BOSS_ENEMY = "Dragon"

# NPC dialogue by map position
NPCS = {
    (12, 2): ["A dark crypt lies to the south-east.", "Beware the Shadow Knight within."],
    (6,  7): ["The mountains to the north are impassable.", "Seek a path through the forest."],
    (19,12): ["The Dragon sleeps in the peaks.", "None who face it return unchanged."],
}

# Story dialogue sequence
STORY = [
    "Long ago, the Eternal Shards were scattered across the land.",
    "A great evil stirs... the Dragon Malachar awakens.",
    "You, a lone adventurer, must gather strength and allies.",
    "Defeat Malachar before the shards are consumed by darkness.",
    "Your journey begins in Alverton. Seek the dungeon in the east.",
]
