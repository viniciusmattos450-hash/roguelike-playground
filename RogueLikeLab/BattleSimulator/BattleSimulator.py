# -*- coding: utf-8 -*-
"""
BattleSimulator.py
Simulador de batalha roguelike em grid.
Lê ./exports/skills/*.json, ./exports/units/*.json, ./exports/items/*.json e
./exports/affixes/*.json gerados pelos editores.

Sem banco próprio: toda lógica vem dos JSON.
"""

import os, json, math, random, re, copy
from collections import Counter
import pygame

pygame.init()
WIDTH, HEIGHT = 1280, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Battle Simulator - Roguelike Arena")
clock = pygame.time.Clock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR  = os.path.join(BASE_DIR, "exports", "skills")
UNITS_DIR   = os.path.join(BASE_DIR, "exports", "units")
ITEMS_DIR   = os.path.join(BASE_DIR, "exports", "items")
AFFIXES_DIR = os.path.join(BASE_DIR, "exports", "affixes")

# ----------------------------------------------------------------------------
# Cores / Fontes
# ----------------------------------------------------------------------------
BG          = (20, 22, 28)
PANEL       = (35, 40, 52)
PANEL_LIGHT = (50, 58, 76)
TEXT        = (230, 235, 245)
TEXT_DIM    = (150, 158, 178)
ACCENT      = (86, 156, 255)
ACCENT_DARK = (45, 75, 120)
SUCCESS     = (72, 185, 125)
DANGER      = (205, 75, 75)
WARN        = (230, 175, 70)
BORDER      = (78, 88, 110)
GRID_BG     = (28, 32, 42)
GRID_LINE   = (45, 52, 68)
INPUT_BG    = (22, 25, 33)
INPUT_ACT   = (34, 46, 68)
OVERLAY     = (0, 0, 0, 200)

RARITY_COLORS = {
    "Comum":    (200, 200, 200),
    "Incomum":  (100, 220, 100),
    "Raro":     (100, 160, 255),
    "Épico":    (200, 130, 240),
    "Lendário": (240, 170, 60),
    "Mítico":   (255, 100, 100),
}

TEAM_COLORS = [(86,156,255),(230,90,90),(110,200,110),(230,190,90)]
TEAM_COLORS_DARK = [(40,70,120),(120,45,45),(55,100,55),(120,95,45)]
TEAM_NAMES = ["Time Azul","Time Vermelho","Time Verde","Time Amarelo"]

FONT_XL = pygame.font.SysFont("consolas,couriernew,monospace", 24, bold=True)
FONT_L  = pygame.font.SysFont("consolas,couriernew,monospace", 18, bold=True)
FONT_M  = pygame.font.SysFont("consolas,couriernew,monospace", 14)
FONT_S  = pygame.font.SysFont("consolas,couriernew,monospace", 12)
FONT_XS = pygame.font.SysFont("consolas,couriernew,monospace", 11)

GRID_COLS = 20; GRID_ROWS = 14; TILE = 40
GRID_X = 20; GRID_Y = 70
GRID_W = GRID_COLS * TILE; GRID_H = GRID_ROWS * TILE
LOG_X, LOG_Y = 840, 70; LOG_W, LOG_H = 420, 545

EQUIP_SLOTS_UI = ["Cabeça", "Peito", "Pernas", "Pés", "Mãos",
                  "Arma", "Mão Secundária", "Anel", "Amuleto", "Cinto", "Capa"]

# Comportamento dos efeitos
DOT_EFFECTS       = {"Queimadura","Veneno","Sangramento","Dano por Turno"}
REGEN_HP_EFFECTS  = {"Regeneração HP"}
REGEN_MP_EFFECTS  = {"Regeneração Mana"}
REGEN_ST_EFFECTS  = {"Regeneração Stamina"}
SKIP_TURN_EFFECTS = {"Atordoamento","Paralisia","Congelamento","Sono"}
IMMUNITY_EFFECTS  = {"Invencibilidade"}
SHIELD_EFFECTS    = {"Escudo"}
LIFESTEAL_EFFECTS = {"Roubo de Vida","Sanguessuga"}
INIT_UP_EFFECTS   = {"Aceleração","Bufo de Velocidade"}
INIT_DOWN_EFFECTS = {"Lentidão","Debuff de Velocidade"}
ATK_UP_EFFECTS    = {"Bufo de Ataque","Bênção"}
ATK_DOWN_EFFECTS  = {"Debuff de Ataque","Maldição"}
DEF_UP_EFFECTS    = {"Bufo de Defesa"}
DEF_DOWN_EFFECTS  = {"Debuff de Defesa"}
ACC_UP_EFFECTS    = {"Chance de Acerto +"}
EVA_UP_EFFECTS    = {"Chance de Esquiva +"}
CRIT_UP_EFFECTS   = {"Crítico +"}

RESISTANCE_KEYS = {"Fogo":"fire","Gelo":"ice","Elétrico":"lightning",
                   "Veneno":"poison","Sagrado":"holy","Sombrio":"dark"}
DMG_COLORS = {"Fogo":(240,130,60),"Gelo":(130,200,240),"Elétrico":(245,220,90),
              "Veneno":(130,210,100),"Ácido":(170,230,90),"Arcano":(200,140,245),
              "Sagrado":(250,230,160),"Sombrio":(160,120,220),
              "Terra":(190,140,90),"Vento":(200,230,220),"Água":(100,160,230)}

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def get_clipboard_text():
    try:
        import tkinter
        r = tkinter.Tk(); r.withdraw()
        try: t = r.clipboard_get()
        except Exception: t = ""
        r.destroy()
        if t: return t
    except Exception: pass
    try:
        pygame.scrap.init()
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        if raw: return raw.decode("utf-8","ignore").replace("\x00","")
    except Exception: pass
    return ""


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


def load_library():
    units = load_json_dir(UNITS_DIR)
    skills = load_json_dir(SKILLS_DIR)
    items = load_json_dir(ITEMS_DIR)
    affixes = load_json_dir(AFFIXES_DIR)
    return units, {s.get("name","?"): s for s in skills}, items, affixes


