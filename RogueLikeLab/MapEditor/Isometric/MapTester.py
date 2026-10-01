# -*- coding: utf-8 -*-
"""
MapTester — Testa mapas gerados pelo MapEditor.
Carrega o JSON mais recente da pasta exports/maps e permite navegar com um player.
"""
import os, sys, json, math, heapq
from collections import deque
import pygame

# ============================================================
# INIT PYGAME (precisa vir ANTES de criar fontes)
# ============================================================
pygame.init()
pygame.font.init()

# ============================================================
# CONFIG
# ============================================================
WIDTH, HEIGHT = 1280, 740
HUD_H    = 40
CANVAS_X = 0
CANVAS_Y = 0
CANVAS_W = WIDTH
CANVAS_H = HEIGHT - HUD_H

BASE_TILE_W = 64.0
BASE_TILE_H = 32.0
CAM_SPEED_LERP = 6.0

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports", "maps")
TILES_DIR   = os.path.join(BASE_DIR, "exports", "tiles")
SPRITES_DIR = os.path.join(BASE_DIR, "exports", "sprites")
SPRITES_DATA_DIR = os.path.join(SPRITES_DIR, "data")

IMG_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')

G_WALL_H    = 32.0
G_TERRAIN_H = 32.0
G_STAIR_H   = 32.0
G_BLOCK_T   = 6.4

# --- Visual ---
WALL_FADE_RADIUS     = 5.0
WALL_FADE_MIN_ALPHA  = 40    # mais transparente
PICK_ALPHA_THRESHOLD = 128   # elementos com alpha abaixo disso não contam p/ picking

# --- Turn-based (roguelike) ---
TURN_DURATION = 0.12

FORM_FLAT = 'flat'
FORMS_RAMP  = ['ramp_n', 'ramp_s', 'ramp_e', 'ramp_w']
FORMS_STAIR = ['stair_n', 'stair_s', 'stair_e', 'stair_w']
ALL_FORMS   = [FORM_FLAT] + FORMS_RAMP + FORMS_STAIR
N_STEPS     = 4
WALL_HEIGHT_UNITS = 1.0

BG          = (22, 20, 18)
PANEL_BG    = (32, 28, 24)
PANEL_DARK  = (24, 21, 18)
TEXT        = (220, 210, 190)
TEXT_DIM    = (140, 130, 110)
TEXT_GOLD   = (240, 200, 80)
ACCENT      = (200, 155, 85)
ACCENT_DARK = (110, 85, 45)
ACCENT_BRIGHT = (240, 200, 100)
HIGHLIGHT   = (255, 220, 100)
SUCCESS     = (110, 200, 110)
DANGER      = (200, 70, 70)
WARN        = (230, 175, 70)
CANVAS_BG   = (16, 14, 12)

C_WALL_H_FRONT = (232, 220, 200)
C_WALL_V_FRONT = (196, 184, 164)
C_DOOR         = (110, 70, 40)
C_WINDOW       = (150, 212, 240)

FONT_L  = pygame.font.SysFont("georgia,dejavuserif,serif", 15, bold=True)
FONT_M  = pygame.font.SysFont("georgia,dejavuserif,serif", 12)
FONT_S  = pygame.font.SysFont("georgia,dejavuserif,serif", 11)
FONT_XS = pygame.font.SysFont("georgia,dejavuserif,serif", 10)

# ============================================================
# FUNÇÕES DE ALTURA
# ============================================================
def wall_px(cam):    return G_WALL_H    * cam.zoom
def terrain_px(cam): return G_TERRAIN_H * cam.zoom
def stair_px(cam):   return G_STAIR_H   * cam.zoom
def block_thick_px(cam): return G_BLOCK_T * cam.zoom

def tile_h_px(form, cam):
    if form and (form.startswith('stair_') or form.startswith('ramp_')):
        return stair_px(cam)
    return terrain_px(cam)

