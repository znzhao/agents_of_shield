"""Analytics dashboard page"""

import logging
from dash import html, dcc, Output, Input
from dash_bootstrap_components import Container, Row, Col, Card, CardBody, CardHeader
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


def get_analytics_data(story, season_selection, x_axis, y_axis, min_count):
    """Generate analytics data based on user selections"""
    # Select the appropriate story object
    if season_selection == "all":
        story_obj = story
    else:
        story_obj = story.get_season(season_number=season_selection)
    
    # Gather data based on x_axis selection
    categories = []
    counts = []
    
    if x_axis == "role":
        roles = story_obj.get_roles()
        for role_id in roles:
            if y_axis == "scenes":
                count = story_obj.count_scenes_by(role_id=role_id)
            else:  # episodes
                # For episodes with role, we count unique episodes with that role
                if season_selection == "all":
                    # Count unique (season, episode) pairs across all seasons
                    episodes_set = set()
                    for season in story_obj.seasons:
                        for episode in season.episodes:
                            if role_id in episode.roles:
                                episodes_set.add((episode.season, episode.episode))
                    count = len(episodes_set)
                else:
                    # For a single season, count unique episode numbers
                    episodes_set = set()
                    for episode in story_obj.episodes:
                        if role_id in episode.roles:
                            episodes_set.add(episode.episode)
                    count = len(episodes_set)
            
            if count >= min_count:
                categories.append(role_id.replace('_', ' ').title())
                counts.append(count)
    
    elif x_axis == "location":
        locations = story_obj.get_locations()
        for location in locations:
            if y_axis == "scenes":
                count = story_obj.count_scenes_by(location=location)
            else:  # episodes
                count = story_obj.count_episodes_by(location=location)
            
            if count >= min_count:
                categories.append(location.replace('_', ' ').title())
                counts.append(count)
    
    elif x_axis == "vibe":
        vibes = ['tense', 'emotional', 'action-packed', 'comedic', 'mysterious', 
                'romantic', 'tragic', 'hopeful', 'suspenseful', 'dramatic', 
                'dark', 'lighthearted', 'intense', 'melancholic', 'thrilling']
        for vibe in vibes:
            if y_axis == "scenes":
                count = story_obj.count_scenes_by(vibe=vibe)
            else:  # episodes
                # For episodes with vibe, count unique episodes with that vibe
                if season_selection == "all":
                    episodes_set = set()
                    for season in story_obj.seasons:
                        for episode in season.episodes:
                            if any(scene.vibe == vibe for scene in episode.scenes):
                                episodes_set.add((episode.season, episode.episode))
                    count = len(episodes_set)
                else:
                    episodes_set = set()
                    for episode in story_obj.episodes:
                        if any(scene.vibe == vibe for scene in episode.scenes):
                            episodes_set.add(episode.episode)
                    count = len(episodes_set)
            
            if count >= min_count:
                categories.append(vibe.replace('_', ' ').title())
                counts.append(count)
    
    # Sort by count descending
    sorted_data = sorted(zip(categories, counts), key=lambda x: x[1], reverse=True)
    if sorted_data:
        categories, counts = zip(*sorted_data)
        categories = list(categories)
        counts = list(counts)
    else:
        categories = []
        counts = []
    
    return categories, counts


def create_analytics_figure(story, season_selection, x_axis, y_axis, min_count):
    """Create a Plotly figure for the analytics"""
    categories, counts = get_analytics_data(story, season_selection, x_axis, y_axis, min_count)
    
    # Truncate category labels for display if they're too long (especially for locations)
    max_label_length = 15
    truncated_categories = []
    for cat in categories:
        if len(cat) > max_label_length:
            truncated_categories.append(cat[:max_label_length] + "...")
        else:
            truncated_categories.append(cat)
    
    # Create a gradient color palette based on the count values for visual appeal
    if counts:
        max_count = max(counts)
        # Generate colors from light to dark based on values
        colors = []
        for count in counts:
            # Map count value to a color gradient
            intensity = count / max_count
            # Create a nice gradient from light blue to dark blue
            if x_axis == "role":
                r = int(31 + (65 - 31) * (1 - intensity))
                g = int(119 + (191 - 119) * (1 - intensity))
                b = int(180 + (255 - 180) * (1 - intensity))
            elif x_axis == "location":
                r = int(255 + (220 - 255) * intensity)
                g = int(127 + (20 - 127) * intensity)
                b = int(14)
            else:  # vibe
                r = int(148 + (75 - 148) * intensity)
                g = int(103 + (0 - 103) * intensity)
                b = int(189 + (130 - 189) * intensity)
            colors.append(f"rgba({r}, {g}, {b}, 0.85)")
    else:
        colors = ["#1f77b4"]
    
    fig = go.Figure(data=[
        go.Bar(
            x=truncated_categories,
            y=counts,
            customdata=categories,  # Store full category names for hover
            marker=dict(
                color=colors,
                line=dict(color="rgba(0,0,0,0.15)", width=1.5),
                cornerradius=6,
            ),
            text=counts,
            textposition="outside",
            textfont=dict(size=12, color="#2c3e50", family="Arial Black"),
            hovertemplate="<b style='font-size:14px'>%{customdata}</b><br>" + 
                         (f"<b>Scenes:</b> %{{y}}<extra></extra>" if y_axis == "scenes" else f"<b>Episodes:</b> %{{y}}<extra></extra>"),
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="#2c3e50",
                font=dict(size=13, color="#2c3e50", family="Arial")
            )
        )
    ])
    
    # Determine season label
    if season_selection == "all":
        season_label = "All Seasons"
    else:
        season_label = f"Season {season_selection}"
    
    # Update layout with enhanced styling
    fig.update_layout(
        title=dict(
            text=f"<b style='font-size:24px'>{x_axis.title()} by {y_axis.title()}</b><br><sub style='font-size:14px; color:#666'>{season_label}</sub>",
            x=0.5,
            xanchor="center",
            font=dict(size=20, color="#2c3e50", family="Arial, sans-serif")
        ),
        xaxis=dict(
            title=dict(
                text=f"<b>{x_axis.title()}</b>",
                font=dict(size=15, color="#2c3e50", family="Arial Black")
            ),
            tickangle=-45,
            tickfont=dict(size=12, color="#2c3e50", family="Arial"),
            showgrid=False,
            zeroline=False,
            showline=True,
            linewidth=2,
            linecolor="#2c3e50",
            mirror=True,
        ),
        yaxis=dict(
            title=dict(
                text=f"<b>{y_axis.title()}</b>",
                font=dict(size=15, color="#2c3e50", family="Arial Black")
            ),
            tickfont=dict(size=12, color="#2c3e50", family="Arial"),
            showgrid=True,
            gridwidth=1.5,
            gridcolor="rgba(200,200,200,0.3)",
            zeroline=False,
            showline=True,
            linewidth=2,
            linecolor="#2c3e50",
            mirror=True,
        ),
        plot_bgcolor="rgba(245,248,252,1)",
        paper_bgcolor="rgba(255,255,255,1)",
        margin=dict(l=80, r=60, t=120, b=150),
        hovermode="x unified",
        height=700,
        font=dict(family="Arial, sans-serif", size=12, color="#2c3e50"),
        transition=dict(duration=500, easing="cubic-in-out"),
        bargap=0.25,
        bargroupgap=0.1,
        showlegend=False,
    )
    
    return fig


