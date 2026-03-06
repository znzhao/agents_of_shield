import re
import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Annotated, Literal
from pydantic import BaseModel, model_validator, Field, BeforeValidator
from model_structure.embedding import EmbeddingModel

RoleID = Annotated[
    str,
    Field(description="Unique role identifier, e.g. 'skye', or 'grant_ward'. Should be lowercase with underscores, no spaces or special characters."),
    BeforeValidator(lambda v: re.sub(r'\s+', '_', v.strip().lower()))
]

SCENE_VIBES = [
    'tense', 'emotional', 'action-packed', 'comedic', 'mysterious', 
    'romantic', 'tragic', 'hopeful', 'suspenseful', 'dramatic', 
    'dark', 'lighthearted', 'intense', 'melancholic', 'thrilling'
]



class SETimestamp(BaseModel):
    season: int
    episode: int

    def timestamp(self) -> str:
        return f"S{self.season}E{self.episode:02d}"
    
    def __str__(self) -> str:
        return self.timestamp()
    
    def __lt__(self, other):
        if not isinstance(other, SETimestamp):
            return NotImplemented
        if self.season != other.season:
            return self.season < other.season
        return self.episode < other.episode
    
    def __le__(self, other):
        if not isinstance(other, SETimestamp):
            return NotImplemented
        return self < other or self == other
    
    def __gt__(self, other):
        if not isinstance(other, SETimestamp):
            return NotImplemented
        if self.season != other.season:
            return self.season > other.season
        return self.episode > other.episode
    
    def __ge__(self, other):
        if not isinstance(other, SETimestamp):
            return NotImplemented
        return self > other or self == other
    
    def __eq__(self, other):
        if not isinstance(other, SETimestamp):
            return NotImplemented
        return self.season == other.season and self.episode == other.episode
    
    def __ne__(self, other):
        if not isinstance(other, SETimestamp):
            return NotImplemented
        return not self == other
    
    def __eq__(self, other):
        if not isinstance(other, SETimestamp):
            return NotImplemented
        return (self.season == other.season and 
                self.episode == other.episode)
    
    def __ne__(self, other):
        eq_result = self.__eq__(other)
        if eq_result is NotImplemented:
            return NotImplemented
        return not eq_result
    
    def __gt__(self, other):
        if not isinstance(other, SETimestamp):
            return NotImplemented
        if self.season != other.season:
            return self.season > other.season
        return self.episode > other.episode
    
    def __le__(self, other):
        lt_result = self.__lt__(other)
        eq_result = self.__eq__(other)
        if lt_result is NotImplemented or eq_result is NotImplemented:
            return NotImplemented
        return lt_result or eq_result
    
    def __ge__(self, other):
        gt_result = self.__gt__(other)
        eq_result = self.__eq__(other)
        if gt_result is NotImplemented or eq_result is NotImplemented:
            return NotImplemented
        return gt_result or eq_result

