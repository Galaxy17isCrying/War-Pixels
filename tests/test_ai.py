import math
import unittest

from tests import helpers  # noqa: F401
from src.gamemap import load_map
from src.match import Match
from src.pathfinding import find_path
from src.vision import can_see
from tests.helpers import place, quiet_match


class Pathfinding(unittest.TestCase):
    def test_paths_avoid_walls(self):
        for mid in ("depot_09", "blacksite", "frontier"):
            gm = load_map(mid)
            p = find_path(gm, gm.spawns[0][0], gm.spawns[1][0])
            self.assertIsNotNone(p)
            prev = gm.spawns[0][0]
            for node in p:
                self.assertFalse(gm.solid_at(*node))
                self.assertLess(math.hypot(node[0] - prev[0], node[1] - prev[1]), 64)
                prev = node

    def test_unreachable_snaps_or_none(self):
        gm = load_map("depot_09")
        self.assertIsNotNone(find_path(gm, gm.spawns[0][0], (1.0, 1.0)))


class Perception(unittest.TestCase):
    def test_bots_prioritize_visible_objective_carrier(self):
        m = quiet_match()
        bot = next(c for c in m.combatants if c.team == 0 and c.brain)
        nearby = next(c for c in m.combatants if c.team == 1)
        carrier = next(c for c in m.combatants if c.team == 1 and c is not nearby)
        place(m, bot, 16, 3)
        place(m, nearby, 20, 3)
        place(m, carrier, 22, 3)
        carrier.carry = object()
        bot.brain.visible = [nearby, carrier]
        bot.brain._select_target(0)
        self.assertIs(bot.brain.target, carrier)

    def test_no_seeing_through_walls_or_behind(self):
        m = quiet_match()
        a, b = m.combatants[0], m.combatants[10]
        a.team, b.team = 0, 1
        place(m, a, 13, 3)
        place(m, b, 15, 3)
        a.aim = 0.0
        self.assertFalse(can_see(m, a, b, 640))
        place(m, a, 16, 3)
        place(m, b, 20, 3)
        a.aim = 0.0
        self.assertTrue(can_see(m, a, b, 640))
        a.aim = math.pi
        self.assertFalse(can_see(m, a, b, 640))
        a.aim = 0.0
        b.cloak_t = 5.0
        self.assertFalse(can_see(m, a, b, 640))

    def test_elite_not_omniscient(self):
        m = Match("depot_09", "ctf", "ELITE", seed=2)
        for c in m.combatants:
            if c.brain:
                c.brain.visible = []
        m._update_vision()
        far = [c for c in m.combatants if c.team == 0 and c.brain is None][0]
        for e in m.combatants:
            if e.team == 1:
                self.assertFalse(m.is_visible_to(0, e) and not can_see(m, far, e, 700) and not any(
                    can_see(m, a, e, 700) for a in m.combatants if a.team == 0))


class Simulation(unittest.TestCase):
    def _run(self, map_id, mode, diff, secs):
        m = Match(map_id, mode, diff, seed=4, all_bots=True)
        for _ in range(60 * secs):
            m.update(1 / 60)
        return m

    def test_all_modes_run_stably(self):
        for mode in ("ctf", "snd", "hardpoint"):
            m = self._run("dustline", mode, "HARD", 45)
            self.assertLess(len(m.bullets), 400)
            self.assertLess(len(m.fx), 600)
            self.assertGreater(sum(c.stats["kills"] for c in m.combatants), 3)
            for c in m.combatants:
                if c.alive:
                    self.assertFalse(m.map.blocked(c.x, c.y, 10), f"{c.name} inside wall")

    def test_bots_do_not_get_permanently_stuck(self):
        m = self._run("blacksite", "hardpoint", "NORMAL", 90)
        self.assertLess(m.stuck_events, 40)

    def test_all_difficulties_run(self):
        for d in ("EASY", "NORMAL", "HARD", "ELITE"):
            self._run("depot_09", "hardpoint", d, 10)

    def test_difficulty_changes_behavior(self):
        from src.difficulty import DIFFICULTIES as D
        self.assertGreater(D["EASY"]["reaction"], D["ELITE"]["reaction"])
        self.assertGreater(D["EASY"]["aim_err"], D["ELITE"]["aim_err"])
        self.assertLess(D["EASY"]["ability"], D["ELITE"]["ability"])
        self.assertLess(D["EASY"]["tactics"], D["ELITE"]["tactics"])
        self.assertGreater(D["EASY"]["aim_err"], 10.0)
        self.assertGreater(D["NORMAL"]["aim_err"], 5.0)
        self.assertGreater(D["HARD"]["aim_err"], 2.6)
        self.assertGreater(D["ELITE"]["aim_err"], 1.2)
        self.assertGreater(D["EASY"]["aim_tolerance"], D["ELITE"]["aim_tolerance"])
        self.assertLess(D["NORMAL"]["lead"], 0.3)
        self.assertLess(D["NORMAL"]["aim_err"], D["EASY"]["aim_err"])
        self.assertGreater(D["NORMAL"]["tactics"], 0.5)
        self.assertGreater(D["NORMAL"]["cover"], 0.4)

    def test_normal_bots_wait_for_a_closer_aim_before_firing(self):
        m = Match("depot_09", "ctf", "NORMAL", seed=1, all_bots=True)
        bot = next(c for c in m.combatants if c.brain is not None)
        bot.alive = True
        bot.brain.react_t = 0.0
        bot.aim_dist = 100
        bot.trigger = False
        bot.brain._maybe_fire(math.radians(20))
        self.assertFalse(bot.trigger)
        bot.brain._maybe_fire(math.radians(15))
        self.assertTrue(bot.trigger)

    def test_snd_full_match_finishes(self):
        m = Match("depot_09", "snd", "NORMAL", seed=6, all_bots=True)
        for _ in range(60 * 600):
            m.update(1 / 60)
            if m.mode.over:
                break
        self.assertTrue(m.mode.over)

    def test_team_sizes(self):
        m = Match("depot_09", "ctf", "NORMAL", seed=1)
        self.assertEqual(sum(c.team == 0 for c in m.combatants), 10)
        self.assertEqual(sum(c.team == 1 for c in m.combatants), 10)
        self.assertEqual(sum(not c.is_bot for c in m.combatants), 1)


if __name__ == "__main__":
    unittest.main()
