import math

from .config import TILE
from .entities import Effect, Grenade

REVEAL_RADIUS = 380.0
HEAL_RADIUS = 150.0
AMMO_RADIUS = 140.0


def _sprint(m, c):
    c.sprint_t = 3.0
    return True


def _reveal(m, c):
    for e in m.combatants:
        if e.alive and e.team != c.team and math.hypot(e.x - c.x, e.y - c.y) <= REVEAL_RADIUS:
            e.revealed_until[c.team] = m.time + 4.0
    m.fx.append(Effect("ring", c.x, c.y, REVEAL_RADIUS, 0, 0.8, (120, 230, 220)))
    return True


def _heal(m, c):
    amount = 40 * c.mods.get("heal", 1.0)
    healed = False
    for a in m.combatants:
        if a.alive and a.team == c.team and math.hypot(a.x - c.x, a.y - c.y) <= HEAL_RADIUS and a.hp < a.maxhp:
            a.hp = min(a.maxhp, a.hp + amount)
            healed = True
    m.fx.append(Effect("ring", c.x, c.y, HEAL_RADIUS, 0, 0.7, (110, 230, 130)))
    return healed


def _barrier(m, c):
    fx, fy = math.cos(c.aim), math.sin(c.aim)
    px, py = -fy, fx
    placed = 0
    for k in (-1, 0, 1):
        x = c.x + fx * 64 + px * k * TILE
        y = c.y + fy * 64 + py * k * TILE
        tx, ty = int(x // TILE), int(y // TILE)
        if any(o.alive and abs(o.x - (tx * TILE + TILE / 2)) < TILE / 2 + 14 and abs(o.y - (ty * TILE + TILE / 2)) < TILE / 2 + 14
               for o in m.combatants):
            continue
        if m.map.add_barrier(tx, ty, m.time + 12.0):
            placed += 1
    return placed > 0


def _grenade(m, c):
    dist = max(120.0, min(420.0, getattr(c, "aim_dist", 300.0)))
    m.grenades.append(Grenade(c.x, c.y, c.aim, dist / 1.2, c, c.mods.get("explosive", 1.0)))
    return True


def _ammo(m, c):
    needed = False
    for a in m.combatants:
        if a.alive and a.team == c.team and math.hypot(a.x - c.x, a.y - c.y) <= AMMO_RADIUS:
            for w in a.weapons:
                if w.reserve < w.s["reserve"] * a.ammo_mult * 0.7:
                    needed = True
                w.refill(1.0, a.ammo_mult)
    m.fx.append(Effect("ring", c.x, c.y, AMMO_RADIUS, 0, 0.6, (230, 200, 90)))
    return needed


def _steady(m, c):
    c.steady_t = 4.0
    return True


def _cloak(m, c):
    c.cloak_t = 5.0
    return True


HANDLERS = {"sprint": _sprint, "reveal": _reveal, "heal": _heal, "barrier": _barrier,
            "grenade": _grenade, "ammo": _ammo, "steady": _steady, "cloak": _cloak}


def activate(m, c) -> bool:
    ab = c.char["ability"]
    if not c.alive or c.ability_cd > 0:
        return False
    if not HANDLERS[ab["id"]](m, c):
        return False
    c.ability_cd = ab["cooldown"]
    m.sounds.append(("ability", c.x, c.y))
    return True
