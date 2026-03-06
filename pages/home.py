"""Home page showing all seasons and episodes"""

from dash import html, dcc
from dash_bootstrap_components import Container, Row, Col, Card, CardBody, CardHeader

# Theme color palette - Slate Blue variants (matching profile.py and episode.py)
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


def create_home_page(story):
    """Create the main story view with all episodes"""
    season_cards = []
    for season in story.seasons:
        episodes = season.episodes
        episode_count = len(episodes)
        
        # Create clickable episode items
        episode_items = []
        for ep in episodes:
            episode_link = dcc.Link(
                html.Div([
                    html.Span(f"E{ep.episode:02d} - {ep.name}", style={"fontWeight": "500", "color": THEME["text_dark"]}),
                ], style={
                    "padding": "8px 12px",
                    "borderRadius": "4px",
                    "marginBottom": "6px",
                    "cursor": "pointer",
                    "transition": "background-color 0.2s",
                    "backgroundColor": THEME["accent_light"],
                }),
                href=f"/episode/{ep.season}/{ep.episode}",
                style={"textDecoration": "none", "color": "inherit"}
            )
            episode_items.append(html.Li(episode_link, style={"listStyle": "none"}))
        
        season_card = Col([
            Card([
                CardHeader(f"Season {season.season}", style={"fontWeight": "bold", "fontSize": "18px", "backgroundColor": THEME["primary_dark"], "color": "white"}),
                CardBody([
                    html.P(f"{episode_count} Episodes", style={"color": THEME["text_muted"]}),
                    html.Ul(episode_items, style={"marginBottom": "0"})
                ], style={"color": THEME["text_dark"]})
            ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"})
        ], md=4, style={"marginBottom": "20px"})
        season_cards.append(season_card)
    
    return Container([
        html.H1(story.title, style={"textAlign": "center", "marginTop": "20px", "marginBottom": "10px", "color": THEME["text_dark"], "fontWeight": "bold"}),
        html.P(
            f"{len(story.seasons)} Seasons • {len(story.all_episodes())} Episodes",
            style={"textAlign": "center", "color": THEME["text_muted"], "marginBottom": "30px", "fontSize": "16px"}
        ),
        Row(season_cards, style={"marginBottom": "30px"}),
        html.Hr(style={"borderColor": THEME["primary_lightest"]}),
        html.Footer([
            html.P("Agents of S.H.I.E.L.D. Story Viewer", style={"textAlign": "center", "color": THEME["primary_lighter"], "marginTop": "20px"})
        ], style={"marginTop": "40px"})
    ], fluid=True, style={"padding": "20px"})
