# -*- coding: utf-8 -*-
"""
DiabloInventory.py
Sistema de inventário estilo Diablo + mapa roguelike simples.

Sistema de encaixe:
- Item sempre centralizado no cursor
- Snap pela célula sob o cursor com clamp
- Preview: verde (vazio) / azul (swap) / sem preview (bloqueado)
- Item desenhado cola no preview quando há encaixe válido
- Auto-organize (multi-heurística + rotação) — tecla O / botão
- Destaque de raridade pulsante no chão
- Stack de consumíveis com contador e merge automático
"""

import os, json, random, math
import pygame

pygame.init()
WIDTH, HEIGHT = 1280, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Diablo-like Inventory System")
clock = pygame.time.Clock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ITEMS_DIR   = os.path.join(BASE_DIR, "exports", "items")
AFFIXES_DIR = os.path.join(BASE_DIR, "exports", "affixes")
UNITS_DIR   = os.path.join(BASE_DIR, "exports", "units")

# ============================================================================
# Paleta
# ============================================================================
BG            = (10, 8, 6)
PANEL_BG      = (28, 22, 16)
SLOT_BG       = (40, 32, 24)
SLOT_HOVER    = (70, 58, 40)
PANEL_BORDER  = (90, 70, 45)
TEXT          = (220, 210, 190)
TEXT_DIM      = (140, 130, 110)
TEXT_GOLD     = (240, 200, 80)
ACCENT        = (190, 150, 80)
ACCENT_DARK   = (110, 85, 45)
ACCENT_BRIGHT = (240, 200, 100)
DANGER        = (200, 70, 70)
SUCCESS       = (110, 200, 110)
GAIN          = (110, 220, 110)
LOSS          = (230, 100, 100)
WARN          = (230, 175, 70)
PREVIEW_OK    = (110, 220, 110)
PREVIEW_SWAP  = (100, 180, 240)
MAP_FLOOR     = (52, 42, 32)
MAP_FLOOR2    = (60, 48, 38)
MAP_WALL      = (20, 15, 12)
MAP_WALL_TOP  = (38, 28, 20)
MAP_BORDER    = (120, 90, 60)

RARITY_COLORS = {
    "Comum":    (200, 200, 200),
    "Incomum":  (110, 220, 110),
    "Raro":     (130, 180, 255),
    "Épico":    (200, 130, 240),
    "Lendário": (240, 170, 60),
    "Mítico":   (255, 100, 100),
}

# (alpha_base, velocidade) do pulso — Comum não pulsa
RARITY_GLOW = {
    "Comum":    (0,   0.0),
    "Incomum":  (55,  1.8),
    "Raro":     (85,  2.2),
    "Épico":    (115, 2.6),
    "Lendário": (150, 3.0),
    "Mítico":   (185, 3.6),
}

FONT_XL = pygame.font.SysFont("georgia,cambria,dejavuserif,serif", 22, bold=True)
FONT_L  = pygame.font.SysFont("georgia,cambria,dejavuserif,serif", 16, bold=True)
FONT_M  = pygame.font.SysFont("georgia,cambria,dejavuserif,serif", 14)
FONT_S  = pygame.font.SysFont("georgia,cambria,dejavuserif,serif", 12)
FONT_XS = pygame.font.SysFont("georgia,cambria,dejavuserif,serif", 11)
FONT_ICON_M = pygame.font.SysFont("segoeui,dejavusans,arial", 20, bold=True)
FONT_ICON_L = pygame.font.SysFont("segoeui,dejavusans,arial", 26, bold=True)
FONT_ICON_S = pygame.font.SysFont("segoeui,dejavusans,arial", 14, bold=True)

# ============================================================================
# Layout
# ============================================================================
MAP_COLS, MAP_ROWS = 20, 15
TILE = 40
MAP_W, MAP_H = MAP_COLS * TILE, MAP_ROWS * TILE
MAP_X, MAP_Y = 10, 10

LOG_X, LOG_Y = 10, MAP_Y + MAP_H + 8
LOG_W, LOG_H = MAP_W, 170

PANEL_X = MAP_X + MAP_W + 10
PANEL_Y = 10
PANEL_W = WIDTH - PANEL_X - 10
PANEL_H = HEIGHT - 20

CELL = 36
INV_COLS, INV_ROWS = 10, 6

EQUIP_SLOTS = [
    "Cabeça", "Amuleto", "Capa",
    "Peito",  "Mãos",    "Arma",
    "Pernas", "Cinto",   "Mão Secundária",
    "Pés",    "Anel 1",  "Anel 2",
]

SLOT_MAP = {
    "Cabeça": "Cabeça", "Peito": "Peito", "Pernas": "Pernas",
    "Pés": "Pés", "Mãos": "Mãos", "Arma": "Arma",
    "Mão Secundária": "Mão Secundária", "Cinto": "Cinto", "Capa": "Capa",
    "Amuleto": "Amuleto", "Anel": ["Anel 1", "Anel 2"],
}

STAT_LABELS = {
    "attack_physical":"ATQ Físico", "attack_magical":"ATQ Mágico",
    "defense_physical":"DEF Física", "defense_magical":"DEF Mágica",
    "hp":"HP", "mana":"Mana", "stamina":"Stamina",
    "accuracy":"Precisão", "evasion":"Esquiva",
    "crit_chance":"Crítico %", "crit_damage":"Dano Crítico %",
    "initiative":"Iniciativa", "lifesteal":"Roubo de Vida",
    "strength":"Força", "dexterity":"Destreza",
    "intelligence":"Inteligência", "wisdom":"Sabedoria",
    "vitality":"Vitalidade", "luck":"Sorte",
}
RES_LABELS = {
    "fire":"Fogo", "ice":"Gelo", "lightning":"Elétrico",
    "poison":"Veneno", "holy":"Sagrado", "dark":"Sombrio",
}

MAP_LAYOUT = [
    "####################",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "####################",
]

def is_wall(tx, ty):
    if tx < 0 or ty < 0 or tx >= MAP_COLS or ty >= MAP_ROWS: return True
    return MAP_LAYOUT[ty][tx] == "#"

# ============================================================================
# Helpers
# ============================================================================
def load_json_dir(d):
    out = []
    if not os.path.isdir(d): return out
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                    out.append(json.load(f))
            except Exception: pass
    return out


def draw_text(surf, text, x, y, font=FONT_M, color=TEXT, center=False):
    r = font.render(str(text), True, color)
    if center: surf.blit(r, (x - r.get_width()//2, y))
    else:      surf.blit(r, (x, y))
    return r


def draw_panel(surf, rect, bg=PANEL_BG, border=PANEL_BORDER, radius=6, thickness=2):
    pygame.draw.rect(surf, bg, rect, border_radius=radius)
    pygame.draw.rect(surf, border, rect, thickness, border_radius=radius)


def fit(text, font, w):
    if font.size(text)[0] <= w: return text
    t = text
    while t and font.size("..." + t)[0] > w: t = t[1:]
    return "..." + t


def item_size(item_data):
    gs = item_data.get("grid_size")
    if isinstance(gs, (list, tuple)) and len(gs) == 2:
        try:
            w = max(1, min(8, int(gs[0])))
            h = max(1, min(8, int(gs[1])))
            return (w, h)
        except Exception:
            pass
    return (1, 1)


def item_icon(item_data, fallback_name=""):
    ic = (item_data.get("icon") or "").strip()
    if ic: return ic
    nm = (fallback_name or item_data.get("name", "") or "?").strip()
    return nm[:1].upper() if nm else "?"


def icon_font_for_size(w_px, h_px):
    if w_px >= CELL*2 and h_px >= CELL*2: return FONT_ICON_L
    if w_px <= CELL and h_px <= CELL:     return FONT_ICON_S
    return FONT_ICON_M


def draw_stack_badge(surf, x, y, count, font=FONT_S):
    """Desenha o contador de stack no canto inferior direito da área (x,y)."""
    txt = str(count)
    ts = font.render(txt, True, (255, 245, 220))
    pad = 3
    bw = ts.get_width() + pad*2
    bh = ts.get_height() + 1
    bx = x - bw - 2
    by = y - bh - 2
    bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 210))
    surf.blit(bg, (bx, by))
    pygame.draw.rect(surf, (60, 45, 30), (bx, by, bw, bh), 1, border_radius=2)
    surf.blit(ts, (bx + pad, by))


# ============================================================================
# Auto-organize — packer multi-heurística com rotação + merge de stacks
# ============================================================================
def _merge_stacks(items):
    """Mescla stacks empilháveis idênticos numa única lista."""
    merged = []
    for it in items:
        remaining = it.stack_count
        for m in merged:
            if remaining <= 0: break
            if m.can_stack_with(it):
                space = m.max_stack() - m.stack_count
                move = min(space, remaining)
                m.stack_count += move
                remaining -= move
        if remaining > 0:
            it.stack_count = remaining
            merged.append(it)
    return merged


