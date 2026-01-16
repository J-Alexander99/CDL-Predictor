"""
Match scraper for BreakingPoint.gg match pages
"""
from typing import Dict, List, Optional
from datetime import datetime
import re

from bs4 import BeautifulSoup, Tag

from .base_scraper import BaseScraper
from src.models import Match, MapResult


class MatchScraper(BaseScraper):
    """Scrapes match data from BreakingPoint.gg match pages"""
    
    def scrape(self, url: str) -> Dict:
        """
        Scrape a match page and extract all relevant data
        
        Args:
            url: URL of the match page
        
        Returns:
            Dictionary containing match data, map results, and player stats
        """
        soup = self.fetch_page(url)
        
        # Extract match ID from URL
        match_id = self._extract_match_id(url)
        
        # Extract basic match info
        match_info = self._extract_match_info(soup, match_id, url)
        
        # Extract map results
        map_results = self._extract_map_results(soup)
        
        # Extract player statistics
        player_stats = self._extract_player_stats(soup)
        
        return {
            "match_info": match_info,
            "map_results": map_results,
            "player_stats": player_stats
        }
    
    def _extract_match_id(self, url: str) -> str:
        """Extract match ID from URL"""
        match = re.search(r'/match/(\d+)/', url)
        return match.group(1) if match else "unknown"
    
    def _extract_match_info(self, soup: BeautifulSoup, match_id: str, url: str) -> Dict:
        """Extract basic match information"""
        try:
            # Find team names and scores from the page header
            team_links = soup.find_all("a", href=re.compile(r'/teams/\d+'))
            
            if len(team_links) >= 2:
                team_a = team_links[0].get_text(strip=True)
                team_b = team_links[1].get_text(strip=True)
            else:
                # Fallback: extract from URL
                url_parts = url.split('/')
                match_name = url_parts[-1] if url_parts else ""
                teams = match_name.split('-vs-')[0:2]
                team_a = teams[0].replace('-', ' ') if len(teams) > 0 else "Unknown"
                team_b = teams[1].split('-at-')[0].replace('-', ' ') if len(teams) > 1 else "Unknown"
            
            # Extract final score
            score_elements = soup.find_all("p", class_=re.compile(r'.*'))
            final_score_a = 0
            final_score_b = 0
            
            # Look for the match score near team names
            for elem in soup.find_all(['h1', 'h2', 'div']):
                text = elem.get_text()
                # Pattern like "2 - 3" or "3-2"
                score_match = re.search(r'(\d+)\s*-\s*(\d+)', text)
                if score_match and elem.find_parent():
                    final_score_a = int(score_match.group(1))
                    final_score_b = int(score_match.group(2))
                    break
            
            # Extract tournament/event info
            event_link = soup.find("a", href=re.compile(r'/events/\d+'))
            tournament = event_link.get_text(strip=True) if event_link else "Unknown Tournament"
            
            # Extract date
            date_text = soup.find(text=re.compile(r'\d{1,2}/\d{1,2}/\d{4}'))
            match_date = datetime.now()
            if date_text:
                try:
                    date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', str(date_text))
                    if date_match:
                        month, day, year = date_match.groups()
                        match_date = datetime(int(year), int(month), int(day))
                except:
                    pass
            
            return {
                "match_id": match_id,
                "team_a": team_a,
                "team_b": team_b,
                "team_a_score": final_score_a,
                "team_b_score": final_score_b,
                "tournament": tournament,
                "date": match_date.strftime("%Y-%m-%d"),
                "url": url
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting match info: {str(e)}")
            return {
                "match_id": match_id,
                "team_a": "Unknown",
                "team_b": "Unknown",
                "team_a_score": 0,
                "team_b_score": 0,
                "tournament": "Unknown",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "url": url
            }
    
    def _extract_map_results(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract individual map results"""
        maps = []
        seen_maps = set()  # Track unique maps to avoid duplicates
        
        try:
            # Strategy: Look for specific patterns in the text that represent complete map info
            # Format example: "Hardpoint Exposure 250 - 231"
            
            page_text = soup.get_text()
            
            # Split into lines and look for map patterns
            lines = page_text.split('\n')
            
            mode_pattern = re.compile(r'(Hardpoint|Search\s*&?\s*Destroy|Control)', re.IGNORECASE)
            map_names = ['Exposure', 'Den', 'Overload', 'Colossus', 'Scar', 'Protocol', 'Skyline', 'Vault']
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Check if line contains a game mode
                mode_match = mode_pattern.search(line)
                if mode_match:
                    mode = mode_match.group(1)
                    if "Search" in mode:
                        mode = "Search & Destroy"
                    
                    # Look in the next few lines for map name and scores
                    map_name = "Unknown"
                    score_a = None
                    score_b = None
                    
                    # Check next 5 lines for map name and scores
                    for j in range(i, min(i+6, len(lines))):
                        check_line = lines[j].strip()
                        
                        # Find map name
                        for name in map_names:
                            if name.lower() in check_line.lower():
                                map_name = name
                                break
                        
                        # Find scores - looking for pattern like "250" on one line and "231" on another
                        # or "250 - 231" together
                        score_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', check_line)
                        if score_match:
                            score_a = int(score_match.group(1))
                            score_b = int(score_match.group(2))
                            break
                    
                    # Only add if we found valid scores and haven't seen this exact map before
                    if score_a is not None and score_b is not None:
                        map_key = f"{mode}_{map_name}_{score_a}_{score_b}"
                        if map_key not in seen_maps:
                            seen_maps.add(map_key)
                            maps.append({
                                "mode": mode,
                                "map_name": map_name,
                                "team_a_score": score_a,
                                "team_b_score": score_b
                            })
                
                i += 1
            
            # Deduplicate and limit to 5 maps (typical match is best of 5)
            unique_maps = []
            seen_keys = set()
            for m in maps:
                key = f"{m['mode']}_{m['map_name']}_{m['team_a_score']}_{m['team_b_score']}"
                if key not in seen_keys and len(unique_maps) < 5:
                    seen_keys.add(key)
                    unique_maps.append(m)
            
            self.logger.info(f"Extracted {len(unique_maps)} map results")
            return unique_maps
            
        except Exception as e:
            self.logger.error(f"Error extracting map results: {str(e)}")
            return []
    
    def _extract_player_stats(self, soup: BeautifulSoup) -> Dict[str, List[Dict]]:
        """Extract player statistics from both teams"""
        player_stats = {
            "team_a": [],
            "team_b": []
        }
        
        try:
            # Look for tables with player stats
            # Stats typically include: Player name, Kills, Deaths, K/D, +/-, Damage, etc.
            
            tables = soup.find_all("table")
            
            for table in tables:
                rows = table.find_all("tr")
                
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    
                    if len(cells) >= 6:  # Ensure we have enough columns
                        # Try to extract player data
                        player_data = []
                        for cell in cells:
                            text = cell.get_text(strip=True)
                            player_data.append(text)
                        
                        # Check if this looks like a player row (has a name and numbers)
                        if player_data and player_data[0] and not player_data[0].lower() in ['team', 'player', 'name']:
                            try:
                                # Typical format: [Name, Kills, Deaths, K/D, +/-, Damage, Rating]
                                if len(player_data) >= 7:
                                    stats = {
                                        "player": player_data[0],
                                        "kills": int(player_data[1]) if player_data[1].isdigit() else 0,
                                        "deaths": int(player_data[2]) if player_data[2].isdigit() else 0,
                                        "kd": float(player_data[3]) if self._is_float(player_data[3]) else 0.0,
                                        "plus_minus": player_data[4],
                                        "damage": int(player_data[5].replace(',', '')) if player_data[5].replace(',', '').isdigit() else 0,
                                        "rating": float(player_data[6]) if self._is_float(player_data[6]) else 0.0
                                    }
                                    
                                    # Determine which team (this is simplified - may need refinement)
                                    if len(player_stats["team_a"]) <= len(player_stats["team_b"]):
                                        player_stats["team_a"].append(stats)
                                    else:
                                        player_stats["team_b"].append(stats)
                            except (ValueError, IndexError) as e:
                                continue
            
            # Alternative: Look for specific player stat patterns in text
            if not player_stats["team_a"] and not player_stats["team_b"]:
                self._extract_player_stats_alternative(soup, player_stats)
            
            self.logger.info(f"Extracted stats for {len(player_stats['team_a'])} + {len(player_stats['team_b'])} players")
            
        except Exception as e:
            self.logger.error(f"Error extracting player stats: {str(e)}")
        
        return player_stats
    
    def _extract_player_stats_alternative(self, soup: BeautifulSoup, player_stats: Dict):
        """Alternative method to extract player stats from div/span elements"""
        # Look for patterns like "PlayerName | 89 | 92 | 0.97 | -3 | 12,344 | 0.64"
        all_text = soup.get_text()
        
        # Common CDL player names pattern
        player_pattern = re.compile(r'([A-Za-z0-9]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*([+-]?\d+)\s*\|\s*([\d,]+)\s*\|\s*([\d.]+)')
        
        matches = player_pattern.findall(all_text)
        
        for match in matches:
            try:
                stats = {
                    "player": match[0],
                    "kills": int(match[1]),
                    "deaths": int(match[2]),
                    "kd": float(match[3]),
                    "plus_minus": match[4],
                    "damage": int(match[5].replace(',', '')),
                    "rating": float(match[6])
                }
                
                # Split between teams (first 4 players = team A, next 4 = team B)
                if len(player_stats["team_a"]) < 4:
                    player_stats["team_a"].append(stats)
                else:
                    player_stats["team_b"].append(stats)
            except:
                continue
    
    def _is_float(self, value: str) -> bool:
        """Check if a string can be converted to float"""
        try:
            float(value)
            return True
        except ValueError:
            return False
