import math
import random

RELOAD_TIME_MULTIPLIER = 0.9


class WeaponState:
    """Runtime state of one weapon: ammo, reload, cooldown and recoil bloom."""

    def __init__(self, spec: dict, ammo_mult: float = 1.0, recoil_scale: float = 1.0):
        self.s = spec
        self.recoil_scale = max(0.0, recoil_scale)
        self.mag = spec["mag"]
        self.reserve = int(spec["reserve"] * ammo_mult)
        self.unlimited = spec["cat"] == "MELEE"
        self.cooldown = 0.0
        self.reload_t = 0.0
        self.reload_duration = 0.0
        self.bloom = 0.0
        self.seq = 0
        self.since = 9.0
        self.phase = (sum(map(ord, spec["id"])) % 628) / 100.0

    @property
    def reloading(self) -> bool:
        return self.reload_t > 0

    @property
    def reload_progress(self) -> float:
        if self.reload_duration <= 0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - self.reload_t / self.reload_duration))

    def refill(self, fraction=1.0, ammo_mult=1.0):
        self.reserve = max(self.reserve, int(self.s["reserve"] * ammo_mult * fraction))

    def full_reset(self, ammo_mult=1.0):
        self.mag = self.s["mag"]
        self.reserve = int(self.s["reserve"] * ammo_mult)
        self.reload_t = self.reload_duration = self.cooldown = self.bloom = 0.0
        self.seq = 0

    def start_reload(self) -> bool:
        if self.reloading or self.mag >= self.s["mag"] or self.reserve <= 0:
            return False
        self.reload_duration = self.s["reload"] * RELOAD_TIME_MULTIPLIER
        self.reload_t = self.reload_duration
        return True

    def update(self, dt: float):
        self.cooldown -= dt
        self.since += dt
        if self.reload_t > 0:
            self.reload_t -= dt
            if self.reload_t <= 0:
                self.reload_t = 0.0
                take = min(self.s["mag"] - self.mag, self.reserve)
                self.mag += take
                self.reserve -= take
        if self.since > 0.09:
            self.bloom = max(0.0, self.bloom - self.s["recover"] * dt)
        if self.since > 0.35:
            self.seq = 0

    def ready(self) -> bool:
        return self.cooldown <= 0 and (self.unlimited or self.mag > 0) and not self.reloading

    def spread(self, ads: bool, speed_frac: float, still_mult: float = 1.0, steady: bool = False) -> float:
        base = self.s["aim"] if ads else self.s["hip"]
        if steady:
            return base * 0.15
        spread = base + self.s["movepen"] * speed_frac + self.bloom
        if speed_frac < 0.05:
            spread *= still_mult
        return spread

    def fire(self, rng: random.Random, ads: bool, speed_frac: float, still_mult=1.0, steady=False, extra_err=0.0):
        """Consumes ammo and returns a list of bullet angle offsets in radians, or None."""
        if not self.ready():
            return None
        s = self.s
        spread = self.spread(ads, speed_frac, still_mult, steady) + extra_err
        kick = (0.0 if steady else s["hrec"] * self.recoil_scale
                * math.sin(self.seq * 0.85 + self.phase) * min(1.0, self.seq / 3.0))
        offsets = []
        for _ in range(s["pellets"]):
            jitter = max(-spread, min(spread, rng.gauss(0, spread / 2.0)))
            offsets.append(math.radians(kick + jitter))
        if not self.unlimited:
            self.mag -= 1
        self.cooldown = 60.0 / s["rate"]
        self.since = 0.0
        self.seq += 1
        if not steady:
            self.bloom = min(self.bloom + s["vrec"] * self.recoil_scale, s["vrec"] * self.recoil_scale * 12)
        return offsets


def damage_at_range(spec: dict, dist: float) -> float:
    half = spec["range"] * 0.5
    if dist <= half:
        return spec["dmg"]
    t = min(1.0, (dist - half) / (spec["range"] - half))
    return spec["dmg"] * (1.0 - t * (1.0 - spec["falloff"]))


def aim_assist_angle(angle: float, origin, targets, cone: float, strength: float, max_distance: float) -> float:
    """Nudge aim toward the closest eligible target without changing base weapon accuracy."""
    if strength <= 0 or cone <= 0 or max_distance <= 0:
        return angle
    best = None
    for target in targets:
        dx, dy = target.x - origin[0], target.y - origin[1]
        distance = math.hypot(dx, dy)
        delta = (math.atan2(dy, dx) - angle + math.pi) % (2 * math.pi) - math.pi
        if distance <= max_distance and abs(delta) <= cone:
            candidate = (abs(delta), distance, delta)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
    return angle if best is None else angle + best[2] * min(1.0, strength)


def ttk_seconds(spec: dict, hp: float = 100.0) -> float:
    shots = math.ceil(hp / (spec["dmg"] * spec["pellets"] * 0.6 if spec["pellets"] > 1 else spec["dmg"]))
    return max(0, shots - 1) * 60.0 / spec["rate"]
