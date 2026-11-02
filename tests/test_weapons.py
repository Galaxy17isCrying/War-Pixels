import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests import helpers  # noqa: F401
from src.config import CATEGORY_ORDER, weapon_list
from src.weapons import RELOAD_TIME_MULTIPLIER, WeaponState, aim_assist_angle, damage_at_range

REQUIRED = ["dmg", "hs", "limb", "rate", "mag", "reserve", "reload", "speed", "range", "falloff", "hip", "aim", "vrec",
            "hrec", "recover", "movepen", "swap", "auto", "pellets", "move"]


class WeaponData(unittest.TestCase):
    def test_selected_weapon_buffs(self):
        by_id = {w["id"]: w for w in weapon_list()}
        self.assertEqual(by_id["falcon"]["dmg"], 40)
        self.assertEqual(by_id["reaper"]["dmg"], 22)
        self.assertEqual(by_id["wasp"]["dmg"], 15)
        self.assertEqual(by_id["scatter"]["dmg"], 9)

    def test_counts_and_fields(self):
        ws = weapon_list()
        prim = [w for w in ws if w["cat"] != "PISTOL"]
        self.assertGreaterEqual(len(prim), 18)
        for cat in CATEGORY_ORDER:
            self.assertGreaterEqual(sum(w["cat"] == cat for w in ws), 3, cat)
        self.assertGreaterEqual(sum(w["cat"] == "PISTOL" for w in ws), 3)
        for w in ws:
            for k in REQUIRED:
                self.assertIn(k, w, f"{w['id']} missing {k}")

    def test_category_identities(self):
        by = {}
        for w in weapon_list():
            by.setdefault(w["cat"], []).append(w)
        avg = lambda c, k: sum(w[k] for w in by[c]) / len(by[c])
        self.assertGreater(avg("SNIPER", "dmg"), avg("AR", "dmg") * 2.5)
        self.assertLess(avg("SNIPER", "rate"), avg("AR", "rate") / 5)
        self.assertGreater(avg("SMG", "rate"), avg("AR", "rate"))
        self.assertGreater(avg("LMG", "mag"), avg("AR", "mag") * 2)
        self.assertTrue(all(w["pellets"] > 1 for w in by["SG"]))
        self.assertTrue(all(w["falloff"] < 0.2 for w in by["SG"]))
        self.assertTrue(all(not w["auto"] for w in by["MARKSMAN"]))
        self.assertTrue(all(90 <= w["dmg"] <= 100 for w in by["SNIPER"]))

    def test_falloff(self):
        w = next(w for w in weapon_list() if w["id"] == "vanguard")
        self.assertEqual(damage_at_range(w, 10), w["dmg"])
        self.assertLess(damage_at_range(w, w["range"]), w["dmg"])
        self.assertAlmostEqual(damage_at_range(w, w["range"]), w["dmg"] * w["falloff"])


class Recoil(unittest.TestCase):
    def test_player_recoil_scale_is_reduced_for_both_equipped_weapons(self):
        from src.entities import Combatant

        player = Combatant(0, "PLAYER", 0, "vanguard", "vanguard", "p9", is_bot=False)
        bot = Combatant(1, "BOT", 1, "vanguard", "vanguard", "p9", is_bot=True)
        self.assertTrue(all(weapon.recoil_scale == 0.55 for weapon in player.weapons))
        self.assertTrue(all(weapon.recoil_scale == 1.0 for weapon in bot.weapons))

        rng = random.Random(7)
        player_weapon, bot_weapon = player.weapons[0], bot.weapons[0]
        for _ in range(5):
            player_weapon.fire(rng, False, 0)
            bot_weapon.fire(rng, False, 0)
            player_weapon.cooldown = bot_weapon.cooldown = 0
        self.assertLess(player_weapon.bloom, bot_weapon.bloom)

    def test_bloom_grows_and_recovers(self):
        spec = next(w for w in weapon_list() if w["id"] == "vanguard")
        w, rng = WeaponState(spec), random.Random(1)
        start = w.spread(False, 0)
        for _ in range(12):
            self.assertIsNotNone(w.fire(rng, False, 0))
            w.cooldown = 0
        self.assertGreater(w.spread(False, 0), start + 5)
        for _ in range(120):
            w.update(1 / 60)
        self.assertAlmostEqual(w.spread(False, 0), start)

    def test_ads_and_steady_tighten(self):
        spec = next(w for w in weapon_list() if w["id"] == "vanguard")
        w = WeaponState(spec)
        self.assertLess(w.spread(True, 0), w.spread(False, 0))
        self.assertLess(w.spread(False, 0, steady=True), w.spread(True, 0))
        self.assertGreater(w.spread(False, 1.0), w.spread(False, 0))

    def test_reload_and_ammo(self):
        spec = next(w for w in weapon_list() if w["id"] == "p9")
        w, rng = WeaponState(spec), random.Random(1)
        for _ in range(spec["mag"]):
            w.fire(rng, False, 0)
            w.cooldown = 0
        self.assertEqual(w.mag, 0)
        self.assertIsNone(w.fire(rng, False, 0))
        self.assertTrue(w.start_reload())
        self.assertAlmostEqual(w.reload_t, spec["reload"] * RELOAD_TIME_MULTIPLIER)
        self.assertEqual(w.reload_progress, 0)
        w.update(0.5)
        self.assertGreater(w.reload_progress, 0)
        for _ in range(int(spec["reload"] * 60) + 5):
            w.update(1 / 60)
        self.assertEqual(w.mag, spec["mag"])
        self.assertEqual(w.reserve, spec["reserve"] - spec["mag"])

    def test_shotgun_pellets(self):
        spec = next(w for w in weapon_list() if w["id"] == "breaker")
        offs = WeaponState(spec).fire(random.Random(2), False, 0)
        if offs is None:
            self.fail("Shotgun should be ready to fire")
        self.assertEqual(len(offs), spec["pellets"])

    def test_unlimited_ammo_does_not_consume_magazine(self):
        spec = next(w for w in weapon_list() if w["id"] == "p9")
        w = WeaponState(spec)
        w.unlimited = True
        for _ in range(spec["mag"] + 1):
            self.assertIsNotNone(w.fire(random.Random(1), False, 0))
            w.cooldown = 0
        self.assertEqual(w.mag, spec["mag"])


class AimAssist(unittest.TestCase):
    def test_mild_assist_nudges_toward_nearby_target(self):
        from types import SimpleNamespace

        angle = aim_assist_angle(0.0, (0, 0), [SimpleNamespace(x=100, y=10)], .2, .2, 200)
        self.assertGreater(angle, 0.0)
        self.assertLess(angle, math.atan2(10, 100))

    def test_assist_does_not_pull_targets_outside_cone_or_range(self):
        from types import SimpleNamespace

        self.assertEqual(aim_assist_angle(0.0, (0, 0), [SimpleNamespace(x=100, y=50)], .1, .2, 200), 0.0)
        self.assertEqual(aim_assist_angle(0.0, (0, 0), [SimpleNamespace(x=300, y=0)], .2, .2, 200), 0.0)


if __name__ == "__main__":
    unittest.main()
