-- CDL Predictor Database Schema

-- Core match data
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT UNIQUE NOT NULL,
    team_a TEXT NOT NULL,
    team_b TEXT NOT NULL,
    winner TEXT NOT NULL,
    team_a_score INTEGER NOT NULL,
    team_b_score INTEGER NOT NULL,
    tournament TEXT,
    match_date DATE NOT NULL,
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual map results
CREATE TABLE IF NOT EXISTS map_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    map_number INTEGER NOT NULL,
    mode TEXT NOT NULL,
    map_name TEXT NOT NULL,
    team_a_score INTEGER NOT NULL,
    team_b_score INTEGER NOT NULL,
    winner TEXT NOT NULL,
    FOREIGN KEY (match_id) REFERENCES matches(match_id),
    UNIQUE(match_id, map_number)
);

-- Player statistics per match (series totals)
CREATE TABLE IF NOT EXISTS player_match_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    kills INTEGER NOT NULL,
    deaths INTEGER NOT NULL,
    kd REAL NOT NULL,
    plus_minus TEXT,
    damage INTEGER NOT NULL,
    rating REAL NOT NULL,
    FOREIGN KEY (match_id) REFERENCES matches(match_id),
    UNIQUE(match_id, player_name)
);

-- Player statistics per individual map
CREATE TABLE IF NOT EXISTS player_map_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    map_number INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    mode TEXT NOT NULL,
    map_name TEXT NOT NULL,
    kills INTEGER NOT NULL,
    deaths INTEGER NOT NULL,
    kd REAL NOT NULL,
    damage INTEGER NOT NULL,
    rating REAL NOT NULL,
    FOREIGN KEY (match_id) REFERENCES matches(match_id),
    UNIQUE(match_id, map_number, player_name)
);

-- Aggregated team statistics
CREATE TABLE IF NOT EXISTS team_stats (
    team_name TEXT PRIMARY KEY,
    total_matches INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    maps_won INTEGER DEFAULT 0,
    maps_lost INTEGER DEFAULT 0,
    map_win_rate REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Team statistics by mode (Hardpoint, Search & Destroy, etc.)
CREATE TABLE IF NOT EXISTS team_mode_stats (
    team_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_score_for REAL DEFAULT 0.0,
    avg_score_against REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team_name, mode)
);

-- Team statistics by map-mode combination (e.g., "Hardpoint on Exposure")
CREATE TABLE IF NOT EXISTS team_map_mode_stats (
    team_name TEXT NOT NULL,
    map_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_score_for REAL DEFAULT 0.0,
    avg_score_against REAL DEFAULT 0.0,
    total_played INTEGER DEFAULT 0,
    last_played DATE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team_name, map_name, mode)
);

-- Head-to-head records between teams
CREATE TABLE IF NOT EXISTS head_to_head (
    team_a TEXT NOT NULL,
    team_b TEXT NOT NULL,
    team_a_wins INTEGER DEFAULT 0,
    team_b_wins INTEGER DEFAULT 0,
    team_a_map_wins INTEGER DEFAULT 0,
    team_b_map_wins INTEGER DEFAULT 0,
    last_match_date DATE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team_a, team_b),
    CHECK (team_a < team_b)  -- Ensure alphabetical ordering to avoid duplicates
);

-- Head-to-head by specific map-mode combination
CREATE TABLE IF NOT EXISTS head_to_head_map_mode (
    team_a TEXT NOT NULL,
    team_b TEXT NOT NULL,
    map_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    team_a_wins INTEGER DEFAULT 0,
    team_b_wins INTEGER DEFAULT 0,
    last_played DATE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team_a, team_b, map_name, mode),
    CHECK (team_a < team_b)
);

-- Player average statistics (overall)
CREATE TABLE IF NOT EXISTS player_stats (
    player_name TEXT PRIMARY KEY,
    current_team TEXT,
    total_matches INTEGER DEFAULT 0,
    avg_kills REAL DEFAULT 0.0,
    avg_deaths REAL DEFAULT 0.0,
    avg_kd REAL DEFAULT 0.0,
    avg_damage REAL DEFAULT 0.0,
    avg_rating REAL DEFAULT 0.0,
    total_kills INTEGER DEFAULT 0,
    total_deaths INTEGER DEFAULT 0,
    total_damage INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Player statistics by game mode
CREATE TABLE IF NOT EXISTS player_mode_stats (
    player_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    maps_played INTEGER DEFAULT 0,
    avg_kills REAL DEFAULT 0.0,
    avg_deaths REAL DEFAULT 0.0,
    avg_kd REAL DEFAULT 0.0,
    avg_damage REAL DEFAULT 0.0,
    avg_rating REAL DEFAULT 0.0,
    total_kills INTEGER DEFAULT 0,
    total_deaths INTEGER DEFAULT 0,
    total_damage INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (player_name, mode)
);

-- Player statistics by map-mode combination
CREATE TABLE IF NOT EXISTS player_map_mode_stats (
    player_name TEXT NOT NULL,
    map_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    maps_played INTEGER DEFAULT 0,
    avg_kills REAL DEFAULT 0.0,
    avg_deaths REAL DEFAULT 0.0,
    avg_kd REAL DEFAULT 0.0,
    avg_damage REAL DEFAULT 0.0,
    avg_rating REAL DEFAULT 0.0,
    total_kills INTEGER DEFAULT 0,
    total_deaths INTEGER DEFAULT 0,
    total_damage INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (player_name, map_name, mode)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date DESC);
CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(team_a, team_b);
CREATE INDEX IF NOT EXISTS idx_map_results_match ON map_results(match_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_match ON player_match_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_team ON player_match_stats(team);
CREATE INDEX IF NOT EXISTS idx_player_map_stats_match ON player_map_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_player_map_stats_player ON player_map_stats(player_name);
CREATE INDEX IF NOT EXISTS idx_player_map_stats_mode ON player_map_stats(mode);
CREATE INDEX IF NOT EXISTS idx_player_map_stats_map ON player_map_stats(map_name);
