import pygame
import random
import math
from collections import deque
from dataclasses import dataclass, field

# ============================================================
# MINI CATACLYSM V6
# ============================================================
#
# Grande salto de arquitetura mantendo a proposta de um único
# arquivo e sem assets externos.
#
# NOVO NESTA VERSÃO:
#   - barras visuais para Fome e Sede
#   - mapa muito maior
#   - câmera dinâmica suave seguindo o jogador
#   - ruas geradas antes das construções e organizadas por blocos
#   - casas de 1 a 6 andares
#   - vários tipos de prédios
#   - múltiplos cômodos por andar
#   - banheiro, sala, quarto, cozinha, escritório etc.
#   - portas abertas e fechadas
#   - portas internas também
#   - telhados visuais nas construções quando vistas de fora
#   - Z layer / andares
#   - escadas para subir/descer
#   - Fog of War por andar
#   - clique esquerdo com pathfinding
#   - clique esquerdo abre porta próxima / navega até porta
#   - clique direito ataca
#   - melee em qualquer uma das 8 casas adjacentes
#   - tiro à distância em qualquer direção dentro da LOS
#   - tooltip flutuante no mouse
#   - loot, armas, necessidades, HUD e inventário
#
# CONTROLES:
#   WASD / SETAS  = mover
#   ESQUERDO      = andar / abrir porta
#   DIREITO       = atacar
#   1             = faca
#   2             = pistola
#   3             = shotgun
#   R             = recarregar
#   E             = pegar / fechar porta próxima
#   F             = comer
#   G             = beber
#   H             = medkit
#   I             = inventário
#   U             = subir escada
#   J             = descer escada
#   ESPAÇO        = esperar
#   ESC           = cancelar caminho / fechar inventário
#   Q             = sair
#
# Requer:
#   pip install pygame-ce
#
# ============================================================

pygame.init()

# ============================================================
# CONFIGURAÇÃO
# ============================================================

TILE = 24
MAP_W = 90
MAP_H = 70
HUD_H = 155
SCREEN_W = 1280
SCREEN_H = 780
FPS = 60

VISION_RADIUS = 11
AUTO_MOVE_DELAY = 90
CAMERA_SMOOTH = 9.0
ROAD_WIDTH = 3
SIDEWALK_WIDTH = 1
MAX_BUILDING_FLOORS = 6

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Mini Cataclysm V6 - City / Z-Layers / Fog of War")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("consolas", 16)
FONT_SMALL = pygame.font.SysFont("consolas", 13)
FONT_TINY = pygame.font.SysFont("consolas", 11)
FONT_BIG = pygame.font.SysFont("consolas", 24, bold=True)

# ============================================================
# CORES
# ============================================================

BLACK = (4, 5, 7)
WHITE = (235, 235, 235)
HUD_BG = (16, 17, 20)
HUD_BORDER = (72, 75, 82)

GRASS = (55, 106, 55)
GRASS_DARK = (42, 88, 43)
ROAD = (68, 70, 73)
ROAD_DARK = (50, 52, 55)
SIDEWALK = (112, 112, 108)
SIDEWALK_DARK = (82, 82, 80)

WALL = (45, 46, 50)
WALL_DARK = (26, 27, 30)
FLOOR = (126, 108, 80)
FLOOR_DARK = (104, 89, 67)

OPEN_DOOR_COLOR = (188, 141, 65)
CLOSED_DOOR_COLOR = (111, 75, 36)
STAIR_COLOR = (185, 185, 190)

PLAYER_COLOR = (55, 225, 255)
ZOMBIE_COLOR = (208, 55, 55)
PATH_COLOR = (90, 180, 255)
CURSOR_COLOR = (245, 245, 245)

ITEM_YELLOW = (244, 209, 56)
ITEM_GREEN = (88, 210, 90)
ITEM_BLUE = (72, 155, 245)
ITEM_RED = (235, 84, 84)
ITEM_AMMO = (226, 180, 68)

TOOLTIP_BG = (20, 20, 24)
TOOLTIP_BORDER = (210, 210, 210)

# ============================================================
# TILES
# ============================================================

GRASS_TILE = 0
ROAD_TILE = 1
SIDEWALK_TILE = 2
FLOOR_TILE = 3
WALL_TILE = 4
OPEN_DOOR_TILE = 5
CLOSED_DOOR_TILE = 6
STAIR_UP_TILE = 7
STAIR_DOWN_TILE = 8
STAIR_BOTH_TILE = 9
VOID_TILE = 10

WALKABLE = {
    GRASS_TILE,
    ROAD_TILE,
    SIDEWALK_TILE,
    FLOOR_TILE,
    OPEN_DOOR_TILE,
    STAIR_UP_TILE,
    STAIR_DOWN_TILE,
    STAIR_BOTH_TILE,
}

BLOCKING = {
    WALL_TILE,
    CLOSED_DOOR_TILE,
    VOID_TILE,
}

# ============================================================
# ARMAS
# ============================================================

WEAPONS = {
    "knife": {
        "name": "Faca",
        "type": "melee",
        "damage": (8, 14),
        "range": 1,
        "ammo_type": None,
        "mag_size": 0,
        "accuracy": 1.0,
    },
    "pistol": {
        "name": "Pistola",
        "type": "ranged",
        "damage": (12, 20),
        "range": 12,
        "ammo_type": "9mm",
        "mag_size": 8,
        "accuracy": 0.92,
    },
    "shotgun": {
        "name": "Shotgun",
        "type": "ranged",
        "damage": (22, 38),
        "range": 8,
        "ammo_type": "shell",
        "mag_size": 2,
        "accuracy": 0.94,
    },
}

# ============================================================
# COMODOS
# ============================================================

ROOM_TYPES = [
    "Living Room",
    "Bedroom",
    "Kitchen",
    "Bathroom",
    "Office",
    "Storage",
    "Hall",
    "Reception",
    "Meeting Room",
    "Server Room",
]

ROOM_COLOR = {
    "Living Room": (142, 120, 88),
    "Bedroom": (127, 112, 105),
    "Kitchen": (137, 125, 83),
    "Bathroom": (93, 129, 137),
    "Office": (103, 104, 123),
    "Storage": (100, 91, 76),
    "Hall": (133, 118, 96),
    "Reception": (117, 105, 95),
    "Meeting Room": (108, 108, 118),
    "Server Room": (77, 87, 100),
}

# ============================================================
# BUILDING TYPES
# ============================================================

BUILDING_TYPES = {
    "Shed": {
        "weight": 11,
        "floors": (1, 1),
        "rooms": (1, 1),
        "size": ((5, 7), (5, 7)),
        "loot": 1,
    },
    "Small House": {
        "weight": 22,
        "floors": (1, 2),
        "rooms": (2, 4),
        "size": ((7, 10), (6, 9)),
        "loot": 2,
    },
    "House": {
        "weight": 21,
        "floors": (1, 3),
        "rooms": (3, 6),
        "size": ((9, 13), (8, 12)),
        "loot": 3,
    },
    "Townhouse": {
        "weight": 11,
        "floors": (2, 4),
        "rooms": (3, 6),
        "size": ((7, 11), (8, 13)),
        "loot": 4,
    },
    "Office": {
        "weight": 13,
        "floors": (3, 6),
        "rooms": (4, 9),
        "size": ((9, 14), (9, 14)),
        "loot": 7,
    },
    "Apartment": {
        "weight": 16,
        "floors": (3, 6),
        "rooms": (3, 7),
        "size": ((9, 14), (10, 15)),
        "loot": 6,
    },
    "Clinic": {
        "weight": 6,
        "floors": (2, 4),
        "rooms": (4, 8),
        "size": ((9, 13), (8, 12)),
        "loot": 8,
    },
}

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Item:
    kind: str
    amount: int = 1

    def name(self):
        return {
            "food": "Food",
            "water": "Water",
            "medkit": "Medkit",
            "9mm": "9mm Ammo",
            "shell": "Shotgun Shells",
            "pistol": "Pistol",
            "shotgun": "Shotgun",
        }.get(self.kind, self.kind)

    def symbol(self):
        return {
            "food": "%",
            "water": "~",
            "medkit": "+",
            "9mm": "•",
            "shell": "S",
            "pistol": "P",
            "shotgun": "G",
        }.get(self.kind, "?")


@dataclass
class FloorData:
    z: int
    tiles: dict = field(default_factory=dict)
    rooms: dict = field(default_factory=dict)
    doors: set = field(default_factory=set)
    stairs: set = field(default_factory=set)


@dataclass
class Building:
    id: int
    kind: str
    x: int
    y: int
    w: int
    h: int
    floors: int
    floors_data: list = field(default_factory=list)
    exterior_doors: set = field(default_factory=set)
    roof_style: int = 0

    def contains(self, x, y):
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def floor_contains(self, z, x, y):
        return 0 <= z < self.floors and self.contains(x, y)


@dataclass
class Zombie:
    x: int
    y: int
    z: int = 0
    max_hp: int = 40
    hp: int = 40
    damage: int = 8
    alive: bool = True
    alert: int = 0


# ============================================================
# GAME
# ============================================================

