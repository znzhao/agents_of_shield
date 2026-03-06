"""
PovParser - LangGraph-based agent that parses Agents of S.H.I.E.L.D. episodes
into structured scenes, character identifiers, and narrative summaries.
"""

import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict

# Ensure project root is on sys.path so absolute imports (core.*, model_structures.*, etc.) work
# even when this file is executed directly as a script.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from core.llm_engine import Engine
from model_structure.stories import (
    Story, Season, Episode, Scene, SETimestamp, RoleID,
    read_story_from_files,
)

logger = logging.getLogger(__name__)


# Module-level validators (module-level functions are deepcopy/pickle-safe)
def validate_episode_role_ids(value, allowed_person_ids=None):
    if allowed_person_ids is not None:
        for role_id in value:
            if role_id not in allowed_person_ids:
                raise ValueError(f"Role ID '{role_id}' is not in the allowed person IDs list.")
    return value


def validate_episode_affiliations(value, allowed_affiliations=None):
    if allowed_affiliations is not None:
        for affiliation in value:
            if affiliation not in allowed_affiliations:
                raise ValueError(f"Affiliation '{affiliation}' is not in the allowed affiliations list.")
    return value


def validate_episode_locations(value, allowed_locations=None):
    if allowed_locations is not None:
        for location in value:
            if location not in allowed_locations:
                raise ValueError(f"Location '{location}' is not in the allowed locations list.")
    return value


def validate_roles(value, allowed_roles=None):
    if allowed_roles is not None:
        for role in value:
            if role not in allowed_roles:
                raise ValueError(f"Role '{role}' is not in the allowed roles list.")
    return value


def validate_location(value, allowed_locations=None):
    if allowed_locations is not None and value != "unknown":
        if value not in allowed_locations:
            raise ValueError(f"Location '{value}' is not in the allowed locations list.")
    return value


# ===============================================================================
# Pydantic response models - structured output schemas for the LLM
# ===============================================================================
class SeasonResponse(BaseModel):
    """Main recurring characters identified for an entire season."""

    roles: List[RoleID] = Field(
        description=(
            "List of MAIN recurring characters for this season. "
            "Include characters who will appear in later seasons or episodes and drive the story. "
            "Exclude one-off minor characters, concepts, titles, and nicknames. "
            "Stable snake_case identifier for the physical person/character, "
            "e.g. 'phil_coulson', 'skye'. Must be the REAL name, "
            "never a title, rank, nickname or concept."
        )
    )

    locations: List[str] = Field(
        description=(
            "List of important in-universe locations for this season, e.g. 'New York City', "
            "'S.H.I.E.L.D. Helicarrier', 'Hydra Base', as detailed as possible. "
            "Exclude generic locations like 'city' or 'building' — be specific when possible."
        )
    )

    affiliations: List[str] = Field(
        description=(
            "List of important affiliations/groups for this season, e.g. 'S.H.I.E.L.D.', 'Hydra', "
            "'Inhumans', 'LMDs', as detailed as possible. Exclude generic affiliations "
            "like 'organization' or 'group' — be specific when possible."
        )
    )

class IdentifiersResponse(BaseModel):
    """Identifiers extracted from a single episode."""

    # All identifiers that APPEAR in this episode (new + previously established)
    episode_role_ids: List[RoleID] = Field(
        description=("ALL role_ids that appear or are active in this episode."
        "Must be a subset of the season's allowed person_ids.")
    )
    episode_aliases: List[str] = Field(
        description="ALL human-readable aliases mentioned in this episode."
    )
    episode_affiliations: List[str] = Field(
        description=("ALL affiliations mentioned or relevant in this episode."
        "Must be a subset of the season's allowed affiliations.")
    )
    episode_locations: List[str] = Field(
        description=("ALL in-universe locations featured in this episode."
        "Must be a subset of the season's allowed locations.")
    )
    # Validators are provided as module-level callables to avoid storing
    # bound method/classmethod objects on the class which can break deepcopy/pickle.
    _model_validators = {
        "episode_role_ids": validate_episode_role_ids,
        "episode_affiliations": validate_episode_affiliations,
        "episode_locations": validate_episode_locations,
    }

