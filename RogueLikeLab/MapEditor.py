# -*- coding: utf-8 -*-
"""
MapEditor.py — Editor de tile maps estilo RPG Maker.
"""

import os, json
import pygame

# ============================================================================
# Config / layout
# ============================================================================
WIDTH, HEIGHT = 1400, 850
TOP_H     = 42
LEFT_W    = 280
RIGHT_W   = 340
BOTTOM_H  = 26
CANVAS_X  = LEFT_W
CANVAS_Y  = TOP_H
CANVAS_W  = WIDTH - LEFT_W - RIGHT_W
CANVAS_H  = HEIGHT - TOP_H - BOTTOM_H
LAYERS = 4

pygame.init()
pygame.font.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Map Editor")
clock = pygame.time.Clock()

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports", "maps")
os.makedirs(EXPORTS_DIR, exist_ok=True)
AUTOSAVE_PATH = os.path.join(EXPORTS_DIR, "_autosave.json")

# ============================================================================
# Cores
# ============================================================================
BG            = (22, 20, 18)
PANEL_BG      = (32, 28, 24)
PANEL_DARK    = (24, 21, 18)
PANEL_BORDER  = (80, 65, 45)
TEXT          = (220, 210, 190)
TEXT_DIM      = (140, 130, 110)
TEXT_GOLD     = (240, 200, 80)
ACCENT        = (200, 155, 85)
ACCENT_DARK   = (110, 85, 45)
ACCENT_BRIGHT = (240, 200, 100)
HIGHLIGHT     = (255, 220, 100)
SUCCESS       = (110, 200, 110)
DANGER        = (200, 70, 70)
WARN          = (230, 175, 70)
BTN           = (60, 50, 40)
BTN_HOVER     = (95, 78, 58)
BTN_ACTIVE    = (140, 110, 70)
BTN_TEXT      = (235, 225, 205)
CANVAS_BG     = (16, 14, 12)
EMPTY_CELL    = (42, 38, 34)

PASS_OK       = (110, 220, 110, 130)
PASS_BLOCK    = (220, 80, 80, 130)
PASS_ABOVE    = (120, 180, 240, 130)
PASS_TILE_OK  = (110, 220, 110, 35)
PASS_TILE_BLK = (220, 80, 80, 35)

FONT_L  = pygame.font.SysFont("georgia,dejavuserif,serif", 16, bold=True)
FONT_M  = pygame.font.SysFont("georgia,dejavuserif,serif", 13)
FONT_S  = pygame.font.SysFont("georgia,dejavuserif,serif", 11)
FONT_XS = pygame.font.SysFont("georgia,dejavuserif,serif", 10)

# ============================================================================
# Helpers
# ============================================================================
def draw_text(surf, text, x, y, font=FONT_M, color=TEXT, center=False):
    r = font.render(str(text), True, color)
    if center: surf.blit(r, (x - r.get_width()//2, y))
    else:      surf.blit(r, (x, y))
    return r

def draw_button(surf, rect, label, font=FONT_XS, active=False, primary=False,
                danger=False):
    mouse = pygame.mouse.get_pos()
    hover = rect.collidepoint(mouse)
    if primary:
        bg = (175, 135, 70) if hover else ACCENT
        border = ACCENT_BRIGHT
    elif danger:
        bg = (150, 60, 60) if hover else (100, 45, 45)
        border = DANGER
    elif active:
        bg = BTN_ACTIVE
        border = ACCENT_BRIGHT
    elif hover:
        bg = BTN_HOVER
        border = ACCENT_DARK
    else:
        bg = BTN
        border = ACCENT_DARK
    pygame.draw.rect(surf, bg, rect, border_radius=4)
    pygame.draw.rect(surf, border, rect, 1, border_radius=4)
    r = font.render(label, True, BTN_TEXT)
    surf.blit(r, (rect.centerx - r.get_width()//2,
                  rect.centery - r.get_height()//2))

def clamp(v, mn, mx): return max(mn, min(mx, v))

def pick_image_file():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        path = filedialog.askopenfilename(
            title="Escolher sprite",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.gif"),
                       ("Todos", "*.*")])
        root.destroy()
        return path or None
    except Exception:
        return None

def parse_hex_color(s, default=(150, 150, 150)):
    try:
        s = s.strip().lstrip("#")
        if len(s) >= 6:
            return (int(s[0:2],16), int(s[2:4],16), int(s[4:6],16))
    except Exception: pass
    return default

def color_to_hex(c): return "%02x%02x%02x" % tuple(c[:3])

# ============================================================================
# TextField
# ============================================================================
class TextField:
    def __init__(self, key, label, value="", max_len=80):
        self.key = key; self.label = label; self.value = value
        self.max_len = max_len
        self.label_rect = pygame.Rect(0, 0, 0, 0)
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.focused = False
        self.active_this_frame = False

    def set_position(self, x, y, w):
        self.label_rect = pygame.Rect(x, y, w, 12)
        self.rect = pygame.Rect(x, y + 14, w, 24)
        self.active_this_frame = True

    def mark_inactive(self):
        self.label_rect = pygame.Rect(0, 0, 0, 0)
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.active_this_frame = False

    def handle_key(self, event):
        if not self.focused: return False
        if event.key == pygame.K_BACKSPACE:
            self.value = self.value[:-1]; return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.focused = False; return True
        ch = event.unicode
        if ch and ch.isprintable() and len(self.value) < self.max_len:
            self.value += ch; return True
        return False

    def draw(self, surf):
        lab = FONT_XS.render(self.label, True, TEXT_DIM)
        surf.blit(lab, (self.label_rect.x, self.label_rect.y))
        bg = (55, 45, 34) if self.focused else (36, 30, 25)
        pygame.draw.rect(surf, bg, self.rect, border_radius=3)
        border = ACCENT_BRIGHT if self.focused else ACCENT_DARK
        pygame.draw.rect(surf, border, self.rect, 1, border_radius=3)
        ts = FONT_S.render(self.value, True, TEXT)
        clip_old = surf.get_clip()
        surf.set_clip(self.rect.inflate(-8, -4))
        surf.blit(ts, (self.rect.x + 6, self.rect.y + 6))
        if self.focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            cx = self.rect.x + 6 + ts.get_width()
            pygame.draw.line(surf, TEXT, (cx, self.rect.y + 5),
                             (cx, self.rect.bottom - 5), 1)
        surf.set_clip(clip_old)

# ============================================================================
# InputDialog
# ============================================================================
class InputDialog:
    def __init__(self):
        self.active = False
        self.text = ""
        self.title = ""
        self.prompt = ""
        self.rect = pygame.Rect(0, 0, 480, 180)
        self.rect.center = (WIDTH // 2, HEIGHT // 2)
        self.input_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_ok = None; self.btn_cancel = None
        self.on_ok = None

    def open(self, title, prompt, default="", on_ok=None):
        self.active = True
        self.title = title; self.prompt = prompt
        self.text = default
        self.on_ok = on_ok
        r = self.rect
        self.input_rect = pygame.Rect(r.x + 20, r.y + 70, r.w - 40, 34)
        bw = 130; by = r.bottom - 50
        self.btn_cancel = pygame.Rect(r.x + 20, by, bw, 32)
        self.btn_ok = pygame.Rect(r.right - 20 - bw, by, bw, 32)

    def close(self): self.active = False

    def handle_event(self, event):
        if not self.active: return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: self.close()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.on_ok: self.on_ok(self.text)
                self.close()
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable() and len(self.text) < 64:
                    if ch not in '\\/:*?"<>|': self.text += ch
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.btn_cancel.collidepoint(event.pos): self.close()
            elif self.btn_ok.collidepoint(event.pos):
                if self.on_ok: self.on_ok(self.text)
                self.close()

    def draw(self, surf):
        if not self.active: return
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170)); surf.blit(overlay, (0, 0))
        r = self.rect
        pygame.draw.rect(surf, PANEL_BG, r, border_radius=8)
        pygame.draw.rect(surf, ACCENT_BRIGHT, r, 2, border_radius=8)
        draw_text(surf, self.title, r.x + 20, r.y + 16, FONT_L, ACCENT_BRIGHT)
        draw_text(surf, self.prompt, r.x + 20, r.y + 48, FONT_S, TEXT_DIM)
        pygame.draw.rect(surf, (22, 19, 16), self.input_rect, border_radius=4)
        pygame.draw.rect(surf, ACCENT_DARK, self.input_rect, 1, border_radius=4)
        caret = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        shown = self.text + caret
        col = TEXT if self.text else (90, 80, 65)
        txt = FONT_M.render(shown if self.text else "digite aqui", True, col)
        surf.blit(txt, (self.input_rect.x + 8, self.input_rect.y + 9))
        draw_button(surf, self.btn_cancel, "Cancelar  (ESC)", FONT_M)
        draw_button(surf, self.btn_ok, "OK  (Enter)", FONT_M, primary=True)

# ============================================================================
# SaveDialog
# ============================================================================
class SaveDialog:
    def __init__(self):
        self.active = False; self.text = ""
        self.rect = pygame.Rect(0, 0, 460, 190)
        self.rect.center = (WIDTH // 2, HEIGHT // 2)
        self.input_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_save = None; self.btn_cancel = None
        self._layout()
    def _layout(self):
        r = self.rect
        self.input_rect = pygame.Rect(r.x + 20, r.y + 70, r.w - 40, 34)
        bw = 130; by = r.bottom - 50
        self.btn_cancel = pygame.Rect(r.x + 20, by, bw, 32)
        self.btn_save = pygame.Rect(r.right - 20 - bw, by, bw, 32)
    def open(self, default_name=""):
        self.active = True; self.text = default_name or ""; self._layout()
    def close(self): self.active = False
    def handle_event(self, event):
        if not self.active: return None
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: return "cancel"
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER): return "save"
            if event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable() and len(self.text) < 64:
                    if ch not in '\\/:*?"<>|': self.text += ch
            return None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.btn_cancel.collidepoint(event.pos): return "cancel"
            if self.btn_save.collidepoint(event.pos): return "save"
            if not self.rect.collidepoint(event.pos): return "cancel"
        return None
    def draw(self, surf):
        if not self.active: return
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170)); surf.blit(overlay, (0, 0))
        r = self.rect
        pygame.draw.rect(surf, PANEL_BG, r, border_radius=8)
        pygame.draw.rect(surf, ACCENT_BRIGHT, r, 2, border_radius=8)
        draw_text(surf, "SALVAR PROJETO COMO", r.x + 20, r.y + 16, FONT_L, ACCENT_BRIGHT)
        draw_text(surf, "Digite o nome do arquivo:", r.x + 20, r.y + 48, FONT_S, TEXT_DIM)
        pygame.draw.rect(surf, (22, 19, 16), self.input_rect, border_radius=4)
        pygame.draw.rect(surf, ACCENT_DARK, self.input_rect, 1, border_radius=4)
        caret = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        shown = self.text + caret
        col = TEXT if self.text else (90, 80, 65)
        txt = FONT_M.render(shown if self.text else "meu_projeto", True, col)
        surf.blit(txt, (self.input_rect.x + 8, self.input_rect.y + 9))
        draw_button(surf, self.btn_cancel, "Cancelar  (ESC)", FONT_M)
        draw_button(surf, self.btn_save, "Salvar  (Enter)", FONT_M, primary=True)

