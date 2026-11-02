import json
import importlib
import os
import random
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Dict

from .campaign import CAMPAIGN_MISSIONS
from .config import ROOT, SAVE_DIR, weapon_list, weapons
from .progression import (CRATE_LEVEL_INTERVAL, CRATE_RARITY_WEIGHTS, LEVEL_WEAPON_REWARDS, RANKED_LOSS_POINTS,
                          AVATAR_FRAMES, CALLING_CARDS, RANKED_WIN_POINTS, SKIN_DESIGNS, legendary_skin_name,
                          legendary_weapon_ids, STORE_SKIN_PRICES, legendary_skin_effect, random_skin_name, rank_for_points)

RESOLUTIONS = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)]
FPS_CAPS = [30, 60, 120, 144, 0]
TRIMS = [(1, "AMBER", (255, 170, 40)), (2, "CYAN", (80, 210, 220)), (3, "BONE", (225, 222, 205)),
         (5, "MAGENTA", (225, 80, 190)), (8, "GOLD", (240, 205, 70))]
KEY_LABELS = [("up", "MOVE UP"), ("down", "MOVE DOWN"), ("left", "MOVE LEFT"), ("right", "MOVE RIGHT"),
              ("reload", "RELOAD"), ("ability", "ABILITY"), ("interact", "INTERACT"), ("sprint", "SPRINT"),
              ("switch", "SWITCH WEAPON"), ("scoreboard", "SCOREBOARD"), ("tactical", "TACTICAL MAP")]
DEFAULT_KEYS = dict(up="w", down="s", left="a", right="d", reload="r", ability="space", interact="e",
                    sprint="left shift", switch="q", scoreboard="tab", tactical="m")
DEFAULT_LOADOUT = dict(char="vanguard", primary="vanguard", secondary="p9", equipment="none", scorestreaks=["uav", "hunter_killer", "shield_turret"])
DEFAULT_HUD_CONTROLS = {
    "move": [0.12, 0.82, 1.0], "aim": [0.76, 0.80, 1.0], "fire": [0.91, 0.66, 1.0],
    "ads": [0.91, 0.85, 0.82], "reload": [0.82, 0.91, 0.78], "ability": [0.70, 0.91, 0.78],
    "switch": [0.99, 0.87, 0.72], "interact": [0.59, 0.91, 0.72],
}
DEFAULTS = dict(master=0.8, music=0.35, sfx=0.8, res=0, fullscreen=False, fps=2, mouse_sens=1.0, aim_sens=0.6,
                shake=True, fx="HIGH", difficulty="NORMAL", minimap=True, minimap_size=1, ui_scale=1.0,
                trim=0, keys=DEFAULT_KEYS, loadout=DEFAULT_LOADOUT, hud_controls=DEFAULT_HUD_CONTROLS,
                match_server="127.0.0.1:8765",
                loadout_slots=[dict(DEFAULT_LOADOUT) for _ in range(10)], active_loadout_slot=1)


class Settings(dict):
    path = SAVE_DIR / "settings.json"

    def __init__(self):
        super().__init__(json.loads(json.dumps(DEFAULTS)))
        data = {}
        try:
            data = json.loads(self.path.read_text())
            for k, v in data.items():
                if k in DEFAULTS:
                    if isinstance(DEFAULTS[k], dict) and isinstance(v, dict):
                        self[k].update(v)
                    elif not isinstance(DEFAULTS[k], dict):
                        self[k] = v
        except (OSError, ValueError):
            pass
        if "loadout_slots" not in data or not isinstance(self["loadout_slots"], list):
            self["loadout_slots"] = [dict(self["loadout"]) for _ in range(10)]
        else:
            slots = [slot for slot in self["loadout_slots"] if isinstance(slot, dict)]
            while len(slots) < 10:
                slots.append(dict(self["loadout"]))
            self["loadout_slots"] = slots[:10]
        for control, default in DEFAULT_HUD_CONTROLS.items():
            saved = self["hud_controls"].get(control)
            if (not isinstance(saved, (list, tuple)) or len(saved) != 3 or
                    not all(isinstance(value, (int, float)) for value in saved)):
                self["hud_controls"][control] = list(default)
            else:
                self["hud_controls"][control] = [
                    min(0.99, max(0.01, float(saved[0]))),
                    min(0.99, max(0.01, float(saved[1]))),
                    min(1.5, max(0.5, float(saved[2]))),
                ]
        if not isinstance(self["match_server"], str):
            self["match_server"] = DEFAULTS["match_server"]
        self["active_loadout_slot"] = min(10, max(1, int(self["active_loadout_slot"])))
        if "loadout_slots" in data and isinstance(data.get("loadout_slots"), list):
            self["loadout"] = dict(self["loadout_slots"][self["active_loadout_slot"] - 1])

    def save(self):
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self, indent=1))
        except OSError:
            pass

    def reset(self):
        loadout = dict(self["loadout"])
        self.clear()
        self.update(json.loads(json.dumps(DEFAULTS)))
        self["loadout"] = loadout
        self["loadout_slots"][0] = dict(loadout)
        self.save()


def load_env_file():
    for p in (ROOT / ".env", Path.cwd() / ".env"):
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("\"'")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass


def level_for(xp: int) -> int:
    return xp // 250 + 1