class SceneItem(BaseModel):
    """A single scene extracted by the LLM.

    Field types mirror the Scene model from model_structures.stories so that
    Pydantic validates/normalises the LLM output at parse-time (e.g. RoleID
    BeforeValidators, Literal constraints for significance, vibe,
    weather, time_of_day).
    """

    scene_name: str = Field(
        description="CamelCase scene name without spaces, e.g. 'TheBusConflict' or 'CoulsonVsWard'."
    )
    description: str = Field(
        description="Detailed description of the scene including key events, character actions, and dialogue summary."
    )
    roles: List[RoleID] = Field(
        description=(
            "List of role_ids (strings) that appear or are active in this scene. "
            "Only include role_ids that are present in the episode's episode_role_ids list, "
            "do NOT invent new role_ids here. If a character appears in the scene "
            "but has no role_id, simply omit them from the roles list."
        )
    )
    significance: Literal['minor', 'major', 'climactic'] = Field(
        description="One of: 'minor', 'major', 'climactic'."
    )
    vibe: Literal[
        'tense', 'emotional', 'action-packed', 'comedic', 'mysterious', 
        'romantic', 'tragic', 'hopeful', 'suspenseful', 'dramatic', 
        'dark', 'lighthearted', 'intense', 'melancholic', 'thrilling'
    ] = Field(
        description=(
            "One of: 'tense', 'emotional', 'action-packed', 'comedic', 'mysterious', "
            "'romantic', 'tragic', 'hopeful', 'suspenseful', 'dramatic', 'dark', "
            "'lighthearted', 'intense', 'melancholic', 'thrilling'."
        )
    )
    location: Optional[str] = Field(
        default="unknown", 
        description=("In-universe location of the scene." \
        "Must be one of the episode's episode_locations or 'unknown' if not specified or unclear.")
        )
    transcript_start_line: int = Field(
        description=(
            "The 1-indexed line number in the numbered transcript where this scene BEGINS. "
            "The first scene should normally start at line 1. Each subsequent scene's "
            "start_line marks where the previous scene's transcript ends (exclusive). "
            "Every transcript line must belong to exactly one scene with no gaps or overlaps."
        )
    )

class ScenesResponse(BaseModel):
    """List of scenes for one episode."""
    scenes: List[SceneItem]

class SummaryResponse(BaseModel):
    """Cumulative narrative summary through the current episode."""

    summary: str = Field(
        description=(
            "A concise but comprehensive narrative summary of everything important "
            "that has happened in the story through this episode. 2-3 paragraphs. "
            "Cover major plot points, character arcs, and significant events."
        )
    )


# ===============================================================================
# LangGraph state
# ===============================================================================

class PovParserState(TypedDict):
    # -- Inputs --
    timestamp: dict             # Serialised SETimestamp {"season": int, "episode": int}
    episode_name: str
    synopsis: str
    transcript: list            # List[Dict[str, str]]
    prev_summary: str           # Cumulative narrative summary from previous episode (empty string if first episode)

    # -- Context from prior episodes --
    prev_summary: str           # Empty string -> first episode

    # -- Computed by load_seasons --
    season_role_ids: list
    season_affiliations: list
    season_locations: list

    # -- Computed by check_context --
    is_first_episode: bool

    # -- Outputs from extract_identifiers --
    episode_role_ids: list
    episode_aliases: list
    episode_affiliations: list
    episode_locations: list

    # -- Outputs from create_scenes --
    scenes: list

    # -- Outputs from create_summary --
    episode_summary: str

# ===============================================================================
# PovParser agent
# ===============================================================================

