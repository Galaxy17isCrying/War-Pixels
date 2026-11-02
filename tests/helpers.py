import math
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("OVERHEAD_OPS_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.match import Match  # noqa: E402


def quiet_match(map_id="depot_09", mode="ctf", **kw):
    m = Match(map_id, mode, "NORMAL", seed=1, all_bots=True, **kw)
    for c in m.combatants:
        c.alive = False
        c.respawn_t = 0.0
    return m


def place(m, c, tx, ty, team=None):
    c.alive = True
    c.hp = float(c.maxhp)
    c.invuln = 0.0
    c.x, c.y = m.map.center(tx, ty)
    c.vx = c.vy = 0.0
    if team is not None:
        c.team = team
    return c
