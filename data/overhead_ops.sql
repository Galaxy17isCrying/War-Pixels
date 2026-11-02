CREATE DATABASE IF NOT EXISTS overhead_ops
  CHARACTER SET utf8mb4;

USE overhead_ops;

CREATE TABLE IF NOT EXISTS player_profiles (
    player_uid VARCHAR(40) PRIMARY KEY,
    player_name VARCHAR(20) NOT NULL,
    rank_points INT UNSIGNED NOT NULL,
    campaign_completed INT UNSIGNED NOT NULL,
    xp BIGINT UNSIGNED NOT NULL,
    coins BIGINT UNSIGNED NOT NULL,
    crates INT UNSIGNED NOT NULL,
    avatar_frame VARCHAR(64) NULL
);

CREATE TABLE IF NOT EXISTS match_history (
    player_uid VARCHAR(40) NOT NULL,
    local_match_id BIGINT NOT NULL,
    played_at DOUBLE NOT NULL,
    mode VARCHAR(32) NOT NULL,
    map_id VARCHAR(64) NOT NULL,
    difficulty VARCHAR(32) NOT NULL,
    won TINYINT NOT NULL,
    kills INT NOT NULL,
    deaths INT NOT NULL,
    shots INT NOT NULL,
    hits INT NOT NULL,
    headshots INT NOT NULL,
    xp INT NOT NULL,
    PRIMARY KEY (player_uid, local_match_id)
);

CREATE TABLE IF NOT EXISTS weapon_kills (
    player_uid VARCHAR(40) NOT NULL,
    weapon_id VARCHAR(64) NOT NULL,
    kills INT NOT NULL,
    PRIMARY KEY (player_uid, weapon_id)
);

CREATE TABLE IF NOT EXISTS weapon_unlocks (
    player_uid VARCHAR(40) NOT NULL,
    weapon_id VARCHAR(64) NOT NULL,
    PRIMARY KEY (player_uid, weapon_id)
);

CREATE TABLE IF NOT EXISTS owned_skins (
    player_uid VARCHAR(40) NOT NULL,
    skin_id VARCHAR(64) NOT NULL,
    weapon_id VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    rarity VARCHAR(16) NOT NULL,
    kill_effect TINYINT NOT NULL,
    PRIMARY KEY (player_uid, skin_id)
);

CREATE TABLE IF NOT EXISTS equipped_skins (
    player_uid VARCHAR(40) NOT NULL,
    weapon_id VARCHAR(64) NOT NULL,
    skin_id VARCHAR(64) NOT NULL,
    PRIMARY KEY (player_uid, weapon_id)
);

CREATE TABLE IF NOT EXISTS avatar_frame_unlocks (
    player_uid VARCHAR(40) NOT NULL,
    frame_id VARCHAR(64) NOT NULL,
    PRIMARY KEY (player_uid, frame_id)
);

CREATE TABLE IF NOT EXISTS calling_card_unlocks (
    player_uid VARCHAR(40) NOT NULL,
    card_id VARCHAR(64) NOT NULL,
    equipped TINYINT NOT NULL DEFAULT 0,
    PRIMARY KEY (player_uid, card_id)
);
