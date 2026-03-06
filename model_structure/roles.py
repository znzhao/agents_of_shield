
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from model_structure.stories import SETimestamp, RoleID

class AliasDelta(BaseModel):
    # Previous alias will need to be revealed to the model
    action: Literal['+', '-']
    alias: str

class AffiliationDelta(BaseModel):
    # Previous affiliation will need to be revealed to the model
    action: Literal['+', '-']
    affiliation: str = Field(description="Name of the affiliation or group, e.g. 'S.H.I.E.L.D.', 'Hydra', 'Inhumans'")

class SuperpowerDelta(BaseModel):
    # Previous superpower will need to be revealed to the model
    action: Literal['+', '-']
    superpower: str = Field(description="Name of the superpower, e.g. 'super_strength', 'telepathy', 'invisibility'")

class Goal(BaseModel):
    goal_id: str = Field(description="Unique identifier for the goal, e.g. 'protect_world', 'gain_power', 'find_family'")
    goal: Optional[str] = Field(default=None, description="Description of the character's goal or motivation, e.g. 'protect the world', 'gain power', 'find family'")

class GoalDelta(BaseModel):
    # Previous goal_id will need to be revealed to the model
    action: Literal['+', '-'] = Field(description="Action to perform on the goal, '+' to add or update, '-' to remove. When action is '-', only goal_id is required.")
    goal: Goal

class AuraDelta(BaseModel):
    action: Literal['+', '-']
    trait: Literal['intimidation_warmth', 'recklessness_carefulness', 'humor', 'attractiveness', 'mystery']
    
class Aura(BaseModel):
    """
    Represents the character's overall aura or vibe, which can influence how they are perceived by others.
    """
    intimidation_warmth: int = Field(0, ge=-10, le=10, description="Level of warmth or friendliness, -10 is intimidating, 10 is warm")
    recklessness_carefulness: int = Field(0, ge=-10, le=10, description="Level of carefulness or recklessness, -10 is reckless, 10 is careful")
    humor: int = Field(0, ge=-10, le=10, description="Level of humor or wit")
    attractiveness: int = Field(0, ge=-10, le=10, description="Level of physical attractiveness or appeal")
    mystery: int = Field(0, ge=-10, le=10, description="Level of mystery or intrigue")

class DemographicsDelta(BaseModel):
    state: Optional[Literal['healthy', 'injured', 'sick', 'exhausted', 'poisoned', 'cursed', 'empowered', 'weakened', 'normal']] = None
    appearance: Optional[Literal['normal', 'disheveled', 'wounded', 'scarred', 'glowing', 'shadowy', 'other']] = None
    age: Optional[Literal['child', 'teen', 'young_adult', 'adult', 'middle_aged', 'senior', 'elderly']] = None
    sex: Optional[Literal['m', 'f', 'o']] = None
    sexual_orientation: Optional[Literal['heterosexual', 'homosexual', 'bisexual', 'asexual', 'other']] = None
    nationality: Optional[str] = None
    religion: Optional[Literal['atheism', 'agnosticism', 'christianity', 'islam', 'hinduism', 'buddhism', 'judaism', 'other']] = None
    occupation: Optional[str] = None
    
class Demographics(BaseModel):
    state: Optional[Literal['healthy', 'injured', 'sick', 'exhausted', 'poisoned', 'cursed', 'empowered', 'weakened', 'normal']] = None
    appearance: Optional[Literal['normal', 'disheveled', 'wounded', 'scarred', 'glowing', 'shadowy', 'other']] = None
    age: Optional[Literal['child', 'teen', 'young_adult', 'adult', 'middle_aged', 'senior', 'elderly']] = None
    sex: Optional[Literal['m', 'f', 'o']] = None
    sexual_orientation: Optional[Literal['heterosexual', 'homosexual', 'bisexual', 'asexual', 'other']] = None
    nationality: Optional[str] = None
    religion: Optional[Literal['atheism', 'agnosticism', 'christianity', 'islam', 'hinduism', 'buddhism', 'judaism', 'other']] = None
    occupation: Optional[str] = None
    affiliation: List[str] = Field(default_factory=list, description="List of affiliations or groups the character is associated with.")
    superpowers: List[str] = Field(default_factory=list, description="List of superpowers or special abilities the character possesses.")
    
