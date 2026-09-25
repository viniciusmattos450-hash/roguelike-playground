from __future__ import annotations

import heapq
import math
import random
import sys
from dataclasses import dataclass

try:
    import pygame
except ModuleNotFoundError:
    pygame = None


# ============================================================
# OVERMAP GENERATOR
# ============================================================
#
# The Overmap is intentionally MACRO.
#
# One overmap cell represents one area, not one building.
#
# Examples:
#   field       -> AreaGenerator creates countryside
#   forest      -> AreaGenerator creates a forest area
#   city        -> AreaGenerator creates the entire city
#   village     -> AreaGenerator creates the entire village
#   farm        -> AreaGenerator creates the entire farm
#   ruin        -> AreaGenerator creates the entire ruin
#
# This file does NOT generate buildings or local tiles.
#
# The next layer is expected to live in:
#   area_generator.py
#
# Suggested architecture:
#
#   OvermapGenerator
#       -> macro terrain / roads / settlements / specials
#
#   AreaGenerator
#       -> city / village / farm / ruin / forest / etc.
#
# ============================================================


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

OVERMAP_W = 120
OVERMAP_H = 90

# Z is kept here so the API remains ready for future multi-level
# overmaps, even though generation currently happens at z=0.
OVERMAP_MIN_Z = 0
OVERMAP_MAX_Z = 5


# ------------------------------------------------------------
# Macro terrain identifiers
# ------------------------------------------------------------

T_FIELD = "field"
T_FIELD_CROPS = "field_crops"
T_FOREST = "forest"
T_FOREST_THICK = "forest_thick"
T_FOREST_TRAIL = "forest_trail"
T_SWAMP = "swamp"
T_LAKE = "lake"
T_RIVER = "river"
T_ROAD = "road"
T_HIGHWAY = "highway"
T_BRIDGE = "bridge"
T_CITY = "city"
T_VILLAGE = "village"
T_FARM = "farm"
T_CABIN = "cabin"
T_CAMPGROUND = "campground"
T_GAS_STATION = "gas_station"
T_PARKING = "parking"
T_RUIN = "ruin"

ROAD_TERRAINS = {
    T_ROAD,
    T_HIGHWAY,
    T_BRIDGE,
}

WATER_TERRAINS = {
    T_LAKE,
    T_RIVER,
}

SETTLEMENT_TERRAINS = {
    T_CITY,
    T_VILLAGE,
}


# ------------------------------------------------------------
# Data structures
# ------------------------------------------------------------

@dataclass
class OvermapCell:
    x: int
    y: int
    terrain: str = T_FIELD

    # A settlement/special occupies the whole OMT.
    area_id: str | None = None
    area_name: str | None = None
    area_size: str | None = None

    # Optional macro metadata for the AreaGenerator.
    population: int = 0
    district_hint: str | None = None

    # For diagnostics / future expansion.
    special_name: str | None = None


@dataclass
class Settlement:
    area_id: str
    name: str
    kind: str
    x: int
    y: int
    population: int
    size: str


@dataclass
class Special:
    area_id: str
    name: str
    kind: str
    x: int
    y: int


# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def stable_seed(*parts) -> int:
    """Deterministic seed; unlike hash(), it is stable across processes."""
    value = 2166136261

    for part in parts:
        text = str(part)

        for ch in text:
            value ^= ord(ch)
            value = (value * 16777619) & 0xFFFFFFFF

    return value


def weighted_choice(rng: random.Random, entries):
    total = sum(max(0, weight) for _value, weight in entries)

    if total <= 0:
        return entries[0][0]

    roll = rng.uniform(0, total)
    acc = 0.0

    for value, weight in entries:
        acc += max(0, weight)

        if roll <= acc:
            return value

    return entries[-1][0]


def neighbors4(x: int, y: int):
    yield x, y - 1
    yield x + 1, y
    yield x, y + 1
    yield x - 1, y


def neighbors8(x: int, y: int):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield x + dx, y + dy


# ------------------------------------------------------------
# Main generator
# ------------------------------------------------------------


