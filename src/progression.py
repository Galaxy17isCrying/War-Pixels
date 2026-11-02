import random
import zlib

from .config import weapon_list

RANK_TIERS = (
    ("Bronze I", 0),
    ("Bronze II", 35),
    ("Bronze III", 70),
    ("Silver I", 100),
    ("Silver II", 135),
    ("Silver III", 170),
    ("Gold I", 200),
    ("Gold II", 250),
    ("Gold III", 300),
    ("Platinum I", 350),
    ("Platinum II", 400),
    ("Platinum III", 450),
    ("Diamond I", 500),
    ("Diamond II", 560),
    ("Diamond III", 630),
    ("Master I", 700),
    ("Master II", 760),
    ("Master III", 830),
    ("Legendary", 900),
    ("Legendary II", 1000),
    ("Legendary III", 1100),
    ("Mythic", 1200),
    ("Mythic II", 1500),
    ("Mythic III", 1800),
    ("Mythic IV", 2200),
    ("Mythic V", 2700),
)
RANKED_WIN_POINTS = 25
RANKED_LOSS_POINTS = 15
CRATE_LEVEL_INTERVAL = 5
LEVEL_WEAPON_REWARDS = {2: "cyclone", 4: "rift", 6: "monarch", 8: "solstice"}
WEAPON_RARITIES = {
    "hawk": "RARE",
    "rattler": "RARE",
    "arbiter": "RARE",
    "magnum": "RARE",
    "falcon": "EPIC",
    "bulwark": "EPIC",
    "hammer": "EPIC",
    "viper": "LEGENDARY",
    "longbow": "LEGENDARY",
    "solstice": "LEGENDARY",
}
RARITY_COLORS = {
    "COMMON": (190, 195, 190),
    "UNCOMMON": (105, 210, 120),
    "RARE": (90, 160, 255),
    "EPIC": (190, 105, 245),
    "LEGENDARY": (255, 170, 40),
}
CRATE_RARITY_WEIGHTS = (("COMMON", 60), ("UNCOMMON", 25), ("RARE", 10), ("EPIC", 4), ("LEGENDARY", 1))
SKIN_PREFIXES = ("Gilded", "Neon", "Phantom", "Solar", "Frost", "Carbon", "Tempest", "Verdant")
FIREARM_CATEGORIES = ("AR", "SMG", "LMG", "SG", "MARKSMAN", "SNIPER", "PISTOL")
SKIN_RARITY_COUNTS = (("COMMON", 38), ("UNCOMMON", 25), ("RARE", 18), ("EPIC", 9), ("LEGENDARY", 10))
SKIN_DESIGN_PREFIXES = ("Ashen", "Aurora", "Blackout", "Celestial", "Crimson", "Dusk", "Ember", "Frost",
                        "Gilded", "Hollow")
SKIN_DESIGN_SUFFIXES = ("Bastion", "Circuit", "Crown", "Drift", "Echo", "Fang", "Flare", "Horizon",
                        "Mirage", "Revenant")
