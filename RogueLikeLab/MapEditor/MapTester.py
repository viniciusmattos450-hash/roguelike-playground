# -*- coding: utf-8 -*-
"""
MapTester.py v3.1 — Isométrico com rotação e oclusão.

- Q/E: rotaciona a vista isométrica em 90°
- T: alterna isométrico / top-down
- Paredes que escondem o player ficam translúcidas automaticamente
- Player spawna no evento 'player_spawn' (kind ou tag)
- LMB: mover (pathfinding)  ·  WASD/Setas: câmera
"""

import os, json, math
from collections import deque
import pygame

# === Paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_DIR = os.path.join(BASE_DIR, "exports", "maps")

# === Pygame ===
pygame.init()
pygame.font.init()
WIDTH, HEIGHT = 1280, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Map Tester — Isometric + Rotate")
clock = pygame.time.Clock()

# === Cores ===
BG = (18, 16, 14)
PANEL_BG = (32, 28, 24)
PANEL_BORDER = (80, 65, 45)
TEXT = (220, 210, 190)
TEXT_DIM = (140, 130, 110)
ACCENT = (200, 155, 85)
HIGHLIGHT = (255, 220, 100)
SUCCESS = (110, 200, 110)
DANGER = (200, 70, 70)

FONT_M = pygame.font.SysFont("georgia,dejavuserif,serif", 14)
FONT_S = pygame.font.SysFont("georgia,dejavuserif,serif", 12)
FONT_XS = pygame.font.SysFont("georgia,dejavuserif,serif", 11)

# === Constantes iso ===
ISO_TW = 64
ISO_TH = 32
ISO_WALL_H = 40
OCCLUDE_ALPHA = 120

# === Top-down ===
TD_CELL = 28


# ============================================================================
# Loader
# ============================================================================
def find_project_file():
    if not os.path.isdir(MAPS_DIR): return None
    files = []
    for f in os.listdir(MAPS_DIR):
        if f.endswith(".json"):
            fp = os.path.join(MAPS_DIR, f)
            files.append((os.path.getmtime(fp), fp, f))
    if not files: return None
    files_no_auto = [x for x in files
                     if not os.path.basename(x[2]).startswith("_")]
    pool = files_no_auto if files_no_auto else files
    pool.sort(reverse=True)
    return pool[0][1]


def make_demo_project():
    tileset = {
        "order": ["grass", "grass_dark", "dirt", "wall_stone", "water",
                  "tree", "flower_red"],
        "tiles": [
            {"id": "grass", "name": "Grama", "color": [90,140,80],
             "walkable": True, "category": "Terreno", "image_path": None,
             "height": 0, "blocks_sight": False},
            {"id": "grass_dark", "name": "Grama escura", "color": [66,105,60],
             "walkable": True, "category": "Terreno", "image_path": None,
             "height": 0, "blocks_sight": False},
            {"id": "dirt", "name": "Terra", "color": [140,100,70],
             "walkable": True, "category": "Terreno", "image_path": None,
             "height": 0, "blocks_sight": False},
            {"id": "wall_stone", "name": "Parede", "color": [150,140,130],
             "walkable": False, "category": "Estruturas", "image_path": None,
             "height": 1, "blocks_sight": True},
            {"id": "water", "name": "Água", "color": [60,90,160],
             "walkable": False, "category": "Terreno", "image_path": None,
             "height": 0, "blocks_sight": False},
            {"id": "tree", "name": "Árvore", "color": [80,140,70],
             "walkable": False, "category": "Natureza", "image_path": None,
             "height": 2, "blocks_sight": True},
            {"id": "flower_red", "name": "Flor", "color": [200,80,80],
             "walkable": True, "category": "Detalhes", "image_path": None,
             "height": 0, "blocks_sight": False},
        ],
    }
    w, h = 20, 15
    data = []
    for y in range(h):
        row = []
        for x in range(w):
            layer0 = "grass" if (x+y) % 2 == 0 else "grass_dark"
            if x < 2 or x > w-3 or y < 2 or y > h-3:
                layer0 = "wall_stone"
            row.append([layer0, None, None, None])
        data.append(row)
    for i in range(4, 12):
        data[8][i] = ["wall_stone", None, None, None]
    for i in range(3, 9):
        data[i][10] = ["wall_stone", None, None, None]
    for tx, ty in [(4,4), (6,5), (14,10), (12,4)]:
        data[ty][tx][1] = "tree"
    for tx, ty in [(15,13), (16,12), (9,11)]:
        data[ty][tx][1] = "flower_red"
    project = {
        "tileset": tileset,
        "event_types": [],
        "maps": {
            "demo": {
                "name": "demo", "parent": None, "w": w, "h": h,
                "num_layers": 4,
                "data": data, "passability": [],
                "events": [
                    {"kind": "player_spawn", "x": 5, "y": 11,
                     "id": 1, "name": "", "tag": "player_spawn",
                     "sprite": None, "data": {}},
                ],
            }
        },
        "active_map_name": "demo",
    }
    return project, "(demo em memória)"


