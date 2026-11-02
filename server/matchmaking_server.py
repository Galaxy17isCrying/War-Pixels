"""Async TCP matchmaking and deterministic 20 Hz input relay."""

from __future__ import annotations

import asyncio
import json
import math
import re
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from src.config import EQUIPMENT, characters, maps_meta, weapons
from src.modes import MODES

TICK_RATE = 20
TICK_INTERVAL = 1 / TICK_RATE
MAX_LINE_BYTES = 16_384
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
_ROOM_CODE = re.compile(r"^[A-HJ-NP-Z2-9]{6}$")
_PROFILE_FIELDS = {
    "player_id": 64,
    "name": 32,
    "char": 48,
    "primary": 48,
    "secondary": 48,
    "equipment": 48,
}
_ACTION_FIELDS = {
    "move_x", "move_y", "aim", "trigger", "ads", "sprint", "interact",
    "reload", "ability", "swap_to",
}
_HELD_BOOLEAN_FIELDS = {"trigger", "ads", "sprint", "interact"}
_EDGE_BOOLEAN_FIELDS = {"reload", "ability"}
_MATCH_MODES = frozenset(set(MODES) - {"practice", "groundwar"})
_MAP_IDS = frozenset(map_data["id"] for map_data in maps_meta() if map_data["id"] != "ground_war")
_CHARACTER_IDS = frozenset(char["id"] for char in characters())
_WEAPON_IDS = frozenset(weapons())


class ProtocolError(ValueError):
    """Raised when a client message is invalid or exceeds protocol bounds."""


