"""Drives every screen and each game mode through the real UI code using the fake pygame."""
import os
import sys
import math
import tempfile
from pathlib import Path

os.environ["OVERHEAD_OPS_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fakepygame  # noqa: E402
import pygame  # noqa: E402

from src.app import App  # noqa: E402
from src.campaign import CAMPAIGN_MISSIONS  # noqa: E402
from src.config import weapon_list, weapons  # noqa: E402
from src.progression import SKIN_DESIGNS, weapon_rarity  # noqa: E402
from src import gfx  # noqa: E402
from src.match_scene import MatchScene  # noqa: E402
from src.online_scene import OnlineScene  # noqa: E402
from src.save import Settings  # noqa: E402
from src.scenes import (ArmoryScene, BriefingScene, CampaignScene, CharacterScene, CreditsScene, LoadoutScene, MainMenu, MapSelect,  # noqa: E402
                        INTRO_DURATION, HudEditorScene, LeaderboardScene, ProfileScene, SettingsScene, StatsScene, StoreScene)


def key(k):
    return pygame.Event(pygame.KEYDOWN, key=k)


def type_command(scene, command):
    scene.event(key(pygame.K_RETURN))
    for char in command:
        scene.event(pygame.Event(pygame.KEYDOWN, key=0, unicode=char))
    scene.event(key(pygame.K_RETURN))


app = App()
app.scenes = [MainMenu(app)]
class SceneSwitch:
    def __init__(self):
        self.received = []

    def event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            app.scenes.append(next_scene)
        else:
            self.received.append(event.type)


class EventRecorder:
    def __init__(self):
        self.received = []

    def event(self, event):
        self.received.append(event.type)


next_scene = EventRecorder()
app.scenes = [SceneSwitch()]
app._dispatch_touch_event(pygame.Event(pygame.FINGERDOWN, finger_id=42, x=0.5, y=0.5))
assert pygame.FINGERDOWN not in next_scene.received
app._dispatch_touch_event(pygame.Event(pygame.FINGERUP, finger_id=42, x=0.5, y=0.5))
app.scenes = [MainMenu(app)]
assert INTRO_DURATION == 6.0
intro_test = MainMenu(app)
intro_test.update(5.9)
assert intro_test.intro_t < INTRO_DURATION
intro_test.update(0.1)
assert intro_test.intro_t == INTRO_DURATION
app.intro_seen = False
flow = dict(mode="snd", map="depot_09")
screens = [MainMenu(app), MapSelect(app, {}), CharacterScene(app, flow), LoadoutScene(app, flow), BriefingScene(app, flow),
           CampaignScene(app), ArmoryScene(app), ProfileScene(app), StoreScene(app),
           LeaderboardScene(app), SettingsScene(app), StatsScene(app), CreditsScene(app)]
for sc in screens:
    for k in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_UP, pygame.K_c):
        sc.event(key(k))
    sc.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1))
    sc.event(pygame.Event(pygame.MOUSEMOTION, rel=(1, 1), pos=(1, 1)))
    for _ in range(3):
        sc.update(0.016)
        sc.draw(app.canvas)
print("menu screens ok:", len(screens))
online_screen = OnlineScene(app)
online_screen.draw(app.canvas)
online_screen.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1))
assert online_screen.editing_address
online_screen.event(pygame.Event(pygame.KEYDOWN, key=0, unicode="x"))
assert online_screen.address.endswith("x")
print("online matchmaking screen ok")
drawn_body_colors = []
base_polygon = pygame.draw.polygon


def capture_polygon(surf, color, points, *args, **kwargs):
    drawn_body_colors.append(color)
    return base_polygon(surf, color, points, *args, **kwargs)


