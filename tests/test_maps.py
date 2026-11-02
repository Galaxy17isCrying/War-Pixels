import unittest

from tests import helpers  # noqa: F401
from src.config import maps_meta
from src.gamemap import load_map
from src.pathfinding import find_path


class Maps(unittest.TestCase):
    def test_five_distinct_maps(self):
        metas = maps_meta()
        self.assertGreaterEqual(len(metas), 5)
        areas = [load_map(m["id"]).w * load_map(m["id"]).h for m in metas]
        self.assertEqual(areas, sorted(areas))
        self.assertGreater(areas[-1] / areas[0], 6)
        layouts = {tuple(map(tuple, load_map(m["id"]).grid[:12])) for m in metas}
        self.assertEqual(len(layouts), len(metas))

    def test_markers_and_connectivity(self):
        for m in maps_meta():
            gm = load_map(m["id"])
            self.assertGreaterEqual(len(gm.spawns[0]), 10, m["id"])
            self.assertGreaterEqual(len(gm.spawns[1]), 10, m["id"])
            self.assertEqual(sorted(gm.flags), [0, 1])
            self.assertGreaterEqual(len(gm.sites), 2)
            self.assertGreaterEqual(len(gm.zones), 3)
            for team in (0, 1):
                for p in gm.spawns[team]:
                    self.assertFalse(gm.blocked(p[0], p[1], 12), f"{m['id']} spawn blocked")
            targets = gm.sites + gm.zones + list(gm.flags.values()) + gm.spawns[1]
            for t in targets:
                self.assertIsNotNone(find_path(gm, gm.spawns[0][0], t), f"{m['id']} unreachable {t}")

    def test_collision_and_raycast(self):
        gm = load_map("depot_09")
        self.assertTrue(gm.blocked(5, 5, 10))
        self.assertTrue(gm.solid_at(-5, 100))
        self.assertIsNotNone(gm.raycast(*gm.center(13, 3), *gm.center(15, 3)))
        self.assertIsNone(gm.raycast(*gm.center(2, 3), *gm.center(10, 3)))

    def test_practice_range(self):
        gm = load_map("range")
        self.assertGreaterEqual(len(gm.targets), 5)
        self.assertGreaterEqual(len(gm.movers), 2)


if __name__ == "__main__":
    unittest.main()