class Scene(SETimestamp):
    num: int = Field(default_factory=int, description="Unique scene identifier within the episode, e.g. 1 for the first scene, 2 for the second scene, etc.")
    scene_name: str = Field(description="Scene name, should only be words in CamelCase without spaces, e.g. 'TheBusConflict' or 'CoulsonVsWard'")
    description: str = Field(description="Detailed description of the scene, including key events, character actions, and summary of any important dialogue")
    roles: List[RoleID] = Field(default_factory=list, description="List of character identifiers present in the scene, e.g. ['phil_coulson', 'grant_ward']. Note that these should be character identifiers (PersonIDs) rather than role identifiers, since a character may have multiple roles across the story.")
    vibe: Literal[
        'tense', 'emotional', 'action-packed', 'comedic', 'mysterious', 
        'romantic', 'tragic', 'hopeful', 'suspenseful', 'dramatic', 
        'dark', 'lighthearted', 'intense', 'melancholic', 'thrilling'
    ] = Field(description="Vibe of the scene, e.g. 'tense', 'emotional', 'action-packed', etc.")
    location: Optional[str] = Field(default='unknown', description="In-universe location of the scene, if known, e.g. 'New York City', 'S.H.I.E.L.D. Helicarrier', or 'Unknown'")
    significance: Literal['minor', 'major', 'climactic'] = Field(description="Significance of the scene, e.g. 'minor', 'major', 'climactic'")
    transcript: Optional[List[Dict[str, str]]] = None
    
    @property
    def id(self) -> str:
        return f"{self.timestamp()}-{self.num}-{self.scene_name}"

    def __str__(self) -> str:
        return f"S{self.season}E{self.episode:02d}-{self.scene_name}: {self.description}"

    def __lt__(self, other):
        if not isinstance(other, Scene):
            return NotImplemented
        if self.timestamp() != other.timestamp():
            return SETimestamp(season=self.season, episode=self.episode) < SETimestamp(season=other.season, episode=other.episode)
        return self.num < other.num

    def __eq__(self, other):
        if not isinstance(other, Scene):
            return NotImplemented
        return (self.season == other.season and 
                self.episode == other.episode and 
                self.num == other.num)

    def __ne__(self, other):
        eq_result = self.__eq__(other)
        if eq_result is NotImplemented:
            return NotImplemented
        return not eq_result

    def __gt__(self, other):
        if not isinstance(other, Scene):
            return NotImplemented
        if self.timestamp() != other.timestamp():
            return SETimestamp(season=self.season, episode=self.episode) > SETimestamp(season=other.season, episode=other.episode)
        return self.num > other.num

    def __le__(self, other):
        lt_result = self.__lt__(other)
        eq_result = self.__eq__(other)
        if lt_result is NotImplemented or eq_result is NotImplemented:
            return NotImplemented
        return lt_result or eq_result

    def __ge__(self, other):
        gt_result = self.__gt__(other)
        eq_result = self.__eq__(other)
        if gt_result is NotImplemented or eq_result is NotImplemented:
            return NotImplemented
        return gt_result or eq_result

    def save_to_json(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=4)

    @classmethod
    def load_from_json(cls, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return cls(**data)

class Episode(SETimestamp):
    name: str = Field(description="Episode name for better readability")
    synopsis: Optional[str] = None
    summary: Optional[str] = None
    transcript: Optional[List[Dict[str, str]]] = None

    scenes: List[Scene] = Field(default_factory=list)
    scene_embeddings: Optional[List[List[float]]] = Field(default_factory=list)
    roles: List[RoleID] = Field(default_factory=list, description="List of role identifiers present in the episode, e.g. ['skye', 'phil_coulson', 'grant_ward']")
    role_aliases: Optional[List[str]] = Field(default_factory=list, description="Alternative names or titles for the roles in the episode, e.g. 'Phil Coulson' or 'Agent Coulson'")
    affiliations: Optional[List[str]] = Field(default_factory=list, description="List of character affiliations or groups present in the episode, e.g. 'S.H.I.E.L.D.', 'Hydra', 'Inhumans', 'Avengers', etc.")
    locations: Optional[List[str]] = Field(default_factory=list, description="List of in-universe locations featured in the episode, e.g. 'New York City', 'S.H.I.E.L.D. Helicarrier', 'Coulson's Apartment', etc.")

    @model_validator(mode='after')
    def validate_scenes(self):
        scene_ids = set()
        for scene in self.scenes:
            if scene.season != self.season or scene.episode != self.episode:
                raise ValueError(
                    f"Scene {scene.id} has season {scene.season} and episode {scene.episode} "
                    f"but should be season {self.season} and episode {self.episode}"
                )
            if scene.id in scene_ids:
                raise ValueError(
                    f"Duplicate scene ID {scene.id} in episode {self.timestamp()}"
                )
            scene_ids.add(scene.id)
        return self

    def script(self) -> str:
        summary = '=' * 40 + '\n'
        summary = f"Episode S{self.season}E{self.episode:02d} - {self.name}"
        summary += '\n' + '=' * 40
        if self.synopsis:
            summary += f"\nSynopsis: \n{self.synopsis}"
        if self.transcript:
            summary += "\n" + "-" * 40
            summary += "\nTranscript:"
            for line in self.transcript:
                character = line['character']
                dialogue = line['line']
                summary += f"\n{character}: {dialogue}"
        summary += '\n' + '=' * 40
        return summary

    def __str__(self) -> str:
        return f"S{self.season}E{self.episode:02d} - {self.name}"
    
    def embedding_scenes(self) -> List[List[float]]:
        if self.scene_embeddings is not None:
            return self.scene_embeddings
        if not self.scenes:
            return []
        embedding_model = EmbeddingModel()
        items = []
        for scene in self.scenes:
            metadata = scene.model_dump()
            items.append({"text": json.dumps(metadata, ensure_ascii=False), "metadata": metadata})
        # add items (text + metadata) so the embedding model stores metadata alongside embeddings
        embedding_model.add(items)
        # build combined structure for persistence: [{'embedding': [...], 'metadata': {...}}, ...]
        combined = []
        for emb, item in zip(embedding_model.embeddings, embedding_model.data):
            emb_list = emb.tolist() if hasattr(emb, "tolist") else list(emb)
            combined.append({"embedding": emb_list, "metadata": item.get("metadata", {})})
        # keep scene_embeddings as list of embedding vectors for Episode model
        self.scene_embeddings = [c["embedding"] for c in combined]
        return self.scene_embeddings

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        for scene in self.scenes:
            if scene.id == scene_id:
                return scene
        return None
    
    def __getitem__(self, key):
        if isinstance(key, int):
            if 0 <= key < len(self.scenes):
                return self.scenes[key]
            else:
                raise IndexError("Scene index out of range")
        if isinstance(key, str):
            return self.get_scene(key)
        if isinstance(key, slice):
            return self.scenes[key]
        else:
            raise TypeError("Key must be int (scene index) or str (scene_id) to retrieve a scene")

    def __next__(self):
        for scene in self.scenes:
            yield scene

    def __iter__(self):
        return self.__next__()
    
    def __len__(self):
        return len(self.scenes)
    
    def count_scenes_by(self, 
                     role_id: Optional[RoleID] = None,
                     vibe: Optional[str] = None,
                     location: Optional[str] = None,
                     significance: Optional[str] = None,
                     ) -> int:
        count = 0
        for scene in self.scenes:
            if role_id and role_id not in scene.roles:
                continue
            if location and (not scene.location or location.lower() not in scene.location.lower()):
                continue
            if vibe and scene.vibe != vibe:
                continue
            if significance and scene.significance != significance:
                continue
            count += 1
        return count

    def save_to_json(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=4)

    @classmethod
    def load_from_json(cls, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return cls(**data)

class Season(BaseModel):
    season: int
    episodes: Optional[List[Episode]] = Field(default_factory=list)

    def __len__(self):
        return len(self.episodes)

    @model_validator(mode='after')
    def validate_episodes(self):
        episode_numbers = set()
        for episode in self.episodes:
            if episode.season != self.season:
                raise ValueError(f"Episode {episode} has season {episode.season} but should be {self.season}")
            if episode.episode in episode_numbers:
                raise ValueError(f"Duplicate episode number {episode.episode} in season {self.season}")
            episode_numbers.add(episode.episode)
        return self

    def __next__(self):
        for episode in self.episodes:
            yield episode

    def __iter__(self):
        return self.__next__()

    def __str__(self) -> str:
        return f"Season {self.season} with {len(self.episodes)} episodes"

    def get_episode(self, name: str) -> Optional[Episode]:
        for episode in self.episodes:
            if episode.name.lower() == name.lower():
                return episode
        return None

    def __getitem__(self, key):
        if isinstance(key, int):
            if 0 <= key < len(self.episodes):
                return self.episodes[key]
            else:
                raise IndexError("Episode index out of range")
        elif isinstance(key, str):
            return self.get_episode(key)
        elif isinstance(key, slice):
            # Return a slice of episodes
            return self.episodes[key]
        else:
            raise TypeError("Key must be int (index or episode number), str (episode name), or slice")

    def sort(self):
        self.episodes.sort(key=lambda ep: (ep.season, ep.episode))

    def append(self, episode: Episode):
        if episode.season != self.season:
            raise ValueError(f"Episode {episode.name} has season {episode.season} but should be {self.season}")
        if any(ep.episode == episode.episode for ep in self.episodes):
            raise ValueError(f"Episode number {episode.episode} already exists in season {self.season}")
        self.episodes.append(episode)
        self.sort()
    
    def search_scenes(self, 
                      query: Optional[str] = None, 
                      role: Optional[RoleID] = None,
                      vibe: Optional[str] = None,
                      location: Optional[str] = None,
                      min_timestamp: Optional[SETimestamp] = None,
                      max_timestamp: Optional[SETimestamp] = None,
                      top_n: int = None,
                      vec_search: bool = False,
                      ) -> List[Scene]:
        '''
        Search for scenes based on keyword in description, character involvement, location, and/or timestamp.
        If vec_search is True and query is provided, performs vector search on scene descriptions for semantic similarity, 
        with optional metadata filtering by role, vibe, and location. Returns results sorted by relevance.
        Otherwise, performs keyword search on scene descriptions with the same metadata and timestamp filters, 
        but without semantic understanding. Results are returned in the order they appear in the season.
        '''
        if vec_search and query:
            return self.vec_search_scenes(
                query=query, 
                role=role,
                vibe=vibe,
                location=location,
                min_timestamp=min_timestamp,
                max_timestamp=max_timestamp,
                top_n=top_n
                )
        results = []

        for episode in self.episodes:
            ep_timestamp = SETimestamp(season=episode.season, episode=episode.episode)
            if max_timestamp and ep_timestamp > max_timestamp:
                continue
            if min_timestamp and ep_timestamp < min_timestamp:
                continue
            for scene in episode.scenes:
                if query and not any(word in scene.description.lower() for word in query.lower().split()):
                    continue
                if role and role not in scene.roles:
                    continue
                if location and (not scene.location or location.lower() not in scene.location.lower()):
                    continue
                if vibe and (not scene.vibe or vibe.lower() not in scene.vibe.lower()):
                    continue
                results.append(scene)
                if top_n and len(results) >= top_n:
                    return results
        return results
    
    def vec_search_scenes(
            self, 
            query: str, 
            role: Optional[RoleID] = None,
            vibe: Optional[str] = None,
            location: Optional[str] = None,
            min_timestamp: Optional[SETimestamp] = None, 
            max_timestamp: Optional[SETimestamp] = None,
            top_n: int = None, 
            ) -> List[Scene]:
        """
        Vector search scenes in this season by semantic similarity of scene descriptions.
        Supports optional metadata_filter (dict) to restrict search results by metadata keys/values.
        Supports min_timestamp and max_timestamp to filter episodes.
        Returns results sorted from most related to less.
        """
        all_items: List[dict] = []
        all_embeddings: List[List[float]] = []
        scene_map: Dict[str, Scene] = {}

        for episode in self.episodes:
            ep_timestamp = SETimestamp(season=episode.season, episode=episode.episode)
            if min_timestamp and ep_timestamp < min_timestamp:
                continue
            if max_timestamp and ep_timestamp > max_timestamp:
                continue

            emb = episode.scene_embeddings
            texts = [json.dumps(scene.model_dump(), ensure_ascii=False) for scene in episode.scenes]

            # Only encode if embeddings are missing or length mismatch
            if not emb or len(emb) != len(texts):
                emb = episode.embedding_scenes()
            # If still missing, skip
            if not emb or len(emb) != len(texts):
                continue

            for i, scene in enumerate(episode.scenes):
                metadata = scene.model_dump()
                metadata["scene_id"] = scene.id
                all_items.append({"text": texts[i], "metadata": metadata})
                all_embeddings.append(emb[i])
                scene_map[scene.id] = scene

        if not all_embeddings:
            return []

        # Cache the embedding model for this Season instance
        embedding_model = EmbeddingModel()
        # Replace cache contents with current season data (fresh index)
        embedding_model.embeddings = []
        embedding_model.data = []
        embedding_model.add_existing(all_items, all_embeddings)

        # apply metadata filters if provided
        metadata_filter = {}
        if role:
            metadata_filter["roles"] = [role]
        if vibe:
            metadata_filter["vibe"] = vibe
        if location:
            metadata_filter["location"] = location
        results = embedding_model.search(query, top_n=top_n, metadata_filter=metadata_filter)

        results_scenes: List[Scene] = []
        for item in results:
            sid = item.get("metadata", {}).get("scene_id")
            if sid and sid in scene_map:
                results_scenes.append(scene_map[sid])
        return results_scenes

    def get_roles(self, min_timestamp: Optional[SETimestamp] = None, max_timestamp: Optional[SETimestamp] = None) -> List[str]:
        roles = set()
        for episode in self.episodes:
            if max_timestamp and episode.timestamp() > max_timestamp:
                continue
            if min_timestamp and episode.timestamp() < min_timestamp:
                continue
            for scene in episode.scenes:
                roles.update(scene.roles)
        return list(roles)
    
    def get_role_aliases(self, min_timestamp: Optional[SETimestamp] = None, max_timestamp: Optional[SETimestamp] = None) -> List[str]:
        aliases = set()
        for episode in self.episodes:
            if max_timestamp and episode.timestamp() > max_timestamp:
                continue
            if min_timestamp and episode.timestamp() < min_timestamp:
                continue
            aliases.update(episode.role_aliases)
        return list(aliases)
    
    def get_affiliations(self, min_timestamp: Optional[SETimestamp] = None, max_timestamp: Optional[SETimestamp] = None) -> List[str]:
        affiliations = set()
        for episode in self.episodes:
            if max_timestamp and episode.timestamp() > max_timestamp:
                continue
            if min_timestamp and episode.timestamp() < min_timestamp:
                continue
            affiliations.update(episode.affiliations)
        return list(affiliations)

    def get_locations(self, min_timestamp: Optional[SETimestamp] = None, max_timestamp: Optional[SETimestamp] = None) -> List[str]:
        locations = set()
        for episode in self.episodes:
            if max_timestamp and episode.timestamp() > max_timestamp:
                continue
            if min_timestamp and episode.timestamp() < min_timestamp:
                continue
            locations.update(episode.locations)
        return list(locations)

    def count_episodes_by(self, 
                          role_id: Optional[RoleID] = None, 
                          affiliation: Optional[str] = None,
                          location: Optional[str] = None
                          ) -> int:
        count = 0
        for episode in self.episodes:
            if role_id and role_id not in episode.roles:
                continue
            if affiliation and affiliation not in episode.affiliations:
                continue
            if location and location not in episode.locations:
                continue
            count += 1
        return count

    def count_scenes_by(self, 
                      role_id: Optional[RoleID] = None,
                      location: Optional[str] = None,
                      vibe: Optional[str] = None,
                      significance: Optional[str] = None,
                      ) -> int:
        count = 0
        for episode in self.episodes:
            count += episode.count_scenes_by(
                role_id=role_id,
                location=location,
                vibe=vibe,
                significance=significance,
            )
        return count

    def save_to_json(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=4)

    @classmethod
    def load_from_json(cls, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return cls(**data)

class Story(BaseModel):
    title: str
    seasons: Optional[List[Season]] = Field(default_factory=list)

    def __next__(self):
        for season in self.seasons:
            for episode in season.episodes:
                yield episode

    def __iter__(self):
        return self.__next__()

    def __str__(self) -> str:
        return f"{self.title} with {len(self.seasons)} seasons, {len(self.all_episodes())} episodes"
    
    def __len__(self):
        return len(self.seasons)

    def get_season(self, season_number: int) -> Optional[Season]:
        for season in self.seasons:
            if season.season == season_number:
                return season
        return None
    
    def get_episode(self, name: str) -> Optional[Episode]:
        for season in self.seasons:
            episode = season.get_episode(name)
            if episode:
                return episode
        raise ValueError(f"Episode with name '{name}' not found in story '{self.title}'")
    
    def all_episodes(self) -> List[Episode]:
        episodes = []
        for season in self.seasons:
            episodes.extend(season.episodes)
        return episodes
    
    def __getitem__(self, key):
        if isinstance(key, int):
            if 0 <= key < len(self.seasons):
                return self.seasons[key]
            else:
                raise IndexError("Season index out of range")
        elif isinstance(key, str):
            return self.get_episode(key)
        elif isinstance(key, tuple) and len(key) == 2:
            season_idx, episode_idx = key
            if isinstance(season_idx, int) and isinstance(episode_idx, int):
                # Treat as array indices (0-based)
                if 0 <= season_idx < len(self.seasons):
                    if 0 <= episode_idx < len(self.seasons[season_idx].episodes):
                        return self.seasons[season_idx].episodes[episode_idx]
                    else:
                        raise IndexError("Episode index out of range")
                else:
                    raise IndexError("Season index out of range")
            else:
                raise TypeError("For tuple keys, both season and episode indices must be integers")
        elif isinstance(key, SETimestamp):
            # Access by season number (1-based) and episode number (1-based)
            season = self.get_season(key.season)
            if season is None:
                raise ValueError(f"Season {key.season} not found")
            for ep in season.episodes:
                if ep.episode == key.episode:
                    return ep
            raise ValueError(f"Episode {key.episode} not found in Season {key.season}")
        elif isinstance(key, slice):
            # Return a slice of seasons
            return self.seasons[key]
        else:
            raise TypeError("Key must be int (season index), str (episode name), tuple (season_idx, episode_idx), SETimestamp, or slice")

    def __next__(self):
        for season in self.seasons:
            for episode in season.episodes:
                yield episode

    def __iter__(self):
        return self.__next__()
    
    def __str__(self):
        return f"{self.title} with {len(self.seasons)} seasons and {len(self.all_episodes())} episodes"

    def sort(self):
        for season in self.seasons:
            season.sort()
        self.seasons.sort(key=lambda s: s.season)

    def append(self, season: Season):
        if any(s.season == season.season for s in self.seasons):
            raise ValueError(f"Season number {season.season} already exists in story {self.title}")
        self.seasons.append(season)
        self.sort()

    def search_scenes(
            self,
            query: Optional[str] = None,
            role: Optional[RoleID] = None,
            vibe: Optional[str] = None,
            location: Optional[str] = None,
            min_timestamp: Optional[SETimestamp] = None,
            max_timestamp: Optional[SETimestamp] = None,
            top_k: Optional[int] = None,
            vec_search: bool = False
            ) -> List[Scene]:
        """
        Search for scenes across all seasons and episodes.
        If vec_search is True and query is provided, performs semantic vector search.
        Otherwise, performs keyword search on scene descriptions.
        Supports filtering by role, vibe, location, and timestamp.
        """
        results = []
        if vec_search and query:
            return self.vec_search_scenes(
                query=query,
                role=role,
                vibe=vibe,
                location=location,
                min_timestamp=min_timestamp,
                max_timestamp=max_timestamp,
                top_n=top_k
            )
        for season in self.seasons:
            for episode in season.episodes:
                ep_timestamp = SETimestamp(season=episode.season, episode=episode.episode)
                if max_timestamp and ep_timestamp > max_timestamp:
                    continue
                if min_timestamp and ep_timestamp < min_timestamp:
                    continue
                for scene in episode.scenes:
                    if query and not any(word in scene.description.lower() for word in query.lower().split()):
                        continue
                    if role and role not in scene.roles:
                        continue
                    if location and (not scene.location or location.lower() not in scene.location.lower()):
                        continue
                    if vibe and scene.vibe != vibe:
                        continue
                    results.append(scene)
                    if top_k and len(results) >= top_k:
                        return results
        return results

    def vec_search_scenes(
            self, 
            query: str, 
            role: Optional[RoleID] = None,
            vibe: Optional[str] = None,
            location: Optional[str] = None,
            top_n: int = None, 
            min_timestamp: Optional[SETimestamp] = None, 
            max_timestamp: Optional[SETimestamp] = None
            ) -> List[Scene]:
        """
        Vector search scenes in this season by semantic similarity of scene descriptions.
        Supports optional metadata_filter (dict) to restrict search results by metadata keys/values.
        Supports min_timestamp and max_timestamp to filter episodes.
        Returns results sorted from most related to less.
        """
        all_items: List[dict] = []
        all_embeddings: List[List[float]] = []
        scene_map: Dict[str, Scene] = {}
        for season in self.seasons:
            for episode in season.episodes:
                ep_timestamp = SETimestamp(season=episode.season, episode=episode.episode)
                if min_timestamp and ep_timestamp < min_timestamp:
                    continue
                if max_timestamp and ep_timestamp > max_timestamp:
                    continue

                emb = episode.scene_embeddings
                texts = [json.dumps(scene.model_dump(), ensure_ascii=False) for scene in episode.scenes]

                # Only encode if embeddings are missing or length mismatch
                if not emb or len(emb) != len(texts):
                    emb = episode.embedding_scenes()
                # If still missing, skip
                if not emb or len(emb) != len(texts):
                    continue

                for i, scene in enumerate(episode.scenes):
                    metadata = scene.model_dump()
                    metadata["scene_id"] = scene.id
                    all_items.append({"text": texts[i], "metadata": metadata})
                    all_embeddings.append(emb[i])
                    scene_map[scene.id] = scene

        if not all_embeddings:
            return []

        embedding_model = EmbeddingModel()
        # Replace cache contents with current season data (fresh index)
        embedding_model.embeddings = []
        embedding_model.data = []
        embedding_model.add_existing(all_items, all_embeddings)

        # apply metadata filters if provided
        metadata_filter = {}
        if role:
            metadata_filter["roles"] = [role]
        if vibe:
            metadata_filter["vibe"] = vibe
        if location:
            metadata_filter["location"] = location
        results = embedding_model.search(query, top_n=top_n, metadata_filter=metadata_filter)

        results_scenes: List[Scene] = []
        for item in results:
            sid = item.get("metadata", {}).get("scene_id")
            if sid and sid in scene_map:
                results_scenes.append(scene_map[sid])
        return results_scenes

    def get_roles(self, min_timestamp: Optional[SETimestamp] = None, max_timestamp: Optional[SETimestamp] = None) -> List[str]:
        roles = set()
        for season in self.seasons:
            for episode in season.episodes:
                if max_timestamp and episode.timestamp() > max_timestamp:
                    continue
                if min_timestamp and episode.timestamp() < min_timestamp:
                    continue
                for scene in episode.scenes:
                    roles.update(scene.roles)
        return list(roles)
    
    def get_role_aliases(self, min_timestamp: Optional[SETimestamp] = None, max_timestamp: Optional[SETimestamp] = None) -> List[str]:
        aliases = set()
        for season in self.seasons:
            for episode in season.episodes:
                if max_timestamp and episode.timestamp() > max_timestamp:
                    continue
                if min_timestamp and episode.timestamp() < min_timestamp:
                    continue
                aliases.update(episode.role_aliases)
        return list(aliases)
    
    def get_affiliations(self, min_timestamp: Optional[SETimestamp] = None, max_timestamp: Optional[SETimestamp] = None) -> List[str]:
        affiliations = set()
        for season in self.seasons:
            for episode in season.episodes:
                if max_timestamp and episode.timestamp() > max_timestamp:
                    continue
                if min_timestamp and episode.timestamp() < min_timestamp:
                    continue
                affiliations.update(episode.affiliations)
        return list(affiliations)
    
    def get_locations(self, min_timestamp: Optional[SETimestamp] = None, max_timestamp: Optional[SETimestamp] = None) -> List[str]:
        locations = set()
        for season in self.seasons:
            for episode in season.episodes:
                if max_timestamp and episode.timestamp() > max_timestamp:
                    continue
                if min_timestamp and episode.timestamp() < min_timestamp:
                    continue
                locations.update(episode.locations)
        return list(locations)

    def count_episodes_by(self, 
                          role_id: Optional[RoleID] = None,
                          affiliation: Optional[str] = None,
                          location: Optional[str] = None) -> int:
        count = 0
        for season in self.seasons:
            for episode in season.episodes:
                if role_id and role_id not in episode.roles:
                    continue
                if affiliation and affiliation not in episode.affiliations:
                    continue
                if location and location not in episode.locations:
                    continue
                count += 1
        return count

    def count_scenes_by(self, 
                            role_id: Optional[RoleID] = None,
                            location: Optional[str] = None,
                            vibe: Optional[str] = None,
                            significance: Optional[str] = None,
                            ) -> int:
            count = 0
            for season in self.seasons:
                for episode in season.episodes:
                    count += episode.count_scenes_by(
                        role_id=role_id,
                        location=location,
                        vibe=vibe,
                        significance=significance,
                    )
            return count

    def save_to_json(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=4)
    
    @classmethod
    def load_from_json(cls, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return cls(**data)
        
class StoryManager():
    def __init__(self, title: str):
        self.story = Story(title=title)

    def _find_episode_dir(self, season: int, episode: int, data_dir: str = "data") -> Optional[Path]:
        '''
        Locate the episode directory under data/Season_{season}/S{season}E{episode:02d}_*.
        Returns the Path if found, else None.
        '''
        season_dir = Path(data_dir) / f"Season_{season}"
        if not season_dir.exists():
            return None
        prefix = f"S{season}E{episode:02d}_"
        for entry in season_dir.iterdir():
            if entry.is_dir() and entry.name.startswith(prefix):
                return entry
        return None

    def add_episode(self, season: int, episode: int, name: str,
                     synopsis: Optional[str] = None,
                     summary: Optional[str] = None,
                     transcript: Optional[List[Dict[str, str]]] = None,
                     scenes: Optional[List[Scene]] = None,
                     scenes_embedding: Optional[List[List[float]]] = None,
                     roles: Optional[List[str]] = None,
                     role_aliases: Optional[List[str]] = None,
                     affiliations: Optional[List[str]] = None,
                     locations: Optional[List[str]] = None):

        ep = Episode(
            season=season, episode=episode, name=name,
            synopsis=synopsis, summary=summary, transcript=transcript,
            scenes=scenes or [],
            scene_embeddings=scenes_embedding or [],
            roles=roles or [],
            role_aliases=role_aliases or [],
            affiliations=affiliations or [],
            locations=locations or []
        )
        season_obj = self.story.get_season(season)
        if not season_obj:
            season_obj = Season(season=season)
            self.story.append(season_obj)
        season_obj.append(ep)
    
    def read_synopsis(self, season: int, episode: int, data_dir: str = "data") -> Optional[str]:
        '''
        Read synopsis from data/Season_{season}/S{season}E{episode:02d}_{name}/synopsis.txt for a specific episode.
        '''
        ep_dir = self._find_episode_dir(season, episode, data_dir)
        if not ep_dir:
            print(f"Episode directory not found for S{season}E{episode:02d}")
            return None
        filepath = ep_dir / "synopsis.txt"
        if not filepath.exists():
            print(f"Synopsis file not found for S{season}E{episode:02d} at {filepath}")
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    def read_transcript(self, season: int, episode: int, data_dir: str = "data") -> Optional[List[Dict[str, str]]]:
        '''
        Read transcript from data/Season_{season}/S{season}E{episode:02d}_{name}/transcript.csv for a specific episode.
        '''
        ep_dir = self._find_episode_dir(season, episode, data_dir)
        if not ep_dir:
            print(f"Episode directory not found for S{season}E{episode:02d}")
            return None
        filepath = ep_dir / "transcript.csv"
        if not filepath.exists():
            print(f"Transcript file not found for S{season}E{episode:02d} at {filepath}")
            return None

        lines = []
        with open(filepath, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                character = row['character']
                dialogue = row['line']
                character = character.replace('\u2019', "'")
                dialogue = dialogue.replace('\u2019', "'")
                lines.append({'character': character, 'line': dialogue})
        return lines

    def read_identifiers(self, season: int, episode: int, data_dir: str = "data") -> Optional[Dict]:
        '''
        Read identifiers from data/Season_{season}/S{season}E{episode:02d}_{name}/identifiers.json for a specific episode.
        Returns a dict with keys: role_ids, person_ids, aliases, affiliations, locations, role_person_mapping.
        '''
        ep_dir = self._find_episode_dir(season, episode, data_dir)
        if not ep_dir:
            logging.info(f"Episode directory not found for S{season}E{episode:02d}")
            return None
        filepath = ep_dir / "identifiers.json"
        if not filepath.exists():
            logging.info(f"Identifiers file not found for S{season}E{episode:02d} at {filepath}")
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def read_scenes(self, season: int, episode: int, data_dir: str = "data") -> List[Scene]:
        '''
        Read all scene JSON files from data/Season_{season}/S{season}E{episode:02d}_{name}/scenes/ for a specific episode.
        '''
        ep_dir = self._find_episode_dir(season, episode, data_dir)
        if not ep_dir:
            logging.info(f"Episode directory not found for S{season}E{episode:02d}")
            return []
        scenes_dir = ep_dir / "scenes"
        if not scenes_dir.exists() or not scenes_dir.is_dir():
            logging.info(f"Scenes directory not found for S{season}E{episode:02d} at {scenes_dir}")
            return []
        scenes = []
        for scene_file in sorted(scenes_dir.iterdir()):
            if scene_file.suffix == '.json':
                scene = Scene.load_from_json(str(scene_file))
                scenes.append(scene)
        return scenes

    def read_embeddings(self, season: int, episode: int, data_dir: str = "data") -> Optional[List[List[float]]]:
        '''
        Read scene embeddings from data/Season_{season}/S{season}E{episode:02d}_{name}/scenes_embedding.json for a specific episode.
        Supports legacy format (list of lists) and new format (list of {"embedding": [...], "metadata": {...}}).
        '''
        ep_dir = self._find_episode_dir(season, episode, data_dir)
        if not ep_dir:
            logging.info(f"Episode directory not found for S{season}E{episode:02d}")
            return None
        filepath = ep_dir / "scenes_embedding.json"
        if not filepath.exists():
            logging.info(f"Scene embeddings file not found for S{season}E{episode:02d} at {filepath}")
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            return None
        # new format: list of dicts with 'embedding' key
        if isinstance(data, list) and all(isinstance(el, dict) and 'embedding' in el for el in data):
            return [el['embedding'] for el in data]
        # legacy: assume list of lists
        return data

    def read_summary(self, season: int, episode: int, data_dir: str = "data") -> Optional[str]:
        '''
        Read summary from data/Season_{season}/S{season}E{episode:02d}_{name}/summary.txt for a specific episode.
        '''
        ep_dir = self._find_episode_dir(season, episode, data_dir)
        if not ep_dir:
            logging.info(f"Episode directory not found for S{season}E{episode:02d}")
            return None
        filepath = ep_dir / "summary.txt"
        if not filepath.exists():
            logging.info(f"Summary file not found for S{season}E{episode:02d} at {filepath}")
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

def read_story_from_files(
        title: str, 
        data_dir: str = "data", 
        force_reembedding: bool = False, 
        save_embeddings: bool = False, 
        compute_embeddings: bool = False
        ) -> Story:
    manager = StoryManager(title=title)
    data_path = Path(data_dir)
    print(f"Reading story '{title}' from episode directories in '{data_path.absolute()}'...")

    # Try to load episode names from the master JSON if it exists
    episode_names: Dict[str, str] = {}
    master_json = data_path / "agents_of_shield.json"
    if master_json.exists():
        try:
            with open(master_json, 'r', encoding='utf-8') as f:
                story_data = json.load(f)
            for season_data in story_data.get("seasons", []):
                for ep_data in season_data.get("episodes", []):
                    key = f"S{ep_data['season']}E{ep_data['episode']:02d}"
                    episode_names[key] = ep_data.get("name", key)
        except Exception:
            pass

    # Scan for Season_X / SxEyy_Name directories containing any episode data
    season_pattern = re.compile(r"^Season_(\d+)$")
    ep_pattern = re.compile(r"^S(\d+)E(\d+)_(.+)$")
    for season_entry in sorted(data_path.iterdir()):
        if not season_entry.is_dir():
            continue
        if not season_pattern.match(season_entry.name):
            continue
        for entry in sorted(season_entry.iterdir()):
            if not entry.is_dir():
                continue
            match = ep_pattern.match(entry.name)
            if not match:
                continue
            season = int(match.group(1))
            episode = int(match.group(2))
            dir_ep_name = match.group(3)  # episode name from directory
            ep_key = f"S{season}E{episode:02d}"

            # Check if directory contains any recognised data files
            synopsis_file = entry / "synopsis.txt"
            transcript_file = entry / "transcript.csv"
            identifiers_file = entry / "identifiers.json"
            scenes_dir = entry / "scenes"
            if not any(p.exists() for p in [synopsis_file, transcript_file, identifiers_file, scenes_dir]):
                continue

            logging.info(f"Processing episode directory: {ep_key}")
            name = episode_names.get(ep_key, dir_ep_name)

            # Read text data
            synopsis_text = manager.read_synopsis(season, episode, data_dir)
            summary_text = manager.read_summary(season, episode, data_dir)
            transcript_lines = manager.read_transcript(season, episode, data_dir)

            # Read identifiers (roles, aliases, affiliations, locations)
            identifiers = manager.read_identifiers(season, episode, data_dir)
            roles = identifiers.get("role_ids", []) if identifiers else []
            role_aliases = identifiers.get("aliases", []) if identifiers else []
            affiliations = identifiers.get("affiliations", []) if identifiers else []
            locations = identifiers.get("locations", []) if identifiers else []

            # Read scenes
            scenes = manager.read_scenes(season, episode, data_dir)
            if not scenes:
                logging.info(f"No scenes found for {ep_key}, will create an empty list.")
                scenes = []
                scenes_embedding = []
            else:
                logging.info(f"Read {len(scenes)} scenes for {ep_key}.")
                scenes_embedding = []
                
                if compute_embeddings:
                    # add scene embeddings if available
                    scenes_embedding = manager.read_embeddings(season, episode, data_dir)
                    if not scenes_embedding or force_reembedding:
                        logging.info(f"No scene embeddings found for {ep_key}, will compute again.")
                        embedding_model = EmbeddingModel()
                        items = []
                        for scene in scenes:
                            metadata = scene.model_dump()
                            items.append({"text": scene.description, "metadata": metadata})
                        # add items so the embedding model stores metadata alongside embeddings
                        embedding_model.add(items)
                        # build combined structure for persistence: [{'embedding': [...], 'metadata': {...}}, ...]
                        combined = []
                        for emb, item in zip(embedding_model.embeddings, embedding_model.data):
                            emb_list = emb.tolist() if hasattr(emb, "tolist") else list(emb)
                            combined.append({"embedding": emb_list, "metadata": item.get("metadata", {})})
                        # keep scenes_embedding as list of embedding vectors for Episode model
                        scenes_embedding = [c["embedding"] for c in combined]
                        
                        # save the computed embeddings + metadata to a JSON file for future use
                        ep_dir = manager._find_episode_dir(season, episode, data_dir)
                        if ep_dir and save_embeddings:
                            embedding_filepath = ep_dir / "scenes_embedding.json"
                            with open(embedding_filepath, 'w', encoding='utf-8') as f:
                                json.dump(combined, f, ensure_ascii=False, indent=4)
                else:
                    logging.info(f"Skipping embeddings for {ep_key} (compute_embeddings=False).")

            manager.add_episode(
                season=season, episode=episode, name=name,
                synopsis=synopsis_text, summary=summary_text,
                transcript=transcript_lines,
                scenes=scenes,
                scenes_embedding=scenes_embedding,
                roles=roles, role_aliases=role_aliases,
                affiliations=affiliations,
                locations=locations
            )

    return manager.story

if __name__ == "__main__":
    story = read_story_from_files(title="Agents of S.H.I.E.L.D.", data_dir="data")
    # save story to JSON
    story.save_to_json("data/agents_of_shield.json")

    season_1 = story.get_season(1)

    from textwrap import fill
    scenes = list(season_1.vec_search_scenes(query="what happened at the hub", top_k=10, metadata_filter={"roles": ["skye"]}))

    for scene in scenes:
        print("-" * 80)
        print(f"Scene {scene.num} in episode {scene.episode} is set in {scene.location} - {scene.scene_name}")
        print(fill(scene.description, width=80, initial_indent='    ', subsequent_indent='    '))