# -*- coding: utf-8 -*-
"""
GridTest.py
App isolado para desvendar o sistema de encaixe em grid de inventário.

- Grid 12x9
- Botão SPAWNAR ITEM
- Clique para pegar/arrastar/soltar
- R rotaciona enquanto arrasta
- Preview:
   - Verde  -> encaixa em célula vazia
   - Azul   -> swap válido (sobrepõe exatamente 1 item)
   - Vermelho -> não cabe ou sobrepõe 2+ itens
- Debug em tempo real
"""

import pygame
import random

pygame.init()
WIDTH, HEIGHT = 1200, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Grid Test - Swap")
clock = pygame.time.Clock()

# ----------------------------------------------------------------------------
# Grid
# ----------------------------------------------------------------------------
CELL = 40
GRID_X, GRID_Y = 40, 100
GRID_COLS, GRID_ROWS = 12, 9
GRID_W = GRID_COLS * CELL
GRID_H = GRID_ROWS * CELL

SPAWN_X = GRID_X + GRID_W + 40
SPAWN_Y = 100

# Cores
BG           = (28, 30, 40)
GRID_BG      = (42, 45, 58)
GRID_LINE    = (65, 68, 85)
TEXT         = (230, 232, 240)
TEXT_DIM     = (150, 155, 175)
PREVIEW_OK   = (100, 220, 100)
PREVIEW_SWAP = (100, 180, 240)
PREVIEW_BAD  = (220, 90, 90)

ITEM_COLORS = [
    (200, 80, 80), (80, 200, 80), (80, 130, 220),
    (200, 180, 80), (180, 80, 200), (80, 200, 200),
]

SIZES = [(1,1), (1,2), (1,3), (1,4), (2,1), (2,2), (2,3), (3,1), (3,2), (3,3)]

FONT_S = pygame.font.SysFont("consolas", 13)
FONT_M = pygame.font.SysFont("arial", 14)
FONT_L = pygame.font.SysFont("arial", 16, bold=True)


class Item:
    def __init__(self, w, h, color):
        self.w = w
        self.h = h
        self.color = color
        self.x = None
        self.y = None
        self.spawn_x = 0
        self.spawn_y = 0


