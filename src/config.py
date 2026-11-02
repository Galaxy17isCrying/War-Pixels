import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SAVE_DIR = Path(os.environ.get("OVERHEAD_OPS_HOME", str(Path.home() / ".overhead_ops")))

TILE = 32
CANVAS_W, CANVAS_H = 1280, 720
APP_TITLE = "War Pixels"
BODY_RADIUS = 12
TEAM_COLORS = {0: (74, 144, 255), 1: (238, 96, 58)}
TEAM_NAMES = {0: "ALPHA", 1: "BRAVO"}
CATEGORY_ORDER = ["AR", "SMG", "LMG", "SG", "MARKSMAN", "SNIPER"]
CATEGORY_LABEL = {"AR": "ASSAULT RIFLES", "SMG": "SUBMACHINE GUNS", "LMG": "LIGHT MACHINE GUNS",
                  "SG": "SHOTGUNS", "MARKSMAN": "MARKSMAN RIFLES", "SNIPER": "SNIPER RIFLES", "PISTOL": "PISTOLS"}
EQUIPMENT = {
    "none": ("NONE", "No equipment."),
    "armor": ("ARMOR VEST", "+20 health, 5% slower."),
    "ammo": ("EXTRA MAGS", "+30% reserve ammunition."),
    "boots": ("LIGHT BOOTS", "+5% speed, -10 health."),
}
BOT_NAMES = ["Rook", "Ember", "Nyx", "Tango", "Cobalt", "Vesper", "Flint", "Mako", "Zephyr", "Onyx", "Sable",
             "Quill", "Havoc", "Lynx", "Argent", "Bishop", "Drift", "Echo", "Fable", "Gamma", "Halo", "Iris",
             "Peter Griffin", "Gojo Satoru", "Rizzler", "Yuji Itadori", "Nino Nakano", "Miku Nakano",
             "Itsuki Nakano", "Yotsuba Nakano", "Ichika Nakano", "Fuutarou Uesugi", "Megumin",
             "Anya Forger", "Goku WiFi", "Shrek Main", "Amongus ඞ", "Toji Tax Collector",
             "Nah Id Win", "Domain Expansion", "Kono Dio Da", "Sukuna Finger", "Batman No Prep"]


@lru_cache(maxsize=None)
def _load(rel: str):
    return json.loads((DATA_DIR / rel).read_text(encoding="utf-8"))


def weapon_list():
    return _load("weapons.json")


def weapons():
    return {w["id"]: w for w in weapon_list()}


def characters():
    return _load("characters.json")


def character(cid: str):
    return next(c for c in characters() if c["id"] == cid)


def maps_meta():
    return _load("maps/meta.json")


def map_lines(filename: str):
    return (DATA_DIR / "maps" / filename).read_text(encoding="utf-8").splitlines()
