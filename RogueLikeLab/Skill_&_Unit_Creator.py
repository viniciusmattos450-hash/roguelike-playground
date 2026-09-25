# -*- coding: utf-8 -*-
"""
SkillCreator.py
Criador de Habilidades e Unidades para Roguelike
------------------------------------------------
- Interface em Pygame (1280 x 800)
- Cria / Edita Skills e Unidades
- Gerencia (ver / duplicar / renomear / excluir) Skills e Unidades salvas
- Importa Skills e Unidades colando JSON em texto único (com detecção de tipo)
- Exporta tudo para .json em ./exports/skills e ./exports/units

Campos extras por tipo de skill:
- Invocação  → summon: {unit_name, count, duration}
- Reação     → trigger: string
"""

import os
import re
import json
import pygame

# ============================================================================
# Inicialização
# ============================================================================
pygame.init()
pygame.key.set_repeat(400, 40)
try:
    pygame.scrap.init()
except Exception:
    pass

def get_clipboard_text():
    try:
        import tkinter
        r = tkinter.Tk(); r.withdraw()
        try: text = r.clipboard_get()
        except Exception: text = ""
        r.destroy()
        if text: return text
    except Exception:
        pass
    try:
        pygame.scrap.init()
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        if raw: return raw.decode("utf-8", "ignore").replace("\x00", "")
    except Exception:
        pass
    return ""


WIDTH, HEIGHT = 1280, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Skill & Unit Creator")
clock = pygame.time.Clock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
SKILLS_DIR = os.path.join(EXPORTS_DIR, "skills")
UNITS_DIR = os.path.join(EXPORTS_DIR, "units")
os.makedirs(SKILLS_DIR, exist_ok=True)
os.makedirs(UNITS_DIR, exist_ok=True)

# ============================================================================
# Paleta / Fontes
# ============================================================================
BG          = (24, 26, 34)
PANEL       = (36, 40, 52)
PANEL_REQ   = (42, 46, 66)
PANEL_SPEC  = (46, 40, 60)
PANEL_LIGHT = (55, 62, 80)
ACCENT      = (86, 156, 255)
ACCENT_DARK = (45, 75, 120)
TEXT        = (232, 236, 245)
TEXT_DIM    = (150, 158, 178)
TEXT_HINT   = (170, 180, 210)
INPUT_BG    = (22, 25, 33)
INPUT_ACT   = (34, 46, 68)
BORDER      = (78, 88, 110)
BORDER_REQ  = (120, 140, 200)
BORDER_SPEC = (160, 120, 200)
DANGER      = (205, 75, 75)
SUCCESS     = (72, 185, 125)
WARN        = (230, 175, 70)
OVERLAY     = (0, 0, 0, 170)

FONT_XL = pygame.font.SysFont("consolas,couriernew,dejavusansmono", 24, bold=True)
FONT_L  = pygame.font.SysFont("consolas,couriernew,dejavusansmono", 18, bold=True)
FONT_M  = pygame.font.SysFont("consolas,couriernew,dejavusansmono", 15)
FONT_S  = pygame.font.SysFont("consolas,couriernew,dejavusansmono", 12)

# ============================================================================
# Listas de opções
# ============================================================================
SKILL_TYPES = [
    "Ataque Único", "Ataque Múltiplo", "Buff", "Debuff", "Cura",
    "Suporte", "Invocação", "Passiva", "Reação", "Ultimate",
]

DAMAGE_TYPES = [
    "Nenhum", "Físico", "Fogo", "Gelo", "Elétrico", "Veneno", "Ácido",
    "Terra", "Vento", "Água", "Arcano", "Sagrado", "Sombrio", "Puro", "Verdadeiro",
]

TARGETS = [
    "Inimigo Único", "Todos os Inimigos", "Inimigo Aleatório",
    "Aliado Único", "Todos os Aliados", "Si Mesmo", "Área", "Linha", "Cone",
]

EFFECT_TYPES = [
    "Sangramento", "Veneno", "Queimadura", "Congelamento", "Atordoamento",
    "Paralisia", "Sono", "Silêncio", "Cegueira", "Confusão", "Medo",
    "Provocar", "Lentidão", "Aceleração", "Bufo de Ataque", "Bufo de Defesa",
    "Bufo de Velocidade", "Debuff de Ataque", "Debuff de Defesa",
    "Debuff de Velocidade", "Regeneração HP", "Regeneração Mana",
    "Regeneração Stamina", "Dano por Turno", "Escudo", "Invencibilidade",
    "Reflexo", "Sanguessuga", "Roubo de Vida", "Maldição", "Bênção",
    "Chance de Acerto +", "Chance de Esquiva +", "Crítico +", "Outro",
]

REACTION_TRIGGERS = [
    "Ao ser atacado",
    "Ao acertar ataque",
    "Ao morrer",
    "Ao iniciar turno",
    "Quando HP < 50%",
    "Quando HP < 25%",
    "Ao usar skill",
    "Ao ser curado",
]

SKILL_FILTERS = ["Todos"] + SKILL_TYPES

# ============================================================================
# Helpers
# ============================================================================
def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s-]+", "_", s)
    return s or "sem_nome"