# ============================================================
# HELPERS
# ============================================================
def draw_text(surf, text, x, y, font=FONT_M, color=TEXT, center=False):
    r = font.render(str(text), True, color)
    if center: surf.blit(r, (x - r.get_width()//2, y))
    else:      surf.blit(r, (x, y))
    return r

def clamp(v, mn, mx): return max(mn, min(mx, v))

def darken(c, f):
    return tuple(max(0, min(255, int(c[i] * f))) for i in range(3))

def wall_val(v):
    if v is None: return ('wall', None)
    if isinstance(v, str): return (v, None)
    if isinstance(v, (tuple, list)):
        if len(v) >= 2: return (v[0], v[1])
        return (v[0], None)
    return ('wall', None)

def make_missing_texture(size=32):
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(0, size, 8):
        for x in range(0, size, 8):
            c = (255, 0, 255, 255) if ((x//8 + y//8) % 2 == 0) else (30, 30, 30, 255)
            pygame.draw.rect(surf, c, (x, y, 8, 8))
    return surf

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

def draw_masked_face(screen, pts, src_img, dim=1.0, alpha=255):
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
    final_alpha = int(255 * dim * alpha / 255)
    if final_alpha < 255:
        spr.set_alpha(final_alpha)
    screen.blit(spr, (x0, y0))

def draw_polygon_alpha(screen, color, pts, alpha=255):
    if alpha >= 255:
        pygame.draw.polygon(screen, color, pts)
        return
    if alpha <= 0: return
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0 = int(min(xs)), int(min(ys))
    x1, y1 = int(max(xs)), int(max(ys))
    w = max(1, x1 - x0); h = max(1, y1 - y0)
    tmp = pygame.Surface((w, h), pygame.SRCALPHA)
    rel = [(p[0] - x0, p[1] - y0) for p in pts]
    pygame.draw.polygon(tmp, (color[0], color[1], color[2], alpha), rel)
    screen.blit(tmp, (x0, y0))

# ============================================================
# LEITURA ROBUSTA DE JSON
# ============================================================
def read_json_robust(fp):
    with open(fp, "rb") as f:
        raw_bytes = f.read()
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        raw_bytes = raw_bytes[3:]
    elif raw_bytes.startswith(b'\xff\xfe') or raw_bytes.startswith(b'\xfe\xff'):
        try:
            text = raw_bytes.decode('utf-16').lstrip('\ufeff').strip()
            idx = text.find('{')
            if idx >= 0:
                return json.loads(text[idx:])
        except Exception:
            pass
    try:
        text = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        text = raw_bytes.decode('latin-1', errors='replace')
    text = text.strip()
    if not text:
        raise ValueError("arquivo vazio")
    idx = text.find('{')
    if idx < 0:
        raise ValueError("nenhum objeto JSON encontrado")
    text = text[idx:]
    return json.loads(text)

# ============================================================
# TILE / TILESET / SPRITE / EVENT / MAP / PROJECT
# ============================================================
class Tile:
    def __init__(self, tid, name, color=(150,150,150), walkable=True,
                 category="Geral", height=0, blocks_sight=False, folder=None):
        self.id = tid; self.name = name; self.color = tuple(color)
        self.walkable = walkable; self.category = category
        self.height = int(height); self.blocks_sight = bool(blocks_sight)
        self.folder = folder or os.path.join(TILES_DIR, tid)
        self._cache = {}; self._mtimes = {}

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
    def get(self, tid): return self.tiles.get(tid)
    @classmethod
    def from_dict(cls, d):
        ts = cls()
        for td in d.get("tiles", []): ts.add(Tile.from_dict(td))
        ts.order = d.get("order", list(ts.tiles.keys()))
        return ts

class CustomSprite:
    def __init__(self, name, path, surface=None):
        self.name = name; self.path = path
        if surface is not None:
            self.original = surface
        else:
            self.original = load_sprite_surface(path)
        self.scale = 1.0
        self.offset_x = 0.0; self.offset_y = 0.0
        self.anchor_x = 0.5; self.anchor_y = 1.0
        self.mirror_x = False
        self.mirror_y = False
        self._cache_key = None; self._cache = None

    def surface(self, cam_zoom=1.0, mirror_x=None, mirror_y=None):
        if mirror_x is None: mirror_x = self.mirror_x
        if mirror_y is None: mirror_y = self.mirror_y
        key = (round(self.scale,4), round(cam_zoom,4),
               bool(mirror_x), bool(mirror_y))
        if self._cache_key != key:
            ow, oh = self.original.get_size()
            img = self.original
            if mirror_x or mirror_y:
                img = pygame.transform.flip(img, bool(mirror_x), bool(mirror_y))
            w = max(1, int(ow * self.scale * cam_zoom))
            h = max(1, int(oh * self.scale * cam_zoom))
            self._cache = pygame.transform.smoothscale(img, (w, h))
            self._cache_key = key
        return self._cache

    def draw_at(self, screen, sx, sy, cam_zoom=1.0,
                dyn_dx=0.0, dyn_dy=0.0, dyn_dz_px=0.0,
                dyn_mirror_x=None, dyn_mirror_y=None, alpha=255):
        mx = self.mirror_x if dyn_mirror_x is None else (self.mirror_x ^ bool(dyn_mirror_x))
        my = self.mirror_y if dyn_mirror_y is None else (self.mirror_y ^ bool(dyn_mirror_y))
        s = self.surface(cam_zoom, mx, my)
        w, h = s.get_size()
        ox = (self.offset_x + dyn_dx) * cam_zoom
        oy = (self.offset_y + dyn_dy) * cam_zoom
        dx = sx - self.anchor_x * w + ox
        dy = sy - self.anchor_y * h + oy - dyn_dz_px
        if alpha >= 255:
            screen.blit(s, (int(dx), int(dy)))
        else:
            tmp = s.copy()
            tmp.set_alpha(alpha)
            screen.blit(tmp, (int(dx), int(dy)))

class GameEvent:
    def __init__(self, kind="other", x=0, y=0, eid=0):
        self.kind = kind; self.x = x; self.y = y; self.id = eid
        self.name = ""; self.tag = ""; self.data = {}
        self.sprite_idx = None
        self.trigger = "OnInteract"
    @classmethod
    def from_dict(cls, d):
        ev = cls(d.get("kind","other"), d["x"], d["y"], d.get("id",0))
        ev.name = d.get("name",""); ev.tag = d.get("tag","")
        ev.data = dict(d.get("data", {}))
        ev.sprite_idx = d.get("sprite_idx", None)
        ev.trigger = d.get("trigger", "OnInteract")
        return ev

def object_unpack(val):
    try:
        if len(val) >= 6:
            return (int(val[0]), float(val[1]), float(val[2]), float(val[3]),
                    bool(val[4]), bool(val[5]))
        elif len(val) >= 4:
            return (int(val[0]), float(val[1]), float(val[2]), float(val[3]),
                    False, False)
    except Exception:
        pass
    return None

DEFAULT_TILE_ID = 'sample'
def default_terrain():
    return {'tile_id': DEFAULT_TILE_ID, 'h': 0, 'form': FORM_FLAT}

class TileMap:
    def __init__(self, name="novo_mapa", w=24, h=20, num_floors=6):
        self.name = name; self.w = w; self.h = h
        self.num_floors = num_floors
        self.terrain = {}
        self.blocks = {}
        self.walls_h = {}; self.walls_v = {}
        self.objects = {}
        self.passability = {}
        self.events = []
        self.parent = None

    def in_bounds(self, x, y): return 0 <= x < self.w and 0 <= y < self.h
    def get_terrain(self, x, y): return self.terrain.get((x, y), default_terrain())
    def event_at(self, x, y):
        for ev in self.events:
            if ev.x == x and ev.y == y: return ev
        return None

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict):
            raise ValueError("TileMap.from_dict: entrada não é objeto")
        try: name = str(d.get("name", "mapa"))
        except Exception: name = "mapa"
        try: w = int(d.get("w", 24))
        except Exception: w = 24
        try: h = int(d.get("h", 20))
        except Exception: h = 20
        w = max(4, min(400, w)); h = max(4, min(400, h))
        try: nf = int(d.get("num_floors", 6))
        except Exception: nf = 6
        nf = max(1, min(64, nf))

        m = cls(name, w, h, nf)
        try: m.parent = d.get("parent")
        except Exception: m.parent = None

        m.terrain = {}
        for entry in (d.get("terrain", []) or []):
            try:
                if not isinstance(entry, (list, tuple)) or len(entry) < 3: continue
                x = int(entry[0]); y = int(entry[1]); tid = entry[2]
                hh = int(entry[3]) if len(entry) > 3 else 0
                fm = entry[4] if len(entry) > 4 else FORM_FLAT
                if not (0 <= x < w and 0 <= y < h): continue
                m.terrain[(x, y)] = {'tile_id': tid, 'h': hh, 'form': fm}
            except Exception: continue
        for y in range(h):
            for x in range(w):
                if (x, y) not in m.terrain:
                    m.terrain[(x, y)] = default_terrain()

        m.blocks = {}
        for e in (d.get("blocks", []) or []):
            try:
                if len(e) < 4: continue
                m.blocks[(int(e[0]), int(e[1]), int(e[2]))] = e[3]
            except Exception: continue

        m.walls_h = {}
        for e in (d.get("walls_h", []) or []):
            try:
                if len(e) >= 5:
                    m.walls_h[(int(e[0]), int(e[1]), int(e[2]))] = (e[3], e[4])
                elif len(e) == 4:
                    m.walls_h[(int(e[0]), int(e[1]), int(e[2]))] = (e[3], None)
            except Exception: continue
        m.walls_v = {}
        for e in (d.get("walls_v", []) or []):
            try:
                if len(e) >= 5:
                    m.walls_v[(int(e[0]), int(e[1]), int(e[2]))] = (e[3], e[4])
                elif len(e) == 4:
                    m.walls_v[(int(e[0]), int(e[1]), int(e[2]))] = (e[3], None)
            except Exception: continue

        m.objects = {}
        for e in (d.get("objects", []) or []):
            try:
                if len(e) >= 10:
                    key = (int(e[0]), int(e[1]), int(e[2]), int(e[3]))
                    val = (int(e[4]), float(e[5]), float(e[6]), float(e[7]),
                           bool(e[8]), bool(e[9]))
                elif len(e) >= 8:
                    key = (int(e[0]), int(e[1]), int(e[2]), int(e[3]))
                    val = (int(e[4]), float(e[5]), float(e[6]), float(e[7]),
                           False, False)
                elif len(e) == 4:
                    key = (int(e[0]), int(e[1]), int(e[2]), 0)
                    val = (int(e[3]), 0.0, 0.0, 0.0, False, False)
                else:
                    continue
                m.objects[key] = val
            except Exception: continue

        m.passability = {}
        for e in (d.get("passability", []) or []):
            try:
                if len(e) >= 3:
                    m.passability[(int(e[0]), int(e[1]))] = e[2]
            except Exception: continue

        m.events = []
        for evd in (d.get("events", []) or []):
            try:
                m.events.append(GameEvent.from_dict(evd))
            except Exception: pass
        return m

class Project:
    def __init__(self):
        self.tileset = TileSet()
        self.sprites = []
        self.maps = {}
        self.active_map_name = None
        self.wall_height = 32.0
        self.terrain_height = 32.0
        self.stair_height = 32.0
        self.block_thickness = 6.4

    def active_map(self): return self.maps.get(self.active_map_name)

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict):
            raise ValueError("Project.from_dict: JSON raiz não é objeto")
        p = cls.__new__(cls)
        try:
            p.wall_height    = max(1.0, float(d.get("wall_height", 32.0)))
            p.terrain_height = max(1.0, float(d.get("terrain_height", 32.0)))
            p.stair_height   = max(1.0, float(d.get("stair_height", 32.0)))
            p.block_thickness = max(1.0, float(d.get("block_thickness", 6.4)))
        except Exception:
            p.wall_height = 32.0; p.terrain_height = 32.0
            p.stair_height = 32.0; p.block_thickness = 6.4

        try:
            p.tileset = TileSet.from_dict(d.get("tileset", {}) or {})
        except Exception:
            p.tileset = TileSet()

        p.sprites = []
        for i, sd in enumerate(d.get("sprites", []) or []):
            if not isinstance(sd, dict):
                p.sprites.append(CustomSprite(f"missing_{i}", "",
                                              surface=make_missing_texture()))
                continue
            name = sd.get("name", f"sprite_{i}")
            path = sd.get("path", "")
            try:
                sp = CustomSprite(name, path)
                sp.scale    = float(sd.get("scale", 1.0))
                sp.offset_x = float(sd.get("offset_x", 0.0))
                sp.offset_y = float(sd.get("offset_y", 0.0))
                sp.anchor_x = float(sd.get("anchor_x", 0.5))
                sp.anchor_y = float(sd.get("anchor_y", 1.0))
                sp.mirror_x = bool(sd.get("mirror_x", False))
                sp.mirror_y = bool(sd.get("mirror_y", False))
                p.sprites.append(sp)
            except Exception:
                p.sprites.append(CustomSprite(name, path,
                                              surface=make_missing_texture()))

        p.maps = {}
        for key, md in (d.get("maps") or {}).items():
            try:
                m = TileMap.from_dict(md)
                p.maps[m.name] = m
            except Exception: pass

        p.active_map_name = d.get("active_map_name")
        if p.active_map_name not in p.maps:
            p.active_map_name = next(iter(p.maps)) if p.maps else None
        return p

def _sync_height_globals(project):
    global G_WALL_H, G_TERRAIN_H, G_STAIR_H, G_BLOCK_T
    try: G_WALL_H = max(1.0, float(project.wall_height))
    except Exception: G_WALL_H = 32.0
    try: G_TERRAIN_H = max(1.0, float(project.terrain_height))
    except Exception: G_TERRAIN_H = 32.0
    try: G_STAIR_H = max(1.0, float(project.stair_height))
    except Exception: G_STAIR_H = 32.0
    try: G_BLOCK_T = max(1.0, float(project.block_thickness))
    except Exception: G_BLOCK_T = 6.4

# ============================================================
# CAMERA / PROJECAO
# ============================================================
class Camera:
    def __init__(self):
        self.x = 0.0; self.y = 0.0; self.zoom = 1.0

def tile_size(cam): return BASE_TILE_W * cam.zoom, BASE_TILE_H * cam.zoom

def world_to_screen(px, py, cam, ox, oy):
    tw, th = tile_size(cam)
    return ox + (px - py) * tw * 0.5, oy + (px + py) * th * 0.5

def screen_to_world(sx, sy, cam, ox, oy):
    tw, th = tile_size(cam)
    ax = (sx - ox) / (tw * 0.5)
    ay = (sy - oy) / (th * 0.5)
    return (ax + ay) * 0.5, (ay - ax) * 0.5

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
# RENDER ISO
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

def draw_terrain_iso(screen, terrain_t, tile, x, y, z_base, cam, ox, oy,
                     alpha=255):
    form = terrain_t['form']; h = terrain_t['h']
    n_h, e_h, s_h, w_h = corner_heights(form, h)
    z = tile_h_px(form, cam)
    tw, th = tile_size(cam)
    tw_i = max(2, int(tw) + 2)
    th_i = max(2, int(th) + 2)

    N = world_to_screen(x,   y,   cam, ox, oy)
    E = world_to_screen(x+1, y,   cam, ox, oy)
    S = world_to_screen(x+1, y+1, cam, ox, oy)
    W = world_to_screen(x,   y+1, cam, ox, oy)
    Nt = (N[0], N[1] - n_h * z); Et = (E[0], E[1] - e_h * z)
    St = (S[0], S[1] - s_h * z); Wt = (W[0], W[1] - w_h * z)

    if form == FORM_FLAT and h == 0:
        top_spr = tile.get_sprite("top", (tw_i, th_i))
        if top_spr:
            d = mask_diamond(top_spr, tw_i, th_i)
            if alpha < 255:
                d = d.copy(); d.set_alpha(alpha)
            screen.blit(d, (int(N[0] - tw_i / 2), int(N[1])))
        else:
            draw_polygon_alpha(screen, tile.color, [N, E, S, W], alpha)
        return

    if s_h > 0 or w_h > 0:
        pts = [W, S, St, Wt]
        left = tile.get_sprite("side_left", (64, 64))
        if left is None: left = tile.get_sprite("top", (64, 64))
        if left:
            draw_masked_face(screen, pts, left, 1.0, alpha)
        else:
            draw_polygon_alpha(screen, darken(tile.color, 0.55), pts, alpha)

    if s_h > 0 or e_h > 0:
        pts = [S, E, Et, St]
        right = tile.get_sprite("side_right", (64, 64))
        if right is None: right = tile.get_sprite("top", (64, 64))
        if right:
            draw_masked_face(screen, pts, right, 1.0, alpha)
        else:
            draw_polygon_alpha(screen, darken(tile.color, 0.75), pts, alpha)

    if n_h == e_h == s_h == w_h:
        top_spr = tile.get_sprite("top", (tw_i, th_i))
        if top_spr:
            d = mask_diamond(top_spr, tw_i, th_i)
            if alpha < 255:
                d = d.copy(); d.set_alpha(alpha)
            screen.blit(d, (int(Nt[0] - tw_i / 2), int(Nt[1])))
        else:
            draw_polygon_alpha(screen, tile.color, [Nt, Et, St, Wt], alpha)
    else:
        top_spr = tile.get_sprite("top", (int(tw), int(th)))
        if top_spr:
            draw_masked_face(screen, [Nt, Et, St, Wt], top_spr, 1.0, alpha)
        else:
            draw_polygon_alpha(screen, tile.color, [Nt, Et, St, Wt], alpha)

def draw_block_iso(screen, tile, x, y, z, cam, ox, oy, dim=1.0, alpha=255):
    z_unit = wall_px(cam)
    thick = block_thick_px(cam)
    tw, th = tile_size(cam)
    z_bot = z * z_unit
    z_top = z_bot + thick
    tw_i = max(2, int(tw) + 2)
    th_i = max(2, int(th) + 2)

    Nb = world_to_screen(x,     y,     cam, ox, oy)
    Eb = world_to_screen(x + 1, y,     cam, ox, oy)
    Sb = world_to_screen(x + 1, y + 1, cam, ox, oy)
    Wb = world_to_screen(x,     y + 1, cam, ox, oy)

    N0 = (Nb[0], Nb[1] - z_bot); E0 = (Eb[0], Eb[1] - z_bot)
    S0 = (Sb[0], Sb[1] - z_bot); W0 = (Wb[0], Wb[1] - z_bot)
    N1 = (Nb[0], Nb[1] - z_top); E1 = (Eb[0], Eb[1] - z_top)
    S1 = (Sb[0], Sb[1] - z_top); W1 = (Wb[0], Wb[1] - z_top)

    def _face(pts, slot, fallback):
        spr = tile.get_sprite(slot, (64, 64))
        if spr: draw_masked_face(screen, pts, spr, dim, alpha)
        else: draw_polygon_alpha(screen, darken(tile.color, fallback * dim),
                                 pts, alpha)

    _face([W0, S0, S1, W1], "side_left",  0.55)
    _face([S0, E0, E1, S1], "side_right", 0.75)

    top_spr = tile.get_sprite("top", (tw_i, th_i))
    if top_spr:
        d = mask_diamond(top_spr, tw_i, th_i)
        if alpha < 255:
            d = d.copy(); d.set_alpha(alpha)
        screen.blit(d, (int(N1[0] - tw_i / 2), int(N1[1])))
    else:
        draw_polygon_alpha(screen, darken(tile.color, dim),
                           [N1, E1, S1, W1], alpha)

def draw_stairs_iso(screen, terrain_t, tile, x, y, cam, ox, oy, alpha=255):
    h = terrain_t['h']; form = terrain_t['form']
    direction = form.split('_')[1]
    z_unit = stair_px(cam)
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
        if src: draw_masked_face(screen, pts, src, 1.0, alpha)
        else: draw_polygon_alpha(screen, darken(base_col, factor), pts, alpha)

    for _, sx0, sy0, sx1, sy1, sz_top in steps:
        N = world_to_screen(sx0, sy0, cam, ox, oy)
        E = world_to_screen(sx1, sy0, cam, ox, oy)
        S = world_to_screen(sx1, sy1, cam, ox, oy)
        W = world_to_screen(sx0, sy1, cam, ox, oy)
        z_off = sz_top * z_unit
        Nt = (N[0], N[1]-z_off); Et = (E[0], E[1]-z_off)
        St = (S[0], S[1]-z_off); Wt = (W[0], W[1]-z_off)
        Nb = (N[0], N[1]); Eb = (E[0], E[1])
        Sb = (S[0], S[1]); Wb = (W[0], W[1])
        face([Nb, Wb, Wt, Nt], left_src, 0.55)
        face([Sb, Wb, Wt, St], left_src, 0.85)
        face([Eb, Sb, St, Et], right_src, 0.80)
        face([Nb, Eb, Et, Nt], right_src, 0.65)
        if top_src:
            draw_masked_face(screen, [Nt, Et, St, Wt], top_src, 1.0, alpha)
        else:
            draw_polygon_alpha(screen, base_col, [Nt, Et, St, Wt], alpha)

def _wall_overlay(screen, p1, p2, wh, kind, dim, alpha=255):
    if kind == 'door':
        t0, t1 = 0.18, 0.82; u0, u1 = 0.03, 0.90; col = C_DOOR
    else:
        t0, t1 = 0.22, 0.78; u0, u1 = 0.32, 0.76; col = C_WINDOW
    def lerp(a, b, t):
        return (a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t)
    q1 = lerp(p1, p2, t0); q2 = lerp(p1, p2, t1)
    r1 = (q1[0], q1[1] - wh * u0); r2 = (q2[0], q2[1] - wh * u0)
    r3 = (q2[0], q2[1] - wh * u1); r4 = (q1[0], q1[1] - wh * u1)
    draw_polygon_alpha(screen, darken(col, dim), [r1, r2, r3, r4], alpha)

def draw_wall_h_iso(screen, cam, ox, oy, x, y, z, kind, tile=None,
                    dim=1.0, alpha=255):
    z_off = z * wall_px(cam); wh = wall_px(cam) * WALL_HEIGHT_UNITS
    p1 = world_to_screen(x,     y, cam, ox, oy); p2 = world_to_screen(x + 1, y, cam, ox, oy)
    p1 = (p1[0], p1[1] - z_off); p2 = (p2[0], p2[1] - z_off)
    p1u = (p1[0], p1[1] - wh);   p2u = (p2[0], p2[1] - wh)
    quad = [(p1[0]-0.5, p1[1]), (p2[0]+0.5, p2[1]),
            (p2u[0]+0.5, p2u[1]), (p1u[0]-0.5, p1u[1])]

    textured = False
    if tile is not None:
        spr = tile.get_sprite("side_left", (64, 64))
        if spr is None: spr = tile.get_sprite("top", (64, 64))
        if spr is not None:
            draw_masked_face(screen, quad, spr, dim, alpha)
            textured = True
    if not textured:
        draw_polygon_alpha(screen, darken(C_WALL_H_FRONT, dim), quad, alpha)

    if kind in ('door', 'window'):
        _wall_overlay(screen, p1, p2, wh, kind, dim, alpha)

def draw_wall_v_iso(screen, cam, ox, oy, x, y, z, kind, tile=None,
                    dim=1.0, alpha=255):
    z_off = z * wall_px(cam); wh = wall_px(cam) * WALL_HEIGHT_UNITS
    p1 = world_to_screen(x, y,     cam, ox, oy); p2 = world_to_screen(x, y + 1, cam, ox, oy)
    p1 = (p1[0], p1[1] - z_off); p2 = (p2[0], p2[1] - z_off)
    p1u = (p1[0], p1[1] - wh);   p2u = (p2[0], p2[1] - wh)
    quad = [(p1[0], p1[1]-0.5), (p2[0], p2[1]+0.5),
            (p2u[0], p2u[1]+0.5), (p1u[0], p1u[1]-0.5)]

    textured = False
    if tile is not None:
        spr = tile.get_sprite("side_right", (64, 64))
        if spr is None: spr = tile.get_sprite("side_left", (64, 64))
        if spr is None: spr = tile.get_sprite("top", (64, 64))
        if spr is not None:
            draw_masked_face(screen, quad, spr, dim, alpha)
            textured = True
    if not textured:
        draw_polygon_alpha(screen, darken(C_WALL_V_FRONT, dim), quad, alpha)

    if kind in ('door', 'window'):
        _wall_overlay(screen, p1, p2, wh, kind, dim, alpha)

# ============================================================
# INTERPOLAÇÃO DE Z DO PISO NO PONTO (px)
# ============================================================
def cell_z_px(m, px, py, h_terr=None, h_stair=None):
    if h_terr is None: h_terr = G_TERRAIN_H
    if h_stair is None: h_stair = G_STAIR_H
    tx = int(math.floor(px)); ty = int(math.floor(py))
    if not m.in_bounds(tx, ty): return 0.0
    t = m.get_terrain(tx, ty)
    form = t['form']
    ch = corner_heights(form, t['h'])
    fx = px - tx; fy = py - ty
    n, e, s, w = ch
    top = n * (1 - fx) + e * fx
    bot = w * (1 - fx) + s * fy
    z_level = top * (1 - fy) + bot * fy
    if form.startswith(('stair_', 'ramp_')):
        return z_level * h_stair
    return z_level * h_terr

def player_z_px(m, px, py, floor_z, cam):
    if floor_z <= 0:
        return cell_z_px(m, px, py)
    base = floor_z * G_WALL_H * cam.zoom
    terr_z = cell_z_px(m, px, py)
    return max(base, terr_z)

# ============================================================
# WALKABILITY / PAREDES / PATHFINDING
# ============================================================
def can_stand_at(m, tileset, x, y, floor_z):
    if not m.in_bounds(x, y): return False
    t = m.get_terrain(x, y)
    tile = tileset.get(t['tile_id'])
    if not tile or not tile.walkable: return False
    if floor_z <= 0:
        return True
    form = t['form']
    if form.startswith('stair_') or form.startswith('ramp_'):
        return True
    if (x, y, floor_z) in m.blocks: return True
    if (x, y, floor_z - 1) in m.blocks: return True
    terr_z = t['h'] * G_TERRAIN_H
    target_z = floor_z * G_WALL_H
    if abs(terr_z - target_z) <= max(G_TERRAIN_H, G_WALL_H) * 0.6:
        return True
    return False

def cell_avg_z_px(m, cell, h_terr=None, h_stair=None):
    if h_terr is None: h_terr = G_TERRAIN_H
    if h_stair is None: h_stair = G_STAIR_H
    x, y = cell
    t = m.get_terrain(x, y)
    form = t['form']
    ch = corner_heights(form, t['h'])
    avg = sum(ch) / 4.0
    if form.startswith(('stair_', 'ramp_')):
        return avg * h_stair
    return avg * h_terr

def _wall_is_solid(val):
    if val is None: return False
    kind, _ = wall_val(val)
    return kind in ('wall', 'window')

def wall_blocks_move(m, a, b, floor_z):
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    if dx == 1 and dy == 0:
        return _wall_is_solid(m.walls_v.get((bx, ay, floor_z)))
    if dx == -1 and dy == 0:
        return _wall_is_solid(m.walls_v.get((ax, ay, floor_z)))
    if dx == 0 and dy == 1:
        return _wall_is_solid(m.walls_h.get((ax, by, floor_z)))
    if dx == 0 and dy == -1:
        return _wall_is_solid(m.walls_h.get((ax, ay, floor_z)))
    return False

def _is_stair(m, x, y):
    t = m.get_terrain(x, y)
    form = t['form']
    return form.startswith('stair_') or form.startswith('ramp_')

def can_step(m, tileset, a, b, floor_a, floor_b):
    if a == b:
        if floor_a == floor_b: return False
        if abs(floor_a - floor_b) != 1: return False
        if not _is_stair(m, a[0], a[1]): return False
        return can_stand_at(m, tileset, b[0], b[1], floor_b)
    if floor_a != floor_b:
        return False
    if not can_stand_at(m, tileset, b[0], b[1], floor_b): return False
    if wall_blocks_move(m, a, b, floor_a): return False
    if floor_a == 0:
        if _is_stair(m, b[0], b[1]): return True
        za = cell_avg_z_px(m, a)
        zb = cell_avg_z_px(m, b)
        return abs(zb - za) <= G_TERRAIN_H + 0.01
    return True

def find_path(m, tileset, start, goal, floor_start, floor_goal):
    start_s = (start[0], start[1], floor_start)
    goal_s = (goal[0], goal[1], floor_goal)
    if start_s == goal_s: return [start_s]
    if not can_stand_at(m, tileset, goal[0], goal[1], floor_goal): return []
    open_set = [(0, start_s)]
    came_from = {}
    g_score = {start_s: 0.0}
    closed = set()
    while open_set:
        _, cur = heapq.heappop(open_set)
        if cur == goal_s:
            path = [cur]
            while cur in came_from:
                cur = came_from[cur]; path.append(cur)
            path.reverse()
            return path
        if cur in closed: continue
        closed.add(cur)
        cx, cy, cf = cur
        neighbors = []
        for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)):
            neighbors.append((cx + dx, cy + dy, cf))
        if _is_stair(m, cx, cy):
            neighbors.append((cx, cy, cf + 1))
            neighbors.append((cx, cy, cf - 1))
        for nb in neighbors:
            nbx, nby, nbf = nb
            if nbf < 0 or nbf >= m.num_floors: continue
            if nb in closed: continue
            if not can_step(m, tileset, (cx, cy), (nbx, nby), cf, nbf): continue
            extra = 1.0 if nbf != cf else 0.0
            tentative = g_score[cur] + 1.0 + extra
            if tentative < g_score.get(nb, 1e18):
                came_from[nb] = cur
                g_score[nb] = tentative
                h = abs(nbx - goal_s[0]) + abs(nby - goal_s[1]) \
                    + abs(nbf - goal_s[2]) * 2
                heapq.heappush(open_set, (tentative + h, nb))
    return []

