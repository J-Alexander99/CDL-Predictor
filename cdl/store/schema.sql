-- Rebuilt from data/raw + data/meta on every run. All keys are Breaking Point ids.

CREATE TABLE seasons (
    id          INTEGER PRIMARY KEY,      -- = year, e.g. 2027
    title       TEXT,                     -- "Call of Duty: Modern Warfare IV"
    title_short TEXT,
    modes       TEXT                      -- JSON list of mode names
);

CREATE TABLE events (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    season_id  INTEGER NOT NULL,
    tier       TEXT,
    type       TEXT,
    lan        INTEGER,
    start_date TEXT,
    end_date   TEXT
);

CREATE TABLE teams (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    name_short TEXT,
    logo       TEXT,
    color      TEXT
);

CREATE TABLE players (
    id  INTEGER PRIMARY KEY,
    tag TEXT NOT NULL
);

CREATE TABLE matches (
    id           INTEGER PRIMARY KEY,
    event_id     INTEGER NOT NULL REFERENCES events(id),
    season_id    INTEGER NOT NULL,
    datetime     TEXT NOT NULL,
    best_of      INTEGER,
    team_1_id    INTEGER NOT NULL REFERENCES teams(id),
    team_2_id    INTEGER NOT NULL REFERENCES teams(id),
    winner_id    INTEGER,
    team_1_score INTEGER,
    team_2_score INTEGER,
    round        TEXT,
    round_stage  TEXT,
    lan          INTEGER,
    division_id  INTEGER                  -- 3 = CDL, 1 = Challengers
);
CREATE INDEX ix_matches_dt ON matches(datetime);

CREATE TABLE games (
    match_id     INTEGER NOT NULL REFERENCES matches(id),
    game_num     INTEGER NOT NULL,
    mode         TEXT NOT NULL,
    map          TEXT,
    team_1_id    INTEGER NOT NULL,
    team_2_id    INTEGER NOT NULL,
    winner_id    INTEGER,
    team_1_score INTEGER,
    team_2_score INTEGER,
    duration_s   INTEGER,
    PRIMARY KEY (match_id, game_num)
);

CREATE TABLE player_game_stats (
    match_id            INTEGER NOT NULL,
    game_num            INTEGER NOT NULL,
    player_id           INTEGER NOT NULL REFERENCES players(id),
    team_id             INTEGER NOT NULL,
    kills               INTEGER,
    deaths              INTEGER,
    assists             INTEGER,
    damage              INTEGER,
    bp_rating           REAL,
    non_traded_kills    INTEGER,
    highest_streak      INTEGER,
    hill_time           INTEGER,
    contested_hill_time INTEGER,
    first_blood_count   INTEGER,
    first_death_count   INTEGER,
    plant_count         INTEGER,
    defuse_count        INTEGER,
    snd_rounds          INTEGER,
    extra               TEXT,                 -- JSON of any other non-null stats
    PRIMARY KEY (match_id, game_num, player_id)
);

CREATE TABLE vetoes (
    match_id   INTEGER NOT NULL,
    ord        INTEGER,
    team_id    INTEGER,
    mode       TEXT,
    map        TEXT,
    action     TEXT,                          -- Pick / Ban
    map_number INTEGER
);

CREATE VIEW v_games AS
SELECT g.*, m.datetime, m.season_id, m.event_id, m.lan, m.best_of,
       t1.name AS team_1, t2.name AS team_2
FROM games g
JOIN matches m ON m.id = g.match_id
JOIN teams t1 ON t1.id = g.team_1_id
JOIN teams t2 ON t2.id = g.team_2_id;
