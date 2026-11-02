"""Generates the map text files in data/maps. Maps are mirrored left/right so both teams get fair layouts.
Legend: # wall, c crate, . floor, a/b spawns, P/Q flag bases, X/Y bomb sites, h hardpoint zones, t/m practice targets."""
import json
import random
from collections import deque
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "maps"


class Grid:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.g = [["."] * w for _ in range(h)]
        for x in range(w):
            self.g[0][x] = self.g[h - 1][x] = "#"
        for y in range(h):
            self.g[y][0] = self.g[y][w - 1] = "#"

    def inside(self, x, y):
        return 1 <= x < self.w - 1 and 1 <= y < self.h - 1

    def put(self, x, y, ch, mirror=True):
        if self.inside(x, y):
            self.g[y][x] = ch
        if mirror and self.inside(self.w - 1 - x, y):
            self.g[y][self.w - 1 - x] = ch

    def rect(self, x0, y0, x1, y1, ch, mirror=True):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, ch, mirror)

    def box(self, x0, y0, x1, y1, ch="#", mirror=True):
        for x in range(x0, x1 + 1):
            self.put(x, y0, ch, mirror)
            self.put(x, y1, ch, mirror)
        for y in range(y0, y1 + 1):
            self.put(x0, y, ch, mirror)
            self.put(x1, y, ch, mirror)

    def free(self, x0, y0, x1, y1, margin=1):
        for y in range(y0 - margin, y1 + margin + 1):
            for x in range(x0 - margin, x1 + margin + 1):
                if not self.inside(x, y) or self.g[y][x] != ".":
                    return False
        return True

    def text(self):
        return "\n".join("".join(r) for r in self.g)