class PersonalityDelta(BaseModel):
    action: Literal['+', '-']
    trait: Literal['extraversion', 'sensing', 'thinking', 'judging']

class Personality(BaseModel):
    """
    Represents a character's personality traits with values between -10 and 10.
    Based on MBTI dimensions: 
        - Extraversion (E) vs Introversion (I), 
        - Sensing (S) vs Intuition (N), 
        - Thinking (T) vs Feeling (F), 
        - Judging (J) vs Perceiving (P),
    """
    extraversion: int = Field(default=0, ge=-10, le=10, description="Extraversion vs Introversion, -10 is fully introverted, 10 is fully extraverted")
    sensing: int = Field(default=0, ge=-10, le=10, description="Sensing vs Intuition, -10 is fully intuitive, 10 is fully sensing")
    thinking: int = Field(default=0, ge=-10, le=10, description="Thinking vs Feeling, -10 is fully feeling, 10 is fully thinking")
    judging: int = Field(default=0, ge=-10, le=10, description="Judging vs Perceiving, -10 is fully perceiving, 10 is fully judging")
    
    def __str__(self):
        classification = []
        classification.append('E' if self.extraversion > 0 else 'I')
        classification.append('S' if self.sensing > 0 else 'N')
        classification.append('T' if self.thinking > 0 else 'F')
        classification.append('J' if self.judging > 0 else 'P')
        return f"Personality: {''.join(classification)} E/I: {self.extraversion}, S/N: {self.sensing}, T/F: {self.thinking}, J/P: {self.judging}"

class SkillDelta(BaseModel):
    action: Literal['+', '-']
    skill: Literal['physical_fitness', 'combat', 'espionage', 'stealth', 'hacking', 'negotiation', 'leadership', 'field_medicine', 'intelligence', 'research', 'decision_making', 'mechanical_repair']
    level: int = Field(default=1, ge=1, le=5)

class Skills(BaseModel):
    physical_fitness: int = Field(default=3, ge=0, le=10)
    combat: int = Field(default=3, ge=0, le=10)
    espionage: int = Field(default=3, ge=0, le=10)
    stealth: int = Field(default=3, ge=0, le=10)
    hacking: int = Field(default=3, ge=0, le=10)
    negotiation: int = Field(default=3, ge=0, le=10)
    leadership: int = Field(default=3, ge=0, le=10)
    field_medicine: int = Field(default=3, ge=0, le=10)
    intelligence: int = Field(default=3, ge=0, le=10)
    research: int = Field(default=3, ge=0, le=10)
    decision_making: int = Field(default=3, ge=0, le=10)
    mechanical_repair: int = Field(default=3, ge=0, le=10)

class CoreEmoDelta(BaseModel):
    action: Literal['+', '-']
    emotion: Literal['happiness', 'sadness', 'anger', 'fear', 'disgust', 'shocked']
    level: int = Field(default=1, ge=1, le=5) # core emotions change faster than mood

class CoreEmotion(BaseModel):
    """
    Primary emotions experienced by the character, each ranging from 0 to 10.
    """
    happiness: int = Field(0, ge=0, le=10, description="Level of happiness or joy")
    sadness: int = Field(0, ge=0, le=10, description="Level of sadness or sorrow")
    anger: int = Field(0, ge=0, le=10, description="Level of anger or rage")
    fear: int = Field(0, ge=0, le=10, description="Level of fear or anxiety")
    disgust: int = Field(0, ge=0, le=10, description="Level of disgust or aversion")
    shocked: int = Field(0, ge=0, le=10, description="Level of shock or surprise")

class MoodDelta(BaseModel):
    action: Literal['+', '-']
    mood: Literal['calmness_anxiety', 'loneliness_connection', 'despair_hope', 'helplessness_confidence']
    level: int = Field(default=1, ge=1, le=3) # mood changes slower than core emotions, but still relatively slow

