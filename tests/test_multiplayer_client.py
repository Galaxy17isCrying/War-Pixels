import asyncio
import unittest

from server.matchmaking_server import MatchmakingServer
from src.multiplayer import MatchmakingClient


def request(player_id):
    return {
        "type": "queue",
        "mode_id": "snd",
        "map_id": "depot_09",
        "team_size": 5,
        "profile": {
            "player_id": player_id,
            "name": player_id.upper(),
            "char": "vanguard",
            "primary": "vanguard",
            "secondary": "p9",
            "equipment": "none",
        },
    }


def idle_action(**overrides):
    action = {
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
    }
    action.update(overrides)
    return action


class MultiplayerClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_friend_room_code_connects_two_clients(self):
        matchmaking = MatchmakingServer()
        server = await matchmaking.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        host_request = request("host")
        host_request["type"] = "create_room"
        host = MatchmakingClient("127.0.0.1", port, host_request)
        friend = None
        try:
            host.start()
            room_code = None
            deadline = asyncio.get_running_loop().time() + 3.0
            while room_code is None and asyncio.get_running_loop().time() < deadline:
                for message in host.poll():
                    if message.get("type") == "room_created":
                        room_code = message["room_code"]
                    elif message.get("type") == "error":
                        self.fail(message.get("message", "room creation failed"))
                await asyncio.sleep(0.01)
            self.assertIsNotNone(room_code, "timed out waiting for a friend room")

            friend_request = request("friend")
            friend_request["type"] = "join_room"
            friend_request["room_code"] = room_code
            friend = MatchmakingClient("127.0.0.1", port, friend_request)
            friend.start()
            matched = {host.player_id: None, friend.player_id: None}
            deadline = asyncio.get_running_loop().time() + 3.0
            while asyncio.get_running_loop().time() < deadline and any(value is None for value in matched.values()):
                for client in (host, friend):
                    for message in client.poll():
                        if message.get("type") == "matched":
                            matched[client.player_id] = message
                        elif message.get("type") == "error":
                            self.fail(message.get("message", "room join failed"))
                await asyncio.sleep(0.01)
            self.assertIsNotNone(matched["host"])
            self.assertIsNotNone(matched["friend"])
            self.assertEqual(matched["host"], matched["friend"])
        finally:
            host.close()
            if friend is not None:
                friend.close()
            await matchmaking.close()

    async def test_clients_match_and_receive_relayed_inputs(self):
        matchmaking = MatchmakingServer()
        server = await matchmaking.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        first = MatchmakingClient("127.0.0.1", port, request("alpha"))
        second = MatchmakingClient("127.0.0.1", port, request("bravo"))
        first.start()
        second.start()
        try:
            matched = {first.player_id: None, second.player_id: None}
            deadline = asyncio.get_running_loop().time() + 3.0
            while asyncio.get_running_loop().time() < deadline and any(value is None for value in matched.values()):
                for client in (first, second):
                    for message in client.poll():
                        if message.get("type") == "matched":
                            matched[client.player_id] = message
                        elif message.get("type") == "error":
                            self.fail(message.get("message", "client connection failed"))
                await asyncio.sleep(0.01)
            self.assertIsNotNone(matched["alpha"])
            self.assertIsNotNone(matched["bravo"])
            self.assertEqual(matched["alpha"], matched["bravo"])

            first.send_input(idle_action(move_x=0.25, trigger=True))
            received = False
            deadline = asyncio.get_running_loop().time() + 3.0
            while asyncio.get_running_loop().time() < deadline and not received:
                for message in first.poll() + second.poll():
                    if message.get("type") == "tick":
                        alpha = next(item for item in message["inputs"] if item["player_id"] == "alpha")
                        if alpha["action"]["move_x"] == 0.25:
                            self.assertTrue(alpha["action"]["trigger"])
                            received = True
                            break
                await asyncio.sleep(0.01)
            self.assertTrue(received, "timed out waiting for the relayed player input")
        finally:
            first.close()
            second.close()
            await matchmaking.close()


if __name__ == "__main__":
    unittest.main()