class App:
    def __init__(self):
        self.items = []
        self.grid = [[None for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
        self.dragging = None
        self.drag_offset = (0, 0)
        self.preview_cell = None
        self.preview_valid = False
        self.swap_target = None
        self.preview_kind = "none"

        self.spawn_btn = pygame.Rect(SPAWN_X, 40, 200, 40)

        for _ in range(3):
            self.spawn_item()

    # ------------------------------------------------------------------
    def spawn_item(self):
        w, h = random.choice(SIZES)
        color = random.choice(ITEM_COLORS)
        item = Item(w, h, color)
        self.items.append(item)
        self.arrange_spawn_area()

    def arrange_spawn_area(self):
        y = SPAWN_Y
        for item in self.items:
            if item.x is None:
                item.spawn_x = SPAWN_X
                item.spawn_y = y
                y += item.h * CELL + 10
                if y > HEIGHT - 60:
                    y = SPAWN_Y

    # ------------------------------------------------------------------
    def item_at_mouse(self, mx, my):
        if (GRID_X <= mx < GRID_X + GRID_W and
            GRID_Y <= my < GRID_Y + GRID_H):
            cx = (mx - GRID_X) // CELL
            cy = (my - GRID_Y) // CELL
            if 0 <= cx < GRID_COLS and 0 <= cy < GRID_ROWS:
                return self.grid[cy][cx]
        for item in self.items:
            if item.x is None:
                r = pygame.Rect(item.spawn_x, item.spawn_y,
                                item.w * CELL, item.h * CELL)
                if r.collidepoint(mx, my):
                    return item
        return None

    # ------------------------------------------------------------------
    def can_place(self, item, cx, cy, ignore=None):
        if cx < 0 or cy < 0: return False
        if cx + item.w > GRID_COLS: return False
        if cy + item.h > GRID_ROWS: return False
        for dx in range(item.w):
            for dy in range(item.h):
                occupant = self.grid[cy + dy][cx + dx]
                if occupant is not None and occupant is not ignore:
                    return False
        return True

    def find_drop(self, item, cx, cy):
        """
        Retorna (valid, kind, swap_target):
        - kind = 'ok'   -> célula(s) vazia(s)
        - kind = 'swap' -> sobrepõe exatamente 1 item distinto, e cabe se ele for removido
        - kind = 'bad'  -> não cabe
        """
        if not (0 <= cx < GRID_COLS and 0 <= cy < GRID_ROWS):
            return False, "bad", None
        if cx + item.w > GRID_COLS or cy + item.h > GRID_ROWS:
            return False, "bad", None

        # Coleta todos os itens ocupando as células alvo
        occupants = {}
        for dx in range(item.w):
            for dy in range(item.h):
                cell = self.grid[cy + dy][cx + dx]
                if cell is not None and cell is not item:
                    occupants[id(cell)] = cell

        # Caso 1: sem ocupantes -> encaixa direto
        if not occupants:
            return True, "ok", None

        # Caso 2: exatamente 1 ocupante -> tenta swap
        if len(occupants) == 1:
            target = next(iter(occupants.values()))

            saved = {}
            for dx in range(target.w):
                for dy in range(target.h):
                    gx, gy = target.x + dx, target.y + dy
                    saved[(gx, gy)] = self.grid[gy][gx]
                    self.grid[gy][gx] = None

            can = self.can_place(item, cx, cy)

            for (gx, gy), val in saved.items():
                self.grid[gy][gx] = val

            if can:
                return True, "swap", target
            return False, "bad", None

        # Caso 3: 2+ ocupantes diferentes -> bloqueado
        return False, "bad", None

    # ------------------------------------------------------------------
    def place_item(self, item, cx, cy):
        item.x = cx
        item.y = cy
        for dx in range(item.w):
            for dy in range(item.h):
                self.grid[cy + dy][cx + dx] = item

    def remove_from_grid(self, item):
        if item.x is None:
            return
        for dx in range(item.w):
            for dy in range(item.h):
                self.grid[item.y + dy][item.x + dx] = None
        item.x = None
        item.y = None

    # ------------------------------------------------------------------
    def handle_click(self, pos):
        mx, my = pos

        if self.spawn_btn.collidepoint(pos):
            self.spawn_item()
            return

        # Soltar
        if self.dragging is not None:
            if self.preview_valid and self.preview_cell:
                cx, cy = self.preview_cell
                if self.preview_kind == "swap" and self.swap_target is not None:
                    swap = self.swap_target
                    self.remove_from_grid(swap)
                    self.place_item(self.dragging, cx, cy)
                    # Alvo vai pro cursor
                    self.dragging = swap
                    pw = swap.w * CELL
                    ph = swap.h * CELL
                    self.drag_offset = (-pw // 2, -ph // 2)
                    self.swap_target = None
                    self.arrange_spawn_area()
                    return
                else:
                    self.place_item(self.dragging, cx, cy)
                    self.dragging = None
                    self.arrange_spawn_area()
                    return
            self.dragging = None
            self.arrange_spawn_area()
            return

        # Pegar
        item = self.item_at_mouse(mx, my)
        if item:
            if item.x is not None:
                tl_x = GRID_X + item.x * CELL
                tl_y = GRID_Y + item.y * CELL
                self.remove_from_grid(item)
            else:
                tl_x = item.spawn_x
                tl_y = item.spawn_y

            self.dragging = item
            self.drag_offset = (tl_x - mx, tl_y - my)

    def rotate_dragging(self):
        if self.dragging is None:
            return
        self.dragging.w, self.dragging.h = self.dragging.h, self.dragging.w

    # ------------------------------------------------------------------
    def update_drag(self, mouse_pos):
        if self.dragging is None:
            self.preview_cell = None
            self.preview_valid = False
            self.swap_target = None
            self.preview_kind = "none"
            return

        mx, my = mouse_pos
        tl_x = mx + self.drag_offset[0]
        tl_y = my + self.drag_offset[1]

        cx = int(round((tl_x - GRID_X) / CELL))
        cy = int(round((tl_y - GRID_Y) / CELL))

        cx = max(0, min(GRID_COLS - self.dragging.w, cx))
        cy = max(0, min(GRID_ROWS - self.dragging.h, cy))

        near_grid = (
            GRID_X - CELL <= mx < GRID_X + GRID_W + CELL and
            GRID_Y - CELL <= my < GRID_Y + GRID_H + CELL
        )
        if near_grid:
            valid, kind, target = self.find_drop(self.dragging, cx, cy)
            self.preview_cell = (cx, cy)
            self.preview_valid = valid
            self.preview_kind = kind
            self.swap_target = target
        else:
            self.preview_cell = None
            self.preview_valid = False
            self.preview_kind = "none"
            self.swap_target = None

    # ------------------------------------------------------------------
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return False
                if e.key == pygame.K_r and self.dragging:
                    self.rotate_dragging()
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.handle_click(e.pos)
        return True

    # ------------------------------------------------------------------
    def draw(self):
        screen.fill(BG)

        # Grid
        grid_rect = pygame.Rect(GRID_X, GRID_Y, GRID_W, GRID_H)
        pygame.draw.rect(screen, GRID_BG, grid_rect)
        for i in range(GRID_COLS + 1):
            x = GRID_X + i * CELL
            pygame.draw.line(screen, GRID_LINE, (x, GRID_Y), (x, GRID_Y + GRID_H))
        for j in range(GRID_ROWS + 1):
            y = GRID_Y + j * CELL
            pygame.draw.line(screen, GRID_LINE, (GRID_X, y), (GRID_X + GRID_W, y))
        pygame.draw.rect(screen, GRID_LINE, grid_rect, 2)

        # Preview
        if self.preview_cell:
            cx, cy = self.preview_cell
            px = GRID_X + cx * CELL
            py = GRID_Y + cy * CELL
            pw = self.dragging.w * CELL
            ph = self.dragging.h * CELL

            if self.preview_kind == "swap":
                color = PREVIEW_SWAP
            elif self.preview_kind == "ok":
                color = PREVIEW_OK
            else:
                color = PREVIEW_BAD

            surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
            surf.fill((*color, 70))
            screen.blit(surf, (px, py))
            pygame.draw.rect(screen, color, (px, py, pw, ph), 3)

            if self.preview_kind == "swap" and self.swap_target:
                t = self.swap_target
                tpx = GRID_X + t.x * CELL
                tpy = GRID_Y + t.y * CELL
                tpw = t.w * CELL
                tph = t.h * CELL
                pygame.draw.rect(screen, PREVIEW_SWAP,
                                 (tpx + 1, tpy + 1, tpw - 2, tph - 2), 2)

        # Itens no grid
        for item in self.items:
            if item.x is not None and item is not self.dragging:
                px = GRID_X + item.x * CELL
                py = GRID_Y + item.y * CELL
                pw = item.w * CELL
                ph = item.h * CELL
                pygame.draw.rect(screen, item.color, (px + 2, py + 2, pw - 4, ph - 4))
                pygame.draw.rect(screen, (255, 255, 255), (px + 2, py + 2, pw - 4, ph - 4), 1)
                label = FONT_S.render(f"{item.w}x{item.h}", True, (255, 255, 255))
                screen.blit(label, (px + pw // 2 - label.get_width() // 2,
                                    py + ph // 2 - label.get_height() // 2))

        # Itens fora do grid
        for item in self.items:
            if item.x is None and item is not self.dragging:
                px = item.spawn_x
                py = item.spawn_y
                pw = item.w * CELL
                ph = item.h * CELL
                pygame.draw.rect(screen, item.color, (px, py, pw, ph))
                pygame.draw.rect(screen, (255, 255, 255), (px, py, pw, ph), 1)
                label = FONT_S.render(f"{item.w}x{item.h}", True, (255, 255, 255))
                screen.blit(label, (px + pw // 2 - label.get_width() // 2,
                                    py + ph // 2 - label.get_height() // 2))

        # Item arrastado
        if self.dragging:
            mx, my = pygame.mouse.get_pos()
            tl_x = mx + self.drag_offset[0]
            tl_y = my + self.drag_offset[1]
            pw = self.dragging.w * CELL
            ph = self.dragging.h * CELL
            surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
            surf.fill((*self.dragging.color, 210))
            screen.blit(surf, (tl_x, tl_y))
            pygame.draw.rect(screen, (255, 255, 255), (tl_x, tl_y, pw, ph), 2)
            label = FONT_S.render(f"{self.dragging.w}x{self.dragging.h}", True, (255, 255, 255))
            screen.blit(label, (tl_x + pw // 2 - label.get_width() // 2,
                                tl_y + ph // 2 - label.get_height() // 2))

        # Botão spawn
        pygame.draw.rect(screen, (70, 130, 80), self.spawn_btn, border_radius=6)
        txt = FONT_L.render("+ SPAWNAR ITEM", True, (255, 255, 255))
        screen.blit(txt, (self.spawn_btn.centerx - txt.get_width() // 2,
                          self.spawn_btn.centery - txt.get_height() // 2))

        # Debug
        mx, my = pygame.mouse.get_pos()
        debug_lines = [f"Mouse: ({mx}, {my})"]
        if self.dragging:
            tl_x = mx + self.drag_offset[0]
            tl_y = my + self.drag_offset[1]
            cfx = (tl_x - GRID_X) / CELL
            cfy = (tl_y - GRID_Y) / CELL
            debug_lines += [
                f"Item: {self.dragging.w}x{self.dragging.h}",
                f"Offset: {self.drag_offset}",
                f"Topo-esq: ({tl_x:.0f}, {tl_y:.0f})",
                f"Célula float: ({cfx:.2f}, {cfy:.2f})",
                f"Célula round: ({int(round(cfx))}, {int(round(cfy))})",
                f"Preview cell: {self.preview_cell}",
                f"Preview kind: {self.preview_kind}",
                f"Swap target: {self.swap_target.w}x{self.swap_target.h}" if self.swap_target else "Swap target: -",
            ]
        else:
            debug_lines.append("(nada arrastando)")

        y = 500
        for line in debug_lines:
            s = FONT_S.render(line, True, TEXT_DIM)
            screen.blit(s, (SPAWN_X, y))
            y += 18

        # Legenda
        legend = [
            ("Verde  = encaixa (vazio)", PREVIEW_OK),
            ("Azul   = swap com item", PREVIEW_SWAP),
            ("Vermelho = não cabe / 2+ itens", PREVIEW_BAD),
        ]
        y = HEIGHT - 130
        for text, col in legend:
            pygame.draw.rect(screen, col, (40, y + 4, 14, 14))
            s = FONT_S.render(text, True, TEXT_DIM)
            screen.blit(s, (62, y))
            y += 20

        pygame.display.flip()

    # ------------------------------------------------------------------
    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update_drag(pygame.mouse.get_pos())
            self.draw()
            clock.tick(60)
        pygame.quit()


if __name__ == "__main__":
    App().run()