class Mood(BaseModel):
    """
    Ongoing mood states that influence the character's emotional baseline.
    """
    calmness_anxiety: int = Field(0, ge=-10, le=10, description="Level of calmness vs anxiety, 0 is calm, 10 is anxious")
    loneliness_connection: int = Field(0, ge=-10, le=10, description="Level of loneliness vs connection, 0 is lonely, 10 is connected")
    despair_hope: int = Field(0, ge=-10, le=10, description="Level of despair vs hope, 0 is despairing, 10 is hopeful")
    helplessness_confidence: int = Field(0, ge=-10, le=10, description="Level of helplessness vs confidence, 0 is helpless, 10 is confident")

class SelfStateDelta(BaseModel):
    action: Literal['+', '-']
    self_state: Literal['self_worth', 'social_trust', 'guilt', 'shame', 'hostility', 'resentment']

class SelfState(BaseModel):
    """
    Self-directed emotional states reflecting the character's self-perception.
    """
    self_worth: int = Field(0, ge=-10, le=10, description="Overall sense of personal value and competence")
    social_trust: int = Field(0, ge=-10, le=10, description="Expectation of safety and goodwill from others")
    guilt: int = Field(0, ge=-10, le=10, description="Remorse over specific actions violating personal or social norms")
    shame: int = Field(0, ge=-10, le=10, description="Global negative self-evaluation and fear of social devaluation")
    hostility: int = Field(0, ge=-10, le=10, description="Immediate aggressive or confrontational impulse")
    resentment: int = Field(0, ge=-10, le=10, description="Accumulated bitterness from unresolved perceived injustice")

class EmotionIntensity(BaseModel):
    arousal: int = Field(5, ge=1, le=10, description="Level of physiological arousal or activation")

class Emotions(BaseModel):
    core: CoreEmotion
    mood: Mood
    self_state: SelfState
    intensity: EmotionIntensity

class CoreValueDelta(BaseModel):
    action: Literal['+', '-']
    value: Literal['honesty', 'compassion', 'violence', 'justice', 'loyalty', 'courage', 'freedom', 'order', 'self_interest', 'pragmatism', 'kindness']
    level: int = Field(default=1, ge=1, le=5)

class CoreValues(BaseModel):
    honesty: int = Field(0, ge=-10, le=10, description="Level of honesty or integrity")
    compassion: int = Field(0, ge=-10, le=10, description="Level of compassion or empathy")
    violence: int = Field(0, ge=-10, le=10, description="Level of acceptance or endorsement of violence")
    justice: int = Field(0, ge=-10, le=10, description="Level of commitment to justice or fairness")
    loyalty: int = Field(0, ge=-10, le=10, description="Level of loyalty or allegiance")
    courage: int = Field(0, ge=-10, le=10, description="Level of courage or bravery")
    freedom: int = Field(0, ge=-10, le=10, description="Level of value placed on freedom or autonomy")
    order: int = Field(0, ge=-10, le=10, description="Level of value placed on order or structure")
    self_interest: int = Field(0, ge=-10, le=10, description="Level of self-interest or personal gain")
    pragmatism: int = Field(0, ge=-10, le=10, description="Level of pragmatism or practical thinking")
    kindness: int = Field(0, ge=-10, le=10, description="Level of kindness or benevolence")

class CatchPhraseDelta(BaseModel):
    action: Literal['+', '-']
    id: str = Field(description="Unique identifier for the catch phrase, e.g. 'catchphrase_1'")
    context: Optional[str] = Field(default=None, description="Context or situation in which the catch phrase is used, e.g. 'battle cry', 'greeting', 'signature line'")
    catch_phrase: str = Field(description="A memorable phrase or saying associated with the character, e.g. 'I am Groot', 'Avengers Assemble!'")

class CatchPhrase(BaseModel):
    id: str = Field(description="Unique identifier for the catch phrase, e.g. 'catchphrase_1'")
    context: Optional[str] = Field(default=None, description="Context or situation in which the catch phrase is used, e.g. 'battle cry', 'greeting', 'signature line'")
    catch_phrase: str = Field(description="A memorable phrase or saying associated with the character, e.g. 'I am Groot', 'Avengers Assemble!'")

