"""Profile page showing detailed information about characters"""
import logging
from typing import Optional, Dict, Any
from dash import html, dcc, Output, Input, State
from dash_bootstrap_components import Container, Row, Col, Card, CardBody, CardHeader, Tab, Tabs
from model_structure.stories import SETimestamp
from model_structure.roles import RoleProfile, Demographics, Personality, Skills, CoreEmotion, Mood, SelfState, CoreValues, Aura
from utils.profile_manager import get_profile_snapshot
from pages.vibe_colors import get_vibe_color

logger = logging.getLogger(__name__)

# Theme color palette - Slate Blue variants
THEME = {
    "primary_darkest": "#1a252f",
    "primary_dark": "#2c3e50",
    "primary_medium": "#3d5a80",
    "primary": "#34495e",
    "primary_light": "#5d6f7f",
    "primary_lighter": "#8b95a5",
    "primary_lightest": "#d4dce6",
    "accent_light": "#ecf0f1",
    "text_dark": "#2c3e50",
    "text_muted": "#555",
}




def get_color_for_value(value: int, min_val: int = -10, max_val: int = 10) -> str:
    """
    Get color for a value in a range.
    Uses theme color variants from light to medium intensity.
    """
    # Normalize to 0-1 range
    normalized = (value - min_val) / (max_val - min_val) if max_val > min_val else 0
    normalized = max(0, min(1, normalized))  # Clamp to 0-1
    
    # Color gradient using theme: light -> medium
    # Light variant for low values, darker variant for high values
    if normalized < 0.5:
        # Light to medium-light
        r = int(212 + (normalized * 2) * (61 - 212))
        g = int(220 + (normalized * 2) * (90 - 220))
        b = int(230 + (normalized * 2) * (128 - 230))
    else:
        # Medium-light to medium
        r = int(136 + (normalized - 0.5) * 2 * (90 - 136))
        g = int(149 + (normalized - 0.5) * 2 * (94 - 149))
        b = int(165 + (normalized - 0.5) * 2 * (128 - 165))
    
    return f"rgba({r}, {g}, {b}, 0.8)"


