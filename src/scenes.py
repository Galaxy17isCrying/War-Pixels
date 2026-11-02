import math
import json
import random
import time
import shutil
from pathlib import Path

import pygame

from . import gfx
from .campaign import CAMPAIGN_MISSIONS, campaign_mission
from .config import (APP_TITLE, CANVAS_H, CANVAS_W, CATEGORY_LABEL, CATEGORY_ORDER, EQUIPMENT, SAVE_DIR, TEAM_COLORS, characters,
                     maps_meta, weapon_list, weapons)
from .difficulty import DIFFICULTIES, ORDER
from .gamemap import load_map
from .gfx import AMBER, CYAN, GRAY, GREEN, RED, WHITE, bar, panel, text
from .modes import MODE_ORDER, MODES
from .progression import (AVATAR_FRAMES, CALLING_CARDS, LEVEL_WEAPON_REWARDS, RARITY_COLORS, SKIN_DESIGNS,
                          STORE_SKIN_PRICES, avatar_frame, calling_card, legendary_skin_name, weapon_rarity)
from .save import DEFAULT_KEYS, FPS_CAPS, KEY_LABELS, RESOLUTIONS, TRIMS, level_for
from .scorestreaks import SCORESTREAKS, STREAK_SKINS

CX = CANVAS_W // 2
INTRO_DURATION = 6.0
HUD_CONTROL_RADII = {
    "move": 68, "aim": 62, "fire": 48, "ads": 38, "reload": 38, "ability": 38, "switch": 34, "interact": 34,
}
HUD_CONTROL_LABELS = {
    "move": "MOVE", "aim": "AIM", "fire": "FIRE", "ads": "ADS", "reload": "RELOAD",
    "ability": "SKILL", "switch": "SWAP", "interact": "USE",
}


class Scene:
    def __init__(self, app):
        self.app = app
        self.t = 0.0

    def event(self, e): ...
    def update(self, dt): self.t += dt
    def draw(self, surf): ...
    def on_enter(self): ...


class Menu:
    def __init__(self, app, items, x, y, w=360, h=46, size=24, gap=8):
        self.app, self.items, self.x, self.y, self.w, self.h, self.size, self.gap = app, items, x, y, w, h, size, gap
        self.sel = 0

    def rects(self):
        return [pygame.Rect(self.x, self.y + i * (self.h + self.gap), self.w, self.h) for i in range(len(self.items))]

    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % len(self.items)
                self.app.audio.play("click", 0.5)
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % len(self.items)
                self.app.audio.play("click", 0.5)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.items[self.sel][1]()
        elif e.type == pygame.MOUSEMOTION:
            pos = self.app.mouse()
            for i, r in enumerate(self.rects()):
                if r.collidepoint(pos):
                    self.sel = i
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = self.app.mouse()
            for i, r in enumerate(self.rects()):
                if r.collidepoint(pos):
                    self.sel = i
                    self.app.audio.play("click", 0.7)
                    self.items[i][1]()

    def draw(self, surf, t=0.0):
        for i, (r, (label, _)) in enumerate(zip(self.rects(), self.items)):
            sel = i == self.sel
            panel(surf, r, AMBER if sel else GREEN, gfx.PANEL2 if sel else gfx.PANEL)
            if sel:
                pygame.draw.polygon(surf, AMBER, [(r.x + 5, r.y + 7), (r.x + 10, r.y + 7),
                                                   (r.x + 10, r.bottom - 7), (r.x + 5, r.bottom - 7)])
            text(surf, ("> " if sel else "  ") + label, (r.x + 18, r.centery), self.size, AMBER if sel else WHITE, "midleft")


class MainMenu(Scene):
    def __init__(self, app):
        super().__init__(app)
        app.audio.start_music("menu")
        a = app
        self.menu = Menu(a, [("MULTIPLAYER", self.play_online),
                             ("CLASSIC (CASUAL)", self.play_classic),
                             ("RANKED MATCH", self.play_ranked),
                             ("CAMPAIGN", lambda: a.push(CampaignScene(a))),
                             ("GROUND WAR EVENT 50v50", self.ground_war),
                             ("PRACTICE RANGE", self.practice), ("LOADOUT", lambda: a.push(LoadoutScene(a))),
                             ("CUSTOMIZE MOBILE HUD", lambda: a.push(HudEditorScene(a))),
                             ("ARMORY / CRATES", lambda: a.push(ArmoryScene(a))),
                             ("GAME STORE", lambda: a.push(StoreScene(a))),
                             ("LEADERBOARD", lambda: a.push(LeaderboardScene(a))),
                             ("CLANS", lambda: a.push(ClanScene(a))),
                             ("PLAYER PROFILE", lambda: a.push(ProfileScene(a))),
                             ("CHARACTERS", lambda: a.push(CharacterScene(a))), ("SETTINGS", lambda: a.push(SettingsScene(a))),
                             ("STATISTICS", lambda: a.push(StatsScene(a))), ("CREDITS", lambda: a.push(CreditsScene(a))),
                             ("EXIT GAME", a.quit)], 90, 180, 420, 26, 14, 1)
        self.command_open = False
        self.command_input = ""
        self.command_message = ""
        self.intro_t = INTRO_DURATION if getattr(app, "intro_seen", False) else 0.0
        self.intro_skipped = bool(getattr(app, "intro_seen", False))

    def update(self, dt):
        super().update(dt)
        if self.intro_t < INTRO_DURATION:
            self.intro_t = min(INTRO_DURATION, self.intro_t + max(0.0, dt))
            if self.intro_t >= INTRO_DURATION:
                self.app.intro_seen = True
                self.app.audio.start_music("menu")

    def on_enter(self):
        if self.intro_t < INTRO_DURATION:
            self.app.audio.start_music("intro")
        else:
            self.app.audio.start_music("menu")

    def play_classic(self):
        self.app.push(MapSelect(self.app, dict(ranked=False, team_size=5)))

    def play_online(self):
        from .online_scene import OnlineScene
        self.app.push(OnlineScene(self.app))

    def play_ranked(self):
        self.app.push(MapSelect(self.app, dict(ranked=True, team_size=5)))

    def play(self):
        self.play_classic()

    def practice(self):
        from .match_scene import MatchScene
        self.app.push(MatchScene(self.app, "practice", "range"))

    def ground_war(self):
        self.app.push(LoadoutScene(self.app, dict(mode="groundwar", map="ground_war", ranked=False)))

    def event(self, e):
        if self.intro_t < INTRO_DURATION:
            if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.intro_t = INTRO_DURATION
                self.intro_skipped = True
                self.app.intro_seen = True
                self.app.audio.start_music("menu")
                if e.type == pygame.KEYDOWN and e.key == pygame.K_SLASH:
                    pass
                else:
                    return
        if self.command_open and e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.command_open = False
                self.command_input = ""
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._run_admin_command(self.command_input)
                self.command_input = ""
            elif e.key == pygame.K_BACKSPACE:
                self.command_input = self.command_input[:-1]
            else:
                char = getattr(e, "unicode", "")
                if char and char.isprintable() and len(self.command_input) < 80:
                    self.command_input += char
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_SLASH:
            self.command_open = True
            self.command_input = "/"
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            return
        self.menu.event(e)

    def _studio_splash(self, surf):
        # Cinematic studio ident: animated starfield, scanning rings, shutter bars, and a clean wordmark.
        t = self.intro_t
        fade_in = min(1.0, t / 0.45)
        fade_out = min(1.0, max(0.0, (INTRO_DURATION - t) / 0.55))
        alpha = int(255 * min(fade_in, fade_out))
        veil = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        veil.fill((4, 7, 13, 255))
        surf.blit(veil, (0, 0))
        # Subtle moving starfield, deterministic so it stays light on the renderer.
        for i in range(72):
            x = (i * 173 + int(t * (18 + i % 5) * 13)) % CANVAS_W
            y = (i * 97 + (i % 7) * 19) % CANVAS_H
            r = 1 if i % 5 else 2
            pygame.draw.circle(surf, (42 + i % 35, 77 + i % 50, 91 + i % 55), (x, y), r)
        cx, cy = CX, 270
        pulse = 1.0 + math.sin(t * 3.5) * 0.035
        # Light rays behind the emblem
        for i in range(16):
            a = i * math.tau / 16 + t * 0.08
            inner = 82 * pulse
            outer = 122 + 8 * math.sin(t * 2 + i)
            p1 = (int(cx + math.cos(a) * inner), int(cy + math.sin(a) * inner))
            p2 = (int(cx + math.cos(a) * outer), int(cy + math.sin(a) * outer))
            pygame.draw.line(surf, (19, 61, 76), p1, p2, 2)
        pygame.draw.circle(surf, (8, 19, 29), (cx, cy), int(83 * pulse))
        pygame.draw.circle(surf, (27, 180, 204), (cx, cy), int(75 * pulse), 3)
        pygame.draw.circle(surf, (244, 170, 74), (cx, cy), 59, 2)
        pygame.draw.circle(surf, (12, 34, 43), (cx, cy), 47)
        # Abstract galaxy/rice-grain mark, original to the studio ident.
        for i in range(3):
            a = t * (1.1 + i * 0.23) + i * math.tau / 3
            px, py = int(cx + math.cos(a) * 44), int(cy + math.sin(a) * 44)
            pygame.draw.ellipse(surf, (255, 186, 91) if i == 0 else (96, 225, 233), (px-5, py-10, 10, 20))
            pygame.draw.circle(surf, (235, 250, 248), (px, py), 2)
        pygame.draw.circle(surf, (255, 191, 91), (cx, cy), 11)
        pygame.draw.circle(surf, (255, 237, 191), (cx-3, cy-3), 4)
        # Shutter bars slide away during the reveal.
        reveal = min(1.0, max(0.0, (t - 0.22) / 0.62))
        shutter = int((1.0 - reveal) * 170)
        pygame.draw.rect(surf, (4, 7, 13), (0, 0, CANVAS_W, shutter))
        pygame.draw.rect(surf, (4, 7, 13), (0, CANVAS_H-shutter, CANVAS_W, shutter))
        text(surf, "GALAXYLOVESRICE", (cx, 382), 37, WHITE, "midtop")
        text(surf, "S T U D I O S", (cx, 432), 18, (92, 218, 229), "midtop")
        pygame.draw.line(surf, (255, 174, 64), (cx-205, 468), (cx+205, 468), 2)
        text(surf, "INDEPENDENT GAME DEVELOPMENT", (cx, 486), 13, (177, 194, 204), "midtop")
        if t > 0.55:
            prompt_color = (205, 218, 225) if int(t * 3) % 2 else (126, 153, 165)
            text(surf, "PRESS ANY KEY TO SKIP", (CX, 653), 13, prompt_color, "midtop")

    def _run_admin_command(self, command):
        parts = command.strip().lower().split()
        if parts == ["/admin", "help"]:
            self.command_message = "/admin rank <points>  |  /admin coins <amount>  |  /admin unlock legendary/all/frames"
        elif parts == ["/admin", "unlock", "legendary"]:
            ids = self.app.stats.grant_legendary_armory()
            self.command_message = f"LOCAL ADMIN: LEGENDARY ARMORY UNLOCKED ({len(ids)} WEAPONS)"
        elif parts == ["/admin", "unlock", "all"]:
            ids = self.app.stats.unlock_all_weapons()
            self.command_message = f"LOCAL ADMIN: ALL WEAPONS UNLOCKED ({len(ids)})"
        elif parts == ["/admin", "unlock", "frames"]:
            ids = self.app.stats.grant_all_avatar_frames()
            self.command_message = f"LOCAL ADMIN: ALL AVATAR FRAMES UNLOCKED ({len(ids)})"
        elif len(parts) == 3 and parts[:2] == ["/admin", "coins"]:
            try:
                amount = int(parts[2].replace(",", ""))
                self.app.stats.grant_coins(amount)
                self.command_message = f"LOCAL ADMIN: GRANTED {amount:,} COINS"
            except ValueError:
                self.command_message = "INVALID COIN AMOUNT"
        elif len(parts) == 3 and parts[:2] == ["/admin", "rank"]:
            try:
                rank = self.app.stats.set_rank_points(int(parts[2].replace(",", "")))
                self.command_message = f"LOCAL ADMIN: RANK SET TO {rank['tier'].upper()} ({rank['points']:,} RP)"
            except ValueError:
                self.command_message = "INVALID RANK POINTS"
        elif len(parts) == 3 and parts[:2] == ["/admin", "unlock"]:
            weapon_id = parts[2]
            if self.app.stats.unlock_weapon(weapon_id):
                self.command_message = f"LOCAL ADMIN: UNLOCKED {weapons()[weapon_id]['name']}"
            else:
                self.command_message = f"UNKNOWN WEAPON ID: {weapon_id}"
        else:
            self.command_message = "UNKNOWN ADMIN COMMAND - TYPE /ADMIN HELP"

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        glow = 8 + int(math.sin(self.t * 3) * 3)
        text(surf, APP_TITLE.upper(), (90, 80), 72, AMBER)
        text(surf, "TACTICAL TOP-DOWN SHOOTER  //  10 vs 10", (94, 168), 20, GREEN)
        pygame.draw.rect(surf, AMBER, (92, 200, 380, 3))
        self.menu.draw(surf)
        s = self.app.stats.summary()
        panel(surf, (780, 220, 410, 280))
        text(surf, "OPERATOR STATUS", (800, 232), 18, AMBER)
        gfx.draw_profile_avatar(surf, (1145, 270), 64, self.app.stats.player_picture(),
                                avatar_frame(self.app.stats.equipped_avatar_frame()), self.t)
        text(surf, f"{self.app.stats.player_name()}  /  {self.app.stats.player_uid()}", (800, 262), 14, CYAN)
        text(surf, f"LEVEL {s['level']}   XP {s['xp']}", (800, 296), 18, WHITE)
        text(surf, f"MATCHES {s['matches']}   WINS {s['wins']}", (800, 324), 16, GRAY)
        text(surf, f"K/D {s['kd']:.2f}   ACC {s['accuracy'] * 100:.0f}%", (800, 350), 16, GRAY)
        text(surf, f"RANK {s['rank']['tier'].upper()}   {s['rank_points']} RP   CRATES {s['crates']}", (800, 376), 14, AMBER)
        text(surf, f"COINS {s['coins']:,}", (800, 394), 14, AMBER)
        lo = self.app.settings["loadout"]
        text(surf, f"{lo['char'].upper()}  /  {weapons()[lo['primary']]['name']}", (800, 410), 14, CYAN)
        text(surf, "TYPE / FOR LOCAL ADMIN COMMANDS", (800, 450), 13, GRAY)
        if self.command_message:
            text(surf, self.command_message[:48], (800, 474), 12, GREEN)
        if self.command_open:
            panel(surf, (180, 560, 920, 92))
            text(surf, "LOCAL ADMIN CONSOLE  -  ENTER RUNS, ESC CLOSES", (205, 572), 14, AMBER)
            text(surf, self.command_input + ("_" if int(self.t * 2) % 2 else ""), (205, 602), 20, WHITE)
        if int(self.t * 2) % 2:
            text(surf, "_", (94, 690), 16, GREEN)
        text(surf, "W/S + ENTER  OR  MOUSE", (90, 682), 14, GRAY)
        track_title = getattr(self.app.audio, "menu_music_title", "")
        if track_title:
            text(surf, f"NOW PLAYING: {track_title}", (782, 510), 12, CYAN)
        if self.intro_t < INTRO_DURATION:
            self._studio_splash(surf)


class ProfileScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.name = app.stats.player_name()
        self.frames = AVATAR_FRAMES
        self.frame_index = next((i for i, frame in enumerate(self.frames)
                                 if frame["id"] == app.stats.equipped_avatar_frame()), 0)
        self.message = "PICTURES ARE STORED LOCALLY ON THIS DEVICE"

    def choose_picture(self):
        try:
            import tkinter
            from tkinter import filedialog
        except ImportError:
            self.message = "LOCAL FILE PICKER IS UNAVAILABLE"
            return
        try:
            root = tkinter.Tk()
            root.withdraw()
        except tkinter.TclError:
            self.message = "COULD NOT OPEN LOCAL FILE PICKER"
            return
        try:
            selected = filedialog.askopenfilename(
                parent=root, title="Choose profile picture",
                filetypes=[("Profile pictures", "*.png *.jpg *.jpeg"), ("PNG images", "*.png"),
                           ("JPEG images", "*.jpg *.jpeg")])
        except tkinter.TclError:
            self.message = "COULD NOT OPEN LOCAL FILE PICKER"
            return
        finally:
            root.destroy()
        if not selected:
            self.message = "PICTURE SELECTION CANCELLED"
            return
        source = Path(selected)
        if source.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            self.message = "CHOOSE A PNG OR JPG IMAGE"
            return
        try:
            image = pygame.image.load(str(source))
            width, height = image.get_size()
            if width < 1 or height < 1 or width > 4096 or height > 4096 or source.stat().st_size > 8 * 1024 * 1024:
                self.message = "IMAGE MUST BE 1-4096 PX AND UNDER 8 MB"
                return
            target_dir = SAVE_DIR / "profile_pictures"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"profile{source.suffix.lower()}"
            shutil.copyfile(source, target)
            self.app.stats.set_player_picture(str(target))
            self.message = "PROFILE PICTURE SAVED LOCALLY"
        except (OSError, pygame.error):
            self.message = "COULD NOT LOAD OR SAVE THAT IMAGE"

    def event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if pygame.Rect(470, 480, 250, 40).collidepoint(self.app.mouse()):
                self.choose_picture()
            return
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.app.pop()
        elif e.key == pygame.K_F2:
            self.choose_picture()
        elif e.key == pygame.K_LEFT:
            self.frame_index = (self.frame_index - 1) % len(self.frames)
        elif e.key == pygame.K_RIGHT:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
        elif e.key == pygame.K_F4:
            frame = self.frames[self.frame_index]
            self.message = ("AVATAR FRAME EQUIPPED" if self.app.stats.equip_avatar_frame(frame["id"])
                            else "LOCKED - BUY WITH F3 OR FIND IN A CRATE")
        elif e.key == pygame.K_F3:
            frame = self.frames[self.frame_index]
            if frame["source"] == "COINS" and self.app.stats.buy_avatar_frame(frame["id"]):
                self.message = f"UNLOCKED {frame['name']}"
            elif frame["id"] in self.app.stats.unlocked_avatar_frames():
                self.message = "FRAME ALREADY UNLOCKED - PRESS F4 TO EQUIP"
            elif frame["source"] == "COINS":
                self.message = f"NOT ENOUGH COINS - NEED {frame['price']}"
            else:
                self.message = "THIS FRAME IS FREE OR CRATE-ONLY"
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            old_name = self.app.stats.player_name()
            if self.app.stats.set_player_name(self.name):
                self.message = "PLAYER NAME SAVED"
                self._sync_clan_player_name(old_name, self.name)
            else:
                self.message = "NAME CANNOT BE EMPTY"
        elif e.key == pygame.K_BACKSPACE:
            self.name = self.name[:-1]
        else:
            char = getattr(e, "unicode", "")
            if char and char.isprintable() and char not in "\r\n" and len(self.name) < 20:
                self.name += char

    def _sync_clan_player_name(self, old_name, new_name):
        path = SAVE_DIR / "clans.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for clan in data.get("clans", []):
                if clan.get("leader") == old_name:
                    clan["leader"] = new_name
                    changed = True
                for member in clan.get("members", []):
                    if member.get("name") == old_name:
                        member["name"] = new_name
                        changed = True
            if changed:
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "PLAYER PROFILE", (CX, 90), 44, AMBER, "midtop")
        panel(surf, (220, 175, 840, 420))
        text(surf, "PLAYER NAME  (1-20 CHARACTERS)", (300, 205), 18, GRAY)
        pygame.draw.rect(surf, AMBER, (300, 240, 680, 52), 2)
        text(surf, self.name + ("_" if int(self.t * 2) % 2 else ""), (320, 266), 26, WHITE, "midleft")
        frame = self.frames[self.frame_index]
        gfx.draw_profile_avatar(surf, (370, 385), 104, self.app.stats.player_picture(), frame, self.t)
        text(surf, "GENERATED PLAYER UID", (470, 327), 16, GRAY)
        text(surf, self.app.stats.player_uid(), (470, 354), 21, CYAN)
        unlocked = frame["id"] in self.app.stats.unlocked_avatar_frames()
        status = "UNLOCKED" if unlocked else frame["source"]
        price = f"  -  {frame['price']} COINS" if frame["source"] == "COINS" else ""
        text(surf, f"<  {frame['name']}  >", (470, 399), 20, RARITY_COLORS[frame["rarity"]])
        text(surf, f"{frame['rarity']}  /  {status}{price}", (470, 430), 14, GRAY)
        text(surf, f"COINS: {self.app.stats.coins():,}  -  FRAME: {frame['animation'].upper()}",
             (470, 457), 14, AMBER)
        picture_button = pygame.Rect(470, 480, 250, 40)
        pygame.draw.rect(surf, gfx.PANEL2, picture_button)
        pygame.draw.rect(surf, CYAN, picture_button, 2)
        text(surf, "BROWSE FILES  (F2)", picture_button.center, 15, CYAN, "center")
        text(surf, self.message, (300, 512), 15, GREEN)
        text(surf, "CHOOSE PNG/JPG FROM FILE MANAGER  -  LEFT/RIGHT FRAME  -  F3 BUY  -  F4 EQUIP  -  ENTER SAVE NAME  -  ESC BACK",
             (CX, 625), 13, GRAY, "center")


class CreditsScene(Scene):
    def event(self, e):
        if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.pop()

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "CREDITS", (CX, 100), 44, AMBER, "midtop")
        lines = [APP_TITLE.upper(), "Original tactical top-down shooter", "Built with Python + Pygame", "",
                 "Visuals, gameplay sounds and battle music are generated in code.",
                 "Menu music is included separately.",
                 "All names, maps, characters and weapons are original.", "", "PRESS ANY KEY"]
        for i, ln in enumerate(lines):
            text(surf, ln, (CX, 190 + i * 34), 20, WHITE if i else AMBER, "midtop")


class StatsScene(Scene):
    def event(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN) or e.type == pygame.MOUSEBUTTONDOWN:
            self.app.pop()

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        s = self.app.stats.summary()
        text(surf, "STATISTICS", (60, 40), 44, AMBER)
        panel(surf, (60, 120, 560, 400))
        rows = [("MATCHES PLAYED", s["matches"]), ("WINS / LOSSES", f"{s['wins']} / {s['losses']}"), ("TOTAL KILLS", s["kills"]),
                ("TOTAL DEATHS", s["deaths"]), ("K/D RATIO", f"{s['kd']:.2f}"), ("ACCURACY", f"{s['accuracy'] * 100:.1f}%"),
                ("HEADSHOTS", s["headshots"]), ("FAVORITE WEAPON", weapons().get(s["favorite"], {}).get("name", "-")),
                ("RANKED", f"{s['rank']['tier'].upper()}  -  {s['rank_points']} RP")]
        for i, (k, v) in enumerate(rows):
            text(surf, k, (84, 144 + i * 42), 20, GRAY)
            text(surf, v, (590, 144 + i * 42), 20, WHITE, "topright")
        panel(surf, (660, 120, 560, 190))
        text(surf, f"LEVEL {s['level']}", (684, 136), 28, AMBER)
        into = s["xp"] % 250
        bar(surf, (684, 184, 500, 18), into / 250, AMBER)
        text(surf, f"{s['xp']} XP  -  {250 - into} TO NEXT LEVEL", (684, 212), 16, GRAY)
        text(surf, "MODE PERFORMANCE", (684, 250), 16, AMBER)
        y = 276
        for mode, (n, w, k) in s["modes"].items():
            text(surf, f"{mode.upper():<10} PLAYED {n}  WON {w or 0}  KILLS {k or 0}", (684, y), 14, WHITE)
            y += 22
        panel(surf, (660, 350, 560, 190))
        text(surf, "COSMETIC TRIMS (no gameplay effect)", (684, 364), 16, AMBER)
        for i, (lvl, name, col) in enumerate(TRIMS):
            unlocked = s["level"] >= lvl
            pygame.draw.rect(surf, col if unlocked else gfx.DIM, (684, 396 + i * 28, 20, 16))
            text(surf, f"{name}  -  LEVEL {lvl}{'' if unlocked else '  (LOCKED)'}", (716, 394 + i * 28), 14, WHITE if unlocked else gfx.DIM)
        text(surf, "ESC  BACK", (60, 660), 16, GRAY)


class LeaderboardScene(Scene):
    VISIBLE_ROWS = 18

    def __init__(self, app):
        super().__init__(app)
        self.rows = app.stats.ranked_leaderboard(100)
        self.scroll = 0
        self.selected_profile = None
        self.selected_index = 0
        self.clan_data = self._load_clans()

    def _load_clans(self):
        path = SAVE_DIR / "clans.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"clans": []}
        except (OSError, ValueError):
            return {"clans": []}

    def _clan_for(self, name):
        if name == self.app.stats.player_name():
            cid = self.clan_data.get("my_clan")
            if cid:
                for clan in self.clan_data.get("clans", []):
                    if clan.get("id") == cid:
                        return clan.get("name", "—")
            for clan in self.clan_data.get("clans", []):
                if any(member.get("name") == name for member in clan.get("members", [])):
                    return clan.get("name", "—")
            return "—"
        for clan in self.clan_data.get("clans", []):
            if any(member.get("name") == name for member in clan.get("members", [])):
                return clan.get("name", "—")
        clans = self.clan_data.get("clans", [])
        if clans:
            index = sum(ord(ch) for ch in name) % len(clans)
            return clans[index].get("name", "—")
        return "INDEPENDENT"

    def update(self, dt):
        super().update(dt)
        self.rows = self.app.stats.ranked_leaderboard(100)
        self.clan_data = self._load_clans()

    def _scroll(self, amount):
        self.scroll = min(max(0, self.scroll + amount), max(0, len(self.rows) - self.VISIBLE_ROWS))

    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if self.selected_profile:
                if e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE, pygame.K_BACKSPACE):
                    self.selected_profile = None
                return
            if e.key in (pygame.K_ESCAPE,):
                self.app.pop()
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                if 0 <= self.selected_index < len(self.rows):
                    self.selected_profile = self.rows[self.selected_index]
                    self.app.audio.play("click", 0.6)
            elif e.key in (pygame.K_DOWN, getattr(pygame, "K_PAGEDOWN", pygame.K_DOWN)):
                step = 1 if e.key == pygame.K_DOWN else self.VISIBLE_ROWS
                self.selected_index = min(len(self.rows) - 1, self.selected_index + step)
                self._scroll(step)
            elif e.key in (pygame.K_UP, getattr(pygame, "K_PAGEUP", pygame.K_UP)):
                step = 1 if e.key == pygame.K_UP else self.VISIBLE_ROWS
                self.selected_index = max(0, self.selected_index - step)
                self._scroll(-step)
        elif e.type == getattr(pygame, "MOUSEWHEEL", -1):
            if not self.selected_profile:
                self._scroll(-e.y)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if self.selected_profile:
                position = (self.app.screen_to_canvas(e.pos) if hasattr(e, "pos") else self.app.mouse())
                if not pygame.Rect(330, 155, 620, 410).collidepoint(position):
                    self.selected_profile = None
                return
            if getattr(e, "button", None) == 1:
                position = (self.app.screen_to_canvas(e.pos) if hasattr(e, "pos") else self.app.mouse())
                mx, my = position
                visible = self.rows[self.scroll:self.scroll + self.VISIBLE_ROWS]
                if 52 <= mx <= 1228 and 152 <= my < 152 + len(visible) * 24:
                    row_index = int((my - 152) // 24)
                    absolute = self.scroll + row_index
                    if 0 <= absolute < len(self.rows):
                        self.selected_index = absolute
                        self.selected_profile = self.rows[absolute]
                        self.app.audio.play("click", 0.6)
            elif getattr(e, "button", None) in (4, 5):
                self._scroll(-1 if e.button == 4 else 1)

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "RANKED LEADERBOARD", (48, 28), 36, AMBER)
        text(surf, f"TOP 100  /  LIVE OFFLINE SIMULATION  /  {self.app.stats.player_name()}",
             (52, 72), 15, CYAN)
        panel(surf, (42, 108, 1196, 512))
        headers = (("#", 62), ("PLAYER  /  CLICK FOR PROFILE", 105), ("CLAN", 390), ("RANK", 700), ("STREAK", 835), ("W-L", 930), ("RANK POINTS", 1050))
        for label, x in headers:
            text(surf, label, (x, 126), 13, AMBER)
        visible = self.rows[self.scroll:self.scroll + self.VISIBLE_ROWS]
        mx, my = self.app.mouse()
        for index, row in enumerate(visible):
            y = 154 + index * 24
            row_rect = pygame.Rect(52, y - 2, 1176, 22)
            abs_index = self.scroll + index
            is_hover = (52 <= mx <= 1228 and y - 2 <= my < y + 22) and not self.selected_profile
            is_cursor = (abs_index == self.selected_index) and not self.selected_profile
            if row["is_player"]:
                pygame.draw.rect(surf, (78, 58, 24) if (is_hover or is_cursor) else (66, 49, 20), row_rect, border_radius=3)
            elif is_hover or is_cursor:
                pygame.draw.rect(surf, (38, 50, 44), row_rect, border_radius=3)
            elif index % 2 == 0:
                pygame.draw.rect(surf, (25, 31, 28), row_rect, border_radius=3)
            if is_hover or is_cursor:
                pygame.draw.rect(surf, AMBER if (row["is_player"] or is_cursor) else CYAN, row_rect, 1, border_radius=3)
            color = AMBER if row["is_player"] else WHITE
            name = f"{row['name']} (YOU)" if row["is_player"] else row["name"]
            text(surf, f"{row['position']:02}", (62, y), 13, color)
            text(surf, name[:24], (105, y), 13, color)
            text(surf, self._clan_for(row["name"])[:26], (390, y), 12, CYAN if not row["is_player"] else AMBER)
            gfx.draw_rank_emblem(surf, (710, y + 8), 12, row["tier"], self.t)
            text(surf, row["tier"].upper(), (729, y), 12, color)
            streak = row.get("streak", 0)
            text(surf, f"W{streak}" if streak > 0 else f"L{abs(streak)}" if streak < 0 else "—",
                 (835, y), 12, GREEN if streak > 0 else RED if streak < 0 else GRAY)
            text(surf, f"{row.get('wins', 0)}-{row.get('losses', 0)}", (930, y), 12, WHITE)
            text(surf, f"{row['points']} RP", (1050, y), 12, CYAN if row["is_player"] else WHITE)
        text(surf, f"SHOWING {self.scroll + 1}-{self.scroll + len(visible)} OF {len(self.rows)}  /  CLICK OR PRESS ENTER ON ANY PLAYER FOR PROFILE  /  ARROWS OR WHEEL TO SCROLL  /  ESC BACK",
             (48, 642), 13, GRAY)
        if self.selected_profile:
            self._draw_player_profile(surf, self.selected_profile)

    def _draw_player_profile(self, surf, row):
        shade = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 190))
        surf.blit(shade, (0, 0))
        panel(surf, (330, 155, 620, 410), fill=(16, 23, 21), alpha=250)
        text(surf, "PLAYER PROFILE", (640, 178), 30, AMBER, "midtop")
        picture = self.app.stats.player_picture() if row["is_player"] else None
        frame = avatar_frame(self.app.stats.equipped_avatar_frame()) if row["is_player"] else None
        if row["is_player"] and picture:
            gfx.draw_profile_avatar(surf, (435, 300), 94, picture, frame, self.t)
        else:
            initials = "".join(part[0] for part in row["name"].split()[:2]).upper() or "?"
            pygame.draw.circle(surf, (42, 83, 98), (435, 300), 52)
            pygame.draw.circle(surf, CYAN, (435, 300), 52, 3)
            text(surf, initials, (435, 279), 30, WHITE, "midtop")
        clan = self._clan_for(row["name"])
        text(surf, row["name"][:28], (510, 235), 24, WHITE)
        text(surf, f"CLAN  {clan[:28]}", (510, 278), 15, CYAN)
        text(surf, f"RANK  {row['tier'].upper()}  /  {row['points']} RP", (510, 309), 15, AMBER)
        text(surf, f"POSITION  #{row['position']}", (510, 338), 15, WHITE)
        text(surf, f"MATCH RECORD  {row.get('wins', 0)} W  -  {row.get('losses', 0)} L", (510, 367), 15, WHITE)
        streak = row.get("streak", 0)
        streak_label = f"WIN STREAK {streak}" if streak > 0 else f"LOSS STREAK {abs(streak)}" if streak < 0 else "NO ACTIVE STREAK"
        text(surf, streak_label, (510, 396), 15, GREEN if streak > 0 else RED if streak < 0 else GRAY)
        text(surf, "PROFILE PICTURE" if picture else "LOCAL BOT AVATAR", (435, 375), 11, GRAY, "midtop")
        card_rect = pygame.Rect(510, 428, 390, 58)
        card = (calling_card(self.app.stats.equipped_calling_card()) if row["is_player"]
                else CALLING_CARDS[0])
        subtitle = (f"TOP {max(1, row.get('position', 100))}% OPERATIVE" if row["is_player"]
                    else "LOCAL SIMULATION  /  COMBAT RECORD")
        gfx.draw_calling_card(surf, card_rect, card, subtitle=subtitle, t=self.t)
        text(surf, "CLICK OR PRESS ESC TO CLOSE", (640, 525), 13, GRAY, "midtop")