class RoleDelta(BaseModel):
    # The traits that needs to be shown to the model for each episode.
    timestamp: SETimestamp
    role_id: RoleID
    first_name: str
    last_name: Optional[str] = None
    description: str = ""
    aliases: Optional[List[AliasDelta]] = []
    affiliations: Optional[List[AffiliationDelta]] = []
    superpowers: Optional[List[SuperpowerDelta]] = []

    # The traits that are hidden from the model and only used for generating the profile when snapshotting.
    demographics: Optional[DemographicsDelta] = None
    personality: Optional[List[PersonalityDelta]] = []
    skills: Optional[List[SkillDelta]] = []
    core_emotions: Optional[List[CoreEmoDelta]] = []
    moods: Optional[List[MoodDelta]] = []
    self_states: Optional[List[SelfStateDelta]] = []
    intensities: Optional[EmotionIntensity] = None
    core_values: Optional[List[CoreValueDelta]] = []
    goals: Optional[List[GoalDelta]] = []
    aura: Optional[List[AuraDelta]] = []
    catch_phrases_delta: Optional[List[CatchPhraseDelta]] = []
    
class RoleProfile(BaseModel):
    timestamp: SETimestamp
    role_id: RoleID
    first_name: str
    last_name: Optional[str] = None
    aliases: list[str] = []
    demographics: Demographics = Demographics()
    personality: Personality = Personality()
    skills: Skills = Skills()
    emotions: Emotions = Emotions(core=CoreEmotion(), mood=Mood(), self_state=SelfState(), intensity=EmotionIntensity())
    core_values: CoreValues = CoreValues()
    goals: List[Goal] = []
    aura: Aura = Aura()
    description: str = ""
    catch_phrases: List[CatchPhrase] = []

    def __str__(self):
        '''
        String representation of the role profile, including only name.
        '''
        aliases_str = ", ".join(self.aliases) if self.aliases else "None"
        return f"Role ID: {self.role_id} at {self.timestamp}, Name: {self.first_name} {self.last_name}"