def draw_text(surf, text, x, y, font=FONT_M, color=TEXT, center_x=False):
    r = font.render(str(text), True, color)
    if center_x: surf.blit(r, (x - r.get_width()//2, y))
    else:        surf.blit(r, (x, y))
    return r


def draw_panel(surf, rect, color=PANEL, radius=8, border=True):
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, BORDER, rect, 1, border_radius=radius)


def fit(text, font, w):
    if font.size(text)[0] <= w: return text
    t = text
    while t and font.size("..." + t)[0] > w: t = t[1:]
    return "..." + t


# ----------------------------------------------------------------------------
# Equipment helpers
# ----------------------------------------------------------------------------
def default_equipped():
    """Retorna dict vazio {slot: {item_id, prefix_id, suffix_id}}."""
    return {slot: {"item_id": None, "prefix_id": None, "suffix_id": None}
            for slot in EQUIP_SLOTS_UI}


def get_item_full_name(slot_eq, items_by_id, affixes_by_id):
    """Retorna nome completo do item equipado neste slot, ou None."""
    if not slot_eq: return None
    item = items_by_id.get(slot_eq.get("item_id"))
    if not item: return None
    pre = affixes_by_id.get(slot_eq.get("prefix_id"))
    suf = affixes_by_id.get(slot_eq.get("suffix_id"))
    name = item.get("name", "?")
    if pre: name = pre.get("name", "") + " " + name
    if suf: name = name + " " + suf.get("name", "")
    return name


def compute_effective_stats(unit_data, equipped, items_by_id, affixes_by_id):
    """
    Retorna um dict com todos os stats somados (base + itens + afixos).
    Chaves: hp, stamina, mana, hp_regen, mana_regen, stamina_regen,
    attack_physical, attack_magical, defense_physical, defense_magical,
    speed, accuracy, evasion, crit_chance, crit_damage, lifesteal, initiative,
    strength, dexterity, intelligence, wisdom, vitality, luck,
    resistances (dict), bonus_dmg_min, bonus_dmg_max, bonus_dmg_type,
    special_effects (list of {type, value, duration, chance, trigger, source})
    """
    res = unit_data.get("resources", {})
    cb = unit_data.get("combat", {})
    at = unit_data.get("attributes", {})

    s = {
        "hp": res.get("hp", 10), "stamina": res.get("stamina", 0), "mana": res.get("mana", 0),
        "hp_regen": res.get("hp_regen", 0), "mana_regen": res.get("mana_regen", 0),
        "stamina_regen": res.get("stamina_regen", 0),
        "attack_physical": cb.get("attack_physical", 0),
        "attack_magical": cb.get("attack_magical", 0),
        "defense_physical": cb.get("defense_physical", 0),
        "defense_magical": cb.get("defense_magical", 0),
        "speed": cb.get("speed", 10), "initiative": cb.get("initiative", 10),
        "accuracy": cb.get("accuracy", 100), "evasion": cb.get("evasion", 0),
        "crit_chance": cb.get("crit_chance", 0), "crit_damage": cb.get("crit_damage", 150),
        "lifesteal": cb.get("lifesteal", 0),
        "strength": at.get("strength", 0), "dexterity": at.get("dexterity", 0),
        "intelligence": at.get("intelligence", 0), "wisdom": at.get("wisdom", 0),
        "vitality": at.get("vitality", 0), "luck": at.get("luck", 0),
        "resistances": dict(unit_data.get("resistances", {})),
        "bonus_dmg_min": 0, "bonus_dmg_max": 0, "bonus_dmg_type": "Nenhum",
        "special_effects": [],
    }

    # Aplica itens e afixos
    for slot, eq in (equipped or {}).items():
        item = items_by_id.get(eq.get("item_id"))
        if item:
            _apply_source_to_stats(s, item, source_kind="item")
        pre = affixes_by_id.get(eq.get("prefix_id"))
        if pre:
            _apply_source_to_stats(s, pre, source_kind="affix")
        suf = affixes_by_id.get(eq.get("suffix_id"))
        if suf:
            _apply_source_to_stats(s, suf, source_kind="affix")

    return s


def _apply_source_to_stats(s, source, source_kind):
    """Aplica modificadores de um item OU afixo ao dict de stats `s`."""
    # Stat modifiers (equipment.stat_modifiers) ou (affix.stat_modifiers)
    mods = source.get("stat_modifiers", {}) if source_kind == "affix" else \
           (source.get("equipment") or {}).get("stat_modifiers", {})
    for k, v in mods.items():
        if k in s:
            s[k] += v
        else:
            s[k] = v

    # Resistências
    if source_kind == "affix":
        res = source.get("resistances", {})
    else:
        res = (source.get("equipment") or {}).get("resistances", {})
    for k, v in res.items():
        s["resistances"][k] = s["resistances"].get(k, 0) + v

    # Damage bonus (do afixo)
    if source_kind == "affix":
        db = source.get("damage_bonus", {})
        if db.get("max", 0) > 0 or db.get("min", 0) > 0:
            s["bonus_dmg_min"] += db.get("min", 0)
            s["bonus_dmg_max"] += db.get("max", 0)
            s["bonus_dmg_type"] = db.get("type", "Nenhum")
    else:
        # Do item: dano base é somado como bonus de ataque
        eq = source.get("equipment") or {}
        dmg = eq.get("damage", {})
        if dmg.get("max", 0) > 0 or dmg.get("min", 0) > 0:
            s["bonus_dmg_min"] += dmg.get("min", 0)
            s["bonus_dmg_max"] += dmg.get("max", 0)
            s["bonus_dmg_type"] = dmg.get("type", "Nenhum")

    # Efeitos especiais
    if source_kind == "affix":
        fx = source.get("special_effects", [])
    else:
        fx = (source.get("equipment") or {}).get("special_effects", [])
    for e in fx:
        s["special_effects"].append(dict(e))


# ----------------------------------------------------------------------------
# Widgets
# ----------------------------------------------------------------------------
class TextInput:
    def __init__(self, x, y, w, h, placeholder="", text=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.placeholder = placeholder; self.text = text
        self.active = False; self._blink = 0.0; self._show_cursor = True
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos): self.active = True; return True
            else: self.active = False
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB): self.active = False
            elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL): self.text += get_clipboard_text()
            else:
                ch = event.unicode
                if ch and ch.isprintable(): self.text += ch
            return True
        return False
    def draw(self, surf, dt=0.0):
        bg = INPUT_ACT if self.active else INPUT_BG
        pygame.draw.rect(surf, bg, self.rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT if self.active else BORDER, self.rect, 1, border_radius=5)
        shown = self.text if self.text else self.placeholder
        col = TEXT if self.text else TEXT_DIM
        shown = fit(shown, FONT_S, self.rect.w - 16)
        r = FONT_S.render(shown, True, col)
        surf.blit(r, (self.rect.x + 8, self.rect.y + (self.rect.h - r.get_height())//2))
        if self.active:
            self._blink += dt
            if self._blink > 0.5:
                self._blink = 0.0; self._show_cursor = not self._show_cursor
            if self._show_cursor:
                full = fit(self.text, FONT_S, self.rect.w - 16)
                cx = self.rect.x + 8 + FONT_S.size(full)[0] + 2
                pygame.draw.line(surf, TEXT, (cx, self.rect.y+6), (cx, self.rect.y+self.rect.h-6), 2)


class Button:
    def __init__(self, x, y, w, h, text, cb, color=ACCENT, font=FONT_M):
        self.rect = pygame.Rect(x, y, w, h); self.text = text; self.cb = cb
        self.color = color; self.font = font; self.hover = False; self.enabled = True
    def handle_event(self, e):
        if e.type == pygame.MOUSEMOTION: self.hover = self.rect.collidepoint(e.pos)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.enabled and self.rect.collidepoint(e.pos): self.cb(); return True
        return False
    def draw(self, surf, dt=0):
        base = self.color if self.enabled else (70, 74, 86)
        c = tuple(min(255, v + 35) for v in base) if self.hover and self.enabled else base
        pygame.draw.rect(surf, c, self.rect, border_radius=6)
        pygame.draw.rect(surf, (255,255,255,25), self.rect, 1, border_radius=6)
        r = self.font.render(self.text, True, (255,255,255))
        surf.blit(r, (self.rect.centerx - r.get_width()//2, self.rect.centery - r.get_height()//2))


class Dropdown:
    MAX_VISIBLE = 10
    def __init__(self, x, y, w, h, options, index=0):
        self.rect = pygame.Rect(x, y, w, h)
        self.options = list(options) if options else [""]
        self.index = max(0, min(index, len(self.options)-1))
        self.open = False; self.scroll = 0
    @property
    def value(self): return self.options[self.index] if self.options else ""
    def list_geometry(self):
        item_h = self.rect.h
        visible = min(len(self.options), self.MAX_VISIBLE)
        h = visible * item_h
        y = self.rect.y + self.rect.h
        if y + h > HEIGHT - 10: y = max(10, self.rect.y - h)
        return y, h, item_h
    def list_rect(self):
        y, h, _ = self.list_geometry()
        return pygame.Rect(self.rect.x, y, self.rect.w, h)
    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.open:
            mx, my = pygame.mouse.get_pos()
            if self.list_rect().collidepoint(mx, my):
                visible = min(len(self.options), self.MAX_VISIBLE)
                max_scroll = max(0, len(self.options) - visible)
                self.scroll = max(0, min(max_scroll, self.scroll - event.y)); return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.open:
                lr = self.list_rect()
                if lr.collidepoint(event.pos):
                    _, _, item_h = self.list_geometry()
                    idx = self.scroll + (event.pos[1] - lr.y) // item_h
                    if 0 <= idx < len(self.options): self.index = idx
                    self.open = False; return True
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
                if self.open:
                    self.scroll = max(0, min(self.index, max(0, len(self.options) - self.MAX_VISIBLE)))
                return True
        return False
    def draw(self, surf, dt=0.0):
        pygame.draw.rect(surf, INPUT_BG, self.rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT if self.open else BORDER, self.rect, 1, border_radius=5)
        txt = fit(self.value, FONT_S, self.rect.w - 24)
        r = FONT_S.render(txt, True, TEXT)
        surf.blit(r, (self.rect.x + 6, self.rect.y + (self.rect.h - r.get_height())//2))
        ax, ay = self.rect.right - 12, self.rect.centery
        pygame.draw.polygon(surf, TEXT_DIM, [(ax-4, ay-2), (ax+4, ay-2), (ax, ay+3)])
    def draw_list(self, surf):
        y, h, item_h = self.list_geometry()
        lr = pygame.Rect(self.rect.x, y, self.rect.w, h)
        pygame.draw.rect(surf, (18, 21, 28), lr, border_radius=5)
        pygame.draw.rect(surf, ACCENT, lr, 1, border_radius=5)
        mx, my = pygame.mouse.get_pos()
        visible = min(len(self.options), self.MAX_VISIBLE)
        for i in range(visible):
            idx = self.scroll + i
            if idx >= len(self.options): break
            r = pygame.Rect(lr.x, lr.y + i*item_h, lr.w, item_h)
            if r.collidepoint(mx, my): pygame.draw.rect(surf, PANEL_LIGHT, r)
            if idx == self.index: pygame.draw.rect(surf, ACCENT_DARK, r)
            t = fit(self.options[idx], FONT_S, r.w - 16)
            tr = FONT_S.render(t, True, TEXT)
            surf.blit(tr, (r.x + 8, r.y + (r.h - tr.get_height())//2))


# ----------------------------------------------------------------------------
# Unit
# ----------------------------------------------------------------------------
class Unit:
    def __init__(self, data, team, x=0, y=0, tag="", equipped=None,
                 items_by_id=None, affixes_by_id=None):
        self.data = data
        self.name = data.get("name", "?")
        self.team = team; self.tag = tag; self.x, self.y = x, y

        items_by_id = items_by_id or {}
        affixes_by_id = affixes_by_id or {}

        s = compute_effective_stats(data, equipped, items_by_id, affixes_by_id)

        self.max_hp = max(1, s["hp"])
        self.hp = self.max_hp
        self.max_sta = s["stamina"]; self.sta = self.max_sta
        self.max_mana = s["mana"]; self.mana = self.max_mana
        self.hp_regen = s["hp_regen"]; self.sta_regen = s["stamina_regen"]
        self.mana_regen = s["mana_regen"]

        self.atk_phys = s["attack_physical"]; self.atk_mag = s["attack_magical"]
        self.def_phys = s["defense_physical"]; self.def_mag = s["defense_magical"]
        self.speed = s["speed"]; self.initiative = s["initiative"]
        self.accuracy = s["accuracy"]; self.evasion = s["evasion"]
        self.crit_chance = s["crit_chance"]; self.crit_dmg = s["crit_damage"]
        self.lifesteal = s["lifesteal"]
        self.resistances = s["resistances"]
        self.level = data.get("level", 1)
        self.race = data.get("race", "")
        self.klass = data.get("class", "")

        # Bônus de dano das armas
        self.bonus_dmg_min = s["bonus_dmg_min"]
        self.bonus_dmg_max = s["bonus_dmg_max"]
        self.bonus_dmg_type = s["bonus_dmg_type"]

        # Efeitos especiais do equipamento (a serem disparados por trigger)
        self.equipment_effects = s["special_effects"]

        # Lista de nomes de itens equipados (para display)
        self.equipped_display = []
        for slot in EQUIP_SLOTS_UI:
            nm = get_item_full_name((equipped or {}).get(slot), items_by_id, affixes_by_id)
            if nm: self.equipped_display.append((slot, nm))

        self.skill_names = list(data.get("skills", []))
        self.alive = True
        self.effects = []
        self.cooldowns = {}
        self.shield = 0
        self.skip_next = False
        self.is_summon = False
        self.summon_expiry_round = 0
        self.summoner = None

    def display(self):
        return self.name + (f" {self.tag}" if self.tag else "")

    def has_effect(self, etype):
        return any(e["type"] == etype for e in self.effects)

    def effect_value(self, etype):
        return sum(e["value"] for e in self.effects if e["type"] == etype)

    def sum_effects(self, types):
        return sum(e["value"] for e in self.effects if e["type"] in types)


# ----------------------------------------------------------------------------
# Battle
# ----------------------------------------------------------------------------
class Battle:
    def __init__(self, teams, skills_by_name, items_by_id=None, affixes_by_id=None,
                 team_equipment=None):
        """
        teams: lista de listas de dicts (unit_data)
        team_equipment: {(ti, ui): {slot: {item_id, prefix_id, suffix_id}}}
        """
        self.skills_by_name = skills_by_name
        self.items_by_id = items_by_id or {}
        self.affixes_by_id = affixes_by_id or {}
        self.units_library = {u.get("name"): u for u in load_json_dir(UNITS_DIR)}
        self.team_equipment = team_equipment or {}

        self.units = []
        self.log = []
        self.round = 1; self.turn_index = 0
        self.finished = False; self.winner_team = None
        self._in_reaction = False

        # Cria unidades e aplica equipamento
        for ti, roster in enumerate(teams):
            name_counts = Counter(u.get("name", "?") for u in roster)
            pos_in_name = {}
            for ui, udata in enumerate(roster):
                nm = udata.get("name", "?")
                tag = ""
                if name_counts[nm] > 1:
                    idx_in = pos_in_name.get(nm, 0)
                    tag = chr(ord('A') + idx_in)
                    pos_in_name[nm] = idx_in + 1
                equipped = self.team_equipment.get((ti, ui), default_equipped())
                self.units.append(Unit(udata, ti, tag=tag, equipped=equipped,
                                       items_by_id=self.items_by_id,
                                       affixes_by_id=self.affixes_by_id))

        positions = self._spawn_positions(teams)
        unit_idx = 0
        for ti, roster in enumerate(teams):
            for ui in range(len(roster)):
                px, py = positions[(ti, ui)]
                self.units[unit_idx].x = px
                self.units[unit_idx].y = py
                unit_idx += 1

        for u in self.units:
            self._apply_passives(u)
            # Efeitos "Ao equipar" uma vez no início
            self._fire_equipment_effects(u, trigger="Ao equipar", attacker=u, target=u)

        self._rebuild_turn_order()
        self.add_log("=== INÍCIO DA BATALHA ===", ACCENT)

    # --- Spatial ---
    def _spawn_positions(self, teams):
        positions = {}
        n = len(teams); cols, rows = GRID_COLS, GRID_ROWS
        if n == 2:
            for ti in range(2):
                col = 1 if ti == 0 else cols - 2
                for ui in range(len(teams[ti])):
                    positions[(ti, ui)] = (col, max(1, min(rows-2, 3+ui)))
        elif n == 3:
            for ui in range(len(teams[0])):
                positions[(0, ui)] = (1, max(1, min(rows-2, 3+ui)))
            for ui in range(len(teams[1])):
                positions[(1, ui)] = (cols-2, max(1, min(rows-2, 3+ui)))
            for ui in range(len(teams[2])):
                positions[(2, ui)] = (max(1, min(cols-2, 7+ui)), rows-2)
        else:
            corners = [(2,2),(cols-3,2),(2,rows-3),(cols-3,rows-3)]
            for ti in range(4):
                cx, cy = corners[ti]
                for ui in range(len(teams[ti])):
                    dx = (ui % 2); dy = (ui // 2)
                    px = cx + (dx if ti in (0,2) else -dx)
                    py = cy + (dy if ti in (0,1) else -dy)
                    positions[(ti, ui)] = (max(0,min(cols-1,px)), max(0,min(rows-1,py)))
        return positions

    def _occupied(self, x, y, exclude=None):
        for u in self.alive_units():
            if u is exclude: continue
            if u.x == x and u.y == y: return u
        return None

    def _free_adjacent(self, unit, max_count):
        tiles = []
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                if dx == 0 and dy == 0: continue
                nx, ny = unit.x+dx, unit.y+dy
                if 0 <= nx < GRID_COLS and 0 <= ny < GRID_ROWS:
                    if self._occupied(nx, ny) is None: tiles.append((nx, ny))
        return tiles[:max_count]

    # --- Turn order ---
    def _effective_initiative(self, u):
        return u.initiative + u.sum_effects(INIT_UP_EFFECTS) - u.sum_effects(INIT_DOWN_EFFECTS)

    def _rebuild_turn_order(self):
        self.turn_order = sorted([u for u in self.units if u.alive],
                                 key=lambda u: -self._effective_initiative(u))
        self.turn_index = 0

    def current(self):
        while self.turn_index < len(self.turn_order):
            u = self.turn_order[self.turn_index]
            if u.alive: return u
            self.turn_index += 1
        return None

    def add_log(self, text, color=TEXT):
        self.log.append((text, color))
        if len(self.log) > 500: self.log = self.log[-500:]

    def alive_units(self): return [u for u in self.units if u.alive]
    def teams_alive(self): return set(u.team for u in self.alive_units())

    def _nearest_enemy(self, u):
        enemies = [e for e in self.alive_units() if e.team != u.team]
        if not enemies: return None
        return min(enemies, key=lambda e: abs(u.x-e.x)+abs(u.y-e.y))

    # --- Condition parser ---
    def _check_condition(self, unit, cond):
        cond = (cond or "").strip().lower().replace(" ","")
        if not cond: return True
        m = re.match(r"hp([<>=!]+)(\d+)%?", cond)
        if m:
            op, val = m.group(1), int(m.group(2))
            pct = unit.hp / max(1, unit.max_hp) * 100
            if op == "<": return pct < val
            if op == "<=": return pct <= val
            if op == ">": return pct > val
            if op == ">=": return pct >= val
        m = re.match(r"mp([<>=!]+)(\d+)%?", cond)
        if m:
            op, val = m.group(1), int(m.group(2))
            pct = unit.mana / max(1, unit.max_mana) * 100
            if op == "<": return pct < val
            if op == "<=": return pct <= val
            if op == ">": return pct > val
            if op == ">=": return pct >= val
        return True

    # --- Passivas ---
    def _apply_passives(self, u):
        for name in u.skill_names:
            s = self.skills_by_name.get(name)
            if not s or s.get("type") != "Passiva": continue
            for e in s.get("effects", []):
                u.effects.append({
                    "type": e.get("type","Outro"),
                    "value": e.get("value",0),
                    "duration": 99999,
                    "source": u,
                })
            self.add_log(f"{u.display()} tem passiva '{name}' ativa.", SUCCESS)

    # --- Reactions (skills com type=Reação) ---
    def _check_reactions(self, trigger_name, unit, event_data=None):
        if self._in_reaction or not unit.alive: return
        for name in unit.skill_names:
            s = self.skills_by_name.get(name)
            if not s or s.get("type") != "Reação": continue
            if s.get("trigger") != trigger_name: continue
            if unit.cooldowns.get(name, 0) > 0: continue
            cost = s.get("cost", {})
            if cost.get("mana",0) > unit.mana: continue
            if cost.get("stamina",0) > unit.sta: continue

            self._in_reaction = True
            try:
                self.add_log(f"REAÇÃO: {unit.display()} usa {name}!", SUCCESS)
                unit.mana -= cost.get("mana",0); unit.sta -= cost.get("stamina",0)
                cd = s.get("cooldown",0)
                if cd > 0: unit.cooldowns[name] = cd
                target = None
                if event_data and "attacker" in event_data:
                    target = event_data["attacker"]
                if target is None or not target.alive:
                    target = self._nearest_enemy(unit)
                if target: self._apply_skill_to(unit, target, s)
            finally:
                self._in_reaction = False
            return

    # --- Equipment effects (armas/armaduras com efeitos por trigger) ---
    def _fire_equipment_effects(self, unit, trigger, attacker=None, target=None):
        """Dispara efeitos de equipamento baseados no trigger."""
        if not unit.alive: return
        for fx in unit.equipment_effects:
            if fx.get("trigger", "") != trigger: continue
            chance = fx.get("chance", 100)
            if random.random() * 100 > chance: continue
            etype = fx.get("type", "Outro")
            val = fx.get("value", 0)
            dur = fx.get("duration", 0)

            # Efeitos instantâneos
            if etype in REGEN_HP_EFFECTS and dur <= 0:
                unit.hp = min(unit.max_hp, unit.hp + val)
                self.add_log(f"  {unit.display()} cura {val} HP (item).", SUCCESS)
                continue
            if etype in REGEN_MP_EFFECTS and dur <= 0:
                unit.mana = min(unit.max_mana, unit.mana + val)
                self.add_log(f"  {unit.display()} recupera {val} mana (item).", SUCCESS)
                continue
            if etype in LIFESTEAL_EFFECTS:
                unit.lifesteal += val
                continue

            # Efeitos que aplicam no alvo (armas)
            tgt = target if (trigger in ("Ao acertar","Em crítico") and target) else unit
            if trigger in ("Ao ser acertado", "Ao morrer", "Quando HP < 50%", "Quando HP < 25%"):
                tgt = unit  # autobuff/self
            if not tgt: continue

            # Aplica efeito persistente
            ed = {
                "type": etype,
                "value": val,
                "duration": max(1, dur),
                "source": unit,
            }
            tgt.effects.append(ed)
            self.add_log(f"  ITEM: {tgt.display()} sofre {etype} ({max(1,dur)}t).", WARN)
            if etype in SKIP_TURN_EFFECTS:
                tgt.skip_next = True

    # --- Main loop ---
    def advance(self):
        if self.finished: return
        cur = self.current()
        if cur is None:
            self.round += 1
            for u in list(self.alive_units()):
                if u.is_summon and u.summon_expiry_round and self.round >= u.summon_expiry_round:
                    self.add_log(f"{u.display()} desaparece (fim da invocação).", TEXT_DIM)
                    self._kill(u, fire_reaction=False)
            self._rebuild_turn_order()
            cur = self.current()
            if cur is None: self.finished = True; return
            self.add_log(f"=== RODADA {self.round} ===", ACCENT)

        if cur.alive:
            self._check_reactions("Ao iniciar turno", cur)
            hp_pct = cur.hp / max(1, cur.max_hp)
            if hp_pct < 0.25: self._check_reactions("Quando HP < 25%", cur)
            elif hp_pct < 0.50: self._check_reactions("Quando HP < 50%", cur)

        self._start_of_turn(cur)
        if not cur.alive: self.turn_index += 1; return

        if cur.has_effect("Silêncio"):
            self.add_log(f"{cur.display()} está silenciado e perde o turno.", WARN)
            self.turn_index += 1; return
        if cur.skip_next:
            cur.skip_next = False
            self.add_log(f"{cur.display()} está impedido e perde o turno.", WARN)
            self.turn_index += 1; return
        if cur.has_effect("Medo") and random.random() < 0.30:
            self.add_log(f"{cur.display()} está apavorado e hesita.", WARN)
            self.turn_index += 1; return

        self._take_action(cur)

        if len(self.teams_alive()) <= 1:
            self.finished = True
            alive = self.teams_alive()
            self.winner_team = next(iter(alive)) if alive else None
            if self.winner_team is not None:
                self.add_log(f"*** {TEAM_NAMES[self.winner_team]} VENCEU! ***", SUCCESS)
            else:
                self.add_log("*** EMPATE ***", WARN)
            return
        self.turn_index += 1

    def _start_of_turn(self, u):
        for e in list(u.effects):
            et = e["type"]
            if et in DOT_EFFECTS:
                dmg = e["value"]; u.hp -= dmg
                self.add_log(f"{u.display()} sofre {dmg} de {et}.", DANGER)
                if u.hp <= 0: self._kill(u); return
            elif et in REGEN_HP_EFFECTS:
                heal = e["value"]; u.hp = min(u.max_hp, u.hp + heal)
                self.add_log(f"{u.display()} regenera {heal} HP.", SUCCESS)
            elif et in REGEN_MP_EFFECTS:
                u.mana = min(u.max_mana, u.mana + e["value"])
            elif et in REGEN_ST_EFFECTS:
                u.sta = min(u.max_sta, u.sta + e["value"])

        for e in list(u.effects):
            e["duration"] -= 1
            if e["duration"] <= 0: u.effects.remove(e)
        for k in list(u.cooldowns.keys()):
            u.cooldowns[k] -= 1
            if u.cooldowns[k] <= 0: del u.cooldowns[k]

        if u.hp_regen:   u.hp   = min(u.max_hp, u.hp + u.hp_regen)
        if u.sta_regen:  u.sta  = min(u.max_sta, u.sta + u.sta_regen)
        if u.mana_regen: u.mana = min(u.max_mana, u.mana + u.mana_regen)

    def _kill(self, u, fire_reaction=True):
        if not u.alive: return
        u.alive = False; u.hp = 0
        self.add_log(f"{u.display()} morreu.", (200, 100, 100))
        if fire_reaction:
            self._check_reactions("Ao morrer", u)
            # Efeitos "Ao matar" são disparados pelo assassino; aqui só "Ao morrer" da vítima

    def _take_action(self, u):
        enemies = [e for e in self.alive_units() if e.team != u.team]
        if not enemies: return

        if u.has_effect("Confusão") and random.random() < 0.5:
            allies = [a for a in self.alive_units() if a.team == u.team and a is not u]
            if allies:
                self.add_log(f"{u.display()} está confuso e pode atacar aliados!", WARN)
                enemies = allies

        provokes = [e for e in u.effects if e["type"] in ("Provocar",) and e.get("source")]
        provokes = [e for e in provokes if e["source"] and e["source"].alive]
        if provokes:
            forced = provokes[0]["source"]
            enemies = [forced]
            self.add_log(f"{u.display()} é forçado a atacar {forced.display()}!", WARN)

        target = min(enemies, key=lambda e: abs(u.x-e.x)+abs(u.y-e.y))

        usable = []
        for name in u.skill_names:
            s = self.skills_by_name.get(name)
            if not s or s.get("type") == "Passiva": continue
            if u.cooldowns.get(name, 0) > 0: continue
            req = s.get("requirements", {})
            if req.get("level",1) > u.level: continue
            rc = req.get("class","")
            rr = req.get("race","")
            if rc and u.klass and rc.lower() != u.klass.lower(): continue
            if rr and u.race and rr.lower() != u.race.lower(): continue
            cost = s.get("cost", {})
            if cost.get("mana",0) > u.mana: continue
            if cost.get("stamina",0) > u.sta: continue
            usable.append((name, s))

        def priority(p):
            name, s = p
            t = s.get("type",""); dmg = s.get("damage",{})
            dmax = dmg.get("max",0)
            if "Ataque" in t or dmg.get("min",0) > 0: return (0, -dmax)
            if t == "Cura": return (1, 0)
            if t == "Invocação": return (2, 0)
            if t == "Buff": return (3, 0)
            if t == "Ultimate": return (0, -dmax - 1000)
            if t == "Debuff": return (4, 0)
            return (5, 0)
        usable.sort(key=priority)

        for name, s in usable:
            rng = s.get("range",1) or 1
            tgt_type = s.get("target","Inimigo Único")
            if tgt_type == "Si Mesmo": primary = u
            elif tgt_type in ("Aliado Único","Todos os Aliados"): primary = u
            else: primary = target
            dist = abs(u.x - primary.x) + abs(u.y - primary.y)
            if dist > rng: continue
            self._use_skill(u, primary, name, s)
            return

        self._move_toward(u, target)

    def _move_toward(self, u, target):
        options = []
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx, ny = u.x+dx, u.y+dy
            if 0 <= nx < GRID_COLS and 0 <= ny < GRID_ROWS:
                if self._occupied(nx, ny, exclude=u) is None:
                    options.append((abs(nx-target.x)+abs(ny-target.y), nx, ny))
        if not options:
            self.add_log(f"{u.display()} não consegue se mover.", TEXT_DIM); return
        options.sort()
        _, nx, ny = options[0]
        u.x, u.y = nx, ny
        self.add_log(f"{u.display()} move-se para ({nx},{ny}).", TEXT_DIM)

    def _use_skill(self, attacker, primary, name, s):
        if s.get("type") == "Invocação":
            cost = s.get("cost", {})
            attacker.mana -= cost.get("mana",0)
            attacker.sta -= cost.get("stamina",0)
            cd = s.get("cooldown",0)
            if cd > 0: attacker.cooldowns[name] = cd
            self.add_log(f"{attacker.display()} usa {name}.", ACCENT)
            self._summon(attacker, s); return

        cost = s.get("cost", {})
        attacker.mana -= cost.get("mana",0)
        attacker.sta -= cost.get("stamina",0)
        cd = s.get("cooldown",0)
        if cd > 0: attacker.cooldowns[name] = cd

        tt = s.get("target","Inimigo Único")
        if tt in ("Inimigo Único","Inimigo Aleatório"): targets = [primary]
        elif tt == "Todos os Inimigos":
            targets = [e for e in self.alive_units() if e.team != attacker.team]
        elif tt in ("Área","Linha","Cone"):
            targets = [e for e in self.alive_units()
                       if e.team != attacker.team
                       and abs(e.x-primary.x)+abs(e.y-primary.y) <= 1]
            if not targets: targets = [primary]
        elif tt == "Todos os Aliados":
            targets = [a for a in self.alive_units() if a.team == attacker.team]
        elif tt == "Aliado Único": targets = [primary]
        else: targets = [attacker]

        self.add_log(f"{attacker.display()} usa {name}.", ACCENT)
        for tgt in targets:
            if not tgt.alive: continue
            self._apply_skill_to(attacker, tgt, s)

        self._check_reactions("Ao usar skill", attacker)

    def _summon(self, summoner, s):
        spec = s.get("summon") or {}
        unit_name = (spec.get("unit_name") or "").strip()
        count = max(1, int(spec.get("count",1) or 1))
        duration = max(0, int(spec.get("duration",0) or 0))
        if not unit_name:
            self.add_log(f"  {summoner.display()} tenta invocar, mas nada foi definido.", WARN); return
        data = self.units_library.get(unit_name)
        if not data:
            self.add_log(f"  '{unit_name}' não existe.", DANGER); return
        free = self._free_adjacent(summoner, count)
        if not free:
            self.add_log(f"  {summoner.display()} não tem espaço livre!", WARN); return

        for i, (tx, ty) in enumerate(free):
            tag = "I" + (chr(ord('A')+i) if count > 1 else "")
            nu = Unit(data, summoner.team, tx, ty, tag=tag,
                      equipped=default_equipped(),
                      items_by_id=self.items_by_id, affixes_by_id=self.affixes_by_id)
            nu.is_summon = True; nu.summoner = summoner
            if duration > 0: nu.summon_expiry_round = self.round + duration
            self.units.append(nu); self.turn_order.append(nu)
            self.add_log(f"  → {nu.display()} é invocado!", SUCCESS)
            self._apply_passives(nu)

    def _apply_skill_to(self, attacker, tgt, s):
        if not tgt.alive: return
        dmg = s.get("damage", {})
        dmin, dmax = dmg.get("min",0), dmg.get("max",0)
        dtype = dmg.get("type", "Nenhum")

        # Aplica bônus de arma (do equipamento)
        # Se o tipo de dano do ataque bate com o tipo de dano da arma, soma.
        if attacker.bonus_dmg_max > 0:
            if dtype in (attacker.bonus_dmg_type, "Físico", "Nenhum"):
                dmin += attacker.bonus_dmg_min
                dmax += attacker.bonus_dmg_max

        if dmax > 0 or dmin > 0:
            if tgt.has_effect("Invencibilidade"):
                self.add_log(f"  {tgt.display()} está imune a dano!", WARN)
            else:
                hits = max(1, dmg.get("hits", 1))
                total = 0
                for _ in range(hits):
                    if not tgt.alive: break
                    acc = dmg.get("accuracy", 100)
                    if attacker.has_effect("Cegueira"): acc *= 0.5
                    acc += attacker.sum_effects(ACC_UP_EFFECTS)
                    if random.random()*100 > acc:
                        self.add_log(f"  {tgt.display()} esquivou do golpe!", TEXT_DIM)
                        continue
                    eva = tgt.evasion + tgt.sum_effects(EVA_UP_EFFECTS)
                    if random.random()*100 < eva:
                        self.add_log(f"  {tgt.display()} evadiu!", TEXT_DIM)
                        continue

                    base = random.randint(min(dmin, dmax), max(dmin, dmax))
                    phys = dtype in ("Físico", "Nenhum")
                    atk = attacker.atk_phys if phys else attacker.atk_mag
                    dfn = tgt.def_phys if phys else tgt.def_mag

                    atk_mod = 1.0 + attacker.sum_effects(ATK_UP_EFFECTS)/100.0 \
                                  - attacker.sum_effects(ATK_DOWN_EFFECTS)/100.0
                    def_mod = 1.0 + tgt.sum_effects(DEF_UP_EFFECTS)/100.0 \
                                  - tgt.sum_effects(DEF_DOWN_EFFECTS)/100.0
                    atk *= max(0.1, atk_mod); dfn *= max(0.1, def_mod)

                    raw = max(1.0, base + atk*0.5 - dfn*0.4)

                    # Resistência elemental
                    res_key = RESISTANCE_KEYS.get(dtype)
                    if res_key:
                        res = tgt.resistances.get(res_key, 0)
                        raw *= (1.0 - res/100.0)
                        raw = max(0.0, raw)

                    crit_total = attacker.crit_chance + attacker.sum_effects(CRIT_UP_EFFECTS)
                    is_crit = False
                    if random.random()*100 < crit_total:
                        raw *= attacker.crit_dmg/100.0
                        is_crit = True
                        self.add_log(f"  CRÍTICO em {tgt.display()}!", WARN)

                    dmg_int = int(round(raw))
                    if tgt.shield > 0 and dmg_int > 0:
                        absorbed = min(tgt.shield, dmg_int)
                        tgt.shield -= absorbed; dmg_int -= absorbed
                        if absorbed > 0:
                            self.add_log(f"  {tgt.display()} absorve {absorbed} com escudo.", TEXT_DIM)

                    if dmg_int > 0:
                        tgt.hp -= dmg_int; total += dmg_int
                        self.add_log(f"  {tgt.display()} recebe {dmg_int} de dano {dtype}.",
                                     DMG_COLORS.get(dtype, TEXT))

                    if tgt.hp <= 0:
                        self._kill(tgt)
                        # Efeitos "Ao matar" do atacante
                        self._fire_equipment_effects(attacker, "Ao matar", attacker, tgt)
                        self._check_reactions("Ao matar", attacker, {"target": tgt})
                        break

                    # Efeitos "Ao acertar" do atacante
                    self._fire_equipment_effects(attacker, "Ao acertar", attacker, tgt)
                    self._check_reactions("Ao acertar ataque", attacker, {"target": tgt})
                    if is_crit:
                        self._fire_equipment_effects(attacker, "Em crítico", attacker, tgt)

                # Lifesteal
                ls = attacker.lifesteal
                if ls and total > 0:
                    heal = int(total * ls / 100)
                    if heal > 0:
                        attacker.hp = min(attacker.max_hp, attacker.hp + heal)
                        self.add_log(f"  {attacker.display()} rouba {heal} HP.", SUCCESS)

                # Reflexo
                if tgt.alive and tgt.has_effect("Reflexo") and total > 0:
                    refl = tgt.effect_value("Reflexo")
                    refl_dmg = int(total * refl / 100)
                    if refl_dmg > 0:
                        attacker.hp -= refl_dmg
                        self.add_log(f"  {tgt.display()} reflete {refl_dmg} em {attacker.display()}!", WARN)
                        if attacker.hp <= 0: self._kill(attacker)

                # "Ao ser acertado" no alvo
                if tgt.alive:
                    self._fire_equipment_effects(tgt, "Ao ser acertado", tgt, attacker)
                    self._check_reactions("Ao ser atacado", tgt, {"attacker": attacker})

        # Effects da skill
        for e in s.get("effects", []):
            if not tgt.alive: break
            cond = e.get("condition", "")
            if cond and not self._check_condition(tgt, cond): continue
            if random.random()*100 > e.get("chance", 100): continue

            etype = e.get("type", "Outro")
            val = e.get("value", 0); dur = e.get("duration", 0)

            if etype in LIFESTEAL_EFFECTS:
                if dur > 0:
                    attacker.effects.append({"type":"Sanguessuga","value":val,
                                             "duration":dur,"source":attacker})
                attacker.lifesteal += val
                self.add_log(f"  {attacker.display()} ganha {val}% roubo de vida.", SUCCESS)
                continue
            if etype in SHIELD_EFFECTS:
                tgt.shield += val
                self.add_log(f"  {tgt.display()} ganha escudo {val}.", SUCCESS); continue
            if etype in REGEN_HP_EFFECTS and dur <= 0:
                tgt.hp = min(tgt.max_hp, tgt.hp + val)
                self.add_log(f"  {tgt.display()} cura {val} HP.", SUCCESS); continue
            if etype in REGEN_MP_EFFECTS and dur <= 0:
                tgt.mana = min(tgt.max_mana, tgt.mana + val)
                self.add_log(f"  {tgt.display()} recupera {val} mana.", SUCCESS); continue
            if etype in REGEN_ST_EFFECTS and dur <= 0:
                tgt.sta = min(tgt.max_sta, tgt.sta + val)
                self.add_log(f"  {tgt.display()} recupera {val} stamina.", SUCCESS); continue

            ed = {"type": etype, "value": val, "duration": max(1,dur), "source": attacker}
            tgt.effects.append(ed)
            self.add_log(f"  {tgt.display()} sofre {etype} ({max(1,dur)}t).", WARN)
            if etype in SKIP_TURN_EFFECTS: tgt.skip_next = True


# ----------------------------------------------------------------------------
# Scenes
# ----------------------------------------------------------------------------
class Scene:
    def __init__(self, app):
        self.app = app
        self.all_widgets = []; self.all_inputs = []; self.all_dropdowns = []
    def handle_events(self, events):
        for e in events:
            if e.type == pygame.QUIT: self.app.running = False; return
        any_active = any(i.active for i in self.all_inputs)
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                if any_active:
                    for i in self.all_inputs: i.active = False
                    for d in self.all_dropdowns: d.open = False
                    return
                self.app.change_scene(MenuScene(self.app)); return
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                in_list = any(d.open and d.list_rect().collidepoint(e.pos) for d in self.all_dropdowns)
                if in_list:
                    for d in self.all_dropdowns:
                        if d.handle_event(e): break
                    continue
                for d in self.all_dropdowns:
                    if not d.rect.collidepoint(e.pos): d.open = False
            for w in self.all_widgets: w.handle_event(e)
    def update(self, dt): pass
    def draw(self, surf, dt): pass


class MenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.buttons = [
            Button(WIDTH//2 - 200, 300, 400, 60, "INICIAR SIMULAÇÃO",
                   lambda: app.change_scene(TeamBuilderScene(app)), ACCENT),
            Button(WIDTH//2 - 200, 380, 400, 60, "SAIR",
                   lambda: setattr(app, "running", False), DANGER),
        ]
        self.all_widgets = list(self.buttons)
    def draw(self, surf, dt):
        surf.fill(BG)
        for i in range(0, WIDTH, 60):
            pygame.draw.line(surf, (30,34,44), (i,0), (i,HEIGHT))
        for j in range(0, HEIGHT, 60):
            pygame.draw.line(surf, (30,34,44), (0,j), (WIDTH,j))
        draw_text(surf, "BATTLE SIMULATOR", WIDTH//2, 130, FONT_XL, TEXT, center_x=True)
        draw_text(surf, "Arena roguelike para testar skills, itens e criaturas",
                  WIDTH//2, 180, FONT_L, TEXT_DIM, center_x=True)
        draw_text(surf, f"Skills: {SKILLS_DIR}", WIDTH//2, 220, FONT_S, ACCENT, center_x=True)
        draw_text(surf, f"Units:  {UNITS_DIR}", WIDTH//2, 238, FONT_S, ACCENT, center_x=True)
        draw_text(surf, f"Itens:  {ITEMS_DIR}", WIDTH//2, 256, FONT_S, ACCENT, center_x=True)
        draw_text(surf, f"Afixos: {AFFIXES_DIR}", WIDTH//2, 274, FONT_S, ACCENT, center_x=True)
        for w in self.all_widgets: w.draw(surf, dt)


# ----------------------------------------------------------------------------
# Equipment Modal (dentro do TeamBuilder)
# ----------------------------------------------------------------------------
class EquipmentModal:
    """Modal de equipamento de UMA unidade do time."""
    def __init__(self, unit_data, equipment, items_lib, affixes_lib, on_close):
        self.unit_data = unit_data
        self.equipment = equipment  # dict slot -> {item_id, prefix_id, suffix_id}
        self.items_lib = items_lib
        self.affixes_lib = affixes_lib
        self.on_close = on_close

        self.items_by_id = {it.get("id",""): it for it in items_lib}
        self.affixes_by_id = {af.get("id",""): af for af in affixes_lib}

        # Para cada slot: lista de itens disponíveis
        self.slot_items = {}
        for slot in EQUIP_SLOTS_UI:
            opts = [it for it in items_lib
                    if (it.get("equipment") or {}).get("slot") == slot]
            self.slot_items[slot] = opts

        # Dropdowns
        self.slot_widgets = {}  # slot -> {"item_dd", "prefix_dd", "suffix_dd", "clear_btn"}
        self._build_widgets()

        self.close_btn = Button(970, 82, 100, 34, "FECHAR", self.close, (90, 90, 110))
        self.all_widgets = [self.close_btn]
        for d in self.slot_widgets.values():
            self.all_widgets.append(d["item_dd"])
            self.all_widgets.append(d["prefix_dd"])
            self.all_widgets.append(d["suffix_dd"])
            self.all_widgets.append(d["clear_btn"])

        self._last_item_indices = {slot: 0 for slot in EQUIP_SLOTS_UI}

    def _build_widgets(self):
        start_y = 130
        row_h = 44
        for i, slot in enumerate(EQUIP_SLOTS_UI):
            y = start_y + i * row_h
            items_opts = ["(vazio)"] + [
                it.get("name", "?") + f" [{it.get('rarity','?')}]"
                for it in self.slot_items[slot]
            ]
            item_dd = Dropdown(210, y, 360, 32, items_opts, 0)
            prefix_dd = Dropdown(580, y, 200, 32, ["(vazio)"], 0)
            suffix_dd = Dropdown(790, y, 200, 32, ["(vazio)"], 0)
            clear_btn = Button(1000, y, 60, 32, "X", (lambda s=slot: self._clear_slot(s)),
                               color=(120, 90, 90), font=FONT_S)

            self.slot_widgets[slot] = {
                "item_dd": item_dd, "prefix_dd": prefix_dd,
                "suffix_dd": suffix_dd, "clear_btn": clear_btn,
            }

            # Carrega estado salvo
            eq = self.equipment.get(slot, {})
            if eq.get("item_id"):
                # Encontra índice
                for j, it in enumerate(self.slot_items[slot]):
                    if it.get("id") == eq["item_id"]:
                        item_dd.index = j + 1
                        break
            self._refresh_affix_options(slot)

            if eq.get("prefix_id"):
                for j, af in enumerate(self._get_applicable_affixes(slot, "Prefixo")):
                    if af.get("id") == eq["prefix_id"]:
                        prefix_dd.index = j + 1
                        break
            if eq.get("suffix_id"):
                for j, af in enumerate(self._get_applicable_affixes(slot, "Sufixo")):
                    if af.get("id") == eq["suffix_id"]:
                        suffix_dd.index = j + 1
                        break

    def _get_selected_item(self, slot):
        dd = self.slot_widgets[slot]["item_dd"]
        if dd.index == 0: return None
        idx = dd.index - 1
        if 0 <= idx < len(self.slot_items[slot]):
            return self.slot_items[slot][idx]
        return None

    def _get_applicable_affixes(self, slot, kind):
        item = self._get_selected_item(slot)
        if not item: return []
        cat = item.get("category", "")
        return [af for af in self.affixes_lib
                if af.get("kind") == kind and cat in af.get("applies_to", [])]

    def _refresh_affix_options(self, slot):
        prefixes = self._get_applicable_affixes(slot, "Prefixo")
        suffixes = self._get_applicable_affixes(slot, "Sufixo")
        pref_opts = ["(vazio)"] + [af.get("name","?") for af in prefixes]
        suf_opts  = ["(vazio)"] + [af.get("name","?") for af in suffixes]
        self.slot_widgets[slot]["prefix_dd"].options = pref_opts
        self.slot_widgets[slot]["prefix_dd"].index = min(self.slot_widgets[slot]["prefix_dd"].index, len(pref_opts)-1)
        self.slot_widgets[slot]["suffix_dd"].options = suf_opts
        self.slot_widgets[slot]["suffix_dd"].index = min(self.slot_widgets[slot]["suffix_dd"].index, len(suf_opts)-1)

    def _clear_slot(self, slot):
        self.slot_widgets[slot]["item_dd"].index = 0
        self.slot_widgets[slot]["prefix_dd"].index = 0
        self.slot_widgets[slot]["suffix_dd"].index = 0
        self.equipment[slot] = {"item_id": None, "prefix_id": None, "suffix_id": None}
        self._refresh_affix_options(slot)

    def commit(self):
        """Salva a seleção atual no dict `self.equipment`."""
        for slot in EQUIP_SLOTS_UI:
            dd = self.slot_widgets[slot]
            item = self._get_selected_item(slot)
            item_id = item.get("id") if item else None

            pre_idx = dd["prefix_dd"].index
            suf_idx = dd["suffix_dd"].index
            prefixes = self._get_applicable_affixes(slot, "Prefixo")
            suffixes = self._get_applicable_affixes(slot, "Sufixo")
            pre_id = prefixes[pre_idx - 1].get("id") if (pre_idx > 0 and pre_idx-1 < len(prefixes)) else None
            suf_id = suffixes[suf_idx - 1].get("id") if (suf_idx > 0 and suf_idx-1 < len(suffixes)) else None

            self.equipment[slot] = {
                "item_id": item_id, "prefix_id": pre_id, "suffix_id": suf_id,
            }

    def update(self, dt):
        # Detecta mudança em item_dd → refaz opções de affix
        for slot in EQUIP_SLOTS_UI:
            dd = self.slot_widgets[slot]["item_dd"]
            if dd.index != self._last_item_indices[slot]:
                self._last_item_indices[slot] = dd.index
                self._refresh_affix_options(slot)

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                in_list = any(d["item_dd"].open and d["item_dd"].list_rect().collidepoint(e.pos)
                              for d in self.slot_widgets.values())
                in_list2 = any(d["prefix_dd"].open and d["prefix_dd"].list_rect().collidepoint(e.pos)
                              for d in self.slot_widgets.values())
                in_list3 = any(d["suffix_dd"].open and d["suffix_dd"].list_rect().collidepoint(e.pos)
                              for d in self.slot_widgets.values())
                if in_list or in_list2 or in_list3:
                    for d in self.slot_widgets.values():
                        for dd in (d["item_dd"], d["prefix_dd"], d["suffix_dd"]):
                            if dd.open:
                                if dd.handle_event(e): break
                    continue
                # Fecha abertos
                for d in self.slot_widgets.values():
                    for dd in (d["item_dd"], d["prefix_dd"], d["suffix_dd"]):
                        if dd.open and not dd.rect.collidepoint(e.pos): dd.open = False
            for w in self.all_widgets:
                w.handle_event(e)

    def close(self):
        self.commit()
        self.on_close()

    def draw(self, surf, dt):
        # Overlay
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill(OVERLAY); surf.blit(ov, (0,0))

        # Painel principal
        rect = pygame.Rect(10, 10, WIDTH - 20, HEIGHT - 20)
        draw_panel(surf, rect, color=PANEL, radius=10)

        draw_text(surf, "EQUIPAR: " + self.unit_data.get("name","?"),
                  20, 25, FONT_L, ACCENT)
        draw_text(surf, "Escolha item, prefixo e sufixo por slot. Slot (vazio) = sem item.",
                  20, 55, FONT_S, TEXT_DIM)
        draw_text(surf, "SLOT", 20, 105, FONT_S, TEXT_DIM)
        draw_text(surf, "ITEM", 210, 105, FONT_S, TEXT_DIM)
        draw_text(surf, "PREFIXO", 580, 105, FONT_S, TEXT_DIM)
        draw_text(surf, "SUFIXO", 790, 105, FONT_S, TEXT_DIM)

        # Slots
        start_y = 130; row_h = 44
        for i, slot in enumerate(EQUIP_SLOTS_UI):
            y = start_y + i * row_h
            draw_text(surf, slot, 20, y + 8, FONT_M, TEXT)

        # Widgets
        for w in self.all_widgets:
            w.draw(surf, dt)
        for d in self.slot_widgets.values():
            for dd in (d["item_dd"], d["prefix_dd"], d["suffix_dd"]):
                if dd.open: dd.draw_list(surf)

        # Preview de stats à direita
        self.commit()
        stats = compute_effective_stats(self.unit_data, self.equipment,
                                        self.items_by_id, self.affixes_by_id)
        base_res = self.unit_data.get("resources", {})
        base_cb = self.unit_data.get("combat", {})

        px = 1080
        draw_text(surf, "PREVIEW", px, 105, FONT_S, ACCENT)
        py = 130
        stat_rows = [
            ("HP",       base_res.get("hp",0),       stats["hp"]),
            ("MANA",     base_res.get("mana",0),     stats["mana"]),
            ("STA",      base_res.get("stamina",0),  stats["stamina"]),
            ("ATQ F",    base_cb.get("attack_physical",0), stats["attack_physical"]),
            ("ATQ M",    base_cb.get("attack_magical",0),  stats["attack_magical"]),
            ("DEF F",    base_cb.get("defense_physical",0),stats["defense_physical"]),
            ("DEF M",    base_cb.get("defense_magical",0), stats["defense_magical"]),
            ("ACERTO",   base_cb.get("accuracy",100),stats["accuracy"]),
            ("ESQUIVA",  base_cb.get("evasion",0),   stats["evasion"]),
            ("CRIT",     base_cb.get("crit_chance",0),stats["crit_chance"]),
            ("INICIAT",  base_cb.get("initiative",0),stats["initiative"]),
            ("LIFESTEAL",base_cb.get("lifesteal",0), stats["lifesteal"]),
        ]
        for label, base, final in stat_rows:
            color = TEXT
            delta = final - base
            txt = f"{label}: {final}"
            if delta > 0: color = SUCCESS; txt += f" (+{delta})"
            elif delta < 0: color = DANGER; txt += f" ({delta})"
            draw_text(surf, txt, px, py, FONT_XS, color)
            py += 14
            if py > HEIGHT - 40: break


# ----------------------------------------------------------------------------
# Team Builder
# ----------------------------------------------------------------------------
class TeamBuilderScene(Scene):
    LIB_X, LIB_Y, LIB_W = 10, 70, 535
    LIB_H = 660
    TMS_X, TMS_Y, TMS_W = 555, 70, 715
    TMS_H = 660
    ROWS_PER_PAGE = 16
    ROW_H = 33

    def __init__(self, app):
        super().__init__(app)
        self.units_lib, self.skills_by_name, self.items_lib, self.affixes_lib = load_library()
        self.items_by_id = {it.get("id",""): it for it in self.items_lib}
        self.affixes_by_id = {af.get("id",""): af for af in self.affixes_lib}

        # Equipamento por (ti, ui) — vem de equipar via modal
        # NOTA: quando o roster muda (add/remove), a chave precisa ser reindexada.
        # Solução simples: guardamos o equipment dentro de cada entrada do roster.
        # Ao remover uma unidade, a equip some com ela.

        races = sorted(set(u.get("race", "") for u in self.units_lib if u.get("race")))
        self.filter_options = ["Todas"] + races
        self.filter_dd = Dropdown(370, 80, 165, 28, self.filter_options, 0)
        self.search_input = TextInput(20, 80, 340, 28, "Buscar unidade...")
        self.btn_clear_search = Button(348, 80, 18, 28, "x",
                                       self._clear_search, (120,90,90), font=FONT_S)
        self.num_teams = 2
        self.teams = [[], [], [], []]
        self.active_team = 0
        self.page = 0
        self.filtered = []
        self.page_items = []
        self.message = ""
        self.message_color = SUCCESS
        self.message_timer = 0.0
        self._last_search = ""; self._last_filter = 0
        self.modal = None  # EquipmentModal ativo
        self._rebuild()

    def _clear_search(self):
        self.search_input.text = ""; self.search_input.active = False
        self.page = 0; self._rebuild()

    def _set_team_count(self, n):
        self.num_teams = n
        if self.active_team >= n: self.active_team = 0
        # Limpa equipamento órfão
        for ti in range(n, 4):
            for entry in self.teams[ti]:
                entry.pop("__equipped__", None)
        self._rebuild()

    def _set_active_team(self, ti):
        self.active_team = ti; self._rebuild()

    def _apply_filters(self):
        q = self.search_input.text.strip().lower()
        race_filter = self.filter_dd.value
        out = []
        for u in self.units_lib:
            name = u.get("name", "")
            if q and q not in name.lower(): continue
            if race_filter != "Todas" and u.get("race", "") != race_filter: continue
            out.append(u)
        return out

    def _rebuild(self):
        self.filtered = self._apply_filters()
        total = len(self.filtered)
        max_page = max(0, (total - 1)//self.ROWS_PER_PAGE) if total > 0 else 0
        if self.page > max_page: self.page = max_page
        start = self.page * self.ROWS_PER_PAGE
        end = min(start + self.ROWS_PER_PAGE, total)
        self.page_items = self.filtered[start:end]

        self.all_widgets = []; self.all_inputs = [self.search_input]
        self.all_dropdowns = [self.filter_dd]

        for i, n in enumerate([2,3,4]):
            self.all_widgets.append(Button(20 + i*90, 20, 80, 34, f"{n} TIMES",
                (lambda nn=n: self._set_team_count(nn)),
                color=ACCENT if self.num_teams == n else (60,66,82), font=FONT_S))

        for i in range(self.num_teams):
            self.all_widgets.append(Button(320 + i*190, 20, 175, 34, TEAM_NAMES[i],
                (lambda ti=i: self._set_active_team(ti)),
                color=TEAM_COLORS[i] if self.active_team == i else TEAM_COLORS_DARK[i],
                font=FONT_S))

        self.all_widgets.append(self.search_input)
        self.all_widgets.append(self.btn_clear_search)
        self.all_widgets.append(self.filter_dd)

        row_y = 145
        for udata in self.page_items:
            name = udata.get("name", "?")
            self.all_widgets.append(Button(self.LIB_X+5, row_y, self.LIB_W-10, 30, name,
                (lambda nn=name: self._add_unit(nn)),
                color=(50,58,76), font=FONT_S))
            row_y += self.ROW_H

        self.btn_prev = Button(self.LIB_X+5, 700, 90, 28, "◀ ANT",
                               self._prev_page, color=(95,130,220), font=FONT_S)
        self.btn_next = Button(self.LIB_X+self.LIB_W-95, 700, 90, 28, "PRÓX ▶",
                               self._next_page, color=(95,130,220), font=FONT_S)
        self.btn_prev.enabled = self.page > 0
        self.btn_next.enabled = (self.page + 1) * self.ROWS_PER_PAGE < total
        self.all_widgets.append(self.btn_prev)
        self.all_widgets.append(self.btn_next)

        # Chips de time + botão EQ
        for ti in range(self.num_teams):
            base_y = self._team_box_y(ti) + 30
            for ui, udata in enumerate(self.teams[ti]):
                cols = 3; col = ui % cols; row = ui // cols
                chip_x = self.TMS_X + 10 + col * 228
                chip_y = base_y + row * 30
                name = udata.get("name", "?")
                self.all_widgets.append(Button(chip_x, chip_y, 190, 26,
                    "× " + fit(name, FONT_S, 180),
                    (lambda t=ti, u=ui: self._remove_unit(t, u)),
                    color=TEAM_COLORS_DARK[ti], font=FONT_S))
                # Botão de equipar
                eq_count = sum(1 for v in (udata.get("__equipped__") or {}).values()
                               if v.get("item_id"))
                eq_label = f"⚙ {eq_count}" if eq_count else "⚙ EQ"
                eq_color = (180, 140, 60) if eq_count else (90, 80, 60)
                self.all_widgets.append(Button(chip_x + 194, chip_y, 32, 26,
                    eq_label, (lambda t=ti, u=ui: self._open_equip_modal(t, u)),
                    color=eq_color, font=FONT_XS))

        self.all_widgets.append(Button(20, 745, 160, 42, "VOLTAR",
            lambda: self.app.change_scene(MenuScene(self.app)), color=(90,90,110)))
        self.all_widgets.append(Button(WIDTH - 280, 743, 260, 46, "INICIAR BATALHA",
            self._start_battle, color=SUCCESS))

    def _team_box_y(self, ti):
        box_h, gap = self._team_box_geom()
        return self.TMS_Y + ti * (box_h + gap)

    def _team_box_geom(self):
        gap = 8
        box_h = (self.TMS_H - gap * (self.num_teams - 1)) // self.num_teams
        return box_h, gap

    def _add_unit(self, name):
        udata = next((u for u in self.units_lib if u.get("name") == name), None)
        if not udata: return
        if len(self.teams[self.active_team]) >= 6:
            self.show_message("Time cheio (máx 6).", WARN); return
        copy_entry = copy.deepcopy(udata)
        copy_entry["__equipped__"] = default_equipped()
        self.teams[self.active_team].append(copy_entry)
        self.show_message(f"{name} → {TEAM_NAMES[self.active_team]}.", SUCCESS)
        self._rebuild()

    def _remove_unit(self, ti, ui):
        if 0 <= ui < len(self.teams[ti]): self.teams[ti].pop(ui)
        self._rebuild()

    def _next_page(self): self.page += 1; self._rebuild()
    def _prev_page(self): self.page = max(0, self.page-1); self._rebuild()

    def _open_equip_modal(self, ti, ui):
        if not (0 <= ti < self.num_teams and 0 <= ui < len(self.teams[ti])): return
        entry = self.teams[ti][ui]
        if "__equipped__" not in entry:
            entry["__equipped__"] = default_equipped()
        self.modal = EquipmentModal(entry, entry["__equipped__"],
                                    self.items_lib, self.affixes_lib,
                                    on_close=self._close_modal)

    def _close_modal(self):
        self.modal = None
        self._rebuild()

    def _start_battle(self):
        active = [self.teams[i] for i in range(self.num_teams)]
        if any(len(t) == 0 for t in active):
            self.show_message("Cada time precisa de pelo menos 1 unidade.", DANGER); return
        # Monta dict de equipamento {(ti, ui): {slot: {...}}}
        team_equipment = {}
        for ti in range(self.num_teams):
            for ui, entry in enumerate(self.teams[ti]):
                team_equipment[(ti, ui)] = entry.get("__equipped__", default_equipped())
        self.app.change_scene(BattleScene(self.app, active, self.skills_by_name,
                                          self.items_by_id, self.affixes_by_id, team_equipment))

    def show_message(self, msg, color=SUCCESS):
        self.message = msg; self.message_color = color; self.message_timer = 3.0

    def handle_events(self, events):
        if self.modal:
            # Modal intercepta tudo
            for e in events:
                if e.type == pygame.QUIT: self.app.running = False; return
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    self.modal.close(); return
            self.modal.handle_events(events)
            return
        super().handle_events(events)

    def update(self, dt):
        if self.modal:
            self.modal.update(dt)
            return
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0: self.message = ""
        if self.search_input.text != self._last_search:
            self._last_search = self.search_input.text; self.page = 0; self._rebuild()
        if self.filter_dd.index != self._last_filter:
            self._last_filter = self.filter_dd.index; self.page = 0; self._rebuild()

    def draw(self, surf, dt):
        surf.fill(BG)
        draw_text(surf, "MONTAR TIMES", 20, 22, FONT_L, TEXT)

        # Biblioteca
        draw_panel(surf, pygame.Rect(self.LIB_X, self.LIB_Y, self.LIB_W, self.LIB_H))
        draw_text(surf, "BIBLIOTECA DE UNIDADES", self.LIB_X+10, self.LIB_Y+8, FONT_L, ACCENT)
        total = len(self.filtered)
        if total == 0:
            draw_text(surf, "Nenhuma unidade encontrada.", self.LIB_X+10, 140, FONT_M, WARN)
        else:
            tp = max(1, (total + self.ROWS_PER_PAGE - 1)//self.ROWS_PER_PAGE)
            draw_text(surf, f"{total} filtradas · pág {self.page+1}/{tp}",
                      self.LIB_X+10, 120, FONT_S, TEXT_DIM)

        # Times
        for ti in range(self.num_teams):
            by = self._team_box_y(ti)
            bh, _ = self._team_box_geom()
            col = TEAM_COLORS[ti]
            bg = PANEL_LIGHT if self.active_team == ti else PANEL
            pygame.draw.rect(surf, bg, pygame.Rect(self.TMS_X, by, self.TMS_W, bh), border_radius=6)
            pygame.draw.rect(surf, col if self.active_team == ti else BORDER,
                             pygame.Rect(self.TMS_X, by, self.TMS_W, bh), 2, border_radius=6)
            draw_text(surf, TEAM_NAMES[ti], self.TMS_X+10, by+6, FONT_L, col)
            count = len(self.teams[ti])
            draw_text(surf, f"{count}/6", self.TMS_X+self.TMS_W-50, by+8, FONT_M, TEXT_DIM)
            if count == 0:
                draw_text(surf, "Clique numa unidade para adicionar.",
                          self.TMS_X+10, by+40, FONT_S, TEXT_DIM)

        for w in self.all_widgets: w.draw(surf, dt)
        for d in self.all_dropdowns:
            if d.open: d.draw_list(surf)

        if self.message:
            r = FONT_M.render(self.message, True, self.message_color)
            surf.blit(r, (WIDTH//2 - r.get_width()//2, 715))
        draw_text(surf, "ESC = menu   |   ⚙ EQ = equipar", WIDTH - 260, 758, FONT_S, TEXT_DIM)

        if self.modal:
            self.modal.draw(surf, dt)


# ----------------------------------------------------------------------------
# Battle Scene
# ----------------------------------------------------------------------------
class BattleScene(Scene):
    def __init__(self, app, teams, skills_by_name, items_by_id, affixes_by_id, team_equipment):
        super().__init__(app)
        self.battle = Battle(teams, skills_by_name,
                             items_by_id=items_by_id,
                             affixes_by_id=affixes_by_id,
                             team_equipment=team_equipment)
        self.auto = False; self.auto_delay = 0.5; self.auto_timer = 0.0
        self._rebuild()

    def _rebuild(self):
        self.all_widgets = [
            Button(WIDTH-300, 738, 130, 42, "PRÓXIMO TURNO",
                   self._next_turn, color=ACCENT, font=FONT_S),
            Button(WIDTH-160, 738, 140, 42,
                   ("AUTO: ON" if self.auto else "AUTO: OFF"),
                   self._toggle_auto, color=SUCCESS if self.auto else (90,90,110),
                   font=FONT_S),
            Button(20, 738, 160, 42, "VOLTAR",
                   lambda: self.app.change_scene(MenuScene(self.app)),
                   color=(90,90,110), font=FONT_S),
        ]

    def _next_turn(self):
        if not self.battle.finished: self.battle.advance()
    def _toggle_auto(self):
        self.auto = not self.auto; self.auto_timer = 0.0; self._rebuild()

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.QUIT: self.app.running = False; return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.app.change_scene(MenuScene(self.app)); return
                if e.key == pygame.K_SPACE: self._next_turn()
                if e.key == pygame.K_a: self._toggle_auto()
            for w in self.all_widgets: w.handle_event(e)

    def update(self, dt):
        if self.auto and not self.battle.finished:
            self.auto_timer += dt
            if self.auto_timer >= self.auto_delay:
                self.auto_timer = 0.0; self._next_turn()

    def draw(self, surf, dt):
        surf.fill(BG)
        b = self.battle
        draw_text(surf, "BATTLE SIMULATOR", 20, 15, FONT_XL, TEXT)
        draw_text(surf, f"RODADA {b.round}", WIDTH//2 - 60, 22, FONT_L, ACCENT)
        apt = {}
        for u in b.alive_units(): apt[u.team] = apt.get(u.team, 0) + 1
        info = "  ".join(f"{TEAM_NAMES[t]}: {c}" for t, c in sorted(apt.items()))
        draw_text(surf, info, WIDTH//2 - 60, 46, FONT_S, TEXT_DIM)

        grid_rect = pygame.Rect(GRID_X, GRID_Y, GRID_W, GRID_H)
        pygame.draw.rect(surf, GRID_BG, grid_rect)
        for c in range(GRID_COLS+1):
            x = GRID_X + c*TILE
            pygame.draw.line(surf, GRID_LINE, (x, GRID_Y), (x, GRID_Y+GRID_H))
        for r in range(GRID_ROWS+1):
            y = GRID_Y + r*TILE
            pygame.draw.line(surf, GRID_LINE, (GRID_X, y), (GRID_X+GRID_W, y))
        pygame.draw.rect(surf, BORDER, grid_rect, 2)

        cur = b.current()
        for u in b.units:
            px = GRID_X + u.x*TILE; py = GRID_Y + u.y*TILE
            if not u.alive:
                pygame.draw.line(surf, (70,70,80), (px+6,py+6), (px+TILE-6,py+TILE-6), 3)
                pygame.draw.line(surf, (70,70,80), (px+TILE-6,py+6), (px+6,py+TILE-6), 3)
                continue
            col = TEAM_COLORS[u.team]
            if u is cur:
                pygame.draw.rect(surf, (255,255,255,60),
                                 pygame.Rect(px+1,py+1,TILE-2,TILE-2), border_radius=6)
            pygame.draw.rect(surf, col, pygame.Rect(px+4,py+4,TILE-8,TILE-8), border_radius=6)
            pygame.draw.rect(surf, (255,255,255,40),
                             pygame.Rect(px+4,py+4,TILE-8,TILE-8), 2, border_radius=6)
            if u.is_summon:
                pygame.draw.rect(surf, WARN,
                                 pygame.Rect(px+2,py+2,TILE-4,TILE-4), 2, border_radius=6)

            init = u.name[:1].upper()
            r = FONT_L.render(init, True, (255,255,255))
            surf.blit(r, (px+(TILE-r.get_width())//2, py+(TILE-r.get_height())//2-2))

            hp_pct = max(0.0, u.hp/u.max_hp)
            bar_w = TILE-12; bar_h = 4
            bx = px+6; by = py+TILE-9
            pygame.draw.rect(surf, (30,30,40), pygame.Rect(bx,by,bar_w,bar_h))
            hp_col = SUCCESS if hp_pct > 0.5 else (WARN if hp_pct > 0.25 else DANGER)
            pygame.draw.rect(surf, hp_col, pygame.Rect(bx,by,int(bar_w*hp_pct),bar_h))

            if u.skip_next:
                pygame.draw.circle(surf, WARN, (px+TILE-8, py+8), 4)
            if u.has_effect("Silêncio"):
                pygame.draw.circle(surf, (200,100,200), (px+8, py+8), 4)
            if u.has_effect("Invencibilidade"):
                pygame.draw.circle(surf, (255,255,100), (px+TILE-8, py+16), 4)

        # Log
        log_rect = pygame.Rect(LOG_X, LOG_Y, LOG_W, LOG_H)
        draw_panel(surf, log_rect)
        draw_text(surf, "LOG DE BATALHA", LOG_X+10, LOG_Y+8, FONT_L, ACCENT)
        line_h = 16; avail = LOG_H - 40; max_lines = avail // line_h
        lines = b.log[-max_lines:]
        ly = LOG_Y + 34
        for text, color in lines:
            draw_text(surf, fit(text, FONT_S, LOG_W-20), LOG_X+10, ly, FONT_S, color)
            ly += line_h

        # Próximos
        order_y = LOG_Y + LOG_H + 8
        draw_text(surf, "PRÓXIMOS:", LOG_X, order_y, FONT_S, TEXT_DIM)
        tx = LOG_X + 90
        for i, u in enumerate(b.turn_order):
            if i < b.turn_index or not u.alive: continue
            col = TEAM_COLORS[u.team]
            label = u.display()[:12]
            r = FONT_XS.render(label, True, (20,20,30))
            w = r.get_width() + 12
            if tx + w > LOG_X + LOG_W: break
            pygame.draw.rect(surf, col, pygame.Rect(tx, order_y-2, w, 18), border_radius=4)
            surf.blit(r, (tx+6, order_y))
            tx += w + 4

        # Painel unidade atual
        cur = b.current()
        if cur is not None:
            info_rect = pygame.Rect(20, 640, GRID_W, 86)
            draw_panel(surf, info_rect, color=(28,33,44))
            draw_text(surf, f"VEZ DE: {cur.display()}", 30, 646, FONT_L, TEAM_COLORS[cur.team])
            # Equipamentos (1ª linha)
            eq_txt = " · ".join([f"{s}: {n}" for s, n in cur.equipped_display[:3]])
            if eq_txt:
                draw_text(surf, "⚙ " + fit(eq_txt, FONT_XS, GRID_W - 20),
                          30, 668, FONT_XS, (200, 180, 120))

            bar_y = 685; bar_w = 240
            hp_pct = max(0, cur.hp)/cur.max_hp
            pygame.draw.rect(surf, (30,30,40), pygame.Rect(30,bar_y,bar_w,14), border_radius=3)
            pygame.draw.rect(surf, DANGER, pygame.Rect(30,bar_y,int(bar_w*hp_pct),14), border_radius=3)
            draw_text(surf, f"HP {max(0,cur.hp)}/{cur.max_hp}", 34, bar_y+1, FONT_XS, TEXT)
            if cur.max_mana:
                mp = cur.mana/max(1,cur.max_mana)
                pygame.draw.rect(surf, (30,30,40), pygame.Rect(290,bar_y,bar_w,14), border_radius=3)
                pygame.draw.rect(surf, ACCENT, pygame.Rect(290,bar_y,int(bar_w*mp),14), border_radius=3)
                draw_text(surf, f"MP {cur.mana}/{cur.max_mana}", 294, bar_y+1, FONT_XS, TEXT)
            if cur.max_sta:
                sp = cur.sta/max(1,cur.max_sta)
                pygame.draw.rect(surf, (30,30,40), pygame.Rect(550,bar_y,bar_w,14), border_radius=3)
                pygame.draw.rect(surf, SUCCESS, pygame.Rect(550,bar_y,int(bar_w*sp),14), border_radius=3)
                draw_text(surf, f"ST {cur.sta}/{cur.max_sta}", 554, bar_y+1, FONT_XS, TEXT)

            ex = 810
            for e in cur.effects[:6]:
                label = f"{e['type'][:9]}({e['duration']})"
                r = FONT_XS.render(label, True, WARN)
                surf.blit(r, (ex, bar_y))
                ex += r.get_width() + 8
                if ex > GRID_X + GRID_W - 40: break

        for w in self.all_widgets: w.draw(surf, dt)

        if b.finished:
            ov = pygame.Surface((GRID_W, GRID_H), pygame.SRCALPHA)
            ov.fill((0,0,0,150)); surf.blit(ov, (GRID_X, GRID_Y))
            if b.winner_team is not None:
                msg = f"{TEAM_NAMES[b.winner_team]} VENCEU!"
                col = TEAM_COLORS[b.winner_team]
            else:
                msg = "EMPATE"; col = WARN
            r = FONT_XL.render(msg, True, col)
            surf.blit(r, (GRID_X + GRID_W//2 - r.get_width()//2,
                          GRID_Y + GRID_H//2 - r.get_height()//2))

        draw_text(surf, "ESPAÇO = próximo turno   |   A = auto   |   ESC = menu",
                  20, 782, FONT_S, TEXT_DIM)


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------
class App:
    def __init__(self):
        self.running = True
        self.scene = MenuScene(self)
    def change_scene(self, scene):
        for w in getattr(self.scene, "all_inputs", []):
            w.active = False
        self.scene = scene
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