import math
import random

import pygame

from . import gfx
from .campaign import CAMPAIGN_MISSIONS, campaign_mission
from .config import CANVAS_H, CANVAS_W, CATEGORY_ORDER, TILE, weapon_list, weapons
from .gfx import AMBER, CYAN, GRAY, RED, WHITE, bar, panel, text
from .match import Match
from .render import CX, CY, Renderer
from .save import DEFAULT_KEYS
from .scenes import (HUD_CONTROL_LABELS, HUD_CONTROL_RADII, CampaignScene, HudEditorScene, Menu, Scene)
from .weapons import WeaponState, aim_assist_angle


class MatchScene(Scene):
    def __init__(self, app, mode_id, map_id, ranked=False, campaign_index=None, team_size=5,
                 online_client=None, online_match=None):
        super().__init__(app)
        app.audio.start_music("battle")
        s = app.settings
        lo = s["loadout"]
        self.mode_id, self.map_id = mode_id, map_id
        self.ranked = ranked
        self.team_size = team_size
        self.campaign_index = campaign_index
        self.online_client = online_client
        self.online_match = online_match
        self.online_edges = {"reload": False, "ability": False, "swap_to": None}
        self.last_online_tick = -1
        self.practice = mode_id == "practice"
        player = dict(char=lo["char"], primary=lo["primary"], secondary=lo["secondary"], equipment=lo["equipment"],
                      name=app.stats.player_name())
        match_options = {}
        if online_match is not None:
            player_roster = online_match["players"]
            if len(player_roster) != 2 or {entry["team"] for entry in player_roster} != {0, 1}:
                raise ValueError("The matchmaking server returned an invalid player roster.")
            match_options = dict(seed=online_match["seed"], online_players=player_roster,
                                 local_player_id=online_client.player_id)
        difficulty = "NORMAL" if online_match is not None else s["difficulty"]
        self.m = Match(map_id, mode_id, difficulty, player, team_size=team_size, **match_options)
        if online_match is not None and self.m.player is None:
            raise ValueError("The matchmaking server did not include this player.")
        self.m.player.kill_effect_weapons = app.stats.kill_effect_weapon_ids()
        self.m.player.equipped_skins = app.stats.equipped_skins()
        self.r = Renderer(self.m, s)
        self.r.scene = self
        self.keys = {}
        for act, name in s["keys"].items():
            try:
                self.keys[act] = pygame.key.key_code(name)
            except ValueError:
                self.keys[act] = pygame.key.key_code(DEFAULT_KEYS[act])
        p = self.m.player
        self.cam = [p.x, p.y]
        self.cursor = [CX + 140.0, CY]
        self.shake = 0.0
        self.hit_t = 0.0
        self.hit_kill = False
        self.indicators = []
        self.chat_open = False
        self.chat_input = ""
        self.chat_message = ""
        self.chat_message_t = 0.0
        self.unlimited_ammo = False
        self.respawn_slot = 0
        self.respawn_primary = lo["primary"]
        self.respawn_secondary = lo["secondary"]
        self.paused = False
        self.end_t = 0.0
        self.recorded = False
        self.result = None
        self.last_hit = "-"
        self.compare = False
        self.scorestreaks = list(lo.get("scorestreaks", ["uav", "hunter_killer", "shield_turret"]))[:3]
        while len(self.scorestreaks) < 3:
            self.scorestreaks.append("uav")
        self.streak_message = ""
        self.streak_message_t = 0.0
        self.streak_ready_seen = [False, False, False]
        self.streak_rects = []
        self.touch_fingers = {}
        self.pw_list = weapon_list()
        self.pw = next((i for i, w in enumerate(self.pw_list) if w["id"] == lo["primary"]), 0)
        self.prev_spec = self.pw_list[self.pw]
        pause_items = ([("RESUME", self.resume), ("QUIT TO MENU", self.to_menu)] if self.online_client else
                       [("RESUME", self.resume), ("CUSTOMIZE HUD", self.open_hud_editor),
                        ("SETTINGS", self.open_settings), ("QUIT TO MENU", self.to_menu)])
        self.pause_menu = Menu(app, pause_items, CX - 190, 250, 380)
        end_items = ([("CAMPAIGN MAP", self.open_campaign), ("REPLAY MISSION", self.rematch),
                      ("MAIN MENU", self.to_menu)] if campaign_index is not None else
                     [("MAIN MENU", self.to_menu)] if self.online_client else
                     [("REMATCH", self.rematch), ("MAIN MENU", self.to_menu)])
        self.end_menu = Menu(app, end_items, CX - 190, 470, 380)
        self.grab(True)

    # ---------------------------------------------------------------- helpers
    def grab(self, on):
        try:
            pygame.event.set_grab(on)
            pygame.mouse.set_visible(not on)
        except pygame.error:
            pass

    def on_enter(self):
        self.grab(not self.paused and not self.m.mode.over)

    def resume(self):
        self.paused = False
        self.grab(True)

    def open_settings(self):
        from .scenes import SettingsScene
        self.grab(False)
        self.app.push(SettingsScene(self.app))

    def open_hud_editor(self):
        self.grab(False)
        self.app.push(HudEditorScene(self.app))

    def to_menu(self):
        if self.online_client:
            self.online_client.close()
            self.online_client = None
        self.grab(False)
        self.app.reset_to_menu()

    def rematch(self):
        self.grab(False)
        self.app.replace(MatchScene(self.app, self.mode_id, self.map_id, self.ranked, self.campaign_index, self.team_size))

    def open_campaign(self):
        self.grab(False)
        self.app.push(CampaignScene(self.app))

    def current_player_target(self):
        p = self.m.player
        if p.alive:
            return p
        allies = [a for a in self.m.combatants if a.alive and a.team == p.team and not a.is_target]
        return allies[0] if allies else p

    # ----------------------------------------------------------------- input
    def event(self, e):
        p = self.m.player
        if e.type in (getattr(pygame, "FINGERDOWN", -1), getattr(pygame, "FINGERMOTION", -2),
                      getattr(pygame, "FINGERUP", -3)):
            self._touch_event(e)
            return
        if p.awaiting_loadout and not self.m.mode.over and e.type == pygame.KEYDOWN:
            if e.key == pygame.K_UP or e.key == pygame.K_DOWN:
                self.respawn_slot = 1 - self.respawn_slot
            elif e.key == pygame.K_LEFT:
                self._cycle_respawn_weapon(-1)
            elif e.key == pygame.K_RIGHT:
                self._cycle_respawn_weapon(1)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._confirm_respawn_loadout()
            return
        if self.chat_open and e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.chat_open = False
                self.chat_input = ""
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._run_cheat(self.chat_input)
                self.chat_input = ""
                self.chat_open = False
            elif e.key == pygame.K_BACKSPACE:
                self.chat_input = self.chat_input[:-1]
            else:
                char = getattr(e, "unicode", "")
                if char and char.isprintable() and len(self.chat_input) < 64:
                    self.chat_input += char
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE and not self.m.mode.over:
            self.paused = not self.paused
            self.grab(not self.paused)
            return
        if self.paused or (self.m.mode.over and self.end_t > 1.5):
            (self.pause_menu if self.paused else self.end_menu).event(e)
            return
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and not self.online_client:
            self.chat_open = True
            self.chat_input = ""
            return
        if e.type == pygame.MOUSEMOTION:
            sens = self.app.settings["mouse_sens"] * (self.app.settings["aim_sens"] if p.ads else 1.0)
            k = sens / self.app.scale
            self.cursor[0] = min(CANVAS_W - 1, max(0, self.cursor[0] + e.rel[0] * k))
            self.cursor[1] = min(CANVAS_H - 1, max(0, self.cursor[1] + e.rel[1] * k))
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not self.paused:
            pos = self.app.mouse()
            if getattr(self, "minimap_toggle_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                self.app.settings["minimap"] = not self.app.settings.get("minimap", True)
                self.app.settings.save()
                state = "ENABLED" if self.app.settings["minimap"] else "DISABLED"
                self.streak_message = f"MINIMAP: {state} ([M] TO TOGGLE)"
                self.streak_message_t = 2.0
                self.app.audio.play("click", 0.6)
                return
            if p.alive and not self.practice:
                for slot, rect in enumerate(getattr(self, "streak_rects", [])):
                    if rect.collidepoint(pos):
                        self.activate_scorestreak(slot)
                        return
        elif e.type == pygame.KEYDOWN and p.alive:
            k = self.keys
            if e.key in (pygame.K_m, k.get("tactical")):
                self.app.settings["minimap"] = not self.app.settings.get("minimap", True)
                self.app.settings.save()
                state = "ENABLED" if self.app.settings["minimap"] else "DISABLED"
                self.streak_message = f"MINIMAP: {state} ([M] TO TOGGLE)"
                self.streak_message_t = 2.0
                self.app.audio.play("click", 0.6)
            elif e.key == k["reload"]:
                p.want_reload = True
            elif e.key == k["ability"]:
                p.want_ability = True
            elif e.key == k["switch"]:
                p.swap_to = 1 - p.cur
            elif e.key == pygame.K_1:
                p.swap_to = 0
            elif e.key == pygame.K_2:
                p.swap_to = 1
            elif e.key in (pygame.K_4, pygame.K_5, pygame.K_6):
                slot = {pygame.K_4: 0, pygame.K_5: 1, pygame.K_6: 2}[e.key]
                if self.online_client:
                    self.chat_message = "SCORESTREAKS ARE DISABLED IN ONLINE MATCHES"
                    self.chat_message_t = 2.0
                else:
                    self.activate_scorestreak(slot)
        if e.type == pygame.KEYDOWN and self.practice:
            self._practice_key(e.key)

    def _touch_canvas_pos(self, event):
        window_w, window_h = self.app.window.get_size()
        return self.app.screen_to_canvas((event.x * window_w, event.y * window_h))

    def _touch_event(self, event):
        if self.paused or self.m.mode.over:
            return
        self.app.touch_enabled = True
        finger_id = event.finger_id
        if event.type == getattr(pygame, "FINGERDOWN", -1):
            pos = self._touch_canvas_pos(event)
            for name in reversed(tuple(HUD_CONTROL_RADII)):
                controls = self.app.settings["hud_controls"]
                center = (controls[name][0] * CANVAS_W, controls[name][1] * CANVAS_H)
                radius = HUD_CONTROL_RADII[name] * controls[name][2]
                if math.hypot(pos[0] - center[0], pos[1] - center[1]) <= radius:
                    self.touch_fingers[finger_id] = (name, pos)
                    if name == "reload":
                        self.m.player.want_reload = True
                    elif name == "ability":
                        self.m.player.want_ability = True
                    elif name == "switch":
                        self.m.player.swap_to = 1 - self.m.player.cur
                    return
            if pos[0] >= CANVAS_W * 0.4:
                self.touch_fingers[finger_id] = ("pointer", pos)
                self.cursor[:] = pos
        elif event.type == getattr(pygame, "FINGERMOTION", -2):
            current = self.touch_fingers.get(finger_id)
            if current is None:
                return
            name, _ = current
            pos = self._touch_canvas_pos(event)
            self.touch_fingers[finger_id] = (name, pos)
            if name == "pointer":
                self.cursor[:] = pos
        elif event.type == getattr(pygame, "FINGERUP", -3):
            self.touch_fingers.pop(finger_id, None)

    def activate_scorestreak(self, slot):
        if self.online_client:
            self.streak_message = "SCORESTREAKS ARE DISABLED IN ONLINE MATCHES"
            self.streak_message_t = 2.0
            return
        from .scorestreaks import SCORESTREAKS
        from .match import Effect
        if slot >= len(self.scorestreaks):
            return
        streak_id = self.scorestreaks[slot]
        item = next((x for x in SCORESTREAKS if x["id"] == streak_id), None)
        if item is None:
            self.streak_message = f"SLOT {slot + 1}: NO SCORESTREAK EQUIPPED"
            self.streak_message_t = 2.0
            return
        p = self.m.player
        req_score = item.get("points") or 500
        cur_score = getattr(p, "streak_score", 0)

        # In standard play require points; bypass in practice or when unlimited ammo cheat is on
        if not self.practice and not getattr(self, "unlimited_ammo", False) and cur_score < req_score:
            self.streak_message = f"{item['name'].upper()} LOCKED - NEED {req_score - cur_score} PTS"
            self.streak_message_t = 2.0
            self.app.audio.play("click", 0.4)
            return

        if not self.practice and not getattr(self, "unlimited_ammo", False):
            p.streak_score = max(0, cur_score - req_score)
            if hasattr(self, "streak_ready_seen") and slot < len(self.streak_ready_seen):
                self.streak_ready_seen[slot] = False

        self.streak_message = f"{item['name'].upper()} DEPLOYED!"
        self.streak_message_t = 3.0
        self.app.audio.play("click", 1.0)

        if streak_id in ("uav", "advanced_uav"):
            for e in self.m.combatants:
                if e.team != p.team:
                    e.revealed_until[p.team] = self.m.time + 18.0
            self.indicators = [(math.atan2(e.y - p.y, e.x - p.x), 1.0)
                               for e in self.m.combatants if e.team != p.team and e.alive]
            self.streak_message = "UAV RECON ONLINE: HOSTILES REVEALED"
        elif streak_id == "counter_uav":
            self.chat_message = "COUNTER-UAV DEPLOYED: ENEMY RADAR SCRAMBLED"
            self.chat_message_t = 3.0
        elif streak_id in ("hunter_killer", "bomb_drone", "swarm"):
            enemies = sorted([e for e in self.m.combatants if e.team != p.team and e.alive],
                             key=lambda e: math.hypot(e.x - p.x, e.y - p.y))
            if enemies:
                target = enemies[0]
                self.m.damage(target, 160, p, streak_id)
                self.m.fx.append(Effect("explosion", target.x, target.y, 45, 0, 0.6))
                self.streak_message = f"HUNTER KILLER ELIMINATED {target.name.upper()}!"
            else:
                self.streak_message = "HUNTER KILLER DEPLOYED: PATROLLING AIRSPACE"
        elif streak_id in ("predator_missile", "lightning_strike", "vtol", "gunship", "stealth_chopper", "napalm", "orbital_laser"):
            enemies = [e for e in self.m.combatants if e.team != p.team and e.alive]
            for target in enemies[:3]:
                self.m.damage(target, 220, p, streak_id)
                self.m.fx.append(Effect("explosion", target.x, target.y, 55, 0, 0.8))
            self.streak_message = f"AIR SUPPORT CONFIRMED: {min(len(enemies), 3)} TARGETS HIT"
        elif streak_id == "care_package":
            for w in p.weapons:
                w.reserve = int(w.s["reserve"] * p.ammo_mult)
            p.hp = min(p.maxhp, p.hp + 50)
            p.streak_score = getattr(p, "streak_score", 0) + 200
            self.streak_message = "CARE PACKAGE RECEIVED: RESUPPLY & BONUS 200 PTS"
        elif streak_id in ("shield_turret", "sentry_gun"):
            tx, ty = int(p.x // TILE), int(p.y // TILE)
            self.m.map.add_barrier(tx + 1, ty, self.m.time + 35.0)
            self.streak_message = f"{item['name'].upper()} FORTIFICATION DEPLOYED"
        elif streak_id == "emp_systems":
            self.chat_message = "EMP SYSTEMS ACTIVE: HOSTILE ELECTRONICS DISABLED"
            self.chat_message_t = 3.0

    def _run_cheat(self, command):
        if self.online_client:
            self.chat_message = "COMMANDS ARE DISABLED IN ONLINE MATCHES"
            self.chat_message_t = 3.0
            return
        p = self.m.player
        command = command.strip().lower()
        if not command:
            return
        if command in ("/unliamo", "/unlimitedammo"):
            self.unlimited_ammo = not self.unlimited_ammo
            for weapon in p.weapons:
                weapon.unlimited = self.unlimited_ammo
                if self.unlimited_ammo:
                    weapon.mag = weapon.s["mag"]
                    weapon.reserve = int(weapon.s["reserve"] * p.ammo_mult)
                    weapon.reload_t = 0.0
            self.chat_message = f"UNLIMITED AMMO {'ON' if self.unlimited_ammo else 'OFF'}"
        elif command == "/immortal":
            p.immortal = not p.immortal
            self.chat_message = f"IMMORTAL {'ON' if p.immortal else 'OFF'}"
        elif command == "/heal":
            if not p.alive:
                self.chat_message = "HEAL FAILED: YOU ARE ELIMINATED"
            else:
                p.hp = float(p.maxhp)
                p.full_resupply()
                self.chat_message = "HEALTH AND AMMO RESTORED"
        elif command == "/ability":
            p.ability_cd = 0.0
            self.chat_message = "ABILITY READY"
        elif command == "/nuke":
            if not p.alive:
                self.chat_message = "NUKE FAILED: YOU ARE ELIMINATED"
            elif p.nuke_charges <= 0:
                self.chat_message = f"NUKE LOCKED: {p.kill_streak}/20 KILLS"
            elif self.m.call_nuke(p):
                self.chat_message = "NUKE CALLED IN!"
            else:
                self.chat_message = "NUKE FAILED: NO ENEMIES LEFT"
        elif command in ("/admin unlock legendary", "/admin unlock all legendary"):
            ids = self.app.stats.grant_legendary_armory()
            self.chat_message = f"LOCAL ADMIN: LEGENDARY ARMORY UNLOCKED ({len(ids)} WEAPONS)"
        elif command == "/admin unlock all":
            ids = self.app.stats.unlock_all_weapons()
            self.chat_message = f"LOCAL ADMIN: ALL WEAPONS UNLOCKED ({len(ids)})"
        elif command == "/admin unlock frames":
            ids = self.app.stats.grant_all_avatar_frames()
            self.chat_message = f"LOCAL ADMIN: ALL AVATAR FRAMES UNLOCKED ({len(ids)})"
        elif command.startswith("/admin coins "):
            try:
                amount = int(command.removeprefix("/admin coins ").replace(",", "").strip())
                total = self.app.stats.grant_coins(amount)
                self.chat_message = f"LOCAL ADMIN: GRANTED {amount:,} COINS ({total:,} TOTAL)"
            except ValueError:
                self.chat_message = "INVALID COIN AMOUNT"
        elif command.startswith("/admin rank "):
            try:
                points = int(command.removeprefix("/admin rank ").replace(",", "").strip())
                rank = self.app.stats.set_rank_points(points)
                self.chat_message = f"LOCAL ADMIN: RANK SET TO {rank['tier'].upper()} ({rank['points']:,} RP)"
            except ValueError:
                self.chat_message = "INVALID RANK POINTS"
        elif command.startswith("/admin unlock "):
            weapon_id = command.removeprefix("/admin unlock ").strip()
            if self.app.stats.unlock_weapon(weapon_id):
                self.chat_message = f"LOCAL ADMIN: UNLOCKED {weapons()[weapon_id]['name']}"
            else:
                self.chat_message = f"UNKNOWN WEAPON ID: {weapon_id}"
        elif command == "/help":
            self.chat_message = "/unliamo /immortal /heal /ability /nuke /admin rank <points> /admin coins <amount>"
        else:
            self.chat_message = f"UNKNOWN COMMAND: {command} (TYPE /HELP)"
        self.chat_message_t = 4.0

    def _practice_key(self, key):
        p = self.m.player
        if key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
            self.prev_spec = self.pw_list[self.pw]
            self.pw = (self.pw + (1 if key == pygame.K_RIGHTBRACKET else -1)) % len(self.pw_list)
            p.weapons[0] = WeaponState(self.pw_list[self.pw], p.ammo_mult, p.weapon.recoil_scale)
            p.weapons[0].unlimited = self.unlimited_ammo
            p.cur = 0
        elif key == pygame.K_b:
            self.m.toggle_practice_bots(3)
        elif key == pygame.K_c:
            self.compare = not self.compare
        elif key == pygame.K_t:
            for k in ("shots", "hits", "headshots", "damage"):
                p.stats[k] = 0

    def _apply_input(self, dt):
        p = self.m.player
        keys = pygame.key.get_pressed()
        k = self.keys
        if p.alive and not self.paused and not self.chat_open:
            p.mx = float(keys[k["right"]]) - float(keys[k["left"]])
            p.my = float(keys[k["down"]]) - float(keys[k["up"]])
            # Normalize diagonal movement so moving at 45° doesn't give a speed boost
            _mag = math.hypot(p.mx, p.my)
            if _mag > 1.0:
                p.mx /= _mag
                p.my /= _mag
            b = pygame.mouse.get_pressed()
            p.trigger = bool(b[0])
            p.ads = bool(b[2]) and not keys[k["sprint"]]
            p.sprint = bool(keys[k["sprint"]])
            p.interact = bool(keys[k["interact"]])
            ps = (p.x - self.cam[0] + CX, p.y - self.cam[1] + CY)
            fingers = [control for control, _ in self.touch_fingers.values()]
            if "move" in fingers:
                control = self.app.settings["hud_controls"]["move"]
                center = (control[0] * CANVAS_W, control[1] * CANVAS_H)
                pos = next(pos for name, pos in self.touch_fingers.values() if name == "move")
                radius = max(1.0, HUD_CONTROL_RADII["move"] * control[2])
                p.mx = max(-1.0, min(1.0, (pos[0] - center[0]) / radius))
                p.my = max(-1.0, min(1.0, (pos[1] - center[1]) / radius))
            aim_pos = next((pos for name, pos in self.touch_fingers.values() if name == "aim"), None)
            if aim_pos is not None:
                control = self.app.settings["hud_controls"]["aim"]
                center = (control[0] * CANVAS_W, control[1] * CANVAS_H)
                dx, dy = aim_pos[0] - center[0], aim_pos[1] - center[1]
                if math.hypot(dx, dy) >= 4:
                    self.cursor[:] = (ps[0] + dx * 4, ps[1] + dy * 4)
            p.trigger = p.trigger or "fire" in fingers
            p.ads = p.ads or "ads" in fingers
            p.interact = p.interact or "interact" in fingers
            dx, dy = self.cursor[0] - ps[0], self.cursor[1] - ps[1]
            p.aim = math.atan2(dy, dx)
            assist = p.weapon.s
            if p.ads:
                targets = [target for target in self.m.enemies_alive(p.team)
                           if self.m.map.los(p.x, p.y, target.x, target.y)]
                p.aim = aim_assist_angle(
                    p.aim, (p.x, p.y), targets,
                    assist.get("aim_assist_cone", math.radians(10)),
                    min(0.3, assist.get("aim_assist", 0.2)),
                    min(500, assist.get("aim_assist_range", assist["range"])))
            p.aim_dist = math.hypot(dx, dy)
        else:
            p.mx = p.my = 0.0
            p.trigger = p.ads = p.sprint = p.interact = False

    def _send_online_input(self):
        p = self.m.player
        self.online_edges["reload"] = self.online_edges["reload"] or p.want_reload
        self.online_edges["ability"] = self.online_edges["ability"] or p.want_ability
        if p.swap_to is not None:
            self.online_edges["swap_to"] = p.swap_to
        action = {
            "move_x": p.mx, "move_y": p.my, "aim": p.aim,
            "trigger": p.trigger, "ads": p.ads, "sprint": p.sprint, "interact": p.interact,
            "reload": self.online_edges["reload"], "ability": self.online_edges["ability"],
            "swap_to": self.online_edges["swap_to"],
        }
        self.online_client.send_input(action)
        p.want_reload = p.want_ability = False
        p.swap_to = None

    def _apply_online_tick(self, message):
        tick = int(message["tick"])
        if tick <= self.last_online_tick:
            return
        actions = {entry["player_id"]: entry["action"] for entry in message["inputs"]}
        for player_id, combatant in self.m.online_players.items():
            action = actions.get(player_id, {})
            combatant.mx = max(-1.0, min(1.0, float(action.get("move_x", 0.0))))
            combatant.my = max(-1.0, min(1.0, float(action.get("move_y", 0.0))))
            combatant.aim = float(action.get("aim", combatant.aim))
            combatant.trigger = bool(action.get("trigger", False))
            combatant.ads = bool(action.get("ads", False))
            combatant.sprint = bool(action.get("sprint", False))
            combatant.interact = bool(action.get("interact", False))
            combatant.want_reload = bool(action.get("reload", False))
            combatant.want_ability = bool(action.get("ability", False))
            swap_to = action.get("swap_to")
            combatant.swap_to = swap_to if swap_to in (0, 1) else None
        self.m.update(0.05)
        self._consume_events()
        self.last_online_tick = tick
        self.online_edges = {"reload": False, "ability": False, "swap_to": None}

    def _disconnect_online_match(self, message):
        self.chat_message = str(message.get("message", "PLAYER DISCONNECTED"))[:80].upper()
        self.chat_message_t = 4.0
        if self.online_client:
            self.online_client.close()
            self.online_client = None
        if not self.m.mode.over:
            self.m.mode.over = True
            self.m.mode.winner = self.m.player.team

    def _respawn_options(self, slot):
        unlocked = self.app.stats.unlocked_weapon_ids()
        if slot == 0:
            return [spec for spec in self.pw_list
                    if spec["cat"] in CATEGORY_ORDER and spec["id"] in unlocked]
        return [spec for spec in self.pw_list
                if spec["cat"] in ("PISTOL", "MELEE", "EXPLOSIVE") and spec["id"] in unlocked]

    def _cycle_respawn_weapon(self, direction):
        slot = self.respawn_slot
        options = self._respawn_options(slot)
        if not options:
            return
        attr = "respawn_primary" if slot == 0 else "respawn_secondary"
        selected = getattr(self, attr)
        ids = [spec["id"] for spec in options]
        index = ids.index(selected) if selected in ids else 0
        setattr(self, attr, ids[(index + direction) % len(ids)])

    def _confirm_respawn_loadout(self):
        p = self.m.player
        if not p.awaiting_loadout:
            return
        primary_ids = {spec["id"] for spec in self._respawn_options(0)}
        secondary_ids = {spec["id"] for spec in self._respawn_options(1)}
        if self.respawn_primary not in primary_ids or self.respawn_secondary not in secondary_ids:
            self.chat_message = "LOADOUT INVALID - SELECT AN UNLOCKED WEAPON"
            self.chat_message_t = 3.0
            return
        loadout = self.app.settings["loadout"]
        loadout["primary"], loadout["secondary"] = self.respawn_primary, self.respawn_secondary
        self.app.settings.save()
        recoil_scale = p.weapon.recoil_scale
        p.weapons = [WeaponState(weapons()[self.respawn_primary], p.ammo_mult, recoil_scale),
                     WeaponState(weapons()[self.respawn_secondary], p.ammo_mult, recoil_scale)]
        for weapon in p.weapons:
            weapon.unlimited = self.unlimited_ammo
        p.cur = 0
        p.awaiting_loadout = False
        self.m.spawn(p, full=True)

    def _camera(self, dt):
        p = self.m.player
        tgt = self.current_player_target()
        k = 0.18
        if p.alive and p.ads:
            k = 0.18 + (p.weapon.s["zoom"] - 1.0) * 0.6
        ox, oy = ((self.cursor[0] - CX) * k, (self.cursor[1] - CY) * k) if p.alive else (0, 0)
        tx, ty = tgt.x + ox, tgt.y + oy
        gm = self.m.map
        tx = gm.px_w / 2 if gm.px_w <= CANVAS_W else min(max(tx, CX), gm.px_w - CX)
        ty = gm.px_h / 2 if gm.px_h <= CANVAS_H else min(max(ty, CY), gm.px_h - CY)
        f = min(1.0, dt * 12)
        self.cam[0] += (tx - self.cam[0]) * f
        self.cam[1] += (ty - self.cam[1]) * f

    def _consume_events(self):
        m = self.m
        for ev in m.events:
            if ev[0] == "shake":
                self.shake = max(self.shake, ev[1])
            elif ev[0] == "damaged":
                self.indicators.append([ev[1], 1.0])
                self.shake = max(self.shake, 5.0)
            elif ev[0] == "hit":
                self.hit_t = 0.2
                self.hit_kill = ev[2]
                self.last_hit = "KILL" if ev[2] else "HEADSHOT" if ev[1] else "HIT"
            elif ev[0] == "nuke_ready":
                self.chat_message = "20 KILL STREAK! TYPE /NUKE TO CALL IT IN"
                self.chat_message_t = 6.0
        m.events.clear()
        listener = self.current_player_target()
        for name, x, y in m.sounds:
            d = math.hypot(x - listener.x, y - listener.y)
            self.app.audio.play(name, max(0.0, 1.0 - d / 1100.0))
        m.sounds.clear()

    # ----------------------------------------------------------------- update
    def update(self, dt):
        self.t += dt
        if self.paused and not self.online_client:
            return
        m = self.m
        if self.online_client:
            if self.paused:
                p = m.player
                p.mx = p.my = 0.0
                p.trigger = p.ads = p.sprint = p.interact = False
                p.want_reload = p.want_ability = False
                p.swap_to = None
            else:
                self._apply_input(dt)
            self._send_online_input()
            for message in self.online_client.poll():
                if message.get("type") == "tick":
                    try:
                        self._apply_online_tick(message)
                    except (KeyError, TypeError, ValueError) as exc:
                        self._disconnect_online_match({"message": f"INVALID MATCH UPDATE: {exc}"})
                        break
                elif message.get("type") in ("error", "disconnected"):
                    self._disconnect_online_match(message)
                    break
        else:
            self._apply_input(dt)
            m.update(dt)
            self._consume_events()
        self._camera(dt)
        self.shake = max(0.0, self.shake - dt * 18)
        self.hit_t = max(0.0, self.hit_t - dt)
        self.indicators = [[a, t - dt * 1.6] for a, t in self.indicators if t - dt * 1.6 > 0]
        self.chat_message_t = max(0.0, self.chat_message_t - dt)
        self.streak_message_t = max(0.0, self.streak_message_t - dt)

        p = self.m.player
        if p.alive and not self.practice:
            from .scorestreaks import SCORESTREAKS
            if not hasattr(self, "streak_ready_seen"):
                self.streak_ready_seen = [False, False, False]
            cur_score = getattr(p, "streak_score", 0)
            for slot, sid in enumerate(self.scorestreaks):
                item = next((x for x in SCORESTREAKS if x["id"] == sid), None)
                if item:
                    pts = item.get("points") or 500
                    if cur_score >= pts and not self.streak_ready_seen[slot]:
                        self.streak_ready_seen[slot] = True
                        self.streak_message = f"SCORESTREAK READY: {item['name'].upper()} [PRESS {slot + 4}]"
                        self.streak_message_t = 3.2
                        self.app.audio.play("hitmarker", 0.7)
        elif not p.alive:
            self.streak_ready_seen = [False, False, False]
        if m.mode.over:
            if self.online_client:
                self.online_client.close()
                self.online_client = None
            self.end_t += dt
            if self.end_t > 0.1:
                self.grab(False)
            if not self.recorded and not self.practice:
                self._record()
            self.recorded = True

    def _record(self):
        m, p = self.m, self.m.player
        won = m.mode.winner == p.team
        draw = m.mode.winner is None
        old_rank = self.app.stats.summary()["rank_points"]
        xp = self.app.stats.record_match(m.mode.id, m.map.id, m.diff_name, won, p.stats,
                                        ranked=self.ranked, draw=draw)
        total = self.app.stats.summary()
        campaign_progress = None
        if self.campaign_index is not None and won:
            campaign_progress = self.app.stats.complete_campaign_mission(self.campaign_index)
        self.result = dict(won=won, draw=draw, xp=xp, total=total,
                           rank_change=total["rank_points"] - old_rank if self.ranked else 0,
                           campaign_progress=campaign_progress)

    # ------------------------------------------------------------------ draw
    def draw(self, surf):
        m, p, s = self.m, self.m.player, self.app.settings
        cam = list(self.cam)
        if s["shake"] and self.shake > 0.05:
            cam[0] += random.uniform(-1, 1) * self.shake
            cam[1] += random.uniform(-1, 1) * self.shake
        self.r.draw_world(surf, cam, 0, self.t)
        for ang, a in self.indicators:
            x, y = CX + math.cos(ang) * 110, CY + math.sin(ang) * 110
            pygame.draw.line(surf, (255, int(60 * a), int(60 * a)), (CX + math.cos(ang) * 80, CY + math.sin(ang) * 80), (x, y), 8)
        info = None
        if self.practice:
            st = p.stats
            info = dict(shots=st["shots"], hits=st["hits"], hs=st["headshots"], dmg=st["damage"], last=self.last_hit,
                        acc=st["hits"] / st["shots"] * 100 if st["shots"] else 0.0,
                        compare=(p.weapon.s, self.prev_spec) if self.compare else None)
        self.r.draw_hud(surf, p, self.cursor, self.t, info)
        if self.app.touch_enabled and p.alive and not self.paused and not m.mode.over:
            self._draw_touch_hud(surf)
        if p.kill_streak > 0:
            streak = f"KILL STREAK {p.kill_streak}"
            if p.nuke_charges:
                streak += f"   NUKE READY x{p.nuke_charges} — TYPE /NUKE"
            text(surf, streak, (CX, CANVAS_H - 118), 15, AMBER, "midtop")
        if p.awaiting_loadout and not m.mode.over:
            self._overlay(surf, "CHOOSE YOUR RESPAWN LOADOUT")
            primary = weapons()[self.respawn_primary]
            secondary = weapons()[self.respawn_secondary]
            text(surf, f"{'> ' if self.respawn_slot == 0 else '  '}PRIMARY  -  {primary['name']}",
                 (CX, 300), 23, AMBER if self.respawn_slot == 0 else WHITE, "midtop")
            text(surf, f"{'> ' if self.respawn_slot == 1 else '  '}SECONDARY  -  {secondary['name']}",
                 (CX, 342), 23, AMBER if self.respawn_slot == 1 else WHITE, "midtop")
            countdown = f"RESPAWN IN {max(0, self.m.player.respawn_t):.1f}s" if self.m.player.respawn_t > 0 else "RESPAWN READY"
            text(surf, f"{countdown}  -  UP/DOWN SLOT  -  LEFT/RIGHT CHOOSE", (CX, 400), 15, GRAY, "midtop")
            text(surf, "ENTER CONFIRMS AND RESPAWNS", (CX, 432), 16, CYAN, "midtop")
        if p.alive and not self.paused and not m.mode.over:
            self.r.draw_crosshair(surf, p, self.cursor)
            if self.hit_t > 0:
                x, y = int(self.cursor[0]), int(self.cursor[1])
                col = RED if self.hit_kill else WHITE
                for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                    pygame.draw.line(surf, col, (x + dx * 6, y + dy * 6), (x + dx * 14, y + dy * 14), 3)
        keys = pygame.key.get_pressed()
        if keys[self.keys["scoreboard"]] and not self.practice:
            self.r.rank_lookup = {row["name"]: row["tier"] for row in self.app.stats.ranked_leaderboard(100)}
            self.r.player_name = self.app.stats.player_name()
            self.r.draw_scoreboard(surf)
        if keys[self.keys["tactical"]]:
            self.r.draw_tactical(surf, p)
        if self.chat_message_t > 0:
            text(surf, self.chat_message, (CX, 125), 16, AMBER, "midtop")
        if p.alive and not self.practice and not self.paused and not m.mode.over:
            from .scorestreaks import SCORESTREAKS
            card_w, card_h = 168, 60
            card_x = CANVAS_W - card_w - 14
            base_y = 220
            self.streak_rects = []
            cur_score = getattr(p, "streak_score", 0)

            # Scorestreak header badge
            header_rect = pygame.Rect(card_x, base_y - 20, card_w, 18)
            text(surf, f"SCORESTREAKS [{cur_score} PTS]", (card_x + 4, base_y - 18), 11, CYAN)

            for slot, key in enumerate(("4", "5", "6")):
                sid = self.scorestreaks[slot]
                item = next((x for x in SCORESTREAKS if x["id"] == sid), None)
                name = item["name"] if item else "EMPTY"
                req_score = (item.get("points") or 500) if item else 500
                ready = cur_score >= req_score
                frac = min(1.0, max(0.0, cur_score / req_score))

                card_rect = pygame.Rect(card_x, base_y + slot * 68, card_w, card_h)
                self.streak_rects.append(card_rect)

                # Card background & border
                if ready:
                    pulse = 0.8 + 0.2 * math.sin(self.t * 8)
                    border_color = (255, int(190 * pulse), 40)
                    pygame.draw.rect(surf, (18, 26, 30), card_rect, border_radius=5)
                    pygame.draw.rect(surf, border_color, card_rect, 2, border_radius=5)
                else:
                    border_color = (36, 48, 52)
                    pygame.draw.rect(surf, (12, 16, 20), card_rect, border_radius=5)
                    pygame.draw.rect(surf, border_color, card_rect, 1, border_radius=5)

                # Hotkey indicator badge
                key_rect = pygame.Rect(card_rect.x + 6, card_rect.y + 8, 26, 22)
                pygame.draw.rect(surf, AMBER if ready else (22, 28, 32), key_rect, border_radius=3)
                if not ready:
                    pygame.draw.rect(surf, (45, 60, 65), key_rect, 1, border_radius=3)
                text(surf, key, key_rect.center, 13, (10, 14, 16) if ready else CYAN, "center")

                # Streak name & score requirement
                text(surf, name[:12].upper(), (card_rect.x + 38, card_rect.y + 7), 11, AMBER if ready else WHITE)
                status_text = "READY [TAP]" if ready else f"{cur_score}/{req_score} PTS"
                text(surf, status_text, (card_rect.x + 38, card_rect.y + 23), 10, AMBER if ready else GRAY)

                # Vector icon on the right
                icon_rect = pygame.Rect(card_rect.right - 44, card_rect.y + 7, 38, 38)
                gfx.streak_icon(surf, sid, icon_rect, AMBER if ready else (90, 120, 130), ready=ready)

                # High-tech energy progress bar along bottom of card
                bar_rect = pygame.Rect(card_rect.x + 6, card_rect.bottom - 10, card_w - 12, 5)
                bar(surf, bar_rect, frac, AMBER if ready else (60, 200, 220), back=(10, 14, 18))

            # Tactical notification banner
            if self.streak_message_t > 0:
                banner_r = pygame.Rect(CX - 240, 116, 480, 32)
                panel(surf, banner_r, AMBER, (16, 22, 24), alpha=240)
                text(surf, f"★  {self.streak_message}  ★", banner_r.center, 13, AMBER, "center")
        if self.chat_open:
            panel(surf, (CX - 310, 555, 620, 68))
            text(surf, f"> {self.chat_input}_", (CX - 290, 566), 18, WHITE)
            text(surf, "ENTER TO RUN  |  ESC TO CANCEL", (CX, 598), 11, GRAY, "midtop")
        if self.paused:
            self._overlay(surf, "PAUSED")
            self.pause_menu.draw(surf)
            self._controls(surf)
        elif m.mode.over and self.end_t > 1.5:
            self._end_screen(surf)

    def _draw_touch_hud(self, surf):
        active = {name for name, _ in self.touch_fingers.values()}
        controls = self.app.settings["hud_controls"]
        for name, label in HUD_CONTROL_LABELS.items():
            spec = controls[name]
            center = (int(spec[0] * CANVAS_W), int(spec[1] * CANVAS_H))
            radius = int(HUD_CONTROL_RADII[name] * spec[2])
            color = AMBER if name in active else CYAN if name in ("move", "aim") else WHITE
            pygame.draw.circle(surf, (17, 31, 38), center, radius)
            pygame.draw.circle(surf, color, center, radius, 2)
            text(surf, label, center, max(10, min(15, radius // 3)), color, "center")

    def _overlay(self, surf, title):
        s = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 170))
        surf.blit(s, (0, 0))
        text(surf, title, (CX, 190), 56, AMBER, "midtop")

    def _controls(self, surf):
        k = self.app.settings["keys"]
        line = (f"{k['up']}/{k['left']}/{k['down']}/{k['right']} MOVE   LMB FIRE   RMB AIM   {k['reload']} RELOAD   {k['ability']} ABILITY   "
                f"{k['sprint']} SPRINT   {k['interact']} PLANT/DEFUSE   1/2/{k['switch']} WEAPON   ENTER CHAT   "
                f"{k['scoreboard']} SCORES   {k['tactical']} MAP   4/5/6 SCORESTREAKS").upper()
        text(surf, line, (CX, 660), 12, GRAY, "midtop")

    def _end_screen(self, surf):
        m = self.m
        self._overlay(surf, "")
        res = self.result or dict(won=False, draw=True, xp=0, total=None)
        title, col = ("DRAW", GRAY) if res["draw"] else ("VICTORY", (110, 230, 120)) if res["won"] else ("DEFEAT", RED)
        text(surf, title, (CX, 130), 72, col, "midtop")
        text(surf, f"ALPHA {m.mode.scores[0]}  -  {m.mode.scores[1]} BRAVO", (CX, 220), 32, WHITE, "midtop")
        st = m.player.stats
        acc = st["hits"] / st["shots"] * 100 if st["shots"] else 0
        text(surf, f"KILLS {st['kills']}   DEATHS {st['deaths']}   ACCURACY {acc:.0f}%   HEADSHOTS {st['headshots']}", (CX, 290), 20, GRAY, "midtop")
        if res["total"]:
            text(surf, f"+{res['xp']} XP   LEVEL {res['total']['level']}", (CX, 330), 24, AMBER, "midtop")
        if self.ranked:
            delta = res.get("rank_change", 0)
            text(surf, f"RANK {res['total']['rank']['tier'].upper()}  {res['total']['rank_points']} RP  ({delta:+d})",
                 (CX, 368), 18, CYAN if delta >= 0 else RED, "midtop")
        if self.campaign_index is not None:
            mission = campaign_mission(self.campaign_index)
            if res["won"]:
                status = ("CAMPAIGN COMPLETE" if res.get("campaign_progress") == len(CAMPAIGN_MISSIONS)
                          else f"CHAPTER {self.campaign_index + 1} COMPLETE  -  NEXT CHAPTER UNLOCKED")
                color = (110, 230, 120)
            else:
                status = f"CHAPTER {self.campaign_index + 1} FAILED  -  RETRY TO CONTINUE"
                color = RED
            text(surf, f"{mission['name'].upper()}  |  {status}", (CX, 404), 16, color, "midtop")
        self.end_menu.draw(surf)
