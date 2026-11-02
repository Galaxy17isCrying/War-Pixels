import math
import unittest

from tests.helpers import place, quiet_match
from src.match import Match


def at(m, c, pos):
    c.x, c.y = pos
    c.alive = True


class CTF(unittest.TestCase):
    def test_capture_requires_home_flag(self):
        m = quiet_match(mode="ctf")
        mode = m.mode
        runner = m.combatants[1]
        runner.team = 0
        at(m, runner, mode.flags[1].home)
        mode.update(0.016)
        self.assertIs(runner.carry, mode.flags[1])
        thief = m.combatants[12]
        thief.team = 1
        at(m, thief, m.map.spawns[1][0])
        mode.flags[0].carrier, thief.carry, mode.flags[0].at_home = thief, mode.flags[0], False
        at(m, runner, mode.flags[0].home)
        mode.update(0.016)
        self.assertEqual(mode.scores, [0, 0])
        mode.send_home(mode.flags[0])
        mode.update(0.016)
        self.assertEqual(mode.scores, [1, 0])
        self.assertTrue(mode.flags[1].at_home)
        self.assertIsNone(runner.carry)

    def test_drop_and_recover(self):
        m = quiet_match(mode="ctf")
        mode = m.mode
        runner = m.combatants[1]
        runner.team = 0
        at(m, runner, mode.flags[1].home)
        mode.update(0.016)
        m.kill(runner, None, "p9", False)
        self.assertIsNone(mode.flags[1].carrier)
        self.assertFalse(mode.flags[1].at_home)
        runner2 = m.combatants[2]
        runner2.team = 1
        at(m, runner2, (mode.flags[1].x, mode.flags[1].y))
        mode.update(0.016)
        self.assertTrue(mode.flags[1].at_home)

    def test_score_limit_ends_match(self):
        m = quiet_match(mode="ctf")
        m.mode.scores[0] = m.mode.SCORE_LIMIT - 1
        runner = m.combatants[1]
        runner.team = 0
        at(m, runner, m.mode.flags[1].home)
        m.mode.update(0.016)
        at(m, runner, m.mode.flags[0].home)
        m.mode.update(0.016)
        self.assertTrue(m.mode.over)
        self.assertEqual(m.mode.winner, 0)

    def test_timer_ends_match(self):
        m = quiet_match(mode="ctf")
        m.mode.scores[1] = 1
        m.mode.time_left = 0.01
        m.mode.update(0.1)
        self.assertEqual(m.mode.winner, 1)


class SearchDestroy(unittest.TestCase):
    def setUp(self):
        self.m = quiet_match(mode="snd")
        self.mode = self.m.mode
        self.mode.t = 0
        self.mode.update(0.1)
        self.assertEqual(self.mode.state, "live")
        for c in self.m.combatants:
            c.alive = False
        att = [c for c in self.m.combatants if c.team == self.mode.attackers]
        dfn = [c for c in self.m.combatants if c.team != self.mode.attackers]
        self.att, self.dfn = att[0], dfn[0]
        self.att2, self.dfn2 = att[1], dfn[1]
        for c in (self.att, self.att2, self.dfn, self.dfn2):
            c.alive = True
        self.site = self.m.map.sites[0]
        self.dfn.x, self.dfn.y = self.m.map.spawns[1][0]
        self.dfn2.x, self.dfn2.y = self.m.map.spawns[1][1]

    def plant(self):
        self.att.x, self.att.y = self.site
        self.att.interact = True
        for _ in range(int((self.mode.PLANT + 0.5) * 60)):
            self.mode.update(1 / 60)

    def test_plant_and_detonate(self):
        self.plant()
        self.assertIsNotNone(self.mode.bomb)
        self.att.interact = False
        self.m.mode.bomb["timer"] = 0.05
        self.mode.update(0.1)
        self.assertEqual(self.mode.state, "ended")
        self.assertEqual(self.mode.scores[self.mode.attackers], 1)

    def test_defuse(self):
        self.plant()
        self.att.interact = False
        self.dfn.x, self.dfn.y = self.site
        self.dfn.interact = True
        for _ in range(int((self.mode.DEFUSE + 0.5) * 60)):
            self.mode.update(1 / 60)
        self.assertEqual(self.mode.scores[1 - self.mode.attackers], 1)

    def test_elimination_and_timeout(self):
        self.att.alive = self.att2.alive = False
        self.mode.update(0.1)
        self.assertEqual(self.mode.scores[1 - self.mode.attackers], 1)

    def test_timeout_favors_defenders(self):
        self.mode.time_left = 0.01
        self.mode.update(0.1)
        self.assertEqual(self.mode.scores[1 - self.mode.attackers], 1)

    def test_sides_switch_and_match_ends(self):
        first = self.mode.attackers
        for r in range(3):
            self.mode.end_round(first, "t")
            self.mode.t = 0
            self.mode.update(0.1)
            if self.mode.over:
                break
            self.mode.t = 0
            self.mode.update(0.1)
            self.mode.state = "live"
        self.assertNotEqual(self.mode.attackers, first)
        self.mode.scores[0] = self.mode.ROUNDS_TO_WIN - 1
        self.mode.state = "live"
        self.mode.end_round(0, "t")
        self.mode.t = 0
        self.mode.update(0.1)
        self.assertTrue(self.mode.over)
        self.assertEqual(self.mode.winner, 0)


class Hardpoint(unittest.TestCase):
    def test_objectives_are_randomized_across_the_map(self):
        first = quiet_match(mode="hardpoint")
        second = quiet_match(mode="hardpoint")
        first_zones = first.mode.order
        second_zones = second.mode.order
        self.assertEqual(len(first_zones), 6)
        self.assertEqual(len(set(first_zones)), len(first_zones))
        xs = [x for x, _ in first_zones]
        ys = [y for _, y in first_zones]
        self.assertGreater(max(xs) - min(xs), first.map.px_w * 0.45)
        self.assertGreater(max(ys) - min(ys), first.map.px_h * 0.45)
        self.assertEqual(first_zones, second_zones)
        different_seed = Match("depot_09", "hardpoint", seed=2, all_bots=True)
        self.assertNotEqual(first_zones, different_seed.mode.order)

    def test_scoring_and_contest(self):
        m = quiet_match(mode="hardpoint")
        mode = m.mode
        z = mode.active
        a, b = m.combatants[1], m.combatants[2]
        a.team, b.team = 0, 1
        at(m, a, z)
        for _ in range(60 * 10):
            mode.update(1 / 60)
        self.assertAlmostEqual(mode.scores[0], 10, delta=1)
        at(m, b, z)
        before = list(mode.scores)
        for _ in range(60 * 5):
            mode.update(1 / 60)
        self.assertEqual(mode.scores, before)
        self.assertTrue(mode.contested)

    def test_rotation_and_limit(self):
        m = quiet_match(mode="hardpoint")
        mode = m.mode
        first = mode.active
        mode.zone_t = 0.01
        mode.update(0.1)
        self.assertNotEqual(mode.active, first)
        mode.scores[1] = mode.SCORE_LIMIT
        mode.update(0.1)
        self.assertTrue(mode.over)
        self.assertEqual(mode.winner, 1)


if __name__ == "__main__":
    unittest.main()