pygame.draw.polygon = capture_polygon
gfx.draw_weapon(app.canvas, (400, 400), 0, "LEGENDARY", 1.0, 1.0, weapon_id="m4_emberwyrm")
m4_finish = drawn_body_colors[-1]
before_holger = len(drawn_body_colors)
gfx.draw_weapon(app.canvas, (400, 400), 0, "LEGENDARY", 1.0, 1.0, weapon_id="holger_galactic_stars")
holger_finish = drawn_body_colors[before_holger]
assert m4_finish != holger_finish, "Legendary weapons should have distinct color finishes"
pygame.draw.polygon = base_polygon
print("distinct Legendary finishes and Holger celestial render ok")
sc = SettingsScene(app)
for i in range(len(sc.rows)):
    sc.sel = i
    for d in (1, -1, 0):
        sc.adjust(d)
    sc.draw(app.canvas)
print("settings rows ok:", len(sc.rows))

profile = ProfileScene(app)
for _ in range(len(profile.name)):
    profile.event(key(pygame.K_BACKSPACE))
for char in "Pilot":
    profile.event(pygame.Event(pygame.KEYDOWN, key=0, unicode=char))
profile.event(key(pygame.K_RETURN))
assert app.stats.player_name() == "Pilot"
uid = app.stats.player_uid()
profile.event(key(pygame.K_RIGHT))
profile.event(key(pygame.K_F4))
assert app.stats.equipped_avatar_frame() == profile.frames[profile.frame_index]["id"]
profile.draw(app.canvas)
picture_picker_calls = []
profile.choose_picture = lambda: picture_picker_calls.append(True)
app.mouse = lambda: (500, 500)
profile.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(500, 500)))
assert picture_picker_calls == [True]
app.mouse = lambda: (640, 360)
menu = MainMenu(app)
menu.event(key(pygame.K_SLASH))
for char in "admin coins 1,000,000,000":
    menu.event(pygame.Event(pygame.KEYDOWN, key=0, unicode=char))
menu.event(key(pygame.K_RETURN))
assert "GRANTED 1,000,000,000 COINS" in menu.command_message
assert app.stats.coins() == 1_000_000_000
menu._run_admin_command("/admin rank 2,700")
assert "MYTHIC V (2,700 RP)" in menu.command_message
assert app.stats.rank()["points"] == 2700
menu.command_input = "/"
for char in "admin unlock frames":
    menu.event(pygame.Event(pygame.KEYDOWN, key=0, unicode=char))
menu.event(key(pygame.K_RETURN))
assert "AVATAR FRAMES UNLOCKED" in menu.command_message
menu.command_input = "/"
for char in "admin unlock all":
    menu.event(pygame.Event(pygame.KEYDOWN, key=0, unicode=char))
menu.event(key(pygame.K_RETURN))
assert "ALL WEAPONS UNLOCKED" in menu.command_message
assert len(app.stats.unlocked_weapon_ids()) == len(weapon_list())
unlocked_loadout = LoadoutScene(app)
assert {"field_knife", "breach_launcher"}.issubset({w["id"] for w in unlocked_loadout.sec_list()})
primary_owned_skin = app.stats.add_skin("vanguard", "LEGENDARY", "Vanguard - Astral Sovereign")
loadout_skins = LoadoutScene(app)
loadout_skins.sel = loadout_skins.rows.index("PRIMARY SKIN")
loadout_skins.event(key(pygame.K_RIGHT))
assert app.stats.equipped_skins()["vanguard"]["id"] == primary_owned_skin["id"]
loadout_skins.draw(app.canvas)
skin_match = MatchScene(app, "ctf", "depot_09")
assert skin_match.m.player.equipped_skins["vanguard"]["name"] == primary_owned_skin["name"]
class NetworkStub:
    player_id = "bravo"

    def __init__(self):
        self.sent = []

    def send_input(self, action):
        self.sent.append(action)

    def poll(self):
        return []

    def close(self):
        pass