class Game:

    def __init__(self):
        self.running = True
        self.dead = False
        self.turn = 0
        self.kills = 0

        self.base_map = {}
        self.buildings = []
        self.items = []
        self.zombies = []

        self.explored = set()
        self.visible = set()

        self.path = []
        self.pending_door = None
        self.pending_building = None
        self.inventory_open = False

        self.messages = []
        self.next_building_id = 1

        self.player = {
            "x": 0,
            "y": 0,
            "z": 0,
            "hp": 100,
            "max_hp": 100,
            "hunger": 12,  # 0 = sem necessidade, 100 = crítico
            "thirst": 10,
            "weapon": "knife",
            "weapons": {
                "knife": True,
                "pistol": True,
                "shotgun": False,
            },
            "ammo": {
                "9mm": 22,
                "shell": 0,
            },
            "mag": {
                "pistol": 8,
                "shotgun": 0,
            },
            "food": 3,
            "water": 3,
            "medkit": 1,
        }

        # câmera em pixels no mundo
        self.camera_x = 0.0
        self.camera_y = 0.0

        # cursor armazenado para tooltip
        self.mouse_pos = (0, 0)

        self.generate_world()

        self.player["x"], self.player["y"] = self.find_spawn()

        self.update_fog_of_war()

        self.camera_x, self.camera_y = self.get_camera_target()

        self.message("Você acorda em uma cidade infestada.")
        self.message("A grama agora é caminhável.")
        self.message("Esq = andar | Dir = atacar")
        self.message("U = subir | J = descer")

    # ========================================================
    # MENSAGENS
    # ========================================================

    def message(self, text):
        self.messages.append(text)
        if len(self.messages) > 7:
            self.messages.pop(0)

    # ========================================================
    # MAPA BASE
    # ========================================================

    def set_base(self, x, y, tile):
        self.base_map[(x, y)] = tile

    def base_tile(self, x, y):
        if not self.inside(x, y):
            return VOID_TILE
        return self.base_map.get((x, y), GRASS_TILE)

    def get_building(self, x, y):
        for b in self.buildings:
            if b.contains(x, y):
                return b
        return None

    def get_floor_data(self, building, z):
        if not building or not (0 <= z < building.floors):
            return None
        return building.floors_data[z]

    def tile_at(self, x, y, z=None):
        if z is None:
            z = self.player["z"]

        if not self.inside(x, y):
            return VOID_TILE

        if z == 0:
            b = self.get_building(x, y)
            if b and 0 <= z < b.floors:
                local_x = x - b.x
                local_y = y - b.y
                fd = b.floors_data[0]
                return fd.tiles.get((local_x, local_y), WALL_TILE)
            return self.base_tile(x, y)

        b = self.get_building(x, y)
        if not b or not (0 <= z < b.floors):
            return VOID_TILE
        fd = b.floors_data[z]
        lx = x - b.x
        ly = y - b.y
        return fd.tiles.get((lx, ly), VOID_TILE)

    def room_at(self, x, y, z=None):
        if z is None:
            z = self.player["z"]
        b = self.get_building(x, y)
        if not b or not (0 <= z < b.floors):
            return None
        fd = b.floors_data[z]
        return fd.rooms.get((x - b.x, y - b.y))

    def door_open(self, x, y, z=None):
        return self.tile_at(x, y, z) == OPEN_DOOR_TILE

    # ========================================================
    # WORLD GENERATION
    # ========================================================

    def generate_world(self):
        self.base_map.clear()
        self.buildings.clear()

        for y in range(MAP_H):
            for x in range(MAP_W):
                self.set_base(x, y, GRASS_TILE)

        vertical_roads = self.make_road_positions(MAP_W)
        horizontal_roads = self.make_road_positions(MAP_H)

        for center in vertical_roads:
            for x in range(center - ROAD_WIDTH // 2, center + ROAD_WIDTH // 2 + 1):
                if 0 <= x < MAP_W:
                    for y in range(MAP_H):
                        self.set_base(x, y, ROAD_TILE)
                    for side in (-1, 1):
                        sx = x + side * (ROAD_WIDTH // 2 + 1)
                        if 0 <= sx < MAP_W and self.base_tile(sx, 0) != ROAD_TILE:
                            for y in range(MAP_H):
                                if self.base_tile(sx, y) == GRASS_TILE:
                                    self.set_base(sx, y, SIDEWALK_TILE)

        for center in horizontal_roads:
            for y in range(center - ROAD_WIDTH // 2, center + ROAD_WIDTH // 2 + 1):
                if 0 <= y < MAP_H:
                    for x in range(MAP_W):
                        self.set_base(x, y, ROAD_TILE)
                    for side in (-1, 1):
                        sy = y + side * (ROAD_WIDTH // 2 + 1)
                        if 0 <= sy < MAP_H and self.base_tile(0, sy) != ROAD_TILE:
                            for x in range(MAP_W):
                                if self.base_tile(x, sy) == GRASS_TILE:
                                    self.set_base(x, sy, SIDEWALK_TILE)

        # Faixas simples no centro das ruas.
        self.road_positions = vertical_roads, horizontal_roads

        self.generate_blocks_and_buildings(vertical_roads, horizontal_roads)
        self.spawn_city_loot()
        self.spawn_zombies()

    def make_road_positions(self, size):
        positions = []
        cursor = 6
        while cursor < size - 5:
            positions.append(cursor)
            cursor += random.randint(12, 16)
        return positions

    def road_intervals(self, positions, size):
        edges = []
        starts = [0]
        ends = []
        for p in positions:
            half = ROAD_WIDTH // 2
            starts.append(max(0, p + half + SIDEWALK_WIDTH + 1))
            ends.append(max(0, p - half - SIDEWALK_WIDTH - 1))
        previous = 0
        for p in positions:
            left = previous + ROAD_WIDTH // 2 + SIDEWALK_WIDTH + 1 if positions else 1
            right = p - ROAD_WIDTH // 2 - SIDEWALK_WIDTH - 1
            if right - left >= 6:
                edges.append((left, right))
            previous = p
        left = (positions[-1] if positions else -1) + ROAD_WIDTH // 2 + SIDEWALK_WIDTH + 1
        right = size - 2
        if right - left >= 6:
            edges.append((left, right))
        return edges

    def generate_blocks_and_buildings(self, vertical_roads, horizontal_roads):
        xs = self.road_intervals(vertical_roads, MAP_W)
        ys = self.road_intervals(horizontal_roads, MAP_H)

        for bx1, bx2 in xs:
            for by1, by2 in ys:
                block_w = bx2 - bx1 + 1
                block_h = by2 - by1 + 1
                if block_w < 7 or block_h < 7:
                    continue

                density = random.random()
                target = 1
                if block_w >= 16 and block_h >= 12:
                    target = 2 if density < 0.70 else 1
                if block_w >= 20 and block_h >= 14 and density < 0.35:
                    target = 3

                used = []
                for _ in range(target):
                    info_name = random.choices(
                        list(BUILDING_TYPES.keys()),
                        weights=[BUILDING_TYPES[k]["weight"] for k in BUILDING_TYPES]
                    )[0]
                    info = BUILDING_TYPES[info_name]

                    w = random.randint(*info["size"][0])
                    h = random.randint(*info["size"][1])

                    if w > block_w - 2 or h > block_h - 2:
                        continue

                    candidates = []
                    for y in range(by1, by2 - h + 2):
                        for x in range(bx1, bx2 - w + 2):
                            if self.can_place_building(x, y, w, h, used, bx1, by1, bx2, by2):
                                candidates.append((x, y))
                    if not candidates:
                        continue

                    x, y = random.choice(candidates)
                    floors = random.randint(*info["floors"])
                    floors = min(floors, MAX_BUILDING_FLOORS)
                    b = self.create_building(info_name, x, y, w, h, floors)
                    self.buildings.append(b)
                    used.append((x, y, w, h))

    def can_place_building(self, x, y, w, h, used, bx1, by1, bx2, by2):
        if x <= bx1 or y <= by1 or x + w - 1 >= bx2 or y + h - 1 >= by2:
            return False
        for ox, oy, ow, oh in used:
            if not (x + w + 1 < ox or ox + ow + 1 < x or y + h + 1 < oy or oy + oh + 1 < y):
                return False
        # Não invadir rua/calçada.
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if self.base_tile(xx, yy) in (ROAD_TILE, SIDEWALK_TILE):
                    return False
        return True

    # ========================================================
    # BUILDING CREATION
    # ========================================================

    def create_building(self, kind, x, y, w, h, floors):
        b = Building(
            id=self.next_building_id,
            kind=kind,
            x=x,
            y=y,
            w=w,
            h=h,
            floors=floors,
            roof_style=random.randint(0, 2),
        )
        self.next_building_id += 1

        for z in range(floors):
            fd = self.create_floor_layout(b, z)
            b.floors_data.append(fd)

        # Uma porta externa. Prédios grandes podem ter 2 ou 3.
        possible = self.external_door_candidates(b)
        door_count = 1
        if kind in ("Office", "Apartment", "Clinic") and random.random() < 0.65:
            door_count = 2
        if kind in ("Office", "Apartment") and random.random() < 0.25:
            door_count = 3
        random.shuffle(possible)
        chosen = []
        for p in possible:
            if all(max(abs(p[0] - q[0]), abs(p[1] - q[1])) > 2 for q in chosen):
                chosen.append(p)
            if len(chosen) >= door_count:
                break

        for gx, gy in chosen:
            lx, ly = gx - b.x, gy - b.y
            b.floors_data[0].tiles[(lx, ly)] = OPEN_DOOR_TILE if random.random() < 0.55 else CLOSED_DOOR_TILE
            b.floors_data[0].doors.add((lx, ly))
            b.exterior_doors.add((gx, gy))

        # Coloca escadas depois da porta.
        for z in range(floors):
            self.place_vertical_stairs(b, z)

        # Faz a casa aparecer no layer 0 também.
        return b

    def external_door_candidates(self, b):
        out = []
        for x in range(b.x + 1, b.x + b.w - 1):
            out.append((x, b.y))
            out.append((x, b.y + b.h - 1))
        for y in range(b.y + 1, b.y + b.h - 1):
            out.append((b.x, y))
            out.append((b.x + b.w - 1, y))
        return out

    def create_floor_layout(self, b, z):
        fd = FloorData(z=z)

        # Tudo dentro do footprint vira piso inicialmente.
        for ly in range(b.h):
            for lx in range(b.w):
                if lx == 0 or ly == 0 or lx == b.w - 1 or ly == b.h - 1:
                    fd.tiles[(lx, ly)] = WALL_TILE
                else:
                    fd.tiles[(lx, ly)] = FLOOR_TILE

        room_count = random.randint(
            BUILDING_TYPES[b.kind]["rooms"][0],
            BUILDING_TYPES[b.kind]["rooms"][1]
        )
        room_count = min(room_count, max(1, (b.w - 2) * (b.h - 2) // 12))

        # Divisórias simples, priorizando prédios maiores.
        if room_count >= 2:
            if b.w >= b.h:
                cuts = self.make_partition_cuts(b.w - 2, room_count, vertical=True)
                for lx in cuts:
                    gap_count = random.randint(1, 2)
                    gaps = random.sample(range(1, b.h - 1), min(gap_count, b.h - 2))
                    for ly in range(1, b.h - 1):
                        if ly not in gaps:
                            fd.tiles[(lx, ly)] = WALL_TILE
                        else:
                            fd.tiles[(lx, ly)] = CLOSED_DOOR_TILE if random.random() < 0.35 else OPEN_DOOR_TILE
                            fd.doors.add((lx, ly))
            else:
                cuts = self.make_partition_cuts(b.h - 2, room_count, vertical=False)
                for ly in cuts:
                    gap_count = random.randint(1, 2)
                    gaps = random.sample(range(1, b.w - 1), min(gap_count, b.w - 2))
                    for lx in range(1, b.w - 1):
                        if lx not in gaps:
                            fd.tiles[(lx, ly)] = WALL_TILE
                        else:
                            fd.tiles[(lx, ly)] = CLOSED_DOOR_TILE if random.random() < 0.35 else OPEN_DOOR_TILE
                            fd.doors.add((lx, ly))

            # Segunda direção para alguns prédios.
            if room_count >= 5 and min(b.w, b.h) >= 9:
                if b.w >= b.h:
                    ly = random.randint(3, b.h - 4)
                    gaps = random.sample(range(1, b.w - 1), min(2, b.w - 2))
                    for lx in range(1, b.w - 1):
                        if lx not in gaps:
                            fd.tiles[(lx, ly)] = WALL_TILE
                        else:
                            fd.tiles[(lx, ly)] = CLOSED_DOOR_TILE if random.random() < 0.30 else OPEN_DOOR_TILE
                            fd.doors.add((lx, ly))
                else:
                    lx = random.randint(3, b.w - 4)
                    gaps = random.sample(range(1, b.h - 1), min(2, b.h - 2))
                    for ly in range(1, b.h - 1):
                        if ly not in gaps:
                            fd.tiles[(lx, ly)] = WALL_TILE
                        else:
                            fd.tiles[(lx, ly)] = CLOSED_DOOR_TILE if random.random() < 0.30 else OPEN_DOOR_TILE
                            fd.doors.add((lx, ly))

        self.assign_rooms(fd, b)
        return fd

    def make_partition_cuts(self, span, room_count, vertical=True):
        if span < 5:
            return []
        desired = min(room_count - 1, 2 if span < 12 else 3)
        if desired <= 0:
            return []
        possible = list(range(3, span - 1))
        random.shuffle(possible)
        cuts = []
        for p in possible:
            if all(abs(p - q) >= 3 for q in cuts):
                cuts.append(p)
                if len(cuts) >= desired:
                    break
        if vertical:
            return [min(max(1, p), span - 1) for p in sorted(cuts)]
        return [min(max(1, p), span - 1) for p in sorted(cuts)]

    def assign_rooms(self, fd, b):
        # Descobre áreas conectadas de piso/porta/escada.
        seen = set()
        regions = []
        for ly in range(1, b.h - 1):
            for lx in range(1, b.w - 1):
                if (lx, ly) in seen:
                    continue
                if fd.tiles.get((lx, ly)) not in WALKABLE:
                    continue
                q = deque([(lx, ly)])
                seen.add((lx, ly))
                region = []
                while q:
                    cx, cy = q.popleft()
                    region.append((cx, cy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if not (1 <= nx < b.w - 1 and 1 <= ny < b.h - 1):
                            continue
                        if (nx, ny) in seen:
                            continue
                        if fd.tiles.get((nx, ny)) not in WALKABLE:
                            continue
                        seen.add((nx, ny))
                        q.append((nx, ny))
                if region:
                    regions.append(region)

        # Se divisórias não criaram regiões suficientes, continua sendo um grande cômodo.
        regions.sort(key=len, reverse=True)
        ordered_names = self.room_name_order(b.kind, len(regions))
        for i, region in enumerate(regions):
            name = ordered_names[i] if i < len(ordered_names) else random.choice(ROOM_TYPES)
            for pos in region:
                fd.rooms[pos] = name

    def room_name_order(self, kind, count):
        preferred = {
            "Shed": ["Storage"],
            "Small House": ["Living Room", "Kitchen", "Bedroom", "Bathroom"],
            "House": ["Living Room", "Kitchen", "Bedroom", "Bathroom", "Storage", "Office"],
            "Townhouse": ["Living Room", "Kitchen", "Bedroom", "Bathroom", "Bedroom", "Office"],
            "Office": ["Reception", "Office", "Office", "Meeting Room", "Server Room", "Storage", "Bathroom"],
            "Apartment": ["Living Room", "Kitchen", "Bedroom", "Bathroom", "Bedroom", "Storage", "Office"],
            "Clinic": ["Reception", "Office", "Bathroom", "Office", "Storage", "Meeting Room", "Server Room"],
        }
        base = preferred.get(kind, ROOM_TYPES)
        if count <= len(base):
            return base[:count]
        out = base[:]
        while len(out) < count:
            out.append(random.choice(ROOM_TYPES))
        return out

    def place_vertical_stairs(self, b, z):
        fd = b.floors_data[z]
        candidates = []
        for ly in range(2, b.h - 2):
            for lx in range(2, b.w - 2):
                if fd.tiles.get((lx, ly)) in WALKABLE and len(candidates) < 200:
                    candidates.append((lx, ly))
        if not candidates:
            return

        # Mantém o mesmo eixo de escada sempre que possível.
        if z > 0 and b.floors_data[z - 1].stairs:
            px, py = next(iter(b.floors_data[z - 1].stairs))
            candidates.sort(key=lambda p: abs(p[0] - px) + abs(p[1] - py))
            pos = candidates[0]
        else:
            pos = random.choice(candidates)

        lx, ly = pos
        if z == 0 and b.floors > 1:
            fd.tiles[(lx, ly)] = STAIR_UP_TILE
        elif z == b.floors - 1:
            if b.floors > 1:
                fd.tiles[(lx, ly)] = STAIR_DOWN_TILE
        else:
            fd.tiles[(lx, ly)] = STAIR_BOTH_TILE
        fd.stairs.add((lx, ly))
        fd.rooms[(lx, ly)] = "Stairs"

    # ========================================================
    # SPAWNS
    # ========================================================

    def find_spawn(self):
        # Prefer road/grass aberta, não dentro de prédios.
        candidates = []
        for y in range(MAP_H):
            for x in range(MAP_W):
                t = self.tile_at(x, y, 0)
                if t in (GRASS_TILE, ROAD_TILE, SIDEWALK_TILE):
                    candidates.append((x, y))
        return random.choice(candidates) if candidates else (2, 2)

    def find_spawn_on_layer(self, z=0, min_distance=10, building=None):
        px, py, pz = self.player["x"], self.player["y"], self.player["z"]
        for _ in range(3000):
            if building:
                x = random.randint(building.x + 1, building.x + building.w - 2)
                y = random.randint(building.y + 1, building.y + building.h - 2)
            else:
                x = random.randint(1, MAP_W - 2)
                y = random.randint(1, MAP_H - 2)
            if self.tile_at(x, y, z) not in WALKABLE:
                continue
            if z == pz:
                if self.grid_distance(x, y, px, py) < min_distance:
                    continue
            if self.zombie_at(x, y, z):
                continue
            return x, y
        return None

    def spawn_city_loot(self):
        # Exterior
        for _ in range(90):
            pos = self.find_spawn_on_layer(0, min_distance=0)
            if not pos:
                break
            x, y = pos
            if self.get_building(x, y) is not None:
                continue
            if random.random() < 0.65:
                self.add_random_item(x, y, 0, exterior=True)

        # Interior, respeitando cômodos.
        for b in self.buildings:
            info = BUILDING_TYPES[b.kind]
            amount = info["loot"] + random.randint(0, 3)
            for _ in range(amount * b.floors):
                z = random.randrange(b.floors)
                candidates = [
                    (lx, ly)
                    for ly in range(1, b.h - 1)
                    for lx in range(1, b.w - 1)
                    if b.floors_data[z].tiles.get((lx, ly)) in WALKABLE
                    and b.floors_data[z].tiles.get((lx, ly)) not in {
                        STAIR_UP_TILE,
                        STAIR_DOWN_TILE,
                        STAIR_BOTH_TILE,
                    }
                ]
                if not candidates:
                    continue
                lx, ly = random.choice(candidates)
                self.add_random_item(b.x + lx, b.y + ly, z, exterior=False)

    def add_random_item(self, x, y, z, exterior=False):
        if any(i["x"] == x and i["y"] == y and i["z"] == z for i in self.items):
            return
        kind = random.choices(
            ["food", "water", "medkit", "9mm", "shell", "pistol", "shotgun"],
            weights=[25, 24, 7, 21, 10, 8, 5] if not exterior else [30, 26, 4, 25, 8, 5, 2]
        )[0]
        amount = 1
        if kind == "9mm":
            amount = random.randint(4, 15)
        elif kind == "shell":
            amount = random.randint(1, 5)
        self.items.append({"x": x, "y": y, "z": z, "item": Item(kind, amount)})

    def spawn_zombies(self):
        # Zumbis mais numerosos na rua e alguns dentro dos prédios.
        for _ in range(60):
            if random.random() < 0.74:
                z = 0
                pos = self.find_spawn_on_layer(z, min_distance=12)
                if not pos:
                    continue
                x, y = pos
            else:
                if not self.buildings:
                    continue
                b = random.choice(self.buildings)
                z = random.randrange(b.floors)
                pos = self.find_spawn_on_layer(z, min_distance=5, building=b)
                if not pos:
                    continue
                x, y = pos

            hp = random.randint(30, 50)
            self.zombies.append(
                Zombie(
                    x=x,
                    y=y,
                    z=z,
                    max_hp=hp,
                    hp=hp,
                    damage=random.randint(5, 11),
                )
            )

    # ========================================================
    # BASIC HELPERS
    # ========================================================

    def inside(self, x, y):
        return 0 <= x < MAP_W and 0 <= y < MAP_H

    def walkable(self, x, y, z=None):
        if z is None:
            z = self.player["z"]
        return self.tile_at(x, y, z) in WALKABLE

    def grid_distance(self, x1, y1, x2, y2):
        return max(abs(x2 - x1), abs(y2 - y1))

    def zombie_at(self, x, y, z=None):
        if z is None:
            z = self.player["z"]
        for zombie in self.zombies:
            if zombie.alive and zombie.z == z and zombie.x == x and zombie.y == y:
                return zombie
        return None

    def item_at(self, x, y, z=None):
        if z is None:
            z = self.player["z"]
        for obj in self.items:
            if obj["z"] == z and obj["x"] == x and obj["y"] == y:
                return obj
        return None

    # ========================================================
    # FOG OF WAR
    # ========================================================

    def is_visible(self, x, y, z=None):
        if z is None:
            z = self.player["z"]
        return (z, x, y) in self.visible

    def is_explored(self, x, y, z=None):
        if z is None:
            z = self.player["z"]
        return (z, x, y) in self.explored

    def line_of_sight(self, x1, y1, x2, y2, z=None):
        if z is None:
            z = self.player["z"]
        if not self.inside(x1, y1) or not self.inside(x2, y2):
            return False

        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        x, y = x1, y1

        while True:
            if (x, y) != (x1, y1):
                if self.tile_at(x, y, z) in (WALL_TILE, CLOSED_DOOR_TILE, VOID_TILE):
                    return False
            if x == x2 and y == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
            if not self.inside(x, y):
                return False
        return True

    def update_fog_of_war(self):
        px = self.player["x"]
        py = self.player["y"]
        pz = self.player["z"]
        new_visible = set()
        radius_sq = VISION_RADIUS * VISION_RADIUS

        for y in range(max(0, py - VISION_RADIUS), min(MAP_H, py + VISION_RADIUS + 1)):
            for x in range(max(0, px - VISION_RADIUS), min(MAP_W, px + VISION_RADIUS + 1)):
                dx = x - px
                dy = y - py
                if dx * dx + dy * dy > radius_sq:
                    continue
                if self.line_of_sight(px, py, x, y, pz):
                    new_visible.add((pz, x, y))

        self.visible = new_visible
        self.explored.update(new_visible)

    # ========================================================
    # PATHFINDING
    # ========================================================

    def find_path(self, start, goal, z=None):
        if z is None:
            z = self.player["z"]
        sx, sy = start
        gx, gy = goal
        if not self.walkable(gx, gy, z):
            return []
        if not self.is_explored(gx, gy, z):
            return []

        queue = deque([(sx, sy)])
        came = {(sx, sy): None}
        dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))

        while queue:
            x, y = queue.popleft()
            if (x, y) == (gx, gy):
                break
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                if not self.inside(nx, ny):
                    continue
                if (nx, ny) in came:
                    continue
                if not self.walkable(nx, ny, z):
                    continue
                if self.zombie_at(nx, ny, z):
                    continue
                came[(nx, ny)] = (x, y)
                queue.append((nx, ny))

        if (gx, gy) not in came:
            return []

        path = []
        cur = (gx, gy)
        while cur is not None:
            path.append(cur)
            cur = came[cur]
        path.reverse()
        return path

    def path_to_adjacent(self, tx, ty, z=None, diagonal=True):
        if z is None:
            z = self.player["z"]
        if diagonal:
            neighbors = [
                (tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1),
                (tx + 1, ty + 1), (tx + 1, ty - 1), (tx - 1, ty + 1), (tx - 1, ty - 1),
            ]
        else:
            neighbors = [
                (tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)
            ]
        neighbors = [
            p for p in neighbors
            if self.inside(*p)
            and self.walkable(*p, z)
            and self.is_explored(*p, z)
            and self.zombie_at(*p, z) is None
        ]
        neighbors.sort(key=lambda p: abs(p[0] - self.player["x"]) + abs(p[1] - self.player["y"]))
        for p in neighbors:
            path = self.find_path((self.player["x"], self.player["y"]), p, z)
            if path:
                return path
        return []

    def path_to_door(self, dx, dy, z=None):
        if z is None:
            z = self.player["z"]
        path = self.path_to_adjacent(dx, dy, z=z, diagonal=True)
        return path

    # ========================================================
    # TURN / NEEDS
    # ========================================================

    def player_action(self):
        self.turn += 1
        self.update_needs()
        self.zombie_turn()
        self.update_fog_of_war()
        self.check_death()

    def update_needs(self):
        if self.turn % 6 == 0:
            self.player["hunger"] = min(100, self.player["hunger"] + 2)
            self.player["thirst"] = min(100, self.player["thirst"] + 3)

        if self.player["hunger"] >= 95:
            self.player["hp"] -= 1
            if self.turn % 10 == 0:
                self.message("Você está faminto!")
        if self.player["thirst"] >= 95:
            self.player["hp"] -= 1
            if self.turn % 10 == 0:
                self.message("Você está com muita sede!")

    # ========================================================
    # MOVEMENT
    # ========================================================

    def move_player(self, dx, dy):
        if self.dead:
            return
        self.path.clear()
        self.pending_door = None

        x, y, z = self.player["x"], self.player["y"], self.player["z"]
        nx, ny = x + dx, y + dy
        if not self.inside(nx, ny):
            return

        zombie = self.zombie_at(nx, ny, z)
        if zombie:
            self.melee_attack(zombie)
            return

        tile = self.tile_at(nx, ny, z)
        if tile == CLOSED_DOOR_TILE:
            self.message("A porta está fechada. Clique nela para abrir.")
            return
        if tile not in WALKABLE:
            self.message("Você não pode passar por aqui.")
            return

        self.player["x"] = nx
        self.player["y"] = ny
        self.pickup_items()
        self.player_action()

    def click_move(self, tx, ty):
        z = self.player["z"]
        if not self.inside(tx, ty):
            return
        if not self.is_explored(tx, ty, z):
            self.message("Esse local ainda está coberto pelo nevoeiro.")
            return

        self.path.clear()
        self.pending_door = None

        tile = self.tile_at(tx, ty, z)
        if tile == CLOSED_DOOR_TILE:
            if self.grid_distance(self.player["x"], self.player["y"], tx, ty) <= 1:
                self.open_door(tx, ty, z)
                return
            path = self.path_to_door(tx, ty, z)
            if path:
                self.path = path[1:]
                self.pending_door = (tx, ty, z)
            else:
                self.message("Não consigo chegar até essa porta.")
            return

        zombie = self.zombie_at(tx, ty, z)
        if zombie:
            path = self.path_to_adjacent(tx, ty, z=z, diagonal=True)
            if path:
                self.path = path[1:]
            return

        path = self.find_path((self.player["x"], self.player["y"]), (tx, ty), z)
        if len(path) > 1:
            self.path = path[1:]

    def process_auto_path(self):
        if not self.path:
            self.finish_pending_path()
            return

        nx, ny = self.path[0]
        z = self.player["z"]
        if not self.walkable(nx, ny, z):
            self.path.clear()
            return

        zombie = self.zombie_at(nx, ny, z)
        if zombie:
            self.path.clear()
            if self.grid_distance(self.player["x"], self.player["y"], zombie.x, zombie.y) <= 1:
                self.melee_attack(zombie)
            return

        self.player["x"] = nx
        self.player["y"] = ny
        self.path.pop(0)
        self.pickup_items()
        self.player_action()
        if not self.path:
            self.finish_pending_path()

    def finish_pending_path(self):
        if not self.pending_door:
            return
        dx, dy, z = self.pending_door
        self.pending_door = None
        if self.inside(dx, dy) and self.tile_at(dx, dy, z) == CLOSED_DOOR_TILE:
            if self.grid_distance(self.player["x"], self.player["y"], dx, dy) <= 1:
                self.open_door(dx, dy, z)

    # ========================================================
    # DOORS
    # ========================================================

    def set_tile_world(self, x, y, z, tile):
        b = self.get_building(x, y)
        if not b or not (0 <= z < b.floors):
            if z == 0:
                self.set_base(x, y, tile)
            return
        lx, ly = x - b.x, y - b.y
        b.floors_data[z].tiles[(lx, ly)] = tile

    def open_door(self, x, y, z=None):
        if z is None:
            z = self.player["z"]
        if not self.inside(x, y) or self.tile_at(x, y, z) != CLOSED_DOOR_TILE:
            return False
        if self.grid_distance(self.player["x"], self.player["y"], x, y) > 1:
            return False
        self.set_tile_world(x, y, z, OPEN_DOOR_TILE)
        self.path.clear()
        self.message("Você abriu a porta.")
        self.player_action()
        return True

    def close_nearby_door(self):
        px, py, z = self.player["x"], self.player["y"], self.player["z"]
        if self.tile_at(px, py, z) in (OPEN_DOOR_TILE,):
            self.message("Você está em cima da porta. Saia dela primeiro.")
            return False

        candidates = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = px + dx, py + dy
                if self.inside(nx, ny) and self.tile_at(nx, ny, z) == OPEN_DOOR_TILE:
                    candidates.append((nx, ny))
        if not candidates:
            self.message("Não há porta aberta próxima.")
            return False
        candidates.sort(key=lambda p: abs(p[0] - px) + abs(p[1] - py))
        dx, dy = candidates[0]
        self.set_tile_world(dx, dy, z, CLOSED_DOOR_TILE)
        self.path.clear()
        self.message("Você fechou a porta.")
        self.player_action()
        return True

    # ========================================================
    # Z LAYER / ESCADAS
    # ========================================================

    def current_building(self):
        return self.get_building(self.player["x"], self.player["y"])

    def change_floor(self, delta):
        b = self.current_building()
        z = self.player["z"]
        if not b:
            self.message("Você não está dentro de um prédio.")
            return

        tile = self.tile_at(self.player["x"], self.player["y"], z)
        if delta > 0:
            if tile not in (STAIR_UP_TILE, STAIR_BOTH_TILE):
                self.message("Você precisa estar em uma escada.")
                return
            if z + 1 >= b.floors:
                self.message("Você já está no último andar.")
                return
            self.player["z"] += 1
            self.path.clear()
            self.update_fog_of_war()
            self.reveal_current_floor_hint()
            self.message(f"Você subiu para o andar {self.player['z'] + 1}.")
            return

        if delta < 0:
            if tile not in (STAIR_DOWN_TILE, STAIR_BOTH_TILE):
                self.message("Você precisa estar em uma escada.")
                return
            if z <= 0:
                self.message("Você já está no térreo.")
                return
            self.player["z"] -= 1
            self.path.clear()
            self.update_fog_of_war()
            self.message(f"Você desceu para o andar {self.player['z'] + 1}.")

    def reveal_current_floor_hint(self):
        # Revela a área ao redor da escada sem quebrar o Fog.
        self.update_fog_of_war()

    # ========================================================
    # MELEE / RANGED
    # ========================================================

    def melee_attack(self, zombie):
        weapon = WEAPONS[self.player["weapon"]]
        if weapon["type"] != "melee":
            self.message("Sua arma atual é de longo alcance.")
            return

        distance = self.grid_distance(
            self.player["x"], self.player["y"], zombie.x, zombie.y
        )
        if distance != 1:
            self.message("O zumbi está longe demais.")
            return

        damage = random.randint(*weapon["damage"])
        zombie.hp -= damage
        self.path.clear()
        self.message(f"Você acertou o zumbi por {damage}.")

        if zombie.hp <= 0:
            zombie.alive = False
            self.kills += 1
            self.message("Zumbi morto!")
            self.spawn_zombie_loot(zombie.x, zombie.y, zombie.z)

        self.player_action()

    def ranged_attack(self, tx, ty):
        weapon_id = self.player["weapon"]
        weapon = WEAPONS[weapon_id]
        z = self.player["z"]
        if weapon["type"] != "ranged":
            self.message("Equipe uma arma de fogo primeiro.")
            return
        if not self.is_visible(tx, ty, z):
            self.message("Você não consegue ver esse alvo.")
            return
        zombie = self.zombie_at(tx, ty, z)
        if not zombie:
            self.message("Não há nenhum zumbi nesse local.")
            return

        distance = math.hypot(tx - self.player["x"], ty - self.player["y"])
        if distance > weapon["range"]:
            self.message("Alvo fora do alcance.")
            return
        if not self.line_of_sight(self.player["x"], self.player["y"], tx, ty, z):
            self.message("A parede ou porta fechada bloqueia o tiro.")
            return
        if self.player["mag"][weapon_id] <= 0:
            self.message("Arma descarregada. Pressione R.")
            return

        self.player["mag"][weapon_id] -= 1
        accuracy = max(0.50, weapon["accuracy"] - distance * 0.025)
        if random.random() <= accuracy:
            damage = random.randint(*weapon["damage"])
            # Shotgun recebe pequeno bônus próximo.
            if weapon_id == "shotgun" and distance <= 3:
                damage += random.randint(5, 12)
            zombie.hp -= damage
            self.message(f"Tiro! Você causou {damage} de dano.")
            if zombie.hp <= 0:
                zombie.alive = False
                self.kills += 1
                self.message("Zumbi morto a distância!")
                self.spawn_zombie_loot(zombie.x, zombie.y, zombie.z)
        else:
            self.message("Você errou o tiro.")
        self.path.clear()
        self.player_action()

    def spawn_zombie_loot(self, x, y, z):
        if random.random() < 0.40:
            kind = random.choice(["food", "water", "9mm", "shell", "medkit"])
            amount = 1
            if kind == "9mm":
                amount = random.randint(3, 10)
            elif kind == "shell":
                amount = random.randint(1, 3)
            self.items.append({"x": x, "y": y, "z": z, "item": Item(kind, amount)})

    # ========================================================
    # ITEM ACTIONS
    # ========================================================

    def pickup_items(self):
        z = self.player["z"]
        px, py = self.player["x"], self.player["y"]
        found = [i for i in self.items if i["z"] == z and i["x"] == px and i["y"] == py]
        for obj in found:
            item = obj["item"]
            k = item.kind
            if k == "food":
                self.player["food"] += item.amount
                self.message(f"Você pegou Food x{item.amount}.")
            elif k == "water":
                self.player["water"] += item.amount
                self.message(f"Você pegou Water x{item.amount}.")
            elif k == "medkit":
                self.player["medkit"] += item.amount
                self.message(f"Você pegou Medkit x{item.amount}.")
            elif k == "9mm":
                self.player["ammo"]["9mm"] += item.amount
                self.message(f"+{item.amount} munição 9mm.")
            elif k == "shell":
                self.player["ammo"]["shell"] += item.amount
                self.message(f"+{item.amount} cartuchos.")
            elif k == "pistol":
                self.player["weapons"]["pistol"] = True
                self.message("Você encontrou uma Pistol.")
            elif k == "shotgun":
                self.player["weapons"]["shotgun"] = True
                self.message("Você encontrou uma Shotgun!")
            self.items.remove(obj)

    def eat(self):
        if self.player["food"] <= 0:
            self.message("Você não tem Food.")
            return
        self.player["food"] -= 1
        self.player["hunger"] = max(0, self.player["hunger"] - 36)
        self.message("Você comeu.")
        self.player_action()

    def drink(self):
        if self.player["water"] <= 0:
            self.message("Você não tem Water.")
            return
        self.player["water"] -= 1
        self.player["thirst"] = max(0, self.player["thirst"] - 42)
        self.message("Você bebeu água.")
        self.player_action()

    def use_medkit(self):
        if self.player["medkit"] <= 0:
            self.message("Você não tem Medkit.")
            return
        if self.player["hp"] >= self.player["max_hp"]:
            self.message("Sua vida já está cheia.")
            return
        self.player["medkit"] -= 1
        self.player["hp"] = min(self.player["max_hp"], self.player["hp"] + 35)
        self.message("Você usou um Medkit.")
        self.player_action()

    def reload_weapon(self):
        wid = self.player["weapon"]
        weapon = WEAPONS[wid]
        if weapon["type"] != "ranged":
            self.message("Essa arma não usa munição.")
            return
        current = self.player["mag"][wid]
        if current >= weapon["mag_size"]:
            self.message("O carregador já está cheio.")
            return
        ammo_type = weapon["ammo_type"]
        reserve = self.player["ammo"][ammo_type]
        if reserve <= 0:
            self.message("Você não possui munição.")
            return
        amount = min(weapon["mag_size"] - current, reserve)
        self.player["mag"][wid] += amount
        self.player["ammo"][ammo_type] -= amount
        self.message(f"Você recarregou {amount} munição.")
        self.player_action()

    def equip_weapon(self, wid):
        if not self.player["weapons"].get(wid, False):
            self.message("Você ainda não possui essa arma.")
            return
        self.player["weapon"] = wid
        self.path.clear()
        self.pending_door = None
        self.message(f"Equipado: {WEAPONS[wid]['name']}.")

    # ========================================================
    # ZOMBIE AI
    # ========================================================

    def zombie_turn(self):
        occupied = {(z.x, z.y, z.z) for z in self.zombies if z.alive}
        px, py, pz = self.player["x"], self.player["y"], self.player["z"]

        for zombie in self.zombies:
            if not zombie.alive:
                continue

            occupied.discard((zombie.x, zombie.y, zombie.z))

            # Em outro andar, só reage se houver escada próxima ou fica vagando.
            if zombie.z != pz:
                self.zombie_wander(zombie, occupied)
                occupied.add((zombie.x, zombie.y, zombie.z))
                continue

            distance = self.grid_distance(zombie.x, zombie.y, px, py)

            if distance <= 1:
                damage = random.randint(3, zombie.damage)
                self.player["hp"] -= damage
                self.message(f"O zumbi te acertou por {damage}.")
                occupied.add((zombie.x, zombie.y, zombie.z))
                continue

            can_see = distance <= 13 and self.line_of_sight(zombie.x, zombie.y, px, py, pz)
            moved = False
            if can_see:
                zombie.alert = min(10, zombie.alert + 2)
                candidates = [
                    (zombie.x + 1, zombie.y), (zombie.x - 1, zombie.y),
                    (zombie.x, zombie.y + 1), (zombie.x, zombie.y - 1),
                ]
                candidates = [
                    p for p in candidates
                    if self.inside(*p)
                    and self.walkable(*p, pz)
                    and (p[0], p[1], pz) not in occupied
                    and p != (px, py)
                ]
                candidates.sort(key=lambda p: abs(p[0] - px) + abs(p[1] - py))
                if candidates:
                    nx, ny = candidates[0]
                    zombie.x, zombie.y = nx, ny
                    moved = True
            else:
                zombie.alert = max(0, zombie.alert - 1)

            if not moved and random.random() < (0.40 if zombie.alert == 0 else 0.15):
                self.zombie_wander(zombie, occupied)

            occupied.add((zombie.x, zombie.y, zombie.z))

    def zombie_wander(self, zombie, occupied):
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = zombie.x + dx, zombie.y + dy
            if not self.inside(nx, ny):
                continue
            if not self.walkable(nx, ny, zombie.z):
                continue
            if (nx, ny, zombie.z) in occupied:
                continue
            if (nx, ny, zombie.z) == (self.player["x"], self.player["y"], self.player["z"]):
                continue
            zombie.x, zombie.y = nx, ny
            return

    # ========================================================
    # DEATH / CAMERA
    # ========================================================

    def check_death(self):
        if self.player["hp"] <= 0:
            self.player["hp"] = 0
            self.dead = True
            self.path.clear()

    def restart(self):
        self.__init__()

    def get_camera_target(self):
        world_x = self.player["x"] * TILE + TILE / 2
        world_y = self.player["y"] * TILE + TILE / 2
        target_x = world_x - SCREEN_W / 2
        target_y = world_y - (SCREEN_H - HUD_H) / 2
        max_x = max(0, MAP_W * TILE - SCREEN_W)
        max_y = max(0, MAP_H * TILE - (SCREEN_H - HUD_H))
        return max(0, min(target_x, max_x)), max(0, min(target_y, max_y))

    def update_camera(self, dt):
        tx, ty = self.get_camera_target()
        factor = 1.0 - math.exp(-CAMERA_SMOOTH * dt)
        self.camera_x += (tx - self.camera_x) * factor
        self.camera_y += (ty - self.camera_y) * factor

    # ========================================================
    # INPUT
    # ========================================================

    def mouse_to_world(self, pos):
        mx, my = pos
        if my >= SCREEN_H - HUD_H:
            return None
        wx = int((mx + self.camera_x) // TILE)
        wy = int((my + self.camera_y) // TILE)
        if not self.inside(wx, wy):
            return None
        return wx, wy

    def handle_mouse(self, button, pos):
        self.mouse_pos = pos
        if self.dead or self.inventory_open:
            return
        tile = self.mouse_to_world(pos)
        if tile is None:
            return
        tx, ty = tile

        if button == 1:
            self.click_move(tx, ty)
        elif button == 3:
            if not self.is_visible(tx, ty, self.player["z"]):
                self.message("Você não consegue ver esse local.")
                return
            zombie = self.zombie_at(tx, ty, self.player["z"])
            if zombie:
                if WEAPONS[self.player["weapon"]]["type"] == "ranged":
                    self.ranged_attack(tx, ty)
                else:
                    self.melee_attack(zombie)

    def handle_key(self, key):
        if self.dead:
            if key == pygame.K_r:
                self.restart()
            elif key == pygame.K_q:
                self.running = False
            return

        if key == pygame.K_ESCAPE:
            self.path.clear()
            self.pending_door = None
            self.inventory_open = False
            return
        if key == pygame.K_q:
            self.running = False
            return
        if key == pygame.K_i:
            self.inventory_open = not self.inventory_open
            self.path.clear()
            return

        if key in (pygame.K_w, pygame.K_UP):
            self.move_player(0, -1); return
        if key in (pygame.K_s, pygame.K_DOWN):
            self.move_player(0, 1); return
        if key in (pygame.K_a, pygame.K_LEFT):
            self.move_player(-1, 0); return
        if key in (pygame.K_d, pygame.K_RIGHT):
            self.move_player(1, 0); return

        if key == pygame.K_1:
            self.equip_weapon("knife"); return
        if key == pygame.K_2:
            self.equip_weapon("pistol"); return
        if key == pygame.K_3:
            self.equip_weapon("shotgun"); return
        if key == pygame.K_r:
            self.reload_weapon(); return

        if key == pygame.K_e:
            if self.item_at(self.player["x"], self.player["y"], self.player["z"]):
                self.pickup_items()
            else:
                self.close_nearby_door()
            return

        if key == pygame.K_f:
            self.eat(); return
        if key == pygame.K_g:
            self.drink(); return
        if key == pygame.K_h:
            self.use_medkit(); return
        if key == pygame.K_u:
            self.change_floor(+1); return
        if key == pygame.K_j:
            self.change_floor(-1); return
        if key == pygame.K_SPACE:
            self.message("Você esperou.")
            self.player_action()

    # ========================================================
    # TOOLTIP
    # ========================================================

    def hover_name(self, tx, ty):
        z = self.player["z"]
        if not self.is_visible(tx, ty, z):
            return None

        zombie = self.zombie_at(tx, ty, z)
        if zombie:
            return "Zombie"

        item = self.item_at(tx, ty, z)
        if item:
            return item["item"].name()

        tile = self.tile_at(tx, ty, z)
        if tile == OPEN_DOOR_TILE:
            return "Open Door"
        if tile == CLOSED_DOOR_TILE:
            return "Closed Door"
        if tile == STAIR_UP_TILE:
            return "Stairs Up"
        if tile == STAIR_DOWN_TILE:
            return "Stairs Down"
        if tile == STAIR_BOTH_TILE:
            return "Stairs"

        room = self.room_at(tx, ty, z)
        if room:
            return room

        if tile == ROAD_TILE:
            return "Road"
        if tile == SIDEWALK_TILE:
            return "Sidewalk"
        if tile == GRASS_TILE:
            return "Grass"
        if tile == WALL_TILE:
            return "Wall"
        return None

    def draw_tooltip(self):
        if self.inventory_open or self.dead:
            return
        tile = self.mouse_to_world(self.mouse_pos)
        if tile is None:
            return
        tx, ty = tile
        name = self.hover_name(tx, ty)
        if not name:
            return

        mx, my = self.mouse_pos
        text = FONT.render(name, True, WHITE)
        pad_x, pad_y = 8, 4
        rect = pygame.Rect(
            mx + 14,
            my + 12,
            text.get_width() + pad_x * 2,
            text.get_height() + pad_y * 2,
        )
        view_h = SCREEN_H - HUD_H
        if rect.right > SCREEN_W:
            rect.x = mx - rect.width - 12
        if rect.bottom > view_h:
            rect.y = my - rect.height - 10

        pygame.draw.rect(screen, TOOLTIP_BG, rect, border_radius=5)
        pygame.draw.rect(screen, TOOLTIP_BORDER, rect, 1, border_radius=5)
        screen.blit(text, (rect.x + pad_x, rect.y + pad_y))

    # ========================================================
    # RENDER HELPERS
    # ========================================================

    def world_to_screen_rect(self, x, y, w=1, h=1):
        return pygame.Rect(
            int(x * TILE - self.camera_x),
            int(y * TILE - self.camera_y),
            int(w * TILE),
            int(h * TILE),
        )

    def visible_building_under(self, x, y, z):
        b = self.get_building(x, y)
        if not b:
            return None
        if not b.floor_contains(z, x, y):
            return None
        return b

    # ========================================================
    # MAP DRAW
    # ========================================================

    def draw_map(self):
        view_w_tiles = SCREEN_W // TILE + 3
        view_h_tiles = (SCREEN_H - HUD_H) // TILE + 3
        start_x = max(0, int(self.camera_x // TILE) - 2)
        start_y = max(0, int(self.camera_y // TILE) - 2)
        end_x = min(MAP_W, start_x + view_w_tiles + 4)
        end_y = min(MAP_H, start_y + view_h_tiles + 4)
        z = self.player["z"]
        current_b = self.current_building()

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                explored = self.is_explored(x, y, z)
                visible = self.is_visible(x, y, z)
                rect = self.world_to_screen_rect(x, y)
                if not explored:
                    pygame.draw.rect(screen, BLACK, rect)
                    continue

                tile = self.tile_at(x, y, z)
                b = self.get_building(x, y)

                # ------------------------------------------------
                # TELHADO: quando estamos do lado de fora, o prédio
                # aparece como um volume coberto. A porta externa
                # continua visível para permitir interação.
                # ------------------------------------------------
                render_as_roof = False
                if z == 0 and b and current_b is not b:
                    if tile not in b.floors_data[0].doors and tile != CLOSED_DOOR_TILE:
                        render_as_roof = True
                    if tile in (OPEN_DOOR_TILE, CLOSED_DOOR_TILE):
                        render_as_roof = False

                if render_as_roof:
                    self.draw_roof_tile(rect, b, x, y, visible)
                    continue

                color = self.tile_color(tile)
                if not visible:
                    color = tuple(max(0, int(c * 0.34)) for c in color)
                pygame.draw.rect(screen, color, rect)

                self.draw_tile_detail(rect, x, y, z, tile, visible, b)

    def tile_color(self, tile):
        return {
            GRASS_TILE: GRASS,
            ROAD_TILE: ROAD,
            SIDEWALK_TILE: SIDEWALK,
            FLOOR_TILE: FLOOR,
            WALL_TILE: WALL,
            OPEN_DOOR_TILE: OPEN_DOOR_COLOR,
            CLOSED_DOOR_TILE: CLOSED_DOOR_COLOR,
            STAIR_UP_TILE: STAIR_COLOR,
            STAIR_DOWN_TILE: STAIR_COLOR,
            STAIR_BOTH_TILE: STAIR_COLOR,
            VOID_TILE: BLACK,
        }.get(tile, BLACK)

    def draw_tile_detail(self, rect, x, y, z, tile, visible, building):
        if tile == GRASS_TILE:
            if (x * 17 + y * 31 + z * 7) % 11 == 0:
                c = GRASS_DARK
                if not visible:
                    c = tuple(max(0, int(v * 0.34)) for v in c)
                pygame.draw.line(
                    screen, c,
                    (rect.x + 5, rect.y + 17),
                    (rect.x + 7, rect.y + 11),
                    1,
                )
        elif tile == ROAD_TILE:
            if (z == 0) and (x + y) % 9 == 0:
                pygame.draw.line(
                    screen,
                    ROAD_DARK if visible else tuple(max(0, int(v * 0.34)) for v in ROAD_DARK),
                    (rect.x + 6, rect.y + 6),
                    (rect.x + 13, rect.y + 6),
                    1,
                )
        elif tile == SIDEWALK_TILE:
            if (x + y) % 4 == 0:
                c = SIDEWALK_DARK if visible else tuple(max(0, int(v * 0.34)) for v in SIDEWALK_DARK)
                pygame.draw.line(screen, c, (rect.x, rect.y + TILE - 2), (rect.right, rect.y + TILE - 2), 1)
        elif tile == WALL_TILE:
            pygame.draw.rect(
                screen,
                WALL_DARK if visible else tuple(max(0, int(v * 0.34)) for v in WALL_DARK),
                rect,
                2,
            )
        elif tile in (OPEN_DOOR_TILE, CLOSED_DOOR_TILE):
            door_color = OPEN_DOOR_COLOR if tile == OPEN_DOOR_TILE else CLOSED_DOOR_COLOR
            if not visible:
                door_color = tuple(max(0, int(c * 0.34)) for c in door_color)
            inner = rect.inflate(-7, -5)
            pygame.draw.rect(screen, door_color, inner, border_radius=2)
            if tile == CLOSED_DOOR_TILE:
                knob = (200, 172, 72) if visible else (65, 52, 22)
                pygame.draw.circle(screen, knob, (inner.right - 4, inner.centery), 2)
        elif tile in (STAIR_UP_TILE, STAIR_DOWN_TILE, STAIR_BOTH_TILE):
            c = STAIR_COLOR if visible else tuple(max(0, int(v * 0.34)) for v in STAIR_COLOR)
            pygame.draw.line(screen, c, (rect.x + 4, rect.bottom - 5), (rect.right - 4, rect.y + 5), 2)
            pygame.draw.line(screen, c, (rect.x + 4, rect.bottom - 9), (rect.right - 4, rect.y + 1), 1)
        pygame.draw.rect(screen, BLACK, rect, 1)

    def draw_roof_tile(self, rect, building, x, y, visible):
        base = [
            (72, 61, 72),
            (82, 64, 52),
            (61, 68, 77),
        ][building.roof_style]
        if not visible:
            base = tuple(max(0, int(c * 0.34)) for c in base)
        pygame.draw.rect(screen, base, rect)
        stripe = tuple(max(0, min(255, c + 10)) for c in base) if visible else base
        if building.roof_style == 0:
            pygame.draw.line(screen, stripe, (rect.x + 3, rect.y + TILE - 4), (rect.right - 3, rect.y + 4), 1)
        elif building.roof_style == 1:
            pygame.draw.line(screen, stripe, (rect.x + 5, rect.centery), (rect.right - 5, rect.centery), 1)
        else:
            pygame.draw.line(screen, stripe, (rect.x + 3, rect.y + 3), (rect.right - 3, rect.bottom - 3), 1)
            pygame.draw.line(screen, stripe, (rect.right - 3, rect.y + 3), (rect.x + 3, rect.bottom - 3), 1)
        pygame.draw.rect(screen, BLACK, rect, 1)

    # ========================================================
    # ENTITIES
    # ========================================================

    def draw_path(self):
        for x, y in self.path:
            if not self.is_explored(x, y, self.player["z"]):
                continue
            cx = int(x * TILE - self.camera_x + TILE / 2)
            cy = int(y * TILE - self.camera_y + TILE / 2)
            pygame.draw.circle(screen, PATH_COLOR, (cx, cy), 3)

    def draw_items(self):
        z = self.player["z"]
        for obj in self.items:
            if obj["z"] != z or not self.is_visible(obj["x"], obj["y"], z):
                continue
            sx = int(obj["x"] * TILE - self.camera_x + TILE / 2)
            sy = int(obj["y"] * TILE - self.camera_y + TILE / 2)
            k = obj["item"].kind
            color = ITEM_YELLOW
            if k == "food": color = ITEM_GREEN
            elif k == "water": color = ITEM_BLUE
            elif k == "medkit": color = ITEM_RED
            elif k in ("9mm", "shell"): color = ITEM_AMMO
            pygame.draw.circle(screen, color, (sx, sy), 7)
            text = FONT_TINY.render(obj["item"].symbol(), True, BLACK)
            screen.blit(text, (sx - text.get_width() // 2, sy - text.get_height() // 2))

    def draw_zombies(self):
        z = self.player["z"]
        for zombie in self.zombies:
            if not zombie.alive or zombie.z != z or not self.is_visible(zombie.x, zombie.y, z):
                continue
            sx = int(zombie.x * TILE - self.camera_x + TILE / 2)
            sy = int(zombie.y * TILE - self.camera_y + TILE / 2)
            pygame.draw.circle(screen, ZOMBIE_COLOR, (sx, sy), TILE // 2 - 3)
            text = FONT_TINY.render("Z", True, WHITE)
            screen.blit(text, (sx - text.get_width() // 2, sy - text.get_height() // 2))
            bw = TILE - 4
            pygame.draw.rect(screen, BLACK, (sx - bw // 2, sy - TILE // 2 + 2, bw, 3))
            hpw = int(bw * max(0, zombie.hp) / zombie.max_hp)
            pygame.draw.rect(screen, (80, 220, 80), (sx - bw // 2, sy - TILE // 2 + 2, hpw, 3))

    def draw_player(self):
        sx = int(self.player["x"] * TILE - self.camera_x + TILE / 2)
        sy = int(self.player["y"] * TILE - self.camera_y + TILE / 2)
        pygame.draw.circle(screen, PLAYER_COLOR, (sx, sy), TILE // 2 - 3)
        text = FONT_TINY.render("@", True, BLACK)
        screen.blit(text, (sx - text.get_width() // 2, sy - text.get_height() // 2))

    # ========================================================
    # HUD
    # ========================================================

    def draw_meter(self, x, y, width, height, value, label):
        pygame.draw.rect(screen, (30, 30, 33), (x, y, width, height), border_radius=3)
        ratio = max(0.0, min(1.0, value / 100.0))
        fill = (75, 190, 85)
        if value >= 70:
            fill = (225, 170, 60)
        if value >= 90:
            fill = (220, 70, 70)
        pygame.draw.rect(screen, fill, (x, y, int(width * ratio), height), border_radius=3)
        pygame.draw.rect(screen, HUD_BORDER, (x, y, width, height), 1, border_radius=3)
        text = FONT_SMALL.render(f"{label}: {value}%", True, WHITE)
        screen.blit(text, (x + 6, y + 2))

    def draw_hud(self):
        y = SCREEN_H - HUD_H
        pygame.draw.rect(screen, HUD_BG, (0, y, SCREEN_W, HUD_H))
        pygame.draw.line(screen, HUD_BORDER, (0, y), (SCREEN_W, y), 2)

        self.draw_meter(14, y + 10, 190, 23, self.player["hunger"], "Fome")
        self.draw_meter(214, y + 10, 190, 23, self.player["thirst"], "Sede")

        hp_ratio = self.player["hp"] / max(1, self.player["max_hp"])
        hp_pct = int(max(0, min(1, hp_ratio)) * 100)
        hp_fill = (70, 190, 80) if hp_ratio > 0.35 else (220, 75, 70)
        pygame.draw.rect(screen, (30, 30, 33), (414, y + 10, 190, 23), border_radius=3)
        pygame.draw.rect(screen, hp_fill, (414, y + 10, int(190 * hp_ratio), 23), border_radius=3)
        pygame.draw.rect(screen, HUD_BORDER, (414, y + 10, 190, 23), 1, border_radius=3)
        hp_text = FONT_SMALL.render(f"HP: {self.player['hp']}/{self.player['max_hp']} ({hp_pct}%)", True, WHITE)
        screen.blit(hp_text, (420, y + 12))

        weapon = WEAPONS[self.player["weapon"]]
        weapon_text = FONT.render(f"Arma: {weapon['name']}", True, WHITE)
        screen.blit(weapon_text, (620, y + 10))

        if weapon["type"] == "ranged":
            ammo_type = weapon["ammo_type"]
            ammo_text = FONT.render(
                f"Munição: {self.player['mag'][self.player['weapon']]}/{self.player['ammo'][ammo_type]}",
                True,
                WHITE,
            )
        else:
            ammo_text = FONT.render("Munição: --", True, WHITE)
        screen.blit(ammo_text, (820, y + 10))

        floor_text = FONT.render(
            f"Z: {self.player['z']} | Andar: {self.player['z'] + 1}",
            True,
            WHITE,
        )
        screen.blit(floor_text, (1040, y + 10))

        inv_text = FONT_SMALL.render(
            f"Food: {self.player['food']}   Water: {self.player['water']}   Medkits: {self.player['medkit']}   Kills: {self.kills}   Turno: {self.turn}",
            True,
            WHITE,
        )
        screen.blit(inv_text, (14, y + 42))

        b = self.current_building()
        place = f"Prédio: {b.kind} #{b.id} | Andares: {b.floors}" if b else "Exterior / Rua"
        place_text = FONT_SMALL.render(place, True, (205, 205, 210))
        screen.blit(place_text, (14, y + 62))

        msg_y = y + 84
        for msg in self.messages[-3:]:
            text = FONT_SMALL.render("> " + msg, True, (210, 210, 215))
            screen.blit(text, (14, msg_y))
            msg_y += 18

        controls = "Esq: andar/abrir  Dir: atacar  E: porta  F: comer  G: beber  H: medkit  U/J: andar 1/2/3: armas"
        control_text = FONT_TINY.render(controls, True, (155, 158, 164))
        screen.blit(control_text, (SCREEN_W - control_text.get_width() - 12, y + HUD_H - 18))

    # ========================================================
    # INVENTORY
    # ========================================================

    def draw_inventory(self):
        if not self.inventory_open:
            return
        view_h = SCREEN_H - HUD_H
        overlay = pygame.Surface((SCREEN_W, view_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 225))
        screen.blit(overlay, (0, 0))

        title = FONT_BIG.render("INVENTÁRIO", True, WHITE)
        screen.blit(title, (40, 28))

        lines = [
            f"Food: {self.player['food']}",
            f"Water: {self.player['water']}",
            f"Medkits: {self.player['medkit']}",
            "",
            "Armas:",
            f"[1] Faca: {'SIM' if self.player['weapons']['knife'] else 'NÃO'}",
            f"[2] Pistola: {'SIM' if self.player['weapons']['pistol'] else 'NÃO'}",
            f"[3] Shotgun: {'SIM' if self.player['weapons']['shotgun'] else 'NÃO'}",
            "",
            f"9mm: {self.player['ammo']['9mm']}",
            f"Cartuchos: {self.player['ammo']['shell']}",
            "",
            f"Andar atual: Z {self.player['z']} / {self.player['z'] + 1}",
            "",
            "ESC para fechar",
        ]
        y = 78
        for line in lines:
            text = FONT.render(line, True, WHITE)
            screen.blit(text, (45, y))
            y += 26

    # ========================================================
    # CURSOR
    # ========================================================

    def draw_cursor(self):
        if self.inventory_open:
            return
        tile = self.mouse_to_world(self.mouse_pos)
        if tile is None:
            return
        x, y = tile
        if not self.is_explored(x, y, self.player["z"]):
            return
        rect = self.world_to_screen_rect(x, y)
        pygame.draw.rect(screen, CURSOR_COLOR, rect, 1)

    # ========================================================
    # DEATH
    # ========================================================

    def draw_death(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 218))
        screen.blit(overlay, (0, 0))

        title = FONT_BIG.render("VOCÊ MORREU", True, (225, 65, 65))
        screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, SCREEN_H // 2 - 80))

        lines = [
            f"Turnos: {self.turn}",
            f"Zumbis mortos: {self.kills}",
            f"Andar em que morreu: Z {self.player['z']}",
            "",
            "R = reiniciar",
            "Q = sair",
        ]
        y = SCREEN_H // 2 - 35
        for line in lines:
            text = FONT.render(line, True, WHITE)
            screen.blit(text, (SCREEN_W // 2 - text.get_width() // 2, y))
            y += 27

    # ========================================================
    # DRAW
    # ========================================================

    def draw(self):
        screen.fill(BLACK)
        view = pygame.Rect(0, 0, SCREEN_W, SCREEN_H - HUD_H)
        old_clip = screen.get_clip()
        screen.set_clip(view)

        self.draw_map()
        self.draw_path()
        self.draw_items()
        self.draw_zombies()
        self.draw_player()
        self.draw_cursor()
        self.draw_tooltip()

        screen.set_clip(old_clip)
        self.draw_hud()
        self.draw_inventory()
        if self.dead:
            self.draw_death()


# ============================================================
# MAIN LOOP
# ============================================================

def main():
    game = Game()
    last_auto_move = 0

    while game.running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False
            elif event.type == pygame.KEYDOWN:
                game.handle_key(event.key)
            elif event.type == pygame.MOUSEMOTION:
                game.mouse_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONDOWN:
                game.mouse_pos = event.pos
                if event.button in (1, 3):
                    game.handle_mouse(event.button, event.pos)

        now = pygame.time.get_ticks()
        if (
            not game.dead
            and not game.inventory_open
            and game.path
            and now - last_auto_move >= AUTO_MOVE_DELAY
        ):
            game.process_auto_path()
            last_auto_move = now

        game.update_camera(dt)
        game.draw()
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
