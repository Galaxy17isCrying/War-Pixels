import math
from typing import List, Optional, Tuple


class Task:
    __slots__ = ("kind", "pos", "radius", "interact", "tag")

    def __init__(self, kind: str, pos: Tuple[float, float], radius: float = 40.0, interact: bool = False, tag: str = ""):
        self.kind, self.pos, self.radius, self.interact, self.tag = kind, pos, radius, interact, tag


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def fmt_time(t: float) -> str:
    t = max(0, int(math.ceil(t)))
    return f"{t // 60:02d}:{t % 60:02d}"


class Mode:
    id = "base"
    name = "BASE"
    desc = ""
    respawn_delay: Optional[float] = None

    def __init__(self, m):
        self.m = m
        self.scores = [0, 0]
        self.over = False
        self.winner: Optional[int] = None
        self.frozen = False
        self.time_left: Optional[float] = None

    def start(self):
        for c in self.m.combatants:
            self.m.spawn(c, full=True)

    def update(self, dt: float):
        pass

    def on_death(self, victim, killer):
        pass

    def task_for(self, c) -> Task:
        return Task("go", (c.x, c.y), 60)

    def finish(self, winner: Optional[int]):
        if not self.over:
            self.over = True
            self.winner = winner
            self.m.announce("MATCH OVER")

    def finish_by_score(self):
        a, b = self.scores
        self.finish(0 if a > b else 1 if b > a else None)

    def hud(self) -> dict:
        return dict(timer="", sub="", bar=None)

    def markers(self) -> list:
        """(kind, x, y, radius, team_or_None, label)"""
        return []

    def assign_defenders(self, n: int):
        for t in (0, 1):
            bots = sorted([c for c in self.m.combatants if c.team == t and c.is_bot],
                          key=lambda c: (c.role not in ("defender", "support"), c.id))
            for c in bots[:n]:
                c.role = "defender"


class Flag:
    def __init__(self, team, home):
        self.team = team
        self.home = home
        self.x, self.y = home
        self.carrier = None
        self.at_home = True
        self.drop_t = 0.0


