# -*- coding: utf-8 -*-
"""
Overmap.py — Gerador de overmap com biomas + painel de configurações.

Controles:
- TAB        : abre/fecha painel de configurações
- ESPAÇO / R : gera novo mundo (novo seed) com os parâmetros atuais
- WASD       : move a câmera (SHIFT = rápido)
- Scroll     : zoom centrado no cursor
- HOME       : recentraliza o mapa
- L          : carrega o último overmap salvo
- B          : abre diálogo de salvar (pede nome)
- ESC        : fecha painel / diálogo / sai
"""

import os, json, random
import pygame

# ============================================================================
# Config
# ============================================================================
WIDTH, HEIGHT = 1280, 800
BASE_CELL = 28
SETTINGS_W = 360

pygame.init()
pygame.font.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Overmap Generator")
clock = pygame.time.Clock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports", "overmaps")
os.makedirs(EXPORTS_DIR, exist_ok=True)

# ============================================================================
# Cores
# ============================================================================
BG            = (18, 16, 14)
PANEL_BG      = (30, 26, 22)
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
BTN           = (60, 50, 40)
BTN_HOVER     = (95, 78, 58)
BTN_TEXT      = (235, 225, 205)

FONT_L  = pygame.font.SysFont("georgia,dejavuserif,serif", 18, bold=True)
FONT_M  = pygame.font.SysFont("georgia,dejavuserif,serif", 14)
FONT_S  = pygame.font.SysFont("georgia,dejavuserif,serif", 12)
FONT_XS = pygame.font.SysFont("georgia,dejavuserif,serif", 11)

