"""Regenerates data/weapons.json and data/characters.json. Edit numbers here or edit the JSON directly."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data"

BASE = dict(hs=1.6, limb=0.75, reserve=100, speed=1700, falloff=0.5, hip=4.0, aim=1.0, vrec=1.0, hrec=0.5,
            recover=9.0, movepen=3.0, swap=0.5, auto=True, pellets=1, move=0.95, noise=800, zoom=1.1)

def W(id, name, cat, **kw):
    d = dict(BASE); d.update(kw); d.update(id=id, name=name, cat=cat)
    return d

weapons = [
    W("longbow", "LONGBOW", "SNIPER", dmg=115, hs=2.0, rate=42, mag=5, reserve=20, reload=3.4, speed=3000, range=1500, falloff=.9, hip=7, aim=.12, vrec=7, hrec=1.2, recover=3.5, movepen=6, swap=1.0, auto=False, move=.86, noise=1200, zoom=1.7),
    W("viper", "VIPER-X", "SNIPER", dmg=95, hs=2.0, rate=55, mag=6, reserve=24, reload=3.0, speed=2900, range=1350, falloff=.9, hip=7, aim=.15, vrec=5.5, hrec=1.0, recover=4, movepen=6, swap=.9, auto=False, move=.88, noise=1150, zoom=1.6),
    W("sentinel", "SENTINEL", "SNIPER", dmg=80, hs=1.9, rate=75, mag=8, reserve=32, reload=2.8, speed=2800, range=1200, falloff=.85, hip=6.5, aim=.2, vrec=4, hrec=.9, recover=5, movepen=5, swap=.8, auto=False, move=.9, noise=1100, zoom=1.5),
    W("arbiter", "ARBITER DMR", "MARKSMAN", dmg=46, hs=1.8, rate=230, mag=10, reserve=50, reload=2.4, speed=2200, range=950, falloff=.7, hip=4.5, aim=.35, vrec=2.4, hrec=.8, recover=7, movepen=3, swap=.55, auto=False, move=.95, noise=850, zoom=1.3),
    W("lancer", "LANCER", "MARKSMAN", dmg=55, hs=1.8, rate=180, mag=8, reserve=40, reload=2.6, speed=2300, range=1050, falloff=.7, hip=4.8, aim=.3, vrec=3, hrec=.9, recover=6.5, movepen=3.5, swap=.6, auto=False, move=.93, noise=900, zoom=1.35),
    W("falcon", "FALCON", "MARKSMAN", dmg=40, hs=1.7, rate=300, mag=12, reserve=60, reload=2.3, speed=2100, range=850, falloff=.65, hip=4.2, aim=.45, vrec=2, hrec=.7, recover=8, movepen=2.5, swap=.5, auto=False, move=.96, noise=800, zoom=1.25),
    W("vanguard", "AR-7 VANGUARD", "AR", dmg=25, rate=620, mag=30, reserve=120, reload=2.2, range=700, falloff=.55, hip=4, aim=1.0, vrec=.9, hrec=.55, recover=9, movepen=3.5, move=.93),
    W("hawk", "HAWK AR", "AR", dmg=30, rate=520, mag=25, reserve=100, reload=2.4, range=760, falloff=.6, hip=3.8, aim=.8, vrec=1.0, hrec=.45, recover=9, movepen=3.5, move=.92),
    W("reaper", "REAPER AR", "AR", dmg=22, rate=760, mag=35, reserve=140, reload=2.1, range=620, falloff=.5, hip=4.4, aim=1.2, vrec=.8, hrec=.75, recover=10, movepen=3, move=.94),
    W("spitfire", "SPITFIRE", "SMG", dmg=16, hs=1.5, rate=900, mag=32, reserve=128, reload=1.8, speed=1500, range=420, falloff=.4, hip=3.5, aim=1.6, vrec=.6, hrec=.5, recover=12, movepen=1.5, swap=.35, move=1.0, noise=600, zoom=1.0),
    W("wasp", "WASP", "SMG", dmg=15, hs=1.5, rate=1050, mag=28, reserve=140, reload=1.7, speed=1500, range=380, falloff=.4, hip=4, aim=1.9, vrec=.5, hrec=.8, recover=12, movepen=1.2, swap=.3, move=1.02, noise=600, zoom=1.0),
    W("rattler", "RATTLER", "SMG", dmg=18, hs=1.5, rate=800, mag=40, reserve=120, reload=2.1, speed=1550, range=450, falloff=.45, hip=3.4, aim=1.4, vrec=.65, hrec=.4, recover=11, movepen=1.8, swap=.4, move=.99, noise=620, zoom=1.0),
    W("anvil", "ANVIL LMG", "LMG", dmg=27, rate=650, mag=100, reserve=200, reload=5.2, range=760, falloff=.55, hip=5, aim=1.4, vrec=.7, hrec=.6, recover=5, movepen=5, swap=.9, move=.8, noise=950, zoom=1.1),
    W("bulwark", "BULWARK", "LMG", dmg=31, rate=560, mag=75, reserve=150, reload=4.8, range=800, falloff=.6, hip=4.8, aim=1.2, vrec=.9, hrec=.5, recover=5.5, movepen=5, swap=.85, move=.82, noise=950, zoom=1.15),
    W("hailstorm", "HAILSTORM", "LMG", dmg=23, rate=780, mag=120, reserve=240, reload=5.8, range=700, falloff=.5, hip=5.4, aim=1.7, vrec=.65, hrec=.85, recover=4.5, movepen=5.5, swap=1.0, move=.78, noise=1000, zoom=1.05),
    W("breaker", "BREAKER", "SG", dmg=11, hs=1.3, rate=70, mag=6, reserve=30, reload=3.0, speed=1300, range=260, falloff=.12, hip=7, aim=5, vrec=6, hrec=1, recover=5, movepen=2, swap=.6, auto=False, pellets=8, move=.95, noise=900, zoom=1.0),
    W("scatter", "SCATTER", "SG", dmg=9, hs=1.3, rate=95, mag=8, reserve=40, reload=3.4, speed=1300, range=240, falloff=.1, hip=8, aim=6.5, vrec=5, hrec=1, recover=5, movepen=2, swap=.55, auto=False, pellets=10, move=.96, noise=900, zoom=1.0),
    W("hammer", "HAMMER", "SG", dmg=17, hs=1.3, rate=55, mag=4, reserve=24, reload=3.2, speed=1400, range=300, falloff=.15, hip=6, aim=4.2, vrec=7, hrec=1.2, recover=4.5, movepen=2, swap=.7, auto=False, pellets=6, move=.93, noise=950, zoom=1.0),
    W("p9", "P9 SIDEARM", "PISTOL", dmg=22, hs=1.7, rate=420, mag=15, reserve=60, reload=1.5, speed=1500, range=400, falloff=.5, hip=3, aim=1.8, vrec=1.5, hrec=.5, recover=10, movepen=1, swap=.3, auto=False, move=1.0, noise=500, zoom=1.0),
    W("magnum", "MAGNUM .50", "PISTOL", dmg=56, hs=1.8, rate=140, mag=6, reserve=30, reload=2.4, speed=1800, range=560, falloff=.6, hip=4, aim=1.2, vrec=4, hrec=1.2, recover=6, movepen=2, swap=.4, auto=False, move=.98, noise=800, zoom=1.0),
    W("stinger", "STINGER MP", "PISTOL", dmg=13, hs=1.5, rate=850, mag=20, reserve=80, reload=1.6, speed=1400, range=300, falloff=.4, hip=4.5, aim=3, vrec=.8, hrec=1.0, recover=11, movepen=1, swap=.3, auto=True, move=1.0, noise=550, zoom=1.0),
    W("compact", "COMPACT-12", "PISTOL", dmg=20, hs=1.6, rate=480, mag=12, reserve=72, reload=1.4, speed=1500, range=380, falloff=.5, hip=3.4, aim=2, vrec=1.2, hrec=.5, recover=10, movepen=1, swap=.25, auto=False, move=1.0, noise=480, zoom=1.0),
    W("cyclone", "CYCLONE-28", "AR", dmg=28, rate=560, mag=28, reserve=120, reload=2.3, range=720, falloff=.55, hip=3.8, aim=.9, vrec=.9, hrec=.55, recover=9, movepen=3.2, move=.95, rarity="RARE"),
    W("rift", "RIFT-9", "SMG", dmg=16, hs=1.5, rate=980, mag=34, reserve=135, reload=1.75, speed=1550, range=430, falloff=.45, hip=3.6, aim=1.5, vrec=.6, hrec=.55, recover=11, movepen=1.4, swap=.32, move=1.01, noise=610, zoom=1.0, rarity="EPIC"),
    W("monarch", "MONARCH DMR", "MARKSMAN", dmg=50, hs=1.8, rate=205, mag=10, reserve=48, reload=2.45, speed=2250, range=980, falloff=.68, hip=4.4, aim=.34, vrec=2.5, hrec=.75, recover=7.2, movepen=3, swap=.56, auto=False, move=.94, noise=860, zoom=1.3, rarity="EPIC"),
    W("solstice", "SOLSTICE-100", "SNIPER", dmg=100, hs=2.0, rate=58, mag=6, reserve=24, reload=3.1, speed=2900, range=1400, falloff=.88, hip=6.8, aim=.14, vrec=5.2, hrec=1.0, recover=4.2, movepen=5.8, swap=.85, auto=False, move=.89, noise=1150, zoom=1.55, rarity="LEGENDARY"),
]

NEW_GUNS = {
    "AR": [
        ("aegis", "AEGIS-14"), ("boreal", "BOREAL-5"), ("cinder", "CINDER-6"), ("driftwood", "DRIFTWOOD"),
        ("echelon", "ECHELON-3"), ("flare", "FLARE-9"), ("granite", "GRANITE - IRONBLOOM"),
        ("helix", "HELIX-11 - STORMCROWN"),
        ("ion", "ION-4"), ("keystone", "KEYSTONE"),
    ],
    "SMG": [
        ("lumen", "LUMEN-8"), ("mistral", "MISTRAL"), ("needle", "NEEDLE-5"), ("orbit", "ORBIT-9"),
        ("pulse", "PULSE-7"), ("quartz", "QUARTZ"), ("riptide", "RIPTIDE - ABYSSAL"),
        ("sirocco", "SIROCCO-2 - SUNFANG"),
        ("tremor", "TREMOR"), ("umbra", "UMBRA-6"),
    ],
    "LMG": [
        ("vulcan", "VULCAN-90"), ("warden", "WARDEN"), ("xenon", "XENON-8"), ("yukon", "YUKON"),
        ("zephyr_lmg", "ZEPHYR-40"), ("atlas", "ATLAS-120"), ("brimstone", "BRIMSTONE - ASHEN KING"),
        ("crag", "CRAG-7 - IRON TEMPEST"),
        ("dynamo", "DYNAMO"), ("everest", "EVEREST"),
    ],
    "SG": [
        ("furnace", "FURNACE"), ("gale", "GALE-12"), ("harbor", "HARBOR"), ("ingress", "INGRESS-8"),
        ("javelin", "JAVELIN"), ("kiln", "KILN-4"), ("lodestar", "LODESTAR - STARFALL"),
        ("mammoth", "MAMMOTH - FROSTBITE"),
        ("nova_sg", "NOVA-6"), ("outpost", "OUTPOST"),
    ],
    "MARKSMAN": [
        ("parallax", "PARALLAX"), ("quarry", "QUARRY-11"), ("rail", "RAIL-3"), ("solace", "SOLACE"),
        ("talisman", "TALISMAN"), ("undertow", "UNDERTOW-7"), ("vector", "VECTOR DMR"), ("wayfinder", "WAYFINDER"),
        ("xiphos", "XIPHOS - OATHBREAKER"), ("yield", "YIELD-9 - WRAITHMARK"),
    ],
    "SNIPER": [
        ("zenith", "ZENITH-50"), ("apogee", "APOGEE"), ("bastion_s", "BASTION-12"), ("comet", "COMET-8"),
        ("deadfall", "DEADFALL"), ("eclipse", "ECLIPSE-4"), ("farpoint", "FARPOINT - DEAD ORBIT"),
        ("glacier", "GLACIER-7 - BLUE VEIL"),
        ("highland", "HIGHLAND"), ("ironsight", "IRONSIGHT-3"),
    ],
    "PISTOL": [
        ("jolt", "JOLT-9"), ("knell", "KNELL"), ("lark", "LARK-22"), ("morrow", "MORROW-6"),
        ("nimbus", "NIMBUS"),         ("onyx_p", "ONYX-5"), ("pioneer", "PIONEER-10 - GOLDEN HOUR"), ("quill_p", "QUILL-8 - NIGHTBLOOM"),
        ("relay", "RELAY-3"), ("sable_p", "SABLE-12"),
    ],
}

RARITY_BY_INDEX = ("COMMON", "UNCOMMON", "RARE", "RARE", "EPIC", "EPIC",
                   "LEGENDARY", "LEGENDARY", "UNCOMMON", "RARE")
CATEGORY_STATS = {
    "AR": dict(dmg=25, rate=600, mag=30, reserve=120, reload=2.2, speed=1750, range=700, falloff=.55,
               hip=4.0, aim=1.0, vrec=.9, hrec=.55, recover=9, movepen=3.5, move=.94, noise=800, zoom=1.1),
    "SMG": dict(dmg=16, hs=1.5, rate=900, mag=32, reserve=128, reload=1.8, speed=1500, range=420, falloff=.4,
                hip=3.5, aim=1.6, vrec=.6, hrec=.5, recover=12, movepen=1.5, swap=.35, move=1.0, noise=600, zoom=1.0),
    "LMG": dict(dmg=26, rate=650, mag=90, reserve=180, reload=5.0, speed=1700, range=740, falloff=.52,
                hip=5.0, aim=1.4, vrec=.8, hrec=.65, recover=5, movepen=5, swap=.9, move=.8, noise=950, zoom=1.1),
    "SG": dict(dmg=11, hs=1.3, rate=75, mag=7, reserve=35, reload=3.1, speed=1300, range=250, falloff=.12,
               hip=7, aim=5, vrec=6, hrec=1, recover=5, movepen=2, swap=.6, auto=False, pellets=8, move=.95, noise=900, zoom=1.0),
    "MARKSMAN": dict(dmg=47, hs=1.8, rate=220, mag=10, reserve=50, reload=2.4, speed=2200, range=950, falloff=.7,
                     hip=4.5, aim=.35, vrec=2.4, hrec=.8, recover=7, movepen=3, swap=.55, auto=False, move=.95, noise=850, zoom=1.3),
    "SNIPER": dict(dmg=95, hs=2.0, rate=55, mag=6, reserve=24, reload=3.0, speed=2900, range=1350, falloff=.9,
                   hip=7, aim=.15, vrec=5.5, hrec=1, recover=4, movepen=6, swap=.9, auto=False, move=.88, noise=1150, zoom=1.6),
    "PISTOL": dict(dmg=22, hs=1.7, rate=420, mag=15, reserve=60, reload=1.5, speed=1500, range=400, falloff=.5,
                   hip=3, aim=1.8, vrec=1.5, hrec=.5, recover=10, movepen=1, swap=.3, auto=False, move=1.0, noise=500, zoom=1.0),
}

for category, entries in NEW_GUNS.items():
    for index, (weapon_id, name) in enumerate(entries):
        stats = dict(CATEGORY_STATS[category])
        stats["dmg"] = round(stats["dmg"] * (0.9 + (index % 4) * 0.07), 1)
        stats["rate"] = round(stats["rate"] * (0.92 + (index % 3) * 0.08))
        stats["mag"] = max(1, stats["mag"] + (index % 5 - 2) * (2 if category != "SG" else 1))
        stats["rarity"] = RARITY_BY_INDEX[index]
        stats["locked_by_default"] = stats["rarity"] in ("RARE", "EPIC", "LEGENDARY")
        weapons.append(W(weapon_id, name, category, **stats))

weapons.extend([
    W("holger_galactic_stars", "HOLGER - GALACTIC STARS", "LMG", dmg=42, hs=1.6, rate=1200, mag=300,
      reserve=1000, reload=6.0, speed=1850, range=820, falloff=.65, hip=0, aim=0, vrec=0,
      hrec=0, recover=0, movepen=0, swap=.8, auto=True, pellets=1, move=.78, noise=1100,
      zoom=1.1, rarity="LEGENDARY", locked_by_default=False, kill_effect="supernova"),
    W("m4_emberwyrm", "M4 - EMBERWYRM", "AR", dmg=27, rate=600, mag=30, reserve=120, reload=2.15,
      speed=1750, range=720, falloff=.57, hip=3.8, aim=.85, vrec=.85, hrec=.5, recover=9.5,
      movepen=3.2, move=.96, noise=820, zoom=1.1, aim_assist=.2, aim_assist_cone=.16,
      aim_assist_range=380, rarity="LEGENDARY", locked_by_default=False,
      kill_effect="dragon"),
    W("field_knife", "FIELD KNIFE", "MELEE", dmg=72, hs=1.0, rate=90, mag=99, reserve=0, reload=.1,
      speed=0, range=74, falloff=1.0, hip=0, aim=0, vrec=0, hrec=0, recover=100, movepen=0,
      swap=.15, auto=False, move=1.0, noise=0, zoom=1.0),
    W("breach_launcher", "BREACH LAUNCHER", "EXPLOSIVE", dmg=70, hs=1.0, rate=48, mag=1, reserve=8,
      reload=2.8, speed=900, range=650, falloff=.8, hip=3.5, aim=1.2, vrec=2.0, hrec=.6,
      recover=5, movepen=2, swap=.65, auto=False, move=.88, noise=1000, zoom=1.0,
      blast_radius=105, blast_damage=78),
])

for spec in weapons:
    spec["kill_effect"] = {
        "viper": "void_rift",
        "longbow": "comet",
        "solstice": "ice_shatter",
    }.get(spec["id"], spec.get("kill_effect"))

def C(id, name, role, ai_role, hp, speed, ab, ab_name, cd, ab_desc, pa_name, pa_desc, mods, color, desc, strength, weakness, prefs):
    return dict(id=id, name=name, role=role, ai_role=ai_role, hp=hp, speed=speed,
                ability=dict(id=ab, name=ab_name, cooldown=cd, desc=ab_desc),
                passive=dict(name=pa_name, desc=pa_desc, mods=mods),
                color=color, desc=desc, strength=strength, weakness=weakness, prefs=prefs)

characters = [
    C("vanguard", "VANGUARD", "ASSAULT", "assault", 100, 1.0, "sprint", "COMBAT SPRINT", 14, "Surge forward at +60% speed for 3s.", "QUICK HANDS", "Weapon swaps 30% faster.", {"swap": .7}, [90, 130, 220], "Balanced front-line fighter.", "Flexible; strong at any range.", "No special utility.", ["AR", "LMG", "SMG"]),
    C("hawkeye", "HAWKEYE", "RECON", "flanker", 90, 1.05, "reveal", "SONAR PULSE", 20, "Reveals enemies within 380px for 4s.", "LOW PROFILE", "Enemies spot you from 40% less distance.", {"detect": .6}, [70, 200, 190], "Scout who finds targets and flanks.", "Information; hard to spot.", "Low health.", ["SMG", "MARKSMAN", "AR"]),
    C("doc", "DOC", "MEDIC", "support", 100, 1.0, "heal", "FIELD MEDKIT", 18, "Heals 40 HP to allies within 150px (and self).", "STEADY HANDS", "Healing is 50% more effective.", {"heal": 1.5}, [90, 200, 120], "Keeps the squad alive.", "Sustained team fights.", "Few offensive tools.", ["AR", "SMG"]),
    C("wrench", "WRENCH", "ENGINEER", "defender", 110, 1.0, "barrier", "DEPLOY BARRIER", 16, "Drops a barrier ahead for 12s.", "FAST HANDS", "Plant and defuse actions are 50% faster.", {"objective": 1.5}, [230, 180, 60], "Holds ground with deployable cover.", "Objective control.", "Barrier also blocks allies.", ["SG", "AR", "SMG"]),
    C("blast", "BLAST", "DEMOLITION", "assault", 120, .95, "grenade", "FRAG CHARGE", 20, "Throws an explosive (radius 95, up to 85 dmg).", "BLAST EXPERT", "Explosives deal 30% more damage.", {"explosive": 1.3}, [220, 110, 50], "Breaks up clustered enemies.", "Area damage; high health.", "Slower than average.", ["SG", "LMG", "AR"]),
    C("cache", "CACHE", "SUPPORT", "support", 105, .97, "ammo", "AMMO DROP", 22, "Refills ammo for allies within 140px (and self).", "DEEP POCKETS", "+50% reserve ammunition.", {"ammo": 1.5}, [180, 150, 90], "Keeps allies shooting.", "Sustained firepower.", "Average mobility.", ["LMG", "AR"]),
    C("longshot", "LONGSHOT", "MARKSMAN", "sniper", 95, 1.0, "steady", "STEADY AIM", 18, "Near-perfect accuracy and no recoil for 4s.", "STILL WATER", "Half the spread while standing still.", {"still": .5}, [150, 110, 200], "Precision at range.", "Dominates sightlines.", "Weak up close.", ["SNIPER", "MARKSMAN"]),
    C("phantom", "PHANTOM", "GHOST", "flanker", 85, 1.1, "cloak", "SHADOW VEIL", 24, "Only seen within 70px for 5s.", "HUSHED", "Gunfire is 60% quieter.", {"noise": .4}, [140, 140, 160], "Infiltrates and ambushes.", "Stealth and speed.", "Lowest health.", ["SMG", "MARKSMAN", "SG"]),
]

(OUT / "weapons.json").write_text(json.dumps(weapons, indent=1))
(OUT / "characters.json").write_text(json.dumps(characters, indent=1))
print(len(weapons), "weapons", len(characters), "characters")
