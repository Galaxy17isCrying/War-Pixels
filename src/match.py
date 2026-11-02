import math
import random
import zlib
from typing import List, Optional

from . import abilities
from .ai import BotBrain
from .config import BODY_RADIUS, BOT_NAMES, TILE, character, characters, weapon_list, weapons
from .difficulty import DIFFICULTIES
from .entities import BASE_SPEED, Bullet, Combatant, Effect
from .gamemap import load_map
from .modes import MODES
from .vision import can_see
from .weapons import damage_at_range

TEAM_SIZE = 10
GROUND_WAR_TEAM_SIZE = 50


def bot_loadout(char: dict, rng: random.Random):
    cat = rng.choice(char["prefs"])
    primary = rng.choice([w for w in weapon_list() if w["cat"] == cat])["id"]
    secondary = rng.choice([w for w in weapon_list() if w["cat"] == "PISTOL"])["id"]
    return primary, secondary, rng.choice(["none", "none", "armor", "ammo", "boots"])


class Match:
    def __init__(self, map_id: str, mode_id: str, difficulty: str = "NORMAL", player: Optional[dict] = None,
                 seed: Optional[int] = None, all_bots: bool = False, practice_bots: int = 0, team_size: int = 10,
                 online_players=None, local_player_id=None):
        self.rng = random.Random(seed)
        self.map = load_map(map_id)
        self.diff_name = difficulty
        self.diff = DIFFICULTIES[difficulty]
        self.time = 0.0
        self.combatants: List[Combatant] = []
        self.bullets: List[Bullet] = []
        self.grenades = []
        self.fx: List[Effect] = []
        self.killfeed = []
        self.events = []
        self.sounds = []
        self.announcements = []
        self.team_known = {0: {}, 1: {}}
        self.visible = {0: {}, 1: {}}
        self.path_budget = 4
        self.vision_t = 0.0
        self.stuck_events = 0
        self.practice = mode_id == "practice"
        self.player: Optional[Combatant] = None
        self.online_players = {}
        player = player or dict(char="vanguard", primary="vanguard", secondary="p9", equipment="none", name="YOU")
        self._next_id = 0
        if self.practice:
            self._build_practice(player, practice_bots)
        else:
            self._build_teams(player, all_bots, team_size, online_players, local_player_id)
        self.mode = MODES[mode_id](self)
        self.mode.start()

    def _new_id(self):
        self._next_id += 1
        return self._next_id - 1

    def _add_bot(self, team: int, name: str):
        char = self.rng.choice(characters())
        primary, secondary, equip = bot_loadout(char, self.rng)
        c = Combatant(self._new_id(), name, team, char["id"], primary, secondary, equip, is_bot=True)
        c.brain = BotBrain(c, self)
        self.combatants.append(c)
        return c

    def _build_teams(self, player: dict, all_bots: bool, selected_team_size: int = 10,
                     online_players=None, local_player_id=None):
        team_size = GROUND_WAR_TEAM_SIZE if self.map.id == "ground_war" else max(5, min(10, int(selected_team_size)))
        online_by_team = {item["team"]: item for item in online_players or ()}
        needed = (team_size * 2 - len(online_by_team)) if online_by_team else (team_size - (0 if all_bots else 1)) + team_size
        if needed <= len(BOT_NAMES):
            names = self.rng.sample(BOT_NAMES, needed)
        else:
            names = [f"{BOT_NAMES[i % len(BOT_NAMES)]}-{i // len(BOT_NAMES) + 1}" for i in range(needed)]
            self.rng.shuffle(names)
        for team in (0, 1):
            for i in range(team_size):
                if online_by_team and i == 0 and team in online_by_team:
                    remote = online_by_team[team]
                    c = Combatant(self._new_id(), remote["name"], team, remote["char"], remote["primary"],
                                  remote["secondary"], remote.get("equipment", "none"), is_bot=False)
                    self.online_players[remote["player_id"]] = c
                    if remote["player_id"] == local_player_id:
                        self.player = c
                    self.combatants.append(c)
                elif not online_by_team and team == 0 and i == 0 and not all_bots:
                    c = Combatant(self._new_id(), player.get("name", "YOU"), 0, player["char"], player["primary"],
                                  player["secondary"], player.get("equipment", "none"), is_bot=False)
                    self.player = c
                    self.combatants.append(c)
                else:
                    self._add_bot(team, names.pop())

    def _build_practice(self, player: dict, n_bots: int):
        c = Combatant(self._new_id(), player.get("name", "YOU"), 0, player["char"], player["primary"], player["secondary"],
                      player.get("equipment", "none"), is_bot=False)
        self.player = c
        self.combatants.append(c)
        for i, pos in enumerate(self.map.targets + self.map.movers):
            t = Combatant(self._new_id(), f"TARGET {i + 1}", 1, "vanguard", "p9", "p9", is_bot=False)
            t.is_target = True
            t.maxhp = 100
            t.home = pos
            if pos in self.map.movers:
                t.patrol = (pos[1], 0.6 + 0.1 * i, 120.0)
            self.combatants.append(t)
        for i in range(n_bots):
            self._add_bot(1, f"SPARRING {i + 1}")

    def announce(self, text: str):
        self.announcements.append((self.time, text))
        if len(self.announcements) > 12:
            self.announcements.pop(0)

    def sound(self, name, x, y):
        if len(self.sounds) < 48:
            self.sounds.append((name, x, y))

    def enemies_alive(self, team):
        return [e for e in self.combatants if e.alive and e.team != team]

    def allies_alive(self, c):
        return [a for a in self.combatants if a.alive and a.team == c.team and a is not c]

    def spawn(self, c: Combatant, full: bool = False):
        if c.is_target:
            c.x, c.y = c.home
        else:
            pts = list(self.map.spawns[c.team])
            self.rng.shuffle(pts)
            pos = None
            for p in pts:
                if all(not o.alive or math.hypot(o.x - p[0], o.y - p[1]) > 26 for o in self.combatants if o is not c):
                    pos = p
                    break
            if pos is None:
                pos = self.map.random_floor_near(pts[0][0], pts[0][1], 80, self.rng)
            c.x, c.y = pos
        c.hp = float(c.maxhp)
        c.alive = True
        c.invuln = 0.0 if c.is_target else 1.5
        c.vx = c.vy = c.mx = c.my = 0.0
        c.aim = 0.0 if c.team == 0 else math.pi
        c.cur = 0
        c.carry = None
        c.sprint_t = c.steady_t = c.cloak_t = 0.0
        c.ability_cd = min(c.ability_cd, 6.0) if not full else 0.0
        c.revealed_until = {0: 0.0, 1: 0.0}
        c.respawn_t = 0.0
        c.awaiting_loadout = False
        c.trigger = c.trigger_prev = False
        c.full_resupply()
        c.spawn_count += 1
        if c.brain:
            c.brain.reset()

    def respawn_blocked(self, c):
        return False

    def emit_noise(self, x, y, radius, team):
        for b in self.combatants:
            if b.alive and b.brain and b.team != team and math.hypot(b.x - x, b.y - y) < radius:
                b.brain.hear(x, y)

    def damage(self, victim: Combatant, amount: float, attacker: Optional[Combatant], wid: str, headshot=False, bullet=True):
        if not victim.alive or victim.invuln > 0 or victim.immortal or self.mode.over:
            return
        if attacker is not None and attacker.team == victim.team and not self.practice:
            return
        victim.hp -= amount
        victim.last_attacker = attacker
        victim.last_hit_t = self.time
        if attacker is not None:
            attacker.stats["damage"] += amount
            attacker.streak_score = getattr(attacker, "streak_score", 0) + max(5, int(amount * 0.15))
            if bullet:
                attacker.stats["hits"] += 1
                if headshot:
                    attacker.stats["headshots"] += 1
        if victim is self.player and attacker is not None:
            self.events.append(("damaged", math.atan2(attacker.y - victim.y, attacker.x - victim.x), amount))
        if attacker is self.player:
            self.events.append(("hit", headshot, victim.hp <= 0))
            self.sound("hitmarker", victim.x, victim.y)
        self.fx.append(Effect("blood", victim.x, victim.y, 0, 0, 0.3))
        if victim.hp <= 0:
            self.kill(victim, attacker, wid, headshot)

    def kill(self, victim: Combatant, attacker: Optional[Combatant], wid: str, headshot: bool,
             award_streak: bool = True):
        victim.alive = False
        victim.hp = 0
        victim.stats["deaths"] += 1
        victim.kill_streak = 0
        victim.streak_score = 0
        victim.nuke_charges = 0
        victim.trigger = False
        victim.respawn_t = self.mode.respawn_delay or 0.0
        victim.awaiting_loadout = victim is self.player and victim.respawn_t > 0 and not self.online_players
        if attacker is not None and attacker is not victim:
            attacker.stats["kills"] += 1
            wk = attacker.stats["weapon_kills"]
            wk[wid] = wk.get(wid, 0) + 1
            if award_streak:
                attacker.kill_streak += 1
                attacker.streak_score = getattr(attacker, "streak_score", 0) + (125 if headshot else 100)
                if attacker.kill_streak % 20 == 0:
                    attacker.nuke_charges += 1
                    self.announce(f"{attacker.name.upper()} EARNED A NUKE")
                    if attacker is self.player:
                        self.events.append(("nuke_ready", attacker.nuke_charges))
        self.killfeed.append(dict(t=self.time, attacker=attacker.name if attacker else "BOMB",
                                  a_team=attacker.team if attacker else -1, weapon=weapons().get(wid, {}).get("name", wid.upper()),
                                  victim=victim.name, v_team=victim.team, hs=headshot))
        self.fx.append(Effect("death", victim.x, victim.y, 0, 0, 0.8))
        if attacker is not None and wid in getattr(attacker, "kill_effect_weapons", set()):
            spec = weapons().get(wid, {})
            skin = getattr(attacker, "equipped_skins", {}).get(wid, {})
            effect_id = skin.get("effect_id") if skin.get("kill_effect") else None
            if effect_id:
                effect = f"skin_{effect_id}_death"
                variant = zlib.crc32(effect_id.encode("utf-8"))
            else:
                effect = {
                "dragon": "dragon_death",
                "supernova": "supernova_death",
                "void_rift": "void_rift_death",
                "comet": "comet_death",
                "ice_shatter": "ice_shatter_death",
                }.get(spec.get("kill_effect"), "legendary_death")
            life = {"dragon_death": 2.6, "supernova_death": 2.4, "void_rift_death": 2.1,
                    "comet_death": 1.8, "ice_shatter_death": 1.6}.get(effect, 2.0 if effect_id else 0.9)
            skin_colors = {
                "astral_sovereign": (95, 205, 255), "infernal_wyrm": (255, 100, 50),
                "prismatic_tempest": (215, 120, 255), "frostbound_nova": (150, 225, 255),
                "void_reaver": (145, 80, 220), "solar_devourer": (255, 190, 65),
                "verdant_leviathan": (95, 220, 135), "quantum_phantom": (90, 245, 235),
                "eclipse_engine": (190, 155, 255), "starlight_armada": (255, 230, 145),
            }
            if effect_id:
                effect_theme = effect_id.split("__", 1)[0]
                color = skin_colors.get(effect_theme, (255, 170, 40))
                shift = ((variant >> 8) % 61) - 30
                color = (max(0, min(255, color[0] + shift)),
                         max(0, min(255, color[1] + ((variant >> 16) % 61) - 30)),
                         max(0, min(255, color[2] + ((variant >> 24) % 61) - 30)))
                life = 1.8 + (variant % 41) / 100
                radius = 38 + (variant % 17)
            else:
                color = (255, 170, 40)
                radius = 42
            self.fx.append(Effect(effect, victim.x, victim.y, radius, 0, life, color))
        self.sound("death", victim.x, victim.y)
        if victim is self.player:
            self.events.append(("died", attacker.name if attacker else ""))
        self.mode.on_death(victim, attacker)

    def call_nuke(self, caller: Combatant) -> bool:
        if self.mode.over or not caller.alive or caller.nuke_charges <= 0:
            return False
        enemies = [e for e in self.combatants if e.alive and e.team != caller.team]
        if not enemies:
            return False
        caller.nuke_charges -= 1
        self.announce(f"{caller.name.upper()} CALLED IN A NUKE")
        self.fx.append(Effect("explosion", self.map.px_w / 2, self.map.px_h / 2,
                              max(self.map.px_w, self.map.px_h), 0, 1.5))
        self.sound("explosion", self.map.px_w / 2, self.map.px_h / 2)
        self.events.append(("shake", 12.0))
        for enemy in enemies:
            self.kill(enemy, caller, "nuke", False, award_streak=False)
        return True

    def explosion(self, x, y, radius, dmg, owner, mult, big=False, wid="frag"):
        self.fx.append(Effect("explosion", x, y, radius, 0, 0.5))
        self.sound("explosion", x, y)
        if self.player:
            d = math.hypot(self.player.x - x, self.player.y - y)
            if d < 500:
                self.events.append(("shake", 6.0 * (1 - d / 500)))
        for e in self.combatants:
            if not e.alive or (owner and e.team == owner.team):
                continue
            d = math.hypot(e.x - x, e.y - y)
            if d < radius and self.map.los(x, y, e.x, e.y):
                self.damage(e, dmg * mult * (1 - 0.7 * d / radius), owner, wid, False, bullet=False)

    def _fire(self, c: Combatant):
        w = c.weapon
        speed_frac = min(1.0, math.hypot(c.vx, c.vy) / (BASE_SPEED * c.speed_mult))
        offs = w.fire(self.rng, c.ads, speed_frac, c.mods.get("still", 1.0), c.steady_t > 0)
        if offs is None:
            return
        if w.s["cat"] == "MELEE":
            for offset in offs:
                angle = c.aim + offset
                targets = []
                for target in self.combatants:
                    if not target.alive or target.team == c.team:
                        continue
                    dx, dy = target.x - c.x, target.y - c.y
                    distance = math.hypot(dx, dy)
                    delta = (math.atan2(dy, dx) - angle + math.pi) % (2 * math.pi) - math.pi
                    if distance <= w.s["range"] and abs(delta) <= 0.55 and self.map.los(c.x, c.y, target.x, target.y):
                        targets.append((distance, target))
                if targets:
                    _, target = min(targets, key=lambda item: item[0])
                    self.damage(target, w.s["dmg"], c, w.s["id"], False)
            self.fx.append(Effect("slash", c.x, c.y, c.aim, w.s["range"], 0.16))
        else:
            for o in offs:
                self.bullets.append(Bullet(c.x, c.y, c.aim + o, w.s, c))
        c.stats["shots"] += len(offs)
        self.fx.append(Effect("muzzle", c.x + math.cos(c.aim) * 18, c.y + math.sin(c.aim) * 18, c.aim, 0, 0.06))
        if w.s["cat"] not in ("SG", "MELEE"):
            self.fx.append(Effect("casing", c.x, c.y, c.aim + math.pi / 2, self.rng.uniform(40, 90), 0.7))
        self.sound("shot_" + w.s["cat"], c.x, c.y)
        self.emit_noise(c.x, c.y, w.s["noise"] * c.mods.get("noise", 1.0), c.team)
        if c is self.player:
            self.events.append(("shake", 1.2 + w.s["vrec"] * 0.5))

    def _step_bullets(self, dt):
        alive = [e for e in self.combatants if e.alive and e.invuln <= 0 and not e.immortal]
        R = BODY_RADIUS
        for b in self.bullets:
            step = min(b.speed * dt, b.max_dist - b.traveled)
            x1, y1 = b.x + b.dx * step, b.y + b.dy * step
            tw = self.map.raycast(b.x, b.y, x1, y1)
            best, hit, off = (tw if tw is not None else 2.0), None, 0.0
            for e in alive:
                if e.team == b.owner.team:
                    continue
                vx, vy = e.x - b.x, e.y - b.y
                t = vx * b.dx + vy * b.dy
                if t < -R or t > step + R:
                    continue
                tc = min(max(t, 0.0), step)
                px, py = b.x + b.dx * tc, b.y + b.dy * tc
                if (e.x - px) ** 2 + (e.y - py) ** 2 <= R * R:
                    frac = tc / step if step > 0 else 0.0
                    if frac < best:
                        best, hit = frac, e
                        off = abs(vx * b.dy - vy * b.dx) / R
            if hit is not None:
                dist = b.traveled + best * step
                spec = b.spec
                ix, iy = b.x + b.dx * best * step, b.y + b.dy * best * step
                if spec["cat"] == "EXPLOSIVE":
                    self.explosion(ix, iy, spec["blast_radius"], spec["blast_damage"], b.owner, 1.0,
                                   wid=b.wid)
                else:
                    mult, hs = (spec["hs"], True) if off < 0.16 else (spec.get("limb", 0.75), False) if off > 0.8 else (1.0, False)
                    self.damage(hit, damage_at_range(spec, dist) * mult, b.owner, b.wid, hs)
                b.alive = False
            elif tw is not None:
                ix, iy = b.x + (x1 - b.x) * tw, b.y + (y1 - b.y) * tw
                if b.spec["cat"] == "EXPLOSIVE":
                    self.explosion(ix, iy, b.spec["blast_radius"], b.spec["blast_damage"], b.owner, 1.0,
                                   wid=b.wid)
                else:
                    self.fx.append(Effect("spark", ix, iy, math.atan2(-b.dy, -b.dx), 0, 0.25))
                b.alive = False
            else:
                b.x, b.y = x1, y1
                b.traveled += step
                if b.traveled >= b.max_dist:
                    b.alive = False
        self.bullets = [b for b in self.bullets if b.alive]

    def _step_grenades(self, dt):
        for g in self.grenades:
            nx, ny = g.x + g.vx * dt, g.y + g.vy * dt
            if self.map.raycast(g.x, g.y, nx, ny) is not None:
                g.vx = g.vy = 0.0
            else:
                g.x, g.y = nx, ny
            g.fuse -= dt
            if g.fuse <= 0:
                self.explosion(g.x, g.y, 95, 85, g.owner, g.mult)
                g.alive = False
        self.grenades = [g for g in self.grenades if g.alive]

    def _move(self, c: Combatant, dt: float):
        if dt <= 0:
            c.vx = c.vy = 0.0
            return
        ox, oy = c.x, c.y
        mag = math.hypot(c.mx, c.my)
        if mag > 0.01:
            speed = c.speed_now() * min(1.0, mag) / mag
            dist = speed * dt
            r = BODY_RADIUS
            steps = max(1, int(math.ceil(dist / 4.0)))
            step_dist = dist / steps
            dir_x, dir_y = c.mx / mag, c.my / mag

            for _ in range(steps):
                step_x = dir_x * step_dist
                step_y = dir_y * step_dist

                nx = c.x + step_x
                ny = c.y + step_y
                if not self.map.blocked(nx, ny, r):
                    c.x, c.y = nx, ny
                    continue

                if step_x != 0 and not self.map.blocked(c.x + step_x, c.y, r):
                    c.x += step_x

                if step_y != 0 and not self.map.blocked(c.x, c.y + step_y, r):
                    c.y += step_y

        c.vx, c.vy = (c.x - ox) / dt, (c.y - oy) / dt

    def _separate(self):
        live = [c for c in self.combatants if c.alive and not c.is_target]
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                d2 = dx * dx + dy * dy
                if 0 < d2 < 576:
                    d = math.sqrt(d2)
                    push = (24 - d) * 0.25
                    ux, uy = dx / d, dy / d
                    for o, sgn in ((a, -1), (b, 1)):
                        nx, ny = o.x + ux * push * sgn, o.y + uy * push * sgn
                        if not self.map.blocked(nx, ny, BODY_RADIUS):
                            o.x, o.y = nx, ny

    def _step_combatant(self, c: Combatant, dt: float):
        c.invuln = max(0.0, c.invuln - dt)
        c.ability_cd = max(0.0, c.ability_cd - dt)
        c.sprint_t = max(0.0, c.sprint_t - dt)
        c.steady_t = max(0.0, c.steady_t - dt)
        c.cloak_t = max(0.0, c.cloak_t - dt)
        if c.is_target:
            if c.patrol:
                base_y, speed, amp = c.patrol
                ny = base_y + math.sin(self.time * speed) * amp
                c.vy = (ny - c.y) / dt
                c.y = ny
            return
        for i, w in enumerate(c.weapons):
            w.update(dt)
            if i != c.cur and w.reload_t > 0:
                w.reload_t = 0.0
        c.swap_t -= dt
        if self.mode.frozen:
            c.vx = c.vy = 0.0
            return
        if c.swap_to is not None:
            if c.swap_to != c.cur and 0 <= c.swap_to < len(c.weapons):
                c.cur = c.swap_to
                c.swap_t = c.weapon.s["swap"] * c.mods.get("swap", 1.0)
                c.weapon.cooldown = max(c.weapon.cooldown, c.swap_t)
                c.weapon.reload_t = 0.0
            c.swap_to = None
        if c.want_ability:
            abilities.activate(self, c)
            c.want_ability = False
        w = c.weapon
        if c.want_reload:
            w.start_reload()
            c.want_reload = False
        if c.sprint:
            c.ads = False
        if c.trigger and c.swap_t <= 0:
            if w.mag == 0:
                w.start_reload()
            elif w.ready() and (w.s["auto"] or c.is_bot or not c.trigger_prev):
                self._fire(c)
        c.trigger_prev = c.trigger
        self._move(c, dt)

    def is_visible_to(self, team: int, e: Combatant) -> bool:
        return e.team == team or e.is_target or self.visible[team].get(e.id, 0.0) > self.time

    def _update_vision(self):
        now = self.time
        base = self.diff["view"]
        live = [c for c in self.combatants if c.alive and not c.is_target]
        for a in live:
            seen = []
            for e in live:
                if e.team == a.team:
                    continue
                if can_see(self, a, e, base):
                    seen.append(e)
                    self.visible[a.team][e.id] = now + 0.35
                    self.team_known[a.team][e.id] = (e.x, e.y, now)
            if a.brain:
                a.brain.visible = seen
        for e in live:
            for t in (0, 1):
                if t != e.team and e.revealed_until[t] > now:
                    self.visible[t][e.id] = now + 0.35
                    self.team_known[t][e.id] = (e.x, e.y, now)

    def update(self, dt: float):
        dt = min(dt, 0.05)
        self.time += dt
        self.path_budget = 4
        self.map.tick(self.time)
        self.mode.update(dt)
        self.vision_t -= dt
        if self.vision_t <= 0:
            self.vision_t = 0.1
            self._update_vision()
        for c in self.combatants:
            if c.alive:
                if c.brain:
                    c.brain.think(dt)
                self._step_combatant(c, dt)
            elif c.respawn_t > 0:
                c.respawn_t -= dt
                if c.respawn_t <= 0 and not c.awaiting_loadout:
                    self.spawn(c)
        self._separate()
        self._step_bullets(dt)
        self._step_grenades(dt)
        for e in self.fx:
            e.ttl -= dt
        self.fx = [e for e in self.fx if e.ttl > 0]
        if len(self.killfeed) > 40:
            del self.killfeed[:-20]

    # practice helpers
    def toggle_practice_bots(self, n=3):
        bots = [c for c in self.combatants if c.brain]
        if bots:
            for b in bots:
                self.combatants.remove(b)
        else:
            for i in range(n):
                b = self._add_bot(1, f"SPARRING {i + 1}")
                self.spawn(b)
