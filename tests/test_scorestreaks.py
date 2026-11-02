import tempfile
import unittest
from pathlib import Path

from src.save import StatsDB
from src.scorestreaks import SCORESTREAKS, STREAK_SKINS


class ScorestreakProgressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = StatsDB(Path(self.temp.name) / "stats.db")

    def tearDown(self):
        self.db.db.close()
        self.temp.cleanup()

    def test_level_one_streaks_are_available(self):
        owned = self.db.unlocked_scorestreak_ids()
        self.assertIn("uav", owned)
        self.assertIn("shield_turret", owned)
        self.assertIn("gunship", owned)
        self.assertNotIn("bomb_drone", owned)

    def test_store_purchase_requires_level_and_credits(self):
        result = self.db.buy_scorestreak("bomb_drone")
        self.assertEqual(result["status"], "level_locked")
        self.db.grant_coins(5000)
        for _ in range(5):
            self.db.record_match("tdm", "depot_09", "NORMAL", True,
                                 dict(kills=10, headshots=0, deaths=0, shots=0, hits=0, weapon_kills={}))
        result = self.db.buy_scorestreak("bomb_drone")
        self.assertEqual(result["status"], "purchased")
        self.assertIn("bomb_drone", self.db.unlocked_scorestreak_ids())

    def test_store_purchase_checks_credits(self):
        self.db.db.execute("INSERT INTO matches(ts,mode,map,difficulty,won,kills,deaths,shots,hits,headshots,xp) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                           (1, "tdm", "depot_09", "NORMAL", 1, 0, 0, 0, 0, 0, 500))
        self.db.db.commit()
        result = self.db.buy_scorestreak("bomb_drone")
        self.assertEqual(result["status"], "insufficient_coins")

    def test_scorestreak_skin_purchase_and_equipping(self):
        self.db.grant_coins(1000)
        result = self.db.buy_scorestreak_skin("uav", STREAK_SKINS[0]["id"])
        self.assertEqual(result["status"], "purchased")
        self.assertEqual(self.db.equipped_scorestreak_skin("uav"), "neon")
        self.assertEqual(self.db.owned_scorestreak_skins("uav")[0]["id"], "neon")

    def test_all_requested_streaks_have_definitions(self):
        names = {item["name"] for item in SCORESTREAKS}
        for name in ("UAV", "Bomb Drone", "Shock RC", "Care Package", "Counter-UAV",
                     "Predator Missile", "Sentry Gun", "Stealth Chopper", "Swarm", "VTOL",
                     "The Gunship", "Strafe Run"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
