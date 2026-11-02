import math
import random
from typing import List, Tuple

from .config import TILE, map_lines, maps_meta

FLOOR, WALL, CRATE, BARRIER = 0, 1, 2, 3
INF = math.inf


class GameMap:
    def __init__(self, meta: dict, lines: List[str]):
        self.meta = meta
        self.id = meta["id"]
        self.name = meta["name"]
        self.h = len(lines)
        self.w = len(lines[0])
        self.grid = [[FLOOR] * self.w for _ in range(self.h)]
        self.spawns = {0: [], 1: []}
        self.flags = {}
        self.sites: List[Tuple[float, float]] = []
        self.zones: List[Tuple[float, float]] = []
        self.targets: List[Tuple[float, float]] = []
        self.movers: List[Tuple[float, float]] = []
        self.barriers = {}
        self.version = 0
        for y, line in enumerate(lines):
            for x, ch in enumerate(line):
                c = self.center(x, y)
                if ch == "#":
                    self.grid[y][x] = WALL
                elif ch == "c":
                    self.grid[y][x] = CRATE
                elif ch == "a":
                    self.spawns[0].append(c)
                elif ch == "b":
                    self.spawns[1].append(c)
                elif ch == "P":
                    self.flags[0] = c
                elif ch == "Q":
                    self.flags[1] = c
                elif ch in "XY":
                    self.sites.append(c)
                elif ch == "h":
                    self.zones.append(c)
                elif ch == "t":
                    self.targets.append(c)
                elif ch == "m":
                    self.movers.append(c)
        self.zones.sort()
        self.near_wall = [[any(self.solid(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                           for x in range(self.w)] for y in range(self.h)]
        self._spots = None
        self.px_w = self.w * TILE
        self.px_h = self.h * TILE

    @staticmethod
    def center(tx, ty):
        return (tx * TILE + TILE / 2, ty * TILE + TILE / 2)

    def solid(self, tx: int, ty: int) -> bool:
        if tx < 0 or ty < 0 or tx >= self.w or ty >= self.h:
            return True
        return self.grid[ty][tx] != FLOOR

    def solid_at(self, x: float, y: float) -> bool:
        return self.solid(int(x // TILE), int(y // TILE))

    def blocked(self, x: float, y: float, r: float) -> bool:
        for ty in range(int((y - r) // TILE), int((y + r) // TILE) + 1):
            for tx in range(int((x - r) // TILE), int((x + r) // TILE) + 1):
                if self.solid(tx, ty):
                    cx = min(max(x, tx * TILE), tx * TILE + TILE)
                    cy = min(max(y, ty * TILE), ty * TILE + TILE)
                    if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
                        return True
        return False

    def raycast(self, x0, y0, x1, y1):
        """Fraction (0..1) along the segment where the first solid tile is entered, or None."""
        dx, dy = x1 - x0, y1 - y0
        tx, ty = int(x0 // TILE), int(y0 // TILE)
        if self.solid(tx, ty):
            return 0.0
        if dx == 0 and dy == 0:
            return None
        sx = 1 if dx > 0 else -1
        sy = 1 if dy > 0 else -1
        tdx = abs(TILE / dx) if dx else INF
        tdy = abs(TILE / dy) if dy else INF
        nx = (((tx + (1 if dx > 0 else 0)) * TILE) - x0) / dx if dx else INF
        ny = (((ty + (1 if dy > 0 else 0)) * TILE) - y0) / dy if dy else INF
        while True:
            if nx < ny:
                t = nx
                tx += sx
                nx += tdx
            else:
                t = ny
                ty += sy
                ny += tdy
            if t > 1.0:
                return None
            if self.solid(tx, ty):
                return t

    def los(self, x0, y0, x1, y1) -> bool:
        return self.raycast(x0, y0, x1, y1) is None

    def walk_clear(self, x0, y0, x1, y1, r=10.0) -> bool:
        dx, dy = x1 - x0, y1 - y0
        d = math.hypot(dx, dy) or 1.0
        ox, oy = -dy / d * r, dx / d * r
        return (self.raycast(x0, y0, x1, y1) is None and self.raycast(x0 + ox, y0 + oy, x1 + ox, y1 + oy) is None
                and self.raycast(x0 - ox, y0 - oy, x1 - ox, y1 - oy) is None)

    def add_barrier(self, tx, ty, expires) -> bool:
        if 0 <= tx < self.w and 0 <= ty < self.h and self.grid[ty][tx] == FLOOR:
            self.grid[ty][tx] = BARRIER
            self.barriers[(tx, ty)] = expires
            self.version += 1
            return True
        return False

    def tick(self, now):
        if self.barriers:
            for key in [k for k, t in self.barriers.items() if t <= now]:
                del self.barriers[key]
                self.grid[key[1]][key[0]] = FLOOR
                self.version += 1

    def nearest_floor(self, x, y):
        tx, ty = int(x // TILE), int(y // TILE)
        for r in range(0, 12):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r and not self.solid(tx + dx, ty + dy):
                        return self.center(tx + dx, ty + dy)
        return (x, y)

    def random_floor_near(self, x, y, radius, rng: random.Random):
        for _ in range(20):
            a = rng.uniform(0, math.tau)
            d = rng.uniform(0.2, 1.0) * radius
            px, py = x + math.cos(a) * d, y + math.sin(a) * d
            if not self.blocked(px, py, 14) and self.los(x, y, px, py):
                return (px, py)
        return self.nearest_floor(x, y)

    def open_spots(self):
        if self._spots is None:
            rng = random.Random(self.id)
            spots = []
            for _ in range(500):
                tx, ty = rng.randrange(self.w), rng.randrange(self.h)
                if self.solid(tx, ty):
                    continue
                x, y = self.center(tx, ty)
                score = 0.0
                for k in range(8):
                    a = k * math.pi / 4
                    t = self.raycast(x, y, x + math.cos(a) * 800, y + math.sin(a) * 800)
                    score += 800 if t is None else t * 800
                spots.append((score, x, y))
            spots.sort(reverse=True)
            self._spots = [(x, y) for _, x, y in spots[:80]]
        return self._spots

    def sniper_spot(self, pos, rng):
        best, best_s = None, -1
        for sx, sy in self.open_spots():
            d = math.hypot(sx - pos[0], sy - pos[1])
            if 220 < d < 750 and self.los(sx, sy, pos[0], pos[1]):
                s = 1000 - abs(d - 480) + rng.random() * 120
                if s > best_s:
                    best, best_s = (sx, sy), s
        return best or pos


def ground_war_lines():
    width, height = 160, 100
    grid = [["." for _ in range(width)] for _ in range(height)]
    for x in range(width):
        grid[0][x] = grid[height - 1][x] = "#"
    for y in range(height):
        grid[y][0] = grid[y][width - 1] = "#"

    for x0 in (14, 34, 54, 94, 114, 134):
        for y0 in (14, 34, 62, 82):
            for y in range(y0, min(y0 + 6, height - 2)):
                for x in range(x0, min(x0 + 8, width - 2)):
                    if x in (x0, x0 + 7) or y in (y0, y0 + 5):
                        grid[y][x] = "#"
            if y0 + 5 < height - 1:
                grid[y0 + 5][x0 + 3] = "."
                grid[y0 + 5][x0 + 4] = "."
            if y0 > 1:
                grid[y0][x0 + 3] = "."
                grid[y0][x0 + 4] = "."
            for y in range(y0 + 2, min(y0 + 4, height - 1)):
                for x in range(x0 + 2, min(x0 + 6, width - 1)):
                    if grid[y][x] == "." and (x + y) % 5 == 0:
                        grid[y][x] = "c"

    for row in range(5):
        for col in range(10):
            grid[4 + row * 2][5 + col * 2] = "a"
            grid[4 + row * 2][135 + col * 2] = "b"

    grid[50][8] = "P"
    grid[50][151] = "Q"
    grid[50][78] = "X"
    grid[50][82] = "Y"
    for x, y in ((48, 50), (65, 35), (80, 50), (95, 65), (112, 50)):
        grid[y][x] = "h"
    return ["".join(row) for row in grid]


def load_map(map_id: str) -> GameMap:
    if map_id == "range":
        return GameMap({"id": "range", "name": "PRACTICE RANGE"}, map_lines("range.txt"))
    if map_id == "ground_war":
        meta = next(m for m in maps_meta() if m["id"] == map_id)
        return GameMap(meta, ground_war_lines())
    meta = next(m for m in maps_meta() if m["id"] == map_id)
    return GameMap(meta, map_lines(meta["file"]))
