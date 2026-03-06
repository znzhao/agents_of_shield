"""Memory Search page for semantic and keyword search across episodes"""

import logging
import traceback
from dash import html, dcc, Output, Input, State, callback, clientside_callback
from dash_bootstrap_components import Container, Row, Col, Card, CardBody, CardHeader, Button
from model_structure.stories import SETimestamp, Story
from pages.vibe_colors import get_vibe_color

logger = logging.getLogger(__name__)

# Theme color palette - Slate Blue variants (matching other pages)
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


def create_memory_search_page(story: Story):
    """Create the memory search page"""
    
    # Get all available roles
    all_roles = story.get_roles()
    role_options = [{"label": role.replace("_", " ").title(), "value": role} for role in sorted(all_roles)]
    
    # Get max season and episode for default bounds
    max_season = max((s.season for s in story.seasons), default=1)
    max_episode_in_last_season = len(story.get_season(max_season).episodes) if story.get_season(max_season) else 1
    
    # Pre-populate episode options for initial season values
    season_1 = story.get_season(1)
    initial_start_episodes = [{"label": f"Episode {i}", "value": i} for i in range(1, len(season_1.episodes) + 1)] if season_1 else []
    
    max_season_obj = story.get_season(max_season)
    initial_end_episodes = [{"label": f"Episode {i}", "value": i} for i in range(1, len(max_season_obj.episodes) + 1)] if max_season_obj else []
    
    return Container([
        html.H1("Memory Search", style={"marginTop": "20px", "marginBottom": "10px", "color": THEME["text_dark"], "fontWeight": "bold"}),
        html.P(
            "Search across episodes using keywords or semantic similarity",
            style={"color": THEME["text_muted"], "marginBottom": "30px", "fontSize": "16px"}
        ),
        
        # Hidden store for Enter key listener setup
        dcc.Store(id="_memory_search_enter_listener"),
        
        Row([
            Col([
                Card([
                    CardHeader("Search Parameters", style={"fontWeight": "bold", "fontSize": "16px", "backgroundColor": THEME["primary_dark"], "color": "white"}),
                    CardBody([
                        # Start Season/Episode
                        html.Div([
                            html.H5("Start Episode", style={"color": THEME["text_dark"], "marginBottom": "12px", "fontWeight": "bold"}),
                            Row([
                                Col([
                                    html.Label("Season:", style={"fontWeight": "bold", "color": THEME["text_dark"], "marginBottom": "5px"}),
                                    dcc.Dropdown(
                                        id="start-season-dropdown",
                                        options=[{"label": f"Season {s.season}", "value": s.season} for s in story.seasons],
                                        value=1,
                                        style={"width": "100%"}
                                    )
                                ], md=6),
                                Col([
                                    html.Label("Episode:", style={"fontWeight": "bold", "color": THEME["text_dark"], "marginBottom": "5px"}),
                                    dcc.Dropdown(
                                        id="start-episode-dropdown",
                                        options=initial_start_episodes,
                                        value=1,
                                        style={"width": "100%"}
                                    )
                                ], md=6),
                            ]),
                        ], style={"marginBottom": "20px"}),
                        
                        # End Season/Episode
                        html.Div([
                            html.H5("End Episode", style={"color": THEME["text_dark"], "marginBottom": "12px", "fontWeight": "bold"}),
                            Row([
                                Col([
                                    html.Label("Season:", style={"fontWeight": "bold", "color": THEME["text_dark"], "marginBottom": "5px"}),
                                    dcc.Dropdown(
                                        id="end-season-dropdown",
                                        options=[{"label": f"Season {s.season}", "value": s.season} for s in story.seasons],
                                        value=max_season,
                                        style={"width": "100%"}
                                    )
                                ], md=6),
                                Col([
                                    html.Label("Episode:", style={"fontWeight": "bold", "color": THEME["text_dark"], "marginBottom": "5px"}),
                                    dcc.Dropdown(
                                        id="end-episode-dropdown",
                                        options=initial_end_episodes,
                                        value=max_episode_in_last_season,
                                        style={"width": "100%"}
                                    )
                                ], md=6),
                            ]),
                        ], style={"marginBottom": "20px"}),
                        
                        # Roles
                        html.Div([
                            html.H5("Filter by Roles (Optional)", style={"color": THEME["text_dark"], "marginBottom": "12px", "fontWeight": "bold"}),
                            dcc.Dropdown(
                                id="role-dropdown",
                                options=role_options,
                                value=None,
                                multi=False,
                                placeholder="Select roles... (leave empty for all)",
                                style={"width": "100%"}
                            )
                        ], style={"marginBottom": "20px"}),
                        # Search Type and Parameters
                        html.Div([
                            html.H5("Search Settings", style={"color": THEME["text_dark"], "marginBottom": "12px", "fontWeight": "bold"}),
                            Row([
                                Col([
                                    dcc.Checklist(
                                        id="vector-search-toggle",
                                        options=[{"label": " Use Vector Search (Semantic)", "value": True}],
                                        value=[True],
                                        style={"display": "flex", "alignItems": "center", "marginBottom": "15px"}
                                    ),
                                ], md=12),
                            ]),
                            Row([
                                Col([
                                    html.Label("Number of Top Results:", style={"fontWeight": "bold", "color": THEME["text_dark"], "marginBottom": "5px"}),
                                    dcc.Input(
                                        id="top-n-input",
                                        type="number",
                                        placeholder="Enter number of results",
                                        value=3,
                                        min=1,
                                        max=20,
                                        step=1,
                                        style={
                                            "width": "100%",
                                            "padding": "8px",
                                            "borderRadius": "4px",
                                            "border": f"1px solid {THEME['primary_lightest']}",
                                            "fontSize": "14px"
                                        }
                                    )
                                ], md=6),
                            ]),
                        ], style={"marginBottom": "20px"}),
                    ], style={"color": THEME["text_dark"]})
                ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)", "marginBottom": "20px", "height": "100%", "display": "flex", "flexDirection": "column"}),
            ], md=4, style={"display": "flex", "flexDirection": "column"}),
            
            Col([
                Card([
                    CardHeader("Search Query", style={"fontWeight": "bold", "fontSize": "16px", "backgroundColor": THEME["primary_dark"], "color": "white"}),
                    CardBody([
                        html.Label("Enter search terms:", style={"fontWeight": "bold", "color": THEME["text_dark"], "marginBottom": "10px", "display": "block"}),
                        dcc.Textarea(
                            id="search-query-input",
                            placeholder="Enter your search query here... (e.g., 'team conflict', 'alien invasion', 'character development')",
                            style={
                                "width": "100%",
                                "height": "300px",
                                "padding": "10px",
                                "borderRadius": "4px",
                                "border": f"1px solid {THEME['primary_lightest']}",
                                "fontSize": "14px",
                                "fontFamily": "Arial, sans-serif",
                                "resize": "vertical"
                            }
                        ),
                        html.Div(style={"height": "10px"}),
                        Button(
                            "Search",
                            id="search-button",
                            n_clicks=0,
                            style={
                                "width": "100%",
                                "padding": "10px",
                                "backgroundColor": THEME["primary_dark"],
                                "color": "white",
                                "border": "none",
                                "borderRadius": "4px",
                                "fontSize": "16px",
                                "fontWeight": "bold",
                                "cursor": "pointer",
                                "transition": "background-color 0.2s",
                            }
                        )
                    ], style={"color": THEME["text_dark"]})
                ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)", "marginBottom": "20px", "height": "100%", "display": "flex", "flexDirection": "column"}),
            ], md=8, style={"display": "flex", "flexDirection": "column"}),
        ], style={"display": "flex", "alignItems": "stretch"}),
        
        # Results area with loading indicator
        dcc.Loading(
            id="search-loading",
            type="default",
            fullscreen=False,
            children=html.Div(id="search-results-container", style={"marginTop": "30px"}),
            style={
                "display": "flex",
                "justifyContent": "center",
                "alignItems": "center",
                "minHeight": "200px"
            }
        ),
        
    ], fluid=True, style={"padding": "20px"})

def format_scene_name(scene_name: str) -> str:
    """Convert camelCase or snake_case scene name to readable sentence"""
    import re
    # Replace underscores with spaces first
    name = scene_name.replace("_", " ")
    # Add space before capital letters, but keep consecutive capitals together
    # Only split before a capital that is followed by a lowercase letter
    name = re.sub(r'(?<!^)(?=[A-Z][a-z])', ' ', name)
    return name

def create_scene_result_card(scene, story):
    """Create a card for displaying a search result scene"""
    # Safely get the episode
    season_obj = story.get_season(scene.season)
    if not season_obj or scene.episode > len(season_obj.episodes):
        episode_name = "Unknown Episode"
    else:
        episode = season_obj.episodes[scene.episode - 1]  # episodes are 1-indexed
        episode_name = episode.name
    
    # Get the vibe color
    vibe_color = get_vibe_color(scene.vibe, THEME["primary_light"])
    
    # Roles present in scene
    roles_display = ", ".join([role.replace("_", " ").title() for role in scene.roles[:5]])
    if len(scene.roles) > 5:
        roles_display += f", +{len(scene.roles) - 5} more"
    
    return html.Div([
        html.Div([
            html.Div([
                html.H5(
                    f"S{scene.season}E{scene.episode:02d} - {format_scene_name(scene.scene_name)}",
                    style={"margin": "0", "color": THEME["text_dark"], "fontWeight": "bold"}
                ),
                html.P(
                    f"From episode: {episode_name}",
                    style={"margin": "5px 0", "color": THEME["text_muted"], "fontSize": "13px"}
                ),
            ], style={"flex": "1"}),
            html.Span(
                scene.vibe.replace("_", " ").title(),
                style={
                    "backgroundColor": vibe_color,
                    "color": "white",
                    "padding": "5px 12px",
                    "borderRadius": "20px",
                    "fontSize": "12px",
                    "fontWeight": "bold",
                    "whiteSpace": "nowrap",
                    "marginLeft": "10px"
                }
            )
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px", "justifyContent": "space-between"}),
        
        html.P(
            scene.description,
            style={"color": THEME["text_muted"], "marginBottom": "10px", "lineHeight": "1.6"}
        ),
        
        html.Div([
            html.Div([
                html.Span("Roles: ", style={"fontWeight": "bold", "color": THEME["text_dark"]}),
                html.Span(roles_display, style={"color": THEME["text_muted"]})
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Span("Location: ", style={"fontWeight": "bold", "color": THEME["text_dark"]}),
                html.Span(scene.location or "Unknown", style={"color": THEME["text_muted"]})
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Span("Significance: ", style={"fontWeight": "bold", "color": THEME["text_dark"]}),
                html.Span(scene.significance.title(), style={"color": THEME["text_muted"]})
            ]),
        ]),
    ], style={
        "padding": "15px",
        "border": f"1px solid {THEME['primary_lightest']}",
        "borderRadius": "6px",
        "marginBottom": "15px",
        "backgroundColor": "#fafafa",
        "transition": "all 0.2s",
        "cursor": "pointer"
    }, className="scene-result-card")


def setup_memory_search_callbacks(app, story):
    """Setup callbacks for the memory search page"""
    
    # Setup Enter key listener for search query textarea
    app.clientside_callback(
        """
        function(dummy) {
            var textarea = document.getElementById('search-query-input');
            if (textarea && !textarea.__enter_key_listener_added__) {
                textarea.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        document.getElementById('search-button').click();
                    }
                });
                textarea.__enter_key_listener_added__ = true;
            }
            return null;
        }
        """,
        Output('_memory_search_enter_listener', 'data'),
        Input('search-query-input', 'id'),
        prevent_initial_call=False
    )
    
    @app.callback(
        Output("start-episode-dropdown", "options"),
        Input("start-season-dropdown", "value")
    )
    def update_start_episode_options(season_value):
        if not season_value:
            return []
        season = story.get_season(int(season_value))
        if not season:
            return []
        num_episodes = len(season.episodes)
        return [{"label": f"Episode {i}", "value": int(i)} for i in range(1, num_episodes + 1)]
    
    @app.callback(
        Output("end-episode-dropdown", "options"),
        Input("end-season-dropdown", "value")
    )
    def update_end_episode_options(season_value):
        if not season_value:
            return []
        season = story.get_season(int(season_value))
        if not season:
            return []
        num_episodes = len(season.episodes)
        return [{"label": f"Episode {i}", "value": int(i)} for i in range(1, num_episodes + 1)]
    
    @app.callback(
        Output("search-results-container", "children"),
        Input("search-button", "n_clicks"),
        State("search-query-input", "value"),
        State("start-season-dropdown", "value"),
        State("start-episode-dropdown", "value"),
        State("end-season-dropdown", "value"),
        State("end-episode-dropdown", "value"),
        State("role-dropdown", "value"),
        State("vector-search-toggle", "value"),
        State("top-n-input", "value"),
        prevent_initial_call=True
    )
    def perform_search(n_clicks, query_text, start_season, start_episode, end_season, end_episode, selected_role, vec_search_toggle, top_n):
        """Perform the search and display results"""
        
        if not query_text or not query_text.strip():
            return html.Div([
                html.P("Please enter a search query.", style={"color": "#e74c3c", "fontSize": "16px", "fontWeight": "bold"})
            ])
        
        try:
            # Validate and set up search parameters
            if start_season is None or start_episode is None or end_season is None or end_episode is None:
                return html.Div([
                    html.P("Please select both start and end episodes.", style={"color": "#e74c3c", "fontSize": "16px", "fontWeight": "bold"})
                ])
            
            # Ensure all values are integers
            start_season = int(start_season)
            start_episode = int(start_episode)
            end_season = int(end_season)
            end_episode = int(end_episode)
            
            min_timestamp = SETimestamp(season=start_season, episode=start_episode)
            max_timestamp = SETimestamp(season=end_season, episode=end_episode)
            
            # Validate timestamp order
            if min_timestamp > max_timestamp:
                return html.Div([
                    html.P("End episode must be after or equal to start episode.", style={"color": "#e74c3c", "fontSize": "16px", "fontWeight": "bold"})
                ])
            
            # Set default top_n if not provided
            if not top_n or top_n < 1:
                top_n = 10
            
            # Determine search type
            use_vec_search = bool(vec_search_toggle)
            
            # Perform the search
            results = story.search_scenes(
                query=query_text,
                role=selected_role,
                min_timestamp=min_timestamp,
                max_timestamp=max_timestamp,
                top_k=top_n,
                vec_search=use_vec_search
            )
            
            # Create results display
            if not results:
                return html.Div([
                    html.P(
                        "No scenes found matching your search criteria.",
                        style={"color": THEME["text_muted"], "fontSize": "16px", "fontStyle": "italic"}
                    )
                ])
            
            # Display results
            search_type = "Semantic" if use_vec_search else "Keyword"
            result_cards = [
                html.Div([
                    html.H4(
                        f"Search Results - {search_type} Search ({len(results)} found)",
                        style={"color": THEME["text_dark"], "marginBottom": "20px", "fontWeight": "bold"}
                    ),
                ]),
                html.Div([create_scene_result_card(scene, story) for scene in results])
            ]
            
            return html.Div(result_cards)
        
        except Exception as e:
            tb_str = traceback.format_exc()
            logger.error(f"Error performing search: {tb_str}")
            return html.Div([
                html.Div([
                    html.P(
                        "Error during search:",
                        style={"color": "#e74c3c", "fontSize": "16px", "fontWeight": "bold", "marginBottom": "10px"}
                    ),
                    html.Pre(
                        tb_str,
                        style={
                            "backgroundColor": "#f5f5f5",
                            "border": "1px solid #ddd",
                            "borderRadius": "4px",
                            "padding": "12px",
                            "fontSize": "12px",
                            "color": "#333",
                            "overflow": "auto",
                            "maxHeight": "400px",
                            "fontFamily": "monospace",
                            "whiteSpace": "pre-wrap",
                            "wordWrap": "break-word"
                        }
                    )
                ])
            ])