class StatsDB:
    def __init__(self, path=None):
        load_env_file()
        self.mysql_enabled = os.environ.get("OVERHEAD_OPS_MYSQL_ENABLED", os.environ.get("MYSQL_ENABLED", "")).lower() in ("1", "true", "yes")
        self.mysql_host = os.environ.get("OVERHEAD_OPS_MYSQL_HOST", os.environ.get("MYSQL_HOST", "127.0.0.1"))
        self.mysql_port = int(os.environ.get("OVERHEAD_OPS_MYSQL_PORT", os.environ.get("MYSQL_PORT", "3306")))
        self.mysql_database = os.environ.get("OVERHEAD_OPS_MYSQL_DATABASE", os.environ.get("MYSQL_DATABASE", "overhead_ops"))
        self.mysql_user = os.environ.get("OVERHEAD_OPS_MYSQL_USER", os.environ.get("MYSQL_USER", "root"))
        self.mysql_password = os.environ.get("OVERHEAD_OPS_MYSQL_PASSWORD", os.environ.get("MYSQL_PASSWORD", ""))
        if self.mysql_enabled and not self.mysql_password:
            raise RuntimeError("MySQL mirroring is enabled but no MySQL password is configured.")
        self._mysql_connection = None
        self._mysql_connector = None
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path or SAVE_DIR / "stats.db"))
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY, ts REAL, mode TEXT, map TEXT, difficulty TEXT,
                won INTEGER, kills INTEGER, deaths INTEGER, shots INTEGER, hits INTEGER, headshots INTEGER, xp INTEGER);
            CREATE TABLE IF NOT EXISTS weapon_kills(weapon TEXT PRIMARY KEY, kills INTEGER);
            CREATE TABLE IF NOT EXISTS profile(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS weapon_unlocks(weapon_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS owned_skins(id TEXT PRIMARY KEY, weapon_id TEXT NOT NULL, name TEXT NOT NULL,
                rarity TEXT NOT NULL, kill_effect INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS equipped_skins(weapon_id TEXT PRIMARY KEY, skin_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS avatar_frame_unlocks(frame_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS calling_card_unlocks(card_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS owned_scorestreaks(streak_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS owned_scorestreak_skins(streak_id TEXT NOT NULL, skin_id TEXT NOT NULL,
                PRIMARY KEY(streak_id, skin_id));
            CREATE TABLE IF NOT EXISTS equipped_scorestreak_skins(streak_id TEXT PRIMARY KEY, skin_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS season_history(
                season INTEGER NOT NULL,
                highest_rank TEXT NOT NULL,
                highest_points INTEGER NOT NULL,
                ended_at REAL NOT NULL,
                PRIMARY KEY(season)
            );
        """)
        if self._profile_value("player_uid") is None:
            self._set_profile_value("player_uid", f"OPS-{uuid.uuid4().hex[:10].upper()}")
        if self._profile_value("player_name") is None:
            self._set_profile_value("player_name", "PLAYER")
        self.db.executemany("INSERT OR IGNORE INTO avatar_frame_unlocks(frame_id) VALUES(?)",
                            ((frame["id"],) for frame in AVATAR_FRAMES if frame["source"] == "FREE"))
        self.db.executemany("INSERT OR IGNORE INTO calling_card_unlocks(card_id) VALUES(?)",
                            ((card["id"],) for card in CALLING_CARDS if card["source"] == "FREE"))
        self._commit()

    def _commit(self):
        self.db.commit()
        self._sync_mysql()

    def _sync_mysql(self):
        if not self.mysql_enabled:
            return
        if self._mysql_connector is None:
            try:
                self._mysql_connector = importlib.import_module("mysql.connector")
            except ImportError as exc:
                raise RuntimeError(
                    "MySQL mirroring is enabled but mysql-connector-python is not installed"
                ) from exc
        connector = self._mysql_connector
        if self._mysql_connection is None or not self._mysql_connection.is_connected():
            try:
                self._mysql_connection = connector.connect(
                    host=self.mysql_host, port=self.mysql_port, user=self.mysql_user,
                    password=self.mysql_password, database=self.mysql_database)
            except connector.Error as exc:
                self._mysql_connection = None
                return
            self._ensure_mysql_schema()

        uid = self.player_uid()
        xp = self.db.execute("SELECT COALESCE(SUM(xp),0) FROM matches").fetchone()[0]
        profile = (uid, self.player_name(), self._profile_int("rank_points"),
                   self.campaign_progress(), xp, self.coins(), self.crate_count(),
                   self._profile_value("avatar_frame"))
        try:
            with self._mysql_connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO player_profiles "
                    "(player_uid,player_name,rank_points,campaign_completed,xp,coins,crates,avatar_frame) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                    "player_name=VALUES(player_name),rank_points=VALUES(rank_points),"
                    "campaign_completed=VALUES(campaign_completed),xp=VALUES(xp),coins=VALUES(coins),"
                    "crates=VALUES(crates),avatar_frame=VALUES(avatar_frame)", profile)
                table_queries = (
                    ("match_history", "DELETE FROM match_history WHERE player_uid=%s",
                     "INSERT INTO match_history "
                     "(player_uid,local_match_id,played_at,mode,map_id,difficulty,won,kills,deaths,shots,hits,headshots,xp) "
                     "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                     "SELECT id,ts,mode,map,difficulty,won,kills,deaths,shots,hits,headshots,xp FROM matches"),
                    ("weapon_kills", "DELETE FROM weapon_kills WHERE player_uid=%s",
                     "INSERT INTO weapon_kills (player_uid,weapon_id,kills) VALUES (%s,%s,%s)",
                     "SELECT weapon,kills FROM weapon_kills"),
                    ("weapon_unlocks", "DELETE FROM weapon_unlocks WHERE player_uid=%s",
                     "INSERT INTO weapon_unlocks (player_uid,weapon_id) VALUES (%s,%s)",
                     "SELECT weapon_id FROM weapon_unlocks"),
                    ("owned_skins", "DELETE FROM owned_skins WHERE player_uid=%s",
                     "INSERT INTO owned_skins (player_uid,skin_id,weapon_id,name,rarity,kill_effect) "
                     "VALUES (%s,%s,%s,%s,%s,%s)",
                     "SELECT id,weapon_id,name,rarity,kill_effect FROM owned_skins"),
                    ("equipped_skins", "DELETE FROM equipped_skins WHERE player_uid=%s",
                     "INSERT INTO equipped_skins (player_uid,weapon_id,skin_id) VALUES (%s,%s,%s)",
                     "SELECT weapon_id,skin_id FROM equipped_skins"),
                    ("avatar_frame_unlocks", "DELETE FROM avatar_frame_unlocks WHERE player_uid=%s",
                     "INSERT INTO avatar_frame_unlocks (player_uid,frame_id) VALUES (%s,%s)",
                     "SELECT frame_id FROM avatar_frame_unlocks"),
                    ("calling_card_unlocks", "DELETE FROM calling_card_unlocks WHERE player_uid=%s",
                     "INSERT INTO calling_card_unlocks (player_uid,card_id,equipped) VALUES (%s,%s,%s)",
                     "SELECT card_id FROM calling_card_unlocks"),
                    ("season_history", "DELETE FROM season_history WHERE player_uid=%s",
                     "INSERT INTO season_history (player_uid,season,highest_rank,highest_points,ended_at) "
                     "VALUES (%s,%s,%s,%s,%s)",
                     "SELECT season,highest_rank,highest_points,ended_at FROM season_history"),
                )
                for table, delete_sql, insert_sql, select_sql in table_queries:
                    cursor.execute(delete_sql, (uid,))
                    rows = self.db.execute(select_sql).fetchall()
                    if table == "match_history":
                        values = [(uid, *row) for row in rows]
                    elif table == "weapon_kills":
                        values = [(uid, *row) for row in rows]
                    elif table == "weapon_unlocks" or table == "avatar_frame_unlocks":
                        values = [(uid, row[0]) for row in rows]
                    elif table == "calling_card_unlocks":
                        equipped_card = self.equipped_calling_card()
                        values = [(uid, row[0], row[0] == equipped_card) for row in rows]
                    else:
                        values = [(uid, *row) for row in rows]
                    if values:
                        cursor.executemany(insert_sql, values)
            self._mysql_connection.commit()
        except connector.Error as exc:
            self._mysql_connection.rollback()
            self._mysql_connection.close()
            self._mysql_connection = None
            raise RuntimeError(
                "MySQL mirroring failed; the local SQLite save is intact. "
                "Check the MySQL service, database, and environment configuration."
            ) from exc

    def _ensure_mysql_schema(self):
        statements = (
            "CREATE TABLE IF NOT EXISTS player_profiles (player_uid VARCHAR(40) PRIMARY KEY,"
            "player_name VARCHAR(20) NOT NULL,rank_points INT UNSIGNED NOT NULL,"
            "campaign_completed INT UNSIGNED NOT NULL,xp BIGINT UNSIGNED NOT NULL,"
            "coins BIGINT UNSIGNED NOT NULL,crates INT UNSIGNED NOT NULL,avatar_frame VARCHAR(64) NULL)",
            "CREATE TABLE IF NOT EXISTS match_history (player_uid VARCHAR(40) NOT NULL,"
            "local_match_id BIGINT NOT NULL,played_at DOUBLE NOT NULL,mode VARCHAR(32) NOT NULL,"
            "map_id VARCHAR(64) NOT NULL,difficulty VARCHAR(32) NOT NULL,won TINYINT NOT NULL,"
            "kills INT NOT NULL,deaths INT NOT NULL,shots INT NOT NULL,hits INT NOT NULL,"
            "headshots INT NOT NULL,xp INT NOT NULL,PRIMARY KEY (player_uid,local_match_id))",
            "CREATE TABLE IF NOT EXISTS weapon_kills (player_uid VARCHAR(40) NOT NULL,"
            "weapon_id VARCHAR(64) NOT NULL,kills INT NOT NULL,PRIMARY KEY (player_uid,weapon_id))",
            "CREATE TABLE IF NOT EXISTS weapon_unlocks (player_uid VARCHAR(40) NOT NULL,"
            "weapon_id VARCHAR(64) NOT NULL,PRIMARY KEY (player_uid,weapon_id))",
            "CREATE TABLE IF NOT EXISTS owned_skins (player_uid VARCHAR(40) NOT NULL,"
            "skin_id VARCHAR(64) NOT NULL,weapon_id VARCHAR(64) NOT NULL,name VARCHAR(128) NOT NULL,"
            "rarity VARCHAR(16) NOT NULL,kill_effect TINYINT NOT NULL,PRIMARY KEY (player_uid,skin_id))",
            "CREATE TABLE IF NOT EXISTS equipped_skins (player_uid VARCHAR(40) NOT NULL,"
            "weapon_id VARCHAR(64) NOT NULL,skin_id VARCHAR(64) NOT NULL,PRIMARY KEY (player_uid,weapon_id))",
            "CREATE TABLE IF NOT EXISTS avatar_frame_unlocks (player_uid VARCHAR(40) NOT NULL,"
            "frame_id VARCHAR(64) NOT NULL,PRIMARY KEY (player_uid,frame_id))",
            "CREATE TABLE IF NOT EXISTS calling_card_unlocks (player_uid VARCHAR(40) NOT NULL,"
            "card_id VARCHAR(64) NOT NULL,equipped TINYINT NOT NULL DEFAULT 0,PRIMARY KEY (player_uid,card_id))",
            "CREATE TABLE IF NOT EXISTS season_history (player_uid VARCHAR(40) NOT NULL,"
            "season INT NOT NULL,highest_rank VARCHAR(64) NOT NULL,highest_points INT NOT NULL,"
            "ended_at DOUBLE NOT NULL,PRIMARY KEY (player_uid,season))",
        )
        try:
            with self._mysql_connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            self._mysql_connection.commit()
        except self._mysql_connector.Error as exc:
            self._mysql_connection.rollback()
            self._mysql_connection.close()
            self._mysql_connection = None
            raise RuntimeError(
                "Could not create the MySQL mirror tables; the local SQLite save is intact."
            ) from exc

    def _profile_value(self, key):
        row = self.db.execute("SELECT value FROM profile WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _set_profile_value(self, key, value):
        self.db.execute("INSERT INTO profile(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, str(value)))

    def player_uid(self):
        return self._profile_value("player_uid")

    def player_name(self):
        return self._profile_value("player_name") or "PLAYER"

    def set_player_name(self, name):
        # Sanitize: strip, collapse whitespace, remove control chars and SQL-risky chars
        import re
        name = re.sub(r'[\x00-\x1f\x7f;\'\"\\\/\-\-]', '', name)
        name = " ".join(name.split())[:20]
        if not name or len(name) < 1:
            return False
        self._set_profile_value("player_name", name)
        self._commit()
        return True

    def player_picture(self):
        return self._profile_value("player_picture")

    def set_player_picture(self, path):
        self._set_profile_value("player_picture", str(path))
        self._commit()

    def coins(self):
        return self._profile_int("coins")

    def grant_coins(self, amount):
        if not isinstance(amount, int) or amount < 0:
            raise ValueError("Coin grant must be a non-negative integer")
        total = self.coins() + amount
        self._set_profile_int("coins", total)
        self._commit()
        return total

    def unlocked_avatar_frames(self):
        return {row[0] for row in self.db.execute("SELECT frame_id FROM avatar_frame_unlocks")}

    def equipped_avatar_frame(self):
        selected = self._profile_value("avatar_frame")
        return selected if selected in self.unlocked_avatar_frames() else "rookie_ring"

    def equip_avatar_frame(self, frame_id):
        if frame_id not in self.unlocked_avatar_frames():
            return False
        self._set_profile_value("avatar_frame", frame_id)
        self._commit()
        return True

    def buy_avatar_frame(self, frame_id):
        frame = next((item for item in AVATAR_FRAMES if item["id"] == frame_id), None)
        if frame is None or frame["source"] != "COINS":
            return False
        if frame_id in self.unlocked_avatar_frames():
            return True
        if self.coins() < frame["price"]:
            return False
        self._set_profile_int("coins", self.coins() - frame["price"])
        self.db.execute("INSERT OR IGNORE INTO avatar_frame_unlocks(frame_id) VALUES(?)", (frame_id,))
        self._commit()
        return True

    def owned_calling_card_ids(self):
        return {row[0] for row in self.db.execute("SELECT card_id FROM calling_card_unlocks")}

    def equipped_calling_card(self):
        selected = self._profile_value("calling_card")
        return selected if selected in self.owned_calling_card_ids() else "frontline_veteran"

    def equip_calling_card(self, card_id):
        if card_id not in self.owned_calling_card_ids():
            return False
        self._set_profile_value("calling_card", card_id)
        self._commit()
        return True

    def buy_calling_card(self, card_id):
        card = next((item for item in CALLING_CARDS if item["id"] == card_id), None)
        if card is None:
            return {"status": "unavailable"}
        if card_id in self.owned_calling_card_ids():
            self.equip_calling_card(card_id)
            return {"status": "already_owned", "name": card["name"]}
        if card["source"] != "COINS":
            return {"status": "unavailable"}
        if self.coins() < card["price"]:
            return {"status": "insufficient_coins", "price": card["price"]}
        with self.db:
            self._set_profile_int("coins", self.coins() - card["price"])
            self.db.execute("INSERT INTO calling_card_unlocks(card_id) VALUES(?)", (card_id,))
            self._set_profile_value("calling_card", card_id)
        self._sync_mysql()
        return {"status": "purchased", "name": card["name"], "price": card["price"]}

    def scorestreak_level(self):
        xp = self.db.execute("SELECT COALESCE(SUM(xp),0) FROM matches").fetchone()[0]
        return level_for(xp)

    def unlocked_scorestreak_ids(self):
        from .scorestreaks import SCORESTREAKS
        level = self.scorestreak_level()
        purchased = {row[0] for row in self.db.execute("SELECT streak_id FROM owned_scorestreaks")}
        return {item["id"] for item in SCORESTREAKS
                if (item["price"] == 0 and item["unlock_level"] <= level) or item["id"] in purchased}

    def buy_scorestreak(self, streak_id):
        from .scorestreaks import SCORESTREAKS
        item = next((x for x in SCORESTREAKS if x["id"] == streak_id), None)
        if item is None:
            return {"status": "unavailable"}
        if item["id"] in self.unlocked_scorestreak_ids():
            return {"status": "already_owned", "name": item["name"]}
        if item["unlock_level"] > self.scorestreak_level():
            return {"status": "level_locked", "level": item["unlock_level"]}
        if item["price"] <= 0:
            return {"status": "level_locked", "level": item["unlock_level"]}
        if self.coins() < item["price"]:
            return {"status": "insufficient_coins", "price": item["price"]}
        with self.db:
            self._set_profile_int("coins", self.coins() - item["price"])
            self.db.execute("INSERT OR IGNORE INTO owned_scorestreaks(streak_id) VALUES(?)", (streak_id,))
        self._sync_mysql()
        return {"status": "purchased", "name": item["name"], "price": item["price"]}

    def owned_scorestreak_skins(self, streak_id):
        from .scorestreaks import STREAK_SKINS
        owned = {row[0] for row in self.db.execute(
            "SELECT skin_id FROM owned_scorestreak_skins WHERE streak_id=?", (streak_id,))}
        return [dict(item) for item in STREAK_SKINS if item["id"] in owned]

    def buy_scorestreak_skin(self, streak_id, skin_id):
        from .scorestreaks import STREAK_SKINS, SCORESTREAKS
        if streak_id not in self.unlocked_scorestreak_ids() or not any(x["id"] == streak_id for x in SCORESTREAKS):
            return {"status": "unavailable"}
        skin = next((x for x in STREAK_SKINS if x["id"] == skin_id), None)
        if skin is None:
            return {"status": "unavailable"}
        owned = {row[0] for row in self.db.execute(
            "SELECT skin_id FROM owned_scorestreak_skins WHERE streak_id=?", (streak_id,))}
        if skin_id in owned:
            self._set_profile_value("equipped_scorestreak_skin:" + streak_id, skin_id)
            self._commit()
            return {"status": "already_owned", "name": skin["name"]}
        if self.coins() < skin["price"]:
            return {"status": "insufficient_coins", "price": skin["price"]}
        with self.db:
            self._set_profile_int("coins", self.coins() - skin["price"])
            self.db.execute("INSERT INTO owned_scorestreak_skins(streak_id,skin_id) VALUES(?,?)", (streak_id, skin_id))
            self._set_profile_value("equipped_scorestreak_skin:" + streak_id, skin_id)
        self._sync_mysql()
        return {"status": "purchased", "name": skin["name"], "price": skin["price"]}

    def equipped_scorestreak_skin(self, streak_id):
        return self._profile_value("equipped_scorestreak_skin:" + streak_id)

    def buy_store_skin(self, weapon_id, design_id):
        spec = weapons().get(weapon_id)
        design = next((item for item in SKIN_DESIGNS if item["id"] == design_id), None)
        if spec is None or design is None or weapon_id not in self.unlocked_weapon_ids():
            return dict(status="unavailable")
        name = (legendary_skin_name(spec["name"], design["name"]) if design["rarity"] == "LEGENDARY"
                else f"{design['name']} {spec['name']}")
        price = STORE_SKIN_PRICES[design["rarity"]]
        with self.db:
            existing = self.db.execute("SELECT id FROM owned_skins WHERE weapon_id=? AND name=?",
                                       (weapon_id, name)).fetchone()
            if existing:
                skin_id = existing[0]
                already_owned = True
            else:
                if self.coins() < price:
                    return dict(status="insufficient_coins", price=price)
                skin_id = uuid.uuid4().hex
                kill_effect = int(design["rarity"] == "LEGENDARY")
                self.db.execute("INSERT INTO owned_skins(id,weapon_id,name,rarity,kill_effect) VALUES(?,?,?,?,?)",
                                (skin_id, weapon_id, name, design["rarity"], kill_effect))
                self._set_profile_int("coins", self.coins() - price)
                already_owned = False
            self.db.execute("INSERT INTO equipped_skins(weapon_id,skin_id) VALUES(?,?) "
                            "ON CONFLICT(weapon_id) DO UPDATE SET skin_id=excluded.skin_id", (weapon_id, skin_id))
        self._sync_mysql()
        return dict(status="already_owned" if already_owned else "purchased", id=skin_id, weapon_id=weapon_id,
                    weapon_name=spec["name"], name=name, rarity=design["rarity"], price=price,
                    kill_effect=design["rarity"] == "LEGENDARY",
                    effect_id=legendary_skin_effect(name, skin_id) if design["rarity"] == "LEGENDARY" else None)

    def grant_all_avatar_frames(self):
        ids = [frame["id"] for frame in AVATAR_FRAMES]
        self.db.executemany("INSERT OR IGNORE INTO avatar_frame_unlocks(frame_id) VALUES(?)",
                            ((frame_id,) for frame_id in ids))
        self._commit()
        return ids

    def _profile_int(self, key, default=0):
        row = self.db.execute("SELECT value FROM profile WHERE key=?", (key,)).fetchone()
        return int(row[0]) if row else default

    def _set_profile_int(self, key, value):
        self.db.execute("INSERT INTO profile(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, str(value)))

    def campaign_progress(self):
        return min(len(CAMPAIGN_MISSIONS), max(0, self._profile_int("campaign_completed")))

    def complete_campaign_mission(self, mission_index):
        if not isinstance(mission_index, int) or not 0 <= mission_index < len(CAMPAIGN_MISSIONS):
            raise ValueError(f"Unknown campaign mission index: {mission_index}")
        progress = self.campaign_progress()
        if mission_index > progress:
            raise ValueError("Campaign missions must be completed in order")
        progress = max(progress, mission_index + 1)
        self._set_profile_int("campaign_completed", progress)
        self._commit()
        return progress

    def rank(self):
        return rank_for_points(self._profile_int("rank_points"))

    def set_rank_points(self, points):
        if not isinstance(points, int) or points < 0:
            raise ValueError("Rank points must be a non-negative integer")
        self._set_profile_int("rank_points", points)
        self._commit()
        return self.rank()

    def end_season(self):
        """End current season: record highest rank achieved, return season summary."""
        rank = self.rank()
        seasons = self.db.execute("SELECT COALESCE(MAX(season),0) FROM season_history").fetchone()[0]
        new_season = seasons + 1
        self.db.execute(
            "INSERT INTO season_history(season,highest_rank,highest_points,ended_at) VALUES(?,?,?,?)",
            (new_season, rank["tier"], rank["points"], time.time()))
        # Reset rank points for new season (keep some based on tier)
        from .progression import RANK_TIERS
        _rank_base = getattr(__import__('src.progression', fromlist=['_rank_base']), '_rank_base', None) if hasattr(__import__('src.progression', fromlist=['_rank_base']), '_rank_base') else None
        carryover = min(rank["points"] // 4, 200)  # carry over up to 200 points
        self._set_profile_int("rank_points", carryover)
        self._commit()
        return dict(season=new_season, highest_rank=rank["tier"], highest_points=rank["points"],
                    new_points=carryover)

    def season_history(self):
        """Return list of all past season records."""
        rows = self.db.execute(
            "SELECT season,highest_rank,highest_points,ended_at FROM season_history ORDER BY season DESC")
        return [dict(season=r[0], highest_rank=r[1], highest_points=r[2], ended_at=r[3]) for r in rows]

    def mythic_season_count(self):
        """Count how many seasons the player reached Mythic rank."""
        row = self.db.execute(
            "SELECT COUNT(*) FROM season_history WHERE highest_rank LIKE 'Mythic%'").fetchone()
        return row[0] if row else 0

    def legendary_season_count(self):
        """Count how many seasons the player reached at least Legendary rank."""
        row = self.db.execute(
            "SELECT COUNT(*) FROM season_history WHERE highest_rank LIKE 'Legendary%' OR highest_rank LIKE 'Mythic%'").fetchone()
        return row[0] if row else 0

    def highest_rank_ever(self):
        """Return the highest rank tier and points ever achieved across all seasons."""
        current = self.rank()
        row = self.db.execute(
            "SELECT highest_rank,highest_points FROM season_history ORDER BY highest_points DESC LIMIT 1").fetchone()
        if row and row[1] > current["points"]:
            return dict(tier=row[0], points=row[1])
        return dict(tier=current["tier"], points=current["points"])

    def crate_count(self):
        return self._profile_int("crates")

    def unlocked_weapon_ids(self):
        unlocked = {row[0] for row in self.db.execute("SELECT weapon_id FROM weapon_unlocks")}
        return {w["id"] for w in weapon_list()
                if not w.get("locked_by_default") and w["id"] not in LEVEL_WEAPON_REWARDS.values()} | unlocked

    def unlock_weapon(self, weapon_id):
        if weapon_id not in weapons():
            return False
        self.db.execute("INSERT OR IGNORE INTO weapon_unlocks(weapon_id) VALUES(?)", (weapon_id,))
        self._commit()
        return True

    def add_skin(self, weapon_id, rarity, name=None):
        spec = weapons().get(weapon_id)
        if spec is None:
            raise ValueError(f"Unknown weapon id: {weapon_id}")
        skin_id = uuid.uuid4().hex
        name = name or random_skin_name(spec["name"], rarity)
        kill_effect = int(rarity == "LEGENDARY")
        self.db.execute("INSERT INTO owned_skins(id,weapon_id,name,rarity,kill_effect) VALUES(?,?,?,?,?)",
                        (skin_id, weapon_id, name, rarity, kill_effect))
        self._commit()
        return dict(id=skin_id, weapon_id=weapon_id, weapon_name=spec["name"], name=name,
                    rarity=rarity, kill_effect=bool(kill_effect),
                    effect_id=legendary_skin_effect(name, skin_id) if kill_effect else None)

    def open_crate(self, rng=None):
        if self.crate_count() <= 0:
            return None
        rng = rng or random.SystemRandom()
        rarity = rng.choices([r for r, _ in CRATE_RARITY_WEIGHTS],
                             weights=[weight for _, weight in CRATE_RARITY_WEIGHTS], k=1)[0]
        crate_frames = [frame for frame in AVATAR_FRAMES
                        if frame["source"] == "CRATE" and frame["rarity"] == rarity
                        and frame["id"] not in self.unlocked_avatar_frames()]
        if crate_frames and rng.random() < 0.2:
            frame = rng.choice(crate_frames)
            self.db.execute("INSERT INTO avatar_frame_unlocks(frame_id) VALUES(?)", (frame["id"],))
            self._set_profile_int("crates", self.crate_count() - 1)
            self._commit()
            return dict(type="AVATAR_FRAME", frame_id=frame["id"], name=frame["name"], rarity=frame["rarity"],
                        kill_effect=False)
        available = self.unlocked_weapon_ids()
        spec = rng.choice([w for w in weapon_list() if w["id"] in available])
        design = rng.choice([skin for skin in SKIN_DESIGNS if skin["rarity"] == rarity])
        self._set_profile_int("crates", self.crate_count() - 1)
        name = (legendary_skin_name(spec["name"], design["name"]) if rarity == "LEGENDARY"
                else f"{design['name']} {spec['name']}")
        reward = self.add_skin(spec["id"], rarity, name)
        reward["design_id"] = design["id"]
        self._commit()
        return reward

    def skins(self):
        out = []
        for skin_id, weapon_id, name, rarity, kill_effect in self.db.execute(
                "SELECT id,weapon_id,name,rarity,kill_effect FROM owned_skins ORDER BY id"):
            out.append(dict(id=skin_id, weapon_id=weapon_id, weapon_name=weapons()[weapon_id]["name"], name=name,
                            rarity=rarity, kill_effect=bool(kill_effect),
                            effect_id=legendary_skin_effect(name, skin_id) if kill_effect else None))
        return out

    def equip_skin(self, skin_id):
        row = self.db.execute("SELECT weapon_id FROM owned_skins WHERE id=?", (skin_id,)).fetchone()
        if row is None:
            return False
        self.db.execute("INSERT INTO equipped_skins(weapon_id,skin_id) VALUES(?,?) "
                        "ON CONFLICT(weapon_id) DO UPDATE SET skin_id=excluded.skin_id", (row[0], skin_id))
        self._commit()
        return True

    def unequip_skin(self, weapon_id):
        if weapon_id not in weapons():
            return False
        self.db.execute("DELETE FROM equipped_skins WHERE weapon_id=?", (weapon_id,))
        self._commit()
        return True

    def skins_for_weapon(self, weapon_id):
        if weapon_id not in weapons():
            return []
        return [skin for skin in self.skins() if skin["weapon_id"] == weapon_id]

    def equipped_skin_ids(self):
        return {weapon_id: skin_id for weapon_id, skin_id in
                self.db.execute("SELECT weapon_id,skin_id FROM equipped_skins")}

    def equipped_skins(self):
        out = {}
        rows = self.db.execute(
            "SELECT e.weapon_id,s.id,s.name,s.rarity,s.kill_effect FROM equipped_skins e "
            "JOIN owned_skins s ON s.id=e.skin_id")
        for weapon_id, skin_id, name, rarity, kill_effect in rows:
            out[weapon_id] = dict(id=skin_id, name=name, rarity=rarity, kill_effect=bool(kill_effect),
                                  effect_id=legendary_skin_effect(name, skin_id) if kill_effect else None)
        return out

    def kill_effect_weapon_ids(self):
        effects = legendary_weapon_ids()
        effects.update(row[0] for row in self.db.execute(
            "SELECT weapon_id FROM equipped_skins WHERE skin_id IN "
            "(SELECT id FROM owned_skins WHERE kill_effect=1)"))
        return effects

    def grant_legendary_armory(self):
        ids = legendary_weapon_ids()
        for weapon_id in ids:
            self.unlock_weapon(weapon_id)
            skin_name = f"Admin Issue {weapons()[weapon_id]['name']}"
            exists = self.db.execute(
                "SELECT 1 FROM owned_skins WHERE weapon_id=? AND rarity='LEGENDARY' AND name=? LIMIT 1",
                (weapon_id, skin_name)).fetchone()
            if exists is None:
                self.add_skin(weapon_id, "LEGENDARY", skin_name)
        self._commit()
        return sorted(ids)

    def unlock_all_weapons(self):
        ids = sorted(w["id"] for w in weapon_list())
        self.db.executemany("INSERT OR IGNORE INTO weapon_unlocks(weapon_id) VALUES(?)", ((weapon_id,) for weapon_id in ids))
        self._commit()
        return ids

    def record_match(self, mode, map_id, difficulty, won, stats: Dict, ranked=False, draw=False) -> int:
        previous_xp = self.db.execute("SELECT COALESCE(SUM(xp),0) FROM matches").fetchone()[0]
        xp = stats["kills"] * 10 + stats["headshots"] * 5 + 25 + (100 if won else 0)
        coins_awarded = 50 + stats["kills"] * 5 + (50 if won else 0)
        self.db.execute("INSERT INTO matches(ts,mode,map,difficulty,won,kills,deaths,shots,hits,headshots,xp) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (time.time(), mode, map_id, difficulty, int(won), stats["kills"], stats["deaths"], stats["shots"],
                         stats["hits"], stats["headshots"], xp))
        for w, n in stats["weapon_kills"].items():
            self.db.execute("INSERT INTO weapon_kills(weapon,kills) VALUES(?,?) ON CONFLICT(weapon) DO UPDATE SET kills=kills+?", (w, n, n))
        new_xp = previous_xp + xp
        self._set_profile_int("coins", self.coins() + coins_awarded)
        for level in range(level_for(previous_xp) + 1, level_for(new_xp) + 1):
            if level % CRATE_LEVEL_INTERVAL == 0:
                self._set_profile_int("crates", self.crate_count() + 1)
            weapon_id = LEVEL_WEAPON_REWARDS.get(level)
            if weapon_id:
                self.db.execute("INSERT OR IGNORE INTO weapon_unlocks(weapon_id) VALUES(?)", (weapon_id,))
        rank_points = self._profile_int("rank_points")
        if ranked and not draw:
            rank_points += RANKED_WIN_POINTS if won else -RANKED_LOSS_POINTS
            self._set_profile_int("rank_points", max(0, rank_points))
        self._commit()
        return xp

    def leaderboard(self, limit=10):
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("Leaderboard limit must be a positive integer")
        rows = self.db.execute(
            "SELECT id,ts,mode,map,difficulty,won,kills,deaths,headshots FROM matches "
            "ORDER BY kills DESC, headshots DESC, won DESC, ts ASC LIMIT ?", (limit,))
        return [dict(id=row[0], timestamp=row[1], mode=row[2], map=row[3], difficulty=row[4],
                     won=bool(row[5]), kills=row[6], deaths=row[7], headshots=row[8]) for row in rows]

    def update_bot_world(self, dt=0.0):
        if not hasattr(self, "_bot_world"):
            names = ["Peter Griffin", "Gojo Satoru", "Nino Nakano", "Miku Nakano", "Yotsuba Nakano",
                     "Ichika Nakano", "Itsuki Nakano", "Fuutarou Uesugi", "Anya Forger", "Shrek Main",
                     "Rizzler", "Nah Id Win", "Toji Tax Collector", "Amongus ඞ", "Goku WiFi",
                     "Megumin", "Kono Dio Da", "Domain Expansion", "Sukuna Finger", "Batman No Prep",
                     "Lo Nova", "Ghost Reaper", "Vex Pilot", "Raven Ace", "Echo Wolf", "Frost Zero",
                     "Solar Striker", "Phantom Scout", "Rift Fox", "Ember Knight", "Taco Bell Titan",
                     "Sigma Sloth", "Kirito Offline", "Luffy Tax Evasion", "Pikachu.exe", "Walter White",
                     "Speedwagon GOAT", "Bocchi The Rock", "Levi Ackerman", "Saitama OneTap", "Doraemon OP",
                     "Mr Worldwide", "Certified NPC", "WiFi Samurai", "Unpaid Intern", "Critical Hitman", "Lo Bot",
                     "Potato Aim", "Lagging Legend", "Sleepy Sniper", "NoScope Grandma", "Keyboard Cat"]
            rng = random.Random()
            rng.shuffle(names)
            while len(names) < 99:
                base = rng.choice(names)
                candidate = f"{base} {rng.randint(2, 999)}"
                if candidate not in names:
                    names.append(candidate)
            self._bot_world = []
            for name in names[:99]:
                points = rng.randint(0, 3200)
                self._bot_world.append(dict(name=name, points=points, wins=0, losses=0, streak=0,
                                            best=0, next_match=rng.uniform(0.5, 8.0), rng_seed=rng.randint(1, 999999)))
            self._bot_world_rng = rng
            self._bot_world_clock = 0.0
        self._bot_world_clock += dt
        rng = self._bot_world_rng
        for bot in self._bot_world:
            bot["next_match"] -= dt
            if bot["next_match"] <= 0:
                won = rng.random() < max(0.28, min(0.72, 0.5 + (bot["points"] - 1600) / 9000))
                if won:
                    bot["wins"] += 1
                    bot["streak"] = bot["streak"] + 1 if bot["streak"] > 0 else 1
                    bot["points"] += rng.randint(12, 34)
                else:
                    bot["losses"] += 1
                    bot["streak"] = bot["streak"] - 1 if bot["streak"] < 0 else -1
                    bot["points"] -= rng.randint(8, 27)
                bot["best"] = max(bot["best"], bot["streak"])
                bot["points"] = max(0, min(4200, bot["points"]))
                bot["next_match"] = rng.uniform(2.0, 12.0)

    def ranked_leaderboard(self, limit=100):
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("Leaderboard limit must be a positive integer")
        self.update_bot_world(0)
        player_results = [bool(row[0]) for row in self.db.execute("SELECT won FROM matches ORDER BY ts DESC, id DESC").fetchall()]
        player_wins = sum(1 for result in player_results if result)
        player_losses = len(player_results) - player_wins
        player_streak = 0
        if player_results:
            current_result = player_results[0]
            for result in player_results:
                if result != current_result:
                    break
                player_streak += 1 if result else -1
        entries = [dict(name=self.player_name(), points=self._profile_int("rank_points"), is_player=True,
                        streak=player_streak, wins=player_wins, losses=player_losses)]
        for bot in self._bot_world:
            entries.append(dict(name=bot["name"], points=bot["points"], is_player=False,
                                streak=bot["streak"], wins=bot["wins"], losses=bot["losses"]))
        entries.sort(key=lambda entry: (-entry["points"], not entry["is_player"], entry["name"].casefold()))
        return [dict(position=position, name=entry["name"], points=entry["points"],
                     tier=rank_for_points(entry["points"])["tier"], is_player=entry["is_player"],
                     streak=entry["streak"], wins=entry["wins"], losses=entry["losses"])
                for position, entry in enumerate(entries[:limit], start=1)]

    def summary(self) -> Dict:
        q = self.db.execute("SELECT COUNT(*),COALESCE(SUM(won),0),COALESCE(SUM(kills),0),COALESCE(SUM(deaths),0),"
                            "COALESCE(SUM(shots),0),COALESCE(SUM(hits),0),COALESCE(SUM(headshots),0),COALESCE(SUM(xp),0) FROM matches").fetchone()
        n, wins, k, d, shots, hits, hs, xp = q
        fav = self.db.execute("SELECT weapon FROM weapon_kills ORDER BY kills DESC LIMIT 1").fetchone()
        modes = {r[0]: (r[1], r[2], r[3]) for r in self.db.execute("SELECT mode,COUNT(*),SUM(won),SUM(kills) FROM matches GROUP BY mode")}
        return dict(matches=n, wins=wins, losses=n - wins, kills=k, deaths=d, kd=k / d if d else float(k),
                    accuracy=hits / shots if shots else 0.0, headshots=hs, xp=xp, level=level_for(xp),
                    favorite=fav[0] if fav else "-", modes=modes, rank=self.rank(),
                    rank_points=self.rank()["points"],
                    mythic_seasons=self.mythic_season_count(),
                    legendary_seasons=self.legendary_season_count(),
                    highest_rank_ever=self.highest_rank_ever(),
                    season_history=self.season_history(),
                    crates=self.crate_count(), coins=self.coins(), unlocked_weapons=self.unlocked_weapon_ids())
