import asyncio
import unittest

from server.matchmaking_server import (
    MAX_LINE_BYTES,
    MatchmakingServer,
    ProtocolError,
    encode_message,
    read_message,
    validate_action,
    validate_queue_message,
)


def queue_message(player_id):
    return {
        "type": "queue",
        "mode_id": "snd",
        "map_id": "depot_09",
        "team_size": 5,
        "profile": {
            "player_id": player_id,
            "name": player_id,
            "char": "vanguard",
            "primary": "vanguard",
            "secondary": "p9",
            "equipment": "none",
        },
    }


def action(**overrides):
    result = {
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
    result.update(overrides)
    return result


class ValidatorTests(unittest.TestCase):
    def test_queue_request_is_copied_and_validated(self):
        message = queue_message("player-1")
        clean = validate_queue_message(message)
        self.assertEqual(clean, message)
        self.assertIsNot(clean["profile"], message["profile"])

    def test_queue_rejects_bool_team_size_and_extra_profile_fields(self):
        request = queue_message("player-1")
        request["team_size"] = True
        with self.assertRaises(ProtocolError):
            validate_queue_message(request)
        request = queue_message("player-1")
        request["profile"]["rank"] = "gold"
        with self.assertRaises(ProtocolError):
            validate_queue_message(request)

    def test_action_accepts_exact_client_payload(self):
        payload = action(
            move_x=0.5,
            move_y=-1.0,
            aim=1.25,
            trigger=True,
            ads=True,
            sprint=True,
            interact=True,
            reload=True,
            ability=True,
            swap_to=1,
        )
        self.assertEqual(validate_action(payload), payload)

    def test_action_rejects_out_of_range_values_and_wrong_field_types(self):
        with self.assertRaises(ProtocolError):
            validate_action(action(move_x=1.01))
        with self.assertRaises(ProtocolError):
            validate_action(action(aim=float("inf")))
        with self.assertRaises(ProtocolError):
            validate_action(action(aim=10**10000))
        with self.assertRaises(ProtocolError):
            validate_action(action(trigger=1))
        with self.assertRaises(ProtocolError):
            validate_action(action(swap_to=True))
        with self.assertRaises(ProtocolError):
            validate_action({"move_x": 0.0})


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_line_codec_and_size_limit(self):
        encoded = encode_message({"type": "ok", "text": "café"})
        reader = asyncio.StreamReader()
        reader.feed_data(encoded)
        reader.feed_eof()
        self.assertEqual(await read_message(reader), {"type": "ok", "text": "café"})
        with self.assertRaises(ProtocolError):
            encode_message({"payload": "x" * MAX_LINE_BYTES})

    async def test_match_and_tick_edge_lifetime_and_disconnect(self):
        matchmaking = MatchmakingServer()
        server = await matchmaking.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        first = second = None
        try:
            first = await asyncio.open_connection("127.0.0.1", port)
            second = await asyncio.open_connection("127.0.0.1", port)
            r1, w1 = first
            r2, w2 = second
            w1.write(encode_message(queue_message("one")))
            w2.write(encode_message(queue_message("two")))
            await asyncio.gather(w1.drain(), w2.drain())
            m1, m2 = await asyncio.gather(read_message(r1), read_message(r2))
            if m1["type"] == "queued":
                m1 = await read_message(r1)
            if m2["type"] == "queued":
                m2 = await read_message(r2)
            self.assertEqual(m1["type"], "matched")
            self.assertEqual(m1, m2)
            self.assertEqual([p["team"] for p in m1["players"]], [0, 1])

            w1.write(encode_message({
                "type": "input",
                "action": action(
                    move_x=0.5, trigger=True, ads=True, sprint=True, interact=True,
                    reload=True, ability=True, swap_to=1,
                ),
            }))
            await w1.drain()
            t1, t2 = await asyncio.gather(read_message(r1), read_message(r2))
            self.assertEqual(t1, t2)
            self.assertEqual(t1["tick"], 0)
            expected = action(
                move_x=0.5, trigger=True, ads=True, sprint=True, interact=True,
                reload=True, ability=True, swap_to=1,
            )
            self.assertEqual(t1["inputs"][0]["action"], expected)
            self.assertEqual(t1["inputs"][1]["action"], action())

            w1.write(encode_message({
                "type": "input",
                "action": action(
                    move_x=0.5, trigger=True, ads=True, sprint=True, interact=True,
                    reload=True, ability=True, swap_to=1,
                ),
            }))
            await w1.drain()
            t1, t2 = await asyncio.gather(read_message(r1), read_message(r2))
            self.assertEqual(t1, t2)
            self.assertEqual(
                t1["inputs"][0]["action"],
                action(
                    move_x=0.5,
                    trigger=True,
                    ads=True,
                    sprint=True,
                    interact=True,
                ),
            )

            w1.write(encode_message({"type": "input", "action": action()}))
            w1.write(encode_message({
                "type": "input",
                "action": action(reload=True, ability=True, swap_to=1),
            }))
            await w1.drain()
            t1, t2 = await asyncio.gather(read_message(r1), read_message(r2))
            self.assertEqual(t1, t2)
            self.assertTrue(t1["inputs"][0]["action"]["reload"])
            self.assertTrue(t1["inputs"][0]["action"]["ability"])
            self.assertEqual(t1["inputs"][0]["action"]["swap_to"], 1)

            w1.close()
            await w1.wait_closed()
            self.assertEqual(await asyncio.wait_for(read_message(r2), 1), {"type": "disconnected"})
        finally:
            for pair in (first, second):
                if pair:
                    pair[1].close()
            await matchmaking.close()


if __name__ == "__main__":
    unittest.main()
