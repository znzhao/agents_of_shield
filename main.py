import logging
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from model_structure.stories import Story, read_story_from_files
from desk_dash.desk_dash import DeskDashApp
from core.utils import is_openai_key_set, save_openai_api_key
from pages.home import create_home_page
from pages.episode import create_episode_page
from pages.analytics import create_analytics_page, setup_analytics_callbacks
from pages.profile import create_profile_page, setup_profile_callbacks
from pages.memory_search import create_memory_search_page, setup_memory_search_callbacks
from pages.chat_with import create_chat_with_page, setup_chat_with_callbacks
from pages.parser_control import create_parser_control_page, setup_parser_control_callbacks

logger = logging.getLogger(__name__)

class StoryViewerApp(DeskDashApp):
    def __init__(self, story: Story, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.story = story
    
    def create_layout(self):
        """Create a well-structured layout to display story content"""
        return html.Div([
            dcc.Location(id="url", refresh=False),
            dcc.Store(id="sidebar-state", data={"open": True}),
            dcc.Store(id="openai-key-status", data={"configured": is_openai_key_set()}),

            # -- OpenAI API Key Setup Modal ----------------------------
            dbc.Modal([
                dbc.ModalHeader(
                    dbc.ModalTitle("OpenAI API Key"),
                    close_button=False,
                    style={"backgroundColor": "#2c3e50", "color": "white"},
                ),
                dbc.ModalBody([
                    html.P(
                        "An OpenAI API key is required to use GPT models (gpt-4o, gpt-4.1, etc.). "
                        "You can proceed without one — only local Ollama models will be available.",
                        style={"marginBottom": "16px"},
                    ),
                    dbc.Input(
                        id="apikey-input",
                        type="password",
                        placeholder="sk-...",
                        debounce=False,
                        style={"marginBottom": "8px"},
                    ),
                    html.Div(id="apikey-feedback", style={"fontSize": "13px", "minHeight": "20px"}),
                ]),
                dbc.ModalFooter([
                    dbc.Button(
                        "Save & Enable GPT",
                        id="apikey-save-btn",
                        color="primary",
                        style={"marginRight": "8px"},
                    ),
                    dbc.Button(
                        "Proceed Without GPT",
                        id="apikey-skip-btn",
                        color="secondary",
                        outline=True,
                    ),
                ]),
            ],
                id="apikey-modal",
                is_open=not is_openai_key_set(),
                backdrop="static",
                keyboard=False,
                centered=True,
            ),

            html.Div([
                # Sidebar
                html.Div([
                    html.Div([
                        html.Button(
                            "☰",
                            id="sidebar-toggle",
                            n_clicks=0,
                            style={
                                "backgroundColor": "transparent",
                                "border": "none",
                                "color": "white",
                                "fontSize": "24px",
                                "cursor": "pointer",
                                "marginBottom": "20px",
                                "padding": "5px",
                            }
                        ),
                        html.Div([
                            html.H3("Menu", style={"marginBottom": "30px", "color": "white", "marginTop": "0"}),
                            html.Ul([
                                html.Li(
                                    dcc.Link(
                                        "Home",
                                        href="/",
                                        style={
                                            "color": "white",
                                            "textDecoration": "none",
                                            "fontSize": "18px",
                                            "display": "block",
                                            "padding": "10px",
                                            "borderRadius": "5px",
                                            "transition": "background-color 0.2s, border-left 0.2s",
                                            "borderLeft": "4px solid transparent",
                                        },
                                        id="nav-home"
                                    ),
                                    style={"listStyle": "none", "marginBottom": "15px"},
                                    className="nav-item"
                                ),
                                html.Li(
                                    dcc.Link(
                                        "Memory Search",
                                        href="/memory-search",
                                        style={
                                            "color": "white",
                                            "textDecoration": "none",
                                            "fontSize": "18px",
                                            "display": "block",
                                            "padding": "10px",
                                            "borderRadius": "5px",
                                            "transition": "background-color 0.2s, border-left 0.2s",
                                            "borderLeft": "4px solid transparent",
                                        },
                                        id="nav-memory-search"
                                    ),
                                    style={"listStyle": "none", "marginBottom": "15px"},
                                    className="nav-item"
                                ),
                                html.Li(
                                    dcc.Link(
                                        "Analytics",
                                        href="/analytics",
                                        style={
                                            "color": "white",
                                            "textDecoration": "none",
                                            "fontSize": "18px",
                                            "display": "block",
                                            "padding": "10px",
                                            "borderRadius": "5px",
                                            "transition": "background-color 0.2s, border-left 0.2s",
                                            "borderLeft": "4px solid transparent",
                                        },
                                        id="nav-analytics"
                                    ),
                                    style={"listStyle": "none", "marginBottom": "15px"},
                                    className="nav-item"
                                ),
                                html.Li(
                                    dcc.Link(
                                        "Profile",
                                        href="/profile",
                                        style={
                                            "color": "white",
                                            "textDecoration": "none",
                                            "fontSize": "18px",
                                            "display": "block",
                                            "padding": "10px",
                                            "borderRadius": "5px",
                                            "transition": "background-color 0.2s, border-left 0.2s",
                                            "borderLeft": "4px solid transparent",
                                        },
                                        id="nav-profile"
                                    ),
                                    style={"listStyle": "none", "marginBottom": "15px"},
                                    className="nav-item"
                                ),
                                html.Li(
                                    dcc.Link(
                                        "Chat With",
                                        href="/chat-with",
                                        style={
                                            "color": "white",
                                            "textDecoration": "none",
                                            "fontSize": "18px",
                                            "display": "block",
                                            "padding": "10px",
                                            "borderRadius": "5px",
                                            "transition": "background-color 0.2s, border-left 0.2s",
                                            "borderLeft": "4px solid transparent",
                                        },
                                        id="nav-chat-with"
                                    ),
                                    style={"listStyle": "none", "marginBottom": "15px"},
                                    className="nav-item"
                                ),
                                html.Li(
                                    dcc.Link(
                                        "Parser Control",
                                        href="/parser-control",
                                        style={
                                            "color": "white",
                                            "textDecoration": "none",
                                            "fontSize": "18px",
                                            "display": "block",
                                            "padding": "10px",
                                            "borderRadius": "5px",
                                            "transition": "background-color 0.2s, border-left 0.2s",
                                            "borderLeft": "4px solid transparent",
                                        },
                                        id="nav-parser-control"
                                    ),
                                    style={"listStyle": "none", "marginBottom": "15px"},
                                    className="nav-item"
                                ),
                            ], style={"padding": "0", "margin": "0"}),
                        ], id="menu-content"),
                    ], style={"padding": "20px"})
                ], id="sidebar", style={
                    "backgroundColor": "#2c3e50",
                    "width": "16.666%",
                    "position": "fixed",
                    "left": "0",
                    "top": "0",
                    "height": "100vh",
                    "overflowY": "auto",
                    "transition": "width 0.3s ease",
                }),
                
                # Main content area
                html.Div([
                    html.Div(id="page-content", style={"padding": "20px"})
                ], id="main-content", style={
                    "marginLeft": "16.666%",
                    "width": "83.334%",
                    "transition": "margin-left 0.3s ease, width 0.3s ease",
                })
            ], style={
                "display": "flex",
                "margin": "0",
                "padding": "0",
            })
        ], style={"margin": "0", "padding": "0"})
    
    def setup_callbacks(self):
        """Setup routing callbacks"""
        # Setup page-specific callbacks
        setup_analytics_callbacks(self.dash_app, self.story)
        setup_profile_callbacks(self.dash_app, self.story)
        setup_memory_search_callbacks(self.dash_app, self.story)
        setup_chat_with_callbacks(self.dash_app, self.story)
        setup_parser_control_callbacks(self.dash_app, self.story)

        # -- OpenAI API Key Modal callbacks -------------------------
        @self.dash_app.callback(
            Output("apikey-modal", "is_open"),
            Output("openai-key-status", "data"),
            Output("apikey-feedback", "children"),
            Output("apikey-feedback", "style"),
            Input("apikey-save-btn", "n_clicks"),
            Input("apikey-skip-btn", "n_clicks"),
            State("apikey-input", "value"),
            State("openai-key-status", "data"),
            prevent_initial_call=True,
        )
        def handle_apikey_modal(save_clicks, skip_clicks, key_input, current_status):
            from dash import callback_context as ctx
            triggered = ctx.triggered_id

            if triggered == "apikey-skip-btn":
                return False, {"configured": False}, "", {"fontSize": "13px", "minHeight": "20px"}

            if triggered == "apikey-save-btn":
                key = (key_input or "").strip()
                if not key:
                    return True, current_status, "Please enter an API key.", {
                        "fontSize": "13px", "minHeight": "20px", "color": "#c0392b"
                    }
                save_openai_api_key(key)
                return False, {"configured": True}, "", {"fontSize": "13px", "minHeight": "20px"}

            return True, current_status, "", {"fontSize": "13px", "minHeight": "20px"}

        # Callback to highlight active nav link
        @self.dash_app.callback(
            Output("nav-home", "style"),
            Output("nav-memory-search", "style"),
            Output("nav-profile", "style"),
            Output("nav-chat-with", "style"),
            Output("nav-parser-control", "style"),
            Output("nav-analytics", "style"),
            Input("url", "pathname")
        )
        def update_nav_styles(pathname):
            # Base style for all nav links
            base_style = {
                "color": "white",
                "textDecoration": "none",
                "fontSize": "18px",
                "display": "block",
                "padding": "10px",
                "borderRadius": "5px",
                "transition": "background-color 0.2s, border-left 0.2s",
                "borderLeft": "4px solid transparent",
            }
            
            # Active style
            active_style = {
                **base_style,
                "backgroundColor": "#34495e",
                "borderLeft": "4px solid #3498db",
                "fontWeight": "bold",
            }
            
            # Determine which nav is active
            pathname = pathname or "/"
            home_style = active_style if pathname == "/" else base_style
            memory_search_style = active_style if pathname == "/memory-search" else base_style
            profile_style = active_style if pathname == "/profile" else base_style
            chat_with_style = active_style if pathname == "/chat-with" else base_style
            parser_control_style = active_style if pathname == "/parser-control" else base_style
            analytics_style = active_style if pathname == "/analytics" else base_style
            
            return home_style, memory_search_style, profile_style, chat_with_style, parser_control_style, analytics_style
        
        # Clientside callback for sidebar toggle
        self.dash_app.clientside_callback(
            """
            function(n_clicks, data) {
                var sidebar = document.getElementById('sidebar');
                var mainContent = document.getElementById('main-content');
                var menuContent = document.getElementById('menu-content');
                
                if (!data) {
                    data = {open: true};
                }
                
                var isOpen = data.open;
                var newState = {open: !isOpen};
                
                if (newState.open) {
                    sidebar.style.width = '16.666%';
                    mainContent.style.marginLeft = '16.666%';
                    mainContent.style.width = '83.334%';
                    if (menuContent) menuContent.style.display = 'block';
                } else {
                    sidebar.style.width = '60px';
                    mainContent.style.marginLeft = '60px';
                    mainContent.style.width = 'calc(100% - 60px)';
                    if (menuContent) menuContent.style.display = 'none';
                }
                
                return newState;
            }
            """,
            Output("sidebar-state", "data"),
            Input("sidebar-toggle", "n_clicks"),
            State("sidebar-state", "data"),
            prevent_initial_call=True
        )
        
        @self.dash_app.callback(
            Output("page-content", "children"),
            Input("url", "pathname")
        )
        def display_page(pathname):
            if pathname == "/" or pathname == "":
                return create_home_page(self.story)
            elif pathname == "/memory-search":
                return create_memory_search_page(self.story)
            elif pathname == "/analytics":
                return create_analytics_page(self.story)
            elif pathname == "/profile":
                return create_profile_page()
            elif pathname == "/chat-with":
                return create_chat_with_page(self.story)
            elif pathname == "/parser-control":
                return create_parser_control_page(self.story)
            elif pathname.startswith("/episode/"):
                try:
                    parts = pathname.split("/")
                    season_num = int(parts[2])
                    episode_num = int(parts[3])
                    return create_episode_page(self.story, season_num, episode_num)
                except (IndexError, ValueError):
                    return html.H1("Invalid Episode URL", style={"color": "red"})
            else:
                return html.H1("Page Not Found", style={"color": "red"})
    
    def on_quit(self):
        """Clean up resources before quitting"""
        logger.info("Cleaning up application resources...")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load story data
    logger.info("Loading Agents of S.H.I.E.L.D. story data...")
    story = read_story_from_files(
        title="Agents of S.H.I.E.L.D.",
        data_dir="data",
        compute_embeddings=True,
        save_embeddings=True,
        force_reembedding=False
    )
    logger.info(f"Loaded story: {story}")
    
    # Create and run the app
    app = StoryViewerApp(story=story, app_name="Story Viewer - Agents of S.H.I.E.L.D.")
    logger.info("Starting Story Viewer application...")
    app.run(debug=False)
