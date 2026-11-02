import math
import random
import zlib
from functools import lru_cache

import pygame

from .config import TEAM_COLORS, TILE

BG = (16, 19, 16)
PANEL = (27, 32, 27)
PANEL2 = (36, 43, 35)
GREEN = (92, 122, 74)
AMBER = (255, 170, 40)
GRAY = (140, 148, 140)
WHITE = (232, 234, 226)
RED = (224, 72, 60)
CYAN = (80, 210, 220)
DIM = (80, 88, 80)

RANK_COLORS = {
    "Bronze": (205, 127, 50),
    "Silver": (192, 192, 210),
    "Gold": (255, 215, 0),
    "Platinum": (120, 200, 220),
    "Diamond": (185, 242, 255),
    "Master": (190, 105, 245),
    "Legendary": (255, 170, 40),
    "Mythic": (255, 50, 50),
}

_fonts = {}


def font(size: int) -> "pygame.font.Font":
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont("consolas,couriernew,dejavusansmono,menlo,monospace", size, bold=True)
    return _fonts[size]


def text(surf, s, pos, size=18, color=WHITE, anchor="topleft", shadow=True):
    f = font(size)
    img = f.render(str(s), False, color)
    r = img.get_rect()
    setattr(r, anchor, pos)
    if shadow:
        surf.blit(f.render(str(s), False, (0, 0, 0)), r.move(2, 2))
    surf.blit(img, r)
    return r


def darker(c, k=0.6):
    return tuple(int(v * k) for v in c)


def lighter(c, k=0.4):
    return tuple(int(v + (255 - v) * k) for v in c)