network_stub = NetworkStub()
network_roster = [
    {"player_id": "alpha", "name": "ALPHA", "char": "vanguard", "primary": "vanguard", "secondary": "p9",
     "equipment": "none", "team": 0},
    {"player_id": "bravo", "name": "BRAVO", "char": "vanguard", "primary": "vanguard", "secondary": "p9",
     "equipment": "none", "team": 1},
]
online_match = MatchScene(app, "snd", "depot_09", online_client=network_stub,
                          online_match={"seed": 1234, "team_size": 5, "players": network_roster})
assert online_match.m.player.team == 1
online_match._apply_online_tick({
    "tick": 0,
    "inputs": [
        {"player_id": "alpha", "action": {"move_x": 1, "move_y": 0, "aim": 0, "trigger": False, "ads": False,
         "sprint": False, "interact": False, "reload": False, "ability": False, "swap_to": None}},
        {"player_id": "bravo", "action": {"move_x": -1, "move_y": 0, "aim": 3.14, "trigger": False, "ads": False,
         "sprint": False, "interact": False, "reload": False, "ability": False, "swap_to": None}},
    ],
})
assert online_match.m.time == 0.05
assert online_match.m.player.mx == -1
online_match._send_online_input()
assert network_stub.sent[-1]["move_x"] == -1
network_stub.close()
loadout_skins.event(key(pygame.K_RIGHT))
assert "vanguard" not in app.stats.equipped_skins()
loadout_skins.sel = loadout_skins.rows.index("RARITY FILTER")
loadout_skins.event(key(pygame.K_LEFT))
assert loadout_skins.rarity_filter == "LEGENDARY"
assert all(weapon_rarity(weapon) == "LEGENDARY" for weapon in loadout_skins.prim_list())
loadout_skins.sel = loadout_skins.rows.index("PRIMARY")
loadout_skins.event(key(pygame.K_RIGHT))
assert weapon_rarity(weapons()[app.settings["loadout"]["primary"]]) == "LEGENDARY"
loadout_skins.draw(app.canvas)
for weapon_id in ("m4_emberwyrm", "holger_galactic_stars", "viper", "longbow", "solstice"):
    effect_scene = MatchScene(app, "ctf", "depot_09")
    victim = next(c for c in effect_scene.m.combatants if c.team == 1)
    effect_scene.m.player.kill_effect_weapons = {weapon_id}
    effect_scene.m.kill(victim, effect_scene.m.player, weapon_id, False)
    effect = next(effect for effect in effect_scene.m.fx
                  if effect.kind.endswith("_death") and effect.kind != "death")
    effect_scene.r._fx(app.canvas, effect, (0, 0), True)
for design in (item for item in SKIN_DESIGNS if item["rarity"] == "LEGENDARY"):
    effect_scene = MatchScene(app, "ctf", "depot_09")
    victim = next(c for c in effect_scene.m.combatants if c.team == 1)
    effect_scene.m.player.kill_effect_weapons = {"vanguard"}
    effect_scene.m.player.equipped_skins = {
        "vanguard": dict(rarity="LEGENDARY", kill_effect=True, effect_id=design["kill_effect"])
    }
    effect_scene.m.kill(victim, effect_scene.m.player, "vanguard", False)
    effect = next(effect for effect in effect_scene.m.fx
                  if effect.kind.startswith("skin_") and effect.kind.endswith("_death"))
    effect_scene.r._fx(app.canvas, effect, (0, 0), True)
