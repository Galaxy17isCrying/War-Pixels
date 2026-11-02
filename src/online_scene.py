import pygame

from .config import CANVAS_H, CANVAS_W
from .gfx import AMBER, CYAN, GRAY, WHITE, panel, text
from .multiplayer import MatchmakingClient
from .scenes import CX, Scene


class OnlineScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.address = app.settings["match_server"]
        self.editing_address = False
        self.status = "ENTER A MATCH SERVER, THEN FIND MATCH."
        self.client = None
        self.queue_rect = pygame.Rect(CX - 185, 415, 370, 54)
        self.address_rect = pygame.Rect(CX - 220, 320, 440, 48)

    def _text_input(self, enabled):
        method = getattr(pygame.key, "start_text_input" if enabled else "stop_text_input", None)
        if method:
            method()

    def _cancel(self):
        if self.client:
            self.client.close()
            self.client = None
        self._text_input(False)
        self.app.pop()

    def _start_queue(self):
        if self.client:
            self.client.close()
        endpoint = self.address.strip()
        try:
            host, port_text = endpoint.rsplit(":", 1)
            port = int(port_text)
            if not host or not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.status = "INVALID SERVER ADDRESS. USE HOST:PORT."
            return
        self.address = endpoint
        self.app.settings["match_server"] = endpoint
        self.app.settings.save()
        loadout = self.app.settings["loadout"]
        profile = {
            "player_id": self.app.stats.player_uid(),
            "name": self.app.stats.player_name(),
            "char": loadout["char"],
            "primary": loadout["primary"],
            "secondary": loadout["secondary"],
            "equipment": loadout["equipment"],
        }
        request = {
            "type": "queue",
            "mode_id": "snd",
            "map_id": "depot_09",
            "team_size": 5,
            "profile": profile,
        }
        self.client = MatchmakingClient(host, port, request)
        self.client.start()
        self.status = "CONNECTING TO MATCHMAKING..."

    def event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.editing_address:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.editing_address = False
                    self._text_input(False)
                elif event.key == pygame.K_ESCAPE:
                    self.editing_address = False
                    self._text_input(False)
                elif event.key == pygame.K_BACKSPACE:
                    self.address = self.address[:-1]
                else:
                    value = getattr(event, "unicode", "")
                    if value and value.isprintable() and len(self.address) < 180:
                        self.address += value
                return
            if event.key == pygame.K_ESCAPE:
                self._cancel()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._start_queue()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.app.mouse()
            if self.address_rect.collidepoint(pos):
                self.editing_address = True
                self._text_input(True)
            elif self.queue_rect.collidepoint(pos):
                self._start_queue()
            elif pygame.Rect(32, CANVAS_H - 64, 170, 40).collidepoint(pos):
                self._cancel()

    def update(self, dt):
        super().update(dt)
        if not self.client:
            return
        for message in self.client.poll():
            kind = message.get("type")
            if kind == "queued":
                self.status = "IN QUEUE - WAITING FOR ANOTHER PLAYER..."
            elif kind == "matched":
                try:
                    from .match_scene import MatchScene
                    match_scene = MatchScene(self.app, message["mode_id"], message["map_id"],
                                             team_size=message["team_size"],
                                             online_client=self.client, online_match=message)
                except (KeyError, TypeError, ValueError) as exc:
                    self.status = f"INVALID MATCH DATA: {str(exc)[:70]}".upper()
                    self.client.close()
                    self.client = None
                    return
                self.app.replace(match_scene)
                return
            elif kind in ("error", "disconnected"):
                self.status = str(message.get("message", "SERVER DISCONNECTED"))[:100].upper()
                self.client.close()
                self.client = None

    def draw(self, surf):
        surf.fill((8, 13, 17))
        panel(surf, (CANVAS_W // 2 - 300, 180, 600, 390), fill=(15, 23, 26), alpha=245)
        text(surf, "ONLINE MATCHMAKING", (CX, 208), 33, AMBER, "midtop")
        text(surf, "DEDICATED SERVER  /  SEARCH AND DESTROY  /  5v5", (CX, 260), 14, CYAN, "midtop")
        color = AMBER if self.editing_address else WHITE
        panel(surf, self.address_rect, fill=(8, 14, 18), alpha=255)
        text(surf, f"{self.address}{'_' if self.editing_address else ''}",
             (CX, self.address_rect.centery), 18, color, "center")
        text(surf, "SERVER ADDRESS - TAP TO EDIT", (CX, 296), 12, GRAY, "midtop")
        panel(surf, self.queue_rect, AMBER, (29, 34, 30), alpha=255)
        text(surf, "FIND MATCH", self.queue_rect.center, 21, AMBER, "center")
        text(surf, self.status, (CX, 495), 15, CYAN if self.client else GRAY, "midtop")
        text(surf, "ESC TO RETURN  /  SERVER USES THE SAME MATCHMAKING BUILD", (CX, 535), 12, GRAY, "midtop")
        panel(surf, (32, CANVAS_H - 64, 170, 40), CYAN, (14, 21, 23), alpha=230)
        text(surf, "BACK", (117, CANVAS_H - 44), 14, WHITE, "center")