# ============================================================================
# ContextMenu
# ============================================================================
class ContextMenu:
    def __init__(self):
        self.active = False; self.items = []; self.rect = None
    def open(self, pos, items):
        if not items: return
        self.active = True; self.items = items
        w = max(FONT_M.size(l)[0] for l, _ in items) + 24
        h = len(items) * 24 + 8
        x = min(pos[0], WIDTH - w - 4)
        y = min(pos[1], HEIGHT - h - 4)
        self.rect = pygame.Rect(x, y, w, h)
    def close(self):
        self.active = False; self.items = []
    def handle_event(self, event):
        if not self.active: return None
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for i, (label, cb) in enumerate(self.items):
                    r = pygame.Rect(self.rect.x, self.rect.y + 4 + i*24,
                                    self.rect.w, 24)
                    if r.collidepoint(event.pos):
                        self.close()
                        return cb
                if not self.rect.collidepoint(event.pos):
                    self.close()
            elif event.button == 3:
                self.close()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
        return None
    def draw(self, surf):
        if not self.active or not self.items: return
        pygame.draw.rect(surf, PANEL_BG, self.rect, border_radius=4)
        pygame.draw.rect(surf, ACCENT_BRIGHT, self.rect, 2, border_radius=4)
        for i, (label, _) in enumerate(self.items):
            r = pygame.Rect(self.rect.x, self.rect.y + 4 + i*24, self.rect.w, 24)
            if r.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(surf, BTN_HOVER, r, border_radius=3)
            draw_text(surf, label, r.x + 10, r.y + 5, FONT_M, TEXT)

# ============================================================================
# Tile
# ============================================================================
class Tile:
    def __init__(self, tid, name, color=(128,128,128),
                 walkable=True, category="Geral", image_path=None):
        self.id = tid; self.name = name
        self.color = tuple(color); self.walkable = walkable
        self.category = category; self.image_path = image_path
        self._img_cache = {}
    def get_surface(self, size):
        if not self.image_path: return None
        if size in self._img_cache: return self._img_cache[size]
        try:
            if not os.path.isfile(self.image_path):
                self._img_cache[size] = None; return None
            img = pygame.image.load(self.image_path).convert_alpha()
            scaled = pygame.transform.smoothscale(img, (size, size))
            self._img_cache[size] = scaled; return scaled
        except Exception:
            self._img_cache[size] = None; return None
    def clear_cache(self): self._img_cache = {}
    def to_dict(self):
        return {"id": self.id, "name": self.name,
                "color": list(self.color), "walkable": self.walkable,
                "category": self.category, "image_path": self.image_path}
    @classmethod
    def from_dict(cls, d):
        return cls(d["id"], d["name"], tuple(d.get("color", (128,128,128))),
                   d.get("walkable", True), d.get("category", "Geral"),
                   d.get("image_path"))

# ============================================================================
# TileSet
# ============================================================================
class TileSet:
    def __init__(self):
        self.tiles = {}; self.order = []
    def add(self, tile):
        self.tiles[tile.id] = tile
        if tile.id not in self.order: self.order.append(tile.id)
    def remove(self, tid):
        if tid in self.tiles:
            del self.tiles[tid]
            self.order = [t for t in self.order if t != tid]
    def get(self, tid): return self.tiles.get(tid)
    def unique_id(self, base="tile"):
        i = 1
        while f"{base}_{i}" in self.tiles: i += 1
        return f"{base}_{i}"
    def categories(self):
        cats = []
        for tid in self.order:
            c = self.tiles[tid].category
            if c not in cats: cats.append(c)
        return cats
    def to_dict(self):
        return {"order": self.order,
                "tiles": [self.tiles[tid].to_dict() for tid in self.order]}
    @classmethod
    def from_dict(cls, d):
        ts = cls()
        for td in d.get("tiles", []): ts.add(Tile.from_dict(td))
        ts.order = d.get("order", list(ts.tiles.keys()))
        return ts

def default_tileset():
    ts = TileSet()
    data = [
        ("grass","Grama",(90,140,80),True,"Terreno"),
        ("grass_dark","Grama escura",(66,105,60),True,"Terreno"),
        ("dirt","Terra",(140,100,70),True,"Terreno"),
        ("sand","Areia",(220,200,130),True,"Terreno"),
        ("snow","Neve",(230,230,240),True,"Terreno"),
        ("stone_floor","Piso de pedra",(130,125,115),True,"Piso"),
        ("wood_floor","Piso de madeira",(150,110,75),True,"Piso"),
        ("water","Água",(60,90,160),False,"Terreno"),
        ("lava","Lava",(210,90,40),False,"Terreno"),
        ("tree","Árvore",(35,70,35),False,"Natureza"),
        ("bush","Arbusto",(55,100,55),True,"Natureza"),
        ("rock","Rocha",(100,95,88),False,"Natureza"),
        ("flower_red","Flor vermelha",(200,80,80),True,"Detalhes"),
        ("flower_yellow","Flor amarela",(220,200,80),True,"Detalhes"),
        ("path_stone","Caminho de pedra",(170,160,140),True,"Detalhes"),
        ("wall_stone","Parede de pedra",(75,70,65),False,"Estruturas"),
        ("wall_wood","Parede madeira",(120,85,55),False,"Estruturas"),
        ("door","Porta",(170,120,70),True,"Estruturas"),
    ]
    for tid, name, col, walk, cat in data:
        ts.add(Tile(tid, name, col, walk, cat))
    return ts

# ============================================================================
# EventType
# ============================================================================
class EventType:
    def __init__(self, tag, label, color=(200,200,200),
                 image_path=None, is_preset=False):
        self.tag = tag; self.label = label
        self.color = tuple(color); self.image_path = image_path
        self.is_preset = is_preset
        self._img_cache = {}
    def get_surface(self, size):
        if not self.image_path: return None
        if size in self._img_cache: return self._img_cache[size]
        try:
            if not os.path.isfile(self.image_path):
                self._img_cache[size] = None; return None
            img = pygame.image.load(self.image_path).convert_alpha()
            scaled = pygame.transform.smoothscale(img, (size, size))
            self._img_cache[size] = scaled; return scaled
        except Exception:
            self._img_cache[size] = None; return None
    def clear_cache(self): self._img_cache = {}
    def to_dict(self):
        return {"tag": self.tag, "label": self.label,
                "color": list(self.color), "image_path": self.image_path,
                "is_preset": self.is_preset}
    @classmethod
    def from_dict(cls, d):
        return cls(d["tag"], d["label"], tuple(d.get("color", (200,200,200))),
                   d.get("image_path"), d.get("is_preset", False))

def default_event_types():
    return [
        EventType("player_spawn", "Player Spawn", (100, 220, 255), is_preset=True),
        EventType("npc",          "NPC",          (240, 200, 80),  is_preset=True),
        EventType("chest",        "Baú",          (180, 140, 70),  is_preset=True),
        EventType("teleport",     "Teleporte",    (200, 130, 240), is_preset=True),
        EventType("trigger",      "Trigger",      (230, 100, 100), is_preset=True),
        EventType("save_point",   "Save Point",   (110, 220, 110), is_preset=True),
    ]

# ============================================================================
# GameEvent
# ============================================================================
class GameEvent:
    def __init__(self, tag, x, y, eid=0, data=None):
        self.tag = tag; self.x = x; self.y = y
        self.id = eid; self.data = data or {}
    def to_dict(self):
        return {"tag": self.tag, "x": self.x, "y": self.y,
                "id": self.id, "data": dict(self.data)}
    @classmethod
    def from_dict(cls, d):
        return cls(d.get("tag", d.get("type", "npc")),
                   d["x"], d["y"], d.get("id", 0), d.get("data"))

# ============================================================================
# TileMap
# ============================================================================
class TileMap:
    def __init__(self, name="novo_mapa", w=30, h=20):
        self.name = name; self.w = w; self.h = h
        self.data = [[[None] * LAYERS for _ in range(w)] for _ in range(h)]
        self.passability = {}
        self.events = []
        self.parent = None

    def in_bounds(self, x, y): return 0 <= x < self.w and 0 <= y < self.h
    def get_layer(self, x, y, layer):
        if self.in_bounds(x, y) and 0 <= layer < LAYERS:
            return self.data[y][x][layer]
        return None
    def set_layer(self, x, y, layer, tid):
        if self.in_bounds(x, y) and 0 <= layer < LAYERS:
            self.data[y][x][layer] = tid
    def get_top(self, x, y):
        if not self.in_bounds(x, y): return None
        for l in reversed(range(LAYERS)):
            if self.data[y][x][l] is not None: return self.data[y][x][l]
        return None
    def is_empty(self, x, y):
        if not self.in_bounds(x, y): return True
        for l in range(LAYERS):
            if self.data[y][x][l] is not None: return False
        return True
    def tile_walkable_default(self, x, y, tileset):
        tid = self.get_top(x, y)
        if tid is None: return False
        t = tileset.get(tid)
        return t.walkable if t else False
    def is_walkable(self, x, y, tileset):
        if not self.in_bounds(x, y): return False
        v = self.passability.get((x, y), None)
        if v is True or v == "ok" or v == "above": return True
        if v is False or v == "block": return False
        return self.tile_walkable_default(x, y, tileset)
    def is_above(self, x, y):
        return self.passability.get((x, y)) == "above"
    def set_passability(self, x, y, value):
        if not self.in_bounds(x, y): return
        if value is None: self.passability.pop((x, y), None)
        else: self.passability[(x, y)] = value

    def event_at(self, x, y):
        for ev in self.events:
            if ev.x == x and ev.y == y: return ev
        return None
    def remove_event(self, ev):
        self.events = [e for e in self.events if e is not ev]
    def next_event_id(self):
        used = {ev.id for ev in self.events}
        i = 1
        while i in used: i += 1
        return i

    def resize(self, nw, nh):
        nd = [[[None] * LAYERS for _ in range(nw)] for _ in range(nh)]
        for y in range(min(self.h, nh)):
            for x in range(min(self.w, nw)):
                nd[y][x] = list(self.data[y][x])
        self.data = nd; self.w, self.h = nw, nh
        self.passability = {(x, y): v for (x, y), v in self.passability.items()
                            if 0 <= x < nw and 0 <= y < nh}
        self.events = [ev for ev in self.events
                       if 0 <= ev.x < nw and 0 <= ev.y < nh]

    def to_dict(self):
        pass_out = []
        for (x, y), v in self.passability.items():
            if v is True: pass_out.append([x, y, "ok"])
            elif v is False: pass_out.append([x, y, "block"])
            elif v == "above": pass_out.append([x, y, "above"])
            elif v == "ok": pass_out.append([x, y, "ok"])
            elif v == "block": pass_out.append([x, y, "block"])
        return {"name": self.name, "w": self.w, "h": self.h,
                "parent": self.parent, "data": self.data,
                "passability": pass_out,
                "events": [ev.to_dict() for ev in self.events]}

    @classmethod
    def from_dict(cls, d):
        m = cls(d["name"], d["w"], d["h"])
        m.parent = d.get("parent")
        raw = d["data"]
        for y in range(m.h):
            for x in range(m.w):
                v = raw[y][x]
                if isinstance(v, list):
                    m.data[y][x] = list(v)[:LAYERS] + [None]*(LAYERS - len(v))
                elif v is None:
                    m.data[y][x] = [None]*LAYERS
                else:
                    m.data[y][x] = [v] + [None]*(LAYERS-1)
        for entry in d.get("passability", []):
            if len(entry) >= 3:
                x, y, v = entry
                if isinstance(v, bool): v = "ok" if v else "block"
                m.passability[(x, y)] = v
        for evd in d.get("events", []):
            m.events.append(GameEvent.from_dict(evd))
        return m

