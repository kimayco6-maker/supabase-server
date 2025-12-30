"""
Data models for the Fishing Game
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Player:
    """Player model"""
    id: str
    username: str
    email: str
    total_catches: int
    total_points: int
    created_at: datetime

@dataclass
class FishSpecies:
    """Fish species model"""
    id: str
    name: str
    rarity: str  # common, uncommon, rare, epic, legendary, mythic
    min_weight: float
    max_weight: float
    base_probability: float
    image_url: Optional[str]
    description: str
    points: int

@dataclass
class Catch:
    """Catch model"""
    id: str
    player_id: str
    fish_species_id: str
    weight: float
    caught_at: datetime
    is_personal_best: bool
    points_earned: int

@dataclass
class CastResult:
    """Result of a fishing cast"""
    success: bool
    fish: Optional[FishSpecies]
    weight: Optional[float]
    points: Optional[int]
    is_personal_best: bool
    message: str