class Role(BaseModel):
    role_id: RoleID
    role_init_profile: Optional[RoleProfile] = None
    role_deltas: list[RoleDelta] = []

    def sort(self, deltas: List[RoleDelta]) -> List[RoleDelta]:
        """Sorts the list of RoleDelta objects based on their timestamps."""
        return sorted(deltas, key=lambda delta: delta.timestamp)

    def apply_demographics_delta(self, demographics_delta: DemographicsDelta, profile: RoleProfile):
        for field in demographics_delta.model_fields_set:
            setattr(profile.demographics, field, getattr(demographics_delta, field))
        return profile
    
    def apply_affiliation_delta(self, affiliation_delta: AffiliationDelta, profile: RoleProfile):
        if affiliation_delta.action == '+':
            if affiliation_delta.affiliation not in profile.demographics.affiliation:
                profile.demographics.affiliation.append(affiliation_delta.affiliation)
        elif affiliation_delta.action == '-':
            if affiliation_delta.affiliation in profile.demographics.affiliation:
                profile.demographics.affiliation.remove(affiliation_delta.affiliation)
        return profile
    
    def apply_superpower_delta(self, superpower_delta: SuperpowerDelta, profile: RoleProfile):
        if superpower_delta.action == '+':
            if superpower_delta.superpower not in profile.demographics.superpowers:
                profile.demographics.superpowers.append(superpower_delta.superpower)
        elif superpower_delta.action == '-':
            if superpower_delta.superpower in profile.demographics.superpowers:
                profile.demographics.superpowers.remove(superpower_delta.superpower)
        return profile

    def apply_personality_delta(self, personality_delta: PersonalityDelta, profile: RoleProfile):
        current_level = getattr(profile.personality, personality_delta.trait)
        if personality_delta.action == '+':
            new_level = min(current_level + 1, 10)
        elif personality_delta.action == '-':
            new_level = max(current_level - 1, -10)
        setattr(profile.personality, personality_delta.trait, new_level)
        return profile

    def apply_alias_delta(self, alias_delta: AliasDelta, profile: RoleProfile):
        if alias_delta.action == '+':
            if alias_delta.alias not in profile.aliases:
                profile.aliases.append(alias_delta.alias)
        elif alias_delta.action == '-':
            if alias_delta.alias in profile.aliases:
                profile.aliases.remove(alias_delta.alias)
        return profile

    def apply_skill_delta(self, skill_delta: SkillDelta, profile: RoleProfile):
        current_level = getattr(profile.skills, skill_delta.skill)
        if skill_delta.action == '+':
            new_level = min(current_level + 1, 10)
        elif skill_delta.action == '-':
            new_level = max(current_level - 1, 1)
        setattr(profile.skills, skill_delta.skill, new_level)
        return profile

    def apply_core_emo_delta(self, core_emo_delta: CoreEmoDelta, profile: RoleProfile):
        current_level = getattr(profile.emotions.core, core_emo_delta.emotion)
        if core_emo_delta.action == '+':
            new_level = min(current_level + 1, 10)
        elif core_emo_delta.action == '-':
            new_level = max(current_level - 1, 0)
        setattr(profile.emotions.core, core_emo_delta.emotion, new_level)
        return profile
    
    def apply_mood_delta(self, mood_delta: MoodDelta, profile: RoleProfile):
        current_level = getattr(profile.emotions.mood, mood_delta.mood)
        if mood_delta.action == '+':
            new_level = min(current_level + 1, 10)
        elif mood_delta.action == '-':
            new_level = max(current_level - 1, -10)
        setattr(profile.emotions.mood, mood_delta.mood, new_level)
        return profile
    
    def apply_self_state_delta(self, self_state_delta: SelfStateDelta, profile: RoleProfile):
        current_level = getattr(profile.emotions.self_state, self_state_delta.self_state)
        if self_state_delta.action == '+':
            new_level = min(current_level + 1, 10)
        elif self_state_delta.action == '-':
            new_level = max(current_level - 1, -10)
        setattr(profile.emotions.self_state, self_state_delta.self_state, new_level)
        return profile
    
    def apply_emotion_intensity_delta(self, intensity_delta: EmotionIntensity, profile: RoleProfile):
        current_level = profile.emotions.intensity.arousal
        new_level = max(0, min(current_level + intensity_delta.arousal, 10))
        profile.emotions.intensity.arousal = new_level
        return profile

    def apply_core_value_delta(self, core_value_delta: CoreValueDelta, profile: RoleProfile):
        current_level = getattr(profile.core_values, core_value_delta.value)
        if core_value_delta.action == '+':
            new_level = min(current_level + 1, 10)
        elif core_value_delta.action == '-':
            new_level = max(current_level - 1, -10)
        setattr(profile.core_values, core_value_delta.value, new_level)
        return profile

    def apply_goal_delta(self, goal_delta: GoalDelta, profile: RoleProfile):
        if goal_delta.action == '+':
            existing_goal = next((goal for goal in profile.goals if goal.goal_id == goal_delta.goal.goal_id), None)
            if existing_goal:
                existing_goal.goal = goal_delta.goal.goal
            else:
                profile.goals.append(goal_delta.goal)
        elif goal_delta.action == '-':
            profile.goals = [goal for goal in profile.goals if goal.goal_id != goal_delta.goal.goal_id]
        return profile
    
    def apply_aura_delta(self, aura_delta: AuraDelta, profile: RoleProfile):
        current_level = getattr(profile.aura, aura_delta.trait)
        
        if aura_delta.action == '+':
            new_level = min(current_level + 1, 10)
        elif aura_delta.action == '-':
            new_level = max(current_level - 1, -10)
        setattr(profile.aura, aura_delta.trait, new_level)
        return profile

    def apply_catch_phrase_delta(self, catch_phrase_delta: CatchPhraseDelta, profile: RoleProfile):
        if catch_phrase_delta.action == '+':
            existing_catch = next((cp for cp in profile.catch_phrases if cp.id == catch_phrase_delta.id), None)
            if existing_catch:
                existing_catch.catch_phrase = catch_phrase_delta.catch_phrase
                existing_catch.context = catch_phrase_delta.context
            else:
                profile.catch_phrases.append(CatchPhrase(id=catch_phrase_delta.id, context=catch_phrase_delta.context, catch_phrase=catch_phrase_delta.catch_phrase))
        elif catch_phrase_delta.action == '-':
            profile.catch_phrases = [cp for cp in profile.catch_phrases if cp.id != catch_phrase_delta.id]
        return profile

    def snapshot(self, timestamp: SETimestamp) -> RoleProfile:
        '''
        Generate a snapshot of the role's profile at a given timestamp by applying all relevant deltas up to that timestamp.
        '''
        self.role_deltas = self.sort(self.role_deltas)

        # Start with initial profile if available, otherwise create a new one
        if self.role_init_profile:
            profile = self.role_init_profile.model_copy(deep=True)
            profile.timestamp = timestamp
        else:
            profile = RoleProfile(
                timestamp=timestamp,
                role_id=self.role_id,
                first_name=self.role_deltas[0].first_name if self.role_deltas else "Unknown",
                description=self.role_deltas[0].description if self.role_deltas else "No description"
            )
        
        for delta in self.role_deltas:
            if delta.timestamp > timestamp:
                break
            
            profile.first_name = delta.first_name
            profile.last_name = delta.last_name
            profile.description = delta.description
            if delta.demographics:
                self.apply_demographics_delta(delta.demographics, profile)
            # affiliations and superpowers are handled separately since they are lists that can have multiple entries added or removed over time
            for affiliation_delta in delta.affiliations:
                self.apply_affiliation_delta(affiliation_delta, profile)
            for superpower_delta in delta.superpowers:
                self.apply_superpower_delta(superpower_delta, profile)
            for alias_delta in delta.aliases:
                self.apply_alias_delta(alias_delta, profile)
            for skill_delta in delta.skills:
                self.apply_skill_delta(skill_delta, profile)
            for personality_delta in delta.personality:
                self.apply_personality_delta(personality_delta, profile)
            for core_emo_delta in delta.core_emotions:
                self.apply_core_emo_delta(core_emo_delta, profile)
            for mood_delta in delta.moods:
                self.apply_mood_delta(mood_delta, profile)
            for self_state_delta in delta.self_states:
                self.apply_self_state_delta(self_state_delta, profile)
            for catch_phrase_delta in delta.catch_phrases_delta:
                self.apply_catch_phrase_delta(catch_phrase_delta, profile)
            if delta.intensities:
                self.apply_emotion_intensity_delta(delta.intensities, profile)
            for aura_delta in delta.aura:
                self.apply_aura_delta(aura_delta, profile)
            for core_value_delta in delta.core_values:
                self.apply_core_value_delta(core_value_delta, profile)
            for goal_delta in delta.goals:
                self.apply_goal_delta(goal_delta, profile)
        return profile