def draw_text(surf, text, x, y, font=FONT_M, color=TEXT, center_x=False):
    r = font.render(str(text), True, color)
    if center_x:
        surf.blit(r, (x - r.get_width() // 2, y))
    else:
        surf.blit(r, (x, y))
    return r


def draw_panel(surf, rect, color=PANEL, radius=10, border=True, border_color=None):
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border_color or BORDER, rect, 1, border_radius=radius)


def fit_text(text, font, max_w):
    if font.size(text)[0] <= max_w:
        return text
    t = text
    while t and font.size("..." + t)[0] > max_w:
        t = t[1:]
    return "..." + t


def wrap_text_lines(text, font, max_w):
    result = []
    for line in text.split("\n"):
        if not line:
            result.append("")
            continue
        remaining = line
        while remaining:
            if font.size(remaining)[0] <= max_w:
                result.append(remaining)
                break
            lo, hi = 1, len(remaining)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if font.size(remaining[:mid])[0] <= max_w:
                    lo = mid
                else:
                    hi = mid - 1
            result.append(remaining[:lo])
            remaining = remaining[lo:]
    return result


def load_json_files(directory):
    out = []
    if os.path.isdir(directory):
        for fn in sorted(os.listdir(directory)):
            if not fn.endswith(".json"):
                continue
            path = os.path.join(directory, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                out.append({"path": path, "filename": fn, "data": data})
            except Exception:
                pass
    return out


def parse_json_items(raw):
    raw = raw.strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [p for p in parsed if isinstance(p, dict)]
        if isinstance(parsed, dict):
            for key in ("items", "data", "skills", "units", "list"):
                if key in parsed and isinstance(parsed[key], list):
                    return [p for p in parsed[key] if isinstance(p, dict)]
            return [parsed]
    except Exception:
        pass
    items = []
    depth = 0
    start = None
    in_string = False
    escape = False
    for i, ch in enumerate(raw):
        if escape:
            escape = False; continue
        if in_string:
            if ch == '\\': escape = True
            elif ch == '"': in_string = False
            continue
        if ch == '"': in_string = True
        elif ch == '{':
            if depth == 0: start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                snippet = raw[start:i + 1]
                try:
                    obj = json.loads(snippet)
                    if isinstance(obj, dict): items.append(obj)
                except Exception: pass
                start = None
    return items


def detect_item_kind(item):
    if not isinstance(item, dict):
        return "unknown"
    skill_score = 0
    unit_score = 0
    if isinstance(item.get("damage"), dict):        skill_score += 2
    if isinstance(item.get("cost"), dict):          skill_score += 2
    if isinstance(item.get("effects"), list):       skill_score += 2
    if isinstance(item.get("requirements"), dict):  skill_score += 2
    if isinstance(item.get("resources"), dict):     unit_score += 2
    if isinstance(item.get("combat"), dict):        unit_score += 2
    if isinstance(item.get("attributes"), dict):    unit_score += 2
    if isinstance(item.get("resistances"), dict):   unit_score += 2
    if "cooldown" in item:             skill_score += 1
    if "target" in item:               skill_score += 1
    if "battle_description" in item:   skill_score += 1
    if isinstance(item.get("skills"), list):    unit_score += 1
    if "race" in item and item.get("race") and not isinstance(item.get("requirements"), dict):
        unit_score += 1
    if "level" in item and not isinstance(item.get("requirements"), dict):
        unit_score += 1
    id_ = str(item.get("id", "")).lower()
    if id_.startswith("skill_"): skill_score += 3
    if id_.startswith("unit_"):  unit_score += 3
    if skill_score == 0 and unit_score == 0: return "unknown"
    if skill_score == unit_score: return "ambiguous"
    return "skill" if skill_score > unit_score else "unit"


# ============================================================================
# Widgets
# ============================================================================
class TextInput:
    def __init__(self, x, y, w, h, label="", placeholder="", text=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.placeholder = placeholder
        self.text = text
        self.active = False
        self._blink = 0.0
        self._show_cursor = True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.active = True
                return True
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self.active = False
            elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                self.text += get_clipboard_text()
            else:
                ch = event.unicode
                if ch and ch.isprintable():
                    self.text += ch
            return True
        return False

    def draw(self, surf, dt=0.0):
        if self.label:
            draw_text(surf, self.label, self.rect.x, self.rect.y - 15, FONT_S, TEXT_DIM)
        bg = INPUT_ACT if self.active else INPUT_BG
        pygame.draw.rect(surf, bg, self.rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT if self.active else BORDER, self.rect, 1, border_radius=5)
        shown = self.text if self.text else self.placeholder
        col = TEXT if self.text else TEXT_DIM
        shown = fit_text(shown, FONT_M, self.rect.w - 16)
        r = FONT_M.render(shown, True, col)
        surf.blit(r, (self.rect.x + 8, self.rect.y + (self.rect.h - r.get_height()) // 2))
        if self.active:
            self._blink += dt
            if self._blink > 0.5:
                self._blink = 0.0
                self._show_cursor = not self._show_cursor
            if self._show_cursor:
                full = fit_text(self.text, FONT_M, self.rect.w - 16)
                cx = self.rect.x + 8 + FONT_M.size(full)[0] + 2
                pygame.draw.line(surf, TEXT, (cx, self.rect.y + 6),
                                 (cx, self.rect.y + self.rect.h - 6), 2)


class TextArea:
    def __init__(self, x, y, w, h, label="", placeholder=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.placeholder = placeholder
        self.text = ""
        self.active = False
        self.scroll = 0
        self._blink = 0.0
        self._show_cursor = True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.active = True
                return True
        if event.type == pygame.MOUSEWHEEL and self.active:
            mx, my = pygame.mouse.get_pos()
            if self.rect.collidepoint(mx, my):
                self.scroll = max(0, self.scroll - event.y * 30)
                return True
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.text += "\n"
            elif event.key == pygame.K_TAB:
                self.active = False
            elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                self.text += get_clipboard_text()
            else:
                ch = event.unicode
                if ch and ch.isprintable():
                    self.text += ch
            return True
        return False

    def draw(self, surf, dt=0.0):
        if self.label:
            draw_text(surf, self.label, self.rect.x, self.rect.y - 15, FONT_S, TEXT_DIM)
        bg = INPUT_ACT if self.active else INPUT_BG
        pygame.draw.rect(surf, bg, self.rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT if self.active else BORDER, self.rect, 1, border_radius=5)
        line_h = FONT_M.get_height() + 2
        max_w = self.rect.w - 16
        if self.text:
            visual = wrap_text_lines(self.text, FONT_M, max_w)
        else:
            visual = [self.placeholder] if self.placeholder else []
        total_h = len(visual) * line_h
        view_h = self.rect.h - 8
        if total_h > view_h: self.scroll = max(0, total_h - view_h)
        else: self.scroll = 0
        old_clip = surf.get_clip()
        surf.set_clip(self.rect.inflate(-4, -4))
        y = self.rect.y + 4 - self.scroll
        for i, vl in enumerate(visual):
            if y + line_h > self.rect.y and y < self.rect.bottom:
                col = TEXT_DIM if (not self.text) else TEXT
                r = FONT_M.render(vl, True, col)
                surf.blit(r, (self.rect.x + 8, y))
            y += line_h
        if self.active:
            self._blink += dt
            if self._blink > 0.5:
                self._blink = 0.0
                self._show_cursor = not self._show_cursor
            if self._show_cursor and visual:
                last = visual[-1]
                cx = self.rect.x + 8 + FONT_M.size(last)[0] + 2
                cy = self.rect.y + 4 + (len(visual) - 1) * line_h - self.scroll
                if cy + line_h > self.rect.y and cy < self.rect.bottom:
                    pygame.draw.line(surf, TEXT, (cx, cy + 2),
                                     (cx, cy + line_h - 4), 2)
        surf.set_clip(old_clip)
        if total_h > view_h:
            bar_x = self.rect.right - 6
            bar_h = max(20, int(view_h * view_h / total_h))
            max_scroll = total_h - view_h
            bar_y = self.rect.y + 4 + int((view_h - bar_h) * self.scroll / max(1, max_scroll))
            pygame.draw.rect(surf, ACCENT, (bar_x, bar_y, 3, bar_h), border_radius=2)


class Button:
    def __init__(self, x, y, w, h, text, callback, color=ACCENT, font=FONT_M):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.callback = callback
        self.color = color
        self.font = font
        self.hover = False
        self.enabled = True

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.enabled and self.rect.collidepoint(event.pos):
                self.callback()
                return True
        return False

    def draw(self, surf, dt=0.0):
        base = self.color if self.enabled else (70, 74, 86)
        c = tuple(min(255, v + 35) for v in base) if self.hover and self.enabled else base
        pygame.draw.rect(surf, c, self.rect, border_radius=6)
        pygame.draw.rect(surf, (255, 255, 255, 25), self.rect, 1, border_radius=6)
        r = self.font.render(self.text, True, (255, 255, 255))
        surf.blit(r, (self.rect.centerx - r.get_width() // 2,
                      self.rect.centery - r.get_height() // 2))


class ToggleButton(Button):
    def __init__(self, x, y, w, h, text, callback=None):
        super().__init__(x, y, w, h, text, callback, color=(60, 66, 82), font=FONT_S)
        self.selected = False

    def draw(self, surf, dt=0.0):
        base = SUCCESS if self.selected else (58, 64, 80)
        c = tuple(min(255, v + 30) for v in base) if self.hover else base
        pygame.draw.rect(surf, c, self.rect, border_radius=6)
        pygame.draw.rect(surf, BORDER, self.rect, 1, border_radius=6)
        r = self.font.render(self.text, True, (255, 255, 255))
        surf.blit(r, (self.rect.centerx - r.get_width() // 2,
                      self.rect.centery - r.get_height() // 2))


class Dropdown:
    MAX_VISIBLE = 6

    def __init__(self, x, y, w, h, label, options, index=0):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.options = list(options) if options else [""]
        self.index = max(0, min(index, len(self.options) - 1))
        self.open = False
        self.scroll = 0

    @property
    def value(self):
        return self.options[self.index] if self.options else ""

    def list_geometry(self):
        item_h = self.rect.h
        visible = min(len(self.options), self.MAX_VISIBLE)
        h = visible * item_h
        y = self.rect.y + self.rect.h
        if y + h > HEIGHT - 10:
            y = max(10, self.rect.y - h)
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
                self.scroll = max(0, min(max_scroll, self.scroll - event.y))
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.open:
                lr = self.list_rect()
                if lr.collidepoint(event.pos):
                    _, _, item_h = self.list_geometry()
                    idx = self.scroll + (event.pos[1] - lr.y) // item_h
                    if 0 <= idx < len(self.options):
                        self.index = idx
                    self.open = False
                    return True
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
                if self.open:
                    self.scroll = max(0, min(self.index, max(0, len(self.options) - self.MAX_VISIBLE)))
                return True
        return False

    def draw(self, surf, dt=0.0):
        if self.label:
            draw_text(surf, self.label, self.rect.x, self.rect.y - 15, FONT_S, TEXT_DIM)
        pygame.draw.rect(surf, INPUT_BG, self.rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT if self.open else BORDER, self.rect, 1, border_radius=5)
        txt = fit_text(self.value, FONT_M, self.rect.w - 32)
        r = FONT_M.render(txt, True, TEXT)
        surf.blit(r, (self.rect.x + 8, self.rect.y + (self.rect.h - r.get_height()) // 2))
        ax, ay = self.rect.right - 15, self.rect.centery
        pygame.draw.polygon(surf, TEXT_DIM, [(ax - 5, ay - 2), (ax + 5, ay - 2), (ax, ay + 4)])

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
            r = pygame.Rect(lr.x, lr.y + i * item_h, lr.w, item_h)
            if r.collidepoint(mx, my):
                pygame.draw.rect(surf, PANEL_LIGHT, r)
            if idx == self.index:
                pygame.draw.rect(surf, ACCENT_DARK, r)
            t = fit_text(self.options[idx], FONT_M, r.w - 16)
            tr = FONT_M.render(t, True, TEXT)
            surf.blit(tr, (r.x + 8, r.y + (r.h - tr.get_height()) // 2))
        if len(self.options) > self.MAX_VISIBLE:
            bar_x = lr.right - 5
            total = len(self.options)
            bar_h = max(18, int(h * visible / total))
            bar_y = lr.y + int((h - bar_h) * self.scroll / max(1, total - visible))
            pygame.draw.rect(surf, ACCENT, (bar_x, bar_y, 3, bar_h), border_radius=2)


# ============================================================================
# Cena base
# ============================================================================
class Scene:
    def __init__(self, app):
        self.app = app
        self.all_widgets = []
        self.all_inputs = []
        self.all_dropdowns = []

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.QUIT:
                self.app.running = False
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_scene(MenuScene(self.app))
                return
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                in_list = any(d.open and d.list_rect().collidepoint(e.pos) for d in self.all_dropdowns)
                if in_list:
                    for d in self.all_dropdowns:
                        if d.handle_event(e): break
                    continue
                for d in self.all_dropdowns:
                    if not d.rect.collidepoint(e.pos):
                        d.open = False
                for i in self.all_inputs:
                    if not i.rect.collidepoint(e.pos):
                        i.active = False
            for w in self.all_widgets:
                w.handle_event(e)

    def update(self, dt): pass
    def draw(self, surf, dt):
        for w in self.all_widgets: w.draw(surf, dt)
        for d in self.all_dropdowns:
            if d.open: d.draw_list(surf)


# ============================================================================
# Menu
# ============================================================================
class MenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        bw, bh = 380, 56
        self.buttons = [
            Button(240, 240, bw, bh, "CRIAR HABILIDADES",
                   lambda: app.change_scene(SkillCreatorScene(app)), ACCENT),
            Button(660, 240, bw, bh, "CRIAR UNIDADES",
                   lambda: app.change_scene(UnitCreatorScene(app)), (95, 130, 220)),
            Button(240, 310, bw, bh, "GERENCIAR HABILIDADES",
                   lambda: app.change_scene(SkillManagerScene(app)), (95, 130, 220)),
            Button(660, 310, bw, bh, "GERENCIAR UNIDADES",
                   lambda: app.change_scene(UnitManagerScene(app)), (95, 130, 220)),
            Button(440, 390, 400, bh, "IMPORTAR DADOS (JSON)",
                   lambda: app.change_scene(ImportScene(app)), SUCCESS),
            Button(540, 460, 200, bh, "SAIR",
                   lambda: setattr(app, "running", False), DANGER),
        ]
        self.all_widgets = list(self.buttons)

    def draw(self, surf, dt):
        surf.fill(BG)
        for i in range(0, WIDTH, 60):
            pygame.draw.line(surf, (32, 36, 46), (i, 0), (i, HEIGHT))
        for j in range(0, HEIGHT, 60):
            pygame.draw.line(surf, (32, 36, 46), (0, j), (WIDTH, j))
        draw_text(surf, "CRIADOR DE HABILIDADES E UNIDADES", WIDTH // 2, 100, FONT_XL, TEXT, center_x=True)
        draw_text(surf, "para RPG / Roguelike", WIDTH // 2, 140, FONT_L, TEXT_DIM, center_x=True)
        draw_text(surf, "Arquivos .json salvos em:", WIDTH // 2, 600, FONT_S, TEXT_DIM, center_x=True)
        draw_text(surf, SKILLS_DIR, WIDTH // 2, 622, FONT_S, ACCENT, center_x=True)
        draw_text(surf, UNITS_DIR, WIDTH // 2, 642, FONT_S, ACCENT, center_x=True)
        draw_text(surf, "ESC = voltar   |   Clique nos campos para digitar",
                  WIDTH // 2, HEIGHT - 30, FONT_S, TEXT_DIM, center_x=True)
        for w in self.all_widgets: w.draw(surf, dt)


# ============================================================================
# Linha de Efeito
# ============================================================================
class EffectRow:
    def __init__(self, on_remove):
        self.on_remove = on_remove
        h = 32
        self.type_dd   = Dropdown(0, 0, 190, h, "", EFFECT_TYPES, 0)
        self.value_in  = TextInput(0, 0, 90, h, "", "0", "0")
        self.dur_in    = TextInput(0, 0, 90, h, "", "turnos", "3")
        self.cond_in   = TextInput(0, 0, 620, h, "", "ex: HP < 50%", "")
        self.chance_in = TextInput(0, 0, 80, h, "", "%", "100")
        self.remove_btn = Button(0, 0, 40, h, "X", lambda: self.on_remove(self), DANGER, font=FONT_S)
        self.widgets = [self.type_dd, self.value_in, self.dur_in,
                        self.cond_in, self.chance_in, self.remove_btn]
        self.inputs = [self.value_in, self.dur_in, self.cond_in, self.chance_in]
        self.dropdowns = [self.type_dd]

    def set_y(self, y):
        self.type_dd.rect.topleft    = (20, y)
        self.value_in.rect.topleft   = (225, y)
        self.dur_in.rect.topleft     = (330, y)
        self.cond_in.rect.topleft    = (435, y)
        self.chance_in.rect.topleft  = (1075, y)
        self.remove_btn.rect.topleft = (1175, y)

    def to_dict(self):
        def as_int(s, default=0):
            try: return int(float(s))
            except Exception: return default
        return {
            "type": self.type_dd.value,
            "value": as_int(self.value_in.text, 0),
            "duration": as_int(self.dur_in.text, 0),
            "condition": self.cond_in.text.strip(),
            "chance": as_int(self.chance_in.text, 100),
        }

    def load_from(self, data):
        t = data.get("type", EFFECT_TYPES[0])
        self.type_dd.index = EFFECT_TYPES.index(t) if t in EFFECT_TYPES else 0
        self.value_in.text = str(data.get("value", 0))
        self.dur_in.text = str(data.get("duration", 0))
        self.cond_in.text = data.get("condition", "")
        self.chance_in.text = str(data.get("chance", 100))


# ============================================================================
# Cena: Skill Creator  (layout reorganizado)
# ============================================================================
class SkillCreatorScene(Scene):
    # Layout do painel de efeitos
    EFFECTS_START_Y = 558
    EFFECT_ROW_H = 32
    MAX_EFFECTS = 5

    def __init__(self, app, go_back_factory=None, existing_data=None):
        super().__init__(app)
        self.go_back_factory = go_back_factory or (lambda: MenuScene(app))
        self.effects = []
        self.message = ""
        self.message_color = SUCCESS
        self.message_timer = 0.0
        self.editing_name = existing_data.get("name", "") if existing_data else ""

        self.static_inputs = []
        self.static_dropdowns = []
        self.static_widgets = []

        def add_input(x, y, w, h, label, ph="", text=""):
            i = TextInput(x, y, w, h, label, ph, text)
            self.static_inputs.append(i); self.static_widgets.append(i); return i

        def add_dd(x, y, w, h, label, options, idx=0):
            d = Dropdown(x, y, w, h, label, options, idx)
            self.static_dropdowns.append(d); self.static_widgets.append(d); return d

        # ---- Linha 1 (y=72): Identificação ----
        self.in_name  = add_input(20, 72, 380, 36, "NOME DA HABILIDADE", "ex: Corte Flamejante")
        self.in_desc  = add_input(420, 72, 400, 36, "DESCRIÇÃO", "ex: Um corte envolto em chamas...")
        self.in_bdesc = add_input(840, 72, 420, 36, "DESCRIÇÃO EM BATALHA", "ex: Queima o inimigo!")

        # ---- Linha 2 (y=157): Classificação ----
        self.dd_type   = add_dd(20, 157, 220, 36, "TIPO DE HABILIDADE", SKILL_TYPES, 0)
        self.dd_dmg    = add_dd(260, 157, 220, 36, "TIPO DE DANO", DAMAGE_TYPES, 1)
        self.dd_target = add_dd(500, 157, 220, 36, "ALVO", TARGETS, 0)
        self.in_hits   = add_input(740, 157, 130, 36, "Nº DE GOLPES", "1", "1")
        self.in_acc    = add_input(890, 157, 160, 36, "ACERTO %", "100", "100")

        # ---- Linha 3 (y=242): Números ----
        self.in_dmin   = add_input(20, 242, 140, 36, "DANO MÍN", "0", "0")
        self.in_dmax   = add_input(180, 242, 140, 36, "DANO MÁX", "0", "0")
        self.in_mana   = add_input(340, 242, 140, 36, "CUSTO MANA", "0", "0")
        self.in_stam   = add_input(500, 242, 140, 36, "CUSTO STAMINA", "0", "0")
        self.in_cd     = add_input(660, 242, 140, 36, "COOLDOWN (turnos)", "0", "0")
        self.in_dur    = add_input(820, 242, 140, 36, "DURAÇÃO (turnos)", "0", "0")
        self.in_range  = add_input(980, 242, 140, 36, "ALCANCE (grid)", "1", "1")

        # ---- Linha 4 (y=345): Requisitos ----
        self.in_lvl    = add_input(20, 345, 200, 36, "NÍVEL MÍNIMO", "1", "1")
        self.in_class  = add_input(240, 345, 380, 36, "CLASSE (vazio = todos)", "todos", "")
        self.in_race   = add_input(640, 345, 380, 36, "RAÇA (vazio = todos)", "todos", "")

        # Tags (dentro do painel de requisitos, linha de baixo)
        self.in_tags   = add_input(20, 388, 1240, 22, "TAGS (separadas por vírgula)",
                                   "fogo, corte, melee", "")

        # ---- Linha 5 (y=470): ESPECIAIS ----
        unit_names = self._load_unit_names()
        self.summon_unit_dd = add_dd(20, 470, 320, 30, "UNIDADE INVOCADA",
                                     unit_names, 0)
        self.summon_count_in = add_input(350, 470, 80, 30, "QTD", "1", "1")
        self.summon_duration_in = add_input(440, 470, 100, 30, "DURAÇÃO", "0", "0")
        self.trigger_dd = add_dd(560, 470, 700, 30, "GATILHO (só Reação)",
                                 REACTION_TRIGGERS, 0)

        # ---- Botões ----
        self.btn_back   = Button(20, 730, 160, 42, "VOLTAR",
                                 lambda: app.change_scene(self.go_back_factory()), (90, 90, 110))
        self.btn_add    = Button(190, 730, 200, 42, "+ ADICIONAR EFEITO", self.add_effect, ACCENT)
        self.btn_clear  = Button(400, 730, 120, 42, "LIMPAR", self.clear_all, (90, 90, 110))
        self.btn_save   = Button(1000, 727, 260, 48, "SALVAR SKILL (.JSON)", self.save_skill, SUCCESS)
        self.static_widgets += [self.btn_back, self.btn_add, self.btn_clear, self.btn_save]

        if existing_data:
            self.load_from_data(existing_data)
        else:
            self.add_effect(silent=True)
            self.rebuild()

    def _load_unit_names(self):
        names = ["(nenhuma)"]
        for u in load_json_files(UNITS_DIR):
            n = u["data"].get("name", "")
            if n and n not in names:
                names.append(n)
        return names

    def rebuild(self):
        self.all_widgets = list(self.static_widgets)
        self.all_inputs = list(self.static_inputs)
        self.all_dropdowns = list(self.static_dropdowns)
        for i, row in enumerate(self.effects):
            row.set_y(self.EFFECTS_START_Y + i * self.EFFECT_ROW_H)
            self.all_widgets.extend(row.widgets)
            self.all_inputs.extend(row.inputs)
            self.all_dropdowns.extend(row.dropdowns)

    def add_effect(self, silent=False):
        if len(self.effects) >= self.MAX_EFFECTS:
            if not silent:
                self.show_message("Máximo de %d efeitos atingido." % self.MAX_EFFECTS, WARN)
            return
        self.effects.append(EffectRow(self.remove_effect))
        self.rebuild()

    def remove_effect(self, row):
        if row in self.effects:
            self.effects.remove(row)
        self.rebuild()

    def clear_all(self):
        self.effects.clear()
        self.rebuild()
        self.show_message("Efeitos limpos.", TEXT_DIM)

    def show_message(self, msg, color=SUCCESS):
        self.message = msg; self.message_color = color; self.message_timer = 3.5

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0: self.message = ""

    def load_from_data(self, data):
        self.in_name.text = data.get("name", "")
        self.in_desc.text = data.get("description", "")
        self.in_bdesc.text = data.get("battle_description", "")

        st = data.get("type", SKILL_TYPES[0])
        self.dd_type.index = SKILL_TYPES.index(st) if st in SKILL_TYPES else 0
        dmg = data.get("damage", {})
        dt_ = dmg.get("type", DAMAGE_TYPES[0])
        self.dd_dmg.index = DAMAGE_TYPES.index(dt_) if dt_ in DAMAGE_TYPES else 0
        tg = data.get("target", TARGETS[0])
        self.dd_target.index = TARGETS.index(tg) if tg in TARGETS else 0

        self.in_dmin.text = str(dmg.get("min", 0))
        self.in_dmax.text = str(dmg.get("max", 0))
        self.in_hits.text = str(dmg.get("hits", 1))
        self.in_acc.text = str(dmg.get("accuracy", 100))

        cost = data.get("cost", {})
        self.in_mana.text = str(cost.get("mana", 0))
        self.in_stam.text = str(cost.get("stamina", 0))

        self.in_cd.text = str(data.get("cooldown", 0))
        self.in_dur.text = str(data.get("duration", 0))
        self.in_range.text = str(data.get("range", 1))
        self.in_tags.text = ", ".join(data.get("tags", []))

        req = data.get("requirements", {})
        self.in_lvl.text = str(req.get("level", 1))
        self.in_class.text = req.get("class", "")
        self.in_race.text = req.get("race", "")

        summon = data.get("summon") or {}
        sn = summon.get("unit_name", "")
        if sn and sn in self.summon_unit_dd.options:
            self.summon_unit_dd.index = self.summon_unit_dd.options.index(sn)
        else:
            self.summon_unit_dd.index = 0
        self.summon_count_in.text = str(summon.get("count", 1))
        self.summon_duration_in.text = str(summon.get("duration", 0))

        trig = data.get("trigger", "")
        if trig and trig in REACTION_TRIGGERS:
            self.trigger_dd.index = REACTION_TRIGGERS.index(trig)
        else:
            self.trigger_dd.index = 0

        self.effects = []
        for e in data.get("effects", []):
            row = EffectRow(self.remove_effect)
            row.load_from(e)
            self.effects.append(row)
        if not self.effects:
            self.effects.append(EffectRow(self.remove_effect))
        self.rebuild()

    def save_skill(self):
        name = self.in_name.text.strip()
        if not name:
            self.show_message("Digite um nome para a habilidade!", DANGER)
            return

        def as_int(s, default=0):
            try: return int(float(s))
            except Exception: return default

        def as_float(s, default=0.0):
            try: return float(s)
            except Exception: return default

        cls = self.in_class.text.strip()
        race = self.in_race.text.strip()

        data = {
            "id": "skill_" + slugify(name),
            "name": name,
            "description": self.in_desc.text.strip(),
            "battle_description": self.in_bdesc.text.strip(),
            "type": self.dd_type.value,
            "target": self.dd_target.value,
            "tags": [t.strip() for t in self.in_tags.text.split(",") if t.strip()],
            "damage": {
                "min": as_int(self.in_dmin.text, 0),
                "max": as_int(self.in_dmax.text, 0),
                "type": self.dd_dmg.value,
                "hits": max(1, as_int(self.in_hits.text, 1)),
                "accuracy": as_float(self.in_acc.text, 100.0),
            },
            "cost": {
                "mana": as_int(self.in_mana.text, 0),
                "stamina": as_int(self.in_stam.text, 0),
            },
            "cooldown": as_int(self.in_cd.text, 0),
            "duration": as_int(self.in_dur.text, 0),
            "range": as_int(self.in_range.text, 1),
            "effects": [e.to_dict() for e in self.effects],
            "requirements": {
                "level": as_int(self.in_lvl.text, 1),
                "class": cls,
                "race": race,
                "all": (cls == "" and race == ""),
            },
        }

        if self.dd_type.value == "Invocação":
            unit_name = self.summon_unit_dd.value
            if unit_name == "(nenhuma)": unit_name = ""
            data["summon"] = {
                "unit_name": unit_name,
                "count": max(1, as_int(self.summon_count_in.text, 1)),
                "duration": max(0, as_int(self.summon_duration_in.text, 0)),
            }

        if self.dd_type.value == "Reação":
            data["trigger"] = self.trigger_dd.value

        slug = slugify(name)
        path = os.path.join(SKILLS_DIR, slug + ".json")
        if self.editing_name and slugify(self.editing_name) != slug:
            old = os.path.join(SKILLS_DIR, slugify(self.editing_name) + ".json")
            if os.path.exists(old):
                try: os.remove(old)
                except Exception: pass

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.editing_name = name
            self.show_message("Salvo em: " + os.path.relpath(path, BASE_DIR), SUCCESS)
        except Exception as ex:
            self.show_message("Erro ao salvar: " + str(ex), DANGER)

    def draw(self, surf, dt):
        surf.fill(BG)
        title = "EDITAR HABILIDADE" if self.editing_name else "CRIADOR DE HABILIDADES"
        draw_text(surf, title, 20, 15, FONT_XL, TEXT)
        draw_text(surf, "ESC = menu", WIDTH - 110, 22, FONT_S, TEXT_DIM)

        # ---- Painéis (sem sobreposição) ----
        draw_panel(surf, pygame.Rect(10, 45,  WIDTH - 20, 80))                           # 45-125   Identificação
        draw_panel(surf, pygame.Rect(10, 130, WIDTH - 20, 80))                           # 130-210  Classificação
        draw_panel(surf, pygame.Rect(10, 215, WIDTH - 20, 80))                           # 215-295  Números
        draw_panel(surf, pygame.Rect(10, 300, WIDTH - 20, 125),
                   color=PANEL_REQ, border_color=BORDER_REQ)                             # 300-425  Requisitos + Tags
        draw_panel(surf, pygame.Rect(10, 430, WIDTH - 20, 80),
                   color=PANEL_SPEC, border_color=BORDER_SPEC)                           # 430-510  Especiais
        draw_panel(surf, pygame.Rect(10, 515, WIDTH - 20, 205))                          # 515-720  Efeitos

        # ---- Cabeçalhos (cada um no seu painel) ----
        draw_text(surf, "REQUISITOS PARA USAR  (deixe CLASSE e RAÇA em branco para 'todos')",
                  20, 307, FONT_S, TEXT_HINT)
        draw_text(surf, "ESPECIAIS  —  preencha só se o TIPO for 'Invocação' ou 'Reação'",
                  20, 437, FONT_S, TEXT_HINT)
        draw_text(surf, "EFEITOS / STATUS APLICADOS", 20, 522, FONT_L, ACCENT)

        headers = [("TIPO", 20), ("VALOR", 225), ("DURAÇÃO", 330),
                   ("CONDIÇÃO (opcional)", 435), ("CHANCE %", 1075)]
        for text, x in headers:
            draw_text(surf, text, x, 542, FONT_S, TEXT_DIM)

        for w in self.all_widgets:
            w.draw(surf, dt)
        for d in self.all_dropdowns:
            if d.open:
                d.draw_list(surf)

        draw_text(surf, "Efeitos: %d/%d" % (len(self.effects), self.MAX_EFFECTS),
                  530, 742, FONT_S, TEXT_DIM)
        if self.message:
            r = FONT_M.render(self.message, True, self.message_color)
            surf.blit(r, (WIDTH - 20 - r.get_width(), 742))


# ============================================================================
# Cena: Unit Creator
# ============================================================================
class UnitCreatorScene(Scene):
    SKILLS_PER_PAGE = 18
    SKILL_COLS      = 6
    SKILL_ROWS      = 3
    SKILL_CHIP_W    = 200
    SKILL_CHIP_H    = 24
    SKILLS_AREA_X   = 20
    SKILLS_AREA_Y   = 628

    def __init__(self, app, go_back_factory=None, existing_data=None):
        super().__init__(app)
        self.go_back_factory = go_back_factory or (lambda: MenuScene(app))
        self.fields = {}
        self.dropdowns = []
        self.skill_buttons = []
        self.message = ""
        self.message_color = SUCCESS
        self.message_timer = 0.0
        self.editing_name = existing_data.get("name", "") if existing_data else ""
        self.all_skills = []
        self.filtered_skills = []
        self.total_filtered = 0
        self.skill_page = 0
        self.selected_skills = set()
        self._last_search_text = ""
        self._last_filter_index = 0

        self._create_fields()

        self.skill_search = TextInput(20, 600, 620, 26, "", "Buscar por nome...")
        self.skill_filter_dd = Dropdown(660, 600, 380, 26, "", SKILL_FILTERS, 0)
        self.btn_prev = Button(1060, 708, 90, 28, "◀ ANT", self._prev_page,
                               color=(95, 130, 220), font=FONT_S)
        self.btn_next = Button(1160, 708, 100, 28, "PRÓX ▶", self._next_page,
                               color=(95, 130, 220), font=FONT_S)
        self.btn_clear_search = Button(1010, 600, 60, 26, "X", self._clear_search,
                                       color=(120, 90, 90), font=FONT_S)

        self.btn_back   = Button(20, 750, 160, 42, "VOLTAR",
                                 lambda: app.change_scene(self.go_back_factory()), (90, 90, 110))
        self.btn_reload = Button(200, 750, 200, 42, "RECARREGAR SKILLS",
                                 self.load_skill_chips, ACCENT)
        self.btn_save   = Button(1000, 747, 260, 48, "SALVAR UNIDADE (.JSON)",
                                 self.save_unit, SUCCESS)

        self.static_widgets = list(self.fields.values()) + self.dropdowns + [
            self.skill_search, self.skill_filter_dd,
            self.btn_prev, self.btn_next, self.btn_clear_search,
            self.btn_back, self.btn_reload, self.btn_save,
        ]

        self.load_skill_chips()
        if existing_data:
            self.load_from_data(existing_data)

    def _create_fields(self):
        def f(key, x, y, w, label, ph="", text=""):
            inp = TextInput(x, y, w, 36, label, ph, text)
            self.fields[key] = inp
            return inp
        f("name",  20, 70, 400, "NOME", "ex: Goblin Batedor", "")
        f("race", 440, 70, 260, "RAÇA", "ex: Goblin", "")
        f("class", 720, 70, 260, "CLASSE", "ex: Ladino", "")
        f("level", 1000, 70, 260, "NÍVEL", "1", "1")
        f("desc",   20, 135, 1240, "DESCRIÇÃO", "ex: Um goblin ágil que ataca em bandos...", "")
        f("hp",        20, 220, 190, "HP MÁXIMO", "100", "100")
        f("stamina",  230, 220, 190, "STAMINA MÁX", "50", "50")
        f("mana",     440, 220, 190, "MANA MÁX", "0", "0")
        f("hp_regen", 650, 220, 190, "REGEN HP/TURNO", "0", "0")
        f("mp_regen", 860, 220, 190, "REGEN MANA/TURNO", "0", "0")
        f("st_regen",1070, 220, 190, "REGEN STAMINA/TURNO", "0", "0")
        f("atk_phys",  20, 295, 190, "ATAQUE FÍSICO", "10", "10")
        f("atk_mag",  230, 295, 190, "ATAQUE MÁGICO", "10", "10")
        f("def_phys", 440, 295, 190, "DEFESA FÍSICA", "5", "5")
        f("def_mag",  650, 295, 190, "DEFESA MÁGICA", "5", "5")
        f("speed",    860, 295, 190, "VELOCIDADE", "10", "10")
        f("accuracy",1070, 295, 190, "PRECISÃO", "100", "100")
        f("str",   20, 370, 190, "FORÇA", "10", "10")
        f("dex",  230, 370, 190, "DESTREZA", "10", "10")
        f("int",  440, 370, 190, "INTELIGÊNCIA", "10", "10")
        f("wis",  650, 370, 190, "SABEDORIA", "10", "10")
        f("vit",  860, 370, 190, "VITALIDADE", "10", "10")
        f("luck",1070, 370, 190, "SORTE", "10", "10")
        f("evasion",   20, 445, 190, "ESQUIVA %", "0", "0")
        f("crit",     230, 445, 190, "CRÍTICO %", "5", "5")
        f("crit_dmg", 440, 445, 190, "DANO CRÍTICO %", "150", "150")
        f("block",    650, 445, 190, "BLOQUEIO %", "0", "0")
        f("lifesteal",860, 445, 190, "ROUBO DE VIDA %", "0", "0")
        f("initiative",1070, 445, 190, "INICIATIVA", "10", "10")
        f("res_fire",    20, 520, 190, "RES. FOGO %", "0", "0")
        f("res_ice",    230, 520, 190, "RES. GELO %", "0", "0")
        f("res_light",  440, 520, 190, "RES. ELÉTRICO %", "0", "0")
        f("res_poison", 650, 520, 190, "RES. VENENO %", "0", "0")
        f("res_holy",   860, 520, 190, "RES. SAGRADO %", "0", "0")
        f("res_dark",  1070, 520, 190, "RES. SOMBRIO %", "0", "0")

    def load_skill_chips(self):
        self.all_skills = load_json_files(SKILLS_DIR)
        self.skill_page = 0
        self.refresh_page()

    def get_filtered_skills(self):
        query = self.skill_search.text.strip().lower()
        filt = self.skill_filter_dd.value
        result = []
        for sk in self.all_skills:
            data = sk["data"]
            name = data.get("name", sk["filename"][:-5])
            if query and query not in name.lower(): continue
            if filt != "Todos" and data.get("type", "") != filt: continue
            result.append(sk)
        return result

    def refresh_page(self):
        self.filtered_skills = self.get_filtered_skills()
        self.total_filtered = len(self.filtered_skills)
        max_page = max(0, (self.total_filtered - 1) // self.SKILLS_PER_PAGE) if self.total_filtered > 0 else 0
        if self.skill_page > max_page: self.skill_page = max_page
        self.skill_buttons = []
        start = self.skill_page * self.SKILLS_PER_PAGE
        end = min(start + self.SKILLS_PER_PAGE, self.total_filtered)
        page_items = self.filtered_skills[start:end]
        for idx, sk in enumerate(page_items):
            row = idx // self.SKILL_COLS
            col = idx % self.SKILL_COLS
            x = self.SKILLS_AREA_X + col * (self.SKILL_CHIP_W + 6)
            y = self.SKILLS_AREA_Y + row * (self.SKILL_CHIP_H + 2)
            name = sk["data"].get("name", sk["filename"][:-5])
            btn = ToggleButton(x, y, self.SKILL_CHIP_W, self.SKILL_CHIP_H, name)
            btn.selected = name in self.selected_skills
            btn.callback = (lambda b=btn: self._toggle_skill(b))
            self.skill_buttons.append(btn)
        self.btn_prev.enabled = self.skill_page > 0
        self.btn_next.enabled = (self.skill_page + 1) * self.SKILLS_PER_PAGE < self.total_filtered
        self.rebuild()

    def _toggle_skill(self, btn):
        btn.selected = not btn.selected
        if btn.selected: self.selected_skills.add(btn.text)
        else: self.selected_skills.discard(btn.text)

    def _next_page(self): self.skill_page += 1; self.refresh_page()
    def _prev_page(self): self.skill_page = max(0, self.skill_page - 1); self.refresh_page()
    def _clear_search(self):
        self.skill_search.text = ""
        self.skill_search.active = False
        self.skill_page = 0
        self.refresh_page()

    def rebuild(self):
        self.all_widgets = list(self.static_widgets) + self.skill_buttons
        self.all_inputs = list(self.fields.values()) + [self.skill_search]
        self.all_dropdowns = list(self.dropdowns) + [self.skill_filter_dd]

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0: self.message = ""
        if self.skill_search.text != self._last_search_text:
            self._last_search_text = self.skill_search.text
            self.skill_page = 0
            self.refresh_page()
        if self.skill_filter_dd.index != self._last_filter_index:
            self._last_filter_index = self.skill_filter_dd.index
            self.skill_page = 0
            self.refresh_page()

    def show_message(self, msg, color=SUCCESS):
        self.message = msg; self.message_color = color; self.message_timer = 3.5

    def load_from_data(self, data):
        self.fields["name"].text = data.get("name", "")
        self.fields["race"].text = data.get("race", "")
        self.fields["class"].text = data.get("class", "")
        self.fields["level"].text = str(data.get("level", 1))
        self.fields["desc"].text = data.get("description", "")
        res = data.get("resources", {})
        self.fields["hp"].text = str(res.get("hp", 100))
        self.fields["stamina"].text = str(res.get("stamina", 0))
        self.fields["mana"].text = str(res.get("mana", 0))
        self.fields["hp_regen"].text = str(res.get("hp_regen", 0))
        self.fields["mp_regen"].text = str(res.get("mana_regen", 0))
        self.fields["st_regen"].text = str(res.get("stamina_regen", 0))
        cb = data.get("combat", {})
        self.fields["atk_phys"].text = str(cb.get("attack_physical", 0))
        self.fields["atk_mag"].text = str(cb.get("attack_magical", 0))
        self.fields["def_phys"].text = str(cb.get("defense_physical", 0))
        self.fields["def_mag"].text = str(cb.get("defense_magical", 0))
        self.fields["speed"].text = str(cb.get("speed", 0))
        self.fields["accuracy"].text = str(cb.get("accuracy", 100))
        self.fields["evasion"].text = str(cb.get("evasion", 0))
        self.fields["crit"].text = str(cb.get("crit_chance", 0))
        self.fields["crit_dmg"].text = str(cb.get("crit_damage", 150))
        self.fields["block"].text = str(cb.get("block", 0))
        self.fields["lifesteal"].text = str(cb.get("lifesteal", 0))
        self.fields["initiative"].text = str(cb.get("initiative", 0))
        at = data.get("attributes", {})
        self.fields["str"].text = str(at.get("strength", 0))
        self.fields["dex"].text = str(at.get("dexterity", 0))
        self.fields["int"].text = str(at.get("intelligence", 0))
        self.fields["wis"].text = str(at.get("wisdom", 0))
        self.fields["vit"].text = str(at.get("vitality", 0))
        self.fields["luck"].text = str(at.get("luck", 0))
        rs = data.get("resistances", {})
        self.fields["res_fire"].text = str(rs.get("fire", 0))
        self.fields["res_ice"].text = str(rs.get("ice", 0))
        self.fields["res_light"].text = str(rs.get("lightning", 0))
        self.fields["res_poison"].text = str(rs.get("poison", 0))
        self.fields["res_holy"].text = str(rs.get("holy", 0))
        self.fields["res_dark"].text = str(rs.get("dark", 0))
        self.selected_skills = set(data.get("skills", []))
        self.skill_page = 0
        self.refresh_page()

    def save_unit(self):
        name = self.fields["name"].text.strip()
        if not name:
            self.show_message("Digite um nome para a unidade!", DANGER)
            return
        def as_int(key, default=0):
            try: return int(float(self.fields[key].text))
            except Exception: return default
        def as_float(key, default=0.0):
            try: return float(self.fields[key].text)
            except Exception: return default
        data = {
            "id": "unit_" + slugify(name),
            "name": name,
            "race": self.fields["race"].text.strip(),
            "class": self.fields["class"].text.strip(),
            "level": as_int("level", 1),
            "description": self.fields["desc"].text.strip(),
            "resources": {
                "hp": as_int("hp", 1),
                "stamina": as_int("stamina", 0),
                "mana": as_int("mana", 0),
                "hp_regen": as_int("hp_regen", 0),
                "mana_regen": as_int("mp_regen", 0),
                "stamina_regen": as_int("st_regen", 0),
            },
            "combat": {
                "attack_physical": as_int("atk_phys", 0),
                "attack_magical": as_int("atk_mag", 0),
                "defense_physical": as_int("def_phys", 0),
                "defense_magical": as_int("def_mag", 0),
                "speed": as_int("speed", 0),
                "accuracy": as_float("accuracy", 100.0),
                "evasion": as_float("evasion", 0.0),
                "crit_chance": as_float("crit", 0.0),
                "crit_damage": as_float("crit_dmg", 150.0),
                "block": as_float("block", 0.0),
                "lifesteal": as_float("lifesteal", 0.0),
                "initiative": as_int("initiative", 0),
            },
            "attributes": {
                "strength": as_int("str", 0),
                "dexterity": as_int("dex", 0),
                "intelligence": as_int("int", 0),
                "wisdom": as_int("wis", 0),
                "vitality": as_int("vit", 0),
                "luck": as_int("luck", 0),
            },
            "resistances": {
                "fire": as_float("res_fire", 0.0),
                "ice": as_float("res_ice", 0.0),
                "lightning": as_float("res_light", 0.0),
                "poison": as_float("res_poison", 0.0),
                "holy": as_float("res_holy", 0.0),
                "dark": as_float("res_dark", 0.0),
            },
            "skills": sorted(self.selected_skills),
        }
        slug = slugify(name)
        path = os.path.join(UNITS_DIR, slug + ".json")
        if self.editing_name and slugify(self.editing_name) != slug:
            old = os.path.join(UNITS_DIR, slugify(self.editing_name) + ".json")
            if os.path.exists(old):
                try: os.remove(old)
                except Exception: pass
        try:
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
            self.editing_name = name
            self.show_message("Salvo em: " + os.path.relpath(path, BASE_DIR), SUCCESS)
        except Exception as ex:
            self.show_message("Erro ao salvar: " + str(ex), DANGER)

    def draw(self, surf, dt):
        surf.fill(BG)
        title = "EDITAR UNIDADE" if self.editing_name else "CRIADOR DE UNIDADES"
        draw_text(surf, title, 20, 15, FONT_XL, TEXT)
        draw_text(surf, "ESC = menu", WIDTH - 110, 22, FONT_S, TEXT_DIM)
        draw_panel(surf, pygame.Rect(10, 45, WIDTH - 20, 140))
        draw_panel(surf, pygame.Rect(10, 190, WIDTH - 20, 75))
        draw_panel(surf, pygame.Rect(10, 265, WIDTH - 20, 75))
        draw_panel(surf, pygame.Rect(10, 340, WIDTH - 20, 75))
        draw_panel(surf, pygame.Rect(10, 415, WIDTH - 20, 75))
        draw_panel(surf, pygame.Rect(10, 490, WIDTH - 20, 75))
        draw_panel(surf, pygame.Rect(10, 570, WIDTH - 20, 175))
        draw_text(surf, "HABILIDADES CONHECIDAS", 20, 576, FONT_L, ACCENT)
        total_selected = len(self.selected_skills)
        txt = "Marcadas: %d / %d disponíveis" % (total_selected, len(self.all_skills))
        draw_text(surf, txt, WIDTH - 20 - FONT_S.size(txt)[0], 582, FONT_S, TEXT_DIM)
        if not self.all_skills:
            draw_text(surf, "Nenhuma skill salva ainda.", 20, 640, FONT_M, TEXT_DIM)
        elif self.total_filtered == 0:
            draw_text(surf, "Nenhuma habilidade corresponde à busca/filtro.", 20, 640, FONT_M, WARN)
        if self.total_filtered > 0:
            total_pages = max(1, (self.total_filtered + self.SKILLS_PER_PAGE - 1) // self.SKILLS_PER_PAGE)
            page_num = self.skill_page + 1
            draw_text(surf,
                      "Página %d/%d  ·  %d filtradas  ·  %d cadastradas no total"
                      % (page_num, total_pages, self.total_filtered, len(self.all_skills)),
                      20, 712, FONT_S, TEXT_DIM)
        for w in self.all_widgets: w.draw(surf, dt)
        for d in self.all_dropdowns:
            if d.open: d.draw_list(surf)
        if self.message:
            r = FONT_M.render(self.message, True, self.message_color)
            surf.blit(r, (WIDTH // 2 - r.get_width() // 2, 726))


# ============================================================================
# Gerenciador de Entidades (com busca + filtro)
# ============================================================================
class EntityManagerScene(Scene):
    ROW_H = 80
    LIST_TOP = 105
    LIST_BOTTOM = 725
    TITLE = "GERENCIAR"
    NEW_LABEL = "+ NOVO"
    DIR = None
    FILTER_ALL_LABEL = "Todos"

    def __init__(self, app, go_back_factory=None):
        super().__init__(app)
        self.go_back_factory = go_back_factory or (lambda: MenuScene(app))
        self.entities = []
        self.filtered = []
        self.scroll = 0
        self.max_scroll = 0
        self.message = ""
        self.message_color = SUCCESS
        self.message_timer = 0.0
        self._last_search = ""
        self._last_filter = 0

        # Header: título + botões + busca + filtro
        self.search_input = TextInput(300, 57, 350, 34, "", "Buscar por nome...")
        self.filter_dd = Dropdown(660, 57, 230, 34, "", [self.FILTER_ALL_LABEL], 0)
        self.btn_clear_search = Button(272, 57, 24, 34, "x", self._clear_search,
                                       color=(120, 90, 90), font=FONT_S)

        self.btn_back = Button(20, 55, 120, 38, "VOLTAR",
                               lambda: app.change_scene(self.go_back_factory()), (90, 90, 110))
        self.btn_refresh = Button(148, 55, 120, 38, "ATUALIZAR", self.load_data, ACCENT)
        self.btn_new = Button(WIDTH - 270, 55, 250, 38, self.NEW_LABEL,
                              self._new_entity, SUCCESS)

        # Modais
        self.rename_index = -1
        self.rename_input = TextInput(0, 0, 460, 42, "NOVO NOME", "Digite um novo nome...", "")
        self.rename_ok = Button(0, 0, 140, 42, "RENOMEAR", self._confirm_rename, SUCCESS)
        self.rename_cancel = Button(0, 0, 140, 42, "CANCELAR", self._cancel_rename, (90, 90, 110))

        self.delete_index = -1
        self.delete_yes = Button(0, 0, 160, 42, "EXCLUIR", self._confirm_delete, DANGER)
        self.delete_no = Button(0, 0, 160, 42, "CANCELAR", self._cancel_delete, (90, 90, 110))

        self.all_widgets = [self.btn_back, self.btn_refresh, self.btn_new,
                            self.search_input, self.filter_dd, self.btn_clear_search]
        self.all_inputs = [self.search_input]
        self.all_dropdowns = [self.filter_dd]

        self.load_data()

    # ------------------------------------------------------------------
    # Hooks para subclasses
    def _make_editor(self, existing_data=None):
        raise NotImplementedError

    def get_row_info(self, data):
        return (data.get("name", "?"), "")

    def _duplicate_filename_suffix(self):
        return "(Cópia)"

    def get_filter_options(self):
        """Retorna lista de strings de filtro. Deve ser implementado."""
        return [self.FILTER_ALL_LABEL]

    def passes_filter(self, data, filt):
        """Verifica se um dado item passa pelo filtro. Deve ser implementado."""
        return True

    # ------------------------------------------------------------------
    def load_data(self):
        self.entities = load_json_files(self.DIR) if self.DIR else []
        # Reconstrói filtro
        new_options = self.get_filter_options()
        if new_options != self.filter_dd.options:
            self.filter_dd.options = new_options
            self.filter_dd.index = 0
        self._apply_filters()
        self.show_message("%d item(ns) carregado(s)." % len(self.entities), TEXT_DIM)

    def _apply_filters(self):
        q = self.search_input.text.strip().lower()
        filt = self.filter_dd.value
        out = []
        for ent in self.entities:
            data = ent.get("data", {})
            name = data.get("name", "")
            if q and q not in name.lower():
                continue
            if not self.passes_filter(data, filt):
                continue
            out.append(ent)
        self.filtered = out
        self._update_scroll()

    def _clear_search(self):
        self.search_input.text = ""
        self.search_input.active = False
        self._apply_filters()

    def _update_scroll(self):
        total_h = len(self.filtered) * self.ROW_H
        view_h = self.LIST_BOTTOM - self.LIST_TOP
        self.max_scroll = max(0, total_h - view_h)
        self.scroll = max(0, min(self.scroll, self.max_scroll))

    def show_message(self, msg, color=SUCCESS):
        self.message = msg; self.message_color = color; self.message_timer = 3.0

    def _row_buttons(self, y):
        return {
            "edit":   pygame.Rect(760, y + 21, 105, 38),
            "dup":    pygame.Rect(875, y + 21, 110, 38),
            "rename": pygame.Rect(995, y + 21, 115, 38),
            "delete": pygame.Rect(1120, y + 21, 130, 38),
        }

    def _visible_rows(self):
        for i, sk in enumerate(self.filtered):
            y = self.LIST_TOP + i * self.ROW_H - self.scroll
            if y + self.ROW_H > self.LIST_TOP and y < self.LIST_BOTTOM:
                yield i, y

    def _new_entity(self): self.app.change_scene(self._make_editor(None))
    def _edit_entity(self, idx):
        # idx é índice em self.filtered
        data = self.filtered[idx]["data"]
        self.app.change_scene(self._make_editor(data))

    def _duplicate_entity(self, idx):
        data = dict(self.filtered[idx]["data"])
        old_name = data.get("name", "item")
        counter = 1
        new_name = "%s %s" % (old_name, self._duplicate_filename_suffix())
        new_slug = slugify(new_name)
        while os.path.exists(os.path.join(self.DIR, new_slug + ".json")):
            counter += 1
            new_name = "%s (Cópia %d)" % (old_name, counter)
            new_slug = slugify(new_name)
        data["name"] = new_name
        prefix = "skill_" if self.DIR == SKILLS_DIR else "unit_"
        data["id"] = prefix + new_slug
        path = os.path.join(self.DIR, new_slug + ".json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.load_data()
            self.show_message("Duplicado como: " + new_name, SUCCESS)
        except Exception as ex: self.show_message("Erro: " + str(ex), DANGER)

    def _open_rename(self, idx):
        self.rename_index = idx
        self.rename_input.text = self.filtered[idx]["data"].get("name", "")
        self.rename_input.active = True

    def _confirm_rename(self):
        if self.rename_index < 0: return
        new_name = self.rename_input.text.strip()
        if not new_name:
            self.show_message("Nome não pode ser vazio!", DANGER); return
        sk = self.filtered[self.rename_index]
        data = dict(sk["data"])
        data["name"] = new_name
        prefix = "skill_" if self.DIR == SKILLS_DIR else "unit_"
        data["id"] = prefix + slugify(new_name)
        new_path = os.path.join(self.DIR, slugify(new_name) + ".json")
        try:
            if sk["path"] != new_path and os.path.exists(sk["path"]):
                os.remove(sk["path"])
            with open(new_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.rename_index = -1
            self.rename_input.active = False
            self.load_data()
            self.show_message("Renomeado para: " + new_name, SUCCESS)
        except Exception as ex: self.show_message("Erro: " + str(ex), DANGER)

    def _cancel_rename(self): self.rename_index = -1; self.rename_input.active = False
    def _open_delete(self, idx): self.delete_index = idx

    def _confirm_delete(self):
        if self.delete_index < 0: return
        sk = self.filtered[self.delete_index]
        try:
            if os.path.exists(sk["path"]): os.remove(sk["path"])
            self.delete_index = -1
            self.load_data()
            self.show_message("Item excluído.", WARN)
        except Exception as ex: self.show_message("Erro: " + str(ex), DANGER)

    def _cancel_delete(self): self.delete_index = -1

    def handle_events(self, events):
        if self.rename_index >= 0 or self.delete_index >= 0:
            for e in events:
                if e.type == pygame.QUIT: self.app.running = False; return
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    self._cancel_rename(); self._cancel_delete(); return
                if self.rename_index >= 0:
                    if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._confirm_rename(); return
                    self.rename_input.handle_event(e)
                    self.rename_ok.handle_event(e)
                    self.rename_cancel.handle_event(e)
                elif self.delete_index >= 0:
                    self.delete_yes.handle_event(e)
                    self.delete_no.handle_event(e)
            return

        for e in events:
            if e.type == pygame.QUIT: self.app.running = False; return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                if self.search_input.active:
                    self.search_input.active = False
                    return
                self.app.change_scene(MenuScene(self.app)); return

            if e.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self.LIST_TOP <= my <= self.LIST_BOTTOM:
                    self.scroll = max(0, min(self.max_scroll, self.scroll - e.y * 40))

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # Fecha dropdowns se clicou fora
                if self.filter_dd.open and not self.filter_dd.list_rect().collidepoint(e.pos):
                    self.filter_dd.open = False
                # Desativa search se clicou fora
                if self.search_input.active and not self.search_input.rect.collidepoint(e.pos):
                    self.search_input.active = False

                # Se clicou na lista, verifica botões de linha
                if self.LIST_TOP <= e.pos[1] <= self.LIST_BOTTOM:
                    for i, y in self._visible_rows():
                        btns = self._row_buttons(y)
                        if btns["edit"].collidepoint(e.pos):   self._edit_entity(i); return
                        if btns["dup"].collidepoint(e.pos):    self._duplicate_entity(i); return
                        if btns["rename"].collidepoint(e.pos): self._open_rename(i); return
                        if btns["delete"].collidepoint(e.pos): self._open_delete(i); return

            # Repassa para widgets
            for w in self.all_widgets:
                w.handle_event(e)

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0: self.message = ""

        if self.search_input.text != self._last_search:
            self._last_search = self.search_input.text
            self.scroll = 0
            self._apply_filters()

        if self.filter_dd.index != self._last_filter:
            self._last_filter = self.filter_dd.index
            self.scroll = 0
            self._apply_filters()

    def draw(self, surf, dt):
        surf.fill(BG)
        # Título em cima
        draw_text(surf, self.TITLE, 20, 15, FONT_XL, TEXT)
        # Contadores
        count_txt = "%d de %d" % (len(self.filtered), len(self.entities))
        draw_text(surf, count_txt, WIDTH - 20 - FONT_M.size(count_txt)[0], 22, FONT_M, TEXT_DIM)

        # Botões de header
        for w in self.all_widgets:
            w.draw(surf, dt)
        for d in self.all_dropdowns:
            if d.open: d.draw_list(surf)

        # Lista
        list_rect = pygame.Rect(10, self.LIST_TOP - 5, WIDTH - 20,
                                self.LIST_BOTTOM - self.LIST_TOP + 10)
        draw_panel(surf, list_rect)

        old_clip = surf.get_clip()
        surf.set_clip(list_rect.inflate(-4, -4))

        if not self.entities:
            draw_text(surf, "Nada salvo ainda.", WIDTH // 2, self.LIST_TOP + 60,
                      FONT_L, TEXT_DIM, center_x=True)
            draw_text(surf, "Use o botão '%s' para começar." % self.NEW_LABEL,
                      WIDTH // 2, self.LIST_TOP + 95, FONT_M, TEXT_DIM, center_x=True)
        elif not self.filtered:
            draw_text(surf, "Nenhum item corresponde à busca/filtro.", WIDTH // 2,
                      self.LIST_TOP + 60, FONT_L, TEXT_DIM, center_x=True)

        mx, my = pygame.mouse.get_pos()
        for i, y in self._visible_rows():
            data = self.filtered[i]["data"]
            row_rect = pygame.Rect(15, y, WIDTH - 30, self.ROW_H - 4)
            color = PANEL if i % 2 == 0 else (42, 46, 58)
            pygame.draw.rect(surf, color, row_rect, border_radius=6)
            name, info = self.get_row_info(data)
            draw_text(surf, fit_text(name, FONT_L, 700), 30, y + 10, FONT_L, TEXT)
            draw_text(surf, fit_text(info, FONT_S, 700), 30, y + 40, FONT_S, TEXT_DIM)
            btns = self._row_buttons(y)
            specs = [("edit", "EDITAR", ACCENT), ("dup", "DUPLICAR", (95, 130, 220)),
                     ("rename", "RENOMEAR", (150, 130, 220)), ("delete", "EXCLUIR", DANGER)]
            for key, label, base in specs:
                r = btns[key]
                hover = r.collidepoint(mx, my)
                c = tuple(min(255, v + 35) for v in base) if hover else base
                pygame.draw.rect(surf, c, r, border_radius=6)
                pygame.draw.rect(surf, (255, 255, 255, 25), r, 1, border_radius=6)
                txt = FONT_S.render(label, True, (255, 255, 255))
                surf.blit(txt, (r.centerx - txt.get_width() // 2,
                                r.centery - txt.get_height() // 2))
        surf.set_clip(old_clip)

        if self.max_scroll > 0:
            view_h = self.LIST_BOTTOM - self.LIST_TOP
            total_h = len(self.filtered) * self.ROW_H
            bar_h = max(30, int(view_h * view_h / total_h))
            bar_y = self.LIST_TOP + int((view_h - bar_h) * self.scroll / self.max_scroll)
            pygame.draw.rect(surf, ACCENT_DARK, (WIDTH - 16, self.LIST_TOP, 6, view_h), border_radius=3)
            pygame.draw.rect(surf, ACCENT, (WIDTH - 16, bar_y, 6, bar_h), border_radius=3)

        if self.message:
            r = FONT_M.render(self.message, True, self.message_color)
            surf.blit(r, (WIDTH // 2 - r.get_width() // 2, 748))

        if self.rename_index >= 0: self._draw_rename_modal(surf, dt)
        elif self.delete_index >= 0: self._draw_delete_modal(surf, dt)

    def _draw_rename_modal(self, surf, dt):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill(OVERLAY); surf.blit(overlay, (0, 0))
        pw, ph = 600, 200
        px = (WIDTH - pw) // 2; py = (HEIGHT - ph) // 2
        draw_panel(surf, pygame.Rect(px, py, pw, ph), PANEL)
        draw_text(surf, "RENOMEAR", px + 20, py + 18, FONT_L, TEXT)
        old = self.filtered[self.rename_index]["data"].get("name", "")
        draw_text(surf, "Atual: " + fit_text(old, FONT_S, pw - 40), px + 20, py + 48, FONT_S, TEXT_DIM)
        self.rename_input.rect = pygame.Rect(px + 20, py + 80, pw - 40, 42)
        self.rename_input.draw(surf, dt)
        self.rename_cancel.rect = pygame.Rect(px + 20, py + 140, 160, 42)
        self.rename_ok.rect = pygame.Rect(px + pw - 180, py + 140, 160, 42)
        self.rename_cancel.draw(surf, dt); self.rename_ok.draw(surf, dt)

    def _draw_delete_modal(self, surf, dt):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill(OVERLAY); surf.blit(overlay, (0, 0))
        pw, ph = 560, 170
        px = (WIDTH - pw) // 2; py = (HEIGHT - ph) // 2
        draw_panel(surf, pygame.Rect(px, py, pw, ph), PANEL)
        draw_text(surf, "EXCLUIR?", px + 20, py + 18, FONT_L, DANGER)
        nm = self.filtered[self.delete_index]["data"].get("name", "")
        draw_text(surf, fit_text(nm, FONT_M, pw - 40), px + 20, py + 55, FONT_M, TEXT)
        draw_text(surf, "Essa ação não pode ser desfeita.", px + 20, py + 82, FONT_S, TEXT_DIM)
        self.delete_no.rect = pygame.Rect(px + 20, py + 110, 180, 42)
        self.delete_yes.rect = pygame.Rect(px + pw - 200, py + 110, 180, 42)
        self.delete_no.draw(surf, dt); self.delete_yes.draw(surf, dt)


class SkillManagerScene(EntityManagerScene):
    TITLE = "HABILIDADES SALVAS"
    NEW_LABEL = "+ NOVA HABILIDADE"
    DIR = SKILLS_DIR

    def _make_editor(self, existing_data=None):
        return SkillCreatorScene(self.app, go_back_factory=lambda: SkillManagerScene(self.app),
                                 existing_data=existing_data)

    def get_filter_options(self):
        return ["Todos"] + SKILL_TYPES

    def passes_filter(self, data, filt):
        if filt == "Todos": return True
        return data.get("type", "") == filt

    def get_row_info(self, data):
        name = data.get("name", "?")
        dmg = data.get("damage", {})
        info = "[%s]  ·  dano: %s-%s %s  ·  CD: %s  ·  Lvl: %s  ·  efeitos: %d" % (
            data.get("type", "?"), dmg.get("min", 0), dmg.get("max", 0), dmg.get("type", "-"),
            data.get("cooldown", 0), data.get("requirements", {}).get("level", 1),
            len(data.get("effects", [])))
        return (name, info)


class UnitManagerScene(EntityManagerScene):
    TITLE = "UNIDADES SALVAS"
    NEW_LABEL = "+ NOVA UNIDADE"
    DIR = UNITS_DIR

    def _make_editor(self, existing_data=None):
        return UnitCreatorScene(self.app, go_back_factory=lambda: UnitManagerScene(self.app),
                                existing_data=existing_data)

    def get_filter_options(self):
        races = sorted(set(u["data"].get("race", "") for u in self.entities
                           if u["data"].get("race")))
        return ["Todas"] + races

    def passes_filter(self, data, filt):
        if filt in ("Todas", "Todos"): return True
        return data.get("race", "") == filt

    def get_row_info(self, data):
        name = data.get("name", "?")
        res = data.get("resources", {})
        info = "%s / %s  ·  Lvl %s  ·  HP %s / Mana %s / Stm %s  ·  skills: %d" % (
            data.get("race", "-") or "-", data.get("class", "-") or "-",
            data.get("level", 1), res.get("hp", 0), res.get("mana", 0), res.get("stamina", 0),
            len(data.get("skills", [])))
        return (name, info)


# ============================================================================
# Import
# ============================================================================
class ImportScene(Scene):
    def __init__(self, app, go_back_factory=None):
        super().__init__(app)
        self.go_back_factory = go_back_factory or (lambda: MenuScene(app))
        self.mode = "auto"
        self.message = ""; self.message_color = SUCCESS; self.message_timer = 0.0
        self.last_errors = []
        self.tab_auto   = ToggleButton(20, 75, 200, 40, "AUTO (DETECTAR)")
        self.tab_skills = ToggleButton(230, 75, 160, 40, "SKILLS")
        self.tab_units  = ToggleButton(400, 75, 160, 40, "UNIDADES")
        self.tab_auto.selected = True
        self.tab_auto.callback   = lambda: self.set_mode("auto")
        self.tab_skills.callback = lambda: self.set_mode("skills")
        self.tab_units.callback  = lambda: self.set_mode("units")
        self.text_area = TextArea(20, 155, WIDTH - 40, 470,
            label="COLE O TEXTO JSON AQUI  (Ctrl+V para colar)",
            placeholder='Exemplos aceitos:\n  { "name": "...", ... }\n  [ { ... }, { ... } ]\n  { ... } { ... } { ... }')
        self.btn_back = Button(20, 730, 160, 42, "VOLTAR",
                               lambda: app.change_scene(self.go_back_factory()), (90, 90, 110))
        self.btn_clear = Button(200, 730, 140, 42, "LIMPAR", self.clear, (90, 90, 110))
        self.btn_import = Button(1000, 727, 260, 48, "IMPORTAR AGORA", self.do_import, SUCCESS)
        self.all_widgets = [self.tab_auto, self.tab_skills, self.tab_units,
                            self.text_area, self.btn_back, self.btn_clear, self.btn_import]
        self.all_inputs = [self.text_area]
        self.all_dropdowns = []

    def set_mode(self, mode):
        self.mode = mode
        self.tab_auto.selected   = (mode == "auto")
        self.tab_skills.selected = (mode == "skills")
        self.tab_units.selected  = (mode == "units")

    def clear(self):
        self.text_area.text = ""; self.last_errors = []
        self.show_message("Texto limpo.", TEXT_DIM)

    def show_message(self, msg, color=SUCCESS):
        self.message = msg; self.message_color = color; self.message_timer = 6.0

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0: self.message = ""

    def _save_item(self, item, target_dir, prefix):
        try:
            name = str(item.get("name", "")).strip()
            if not name: return False, "falta o campo 'name'"
            if "id" not in item or not item["id"]:
                item["id"] = prefix + slugify(name)
            path = os.path.join(target_dir, slugify(name) + ".json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(item, f, ensure_ascii=False, indent=2)
            return True, None
        except Exception as ex:
            return False, str(ex)

    def do_import(self):
        raw = self.text_area.text.strip()
        if not raw:
            self.show_message("Cole um texto JSON antes de importar.", WARN); return
        items = parse_json_items(raw)
        if not items:
            self.show_message("Nenhum JSON válido encontrado no texto.", DANGER); return
        self.last_errors = []
        kinds = [detect_item_kind(it) for it in items]
        if self.mode == "auto":
            n_skills = n_units = 0
            errors = []; unknown = []
            for i, (item, kind) in enumerate(zip(items, kinds)):
                name = str(item.get("name", "?"))
                if kind == "skill":
                    ok, err = self._save_item(item, SKILLS_DIR, "skill_")
                    if ok: n_skills += 1
                    else: errors.append("%s (skill): %s" % (name, err))
                elif kind == "unit":
                    ok, err = self._save_item(item, UNITS_DIR, "unit_")
                    if ok: n_units += 1
                    else: errors.append("%s (unidade): %s" % (name, err))
                else:
                    unknown.append("%s [item %d, tipo: %s]" % (name, i + 1, kind))
            parts = []
            if n_skills: parts.append("%d skill(s)" % n_skills)
            if n_units:  parts.append("%d unidade(s)" % n_units)
            summary = " + ".join(parts) if parts else "0 itens"
            if (n_skills or n_units) and not unknown and not errors:
                self.show_message("OK! Importado: " + summary, SUCCESS)
            elif n_skills or n_units:
                self.show_message("Importado: %s. %d ignorado(s)."
                                  % (summary, len(unknown) + len(errors)), WARN)
            else:
                self.show_message("Nada importado. Tipos não reconhecidos.", DANGER)
            self.last_errors = (["Ignorado: " + u for u in unknown[:8]] + errors[:8])[:10]
            return
        expected = "skill" if self.mode == "skills" else "unit"
        target_dir = SKILLS_DIR if expected == "skill" else UNITS_DIR
        prefix = "skill_" if expected == "skill" else "unit_"
        expected_word = "HABILIDADE" if expected == "skill" else "UNIDADE"
        other_word = "UNIDADE" if expected == "skill" else "HABILIDADE"
        n_other = n_unknown = 0
        other_names = []; unknown_names = []
        for i, (item, kind) in enumerate(zip(items, kinds)):
            name = str(item.get("name", "?"))
            if kind == expected: continue
            elif kind in ("unknown", "ambiguous"):
                n_unknown += 1; unknown_names.append("%s (item %d)" % (name, i + 1))
            else:
                n_other += 1; other_names.append(name)
        if n_other > 0:
            self.last_errors = (["Tipo errado (%s): %s" % (other_word.lower(), nm)
                                 for nm in other_names[:8]]
                                + ["Formato ambíguo: " + nm for nm in unknown_names[:4]])[:10]
            self.show_message("BLOQUEADO: %d %s(s) detectada(s) na aba %s."
                              % (n_other, other_word, expected_word), DANGER)
            return
        if n_unknown > 0:
            self.last_errors = ["Ambíguo: " + nm for nm in unknown_names[:10]]
            self.show_message("BLOQUEADO: %d item(ns) ambíguo." % n_unknown, DANGER)
            return
        imported = 0; errors = []
        for item in items:
            name = str(item.get("name", "?"))
            ok, err = self._save_item(item, target_dir, prefix)
            if ok: imported += 1
            else: errors.append("%s: %s" % (name, err))
        if imported and not errors:
            self.show_message("OK! %d %s(s) importada(s)." % (imported, expected_word.lower()), SUCCESS)
        elif imported and errors:
            self.show_message("%d importada(s), %d com erro." % (imported, len(errors)), WARN)
        else:
            self.show_message("Nada foi importado.", DANGER)
        self.last_errors = errors[:10]

    def draw(self, surf, dt):
        surf.fill(BG)
        draw_text(surf, "IMPORTAR DADOS (JSON)", 20, 15, FONT_XL, TEXT)
        draw_text(surf, "ESC = menu", WIDTH - 110, 22, FONT_S, TEXT_DIM)
        draw_text(surf, "DESTINO:", 20, 55, FONT_S, TEXT_DIM)
        self.tab_auto.draw(surf, dt); self.tab_skills.draw(surf, dt); self.tab_units.draw(surf, dt)
        if self.mode == "auto":
            hint = "AUTO: cada objeto vai para a pasta certa (skills ou units)."
        elif self.mode == "skills":
            hint = "SKILLS: aceita só habilidades. Bloqueia se detectar unidades."
        else:
            hint = "UNIDADES: aceita só unidades. Bloqueia se detectar habilidades."
        draw_text(surf, hint, 20, 122, FONT_S, TEXT_DIM)
        draw_text(surf, "Formatos aceitos:", 620, 55, FONT_S, TEXT_DIM)
        draw_text(surf, '• Objeto único:   { "name": "...", ... }', 620, 75, FONT_S, TEXT_DIM)
        draw_text(surf, '• Array:   [ { ... }, { ... } ]', 620, 92, FONT_S, TEXT_DIM)
        draw_text(surf, '• Colados:   { ... } { ... } { ... }', 620, 109, FONT_S, TEXT_DIM)
        draw_text(surf, '• Container:   { "skills": [...] } ou { "units": [...] }',
                  620, 126, FONT_S, TEXT_DIM)
        self.text_area.draw(surf, dt)
        for w in [self.btn_back, self.btn_clear, self.btn_import]: w.draw(surf, dt)
        if self.message:
            r = FONT_M.render(self.message, True, self.message_color)
            surf.blit(r, (WIDTH // 2 - r.get_width() // 2, 700))
        if self.last_errors:
            y = 760
            for err in self.last_errors:
                draw_text(surf, "• " + fit_text(err, FONT_S, WIDTH - 40), 20, y, FONT_S, DANGER)
                y += 14
                if y > HEIGHT - 12: break


# ============================================================================
# App
# ============================================================================
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