def load_project():
    fp = find_project_file()
    if fp:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, fp
    return make_demo_project()


# ============================================================================
# Model
# ============================================================================
class Model:
    def __init__(self, project):
        self.project = project
        self.tileset = {t["id"]: t for t in project["tileset"]["tiles"]}
        self.load_map(project.get("active_map_name") or
                      next(iter(project["maps"])))

    def load_map(self, name):
        self.map_name = name
        mp = self.project["maps"][name]
        self.map = mp
        self.w = mp["w"]; self.h = mp["h"]
        self.num_layers = mp.get("num_layers",
                                 len(mp["data"][0][0]) if mp["data"] else 4)
        self.data = mp["data"]
        self.passability = {}
        for entry in mp.get("passability", []):
            if len(entry) >= 3:
                x, y, v = entry
                if isinstance(v, bool): v = "ok" if v else "block"
                self.passability[(x, y)] = v
        self.events = {}
        for ev in mp.get("events", []):
            self.events[(ev["x"], ev["y"])] = ev

    def get_tile(self, x, y, layer=None):
        if not (0 <= x < self.w and 0 <= y < self.h): return None
        if layer is not None:
            return self.data[y][x][layer] if layer < self.num_layers else None
        for l in reversed(range(self.num_layers)):
            if self.data[y][x][l] is not None:
                return self.data[y][x][l]
        return None

    def get_tile_color(self, tid):
        if not tid: return (42, 38, 34)
        t = self.tileset.get(tid)
        if not t: return (200, 50, 200)
        return tuple(t["color"])

    def get_tile_height(self, tid):
        if not tid: return 0
        t = self.tileset.get(tid)
        if not t: return 0
        return max(0, int(t.get("height", 0)))

    def get_tile_name(self, tid):
        if not tid: return None
        t = self.tileset.get(tid)
        return t["name"] if t else None

    def is_walkable(self, x, y):
        if not (0 <= x < self.w and 0 <= y < self.h): return False
        v = self.passability.get((x, y), None)
        if v in ("ok", "above", True): return True
        if v in ("block", False): return False
        tid = self.get_tile(x, y)
        if tid is None: return False
        t = self.tileset.get(tid)
        return t.get("walkable", True) if t else False

    def event_at(self, x, y):
        return self.events.get((x, y))


# ============================================================================
# BFS
# ============================================================================
def bfs_path(model, start, goal):
    if start == goal: return [start]
    if not model.is_walkable(*goal): return []
    visited = {start}
    parent = {start: None}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx, ny = x+dx, y+dy
            if (nx, ny) in visited: continue
            if not model.is_walkable(nx, ny): continue
            visited.add((nx, ny)); parent[(nx, ny)] = (x, y)
            if (nx, ny) == goal:
                path = []
                cur = goal
                while cur is not None:
                    path.append(cur); cur = parent[cur]
                return list(reversed(path))
            q.append((nx, ny))
    return []


# ============================================================================
# Helpers gráficos
# ============================================================================
def darken(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color[:3])

def world_pos(rgx, rgy):
    return ((rgx - rgy) * ISO_TW // 2, (rgx + rgy) * ISO_TH // 2)

def rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw < bx or bx + bw < ax or
                ay + ah < by or by + bh < ay)

def draw_diamond(surf, cx, cy, color, alpha=None):
    hw = ISO_TW // 2; hh = ISO_TH // 2
    pts = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]
    if alpha is None:
        pygame.draw.polygon(surf, color, pts)
    else:
        bw = ISO_TW + 4; bh = ISO_TH + 4
        off_x = cx - bw // 2; off_y = cy - bh // 2
        tmp = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pts_rel = [(p[0] - off_x, p[1] - off_y) for p in pts]
        pygame.draw.polygon(tmp, (color[0], color[1], color[2], alpha),
                            pts_rel)
        surf.blit(tmp, (off_x, off_y))

