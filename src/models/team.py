"""
Team model representing a CDL team
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Team:
    """Represents a Call of Duty League team"""
    
    name: str
    roster: List[str] = field(default_factory=list)
    
    # Performance stats
    wins: int = 0
    losses: int = 0
    
    # Mode-specific records
    hardpoint_record: Dict[str, int] = field(default_factory=lambda: {"wins": 0, "losses": 0})
    search_record: Dict[str, int] = field(default_factory=lambda: {"wins": 0, "losses": 0})
    control_record: Dict[str, int] = field(default_factory=lambda: {"wins": 0, "losses": 0})
    
    # Head-to-head records
    h2h_record: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    @property
    def win_rate(self) -> float:
        """Calculate overall win rate"""
        total_games = self.wins + self.losses
        return (self.wins / total_games * 100) if total_games > 0 else 0.0
    
    def add_match_result(self, won: bool) -> None:
        """Record a match result"""
        if won:
            self.wins += 1
        else:
            self.losses += 1
    
    def add_mode_result(self, mode: str, won: bool) -> None:
        """Record a mode-specific result"""
        mode_map = {
            "Hardpoint": self.hardpoint_record,
            "Search and Destroy": self.search_record,
            "Control": self.control_record
        }
        
        if mode in mode_map:
            if won:
                mode_map[mode]["wins"] += 1
            else:
                mode_map[mode]["losses"] += 1
    
    def update_h2h(self, opponent: str, won: bool) -> None:
        """Update head-to-head record against specific opponent"""
        if opponent not in self.h2h_record:
            self.h2h_record[opponent] = {"wins": 0, "losses": 0}
        
        if won:
            self.h2h_record[opponent]["wins"] += 1
        else:
            self.h2h_record[opponent]["losses"] += 1
    
    def __repr__(self) -> str:
        return f"Team({self.name}, {self.wins}-{self.losses})"
