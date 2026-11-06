"""
Player model representing a CDL player
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Player:
    """Represents a Call of Duty League player"""
    
    name: str
    team: str
    
    # Performance metrics
    kd_history: List[float] = field(default_factory=list)
    bp_rating_history: List[float] = field(default_factory=list)
    
    @property
    def avg_kd(self) -> float:
        """Calculate average K/D ratio"""
        return sum(self.kd_history) / len(self.kd_history) if self.kd_history else 0.0
    
    @property
    def avg_bp_rating(self) -> float:
        """Calculate average Breaking Point rating"""
        return sum(self.bp_rating_history) / len(self.bp_rating_history) if self.bp_rating_history else 0.0
    
    @property
    def recent_form(self) -> float:
        """Get recent form (last 5 matches K/D average)"""
        recent = self.kd_history[-5:] if len(self.kd_history) >= 5 else self.kd_history
        return sum(recent) / len(recent) if recent else 0.0
    
    def add_performance(self, kd: float, bp_rating: float) -> None:
        """Add a match performance"""
        self.kd_history.append(kd)
        self.bp_rating_history.append(bp_rating)
    
    def __repr__(self) -> str:
        return f"Player({self.name}, {self.team}, K/D: {self.avg_kd:.2f})"
