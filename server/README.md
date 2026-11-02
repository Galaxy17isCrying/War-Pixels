# Matchmaking and input relay server

Run with Python 3.10 or later and no third-party packages:

```console
python -m server --host 0.0.0.0 --port 8765
```

Clients connect over TCP and send one newline-delimited JSON `queue` request
first. Requests are paired only when `mode_id`, `map_id`, and `team_size` all
match exactly. The returned `players` list has one profile per connected client,
assigned to teams 0 and 1 respectively; `team_size` is match metadata.
The game currently queues Search and Destroy on Depot 09 and fills the remaining
team slots with bots.

After matching, clients send newline-delimited
`{"type":"input","action":{...}}` messages. `action` must contain exactly
`move_x`, `move_y`, `aim`, `trigger`, `ads`, `sprint`, `interact`, `reload`,
`ability`, and `swap_to`. Movement values are finite numbers from -1 to 1;
`aim` is a finite radians value; the controls are booleans; `swap_to` is null,
0, or 1. Movement, aim, and trigger/ads/sprint/interact remain held across
ticks until updated. `reload`, `ability`, and non-null `swap_to` are one-shot:
they are carried into one tick and reset. Every 50 ms, both clients receive the
same tick number and ordered input snapshot. A disconnected peer receives
`{"type":"disconnected"}` when possible. Lines are limited to 16 KiB. Invalid
input is rejected and the connection is closed. The server does not require or
connect to MySQL.