class CaptureTheFlag(Mode):
    id = "ctf"
    name = "CAPTURE THE FLAG"
    desc = "Steal the enemy flag and bring it to your base while your own flag is home. First to 3 captures."
    respawn_delay = 8.0
    SCORE_LIMIT = 3
    PICKUP = 26.0

    def __init__(self, m):
        super().__init__(m)
        self.time_left = 480.0
        self.flags = [Flag(0, m.map.flags[0]), Flag(1, m.map.flags[1])]
        self.wave = [dict(go=False, t=0.0), dict(go=False, t=0.0)]
        self._stage = {}

    def staging(self, team):
        if team not in self._stage:
            a, b = self.flags[team].home, self.flags[1 - team].home
            self._stage[team] = self.m.map.nearest_floor(a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25)
        return self._stage[team]

    def _update_waves(self, dt):
        for team in (0, 1):
            w = self.wave[team]
            w["t"] += dt
            raiders = [c for c in self.m.combatants if c.alive and c.team == team and c.role != "defender" and c.role != "sniper"]
            if w["go"]:
                if w["t"] > 45.0 or not raiders:
                    w["go"], w["t"] = False, 0.0
            else:
                sp = self.staging(team)
                ready = sum(1 for c in raiders if math.hypot(c.x - sp[0], c.y - sp[1]) < 260)
                if (len(raiders) >= 3 and ready >= min(5, len(raiders))) or w["t"] > 30.0:
                    w["go"], w["t"] = True, 0.0

    def start(self):
        super().start()
        self.assign_defenders(2)

    def drop(self, f, x, y):
        if f.carrier is not None:
            f.carrier.carry = None
        f.carrier = None
        f.x, f.y = x, y
        f.at_home = False
        f.drop_t = 25.0
        self.m.announce(f"{'ALPHA' if f.team == 0 else 'BRAVO'} FLAG DROPPED")

    def send_home(self, f):
        if f.carrier is not None:
            f.carrier.carry = None
        f.carrier = None
        f.x, f.y = f.home
        f.at_home = True

    def update(self, dt):
        if self.over:
            return
        self.time_left -= dt
        if self.time_left <= 0:
            self.finish_by_score()
            return
        self._update_waves(dt)
        for f in self.flags:
            if f.carrier is not None:
                f.x, f.y = f.carrier.x, f.carrier.y
            elif not f.at_home:
                f.drop_t -= dt
                if f.drop_t <= 0:
                    self.send_home(f)
                    self.m.announce("FLAG RETURNED")
        for c in self.m.combatants:
            if not c.alive:
                continue
            for f in self.flags:
                if f.carrier is None and dist((c.x, c.y), (f.x, f.y)) < self.PICKUP:
                    if f.team != c.team:
                        f.carrier, c.carry, f.at_home = c, f, False
                        self.m.announce(f"{c.name.upper()} TOOK THE {'ALPHA' if f.team == 0 else 'BRAVO'} FLAG")
                        self.m.sounds.append(("ability", c.x, c.y))
                    elif not f.at_home:
                        self.send_home(f)
                        self.m.announce("FLAG RECOVERED")
            if c.carry is not None and self.flags[c.team].at_home and dist((c.x, c.y), self.flags[c.team].home) < 34:
                self.scores[c.team] += 1
                self.send_home(c.carry)
                self.m.announce(f"{'ALPHA' if c.team == 0 else 'BRAVO'} SCORES")
                if self.scores[c.team] >= self.SCORE_LIMIT:
                    self.finish(c.team)
                    return

    def on_death(self, victim, killer):
        if victim.carry is not None:
            self.drop(victim.carry, victim.x, victim.y)

    def task_for(self, c):
        own, enemy = self.flags[c.team], self.flags[1 - c.team]
        if c.carry is not None:
            return Task("go", own.home, 34, tag="capture")
        if enemy.carrier is not None and enemy.carrier.team == c.team and c.role in ("support", "flanker"):
            return Task("go", (enemy.carrier.x, enemy.carrier.y), 110, tag="escort")
        if own.carrier is not None and c.role != "sniper":
            return Task("go", (own.carrier.x, own.carrier.y), 60, tag="hunt")
        if not own.at_home and own.carrier is None and c.role in ("defender", "support", "assault"):
            return Task("go", (own.x, own.y), 20, tag="recover")
        if c.role == "defender":
            return Task("go", own.home, 230, tag="hold")
        if c.role == "sniper":
            mid = ((own.home[0] * 0.65 + enemy.home[0] * 0.35), (own.home[1] * 0.65 + enemy.home[1] * 0.35))
            return Task("go", mid, 260, tag="overwatch")
        if not self.wave[c.team]["go"] and enemy.carrier is None:
            return Task("go", self.staging(c.team), 170, tag="stage")
        return Task("go", (enemy.x, enemy.y), 28, tag="attack")

    def hud(self):
        f0, f1 = self.flags
        def st(f):
            return "TAKEN" if f.carrier else "HOME" if f.at_home else "DROPPED"
        return dict(timer=fmt_time(self.time_left), sub=f"ALPHA FLAG {st(f0)}  |  BRAVO FLAG {st(f1)}  |  FIRST TO {self.SCORE_LIMIT}", bar=None)

    def markers(self):
        out = []
        for f in self.flags:
            out.append(("flag", f.x, f.y, 0, f.team, "FLAG"))
            out.append(("base", f.home[0], f.home[1], 34, f.team, "BASE"))
        return out


