"""
Match model representing a CDL match
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class MapResult:
    """Result of a single map in a series"""
    mode: str  # Hardpoint, Search and Destroy, Control
    team_a_score: int
    team_b_score: int
    winner: str


@dataclass
class Match:
    """Represents a Call of Duty League match"""
    
    match_id: str
    team_a: str
    team_b: str
    date: datetime
    match_type: str  # "Online" or "LAN"
    
    # Results
    team_a_score: int = 0
    team_b_score: int = 0
    winner: Optional[str] = None
    
    # Map-by-map results
    map_results: List[MapResult] = field(default_factory=list)
    
    # Additional context
    stage: str = "Regular Season"
    tournament: Optional[str] = None
    
    @property
    def is_completed(self) -> bool:
        """Check if match has been completed"""
        return self.winner is not None
    
    @property
    def total_maps(self) -> int:
        """Total number of maps played"""
        return len(self.map_results)
    
    def add_map_result(self, mode: str, team_a_score: int, team_b_score: int) -> None:
        """Add a map result and update match scores"""
        winner = self.team_a if team_a_score > team_b_score else self.team_b
        
        map_result = MapResult(
            mode=mode,
            team_a_score=team_a_score,
            team_b_score=team_b_score,
            winner=winner
        )
        self.map_results.append(map_result)
        
        # Update match score
        if winner == self.team_a:
            self.team_a_score += 1
        else:
            self.team_b_score += 1
    
    def finalize(self) -> None:
        """Finalize match and determine winner"""
        if self.team_a_score > self.team_b_score:
            self.winner = self.team_a
        elif self.team_b_score > self.team_a_score:
            self.winner = self.team_b
    
    def __repr__(self) -> str:
        if self.is_completed:
            return f"Match({self.team_a} vs {self.team_b}: {self.team_a_score}-{self.team_b_score})"
        return f"Match({self.team_a} vs {self.team_b}, {self.date.strftime('%Y-%m-%d')})"