# ============================================================
# DETECÇÃO DE SALA (TELHADO) POR FLOOD FILL
# ============================================================
def compute_room_occlusion(m, pcx, pcy, player_floor):
    hidden_blocks = set()
    hidden_walls = set()
    for f in range(player_floor + 1, m.num_floors):
        if (pcx, pcy, f) not in m.blocks:
            continue
        queue = deque([(pcx, pcy)])
        visited = set()
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in visited: continue
            if not m.in_bounds(cx, cy): continue
            if (cx, cy, f) not in m.blocks: continue
            visited.add((cx, cy))
            hidden_blocks.add((cx, cy, f))
            queue.append((cx+1, cy)); queue.append((cx-1, cy))
            queue.append((cx, cy+1)); queue.append((cx, cy-1))
        for (tx, ty, tz) in list(m.walls_h.keys()):
            if tz != f: continue
            if (tx, ty, f) in hidden_blocks or (tx, ty+1, f) in hidden_blocks:
                hidden_walls.add(('h', tx, ty, tz))
        for (tx, ty, tz) in list(m.walls_v.keys()):
            if tz != f: continue
            if (tx, ty, f) in hidden_blocks or (tx+1, ty, f) in hidden_blocks:
                hidden_walls.add(('v', tx, ty, tz))
    return hidden_blocks, hidden_walls