def _validate_text(value: Any, field_name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ProtocolError(f"{field_name} must be a string")
    if not value or len(value) > max_length or value != value.strip():
        raise ProtocolError(f"{field_name} has an invalid length or whitespace")
    if any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ProtocolError(f"{field_name} contains control characters")
    return value


def validate_queue_message(message: Any) -> dict[str, Any]:
    """Validate and copy the initial queue request."""
    if not isinstance(message, dict) or set(message) != {
        "type", "mode_id", "map_id", "team_size", "profile"
    } or message.get("type") != "queue":
        raise ProtocolError("first message must be a queue request")
    mode_id = _validate_text(message.get("mode_id"), "mode_id", 48)
    map_id = _validate_text(message.get("map_id"), "map_id", 48)
    if not _IDENTIFIER.fullmatch(mode_id) or not _IDENTIFIER.fullmatch(map_id):
        raise ProtocolError("mode_id and map_id must be identifiers")
    if mode_id not in _MATCH_MODES or map_id not in _MAP_IDS:
        raise ProtocolError("mode_id or map_id is not available for online matches")
    team_size = message.get("team_size")
    if isinstance(team_size, bool) or not isinstance(team_size, int) or not 5 <= team_size <= 10:
        raise ProtocolError("team_size must be an integer from 5 to 10")

    raw_profile = message.get("profile")
    if not isinstance(raw_profile, dict) or set(raw_profile) != set(_PROFILE_FIELDS):
        raise ProtocolError("profile must contain exactly the required profile fields")
    profile = {
        key: _validate_text(raw_profile[key], f"profile.{key}", length)
        for key, length in _PROFILE_FIELDS.items()
    }
    if (profile["char"] not in _CHARACTER_IDS or profile["primary"] not in _WEAPON_IDS or
            profile["secondary"] not in _WEAPON_IDS or profile["equipment"] not in EQUIPMENT):
        raise ProtocolError("profile contains an unavailable character, weapon, or equipment")
    return {
        "type": "queue",
        "mode_id": mode_id,
        "map_id": map_id,
        "team_size": team_size,
        "profile": profile,
    }


def validate_room_message(message: Any, room_action: str) -> dict[str, Any]:
    """Validate a private-room create or join request."""
    if room_action not in ("create_room", "join_room"):
        raise ProtocolError("room action is not supported")
    expected = {"type", "mode_id", "map_id", "team_size", "profile"}
    if room_action == "join_room":
        expected.add("room_code")
    if not isinstance(message, dict) or set(message) != expected or message.get("type") != room_action:
        raise ProtocolError(f"first message must be a {room_action} request")

    queue_request = {
        "type": "queue",
        "mode_id": message["mode_id"],
        "map_id": message["map_id"],
        "team_size": message["team_size"],
        "profile": message["profile"],
    }
    clean = validate_queue_message(queue_request)
    clean["type"] = room_action
    if room_action == "join_room":
        room_code = _validate_text(message["room_code"], "room_code", 6).upper()
        if not _ROOM_CODE.fullmatch(room_code):
            raise ProtocolError("room_code must be a six-character room code")
        clean["room_code"] = room_code
    return clean


def validate_client_request(message: Any) -> dict[str, Any]:
    """Validate the first request from either a matchmaking or room client."""
    if isinstance(message, dict):
        request_type = message.get("type")
        if request_type == "queue":
            return validate_queue_message(message)
        if request_type in ("create_room", "join_room"):
            return validate_room_message(message, request_type)
    raise ProtocolError("first message must be a queue, create_room, or join_room request")


def validate_action(action: Any) -> dict[str, Any]:
    """Validate the complete client action state and return a clean copy."""
    if not isinstance(action, dict) or set(action) != _ACTION_FIELDS:
        raise ProtocolError("action must contain exactly the supported action fields")
    clean: dict[str, Any] = {}
    for field_name in ("move_x", "move_y"):
        value = action[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProtocolError(f"action.{field_name} must be a number")
        try:
            numeric_value = float(value)
        except (OverflowError, ValueError) as exc:
            raise ProtocolError(f"action.{field_name} must be finite and between -1 and 1") from exc
        if not math.isfinite(numeric_value) or not -1 <= numeric_value <= 1:
            raise ProtocolError(f"action.{field_name} must be finite and between -1 and 1")
        clean[field_name] = numeric_value
    aim = action["aim"]
    if isinstance(aim, bool) or not isinstance(aim, (int, float)):
        raise ProtocolError("action.aim must be a finite number")
    try:
        numeric_aim = float(aim)
    except (OverflowError, ValueError) as exc:
        raise ProtocolError("action.aim must be a finite number") from exc
    if not math.isfinite(numeric_aim):
        raise ProtocolError("action.aim must be a finite number")
    clean["aim"] = numeric_aim
    for field_name in _HELD_BOOLEAN_FIELDS | _EDGE_BOOLEAN_FIELDS:
        if not isinstance(action[field_name], bool):
            raise ProtocolError(f"action.{field_name} must be a boolean")
        clean[field_name] = action[field_name]
    swap_to = action["swap_to"]
    if swap_to is not None and (
        isinstance(swap_to, bool) or not isinstance(swap_to, int) or swap_to not in (0, 1)
    ):
        raise ProtocolError("action.swap_to must be null, 0, or 1")
    clean["swap_to"] = swap_to
    return clean


def encode_message(message: dict[str, Any]) -> bytes:
    """Serialize a protocol object as one bounded newline-delimited JSON line."""
    try:
        data = json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ProtocolError("message cannot be encoded") from exc
    if len(data) + 1 > MAX_LINE_BYTES:
        raise ProtocolError("message exceeds line size limit")
    return data + b"\n"


async def read_message(reader: asyncio.StreamReader) -> dict[str, Any] | None:
    """Read one bounded JSON line; return None only for a clean EOF."""
    try:
        line = await reader.readline()
    except (ValueError, asyncio.LimitOverrunError) as exc:
        raise ProtocolError("message exceeds line size limit") from exc
    if not line:
        return None
    if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
        raise ProtocolError("message must be a bounded newline-terminated line")
    try:
        message = json.loads(
            line.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ProtocolError("message must be valid JSON") from exc
    if not isinstance(message, dict):
        raise ProtocolError("message must be a JSON object")
    return message


@dataclass(eq=False)
class _Client:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    queue_request: dict[str, Any]
    room_code: str | None = None
    matched: asyncio.Event = field(default_factory=asyncio.Event)
    match: "_Match | None" = None
    held: dict[str, Any] = field(default_factory=lambda: {
        "move_x": 0.0,
        "move_y": 0.0,
        "aim": 0.0,
        "trigger": False,
        "ads": False,
        "sprint": False,
        "interact": False,
        "reload": False,
        "ability": False,
        "swap_to": None,
    })
    pending_reload: bool = False
    pending_ability: bool = False
    pending_swap_to: int | None = None

    @property
    def player_id(self) -> str:
        return self.queue_request["profile"]["player_id"]


@dataclass
class _Match:
    match_id: str
    seed: int
    clients: tuple[_Client, _Client]
    mode_id: str
    map_id: str
    team_size: int
    ready_count: int = 0
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    tick_task: asyncio.Task[None] | None = None
    ended: bool = False
    tick: int = 0

    def matched_message(self, client: _Client) -> dict[str, Any]:
        players = []
        for team, player in enumerate(self.clients):
            profile = dict(player.queue_request["profile"])
            profile["team"] = team
            players.append(profile)
        return {
            "type": "matched",
            "match_id": self.match_id,
            "seed": self.seed,
            "mode_id": self.mode_id,
            "map_id": self.map_id,
            "team_size": self.team_size,
            "players": players,
        }


class MatchmakingServer:
    """Pair compatible TCP clients and relay their inputs at a fixed tick rate."""

    def __init__(self) -> None:
        self._waiting: dict[tuple[str, str, int], deque[_Client]] = defaultdict(deque)
        self._rooms: dict[str, _Client] = {}
        self._clients: set[_Client] = set()
        self._player_ids: set[str] = set()
        self._lock = asyncio.Lock()
        self._server: asyncio.AbstractServer | None = None

    async def start(self, host: str = "0.0.0.0", port: int = 8765) -> asyncio.AbstractServer:
        if self._server is not None:
            raise RuntimeError("server is already started")
        self._server = await asyncio.start_server(
            self._handle_client,
            host,
            port,
            limit=MAX_LINE_BYTES,
        )
        return self._server

    async def serve_forever(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        server = await self.start(host, port)
        async with server:
            await server.serve_forever()

    async def close(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            server.close()
            await server.wait_closed()
        clients = list(self._clients)
        for client in clients:
            match = client.match
            if match is not None and match.tick_task is not None:
                match.tick_task.cancel()
            client.writer.close()
        if clients:
            await asyncio.gather(
                *(client.writer.wait_closed() for client in clients),
                return_exceptions=True,
            )

    async def _send(self, writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
        writer.write(encode_message(message))
        await writer.drain()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        client: _Client | None = None
        try:
            request = await read_message(reader)
            if request is None:
                return
            request = validate_client_request(request)
            client = _Client(reader=reader, writer=writer, queue_request=request)
            await self._register(client)
            await client.matched.wait()
            match = client.match
            if match is None or match.ended:
                return
            await self._send(writer, match.matched_message(client))
            match.ready_count += 1
            if match.ready_count == len(match.clients):
                match.ready.set()
            while not match.ended:
                message = await read_message(reader)
                if message is None:
                    break
                if message.get("type") != "input" or set(message) != {"type", "action"}:
                    raise ProtocolError("expected an input message")
                action = validate_action(message["action"])
                if match.ended:
                    break
                client.held.update({key: action[key] for key in _HELD_BOOLEAN_FIELDS})
                client.held.update({
                    "move_x": action["move_x"],
                    "move_y": action["move_y"],
                    "aim": action["aim"],
                })
                client.pending_reload = client.pending_reload or (action["reload"] and not client.held["reload"])
                client.pending_ability = client.pending_ability or (action["ability"] and not client.held["ability"])
                if action["swap_to"] is not None and action["swap_to"] != client.held["swap_to"]:
                    client.pending_swap_to = action["swap_to"]
                client.held["reload"] = action["reload"]
                client.held["ability"] = action["ability"]
                client.held["swap_to"] = action["swap_to"]
        except (ProtocolError, ConnectionError, OSError, asyncio.IncompleteReadError) as exc:
            if (client is None or client not in self._clients) and not writer.is_closing():
                try:
                    message = str(exc) if isinstance(exc, ProtocolError) else "invalid protocol message"
                    await self._send(writer, {"type": "error", "message": message})
                except (ConnectionError, OSError, ProtocolError):
                    pass
        finally:
            if client is not None:
                await self._remove_client(client)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    async def _register(self, client: _Client) -> None:
        key = (
            client.queue_request["mode_id"],
            client.queue_request["map_id"],
            client.queue_request["team_size"],
        )
        async with self._lock:
            player_id = client.player_id
            if player_id in self._player_ids:
                raise ProtocolError("player_id is already connected")
            request_type = client.queue_request["type"]
            host = None
            if request_type == "join_room":
                room_code = client.queue_request["room_code"]
                host = self._rooms.get(room_code)
                if host is None or host.writer.is_closing():
                    self._rooms.pop(room_code, None)
                    raise ProtocolError("room not found")
                host_request = host.queue_request
                if any(host_request[name] != client.queue_request[name]
                       for name in ("mode_id", "map_id", "team_size")):
                    raise ProtocolError("room settings do not match")
            self._player_ids.add(player_id)
            self._clients.add(client)
            if request_type == "create_room":
                room_code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
                while room_code in self._rooms:
                    room_code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
                self._rooms[room_code] = client
                client.room_code = room_code
                await self._send(client.writer, {"type": "room_created", "room_code": room_code})
                return
            if request_type == "join_room":
                assert host is not None
                self._rooms.pop(client.queue_request["room_code"], None)
                host.room_code = None
                client.room_code = None
                self._pair_clients(host, client, key)
                return
            queue = self._waiting[key]
            while queue and queue[0].writer.is_closing():
                queue.popleft()
            if queue:
                other = queue.popleft()
                if not queue:
                    self._waiting.pop(key, None)
                self._pair_clients(other, client, key)
            else:
                queue.append(client)
                await self._send(client.writer, {"type": "queued"})

    def _pair_clients(
        self,
        first: _Client,
        second: _Client,
        key: tuple[str, str, int],
    ) -> None:
        match = _Match(
            match_id=secrets.token_urlsafe(12),
            seed=secrets.randbelow(2**31),
            clients=(first, second),
            mode_id=key[0],
            map_id=key[1],
            team_size=key[2],
        )
        first.match = second.match = match
        first.matched.set()
        second.matched.set()
        match.tick_task = asyncio.create_task(self._tick_loop(match))

    async def _remove_client(self, client: _Client) -> None:
        async with self._lock:
            if client not in self._clients:
                return
            self._clients.discard(client)
            self._player_ids.discard(client.player_id)
            if client.room_code is not None and self._rooms.get(client.room_code) is client:
                self._rooms.pop(client.room_code, None)
                client.room_code = None
            for key, queue in list(self._waiting.items()):
                try:
                    queue.remove(client)
                except ValueError:
                    continue
                if not queue:
                    self._waiting.pop(key, None)
                break
            match = client.match
            if match is None or match.ended:
                return
            match.ended = True
            peer = next((candidate for candidate in match.clients if candidate is not client), None)
            tick_task = match.tick_task
        if tick_task is not None and tick_task is not asyncio.current_task():
            tick_task.cancel()
            await asyncio.gather(tick_task, return_exceptions=True)
        if peer is not None and not peer.writer.is_closing():
            try:
                async with match.send_lock:
                    await self._send(peer.writer, {"type": "disconnected"})
            except (ConnectionError, OSError, ProtocolError):
                pass
            peer.writer.close()

    async def _tick_loop(self, match: _Match) -> None:
        try:
            await match.ready.wait()
            next_tick = time.monotonic() + TICK_INTERVAL
            while not match.ended:
                await asyncio.sleep(max(0.0, next_tick - time.monotonic()))
                if match.ended:
                    return
                inputs = []
                for client in match.clients:
                    action = dict(client.held)
                    action["reload"] = client.pending_reload
                    action["ability"] = client.pending_ability
                    action["swap_to"] = client.pending_swap_to
                    client.pending_reload = False
                    client.pending_ability = False
                    client.pending_swap_to = None
                    inputs.append({"player_id": client.player_id, "action": action})
                message = {"type": "tick", "tick": match.tick, "inputs": inputs}
                match.tick += 1
                async with match.send_lock:
                    if match.ended:
                        return
                    await asyncio.gather(
                        *(self._send(client.writer, message) for client in match.clients)
                    )
                next_tick += TICK_INTERVAL
                if next_tick < time.monotonic() - TICK_INTERVAL:
                    next_tick = time.monotonic() + TICK_INTERVAL
        except (ConnectionError, OSError, ProtocolError, asyncio.CancelledError):
            return
