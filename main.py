"""
Main entry point for CDL Predictor CLI
"""
import click
from pathlib import Path

from src.utils import setup_logger
from config.settings import PROJECT_ROOT, LOGS_DIR
from config.teams import TEAM_SHORT_NAMES
from src.database.db_manager import DatabaseManager

logger = setup_logger("main", LOGS_DIR)


@click.group()
@click.version_option(version="2.0.0")
def cli():
    """CDL Match Predictor - Scrape data and predict Call of Duty League matches"""
    pass


@cli.command()
@click.option('--url', required=True, help='URL of the match page to scrape')
@click.option('--save', default='data/matches', help='Directory to save scraped data')
def scrape(url: str, save: str):
    """Scrape match data from a CDL match page"""
    import json
    from pathlib import Path
    from src.scrapers.enhanced_match_scraper import EnhancedMatchScraper
    
    logger.info(f"Scraping match from: {url}")
    click.echo(f"Scraping {url}...")
    
    try:
        scraper = EnhancedMatchScraper()
        data = scraper.scrape(url)
        
        # Calculate final scores from map results
        team_a_wins = sum(1 for m in data['map_results'] if m['team_a_score'] > m['team_b_score'])
        team_b_wins = sum(1 for m in data['map_results'] if m['team_b_score'] > m['team_a_score'])
        
        data['match_info']['team_a_score'] = team_a_wins
        data['match_info']['team_b_score'] = team_b_wins
        
        # Generate filename based on teams and match count
        team_a = data['match_info']['team_a']
        team_b = data['match_info']['team_b']
        match_date = data['match_info']['date']
        match_year = match_date.split('-')[0]
        
        # Get short team names, fallback to cleaned full name if not in mapping
        short_team_a = TEAM_SHORT_NAMES.get(team_a, ''.join(c for c in team_a if c.isalnum()))
        short_team_b = TEAM_SHORT_NAMES.get(team_b, ''.join(c for c in team_b if c.isalnum()))
        
        # Query database to count existing matches between these teams this year
        db = DatabaseManager()
        match_count = db.get_head_to_head_count(team_a, team_b, match_year)
        match_number = match_count + 1  # Next match number
        
        # Create filename: TeamATeamB1.json, TeamATeamB2.json, etc.
        filename = f"{short_team_a}{short_team_b}{match_number}.json"
        
        # Save to file
        save_path = Path(save)
        save_path.mkdir(parents=True, exist_ok=True)
        output_file = save_path / filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Save to database and update stats
        try:
            db.insert_match(data)
            db.update_all_stats()
            logger.info("Match saved to database and stats updated")
        except Exception as e:
            logger.warning(f"Failed to save to database: {e}")
        
        click.echo(f"\n[SUCCESS] Match data scraped successfully!")
        click.echo(f"  Match: {data['match_info']['team_a']} vs {data['match_info']['team_b']}")
        click.echo(f"  Score: {team_a_wins}-{team_b_wins}")
        click.echo(f"  Maps: {len(data['map_results'])}")
        click.echo(f"  Players: {len(data['player_stats']['team_a'])} vs {len(data['player_stats']['team_b'])}")
        click.echo(f"  Saved to: {output_file}")
        click.echo(f"  Database: Updated")
        
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--file', 'url_file', required=True, help='File containing match URLs (one per line)')
@click.option('--save', default='data/matches', help='Directory to save scraped data')
@click.option('--delay', default=10, help='Delay between scrapes in seconds (default: 10)')
def scrape_bulk(url_file: str, save: str, delay: int):
    """Scrape multiple matches from a file containing URLs"""
    import json
    import time
    from pathlib import Path
    from src.scrapers.enhanced_match_scraper import EnhancedMatchScraper
    
    # Read URLs from file
    try:
        with open(url_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    except FileNotFoundError:
        click.echo(f"[ERROR] File not found: {url_file}", err=True)
        return
    
    if not urls:
        click.echo("[ERROR] No URLs found in file", err=True)
        return
    
    click.echo(f"\nFound {len(urls)} matches to scrape")
    click.echo(f"Delay between scrapes: {delay} seconds\n")
    
    success_count = 0
    fail_count = 0
    
    for i, url in enumerate(urls, 1):
        click.echo(f"[{i}/{len(urls)}] Scraping {url}...")
        
        try:
            scraper = EnhancedMatchScraper()
            data = scraper.scrape(url)
            
            # Calculate final scores
            team_a_wins = sum(1 for m in data['map_results'] if m['team_a_score'] > m['team_b_score'])
            team_b_wins = sum(1 for m in data['map_results'] if m['team_b_score'] > m['team_a_score'])
            data['match_info']['team_a_score'] = team_a_wins
            data['match_info']['team_b_score'] = team_b_wins
            
            # Generate filename
            team_a = data['match_info']['team_a']
            team_b = data['match_info']['team_b']
            match_date = data['match_info']['date']
            match_year = match_date.split('-')[0]
            
            short_team_a = TEAM_SHORT_NAMES.get(team_a, ''.join(c for c in team_a if c.isalnum()))
            short_team_b = TEAM_SHORT_NAMES.get(team_b, ''.join(c for c in team_b if c.isalnum()))
            
            db = DatabaseManager()
            match_count = db.get_head_to_head_count(team_a, team_b, match_year)
            match_number = match_count + 1
            filename = f"{short_team_a}{short_team_b}{match_number}.json"
            
            # Save to file
            save_path = Path(save)
            save_path.mkdir(parents=True, exist_ok=True)
            output_file = save_path / filename
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Save to database
            db.insert_match(data)
            db.update_all_stats()
            
            click.echo(f"  ✓ {team_a} vs {team_b} ({team_a_wins}-{team_b_wins}) → {filename}\n")
            success_count += 1
            
            # Delay before next scrape (except for last one)
            if i < len(urls):
                time.sleep(delay)
                
        except Exception as e:
            click.echo(f"  ✗ Failed: {str(e)}\n", err=True)
            logger.error(f"Failed to scrape {url}: {str(e)}")
            fail_count += 1
            continue
    
    click.echo("\n" + "="*50)
    click.echo(f"Bulk scraping complete!")
    click.echo(f"  Success: {success_count}/{len(urls)}")
    click.echo(f"  Failed: {fail_count}/{len(urls)}")


@cli.command()
def update_stats():
    """Update all team and player statistics from database"""
    logger.info("Updating statistics...")
    click.echo("Recalculating all statistics from match data...")
    
    try:
        db = DatabaseManager()
        db.update_all_stats()
        click.echo("[SUCCESS] Statistics updated successfully!")
    except Exception as e:
        logger.error(f"Stats update failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--team-a', required=True, help='First team name')
@click.option('--team-b', required=True, help='Second team name')
def predict(team_a: str, team_b: str):
    """Predict the outcome of a match between two teams"""
    from src.predictor import MatchPredictor
    
    logger.info(f"Predicting: {team_a} vs {team_b}")
    click.echo(f"\n{'='*80}")
    click.echo(f"CDL MATCH PREDICTION: {team_a} vs {team_b}")
    click.echo(f"{'='*80}\n")
    
    try:
        predictor = MatchPredictor()
        result = predictor.predict(team_a, team_b)
        
        # Display rosters
        click.echo("CURRENT ROSTERS:")
        click.echo(f"  {team_a}: {', '.join(result['team_a_roster'])}")
        click.echo(f"  {team_b}: {', '.join(result['team_b_roster'])}")
        click.echo()
        
        # Display team statistics
        click.echo("TEAM STATISTICS:")
        stats_a = result['team_a_stats']
        stats_b = result['team_b_stats']
        
        click.echo(f"\n  {team_a}:")
        click.echo(f"    Team Chemistry:")
        click.echo(f"      Weighted Matches: {stats_a['weighted_matches']} ({stats_a['matches_played']} total)")
        click.echo(f"      Win Rate: {stats_a['win_rate']}%")
        click.echo(f"      Map Win Rate: {stats_a['map_win_rate']}%")
        click.echo(f"    Roster Quality:")
        click.echo(f"      Avg K/D: {stats_a['roster_quality']['avg_kd']}")
        click.echo(f"      Avg Rating: {stats_a['roster_quality']['avg_rating']}")
        click.echo(f"      Avg Damage: {stats_a['roster_quality']['avg_damage']:.0f}")
        
        click.echo(f"\n  {team_b}:")
        click.echo(f"    Team Chemistry:")
        click.echo(f"      Weighted Matches: {stats_b['weighted_matches']} ({stats_b['matches_played']} total)")
        click.echo(f"      Win Rate: {stats_b['win_rate']}%")
        click.echo(f"      Map Win Rate: {stats_b['map_win_rate']}%")
        click.echo(f"    Roster Quality:")
        click.echo(f"      Avg K/D: {stats_b['roster_quality']['avg_kd']}")
        click.echo(f"      Avg Rating: {stats_b['roster_quality']['avg_rating']}")
        click.echo(f"      Avg Damage: {stats_b['roster_quality']['avg_damage']:.0f}")
        
        # Display head-to-head
        h2h = result['head_to_head']
        if h2h['total_matches'] > 0:
            click.echo(f"\nHEAD-TO-HEAD RECORD:")
            click.echo(f"  {team_a}: {h2h['team_a_wins']} wins")
            click.echo(f"  {team_b}: {h2h['team_b_wins']} wins")
            click.echo(f"  Total matches: {h2h['total_matches']}")
        else:
            click.echo(f"\nHEAD-TO-HEAD: No previous matches")
        
        # Display prediction
        click.echo(f"\n{'='*80}")
        click.echo("PREDICTIONS:")
        click.echo(f"{'='*80}")
        
        # Overall Team Comparison
        click.echo(f"\n  1) OVERALL TEAM COMPARISON (All modes combined + H2H):")
        overall_winner = team_a if result['team_a_win_probability'] > result['team_b_win_probability'] else team_b
        overall_margin = abs(result['team_a_win_probability'] - result['team_b_win_probability'])
        click.echo(f"     Predicted Winner: {overall_winner}")
        click.echo(f"     Win Probability:")
        click.echo(f"       {team_a}: {result['team_a_win_probability']}%")
        click.echo(f"       {team_b}: {result['team_b_win_probability']}%")
        click.echo(f"     Margin: {overall_margin:.1f}%")
        
        # Mode-Specific Map Prediction
        click.echo(f"\n  2) MODE-SPECIFIC MAP-BY-MAP PREDICTION:")
        click.echo(f"     Predicted Winner: {result['predicted_winner']}")
        click.echo(f"     Predicted Score: {result['predicted_score']}")
        
        # Map-by-map breakdown with detailed mode stats
        click.echo(f"\n  Map-by-Map Predictions:")
        for map_pred in result['map_predictions']:
            winner = map_pred['predicted_winner']
            winner_symbol = "→" if winner == team_a else "←"
            
            mode_stats_a = map_pred['team_a_mode_stats']
            mode_stats_b = map_pred['team_b_mode_stats']
            
            click.echo(f"\n    Map {map_pred['map_number']}: {map_pred['mode']}")
            click.echo(f"      {team_a}: {map_pred['team_a_probability']}% {winner_symbol if winner == team_a else ''}")
            click.echo(f"        Mode Stats: {mode_stats_a['win_rate']:.1f}% WR, {mode_stats_a['weighted_maps']:.1f} weighted maps", nl=False)
            if mode_stats_a.get('avg_score_diff', 0) != 0:
                click.echo(f", Avg Diff: {mode_stats_a['avg_score_diff']:+.1f}")
            else:
                click.echo()
            
            click.echo(f"      {team_b}: {map_pred['team_b_probability']}% {winner_symbol if winner == team_b else ''}")
            click.echo(f"        Mode Stats: {mode_stats_b['win_rate']:.1f}% WR, {mode_stats_b['weighted_maps']:.1f} weighted maps", nl=False)
            if mode_stats_b.get('avg_score_diff', 0) != 0:
                click.echo(f", Avg Diff: {mode_stats_b['avg_score_diff']:+.1f}")
            else:
                click.echo()
        
        # Analysis note
        click.echo(f"\n  ANALYSIS:")
        overall_winner = team_a if result['team_a_win_probability'] > result['team_b_win_probability'] else team_b
        map_winner = result['predicted_winner']
        
        if overall_winner == map_winner:
            click.echo(f"    ✓ Both predictions align - {overall_winner} favored")
            click.echo(f"    Confidence: HIGH")
        else:
            click.echo(f"    ⚠ Predictions diverge!")
            click.echo(f"      Overall comparison favors: {overall_winner}")
            click.echo(f"      Mode-specific favors: {map_winner}")
            click.echo(f"    Confidence: MODERATE - Mode-specific strengths may override overall stats")
        
        if result['confidence'] < 10:
            click.echo(f"    Note: Very close matchup ({result['confidence']:.1f}% margin)")
        elif result['confidence'] > 30:
            click.echo(f"    Note: Strong favorite ({result['confidence']:.1f}% margin)")
        
        # Pick/Ban Prediction
        click.echo(f"\n  3) PREDICTED MAP POOL (Pick/Ban Simulation):")
        pick_ban = result['pick_ban_prediction']
        
        for pred_map in pick_ban['predicted_maps']:
            click.echo(f"\n    Map {pred_map['map_number']}: {pred_map['mode']} - {pred_map['predicted_map']}")
            if 'team_a_winrate' in pred_map:
                click.echo(f"      {team_a}: {pred_map['team_a_winrate']}% WR ({pred_map['team_a_plays']:.1f} weighted plays)")
                click.echo(f"      {team_b}: {pred_map['team_b_winrate']}% WR ({pred_map['team_b_plays']:.1f} weighted plays)")
            click.echo(f"      Reasoning: {pred_map['reasoning']}")
        
        click.echo(f"\n{'='*80}\n")
        
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}")
        click.echo(f"\n[ERROR] {str(e)}", err=True)
        click.echo(f"Make sure both team names are spelled correctly.\n", err=True)


@cli.command()
@click.option('--team', required=True, help='Team name to look up')
@click.option('--map', 'map_name', help='Filter by specific map')
@click.option('--mode', help='Filter by game mode')
def team_stats(team: str, map_name: str, mode: str):
    """View team statistics by map-mode combinations"""
    try:
        db = DatabaseManager()
        
        # Get map-mode stats
        stats = db.get_team_map_mode_stats(team, map_name, mode)
        
        if not stats:
            click.echo(f"No stats found for {team}")
            if map_name:
                click.echo(f"  Map filter: {map_name}")
            if mode:
                click.echo(f"  Mode filter: {mode}")
            return
        
        click.echo(f"\n{team} Statistics:")
        click.echo("=" * 80)
        
        for stat in stats:
            click.echo(f"\n{stat['mode']} on {stat['map_name']}:")
            click.echo(f"  Record: {stat['wins']}-{stat['losses']} ({stat['win_rate']:.1f}% win rate)")
            click.echo(f"  Avg Score For: {stat['avg_score_for']:.1f}")
            click.echo(f"  Avg Score Against: {stat['avg_score_against']:.1f}")
            click.echo(f"  Total Played: {stat['total_played']}")
            click.echo(f"  Last Played: {stat['last_played']}")
        
    except Exception as e:
        logger.error(f"Stats lookup failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
def teams():
    """List all teams in the database"""
    try:
        db = DatabaseManager()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT team_a FROM matches UNION SELECT DISTINCT team_b FROM matches ORDER BY team_a")
        teams_list = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not teams_list:
            click.echo("No teams found in database. Import some matches first.")
            return
        
        click.echo(f"\nTeams in database ({len(teams_list)}):")
        for team in teams_list:
            click.echo(f"  - {team}")
            
    except Exception as e:
        logger.error(f"Teams lookup failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--player', help='Filter by specific player name')
@click.option('--team', help='Filter by team')
@click.option('--mode', help='Filter by game mode (Hardpoint, Search & Destroy, etc.)')
@click.option('--map', 'map_name', help='Filter by map name')
@click.option('--limit', default=10, help='Number of players to show (default: 10)')
@click.option('--sort-by', type=click.Choice(['rating', 'kd', 'kills', 'damage']), default='rating', help='Sort by stat')
def player_stats(player: str, team: str, mode: str, map_name: str, limit: int, sort_by: str):
    """View player statistics (overall, by mode, or by map-mode combo)"""
    try:
        db = DatabaseManager()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        if player:
            # Get specific player - show different views based on filters
            if mode and map_name:
                # Map-mode combo stats
                cursor.execute("""
                    SELECT * FROM player_map_mode_stats 
                    WHERE player_name = ? AND mode = ? AND map_name = ?
                """, (player, mode, map_name))
                rows = cursor.fetchall()
                
                if not rows:
                    click.echo(f"No stats found for {player} on {mode} {map_name}")
                    conn.close()
                    return
                
                row = dict(rows[0])
                click.echo(f"\n{player} - {mode} on {map_name}:")
                click.echo("=" * 80)
                click.echo(f"  Maps Played: {row['maps_played']}")
                click.echo(f"  Avg K/D: {row['avg_kd']:.2f}")
                click.echo(f"  Avg Kills: {row['avg_kills']:.1f}")
                click.echo(f"  Avg Deaths: {row['avg_deaths']:.1f}")
                click.echo(f"  Avg Damage: {row['avg_damage']:.1f}")
                click.echo(f"  Avg Rating: {row['avg_rating']:.2f}")
                
            elif mode:
                # Mode stats
                cursor.execute("""
                    SELECT * FROM player_mode_stats 
                    WHERE player_name = ? AND mode = ?
                """, (player, mode))
                rows = cursor.fetchall()
                
                if not rows:
                    click.echo(f"No {mode} stats found for {player}")
                    conn.close()
                    return
                
                row = dict(rows[0])
                click.echo(f"\n{player} - {mode} Stats:")
                click.echo("=" * 80)
                click.echo(f"  Maps Played: {row['maps_played']}")
                click.echo(f"  Avg K/D: {row['avg_kd']:.2f}")
                click.echo(f"  Avg Kills: {row['avg_kills']:.1f}")
                click.echo(f"  Avg Deaths: {row['avg_deaths']:.1f}")
                click.echo(f"  Avg Damage: {row['avg_damage']:.1f}")
                click.echo(f"  Avg Rating: {row['avg_rating']:.2f}")
                click.echo(f"  Total Kills: {row['total_kills']}")
                click.echo(f"  Total Deaths: {row['total_deaths']}")
                
            else:
                # Overall stats
                cursor.execute("SELECT * FROM player_stats WHERE player_name = ?", (player,))
                players = cursor.fetchall()
                
                if not players:
                    click.echo(f"No stats found for player: {player}")
                    conn.close()
                    return
                
                player_data = dict(players[0])
                click.echo(f"\n{player_data['player_name']} Statistics:")
                click.echo("=" * 80)
                click.echo(f"  Current Team: {player_data['current_team']}")
                click.echo(f"  Total Matches: {player_data['total_matches']}")
                click.echo(f"  Avg K/D: {player_data['avg_kd']:.2f}")
                click.echo(f"  Avg Kills: {player_data['avg_kills']:.1f}")
                click.echo(f"  Avg Deaths: {player_data['avg_deaths']:.1f}")
                click.echo(f"  Avg Damage: {player_data['avg_damage']:.1f}")
                click.echo(f"  Avg Rating: {player_data['avg_rating']:.2f}")
                click.echo(f"  Total Kills: {player_data['total_kills']}")
                click.echo(f"  Total Deaths: {player_data['total_deaths']}")
                click.echo(f"  Total Damage: {player_data['total_damage']}")
        else:
            # List multiple players with optional filters
            if mode and map_name:
                # Query map-mode combo stats
                query = "SELECT * FROM player_map_mode_stats WHERE mode = ? AND map_name = ?"
                params = [mode, map_name]
                
                sort_column_map = {
                    'rating': 'avg_rating',
                    'kd': 'avg_kd',
                    'kills': 'avg_kills',
                    'damage': 'avg_damage'
                }
                query += f" ORDER BY {sort_column_map[sort_by]} DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                players = cursor.fetchall()
                
                if not players:
                    click.echo(f"No stats found for {mode} on {map_name}")
                    conn.close()
                    return
                
                title = f"Top {len(players)} Players - {mode} on {map_name}"
                click.echo(f"\n{title}")
                click.echo("=" * 100)
                click.echo(f"{'Player':<20} {'Maps':<6} {'K/D':<8} {'Kills':<8} {'Deaths':<8} {'Damage':<10} {'Rating':<8}")
                click.echo("-" * 100)
                
                for row in players:
                    player_data = dict(row)
                    click.echo(
                        f"{player_data['player_name']:<20} "
                        f"{player_data['maps_played']:<6} "
                        f"{player_data['avg_kd']:<8.2f} "
                        f"{player_data['avg_kills']:<8.1f} "
                        f"{player_data['avg_deaths']:<8.1f} "
                        f"{player_data['avg_damage']:<10.0f} "
                        f"{player_data['avg_rating']:<8.2f}"
                    )
                    
            elif mode:
                # Query mode stats
                query = "SELECT * FROM player_mode_stats WHERE mode = ?"
                params = [mode]
                
                sort_column_map = {
                    'rating': 'avg_rating',
                    'kd': 'avg_kd',
                    'kills': 'avg_kills',
                    'damage': 'avg_damage'
                }
                query += f" ORDER BY {sort_column_map[sort_by]} DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                players = cursor.fetchall()
                
                if not players:
                    click.echo(f"No {mode} stats found")
                    conn.close()
                    return
                
                title = f"Top {len(players)} Players - {mode}"
                click.echo(f"\n{title}")
                click.echo("=" * 100)
                click.echo(f"{'Player':<20} {'Maps':<6} {'K/D':<8} {'Kills':<8} {'Deaths':<8} {'Damage':<10} {'Rating':<8}")
                click.echo("-" * 100)
                
                for row in players:
                    player_data = dict(row)
                    click.echo(
                        f"{player_data['player_name']:<20} "
                        f"{player_data['maps_played']:<6} "
                        f"{player_data['avg_kd']:<8.2f} "
                        f"{player_data['avg_kills']:<8.1f} "
                        f"{player_data['avg_deaths']:<8.1f} "
                        f"{player_data['avg_damage']:<10.0f} "
                        f"{player_data['avg_rating']:<8.2f}"
                    )
                    
            else:
                # Query overall stats
                query = "SELECT * FROM player_stats"
                params = []
                
                if team:
                    query += " WHERE current_team = ?"
                    params.append(team)
                
                sort_column_map = {
                    'rating': 'avg_rating',
                    'kd': 'avg_kd',
                    'kills': 'avg_kills',
                    'damage': 'avg_damage'
                }
                query += f" ORDER BY {sort_column_map[sort_by]} DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                players = cursor.fetchall()
                
                if not players:
                    click.echo("No player stats found in database.")
                    conn.close()
                    return
                
                title = f"Top {len(players)} Players"
                if team:
                    title += f" ({team})"
                
                click.echo(f"\n{title}")
                click.echo("=" * 100)
                click.echo(f"{'Player':<20} {'Team':<20} {'Matches':<8} {'K/D':<8} {'Kills':<8} {'Deaths':<8} {'Damage':<10} {'Rating':<8}")
                click.echo("-" * 100)
                
                for row in players:
                    player_data = dict(row)
                    click.echo(
                        f"{player_data['player_name']:<20} "
                        f"{player_data['current_team']:<20} "
                        f"{player_data['total_matches']:<8} "
                        f"{player_data['avg_kd']:<8.2f} "
                        f"{player_data['avg_kills']:<8.1f} "
                        f"{player_data['avg_deaths']:<8.1f} "
                        f"{player_data['avg_damage']:<10.0f} "
                        f"{player_data['avg_rating']:<8.2f}"
                    )
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Player stats lookup failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


if __name__ == "__main__":
    cli()
