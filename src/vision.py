import math

FOV = math.radians(150)
CLOSE_SENSE = 110.0
CLOAK_RANGE = 70.0


def view_range(a, base: float) -> float:
    return base * (1.2 if a.ads else 1.0)


def can_see(m, a, e, base_range: float) -> bool:
    """Legitimate line-of-sight check: range, field of view, walls, cloak and passives all apply."""
    dx, dy = e.x - a.x, e.y - a.y
    d2 = dx * dx + dy * dy
    rng = view_range(a, base_range) * e.mods.get("detect", 1.0)
    if e.cloak_t > 0:
        rng = CLOAK_RANGE
    if d2 > rng * rng:
        return False
    if d2 > CLOSE_SENSE * CLOSE_SENSE:
        diff = abs((math.atan2(dy, dx) - a.aim + math.pi) % math.tau - math.pi)
        if diff > FOV / 2:
            return False
    return m.map.los(a.x, a.y, e.x, e.y)
