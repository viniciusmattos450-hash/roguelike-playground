# -*- coding: utf-8 -*-
"""
MapEditor.py v10 — Paredes com espessura ajustável.

Novidades:
- Tile tem `thickness` (0.10..1.00) e `thin_axis` ("none" | "x" | "y")
- Em iso, paredes finas são desenhadas com o footprint encolhido no eixo escolhido
- Paredes adjacentes com mesma `thin_axis`+`thickness` se conectam lado a lado
- Cores sólidas ou texturas (mascaradas) — cai pra cor se não houver sprite

Rodar:  MapEditor v10
"""

import os, json, math, subprocess, sys
import pygame

# ============================================================================
# Config
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
MAX_LAYERS     = 10
DEFAULT_LAYERS = 4

INACTIVE_LAYER_ALPHA = 90

pygame.init()
pygame.font.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Map Editor v10")
clock = pygame.time.Clock()

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports", "maps")
TILES_DIR   = os.path.join(BASE_DIR, "exports", "tiles")
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(TILES_DIR, exist_ok=True)
AUTOSAVE_PATH = os.path.join(EXPORTS_DIR, "_autosave.json")

BASE_TEXTURE       = os.path.join(TILES_DIR, "base_texture.png")
SIDE_LEFT_TEXTURE  = os.path.join(TILES_DIR, "side_left_texture.png")
SIDE_RIGHT_TEXTURE = os.path.join(TILES_DIR, "side_right_texture.png")

TILE_SLOTS = ("top", "side_left", "side_right")

THIN_AXES = [
    ("none", "Cheio (sem encolher)"),
    ("x",    "Fino em X (corre em Y)"),
    ("y",    "Fino em Y (corre em X)"),
]