def markers(g):
    w, h = g.w, g.h
    cy = h // 2
    cx = w // 2
    g.rect(1, cy - 6, 9, cy + 6, ".")
    fx = 11
    g.rect(fx - 2, cy - 2, fx + 2, cy + 2, ".")
    for sy in (h // 4, h * 3 // 4):
        g.rect(cx - 2, sy - 2, cx + 2, sy + 2, ".")
    g.rect(cx - 2, cy - 2, cx + 2, cy + 2, ".")
    zx = w * 3 // 8
    g.rect(zx - 2, cy - 2, zx + 2, cy + 2, ".")
    for gx in (3, 5, 7):
        for gy in (-3, -1, 1, 3):
            g.g[cy + gy][gx] = "a"
            g.g[cy + gy][w - 1 - gx] = "b"
    g.g[cy][fx] = "P"
    g.g[cy][w - 1 - fx] = "Q"
    for sy in (h // 4, h * 3 // 4):
        g.g[sy][cx] = "X" if sy < cy else "Y"
    g.g[cy][cx] = "h"
    g.g[cy][zx] = "h"
    g.g[cy][w - 1 - zx] = "h"


def connect(g):
    w, h = g.w, g.h
    pts = [(x, y) for y in range(h) for x in range(w) if g.g[y][x] in "abPQXYh"]
    start = next(p for p in pts if g.g[p[1]][p[0]] == "a")

    def flood():
        seen = {start}
        dq = deque([start])
        while dq:
            x, y = dq.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if n not in seen and g.g[n[1]][n[0]] not in "#c":
                    seen.add(n)
                    dq.append(n)
        return seen

    for p in pts:
        seen = flood()
        if p in seen:
            continue
        x, y = p
        while (x, y) not in seen:
            if abs(x - w // 2) > 1 and (abs(x - w // 2) > abs(y - h // 2)):
                x += 1 if x < w // 2 else -1
            else:
                y += 1 if y < h // 2 else -1
            if g.g[y][x] in "#c":
                g.g[y][x] = "."
    seen = flood()
    for y in range(h):
        for x in range(w):
            if g.g[y][x] == "." and (x, y) not in seen:
                g.g[y][x] = "#"


def depot(rng):
    g = Grid(48, 32)
    for x in (14, 19):
        gaps = rng.sample(range(3, g.h - 6), 4)
        g.rect(x, 2, x, g.h - 3, "#")
        for gy in gaps:
            g.rect(x, gy, x, gy + 2, ".")
    for _ in range(16):
        x, y = rng.randint(12, 22), rng.randint(3, g.h - 5)
        if g.free(x, y, x + 1, y + 1):
            g.rect(x, y, x + 1, y + 1, "c")
    g.rect(21, 6, 22, 10, "#")
    g.rect(21, g.h - 11, 22, g.h - 7, "#")
    return g


def dustline(rng):
    g = Grid(64, 40)
    for _ in range(4):
        for _ in range(40):
            x, y = rng.randint(12, 26), rng.randint(3, g.h - 11)
            if g.free(x, y, x + 6, y + 5, 2):
                g.box(x, y, x + 6, y + 5, "#")
                for _ in range(2):
                    side = rng.choice("nsew")
                    if side in "ns":
                        gx = rng.randint(x + 1, x + 4)
                        g.rect(gx, y if side == "n" else y + 5, gx + 1, y if side == "n" else y + 5, ".")
                    else:
                        gy = rng.randint(y + 1, y + 3)
                        g.rect(x if side == "w" else x + 6, gy, x if side == "w" else x + 6, gy + 1, ".")
                break
    for _ in range(14):
        for _ in range(20):
            w, h = rng.choice(((3, 2), (2, 3), (2, 2)))
            x, y = rng.randint(11, 30), rng.randint(3, g.h - 6)
            if g.free(x, y, x + w - 1, y + h - 1):
                g.rect(x, y, x + w - 1, y + h - 1, "c")
                break
    return g


def blacksite(rng):
    g = Grid(80, 50)
    xs = [12, 24, 36]
    ys = [g.h // 3, g.h * 2 // 3]
    for x in xs:
        g.rect(x, 1, x, g.h - 2, "#")
    for y in ys:
        g.rect(1, y, g.w // 2, y, "#")
    ybounds = [0] + ys + [g.h - 1]
    for x in xs:
        for a, b in zip(ybounds, ybounds[1:]):
            d = rng.randint(a + 2, b - 4)
            g.rect(x, d, x, d + 2, ".")
            if b - a > 12:
                d2 = rng.randint(a + 2, b - 4)
                g.rect(x, d2, x, d2 + 2, ".")
    xbounds = [0] + xs + [g.w // 2]
    for y in ys:
        for a, b in zip(xbounds, xbounds[1:]):
            d = rng.randint(a + 2, max(a + 3, b - 4))
            g.rect(d, y, d + 2, y, ".")
    for a, b in zip(xbounds[:-1], xbounds[1:]):
        for c, d in zip(ybounds, ybounds[1:]):
            if b - a < 8:
                continue
            for _ in range(2):
                x, y = rng.randint(a + 2, b - 4), rng.randint(c + 2, d - 4)
                if g.free(x, y, x + 1, y + 1):
                    g.rect(x, y, x + 1, y + 1, "c")
    for y in range(5, g.h - 5, 8):
        g.rect(g.w // 2 - 1, y, g.w // 2 - 1, y + 1, "#", False)
        g.rect(g.w // 2, y, g.w // 2, y + 1, "#", False)
    return g


def iron_district(rng):
    g = Grid(100, 64)
    for x0 in range(15, g.w // 2 - 6, 16):
        for y0 in range(3, g.h - 10, 13):
            bw, bh = rng.choice((9, 11)), rng.choice((7, 8, 9))
            g.rect(x0, y0, x0 + bw, y0 + bh, "#")
            roll = rng.random()
            if roll < .35:
                g.rect(x0 + bw // 2, y0, x0 + bw // 2 + 1, y0 + bh, ".")
            elif roll < .75:
                g.rect(x0 + 1, y0 + 1, x0 + bw - 1, y0 + bh - 1, ".")
                gx = rng.randint(x0 + 1, x0 + bw - 2)
                g.rect(gx, y0 if rng.random() < .5 else y0 + bh, gx + 1, y0 if rng.random() < .5 else y0 + bh, ".")
                g.rect(x0 + bw // 2, y0 + bh // 2, x0 + bw // 2 + 1, y0 + bh // 2, "c")
    for _ in range(30):
        x, y = rng.randint(12, g.w // 2 - 2), rng.randint(2, g.h - 4)
        if g.free(x, y, x + 1, y, 1):
            g.rect(x, y, x + 1, y, "c")
    return g


def frontier(rng):
    g = Grid(130, 80)
    for x0 in (16, 42):
        for y0 in (5, 32, 58):
            g.box(x0, y0, x0 + 21, y0 + 15, "#")
            for side in rng.sample("nsew", 3):
                if side in "ns":
                    gx = rng.randint(x0 + 3, x0 + 15)
                    yy = y0 if side == "n" else y0 + 15
                    g.rect(gx, yy, gx + 3, yy, ".")
                else:
                    gy = rng.randint(y0 + 3, y0 + 9)
                    xx = x0 if side == "w" else x0 + 21
                    g.rect(xx, gy, xx, gy + 3, ".")
            g.box(x0 + 8, y0 + 5, x0 + 13, y0 + 9, "#")
            g.rect(x0 + 10, y0 + 9, x0 + 11, y0 + 9, ".")
            for _ in range(5):
                x, y = rng.randint(x0 + 2, x0 + 18), rng.randint(y0 + 2, y0 + 12)
                if g.free(x, y, x + 1, y + 1, 1):
                    g.rect(x, y, x + 1, y + 1, "c")
    for _ in range(12):
        for _ in range(15):
            ln = rng.randint(3, 5)
            x, y = rng.randint(10, 62), rng.randint(2, g.h - 4)
            if g.free(x, y, x + ln, y, 1):
                g.rect(x, y, x + ln, y, "c")
                break
    for _ in range(8):
        for _ in range(20):
            x, y = rng.randint(30, 60), rng.randint(3, g.h - 6)
            if g.free(x, y, x + 2, y + 2, 2):
                g.rect(x, y, x + 2, y + 2, "#")
                break
    return g


def practice_range():
    g = Grid(44, 26)
    for x, y in ((12, 5), (12, 20), (22, 3), (22, 22)):
        g.rect(x, y, x + 1, y + 1, "c", False)
    for x in (3,):
        for y in (11, 12, 13, 14):
            g.g[y][x] = "a"
    for y in (8, 10, 12, 14, 16, 18):
        g.g[y][41] = "b"
    for x, y in ((16, 6), (16, 13), (16, 20), (24, 8), (24, 18), (32, 6), (32, 13), (32, 20)):
        g.g[y][x] = "t"
    for x, y in ((20, 13), (28, 13), (36, 13)):
        g.g[y][x] = "m"
    return g


META = [
    ("depot_09", "DEPOT 09", "SMALL", 2, "Compact industrial warehouse. Shelf rows, tight gaps and brutal close-range fights.", depot, 9),
    ("dustline", "DUSTLINE", "SMALL-MEDIUM", 2, "Desert outpost of shipping containers, huts and open courtyards. Mixed ranges.", dustline, 21),
    ("blacksite", "BLACKSITE", "MEDIUM", 3, "Secret research facility: corridors, labs and several entrances. Watch your doors.", blacksite, 33),
    ("iron_district", "IRON DISTRICT", "LARGE", 4, "Urban industrial zone with long streets, alleys and enterable buildings. Snipers thrive.", iron_district, 47),
    ("frontier", "FRONTIER COMPLEX", "VERY LARGE", 5, "Sprawling military installation with walled compounds, flank routes and towers.", frontier, 58),
]

if __name__ == "__main__":
    meta = []
    for mid, name, size, rating, desc, fn, seed in META:
        g = fn(random.Random(seed))
        markers(g)
        connect(g)
        (OUT / f"{mid}.txt").write_text(g.text())
        meta.append(dict(id=mid, name=name, size=size, rating=rating, desc=desc, file=f"{mid}.txt"))
        print(mid, g.w, g.h)
    pr = practice_range()
    (OUT / "range.txt").write_text(pr.text())
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
