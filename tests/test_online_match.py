import unittest

from src.match import Match


ROSTER = [
    {"player_id": "alpha", "name": "ALPHA", "char": "vanguard", "primary": "vanguard", "secondary": "p9",
     "equipment": "none", "team": 0},
    {"player_id": "bravo", "name": "BRAVO", "char": "vanguard", "primary": "vanguard", "secondary": "p9",
     "equipment": "none", "team": 1},
]


class OnlineMatchTests(unittest.TestCase):
    def create_match(self, local_player_id):
        return Match("depot_09", "snd", "NORMAL", seed=8231, team_size=5,
                     online_players=ROSTER, local_player_id=local_player_id)

    def test_roster_assigns_one_local_player_per_team(self):
        alpha = self.create_match("alpha")
        bravo = self.create_match("bravo")

        self.assertEqual(alpha.player.name, "ALPHA")
        self.assertEqual(alpha.player.team, 0)
        self.assertEqual(bravo.player.name, "BRAVO")
        self.assertEqual(bravo.player.team, 1)
        self.assertEqual(len(alpha.online_players), 2)
        self.assertEqual(len(alpha.combatants), 10)
        self.assertEqual([(bot.name, bot.team) for bot in alpha.combatants if bot.is_bot],
                         [(bot.name, bot.team) for bot in bravo.combatants if bot.is_bot])

    def test_identical_seed_and_relayed_inputs_keep_simulations_in_sync(self):
        matches = [self.create_match("alpha"), self.create_match("bravo")]
        for _ in range(24):
            for match in matches:
                alpha = match.online_players["alpha"]
                bravo = match.online_players["bravo"]
                alpha.mx, alpha.my, alpha.aim, alpha.trigger = 1.0, 0.0, 0.0, True
                bravo.mx, bravo.my, bravo.aim, bravo.trigger = -1.0, 0.0, 3.14, True
                match.update(0.05)

        first, second = matches
        self.assertEqual(first.time, second.time)
        for player_id in ("alpha", "bravo"):
            a, b = first.online_players[player_id], second.online_players[player_id]
            self.assertAlmostEqual(a.x, b.x)
            self.assertAlmostEqual(a.y, b.y)
            self.assertEqual(a.hp, b.hp)
            self.assertEqual(a.weapon.mag, b.weapon.mag)

    def test_online_player_death_does_not_open_a_client_only_loadout_picker(self):
        match = Match("depot_09", "ctf", "NORMAL", seed=8231, team_size=5,
                      online_players=ROSTER, local_player_id="alpha")
        victim = match.online_players["alpha"]
        attacker = match.online_players["bravo"]

        match.kill(victim, attacker, "vanguard", False)

        self.assertFalse(victim.awaiting_loadout)


if __name__ == "__main__":
    unittest.main()
