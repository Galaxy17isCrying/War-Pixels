#include <algorithm>
#include <fstream>
#include <iostream>
#include <queue>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

struct MapReport {
    string name;
    int width = 0;
    int height = 0;
    int walls = 0;
    int crates = 0;
    int walkable = 0;
    int components = 0;
    int largest_component = 0;
    int choke_candidates = 0;
};

bool is_solid(char tile) {
    return tile == '#' || tile == 'c';
}

MapReport analyze_map(const string& name, const vector<string>& grid) {
    MapReport report;
    report.name = name;
    report.height = static_cast<int>(grid.size());
    report.width = static_cast<int>(grid.front().size());

    for (const string& row : grid) {
        if (static_cast<int>(row.size()) != report.width) {
            throw runtime_error("ragged map row");
        }
        for (char tile : row) {
            report.walls += tile == '#';
            report.crates += tile == 'c';
            report.walkable += !is_solid(tile);
        }
    }

    vector<vector<bool>> visited(report.height, vector<bool>(report.width, false));
    const int dx[] = {1, -1, 0, 0};
    const int dy[] = {0, 0, 1, -1};
    for (int y = 0; y < report.height; ++y) {
        for (int x = 0; x < report.width; ++x) {
            if (is_solid(grid[y][x])) {
                continue;
            }

            const bool left_blocked = x == 0 || is_solid(grid[y][x - 1]);
            const bool right_blocked = x == report.width - 1 || is_solid(grid[y][x + 1]);
            const bool up_blocked = y == 0 || is_solid(grid[y - 1][x]);
            const bool down_blocked = y == report.height - 1 || is_solid(grid[y + 1][x]);
            const bool horizontal_lane = y > 0 && y + 1 < report.height &&
                left_blocked && right_blocked && !up_blocked && !down_blocked;
            const bool vertical_lane = x > 0 && x + 1 < report.width &&
                up_blocked && down_blocked && !left_blocked && !right_blocked;
            report.choke_candidates += horizontal_lane || vertical_lane;

            if (visited[y][x]) {
                continue;
            }
            ++report.components;
            int component_size = 0;
            queue<pair<int, int>> frontier;
            frontier.push({x, y});
            visited[y][x] = true;
            while (!frontier.empty()) {
                const auto [cx, cy] = frontier.front();
                frontier.pop();
                ++component_size;
                for (int direction = 0; direction < 4; ++direction) {
                    const int nx = cx + dx[direction];
                    const int ny = cy + dy[direction];
                    if (nx >= 0 && nx < report.width && ny >= 0 && ny < report.height &&
                        !visited[ny][nx] && !is_solid(grid[ny][nx])) {
                        visited[ny][nx] = true;
                        frontier.push({nx, ny});
                    }
                }
            }
            report.largest_component = max(report.largest_component, component_size);
        }
    }
    return report;
}

int main() {
    cout << "=== Overhead Ops C++ Map Optimizer & Tactical Analyzer ===" << endl;
    const vector<string> map_names = {
        "nuketown", "crashsite", "standoff", "firing_range",
        "depot_09", "raidhouse", "summitline", "marketrow",
        "blacksite", "dustline", "frontier", "hijackedbay",
        "iron_district", "launchpad", "range"
    };

    int analyzed = 0;
    int invalid = 0;
    for (const string& name : map_names) {
        const string path = "data/maps/" + name + ".txt";
        ifstream infile(path);
        if (!infile.is_open()) {
            continue;
        }

        vector<string> grid;
        string line;
        while (getline(infile, line)) {
            if (!line.empty() && line.back() == '\r') {
                line.pop_back();
            }
            if (!line.empty()) {
                grid.push_back(line);
            }
        }
        if (grid.empty()) {
            cout << "[INVALID] " << name << ": map has no rows" << endl;
            ++invalid;
            continue;
        }

        try {
            const MapReport report = analyze_map(name, grid);
            const double connected_percent = report.walkable == 0 ? 0.0 :
                100.0 * report.largest_component / report.walkable;
            cout << "[MAP] " << report.name << " (" << report.width << "x" << report.height
                 << ") Walls: " << report.walls << " Crates: " << report.crates
                 << " Walkable: " << report.walkable
                 << " Components: " << report.components
                 << " Largest: " << report.largest_component << " ("
                 << connected_percent << "%) Choke candidates: " << report.choke_candidates << endl;
            ++analyzed;
        } catch (const runtime_error& error) {
            cout << "[INVALID] " << name << ": " << error.what() << endl;
            ++invalid;
        }
    }

    cout << "=== Analysis Complete: " << analyzed << " maps analyzed, "
         << invalid << " invalid ===" << endl;
    return analyzed == 0 || invalid > 0 ? 1 : 0;
}