def create_stat_bar(label: str, value: int, min_val: int = -10, max_val: int = 10, show_value: bool = True):
    """Create a horizontal bar for displaying integer stats with bidirectional bar"""
    range_size = max_val - min_val
    
    # Determine bar position and width for bidirectional scale (like -10 to 10)
    if min_val < 0 and max_val > 0:
        # Bidirectional bar
        center_percent = abs(min_val) / range_size * 100
        
        if value >= 0:
            bar_start = center_percent
            bar_width = (value / range_size) * 100
        else:
            bar_width = (abs(value) / range_size) * 100
            bar_start = center_percent - bar_width
    else:
        # Unidirectional bar (0 to max)
        bar_start = 0
        bar_width = ((value - min_val) / range_size) * 100 if range_size > 0 else 0
    
    bar_color = get_color_for_value(value, min_val, max_val)
    label_display = label.replace("_", " ").title()
    
    return html.Div([
        html.Div([
            html.Span(label_display, style={"fontSize": "13px", "fontWeight": "bold"}),
            html.Span(str(value), style={"fontSize": "13px", "color": THEME["primary_lighter"], "marginLeft": "8px"})
        ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px", "alignItems": "center"}),
        html.Div([
            html.Div(
                style={
                    "marginLeft": f"{bar_start}%",
                    "width": f"{max(bar_width, 1)}%",  # Minimum width for visibility
                    "height": "20px",
                    "backgroundColor": bar_color,
                    "borderRadius": "3px",
                    "transition": "all 0.6s ease-in-out",
                }
            )
        ], style={
            "width": "100%",
            "height": "20px",
            "backgroundColor": THEME["accent_light"],
            "borderRadius": "3px",
            "border": "1px solid " + THEME["primary_lightest"],
            "overflow": "hidden"
        })
    ], style={"marginBottom": "12px"})


def create_text_field(label: str, value: Optional[str], truncate: bool = False, full_width: bool = False):
    """Create a text field for displaying string data"""
    if not value:
        value = "Not specified"
    
    if truncate and len(value) > 100:
        value = value[:100] + "..."
    
    return html.Div([
        html.Span(label + ":", style={"fontWeight": "bold", "color": THEME["text_dark"], "display": "block", "marginBottom": "5px"}),
        html.P(value, style={"color": THEME["text_muted"], "marginTop": "0", "marginBottom": "0", "lineHeight": "1.5", "wordBreak": "break-word"})
    ], style={"marginBottom": "12px"})


def create_list_field(label: str, items: list, empty_message: str = "None"):
    """Create a field for displaying list items"""
    if not items:
        items_display = [html.Span(empty_message, style={"color": THEME["primary_lighter"], "fontStyle": "italic"})]
    else:
        items_display = [
            html.Div([
                html.Span("•", style={"marginRight": "8px", "color": THEME["text_dark"]}),
                html.Span(str(item).replace("_", " ").title())
            ], style={"display": "flex", "marginBottom": "5px", "alignItems": "flex-start"})
            for item in items
        ]
    
    return html.Div([
        html.Span(label + ":", style={"fontWeight": "bold", "color": THEME["text_dark"], "display": "block", "marginBottom": "8px"}),
        html.Div(items_display, style={"paddingLeft": "8px"})
    ], style={"marginBottom": "12px"})


def create_demographic_badge(label: str, value: Optional[str]):
    """Create a badge for demographic information"""
    if not value:
        return None
    
    return html.Span(
        value.replace("_", " ").title(),
        style={
            "display": "inline-block",
            "backgroundColor": THEME["primary_lightest"],
            "color": THEME["primary_dark"],
            "padding": "4px 12px",
            "borderRadius": "20px",
            "fontSize": "12px",
            "fontWeight": "500",
            "marginRight": "8px",
            "marginBottom": "8px"
        }
    )


def create_profile_cards(role_profile: RoleProfile):
    """Create comprehensive profile cards showing all character information"""
    cards = []
    
    # 1. HEADER/OVERVIEW CARD
    full_name = f"{role_profile.first_name}"
    if role_profile.last_name:
        full_name += f" {role_profile.last_name}"
    
    header_content = [
        html.H2(full_name, style={"margin": "0 0 12px 0", "color": THEME["text_dark"]}),
        html.Span(
            f"Season {role_profile.timestamp.season}, Episode {role_profile.timestamp.episode}",
            style={"backgroundColor": THEME["primary_light"], "color": "white", "padding": "6px 12px", "borderRadius": "4px", "marginRight": "8px"}
        ),
        html.Span(
            role_profile.role_id.replace("_", " ").title(),
            style={"backgroundColor": THEME["primary"], "color": "white", "padding": "6px 12px", "borderRadius": "4px", "marginRight": "8px"}
        ),
    ]
    
    # Add alias spans
    if role_profile.aliases:
        for alias in role_profile.aliases:
            header_content.append(
                html.Span(
                    alias,
                    style={"backgroundColor": THEME["primary_lightest"], "color": THEME["primary_dark"], "padding": "6px 12px", "borderRadius": "4px", "marginRight": "8px"}
                )
            )
    
    cards.append(Card([
        CardBody(header_content, style={"padding": "20px"})
        ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.15)", "borderLeft": "4px solid " + THEME["primary_dark"]}))
    
    # 2. DESCRIPTION CARD
    if role_profile.description:
        cards.append(Card([
            CardHeader("Overview", style={
                "backgroundColor": THEME["primary_dark"],
                "color": "white",
                "fontWeight": "bold",
                "fontSize": "16px"
            }),
            CardBody([
                html.P(role_profile.description, style={
                    "color": THEME["text_dark"],
                    "lineHeight": "1.7",
                    "marginBottom": "0"
                })
            ], style={"padding": "20px"})
        ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))
    
    # 3. DEMOGRAPHICS CARD
    demographics = role_profile.demographics
    demo_fields = []
    
    demo_fields.append(create_text_field("Full Name", f"{role_profile.first_name}{' ' + role_profile.last_name if role_profile.last_name else ''}"))
    
    if demographics.age:
        demo_fields.append(create_text_field("Age", demographics.age.replace("_", " ").title()))
    if demographics.sex:
        demo_fields.append(create_text_field("Sex", "Male" if demographics.sex == "m" else "Female" if demographics.sex == "f" else "Other"))
    if demographics.nationality:
        demo_fields.append(create_text_field("Nationality", demographics.nationality.title()))
    if demographics.occupation:
        demo_fields.append(create_text_field("Occupation", demographics.occupation.title()))
    if demographics.state:
        demo_fields.append(create_text_field("Physical State", demographics.state.replace("_", " ").title()))
    if demographics.appearance:
        demo_fields.append(create_text_field("Appearance", demographics.appearance.replace("_", " ").title()))
    if demographics.religion:
        demo_fields.append(create_text_field("Religion", demographics.religion.replace("_", " ").title()))
    if demographics.sexual_orientation:
        demo_fields.append(create_text_field("Sexual Orientation", demographics.sexual_orientation.replace("_", " ").title()))
    
    # Split fields into two columns
    mid_point = (len(demo_fields) + 1) // 2
    left_demo_fields = demo_fields[:mid_point]
    right_demo_fields = demo_fields[mid_point:]
    
    # Create two-column layout for basic fields
    demo_content = [
        Row([
            Col(html.Div(left_demo_fields, style={"display": "flex", "flexDirection": "column", "gap": "12px"}), md=6),
            Col(html.Div(right_demo_fields, style={"display": "flex", "flexDirection": "column", "gap": "12px"}), md=6)
        ])
    ]
    
    # Add list fields below (full width)
    if demographics.affiliation:
        demo_content.append(create_list_field("Affiliations", demographics.affiliation))
    
    if role_profile.aliases:
        demo_content.append(create_list_field("Aliases", role_profile.aliases))
    
    if demographics.superpowers:
        demo_content.append(create_list_field("Superpowers", demographics.superpowers))
    
    cards.append(Card([
        CardHeader("Demographics", style={
            "backgroundColor": THEME["primary_dark"],
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "16px"
        }),
        CardBody(demo_content, style={"padding": "20px"})
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))

    
    # 4. PERSONALITY CARD
    personality = role_profile.personality
    personality_content = [
        create_stat_bar("Extraversion", personality.extraversion),
        create_stat_bar("Sensing", personality.sensing),
        create_stat_bar("Thinking", personality.thinking),
        create_stat_bar("Judging", personality.judging),
        html.Hr(style={"margin": "15px 0"}),
        html.P(str(personality), style={"fontSize": "12px", "color": THEME["primary_lighter"], "marginBottom": "0", "fontStyle": "italic"})
    ]
    
    cards.append(Card([
        CardHeader("Personality (MBTI)", style={
            "backgroundColor": THEME["primary_dark"],
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "16px"
        }),
        CardBody(personality_content, style={"padding": "20px"})
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))

    
    # 5. SKILLS CARD
    skills = role_profile.skills
    skill_fields = [f for f in skills.model_fields.keys()]
    skills_content = [
        create_stat_bar(field, getattr(skills, field), min_val=0, max_val=10)
        for field in skill_fields
    ]
    
    cards.append(Card([
        CardHeader("Skills", style={
            "backgroundColor": THEME["primary_dark"],
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "16px"
        }),
        CardBody(skills_content, style={"padding": "20px"})
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))

    
    # 6. EMOTIONS CARD - Core Emotions
    core_emo = role_profile.emotions.core
    core_emo_fields = ['happiness', 'sadness', 'anger', 'fear', 'disgust', 'shocked']
    core_emo_content = [
        create_stat_bar(field, getattr(core_emo, field), min_val=0, max_val=10)
        for field in core_emo_fields
    ]
    
    cards.append(Card([
        CardHeader("Emotions - Core", style={
            "backgroundColor": THEME["primary_dark"],
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "16px"
        }),
        CardBody(core_emo_content, style={"padding": "20px"})
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))

    
    # 7. EMOTIONS CARD - Mood
    mood = role_profile.emotions.mood
    mood_fields = ['calmness_anxiety', 'loneliness_connection', 'despair_hope', 'helplessness_confidence']
    mood_content = [
        create_stat_bar(field, getattr(mood, field))
        for field in mood_fields
    ]
    mood_content.append(html.Hr(style={"margin": "12px 0"}))
    mood_content.append(html.Div([
        html.Span("Arousal Level: ", style={"fontWeight": "bold"}),
        html.Span(str(role_profile.emotions.intensity.arousal), style={"color": THEME["primary_lighter"]})
    ]))
    
    cards.append(Card([
        CardHeader("Emotions - Mood", style={
            "backgroundColor": THEME["primary_dark"],
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "16px"
        }),
        CardBody(mood_content, style={"padding": "20px"})
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))

    
    # 8. EMOTIONS CARD - Self State
    self_state = role_profile.emotions.self_state
    self_state_fields = ['self_worth', 'social_trust', 'guilt', 'shame', 'hostility', 'resentment']
    self_state_content = [
        create_stat_bar(field, getattr(self_state, field))
        for field in self_state_fields
    ]
    
    cards.append(Card([
        CardHeader("Emotions - Self State", style={
            "backgroundColor": THEME["primary_dark"],
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "16px"
        }),
        CardBody(self_state_content, style={"padding": "20px"})
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))

    
    # 9. CORE VALUES CARD
    core_values = role_profile.core_values
    core_value_fields = [f for f in core_values.model_fields.keys()]
    core_values_content = [
        create_stat_bar(field, getattr(core_values, field))
        for field in core_value_fields
    ]
    
    cards.append(Card([
        CardHeader("Core Values", style={
            "backgroundColor": THEME["primary_dark"],
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "16px"
        }),
        CardBody(core_values_content, style={"padding": "20px"})
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))

    
    # 10. AURA CARD
    aura = role_profile.aura
    aura_fields = ['intimidation_warmth', 'recklessness_carefulness', 'humor', 'attractiveness', 'mystery']
    aura_content = [
        create_stat_bar(field, getattr(aura, field))
        for field in aura_fields
    ]
    
    cards.append(Card([
        CardHeader("Aura / Presence", style={
            "backgroundColor": THEME["primary_dark"],
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "16px"
        }),
        CardBody(aura_content, style={"padding": "20px"})
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))

    
    # 11. GOALS CARD
    if role_profile.goals:
        goals_content = []
        for i, goal in enumerate(role_profile.goals, 1):
            goals_content.append(html.Div([
                html.H5(f"{goal.goal_id.replace('_', ' ').title()}", style={
                    "margin": "0 0 8px 0",
                    "color": THEME["text_dark"]
                }),
                html.P(goal.goal, style={
                    "margin": "0 0 12px 0",
                    "color": THEME["text_muted"],
                    "lineHeight": "1.5"
                }),
                html.Hr(style={"margin": "12px 0", "borderColor": THEME["primary_lightest"]})
                if i < len(role_profile.goals) else None
            ]))
        
        cards.append(Card([
            CardHeader(f"Goals ({len(role_profile.goals)})", style={
                "backgroundColor": THEME["primary_dark"],
                "color": "white",
                "fontWeight": "bold",
                "fontSize": "16px"
            }),
            CardBody(goals_content, style={"padding": "20px"})
        ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))
    # 12. CATCH PHRASES CARD
    if role_profile.catch_phrases:
        phrases_content = []
        for i, phrase in enumerate(role_profile.catch_phrases, 1):
            phrases_content.append(html.Div([
                html.Div([
                    html.Span("Context: ", style={"fontWeight": "bold", "color": THEME["text_dark"]}),
                    html.Span(phrase.context or "General", style={"color": THEME["primary_lighter"]})
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Blockquote(
                    f'"{phrase.catch_phrase}"',
                    style={
                        "borderLeft": "4px solid " + THEME["primary_medium"],
                        "paddingLeft": "12px",
                        "marginLeft": "0",
                        "marginRight": "0",
                        "marginTop": "8px",
                        "marginBottom": "12px",
                        "fontStyle": "italic",
                        "color": THEME["text_dark"]
                    }
                ),
                html.Hr(style={"margin": "12px 0", "borderColor": THEME["primary_lightest"]})
                if i < len(role_profile.catch_phrases) else None
            ]))
        
        cards.append(Card([
            CardHeader(f"Catch Phrases ({len(role_profile.catch_phrases)})", style={
                "backgroundColor": THEME["primary_dark"],
                "color": "white",
                "fontWeight": "bold",
                "fontSize": "16px"
            }),
            CardBody(phrases_content, style={"padding": "20px"})
        ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"}))
    
    return cards

def format_scene_name(scene_name: str) -> str:
    """Convert camelCase or snake_case scene name to readable sentence"""
    import re
    # Replace underscores with spaces first
    name = scene_name.replace("_", " ")
    # Add space before capital letters, but keep consecutive capitals together
    # Only split before a capital that is followed by a lowercase letter
    name = re.sub(r'(?<!^)(?=[A-Z][a-z])', ' ', name)
    return name


def create_memories_card(story, role_id: str, season: int, episode: int):
    """Create a card showing scenes featuring this role in the episode"""
    try:
        season_obj = story.get_season(season)
        if not season_obj:
            return None
        
        timestamp = SETimestamp(season=season, episode=episode)
        scenes = season_obj.search_scenes(
            role=role_id,
            min_timestamp=timestamp,
            max_timestamp=timestamp
        )
        
        if not scenes:
            return None
        
        scenes_content = []
        for i, scene in enumerate(scenes, 1):
            scenes_content.append(html.Div([
                html.H5(
                    format_scene_name(scene.scene_name),
                    style={"margin": "0 0 8px 0", "color": THEME["text_dark"]}
                ),
                html.Div([
                    html.Span("Location: ", style={"fontWeight": "bold"}),
                    html.Span(scene.location or "Unknown", style={"color": THEME["primary_lighter"]})
                ], style={"fontSize": "13px", "marginBottom": "6px"}),
                html.Div([
                    html.Span("Vibe: ", style={"fontWeight": "bold"}),
                    html.Span(
                        scene.vibe.replace("_", " ").title(),
                        style={
                            "display": "inline-block",
                            "backgroundColor": get_vibe_color(scene.vibe, THEME["primary_light"]),
                            "color": "white",
                            "padding": "2px 8px",
                            "borderRadius": "12px",
                            "fontSize": "12px",
                            "fontWeight": "bold"
                        }
                    )
                ], style={"fontSize": "13px", "marginBottom": "6px"}),
                html.P(
                    scene.description,
                    style={"color": THEME["text_muted"], "margin": "8px 0", "lineHeight": "1.5", "fontSize": "13px"}
                ),
                html.Hr(style={"margin": "12px 0", "borderColor": THEME["primary_lightest"]})
                if i < len(scenes) else None
            ]))
        
        return Card([
            CardHeader(f"Memories ({len(scenes)})", style={
                "backgroundColor": THEME["primary_dark"],
                "color": "white",
                "fontWeight": "bold",
                "fontSize": "16px"
            }),
            CardBody(scenes_content, style={"padding": "20px"})
        ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"})
    except Exception as e:
        logger.warning(f"Could not load memories for {role_id}: {e}")
        return None


def create_profile_page():
    """Create an interactive profile page with character details loaded from data"""
    from utils.profile_manager import ProfileManager
    
    manager = ProfileManager("data")
    
    # Get all roles across all seasons
    all_roles = set()
    for season_num in range(1, 8):  # Seasons 1-7
        season_roles = manager.get_all_roles_in_season(season_num)
        all_roles.update(season_roles)
    
    all_roles = sorted(list(all_roles))
    initial_roles_options = [
        {"label": role.replace("_", " ").title(), "value": role}
        for role in all_roles
    ]
    
    # Initial values
    initial_role = all_roles[0] if all_roles else None
    initial_season = None
    initial_episodes = []
    
    return Container([
        html.H1("Character Profile", style={
            "marginBottom": "30px",
            "marginTop": "20px",
            "color": THEME["text_dark"],
            "fontWeight": "bold"
        }),
        
        # Configuration Card
        Card([
            CardHeader("Select Character & Episode", style={
                "backgroundColor": THEME["primary_dark"],
                "color": "white",
                "fontWeight": "bold",
                "fontSize": "18px"
            }),
            CardBody([
                Row([
                    Col([
                        html.Label("Character:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="profile-role-selector",
                            options=initial_roles_options,
                            value=initial_role,
                            style={"fontFamily": "Arial, sans-serif"},
                            clearable=False
                        )
                    ], md=4, style={"marginBottom": "15px"}),
                    
                    Col([
                        html.Label("Season:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="profile-season-selector",
                            options=[],
                            value=None,
                            style={"fontFamily": "Arial, sans-serif"},
                            clearable=False
                        )
                    ], md=4, style={"marginBottom": "15px"}),
                    
                    Col([
                        html.Label("Episode:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="profile-episode-selector",
                            options=[],
                            value=None,
                            style={"fontFamily": "Arial, sans-serif"},
                            clearable=False
                        )
                    ], md=4, style={"marginBottom": "15px"}),
                ], style={"marginBottom": "10px"})
            ])
        ], style={"marginBottom": "30px", "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"}),
        
        # Profile Content
        dcc.Loading(
            id="loading-profile",
            type="default",
            children=[
                html.Div(id="profile-cards-container", style={
                    "marginBottom": "30px",
                    "display": "flex",
                    "flexDirection": "column",
                    "gap": "20px"
                })
            ]
        ),
        
        html.Hr(),
        html.Footer([
            html.P("Character Profile - Agents of S.H.I.E.L.D.",
                  style={"textAlign": "center", "color": THEME["primary_lighter"], "marginTop": "20px"})
        ], style={"marginTop": "40px"})
    ], fluid=True, style={"padding": "20px"})


def setup_profile_callbacks(dash_app, story):
    """Register profile-specific callbacks"""
    from utils.profile_manager import ProfileManager
    
    manager = ProfileManager("data")
    
    # Update season dropdown based on role selection
    @dash_app.callback(
        Output("profile-season-selector", "options"),
        Output("profile-season-selector", "value"),
        Input("profile-role-selector", "value")
    )
    def update_seasons(role_id):
        if not role_id:
            return [], None
        
        # Find all seasons where this role appears
        available_seasons = []
        for season_num in range(1, 8):  # Seasons 1-7
            profiles = manager.get_profile_history(role_id, season_num)
            if profiles:
                available_seasons.append({
                    "label": f"Season {season_num}",
                    "value": season_num
                })
        
        return available_seasons, available_seasons[0]["value"] if available_seasons else None
    
    # Update episode dropdown based on role and season selection
    @dash_app.callback(
        Output("profile-episode-selector", "options"),
        Output("profile-episode-selector", "value"),
        Input("profile-season-selector", "value"),
        Input("profile-role-selector", "value")
    )
    def update_episodes(season_num, role_id):
        if not season_num or not role_id:
            return [], None
        
        # Get all episodes where this role appears in the selected season
        profiles = manager.get_profile_history(role_id, season_num)
        
        episodes = [
            {
                "label": f"Episode {episode_num}",
                "value": episode_num
            }
            for episode_num, _ in profiles
        ]
        
        return episodes, episodes[0]["value"] if episodes else None
    
    # Generate profile content based on selections
    @dash_app.callback(
        Output("profile-cards-container", "children"),
        Input("profile-role-selector", "value"),
        Input("profile-episode-selector", "value"),
        Input("profile-season-selector", "value")
    )
    def update_profile(role_id, episode_num, season_num):
        if not role_id or not episode_num or not season_num:
            return [html.Div([
                html.P("Please select a character, season, and episode.", style={"color": THEME["primary_lighter"]})
            ])]
        
        try:
            # Load profile from data
            profile = get_profile_snapshot(role_id, season_num, episode_num, "data")
            
            if not profile:
                return [html.Div([
                    html.P(f"Profile not found for {role_id} in Season {season_num}, Episode {episode_num}.", style={"color": THEME["primary_lighter"]})
                ])]
            
            cards = create_profile_cards(profile)
            
            # Add memories card (scenes featuring this role in this episode)
            memories_card = create_memories_card(story, role_id, season_num, episode_num)
            
            # Split cards into two columns
            # First 2 cards (header + overview) in full width, rest in 2 columns
            result = []
            
            basic_info_count = 2 if len(cards) > 2 else len(cards)
            
            # Add first 2 cards in full width
            for i in range(min(basic_info_count, len(cards))):
                result.append(cards[i])
            
            # Split remaining cards into two columns
            # Right column: MBTI, Goals (if exists), Catch Phrases (if exists), then Memory
            # Left column: everything else
            remaining_cards = cards[basic_info_count:]
            
            if remaining_cards or memories_card:
                right_column_cards = []
                left_column_cards = []
                
                # Identify indices to move to right panel
                right_indices = set()
                
                # MBTI is at index 1 of remaining_cards
                if len(remaining_cards) > 1:
                    right_indices.add(1)
                
                # Core Values is at index 6 of remaining_cards
                if len(remaining_cards) > 6:
                    right_indices.add(6)
                
                # Goals: at index len-2 if we have >= 9 remaining cards (11 total)
                if len(remaining_cards) >= 9:
                    right_indices.add(len(remaining_cards) - 2)
                
                # Catch Phrases: at index len-1 if we have >= 10 remaining cards (12 total)
                if len(remaining_cards) >= 10:
                    right_indices.add(len(remaining_cards) - 1)
                
                # Distribute cards based on right_indices
                for i, card in enumerate(remaining_cards):
                    if i in right_indices:
                        right_column_cards.append(card)
                    else:
                        left_column_cards.append(card)
                
                # Add memory card to right column (at the end)
                if memories_card:
                    right_column_cards.append(memories_card)
                
                # Create two column layout with vertical stacking
                result.append(
                    Row([
                        Col(
                            html.Div(left_column_cards, style={
                                "display": "flex",
                                "flexDirection": "column",
                                "gap": "20px"
                            }),
                            md=6
                        ),
                        Col(
                            html.Div(right_column_cards, style={
                                "display": "flex",
                                "flexDirection": "column",
                                "gap": "20px"
                            }),
                            md=6
                        )
                    ])
                )
            
            return result
        except Exception as e:
            logger.error(f"Error generating profile: {e}", exc_info=True)
            return [html.Div([
                html.P(f"Error loading profile: {str(e)}", style={"color": "red"})
            ])]