def _pack_attempt(items, orig_sizes, cont_w, cont_h, order):
    grid = [[False]*cont_w for _ in range(cont_h)]

    def can_place(w, h, x, y):
        if x < 0 or y < 0 or x + w > cont_w or y + h > cont_h: return False
        for dy in range(h):
            for dx in range(w):
                if grid[y+dy][x+dx]: return False
        return True

    def first_fit(w, h):
        for y in range(cont_h - h + 1):
            for x in range(cont_w - w + 1):
                if can_place(w, h, x, y): return (x, y)
        return None

    def mark(w, h, x, y):
        for dy in range(h):
            for dx in range(w):
                grid[y+dy][x+dx] = True

    placements = []
    leftovers = []
    used = 0
    for it in order:
        ow, oh = orig_sizes[id(it)]
        candidates = [(ow, oh)] if ow == oh else [(ow, oh), (oh, ow)]
        done = False
        for (w, h) in candidates:
            if w > cont_w or h > cont_h: continue
            pos = first_fit(w, h)
            if pos:
                mark(w, h, pos[0], pos[1])
                placements.append((it, (w, h), pos))
                used += w * h
                done = True
                break
        if not done:
            leftovers.append(it)

    return leftovers, placements, used


def pack_items_into(cont, items):
    if not items:
        return []

    items = _merge_stacks(items)
    if not items:
        # Tudo virou merge — limpa o container e retorna
        for it in list(cont.items):
            cont.remove(it)
        return []

    orig_sizes = {id(it): tuple(it.size) for it in items}

    def key_area(it):   s = orig_sizes[id(it)]; return (-(s[0]*s[1]), -max(s), -min(s))
    def key_tall(it):   s = orig_sizes[id(it)]; return (-s[1], -(s[0]*s[1]), -s[0])
    def key_wide(it):   s = orig_sizes[id(it)]; return (-s[0], -(s[0]*s[1]), -s[1])
    def key_maxside(it):s = orig_sizes[id(it)]; return (-max(s), -min(s))
    def key_minside(it):s = orig_sizes[id(it)]; return (-min(s), -max(s))

    orders = [
        sorted(items, key=key_area),
        sorted(items, key=key_tall),
        sorted(items, key=key_wide),
        sorted(items, key=key_maxside),
        sorted(items, key=key_minside),
    ]

    best = None
    for order in orders:
        leftovers, placements, used = _pack_attempt(
            items, orig_sizes, cont.w, cont.h, order
        )
        score = (len(leftovers), -used)
        if best is None or score < best[0]:
            best = (score, placements, leftovers)

    _, placements, leftovers = best

    for it in list(cont.items):
        cont.remove(it)
    for it, (w, h), (x, y) in placements:
        it.size = (w, h)
        cont.place(it, x, y)

    return leftovers


def organize_container(cont):
    saved = [(it, it.x, it.y, tuple(it.size), it.stack_count) for it in cont.items]
    items = [it for it, _, _, _, _ in saved]

    for it in items:
        cont.remove(it)

    leftovers = pack_items_into(cont, items)

    if leftovers:
        for it in list(cont.items):
            cont.remove(it)
        for it, x, y, size, sc in saved:
            it.size = size
            it.stack_count = sc
            cont.place(it, x, y)
        return False
    return True


# ============================================================================
# PlacedItem
# ============================================================================
class PlacedItem:
    def __init__(self, data, prefix=None, suffix=None, stack_count=1):
        self.data = data
        self.prefix = prefix
        self.suffix = suffix
        self.size = item_size(data)
        self.x = 0; self.y = 0
        self.container = None
        self.stack_count = max(1, int(stack_count))

    # --- Stacking ------------------------------------------------------
    def max_stack(self):
        try:
            return max(1, int(self.data.get("max_stack", 1)))
        except Exception:
            return 1

    def is_stackable(self):
        if self.data.get("category") != "Consumível": return False
        return self.max_stack() > 1

    def stack_key(self):
        if not self.is_stackable(): return None
        pid = self.prefix.get("name") if self.prefix else None
        sid = self.suffix.get("name") if self.suffix else None
        return (id(self.data), pid, sid)

    def can_stack_with(self, other):
        if other is self or other is None: return False
        if not self.is_stackable() or not other.is_stackable(): return False
        if self.stack_count >= self.max_stack(): return False
        return self.stack_key() == other.stack_key()

    # --- Display -------------------------------------------------------
    def display_name(self):
        parts = []
        if self.prefix: parts.append(self.prefix.get("name",""))
        parts.append(self.data.get("name","?"))
        if self.suffix: parts.append(self.suffix.get("name",""))
        return " ".join(parts)

    def rarity(self): return self.data.get("rarity", "Comum")
    def rarity_color(self): return RARITY_COLORS.get(self.rarity(), TEXT)
    def icon(self): return item_icon(self.data, self.display_name())

    def is_equipment(self):
        return self.data.get("category") in ("Arma", "Armadura", "Acessório")

    def is_consumable(self):
        return self.data.get("category") == "Consumível"

    def equip_slot(self):
        eq = self.data.get("equipment") or {}
        return eq.get("slot", None)

    def get_all_effects(self):
        fx = []
        for src, kind in ((self.data, "item"), (self.prefix, "affix"), (self.suffix, "affix")):
            if not src: continue
            if kind == "affix":
                fx += src.get("special_effects", [])
            else:
                fx += (src.get("equipment") or {}).get("special_effects", [])
        return fx

    def get_stat_mods(self):
        mods = {}
        for src, kind in ((self.data, "item"), (self.prefix, "affix"), (self.suffix, "affix")):
            if not src: continue
            if kind == "affix":
                m = src.get("stat_modifiers", {})
            else:
                m = (src.get("equipment") or {}).get("stat_modifiers", {})
            for k, v in m.items(): mods[k] = mods.get(k, 0) + v
        return mods

    def get_resistances(self):
        res = {}
        for src, kind in ((self.data, "item"), (self.prefix, "affix"), (self.suffix, "affix")):
            if not src: continue
            if kind == "affix":
                r = src.get("resistances", {})
            else:
                r = (src.get("equipment") or {}).get("resistances", {})
            for k, v in r.items(): res[k] = res.get(k, 0) + v
        return res

    def get_damage(self):
        eq = self.data.get("equipment") or {}
        d = eq.get("damage", {})
        dmin = d.get("min", 0); dmax = d.get("max", 0); dtype = d.get("type", "Físico")
        for af in (self.prefix, self.suffix):
            if af:
                db = af.get("damage_bonus", {})
                dmin += db.get("min", 0); dmax += db.get("max", 0)
                if db.get("max", 0) > 0: dtype = db.get("type", dtype)
        if dmax == 0 and dmin == 0: return None
        return (dmin, dmax, dtype)

    def get_armor(self):
        eq = self.data.get("equipment") or {}
        return eq.get("armor", 0)

    def tooltip_lines(self):
        lines = []
        lines.append((self.display_name(), self.rarity_color()))
        cat = self.data.get("category", "")
        sub = self.data.get("subcategory", "")
        lines.append((f"{self.rarity()} {sub or cat}", TEXT_DIM))

        if self.stack_count > 1:
            lines.append((f"Quantidade: {self.stack_count} / {self.max_stack()}", (220, 200, 140)))

        dmg = self.get_damage()
        eq = self.data.get("equipment") or {}
        if dmg:
            dmin, dmax, dtype = dmg
            lines.append(("", TEXT))
            lines.append((f"Dano: {dmin}-{dmax}  ({dtype})", TEXT))
        if eq.get("armor", 0) > 0:
            lines.append((f"Armadura: {eq.get('armor', 0)}", TEXT))

        mods = self.get_stat_mods()
        if mods:
            lines.append(("", TEXT))
            for k, v in mods.items():
                sign = "+" if v >= 0 else ""
                color = SUCCESS if v >= 0 else DANGER
                lines.append((f"{sign}{v} {STAT_LABELS.get(k, k)}", color))

        res = self.get_resistances()
        if res:
            lines.append(("", TEXT))
            for k, v in res.items():
                lines.append((f"+{v}% Resistência a {RES_LABELS.get(k, k)}", (160, 200, 220)))

        fx = self.get_all_effects()
        if fx:
            lines.append(("", TEXT))
            for e in fx:
                trig = e.get("trigger", "?")
                lines.append((f"[{trig}] {e.get('type','?')} ({e.get('value',0)}) — {e.get('chance',100)}%",
                              (220, 180, 100)))

        lvl = self.data.get("level_required", 1)
        lines.append(("", TEXT))
        if lvl > 1: lines.append((f"Requer nível {lvl}", TEXT_DIM))
        lines.append((f"Vale {self.data.get('value',0)} ouro", TEXT_GOLD))

        desc = self.data.get("long_description") or self.data.get("description") or ""
        if desc:
            lines.append(("", TEXT))
            words = desc.split()
            cur = ""
            for w in words:
                if len(cur) + len(w) + 1 > 44:
                    lines.append((f'"{cur}"', (180, 160, 120)))
                    cur = w
                else:
                    cur = (cur + " " + w).strip()
            if cur: lines.append((f'"{cur}"', (180, 160, 120)))
        return lines