class SearchAndDestroy(Mode):
    id = "snd"
    name = "SEARCH & DESTROY"
    desc = "Attackers plant the bomb at a site, defenders stop them. No respawns. First to 4 rounds; sides switch after round 3."
    respawn_delay = None
    ROUNDS_TO_WIN = 4
    ROUND_TIME = 100.0
    FREEZE = 3.0
    END_PAUSE = 4.0
    PLANT = 3.2
    DEFUSE = 5.0
    BOMB = 35.0
    SWITCH_AFTER = 3
    SITE_R = 42.0

    def __init__(self, m):
        super().__init__(m)
        self.attackers = 0
        self.round = 0
        self.state = "freeze"
        self.t = 0.0
        self.bomb: Optional[dict] = None
        self.plant_prog = 0.0
        self.defuse_prog = 0.0
        self.att_site = 0
        self.last_winner = None

    def start(self):
        self.new_round()

    def new_round(self):
        m = self.m
        self.round += 1
        if self.round == self.SWITCH_AFTER + 1:
            self.attackers = 1 - self.attackers
            m.announce("SIDES SWITCHED")
        self.state, self.t, self.frozen = "freeze", self.FREEZE, True
        self.bomb = None
        self.plant_prog = self.defuse_prog = 0.0
        self.time_left = self.ROUND_TIME
        for c in m.combatants:
            m.spawn(c, full=True)
        self.att_site = m.rng.randrange(len(m.map.sites))
        m.announce(f"ROUND {self.round}  -  {'ATTACK' if self.attackers == 0 else 'DEFEND'}")

    def end_round(self, winner: int, why: str):
        if self.state == "ended":
            return
        self.scores[winner] += 1
        self.last_winner = winner
        self.state, self.t = "ended", self.END_PAUSE
        self.m.announce(f"{'ALPHA' if winner == 0 else 'BRAVO'} WINS ROUND - {why}")

    def advance(self):
        best = max(self.scores)
        if best >= self.ROUNDS_TO_WIN or self.round >= 2 * self.ROUNDS_TO_WIN - 1:
            self.finish_by_score()
        else:
            self.new_round()

    def alive_count(self, team):
        return sum(1 for c in self.m.combatants if c.alive and c.team == team)

    def update(self, dt):
        if self.over:
            return
        m = self.m
        if self.state == "freeze":
            self.t -= dt
            if self.t <= 0:
                self.state, self.frozen = "live", False
                m.announce("GO")
            return
        if self.state == "ended":
            self.t -= dt
            if self.t <= 0:
                self.advance()
            return
        att, dfn = self.attackers, 1 - self.attackers
        a_alive, d_alive = self.alive_count(att), self.alive_count(dfn)
        if self.bomb is None:
            self.time_left -= dt
            planter = None
            for c in m.combatants:
                if c.alive and c.team == att and c.interact:
                    if any(dist((c.x, c.y), s) < self.SITE_R for s in m.map.sites):
                        planter = c
                        break
            if planter:
                self.plant_prog += dt * planter.mods.get("objective", 1.0)
                if self.plant_prog >= self.PLANT:
                    site = min(m.map.sites, key=lambda s: dist((planter.x, planter.y), s))
                    self.bomb = dict(pos=site, timer=self.BOMB)
                    self.time_left = self.BOMB
                    m.announce("BOMB PLANTED")
                    m.sounds.append(("ability", site[0], site[1]))
            else:
                self.plant_prog = max(0.0, self.plant_prog - dt * 2)
            if not a_alive:
                self.end_round(dfn, "ATTACKERS ELIMINATED")
            elif not d_alive:
                self.end_round(att, "DEFENDERS ELIMINATED")
            elif self.time_left <= 0:
                self.end_round(dfn, "TIME EXPIRED")
        else:
            self.bomb["timer"] -= dt
            self.time_left = self.bomb["timer"]
            defuser = None
            for c in m.combatants:
                if c.alive and c.team == dfn and c.interact and dist((c.x, c.y), self.bomb["pos"]) < 34:
                    defuser = c
                    break
            if defuser:
                self.defuse_prog += dt * defuser.mods.get("objective", 1.0)
                if self.defuse_prog >= self.DEFUSE:
                    self.end_round(dfn, "BOMB DEFUSED")
            else:
                self.defuse_prog = max(0.0, self.defuse_prog - dt)
            if self.bomb["timer"] <= 0:
                m.explosion(self.bomb["pos"][0], self.bomb["pos"][1], 140, 0, None, 1.0, big=True)
                self.end_round(att, "BOMB DETONATED")
            elif not d_alive:
                self.end_round(att, "DEFENDERS ELIMINATED")

    def task_for(self, c):
        m = self.m
        sites = m.map.sites
        if c.team == self.attackers:
            if self.bomb:
                return Task("go", self.bomb["pos"], 170, tag="guard")
            idx = self.att_site if c.id % 4 else (self.att_site + 1) % len(sites)
            return Task("plant", sites[idx], 24, True, tag="plant")
        if self.bomb:
            return Task("defuse", self.bomb["pos"], 22, True, tag="defuse")
        return Task("go", sites[c.id % len(sites)], 170, tag="hold")

    def hud(self):
        att = "ATTACKING" if self.attackers == 0 else "DEFENDING"
        if self.state == "freeze":
            sub = f"ROUND {self.round}  |  YOU ARE {att}  |  GET READY"
        elif self.bomb:
            sub = f"ROUND {self.round}  |  BOMB PLANTED  |  DEFUSE {self.defuse_prog / self.DEFUSE * 100:.0f}%"
        else:
            sub = f"ROUND {self.round}  |  YOU ARE {att}  |  FIRST TO {self.ROUNDS_TO_WIN}"
        bar = None
        if self.plant_prog > 0 and not self.bomb:
            bar = (self.plant_prog / self.PLANT, "PLANTING")
        elif self.defuse_prog > 0 and self.bomb:
            bar = (self.defuse_prog / self.DEFUSE, "DEFUSING")
        return dict(timer=fmt_time(self.time_left or 0), sub=sub, bar=bar)

    def markers(self):
        out = [("site", s[0], s[1], self.SITE_R, None, "AB"[i] if i < 2 else chr(ord("A") + i)) for i, s in enumerate(self.m.map.sites)]
        if self.bomb:
            out.append(("bomb", self.bomb["pos"][0], self.bomb["pos"][1], 0, None, f"{self.bomb['timer']:.0f}"))
        return out


