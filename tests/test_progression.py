import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.config import weapon_list
from src.progression import (AVATAR_FRAMES, CALLING_CARDS, FIREARM_CATEGORIES, SKIN_DESIGNS, SKIN_RARITY_COUNTS,
                             legendary_weapon_ids, LEGENDARY_SKIN_EFFECTS, RANK_TIERS, STORE_SKIN_PRICES,
                             legendary_skin_effect, rank_for_points, weapon_rarity)
from src.save import StatsDB


class RankedProgression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = StatsDB(Path(self.temp.name) / "stats.db")
        self.extra_dbs = []

    def tearDown(self):
        for db in self.extra_dbs:
            db.db.close()
        self.db.db.close()
        self.temp.cleanup()

    @staticmethod
    def stats(kills=0):
        return dict(kills=kills, headshots=0, deaths=0, shots=0, hits=0, weapon_kills={})

    def test_rank_tiers_and_ranked_results(self):
        self.assertEqual(rank_for_points(0)["tier"], "Bronze I")
        self.assertEqual(rank_for_points(900)["tier"], "Legendary")
        self.assertEqual(rank_for_points(1200)["tier"], "Mythic")
        self.assertEqual(rank_for_points(50)["tier"], "Bronze II")
        self.assertEqual(rank_for_points(1050)["tier"], "Legendary II")
        self.assertEqual(rank_for_points(2800)["tier"], "Mythic V")
        self.assertGreater(len(RANK_TIERS), 8)
        self.db.record_match("ctf", "depot_09", "NORMAL", True, self.stats(), ranked=True)
        self.assertEqual(self.db.rank()["points"], 25)
        self.db.record_match("ctf", "depot_09", "NORMAL", False, self.stats(), ranked=True)
        self.assertEqual(self.db.rank()["points"], 10)
        self.db.record_match("ctf", "depot_09", "NORMAL", False, self.stats(), ranked=True, draw=True)
        self.assertEqual(self.db.rank()["points"], 10)

    def test_admin_rank_points_set_rank_and_persist(self):
        rank = self.db.set_rank_points(2700)
        self.assertEqual(rank["tier"], "Mythic V")
        self.assertEqual(self.db.rank()["points"], 2700)
        with self.assertRaises(ValueError):
            self.db.set_rank_points(-1)

    def test_leaderboard_orders_best_match_scores_first(self):
        self.db.record_match("ctf", "depot_09", "NORMAL", False,
                             dict(kills=3, headshots=1, deaths=2, shots=20, hits=10, weapon_kills={}))
        self.db.record_match("hardpoint", "frontier", "ELITE", True,
                             dict(kills=8, headshots=2, deaths=4, shots=30, hits=20, weapon_kills={}))
        rows = self.db.leaderboard()
        self.assertEqual([row["kills"] for row in rows], [8, 3])
        self.assertEqual(rows[0]["mode"], "hardpoint")
        self.assertTrue(rows[0]["won"])
        with self.assertRaises(ValueError):
            self.db.leaderboard(0)

    def test_ranked_leaderboard_contains_player_and_99_stable_bots(self):
        self.db.set_player_name("Nova")
        self.db.record_match("ranked", "depot_09", "NORMAL", True, self.stats(), ranked=True)

        rows = self.db.ranked_leaderboard()
        player_rows = [row for row in rows if row["is_player"]]

        self.assertEqual(len(rows), 100)
        self.assertEqual(len(player_rows), 1)
        self.assertEqual(player_rows[0]["name"], "Nova")
        self.assertEqual(player_rows[0]["points"], 25)
        self.assertEqual([row["position"] for row in rows], list(range(1, 101)))
        self.assertEqual([row["points"] for row in rows],
                         sorted((row["points"] for row in rows), reverse=True))
        self.assertIn("Lo Bot", {row["name"] for row in rows})
        self.assertEqual(rows, self.db.ranked_leaderboard())
        with self.assertRaises(ValueError):
            self.db.ranked_leaderboard(0)

    def test_mysql_mirror_uploads_local_snapshot_when_enabled(self):
        connection = MagicMock()
        connection.is_connected.return_value = True
        connector = SimpleNamespace(Error=Exception, connect=MagicMock(return_value=connection))
        env = {
            "OVERHEAD_OPS_MYSQL_ENABLED": "1",
            "OVERHEAD_OPS_MYSQL_HOST": "127.0.0.1",
            "OVERHEAD_OPS_MYSQL_PORT": "3306",
            "OVERHEAD_OPS_MYSQL_DATABASE": "ops_test",
            "OVERHEAD_OPS_MYSQL_USER": "test_user",
            "OVERHEAD_OPS_MYSQL_PASSWORD": "test-only-secret",
        }
        with patch.dict(os.environ, env, clear=False), \
                patch("src.save.importlib.import_module", return_value=connector):
            db = StatsDB(Path(self.temp.name) / "mysql-mirror.db")
            self.extra_dbs.append(db)
            db.set_player_name("My Pilot")
            db.complete_campaign_mission(0)
            db.unlock_weapon("hawk")
            skin = db.add_skin("vanguard", "EPIC", "Test Skin")
            db.equip_skin(skin["id"])
            match_stats = self.stats(kills=4)
            match_stats["weapon_kills"] = {"vanguard": 4}
            db.record_match("ctf", "depot_09", "NORMAL", True, match_stats, ranked=True)

        connector.connect.assert_called_once_with(
            host="127.0.0.1", port=3306, user="test_user",
            password="test-only-secret", database="ops_test")
        cursor = connection.cursor.return_value.__enter__.return_value
        sql_statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any(statement.startswith("CREATE TABLE IF NOT EXISTS match_history")
                            for statement in sql_statements))
        inserts = {call.args[0] for call in cursor.executemany.call_args_list}
        for table in ("match_history", "weapon_kills", "weapon_unlocks", "owned_skins",
                      "equipped_skins", "avatar_frame_unlocks"):
            self.assertTrue(any(statement.startswith(f"INSERT INTO {table}") for statement in inserts), table)
        profile_writes = [call.args[1] for call in cursor.execute.call_args_list
                          if call.args[0].startswith("INSERT INTO player_profiles")]
        self.assertEqual(profile_writes[-1][2:4], (25, 1))
        self.assertGreaterEqual(connection.commit.call_count, 3)

    def test_level_rewards_grant_weapons_and_crates(self):
        self.db.record_match("ctf", "depot_09", "NORMAL", True, self.stats(kills=100))
        summary = self.db.summary()
        self.assertGreaterEqual(summary["level"], 5)
        self.assertEqual(summary["crates"], 1)
        self.assertIn("cyclone", summary["unlocked_weapons"])
        self.assertIn("rift", summary["unlocked_weapons"])

    def test_crates_and_legendary_skin_kill_effect(self):
        self.db.record_match("ctf", "depot_09", "NORMAL", True, self.stats(kills=100))
        reward = self.db.open_crate()
        self.assertIsNotNone(reward)
        self.assertEqual(self.db.crate_count(), 0)
        skin = self.db.add_skin("solstice", "LEGENDARY")
        self.assertTrue(skin["kill_effect"])
        self.assertTrue(self.db.equip_skin(skin["id"]))
        self.assertIn("solstice", self.db.kill_effect_weapon_ids())
        self.assertEqual(self.db.equipped_skins()["solstice"]["id"], skin["id"])

    def test_weapon_rarity(self):
        self.assertEqual(weapon_rarity({"id": "solstice", "rarity": "LEGENDARY"}), "LEGENDARY")
        self.assertEqual(weapon_rarity({"id": "vanguard"}), "COMMON")

    def test_profile_uid_is_generated_once_and_name_persists(self):
        path = Path(self.temp.name) / "profile.db"
        db = StatsDB(path)
        uid = db.player_uid()
        self.assertRegex(uid, r"^OPS-[A-F0-9]{10}$")
        self.assertTrue(db.set_player_name("  Nova   Pilot  "))
        self.assertEqual(db.player_name(), "Nova Pilot")
        db.db.close()
        reopened = StatsDB(path)
        self.assertEqual(reopened.player_uid(), uid)
        self.assertEqual(reopened.player_name(), "Nova Pilot")
        reopened.db.close()

    def test_legendary_and_full_weapon_unlocks_are_persistent_and_idempotent(self):
        legends = self.db.grant_legendary_armory()
        skin_count = len(self.db.skins())
        self.assertTrue(legends)
        self.assertEqual(self.db.grant_legendary_armory(), legends)
        self.assertEqual(len(self.db.skins()), skin_count)
        self.assertTrue(set(legends).issubset(self.db.unlocked_weapon_ids()))
        all_ids = self.db.unlock_all_weapons()
        self.assertEqual(set(all_ids), {weapon["id"] for weapon in weapon_list()})
        self.assertEqual(set(all_ids), self.db.unlocked_weapon_ids())

    def test_each_firearm_category_has_ten_additional_original_weapons(self):
        all_weapons = weapon_list()
        for category in FIREARM_CATEGORIES:
            with self.subTest(category=category):
                self.assertEqual(sum(weapon["cat"] == category for weapon in all_weapons),
                                 {"AR": 15, "SMG": 14, "LMG": 14, "SG": 13, "MARKSMAN": 14, "SNIPER": 14,
                                  "PISTOL": 14}[category])
                self.assertGreaterEqual(sum(weapon["cat"] == category and weapon_rarity(weapon) == "LEGENDARY"
                                            for weapon in all_weapons), 2)

    def test_m4_emberwyrm_is_free_legendary_with_dragon_effect(self):
        m4 = next(weapon for weapon in weapon_list() if weapon["id"] == "m4_emberwyrm")
        self.assertEqual(m4["name"], "M4 - EMBERWYRM")
        self.assertEqual(m4["cat"], "AR")
        self.assertEqual(weapon_rarity(m4), "LEGENDARY")
        self.assertEqual(m4["kill_effect"], "dragon")
        self.assertFalse(m4["locked_by_default"])
        self.assertIn("m4_emberwyrm", self.db.unlocked_weapon_ids())
        self.assertGreater(m4["aim_assist"], 0)

    def test_holger_galactic_stars_is_a_free_zero_recoil_lmg(self):
        holger = next(weapon for weapon in weapon_list() if weapon["id"] == "holger_galactic_stars")
        self.assertEqual(holger["name"], "HOLGER - GALACTIC STARS")
        self.assertEqual(holger["cat"], "LMG")
        self.assertEqual((holger["mag"], holger["reserve"]), (300, 1000))
        self.assertEqual((holger["hip"], holger["aim"], holger["vrec"], holger["hrec"], holger["movepen"]),
                         (0, 0, 0, 0, 0))
        self.assertGreaterEqual(holger["dmg"], 40)
        self.assertGreaterEqual(holger["rate"], 1000)
        self.assertEqual(holger["kill_effect"], "supernova")
        self.assertFalse(holger["locked_by_default"])
        self.assertIn(holger["id"], self.db.unlocked_weapon_ids())

    def test_store_skin_purchase_deducts_coins_once_and_auto_equips(self):
        design = next(item for item in SKIN_DESIGNS if item["rarity"] == "COMMON")
        price = STORE_SKIN_PRICES[design["rarity"]]
        self.db.grant_coins(price)
        purchase = self.db.buy_store_skin("vanguard", design["id"])
        self.assertEqual(purchase["status"], "purchased")
        self.assertEqual(self.db.coins(), 0)
        self.assertEqual(self.db.equipped_skins()["vanguard"]["id"], purchase["id"])
        duplicate = self.db.buy_store_skin("vanguard", design["id"])
        self.assertEqual(duplicate["status"], "already_owned")
        self.assertEqual(self.db.coins(), 0)
        other_design = next(item for item in SKIN_DESIGNS if item["id"] != design["id"])
        self.assertEqual(self.db.buy_store_skin("vanguard", other_design["id"])["status"], "insufficient_coins")

    def test_store_will_not_sell_skins_for_locked_weapons(self):
        locked = next(w for w in weapon_list() if w.get("locked_by_default"))
        self.assertEqual(self.db.buy_store_skin(locked["id"], SKIN_DESIGNS[0]["id"])["status"], "unavailable")

    def test_calling_card_purchase_equips_and_deducts_coins_once(self):
        card = next(item for item in CALLING_CARDS if item["source"] == "COINS")
        self.assertEqual(self.db.equipped_calling_card(), "frontline_veteran")
        self.assertEqual(self.db.buy_calling_card("frontline_veteran")["status"], "already_owned")
        self.assertEqual(self.db.buy_calling_card(card["id"])["status"], "insufficient_coins")
        self.db.grant_coins(card["price"])
        self.assertEqual(self.db.buy_calling_card(card["id"])["status"], "purchased")
        self.assertEqual(self.db.coins(), 0)
        self.assertEqual(self.db.equipped_calling_card(), card["id"])
        self.assertEqual(self.db.buy_calling_card(card["id"])["status"], "already_owned")
        self.assertEqual(self.db.coins(), 0)
        self.assertTrue(self.db.equip_calling_card("frontline_veteran"))
        self.assertEqual(self.db.equipped_calling_card(), "frontline_veteran")
        self.assertEqual(self.db.buy_calling_card("not_a_card")["status"], "unavailable")
        path = Path(self.temp.name) / "stats.db"
        self.db.db.close()
        self.db = StatsDB(path)
        self.assertIn(card["id"], self.db.owned_calling_card_ids())
        self.assertEqual(self.db.equipped_calling_card(), "frontline_veteran")

    def test_weapon_skin_selection_can_be_changed_or_cleared(self):
        first = self.db.add_skin("vanguard", "LEGENDARY", "Vanguard - Astral Sovereign")
        second = self.db.add_skin("vanguard", "EPIC", "Vanguard - Violet Circuit")
        self.assertEqual({skin["id"] for skin in self.db.skins_for_weapon("vanguard")},
                         {first["id"], second["id"]})
        self.assertTrue(self.db.equip_skin(first["id"]))
        self.assertEqual(self.db.equipped_skins()["vanguard"]["id"], first["id"])
        self.assertTrue(self.db.equip_skin(second["id"]))
        self.assertEqual(self.db.equipped_skins()["vanguard"]["id"], second["id"])
        self.assertTrue(self.db.unequip_skin("vanguard"))
        self.assertNotIn("vanguard", self.db.equipped_skins())

    def test_legendary_skins_and_ten_legendary_frames_are_store_items(self):
        legendary_designs = [design for design in SKIN_DESIGNS if design["rarity"] == "LEGENDARY"]
        legendary_frames = [frame for frame in AVATAR_FRAMES
                            if frame["rarity"] == "LEGENDARY" and frame["source"] == "COINS"]
        self.assertEqual(len(legendary_designs), 10)
        self.assertEqual(len({design["name"] for design in legendary_designs}), 10)
        self.assertEqual(len(legendary_frames), 10)
        self.assertEqual(len({frame["id"] for frame in legendary_frames}), 10)

        design = legendary_designs[0]
        self.db.grant_coins(STORE_SKIN_PRICES["LEGENDARY"])
        skin = self.db.buy_store_skin("vanguard", design["id"])
        self.assertEqual(skin["status"], "purchased")
        self.assertTrue(skin["kill_effect"])
        self.assertIn("vanguard", self.db.kill_effect_weapon_ids())

        frame = legendary_frames[0]
        self.db.grant_coins(frame["price"])
        self.assertTrue(self.db.buy_avatar_frame(frame["id"]))
        self.assertIn(frame["id"], self.db.unlocked_avatar_frames())

    def test_every_legendary_skin_has_its_own_effect_id(self):
        legendary = [design for design in SKIN_DESIGNS if design["rarity"] == "LEGENDARY"]
        effects = [design["kill_effect"] for design in legendary]
        self.assertEqual(len(legendary), 10)
        self.assertEqual(set(effects), set(LEGENDARY_SKIN_EFFECTS))
        self.assertIn(legendary_skin_effect("Admin Issue - Custom Legendary Gun"), LEGENDARY_SKIN_EFFECTS)
        skin_effect_ids = []
        for design in legendary:
            with self.subTest(design=design["name"]):
                skin = self.db.add_skin(
                    "vanguard", "LEGENDARY", f"AR-7 VANGUARD - {design['name'].upper()}")
                self.assertTrue(skin["effect_id"].startswith(f"{design['kill_effect']}__"))
                self.assertTrue(skin["kill_effect"])
                skin_effect_ids.append(skin["effect_id"])
        self.assertEqual(len(skin_effect_ids), len(set(skin_effect_ids)))
        stored_effect_ids = [skin["effect_id"] for skin in self.db.skins()]
        self.assertEqual(set(stored_effect_ids), set(skin_effect_ids))
        self.assertTrue(self.db.equip_skin(self.db.skins()[0]["id"]))
        equipped_effect = self.db.equipped_skins()["vanguard"]["effect_id"]
        self.assertIn(equipped_effect, skin_effect_ids)

    def test_one_hundred_skin_designs_have_requested_rarity_distribution(self):
        self.assertEqual(len(SKIN_DESIGNS), 100)
        self.assertEqual(len({skin["name"] for skin in SKIN_DESIGNS}), 100)
        self.assertEqual(len({skin["id"] for skin in SKIN_DESIGNS}), 100)
        for rarity, count in SKIN_RARITY_COUNTS:
            with self.subTest(rarity=rarity):
                self.assertEqual(sum(skin["rarity"] == rarity for skin in SKIN_DESIGNS), count)
        self.db.record_match("ctf", "depot_09", "NORMAL", True, self.stats(kills=100))
        class CommonSkinRoll:
            @staticmethod
            def choices(values, weights, k):
                return ["COMMON"]

            @staticmethod
            def random():
                return 1.0

            @staticmethod
            def choice(values):
                return values[0]

        reward = self.db.open_crate(CommonSkinRoll())
        self.assertIn(reward["rarity"], {rarity for rarity, _ in SKIN_RARITY_COUNTS})
        self.assertTrue(reward["name"])
        self.assertTrue(reward["design_id"])

    def test_each_weapon_can_receive_a_named_legendary_variant(self):
        from src.progression import legendary_skin_name

        for spec in weapon_list():
            with self.subTest(weapon=spec["id"]):
                variant = legendary_skin_name(spec["name"], "Ashen Bastion")
                self.assertIn(spec["name"], variant)
                self.assertTrue(variant.endswith("ASHEN BASTION"))

    def test_coin_rewards_and_premium_frame_unlocks(self):
        self.assertEqual(self.db.coins(), 0)
        self.db.record_match("ctf", "depot_09", "NORMAL", True, self.stats(kills=4))
        self.assertEqual(self.db.coins(), 120)
        premium = next(frame for frame in AVATAR_FRAMES if frame["source"] == "COINS")
        self.assertFalse(self.db.buy_avatar_frame(premium["id"]))
        self.db.grant_coins(1000)
        self.assertTrue(self.db.buy_avatar_frame(premium["id"]))
        self.assertIn(premium["id"], self.db.unlocked_avatar_frames())
        self.assertEqual(self.db.coins(), 1000 - premium["price"] + 120)

    def test_admin_frame_grant_and_crate_frame_reward(self):
        granted = self.db.grant_all_avatar_frames()
        self.assertEqual(set(granted), self.db.unlocked_avatar_frames())
        # A fresh profile is used to verify that crate-only frames can be earned.
        crate_db = StatsDB(Path(self.temp.name) / "crate-frames.db")
        crate_db.record_match("ctf", "depot_09", "NORMAL", True, self.stats(kills=100))

        class RareFrameRoll:
            @staticmethod
            def choices(values, weights, k):
                return ["RARE"]

            @staticmethod
            def random():
                return 0.0

            @staticmethod
            def choice(values):
                return values[0]

        reward = crate_db.open_crate(RareFrameRoll())
        self.assertEqual(reward["type"], "AVATAR_FRAME")
        self.assertIn(reward["frame_id"], crate_db.unlocked_avatar_frames())
        crate_db.db.close()


if __name__ == "__main__":
    unittest.main()