# ============================================================================
# Container
# ============================================================================
class Container:
    def __init__(self, w, h, name="Container"):
        self.w = w; self.h = h; self.name = name
        self.grid = [[None]*w for _ in range(h)]
        self.items = []

    def can_place_size(self, w, h, x, y):
        if x < 0 or y < 0 or x + w > self.w or y + h > self.h: return False
        for dy in range(h):
            for dx in range(w):
                if self.grid[y+dy][x+dx] is not None: return False
        return True

    def can_place(self, item, x, y):
        w, h = item.size
        return self.can_place_size(w, h, x, y)

    def place(self, item, x, y):
        if not self.can_place(item, x, y): return False
        iw, ih = item.size
        for dy in range(ih):
            for dx in range(iw):
                self.grid[y+dy][x+dx] = item
        item.x = x; item.y = y; item.container = self
        if item not in self.items: self.items.append(item)
        return True

    def remove(self, item):
        if item not in self.items: return False
        iw, ih = item.size
        for dy in range(ih):
            for dx in range(iw):
                yy, xx = item.y+dy, item.x+dx
                if 0 <= yy < self.h and 0 <= xx < self.w:
                    self.grid[yy][xx] = None
        self.items.remove(item)
        item.container = None
        return True

    def find_free_spot(self, item):
        iw, ih = item.size
        for y in range(self.h - ih + 1):
            for x in range(self.w - iw + 1):
                if self.can_place(item, x, y): return (x, y)
        return None

    def add_auto(self, item):
        """Tenta empilhar em stacks existentes e depois achar slot livre."""
        if item.is_stackable():
            for existing in list(self.items):
                if item.stack_count <= 0: break
                if existing.can_stack_with(item):
                    space = existing.max_stack() - existing.stack_count
                    move = min(space, item.stack_count)
                    existing.stack_count += move
                    item.stack_count -= move
            if item.stack_count <= 0:
                return True
        spot = self.find_free_spot(item)
        if not spot: return False
        return self.place(item, spot[0], spot[1])


# ============================================================================
# Player / entities
# ============================================================================
class Player:
    def __init__(self, x, y):
        self.x = x; self.y = y
        self.gold = 100
        self.inventory = Container(INV_COLS, INV_ROWS, "Inventário")
        self.equipment = {slot: None for slot in EQUIP_SLOTS}
        self.hp = 100; self.max_hp = 100


class GroundItem:
    def __init__(self, item, x, y):
        self.item = item; self.x = x; self.y = y


class Chest:
    def __init__(self, x, y, name="Baú"):
        self.x = x; self.y = y; self.name = name
        self.container = Container(8, 5, name)


class Corpse:
    def __init__(self, x, y, name="Corpo"):
        self.x = x; self.y = y; self.name = name
        self.container = Container(6, 4, name)


class World:
    def __init__(self):
        self.ground_items = []
        self.chests = []
        self.corpses = []

    def is_free(self, x, y):
        if is_wall(x, y): return False
        for gi in self.ground_items:
            if gi.x == x and gi.y == y: return False
        for c in self.chests:
            if c.x == x and c.y == y: return False
        for c in self.corpses:
            if c.x == x and c.y == y: return False
        return True

    def find_free_near(self, cx, cy):
        for r in range(0, 8):
            for dy in range(-r, r+1):
                for dx in range(-r, r+1):
                    if abs(dx) != r and abs(dy) != r: continue
                    nx, ny = cx+dx, cy+dy
                    if self.is_free(nx, ny): return (nx, ny)
        return None


def roll_item(items_lib, affixes_lib):
    if not items_lib: return None
    item = random.choice(items_lib)
    cat = item.get("category", "")
    prefix = suffix = None
    if random.random() < 0.45:
        cands = [a for a in affixes_lib if a.get("kind") == "Prefixo"
                 and cat in a.get("applies_to", [])]
        if cands: prefix = random.choice(cands)
    if random.random() < 0.45:
        cands = [a for a in affixes_lib if a.get("kind") == "Sufixo"
                 and cat in a.get("applies_to", [])]
        if cands: suffix = random.choice(cands)
    pi = PlacedItem(item, prefix, suffix)
    # Consumíveis spawnam em pequenos stacks aleatórios (até max_stack)
    if pi.is_stackable():
        cap = pi.max_stack()
        pi.stack_count = random.randint(1, cap)
    return pi


