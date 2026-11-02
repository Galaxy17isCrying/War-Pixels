import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gamemap import GameMap
from src.pathfinding import find_path

def create_natural_border(w, h):
    grid = [["." for _ in range(w)] for _ in range(h)]
    # Natural rock jagged borders
    for x in range(w):
        grid[0][x] = "#"
        grid[h - 1][x] = "#"
    for y in range(h):
        grid[y][0] = "#"
        grid[y][w - 1] = "#"

    # Organic corner rock formations
    corner_rocks = [
        # Top-left corner
        (1, 1), (2, 1), (3, 1), (1, 2), (2, 2), (1, 3),
        # Top-right corner
        (w - 2, 1), (w - 3, 1), (w - 4, 1), (w - 2, 2), (w - 3, 2), (w - 2, 3),
        # Bottom-left corner
        (1, h - 2), (2, h - 2), (3, h - 2), (1, h - 3), (2, h - 3), (1, h - 4),
        # Bottom-right corner
        (w - 2, h - 2), (w - 3, h - 2), (w - 4, h - 2), (w - 2, h - 3), (w - 3, h - 3), (w - 2, h - 4),
    ]
    for x, y in corner_rocks:
        grid[y][x] = "#"

    # Organic jagged edge indentations (rock cliffs / trees)
    for x in (11, 12, 23, 24, 35, 36):
        grid[1][x] = "#"
        grid[h - 2][x] = "#"
    for y in (7, 8, 19, 20):
        grid[y][1] = "#"
        grid[y][w - 2] = "#"

    return grid

def generate_nuketown():
    w, h = 48, 28
    grid = create_natural_border(w, h)

    # West House (Green House)
    # Porch and main walls
    for y in range(7, 21):
        if y in (7, 13, 20):
            for x in range(8, 17):
                grid[y][x] = "#"
        else:
            grid[y][8] = "#"
            grid[y][16] = "#"
    # Doorways (wide 2-tile clearance)
    grid[10][16] = "."  # Front door to cul-de-sac
    grid[11][16] = "."
    grid[16][16] = "."  # Second front entrance
    grid[17][16] = "."
    grid[10][8] = "."   # Back door to backyard
    grid[11][8] = "."
    grid[16][8] = "."   # Second back door
    grid[17][8] = "."
    grid[13][11] = "."  # Interior hallway
    grid[13][12] = "."
    grid[13][13] = "."
    # West House Interior Furniture/Cover
    grid[9][12] = "c"
    grid[18][12] = "c"
    # Backyard Fence & Patio Cover
    grid[5][5] = "#"
    grid[5][6] = "c"
    grid[22][5] = "#"
    grid[22][6] = "c"

    # East House (Yellow House)
    for y in range(7, 21):
        if y in (7, 13, 20):
            for x in range(31, 40):
                grid[y][x] = "#"
        else:
            grid[y][31] = "#"
            grid[y][39] = "#"
    # Doorways (wide 2-tile clearance)
    grid[10][31] = "."  # Front door
    grid[11][31] = "."
    grid[16][31] = "."  # Second front entrance
    grid[17][31] = "."
    grid[10][39] = "."  # Back door
    grid[11][39] = "."
    grid[16][39] = "."  # Second back door
    grid[17][39] = "."
    grid[13][34] = "."  # Interior hallway
    grid[13][35] = "."
    grid[13][36] = "."
    # East House Interior Cover
    grid[9][35] = "c"
    grid[18][35] = "c"
    # Backyard Fence & Patio Cover
    grid[5][41] = "c"
    grid[5][42] = "#"
    grid[22][41] = "c"
    grid[22][42] = "#"

    # Central Cul-de-Sac Obstacles
    # Yellow School Bus (angled slightly, north-center)
    for x in range(21, 28):
        grid[10][x] = "#"
    grid[9][22] = "c"
    grid[9][26] = "c"
    grid[11][21] = "c"
    grid[11][27] = "c"

    # Blue Cargo Truck (angled south-center)
    for x in range(20, 27):
        grid[17][x] = "#"
    grid[18][21] = "c"
    grid[18][25] = "c"
    grid[16][20] = "c"
    grid[16][26] = "c"

    # Side-lane tactical obstacles (sandbags and crates)
    grid[4][23] = "c"
    grid[4][24] = "c"
    grid[23][23] = "c"
    grid[23][24] = "c"

    # Spawns: 10 spawns for team 0 (West Lawn)
    spawns_a = [(4, 9), (4, 11), (4, 13), (4, 15), (4, 17),
                (5, 10), (5, 12), (5, 14), (5, 16), (5, 18)]
    for x, y in spawns_a:
        grid[y][x] = "a"

    # Spawns: 10 spawns for team 1 (East Lawn)
    spawns_b = [(43, 9), (43, 11), (43, 13), (43, 15), (43, 17),
                (42, 10), (42, 12), (42, 14), (42, 16), (42, 18)]
    for x, y in spawns_b:
        grid[y][x] = "b"

    # Flags
    grid[14][3] = "P"
    grid[14][44] = "Q"

    # Bomb Sites
    grid[5][24] = "X"   # North garden lane
    grid[22][24] = "Y"  # South garden lane

    # Hardpoint Zones
    grid[14][24] = "h"  # Center Cul-de-sac between Bus & Truck
    grid[15][12] = "h"  # West House Living Room
    grid[15][35] = "h"  # East House Living Room

    return ["".join(row) for row in grid]