class Hardpoint(Mode):
    id = "hardpoint"
    name = "HARDPOINT"
    desc = "Hold the active zone to earn points. The zone rotates every 45 seconds. First to 150 points."
    respawn_delay = 5.0
    SCORE_LIMIT = 150
    ROTATE = 45.0
    RADIUS = 95.0

    def __init__(self, m):
        super().__init__(m)
        self.time_left = 360.0
        zones = []
        for row in range(2):
            for column in range(3):
                left = max(2, column * m.map.w // 3)
                right = min(m.map.w - 2, (column + 1) * m.map.w // 3)
                top = max(2, row * m.map.h // 2)
                bottom = min(m.map.h - 2, (row + 1) * m.map.h // 2)
                candidates = [m.map.center(tx, ty)
                              for ty in range(top, bottom)
                              for tx in range(left, right)
                              if not m.map.blocked(*m.map.center(tx, ty), 24)]
                if candidates:
                    zones.append(m.rng.choice(candidates))
        if not zones:
            zones = list(m.map.zones)
        m.rng.shuffle(zones)
        self.order = zones
        self.idx = 0
        self.zone_t = self.ROTATE
        self.accum = [0.0, 0.0]
        self.control: Optional[int] = None
        self.contested = False

    @property
    def active(self):
        return self.order[self.idx % len(self.order)]

    @property
    def upcoming(self):
        return self.order[(self.idx + 1) % len(self.order)]

    def update(self, dt):
        if self.over:
            return
        self.time_left -= dt
        self.zone_t -= dt
        if self.zone_t <= 0:
            self.idx += 1
            self.zone_t = self.ROTATE
            self.m.announce("HARDPOINT MOVED")
        counts = [0, 0]
        for c in self.m.combatants:
            if c.alive and dist((c.x, c.y), self.active) < self.RADIUS:
                counts[c.team] += 1
        self.contested = counts[0] > 0 and counts[1] > 0
        self.control = 0 if counts[0] and not counts[1] else 1 if counts[1] and not counts[0] else None
        if self.control is not None:
            self.accum[self.control] += dt
            while self.accum[self.control] >= 1.0:
                self.accum[self.control] -= 1.0
                self.scores[self.control] += 1
        if max(self.scores) >= self.SCORE_LIMIT:
            self.finish_by_score()
        elif self.time_left <= 0:
            self.finish_by_score()

    def task_for(self, c):
        if self.zone_t < 7 and c.role not in ("defender",):
            return Task("go", self.upcoming, 70, tag="rotate")
        if c.role == "sniper":
            return Task("go", self.active, 300, tag="overwatch")
        return Task("go", self.active, self.RADIUS * 0.8, tag="hold")

    def hud(self):
        ctrl = "CONTESTED" if self.contested else ("ALPHA HOLDS" if self.control == 0 else "BRAVO HOLDS" if self.control == 1 else "UNCLAIMED")
        return dict(timer=fmt_time(self.time_left), sub=f"{ctrl}  |  MOVES IN {self.zone_t:.0f}s  |  FIRST TO {self.SCORE_LIMIT}", bar=None)

    def markers(self):
        return [("zone", self.active[0], self.active[1], self.RADIUS, self.control, "ACTIVE"),
                ("zone_next", self.upcoming[0], self.upcoming[1], self.RADIUS, None, "NEXT")]


class GroundWar(Mode):
    id = "groundwar"
    name = "GROUND WAR"
    desc = "50v50 event. Capture command sectors and eliminate enemy forces. First to 300 points."
    respawn_delay = 4.0
    SCORE_LIMIT = 300
    CAPTURE_TIME = 8.0
    HOLD_INTERVAL = 4.0
    RADIUS = 180.0

    def __init__(self, m):
        super().__init__(m)
        self.time_left = 900.0
        self.zones = [{"pos": pos, "owner": None, "capture": [0.0, 0.0], "hold": 0.0}
                      for pos in m.map.zones]

    def on_death(self, victim, killer):
        if killer is not None and killer.team != victim.team:
            self.scores[killer.team] += 1
            self._check_score()

    def _check_score(self):
        if max(self.scores) >= self.SCORE_LIMIT:
            self.finish_by_score()

    def update(self, dt):
        if self.over:
            return
        self.time_left -= dt
        for zone in self.zones:
            counts = [sum(c.alive and c.team == team and not c.is_target
                          and dist((c.x, c.y), zone["pos"]) <= self.RADIUS
                          for c in self.m.combatants) for team in (0, 1)]
            if counts[0] and not counts[1]:
                attacking = 0
            elif counts[1] and not counts[0]:
                attacking = 1
            else:
                attacking = None
            if attacking is not None and zone["owner"] != attacking:
                zone["capture"][attacking] = min(self.CAPTURE_TIME,
                                                   zone["capture"][attacking] + dt)
                zone["capture"][1 - attacking] = max(0.0, zone["capture"][1 - attacking] - dt)
                if zone["capture"][attacking] >= self.CAPTURE_TIME:
                    zone["owner"] = attacking
                    zone["capture"] = [0.0, 0.0]
                    self.m.announce(f"TEAM {('ALPHA', 'BRAVO')[attacking]} CAPTURED A SECTOR")
            elif attacking is None:
                zone["capture"] = [max(0.0, value - dt * 0.5) for value in zone["capture"]]
            if zone["owner"] is not None:
                zone["hold"] += dt
                while zone["hold"] >= self.HOLD_INTERVAL:
                    zone["hold"] -= self.HOLD_INTERVAL
                    self.scores[zone["owner"]] += 1
        self._check_score()
        if not self.over and self.time_left <= 0:
            self.finish_by_score()

    def task_for(self, c):
        zone = self.zones[c.id % len(self.zones)]
        return Task("go", zone["pos"], self.RADIUS * 0.7,
                    tag="hold" if zone["owner"] == c.team else "capture")

    def hud(self):
        owned = [sum(zone["owner"] == team for zone in self.zones) for team in (0, 1)]
        return dict(timer=fmt_time(self.time_left), sub=f"SECTORS  {owned[0]} - {owned[1]}  |  ELIMINATIONS + SECTOR CONTROL",
                    bar=None)

    def markers(self):
        out = []
        for index, zone in enumerate(self.zones):
            label = f"{index + 1}  {zone['capture'][0] / self.CAPTURE_TIME * 100:.0f}%" \
                if zone["owner"] is None else str(index + 1)
            out.append(("zone", zone["pos"][0], zone["pos"][1], self.RADIUS, zone["owner"], label))
        return out


class Practice(Mode):
    id = "practice"
    name = "PRACTICE RANGE"
    desc = "Test every weapon on stationary and moving targets."
    respawn_delay = 3.0

    def task_for(self, c):
        p = self.m.player
        return Task("go", (p.x, p.y) if p else (c.x, c.y), 220, tag="spar")

    def hud(self):
        return dict(timer="", sub="PRACTICE  |  [ ] CHANGE WEAPON  |  B TOGGLE BOTS  |  C COMPARE", bar=None)


MODES = {"ctf": CaptureTheFlag, "snd": SearchAndDestroy, "hardpoint": Hardpoint,
         "groundwar": GroundWar, "practice": Practice}
MODE_ORDER = ["ctf", "snd", "hardpoint"]