# ============================================================================
# Texturas base
# ============================================================================
def _make_checker(size=64, c1=200, c2=160, border=90, path=None):
    if path and os.path.isfile(path): return
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        for x in range(size):
            c = c1 if ((x // 8 + y // 8) % 2 == 0) else c2
            surf.set_at((x, y), (c, c, c, 255))
    pygame.draw.rect(surf, (border, border, border, 255), (0, 0, size, size), 1)
    if path:
        try: pygame.image.save(surf, path)
        except Exception: pass

def ensure_base_textures():
    _make_checker(64, 200, 160, 90,  BASE_TEXTURE)
    _make_checker(64, 110, 80,  60,  SIDE_LEFT_TEXTURE)
    _make_checker(64, 150, 120, 70,  SIDE_RIGHT_TEXTURE)

def ensure_default_tile_folders():
    for tid, slots in [
        ("ground", ("top",)),
        ("wall",   ("top", "side_left", "side_right")),
        ("tree",   ("top", "side_left", "side_right")),
        ("water",  ("top",)),
    ]:
        folder = os.path.join(TILES_DIR, tid)
        os.makedirs(folder, exist_ok=True)
        for slot in slots:
            p = os.path.join(folder, f"{slot}.png")
            if os.path.isfile(p): continue
            src_file = {"top": BASE_TEXTURE,
                        "side_left": SIDE_LEFT_TEXTURE,
                        "side_right": SIDE_RIGHT_TEXTURE}[slot]
            try:
                img = pygame.image.load(src_file)
                pygame.image.save(img, p)
            except Exception: pass

ensure_base_textures()
ensure_default_tile_folders()

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
POPUP_BG      = (28, 24, 20)

PASS_OK       = (110, 220, 110, 130)
PASS_BLOCK    = (220, 80, 80, 130)
PASS_ABOVE    = (120, 180, 240, 130)
PASS_TILE_OK  = (110, 220, 110, 35)
PASS_TILE_BLK = (220, 80, 80, 35)

EVENT_KINDS = [
    ("player_spawn", "Player Spawn"),
    ("trigger",      "Trigger"),
    ("teleport",     "Teleport"),
    ("other",        "Other"),
]
EVENT_KIND_COLORS = {
    "player_spawn": (100, 220, 255),
    "trigger":      (230, 100, 100),
    "teleport":     (200, 130, 240),
    "other":        (200, 200, 200),
}
EVENT_KIND_GLYPHS = {
    "player_spawn": "P", "trigger": "T", "teleport": "!", "other": "?",
}
TRIGGER_WHENS = [
    ("on_start",            "onStart"),
    ("on_collision_enter",  "onCollisionEnter"),
    ("on_collision_exit",   "onCollisionExit"),
    ("on_interact",         "onInteract"),
    ("on_timer",            "onTimer"),
]

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

def darken(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color[:3])

def open_folder(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass

# ============================================================================
# TextField
# ============================================================================
class TextField:
    def __init__(self, key, label, value="", max_len=80):
        self.key = key; self.label = label; self.value = value
        self.max_len = max_len
        self.label_rect = pygame.Rect(0,0,0,0)
        self.rect = pygame.Rect(0,0,0,0)
        self.focused = False
        self.active_this_frame = False
    def set_position(self, x, y, w):
        self.label_rect = pygame.Rect(x, y, w, 12)
        self.rect = pygame.Rect(x, y + 14, w, 24)
        self.active_this_frame = True
    def mark_inactive(self):
        self.label_rect = pygame.Rect(0,0,0,0)
        self.rect = pygame.Rect(0,0,0,0)
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
        clip = surf.get_clip()
        surf.set_clip(self.rect.inflate(-8, -4))
        surf.blit(ts, (self.rect.x + 6, self.rect.y + 6))
        if self.focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            cx = self.rect.x + 6 + ts.get_width()
            pygame.draw.line(surf, TEXT, (cx, self.rect.y + 5),
                             (cx, self.rect.bottom - 5), 1)
        surf.set_clip(clip)

# ============================================================================
# Dropdown
# ============================================================================
class Dropdown:
    def __init__(self, key, label, options, value,
                 on_change=None, max_visible=12):
        self.key = key; self.label = label
        self.options = options
        self.value = value
        self.on_change = on_change
        self.max_visible = max_visible
        self.expanded = False
        self.label_rect = pygame.Rect(0,0,0,0)
        self.rect = pygame.Rect(0,0,0,0)
        self.active_this_frame = False
    def set_position(self, x, y, w, h=24):
        self.label_rect = pygame.Rect(x, y, w, 12)
        self.rect = pygame.Rect(x, y + 14, w, h)
        self.active_this_frame = True
    def mark_inactive(self):
        self.label_rect = pygame.Rect(0,0,0,0)
        self.rect = pygame.Rect(0,0,0,0)
        self.active_this_frame = False
    def set_options(self, options):
        self.options = options
    def display_label(self):
        for v, lbl in self.options:
            if v == self.value: return lbl
        return str(self.value) if self.value is not None else "—"
    def list_rect(self):
        n = min(len(self.options), self.max_visible)
        h = n * 24 + 4
        ly = self.rect.bottom
        if ly + h > HEIGHT - BOTTOM_H:
            ly = max(TOP_H + 4, self.rect.top - h)
        return pygame.Rect(self.rect.x, ly, self.rect.w, h)
    def handle_click(self, pos):
        if self.expanded:
            lr = self.list_rect()
            if lr.collidepoint(pos):
                idx = (pos[1] - lr.y - 2) // 24
                idx = clamp(idx, 0, len(self.options) - 1)
                new_val = self.options[idx][0]
                if new_val != self.value:
                    self.value = new_val
                    if self.on_change: self.on_change(new_val)
                self.expanded = False
                return True
            self.expanded = False
            return False
        if self.rect.collidepoint(pos):
            self.expanded = True
            return True
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
        surf.blit(ts, (self.rect.x + 6, self.rect.y + 6))
        surf.set_clip(clip)
        ax = self.rect.right - 12
        ay = self.rect.centery
        pygame.draw.polygon(surf, TEXT,
                            [(ax-4, ay-2), (ax+4, ay-2), (ax, ay+3)])
    def draw_overlay(self, surf):
        if not self.expanded: return
        lr = self.list_rect()
        pygame.draw.rect(surf, POPUP_BG, lr)
        pygame.draw.rect(surf, ACCENT_BRIGHT, lr, 1)
        mouse = pygame.mouse.get_pos()
        for i, (v, lbl) in enumerate(self.options[:self.max_visible]):
            r = pygame.Rect(lr.x + 2, lr.y + 2 + i*24, lr.w - 4, 24)
            if r.collidepoint(mouse):
                pygame.draw.rect(surf, BTN_HOVER, r)
            if v == self.value:
                pygame.draw.rect(surf, BTN_ACTIVE, r)
            t = FONT_S.render(lbl, True, TEXT)
            surf.blit(t, (r.x + 6, r.y + 6))

# ============================================================================
# Dialogs
# ============================================================================
class InputDialog:
    def __init__(self):
        self.active = False; self.text = ""
        self.title = ""; self.prompt = ""
        self.rect = pygame.Rect(0,0,480,180)
        self.rect.center = (WIDTH//2, HEIGHT//2)
        self.input_rect = pygame.Rect(0,0,0,0)
        self.btn_ok = None; self.btn_cancel = None
        self.on_ok = None
    def open(self, title, prompt, default="", on_ok=None):
        self.active = True
        self.title = title; self.prompt = prompt
        self.text = default; self.on_ok = on_ok
        r = self.rect
        self.input_rect = pygame.Rect(r.x+20, r.y+70, r.w-40, 34)
        bw = 130; by = r.bottom-50
        self.btn_cancel = pygame.Rect(r.x+20, by, bw, 32)
        self.btn_ok = pygame.Rect(r.right-20-bw, by, bw, 32)
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
        overlay.fill((0,0,0,170)); surf.blit(overlay, (0,0))
        r = self.rect
        pygame.draw.rect(surf, PANEL_BG, r, border_radius=8)
        pygame.draw.rect(surf, ACCENT_BRIGHT, r, 2, border_radius=8)
        draw_text(surf, self.title, r.x+20, r.y+16, FONT_L, ACCENT_BRIGHT)
        draw_text(surf, self.prompt, r.x+20, r.y+48, FONT_S, TEXT_DIM)
        pygame.draw.rect(surf, (22,19,16), self.input_rect, border_radius=4)
        pygame.draw.rect(surf, ACCENT_DARK, self.input_rect, 1, border_radius=4)
        caret = "_" if (pygame.time.get_ticks()//500)%2==0 else " "
        shown = self.text + caret
        col = TEXT if self.text else (90,80,65)
        txt = FONT_M.render(shown if self.text else "digite aqui", True, col)
        surf.blit(txt, (self.input_rect.x+8, self.input_rect.y+9))
        draw_button(surf, self.btn_cancel, "Cancelar  (ESC)", FONT_M)
        draw_button(surf, self.btn_ok, "OK  (Enter)", FONT_M, primary=True)

class SaveDialog:
    def __init__(self):
        self.active = False; self.text = ""
        self.rect = pygame.Rect(0,0,460,190)
        self.rect.center = (WIDTH//2, HEIGHT//2)
        self.input_rect = pygame.Rect(0,0,0,0)
        self.btn_save = None; self.btn_cancel = None
        self._layout()
    def _layout(self):
        r = self.rect
        self.input_rect = pygame.Rect(r.x+20, r.y+70, r.w-40, 34)
        bw = 130; by = r.bottom-50
        self.btn_cancel = pygame.Rect(r.x+20, by, bw, 32)
        self.btn_save = pygame.Rect(r.right-20-bw, by, bw, 32)
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
        overlay.fill((0,0,0,170)); surf.blit(overlay, (0,0))
        r = self.rect
        pygame.draw.rect(surf, PANEL_BG, r, border_radius=8)
        pygame.draw.rect(surf, ACCENT_BRIGHT, r, 2, border_radius=8)
        draw_text(surf, "SALVAR PROJETO COMO", r.x+20, r.y+16, FONT_L, ACCENT_BRIGHT)
        draw_text(surf, "Digite o nome do arquivo:", r.x+20, r.y+48, FONT_S, TEXT_DIM)
        pygame.draw.rect(surf, (22,19,16), self.input_rect, border_radius=4)
        pygame.draw.rect(surf, ACCENT_DARK, self.input_rect, 1, border_radius=4)
        caret = "_" if (pygame.time.get_ticks()//500)%2==0 else " "
        shown = self.text + caret
        col = TEXT if self.text else (90,80,65)
        txt = FONT_M.render(shown if self.text else "meu_projeto", True, col)
        surf.blit(txt, (self.input_rect.x+8, self.input_rect.y+9))
        draw_button(surf, self.btn_cancel, "Cancelar  (ESC)", FONT_M)
        draw_button(surf, self.btn_save, "Salvar  (Enter)", FONT_M, primary=True)

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
        if y + h > HEIGHT - BOTTOM_H:
            y = max(TOP_H + 4, HEIGHT - BOTTOM_H - h - 4)
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
# Tile — pasta com slots + espessura de parede
# ============================================================================
class Tile:
    def __init__(self, tid, name, color=(128,128,128),
                 walkable=True, category="Geral", height=0,
                 blocks_sight=False, folder=None,
                 thickness=1.0, thin_axis="none"):
        self.id = tid; self.name = name
        self.color = tuple(color); self.walkable = walkable
        self.category = category
        self.height = int(height)
        self.blocks_sight = bool(blocks_sight)
        self.thickness = float(thickness)
        self.thin_axis = thin_axis
        self.folder = folder or os.path.join(TILES_DIR, tid)
        try: os.makedirs(self.folder, exist_ok=True)
        except Exception: pass
        self._cache = {}
        self._mtimes = {}

    def slot_path(self, slot):
        return os.path.join(self.folder, f"{slot}.png")
    def has_slot(self, slot):
        return os.path.isfile(self.slot_path(slot))

    def get_sprite(self, slot, size, alpha=255):
        p = self.slot_path(slot)
        if not os.path.isfile(p): return None
        try: mtime = os.path.getmtime(p)
        except Exception: return None
        if self._mtimes.get(slot) != mtime:
            for k in list(self._cache.keys()):
                if k[0] == slot: del self._cache[k]
            self._mtimes[slot] = mtime
        if isinstance(size, int): size = (size, size)
        if size[0] <= 0 or size[1] <= 0: return None
        key = (slot, size, alpha)
        if key in self._cache: return self._cache[key]
        try:
            img = pygame.image.load(p).convert_alpha()
            scaled = pygame.transform.smoothscale(img, size)
            if alpha < 255:
                scaled = scaled.copy()
                scaled.fill((255, 255, 255, alpha),
                            special_flags=pygame.BLEND_RGBA_MULT)
            self._cache[key] = scaled
            return scaled
        except Exception:
            self._cache[key] = None
            return None

    def get_any_sprite(self, size):
        for slot in ("top", "side_left", "side_right"):
            s = self.get_sprite(slot, size)
            if s: return s
        return None

    def clear_cache(self):
        self._cache = {}
        self._mtimes = {}

    def set_slot_from_file(self, slot, src_path):
        try:
            os.makedirs(self.folder, exist_ok=True)
            img = pygame.image.load(src_path).convert_alpha()
            pygame.image.save(img, self.slot_path(slot))
            self.clear_cache()
            return True
        except Exception:
            return False

    def remove_slot(self, slot):
        p = self.slot_path(slot)
        if os.path.isfile(p):
            try: os.remove(p)
            except Exception: pass
        self.clear_cache()

    def to_dict(self):
        return {"id": self.id, "name": self.name,
                "color": list(self.color), "walkable": self.walkable,
                "category": self.category,
                "height": self.height, "blocks_sight": self.blocks_sight,
                "thickness": round(self.thickness, 3),
                "thin_axis": self.thin_axis}

    @classmethod
    def from_dict(cls, d):
        t = cls(d["id"], d["name"], tuple(d.get("color", (128,128,128))),
                d.get("walkable", True), d.get("category", "Geral"),
                height=d.get("height", 0),
                blocks_sight=d.get("blocks_sight", False),
                thickness=d.get("thickness", 1.0),
                thin_axis=d.get("thin_axis", "none"))
        legacy = d.get("image_path")
        if legacy and os.path.isfile(legacy):
            top_p = t.slot_path("top")
            if not os.path.isfile(top_p):
                try:
                    img = pygame.image.load(legacy).convert_alpha()
                    pygame.image.save(img, top_p)
                    t.clear_cache()
                except Exception:
                    pass
        return t

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
    # id, nome, walk, cat, height, blocks_sight, thickness, thin_axis
    data = [
        ("ground", "Ground", True,  "Terreno",   0, False, 1.00, "none"),
        ("wall",   "Wall",   False, "Estruturas",1, True,  1.00, "none"),
        ("tree",   "Tree",   False, "Natureza",  2, True,  1.00, "none"),
        ("water",  "Water",  False, "Terreno",   0, False, 1.00, "none"),
    ]
    for tid, name, walk, cat, h, bs, th, ax in data:
        t = Tile(tid, name, color=(150, 150, 150), walkable=walk,
                 category=cat, height=h, blocks_sight=bs,
                 folder=os.path.join(TILES_DIR, tid),
                 thickness=th, thin_axis=ax)
        ts.add(t)
    return ts

# ============================================================================
# GameEvent
# ============================================================================
class GameEvent:
    def __init__(self, kind="other", x=0, y=0, eid=0):
        self.kind = kind
        self.x = x; self.y = y
        self.id = eid
        self.name = ""
        self.tag = ""
        self.sprite = None
        self.data = {}
    def color(self):
        return EVENT_KIND_COLORS.get(self.kind, (200,200,200))
    def glyph(self):
        return EVENT_KIND_GLYPHS.get(self.kind, "?")
    def to_dict(self):
        return {"kind": self.kind, "x": self.x, "y": self.y, "id": self.id,
                "name": self.name, "tag": self.tag,
                "sprite": self.sprite, "data": dict(self.data)}
    @classmethod
    def from_dict(cls, d):
        ev = cls(d.get("kind", "other"), d["x"], d["y"], d.get("id", 0))
        ev.name = d.get("name", "")
        ev.tag = d.get("tag", "")
        ev.sprite = d.get("sprite")
        ev.data = dict(d.get("data", {}))
        return ev

# ============================================================================
# TileMap
# ============================================================================
class TileMap:
    def __init__(self, name="novo_mapa", w=30, h=20, num_layers=DEFAULT_LAYERS):
        self.name = name; self.w = w; self.h = h
        self.num_layers = clamp(num_layers, 1, MAX_LAYERS)
        self.data = [[[None] * self.num_layers for _ in range(w)]
                     for _ in range(h)]
        self.passability = {}
        self.events = []
        self.parent = None

    def in_bounds(self, x, y): return 0 <= x < self.w and 0 <= y < self.h
    def get_layer(self, x, y, layer):
        if self.in_bounds(x, y) and 0 <= layer < self.num_layers:
            return self.data[y][x][layer]
        return None
    def set_layer(self, x, y, layer, tid):
        if self.in_bounds(x, y) and 0 <= layer < self.num_layers:
            self.data[y][x][layer] = tid
    def get_top(self, x, y):
        if not self.in_bounds(x, y): return None
        for l in reversed(range(self.num_layers)):
            if self.data[y][x][l] is not None: return self.data[y][x][l]
        return None
    def is_empty(self, x, y):
        if not self.in_bounds(x, y): return True
        for l in range(self.num_layers):
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
    def is_above(self, x, y): return self.passability.get((x, y)) == "above"
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

    def set_num_layers(self, n):
        n = clamp(n, 1, MAX_LAYERS)
        if n == self.num_layers: return
        for y in range(self.h):
            for x in range(self.w):
                row = self.data[y][x]
                if n > len(row):
                    row.extend([None] * (n - len(row)))
                else:
                    del row[n:]
        self.num_layers = n

    def resize(self, nw, nh):
        nl = self.num_layers
        nd = [[[None] * nl for _ in range(nw)] for _ in range(nh)]
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
            if v is True: v = "ok"
            elif v is False: v = "block"
            pass_out.append([x, y, v])
        return {"name": self.name, "w": self.w, "h": self.h,
                "num_layers": self.num_layers, "parent": self.parent,
                "data": self.data, "passability": pass_out,
                "events": [ev.to_dict() for ev in self.events]}

    @classmethod
    def from_dict(cls, d):
        nl = d.get("num_layers", None)
        m = cls(d["name"], d["w"], d["h"],
                num_layers=nl if nl else DEFAULT_LAYERS)
        m.parent = d.get("parent")
        raw = d["data"]
        for y in range(m.h):
            for x in range(m.w):
                v = raw[y][x]
                if isinstance(v, list):
                    row = list(v)[:m.num_layers]
                    row += [None] * (m.num_layers - len(row))
                    m.data[y][x] = row
                elif v is None:
                    m.data[y][x] = [None] * m.num_layers
                else:
                    m.data[y][x] = [v] + [None] * (m.num_layers - 1)
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
        self.maps = {}
        self.active_map_name = None
        m = TileMap("mapa_inicial", 30, 20)
        for y in range(20):
            for x in range(30):
                m.set_layer(x, y, 0, "ground")
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
    def to_dict(self):
        return {"tileset": self.tileset.to_dict(),
                "maps": {n: m.to_dict() for n, m in self.maps.items()},
                "active_map_name": self.active_map_name}
    @classmethod
    def from_dict(cls, d):
        p = cls.__new__(cls)
        p.tileset = TileSet.from_dict(d["tileset"])
        p.maps = {n: TileMap.from_dict(md) for n, md in d["maps"].items()}
        p.active_map_name = d.get("active_map_name")
        if not p.maps: p.add_map(TileMap("mapa_inicial"))
        if p.active_map_name not in p.maps:
            p.active_map_name = next(iter(p.maps))
        return p

# ============================================================================
# Tools
# ============================================================================
TOOL_BRUSH  = "brush"
TOOL_ERASER = "eraser"
TOOL_FILL   = "fill"
TOOL_PICKER = "picker"

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
        MODE_MAP:   ("map_", "quick_size"),
        MODE_TILES: ("tile_",),
        MODE_EVENTS:("ev_",),
        MODE_PASS:  (),
    }

    def __init__(self):
        self.running = True
        self.project = Project()
        self.mode = self.MODE_MAP
        self.tool = TOOL_BRUSH
        self.rect_mode = False
        self.active_layer = 0
        self.view_iso = False

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

        self.fields = {}
        self.dropdowns = {}
        self.focused_field = None
        self.expanded_dropdown = None
        self._init_widgets()

        self.msg = ""; self.msg_timer = 0.0; self.msg_color = ACCENT
        self.save_dialog = SaveDialog()
        self.rename_dialog = InputDialog()
        self.ctx_menu = ContextMenu()

        self.current_event_kind = "player_spawn"
        self.editing_event = None

        self.dragging_map_name = None
        self.pending_map_click = None

        self._right_hits = []
        self._left_hits  = []
        self._top_hits   = []

        self.show_grid = True
        self.debug_hud = True
        self.paint_flashes = []

        self._sync_fields_from_map()
        self._sync_fields_from_tile()
        self._recenter()

        if os.path.isfile(AUTOSAVE_PATH):
            self._load_autosave()

    # ------------------------------------------------------------------
    def _init_widgets(self):
        for k, lbl in [("map_name","Nome do mapa"),("map_w","Largura"),
                       ("map_h","Altura")]:
            self.fields[k] = TextField(k, lbl, "", max_len=32)
        self.fields["quick_size"] = TextField("quick_size", "Rápido (ex: 5x5)", "", max_len=16)
        for k, lbl in [("tile_name","Nome"),("tile_category","Categoria"),
                       ("tile_color","Cor (fallback)"),
                       ("tile_height","Altura 3D (int)"),
                       ("tile_thickness","Espessura (0.10 .. 1.00)")]:
            self.fields[k] = TextField(k, lbl, "", max_len=200)
        self.fields["ev_id"]   = TextField("ev_id",   "ID (int)", "", max_len=16)
        self.fields["ev_name"] = TextField("ev_name", "Nome",     "", max_len=64)
        self.fields["ev_tag"]  = TextField("ev_tag",  "Tag",      "", max_len=64)
        for i in range(1, 7):
            self.fields[f"ev_k{i}"] = TextField(f"ev_k{i}", f"chave{i}", "", max_len=40)
            self.fields[f"ev_v{i}"] = TextField(f"ev_v{i}", f"valor{i}", "", max_len=200)
        self.fields["ev_tx"] = TextField("ev_tx", "X", "", max_len=12)
        self.fields["ev_ty"] = TextField("ev_ty", "Y", "", max_len=12)
        self.fields["ev_tz"] = TextField("ev_tz", "Z", "", max_len=12)
        self.fields["ev_target_map"] = TextField("ev_target_map", "Mapa alvo", "", max_len=64)

        self.dropdowns["active_layer"] = Dropdown(
            "active_layer", "Camada ativa",
            [(i, f"Camada {i+1}") for i in range(MAX_LAYERS)],
            self.active_layer,
            on_change=self._set_layer)
        self.dropdowns["ev_kind"] = Dropdown(
            "ev_kind", "Tipo de evento", EVENT_KINDS, "player_spawn",
            on_change=self._on_event_kind_change)
        self.dropdowns["ev_when"] = Dropdown(
            "ev_when", "Quando ativar", TRIGGER_WHENS, "on_start",
            on_change=lambda v: None)
        self.dropdowns["tile_thin_axis"] = Dropdown(
            "tile_thin_axis", "Direção fina (paredes)", THIN_AXES, "none",
            on_change=lambda v: None)

    def _msg(self, text, color=ACCENT):
        self.msg = text; self.msg_color = color; self.msg_timer = 2.5

    def _canvas_rect(self): return pygame.Rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H)
    def _in_canvas(self, pos): return self._canvas_rect().collidepoint(pos)
    def _in_right_panel(self, pos): return pos[0] >= WIDTH - RIGHT_W
    def _in_left_panel(self, pos):
        return 0 <= pos[0] < LEFT_W and TOP_H <= pos[1] < HEIGHT - BOTTOM_H
    def _in_top_bar(self, pos): return pos[1] < TOP_H

    # --- iso helpers ---
    def _iso_tw(self): return self.cell * 2
    def _iso_th(self): return self.cell
    def _iso_wall_unit(self): return self.cell * 1.25

    def _toggle_view(self):
        self.view_iso = not self.view_iso
        self._recenter(); self._clamp_cam()
        self._msg("Vista: " + ("Isométrico" if self.view_iso else "Top-down"), ACCENT)

    def _recenter(self):
        m = self.project.active_map()
        if not m: return
        if self.view_iso:
            tw = self._iso_tw(); th = self._iso_th()
            min_x = -m.h * tw / 2
            max_x = m.w * tw / 2
            min_y = -th * 2
            max_y = (m.w + m.h) * th / 2 + th
            self.cam[0] = (min_x + max_x) / 2
            self.cam[1] = (min_y + max_y) / 2
        else:
            self.cam[0] = m.w * self.cell / 2 - CANVAS_W / 2
            self.cam[1] = m.h * self.cell / 2 - CANVAS_H / 2

    def _clamp_cam(self):
        m = self.project.active_map()
        if not m: return
        if self.view_iso:
            tw = self._iso_tw(); th = self._iso_th()
            min_x = -m.h * tw / 2 - CANVAS_W * 0.5
            max_x = m.w * tw / 2 + CANVAS_W * 0.5
            min_y = -th * 5 - CANVAS_H * 0.5
            max_y = (m.w + m.h) * th / 2 + th * 2 + CANVAS_H * 0.5
            self.cam[0] = clamp(self.cam[0], min_x, max_x)
            self.cam[1] = clamp(self.cam[1], min_y, max_y)
        else:
            ww = m.w * self.cell; wh = m.h * self.cell
            self.cam[0] = clamp(self.cam[0], -CANVAS_W*0.5, ww - CANVAS_W*0.5)
            self.cam[1] = clamp(self.cam[1], -CANVAS_H*0.5, wh - CANVAS_H*0.5)

    def _screen_to_world(self, sx, sy):
        if self.view_iso:
            cx = CANVAS_X + CANVAS_W / 2
            cy = CANVAS_Y + CANVAS_H / 2
            return (sx - cx + self.cam[0], sy - cy + self.cam[1])
        else:
            return (sx - CANVAS_X + self.cam[0], sy - CANVAS_Y + self.cam[1])

    def _world_to_screen(self, wx, wy):
        if self.view_iso:
            cx = CANVAS_X + CANVAS_W / 2
            cy = CANVAS_Y + CANVAS_H / 2
            return (cx + (wx - self.cam[0]), cy + (wy - self.cam[1]))
        else:
            return (CANVAS_X + (wx - self.cam[0]),
                    CANVAS_Y + (wy - self.cam[1]))

    def _cell_from_pos(self, pos):
        m = self.project.active_map()
        if not m: return None
        wx, wy = self._screen_to_world(pos[0], pos[1])
        if self.view_iso:
            tw = self._iso_tw(); th = self._iso_th()
            gx_f = wx / tw + wy / th
            gy_f = wy / th - wx / tw
            gx = int(math.floor(gx_f))
            gy = int(math.floor(gy_f))
            if 0 <= gx < m.w and 0 <= gy < m.h:
                return (gx, gy)
            return None
        else:
            gx = int(wx // self.cell); gy = int(wy // self.cell)
            if m.in_bounds(gx, gy): return (gx, gy)
            return None

    # --- undo/redo ---
    def _snapshot(self):
        m = self.project.active_map()
        if not m: return None
        return {"map": m.name,
                "data": [[list(c) for c in row] for row in m.data],
                "num_layers": m.num_layers,
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
        m.num_layers = snap.get("num_layers", len(snap["data"][0][0]))
        m.passability = dict(snap["pass"])
        m.events = [GameEvent.from_dict(ev) for ev in snap["events"]]
        m.w = snap["w"]; m.h = snap["h"]
        self.active_layer = min(self.active_layer, m.num_layers - 1)
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
            self._sync_fields_from_map(); self._sync_fields_from_tile()
            self._recenter()
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
        opts = []
        for i in range(MAX_LAYERS):
            lbl = f"Camada {i+1}"
            if i >= m.num_layers:
                lbl += "  (vazia)"
            opts.append((i, lbl))
        self.dropdowns["active_layer"].set_options(opts)
        self.dropdowns["active_layer"].value = min(self.active_layer, MAX_LAYERS - 1)

    def _sync_fields_from_tile(self):
        tid = self.selected_tile_id
        if not tid: return
        t = self.project.tileset.get(tid)
        if not t: return
        self.fields["tile_name"].value = t.name
        self.fields["tile_category"].value = t.category
        self.fields["tile_color"].value = color_to_hex(t.color)
        self.fields["tile_height"].value = str(t.height)
        self.fields["tile_thickness"].value = f"{t.thickness:.2f}"
        self.dropdowns["tile_thin_axis"].value = t.thin_axis

    def _sync_fields_from_event(self, ev):
        self.editing_event = ev
        if not ev: return
        self.fields["ev_id"].value = str(ev.id)
        self.fields["ev_name"].value = ev.name
        self.fields["ev_tag"].value = ev.tag
        for i in range(1, 7):
            self.fields[f"ev_k{i}"].value = ""
            self.fields[f"ev_v{i}"].value = ""
        items = list(ev.data.items())
        for i, (k, v) in enumerate(items):
            if i >= 6: break
            self.fields[f"ev_k{i+1}"].value = str(k)
            self.fields[f"ev_v{i+1}"].value = str(v)
        self.dropdowns["ev_kind"].value = ev.kind
        self.fields["ev_tx"].value = str(ev.data.get("x", ""))
        self.fields["ev_ty"].value = str(ev.data.get("y", ""))
        self.fields["ev_tz"].value = str(ev.data.get("z", ""))
        self.fields["ev_target_map"].value = str(ev.data.get("target_map", ""))
        self.dropdowns["ev_when"].value = ev.data.get("when", "on_start")

    # --- aplicar ---
    def _apply_tile_fields(self):
        tid = self.selected_tile_id
        if not tid: return
        t = self.project.tileset.get(tid)
        if not t: return
        t.name = self.fields["tile_name"].value.strip() or t.id
        t.category = self.fields["tile_category"].value.strip() or "Geral"
        t.color = parse_hex_color(self.fields["tile_color"].value, t.color)
        try:
            t.height = int(self.fields["tile_height"].value or 0)
        except Exception:
            pass
        # espessura
        try:
            v = float(self.fields["tile_thickness"].value.replace(",", "."))
            t.thickness = max(0.10, min(1.00, v))
        except Exception:
            pass
        t.thin_axis = self.dropdowns["tile_thin_axis"].value
        # atualiza field com valor clamped
        self.fields["tile_thickness"].value = f"{t.thickness:.2f}"
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
        self._mark_dirty(); self._sync_fields_from_map(); self._recenter()

    def _apply_event_fields(self):
        ev = self.editing_event
        if not ev: return
        try: ev.id = int(self.fields["ev_id"].value or 0)
        except Exception: pass
        ev.name = self.fields["ev_name"].value.strip()
        ev.tag  = self.fields["ev_tag"].value.strip()
        ev.kind = self.dropdowns["ev_kind"].value
        new_data = {}
        if ev.kind == "teleport":
            for k, f in [("x","ev_tx"),("y","ev_ty"),("z","ev_tz")]:
                v = self.fields[f].value.strip()
                if v:
                    try: v = int(v)
                    except Exception:
                        try: v = float(v)
                        except Exception: pass
                    new_data[k] = v
            tm = self.fields["ev_target_map"].value.strip()
            if tm: new_data["target_map"] = tm
        elif ev.kind == "trigger":
            new_data["when"] = self.dropdowns["ev_when"].value
        for i in range(1, 7):
            k = self.fields[f"ev_k{i}"].value.strip()
            v = self.fields[f"ev_v{i}"].value.strip()
            if k and k not in new_data:
                try:
                    if "." in v: v = float(v)
                    else: v = int(v)
                except Exception: pass
                new_data[k] = v
        ev.data = new_data
        self._mark_dirty(); self._msg("Evento atualizado.", SUCCESS)

    def _apply_quick_size(self):
        m = self.project.active_map()
        if not m: return
        s = self.fields["quick_size"].value.strip().lower()
        if "x" not in s:
            self._msg("Formato inválido.", DANGER); return
        try:
            a, b = s.split("x")
            nw = clamp(int(a), 4, 300); nh = clamp(int(b), 4, 300)
        except Exception:
            self._msg("Formato inválido.", DANGER); return
        if (nw, nh) != (m.w, m.h):
            self._push_undo(); m.resize(nw, nh)
            self._mark_dirty(); self._sync_fields_from_map(); self._recenter()
            self._msg(f"Redimensionado: {nw}x{nh}", SUCCESS)

    def _apply_current_field_group(self):
        f = self.focused_field
        if not f: return
        if f.key == "quick_size": self._apply_quick_size()
        elif f.key.startswith("tile_"): self._apply_tile_fields()
        elif f.key.startswith("ev_"): self._apply_event_fields()
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
            self._sync_fields_from_map(); self._sync_fields_from_tile()
            self._recenter()
            self._msg(f"Carregado: {files[-1]}", SUCCESS)
        except Exception as ex: self._msg(f"Erro: {ex}", DANGER)

    # --- mapas ---
    def _switch_map(self, name):
        if name not in self.project.maps: return
        self.project.active_map_name = name
        self.active_layer = min(self.active_layer,
                                self.project.active_map().num_layers - 1)
        self._sync_fields_from_map(); self._recenter()
        self._msg(f"Mapa: {name}", ACCENT)
    def _new_map(self, parent=None):
        name = self.project.unique_map_name("mapa")
        m = TileMap(name, 30, 20); m.parent = parent
        self.project.add_map(m)
        self.active_layer = 0
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
        self.active_layer = 0
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

    # --- layers ---
    def _set_layer(self, i):
        m = self.project.active_map()
        if not m: return
        i = clamp(i, 0, MAX_LAYERS - 1)
        if i >= m.num_layers:
            self._push_undo()
            m.set_num_layers(i + 1)
            self._mark_dirty()
        self.active_layer = i
        self._sync_fields_from_map()
    def _add_layer(self):
        m = self.project.active_map()
        if not m: return
        if m.num_layers >= MAX_LAYERS:
            self._msg("Máximo de camadas atingido.", WARN); return
        self._push_undo()
        m.set_num_layers(m.num_layers + 1)
        self._mark_dirty(); self._sync_fields_from_map()
        self._msg(f"Camadas: {m.num_layers}", ACCENT)
    def _del_layer(self):
        m = self.project.active_map()
        if not m: return
        if m.num_layers <= 1:
            self._msg("Mínimo 1 camada.", WARN); return
        self._push_undo()
        m.set_num_layers(m.num_layers - 1)
        self.active_layer = min(self.active_layer, m.num_layers - 1)
        self._mark_dirty(); self._sync_fields_from_map()
        self._msg(f"Camadas: {m.num_layers}", ACCENT)

    # --- tiles ---
    def _new_tile(self):
        tid = self.project.tileset.unique_id("tile")
        folder = os.path.join(TILES_DIR, tid)
        t = Tile(tid, "Novo tile", (150,150,150), True, "Geral",
                 height=0, folder=folder)
        try:
            img = pygame.image.load(BASE_TEXTURE)
            pygame.image.save(img, t.slot_path("top"))
            t.clear_cache()
        except Exception: pass
        self.project.tileset.add(t)
        self.selected_tile_id = tid
        self._sync_fields_from_tile(); self._mark_dirty()
        self._msg(f"Tile criado: {tid}", ACCENT)
    def _dup_tile(self):
        tid = self.selected_tile_id
        if not tid: return
        t = self.project.tileset.get(tid)
        if not t: return
        new_id = self.project.tileset.unique_id(t.id)
        nt = Tile(new_id, t.name+" copy", t.color, t.walkable, t.category,
                  t.height, t.blocks_sight, thickness=t.thickness,
                  thin_axis=t.thin_axis)
        for slot in TILE_SLOTS:
            src = t.slot_path(slot)
            if os.path.isfile(src):
                try:
                    img = pygame.image.load(src)
                    pygame.image.save(img, nt.slot_path(slot))
                except Exception: pass
        nt.clear_cache()
        self.project.tileset.add(nt)
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
                    for l in range(m.num_layers):
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
    def _toggle_blocks_sight(self):
        t = self.project.tileset.get(self.selected_tile_id)
        if t:
            t.blocks_sight = not t.blocks_sight
            self._mark_dirty()
            self._msg(f"{t.id}: blocks_sight={t.blocks_sight}", ACCENT)

    def _pick_slot_image(self, slot):
        path = pick_image_file()
        if not path: return
        t = self.project.tileset.get(self.selected_tile_id)
        if not t: return
        if t.set_slot_from_file(slot, path):
            self._mark_dirty()
            self._msg(f"{slot}.png salvo", SUCCESS)
        else:
            self._msg(f"Erro ao salvar {slot}.png", DANGER)

    def _remove_slot_image(self, slot):
        t = self.project.tileset.get(self.selected_tile_id)
        if not t: return
        t.remove_slot(slot)
        self._mark_dirty()
        self._msg(f"{slot} removido", TEXT_DIM)

    def _open_tile_folder(self):
        t = self.project.tileset.get(self.selected_tile_id)
        if not t: return
        try: os.makedirs(t.folder, exist_ok=True)
        except Exception: pass
        open_folder(t.folder)
        self._msg(f"Abrindo: {os.path.basename(t.folder)}/", ACCENT)

    # --- eventos ---
    def _on_event_kind_change(self, new_kind):
        if self.editing_event:
            self.editing_event.kind = new_kind
            self._sync_fields_from_event(self.editing_event)
            self._mark_dirty()
    def _dup_event(self, ev):
        m = self.project.active_map()
        if not m: return
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                nx, ny = ev.x + dx, ev.y + dy
                if 0 <= nx < m.w and 0 <= ny < m.h and not m.event_at(nx, ny):
                    new_ev = GameEvent(ev.kind, nx, ny, eid=m.next_event_id())
                    new_ev.name = ev.name
                    new_ev.tag = ev.tag
                    new_ev.sprite = ev.sprite
                    new_ev.data = dict(ev.data)
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
        self._mark_dirty(); self._msg("Evento deletado.", TEXT_DIM)
    def _select_target_map(self, pos):
        items = []
        for name in list(self.project.maps.keys())[:15]:
            items.append((name, (lambda n=name: self._set_target_map(n))))
        if not items:
            self._msg("Sem mapas no projeto.", DANGER); return
        self.ctx_menu.open(pos, items)
    def _set_target_map(self, name):
        self.fields["ev_target_map"].value = name
        if self.editing_event:
            self.editing_event.data["target_map"] = name
        self._mark_dirty()
        self._msg(f"Mapa alvo: {name}", ACCENT)

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

            if self.expanded_dropdown:
                if e.type == pygame.MOUSEBUTTONDOWN:
                    dd = self.dropdowns.get(self.expanded_dropdown)
                    if dd is not None:
                        if dd.handle_click(e.pos):
                            if not dd.expanded:
                                self.expanded_dropdown = None
                            continue
                        self.expanded_dropdown = None
                    else:
                        self.expanded_dropdown = None

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
                    if self.editing_event:
                        self.editing_event = None
                    elif self.rect_start:
                        self.rect_start = None; self.rect_end = None
                    else:
                        self.running = False
                    return
                if e.key == pygame.K_TAB:
                    idx = self.MODE_ORDER.index(self.mode)
                    self.mode = self.MODE_ORDER[(idx+1) % len(self.MODE_ORDER)]
                    if self.mode == self.MODE_TILES: self._sync_fields_from_tile()
                if e.key == pygame.K_g: self.show_grid = not self.show_grid
                if e.key == pygame.K_F1: self.debug_hud = not self.debug_hud
                if e.key == pygame.K_i: self._toggle_view()
                if e.key == pygame.K_z and (e.mod & pygame.KMOD_CTRL): self._do_undo()
                if e.key == pygame.K_y and (e.mod & pygame.KMOD_CTRL): self._do_redo()
                if self.mode == self.MODE_MAP:
                    if e.key == pygame.K_b: self.tool = TOOL_BRUSH
                    if e.key == pygame.K_e: self.tool = TOOL_ERASER
                    if e.key == pygame.K_f: self.tool = TOOL_FILL
                    if e.key == pygame.K_p: self.tool = TOOL_PICKER
                    if e.key == pygame.K_r:
                        self.rect_mode = not self.rect_mode
                        self._msg("Modo retângulo: " +
                                  ("ON" if self.rect_mode else "OFF"), ACCENT)
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
        mx, my = mouse_pos
        if self.view_iso:
            wx, wy = self._screen_to_world(mx, my)
            tw_old = old * 2; th_old = old
            gx_f = wx / tw_old + wy / th_old
            gy_f = wy / th_old - wx / tw_old
            self.cell = new
            tw = new * 2; th = new
            new_wx = (gx_f - gy_f) * tw / 2
            new_wy = (gx_f + gy_f) * th / 2
            cx = CANVAS_X + CANVAS_W / 2
            cy = CANVAS_Y + CANVAS_H / 2
            self.cam[0] = new_wx - (mx - cx)
            self.cam[1] = new_wy - (my - cy)
        else:
            wx_cell = (mx - CANVAS_X + self.cam[0]) / old
            wy_cell = (my - CANVAS_Y + self.cam[1]) / old
            self.cell = new
            self.cam[0] = wx_cell * new - (mx - CANVAS_X)
            self.cam[1] = wy_cell * new - (my - CANVAS_Y)
        self._clamp_cam()

    def _on_motion(self, pos):
        if self._in_canvas(pos):
            cell = self._cell_from_pos(pos)
            self.hover_cell = cell
            if self.mode == self.MODE_MAP:
                if self.rect_mode and self.rect_start and cell:
                    self.rect_end = cell
                elif self.dragging_paint and cell and not self.rect_mode:
                    self._paint_cell(cell)
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
            for key, dd in self.dropdowns.items():
                if not dd.active_this_frame: continue
                if dd.rect.collidepoint(pos):
                    dd.expanded = True
                    self.expanded_dropdown = key
                    return
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
        if self.pending_map_click:
            name, start = self.pending_map_click
            dx = pos[0] - start[0]; dy = pos[1] - start[1]
            dist = (dx*dx + dy*dy) ** 0.5
            if dist > 6:
                for rect, target in self._map_list_hits_for_drag():
                    if rect.collidepoint(pos) and target != name:
                        self._move_map_to(name, target); break
            else:
                self._switch_map(name)
            self.pending_map_click = None
        self.dragging_map_name = None

        if self.mode == self.MODE_MAP:
            if self.rect_mode and self.rect_start and self.rect_end:
                m = self.project.active_map()
                if m:
                    x1, y1 = self.rect_start; x2, y2 = self.rect_end
                    xa, xb = sorted((x1, x2)); ya, yb = sorted((y1, y2))
                    is_erase = (self.tool == TOOL_ERASER)
                    for yy in range(ya, yb + 1):
                        for xx in range(xa, xb + 1):
                            if is_erase:
                                m.set_layer(xx, yy, self.active_layer, None)
                            else:
                                m.set_layer(xx, yy, self.active_layer, self.selected_tile_id)
                            self._add_paint_flash(xx, yy)
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
        return False

    # ------------------------------------------------------------------
    # Canvas
    # ------------------------------------------------------------------
    def _handle_canvas_left(self, pos):
        if not self._in_canvas(pos): return
        cell = self._cell_from_pos(pos)
        if cell is None: return
        self.hover_cell = cell
        m = self.project.active_map()
        if not m: return

        if self.mode == self.MODE_MAP:
            if self.tool == TOOL_PICKER:
                tid = m.get_layer(*cell, self.active_layer) or m.get_top(*cell)
                if tid:
                    self.selected_tile_id = tid; self._sync_fields_from_tile()
                    self._msg(f"Selecionado: {tid}", ACCENT)
                return
            self._push_undo()
            if self.tool == TOOL_FILL:
                flood_fill_layer(m, cell[0], cell[1],
                                 self.active_layer, self.selected_tile_id)
                self._add_paint_flash(cell[0], cell[1])
                self._mark_dirty()
            elif self.rect_mode and self.tool in (TOOL_BRUSH, TOOL_ERASER):
                self.rect_start = cell; self.rect_end = cell
            else:
                self.dragging_paint = True
                self._paint_cell(cell)
        elif self.mode == self.MODE_PASS:
            self._push_undo()
            self.dragging_pass = self.pass_mode
            self._pass_cell(cell, self.pass_mode)
        elif self.mode == self.MODE_EVENTS:
            ev = m.event_at(*cell)
            if ev:
                self._sync_fields_from_event(ev)
                self._msg(f"Evento id {ev.id} ({ev.kind})", ACCENT)
                return
            self._push_undo()
            new_ev = GameEvent(self.current_event_kind, *cell,
                               eid=m.next_event_id())
            m.events.append(new_ev)
            self._sync_fields_from_event(new_ev)
            self._mark_dirty()
            self._msg(f"Colocado: {new_ev.kind} (id {new_ev.id})", ACCENT)

    def _handle_canvas_right(self, pos):
        if not self._in_canvas(pos): return
        cell = self._cell_from_pos(pos)
        if cell is None: return
        m = self.project.active_map()
        if not m: return
        if self.mode == self.MODE_MAP:
            self._push_undo()
            m.set_layer(*cell, self.active_layer, None)
            self._mark_dirty()
        elif self.mode == self.MODE_PASS:
            self._push_undo()
            self.dragging_pass = "block"
            self._pass_cell(cell, "block")
        elif self.mode == self.MODE_EVENTS:
            ev = m.event_at(*cell)
            if ev:
                items = [
                    ("Editar", lambda e=ev: self._sync_fields_from_event(e)),
                    ("Duplicar", lambda e=ev: self._dup_event(e)),
                    ("Deletar",  lambda e=ev: self._del_event(e)),
                ]
                self.ctx_menu.open(pos, items)

    def _add_paint_flash(self, x, y):
        self.paint_flashes.append([x, y, 0.35])

    def _paint_cell(self, cell):
        m = self.project.active_map()
        if not m: return
        if self.tool == TOOL_ERASER:
            m.set_layer(cell[0], cell[1], self.active_layer, None)
        elif self.tool == TOOL_BRUSH:
            m.set_layer(cell[0], cell[1], self.active_layer, self.selected_tile_id)
        self._add_paint_flash(cell[0], cell[1])
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
            self._sync_fields_from_map(); self._recenter()
            self._msg(f"{nw}x{nh}", ACCENT)
    def _clear_all_passability(self):
        m = self.project.active_map()
        if not m: return
        self._push_undo(); m.passability.clear(); self._mark_dirty()
        self._msg("Passability limpa.", TEXT_DIM)

    def update(self, dt):
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0: self.msg = ""
        if self.autosave_dirty:
            self.autosave_timer -= dt
            if self.autosave_timer <= 0:
                self._do_autosave(); self.autosave_dirty = False
        if self.paint_flashes:
            alive = []
            for f in self.paint_flashes:
                f[2] -= dt
                if f[2] > 0: alive.append(f)
            self.paint_flashes = alive

        if self.save_dialog.active or self.rename_dialog.active: return
        if self.focused_field or self.expanded_dropdown: return
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

    def draw(self):
        screen.fill(BG)
        self._right_hits = []
        self._left_hits = []
        self._top_hits = []
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
            if dd.active_this_frame and dd.expanded:
                dd.draw_overlay(screen)

        self._draw_debug_hud()
        self._draw_msg()
        pygame.display.flip()

    def _draw_debug_hud(self):
        if not getattr(self, "debug_hud", False): return
        m = self.project.active_map()
        rect_status = "ON" if self.rect_mode else "off"
        lines = [
            f"mode: {self.mode}",
            f"view: {'ISO' if self.view_iso else 'TOP'}",
            f"tool: {self.tool}  ·  rect: {rect_status}",
            f"layer: {self.active_layer + 1}/{m.num_layers if m else '?'}",
            f"tile: {self.selected_tile_id}",
            f"hover: {self.hover_cell}",
            f"cell: {int(self.cell)}px",
            f"cam: ({int(self.cam[0])},{int(self.cam[1])})",
            f"painting: {self.dragging_paint}",
            f"[F1] HUD  ·  [I] vista  ·  [R] rect",
        ]
        bx = CANVAS_X + CANVAS_W - 230
        by = CANVAS_Y + 6
        bw = 222; bh = len(lines) * 14 + 8
        bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 175))
        screen.blit(bg, (bx, by))
        pygame.draw.rect(screen, (255, 220, 100), (bx, by, bw, bh), 1)
        for i, ln in enumerate(lines):
            draw_text(screen, ln, bx + 6, by + 4 + i*14, FONT_XS, (255, 240, 180))

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
        x += 8
        vw = 130
        rect = pygame.Rect(x, 6, vw, TOP_H-12)
        label = "Vista: Isométrico" if self.view_iso else "Vista: Top-down"
        draw_button(screen, rect, label, FONT_S, active=self.view_iso)
        self._top_hits.append((rect, self._toggle_view))
        x += vw + 10
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
        draw_text(screen, "MAP EDITOR v10", WIDTH - 160, 13, FONT_L, ACCENT_BRIGHT)

    def _switch_mode(self, mode):
        self.mode = mode
        self.expanded_dropdown = None
        for dd in self.dropdowns.values(): dd.expanded = False
        if mode == self.MODE_TILES: self._sync_fields_from_tile()
        if mode == self.MODE_EVENTS and self.editing_event:
            self._sync_fields_from_event(self.editing_event)
        if mode == self.MODE_MAP:
            self._sync_fields_from_map()

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
            draw_text(screen, f"CAMADA ATIVA: {self.active_layer+1}",
                      x, y, FONT_XS, HIGHLIGHT); y += 16
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
            draw_text(screen, "TILES  (clique para escolher)", x, y, FONT_XS, ACCENT); y += 16
            cols = 5; tw = (w - (cols-1)*4) // cols
            cx = x; cy = y
            for tid in self.project.tileset.order:
                t = self.project.tileset.get(tid)
                if not t: continue
                if self.selected_category != "Todos" and t.category != self.selected_category:
                    continue
                rect = pygame.Rect(cx, cy, tw, tw)
                img = t.get_sprite("top", (tw - 4, tw - 4))
                if img: screen.blit(img, (cx+2, cy+2))
                else: pygame.draw.rect(screen, t.color, (cx+2, cy+2, tw-4, tw-4))
                if tid == self.selected_tile_id:
                    pygame.draw.rect(screen, HIGHLIGHT, rect, 3, border_radius=3)
                else:
                    pygame.draw.rect(screen, ACCENT_DARK, rect, 1, border_radius=3)
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
                img = t.get_sprite("top", (tw-4, tw-4))
                if img: screen.blit(img, (cx+2, cy+2))
                else: pygame.draw.rect(screen, t.color, (cx+2, cy+2, tw-4, tw-4))
                if tid == self.selected_tile_id:
                    pygame.draw.rect(screen, HIGHLIGHT, rect, 3, border_radius=3)
                else:
                    pygame.draw.rect(screen, ACCENT_DARK, rect, 1, border_radius=3)
                self._left_hits.append((rect, (lambda tt=tid: self._set_tile(tt)), None))
                cx += tw + 4
                if cx + tw > x + w + 2: cx = x; cy += tw + 4

        elif self.mode == self.MODE_EVENTS:
            draw_text(screen, "TIPO A COLOCAR", x, y, FONT_XS, ACCENT); y += 16
            for kind, label in EVENT_KINDS:
                rect = pygame.Rect(x, y, w, 26)
                active = (kind == self.current_event_kind)
                bg = BTN_ACTIVE if active else BTN
                if rect.collidepoint(pygame.mouse.get_pos()) and not active:
                    bg = BTN_HOVER
                pygame.draw.rect(screen, bg, rect, border_radius=3)
                pygame.draw.rect(screen, EVENT_KIND_COLORS[kind],
                                 (x + 3, y + 3, 20, 20), border_radius=2)
                draw_text(screen, EVENT_KIND_GLYPHS[kind], x + 7, y + 6,
                          FONT_S, (20,15,10))
                draw_text(screen, label, x + 30, y + 6, FONT_S, TEXT)
                self._left_hits.append((rect, (lambda k=kind: self._set_event_kind(k)), None))
                y += 28
            y += 8
            draw_text(screen, "LMB no canvas coloca evento.",
                      x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "Clique num evento para editá-lo.",
                      x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "RMB num evento: menu.",
                      x, y, FONT_XS, TEXT_DIM)

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

    def _set_category(self, cat): self.selected_category = cat
    def _set_tile(self, tid):
        self.selected_tile_id = tid
        self._sync_fields_from_tile()
        self._msg(f"Tile: {tid}", ACCENT)
    def _set_event_kind(self, kind):
        self.current_event_kind = kind

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
            if self.pending_map_click and self.pending_map_click[0] == name:
                bg = (150, 130, 80)
            elif self.dragging_map_name == name:
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
        self.pending_map_click = (name, pygame.mouse.get_pos())

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

    def _draw_right_map(self, x, y, w):
        m = self.project.active_map()
        draw_text(screen, "MAPA", x, y, FONT_XS, ACCENT); y += 16
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
        draw_button(screen, r1, "Larg −1", FONT_XS); draw_button(screen, r2, "Larg +1", FONT_XS)
        self._right_hits.append((r1, lambda: self._quick_resize(-1, 0)))
        self._right_hits.append((r2, lambda: self._quick_resize(1, 0)))
        y += 28
        r3 = pygame.Rect(x, y, half, 24); r4 = pygame.Rect(x + half + 6, y, half, 24)
        draw_button(screen, r3, "Alt −1", FONT_XS); draw_button(screen, r4, "Alt +1", FONT_XS)
        self._right_hits.append((r3, lambda: self._quick_resize(0, -1)))
        self._right_hits.append((r4, lambda: self._quick_resize(0, 1)))
        y += 34

        num_layers = m.num_layers if m else 1
        draw_text(screen, f"CAMADAS  ({num_layers} de {MAX_LAYERS})",
                  x, y, FONT_XS, ACCENT); y += 16
        self.dropdowns["active_layer"].set_position(x, y, w); y += 44
        hlf = (w - 6) // 2
        rl = pygame.Rect(x, y, hlf, 26); rr = pygame.Rect(x + hlf + 6, y, hlf, 26)
        draw_button(screen, rl, "+ Adicionar", FONT_XS)
        draw_button(screen, rr, "− Remover", FONT_XS)
        self._right_hits.append((rl, self._add_layer))
        self._right_hits.append((rr, self._del_layer))
        y += 32

        draw_text(screen, "FERRAMENTAS", x, y, FONT_XS, ACCENT); y += 16
        tools = [("Brush (B)", TOOL_BRUSH), ("Eraser (E)", TOOL_ERASER),
                 ("Fill (F)", TOOL_FILL), ("Conta-gotas (P)", TOOL_PICKER)]
        bw = (w - 6) // 2
        for i, (label, key) in enumerate(tools):
            col = i % 2; row = i // 2
            rect = pygame.Rect(x + col*(bw+6), y + row*26, bw, 22)
            draw_button(screen, rect, label, FONT_XS, active=(self.tool == key))
            self._right_hits.append((rect, (lambda k=key: self._set_tool(k))))
        y += 2 * 26 + 4

        r_rect = pygame.Rect(x, y, w, 24)
        draw_button(screen, r_rect,
                    "▦ Modo retângulo (R): " + ("ON" if self.rect_mode else "OFF"),
                    FONT_XS, active=self.rect_mode)
        self._right_hits.append((r_rect, self._toggle_rect_mode))
        y += 30

        draw_text(screen, "TILE SELECIONADO", x, y, FONT_XS, ACCENT); y += 16
        tid = self.selected_tile_id
        t = self.project.tileset.get(tid) if tid else None
        if t:
            img = t.get_sprite("top", (60, 60))
            if img: screen.blit(img, (x+2, y+2))
            else: pygame.draw.rect(screen, t.color, (x+2, y+2, 60, 60))
            pygame.draw.rect(screen, ACCENT_DARK, (x, y, 64, 64), 2)
            draw_text(screen, t.name[:24], x+76, y+4, FONT_S, TEXT)
            draw_text(screen, f"id: {t.id}", x+76, y+20, FONT_XS, TEXT_DIM)
            if t.height > 0:
                draw_text(screen, f"h:{t.height} esp:{t.thickness:.2f} ({t.thin_axis})",
                          x+76, y+34, FONT_XS, TEXT_DIM)
            else:
                draw_text(screen, f"h:{t.height}", x+76, y+34, FONT_XS, TEXT_DIM)

    def _set_layer(self, i): self.active_layer = i
    def _set_tool(self, k):
        self.tool = k
        self._msg(f"Tool: {k}", ACCENT)
    def _toggle_rect_mode(self):
        self.rect_mode = not self.rect_mode
        self._msg("Modo retângulo: " + ("ON" if self.rect_mode else "OFF"), ACCENT)

    def _draw_right_tiles(self, x, y, w):
        draw_text(screen, "EDITAR TILE", x, y, FONT_XS, ACCENT); y += 16
        tid = self.selected_tile_id
        t = self.project.tileset.get(tid) if tid else None
        if t:
            img = t.get_sprite("top", (76, 76))
            if img: screen.blit(img, (x+2, y+2))
            else: pygame.draw.rect(screen, t.color, (x+2, y+2, 76, 76))
            pygame.draw.rect(screen, ACCENT_DARK, (x, y, 80, 80), 2)
            draw_text(screen, f"id: {t.id}", x+90, y+6, FONT_S, TEXT_GOLD)
            draw_text(screen, f"walk: {t.walkable}", x+90, y+24, FONT_XS,
                      SUCCESS if t.walkable else DANGER)
            draw_text(screen, f"h: {t.height}  ·  sight: {t.blocks_sight}",
                      x+90, y+40, FONT_XS, TEXT_DIM)
            draw_text(screen, f"esp: {t.thickness:.2f}  ·  {t.thin_axis}",
                      x+90, y+54, FONT_XS, ACCENT)
            y += 92
        self.fields["tile_name"].set_position(x, y, w); y += 42
        self.fields["tile_category"].set_position(x, y, w); y += 42
        hlf = (w - 6) // 2
        self.fields["tile_color"].set_position(x, y, hlf)
        self.fields["tile_height"].set_position(x + hlf + 6, y, hlf); y += 42

        # Linha de espessura
        draw_text(screen, "ESPESSURA DA PAREDE (height > 0)", x, y, FONT_XS, ACCENT)
        y += 14
        hlf2 = (w - 6) // 2
        self.fields["tile_thickness"].set_position(x, y, hlf2)
        self.dropdowns["tile_thin_axis"].set_position(x + hlf2 + 6, y, hlf2)
        y += 46

        draw_text(screen, "SPRITES DO TILE  (top / side_left / side_right)",
                  x, y, FONT_XS, ACCENT); y += 18
        slot_names_pt = {"top": "Top", "side_left": "Left", "side_right": "Right"}
        for slot in TILE_SLOTS:
            row = pygame.Rect(x, y, w, 28)
            pygame.draw.rect(screen, (30, 26, 22), row, border_radius=3)
            pygame.draw.rect(screen, ACCENT_DARK, row, 1, border_radius=3)
            mini = pygame.Rect(x + 3, y + 3, 22, 22)
            img = t.get_sprite(slot, (20, 20)) if t else None
            if img: screen.blit(img, (mini.x + 1, mini.y + 1))
            else:
                pygame.draw.rect(screen, (50, 44, 38), mini)
                draw_text(screen, "—", mini.x + 7, mini.y + 3, FONT_XS, TEXT_DIM)
            pygame.draw.rect(screen, ACCENT_DARK, mini, 1)
            draw_text(screen, slot_names_pt[slot], x + 32, y + 7, FONT_S, TEXT)
            bw2 = 80
            r_pick = pygame.Rect(x + w - bw2*2 - 6, y + 2, bw2, 24)
            r_del  = pygame.Rect(x + w - bw2 + 2 - 12, y + 2, 20, 24)
            draw_button(screen, r_pick, "Escolher…", FONT_XS)
            draw_button(screen, r_del, "X", FONT_XS, danger=True)
            self._right_hits.append((r_pick, (lambda s=slot: self._pick_slot_image(s))))
            self._right_hits.append((r_del, (lambda s=slot: self._remove_slot_image(s))))
            y += 32

        r_open = pygame.Rect(x, y, w, 26)
        draw_button(screen, r_open, "Abrir pasta do tile", FONT_XS)
        self._right_hits.append((r_open, self._open_tile_folder))
        y += 32

        rects = [
            ("Aplicar propriedades", self._apply_tile_fields, True, False),
            ("Walkable (toggle)", self._toggle_walkable, False, False),
            ("Blocks sight (toggle)", self._toggle_blocks_sight, False, False),
            ("+ Novo tile", self._new_tile, False, False),
            ("Duplicar", self._dup_tile, False, False),
            ("Excluir", self._del_tile, False, True),
        ]
        for label, cb, primary, danger in rects:
            r = pygame.Rect(x, y, w, 28)
            draw_button(screen, r, label, FONT_XS, primary=primary, danger=danger)
            self._right_hits.append((r, cb))
            y += 32

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
        for line in ["· LMB pinta modo ativo",
                     "· RMB pinta Blocked",
                     "· Shift+LMB limpa override",
                     "· Sem override, tile decide"]:
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
        ev = self.editing_event
        if not ev:
            draw_text(screen, "EDITAR EVENTO", x, y, FONT_XS, ACCENT); y += 20
            draw_text(screen, "Clique num evento no canvas",
                      x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "para editá-lo.",
                      x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "Ou clique no canvas (vazio)",
                      x, y, FONT_XS, TEXT_DIM); y += 14
            draw_text(screen, "para colocar um novo.",
                      x, y, FONT_XS, TEXT_DIM)
            return

        draw_text(screen, "EDITAR EVENTO", x, y, FONT_XS, ACCENT); y += 16
        col = EVENT_KIND_COLORS.get(ev.kind, (200,200,200))
        pygame.draw.rect(screen, col, (x, y, 24, 24), border_radius=3)
        draw_text(screen, EVENT_KIND_GLYPHS.get(ev.kind, "?"),
                  x + 7, y + 6, FONT_S, (20,15,10))
        draw_text(screen, f"posição: ({ev.x},{ev.y})", x + 32, y + 8,
                  FONT_XS, TEXT_DIM)
        y += 32
        self.dropdowns["ev_kind"].set_position(x, y, w); y += 44
        hlf = (w - 6) // 2
        self.fields["ev_name"].set_position(x, y, hlf)
        self.fields["ev_id"].set_position(x + hlf + 6, y, hlf); y += 42
        self.fields["ev_tag"].set_position(x, y, w); y += 42

        if ev.kind == "trigger":
            draw_text(screen, "QUANDO ATIVAR", x, y, FONT_XS, ACCENT); y += 16
            self.dropdowns["ev_when"].set_position(x, y, w); y += 44
        elif ev.kind == "teleport":
            draw_text(screen, "DESTINO", x, y, FONT_XS, ACCENT); y += 16
            third = (w - 12) // 3
            self.fields["ev_tx"].set_position(x, y, third)
            self.fields["ev_ty"].set_position(x + third + 6, y, third)
            self.fields["ev_tz"].set_position(x + 2*(third+6), y, third)
            y += 42
            self.fields["ev_target_map"].set_position(x, y, w - 96)
            r = pygame.Rect(x + w - 90, y + 14, 90, 24)
            draw_button(screen, r, "Escolher mapa", FONT_XS)
            self._right_hits.append((r, (lambda p=(x, y+40): self._select_target_map(p))))
            y += 42

        draw_text(screen, "PROPRIEDADES CUSTOM", x, y, FONT_XS, ACCENT); y += 14
        for i in range(1, 7):
            hlf2 = (w - 6) // 2
            self.fields[f"ev_k{i}"].set_position(x, y, hlf2)
            self.fields[f"ev_v{i}"].set_position(x + hlf2 + 6, y, hlf2)
            y += 42

        r_apply = pygame.Rect(x, y, w, 30)
        draw_button(screen, r_apply, "Aplicar alterações", FONT_XS, primary=True)
        self._right_hits.append((r_apply, self._apply_event_fields)); y += 34
        r_del = pygame.Rect(x, y, w, 30)
        draw_button(screen, r_del, "Deletar evento", FONT_XS, danger=True)
        self._right_hits.append((r_del, (lambda e=ev: self._del_event(e)))); y += 34

    # ================================================================
    # Canvas
    # ================================================================
    def _draw_canvas(self):
        clip = self._canvas_rect()
        old = screen.get_clip()
        screen.set_clip(clip)
        pygame.draw.rect(screen, CANVAS_BG, clip)

        m = self.project.active_map()
        if m:
            if self.view_iso:
                self._draw_map_layers_iso(m)
                self._draw_layer_highlight_iso(m)
                if self.mode == self.MODE_PASS: self._draw_passability_iso(m)
                if self.mode == self.MODE_EVENTS: self._draw_events_iso(m)
                self._draw_paint_flashes_iso()
                self._draw_iso_rect_preview()
                self._draw_hover_iso()
            else:
                self._draw_map_layers(m)
                self._draw_layer_highlight_td(m)
                if self.mode == self.MODE_PASS: self._draw_passability(m)
                if self.mode == self.MODE_EVENTS: self._draw_events(m)
                self._draw_paint_flashes_td()
                self._draw_hover_td()

        screen.set_clip(old)
        pygame.draw.rect(screen, PANEL_BORDER, clip, 2)

    # ================================================================
    # Layer highlight
    # ================================================================
    def _cell_has_active(self, m, gx, gy):
        return m.data[gy][gx][self.active_layer] is not None
    def _cell_has_inactive(self, m, gx, gy):
        for l in range(m.num_layers):
            if l == self.active_layer: continue
            if m.data[gy][gx][l] is not None: return True
        return False

    def _draw_layer_highlight_td(self, m):
        cs_i = int(round(self.cell))
        ox = CANVAS_X - self.cam[0]; oy = CANVAS_Y - self.cam[1]
        cell_w = int(self.cell)
        x0 = max(0, int((CANVAS_X - ox) // self.cell))
        y0 = max(0, int((CANVAS_Y - oy) // self.cell))
        x1 = min(m.w, int((CANVAS_X + CANVAS_W - ox) // self.cell) + 1)
        y1 = min(m.h, int((CANVAS_Y + CANVAS_H - oy) // self.cell) + 1)
        overlay = pygame.Surface((cell_w, cell_w), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 255 - INACTIVE_LAYER_ALPHA))
        for y in range(y0, y1):
            for x in range(x0, x1):
                if self._cell_has_active(m, x, y): continue
                if not self._cell_has_inactive(m, x, y): continue
                rx = int(ox + x * self.cell)
                ry = int(oy + y * self.cell)
                screen.blit(overlay, (rx, ry))

    def _draw_layer_highlight_iso(self, m):
        tw = self._iso_tw(); th = self._iso_th()
        dark_alpha = 255 - INACTIVE_LAYER_ALPHA
        for depth in range(m.w + m.h - 1):
            gx_start = max(0, depth - m.h + 1)
            gx_end = min(m.w - 1, depth)
            for gx in range(gx_start, gx_end + 1):
                gy = depth - gx
                if not (0 <= gy < m.h): continue
                if self._cell_has_active(m, gx, gy): continue
                if not self._cell_has_inactive(m, gx, gy): continue
                wx = (gx - gy) * tw / 2
                wy = (gx + gy) * th / 2
                cx, cy = self._world_to_screen(wx, wy + th / 2)
                cx = int(cx); cy = int(cy)
                if cx + tw < CANVAS_X or cx - tw > CANVAS_X + CANVAS_W: continue
                if cy + th * 2 < CANVAS_Y or cy - th * 2 > CANVAS_Y + CANVAS_H:
                    continue
                self._draw_iso_diamond_flat(cx, cy, (0, 0, 0), alpha=dark_alpha)

    # ================================================================
    # Top-down
    # ================================================================
    def _draw_paint_flashes_td(self):
        if not self.paint_flashes: return
        cs = int(round(self.cell))
        for fx, fy, tleft in self.paint_flashes:
            rx = int(CANVAS_X + fx * self.cell - self.cam[0])
            ry = int(CANVAS_Y + fy * self.cell - self.cam[1])
            a = int(200 * (tleft / 0.35))
            s = pygame.Surface((cs, cs), pygame.SRCALPHA)
            s.fill((255, 240, 120, a))
            screen.blit(s, (rx, ry))

    def _draw_hover_td(self):
        if not self.hover_cell: return
        if self.mode not in (self.MODE_MAP, self.MODE_PASS, self.MODE_EVENTS): return
        cs = int(round(self.cell))
        wx, wy = self.hover_cell
        x = int(wx * self.cell - self.cam[0]) + CANVAS_X
        y = int(wy * self.cell - self.cam[1]) + CANVAS_Y
        if self.mode == self.MODE_MAP and self.rect_mode \
                and self.rect_start and self.rect_end:
            x1, y1 = self.rect_start; x2, y2 = self.rect_end
            xa, xb = sorted((x1, x2)); ya, yb = sorted((y1, y2))
            rx1 = int(xa * self.cell - self.cam[0]) + CANVAS_X
            ry1 = int(ya * self.cell - self.cam[1]) + CANVAS_Y
            rw = int((xb - xa + 1) * self.cell)
            rh = int((yb - ya + 1) * self.cell)
            s = pygame.Surface((rw, rh), pygame.SRCALPHA)
            if self.tool == TOOL_ERASER:
                s.fill((230, 100, 100, 80))
                border = DANGER
            else:
                s.fill((255, 220, 100, 80))
                border = HIGHLIGHT
            screen.blit(s, (rx1, ry1))
            pygame.draw.rect(screen, border, (rx1, ry1, rw, rh), 2)
        else:
            border_col = HIGHLIGHT
            if self.mode == self.MODE_PASS: border_col = SUCCESS
            if self.mode == self.MODE_EVENTS:
                border_col = EVENT_KIND_COLORS.get(self.current_event_kind, HIGHLIGHT)
            pygame.draw.rect(screen, border_col, (x, y, cs, cs), 2)

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
        for layer in range(m.num_layers):
            for y in range(y0, y1):
                for x in range(x0, x1):
                    tid = m.data[y][x][layer]
                    if tid is None: continue
                    t = self.project.tileset.get(tid)
                    if t is None: continue
                    rx = int(ox + x * cs); ry = int(oy + y * cs)
                    img = t.get_sprite("top", (cs_i+1, cs_i+1))
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
            col = EVENT_KIND_COLORS.get(ev.kind, (200,200,200))
            sprite_drawn = False
            if ev.sprite:
                try:
                    if os.path.isfile(ev.sprite):
                        img = pygame.image.load(ev.sprite).convert_alpha()
                        img = pygame.transform.smoothscale(img, (cs_i, cs_i))
                        screen.blit(img, (rx, ry)); sprite_drawn = True
                except Exception: pass
            if not sprite_drawn:
                pygame.draw.rect(screen, col, (rx+2, ry+2, cs_i-4, cs_i-4),
                                 border_radius=3)
                pygame.draw.rect(screen, (20,15,10), (rx+2, ry+2, cs_i-4, cs_i-4),
                                 2, border_radius=3)
                g = FONT_XS.render(EVENT_KIND_GLYPHS.get(ev.kind, "?"),
                                   True, (20,15,10))
                screen.blit(g, (rx + cs_i//2 - g.get_width()//2,
                                ry + cs_i//2 - g.get_height()//2))
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

    # ================================================================
    # Isométrico — helpers de desenho
    # ================================================================
    def _draw_iso_diamond_flat(self, cx, cy, color, alpha=255):
        tw = self._iso_tw(); th = self._iso_th()
        hw = tw / 2; hh = th / 2
        pts = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]
        if alpha >= 255:
            pygame.draw.polygon(screen, color[:3], pts)
        else:
            minx = int(cx - hw) - 2; miny = int(cy - hh) - 2
            w = int(tw) + 6; h = int(th) + 6
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            lp = [(hw, 0), (tw, hh), (hw, th), (0, hh)]
            lp = [(int(p[0]) + 3, int(p[1]) + 3) for p in lp]
            pygame.draw.polygon(surf, (color[0], color[1], color[2], alpha), lp)
            screen.blit(surf, (minx, miny))

    def _draw_iso_diamond_textured(self, cx, cy, img):
        tw = int(self._iso_tw()); th = int(self._iso_th())
        hw = tw // 2; hh = th // 2
        mask = pygame.Surface((tw, th), pygame.SRCALPHA)
        pts = [(hw, 0), (tw, hh), (hw, th), (0, hh)]
        pygame.draw.polygon(mask, (255, 255, 255, 255), pts)
        tex = img.copy()
        tex.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(tex, (int(cx - hw), int(cy - hh)))

    def _draw_poly_solid(self, poly, color):
        pygame.draw.polygon(screen, color[:3], poly)

    def _draw_poly_textured(self, poly, t, slot, fallback_color):
        """Desenha um polígono com textura (ou cor se não houver sprite)."""
        if t is None:
            self._draw_poly_solid(poly, fallback_color); return
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        minx = int(min(xs)) - 1; miny = int(min(ys)) - 1
        maxx = int(max(xs)) + 1; maxy = int(max(ys)) + 1
        w = maxx - minx + 2; h = maxy - miny + 2
        if w <= 1 or h <= 1:
            self._draw_poly_solid(poly, fallback_color); return
        img = t.get_sprite(slot, (w, h))
        if img is None:
            self._draw_poly_solid(poly, fallback_color); return
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        local_poly = [(int(p[0]) - minx, int(p[1]) - miny) for p in poly]
        pygame.draw.polygon(mask, (255, 255, 255, 255), local_poly)
        tex = img.copy()
        tex.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(tex, (minx, miny))

    def _draw_iso_wall_full(self, t, cx, cy, height):
        """Muro padrão: cubo isométrico de célula cheia."""
        tw = self._iso_tw(); th = self._iso_th()
        hw = tw / 2; hh = th / 2
        H = int(height)
        # Vértices base e topo
        N = (cx, cy - hh); E = (cx + hw, cy)
        S = (cx, cy + hh); W = (cx - hw, cy)
        Nt = (N[0], N[1] - H); Et = (E[0], E[1] - H)
        St = (S[0], S[1] - H); Wt = (W[0], W[1] - H)

        col_sw = darken(t.color, 0.5)
        col_se = darken(t.color, 0.75)
        col_top = tuple(t.color[:3])

        # Fase SW (esquerda visível) = W-S
        self._draw_poly_textured([W, S, St, Wt], t, "side_left", col_sw)
        # Fase SE (direita visível) = S-E
        self._draw_poly_textured([S, E, Et, St], t, "side_right", col_se)
        # Topo = N-E-S-W
        self._draw_poly_textured([Nt, Et, St, Wt], t, "top", col_top)

    def _draw_iso_wall_thin(self, t, cx, cy, height, thickness, thin_axis):
        """
        Muro com espessura < 1.

        thin_axis='x': encolhe ao longo de gx (aparece como faixa vertical na tela)
        thin_axis='y': encolhe ao longo de gy (aparece como faixa horizontal na tela)

        Paredes adjacentes no mesmo eixo compartilham a mesma aresta encolhida,
        então se conectam perfeitamente.
        """
        tw = self._iso_tw(); th = self._iso_th()
        s = max(0.0, min(0.49, (1.0 - thickness) / 2.0))
        H = int(height)

        # Offsets das 4 quinas em relação ao CENTRO do diamante
        # (comprovado por álgebra: dx = (a-b)*tw/2, dy = (a+b-1)*th/2)
        if thin_axis == "x":
            N = ( s * tw / 2,  (s - 1) * th / 2)
            E = ((1 - s) * tw / 2, -s * th / 2)
            S = (-s * tw / 2, (1 - s) * th / 2)
            W = ((s - 1) * tw / 2, s * th / 2)
        else:  # "y"
            N = (-s * tw / 2, (s - 1) * th / 2)
            E = ((1 - s) * tw / 2, s * th / 2)
            S = ( s * tw / 2, (1 - s) * th / 2)
            W = ((s - 1) * tw / 2, -s * th / 2)

        Np = (cx + N[0], cy + N[1])
        Ep = (cx + E[0], cy + E[1])
        Sp = (cx + S[0], cy + S[1])
        Wp = (cx + W[0], cy + W[1])
        Nt = (Np[0], Np[1] - H)
        Et = (Ep[0], Ep[1] - H)
        St = (Sp[0], Sp[1] - H)
        Wt = (Wp[0], Wp[1] - H)

        col_sw = darken(t.color, 0.5)
        col_se = darken(t.color, 0.75)
        col_top = tuple(t.color[:3])

        # Faces visíveis (SW e SE) + topo
        self._draw_poly_textured([Wp, Sp, St, Wt], t, "side_left", col_sw)
        self._draw_poly_textured([Sp, Ep, Et, St], t, "side_right", col_se)
        self._draw_poly_textured([Nt, Et, St, Wt], t, "top", col_top)

    def _draw_iso_tile(self, t, cx, cy, height_px):
        """Ponto de entrada: dispatch entre ground e wall (cheio/fino)."""
        tw = self._iso_tw(); th = self._iso_th()
        if height_px <= 0:
            # Ground: sempre diamante com textura top
            top = t.get_sprite("top", (int(tw), int(th)))
            if top:
                self._draw_iso_diamond_textured(cx, cy, top)
            else:
                self._draw_iso_diamond_flat(cx, cy, t.color)
            return

        # Wall: cheio ou fino?
        if (t.thin_axis in ("x", "y")) and (t.thickness < 0.999):
            self._draw_iso_wall_thin(t, cx, cy, height_px,
                                     t.thickness, t.thin_axis)
        else:
            self._draw_iso_wall_full(t, cx, cy, height_px)

    def _draw_map_layers_iso(self, m):
        tw = self._iso_tw(); th = self._iso_th()
        wall_unit = self._iso_wall_unit()
        for depth in range(m.w + m.h - 1):
            gx_start = max(0, depth - m.h + 1)
            gx_end = min(m.w - 1, depth)
            for gx in range(gx_start, gx_end + 1):
                gy = depth - gx
                if not (0 <= gy < m.h): continue
                wx = (gx - gy) * tw / 2
                wy = (gx + gy) * th / 2
                cx, cy = self._world_to_screen(wx, wy + th / 2)
                cx = int(cx); cy = int(cy)
                if cx + tw < CANVAS_X or cx - tw > CANVAS_X + CANVAS_W: continue
                if cy + th * 2 < CANVAS_Y or cy - wall_unit * 12 > CANVAS_Y + CANVAS_H:
                    continue
                for layer in range(m.num_layers):
                    tid = m.data[gy][gx][layer]
                    if tid is None: continue
                    t = self.project.tileset.get(tid)
                    if t is None: continue
                    self._draw_iso_tile(t, cx, cy, wall_unit * t.height)
                if self.show_grid and self.cell >= 10:
                    hw = tw / 2; hh = th / 2
                    pts = [(cx, cy - hh), (cx + hw, cy),
                           (cx, cy + hh), (cx - hw, cy)]
                    pygame.draw.polygon(screen, (0, 0, 0), pts, 1)

    def _draw_passability_iso(self, m):
        tw = self._iso_tw(); th = self._iso_th()
        for gy in range(m.h):
            for gx in range(m.w):
                base = m.tile_walkable_default(gx, gy, self.project.tileset) \
                    if not m.is_empty(gx, gy) else None
                override = m.passability.get((gx, gy))
                if override == "ok" or override is True: col = PASS_OK
                elif override == "block" or override is False: col = PASS_BLOCK
                elif override == "above": col = PASS_ABOVE
                elif override is None:
                    if base is True: col = PASS_TILE_OK
                    elif base is False: col = PASS_TILE_BLK
                    else: col = None
                else: col = None
                if col is None: continue
                wx = (gx - gy) * tw / 2
                wy = (gx + gy) * th / 2
                cx, cy = self._world_to_screen(wx, wy + th / 2)
                cx = int(cx); cy = int(cy)
                if cx + tw < CANVAS_X or cx - tw > CANVAS_X + CANVAS_W: continue
                if cy + th * 2 < CANVAS_Y or cy - th * 2 > CANVAS_Y + CANVAS_H: continue
                self._draw_iso_diamond_flat(cx, cy, col[:3], alpha=col[3])

    def _draw_events_iso(self, m):
        tw = self._iso_tw(); th = self._iso_th()
        for ev in m.events:
            wx = (ev.x - ev.y) * tw / 2
            wy = (ev.x + ev.y) * th / 2
            cx, cy = self._world_to_screen(wx, wy + th / 2)
            cx = int(cx); cy = int(cy)
            if cx + tw < CANVAS_X or cx - tw > CANVAS_X + CANVAS_W: continue
            if cy + th * 2 < CANVAS_Y or cy - th * 2 > CANVAS_Y + CANVAS_H: continue
            col = EVENT_KIND_COLORS.get(ev.kind, (200, 200, 200))
            r = max(6, int(self.cell * 0.4))
            pygame.draw.circle(screen, col, (cx, cy), r)
            pygame.draw.circle(screen, (20, 15, 10), (cx, cy), r, 2)
            g = FONT_XS.render(EVENT_KIND_GLYPHS.get(ev.kind, "?"),
                               True, (20, 15, 10))
            screen.blit(g, (cx - g.get_width()//2, cy - g.get_height()//2))
            if r >= 10:
                idtxt = FONT_XS.render(str(ev.id), True, (255, 255, 255))
                idbg = pygame.Surface((idtxt.get_width() + 4,
                                       idtxt.get_height() + 2), pygame.SRCALPHA)
                idbg.fill((0, 0, 0, 180))
                screen.blit(idbg, (cx + r - 2, cy - r - 2))
                screen.blit(idtxt, (cx + r, cy - r))

    def _draw_paint_flashes_iso(self):
        if not self.paint_flashes: return
        tw = self._iso_tw(); th = self._iso_th()
        for fx, fy, tleft in self.paint_flashes:
            wx = (fx - fy) * tw / 2
            wy = (fx + fy) * th / 2
            cx, cy = self._world_to_screen(wx, wy + th / 2)
            cx = int(cx); cy = int(cy)
            if cx + tw < CANVAS_X or cx - tw > CANVAS_X + CANVAS_W: continue
            if cy + th * 2 < CANVAS_Y or cy - th * 2 > CANVAS_Y + CANVAS_H: continue
            a = int(200 * (tleft / 0.35))
            self._draw_iso_diamond_flat(cx, cy, (255, 240, 120), alpha=a)

    def _draw_iso_rect_preview(self):
        if self.mode != self.MODE_MAP: return
        if not self.rect_mode: return
        if not (self.rect_start and self.rect_end): return
        tw = self._iso_tw(); th = self._iso_th()
        x1, y1 = self.rect_start; x2, y2 = self.rect_end
        xa, xb = min(x1, x2), max(x1, x2)
        ya, yb = min(y1, y2), max(y1, y2)
        is_erase = (self.tool == TOOL_ERASER)
        color = (230, 100, 100) if is_erase else (255, 240, 120)
        for gy in range(ya, yb + 1):
            for gx in range(xa, xb + 1):
                wx = (gx - gy) * tw / 2
                wy = (gx + gy) * th / 2
                cx, cy = self._world_to_screen(wx, wy + th / 2)
                cx = int(cx); cy = int(cy)
                self._draw_iso_diamond_flat(cx, cy, color, alpha=100)

    def _draw_hover_iso(self):
        if not self.hover_cell: return
        if self.mode not in (self.MODE_MAP, self.MODE_PASS, self.MODE_EVENTS): return
        gx, gy = self.hover_cell
        tw = self._iso_tw(); th = self._iso_th()
        hw = tw / 2; hh = th / 2
        wx = (gx - gy) * tw / 2
        wy = (gx + gy) * th / 2
        cx, cy = self._world_to_screen(wx, wy + th / 2)
        cx = int(cx); cy = int(cy)
        m = self.project.active_map()
        if self.mode == self.MODE_PASS:
            walk = m.is_walkable(gx, gy, self.project.tileset)
            col = SUCCESS if walk else DANGER
        elif self.mode == self.MODE_EVENTS:
            col = EVENT_KIND_COLORS.get(self.current_event_kind, HIGHLIGHT)
        else:
            col = HIGHLIGHT
        pts = [(cx, cy - hh), (cx + hw, cy),
               (cx, cy + hh), (cx - hw, cy)]
        pygame.draw.polygon(screen, col, pts, 2)

    # ================================================================
    # Bottom bar / msg
    # ================================================================
    def _draw_bottom_bar(self):
        r = pygame.Rect(0, HEIGHT - BOTTOM_H, WIDTH, BOTTOM_H)
        pygame.draw.rect(screen, PANEL_DARK, r)
        pygame.draw.line(screen, PANEL_BORDER, (0, HEIGHT-BOTTOM_H),
                         (WIDTH, HEIGHT-BOTTOM_H))
        m = self.project.active_map()
        nl = m.num_layers if m else 1
        vista = "ISO" if self.view_iso else "TOP"
        rect_tag = "  ·  ▦ rect ON" if self.rect_mode else ""
        if self.mode == self.MODE_MAP:
            hint = (f"[{vista}] Camada {self.active_layer+1}/{nl}  ·  tool: {self.tool}{rect_tag}  ·  "
                    "B/E/F/P/R  ·  I vista  ·  Ctrl+Z/Y undo  ·  G grade  ·  F1 debug")
        elif self.mode == self.MODE_TILES:
            hint = f"[{vista}] Sprites por slot  ·  Espessura p/ paredes finas"
        elif self.mode == self.MODE_PASS:
            hint = f"[{vista}] LMB pinta modo ativo  ·  RMB pinta Blocked"
        else:
            hint = f"[{vista}] LMB coloca/seleciona  ·  RMB menu"
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
    print("=" * 66)
    print("MapEditor v10 — Paredes com espessura ajustável")
    print("· Campo 'Espessura' 0.10..1.00 (1.00 = cheia)")
    print("· Direção fina: 'Fino em X' (corre em Y) / 'Fino em Y' (corre em X)")
    print("· Duas paredes adjacentes com a MESMA espessura+direção se conectam")
    print("· Só afeta tiles com height > 0 (paredes)")
    print("=" * 66)
    MapEditorApp().run()