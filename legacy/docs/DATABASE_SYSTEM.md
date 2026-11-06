# CDL Predictor - Database System

The database system has been successfully implemented with granular map-mode combination tracking.

## Database Schema

The system includes the following tables:

### Core Data Tables
- **matches**: Stores complete match information (teams, scores, tournament, date)
- **map_results**: Individual map results for each match
- **player_match_stats**: Player statistics for each match

### Aggregated Statistics Tables
- **team_stats**: Overall team statistics (matches won/lost, map win rates)
- **team_mode_stats**: Team statistics by game mode (Hardpoint, S&D, etc.)
- **team_map_mode_stats**: Team statistics by map-mode combination (e.g., "Hardpoint on Exposure" tracked separately from "S&D on Exposure")
- **head_to_head**: Overall head-to-head records between teams
- **head_to_head_map_mode**: Head-to-head records for specific map-mode combinations
- **player_stats**: Player average statistics across all matches

## Features

### Data Import
```bash
# Import existing JSON matches into database
python -m src.database.import_matches
```

### CLI Commands

```bash
# Scrape a match (automatically saves to database and updates stats)
python main.py scrape --url "https://www.breakingpoint.gg/match/..."

# List all teams in database
python main.py teams

# View team statistics (all map-mode combinations)
python main.py team-stats --team "Toronto KOI"

# View stats filtered by mode
python main.py team-stats --team "Toronto KOI" --mode "Hardpoint"

# View stats for specific map
python main.py team-stats --team "Toronto KOI" --map "Exposure"

# View stats for specific map-mode combination
python main.py team-stats --team "Toronto KOI" --map "Exposure" --mode "Hardpoint"

# Recalculate all statistics from match data
python main.py update-stats
```

## Map-Mode Combination Tracking

The key feature of this system is tracking each map-mode combination as a distinct entity. For example:

- **Hardpoint on Exposure**: Tracked separately with its own win/loss record, average scores
- **Search & Destroy on Exposure**: Tracked separately as a different stat
- **Overload on Exposure**: Tracked separately

This allows for highly specific predictions based on a team's performance in the exact game mode and map combination that will be played.

## Database Location

The SQLite database is stored at: `data/cdl_predictor.db`

## Next Steps

To build on this foundation:

1. **Bulk Scraping**: Add functionality to scrape multiple matches at once
2. **Head-to-Head Queries**: Add CLI commands to view head-to-head records
3. **Recent Form**: Add queries for team performance over last N matches
4. **Prediction Model**: Build ML model using the aggregated statistics
5. **API**: Create REST API to expose statistics for web interfaces

## Statistics Auto-Update

Every time a new match is scraped, the system automatically:
1. Inserts match data into core tables
2. Updates team_stats for both teams
3. Updates team_mode_stats for all modes played
4. Updates team_map_mode_stats for all map-mode combinations
5. Updates head-to-head records
6. Updates head-to-head map-mode records
7. Updates player statistics for all 8 players

This ensures statistics are always current and ready for predictions.