class PovParser:
    """
    LangGraph-based agent that parses a single Agents of S.H.I.E.L.D. episode.

    Nodes:
        1. load_seasons          - Load (or create) data/Season_{n}/season_identifiers.json with
                                   the season's role_ids, affiliations, and locations.
        2. check_context         - Determine if this is the very first episode.
        3. extract_identifiers   - Extract episode level role_ids, aliases, affiliations, locations.
        4. create_scenes         - Produce a list of Scene objects.
        5. save_scenes           - Persist scene & delta JSON files.
        6. create_summary        - Write cumulative narrative summary.
    """

    def __init__(self, timestamp: SETimestamp):
        self.timestamp = timestamp
        self.engine_mini = Engine(model="gpt-5-mini")  # For load_seasons node
        self.engine = Engine(model="gpt-4.1")  # For all other nodes
        self.graph = self._build_graph()

    # -- Graph construction -------------------------------------------------

    def _build_graph(self):
        builder = StateGraph(PovParserState)

        builder.add_node("load_seasons", self._node_load_seasons)
        builder.add_node("check_context", self._node_check_context)
        builder.add_node("extract_identifiers", self._node_extract_identifiers)
        builder.add_node("create_scenes", self._node_create_scenes)
        builder.add_node("save_scenes", self._node_save_scenes)
        builder.add_node("create_summary", self._node_create_summary)

        builder.set_entry_point("load_seasons")
        builder.add_edge("load_seasons", "check_context")        
        builder.add_edge("check_context", "extract_identifiers")
        builder.add_edge("extract_identifiers", "create_scenes")
        builder.add_edge("create_scenes", "save_scenes")
        builder.add_edge("save_scenes", "create_summary")
        builder.add_edge("create_summary", END)

        return builder.compile()

    # -- Node implementations -----------------------------------------------
    def _node_load_seasons(self, state: PovParserState) -> dict:
        """Step 1: load (or create) the season-level season_identifiers.json with role_ids, affiliations, and locations.

        Checks for ``data/Season_{n}/season_identifiers.json``.  If the file exists the
        identifiers are loaded directly.  If it is absent, all synopsis files for
        the season are gathered and an LLM call determines the main recurring
        characters, locations and affiliations, which are then persisted for future runs.
        """
        ts = SETimestamp(**state["timestamp"])
        season_dir = Path("data") / f"Season_{ts.season}"
        identifiers_path = season_dir / "season_identifiers.json"
        # If identifiers_path exists, load season identifiers
        if identifiers_path.exists():
            with open(identifiers_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                season_role_ids: List[str] = data.get("roles", [])
                season_affiliations: List[str] = data.get("affiliations", [])
                season_locations: List[str] = data.get("locations", [])

            logger.info(
            f"[load_seasons] Loaded {len(season_role_ids)} roles, "
            f"{len(season_affiliations)} affiliations, "
            f"and {len(season_locations)} locations from {identifiers_path}. "
            )
            return {
            "season_role_ids": season_role_ids,
            "season_affiliations": season_affiliations,
            "season_locations": season_locations,
            }

        # -- season_identifiers.json absent -> gather all synopses and call LLM ------
        ep_pattern = re.compile(r"^S(\d+)E(\d+)")
        synopses_block = ""
        for entry in sorted(season_dir.iterdir()):
            if not entry.is_dir():
                continue
            m = ep_pattern.match(entry.name)
            if not m:
                continue
            synopsis_file = entry / "synopsis.txt"
            if not synopsis_file.exists():
                continue
            with open(synopsis_file, "r", encoding="utf-8") as f:
                text = f.read().strip()
            ep_label = f"S{m.group(1)}E{int(m.group(2)):02d}"
            synopses_block += f"\n\n### {ep_label}\n{text}"
        
        # get all previous seasons role_ids, affiliations, and locations for context
        prev_season_role_ids = []
        prev_season_affiliations = []
        prev_season_locations = []
        for s in range(1, ts.season):
            prev_season_dir = Path("data") / f"Season_{s}"
            prev_identifiers_path = prev_season_dir / "season_identifiers.json"
            if prev_identifiers_path.exists():
                with open(prev_identifiers_path, "r", encoding="utf-8") as f:
                    prev_data = json.load(f)
                prev_season_role_ids.extend(prev_data.get("roles", []))
                prev_season_affiliations.extend(prev_data.get("affiliations", []))
                prev_season_locations.extend(prev_data.get("locations", []))

        # deduplicate previous context lists
        prev_season_role_ids = list(set(prev_season_role_ids))
        prev_season_affiliations = list(set(prev_season_affiliations))
        prev_season_locations = list(set(prev_season_locations))
        
        system_prompt = f"""You are an expert media analyst for the TV show Agents of S.H.I.E.L.D.
## Task
Below are the synopses for every episode in Season {ts.season}.
1. Identify the MAIN RECURRING characters for this season — characters who appear
in multiple episodes and are central to the story.
2. Identify important affiliations/groups featured in this season.
3. Identify important locations featured in this season.

## CRITICAL: NO DUPLICATES
Ensure each role_id, affiliation, and location appears EXACTLY ONCE in your response.
Do NOT list the same character, group, or location multiple times under different names.

## Rules for role_ids
- Use the character's REAL full name in snake_case (e.g. 'phil_coulson',
    'daisy_johnson', 'melinda_may').
- NEVER use a title, rank, nickname, or concept as a role_id.
    Bad: 'director_coulson', 'agent_may', 'the_clairvoyant'
    Good: 'phil_coulson', 'melinda_may'
- Each role_id must be unique and represent exactly one individual.
- Omit characters who appear in only one episode and have no lasting
    impact on the season's story (minor/one-off characters).
- If a character is very important for the following season but only 
    appears in one episode of this season, you may still include them.

## Rules for affiliations
- Be as specific and detailed as possible. For example, prefer 'S.H.I.E.L.D.' over 'organization', or 'Hydra' over 'group'.
- Previously identified affiliations from prior seasons MUST be reused — never create a duplicate.
- Include all affiliations that appear in this season's synopses, even if they were established in previous seasons.
- Keep the consistency of affiliation names across seasons. If an affiliation was established in a previous season, use the same identifier for it in this season.

Here are all previously established affiliations (REUSE these, do NOT duplicate):
{json.dumps(prev_season_affiliations)}

## Rules for locations
- Be as specific and detailed as possible. For example, prefer 'S.H.I.E.L.D. Helicarrier' over just 'Helicarrier', or 'New York City' over 'city'.
- Previously identified locations from prior seasons MUST be reused — never create a duplicate.
- Include all locations that appear in this season's synopses, even if they were established in previous seasons.
- Keep the consistency of location names across seasons. If a location was established in a previous season, use the same identifier for it in this season.

Here are all previously established locations (REUSE these, do NOT duplicate):
{json.dumps(prev_season_locations)}

## IMPORTANT for all identifiers
- Keep the consistency of role_ids across seasons. If a character, like 'skye', was established as a role_id in season 1, 
    continue to use 'skye' in season 2 even after her name is revealed to be 'daisy_johnson'. Do NOT switch to 'daisy_johnson' in season 2 
    if 'skye' was the established role_id in season 1.

Here are all previously established role_ids (REUSE these, do NOT change them):
{json.dumps(prev_season_role_ids)}
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"""## Season {ts.season} synopses:
{synopses_block}
""")
        ]

        result: SeasonResponse = self.engine_mini.invoke(
            messages, base_model=SeasonResponse
        )

        # Deduplicate to prevent the LLM from providing duplicate identifiers
        unique_roles = list(dict.fromkeys(result.roles))  # Preserves order, removes duplicates
        unique_affiliations = list(dict.fromkeys(result.affiliations))
        unique_locations = list(dict.fromkeys(result.locations))

        # Persist so subsequent runs skip the LLM call
        season_dir.mkdir(parents=True, exist_ok=True)
        identifiers_data = {
            "season": ts.season,
            "roles": unique_roles,
            "affiliations": unique_affiliations,
            "locations": unique_locations,
        }
        with open(identifiers_path, "w", encoding="utf-8") as f:
            json.dump(identifiers_data, f, ensure_ascii=False, indent=4)

        season_role_ids: List[str] = unique_roles
        season_affiliations: List[str] = unique_affiliations
        season_locations: List[str] = unique_locations
        logger.info(
            f"[load_seasons] Created {identifiers_path} with "
            f"{len(season_role_ids)} roles: {season_role_ids}, "
            f"{len(season_affiliations)} affiliations: {season_affiliations}, "
            f"{len(season_locations)} locations: {season_locations}"
        )
        return {
            "season_role_ids": season_role_ids,
            "season_affiliations": season_affiliations,
            "season_locations": season_locations,
        }

    def _node_check_context(self, state: PovParserState) -> dict:
        """Step 1: decide whether this is the very first episode of the story."""
        has_prior_context = (
            (state.get("prev_summary") and state["prev_summary"].strip() != "")
            or bool(state.get("prev_role_ids"))
            or bool(state.get("prev_aliases"))
            or bool(state.get("prev_affiliations"))
            or bool(state.get("prev_locations"))
        )
        is_first = not has_prior_context
        logger.info(
            f"[check_context] {SETimestamp(**state['timestamp'])} - "
            f"is_first_episode={is_first}"
        )
        return {"is_first_episode": is_first}

    # -- Step 3: extract identifiers ----------------------------------------

    def _node_extract_identifiers(self, state: PovParserState) -> dict:
        """
        Step 3: determine unique role_ids, aliases, affiliations, locations.
        """
        ts = SETimestamp(**state["timestamp"])

        system_prompt = f"""You are an expert media analyst parsing TV episodes into structured data.

## CRITICAL CONSTRAINT: USE ONLY ALLOWED IDENTIFIERS
You MUST only use role_ids, affiliations, and locations from the allowed lists below.
Creating NEW role_ids, affiliations, or locations is STRICTLY PROHIBITED.

If a character, group, or place appears in the episode but is NOT in the allowed lists, 
you MUST OMIT it from your response. Do not invent identifiers.

## Task
Extract identifiers that are **both** (1) present in the episode AND (2) in the allowed lists:
- Role IDs: unique snake_case identifiers for characters (e.g. 'phil_coulson', 'skye').
- Aliases: human-readable display names for characters (e.g. 'Agent Phil Coulson', 'Skye').
- Affiliations: groups or organisations characters belong to (e.g. 'S.H.I.E.L.D.', 'Hydra').
- Locations: specific in-universe places (e.g. 'New York City', 'Zephyr One').

## ALLOWED Season's main characters (role_ids) — ONLY use these:
{json.dumps(state['season_role_ids'])}

## ALLOWED Season's affiliations — ONLY use these:
{json.dumps(state['season_affiliations'])}

## ALLOWED Season's locations — ONLY use these:
{json.dumps(state['season_locations'])}

## Examples of INCORRECT behavior (DO NOT DO THIS):
- Episode has a character 'Gideon Malick' but 'gideon_malick' is NOT in allowed role_ids → OMIT IT
- Episode mentions 'S.H.I.E.L.D. Science Division' but 'S.H.I.E.L.D. Science Division' is NOT in allowed affiliations → OMIT IT
- Episode is set in 'Tokyo' but 'Tokyo' is NOT in allowed locations → OMIT IT

## Rules for Aliases
- Keep aliases simple and avoid inventing new formats. Use names/titles that actually appear in the dialogue or synopsis.
- Do NOT create aliases that don't exist in the content.

## Deduplication
- Ensure no duplicate role_ids, affiliations, or locations in your response.
- Each identifier should appear exactly once in the lists you return.
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"""## Current episode: {ts.timestamp()} - {state['episode_name']}

### Synopsis:
{state['synopsis']}

### Transcript (excerpt):
{self._format_transcript(state['transcript'])}

Analyse the episode thoroughly and extract identifiers.
"""
            ),
        ]

        result: IdentifiersResponse = self.engine.invoke(
            messages, base_model=IdentifiersResponse
        )

        # Post-process: Filter to only allowed identifiers and deduplicate
        filtered_role_ids = [
            rid for rid in result.episode_role_ids 
            if rid in state["season_role_ids"]
        ]
        # Remove duplicates while preserving order
        filtered_role_ids = list(dict.fromkeys(filtered_role_ids))

        filtered_affiliations = [
            aff for aff in result.episode_affiliations 
            if aff in state["season_affiliations"]
        ]
        filtered_affiliations = list(dict.fromkeys(filtered_affiliations))

        filtered_locations = [
            loc for loc in result.episode_locations 
            if loc in state["season_locations"]
        ]
        filtered_locations = list(dict.fromkeys(filtered_locations))

        # Deduplicate aliases
        filtered_aliases = list(dict.fromkeys(result.episode_aliases))

        logger.info(
            f"[extract_identifiers] {ts} - "
            f"{len(filtered_role_ids)} roles (filtered from {len(result.episode_role_ids)}), "
            f"{len(filtered_aliases)} aliases, "
            f"{len(filtered_affiliations)} affiliations (filtered from {len(result.episode_affiliations)}), "
            f"{len(filtered_locations)} locations (filtered from {len(result.episode_locations)})"
        )

        return {
            "episode_role_ids": filtered_role_ids,
            "episode_aliases": filtered_aliases,
            "episode_affiliations": filtered_affiliations,
            "episode_locations": filtered_locations,
        }

    # -- Step 4: create scenes ----------------------------------------------

    def _node_create_scenes(self, state: PovParserState) -> dict:
        """Step 4: break the episode into a chronological list of Scene objects."""
        ts = SETimestamp(**state["timestamp"])

        all_role_ids = state["episode_role_ids"]
        all_locations = state["episode_locations"]

        total_lines = len(state['transcript']) if state['transcript'] else 0

        system_prompt = f"""You are an expert media analyst. Break the following TV episode into
a chronological sequence of **scenes**.

## CRITICAL CONSTRAINT: USE ONLY ALLOWED IDENTIFIERS
You MUST only use role_ids from the episode's extracted role_ids list.
You MUST only use locations from the episode's extracted locations list.

Creating NEW role_ids or locations for scenes is STRICTLY PROHIBITED.
If a character or location appears in a scene but is NOT in the allowed lists, OMIT IT.

## Rules
- The `roles` field in each scene must contain **only** role_ids from this list:
  {json.dumps(all_role_ids)}
- The `location` field must be **only** from this list or 'unknown':
  {json.dumps(all_locations)}
- If a character appears in a scene but has NO role_id in the allowed list, DO NOT invent one — simply omit the character.
- If a location is not in the allowed list, set location to 'unknown'.

- scene_name: CamelCase, no spaces (e.g. 'CoulsonMeetsReyes'). Must be unique within the episode.
- significance: one of 'minor', 'major', 'climactic'.
- vibe: one of 'tense', 'emotional', 'action-packed', 'comedic', 'mysterious',
  'romantic', 'tragic', 'hopeful', 'suspenseful', 'dramatic', 'dark',
  'lighthearted', 'intense', 'melancholic', 'thrilling'.
- Aim for 5-15 scenes per episode covering all major story beats.
- description should be detailed (2-4 sentences minimum).

## Deduplication
- Ensure no duplicate role_ids within a single scene.
- Ensure no duplicate scenes.

## Examples of INCORRECT behavior (DO NOT DO THIS):
- Character 'Gideon Malick' appears in scene but 'gideon_malick' NOT in allowed roles →  DO NOT ADD 'gideon_malick' to roles, OMIT IT
- Flashback to 'Tokyo' but 'Tokyo' NOT in allowed locations → SET location='unknown', DO NOT INVENT 'Tokyo'
- A villain 'Red Skull' appears but 'red_skull' NOT in allowed roles → OMIT from roles, DO NOT ADD IT

## Transcript scene breaker
The transcript below has **numbered lines** (e.g. [1], [2], …).
The total number of transcript lines is **{total_lines}**.
For each scene, set `transcript_start_line` to the **1-indexed line number** where
that scene BEGINS in the transcript. Rules:
- The first scene MUST have `transcript_start_line = 1`.
- Start lines must be strictly increasing across scenes (each scene starts after
  the previous one).
- Every transcript line must belong to exactly one scene — the previous scene's
  lines end just before the next scene's `transcript_start_line`.
- The last scene implicitly covers from its start line through line {total_lines}.

## Episode: {ts.timestamp()} - {state['episode_name']}

### Synopsis:
{state['synopsis']}

### Transcript (numbered lines):
{self._format_transcript(state['transcript'], numbered=True)}
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Create the chronological list of scenes for this episode."),
        ]

        result: ScenesResponse = self.engine.invoke(messages, base_model=ScenesResponse)

        # -- Split the episode transcript into per-scene slices ----------
        transcript = state.get("transcript") or []
        total_lines = len(transcript)

        # Collect and sanitise start-line breakers (1-indexed, strictly increasing)
        raw_starts = [sc.transcript_start_line for sc in result.scenes]
        sanitised_starts: List[int] = []
        prev_start = 0
        for s in raw_starts:
            clamped = max(prev_start + 1, min(s, total_lines or 1))
            sanitised_starts.append(clamped)
            prev_start = clamped

        # Build per-scene transcript slices (no overlap, full coverage)
        scene_transcripts: List[Optional[List[Dict[str, str]]]] = []
        for i, start in enumerate(sanitised_starts):
            end = sanitised_starts[i + 1] - 1 if i + 1 < len(sanitised_starts) else total_lines
            # Convert 1-indexed inclusive range to 0-indexed Python slice
            scene_transcripts.append(transcript[start - 1 : end] if total_lines else None)

        # Convert to validated Scene objects, ensuring unique scene_names
        scenes_dicts = []
        seen_names: set = set()
        allowed_role_ids = set(state["episode_role_ids"])  # Only allow roles that were extracted for this episode
        allowed_locations = set(state["episode_locations"])  # Only allow locations that were extracted for this episode

        for idx, sc in enumerate(result.scenes, start=1):
            name = sc.scene_name
            if name in seen_names:
                name = f"{name}_{len(seen_names)}"
            seen_names.add(name)

            # Filter scene roles to only include those in episode_role_ids
            filtered_scene_roles = [
                role for role in sc.roles 
                if role in allowed_role_ids
            ]
            # Deduplicate roles within this scene
            filtered_scene_roles = list(dict.fromkeys(filtered_scene_roles))

            # Filter location to allowed episode locations
            scene_location = sc.location
            if scene_location and scene_location != "unknown" and scene_location not in allowed_locations:
                logger.warning(
                    f"[create_scenes] Scene '{name}' has location '{scene_location}' "
                    f"not in allowed locations. Setting to 'unknown'."
                )
                scene_location = "unknown"

            # Build a Scene to run all model_structures validators (Literal
            # constraints, RoleID/PersonID normalisers, etc.) at creation time.
            try:
                scene = Scene(
                    season=ts.season,
                    episode=ts.episode,
                    num=idx,
                    scene_name=name,
                    roles=filtered_scene_roles,
                    description=sc.description,
                    significance=sc.significance,
                    vibe=sc.vibe,
                    location=scene_location,
                    transcript=scene_transcripts[idx - 1] if idx - 1 < len(scene_transcripts) else None,
                )
                scenes_dicts.append(scene.model_dump())
            except Exception as e:
                logger.warning(f"[create_scenes] Skipping invalid scene '{name}': {e}")

        logger.info(f"[create_scenes] {ts} - created {len(scenes_dicts)} scenes")
        return {"scenes": scenes_dicts}

    # -- Step 5: save scenes -----------------------------------------
    def _node_save_scenes(self, state: PovParserState) -> dict:
        """Step 5: persist parsed scenes, person deltas, and identifiers to disk."""
        ts = SETimestamp(**state["timestamp"])
        ep_dir = Path("data") / f"Season_{ts.season}" / f"{ts.timestamp()}_{state['episode_name']}"

        # Save scenes
        scenes_dir = ep_dir / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)

        for scene_dict in state["scenes"]:
            scene = Scene(**scene_dict)
            filepath = scenes_dir / f"{scene.id}.json"
            scene.save_to_json(str(filepath))
            logger.info(f"[save_scenes] Saved scene -> {filepath}")

        # Save episode identifiers so future single-episode runs can load context
        identifiers = {
            "role_ids": state["episode_role_ids"],
            "aliases": state["episode_aliases"],
            "affiliations": state["episode_affiliations"],
            "locations": state["episode_locations"],
        }
        identifiers_path = ep_dir / "identifiers.json"
        with open(identifiers_path, "w", encoding="utf-8") as f:
            json.dump(identifiers, f, ensure_ascii=False, indent=4)
        logger.info(f"[save_scenes] Saved identifiers -> {identifiers_path}")

        return {}

    # -- Step 6: cumulative summary -----------------------------------------
    def _node_create_summary(self, state: PovParserState) -> dict:
        """Step 6: create a cumulative narrative summary for the next episode."""
        ts = SETimestamp(**state["timestamp"])

        prior_block = ""
        if not state["is_first_episode"] and state["prev_summary"]:
            prior_block = (
                f"## Story so far (through previous episode):\n"
                f"{state['prev_summary']}\n\n"
            )

        system_prompt = f"""{prior_block}You are an expert media analyst.