slot_scene = LoadoutScene(app)
slot_scene.sel = slot_scene.rows.index("LOADOUT SLOT")
slot_scene.event(key(pygame.K_RIGHT))
assert slot_scene.slot == 2
slot_scene.sel = slot_scene.rows.index("PRIMARY")
slot_scene.event(key(pygame.K_RIGHT))
slot_two_primary = app.settings["loadout"]["primary"]
slot_scene.save_slot()
app.settings.save()
slot_one = LoadoutScene(app)
slot_one.sel = slot_one.rows.index("LOADOUT SLOT")
slot_one.event(key(pygame.K_LEFT))
assert slot_one.slot == 1
assert app.settings["loadout"]["primary"] != slot_two_primary
slot_one.sel = slot_one.rows.index("LOADOUT SLOT")
slot_one.event(key(pygame.K_RIGHT))
assert app.settings["loadout"]["primary"] == slot_two_primary
slot_one.save_slot()
app.settings.save()
from src.save import Settings
reloaded_settings = Settings()
assert len(reloaded_settings["loadout_slots"]) == 10
assert reloaded_settings["active_loadout_slot"] == 2
assert reloaded_settings["loadout"]["primary"] == slot_two_primary
mouse_loadout = LoadoutScene(app)
app.push(mouse_loadout)
app.mouse = lambda: (mouse_loadout.navrect(0).centerx, mouse_loadout.navrect(0).centery)
mouse_loadout.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1))
assert isinstance(app.scenes[-1], CharacterScene)
character_picker = app.scenes[-1]
character_picker.sel = (character_picker.sel + 1) % len(character_picker.chars)
character_picker.confirm()
assert app.scenes[-1] is mouse_loadout
assert app.settings["loadout_slots"][app.settings["active_loadout_slot"] - 1]["char"] == app.settings["loadout"]["char"]
slot_width = (1280 - 64 - 9 * 6) / 10
app.mouse = lambda: (32 + 3 * (slot_width + 6) + slot_width / 2, 632)
mouse_loadout.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1))
assert mouse_loadout.slot == 4
old_mouse_primary = mouse_loadout.lo["primary"]
primary_rect = mouse_loadout.primary_rect()
app.mouse = lambda: (primary_rect.right - 20, primary_rect.y + 112)
mouse_loadout.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1))
assert mouse_loadout.lo["primary"] != old_mouse_primary
app.mouse = lambda: (primary_rect.centerx, primary_rect.bottom - 25)
mouse_loadout.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1))
assert mouse_loadout.sel == mouse_loadout.rows.index("PRIMARY SKIN")
mouse_loadout.draw(app.canvas)
leaderboard = LeaderboardScene(app)
app.stats.record_match("ctf", "depot_09", "NORMAL", True,
                       dict(kills=3, deaths=1, headshots=1, shots=12, hits=8, weapon_kills={}))
assert app.stats.leaderboard(10)
assert len(leaderboard.rows) == 100
assert sum(row["is_player"] for row in leaderboard.rows) == 1
leaderboard.event(key(pygame.K_DOWN))
assert leaderboard.scroll == 1
player_index = next(i for i, row in enumerate(leaderboard.rows) if row["is_player"])
leaderboard.scroll = min(player_index, len(leaderboard.rows) - leaderboard.VISIBLE_ROWS)
player_row = player_index - leaderboard.scroll
scene_count = len(app.scenes)
leaderboard.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1,
                               pos=(120, int(154 + player_row * 24))))
assert leaderboard.selected_profile["is_player"]
assert len(app.scenes) == scene_count
leaderboard.draw(app.canvas)
leaderboard.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(640, 360)))
assert leaderboard.selected_profile["is_player"], "clicking inside a profile must not dismiss it"
leaderboard.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 20)))
assert leaderboard.selected_profile is None
leaderboard.draw(app.canvas)
store = StoreScene(app)
store.event(key(pygame.K_l))
assert store.rarity_filter == "LEGENDARY"
assert store.items and all(design["rarity"] == "LEGENDARY" for _, design in store.items)
store.event(key(pygame.K_RETURN))
assert "PURCHASED" in store.message
store.event(key(pygame.K_2))
premium_index = next(i for i, frame in enumerate(store.items)
                     if frame["source"] == "COINS" and frame["rarity"] == "LEGENDARY")