# ============================================================================
# Project
# ============================================================================
class Project:
    def __init__(self):
        self.tileset = default_tileset()
        self.event_types = {}
        for et in default_event_types(): self.event_types[et.tag] = et
        self.maps = {}
        self.active_map_name = None
        m = TileMap("mapa_inicial", 30, 20)
        for y in range(20):
            for x in range(30):
                if x < 8: m.set_layer(x, y, 0, "grass")
                elif x < 15: m.set_layer(x, y, 0, "grass_dark")
                elif x < 22: m.set_layer(x, y, 0, "dirt")
                else: m.set_layer(x, y, 0, "stone_floor")
        self.maps[m.name] = m
        self.active_map_name = m.name
    def active_map(self): return self.maps.get(self.active_map_name)
    def add_map(self, m):
        self.maps[m.name] = m; self.active_map_name = m.name
    def unique_map_name(self, base):
        if base not in self.maps: return base
        i = 1
        while f"{base}_{i}" in self.maps: i += 1
        return f"{base}_{i}"
    def children_of(self, parent_name):
        return [n for n, m in self.maps.items() if m.parent == parent_name]
    def roots(self):
        return [n for n, m in self.maps.items() if m.parent is None]
    def unique_event_tag(self, base="custom"):
        i = 1
        while f"{base}_{i}" in self.event_types: i += 1
        return f"{base}_{i}"
    def to_dict(self):
        return {"tileset": self.tileset.to_dict(),
                "event_types": [et.to_dict() for et in self.event_types.values()],
                "maps": {n: m.to_dict() for n, m in self.maps.items()},
                "active_map_name": self.active_map_name}
    @classmethod
    def from_dict(cls, d):
        p = cls.__new__(cls)
        p.tileset = TileSet.from_dict(d["tileset"])
        p.event_types = {}
        if "event_types" in d:
            for etd in d["event_types"]:
                et = EventType.from_dict(etd); p.event_types[et.tag] = et
        else:
            for et in default_event_types(): p.event_types[et.tag] = et
        p.maps = {n: TileMap.from_dict(md) for n, md in d["maps"].items()}
        p.active_map_name = d.get("active_map_name")
        if not p.maps: p.add_map(TileMap("mapa_inicial"))
        if p.active_map_name not in p.maps:
            p.active_map_name = next(iter(p.maps))
        return p

# ============================================================================
# Tools
# ============================================================================
TOOL_BRUSH = "brush"; TOOL_ERASER = "eraser"; TOOL_FILL = "fill"
TOOL_RECT = "rect"; TOOL_PICKER = "picker"

def flood_fill_layer(map_obj, x, y, layer, new_tid):
    if not map_obj.in_bounds(x, y): return
    old = map_obj.get_layer(x, y, layer)
    if old == new_tid: return
    queue = [(x, y)]; visited = set()
    while queue:
        cx, cy = queue.pop()
        if (cx, cy) in visited: continue
        if not map_obj.in_bounds(cx, cy): continue
        if map_obj.get_layer(cx, cy, layer) != old: continue
        visited.add((cx, cy))
        map_obj.set_layer(cx, cy, layer, new_tid)
        queue.append((cx+1, cy)); queue.append((cx-1, cy))
        queue.append((cx, cy+1)); queue.append((cx, cy-1))

