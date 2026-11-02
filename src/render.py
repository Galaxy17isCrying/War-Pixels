import math
import zlib

import pygame

from . import gfx
from .config import CANVAS_H, CANVAS_W, TEAM_COLORS, TEAM_NAMES, TILE, weapons
from .gfx import AMBER, CYAN, GRAY, GREEN, PANEL, RED, WHITE, bar, panel, text
from .progression import weapon_rarity
from .save import TRIMS
from .weapons import ttk_seconds

CX, CY = CANVAS_W // 2, CANVAS_H // 2


def _draw_star(surf, cx, cy, radius, color):
    vertices = []
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        size = radius if index % 2 == 0 else radius * 0.42
        vertices.append((int(cx + math.cos(angle) * size), int(cy + math.sin(angle) * size)))
    pygame.draw.polygon(surf, color, vertices)


class Renderer:
    def __init__(self, match, settings):
        self.m = match
        self.s = settings
        self.tiles = gfx.make_tiles()
        self.mini = None
        self.mini_size = 0
        self.cam = [match.player.x if match.player else 0.0, match.player.y if match.player else 0.0]

    # ------------------------------------------------------------- world
    def world_to_screen(self, x, y, cam):
        return int(x - cam[0] + CX), int(y - cam[1] + CY)

    def draw_world(self, surf, cam, viewer_team, t):
        m, gm = self.m, self.m.map
        surf.fill((10, 12, 10))
        x0, y0 = int((cam[0] - CX) // TILE), int((cam[1] - CY) // TILE)
        x1, y1 = x0 + CANVAS_W // TILE + 2, y0 + CANVAS_H // TILE + 2
        for ty in range(max(0, y0), min(gm.h, y1)):
            for tx in range(max(0, x0), min(gm.w, x1)):
                g = gm.grid[ty][tx]
                img = self.tiles["floor"][(tx * 7 + ty * 13) % 3] if g == 0 else \
                    self.tiles["wall"] if g == 1 else self.tiles["crate"] if g == 2 else self.tiles["barrier"]
                px, py = int(tx * TILE - cam[0] + CX), int(ty * TILE - cam[1] + CY)
                if g == 0:
                    self._draw_ground_detail(surf, px, py, tx, ty, gm.id)
                elif g == 1:
                    surf.blit(self.tiles["wall"], (px, py))
                    self._draw_wall_volume(surf, px, py, tx, ty, gm.id)
                elif g == 2:
                    self._draw_obstacle(surf, px, py, tx, ty, gm.id)
                else:
                    surf.blit(self.tiles["barrier"], (px, py))
        self._terrain_dressing(surf, cam, x0, y0, x1, y1, t)
        self._markers(surf, cam, t)
        high = self.s["fx"] == "HIGH"
        for e in m.fx:
            self._fx(surf, e, cam, high)
        for g in m.grenades:
            sx, sy = self.world_to_screen(g.x, g.y, cam)
            pygame.draw.circle(surf, (40, 44, 40), (sx, sy), 6)
            pygame.draw.circle(surf, RED if int(t * 8) % 2 else AMBER, (sx, sy), 3)
        for c in m.combatants:
            if not c.alive:
                continue
            if not m.is_visible_to(viewer_team, c):
                continue
            self._combatant(surf, c, cam, viewer_team)
        for b in m.bullets:
            sx, sy = self.world_to_screen(b.x, b.y, cam)
            ln = min(40, b.speed * 0.02)
            ex, ey = sx - b.dx * ln, sy - b.dy * ln
            pygame.draw.line(surf, (255, 230, 150), (sx, sy), (ex, ey), 2)
        # World boundaries are rendered as environmental terrain, not a UI frame.
        self._draw_environment_edge(surf, cam, t)

    def _draw_environment_edge(self, surf, cam, t):
        """Natural organic terrain perimeter with rocky cliffs, strata, and lush tree canopy borders."""
        gm = self.m.map
        left, top = int(-cam[0] + CX), int(-cam[1] + CY)
        right, bottom = int(gm.px_w - cam[0] + CX), int(gm.px_h - cam[1] + CY)

        # 1. Natural jagged rock cliff silhouettes extending inward from map perimeter
        for side, edge in (("l", left), ("r", right)):
            if -40 < edge < CANVAS_W + 40:
                for y in range(-24, CANVAS_H + 32, 24):
                    seed = zlib.crc32(f"{gm.id}:rock:{side}:{y//24}".encode())
                    depth = 14 + (seed % 16)
                    if side == "l":
                        pts = [(edge - 28, y - 4), (edge + depth, y + 2), (edge + depth + 6, y + 12),
                               (edge + depth - 2, y + 22), (edge - 24, y + 28)]
                    else:
                        pts = [(edge + 28, y - 4), (edge - depth, y + 2), (edge - depth - 6, y + 12),
                               (edge - depth + 2, y + 22), (edge + 24, y + 28)]
                    # Base rock mass & layered strata
                    pygame.draw.polygon(surf, (22, 28, 28), pts)
                    for k in range(len(pts) - 1):
                        pygame.draw.line(surf, (58, 68, 64), pts[k], pts[k + 1], 2)
                    if seed % 2 == 0:
                        hi_pt = pts[2]
                        pygame.draw.circle(surf, (108, 118, 110), hi_pt, 2)

        for side, edge in (("t", top), ("b", bottom)):
            if -40 < edge < CANVAS_H + 40:
                for x in range(-24, CANVAS_W + 32, 26):
                    seed = zlib.crc32(f"{gm.id}:rock:{side}:{x//26}".encode())
                    depth = 14 + (seed % 16)
                    if side == "t":
                        pts = [(x - 4, edge - 28), (x + 3, edge + depth), (x + 13, edge + depth + 5),
                               (x + 23, edge + depth - 2), (x + 30, edge - 24)]
                    else:
                        pts = [(x - 4, edge + 28), (x + 3, edge - depth), (x + 13, edge - depth - 5),
                               (x + 23, edge - depth + 2), (x + 30, edge + 24)]
                    pygame.draw.polygon(surf, (22, 28, 28), pts)
                    for k in range(len(pts) - 1):
                        pygame.draw.line(surf, (58, 68, 64), pts[k], pts[k + 1], 2)

        # 2. Dense natural tree canopies softening the perimeter into an organic forest / valley edge
        for side, edge in (("l", left), ("r", right)):
            if -50 < edge < CANVAS_W + 50:
                for y in range(-20, CANVAS_H + 40, 32):
                    seed = zlib.crc32(f"{gm.id}:tree:{side}:{y//32}".encode())
                    r = 16 + (seed % 9)
                    tx = edge + (r // 2 if side == "l" else -r // 2)
                    ty = y + 16
                    # Layered foliage crown
                    pygame.draw.circle(surf, (18, 36, 22), (tx, ty), r)
                    pygame.draw.circle(surf, (34, 68, 38), (tx + 1, ty - 2), r - 4)
                    pygame.draw.circle(surf, (55, 105, 52), (tx + 2, ty - 4), max(2, r - 8))
                    pygame.draw.circle(surf, (80, 142, 70), (tx + 3, ty - 6), max(1, r - 12))

        for side, edge in (("t", top), ("b", bottom)):
            if -50 < edge < CANVAS_H + 50:
                for x in range(-20, CANVAS_W + 40, 34):
                    seed = zlib.crc32(f"{gm.id}:tree:{side}:{x//34}".encode())
                    r = 16 + (seed % 9)
                    tx = x + 17
                    ty = edge + (r // 2 if side == "t" else -r // 2)
                    pygame.draw.circle(surf, (18, 36, 22), (tx, ty), r)
                    pygame.draw.circle(surf, (34, 68, 38), (tx - 1, ty + (1 if side == "t" else -2)), r - 4)
                    pygame.draw.circle(surf, (55, 105, 52), (tx - 2, ty + (2 if side == "t" else -4)), max(2, r - 8))

    def _draw_ground_detail(self, surf, px, py, tx, ty, map_id):
        """Rich thematic floor rendering: lush lawns, paved asphalt with road markings, parquet, clay, and snow."""
        seed = zlib.crc32(f"ground:{map_id}:{tx}:{ty}".encode())
        mid = map_id.lower()

        if "nuketown" in mid:
            # 1. House Interiors: Polished Hardwood Parquet
            if (8 <= tx <= 16 or 31 <= tx <= 39) and (7 <= ty <= 20):
                pygame.draw.rect(surf, (82, 54, 34), (px, py, 32, 32))
                for y_off in (0, 8, 16, 24):
                    pygame.draw.line(surf, (108, 74, 46), (px, py + y_off), (px + 32, py + y_off), 1)
                for x_off in (8, 16, 24):
                    y_start = py + ((x_off // 8) % 2) * 8
                    pygame.draw.line(surf, (58, 38, 24), (px + x_off, y_start), (px + x_off, py + 32), 1)
            # 2. Roadway / Cul-de-sac: Dark Paved Asphalt with Markings
            elif 17 <= tx <= 30 and 2 <= ty <= 25:
                pygame.draw.rect(surf, (36, 40, 42), (px, py, 32, 32))
                # Aggregate specks
                for j in range(4):
                    sx = px + ((seed >> (j * 3)) % 30) + 1
                    sy = py + ((seed >> (j * 3 + 2)) % 30) + 1
                    pygame.draw.line(surf, (56, 62, 64), (sx, sy), (sx + 1, sy), 1)
                # Double yellow road centerline down center
                if tx == 24:
                    pygame.draw.line(surf, (225, 185, 45), (px - 2, py), (px - 2, py + 32), 2)
                    pygame.draw.line(surf, (225, 185, 45), (px + 2, py), (px + 2, py + 32), 2)
                # Concrete sidewalk curbs on edges
                if tx == 17:
                    pygame.draw.rect(surf, (92, 98, 96), (px, py, 5, 32))
                    pygame.draw.line(surf, (120, 126, 124), (px + 5, py), (px + 5, py + 32), 1)
                elif tx == 30:
                    pygame.draw.rect(surf, (92, 98, 96), (px + 27, py, 5, 32))
                    pygame.draw.line(surf, (120, 126, 124), (px + 27, py), (px + 27, py + 32), 1)
            # 3. Lawns & Yards: Vibrant Suburban Green Grass
            else:
                mow_col = (48, 86, 38) if (tx // 2) % 2 == 0 else (42, 76, 34)
                pygame.draw.rect(surf, mow_col, (px, py, 32, 32))
                for j in range(3):
                    gx = px + 4 + ((seed >> (j * 3)) % 24)
                    gy = py + 5 + ((seed >> (j * 4 + 2)) % 22)
                    pygame.draw.line(surf, (72, 124, 56), (gx, gy + 3), (gx - 1, gy - 3), 1)
                if seed % 7 == 0:
                    pygame.draw.circle(surf, (86, 148, 64), (px + 14, py + 14), 2)
                if ((5 <= tx <= 6 or 41 <= tx <= 42) and (5 <= ty <= 22)):
                    pygame.draw.rect(surf, (115, 110, 102), (px + 3, py + 3, 26, 26), border_radius=2)
                    pygame.draw.rect(surf, (68, 64, 58), (px + 3, py + 3, 26, 26), 1, border_radius=2)
        elif "crash" in mid or "standoff" in mid or "dustline" in mid:
            # Weathered sun-baked desert asphalt, dust ruts & cobblestones
            pygame.draw.rect(surf, (60, 58, 50), (px, py, 32, 32))
            if seed % 3 == 0:
                pygame.draw.rect(surf, (98, 86, 68), (px + 2, py + 2, 28, 28), border_radius=2)
                pygame.draw.rect(surf, (45, 38, 30), (px + 2, py + 2, 28, 28), 1, border_radius=2)
            else:
                for j in range(3):
                    sx = px + ((seed >> (j * 3)) % 26) + 3
                    sy = py + ((seed >> (j * 4)) % 26) + 3
                    pygame.draw.circle(surf, (126, 110, 84), (sx, sy), 2)
                if seed % 5 == 0:
                    pygame.draw.line(surf, (42, 38, 32), (px + 4, py + 12), (px + 18, py + 18), 1)
        elif "firing" in mid or "range" in mid:
            # Training Grounds: Packed Clay & Wooden Duckboards
            pygame.draw.rect(surf, (92, 75, 52), (px, py, 32, 32))
            if ty in (12, 15):
                pygame.draw.rect(surf, (115, 78, 42), (px, py + 3, 32, 26))
                for px_step in (px + 4, px + 12, px + 20, px + 28):
                    pygame.draw.line(surf, (68, 45, 24), (px_step, py + 3), (px_step, py + 29), 1)
                    pygame.draw.circle(surf, (40, 28, 16), (px_step, py + 8), 1)
            else:
                for j in range(3):
                    gx = px + ((seed >> (j * 3)) % 26) + 3
                    gy = py + ((seed >> (j * 4)) % 26) + 3
                    pygame.draw.circle(surf, (132, 115, 84), (gx, gy), 1)
        elif "summit" in mid:
            # Snowbound Facility: Crusted Snow & Ice
            pygame.draw.rect(surf, (208, 220, 228), (px, py, 32, 32))
            pygame.draw.ellipse(surf, (168, 185, 198), (px + 4, py + 6, 24, 18))
            pygame.draw.line(surf, (245, 252, 255), (px + 6, py + 8), (px + 20, py + 12), 2)
        elif any(k in mid for k in ("depot", "blacksite", "launchpad", "iron")):
            # Industrial Steel Diamond-Plate & Catwalks
            pygame.draw.rect(surf, (46, 52, 54), (px, py, 32, 32))
            for step in (4, 12, 20, 28):
                pygame.draw.line(surf, (62, 70, 72), (px + step, py), (px, py + step), 1)
                pygame.draw.line(surf, (62, 70, 72), (px + step, py + 32), (px + 32, py + step), 1)
            if tx % 6 == 0 and ty % 6 == 0:
                pygame.draw.rect(surf, (24, 28, 30), (px + 6, py + 6, 20, 20))
                for gy in range(py + 8, py + 26, 4):
                    pygame.draw.line(surf, (55, 62, 64), (px + 8, gy), (px + 24, gy), 1)
        else:
            # Mediterranean Terracotta Pavers
            pygame.draw.rect(surf, (126, 95, 68), (px, py, 32, 32))
            pygame.draw.rect(surf, (78, 58, 40), (px + 1, py + 1, 30, 30), 1)

    def _draw_obstacle(self, surf, px, py, tx, ty, map_id):
        """Rich themed obstacles: school bus, truck, downed chopper, sandbag bunkers, and tactical barriers."""
        mid = map_id.lower()
        if "nuketown" in mid and 10 <= ty <= 11 and 21 <= tx <= 27:
            # Yellow School Bus
            pygame.draw.rect(surf, (225, 175, 30), (px, py, 32, 32))
            pygame.draw.line(surf, (255, 220, 70), (px, py + 2), (px + 32, py + 2), 2)
            pygame.draw.rect(surf, (24, 28, 30), (px + 3, py + 7, 26, 11), border_radius=2)
            pygame.draw.line(surf, (90, 195, 225), (px + 6, py + 9), (px + 14, py + 9), 1)
            pygame.draw.rect(surf, (42, 45, 48), (px + 2, py + 24, 28, 6), border_radius=2)
        elif "nuketown" in mid and 16 <= ty <= 17 and 20 <= tx <= 26:
            # Blue Moving Truck
            pygame.draw.rect(surf, (28, 58, 105), (px, py, 32, 32))
            pygame.draw.rect(surf, (198, 205, 210), (px + 2, py + 2, 28, 22))
            pygame.draw.line(surf, (90, 120, 165), (px + 2, py + 26), (px + 30, py + 26), 2)
        elif "crash" in mid and 13 <= ty <= 15 and 19 <= tx <= 25:
            # Downed Helicopter Wreck
            pygame.draw.rect(surf, (38, 46, 42), (px, py, 32, 32))
            pygame.draw.line(surf, (72, 85, 78), (px + 2, py + 4), (px + 30, py + 4), 2)
            pygame.draw.circle(surf, (22, 26, 24), (px + 16, py + 16), 8)
            pygame.draw.line(surf, (85, 98, 92), (px + 4, py + 16), (px + 28, py + 16), 2)
        elif any(k in mid for k in ("firing", "range", "standoff", "dustline")):
            # Stacked Burlap Sandbag Bunker
            pygame.draw.rect(surf, (138, 118, 88), (px, py, 32, 32))
            for sy_off in (3, 13, 23):
                pygame.draw.line(surf, (170, 148, 112), (px + 2, py + sy_off), (px + 30, py + sy_off), 2)
                pygame.draw.line(surf, (95, 78, 55), (px + 2, py + sy_off + 7), (px + 30, py + sy_off + 7), 1)
                pygame.draw.line(surf, (95, 78, 55), (px + 16, py + sy_off), (px + 16, py + sy_off + 7), 1)
        elif any(k in mid for k in ("depot", "blacksite", "launchpad", "iron")):
            # Military Reinforced Container
            pygame.draw.rect(surf, (54, 70, 52), (px, py, 32, 32))
            pygame.draw.rect(surf, (35, 48, 34), (px + 2, py + 2, 28, 28), 2)
            pygame.draw.line(surf, (220, 185, 45), (px + 8, py + 16), (px + 24, py + 16), 2)
        else:
            # Weathered Wooden Crate with Iron Braces
            surf.blit(self.tiles["crate"], (px, py))
            pygame.draw.rect(surf, (42, 48, 50), (px, py, 32, 32), 1)

    def _draw_wall_volume(self, surf, px, py, tx, ty, map_id):
        """Give existing collision walls architectural mass: façades, windows and ledges."""
        gm = self.m.map
        mid = map_id.lower()
        city = any(k in mid for k in ("nuketown", "crash", "standoff", "market", "iron_district", "raidhouse", "depot", "blacksite", "hijacked"))
        field = any(k in mid for k in ("frontier", "firing", "ground_war", "dustline", "summit", "launchpad"))
        # A dark cast shadow on the lower/right edges makes the existing solid tile feel raised.
        pygame.draw.polygon(surf, (12, 15, 16), [(px + 4, py + 25), (px + 32, py + 25), (px + 32, py + 32), (px + 4, py + 32)])
        if city:
            seed = zlib.crc32(f"facade:{map_id}:{tx}:{ty}".encode())
            palette = ((70, 75, 76), (86, 77, 65), (65, 78, 83), (94, 88, 75))
            base = palette[seed % len(palette)]
            pygame.draw.rect(surf, base, (px + 2, py + 1, 28, 25))
            pygame.draw.line(surf, tuple(min(255, c + 32) for c in base), (px + 2, py + 1), (px + 28, py + 1), 2)
            pygame.draw.line(surf, (32, 37, 39), (px + 2, py + 24), (px + 29, py + 24), 2)
            if seed % 5 != 0:
                glass = (45, 87, 99) if seed % 2 else (39, 48, 52)
                for wx in (px + 6, px + 19):
                    pygame.draw.rect(surf, (28, 33, 34), (wx - 1, py + 5, 7, 10))
                    pygame.draw.rect(surf, glass, (wx, py + 6, 5, 8))
                    pygame.draw.line(surf, (119, 151, 151), (wx + 1, py + 7), (wx + 3, py + 7), 1)
        elif field:
            pygame.draw.polygon(surf, (54, 60, 48), [(px + 1, py + 7), (px + 7, py + 2), (px + 30, py + 4), (px + 31, py + 25), (px + 3, py + 27)])
            pygame.draw.line(surf, (111, 117, 85), (px + 5, py + 5), (px + 26, py + 6), 2)
            pygame.draw.line(surf, (39, 44, 37), (px + 4, py + 20), (px + 28, py + 21), 2)
        else:
            pygame.draw.polygon(surf, (70, 76, 75), [(px + 2, py + 4), (px + 8, py + 1), (px + 30, py + 3), (px + 29, py + 24), (px + 3, py + 25)])
            pygame.draw.line(surf, (118, 128, 120), (px + 5, py + 5), (px + 26, py + 5), 2)
            pygame.draw.line(surf, (43, 49, 48), (px + 5, py + 19), (px + 27, py + 19), 2)

    def _terrain_dressing(self, surf, cam, x0, y0, x1, y1, t):
        """Clean, unobtrusive ground detail that adds texture without fake blocking silhouettes."""
        gm = self.m.map
        for ty in range(max(1, y0), min(gm.h - 1, y1)):
            for tx in range(max(1, x0), min(gm.w - 1, x1)):
                if gm.grid[ty][tx] != 0:
                    continue
                seed = zlib.crc32(f"{gm.id}:{tx}:{ty}".encode())
                if seed % 23 != 0:
                    continue
                sx, sy = self.world_to_screen(tx * TILE + TILE // 2, ty * TILE + TILE // 2, cam)
                map_id = gm.id.lower()
                field_theme = any(tag in map_id for tag in ("firing", "frontier", "ground_war", "dustline", "summit"))
                if field_theme:
                    pygame.draw.circle(surf, (36, 50, 32), (sx, sy), 3)
                    pygame.draw.line(surf, (55, 75, 42), (sx - 2, sy), (sx + 2, sy - 2), 1)
                else:
                    pygame.draw.rect(surf, (22, 26, 28), (sx - 3, sy - 2, 6, 4))
                    pygame.draw.line(surf, (44, 48, 50), (sx - 2, sy), (sx + 2, sy), 1)

    def _markers(self, surf, cam, t):
        for kind, x, y, r, team, label in self.m.mode.markers():
            sx, sy = self.world_to_screen(x, y, cam)
            if kind == "base":
                pygame.draw.circle(surf, gfx.darker(TEAM_COLORS[team], 0.7), (sx, sy), r, 2)
            elif kind == "flag":
                col = TEAM_COLORS[team]
                pygame.draw.line(surf, WHITE, (sx, sy + 12), (sx, sy - 18), 2)
                pygame.draw.polygon(surf, col, [(sx, sy - 18), (sx + 16, sy - 12), (sx, sy - 6)])
            elif kind == "site":
                pygame.draw.circle(surf, AMBER, (sx, sy), r, 2)
                text(surf, label, (sx, sy), 24, AMBER, "center")
            elif kind == "bomb":
                pygame.draw.rect(surf, RED if int(t * 4) % 2 else (120, 30, 30), (sx - 8, sy - 8, 16, 16))
                text(surf, label, (sx, sy - 22), 16, RED, "center")
            elif kind in ("zone", "zone_next"):
                col = AMBER if team is None else TEAM_COLORS[team]
                if kind == "zone_next":
                    col = GRAY
                pygame.draw.circle(surf, col, (sx, sy), r, 2 if kind == "zone" else 1)
                text(surf, label, (sx, sy - r - 12), 14, col, "center")

    def _fx(self, surf, e, cam, high):
        sx, sy = self.world_to_screen(e.x, e.y, cam)
        k = 1 - e.ttl / e.life
        if e.kind == "muzzle":
            pygame.draw.circle(surf, (255, 236, 160), (sx, sy), 6)
            pygame.draw.circle(surf, (255, 150, 40), (sx, sy), 3)
        elif e.kind == "spark" and high:
            for i in range(-1, 2):
                a = e.a + i * 0.7
                pygame.draw.line(surf, (255, 210, 120), (sx, sy), (sx + math.cos(a) * 10 * k + 2, sy + math.sin(a) * 10 * k), 2)
        elif e.kind == "blood" and high:
            pygame.draw.circle(surf, (170, 30, 30), (sx, sy), int(4 + 8 * k), 2)
        elif e.kind == "death":
            pygame.draw.line(surf, (200, 60, 60), (sx - 8, sy - 8), (sx + 8, sy + 8), 3)
            pygame.draw.line(surf, (200, 60, 60), (sx + 8, sy - 8), (sx - 8, sy + 8), 3)
        elif e.kind == "legendary_death":
            color = e.extra or (255, 170, 40)
            radius = int(e.a * (0.4 + 0.6 * k))
            pygame.draw.circle(surf, color, (sx, sy), radius, 3)
            pygame.draw.circle(surf, (255, 238, 170), (sx, sy), max(2, radius // 3), 1)
        elif e.kind == "dragon_death":
            radius = e.a * (0.35 + 0.65 * min(1.0, k * 3))
            age = e.life - e.ttl
            points = []
            for i in range(11):
                angle = age * 4.2 - i * 0.23
                wave = math.sin(age * 5.0 - i * 0.55) * 3
                points.append((sx + math.cos(angle) * (radius + wave),
                               sy + math.sin(angle) * (radius + wave)))
            for i in range(len(points) - 1, 0, -1):
                width = max(2, int(8 - i * 0.5))
                pygame.draw.line(surf, (190, 62, 35) if i % 2 else (245, 174, 55),
                                 points[i], points[i - 1], width)
                pygame.draw.circle(surf, (255, 208, 104), points[i],
                                   max(2, width // 2))
            head = points[0]
            head_angle = age * 4.2 + math.pi / 2
            nose = (head[0] + math.cos(head_angle) * 10, head[1] + math.sin(head_angle) * 10)
            side_a = (head[0] + math.cos(head_angle + 2.4) * 7, head[1] + math.sin(head_angle + 2.4) * 7)
            side_b = (head[0] + math.cos(head_angle - 2.4) * 7, head[1] + math.sin(head_angle - 2.4) * 7)
            pygame.draw.polygon(surf, (255, 220, 120), (nose, side_a, side_b))
            pygame.draw.circle(surf, (255, 70, 36), (int(head[0]), int(head[1])), 2)
        elif e.kind == "supernova_death":
            age = e.life - e.ttl
            converge = min(1.0, age / 0.65)
            separation = 62 * (1.0 - converge)
            star_size = 8 + int(2 * math.sin(age * 12))

            _draw_star(surf, sx - separation, sy - 8, star_size, (90, 205, 255))
            _draw_star(surf, sx + separation, sy - 8, star_size, (255, 190, 70))
            if age > 0.5:
                burst = min(1.0, (age - 0.5) / 1.9)
                radius = int(12 + 82 * burst)
                pygame.draw.circle(surf, (125, 205, 255), (sx, sy), radius, 3)
                pygame.draw.circle(surf, (255, 225, 145), (sx, sy), max(3, radius // 3), 2)
                for index in range(8):
                    angle = index * math.pi / 4 + age * 0.8
                    end = (int(sx + math.cos(angle) * radius), int(sy + math.sin(angle) * radius))
                    pygame.draw.line(surf, (200, 235, 255), (sx, sy), end, 2)
        elif e.kind == "void_rift_death":
            age = e.life - e.ttl
            radius = int(12 + 42 * min(1.0, age / 1.5))
            pygame.draw.circle(surf, (95, 35, 160), (sx, sy), radius, 3)
            pygame.draw.circle(surf, (25, 12, 45), (sx, sy), max(2, radius // 2), 0)
            for index in range(4):
                angle = age * (2.8 if index % 2 else -2.4) + index * math.pi / 2
                start = (int(sx + math.cos(angle) * (radius * 0.35)),
                         int(sy + math.sin(angle) * (radius * 0.35)))
                end = (int(sx + math.cos(angle + 1.8) * radius),
                       int(sy + math.sin(angle + 1.8) * radius))
                pygame.draw.line(surf, (190, 110, 255), start, end, 3)
            pygame.draw.circle(surf, (235, 205, 255), (sx, sy), max(2, radius // 8))
        elif e.kind == "comet_death":
            age = e.life - e.ttl
            progress = min(1.0, age / e.life)
            radius = int(7 + 34 * progress)
            angle = -math.pi / 2 + age * 4
            head = (int(sx + math.cos(angle) * radius), int(sy + math.sin(angle) * radius))
            for tail in range(1, 6):
                distance = tail * 7
                point = (int(head[0] - math.cos(angle) * distance),
                         int(head[1] - math.sin(angle) * distance))
                pygame.draw.line(surf, (100, 195, 255), point, head, max(1, 6 - tail))
            pygame.draw.circle(surf, (245, 250, 255), head, 7)
            pygame.draw.circle(surf, (255, 185, 85), head, 3)
            pygame.draw.circle(surf, (115, 195, 255), (sx, sy), int(10 + 32 * progress), 2)
        elif e.kind == "ice_shatter_death":
            age = e.life - e.ttl
            expansion = min(1.0, age / e.life)
            radius = int(10 + 58 * expansion)
            pygame.draw.circle(surf, (90, 200, 255), (sx, sy), radius, 2)
            pygame.draw.circle(surf, (190, 240, 255), (sx, sy), max(2, radius // 3), 1)
            for index in range(10):
                angle = index * math.tau / 10 + age * 0.5
                inner = radius * 0.35
                outer = radius * (0.8 + 0.2 * math.sin(age * 5 + index))
                base = (sx + math.cos(angle) * inner, sy + math.sin(angle) * inner)
                tip = (sx + math.cos(angle) * outer, sy + math.sin(angle) * outer)
                side = (sx + math.cos(angle + 0.12) * outer * 0.65,
                        sy + math.sin(angle + 0.12) * outer * 0.65)
                pygame.draw.polygon(surf, (155, 225, 255), (base, tip, side))
        elif e.kind.startswith("skin_") and e.kind.endswith("_death"):
            age = e.life - e.ttl
            progress = min(1.0, age / e.life)
            effect_id = e.kind[5:-6]
            effect_theme = effect_id.split("__", 1)[0]
            variant = zlib.crc32(effect_id.encode("utf-8"))
            phase = variant / 0xFFFFFFFF * math.tau
            radius = int(e.a * (12 + 54 * progress) / 42)
            color = e.extra or (210, 210, 255)
            if effect_theme == "astral_sovereign":
                pygame.draw.circle(surf, color, (sx, sy), radius, 2)
                for index in range(5):
                    angle = age * 0.7 + index * math.tau / 5
                    orbit = radius * (0.55 + 0.1 * math.sin(age * 3 + index))
                    _draw_star(surf, sx + math.cos(angle) * orbit, sy + math.sin(angle) * orbit,
                               max(3, int(7 * (1 - progress * 0.4))), color)
            elif effect_theme == "infernal_wyrm":
                for index in range(12):
                    angle = age * 4 - index * 0.42
                    distance = radius * (index + 1) / 12
                    point = (int(sx + math.cos(angle) * distance),
                             int(sy + math.sin(angle) * distance))
                    pygame.draw.circle(surf, (255, 90 + index * 10, 35), point,
                                       max(2, 7 - index // 2))
                pygame.draw.circle(surf, (255, 225, 115), (sx, sy), max(3, radius // 5))
            elif effect_theme == "prismatic_tempest":
                for index in range(8):
                    angle = index * math.tau / 8 + age
                    inner = radius * 0.2
                    outer = radius * (0.55 + 0.45 * ((index + int(age * 8)) % 2))
                    points = [(int(sx + math.cos(angle) * inner), int(sy + math.sin(angle) * inner)),
                              (int(sx + math.cos(angle + 0.3) * outer), int(sy + math.sin(angle + 0.3) * outer)),
                              (int(sx + math.cos(angle - 0.3) * outer), int(sy + math.sin(angle - 0.3) * outer))]
                    shard_color = ((index * 37 + 80) % 255, (index * 83 + 110) % 255, (index * 113 + 160) % 255)
                    pygame.draw.polygon(surf, shard_color, points)
            elif effect_theme == "frostbound_nova":
                pygame.draw.circle(surf, color, (sx, sy), radius, 2)
                for index in range(6):
                    angle = index * math.tau / 6
                    end = (int(sx + math.cos(angle) * radius), int(sy + math.sin(angle) * radius))
                    branch = (int(sx + math.cos(angle + 0.18) * radius * 0.65),
                              int(sy + math.sin(angle + 0.18) * radius * 0.65))
                    pygame.draw.line(surf, (190, 240, 255), (sx, sy), end, 3)
                    pygame.draw.line(surf, color, end, branch, 2)
            elif effect_theme == "void_reaver":
                pygame.draw.circle(surf, (18, 8, 38), (sx, sy), radius // 2)
                pygame.draw.circle(surf, color, (sx, sy), radius, 2)
                for index in range(4):
                    angle = age * (3 + index * 0.25) + index * math.pi / 2
                    point = (int(sx + math.cos(angle) * radius * 0.7),
                             int(sy + math.sin(angle) * radius * 0.7))
                    pygame.draw.line(surf, color, (sx, sy), point, 2)
                    pygame.draw.circle(surf, (235, 205, 255), point, 3)
            elif effect_theme == "solar_devourer":
                pygame.draw.circle(surf, (255, 115, 35), (sx, sy), radius // 2)
                pygame.draw.circle(surf, (255, 225, 115), (sx, sy), radius // 3)
                for index in range(12):
                    angle = index * math.tau / 12 + age * 0.4
                    start = (int(sx + math.cos(angle) * radius * 0.6),
                             int(sy + math.sin(angle) * radius * 0.6))
                    end = (int(sx + math.cos(angle) * radius), int(sy + math.sin(angle) * radius))
                    pygame.draw.line(surf, color, start, end, 3)
            elif effect_theme == "verdant_leviathan":
                pygame.draw.circle(surf, color, (sx, sy), radius, 2)
                for index in range(7):
                    angle = age * 1.3 + index * math.tau / 7
                    base = (int(sx + math.cos(angle) * radius * 0.35),
                            int(sy + math.sin(angle) * radius * 0.35))
                    tip = (int(sx + math.cos(angle + 0.4) * radius),
                           int(sy + math.sin(angle + 0.4) * radius))
                    side = (int(sx + math.cos(angle - 0.5) * radius * 0.75),
                            int(sy + math.sin(angle - 0.5) * radius * 0.75))
                    pygame.draw.polygon(surf, color, (base, tip, side))
            elif effect_theme == "quantum_phantom":
                for index in range(3):
                    offset = int(math.sin(age * 8 + index * math.tau / 3) * 15)
                    center = (sx + offset, sy + int(math.cos(age * 8 + index * math.tau / 3) * 10))
                    pygame.draw.circle(surf, color, center, max(4, radius - index * 12), 2)
                    pygame.draw.line(surf, color, (sx, sy), center, 1)
            elif effect_theme == "eclipse_engine":
                pygame.draw.circle(surf, color, (sx, sy), radius, 3)
                shadow_x = sx + int(radius * 0.35 * math.sin(age * 2))
                pygame.draw.circle(surf, (16, 12, 32), (shadow_x, sy), int(radius * 0.7))
                pygame.draw.circle(surf, color, (sx, sy), radius + 7, 1)
            elif effect_theme == "starlight_armada":
                pygame.draw.circle(surf, color, (sx, sy), radius, 1)
                for index in range(7):
                    angle = age * 1.8 + index * math.tau / 7
                    distance = radius * (0.35 + 0.6 * ((index % 3) / 3))
                    point = (sx + math.cos(angle) * distance, sy + math.sin(angle) * distance)
                    _draw_star(surf, point[0], point[1], max(3, 7 - index // 2),
                               (210, 235, 255) if index % 2 else color)
            signature_angle = phase + age * (1 + variant % 5)
            signature_radius = radius + 6 + variant % 9
            signature = (int(sx + math.cos(signature_angle) * signature_radius),
                         int(sy + math.sin(signature_angle) * signature_radius))
            pygame.draw.circle(surf, color, (sx, sy), signature_radius, 1)
            _draw_star(surf, signature[0], signature[1], 3 + variant % 4, color)
        elif e.kind == "slash":
            reach = e.b * (0.4 + 0.6 * k)
            ex, ey = sx + math.cos(e.a) * reach, sy + math.sin(e.a) * reach
            pygame.draw.line(surf, (220, 235, 220), (sx, sy), (ex, ey), 4)
        elif e.kind == "casing" and high:
            d = e.b * k
            pygame.draw.rect(surf, (230, 190, 80), (sx + math.cos(e.a) * d, sy + math.sin(e.a) * d, 3, 2))
        elif e.kind == "explosion":
            r = int(e.a * (0.3 + 0.7 * k))
            pygame.draw.circle(surf, (255, 150, 40), (sx, sy), r, 0 if k < 0.4 else 4)
            pygame.draw.circle(surf, (255, 230, 150), (sx, sy), int(r * 0.5), 0 if k < 0.3 else 2)
        elif e.kind == "ring":
            pygame.draw.circle(surf, e.extra, (sx, sy), int(e.a * (0.2 + 0.8 * k)), 2)

    def _combatant(self, surf, c, cam, viewer_team):
        sx, sy = self.world_to_screen(c.x, c.y, cam)
        trim = None
        if c is self.m.player:
            unlocked = [t for t in TRIMS]
            trim = unlocked[min(self.s["trim"], len(unlocked) - 1)][2]
        # Ground shadow offset makes operators read as raised sprites above the floor.
        pygame.draw.ellipse(surf, (8, 11, 14), (sx - 17, sy + 10, 35, 13))
        pygame.draw.ellipse(surf, (24, 29, 32), (sx - 12, sy + 11, 25, 7))

        # Dynamic walking combat boots with animated stride
        speed = math.hypot(c.vx, c.vy)
        sole_col = (14, 18, 18)
        boot_col = (36, 42, 40)
        if speed > 8:
            stride = math.sin(self.m.time * 16.0) * min(6.5, speed * 0.04)
            lx = int(sx - math.sin(c.aim) * 7 + math.cos(c.aim) * stride)
            ly = int(sy + math.cos(c.aim) * 7 + math.sin(c.aim) * stride)
            rx = int(sx + math.sin(c.aim) * 7 - math.cos(c.aim) * stride)
            ry = int(sy - math.cos(c.aim) * 7 - math.sin(c.aim) * stride)
            pygame.draw.ellipse(surf, sole_col, (lx - 4, ly - 3, 8, 6))
            pygame.draw.ellipse(surf, boot_col, (lx - 3, ly - 2, 6, 4))
            pygame.draw.ellipse(surf, sole_col, (rx - 4, ry - 3, 8, 6))
            pygame.draw.ellipse(surf, boot_col, (rx - 3, ry - 2, 6, 4))
        else:
            lx = int(sx - math.sin(c.aim) * 7)
            ly = int(sy + math.cos(c.aim) * 7)
            rx = int(sx + math.sin(c.aim) * 7)
            ry = int(sy - math.cos(c.aim) * 7)
            pygame.draw.ellipse(surf, sole_col, (lx - 4, ly - 3, 8, 6))
            pygame.draw.ellipse(surf, boot_col, (lx - 3, ly - 2, 6, 4))
            pygame.draw.ellipse(surf, sole_col, (rx - 4, ry - 3, 8, 6))
            pygame.draw.ellipse(surf, boot_col, (rx - 3, ry - 2, 6, 4))

        spr = gfx.char_sprite(c.char, c.team, c.aim, trim)
        if c.cloak_t > 0 and c.team == viewer_team:
            spr = spr.copy()
            spr.set_alpha(110)
        if c.invuln > 0 and int(self.m.time * 12) % 2:
            spr = spr.copy()
            spr.set_alpha(120)
        surf.blit(spr, spr.get_rect(center=(sx, sy)))

        # Dynamic tactical arms holding the weapon forward of the torso
        team_col = TEAM_COLORS[c.team]
        recoil = 2.5 if (c.trigger and c.weapon.mag > 0) else 0.0
        forward = 9.0 - recoil
        wx = sx + math.cos(c.aim) * forward
        wy = sy + math.sin(c.aim) * forward
        rg_x = int(wx + math.cos(c.aim) * 3 + math.sin(c.aim) * 4)
        rg_y = int(wy + math.sin(c.aim) * 3 - math.cos(c.aim) * 4)
        pygame.draw.line(surf, team_col, (int(sx + math.sin(c.aim) * 8), int(sy - math.cos(c.aim) * 8)), (rg_x, rg_y), 3)
        pygame.draw.circle(surf, (30, 36, 36), (rg_x, rg_y), 3)
        lg_x = int(wx + math.cos(c.aim) * 11 - math.sin(c.aim) * 3)
        lg_y = int(wy + math.sin(c.aim) * 11 + math.cos(c.aim) * 3)
        pygame.draw.line(surf, team_col, (int(sx - math.sin(c.aim) * 8), int(sy + math.cos(c.aim) * 8)), (lg_x, lg_y), 3)
        pygame.draw.circle(surf, (30, 36, 36), (lg_x, lg_y), 3)

        active_weapon = c.weapon.s
        equipped_skins = getattr(c, "equipped_skins", {})
        skin = equipped_skins.get(active_weapon["id"])
        gfx.draw_weapon(surf, (wx, wy), c.aim, skin["rarity"] if skin else weapon_rarity(active_weapon),
                        0.9, self.m.time, skin["name"] if skin else None, active_weapon["id"])

        if c.trigger and c.weapon.mag > 0 and int(self.m.time * 28) % 2 == 0:
            mx = int(wx + math.cos(c.aim) * 26)
            my = int(wy + math.sin(c.aim) * 26)
            pygame.draw.circle(surf, (255, 238, 150), (mx, my), 6)
            pygame.draw.circle(surf, (255, 140, 30), (mx, my), 3)

        if c.is_target:
            pygame.draw.circle(surf, (230, 230, 230), (sx, sy), 14, 2)
            pygame.draw.circle(surf, RED, (sx, sy), 6, 2)
        col = TEAM_COLORS[c.team]
        bar(surf, (sx - 14, sy - 24, 28, 4), c.hp / c.maxhp, (90, 210, 100) if c.team == viewer_team else RED)
        if c.team == viewer_team and c is not self.m.player:
            text(surf, c.name, (sx, sy - 34), 12, col, "center")
        if c.carry is not None:
            pygame.draw.polygon(surf, TEAM_COLORS[c.carry.team], [(sx, sy - 44), (sx + 12, sy - 39), (sx, sy - 34)])
        if c.revealed_until.get(viewer_team, 0) > self.m.time:
            pygame.draw.circle(surf, CYAN, (sx, sy), 20, 1)

    # --------------------------------------------------------------- HUD
    def draw_hud(self, surf, c, cursor, t, practice_info=None):
        m, s = self.m, self.s
        U = s["ui_scale"]
        f = lambda n: int(n * U)
        mode = m.mode
        # top bar
        hud = mode.hud()
        panel(surf, (CX - f(210), 8, f(420), f(62)))
        text(surf, str(mode.scores[0]), (CX - f(150), 14), f(34), TEAM_COLORS[0], "midtop")
        text(surf, str(mode.scores[1]), (CX + f(150), 14), f(34), TEAM_COLORS[1], "midtop")
        text(surf, hud["timer"] or mode.name[:3], (CX, 12), f(30), WHITE, "midtop")
        text(surf, hud["sub"], (CX, 10 + f(40)), f(12), GRAY, "midtop")
        text(surf, mode.name, (CX, 74 + f(2)), f(13), AMBER, "midtop")
        if hud["bar"]:
            frac, label = hud["bar"]
            bar(surf, (CX - 100, 110, 200, 14), frac, AMBER)
            text(surf, label, (CX, 108), 12, WHITE, "midtop")
        # kill feed
        y = 12
        for k in m.killfeed[-6:]:
            if m.time - k["t"] > 6:
                continue
            ac = TEAM_COLORS.get(k["a_team"], GRAY)
            line = f"{k['attacker']}  [{k['weapon']}]{' HS' if k['hs'] else ''}  {k['victim']}"
            r = text(surf, line, (CANVAS_W - 14, y), 14, ac, "topright")
            y += 20
        # announcements
        for t0, msg in m.announcements[-1:]:
            if m.time - t0 < 3.0:
                text(surf, msg, (CX, 150), f(26), AMBER, "midtop")
        if c is not None and c.alive:
            self._player_hud(surf, c, f, t)
        elif c is not None:
            text(surf, "ELIMINATED", (CX, CANVAS_H - 150), 28, RED, "midtop")
            if c.respawn_t > 0:
                text(surf, f"RESPAWN IN {c.respawn_t:.0f}", (CX, CANVAS_H - 115), 18, WHITE, "midtop")
            else:
                text(surf, "SPECTATING TEAMMATE", (CX, CANVAS_H - 115), 16, GRAY, "midtop")
        show_mini = s.get("minimap", True)
        if show_mini:
            self.draw_minimap(surf, c)
            if self.mini is not None:
                btn_r = pygame.Rect(14, 18 + self.mini.get_height(), 108, 18)
                panel(surf, btn_r)
                pygame.draw.rect(surf, (60, 70, 70), btn_r, 1)
                text(surf, "[M] HIDE RADAR", btn_r.center, 10, CYAN, "center")
                if hasattr(self, "scene") and self.scene is not None:
                    self.scene.minimap_toggle_rect = btn_r
        else:
            btn_r = pygame.Rect(14, 14, 114, 22)
            panel(surf, btn_r)
            pygame.draw.rect(surf, GREEN, btn_r, 1)
            text(surf, "[M] SHOW RADAR", btn_r.center, 11, GREEN, "center")
            if hasattr(self, "scene") and self.scene is not None:
                self.scene.minimap_toggle_rect = btn_r
        if practice_info:
            self._practice_panel(surf, practice_info)

    def _player_hud(self, surf, c, f, t):
        w = c.weapon
        panel(surf, (14, CANVAS_H - f(96), f(300), f(82)))
        text(surf, c.char["name"], (28, CANVAS_H - f(90)), f(14), AMBER)
        text(surf, f"{int(c.hp)}", (28, CANVAS_H - f(72)), f(40), WHITE)
        bar(surf, (28 + f(90), CANVAS_H - f(52), f(190), f(14)), c.hp / c.maxhp,
            (90, 210, 100) if c.hp > c.maxhp * 0.35 else RED)
        panel(surf, (CANVAS_W - f(330), CANVAS_H - f(96), f(316), f(82)))
        text(surf, w.s["name"], (CANVAS_W - f(318), CANVAS_H - f(90)), f(15), AMBER)
        ammo_col = RED if w.mag <= w.s["mag"] * 0.25 else WHITE
        text(surf, "INF" if w.unlimited else f"{w.mag}", (CANVAS_W - f(318), CANVAS_H - f(72)), f(40), ammo_col)
        text(surf, "/ INF" if w.unlimited else f"/ {w.reserve}",
             (CANVAS_W - f(318) + f(90), CANVAS_H - f(56)), f(20), GRAY)
        if w.reloading:
            bar(surf, (CANVAS_W - f(318), CANVAS_H - f(26), f(160), f(8)), w.reload_progress, AMBER)
            text(surf, "RELOADING", (CANVAS_W - f(150), CANVAS_H - f(30)), f(12), AMBER)
        text(surf, f"[{c.cur + 1}] {c.weapons[1 - c.cur].s['name']}", (CANVAS_W - f(318), CANVAS_H - f(28)) if not w.reloading else (CANVAS_W - f(150), CANVAS_H - f(48)), f(11), GRAY)
        ab = c.char["ability"]
        r = pygame.Rect(14 + f(310), CANVAS_H - f(80), f(56), f(56))
        ready = c.ability_cd <= 0
        gfx.ability_icon(surf, ab["id"], r, AMBER if ready else gfx.DIM)
        if not ready:
            text(surf, f"{c.ability_cd:.0f}", r.center, f(20), WHITE, "center")
        else:
            text(surf, "SPACE", (r.centerx, r.bottom + 2), f(11), GRAY, "midtop")

    def draw_crosshair(self, surf, c, cursor):
        if not c or not c.alive:
            return
        speed_frac = min(1.0, math.hypot(c.vx, c.vy) / 190.0)
        spread = c.weapon.spread(c.ads, speed_frac, c.mods.get("still", 1.0), c.steady_t > 0)
        dist = math.hypot(cursor[0] - CX, cursor[1] - CY)
        gap = int(4 + math.tan(math.radians(min(spread, 30))) * max(dist, 80) * 0.5)
        x, y = int(cursor[0]), int(cursor[1])
        col = (255, 90, 80) if c.weapon.reloading else (240, 240, 230)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, col, (x + dx * gap, y + dy * gap), (x + dx * (gap + 8), y + dy * (gap + 8)), 2)
        pygame.draw.rect(surf, col, (x - 1, y - 1, 2, 2))

    def _practice_panel(self, surf, info):
        panel(surf, (14, 190, 330, 150))
        lines = [f"SHOTS {info['shots']}  HITS {info['hits']}", f"ACCURACY {info['acc']:.0f}%  HEADSHOTS {info['hs']}",
                 f"DAMAGE DEALT {info['dmg']:.0f}", f"LAST HIT {info['last']}"]
        for i, ln in enumerate(lines):
            text(surf, ln, (26, 200 + i * 22), 14, WHITE)
        text(surf, "T RESET STATS", (26, 296), 12, GRAY)
        if info.get("compare"):
            self.draw_weapon_compare(surf, info["compare"])

    def draw_weapon_compare(self, surf, pair):
        panel(surf, (14, 350, 330, 190))
        a, b = pair
        text(surf, "WEAPON COMPARISON", (26, 358), 14, AMBER)
        rows = [("NAME", "name"), ("DAMAGE", "dmg"), ("RPM", "rate"), ("RANGE", "range"), ("MAG", "mag"), ("RELOAD", "reload"), ("V.RECOIL", "vrec")]
        for i, (lbl, key) in enumerate(rows):
            y = 382 + i * 22
            text(surf, lbl, (26, y), 12, GRAY)
            text(surf, str(a[key])[:12], (120, y), 12, WHITE)
            text(surf, str(b[key])[:12], (230, y), 12, CYAN)
        text(surf, f"TTK {ttk_seconds(a):.2f}s", (120, 536 - 12), 12, WHITE)
        text(surf, f"TTK {ttk_seconds(b):.2f}s", (230, 536 - 12), 12, CYAN)

    # ----------------------------------------------------------- minimap
    def _build_mini(self, size):
        gm = self.m.map
        s = pygame.Surface((gm.w, gm.h))
        for y in range(gm.h):
            for x in range(gm.w):
                g = gm.grid[y][x]
                s.set_at((x, y), (26, 30, 26) if g == 0 else (120, 124, 118) if g == 1 else (160, 118, 62))
        scale = size / max(gm.w, gm.h)
        self.mini = pygame.transform.scale(s, (int(gm.w * scale), int(gm.h * scale)))
        self.mini_scale = scale * 1.0 / TILE
        self.mini_size = size

    def draw_minimap(self, surf, c, full=None):
        size = [150, 210, 270][self.s["minimap_size"]] if full is None else full
        if self.mini is None or self.mini_size != size:
            self._build_mini(size)
        ox, oy = (14, 14) if full is None else ((CANVAS_W - self.mini.get_width()) // 2, (CANVAS_H - self.mini.get_height()) // 2)
        surf.blit(self.mini, (ox, oy))
        pygame.draw.rect(surf, GREEN, (ox - 1, oy - 1, self.mini.get_width() + 2, self.mini.get_height() + 2), 2)
        sc = self.mini_scale
        team = c.team if c else 0
        for kind, x, y, r, tm, label in self.m.mode.markers():
            col = AMBER if tm is None else TEAM_COLORS.get(tm, AMBER)
            pygame.draw.circle(surf, col, (int(ox + x * sc), int(oy + y * sc)), max(3, int(r * sc)) if kind in ("zone", "site") else 3, 1 if kind in ("zone", "site", "zone_next", "base") else 0)
        for e in self.m.combatants:
            if not e.alive or not self.m.is_visible_to(team, e):
                continue
            col = TEAM_COLORS[e.team]
            px, py = int(ox + e.x * sc), int(oy + e.y * sc)
            if e is self.m.player:
                pygame.draw.circle(surf, WHITE, (px, py), 4)
                pygame.draw.line(surf, WHITE, (px, py), (px + math.cos(e.aim) * 8, py + math.sin(e.aim) * 8), 2)
            else:
                pygame.draw.circle(surf, col, (px, py), 3)
                if e.carry is not None:
                    pygame.draw.circle(surf, WHITE, (px, py), 5, 1)

    # -------------------------------------------------------- overlays
    def draw_scoreboard(self, surf):
        m = self.m
        panel(surf, (CX - 420, 130, 840, 460), fill=(14, 18, 14), alpha=240)
        text(surf, f"{m.mode.name}  -  {m.map.name}  -  {m.diff_name}", (CX, 140), 18, AMBER, "midtop")
        for team in (0, 1):
            x = CX - 400 + team * 410
            text(surf, f"TEAM {TEAM_NAMES[team]}  {m.mode.scores[team]}", (x, 172), 18, TEAM_COLORS[team])
            text(surf, "NAME       RANK       K   D  HS  DMG  ACC", (x, 198), 11, GRAY)
            rows = sorted([c for c in m.combatants if c.team == team and not c.is_target],
                          key=lambda c: (-c.stats["kills"], -c.stats["damage"], c.stats["deaths"]))
            for i, c in enumerate(rows):
                if i >= 14:
                    if i == 14:
                        text(surf, f"+ {len(rows) - 14} MORE SQUADMATES",
                             (x, 220 + 14 * 26), 11, GRAY)
                    break
                st = c.stats
                acc = st["hits"] / st["shots"] * 100 if st["shots"] else 0
                col = WHITE if c.alive else gfx.DIM
                if c is m.player:
                    col = AMBER
                rank_name = getattr(self, "rank_lookup", {}).get(c.name, "GOLD")
                if c.name == getattr(self, "player_name", None):
                    rank_name = getattr(self, "rank_lookup", {}).get(c.name, "BRONZE")
                text(surf, f"{c.name[:10]:<10} {rank_name[:8]:<8} {st['kills']:>2} {st['deaths']:>2} {st['headshots']:>2} "
                           f"{st['damage']:>4.0f} {acc:>3.0f}%",
                     (x, 220 + i * 26), 11, col)

    def draw_tactical(self, surf, c):
        s = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        s.fill((6, 8, 6, 225))
        surf.blit(s, (0, 0))
        text(surf, "TACTICAL OVERVIEW  (release M)", (CX, 20), 20, AMBER, "midtop")
        self.draw_minimap(surf, c, full=560)