def draw_wall_block(surf, cx, cy, height_px, color, alpha=None):
    hw = ISO_TW // 2; hh = ISO_TH // 2
    top_y = cy - height_px
    b_lft = (cx - hw, cy); b_bot = (cx, cy + hh)
    b_rgt = (cx + hw, cy)
    t_top = (cx, top_y - hh); t_rgt = (cx + hw, top_y)
    t_bot = (cx, top_y + hh); t_lft = (cx - hw, top_y)
    col_sw = darken(color, 0.50)
    col_se = darken(color, 0.75)
    col_t  = color
    if alpha is None:
        pygame.draw.polygon(surf, col_sw, [b_lft, b_bot, t_bot, t_lft])
        pygame.draw.polygon(surf, col_se, [b_bot, b_rgt, t_rgt, t_bot])
        pygame.draw.polygon(surf, col_t,  [t_top, t_rgt, t_bot, t_lft])
    else:
        min_x = cx - hw; max_x = cx + hw
        min_y = top_y - hh; max_y = cy + hh
        bw = max_x - min_x + 4; bh = max_y - min_y + 4
        off_x = min_x - 2; off_y = min_y - 2
        tmp = pygame.Surface((bw, bh), pygame.SRCALPHA)
        def T(p): return (p[0] - off_x, p[1] - off_y)
        pygame.draw.polygon(tmp, (*col_sw, alpha),
                            [T(b_lft), T(b_bot), T(t_bot), T(t_lft)])
        pygame.draw.polygon(tmp, (*col_se, alpha),
                            [T(b_bot), T(b_rgt), T(t_rgt), T(t_bot)])
        pygame.draw.polygon(tmp, (*col_t, alpha),
                            [T(t_top), T(t_rgt), T(t_bot), T(t_lft)])
        surf.blit(tmp, (off_x, off_y))


