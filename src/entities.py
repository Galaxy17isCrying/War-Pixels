import math
from typing import Optional

from .config import BODY_RADIUS, character, weapons
from .weapons import WeaponState

BASE_SPEED = 190.0


class Bullet:
    __slots__ = ("x", "y", "dx", "dy", "speed", "dmg", "owner", "wid", "traveled", "max_dist", "spec", "alive")

    def __init__(self, x, y, angle, spec, owner):
        self.x, self.y = x, y
        self.dx, self.dy = math.cos(angle), math.sin(angle)
        self.speed = spec["speed"]
        self.spec = spec
        self.dmg = spec["dmg"]
        self.owner = owner
        self.wid = spec["id"]
        self.traveled = 0.0
        self.max_dist = spec["range"] * 1.5
        self.alive = True


class Grenade:
    __slots__ = ("x", "y", "vx", "vy", "fuse", "owner", "mult", "alive")

    def __init__(self, x, y, angle, speed, owner, mult):
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.fuse = 1.4
        self.owner = owner
        self.mult = mult
        self.alive = True


class Effect:
    __slots__ = ("kind", "x", "y", "a", "b", "ttl", "life", "extra")

    def __init__(self, kind, x, y, a=0.0, b=0.0, ttl=0.2, extra=None):
        self.kind, self.x, self.y, self.a, self.b = kind, x, y, a, b
        self.ttl = self.life = ttl
        self.extra = extra


class Combatant:
    def __init__(self, cid: int, name: str, team: int, char_id: str, primary: str, secondary: str,
                 equipment: str = "none", is_bot: bool = True):
        self.id = cid
        self.name = name
        self.team = team
        self.char = character(char_id)
        self.role = self.char["ai_role"]
        self.is_bot = is_bot
        self.is_target = False
        self.brain = None
        self.mods = self.char["passive"]["mods"]
        self.equipment = equipment
        wdb = weapons()
        ammo_mult = self.mods.get("ammo", 1.0) * (1.3 if equipment == "ammo" else 1.0)
        self.ammo_mult = ammo_mult
        recoil_scale = 0.55 if not is_bot else 1.0
        self.weapons = [WeaponState(wdb[primary], ammo_mult, recoil_scale),
                        WeaponState(wdb[secondary], ammo_mult, recoil_scale)]
        self.cur = 0
        self.swap_t = 0.0
        self.maxhp = self.char["hp"] + (20 if equipment == "armor" else -10 if equipment == "boots" else 0)
        self.hp = float(self.maxhp)
        self.immortal = False
        self.speed_mult = self.char["speed"] * (0.95 if equipment == "armor" else 1.05 if equipment == "boots" else 1.0)
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.aim = 0.0
        self.alive = False
        self.respawn_t = 0.0
        self.awaiting_loadout = False
        self.invuln = 0.0
        self.mx = self.my = 0.0
        self.trigger = False
        self.trigger_prev = False
        self.ads = False
        self.sprint = False
        self.want_reload = False
        self.want_ability = False
        self.interact = False
        self.swap_to: Optional[int] = None
        self.ability_cd = 0.0
        self.sprint_t = self.steady_t = self.cloak_t = 0.0
        self.revealed_until = {0: 0.0, 1: 0.0}
        self.carry = None
        self.home = (0.0, 0.0)
        self.patrol = None
        self.stats = dict(kills=0, deaths=0, shots=0, hits=0, headshots=0, damage=0, weapon_kills={})
        self.kill_streak = 0
        self.streak_score = 0
        self.nuke_charges = 0
        self.last_attacker = None
        self.last_hit_t = -99.0
        self.spawn_count = 0

    @property
    def weapon(self) -> WeaponState:
        return self.weapons[self.cur]

    @property
    def radius(self):
        return BODY_RADIUS

    def speed_now(self) -> float:
        w = self.weapon.s
        s = BASE_SPEED * self.speed_mult * w["move"]
        if self.sprint_t > 0:
            s *= 1.6
        elif self.sprint and not self.ads:
            s *= 1.22
        if self.carry is not None:
            s *= 0.85
        if self.ads:
            s *= 0.65
        if self.weapon.reloading:
            s *= 0.9
        return s

    def full_resupply(self):
        for w in self.weapons:
            w.full_reset(self.ammo_mult)
