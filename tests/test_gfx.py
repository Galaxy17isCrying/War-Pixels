import unittest

import pygame

from src.gfx import draw_profile_avatar


class ProfileAvatarTests(unittest.TestCase):
    def test_missing_frame_uses_default_avatar_frame(self):
        surface = pygame.Surface((100, 100))

        draw_profile_avatar(surface, (50, 50), 48, None, None, 0.0)


if __name__ == "__main__":
    unittest.main()
