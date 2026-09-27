# -*- coding: utf-8 -*-
"""
MapEditor v19 — Texture Mode aplica em paredes e escadas.
"""
import os, sys, json, math, subprocess
from collections import deque
import pygame

try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TK = True
except ImportError:
    HAS_TK = False

# ============================================================
# CONFIG
# ============================================================
WIDTH, HEIGHT = 1280, 740
TOP_H     = 38
LEFT_W    = 240
RIGHT_W   = 320
BOTTOM_H  = 24
CANVAS_X  = LEFT_W
CANVAS_Y  = TOP_H
CANVAS_W  = WIDTH - LEFT_W - RIGHT_W
CANVAS_H  = HEIGHT - TOP_H - BOTTOM_H
NUM_FLOORS = 6
N_STEPS    = 4
WALL_HEIGHT_UNITS = 1.0
BLOCK_THICKNESS   = 0.20

BASE_TILE_W  = 64.0
BASE_TILE_H  = 32.0
BASE_WALL_H  = 16.0
CAM_SPEED    = 5.0

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports", "maps")
TILES_DIR   = os.path.join(BASE_DIR, "exports", "tiles")
SPRITES_DIR = os.path.join(BASE_DIR, "exports", "sprites")
for d in (EXPORTS_DIR, TILES_DIR, SPRITES_DIR):
    os.makedirs(d, exist_ok=True)
AUTOSAVE_PATH = os.path.join(EXPORTS_DIR, "_autosave.json")

TILE_SLOTS = ("top", "side_left", "side_right")
FORM_FLAT = 'flat'
FORMS_RAMP  = ['ramp_n', 'ramp_s', 'ramp_e', 'ramp_w']
FORMS_STAIR = ['stair_n', 'stair_s', 'stair_e', 'stair_w']
ALL_FORMS   = [FORM_FLAT] + FORMS_RAMP + FORMS_STAIR
WALL_KINDS = [('wall','Parede'), ('door','Porta'), ('window','Janela')]

TOOL_BRUSH  = 'brush'
TOOL_ERASER = 'eraser'
TOOL_FILL   = 'fill'
TOOL_RECT   = 'rect'
TOOL_DEFS = [
    (TOOL_BRUSH,  'Pincel',    'B'),
    (TOOL_ERASER, 'Borracha',  'E'),
    (TOOL_FILL,   'Fill',      'F'),
    (TOOL_RECT,   'Retangulo', 'R'),
]

pygame.init()
pygame.font.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Map Editor v19")
clock = pygame.time.Clock()

DEFAULT_TILE_ID  = 'sample'
DEFAULT_TILE_COL = (150, 150, 150)

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
POPUP_BG      = (28, 24, 20)

C_WALL_H_FRONT = (232, 220, 200)
C_WALL_V_FRONT = (196, 184, 164)
C_DOOR         = (110, 70, 40)
C_WINDOW       = (150, 212, 240)

FONT_L  = pygame.font.SysFont("georgia,dejavuserif,serif", 15, bold=True)
FONT_M  = pygame.font.SysFont("georgia,dejavuserif,serif", 12)
FONT_S  = pygame.font.SysFont("georgia,dejavuserif,serif", 11)
FONT_XS = pygame.font.SysFont("georgia,dejavuserif,serif", 10)