# ============================================================
# ALPHA UNIFICADO PARA ELEMENTOS
# ============================================================
def element_alpha_for_player(tx, ty, tz, pcx, pcy, pfz,
                              radius=WALL_FADE_RADIUS,
                              min_alpha=WALL_FADE_MIN_ALPHA):
    """
    Alpha de um elemento (bloco/parede) baseado em sua posição relativa ao player.

    Regra:
      - Depth (tx+ty) menor que do player  → opaco (atrás)
      - Depth igual e andar ≤ player       → opaco
      - Andar abaixo do player             → opaco
      - Caso contrário (à frente ou acima) → fade proporcional à distância
    """
    # 1) Atrás (depth menor)
    if (tx + ty) < (pcx + pcy):
        return 255
    # 2) Mesma depth, andar ≤ player
    if (tx + ty) == (pcx + pcy) and tz <= pfz:
        return 255
    # 3) Andar abaixo do player
    if tz < pfz:
        return 255
    # 4) À frente ou acima → fade
    dxy = math.hypot(tx - pcx, ty - pcy)
    # Elemento na mesma célula (e acima): fade máximo
    if dxy < 0.5 and tz > pfz:
        return min_alpha
    if dxy > radius:
        return 255
    t = clamp(1.0 - dxy / radius, 0.0, 1.0)
    # Fade extra se estiver acima do player
    if tz > pfz:
        t = min(1.0, t + 0.3 * (tz - pfz))
    return int(255 - t * (255 - min_alpha))