class OvermapGenerator:
    """
    Generate only macro world structure.

    Important design rule:
        ONE OMT = ONE AREA PROMISE

    The overmap does not decide individual houses, shops, rooms, etc.
    That responsibility belongs to AreaGenerator.
    """

    CITY_NAMES = [
        "Ashford",
        "Raven Creek",
        "Millbrook",
        "Pine Ridge",
        "Blackwater",
        "Northgate",
        "Fairview",
        "Stonebridge",
        "Oak Hollow",
        "Redwood",
        "Cedar Vale",
        "Westfield",
        "Greystone",
        "Silver Lake",
        "Maplewood",
        "Brookhaven",
        "Kingsport",
        "Hawthorne",
        "Clearwater",
        "Riverside",
    ]

    VILLAGE_NAMES = [
        "Mason's Crossing",
        "Pine Hollow",
        "Mill Road",
        "Oak Creek",
        "Willow Bend",
        "Cedar Grove",
        "Fox Run",
        "Maple Cross",
        "Red Hill",
        "Old Mill",
        "Greenfield",
        "Stone Creek",
        "Lakeview",
        "Easton",
        "Westvale",
    ]

    SPECIAL_NAMES = {
        T_FARM: "Farm",
        T_CABIN: "Cabin",
        T_CAMPGROUND: "Campground",
        T_GAS_STATION: "Gas Station",
        T_RUIN: "Ruin",
    }

    def __init__(self, seed: int | None = None):
        self.seed = int(
            seed
            if seed is not None
            else random.randrange(1, 2**31 - 1)
        )

        self.rng = random.Random(self.seed)

        self.cells: list[list[OvermapCell]] = [
            [OvermapCell(x, y) for x in range(OVERMAP_W)]
            for y in range(OVERMAP_H)
        ]

        self.settlements: list[Settlement] = []
        self.cities: list[Settlement] = []
        self.villages: list[Settlement] = []
        self.specials: list[Special] = []

        # Keep successful inter-settlement routes so roadside systems
        # can place infrastructure using the actual road network.
        self.intercity_routes: list[dict] = []

        self.generate()

    # --------------------------------------------------------
    # Basic access
    # --------------------------------------------------------

    def cell(self, x: int, y: int) -> OvermapCell | None:
        if 0 <= x < OVERMAP_W and 0 <= y < OVERMAP_H:
            return self.cells[y][x]
        return None

    def set_terrain(self, x: int, y: int, terrain: str):
        cell = self.cell(x, y)

        if cell is not None:
            cell.terrain = terrain

    # --------------------------------------------------------
    # Generation pipeline
    # --------------------------------------------------------

    def generate(self):
        # Natural macro terrain first.
        self.generate_base_nature()
        self.generate_lakes()
        self.generate_rivers()
        self.generate_swamps()

        # Settlements are individual macro cells now.
        self.generate_settlements()

        # Transportation connects those macro areas.
        self.generate_intercity_roads()
        self.generate_village_roads()
        self.generate_forest_trails()

        # Finally place isolated area specials.
        self.generate_specials()

    # --------------------------------------------------------
    # Natural terrain
    # --------------------------------------------------------

    def generate_base_nature(self):
        for row in self.cells:
            for cell in row:
                cell.terrain = T_FIELD
                cell.area_id = None
                cell.area_name = None
                cell.area_size = None
                cell.population = 0
                cell.district_hint = None
                cell.special_name = None

        # Several broad forest regions.
        for _ in range(32):
            cx = self.rng.randint(4, OVERMAP_W - 5)
            cy = self.rng.randint(4, OVERMAP_H - 5)
            rx = self.rng.randint(5, 19)
            ry = self.rng.randint(4, 16)

            thick_bias = self.rng.uniform(0.18, 0.45)

            for y in range(
                max(0, cy - ry),
                min(OVERMAP_H, cy + ry + 1),
            ):
                for x in range(
                    max(0, cx - rx),
                    min(OVERMAP_W, cx + rx + 1),
                ):
                    nx = (x - cx) / max(1, rx)
                    ny = (y - cy) / max(1, ry)
                    d = nx * nx + ny * ny

                    if d <= 1.0:
                        chance = 0.92 - d * 0.34

                        if self.rng.random() < chance:
                            self.set_terrain(
                                x,
                                y,
                                (
                                    T_FOREST_THICK
                                    if self.rng.random() < thick_bias
                                    else T_FOREST
                                ),
                            )

        # Agricultural countryside.
        for _ in range(26):
            cx = self.rng.randint(4, OVERMAP_W - 5)
            cy = self.rng.randint(4, OVERMAP_H - 5)
            rx = self.rng.randint(2, 8)
            ry = self.rng.randint(2, 6)

            for y in range(
                max(0, cy - ry),
                min(OVERMAP_H, cy + ry + 1),
            ):
                for x in range(
                    max(0, cx - rx),
                    min(OVERMAP_W, cx + rx + 1),
                ):
                    nx = (x - cx) / max(1, rx)
                    ny = (y - cy) / max(1, ry)

                    if nx * nx + ny * ny <= 1.0:
                        if self.rng.random() < 0.70:
                            if self.cell(x, y).terrain in {
                                T_FIELD,
                                T_FIELD_CROPS,
                            }:
                                self.set_terrain(
                                    x,
                                    y,
                                    T_FIELD_CROPS,
                                )

    def generate_lakes(self):
        lake_count = self.rng.randint(3, 6)

        for _ in range(lake_count):
            cx = self.rng.randint(10, OVERMAP_W - 11)
            cy = self.rng.randint(8, OVERMAP_H - 9)
            rx = self.rng.randint(3, 9)
            ry = self.rng.randint(3, 8)

            for y in range(
                max(0, cy - ry),
                min(OVERMAP_H, cy + ry + 1),
            ):
                for x in range(
                    max(0, cx - rx),
                    min(OVERMAP_W, cx + rx + 1),
                ):
                    nx = (x - cx) / max(1, rx)
                    ny = (y - cy) / max(1, ry)

                    # Small deterministic distortion around the ellipse.
                    distortion = 1.0 + self.rng.uniform(-0.10, 0.10)

                    if nx * nx + ny * ny <= distortion:
                        self.set_terrain(
                            x,
                            y,
                            T_LAKE,
                        )

    def generate_rivers(self):
        """
        Generate large-scale rivers as wandering macro paths.

        They are intentionally macro; local water banks/shorelines belong
        to AreaGenerator.
        """
        river_count = self.rng.randint(1, 3)

        for idx in range(river_count):
            horizontal = idx % 2 == 0

            if horizontal:
                self._generate_horizontal_river()
            else:
                self._generate_vertical_river()

    def _generate_horizontal_river(self):
        y = self.rng.randint(
            10,
            OVERMAP_H - 11,
        )

        x = -2
        target_x = OVERMAP_W + 2

        drift = self.rng.uniform(-0.45, 0.45)
        phase = self.rng.uniform(0.0, math.tau)

        while x <= target_x:
            wave_a = math.sin(
                x * 0.085 + phase
            ) * 0.9

            wave_b = math.sin(
                x * 0.027 + phase * 1.7
            ) * 1.3

            drift += self.rng.uniform(
                -0.16,
                0.16,
            )

            drift = clamp(
                drift,
                -2.3,
                2.3,
            )

            yy = int(round(
                y + wave_a + wave_b + drift
            ))

            yy = clamp(
                yy,
                2,
                OVERMAP_H - 3,
            )

            width = 1

            if self.rng.random() < 0.12:
                width = 2

            for dy in range(
                -width,
                width + 1,
            ):
                self.set_terrain(
                    x,
                    yy + dy,
                    T_RIVER,
                )

            x += 1

    def _generate_vertical_river(self):
        x = self.rng.randint(
            10,
            OVERMAP_W - 11,
        )

        y = -2
        target_y = OVERMAP_H + 2

        drift = self.rng.uniform(-0.45, 0.45)
        phase = self.rng.uniform(0.0, math.tau)

        while y <= target_y:
            wave_a = math.cos(
                y * 0.078 + phase
            ) * 1.0

            wave_b = math.cos(
                y * 0.025 + phase * 1.3
            ) * 1.4

            drift += self.rng.uniform(
                -0.16,
                0.16,
            )

            drift = clamp(
                drift,
                -2.3,
                2.3,
            )

            xx = int(round(
                x + wave_a + wave_b + drift
            ))

            xx = clamp(
                xx,
                2,
                OVERMAP_W - 3,
            )

            width = 1

            if self.rng.random() < 0.12:
                width = 2

            for dx in range(
                -width,
                width + 1,
            ):
                self.set_terrain(
                    xx + dx,
                    y,
                    T_RIVER,
                )

            y += 1

    def generate_swamps(self):
        for _ in range(
            self.rng.randint(8, 14)
        ):
            cx = self.rng.randint(5, OVERMAP_W - 6)
            cy = self.rng.randint(5, OVERMAP_H - 6)

            if self.cell(cx, cy).terrain not in {
                T_FIELD,
                T_FOREST,
            }:
                continue

            rx = self.rng.randint(2, 7)
            ry = self.rng.randint(2, 5)

            for y in range(
                max(0, cy - ry),
                min(OVERMAP_H, cy + ry + 1),
            ):
                for x in range(
                    max(0, cx - rx),
                    min(OVERMAP_W, cx + rx + 1),
                ):
                    nx = (x - cx) / max(1, rx)
                    ny = (y - cy) / max(1, ry)

                    if nx * nx + ny * ny <= 1.0:
                        if self.rng.random() < 0.55:
                            if self.cell(x, y).terrain in {
                                T_FIELD,
                                T_FOREST,
                            }:
                                self.set_terrain(
                                    x,
                                    y,
                                    T_SWAMP,
                                )

    # --------------------------------------------------------
    # Settlements
    # --------------------------------------------------------

    def generate_settlements(self):
        """
        Place cities and villages as SINGLE overmap cells.

        No city footprint is generated here.
        AreaGenerator receives this cell and generates the full area.
        """
        settlement_count = self.rng.randint(4, 7)

        # Usually 2-4 real cities, with villages filling the rest.
        city_count = clamp(
            self.rng.randint(2, 4),
            1,
            settlement_count - 1,
        )

        village_count = settlement_count - city_count

        for city_index in range(city_count):
            settlement = self._place_settlement(
                kind=T_CITY,
                name=self.CITY_NAMES[city_index % len(self.CITY_NAMES)],
                index=city_index,
            )

            if settlement is not None:
                self.cities.append(settlement)
                self.settlements.append(settlement)

        for village_index in range(village_count):
            settlement = self._place_settlement(
                kind=T_VILLAGE,
                name=self.VILLAGE_NAMES[
                    village_index % len(self.VILLAGE_NAMES)
                ],
                index=village_index,
            )

            if settlement is not None:
                self.villages.append(settlement)
                self.settlements.append(settlement)

    def _place_settlement(
        self,
        kind: str,
        name: str,
        index: int,
    ) -> Settlement | None:
        for _attempt in range(600):
            x = self.rng.randint(
                8,
                OVERMAP_W - 9,
            )

            y = self.rng.randint(
                8,
                OVERMAP_H - 9,
            )

            cell = self.cell(x, y)

            if cell is None:
                continue

            # Avoid deep water and swamp.
            if cell.terrain in {
                T_LAKE,
                T_RIVER,
                T_SWAMP,
            }:
                continue

            # Villages can be closer to cities than cities can be to each other.
            min_distance = (
                15
                if kind == T_CITY
                else 8
            )

            too_close = False

            for settlement in self.settlements:
                distance = math.hypot(
                    x - settlement.x,
                    y - settlement.y,
                )

                required = min_distance

                if (
                    kind == T_CITY
                    and settlement.kind == T_CITY
                ):
                    required = 22

                elif (
                    kind == T_CITY
                    or settlement.kind == T_CITY
                ):
                    required = 13

                if distance < required:
                    too_close = True
                    break

            if too_close:
                continue

            if kind == T_CITY:
                population = self.rng.randint(
                    5000,
                    180000,
                )

                size = self.choose_city_size(
                    population
                )

                area_id = f"city_{index}_{x}_{y}"

            else:
                population = self.rng.randint(
                    120,
                    4500,
                )

                size = self.choose_village_size(
                    population
                )

                area_id = f"village_{index}_{x}_{y}"

            cell.terrain = kind
            cell.area_id = area_id
            cell.area_name = name
            cell.area_size = size
            cell.population = population
            cell.special_name = None

            # Optional hint for AreaGenerator.
            if kind == T_CITY:
                if population > 90000:
                    cell.district_hint = "mixed_urban"
                elif population > 30000:
                    cell.district_hint = "urban"
                else:
                    cell.district_hint = "small_city"
            else:
                cell.district_hint = "village"

            return Settlement(
                area_id=area_id,
                name=name,
                kind=kind,
                x=x,
                y=y,
                population=population,
                size=size,
            )

        return None

    @staticmethod
    def choose_city_size(population: int) -> str:
        if population >= 100000:
            return "large"

        if population >= 50000:
            return "medium_large"

        if population >= 20000:
            return "medium"

        return "small"

    @staticmethod
    def choose_village_size(population: int) -> str:
        if population >= 2500:
            return "large"

        if population >= 900:
            return "medium"

        return "small"

    # --------------------------------------------------------
    # Inter-settlement roads
    # --------------------------------------------------------

    def terrain_cost(self, terrain: str) -> float:
        return {
            T_FIELD: 1.0,
            T_FIELD_CROPS: 1.2,
            T_FOREST: 2.4,
            T_FOREST_THICK: 3.5,
            T_FOREST_TRAIL: 1.6,
            T_SWAMP: 5.5,
            T_LAKE: 18.0,
            T_RIVER: 16.0,
            T_ROAD: 0.20,
            T_HIGHWAY: 0.12,
            T_BRIDGE: 0.15,
            T_CITY: 0.30,
            T_VILLAGE: 0.45,
            T_FARM: 8.0,
            T_CABIN: 9.0,
            T_CAMPGROUND: 8.0,
            T_GAS_STATION: 5.0,
            T_PARKING: 4.0,
            T_RUIN: 9.0,
        }.get(terrain, 3.0)

    def astar(self, start: tuple[int, int], goal: tuple[int, int]):
        open_heap = [(0.0, start)]
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score = {start: 0.0}
        closed: set[tuple[int, int]] = set()

        while open_heap:
            _f, current = heapq.heappop(open_heap)

            if current in closed:
                continue

            closed.add(current)

            if current == goal:
                path = [current]

                while current in came_from:
                    current = came_from[current]
                    path.append(current)

                path.reverse()
                return path

            cx, cy = current

            for nx, ny in neighbors4(cx, cy):
                if not (
                    0 <= nx < OVERMAP_W
                    and 0 <= ny < OVERMAP_H
                ):
                    continue

                step_cost = self.terrain_cost(
                    self.cell(nx, ny).terrain
                )

                tentative = (
                    g_score[current]
                    + step_cost
                )

                if tentative >= g_score.get(
                    (nx, ny),
                    float("inf"),
                ):
                    continue

                came_from[(nx, ny)] = current
                g_score[(nx, ny)] = tentative

                heuristic = (
                    abs(goal[0] - nx)
                    + abs(goal[1] - ny)
                )

                heapq.heappush(
                    open_heap,
                    (
                        tentative + heuristic * 0.85,
                        (nx, ny),
                    ),
                )

        return []

    def generate_intercity_roads(self):
        """
        Connect cities and villages without turning the whole map into a grid.

        Each settlement gets a small number of meaningful macro connections.
        Successful routes are stored so roadside infrastructure can use the
        real transport corridors instead of random map coordinates.
        """
        self.intercity_routes.clear()

        if len(self.settlements) < 2:
            return

        connected: set[tuple[str, str]] = set()

        # 1. Main city-city network.
        if len(self.cities) >= 2:
            for city in self.cities:
                nearest = self._nearest_settlements(
                    city,
                    only_kind=T_CITY,
                )

                if nearest:
                    target = nearest[0]
                    self._connect_settlements(
                        city,
                        target,
                        connected,
                        major=True,
                    )

        # 2. Villages usually connect to the nearest city.
        for village in self.villages:
            candidates = self._nearest_settlements(
                village,
                only_kind=T_CITY,
            )

            if not candidates:
                candidates = self._nearest_settlements(
                    village,
                    only_kind=None,
                )

            if candidates:
                target = candidates[0]
                self._connect_settlements(
                    village,
                    target,
                    connected,
                    major=False,
                )

        # 3. A few secondary city-city links, only when the cities are not
        # already sufficiently connected.
        for city in self.cities:
            candidates = self._nearest_settlements(
                city,
                only_kind=T_CITY,
            )

            if len(candidates) < 2:
                continue

            target = candidates[1]

            if self.rng.random() < 0.45:
                self._connect_settlements(
                    city,
                    target,
                    connected,
                    major=True,
                )

    def _nearest_settlements(
        self,
        source: Settlement,
        only_kind: str | None,
    ):
        candidates = [
            settlement
            for settlement in self.settlements
            if settlement.area_id != source.area_id
            and (
                only_kind is None
                or settlement.kind == only_kind
            )
        ]

        return sorted(
            candidates,
            key=lambda settlement: math.hypot(
                settlement.x - source.x,
                settlement.y - source.y,
            ),
        )

    def _connect_settlements(
        self,
        a: Settlement,
        b: Settlement,
        connected: set[tuple[str, str]],
        major: bool,
    ):
        pair = tuple(
            sorted(
                (
                    a.area_id,
                    b.area_id,
                )
            )
        )

        if pair in connected:
            return

        connected.add(pair)

        path = self.astar(
            (a.x, a.y),
            (b.x, b.y),
        )

        if not path:
            return

        self.intercity_routes.append(
            {
                "a": a,
                "b": b,
                "path": list(path),
                "major": major,
            }
        )

        for x, y in path:
            cell = self.cell(x, y)

            if cell is None:
                continue

            # Roads crossing water become bridges.
            if cell.terrain in {
                T_RIVER,
                T_LAKE,
            }:
                cell.terrain = T_BRIDGE

            # Settlement cells remain settlement cells.
            elif cell.terrain in SETTLEMENT_TERRAINS:
                continue

            else:
                cell.terrain = (
                    T_HIGHWAY
                    if major
                    else T_ROAD
                )

    def generate_village_roads(self):
        """
        Small macro roads around villages.

        Villages occupy one OMT, so these are only approach roads on the
        macro map. The actual street layout is AreaGenerator's job.
        """
        for village in self.villages:
            # Occasionally add one local macro road extension beyond the
            # settlement connection, but do not create grids.
            if self.rng.random() > 0.45:
                continue

            directions = [
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
            ]

            dx, dy = self.rng.choice(directions)

            length = self.rng.randint(
                2,
                5,
            )

            for step in range(
                1,
                length + 1,
            ):
                x = village.x + dx * step
                y = village.y + dy * step

                cell = self.cell(x, y)

                if cell is None:
                    break

                if cell.terrain in {
                    T_LAKE,
                    T_RIVER,
                    T_CITY,
                    T_VILLAGE,
                }:
                    break

                if cell.terrain not in {
                    T_HIGHWAY,
                    T_BRIDGE,
                }:
                    cell.terrain = T_ROAD

    # --------------------------------------------------------
    # Forest trails
    # --------------------------------------------------------

    def generate_forest_trails(self):
        trail_count = max(
            6,
            len(self.settlements) * 2,
        )

        forest_positions = [
            (cell.x, cell.y)
            for row in self.cells
            for cell in row
            if cell.terrain in {
                T_FOREST,
                T_FOREST_THICK,
            }
            and cell.area_id is None
        ]

        if not forest_positions:
            return

        for _ in range(trail_count):
            x, y = self.rng.choice(
                forest_positions
            )

            for _step in range(
                self.rng.randint(
                    6,
                    18,
                )
            ):
                cell = self.cell(x, y)

                if cell is not None:
                    if cell.terrain in {
                        T_FOREST,
                        T_FOREST_THICK,
                    }:
                        cell.terrain = T_FOREST_TRAIL

                dx, dy = self.rng.choice(
                    [
                        (1, 0),
                        (-1, 0),
                        (0, 1),
                        (0, -1),
                    ]
                )

                x = clamp(
                    x + dx,
                    1,
                    OVERMAP_W - 2,
                )

                y = clamp(
                    y + dy,
                    1,
                    OVERMAP_H - 2,
                )

    # --------------------------------------------------------
    # Specials
    # --------------------------------------------------------

    def generate_specials(self):
        """
        Roadside gas stations are generated first because their placement
        depends on the already-generated intercity road network.

        Other countryside specials remain sparse and independent.
        """
        self.generate_roadside_gas_stations()

        desired = self.rng.randint(
            15,
            24,
        )

        attempts = 700
        placed = 0

        while (
            attempts > 0
            and placed < desired
        ):
            attempts -= 1

            x = self.rng.randint(
                3,
                OVERMAP_W - 4,
            )

            y = self.rng.randint(
                3,
                OVERMAP_H - 4,
            )

            cell = self.cell(
                x,
                y,
            )

            if cell is None:
                continue

            if cell.area_id is not None:
                continue

            if cell.terrain not in {
                T_FIELD,
                T_FIELD_CROPS,
                T_FOREST,
                T_FOREST_THICK,
                T_FOREST_TRAIL,
                T_SWAMP,
            }:
                continue

            # Gas stations are handled by the road-aware generator below.
            if cell.terrain == T_GAS_STATION:
                continue

            # Keep countryside specials separated.
            if any(
                math.hypot(
                    x - special.x,
                    y - special.y,
                ) < 2.5
                for special in self.specials
            ):
                continue

            if cell.terrain in {
                T_FOREST,
                T_FOREST_THICK,
                T_FOREST_TRAIL,
            }:
                kind = weighted_choice(
                    self.rng,
                    [
                        (T_CABIN, 38),
                        (T_CAMPGROUND, 14),
                        (T_RUIN, 8),
                    ],
                )

            elif cell.terrain in {
                T_FIELD,
                T_FIELD_CROPS,
            }:
                kind = weighted_choice(
                    self.rng,
                    [
                        (T_FARM, 38),
                        (T_RUIN, 6),
                    ],
                )

            else:
                kind = weighted_choice(
                    self.rng,
                    [
                        (T_CAMPGROUND, 10),
                        (T_RUIN, 7),
                    ],
                )

            area_id = f"{kind}_{x}_{y}"
            name = self.SPECIAL_NAMES.get(
                kind,
                kind.replace("_", " ").title(),
            )

            cell.terrain = kind
            cell.area_id = area_id
            cell.area_name = name
            cell.area_size = "small"
            cell.population = 0
            cell.special_name = name
            cell.district_hint = None

            self.specials.append(
                Special(
                    area_id=area_id,
                    name=name,
                    kind=kind,
                    x=x,
                    y=y,
                )
            )

            placed += 1

    def generate_roadside_gas_stations(self):
        """
        Place gas stations on useful roadside positions along major
        city-to-city routes.

        The station itself occupies a neighboring OMT to the road, leaving
        the road intact. AreaGenerator can then inspect connection_mask() and
        know which side of the station has road access.
        """
        # Both highway and normal road corridors can receive roadside
        # service. Highways are preferred, but ordinary inter-settlement
        # roads are valid too (especially city-village routes).
        service_routes = [
            route
            for route in self.intercity_routes
            if (
                route["a"].kind in SETTLEMENT_TERRAINS
                and route["b"].kind in SETTLEMENT_TERRAINS
                and len(route["path"]) >= 8
            )
        ]

        if not service_routes:
            return

        # Long corridors are better candidates for roadside services.
        # Keep at least one normal-road corridor in the front of the queue
        # when one exists, so the two available stations do not both end up
        # on highways.
        highway_routes = sorted(
            (
                route
                for route in service_routes
                if route.get("major")
            ),
            key=lambda route: len(route["path"]),
            reverse=True,
        )

        road_routes = sorted(
            (
                route
                for route in service_routes
                if not route.get("major")
            ),
            key=lambda route: len(route["path"]),
            reverse=True,
        )

        service_routes = []

        if highway_routes:
            service_routes.append(highway_routes[0])

        if road_routes:
            service_routes.append(road_routes[0])

        remaining_routes = [
            route
            for route in service_routes
            if False
        ]

        selected_ids = {
            id(route)
            for route in service_routes
        }

        remaining_routes = sorted(
            (
                route
                for route in highway_routes[1:] + road_routes[1:]
                if id(route) not in selected_ids
            ),
            key=lambda route: len(route["path"]),
            reverse=True,
        )

        service_routes.extend(remaining_routes)

        placed = 0

        for route_index, route in enumerate(
            service_routes
        ):
            path = route["path"]
            a = route["a"]
            b = route["b"]

            route_length = len(path)

            if route_length < 12:
                continue

            # Highways are preferred, but ordinary roads deliberately get
            # a guaranteed first opportunity when the generator has at least
            # one viable road corridor. Later roads are less likely to get
            # another station.
            route_is_major = bool(route.get("major"))

            is_primary_highway = (
                route_is_major
                and highway_routes
                and route is highway_routes[0]
            )

            is_primary_road = (
                (not route_is_major)
                and road_routes
                and route is road_routes[0]
            )

            if is_primary_highway or is_primary_road:
                chance = 1.0
            elif route_is_major:
                chance = (
                    0.65
                    if route_length >= 35
                    else 0.45
                )
            else:
                chance = (
                    0.50
                    if route_length >= 20
                    else 0.30
                )

            if self.rng.random() > chance:
                continue

            # Avoid the city endpoints; a gas station belongs on the trip,
            # not right outside the city center.
            start_index = max(
                4,
                int(route_length * 0.20),
            )

            end_index = min(
                route_length - 5,
                int(route_length * 0.80),
            )

            if start_index >= end_index:
                continue

            candidates = []

            # Sample the corridor instead of checking every path cell. This
            # keeps generation inexpensive on long routes.
            for path_index in range(
                start_index,
                end_index + 1,
                2,
            ):
                road_x, road_y = path[path_index]

                for sx, sy in (
                    (road_x + 1, road_y),
                    (road_x - 1, road_y),
                    (road_x, road_y + 1),
                    (road_x, road_y - 1),
                ):
                    cell = self.cell(
                        sx,
                        sy,
                    )

                    if cell is None:
                        continue

                    if cell.area_id is not None:
                        continue

                    if cell.terrain not in {
                        T_FIELD,
                        T_FIELD_CROPS,
                        T_FOREST,
                        T_FOREST_TRAIL,
                    }:
                        continue

                    # Stay away from the settlement endpoints.
                    dist_a = math.hypot(
                        sx - a.x,
                        sy - a.y,
                    )

                    dist_b = math.hypot(
                        sx - b.x,
                        sy - b.y,
                    )

                    if dist_a < 5.0 or dist_b < 5.0:
                        continue

                    # Don't stack services next to another special.
                    if any(
                        math.hypot(
                            sx - special.x,
                            sy - special.y,
                        ) < 5.0
                        for special in self.specials
                    ):
                        continue

                    # Prefer open roadside terrain. A station in dense forest
                    # is possible, but less likely than one in a field.
                    terrain_score = {
                        T_FIELD: 1.00,
                        T_FIELD_CROPS: 0.90,
                        T_FOREST_TRAIL: 0.70,
                        T_FOREST: 0.55,
                    }.get(
                        cell.terrain,
                        0.0,
                    )

                    # Normal roads remain valid service corridors; highways
                    # simply get a modest placement preference.
                    route_type_score = (
                        0.45
                        if route_is_major
                        else 0.20
                    )

                    # Deterministic candidate noise.
                    noise_seed = stable_seed(
                        self.seed,
                        "gas-station",
                        a.area_id,
                        b.area_id,
                        sx,
                        sy,
                    )

                    noise = (
                        noise_seed % 10000
                    ) / 10000.0

                    center_distance = abs(
                        path_index
                        - route_length / 2.0
                    )

                    center_score = 1.0 - (
                        center_distance
                        / max(
                            1.0,
                            route_length / 2.0,
                        )
                    )

                    score = (
                        terrain_score * 2.0
                        + center_score * 1.2
                        + route_type_score
                        + noise * 0.7
                    )

                    candidates.append(
                        (
                            score,
                            sx,
                            sy,
                        )
                    )

            if not candidates:
                continue

            candidates.sort(
                key=lambda value: value[0],
                reverse=True,
            )

            chosen = None

            for _score, sx, sy in candidates:
                if any(
                    math.hypot(
                        sx - special.x,
                        sy - special.y,
                    ) < 7.0
                    for special in self.specials
                ):
                    continue

                # Make sure the station has a direct neighbor of the
                # same road class as the route being serviced. This matters
                # because a normal road can cross or overlap a highway; a
                # station chosen for a normal road must actually touch T_ROAD,
                # not merely some road-like terrain.
                desired_road_terrain = (
                    T_HIGHWAY
                    if route_is_major
                    else T_ROAD
                )

                if not any(
                    neighbor is not None
                    and neighbor.terrain == desired_road_terrain
                    for nx, ny in neighbors4(sx, sy)
                    for neighbor in [
                        self.cell(nx, ny)
                    ]
                ):
                    continue

                chosen = (
                    sx,
                    sy,
                )
                break

            if chosen is None:
                continue

            sx, sy = chosen

            cell = self.cell(
                sx,
                sy,
            )

            if cell is None:
                continue

            area_id = (
                f"gas_station_{sx}_{sy}"
            )

            cell.terrain = T_GAS_STATION
            cell.area_id = area_id
            cell.area_name = "Gas Station"
            cell.area_size = "small"
            cell.population = 0
            cell.special_name = "Gas Station"
            cell.district_hint = "roadside_service"

            self.specials.append(
                Special(
                    area_id=area_id,
                    name="Gas Station",
                    kind=T_GAS_STATION,
                    x=sx,
                    y=sy,
                )
            )

            placed += 1

            # A second station is only allowed on another route.
            if placed >= 2:
                break

    def _place_special_parking(self, x: int, y: int):
        """
        Compatibility helper retained for older callers.

        Roadside gas stations now use their road adjacency directly, so
        parking does not need to be randomly reserved at the macro level.
        """
        candidates = list(
            neighbors4(x, y)
        )

        self.rng.shuffle(
            candidates
        )

        for nx, ny in candidates:
            cell = self.cell(
                nx,
                ny,
            )

            if cell is None:
                continue

            if cell.area_id is not None:
                continue

            if cell.terrain in {
                T_FIELD,
                T_FIELD_CROPS,
            }:
                cell.terrain = T_PARKING
                cell.area_id = (
                    f"parking_{nx}_{ny}"
                )
                cell.area_name = "Parking"
                cell.area_size = "small"
                return

    # --------------------------------------------------------
    # Queries / diagnostics
    # --------------------------------------------------------

    def count_terrain(self, terrain: str) -> int:
        return sum(
            cell.terrain == terrain
            for row in self.cells
            for cell in row
        )

    def terrain_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}

        for row in self.cells:
            for cell in row:
                counts[cell.terrain] = (
                    counts.get(cell.terrain, 0) + 1
                )

        return counts

    def connection_mask(self, x: int, y: int):
        """Return N/E/S/W connectivity for macro roads."""
        result = []

        for nx, ny in (
            (x, y - 1),
            (x + 1, y),
            (x, y + 1),
            (x - 1, y),
        ):
            neighbor = self.cell(
                nx,
                ny,
            )

            result.append(
                neighbor is not None
                and neighbor.terrain in ROAD_TERRAINS
            )

        return tuple(result)

    def settlement_at(
        self,
        x: int,
        y: int,
    ) -> Settlement | None:
        for settlement in self.settlements:
            if (
                settlement.x == x
                and settlement.y == y
            ):
                return settlement

        return None

    def area_info(
        self,
        x: int,
        y: int,
    ) -> dict:
        """Small, stable contract for AreaGenerator."""
        cell = self.cell(x, y)

        if cell is None:
            return {
                "type": "void",
                "x": x,
                "y": y,
            }

        return {
            "type": cell.terrain,
            "x": x,
            "y": y,
            "area_id": cell.area_id,
            "name": cell.area_name,
            "size": cell.area_size,
            "population": cell.population,
            "district_hint": cell.district_hint,
            "connections": self.connection_mask(x, y),
        }


