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
@click.option('--generate-graphic', '-g', is_flag=True, help='Generate prediction graphic')
@click.option('--output-dir', default='outputs', help='Directory for generated graphics')
def predict(team_a: str, team_b: str, generate_graphic: bool, output_dir: str):
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
        click.echo(f"    Recent Form (Momentum): {stats_a['momentum']:.3f} {'🔥' if stats_a['momentum'] > 0.3 else '❄️' if stats_a['momentum'] < -0.3 else '='}")
        click.echo(f"    Roster Quality:")
        click.echo(f"      Avg K/D: {stats_a['roster_quality']['avg_kd']}")
        click.echo(f"      Avg Rating: {stats_a['roster_quality']['avg_rating']}")
        click.echo(f"      Avg Damage: {stats_a['roster_quality']['avg_damage']:.0f}")
        
        click.echo(f"\n  {team_b}:")
        click.echo(f"    Team Chemistry:")
        click.echo(f"      Weighted Matches: {stats_b['weighted_matches']} ({stats_b['matches_played']} total)")
        click.echo(f"      Win Rate: {stats_b['win_rate']}%")
        click.echo(f"      Map Win Rate: {stats_b['map_win_rate']}%")
        click.echo(f"    Recent Form (Momentum): {stats_b['momentum']:.3f} {'🔥' if stats_b['momentum'] > 0.3 else '❄️' if stats_b['momentum'] < -0.3 else '='}")
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
        
        # Generate graphic if requested
        if generate_graphic:
            try:
                from src.utils.graphics_generator import generate_prediction_graphic
                click.echo("Generating prediction graphic...")
                graphic_path = generate_prediction_graphic(result, output_dir=output_dir)
                click.echo(f"[SUCCESS] Graphic saved to: {graphic_path}\n")
                logger.info(f"Generated graphic: {graphic_path}")
            except Exception as graphic_error:
                logger.error(f"Graphic generation failed: {str(graphic_error)}")
                click.echo(f"[WARNING] Failed to generate graphic: {str(graphic_error)}\n", err=True)
        
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


