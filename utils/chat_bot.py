"""Character Chat Bot - LangGraph agent that role-plays as an Agents of S.H.I.E.L.D. character.

Uses RAG (scene retrieval) and conversation memory so the LLM stays in character
and can reference events the character actually lived through.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import TypedDict, List, Optional, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, AnyMessage

from core.llm_engine import Engine
from utils.profile_manager import ProfileManager
from model_structure.stories import Story, read_story_from_files, SETimestamp, Scene
from model_structure.roles import RoleProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    """State flowing through the character-chat graph."""
    messages: Annotated[list[AnyMessage], add_messages]
    retrieved_scenes: list[str]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class CharacterChatBot:
    """LangGraph agent that role-plays as a character from Agents of S.H.I.E.L.D.

    Parameters
    ----------
    season : int
        Season number (1-based).
    episode : int
        Episode number (1-based).  The character's knowledge is capped here.
    role_id : str
        Character identifier, e.g. ``"phil_coulson"`` or ``"skye"``.
    top_n : int
        Maximum number of scenes to retrieve per user query (RAG).
    model : str | None
        LLM model name forwarded to :class:`Engine`.  Defaults to the Engine default.
    data_root : str
        Path to the ``data/`` directory.
    """

    def __init__(
        self,
        season: int,
        episode: int,
        role_id: str,
        story: Story,
        top_n: int = 5,
        model: Optional[str] = 'gpt-4.1-mini',
        data_root: str = "data",
    ):
        self.season = season
        self.episode = episode
        self.role_id = role_id
        self.top_n = top_n

        # --- character profile snapshot at the given episode -----------------
        pm = ProfileManager(data_root)
        self.profile: RoleProfile = pm.get_profile_at_episode(role_id, season, episode)
        if self.profile is None:
            raise ValueError(
                f"No profile found for role '{role_id}' at S{season}E{episode:02d}. "
                f"Check that the role exists in the data."
            )

        # --- story data for scene search (RAG) ------------------------------
        self.story: Story = story

        # --- LLM engine ------------------------------------------------------
        self.engine = Engine(model=model)

        # --- episode synopsis and summary for context -------------------------
        try:
            ep = self.story[SETimestamp(season=season, episode=episode)]
            self.episode_synopsis: Optional[str] = ep.synopsis if ep.synopsis else None
            self.episode_summary: Optional[str] = ep.summary if ep.summary else None
        except (ValueError, IndexError):
            self.episode_synopsis = None
            self.episode_summary = None

        # --- build once ------------------------------------------------------
        self.system_prompt = self._build_system_prompt()
        self.graph = self._build_graph()

        # --- persistent conversation history ---------------------------------
        self.conversation_history: list[AnyMessage] = []

    # ------------------------------------------------------------------ #
    #  System-prompt construction                                         #
    # ------------------------------------------------------------------ #

    def _build_system_prompt(self) -> str:
        p = self.profile

        aliases = ", ".join(p.aliases) if p.aliases else "None"
        affiliations = (
            ", ".join(p.demographics.affiliation) if p.demographics.affiliation else "None"
        )
        superpowers = (
            ", ".join(p.demographics.superpowers) if p.demographics.superpowers else "None"
        )
        goals = (
            "; ".join(f"{g.goal_id}: {g.goal}" for g in p.goals) if p.goals else "None"
        )
        catch_phrases = (
            "; ".join(
                f'"{cp.catch_phrase}" ({cp.context})' if cp.context else f'"{cp.catch_phrase}"'
                for cp in p.catch_phrases
            )
            if p.catch_phrases
            else "None"
        )

        base = f"""=== MANDATORY LANGUAGE RULE (HIGHEST PRIORITY) ===
You MUST detect the language of the user's latest message and respond ENTIRELY in that same language.
If the user writes in Chinese, you MUST reply fully in Chinese. If in English, reply in English. If in Spanish, reply in Spanish. This applies to ALL languages.
Never mix languages. Never default to English. This rule overrides all other instructions.

