CREATE TABLE IF NOT EXISTS stg_api_football_fixtures (
    fixture_id BIGINT PRIMARY KEY,
    fixture_date TIMESTAMPTZ,
    fixture_timestamp BIGINT,
    timezone TEXT,
    status_short TEXT,
    status_long TEXT,
    league_id INTEGER,
    league_name TEXT,
    season INTEGER,
    round_name TEXT,
    home_team_id INTEGER,
    home_team_name TEXT,
    away_team_id INTEGER,
    away_team_name TEXT,
    venue_name TEXT,
    venue_city TEXT,
    goals_home INTEGER,
    goals_away INTEGER,
    score_ht_home INTEGER,
    score_ht_away INTEGER,
    score_ft_home INTEGER,
    score_ft_away INTEGER,
    source_endpoint TEXT,
    source_params JSONB,
    ingested_at TIMESTAMPTZ,
    loaded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS etl_request_log (
    request_id BIGSERIAL PRIMARY KEY,
    requested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    source_system TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    params JSONB,
    status_code INTEGER,
    rows_loaded INTEGER,
    remaining_requests INTEGER,
    daily_limit INTEGER,
    raw_path TEXT
);

CREATE TABLE IF NOT EXISTS mart_upcoming_fixtures (
    fixture_id BIGINT PRIMARY KEY,
    fixture_date TIMESTAMPTZ,
    league_id INTEGER,
    league_name TEXT,
    season INTEGER,
    round_name TEXT,
    home_team_id INTEGER,
    home_team_name TEXT,
    away_team_id INTEGER,
    away_team_name TEXT,
    status_short TEXT,
    status_long TEXT,
    ingested_at TIMESTAMPTZ,
    refreshed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_api_football_fixture_events (
    event_id BIGSERIAL PRIMARY KEY,
    fixture_id BIGINT NOT NULL,
    elapsed INTEGER,
    elapsed_extra INTEGER,
    team_id INTEGER,
    team_name TEXT,
    player_id INTEGER,
    player_name TEXT,
    assist_id INTEGER,
    assist_name TEXT,
    event_type TEXT,
    event_detail TEXT,
    ingested_at TIMESTAMPTZ,
    loaded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (fixture_id, elapsed, elapsed_extra, team_id, player_id, event_type, event_detail)
);

CREATE TABLE IF NOT EXISTS mart_fixture_quality_summary (
    summary_id BIGSERIAL PRIMARY KEY,
    checked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fixtures_total INTEGER NOT NULL,
    fixtures_without_date INTEGER NOT NULL,
    fixtures_without_teams INTEGER NOT NULL,
    duplicated_fixture_ids INTEGER NOT NULL
);