# ============================================================================
# App
# ============================================================================
class MapEditorApp:
    MODE_MAP = "map"; MODE_TILES = "tiles"
    MODE_PASS = "pass"; MODE_EVENTS = "events"
    MODE_ORDER = [MODE_MAP, MODE_TILES, MODE_PASS, MODE_EVENTS]
    MODE_LABELS = {MODE_MAP:"Mapa", MODE_TILES:"Tiles",
                   MODE_PASS:"Passabilidade", MODE_EVENTS:"Eventos"}
    FIELD_PREFIX_BY_MODE = {
        MODE_MAP: ("map_", "quick_size"),
        MODE_TILES: ("tile_",),
        MODE_EVENTS: ("ev_", "et_"),
        MODE_PASS: (),
    }

    def __init__(self):
        self.running = True
        self.project = Project()
        self.mode = self.MODE_MAP
        self.tool = TOOL_BRUSH
        self.active_layer = 0

        self.cell = 32.0
        self.cam = [0.0, 0.0]
        self.cam_speed = 500.0

        self.selected_tile_id = (self.project.tileset.order[0]
                                 if self.project.tileset.order else None)
        self.selected_category = "Todos"
        self.hover_cell = None

        self.pass_mode = "ok"

        self.dragging_paint = False
        self.dragging_pass = None
        self.rect_start = None; self.rect_end = None

        self.undo_stack = []; self.redo_stack = []
        self.autosave_dirty = False; self.autosave_timer = 0.0

        self.focused_field = None; self.fields = {}
        self._init_fields()

        self.msg = ""; self.msg_timer = 0.0; self.msg_color = ACCENT
        self.save_dialog = SaveDialog()
        self.rename_dialog = InputDialog()
        self.ctx_menu = ContextMenu()

        self.selected_event_tag = None
        self.editing_event = None
        self.editing_event_type = None
        self.last_right_panel = None

        self.dragging_map_name = None

        self._right_hits = []
        self._left_hits  = []
        self._top_hits   = []

        self.show_grid = True
        self._sync_fields_from_map()
        self._recenter()

        if self.project.event_types:
            self.selected_event_tag = next(iter(self.project.event_types))

        if os.path.isfile(AUTOSAVE_PATH):
            self._load_autosave()

    # ------------------------------------------------------------------
    def _init_fields(self):
        for k, lbl in [("tile_name","Nome"),("tile_category","Categoria"),
                       ("tile_color","Cor (hex)"),("tile_image","Imagem")]:
            self.fields[k] = TextField(k, lbl, "", max_len=200)
        for k, lbl in [("map_name","Nome do mapa"),("map_w","Largura"),
                       ("map_h","Altura")]:
            self.fields[k] = TextField(k, lbl, "", max_len=32)
        self.fields["quick_size"] = TextField("quick_size", "Rápido (ex: 5x5)", "", max_len=16)
        self.fields["ev_id"] = TextField("ev_id", "ID (int)", "", max_len=32)
        self.fields["ev_name"] = TextField("ev_name", "Nome (opcional)", "", max_len=64)
        for i in range(1, 7):
            self.fields[f"ev_k{i}"] = TextField(f"ev_k{i}", f"chave{i}", "", max_len=40)
            self.fields[f"ev_v{i}"] = TextField(f"ev_v{i}", f"valor{i}", "", max_len=200)
        for k, lbl in [("et_tag","Tag (id no jogo)"),("et_label","Rótulo"),
                       ("et_color","Cor (hex)"),("et_image","Imagem")]:
            self.fields[k] = TextField(k, lbl, "", max_len=200)

    def _msg(self, text, color=ACCENT):
        self.msg = text; self.msg_color = color; self.msg_timer = 2.5

    def _canvas_rect(self): return pygame.Rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H)
    def _in_canvas(self, pos): return self._canvas_rect().collidepoint(pos)
    def _in_right_panel(self, pos): return pos[0] >= WIDTH - RIGHT_W
    def _in_left_panel(self, pos):
        return 0 <= pos[0] < LEFT_W and TOP_H <= pos[1] < HEIGHT - BOTTOM_H
    def _in_top_bar(self, pos): return pos[1] < TOP_H

    def _recenter(self):
        m = self.project.active_map()
        if not m: return
        self.cam[0] = m.w * self.cell / 2 - CANVAS_W / 2
        self.cam[1] = m.h * self.cell / 2 - CANVAS_H / 2

    def _clamp_cam(self):
        m = self.project.active_map()
        if not m: return
        ww = m.w * self.cell; wh = m.h * self.cell
        self.cam[0] = clamp(self.cam[0], -CANVAS_W*0.5, ww - CANVAS_W*0.5)
        self.cam[1] = clamp(self.cam[1], -CANVAS_H*0.5, wh - CANVAS_H*0.5)

    def _screen_to_world(self, sx, sy):
        return (sx - CANVAS_X + self.cam[0], sy - CANVAS_Y + self.cam[1])

    # --- undo/redo ---
    def _snapshot(self):
        m = self.project.active_map()
        if not m: return None
        return {"map": m.name,
                "data": [[list(c) for c in row] for row in m.data],
                "pass": dict(m.passability),
                "events": [ev.to_dict() for ev in m.events],
                "w": m.w, "h": m.h}
    def _push_undo(self):
        snap = self._snapshot()
        if snap is None: return
        self.undo_stack.append(snap)
        if len(self.undo_stack) > 40: self.undo_stack = self.undo_stack[-40:]
        self.redo_stack.clear()
    def _restore(self, snap):
        m = self.project.maps.get(snap["map"])
        if not m: m = self.project.active_map()
        if not m: return
        m.data = [[list(c) for c in row] for row in snap["data"]]
        m.passability = dict(snap["pass"])
        m.events = [GameEvent.from_dict(ev) for ev in snap["events"]]
        m.w = snap["w"]; m.h = snap["h"]
    def _do_undo(self):
        if not self.undo_stack: self._msg("Nada para desfazer.", TEXT_DIM); return
        self.redo_stack.append(self._snapshot())
        self._restore(self.undo_stack.pop())
        self._mark_dirty(); self._msg("Desfeito.", TEXT_DIM)
    def _do_redo(self):
        if not self.redo_stack: self._msg("Nada para refazer.", TEXT_DIM); return
        self.undo_stack.append(self._snapshot())
        self._restore(self.redo_stack.pop())
        self._mark_dirty(); self._msg("Refeito.", TEXT_DIM)

    # --- autosave ---
    def _mark_dirty(self):
        self.autosave_dirty = True; self.autosave_timer = 0.5
    def _do_autosave(self):
        try:
            with open(AUTOSAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.project.to_dict(), f, ensure_ascii=False)
        except Exception: pass
    def _load_autosave(self):
        try:
            with open(AUTOSAVE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.project = Project.from_dict(data)
            self.selected_tile_id = (self.project.tileset.order[0]
                                     if self.project.tileset.order else None)
            self._sync_fields_from_map(); self._recenter()
            if self.project.event_types:
                self.selected_event_tag = next(iter(self.project.event_types))
            self._msg("Autosave carregado.", TEXT_DIM)
        except Exception: pass

    # --- sync ---
    def _sync_fields_from_map(self):
        m = self.project.active_map()
        if not m: return
        self.fields["map_name"].value = m.name
        self.fields["map_w"].value = str(m.w)
        self.fields["map_h"].value = str(m.h)
        self.fields["quick_size"].value = f"{m.w}x{m.h}"
    def _sync_fields_from_tile(self):
        tid = self.selected_tile_id
        if not tid: return
        t = self.project.tileset.get(tid)
        if not t: return
        self.fields["tile_name"].value = t.name
        self.fields["tile_category"].value = t.category
        self.fields["tile_color"].value = color_to_hex(t.color)
        self.fields["tile_image"].value = t.image_path or ""
    def _sync_fields_from_event(self, ev):
        self.editing_event = ev
        if not ev: return
        self.last_right_panel = "event"
        self.fields["ev_id"].value = str(ev.id)
        self.fields["ev_name"].value = str(ev.data.get("name", ""))
        for i in range(1, 7):
            self.fields[f"ev_k{i}"].value = ""
            self.fields[f"ev_v{i}"].value = ""
        items = [(k, v) for k, v in ev.data.items() if k != "name"]
        for i, (k, v) in enumerate(items):
            if i >= 6: break
            self.fields[f"ev_k{i+1}"].value = str(k)
            self.fields[f"ev_v{i+1}"].value = str(v)
    def _sync_fields_from_event_type(self, et):
        self.editing_event_type = et
        if not et: return
        self.last_right_panel = "event_type"
        self.fields["et_tag"].value = et.tag
        self.fields["et_label"].value = et.label
        self.fields["et_color"].value = color_to_hex(et.color)
        self.fields["et_image"].value = et.image_path or ""

    # --- aplicar ---
    def _apply_tile_fields(self):
        tid = self.selected_tile_id
        if not tid: return
        t = self.project.tileset.get(tid)
        if not t: return
        t.name = self.fields["tile_name"].value.strip() or t.id
        t.category = self.fields["tile_category"].value.strip() or "Geral"
        t.color = parse_hex_color(self.fields["tile_color"].value, t.color)
        img = self.fields["tile_image"].value.strip()
        if img != (t.image_path or ""):
            t.image_path = img or None; t.clear_cache()
        self._mark_dirty(); self._msg("Tile atualizado.", SUCCESS)
    def _apply_map_fields(self):
        m = self.project.active_map()
        if not m: return
        old_name = m.name
        new_name = self.fields["map_name"].value.strip() or m.name
        try: nw = int(self.fields["map_w"].value); nh = int(self.fields["map_h"].value)
        except Exception: nw, nh = m.w, m.h
        nw = clamp(nw, 4, 300); nh = clamp(nh, 4, 300)
        if (nw, nh) != (m.w, m.h):
            self._push_undo(); m.resize(nw, nh)
            self._msg(f"Redimensionado: {nw}x{nh}", SUCCESS)
        if new_name != old_name:
            del self.project.maps[old_name]
            m.name = self.project.unique_map_name(new_name)
            self.project.maps[m.name] = m
            for child in self.project.maps.values():
                if child.parent == old_name: child.parent = m.name
            self.project.active_map_name = m.name
        self._mark_dirty(); self._sync_fields_from_map()
    def _apply_event_fields(self):
        ev = self.editing_event
        if not ev: return
        try: ev.id = int(self.fields["ev_id"].value or 0)
        except Exception: pass
        new_data = {}
        name = self.fields["ev_name"].value.strip()
        if name: new_data["name"] = name
        for i in range(1, 7):
            k = self.fields[f"ev_k{i}"].value.strip()
            v = self.fields[f"ev_v{i}"].value.strip()
            if k and k != "name":
                try:
                    if "." in v: v = float(v)
                    else: v = int(v)
                except Exception: pass
                new_data[k] = v
        ev.data = new_data
        self._mark_dirty(); self._msg("Evento atualizado.", SUCCESS)
    def _apply_event_type_fields(self):
        et = self.editing_event_type
        if not et: return
        new_tag = self.fields["et_tag"].value.strip()
        if not new_tag:
            self._msg("Tag não pode ser vazia.", DANGER); return
        if new_tag != et.tag:
            if new_tag in self.project.event_types:
                self._msg("Já existe uma tag com esse nome.", DANGER); return
            old_tag = et.tag
            del self.project.event_types[old_tag]
            et.tag = new_tag
            self.project.event_types[new_tag] = et
            for m in self.project.maps.values():
                for ev in m.events:
                    if ev.tag == old_tag: ev.tag = new_tag
            if self.selected_event_tag == old_tag:
                self.selected_event_tag = new_tag
        et.label = self.fields["et_label"].value.strip() or et.tag
        et.color = parse_hex_color(self.fields["et_color"].value, et.color)
        img = self.fields["et_image"].value.strip()
        if img != (et.image_path or ""):
            et.image_path = img or None; et.clear_cache()
        self._mark_dirty(); self._msg("Tipo de evento atualizado.", SUCCESS)
    def _apply_quick_size(self):
        m = self.project.active_map()
        if not m: return
        s = self.fields["quick_size"].value.strip().lower()
        if "x" not in s:
            self._msg("Formato inválido. Use algo como 10x25", DANGER); return
        try:
            a, b = s.split("x")
            nw = clamp(int(a), 4, 300); nh = clamp(int(b), 4, 300)
        except Exception:
            self._msg("Formato inválido.", DANGER); return
        if (nw, nh) != (m.w, m.h):
            self._push_undo(); m.resize(nw, nh)
            self._mark_dirty(); self._sync_fields_from_map()
            self._msg(f"Redimensionado: {nw}x{nh}", SUCCESS)
    def _apply_current_field_group(self):
        f = self.focused_field
        if not f: return
        if f.key == "quick_size": self._apply_quick_size()
        elif f.key.startswith("tile_"): self._apply_tile_fields()
        elif f.key.startswith("ev_"): self._apply_event_fields()
        elif f.key.startswith("et_"): self._apply_event_type_fields()
        elif f.key.startswith("map_"): self._apply_map_fields()

    # --- save/load ---
    def _open_save_dialog(self): self.save_dialog.open("meu_projeto")
    def _do_save_as(self):
        name = self.save_dialog.text.strip() or "meu_projeto"
        safe = "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "meu_projeto"
        fp = os.path.join(EXPORTS_DIR, f"{safe}.json")
        try:
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(self.project.to_dict(), f, indent=2, ensure_ascii=False)
            self._msg(f"Salvo: {safe}.json", SUCCESS)
        except Exception as ex: self._msg(f"Erro: {ex}", DANGER)
    def _load_project_dialog(self):
        files = sorted([f for f in os.listdir(EXPORTS_DIR)
                        if f.endswith(".json") and not f.startswith("_")])
        if not files: self._msg("Nenhum projeto salvo.", DANGER); return
        fp = os.path.join(EXPORTS_DIR, files[-1])
        try:
            with open(fp, "r", encoding="utf-8") as f:
                self.project = Project.from_dict(json.load(f))
            self.selected_tile_id = (self.project.tileset.order[0]
                                     if self.project.tileset.order else None)
            self._sync_fields_from_map(); self._recenter()
            if self.project.event_types:
                self.selected_event_tag = next(iter(self.project.event_types))
            self._msg(f"Carregado: {files[-1]}", SUCCESS)
        except Exception as ex: self._msg(f"Erro: {ex}", DANGER)

    # --- mapas ---
    def _switch_map(self, name):
        if name not in self.project.maps: return
        self.project.active_map_name = name
        self._sync_fields_from_map(); self._recenter()
        self._msg(f"Mapa: {name}", ACCENT)
    def _new_map(self, parent=None):
        name = self.project.unique_map_name("mapa")
        m = TileMap(name, 30, 20); m.parent = parent
        self.project.add_map(m)
        self._sync_fields_from_map(); self._recenter(); self._mark_dirty()
        self._msg(f"Novo mapa: {name}", ACCENT)
    def _dup_map(self):
        m = self.project.active_map()
        if not m: return
        name = self.project.unique_map_name(m.name + "_copy")
        m2 = TileMap.from_dict(m.to_dict())
        m2.name = name; m2.parent = m.parent
        self.project.add_map(m2); self._mark_dirty()
        self._msg(f"Duplicado: {name}", ACCENT)
    def _del_map(self, name=None):
        name = name or self.project.active_map_name
        if len(self.project.maps) <= 1:
            self._msg("Não pode remover o último mapa.", DANGER); return
        for m in self.project.maps.values():
            if m.parent == name: m.parent = None
        del self.project.maps[name]
        self.project.active_map_name = next(iter(self.project.maps))
        self._sync_fields_from_map(); self._recenter(); self._mark_dirty()
        self._msg(f"Removido: {name}", TEXT_DIM)
    def _open_rename_dialog(self, name):
        m = self.project.maps.get(name)
        if not m: return
        def do_rename(new_name):
            new_name = new_name.strip()
            if not new_name or new_name == name: return
            del self.project.maps[name]
            m.name = self.project.unique_map_name(new_name)
            self.project.maps[m.name] = m
            for child in self.project.maps.values():
                if child.parent == name: child.parent = m.name
            if self.project.active_map_name == name:
                self.project.active_map_name = m.name
            self._mark_dirty(); self._sync_fields_from_map()
            self._msg(f"Renomeado para: {m.name}", SUCCESS)
        self.rename_dialog.open("RENOMEAR MAPA",
                                "Digite o novo nome:", name, do_rename)
    def _move_map_to(self, child_name, parent_name):
        if child_name == parent_name: return
        cur = parent_name
        while cur is not None:
            if cur == child_name:
                self._msg("Não pode criar ciclo.", DANGER); return
            cur = self.project.maps[cur].parent if cur in self.project.maps else None
        self.project.maps[child_name].parent = parent_name
        self._mark_dirty()
        self._msg(f"{child_name} → filho de {parent_name}", SUCCESS)

    # --- tiles ---
    def _new_tile(self):
        tid = self.project.tileset.unique_id("tile")
        self.project.tileset.add(Tile(tid, "Novo tile", (150,150,150), True, "Geral"))
        self.selected_tile_id = tid
        self._sync_fields_from_tile(); self._mark_dirty()
        self._msg(f"Tile criado: {tid}", ACCENT)
    def _dup_tile(self):
        tid = self.selected_tile_id
        if not tid: return
        t = self.project.tileset.get(tid)
        if not t: return
        new_id = self.project.tileset.unique_id(t.id)
        self.project.tileset.add(Tile(new_id, t.name+" copy", t.color,
                                      t.walkable, t.category, t.image_path))
        self.selected_tile_id = new_id
        self._sync_fields_from_tile(); self._mark_dirty()
        self._msg(f"Duplicado: {new_id}", ACCENT)
    def _del_tile(self):
        tid = self.selected_tile_id
        if not tid: return
        if len(self.project.tileset.tiles) <= 1:
            self._msg("Não pode remover o último tile.", DANGER); return
        self.project.tileset.remove(tid)
        for m in self.project.maps.values():
            for y in range(m.h):
                for x in range(m.w):
                    for l in range(LAYERS):
                        if m.data[y][x][l] == tid: m.data[y][x][l] = None
        self.selected_tile_id = (self.project.tileset.order[0]
                                 if self.project.tileset.order else None)
        self._sync_fields_from_tile(); self._mark_dirty()
        self._msg("Tile removido.", TEXT_DIM)
    def _toggle_walkable(self):
        t = self.project.tileset.get(self.selected_tile_id)
        if t:
            t.walkable = not t.walkable
            self._mark_dirty(); self._msg(f"{t.id}: walkable={t.walkable}", ACCENT)
    def _pick_tile_image(self):
        path = pick_image_file()
        if not path: return
        self.fields["tile_image"].value = path
        self._apply_tile_fields(); self._msg("Sprite carregado.", SUCCESS)
    def _clear_tile_image(self):
        self.fields["tile_image"].value = ""
        self._apply_tile_fields(); self._msg("Sprite removido.", TEXT_DIM)

    # --- event types ---
    def _new_event_type(self):
        tag = self.project.unique_event_tag("custom")
        et = EventType(tag, tag, (200, 200, 200))
        self.project.event_types[tag] = et
        self.selected_event_tag = tag
        self._sync_fields_from_event_type(et)
        self._mark_dirty()
        self._msg(f"Tipo criado: {tag}", ACCENT)
    def _dup_event_type(self):
        et = self.project.event_types.get(self.selected_event_tag)
        if not et: return
        tag = self.project.unique_event_tag(et.tag + "_copy")
        net = EventType(tag, et.label + " copy", et.color, et.image_path, False)
        self.project.event_types[tag] = net
        self.selected_event_tag = tag
        self._sync_fields_from_event_type(net)
        self._mark_dirty()
        self._msg(f"Duplicado: {tag}", ACCENT)
    def _del_event_type(self):
        tag = self.selected_event_tag
        et = self.project.event_types.get(tag)
        if not et: return
        if et.is_preset:
            self._msg("Presets não podem ser deletados.", DANGER); return
        for m in self.project.maps.values():
            m.events = [ev for ev in m.events if ev.tag != tag]
        del self.project.event_types[tag]
        self.selected_event_tag = (next(iter(self.project.event_types))
                                   if self.project.event_types else None)
        if self.selected_event_tag:
            self._sync_fields_from_event_type(
                self.project.event_types[self.selected_event_tag])
        self._mark_dirty(); self._msg("Tipo removido.", TEXT_DIM)
    def _del_event_type_tag(self, tag):
        et = self.project.event_types.get(tag)
        if not et or et.is_preset: return
        for m in self.project.maps.values():
            m.events = [ev for ev in m.events if ev.tag != tag]
        del self.project.event_types[tag]
        if self.selected_event_tag == tag:
            self.selected_event_tag = (next(iter(self.project.event_types))
                                       if self.project.event_types else None)
        self._mark_dirty(); self._msg("Tipo removido.", TEXT_DIM)
    def _pick_event_image(self):
        path = pick_image_file()
        if not path: return
        self.fields["et_image"].value = path
        self._apply_event_type_fields(); self._msg("Sprite carregado.", SUCCESS)
    def _clear_event_image(self):
        self.fields["et_image"].value = ""
        self._apply_event_type_fields(); self._msg("Sprite removido.", TEXT_DIM)

    # --- eventos ---
    def _dup_event(self, ev):
        m = self.project.active_map()
        if not m: return
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                nx, ny = ev.x + dx, ev.y + dy
                if 0 <= nx < m.w and 0 <= ny < m.h and not m.event_at(nx, ny):
                    new_ev = GameEvent(ev.tag, nx, ny, eid=m.next_event_id(),
                                       data=dict(ev.data))
                    m.events.append(new_ev); self._mark_dirty()
                    self._msg("Evento duplicado.", ACCENT); return
        self._msg("Sem espaço próximo.", DANGER)
    def _del_event(self, ev):
        m = self.project.active_map()
        if not m: return
        self._push_undo()
        m.remove_event(ev)
        if self.editing_event is ev:
            self.editing_event = None
            self.last_right_panel = None
        self._mark_dirty(); self._msg("Evento deletado.", TEXT_DIM)

    # ------------------------------------------------------------------
    # Eventos pygame
    # ------------------------------------------------------------------
    def handle_events(self, events):
        for e in events:
            if e.type == pygame.QUIT:
                self.running = False; return

            if self.rename_dialog.active:
                self.rename_dialog.handle_event(e); continue
            if self.save_dialog.active:
                act = self.save_dialog.handle_event(e)
                if act == "save": self._do_save_as(); self.save_dialog.close()
                elif act == "cancel": self.save_dialog.close()
                continue
            if self.ctx_menu.active:
                cb = self.ctx_menu.handle_event(e)
                if cb: cb()
                continue

            if self.focused_field:
                if e.type == pygame.KEYDOWN:
                    if self.focused_field.handle_key(e):
                        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            self._apply_current_field_group()
                        continue
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if not self.focused_field.rect.collidepoint(e.pos):
                        self._apply_current_field_group()
                        self.focused_field.focused = False
                        self.focused_field = None

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False; return
                if e.key == pygame.K_TAB:
                    idx = self.MODE_ORDER.index(self.mode)
                    self.mode = self.MODE_ORDER[(idx+1) % len(self.MODE_ORDER)]
                    if self.mode == self.MODE_TILES: self._sync_fields_from_tile()
                if e.key == pygame.K_g: self.show_grid = not self.show_grid
                if e.key == pygame.K_z and (e.mod & pygame.KMOD_CTRL): self._do_undo()
                if e.key == pygame.K_y and (e.mod & pygame.KMOD_CTRL): self._do_redo()
                if self.mode == self.MODE_MAP:
                    if e.key == pygame.K_b: self.tool = TOOL_BRUSH
                    if e.key == pygame.K_e: self.tool = TOOL_ERASER
                    if e.key == pygame.K_f: self.tool = TOOL_FILL
                    if e.key == pygame.K_r: self.tool = TOOL_RECT
                    if e.key == pygame.K_p: self.tool = TOOL_PICKER
                    if e.key == pygame.K_1: self.active_layer = 0
                    if e.key == pygame.K_2: self.active_layer = 1
                    if e.key == pygame.K_3: self.active_layer = 2
                    if e.key == pygame.K_4: self.active_layer = 3
                    if e.key == pygame.K_s: self._open_save_dialog()
                    if e.key == pygame.K_l: self._load_project_dialog()

            if e.type == pygame.MOUSEWHEEL:
                if self._in_canvas(pygame.mouse.get_pos()):
                    self._zoom_at(pygame.mouse.get_pos(), e.y)

            if e.type == pygame.MOUSEMOTION:
                self._on_motion(e.pos)

            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1: self._on_left_down(e.pos)
                elif e.button == 3: self._on_right_down(e.pos)
            if e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1: self._on_left_up(e.pos)
                elif e.button == 3: self._on_right_up(e.pos)

    def _zoom_at(self, mouse_pos, delta):
        old = self.cell
        new = clamp(old * (1.15 ** delta), 8.0, 96.0)
        if abs(new - old) < 0.01: return
        wx = (mouse_pos[0] - CANVAS_X + self.cam[0]) / self.cell
        wy = (mouse_pos[1] - CANVAS_Y + self.cam[1]) / self.cell
        self.cell = new
        self.cam[0] = wx * new - (mouse_pos[0] - CANVAS_X)
        self.cam[1] = wy * new - (mouse_pos[1] - CANVAS_Y)
        self._clamp_cam()

    def _on_motion(self, pos):
        if self._in_canvas(pos):
            wx, wy = self._screen_to_world(pos[0], pos[1])
            gx = int(wx // self.cell); gy = int(wy // self.cell)
            m = self.project.active_map()
            if m and m.in_bounds(gx, gy): self.hover_cell = (gx, gy)
            else: self.hover_cell = None
            if self.mode == self.MODE_MAP:
                if self.tool == TOOL_RECT and self.rect_start:
                    self.rect_end = self.hover_cell
                if self.dragging_paint and self.hover_cell:
                    self._paint_cell(self.hover_cell)
            elif self.mode == self.MODE_PASS:
                if self.dragging_pass and self.hover_cell:
                    self._pass_cell(self.hover_cell, self.dragging_pass)
        else:
            self.hover_cell = None

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    def _on_left_down(self, pos):
        for rect, cb in self._top_hits:
            if rect.collidepoint(pos): cb(); return
        for item in self._left_hits:
            rect, cb = item[0], item[1]
            if rect.collidepoint(pos): cb(); return
        if self._in_right_panel(pos):
            prefixes = self.FIELD_PREFIX_BY_MODE.get(self.mode, ())
            for key, f in self.fields.items():
                if not f.active_this_frame: continue
                if not any(key.startswith(p) for p in prefixes): continue
                if f.rect.collidepoint(pos):
                    if self.focused_field and self.focused_field is not f:
                        self._apply_current_field_group()
                    self.focused_field = f; f.focused = True
                    for k2, f2 in self.fields.items():
                        if f2 is not f: f2.focused = False
                    return
            for rect, cb in self._right_hits:
                if rect.collidepoint(pos): cb(); return
            return
        self._handle_canvas_left(pos)

    def _on_right_down(self, pos):
        if self._in_left_panel(pos):
            if self._handle_left_context_menu(pos): return
        self._handle_canvas_right(pos)

    def _on_left_up(self, pos):
        if self.dragging_map_name:
            for rect, name in self._map_list_hits_for_drag():
                if rect.collidepoint(pos) and name != self.dragging_map_name:
                    self._move_map_to(self.dragging_map_name, name); break
            self.dragging_map_name = None
        if self.mode == self.MODE_MAP:
            if self.tool == TOOL_RECT and self.rect_start and self.rect_end:
                m = self.project.active_map()
                if m:
                    x1, y1 = self.rect_start; x2, y2 = self.rect_end
                    xa, xb = sorted((x1, x2)); ya, yb = sorted((y1, y2))
                    for yy in range(ya, yb + 1):
                        for xx in range(xa, xb + 1):
                            m.set_layer(xx, yy, self.active_layer, self.selected_tile_id)
                    self._mark_dirty()
            self.rect_start = None; self.rect_end = None
        self.dragging_paint = False
        self.dragging_pass = None

    def _on_right_up(self, pos):
        self.dragging_pass = None

    def _map_list_hits_for_drag(self):
        out = []
        for item in self._left_hits:
            if len(item) >= 3 and item[2] == "map":
                out.append((item[0], item[1]))
        return out

    # ------------------------------------------------------------------
    # Context menu (RMB painel esquerdo)
    # ------------------------------------------------------------------
    def _handle_left_context_menu(self, pos):
        for item in self._left_hits:
            if len(item) < 3: continue
            rect, payload, kind = item
            if not rect.collidepoint(pos): continue
            if kind == "map":
                name = payload
                items = [
                    ("Renomear…", lambda n=name: self._open_rename_dialog(n)),
                    ("Deletar", lambda n=name: self._del_map(n)),
                ]
                others = [n for n in self.project.maps if n != name]
                if others:
                    sub = [(f"→ {p}", (lambda c=name, p=p: self._move_map_to(c, p)))
                           for p in others[:10]]
                    items.append(("Mover para…",
                                  lambda s=sub, p=pos: self.ctx_menu.open(
                                      (min(p[0]+180, WIDTH-220), p[1]), s)))
                self.ctx_menu.open(pos, items); return True
            if kind == "event_type":
                tag = payload
                et = self.project.event_types.get(tag)
                if et and not et.is_preset:
                    self.ctx_menu.open(pos, [("Deletar tipo",
                        lambda t=tag: self._del_event_type_tag(t))])
                return True
        return False

    # ------------------------------------------------------------------
    # Canvas
    # ------------------------------------------------------------------
    def _handle_canvas_left(self, pos):
        if not self._in_canvas(pos): return
        if self.hover_cell is None: return
        m = self.project.active_map()
        if not m: return

        if self.mode == self.MODE_MAP:
            if self.tool == TOOL_PICKER:
                tid = m.get_layer(*self.hover_cell, self.active_layer) \
                    or m.get_top(*self.hover_cell)
                if tid:
                    self.selected_tile_id = tid; self._sync_fields_from_tile()
                    self._msg(f"Selecionado: {tid}", ACCENT)
                return
            self._push_undo()
            if self.tool == TOOL_RECT:
                self.rect_start = self.hover_cell; self.rect_end = self.hover_cell
            elif self.tool == TOOL_FILL:
                flood_fill_layer(m, self.hover_cell[0], self.hover_cell[1],
                                 self.active_layer, self.selected_tile_id)
                self._mark_dirty()
            else:
                self.dragging_paint = True; self._paint_cell(self.hover_cell)
        elif self.mode == self.MODE_PASS:
            self._push_undo()
            self.dragging_pass = self.pass_mode
            self._pass_cell(self.hover_cell, self.pass_mode)
        elif self.mode == self.MODE_EVENTS:
            ev = m.event_at(*self.hover_cell)
            if ev:
                self._sync_fields_from_event(ev)
                self._msg(f"Evento id {ev.id} ({ev.tag})", ACCENT)
                return
            if not self.selected_event_tag:
                self._msg("Selecione um tipo de evento à esquerda.", WARN); return
            self._push_undo()
            new_ev = GameEvent(self.selected_event_tag, *self.hover_cell,
                               eid=m.next_event_id())
            m.events.append(new_ev)
            self._sync_fields_from_event(new_ev)
            self._mark_dirty()
            self._msg(f"Colocado: {new_ev.tag} (id {new_ev.id})", ACCENT)

    def _handle_canvas_right(self, pos):
        if not self._in_canvas(pos): return
        if self.hover_cell is None: return
        m = self.project.active_map()
        if not m: return
        if self.mode == self.MODE_MAP:
            self._push_undo()
            m.set_layer(*self.hover_cell, self.active_layer, None)
            self._mark_dirty()
        elif self.mode == self.MODE_PASS:
            self._push_undo()
            self.dragging_pass = "block"
            self._pass_cell(self.hover_cell, "block")
        elif self.mode == self.MODE_EVENTS:
            ev = m.event_at(*self.hover_cell)
            if ev:
                items = [
                    ("Editar", lambda e=ev: self._sync_fields_from_event(e)),
                    ("Duplicar", lambda e=ev: self._dup_event(e)),
                    ("Deletar",  lambda e=ev: self._del_event(e)),
                ]
                self.ctx_menu.open(pos, items)

    # ------------------------------------------------------------------
    def _paint_cell(self, cell):
        m = self.project.active_map()
        if not m: return
        if self.tool == TOOL_ERASER:
            m.set_layer(cell[0], cell[1], self.active_layer, None)
        elif self.tool == TOOL_BRUSH:
            m.set_layer(cell[0], cell[1], self.active_layer, self.selected_tile_id)
        self._mark_dirty()
    def _pass_cell(self, cell, mode):
        m = self.project.active_map()
        if not m: return
        if mode == "ok": m.set_passability(cell[0], cell[1], "ok")
        elif mode == "block": m.set_passability(cell[0], cell[1], "block")
        elif mode == "above": m.set_passability(cell[0], cell[1], "above")
        elif mode == "clear": m.set_passability(cell[0], cell[1], None)
        self._mark_dirty()
    def _quick_resize(self, dw, dh):
        m = self.project.active_map()
        if not m: return
        nw = clamp(m.w + dw, 4, 300); nh = clamp(m.h + dh, 4, 300)
        if (nw, nh) != (m.w, m.h):
            self._push_undo(); m.resize(nw, nh); self._mark_dirty()
            self._sync_fields_from_map()
            self._msg(f"{nw}x{nh}", ACCENT)
    def _clear_all_passability(self):
        m = self.project.active_map()
        if not m: return
        self._push_undo(); m.passability.clear(); self._mark_dirty()
        self._msg("Passability limpa.", TEXT_DIM)

    # ------------------------------------------------------------------
    def update(self, dt):
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0: self.msg = ""
        if self.autosave_dirty:
            self.autosave_timer -= dt
            if self.autosave_timer <= 0:
                self._do_autosave(); self.autosave_dirty = False
        if self.save_dialog.active or self.rename_dialog.active: return
        if self.focused_field: return
        keys = pygame.key.get_pressed()
        speed = self.cam_speed * (2.5 if (keys[pygame.K_LSHIFT] or
                                          keys[pygame.K_RSHIFT]) else 1.0)
        dx = dy = 0.0
        if keys[pygame.K_a]: dx -= 1
        if keys[pygame.K_d]: dx += 1
        if keys[pygame.K_w]: dy -= 1
        if keys[pygame.K_s]: dy += 1
        if dx or dy:
            n = (dx*dx + dy*dy) ** 0.5
            self.cam[0] += dx / n * speed * dt
            self.cam[1] += dy / n * speed * dt
            self._clamp_cam()

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------
    def draw(self):
        screen.fill(BG)
        self._right_hits = []
        self._left_hits = []
        self._top_hits = []
        for f in self.fields.values(): f.mark_inactive()

        self._draw_top_bar()
        self._draw_canvas()
        self._draw_left_panel()
        self._draw_right_panel()
        self._draw_bottom_bar()

        self.save_dialog.draw(screen)
        self.rename_dialog.draw(screen)
        self.ctx_menu.draw(screen)
        self._draw_msg()
        pygame.display.flip()

    def _draw_top_bar(self):
        r = pygame.Rect(0, 0, WIDTH, TOP_H)
        pygame.draw.rect(screen, PANEL_BG, r)
        pygame.draw.line(screen, PANEL_BORDER, (0, TOP_H), (WIDTH, TOP_H))
        x = 8
        for mode in self.MODE_ORDER:
            label = self.MODE_LABELS[mode]
            tw = max(72, FONT_M.size(label)[0] + 20)
            rect = pygame.Rect(x, 6, tw, TOP_H-12)
            draw_button(screen, rect, label, FONT_M, active=(self.mode == mode))
            self._top_hits.append((rect, (lambda mm=mode: self._switch_mode(mm))))
            x += tw + 4
        x = 480
        for label, cb in [("Novo mapa", lambda: self._new_map(None)),
                          ("Salvar como…", self._open_save_dialog),
                          ("Carregar…", self._load_project_dialog)]:
            bw = FONT_S.size(label)[0] + 24
            rect = pygame.Rect(x, 6, bw, TOP_H-12)
            draw_button(screen, rect, label, FONT_S)
            self._top_hits.append((rect, cb))
            x += bw + 6
        for label, cb in [("Undo", self._do_undo), ("Redo", self._do_redo)]:
            rect = pygame.Rect(x, 6, 60, TOP_H-12)
            draw_button(screen, rect, label, FONT_S)
            self._top_hits.append((rect, cb))
            x += 66
        draw_text(screen, "MAP EDITOR", WIDTH - 130, 13, FONT_L, ACCENT_BRIGHT)

    def _switch_mode(self, mode):
        self.mode = mode
        if mode == self.MODE_TILES: self._sync_fields_from_tile()
        if mode == self.MODE_EVENTS:
            if self.last_right_panel == "event" and self.editing_event:
                self._sync_fields_from_event(self.editing_event)
            else:
                tag = self.selected_event_tag
                if tag and tag in self.project.event_types:
                    self._sync_fields_from_event_type(self.project.event_types[tag])
        if mode == self.MODE_MAP:
            self._sync_fields_from_map()

    # ------------------------------------------------------------------
    # Painel esquerdo
    # ------------------------------------------------------------------
    def _draw_left_panel(self):
        r = pygame.Rect(0, TOP_H, LEFT_W, HEIGHT - TOP_H - BOTTOM_H)
        pygame.draw.rect(screen, PANEL_BG, r)
        pygame.draw.line(screen, PANEL_BORDER, (LEFT_W, TOP_H),
                         (LEFT_W, HEIGHT - BOTTOM_H))
        x = 8; y = TOP_H + 8; w = LEFT_W - 16

        draw_text(screen, "ÁRVORE DE MAPAS (RMB menu · arraste p/ hierarquia)",
                  x, y, FONT_XS, ACCENT); y += 16
        self._draw_map_tree(self.project.roots(), 0, x, y, w)
        tree_h = self._tree_height()
        y = TOP_H + 8 + 18 + tree_h + 8

        if self.mode == self.MODE_MAP:
            draw_text(screen, f"CAMADA: {self.active_layer+1}", x, y, FONT_XS, HIGHLIGHT); y += 16
            draw_text(screen, "CATEGORIA", x, y, FONT_XS, ACCENT); y += 16
            cats = ["Todos"] + self.project.tileset.categories()
            cx = x
            for cat in cats:
                tw = FONT_XS.size(cat)[0] + 12
                if cx + tw > x + w: cx = x; y += 22
                rect = pygame.Rect(cx, y, tw, 20)
                active = (cat == self.selected_category)
                bg = BTN_ACTIVE if active else BTN
                if rect.collidepoint(pygame.mouse.get_pos()) and not active: bg = BTN_HOVER
                pygame.draw.rect(screen, bg, rect, border_radius=3)
                pygame.draw.rect(screen, ACCENT_DARK, rect, 1, border_radius=3)
                draw_text(screen, cat, cx + 6, y + 4, FONT_XS, TEXT)
                self._left_hits.append((rect, (lambda c=cat: self._set_category(c)), None))
                cx += tw + 4
            y += 26
            draw_text(screen, "TILES", x, y, FONT_XS, ACCENT); y += 16
            cols = 5; tw = (w - (cols-1)*4) // cols
            cx = x; cy = y
            for tid in self.project.tileset.order:
                t = self.project.tileset.get(tid)
                if not t: continue
                if self.selected_category != "Todos" and t.category != self.selected_category:
                    continue
                rect = pygame.Rect(cx, cy, tw, tw)
                img = t.get_surface(tw - 4)
                if img: screen.blit(img, (cx+2, cy+2))
                else: pygame.draw.rect(screen, t.color, (cx+2, cy+2, tw-4, tw-4))
                border = HIGHLIGHT if tid == self.selected_tile_id else ACCENT_DARK
                pygame.draw.rect(screen, border, rect,
                                 2 if tid == self.selected_tile_id else 1,
                                 border_radius=3)
                self._left_hits.append((rect, (lambda tt=tid: self._set_tile(tt)), None))
                cx += tw + 4
                if cx + tw > x + w + 2: cx = x; cy += tw + 4

        elif self.mode == self.MODE_TILES:
            draw_text(screen, "TILES DO PROJETO", x, y, FONT_XS, ACCENT); y += 16
            tw = 40; cx = x; cy = y
            for tid in self.project.tileset.order:
                t = self.project.tileset.get(tid)
                if not t: continue
                rect = pygame.Rect(cx, cy, tw, tw)
                img = t.get_surface(tw-4)
                if img: screen.blit(img, (cx+2, cy+2))
                else: pygame.draw.rect(screen, t.color, (cx+2, cy+2, tw-4, tw-4))
                border = HIGHLIGHT if tid == self.selected_tile_id else ACCENT_DARK
                pygame.draw.rect(screen, border, rect,
                                 2 if tid == self.selected_tile_id else 1,
                                 border_radius=3)
                self._left_hits.append((rect, (lambda tt=tid: self._set_tile(tt)), None))
                cx += tw + 4
                if cx + tw > x + w + 2: cx = x; cy += tw + 4

        elif self.mode == self.MODE_EVENTS:
            draw_text(screen, "TIPOS DE EVENTO", x, y, FONT_XS, ACCENT); y += 16
            for tag, et in self.project.event_types.items():
                rect = pygame.Rect(x, y, w, 24)
                active = (tag == self.selected_event_tag)
                bg = BTN_ACTIVE if active else BTN
                if rect.collidepoint(pygame.mouse.get_pos()) and not active:
                    bg = BTN_HOVER
                pygame.draw.rect(screen, bg, rect, border_radius=3)
                pygame.draw.rect(screen, et.color, (x + 3, y + 3, 18, 18),
                                 border_radius=2)
                spr = et.get_surface(18)
                if spr: screen.blit(spr, (x + 3, y + 3))
                label = ("★ " if et.is_preset else "") + et.label
                draw_text(screen, label, x + 26, y + 5, FONT_S, TEXT)
                self._left_hits.append((rect, (lambda tg=tag: self._select_event_type(tg)), "event_type"))
                y += 26
            y += 8
            draw_text(screen, "LMB no canvas: coloca/seleciona", x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "RMB num evento: menu", x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "RMB num tipo custom: deletar", x, y, FONT_XS, TEXT_DIM)

        y = HEIGHT - BOTTOM_H - 34
        bw = (w - 8) // 3
        if self.mode == self.MODE_MAP:
            r1 = pygame.Rect(x, y, bw, 28); r2 = pygame.Rect(x + bw + 4, y, bw, 28)
            r3 = pygame.Rect(x + 2*(bw+4), y, bw, 28)
            draw_button(screen, r1, "+ Mapa", FONT_XS); draw_button(screen, r2, "Dup", FONT_XS)
            draw_button(screen, r3, "Del", FONT_XS)
            self._left_hits += [(r1, lambda: self._new_map(None), None),
                                (r2, self._dup_map, None),
                                (r3, self._del_map, None)]
        elif self.mode == self.MODE_TILES:
            r1 = pygame.Rect(x, y, bw, 28); r2 = pygame.Rect(x + bw + 4, y, bw, 28)
            r3 = pygame.Rect(x + 2*(bw+4), y, bw, 28)
            draw_button(screen, r1, "+ Tile", FONT_XS); draw_button(screen, r2, "Dup", FONT_XS)
            draw_button(screen, r3, "Del", FONT_XS)
            self._left_hits += [(r1, self._new_tile, None),
                                (r2, self._dup_tile, None),
                                (r3, self._del_tile, None)]
        elif self.mode == self.MODE_EVENTS:
            r1 = pygame.Rect(x, y, bw, 28); r2 = pygame.Rect(x + bw + 4, y, bw, 28)
            r3 = pygame.Rect(x + 2*(bw+4), y, bw, 28)
            draw_button(screen, r1, "+ Tipo", FONT_XS); draw_button(screen, r2, "Dup Tipo", FONT_XS)
            draw_button(screen, r3, "Del Tipo", FONT_XS)
            self._left_hits += [(r1, self._new_event_type, None),
                                (r2, self._dup_event_type, None),
                                (r3, self._del_event_type, None)]

    def _set_category(self, cat): self.selected_category = cat
    def _set_tile(self, tid):
        self.selected_tile_id = tid; self._sync_fields_from_tile()
    def _select_event_type(self, tag):
        self.selected_event_tag = tag
        et = self.project.event_types.get(tag)
        if et: self._sync_fields_from_event_type(et)

    def _tree_height(self):
        def walk(names, depth):
            h = 0
            for n in names:
                h += 22
                h += walk(self.project.children_of(n), depth + 1)
            return h
        return walk(self.project.roots(), 0)

    def _draw_map_tree(self, names, depth, x0, y0, w):
        x = x0 + depth * 12
        y = y0
        for name in names:
            rect = pygame.Rect(x, y, w - depth * 12, 20)
            active = (name == self.project.active_map_name)
            bg = BTN_ACTIVE if active else BTN
            if rect.collidepoint(pygame.mouse.get_pos()) and not active:
                bg = BTN_HOVER
            if self.dragging_map_name == name:
                bg = (150, 130, 80)
            pygame.draw.rect(screen, bg, rect, border_radius=3)
            pygame.draw.rect(screen, ACCENT_DARK, rect, 1, border_radius=3)
            prefix = "▾ " if self.project.children_of(name) else "  "
            draw_text(screen, prefix + name[:22], x + 6, y + 4, FONT_XS, TEXT)
            self._left_hits.append((rect, (lambda n=name: self._left_click_map(n)), "map"))
            y += 22
            children = self.project.children_of(name)
            if children:
                y = self._draw_map_tree(children, depth + 1, x0, y, w)
        return y

    def _left_click_map(self, name):
        self.dragging_map_name = name
        self._switch_map(name)

    # ------------------------------------------------------------------
    # Painel direito
    # ------------------------------------------------------------------
    def _draw_right_panel(self):
        rx = WIDTH - RIGHT_W
        r = pygame.Rect(rx, TOP_H, RIGHT_W, HEIGHT - TOP_H - BOTTOM_H)
        pygame.draw.rect(screen, PANEL_BG, r)
        pygame.draw.line(screen, PANEL_BORDER, (rx, TOP_H),
                         (rx, HEIGHT - BOTTOM_H))
        x = rx + 16; y = TOP_H + 10; w = RIGHT_W - 32

        if self.mode == self.MODE_MAP:
            self._draw_right_map(x, y, w)
        elif self.mode == self.MODE_TILES:
            self._draw_right_tiles(x, y, w)
        elif self.mode == self.MODE_PASS:
            self._draw_right_pass(x, y, w)
        elif self.mode == self.MODE_EVENTS:
            self._draw_right_events(x, y, w)

        # desenha TODOS os campos ativos (o que estava faltando!)
        for key, f in self.fields.items():
            if f.active_this_frame:
                f.draw(screen)

    def _draw_right_map(self, x, y, w):
        draw_text(screen, "MAPA (tamanho e nome)", x, y, FONT_XS, ACCENT); y += 16
        self.fields["map_name"].set_position(x, y, w); y += 42
        half = (w - 6) // 2
        self.fields["map_w"].set_position(x, y, half)
        self.fields["map_h"].set_position(x + half + 6, y, half); y += 42

        rect = pygame.Rect(x, y, w, 28)
        draw_button(screen, rect, "Aplicar nome/tamanho", FONT_XS, primary=True)
        self._right_hits.append((rect, self._apply_map_fields)); y += 34

        draw_text(screen, "Tamanho rápido:", x, y, FONT_XS, TEXT_DIM); y += 14
        half2 = w - 78
        self.fields["quick_size"].set_position(x, y, half2)
        rect2 = pygame.Rect(x + half2 + 6, y + 14, 72, 24)
        draw_button(screen, rect2, "Aplicar", FONT_XS)
        self._right_hits.append((rect2, self._apply_quick_size))
        y += 42

        draw_text(screen, "Ajuste fino:", x, y, FONT_XS, TEXT_DIM); y += 14
        half = (w - 6) // 2
        r1 = pygame.Rect(x, y, half, 24); r2 = pygame.Rect(x + half + 6, y, half, 24)
        draw_button(screen, r1, "Larg −1", FONT_XS)
        draw_button(screen, r2, "Larg +1", FONT_XS)
        self._right_hits.append((r1, lambda: self._quick_resize(-1, 0)))
        self._right_hits.append((r2, lambda: self._quick_resize(1, 0)))
        y += 28
        r3 = pygame.Rect(x, y, half, 24); r4 = pygame.Rect(x + half + 6, y, half, 24)
        draw_button(screen, r3, "Alt −1", FONT_XS)
        draw_button(screen, r4, "Alt +1", FONT_XS)
        self._right_hits.append((r3, lambda: self._quick_resize(0, -1)))
        self._right_hits.append((r4, lambda: self._quick_resize(0, 1)))
        y += 32

        draw_text(screen, "CAMADAS", x, y, FONT_XS, ACCENT); y += 16
        bw = (w - 3*6) // 4
        labels = ["1 Base","2 Det","3 Ext","4 Top"]
        for i in range(LAYERS):
            rect = pygame.Rect(x + i*(bw+6), y, bw, 26)
            draw_button(screen, rect, labels[i], FONT_XS,
                        active=(i == self.active_layer))
            self._right_hits.append((rect, (lambda ii=i: self._set_layer(ii))))
        y += 34

        draw_text(screen, "FERRAMENTAS", x, y, FONT_XS, ACCENT); y += 16
        tools = [("Brush (B)", TOOL_BRUSH), ("Eraser (E)", TOOL_ERASER),
                 ("Fill (F)", TOOL_FILL), ("Retâng. (R)", TOOL_RECT),
                 ("Conta-gotas (P)", TOOL_PICKER)]
        bw = (w - 6) // 2
        for i, (label, key) in enumerate(tools):
            col = i % 2; row = i // 2
            rect = pygame.Rect(x + col*(bw+6), y + row*26, bw, 22)
            draw_button(screen, rect, label, FONT_XS, active=(self.tool == key))
            self._right_hits.append((rect, (lambda k=key: self._set_tool(k))))
        y += 3*26 + 10

        draw_text(screen, "TILE SELECIONADO", x, y, FONT_XS, ACCENT); y += 16
        tid = self.selected_tile_id
        t = self.project.tileset.get(tid) if tid else None
        if t:
            img = t.get_surface(60)
            if img: screen.blit(img, (x+2, y+2))
            else: pygame.draw.rect(screen, t.color, (x+2, y+2, 60, 60))
            pygame.draw.rect(screen, ACCENT_DARK, (x, y, 64, 64), 2)
            draw_text(screen, t.name[:24], x+76, y+4, FONT_S, TEXT)
            draw_text(screen, f"id: {t.id}", x+76, y+20, FONT_XS, TEXT_DIM)
            draw_text(screen, f"walk: {t.walkable}", x+76, y+34, FONT_XS,
                      SUCCESS if t.walkable else DANGER)

    def _set_layer(self, i): self.active_layer = i
    def _set_tool(self, k): self.tool = k

    def _draw_right_tiles(self, x, y, w):
        draw_text(screen, "EDITAR TILE", x, y, FONT_XS, ACCENT); y += 16
        tid = self.selected_tile_id
        t = self.project.tileset.get(tid) if tid else None
        if t:
            img = t.get_surface(76)
            if img: screen.blit(img, (x+2, y+2))
            else: pygame.draw.rect(screen, t.color, (x+2, y+2, 76, 76))
            pygame.draw.rect(screen, ACCENT_DARK, (x, y, 80, 80), 2)
            draw_text(screen, f"id: {t.id}", x+90, y+6, FONT_S, TEXT_GOLD)
            draw_text(screen, f"walkable: {t.walkable}", x+90, y+24, FONT_XS,
                      SUCCESS if t.walkable else DANGER)
            y += 92
        self.fields["tile_name"].set_position(x, y, w); y += 42
        self.fields["tile_category"].set_position(x, y, w); y += 42
        self.fields["tile_color"].set_position(x, y, w); y += 42
        self.fields["tile_image"].set_position(x, y, w); y += 42

        rects = [
            ("Aplicar", self._apply_tile_fields, True, False),
            ("Walkable (toggle)", self._toggle_walkable, False, False),
            ("Buscar imagem…", self._pick_tile_image, False, False),
            ("Remover imagem", self._clear_tile_image, False, False),
            ("+ Novo tile", self._new_tile, False, False),
            ("Duplicar", self._dup_tile, False, False),
            ("Excluir", self._del_tile, False, True),
        ]
        yy = y
        for label, cb, primary, danger in rects:
            r = pygame.Rect(x, yy, w, 30)
            draw_button(screen, r, label, FONT_XS, primary=primary, danger=danger)
            self._right_hits.append((r, cb))
            yy += 34

    def _draw_right_pass(self, x, y, w):
        draw_text(screen, "MODO DE PINTURA", x, y, FONT_XS, ACCENT); y += 16
        modes = [("Walkable", "ok", SUCCESS),
                 ("Blocked", "block", DANGER),
                 ("Above (sprite acima)", "above", (120, 180, 240)),
                 ("Limpar (volta ao tile)", "clear", TEXT_DIM)]
        for label, mode, col in modes:
            r = pygame.Rect(x, y, w, 26)
            active = (self.pass_mode == mode)
            bg = BTN_ACTIVE if active else BTN
            if r.collidepoint(pygame.mouse.get_pos()) and not active: bg = BTN_HOVER
            pygame.draw.rect(screen, bg, r, border_radius=4)
            pygame.draw.rect(screen, col, r, 2, border_radius=4)
            draw_text(screen, label, r.x + 12, r.y + 6, FONT_S, TEXT)
            self._right_hits.append((r, (lambda m=mode: self._set_pass_mode(m))))
            y += 30
        y += 8
        draw_text(screen, "Como funciona:", x, y, FONT_S, TEXT); y += 16
        for line in [
            "· LMB no canvas pinta o modo ativo",
            "· RMB no canvas pinta Blocked",
            "· Shift+LMB limpa override",
            "· Células sem override usam",
            "  o walkable do tile do topo",
            "· 'Above' = sprite desenhado",
            "  acima do jogador (ex: copa)",
        ]:
            draw_text(screen, line, x, y, FONT_XS, TEXT_DIM); y += 14
        y += 10
        m = self.project.active_map()
        if m:
            ok = sum(1 for v in m.passability.values() if v in (True, "ok"))
            blk = sum(1 for v in m.passability.values() if v in (False, "block"))
            ab = sum(1 for v in m.passability.values() if v == "above")
            draw_text(screen, f"walkable: {ok}", x, y, FONT_S, SUCCESS); y += 16
            draw_text(screen, f"blocked:  {blk}", x, y, FONT_S, DANGER); y += 16
            draw_text(screen, f"above:    {ab}", x, y, FONT_S, (120,180,240)); y += 18
        y += 6
        r = pygame.Rect(x, y, w, 30)
        draw_button(screen, r, "Limpar todos os overrides", FONT_XS, danger=True)
        self._right_hits.append((r, self._clear_all_passability))

    def _set_pass_mode(self, m): self.pass_mode = m

    def _draw_right_events(self, x, y, w):
        if self.last_right_panel == "event_type" and self.editing_event_type:
            self._draw_event_type_editor(x, y, w)
        elif self.last_right_panel == "event" and self.editing_event:
            self._draw_event_instance_editor(x, y, w)
        else:
            draw_text(screen, "SELECIONE UM EVENTO OU TIPO", x, y, FONT_XS, ACCENT); y += 20
            draw_text(screen, "· Clique num tipo à esquerda para editá-lo",
                      x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "· Clique num evento no canvas para editá-lo",
                      x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "· LMB no canvas (vazio) coloca evento",
                      x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "· RMB num evento abre menu",
                      x, y, FONT_XS, TEXT_DIM)

    def _draw_event_type_editor(self, x, y, w):
        et = self.editing_event_type
        draw_text(screen, "EDITAR TIPO DE EVENTO", x, y, FONT_XS, ACCENT); y += 16
        img = et.get_surface(60)
        if img: screen.blit(img, (x+2, y+2))
        else: pygame.draw.rect(screen, et.color, (x+2, y+2, 60, 60))
        pygame.draw.rect(screen, ACCENT_DARK, (x, y, 64, 64), 2)
        pres = "PRESET" if et.is_preset else "CUSTOM"
        draw_text(screen, pres, x+76, y+6, FONT_S,
                  TEXT_GOLD if et.is_preset else ACCENT)
        draw_text(screen, f"tag: {et.tag}", x+76, y+24, FONT_XS, TEXT_DIM)
        y += 74
        self.fields["et_tag"].set_position(x, y, w); y += 42
        self.fields["et_label"].set_position(x, y, w); y += 42
        self.fields["et_color"].set_position(x, y, w); y += 42
        self.fields["et_image"].set_position(x, y, w); y += 42
        bw2 = (w - 8) // 2
        r_apply = pygame.Rect(x, y, w, 30)
        draw_button(screen, r_apply, "Aplicar", FONT_XS, primary=True)
        self._right_hits.append((r_apply, self._apply_event_type_fields)); y += 34
        r_pick = pygame.Rect(x, y, bw2, 30)
        r_clear = pygame.Rect(x + bw2 + 8, y, bw2, 30)
        draw_button(screen, r_pick, "Buscar sprite…", FONT_XS)
        draw_button(screen, r_clear, "Remover sprite", FONT_XS)
        self._right_hits.append((r_pick, self._pick_event_image))
        self._right_hits.append((r_clear, self._clear_event_image)); y += 34
        if et.is_preset:
            draw_text(screen, "Preset: não pode ser deletado.",
                      x, y, FONT_XS, TEXT_DIM)
        else:
            r_del = pygame.Rect(x, y, w, 30)
            draw_button(screen, r_del, "Deletar tipo", FONT_XS, danger=True)
            self._right_hits.append((r_del, self._del_event_type))

    def _draw_event_instance_editor(self, x, y, w):
        ev = self.editing_event
        et = self.project.event_types.get(ev.tag)
        draw_text(screen, "EDITAR EVENTO", x, y, FONT_XS, ACCENT); y += 16
        if et:
            pygame.draw.rect(screen, et.color, (x, y, 24, 24), border_radius=3)
            spr = et.get_surface(24)
            if spr: screen.blit(spr, (x, y))
            draw_text(screen, et.label, x + 32, y + 5, FONT_S, TEXT)
            draw_text(screen, f"tag: {ev.tag}", x + 32, y + 22, FONT_XS, TEXT_DIM)
        else:
            draw_text(screen, f"(tag desconhecida: {ev.tag})", x, y + 5, FONT_S, DANGER)
        y += 42
        draw_text(screen, f"Posição no mapa: ({ev.x},{ev.y})",
                  x, y, FONT_XS, TEXT_DIM); y += 20

        half = (w - 6) // 2
        self.fields["ev_id"].set_position(x, y, half)
        self.fields["ev_name"].set_position(x + half + 6, y, half); y += 42

        draw_text(screen, "PROPRIEDADES (chave = valor)", x, y, FONT_XS, ACCENT); y += 14
        for i in range(1, 7):
            half2 = (w - 6) // 2
            self.fields[f"ev_k{i}"].set_position(x, y, half2)
            self.fields[f"ev_v{i}"].set_position(x + half2 + 6, y, half2)
            y += 42

        r_apply = pygame.Rect(x, y, w, 30)
        draw_button(screen, r_apply, "Aplicar alterações", FONT_XS, primary=True)
        self._right_hits.append((r_apply, self._apply_event_fields)); y += 34
        r_del = pygame.Rect(x, y, w, 30)
        draw_button(screen, r_del, "Deletar evento", FONT_XS, danger=True)
        self._right_hits.append((r_del, (lambda: self._del_event(ev)))); y += 34

    # ------------------------------------------------------------------
    # Canvas
    # ------------------------------------------------------------------
    def _draw_canvas(self):
        clip = self._canvas_rect()
        old = screen.get_clip()
        screen.set_clip(clip)
        pygame.draw.rect(screen, CANVAS_BG, clip)

        m = self.project.active_map()
        if m:
            self._draw_map_layers(m)
            if self.mode == self.MODE_PASS: self._draw_passability(m)
            if self.mode == self.MODE_EVENTS: self._draw_events(m)

        if self.hover_cell and self.mode in (self.MODE_MAP, self.MODE_PASS,
                                             self.MODE_EVENTS):
            cs = int(round(self.cell))
            wx, wy = self.hover_cell
            x = int(wx * self.cell - self.cam[0]) + CANVAS_X
            y = int(wy * self.cell - self.cam[1]) + CANVAS_Y
            if self.mode == self.MODE_MAP and self.tool == TOOL_RECT \
                    and self.rect_start and self.rect_end:
                x1, y1 = self.rect_start; x2, y2 = self.rect_end
                xa, xb = sorted((x1, x2)); ya, yb = sorted((y1, y2))
                rx1 = int(xa * self.cell - self.cam[0]) + CANVAS_X
                ry1 = int(ya * self.cell - self.cam[1]) + CANVAS_Y
                rw = int((xb - xa + 1) * self.cell)
                rh = int((yb - ya + 1) * self.cell)
                s = pygame.Surface((rw, rh), pygame.SRCALPHA)
                s.fill((255, 220, 100, 80)); screen.blit(s, (rx1, ry1))
                pygame.draw.rect(screen, HIGHLIGHT, (rx1, ry1, rw, rh), 2)
            else:
                border_col = HIGHLIGHT
                if self.mode == self.MODE_PASS: border_col = SUCCESS
                if self.mode == self.MODE_EVENTS:
                    et = self.project.event_types.get(self.selected_event_tag)
                    border_col = et.color if et else HIGHLIGHT
                pygame.draw.rect(screen, border_col, (x, y, cs, cs), 2)

        screen.set_clip(old)
        pygame.draw.rect(screen, PANEL_BORDER, clip, 2)

    def _draw_map_layers(self, m):
        cs = self.cell; cs_i = int(round(cs))
        ox = CANVAS_X - self.cam[0]; oy = CANVAS_Y - self.cam[1]
        x0 = max(0, int((CANVAS_X - ox) // cs))
        y0 = max(0, int((CANVAS_Y - oy) // cs))
        x1 = min(m.w, int((CANVAS_X + CANVAS_W - ox) // cs) + 1)
        y1 = min(m.h, int((CANVAS_Y + CANVAS_H - oy) // cs) + 1)
        for y in range(y0, y1):
            for x in range(x0, x1):
                rx = int(ox + x * cs); ry = int(oy + y * cs)
                if m.is_empty(x, y):
                    pygame.draw.rect(screen, EMPTY_CELL, (rx, ry, cs_i+1, cs_i+1))
        for layer in range(LAYERS):
            for y in range(y0, y1):
                for x in range(x0, x1):
                    tid = m.data[y][x][layer]
                    if tid is None: continue
                    t = self.project.tileset.get(tid)
                    if t is None: continue
                    rx = int(ox + x * cs); ry = int(oy + y * cs)
                    img = t.get_surface(cs_i + 1)
                    if img: screen.blit(img, (rx, ry))
                    else: pygame.draw.rect(screen, t.color, (rx, ry, cs_i+1, cs_i+1))
        if self.show_grid and cs >= 10:
            grid = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
            for x in range(x0, x1 + 1):
                rx = int(ox + x * cs) - CANVAS_X
                pygame.draw.line(grid, (0,0,0,70), (rx, 0), (rx, CANVAS_H))
            for y in range(y0, y1 + 1):
                ry = int(oy + y * cs) - CANVAS_Y
                pygame.draw.line(grid, (0,0,0,70), (0, ry), (CANVAS_W, ry))
            screen.blit(grid, (CANVAS_X, CANVAS_Y))
        mw = int(m.w * cs); mh = int(m.h * cs)
        pygame.draw.rect(screen, PANEL_BORDER,
                         (int(ox)-2, int(oy)-2, mw+4, mh+4), 2)

    def _draw_passability(self, m):
        cs = self.cell; cs_i = int(round(cs))
        ox = CANVAS_X - self.cam[0]; oy = CANVAS_Y - self.cam[1]
        x0 = max(0, int((CANVAS_X - ox) // cs))
        y0 = max(0, int((CANVAS_Y - oy) // cs))
        x1 = min(m.w, int((CANVAS_X + CANVAS_W - ox) // cs) + 1)
        y1 = min(m.h, int((CANVAS_Y + CANVAS_H - oy) // cs) + 1)
        for y in range(y0, y1):
            for x in range(x0, x1):
                rx = int(ox + x * cs); ry = int(oy + y * cs)
                base = m.tile_walkable_default(x, y, self.project.tileset) \
                    if not m.is_empty(x, y) else None
                override = m.passability.get((x, y))
                if override == "ok" or override is True: col = PASS_OK
                elif override == "block" or override is False: col = PASS_BLOCK
                elif override == "above": col = PASS_ABOVE
                elif override is None:
                    if base is True: col = PASS_TILE_OK
                    elif base is False: col = PASS_TILE_BLK
                    else: col = None
                else: col = None
                if col is not None:
                    s = pygame.Surface((cs_i+1, cs_i+1), pygame.SRCALPHA)
                    s.fill(col); screen.blit(s, (rx, ry))

    def _draw_events(self, m):
        cs = self.cell; cs_i = int(round(cs))
        ox = CANVAS_X - self.cam[0]; oy = CANVAS_Y - self.cam[1]
        for ev in m.events:
            rx = int(ox + ev.x * cs); ry = int(oy + ev.y * cs)
            et = self.project.event_types.get(ev.tag)
            col = et.color if et else (200, 200, 200)
            sprite_drawn = False
            if et:
                spr = et.get_surface(cs_i)
                if spr:
                    screen.blit(spr, (rx, ry)); sprite_drawn = True
            if not sprite_drawn:
                pygame.draw.rect(screen, col, (rx+2, ry+2, cs_i-4, cs_i-4),
                                 border_radius=3)
                pygame.draw.rect(screen, (20,15,10), (rx+2, ry+2, cs_i-4, cs_i-4),
                                 2, border_radius=3)
            selected = (self.editing_event is ev)
            border_col = HIGHLIGHT if selected else (20, 15, 10)
            border_w = 3 if selected else 2
            pygame.draw.rect(screen, border_col, (rx+1, ry+1, cs_i-2, cs_i-2),
                             border_w, border_radius=3)
            if cs_i >= 18:
                idtxt = FONT_XS.render(str(ev.id), True, (255, 255, 255))
                idbg = pygame.Surface((idtxt.get_width() + 4,
                                       idtxt.get_height() + 2), pygame.SRCALPHA)
                idbg.fill((0, 0, 0, 180))
                screen.blit(idbg, (rx + cs_i - idtxt.get_width() - 4, ry + 2))
                screen.blit(idtxt, (rx + cs_i - idtxt.get_width() - 2, ry + 2))

    def _draw_bottom_bar(self):
        r = pygame.Rect(0, HEIGHT - BOTTOM_H, WIDTH, BOTTOM_H)
        pygame.draw.rect(screen, PANEL_DARK, r)
        pygame.draw.line(screen, PANEL_BORDER, (0, HEIGHT-BOTTOM_H),
                         (WIDTH, HEIGHT-BOTTOM_H))
        if self.mode == self.MODE_MAP:
            hint = (f"Camada {self.active_layer+1}  ·  B/E/F/R/P ferramentas  ·  "
                    "Ctrl+Z/Y undo  ·  G grade  ·  WASD câmera  ·  TAB muda modo")
        elif self.mode == self.MODE_TILES:
            hint = "Edite tiles à direita  ·  Enter nos campos aplica  ·  TAB muda modo"
        elif self.mode == self.MODE_PASS:
            hint = ("LMB pinta modo ativo  ·  RMB pinta Blocked  ·  "
                    "Shift+LMB limpa override  ·  TAB muda modo")
        else:
            hint = "LMB coloca/seleciona  ·  RMB menu  ·  Tipos customizáveis à esquerda"
        draw_text(screen, hint, 10, HEIGHT - BOTTOM_H + 6, FONT_XS, TEXT_DIM)
        if self.autosave_dirty:
            draw_text(screen, "● salvando…", WIDTH - 190, HEIGHT-BOTTOM_H+6,
                      FONT_XS, WARN)
        else:
            draw_text(screen, "✓ autosave", WIDTH - 190, HEIGHT-BOTTOM_H+6,
                      FONT_XS, TEXT_DIM)
        draw_text(screen, f"zoom: {int(self.cell)}px", WIDTH - 90,
                  HEIGHT-BOTTOM_H+6, FONT_XS, TEXT_DIM)

    def _draw_msg(self):
        if not self.msg: return
        r = FONT_M.render(self.msg, True, self.msg_color)
        bg = pygame.Surface((r.get_width()+20, r.get_height()+10), pygame.SRCALPHA)
        bg.fill((0,0,0,210))
        x = CANVAS_X + CANVAS_W//2 - bg.get_width()//2
        y = CANVAS_Y + CANVAS_H - 60
        screen.blit(bg, (x, y)); screen.blit(r, (x+10, y+5))

    def run(self):
        while self.running:
            dt = clock.tick(60) / 1000.0
            events = pygame.event.get()
            self.handle_events(events)
            self.update(dt)
            self.draw()
        pygame.quit()

# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    MapEditorApp().run()