# ============================================================
# SELF TEST
# ============================================================


def self_test(seed: int | None = None):
    overmap = OvermapGenerator(seed)

    if not overmap.settlements:
        raise AssertionError(
            "No settlements generated"
        )

    if not overmap.cities:
        raise AssertionError(
            "No cities generated"
        )

    if not overmap.villages:
        raise AssertionError(
            "No villages generated"
        )

    # Cities/villages must occupy exactly one OMT each.
    for settlement in overmap.settlements:
        cell = overmap.cell(
            settlement.x,
            settlement.y,
        )

        if cell is None:
            raise AssertionError(
                "Settlement points outside map"
            )

        if cell.terrain != settlement.kind:
            raise AssertionError(
                "Settlement terrain mismatch"
            )

        if cell.area_id != settlement.area_id:
            raise AssertionError(
                "Settlement area_id mismatch"
            )

    # No city footprint should exist in the macro generator.
    # Every city is represented by exactly one city OMT.
    if overmap.count_terrain(T_CITY) != len(
        overmap.cities
    ):
        raise AssertionError(
            "City OMT count does not match city count"
        )

    if overmap.count_terrain(T_VILLAGE) != len(
        overmap.villages
    ):
        raise AssertionError(
            "Village OMT count does not match village count"
        )

    # All cells keep valid coordinates.
    for row in overmap.cells:
        for cell in row:
            if not (
                0 <= cell.x < OVERMAP_W
                and 0 <= cell.y < OVERMAP_H
            ):
                raise AssertionError(
                    "Invalid overmap coordinates"
                )

    print("OVERMAP SELF-TEST PASS")
    print(f"seed={overmap.seed}")
    print(f"cities={len(overmap.cities)}")
    print(f"villages={len(overmap.villages)}")
    print(f"specials={len(overmap.specials)}")
    print("terrain_counts:")

    for terrain, count in sorted(
        overmap.terrain_counts().items()
    ):
        print(
            f"  {terrain:18s} {count}"
        )

    # Gas stations must be roadside infrastructure, never isolated specials.
    for special in overmap.specials:
        if special.kind != T_GAS_STATION:
            continue

        mask = overmap.connection_mask(
            special.x,
            special.y,
        )

        if not any(mask):
            raise AssertionError(
                "Gas station is not adjacent to a road"
            )

    gas_count = sum(
        1
        for special in overmap.specials
        if special.kind == T_GAS_STATION
    )

    gas_next_to_road = 0
    gas_next_to_highway = 0

    for special in overmap.specials:
        if special.kind != T_GAS_STATION:
            continue

        adjacent = [
            overmap.cell(nx, ny)
            for nx, ny in neighbors4(
                special.x,
                special.y,
            )
        ]

        terrain_set = {
            cell.terrain
            for cell in adjacent
            if cell is not None
        }

        if T_ROAD in terrain_set:
            gas_next_to_road += 1
        if T_HIGHWAY in terrain_set:
            gas_next_to_highway += 1

    print(
        f"gas_stations={gas_count}"
    )
    print(
        f"gas_next_to_road={gas_next_to_road}"
    )
    print(
        f"gas_next_to_highway={gas_next_to_highway}"
    )

    print("settlements:")

    for settlement in overmap.settlements:
        print(
            f"  {settlement.kind:8s}"
            f" {settlement.name:20s}"
            f" @ {settlement.x:3d},{settlement.y:3d}"
            f" size={settlement.size:12s}"
            f" population={settlement.population}"
        )