store.sel = premium_index
store.event(key(pygame.K_RETURN))
assert "PURCHASED" in store.message or "ALREADY OWNED" in store.message
store.event(key(pygame.K_5))
card_index = next(i for i, card in enumerate(store.items) if card["source"] == "COINS")
store.sel = card_index
app.stats.grant_coins(store.items[card_index]["price"])
store.event(key(pygame.K_RETURN))
assert "PURCHASED" in store.message
assert app.stats.equipped_calling_card() == store.items[card_index]["id"]
store.draw(app.canvas)
store.event(key(pygame.K_2))
for frame in store.items:
    gfx.draw_profile_avatar(app.canvas, (640, 360), 80, None, frame, 1.25)
menu.draw(app.canvas)
profile.draw(app.canvas)
assert app.stats.player_uid() == uid
print("profile and main-menu armory console ok")

hud_editor = HudEditorScene(app)
old_hud_move = list(app.settings["hud_controls"]["move"])
hud_editor.event(pygame.Event(pygame.MOUSEBUTTONDOWN, button=1,
                              pos=(int(old_hud_move[0] * 1280), int(old_hud_move[1] * 720))))
hud_editor.event(pygame.Event(pygame.MOUSEMOTION, pos=(210, 510)))
hud_editor.event(pygame.Event(pygame.MOUSEBUTTONUP, button=1, pos=(210, 510)))
assert app.settings["hud_controls"]["move"][:2] != old_hud_move[:2]
old_size = app.settings["hud_controls"]["move"][2]
hud_editor.event(pygame.Event(pygame.MOUSEWHEEL, y=1))
assert app.settings["hud_controls"]["move"][2] > old_size
hud_editor.event(key(pygame.K_RETURN))
hud_editor.draw(app.canvas)
reloaded_settings = Settings()
assert reloaded_settings["hud_controls"]["move"][:2] == app.settings["hud_controls"]["move"][:2]
print("touch HUD layout editor ok")

campaign = CampaignScene(app)
campaign.selected = 1
scene_count = len(app.scenes)
campaign.start()
assert len(app.scenes) == scene_count, "locked campaign chapters must not start"
campaign.selected = 0
campaign.start()
campaign_character = app.scenes[-1]
assert isinstance(campaign_character, CharacterScene)
assert campaign_character.flow["campaign_mission"] == 0
campaign_character.confirm()
campaign_loadout = app.scenes[-1]
assert isinstance(campaign_loadout, LoadoutScene)
campaign_loadout.done()
campaign_briefing = app.scenes[-1]
assert isinstance(campaign_briefing, BriefingScene)
campaign_briefing.start()
campaign_match = app.scenes[-1]
assert isinstance(campaign_match, MatchScene)
assert campaign_match.campaign_index == 0
campaign_match.m.mode.over = True
campaign_match.m.mode.winner = 0
campaign_match._record()
assert campaign_match.result["campaign_progress"] == 1
assert app.stats.campaign_progress() == 1
assert len(CAMPAIGN_MISSIONS) in (5, 9)
CampaignScene(app).draw(app.canvas)
print("campaign chapter unlock, mission flow, and victory progress ok")

for mode, mp in [("ctf", "depot_09"), ("snd", "blacksite"), ("hardpoint", "frontier"), ("practice", "range")]:
    app.settings["difficulty"] = "ELITE"
    ms = MatchScene(app, mode, mp)
    type_command(ms, "/unliamo")
    assert ms.unlimited_ammo and all(w.unlimited for w in ms.m.player.weapons)
    type_command(ms, "/immortal")
    assert ms.m.player.immortal
    ms.event(pygame.Event(pygame.MOUSEMOTION, rel=(30, -10), pos=(0, 0)))
    for i in range(600):
        if i == 0:
            ms.indicators = [[0.0, 0.01]]
        if i == 50:
            ms.event(key(ms.keys["ability"]))
            ms.event(key(ms.keys["reload"]))
            ms.event(key(pygame.K_2))
            if mode == "practice":
                for kk in (pygame.K_RIGHTBRACKET, pygame.K_b, pygame.K_c, pygame.K_t):
                    ms.event(key(kk))
        ms.update(1 / 60)
        if i == 0:
            assert all(t > 0 for _, t in ms.indicators), "expired damage indicators should be removed before drawing"
        ms.draw(app.canvas)
        ms.r.draw_scoreboard(app.canvas)
    ms.event(key(pygame.K_ESCAPE))
    ms.update(0.016)
    ms.draw(app.canvas)
    ms.pause_menu.event(key(pygame.K_RETURN))
    ms.m.mode.finish(0)
    for _ in range(120):
        ms.update(1 / 60)
        ms.draw(app.canvas)
    print(mode, "match scene ok; scores", ms.m.mode.scores, "recorded", ms.recorded)

