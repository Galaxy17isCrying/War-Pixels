import os
import sys

import pygame

from .audio import Audio
from .config import APP_TITLE, CANVAS_H, CANVAS_W
from .save import FPS_CAPS, RESOLUTIONS, Settings, StatsDB


class App:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption(APP_TITLE)
        self.settings = Settings()
        self.stats = StatsDB()
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H))
        self.window = None
        self.scale, self.offset = 1.0, (0, 0)
        self.apply_display()
        self.audio = Audio(self.settings)
        self.audio.start_music()
        self.clock = pygame.time.Clock()
        self.scenes = []
        self.intro_seen = False
        self.running = True
        self.touch_enabled = sys.platform == "android" or bool(os.environ.get("ANDROID_ARGUMENT"))
        self._touch_points = {}
        self._touch_mouse_pos = None

    # display ------------------------------------------------------------
    def apply_display(self):
        s = self.settings
        if s["fullscreen"]:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(RESOLUTIONS[s["res"]], pygame.RESIZABLE)
        self._layout()

    def _layout(self):
        w, h = self.window.get_size()
        self.scale = min(w / CANVAS_W, h / CANVAS_H)
        self.offset = ((w - CANVAS_W * self.scale) / 2, (h - CANVAS_H * self.scale) / 2)

    def mouse(self):
        if self._touch_mouse_pos is not None:
            return self.screen_to_canvas(self._touch_mouse_pos)
        return self.screen_to_canvas(pygame.mouse.get_pos())

    def screen_to_canvas(self, pos):
        x, y = pos
        return ((x - self.offset[0]) / self.scale, (y - self.offset[1]) / self.scale)

    def _dispatch_touch_event(self, event):
        self.touch_enabled = True
        event_scene = self.scenes[-1]
        window_w, window_h = self.window.get_size()
        finger_id = event.finger_id
        previous = self._touch_points.get(finger_id)
        pos = (event.x * window_w, event.y * window_h)
        self._touch_mouse_pos = pos
        if event.type == getattr(pygame, "FINGERDOWN", -1):
            self._touch_points[finger_id] = pos
            mouse_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)
        elif event.type == getattr(pygame, "FINGERMOTION", -2):
            self._touch_points[finger_id] = pos
            old = previous or pos
            mouse_event = pygame.event.Event(
                pygame.MOUSEMOTION, pos=pos, rel=(pos[0] - old[0], pos[1] - old[1]), buttons=(1, 0, 0))
        else:
            mouse_event = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)
        event_scene.event(mouse_event)
        if self.scenes[-1] is event_scene:
            event_scene.event(event)
        if event.type == getattr(pygame, "FINGERUP", -3):
            self._touch_points.pop(finger_id, None)
            self._touch_mouse_pos = next(iter(self._touch_points.values()), None)

    # scenes -------------------------------------------------------------
    def push(self, scene):
        self.scenes.append(scene)

    def pop(self):
        if len(self.scenes) > 1:
            self.scenes.pop()
            self.scenes[-1].on_enter()

    def replace(self, scene):
        self.scenes[-1] = scene

    def reset_to_menu(self):
        from .scenes import MainMenu
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        self.scenes = [MainMenu(self)]

    def quit(self):
        self.running = False

    # loop ---------------------------------------------------------------
    def run(self):
        from .scenes import MainMenu
        self.scenes = [MainMenu(self)]
        while self.running:
            cap = FPS_CAPS[self.settings["fps"]]
            dt = self.clock.tick(cap) / 1000.0
            self.stats.update_bot_world(min(dt, 0.1))
            scene = self.scenes[-1]
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.VIDEORESIZE and not self.settings["fullscreen"]:
                    self.window = pygame.display.get_surface()
                    self._layout()
                elif e.type in (getattr(pygame, "FINGERDOWN", -1),
                                getattr(pygame, "FINGERMOTION", -2),
                                getattr(pygame, "FINGERUP", -3)):
                    self._dispatch_touch_event(e)
                else:
                    self.scenes[-1].event(e)
            scene = self.scenes[-1]
            scene.update(min(dt, 0.1))
            scene.draw(self.canvas)
            self.window.fill((0, 0, 0))
            w, h = int(CANVAS_W * self.scale), int(CANVAS_H * self.scale)
            if (w, h) == (CANVAS_W, CANVAS_H):
                self.window.blit(self.canvas, self.offset)
            else:
                self.window.blit(pygame.transform.scale(self.canvas, (w, h)), self.offset)
            pygame.display.flip()
        self.settings.save()
        pygame.quit()