# ============================================================
# PLAYER (turn-based)
# ============================================================
class Player:
    def __init__(self, x=0, y=0, sprite_idx=None):
        self.cell_x = int(x)
        self.cell_y = int(y)
        self.visual_x = float(x)
        self.visual_y = float(y)
        self.floor_z = 0
        self.sprite_idx = sprite_idx
        self.path = []
        self.target_marker = None
        self._animating = False
        self._anim_t = 0.0
        self._anim_from = (0.0, 0.0)
        self._anim_to = (0.0, 0.0)
        self._step_cooldown = 0.0

    def cell(self):
        return (self.cell_x, self.cell_y)

    def set_path(self, path):
        if not path: return
        cur = (self.cell_x, self.cell_y, self.floor_z)
        if path and path[0] == cur:
            path = path[1:]
        self.path = list(path)
        self.target_marker = self.path[-1] if self.path else None

    def _start_move(self, nx, ny, nf):
        self._anim_from = (self.visual_x, self.visual_y)
        self._anim_to = (float(nx), float(ny))
        self._anim_t = 0.0
        self._animating = True
        self.cell_x = nx; self.cell_y = ny; self.floor_z = nf

    def try_step(self, dx, dy, m, tileset):
        if self._animating: return False
        nx = self.cell_x + dx; ny = self.cell_y + dy
        if not can_step(m, tileset, (self.cell_x, self.cell_y), (nx, ny),
                        self.floor_z, self.floor_z):
            return False
        self.path = []
        self.target_marker = None
        self._start_move(nx, ny, self.floor_z)
        return True

    def advance_path(self, m, tileset):
        if self._animating or not self.path: return False
        nx, ny, nf = self.path.pop(0)
        self._start_move(nx, ny, nf)
        if not self.path:
            self.target_marker = None
        return True

    def update(self, dt):
        if self._animating:
            self._anim_t += dt / max(1e-6, TURN_DURATION)
            if self._anim_t >= 1.0:
                self.visual_x = self._anim_to[0]
                self.visual_y = self._anim_to[1]
                self._animating = False
            else:
                t = self._anim_t
                self.visual_x = self._anim_from[0] + (self._anim_to[0] - self._anim_from[0]) * t
                self.visual_y = self._anim_from[1] + (self._anim_to[1] - self._anim_from[1]) * t
        if self._step_cooldown > 0:
            self._step_cooldown -= dt

    def z_px(self, m, cam):
        return player_z_px(m, self.visual_x, self.visual_y, self.floor_z, cam)

    def draw(self, screen, cam, ox, oy, project, m):
        tw, th = tile_size(cam)
        wx = (self.visual_x - self.visual_y) * tw * 0.5
        wy = (self.visual_x + self.visual_y) * th * 0.5
        scr_x = ox + wx
        scr_y = oy + wy + th * 0.5 - self.z_px(m, cam)

        sh = pygame.Surface((28, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 90), (0, 0, 28, 12))
        screen.blit(sh, (int(scr_x) - 14, int(scr_y) - 6))

        if (self.sprite_idx is not None
                and 0 <= self.sprite_idx < len(project.sprites)):
            sp = project.sprites[self.sprite_idx]
            sp.draw_at(screen, scr_x, scr_y, cam.zoom)
        else:
            r = 10
            pygame.draw.circle(screen, (100, 200, 255),
                               (int(scr_x), int(scr_y) - r), r)
            pygame.draw.circle(screen, (20, 40, 70),
                               (int(scr_x), int(scr_y) - r), r, 2)
            pygame.draw.circle(screen, (240, 250, 255),
                               (int(scr_x), int(scr_y) - r), 3)