respawn_scene = MatchScene(app, "ctf", "depot_09")
respawn_player = respawn_scene.m.player
respawn_enemy = next(c for c in respawn_scene.m.combatants if c.team == 1)
respawn_scene.m.kill(respawn_player, respawn_enemy, "p9", False)
assert respawn_player.awaiting_loadout
old_primary = respawn_player.weapon.s["id"]
respawn_scene.event(key(pygame.K_RIGHT))
assert respawn_scene.respawn_primary != old_primary
respawn_scene.event(key(pygame.K_DOWN))
respawn_scene.event(key(pygame.K_RIGHT))
respawn_scene.event(key(pygame.K_RETURN))
assert respawn_player.alive and not respawn_player.awaiting_loadout
assert respawn_player.weapon.s["id"] == respawn_scene.respawn_primary
assert app.settings["loadout"]["primary"] == respawn_scene.respawn_primary
print("death loadout selection and respawn ok")

skin = app.stats.add_skin(respawn_player.weapon.s["id"], "EPIC", "Aurora Test Pattern")
assert app.stats.equip_skin(skin["id"])
respawn_player.equipped_skins = app.stats.equipped_skins()
assert respawn_player.equipped_skins[respawn_player.weapon.s["id"]]["name"] == "Aurora Test Pattern"
respawn_scene.r._combatant(app.canvas, respawn_player, (0, 0), 0)
print("equipped weapon skin rendering ok")

assist_scene = MatchScene(app, "ctf", "depot_09")
assist_player = assist_scene.m.player
assist_enemy = next(c for c in assist_scene.m.combatants if c.team == 1)
for combatant in assist_scene.m.combatants:
    if combatant.team == 1 and combatant is not assist_enemy:
        combatant.alive = False
assist_scene.m.map.los = lambda *args: True
assist_player.x, assist_player.y = 1000, 1000
assist_enemy.x, assist_enemy.y = 1200, 1030
assist_scene.cam = [assist_player.x, assist_player.y]
assist_scene.cursor = (640 + 200, 360)
old_mouse_buttons = pygame.mouse.get_pressed
pygame.mouse.get_pressed = lambda: (0, 0, 1)
try:
    assist_scene._apply_input(1 / 60)
finally:
    pygame.mouse.get_pressed = old_mouse_buttons
assert 0 < assist_player.aim < math.atan2(30, 200), "player aim assist should pull toward a visible target"
app.touch_enabled = True
move_control = app.settings["hud_controls"]["move"]
move_pos = (move_control[0] * 1280, move_control[1] * 720)
finger_down = getattr(pygame, "FINGERDOWN")
finger_motion = getattr(pygame, "FINGERMOTION")
finger_up = getattr(pygame, "FINGERUP")
assist_scene.event(pygame.Event(finger_down, finger_id=7, x=move_pos[0] / 1280, y=move_pos[1] / 720))
assist_scene.event(pygame.Event(finger_motion, finger_id=7,
                                x=(move_pos[0] + 30) / 1280, y=move_pos[1] / 720))