Write a **cumulative narrative summary** covering everything important that has
happened in the story UP TO AND INCLUDING the current episode.

This summary will be used as context when parsing the NEXT episode, so it must
capture:
- Major plot points and turning points
- Character developments and relationship changes
- Key revelations and unresolved mysteries
- Current status of major characters and ongoing storylines

Keep it concise but comprehensive (3-5 paragraphs).

**Important:** Focus on the story itself without meta-references to episode numbers,
seasons, or production details. Write as if immersed in the narrative world — avoid
phrases like "in the first two episodes" or "so far in season X". Instead, describe
events as they naturally occurred in the story's timeline.

## Current episode: {ts.timestamp()} - {state['episode_name']}

### Synopsis:
{state['synopsis']}

### Scenes parsed (for reference):
{json.dumps(state['scenes'], indent=2)[:4000]}
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content="Write the cumulative story summary through this episode."
            ),
        ]

        result: SummaryResponse = self.engine.invoke(
            messages, base_model=SummaryResponse
        )

        # Persist summary so future single-episode runs can load it as context
        summary_dir = Path("data") / f"Season_{ts.season}" / f"{ts.timestamp()}_{state['episode_name']}"
        summary_dir.mkdir(parents=True, exist_ok=True)
        summary_path = summary_dir / "summary.txt"
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(result.summary)
        logger.info(f"[create_summary] {ts} - summary length: {len(result.summary)} chars, saved -> {summary_path}")
        return {"episode_summary": result.summary}

    @staticmethod
    def load_previous_context(
        target_ts: SETimestamp,
        data_dir: str = "data",
    ) -> Dict[str, Any]:
        """
        Scan the *data_dir* for previously parsed episode directories and
        load the summary from the most recent episode **before** *target_ts*.

        Each parsed episode is expected to have:
            - ``data/Season_{x}/{SxEyy}_{name}/summary.txt``        (cumulative narrative summary)

        Returns a dict suitable for unpacking into ``PovParser.parse()``:
            prev_summary
        """
        data_path = Path(data_dir)
        season_pattern = re.compile(r"^Season_(\d+)$")
        ep_pattern = re.compile(r"^S(\d+)E(\d+)")

        # Discover parsed episode directories (data/Season_x/SxEyy_name/)
        prior_episodes: List[tuple] = []  # (SETimestamp, Path)
        for season_entry in sorted(data_path.iterdir()):
            if not season_entry.is_dir():
                continue
            if not season_pattern.match(season_entry.name):
                continue
            for entry in sorted(season_entry.iterdir()):
                if not entry.is_dir():
                    continue
                m = ep_pattern.match(entry.name)
                if not m:
                    continue
                ep_ts = SETimestamp(season=int(m.group(1)), episode=int(m.group(2)))
                if ep_ts < target_ts:
                    prior_episodes.append((ep_ts, entry))

        prior_episodes.sort(key=lambda x: x[0])

        # Load summary from the most recent prior episode
        latest_summary: str = ""
        if prior_episodes:
            ep_ts, ep_dir = prior_episodes[-1]
            summary_file = ep_dir / "summary.txt"
            if summary_file.exists():
                with open(summary_file, "r", encoding="utf-8") as f:
                    latest_summary = f.read().strip()

        logger.info(
            f"[load_previous_context] Loaded context from most recent prior episode, "
            f"summary={'yes' if latest_summary else 'no'}"
        )

        return {
            "prev_summary": latest_summary,
        }

    # -- Cleanup --------------------------------------------------------------

    @staticmethod
    def clean_episode_parsed_data(
        ts: SETimestamp,
        episode_name: str,
        data_dir: str = "data",
    ) -> None:
        """
        Remove previously parsed data for a single episode while preserving
        raw source files (transcript.csv, synopsis.txt).

        Deleted artefacts:
            - scenes/          (directory)
            - person_deltas/   (directory)
            - identifiers.json
            - scenes_embedding.json
            - summary.txt
            - {SxEyy}.json     (episode-level JSON)
        """
        ep_dir = Path(data_dir) / f"Season_{ts.season}" / f"{ts.timestamp()}_{episode_name}"
        if not ep_dir.exists():
            return

        # Directories created by the parser
        for subdir in ("scenes", "person_deltas"):
            target = ep_dir / subdir
            if target.exists():
                shutil.rmtree(target)
                logger.info(f"[clean] Removed {target}")

        # Individual files created by the parser
        for filename in ("identifiers.json", "summary.txt", f"{ts.timestamp()}.json", "scenes_embedding.json"):
            target = ep_dir / filename
            if target.exists():
                target.unlink()
                logger.info(f"[clean] Removed {target}")

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _format_transcript(transcript: list, numbered: bool = False) -> str:
        """Format transcript entries as readable dialogue without truncation.

        Args:
            transcript: List of {'character': str, 'line': str} dicts.
            numbered: If True, prepend 1-indexed line numbers (e.g. '[1] CHARACTER: dialogue').
        """
        if not transcript:
            return "(no transcript available)"
        lines = []
        for idx, entry in enumerate(transcript, start=1):
            character = entry.get("character", "?")
            dialogue = entry.get("line", "")
            if numbered:
                lines.append(f"[{idx}] {character}: {dialogue}")
            else:
                lines.append(f"{character}: {dialogue}")
        return "\n".join(lines)

    # -- Public API ----------------------------------------------------------

    def parse(
        self,
        episode_name: str,
        synopsis: str,
        transcript: Optional[List[Dict[str, str]]] = None,
        prev_summary: str = "",
    ) -> Dict[str, Any]:
        """
        Run the full LangGraph pipeline for one episode.

        Person IDs are determined at the season level (``data/Season_{n}/people.json``)
        by the ``load_season_people`` node — not per-episode.
        """
        initial_state: PovParserState = {
            "timestamp": {
                "season": self.timestamp.season,
                "episode": self.timestamp.episode,
            },
            "episode_name": episode_name,
            "synopsis": synopsis or "",
            "transcript": transcript or [],
            "prev_summary": prev_summary or "",
            "is_first_episode": False,
            # Populated by extract_identifiers node
            "new_role_ids": [],
            "new_aliases": [],
            "new_affiliations": [],
            "new_locations": [],
            "episode_role_ids": [],
            "episode_aliases": [],
            "episode_affiliations": [],
            "episode_locations": [],
            "role_person_mapping": [],
            "scenes": [],
            "person_deltas": [],
            "episode_summary": "",
        }

        final_state = self.graph.invoke(initial_state)
        return final_state

