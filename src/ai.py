import math
import random

from . import abilities
from .pathfinding import find_path


def angle_diff(a, b):
    return (a - b + math.pi) % math.tau - math.pi


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


class BotBrain:
    """Per-bot decision making: perception -> state -> movement/aim/fire/abilities."""

    def __init__(self, c, m):
        self.c, self.m = c, m
        self.rng = random.Random(m.rng.random())
        self.d = m.diff
        self.visible = []
        self.reset()

    def reset(self):
        c = self.c
        self.path = []
        self.goal = None
        self.goal_ver = -1
        self.path_t = 0.0
        self.target = None
        self.react_t = 0.0
        self.err = 0.0
        self.err_t = 0.0
        self.heard = None
        self.last_seen = None
        self.last_seen_t = -99.0
        self.state = "objective"
        self.stuck_t = 0.0
        self.check_t = 0.5
        self.check_pos = (c.x, c.y)
        self.cmd_move = 0.0
        self.strafe = 1
        self.strafe_t = 0.0
        self.hold_pt = None
        self.hold_t = 0.0
        self.abil_t = self.rng.random() * 0.6
        self.cover = None
        self.cover_t = 0.0
        self.aim_cur = c.aim
        self.look_a = c.aim
        self.look_t = 0.0
        self.unstick_t = 0.0
        self.unstick_dir = (0.0, 0.0)
        self.waypoint = None
        self.waypoint_done = False
        self.task = None
        self.task_t = 0.0
        self.task_key = None
        self.spot = None
        self.retreat_ok = self.rng.random() < self.d["tactics"] + 0.25
        self.brave = self.rng.random()
        self.objective_focus = self.rng.random() < self.d["tactics"] * 0.85
        self.visible = []
        self.investigate_until = 0.0
        self.at_goal = False

    # --- perception hooks -------------------------------------------------
    def hear(self, x, y):
        if self.target is not None or not self.c.alive:
            return
        err = self.d["hear_err"]
        self.heard = (x + self.rng.gauss(0, err / 2), y + self.rng.gauss(0, err / 2), self.m.time)

    def _select_target(self, dt):
        m, c, d = self.m, self.c, self.d
        prev = self.target
        if self.visible:
            spec = c.weapon.s

            def target_score(enemy):
                distance = dist(c.x, c.y, enemy.x, enemy.y)
                out_of_range = max(0.0, distance - spec["range"] * 0.7)
                wounded = (enemy.maxhp - enemy.hp) * 0.3 * d["aggression"]
                objective = 180.0 if enemy.carry is not None else 0.0
                return distance + out_of_range * 0.5 - wounded - objective

            best = min(self.visible, key=target_score)
            if best is not prev and not (best is getattr(self, "_last_target", None) and m.time - self.last_seen_t < 0.6):
                self.react_t = d["reaction"] * self.rng.uniform(0.8, 1.25)
            self.target = best
            self._last_target = best
            self.last_seen = (best.x, best.y)
            self.last_seen_t = m.time
            self.react_t = max(0.0, self.react_t - dt)
        else:
            self.target = None
        if self.target is None and m.time - c.last_hit_t < 0.3 and c.last_attacker and c.last_attacker.alive \
                and c.last_attacker.team != c.team:
            a = c.last_attacker
            self.heard = (a.x + self.rng.gauss(0, 60), a.y + self.rng.gauss(0, 60), m.time)

    def _investigate_pos(self, task):
        m, c, d = self.m, self.c, self.d
        best, best_t = None, -1.0
        if self.last_seen and m.time - self.last_seen_t < 6.0:
            best, best_t = self.last_seen, self.last_seen_t
        if self.heard and m.time - self.heard[2] < 8.0 and self.heard[2] > best_t:
            best, best_t = (self.heard[0], self.heard[1]), self.heard[2]
        if d["share"] > 0:
            for x, y, t in m.team_known[c.team].values():
                if m.time - t < 3.5 and t > best_t:
                    best, best_t = (x, y), t
        if best is None or c.carry is not None:
            return None
        if task.interact and dist(c.x, c.y, *task.pos) < 70:
            return None
        if task.tag in ("attack", "capture", "escort", "recover", "hunt") and self.brave < d["aggression"] + 0.2:
            return None
        if c.role == "defender" and dist(best[0], best[1], *task.pos) > 450:
            return None
        if dist(c.x, c.y, *best) < 45:
            self.last_seen = None
            self.heard = None
            return None
        return best

    # --- movement helpers ---------------------------------------------------
    def _request_path(self, pos):
        m = self.m
        if m.path_budget <= 0:
            return
        m.path_budget -= 1
        p = find_path(m.map, (self.c.x, self.c.y), pos)
        self.path = p or []
        self.goal, self.goal_ver = pos, m.map.version
        self.path_t = 0.6 if p else 0.3

    def goto(self, pos):
        need = (self.goal is None or dist(self.goal[0], self.goal[1], pos[0], pos[1]) > 40
                or self.goal_ver != self.m.map.version)
        if (need and self.path_t <= 0) or (not self.path and self.path_t <= 0):
            self._request_path(pos)
        self._follow()

    def _follow(self):
        c, gm = self.c, self.m.map
        if self.unstick_t > 0:
            c.mx, c.my = self.unstick_dir
            self.cmd_move += 1
            return
        for _ in range(2):
            if len(self.path) > 1 and gm.walk_clear(c.x, c.y, self.path[1][0], self.path[1][1]):
                self.path.pop(0)
        if not self.path:
            return
        wx, wy = self.path[0]
        if dist(c.x, c.y, wx, wy) < 12:
            self.path.pop(0)
            if not self.path:
                return
            wx, wy = self.path[0]
        if gm.solid_at(wx, wy):
            self.path = []
            self.path_t = 0.0
            return
        d = dist(c.x, c.y, wx, wy) or 1.0
        c.mx, c.my = (wx - c.x) / d, (wy - c.y) / d
        self.cmd_move += 1

    def _stuck_check(self, dt):
        m, c = self.m, self.c
        self.check_t -= dt
        if self.unstick_t > 0:
            self.unstick_t -= dt
        if self.check_t <= 0:
            moved = dist(c.x, c.y, *self.check_pos)
            if self.cmd_move > 6 and moved < 6 and not self.at_goal:
                self.stuck_t += 0.5
            else:
                self.stuck_t = 0.0
            if self.stuck_t >= 1.0:
                # Try 8 directions, pick the one with most clearance
                best_dir = None
                best_clear = -1
                for i in range(8):
                    a = i * math.tau / 8
                    dx, dy = math.cos(a), math.sin(a)
                    clear = 0
                    for step in range(1, 6):
                        test_x = c.x + dx * step * 10
                        test_y = c.y + dy * step * 10
                        if not m.map.blocked(test_x, test_y, 12):
                            clear += 1
                        else:
                            break
                    if clear > best_clear:
                        best_clear = clear
                        best_dir = (dx, dy)
                if best_dir and best_clear > 0:
                    self.unstick_dir = best_dir
                else:
                    a = self.rng.uniform(0, math.tau)
                    self.unstick_dir = (math.cos(a), math.sin(a))
                self.unstick_t = 0.5
                self.stuck_t = 0.0
                self.path = []
                self.path_t = 0.0
                m.stuck_events += 1
            self.check_t = 0.5
            self.check_pos = (c.x, c.y)
            self.cmd_move = 0

    def _free_dir(self, dx, dy, look=22.0):
        c = self.c
        return not self.m.map.blocked(c.x + dx * look, c.y + dy * look, 12)

    def _find_cover(self, threat):
        m, c = self.m, self.c
        if self.cover and m.time < self.cover_t:
            return self.cover
        best, best_score = None, -1e9
        for _ in range(24):
            p = m.map.random_floor_near(c.x, c.y, 280, self.rng)
            if m.map.los(p[0], p[1], threat[0], threat[1]):
                continue
            d_self = dist(c.x, c.y, *p)
            d_threat = dist(p[0], p[1], threat[0], threat[1])
            # Prefer cover that is close to us but not too close to the threat
            score = -d_self + d_threat * 0.3
            if score > best_score:
                best_score = score
                best, _ = p, score
        self.cover = best
        self.cover_t = m.time + 2.5
        return best

    # --- task selection -------------------------------------------------------
    def _current_task(self):
        m, c = self.m, self.c
        if self.task is None or m.time >= self.task_t:
            self.task = m.mode.task_for(c)
            self.task_t = m.time + 0.4
            key = (self.task.kind, round(self.task.pos[0] / 64), round(self.task.pos[1] / 64))
            if key != self.task_key:
                self.task_key = key
                self.waypoint = None
                self.waypoint_done = False
                self.spot = None
        return self.task

    def _destination(self, task):
        m, c, d = self.m, self.c, self.d
        dest, radius = task.pos, task.radius
        if c.role == "sniper" and not task.interact and task.kind == "go" and task.tag not in ("capture", "recover", "hunt", "escort"):
            if self.spot is None:
                self.spot = m.map.sniper_spot(task.pos, self.rng)
            return self.spot, 60
        if c.role == "flanker" and task.tag in ("attack", "hold", "rotate") and not self.waypoint_done \
                and dist(c.x, c.y, *task.pos) > 500:
            if self.waypoint is None and self.rng.random() < d["tactics"]:
                gm = m.map
                y = gm.px_h * self.rng.choice((0.15, 0.85))
                self.waypoint = gm.nearest_floor((c.x + task.pos[0]) / 2, y)
            if self.waypoint is not None:
                if dist(c.x, c.y, *self.waypoint) < 70:
                    self.waypoint_done = True
                else:
                    return self.waypoint, 50
            else:
                self.waypoint_done = True
        if c.role == "support" and task.tag in ("attack", "hold", "rotate") and dist(c.x, c.y, *task.pos) > 350:
            allies = [a for a in m.allies_alive(c) if a.role in ("assault", "flanker") and not a.is_target]
            if allies:
                a = min(allies, key=lambda a: dist(a.x, a.y, *task.pos))
                if dist(a.x, a.y, *task.pos) < dist(c.x, c.y, *task.pos) + 200:
                    return (a.x, a.y), 90
        return dest, radius

    # --- main update -----------------------------------------------------------
    def think(self, dt):
        c, m, d = self.c, self.m, self.d
        c.mx = c.my = 0.0
        c.trigger = False
        c.interact = False
        c.sprint = False
        c.ads = False
        if not c.alive or m.mode.frozen:
            return
        self.path_t -= dt
        self.err_t -= dt
        self.abil_t -= dt
        self.strafe_t -= dt
        self.hold_t -= dt
        self.look_t -= dt
        if self.err_t <= 0:
            self.err_t = 0.4
            self.err = math.radians(self.rng.gauss(0, d["aim_err"] / 2))
        self.at_goal = False
        self._select_target(dt)
        task = self._current_task()
        hp_frac = c.hp / c.maxhp
        invest = None
        if self.target is None:
            invest = self._investigate_pos(task)
        if self.target is not None and self.retreat_ok and hp_frac < d["retreat_hp"] and c.carry is None:
            self.state = "retreat"
        elif self.target is not None:
            self.state = "engage" if hp_frac >= d["retreat_hp"] or not self.retreat_ok else "retreat"
        elif hp_frac < d["retreat_hp"] and self.retreat_ok and m.time - c.last_hit_t < 4.0 and c.carry is None:
            self.state = "retreat"
        elif invest is not None:
            self.state = "investigate"
        else:
            self.state = "objective"
        desired_aim = None
        if self.target is not None:
            desired_aim = self._engage_aim(dt)
        if self.state == "retreat":
            threat = (self.target.x, self.target.y) if self.target else (self.last_seen or (c.x + 1, c.y))
            cover = self._find_cover(threat)
            if cover:
                self.goto(cover)
            else:
                # Fall back toward nearest alive ally instead of just spawn
                allies = [a for a in m.allies_alive(c) if a is not c and dist(a.x, a.y, c.x, c.y) > 60]
                if allies:
                    nearest = min(allies, key=lambda a: dist(a.x, a.y, c.x, c.y))
                    self.goto((nearest.x, nearest.y))
                else:
                    self.goto(m.map.spawns[c.team][0])
            if c.ability_cd <= 0 and c.hp < c.maxhp * 0.5 and c.char["ability"]["id"] == "sprint":
                c.want_ability = True
        elif self.state == "engage":
            self._engage_move(dt)
        elif self.state == "investigate":
            self.goto(invest)
            if dist(c.x, c.y, *invest) > 500 and self.target is None:
                c.sprint = True
        else:
            self._objective_move(task, dt)
        self._aim_update(dt, desired_aim)
        self._reload_logic()
        if self.abil_t <= 0:
            self.abil_t = 0.5
            self._use_ability(task, invest)
        self._stuck_check(dt)

    def _engage_aim(self, dt):
        c, d = self.c, self.d
        t = self.target
        dx, dy = t.x - c.x, t.y - c.y
        dd = math.hypot(dx, dy)
        spec = c.weapon.s
        flight = dd / spec["speed"]
        px = t.x + t.vx * flight * d["lead"]
        py = t.y + t.vy * flight * d["lead"]
        c.aim_dist = dd
        return math.atan2(py - c.y, px - c.x)

    def _aim_update(self, dt, desired):
        c, d = self.c, self.d
        if desired is None:
            if c.mx or c.my:
                desired = math.atan2(c.my, c.mx)
            else:
                if self.look_t <= 0:
                    self.look_t = self.rng.uniform(1.2, 2.8)
                    self.look_a = self.aim_cur + self.rng.uniform(-1.4, 1.4)
                desired = self.look_a
        turn = math.radians(d["turn"]) * dt
        diff = angle_diff(desired, self.aim_cur)
        self.aim_cur += max(-turn, min(turn, diff))
        c.aim = self.aim_cur + (self.err if self.target is not None else 0.0)
        if self.target is not None:
            self._maybe_fire(abs(diff))

    def _maybe_fire(self, off):
        c, d = self.c, self.d
        w = c.weapon
        spec = w.s
        dd = getattr(c, "aim_dist", 999.0)
        if self.react_t > 0 or w.mag == 0 or dd > spec["range"] * 1.25:
            return
        tol = math.radians(5 + max(2.0, 25 - dd / 20)) if dd < 500 else math.radians(4)
        tol *= d["aim_tolerance"]
        if off > tol:
            return
        if spec["cat"] in ("SNIPER", "MARKSMAN") or (dd > spec["range"] * 0.45 and spec["cat"] in ("AR", "LMG")):
            c.ads = True
        if spec["auto"] and w.seq >= d["burst"] and w.since < 0.3:
            return
        c.trigger = True

    def _engage_move(self, dt):
        m, c, d = self.m, self.c, self.d
        t = self.target
        spec = c.weapon.s
        dd = dist(c.x, c.y, t.x, t.y)
        cat = spec["cat"]
        ideal = spec["range"] * (0.7 if cat == "SNIPER" else 0.5 if cat == "SG" else 0.4)
        ux, uy = (t.x - c.x) / (dd or 1), (t.y - c.y) / (dd or 1)
        task = self.task
        if task is not None and cat != "SNIPER" and c.role != "sniper":
            if c.carry is not None or ((self.objective_focus or task.tag == "attack") and dd > 110 and
                                       task.tag in ("attack", "capture", "recover", "hunt", "escort", "rotate")):
                self._objective_move(task, dt)
                return
        if cat == "SNIPER" or (c.role == "sniper" and dd > 250):
            c.ads = True
            return
        if self.react_t > 0 and d["tactics"] < 0.5:
            return
        if dd > ideal * 1.4 and self.brave < d["aggression"] + 0.15:
            self.goto((t.x, t.y))
            return
        if dd < ideal * 0.5 and cat not in ("SG", "SMG"):
            if self._free_dir(-ux, -uy):
                c.mx, c.my = -ux, -uy
                return
        if d["tactics"] > 0.35 or self.brave > 0.5:
            if self.strafe_t <= 0:
                self.strafe = -self.strafe
                self.strafe_t = self.rng.uniform(0.4, 1.2)
            # Mix strafe with slight forward/backward for unpredictable movement
            approach = 0.0
            if dd > ideal * 0.9 and self.brave > 0.4:
                approach = 0.3  # slight forward bias
            elif dd < ideal * 0.6:
                approach = -0.25  # slight backward bias
            sx, sy = -uy * self.strafe + ux * approach, ux * self.strafe + uy * approach
            mag = math.hypot(sx, sy) or 1.0
            sx, sy = sx / mag, sy / mag
            if not self._free_dir(sx, sy):
                self.strafe = -self.strafe
                sx, sy = -uy * self.strafe, ux * self.strafe
                mag = math.hypot(sx, sy) or 1.0
                sx, sy = sx / mag, sy / mag
            if self._free_dir(sx, sy):
                c.mx, c.my = sx * 0.85, sy * 0.85
            # Quick direction swap on being hit
            if m.time - c.last_hit_t < 0.15 and self.rng.random() < d["tactics"]:
                self.strafe = -self.strafe
                self.strafe_t = self.rng.uniform(0.3, 0.7)
        if c.weapon.reloading and d["cover"] > 0.3 and self.rng.random() < d["cover"]:
            cover = self._find_cover((t.x, t.y))
            if cover:
                self.goto(cover)

    def _objective_move(self, task, dt):
        c, m = self.c, self.m
        dest, radius = self._destination(task)
        dd = dist(c.x, c.y, *dest)
        arrive = max(radius if task.interact else radius * 0.6, 12.0)
        self.at_goal = dd <= arrive + 30
        if dd > arrive:
            self.hold_pt = None
            self.goto(dest)
            if dd > 450 and not self.visible:
                c.sprint = True
            return
        if task.interact and dest == task.pos:
            c.interact = True
            ax, ay = task.pos[0] - c.x, task.pos[1] - c.y
            return
        if self.hold_pt is None or self.hold_t <= 0:
            self.hold_t = self.rng.uniform(4.0, 8.0)
            self.hold_pt = m.map.random_floor_near(dest[0], dest[1], max(radius, 60.0), self.rng)
        if dist(c.x, c.y, *self.hold_pt) > 18:
            self.goto(self.hold_pt)
        if c.role == "sniper":
            c.ads = True

    def _reload_logic(self):
        c, d = self.c, self.d
        w = c.weapon
        other = c.weapons[1 - c.cur]
        if w.mag == 0 and not w.reloading:
            dd = getattr(c, "aim_dist", 999.0)
            if self.target is not None and other.mag > 0 and dd < 450 and self.rng.random() < d["tactics"] + 0.3:
                c.swap_to = 1 - c.cur
            else:
                c.want_reload = True
        elif self.target is None:
            if w.mag < w.s["mag"] * 0.5 and w.reserve > 0:
                c.want_reload = True
            elif c.cur == 1 and c.weapons[0].mag > 0:
                c.swap_to = 0

    def _use_ability(self, task, invest):
        c, m, d = self.c, self.m, self.d
        if c.ability_cd > 0 or self.rng.random() > d["ability"]:
            return
        ab = c.char["ability"]["id"]
        tgt = self.target
        do = False
        if ab == "sprint":
            do = (self.state == "objective" and dist(c.x, c.y, *task.pos) > 600 and tgt is None) or \
                 (self.state == "retreat")
        elif ab == "reveal":
            do = self.state == "investigate" or (self.state == "objective" and dist(c.x, c.y, *task.pos) < 600
                                                 and self.rng.random() < 0.35)
        elif ab == "heal":
            do = any(a.hp < a.maxhp * 0.65 and dist(a.x, a.y, c.x, c.y) < 140 for a in m.allies_alive(c)) or \
                 c.hp < c.maxhp * 0.5
        elif ab == "barrier":
            do = tgt is not None and dist(c.x, c.y, tgt.x, tgt.y) < 450 and c.hp < c.maxhp * 0.75
        elif ab == "grenade":
            do = tgt is not None and 120 < dist(c.x, c.y, tgt.x, tgt.y) < 400 and self.react_t <= 0
        elif ab == "ammo":
            do = tgt is None and (c.weapon.reserve < c.weapon.s["reserve"] * 0.4 or
                                  any(w.reserve < w.s["reserve"] * 0.3 for a in m.allies_alive(c)
                                      if dist(a.x, a.y, c.x, c.y) < 130 for w in a.weapons))
        elif ab == "steady":
            do = tgt is not None and dist(c.x, c.y, tgt.x, tgt.y) > 300
        elif ab == "cloak":
            do = (self.state == "investigate") or (tgt is not None and c.hp < c.maxhp * 0.6) or \
                 (self.state == "objective" and 150 < dist(c.x, c.y, *task.pos) < 500 and self.rng.random() < 0.3)
        if do:
            abilities.activate(m, c)
