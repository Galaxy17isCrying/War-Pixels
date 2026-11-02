import math
import unittest

from tests.helpers import place, quiet_match
from src.config import weapons
from src.weapons import WeaponState


def shoot(m, shooter, target_pos_angle=None, frames=40):
    shooter.steady_t = 99.0
    shooter.cur = 0
    shooter.weapon.cooldown = 0
    m._fire(shooter)
    for _ in range(frames):
        m._step_bullets(1 / 60)


class Combat(unittest.TestCase):
    def setUp(self):
        self.m = quiet_match()
        self.a, self.b = self.m.combatants[0], self.m.combatants[10]
        self.a.team, self.b.team = 0, 1

    def test_headshot_damage_close_range(self):
        place(self.m, self.a, 16, 3)
        place(self.m, self.b, 20, 3)
        self.a.aim = 0.0
        shoot(self.m, self.a)
        spec = self.a.weapon.s
        expected = spec["dmg"] * spec["hs"]
        self.assertAlmostEqual(self.b.maxhp - self.b.hp, expected, places=3)
        self.assertEqual(self.a.stats["headshots"], 1)

    def test_no_shooting_through_walls(self):
        self.assertTrue(self.m.map.solid(14, 3))
        place(self.m, self.a, 13, 3)
        place(self.m, self.b, 15, 3)
        self.a.aim = 0.0
        shoot(self.m, self.a)
        self.assertEqual(self.b.hp, self.b.maxhp)
        self.assertEqual(self.m.bullets, [])

    def test_no_friendly_fire(self):
        place(self.m, self.a, 16, 3)
        place(self.m, self.b, 20, 3, team=0)
        self.a.aim = 0.0
        shoot(self.m, self.a)
        self.assertEqual(self.b.hp, self.b.maxhp)

    def test_kill_event_and_feed_once(self):
        place(self.m, self.a, 16, 3)
        place(self.m, self.b, 20, 3)
        self.b.hp = 5
        self.a.aim = 0.0
        shoot(self.m, self.a)
        self.assertFalse(self.b.alive)
        self.assertEqual(self.b.stats["deaths"], 1)
        self.assertEqual(self.a.stats["kills"], 1)
        self.assertEqual(len(self.m.killfeed), 1)

    def test_bullets_cleaned_up(self):
        place(self.m, self.a, 12, 3)
        self.a.aim = math.pi / 2
        shoot(self.m, self.a, frames=120)
        self.assertEqual(self.m.bullets, [])

    def test_spawn_protection(self):
        place(self.m, self.a, 16, 3)
        place(self.m, self.b, 20, 3)
        self.b.invuln = 1.0
        self.a.aim = 0.0
        shoot(self.m, self.a)
        self.assertEqual(self.b.hp, self.b.maxhp)

    def test_wall_collision_does_not_push_player_against_input(self):
        self.a.x, self.a.y = 100.0, 98.0
        self.a.mx, self.a.my = 1.0, 0.1
        self.m.map.blocked = lambda x, y, radius: x >= 102 or y >= 100

        self.m._move(self.a, 0.1)

        self.assertGreaterEqual(self.a.y, 98.0)
        self.assertLess(self.a.x, 102.0)

    def test_zero_delta_movement_keeps_velocity_finite(self):
        self.a.vx, self.a.vy = 12.0, -8.0

        self.m._move(self.a, 0.0)

        self.assertEqual((self.a.vx, self.a.vy), (0.0, 0.0))

    def test_immortal_combatant_ignores_damage(self):
        place(self.m, self.a, 16, 3)
        self.a.immortal = True
        self.m.damage(self.a, 50, self.b, "p9")
        self.assertEqual(self.a.hp, self.a.maxhp)
        self.assertTrue(self.a.alive)

    def test_twenty_kill_streak_awards_nuke_and_death_resets_it(self):
        victim = self.m.combatants[10]
        for _ in range(20):
            place(self.m, victim, 20, 3, team=1)
            self.m.kill(victim, self.a, "p9", False)
        self.assertEqual(self.a.kill_streak, 20)
        self.assertEqual(self.a.nuke_charges, 1)
        place(self.m, self.a, 16, 3, team=0)
        self.m.kill(self.a, victim, "p9", False)
        self.assertEqual(self.a.kill_streak, 0)
        self.assertEqual(self.a.nuke_charges, 0)

    def test_nuke_consumes_charge_and_kills_enemy_team(self):
        place(self.m, self.a, 16, 3, team=0)
        enemies = [c for c in self.m.combatants if c.team == 1]
        for enemy in enemies:
            place(self.m, enemy, 20, 3)
        self.a.nuke_charges = 1
        self.assertTrue(self.m.call_nuke(self.a))
        self.assertEqual(self.a.nuke_charges, 0)
        self.assertFalse(any(enemy.alive for enemy in enemies))
        self.assertEqual(self.a.stats["kills"], len(enemies))
        self.assertEqual(self.a.kill_streak, 0)

    def test_legendary_weapon_kill_adds_kill_effect(self):
        place(self.m, self.a, 16, 3, team=0)
        place(self.m, self.b, 20, 3, team=1)
        self.a.kill_effect_weapons = {"solstice"}
        self.m.kill(self.b, self.a, "solstice", False)
        self.assertTrue(any(effect.kind == "ice_shatter_death" for effect in self.m.fx))

    def test_m4_emberwyrm_kill_spawns_circling_dragon_effect(self):
        place(self.m, self.a, 16, 3, team=0)
        place(self.m, self.b, 20, 3, team=1)
        self.a.kill_effect_weapons = {"m4_emberwyrm"}
        self.m.kill(self.b, self.a, "m4_emberwyrm", False)
        dragon = next(effect for effect in self.m.fx if effect.kind == "dragon_death")
        self.assertEqual((dragon.x, dragon.y), (self.b.x, self.b.y))
        self.assertGreater(dragon.life, 2.0)

    def test_legendary_weapons_have_distinct_kill_effects(self):
        for weapon_id, expected in (
                ("holger_galactic_stars", "supernova_death"),
                ("viper", "void_rift_death"),
                ("longbow", "comet_death"),
                ("solstice", "ice_shatter_death")):
            with self.subTest(weapon=weapon_id):
                place(self.m, self.a, 16, 3, team=0)
                place(self.m, self.b, 20, 3, team=1)
                self.a.kill_effect_weapons = {weapon_id}
                self.m.kill(self.b, self.a, weapon_id, False)
                self.assertTrue(any(effect.kind == expected for effect in self.m.fx))

    def test_each_legendary_skin_triggers_a_distinct_death_effect(self):
        from src.progression import SKIN_DESIGNS

        effects = set()
        self.a.kill_effect_weapons = {"vanguard"}
        self.a.equipped_skins = {}
        for design in (item for item in SKIN_DESIGNS if item["rarity"] == "LEGENDARY"):
            with self.subTest(skin=design["name"]):
                self.m.fx.clear()
                place(self.m, self.a, 16, 3, team=0)
                place(self.m, self.b, 20, 3, team=1)
                self.a.equipped_skins["vanguard"] = dict(
                    rarity="LEGENDARY", kill_effect=True,
                    effect_id=f"{design['kill_effect']}__{design['id']}")
                self.m.kill(self.b, self.a, "vanguard", False)
                effect = next(item for item in self.m.fx if item.kind.startswith("skin_")
                              and item.kind.endswith("_death"))
                effects.add(effect.kind)
        self.assertEqual(len(effects), 10)

    def test_explosion_needs_line_of_sight(self):
        place(self.m, self.a, 13, 3)
        place(self.m, self.b, 15, 3)
        cx, cy = self.m.map.center(13, 3)
        self.m.explosion(cx, cy, 120, 80, self.a, 1.0)
        self.assertEqual(self.b.hp, self.b.maxhp)

    def test_knife_hits_in_front_at_melee_range(self):
        place(self.m, self.a, 12, 3)
        place(self.m, self.b, 13, 3)
        self.a.aim = 0.0
        self.a.weapons[0] = WeaponState(weapons()["field_knife"])
        self.a.cur = 0
        self.m._fire(self.a)
        self.assertEqual(self.b.hp, self.b.maxhp - weapons()["field_knife"]["dmg"])
        self.assertFalse(self.m.bullets)

    def test_launcher_detonates_on_impact_and_attributes_weapon_kill(self):
        place(self.m, self.a, 12, 3)
        place(self.m, self.b, 13, 3)
        self.b.hp = 30
        self.a.aim = 0.0
        self.a.weapons[0] = WeaponState(weapons()["breach_launcher"])
        self.a.cur = 0
        self.m._fire(self.a)
        for _ in range(10):
            self.m._step_bullets(1 / 60)
        self.assertFalse(self.b.alive)
        self.assertEqual(self.a.stats["weapon_kills"]["breach_launcher"], 1)