# ============================================================
# PYGAME OVERMAP VIEWER
# ============================================================

SCREEN_W = 1360
SCREEN_H = 840
FPS = 60

OVERMAP_BASE_TILE = 10
OVERMAP_MIN_ZOOM = 0.45
OVERMAP_MAX_ZOOM = 2.6

COL_BG = (18, 20, 22)
COL_PANEL = (22, 24, 28)
COL_PANEL_2 = (29, 32, 37)
COL_TEXT = (238, 238, 238)
COL_MUTED = (167, 173, 180)
COL_HIGHLIGHT = (255, 211, 82)
COL_WHITE = (255, 255, 255)
COL_SELECTION = (255, 224, 90)

OM_COLORS = {
    T_FIELD: (112, 132, 72),
    T_FIELD_CROPS: (141, 146, 61),
    T_FOREST: (43, 90, 50),
    T_FOREST_THICK: (29, 69, 38),
    T_FOREST_TRAIL: (54, 99, 52),
    T_SWAMP: (65, 90, 73),
    T_LAKE: (52, 92, 145),
    T_RIVER: (62, 112, 176),
    T_ROAD: (114, 111, 103),
    T_HIGHWAY: (164, 158, 144),
    T_BRIDGE: (139, 126, 90),
    T_CITY: (194, 146, 86),
    T_VILLAGE: (180, 139, 91),
    T_FARM: (180, 160, 76),
    T_CABIN: (136, 101, 69),
    T_CAMPGROUND: (106, 121, 73),
    T_GAS_STATION: (176, 149, 76),
    T_PARKING: (100, 99, 96),
    T_RUIN: (97, 92, 88),
}