# ============================================================================
# Helpers
# ============================================================================
def draw_text(surf, text, x, y, font=FONT_M, color=TEXT, center=False):
    r = font.render(str(text), True, color)
    if center: surf.blit(r, (x - r.get_width()//2, y))
    else:      surf.blit(r, (x, y))
    return r


def draw_button(surf, rect, label, font=FONT_XS, primary=False):
    mouse = pygame.mouse.get_pos()
    hover = rect.collidepoint(mouse)
    if primary:
        bg = (170, 130, 65) if hover else ACCENT
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


# ============================================================================
# Biomas
# ============================================================================
BIOMES = {
    "sea":      {"color": (40, 70, 120),   "name": "Mar"},
    "coast":    {"color": (200, 180, 120), "name": "Costa"},
    "plains":   {"color": (100, 140, 80),  "name": "Planície"},
    "forest":   {"color": (55, 95, 50),    "name": "Floresta"},
    "swamp":    {"color": (70, 90, 55),    "name": "Pântano"},
    "mountain": {"color": (110, 95, 80),   "name": "Montanha"},
    "snow":     {"color": (215, 215, 225), "name": "Neve"},
    "desert":   {"color": (200, 175, 110), "name": "Deserto"},
}

def biome_color(b): return BIOMES.get(b, {"color": (128,128,128)})["color"]
def biome_name(b):  return BIOMES.get(b, {"name": "?"})["name"]


# ============================================================================
# Noise
# ============================================================================
def _lerp(a, b, t): return a + (b - a) * t
def _smooth(t):     return t * t * (3 - 2 * t)


def value_noise(w, h, seed, scale):
    rng = random.Random(seed)
    gw = max(2, w // scale + 2)
    gh = max(2, h // scale + 2)
    grid = [[rng.random() for _ in range(gw)] for _ in range(gh)]
    out = [[0.0] * w for _ in range(h)]
    for y in range(h):
        gy = y / scale
        y0 = int(gy); fy = _smooth(gy - y0)
        for x in range(w):
            gx = x / scale
            x0 = int(gx); fx = _smooth(gx - x0)
            v00 = grid[y0][x0]
            v10 = grid[y0][min(x0+1, gw-1)]
            v01 = grid[min(y0+1, gh-1)][x0]
            v11 = grid[min(y0+1, gh-1)][min(x0+1, gw-1)]
            out[y][x] = _lerp(_lerp(v00, v10, fx), _lerp(v01, v11, fx), fy)
    return out


def fractal_noise(w, h, seed, scale, octaves=3):
    result = [[0.0] * w for _ in range(h)]
    amp = 1.0; total = 0.0
    for i in range(octaves):
        layer = value_noise(w, h, seed + i * 101, max(2, scale >> i))
        for y in range(h):
            for x in range(w):
                result[y][x] += layer[y][x] * amp
        total += amp
        amp *= 0.5
    for y in range(h):
        for x in range(w):
            result[y][x] /= total
    return result


# ============================================================================
# Parâmetros padrão
# ============================================================================
DEFAULT_PARAMS = {
    "w": 40, "h": 25,
    "elev_scale": 10.0, "elev_octaves": 4,
    "moist_scale": 12.0, "moist_octaves": 3,
    "sea_th": 0.30, "coast_th": 0.36, "mountain_th": 0.74,
    "swamp_elev": 0.48, "swamp_moist": 0.60,
    "forest_moist": 0.55, "desert_moist": 0.40,
    "snow_lat": 0.15, "desert_lat": 0.85,
    "lat_jitter": 0.15,
    "seed_elev": 0, "seed_moist": 5000, "seed_lat": 9999,
}


# ============================================================================
# Overmap
# ============================================================================
class Overmap:
    def __init__(self, seed=None, params=None):
        self.params = dict(DEFAULT_PARAMS)
        if params:
            self.params.update(params)
        self.seed = seed if seed is not None else random.randint(0, 10**9)
        self.w = int(self.params["w"])
        self.h = int(self.params["h"])
        self.biomes = []
        self.counts = {}
        self.generate()

    def generate(self):
        p = self.params
        w, h = self.w, self.h
        elev = fractal_noise(w, h, self.seed + int(p["seed_elev"]),
                             max(2, int(round(p["elev_scale"]))),
                             int(p["elev_octaves"]))
        moist = fractal_noise(w, h, self.seed + int(p["seed_moist"]),
                              max(2, int(round(p["moist_scale"]))),
                              int(p["moist_octaves"]))
        lat_noise = fractal_noise(w, h, self.seed + int(p["seed_lat"]), 5, 3)

        e_vals = [v for row in elev for v in row]
        e_min, e_max = min(e_vals), max(e_vals)
        if e_max - e_min < 1e-6:
            e_max = e_min + 1e-6

        jitter_amp = float(p["lat_jitter"])

        self.biomes = []
        counts = {k: 0 for k in BIOMES.keys()}
        for y in range(h):
            row = []
            t = y / max(1, h - 1)
            for x in range(w):
                e = (elev[y][x] - e_min) / (e_max - e_min)
                m = moist[y][x]
                n = lat_noise[y][x]

                lat_j = (n - 0.5) * jitter_amp
                snow_th   = p["snow_lat"]   + lat_j
                desert_th = p["desert_lat"] - lat_j

                if   e < p["sea_th"]:                                b = "sea"
                elif e < p["coast_th"]:                              b = "coast"
                elif t < snow_th:                                    b = "snow"
                elif e > p["mountain_th"]:                           b = "mountain"
                elif t > desert_th and m < p["desert_moist"]:        b = "desert"
                elif m > p["swamp_moist"] and e < p["swamp_elev"]:   b = "swamp"
                elif m > p["forest_moist"]:                          b = "forest"
                else:                                                b = "plains"

                row.append(b)
                counts[b] += 1
            self.biomes.append(row)
        self.counts = counts

    def biome_at(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.biomes[y][x]
        return None

    def regenerate(self, seed=None):
        if seed is None:
            self.seed = random.randint(0, 10**9)
        else:
            self.seed = seed
        self.w = int(self.params["w"])
        self.h = int(self.params["h"])
        self.generate()

    def to_dict(self):
        return {
            "w": self.w, "h": self.h, "seed": self.seed,
            "biomes": self.biomes,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, d):
        om = cls(seed=d["seed"], params=d.get("params"))
        om.w = d["w"]; om.h = d["h"]
        om.biomes = d["biomes"]
        counts = {k: 0 for k in BIOMES.keys()}
        for row in om.biomes:
            for b in row:
                counts[b] = counts.get(b, 0) + 1
        om.counts = counts
        return om

    def save(self, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ============================================================================
# Slider
# ============================================================================
class Slider:
    def __init__(self, key, label, min_v, max_v, value,
                 is_int=False, fmt=None):
        self.key = key
        self.label = label
        self.min_v = float(min_v)
        self.max_v = float(max_v)
        self.value = value
        self.is_int = is_int
        if fmt is not None:
            self.fmt = fmt
        elif is_int:
            self.fmt = lambda v: str(int(v))
        else:
            self.fmt = lambda v: f"{v:.2f}"

        self.dragging = False
        self.rect = None
        self.label_rect = None

    def set_position(self, x, y, w):
        self.label_rect = pygame.Rect(x, y, w, 14)
        self.rect = pygame.Rect(x, y + 14, w, 10)

    def value_to_x(self):
        t = (self.value - self.min_v) / max(1e-6, self.max_v - self.min_v)
        return self.rect.x + int(t * self.rect.w)

    def x_to_value(self, mx):
        t = (mx - self.rect.x) / max(1, self.rect.w)
        t = max(0.0, min(1.0, t))
        v = self.min_v + t * (self.max_v - self.min_v)
        if self.is_int:
            return int(round(v))
        return round(v, 3)

    def randomize(self):
        if self.is_int:
            self.value = random.randint(int(self.min_v), int(self.max_v))
        else:
            self.value = round(random.uniform(self.min_v, self.max_v), 3)

    def handle_event(self, event):
        changed = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect and self.rect.inflate(0, 14).collidepoint(event.pos):
                self.dragging = True
                nv = self.x_to_value(event.pos[0])
                if nv != self.value:
                    self.value = nv; changed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                nv = self.x_to_value(event.pos[0])
                if nv != self.value:
                    self.value = nv; changed = True
        return changed

    def draw(self, surf):
        lab = FONT_XS.render(self.label, True, TEXT)
        surf.blit(lab, (self.label_rect.x, self.label_rect.y))
        val = FONT_XS.render(self.fmt(self.value), True, TEXT_GOLD)
        surf.blit(val, (self.label_rect.right - val.get_width(),
                        self.label_rect.y))
        ty = self.rect.y + self.rect.h // 2
        pygame.draw.line(surf, (50, 42, 34),
                         (self.rect.x, ty), (self.rect.right, ty), 4)
        kx = self.value_to_x()
        pygame.draw.line(surf, ACCENT, (self.rect.x, ty), (kx, ty), 4)
        pygame.draw.circle(surf, ACCENT_BRIGHT, (kx, ty), 6)
        pygame.draw.circle(surf, (30, 22, 16), (kx, ty), 6, 2)


# ============================================================================
# Save Dialog
# ============================================================================
class SaveDialog:
    """Modal simples para digitar nome e salvar."""
    def __init__(self):
        self.active = False
        self.text = ""
        self.rect = pygame.Rect(0, 0, 460, 190)
        self.rect.center = (WIDTH // 2, HEIGHT // 2)
        self.input_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_save = None
        self.btn_cancel = None
        self._layout()

    def _layout(self):
        r = self.rect
        self.input_rect = pygame.Rect(r.x + 20, r.y + 70, r.w - 40, 34)
        bw = 130
        by = r.bottom - 50
        self.btn_cancel = pygame.Rect(r.x + 20, by, bw, 32)
        self.btn_save   = pygame.Rect(r.right - 20 - bw, by, bw, 32)

    def open(self, default_name=""):
        self.active = True
        self.text = default_name or ""
        self._layout()

    def close(self):
        self.active = False

    def handle_event(self, event):
        """Retorna: None (nada) | 'save' | 'cancel'."""
        if not self.active:
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "cancel"
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "save"
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable() and len(self.text) < 48:
                    # evita barras e caracteres problemáticos no nome
                    if ch not in '\\/:*?"<>|':
                        self.text += ch
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.btn_cancel.collidepoint(event.pos):
                return "cancel"
            if self.btn_save.collidepoint(event.pos):
                return "save"
            # clique fora fecha
            if not self.rect.collidepoint(event.pos):
                return "cancel"
        return None

    def draw(self, surf):
        if not self.active:
            return
        # escurece o fundo
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surf.blit(overlay, (0, 0))

        r = self.rect
        pygame.draw.rect(surf, PANEL_BG, r, border_radius=8)
        pygame.draw.rect(surf, ACCENT_BRIGHT, r, 2, border_radius=8)

        draw_text(surf, "SALVAR OVERMAP", r.x + 20, r.y + 16, FONT_L, ACCENT_BRIGHT)
        draw_text(surf, "Digite um nome para o arquivo:",
                  r.x + 20, r.y + 48, FONT_S, TEXT_DIM)

        # input
        pygame.draw.rect(surf, (22, 19, 16), self.input_rect, border_radius=4)
        pygame.draw.rect(surf, ACCENT_DARK, self.input_rect, 1, border_radius=4)
        # cursor piscante
        caret = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        shown = self.text + caret
        txt_col = TEXT if self.text else TEXT_DIM
        shown_surf = FONT_M.render(shown if self.text else "nome_do_overmap",
                                   True, txt_col if self.text else (90, 80, 65))
        surf.blit(shown_surf, (self.input_rect.x + 8, self.input_rect.y + 9))

        # botões
        draw_button(surf, self.btn_cancel, "Cancelar  (ESC)", FONT_M)
        draw_button(surf, self.btn_save, "Salvar  (Enter)", FONT_M, primary=True)


# ============================================================================
# Settings Panel
# ============================================================================
class SettingsPanel:
    PANEL_W = SETTINGS_W

    def __init__(self, app):
        self.app = app
        self.visible = False
        self.groups = []
        self.sliders = []
        self.buttons = []
        self.new_map_btn = None
        self.save_btn = None
        self.load_btn = None
        self.panel_rect = pygame.Rect(WIDTH - self.PANEL_W, 0,
                                      self.PANEL_W, HEIGHT)
        self._build()

    def _build(self):
        p = self.app.overmap.params

        def S(key, label, mn, mx, is_int=False, fmt=None):
            return Slider(key, label, mn, mx, p.get(key, DEFAULT_PARAMS[key]),
                          is_int, fmt)

        self.groups = [
            ("TAMANHO", [
                S("w", "Largura", 10, 100, True),
                S("h", "Altura", 8, 60, True),
            ]),
            ("ELEVAÇÃO (noise)", [
                S("elev_scale", "Escala", 3, 25, False, lambda v: f"{v:.1f}"),
                S("elev_octaves", "Oitavas", 1, 6, True),
            ]),
            ("UMIDADE (noise)", [
                S("moist_scale", "Escala", 3, 25, False, lambda v: f"{v:.1f}"),
                S("moist_octaves", "Oitavas", 1, 6, True),
            ]),
            ("LIMIARES — ELEVAÇÃO", [
                S("sea_th", "Mar", 0.05, 0.45),
                S("coast_th", "Costa", 0.15, 0.55),
                S("mountain_th", "Montanha", 0.55, 0.95),
            ]),
            ("LIMIARES — UMIDADE", [
                S("swamp_elev", "Pântano · elev", 0.20, 0.70),
                S("swamp_moist", "Pântano · umi", 0.40, 0.85),
                S("forest_moist", "Floresta · umi", 0.30, 0.80),
                S("desert_moist", "Deserto · umi", 0.05, 0.60),
            ]),
            ("LIMIARES — LATITUDE", [
                S("snow_lat", "Neve (topo)", 0.00, 0.60),
                S("desert_lat", "Deserto (base)", 0.30, 1.00),
                S("lat_jitter", "Ruído latitude", 0.00, 0.35),
            ]),
        ]
        self.sliders = [s for _, grp in self.groups for s in grp]

    def layout(self):
        x = self.panel_rect.x + 16
        w = self.PANEL_W - 32
        y = 62

        self.new_map_btn = pygame.Rect(x, y, w, 36)
        y += 44

        # linha de botões: Salvar / Carregar
        bw2 = (w - 8) // 2
        self.save_btn = pygame.Rect(x, y, bw2, 28)
        self.load_btn = pygame.Rect(x + bw2 + 8, y, bw2, 28)
        y += 36

        for title, grp in self.groups:
            y += 16
            for s in grp:
                s.set_position(x, y, w)
                y += 28
            y += 2
        y += 4

        bw = (w - 8) // 2
        b1 = pygame.Rect(x, y, bw, 28)
        b2 = pygame.Rect(x + bw + 8, y, bw, 28)
        self.buttons = [
            (b1, "Resetar",  self._reset_params),
            (b2, "Aleatório", self._randomize_params),
        ]

    def handle_event(self, event):
        if not self.visible:
            return False
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                          pygame.MOUSEMOTION):
            if not self.panel_rect.collidepoint(event.pos):
                return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.new_map_btn and self.new_map_btn.collidepoint(event.pos):
                self._regen(); return True
            if self.save_btn and self.save_btn.collidepoint(event.pos):
                self.app._open_save_dialog(); return True
            if self.load_btn and self.load_btn.collidepoint(event.pos):
                self.app._load_last(); return True
            for rect, _, cb in self.buttons:
                if rect.collidepoint(event.pos):
                    cb(); return True
        changed = False
        for s in self.sliders:
            if s.handle_event(event):
                changed = True
        if changed:
            self._apply()
            return True
        return False

    def _apply(self):
        for s in self.sliders:
            self.app.overmap.params[s.key] = s.value
        self.app.overmap.regenerate(seed=self.app.overmap.seed)
        self.app._clamp_camera()
        self.app.flash = 0.12

    def _reset_params(self):
        for s in self.sliders:
            s.value = DEFAULT_PARAMS[s.key]
        self._apply()
        self.app._msg("Parâmetros resetados.", SUCCESS)

    def _randomize_params(self):
        for s in self.sliders:
            s.randomize()
        self._apply()
        self.app.overmap.regenerate()
        self.app._clamp_camera()
        self.app._msg("Parâmetros randomizados.", ACCENT)

    def _regen(self):
        self.app.overmap.regenerate()
        self.app._clamp_camera()
        self.app.flash = 0.15
        self.app._msg(f"Novo mapa (seed {self.app.overmap.seed})", SUCCESS)

    def draw(self, surf):
        if not self.visible:
            return
        r = self.panel_rect
        pygame.draw.rect(surf, PANEL_BG, r)
        pygame.draw.line(surf, PANEL_BORDER, (r.x, 0), (r.x, HEIGHT), 2)

        draw_text(surf, "CONFIGURAÇÕES", r.x + 16, 14, FONT_L, ACCENT_BRIGHT)
        draw_text(surf, "TAB fecha · ajustes aplicam em tempo real",
                  r.x + 16, 38, FONT_XS, TEXT_DIM)

        if self.new_map_btn:
            draw_button(surf, self.new_map_btn,
                        "GERAR NOVO MAPA  (ESPAÇO)",
                        FONT_M, primary=True)
        if self.save_btn:
            draw_button(surf, self.save_btn, "Salvar  (B)", FONT_XS)
        if self.load_btn:
            draw_button(surf, self.load_btn, "Carregar  (L)", FONT_XS)

        y = 62 + 44 + 36
        for title, grp in self.groups:
            draw_text(surf, title, r.x + 16, y, FONT_XS, ACCENT)
            y += 16
            for s in grp:
                s.draw(surf)
                y += 28
            y += 2

        for rect, label, _ in self.buttons:
            draw_button(surf, rect, label, FONT_XS)


# ============================================================================
# App
# ============================================================================
class OvermapApp:
    def __init__(self):
        self.running = True
        self.overmap = Overmap()
        self.hover_cell = None
        self.msg = ""
        self.msg_timer = 0.0
        self.msg_color = ACCENT
        self.flash = 0.0

        self.cell = float(BASE_CELL)
        self.camera = [0.0, 0.0]
        self.cam_speed = 480.0

        self.panel = SettingsPanel(self)
        self.panel.layout()
        self.save_dialog = SaveDialog()
        self._recenter()

    # ------------------------------------------------------------------
    def _msg(self, text, color=ACCENT):
        self.msg = text; self.msg_color = color; self.msg_timer = 2.5

    def _avail_area(self):
        w = WIDTH - (self.panel.PANEL_W if self.panel.visible else 0)
        return pygame.Rect(0, 60, w, HEIGHT - 100)

    def _recenter(self):
        area = self._avail_area()
        world_w = self.overmap.w * self.cell
        world_h = self.overmap.h * self.cell
        self.camera[0] = world_w / 2 - area.centerx
        self.camera[1] = world_h / 2 - area.centery

    def _clamp_camera(self):
        area = self._avail_area()
        world_w = self.overmap.w * self.cell
        world_h = self.overmap.h * self.cell
        self.camera[0] = max(-area.w * 0.5, min(world_w - area.w * 0.5,
                                                self.camera[0]))
        self.camera[1] = max(-area.h * 0.5, min(world_h - area.h * 0.5,
                                                self.camera[1]))

    def world_to_screen(self, wx, wy):
        return (wx - self.camera[0], wy - self.camera[1])

    def screen_to_world(self, sx, sy):
        return (sx + self.camera[0], sy + self.camera[1])

    # --- save/load ----------------------------------------------------
    def _open_save_dialog(self):
        # nome sugerido
        default = f"overmap_{self.overmap.seed}"
        self.save_dialog.open(default)

    def _do_save(self):
        name = self.save_dialog.text.strip() or f"overmap_{self.overmap.seed}"
        # sanitiza
        safe = "".join(c for c in name if c not in '\\/:*?"<>|').strip()
        if not safe:
            safe = f"overmap_{self.overmap.seed}"
        fp = os.path.join(EXPORTS_DIR, f"{safe}.json")
        try:
            self.overmap.save(fp)
            self._msg(f"Salvo: {safe}.json", SUCCESS)
        except Exception as ex:
            self._msg(f"Erro: {ex}", DANGER)

    def _load_last(self):
        files = sorted([f for f in os.listdir(EXPORTS_DIR)
                        if f.endswith(".json")])
        if not files:
            self._msg("Nenhum overmap salvo.", DANGER)
            return
        fp = os.path.join(EXPORTS_DIR, files[-1])
        try:
            self.overmap = Overmap.load(fp)
            self.panel._build()
            self.panel.layout()
            self._recenter()
            self._msg(f"Carregado: {files[-1]}", SUCCESS)
        except Exception as ex:
            self._msg(f"Erro: {ex}", DANGER)

    # ------------------------------------------------------------------
    def handle_events(self, events):
        for e in events:
            if e.type == pygame.QUIT:
                self.running = False; return

            # diálogo modal primeiro
            if self.save_dialog.active:
                act = self.save_dialog.handle_event(e)
                if act == "save":
                    self._do_save()
                    self.save_dialog.close()
                elif act == "cancel":
                    self.save_dialog.close()
                continue

            if self.panel.handle_event(e):
                continue

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if self.panel.visible:
                        self.panel.visible = False
                    else:
                        self.running = False
                elif e.key == pygame.K_TAB:
                    self.panel.visible = not self.panel.visible
                    self._clamp_camera()
                elif e.key in (pygame.K_SPACE, pygame.K_r):
                    self.overmap.regenerate()
                    self._clamp_camera()
                    self.flash = 0.2
                    self._msg(f"Novo mapa (seed {self.overmap.seed})", SUCCESS)
                elif e.key == pygame.K_HOME:
                    self._recenter()
                    self._msg("Câmera recentralizada.", ACCENT)
                elif e.key == pygame.K_b:
                    self._open_save_dialog()
                elif e.key == pygame.K_l:
                    self._load_last()

            if e.type == pygame.MOUSEWHEEL:
                if not (self.panel.visible and
                        self.panel.panel_rect.collidepoint(pygame.mouse.get_pos())):
                    self._zoom_at(pygame.mouse.get_pos(), e.y)

            if e.type == pygame.MOUSEMOTION:
                self._update_hover(e.pos)

    # --- zoom --------------------------------------------------------
    def _zoom_at(self, mouse_pos, delta):
        old_cell = self.cell
        factor = 1.15 ** delta
        new_cell = max(6.0, min(64.0, old_cell * factor))
        if abs(new_cell - old_cell) < 0.01:
            return
        wx, wy = self.screen_to_world(mouse_pos[0], mouse_pos[1])
        self.cell = new_cell
        self.camera[0] = wx - mouse_pos[0]
        self.camera[1] = wy - mouse_pos[1]
        self._clamp_camera()

    # --- hover -------------------------------------------------------
    def _update_hover(self, pos):
        if self.panel.visible and self.panel.panel_rect.collidepoint(pos):
            self.hover_cell = None
            return
        if self.save_dialog.active:
            self.hover_cell = None
            return
        wx, wy = self.screen_to_world(pos[0], pos[1])
        gx = int(wx // self.cell)
        gy = int(wy // self.cell)
        if 0 <= gx < self.overmap.w and 0 <= gy < self.overmap.h:
            self.hover_cell = (gx, gy)
        else:
            self.hover_cell = None

    # ------------------------------------------------------------------
    def update(self, dt):
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0: self.msg = ""
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt)

        # não move câmera com diálogo aberto
        if self.save_dialog.active:
            return

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
            self.camera[0] += dx / n * speed * dt
            self.camera[1] += dy / n * speed * dt
            self._clamp_camera()

    # ------------------------------------------------------------------
    def draw(self):
        screen.fill(BG)

        cell = self.cell
        cell_i = int(round(cell))
        world_w = self.overmap.w * cell
        world_h = self.overmap.h * cell
        ox, oy = self.world_to_screen(0, 0)

        x0 = max(0, int((0 - ox) // cell))
        y0 = max(0, int((0 - oy) // cell))
        x1 = min(self.overmap.w, int((WIDTH - ox) // cell) + 1)
        y1 = min(self.overmap.h, int((HEIGHT - oy) // cell) + 1)

        for y in range(y0, y1):
            for x in range(x0, x1):
                b = self.overmap.biomes[y][x]
                rx = ox + x * cell
                ry = oy + y * cell
                pygame.draw.rect(screen, biome_color(b),
                                 (int(rx), int(ry), cell_i + 1, cell_i + 1))

        if cell >= 12:
            grid_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for x in range(x0, x1 + 1):
                rx = int(ox + x * cell)
                pygame.draw.line(grid_surf, (0, 0, 0, 40),
                                 (rx, max(0, int(oy))),
                                 (rx, min(HEIGHT, int(oy + world_h))))
            for y in range(y0, y1 + 1):
                ry = int(oy + y * cell)
                pygame.draw.line(grid_surf, (0, 0, 0, 40),
                                 (max(0, int(ox)), ry),
                                 (min(WIDTH, int(ox + world_w)), ry))
            screen.blit(grid_surf, (0, 0))

        pygame.draw.rect(screen, PANEL_BORDER,
                         (int(ox) - 2, int(oy) - 2,
                          int(world_w) + 4, int(world_h) + 4), 2)

        if self.hover_cell:
            cx, cy = self.hover_cell
            rx = ox + cx * cell
            ry = oy + cy * cell
            pygame.draw.rect(screen, HIGHLIGHT,
                             (int(rx), int(ry), cell_i, cell_i), 2)

        if self.flash > 0:
            a = int(120 * (self.flash / 0.2))
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            s.fill((255, 240, 200, a))
            screen.blit(s, (0, 0))

        draw_text(screen, "OVERMAP GENERATOR", 20, 16, FONT_L, ACCENT_BRIGHT)
        zoom_pct = int(cell / BASE_CELL * 100)
        draw_text(screen,
                  f"seed: {self.overmap.seed}   ·   {self.overmap.w}x{self.overmap.h}"
                  f"   ·   zoom: {zoom_pct}%",
                  20, 42, FONT_M, TEXT_DIM)

        if self.hover_cell:
            cx, cy = self.hover_cell
            b = self.overmap.biome_at(cx, cy)
            info = f"({cx},{cy})  {biome_name(b)}"
            r = FONT_M.render(info, True, HIGHLIGHT)
            bg = pygame.Surface((r.get_width() + 16, r.get_height() + 8),
                                pygame.SRCALPHA)
            bg.fill((0, 0, 0, 200))
            bx, by = 20, HEIGHT - 70
            screen.blit(bg, (bx, by))
            screen.blit(r, (bx + 8, by + 4))

        self._draw_legend()
        self.panel.draw(screen)
        self.save_dialog.draw(screen)

        ctrl = ("TAB settings  ·  ESPAÇO/R novo mapa  ·  WASD câmera (SHIFT rápido)"
                "  ·  Scroll zoom  ·  HOME recentraliza  ·  B salvar  ·  L carregar")
        draw_text(screen, ctrl, WIDTH // 2, HEIGHT - 26, FONT_S, TEXT_DIM,
                  center=True)

        if self.msg:
            r = FONT_M.render(self.msg, True, self.msg_color)
            bg = pygame.Surface((r.get_width() + 20, r.get_height() + 10),
                                pygame.SRCALPHA)
            bg.fill((0, 0, 0, 200))
            x = WIDTH // 2 - bg.get_width() // 2
            y = HEIGHT - 100
            screen.blit(bg, (x, y))
            screen.blit(r, (x + 10, y + 5))

        pygame.display.flip()

    def _draw_legend(self):
        keys = list(BIOMES.keys())
        pad = 10
        sw = 14
        lh = 20
        box_w = 190
        box_h = pad * 2 + len(keys) * lh + 6
        bx = 20
        by = 70
        pygame.draw.rect(screen, PANEL_BG, (bx, by, box_w, box_h),
                         border_radius=6)
        pygame.draw.rect(screen, PANEL_BORDER, (bx, by, box_w, box_h), 1,
                         border_radius=6)

        total = max(1, self.overmap.w * self.overmap.h)
        y = by + pad
        for k in keys:
            pygame.draw.rect(screen, biome_color(k),
                             (bx + pad, y + 2, sw, sw), border_radius=2)
            pygame.draw.rect(screen, (0, 0, 0, 120),
                             (bx + pad, y + 2, sw, sw), 1, border_radius=2)
            draw_text(screen, BIOMES[k]["name"], bx + pad + sw + 8, y,
                      FONT_S, TEXT)
            cnt = self.overmap.counts.get(k, 0)
            pct = int(round(cnt / total * 100))
            ct = FONT_XS.render(f"{pct}%", True, TEXT_DIM)
            screen.blit(ct, (bx + box_w - pad - ct.get_width(),
                             y + 2))
            y += lh

    # ------------------------------------------------------------------
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
    OvermapApp().run()