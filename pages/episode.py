"""Episode detail page"""

from dash import html, dcc
from dash_bootstrap_components import Container, Row, Col, Card, CardBody, CardHeader, Badge
from pages.vibe_colors import get_vibe_color

# Theme color palette - Slate Blue variants (matching profile.py)
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


def create_episode_page(story, season_num, episode_num):
    """Create a detailed view for a specific episode"""
    # Find the episode
    episode = None
    for season in story.seasons:
        if season.season == season_num:
            for ep in season.episodes:
                if ep.episode == episode_num:
                    episode = ep
                    break
            break
    
    if episode is None:
        return Container([
            html.H1("Episode Not Found", style={"color": THEME["primary_dark"]}),
            dcc.Link(html.Button("Back to Story", className="btn btn-primary"), href="/")
        ], fluid=True, style={"padding": "20px"})
    
    # Build scenes list, sorted by scene number
    sorted_scenes = sorted(episode.scenes, key=lambda s: s.num)
    scenes_rows = []
    for i in range(0, len(sorted_scenes), 2):
        scene_cards_row = []
        for j in range(2):
            if i + j < len(sorted_scenes):
                scene = sorted_scenes[i + j]
                scene_card = Card([
                    CardHeader([
                        html.Span(f"Scene {scene.num}: {scene.scene_name}", style={"fontWeight": "bold"}),
                    ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "backgroundColor": THEME["primary_dark"], "color": "white"}),
                    CardBody([
                        html.P(scene.description, style={"marginBottom": "12px", "color": THEME["text_muted"]}),
                        Row([
                            Col([
                                html.Strong("Significance: ", style={"color": THEME["text_dark"]}),
                                Badge(scene.significance.capitalize(), color="warning", className="ms-2")
                            ], md=6, style={"marginBottom": "8px"}),
                            Col([
                                html.Strong("Vibe: ", style={"color": THEME["text_dark"]}),
                                Badge(scene.vibe.replace("_", " ").title(), color=get_vibe_color(scene.vibe, THEME["primary_light"]), className="ms-2")
                            ], md=6, style={"marginBottom": "8px"}),
                        ]),
                        Row([
                            Col([
                                html.Strong("Location: ", style={"color": THEME["text_dark"]}),
                                html.Span(scene.location or "Unknown", style={"color": THEME["text_muted"]})
                            ], md=6, style={"marginBottom": "8px"}),
                            Col([
                                html.Strong("Characters: ", style={"color": THEME["text_dark"]}),
                                html.Span(", ".join(scene.roles) if scene.roles else "None", style={"color": THEME["text_muted"]})
                            ], md=6, style={"marginBottom": "8px"}),
                        ]),
                    ])
                ], style={"marginBottom": "15px"})
                scene_cards_row.append(Col(scene_card, md=6, style={"marginBottom": "20px"}))
        scenes_rows.append(Row(scene_cards_row))
    
    scenes_content = scenes_rows
    
    # Build episode metadata
    metadata_content = []
    if episode.roles:
        metadata_content.append(
            html.Div([
                html.Strong("Characters: ", style={"color": THEME["text_dark"]}),
                html.Span(", ".join(episode.roles), style={"color": THEME["text_muted"]})
            ], style={"marginBottom": "12px"})
        )
    if episode.locations:
        metadata_content.append(
            html.Div([
                html.Strong("Locations: ", style={"color": THEME["text_dark"]}),
                html.Span(", ".join(episode.locations), style={"color": THEME["text_muted"]})
            ], style={"marginBottom": "12px"})
        )
    if episode.affiliations:
        metadata_content.append(
            html.Div([
                html.Strong("Affiliations: ", style={"color": THEME["text_dark"]}),
                html.Span(", ".join(episode.affiliations), style={"color": THEME["text_muted"]})
            ], style={"marginBottom": "12px"})
        )
    
    return Container([
        Row([
            Col([
                dcc.Link(
                    html.Button("← Back to Story", className="btn btn-secondary", 
                               style={"marginBottom": "20px", "backgroundColor": THEME["primary_dark"], "borderColor": THEME["primary_dark"], "color": "white"}),
                    href="/"
                ),
            ], md=12)
        ]),
        html.H1(f"S{episode.season}E{episode.episode:02d} - {episode.name}", 
               style={"marginBottom": "10px", "color": THEME["text_dark"], "fontWeight": "bold"}),
        
        # Synopsis
        html.Div([
            html.H4("Synopsis", style={"marginTop": "20px", "marginBottom": "10px", "color": THEME["text_dark"], "fontWeight": "bold"}),
            html.P(episode.synopsis or "No synopsis available.", 
                  style={"fontSize": "16px", "lineHeight": "1.6", "color": THEME["text_muted"]}),
        ]) if episode.synopsis else None,
        
        # Metadata
        html.Div([
            html.H4("Episode Details", style={"marginTop": "20px", "marginBottom": "10px", "color": THEME["text_dark"], "fontWeight": "bold"}),
            html.Div(metadata_content, style={"backgroundColor": THEME["accent_light"], "padding": "15px", "borderRadius": "5px", "borderLeft": f"4px solid {THEME['primary_dark']}"})
        ]) if metadata_content else None,
        
        # Scenes
        html.Div([
            html.H4("Scenes", style={"marginTop": "20px", "marginBottom": "15px", "color": THEME["text_dark"], "fontWeight": "bold"}),
            html.Div(scenes_content)
        ]) if scenes_content else html.P("No scenes available.", style={"color": THEME["text_muted"]}),
        
        # Back button at bottom
        html.Div([
            dcc.Link(
                html.Button("← Back to Story", className="btn btn-secondary", 
                           style={"marginTop": "30px", "backgroundColor": THEME["primary_dark"], "borderColor": THEME["primary_dark"], "color": "white"}),
                href="/"
            )
        ], style={"textAlign": "center"}),
        
        html.Hr(style={"marginTop": "40px", "borderColor": THEME["primary_lightest"]}),
        html.Footer([
            html.P("Agents of S.H.I.E.L.D. Story Viewer", 
                  style={"textAlign": "center", "color": THEME["primary_lighter"], "marginTop": "20px"})
        ], style={"marginTop": "40px"})
    ], fluid=True, style={"padding": "20px"})
