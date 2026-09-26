# -*- coding: utf-8 -*-
"""
ItemCreator.py
Criador de Itens, Equipamentos e Afixos (prefixos/sufixos) para Roguelike
--------------------------------------------------------------------------
- Interface Pygame (1280x800)
- Cria / Edita Itens (armas, armaduras, acessórios, consumíveis, materiais)
- Cria / Edita Afixos (prefixos e sufixos que se somam aos itens)
- Gerencia: ver / duplicar / renomear / excluir
- Importa via JSON colado
- Exporta para ./exports/items e ./exports/affixes

Campos por item:
- id, name, description, long_description, category, subcategory, rarity,
  level_required, value, weight, stackable, max_stack, tags, icon, grid_size,
  equipment (ou null), consumable (ou null)
"""

import os, re, json, pygame

# ============================================================================
# Inicialização
# ============================================================================
pygame.init()
pygame.key.set_repeat(400, 40)
try: pygame.scrap.init()
except Exception: pass

def get_clipboard_text():
    try:
        import tkinter
        r = tkinter.Tk(); r.withdraw()
        try: text = r.clipboard_get()
        except Exception: text = ""
        r.destroy()
        if text: return text
    except Exception: pass
    try:
        pygame.scrap.init()
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        if raw: return raw.decode("utf-8", "ignore").replace("\x00", "")
    except Exception: pass
    return ""


WIDTH, HEIGHT = 1280, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Item & Equipment Creator")
clock = pygame.time.Clock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
ITEMS_DIR   = os.path.join(EXPORTS_DIR, "items")
AFFIXES_DIR = os.path.join(EXPORTS_DIR, "affixes")
os.makedirs(ITEMS_DIR, exist_ok=True)
os.makedirs(AFFIXES_DIR, exist_ok=True)

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
# Listas
# ============================================================================
ITEM_CATEGORIES = ["Arma", "Armadura", "Acessório", "Consumível", "Material", "Quest", "Misc"]

SUBCATEGORIES = {
    "Arma":       ["Espada", "Machado", "Adaga", "Lança", "Arco", "Besta",
                   "Cajado", "Varinha", "Maça", "Martelo", "Clava", "Chicote"],
    "Armadura":   ["Elmo", "Peitoral", "Calças", "Botas", "Luvas", "Escudo", "Capa"],
    "Acessório":  ["Anel", "Amuleto", "Cinto", "Talismã", "Broche"],
    "Consumível": ["Poção", "Pergaminho", "Comida", "Bomba", "Elixir", "Antídoto"],
    "Material":   ["Minério", "Erva", "Gema", "Couro", "Tecido", "Osso", "Madeira"],
    "Quest":      ["Chave", "Relíquia", "Documento", "Selo"],
    "Misc":       ["Misc"],
}

RARITIES = ["Comum", "Incomum", "Raro", "Épico", "Lendário", "Mítico"]
RARITY_COLORS = {
    "Comum":    (200, 200, 200),
    "Incomum":  (100, 220, 100),
    "Raro":     (100, 160, 255),
    "Épico":    (200, 130, 240),
    "Lendário": (240, 170, 60),
    "Mítico":   (255, 100, 100),
}

EQUIP_SLOTS = ["Cabeça", "Peito", "Pernas", "Pés", "Mãos",
               "Arma", "Mão Secundária", "Anel", "Amuleto", "Cinto", "Capa"]

DAMAGE_TYPES = ["Nenhum", "Físico", "Fogo", "Gelo", "Elétrico", "Veneno",
                "Ácido", "Arcano", "Sagrado", "Sombrio"]

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

EFFECT_TRIGGERS = [
    "Ao acertar", "Ao ser acertado", "Ao usar", "Ao equipar",
    "Ao matar", "Em crítico", "Quando HP < 50%", "Quando HP < 25%",
]

STAT_MODS = [
    ("attack_physical",  "ATQ FÍS"),
    ("attack_magical",   "ATQ MÁG"),
    ("defense_physical", "DEF FÍS"),
    ("defense_magical",  "DEF MÁG"),
    ("hp",               "HP"),
    ("mana",             "MANA"),
    ("stamina",          "STAMINA"),
    ("accuracy",         "ACERTO"),
    ("evasion",          "ESQUIVA"),
    ("crit_chance",      "CRÍTICO %"),
    ("crit_damage",      "DANO CRÍT %"),
    ("initiative",       "INICIATIVA"),
    ("strength",         "FORÇA"),
    ("dexterity",        "DESTREZA"),
    ("intelligence",     "INTELIG"),
    ("wisdom",           "SABEDORIA"),
    ("vitality",         "VITALIDADE"),
    ("luck",             "SORTE"),
]

RESIST_FIELDS = [
    ("fire",      "RES FOGO"),
    ("ice",       "RES GELO"),
    ("lightning", "RES ELÉTR"),
    ("poison",    "RES VENENO"),
    ("holy",      "RES SAGRADO"),
    ("dark",      "RES SOMBRIO"),
]

AFFIX_KINDS = ["Prefixo", "Sufixo"]

# Tamanho padrão de grid por subcategoria — usado apenas como SUGESTÃO no editor.
# O valor salvo no JSON é o que está nos campos LARG x ALT, o usuário pode mudar.
SUBCAT_DEFAULT_SIZE = {
    "Adaga": (1, 2), "Espada": (1, 3), "Machado": (2, 3),
    "Lança": (1, 4), "Arco": (2, 3), "Besta": (2, 2),
    "Cajado": (1, 4), "Varinha": (1, 2), "Maça": (2, 2),
    "Martelo": (2, 3), "Clava": (1, 2), "Chicote": (1, 3),
    "Elmo": (2, 2), "Peitoral": (2, 3), "Calças": (2, 3),
    "Botas": (2, 2), "Luvas": (2, 2), "Escudo": (2, 3), "Capa": (2, 2),
    "Anel": (1, 1), "Amuleto": (1, 1), "Cinto": (2, 1),
    "Talismã": (1, 1), "Broche": (1, 1),
    "Poção": (1, 1), "Pergaminho": (1, 2), "Comida": (1, 1),
    "Bomba": (1, 1), "Elixir": (1, 1), "Antídoto": (1, 1),
    "Minério": (1, 1), "Erva": (1, 1), "Gema": (1, 1), "Couro": (1, 1),
    "Tecido": (1, 1), "Osso": (1, 1), "Madeira": (1, 1),
    "Chave": (1, 1), "Relíquia": (1, 1), "Documento": (1, 1),
    "Selo": (1, 1), "Misc": (1, 1),
}

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
    if center_x: surf.blit(r, (x - r.get_width() // 2, y))
    else:        surf.blit(r, (x, y))
    return r


def draw_panel(surf, rect, color=PANEL, radius=10, border=True, border_color=None):
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border_color or BORDER, rect, 1, border_radius=radius)


def fit_text(text, font, max_w):
    if font.size(text)[0] <= max_w: return text
    t = text
    while t and font.size("..." + t)[0] > max_w:
        t = t[1:]
    return "..." + t


def wrap_text_lines(text, font, max_w):
    result = []
    for line in text.split("\n"):
        if not line:
            result.append(""); continue
        remaining = line
        while remaining:
            if font.size(remaining)[0] <= max_w:
                result.append(remaining); break
            lo, hi = 1, len(remaining)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if font.size(remaining[:mid])[0] <= max_w: lo = mid
                else: hi = mid - 1
            result.append(remaining[:lo]); remaining = remaining[lo:]
    return result


def load_json_files(directory):
    out = []
    if os.path.isdir(directory):
        for fn in sorted(os.listdir(directory)):
            if not fn.endswith(".json"): continue
            try:
                with open(os.path.join(directory, fn), "r", encoding="utf-8") as f:
                    out.append({"path": os.path.join(directory, fn),
                                "filename": fn, "data": json.load(f)})
            except Exception: pass
    return out


def parse_json_items(raw):
    raw = raw.strip()
    if not raw: return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list): return [p for p in parsed if isinstance(p, dict)]
        if isinstance(parsed, dict):
            for key in ("items", "data", "list", "affixes"):
                if key in parsed and isinstance(parsed[key], list):
                    return [p for p in parsed[key] if isinstance(p, dict)]
            return [parsed]
    except Exception: pass
    items = []; depth = 0; start = None; in_string = False; escape = False
    for i, ch in enumerate(raw):
        if escape: escape = False; continue
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
                try:
                    obj = json.loads(raw[start:i + 1])
                    if isinstance(obj, dict): items.append(obj)
                except Exception: pass
                start = None
    return items


def detect_kind(item):
    if not isinstance(item, dict): return "unknown"
    if "kind" in item and item["kind"] in ("Prefixo", "Sufixo"): return "affix"
    if "applies_to" in item: return "affix"
    if "equipment" in item or "consumable" in item: return "item"
    if "category" in item: return "item"
    return "unknown"


# ============================================================================
# Widgets
# ============================================================================
class TextInput:
    def __init__(self, x, y, w, h, label="", placeholder="", text=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label; self.placeholder = placeholder; self.text = text
        self.active = False; self._blink = 0.0; self._show_cursor = True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.active = True; return True
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB): self.active = False
            elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                self.text += get_clipboard_text()
            else:
                ch = event.unicode
                if ch and ch.isprintable(): self.text += ch
            return True
        return False

    def draw(self, surf, dt=0.0):
        if self.label: draw_text(surf, self.label, self.rect.x, self.rect.y - 15, FONT_S, TEXT_DIM)
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
                self._blink = 0.0; self._show_cursor = not self._show_cursor
            if self._show_cursor:
                full = fit_text(self.text, FONT_M, self.rect.w - 16)
                cx = self.rect.x + 8 + FONT_M.size(full)[0] + 2
                pygame.draw.line(surf, TEXT, (cx, self.rect.y + 6),
                                 (cx, self.rect.y + self.rect.h - 6), 2)