# ============================================================
# APP
# ============================================================
class MapTesterApp:
    def __init__(self, json_path=None):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Map Tester")
        self.clock = pygame.time.Clock()

        self.project = None
        self.map = None
        self.player = None
        self.cam = Camera()
        self.cam.zoom = 1.0

        self.running = True
        self.msg = ""
        self.msg_timer = 0.0
        self.load_error = ""

        self._room_cache_key = None
        self._room_cache = (set(), set())

        self._load(json_path)
        if self.map:
            self._spawn_player()

    def _msg(self, text, t=3.0):
        self.msg = text; self.msg_timer = t

    def _try_load_file(self, fp):
        try:
            if os.path.getsize(fp) < 4:
                print(f"[Load] '{os.path.basename(fp)}' ignorado (vazio).")
                return False
        except Exception:
            return False
        try:
            raw = read_json_robust(fp)
        except Exception as e:
            print(f"[Load] '{os.path.basename(fp)}' inválido: {e}")
            return False
        try:
            proj = Project.from_dict(raw)
        except Exception as e:
            print(f"[Load] '{os.path.basename(fp)}' from_dict: {e}")
            return False
        if not proj.maps:
            print(f"[Load] '{os.path.basename(fp)}' não tem mapas.")
            return False
        active = proj.active_map()
        if active is None:
            active = next(iter(proj.maps.values()))
        self.project = proj
        _sync_height_globals(self.project)
        self.map = active
        print(f"[Load] OK: {os.path.basename(fp)} | mapa '{self.map.name}' "
              f"{self.map.w}x{self.map.h} | "
              f"hwall={G_WALL_H} hterr={G_TERRAIN_H} hstair={G_STAIR_H}")
        return True

    def _load(self, json_path):
        if json_path:
            if os.path.isfile(json_path):
                if self._try_load_file(json_path):
                    return
                self.load_error = f"Falha ao carregar: {os.path.basename(json_path)}"
                return
            else:
                self.load_error = f"Arquivo não encontrado: {json_path}"
                return

        try:
            all_files = [f for f in os.listdir(EXPORTS_DIR)
                         if f.lower().endswith(".json")
                         and not f.startswith("_")]
        except Exception as e:
            self.load_error = f"Erro listando pasta: {e}"
            print(f"[Load] {self.load_error}")
            return

        if not all_files:
            self.load_error = ("Nenhum .json encontrado em exports/maps. "
                               "Salve um mapa no editor primeiro.")
            print(f"[Load] {self.load_error}")
            return

        try:
            all_files.sort(key=lambda f: os.path.getmtime(
                os.path.join(EXPORTS_DIR, f)), reverse=True)
        except Exception:
            all_files.sort()

        print(f"[Load] {len(all_files)} arquivo(s) .json encontrado(s), "
              f"tentando carregar...")

        for fname in all_files:
            fp = os.path.join(EXPORTS_DIR, fname)
            if self._try_load_file(fp):
                return

        self.load_error = ("Nenhum .json válido em exports/maps.")
        print(f"[Load] {self.load_error}")

    def _spawn_player(self):
        if not self.map: return
        spawn = None
        for ev in self.map.events:
            if ev.kind == "player_spawn":
                spawn = ev; break

        if spawn is not None:
            sx, sy = spawn.x, spawn.y
            sprite_idx = spawn.sprite_idx
            self.player = Player(sx, sy, sprite_idx)
            if (sprite_idx is not None and 0 <= sprite_idx < len(self.project.sprites)):
                self._msg(f"Player spawn em ({sx},{sy}) com sprite.", 3.5)
            else:
                self._msg(f"Player spawn em ({sx},{sy}) — círculo (sem sprite).", 3.5)
        else:
            cx = self.map.w // 2
            cy = self.map.h // 2
            self.player = Player(cx, cy, None)
            self._msg("Sem player_spawn — spawn no centro (círculo).", 3.5)

        self.cam.x = self.player.visual_x
        self.cam.y = self.player.visual_y
        self._room_cache_key = None

    def _iso_origin(self):
        cx = CANVAS_X + CANVAS_W * 0.5
        cy = CANVAS_Y + CANVAS_H * 0.5
        tw, th = tile_size(self.cam)
        return (cx - self.cam.x * tw * 0.5 + self.cam.y * tw * 0.5,
                cy - self.cam.x * th * 0.5 - self.cam.y * th * 0.5)

    def _refresh_room_cache(self):
        if not self.map: return
        if self.player:
            pcx = self.player.cell_x; pcy = self.player.cell_y
            pfz = self.player.floor_z
        else:
            pcx = pcy = -999; pfz = 0
        key = (pcx, pcy, pfz)
        if self._room_cache_key != key:
            self._room_cache_key = key
            self._room_cache = compute_room_occlusion(self.map, pcx, pcy, pfz)

    # ----------------------------------------------------------------
    # PICKING PRECISO DE SUPERFÍCIE (por pixel)
    # ----------------------------------------------------------------
    def _pick_surface_at(self, screen_pos):
        m = self.map
        if not m: return None
        ox, oy = self._iso_origin()
        z_unit = wall_px(self.cam)
        block_t = block_thick_px(self.cam)
        sx, sy = screen_pos

        if self.player:
            pcx = self.player.cell_x; pcy = self.player.cell_y
            pfz = self.player.floor_z
        else:
            pcx = pcy = -999; pfz = 0

        self._refresh_room_cache()
        hidden_blocks, _ = self._room_cache

        wx, wy = screen_to_world(sx, sy, self.cam, ox, oy)
        base_tx = int(math.floor(wx))
        base_ty = int(math.floor(wy))
        R = 8

        candidates = []
        for ty in range(max(0, base_ty - R), min(m.h, base_ty + R + 1)):
            for tx in range(max(0, base_tx - R), min(m.w, base_tx + R + 1)):
                # 1) Terreno (andar 0)
                t = m.get_terrain(tx, ty)
                tile = self.project.tileset.get(t['tile_id'])
                if tile and tile.walkable:
                    form = t['form']
                    z = tile_h_px(form, self.cam)
                    N = world_to_screen(tx, ty, self.cam, ox, oy)
                    E = world_to_screen(tx+1, ty, self.cam, ox, oy)
                    S = world_to_screen(tx+1, ty+1, self.cam, ox, oy)
                    W = world_to_screen(tx, ty+1, self.cam, ox, oy)
                    if form == FORM_FLAT:
                        n_h = e_h = s_h = w_h = float(t['h'])
                    else:
                        n_h, e_h, s_h, w_h = corner_heights(form, t['h'])
                    pts = [(N[0], N[1]-n_h*z), (E[0], E[1]-e_h*z),
                           (S[0], S[1]-s_h*z), (W[0], W[1]-w_h*z)]
                    if point_in_poly(sx, sy, pts):
                        depth = (tx + ty) * 10000 + 0
                        candidates.append((depth, tx, ty, 0))
                # 2) Blocos em andares superiores
                for f in range(1, m.num_floors):
                    if (tx, ty, f) not in m.blocks: continue
                    if (tx, ty, f) in hidden_blocks: continue
                    a = element_alpha_for_player(tx, ty, f, pcx, pcy, pfz)
                    if a < PICK_ALPHA_THRESHOLD: continue
                    z_top = f * z_unit + block_t
                    N = world_to_screen(tx, ty, self.cam, ox, oy)
                    E = world_to_screen(tx+1, ty, self.cam, ox, oy)
                    S = world_to_screen(tx+1, ty+1, self.cam, ox, oy)
                    W = world_to_screen(tx, ty+1, self.cam, ox, oy)
                    pts = [(N[0], N[1]-z_top), (E[0], E[1]-z_top),
                           (S[0], S[1]-z_top), (W[0], W[1]-z_top)]
                    if point_in_poly(sx, sy, pts):
                        depth = (tx + ty) * 10000 + f
                        candidates.append((depth, tx, ty, f))

        if not candidates: return None
        candidates.sort(reverse=True)
        return candidates[0][1:]

    # ----------------------------------------------------------------
    # INPUT
    # ----------------------------------------------------------------
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False; return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False; return
                if e.key == pygame.K_r and self.player:
                    self._spawn_player()
                    self._msg("Respawn.", 2.0)
                if e.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    self.cam.zoom = clamp(self.cam.zoom * 1.15, 0.3, 3.5)
                if e.key == pygame.K_MINUS or e.key == pygame.K_KP_MINUS:
                    self.cam.zoom = clamp(self.cam.zoom / 1.15, 0.3, 3.5)
                if e.key == pygame.K_HOME and self.player:
                    self.cam.zoom = 1.0
                    self.cam.x = self.player.visual_x
                    self.cam.y = self.player.visual_y
                if e.key == pygame.K_PERIOD or e.key == pygame.K_SPACE:
                    if self.player and not self.player._animating:
                        self.player.advance_path(self.map, self.project.tileset)
                if e.key == pygame.K_PAGEUP and self.player:
                    if _is_stair(self.map, self.player.cell_x, self.player.cell_y):
                        nf = self.player.floor_z + 1
                        if nf < self.map.num_floors:
                            self.player.floor_z = nf
                            self._room_cache_key = None
                            self._msg(f"Andar {nf}", 1.5)
                if e.key == pygame.K_PAGEDOWN and self.player:
                    if _is_stair(self.map, self.player.cell_x, self.player.cell_y):
                        nf = self.player.floor_z - 1
                        if nf >= 0:
                            self.player.floor_z = nf
                            self._room_cache_key = None
                            self._msg(f"Andar {nf}", 1.5)
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    self._click_to_move(e.pos)
                elif e.button == 3:
                    if self.player:
                        self.player.path = []
                        self.player.target_marker = None

    def _click_to_move(self, pos):
        if not self.map or not self.player: return
        result = self._pick_surface_at(pos)
        if result is None:
            self._msg("Clique fora do mapa.", 1.2)
            return
        gx, gy, gf = result
        start = (self.player.cell_x, self.player.cell_y)
        path = find_path(self.map, self.project.tileset, start, (gx, gy),
                         self.player.floor_z, gf)
        if not path:
            self._msg(f"Sem caminho até ({gx},{gy}) [andar {gf}].", 1.8)
            return
        self.player.set_path(path)
        self._msg(f"Indo para ({gx},{gy}) andar {gf} — {len(path)-1} passos.", 1.8)

    def update(self, dt):
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0: self.msg = ""

        if not self.map or not self.player: return

        keys = pygame.key.get_pressed()
        dx = dy = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]: dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        if (dx or dy) and not self.player._animating and self.player._step_cooldown <= 0:
            if self.player.try_step(dx, dy, self.map, self.project.tileset):
                self.player._step_cooldown = TURN_DURATION

        if (self.player.path and not self.player._animating
                and self.player._step_cooldown <= 0):
            if self.player.advance_path(self.map, self.project.tileset):
                self.player._step_cooldown = TURN_DURATION * 0.6

        self.player.update(dt)

        lerp = min(1.0, dt * CAM_SPEED_LERP)
        target_x = self.player.visual_x
        target_y = self.player.visual_y
        self.cam.x += (target_x - self.cam.x) * lerp
        self.cam.y += (target_y - self.cam.y) * lerp

    # ----------------------------------------------------------------
    # RENDER
    # ----------------------------------------------------------------
    def _render_iso(self, screen, ox, oy):
        m = self.map
        if not m: return
        tw, th = tile_size(self.cam)
        u_wall = wall_px(self.cam)

        if self.player:
            px = self.player.visual_x; py = self.player.visual_y
            pcx = self.player.cell_x; pcy = self.player.cell_y
            player_floor = self.player.floor_z
        else:
            px = py = -999.0
            pcx = pcy = -999
            player_floor = 0

        self._refresh_room_cache()
        hidden_blocks, hidden_walls = self._room_cache

        items = []
        # Terreno
        for (tx, ty), t in m.terrain.items():
            u_terr = tile_h_px(t['form'], self.cam)
            h_px = t['h'] * u_terr + (0.5 * u_terr if t['form'] != FORM_FLAT else 0.0)
            items.append(((tx + ty, h_px, 0), 'terrain', (tx, ty, t)))
        # Blocos
        for (tx, ty, tz), blk in m.blocks.items():
            if (tx, ty, tz) in hidden_blocks: continue
            a = element_alpha_for_player(tx, ty, tz, pcx, pcy, player_floor)
            if a <= 0: continue
            items.append(((tx + ty, tz * u_wall, 1), 'block', (tx, ty, tz, blk, a)))
        # Paredes H
        for (tx, ty, tz), val in m.walls_h.items():
            if ('h', tx, ty, tz) in hidden_walls: continue
            kind, tid = wall_val(val)
            a = element_alpha_for_player(tx, ty, tz, pcx, pcy, player_floor)
            if a <= 0: continue
            items.append(((tx + ty, tz * u_wall, 2), 'wall_h',
                          (tx, ty, tz, kind, tid, a)))
        # Paredes V
        for (tx, ty, tz), val in m.walls_v.items():
            if ('v', tx, ty, tz) in hidden_walls: continue
            kind, tid = wall_val(val)
            a = element_alpha_for_player(tx, ty, tz, pcx, pcy, player_floor)
            if a <= 0: continue
            items.append(((tx + ty, tz * u_wall, 2), 'wall_v',
                          (tx, ty, tz, kind, tid, a)))
        # Objetos
        for (tx, ty, tz, layer), val in m.objects.items():
            up = object_unpack(val)
            if up is None: continue
            sid, dx, dy, dz, dmx, dmy = up
            if sid < 0 or sid >= len(self.project.sprites): continue
            if tz > player_floor and (tx, ty, tz) in hidden_blocks:
                continue
            terr = m.get_terrain(tx, ty)
            u_terr = tile_h_px(terr['form'], self.cam)
            h_px = tz * u_wall + terr['h'] * u_terr
            items.append(((tx + ty, h_px + 0.01, 3, layer), 'object',
                          (tx, ty, tz, layer, sid, dx, dy, dz, dmx, dmy)))
        # Player
        if self.player:
            pz_px = self.player.z_px(m, self.cam)
            items.append((((px + py), pz_px + 0.005, 4), 'player', None))

        items.sort(key=lambda it: it[0])

        for key, kind, data in items:
            if kind == 'player':
                self.player.draw(screen, self.cam, ox, oy, self.project, m)
                continue
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
                tz = data[2]; tid = data[3]; alpha = data[4]
                tile = self.project.tileset.get(tid)
                if not tile: continue
                draw_block_iso(screen, tile, tx, ty, tz, self.cam, ox, oy,
                               alpha=alpha)
            elif kind == 'wall_h':
                tz = data[2]; kw = data[3]; tid = data[4]; alpha = data[5]
                tile = self.project.tileset.get(tid) if tid else None
                draw_wall_h_iso(screen, self.cam, ox, oy, tx, ty, tz, kw,
                                tile, alpha=alpha)
            elif kind == 'wall_v':
                tz = data[2]; kw = data[3]; tid = data[4]; alpha = data[5]
                tile = self.project.tileset.get(tid) if tid else None
                draw_wall_v_iso(screen, self.cam, ox, oy, tx, ty, tz, kw,
                                tile, alpha=alpha)
            elif kind == 'object':
                (tz, layer, sid, dx, dy, dz, dmx, dmy) = (
                    data[2], data[3], data[4], data[5],
                    data[6], data[7], data[8], data[9])
                sp = self.project.sprites[sid]
                terr = m.get_terrain(tx, ty)
                u_terr = tile_h_px(terr['form'], self.cam)
                wx = (tx - ty) * tw * 0.5; wy = (tx + ty) * th * 0.5
                scr_x = ox + wx
                scr_y = oy + wy + th * 0.5 - (tz * u_wall + terr['h'] * u_terr)
                sp.draw_at(screen, scr_x, scr_y, self.cam.zoom,
                           dyn_dx=dx, dyn_dy=dy, dyn_dz_px=dz * u_wall,
                           dyn_mirror_x=dmx, dyn_mirror_y=dmy)

    def _draw_path_markers(self, screen, ox, oy):
        if not self.player or not self.map: return
        tw, th = tile_size(self.cam)
        for (tx, ty, tz) in self.player.path:
            wx = (tx - ty) * tw * 0.5
            wy = (tx + ty) * th * 0.5
            cx = ox + wx
            cy = oy + wy + th * 0.5
            if tz == 0:
                t = self.map.get_terrain(tx, ty)
                cy -= t['h'] * tile_h_px(t['form'], self.cam)
            else:
                cy -= tz * wall_px(self.cam)
            s = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
            hw = tw * 0.5; hh = th * 0.5
            rel = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]
            pygame.draw.polygon(s, (255, 220, 100, 70), rel)
            screen.blit(s, (0, 0))

        if self.player.target_marker:
            tx, ty, tz = self.player.target_marker
            wx = (tx - ty) * tw * 0.5
            wy = (tx + ty) * th * 0.5
            cx = ox + wx
            cy = oy + wy + th * 0.5
            if tz == 0:
                t = self.map.get_terrain(tx, ty)
                cy -= t['h'] * tile_h_px(t['form'], self.cam)
            else:
                cy -= tz * wall_px(self.cam)
            hw = tw * 0.5; hh = th * 0.5
            pygame.draw.polygon(screen, (255, 220, 100),
                                [(cx, cy - hh), (cx + hw, cy),
                                 (cx, cy + hh), (cx - hw, cy)], 2)

    def _draw_hud(self):
        r = pygame.Rect(0, HEIGHT - HUD_H, WIDTH, HUD_H)
        pygame.draw.rect(self.screen, PANEL_DARK, r)
        pygame.draw.line(self.screen, ACCENT_DARK, (0, HEIGHT - HUD_H),
                         (WIDTH, HEIGHT - HUD_H))

        if self.player and self.map:
            px = self.player.cell_x
            py = self.player.cell_y
            pf = self.player.floor_z
            draw_text(self.screen, f"Pos ({px},{py})  Andar {pf}",
                      12, HEIGHT - HUD_H + 12, FONT_M, TEXT)

            if self.player.path:
                draw_text(self.screen, f"Passos: {len(self.player.path)}",
                          240, HEIGHT - HUD_H + 12, FONT_M, TEXT_GOLD)

            draw_text(self.screen, f"Zoom {self.cam.zoom:.2f}x",
                      420, HEIGHT - HUD_H + 12, FONT_M, TEXT_DIM)

        if self.map:
            mtext = (f"{self.map.name}  {self.map.w}x{self.map.h}  "
                     f"andares {self.map.num_floors}")
            r2 = FONT_S.render(mtext, True, TEXT_DIM)
            self.screen.blit(r2, (WIDTH - r2.get_width() - 12,
                                  HEIGHT - HUD_H + 13))

        if self.msg:
            r3 = FONT_M.render(self.msg, True, TEXT_GOLD)
            self.screen.blit(r3, (12, HEIGHT - HUD_H - 24))

        if self.load_error:
            r4 = FONT_M.render(self.load_error, True, DANGER)
            self.screen.blit(r4, (12, HEIGHT - HUD_H - 44))

    def _draw_help(self):
        lines = [
            "WASD/setas: mover   |   Clique esq.: ir até   |   Clique dir.: cancelar",
            "+/-: zoom   |   Home: recentrar   |   Espaço/.: próximo passo   |   R: respawn",
            "PgUp/PgDn: subir/descer andar (sobre escada)",
        ]
        y = 10
        for ln in lines:
            r = FONT_S.render(ln, True, TEXT_DIM)
            self.screen.blit(r, (10, y))
            y += 16

    def draw(self):
        self.screen.fill(BG)

        canvas_rect = pygame.Rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H)
        pygame.draw.rect(self.screen, CANVAS_BG, canvas_rect)

        if self.map and self.player:
            ox, oy = self._iso_origin()
            prev_clip = self.screen.get_clip()
            self.screen.set_clip(canvas_rect)
            self._render_iso(self.screen, ox, oy)
            self._draw_path_markers(self.screen, ox, oy)
            self.screen.set_clip(prev_clip)
        else:
            msg = self.load_error or "Nenhum mapa carregado."
            r = FONT_L.render(msg, True, DANGER if self.load_error else TEXT)
            self.screen.blit(r, (WIDTH // 2 - r.get_width() // 2,
                                 HEIGHT // 2))

        self._draw_help()
        self._draw_hud()
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()


def main():
    json_path = sys.argv[1] if len(sys.argv) > 1 else None
    app = MapTesterApp(json_path)
    app.run()


if __name__ == "__main__":
    main()