def generate_crash():
    w, h = 48, 28
    grid = create_natural_border(w, h)

    # 3-Story Damaged Building (North lane)
    for x in range(15, 27):
        grid[6][x] = "#"
        grid[11][x] = "#"
    for y in range(6, 12):
        grid[y][15] = "#"
        grid[y][26] = "#"
    # Doorways (wide 2-tile clearance)
    grid[11][20] = "."
    grid[11][21] = "."
    grid[8][15] = "."
    grid[9][15] = "."
    grid[8][26] = "."
    grid[9][26] = "."
    grid[8][19] = "c"

    # Pharmacy / South Building
    for x in range(21, 33):
        grid[17][x] = "#"
        grid[22][x] = "#"
    for y in range(17, 23):
        grid[y][21] = "#"
        grid[y][32] = "#"
    grid[17][26] = "."
    grid[17][27] = "."
    grid[20][21] = "."
    grid[21][21] = "."
    grid[20][32] = "."
    grid[21][32] = "."
    grid[19][25] = "c"
    grid[19][28] = "c"

    # Central Downed Helicopter Wreck (Center Plaza)
    # Fuselage and rotor hub
    for x in range(19, 25):
        grid[14][x] = "#"
    grid[13][21] = "c"
    grid[13][22] = "c"
    grid[15][21] = "c"
    grid[15][22] = "c"
    grid[14][26] = "c" # Tail rotor cover
    grid[14][17] = "c" # Nose cover

    # Alley Sandbag Barricades
    for y in (8, 9):
        grid[y][8] = "#"
        grid[y][39] = "#"
    for y in (19, 20):
        grid[y][8] = "#"
        grid[y][39] = "#"
    grid[14][9] = "c"
    grid[14][38] = "c"

    # Spawns: 10 spawns for team 0
    spawns_a = [(4, 10), (4, 12), (4, 14), (4, 16), (4, 18),
                (5, 11), (5, 13), (5, 15), (5, 17), (6, 14)]
    for x, y in spawns_a:
        grid[y][x] = "a"

    # Spawns: 10 spawns for team 1
    spawns_b = [(43, 10), (43, 12), (43, 14), (43, 16), (43, 18),
                (42, 11), (42, 13), (42, 15), (42, 17), (41, 14)]
    for x, y in spawns_b:
        grid[y][x] = "b"

    # Flags
    grid[14][3] = "P"
    grid[14][44] = "Q"

    # Bomb Sites
    grid[9][24] = "X"   # Inside 3-story building
    grid[19][23] = "Y"  # Inside south building

    # Hardpoints
    grid[14][23] = "h"  # Center Helicopter Plaza
    grid[8][21] = "h"   # North 3-Story Room
    grid[20][27] = "h"  # South Pharmacy

    return ["".join(row) for row in grid]

def generate_standoff():
    w, h = 48, 28
    grid = create_natural_border(w, h)

    # North Building (Warehouse / Granary)
    for x in range(12, 23):
        grid[6][x] = "#"
        grid[11][x] = "#"
    for y in range(6, 12):
        grid[y][12] = "#"
        grid[y][22] = "#"
    grid[11][17] = "."
    grid[11][18] = "."
    grid[8][12] = "."
    grid[9][12] = "."
    grid[8][16] = "."
    grid[9][18] = "c"

    # South Building (Cafe / Bakery)
    for x in range(25, 36):
        grid[16][x] = "#"
        grid[21][x] = "#"
    for y in range(16, 22):
        grid[y][25] = "#"
        grid[y][35] = "#"
    grid[16][30] = "."
    grid[16][31] = "."
    grid[19][35] = "."
    grid[20][35] = "."
    grid[18][29] = "."
    grid[19][31] = "c"

    # Center Street Cover (Abandoned Military Truck & Hay Bales)
    for x in range(22, 27):
        grid[13][x] = "#"
    grid[14][23] = "c"
    grid[14][25] = "c"
    grid[12][22] = "c"
    grid[12][26] = "c"

    # Flanking lane cover
    for y in (7, 8):
        grid[y][29] = "#"
    grid[9][29] = "c"

    for y in (19, 20):
        grid[y][18] = "#"
    grid[18][18] = "c"

    # Spawns: 10 spawns for team 0
    spawns_a = [(4, 9), (4, 11), (4, 13), (4, 15), (4, 17),
                (5, 10), (5, 12), (5, 14), (5, 16), (6, 13)]
    for x, y in spawns_a:
        grid[y][x] = "a"

    # Spawns: 10 spawns for team 1
    spawns_b = [(43, 9), (43, 11), (43, 13), (43, 15), (43, 17),
                (42, 10), (42, 12), (42, 14), (42, 16), (41, 13)]
    for x, y in spawns_b:
        grid[y][x] = "b"

    # Flags
    grid[14][3] = "P"
    grid[14][44] = "Q"

    # Bomb Sites
    grid[8][18] = "X"   # North Warehouse
    grid[19][28] = "Y"  # South Bakery

    # Hardpoints
    grid[14][24] = "h"  # Central Main Street
    grid[9][16] = "h"   # North Building
    grid[18][32] = "h"  # South Building

    return ["".join(row) for row in grid]