if __name__ == "__main__":
    from model_structure.stories import SETimestamp
    
    # Create a role profile directly
    coulson_profile = RoleProfile(
        timestamp=SETimestamp(season=1, episode=1),
        role_id="coulson",
        first_name="Phil",
        last_name="Coulson",
        description="Strategic Operations Commander at S.H.I.E.L.D.",
        aliases=["Agent Coulson"],
        demographics=Demographics(
            state='healthy',
            age='adult',
            sex='m',
            nationality='American',
            occupation='S.H.I.E.L.D. Agent',
            affiliation=['S.H.I.E.L.D.']
        ),
        personality=Personality(extraversion=5, thinking=7),
        skills=Skills(leadership=7, negotiation=7, intelligence=7),
        core_values=CoreValues(loyalty=9, justice=8),
        goals=[Goal(goal_id='protect_world', goal='Protect the world from threats')],
        aura=Aura(intimidation_warmth=6)
    )
    
    # Create a Role with the profile
    coulson = Role(
        role_id="coulson",
        role_init_profile=coulson_profile,
        role_deltas=[]
    )
    
    print("Coulson's Profile:")
    print(f"  Name: {coulson.role_init_profile.first_name} {coulson.role_init_profile.last_name}")
    print(f"  Goals: {[goal.goal for goal in coulson.role_init_profile.goals]}")
    print(f"  Personality: {coulson.role_init_profile.personality}")
