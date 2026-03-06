"""Profile Manager - Load and manage role profiles from data folders"""
import json
import os
from pathlib import Path
from typing import Optional, Dict, List
from model_structure.roles import RoleProfile, Role, RoleDelta
from model_structure.stories import SETimestamp, RoleID


class ProfileManager:
    """Manager for loading and creating role profile snapshots from data folders"""
    
    def __init__(self, data_root: str = "data"):
        """Initialize the profile manager with the data root directory"""
        self.data_root = Path(data_root)
    
    def get_episode_folder(self, season: int, episode: int) -> Path:
        """Get the path to an episode folder"""
        return self.data_root / f"Season_{season}" / f"S{season}E{episode:02d}_*"
    
    def find_episode_folder(self, season: int, episode: int) -> Optional[Path]:
        """Find the episode folder by season and episode number"""
        season_dir = self.data_root / f"Season_{season}"
        if not season_dir.exists():
            return None
        
        # Find folder matching pattern
        for folder in season_dir.iterdir():
            if folder.is_dir() and folder.name.startswith(f"S{season}E{episode:02d}_"):
                return folder
        
        return None
    
    def load_profile_from_file(self, file_path: Path) -> Optional[RoleProfile]:
        """Load a role profile from a JSON file with lenient validation"""
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Try strict validation first
            try:
                return RoleProfile(**data)
            except Exception:
                # If strict validation fails, try to build a minimal profile from available data
                # Extract the fields we need for a basic profile
                profile_data = {
                    'timestamp': data.get('timestamp'),
                    'role_id': data.get('role_id'),
                    'first_name': data.get('first_name', 'Unknown'),
                    'last_name': data.get('last_name'),
                    'aliases': data.get('aliases', []),
                    'description': data.get('description', ''),
                }
                
                # Try to build with minimal data
                return RoleProfile(**profile_data)
        except Exception:
            # If even minimal construction fails, skip this file
            return None
    
    def load_delta_from_file(self, file_path: Path) -> Optional[RoleDelta]:
        """Load a role delta from a JSON file"""
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return RoleDelta(**data)
        except Exception:
            # Silently skip deltas with validation errors
            return None
    
    def get_profile_at_episode(self, role_id: str, season: int, episode: int) -> Optional[RoleProfile]:
        """
        Get a role profile at a specific episode by building it from all deltas up to that episode.
        This uses the Role class to apply deltas and snapshot the profile.
        """
        role = self._build_role(role_id, season)
        if not role:
            return None
        
        # Create timestamp for the episode
        timestamp = SETimestamp(season=season, episode=episode)
        
        # Snapshot the role at this episode
        return role.snapshot(timestamp)
    
    def _build_role(self, role_id: str, season: int) -> Optional[Role]:
        """
        Build a Role object with all deltas accumulated from all episodes up to the given season.
        Mirrors the approach from role_profile_parser.py:
        - The chronologically first file is always a RoleProfile (initializer)
        - All subsequent files are RoleDelta objects
        - Creates a Role with the initial profile and collected deltas
        - Searches from Season 1 onwards to find the initial profile, then accumulates deltas through target season
        """
        initial_profile = None
        all_deltas = []
        
        # Track whether we've found the first appearance yet
        first_appearance_found = False
        
        # Search from season 1 up to the target season to find initial profile and accumulate deltas
        for search_season in range(1, season + 1):
            season_dir = self.data_root / f"Season_{search_season}"
            
            if not season_dir.exists():
                continue
            
            # Collect all episode folders with their episode numbers
            episode_folders = []
            for folder in season_dir.iterdir():
                if folder.is_dir() and folder.name.startswith("S"):
                    try:
                        parts = folder.name.split('_')[0]  # e.g., "S1E01"
                        episode_num = int(parts[3:])  # Extract episode number
                        episode_folders.append((episode_num, folder))
                    except (ValueError, IndexError):
                        continue
            
            # Sort by episode number to process chronologically
            episode_folders.sort(key=lambda x: x[0])
            
            # Load initial profile and deltas from all episodes in chronological order
            for episode_num, folder in episode_folders:
                roles_dir = folder / "roles"
                role_file = roles_dir / f"{role_id}.json"
                
                if not role_file.exists():
                    continue
                
                # The first file we encounter is always a RoleProfile (initial state)
                if not first_appearance_found:
                    profile = self.load_profile_from_file(role_file)
                    if profile:
                        initial_profile = profile
                        first_appearance_found = True
                    continue
                
                # All subsequent files are RoleDelta objects
                delta = self.load_delta_from_file(role_file)
                if delta:
                    all_deltas.append(delta)
        
        # If we have neither profile nor deltas, the role doesn't exist up to this season
        if not initial_profile and not all_deltas:
            return None
        
        # Create and return a Role object with the initial profile and collected deltas
        role = Role(role_id=role_id, role_init_profile=initial_profile, role_deltas=all_deltas)
        return role
    
    def get_profile_history(self, role_id: str, season: int) -> List[tuple[int, RoleProfile]]:
        """
        Get all profiles for a role in a given season.
        Returns a list of (episode_number, profile) tuples.
        Only includes episodes where the role file actually exists.
        """
        profiles = []
        season_dir = self.data_root / f"Season_{season}"
        
        if not season_dir.exists():
            return profiles
        
        # Collect all episode folders with role files for this role
        episode_folders_with_data = []
        for folder in season_dir.iterdir():
            if folder.is_dir() and folder.name.startswith("S"):
                try:
                    parts = folder.name.split('_')[0]  # e.g., "S1E01"
                    episode_num = int(parts[3:])  # Extract episode number
                    
                    # Check if this episode has a role file for the requested role
                    role_file = folder / "roles" / f"{role_id}.json"
                    if role_file.exists():
                        episode_folders_with_data.append((episode_num, folder))
                except (ValueError, IndexError):
                    continue
        
        # Sort by episode number
        episode_folders_with_data.sort(key=lambda x: x[0])
        
        # Build the role once with all deltas for this season
        role = self._build_role(role_id, season)
        if not role:
            return profiles
        
        # Generate snapshots only for episodes where this role's file exists
        for episode_num, folder in episode_folders_with_data:
            timestamp = SETimestamp(season=season, episode=episode_num)
            profile = role.snapshot(timestamp)
            if profile:
                profiles.append((episode_num, profile))
        
        return profiles
    
    def get_all_roles_in_episode(self, season: int, episode: int) -> List[str]:
        """Get all role IDs available in a specific episode"""
        episode_folder = self.find_episode_folder(season, episode)
        if not episode_folder:
            return []
        
        roles_dir = episode_folder / "roles"
        if not roles_dir.exists():
            return []
        
        roles = []
        for file in roles_dir.iterdir():
            if file.suffix == ".json":
                roles.append(file.stem)
        
        return sorted(roles)
    
    def get_all_roles_in_season(self, season: int) -> List[str]:
        """Get all unique role IDs in a season"""
        all_roles = set()
        season_dir = self.data_root / f"Season_{season}"
        
        if not season_dir.exists():
            return []
        
        for folder in season_dir.iterdir():
            if folder.is_dir() and folder.name.startswith("S"):
                roles_dir = folder / "roles"
                if roles_dir.exists():
                    for file in roles_dir.iterdir():
                        if file.suffix == ".json":
                            all_roles.add(file.stem)
        
        return sorted(list(all_roles))


# Utility function for the profile page
def get_profile_snapshot(role_id: str, season: int, episode: int, data_root: str = "data") -> Optional[RoleProfile]:
    """
    Get a profile snapshot for a role at a specific episode.
    This is the main entry point for the profile page.
    """
    manager = ProfileManager(data_root)
    return manager.get_profile_at_episode(role_id, season, episode)