@cli.command()
@click.option('--force', is_flag=True, help='Recalculate even if Elo ratings exist')
def init_elo(force: bool):
    """Initialize Elo rating system from match history"""
    from src.predictor import EloPredictor
    
    logger.info("Initializing Elo rating system...")
    click.echo("\nInitializing Elo rating system from match history...")
    click.echo("This will process all matches in chronological order.\n")
    
    try:
        elo = EloPredictor()
        elo.initialize_from_database(force=force)
        
        # Show top ratings
        ratings = elo.get_all_ratings()
        
        click.echo("\n[SUCCESS] Elo ratings initialized!")
        click.echo(f"\nTop 10 Team Rosters by Elo Rating:")
        click.echo("=" * 80)
        
        for i, rating_data in enumerate(ratings[:10], 1):
            roster_str = ", ".join(rating_data['roster'])
            click.echo(
                f"{i:2d}. {rating_data['team']:<25} "
                f"Rating: {rating_data['rating']:7.1f}  "
                f"Matches: {rating_data['matches']:3d}  "
                f"Last: {rating_data['last_update']}"
            )
            click.echo(f"    Roster: {roster_str}")
        
    except Exception as e:
        logger.error(f"Elo initialization failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--min-matches', default=2, help='Minimum matches required for training data')
def train_ml(min_matches: int):
    """Train the Machine Learning prediction model"""
    from src.predictor import MLPredictor
    
    logger.info("Training ML prediction model...")
    click.echo("\nTraining Machine Learning model...")
    click.echo("This will use historical match data to learn optimal feature weights.\n")
    
    try:
        ml = MLPredictor()
        results = ml.train(min_matches=min_matches)
        
        click.echo(f"\n[SUCCESS] ML model trained!")
        click.echo(f"\nTraining Results:")
        click.echo(f"  Training samples: {results['training_samples']}")
        click.echo(f"  Skipped matches: {results['skipped_matches']}")
        click.echo(f"  Training accuracy: {results['training_accuracy']:.1%}")
        
        click.echo(f"\nFeature Importance (Model Coefficients):")
        click.echo("=" * 60)
        for feature, importance in results['feature_importance'].items():
            direction = "→" if importance > 0 else "←"
            click.echo(f"  {feature:<30} {direction} {importance:+.4f}")
        
        click.echo("\nModel saved and ready for predictions!")
        
    except Exception as e:
        logger.error(f"ML training failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--limit', default=None, type=int, help='Limit number of teams shown (default: all)')
@click.option('--min-matches', default=1, help='Only show teams with at least this many matches')
def show_elo(limit: int, min_matches: int):
    """Show current Elo ratings for all teams"""
    from src.predictor import EloPredictor
    
    logger.info("Displaying Elo ratings...")
    
    try:
        elo = EloPredictor()
        ratings = elo.get_all_ratings()
        
        # Filter by minimum matches
        if min_matches > 1:
            ratings = [r for r in ratings if r['matches'] >= min_matches]
        
        # Apply limit
        if limit:
            ratings = ratings[:limit]
        
        click.echo(f"\n{'='*80}")
        click.echo(f"ELO RATINGS (Sorted by Rating)")
        click.echo(f"{'='*80}\n")
        
        if not ratings:
            click.echo("No Elo ratings found. Run 'python main.py init-elo' first.")
            return
        
        click.echo(f"{'Rank':<6}{'Team':<25}{'Rating':<10}{'Matches':<10}{'Last Update'}")
        click.echo("-" * 80)
        
        for i, rating_data in enumerate(ratings, 1):
            roster_str = ", ".join(rating_data['roster'][:3])  # Show first 3 players
            if len(rating_data['roster']) > 3:
                roster_str += "..."
            
            click.echo(
                f"{i:<6}{rating_data['team']:<25}{rating_data['rating']:>7.1f}   "
                f"{rating_data['matches']:>3}        {rating_data['last_update']}"
            )
            click.echo(f"      Roster: {roster_str}")
        
        click.echo(f"\n{'='*80}")
        click.echo(f"Total teams: {len(ratings)}")
        click.echo(f"{'='*80}\n")
        
    except Exception as e:
        logger.error(f"Show Elo failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--team-a', required=True, help='First team name')
@click.option('--team-b', required=True, help='Second team name')
def compare_predictions(team_a: str, team_b: str):
    """Compare predictions from all three models"""
    from src.predictor import EnsemblePredictor
    
    logger.info(f"Comparing predictions: {team_a} vs {team_b}")
    click.echo(f"\n{'='*80}")
    click.echo(f"PREDICTION COMPARISON: {team_a} vs {team_b}")
    click.echo(f"{'='*80}\n")
    
    try:
        ensemble = EnsemblePredictor()
        results = ensemble.predict_all(team_a, team_b)
        
        # Display each prediction
        click.echo("INDIVIDUAL MODEL PREDICTIONS:")
        click.echo("-" * 80)
        
        predictions = results['predictions']
        
        for model_name, pred in predictions.items():
            if 'error' in pred:
                click.echo(f"\n{model_name.upper()}: ERROR - {pred['error']}")
                continue
            
            click.echo(f"\n{pred['method']}:")
            click.echo(f"  {team_a}: {pred['team_a_probability']}%")
            click.echo(f"  {team_b}: {pred['team_b_probability']}%")
            click.echo(f"  Winner: {pred['predicted_winner']} ({pred['predicted_score']})")
            click.echo(f"  Confidence: {pred['confidence']:.1f}%")
            
            # Show model-specific info
            if model_name == 'elo':
                click.echo(f"  {team_a} Rating: {pred['team_a_rating']}")
                click.echo(f"  {team_b} Rating: {pred['team_b_rating']}")
        
        # Display ensemble prediction
        if 'ensemble' in results and 'error' not in results['ensemble']:
            ens = results['ensemble']
            click.echo(f"\n{'='*80}")
            click.echo(f"ENSEMBLE PREDICTION (Weighted Average):")
            click.echo(f"{'='*80}")
            click.echo(f"  {team_a}: {ens['team_a_probability']}%")
            click.echo(f"  {team_b}: {ens['team_b_probability']}%")
            click.echo(f"  Winner: {ens['predicted_winner']} ({ens['predicted_score']})")
            click.echo(f"  Confidence: {ens['confidence']:.1f}%")
            click.echo(f"  Models used: {', '.join(ens['models_used'])}")
            click.echo(f"  Weights: {ens['weights_used']}")
            click.echo(f"  Agreement: {'✓ All models agree' if ens['models_agree'] else '⚠ Models disagree'}")
        
        click.echo(f"\n{'='*80}\n")
        
    except Exception as e:
        logger.error(f"Comparison failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--team-a', required=True, help='First team name')
@click.option('--team-b', required=True, help='Second team name')
@click.option('--date', required=True, help='Match date (YYYY-MM-DD)')
@click.option('--notes', help='Optional notes about the prediction')
def save_prediction(team_a: str, team_b: str, date: str, notes: str):
    """Save prediction before a match for accuracy tracking"""
    from src.predictor import EnsemblePredictor
    from src.predictor.accuracy_tracker import AccuracyTracker
    
    logger.info(f"Saving prediction: {team_a} vs {team_b} on {date}")
    
    try:
        # Generate predictions
        ensemble = EnsemblePredictor()
        results = ensemble.predict_all(team_a, team_b)
        
        # Save to tracker
        tracker = AccuracyTracker()
        success = tracker.save_prediction(team_a, team_b, results, date, notes)
        
        if success:
            ens = results['ensemble']
            click.echo(f"\n[✓] Prediction saved for {date}:")
            click.echo(f"  {ens['predicted_winner']} wins {ens['predicted_score']}")
            click.echo(f"  Probability: {ens['team_a_probability']:.1f}% vs {ens['team_b_probability']:.1f}%")
            click.echo(f"  Confidence: {ens['confidence']:.1f}%\n")
        else:
            click.echo("[ERROR] Failed to save prediction", err=True)
            
    except Exception as e:
        logger.error(f"Save prediction failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--team-a', required=True, help='First team name')
@click.option('--team-b', required=True, help='Second team name')
@click.option('--date', required=True, help='Match date (YYYY-MM-DD)')
@click.option('--winner', required=True, help='Actual winner')
@click.option('--score', required=True, help='Actual score (e.g., 3-1)')
def record_result(team_a: str, team_b: str, date: str, winner: str, score: str):
    """Record actual match result for accuracy tracking"""
    from src.predictor.accuracy_tracker import AccuracyTracker
    
    logger.info(f"Recording result: {winner} won {score}")
    
    try:
        tracker = AccuracyTracker()
        success = tracker.record_result(team_a, team_b, date, winner, score)
        
        if success:
            click.echo(f"\n[✓] Result recorded: {winner} won {score}\n")
        else:
            click.echo("[ERROR] Failed to record result (no matching prediction found)", err=True)
            
    except Exception as e:
        logger.error(f"Record result failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--min-predictions', default=1, help='Minimum predictions needed to show stats')
def show_accuracy(min_predictions: int):
    """Show prediction accuracy statistics"""
    from src.predictor.accuracy_tracker import AccuracyTracker
    
    logger.info("Displaying accuracy statistics...")
    
    try:
        tracker = AccuracyTracker()
        stats = tracker.get_accuracy_stats(min_predictions)
        
        if 'message' in stats:
            click.echo(f"\n{stats['message']}")
            click.echo(f"Predictions recorded: {stats['total_predictions']}\n")
            return
        
        click.echo(f"\n{'='*80}")
        click.echo("PREDICTION ACCURACY STATISTICS")
        click.echo(f"{'='*80}\n")
        
        models = ['statistical', 'elo', 'ml', 'ensemble']
        model_names = {
            'statistical': 'Statistical Model',
            'elo': 'Elo Rating System',
            'ml': 'Machine Learning',
            'ensemble': 'Ensemble (Combined)'
        }
        
        for model in models:
            if stats[model]['total'] > 0:
                click.echo(f"{model_names[model]}:")
                click.echo(f"  Total predictions: {stats[model]['total']}")
                click.echo(f"  Winner accuracy: {stats[model]['accuracy']:.1f}% "
                          f"({stats[model]['correct']}/{stats[model]['total']})")
                click.echo(f"  Exact score accuracy: {stats[model]['score_accuracy']:.1f}% "
                          f"({stats[model]['correct_score']}/{stats[model]['total']})")
                
                if model == 'ensemble' and stats[model].get('high_conf_total', 0) > 0:
                    click.echo(f"  High confidence (>30%) accuracy: {stats[model]['high_conf_accuracy']:.1f}% "
                              f"({stats[model]['high_conf_correct']}/{stats[model]['high_conf_total']})")
                click.echo()
        
        # Show recent predictions
        recent = tracker.get_recent_predictions(5)
        if recent:
            click.echo(f"{'='*80}")
            click.echo("RECENT PREDICTIONS:")
            click.echo(f"{'='*80}\n")
            
            for pred in recent:
                result_icon = "✓" if pred['correct'] else "✗"
                click.echo(f"{result_icon} {pred['match_date']}: {pred['team_a']} vs {pred['team_b']}")
                click.echo(f"  Predicted: {pred['predicted_winner']} {pred['predicted_score']}")
                click.echo(f"  Actual: {pred['actual_winner']} {pred['actual_score']}")
                click.echo()
        
        click.echo(f"{'='*80}\n")
        
    except Exception as e:
        logger.error(f"Show accuracy failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
def pending_predictions():
    """Show predictions awaiting results"""
    from src.predictor.accuracy_tracker import AccuracyTracker
    
    logger.info("Fetching pending predictions...")
    
    try:
        tracker = AccuracyTracker()
        pending = tracker.get_pending_predictions()
        
        if not pending:
            click.echo("\nNo pending predictions.\n")
            return
        
        click.echo(f"\n{'='*80}")
        click.echo(f"PENDING PREDICTIONS ({len(pending)} matches)")
        click.echo(f"{'='*80}\n")
        
        for pred in pending:
            click.echo(f"📅 {pred['match_date']}: {pred['team_a']} vs {pred['team_b']}")
            click.echo(f"   Prediction: {pred['predicted_winner']} wins {pred['predicted_score']}")
            click.echo(f"   Confidence: {pred['confidence']:.1f}%")
            click.echo()
        
        click.echo(f"{'='*80}")
        click.echo(f"Use 'record-result' command to log actual results\n")
        
    except Exception as e:
        logger.error(f"Pending predictions failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)


@cli.command()
@click.option('--start-match', default=20, help='Start backtesting from this match number')
@click.option('--show-errors', is_flag=True, help='Show matches where all models were wrong')
def backtest(start_match: int, show_errors: bool):
    """Validate model accuracy on historical matches"""
    from src.predictor.backtester import Backtester
    
    logger.info("Running backtest on historical data...")
    click.echo("\n" + "="*80)
    click.echo("BACKTESTING PREDICTION MODELS")
    click.echo("="*80)
    
    try:
        backtester = Backtester()
        results = backtester.run_backtest(start_match=start_match)
        
        if 'error' in results:
            click.echo(f"\n[ERROR] {results['error']}\n")
            return
        
        click.echo(f"\n{'='*80}")
        click.echo("BACKTEST RESULTS")
        click.echo(f"{'='*80}\n")
        click.echo(f"Total matches tested: {results['total_matches']}\n")
        
        # Show accuracy for each model
        models = {
            'statistical': 'Statistical Model',
            'elo': 'Elo Rating System',
            'ml': 'Machine Learning',
            'ensemble': 'Ensemble (Combined)'
        }
        
        for model_key, model_name in models.items():
            acc = results['accuracy'][model_key]
            if acc['total'] > 0:
                click.echo(f"{model_name}:")
                click.echo(f"  Winner predictions: {acc['accuracy_pct']:.1f}% "
                          f"({acc['correct']}/{acc['total']})")
                click.echo(f"  Exact score predictions: {acc['score_accuracy_pct']:.1f}% "
                          f"({acc['correct_score']}/{acc['total']})")
                click.echo()
        
        # Find best and worst models
        best_model = max(results['accuracy'].items(), 
                        key=lambda x: x[1].get('accuracy_pct', 0))
        click.echo(f"🏆 Best Model: {models[best_model[0]]} "
                  f"({best_model[1]['accuracy_pct']:.1f}% accurate)")
        
        # Show matches where all models failed
        if show_errors:
            worst = backtester.get_worst_predictions(results, limit=5)
            if worst:
                click.echo(f"\n{'='*80}")
                click.echo("MATCHES WHERE ALL MODELS WERE WRONG:")
                click.echo(f"{'='*80}\n")
                
                for pred in worst:
                    click.echo(f"❌ {pred['date']}: {pred['team_a']} vs {pred['team_b']}")
                    click.echo(f"   Actual: {pred['actual_winner']} won {pred['actual_score']}")
                    
                    # Show what each model predicted
                    for model in ['ensemble', 'statistical', 'elo', 'ml']:
                        if model in pred['predictions']:
                            p = pred['predictions'][model]
                            click.echo(f"   {model.title()}: {p['winner']} {p['score']}")
                    click.echo()
        
        click.echo(f"{'='*80}\n")
        
        # Insights
        click.echo("💡 INSIGHTS:")
        avg_accuracy = sum(r['accuracy_pct'] for r in results['accuracy'].values() 
                          if 'accuracy_pct' in r) / len(results['accuracy'])
        click.echo(f"  • Average model accuracy: {avg_accuracy:.1f}%")
        click.echo(f"  • Ensemble is {'better' if results['accuracy']['ensemble']['accuracy_pct'] > avg_accuracy else 'worse'} than average")
        click.echo(f"  • Score predictions are harder ({results['accuracy']['ensemble']['score_accuracy_pct']:.1f}% vs {results['accuracy']['ensemble']['accuracy_pct']:.1f}%)")
        click.echo()
        
    except Exception as e:
        logger.error(f"Backtest failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)
        import traceback
        traceback.print_exc()


@cli.command()
@click.option('--team-a', required=True, help='First team name')
@click.option('--team-b', required=True, help='Second team name')
def predict_maps(team_a: str, team_b: str):
    """Predict match outcome map-by-map"""
    from src.predictor.map_predictor import MapPredictor
    
    logger.info(f"Predicting maps: {team_a} vs {team_b}")
    
    try:
        predictor = MapPredictor()
        result = predictor.predict_series(team_a, team_b)
        
        click.echo(f"\n{'='*80}")
        click.echo(f"MAP-BY-MAP PREDICTION: {team_a} vs {team_b}")
        click.echo(f"{'='*80}\n")
        
        # Show overall prediction
        click.echo(f"🎯 OVERALL PREDICTION: {result['predicted_winner']} wins {result['predicted_score']}")
        click.echo(f"   Confidence: {result['confidence']:.1f}%")
        click.echo(f"   Data Quality: {result['data_quality'].upper()}\n")
        
        # Show map-by-map predictions
        click.echo(f"{'='*80}")
        click.echo("MAP-BY-MAP BREAKDOWN:")
        click.echo(f"{'='*80}\n")
        
        for i, map_pred in enumerate(result['map_predictions'], 1):
            winner_icon = "🏆" if map_pred['predicted_winner'] == result['predicted_winner'] else "  "
            click.echo(f"{winner_icon} Map {i} - {map_pred['mode']}")
            if map_pred['map_name'] != 'Unknown':
                click.echo(f"   Map: {map_pred['map_name']}")
            
            click.echo(f"   {team_a}: {map_pred['team_a_probability']}% ({map_pred['team_a_matches']} matches)")
            click.echo(f"   {team_b}: {map_pred['team_b_probability']}% ({map_pred['team_b_matches']} matches)")
            click.echo(f"   Prediction: {map_pred['predicted_winner']} wins")
            click.echo(f"   Confidence: {map_pred['confidence']:.1f}% | Quality: {map_pred['data_quality']}")
            click.echo()
        
        click.echo(f"{'='*80}\n")
        
        # Warnings about data quality
        low_quality_maps = [p for p in result['map_predictions'] if p['data_quality'] in ['low', 'no_data']]
        if low_quality_maps:
            click.echo(f"⚠️  WARNING: {len(low_quality_maps)} maps have limited historical data")
            click.echo(f"   Predictions for those maps are less reliable.\n")
        
    except Exception as e:
        logger.error(f"Map prediction failed: {str(e)}")
        click.echo(f"[ERROR] {str(e)}", err=True)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    cli()