OM_SYMBOLS = {
    T_FIELD: ".",
    T_FIELD_CROPS: ",",
    T_FOREST: "F",
    T_FOREST_THICK: "F",
    T_FOREST_TRAIL: "f",
    T_SWAMP: "s",
    T_LAKE: "~",
    T_RIVER: "~",
    T_ROAD: "-",
    T_HIGHWAY: "=",
    T_BRIDGE: "#",
    T_CITY: "C",
    T_VILLAGE: "V",
    T_FARM: "H",
    T_CABIN: "c",
    T_CAMPGROUND: "G",
    T_GAS_STATION: "g",
    T_PARKING: "P",
    T_RUIN: "%",
}

OM_NAMES = {
    T_FIELD: "Field",
    T_FIELD_CROPS: "Crops",
    T_FOREST: "Forest",
    T_FOREST_THICK: "Dense Forest",
    T_FOREST_TRAIL: "Forest Trail",
    T_SWAMP: "Swamp",
    T_LAKE: "Lake",
    T_RIVER: "River",
    T_ROAD: "Road",
    T_HIGHWAY: "Highway",
    T_BRIDGE: "Bridge",
    T_CITY: "City",
    T_VILLAGE: "Village",
    T_FARM: "Farm",
    T_CABIN: "Cabin",
    T_CAMPGROUND: "Campground",
    T_GAS_STATION: "Gas Station",
    T_PARKING: "Parking",
    T_RUIN: "Ruin",
}