@lru_cache(maxsize=256)
def _panel_fill(size, fill, alpha):
    image = pygame.Surface(size, pygame.SRCALPHA)
    width, height = size
    cut = max(1, min(10, width // 4, height // 4))
    points = ((0, cut), (cut, 0), (width - cut - 1, 0), (width - 1, cut),
              (width - 1, height - cut - 1), (width - cut - 1, height - 1),
              (cut, height - 1), (0, height - cut - 1))
    pygame.draw.polygon(image, (*fill, alpha), points)
    return image


def panel(surf, rect, border=GREEN, fill=PANEL, alpha=235):
    rect = pygame.Rect(rect)
    width, height = max(1, rect.w), max(1, rect.h)
    cut = max(1, min(10, width // 4, height // 4))
    points = [(rect.x, rect.y + cut), (rect.x + cut, rect.y), (rect.right - cut - 1, rect.y),
              (rect.right - 1, rect.y + cut), (rect.right - 1, rect.bottom - cut - 1),
              (rect.right - cut - 1, rect.bottom - 1), (rect.x + cut, rect.bottom - 1),
              (rect.x, rect.bottom - cut - 1)]
    depth = max(2, min(6, height // 12))
    shadow = [(x + depth, y + depth) for x, y in points]
    pygame.draw.polygon(surf, (7, 10, 9), shadow)
    pygame.draw.polygon(surf, darker(border, 0.42), [
        points[3], points[4], points[5], shadow[5], shadow[4], shadow[3],
    ])
    pygame.draw.polygon(surf, darker(border, 0.58), [
        points[5], points[6], shadow[6], shadow[5],
    ])
    surf.blit(_panel_fill((width, height), tuple(fill), int(alpha)), rect.topleft)
    pygame.draw.lines(surf, darker(border, 0.55), True, points, 1)
    pygame.draw.line(surf, lighter(border, 0.35), (rect.x + cut, rect.y), (rect.right - cut - 1, rect.y), 2)
    pygame.draw.line(surf, lighter(border, 0.22), (rect.x + 1, rect.y + cut), (rect.x + 1, rect.bottom - cut - 1), 1)
    pygame.draw.line(surf, darker(border, 0.48), (rect.right - 2, rect.y + cut), (rect.right - 2, rect.bottom - cut - 1), 2)
    pygame.draw.line(surf, darker(border, 0.55), (rect.x + cut, rect.bottom - 1),
                     (rect.right - cut - 1, rect.bottom - 1), 2)
    pygame.draw.line(surf, lighter(fill, 0.18), (rect.left + 2, rect.y + cut + 2),
                     (rect.left + 2, rect.bottom - cut - 3), 1)
    pygame.draw.line(surf, AMBER, (rect.x + cut + 2, rect.y + 1), (rect.x + cut + 18, rect.y + 1), 2)
    inset = pygame.Rect(rect.x + 3, rect.y + 3, rect.w - 6, rect.h - 6)
    if inset.w > 2 and inset.h > 2:
        pygame.draw.rect(surf, darker(border, 0.22), inset, 1)


def draw_calling_card(surf, rect, card, title=None, subtitle=None, t=0.0):
    rect = pygame.Rect(rect)
    color = card["color"]
    accent = card["accent"]
    cut = min(12, max(5, rect.height // 5))
    shape = [(rect.x, rect.y + cut), (rect.x + cut, rect.y), (rect.right - cut - 1, rect.y),
             (rect.right - 1, rect.y + cut), (rect.right - 1, rect.bottom - cut - 1),
             (rect.right - cut - 1, rect.bottom - 1), (rect.x + cut, rect.bottom - 1),
             (rect.x, rect.bottom - cut - 1)]
    pygame.draw.polygon(surf, (10, 17, 26), shape)
    pygame.draw.polygon(surf, color, [
        (rect.x + cut + 2, rect.y + 2), (rect.right - cut - 2, rect.y + 2),
        (rect.right - 2, rect.y + cut), (rect.right - 2, rect.bottom - cut - 2),
        (rect.right - cut - 2, rect.bottom - 2), (rect.x + cut + 2, rect.bottom - 2),
        (rect.x + 2, rect.bottom - cut - 2), (rect.x + 2, rect.y + cut),
    ])
    for stripe in range(5):
        x = rect.x + rect.width * (stripe + 1) // 6
        stripe_color = tuple(int(channel * 0.48) for channel in accent)
        pygame.draw.line(surf, stripe_color, (x, rect.y + cut + 3),
                         (min(rect.right - cut - 2, x + rect.height // 2), rect.bottom - cut - 3),
                         max(1, rect.height // 50))
    pulse = 0.78 + 0.22 * math.sin(t * 3)
    glint = tuple(int(channel * pulse) for channel in accent)
    pygame.draw.lines(surf, glint, True, shape, max(1, rect.height // 45))
    title = title or card["name"]
    subtitle = subtitle or card["subtitle"]
    title_size = max(10, min(22, rect.height // 3))
    text(surf, title, (rect.x + 14, rect.y + rect.height // 5), title_size, WHITE)
    text(surf, subtitle, (rect.x + 14, rect.y + rect.height * 3 // 5),
         max(8, min(14, rect.height // 4)), accent)


def bar(surf, rect, frac, color, back=(10, 12, 10)):
    pygame.draw.rect(surf, back, rect)
    w = int(rect[2] * max(0.0, min(1.0, frac)))
    pygame.draw.rect(surf, color, (rect[0], rect[1], w, rect[3]))
    pygame.draw.rect(surf, GRAY, rect, 1)


def _px(surf16, scale=2):
    return pygame.transform.scale(surf16, (surf16.get_width() * scale, surf16.get_height() * scale))


def make_tiles():
    rng = random.Random(7)
    tiles = {}
    floors = []
    for v in range(3):
        tile = pygame.Surface((16, 16))
        tile.fill(((48 + v * 3), (54 + v * 3), (48 + v * 2)))
        for _ in range(22):
            px, py = rng.randrange(1, 15), rng.randrange(1, 15)
            shade = rng.choice(((39, 45, 39), (62, 68, 58), (54, 60, 51), (70, 72, 60)))
            tile.set_at((px, py), shade)
        pygame.draw.line(tile, (76, 82, 70), (0, 0), (15, 0))
        pygame.draw.line(tile, (70, 76, 66), (0, 0), (0, 15))
        pygame.draw.line(tile, (31, 36, 31), (0, 15), (15, 15))
        pygame.draw.line(tile, (31, 36, 31), (15, 0), (15, 15))
        floors.append(_px(tile))
    tiles["floor"] = floors

    wall = pygame.Surface((16, 16))
    wall.fill((64, 70, 69))
    pygame.draw.rect(wall, (116, 126, 120), (0, 0, 16, 12))
    pygame.draw.rect(wall, (84, 94, 90), (1, 1, 14, 10))
    for y in (4, 8):
        pygame.draw.line(wall, (57, 65, 64), (1, y), (15, y))
    pygame.draw.line(wall, (155, 164, 153), (0, 0), (15, 0), 2)
    pygame.draw.line(wall, (42, 48, 47), (0, 14), (15, 14), 2)
    pygame.draw.polygon(wall, (35, 41, 40), [(0, 12), (16, 12), (16, 16), (0, 16)])
    tiles["wall"] = _px(wall)

    crate = pygame.Surface((16, 16))
    crate.fill((40, 45, 39))
    pygame.draw.polygon(crate, (176, 128, 67), [(1, 2), (13, 0), (15, 3), (15, 13), (3, 15), (1, 12)])
    pygame.draw.polygon(crate, (113, 78, 40), [(1, 2), (4, 4), (4, 13), (3, 15), (1, 12)])
    pygame.draw.line(crate, (220, 174, 103), (3, 3), (12, 2), 1)
    pygame.draw.line(crate, (93, 62, 33), (4, 5), (13, 12), 2)
    pygame.draw.line(crate, (93, 62, 33), (12, 4), (4, 12), 2)
    tiles["crate"] = _px(crate)

    barrier = pygame.Surface((16, 16))
    barrier.fill((39, 55, 59))
    pygame.draw.rect(barrier, (50, 102, 111), (1, 1, 13, 13))
    pygame.draw.rect(barrier, (105, 207, 213), (1, 1, 13, 13), 2)
    pygame.draw.line(barrier, (147, 224, 221), (3, 4), (11, 4), 1)
    pygame.draw.line(barrier, (32, 73, 82), (3, 8), (11, 8), 2)
    pygame.draw.line(barrier, (32, 73, 82), (3, 11), (11, 11), 2)
    tiles["barrier"] = _px(barrier)
    return tiles


_sprite_cache = {}
_base_cache = {}
_profile_picture_cache = {}


def _base_sprite(char, team, trim):
    key = (char["id"], team, trim)
    if key in _base_cache:
        return _base_cache[key]
    # Detailed tactical operator: boots, limbs, tactical plate carrier, FAST helmet, headset, and visor.
    s = pygame.Surface((22, 22), pygame.SRCALPHA)
    team_col = TEAM_COLORS[team]
    armor = tuple(char["color"])
    outline = (19, 24, 23)
    # Ground shadow base
    pygame.draw.ellipse(s, (8, 10, 9, 110), (2, 4, 18, 17))
    # Legs / Combat trousers
    pygame.draw.line(s, outline, (7, 12), (5, 18), 4)
    pygame.draw.line(s, outline, (14, 12), (17, 18), 4)
    pygame.draw.line(s, (58, 64, 58), (7, 12), (5, 17), 2)
    pygame.draw.line(s, (58, 64, 58), (14, 12), (17, 17), 2)
    # Arms / Tactical sleeves
    pygame.draw.line(s, outline, (5, 8), (2, 13), 4)
    pygame.draw.line(s, outline, (15, 8), (19, 11), 4)
    pygame.draw.line(s, team_col, (5, 8), (3, 12), 2)
    pygame.draw.line(s, team_col, (15, 8), (18, 10), 2)
    # Torso and Plate Carrier
    pygame.draw.polygon(s, darker(team_col, 0.55), [(6, 5), (14, 5), (16, 12), (14, 16), (7, 16), (5, 12)])
    pygame.draw.polygon(s, team_col, [(7, 5), (14, 5), (15, 11), (13, 14), (8, 14), (6, 11)])
    pygame.draw.rect(s, armor, (8, 7, 5, 5))
    pygame.draw.line(s, lighter(team_col, 0.45), (7, 6), (13, 6), 1)
    # 3 Front MOLLE magazine pouches
    pygame.draw.rect(s, (32, 38, 34), (8, 8, 1, 3))
    pygame.draw.rect(s, (32, 38, 34), (10, 8, 1, 3))
    pygame.draw.rect(s, (32, 38, 34), (12, 8, 1, 3))
    # Ballistic Tactical Helmet
    pygame.draw.circle(s, (36, 42, 40), (11, 3), 4)
    pygame.draw.circle(s, (82, 92, 86), (11, 3), 3)
    # Side comms headset / earcups
    pygame.draw.rect(s, (24, 28, 28), (6, 2, 2, 3))
    pygame.draw.rect(s, (24, 28, 28), (14, 2, 2, 3))
    # NVG mount shroud & tactical visor
    pygame.draw.rect(s, (28, 39, 43), (9, 1, 4, 2))
    pygame.draw.line(s, (110, 220, 230), (9, 2), (13, 2), 1)
    # Tactical radio on shoulder with miniature antenna
    pygame.draw.rect(s, (22, 26, 26), (4, 4, 2, 3))
    pygame.draw.line(s, (45, 50, 52), (4, 4), (3, 1), 1)
    # Shoulder armor and identity accents
    pygame.draw.rect(s, darker(armor, 0.62), (2, 7, 4, 5))
    pygame.draw.rect(s, lighter(armor, 0.28), (3, 7, 2, 2))
    pygame.draw.rect(s, darker(armor, 0.62), (16, 7, 4, 5))
    pygame.draw.rect(s, lighter(armor, 0.28), (17, 7, 2, 2))
    pygame.draw.rect(s, (42, 46, 40), (7, 12, 3, 3))
    pygame.draw.rect(s, (42, 46, 40), (12, 12, 3, 3))
    pygame.draw.line(s, (190, 226, 223), (10, 2), (13, 3), 1)
    pygame.draw.rect(s, darker(team_col, 0.55), (15, 4, 3, 5))
    pygame.draw.line(s, lighter(team_col, 0.45), (16, 5), (17, 7), 1)
    if trim:
        pygame.draw.line(s, trim, (6, 6), (15, 6), 2)
        pygame.draw.circle(s, trim, (16, 13), 1)
    big = _px(s, 2)
    _base_cache[key] = big
    return big


def char_sprite(char, team, angle, trim=None):
    step = int(math.degrees(angle) // 10) % 36
    key = (char["id"], team, trim, step)
    if key not in _sprite_cache:
        _sprite_cache[key] = pygame.transform.rotate(_base_sprite(char, team, trim), -step * 10)
    return _sprite_cache[key]


def draw_profile_avatar(surf, center, size, picture_path, frame, t):
    x, y = int(center[0] - size / 2), int(center[1] - size / 2)
    image = None
    if picture_path:
        try:
            image = _profile_picture_cache.get(picture_path)
            if image is None:
                image = pygame.image.load(picture_path).convert_alpha()
                _profile_picture_cache[picture_path] = image
            image = pygame.transform.scale(image, (size, size))
            mask = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), (size // 2, size // 2), size // 2)
            image.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(image, (x, y))
        except (OSError, pygame.error):
            image = None
    if image is None:
        pygame.draw.circle(surf, PANEL2, (int(center[0]), int(center[1])), size // 2)
        pygame.draw.circle(surf, GRAY, (int(center[0]), int(center[1])), size // 3, max(1, size // 14))

    palette = {
        "COMMON": (170, 180, 170),
        "UNCOMMON": (100, 210, 120),
        "RARE": (90, 160, 255),
        "EPIC": (190, 105, 245),
        "LEGENDARY": (255, 170, 40),
    }
    if not isinstance(frame, dict):
        frame = {}
    rarity = frame.get("rarity", "COMMON")
    color = frame.get("color", palette.get(rarity, palette["COMMON"]))
    cx, cy = int(center[0]), int(center[1])
    radius = size // 2
    animation = frame.get("animation", "static")
    if animation == "static":
        pygame.draw.circle(surf, color, (cx, cy), radius + 3, max(2, size // 18))
        frame = pygame.Rect(cx - radius - 5, cy - radius - 5, size + 10, size + 10)
        chamfer = max(2, size // 10)
        pygame.draw.lines(surf, color, True, [
            (frame.x, frame.y + chamfer), (frame.x + chamfer, frame.y),
            (frame.right - chamfer, frame.y), (frame.right, frame.y + chamfer),
            (frame.right, frame.bottom - chamfer), (frame.right - chamfer, frame.bottom),
            (frame.x + chamfer, frame.bottom), (frame.x, frame.bottom - chamfer),
        ], 1)
    elif animation == "pulse":
        pulse = 0.65 + 0.35 * math.sin(t * 4)
        current = tuple(int(channel * pulse) for channel in color)
        pygame.draw.circle(surf, current, (cx, cy), radius + 4 + int(2 * pulse), max(2, size // 16))
    elif animation == "orbit":
        pygame.draw.circle(surf, color, (cx, cy), radius + 3, max(2, size // 18))
        for i in range(3):
            angle = t * 2.2 + i * math.tau / 3
            point = (int(cx + math.cos(angle) * (radius + 6)), int(cy + math.sin(angle) * (radius + 6)))
            pygame.draw.circle(surf, WHITE, point, max(2, size // 14))
    elif animation == "dragon":
        pygame.draw.circle(surf, color, (cx, cy), radius + 4, max(2, size // 18))
        for i in range(9):
            angle = t * 2.8 + i * math.tau / 9
            point = (int(cx + math.cos(angle) * (radius + 7)), int(cy + math.sin(angle) * (radius + 7)))
            pygame.draw.circle(surf, (255, 92, 48) if i % 2 else (255, 220, 112), point, max(2, size // 18))
    elif animation == "constellation":
        points = []
        for i in range(5):
            angle = t * 0.35 + i * math.tau / 5
            points.append((int(cx + math.cos(angle) * (radius + 7)),
                           int(cy + math.sin(angle) * (radius + 7))))
        pygame.draw.circle(surf, color, (cx, cy), radius + 3, max(2, size // 18))
        for i, point in enumerate(points):
            pygame.draw.line(surf, color, point, points[(i + 2) % len(points)], max(1, size // 48))
            pygame.draw.circle(surf, WHITE, point, max(2, size // 20))
    elif animation == "solar_flare":
        pulse = 0.8 + 0.2 * math.sin(t * 5)
        pygame.draw.circle(surf, color, (cx, cy), radius + 4, max(2, size // 18))
        for i in range(12):
            angle = t * 0.7 + i * math.tau / 12
            inner = radius + 5
            outer = radius + 10 + int(5 * pulse)
            pygame.draw.line(surf, color,
                             (int(cx + math.cos(angle) * inner), int(cy + math.sin(angle) * inner)),
                             (int(cx + math.cos(angle) * outer), int(cy + math.sin(angle) * outer)),
                             max(1, size // 28))
    elif animation == "nebula":
        for i in range(4):
            phase = t * 1.8 + i * math.tau / 4
            point = (int(cx + math.cos(phase) * (radius + 6)),
                     int(cy + math.sin(phase * 1.3) * (radius + 6)))
            pygame.draw.circle(surf, color, point, max(3, size // 12), 1)
        pygame.draw.circle(surf, color, (cx, cy), radius + 3, max(2, size // 18))
    elif animation == "prism":
        pygame.draw.circle(surf, color, (cx, cy), radius + 3, max(2, size // 18))
        for i, prism_color in enumerate(((100, 220, 255), (190, 120, 255), (255, 130, 205))):
            angle = t * 0.8 + i * math.tau / 3
            point = (int(cx + math.cos(angle) * (radius + 7)),
                     int(cy + math.sin(angle) * (radius + 7)))
            pygame.draw.polygon(surf, prism_color, [
                (point[0], point[1] - max(3, size // 18)),
                (point[0] + max(3, size // 18), point[1]),
                (point[0], point[1] + max(3, size // 18)),
                (point[0] - max(3, size // 18), point[1]),
            ])
    elif animation == "comet":
        pygame.draw.circle(surf, color, (cx, cy), radius + 3, max(2, size // 18))
        angle = t * 2.5
        head = (int(cx + math.cos(angle) * (radius + 7)), int(cy + math.sin(angle) * (radius + 7)))
        for i in range(1, 5):
            tail = (int(cx + math.cos(angle - i * 0.11) * (radius + 7 - i * 4)),
                    int(cy + math.sin(angle - i * 0.11) * (radius + 7 - i * 4)))
            pygame.draw.line(surf, color, tail, head, max(1, size // 22 - i // 2))
        pygame.draw.circle(surf, WHITE, head, max(2, size // 14))
    elif animation == "eclipse":
        pulse = 0.5 + 0.5 * math.sin(t * 2.5)
        pygame.draw.circle(surf, color, (cx, cy), radius + 5, max(2, size // 18))
        pygame.draw.circle(surf, (25, 20, 48), (cx, cy), radius + 1, max(2, size // 18))
        pygame.draw.circle(surf, color, (cx, cy), radius + 5 + int(4 * pulse), 1)
        angle = t * 1.5
        point = (int(cx + math.cos(angle) * (radius + 6)), int(cy + math.sin(angle) * (radius + 6)))
        pygame.draw.circle(surf, WHITE, point, max(2, size // 18))
    elif animation == "aurora":
        pygame.draw.circle(surf, color, (cx, cy), radius + 3, max(2, size // 18))
        for band in range(3):
            points = []
            for i in range(17):
                angle = i * math.tau / 16
                wave = math.sin(angle * 3 + t * 2 + band) * (size * 0.025)
                r = radius + 5 + band * 3 + wave
                points.append((int(cx + math.cos(angle) * r), int(cy + math.sin(angle) * r)))
            for start, end in zip(points, points[1:]):
                pygame.draw.line(surf, color, start, end, max(1, size // 30))
    else:
        pygame.draw.circle(surf, color, (cx, cy), radius + 5 + int(2 * math.sin(t * 5)), max(2, size // 18))
        pygame.draw.circle(surf, WHITE, (cx, cy), radius + 10, 1)


def draw_weapon(surf, center, angle, rarity, scale=1.0, t=0.0, skin_name=None, weapon_id=None):
    palette = {
        "COMMON": ((82, 88, 84), (160, 166, 158)),
        "UNCOMMON": ((52, 112, 70), (132, 222, 142)),
        "RARE": ((46, 88, 150), (126, 190, 255)),
        "EPIC": ((102, 48, 138), (220, 145, 255)),
        "LEGENDARY": ((150, 82, 22), (255, 220, 105)),
    }
    identity = skin_name or weapon_id or rarity
    pattern = zlib.crc32(identity.encode("utf-8"))
    if rarity == "LEGENDARY":
        legendary_finishes = (
            ((30, 79, 112), (85, 220, 255)),
            ((94, 38, 122), (225, 125, 255)),
            ((125, 42, 45), (255, 112, 112)),
            ((30, 107, 82), (111, 255, 193)),
            ((110, 77, 34), (255, 213, 101)),
            ((42, 53, 112), (150, 177, 255)),
            ((100, 45, 77), (255, 145, 204)),
            ((55, 85, 92), (180, 255, 236)),
        )
        body, trim = legendary_finishes[pattern % len(legendary_finishes)]
    else:
        body, trim = palette.get(rarity, palette["COMMON"])
    skin_accents = ((255, 105, 70), (100, 220, 210), (235, 100, 190), (170, 220, 105),
                    (145, 130, 255), (255, 210, 95), (90, 180, 240), (240, 145, 65),
                    (190, 235, 225), (220, 120, 115))
    accent = None
    if skin_name:
        accent = skin_accents[pattern % len(skin_accents)]

    holger = weapon_id == "holger_galactic_stars"
    if holger:
        scale *= 1.3

    def point(x, y):
        return (int(center[0] + (x * math.cos(angle) - y * math.sin(angle)) * scale),
                int(center[1] + (x * math.sin(angle) + y * math.cos(angle)) * scale))

    shell = [point(-8, -2), point(12, -2), point(14, -1), point(14, 1),
             point(12, 2), point(-8, 2)]
    # Clean, authentic top-down tactical firearm profile
    # Shadow extrusion removed — flat top-down 2D profile (no pseudo-3D depth polygon)
    pygame.draw.polygon(surf, body, shell)
    pygame.draw.line(surf, lighter(body, 0.35), point(-7, -1), point(11, -1), max(1, int(scale)))
    pygame.draw.line(surf, (20, 24, 25), point(12, 0), point(20, 0), max(2, int(scale * 2)))
    pygame.draw.circle(surf, (75, 85, 88), point(16, 0), max(1, int(1.2 * scale)))
    if holger:
        pygame.draw.polygon(surf, (23, 50, 74), [point(-2, -3), point(3, -3), point(3, 3), point(-2, 3)])
        pygame.draw.line(surf, (92, 193, 230), point(-1, 0), point(2, 0), max(1, int(scale)))
        pygame.draw.line(surf, (136, 220, 255), point(-8, -2), point(10, -2), max(1, int(scale)))
    pygame.draw.line(surf, trim, point(-7, 0), point(12, 0), max(1, int(scale)))
    pygame.draw.line(surf, (30, 34, 32), point(-6, 2), point(-2, 4), max(1, int(scale)))

    wid = (weapon_id or "").lower()
    is_sniper = any(k in wid for k in ("longbow", "viper", "sentinel", "arbiter", "lancer", "falcon", "sniper", "dmr"))
    is_sg = any(k in wid for k in ("shotgun", "echo", "breach", "krm", "by15", "pump"))
    is_smg = any(k in wid for k in ("spitfire", "wasp", "rattler", "smg", "pdw", "fennec", "qq9", "msmc"))
    is_lmg = any(k in wid for k in ("anvil", "bulwark", "hailstorm", "lmg", "chopper", "rpd", "holger"))
    is_pistol = any(k in wid for k in ("p9", "mw11", "deagle", "j358", "pistol", "revolver"))
    is_melee = any(k in wid for k in ("knife", "blade", "melee", "axe"))

    if is_sniper:
        pygame.draw.line(surf, (16, 20, 22), point(21, 0), point(28, 0), max(2, int(scale * 2)))
        pygame.draw.line(surf, (68, 76, 78), point(21, -1), point(27, -1), max(1, int(scale)))
        pygame.draw.line(surf, (36, 42, 44), point(27, -2), point(27, 2), max(2, int(scale * 3)))
        pygame.draw.line(surf, (26, 32, 34), point(-4, -5), point(7, -5), max(2, int(scale * 2.5)))
        pygame.draw.circle(surf, (48, 56, 60), point(-4, -5), max(2, int(scale * 2)))
        pygame.draw.circle(surf, (48, 56, 60), point(7, -5), max(2, int(scale * 2)))
        pygame.draw.circle(surf, (95, 210, 245), point(7, -5), max(1, int(scale * 1.2)))
        pygame.draw.line(surf, (32, 36, 38), point(-12, 0), point(-16, 0), max(2, int(scale * 2)))
        pygame.draw.line(surf, (48, 54, 56), point(-16, -2), point(-16, 2), max(2, int(scale * 2.5)))
    elif is_sg:
        pygame.draw.line(surf, (20, 24, 25), point(13, -1), point(23, -1), max(2, int(scale * 2)))
        pygame.draw.line(surf, (20, 24, 25), point(13, 1), point(23, 1), max(2, int(scale * 2)))
        pygame.draw.line(surf, (55, 42, 32), point(5, 3), point(14, 3), max(2, int(scale * 2.5)))
        for px_step in (6, 9, 12):
            pygame.draw.line(surf, (25, 20, 15), point(px_step, 2), point(px_step, 4), max(1, int(scale)))
    elif is_smg:
        pygame.draw.line(surf, (28, 32, 34), point(1, 3), point(3, 8), max(2, int(scale * 2.5)))
        pygame.draw.circle(surf, (48, 54, 56), point(18, 0), max(2, int(scale * 1.8)))
        pygame.draw.line(surf, (35, 40, 42), point(-12, -1), point(-16, -1), max(1, int(scale * 1.5)))
        pygame.draw.line(surf, (35, 40, 42), point(-16, -3), point(-16, 1), max(1, int(scale * 1.8)))
    elif is_lmg:
        pygame.draw.ellipse(surf, (30, 35, 38), (point(-1, 2)[0] - int(4 * scale), point(-1, 2)[1] - int(2 * scale), max(6, int(8 * scale)), max(4, int(6 * scale))))
        pygame.draw.line(surf, (220, 180, 50), point(0, 3), point(4, 3), max(1, int(scale)))
        pygame.draw.line(surf, (45, 52, 54), point(14, 2), point(18, 4), max(1, int(scale)))
        pygame.draw.line(surf, (45, 52, 54), point(14, -2), point(18, -4), max(1, int(scale)))
    elif is_pistol:
        pygame.draw.line(surf, lighter(body, 0.35), point(-6, -1), point(9, -1), max(1, int(scale)))
        pygame.draw.line(surf, (22, 26, 28), point(-4, 2), point(-1, 6), max(2, int(scale * 2)))
    elif is_melee:
        pygame.draw.line(surf, (225, 235, 245), point(0, -1), point(16, -1), max(1, int(scale * 2)))
        pygame.draw.line(surf, (120, 130, 135), point(0, 1), point(14, 1), max(1, int(scale)))
    else:
        pygame.draw.line(surf, (26, 30, 32), point(0, 3), point(4, 7), max(2, int(scale * 2.5)))
        pygame.draw.line(surf, (32, 38, 40), point(0, -4), point(4, -4), max(2, int(scale * 2)))
        pygame.draw.circle(surf, (255, 60, 40), point(2, -4), max(1, int(scale * 0.8)))

    if rarity in ("RARE", "EPIC", "LEGENDARY"):
        pygame.draw.line(surf, trim, point(-3, -3), point(5, -3), max(1, int(scale)))
        pygame.draw.circle(surf, trim, point(1, -5), max(1, int(1.5 * scale)), 1)
    if rarity in ("EPIC", "LEGENDARY"):
        pygame.draw.polygon(surf, trim, [point(-8, -2), point(-4, -5), point(0, -2)])
        pygame.draw.line(surf, trim, point(4, 3), point(8, 3), max(1, int(scale)))
    if rarity == "LEGENDARY":
        pulse = 0.75 + 0.25 * math.sin(t * 7)
        glow = tuple(int(channel * pulse) for channel in trim)
        pygame.draw.line(surf, glow, point(-11, -4), point(8, -4), max(1, int(scale)))
        pygame.draw.circle(surf, (255, 244, 180), point(7, 0), max(1, int(2 * scale)))
        for index in range(3):
            x = -7 + index * 7
            pygame.draw.line(surf, trim, point(x, -2), point(x + 2, 2), max(1, int(scale)))
        pygame.draw.circle(surf, trim, point(-8, 0), max(1, int(2 * scale)), 1)
        motif = pattern % 5
        plate = (max(0, body[0] - 28), max(0, body[1] - 18), min(255, body[2] + 38))
        pygame.draw.polygon(surf, plate, [point(-5, -2), point(3, -2), point(5, 2), point(-3, 2)])
        pygame.draw.line(surf, trim, point(-4, 0), point(3, 0), max(1, int(scale)))
        if motif == 0:
            pygame.draw.polygon(surf, trim, [point(-8, -2), point(-12, -7), point(-3, -4)])
            pygame.draw.polygon(surf, trim, [point(2, -2), point(7, -6), point(6, -2)])
            pygame.draw.circle(surf, (255, 245, 195), point(0, 0), max(1, int(scale)))
        elif motif == 1:
            for x in (-9, -2, 5, 11):
                pygame.draw.line(surf, trim, point(x, -2), point(x - 2, -5), max(1, int(scale)))
                pygame.draw.line(surf, trim, point(x - 2, -5), point(x + 1, -4), max(1, int(scale)))
        elif motif == 2:
            for x in (-8, 0, 8):
                pygame.draw.line(surf, trim, point(x, -3), point(x + 2, -1), max(1, int(scale)))
                pygame.draw.line(surf, trim, point(x + 2, -1), point(x, 1), max(1, int(scale)))
                pygame.draw.circle(surf, (225, 250, 255), point(x, -3), max(1, int(scale)))
        elif motif == 3:
            for x in (-6, 2, 10):
                orbit = t * (2.5 + x * 0.05) + x
                pygame.draw.ellipse(surf, trim,
                                    (point(x, -2)[0] - max(2, int(3 * scale)),
                                     point(x, -2)[1] - max(1, int(scale)),
                                     max(4, int(6 * scale)), max(2, int(2 * scale))), 1)
                pygame.draw.circle(surf, (205, 235, 255),
                                   point(x + math.cos(orbit) * 2, -2 + math.sin(orbit)),
                                   max(1, int(scale)))
        else:
            for x in (-8, -1, 6, 12):
                pygame.draw.polygon(surf, trim,
                                    [point(x - 1, -2), point(x, -6), point(x + 2, -2)])
            pygame.draw.line(surf, (255, 242, 195), point(-6, 1), point(10, 1), max(1, int(scale)))
    if accent is not None:
        for stripe in range(1 + pattern % 3):
            x = -8 + stripe * 6
            pygame.draw.line(surf, accent, point(x, -1), point(x + 2, 1), max(1, int(scale)))
        pygame.draw.circle(surf, accent, point(-6 + pattern % 10, 0), max(1, int(scale)))
    if holger:
        orbit_colors = ((100, 220, 255), (255, 180, 80), (205, 150, 255))
        for index, x in enumerate((-7, 2, 10)):
            orbit = t * (1.7 + index * 0.35) + index * math.tau / 3
            orbit_rx, orbit_ry = (3.4 + index * 0.5) * scale, (3.0 + index * 0.45) * scale
            orbit_points = []
            for step in range(17):
                phase = step * math.tau / 16
                orbit_points.append(point(x + math.cos(phase) * (orbit_rx / scale),
                                          math.sin(phase) * (orbit_ry / scale)))
            for start, end in zip(orbit_points, orbit_points[1:]):
                pygame.draw.line(surf, (55, 135, 175), start, end, 1)
            planet = point(x + math.cos(orbit) * (orbit_rx / scale),
                           math.sin(orbit) * (orbit_ry / scale))
            pygame.draw.circle(surf, orbit_colors[index], planet, max(1, int(1.8 * scale)))
            pygame.draw.circle(surf, (235, 250, 255), point(x, 0), max(1, int(scale)))


def ability_icon(surf, ab_id, rect, color=AMBER):
    x, y, w, h = rect
    cx, cy = x + w // 2, y + h // 2
    pygame.draw.rect(surf, (14, 16, 14), rect)
    pygame.draw.rect(surf, color, rect, 2)
    if ab_id == "sprint":
        for i in range(3):
            pygame.draw.polygon(surf, color, [(x + 6 + i * 8, y + 8), (x + 14 + i * 8, cy), (x + 6 + i * 8, y + h - 8)])
    elif ab_id == "reveal":
        for r in (6, 12, 18):
            pygame.draw.circle(surf, color, (cx, cy), r, 1)
    elif ab_id == "heal":
        pygame.draw.rect(surf, color, (cx - 3, y + 7, 6, h - 14))
        pygame.draw.rect(surf, color, (x + 7, cy - 3, w - 14, 6))
    elif ab_id == "barrier":
        pygame.draw.rect(surf, color, (x + 7, cy - 4, w - 14, 8), 2)
    elif ab_id == "grenade":
        pygame.draw.circle(surf, color, (cx, cy + 2), 9)
        pygame.draw.rect(surf, color, (cx - 2, y + 5, 4, 6))
    elif ab_id == "ammo":
        for i in range(3):
            pygame.draw.rect(surf, color, (x + 8 + i * 8, y + 8, 5, h - 16))
    elif ab_id == "steady":
        pygame.draw.circle(surf, color, (cx, cy), 10, 2)
        pygame.draw.line(surf, color, (cx - 14, cy), (cx + 14, cy), 1)
        pygame.draw.line(surf, color, (cx, cy - 14), (cx, cy + 14), 1)
    elif ab_id == "cloak":
        pygame.draw.circle(surf, color, (cx, cy), 10, 1)
        for i in range(-8, 9, 4):
            pygame.draw.line(surf, color, (cx + i, cy - 8), (cx + i, cy + 8), 1)


def streak_icon(surf, sid, rect, color=AMBER, ready=True):
    x, y, w, h = rect
    cx, cy = x + w // 2, y + h // 2
    sid = (sid or "").lower()
    if sid in ("uav", "advanced_uav"):
        # Delta-wing recon stealth drone & radar sweep rings
        pygame.draw.polygon(surf, color, [(cx, cy - 9), (cx + 11, cy + 7), (cx, cy + 3), (cx - 11, cy + 7)])
        pygame.draw.circle(surf, lighter(color, 0.4), (cx, cy - 2), 2)
        pygame.draw.arc(surf, color, (cx - 13, cy - 13, 26, 26), 0.2, 1.3, 1)
        pygame.draw.arc(surf, color, (cx - 17, cy - 17, 34, 34), 0.2, 1.3, 1)
    elif sid in ("hunter_killer", "bomb_drone", "swarm"):
        # Swept attack drone with jet flare
        pygame.draw.polygon(surf, color, [(cx, cy - 10), (cx + 9, cy + 5), (cx + 4, cy + 8), (cx, cy + 4), (cx - 4, cy + 8), (cx - 9, cy + 5)])
        pygame.draw.circle(surf, RED if ready else color, (cx, cy + 7), 2)
        pygame.draw.line(surf, color, (cx - 7, cy), (cx + 7, cy), 1)
    elif sid in ("shield_turret", "sentry_gun", "sam_turret"):
        # Heavy autocannon with ballistic face shield & tripod
        pygame.draw.line(surf, color, (cx - 4, cy - 7), (cx + 9, cy - 7), 3)
        pygame.draw.polygon(surf, color, [(cx - 2, cy - 11), (cx + 2, cy - 11), (cx + 2, cy + 2), (cx - 2, cy + 2)])
        pygame.draw.line(surf, color, (cx, cy), (cx - 6, cy + 8), 2)
        pygame.draw.line(surf, color, (cx, cy), (cx + 6, cy + 8), 2)
    elif sid == "care_package":
        # Military supply container with parachute straps
        pygame.draw.rect(surf, color, (cx - 8, cy - 4, 16, 13), 2)
        pygame.draw.line(surf, color, (cx - 8, cy - 4), (cx + 8, cy + 9), 1)
        pygame.draw.line(surf, color, (cx + 8, cy - 4), (cx - 8, cy + 9), 1)
        pygame.draw.line(surf, color, (cx - 8, cy - 4), (cx, cy - 11), 1)
        pygame.draw.line(surf, color, (cx + 8, cy - 4), (cx, cy - 11), 1)
    elif sid in ("predator_missile", "lightning_strike"):
        # Cruise missile & targeting crosshair
        pygame.draw.polygon(surf, color, [(cx, cy - 11), (cx + 4, cy - 3), (cx + 4, cy + 6), (cx, cy + 8), (cx - 4, cy + 6), (cx - 4, cy - 3)])
        pygame.draw.line(surf, color, (cx - 7, cy + 5), (cx + 7, cy + 5), 2)
        pygame.draw.circle(surf, color, (cx, cy), 9, 1)
    elif sid in ("vtol", "chopper_gunner", "stealth_chopper", "gunship", "strafe_run"):
        # Heavy assault gunship with twin rotors & fuselage
        pygame.draw.line(surf, color, (cx - 12, cy - 7), (cx + 12, cy - 7), 2)
        pygame.draw.ellipse(surf, color, (cx - 7, cy - 6, 14, 11))
        pygame.draw.polygon(surf, color, [(cx, cy), (cx + 11, cy + 5), (cx + 9, cy + 7), (cx, cy + 3)])
        pygame.draw.line(surf, color, (cx - 4, cy + 5), (cx - 4, cy + 9), 2)
        pygame.draw.line(surf, color, (cx + 4, cy + 5), (cx + 4, cy + 9), 2)
    elif sid == "counter_uav":
        # Radar jamming satellite dish with interference lines
        pygame.draw.arc(surf, color, (cx - 9, cy - 8, 18, 16), 0.5, 2.6, 2)
        pygame.draw.line(surf, color, (cx, cy), (cx, cy + 7), 2)
        pygame.draw.line(surf, RED, (cx - 6, cy - 6), (cx + 6, cy + 6), 2)
    elif sid in ("shock_rc", "wheelson", "rc_xd"):
        # Remote combat rover with all-terrain wheels
        pygame.draw.rect(surf, color, (cx - 6, cy - 4, 12, 9), 2)
        pygame.draw.circle(surf, color, (cx - 5, cy - 4), 2)
        pygame.draw.circle(surf, color, (cx + 5, cy - 4), 2)
        pygame.draw.circle(surf, color, (cx - 5, cy + 4), 2)
        pygame.draw.circle(surf, color, (cx + 5, cy + 4), 2)
        pygame.draw.line(surf, color, (cx, cy - 4), (cx + 2, cy - 9), 2)
    elif sid == "emp_systems":
        # EMP sphere with crackling energy
        pygame.draw.circle(surf, color, (cx, cy), 8, 2)
        pygame.draw.lines(surf, color, False, [(cx - 6, cy - 8), (cx - 2, cy - 2), (cx - 4, cy), (cx, cy + 7)], 2)
        pygame.draw.lines(surf, color, False, [(cx + 6, cy - 8), (cx + 2, cy - 2), (cx + 4, cy), (cx, cy + 7)], 2)
    else:
        # Tactical shield chevron
        pygame.draw.polygon(surf, color, [(cx, cy - 9), (cx + 8, cy - 5), (cx + 6, cy + 6), (cx, cy + 10), (cx - 6, cy + 6), (cx - 8, cy - 5)], 2)
        pygame.draw.circle(surf, color, (cx, cy), 3)


def draw_bg(surf, t):
    surf.fill(BG)
    for x in range(0, 1280, 40):
        pygame.draw.line(surf, (22, 27, 22), (x, 0), (x, 720))
    for y in range(0, 720, 40):
        pygame.draw.line(surf, (22, 27, 22), (0, y), (1280, y))
    rng = random.Random(11)
    for i in range(26):
        x = (rng.randrange(1280) + t * rng.randrange(6, 30)) % 1280
        y = rng.randrange(720)
        c = AMBER if i % 5 == 0 else GREEN
        pygame.draw.rect(surf, c, (int(x), y, 4, 4))
    for y in range(0, 720, 4):
        pygame.draw.line(surf, (12, 14, 12), (0, y), (1280, y))


def _rank_base(tier_name):
    """Extract the base rank name (e.g. 'Mythic' from 'Mythic III')."""
    for base in ("Mythic", "Legendary", "Master", "Diamond", "Platinum", "Gold", "Silver", "Bronze"):
        if tier_name.startswith(base):
            return base
    return "Bronze"


def draw_rank_emblem(surf, center, size, tier_name, t=0.0):
    """Draw an animated rank emblem. Higher tiers get more elaborate effects."""
    base = _rank_base(tier_name)
    color = RANK_COLORS.get(base, RANK_COLORS["Bronze"])
    cx, cy = int(center[0]), int(center[1])
    r = max(4, size // 2)
    sub = tier_name.split()[-1] if len(tier_name.split()) > 1 else ""
    tier_num = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}.get(sub, 0)

    if base == "Bronze":
        # Simple shield shape
        pts = [(cx, cy - r), (cx + r, cy - r // 3), (cx + r, cy + r // 3),
               (cx, cy + r), (cx - r, cy + r // 3), (cx - r, cy - r // 3)]
        pygame.draw.polygon(surf, darker(color, 0.5), pts)
        pygame.draw.polygon(surf, color, pts, max(1, size // 12))
        # Tier pips
        for i in range(tier_num):
            pygame.draw.circle(surf, color, (cx - (tier_num - 1) * 4 + i * 8, cy + r // 4), max(1, size // 10))

    elif base == "Silver":
        # Angular shield with silver sheen
        pulse = 0.8 + 0.2 * math.sin(t * 2)
        col = tuple(int(c * pulse) for c in color)
        pts = [(cx, cy - r), (cx + r, cy - r // 2), (cx + r * 3 // 4, cy + r),
               (cx, cy + r * 3 // 4), (cx - r * 3 // 4, cy + r), (cx - r, cy - r // 2)]
        pygame.draw.polygon(surf, darker(col, 0.45), pts)
        pygame.draw.polygon(surf, col, pts, max(1, size // 12))
        # Inner chevron
        pygame.draw.line(surf, WHITE, (cx - r // 2, cy), (cx, cy - r // 2), max(1, size // 14))
        pygame.draw.line(surf, WHITE, (cx, cy - r // 2), (cx + r // 2, cy), max(1, size // 14))
        for i in range(tier_num):
            pygame.draw.rect(surf, col, (cx - (tier_num - 1) * 4 + i * 8 - 2, cy + r // 3, 4, 4))

    elif base == "Gold":
        # Gold shield with star
        pulse = 0.85 + 0.15 * math.sin(t * 3)
        col = tuple(int(c * pulse) for c in color)
        pts = [(cx, cy - r), (cx + r, cy - r // 4), (cx + r * 3 // 4, cy + r),
               (cx, cy + r * 3 // 4), (cx - r * 3 // 4, cy + r), (cx - r, cy - r // 4)]
        pygame.draw.polygon(surf, darker(col, 0.4), pts)
        pygame.draw.polygon(surf, col, pts, max(1, size // 12))
        # 5-point star in center
        star_r = r // 2
        for i in range(5):
            a1 = -math.pi / 2 + i * math.tau / 5
            a2 = -math.pi / 2 + (i + 2) * math.tau / 5
            pygame.draw.line(surf, (255, 245, 180),
                             (cx + int(math.cos(a1) * star_r), cy + int(math.sin(a1) * star_r)),
                             (cx + int(math.cos(a2) * star_r), cy + int(math.sin(a2) * star_r)),
                             max(1, size // 14))
        for i in range(tier_num):
            pygame.draw.circle(surf, (255, 245, 180), (cx - (tier_num - 1) * 4 + i * 8, cy + r * 2 // 3), max(1, size // 10))

    elif base == "Platinum":
        # Platinum crystalline emblem with shimmer
        pulse = 0.7 + 0.3 * math.sin(t * 4)
        col = tuple(int(c * pulse) for c in color)
        # Diamond shape
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surf, darker(col, 0.35), pts)
        pygame.draw.polygon(surf, col, pts, max(1, size // 10))
        # Inner diamond
        ir = r // 2
        inner = [(cx, cy - ir), (cx + ir, cy), (cx, cy + ir), (cx - ir, cy)]
        pygame.draw.polygon(surf, lighter(col, 0.3), inner, max(1, size // 14))
        # Shimmer line
        sx = cx - r + int((2 * r) * ((t * 0.5) % 1.0))
        pygame.draw.line(surf, WHITE, (sx, cy - r), (sx, cy + r), 1)
        for i in range(tier_num):
            pygame.draw.circle(surf, WHITE, (cx - (tier_num - 1) * 4 + i * 8, cy + r * 2 // 3), max(1, size // 10))

    elif base == "Diamond":
        # Diamond with prismatic refraction effect
        phase = t * 3
        # Outer diamond
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surf, darker(color, 0.3), pts)
        # Prismatic inner facets
        prism_colors = [(200, 230, 255), (180, 220, 255), (220, 240, 255)]
        for i, pc in enumerate(prism_colors):
            off = int(3 * math.sin(phase + i * math.tau / 3))
            fr = r * (3 - i) // 4
            facet = [(cx + off, cy - fr), (cx + fr + off, cy), (cx + off, cy + fr), (cx - fr + off, cy)]
            pygame.draw.polygon(surf, pc, facet, max(1, size // 14))
        pygame.draw.polygon(surf, color, pts, max(1, size // 10))
        # Sparkle particles
        for i in range(3):
            angle = t * 2 + i * math.tau / 3
            px = cx + int(math.cos(angle) * (r + 4))
            py = cy + int(math.sin(angle) * (r + 4))
            pygame.draw.circle(surf, WHITE, (px, py), max(1, size // 16))
        for i in range(tier_num):
            pygame.draw.circle(surf, WHITE, (cx - (tier_num - 1) * 4 + i * 8, cy + r * 2 // 3), max(1, size // 10))

    elif base == "Master":
        # Crown emblem with purple glow
        pulse = 0.75 + 0.25 * math.sin(t * 5)
        col = tuple(int(c * pulse) for c in color)
        # Shield base
        pts = [(cx - r, cy - r // 3), (cx + r, cy - r // 3), (cx + r * 3 // 4, cy + r),
               (cx, cy + r * 3 // 4), (cx - r * 3 // 4, cy + r)]
        pygame.draw.polygon(surf, darker(col, 0.35), pts)
        pygame.draw.polygon(surf, col, pts, max(1, size // 12))
        # Crown on top
        crown = [(cx - r, cy - r // 3), (cx - r * 2 // 3, cy - r),
                 (cx - r // 4, cy - r // 2), (cx, cy - r * 5 // 4),
                 (cx + r // 4, cy - r // 2), (cx + r * 2 // 3, cy - r),
                 (cx + r, cy - r // 3)]
        pygame.draw.polygon(surf, darker(col, 0.5), crown)
        pygame.draw.polygon(surf, col, crown, max(1, size // 14))
        # Jewels on crown tips
        for jx, jy in [(cx - r * 2 // 3, cy - r), (cx, cy - r * 5 // 4), (cx + r * 2 // 3, cy - r)]:
            pygame.draw.circle(surf, WHITE, (jx, jy), max(1, size // 10))
        # Orbiting particles
        for i in range(4):
            angle = t * 3 + i * math.tau / 4
            px = cx + int(math.cos(angle) * (r + 5))
            py = cy + int(math.sin(angle) * (r + 5))
            pygame.draw.circle(surf, col, (px, py), max(1, size // 14))
        for i in range(tier_num):
            pygame.draw.circle(surf, (255, 210, 255), (cx - (tier_num - 1) * 4 + i * 8, cy + r // 2), max(1, size // 10))

    elif base == "Legendary":
        # Legendary fire emblem with animated flames
        pulse = 0.7 + 0.3 * math.sin(t * 6)
        col = tuple(int(c * pulse) for c in color)
        # Base shield
        pts = [(cx, cy - r), (cx + r, cy - r // 3), (cx + r * 3 // 4, cy + r),
               (cx, cy + r * 3 // 4), (cx - r * 3 // 4, cy + r), (cx - r, cy - r // 3)]
        pygame.draw.polygon(surf, darker(col, 0.3), pts)
        pygame.draw.polygon(surf, col, pts, max(1, size // 10))
        # Crown
        crown = [(cx - r, cy - r // 3), (cx - r // 2, cy - r * 5 // 4),
                 (cx, cy - r * 3 // 4), (cx + r // 2, cy - r * 5 // 4),
                 (cx + r, cy - r // 3)]
        pygame.draw.polygon(surf, darker(col, 0.4), crown)
        pygame.draw.polygon(surf, col, crown, max(1, size // 14))
        # Animated flame tongues
        for i in range(6):
            angle = -math.pi / 2 + (i - 2.5) * 0.4
            flame_h = r // 2 + int(abs(math.sin(t * 8 + i * 1.2)) * r // 3)
            fx = cx + int(math.cos(angle) * r * 0.6)
            fy = cy - r // 3
            flame_col = (255, 120 + int(80 * math.sin(t * 7 + i)), 30)
            pygame.draw.line(surf, flame_col, (fx, fy), (fx + int(math.cos(angle) * 3), fy - flame_h),
                             max(1, size // 12))
        # Inner emblem glow
        pygame.draw.circle(surf, (255, 220, 120), (cx, cy), r // 3, max(1, size // 14))
        # Orbiting fire particles
        for i in range(5):
            angle = t * 4 + i * math.tau / 5
            px = cx + int(math.cos(angle) * (r + 6))
            py = cy + int(math.sin(angle) * (r + 6))
            pc = (255, 160 + int(60 * math.sin(t * 5 + i)), 40)
            pygame.draw.circle(surf, pc, (px, py), max(1, size // 12))
        for i in range(tier_num):
            pygame.draw.circle(surf, (255, 230, 120), (cx - (tier_num - 1) * 5 + i * 10, cy + r // 2), max(2, size // 8))

    elif base == "Mythic":
        # MYTHIC - The ultimate animated emblem with aurora, particles, crown, and pulsing glow
        phase = t * 2
        pulse = 0.6 + 0.4 * math.sin(t * 4)
        if size > 20:
            # Outer glow rings (expanding)
            for ring in range(3):
                ring_r = r + 6 + ring * 4 + int(3 * math.sin(t * 3 + ring))
                ring_col = (min(255, color[0] + 40), min(255, int(color[1] * 0.6)),
                            min(255, int(color[2] * 0.8)))
                pygame.draw.circle(surf, ring_col, (cx, cy), ring_r, max(1, 2 - ring))

        # Main emblem body - ornate shield
        pts = [(cx, cy - r - 2), (cx + r + 2, cy - r // 4), (cx + r, cy + r // 2),
               (cx + r * 2 // 3, cy + r), (cx, cy + r + 2),
               (cx - r * 2 // 3, cy + r), (cx - r, cy + r // 2), (cx - r - 2, cy - r // 4)]
        col = tuple(int(c * pulse) for c in color)
        pygame.draw.polygon(surf, darker(col, 0.25), pts)
        pygame.draw.polygon(surf, col, pts, max(2, size // 8))

        # Grand crown with 5 peaks
        crown_base_y = cy - r // 4
        crown_pts = [(cx - r - 2, crown_base_y)]
        peaks = 5
        for i in range(peaks):
            peak_x = cx - r + int((2 * r) * (i / (peaks - 1)))
            valley_x = cx - r + int((2 * r) * ((i + 0.5) / (peaks - 1))) if i < peaks - 1 else None
            peak_h = r * 3 // 4 + int(abs(math.sin(t * 6 + i * 0.8)) * r // 4)
            crown_pts.append((peak_x, crown_base_y - peak_h))
            if valley_x is not None:
                crown_pts.append((valley_x, crown_base_y - r // 3))
        crown_pts.append((cx + r + 2, crown_base_y))
        pygame.draw.polygon(surf, darker(col, 0.35), crown_pts)
        pygame.draw.polygon(surf, col, crown_pts, max(1, size // 14))

        # Crown jewels (animated color shift)
        jewel_colors = [(255, 80, 80), (80, 200, 255), (255, 220, 80), (180, 120, 255), (80, 255, 160)]
        for i in range(peaks):
            peak_x = cx - r + int((2 * r) * (i / (peaks - 1)))
            peak_h = r * 3 // 4 + int(abs(math.sin(t * 6 + i * 0.8)) * r // 4)
            jc = jewel_colors[i % len(jewel_colors)]
            jc_pulse = tuple(int(c * (0.7 + 0.3 * math.sin(t * 4 + i))) for c in jc)
            pygame.draw.circle(surf, jc_pulse, (peak_x, crown_base_y - peak_h), max(2, size // 8))

        if size > 20:
            # Aurora wave bands and particles are reserved for full-size emblems.
            for band in range(3):
                aurora_pts = []
                aurora_col = [(255, 100, 100), (255, 180, 80), (255, 255, 120)][band]
                for step in range(13):
                    angle = step * math.tau / 12
                    wave = math.sin(angle * 4 + t * 3 + band * 1.2) * (size * 0.04)
                    ar = r + 8 + band * 3 + wave
                    aurora_pts.append((int(cx + math.cos(angle) * ar), int(cy + math.sin(angle) * ar)))
                for s, e in zip(aurora_pts, aurora_pts[1:]):
                    pygame.draw.line(surf, aurora_col, s, e, max(1, size // 24))

            for i in range(8):
                angle = t * (2.5 + i * 0.15) + i * math.tau / 8
                pr = r + 4 + int(6 * math.sin(t * 2 + i))
                px = cx + int(math.cos(angle) * pr)
                py = cy + int(math.sin(angle) * pr)
                pc = (255, 200 + int(55 * math.sin(t * 3 + i)),
                      min(255, 100 + int(100 * math.sin(t * 4 + i))))
                pygame.draw.circle(surf, pc, (px, py), max(1, size // 10))

        # Central mythic symbol (infinity / wings)
        wing_span = r * 2 // 3
        for side in (-1, 1):
            for step in range(8):
                a = step * math.pi / 7
                wx = cx + side * int(math.sin(a) * wing_span * 0.7)
                wy = cy - int(math.cos(a) * wing_span * 0.4) + r // 6
                pygame.draw.circle(surf, (255, 230, 200), (wx, wy), max(1, size // 16))

        # Tier pips with glow (Mythic I-V)
        for i in range(tier_num):
            pip_x = cx - (tier_num - 1) * 5 + i * 10
            pip_y = cy + r * 2 // 3
            pip_glow = (255, int(180 + 75 * math.sin(t * 6 + i * 0.7)), 60)
            pygame.draw.circle(surf, pip_glow, (pip_x, pip_y), max(3, size // 6))
            pygame.draw.circle(surf, WHITE, (pip_x, pip_y), max(2, size // 8))


def map_preview(gm, w, h):
    s = pygame.Surface((gm.w, gm.h))
    for y in range(gm.h):
        for x in range(gm.w):
            g = gm.grid[y][x]
            s.set_at((x, y), (30, 34, 30) if g == 0 else (130, 134, 128) if g == 1 else (170, 124, 66))
    for team, col in ((0, TEAM_COLORS[0]), (1, TEAM_COLORS[1])):
        for px, py in gm.spawns[team]:
            s.set_at((int(px // TILE), int(py // TILE)), col)
    for px, py in gm.sites + gm.zones:
        s.set_at((int(px // TILE), int(py // TILE)), AMBER)
    scale = min(w / gm.w, h / gm.h)
    return pygame.transform.scale(s, (max(1, int(gm.w * scale)), max(1, int(gm.h * scale))))