class ClanScene(Scene):
    path = SAVE_DIR / "clans.json"
    ranks = ["BRONZE", "SILVER", "GOLD", "PLATINUM", "DIAMOND", "MYTHIC"]
    mythic_names = ["Gojo Satoru", "Nino Nakano", "Miku Nakano", "Yotsuba Nakano", "Ichika Nakano",
                    "Itsuki Nakano", "Fuutarou Uesugi", "Peter Griffin", "Anya Forger", "Shrek Main",
                    "Nah Id Win", "Toji Tax Collector", "Amongus ඞ", "Saitama OneTap", "Walter White"]

    def __init__(self, app):
        super().__init__(app)
        self.data = {"clans": [], "my_clan": None}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, ValueError):
            pass
        if not self.data["clans"]:
            seed_clans = [
                ("MYTHIC LOBOTOMY", 5, ["Gojo Satoru", "Nah Id Win", "Toji Tax Collector"]),
                ("NAKANO QUINTS HQ", 2, ["Nino Nakano", "Miku Nakano", "Yotsuba Nakano"]),
                ("PETER GRIFFIN GAMING", 0, ["Peter Griffin", "Shrek Main", "Rizzler"]),
                ("ANIME FINAL BOSSES", 3, ["Anya Forger", "Saitama OneTap", "Megumin"]),
                ("TQQ PROTECTORS", 1, ["Fuutarou Uesugi", "Ichika Nakano", "Itsuki Nakano"]),
                ("DOMAIN EXPANSION", 4, ["Sukuna Finger", "Kono Dio Da", "Domain Expansion"]),
                ("GRIFFIN INDUSTRIES", 0, ["Peter Griffin", "Lois Main", "Meg Griffin"]),
                ("NO AIM NO BRAIN", 0, ["Potato Aim", "NoScope Grandma", "Lagging Legend"]),
                ("WIFI SAMURAI", 2, ["WiFi Samurai", "Goku WiFi", "Kirito Offline"]),
                ("THE GOAT SQUAD", 3, ["Speedwagon GOAT", "Batman No Prep", "Luffy Tax Evasion"]),
                ("CERTIFIED NPCS", 0, ["Certified NPC", "Unpaid Intern", "Rizzler"]),
                ("NAKANO FAMILY", 2, ["Miku Nakano", "Nino Nakano", "Yotsuba Nakano"]),
            ]
            for idx, (clan_name, min_rank, names) in enumerate(seed_clans):
                self.data["clans"].append({"id": f"NPC-CLAN-{idx}", "name": clan_name,
                    "leader": names[0], "min_rank": min_rank,
                    "members": [{"name": n, "rank": "MYTHIC", "mythic": True} for n in names],
                    "chat": [{"name": "SYSTEM", "message": "Welcome to the clan chat."}]})
            self.save()
        extra_clans = [
            ("TQQ PROTECTORS", 1, ["Fuutarou Uesugi", "Ichika Nakano", "Itsuki Nakano", "Miku Main", "Quintuplet Carry"]),
            ("DOMAIN EXPANSION", 4, ["Sukuna Finger", "Kono Dio Da", "Domain Expansion", "Gojo Blindfold", "Mahoraga Wheel"]),
            ("GRIFFIN INDUSTRIES", 0, ["Peter Griffin", "Lois Main", "Meg Griffin", "Stewie CEO", "Brian The Drip"]),
            ("NO AIM NO BRAIN", 0, ["Potato Aim", "NoScope Grandma", "Lagging Legend", "Missed Every Shot", "Ping 999"]),
            ("WIFI SAMURAI", 2, ["WiFi Samurai", "Goku WiFi", "Kirito Offline", "Router Slayer", "Ethernet Ronin"]),
            ("THE GOAT SQUAD", 3, ["Speedwagon GOAT", "Batman No Prep", "Luffy Tax Evasion", "Levi Spinbot", "Saitama OneTap"]),
            ("CERTIFIED NPCS", 0, ["Certified NPC", "Unpaid Intern", "Rizzler", "Default Dance", "Side Quest Guy"]),
            ("NAKANO FAMILY", 2, ["Miku Nakano", "Nino Nakano", "Yotsuba Nakano", "Ichika Nakano", "Itsuki Nakano"]),
            ("ANIME TAX EVADERS", 1, ["Luffy Tax Evasion", "Zoro Lost Again", "Sanji Simp Mode", "Chopper Emergency", "Usopp 100T Hammer"]),
            ("PETER'S CUTAWAY CREW", 0, ["Peter Griffin", "Ernie The Giant Chicken", "Joe Swanson", "Quagmire Sus", "Cleveland Brown"]),
            ("SHONEN FINAL BOSS", 4, ["Madara Uchiha", "Aizen Glasses", "Meruem Aura", "Frieza Fourth Form", "All For One"]),
            ("TQQ MIKU FAN CLUB", 2, ["Miku Nakano", "Miku Defender", "Miku Hoodie", "Miku Best Girl"]),
            ("GOJO REVIVAL FUND", 3, ["Gojo Satoru", "Nah Id Win", "Six Eyes Merchant", "Unlimited Copium", "Domain Expansion"]),
            ("BRAINROT ELITE", 0, ["Skibidi Operator", "Rizzler Prime", "Fanum Tax", "Sigma Sloth", "Ohio Final Boss"]),
            ("THE NAKANO RAID", 2, ["Nino Nakano", "Yotsuba Nakano", "Ichika Nakano", "Itsuki Nakano", "Fuutarou Uesugi"]),
            ("ONE TAP UNIVERSITY", 1, ["Saitama OneTap", "Critical Hitman", "Headshot Merchant", "Aim Assist Grandma", "Flick Wizard"]),
            ("SHREK SWAMP SECURITY", 0, ["Shrek Main", "Donkey Mic On", "Puss In Boots", "Fiona Carry", "Lord Farquaad"]),
            ("ANIME PROTAGONIST SYNDICATE", 3, ["Naruto Talk No Jutsu", "Ichigo Substitute", "Tanjiro Nezuko Taxi", "Deku Smash", "Eren Rumbling"]),
            ("LAG SPIKE LEGENDS", 0, ["Packet Loss King", "Rubberband Ronin", "Ping Goblin", "Buffering Hero", "FPS 12"]),
            ("MYTHIC MEME COUNCIL", 5, ["Peter Griffin", "Gojo Satoru", "Nino Nakano", "Shrek Main", "Walter White"]),
        ]
        existing_names = {c.get("name") for c in self.data["clans"]}
        for clan_name, min_rank, names in extra_clans:
            clan = next((c for c in self.data["clans"] if c.get("name") == clan_name), None)
            if clan is None:
                idx = len(self.data["clans"])
                clan = {"id": f"NPC-CLAN-{idx}", "name": clan_name,
                    "leader": names[0], "min_rank": min_rank,
                    "members": [], "chat": [{"name": "SYSTEM", "message": "Welcome to the clan chat."}]}
                self.data["clans"].append(clan)
            known_members = {m.get("name") for m in clan.get("members", [])}
            for member_name in names:
                if member_name not in known_members:
                    clan.setdefault("members", []).append({"name": member_name, "rank": "MYTHIC", "mythic": True})
                    known_members.add(member_name)

        # Sync player membership with my_clan
        pname = self.app.stats.player_name()
        my_c = self.clan()
        if my_c:
            if not any(m.get("name") == pname for m in my_c.get("members", [])):
                my_c.setdefault("members", []).append({
                    "name": pname,
                    "rank": "LEADER" if my_c.get("leader") == pname else "MEMBER",
                    "mythic": False
                })
        else:
            found_clan = next((c for c in self.data["clans"] if any(m.get("name") == pname for m in c.get("members", []))), None)
            if found_clan:
                self.data["my_clan"] = found_clan["id"]

        self.save()
        self.mode = "home"
        self.name_input = ""
        self.chat_input = ""
        self.rename_input = ""
        self.renaming = False
        self.message = ""
        self.selected = 0
        self.find_scroll = 0
        self.rank_req = 0
        self.chat_mode = False

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def clan(self):
        cid = self.data.get("my_clan")
        if not cid:
            return None
        return next((c for c in self.data["clans"] if c.get("id") == cid), None)

    def create(self):
        name = self.name_input.strip()
        if not name:
            self.message = "ENTER A CLAN NAME FIRST"
            return
        if self.app.stats.coins() < 1000:
            self.message = "YOU NEED 1,000 COINS TO CREATE A CLAN"
            return
        pname = self.app.stats.player_name()
        # Leave current clan if already in one
        curr = self.clan()
        if curr:
            curr["members"] = [m for m in curr.get("members", []) if m.get("name") != pname]
            if curr.get("leader") == pname:
                if curr["members"]:
                    curr["leader"] = curr["members"][0]["name"]
                    curr["members"][0]["rank"] = "LEADER"
            curr.setdefault("chat", []).append({"name": "SYSTEM", "message": f"{pname} left to create a new clan."})

        self.app.stats._set_profile_int("coins", self.app.stats.coins() - 1000)
        cid = f"CLAN-{int(time.time() * 1000)}"
        members = [{"name": pname, "rank": "LEADER", "mythic": False}]
        names = self.mythic_names[:]
        random.shuffle(names)
        for bot_name in names[:5]:
            members.append({"name": bot_name, "rank": "MYTHIC", "mythic": True})
        c = {"id": cid, "name": name[:24], "leader": pname, "min_rank": self.rank_req,
             "members": members, "chat": [{"name": "SYSTEM", "message": "Clan created! Mythical players joined the squad."}]}
        self.data["clans"].append(c)
        self.data["my_clan"] = cid
        self.save()
        self.mode = "detail"
        self.message = "CLAN CREATED! 1,000 COINS SPENT"

    def _player_rank_index(self):
        rank = self.app.stats.rank()
        tier_base = rank.get("tier", "Bronze").split()[0].upper()
        if tier_base in self.ranks:
            return self.ranks.index(tier_base)
        if tier_base in ("MASTER", "LEGENDARY"):
            return 4  # Master / Legendary counts above Platinum (Diamond tier)
        return 0

    def join(self, c):
        curr = self.clan()
        if curr and curr.get("id") == c.get("id"):
            self.message = "ALREADY A MEMBER OF THIS CLAN"
            self.mode = "detail"
            return
        player_rank_idx = self._player_rank_index()
        if player_rank_idx < c.get("min_rank", 0):
            self.message = f"RANK TOO LOW! REQUIRES {self.ranks[c.get('min_rank', 0)]}"
            return
        pname = self.app.stats.player_name()
        # Seamlessly leave old clan and switch to the new clan
        if curr:
            curr["members"] = [m for m in curr.get("members", []) if m.get("name") != pname]
            if curr.get("leader") == pname:
                if curr["members"]:
                    curr["leader"] = curr["members"][0]["name"]
                    curr["members"][0]["rank"] = "LEADER"
            curr.setdefault("chat", []).append({"name": "SYSTEM", "message": f"{pname} left the clan."})

        c["members"] = [m for m in c.get("members", []) if m.get("name") != pname]
        c["members"].append({"name": pname, "rank": "MEMBER", "mythic": False})
        self.data["my_clan"] = c["id"]
        c.setdefault("chat", []).append({"name": "SYSTEM", "message": f"{pname} joined the clan."})
        self.save()
        self.mode = "detail"
        self.message = f"CHANGED CLAN TO {c['name']}!" if curr else f"JOINED {c['name']}!"

    def leave_clan(self):
        c = self.clan()
        if not c:
            return
        pname = self.app.stats.player_name()
        c["members"] = [m for m in c.get("members", []) if m.get("name") != pname]
        if c.get("leader") == pname:
            if c["members"]:
                c["leader"] = c["members"][0]["name"]
                c["members"][0]["rank"] = "LEADER"
        self.data["my_clan"] = None
        c.setdefault("chat", []).append({"name": "SYSTEM", "message": f"{pname} left the clan."})
        self.save()
        self.mode = "home"
        self.message = "YOU LEFT THE CLAN"

    def rename_clan(self):
        c = self.clan()
        if not c or c.get("leader") != self.app.stats.player_name():
            self.renaming = False
            return
        new_name = self.rename_input.strip()
        if not new_name:
            self.message = "CLAN NAME CANNOT BE EMPTY"
            self.renaming = False
            return
        c["name"] = new_name[:24]
        c.setdefault("chat", []).append({"name": "SYSTEM", "message": f"Clan was renamed to {c['name']}."})
        self.save()
        self.renaming = False
        self.message = f"CLAN RENAMED TO {c['name']}!"

    def _sync_find_scroll(self):
        visible_count = 11
        if self.selected < self.find_scroll:
            self.find_scroll = self.selected
        elif self.selected >= self.find_scroll + visible_count:
            self.find_scroll = self.selected - visible_count + 1
        self.find_scroll = max(0, min(self.find_scroll, max(0, len(self.data["clans"]) - visible_count)))

    def event(self, e):
        # Mouse wheel support
        if e.type == getattr(pygame, "MOUSEWHEEL", -1) and self.mode == "find":
            self.selected = max(0, min(len(self.data["clans"]) - 1, self.selected - e.y))
            self._sync_find_scroll()
            return

        # Mouse click support
        if e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", None) == 1:
            mx, my = self.app.mouse()
            c = self.clan()
            if self.mode == "home":
                items = [("OPEN MY CLAN" if c else "CREATE A CLAN  -  1,000 COINS"), "FIND A CLAN", "BACK"]
                for i in range(len(items)):
                    r = pygame.Rect(100, 180 + i * 72, 600, 54)
                    if r.collidepoint((mx, my)):
                        self.selected = i
                        self.app.audio.play("click", 0.5)
                        if i == 0:
                            self.mode = "detail" if self.clan() else "create"
                        elif i == 1:
                            self.mode = "find"
                        else:
                            self.app.pop()
                        return
            elif self.mode == "find":
                visible_count = 11
                visible = self.data["clans"][self.find_scroll : self.find_scroll + visible_count]
                for idx, clan in enumerate(visible):
                    abs_idx = self.find_scroll + idx
                    r = pygame.Rect(75, 156 + idx * 38, 1000, 34)
                    if r.collidepoint((mx, my)):
                        self.app.audio.play("click", 0.5)
                        if self.selected == abs_idx:
                            self.join(clan)
                        else:
                            self.selected = abs_idx
                        return
                back_r = pygame.Rect(70, 630, 140, 32)
                if back_r.collidepoint((mx, my)):
                    self.app.audio.play("click", 0.5)
                    self.mode = "home"
                    return
            elif self.mode == "detail" and c:
                is_leader = c.get("leader") == self.app.stats.player_name()
                if is_leader and pygame.Rect(450, 138, 160, 28).collidepoint((mx, my)):
                    self.renaming = not self.renaming
                    self.rename_input = c["name"]
                    self.app.audio.play("click", 0.5)
                    return
                if is_leader and pygame.Rect(320, 206, 30, 24).collidepoint((mx, my)):
                    c["min_rank"] = max(0, c.get("min_rank", 0) - 1)
                    self.save()
                    return
                if is_leader and pygame.Rect(360, 206, 30, 24).collidepoint((mx, my)):
                    c["min_rank"] = min(len(self.ranks) - 1, c.get("min_rank", 0) + 1)
                    self.save()
                    return
                if pygame.Rect(80, 570, 150, 34).collidepoint((mx, my)):
                    self.app.audio.play("click", 0.5)
                    self.leave_clan()
                    return
                if pygame.Rect(250, 570, 150, 34).collidepoint((mx, my)):
                    self.app.audio.play("click", 0.5)
                    self.mode = "home"
                    return
                if pygame.Rect(660, 565, 550, 38).collidepoint((mx, my)):
                    self.chat_mode = True
                    return

        if e.type != pygame.KEYDOWN:
            return

        # Rename Clan input mode (for clan leader)
        if self.mode == "detail" and self.renaming:
            if e.key == pygame.K_ESCAPE:
                self.renaming = False
            elif e.key == pygame.K_BACKSPACE:
                self.rename_input = self.rename_input[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.rename_clan()
            else:
                ch = getattr(e, "unicode", "")
                if ch and ch.isprintable() and len(self.rename_input) < 24:
                    self.rename_input += ch
            return

        if self.mode == "create" and not self.chat_mode:
            if e.key == pygame.K_ESCAPE:
                self.mode = "home"
            elif e.key == pygame.K_BACKSPACE:
                self.name_input = self.name_input[:-1]
            elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.rank_req = max(0, min(len(self.ranks)-1, self.rank_req + (1 if e.key == pygame.K_RIGHT else -1)))
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.create()
            else:
                ch = getattr(e, "unicode", "")
                if ch and ch.isprintable() and len(self.name_input) < 24:
                    self.name_input += ch
            return

        if self.mode == "detail" and self.chat_mode:
            if e.key == pygame.K_ESCAPE:
                self.chat_mode = False
            elif e.key == pygame.K_BACKSPACE:
                self.chat_input = self.chat_input[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                msg = self.chat_input.strip()
                if msg:
                    c = self.clan()
                    if c:
                        c.setdefault("chat", []).append({"name": self.app.stats.player_name(), "message": msg[:100]})
                        c["chat"] = c["chat"][-80:]
                        self.save()
                    self.chat_input = ""
            else:
                ch = getattr(e, "unicode", "")
                if ch and ch.isprintable() and len(self.chat_input) < 100:
                    self.chat_input += ch
            return

        if e.key == pygame.K_ESCAPE:
            if self.mode != "home":
                self.mode = "home"
            else:
                self.app.pop()
        elif self.mode == "home":
            if e.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % 3
                self.app.audio.play("click", 0.5)
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % 3
                self.app.audio.play("click", 0.5)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.app.audio.play("click", 0.5)
                if self.selected == 0:
                    self.mode = "detail" if self.clan() else "create"
                elif self.selected == 1:
                    self.mode = "find"
                else:
                    self.app.pop()
        elif self.mode == "find":
            if e.key in (pygame.K_UP, pygame.K_w):
                self.selected = max(0, self.selected - 1)
                self._sync_find_scroll()
                self.app.audio.play("click", 0.4)
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = min(max(0, len(self.data["clans"])-1), self.selected + 1)
                self._sync_find_scroll()
                self.app.audio.play("click", 0.4)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and self.data["clans"]:
                self.join(self.data["clans"][self.selected])
        elif self.mode == "detail":
            c = self.clan()
            if not c:
                self.mode = "home"
                return
            is_leader = c.get("leader") == self.app.stats.player_name()
            if e.key == pygame.K_t:
                self.chat_mode = True
            elif e.key == pygame.K_r and is_leader:
                self.renaming = True
                self.rename_input = c["name"]
            elif e.key in (pygame.K_LEFT, pygame.K_RIGHT) and is_leader:
                c["min_rank"] = max(0, min(len(self.ranks)-1, c.get("min_rank", 0) + (1 if e.key == pygame.K_RIGHT else -1)))
                self.save()
            elif e.key == pygame.K_l:
                self.leave_clan()

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "CLANS", (60, 34), 42, AMBER)
        text(surf, f"COINS {self.app.stats.coins():,}  |  CREATE COST 1,000", (64, 82), 17, CYAN)
        c = self.clan()
        mx, my = self.app.mouse()
        if self.mode == "home":
            items = [("OPEN MY CLAN" if c else "CREATE A CLAN  -  1,000 COINS"), "FIND A CLAN", "BACK"]
            for i, label in enumerate(items):
                r = pygame.Rect(100, 180 + i * 72, 600, 54)
                hovered = r.collidepoint((mx, my))
                sel = i == self.selected or hovered
                pygame.draw.rect(surf, gfx.PANEL2 if sel else gfx.PANEL, r)
                pygame.draw.rect(surf, AMBER if sel else GREEN, r, 2)
                text(surf, label, (r.x + 18, r.centery), 22, AMBER if sel else WHITE, "midleft")
            text(surf, "Create a clan or browse/change clans made by other players.", (100, 430), 17, GRAY)
        elif self.mode == "create":
            panel(surf, (90, 150, 900, 330))
            text(surf, "CLAN NAME", (120, 185), 18, AMBER)
            text(surf, self.name_input + "_", (120, 225), 28, WHITE)
            text(surf, f"MINIMUM JOIN RANK: {self.ranks[self.rank_req]}  (LEFT/RIGHT)", (120, 290), 20, CYAN)
            text(surf, "ENTER CREATE  |  ESC BACK", (120, 355), 16, GRAY)
        elif self.mode == "find":
            curr_name = c["name"] if c else "NONE"
            text(surf, f"SELECT A CLAN TO JOIN OR CHANGE TO  |  CURRENT CLAN: {curr_name}", (70, 122), 16, CYAN)
            if not self.data["clans"]:
                text(surf, "NO CLANS YET - CREATE ONE FIRST", (80, 190), 24, WHITE)
            visible_count = 11
            visible = self.data["clans"][self.find_scroll : self.find_scroll + visible_count]
            player_rank_idx = self._player_rank_index()

            for idx, clan in enumerate(visible):
                abs_idx = self.find_scroll + idx
                y = 158 + idx * 38
                r = pygame.Rect(70, y - 4, 1050, 34)
                hovered = r.collidepoint((mx, my))
                sel = abs_idx == self.selected
                is_curr = c and c.get("id") == clan.get("id")
                req_rank = clan.get("min_rank", 0)
                meets_req = player_rank_idx >= req_rank

                if sel or hovered:
                    pygame.draw.rect(surf, (36, 48, 42) if sel else gfx.PANEL2, r, border_radius=4)
                    pygame.draw.rect(surf, AMBER if sel else CYAN, r, 2, border_radius=4)
                else:
                    if idx % 2 == 0:
                        pygame.draw.rect(surf, (22, 28, 25), r, border_radius=4)

                col = AMBER if sel else WHITE
                text(surf, f"{clan['name']:<24}", (85, y), 17, col)
                text(surf, f"{len(clan.get('members', []))} MEMBERS", (380, y), 16, GRAY)
                min_col = GREEN if meets_req else RED
                text(surf, f"MIN {self.ranks[req_rank]}", (560, y), 15, min_col)
                if is_curr:
                    text(surf, "[ CURRENT CLAN ]", (750, y), 14, GREEN)
                elif meets_req:
                    text(surf, "[ CLICK / ENTER TO JOIN / SWITCH ]" if (sel or hovered) else "ELIGIBLE", (750, y), 13, CYAN if (sel or hovered) else GRAY)
                else:
                    text(surf, f"[ RANK TOO LOW ]", (750, y), 13, RED)

            # Scroll indicator
            total_clans = len(self.data["clans"])
            text(surf, f"SHOWING {self.find_scroll + 1}-{min(total_clans, self.find_scroll + visible_count)} OF {total_clans}  |  UP/DOWN/WHEEL TO SCROLL  |  CLICK OR ENTER TO CHANGE CLAN", (70, 592), 14, GRAY)
            back_r = pygame.Rect(70, 626, 140, 34)
            b_hover = back_r.collidepoint((mx, my))
            pygame.draw.rect(surf, gfx.PANEL2 if b_hover else gfx.PANEL, back_r, border_radius=4)
            pygame.draw.rect(surf, AMBER if b_hover else GREEN, back_r, 2, border_radius=4)
            text(surf, "< BACK (ESC)", (back_r.centerx, back_r.centery), 15, AMBER if b_hover else WHITE, "center")

        elif self.mode == "detail" and c:
            panel(surf, (55, 120, 570, 500))
            panel(surf, (645, 120, 580, 500))
            is_leader = c.get("leader") == self.app.stats.player_name()

            if self.renaming:
                text(surf, "NEW CLAN NAME:", (80, 138), 16, AMBER)
                pygame.draw.rect(surf, gfx.PANEL2, (80, 160, 340, 34))
                pygame.draw.rect(surf, CYAN, (80, 160, 340, 34), 2)
                text(surf, self.rename_input + "_", (90, 177), 18, WHITE, "midleft")
                text(surf, "ENTER SAVE  |  ESC CANCEL", (80, 202), 12, GRAY)
            else:
                text(surf, c["name"], (80, 142), 30, AMBER)
                if is_leader:
                    ren_r = pygame.Rect(450, 138, 160, 28)
                    ren_hover = ren_r.collidepoint((mx, my))
                    pygame.draw.rect(surf, gfx.PANEL2 if ren_hover else gfx.PANEL, ren_r, border_radius=3)
                    pygame.draw.rect(surf, AMBER if ren_hover else CYAN, ren_r, 1, border_radius=3)
                    text(surf, "RENAME (R)", (ren_r.centerx, ren_r.centery), 13, AMBER if ren_hover else CYAN, "center")

            text(surf, f"LEADER: {c.get('leader', '—')}", (80, 183), 16, CYAN)
            min_r_text = f"MIN RANK: {self.ranks[c.get('min_rank',0)]}"
            if is_leader:
                min_r_text += "  (CHANGE: < / > OR LEFT / RIGHT)"
            text(surf, min_r_text, (80, 212), 13, GRAY)

            for i, member in enumerate(c.get("members", [])[:12]):
                tag = "MYTHIC" if member.get("mythic") else member.get("rank", "MEMBER")
                is_you = member.get("name") == self.app.stats.player_name()
                m_color = AMBER if is_you else (CYAN if tag == "LEADER" else (GREEN if tag == "MYTHIC" else WHITE))
                m_label = f"{member['name']}{' (YOU)' if is_you else ''}  -  {tag}"
                text(surf, m_label, (80, 246 + i * 25), 15, m_color)

            # Detail buttons
            leave_r = pygame.Rect(80, 568, 150, 34)
            l_hover = leave_r.collidepoint((mx, my))
            pygame.draw.rect(surf, (60, 20, 20) if l_hover else gfx.PANEL, leave_r, border_radius=4)
            pygame.draw.rect(surf, RED if l_hover else GRAY, leave_r, 2, border_radius=4)
            text(surf, "LEAVE CLAN (L)", (leave_r.centerx, leave_r.centery), 14, RED if l_hover else WHITE, "center")

            menu_r = pygame.Rect(250, 568, 150, 34)
            m_hover = menu_r.collidepoint((mx, my))
            pygame.draw.rect(surf, gfx.PANEL2 if m_hover else gfx.PANEL, menu_r, border_radius=4)
            pygame.draw.rect(surf, AMBER if m_hover else GREEN, menu_r, 2, border_radius=4)
            text(surf, "MENU (ESC)", (menu_r.centerx, menu_r.centery), 14, AMBER if m_hover else WHITE, "center")

            # Chat section
            text(surf, "CLAN CHAT", (670, 142), 23, AMBER)
            msgs = c.get("chat", [])[-14:]
            for i, msg in enumerate(msgs):
                sender = msg.get("name", "SYSTEM")
                content = msg.get("message", "")
                s_col = AMBER if sender == self.app.stats.player_name() else (CYAN if sender == "SYSTEM" else WHITE)
                text(surf, f"{sender}: {content}", (670, 182 + i * 26), 14, s_col)

            if self.chat_mode:
                pygame.draw.rect(surf, gfx.PANEL2, (660, 565, 550, 38))
                pygame.draw.rect(surf, CYAN, (660, 565, 550, 38), 2)
                text(surf, self.chat_input + "_", (670, 584), 14, CYAN, "midleft")
            else:
                chat_hint_r = pygame.Rect(660, 565, 550, 38)
                c_hover = chat_hint_r.collidepoint((mx, my))
                pygame.draw.rect(surf, gfx.PANEL2 if c_hover else gfx.PANEL, chat_hint_r)
                text(surf, "CLICK OR PRESS T TO TYPE A MESSAGE", (670, 584), 13, AMBER if c_hover else GRAY, "midleft")

        if self.message:
            m_col = RED if ("NEED" in self.message or "LOW" in self.message) else GREEN
            text(surf, self.message, (65, 672), 16, m_col)
        text(surf, "CLAN DATA SAVES LOCALLY", (980, 672), 13, GRAY)


class ArmoryScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.skins = app.stats.skins()
        self.sel = 0
        self.message = ""

    def refresh(self):
        self.skins = self.app.stats.skins()
        if self.skins:
            self.sel %= len(self.skins)
        else:
            self.sel = 0

    def event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.app.pop()
        elif e.key == pygame.K_UP and self.skins:
            self.sel = (self.sel - 1) % len(self.skins)
        elif e.key == pygame.K_DOWN and self.skins:
            self.sel = (self.sel + 1) % len(self.skins)
        elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
            reward = self.app.stats.open_crate()
            if reward is None:
                self.message = "NO CRATES AVAILABLE - EARN ONE EVERY 5 LEVELS"
            else:
                prefix = "AVATAR FRAME: " if reward.get("type") == "AVATAR_FRAME" else "CRATE: "
                self.message = f"{prefix}{reward['rarity']} {reward['name']}" + (
                    " - LEGENDARY KILL EFFECT" if reward["kill_effect"] else "")
                self.refresh()
        elif e.key == pygame.K_e and self.skins:
            skin = self.skins[self.sel]
            self.message = "SKIN EQUIPPED" if self.app.stats.equip_skin(skin["id"]) else "COULD NOT EQUIP SKIN"

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        summary = self.app.stats.summary()
        text(surf, "ARMORY & CRATES", (50, 32), 42, AMBER)
        panel(surf, (50, 110, 360, 490))
        text(surf, f"PROFILE LEVEL {summary['level']}", (76, 132), 20, WHITE)
        text(surf, f"RANK {summary['rank']['tier'].upper()}  {summary['rank_points']} RP", (76, 168), 16, AMBER)
        text(surf, f"CRATES AVAILABLE: {summary['crates']}", (76, 224), 20, CYAN)
        text(surf, "ENTER: OPEN ONE FREE CRATE", (76, 270), 15, GRAY)
        text(surf, "LEVEL REWARDS", (76, 326), 17, AMBER)
        for i, (level, weapon_id) in enumerate(sorted(LEVEL_WEAPON_REWARDS.items())):
            unlocked = weapon_id in summary["unlocked_weapons"]
            text(surf, f"LV {level}: {weapons()[weapon_id]['name']}  {'UNLOCKED' if unlocked else 'LOCKED'}",
                 (76, 356 + i * 32), 13, WHITE if unlocked else GRAY)
        text(surf, "FREE CRATE EVERY 5 LEVELS", (76, 510), 14, GRAY)

        panel(surf, (450, 110, 780, 490))
        text(surf, f"WEAPON SKINS  -  {len(SKIN_DESIGNS)} DESIGNS", (476, 132), 20, AMBER)
        equipped = self.app.stats.equipped_skin_ids()
        if not self.skins:
            text(surf, "No skins yet. Open a crate to earn one.", (476, 184), 17, GRAY)
        else:
            start = min(max(0, self.sel - 7), max(0, len(self.skins) - 16))
            visible = self.skins[start:start + 16]
            for i, skin in enumerate(visible):
                index = start + i
                selected = index == self.sel
                equipped_mark = "  [EQUIPPED]" if equipped.get(skin["weapon_id"]) == skin["id"] else ""
                effect_mark = "  [KILL EFFECT]" if skin["kill_effect"] else ""
                text(surf, f"{'> ' if selected else '  '}{skin['name']} - {skin['weapon_name']}{equipped_mark}{effect_mark}",
                     (476, 176 + i * 20), 13 if index != self.sel else 14,
                     RARITY_COLORS[skin["rarity"]])
        if self.message:
            text(surf, self.message, (476, 548), 15, AMBER)
        text(surf, f"COINS {self.app.stats.coins():,}  -  100 WEAPON SKINS + AVATAR FRAMES  -  UP/DOWN SELECT  -  E EQUIP  -  ENTER CRATE",
             (50, 656), 13, GRAY)


class StoreScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.tab = 0
        self.sel = 0
        self.rarity_filter = "ALL"
        self.message = ""
        self.refresh()

    def refresh(self):
        self.owned_skins = {(skin["weapon_id"], skin["name"]) for skin in self.app.stats.skins()}
        if self.tab == 0:
            unlocked = self.app.stats.unlocked_weapon_ids()
            designs = [design for design in SKIN_DESIGNS
                       if self.rarity_filter == "ALL" or design["rarity"] == self.rarity_filter]
            self.items = [(weapon, design) for weapon in weapon_list() if weapon["id"] in unlocked
                          for design in designs]
        elif self.tab == 1:
            self.items = list(AVATAR_FRAMES)
        elif self.tab == 2:
            self.items = [item for item in SCORESTREAKS if item["price"] > 0]
        elif self.tab == 3:
            unlocked_streaks = self.app.stats.unlocked_scorestreak_ids()
            self.items = [(streak, skin) for streak in SCORESTREAKS if streak["id"] in unlocked_streaks
                          for skin in STREAK_SKINS]
        else:
            self.items = list(CALLING_CARDS)
        self.sel %= max(1, len(self.items))

    def event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.app.pop()
        elif e.key in (pygame.K_1, pygame.K_KP1):
            self.tab, self.sel = 0, 0
            self.refresh()
        elif e.key in (pygame.K_2, pygame.K_KP2):
            self.tab, self.sel = 1, 0
            self.refresh()
        elif e.key in (pygame.K_3, pygame.K_KP3):
            self.tab, self.sel = 2, 0
            self.refresh()
        elif e.key in (pygame.K_4, pygame.K_KP4):
            self.tab, self.sel = 3, 0
            self.refresh()
        elif e.key in (pygame.K_5, pygame.K_KP5):
            self.tab, self.sel = 4, 0
            self.refresh()
        elif self.tab == 0 and e.key == pygame.K_l:
            self.rarity_filter, self.sel = "LEGENDARY", 0
            self.refresh()
        elif self.tab == 0 and e.key == pygame.K_r:
            rarities = ("ALL", "COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY")
            self.rarity_filter = rarities[(rarities.index(self.rarity_filter) + 1) % len(rarities)]
            self.sel = 0
            self.refresh()
        elif e.key in (pygame.K_LEFT, pygame.K_UP):
            self.sel = (self.sel - 1) % max(1, len(self.items))
        elif e.key in (pygame.K_RIGHT, pygame.K_DOWN):
            self.sel = (self.sel + 1) % max(1, len(self.items))
        elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.purchase()

    def purchase(self):
        if not self.items:
            self.message = "NOTHING AVAILABLE IN THIS CATEGORY"
            return
        if self.tab == 0:
            weapon, design = self.items[self.sel]
            result = self.app.stats.buy_store_skin(weapon["id"], design["id"])
            if result["status"] == "insufficient_coins":
                self.message = f"NEED {result['price']:,} COINS FOR THIS SKIN"
            elif result["status"] == "unavailable":
                self.message = "ITEM IS NOT AVAILABLE"
            else:
                self.message = ("ALREADY OWNED - EQUIPPED: " if result["status"] == "already_owned"
                                else "PURCHASED & EQUIPPED: ") + result["name"]
                self.owned_skins.add((result["weapon_id"], result["name"]))
        elif self.tab == 1:
            frame = self.items[self.sel]
            if frame["source"] == "CRATE":
                self.message = "CRATE EXCLUSIVE - EARN IT FROM CRATES"
            elif frame["id"] in self.app.stats.unlocked_avatar_frames():
                self.app.stats.equip_avatar_frame(frame["id"])
                self.message = f"ALREADY OWNED - EQUIPPED: {frame['name']}"
            elif self.app.stats.buy_avatar_frame(frame["id"]):
                self.app.stats.equip_avatar_frame(frame["id"])
                self.message = f"PURCHASED & EQUIPPED: {frame['name']}"
            else:
                self.message = f"NEED {frame['price']:,} COINS FOR THIS FRAME"
        elif self.tab == 2:
            item = self.items[self.sel]
            result = self.app.stats.buy_scorestreak(item["id"])
            if result["status"] == "purchased": self.message = f"PURCHASED: {item['name']}"
            elif result["status"] == "insufficient_coins": self.message = f"NEED {result['price']:,} COINS"
            elif result["status"] == "level_locked": self.message = f"REACH LEVEL {result['level']} FIRST"
            elif result["status"] == "already_owned": self.message = f"ALREADY UNLOCKED: {item['name']}"
            else: self.message = "SCORESTREAK UNAVAILABLE"
            self.refresh()
        elif self.tab == 3:
            streak, skin = self.items[self.sel]
            result = self.app.stats.buy_scorestreak_skin(streak["id"], skin["id"])
            if result["status"] == "purchased": self.message = f"PURCHASED & EQUIPPED: {skin['name']}"
            elif result["status"] == "insufficient_coins": self.message = f"NEED {result['price']:,} COINS"
            elif result["status"] == "already_owned": self.message = f"EQUIPPED: {skin['name']}"
            else: self.message = "UNLOCK THE SCORESTREAK FIRST"
        else:
            card = self.items[self.sel]
            result = self.app.stats.buy_calling_card(card["id"])
            if result["status"] == "purchased":
                self.message = f"PURCHASED & EQUIPPED: {result['name']}"
            elif result["status"] == "already_owned":
                self.app.stats.equip_calling_card(card["id"])
                self.message = f"ALREADY OWNED - EQUIPPED: {result['name']}"
            elif result["status"] == "insufficient_coins":
                self.message = f"NEED {result['price']:,} COINS"
            else:
                self.message = "CALLING CARD UNAVAILABLE"
        self.app.audio.play("click", 0.8)

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "GAME STORE", (50, 32), 42, AMBER)
        text(surf, f"COINS {self.app.stats.coins():,}", (980, 48), 20, CYAN)
        panel(surf, (50, 110, 1180, 490))
        text(surf, "1  WEAPON SKINS" + ("  <" if self.tab == 0 else ""), (78, 132), 18,
             AMBER if self.tab == 0 else GRAY)
        text(surf, "2  AVATAR FRAMES" + ("  <" if self.tab == 1 else ""), (300, 132), 16,
             AMBER if self.tab == 1 else GRAY)
        text(surf, "3  SCORESTREAKS" + ("  <" if self.tab == 2 else ""), (480, 132), 16,
             AMBER if self.tab == 2 else GRAY)
        text(surf, "4  STREAK SKINS" + ("  <" if self.tab == 3 else ""), (680, 132), 16,
             AMBER if self.tab == 3 else GRAY)
        text(surf, "5  CALLING CARDS" + ("  <" if self.tab == 4 else ""), (870, 132), 16,
             AMBER if self.tab == 4 else GRAY)
        if self.tab == 0:
            text(surf, f"RARITY FILTER: {self.rarity_filter}", (94, 174), 16,
                 RARITY_COLORS.get(self.rarity_filter, CYAN))
        if self.tab == 0 and self.items:
            weapon, design = self.items[self.sel]
            price = STORE_SKIN_PRICES[design["rarity"]]
            name = (legendary_skin_name(weapon["name"], design["name"]) if design["rarity"] == "LEGENDARY"
                    else f"{design['name']} {weapon['name']}")
            owns = (weapon["id"], name) in self.owned_skins
            text(surf, name, (92, 230), 30, RARITY_COLORS[design["rarity"]])
            text(surf, f"{weapon['cat']}  /  {weapon['name']}  /  {design['rarity']}", (94, 282), 20, WHITE)
            text(surf, f"PRICE {price:,} COINS", (94, 330), 22, AMBER)
            text(surf, "OWNED - ENTER TO EQUIP" if owns else "ENTER TO PURCHASE AND EQUIP",
                 (94, 378), 18, GREEN if owns else CYAN)
            text(surf, f"ITEM {self.sel + 1:,} OF {len(self.items):,}", (94, 430), 16, GRAY)
            gfx.draw_weapon(surf, (760, 340), 0, design["rarity"], 4.0, self.t, name, weapon["id"])
            if design["rarity"] == "LEGENDARY":
                text(surf, "LEGENDARY SKINS GRANT A KILL EFFECT", (94, 474), 16, AMBER)
        elif self.tab == 2 and self.items:
            item = self.items[self.sel]
            text(surf, item["name"], (92, 230), 30, AMBER)
            text(surf, item["desc"], (94, 278), 16, WHITE)
            score_cost = "N/A" if item["id"] == "rc_xd" else (item["points"] if item["points"] is not None else "IMMEDIATE")
            text(surf, f"SCORE COST: {score_cost}", (94, 322), 18, CYAN)
            text(surf, f"STORE PRICE: {item['price']:,} COINS", (94, 358), 20, AMBER)
            text(surf, f"UNLOCK LEVEL: {item['unlock_level']}", (94, 394), 16, GRAY)
            text(surf, f"ITEM {self.sel + 1} OF {len(self.items)}  |  ENTER TO BUY", (94, 442), 16, GREEN)
            pygame.draw.circle(surf, CYAN, (790, 340), 92, 3)
            pygame.draw.line(surf, CYAN, (740, 340), (840, 340), 4)
            pygame.draw.line(surf, CYAN, (790, 290), (790, 390), 4)
        elif self.tab == 3 and self.items:
            streak, skin = self.items[self.sel]
            text(surf, skin["name"], (92, 230), 30, skin["color"])
            text(surf, f"FOR {streak['name']}", (94, 278), 20, WHITE)
            text(surf, f"PRICE {skin['price']:,} COINS", (94, 322), 22, AMBER)
            text(surf, "ENTER TO PURCHASE / EQUIP", (94, 370), 18, CYAN)
            text(surf, f"ITEM {self.sel + 1} OF {len(self.items)}", (94, 420), 16, GRAY)
            pygame.draw.circle(surf, skin["color"], (790, 340), 96, 5)
            pygame.draw.circle(surf, skin["color"], (790, 340), 60, 2)
            pygame.draw.line(surf, skin["color"], (730, 340), (850, 340), 4)
        elif self.tab == 4 and self.items:
            card = self.items[self.sel]
            owned = card["id"] in self.app.stats.owned_calling_card_ids()
            text(surf, card["name"], (92, 230), 30, RARITY_COLORS[card["rarity"]])
            text(surf, f"{card['rarity']}  /  CALLING CARD", (94, 282), 20, WHITE)
            if card["source"] == "FREE":
                text(surf, "DEFAULT CARD", (94, 330), 22, GREEN)
            elif owned:
                text(surf, "OWNED - ENTER TO EQUIP", (94, 330), 22, GREEN)
            else:
                text(surf, f"PRICE {card['price']:,} COINS", (94, 330), 22, AMBER)
                text(surf, "ENTER TO PURCHASE AND EQUIP", (94, 378), 18, CYAN)
            text(surf, f"ITEM {self.sel + 1} OF {len(self.items)}", (94, 430), 16, GRAY)
            gfx.draw_calling_card(surf, pygame.Rect(540, 265, 530, 170), card, t=self.t)
        elif self.tab == 1 and self.items:
            frame = self.items[self.sel]
            unlocked = frame["id"] in self.app.stats.unlocked_avatar_frames()
            text(surf, frame["name"], (92, 230), 30, RARITY_COLORS[frame["rarity"]])
            text(surf, f"{frame['rarity']}  /  {frame['animation'].upper()} FRAME", (94, 282), 20, WHITE)
            if frame["source"] == "CRATE":
                text(surf, "CRATE EXCLUSIVE", (94, 330), 22, AMBER)
                text(surf, "Earn this animated frame from a crate.", (94, 378), 18, GRAY)
            elif unlocked:
                text(surf, "OWNED - ENTER TO EQUIP", (94, 330), 22, GREEN)
            else:
                text(surf, f"PRICE {frame['price']:,} COINS", (94, 330), 22, AMBER)
                text(surf, "ENTER TO PURCHASE AND EQUIP", (94, 378), 18, CYAN)
            text(surf, f"ITEM {self.sel + 1} OF {len(self.items)}", (94, 430), 16, GRAY)
            gfx.draw_profile_avatar(surf, (760, 350), 170, self.app.stats.player_picture(), frame, self.t)
        if self.message:
            text(surf, self.message[:72], (78, 548), 16, AMBER)
        controls = ("1-5 CATEGORY  -  L LEGENDARY  -  R CYCLE RARITY  -  ARROWS BROWSE  -  ENTER BUY/EQUIP  -  ESC BACK"
                    if self.tab == 0 else "1-5 CATEGORY  -  ARROWS BROWSE  -  ENTER BUY/EQUIP  -  ESC BACK")
        text(surf, controls,
             (50, 656), 15, GRAY)


class HudEditorScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.selected = None
        self.dragging = False
        self.save_rect = pygame.Rect(CANVAS_W - 210, 34, 160, 42)

    def _canvas_pos(self, event):
        if hasattr(event, "pos"):
            return self.app.screen_to_canvas(event.pos)
        window_w, window_h = self.app.window.get_size()
        return self.app.screen_to_canvas((event.x * window_w, event.y * window_h))

    def _center(self, name):
        x, y, _ = self.app.settings["hud_controls"][name]
        return int(x * CANVAS_W), int(y * CANVAS_H)

    def _radius(self, name):
        return int(HUD_CONTROL_RADII[name] * self.app.settings["hud_controls"][name][2])

    def _hit_test(self, pos):
        for name in reversed(tuple(HUD_CONTROL_RADII)):
            if math.hypot(pos[0] - self._center(name)[0], pos[1] - self._center(name)[1]) <= self._radius(name):
                return name
        return None

    def _move_selected(self, pos):
        if self.selected is None:
            return
        radius = self._radius(self.selected)
        x = min(CANVAS_W - radius, max(radius, pos[0])) / CANVAS_W
        y = min(CANVAS_H - radius, max(radius, pos[1])) / CANVAS_H
        self.app.settings["hud_controls"][self.selected][:2] = [x, y]

    def _resize(self, amount):
        if self.selected is None:
            return
        control = self.app.settings["hud_controls"][self.selected]
        control[2] = round(min(1.5, max(0.5, control[2] + amount)), 2)

    def event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.settings.save()
                self.app.pop()
            elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self._resize(0.1)
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self._resize(-0.1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.app.settings.save()
        elif event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", None) == 1:
            pos = self._canvas_pos(event)
            if self.save_rect.collidepoint(pos):
                self.app.settings.save()
                return
            self.selected = self._hit_test(pos)
            self.dragging = self.selected is not None
            self._move_selected(pos)
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._move_selected(self._canvas_pos(event))
        elif event.type == pygame.MOUSEBUTTONUP and self.dragging:
            self._move_selected(self._canvas_pos(event))
            self.dragging = False
            self.app.settings.save()
        elif event.type == getattr(pygame, "MOUSEWHEEL", -1):
            self._resize(event.y * 0.05)
        elif event.type == getattr(pygame, "FINGERDOWN", -1):
            self.app.touch_enabled = True
            pos = self._canvas_pos(event)
            if self.save_rect.collidepoint(pos):
                self.app.settings.save()
            else:
                self.selected = self._hit_test(pos)
                self.dragging = self.selected is not None
                self._move_selected(pos)
        elif event.type == getattr(pygame, "FINGERMOTION", -1) and self.dragging:
            self._move_selected(self._canvas_pos(event))
        elif event.type == getattr(pygame, "FINGERUP", -1) and self.dragging:
            self._move_selected(self._canvas_pos(event))
            self.dragging = False
            self.app.settings.save()

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "CUSTOMIZE MOBILE HUD", (48, 34), 34, AMBER)
        text(surf, "DRAG CONTROLS  /  +/- OR MOUSE WHEEL TO RESIZE  /  ENTER TO SAVE",
             (52, 86), 15, CYAN)
        text(surf, "PREVIEW CONTROLS ARE SAVED LOCALLY AND USED ON TOUCHSCREENS",
             (52, 112), 13, GRAY)
        panel(surf, (36, 150, 1208, 504))
        pygame.draw.rect(surf, (14, 25, 30), (52, 166, 1176, 472))
        pygame.draw.line(surf, (37, 76, 80), (640, 166), (640, 638), 1)
        for name, label in HUD_CONTROL_LABELS.items():
            center = self._center(name)
            radius = self._radius(name)
            color = AMBER if name == self.selected else CYAN if name in ("move", "aim") else GREEN
            pygame.draw.circle(surf, (20, 42, 48), center, radius)
            pygame.draw.circle(surf, color, center, radius, 3 if name == self.selected else 2)
            text(surf, label, center, max(11, min(16, radius // 3)), WHITE, "center")
        pygame.draw.rect(surf, AMBER, self.save_rect, 2)
        text(surf, "SAVE HUD", self.save_rect.center, 16, AMBER, "center")
        text(surf, "ESC BACK  /  DRAG BUTTONS TO REPOSITION", (52, 670), 14, GRAY)


class SettingsScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        S = "slider"
        self.rows = [("MASTER VOLUME", S, "master", 0, 1, .05), ("MUSIC VOLUME", S, "music", 0, 1, .05), ("SOUND EFFECTS VOLUME", S, "sfx", 0, 1, .05),
                     ("RESOLUTION", "choice", "res", [f"{w}x{h}" for w, h in RESOLUTIONS]), ("FULLSCREEN", "toggle", "fullscreen"),
                     ("FRAME RATE CAP", "choice", "fps", [str(f) if f else "UNCAPPED" for f in FPS_CAPS]),
                     ("MOUSE SENSITIVITY", S, "mouse_sens", .3, 3.0, .1), ("AIM (ADS) SENSITIVITY", S, "aim_sens", .2, 1.5, .1),
                     ("SCREEN SHAKE", "toggle", "shake"), ("VISUAL EFFECTS", "choice", "fx", ["LOW", "HIGH"]),
                     ("AI DIFFICULTY", "choice", "difficulty", ORDER), ("SHOW TACTICAL MAP", "toggle", "minimap"),
                     ("MINIMAP SIZE", "choice", "minimap_size", ["SMALL", "MEDIUM", "LARGE"]), ("HUD SCALE", S, "ui_scale", .8, 1.4, .1)]
        self.rows += [(f"KEY: {lbl}", "key", k) for k, lbl in KEY_LABELS] + [("RESET TO DEFAULTS", "reset")]
        self.sel = 0
        self.waiting = None
        self.dragging = None
        self.back_rect = pygame.Rect(46, 44, 126, 38)

    def idx(self, row):
        v = self.app.settings[row[2]]
        return row[3].index(v) if isinstance(v, str) else int(v)

    def adjust(self, d):
        row, s = self.rows[self.sel], self.app.settings
        kind = row[1]
        if kind == "slider":
            s[row[2]] = round(min(row[4], max(row[3], s[row[2]] + d * row[5])), 3)
        elif kind == "toggle":
            s[row[2]] = not s[row[2]]
        elif kind == "choice":
            opts = row[3]
            i = (self.idx(row) + d) % len(opts)
            s[row[2]] = opts[i] if isinstance(s[row[2]], str) else i
        elif kind == "key" and d == 0:
            self.waiting = row[2]
        elif kind == "reset" and d == 0:
            s.reset()
            self.app.apply_display()
        if len(row) > 2 and row[2] in ("res", "fullscreen", "fps"):
            self.app.apply_display()
        self.app.audio.update_volumes()
        s.save()

    def rect(self, i):
        return pygame.Rect(200, 120 + i * 38, 880, 34)

    def window(self):
        start = max(0, min(self.sel - 6, len(self.rows) - 13))
        return start, min(len(self.rows), start + 13)

    def event(self, e):
        if self.waiting and e.type == pygame.KEYDOWN:
            if e.key != pygame.K_ESCAPE:
                self.app.settings["keys"][self.waiting] = pygame.key.name(e.key)
                self.app.settings.save()
            self.waiting = None
            return
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.app.settings.save()
                self.app.pop()
            elif e.key == pygame.K_UP:
                self.sel = (self.sel - 1) % len(self.rows)
            elif e.key == pygame.K_DOWN:
                self.sel = (self.sel + 1) % len(self.rows)
            elif e.key == pygame.K_LEFT:
                self.adjust(-1)
            elif e.key == pygame.K_RIGHT:
                self.adjust(1)
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.adjust(1 if self.rows[self.sel][1] not in ("key", "reset") else 0)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = self.app.mouse()
            if self.back_rect.collidepoint(pos):
                self.app.settings.save()
                self.app.pop()
                return
            a, b = self.window()
            for i in range(a, b):
                r = self.rect(i - a)
                if r.collidepoint(pos):
                    self.sel = i
                    row = self.rows[i]
                    kind = row[1]
                    if kind == "slider":
                        slider_box = pygame.Rect(r.x + 520, r.y + 6, 220, 22)
                        if slider_box.collidepoint(pos):
                            frac = max(0.0, min(1.0, (pos[0] - slider_box.x) / slider_box.width))
                            s = self.app.settings
                            s[row[2]] = round(row[3] + frac * (row[4] - row[3]), 3)
                            self.dragging = i
                            self.app.audio.update_volumes()
                            s.save()
                        else:
                            self.adjust(1 if pos[0] > r.centerx else -1)
                    elif kind in ("key", "reset"):
                        self.adjust(0)
                    else:
                        self.adjust(1 if pos[0] > r.centerx else -1)
        elif e.type == pygame.MOUSEMOTION and self.dragging is not None:
            pos = self.app.mouse()
            a, b = self.window()
            if a <= self.dragging < b:
                r = self.rect(self.dragging - a)
                row = self.rows[self.dragging]
                if row[1] == "slider":
                    slider_box = pygame.Rect(r.x + 520, r.y + 6, 220, 22)
                    frac = max(0.0, min(1.0, (pos[0] - slider_box.x) / slider_box.width))
                    s = self.app.settings
                    s[row[2]] = round(row[3] + frac * (row[4] - row[3]), 3)
                    self.app.audio.update_volumes()
                    s.save()
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.dragging = None

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        pos = self.app.mouse()
        b_hover = self.back_rect.collidepoint(pos)
        pygame.draw.rect(surf, gfx.PANEL2 if b_hover else gfx.PANEL, self.back_rect, border_radius=4)
        pygame.draw.rect(surf, AMBER if b_hover else GREEN, self.back_rect, 2, border_radius=4)
        text(surf, "< BACK", self.back_rect.center, 16, AMBER if b_hover else WHITE, "center")

        text(surf, "SYSTEM SETTINGS", (200, 50), 38, AMBER)
        text(surf, "TACTICAL CONFIGURATION & KEYBINDS", (204, 90), 12, GRAY)

        a, b = self.window()
        s = self.app.settings
        for i in range(a, b):
            row = self.rows[i]
            r = self.rect(i - a)
            sel = i == self.sel
            pygame.draw.rect(surf, gfx.PANEL2 if sel else gfx.PANEL, r, border_radius=3)
            pygame.draw.rect(surf, AMBER if sel else (38, 54, 46), r, 1, border_radius=3)
            if sel:
                pygame.draw.rect(surf, AMBER, (r.x, r.y, 4, r.height), border_radius=2)
            text(surf, row[0], (r.x + 16, r.centery), 16, AMBER if sel else WHITE, "midleft")
            kind = row[1]
            if kind == "slider":
                frac = (s[row[2]] - row[3]) / (row[4] - row[3])
                track_r = pygame.Rect(r.x + 520, r.y + 9, 220, 16)
                bar(surf, track_r, frac, AMBER)
                knob_x = int(track_r.x + frac * track_r.width)
                pygame.draw.circle(surf, WHITE, (knob_x, track_r.centery), 7)
                pygame.draw.circle(surf, AMBER, (knob_x, track_r.centery), 5)
                text(surf, f"{s[row[2]]:.2f}", (r.right - 14, r.centery), 16, WHITE, "midright")
            elif kind == "toggle":
                text(surf, "ON" if s[row[2]] else "OFF", (r.right - 14, r.centery), 18, CYAN if s[row[2]] else GRAY, "midright")
            elif kind == "choice":
                text(surf, f"< {row[3][self.idx(row)]} >", (r.right - 14, r.centery), 18, CYAN, "midright")
            elif kind == "key":
                lbl = "PRESS A KEY..." if self.waiting == row[2] else s["keys"][row[2]].upper()
                text(surf, lbl, (r.right - 14, r.centery), 18, AMBER if self.waiting == row[2] else CYAN, "midright")
            elif kind == "reset":
                text(surf, "[ ENTER TO RESET ]", (r.right - 14, r.centery), 14, RED, "midright")
        text(surf, "NAVIGATE: UP/DOWN  |  ADJUST: LEFT/RIGHT OR CLICK SLIDER  |  SELECT/REBIND: ENTER  |  BACK: ESC", (200, 646), 13, GRAY)


class MapSelect(Scene):
    def __init__(self, app, flow):
        super().__init__(app)
        self.flow = flow
        self.ranked = bool(flow.get("ranked", False))
        self.team_size = int(flow.get("team_size", 5))
        self.metas = maps_meta()
        self.sel = 0
        self.mode_i = 0
        self.cache = {}

    def preview(self, i):
        mid = self.metas[i]["id"]
        if mid not in self.cache:
            self.cache[mid] = gfx.map_preview(load_map(mid), 540, 330)
        return self.cache[mid]

    def go(self):
        self.flow["mode"] = MODE_ORDER[self.mode_i]
        self.flow["map"] = self.metas[self.sel]["id"]
        self.flow["ranked"] = self.ranked
        self.flow["team_size"] = self.team_size
        self.app.push(CharacterScene(self.app, self.flow))

    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.app.pop()
            elif e.key == pygame.K_UP:
                self.sel = (self.sel - 1) % len(self.metas)
            elif e.key == pygame.K_DOWN:
                self.sel = (self.sel + 1) % len(self.metas)
            elif e.key == pygame.K_r:
                self.ranked = not self.ranked
            elif e.key == pygame.K_t:
                self.team_size = 15 - self.team_size
            elif e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                self.mode_i = (self.mode_i + (-1 if e.key == pygame.K_LEFT else 1)) % len(MODE_ORDER)
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.go()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = self.app.mouse()
            for i in range(len(MODE_ORDER)):
                if pygame.Rect(60 + i * 250, 100, 240, 44).collidepoint(pos):
                    self.mode_i = i
            for i in range(len(self.metas)):
                if pygame.Rect(60 + (i // 6) * 220, 220 + (i % 6) * 66, 210, 58).collidepoint(pos):
                    if self.sel == i:
                        self.go()
                    self.sel = i
            if pygame.Rect(900, 100, 290, 44).collidepoint(pos):
                self.ranked = not self.ranked
            if pygame.Rect(CX + 250, 650, 300, 44).collidepoint(pos):
                self.go()

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "SELECT MAP", (60, 30), 44, AMBER)
        for i, mid in enumerate(MODE_ORDER):
            r = pygame.Rect(60 + i * 250, 100, 240, 44)
            sel = i == self.mode_i
            panel(surf, r, AMBER if sel else GREEN, gfx.PANEL2 if sel else gfx.PANEL)
            text(surf, MODES[mid].name, r.center, 16, AMBER if sel else WHITE, "center")
        rank = self.app.stats.rank()
        rr = pygame.Rect(900, 100, 290, 44)
        panel(surf, rr, AMBER if self.ranked else GREEN, gfx.PANEL2 if self.ranked else gfx.PANEL)
        label = f"RANKED: {rank['tier'].upper()} {rank['points']} RP" if self.ranked else "CASUAL  (R TOGGLE RANKED)"
        text(surf, label, rr.center, 14, AMBER if self.ranked else GRAY, "center")
        text(surf, MODES[MODE_ORDER[self.mode_i]].desc, (60, 156), 14, GRAY)
        text(surf, "LEFT/RIGHT: MODE   UP/DOWN: MAP   R: RANKED/NORMAL   T: 5v5/10v10   ENTER: CONTINUE", (60, 186), 13, GREEN)
        tr = pygame.Rect(900, 152, 290, 36)
        panel(surf, tr, CYAN, gfx.PANEL)
        text(surf, f"TEAM SIZE: {self.team_size}v{self.team_size}  (T)", tr.center, 16, CYAN, "center")
        for i, m in enumerate(self.metas):
            r = pygame.Rect(60 + (i // 6) * 220, 220 + (i % 6) * 66, 210, 58)
            sel = i == self.sel
            panel(surf, r, AMBER if sel else GREEN, gfx.PANEL2 if sel else gfx.PANEL)
            if sel:
                pygame.draw.polygon(surf, AMBER, [
                    (r.right - 15, r.y + 8), (r.right - 8, r.y + 8), (r.right - 8, r.y + 15),
                ])
            text(surf, m["name"], (r.x + 10, r.y + 6), 17, AMBER if sel else WHITE)
            text(surf, f"{m['size']}   DIFFICULTY {'*' * m['rating']}{'.' * (5 - m['rating'])}", (r.x + 10, r.y + 34), 11, GRAY)
        m = self.metas[self.sel]
        px, py = 510, 220
        panel(surf, (px, py - 10, 700, 430))
        prev = self.preview(self.sel)
        preview_rect = pygame.Rect(px + 10 + (540 - prev.get_width()) // 2, py + (330 - prev.get_height()) // 2,
                                   prev.get_width(), prev.get_height())
        pygame.draw.rect(surf, (5, 8, 8), (preview_rect.x + 4, preview_rect.y + 4,
                                          preview_rect.w, preview_rect.h))
        pygame.draw.rect(surf, CYAN, (preview_rect.x - 2, preview_rect.y - 2,
                                      preview_rect.w + 4, preview_rect.h + 4), 2)
        surf.blit(prev, (px + 10 + (540 - prev.get_width()) // 2, py + (330 - prev.get_height()) // 2))
        text(surf, f"{m['name']}  -  {m['size']}", (px + 14, py + 332), 20, AMBER)
        gm = self.cache[m["id"]]
        lm = load_map(m["id"])
        text(surf, f"{lm.w}x{lm.h} TILES", (px + 14, py + 360), 14, CYAN)
        words, line, y = m["desc"].split(), "", py + 384
        for w in words:
            if len(line) + len(w) > 78:
                text(surf, line, (px + 14, y), 14, WHITE)
                y += 18
                line = ""
            line += w + " "
        text(surf, line, (px + 14, y), 14, WHITE)
        text(surf, "BLUE = ALPHA SPAWN   ORANGE = BRAVO SPAWN   AMBER = OBJECTIVES", (px + 14, py + 396), 11, GRAY)
        panel(surf, (CX + 250, 650, 300, 44), AMBER, gfx.PANEL2)
        text(surf, "CONTINUE >", (CX + 400, 672), 20, AMBER, "center")


class CampaignScene(Scene):
    def __init__(self, app, selected=None):
        super().__init__(app)
        self.progress = app.stats.campaign_progress()
        self.selected = (min(self.progress, len(CAMPAIGN_MISSIONS) - 1)
                         if selected is None else max(0, min(selected, len(CAMPAIGN_MISSIONS) - 1)))
        self.map_cache = {}

    def mission_rect(self, index):
        return pygame.Rect(48, 128 + index * 56, 520, 48)

    @staticmethod
    def wrap(text_value, width):
        lines, line = [], ""
        for word in text_value.split():
            if line and len(line) + len(word) + 1 > width:
                lines.append(line)
                line = ""
            line = f"{line} {word}".strip()
        if line:
            lines.append(line)
        return lines

    def start(self):
        if self.selected > self.progress:
            return
        mission = campaign_mission(self.selected)
        flow = dict(mode=mission["mode"], map=mission["map"], ranked=False,
                    campaign_mission=self.selected)
        self.app.push(CharacterScene(self.app, flow))

    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.app.pop()
            elif e.key in (pygame.K_UP, pygame.K_LEFT):
                self.selected = (self.selected - 1) % len(CAMPAIGN_MISSIONS)
            elif e.key in (pygame.K_DOWN, pygame.K_RIGHT):
                self.selected = (self.selected + 1) % len(CAMPAIGN_MISSIONS)
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = self.app.mouse()
            for index in range(len(CAMPAIGN_MISSIONS)):
                if self.mission_rect(index).collidepoint(pos):
                    if self.selected == index:
                        self.start()
                    self.selected = index
                    return
            if pygame.Rect(900, 584, 300, 42).collidepoint(pos):
                self.start()

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "CAMPAIGN", (48, 28), 42, AMBER)
        completed = min(self.progress, len(CAMPAIGN_MISSIONS))
        text(surf, f"OPERATION ASHEN SIGNAL     {completed}/{len(CAMPAIGN_MISSIONS)} CHAPTERS",
             (50, 82), 15, CYAN)
        for index, mission in enumerate(CAMPAIGN_MISSIONS):
            rect = self.mission_rect(index)
            unlocked = index <= self.progress
            done = index < self.progress
            active = index == self.selected
            border = AMBER if active else GREEN if unlocked else gfx.DIM
            fill = gfx.PANEL2 if active else gfx.PANEL
            panel(surf, rect, border, fill)
            status = "COMPLETE" if done else "AVAILABLE" if unlocked else "LOCKED"
            status_color = (110, 230, 120) if done else CYAN if unlocked else GRAY
            text(surf, f"{index + 1:02}  {mission['codename']}", (rect.x + 12, rect.y + 6),
                 12, AMBER if active else WHITE)
            text(surf, mission["name"], (rect.x + 12, rect.y + 25), 14, WHITE if unlocked else GRAY)
            text(surf, status, (rect.right - 10, rect.y + 9), 9, status_color, "topright")

        mission = campaign_mission(self.selected)
        panel(surf, (600, 128, 632, 522), AMBER if self.selected <= self.progress else GREEN, gfx.PANEL)
        text(surf, f"CHAPTER {self.selected + 1}  /  FIELD DOSSIER", (624, 144), 12, CYAN)
        text(surf, mission["name"], (624, 166), 25, AMBER)
        meta = next(item for item in maps_meta() if item["id"] == mission["map"])
        if mission["map"] not in self.map_cache:
            self.map_cache[mission["map"]] = gfx.map_preview(load_map(mission["map"]), 570, 220)
        preview = self.map_cache[mission["map"]]
        surf.blit(preview, (631 + (570 - preview.get_width()) // 2, 204))
        text(surf, f"{meta['name']}  -  {MODES[mission['mode']].name}",
             (624, 432), 14, CYAN)
        text(surf, "MISSION BRIEF", (624, 460), 11, GRAY)
        for line_index, line in enumerate(self.wrap(mission["briefing"], 68)[:3]):
            text(surf, line, (624, 480 + line_index * 16), 11, WHITE)
        text(surf, f"OBJECTIVE: {mission['objective']}", (624, 534), 11, AMBER)
        text(surf, f"RECOMMENDED AI: {mission['recommended']}", (624, 556), 10, GRAY)
        start_rect = pygame.Rect(900, 584, 300, 42)
        if self.selected <= self.progress:
            pygame.draw.rect(surf, AMBER, start_rect, 2)
            text(surf, "DEPLOY  >", start_rect.center, 18, AMBER, "center")
        else:
            text(surf, "COMPLETE EARLIER CHAPTERS TO UNLOCK", (624, 588), 10, GRAY)
        text(surf, "UP/DOWN SELECT  -  ENTER DEPLOY  -  ESC BACK",
             (48, 680), 13, GRAY)


class CharacterScene(Scene):
    def __init__(self, app, flow=None):
        super().__init__(app)
        self.flow = flow
        self.chars = characters()
        cur = app.settings["loadout"]["char"]
        self.sel = next((i for i, c in enumerate(self.chars) if c["id"] == cur), 0)

    def rect(self, i):
        return pygame.Rect(40 + (i % 4) * 215, 110 + (i // 4) * 180, 205, 170)

    def confirm(self):
        s = self.app.settings
        s["loadout"]["char"] = self.chars[self.sel]["id"]
        active_slot = s["active_loadout_slot"] - 1
        s["loadout_slots"][active_slot] = dict(s["loadout"])
        s["loadout"] = s["loadout_slots"][active_slot]
        s.save()
        if self.flow is not None:
            self.app.push(LoadoutScene(self.app, self.flow))
        else:
            self.app.pop()

    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.app.pop()
            elif e.key == pygame.K_LEFT:
                self.sel = (self.sel - 1) % 8
            elif e.key == pygame.K_RIGHT:
                self.sel = (self.sel + 1) % 8
            elif e.key == pygame.K_UP:
                self.sel = (self.sel - 4) % 8
            elif e.key == pygame.K_DOWN:
                self.sel = (self.sel + 4) % 8
            elif e.key == pygame.K_c:
                lvl = level_for(self.app.stats.summary()["xp"])
                n = [i for i, t in enumerate(TRIMS) if t[0] <= lvl]
                s = self.app.settings
                s["trim"] = n[(n.index(s["trim"]) + 1) % len(n)] if s["trim"] in n else n[0]
                s.save()
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.confirm()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = self.app.mouse()
            for i in range(8):
                if self.rect(i).collidepoint(pos):
                    if self.sel == i:
                        self.confirm()
                    self.sel = i

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "SELECT OPERATOR", (40, 30), 44, AMBER)
        for i, c in enumerate(self.chars):
            r = self.rect(i)
            sel = i == self.sel
            pygame.draw.rect(surf, gfx.PANEL2 if sel else gfx.PANEL, r)
            pygame.draw.rect(surf, AMBER if sel else GREEN, r, 2)
            spr = gfx.char_sprite(c, 0, self.t * 1.2 if sel else 0.0)
            big = pygame.transform.scale(spr, (spr.get_width() * 2, spr.get_height() * 2))
            surf.blit(big, big.get_rect(center=(r.centerx, r.y + 62)))
            text(surf, c["name"], (r.centerx, r.y + 118), 18, AMBER if sel else WHITE, "midtop")
            text(surf, c["role"], (r.centerx, r.y + 142), 13, GRAY, "midtop")
        c = self.chars[self.sel]
        panel(surf, (910, 110, 340, 540))
        text(surf, c["name"], (926, 122), 28, tuple(c["color"]))
        text(surf, c["role"], (926, 156), 16, AMBER)
        y = 186
        for ln in (c["desc"], f"HEALTH {c['hp']}   SPEED {c['speed']:.2f}x"):
            text(surf, ln, (926, y), 13, WHITE)
            y += 22
        gfx.ability_icon(surf, c["ability"]["id"], pygame.Rect(926, y + 6, 54, 54))
        text(surf, c["ability"]["name"], (990, y + 8), 15, AMBER)
        text(surf, f"COOLDOWN {c['ability']['cooldown']}s  (SPACE)", (990, y + 30), 12, GRAY)
        y += 72
        for ln in self.wrap(c["ability"]["desc"], 38):
            text(surf, ln, (926, y), 12, WHITE)
            y += 17
        y += 10
        text(surf, "PASSIVE: " + c["passive"]["name"], (926, y), 15, CYAN)
        y += 24
        for ln in self.wrap(c["passive"]["desc"], 38):
            text(surf, ln, (926, y), 12, WHITE)
            y += 17
        y += 12
        text(surf, "+ " + c["strength"], (926, y), 12, (110, 220, 120))
        text(surf, "- " + c["weakness"], (926, y + 20), 12, RED)
        tn = TRIMS[min(self.app.settings["trim"], len(TRIMS) - 1)][1]
        text(surf, f"C: TRIM COLOR [{tn}]", (926, 628), 13, GRAY)
        text(surf, "ARROWS SELECT  -  ENTER CONFIRM  -  ESC BACK", (40, 680), 14, GRAY)

    @staticmethod
    def wrap(s, n):
        out, line = [], ""
        for w in s.split():
            if len(line) + len(w) + 1 > n:
                out.append(line)
                line = ""
            line += w + " "
        return out + [line]


class LoadoutScene(Scene):
    def __init__(self, app, flow=None):
        super().__init__(app)
        self.flow = flow
        self.slots = app.settings["loadout_slots"]
        self.slot = app.settings["active_loadout_slot"]
        self.lo = app.settings["loadout"]
        self.unlocked = app.stats.unlocked_weapon_ids()
        self.rarity_filter = "ALL"
        wl = weapons()
        self.cat = wl[self.lo["primary"]]["cat"] if wl[self.lo["primary"]]["cat"] in CATEGORY_ORDER else "AR"
        if self.lo["primary"] not in self.unlocked:
            self.lo["primary"] = self.prim_list()[0]["id"]
        if self.lo["secondary"] not in self.unlocked:
            self.lo["secondary"] = self.sec_list()[0]["id"]
        self.rows = ["LOADOUT SLOT", "CATEGORY", "RARITY FILTER", "PRIMARY", "PRIMARY SKIN",
                     "SECONDARY", "SECONDARY SKIN", "EQUIPMENT"]
        self.sel = 0
        self.nav_focus = "WEAPONS"
        self.streak_index = 0
        self.streak_slot = 0
        self.streak_message = "SELECT A STREAK, THEN EQUIP IT TO A SLOT"
        self.maxes = {k: max(w[k] * (w["pellets"] if k == "dmg" else 1) for w in weapon_list()) for k in ("dmg", "rate", "range", "mag")}

    def matches_rarity(self, weapon):
        return self.rarity_filter == "ALL" or weapon_rarity(weapon) == self.rarity_filter

    def prim_list(self):
        return [w for w in weapon_list()
                if w["cat"] == self.cat and w["id"] in self.unlocked and self.matches_rarity(w)]

    def sec_list(self):
        return [w for w in weapon_list()
                if w["cat"] in ("PISTOL", "MELEE", "EXPLOSIVE") and w["id"] in self.unlocked
                and self.matches_rarity(w)]

    def change_rarity_filter(self, d):
        rarities = ("ALL", "COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY")
        current = rarities.index(self.rarity_filter)
        self.rarity_filter = rarities[(current + d) % len(rarities)]
        primary_matches = self.prim_list()
        if primary_matches:
            if self.lo["primary"] not in {weapon["id"] for weapon in primary_matches}:
                self.lo["primary"] = primary_matches[0]["id"]
        else:
            for category in CATEGORY_ORDER:
                self.cat = category
                primary_matches = self.prim_list()
                if primary_matches:
                    self.lo["primary"] = primary_matches[0]["id"]
                    break
        secondary_matches = self.sec_list()
        if secondary_matches and self.lo["secondary"] not in {weapon["id"] for weapon in secondary_matches}:
            self.lo["secondary"] = secondary_matches[0]["id"]

    def save_slot(self):
        self.slots[self.slot - 1] = dict(self.lo)
        self.app.settings["loadout"] = self.slots[self.slot - 1]
        self.app.settings["active_loadout_slot"] = self.slot

    def change_slot(self, d):
        self.select_slot((self.slot - 1 + d) % len(self.slots) + 1)

    def select_slot(self, slot):
        if slot == self.slot:
            return
        self.save_slot()
        self.slot = slot
        self.lo = dict(self.slots[self.slot - 1])
        self.lo.setdefault("scorestreaks", ["uav", "hunter_killer", "shield_turret"])
        self.app.settings["loadout"] = self.lo
        self.app.settings["active_loadout_slot"] = self.slot
        self.cat = weapons()[self.lo["primary"]]["cat"]
        if self.cat not in CATEGORY_ORDER:
            self.cat = "AR"
        self.rarity_filter = "ALL"

    def change(self, d):
        r = self.rows[self.sel]
        if r == "LOADOUT SLOT":
            self.change_slot(d)
        elif r == "CATEGORY":
            self.cat = CATEGORY_ORDER[(CATEGORY_ORDER.index(self.cat) + d) % len(CATEGORY_ORDER)]
            choices = self.prim_list()
            if choices:
                self.lo["primary"] = choices[0]["id"]
        elif r == "RARITY FILTER":
            self.change_rarity_filter(d)
        elif r in ("PRIMARY", "SECONDARY"):
            lst = self.prim_list() if r == "PRIMARY" else self.sec_list()
            if not lst:
                self.app.audio.play("click", 0.5)
                return
            key = "primary" if r == "PRIMARY" else "secondary"
            ids = [w["id"] for w in lst]
            cur = ids.index(self.lo[key]) if self.lo[key] in ids else 0
            self.lo[key] = ids[(cur + d) % len(ids)]
        elif r in ("PRIMARY SKIN", "SECONDARY SKIN"):
            weapon_key = "primary" if r == "PRIMARY SKIN" else "secondary"
            weapon_id = self.lo[weapon_key]
            skins = self.app.stats.skins_for_weapon(weapon_id)
            equipped = self.app.stats.equipped_skin_ids().get(weapon_id)
            skin_ids = [None] + [skin["id"] for skin in skins]
            current = skin_ids.index(equipped) if equipped in skin_ids else 0
            selected = skin_ids[(current + d) % len(skin_ids)]
            if selected is None:
                self.app.stats.unequip_skin(weapon_id)
            else:
                self.app.stats.equip_skin(selected)
        else:
            keys = list(EQUIPMENT)
            self.lo["equipment"] = keys[(keys.index(self.lo["equipment"]) + d) % len(keys)]
        self.app.audio.play("click", 0.5)

    def done(self):
        self.save_slot()
        self.app.settings.save()
        if self.flow is not None:
            self.app.push(BriefingScene(self.app, self.flow))
        else:
            self.app.pop()

    def navrect(self, i):
        return pygame.Rect(32, 130 + i * 64, 132, 54)

    def primary_rect(self):
        return pygame.Rect(520, 132, 350, 250)

    def secondary_rect(self):
        return pygame.Rect(882, 132, 366, 250)

    def equipment_rect(self):
        return pygame.Rect(520, 398, 728, 158)

    def open_character_select(self):
        self.save_slot()
        self.app.push(CharacterScene(self.app))

    def sync_nav_focus(self):
        row = self.rows[self.sel]
        self.nav_focus = ("SKINS" if "SKIN" in row else
                          "EQUIPMENT" if row == "EQUIPMENT" else "WEAPONS")

    def streak_owned(self, item):
        return item["id"] in self.app.stats.unlocked_scorestreak_ids()

    def equip_streak(self):
        item = SCORESTREAKS[self.streak_index]
        if not self.streak_owned(item):
            self.streak_message = "LOCKED - PRESS B TO BUY IN THE SCORESTREAK STORE"
            return
        current = list(self.lo.get("scorestreaks", ["uav", "hunter_killer", "shield_turret"]))
        while len(current) < 3:
            current.append("uav")
        current[self.streak_slot] = item["id"]
        self.lo["scorestreaks"] = current[:3]
        self.streak_message = f"{item['name'].upper()} EQUIPPED IN SLOT {self.streak_slot + 1}"
        self.save_slot()

    def buy_streak(self):
        item = SCORESTREAKS[self.streak_index]
        result = self.app.stats.buy_scorestreak(item["id"])
        if result["status"] == "purchased":
            self.streak_message = f"UNLOCKED: {item['name'].upper()}"
        elif result["status"] == "insufficient_coins":
            self.streak_message = f"NOT ENOUGH CREDITS - NEED {result['price']}"
        elif result["status"] == "level_locked":
            self.streak_message = f"REACH LEVEL {result['level']} TO ACCESS THIS STREAK"
        elif result["status"] == "already_owned":
            self.streak_message = f"{item['name'].upper()} ALREADY UNLOCKED"
        else:
            self.streak_message = "THIS SCORESTREAK IS UNAVAILABLE"

    def buy_streak_skin(self):
        item = SCORESTREAKS[self.streak_index]
        if not self.streak_owned(item):
            self.streak_message = "UNLOCK THE SCORESTREAK FIRST"
            return
        skins = self.app.stats.owned_scorestreak_skins(item["id"])
        owned_ids = {skin["id"] for skin in skins}
        skin = next((skin for skin in STREAK_SKINS if skin["id"] not in owned_ids), STREAK_SKINS[0])
        result = self.app.stats.buy_scorestreak_skin(item["id"], skin["id"])
        if result["status"] == "purchased":
            self.streak_message = f"SKIN UNLOCKED: {skin['name'].upper()}"
        elif result["status"] == "insufficient_coins":
            self.streak_message = f"NOT ENOUGH CREDITS - NEED {result['price']}"
        elif result["status"] == "already_owned":
            self.streak_message = f"EQUIPPED SKIN: {skin['name'].upper()}"
        else:
            self.streak_message = "SKIN UNAVAILABLE"

    def draw_streaks(self, surf):
        text(surf, "SCORESTREAK ARMORY", (180, 112), 25, AMBER)
        text(surf, f"PLAYER LEVEL {self.app.stats.scorestreak_level()}   |   CREDITS {self.app.stats.coins()}",
             (1218, 119), 12, CYAN, "topright")
        text(surf, "CHOOSE ANY THREE. LEVEL UNLOCKS, STORE PURCHASES, AND COSMETIC SKINS ARE SAVED.",
             (182, 145), 10, GRAY)
        items = SCORESTREAKS
        start = (self.streak_index // 12) * 12
        for local in range(12):
            idx = start + local
            if idx >= len(items):
                break
            item = items[idx]
            col, row = local % 2, local // 2
            rect = pygame.Rect(182 + col * 526, 170 + row * 61, 510, 54)
            selected = idx == self.streak_index
            owned = self.streak_owned(item)
            equipped_slot = next((i for i, x in enumerate(self.lo.get("scorestreaks", [])) if x == item["id"]), None)
            border = AMBER if selected else (CYAN if equipped_slot is not None else GREEN)
            panel(surf, rect, border, gfx.PANEL2 if selected else gfx.PANEL)
            icon_rect = pygame.Rect(rect.x + 7, rect.y + 5, 42, 42)
            pygame.draw.rect(surf, (10, 17, 18), icon_rect)
            pygame.draw.rect(surf, gfx.darker(border, 0.55), icon_rect, 1)
            gfx.streak_icon(surf, item["id"], (icon_rect.x + 2, icon_rect.y + 2, 38, 38), border, owned)
            name_color = WHITE if owned else GRAY
            text(surf, item["name"], (rect.x + 58, rect.y + 5), 13, name_color)
            points = ("N/A" if item["id"] == "rc_xd" else "IMMEDIATE") if item["points"] is None else f"{item['points']} SCORE"
            status = f"SLOT {equipped_slot + 1}" if equipped_slot is not None else (
                "UNLOCKED" if owned else f"LVL {item['unlock_level']} / STORE {item['price']} CR")
            text(surf, f"{points}  |  {status}", (rect.x + 58, rect.y + 24), 10,
                 CYAN if equipped_slot is not None else (GREEN if owned else AMBER))
            if selected:
                text(surf, "SELECTED", (rect.right - 10, rect.y + 7), 9, AMBER, "topright")
        # Three editable slots and store actions.
        text(surf, "EQUIPPED STREAKS", (182, 542), 11, GRAY)
        for i in range(3):
            rect = pygame.Rect(182 + i * 174, 559, 164, 37)
            active = self.streak_slot == i
            panel(surf, rect, AMBER if active else GREEN, gfx.PANEL2 if active else gfx.PANEL)
            streak_id = self.lo.get("scorestreaks", ["uav", "hunter_killer", "shield_turret"])[i]
            item = next((x for x in SCORESTREAKS if x["id"] == streak_id), SCORESTREAKS[0])
            gfx.streak_icon(surf, item["id"], (rect.x + 5, rect.y + 3, 28, 28),
                            AMBER if active else CYAN, True)
            text(surf, f"{i+1}. {item['name'][:15]}", (rect.x + 36, rect.centery),
                 10, AMBER if active else WHITE, "midleft")
        actions = [("ENTER / E  EQUIP", pygame.Rect(720, 559, 148, 37)),
                   ("B  BUY STREAK", pygame.Rect(878, 559, 148, 37)),
                   ("S  BUY SKIN", pygame.Rect(1036, 559, 148, 37))]
        for label, rect in actions:
            panel(surf, rect, CYAN, gfx.PANEL2)
            text(surf, label, rect.center, 10, WHITE, "center")
        selected_item = SCORESTREAKS[self.streak_index]
        text(surf, selected_item["desc"][:108], (182, 608), 11, WHITE)
        text(surf, self.streak_message, (182, 627), 11, AMBER)
        text(surf, "ARROWS SELECT  |  1-3 SELECT SLOT  |  ENTER EQUIP  |  B BUY  |  S SKIN  |  PAGE UP/DOWN", (182, 651), 11, GRAY)

    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.app.settings.save()
                self.app.pop()
            elif self.nav_focus == "STREAKS" and e.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_PAGEUP, pygame.K_PAGEDOWN, pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_b, pygame.K_s, pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
                if e.key == pygame.K_UP: self.streak_index = (self.streak_index - 2) % len(SCORESTREAKS)
                elif e.key == pygame.K_DOWN: self.streak_index = (self.streak_index + 2) % len(SCORESTREAKS)
                elif e.key == pygame.K_LEFT: self.streak_index = (self.streak_index - 1) % len(SCORESTREAKS)
                elif e.key == pygame.K_RIGHT: self.streak_index = (self.streak_index + 1) % len(SCORESTREAKS)
                elif e.key == pygame.K_PAGEUP: self.streak_index = max(0, self.streak_index - 12)
                elif e.key == pygame.K_PAGEDOWN: self.streak_index = min(len(SCORESTREAKS)-1, self.streak_index + 12)
                elif e.key == pygame.K_1: self.streak_slot = 0
                elif e.key == pygame.K_2: self.streak_slot = 1
                elif e.key == pygame.K_3: self.streak_slot = 2
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e): self.equip_streak()
                elif e.key == pygame.K_b: self.buy_streak()
                elif e.key == pygame.K_s: self.buy_streak_skin()
            elif e.key == pygame.K_UP:
                self.sel = (self.sel - 1) % len(self.rows)
                self.sync_nav_focus()
            elif e.key == pygame.K_DOWN:
                self.sel = (self.sel + 1) % len(self.rows)
                self.sync_nav_focus()
            elif e.key == pygame.K_LEFT:
                self.change(-1)
            elif e.key == pygame.K_RIGHT:
                self.change(1)
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.done()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = self.app.mouse()
            if pygame.Rect(216, 518, 254, 28).collidepoint(pos):
                self.nav_focus = "OPERATOR"
                self.open_character_select()
                return
            for i, label in enumerate(("OPERATOR", "WEAPONS", "SKINS", "EQUIPMENT", "STREAKS")):
                r = self.navrect(i)
                if r.collidepoint(pos):
                    self.nav_focus = label
                    if label == "OPERATOR":
                        self.open_character_select()
                    elif label == "STREAKS":
                        self.streak_index = min(self.streak_index, len(SCORESTREAKS)-1)
                    else:
                        row = {"WEAPONS": "PRIMARY", "SKINS": "PRIMARY SKIN",
                               "EQUIPMENT": "EQUIPMENT"}[label]
                        self.sel = self.rows.index(row)
                    return
            if self.nav_focus == "STREAKS":
                for i in range(12):
                    idx = (self.streak_index // 12) * 12 + i
                    if idx >= len(SCORESTREAKS): break
                    rect = pygame.Rect(182 + (i % 2) * 526, 170 + (i // 2) * 61, 510, 54)
                    if rect.collidepoint(pos):
                        self.streak_index = idx
                        return
                for i in range(3):
                    if pygame.Rect(182 + i * 174, 559, 164, 37).collidepoint(pos):
                        self.streak_slot = i
                        return
                if pygame.Rect(720, 559, 148, 37).collidepoint(pos): self.equip_streak(); return
                if pygame.Rect(878, 559, 148, 37).collidepoint(pos): self.buy_streak(); return
                if pygame.Rect(1036, 559, 148, 37).collidepoint(pos): self.buy_streak_skin(); return
                return
            category_rect = pygame.Rect(520, 82, 206, 38)
            rarity_rect = pygame.Rect(736, 82, 240, 38)
            if category_rect.collidepoint(pos):
                self.nav_focus = "WEAPONS"
                self.sel = self.rows.index("CATEGORY")
                self.change(1 if pos[0] > category_rect.centerx else -1)
                return
            if rarity_rect.collidepoint(pos):
                self.nav_focus = "WEAPONS"
                self.sel = self.rows.index("RARITY FILTER")
                self.change(1 if pos[0] > rarity_rect.centerx else -1)
                return
            for weapon_key, rect, row_name in (
                    ("primary", self.primary_rect(), "PRIMARY"),
                    ("secondary", self.secondary_rect(), "SECONDARY")):
                skin_rect = pygame.Rect(rect.x + 10, rect.bottom - 41, rect.w - 20, 32)
                skin_row = "PRIMARY SKIN" if weapon_key == "primary" else "SECONDARY SKIN"
                if skin_rect.collidepoint(pos):
                    self.nav_focus = "SKINS"
                    self.sel = self.rows.index(skin_row)
                    self.change(1 if pos[0] >= skin_rect.centerx else -1)
                    return
                if rect.collidepoint(pos):
                    self.nav_focus = "WEAPONS"
                    self.sel = self.rows.index(row_name)
                    direction = -1 if pos[0] < rect.x + 48 else 1 if pos[0] > rect.right - 48 else 0
                    if direction:
                        self.change(direction)
                    return
            equipment = self.equipment_rect()
            if equipment.collidepoint(pos):
                self.nav_focus = "EQUIPMENT"
                self.sel = self.rows.index("EQUIPMENT")
                self.change(1 if pos[0] >= equipment.centerx else -1)
                return
            slots_y = 602
            slot_width = (CANVAS_W - 64 - 9 * 6) / 10
            for i in range(10):
                slot_rect = pygame.Rect(32 + i * (slot_width + 6), slots_y, slot_width, 60)
                if slot_rect.collidepoint(pos):
                    self.select_slot(i + 1)
                    return
            if pygame.Rect(1090, 34, 158, 38).collidepoint(pos):
                self.done()

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        wl = weapons()
        prim, sec = wl[self.lo["primary"]], wl[self.lo["secondary"]]
        equipped_skins = self.app.stats.equipped_skins()
        primary_skin = equipped_skins.get(prim["id"])
        secondary_skin = equipped_skins.get(sec["id"])
        char = next(c for c in characters() if c["id"] == self.lo["char"])
        text(surf, "FIELD LOADOUT", (32, 26), 36, AMBER)
        text(surf, f"PRESET {self.slot:02}  /  10", (300, 39), 15, CYAN)
        confirm_rect = pygame.Rect(1090, 34, 158, 38)
        pygame.draw.rect(surf, gfx.PANEL2, confirm_rect)
        pygame.draw.rect(surf, AMBER, confirm_rect, 2)
        text(surf, "CONFIRM >" if self.flow is not None else "SAVE & BACK",
             confirm_rect.center, 14, AMBER, "center")

        nav_labels = ("OPERATOR", "WEAPONS", "SKINS", "EQUIPMENT", "STREAKS")
        nav_active = self.nav_focus
        for i, label in enumerate(nav_labels):
            rect = self.navrect(i)
            active = label == nav_active
            panel(surf, rect, AMBER if active else GREEN, gfx.PANEL2 if active else gfx.PANEL)
            text(surf, label, rect.center, 13, AMBER if active else WHITE, "center")
        text(surf, "CLICK TO EDIT", (98, 474), 11, GRAY, "center")
        if self.nav_focus == "STREAKS":
            self.draw_streaks(surf)
            return

        operator_rect = pygame.Rect(180, 112, 326, 444)
        panel(surf, operator_rect, tuple(char["color"]), gfx.PANEL)
        text(surf, "OPERATOR PREVIEW", (198, 130), 13, GRAY)
        # Full-body operator showcase: angular inset plate, no circular avatar frame.
        showcase = pygame.Rect(226, 164, 234, 238)
        pygame.draw.rect(surf, (10, 16, 17), showcase)
        pygame.draw.rect(surf, (57, 75, 65), showcase, 1)
        pygame.draw.line(surf, tuple(char["color"]), (showcase.x, showcase.y), (showcase.x + 46, showcase.y), 3)
        pygame.draw.line(surf, tuple(char["color"]), (showcase.right - 46, showcase.bottom), (showcase.right, showcase.bottom), 3)
        pygame.draw.ellipse(surf, (5, 8, 8), (266, 362, 154, 20))
        sprite = gfx.char_sprite(char, 0, self.t * 0.8)
        sprite = pygame.transform.scale(sprite, (sprite.get_width() * 6, sprite.get_height() * 6))
        surf.blit(sprite, sprite.get_rect(center=(343, 278)))
        text(surf, char["name"], (343, 426), 27, tuple(char["color"]), "midtop")
        text(surf, char["role"].upper(), (343, 460), 13, AMBER, "midtop")
        text(surf, f"HP {char['hp']}     SPEED {char['speed']:.2f}x",
             (343, 490), 13, WHITE, "midtop")
        operator_button = pygame.Rect(216, 518, 254, 28)
        pygame.draw.rect(surf, gfx.PANEL2, operator_button)
        pygame.draw.rect(surf, GREEN, operator_button, 1)
        text(surf, "CHANGE OPERATOR", operator_button.center, 12, CYAN, "center")

        category_rect = pygame.Rect(520, 82, 206, 38)
        rarity_rect = pygame.Rect(736, 82, 240, 38)
        for rect, title, value, color in (
                (category_rect, "CLASS", CATEGORY_LABEL[self.cat], CYAN),
                (rarity_rect, "RARITY", self.rarity_filter, RARITY_COLORS.get(self.rarity_filter, WHITE))):
            panel(surf, rect, GREEN, gfx.PANEL)
            text(surf, title, (rect.x + 10, rect.y + 5), 10, GRAY)
            text(surf, f"<  {value}  >", rect.midbottom, 13, color, "midbottom")

        rarity = weapon_rarity(prim)
        sec_rarity = weapon_rarity(sec)
        for weapon, weapon_skin, rect, key, weapon_rarity_value in (
                (prim, primary_skin, self.primary_rect(), "primary", rarity),
                (sec, secondary_skin, self.secondary_rect(), "secondary", sec_rarity)):
            skin_color = RARITY_COLORS[weapon_skin["rarity"]] if weapon_skin else RARITY_COLORS[weapon_rarity_value]
            panel(surf, rect, skin_color, (15, 21, 27))
            # Raised inset display bay gives the weapon card a chunky, machined 2.5D look.
            bay = pygame.Rect(rect.x + 12, rect.y + 62, rect.w - 24, 105)
            pygame.draw.rect(surf, (8, 13, 18), bay, border_radius=5)
            pygame.draw.line(surf, (69, 86, 94), bay.topleft, (bay.right - 8, bay.top), 2)
            pygame.draw.line(surf, (4, 7, 10), (bay.left, bay.bottom), bay.bottomright, 2)
            pygame.draw.line(surf, skin_color, (bay.left + 8, bay.bottom - 5), (bay.left + 64, bay.bottom - 5), 2)
            title = "PRIMARY WEAPON" if key == "primary" else "SIDEARM / SECONDARY"
            text(surf, title, (rect.x + 14, rect.y + 10), 11, GRAY)
            text(surf, weapon["name"], (rect.x + 14, rect.y + 29), 18, WHITE)
            text(surf, weapon_rarity_value, (rect.right - 14, rect.y + 14), 11, skin_color, "topright")
            text(surf, "<", (rect.x + 21, rect.y + 112), 22, AMBER, "center")
            text(surf, ">", (rect.right - 21, rect.y + 112), 22, AMBER, "center")
            gfx.draw_weapon(surf, (rect.centerx, rect.y + 118), 0,
                            weapon_skin["rarity"] if weapon_skin else weapon_rarity_value,
                            2.0, self.t, weapon_skin["name"] if weapon_skin else None, weapon["id"])
            stats_y = rect.y + 151
            damage = weapon["dmg"] * weapon["pellets"]
            text(surf, f"DMG {damage}    RPM {weapon['rate']}    MAG {weapon['mag']}",
                 (rect.x + 14, stats_y), 11, WHITE)
            text(surf, f"RANGE {weapon['range']}    RELOAD {weapon['reload']}s",
                 (rect.x + 14, stats_y + 19), 10, GRAY)
            # Compact stat rails communicate weapon strengths at a glance.
            rail_y = stats_y + 39
            for j, (label, value, maximum, tint) in enumerate((
                    ("DMG", damage, max(1, self.maxes["dmg"]), skin_color),
                    ("RPM", weapon["rate"], max(1, self.maxes["rate"]), CYAN),
                    ("RNG", weapon["range"], max(1, self.maxes["range"]), AMBER))):
                yy = rail_y + j * 7
                text(surf, label, (rect.x + 14, yy - 2), 7, GRAY)
                track = pygame.Rect(rect.x + 43, yy, rect.w - 62, 4)
                pygame.draw.rect(surf, (5, 9, 12), track)
                pygame.draw.rect(surf, tint, (track.x, track.y, max(1, int(track.w * min(1, value / maximum))), track.h))
            skin_rect = pygame.Rect(rect.x + 10, rect.bottom - 41, rect.w - 20, 32)
            pygame.draw.rect(surf, gfx.PANEL2, skin_rect)
            pygame.draw.rect(surf, skin_color, skin_rect, 1)
            text(surf, "SKIN  " + (weapon_skin["name"] if weapon_skin else "DEFAULT LOOK"),
                 (skin_rect.x + 8, skin_rect.centery), 10, skin_color, "midleft")
            text(surf, "CHANGE", (skin_rect.right - 8, skin_rect.centery), 9, AMBER, "midright")

        equipment = self.equipment_rect()
        panel(surf, equipment, AMBER if self.rows[self.sel] == "EQUIPMENT" else GREEN, gfx.PANEL)
        text(surf, "TACTICAL EQUIPMENT", (equipment.x + 16, equipment.y + 12), 12, GRAY)
        text(surf, "<", (equipment.x + 28, equipment.y + 78), 25, AMBER, "center")
        text(surf, EQUIPMENT[self.lo["equipment"]][0],
             (equipment.centerx, equipment.y + 66), 21, AMBER, "midtop")
        text(surf, EQUIPMENT[self.lo["equipment"]][1],
             (equipment.centerx, equipment.y + 102), 11, WHITE, "midtop")
        text(surf, ">", (equipment.right - 28, equipment.y + 78), 25, AMBER, "center")
        text(surf, "CLICK LEFT / RIGHT TO CHANGE", (equipment.right - 14, equipment.y + 13),
             9, GRAY, "topright")

        text(surf, "SAVED LOADOUTS", (32, 578), 11, GRAY)
        slot_width = (CANVAS_W - 64 - 9 * 6) / 10
        for i, slot_data in enumerate(self.slots):
            rect = pygame.Rect(32 + i * (slot_width + 6), 602, slot_width, 60)
            active = i + 1 == self.slot
            border = AMBER if active else GREEN
            panel(surf, rect, border, gfx.PANEL2 if active else gfx.PANEL)
            text(surf, f"{i + 1:02}", (rect.x + 8, rect.y + 8), 13,
                 AMBER if active else GRAY)
            if active:
                slot_data = self.lo
            weapon_name = weapons().get(slot_data["primary"], prim)["name"]
            text(surf, weapon_name[:14], (rect.x + 8, rect.y + 31), 9,
                 WHITE if active else GRAY)
        text(surf, "UP/DOWN SELECT  -  LEFT/RIGHT EDIT  -  ENTER CONFIRM  -  ESC BACK",
             (32, 682), 12, GRAY)


class BriefingScene(Scene):
    def __init__(self, app, flow):
        super().__init__(app)
        self.flow = flow
        self.sel = ORDER.index(app.settings["difficulty"])
        self.admin_open = False
        self.admin_input = ""
        self.admin_message = ""

    def start(self):
        from .match_scene import MatchScene
        self.app.settings["difficulty"] = ORDER[self.sel]
        self.app.settings.save()
        self.app.audio.start_music("battle")
        self.app.push(MatchScene(self.app, self.flow["mode"], self.flow["map"],
                                 bool(self.flow.get("ranked", False)),
                                 self.flow.get("campaign_mission"),
                                 int(self.flow.get("team_size", 5))))

    def _run_admin_command(self, command):
        parts = command.strip().lower().split()
        if parts == ["/admin", "help"]:
            self.admin_message = "/admin rank <points>  |  /admin coins <amount>  |  /admin unlock legendary/all/frames"
        elif parts == ["/admin", "unlock", "legendary"]:
            ids = self.app.stats.grant_legendary_armory()
            self.admin_message = f"LOCAL ADMIN: LEGENDARY ARMORY UNLOCKED ({len(ids)} WEAPONS)"
        elif parts == ["/admin", "unlock", "all"]:
            ids = self.app.stats.unlock_all_weapons()
            self.admin_message = f"LOCAL ADMIN: ALL WEAPONS UNLOCKED ({len(ids)})"
        elif parts == ["/admin", "unlock", "frames"]:
            ids = self.app.stats.grant_all_avatar_frames()
            self.admin_message = f"LOCAL ADMIN: ALL AVATAR FRAMES UNLOCKED ({len(ids)})"
        elif len(parts) == 3 and parts[:2] == ["/admin", "coins"]:
            try:
                amount = int(parts[2].replace(",", ""))
                self.app.stats.grant_coins(amount)
                self.admin_message = f"LOCAL ADMIN: GRANTED {amount:,} COINS"
            except ValueError:
                self.admin_message = "INVALID COIN AMOUNT"
        elif len(parts) == 3 and parts[:2] == ["/admin", "rank"]:
            try:
                rank = self.app.stats.set_rank_points(int(parts[2].replace(",", "")))
                self.admin_message = f"LOCAL ADMIN: RANK SET TO {rank['tier'].upper()} ({rank['points']:,} RP)"
            except ValueError:
                self.admin_message = "INVALID RANK POINTS"
        elif len(parts) == 3 and parts[:2] == ["/admin", "unlock"]:
            weapon_id = parts[2]
            if self.app.stats.unlock_weapon(weapon_id):
                self.admin_message = f"LOCAL ADMIN: UNLOCKED {weapons()[weapon_id]['name']}"
            else:
                self.admin_message = f"UNKNOWN WEAPON ID: {weapon_id}"
        else:
            self.admin_message = "UNKNOWN ADMIN COMMAND - TYPE /ADMIN HELP"

    def rowrect(self, i):
        return pygame.Rect(60, 190 + i * 92, 520, 82)

    def event(self, e):
        if self.admin_open and e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.admin_open = False
                self.admin_input = ""
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._run_admin_command(self.admin_input)
                self.admin_input = ""
                self.admin_open = False
            elif e.key == pygame.K_BACKSPACE:
                self.admin_input = self.admin_input[:-1]
            else:
                char = getattr(e, "unicode", "")
                if char and char.isprintable() and len(self.admin_input) < 80:
                    self.admin_input += char
            return
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.app.pop()
            elif e.key == pygame.K_SLASH:
                self.admin_open = True
                self.admin_input = "/"
            elif e.key in (pygame.K_UP, pygame.K_LEFT):
                self.sel = (self.sel - 1) % 4
            elif e.key in (pygame.K_DOWN, pygame.K_RIGHT):
                self.sel = (self.sel + 1) % 4
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = self.app.mouse()
            for i in range(4):
                if self.rowrect(i).collidepoint(pos):
                    self.sel = i
            if pygame.Rect(700, 560, 400, 60).collidepoint(pos):
                self.start()

    def draw(self, surf):
        gfx.draw_bg(surf, self.t)
        text(surf, "MISSION BRIEFING", (60, 30), 44, AMBER)
        text(surf, "SELECT AI DIFFICULTY", (60, 150), 20, GRAY)
        for i, name in enumerate(ORDER):
            r = self.rowrect(i)
            sel = i == self.sel
            pygame.draw.rect(surf, gfx.PANEL2 if sel else gfx.PANEL, r)
            pygame.draw.rect(surf, AMBER if sel else GREEN, r, 2)
            text(surf, name, (r.x + 16, r.y + 10), 26, AMBER if sel else WHITE)
            text(surf, DIFFICULTIES[name]["desc"], (r.x + 16, r.y + 46), 13, GRAY)
        f, s = self.flow, self.app.settings["loadout"]
        panel(surf, (660, 150, 560, 380))
        meta = next(m for m in maps_meta() if m["id"] == f["map"])
        wl = weapons()
        rows = [("MODE", MODES[f["mode"]].name), ("MAP", meta["name"]), ("OPERATOR", s["char"].upper()), ("PRIMARY", wl[s["primary"]]["name"]),
                ("SECONDARY", wl[s["secondary"]]["name"]), ("EQUIPMENT", EQUIPMENT[s["equipment"]][0]), ("FORMAT", "10 vs 10  (YOU + 9 AI vs 10 AI)")]
        if "campaign_mission" in f:
            mission = campaign_mission(f["campaign_mission"])
            rows.append(("CAMPAIGN", f"CHAPTER {f['campaign_mission'] + 1}: {mission['name']}"))
        for i, (k, v) in enumerate(rows):
            text(surf, k, (684, 174 + i * 40), 16, GRAY)
            text(surf, v, (684, 194 + i * 40), 20, WHITE)
        if f.get("ranked"):
            rank = self.app.stats.rank()
            text(surf, f"RANKED QUEUE  -  {rank['tier'].upper()} {rank['points']} RP",
                 (684, 484), 14, AMBER)
        pygame.draw.rect(surf, AMBER, (700, 560, 400, 60), 3)
        text(surf, "START MATCH", (900, 590), 28, AMBER, "center")
        text(surf, "UP/DOWN DIFFICULTY  -  ENTER START  -  / LOCAL ADMIN CONSOLE  -  ESC BACK",
             (60, 680), 13, GRAY)
        if self.admin_message:
            text(surf, self.admin_message, (CX, 642), 14, AMBER, "midtop")
        if self.admin_open:
            panel(surf, (CX - 320, 535, 640, 76))
            text(surf, "LOCAL OFFLINE ADMIN COMMAND - NO AUTHENTICATION", (CX, 543), 12, GRAY, "midtop")
            text(surf, f"> {self.admin_input}_", (CX - 296, 565), 17, WHITE)
