import unittest

from src.gamemap import load_map
from src.match import Match


class GroundWar(unittest.TestCase):
    def setUp(self):
        self.match = Match("ground_war", "groundwar", seed=4)

    def test_event_has_fifty_per_team_on_extreme_map(self):
        game_map = load_map("ground_war")
        self.assertEqual((game_map.w, game_map.h), (160, 100))
        self.assertEqual(len(game_map.spawns[0]), 50)
        self.assertEqual(len(game_map.spawns[1]), 50)
        self.assertTrue(all(not game_map.blocked(*pos, 12)
                            for team in (0, 1) for pos in game_map.spawns[team]))
        self.assertGreater(game_map.w * game_map.h, load_map("frontier").w * load_map("frontier").h)
        self.assertEqual(sum(combatant.team == 0 for combatant in self.match.combatants), 50)
        self.assertEqual(sum(combatant.team == 1 for combatant in self.match.combatants), 50)
        self.assertIsNotNone(self.match.player)

    def test_kills_and_controlled_sectors_score(self):
        mode = self.match.mode
        player = self.match.player
        enemy = next(c for c in self.match.combatants if c.team == 1)
        self.match.kill(enemy, player, "vanguard", False)
        self.assertEqual(mode.scores[0], 1)

        zone = mode.zones[0]
        for c in self.match.combatants:
            if c.team == 1:
                c.x, c.y = self.match.map.spawns[1][0]
        player.x, player.y = zone["pos"]
        mode.update(mode.CAPTURE_TIME + 0.1)
        self.assertEqual(zone["owner"], 0)
        mode.update(mode.HOLD_INTERVAL)
        self.assertGreaterEqual(mode.scores[0], 2)

    def test_ground_war_finishes_at_score_limit(self):
        mode = self.match.mode
        mode.scores[1] = mode.SCORE_LIMIT - 1
        victim = self.match.player
        attacker = next(c for c in self.match.combatants if c.team == 1)
        mode.on_death(victim, attacker)
        self.assertTrue(mode.over)
        self.assertEqual(mode.winner, 1)


if __name__ == "__main__":
    unittest.main()