# ============================================================
# TEXTURAS BASE
# ============================================================
def _make_checker(size, c1, c2, border, path):
    if os.path.isfile(path): return
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        for x in range(size):
            c = c1 if ((x//8 + y//8) % 2 == 0) else c2
            surf.set_at((x, y), (c, c, c, 255))
    pygame.draw.rect(surf, (border, border, border, 255), (0,0,size,size), 1)
    try: pygame.image.save(surf, path)
    except Exception: pass

BASE_TEXTURE       = os.path.join(TILES_DIR, "base_texture.png")
SIDE_LEFT_TEXTURE  = os.path.join(TILES_DIR, "side_left_texture.png")
SIDE_RIGHT_TEXTURE = os.path.join(TILES_DIR, "side_right_texture.png")

def ensure_base_textures():
    _make_checker(64, 200, 160, 90, BASE_TEXTURE)
    _make_checker(64, 110, 80,  60, SIDE_LEFT_TEXTURE)
    _make_checker(64, 150, 120, 70, SIDE_RIGHT_TEXTURE)
ensure_base_textures()

# ============================================================
# HELPERS
# ============================================================
def draw_text(surf, text, x, y, font=FONT_M, color=TEXT, center=False):
    r = font.render(str(text), True, color)
    if center: surf.blit(r, (x - r.get_width()//2, y))
    else:      surf.blit(r, (x, y))
    return r

def draw_button(surf, rect, label, font=FONT_XS, active=False,
                primary=False, danger=False):
    mouse = pygame.mouse.get_pos()
    hover = rect.collidepoint(mouse)
    if primary:
        bg = (175, 135, 70) if hover else ACCENT; border = ACCENT_BRIGHT
    elif danger:
        bg = (150, 60, 60) if hover else (100, 45, 45); border = DANGER
    elif active:
        bg = BTN_ACTIVE; border = ACCENT_BRIGHT
    elif hover:
        bg = BTN_HOVER; border = ACCENT_DARK
    else:
        bg = BTN; border = ACCENT_DARK
    pygame.draw.rect(surf, bg, rect, border_radius=4)
    pygame.draw.rect(surf, border, rect, 1, border_radius=4)
    r = font.render(label, True, BTN_TEXT)
    surf.blit(r, (rect.centerx - r.get_width()//2,
                  rect.centery - r.get_height()//2))

def clamp(v, mn, mx): return max(mn, min(mx, v))

def darken(c, f):
    return tuple(max(0, min(255, int(c[i] * f))) for i in range(3))

def wall_val(v):
    """Normaliza valor de parede para (kind, tile_id)."""
    if v is None: return ('wall', None)
    if isinstance(v, str): return (v, None)
    if isinstance(v, (tuple, list)):
        if len(v) >= 2: return (v[0], v[1])
        return (v[0], None)
    return ('wall', None)

def safe_filename(s, fallback="sprite"):
    s = "".join(c for c in s if c not in '\\/:*?"<>|').strip()
    return s or fallback

def unique_path_in_dir(folder, base, ext=".png"):
    p = os.path.join(folder, f"{base}{ext}")
    if not os.path.isfile(p): return p
    i = 1
    while True:
        p = os.path.join(folder, f"{base}_{i}{ext}")
        if not os.path.isfile(p): return p
        i += 1

def pick_image_file():
    if HAS_TK:
        root = tk.Tk(); root.withdraw()
        p = filedialog.askopenfilename(
            title="Escolher sprite",
            filetypes=[("Imagens","*.png *.jpg *.jpeg *.bmp *.gif"),
                       ("Todos","*.*")])
        root.destroy()
        return p or None
    try:
        return input("Caminho da imagem: ").strip().strip('"').strip("'") or None
    except EOFError:
        return None

def open_folder(path):
    try:
        if sys.platform.startswith("win"): os.startfile(path)
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])
    except Exception: pass

def load_sprite_surface(path, tol=18):
    img = pygame.image.load(path).convert_alpha()
    w, h = img.get_size()
    has_alpha = False
    step = max(1, min(w,h)//30)
    for x in range(0, w, step):
        for y in range(0, h, step):
            if img.get_at((x,y))[3] < 250:
                has_alpha = True; break
        if has_alpha: break
    if has_alpha: return img
    bg = img.get_at((0,0))
    if bg[0] > 200 and bg[1] > 200 and bg[2] > 200:
        for x in range(w):
            for y in range(h):
                p = img.get_at((x,y))
                if (abs(p[0]-bg[0])<=tol and abs(p[1]-bg[1])<=tol
                        and abs(p[2]-bg[2])<=tol):
                    img.set_at((x,y), (p[0],p[1],p[2],0))
    return img

def draw_masked_face(screen, pts, src_img, dim=1.0):
    """Desenha polígono preenchido com a textura src_img mascarada."""
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0 = int(min(xs)), int(min(ys))
    x1, y1 = int(max(xs)), int(max(ys))
    ww, hh = x1 - x0, y1 - y0
    if ww <= 0 or hh <= 0: return
    try:
        spr = pygame.transform.smoothscale(src_img, (ww, hh))
    except Exception:
        return
    mask = pygame.Surface((ww, hh), pygame.SRCALPHA)
    rel = [(p[0] - x0, p[1] - y0) for p in pts]
    pygame.draw.polygon(mask, (255, 255, 255, 255), rel)
    spr.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    if dim < 1.0:
        spr.set_alpha(int(255 * dim))
    screen.blit(spr, (x0, y0))

# ============================================================
# TILE
# ============================================================
class Tile:
    def __init__(self, tid, name, color=(150,150,150), walkable=True,
                 category="Geral", height=0, blocks_sight=False, folder=None):
        self.id = tid; self.name = name; self.color = tuple(color)
        self.walkable = walkable; self.category = category
        self.height = int(height); self.blocks_sight = bool(blocks_sight)
        self.folder = folder or os.path.join(TILES_DIR, tid)
        try: os.makedirs(self.folder, exist_ok=True)
        except Exception: pass
        self._cache = {}; self._mtimes = {}
        self._ensure_base_textures()

    def _ensure_base_textures(self):
        base_map = {
            'top':        BASE_TEXTURE,
            'side_left':  SIDE_LEFT_TEXTURE,
            'side_right': SIDE_RIGHT_TEXTURE,
        }
        for slot, base_path in base_map.items():
            dst = self.slot_path(slot)
            if os.path.isfile(dst):
                continue
            if not os.path.isfile(base_path):
                continue
            try:
                img = pygame.image.load(base_path)
                pygame.image.save(img, dst)
            except Exception:
                pass

    def slot_path(self, slot): return os.path.join(self.folder, f"{slot}.png")
    def has_slot(self, slot): return os.path.isfile(self.slot_path(slot))

    def get_sprite(self, slot, size):
        p = self.slot_path(slot)
        if not os.path.isfile(p): return None
        try: mtime = os.path.getmtime(p)
        except Exception: return None
        if self._mtimes.get(slot) != mtime:
            for k in list(self._cache.keys()):
                if k[0] == slot: del self._cache[k]
            self._mtimes[slot] = mtime
        if isinstance(size, int): size = (size, size)
        size = (max(1, int(size[0])), max(1, int(size[1])))
        key = (slot, size)
        if key in self._cache: return self._cache[key]
        try:
            img = pygame.image.load(p).convert_alpha()
            scaled = pygame.transform.smoothscale(img, size)
            self._cache[key] = scaled
            return scaled
        except Exception:
            self._cache[key] = None; return None

    def clear_cache(self): self._cache = {}; self._mtimes = {}

    def set_slot_from_file(self, slot, src):
        try:
            os.makedirs(self.folder, exist_ok=True)
            img = pygame.image.load(src).convert_alpha()
            pygame.image.save(img, self.slot_path(slot))
            self.clear_cache(); return True
        except Exception: return False

    def remove_slot(self, slot):
        p = self.slot_path(slot)
        if os.path.isfile(p):
            try: os.remove(p)
            except Exception: pass
        self.clear_cache()

    def to_dict(self):
        return {"id": self.id, "name": self.name, "color": list(self.color),
                "walkable": self.walkable, "category": self.category,
                "height": self.height, "blocks_sight": self.blocks_sight}

    @classmethod
    def from_dict(cls, d):
        return cls(d["id"], d["name"], tuple(d.get("color",(150,150,150))),
                   d.get("walkable", True), d.get("category","Geral"),
                   d.get("height", 0), d.get("blocks_sight", False))

class TileSet:
    def __init__(self):
        self.tiles = {}; self.order = []
    def add(self, t):
        self.tiles[t.id] = t
        if t.id not in self.order: self.order.append(t.id)
    def remove(self, tid):
        if tid in self.tiles:
            del self.tiles[tid]
            self.order = [t for t in self.order if t != tid]
    def get(self, tid): return self.tiles.get(tid)
    def unique_id(self, base="tile"):
        i = 1
        while f"{base}_{i}" in self.tiles: i += 1
        return f"{base}_{i}"
    def to_dict(self):
        return {"order": self.order,
                "tiles": [self.tiles[t].to_dict() for t in self.order]}
    @classmethod
    def from_dict(cls, d):
        ts = cls()
        for td in d.get("tiles", []): ts.add(Tile.from_dict(td))
        ts.order = d.get("order", list(ts.tiles.keys()))
        return ts

def default_tileset():
    ts = TileSet()
    ts.add(Tile(DEFAULT_TILE_ID, "Sample", DEFAULT_TILE_COL,
                True, "Geral", height=0))
    return ts

# ============================================================
# CUSTOM SPRITE
# ============================================================
class CustomSprite:
    def __init__(self, name, path):
        self.name = name; self.path = path
        self.original = load_sprite_surface(path)
        self.scale = 1.0
        self.offset_x = 0.0; self.offset_y = 0.0
        self.anchor_x = 0.5; self.anchor_y = 1.0
        self._cache_key = None; self._cache = None
        self._ghost_key = None; self._ghost = None

    def surface(self, cam_zoom=1.0):
        key = (round(self.scale,4), round(cam_zoom,4))
        if self._cache_key != key:
            ow, oh = self.original.get_size()
            w = max(1, int(ow * self.scale * cam_zoom))
            h = max(1, int(oh * self.scale * cam_zoom))
            self._cache = pygame.transform.smoothscale(self.original, (w, h))
            self._cache_key = key
        return self._cache

    def ghost(self, cam_zoom=1.0):
        s = self.surface(cam_zoom)
        key = (self._cache_key, s.get_size())
        if self._ghost_key != key:
            g = s.copy(); g.set_alpha(140)
            self._ghost = g; self._ghost_key = key
        return self._ghost

    def draw_at(self, screen, sx, sy, cam_zoom=1.0):
        s = self.surface(cam_zoom)
        w, h = s.get_size()
        ox = self.offset_x * cam_zoom; oy = self.offset_y * cam_zoom
        dx = sx - self.anchor_x * w + ox
        dy = sy - self.anchor_y * h + oy
        screen.blit(s, (int(dx), int(dy)))

# ============================================================
# EVENT
# ============================================================
EVENT_KINDS = [("player_spawn","Player Spawn"),("trigger","Trigger"),
               ("teleport","Teleport"),("other","Other")]
EVENT_KIND_COLORS = {"player_spawn":(100,220,255),"trigger":(230,100,100),
                     "teleport":(200,130,240),"other":(200,200,200)}
EVENT_KIND_GLYPHS = {"player_spawn":"P","trigger":"T","teleport":"!","other":"?"}

class GameEvent:
    def __init__(self, kind="other", x=0, y=0, eid=0):
        self.kind = kind; self.x = x; self.y = y; self.id = eid
        self.name = ""; self.tag = ""; self.data = {}
        self.sprite_idx = None
    def to_dict(self):
        return {"kind": self.kind, "x": self.x, "y": self.y, "id": self.id,
                "name": self.name, "tag": self.tag, "data": dict(self.data),
                "sprite_idx": self.sprite_idx}
    @classmethod
    def from_dict(cls, d):
        ev = cls(d.get("kind","other"), d["x"], d["y"], d.get("id",0))
        ev.name = d.get("name",""); ev.tag = d.get("tag","")
        ev.data = dict(d.get("data", {}))
        ev.sprite_idx = d.get("sprite_idx", None)
        return ev

def default_terrain():
    return {'tile_id': DEFAULT_TILE_ID, 'h': 0, 'form': FORM_FLAT}

# ============================================================
# MAPA
# ============================================================
class TileMap:
    def __init__(self, name="novo_mapa", w=24, h=20, num_floors=NUM_FLOORS):
        self.name = name; self.w = w; self.h = h
        self.num_floors = num_floors
        self.terrain = {}
        self.blocks = {}
        self.walls_h = {}; self.walls_v = {}
        self.objects = {}
        self.passability = {}
        self.events = []
        self.parent = None
        for y in range(h):
            for x in range(w):
                self.terrain[(x,y)] = default_terrain()

    def in_bounds(self, x, y): return 0 <= x < self.w and 0 <= y < self.h
    def get_terrain(self, x, y): return self.terrain.get((x, y), default_terrain())
    def set_terrain(self, x, y, t):
        if self.in_bounds(x, y): self.terrain[(x, y)] = t
    def get_block(self, x, y, z): return self.blocks.get((x, y, z))
    def set_block(self, x, y, z, tid):
        if tid is None: self.blocks.pop((x, y, z), None)
        else: self.blocks[(x, y, z)] = tid
    def get_object(self, x, y, z): return self.objects.get((x, y, z))
    def set_object(self, x, y, z, sid):
        if sid is None: self.objects.pop((x, y, z), None)
        else: self.objects[(x, y, z)] = sid

    def is_walkable(self, x, y, tileset):
        if not self.in_bounds(x, y): return False
        v = self.passability.get((x, y))
        if v == 'ok': return True
        if v == 'block': return False
        t = tileset.get(self.get_terrain(x, y)['tile_id'])
        return t.walkable if t else True

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
        new_terrain = {}
        for y in range(nh):
            for x in range(nw):
                new_terrain[(x,y)] = self.terrain.get((x,y), default_terrain())
        self.terrain = new_terrain
        self.blocks  = {(x,y,z):v for (x,y,z),v in self.blocks.items()
                        if 0 <= x < nw and 0 <= y < nh}
        self.walls_h = {(x,y,z):v for (x,y,z),v in self.walls_h.items()
                        if 0 <= x <= nw and 0 <= y < nh}
        self.walls_v = {(x,y,z):v for (x,y,z),v in self.walls_v.items()
                        if 0 <= x < nw and 0 <= y <= nh}
        self.objects = {(x,y,z):v for (x,y,z),v in self.objects.items()
                        if 0 <= x < nw and 0 <= y < nh}
        self.passability = {(x,y):v for (x,y),v in self.passability.items()
                            if 0 <= x < nw and 0 <= y < nh}
        self.events = [ev for ev in self.events
                       if 0 <= ev.x < nw and 0 <= ev.y < nh]
        self.w = nw; self.h = nh

    def to_dict(self):
        def wall_row(x, y, z, v):
            k, tid = wall_val(v)
            return [x, y, z, k, tid]
        return {
            "name": self.name, "w": self.w, "h": self.h,
            "num_floors": self.num_floors, "parent": self.parent,
            "terrain": [[x, y, self.terrain[(x,y)]['tile_id'],
                         self.terrain[(x,y)]['h'], self.terrain[(x,y)]['form']]
                        for (x,y) in self.terrain],
            "blocks":  [[x, y, z, tid] for (x,y,z), tid in self.blocks.items()],
            "walls_h": [wall_row(x, y, z, v) for (x,y,z), v in self.walls_h.items()],
            "walls_v": [wall_row(x, y, z, v) for (x,y,z), v in self.walls_v.items()],
            "objects": [[x, y, z, sid] for (x,y,z), sid in self.objects.items()],
            "passability": [[x, y, v] for (x,y), v in self.passability.items()],
            "events": [ev.to_dict() for ev in self.events],
        }

    @classmethod
    def from_dict(cls, d):
        m = cls(d["name"], d["w"], d["h"], d.get("num_floors", NUM_FLOORS))
        m.parent = d.get("parent")
        m.terrain = {}
        for entry in d.get("terrain", []):
            if len(entry) >= 3:
                x, y, tid = entry[0], entry[1], entry[2]
                h = entry[3] if len(entry) > 3 else 0
                fm = entry[4] if len(entry) > 4 else FORM_FLAT
                m.terrain[(x,y)] = {'tile_id': tid, 'h': h, 'form': fm}
        for y in range(m.h):
            for x in range(m.w):
                if (x,y) not in m.terrain:
                    m.terrain[(x,y)] = default_terrain()
        m.blocks  = {(e[0],e[1],e[2]): e[3] for e in d.get("blocks", [])}
        for e in d.get("walls_h", []):
            if len(e) >= 5:
                m.walls_h[(e[0],e[1],e[2])] = (e[3], e[4])
            elif len(e) == 4:
                m.walls_h[(e[0],e[1],e[2])] = (e[3], None)
        for e in d.get("walls_v", []):
            if len(e) >= 5:
                m.walls_v[(e[0],e[1],e[2])] = (e[3], e[4])
            elif len(e) == 4:
                m.walls_v[(e[0],e[1],e[2])] = (e[3], None)
        m.objects = {(e[0],e[1],e[2]): e[3] for e in d.get("objects", [])}
        for e in d.get("passability", []):
            if len(e) >= 3: m.passability[(e[0],e[1])] = e[2]
        for evd in d.get("events", []):
            m.events.append(GameEvent.from_dict(evd))
        return m

# ============================================================
# PROJECT
# ============================================================
class Project:
    def __init__(self):
        self.tileset = default_tileset()
        self.sprites = []
        self.maps = {}
        m = TileMap("mapa_inicial", 24, 20)
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
    def children_of(self, p):
        return [n for n,m in self.maps.items() if m.parent == p]
    def roots(self):
        return [n for n,m in self.maps.items() if m.parent is None]
    def add_sprite(self, sp):
        self.sprites.append(sp); return len(self.sprites) - 1
    def remove_sprite(self, idx):
        if 0 <= idx < len(self.sprites):
            del self.sprites[idx]
            for m in self.maps.values():
                new_obj = {}
                for k, v in m.objects.items():
                    if v == idx: continue
                    new_obj[k] = v - 1 if v > idx else v
                m.objects = new_obj
                for ev in m.events:
                    if ev.sprite_idx is None: continue
                    if ev.sprite_idx == idx: ev.sprite_idx = None
                    elif ev.sprite_idx > idx: ev.sprite_idx -= 1
    def to_dict(self):
        return {
            "tileset": self.tileset.to_dict(),
            "sprites": [{"name": s.name, "path": s.path, "scale": s.scale,
                         "offset_x": s.offset_x, "offset_y": s.offset_y,
                         "anchor_x": s.anchor_x, "anchor_y": s.anchor_y}
                        for s in self.sprites],
            "maps": {n: m.to_dict() for n,m in self.maps.items()},
            "active_map_name": self.active_map_name,
        }
    @classmethod
    def from_dict(cls, d):
        p = cls.__new__(cls)
        p.tileset = TileSet.from_dict(d["tileset"])
        p.sprites = []
        for sd in d.get("sprites", []):
            try:
                sp = CustomSprite(sd["name"], sd["path"])
                sp.scale = sd.get("scale", 1.0)
                sp.offset_x = sd.get("offset_x", 0.0)
                sp.offset_y = sd.get("offset_y", 0.0)
                sp.anchor_x = sd.get("anchor_x", 0.5)
                sp.anchor_y = sd.get("anchor_y", 1.0)
                p.sprites.append(sp)
            except Exception: pass
        p.maps = {n: TileMap.from_dict(md) for n,md in d["maps"].items()}
        p.active_map_name = d.get("active_map_name")
        if not p.maps:
            m = TileMap("mapa_inicial", 24, 20)
            p.maps[m.name] = m; p.active_map_name = m.name
        if p.active_map_name not in p.maps:
            p.active_map_name = next(iter(p.maps))
        return p

# ============================================================
# UI WIDGETS
# ============================================================
class TextField:
    def __init__(self, key, label, value="", max_len=80):
        self.key = key; self.label = label; self.value = value
        self.max_len = max_len
        self.label_rect = pygame.Rect(0,0,0,0); self.rect = pygame.Rect(0,0,0,0)
        self.focused = False; self.active_this_frame = False
    def set_position(self, x, y, w):
        self.label_rect = pygame.Rect(x, y, w, 12)
        self.rect = pygame.Rect(x, y + 14, w, 22)
        self.active_this_frame = True
    def mark_inactive(self):
        self.label_rect = pygame.Rect(0,0,0,0); self.rect = pygame.Rect(0,0,0,0)
        self.active_this_frame = False
    def handle_key(self, event):
        if not self.focused: return False
        if event.key == pygame.K_BACKSPACE: self.value = self.value[:-1]; return True
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
        clip = surf.get_clip()
        surf.set_clip(self.rect.inflate(-8, -4))
        surf.blit(ts, (self.rect.x + 6, self.rect.y + 5))
        if self.focused and (pygame.time.get_ticks()//500) % 2 == 0:
            cx = self.rect.x + 6 + ts.get_width()
            pygame.draw.line(surf, TEXT, (cx, self.rect.y + 4),
                             (cx, self.rect.bottom - 4), 1)
        surf.set_clip(clip)

class Dropdown:
    def __init__(self, key, label, options, value, on_change=None, max_visible=12):
        self.key = key; self.label = label; self.options = options
        self.value = value; self.on_change = on_change
        self.max_visible = max_visible; self.expanded = False
        self.label_rect = pygame.Rect(0,0,0,0); self.rect = pygame.Rect(0,0,0,0)
        self.active_this_frame = False
    def set_position(self, x, y, w, h=22):
        self.label_rect = pygame.Rect(x, y, w, 12)
        self.rect = pygame.Rect(x, y+14, w, h)
        self.active_this_frame = True
    def mark_inactive(self):
        self.label_rect = pygame.Rect(0,0,0,0); self.rect = pygame.Rect(0,0,0,0)
        self.active_this_frame = False
    def set_options(self, opts): self.options = opts
    def display_label(self):
        for v, l in self.options:
            if v == self.value: return l
        return str(self.value) if self.value is not None else "—"
    def list_rect(self):
        n = min(len(self.options), self.max_visible)
        h = n * 22 + 4
        ly = self.rect.bottom
        if ly + h > HEIGHT - BOTTOM_H:
            ly = max(TOP_H + 4, self.rect.top - h)
        return pygame.Rect(self.rect.x, ly, self.rect.w, h)
    def handle_click(self, pos):
        if self.expanded:
            lr = self.list_rect()
            if lr.collidepoint(pos):
                idx = clamp((pos[1] - lr.y - 2) // 22, 0, len(self.options)-1)
                nv = self.options[idx][0]
                if nv != self.value:
                    self.value = nv
                    if self.on_change: self.on_change(nv)
                self.expanded = False; return True
            self.expanded = False; return False
        if self.rect.collidepoint(pos):
            self.expanded = True; return True
        return False
    def draw(self, surf):
        lab = FONT_XS.render(self.label, True, TEXT_DIM)
        surf.blit(lab, (self.label_rect.x, self.label_rect.y))
        bg = (65, 55, 42) if self.expanded else (36, 30, 25)
        pygame.draw.rect(surf, bg, self.rect, border_radius=3)
        border = ACCENT_BRIGHT if self.expanded else ACCENT_DARK
        pygame.draw.rect(surf, border, self.rect, 1, border_radius=3)
        ts = FONT_S.render(self.display_label(), True, TEXT)
        clip = surf.get_clip()
        surf.set_clip(self.rect.inflate(-20, -4))
        surf.blit(ts, (self.rect.x + 6, self.rect.y + 5))
        surf.set_clip(clip)
        ax = self.rect.right - 12; ay = self.rect.centery
        pygame.draw.polygon(surf, TEXT, [(ax-4, ay-2), (ax+4, ay-2), (ax, ay+3)])
    def draw_overlay(self, surf):
        if not self.expanded: return
        lr = self.list_rect()
        pygame.draw.rect(surf, POPUP_BG, lr)
        pygame.draw.rect(surf, ACCENT_BRIGHT, lr, 1)
        mouse = pygame.mouse.get_pos()
        for i, (v, l) in enumerate(self.options[:self.max_visible]):
            r = pygame.Rect(lr.x+2, lr.y+2+i*22, lr.w-4, 22)
            if r.collidepoint(mouse): pygame.draw.rect(surf, BTN_HOVER, r)
            if v == self.value: pygame.draw.rect(surf, BTN_ACTIVE, r)
            draw_text(surf, l, r.x+6, r.y+5, FONT_S, TEXT)

class InputDialog:
    def __init__(self):
        self.active = False; self.text = ""
        self.title = ""; self.prompt = ""
        self.rect = pygame.Rect(0,0,480,170)
        self.rect.center = (WIDTH//2, HEIGHT//2)
        self.input_rect = pygame.Rect(0,0,0,0)
        self.btn_ok = None; self.btn_cancel = None; self.on_ok = None
    def open(self, title, prompt, default="", on_ok=None):
        self.active = True; self.title = title; self.prompt = prompt
        self.text = default; self.on_ok = on_ok
        r = self.rect
        self.input_rect = pygame.Rect(r.x+20, r.y+60, r.w-40, 32)
        bw = 130; by = r.bottom-46
        self.btn_cancel = pygame.Rect(r.x+20, by, bw, 30)
        self.btn_ok = pygame.Rect(r.right-20-bw, by, bw, 30)
    def close(self): self.active = False
    def handle_event(self, event):
        if not self.active: return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: self.close()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.on_ok: self.on_ok(self.text)
                self.close()
            elif event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
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
        overlay.fill((0,0,0,170)); surf.blit(overlay, (0,0))
        r = self.rect
        pygame.draw.rect(surf, PANEL_BG, r, border_radius=8)
        pygame.draw.rect(surf, ACCENT_BRIGHT, r, 2, border_radius=8)
        draw_text(surf, self.title, r.x+20, r.y+14, FONT_L, ACCENT_BRIGHT)
        draw_text(surf, self.prompt, r.x+20, r.y+44, FONT_S, TEXT_DIM)
        pygame.draw.rect(surf, (22,19,16), self.input_rect, border_radius=4)
        pygame.draw.rect(surf, ACCENT_DARK, self.input_rect, 1, border_radius=4)
        caret = "_" if (pygame.time.get_ticks()//500)%2==0 else " "
        shown = self.text + caret
        col = TEXT if self.text else (90,80,65)
        txt = FONT_M.render(shown if self.text else "digite aqui", True, col)
        surf.blit(txt, (self.input_rect.x+8, self.input_rect.y+8))
        draw_button(surf, self.btn_cancel, "Cancelar  (ESC)", FONT_M)
        draw_button(surf, self.btn_ok, "OK  (Enter)", FONT_M, primary=True)

class SaveDialog:
    def __init__(self):
        self.active = False; self.text = ""
        self.rect = pygame.Rect(0,0,440,175)
        self.rect.center = (WIDTH//2, HEIGHT//2)
        self.input_rect = pygame.Rect(0,0,0,0)
        self.btn_save = None; self.btn_cancel = None
        self._layout()
    def _layout(self):
        r = self.rect
        self.input_rect = pygame.Rect(r.x+20, r.y+60, r.w-40, 32)
        bw = 130; by = r.bottom-46
        self.btn_cancel = pygame.Rect(r.x+20, by, bw, 30)
        self.btn_save = pygame.Rect(r.right-20-bw, by, bw, 30)
    def open(self, d=""):
        self.active = True; self.text = d; self._layout()
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
        overlay.fill((0,0,0,170)); surf.blit(overlay, (0,0))
        r = self.rect
        pygame.draw.rect(surf, PANEL_BG, r, border_radius=8)
        pygame.draw.rect(surf, ACCENT_BRIGHT, r, 2, border_radius=8)
        draw_text(surf, "SALVAR PROJETO", r.x+20, r.y+14, FONT_L, ACCENT_BRIGHT)
        draw_text(surf, "Nome do arquivo:", r.x+20, r.y+44, FONT_S, TEXT_DIM)
        pygame.draw.rect(surf, (22,19,16), self.input_rect, border_radius=4)
        pygame.draw.rect(surf, ACCENT_DARK, self.input_rect, 1, border_radius=4)
        caret = "_" if (pygame.time.get_ticks()//500)%2==0 else " "
        shown = self.text + caret
        col = TEXT if self.text else (90,80,65)
        txt = FONT_M.render(shown if self.text else "meu_projeto", True, col)
        surf.blit(txt, (self.input_rect.x+8, self.input_rect.y+8))
        draw_button(surf, self.btn_cancel, "Cancelar", FONT_M)
        draw_button(surf, self.btn_save, "Salvar", FONT_M, primary=True)

class ContextMenu:
    def __init__(self):
        self.active = False; self.items = []; self.rect = None
    def open(self, pos, items):
        if not items: return
        self.active = True; self.items = items
        w = max(FONT_M.size(l)[0] for l,_ in items) + 24
        h = len(items) * 22 + 8
        x = min(pos[0], WIDTH - w - 4)
        y = min(pos[1], HEIGHT - h - 4)
        if y + h > HEIGHT - BOTTOM_H:
            y = max(TOP_H + 4, HEIGHT - BOTTOM_H - h - 4)
        self.rect = pygame.Rect(x, y, w, h)
    def close(self):
        self.active = False; self.items = []
    def handle_event(self, event):
        if not self.active: return None
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for i, (l, cb) in enumerate(self.items):
                    r = pygame.Rect(self.rect.x, self.rect.y+4+i*22,
                                    self.rect.w, 22)
                    if r.collidepoint(event.pos):
                        self.close(); return cb
                if not self.rect.collidepoint(event.pos): self.close()
            elif event.button == 3: self.close()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
        return None
    def draw(self, surf):
        if not self.active or not self.items: return
        pygame.draw.rect(surf, PANEL_BG, self.rect, border_radius=4)
        pygame.draw.rect(surf, ACCENT_BRIGHT, self.rect, 2, border_radius=4)
        for i, (l, _) in enumerate(self.items):
            r = pygame.Rect(self.rect.x, self.rect.y+4+i*22, self.rect.w, 22)
            if r.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(surf, BTN_HOVER, r, border_radius=3)
            draw_text(surf, l, r.x+10, r.y+4, FONT_M, TEXT)

# ============================================================
# CAMERA / PROJECAO
# ============================================================
class Camera:
    def __init__(self):
        self.x = 0.0; self.y = 0.0; self.zoom = 1.0

def tile_size(cam): return BASE_TILE_W * cam.zoom, BASE_TILE_H * cam.zoom
def unit_px(cam): return BASE_WALL_H * cam.zoom

def world_to_screen(px, py, cam, ox, oy):
    tw, th = tile_size(cam)
    return ox + (px - py) * tw * 0.5, oy + (px + py) * th * 0.5

def screen_to_world(sx, sy, cam, ox, oy):
    tw, th = tile_size(cam)
    ax = (sx - ox) / (tw * 0.5)
    ay = (sy - oy) / (th * 0.5)
    return (ax + ay) * 0.5, (ay - ax) * 0.5

def seg_dist_sq(px, py, x1, y1, x2, y2):
    dx = x2 - x1; dy = y2 - y1
    dd = dx*dx + dy*dy
    if dd < 1e-9: return (px - x1)**2 + (py - y1)**2
    t = max(0.0, min(1.0, ((px - x1)*dx + (py - y1)*dy) / dd))
    ex = x1 + dx*t; ey = y1 + dy*t
    return (px - ex)**2 + (py - ey)**2

def corner_heights(form, h):
    if form == FORM_FLAT or form is None:
        return (h, h, h, h)
    if form.endswith('_n'): return (h+1.0, h+1.0, h+0.0, h+0.0)
    if form.endswith('_s'): return (h+0.0, h+0.0, h+1.0, h+1.0)
    if form.endswith('_e'): return (h+0.0, h+1.0, h+1.0, h+0.0)
    if form.endswith('_w'): return (h+1.0, h+0.0, h+0.0, h+1.0)
    return (h, h, h, h)

def point_in_poly(px, py, pts):
    n = len(pts); inside = False; j = n - 1
    for i in range(n):
        xi, yi = pts[i]; xj, yj = pts[j]
        if ((yi > py) != (yj > py)) and \
           (px < (xj-xi) * (py-yi) / (yj-yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

# ============================================================
# RENDER ISOMETRICO
# ============================================================
def mask_diamond(img, w, h):
    w = max(1, int(w)); h = max(1, int(h))
    src = pygame.transform.smoothscale(img, (w, h))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    hw = w // 2; hh = h // 2
    pygame.draw.polygon(mask, (255,255,255,255),
                        [(hw, 0), (w, hh), (hw, h), (0, hh)])
    src.blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
    return src

def draw_terrain_iso(screen, terrain_t, tile, x, y, z_base, cam, ox, oy):
    form = terrain_t['form']; h = terrain_t['h']
    n_h, e_h, s_h, w_h = corner_heights(form, h)
    z = unit_px(cam); tw, th = tile_size(cam)

    N = world_to_screen(x,   y,   cam, ox, oy)
    E = world_to_screen(x+1, y,   cam, ox, oy)
    S = world_to_screen(x+1, y+1, cam, ox, oy)
    W = world_to_screen(x,   y+1, cam, ox, oy)
    Nt = (N[0], N[1] - n_h * z); Et = (E[0], E[1] - e_h * z)
    St = (S[0], S[1] - s_h * z); Wt = (W[0], W[1] - w_h * z)

    if form == FORM_FLAT and h == 0:
        top_spr = tile.get_sprite("top", (int(tw), int(th)))
        if top_spr:
            screen.blit(mask_diamond(top_spr, tw, th),
                        (int(N[0] - tw/2), int(N[1])))
        else:
            pygame.draw.polygon(screen, tile.color, [N, E, S, W])
            pygame.draw.polygon(screen, darken(tile.color, 0.8), [N, E, S, W], 1)
        return

    if s_h > 0 or w_h > 0:
        pts = [W, S, St, Wt]
        left = tile.get_sprite("side_left", (64, 64))
        if left is None: left = tile.get_sprite("top", (64, 64))
        if left:
            draw_masked_face(screen, pts, left, 1.0)
        else:
            pygame.draw.polygon(screen, darken(tile.color, 0.55), pts)

    if s_h > 0 or e_h > 0:
        pts = [S, E, Et, St]
        right = tile.get_sprite("side_right", (64, 64))
        if right is None: right = tile.get_sprite("top", (64, 64))
        if right:
            draw_masked_face(screen, pts, right, 1.0)
        else:
            pygame.draw.polygon(screen, darken(tile.color, 0.75), pts)

    top_pts = [Nt, Et, St, Wt]
    top = tile.get_sprite("top", (int(tw), int(th)))
    if top:
        draw_masked_face(screen, top_pts, top, 1.0)
    else:
        pygame.draw.polygon(screen, tile.color, top_pts)
        pygame.draw.polygon(screen, darken(tile.color, 0.8), top_pts, 1)

def draw_block_iso(screen, tile, x, y, z, cam, ox, oy, dim=1.0):
    z_unit = unit_px(cam)
    tw, th = tile_size(cam)
    z_bot = z * z_unit
    z_top = (z + BLOCK_THICKNESS) * z_unit

    Nb = world_to_screen(x,     y,     cam, ox, oy)
    Eb = world_to_screen(x + 1, y,     cam, ox, oy)
    Sb = world_to_screen(x + 1, y + 1, cam, ox, oy)
    Wb = world_to_screen(x,     y + 1, cam, ox, oy)

    N0 = (Nb[0], Nb[1] - z_bot); E0 = (Eb[0], Eb[1] - z_bot)
    S0 = (Sb[0], Sb[1] - z_bot); W0 = (Wb[0], Wb[1] - z_bot)
    N1 = (Nb[0], Nb[1] - z_top); E1 = (Eb[0], Eb[1] - z_top)
    S1 = (Sb[0], Sb[1] - z_top); W1 = (Wb[0], Wb[1] - z_top)

    def _draw_face(pts, slot, fallback_factor):
        spr_src = tile.get_sprite(slot, (64, 64))
        if spr_src:
            draw_masked_face(screen, pts, spr_src, dim)
        else:
            c = darken(tile.color, fallback_factor * dim)
            pygame.draw.polygon(screen, c, pts)

    _draw_face([W0, S0, S1, W1], "side_left",  0.55)
    _draw_face([S0, E0, E1, S1], "side_right", 0.75)

    top_spr = tile.get_sprite("top", (int(tw), int(th)))
    if top_spr:
        draw_masked_face(screen, [N1, E1, S1, W1], top_spr, dim)
    else:
        top_pts = [N1, E1, S1, W1]
        c = darken(tile.color, dim)
        pygame.draw.polygon(screen, c, top_pts)
        pygame.draw.polygon(screen, darken(c, 0.8), top_pts, 1)

def draw_stairs_iso(screen, terrain_t, tile, x, y, cam, ox, oy):
    h = terrain_t['h']; form = terrain_t['form']
    direction = form.split('_')[1]
    z_unit = unit_px(cam)
    base_col = tile.color

    top_src = tile.get_sprite("top", (64, 64))
    left_src = tile.get_sprite("side_left", (64, 64))
    right_src = tile.get_sprite("side_right", (64, 64))
    if left_src is None: left_src = top_src
    if right_src is None: right_src = top_src

    steps = []
    for k in range(N_STEPS):
        z_top = h + (N_STEPS - 1 - k) / N_STEPS
        u0 = k / N_STEPS; u1 = (k + 1) / N_STEPS
        if direction == 'n':
            x0, x1 = x, x + 1; y0 = y + u0; y1 = y + u1
        elif direction == 's':
            x0, x1 = x, x + 1; y0 = y + 1 - u1; y1 = y + 1 - u0
        elif direction == 'e':
            y0, y1 = y, y + 1; x0 = x + 1 - u1; x1 = x + 1 - u0
        else:
            y0, y1 = y, y + 1; x0 = x + u0; x1 = x + u1
        steps.append(((x0+x1)*0.5 + (y0+y1)*0.5, x0, y0, x1, y1, z_top))
    steps.sort(key=lambda s: s[0])

    def face(pts, src, factor):
        if src:
            draw_masked_face(screen, pts, src, 1.0)
        else:
            pygame.draw.polygon(screen, darken(base_col, factor), pts)

    for _, sx0, sy0, sx1, sy1, sz_top in steps:
        N = world_to_screen(sx0, sy0, cam, ox, oy)
        E = world_to_screen(sx1, sy0, cam, ox, oy)
        S = world_to_screen(sx1, sy1, cam, ox, oy)
        W = world_to_screen(sx0, sy1, cam, ox, oy)
        z_off = sz_top * z_unit; zb = 0
        Nt = (N[0], N[1]-z_off); Et = (E[0], E[1]-z_off)
        St = (S[0], S[1]-z_off); Wt = (W[0], W[1]-z_off)
        Nb = (N[0], N[1]-zb); Eb = (E[0], E[1]-zb)
        Sb = (S[0], S[1]-zb); Wb = (W[0], W[1]-zb)
        face([Nb, Wb, Wt, Nt], left_src, 0.55)
        face([Sb, Wb, Wt, St], left_src, 0.85)
        face([Eb, Sb, St, Et], right_src, 0.80)
        face([Nb, Eb, Et, Nt], right_src, 0.65)
        if top_src:
            draw_masked_face(screen, [Nt, Et, St, Wt], top_src, 1.0)
        else:
            pygame.draw.polygon(screen, base_col, [Nt, Et, St, Wt])
            pygame.draw.polygon(screen, darken(base_col, 0.75),
                                [Nt, Et, St, Wt], 1)

def _wall_overlay(screen, p1, p2, wh, kind, dim):
    if kind == 'door':
        t0, t1 = 0.18, 0.82; u0, u1 = 0.03, 0.90; col = C_DOOR
    else:
        t0, t1 = 0.22, 0.78; u0, u1 = 0.32, 0.76; col = C_WINDOW
    def lerp(a, b, t):
        return (a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t)
    q1 = lerp(p1, p2, t0); q2 = lerp(p1, p2, t1)
    r1 = (q1[0], q1[1] - wh * u0); r2 = (q2[0], q2[1] - wh * u0)
    r3 = (q2[0], q2[1] - wh * u1); r4 = (q1[0], q1[1] - wh * u1)
    pygame.draw.polygon(screen, darken(col, dim), [r1, r2, r3, r4])
    pygame.draw.polygon(screen, darken((20,20,20), dim), [r1, r2, r3, r4], 1)

def draw_wall_h_iso(screen, cam, ox, oy, x, y, z, kind, tile=None, dim=1.0):
    z_off = z * unit_px(cam); wh = unit_px(cam) * WALL_HEIGHT_UNITS
    p1 = world_to_screen(x,     y, cam, ox, oy); p2 = world_to_screen(x + 1, y, cam, ox, oy)
    p1 = (p1[0], p1[1] - z_off); p2 = (p2[0], p2[1] - z_off)
    p1u = (p1[0], p1[1] - wh);   p2u = (p2[0], p2[1] - wh)
    quad = [p1, p2, p2u, p1u]

    textured = False
    if tile is not None:
        spr = tile.get_sprite("side_left", (64, 64))
        if spr is None: spr = tile.get_sprite("top", (64, 64))
        if spr is not None:
            draw_masked_face(screen, quad, spr, dim)
            textured = True
    if not textured:
        pygame.draw.polygon(screen, darken(C_WALL_H_FRONT, dim), quad)

    if kind in ('door', 'window'):
        _wall_overlay(screen, p1, p2, wh, kind, dim)

def draw_wall_v_iso(screen, cam, ox, oy, x, y, z, kind, tile=None, dim=1.0):
    z_off = z * unit_px(cam); wh = unit_px(cam) * WALL_HEIGHT_UNITS
    p1 = world_to_screen(x, y,     cam, ox, oy); p2 = world_to_screen(x, y + 1, cam, ox, oy)
    p1 = (p1[0], p1[1] - z_off); p2 = (p2[0], p2[1] - z_off)
    p1u = (p1[0], p1[1] - wh);   p2u = (p2[0], p2[1] - wh)
    quad = [p1, p2, p2u, p1u]

    textured = False
    if tile is not None:
        spr = tile.get_sprite("side_right", (64, 64))
        if spr is None: spr = tile.get_sprite("side_left", (64, 64))
        if spr is None: spr = tile.get_sprite("top", (64, 64))
        if spr is not None:
            draw_masked_face(screen, quad, spr, dim)
            textured = True
    if not textured:
        pygame.draw.polygon(screen, darken(C_WALL_V_FRONT, dim), quad)

    if kind in ('door', 'window'):
        _wall_overlay(screen, p1, p2, wh, kind, dim)

# ============================================================
# APP
# ============================================================
class MapEditorApp:
    TAB_LAYOUT  = 'layout'
    TAB_TEXTURE = 'texture'
    TAB_DETAILS = 'details'
    TABS = [TAB_LAYOUT, TAB_TEXTURE, TAB_DETAILS]
    TAB_LABELS = {TAB_LAYOUT: 'Map Layout',
                  TAB_TEXTURE: 'Texture Mode',
                  TAB_DETAILS: 'Detalhes'}

    LMODE_TERRAIN = 'terrain'
    LMODE_BLOCK   = 'block'
    LMODE_WALL    = 'wall'
    LMODES = [LMODE_TERRAIN, LMODE_BLOCK, LMODE_WALL]
    LMODE_LABELS = {LMODE_TERRAIN: 'Terreno',
                    LMODE_BLOCK: 'Piso/Telhado',
                    LMODE_WALL: 'Paredes'}

    DMODE_SPRITE = 'sprite'
    DMODE_EVENT  = 'event'
    DMODES = [DMODE_SPRITE, DMODE_EVENT]
    DMODE_LABELS = {DMODE_SPRITE: 'Sprites', DMODE_EVENT: 'Eventos'}

    TOOLS_MAP = {
        (TAB_LAYOUT, LMODE_TERRAIN): [TOOL_BRUSH, TOOL_ERASER, TOOL_FILL, TOOL_RECT],
        (TAB_LAYOUT, LMODE_BLOCK):   [TOOL_BRUSH, TOOL_ERASER, TOOL_FILL, TOOL_RECT],
        (TAB_LAYOUT, LMODE_WALL):    [TOOL_BRUSH, TOOL_ERASER],
        (TAB_TEXTURE, None):         [TOOL_BRUSH, TOOL_FILL, TOOL_RECT],
        (TAB_DETAILS, DMODE_SPRITE): [TOOL_BRUSH, TOOL_ERASER, TOOL_RECT],
        (TAB_DETAILS, DMODE_EVENT):  [TOOL_BRUSH],
    }

    def __init__(self):
        self.running = True
        self.project = Project()
        self.tab = self.TAB_LAYOUT
        self.layout_mode = self.LMODE_TERRAIN
        self.details_mode = self.DMODE_SPRITE
        self.active_floor = 0
        self.show_grid = False

        self.cam = Camera(); self.cam.zoom = 1.0

        ts = self.project.tileset
        self.selected_tile_id = ts.order[0] if ts.order else None
        self.terrain_height = 0
        self.terrain_form = FORM_FLAT
        self.current_wall_kind = 'wall'

        self.selected_sprite_idx = 0 if self.project.sprites else None
        self.active_sprite_idx = self.selected_sprite_idx
        self.current_event_kind = 'player_spawn'
        self.editing_event = None

        self.active_tool = TOOL_BRUSH
        self.dragging_paint = False
        self.drag_start = None
        self.hover_cell = None
        self.hover_wall = None

        self.undo_stack = []; self.redo_stack = []
        self.fields = {}; self.dropdowns = {}
        self.focused_field = None; self.expanded_dropdown = None
        self._init_widgets()

        self.save_dialog = SaveDialog()
        self.rename_dialog = InputDialog()
        self.ctx_menu = ContextMenu()

        self.autosave_dirty = False; self.autosave_timer = 0.0
        self.msg = ""; self.msg_timer = 0.0; self.msg_color = ACCENT

        self._left_hits = []; self._right_hits = []; self._top_hits = []
        self._map_hits = []
        self.pending_map_click = None

        self._sync_fields_from_map()
        self._sync_fields_from_tile()
        self._sync_fields_from_sprite()
        self._load_autosave_if_any()

    def _init_widgets(self):
        for k, lbl in [("map_name","Nome do mapa"),("map_w","Largura"),
                       ("map_h","Altura"),("num_floors","Andares")]:
            self.fields[k] = TextField(k, lbl, "", max_len=32)
        for k, lbl in [("tile_name","Nome"),("tile_category","Categoria"),
                       ("tile_height","Altura base")]:
            self.fields[k] = TextField(k, lbl, "", max_len=200)
        self.fields["sprite_name"] = TextField("sprite_name", "Nome", "", max_len=64)
        for k, lbl in [("sprite_scale","Escala"),("sprite_off_x","Offset X"),
                       ("sprite_off_y","Offset Y"),("sprite_anc_x","Ancora X"),
                       ("sprite_anc_y","Ancora Y")]:
            self.fields[k] = TextField(k, lbl, "", max_len=10)
        for k in ("ev_id","ev_name","ev_tag"):
            self.fields[k] = TextField(k, k, "", max_len=64)
        for k, lbl in [("ev_tele_map","Mapa destino"),
                       ("ev_tele_x","X"),("ev_tele_y","Y"),("ev_tele_z","Z")]:
            self.fields[k] = TextField(k, lbl, "", max_len=64)
        self.dropdowns["floor"] = Dropdown(
            "floor", "Andar",
            [(i, f"Andar {i}") for i in range(NUM_FLOORS)], 0,
            on_change=lambda v: setattr(self, 'active_floor', int(v)))
        self.dropdowns["ev_kind"] = Dropdown(
            "ev_kind", "Tipo de evento", EVENT_KINDS, 'player_spawn',
            on_change=self._on_event_kind_change)

    def _msg(self, text, color=ACCENT):
        self.msg = text; self.msg_color = color; self.msg_timer = 2.5

    def _canvas_rect(self): return pygame.Rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H)
    def _in_canvas(self, p): return self._canvas_rect().collidepoint(p)
    def _in_right(self, p): return p[0] >= WIDTH - RIGHT_W
    def _in_left(self, p): return 0 <= p[0] < LEFT_W and TOP_H <= p[1] < HEIGHT - BOTTOM_H

    def _canvas_origin(self):
        return CANVAS_X + CANVAS_W * 0.5, CANVAS_Y + CANVAS_H * 0.4

    def _iso_origin(self):
        cx, cy = self._canvas_origin()
        tw, th = tile_size(self.cam)
        return (cx - self.cam.x * tw * 0.5 + self.cam.y * tw * 0.5,
                cy - self.cam.x * th * 0.5 - self.cam.y * th * 0.5)

    def _current_tools(self):
        if self.tab == self.TAB_LAYOUT:
            return self.TOOLS_MAP.get((self.tab, self.layout_mode), [])
        if self.tab == self.TAB_DETAILS:
            return self.TOOLS_MAP.get((self.tab, self.details_mode), [])
        return self.TOOLS_MAP.get((self.tab, None), [])

    def _cell_from_pos(self, pos):
        m = self.project.active_map()
        if not m: return None
        ox, oy = self._iso_origin()
        wx, wy = screen_to_world(pos[0], pos[1], self.cam, ox, oy)
        gx = int(math.floor(wx)); gy = int(math.floor(wy))
        if m.in_bounds(gx, gy): return (gx, gy)
        return None

    def _pick_tile_at(self, mx, my):
        m = self.project.active_map()
        if not m: return None
        ox, oy = self._iso_origin()
        z = unit_px(self.cam)
        wx, wy = screen_to_world(mx, my, self.cam, ox, oy)
        R = 12
        tx_c = int(math.floor(wx)); ty_c = int(math.floor(wy))
        best = None; best_d = -1e9
        for ty in range(max(0, ty_c - R), min(m.h, ty_c + R + 1)):
            for tx in range(max(0, tx_c - R), min(m.w, tx_c + R + 1)):
                t = m.get_terrain(tx, ty)
                form = t['form']
                pick_form = form
                if form.startswith('stair_'):
                    pick_form = 'ramp_' + form.split('_')[1]
                n_h, e_h, s_h, w_h = corner_heights(pick_form, t['h'])
                N = world_to_screen(tx,   ty,   self.cam, ox, oy)
                E = world_to_screen(tx+1, ty,   self.cam, ox, oy)
                S = world_to_screen(tx+1, ty+1, self.cam, ox, oy)
                W = world_to_screen(tx,   ty+1, self.cam, ox, oy)
                pts = [(N[0], N[1]-n_h*z), (E[0], E[1]-e_h*z),
                       (S[0], S[1]-s_h*z), (W[0], W[1]-w_h*z)]
                if point_in_poly(mx, my, pts):
                    d = tx + ty + t['h'] * 0.01
                    if d > best_d: best_d = d; best = (tx, ty)
        return best

    def _pick_tile_at_height(self, mx, my, target_z):
        m = self.project.active_map()
        if not m: return None
        ox, oy = self._iso_origin()
        z_unit = unit_px(self.cam)
        wx, wy = screen_to_world(mx, my + target_z * z_unit, self.cam, ox, oy)
        gx = int(math.floor(wx)); gy = int(math.floor(wy))
        if m.in_bounds(gx, gy): return (gx, gy)
        return None

    def _pick_wall_at(self, mx, my, snap_dist=26.0):
        m = self.project.active_map()
        if not m: return None
        ox, oy = self._iso_origin()
        z = self.active_floor; z_off = z * unit_px(self.cam)
        wx, wy = screen_to_world(mx, my + z_off, self.cam, ox, oy)
        tx = int(math.floor(wx)); ty = int(math.floor(wy))
        candidates = [('h', tx, ty), ('v', tx, ty),
                      ('h', tx, ty + 1), ('v', tx + 1, ty)]
        best = None; best_d2 = snap_dist * snap_dist
        for kind, x, y in candidates:
            if kind == 'h':
                p1 = world_to_screen(x,     y, self.cam, ox, oy)
                p2 = world_to_screen(x + 1, y, self.cam, ox, oy)
            else:
                p1 = world_to_screen(x, y,     self.cam, ox, oy)
                p2 = world_to_screen(x, y + 1, self.cam, ox, oy)
            p1 = (p1[0], p1[1] - z_off); p2 = (p2[0], p2[1] - z_off)
            d2 = seg_dist_sq(mx, my, p1[0], p1[1], p2[0], p2[1])
            if d2 < best_d2: best_d2 = d2; best = (kind, x, y)
        return best

    # --------- undo / autosave ---------
    def _snapshot(self):
        m = self.project.active_map()
        if not m: return None
        return {"map": m.name,
                "terrain": {k: dict(v) for k, v in m.terrain.items()},
                "blocks": dict(m.blocks),
                "walls_h": dict(m.walls_h), "walls_v": dict(m.walls_v),
                "objects": dict(m.objects), "passability": dict(m.passability),
                "events": [ev.to_dict() for ev in m.events],
                "w": m.w, "h": m.h}
    def _push_undo(self):
        s = self._snapshot()
        if s is None: return
        self.undo_stack.append(s)
        if len(self.undo_stack) > 40: self.undo_stack = self.undo_stack[-40:]
        self.redo_stack.clear()
    def _restore(self, s):
        m = self.project.maps.get(s["map"])
        if not m: return
        m.terrain = {k: dict(v) for k, v in s["terrain"].items()}
        m.blocks = dict(s["blocks"])
        m.walls_h = dict(s.get("walls_h", {})); m.walls_v = dict(s.get("walls_v", {}))
        m.objects = dict(s["objects"]); m.passability = dict(s["passability"])
        m.events = [GameEvent.from_dict(e) for e in s["events"]]
        m.w = s["w"]; m.h = s["h"]
    def _undo(self):
        if not self.undo_stack: self._msg("Nada para desfazer.", TEXT_DIM); return
        self.redo_stack.append(self._snapshot())
        self._restore(self.undo_stack.pop())
        self._mark_dirty(); self._msg("Desfeito.", TEXT_DIM)
    def _redo(self):
        if not self.redo_stack: self._msg("Nada para refazer.", TEXT_DIM); return
        self.undo_stack.append(self._snapshot())
        self._restore(self.redo_stack.pop())
        self._mark_dirty(); self._msg("Refeito.", TEXT_DIM)

    def _mark_dirty(self):
        self.autosave_dirty = True; self.autosave_timer = 0.8
    def _do_autosave(self):
        try:
            with open(AUTOSAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.project.to_dict(), f, ensure_ascii=False)
        except Exception: pass
    def _load_autosave_if_any(self):
        if not os.path.isfile(AUTOSAVE_PATH): return
        try:
            with open(AUTOSAVE_PATH, "r", encoding="utf-8") as f:
                self.project = Project.from_dict(json.load(f))
            ts = self.project.tileset
            self.selected_tile_id = ts.order[0] if ts.order else None
            self.selected_sprite_idx = 0 if self.project.sprites else None
            self.active_sprite_idx = self.selected_sprite_idx
            self._sync_fields_from_map()
            self._sync_fields_from_tile()
            self._sync_fields_from_sprite()
            self._msg("Autosave carregado.", TEXT_DIM)
        except Exception as e: print(f"[Autosave] {e}")

    # --------- sync ---------
    def _sync_fields_from_map(self):
        m = self.project.active_map()
        if not m: return
        self.fields["map_name"].value = m.name
        self.fields["map_w"].value = str(m.w)
        self.fields["map_h"].value = str(m.h)
        self.fields["num_floors"].value = str(m.num_floors)
        self.dropdowns["floor"].set_options(
            [(i, f"Andar {i}") for i in range(m.num_floors)])
        self.dropdowns["floor"].value = min(self.active_floor, m.num_floors-1)
    def _sync_fields_from_tile(self):
        tid = self.selected_tile_id
        if not tid: return
        t = self.project.tileset.get(tid)
        if not t: return
        self.fields["tile_name"].value = t.name
        self.fields["tile_category"].value = t.category
        self.fields["tile_height"].value = str(t.height)
    def _sync_fields_from_sprite(self):
        idx = getattr(self, 'selected_sprite_idx', None)
        if idx is None or idx < 0 or idx >= len(self.project.sprites): return
        sp = self.project.sprites[idx]
        self.fields["sprite_name"].value = sp.name
        self.fields["sprite_scale"].value = f"{sp.scale:.2f}"
        self.fields["sprite_off_x"].value = f"{sp.offset_x:.0f}"
        self.fields["sprite_off_y"].value = f"{sp.offset_y:.0f}"
        self.fields["sprite_anc_x"].value = f"{sp.anchor_x:.2f}"
        self.fields["sprite_anc_y"].value = f"{sp.anchor_y:.2f}"
    def _sync_fields_from_event(self, ev):
        self.editing_event = ev
        if not ev: return
        self.fields["ev_id"].value = str(ev.id)
        self.fields["ev_name"].value = ev.name
        self.fields["ev_tag"].value = ev.tag
        self.dropdowns["ev_kind"].value = ev.kind
        d = ev.data or {}
        if ev.kind == 'teleport':
            self.fields["ev_tele_map"].value = str(d.get("target_map", ""))
            self.fields["ev_tele_x"].value = str(d.get("target_x", 0))
            self.fields["ev_tele_y"].value = str(d.get("target_y", 0))
            self.fields["ev_tele_z"].value = str(d.get("target_z", 0))
        else:
            for fk in ("ev_tele_map","ev_tele_x","ev_tele_y","ev_tele_z"):
                self.fields[fk].value = ""

    def _on_event_kind_change(self, kind):
        if self.editing_event:
            self.editing_event.kind = kind
            self._sync_fields_from_event(self.editing_event)

    # --------- apply ---------
    def _apply_map_fields(self):
        m = self.project.active_map()
        if not m: return
        old_name = m.name
        new_name = self.fields["map_name"].value.strip() or m.name
        try: nw = int(self.fields["map_w"].value); nh = int(self.fields["map_h"].value)
        except Exception: nw, nh = m.w, m.h
        nw = clamp(nw, 4, 200); nh = clamp(nh, 4, 200)
        if (nw, nh) != (m.w, m.h):
            self._push_undo(); m.resize(nw, nh)
            self._msg(f"Redimensionado: {nw}x{nh}", SUCCESS)
        if new_name != old_name:
            del self.project.maps[old_name]
            m.name = self.project.unique_map_name(new_name)
            self.project.maps[m.name] = m
            for c in self.project.maps.values():
                if c.parent == old_name: c.parent = m.name
            self.project.active_map_name = m.name
        try: m.num_floors = clamp(int(self.fields["num_floors"].value), 1, 20)
        except Exception: pass
        self._mark_dirty(); self._sync_fields_from_map()
    def _apply_tile_fields(self):
        tid = self.selected_tile_id
        if not tid: return
        t = self.project.tileset.get(tid)
        if not t: return
        t.name = self.fields["tile_name"].value.strip() or t.id
        t.category = self.fields["tile_category"].value.strip() or "Geral"
        try: t.height = int(self.fields["tile_height"].value or 0)
        except Exception: pass
        self._mark_dirty(); self._msg("Tile atualizado.", SUCCESS)
    def _apply_sprite_fields(self):
        idx = self.selected_sprite_idx
        if idx is None or idx < 0 or idx >= len(self.project.sprites): return
        sp = self.project.sprites[idx]
        sp.name = self.fields["sprite_name"].value.strip() or sp.name
        try: sp.scale = max(0.05, float(self.fields["sprite_scale"].value))
        except Exception: pass
        try: sp.offset_x = float(self.fields["sprite_off_x"].value)
        except Exception: pass
        try: sp.offset_y = float(self.fields["sprite_off_y"].value)
        except Exception: pass
        try: sp.anchor_x = clamp(float(self.fields["sprite_anc_x"].value), 0, 1)
        except Exception: pass
        try: sp.anchor_y = clamp(float(self.fields["sprite_anc_y"].value), 0, 1)
        except Exception: pass
        self._mark_dirty(); self._msg("Sprite atualizado.", SUCCESS)
    def _apply_event_fields(self):
        ev = self.editing_event
        if not ev: return
        try: ev.id = int(self.fields["ev_id"].value or 0)
        except Exception: pass
        ev.name = self.fields["ev_name"].value.strip()
        ev.tag = self.fields["ev_tag"].value.strip()
        ev.kind = self.dropdowns["ev_kind"].value
        if ev.kind == 'teleport':
            ev.data["target_map"] = self.fields["ev_tele_map"].value.strip()
            for key, fk in (("target_x","ev_tele_x"),
                            ("target_y","ev_tele_y"),
                            ("target_z","ev_tele_z")):
                try: ev.data[key] = int(self.fields[fk].value or 0)
                except Exception: ev.data[key] = 0
        self._mark_dirty(); self._msg("Evento atualizado.", SUCCESS)
    def _apply_current_field_group(self):
        f = self.focused_field
        if not f: return
        if f.key.startswith("tile_"): self._apply_tile_fields()
        elif f.key.startswith("sprite_"): self._apply_sprite_fields()
        elif f.key.startswith("ev_"): self._apply_event_fields()
        elif f.key.startswith("map_") or f.key == "num_floors": self._apply_map_fields()

    # --------- save/load ---------
    def _open_save_dialog(self): self.save_dialog.open("meu_projeto")
    def _do_save(self):
        name = self.save_dialog.text.strip() or "meu_projeto"
        safe = safe_filename(name, "meu_projeto")
        fp = os.path.join(EXPORTS_DIR, f"{safe}.json")
        try:
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(self.project.to_dict(), f, indent=2, ensure_ascii=False)
            self._msg(f"Salvo: {safe}.json", SUCCESS)
        except Exception as ex: self._msg(f"Erro: {ex}", DANGER)
    def _load_project(self):
        files = sorted([f for f in os.listdir(EXPORTS_DIR)
                        if f.endswith(".json") and not f.startswith("_")])
        if not files: self._msg("Nenhum projeto salvo.", DANGER); return
        fp = os.path.join(EXPORTS_DIR, files[-1])
        try:
            with open(fp, "r", encoding="utf-8") as f:
                self.project = Project.from_dict(json.load(f))
            ts = self.project.tileset
            self.selected_tile_id = ts.order[0] if ts.order else None
            self.selected_sprite_idx = 0 if self.project.sprites else None
            self.active_sprite_idx = self.selected_sprite_idx
            self._sync_fields_from_map()
            self._sync_fields_from_tile()
            self._sync_fields_from_sprite()
            self._msg(f"Carregado: {files[-1]}", SUCCESS)
        except Exception as ex: self._msg(f"Erro: {ex}", DANGER)

    # --------- mapas ---------
    def _switch_map(self, name):
        if name not in self.project.maps: return
        self.project.active_map_name = name
        self.active_floor = min(self.active_floor, self.project.active_map().num_floors - 1)
        self._sync_fields_from_map(); self._msg(f"Mapa: {name}", ACCENT)
    def _new_map(self, parent=None):
        name = self.project.unique_map_name("mapa")
        m = TileMap(name, 24, 20); m.parent = parent
        self.project.add_map(m); self.active_floor = 0
        self._sync_fields_from_map(); self._mark_dirty()
        self._msg(f"Novo mapa: {name}", ACCENT)
    def _del_map(self, name=None):
        name = name or self.project.active_map_name
        if len(self.project.maps) <= 1:
            self._msg("Não pode remover o último mapa.", DANGER); return
        for m in self.project.maps.values():
            if m.parent == name: m.parent = None
        del self.project.maps[name]
        self.project.active_map_name = next(iter(self.project.maps))
        self.active_floor = 0
        self._sync_fields_from_map(); self._mark_dirty()
        self._msg(f"Removido: {name}", TEXT_DIM)
    def _open_rename(self, name):
        m = self.project.maps.get(name)
        if not m: return
        def do_rename(new_name):
            new_name = new_name.strip()
            if not new_name or new_name == name: return
            del self.project.maps[name]
            m.name = self.project.unique_map_name(new_name)
            self.project.maps[m.name] = m
            for c in self.project.maps.values():
                if c.parent == name: c.parent = m.name
            if self.project.active_map_name == name:
                self.project.active_map_name = m.name
            self._mark_dirty(); self._sync_fields_from_map()
        self.rename_dialog.open("RENOMEAR MAPA", "Novo nome:", name, do_rename)
    def _move_map_to(self, child, parent):
        if child == parent: return
        cur = parent
        while cur is not None:
            if cur == child:
                self._msg("Não pode criar ciclo.", DANGER); return
            cur = self.project.maps[cur].parent if cur in self.project.maps else None
        self.project.maps[child].parent = parent
        self._mark_dirty(); self._msg(f"{child} → filho de {parent}", SUCCESS)

    # --------- tiles ---------
    def _new_tile(self):
        tid = self.project.tileset.unique_id("tile")
        t = Tile(tid, "Novo tile", DEFAULT_TILE_COL, True, "Geral", height=0)
        self.project.tileset.add(t)
        self.selected_tile_id = tid
        self._sync_fields_from_tile(); self._mark_dirty()
        self._msg(f"Tile criado: {tid}", ACCENT)
    def _del_tile(self):
        tid = self.selected_tile_id
        if not tid: return
        if len(self.project.tileset.tiles) <= 1:
            self._msg("Não pode remover o último tile.", DANGER); return
        self.project.tileset.remove(tid)
        fallback = (self.project.tileset.order[0]
                    if self.project.tileset.order else DEFAULT_TILE_ID)
        for m in self.project.maps.values():
            for k, t in list(m.terrain.items()):
                if t['tile_id'] == tid: t['tile_id'] = fallback
            for k in list(m.blocks.keys()):
                if m.blocks[k] == tid: del m.blocks[k]
            for k, v in list(m.walls_h.items()):
                kk, tid_ = wall_val(v)
                if tid_ == tid: m.walls_h[k] = (kk, None)
            for k, v in list(m.walls_v.items()):
                kk, tid_ = wall_val(v)
                if tid_ == tid: m.walls_v[k] = (kk, None)
        self.selected_tile_id = (self.project.tileset.order[0]
                                 if self.project.tileset.order else None)
        self._sync_fields_from_tile(); self._mark_dirty()
    def _pick_slot_image(self, slot):
        path = pick_image_file()
        if not path: return
        t = self.project.tileset.get(self.selected_tile_id)
        if not t: return
        if t.set_slot_from_file(slot, path):
            self._mark_dirty(); self._msg(f"{slot}.png salvo", SUCCESS)
    def _remove_slot_image(self, slot):
        t = self.project.tileset.get(self.selected_tile_id)
        if not t: return
        t.remove_slot(slot); self._mark_dirty()
    def _open_tile_folder(self):
        t = self.project.tileset.get(self.selected_tile_id)
        if not t: return
        try: os.makedirs(t.folder, exist_ok=True)
        except Exception: pass
        open_folder(t.folder)

    # --------- sprites ---------
    def _import_sprite(self):
        path = pick_image_file()
        if not path: return
        try:
            base = os.path.splitext(os.path.basename(path))[0]
            base = safe_filename(base, "sprite")
            dst = unique_path_in_dir(SPRITES_DIR, base, ".png")
            img = load_sprite_surface(path)
            pygame.image.save(img, dst)
            name = os.path.basename(dst)
            sp = CustomSprite(name, dst)
            idx = self.project.add_sprite(sp)
            self.selected_sprite_idx = idx; self.active_sprite_idx = idx
            self._sync_fields_from_sprite(); self._mark_dirty()
            self._msg(f"Sprite importado: {name}", SUCCESS)
        except Exception as e:
            self._msg(f"Erro: {e}", DANGER)
    def _remove_sprite(self):
        idx = self.selected_sprite_idx
        if idx is None: return
        self.project.remove_sprite(idx)
        self.selected_sprite_idx = (0 if self.project.sprites else None)
        self.active_sprite_idx = self.selected_sprite_idx
        self._sync_fields_from_sprite(); self._mark_dirty()
        self._msg("Sprite removido.", TEXT_DIM)
    def _open_sprite_folder(self):
        idx = self.selected_sprite_idx
        if idx is None:
            open_folder(SPRITES_DIR); return
        sp = self.project.sprites[idx]
        folder = os.path.dirname(sp.path) if sp.path else SPRITES_DIR
        if os.path.isdir(folder): open_folder(folder)
        else: open_folder(SPRITES_DIR)

    def _del_event(self, ev):
        m = self.project.active_map()
        if not m: return
        self._push_undo(); m.remove_event(ev)
        if self.editing_event is ev: self.editing_event = None
        self._mark_dirty(); self._msg("Evento deletado.", TEXT_DIM)

    def _set_event_sprite(self, ev, idx):
        ev.sprite_idx = idx
        self._mark_dirty()
        if idx is None: self._msg("Sprite do evento removido.", TEXT_DIM)
        else:
            try: self._msg(f"Sprite do evento: {self.project.sprites[idx].name}", SUCCESS)
            except Exception: pass

    # ================================================================
    # FERRAMENTAS - LAYOUT
    # ================================================================
    def _paint_terrain(self, x, y, erase=False):
        m = self.project.active_map()
        if not m.in_bounds(x, y): return
        if erase:
            m.set_terrain(x, y, default_terrain())
        else:
            t = m.get_terrain(x, y)
            t['tile_id'] = self.selected_tile_id or t['tile_id']
            t['h'] = self.terrain_height
            t['form'] = self.terrain_form

    def _flood_fill_terrain(self, x, y, erase=False):
        m = self.project.active_map()
        if not m.in_bounds(x, y): return
        start_tid = m.get_terrain(x, y)['tile_id']
        queue = deque([(x, y)]); visited = set()
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in visited: continue
            if not m.in_bounds(cx, cy): continue
            t = m.get_terrain(cx, cy)
            if t['tile_id'] != start_tid: continue
            visited.add((cx, cy))
            self._paint_terrain(cx, cy, erase=erase)
            queue.append((cx+1, cy)); queue.append((cx-1, cy))
            queue.append((cx, cy+1)); queue.append((cx, cy-1))

    def _rect_terrain(self, x0, y0, x1, y1, erase=False):
        xa, xb = sorted([x0, x1]); ya, yb = sorted([y0, y1])
        for yy in range(ya, yb+1):
            for xx in range(xa, xb+1):
                self._paint_terrain(xx, yy, erase=erase)

    def _paint_block(self, x, y, erase=False):
        m = self.project.active_map()
        if not m.in_bounds(x, y): return
        z = self.active_floor
        if erase: m.blocks.pop((x, y, z), None)
        else:
            if self.selected_tile_id is None: return
            m.blocks[(x, y, z)] = self.selected_tile_id

    def _flood_fill_block(self, x, y, erase=False):
        m = self.project.active_map()
        if not m.in_bounds(x, y): return
        z = self.active_floor
        start_tid = m.blocks.get((x, y, z))
        queue = deque([(x, y)]); visited = set()
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in visited: continue
            if not m.in_bounds(cx, cy): continue
            if m.blocks.get((cx, cy, z)) != start_tid: continue
            visited.add((cx, cy))
            self._paint_block(cx, cy, erase=erase)
            queue.append((cx+1, cy)); queue.append((cx-1, cy))
            queue.append((cx, cy+1)); queue.append((cx, cy-1))

    def _rect_block(self, x0, y0, x1, y1, erase=False):
        xa, xb = sorted([x0, x1]); ya, yb = sorted([y0, y1])
        for yy in range(ya, yb+1):
            for xx in range(xa, xb+1):
                self._paint_block(xx, yy, erase=erase)

    def _paint_wall_at(self, mx, my, erase=False):
        m = self.project.active_map()
        hit = self._pick_wall_at(mx, my)
        if not hit: return False
        kind, x, y = hit
        z = self.active_floor
        d = m.walls_h if kind == 'h' else m.walls_v
        key = (x, y, z)
        if erase:
            if key in d:
                del d[key]; return True
            return False
        new_tid = self.selected_tile_id
        if key not in d:
            d[key] = (self.current_wall_kind, new_tid)
            return True
        cur_kind, cur_tid = wall_val(d[key])
        if cur_kind != self.current_wall_kind or cur_tid != new_tid:
            keep_tid = cur_tid if cur_tid else new_tid
            if cur_kind != self.current_wall_kind:
                d[key] = (self.current_wall_kind, keep_tid)
            else:
                d[key] = (cur_kind, new_tid)
            return True
        return False

    # ================================================================
    # FERRAMENTAS - TEXTURE MODE
    # ================================================================
    def _apply_texture_terrain(self, x, y):
        m = self.project.active_map()
        if not m.in_bounds(x, y): return False
        if self.selected_tile_id is None: return False
        t = m.get_terrain(x, y)
        if t['tile_id'] == self.selected_tile_id: return False
        t['tile_id'] = self.selected_tile_id
        return True

    def _apply_texture_block(self, x, y, z):
        m = self.project.active_map()
        if not m.in_bounds(x, y): return False
        k = (x, y, z)
        if k not in m.blocks: return False
        if self.selected_tile_id is None: return False
        if m.blocks[k] == self.selected_tile_id: return False
        m.blocks[k] = self.selected_tile_id
        return True

    def _apply_texture_wall(self, mx, my):
        m = self.project.active_map()
        hit = self._pick_wall_at(mx, my)
        if not hit: return False
        kind, x, y = hit
        z = self.active_floor
        d = m.walls_h if kind == 'h' else m.walls_v
        key = (x, y, z)
        if key not in d: return False
        cur_kind, cur_tid = wall_val(d[key])
        if cur_tid == self.selected_tile_id: return False
        d[key] = (cur_kind, self.selected_tile_id)
        return True

    def _apply_texture_at(self, pos):
        mx, my = pos
        m = self.project.active_map()
        if not m: return False
        if self._apply_texture_wall(mx, my):
            return True
        cell_b = self._pick_tile_at_height(mx, my, self.active_floor)
        if cell_b and (cell_b[0], cell_b[1], self.active_floor) in m.blocks:
            return self._apply_texture_block(cell_b[0], cell_b[1], self.active_floor)
        cell_t = self._pick_tile_at(mx, my) or self._cell_from_pos(pos)
        if cell_t:
            return self._apply_texture_terrain(cell_t[0], cell_t[1])
        return False

    def _texture_rect(self, x0, y0, x1, y1):
        changed = False
        xa, xb = sorted([x0, x1]); ya, yb = sorted([y0, y1])
        m = self.project.active_map()
        z = self.active_floor
        for yy in range(ya, yb+1):
            for xx in range(xa, xb+1):
                if (xx, yy, z) in m.blocks:
                    if self._apply_texture_block(xx, yy, z): changed = True
                else:
                    if self._apply_texture_terrain(xx, yy): changed = True
        return changed

    def _texture_fill(self, x, y):
        m = self.project.active_map()
        if not m.in_bounds(x, y): return False
        z = self.active_floor
        target_new = self.selected_tile_id
        if target_new is None: return False
        is_block = (x, y, z) in m.blocks
        if is_block:
            old = m.blocks.get((x, y, z))
            def get_val(cx, cy): return m.blocks.get((cx, cy, z))
            def set_val(cx, cy): m.blocks[(cx, cy, z)] = target_new
        else:
            old = m.get_terrain(x, y)['tile_id']
            def get_val(cx, cy): return m.get_terrain(cx, cy)['tile_id']
            def set_val(cx, cy): m.get_terrain(cx, cy)['tile_id'] = target_new
        if old == target_new: return False
        changed = False
        queue = deque([(x, y)]); visited = set()
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in visited: continue
            if not m.in_bounds(cx, cy): continue
            if get_val(cx, cy) != old: continue
            visited.add((cx, cy)); set_val(cx, cy); changed = True
            queue.append((cx+1, cy)); queue.append((cx-1, cy))
            queue.append((cx, cy+1)); queue.append((cx, cy-1))
        return changed

    # ================================================================
    # FERRAMENTAS - DETALHES
    # ================================================================
    def _paint_object(self, x, y, erase=False):
        m = self.project.active_map()
        if not m.in_bounds(x, y): return
        if erase: m.set_object(x, y, self.active_floor, None)
        else:
            if self.selected_sprite_idx is None: return
            m.set_object(x, y, self.active_floor, self.selected_sprite_idx)

    def _rect_object(self, x0, y0, x1, y1, erase=False):
        xa, xb = sorted([x0, x1]); ya, yb = sorted([y0, y1])
        for yy in range(ya, yb+1):
            for xx in range(xa, xb+1):
                self._paint_object(xx, yy, erase=erase)

    def _apply_paint_at(self, pos, erase=False):
        mx, my = pos
        if self.tab == self.TAB_LAYOUT:
            if self.layout_mode == self.LMODE_TERRAIN:
                cell = self._pick_tile_at(mx, my) or self._cell_from_pos(pos)
                if cell: self._paint_terrain(cell[0], cell[1], erase=erase)
            elif self.layout_mode == self.LMODE_BLOCK:
                cell = self._pick_tile_at_height(mx, my, self.active_floor)
                if cell: self._paint_block(cell[0], cell[1], erase=erase)
            elif self.layout_mode == self.LMODE_WALL:
                self._paint_wall_at(mx, my, erase=erase)
        elif self.tab == self.TAB_TEXTURE:
            if not erase:
                self._apply_texture_at(pos)
        elif self.tab == self.TAB_DETAILS:
            if self.details_mode == self.DMODE_SPRITE:
                cell = self._pick_tile_at(mx, my) or self._cell_from_pos(pos)
                if cell: self._paint_object(cell[0], cell[1], erase=erase)
            elif self.details_mode == self.DMODE_EVENT and not erase:
                cell = self._pick_tile_at(mx, my) or self._cell_from_pos(pos)
                if cell:
                    m = self.project.active_map()
                    if m and not m.event_at(cell[0], cell[1]):
                        ev = GameEvent(self.current_event_kind, cell[0], cell[1],
                                       eid=m.next_event_id())
                        m.events.append(ev)
                        self._sync_fields_from_event(ev)
                        self._mark_dirty()

    # ================================================================
    # EVENTOS PYGAME
    # ================================================================
    def handle_events(self, events):
        for e in events:
            if e.type == pygame.QUIT: self.running = False; return
            if self.rename_dialog.active:
                self.rename_dialog.handle_event(e); continue
            if self.save_dialog.active:
                act = self.save_dialog.handle_event(e)
                if act == "save": self._do_save(); self.save_dialog.close()
                elif act == "cancel": self.save_dialog.close()
                continue
            if self.ctx_menu.active:
                cb = self.ctx_menu.handle_event(e)
                if cb: cb()
                continue
            if self.expanded_dropdown:
                if e.type == pygame.MOUSEBUTTONDOWN:
                    dd = self.dropdowns.get(self.expanded_dropdown)
                    if dd is not None:
                        if dd.handle_click(e.pos):
                            if not dd.expanded: self.expanded_dropdown = None
                            continue
                        self.expanded_dropdown = None
                    else: self.expanded_dropdown = None
            if self.focused_field:
                if e.type == pygame.KEYDOWN:
                    if self.focused_field.handle_key(e):
                        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            self._apply_current_field_group()
                        continue
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if not self.focused_field.rect.collidepoint(e.pos):
                        self._apply_current_field_group()
                        self.focused_field.focused = False; self.focused_field = None

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if self.drag_start: self.drag_start = None
                    elif self.editing_event: self.editing_event = None
                    else: self.running = False
                    return
                if e.key == pygame.K_TAB:
                    idx = self.TABS.index(self.tab)
                    self.tab = self.TABS[(idx + 1) % len(self.TABS)]
                    if not self._mode_supports(self.active_tool):
                        self.active_tool = TOOL_BRUSH
                    if self.tab == self.TAB_DETAILS and self.editing_event:
                        self._sync_fields_from_event(self.editing_event)
                if e.key == pygame.K_g: self.show_grid = not self.show_grid
                if e.key == pygame.K_i: self._import_sprite()
                if e.key == pygame.K_z and (e.mod & pygame.KMOD_CTRL): self._undo()
                if e.key == pygame.K_y and (e.mod & pygame.KMOD_CTRL): self._redo()
                if e.key == pygame.K_l: self._load_project()
                if e.key == pygame.K_b:
                    if self._mode_supports(TOOL_BRUSH): self.active_tool = TOOL_BRUSH
                if e.key == pygame.K_e:
                    if self._mode_supports(TOOL_ERASER): self.active_tool = TOOL_ERASER
                if e.key == pygame.K_f:
                    if self._mode_supports(TOOL_FILL): self.active_tool = TOOL_FILL
                if e.key == pygame.K_r:
                    if self._mode_supports(TOOL_RECT): self.active_tool = TOOL_RECT

            if e.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self._in_canvas((mx, my)): self._zoom_at((mx, my), e.y)
            if e.type == pygame.MOUSEMOTION:
                self._on_motion(e.pos)
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1: self._on_left_down(e.pos)
                elif e.button == 3: self._on_right_down(e.pos)
            if e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1: self._on_left_up(e.pos)

    def _mode_supports(self, tool):
        return tool in self._current_tools()

    def _zoom_at(self, mp, delta):
        old = self.cam.zoom
        new = clamp(old * (1.15 ** delta), 0.3, 3.5)
        if abs(new - old) < 0.001: return
        mx, my = mp
        ox, oy = self._iso_origin()
        wx, wy = screen_to_world(mx, my, self.cam, ox, oy)
        self.cam.zoom = new
        new_ox, new_oy = self._iso_origin()
        sx2, sy2 = world_to_screen(wx, wy, self.cam, new_ox, new_oy)
        self.cam.x += (sx2 - mx) / (BASE_TILE_W * self.cam.zoom) * 0.5
        self.cam.y += (sy2 - my) / (BASE_TILE_H * self.cam.zoom) * 0.5

    def _on_motion(self, pos):
        if not self._in_canvas(pos):
            self.hover_cell = None; self.hover_wall = None
            return
        mx, my = pos
        if self.tab == self.TAB_LAYOUT and self.layout_mode == self.LMODE_WALL:
            self.hover_wall = self._pick_wall_at(mx, my)
            self.hover_cell = None
        else:
            self.hover_wall = None
            if (self.tab == self.TAB_LAYOUT and
                self.layout_mode == self.LMODE_BLOCK):
                self.hover_cell = self._pick_tile_at_height(mx, my, self.active_floor)
            else:
                cell = self._pick_tile_at(mx, my)
                if cell is None:
                    cell = self._cell_from_pos(pos)
                self.hover_cell = cell
        if self.dragging_paint and self.active_tool in (TOOL_BRUSH, TOOL_ERASER):
            self._apply_paint_at(pos, erase=(self.active_tool == TOOL_ERASER))

    def _on_left_down(self, pos):
        for r, cb in self._top_hits:
            if r.collidepoint(pos): cb(); return
        if self._in_left(pos):
            for item in self._left_hits:
                if item[0].collidepoint(pos): item[1](); return
            return
        if self._in_right(pos):
            for key, dd in self.dropdowns.items():
                if not dd.active_this_frame: continue
                if dd.rect.collidepoint(pos):
                    dd.expanded = True; self.expanded_dropdown = key; return
            prefixes = ["map_", "num_floors", "tile_", "sprite_", "ev_"]
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
            for r, cb in self._right_hits:
                if r.collidepoint(pos): cb(); return
            return

        if not self._in_canvas(pos): return
        m = self.project.active_map()
        if not m: return
        tool = self.active_tool

        if tool == TOOL_RECT:
            if (self.tab == self.TAB_LAYOUT and
                self.layout_mode == self.LMODE_BLOCK):
                cell = self._pick_tile_at_height(pos[0], pos[1], self.active_floor)
            else:
                cell = self._pick_tile_at(pos[0], pos[1]) or self._cell_from_pos(pos)
            if cell: self.drag_start = cell
            return

        if tool == TOOL_FILL:
            self._push_undo()
            if self.tab == self.TAB_LAYOUT:
                if self.layout_mode == self.LMODE_TERRAIN:
                    cell = self._pick_tile_at(pos[0], pos[1]) or self._cell_from_pos(pos)
                    if cell: self._flood_fill_terrain(cell[0], cell[1])
                elif self.layout_mode == self.LMODE_BLOCK:
                    cell = self._pick_tile_at_height(pos[0], pos[1], self.active_floor)
                    if cell: self._flood_fill_block(cell[0], cell[1])
            elif self.tab == self.TAB_TEXTURE:
                cell = self._pick_tile_at(pos[0], pos[1]) or self._cell_from_pos(pos)
                if cell: self._texture_fill(cell[0], cell[1])
            self._mark_dirty()
            return

        self._push_undo()
        self.dragging_paint = True
        self._apply_paint_at(pos, erase=(tool == TOOL_ERASER))
        self._mark_dirty()

    def _on_left_up(self, pos):
        if self.pending_map_click:
            name, start = self.pending_map_click
            dx = pos[0]-start[0]; dy = pos[1]-start[1]
            if (dx*dx+dy*dy) ** 0.5 > 6:
                for r, target in self._map_hits:
                    if r.collidepoint(pos) and target != name:
                        self._move_map_to(name, target); break
            else: self._switch_map(name)
            self.pending_map_click = None

        if self.drag_start is not None and self.active_tool == TOOL_RECT:
            if (self.tab == self.TAB_LAYOUT and
                self.layout_mode == self.LMODE_BLOCK):
                cell = self._pick_tile_at_height(pos[0], pos[1], self.active_floor)
            else:
                cell = self._pick_tile_at(pos[0], pos[1]) or self._cell_from_pos(pos)
            x0, y0 = self.drag_start
            x1, y1 = cell if cell else (x0, y0)
            self._push_undo()
            if self.tab == self.TAB_LAYOUT:
                if self.layout_mode == self.LMODE_TERRAIN:
                    self._rect_terrain(x0, y0, x1, y1, erase=False)
                elif self.layout_mode == self.LMODE_BLOCK:
                    self._rect_block(x0, y0, x1, y1, erase=False)
            elif self.tab == self.TAB_TEXTURE:
                self._texture_rect(x0, y0, x1, y1)
            elif self.tab == self.TAB_DETAILS and self.details_mode == self.DMODE_SPRITE:
                self._rect_object(x0, y0, x1, y1, erase=False)
            self._mark_dirty()
            self.drag_start = None

        self.dragging_paint = False

    def _on_right_down(self, pos):
        if self._in_left(pos):
            for item in self._left_hits:
                if len(item) < 3: continue
                r, payload, kind = item
                if not r.collidepoint(pos): continue
                if kind == "map":
                    name = payload
                    items = [("Renomear…", lambda n=name: self._open_rename(n)),
                             ("Deletar", lambda n=name: self._del_map(n))]
                    others = [n for n in self.project.maps if n != name]
                    if others:
                        sub = [(f"→ {p}",
                                (lambda c=name, pp=p: self._move_map_to(c, pp)))
                               for p in others[:10]]
                        items.append(("Mover para…",
                                      lambda s=sub, pp=pos: self.ctx_menu.open(
                                          (min(pp[0]+180, WIDTH-220), pp[1]), s)))
                    self.ctx_menu.open(pos, items); return

        if not self._in_canvas(pos): return
        m = self.project.active_map()
        if not m: return
        self._push_undo()
        self._apply_paint_at(pos, erase=True)
        self._mark_dirty()

        if self.tab == self.TAB_DETAILS and self.details_mode == self.DMODE_EVENT:
            cell = self._cell_from_pos(pos)
            if cell:
                ev = m.event_at(cell[0], cell[1])
                if ev:
                    items = [("Editar", lambda e=ev: self._sync_fields_from_event(e)),
                             ("Deletar", lambda e=ev: self._del_event(e))]
                    self.ctx_menu.open(pos, items)

    def update(self, dt):
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0: self.msg = ""
        if self.autosave_dirty:
            self.autosave_timer -= dt
            if self.autosave_timer <= 0:
                self._do_autosave(); self.autosave_dirty = False
        if self.save_dialog.active or self.rename_dialog.active: return
        if self.focused_field or self.expanded_dropdown: return

        keys = pygame.key.get_pressed()
        spd = CAM_SPEED / self.cam.zoom * dt
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]: spd *= 2.5

        ddx = ddy = 0.0
        if keys[pygame.K_a]: ddx -= 1
        if keys[pygame.K_d]: ddx += 1
        if keys[pygame.K_w]: ddy -= 1
        if keys[pygame.K_s]: ddy += 1
        if ddx or ddy:
            m = math.hypot(ddx, ddy); ddx /= m; ddy /= m
            wdx = ddx * 0.5 + ddy * 0.5
            wdy = -ddx * 0.5 + ddy * 0.5
            mm = math.hypot(wdx, wdy)
            if mm > 1e-6: wdx /= mm; wdy /= mm
            self.cam.x += wdx * spd
            self.cam.y += wdy * spd

    # ================================================================
    # DRAW
    # ================================================================
    def draw(self):
        screen.fill(BG)
        self._top_hits = []; self._left_hits = []; self._right_hits = []
        self._map_hits = []
        for f in self.fields.values(): f.mark_inactive()
        for dd in self.dropdowns.values(): dd.mark_inactive()
        self._draw_top_bar()
        self._draw_canvas()
        self._draw_left_panel()
        self._draw_right_panel()
        self._draw_bottom_bar()
        for f in self.fields.values():
            if f.active_this_frame: f.draw(screen)
        for dd in self.dropdowns.values():
            if dd.active_this_frame: dd.draw(screen)
        self.save_dialog.draw(screen)
        self.rename_dialog.draw(screen)
        self.ctx_menu.draw(screen)
        for dd in self.dropdowns.values():
            if dd.active_this_frame and dd.expanded: dd.draw_overlay(screen)
        self._draw_msg()
        pygame.display.flip()

    def _draw_top_bar(self):
        r = pygame.Rect(0, 0, WIDTH, TOP_H)
        pygame.draw.rect(screen, PANEL_BG, r)
        pygame.draw.line(screen, PANEL_BORDER, (0, TOP_H), (WIDTH, TOP_H))
        x = 6
        for tab in self.TABS:
            label = self.TAB_LABELS[tab]
            tw = max(90, FONT_S.size(label)[0] + 16)
            rect = pygame.Rect(x, 5, tw, TOP_H - 10)
            draw_button(screen, rect, label, FONT_S, active=(self.tab == tab))
            self._top_hits.append((rect, (lambda tt=tab: self._switch_tab(tt))))
            x += tw + 4
        x += 8
        for label, cb in [("Novo", lambda: self._new_map(None)),
                          ("Salvar", self._open_save_dialog),
                          ("Carregar", self._load_project)]:
            bw = FONT_S.size(label)[0] + 16
            rect = pygame.Rect(x, 5, bw, TOP_H - 10)
            draw_button(screen, rect, label, FONT_S)
            self._top_hits.append((rect, cb)); x += bw + 3
        for label, cb in [("Undo", self._undo), ("Redo", self._redo)]:
            rect = pygame.Rect(x, 5, 46, TOP_H - 10)
            draw_button(screen, rect, label, FONT_S)
            self._top_hits.append((rect, cb)); x += 48
        rect = pygame.Rect(x, 5, 46, TOP_H - 10)
        draw_button(screen, rect, "Grid", FONT_S, active=self.show_grid)
        self._top_hits.append((rect, lambda: setattr(self, 'show_grid',
                                                     not self.show_grid)))
        draw_text(screen, "MAP EDITOR v19", WIDTH - 130, 11, FONT_L, ACCENT_BRIGHT)

    def _switch_tab(self, tab):
        self.tab = tab
        self.expanded_dropdown = None
        for dd in self.dropdowns.values(): dd.expanded = False
        if not self._mode_supports(self.active_tool):
            self.active_tool = TOOL_BRUSH
        if tab == self.TAB_DETAILS and self.editing_event:
            self._sync_fields_from_event(self.editing_event)

    def _draw_left_panel(self):
        r = pygame.Rect(0, TOP_H, LEFT_W, HEIGHT - TOP_H - BOTTOM_H)
        pygame.draw.rect(screen, PANEL_BG, r)
        pygame.draw.line(screen, PANEL_BORDER, (LEFT_W, TOP_H),
                         (LEFT_W, HEIGHT - BOTTOM_H))
        x = 8; y = TOP_H + 6; w = LEFT_W - 16

        draw_text(screen, "MAPAS (RMB menu)", x, y, FONT_XS, ACCENT); y += 12
        y = self._draw_map_tree(self.project.roots(), 0, x, y, w)
        y += 4

        tools_avail = self._current_tools()
        if tools_avail:
            draw_text(screen, "FERRAMENTA", x, y, FONT_XS, ACCENT); y += 12
            bw = (w - 3*3) // 4
            for i, (tid, tlabel, _key) in enumerate(TOOL_DEFS):
                r = pygame.Rect(x + i*(bw+3), y, bw, 20)
                active = (self.active_tool == tid)
                enabled = tid in tools_avail
                draw_button(screen, r, tlabel, FONT_XS, active=active)
                if enabled:
                    self._left_hits.append(
                        (r, (lambda tt=tid: setattr(self, 'active_tool', tt)), None))
            y += 24
        y += 2

        if self.tab == self.TAB_LAYOUT:
            self._draw_left_layout(x, y, w)
        elif self.tab == self.TAB_TEXTURE:
            self._draw_left_texture(x, y, w)
        elif self.tab == self.TAB_DETAILS:
            self._draw_left_details(x, y, w)

    def _draw_map_tree(self, names, depth, x0, y, w):
        for name in names:
            r = pygame.Rect(x0 + depth*10, y, w - depth*10, 18)
            active = (name == self.project.active_map_name)
            bg = BTN_ACTIVE if active else BTN
            if r.collidepoint(pygame.mouse.get_pos()) and not active: bg = BTN_HOVER
            if self.pending_map_click and self.pending_map_click[0] == name:
                bg = (150, 130, 80)
            pygame.draw.rect(screen, bg, r, border_radius=3)
            pygame.draw.rect(screen, ACCENT_DARK, r, 1, border_radius=3)
            prefix = "▾ " if self.project.children_of(name) else "  "
            draw_text(screen, prefix + name[:22], r.x + 6, r.y + 3, FONT_XS, TEXT)
            self._left_hits.append((r, name, "map"))
            self._map_hits.append((r, name))
            y += 20
            children = self.project.children_of(name)
            if children:
                y = self._draw_map_tree(children, depth + 1, x0, y, w)
        return y

    def _draw_tile_grid(self, x, y, w, cols=5):
        tiles = list(self.project.tileset.order)
        tw = (w - (cols-1)*3) // cols
        cx = x; cy = y
        for tid in tiles:
            t = self.project.tileset.get(tid)
            r = pygame.Rect(cx, cy, tw, tw)
            img = t.get_sprite("top", (tw-4, tw-4))
            if img: screen.blit(img, (cx+2, cy+2))
            else: pygame.draw.rect(screen, t.color, (cx+2, cy+2, tw-4, tw-4))
            if tid == self.selected_tile_id:
                pygame.draw.rect(screen, HIGHLIGHT, r, 3, border_radius=3)
            else:
                pygame.draw.rect(screen, ACCENT_DARK, r, 1, border_radius=3)
            self._left_hits.append((r, (lambda tt=tid: self._set_tile(tt)), None))
            cx += tw + 3
            if cx + tw > x + w + 2: cx = x; cy += tw + 3
        return cy + tw + 4

    def _set_tile(self, tid):
        self.selected_tile_id = tid
        self._sync_fields_from_tile()
        self._msg(f"Tile: {tid}", ACCENT)

    def _draw_left_layout(self, x, y, w):
        draw_text(screen, "SUB-MODO", x, y, FONT_XS, ACCENT); y += 12
        bw = (w - 2*3) // 3
        for i, lm in enumerate(self.LMODES):
            r = pygame.Rect(x + i*(bw+3), y, bw, 20)
            active = (self.layout_mode == lm)
            draw_button(screen, r, self.LMODE_LABELS[lm], FONT_XS, active=active)
            self._left_hits.append((r, (lambda m=lm: self._set_layout_mode(m)), None))
        y += 24

        if self.layout_mode == self.LMODE_TERRAIN:
            draw_text(screen, f"ALTURA: {self.terrain_height}",
                      x, y, FONT_XS, ACCENT); y += 12
            bw = (w - 8) // 3
            r1 = pygame.Rect(x, y, bw, 20)
            r2 = pygame.Rect(x + bw + 4, y, bw, 20)
            r3 = pygame.Rect(x + 2*(bw+4), y, bw, 20)
            draw_button(screen, r1, "− 1", FONT_XS)
            draw_button(screen, r2, "+ 1", FONT_XS)
            draw_button(screen, r3, "0", FONT_XS)
            self._left_hits.append((r1, (lambda: setattr(self, 'terrain_height',
                                                         max(0, self.terrain_height - 1))), None))
            self._left_hits.append((r2, (lambda: setattr(self, 'terrain_height',
                                                         min(NUM_FLOORS, self.terrain_height + 1))), None))
            self._left_hits.append((r3, (lambda: setattr(self, 'terrain_height', 0)), None))
            y += 24
            draw_text(screen, "FORMA", x, y, FONT_XS, ACCENT); y += 12
            forms_pt = [("flat","Plano"),
                        ("ramp_n","Rampa N"),("ramp_s","Rampa S"),
                        ("ramp_e","Rampa L"),("ramp_w","Rampa O"),
                        ("stair_n","Esc. N"),("stair_s","Esc. S"),
                        ("stair_e","Esc. L"),("stair_w","Esc. O")]
            cols = 3; bw = (w - 4*cols) // cols
            cx = x; cy = y
            for i, (f_id, f_lbl) in enumerate(forms_pt):
                r = pygame.Rect(cx, cy, bw, 18)
                active = (self.terrain_form == f_id)
                draw_button(screen, r, f_lbl, FONT_XS, active=active)
                self._left_hits.append((r, (lambda ff=f_id:
                                             setattr(self, 'terrain_form', ff)), None))
                cx += bw + 4
                if (i+1) % cols == 0: cx = x; cy += 22
            y = cy + 4

        elif self.layout_mode == self.LMODE_BLOCK:
            draw_text(screen, f"ANDAR: {self.active_floor}",
                      x, y, FONT_XS, ACCENT); y += 12
            for line in ["Placa fina no topo do andar.",
                         "Pinte pisos nos andares 0,1,2...",
                         "Telhado no andar mais alto."]:
                draw_text(screen, line, x, y, FONT_XS, TEXT_DIM); y += 12
            y += 2

        elif self.layout_mode == self.LMODE_WALL:
            draw_text(screen, "TIPO", x, y, FONT_XS, ACCENT); y += 12
            for kind_id, kind_lbl in WALL_KINDS:
                r = pygame.Rect(x, y, w, 22)
                active = (self.current_wall_kind == kind_id)
                bg = BTN_ACTIVE if active else BTN
                if r.collidepoint(pygame.mouse.get_pos()) and not active: bg = BTN_HOVER
                pygame.draw.rect(screen, bg, r, border_radius=4)
                col = {'wall': C_WALL_H_FRONT, 'door': C_DOOR,
                       'window': C_WINDOW}[kind_id]
                pygame.draw.rect(screen, col, (x + 4, y + 3, 16, 16), border_radius=3)
                draw_text(screen, kind_lbl, x + 28, y + 5, FONT_S, TEXT)
                self._left_hits.append((r, (lambda k=kind_id:
                                             setattr(self, 'current_wall_kind', k)), None))
                y += 24
            y += 4
            for line in ["Clique PERTO da linha",
                         "do grid para colocar.",
                         "Preview amarelo mostra",
                         "onde vai encaixar."]:
                draw_text(screen, line, x, y, FONT_XS, TEXT_DIM); y += 12

        draw_text(screen, "TILES", x, y, FONT_XS, ACCENT); y += 12
        y = self._draw_tile_grid(x, y, w)
        bw = (w - 8) // 3
        r1 = pygame.Rect(x, y, bw, 20)
        r2 = pygame.Rect(x + bw + 4, y, bw, 20)
        r3 = pygame.Rect(x + 2*(bw+4), y, bw, 20)
        draw_button(screen, r1, "+ Tile", FONT_XS)
        draw_button(screen, r2, "Del", FONT_XS, danger=True)
        draw_button(screen, r3, "Pasta", FONT_XS)
        self._left_hits.append((r1, self._new_tile, None))
        self._left_hits.append((r2, self._del_tile, None))
        self._left_hits.append((r3, self._open_tile_folder, None))

    def _set_layout_mode(self, lm):
        self.layout_mode = lm
        if not self._mode_supports(self.active_tool):
            self.active_tool = TOOL_BRUSH

    def _draw_left_texture(self, x, y, w):
        draw_text(screen, "TEXTURA", x, y, FONT_XS, ACCENT); y += 12
        for line in ["Pinta textura em qualquer",
                     "objeto já colocado:",
                     "- Terreno / Rampas / Escadas",
                     "- Piso / Telhado",
                     "- Paredes / Portas / Janelas",
                     "Tipo, altura e forma são",
                     "sempre preservados."]:
            draw_text(screen, line, x, y, FONT_XS, TEXT_DIM); y += 12
        y += 4

        draw_text(screen, "TILES", x, y, FONT_XS, ACCENT); y += 12
        y = self._draw_tile_grid(x, y, w)
        bw = (w - 8) // 3
        r1 = pygame.Rect(x, y, bw, 20)
        r2 = pygame.Rect(x + bw + 4, y, bw, 20)
        r3 = pygame.Rect(x + 2*(bw+4), y, bw, 20)
        draw_button(screen, r1, "+ Tile", FONT_XS)
        draw_button(screen, r2, "Del", FONT_XS, danger=True)
        draw_button(screen, r3, "Pasta", FONT_XS)
        self._left_hits.append((r1, self._new_tile, None))
        self._left_hits.append((r2, self._del_tile, None))
        self._left_hits.append((r3, self._open_tile_folder, None))

    def _draw_left_details(self, x, y, w):
        draw_text(screen, "SUB-MODO", x, y, FONT_XS, ACCENT); y += 12
        bw = (w - 3) // 2
        for i, dm in enumerate(self.DMODES):
            r = pygame.Rect(x + i*(bw+3), y, bw, 20)
            active = (self.details_mode == dm)
            draw_button(screen, r, self.DMODE_LABELS[dm], FONT_XS, active=active)
            self._left_hits.append((r, (lambda m=dm: self._set_details_mode(m)), None))
        y += 24

        if self.details_mode == self.DMODE_SPRITE:
            draw_text(screen, "SPRITES", x, y, FONT_XS, ACCENT); y += 12
            cols = 5; tw = (w - (cols-1)*3) // cols
            cx = x; cy = y
            for i, sp in enumerate(self.project.sprites):
                r = pygame.Rect(cx, cy, tw, tw)
                s = sp.surface(1.0); sw, sh = s.get_size()
                if sh > 0 and sw > 0:
                    ratio = min((tw-4)/sw, (tw-4)/sh, 3)
                    thumb = pygame.transform.smoothscale(
                        s, (max(1,int(sw*ratio)), max(1,int(sh*ratio))))
                    screen.blit(thumb, (r.centerx - thumb.get_width()//2,
                                        r.centery - thumb.get_height()//2))
                if i == self.selected_sprite_idx:
                    pygame.draw.rect(screen, HIGHLIGHT, r, 3, border_radius=3)
                else:
                    pygame.draw.rect(screen, ACCENT_DARK, r, 1, border_radius=3)
                self._left_hits.append((r, (lambda idx=i:
                                             self._select_sprite(idx)), None))
                cx += tw + 3
                if cx + tw > x + w + 2: cx = x; cy += tw + 3
            y = cy + tw + 4
            bw = (w - 8) // 3
            r1 = pygame.Rect(x, y, bw, 20)
            r2 = pygame.Rect(x + bw + 4, y, bw, 20)
            r3 = pygame.Rect(x + 2*(bw+4), y, bw, 20)
            draw_button(screen, r1, "+ Sprite", FONT_XS)
            draw_button(screen, r2, "Del", FONT_XS, danger=True)
            draw_button(screen, r3, "Pasta", FONT_XS)
            self._left_hits.append((r1, self._import_sprite, None))
            self._left_hits.append((r2, self._remove_sprite, None))
            self._left_hits.append((r3, self._open_sprite_folder, None))

        else:
            draw_text(screen, "TIPO A COLOCAR", x, y, FONT_XS, ACCENT); y += 12
            for kind, label in EVENT_KINDS:
                r = pygame.Rect(x, y, w, 22)
                active = (kind == self.current_event_kind)
                bg = BTN_ACTIVE if active else BTN
                if r.collidepoint(pygame.mouse.get_pos()) and not active: bg = BTN_HOVER
                pygame.draw.rect(screen, bg, r, border_radius=3)
                pygame.draw.rect(screen, EVENT_KIND_COLORS[kind],
                                 (x + 3, y + 2, 16, 16), border_radius=2)
                draw_text(screen, EVENT_KIND_GLYPHS[kind], x + 6, y + 4, FONT_S,
                          (20,15,10))
                draw_text(screen, label, x + 26, y + 4, FONT_S, TEXT)
                self._left_hits.append((r, (lambda k=kind:
                                             setattr(self, 'current_event_kind', k)), None))
                y += 24
            y += 6
            for line in ["LMB no canvas coloca.",
                         "RMB num evento: menu.",
                         "Sprite do evento: painel direito."]:
                draw_text(screen, line, x, y, FONT_XS, TEXT_DIM); y += 12

    def _set_details_mode(self, dm):
        self.details_mode = dm
        if not self._mode_supports(self.active_tool):
            self.active_tool = TOOL_BRUSH

    def _select_sprite(self, idx):
        self.selected_sprite_idx = idx; self.active_sprite_idx = idx
        self._sync_fields_from_sprite()
        self._msg(f"Sprite: {self.project.sprites[idx].name}", ACCENT)

    # ================================================================
    # RIGHT PANEL
    # ================================================================
    def _draw_right_panel(self):
        rx = WIDTH - RIGHT_W
        r = pygame.Rect(rx, TOP_H, RIGHT_W, HEIGHT - TOP_H - BOTTOM_H)
        pygame.draw.rect(screen, PANEL_BG, r)
        pygame.draw.line(screen, PANEL_BORDER, (rx, TOP_H), (rx, HEIGHT - BOTTOM_H))
        x = rx + 14; y = TOP_H + 6; w = RIGHT_W - 28

        if self.tab == self.TAB_LAYOUT:
            self._draw_right_layout(x, y, w)
        elif self.tab == self.TAB_TEXTURE:
            self._draw_right_texture(x, y, w)
        elif self.tab == self.TAB_DETAILS:
            self._draw_right_details(x, y, w)

    def _draw_floor_widget(self, x, y, w):
        draw_text(screen, "ANDAR ATIVO", x, y, FONT_XS, ACCENT); y += 12
        self.dropdowns["floor"].set_position(x, y, w)
        return y + 36

    def _draw_tile_properties(self, x, y, w):
        tid = self.selected_tile_id
        t = self.project.tileset.get(tid) if tid else None
        if not t:
            draw_text(screen, "Nenhum tile selecionado.", x, y, FONT_XS, TEXT_DIM)
            return y + 14

        draw_text(screen, "TILE", x, y, FONT_XS, ACCENT); y += 12
        img = t.get_sprite("top", (40, 40))
        if img: screen.blit(img, (x+2, y+2))
        else: pygame.draw.rect(screen, t.color, (x+2, y+2, 40, 40))
        pygame.draw.rect(screen, ACCENT_DARK, (x, y, 44, 44), 2)
        draw_text(screen, t.id[:20], x+50, y+4, FONT_S, TEXT_GOLD)
        draw_text(screen, f"h:{t.height}", x+50, y+22, FONT_XS, TEXT_DIM)
        y += 48

        self.fields["tile_name"].set_position(x, y, w); y += 36
        self.fields["tile_category"].set_position(x, y, w); y += 36
        self.fields["tile_height"].set_position(x, y, w); y += 36

        draw_text(screen, "SPRITES POR SLOT", x, y, FONT_XS, ACCENT); y += 12
        for slot in TILE_SLOTS:
            r = pygame.Rect(x, y, w, 26)
            pygame.draw.rect(screen, (30, 26, 22), r, border_radius=3)
            pygame.draw.rect(screen, ACCENT_DARK, r, 1, border_radius=3)
            mini = pygame.Rect(x+3, y+3, 20, 20)
            m = t.get_sprite(slot, (18, 18))
            if m: screen.blit(m, (mini.x+1, mini.y+1))
            else:
                pygame.draw.rect(screen, (50, 44, 38), mini)
                draw_text(screen, "—", mini.x+6, mini.y+3, FONT_XS, TEXT_DIM)
            pygame.draw.rect(screen, ACCENT_DARK, mini, 1)
            draw_text(screen, slot, x+28, y+7, FONT_S, TEXT)
            bw = 64
            r_pick = pygame.Rect(x + w - bw*2 - 4, y+2, bw, 22)
            r_del  = pygame.Rect(x + w - bw - 4, y+2, 18, 22)
            draw_button(screen, r_pick, "Escolher…", FONT_XS)
            draw_button(screen, r_del, "X", FONT_XS, danger=True)
            self._right_hits.append((r_pick, (lambda s=slot: self._pick_slot_image(s))))
            self._right_hits.append((r_del, (lambda s=slot: self._remove_slot_image(s))))
            y += 28

        r = pygame.Rect(x, y, w, 22)
        def toggle_walk():
            tt = self.project.tileset.get(self.selected_tile_id)
            if tt: tt.walkable = not tt.walkable; self._mark_dirty()
        label = f"Walkable: {'ON' if t.walkable else 'OFF'}"
        draw_button(screen, r, label, FONT_XS, active=t.walkable)
        self._right_hits.append((r, toggle_walk))
        y += 26

        r = pygame.Rect(x, y, w//2 - 3, 22)
        r2 = pygame.Rect(x + w//2 + 3, y, w//2 - 3, 22)
        draw_button(screen, r, "Pasta", FONT_XS)
        draw_button(screen, r2, "Aplicar", FONT_XS, primary=True)
        self._right_hits.append((r, self._open_tile_folder))
        self._right_hits.append((r2, self._apply_tile_fields))
        y += 26

        return y

    def _draw_right_layout(self, x, y, w):
        draw_text(screen, "MAPA", x, y, FONT_XS, ACCENT); y += 12
        self.fields["map_name"].set_position(x, y, w); y += 36
        half = (w - 6) // 2
        self.fields["map_w"].set_position(x, y, half)
        self.fields["map_h"].set_position(x + half + 6, y, half); y += 36
        self.fields["num_floors"].set_position(x, y, half); y += 36
        r = pygame.Rect(x, y, w, 22)
        draw_button(screen, r, "Aplicar mapa", FONT_XS, primary=True)
        self._right_hits.append((r, self._apply_map_fields)); y += 26

        y = self._draw_floor_widget(x, y, w)
        pygame.draw.line(screen, ACCENT_DARK, (x, y), (x+w, y)); y += 6
        y = self._draw_tile_properties(x, y, w)

    def _draw_right_texture(self, x, y, w):
        y = self._draw_floor_widget(x, y, w)
        pygame.draw.line(screen, ACCENT_DARK, (x, y), (x+w, y)); y += 6

        draw_text(screen, "TILE APLICADO", x, y, FONT_XS, ACCENT); y += 12
        y = self._draw_tile_properties(x, y, w)

        y += 6
        pygame.draw.line(screen, ACCENT_DARK, (x, y), (x+w, y)); y += 6
        for line in ["Clique sobre um objeto já",
                     "existente: terreno, rampa,",
                     "escada, piso, telhado, parede,",
                     "porta ou janela.",
                     "",
                     "Só a textura muda. Tipo, altura",
                     "e forma são preservados."]:
            draw_text(screen, line, x, y, FONT_XS, TEXT_DIM); y += 12

    def _draw_right_details(self, x, y, w):
        y = self._draw_floor_widget(x, y, w)
        pygame.draw.line(screen, ACCENT_DARK, (x, y), (x+w, y)); y += 6

        if self.details_mode == self.DMODE_SPRITE:
            self._draw_right_sprite(x, y, w)
        else:
            self._draw_right_event(x, y, w)

    def _draw_right_sprite(self, x, y, w):
        idx = self.selected_sprite_idx
        if idx is None or idx < 0 or idx >= len(self.project.sprites):
            draw_text(screen, "Nenhuma sprite.", x, y, FONT_XS, TEXT_DIM)
            return
        sp = self.project.sprites[idx]
        draw_text(screen, "SPRITE SELECIONADA", x, y, FONT_XS, ACCENT); y += 12
        pv = sp.surface(1.0); pw, ph = pv.get_size()
        if ph > 0 and pw > 0:
            ratio = min(56/ph, 56/pw, 4)
            th = pygame.transform.smoothscale(pv, (int(pw*ratio), int(ph*ratio)))
            screen.blit(th, (x+2, y+2))
        draw_text(screen, sp.name[:22], x+62, y+4, FONT_S, TEXT_GOLD)
        draw_text(screen, f"{pw}x{ph}px", x+62, y+22, FONT_XS, TEXT_DIM)
        y += 62

        self.fields["sprite_name"].set_position(x, y, w); y += 36
        self.fields["sprite_scale"].set_position(x, y, w); y += 36
        half = (w - 6) // 2
        self.fields["sprite_off_x"].set_position(x, y, half)
        self.fields["sprite_off_y"].set_position(x + half + 6, y, half); y += 36
        self.fields["sprite_anc_x"].set_position(x, y, half)
        self.fields["sprite_anc_y"].set_position(x + half + 6, y, half); y += 36
        r = pygame.Rect(x, y, w, 24)
        draw_button(screen, r, "Aplicar propriedades", FONT_XS, primary=True)
        self._right_hits.append((r, self._apply_sprite_fields)); y += 28
        r = pygame.Rect(x, y, w, 24)
        draw_button(screen, r, "Remover sprite", FONT_XS, danger=True)
        self._right_hits.append((r, self._remove_sprite))

    def _draw_right_event(self, x, y, w):
        ev = self.editing_event
        if not ev:
            draw_text(screen, "EDITAR EVENTO", x, y, FONT_XS, ACCENT); y += 18
            for line in ["Clique num evento no canvas",
                         "para editá-lo, ou clique",
                         "num tile vazio para colocar.",
                         "",
                         "Depois é só escolher uma sprite",
                         "para representá-lo."]:
                draw_text(screen, line, x, y, FONT_XS, TEXT_DIM); y += 12
            return
        draw_text(screen, "EDITAR EVENTO", x, y, FONT_XS, ACCENT); y += 12
        col = EVENT_KIND_COLORS.get(ev.kind, (200,200,200))
        pygame.draw.rect(screen, col, (x, y, 20, 20), border_radius=3)
        draw_text(screen, EVENT_KIND_GLYPHS.get(ev.kind,"?"), x+5, y+4,
                  FONT_S, (20,15,10))
        draw_text(screen, f"pos ({ev.x},{ev.y})", x+28, y+5, FONT_XS, TEXT_DIM)
        y += 28
        self.dropdowns["ev_kind"].set_position(x, y, w); y += 38
        half = (w - 6) // 2
        self.fields["ev_name"].set_position(x, y, half)
        self.fields["ev_id"].set_position(x + half + 6, y, half); y += 36
        self.fields["ev_tag"].set_position(x, y, w); y += 36

        # ----- Campos específicos do tipo Teleport -----
        if ev.kind == 'teleport':
            draw_text(screen, "TELEPORT", x, y, FONT_XS, ACCENT); y += 12
            self.fields["ev_tele_map"].set_position(x, y, w); y += 36
            bw = (w - 12) // 3
            self.fields["ev_tele_x"].set_position(x, y, bw)
            self.fields["ev_tele_y"].set_position(x + bw + 6, y, bw)
            self.fields["ev_tele_z"].set_position(x + 2*(bw + 6), y, bw)
            y += 36

        draw_text(screen, "SPRITE DO EVENTO", x, y, FONT_XS, ACCENT); y += 12

        cur_sp = None
        if ev.sprite_idx is not None and 0 <= ev.sprite_idx < len(self.project.sprites):
            cur_sp = self.project.sprites[ev.sprite_idx]
        if cur_sp is not None:
            pv = cur_sp.surface(1.0); pw, ph = pv.get_size()
            if ph > 0 and pw > 0:
                ratio = min(40/ph, 40/pw, 4)
                th = pygame.transform.smoothscale(pv, (int(pw*ratio), int(ph*ratio)))
                screen.blit(th, (x+2, y+2))
            draw_text(screen, cur_sp.name[:18], x+48, y+12, FONT_XS, TEXT)
        else:
            draw_text(screen, "(sem sprite)", x, y+8, FONT_XS, TEXT_DIM)
        y += 46

        if self.project.sprites:
            cols = 6; gap = 3
            tw = (w - (cols-1)*gap) // cols
            cx = x; cy = y
            for i, sp in enumerate(self.project.sprites):
                r = pygame.Rect(cx, cy, tw, tw)
                s = sp.surface(1.0); sw, sh = s.get_size()
                if sh > 0 and sw > 0:
                    ratio = min((tw-4)/sw, (tw-4)/sh, 3)
                    thumb = pygame.transform.smoothscale(
                        s, (max(1,int(sw*ratio)), max(1,int(sh*ratio))))
                    screen.blit(thumb, (r.centerx - thumb.get_width()//2,
                                        r.centery - thumb.get_height()//2))
                if ev.sprite_idx == i:
                    pygame.draw.rect(screen, HIGHLIGHT, r, 2, border_radius=3)
                else:
                    pygame.draw.rect(screen, ACCENT_DARK, r, 1, border_radius=3)
                self._right_hits.append(
                    (r, (lambda idx=i, e=ev: self._set_event_sprite(e, idx))))
                cx += tw + gap
                if cx + tw > x + w + 2: cx = x; cy += tw + gap
            y = cy + tw + 4

        r = pygame.Rect(x, y, w, 20)
        draw_button(screen, r, "✕ Remover sprite do evento", FONT_XS, danger=True)
        self._right_hits.append((r, (lambda e=ev: self._set_event_sprite(e, None))))
        y += 24

        r = pygame.Rect(x, y, w//2 - 3, 24)
        r2 = pygame.Rect(x + w//2 + 3, y, w//2 - 3, 24)
        draw_button(screen, r, "Aplicar", FONT_XS, primary=True)
        draw_button(screen, r2, "Deletar", FONT_XS, danger=True)
        self._right_hits.append((r, self._apply_event_fields))
        self._right_hits.append((r2, (lambda e=ev: self._del_event(e))))

    # ================================================================
    # CANVAS
    # ================================================================
    def _draw_canvas(self):
        clip = self._canvas_rect()
        old = screen.get_clip()
        screen.set_clip(clip)
        pygame.draw.rect(screen, CANVAS_BG, clip)
        m = self.project.active_map()
        if m:
            self._render_iso(m)
            self._draw_hover_iso(m)
        screen.set_clip(old)
        pygame.draw.rect(screen, PANEL_BORDER, clip, 2)

    def _render_iso(self, m):
        tw, th = tile_size(self.cam)
        ox, oy = self._iso_origin()
        z = unit_px(self.cam)

        items = []
        for (tx, ty), t in m.terrain.items():
            key = (tx + ty, t['h'] + (0.5 if t['form'] != FORM_FLAT else 0.0), 0)
            items.append((key, 'terrain', (tx, ty, t)))
        for (tx, ty, tz), blk in m.blocks.items():
            if tz > self.active_floor: continue
            items.append(((tx + ty, tz, 1), 'block', (tx, ty, tz, blk)))
        for (tx, ty, tz), val in m.walls_h.items():
            if tz > self.active_floor: continue
            kind, tid = wall_val(val)
            items.append(((tx + ty, tz, 2), 'wall_h', (tx, ty, tz, kind, tid)))
        for (tx, ty, tz), val in m.walls_v.items():
            if tz > self.active_floor: continue
            kind, tid = wall_val(val)
            items.append(((tx + ty, tz, 2), 'wall_v', (tx, ty, tz, kind, tid)))
        for (tx, ty, tz), sid in m.objects.items():
            if sid < 0 or sid >= len(self.project.sprites): continue
            if tz > self.active_floor: continue
            items.append(((tx + ty, tz, 3), 'object', (tx, ty, tz, sid)))

        items.sort(key=lambda it: it[0])

        for key, kind, data in items:
            tx, ty = data[0], data[1]
            wx = (tx - ty) * tw * 0.5; wy = (tx + ty) * th * 0.5
            sx = ox + wx; sy = oy + wy
            if sx + tw * 2 < CANVAS_X or sx - tw * 2 > CANVAS_X + CANVAS_W: continue
            if sy + th * 4 < CANVAS_Y or sy - th * 20 > CANVAS_Y + CANVAS_H: continue

            if kind == 'terrain':
                tdef = data[2]
                tile = self.project.tileset.get(tdef['tile_id'])
                if not tile: continue
                form = tdef['form']
                if form.startswith('stair_'):
                    draw_stairs_iso(screen, tdef, tile, tx, ty, self.cam, ox, oy)
                else:
                    draw_terrain_iso(screen, tdef, tile, tx, ty, 0, self.cam, ox, oy)
            elif kind == 'block':
                tz = data[2]; tid = data[3]
                tile = self.project.tileset.get(tid)
                if not tile: continue
                draw_block_iso(screen, tile, tx, ty, tz, self.cam, ox, oy)
            elif kind == 'wall_h':
                tz = data[2]; kw = data[3]; tid = data[4]
                tile = self.project.tileset.get(tid) if tid else None
                draw_wall_h_iso(screen, self.cam, ox, oy, tx, ty, tz, kw, tile)
            elif kind == 'wall_v':
                tz = data[2]; kw = data[3]; tid = data[4]
                tile = self.project.tileset.get(tid) if tid else None
                draw_wall_v_iso(screen, self.cam, ox, oy, tx, ty, tz, kw, tile)
            elif kind == 'object':
                tz = data[2]; sid = data[3]
                sp = self.project.sprites[sid]
                wx = (tx - ty) * tw * 0.5; wy = (tx + ty) * th * 0.5
                scr_x = ox + wx; scr_y = oy + wy + th * 0.5 - tz * z
                sp.draw_at(screen, scr_x, scr_y, self.cam.zoom)

        if self.show_grid: self._draw_grid_iso(m)
        if self.tab == self.TAB_DETAILS and self.details_mode == self.DMODE_EVENT:
            self._draw_events_iso(m)

    def _draw_grid_iso(self, m):
        ox, oy = self._iso_origin()
        z_shift = 0
        if self.tab == self.TAB_LAYOUT and self.layout_mode == self.LMODE_BLOCK:
            z_shift = self.active_floor * unit_px(self.cam)
        surf = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        for x in range(m.w + 1):
            p1 = world_to_screen(x, 0, self.cam, ox - CANVAS_X, oy - CANVAS_Y)
            p2 = world_to_screen(x, m.h, self.cam, ox - CANVAS_X, oy - CANVAS_Y)
            p1 = (p1[0], p1[1] - z_shift); p2 = (p2[0], p2[1] - z_shift)
            pygame.draw.line(surf, (255,255,255,45), p1, p2, 1)
        for y in range(m.h + 1):
            p1 = world_to_screen(0, y, self.cam, ox - CANVAS_X, oy - CANVAS_Y)
            p2 = world_to_screen(m.w, y, self.cam, ox - CANVAS_X, oy - CANVAS_Y)
            p1 = (p1[0], p1[1] - z_shift); p2 = (p2[0], p2[1] - z_shift)
            pygame.draw.line(surf, (255,255,255,45), p1, p2, 1)
        screen.blit(surf, (CANVAS_X, CANVAS_Y))

    def _draw_hover_iso(self, m):
        mx, my = pygame.mouse.get_pos()

        if (self.tab == self.TAB_LAYOUT and self.layout_mode == self.LMODE_WALL):
            if not self.hover_wall:
                self.hover_wall = self._pick_wall_at(mx, my)
            if not self.hover_wall: return
            kind, x, y = self.hover_wall
            ox, oy = self._iso_origin()
            z = self.active_floor
            z_off = z * unit_px(self.cam)
            wh = unit_px(self.cam) * WALL_HEIGHT_UNITS
            if kind == 'h':
                p1 = world_to_screen(x,     y, self.cam, ox, oy)
                p2 = world_to_screen(x + 1, y, self.cam, ox, oy)
            else:
                p1 = world_to_screen(x, y,     self.cam, ox, oy)
                p2 = world_to_screen(x, y + 1, self.cam, ox, oy)
            p1 = (p1[0], p1[1] - z_off); p2 = (p2[0], p2[1] - z_off)
            p1u = (p1[0], p1[1] - wh);   p2u = (p2[0], p2[1] - wh)
            s = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
            rel = [(p[0]-CANVAS_X, p[1]-CANVAS_Y) for p in [p1, p2, p2u, p1u]]
            pygame.draw.polygon(s, (255, 240, 100, 120), rel)
            screen.blit(s, (CANVAS_X, CANVAS_Y))
            pygame.draw.polygon(screen, (255, 240, 100), [p1, p2, p2u, p1u], 2)
            return

        if self.tab == self.TAB_TEXTURE:
            hit = self._pick_wall_at(mx, my)
            if hit and m:
                kind, x, y = hit
                z = self.active_floor
                d = m.walls_h if kind == 'h' else m.walls_v
                if (x, y, z) in d:
                    ox, oy = self._iso_origin()
                    z_off = z * unit_px(self.cam)
                    wh = unit_px(self.cam) * WALL_HEIGHT_UNITS
                    if kind == 'h':
                        p1 = world_to_screen(x,     y, self.cam, ox, oy)
                        p2 = world_to_screen(x + 1, y, self.cam, ox, oy)
                    else:
                        p1 = world_to_screen(x, y,     self.cam, ox, oy)
                        p2 = world_to_screen(x, y + 1, self.cam, ox, oy)
                    p1 = (p1[0], p1[1] - z_off); p2 = (p2[0], p2[1] - z_off)
                    p1u = (p1[0], p1[1] - wh);   p2u = (p2[0], p2[1] - wh)
                    s = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
                    rel = [(p[0]-CANVAS_X, p[1]-CANVAS_Y)
                           for p in [p1, p2, p2u, p1u]]
                    pygame.draw.polygon(s, (140, 200, 255, 100), rel)
                    screen.blit(s, (CANVAS_X, CANVAS_Y))
                    pygame.draw.polygon(screen, (140, 200, 255),
                                        [p1, p2, p2u, p1u], 2)

        if self.drag_start is not None and self.active_tool == TOOL_RECT:
            mpos = pygame.mouse.get_pos()
            if (self.tab == self.TAB_LAYOUT and
                self.layout_mode == self.LMODE_BLOCK):
                c2 = self._pick_tile_at_height(mpos[0], mpos[1], self.active_floor)
            else:
                c2 = self._pick_tile_at(mpos[0], mpos[1]) or self._cell_from_pos(mpos)
            c2 = c2 or self.drag_start
            x0, y0 = self.drag_start; x1, y1 = c2
            xa, xb = sorted([x0, x1]); ya, yb = sorted([y0, y1])
            tw, th = tile_size(self.cam); ox, oy = self._iso_origin()
            z_shift = 0
            if (self.tab == self.TAB_LAYOUT and
                self.layout_mode == self.LMODE_BLOCK):
                z_shift = self.active_floor * unit_px(self.cam)
            s = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
            for yy in range(ya, yb+1):
                for xx in range(xa, xb+1):
                    wx = (xx - yy) * tw * 0.5; wy = (xx + yy) * th * 0.5
                    cx = ox + wx; cy = oy + wy + th * 0.5 - z_shift
                    hw = tw * 0.5; hh = th * 0.5
                    rel = [(cx - CANVAS_X, cy - CANVAS_Y - hh),
                           (cx - CANVAS_X + hw, cy - CANVAS_Y),
                           (cx - CANVAS_X, cy - CANVAS_Y + hh),
                           (cx - CANVAS_X - hw, cy - CANVAS_Y)]
                    pygame.draw.polygon(s, (255, 220, 100, 100), rel)
                    pygame.draw.polygon(s, (255, 240, 100, 220), rel, 1)
            screen.blit(s, (CANVAS_X, CANVAS_Y))
            return

        if (self.tab == self.TAB_DETAILS and self.details_mode == self.DMODE_SPRITE
                and self.selected_sprite_idx is not None
                and 0 <= self.selected_sprite_idx < len(self.project.sprites)):
            cell = self.hover_cell
            if cell:
                tx, ty = cell
                tw, th = tile_size(self.cam)
                ox, oy = self._iso_origin()
                wx = (tx - ty) * tw * 0.5; wy = (tx + ty) * th * 0.5
                cx = ox + wx; cy = oy + wy + th * 0.5
                cy -= self.active_floor * unit_px(self.cam)
                sp = self.project.sprites[self.selected_sprite_idx]
                g = sp.ghost(self.cam.zoom)
                w, h = g.get_size()
                oxx = sp.offset_x * self.cam.zoom
                oyy = sp.offset_y * self.cam.zoom
                dx = cx - sp.anchor_x * w + oxx
                dy = cy - sp.anchor_y * h + oyy
                screen.blit(g, (int(dx), int(dy)))
                hw = tw * 0.5; hh = th * 0.5
                pygame.draw.polygon(screen, (255, 240, 100),
                                    [(cx, cy - hh), (cx + hw, cy),
                                     (cx, cy + hh), (cx - hw, cy)], 2)
                return

        cell = self.hover_cell
        if not cell: return
        tw, th = tile_size(self.cam)
        ox, oy = self._iso_origin()
        tx, ty = cell
        wx = (tx - ty) * tw * 0.5; wy = (tx + ty) * th * 0.5
        cx = ox + wx; cy = oy + wy + th * 0.5
        t = m.get_terrain(tx, ty)

        col = HIGHLIGHT
        if self.tab == self.TAB_TEXTURE:
            col = (140, 200, 255)
        if self.tab == self.TAB_LAYOUT and self.layout_mode == self.LMODE_BLOCK:
            cy -= self.active_floor * unit_px(self.cam)
        else:
            cy -= t['h'] * unit_px(self.cam)

        hw = tw * 0.5; hh = th * 0.5
        pygame.draw.polygon(screen, col,
                            [(cx, cy - hh), (cx + hw, cy),
                             (cx, cy + hh), (cx - hw, cy)], 2)

    def _draw_events_iso(self, m):
        """Desenha eventos usando EXATAMENTE as propriedades da sprite
        (escala, offset e âncora) configuradas pelo usuário."""
        tw, th = tile_size(self.cam)
        ox, oy = self._iso_origin(); z = unit_px(self.cam)
        for ev in m.events:
            wx = (ev.x - ev.y) * tw * 0.5
            wy = (ev.x + ev.y) * th * 0.5
            cx = ox + wx
            cy = oy + wy + th * 0.5
            t = m.get_terrain(ev.x, ev.y)
            cy -= t['h'] * z

            sprite_drawn = False
            if (ev.sprite_idx is not None
                    and 0 <= ev.sprite_idx < len(self.project.sprites)):
                sp = self.project.sprites[ev.sprite_idx]
                sp.draw_at(screen, cx, cy, self.cam.zoom)
                sprite_drawn = True

            if not sprite_drawn:
                col = EVENT_KIND_COLORS.get(ev.kind, (200,200,200))
                r = max(6, int(12 * self.cam.zoom))
                pygame.draw.circle(screen, col, (int(cx), int(cy - th*0.3)), r)
                pygame.draw.circle(screen, (20,15,10), (int(cx), int(cy - th*0.3)), r, 2)
                g = FONT_XS.render(EVENT_KIND_GLYPHS.get(ev.kind,"?"), True, (20,15,10))
                screen.blit(g, (int(cx) - g.get_width()//2,
                                int(cy - th*0.3) - g.get_height()//2))

            col = EVENT_KIND_COLORS.get(ev.kind, (200,200,200))
            g2 = FONT_XS.render(EVENT_KIND_GLYPHS.get(ev.kind,"?"), True, col)
            screen.blit(g2, (int(cx) - g2.get_width()//2, int(cy - th*1.9)))

            if self.editing_event is ev:
                r2 = max(8, int(15 * self.cam.zoom))
                pygame.draw.circle(screen, HIGHLIGHT,
                                   (int(cx), int(cy - th*0.3)), r2, 2)

    def _draw_bottom_bar(self):
        r = pygame.Rect(0, HEIGHT - BOTTOM_H, WIDTH, BOTTOM_H)
        pygame.draw.rect(screen, PANEL_DARK, r)
        pygame.draw.line(screen, PANEL_BORDER, (0, HEIGHT-BOTTOM_H), (WIDTH, HEIGHT-BOTTOM_H))
        am = self.project.active_map()
        nf = am.num_floors - 1 if am else 0

        parts = [f"Aba: {self.TAB_LABELS[self.tab]}"]
        if self.tab == self.TAB_LAYOUT:
            parts.append(f"sub: {self.LMODE_LABELS[self.layout_mode]}")
        elif self.tab == self.TAB_DETAILS:
            parts.append(f"sub: {self.DMODE_LABELS[self.details_mode]}")
        parts.append(f"Ferr: {self.active_tool}")
        parts.append(f"Andar {self.active_floor}/{nf}")
        parts.append(f"Zoom {self.cam.zoom:.2f}x")
        parts.append("TAB troca · B/E/F/R ferramenta")
        hint = "  ·  ".join(parts)
        draw_text(screen, hint, 10, HEIGHT - BOTTOM_H + 5, FONT_XS, TEXT_DIM)
        if self.autosave_dirty:
            draw_text(screen, "● salvando…", WIDTH - 90, HEIGHT-BOTTOM_H+5, FONT_XS, WARN)
        else:
            draw_text(screen, "✓ autosave", WIDTH - 90, HEIGHT-BOTTOM_H+5, FONT_XS, TEXT_DIM)

    def _draw_msg(self):
        if not self.msg: return
        r = FONT_M.render(self.msg, True, self.msg_color)
        bg = pygame.Surface((r.get_width()+20, r.get_height()+10), pygame.SRCALPHA)
        bg.fill((0,0,0,210))
        x = CANVAS_X + CANVAS_W//2 - bg.get_width()//2
        y = CANVAS_Y + CANVAS_H - 50
        screen.blit(bg, (x, y)); screen.blit(r, (x+10, y+5))

    def run(self):
        while self.running:
            dt = clock.tick(60) / 1000.0
            events = pygame.event.get()
            self.handle_events(events)
            self.update(dt)
            self.draw()
        pygame.quit()

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 64)
    print("MapEditor v19 — Texture Mode em paredes e escadas")
    print("=" * 64)
    MapEditorApp().run()