def terrain_name(terrain: str) -> str:
    return OM_NAMES.get(terrain, terrain.replace("_", " ").title())


class OvermapViewer:
    """Interactive visual viewer for the macro Overmap only."""

    def __init__(self, seed: int | None = None):
        if pygame is None:
            raise RuntimeError(
                "pygame não está instalado. Instale com:\n"
                "  python -m pip install pygame-ce"
            )

        pygame.init()
        pygame.display.set_caption("Mini Cataclysm - Macro Overmap")
        self.screen = pygame.display.set_mode(
            (SCREEN_W, SCREEN_H),
            pygame.RESIZABLE,
        )
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", 15)
        self.small_font = pygame.font.SysFont("consolas", 12)
        self.title_font = pygame.font.SysFont("consolas", 19, bold=True)
        self.big_font = pygame.font.SysFont("consolas", 25, bold=True)

        self.generator = OvermapGenerator(seed)
        self.overmap_z = 0
        self.zoom = 1.0

        self.selected = None
        self.hover = None

        self.camera_x = OVERMAP_W / 2
        self.camera_y = OVERMAP_H / 2

        self.dragging = False
        self.last_mouse = (0, 0)
        self.show_help = False
        self.running = True

    # --------------------------------------------------------
    # Camera
    # --------------------------------------------------------

    def tile_size(self) -> float:
        return OVERMAP_BASE_TILE * self.zoom

    def view_left(self) -> int:
        return 290

    def world_to_screen(self, x: float, y: float):
        tile = self.tile_size()
        sw, sh = self.screen.get_size()
        view_w = sw - self.view_left()

        sx = (
            self.view_left()
            + view_w / 2
            + (x - self.camera_x) * tile
        )
        sy = sh / 2 + (y - self.camera_y) * tile
        return sx, sy

    def screen_to_world(self, sx: int, sy: int):
        tile = self.tile_size()
        sw, sh = self.screen.get_size()
        view_w = sw - self.view_left()

        x = math.floor(
            (sx - self.view_left() - view_w / 2) / tile
            + self.camera_x
        )
        y = math.floor(
            (sy - sh / 2) / tile
            + self.camera_y
        )
        return int(x), int(y)

    def clamp_camera(self):
        self.camera_x = clamp(
            self.camera_x,
            0,
            OVERMAP_W - 1,
        )
        self.camera_y = clamp(
            self.camera_y,
            0,
            OVERMAP_H - 1,
        )

    def zoom_at(self, factor: float, mouse_pos):
        before = self.screen_to_world(*mouse_pos)

        self.zoom = clamp(
            self.zoom * factor,
            OVERMAP_MIN_ZOOM,
            OVERMAP_MAX_ZOOM,
        )

        after = self.screen_to_world(*mouse_pos)

        self.camera_x += before[0] - after[0]
        self.camera_y += before[1] - after[1]
        self.clamp_camera()

    def center_on(self, x: int, y: int):
        self.camera_x = float(x)
        self.camera_y = float(y)
        self.clamp_camera()

    # --------------------------------------------------------
    # Selection
    # --------------------------------------------------------

    def select_cell(self, x: int, y: int):
        cell = self.generator.cell(x, y)
        if cell is None:
            self.selected = None
            return

        self.selected = (x, y)
        self.center_on(x, y)

    # --------------------------------------------------------
    # Input
    # --------------------------------------------------------

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return

        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(
                (event.w, event.h),
                pygame.RESIZABLE,
            )
            return

        if event.type == pygame.KEYDOWN:
            self.handle_key(event.key)
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                wx, wy = self.screen_to_world(*event.pos)
                if (
                    0 <= wx < OVERMAP_W
                    and 0 <= wy < OVERMAP_H
                ):
                    self.select_cell(wx, wy)

            elif event.button == 3:
                self.dragging = True
                self.last_mouse = event.pos

            elif event.button == 4:
                self.zoom_at(1.15, event.pos)

            elif event.button == 5:
                self.zoom_at(1 / 1.15, event.pos)

            return

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3:
                self.dragging = False
            return

        if event.type == pygame.MOUSEMOTION:
            if self.dragging:
                dx = event.pos[0] - self.last_mouse[0]
                dy = event.pos[1] - self.last_mouse[1]
                tile = self.tile_size()
                self.camera_x -= dx / tile
                self.camera_y -= dy / tile
                self.clamp_camera()
                self.last_mouse = event.pos

            self.hover = self.screen_to_world(*event.pos)

    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.show_help:
                self.show_help = False
            else:
                self.running = False
            return

        if key == pygame.K_h:
            self.show_help = not self.show_help
            return

        if key == pygame.K_r:
            selected = self.selected
            self.generator = OvermapGenerator(self.generator.seed)
            self.selected = selected
            self.clamp_camera()
            return

        if key == pygame.K_n:
            self.generator = OvermapGenerator()
            self.selected = None
            self.camera_x = OVERMAP_W / 2
            self.camera_y = OVERMAP_H / 2
            return

        if key == pygame.K_HOME:
            if self.selected is not None:
                self.center_on(*self.selected)
            else:
                self.camera_x = OVERMAP_W / 2
                self.camera_y = OVERMAP_H / 2
            return

        if key == pygame.K_e:
            self.overmap_z = min(
                OVERMAP_MAX_Z,
                self.overmap_z + 1,
            )
            return

        if key == pygame.K_q:
            self.overmap_z = max(
                OVERMAP_MIN_Z,
                self.overmap_z - 1,
            )
            return

        step = 7.0 / max(0.5, self.zoom)

        if key in (pygame.K_w, pygame.K_UP):
            self.camera_y -= step
        elif key in (pygame.K_s, pygame.K_DOWN):
            self.camera_y += step
        elif key in (pygame.K_a, pygame.K_LEFT):
            self.camera_x -= step
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self.camera_x += step

        self.clamp_camera()

    # --------------------------------------------------------
    # Rendering
    # --------------------------------------------------------

    def visible_bounds(self):
        tile = self.tile_size()
        sw, sh = self.screen.get_size()
        view_w = sw - self.view_left()

        left = int(
            self.camera_x
            - view_w / (2 * tile)
        ) - 2
        right = int(
            self.camera_x
            + view_w / (2 * tile)
        ) + 2
        top = int(
            self.camera_y
            - sh / (2 * tile)
        ) - 2
        bottom = int(
            self.camera_y
            + sh / (2 * tile)
        ) + 2

        return (
            max(0, left),
            min(OVERMAP_W - 1, right),
            max(0, top),
            min(OVERMAP_H - 1, bottom),
        )

    def draw(self):
        self.screen.fill(COL_BG)
        self.draw_overmap()
        self.draw_sidebar()

        if self.show_help:
            self.draw_help()

    def draw_overmap(self):
        left, right, top, bottom = self.visible_bounds()
        tile = self.tile_size()

        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                cell = self.generator.cell(x, y)
                sx, sy = self.world_to_screen(x, y)

                rect = pygame.Rect(
                    int(sx),
                    int(sy),
                    max(1, math.ceil(tile) + 1),
                    max(1, math.ceil(tile) + 1),
                )

                pygame.draw.rect(
                    self.screen,
                    OM_COLORS.get(
                        cell.terrain,
                        (100, 100, 100),
                    ),
                    rect,
                )

                if tile >= 7:
                    symbol = OM_SYMBOLS.get(
                        cell.terrain,
                        "?",
                    )
                    text = self.small_font.render(
                        symbol,
                        True,
                        COL_WHITE,
                    )
                    self.screen.blit(
                        text,
                        (
                            rect.centerx
                            - text.get_width() / 2,
                            rect.centery
                            - text.get_height() / 2,
                        ),
                    )

        # Settlement labels are intentionally drawn from the macro data,
        # not from any AreaGenerator logic.
        for settlement in self.generator.settlements:
            sx, sy = self.world_to_screen(
                settlement.x,
                settlement.y,
            )

            if not (
                -100 < sx < self.screen.get_width() + 100
                and -50 < sy < self.screen.get_height() + 50
            ):
                continue

            if settlement.kind == T_CITY:
                size = max(4, int(tile * 0.34))
                color = (245, 224, 140)
            else:
                size = max(3, int(tile * 0.24))
                color = (227, 205, 155)

            marker = pygame.Rect(
                int(sx - size / 2),
                int(sy - size / 2),
                size,
                size,
            )
            pygame.draw.rect(
                self.screen,
                color,
                marker,
            )

            if self.zoom >= 0.85:
                label = self.small_font.render(
                    settlement.name,
                    True,
                    COL_TEXT,
                )
                self.screen.blit(
                    label,
                    (
                        int(sx + tile * 0.30),
                        int(sy - label.get_height() / 2),
                    ),
                )

        # Selected OMT outline.
        if self.selected is not None:
            sx, sy = self.world_to_screen(*self.selected)
            rect = pygame.Rect(
                int(sx),
                int(sy),
                max(1, int(tile)),
                max(1, int(tile)),
            )
            pygame.draw.rect(
                self.screen,
                COL_SELECTION,
                rect,
                max(2, int(tile * 0.12)),
            )

        self.draw_legend()

        if self.hover is not None:
            x, y = self.hover
            if (
                0 <= x < OVERMAP_W
                and 0 <= y < OVERMAP_H
            ):
                self.draw_hover(x, y)

    def draw_legend(self):
        x = self.screen.get_width() - 230
        y = 14

        rows = [
            (T_FOREST, "Forest"),
            (T_FIELD, "Field"),
            (T_RIVER, "Water"),
            (T_ROAD, "Road"),
            (T_HIGHWAY, "Highway"),
            (T_CITY, "City / Area"),
            (T_VILLAGE, "Village / Area"),
            (T_FARM, "Farm / Area"),
            (T_RUIN, "Ruin / Area"),
        ]

        panel = pygame.Rect(
            x - 12,
            y - 8,
            220,
            len(rows) * 22 + 16,
        )

        surf = pygame.Surface(
            panel.size,
            pygame.SRCALPHA,
        )
        surf.fill((0, 0, 0, 155))
        self.screen.blit(
            surf,
            panel.topleft,
        )

        for terrain, name in rows:
            pygame.draw.rect(
                self.screen,
                OM_COLORS[terrain],
                (x, y + 2, 14, 14),
            )

            text = self.small_font.render(
                f"{OM_SYMBOLS[terrain]}  {name}",
                True,
                COL_TEXT,
            )
            self.screen.blit(
                text,
                (x + 22, y),
            )
            y += 22

    def find_settlement(self, x: int, y: int):
        for settlement in self.generator.settlements:
            if settlement.x == x and settlement.y == y:
                return settlement
        return None

    def draw_hover(self, x: int, y: int):
        cell = self.generator.cell(x, y)
        settlement = self.find_settlement(x, y)

        line1 = (
            f"[{terrain_name(cell.terrain)}]"
            f"  OMT {x},{y}"
        )

        line2 = ""

        if settlement is not None:
            line2 = (
                f"{settlement.name}"
                f" • {settlement.size}"
                f" • pop {settlement.population:,}"
            )
        elif cell.special_name:
            line2 = cell.special_name
        else:
            line2 = "Macro cell"

        self.draw_tooltip(
            line1,
            line2,
            pygame.mouse.get_pos(),
        )

    def draw_tooltip(self, line1, line2, pos):
        t1 = self.font.render(
            line1,
            True,
            COL_TEXT,
        )
        t2 = self.small_font.render(
            line2,
            True,
            COL_MUTED,
        )

        width = max(
            t1.get_width(),
            t2.get_width(),
        ) + 16

        height = (
            t1.get_height()
            + t2.get_height()
            + 14
        )

        x = min(
            pos[0] + 14,
            self.screen.get_width() - width - 4,
        )
        y = min(
            pos[1] + 14,
            self.screen.get_height() - height - 4,
        )

        box = pygame.Rect(
            x,
            y,
            width,
            height,
        )

        surf = pygame.Surface(
            box.size,
            pygame.SRCALPHA,
        )
        surf.fill((10, 11, 13, 225))
        self.screen.blit(
            surf,
            box.topleft,
        )

        self.screen.blit(
            t1,
            (x + 8, y + 5),
        )

        self.screen.blit(
            t2,
            (
                x + 8,
                y + 5 + t1.get_height(),
            ),
        )

    def draw_sidebar(self):
        side = pygame.Rect(
            0,
            0,
            290,
            self.screen.get_height(),
        )

        pygame.draw.rect(
            self.screen,
            COL_PANEL,
            side,
        )

        pygame.draw.line(
            self.screen,
            (55, 57, 61),
            (289, 0),
            (289, self.screen.get_height()),
            2,
        )

        title = self.big_font.render(
            "MINI CATACLYSM",
            True,
            COL_TEXT,
        )
        self.screen.blit(title, (18, 16))

        subtitle = self.small_font.render(
            "MACRO OVERMAP",
            True,
            COL_HIGHLIGHT,
        )
        self.screen.blit(subtitle, (20, 49))

        y = 84
        self.sidebar_line(
            "MODE",
            "OVERMAP",
            y,
        )
        y += 24

        self.sidebar_line(
            "Z",
            str(self.overmap_z),
            y,
        )
        y += 24

        self.sidebar_line(
            "Seed",
            str(self.generator.seed),
            y,
        )
        y += 24

        self.sidebar_line(
            "Size",
            f"{OVERMAP_W} x {OVERMAP_H}",
            y,
        )
        y += 24

        self.sidebar_line(
            "Cities",
            str(len(self.generator.cities)),
            y,
        )
        y += 24

        self.sidebar_line(
            "Villages",
            str(len(self.generator.villages)),
            y,
        )
        y += 24

        self.sidebar_line(
            "Areas",
            str(
                len(self.generator.settlements)
                + len(self.generator.specials)
            ),
            y,
        )
        y += 42

        self.sidebar_text(
            "LMB",
            "select OMT",
            y,
        )
        y += 28

        self.sidebar_text(
            "RMB",
            "pan map",
            y,
        )
        y += 28

        self.sidebar_text(
            "WASD",
            "pan",
            y,
        )
        y += 28

        self.sidebar_text(
            "Wheel",
            "zoom",
            y,
        )
        y += 28

        self.sidebar_text(
            "E / Q",
            "change Z",
            y,
        )
        y += 28

        self.sidebar_text(
            "R",
            "regenerate same seed",
            y,
        )
        y += 28

        self.sidebar_text(
            "N",
            "new seed",
            y,
        )
        y += 28

        self.sidebar_text(
            "H",
            "help",
            y,
        )

        if self.selected is not None:
            x, y0 = self.selected
            cell = self.generator.cell(x, y0)
            settlement = self.find_settlement(x, y0)

            y += 42
            pygame.draw.line(
                self.screen,
                (55, 57, 61),
                (15, y - 10),
                (275, y - 10),
                1,
            )

            self.sidebar_text(
                "SELECTED",
                f"{x},{y0}",
                y,
            )
            y += 24

            self.sidebar_line(
                "Terrain",
                terrain_name(cell.terrain),
                y,
            )
            y += 24

            if settlement is not None:
                self.sidebar_line(
                    "Area",
                    settlement.name,
                    y,
                )
                y += 24

                self.sidebar_line(
                    "Type",
                    settlement.kind,
                    y,
                )
                y += 24

                self.sidebar_line(
                    "Size",
                    settlement.size,
                    y,
                )
                y += 24

                self.sidebar_line(
                    "Population",
                    f"{settlement.population:,}",
                    y,
                )

            elif cell.special_name:
                self.sidebar_line(
                    "Area",
                    cell.special_name,
                    y,
                )

        footer_y = self.screen.get_height() - 94
        pygame.draw.line(
            self.screen,
            (55, 57, 61),
            (15, footer_y - 12),
            (275, footer_y - 12),
            1,
        )

        lines = [
            "1 OMT = 1 macro area promise",
            "Cities do NOT contain buildings here",
            "AreaGenerator owns local detail",
        ]

        for line in lines:
            text = self.small_font.render(
                line,
                True,
                COL_MUTED,
            )
            self.screen.blit(
                text,
                (18, footer_y),
            )
            footer_y += 19

    def sidebar_line(self, label, value, y):
        a = self.small_font.render(
            label,
            True,
            COL_MUTED,
        )
        b = self.small_font.render(
            value,
            True,
            COL_TEXT,
        )
        self.screen.blit(a, (18, y))
        self.screen.blit(b, (105, y))

    def sidebar_text(self, key, value, y):
        a = self.small_font.render(
            key,
            True,
            COL_HIGHLIGHT,
        )
        b = self.small_font.render(
            value,
            True,
            COL_TEXT,
        )
        self.screen.blit(a, (18, y))
        self.screen.blit(b, (85, y))

    def draw_help(self):
        sw, sh = self.screen.get_size()
        box = pygame.Rect(
            330,
            95,
            max(500, sw - 390),
            max(400, sh - 190),
        )

        surf = pygame.Surface(
            box.size,
            pygame.SRCALPHA,
        )
        surf.fill((8, 9, 11, 238))
        self.screen.blit(
            surf,
            box.topleft,
        )
        pygame.draw.rect(
            self.screen,
            (70, 74, 78),
            box,
            2,
        )

        title = self.big_font.render(
            "MACRO OVERMAP",
            True,
            COL_HIGHLIGHT,
        )
        self.screen.blit(
            title,
            (box.x + 24, box.y + 20),
        )

        lines = [
            "Cada célula do Overmap representa UMA ÁREA macro.",
            "Cidade = uma célula; ao clicar, o futuro AreaGenerator criará a cidade inteira.",
            "Vilarejo, fazenda, ruína e outros especiais seguem a mesma ideia.",
            "O Overmap não conhece casas, quartos ou prédios individuais.",
            "Estradas aqui são apenas conexões macro entre áreas.",
            "O layout detalhado de uma área será responsabilidade do area_generator.py.",
            "",
            "LMB = selecionar    RMB = arrastar    Wheel = zoom",
            "WASD/Setas = mover    R = mesma seed    N = nova seed    H = fechar",
        ]

        y = box.y + 72
        for line in lines:
            text = self.font.render(
                line,
                True,
                COL_TEXT,
            )
            self.screen.blit(
                text,
                (box.x + 24, y),
            )
            y += 34

        close = self.small_font.render(
            "ESC = close",
            True,
            COL_MUTED,
        )
        self.screen.blit(
            close,
            (box.x + 24, box.bottom - 32),
        )

    def run(self):
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)

            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()


def main():
    seed = None

    if "--self-test" in sys.argv:
        if "--seed" in sys.argv:
            try:
                seed = int(sys.argv[sys.argv.index("--seed") + 1])
            except (IndexError, ValueError):
                raise SystemExit("--seed requires an integer")

        self_test(seed)
        return

    if "--seed" in sys.argv:
        try:
            seed = int(sys.argv[sys.argv.index("--seed") + 1])
        except (IndexError, ValueError):
            raise SystemExit("--seed requires an integer")

    try:
        OvermapViewer(seed).run()
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
