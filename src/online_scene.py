import pygame

from .config import CANVAS_H, CANVAS_W
from .gfx import AMBER, CYAN, GRAY, GREEN, WHITE, panel, text
from .multiplayer import MatchmakingClient
from .scenes import CX, Scene


class OnlineScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.address = app.settings["match_server"]
        self.room_code = ""
        self.editing_address = False
        self.editing_room_code = False
        self.status = "CHOOSE A FRIEND ROOM OR PUBLIC MATCHMAKING."
        self.client = None
        self.address_rect = pygame.Rect(CX - 250, 280, 500, 46)
        self.room_code_rect = pygame.Rect(CX - 90, 356, 180, 46)
        self.create_room_rect = pygame.Rect(260, 430, 220, 54)
        self.join_room_rect = pygame.Rect(530, 430, 220, 54)
        self.matchmaking_rect = pygame.Rect(800, 430, 220, 54)

    def _text_input(self, enabled):
        method = getattr(pygame.key, "start_text_input" if enabled else "stop_text_input", None)
        if method:
            method()

    def _cancel(self):
        if self.client:
            self.client.close()
            self.client = None
        self.editing_address = False
        self.editing_room_code = False
        self._text_input(False)
        self.app.pop()

    def _start_request(self, request_type):
        endpoint = self.address.strip()
        try:
            host, port_text = endpoint.rsplit(":", 1)
            port = int(port_text)
            if not host or not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.status = "INVALID SERVER ADDRESS. USE HOST:PORT."
            return
        room_code = self.room_code.strip().upper()
        if request_type == "join_room" and (
            len(room_code) != 6 or any(char not in "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" for char in room_code)
        ):
            self.status = "ENTER THE SIX-CHARACTER ROOM CODE."
            return
        self.editing_address = False
        self.editing_room_code = False
        self._text_input(False)
        if self.client:
            self.client.close()
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
            "type": request_type,
            "mode_id": "snd",
            "map_id": "depot_09",
            "team_size": 5,
            "profile": profile,
        }
        if request_type == "join_room":
            request["room_code"] = room_code
        self.client = MatchmakingClient(host, port, request)
        self.client.start()
        self.status = {
            "queue": "CONNECTING TO PUBLIC MATCHMAKING...",
            "create_room": "CREATING A FRIEND ROOM...",
            "join_room": f"JOINING ROOM {room_code}...",
        }[request_type]

    def event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.editing_address or self.editing_room_code:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.editing_address = False
                    self.editing_room_code = False
                    self._text_input(False)
                elif event.key == pygame.K_ESCAPE:
                    self.editing_address = False
                    self.editing_room_code = False
                    self._text_input(False)
                elif event.key == pygame.K_BACKSPACE:
                    if self.editing_address:
                        self.address = self.address[:-1]
                    else:
                        self.room_code = self.room_code[:-1]
                else:
                    value = getattr(event, "unicode", "")
                    if self.editing_address and value and value.isprintable() and len(self.address) < 180:
                        self.address += value
                    elif self.editing_room_code and value:
                        self.room_code = "".join(
                            char for char in (self.room_code + value).upper()
                            if char in "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
                        )[:6]
                return
            if event.key == pygame.K_ESCAPE:
                self._cancel()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._start_request("queue")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.app.mouse()
            if self.address_rect.collidepoint(pos):
                self.editing_address = True
                self.editing_room_code = False
                self._text_input(True)
            elif self.room_code_rect.collidepoint(pos):
                self.editing_room_code = True
                self.editing_address = False
                self._text_input(True)
            elif self.create_room_rect.collidepoint(pos):
                self._start_request("create_room")
            elif self.join_room_rect.collidepoint(pos):
                self._start_request("join_room")
            elif self.matchmaking_rect.collidepoint(pos):
                self._start_request("queue")
            elif pygame.Rect(32, CANVAS_H - 64, 170, 40).collidepoint(pos):
                self._cancel()

    def update(self, dt):
        super().update(dt)
        if not self.client:
            return
        for message in self.client.poll():
            kind = message.get("type")
            if kind == "queued":
                self.status = "PUBLIC MATCHMAKING - WAITING FOR PLAYERS..."
            elif kind == "room_created":
                room_code = message.get("room_code")
                if not isinstance(room_code, str) or len(room_code) != 6:
                    self.status = "SERVER RETURNED AN INVALID ROOM CODE."
                    self.client.close()
                    self.client = None
                    return
                self.room_code = room_code
                self.status = f"ROOM {room_code} CREATED - SHARE THE CODE WITH A FRIEND."
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
        panel(surf, (CANVAS_W // 2 - 520, 150, 1040, 480), fill=(15, 23, 26), alpha=245)
        text(surf, "MULTIPLAYER", (CX, 176), 33, AMBER, "midtop")
        text(surf, "CREATE OR JOIN A FRIEND ROOM, OR FIND A PUBLIC MATCH", (CX, 222), 14, CYAN, "midtop")
        color = AMBER if self.editing_address else WHITE
        panel(surf, self.address_rect, fill=(8, 14, 18), alpha=255)
        text(surf, f"{self.address}{'_' if self.editing_address else ''}",
             (CX, self.address_rect.centery), 18, color, "center")
        text(surf, "SERVER ADDRESS - TAP TO EDIT", (CX, 260), 12, GRAY, "midtop")
        room_color = AMBER if self.editing_room_code else WHITE
        panel(surf, self.room_code_rect, fill=(8, 14, 18), alpha=255)
        text(surf, f"{self.room_code or '------'}{'_' if self.editing_room_code else ''}",
             self.room_code_rect.center, 18, room_color, "center")
        text(surf, "ROOM CODE - ENTER A FRIEND'S CODE TO JOIN", (CX, 338), 12, GRAY, "midtop")
        for rect, label, tint in (
            (self.create_room_rect, "CREATE ROOM", AMBER),
            (self.join_room_rect, "JOIN ROOM", CYAN),
            (self.matchmaking_rect, "FIND MATCH", GREEN),
        ):
            panel(surf, rect, tint, (14, 21, 23), alpha=255)
            text(surf, label, rect.center, 17, tint, "center")
        text(surf, self.status, (CX, 510), 14, CYAN if self.client else GRAY, "midtop")
        text(surf, "FRIENDS MUST USE THE SAME SERVER ADDRESS  /  ESC TO RETURN",
             (CX, 548), 12, GRAY, "midtop")
        panel(surf, (32, CANVAS_H - 64, 170, 40), CYAN, (14, 21, 23), alpha=230)
        text(surf, "BACK", (117, CANVAS_H - 44), 14, WHITE, "center")