class TextArea:
    def __init__(self, x, y, w, h, label="", placeholder=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label; self.placeholder = placeholder; self.text = ""
        self.active = False; self.scroll = 0; self._blink = 0.0; self._show_cursor = True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos): self.active = True; return True
        if event.type == pygame.MOUSEWHEEL and self.active:
            mx, my = pygame.mouse.get_pos()
            if self.rect.collidepoint(mx, my):
                self.scroll = max(0, self.scroll - event.y * 30); return True
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER): self.text += "\n"
            elif event.key == pygame.K_TAB: self.active = False
            elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                self.text += get_clipboard_text()
            else:
                ch = event.unicode
                if ch and ch.isprintable(): self.text += ch
            return True
        return False

    def draw(self, surf, dt=0.0):
        if self.label: draw_text(surf, self.label, self.rect.x, self.rect.y - 15, FONT_S, TEXT_DIM)
        bg = INPUT_ACT if self.active else INPUT_BG
        pygame.draw.rect(surf, bg, self.rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT if self.active else BORDER, self.rect, 1, border_radius=5)
        line_h = FONT_M.get_height() + 2
        max_w = self.rect.w - 16
        visual = wrap_text_lines(self.text, FONT_M, max_w) if self.text else ([self.placeholder] if self.placeholder else [])
        total_h = len(visual) * line_h
        view_h = self.rect.h - 8
        self.scroll = max(0, total_h - view_h) if total_h > view_h else 0
        old_clip = surf.get_clip(); surf.set_clip(self.rect.inflate(-4, -4))
        y = self.rect.y + 4 - self.scroll
        for vl in visual:
            if y + line_h > self.rect.y and y < self.rect.bottom:
                col = TEXT_DIM if (not self.text) else TEXT
                r = FONT_M.render(vl, True, col)
                surf.blit(r, (self.rect.x + 8, y))
            y += line_h
        if self.active:
            self._blink += dt
            if self._blink > 0.5:
                self._blink = 0.0; self._show_cursor = not self._show_cursor
            if self._show_cursor and visual:
                last = visual[-1]
                cx = self.rect.x + 8 + FONT_M.size(last)[0] + 2
                cy = self.rect.y + 4 + (len(visual) - 1) * line_h - self.scroll
                if cy + line_h > self.rect.y and cy < self.rect.bottom:
                    pygame.draw.line(surf, TEXT, (cx, cy + 2), (cx, cy + line_h - 4), 2)
        surf.set_clip(old_clip)


