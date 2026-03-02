"""
Enhanced match scraper for BreakingPoint.gg that handles dynamic tabs
"""
from typing import Dict, List
from datetime import datetime
import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper


class EnhancedMatchScraper(BaseScraper):
    """Enhanced scraper that handles tab-based content for map details"""
    
    def scrape(self, url: str) -> Dict:
        """
        Scrape a match page with enhanced map extraction
        
        Args:
            url: URL of the match page
        
        Returns:
            Dictionary containing complete match data
        """
        self._init_driver()
        match_id = self._extract_match_id(url)
        
        try:
            self.logger.info(f"Loading match page: {url}")
            self.driver.get(url)
            time.sleep(5)  # Wait longer for dynamic content to load
            
            # Get the full page source
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            
            # Extract basic info
            match_info = self._extract_match_info_enhanced(soup, match_id, url)
            
            # Extract map results from the visible content
            map_results = self._extract_maps_from_overview(soup)
            
            # Extract player stats
            player_stats = self._extract_player_stats_enhanced(soup)
            
            return {
                "match_info": match_info,
                "map_results": map_results,
                "player_stats": player_stats
            }
            
        finally:
            self._close_driver()
    
    def _extract_match_id(self, url: str) -> str:
        """Extract match ID from URL"""
        match = re.search(r'/match/(\d+)/', url)
        return match.group(1) if match else "unknown"
    
    def _extract_match_info_enhanced(self, soup: BeautifulSoup, match_id: str, url: str) -> Dict:
        """Extract match information"""
        # Get team names from links
        team_links = soup.find_all("a", href=re.compile(r'/teams/\d+'))
        team_a = team_links[0].get_text(strip=True) if len(team_links) > 0 else "Team A"
        team_b = team_links[1].get_text(strip=True) if len(team_links) > 1 else "Team B"
        
        # Get tournament
        event_link = soup.find("a", href=re.compile(r'/events/\d+'))
        tournament = event_link.get_text(strip=True) if event_link else "Unknown"
        
        # Get date (website uses DD/MM/YYYY format)
        date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', soup.get_text())
        if date_match:
            day, month, year = date_match.groups()  # Fixed: website uses DD/MM/YYYY
            match_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        else:
            match_date = datetime.now().strftime("%Y-%m-%d")
        
        return {
            "match_id": match_id,
            "team_a": team_a,
            "team_b": team_b,
            "tournament": tournament,
            "date": match_date,
            "url": url
        }
    
    def _extract_maps_from_overview(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract map results by parsing the plain text content"""
        maps = []
        
        try:
            # Get all text from the page
            text = soup.get_text()
            
            # Pattern matches like: "HardpointExposure250-231" or "Search & DestroyDen5-6"
            # The text appears to have no spaces between mode and map name
            patterns = [
                # Hardpoint with map name and scores (100-250 range)
                (r'Hardpoint([A-Z][a-z]+)(\d{2,3})-(\d{2,3})', 'Hardpoint'),
                # Search & Destroy with map name and scores (0-6 range)
                (r'Search & Destroy([A-Z][a-z]+)(\d{1})-(\d{1})', 'Search & Destroy'),
                # Overload with map name and scores (0-5 range) 
                (r'Overload([A-Z][a-z]+)(\d{1})-(\d{1})', 'Overload'),
            ]
            
            for pattern, mode in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    map_name = match.group(1)
                    score_a = int(match.group(2))
                    score_b = int(match.group(3))
                    
                    map_data = {
                        "mode": mode,
                        "map_name": map_name,
                        "team_a_score": score_a,
                        "team_b_score": score_b
                    }
                    
                    # Avoid duplicates
                    if map_data not in maps:
                        maps.append(map_data)
                        self.logger.info(f"Found {mode} on {map_name}: {score_a}-{score_b}")
            
            self.logger.info(f"Extracted {len(maps)} maps")
            return maps
            
        except Exception as e:
            self.logger.error(f"Error extracting maps: {str(e)}")
            return []
    
    def _old_extract_maps(self):
        """Old regex-based method - kept for reference"""
        try:
            text_content = soup.get_text()
            map_names = ['Exposure', 'Den', 'Overload', 'Colossus', 'Scar', 'Protocol', 'Skyline', 'Vault', 'Highrise']
            
            # Find all occurrences of game modes with their context
            # Pattern: Mode name followed by map name and scores within next ~100 chars
            mode_patterns = [
                (r'Hardpoint\s+(\w+)\s+(\d{2,3})\s*[-–]\s*(\d{2,3})', 'Hardpoint'),
                (r'Search\s*&?\s*Destroy\s+(\w+)\s+(\d{1})\s*[-–]\s*(\d{1})', 'Search & Destroy'),
                (r'Control\s+(\w+)\s+(\d{1})\s*[-–]\s*(\d{1})', 'Control'),
            ]
            
            for pattern, mode in mode_patterns:
                matches = re.finditer(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    map_name = match.group(1)
                    score_a = int(match.group(2))
                    score_b = int(match.group(3))
                    
                    # Validate map name
                    if map_name not in map_names:
                        # Try to find it in the context
                        for name in map_names:
                            if name.lower() in match.group(0).lower():
                                map_name = name
                                break
                    
                    # Validate scores
                    valid = False
                    if mode == 'Hardpoint' and (score_a >= 50 or score_b >= 50):
                        valid = True
                    elif mode == 'Search & Destroy' and score_a <= 6 and score_b <= 6:
                        valid = True
                    elif mode == 'Control' and score_a <= 5 and score_b <= 5:
                        valid = True
                    
                    if valid:
                        map_data = {
                            "mode": mode,
                            "map_name": map_name,
                            "team_a_score": score_a,
                            "team_b_score": score_b
                        }
                        
                        # Avoid exact duplicates
                        if map_data not in maps:
                            maps.append(map_data)
            
            # Limit to 5 maps (best of 5 series)
            maps = maps[:5]
            
            self.logger.info(f"Extracted {len(maps)} maps")
            return maps
            
        except Exception as e:
            self.logger.error(f"Error extracting maps: {str(e)}")
            return []
    
    def _extract_player_stats_enhanced(self, soup: BeautifulSoup) -> Dict[str, List[Dict]]:
        """Extract player statistics by summing individual map performances"""
        stats = {"team_a": [], "team_b": [], "per_map": []}
        
        try:
            # Find all table rows with the GameOverview_tr class
            rows = soup.find_all('tr', class_=re.compile(r'GameOverview_tr'))
            
            self.logger.info(f"Found {len(rows)} GameOverview table rows")
            
            # Dictionary to accumulate stats for each player
            player_data = {}
            team_assignment = {}  # Track which team each player belongs to
            current_team = 'team_a'
            players_in_current_section = 0
            current_map_number = 0
            map_stats_buffer = []  # Buffer to collect stats for current map
            
            for i, row in enumerate(rows):
                cells = row.find_all('td')
                
                # Header rows reset the player count for current section
                if len(cells) == 0:
                    # Save buffered map stats before starting new map
                    if map_stats_buffer:
                        stats['per_map'].extend(map_stats_buffer)
                        map_stats_buffer = []
                    
                    players_in_current_section = 0
                    current_map_number += 1
                    continue
                
                # Player stat rows have 7 or 8 cells depending on game mode
                # Format: Name, K, D, K/D, +/-, DMG, (OBJ/Other), Rating
                if len(cells) >= 7:
                    try:
                        # Extract player name
                        name_elem = cells[0].find('p', class_='mantine-Text-root')
                        if name_elem:
                            player_name = name_elem.get_text(strip=True)
                        else:
                            player_name = cells[0].get_text(strip=True)
                        
                        # Skip invalid names
                        if (len(player_name) < 2 or 
                            player_name in ['Player', 'Team', 'Total', 'Average']):
                            continue
                        
                        # Assign team on first encounter only
                        # First 4 unique players go to team_a, next 4 to team_b
                        if player_name not in team_assignment:
                            if len(team_assignment) < 4:
                                team_assignment[player_name] = 'team_a'
                            else:
                                team_assignment[player_name] = 'team_b'
                        
                        # Track position in current map section to determine team for this stat
                        players_in_current_section += 1
                        if players_in_current_section <= 4:
                            current_team = 'team_a'
                        else:
                            current_team = 'team_b'
                        
                        # Parse stats (handle both 7 and 8 cell formats)
                        kills = int(cells[1].get_text(strip=True))
                        deaths = int(cells[2].get_text(strip=True))
                        kd = float(cells[3].get_text(strip=True))
                        plus_minus = cells[4].get_text(strip=True)
                        damage = int(cells[5].get_text(strip=True).replace(',', ''))
                        
                        # Rating is in cell 7 for 8-cell rows, cell 6 for 7-cell rows
                        if len(cells) >= 8:
                            rating = float(cells[7].get_text(strip=True))
                        else:
                            rating = float(cells[6].get_text(strip=True))
                        
                        # Accumulate stats
                        if player_name not in player_data:
                            player_data[player_name] = {
                                'kills': 0,
                                'deaths': 0,
                                'damage': 0,
                                'ratings': [],
                                'kds': [],
                                'plus_minus': plus_minus  # Take first one
                            }
                        
                        player_data[player_name]['kills'] += kills
                        player_data[player_name]['deaths'] += deaths
                        player_data[player_name]['damage'] += damage
                        player_data[player_name]['ratings'].append(rating)
                        player_data[player_name]['kds'].append(kd)
                        
                        # Store individual map stats
                        map_stats_buffer.append({
                            'map_number': current_map_number,
                            'player_name': player_name,
                            'team': team_assignment[player_name],
                            'kills': kills,
                            'deaths': deaths,
                            'kd': kd,
                            'damage': damage,
                            'rating': rating
                        })
                        
                    except (ValueError, IndexError, AttributeError) as e:
                        self.logger.debug(f"Failed to parse player row: {e}")
                        continue
            
            # Save any remaining buffered map stats
            if map_stats_buffer:
                stats['per_map'].extend(map_stats_buffer)
            
            # Convert accumulated stats to final format
            for player_name, data in player_data.items():
                team = team_assignment.get(player_name, 'team_a')
                
                # Calculate averages
                avg_rating = sum(data['ratings']) / len(data['ratings']) if data['ratings'] else 0.0
                avg_kd = data['kills'] / data['deaths'] if data['deaths'] > 0 else 0.0
                
                player_stats = {
                    "player": player_name,
                    "kills": data['kills'],
                    "deaths": data['deaths'],
                    "kd": round(avg_kd, 2),
                    "plus_minus": data['plus_minus'],
                    "damage": data['damage'],
                    "rating": round(avg_rating, 2)
                }
                
                stats[team].append(player_stats)
                self.logger.info(f"Aggregated {team} player: {player_name} - K:{data['kills']} D:{data['deaths']}")
            
            self.logger.info(f"Extracted stats for {len(stats['team_a'])} team A and {len(stats['team_b'])} team B players")
            
        except Exception as e:
            self.logger.error(f"Error extracting player stats: {str(e)}")
        
        return stats