def generate_firing_range():
    w, h = 48, 28
    grid = create_natural_border(w, h)

    # Central Shoot House Tower (wide accessible entries)
    for x in range(21, 28):
        grid[11][x] = "#"
        grid[16][x] = "#"
    for y in range(11, 17):
        grid[y][21] = "#"
        grid[y][27] = "#"
    # Wide 3-tile north & south doorways
    grid[11][23] = "."
    grid[11][24] = "."
    grid[11][25] = "."
    grid[16][23] = "."
    grid[16][24] = "."
    grid[16][25] = "."
    # Wide 2-tile side entrances
    grid[13][21] = "."
    grid[14][21] = "."
    grid[13][27] = "."
    grid[14][27] = "."
    grid[13][24] = "."  # Unobstructed center interior

    # North Corridor Shed (Tin Shed)
    for x in range(13, 20):
        grid[6][x] = "#"
    for y in range(6, 10):
        grid[y][13] = "#"
    grid[8][16] = "c"
    grid[7][18] = "c"

    for x in range(28, 35):
        grid[6][x] = "#"
    for y in range(6, 10):
        grid[y][34] = "#"
    grid[8][31] = "c"
    grid[7][29] = "c"

    # South Firing Lanes (Plywood targets and sandbags)
    for x in range(14, 19):
        grid[19][x] = "#"
    grid[20][16] = "c"
    grid[21][17] = "c"

    for x in range(29, 34):
        grid[19][x] = "#"
    grid[20][31] = "c"
    grid[21][30] = "c"

    # Central mid cover
    grid[14][15] = "c"
    grid[14][32] = "c"

    # Spawns: 10 spawns for team 0
    spawns_a = [(4, 9), (4, 11), (4, 13), (4, 15), (4, 17),
                (5, 10), (5, 12), (5, 14), (5, 16), (6, 13)]
    for x, y in spawns_a:
        grid[y][x] = "a"

    # Spawns: 10 spawns for team 1
    spawns_b = [(43, 9), (43, 11), (43, 13), (43, 15), (43, 17),
                (42, 10), (42, 12), (42, 14), (42, 16), (41, 13)]
    for x, y in spawns_b:
        grid[y][x] = "b"

    # Flags
    grid[14][3] = "P"
    grid[14][44] = "Q"

    # Bomb Sites
    grid[8][24] = "X"   # North Shed Lane
    grid[20][24] = "Y"  # South Firing Lane

    # Hardpoints
    grid[14][24] = "h"  # Central Shoot House
    grid[8][16] = "h"   # North Tin Shed
    grid[20][31] = "h"  # South Range Berm

    return ["".join(row) for row in grid]

def test_map(name, lines):
    gm = GameMap({"id": name, "name": name.upper()}, lines)
    assert len(gm.spawns[0]) >= 10, f"{name}: not enough a spawns"
    assert len(gm.spawns[1]) >= 10, f"{name}: not enough b spawns"
    assert sorted(gm.flags) == [0, 1], f"{name}: flags mismatch"
    assert len(gm.sites) >= 2, f"{name}: not enough sites"
    assert len(gm.zones) >= 3, f"{name}: not enough zones"
    for team in (0, 1):
        for p in gm.spawns[team]:
            assert not gm.blocked(p[0], p[1], 12), f"{name}: spawn {p} blocked"
    targets = gm.sites + gm.zones + list(gm.flags.values()) + gm.spawns[1]
    for t in targets:
        path = find_path(gm, gm.spawns[0][0], t)
        assert path is not None, f"{name}: target {t} unreachable"
    print(f"{name} 48x28 passed all validation tests!")

if __name__ == "__main__":
    maps = {
        "nuketown": generate_nuketown(),
        "crashsite": generate_crash(),
        "standoff": generate_standoff(),
        "firing_range": generate_firing_range(),
    }
    for name, lines in maps.items():
        test_map(name, lines)
        out_path = Path(__file__).resolve().parent.parent / "data" / "maps" / f"{name}.txt"
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Saved {out_path.name}")