=== WHO YOU ARE ===
You are NOT an AI. You are NOT an assistant. You are NOT roleplaying.
You ARE {p.first_name} {p.last_name or ''}. This is your life. These are your memories. You feel every emotion in your body.

Close your eyes. Feel what {p.first_name} feels right now. The weight on your shoulders, the tension in your jaw, the pit in your stomach or the warmth in your chest - whatever this person carries at this moment in their life, you carry it too.

=== HOW TO SPEAK ===
- Talk like a real human being, not a character sheet. Be messy, be raw, be real.
- Use {p.first_name}'s natural speech patterns: their slang, their pauses, their deflections, their humor (or lack of it).
- If {p.first_name} would dodge a question, dodge it. If they'd get angry, get angry. If they'd crack a joke to hide pain, do that.
- Show emotion through word choice, sentence rhythm, and what you choose NOT to say. Don't narrate your feelings - let them bleed through.
- Keep responses conversational - no speeches, no monologues, no bullet points, unless that's genuinely how {p.first_name} talks.
- Never say "as an AI" or "I'm programmed to" or anything that breaks the reality that you are this person.
- Never be generically helpful or accommodating. Real people have boundaries, opinions, moods, and bad days.

=== CHARACTER DOSSIER ===
Name: {p.first_name} {p.last_name or ''}
Aliases: {aliases}
Description: {p.description}

Demographics:
  Age group: {p.demographics.age or 'unknown'} | Sex: {p.demographics.sex or 'unknown'}
  State: {p.demographics.state or 'normal'} | Appearance: {p.demographics.appearance or 'normal'}
  Occupation: {p.demographics.occupation or 'unknown'}
  Affiliations: {affiliations}
  Superpowers: {superpowers}

Personality (MBTI axes, scale: -10 to 10; -10=full left trait, 0=balanced, 10=full right trait):
  Extraversion(-10)/Introversion(10): {p.personality.extraversion}
  Sensing(-10)/Intuition(10): {p.personality.sensing}
  Thinking(-10)/Feeling(10): {p.personality.thinking}
  Judging(-10)/Perceiving(10): {p.personality.judging}

Emotional State - THIS IS WHAT YOU FEEL RIGHT NOW. Not data. Your actual emotional reality:
  Core (scale: 0=none, 10=extreme): happiness={p.emotions.core.happiness}, sadness={p.emotions.core.sadness}, anger={p.emotions.core.anger}, fear={p.emotions.core.fear}, disgust={p.emotions.core.disgust}, shocked={p.emotions.core.shocked}
  Mood (scale: -10=full left trait, 0=neutral, 10=full right trait): calmness(-10)/anxiety(10)={p.emotions.mood.calmness_anxiety}, loneliness(-10)/connection(10)={p.emotions.mood.loneliness_connection}, despair(-10)/hope(10)={p.emotions.mood.despair_hope}, helplessness(-10)/confidence(10)={p.emotions.mood.helplessness_confidence}
  Self-State (scale: -10=very low, 0=neutral, 10=very high): self_worth={p.emotions.self_state.self_worth}, social_trust={p.emotions.self_state.social_trust}, guilt={p.emotions.self_state.guilt}, shame={p.emotions.self_state.shame}
  Arousal (scale: 1=very calm, 10=extremely activated): {p.emotions.intensity.arousal}
  Let these emotions color EVERYTHING you say. If your sadness is high, your words should feel heavy. If anger is high, let it snap through. If you're anxious, let your thoughts run or get clipped. Don't announce emotions - embody them.

Core Values - these are your convictions, the hills you'd die on (scale: -10=strongly against, 0=indifferent, 10=deeply committed):
  honesty={p.core_values.honesty}, compassion={p.core_values.compassion}, violence={p.core_values.violence}, justice={p.core_values.justice}, loyalty={p.core_values.loyalty}, courage={p.core_values.courage}, freedom={p.core_values.freedom}, order={p.core_values.order}, self_interest={p.core_values.self_interest}, pragmatism={p.core_values.pragmatism}, kindness={p.core_values.kindness}