LEGENDARY_SKIN_NAMES = (
    "Astral Sovereign", "Infernal Wyrm", "Prismatic Tempest", "Frostbound Nova", "Void Reaver",
    "Solar Devourer", "Verdant Leviathan", "Quantum Phantom", "Eclipse Engine", "Starlight Armada",
)
LEGENDARY_SKIN_EFFECTS = (
    "astral_sovereign", "infernal_wyrm", "prismatic_tempest", "frostbound_nova", "void_reaver",
    "solar_devourer", "verdant_leviathan", "quantum_phantom", "eclipse_engine", "starlight_armada",
)
AVATAR_FRAMES = (
    dict(id="rookie_ring", name="ROOKIE RING", rarity="COMMON", source="FREE", price=0, animation="static"),
    dict(id="field_visor", name="FIELD VISOR", rarity="COMMON", source="FREE", price=0, animation="static"),
    dict(id="olive_badge", name="OLIVE BADGE", rarity="UNCOMMON", source="FREE", price=0, animation="pulse"),
    dict(id="emerald_pulse", name="EMERALD PULSE", rarity="UNCOMMON", source="COINS", price=500, animation="pulse"),
    dict(id="blue_sentinel", name="BLUE SENTINEL", rarity="RARE", source="COINS", price=750, animation="orbit"),
    dict(id="arctic_circuit", name="ARCTIC CIRCUIT", rarity="RARE", source="COINS", price=900, animation="orbit"),
    dict(id="violet_rift", name="VIOLET RIFT", rarity="EPIC", source="COINS", price=1200, animation="orbit"),
    dict(id="solar_crown", name="SOLAR CROWN", rarity="EPIC", source="COINS", price=1500, animation="orbit"),
    dict(id="crate_comet", name="CRATE COMET", rarity="RARE", source="CRATE", price=0, animation="orbit"),
    dict(id="crate_phantom", name="CRATE PHANTOM", rarity="EPIC", source="CRATE", price=0, animation="orbit"),
    dict(id="dragon_aura", name="DRAGON AURA", rarity="LEGENDARY", source="CRATE", price=0, animation="dragon",
         color=(255, 92, 48)),
    dict(id="mythic_nova", name="MYTHIC NOVA", rarity="LEGENDARY", source="CRATE", price=0, animation="nova",
         color=(105, 195, 255)),
    dict(id="stellar_crown", name="STELLAR CROWN", rarity="LEGENDARY", source="COINS", price=3000,
         animation="constellation", color=(95, 205, 255)),
    dict(id="void_serpent", name="VOID SERPENT", rarity="LEGENDARY", source="COINS", price=3500,
         animation="dragon", color=(190, 105, 255)),
    dict(id="solar_phoenix", name="SOLAR PHOENIX", rarity="LEGENDARY", source="COINS", price=4000,
         animation="solar_flare", color=(255, 146, 55)),
    dict(id="nebula_rift", name="NEBULA RIFT", rarity="LEGENDARY", source="COINS", price=4500,
         animation="nebula", color=(175, 115, 255)),
    dict(id="tidal_orbit", name="TIDAL ORBIT", rarity="LEGENDARY", source="COINS", price=5000,
         animation="orbit", color=(65, 200, 220)),
    dict(id="prismatic_guard", name="PRISMATIC GUARD", rarity="LEGENDARY", source="COINS", price=5500,
         animation="prism", color=(255, 110, 195)),
    dict(id="frost_comet", name="FROST COMET", rarity="LEGENDARY", source="COINS", price=6000,
         animation="comet", color=(135, 220, 255)),
    dict(id="eclipse_king", name="ECLIPSE KING", rarity="LEGENDARY", source="COINS", price=6500,
         animation="eclipse", color=(195, 155, 255)),
    dict(id="aurora_guardian", name="AURORA GUARDIAN", rarity="LEGENDARY", source="COINS", price=7000,
         animation="aurora", color=(105, 255, 205)),
    dict(id="celestial_empress", name="CELESTIAL EMPRESS", rarity="LEGENDARY", source="COINS", price=7500,
         animation="nova", color=(255, 210, 115)),
)
CALLING_CARDS = (
    dict(id="frontline_veteran", name="FRONTLINE VETERAN", rarity="COMMON", source="FREE", price=0,
         color=(38, 112, 124), accent=(255, 170, 40), subtitle="OPERATIVE  /  EST. SEASON 01"),
    dict(id="neon_vanguard", name="NEON VANGUARD", rarity="RARE", source="COINS", price=1200,
         color=(24, 76, 130), accent=(80, 220, 230), subtitle="MOVE FAST  /  HOLD THE LINE"),
    dict(id="stormfront_ace", name="STORMFRONT ACE", rarity="EPIC", source="COINS", price=2200,
         color=(87, 47, 130), accent=(240, 110, 190), subtitle="NO SIGNAL  /  NO MERCY"),
    dict(id="eclipse_commander", name="ECLIPSE COMMANDER", rarity="LEGENDARY", source="COINS", price=4000,
         color=(92, 48, 28), accent=(255, 205, 90), subtitle="TACTICAL AUTHORITY"),
)


def _skin_designs():
    rarity_by_index = []
    for rarity, count in SKIN_RARITY_COUNTS:
        rarity_by_index.extend([rarity] * count)
    designs = []
    for i, (prefix, suffix) in enumerate(
            (prefix, suffix) for prefix in SKIN_DESIGN_PREFIXES for suffix in SKIN_DESIGN_SUFFIXES):
        name = LEGENDARY_SKIN_NAMES[i - 90] if i >= 90 else f"{prefix} {suffix}"
        design = dict(id=f"design_{i + 1:03}", name=name, rarity=rarity_by_index[i])
        if i >= 90:
            design["kill_effect"] = LEGENDARY_SKIN_EFFECTS[i - 90]
        designs.append(design)
    return tuple(designs)


SKIN_DESIGNS = _skin_designs()


def weapon_rarity(weapon):
    return weapon.get("rarity", WEAPON_RARITIES.get(weapon["id"], "COMMON"))


def rank_for_points(points):
    tier, minimum = RANK_TIERS[0]
    next_minimum = None
    for i, (candidate, threshold) in enumerate(RANK_TIERS):
        if points < threshold:
            break
        tier, minimum = candidate, threshold
        next_minimum = RANK_TIERS[i + 1][1] if i + 1 < len(RANK_TIERS) else None
    return dict(tier=tier, points=points, floor=minimum, next=next_minimum)


def random_skin_name(weapon_name, rarity, rng=None):
    rng = rng or random.SystemRandom()
    return f"{rng.choice(SKIN_PREFIXES)} {weapon_name} {rarity.title()}"


def legendary_weapon_ids():
    return {w["id"] for w in weapon_list() if weapon_rarity(w) == "LEGENDARY"}


def legendary_skin_name(weapon_name, design_name):
    return f"{weapon_name} - {design_name.upper()}"


def legendary_skin_effect(name, skin_id=None):
    normalized = name.casefold()
    known_effect = next((design["kill_effect"] for design in SKIN_DESIGNS
                         if design["rarity"] == "LEGENDARY" and design["name"].casefold() in normalized), None)
    if known_effect:
        effect = known_effect
    else:
        effect = LEGENDARY_SKIN_EFFECTS[zlib.crc32(normalized.encode("utf-8")) % len(LEGENDARY_SKIN_EFFECTS)]
    return f"{effect}__{skin_id}" if skin_id else effect


STORE_SKIN_PRICES = {"COMMON": 100, "UNCOMMON": 250, "RARE": 500, "EPIC": 1000, "LEGENDARY": 2500}


def avatar_frame(frame_id):
    return next(frame for frame in AVATAR_FRAMES if frame["id"] == frame_id)


def calling_card(card_id):
    return next(card for card in CALLING_CARDS if card["id"] == card_id)
