import unittest

from src.audio import RATE, Audio


class GeneratedMenuMusic(unittest.TestCase):
    def test_menu_track_is_original_generated_loop_with_expected_duration(self):
        audio = Audio.__new__(Audio)
        track = audio._music()

        self.assertEqual(len(track), int(RATE * 8 * 4 * 60 / 128))
        self.assertGreater(max(track), 0)
        self.assertLess(min(track), 0)
        self.assertGreater(len(set(track[::500])), 100)
        self.assertNotEqual(track[:1000], track[1000:2000])

    def test_menu_theme_is_distinct_from_gameplay_theme(self):
        audio = Audio.__new__(Audio)
        menu_track = audio._menu_music()
        battle_track = audio._music()

        self.assertEqual(len(menu_track), int(RATE * 8 * 4 * 60 / 124))
        self.assertNotEqual(menu_track[:10000], battle_track[:10000])
        self.assertGreater(max(menu_track), 0)
        self.assertLess(min(menu_track), 0)


if __name__ == "__main__":
    unittest.main()