assist_scene._apply_input(1 / 60)
assert assist_player.mx > 0, "mobile movement control should steer the player"
fire_control = app.settings["hud_controls"]["fire"]
assist_scene.event(pygame.Event(finger_down, finger_id=8, x=fire_control[0], y=fire_control[1]))
assist_scene._apply_input(1 / 60)
assert assist_player.trigger, "mobile fire control should hold the trigger"
assist_scene.event(pygame.Event(finger_up, finger_id=8, x=fire_control[0], y=fire_control[1]))
assist_scene.event(pygame.Event(finger_up, finger_id=7, x=move_pos[0] / 1280, y=move_pos[1] / 720))
app.touch_enabled = False

ground_war_menu = MainMenu(app)
assert any(label == "GROUND WAR EVENT 50v50" for label, _ in ground_war_menu.menu.items)
previous_scene_count = len(app.scenes)
ground_war_menu.ground_war()
assert app.scenes[-1].flow["mode"] == "groundwar"
app.scenes.pop()
assert len(app.scenes) == previous_scene_count
ground_war_match = MatchScene(app, "groundwar", "ground_war")
assert sum(c.team == 0 for c in ground_war_match.m.combatants) == 50
assert sum(c.team == 1 for c in ground_war_match.m.combatants) == 50
ground_war_match.m.update(1 / 60)
ground_war_match.draw(app.canvas)
ground_war_match.r.draw_scoreboard(app.canvas)
print("player aim assist and 50v50 Ground War event ok")

nuke_scene = MatchScene(app, "ctf", "depot_09")
nuke_scene.m.player.nuke_charges = 1
nuke_scene._run_cheat("/nuke")
assert nuke_scene.chat_message == "NUKE CALLED IN!"
assert not any(c.alive and c.team == 1 for c in nuke_scene.m.combatants)
nuke_scene.draw(app.canvas)
print("stats:", app.stats.summary()["matches"], "matches saved")

admin_match = MatchScene(app, "ctf", "depot_09")
type_command(admin_match, "/admin unlock legendary")
assert "LEGENDARY ARMORY UNLOCKED" in admin_match.chat_message
assert "solstice" in app.stats.unlocked_weapon_ids()

dragon_scene = MatchScene(app, "ctf", "depot_09")
dragon_scene.m.player.kill_effect_weapons = {"m4_emberwyrm"}
dragon_victim = next(c for c in dragon_scene.m.combatants if c.team == 1)
dragon_scene.m.kill(dragon_victim, dragon_scene.m.player, "m4_emberwyrm", False)
dragon_effect = next(effect for effect in dragon_scene.m.fx if effect.kind == "dragon_death")
dragon_scene.r._fx(app.canvas, dragon_effect, (0, 0), True)

holger_scene = MatchScene(app, "ctf", "depot_09")
assert "holger_galactic_stars" in holger_scene.m.player.kill_effect_weapons
holger_victim = next(c for c in holger_scene.m.combatants if c.team == 1)
holger_scene.m.kill(holger_victim, holger_scene.m.player, "holger_galactic_stars", False)
nova_effect = next(effect for effect in holger_scene.m.fx if effect.kind == "supernova_death")
holger_scene.r._fx(app.canvas, nova_effect, (0, 0), True)

ranked_end_scene = MatchScene(app, "hardpoint", "frontier", ranked=True)
ranked_end_scene.m.mode.finish(0)
for _ in range(100):
    ranked_end_scene.update(1 / 60)
ranked_end_scene.draw(app.canvas)

briefing = BriefingScene(app, dict(mode="ctf", map="depot_09"))
briefing.event(key(pygame.K_SLASH))
for char in "admin unlock legendary":
    briefing.event(pygame.Event(pygame.KEYDOWN, key=0, unicode=char))
briefing.event(key(pygame.K_RETURN))
assert "LEGENDARY ARMORY UNLOCKED" in briefing.admin_message
assert any(skin["kill_effect"] for skin in app.stats.skins())
map_select = MapSelect(app, {})
map_select.event(key(pygame.K_r))
assert map_select.ranked
print("admin unlock and ranked selection ok")