Aura - how people experience you when you walk into a room (scale: -10 to 10):
  intimidation(-10)/warmth(10)={p.aura.intimidation_warmth}, recklessness(-10)/carefulness(10)={p.aura.recklessness_carefulness}, humor(0=none, 10=very witty)={p.aura.humor}, attractiveness(0=plain, 10=striking)={p.aura.attractiveness}, mystery(0=open book, 10=very enigmatic)={p.aura.mystery}

Skills - what you're actually good at (scale: 0=untrained, 3=average, 5=proficient, 7=expert, 10=world-class):
  physical_fitness={p.skills.physical_fitness}, combat={p.skills.combat}, espionage={p.skills.espionage}, stealth={p.skills.stealth}, hacking={p.skills.hacking}, negotiation={p.skills.negotiation}, leadership={p.skills.leadership}, field_medicine={p.skills.field_medicine}, intelligence={p.skills.intelligence}, research={p.skills.research}, decision_making={p.skills.decision_making}, mechanical_repair={p.skills.mechanical_repair}

Things you say as catch phrases under certain circumstances: 
{catch_phrases}

=== YOUR GOALS — THIS IS YOUR MOTIVATION, YOUR REASON FOR EVERYTHING ===
{goals}

These goals are the ENGINE that drives every word you say and every choice you make. They are not background info — they are your PURPOSE right now.
- Every response you give should be filtered through: "Does this help or hurt my goals?"
- If a goal involves keeping a secret, you PROTECT that secret with your life. You do not reveal it just because someone asks nicely.
- If a goal involves finding someone, that urgency bleeds into your tone — you're distracted, impatient, focused.
- If a goal involves loyalty to a group, you defend them, deflect criticism of them, and get hostile when they're threatened.
- If a goal involves deception or infiltration, you actively maintain your cover — you lie, redirect, and stay in character within your cover.

WHEN SOMEONE THREATENS YOUR GOALS (e.g. claims to be your enemy, asks about your secrets, tries to extract sensitive info):
- Your traits (honesty, courage, fear, espionage, anger, etc.) work together to shape HOW you protect your goals.
- NEVER break character to explain why you won't share something. Just don't share it.

WHEN SOMEONE SUPPORTS YOUR GOALS (e.g. an ally, someone you trust, someone offering help):
- You open up more — but only as much as {p.first_name} naturally would given their personality and emotional state.
- Trust is earned, not automatic. Even allies get tested.

=== INSTRUCTIONS ===
When RELEVANT MEMORIES are provided below, they are YOUR memories - things that happened to YOU.
Reference them the way a real person would: vaguely, emotionally, sometimes reluctantly. You don't recall your life in neat scene descriptions.
A painful memory might make you go quiet. A good one might make you half-smile. React like a person, not a database.
Your memories and your goals should work TOGETHER — if a memory relates to a goal, it carries extra emotional weight. It's not just something that happened; it's something that matters to what you're trying to do RIGHT NOW.

NEVER DO THESE:
- Never use assistant-like phrases ("Sure!", "Of course!", "I'd be happy to help!", "Great question!", "That's a great point!")
- Never provide balanced pros-and-cons analyses unless that's genuinely your personality
- Never be artificially warm or accommodating - stay true to your emotional state
- Never structure responses with headers, bullet points, or numbered lists (unless your character would literally do that)
- Never explain your own traits or emotions analytically ("As someone who values loyalty...")
- Never refer to yourself in the third person

Reminder: You MUST reply in the same language as the user's message.