# ===============================================================================
# CLI entry point
# ===============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="\033[94m%(asctime)s\033[0m - \033[92m%(name)s\033[0m - %(message)s",
    )

    # Usage:
    #   python -m processors.pov_parser <season> <ep>   -> parse a single episode

    if len(sys.argv) >= 3:
        season_num = int(sys.argv[1])
        episode_num = int(sys.argv[2])

        raw = read_story_from_files(
            "Agents of S.H.I.E.L.D.", "data"
        )
        raw.sort()

        target = None
        for ep in raw:
            if ep.season == season_num and ep.episode == episode_num:
                target = ep
                break

        if target is None:
            print(f"Episode S{season_num}E{episode_num:02d} not found.")
            sys.exit(1)

        ts = SETimestamp(season=season_num, episode=episode_num)

        # Clean previously parsed data for this episode to avoid stale artefacts
        PovParser.clean_episode_parsed_data(ts, episode_name=target.name, data_dir="data")

        # Load accumulated context from previously parsed episodes
        prev_ctx = PovParser.load_previous_context(ts, data_dir="data")
        logger.info(f"Loaded previous context for S{season_num}E{episode_num:02d}: "
                    f"prev_summary={'yes' if prev_ctx.get('prev_summary') else 'no'}")
        parser = PovParser(timestamp=ts)
        result = parser.parse(
            episode_name=target.name,
            synopsis=target.synopsis or "",
            transcript=target.transcript or [],
            **prev_ctx,
        )

        # Print readable subset (exclude raw transcript/synopsis from output)
        output = {
            k: v
            for k, v in result.items()
            if k not in ("transcript", "synopsis")
        }
        print(f'Parsed episode {ts.timestamp()} - {target.name}.')
    else:
        print("Usage: python -m processors.pov_parser <season> <episode>")
        sys.exit(1)