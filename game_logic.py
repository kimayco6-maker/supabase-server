"""
Game logic for fish generation and catch mechanics
"""
import random
import math
from typing import Optional, Tuple, List, Dict
from models import FishSpecies, CastResult

class FishingGame:
    """Main game logic handler"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.fish_species_cache = None
        self.last_cache_update = 0
        self.cache_duration = 300  # Cache for 5 minutes
    
    def get_all_fish_species(self) -> List[Dict]:
        """Get all fish species from database with caching"""
        import time
        current_time = time.time()
        
        # Use cache if available and fresh
        if self.fish_species_cache and (current_time - self.last_cache_update) < self.cache_duration:
            return self.fish_species_cache
        
        # Fetch from database
        response = self.supabase.table('fish_species').select('*').execute()
        
        if response.data:
            self.fish_species_cache = response.data
            self.last_cache_update = current_time
            return response.data
        
        return []
    
    def generate_random_fish(self) -> Optional[Dict]:
        """
        Generate a random fish based on weighted probabilities
        This is the core anti-cheat mechanism - all randomness happens server-side
        """
        fish_list = self.get_all_fish_species()
        
        if not fish_list:
            return None
        
        # Create weighted list based on probabilities
        # Each fish appears in list proportional to its probability
        weighted_choices = []
        
        for fish in fish_list:
            probability = fish['base_probability']
            # Add fish multiple times based on probability (scaled by 1000 for precision)
            weight = int(probability * 1000)
            weighted_choices.extend([fish] * weight)
        
        # Select random fish from weighted list
        if not weighted_choices:
            return None
        
        selected_fish = random.choice(weighted_choices)
        return selected_fish
    
    def generate_weight(self, fish: Dict) -> float:
        """
        Generate random weight for caught fish within species range
        Uses normal distribution for realistic variation
        """
        min_weight = fish['min_weight']
        max_weight = fish['max_weight']
        
        # Calculate mean and standard deviation
        mean = (min_weight + max_weight) / 2
        # Standard deviation is 1/6 of range (95% within min-max)
        std_dev = (max_weight - min_weight) / 6
        
        # Generate weight using normal distribution
        weight = random.gauss(mean, std_dev)
        
        # Clamp to min/max range
        weight = max(min_weight, min(max_weight, weight))
        
        # Round to 2 decimal places
        return round(weight, 2)
    
    def check_personal_best(self, player_id: str, fish_species_id: str, weight: float) -> bool:
        """Check if this catch is a personal best for this player and species"""
        # Query existing catches for this player and species
        response = self.supabase.table('catches')\
            .select('weight')\
            .eq('player_id', player_id)\
            .eq('fish_species_id', fish_species_id)\
            .order('weight', desc=True)\
            .limit(1)\
            .execute()
        
        if not response.data:
            # No previous catches, this is first catch = personal best
            return True
        
        best_weight = response.data[0]['weight']
        return weight > best_weight
    
    def update_personal_best_flags(self, player_id: str, fish_species_id: str):
        """Update is_personal_best flags after new catch"""
        # Set all previous catches of this species to not personal best
        self.supabase.table('catches')\
            .update({'is_personal_best': False})\
            .eq('player_id', player_id)\
            .eq('fish_species_id', fish_species_id)\
            .execute()
        
        # Set the heaviest catch as personal best
        response = self.supabase.table('catches')\
            .select('id')\
            .eq('player_id', player_id)\
            .eq('fish_species_id', fish_species_id)\
            .order('weight', desc=True)\
            .limit(1)\
            .execute()
        
        if response.data:
            catch_id = response.data[0]['id']
            self.supabase.table('catches')\
                .update({'is_personal_best': True})\
                .eq('id', catch_id)\
                .execute()
    
    def save_catch(self, player_id: str, fish: Dict, weight: float, is_personal_best: bool) -> Optional[Dict]:
        """Save catch to database using secure RPC function"""
        try:
            # Use secure SECURITY DEFINER function to bypass RLS
            response = self.supabase.rpc('insert_catch', {
                'p_player_id': player_id,
                'p_fish_species_id': fish['id'],
                'p_weight': weight,
                'p_is_personal_best': is_personal_best,
                'p_points_earned': fish['points']
            }).execute()
            
            if response.data and len(response.data) > 0:
                # Update personal best flags if needed
                if is_personal_best:
                    self.update_personal_best_flags(player_id, fish['id'])
                
                return response.data[0]
            
            return None
        except Exception as e:
            print(f"Error saving catch: {e}")
            raise
    
    def cast_line(self, player_id: str) -> CastResult:
        """
        Main game action: Cast fishing line
        Returns a CastResult with fish, weight, and points
        """
        # Generate random fish
        fish = self.generate_random_fish()
        
        if not fish:
            return CastResult(
                success=False,
                fish=None,
                weight=None,
                points=None,
                is_personal_best=False,
                message="Failed to generate fish"
            )
        
        # Generate weight
        weight = self.generate_weight(fish)
        
        # Check if personal best
        is_personal_best = self.check_personal_best(player_id, fish['id'], weight)
        
        # Save catch to database
        catch = self.save_catch(player_id, fish, weight, is_personal_best)
        
        if not catch:
            return CastResult(
                success=False,
                fish=None,
                weight=None,
                points=None,
                is_personal_best=False,
                message="Failed to save catch"
            )
        
        # Return result
        return CastResult(
            success=True,
            fish=fish,
            weight=weight,
            points=fish['points'],
            is_personal_best=is_personal_best,
            message=f"Caught a {fish['name']}!"
        )
    
    def get_player_stats(self, player_id: str) -> Optional[Dict]:
        """Get player statistics"""
        response = self.supabase.table('players')\
            .select('*')\
            .eq('id', player_id)\
            .single()\
            .execute()
        
        return response.data if response.data else None
    
    def get_player_catches(self, player_id: str, limit: int = 50) -> List[Dict]:
        """Get player's recent catches with fish details"""
        response = self.supabase.table('catches')\
            .select('*, fish_species(*)')\
            .eq('player_id', player_id)\
            .order('caught_at', desc=True)\
            .limit(limit)\
            .execute()
        
        return response.data if response.data else []
    
    def get_leaderboard_heaviest(self, limit: int = 100) -> List[Dict]:
        """Get heaviest fish leaderboard"""
        response = self.supabase.from_('leaderboard_heaviest_fish')\
            .select('*')\
            .limit(limit)\
            .execute()
        
        return response.data if response.data else []
    
    def get_leaderboard_most_catches(self, limit: int = 100) -> List[Dict]:
        """Get most catches leaderboard"""
        response = self.supabase.from_('leaderboard_most_catches')\
            .select('*')\
            .limit(limit)\
            .execute()
        
        return response.data if response.data else []
    
    def get_leaderboard_rare_catches(self, limit: int = 100) -> List[Dict]:
        """Get rare catches leaderboard"""
        response = self.supabase.from_('leaderboard_rare_catches')\
            .select('*')\
            .limit(limit)\
            .execute()
        
        return response.data if response.data else []