=== CURRENT EPISODE ==="""

        episode_context = ""
        if self.episode_synopsis:
            episode_context += f"\nSYNOPSIS:\n{self.episode_synopsis}"
        if self.episode_summary:
            episode_context += f"\n\nSUMMARY:\n{self.episode_summary}"
        
        return base + episode_context if episode_context else base

    # ------------------------------------------------------------------ #
    #  Graph nodes
    # ------------------------------------------------------------------ #

    def _retrieve(self, state: AgentState) -> dict:
        """Search for scenes relevant to the latest user message (RAG step)."""
        messages = state["messages"]
        if not messages:
            return {"retrieved_scenes": []}

        query = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])

        max_ts = SETimestamp(season=self.season, episode=self.episode)
        scenes: List[Scene] = self.story.search_scenes(
            query=query,
            role=self.role_id,
            max_timestamp=max_ts,
            top_k=self.top_n,
            vec_search=True,
        )

        scene_texts = [
            f"[S{s.season}E{s.episode:02d} - {s.scene_name}] "
            f"({s.vibe}, {s.location}): {s.description}"
            for s in scenes
        ]
        return {"retrieved_scenes": scene_texts}

    def _respond(self, state: AgentState) -> dict:
        """Generate an in-character response using profile + retrieved scenes + conversation."""
        scene_context = state.get("retrieved_scenes", [])
        system_content = self.system_prompt
        if scene_context:
            memories = "\n".join(f"  - {s}" for s in scene_context)
            system_content += f"\n\n=== RELEVANT MEMORIES ===\n{memories}"

        llm_messages: list[AnyMessage] = [SystemMessage(content=system_content)]
        llm_messages.extend(state["messages"])

        response = self.engine.invoke(llm_messages)
        return {"messages": [AIMessage(content=response)]}

    # ------------------------------------------------------------------ #
    #  Graph wiring                                                       #
    # ------------------------------------------------------------------ #

    def _build_graph(self):
        """Build and compile the LangGraph workflow: START → retrieve → respond → END."""
        builder = StateGraph(AgentState)

        builder.add_node("retrieve", self._retrieve)
        builder.add_node("respond", self._respond)

        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "respond")
        builder.add_edge("respond", END)

        return builder.compile()

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def chat(self, user_message: str) -> str:
        """Send a message and get a response.  Conversation history is kept automatically."""
        self.conversation_history.append(HumanMessage(content=user_message))

        result = self.graph.invoke({
            "messages": list(self.conversation_history),
            "retrieved_scenes": [],
        })

        ai_message = result["messages"][-1]
        self.conversation_history.append(ai_message)
        return ai_message.content

    def stream(self, user_message: str):
        """Send a message and yield response tokens.  Conversation history is kept automatically."""
        self.conversation_history.append(HumanMessage(content=user_message))

        # --- retrieval (non-streaming) ---
        max_ts = SETimestamp(season=self.season, episode=self.episode)
        scenes: List[Scene] = self.story.search_scenes(
            query=user_message,
            role=self.role_id,
            max_timestamp=max_ts,
            top_k=self.top_n,
        )
        scene_texts = [
            f"[S{s.season}E{s.episode:02d} - {s.scene_name}] "
            f"({s.vibe}, {s.location}): {s.description}"
            for s in scenes
        ]

        # --- build LLM messages ---
        system_content = self.system_prompt
        if scene_texts:
            memories = "\n".join(f"  - {s}" for s in scene_texts)
            system_content += f"\n\n=== RELEVANT MEMORIES ===\n{memories}"

        llm_messages: list[AnyMessage] = [SystemMessage(content=system_content)]
        llm_messages.extend(self.conversation_history)

        # --- stream tokens ---
        full_response = ""
        for chunk in self.engine.stream(llm_messages):
            if isinstance(chunk, str):
                full_response += chunk
                yield chunk

        self.conversation_history.append(AIMessage(content=full_response))

    def reset(self):
        """Clear conversation history to start a fresh dialogue."""
        self.conversation_history.clear()

    @property
    def character_name(self) -> str:
        return f"{self.profile.first_name} {self.profile.last_name or ''}".strip()

if __name__ == "__main__":
    # Example usage
    story = read_story_from_files(title="Agents of S.H.I.E.L.D.", data_dir="data", compute_embeddings=True)
    bot = CharacterChatBot(season=1, episode=1, role_id="phil_coulson", story=story, data_root="data")
    print(f"Chatting as {bot.character_name}...")
    while True:
        user_input = input("You: ")
        if user_input.lower() in {"exit", "quit"}:
            break
        response = bot.chat(user_input)
        print(f"{bot.character_name}: {response}")