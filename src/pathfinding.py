import heapq
import math
from typing import List, Optional, Tuple

from .config import TILE
from .gamemap import GameMap

NEIGHBORS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def find_path(gm: GameMap, start: Tuple[float, float], goal: Tuple[float, float],
              max_nodes: int = 9000) -> Optional[List[Tuple[float, float]]]:
    if gm.solid_at(*goal):
        goal = gm.nearest_floor(*goal)
    if gm.solid_at(*start):
        start = gm.nearest_floor(*start)
    sx, sy = int(start[0] // TILE), int(start[1] // TILE)
    gx, gy = int(goal[0] // TILE), int(goal[1] // TILE)
    if (sx, sy) == (gx, gy):
        return [goal]
    w = gm.w
    start_id, goal_id = sy * w + sx, gy * w + gx
    g = {start_id: 0.0}
    came = {}
    heap = [(0.0, start_id)]
    closed = set()
    expanded = 0
    while heap:
        _, cur = heapq.heappop(heap)
        if cur == goal_id:
            path = []
            while cur in came:
                cx, cy = cur % w, cur // w
                path.append(gm.center(cx, cy))
                cur = came[cur]
            path.reverse()
            path[-1] = goal
            return path
        if cur in closed:
            continue
        closed.add(cur)
        expanded += 1
        if expanded > max_nodes:
            return None
        cx, cy = cur % w, cur // w
        for dx, dy, cost in NEIGHBORS:
            nx, ny = cx + dx, cy + dy
            if gm.solid(nx, ny):
                continue
            if dx and dy and (gm.solid(cx + dx, cy) or gm.solid(cx, cy + dy)):
                continue
            nid = ny * w + nx
            if nid in closed:
                continue
            ng = g[cur] + cost + (0.3 if gm.near_wall[ny][nx] else 0.0)
            if ng < g.get(nid, 1e18):
                g[nid] = ng
                came[nid] = cur
                h = max(abs(gx - nx), abs(gy - ny)) + 0.4142 * min(abs(gx - nx), abs(gy - ny))
                heapq.heappush(heap, (ng + h * 1.1, nid))
    return None