class Button:
    def __init__(self, x, y, w, h, text, callback, color=ACCENT, font=FONT_M):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text; self.callback = callback; self.color = color
        self.font = font; self.hover = False; self.enabled = True

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION: self.hover = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.enabled and self.rect.collidepoint(event.pos):
                self.callback(); return True
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
    MAX_VISIBLE = 8
    def __init__(self, x, y, w, h, label, options, index=0):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label; self.options = list(options) if options else [""]
        self.index = max(0, min(index, len(self.options) - 1))
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
        if self.label: draw_text(surf, self.label, self.rect.x, self.rect.y - 15, FONT_S, TEXT_DIM)
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
            if r.collidepoint(mx, my): pygame.draw.rect(surf, PANEL_LIGHT, r)
            if idx == self.index: pygame.draw.rect(surf, ACCENT_DARK, r)
            t = fit_text(self.options[idx], FONT_M, r.w - 16)
            tr = FONT_M.render(t, True, TEXT)
            surf.blit(tr, (r.x + 8, r.y + (r.h - tr.get_height()) // 2))


# ============================================================================
# Scene base
# ============================================================================
class Scene:
    def __init__(self, app):
        self.app = app
        self.all_widgets = []
        self.all_inputs = []
        self.all_dropdowns = []
    def handle_events(self, events):
        for e in events:
            if e.type == pygame.QUIT: self.app.running = False; return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_scene(MenuScene(self.app)); return
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                in_list = any(d.open and d.list_rect().collidepoint(e.pos) for d in self.all_dropdowns)
                if in_list:
                    for d in self.all_dropdowns:
                        if d.handle_event(e): break
                    continue
                for d in self.all_dropdowns:
                    if not d.rect.collidepoint(e.pos): d.open = False
                for i in self.all_inputs:
                    if not i.rect.collidepoint(e.pos): i.active = False
            for w in self.all_widgets: w.handle_event(e)
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
            Button(240, 200, bw, bh, "CRIAR ITEM / EQUIPAMENTO",
                   lambda: app.change_scene(ItemCreatorScene(app)), ACCENT),
            Button(660, 200, bw, bh, "CRIAR PREFIXO / SUFIXO",
                   lambda: app.change_scene(AffixCreatorScene(app)), (150, 130, 220)),
            Button(240, 270, bw, bh, "GERENCIAR ITENS",
                   lambda: app.change_scene(ItemManagerScene(app)), (95, 130, 220)),
            Button(660, 270, bw, bh, "GERENCIAR PREFIXOS / SUFIXOS",
                   lambda: app.change_scene(AffixManagerScene(app)), (95, 130, 220)),
            Button(440, 350, 400, bh, "IMPORTAR DADOS (JSON)",
                   lambda: app.change_scene(ImportScene(app)), SUCCESS),
            Button(540, 420, 200, bh, "SAIR",
                   lambda: setattr(app, "running", False), DANGER),
        ]
        self.all_widgets = list(self.buttons)
    def draw(self, surf, dt):
        surf.fill(BG)
        for i in range(0, WIDTH, 60):
            pygame.draw.line(surf, (32, 36, 46), (i, 0), (i, HEIGHT))
        for j in range(0, HEIGHT, 60):
            pygame.draw.line(surf, (32, 36, 46), (0, j), (WIDTH, j))
        draw_text(surf, "CRIADOR DE ITENS E EQUIPAMENTOS", WIDTH//2, 80, FONT_XL, TEXT, center_x=True)
        draw_text(surf, "para RPG / Roguelike", WIDTH//2, 115, FONT_L, TEXT_DIM, center_x=True)
        draw_text(surf, f"Itens:   {ITEMS_DIR}", WIDTH//2, 600, FONT_S, ACCENT, center_x=True)
        draw_text(surf, f"Afixos:  {AFFIXES_DIR}", WIDTH//2, 622, FONT_S, ACCENT, center_x=True)
        for w in self.all_widgets: w.draw(surf, dt)


# ============================================================================
# Effect Row
# ============================================================================
class EffectRow:
    def __init__(self, on_remove, show_trigger=True):
        self.on_remove = on_remove
        h = 30
        self.type_dd    = Dropdown(0, 0, 220, h, "", EFFECT_TYPES, 0)
        self.value_in   = TextInput(0, 0, 70, h, "", "0", "0")
        self.dur_in     = TextInput(0, 0, 70, h, "", "0", "0")
        self.chance_in  = TextInput(0, 0, 70, h, "", "100", "100")
        self.trigger_dd = Dropdown(0, 0, 180, h, "", EFFECT_TRIGGERS, 0)
        self.remove_btn = Button(0, 0, 32, h, "X", lambda: self.on_remove(self), DANGER, font=FONT_S)
        self.show_trigger = show_trigger
        self.widgets = [self.type_dd, self.value_in, self.dur_in, self.chance_in]
        if show_trigger: self.widgets.append(self.trigger_dd)
        self.widgets.append(self.remove_btn)
        self.inputs = [self.value_in, self.dur_in, self.chance_in]
        self.dropdowns = [self.type_dd] + ([self.trigger_dd] if show_trigger else [])
    def set_y(self, y):
        self.type_dd.rect.topleft    = (20, y)
        self.value_in.rect.topleft   = (250, y)
        self.dur_in.rect.topleft     = (330, y)
        self.chance_in.rect.topleft  = (410, y)
        if self.show_trigger:
            self.trigger_dd.rect.topleft = (490, y)
        self.remove_btn.rect.topleft = (1180, y)
    def to_dict(self):
        def as_int(s, d=0):
            try: return int(float(s))
            except Exception: return d
        out = {
            "type": self.type_dd.value,
            "value": as_int(self.value_in.text, 0),
            "duration": as_int(self.dur_in.text, 0),
            "chance": as_int(self.chance_in.text, 100),
        }
        if self.show_trigger: out["trigger"] = self.trigger_dd.value
        return out
    def load_from(self, data):
        t = data.get("type", EFFECT_TYPES[0])
        self.type_dd.index = EFFECT_TYPES.index(t) if t in EFFECT_TYPES else 0
        self.value_in.text = str(data.get("value", 0))
        self.dur_in.text = str(data.get("duration", 0))
        self.chance_in.text = str(data.get("chance", 100))
        if self.show_trigger:
            tg = data.get("trigger", EFFECT_TRIGGERS[0])
            self.trigger_dd.index = EFFECT_TRIGGERS.index(tg) if tg in EFFECT_TRIGGERS else 0


# ============================================================================
# Item Creator
# ============================================================================
class ItemCreatorScene(Scene):
    TABS = ["BÁSICO", "STATS", "EFEITOS"]
    MAX_EFFECTS = 10

    def __init__(self, app, go_back_factory=None, existing_data=None):
        super().__init__(app)
        self.go_back_factory = go_back_factory or (lambda: MenuScene(app))
        self.current_tab = 0
        self.effects = []
        self.message = ""; self.message_color = SUCCESS; self.message_timer = 0.0
        self.editing_name = existing_data.get("name", "") if existing_data else ""

        # ---------- Básico ----------
        self.in_name  = TextInput(20, 130, 620, 32, "NOME", "ex: Espada Longa de Aço")
        self.in_desc  = TextInput(660, 130, 600, 32, "DESCRIÇÃO CURTA", "ex: Uma espada comum.")

        self.dd_cat    = Dropdown(20, 200, 220, 32, "CATEGORIA", ITEM_CATEGORIES, 0)
        self.dd_subcat = Dropdown(260, 200, 220, 32, "SUBCATEGORIA", SUBCATEGORIES["Arma"], 0)
        self.dd_rarity = Dropdown(500, 200, 220, 32, "RARIDADE", RARITIES, 0)
        self.in_level  = TextInput(740, 200, 120, 32, "NÍVEL REQ", "1", "1")
        self.in_value  = TextInput(880, 200, 120, 32, "VALOR (ouro)", "50", "50")
        self.in_weight = TextInput(1020, 200, 120, 32, "PESO (kg)", "1.0", "1.0")

        self.tg_stack   = ToggleButton(20, 250, 130, 30, "STACK?")
        self.in_maxstk  = TextInput(170, 250, 100, 30, "MAX STACK", "1", "1")
        self.in_tags    = TextInput(290, 250, 690, 30, "TAGS (separadas por vírgula)", "arma, aço, espada", "")

        # Ícone e tamanho no grid do inventário
        self.in_icon   = TextInput(990, 250, 60, 30, "ÍCONE", "A", "")
        self.in_grid_w = TextInput(1060, 250, 60, 30, "LARG", "1", "1")
        self.in_grid_h = TextInput(1130, 250, 60, 30, "ALT", "1", "1")

        self.in_longdesc = TextArea(20, 320, 1240, 175, "DESCRIÇÃO LONGA (opcional)",
                                    "Descreva a lore do item, o material, origem...")

        # Inicializa tamanho do grid baseado na subcategoria inicial
        def_wh = SUBCAT_DEFAULT_SIZE.get(self.dd_subcat.value, (1, 1))
        self.in_grid_w.text = str(def_wh[0])
        self.in_grid_h.text = str(def_wh[1])
        self._last_subcat = self.dd_subcat.value

        # ---------- Stats ----------
        self.dd_slot    = Dropdown(20, 130, 220, 32, "SLOT", EQUIP_SLOTS, 5)
        self.tg_2h      = ToggleButton(260, 130, 140, 32, "DUAS MÃOS")
        self.dd_dmgtype = Dropdown(420, 130, 220, 32, "TIPO DE DANO", DAMAGE_TYPES, 1)
        self.in_dmgmin  = TextInput(660, 130, 120, 32, "DANO MÍN", "0", "0")
        self.in_dmgmax  = TextInput(800, 130, 120, 32, "DANO MÁX", "0", "0")
        self.in_armor   = TextInput(940, 130, 120, 32, "ARMADURA", "0", "0")

        self.dd_consume_type   = Dropdown(20, 195, 220, 32, "TIPO DE CONSUMO",
                                          ["Instantâneo", "Permanente", "Duração"], 0)
        self.dd_consume_target = Dropdown(260, 195, 220, 32, "ALVO",
                                          ["Si Mesmo", "Aliado Único", "Todos os Aliados",
                                           "Inimigo Único", "Todos os Inimigos", "Área"], 0)

        self.stat_inputs = {}
        rows_y = [290, 345, 400]
        for i, (key, label) in enumerate(STAT_MODS):
            row = i // 6; col = i % 6
            x = 20 + col * 208
            y = rows_y[row]
            self.stat_inputs[key] = TextInput(x, y, 195, 30, label, "0", "0")

        self.res_inputs = {}
        for i, (key, label) in enumerate(RESIST_FIELDS):
            x = 20 + i * 208
            self.res_inputs[key] = TextInput(x, 470, 195, 30, label, "0", "0")

        # ---------- Efeitos ----------
        self.effect_btn_add = Button(190, 735, 200, 42, "+ ADICIONAR EFEITO",
                                     self.add_effect, ACCENT)

        # ---------- Botões fixos (todos alinhados em y=735) ----------
        self.btn_back  = Button(20, 735, 160, 42, "VOLTAR",
                                lambda: app.change_scene(self.go_back_factory()), (90, 90, 110))
        self.btn_clear = Button(400, 735, 120, 42, "LIMPAR", self.clear_all, (90, 90, 110))
        self.btn_save  = Button(1000, 735, 260, 48, "SALVAR (.JSON)", self.save_item, SUCCESS)

        # ---------- Abas ----------
        self.tab_buttons = []
        for i, name in enumerate(self.TABS):
            tb = ToggleButton(20 + i * 165, 55, 155, 34, name,
                              (lambda idx=i: self.set_tab(idx)))
            tb.selected = (i == 0)
            self.tab_buttons.append(tb)

        if existing_data:
            self.load_from_data(existing_data)
        else:
            self.add_effect(silent=True)
            self.refresh()

    # ------------------------------------------------------------------
    def set_tab(self, idx):
        self.current_tab = idx
        for i, tb in enumerate(self.tab_buttons):
            tb.selected = (i == idx)
        self.refresh()

    def add_effect(self, silent=False):
        if len(self.effects) >= self.MAX_EFFECTS:
            if not silent: self.show_message("Máximo de %d efeitos." % self.MAX_EFFECTS, WARN)
            return
        self.effects.append(EffectRow(self.remove_effect, show_trigger=True))
        self.refresh()

    def remove_effect(self, row):
        if row in self.effects: self.effects.remove(row)
        self.refresh()

    def clear_all(self):
        self.effects.clear()
        self.refresh()
        self.show_message("Efeitos limpos.", TEXT_DIM)

    def refresh(self):
        self.all_widgets = []
        self.all_inputs = []
        self.all_dropdowns = []

        self.all_widgets.extend(self.tab_buttons)

        if self.current_tab == 0:  # BÁSICO
            for w in [self.in_name, self.in_desc, self.dd_cat, self.dd_subcat,
                      self.dd_rarity, self.in_level, self.in_value, self.in_weight,
                      self.tg_stack, self.in_maxstk, self.in_tags,
                      self.in_icon, self.in_grid_w, self.in_grid_h, self.in_longdesc]:
                self.all_widgets.append(w)
            self.all_inputs.extend([self.in_name, self.in_desc, self.in_level,
                                    self.in_value, self.in_weight, self.in_maxstk,
                                    self.in_tags, self.in_icon, self.in_grid_w,
                                    self.in_grid_h, self.in_longdesc])
            self.all_dropdowns.extend([self.dd_cat, self.dd_subcat, self.dd_rarity])

        elif self.current_tab == 1:  # STATS
            for w in [self.dd_slot, self.tg_2h, self.dd_dmgtype,
                      self.in_dmgmin, self.in_dmgmax, self.in_armor,
                      self.dd_consume_type, self.dd_consume_target]:
                self.all_widgets.append(w)
            for inp in self.stat_inputs.values():
                self.all_widgets.append(inp); self.all_inputs.append(inp)
            for inp in self.res_inputs.values():
                self.all_widgets.append(inp); self.all_inputs.append(inp)
            self.all_inputs.extend([self.in_dmgmin, self.in_dmgmax, self.in_armor])
            self.all_dropdowns.extend([self.dd_slot, self.dd_dmgtype,
                                       self.dd_consume_type, self.dd_consume_target])

        else:  # EFEITOS
            self.all_widgets.append(self.effect_btn_add)
            for i, row in enumerate(self.effects):
                row.set_y(165 + i * 36)
                self.all_widgets.extend(row.widgets)
                self.all_inputs.extend(row.inputs)
                self.all_dropdowns.extend(row.dropdowns)

        self.all_widgets.extend([self.btn_back, self.btn_clear, self.btn_save])

    # ------------------------------------------------------------------
    def show_message(self, msg, color=SUCCESS):
        self.message = msg; self.message_color = color; self.message_timer = 3.5

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0: self.message = ""
        cat = self.dd_cat.value
        opts = SUBCATEGORIES.get(cat, ["Misc"])
        if opts != self.dd_subcat.options:
            self.dd_subcat.options = opts
            self.dd_subcat.index = 0
        # Auto-preenche grid_size quando muda subcategoria
        sub = self.dd_subcat.value
        if sub != self._last_subcat:
            self._last_subcat = sub
            def_wh = SUBCAT_DEFAULT_SIZE.get(sub, (1, 1))
            self.in_grid_w.text = str(def_wh[0])
            self.in_grid_h.text = str(def_wh[1])

    def load_from_data(self, data):
        self.in_name.text = data.get("name", "")
        self.in_desc.text = data.get("description", "")
        self.in_longdesc.text = data.get("long_description", "")

        cat = data.get("category", ITEM_CATEGORIES[0])
        self.dd_cat.index = ITEM_CATEGORIES.index(cat) if cat in ITEM_CATEGORIES else 0
        self.dd_subcat.options = SUBCATEGORIES.get(cat, ["Misc"])
        sub = data.get("subcategory", self.dd_subcat.options[0])
        self.dd_subcat.index = self.dd_subcat.options.index(sub) if sub in self.dd_subcat.options else 0
        rar = data.get("rarity", RARITIES[0])
        self.dd_rarity.index = RARITIES.index(rar) if rar in RARITIES else 0

        self.in_level.text = str(data.get("level_required", 1))
        self.in_value.text = str(data.get("value", 0))
        self.in_weight.text = str(data.get("weight", 0))
        self.in_tags.text = ", ".join(data.get("tags", []))
        self.tg_stack.selected = data.get("stackable", False)
        self.in_maxstk.text = str(data.get("max_stack", 1))

        # Icon e grid_size
        self.in_icon.text = data.get("icon", "")
        gs = data.get("grid_size", None)
        if isinstance(gs, (list, tuple)) and len(gs) == 2:
            self.in_grid_w.text = str(gs[0])
            self.in_grid_h.text = str(gs[1])
        else:
            def_wh = SUBCAT_DEFAULT_SIZE.get(self.dd_subcat.value, (1, 1))
            self.in_grid_w.text = str(def_wh[0])
            self.in_grid_h.text = str(def_wh[1])
        self._last_subcat = self.dd_subcat.value

        equip = data.get("equipment") or {}
        slot = equip.get("slot", EQUIP_SLOTS[0])
        self.dd_slot.index = EQUIP_SLOTS.index(slot) if slot in EQUIP_SLOTS else 0
        self.tg_2h.selected = equip.get("two_handed", False)
        dmg = equip.get("damage", {})
        self.in_dmgmin.text = str(dmg.get("min", 0))
        self.in_dmgmax.text = str(dmg.get("max", 0))
        dt_ = dmg.get("type", DAMAGE_TYPES[0])
        self.dd_dmgtype.index = DAMAGE_TYPES.index(dt_) if dt_ in DAMAGE_TYPES else 0
        self.in_armor.text = str(equip.get("armor", 0))

        mods = equip.get("stat_modifiers", {})
        for key, inp in self.stat_inputs.items():
            inp.text = str(mods.get(key, 0))
        res = equip.get("resistances", {})
        for key, inp in self.res_inputs.items():
            inp.text = str(res.get(key, 0))

        cons = data.get("consumable") or {}
        ct = cons.get("consume_type", "Instantâneo")
        self.dd_consume_type.index = ["Instantâneo","Permanente","Duração"].index(ct) \
                                      if ct in ("Instantâneo","Permanente","Duração") else 0
        tg = cons.get("target", "Si Mesmo")
        opts = ["Si Mesmo","Aliado Único","Todos os Aliados","Inimigo Único","Todos os Inimigos","Área"]
        self.dd_consume_target.index = opts.index(tg) if tg in opts else 0

        self.effects = []
        for e in (equip.get("special_effects", []) + cons.get("effects", [])):
            row = EffectRow(self.remove_effect, show_trigger=True)
            row.load_from(e)
            self.effects.append(row)
        if not self.effects: self.effects.append(EffectRow(self.remove_effect, show_trigger=True))
        self.refresh()

    def save_item(self):
        name = self.in_name.text.strip()
        if not name:
            self.show_message("Digite um nome para o item!", DANGER); return
        def as_int(s, d=0):
            try: return int(float(s))
            except Exception: return d
        def as_float(s, d=0.0):
            try: return float(s)
            except Exception: return d

        cat = self.dd_cat.value
        sub = self.dd_subcat.value
        rar = self.dd_rarity.value

        gs_w = min(4, max(1, as_int(self.in_grid_w.text, 1)))
        gs_h = min(4, max(1, as_int(self.in_grid_h.text, 1)))
        icon_text = self.in_icon.text.strip()
        if not icon_text:
            icon_text = (name[:1].upper() if name else "?")

        data = {
            "id": "item_" + slugify(name),
            "name": name,
            "description": self.in_desc.text.strip(),
            "long_description": self.in_longdesc.text.strip(),
            "category": cat,
            "subcategory": sub,
            "rarity": rar,
            "level_required": as_int(self.in_level.text, 1),
            "value": as_int(self.in_value.text, 0),
            "weight": as_float(self.in_weight.text, 0.0),
            "stackable": self.tg_stack.selected,
            "max_stack": as_int(self.in_maxstk.text, 1),
            "tags": [t.strip() for t in self.in_tags.text.split(",") if t.strip()],
            "icon": icon_text,
            "grid_size": [gs_w, gs_h],
            "equipment": None,
            "consumable": None,
        }

        if cat in ("Arma", "Armadura", "Acessório"):
            mods = {k: as_int(inp.text, 0) for k, inp in self.stat_inputs.items()}
            res  = {k: as_int(inp.text, 0) for k, inp in self.res_inputs.items()}
            eq_fx = [e.to_dict() for e in self.effects]
            data["equipment"] = {
                "slot": self.dd_slot.value,
                "two_handed": self.tg_2h.selected,
                "damage": {
                    "min": as_int(self.in_dmgmin.text, 0),
                    "max": as_int(self.in_dmgmax.text, 0),
                    "type": self.dd_dmgtype.value,
                },
                "armor": as_int(self.in_armor.text, 0),
                "stat_modifiers": mods,
                "resistances": res,
                "special_effects": eq_fx,
            }
        elif cat == "Consumível":
            data["consumable"] = {
                "consume_type": self.dd_consume_type.value,
                "target": self.dd_consume_target.value,
                "effects": [e.to_dict() for e in self.effects],
            }

        slug = slugify(name)
        path = os.path.join(ITEMS_DIR, slug + ".json")
        if self.editing_name and slugify(self.editing_name) != slug:
            old = os.path.join(ITEMS_DIR, slugify(self.editing_name) + ".json")
            if os.path.exists(old):
                try: os.remove(old)
                except Exception: pass

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.editing_name = name
            self.show_message("Salvo: " + os.path.relpath(path, BASE_DIR), SUCCESS)
        except Exception as ex:
            self.show_message("Erro ao salvar: " + str(ex), DANGER)

    def draw(self, surf, dt):
        surf.fill(BG)
        title = "EDITAR ITEM" if self.editing_name else "CRIADOR DE ITENS"
        draw_text(surf, title, 20, 15, FONT_XL, TEXT)
        draw_text(surf, "ESC = menu", WIDTH - 110, 22, FONT_S, TEXT_DIM)

        if self.current_tab == 0:
            draw_panel(surf, pygame.Rect(10, 100, WIDTH - 20, 185))
            draw_panel(surf, pygame.Rect(10, 295, WIDTH - 20, 210))
            draw_text(surf, "Tamanho = célula do grid (1-4 cada)",
                      990, 290, FONT_S, TEXT_HINT)
        elif self.current_tab == 1:
            draw_panel(surf, pygame.Rect(10, 100, WIDTH - 20, 145))
            draw_panel(surf, pygame.Rect(10, 255, WIDTH - 20, 260),
                       color=PANEL_REQ, border_color=BORDER_REQ)
        else:
            draw_panel(surf, pygame.Rect(10, 100, WIDTH - 20, 615))

        if self.current_tab == 1:
            draw_text(surf, "STAT MODIFIERS  (bônus aplicados quando equipado)",
                      20, 262, FONT_S, TEXT_HINT)
        if self.current_tab == 2:
            draw_text(surf, "EFEITOS ESPECIAIS",
                      20, 105, FONT_L, ACCENT)
            headers = [("TIPO", 20), ("VALOR", 250), ("DURAÇÃO", 330),
                       ("CHANCE %", 410), ("GATILHO", 490)]
            for text, x in headers:
                draw_text(surf, text, x, 140, FONT_S, TEXT_DIM)

        for w in self.all_widgets: w.draw(surf, dt)
        for d in self.all_dropdowns:
            if d.open: d.draw_list(surf)

        if self.current_tab == 2:
            draw_text(surf, "Efeitos: %d/%d" % (len(self.effects), self.MAX_EFFECTS),
                      540, 745, FONT_S, TEXT_DIM)
        if self.message:
            r = FONT_M.render(self.message, True, self.message_color)
            surf.blit(r, (WIDTH - 20 - r.get_width(), 720))


# ============================================================================
# Affix Creator
# ============================================================================
class AffixCreatorScene(Scene):
    MAX_EFFECTS = 3

    def __init__(self, app, go_back_factory=None, existing_data=None):
        super().__init__(app)
        self.go_back_factory = go_back_factory or (lambda: MenuScene(app))
        self.effects = []
        self.message = ""; self.message_color = SUCCESS; self.message_timer = 0.0
        self.editing_name = existing_data.get("name", "") if existing_data else ""

        # Header
        self.in_name = TextInput(20, 120, 400, 32, "NOME DO AFIXO", "ex: Flamejante")
        self.dd_kind = Dropdown(440, 120, 220, 32, "TIPO", AFFIX_KINDS, 0)
        self.dd_rarity = Dropdown(680, 120, 220, 32, "RARIDADE MÍNIMA", RARITIES, 1)
        self.in_desc = TextInput(920, 120, 340, 32, "DESCRIÇÃO", "ex: Envolvido em chamas")

        # Damage bonus
        self.dd_dmgtype = Dropdown(20, 215, 220, 32, "DANO EXTRA (tipo)", DAMAGE_TYPES, 1)
        self.in_dmgmin  = TextInput(260, 215, 120, 32, "DANO MÍN +", "0", "0")
        self.in_dmgmax  = TextInput(400, 215, 120, 32, "DANO MÁX +", "0", "0")

        # Applies to
        self.cat_toggles = []
        x = 20
        for cat in ITEM_CATEGORIES:
            tb = ToggleButton(x, 295, 140, 30, cat)
            self.cat_toggles.append((cat, tb))
            x += 145

        # Stat modifiers
        self.stat_inputs = {}
        rows_y = [385, 440, 495]
        for i, (key, label) in enumerate(STAT_MODS):
            row = i // 6; col = i % 6
            x = 20 + col * 208
            y = rows_y[row]
            self.stat_inputs[key] = TextInput(x, y, 195, 30, label, "0", "0")

        # Resistances
        self.res_inputs = {}
        for i, (key, label) in enumerate(RESIST_FIELDS):
            self.res_inputs[key] = TextInput(20 + i * 208, 550, 195, 30, label, "0", "0")

        # Effect rows
        self.effect_btn_add = Button(190, 735, 200, 42, "+ ADICIONAR EFEITO",
                                     self.add_effect, ACCENT)

        self.btn_back  = Button(20, 735, 160, 42, "VOLTAR",
                                lambda: app.change_scene(self.go_back_factory()), (90, 90, 110))
        self.btn_clear = Button(400, 735, 120, 42, "LIMPAR", self.clear_all, (90, 90, 110))
        self.btn_save  = Button(1000, 735, 260, 48, "SALVAR (.JSON)", self.save_affix, SUCCESS)

        if existing_data:
            self.load_from_data(existing_data)
        else:
            self.add_effect(silent=True)
            self.refresh()

    def refresh(self):
        self.all_widgets = [self.in_name, self.dd_kind, self.dd_rarity, self.in_desc,
                            self.dd_dmgtype, self.in_dmgmin, self.in_dmgmax,
                            self.effect_btn_add, self.btn_back, self.btn_clear, self.btn_save]
        self.all_inputs = [self.in_name, self.in_desc, self.in_dmgmin, self.in_dmgmax]
        self.all_dropdowns = [self.dd_kind, self.dd_rarity, self.dd_dmgtype]
        for cat, tb in self.cat_toggles:
            self.all_widgets.append(tb)
        for inp in self.stat_inputs.values():
            self.all_widgets.append(inp); self.all_inputs.append(inp)
        for inp in self.res_inputs.values():
            self.all_widgets.append(inp); self.all_inputs.append(inp)
        for i, row in enumerate(self.effects):
            row.set_y(645 + i * 34)
            self.all_widgets.extend(row.widgets)
            self.all_inputs.extend(row.inputs)
            self.all_dropdowns.extend(row.dropdowns)

    def add_effect(self, silent=False):
        if len(self.effects) >= self.MAX_EFFECTS:
            if not silent: self.show_message("Máx %d efeitos." % self.MAX_EFFECTS, WARN)
            return
        self.effects.append(EffectRow(self.remove_effect, show_trigger=True))
        self.refresh()

    def remove_effect(self, row):
        if row in self.effects: self.effects.remove(row)
        self.refresh()

    def clear_all(self):
        self.effects.clear()
        self.refresh()
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
        k = data.get("kind", "Prefixo")
        self.dd_kind.index = AFFIX_KINDS.index(k) if k in AFFIX_KINDS else 0
        r = data.get("rarity_min", RARITIES[0])
        self.dd_rarity.index = RARITIES.index(r) if r in RARITIES else 0
        applies = set(data.get("applies_to", []))
        for cat, tb in self.cat_toggles:
            tb.selected = cat in applies

        dmg = data.get("damage_bonus", {})
        self.in_dmgmin.text = str(dmg.get("min", 0))
        self.in_dmgmax.text = str(dmg.get("max", 0))
        dt_ = dmg.get("type", DAMAGE_TYPES[0])
        self.dd_dmgtype.index = DAMAGE_TYPES.index(dt_) if dt_ in DAMAGE_TYPES else 0

        mods = data.get("stat_modifiers", {})
        for k, inp in self.stat_inputs.items():
            inp.text = str(mods.get(k, 0))
        res = data.get("resistances", {})
        for k, inp in self.res_inputs.items():
            inp.text = str(res.get(k, 0))

        self.effects = []
        for e in data.get("special_effects", []):
            row = EffectRow(self.remove_effect, show_trigger=True)
            row.load_from(e)
            self.effects.append(row)
        if not self.effects:
            self.effects.append(EffectRow(self.remove_effect, show_trigger=True))
        self.refresh()

    def save_affix(self):
        name = self.in_name.text.strip()
        if not name:
            self.show_message("Digite o nome do afixo!", DANGER); return
        def as_int(s, d=0):
            try: return int(float(s))
            except Exception: return d

        applies = [cat for cat, tb in self.cat_toggles if tb.selected]
        if not applies:
            self.show_message("Marque pelo menos uma categoria em 'APLICA A'.", DANGER); return

        kind = self.dd_kind.value
        mods = {k: as_int(inp.text, 0) for k, inp in self.stat_inputs.items()}
        res  = {k: as_int(inp.text, 0) for k, inp in self.res_inputs.items()}
        dmg  = {
            "min": as_int(self.in_dmgmin.text, 0),
            "max": as_int(self.in_dmgmax.text, 0),
            "type": self.dd_dmgtype.value,
        }
        prefix = "prefix_" if kind == "Prefixo" else "suffix_"
        data = {
            "id": prefix + slugify(name),
            "name": name,
            "kind": kind,
            "rarity_min": self.dd_rarity.value,
            "applies_to": applies,
            "description": self.in_desc.text.strip(),
            "damage_bonus": dmg,
            "stat_modifiers": mods,
            "resistances": res,
            "special_effects": [e.to_dict() for e in self.effects],
        }
        slug = slugify(name)
        path = os.path.join(AFFIXES_DIR, prefix + slug + ".json")
        if self.editing_name and slugify(self.editing_name) != slug:
            old = os.path.join(AFFIXES_DIR, prefix + slugify(self.editing_name) + ".json")
            if os.path.exists(old):
                try: os.remove(old)
                except Exception: pass
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.editing_name = name
            self.show_message("Salvo: " + os.path.relpath(path, BASE_DIR), SUCCESS)
        except Exception as ex:
            self.show_message("Erro: " + str(ex), DANGER)

    def draw(self, surf, dt):
        surf.fill(BG)
        title = "EDITAR AFIXO" if self.editing_name else "CRIADOR DE PREFIXOS / SUFIXOS"
        draw_text(surf, title, 20, 15, FONT_XL, TEXT)
        draw_text(surf, "ESC = menu", WIDTH - 110, 22, FONT_S, TEXT_DIM)

        draw_panel(surf, pygame.Rect(10, 90, WIDTH - 20, 90))                                 # Header
        draw_panel(surf, pygame.Rect(10, 190, WIDTH - 20, 70))                                # Dano
        draw_panel(surf, pygame.Rect(10, 270, WIDTH - 20, 70))                                # Aplica a
        draw_panel(surf, pygame.Rect(10, 350, WIDTH - 20, 240),
                   color=PANEL_REQ, border_color=BORDER_REQ)                                  # Stats
        draw_panel(surf, pygame.Rect(10, 600, WIDTH - 20, 120))                               # Efeitos

        draw_text(surf, "APLICA A (categorias onde este afixo pode aparecer)",
                  20, 275, FONT_S, TEXT_HINT)
        draw_text(surf, "STAT MODIFIERS (bônus somados ao item base)",
                  20, 357, FONT_S, TEXT_HINT)
        draw_text(surf, "EFEITOS ESPECIAIS", 20, 605, FONT_L, ACCENT)
        headers = [("TIPO", 20), ("VALOR", 250), ("DURAÇÃO", 330),
                   ("CHANCE %", 410), ("GATILHO", 490)]
        for text, x in headers:
            draw_text(surf, text, x, 625, FONT_S, TEXT_DIM)

        for w in self.all_widgets: w.draw(surf, dt)
        for d in self.all_dropdowns:
            if d.open: d.draw_list(surf)

        draw_text(surf, "Efeitos: %d/%d" % (len(self.effects), self.MAX_EFFECTS),
                  540, 745, FONT_S, TEXT_DIM)
        if self.message:
            r = FONT_M.render(self.message, True, self.message_color)
            surf.blit(r, (WIDTH - 20 - r.get_width(), 720))


# ============================================================================
# Item Manager
# ============================================================================
class ItemManagerScene(Scene):
    ROW_H = 66
    LIST_TOP = 145
    LIST_BOTTOM = 725
    TITLE = "ITENS E EQUIPAMENTOS"
    NEW_LABEL = "+ NOVO ITEM"
    DIR = ITEMS_DIR

    def __init__(self, app, go_back_factory=None):
        super().__init__(app)
        self.go_back_factory = go_back_factory or (lambda: MenuScene(app))
        self.entities = []
        self.filtered = []
        self.scroll = 0; self.max_scroll = 0
        self.message = ""; self.message_color = SUCCESS; self.message_timer = 0.0
        self._last_search = ""; self._last_cat = 0; self._last_rar = 0

        self.search_input = TextInput(20, 100, 500, 34, "", "Buscar item...")
        self.cat_dd = Dropdown(540, 100, 280, 34, "", ["Todas"] + ITEM_CATEGORIES, 0)
        self.rar_dd = Dropdown(830, 100, 240, 34, "", ["Todas"] + RARITIES, 0)
        self.btn_clear_search = Button(500, 100, 32, 34, "x", self._clear_search,
                                       color=(120, 90, 90), font=FONT_S)

        self.btn_back = Button(20, 55, 130, 38, "VOLTAR",
                               lambda: app.change_scene(self.go_back_factory()), (90, 90, 110))
        self.btn_refresh = Button(158, 55, 130, 38, "ATUALIZAR", self.load_data, ACCENT)
        self.btn_new = Button(WIDTH - 250, 55, 230, 38, self.NEW_LABEL,
                              self._new_entity, SUCCESS)

        self.rename_index = -1
        self.rename_input = TextInput(0, 0, 460, 42, "NOVO NOME", "", "")
        self.rename_ok = Button(0, 0, 140, 42, "RENOMEAR", self._confirm_rename, SUCCESS)
        self.rename_cancel = Button(0, 0, 140, 42, "CANCELAR", self._cancel_rename, (90, 90, 110))
        self.delete_index = -1
        self.delete_yes = Button(0, 0, 160, 42, "EXCLUIR", self._confirm_delete, DANGER)
        self.delete_no = Button(0, 0, 160, 42, "CANCELAR", self._cancel_delete, (90, 90, 110))

        self.all_widgets = [self.btn_back, self.btn_refresh, self.btn_new,
                            self.search_input, self.cat_dd, self.rar_dd, self.btn_clear_search]
        self.all_inputs = [self.search_input]
        self.all_dropdowns = [self.cat_dd, self.rar_dd]
        self.load_data()

    def load_data(self):
        self.entities = load_json_files(self.DIR)
        self._apply_filters()
        self.show_message("%d item(ns) carregado(s)." % len(self.entities), TEXT_DIM)

    def _apply_filters(self):
        q = self.search_input.text.strip().lower()
        cat = self.cat_dd.value
        rar = self.rar_dd.value
        out = []
        for ent in self.entities:
            data = ent["data"]
            if q and q not in data.get("name", "").lower(): continue
            if cat != "Todas" and data.get("category", "") != cat: continue
            if rar != "Todas" and data.get("rarity", "") != rar: continue
            out.append(ent)
        self.filtered = out
        total_h = len(self.filtered) * self.ROW_H
        view_h = self.LIST_BOTTOM - self.LIST_TOP
        self.max_scroll = max(0, total_h - view_h)
        self.scroll = max(0, min(self.scroll, self.max_scroll))

    def _clear_search(self):
        self.search_input.text = ""; self.search_input.active = False
        self._apply_filters()

    def show_message(self, msg, color=SUCCESS):
        self.message = msg; self.message_color = color; self.message_timer = 3.0

    def _row_buttons(self, y):
        return {
            "edit":   pygame.Rect(760, y + 15, 105, 36),
            "dup":    pygame.Rect(875, y + 15, 110, 36),
            "rename": pygame.Rect(995, y + 15, 115, 36),
            "delete": pygame.Rect(1120, y + 15, 130, 36),
        }

    def _visible_rows(self):
        for i, ent in enumerate(self.filtered):
            y = self.LIST_TOP + i * self.ROW_H - self.scroll
            if y + self.ROW_H > self.LIST_TOP and y < self.LIST_BOTTOM:
                yield i, y

    def _new_entity(self): self.app.change_scene(ItemCreatorScene(self.app))
    def _edit_entity(self, idx):
        self.app.change_scene(ItemCreatorScene(self.app, existing_data=self.filtered[idx]["data"]))

    def _duplicate_entity(self, idx):
        data = dict(self.filtered[idx]["data"])
        old_name = data.get("name", "item")
        counter = 1
        new_name = "%s (Cópia)" % old_name
        new_slug = slugify(new_name)
        while os.path.exists(os.path.join(self.DIR, new_slug + ".json")):
            counter += 1
            new_name = "%s (Cópia %d)" % (old_name, counter)
            new_slug = slugify(new_name)
        data["name"] = new_name
        data["id"] = "item_" + new_slug
        path = os.path.join(self.DIR, new_slug + ".json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.load_data()
            self.show_message("Duplicado: " + new_name, SUCCESS)
        except Exception as ex: self.show_message("Erro: " + str(ex), DANGER)

    def _open_rename(self, idx):
        self.rename_index = idx
        self.rename_input.text = self.filtered[idx]["data"].get("name", "")
        self.rename_input.active = True
    def _confirm_rename(self):
        if self.rename_index < 0: return
        new_name = self.rename_input.text.strip()
        if not new_name: self.show_message("Nome vazio!", DANGER); return
        ent = self.filtered[self.rename_index]
        data = dict(ent["data"]); data["name"] = new_name
        data["id"] = "item_" + slugify(new_name)
        new_path = os.path.join(self.DIR, slugify(new_name) + ".json")
        try:
            if ent["path"] != new_path and os.path.exists(ent["path"]): os.remove(ent["path"])
            with open(new_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.rename_index = -1; self.rename_input.active = False
            self.load_data()
            self.show_message("Renomeado: " + new_name, SUCCESS)
        except Exception as ex: self.show_message("Erro: " + str(ex), DANGER)
    def _cancel_rename(self): self.rename_index = -1; self.rename_input.active = False
    def _open_delete(self, idx): self.delete_index = idx
    def _confirm_delete(self):
        if self.delete_index < 0: return
        ent = self.filtered[self.delete_index]
        try:
            if os.path.exists(ent["path"]): os.remove(ent["path"])
            self.delete_index = -1
            self.load_data()
            self.show_message("Excluído.", WARN)
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
                    self.search_input.active = False; return
                self.app.change_scene(MenuScene(self.app)); return
            if e.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self.LIST_TOP <= my <= self.LIST_BOTTOM:
                    self.scroll = max(0, min(self.max_scroll, self.scroll - e.y * 40))
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.cat_dd.open and not self.cat_dd.list_rect().collidepoint(e.pos):
                    self.cat_dd.open = False
                if self.rar_dd.open and not self.rar_dd.list_rect().collidepoint(e.pos):
                    self.rar_dd.open = False
                if self.search_input.active and not self.search_input.rect.collidepoint(e.pos):
                    self.search_input.active = False
                if self.LIST_TOP <= e.pos[1] <= self.LIST_BOTTOM:
                    for i, y in self._visible_rows():
                        btns = self._row_buttons(y)
                        if btns["edit"].collidepoint(e.pos):   self._edit_entity(i); return
                        if btns["dup"].collidepoint(e.pos):    self._duplicate_entity(i); return
                        if btns["rename"].collidepoint(e.pos): self._open_rename(i); return
                        if btns["delete"].collidepoint(e.pos): self._open_delete(i); return
            for w in self.all_widgets: w.handle_event(e)

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0: self.message = ""
        if self.search_input.text != self._last_search:
            self._last_search = self.search_input.text; self.scroll = 0; self._apply_filters()
        if self.cat_dd.index != self._last_cat:
            self._last_cat = self.cat_dd.index; self.scroll = 0; self._apply_filters()
        if self.rar_dd.index != self._last_rar:
            self._last_rar = self.rar_dd.index; self.scroll = 0; self._apply_filters()

    def draw(self, surf, dt):
        surf.fill(BG)
        draw_text(surf, self.TITLE, 20, 15, FONT_XL, TEXT)
        count_txt = "%d de %d" % (len(self.filtered), len(self.entities))
        draw_text(surf, count_txt, WIDTH - 20 - FONT_M.size(count_txt)[0], 22, FONT_M, TEXT_DIM)
        for w in self.all_widgets: w.draw(surf, dt)
        for d in self.all_dropdowns:
            if d.open: d.draw_list(surf)

        list_rect = pygame.Rect(10, self.LIST_TOP - 5, WIDTH - 20,
                                self.LIST_BOTTOM - self.LIST_TOP + 10)
        draw_panel(surf, list_rect)
        old_clip = surf.get_clip(); surf.set_clip(list_rect.inflate(-4, -4))

        if not self.entities:
            draw_text(surf, "Nenhum item salvo ainda.", WIDTH // 2, self.LIST_TOP + 60,
                      FONT_L, TEXT_DIM, center_x=True)
        elif not self.filtered:
            draw_text(surf, "Nenhum item corresponde à busca/filtro.", WIDTH // 2,
                      self.LIST_TOP + 60, FONT_L, TEXT_DIM, center_x=True)

        mx, my = pygame.mouse.get_pos()
        for i, y in self._visible_rows():
            data = self.filtered[i]["data"]
            row_rect = pygame.Rect(15, y, WIDTH - 30, self.ROW_H - 4)
            col = PANEL if i % 2 == 0 else (42, 46, 58)
            pygame.draw.rect(surf, col, row_rect, border_radius=6)
            rar = data.get("rarity", "Comum")
            rcol = RARITY_COLORS.get(rar, TEXT_DIM)
            pygame.draw.rect(surf, rcol, pygame.Rect(15, y, 5, self.ROW_H - 4), border_radius=3)

            name = data.get("name", "?")
            cat = data.get("category", "-")
            sub = data.get("subcategory", "-")
            lvl = data.get("level_required", 1)
            val = data.get("value", 0)
            eq = data.get("equipment") or {}
            dmg = eq.get("damage", {})
            info = "%s · %s · %s · Lvl %s · %s ouro" % (cat, sub, rar, lvl, val)
            if dmg.get("max", 0) > 0:
                info += "  ·  Dano %s-%s %s" % (dmg.get("min",0), dmg.get("max",0), dmg.get("type", "-"))

            draw_text(surf, fit_text(name, FONT_L, 700), 30, y + 8, FONT_L, rcol)
            draw_text(surf, fit_text(info, FONT_S, 700), 30, y + 34, FONT_S, TEXT_DIM)

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
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill(OVERLAY); surf.blit(overlay, (0, 0))
        pw, ph = 600, 200
        px = (WIDTH - pw)//2; py = (HEIGHT - ph)//2
        draw_panel(surf, pygame.Rect(px, py, pw, ph), PANEL)
        draw_text(surf, "RENOMEAR ITEM", px + 20, py + 18, FONT_L, TEXT)
        old = self.filtered[self.rename_index]["data"].get("name", "")
        draw_text(surf, "Atual: " + fit_text(old, FONT_S, pw - 40), px + 20, py + 48, FONT_S, TEXT_DIM)
        self.rename_input.rect = pygame.Rect(px + 20, py + 80, pw - 40, 42)
        self.rename_input.draw(surf, dt)
        self.rename_cancel.rect = pygame.Rect(px + 20, py + 140, 160, 42)
        self.rename_ok.rect = pygame.Rect(px + pw - 180, py + 140, 160, 42)
        self.rename_cancel.draw(surf, dt); self.rename_ok.draw(surf, dt)

    def _draw_delete_modal(self, surf, dt):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill(OVERLAY); surf.blit(overlay, (0, 0))
        pw, ph = 560, 170
        px = (WIDTH - pw)//2; py = (HEIGHT - ph)//2
        draw_panel(surf, pygame.Rect(px, py, pw, ph), PANEL)
        draw_text(surf, "EXCLUIR ITEM?", px + 20, py + 18, FONT_L, DANGER)
        nm = self.filtered[self.delete_index]["data"].get("name", "")
        draw_text(surf, fit_text(nm, FONT_M, pw - 40), px + 20, py + 55, FONT_M, TEXT)
        draw_text(surf, "Essa ação não pode ser desfeita.", px + 20, py + 82, FONT_S, TEXT_DIM)
        self.delete_no.rect = pygame.Rect(px + 20, py + 110, 180, 42)
        self.delete_yes.rect = pygame.Rect(px + pw - 200, py + 110, 180, 42)
        self.delete_no.draw(surf, dt); self.delete_yes.draw(surf, dt)


# ============================================================================
# Affix Manager
# ============================================================================
class AffixManagerScene(Scene):
    ROW_H = 66
    LIST_TOP = 145
    LIST_BOTTOM = 725
    TITLE = "PREFIXOS E SUFIXOS"
    NEW_LABEL = "+ NOVO AFIXO"
    DIR = AFFIXES_DIR

    def __init__(self, app, go_back_factory=None):
        super().__init__(app)
        self.go_back_factory = go_back_factory or (lambda: MenuScene(app))
        self.entities = []
        self.filtered = []
        self.scroll = 0; self.max_scroll = 0
        self.message = ""; self.message_color = SUCCESS; self.message_timer = 0.0
        self._last_search = ""; self._last_kind = 0; self._last_rar = 0

        self.search_input = TextInput(20, 100, 500, 34, "", "Buscar afixo...")
        self.kind_dd = Dropdown(540, 100, 240, 34, "", ["Todos"] + AFFIX_KINDS, 0)
        self.rar_dd = Dropdown(790, 100, 280, 34, "", ["Todas"] + RARITIES, 0)
        self.btn_clear_search = Button(500, 100, 32, 34, "x", self._clear_search,
                                       color=(120, 90, 90), font=FONT_S)

        self.btn_back = Button(20, 55, 130, 38, "VOLTAR",
                               lambda: app.change_scene(self.go_back_factory()), (90, 90, 110))
        self.btn_refresh = Button(158, 55, 130, 38, "ATUALIZAR", self.load_data, ACCENT)
        self.btn_new = Button(WIDTH - 250, 55, 230, 38, self.NEW_LABEL,
                              self._new_entity, SUCCESS)

        self.rename_index = -1
        self.rename_input = TextInput(0, 0, 460, 42, "NOVO NOME", "", "")
        self.rename_ok = Button(0, 0, 140, 42, "RENOMEAR", self._confirm_rename, SUCCESS)
        self.rename_cancel = Button(0, 0, 140, 42, "CANCELAR", self._cancel_rename, (90, 90, 110))
        self.delete_index = -1
        self.delete_yes = Button(0, 0, 160, 42, "EXCLUIR", self._confirm_delete, DANGER)
        self.delete_no = Button(0, 0, 160, 42, "CANCELAR", self._cancel_delete, (90, 90, 110))

        self.all_widgets = [self.btn_back, self.btn_refresh, self.btn_new,
                            self.search_input, self.kind_dd, self.rar_dd, self.btn_clear_search]
        self.all_inputs = [self.search_input]
        self.all_dropdowns = [self.kind_dd, self.rar_dd]
        self.load_data()

    def load_data(self):
        self.entities = load_json_files(self.DIR)
        self._apply_filters()
        self.show_message("%d afixo(s) carregado(s)." % len(self.entities), TEXT_DIM)

    def _apply_filters(self):
        q = self.search_input.text.strip().lower()
        kind = self.kind_dd.value
        rar = self.rar_dd.value
        out = []
        for ent in self.entities:
            data = ent["data"]
            if q and q not in data.get("name", "").lower(): continue
            if kind != "Todos" and data.get("kind", "") != kind: continue
            if rar != "Todas" and data.get("rarity_min", "") != rar: continue
            out.append(ent)
        self.filtered = out
        total_h = len(self.filtered) * self.ROW_H
        view_h = self.LIST_BOTTOM - self.LIST_TOP
        self.max_scroll = max(0, total_h - view_h)
        self.scroll = max(0, min(self.scroll, self.max_scroll))

    def _clear_search(self):
        self.search_input.text = ""; self.search_input.active = False
        self._apply_filters()

    def show_message(self, msg, color=SUCCESS):
        self.message = msg; self.message_color = color; self.message_timer = 3.0

    def _row_buttons(self, y):
        return {
            "edit":   pygame.Rect(760, y + 15, 105, 36),
            "dup":    pygame.Rect(875, y + 15, 110, 36),
            "rename": pygame.Rect(995, y + 15, 115, 36),
            "delete": pygame.Rect(1120, y + 15, 130, 36),
        }

    def _visible_rows(self):
        for i, ent in enumerate(self.filtered):
            y = self.LIST_TOP + i * self.ROW_H - self.scroll
            if y + self.ROW_H > self.LIST_TOP and y < self.LIST_BOTTOM:
                yield i, y

    def _new_entity(self): self.app.change_scene(AffixCreatorScene(self.app))
    def _edit_entity(self, idx):
        self.app.change_scene(AffixCreatorScene(self.app, existing_data=self.filtered[idx]["data"]))

    def _duplicate_entity(self, idx):
        data = dict(self.filtered[idx]["data"])
        old_name = data.get("name", "afixo")
        counter = 1
        new_name = "%s (Cópia)" % old_name
        kind = data.get("kind", "Prefixo")
        prefix = "prefix_" if kind == "Prefixo" else "suffix_"
        new_slug = slugify(new_name)
        while os.path.exists(os.path.join(self.DIR, prefix + new_slug + ".json")):
            counter += 1
            new_name = "%s (Cópia %d)" % (old_name, counter)
            new_slug = slugify(new_name)
        data["name"] = new_name
        data["id"] = prefix + new_slug
        path = os.path.join(self.DIR, prefix + new_slug + ".json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.load_data()
            self.show_message("Duplicado: " + new_name, SUCCESS)
        except Exception as ex: self.show_message("Erro: " + str(ex), DANGER)

    def _open_rename(self, idx):
        self.rename_index = idx
        self.rename_input.text = self.filtered[idx]["data"].get("name", "")
        self.rename_input.active = True
    def _confirm_rename(self):
        if self.rename_index < 0: return
        new_name = self.rename_input.text.strip()
        if not new_name: self.show_message("Nome vazio!", DANGER); return
        ent = self.filtered[self.rename_index]
        data = dict(ent["data"]); data["name"] = new_name
        kind = data.get("kind", "Prefixo")
        prefix = "prefix_" if kind == "Prefixo" else "suffix_"
        data["id"] = prefix + slugify(new_name)
        new_path = os.path.join(self.DIR, prefix + slugify(new_name) + ".json")
        try:
            if ent["path"] != new_path and os.path.exists(ent["path"]): os.remove(ent["path"])
            with open(new_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.rename_index = -1; self.rename_input.active = False
            self.load_data()
            self.show_message("Renomeado: " + new_name, SUCCESS)
        except Exception as ex: self.show_message("Erro: " + str(ex), DANGER)
    def _cancel_rename(self): self.rename_index = -1; self.rename_input.active = False
    def _open_delete(self, idx): self.delete_index = idx
    def _confirm_delete(self):
        if self.delete_index < 0: return
        ent = self.filtered[self.delete_index]
        try:
            if os.path.exists(ent["path"]): os.remove(ent["path"])
            self.delete_index = -1
            self.load_data()
            self.show_message("Excluído.", WARN)
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
                    self.search_input.active = False; return
                self.app.change_scene(MenuScene(self.app)); return
            if e.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self.LIST_TOP <= my <= self.LIST_BOTTOM:
                    self.scroll = max(0, min(self.max_scroll, self.scroll - e.y * 40))
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for dd in (self.kind_dd, self.rar_dd):
                    if dd.open and not dd.list_rect().collidepoint(e.pos): dd.open = False
                if self.search_input.active and not self.search_input.rect.collidepoint(e.pos):
                    self.search_input.active = False
                if self.LIST_TOP <= e.pos[1] <= self.LIST_BOTTOM:
                    for i, y in self._visible_rows():
                        btns = self._row_buttons(y)
                        if btns["edit"].collidepoint(e.pos):   self._edit_entity(i); return
                        if btns["dup"].collidepoint(e.pos):    self._duplicate_entity(i); return
                        if btns["rename"].collidepoint(e.pos): self._open_rename(i); return
                        if btns["delete"].collidepoint(e.pos): self._open_delete(i); return
            for w in self.all_widgets: w.handle_event(e)

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0: self.message = ""
        if self.search_input.text != self._last_search:
            self._last_search = self.search_input.text; self.scroll = 0; self._apply_filters()
        if self.kind_dd.index != self._last_kind:
            self._last_kind = self.kind_dd.index; self.scroll = 0; self._apply_filters()
        if self.rar_dd.index != self._last_rar:
            self._last_rar = self.rar_dd.index; self.scroll = 0; self._apply_filters()

    def draw(self, surf, dt):
        surf.fill(BG)
        draw_text(surf, self.TITLE, 20, 15, FONT_XL, TEXT)
        count_txt = "%d de %d" % (len(self.filtered), len(self.entities))
        draw_text(surf, count_txt, WIDTH - 20 - FONT_M.size(count_txt)[0], 22, FONT_M, TEXT_DIM)
        for w in self.all_widgets: w.draw(surf, dt)
        for d in self.all_dropdowns:
            if d.open: d.draw_list(surf)

        list_rect = pygame.Rect(10, self.LIST_TOP - 5, WIDTH - 20,
                                self.LIST_BOTTOM - self.LIST_TOP + 10)
        draw_panel(surf, list_rect)
        old_clip = surf.get_clip(); surf.set_clip(list_rect.inflate(-4, -4))

        if not self.entities:
            draw_text(surf, "Nenhum afixo salvo ainda.", WIDTH // 2, self.LIST_TOP + 60,
                      FONT_L, TEXT_DIM, center_x=True)
        elif not self.filtered:
            draw_text(surf, "Nenhum afixo corresponde à busca/filtro.", WIDTH // 2,
                      self.LIST_TOP + 60, FONT_L, TEXT_DIM, center_x=True)

        mx, my = pygame.mouse.get_pos()
        for i, y in self._visible_rows():
            data = self.filtered[i]["data"]
            row_rect = pygame.Rect(15, y, WIDTH - 30, self.ROW_H - 4)
            col = PANEL if i % 2 == 0 else (42, 46, 58)
            pygame.draw.rect(surf, col, row_rect, border_radius=6)
            rar = data.get("rarity_min", "Comum")
            rcol = RARITY_COLORS.get(rar, TEXT_DIM)
            pygame.draw.rect(surf, rcol, pygame.Rect(15, y, 5, self.ROW_H - 4), border_radius=3)

            name = data.get("name", "?")
            kind = data.get("kind", "-")
            applies = ", ".join(data.get("applies_to", []))
            info = "%s · Raridade mín: %s · Aplica a: %s" % (kind, rar, applies)

            display_name = name
            if kind == "Prefixo": display_name = name + " ..."
            elif kind == "Sufixo": display_name = "... " + name

            draw_text(surf, fit_text(display_name, FONT_L, 700), 30, y + 8, FONT_L, rcol)
            draw_text(surf, fit_text(info, FONT_S, 700), 30, y + 34, FONT_S, TEXT_DIM)

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
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill(OVERLAY); surf.blit(overlay, (0, 0))
        pw, ph = 600, 200
        px = (WIDTH - pw)//2; py = (HEIGHT - ph)//2
        draw_panel(surf, pygame.Rect(px, py, pw, ph), PANEL)
        draw_text(surf, "RENOMEAR AFIXO", px + 20, py + 18, FONT_L, TEXT)
        old = self.filtered[self.rename_index]["data"].get("name", "")
        draw_text(surf, "Atual: " + fit_text(old, FONT_S, pw - 40), px + 20, py + 48, FONT_S, TEXT_DIM)
        self.rename_input.rect = pygame.Rect(px + 20, py + 80, pw - 40, 42)
        self.rename_input.draw(surf, dt)
        self.rename_cancel.rect = pygame.Rect(px + 20, py + 140, 160, 42)
        self.rename_ok.rect = pygame.Rect(px + pw - 180, py + 140, 160, 42)
        self.rename_cancel.draw(surf, dt); self.rename_ok.draw(surf, dt)

    def _draw_delete_modal(self, surf, dt):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill(OVERLAY); surf.blit(overlay, (0, 0))
        pw, ph = 560, 170
        px = (WIDTH - pw)//2; py = (HEIGHT - ph)//2
        draw_panel(surf, pygame.Rect(px, py, pw, ph), PANEL)
        draw_text(surf, "EXCLUIR AFIXO?", px + 20, py + 18, FONT_L, DANGER)
        nm = self.filtered[self.delete_index]["data"].get("name", "")
        draw_text(surf, fit_text(nm, FONT_M, pw - 40), px + 20, py + 55, FONT_M, TEXT)
        draw_text(surf, "Essa ação não pode ser desfeita.", px + 20, py + 82, FONT_S, TEXT_DIM)
        self.delete_no.rect = pygame.Rect(px + 20, py + 110, 180, 42)
        self.delete_yes.rect = pygame.Rect(px + pw - 200, py + 110, 180, 42)
        self.delete_no.draw(surf, dt); self.delete_yes.draw(surf, dt)


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
        self.tab_items  = ToggleButton(230, 75, 160, 40, "ITENS")
        self.tab_affix  = ToggleButton(400, 75, 200, 40, "PREFIXOS/SUFIXOS")
        self.tab_auto.selected = True
        self.tab_auto.callback   = lambda: self.set_mode("auto")
        self.tab_items.callback  = lambda: self.set_mode("items")
        self.tab_affix.callback  = lambda: self.set_mode("affixes")

        self.text_area = TextArea(
            20, 155, WIDTH - 40, 470,
            label="COLE O TEXTO JSON AQUI  (Ctrl+V para colar)",
            placeholder='Exemplos: { "name": "...", "category": "Arma", ... } ou [ { ... }, { ... } ]'
        )
        self.btn_back = Button(20, 730, 160, 42, "VOLTAR",
                               lambda: app.change_scene(self.go_back_factory()), (90, 90, 110))
        self.btn_clear = Button(200, 730, 140, 42, "LIMPAR", self.clear, (90, 90, 110))
        self.btn_import = Button(1000, 727, 260, 48, "IMPORTAR AGORA", self.do_import, SUCCESS)

        self.all_widgets = [self.tab_auto, self.tab_items, self.tab_affix,
                            self.text_area, self.btn_back, self.btn_clear, self.btn_import]
        self.all_inputs = [self.text_area]
        self.all_dropdowns = []

    def set_mode(self, mode):
        self.mode = mode
        self.tab_auto.selected  = (mode == "auto")
        self.tab_items.selected = (mode == "items")
        self.tab_affix.selected = (mode == "affixes")

    def clear(self):
        self.text_area.text = ""; self.last_errors = []
        self.show_message("Texto limpo.", TEXT_DIM)

    def show_message(self, msg, color=SUCCESS):
        self.message = msg; self.message_color = color; self.message_timer = 6.0

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0: self.message = ""

    def _save(self, item, directory, prefix):
        try:
            name = str(item.get("name", "")).strip()
            if not name: return False, "sem 'name'"
            kind = item.get("kind", "")
            if kind == "Sufixo": file_prefix = "suffix_"
            else: file_prefix = prefix
            path = os.path.join(directory, file_prefix + slugify(name) + ".json")
            if "id" not in item or not item["id"]:
                item["id"] = file_prefix + slugify(name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(item, f, ensure_ascii=False, indent=2)
            return True, None
        except Exception as ex:
            return False, str(ex)

    def do_import(self):
        raw = self.text_area.text.strip()
        if not raw:
            self.show_message("Cole um JSON.", WARN); return
        items = parse_json_items(raw)
        if not items:
            self.show_message("Nenhum JSON válido encontrado.", DANGER); return
        self.last_errors = []
        kinds = [detect_kind(it) for it in items]

        if self.mode == "auto":
            n_items = n_affixes = 0
            errors = []; unknown = []
            for i, (it, kind) in enumerate(zip(items, kinds)):
                name = str(it.get("name", "?"))
                if kind == "item":
                    ok, err = self._save(it, ITEMS_DIR, "item_")
                    if ok: n_items += 1
                    else: errors.append("%s: %s" % (name, err))
                elif kind == "affix":
                    ok, err = self._save(it, AFFIXES_DIR, "prefix_")
                    if ok: n_affixes += 1
                    else: errors.append("%s: %s" % (name, err))
                else:
                    unknown.append("%s [item %d]" % (name, i+1))
            parts = []
            if n_items:   parts.append("%d item(s)" % n_items)
            if n_affixes: parts.append("%d afixo(s)" % n_affixes)
            summary = " + ".join(parts) if parts else "0"
            if (n_items or n_affixes) and not unknown and not errors:
                self.show_message("OK! Importado: " + summary, SUCCESS)
            elif n_items or n_affixes:
                self.show_message("Importado: %s. %d ignorado(s)." % (summary, len(unknown)+len(errors)), WARN)
            else:
                self.show_message("Nada importado.", DANGER)
            self.last_errors = (["Ignorado: " + u for u in unknown[:8]] + errors[:8])[:10]
            return

        expected = "item" if self.mode == "items" else "affix"
        target_dir = ITEMS_DIR if expected == "item" else AFFIXES_DIR
        prefix = "item_" if expected == "item" else "prefix_"
        word = "ITEM" if expected == "item" else "AFIXO"
        other = "AFIXO" if expected == "item" else "ITEM"
        n_other = n_unknown = 0; other_names = []; unknown_names = []
        for i, (it, kind) in enumerate(zip(items, kinds)):
            name = str(it.get("name", "?"))
            if kind == expected: continue
            elif kind == "unknown":
                n_unknown += 1; unknown_names.append("%s (item %d)" % (name, i+1))
            else:
                n_other += 1; other_names.append(name)
        if n_other > 0:
            self.last_errors = (["Tipo errado (%s): %s" % (other.lower(), nm) for nm in other_names[:8]])[:10]
            self.show_message("BLOQUEADO: %d %s(s) na aba %s." % (n_other, other, word), DANGER)
            return
        if n_unknown > 0:
            self.last_errors = ["Ambíguo: " + nm for nm in unknown_names[:10]]
            self.show_message("BLOQUEADO: %d item(ns) ambíguo." % n_unknown, DANGER)
            return
        imported = 0; errors = []
        for it in items:
            name = str(it.get("name", "?"))
            ok, err = self._save(it, target_dir, prefix)
            if ok: imported += 1
            else: errors.append("%s: %s" % (name, err))
        if imported and not errors:
            self.show_message("OK! %d %s(s) importado(s)." % (imported, word.lower()), SUCCESS)
        elif imported and errors:
            self.show_message("%d importado(s), %d com erro." % (imported, len(errors)), WARN)
        else:
            self.show_message("Nada importado.", DANGER)
        self.last_errors = errors[:10]

    def draw(self, surf, dt):
        surf.fill(BG)
        draw_text(surf, "IMPORTAR ITENS E AFIXOS (JSON)", 20, 15, FONT_XL, TEXT)
        draw_text(surf, "ESC = menu", WIDTH - 110, 22, FONT_S, TEXT_DIM)
        draw_text(surf, "DESTINO:", 20, 55, FONT_S, TEXT_DIM)
        for tb in (self.tab_auto, self.tab_items, self.tab_affix): tb.draw(surf, dt)
        if self.mode == "auto":
            hint = "AUTO: itens vão para /items, afixos para /affixes."
        elif self.mode == "items":
            hint = "ITENS: aceita só itens. Bloqueia afixos."
        else:
            hint = "AFIXOS: aceita só prefixos/sufixos. Bloqueia itens."
        draw_text(surf, hint, 20, 122, FONT_S, TEXT_DIM)
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