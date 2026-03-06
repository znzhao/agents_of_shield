"""
RoleParser - LangGraph-based agent that parses role profiles / deltas for a
single character across Agents of S.H.I.E.L.D. episodes.

Workflow
--------
1. check_role_in_episode  - Verify the role_id appears in this episode's
                            identifiers.json.  If absent → EXIT early.
2. check_first_appearance - Scan ALL episode directories across ALL seasons
                            before the target episode for existing
                            roles/{role_id}.json files.
3. load_previous_profile  - (only when not first appearance) Collect ALL prior
                            delta JSONs, build a Role, snapshot a full
                            RoleProfile baseline just before this episode.
4. parse_role             - Ask the LLM to produce either a RoleProfile (first
                            appearance) or a RoleDelta (subsequent appearance).
5. save_delta             - Convert RoleProfile → RoleDelta if necessary, then
                            persist as  data/Season_X/SXEyy_Name/roles/{role_id}.json
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

# Ensure project root is on sys.path for absolute imports.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from core.llm_engine import Engine
from model_structure.roles import (
    Role,
    RoleDelta,
    RoleProfile,
)
from model_structure.stories import Scene, SETimestamp

logger = logging.getLogger(__name__)


# ===============================================================================
# LangGraph state
# ===============================================================================

class RoleParserState(TypedDict):
    # -- Inputs --
    timestamp: dict          # {"season": int, "episode": int}
    role_id: str
    episode_name: str
    synopsis: str
    scenes: list             # List[Dict] - raw scene dicts from scenes/ folder

    # -- Computed by check_role_in_episode --
    is_role_in_episode: bool

    # -- Computed by check_first_appearance --
    is_first_appearance: bool

    # -- Loaded by load_previous_profile --
    previous_profile_json: str  # JSON string of the full RoleProfile snapshot just before this episode (empty = first appearance)
    prev_summary: str            # Cumulative narrative summary from the most recent prior episode (empty if none)

    # -- Output from parse_role --
    parsed_delta: dict        # The final RoleDelta dict ready for saving


# ===============================================================================
# RoleParser agent
# ===============================================================================

class RoleParser:
    """
    LangGraph-based agent that produces or updates a role profile for one
    character in one Agents of S.H.I.E.L.D. episode.

    Parameters
    ----------
    model : str
        LLM model name accepted by ``Engine``.
    role_id : str
        Snake_case character identifier, e.g. ``'phil_coulson'``.
    season : int
    episode : int
    data_dir : str
        Root data directory (default ``"data"``).
    """

    def __init__(
        self,
        model: str,
        role_id: str,
        season: int,
        episode: int,
        data_dir: str = "data",
    ):
        self.role_id = role_id
        self.timestamp = SETimestamp(season=season, episode=episode)
        self.data_dir = Path(data_dir)
        self.engine = Engine(model=model)
        self.graph = self._build_graph()

    # -------------------------------------------------------------------------
    # Graph construction
    # -------------------------------------------------------------------------

    def _build_graph(self):
        builder = StateGraph(RoleParserState)

        builder.add_node("check_role_in_episode", self._node_check_role_in_episode)
        builder.add_node("check_first_appearance", self._node_check_first_appearance)
        builder.add_node("load_previous_profile", self._node_load_previous_profile)
        builder.add_node("parse_role", self._node_parse_role)
        builder.add_node("save_delta", self._node_save_delta)

        builder.set_entry_point("check_role_in_episode")

        # After checking episode membership: skip everything if absent.
        builder.add_conditional_edges(
            "check_role_in_episode",
            lambda s: "check_first_appearance" if s["is_role_in_episode"] else END,
        )

        builder.add_edge("check_first_appearance", "load_previous_profile")

        # Always move to parse_role after loading (profile will be empty string on
        # first appearance, which is perfectly fine).
        builder.add_edge("load_previous_profile", "parse_role")
        builder.add_edge("parse_role", "save_delta")
        builder.add_edge("save_delta", END)

        return builder.compile()

    # -------------------------------------------------------------------------
    # Helper utilities
    # -------------------------------------------------------------------------

    def _find_episode_dir(self) -> Optional[Path]:
        """Return the episode directory path for self.timestamp, or None."""
        ep_pattern = re.compile(
            rf"^S{self.timestamp.season}E{self.timestamp.episode:02d}_"
        )
        season_dir = self.data_dir / f"Season_{self.timestamp.season}"
        if not season_dir.exists():
            return None
        for entry in season_dir.iterdir():
            if entry.is_dir() and ep_pattern.match(entry.name):
                return entry
        return None

    @staticmethod
    def _scenes_for_role(scenes: list, role_id: str) -> List[Scene]:
        """Deserialise scene dicts, filter to those featuring role_id, return Scene objects.

        Mirrors Season.search_scenes(role=role_id) logic without needing a full Season object.
        """
        result: List[Scene] = []
        for s in scenes:
            roles = s.get("roles", [])
            if role_id in roles:
                try:
                    result.append(Scene.model_validate(s))
                except Exception:
                    pass  # skip malformed scene dicts
        return result

    @staticmethod
    def _format_scenes(scenes: List[Scene]) -> str:
        """Format Scene objects as a compact but informative text block."""
        if not scenes:
            return "(no scenes featuring this role found)"
        lines = []
        for scene in scenes:
            header = (
                f"[{scene.timestamp()}-{scene.scene_name}] "
                f"({scene.significance}, {scene.vibe}, "
                f"loc={scene.location or 'unknown'})"
            )
            lines.append(header)
            lines.append(f"  {scene.description}")
            if scene.transcript:
                lines.append("  Transcript:")
                for line in scene.transcript:
                    speaker = line.get("character", "Unknown")
                    text = line.get("line", "")
                    lines.append(f"    {speaker}: {text}")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Node: check_role_in_episode
    # -------------------------------------------------------------------------

    def _node_check_role_in_episode(self, state: RoleParserState) -> dict:
        """Step 1 - verify the role_id is listed in the episode's identifiers.json."""
        ts = SETimestamp(**state["timestamp"])
        ep_dir = self._find_episode_dir()

        if ep_dir is None:
            logger.warning(
                f"[check_role_in_episode] Episode directory for {ts} not found."
            )
            return {"is_role_in_episode": False}

        identifiers_path = ep_dir / "identifiers.json"
        if not identifiers_path.exists():
            logger.warning(
                f"[check_role_in_episode] identifiers.json missing in {ep_dir}."
            )
            return {"is_role_in_episode": False}

        with open(identifiers_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        role_ids_in_episode: List[str] = data.get("role_ids", [])
        present = state["role_id"] in role_ids_in_episode

        logger.info(
            f"[check_role_in_episode] role_id='{state['role_id']}' present={present} "
            f"in {ts} (found ids: {role_ids_in_episode})"
        )
        return {"is_role_in_episode": present}

    # -------------------------------------------------------------------------
    # Node: check_first_appearance
    # -------------------------------------------------------------------------

    def _node_check_first_appearance(self, state: RoleParserState) -> dict:
        """Step 2 - scan all episodes *before* the target for an existing role file."""
        ts = SETimestamp(**state["timestamp"])
        role_id = state["role_id"]

        season_pattern = re.compile(r"^Season_(\d+)$")
        ep_pattern = re.compile(r"^S(\d+)E(\d+)")

        found_previous = False
        for season_entry in sorted(self.data_dir.iterdir()):
            if not season_entry.is_dir():
                continue
            m_s = season_pattern.match(season_entry.name)
            if not m_s:
                continue
            for ep_entry in sorted(season_entry.iterdir()):
                if not ep_entry.is_dir():
                    continue
                m_e = ep_pattern.match(ep_entry.name)
                if not m_e:
                    continue
                ep_ts = SETimestamp(
                    season=int(m_e.group(1)), episode=int(m_e.group(2))
                )
                if not ep_ts < ts:
                    continue  # only look at episodes strictly before the target
                role_file = ep_entry / "roles" / f"{role_id}.json"
                if role_file.exists():
                    found_previous = True
                    break
            if found_previous:
                break

        is_first = not found_previous
        logger.info(
            f"[check_first_appearance] role_id='{role_id}' "
            f"is_first_appearance={is_first}"
        )
        return {"is_first_appearance": is_first}

    # -------------------------------------------------------------------------
    # Node: load_previous_profile
    # -------------------------------------------------------------------------

    def _node_load_previous_profile(self, state: RoleParserState) -> dict:
        """Step 3 - scan ALL prior episodes across every season to:

        a) Load the most recent cumulative ``summary.txt`` (always, even on
           first character appearance — the story context is always useful).
        b) Collect ALL role delta files for role_id, build a Role, and snapshot
           a full RoleProfile baseline just before this episode (skipped on
           first appearance since no deltas exist yet).
        """
        ts = SETimestamp(**state["timestamp"])
        role_id = state["role_id"]
        is_first = state["is_first_appearance"]

        season_pattern = re.compile(r"^Season_(\d+)$")
        ep_pattern = re.compile(r"^S(\d+)E(\d+)")

        # Scan every episode directory strictly before ts, collecting:
        #   - role delta files  (for profile snapshot)
        #   - summary.txt paths (for narrative context)
        delta_candidates: List[tuple] = []   # (SETimestamp, Path)
        summary_candidates: List[tuple] = [] # (SETimestamp, Path)

        for season_entry in sorted(self.data_dir.iterdir()):
            if not season_entry.is_dir():
                continue
            if not season_pattern.match(season_entry.name):
                continue
            for ep_entry in sorted(season_entry.iterdir()):
                if not ep_entry.is_dir():
                    continue
                m_e = ep_pattern.match(ep_entry.name)
                if not m_e:
                    continue
                ep_ts = SETimestamp(
                    season=int(m_e.group(1)), episode=int(m_e.group(2))
                )
                if not ep_ts < ts:
                    continue

                role_file = ep_entry / "roles" / f"{role_id}.json"
                if role_file.exists():
                    delta_candidates.append((ep_ts, role_file))

                summary_file = ep_entry / "summary.txt"
                if summary_file.exists():
                    summary_candidates.append((ep_ts, summary_file))

        # --- Load most recent cumulative summary ----------------------------
        prev_summary = ""
        if summary_candidates:
            summary_candidates.sort(key=lambda x: x[0])
            _, latest_summary_file = summary_candidates[-1]
            prev_summary = latest_summary_file.read_text(encoding="utf-8").strip()
            logger.info(
                f"[load_previous_profile] Loaded summary from {latest_summary_file}"
            )

        # --- Build profile snapshot (skip on first appearance) --------------
        if is_first or not delta_candidates:
            return {"previous_profile_json": "", "prev_summary": prev_summary}

        delta_candidates.sort(key=lambda x: x[0])

        # The chronologically first file is always a RoleProfile (saved on first
        # appearance); every subsequent file is a RoleDelta.
        _, init_file = delta_candidates[0]
        with open(init_file, "r", encoding="utf-8") as f:
            init_profile = RoleProfile.model_validate_json(f.read())

        all_deltas: List[RoleDelta] = []
        for ep_ts, role_file in delta_candidates[1:]:
            with open(role_file, "r", encoding="utf-8") as f:
                all_deltas.append(RoleDelta.model_validate_json(f.read()))

        logger.info(
            f"[load_previous_profile] Loaded init profile + {len(all_deltas)} delta(s) for "
            f"'{role_id}' across {len(delta_candidates)} episode(s) before {ts}."
        )

        role_obj = Role(role_id=role_id, role_init_profile=init_profile, role_deltas=all_deltas)
        snapshot_ts = delta_candidates[-1][0]
        profile: RoleProfile = role_obj.snapshot(snapshot_ts)

        return {
            "previous_profile_json": profile.model_dump_json(indent=2),
            "prev_summary": prev_summary,
        }

    # -------------------------------------------------------------------------
    # Node: parse_role
    # -------------------------------------------------------------------------

    def _node_parse_role(self, state: RoleParserState) -> dict:
        """Step 4 - call the LLM to produce a RoleProfile or RoleDelta."""
        ts = SETimestamp(**state["timestamp"])
        role_id = state["role_id"]
        is_first = state["is_first_appearance"]
        previous_profile_json = state.get("previous_profile_json", "")

        # --- Build context ---------------------------------------------------
        synopsis_text = state.get("synopsis") or "(no synopsis available)"
        prev_summary_text = state.get("prev_summary") or "(no prior story summary available)"
        scenes_for_role = self._scenes_for_role(state.get("scenes", []), role_id)
        scenes_text = self._format_scenes(scenes_for_role)

        # --- Load episode identifiers (aliases + affiliations) ---------------
        ep_dir = self._find_episode_dir()
        known_aliases: List[str] = []
        known_affiliations: List[str] = []
        if ep_dir is not None:
            identifiers_path = ep_dir / "identifiers.json"
            if identifiers_path.exists():
                with open(identifiers_path, "r", encoding="utf-8") as _f:
                    _id_data = json.load(_f)
                known_aliases = _id_data.get("aliases", [])
                known_affiliations = _id_data.get("affiliations", [])

        # --- System prompt ---------------------------------------------------
        if is_first:
            task_description = f"""\
You are an expert character analyst for the TV show *Agents of S.H.I.E.L.D.*

## Task
This is the FIRST time the character with role_id **'{role_id}'** appears in the story.
Parse a complete **RoleProfile** for this character based solely on the episode content provided.

Fill in EVERY field that can be reasonably inferred from the content.
Use the exact JSON schema of RoleProfile — do NOT invent fields.

### RoleProfile JSON schema (for reference)
{json.dumps(RoleProfile.model_json_schema(), ensure_ascii=False, indent=2)}

### timestamp (fixed — do not change)
{{"season": {ts.season}, "episode": {ts.episode}}}

### role_id (fixed — do not change)
"{role_id}"
"""
            base_model = RoleProfile
        else:
            task_description = f"""\
You are an expert character analyst for the TV show *Agents of S.H.I.E.L.D.*

## Task
The character with role_id **'{role_id}'** has appeared before.
Parse a **RoleDelta** capturing what has CHANGED or evolved for this character based on the episode content.

Capture ONLY changes that are clearly and directly supported by the episode content.
Only update emotional state (core_emotions, moods, self_states) when the character goes
through a significant, explicitly depicted experience. Only include other dimensions (skills,
values, affiliations, goals) when there is unambiguous evidence of a real shift. When in
doubt, leave the list empty.

### Character's full profile baseline (snapshot just before this episode)
This is the character's complete current state. Your delta should describe
only what CHANGES relative to this profile during this episode.

{previous_profile_json}

### RoleDelta JSON schema (for reference)
{json.dumps(RoleDelta.model_json_schema(), ensure_ascii=False, indent=2)}

### timestamp (fixed — do not change)
{{"season": {ts.season}, "episode": {ts.episode}}}

### role_id (fixed — do not change)
"{role_id}"
"""
            base_model = RoleDelta

        system_prompt = task_description + f"""
        ## Guidelines
        - Base your analysis ONLY on the episode content below.
        - For a RoleDelta: action '+' means the trait/value increased or was added;
        '-' means it decreased or was removed.
        - The `description` field must characterise WHO the character is as a person — their role in
        the world, background, personality essence, and defining traits. Write it as a timeless
        character summary. Do NOT reference episode events (avoid phrases like "in this episode",
        "during this episode", "this week", or any similar episode-scoped language). 
        - Consider the character's full history up to this point, and the character arc they have been 
        on across episodes. When parsing changes, consider how they fit into the broader 
        trajectory of the character's development. Be detailed, and write one paragraph that summarizes 
        the character's evolution and whole history.
        - For emotional and mood changes, record nuance shifts. Use level numbers to 
        reflect intensity: 1 for subtle shifts, 2 for moderate changes, 3 for major arcs.
        When in doubt, leave the list empty rather than guessing. consider both modd increase and decrease.
        use level numbers to indicate the significance of the change.
        - Catch phrases — TARGET TOTAL: **no more than 8** across the whole profile after applying this delta.
        Before adding, count how many catch phrases currently exist in the baseline profile above.
        If the running total would exceed 8, you MUST drop older or less distinctive phrases first.
        Prioritise variety: each retained catch phrase should capture a **different** context, trigger, or 
        facet of the character's personality — do not keep near-duplicate phrases.
        Add a phrase only if it clearly and distinctively captures the character's voice or worldview;
        a single powerful utterance can qualify but do not add every memorable line.
        Actively remove phrases that: (a) the character hasn't used recently, (b) feel outdated given 
        their current arc, or (c) overlap with another retained phrase. 
        Most episodes should yield one to two additions and one to two removals.
        
        **Example:** For Phil Coulson, "It's a magical place" (said reflexively about Tahiti) reveals 
        emotional avoidance of trauma — a strong catch phrase. Once he confronts that trauma, remove it 
        and replace it with a phrase that reflects his new directness.
        
        - When populating aliases, prefer values from the **Known aliases** list provided in the episode
        context. When populating affiliations, prefer values from the **Known affiliations** list.
        Add unlisted aliases or affiliations only if clearly and directly supported by the content.
        - Keep descriptions concise but informative.
        - If the character has changed names or identities, use the same role_id but add new aliases. 
        Do NOT create a new role_id. Check if the previously used name is listed as an alias in the 
        episode context; if not, add it to the profile's aliases list. Include nicknames, 
        code names, and alternative identifiers only if clearly supported by the content.
        - Goals — TARGET TOTAL: **3 to 5 goals** in the profile after applying this delta. 
        Before adding, count how many goals currently exist in the baseline profile above.
        If there are already 5 or more goals, you MUST remove or consolidate before adding new ones.
        Combine closely related goals into a single broader goal rather than keeping overlapping entries.
        Actively remove completed objectives, abandoned pursuits, and goals superseded by new developments.
        Add new goals only when they are clearly and explicitly established in this episode's content.
        Aim for a balanced delta: most episodes should produce both removals/consolidations and additions 
        so the list stays focused at 3–5 meaningful, distinct goals.
        - Do NOT hallucinate events, traits, aliases, or affiliations not directly supported by the content.
        """

        aliases_text = ", ".join(known_aliases) if known_aliases else "(none listed)"
        affiliations_text = ", ".join(known_affiliations) if known_affiliations else "(none listed)"

        human_prompt = f"""\
## Episode: {ts} - {state.get('episode_name', '')}

### Known aliases appearing in this episode
{aliases_text}

### Known affiliations appearing in this episode
{affiliations_text}

### Cumulative story summary up to the previous episode
{prev_summary_text}

### Episode synopsis
{synopsis_text}

### Scenes featuring '{role_id}' in this episode
{scenes_text}
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ]
        print("=== System Prompt ==="
              f"\n{system_prompt}\n"
              "=== Human Prompt ==="
              f"\n{human_prompt}\n"
        )
        logger.info(
            f"[parse_role] Invoking LLM for '{role_id}' at {ts}, "
            f"is_first_appearance={is_first}"
        )
        parsed = self.engine.invoke(messages, base_model=base_model)

        # Store serialisable dict
        return {"parsed_delta": parsed.model_dump()}

    # -------------------------------------------------------------------------
    # Node: save_delta
    # -------------------------------------------------------------------------

    def _node_save_delta(self, state: RoleParserState) -> dict:
        """Step 5 - convert to RoleDelta if needed and persist as JSON."""
        ts = SETimestamp(**state["timestamp"])
        role_id = state["role_id"]
        parsed_dict = state["parsed_delta"]

        is_first = state["is_first_appearance"]

        # Resolve the output directory
        ep_dir = self._find_episode_dir()
        if ep_dir is None:
            raise RuntimeError(
                f"Cannot save delta: episode directory for {ts} not found "
                f"under '{self.data_dir}'."
            )

        roles_dir = ep_dir / "roles"
        roles_dir.mkdir(parents=True, exist_ok=True)
        output_path = roles_dir / f"{role_id}.json"

        if is_first:
            # LLM returned a RoleProfile → save directly as the role initialiser
            profile = RoleProfile.model_validate(parsed_dict)
            # Always stamp the correct timestamp + role_id (guard against LLM drift)
            profile.timestamp = ts
            profile.role_id = role_id
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(profile.model_dump_json(indent=2))
            logger.info(
                f"[save_delta] Saved RoleProfile (init) for '{role_id}' at {ts} to {output_path}"
            )
        else:
            # LLM returned a RoleDelta directly
            delta = RoleDelta.model_validate(parsed_dict)
            # Always stamp the correct timestamp + role_id (guard against LLM drift)
            delta.timestamp = ts
            delta.role_id = role_id
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(delta.model_dump_json(indent=2))
            logger.info(
                f"[save_delta] Saved RoleDelta for '{role_id}' at {ts} to {output_path}"
            )
        return {}

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def parse(
        self,
        episode_name: str,
        synopsis: Optional[str] = None,
        scenes: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full LangGraph pipeline.

        Parameters
        ----------
        episode_name : str
            Human-readable episode name, e.g. ``"Pilot"``.
        synopsis : str, optional
            Episode synopsis text.
        scenes : list, optional
            List of scene dicts (raw JSON dicts from scenes/ folder).

        Returns
        -------
        dict
            Final LangGraph state.  Check ``state["is_role_in_episode"]`` to
            determine whether anything was actually parsed.
        """
        initial_state: RoleParserState = {
            "timestamp": {
                "season": self.timestamp.season,
                "episode": self.timestamp.episode,
            },
            "role_id": self.role_id,
            "episode_name": episode_name,
            "synopsis": synopsis or "",
            "scenes": scenes or [],
            "is_role_in_episode": False,
            "is_first_appearance": False,
            "previous_profile_json": "",
            "prev_summary": "",
            "parsed_delta": {},
        }
        return self.graph.invoke(initial_state)

    @classmethod
    def load_episode_data(
        cls,
        season: int,
        episode: int,
        data_dir: str = "data",
    ) -> Dict[str, Any]:
        """
        Convenience helper: read synopsis, transcript and scenes from disk for
        a given episode, returning a dict ready to unpack into ``parse()``.

        Returns
        -------
        dict with keys: episode_name, synopsis, transcript, scenes
        """
        data_path = Path(data_dir)
        ep_pattern = re.compile(rf"^S{season}E{episode:02d}_(.+)$")

        season_dir = data_path / f"Season_{season}"
        if not season_dir.exists():
            raise FileNotFoundError(f"Season directory not found: {season_dir}")

        ep_dir: Optional[Path] = None
        ep_name: str = ""
        for entry in season_dir.iterdir():
            m = ep_pattern.match(entry.name)
            if m and entry.is_dir():
                ep_dir = entry
                ep_name = m.group(1).replace("_", " ")
                break

        if ep_dir is None:
            raise FileNotFoundError(
                f"Episode directory S{season}E{episode:02d} not found in {season_dir}"
            )

        # Synopsis
        synopsis = ""
        synopsis_path = ep_dir / "synopsis.txt"
        if synopsis_path.exists():
            synopsis = synopsis_path.read_text(encoding="utf-8").strip()

        # Scenes (from scenes/ subdirectory)
        scenes: List[Dict[str, Any]] = []
        scenes_dir = ep_dir / "scenes"
        if scenes_dir.exists():
            for scene_file in sorted(scenes_dir.glob("*.json")):
                with open(scene_file, "r", encoding="utf-8") as f:
                    scenes.append(json.load(f))

        return {
            "episode_name": ep_name,
            "synopsis": synopsis,
            "scenes": scenes,
        }


# ===============================================================================
# CLI entry point
# ===============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="\033[94m%(asctime)s\033[0m - \033[92m%(name)s\033[0m - %(message)s",
    )

    # Usage: python -m processors.role_profile_parser <season> <episode> <role_id> [model]
    if len(sys.argv) < 4:
        print(
            "Usage: python -m processors.role_profile_parser "
            "<season> <episode> <role_id> [model]"
        )
        sys.exit(1)

    season_num = int(sys.argv[1])
    episode_num = int(sys.argv[2])
    role_id_arg = sys.argv[3]
    model_arg = sys.argv[4] if len(sys.argv) >= 5 else "gpt-4.1-mini"

    parser = RoleParser(
        model=model_arg,
        role_id=role_id_arg,
        season=season_num,
        episode=episode_num,
    )

    ep_data = RoleParser.load_episode_data(season_num, episode_num)
    result = parser.parse(**ep_data)

    if result.get("is_role_in_episode"):
        print(
            f"Parsed and saved delta for '{role_id_arg}' at "
            f"S{season_num}E{episode_num:02d}."
        )
    else:
        print(
            f"Role '{role_id_arg}' not found in S{season_num}E{episode_num:02d}. "
            "Nothing was saved."
        )