# ============================================================================
# Main Scene
# ============================================================================
class MainScene:
    def __init__(self, app):
        self.app = app
        self.items_lib = load_json_dir(ITEMS_DIR)
        self.affixes_lib = load_json_dir(AFFIXES_DIR)
        self.units_lib = load_json_dir(UNITS_DIR)

        self.world = World()
        self.player = Player(10, 7)

        if self.items_lib:
            for _ in range(3):
                it = roll_item(self.items_lib, self.affixes_lib)
                if it:
                    spot = self.world.find_free_near(10, 7)
                    if spot:
                        self.world.ground_items.append(GroundItem(it, spot[0], spot[1]))

        chest = Chest(3, 3, "Baú Antigo")
        self._fill_container_random(chest.container, 4)
        self.world.chests.append(chest)

        chest2 = Chest(16, 11, "Baú do Tesouro")
        self._fill_container_random(chest2.container, 5)
        self.world.chests.append(chest2)

        corpse = Corpse(5, 11, "Corpo de Aventureiro")
        self._fill_container_random(corpse.container, 3)
        self.world.corpses.append(corpse)

        self.cursor_item = None
        self.cursor_source = None
        self.drag_offset = (0, 0)
        self.open_container = None
        self.open_container_rect = None
        self.open_container_close_rect = None
        self.log = []
        self.msg = ""
        self.msg_timer = 0.0

        self.ground_labels = []
        self.hover_lines = None
        self._ground_icon_cache = []

        self._snap = None

        self.show_labels = False
        self.temp_labels = False
        self.ctrl_held = False

        self._log("Sistema iniciado. CTRL compara · R gira · Z nomes · O organiza", ACCENT)

    def _log(self, text, color=TEXT):
        self.log.append((text, color))
        if len(self.log) > 200: self.log = self.log[-200:]

    def _msg(self, text, color=ACCENT):
        self.msg = text; self.msg_color = color; self.msg_timer = 3.0

    # ------------------------------------------------------------------
    def _fill_container_random(self, cont, n_items):
        items = []
        for _ in range(n_items):
            it = roll_item(self.items_lib, self.affixes_lib)
            if it: items.append(it)
        pack_items_into(cont, items)

    def _organize_all(self):
        ok_inv = organize_container(self.player.inventory)
        ok_cont = True
        if self.open_container:
            ok_cont = organize_container(self.open_container)
        if ok_inv and ok_cont:
            self._log("Organizado.", ACCENT)
        else:
            self._msg("Não deu pra organizar (sem espaço).", DANGER)

    # ==================================================================
    def handle_events(self, events):
        for e in events:
            if e.type == pygame.QUIT:
                self.app.running = False; return
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                    self.ctrl_held = True
                if e.key == pygame.K_ESCAPE:
                    if self.cursor_item:
                        self._return_cursor_to_source()
                    elif self.open_container:
                        self.open_container = None
                        self.open_container_close_rect = None
                    else:
                        self.app.running = False
                    return
                if e.key in (pygame.K_w, pygame.K_UP):    self._try_move(0, -1)
                if e.key in (pygame.K_s, pygame.K_DOWN):  self._try_move(0, 1)
                if e.key in (pygame.K_a, pygame.K_LEFT):  self._try_move(-1, 0)
                if e.key in (pygame.K_d, pygame.K_RIGHT): self._try_move(1, 0)
                if e.key == pygame.K_SPACE: self._spawn_near()
                if e.key == pygame.K_c: self._spawn_chest_near()
                if e.key == pygame.K_x: self._spawn_corpse_near()
                if e.key == pygame.K_o: self._organize_all()
                if e.key == pygame.K_z:
                    self.show_labels = not self.show_labels
                    state = "ATIVADOS" if self.show_labels else "DESATIVADOS"
                    self._log(f"Nomes no chão: {state}", ACCENT)
                if e.key == pygame.K_r and self.cursor_item:
                    w, h = self.cursor_item.size
                    self.cursor_item.size = (h, w)
                    self._log(f"Rotacionado: {w}x{h} -> {h}x{w}", ACCENT)
                if e.key in (pygame.K_LALT, pygame.K_RALT):
                    self.temp_labels = True
            if e.type == pygame.KEYUP:
                if e.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                    self.ctrl_held = False
                if e.key in (pygame.K_LALT, pygame.K_RALT):
                    self.temp_labels = False
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1: self._on_left_click(e.pos)
                elif e.button == 3: self._on_right_click(e.pos)

    def _try_move(self, dx, dy):
        if self.cursor_item: return
        nx, ny = self.player.x + dx, self.player.y + dy
        if is_wall(nx, ny): return
        for c in self.world.chests + self.world.corpses:
            if c.x == nx and c.y == ny: return
        self.player.x = nx; self.player.y = ny

    def _spawn_near(self):
        it = roll_item(self.items_lib, self.affixes_lib)
        if not it:
            self._msg("Sem itens na biblioteca.", DANGER); return
        spot = self.world.find_free_near(self.player.x, self.player.y)
        if not spot:
            self._msg("Sem espaço ao redor.", DANGER); return
        self.world.ground_items.append(GroundItem(it, spot[0], spot[1]))
        extra = f" x{it.stack_count}" if it.stack_count > 1 else ""
        self._log(f"Item gerado: {it.display_name()}{extra}", it.rarity_color())

    def _spawn_chest_near(self):
        spot = self.world.find_free_near(self.player.x, self.player.y)
        if not spot:
            self._msg("Sem espaço.", DANGER); return
        chest = Chest(spot[0], spot[1], "Baú")
        self._fill_container_random(chest.container, random.randint(2, 5))
        self.world.chests.append(chest)
        self._log(f"Baú em ({spot[0]},{spot[1]})", ACCENT)

    def _spawn_corpse_near(self):
        spot = self.world.find_free_near(self.player.x, self.player.y)
        if not spot:
            self._msg("Sem espaço.", DANGER); return
        corpse = Corpse(spot[0], spot[1], "Corpo")
        self._fill_container_random(corpse.container, random.randint(1, 4))
        self.world.corpses.append(corpse)
        self._log(f"Corpo em ({spot[0]},{spot[1]})", ACCENT)

    # ------------------------------------------------------------------
    def _compute_drag_offset(self, item, mouse_pos):
        w_px = item.size[0] * CELL
        h_px = item.size[1] * CELL
        return (-w_px // 2, -h_px // 2)

    # ==================================================================
    def _on_left_click(self, pos):
        if self.cursor_item:
            if self._try_place_cursor(pos):
                return
            tile = self._tile_at(pos)
            if tile and not is_wall(*tile):
                self._drop_to_ground(self.cursor_item, tile)
                self.cursor_item = None
                self.cursor_source = None
                return
            return

        for rect, cb in self._buttons_rects():
            if rect.collidepoint(pos): cb(); return

        if self.open_container_close_rect and \
           self.open_container_close_rect.collidepoint(pos):
            self.open_container = None
            self.open_container_close_rect = None
            return

        if self.open_container and self.open_container_rect:
            cont = self.open_container
            x0, y0 = self.open_container_rect.topleft
            gx = (pos[0] - x0) // CELL
            gy = (pos[1] - y0) // CELL
            if 0 <= gx < cont.w and 0 <= gy < cont.h:
                it = cont.grid[gy][gx]
                if it:
                    offset = self._compute_drag_offset(it, pos)
                    cont.remove(it)
                    self.cursor_item = it
                    self.cursor_source = cont
                    self.drag_offset = offset
                    return
                return

        eq_click = self._equip_slot_at(pos)
        if eq_click:
            slot, item = eq_click
            if item:
                self.drag_offset = self._compute_drag_offset(item, pos)
                self.player.equipment[slot] = None
                self.cursor_item = item
                self.cursor_source = ("equip", slot)
            return

        inv_x0, inv_y0 = self._inv_origin()
        if self._inside(pos, inv_x0, inv_y0, INV_COLS*CELL, INV_ROWS*CELL):
            gx = (pos[0] - inv_x0) // CELL
            gy = (pos[1] - inv_y0) // CELL
            it = self.player.inventory.grid[gy][gx]
            if it:
                offset = self._compute_drag_offset(it, pos)
                self.player.inventory.remove(it)
                self.cursor_item = it
                self.cursor_source = self.player.inventory
                self.drag_offset = offset
            return

        for rect, gi in self.ground_labels:
            if rect.collidepoint(pos):
                if abs(gi.x - self.player.x) + abs(gi.y - self.player.y) <= 2:
                    self._pickup_ground(gi)
                else:
                    self._msg("Muito longe para pegar.", DANGER)
                return

        tile = self._tile_at(pos)
        if tile:
            tx, ty = tile
            if abs(tx - self.player.x) + abs(ty - self.player.y) <= 2:
                for c in self.world.chests:
                    if c.x == tx and c.y == ty:
                        self.open_container = c.container
                        self._log(f"Abriu {c.name}", ACCENT)
                        return
                for c in self.world.corpses:
                    if c.x == tx and c.y == ty:
                        self.open_container = c.container
                        self._log(f"Abriu {c.name}", ACCENT)
                        return

    def _on_right_click(self, pos):
        inv_x0, inv_y0 = self._inv_origin()
        if self._inside(pos, inv_x0, inv_y0, INV_COLS*CELL, INV_ROWS*CELL):
            gx = (pos[0] - inv_x0) // CELL
            gy = (pos[1] - inv_y0) // CELL
            it = self.player.inventory.grid[gy][gx]
            if it: self._auto_use(it); return
        if self.open_container and self.open_container_rect:
            cont = self.open_container
            x0, y0 = self.open_container_rect.topleft
            gx = (pos[0] - x0) // CELL
            gy = (pos[1] - y0) // CELL
            if 0 <= gx < cont.w and 0 <= gy < cont.h:
                it = cont.grid[gy][gx]
                if it:
                    cont.remove(it)
                    if self.player.inventory.add_auto(it):
                        self._log(f"Pegou: {it.display_name()}", it.rarity_color())
                    else:
                        self.cursor_item = it
                        self.cursor_source = cont
                        self.drag_offset = self._compute_drag_offset(it, pos)
                        self._log(f"Na mão: {it.display_name()} (inv cheio)", WARN)
                    return
        eq_click = self._equip_slot_at(pos)
        if eq_click:
            slot, item = eq_click
            if item:
                self.player.equipment[slot] = None
                if not self.player.inventory.add_auto(item):
                    self.cursor_item = item
                    self.cursor_source = None
                    self.drag_offset = self._compute_drag_offset(item, pos)
                    self._log(f"Na mão: {item.display_name()} (inv cheio)", WARN)
                else:
                    self._log(f"Desequipou: {item.display_name()}", ACCENT)

    # ==================================================================
    def _snap_for_container(self, cont, grid_origin, item, mouse_pos):
        x0, y0 = grid_origin
        iw, ih = item.size

        cx = mouse_pos[0] - x0
        cy = mouse_pos[1] - y0
        mx = int(round(cx / CELL - iw / 2))
        my = int(round(cy / CELL - ih / 2))

        max_x = cont.w - iw
        max_y = cont.h - ih
        if max_x < 0 or max_y < 0:
            return None
        mx = max(0, min(max_x, mx))
        my = max(0, min(max_y, my))

        occupants = {}
        for dx in range(iw):
            for dy in range(ih):
                cell = cont.grid[my + dy][mx + dx]
                if cell is not None and cell is not item:
                    occupants[id(cell)] = cell

        if not occupants:
            return {"gx": mx, "gy": my, "target": None, "kind": "ok"}

        if len(occupants) == 1:
            target = next(iter(occupants.values()))
            saved = {}
            for ddx in range(target.size[0]):
                for ddy in range(target.size[1]):
                    gx_, gy_ = target.x + ddx, target.y + ddy
                    if 0 <= gx_ < cont.w and 0 <= gy_ < cont.h:
                        saved[(gx_, gy_)] = cont.grid[gy_][gx_]
                        cont.grid[gy_][gx_] = None
            can = cont.can_place(item, mx, my)
            for (gx_, gy_), v in saved.items():
                cont.grid[gy_][gx_] = v
            if can:
                return {"gx": mx, "gy": my, "target": target, "kind": "swap"}
            return None

        return None

    def _compute_snap(self):
        if not self.cursor_item: return None
        it = self.cursor_item
        mouse = pygame.mouse.get_pos()

        eq_click = self._equip_slot_at(mouse)
        if eq_click:
            slot, _ = eq_click
            if self._can_equip_to_slot(it, slot):
                slot_w = (PANEL_W - 40) // 3 - 6
                slot_h = 50
                for i, name in enumerate(EQUIP_SLOTS):
                    if name == slot:
                        col = i % 3; row = i // 3
                        rx = PANEL_X + 20 + col * (slot_w + 6)
                        ry = PANEL_Y + 50 + row * (slot_h + 6)
                        return {"kind": "equip", "x": rx, "y": ry,
                                "w": slot_w, "h": slot_h}

        if self.open_container and self.open_container_rect:
            cont = self.open_container
            x0, y0 = self.open_container_rect.topleft
            cw = cont.w * CELL
            ch = cont.h * CELL
            if self._inside(mouse, x0, y0, cw, ch):
                sol = self._snap_for_container(cont, (x0, y0), it, mouse)
                if sol:
                    return {"kind": "grid",
                            "x": x0 + sol["gx"] * CELL,
                            "y": y0 + sol["gy"] * CELL,
                            "w": it.size[0] * CELL,
                            "h": it.size[1] * CELL,
                            "cont": cont,
                            "gx": sol["gx"], "gy": sol["gy"],
                            "target": sol["target"],
                            "preview": sol["kind"]}

        inv_x0, inv_y0 = self._inv_origin()
        inv_w = INV_COLS * CELL
        inv_h = INV_ROWS * CELL
        if self._inside(mouse, inv_x0, inv_y0, inv_w, inv_h):
            sol = self._snap_for_container(self.player.inventory,
                                            (inv_x0, inv_y0), it, mouse)
            if sol:
                return {"kind": "grid",
                        "x": inv_x0 + sol["gx"] * CELL,
                        "y": inv_y0 + sol["gy"] * CELL,
                        "w": it.size[0] * CELL,
                        "h": it.size[1] * CELL,
                        "cont": self.player.inventory,
                        "gx": sol["gx"], "gy": sol["gy"],
                        "target": sol["target"],
                        "preview": sol["kind"]}

        return None

    def _try_place_cursor(self, pos):
        it = self.cursor_item
        if it is None: return False

        eq_click = self._equip_slot_at(pos)
        if eq_click:
            slot, current = eq_click
            if self._can_equip_to_slot(it, slot):
                if current is it: return False
                self.player.equipment[slot] = it
                if current is not None:
                    self.cursor_item = current
                    self.cursor_source = ("equip", slot)
                    self.drag_offset = self._compute_drag_offset(current, pos)
                    self._log(f"Trocou: {it.display_name()} equipado · "
                              f"{current.display_name()} na mão", ACCENT)
                else:
                    self.cursor_item = None
                    self.cursor_source = None
                    self._log(f"Equipou: {it.display_name()}", it.rarity_color())
                return True

        if self.open_container and self.open_container_rect:
            cont = self.open_container
            x0, y0 = self.open_container_rect.topleft
            cw = cont.w * CELL
            ch = cont.h * CELL
            if self._inside(pos, x0, y0, cw, ch):
                sol = self._snap_for_container(cont, (x0, y0), it, pos)
                if sol:
                    if self._apply_drop(cont, sol, it, pos):
                        return True
                else:
                    self._msg("Sem espaço aí.", DANGER)
                    return False

        inv_x0, inv_y0 = self._inv_origin()
        inv_w = INV_COLS * CELL
        inv_h = INV_ROWS * CELL
        if self._inside(pos, inv_x0, inv_y0, inv_w, inv_h):
            sol = self._snap_for_container(self.player.inventory,
                                            (inv_x0, inv_y0), it, pos)
            if sol:
                if self._apply_drop(self.player.inventory, sol, it, pos):
                    return True
            else:
                self._msg("Sem espaço aí.", DANGER)
                return False

        return False

    def _apply_drop(self, cont, sol, it, pos):
        """Aplica o resultado do snap: coloca, empilha ou troca."""
        gx, gy, target, kind = sol["gx"], sol["gy"], sol["target"], sol["kind"]

        if kind == "ok":
            cont.place(it, gx, gy)
            self.cursor_item = None
            self.cursor_source = None
            return True

        if kind == "swap":
            # Se der pra empilhar no alvo, empilha em vez de trocar
            if target is not None and it.can_stack_with(target):
                space = target.max_stack() - target.stack_count
                move = min(space, it.stack_count)
                target.stack_count += move
                it.stack_count -= move
                if it.stack_count <= 0:
                    self.cursor_item = None
                    self.cursor_source = None
                    self._log(f"Empilhou: {target.display_name()} "
                              f"(x{target.stack_count})", ACCENT)
                else:
                    # sobrou no cursor; continua com ele
                    self.cursor_item = it
                    self._log(f"Empilhou parcialmente: "
                              f"{target.display_name()} (x{target.stack_count})", ACCENT)
                return True

            # Swap padrão
            cont.remove(target)
            cont.place(it, gx, gy)
            self.cursor_item = target
            self.cursor_source = cont
            self.drag_offset = self._compute_drag_offset(target, pos)
            self._log(f"Trocou: {target.display_name()} <-> "
                      f"{it.display_name()}", ACCENT)
            return True
        return False

    def _can_equip_to_slot(self, item, slot):
        es = item.equip_slot()
        if not es: return False
        target = SLOT_MAP.get(es)
        if isinstance(target, list): return slot in target
        return slot == target

    def _return_cursor_to_source(self):
        it = self.cursor_item
        src = self.cursor_source
        if src is None:
            self._drop_to_ground(it, (self.player.x, self.player.y))
        elif isinstance(src, Container):
            if not src.add_auto(it):
                if not self.player.inventory.add_auto(it):
                    self._drop_to_ground(it, (self.player.x, self.player.y))
        elif isinstance(src, tuple) and src[0] == "equip":
            slot = src[1]
            if self.player.equipment.get(slot) is None:
                self.player.equipment[slot] = it
            else:
                if not self.player.inventory.add_auto(it):
                    self._drop_to_ground(it, (self.player.x, self.player.y))
        else:
            if not self.player.inventory.add_auto(it):
                self._drop_to_ground(it, (self.player.x, self.player.y))
        self.cursor_item = None
        self.cursor_source = None

    def _auto_use(self, item):
        if item.is_equipment():
            es = item.equip_slot()
            if not es: return
            target = SLOT_MAP.get(es)
            if isinstance(target, list):
                slot = None
                for s in target:
                    if self.player.equipment[s] is None: slot = s; break
                if slot is None: slot = target[0]
            else:
                slot = target
            self.player.inventory.remove(item)
            old = self.player.equipment[slot]
            if old:
                if not self.player.inventory.add_auto(old):
                    self._drop_to_ground(old, (self.player.x, self.player.y))
                else:
                    self._log(f"Desequipou: {old.display_name()}", ACCENT)
            self.player.equipment[slot] = item
            self._log(f"Equipou: {item.display_name()}", item.rarity_color())
            return
        if item.is_consumable():
            if item.stack_count > 1:
                item.stack_count -= 1
                self._log(f"Usou: {item.display_name()} "
                          f"({item.stack_count} restam)", SUCCESS)
            else:
                self._log(f"Usou: {item.display_name()} (efeito omitido)", SUCCESS)
                self.player.inventory.remove(item)
            return

    def _pickup_ground(self, ground_item):
        it = ground_item.item
        if self.player.inventory.add_auto(it):
            self.world.ground_items.remove(ground_item)
            extra = f" x{it.stack_count}" if it.stack_count > 1 else ""
            self._log(f"Pegou: {it.display_name()}{extra}", it.rarity_color())
            return
        self.world.ground_items.remove(ground_item)
        self.cursor_item = it
        self.cursor_source = None
        self.drag_offset = self._compute_drag_offset(it, pygame.mouse.get_pos())
        self._log(f"Na mão (inventário cheio): {it.display_name()}", WARN)

    def _drop_to_ground(self, item, tile):
        if not tile: return
        if not self.world.is_free(*tile):
            spot = self.world.find_free_near(*tile)
            if not spot: return
            tile = spot
        self.world.ground_items.append(GroundItem(item, tile[0], tile[1]))
        extra = f" x{item.stack_count}" if item.stack_count > 1 else ""
        self._log(f"Jogou no chão: {item.display_name()}{extra}", TEXT_DIM)

    # ==================================================================
    def _tile_at(self, pos):
        if pos[0] < MAP_X or pos[1] < MAP_Y: return None
        tx = (pos[0] - MAP_X) // TILE
        ty = (pos[1] - MAP_Y) // TILE
        if 0 <= tx < MAP_COLS and 0 <= ty < MAP_ROWS: return (tx, ty)
        return None

    def _inv_origin(self):
        total_w = INV_COLS * CELL
        x0 = PANEL_X + (PANEL_W - total_w) // 2
        y0 = PANEL_Y + 300
        return (x0, y0)

    def _equip_slot_at(self, pos):
        slot_w = (PANEL_W - 40) // 3 - 6
        slot_h = 50
        for i, name in enumerate(EQUIP_SLOTS):
            col = i % 3
            row = i // 3
            x = PANEL_X + 20 + col * (slot_w + 6)
            y = PANEL_Y + 50 + row * (slot_h + 6)
            r = pygame.Rect(x, y, slot_w, slot_h)
            if r.collidepoint(pos):
                return (name, self.player.equipment.get(name))
        return None

    def _inside(self, pos, x, y, w, h):
        return x <= pos[0] < x+w and y <= pos[1] < y+h

    def _buttons_rects(self):
        r1 = pygame.Rect(LOG_X + 10,  LOG_Y + 10, 130, 30)
        r2 = pygame.Rect(LOG_X + 150, LOG_Y + 10, 130, 30)
        r3 = pygame.Rect(LOG_X + 290, LOG_Y + 10, 130, 30)
        r4 = pygame.Rect(LOG_X + 430, LOG_Y + 10, 130, 30)
        return [
            (r1, self._spawn_near),
            (r2, self._spawn_chest_near),
            (r3, self._spawn_corpse_near),
            (r4, self._organize_all),
        ]

    # ==================================================================
    def update(self, dt):
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0: self.msg = ""
        self._snap = self._compute_snap()

    # ==================================================================
    def draw(self, surf, dt):
        surf.fill(BG)
        self._draw_map(surf)
        self._draw_ground_items_icons(surf)
        self._draw_ground_items_labels(surf)
        self._draw_panel(surf)
        self._draw_buttons(surf)
        self._draw_log(surf)
        self._draw_open_container(surf)
        self._draw_tooltip(surf)
        self._draw_snap_highlight(surf)
        self._draw_cursor_item(surf)
        self._draw_msg(surf)

        if self.show_labels:
            state_txt = "[Z] NOMES: LIGADOS"
            state_col = SUCCESS
        elif self.temp_labels:
            state_txt = "[ALT] NOMES: TEMPORÁRIO"
            state_col = WARN
        else:
            state_txt = "[Z] NOMES: DESLIGADOS  (ALT segura · mouse hover)"
            state_col = TEXT_DIM
        draw_text(surf, state_txt, WIDTH//2, HEIGHT - 40, FONT_S, state_col, center=True)

        ctrl = ("WASD: mover · ESPAÇO: item · C: baú · X: corpo · O: organizar · "
                "Z: nomes · ALT: nomes · R: girar · CTRL: comparar · ESC: sair")
        draw_text(surf, ctrl, WIDTH//2, HEIGHT - 20, FONT_S, TEXT_DIM, center=True)

    def _draw_map(self, surf):
        for ty in range(MAP_ROWS):
            for tx in range(MAP_COLS):
                x = MAP_X + tx * TILE
                y = MAP_Y + ty * TILE
                wall = MAP_LAYOUT[ty][tx] == "#"
                if wall:
                    pygame.draw.rect(surf, MAP_WALL, (x, y, TILE, TILE))
                    pygame.draw.rect(surf, MAP_WALL_TOP, (x, y, TILE, 6))
                else:
                    base = MAP_FLOOR if (tx+ty) % 2 == 0 else MAP_FLOOR2
                    pygame.draw.rect(surf, base, (x, y, TILE, TILE))
                    pygame.draw.line(surf, (30, 24, 18), (x, y+TILE), (x+TILE, y+TILE))

        pygame.draw.rect(surf, MAP_BORDER, (MAP_X-2, MAP_Y-2, MAP_W+4, MAP_H+4), 2)

        for c in self.world.chests:
            self._draw_chest_icon(surf, c.x, c.y, (140, 95, 40))
        for c in self.world.corpses:
            self._draw_corpse_icon(surf, c.x, c.y)

        px = MAP_X + self.player.x * TILE
        py = MAP_Y + self.player.y * TILE
        pygame.draw.circle(surf, (240, 220, 180), (px+TILE//2, py+TILE//2), 12)
        pygame.draw.circle(surf, (80, 60, 40), (px+TILE//2, py+TILE//2), 12, 2)

    def _draw_chest_icon(self, surf, tx, ty, col):
        x = MAP_X + tx * TILE
        y = MAP_Y + ty * TILE
        pygame.draw.rect(surf, col, (x+6, y+12, TILE-12, TILE-18), border_radius=3)
        pygame.draw.rect(surf, (200, 150, 70), (x+6, y+18, TILE-12, 4))
        pygame.draw.rect(surf, (60, 40, 20), (x+6, y+12, TILE-12, TILE-18), 2, border_radius=3)

    def _draw_corpse_icon(self, surf, tx, ty):
        x = MAP_X + tx * TILE
        y = MAP_Y + ty * TILE
        pygame.draw.line(surf, (90, 80, 70), (x+8, y+8), (x+TILE-8, y+TILE-8), 4)
        pygame.draw.line(surf, (90, 80, 70), (x+TILE-8, y+8), (x+8, y+TILE-8), 4)

    def _draw_ground_items_icons(self, surf):
        self._ground_icon_cache = []
        t = pygame.time.get_ticks() / 1000.0

        for gi in self.world.ground_items:
            x = MAP_X + gi.x * TILE
            y = MAP_Y + gi.y * TILE
            col = gi.item.rarity_color()
            rarity = gi.item.rarity()

            # Glow pulsante por raridade
            base_a, speed = RARITY_GLOW.get(rarity, (0, 0.0))
            if base_a > 0:
                pulse = 0.5 + 0.5 * math.sin(t * speed)
                alpha = int(base_a * (0.30 + 0.70 * pulse))
                expand = int(4 * pulse) + 1

                glow_size = TILE - 12 + expand * 2
                glow_surf = pygame.Surface((glow_size + 10, glow_size + 10),
                                           pygame.SRCALPHA)
                cx = glow_surf.get_width() // 2
                cy = glow_surf.get_height() // 2
                for layer in range(3):
                    a = int(alpha * (1.0 - layer * 0.35))
                    if a <= 0: continue
                    r = glow_size // 2 + layer * 2
                    pygame.draw.rect(
                        glow_surf, (*col, a),
                        (cx - r, cy - r, r*2, r*2),
                        border_radius=6 + layer * 2
                    )
                surf.blit(glow_surf,
                          (x + TILE//2 - glow_surf.get_width()//2,
                           y + TILE//2 - glow_surf.get_height()//2))

            # Caixa do item
            pygame.draw.rect(surf, (30, 20, 15), (x+6, y+6, TILE-12, TILE-12),
                             border_radius=4)
            pygame.draw.rect(surf, col, (x+6, y+6, TILE-12, TILE-12), 2,
                             border_radius=4)

            icon_glyph = gi.item.icon()
            r = FONT_ICON_M.render(icon_glyph, True, col)
            max_w = TILE - 14
            if r.get_width() > max_w:
                scale = max_w / r.get_width()
                r = pygame.transform.smoothscale(
                    r, (int(r.get_width()*scale), int(r.get_height()*scale)))
            surf.blit(r, (x+TILE//2 - r.get_width()//2,
                          y+TILE//2 - r.get_height()//2))

            # Contador de stack
            if gi.item.stack_count > 1:
                draw_stack_badge(surf, x + TILE - 4, y + TILE - 4,
                                 gi.item.stack_count, FONT_XS)

            self._ground_icon_cache.append((gi, x, y))

    def _draw_ground_items_labels(self, surf):
        self.ground_labels = []
        mouse = pygame.mouse.get_pos()
        show_all = self.show_labels or self.temp_labels

        pending = []
        for gi, x, y in self._ground_icon_cache:
            label = gi.item.display_name()
            if gi.item.stack_count > 1:
                label += f" x{gi.item.stack_count}"
            text_w = FONT_S.size(label)[0]
            lw = text_w + 8
            lh = 18

            lx = x + TILE + 4
            ly = y + 4
            if lx + lw > MAP_X + MAP_W:
                lx = x - lw - 12

            tile_rect = pygame.Rect(x, y, TILE, TILE)
            original_rect = pygame.Rect(lx, ly, lw, lh)
            hovered = tile_rect.collidepoint(mouse) or original_rect.collidepoint(mouse)

            if show_all or hovered:
                pending.append((gi, lx, ly, lw, lh, hovered))

        pending.sort(key=lambda p: (0 if p[5] else 1, p[2]))

        used_rects = []
        for gi, lx, ly, lw, lh, hovered in pending:
            final = self._resolve_label_position(lx, ly, lw, lh, used_rects)
            used_rects.append(final)

            col = gi.item.rarity_color()
            bg_col = (10, 8, 6) if hovered else (20, 16, 12)
            pygame.draw.rect(surf, bg_col, final, border_radius=3)
            border_col = col if hovered else tuple(int(c*0.8) for c in col)
            pygame.draw.rect(surf, border_col, final, 1, border_radius=3)
            label = gi.item.display_name()
            if gi.item.stack_count > 1:
                label += f" x{gi.item.stack_count}"
            draw_text(surf, label, final.x+4, final.y+2, FONT_S, col)
            self.ground_labels.append((final, gi))

    def _resolve_label_position(self, lx, ly, lw, lh, used_rects):
        min_y = MAP_Y + 2
        max_y = MAP_Y + MAP_H - lh - 2

        candidates = [0]
        step = lh + 2
        for s in range(step, 200, step):
            candidates.append(s)
            candidates.append(-s)

        for shift in candidates:
            ty = ly + shift
            ty = max(min_y, min(max_y, ty))
            r = pygame.Rect(lx, ty, lw, lh)
            if not any(r.colliderect(u) for u in used_rects):
                return r

        ty = max(min_y, min(max_y, ly))
        return pygame.Rect(lx, ty, lw, lh)

    # ------------------------------------------------------------------
    def _draw_panel(self, surf):
        panel_rect = pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)
        draw_panel(surf, panel_rect)

        draw_text(surf, "EQUIPAMENTO", PANEL_X + 20, PANEL_Y + 20, FONT_L, ACCENT)

        slot_w = (PANEL_W - 40) // 3 - 6
        slot_h = 50
        mouse = pygame.mouse.get_pos()
        for i, name in enumerate(EQUIP_SLOTS):
            col = i % 3; row = i // 3
            x = PANEL_X + 20 + col * (slot_w + 6)
            y = PANEL_Y + 50 + row * (slot_h + 6)
            r = pygame.Rect(x, y, slot_w, slot_h)
            hovered = r.collidepoint(mouse)
            bg = SLOT_HOVER if hovered else SLOT_BG
            pygame.draw.rect(surf, bg, r, border_radius=4)
            pygame.draw.rect(surf, ACCENT_DARK, r, 1, border_radius=4)

            item = self.player.equipment.get(name)
            draw_text(surf, name, x+6, y+2, FONT_XS, TEXT_DIM)
            if item:
                col2 = item.rarity_color()
                draw_text(surf, fit(item.data.get("name",""), FONT_S, slot_w-30),
                          x+6, y+20, FONT_S, col2)
                if item.prefix or item.suffix:
                    draw_text(surf, "★", x+slot_w-14, y+20, FONT_S, (240, 200, 80))
                ic = item.icon()
                ri = FONT_ICON_S.render(ic, True, col2)
                surf.blit(ri, (x + slot_w - 18, y + 22))

        inv_title_y = PANEL_Y + 280
        draw_text(surf, "INVENTÁRIO", PANEL_X + 20, inv_title_y, FONT_L, ACCENT)
        draw_text(surf, "(clique p/ pegar · R gira · CTRL compara · dir. equipa · O organiza)",
                  PANEL_X + 130, inv_title_y + 2, FONT_XS, TEXT_DIM)

        inv_x0, inv_y0 = self._inv_origin()
        for gy in range(INV_ROWS):
            for gx in range(INV_COLS):
                x = inv_x0 + gx * CELL
                y = inv_y0 + gy * CELL
                pygame.draw.rect(surf, SLOT_BG, (x+1, y+1, CELL-2, CELL-2), border_radius=2)
        pygame.draw.rect(surf, ACCENT_DARK, (inv_x0, inv_y0, INV_COLS*CELL, INV_ROWS*CELL), 2, border_radius=4)

        drawn = set()
        for item in self.player.inventory.items:
            if id(item) in drawn: continue
            drawn.add(id(item))
            self._draw_item_in_grid(surf, item, inv_x0, inv_y0, item.rarity_color())

        draw_text(surf, f"Ouro: {self.player.gold}", PANEL_X + 20,
                  inv_y0 + INV_ROWS*CELL + 15, FONT_M, TEXT_GOLD)

    def _draw_item_in_grid(self, surf, item, ox, oy, color):
        x = ox + item.x * CELL
        y = oy + item.y * CELL
        w = item.size[0] * CELL
        h = item.size[1] * CELL

        pygame.draw.rect(surf, (50, 40, 30), (x+1, y+1, w-2, h-2), border_radius=3)
        pygame.draw.rect(surf, color, (x+1, y+1, w-2, h-2), 2, border_radius=3)

        ic = item.icon()
        f = icon_font_for_size(w, h)
        ri = f.render(ic, True, color)
        max_w = w - 8; max_h = h - 8
        if ri.get_width() > max_w or ri.get_height() > max_h:
            scale = min(max_w / ri.get_width(), max_h / ri.get_height())
            ri = pygame.transform.smoothscale(ri, (max(1,int(ri.get_width()*scale)),
                                                   max(1,int(ri.get_height()*scale))))
        if w >= CELL*2 and h >= CELL*2:
            name = item.display_name()
            max_txt_w = w - 8
            words = name.split()
            lines = []
            cur = ""
            for word in words:
                test = (cur + " " + word).strip()
                if FONT_XS.size(test)[0] <= max_txt_w:
                    cur = test
                else:
                    if cur: lines.append(cur)
                    cur = word
            if cur: lines.append(cur)
            for i, line in enumerate(lines[:2]):
                draw_text(surf, line, x+4, y+4 + i*12, FONT_XS, color)
            surf.blit(ri, (x + (w - ri.get_width())//2,
                           y + h - ri.get_height() - 4))
        else:
            surf.blit(ri, (x + (w - ri.get_width())//2, y + (h - ri.get_height())//2))

        # Contador de stack
        if item.stack_count > 1:
            draw_stack_badge(surf, x + w - 3, y + h - 3,
                             item.stack_count, FONT_S)

    def _draw_buttons(self, surf):
        rects = self._buttons_rects()
        labels = [
            ("GERAR ITEM (SPAÇO)", ACCENT),
            ("GERAR BAÚ (C)", (140, 100, 50)),
            ("GERAR CORPO (X)", (110, 90, 80)),
            ("ORGANIZAR (O)", (80, 140, 90)),
        ]
        mouse = pygame.mouse.get_pos()
        for (r, _), (label, col) in zip(rects, labels):
            hover = r.collidepoint(mouse)
            base = tuple(min(255, v+30) for v in col) if hover else col
            pygame.draw.rect(surf, base, r, border_radius=4)
            pygame.draw.rect(surf, (255,255,255,20), r, 1, border_radius=4)
            draw_text(surf, label, r.centerx, r.y + 7, FONT_S, (20, 15, 10), center=True)

    def _draw_log(self, surf):
        rect = pygame.Rect(LOG_X, LOG_Y, LOG_W, LOG_H)
        draw_panel(surf, rect)
        draw_text(surf, "REGISTRO", LOG_X + 10, LOG_Y + 48, FONT_L, ACCENT)
        y = LOG_Y + 72
        for text, color in self.log[-7:]:
            draw_text(surf, fit(text, FONT_S, LOG_W - 20), LOG_X + 10, y, FONT_S, color)
            y += 14

    def _draw_open_container(self, surf):
        if not self.open_container:
            self.open_container_close_rect = None
            return
        cont = self.open_container
        cols, rows = cont.w, cont.h
        w = cols * CELL + 20
        h = rows * CELL + 50
        x = MAP_X + (MAP_W - w) // 2
        y = MAP_Y + (MAP_H - h) // 2
        self.open_container_rect = pygame.Rect(x + 10, y + 40, cols*CELL, rows*CELL)

        bg_rect = pygame.Rect(x, y, w, h)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((0, 0, 0, 220))
        surf.blit(s, (x, y))
        draw_panel(surf, bg_rect, bg=PANEL_BG, border=ACCENT, radius=6, thickness=2)

        draw_text(surf, cont.name, x + 10, y + 10, FONT_L, ACCENT_BRIGHT)
        draw_text(surf, "Clique em item para pegar. Botão direito = pegar direto. ESC ou X fecha. O organiza.",
                  x + 10, y + 30, FONT_XS, TEXT_DIM)

        close_rect = pygame.Rect(x + w - 32, y + 8, 24, 24)
        self.open_container_close_rect = close_rect
        mouse = pygame.mouse.get_pos()
        hover = close_rect.collidepoint(mouse)
        col_bg = (180, 70, 70) if hover else (120, 50, 50)
        pygame.draw.rect(surf, col_bg, close_rect, border_radius=4)
        pygame.draw.rect(surf, (255, 220, 200), close_rect, 1, border_radius=4)
        pad = 6
        pygame.draw.line(surf, (255, 240, 230),
                         (close_rect.x + pad, close_rect.y + pad),
                         (close_rect.right - pad, close_rect.bottom - pad), 2)
        pygame.draw.line(surf, (255, 240, 230),
                         (close_rect.right - pad, close_rect.y + pad),
                         (close_rect.x + pad, close_rect.bottom - pad), 2)

        gx0, gy0 = self.open_container_rect.topleft
        for gy in range(rows):
            for gx in range(cols):
                xx = gx0 + gx * CELL
                yy = gy0 + gy * CELL
                pygame.draw.rect(surf, SLOT_BG, (xx+1, yy+1, CELL-2, CELL-2), border_radius=2)
        pygame.draw.rect(surf, ACCENT_DARK, (gx0, gy0, cols*CELL, rows*CELL), 2, border_radius=4)

        drawn = set()
        for item in cont.items:
            if id(item) in drawn: continue
            drawn.add(id(item))
            self._draw_item_in_grid(surf, item, gx0, gy0, item.rarity_color())

    # ------------------------------------------------------------------
    def _get_hovered_item(self):
        mouse = pygame.mouse.get_pos()
        inv_x0, inv_y0 = self._inv_origin()
        if self._inside(mouse, inv_x0, inv_y0, INV_COLS*CELL, INV_ROWS*CELL):
            gx = (mouse[0] - inv_x0) // CELL
            gy = (mouse[1] - inv_y0) // CELL
            return self.player.inventory.grid[gy][gx]
        if self.open_container and self.open_container_rect:
            cont = self.open_container
            x0, y0 = self.open_container_rect.topleft
            if self.open_container_rect.collidepoint(mouse):
                gx = (mouse[0] - x0) // CELL
                gy = (mouse[1] - y0) // CELL
                if 0 <= gx < cont.w and 0 <= gy < cont.h:
                    return cont.grid[gy][gx]
        eq_click = self._equip_slot_at(mouse)
        if eq_click and eq_click[1]:
            return eq_click[1]
        for rect, gi in self.ground_labels:
            if rect.collidepoint(mouse):
                return gi.item
        return None

    def _get_equipped_for(self, item):
        es = item.equip_slot()
        if not es: return None
        target = SLOT_MAP.get(es)
        if isinstance(target, list):
            for s in target:
                eq = self.player.equipment.get(s)
                if eq is not None: return eq
            return None
        return self.player.equipment.get(target)

    def _is_currently_equipped(self, item):
        return any(eq is item for eq in self.player.equipment.values())

    def _build_comparison_lines(self, new_item, old_item):
        lines = []
        title = f"vs. {old_item.display_name()}" if old_item else "Nada equipado"
        lines.append((title, ACCENT_BRIGHT if old_item else SUCCESS))

        new_dmg = new_item.get_damage()
        old_dmg = old_item.get_damage() if old_item else None
        if new_dmg or old_dmg:
            n_min, n_max = (new_dmg[0], new_dmg[1]) if new_dmg else (0, 0)
            o_min, o_max = (old_dmg[0], old_dmg[1]) if old_dmg else (0, 0)
            d_min = n_min - o_min
            d_max = n_max - o_max
            if d_min != 0 or d_max != 0:
                sign_min = "+" if d_min >= 0 else ""
                sign_max = "+" if d_max >= 0 else ""
                col_min = GAIN if d_min > 0 else (LOSS if d_min < 0 else TEXT_DIM)
                col_max = GAIN if d_max > 0 else (LOSS if d_max < 0 else TEXT_DIM)
                if col_min == col_max:
                    lines.append((f"Dano: {sign_min}{d_min} a {sign_max}{d_max}", col_min))
                else:
                    lines.append((f"Dano mín: {sign_min}{d_min}", col_min))
                    lines.append((f"Dano máx: {sign_max}{d_max}", col_max))

        n_ar = new_item.get_armor()
        o_ar = old_item.get_armor() if old_item else 0
        d_ar = n_ar - o_ar
        if d_ar != 0:
            sign = "+" if d_ar > 0 else ""
            col = GAIN if d_ar > 0 else LOSS
            lines.append((f"Armadura: {sign}{d_ar}", col))

        n_mods = new_item.get_stat_mods()
        o_mods = old_item.get_stat_mods() if old_item else {}
        all_stats = set(n_mods.keys()) | set(o_mods.keys())
        stat_deltas = []
        for k in all_stats:
            delta = n_mods.get(k, 0) - o_mods.get(k, 0)
            if delta != 0: stat_deltas.append((k, delta))
        if stat_deltas:
            lines.append(("", TEXT))
            stat_deltas.sort(key=lambda x: -x[1])
            for k, delta in stat_deltas:
                sign = "+" if delta > 0 else ""
                col = GAIN if delta > 0 else LOSS
                lines.append((f"{sign}{delta} {STAT_LABELS.get(k, k)}", col))

        n_res = new_item.get_resistances()
        o_res = old_item.get_resistances() if old_item else {}
        all_res = set(n_res.keys()) | set(o_res.keys())
        res_deltas = []
        for k in all_res:
            delta = n_res.get(k, 0) - o_res.get(k, 0)
            if delta != 0: res_deltas.append((k, delta))
        if res_deltas:
            lines.append(("", TEXT))
            res_deltas.sort(key=lambda x: -x[1])
            for k, delta in res_deltas:
                sign = "+" if delta > 0 else ""
                col = GAIN if delta > 0 else LOSS
                lines.append((f"{sign}{delta}% Res. {RES_LABELS.get(k, k)}", col))

        if len(lines) <= 1:
            lines.append(("Sem diferenças", TEXT_DIM))

        return lines

    def _draw_tooltip(self, surf):
        if self.cursor_item:
            self.hover_lines = None
            return
        target = self._get_hovered_item()
        if not target:
            self.hover_lines = None
            return

        mouse = pygame.mouse.get_pos()

        if self.ctrl_held and target.is_equipment() and not self._is_currently_equipped(target):
            old_item = self._get_equipped_for(target)
            base_lines = target.tooltip_lines()
            comp_lines = self._build_comparison_lines(target, old_item)
            self._draw_tooltip_pair(surf, base_lines, comp_lines, mouse,
                                    target.rarity_color())
            return

        self._draw_tooltip_for(surf, target, mouse)

    def _measure_lines_width(self, lines, max_cap=340, pad=10):
        mw = 0
        for t, _ in lines:
            w = FONT_S.size(t)[0]
            if w > mw: mw = w
        return min(mw + pad*2, max_cap)

    def _draw_tooltip_box_at(self, surf, lines, x, y, border_color, box_w):
        pad = 10
        line_h = 16
        box_h = len(lines) * line_h + pad*2
        r = pygame.Rect(x, y, box_w, box_h)

        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 235))
        surf.blit(bg, (x, y))
        pygame.draw.rect(surf, border_color, r, 2, border_radius=4)

        ty = y + pad
        for txt, color in lines:
            if txt == "":
                pygame.draw.line(surf, (90, 75, 55), (x+pad, ty+7), (x+box_w-pad, ty+7), 1)
            else:
                draw_text(surf, fit(txt, FONT_S, box_w - pad*2), x+pad, ty, FONT_S, color)
            ty += line_h
        return r

    def _draw_tooltip_for(self, surf, item, mouse_pos):
        lines = item.tooltip_lines()
        box_w = self._measure_lines_width(lines)
        pad = 10
        box_h = len(lines) * 16 + pad*2
        x, y = mouse_pos[0] + 20, mouse_pos[1] + 20
        if x + box_w > WIDTH: x = mouse_pos[0] - box_w - 20
        if y + box_h > HEIGHT: y = HEIGHT - box_h - 10
        if x < 10: x = 10
        if y < 10: y = 10
        self._draw_tooltip_box_at(surf, lines, x, y, item.rarity_color(), box_w)

    def _draw_tooltip_pair(self, surf, lines_a, lines_b, mouse_pos, color_a):
        gap = 6
        wa = self._measure_lines_width(lines_a)
        wb = self._measure_lines_width(lines_b)
        ha = len(lines_a) * 16 + 20
        hb = len(lines_b) * 16 + 20
        total_w = wa + gap + wb
        total_h = max(ha, hb)

        x_start = mouse_pos[0] + 20
        if x_start + total_w > WIDTH - 10:
            x_start = mouse_pos[0] - total_w - 20
        if x_start < 10:
            x_start = 10

        y_start = mouse_pos[1] + 20
        if y_start + total_h > HEIGHT - 10:
            y_start = HEIGHT - total_h - 10
        if y_start < 10:
            y_start = 10

        self._draw_tooltip_box_at(surf, lines_a, x_start, y_start, color_a, wa)
        self._draw_tooltip_box_at(surf, lines_b, x_start + wa + gap, y_start,
                                  ACCENT_BRIGHT, wb)

    def _draw_snap_highlight(self, surf):
        if not self.cursor_item or not self._snap: return
        s = self._snap
        if s["kind"] == "grid":
            rx, ry, rw, rh = s["x"], s["y"], s["w"], s["h"]
            col = PREVIEW_OK if s.get("preview") == "ok" else PREVIEW_SWAP
            overlay = pygame.Surface((rw-2, rh-2), pygame.SRCALPHA)
            overlay.fill((*col, 70))
            surf.blit(overlay, (rx+1, ry+1))
            pygame.draw.rect(surf, col, (rx+1, ry+1, rw-2, rh-2), 2,
                             border_radius=3)
            if s.get("preview") == "swap" and s.get("target"):
                t = s["target"]
                if t.container:
                    cont = t.container
                    if cont is self.player.inventory:
                        ox, oy = self._inv_origin()
                    elif cont is self.open_container and self.open_container_rect:
                        ox, oy = self.open_container_rect.topleft
                    else:
                        ox = oy = 0
                    tx = ox + t.x * CELL
                    ty = oy + t.y * CELL
                    tw = t.size[0] * CELL
                    th = t.size[1] * CELL
                    pygame.draw.rect(surf, PREVIEW_SWAP,
                                     (tx + 1, ty + 1, tw - 2, th - 2), 2)
        elif s["kind"] == "equip":
            rx, ry, rw, rh = s["x"], s["y"], s["w"], s["h"]
            overlay = pygame.Surface((rw, rh), pygame.SRCALPHA)
            overlay.fill((*PREVIEW_OK, 70))
            surf.blit(overlay, (rx, ry))
            pygame.draw.rect(surf, PREVIEW_OK, (rx, ry, rw, rh), 2, border_radius=4)

    def _draw_cursor_item(self, surf):
        if not self.cursor_item: return
        col = self.cursor_item.rarity_color()
        w = self.cursor_item.size[0] * CELL
        h = self.cursor_item.size[1] * CELL

        if self._snap and self._snap.get("kind") == "grid":
            x = self._snap["x"]
            y = self._snap["y"]
        elif self._snap and self._snap.get("kind") == "equip":
            cx = self._snap["x"] + self._snap["w"] // 2
            cy = self._snap["y"] + self._snap["h"] // 2
            x = cx - w // 2
            y = cy - h // 2
        else:
            mouse = pygame.mouse.get_pos()
            x = mouse[0] + self.drag_offset[0]
            y = mouse[1] + self.drag_offset[1]

        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((30, 22, 16, 200))
        surf.blit(s, (x, y))
        pygame.draw.rect(surf, col, (x, y, w, h), 2, border_radius=3)

        ic = self.cursor_item.icon()
        f = icon_font_for_size(w, h)
        ri = f.render(ic, True, col)
        max_w = w - 8; max_h = h - 8
        if ri.get_width() > max_w or ri.get_height() > max_h:
            scale = min(max_w / ri.get_width(), max_h / ri.get_height())
            ri = pygame.transform.smoothscale(ri, (max(1, int(ri.get_width()*scale)),
                                                   max(1, int(ri.get_height()*scale))))
        surf.blit(ri, (x + (w - ri.get_width())//2, y + (h - ri.get_height())//2))

        if self.cursor_item.stack_count > 1:
            draw_stack_badge(surf, x + w - 3, y + h - 3,
                             self.cursor_item.stack_count, FONT_S)

        hint = FONT_XS.render("R: girar", True, (230, 210, 180))
        surf.blit(hint, (x + w//2 - hint.get_width()//2, y + h + 4))

    def _draw_msg(self, surf):
        if not self.msg: return
        r = FONT_L.render(self.msg, True, self.msg_color)
        bg = pygame.Surface((r.get_width()+20, r.get_height()+10), pygame.SRCALPHA)
        bg.fill((0,0,0,180))
        x = MAP_X + MAP_W//2 - bg.get_width()//2
        y = MAP_Y + MAP_H - 40
        surf.blit(bg, (x, y))
        surf.blit(r, (x+10, y+5))


# ============================================================================
# App
# ============================================================================
class App:
    def __init__(self):
        self.running = True
        self.scene = MainScene(self)
    def run(self):
        while self.running:
            dt = clock.tick(60) / 1000.0
            events = pygame.event.get()
            self.scene.handle_events(events)
            self.scene.update(dt)
            self.scene.draw(screen, dt)
            pygame.display.flip()
        pygame.quit()


if __name__ == "__main__":
    App().run()