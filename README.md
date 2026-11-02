
# War Pixels

A 2.5D Python/Pygame shooter with campaign missions, local multiplayer simulation, online matchmaking, mobile touch controls, and customizable HUD layouts.

The project owner has authorized public distribution of `assets/audio/menu.mp3`. The alternate `haiya_haiya_better_together.mp3` is excluded from the repository and release builds.

## Latest content update
- Added four CODM-inspired tactical layouts: Nuketown, Crash, Standoff, and Firing Range. These are original grid layouts inspired by the pacing and lane structure of familiar mobile-shooter maps, not copied game assets.
- Expanded Operation Ashen Signal to nine sequential campaign missions with briefings, objectives, recommended difficulty, map previews, unlock progression, and replay support.
- Improved leaderboard profile cards with player/avatar badges and a stylized calling-card panel.
- Increased the default programmatic match size to 10v10 for compatibility with full-team simulation; the game UI still passes the player's selected 5v5 or 10v10 size explicitly.
- Fixed map spawn/objective marker coverage and updated the campaign test for nine chapters.

Validation: `python -m unittest discover -s tests -q` (89 tests passed).

## Scorestreak loadout and store

Open **LOADOUT → STREAKS** to equip three scorestreaks. Use the arrow keys to browse, `1`/`2`/`3` to choose an equipped slot, `Enter` to equip, `B` to purchase a scorestreak, and `S` to purchase/equip a cosmetic skin. The page shows each streak's in-match score cost, level requirement, store price, and equipped slot. Loadout choices are saved per preset.

The **GAME STORE** also has tabs `3 SCORESTREAKS` and `4 STREAK SKINS`. Some streaks unlock by player level; store streaks require reaching their listed level and then spending credits. Cosmetic streak skins are saved and equipped per streak. Scorestreak art in this version uses in-game vector emblems, so it does not require downloading external images.

The **GAME STORE** also has **5 CALLING CARDS**. Buy a card with coins to unlock and equip it; the equipped design appears on your leaderboard profile.

## C++ tactical map analysis

The map analyzer reports walkable area, connected regions, and potential choke cells for the shipped layouts. From the project root, build and run it with:

```powershell
g++ -std=c++17 tools\map_optimizer.cpp -o tools\map_optimizer.exe
.\tools\map_optimizer.exe
```

## Visual upgrade: semi-3D battlefield and studio ident

- Added a short original **GalaxyLovesRice Studios** animated logo ident on launch. Press any key or click to skip it.
- The credits distinguish generated visuals/gameplay sounds from the separately bundled menu music.
- Operators have more layered armor, shoulder plates, pouches, visor highlights and stronger ground shadows.
- Weapons now use extra receiver bevels, top highlights, dark underside shading and a defined muzzle for a chunkier pseudo-3D look.
- Battlefield rendering includes sparse, deterministic decorative rubble, scrub trees and scorched tank wreck silhouettes. These are visual set dressing and do not change collision/pathfinding.
- Existing scorestreak loadout and activation bindings are retained (in-match `4`, `5`, `6`); scorestreak behavior is implemented by the existing match systems.

The game remains a native Python/Pygame desktop game, not a website or HTML game. The 2.5D look is created with layered sprite shading and drawing primitives rather than a 3D engine. Some decorative props are visual-only and do not provide cover.

Validation after these changes: `python -m unittest discover -s tests -q` (94 tests passed), plus Python compile checks and ZIP integrity verification.

## Android and touch controls

The Android build configuration is in `buildozer.spec`. Build APKs from Linux or WSL with Buildozer installed (`buildozer android debug`); this project targets landscape mode. Android users can open **CUSTOMIZE MOBILE HUD** from the main menu or pause menu, drag controls, and resize the selected control with `+`/`-` or the mouse wheel. The layout is saved in local settings.

The current Windows workspace does not include Buildozer or Android SDK/ADB, so an APK has not been built or device-tested here.

## Downloadable builds

The **Build War Pixels** GitHub Actions workflow packages a Windows executable and an Android APK on pushes to `main` and on manual runs. Download the build artifacts from the workflow run, or push a version tag such as `v1.0.0` to create a GitHub release containing both builds. Android builds target `arm64-v8a`; install the APK on a compatible device and grant any requested permissions.

## GitHub OAuth and account API

The optional account API uses its own SQLite database (`accounts.db` by default), separate from local game saves and the optional MySQL stats mirror. It stores GitHub profile identifiers and SHA-256 digests of random, expiring OAuth-state and session tokens; GitHub credentials and access tokens are not stored in that database.

1. Copy `.env.example` to `.env` and set `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, and `GITHUB_OAUTH_REDIRECT_URI` to match a GitHub OAuth App. The example callback is `http://127.0.0.1:8000/auth/github/callback` for local development.
2. Keep `.env` private and untracked. OAuth client credentials must remain usable by the server, so do not hash them; use a deployment secret store and HTTPS in production.
3. Start the API with `python -m server.api --host 127.0.0.1 --port 8000`.

The API provides `GET /api/health`, `GET /auth/github/login`, `GET /auth/github/callback`, `GET /api/me`, and `POST /api/logout`. OAuth currently authenticates with the API in a browser; it is not connected to the game client or online-match identity. The multiplayer service remains a client-simulated input relay, not an authoritative anti-cheat system.

## Online matchmaking

Run the dedicated matchmaking and input-relay service from the project root:

```powershell
python -m server --host 0.0.0.0 --port 8765
```

In each game client, choose **ONLINE MATCHMAKING**, enter the server as `host:port`, and find a match. The initial online queue is Search and Destroy on Depot 09; each team has one human player and bots fill the remaining slots. Clients run the same seeded simulation while the server relays inputs at 20 Hz. This prototype is not server-authoritative and should not be treated as cheat-resistant competitive hosting.

The relay does not need MySQL. The existing optional MySQL stats mirror remains a client-side setting; it is separate from matchmaking. For remote play, host the service on a reachable machine and allow inbound TCP on the configured port. See [server/README.md](./server/README.md) for the protocol and local service details.