class Abilities(unittest.TestCase):
    def test_heal_and_cooldown(self):
        from src import abilities
        m = quiet_match()
        doc = next(c for c in m.combatants if c.char["id"] == "doc" and c.team == 0) if any(
            c.char["id"] == "doc" and c.team == 0 for c in m.combatants) else None
        c = m.combatants[0]
        c.char = dict(c.char, ability=dict(id="heal", name="x", cooldown=5, desc=""))
        place(m, c, 12, 3)
        self.assertFalse(abilities.activate(m, c))
        c.hp = 10
        self.assertTrue(abilities.activate(m, c))
        self.assertGreater(c.hp, 10)
        self.assertFalse(abilities.activate(m, c))
        self.assertGreater(c.ability_cd, 0)

    def test_barrier_blocks_then_expires(self):
        from src import abilities
        m = quiet_match()
        c = m.combatants[0]
        c.char = dict(c.char, ability=dict(id="barrier", name="x", cooldown=5, desc=""))
        place(m, c, 20, 3)
        c.aim = 0.0
        self.assertTrue(abilities.activate(m, c))
        self.assertTrue(m.map.solid_at(c.x + 64, c.y))
        m.time += 13
        m.map.tick(m.time)
        self.assertFalse(m.map.solid_at(c.x + 64, c.y))


if __name__ == "__main__":
    unittest.main()