# ============================================================================
# Tester
# ============================================================================
class Tester:
    def __init__(self, project, source):
        self.model = Model(project)
        self.source = source
        self.mode_iso = True
        self.rotation = 0
        self.td_cell = float(TD_CELL)
        self.cam = [0.0, 0.0]
        self.cam_speed = 600.0
        self.player = self._find_spawn()
        self.path = []
        self.move_cd = 0.0
        self.hover_cell = None
        self.show_grid = True
        self.msg = ""
        self.msg_timer = 0.0
        self._center_cam()
        self._msg(f"Carregado: {os.path.basename(source)}", SUCCESS)

    # --- rotação ---
    def _rotated_dims(self):
        w, h = self.model.w, self.model.h
        if self.rotation % 2 == 1:
            return (h, w)
        return (w, h)

    def _rotate(self, gx, gy):
        w, h = self.model.w, self.model.h
        r = self.rotation % 4
        if r == 0: return (gx, gy)
        if r == 1: return (h - 1 - gy, gx)
        if r == 2: return (w - 1 - gx, h - 1 - gy)
        return (gy, w - 1 - gx)

    def _inverse_rotate(self, rgx, rgy):
        w, h = self.model.w, self.model.h
        r = self.rotation % 4
        if r == 0: return (rgx, rgy)
        if r == 1: return (rgy, h - 1 - rgx)
        if r == 2: return (w - 1 - rgx, h - 1 - rgy)
        return (w - 1 - rgy, rgx)

    def _rotate_view(self, delta):
        if not self.mode_iso:
            self.rotation = (self.rotation + delta) % 4
            return
        px, py = self.player
        rgx, rgy = self._rotate(px, py)
        wx_old, wy_old = world_pos(rgx, rgy)
        self.rotation = (self.rotation + delta) % 4
        rgx, rgy = self._rotate(px, py)
        wx_new, wy_new = world_pos(rgx, rgy)
        self.cam[0] += wx_new - wx_old
        self.cam[1] += wy_new - wy_old
        self._clamp_cam()
        self._msg(f"Rotação: {self.rotation * 90}°", ACCENT)

    # --- spawn ---
    def _find_spawn(self):
        for (x, y), ev in self.model.events.items():
            k = ev.get("kind") or ev.get("tag")
            if k == "player_spawn":
                return (x, y)
        cx, cy = self.model.w // 2, self.model.h // 2
        for r in range(0, max(self.model.w, self.model.h)):
            for dy in range(-r, r+1):
                for dx in range(-r, r+1):
                    nx, ny = cx+dx, cy+dy
                    if self.model.is_walkable(nx, ny):
                        return (nx, ny)
        return (0, 0)

    def _msg(self, text, color=ACCENT):
        self.msg = text; self.msg_color = color; self.msg_timer = 2.5

    # --- câmera ---
    def _map_bbox_world(self):
        w2, h2 = self._rotated_dims()
        corners = [(0,0), (0,h2-1), (w2-1,0), (w2-1,h2-1)]
        xs, ys = [], []
        for rgx, rgy in corners:
            wx, wy = world_pos(rgx, rgy)
            xs.append(wx); ys.append(wy)
        return (min(xs) - ISO_TW, min(ys) - ISO_TW,
                max(xs) + ISO_TW, max(ys) + ISO_TW)

    def _center_cam(self):
        if self.mode_iso:
            mnx, mny, mxx, mxy = self._map_bbox_world()
            self.cam[0] = (mnx + mxx) / 2
            self.cam[1] = (mny + mxy) / 2
        else:
            self.cam[0] = self.model.w * self.td_cell / 2
            self.cam[1] = self.model.h * self.td_cell / 2

    def _clamp_cam(self):
        if self.mode_iso:
            mnx, mny, mxx, mxy = self._map_bbox_world()
            pad_x = WIDTH * 0.3; pad_y = HEIGHT * 0.3
            self.cam[0] = max(mnx - pad_x, min(mxx + pad_x, self.cam[0]))
            self.cam[1] = max(mny - pad_y, min(mxy + pad_y, self.cam[1]))
        else:
            ww = self.model.w * self.td_cell
            wh = self.model.h * self.td_cell
            self.cam[0] = max(-WIDTH*0.5, min(ww + WIDTH*0.5, self.cam[0]))
            self.cam[1] = max(-HEIGHT*0.5, min(wh + HEIGHT*0.5, self.cam[1]))

    def _world_to_screen(self, wx, wy):
        return (wx - self.cam[0] + WIDTH/2, wy - self.cam[1] + HEIGHT/2)

    def _screen_to_world(self, sx, sy):
        return (sx + self.cam[0] - WIDTH/2, sy + self.cam[1] - HEIGHT/2)

    def _screen_to_grid(self, sx, sy):
        wx, wy = self._screen_to_world(sx, sy)
        if self.mode_iso:
            rgx_f = wx / ISO_TW + wy / ISO_TH
            rgy_f = -wx / ISO_TW + wy / ISO_TH
            rgx = int(math.floor(rgx_f))
            rgy = int(math.floor(rgy_f))
            w2, h2 = self._rotated_dims()
            if not (0 <= rgx < w2 and 0 <= rgy < h2): return None
            return self._inverse_rotate(rgx, rgy)
        else:
            gx = int(wx // self.td_cell); gy = int(wy // self.td_cell)
            if 0 <= gx < self.model.w and 0 <= gy < self.model.h:
                return (gx, gy)
            return None

    def _zoom_at(self, mouse_pos, delta):
        if self.mode_iso: return
        old = self.td_cell
        new = max(10.0, min(64.0, old * (1.15 ** delta)))
        if abs(new - old) < 0.01: return
        wx = (mouse_pos[0] + self.cam[0] - WIDTH/2) / self.td_cell
        wy = (mouse_pos[1] + self.cam[1] - HEIGHT/2) / self.td_cell
        self.td_cell = new
        self.cam[0] = wx * new - mouse_pos[0] + WIDTH/2
        self.cam[1] = wy * new - mouse_pos[1] + HEIGHT/2
        self._clamp_cam()

    # --- events ---
    def handle(self, events):
        for e in events:
            if e.type == pygame.QUIT: return False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: return False
                if e.key == pygame.K_g: self.show_grid = not self.show_grid
                if e.key == pygame.K_c: self._center_cam()
                if e.key == pygame.K_t:
                    self.mode_iso = not self.mode_iso
                    self._center_cam(); self._clamp_cam()
                    self._msg("Modo: " + ("Isométrico" if self.mode_iso
                                          else "Top-down"), ACCENT)
                if e.key == pygame.K_q: self._rotate_view(-1)
                if e.key == pygame.K_e: self._rotate_view(1)
            if e.type == pygame.MOUSEWHEEL:
                self._zoom_at(pygame.mouse.get_pos(), e.y)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                cell = self._screen_to_grid(*e.pos)
                if cell:
                    path = bfs_path(self.model, self.player, cell)
                    if path: self.path = path[1:]
                    else: self._msg("Sem caminho até aí.", DANGER)
            if e.type == pygame.MOUSEMOTION:
                self.hover_cell = self._screen_to_grid(*e.pos)
        return True

    def _on_enter(self, x, y):
        ev = self.model.event_at(x, y)
        if ev:
            k = ev.get("kind") or ev.get("tag") or "?"
            self._msg(f"Evento: {k}", HIGHLIGHT)
            if k == "teleport":
                data = ev.get("data", {})
                tm = data.get("target_map")
                if tm and tm in self.model.project["maps"]:
                    self.model.load_map(tm)
                    tx = data.get("x"); ty = data.get("y")
                    if tx is not None and ty is not None:
                        try: self.player = (int(tx), int(ty))
                        except: pass
                    self._center_cam()
                    self._msg(f"Teleportou → {tm}", SUCCESS)

    def update(self, dt):
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0: self.msg = ""

        # câmera: WASD + setas
        keys = pygame.key.get_pressed()
        dx = dy = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1
        speed = self.cam_speed * (2.0 if (keys[pygame.K_LSHIFT] or
                                          keys[pygame.K_RSHIFT]) else 1.0)
        if dx or dy:
            n = (dx*dx + dy*dy) ** 0.5
            self.cam[0] += dx / n * speed * dt
            self.cam[1] += dy / n * speed * dt
            self._clamp_cam()

        # movimento por pathfinding
        self.move_cd = max(0.0, self.move_cd - dt)
        if self.path and self.move_cd <= 0:
            nxt = self.path.pop(0)
            self.player = nxt
            self.move_cd = 0.08
            self._on_enter(*nxt)

    # ============ RENDER ============
    def draw(self):
        screen.fill(BG)
        if self.mode_iso: self._draw_iso()
        else: self._draw_topdown()
        self._draw_info()
        self._draw_msg()
        pygame.display.flip()

    def _draw_iso(self):
        w2, h2 = self._rotated_dims()
        prgx, prgy = self._rotate(*self.player)
        player_depth = prgx + prgy
        player_drawn = False

        pwx, pwy = world_pos(prgx, prgy)
        psx, psy = self._world_to_screen(pwx, pwy + ISO_TH // 2)
        player_bbox = (psx - 14, psy - 28, 28, 28)

        for depth in range(w2 + h2 - 1):
            rgx_start = max(0, depth - h2 + 1)
            rgx_end = min(w2 - 1, depth)
            for rgx in range(rgx_start, rgx_end + 1):
                rgy = depth - rgx
                gx, gy = self._inverse_rotate(rgx, rgy)

                alpha = None
                if depth > player_depth:
                    tid = self.model.get_tile(gx, gy)
                    if tid:
                        h_tile = self.model.get_tile_height(tid)
                        if h_tile > 0:
                            wx, wy = world_pos(rgx, rgy)
                            sx, sy = self._world_to_screen(wx, wy + ISO_TH // 2)
                            H = h_tile * ISO_WALL_H
                            wall_bbox = (sx - ISO_TW // 2,
                                         sy - H - ISO_TH // 2,
                                         ISO_TW, H + ISO_TH)
                            if rects_overlap(wall_bbox, player_bbox):
                                alpha = OCCLUDE_ALPHA

                self._draw_iso_cell_at(rgx, rgy, gx, gy, alpha=alpha)

            if not player_drawn and depth >= player_depth:
                self._draw_iso_player()
                player_drawn = True

        if not player_drawn:
            self._draw_iso_player()

        # path
        for (px, py) in self.path:
            rgx, rgy = self._rotate(px, py)
            wx, wy = world_pos(rgx, rgy)
            cx, cy = self._world_to_screen(wx, wy + ISO_TH // 2)
            cx = int(cx); cy = int(cy)
            hw = ISO_TW // 2; hh = ISO_TH // 2
            s = pygame.Surface((ISO_TW, ISO_TH), pygame.SRCALPHA)
            pts = [(hw, 0), (ISO_TW, hh), (hw, ISO_TH), (0, hh)]
            pygame.draw.polygon(s, (255, 220, 100, 90), pts)
            screen.blit(s, (cx - hw, cy - hh))

        # hover
        if self.hover_cell:
            gx, gy = self.hover_cell
            rgx, rgy = self._rotate(gx, gy)
            wx, wy = world_pos(rgx, rgy)
            cx, cy = self._world_to_screen(wx, wy + ISO_TH // 2)
            cx = int(cx); cy = int(cy)
            hw = ISO_TW // 2; hh = ISO_TH // 2
            walk = self.model.is_walkable(gx, gy)
            col = SUCCESS if walk else DANGER
            pts = [(cx, cy - hh), (cx + hw, cy),
                   (cx, cy + hh), (cx - hw, cy)]
            pygame.draw.polygon(screen, col, pts, 2)

    def _draw_iso_cell_at(self, rgx, rgy, gx, gy, alpha=None):
        wx, wy = world_pos(rgx, rgy)
        cx, cy = self._world_to_screen(wx, wy + ISO_TH // 2)
        sx = int(cx); sy = int(cy)
        if sx < -ISO_TW * 2 or sx > WIDTH + ISO_TW * 2: return
        if sy < -400 or sy > HEIGHT + 400: return

        for layer in range(self.model.num_layers):
            tid = self.model.data[gy][gx][layer]
            if tid is None: continue
            color = self.model.get_tile_color(tid)
            h_tile = self.model.get_tile_height(tid)
            if h_tile == 0:
                draw_diamond(screen, sx, sy, color, alpha=alpha)
            else:
                draw_wall_block(screen, sx, sy, h_tile * ISO_WALL_H,
                                color, alpha=alpha)

        if self.show_grid:
            hw = ISO_TW // 2; hh = ISO_TH // 2
            pts = [(sx, sy - hh), (sx + hw, sy),
                   (sx, sy + hh), (sx - hw, sy)]
            pygame.draw.polygon(screen, (0, 0, 0), pts, 1)

    def _draw_iso_player(self):
        gx, gy = self.player
        rgx, rgy = self._rotate(gx, gy)
        wx, wy = world_pos(rgx, rgy)
        cx, cy = self._world_to_screen(wx, wy + ISO_TH // 2)
        cx = int(cx); cy = int(cy)
        shadow = pygame.Surface((44, 18), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 130), (0, 0, 44, 18))
        screen.blit(shadow, (cx - 22, cy - 8))
        pygame.draw.circle(screen, (250, 240, 220), (cx, cy - 14), 14)
        pygame.draw.circle(screen, (60, 40, 30), (cx, cy - 14), 14, 2)
        pygame.draw.circle(screen, (200, 80, 60), (cx, cy - 14), 4)

    def _draw_topdown(self):
        cs = self.td_cell
        ox = -self.cam[0] + WIDTH/2
        oy = -self.cam[1] + HEIGHT/2
        x0 = max(0, int(-ox / cs))
        y0 = max(0, int(-oy / cs))
        x1 = min(self.model.w, int((WIDTH - ox) / cs) + 1)
        y1 = min(self.model.h, int((HEIGHT - oy) / cs) + 1)
        for layer in range(self.model.num_layers):
            for y in range(y0, y1):
                for x in range(x0, x1):
                    tid = self.model.data[y][x][layer]
                    if tid is None: continue
                    rx = int(ox + x * cs); ry = int(oy + y * cs)
                    pygame.draw.rect(screen, self.model.get_tile_color(tid),
                                     (rx, ry, int(cs)+1, int(cs)+1))
        if self.show_grid and cs >= 10:
            gs = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for x in range(x0, x1 + 1):
                rx = int(ox + x * cs)
                pygame.draw.line(gs, (0,0,0,70), (rx, 0), (rx, HEIGHT))
            for y in range(y0, y1 + 1):
                ry = int(oy + y * cs)
                pygame.draw.line(gs, (0,0,0,70), (0, ry), (WIDTH, ry))
            screen.blit(gs, (0, 0))
        mw = int(self.model.w * cs); mh = int(self.model.h * cs)
        pygame.draw.rect(screen, PANEL_BORDER,
                         (int(ox)-2, int(oy)-2, mw+4, mh+4), 2)
        for (x, y) in self.path:
            rx = int(ox + x * cs); ry = int(oy + y * cs)
            s = pygame.Surface((int(cs), int(cs)), pygame.SRCALPHA)
            s.fill((255, 220, 100, 90))
            screen.blit(s, (rx, ry))
        if self.hover_cell:
            hx, hy = self.hover_cell
            rx = int(ox + hx * cs); ry = int(oy + hy * cs)
            col = SUCCESS if self.model.is_walkable(hx, hy) else DANGER
            pygame.draw.rect(screen, col, (rx, ry, int(cs), int(cs)), 2)
        px = int(ox + self.player[0] * cs + cs//2)
        py = int(oy + self.player[1] * cs + cs//2)
        pygame.draw.circle(screen, (250, 240, 220), (px, py), int(cs//2 - 3))
        pygame.draw.circle(screen, (60, 40, 30), (px, py), int(cs//2 - 3), 2)

    def _draw_info(self):
        rot_deg = self.rotation * 90
        lines = [
            f"Fonte: {os.path.basename(self.source)}",
            f"Mapa: {self.model.map_name}  ({self.model.w}x{self.model.h})",
            f"Modo: {'ISOMÉTRICO' if self.mode_iso else 'TOP-DOWN'}   Rot: {rot_deg}°",
            f"Jogador: {self.player}",
        ]
        if self.hover_cell:
            hx, hy = self.hover_cell
            tid = self.model.get_tile(hx, hy)
            tname = self.model.get_tile_name(tid)
            height = self.model.get_tile_height(tid)
            walk = self.model.is_walkable(hx, hy)
            lines += ["", f"Hover: ({hx},{hy})",
                      f"Tile: {tname or '(vazio)'}",
                      f"Height: {height}",
                      f"Walkable: {'sim' if walk else 'não'}"]
            ev = self.model.event_at(hx, hy)
            if ev:
                lines.append(f"Evento: {ev.get('kind') or ev.get('tag')}")
                for k, v in (ev.get("data") or {}).items():
                    lines.append(f"  {k}: {v}")

        pad = 10; box_w = 300
        box_h = pad * 2 + len(lines) * 16
        bx = 10; by = 10
        pygame.draw.rect(screen, PANEL_BG, (bx, by, box_w, box_h),
                         border_radius=6)
        pygame.draw.rect(screen, PANEL_BORDER, (bx, by, box_w, box_h), 1,
                         border_radius=6)
        yy = by + pad
        for i, ln in enumerate(lines):
            col = TEXT if i == 0 else TEXT_DIM
            if ln.startswith("Hover"): col = HIGHLIGHT
            if ln.startswith("Modo:"): col = ACCENT
            s = FONT_S.render(ln, True, col)
            screen.blit(s, (bx + pad, yy))
            yy += 16

        help_lines = [
            "LMB: mover (pathfinding)",
            "WASD/Setas: câmera",
            "SHIFT: câmera rápida",
            "Q/E: rotacionar 90°",
            "T: iso/top-down",
            "G: grid  C: centro",
            "ESC: sair",
        ]
        hb_h = 10 + len(help_lines) * 14
        hb_y = HEIGHT - hb_h - 10
        pygame.draw.rect(screen, PANEL_BG, (10, hb_y, 210, hb_h),
                         border_radius=6)
        pygame.draw.rect(screen, PANEL_BORDER, (10, hb_y, 210, hb_h), 1,
                         border_radius=6)
        yy = hb_y + 6
        for ln in help_lines:
            s = FONT_XS.render(ln, True, TEXT_DIM)
            screen.blit(s, (18, yy))
            yy += 14

    def _draw_msg(self):
        if not self.msg: return
        r = FONT_M.render(self.msg, True, self.msg_color)
        bg = pygame.Surface((r.get_width()+20, r.get_height()+10),
                            pygame.SRCALPHA)
        bg.fill((0,0,0,200))
        x = WIDTH//2 - bg.get_width()//2
        y = HEIGHT - 70
        screen.blit(bg, (x, y))
        screen.blit(r, (x+10, y+5))


# ============================================================================
# Main
# ============================================================================
def main():
    project, source = load_project()
    app = Tester(project, source)
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        events = pygame.event.get()
        running = app.handle(events)
        app.update(dt)
        app.draw()
    pygame.quit()


if __name__ == "__main__":
    main()