def create_analytics_page(story):
    """Create an interactive analytics page with dynamic visualizations"""
    # Get all seasons for dropdown
    season_options = [
        {"label": "All Seasons", "value": "all"}
    ]
    for season in story.seasons:
        season_options.append(
            {"label": f"Season {season.season}", "value": season.season}
        )
    
    return Container([
        html.H1("Analytics Dashboard", style={
            "marginBottom": "30px",
            "marginTop": "20px",
            "color": "#2c3e50",
            "fontWeight": "bold"
        }),
        
        # Control Panel
        Card([
            CardHeader("Chart Configuration", style={
                "backgroundColor": "#2c3e50",
                "color": "white",
                "fontWeight": "bold",
                "fontSize": "18px"
            }),
            CardBody([
                Row([
                    Col([
                        html.Label("Season:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="analytics-season-selector",
                            options=season_options,
                            value="all",
                            style={"fontFamily": "Arial, sans-serif"},
                            clearable=False
                        )
                    ], md=3, style={"marginBottom": "15px"}),
                    
                    Col([
                        html.Label("X-Axis (Category):", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="analytics-x-axis-selector",
                            options=[
                                {"label": "Role", "value": "role"},
                                {"label": "Location", "value": "location"},
                                {"label": "Vibe", "value": "vibe"}
                            ],
                            value="role",
                            style={"fontFamily": "Arial, sans-serif"},
                            clearable=False
                        )
                    ], md=3, style={"marginBottom": "15px"}),
                    
                    Col([
                        html.Label("Y-Axis (Metric):", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="analytics-y-axis-selector",
                            options=[
                                {"label": "Scene Count", "value": "scenes"},
                                {"label": "Episode Count", "value": "episodes"}
                            ],
                            value="scenes",
                            style={"fontFamily": "Arial, sans-serif"},
                            clearable=False
                        )
                    ], md=3, style={"marginBottom": "15px"}),
                    
                    Col([
                        html.Label("Min Count:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Input(
                            id="analytics-min-count",
                            type="number",
                            value=0,
                            min=0,
                            step=1,
                            style={
                                "width": "100%",
                                "padding": "8px",
                                "borderRadius": "4px",
                                "border": "1px solid #ddd"
                            }
                        )
                    ], md=3, style={"marginBottom": "15px"}),
                ], style={"marginBottom": "10px"})
            ])
        ], style={"marginBottom": "30px", "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"}),
        
        # Graph
        html.Div([
            dcc.Loading(
                id="loading-graph",
                type="default",
                children=[
                    dcc.Graph(
                        id="analytics-graph",
                        figure=create_analytics_figure(story, "all", "role", "scenes", 0),
                        style={"height": "600px"},
                        config={"responsive": True, "displayModeBar": True}
                    )
                ]
            )
        ], style={"marginBottom": "30px"}),
        
        html.Hr(),
        html.Footer([
            html.P("Interactive Analytics - Agents of S.H.I.E.L.D.",
                  style={"textAlign": "center", "color": "#999", "marginTop": "20px"})
        ], style={"marginTop": "40px"})
    ], fluid=True, style={"padding": "20px"})


def setup_analytics_callbacks(dash_app, story):
    """Register analytics-specific callbacks"""
    @dash_app.callback(
        Output("analytics-graph", "figure"),
        Input("analytics-season-selector", "value"),
        Input("analytics-x-axis-selector", "value"),
        Input("analytics-y-axis-selector", "value"),
        Input("analytics-min-count", "value")
    )
    def update_analytics_graph(season, x_axis, y_axis, min_count):
        try:
            return create_analytics_figure(story, season, x_axis, y_axis, min_count or 0)
        except Exception as e:
            logger.error(f"Error updating analytics graph: {e}")
            # Return empty figure on error
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error loading chart: {str(e)}",
                showarrow=False,
                font=dict(size=14, color="red")
            )
            return fig
