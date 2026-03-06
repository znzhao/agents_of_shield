"""Chat With page - Interactive chat with Agents of S.H.I.E.L.D. characters"""

import logging
import threading
from dash import html, dcc, Output, Input, State, no_update, callback_context
from dash_bootstrap_components import Container, Row, Col, Card, CardBody, CardHeader, Button
from model_structure.stories import Story
from core.llm_engine import Engine

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

# Available LLM models — GPT options carry a flag so they can be disabled at runtime
_GPT_LABEL_SUFFIX = "  (requires OpenAI key)"
MODEL_OPTIONS_ALL = [
    {"label": m, "value": m} for m in Engine.ALL_MODELS
]

def _build_model_options(openai_configured: bool) -> list:
    """Return model option list with GPT entries disabled when no key is set."""
    opts = []
    for m in Engine.ALL_MODELS:
        if m in Engine.GPT_MODELS and not openai_configured:
            opts.append({"label": m + _GPT_LABEL_SUFFIX, "value": m, "disabled": True})
        else:
            opts.append({"label": m, "value": m})
    return opts

_DEFAULT_MODEL = Engine.OLLAMA_MODELS[0]  # safe default regardless of key


def create_chat_with_page(story: Story):
    """Create the Chat With page layout"""
    from utils.profile_manager import ProfileManager

    manager = ProfileManager("data")

    # Gather all roles across all seasons
    all_roles = set()
    for season_num in range(1, 8):
        season_roles = manager.get_all_roles_in_season(season_num)
        all_roles.update(season_roles)

    all_roles = sorted(list(all_roles))
    role_options = [
        {"label": role.replace("_", " ").title(), "value": role}
        for role in all_roles
    ]
    initial_role = all_roles[0] if all_roles else None

    return Container([
        html.H1("Chat With a Character", style={
            "marginBottom": "10px",
            "marginTop": "20px",
            "color": THEME["text_dark"],
            "fontWeight": "bold",
        }),
        html.P(
            "Select a character, season, and episode, then start a conversation in character.",
            style={"color": THEME["text_muted"], "marginBottom": "25px", "fontSize": "16px"},
        ),

        # Hidden store for conversation history
        dcc.Store(id="chat-history", data=[]),
        # Store the current bot config so we know when to reset
        dcc.Store(id="chat-bot-config", data={}),
        # Interval for polling streamed responses
        dcc.Interval(id="chat-stream-interval", interval=150, disabled=True, n_intervals=0),

        # ── Configuration Card ────────────────────────────────────────
        Card([
            CardHeader("Configuration", style={
                "backgroundColor": THEME["primary_dark"],
                "color": "white",
                "fontWeight": "bold",
                "fontSize": "18px",
            }),
            CardBody([
                Row([
                    Col([
                        html.Label("Character:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="chat-role-selector",
                            options=role_options,
                            value=initial_role,
                            clearable=False,
                            style={"fontFamily": "Arial, sans-serif"},
                        ),
                    ], md=3, style={"marginBottom": "15px"}),

                    Col([
                        html.Label("Season:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="chat-season-selector",
                            options=[],
                            value=None,
                            clearable=False,
                            style={"fontFamily": "Arial, sans-serif"},
                        ),
                    ], md=2, style={"marginBottom": "15px"}),

                    Col([
                        html.Label("Episode:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="chat-episode-selector",
                            options=[],
                            value=None,
                            clearable=False,
                            style={"fontFamily": "Arial, sans-serif"},
                        ),
                    ], md=2, style={"marginBottom": "15px"}),

                    Col([
                        html.Label("RAG Top-N:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="chat-topn-selector",
                            options=[{"label": str(n), "value": n} for n in [1, 3, 5, 8, 10, 15, 20]],
                            value=5,
                            clearable=False,
                            style={"fontFamily": "Arial, sans-serif"},
                        ),
                    ], md=2, style={"marginBottom": "15px"}),

                    Col([
                        html.Label("Model:", style={"fontWeight": "bold", "marginBottom": "8px"}),
                        dcc.Dropdown(
                            id="chat-model-selector",
                            options=MODEL_OPTIONS_ALL,
                            value=_DEFAULT_MODEL,
                            clearable=False,
                            style={"fontFamily": "Arial, sans-serif"},
                        ),
                        html.Div(
                            id="chat-no-apikey-warning",
                            children="",
                            style={"fontSize": "11px", "color": "#e67e22", "marginTop": "4px"},
                        ),
                    ], md=3, style={"marginBottom": "15px"}),
                ]),
            ]),
        ], style={"marginBottom": "20px", "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"}),

        # ── Character Snapshot ────────────────────────────────────────
        Card([
            CardHeader(
                html.Div([
                    html.Span("Character Snapshot", style={"flex": "1"}),
                    html.Span(
                        id="chat-snapshot-episode-label",
                        style={"fontSize": "13px", "fontWeight": "normal", "opacity": "0.85"},
                    ),
                ], style={"display": "flex", "alignItems": "center"}),
                style={
                    "backgroundColor": THEME["primary"],
                    "color": "white",
                    "fontWeight": "bold",
                    "fontSize": "16px",
                },
            ),
            CardBody(
                html.Div(
                    id="chat-snapshot-display",
                    children=[html.P(
                        "Select a character, season, and episode to view the profile snapshot.",
                        style={"color": THEME["primary_lighter"], "fontStyle": "italic",
                               "textAlign": "center", "margin": "0"},
                    )],
                ),
                style={"padding": "12px 20px"},
            ),
        ], style={"marginBottom": "20px", "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"}),

        # ── Chat Area ─────────────────────────────────────────────────
        Card([
            CardHeader(
                html.Div([
                    html.Span("Conversation", style={"flex": "1"}),
                    Button(
                        "Clear Chat",
                        id="chat-clear-btn",
                        color="light",
                        size="sm",
                        style={"fontSize": "13px"},
                    ),
                ], style={"display": "flex", "alignItems": "center"}),
                style={
                    "backgroundColor": THEME["primary_dark"],
                    "color": "white",
                    "fontWeight": "bold",
                    "fontSize": "18px",
                },
            ),
            CardBody([
                # Message display area
                html.Div(
                    id="chat-messages",
                    children=[
                        html.P(
                            "Select a character and start chatting!",
                            style={"color": THEME["primary_lighter"], "fontStyle": "italic", "textAlign": "center", "marginTop": "40px"},
                        )
                    ],
                    style={
                        "height": "450px",
                        "overflowY": "auto",
                        "padding": "15px",
                        "backgroundColor": "#fafbfc",
                        "borderRadius": "6px",
                        "border": f"1px solid {THEME['primary_lightest']}",
                        "marginBottom": "15px",
                    },
                ),

                # Input row
                Row([
                    Col([
                        dcc.Input(
                            id="chat-input",
                            type="text",
                            placeholder="Type your message…",
                            debounce=False,
                            n_submit=0,
                            style={
                                "width": "100%",
                                "padding": "10px 14px",
                                "borderRadius": "6px",
                                "border": f"1px solid {THEME['primary_lightest']}",
                                "fontSize": "15px",
                                "outline": "none",
                            },
                        ),
                    ], md=10, style={"paddingRight": "0"}),
                    Col([
                        Button(
                            "Send",
                            id="chat-send-btn",
                            color="primary",
                            style={
                                "width": "100%",
                                "borderRadius": "6px",
                                "fontWeight": "bold",
                                "backgroundColor": THEME["primary_dark"],
                                "borderColor": THEME["primary_dark"],
                            },
                        ),
                    ], md=2),
                ]),
            ]),
        ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.12)"}),

        html.Hr(),
        html.Footer([
            html.P(
                "Chat With - Agents of S.H.I.E.L.D.",
                style={"textAlign": "center", "color": THEME["primary_lighter"], "marginTop": "20px"},
            )
        ], style={"marginTop": "40px"}),
    ], fluid=True, style={"padding": "20px"})


# ---------------------------------------------------------------------------
#  Helper: render chat history list → Dash components
# ---------------------------------------------------------------------------

def _render_messages(history: list) -> list:
    """Turn the chat-history store (list of dicts) into styled Dash children."""
    if not history:
        return [
            html.P(
                "No messages yet. Say something!",
                style={"color": THEME["primary_lighter"], "fontStyle": "italic", "textAlign": "center", "marginTop": "40px"},
            )
        ]

    children = []
    for msg in history:
        role = msg.get("role", "user")
        text = msg.get("content", "")

        if role == "user":
            children.append(
                html.Div([
                    html.Div(
                        text,
                        style={
                            "backgroundColor": THEME["primary_dark"],
                            "color": "white",
                            "padding": "10px 16px",
                            "borderRadius": "16px 16px 4px 16px",
                            "maxWidth": "70%",
                            "display": "inline-block",
                            "wordBreak": "break-word",
                            "fontSize": "14px",
                            "lineHeight": "1.5",
                        },
                    ),
                ], style={"textAlign": "right", "marginBottom": "12px"})
            )
        else:
            children.append(
                html.Div([
                    html.Span(
                        msg.get("name", "Character"),
                        style={
                            "fontWeight": "bold",
                            "fontSize": "12px",
                            "color": THEME["primary_medium"],
                            "display": "block",
                            "marginBottom": "4px",
                        },
                    ),
                    html.Div(
                        text,
                        style={
                            "backgroundColor": THEME["accent_light"],
                            "color": THEME["text_dark"],
                            "padding": "10px 16px",
                            "borderRadius": "16px 16px 16px 4px",
                            "maxWidth": "70%",
                            "display": "inline-block",
                            "wordBreak": "break-word",
                            "fontSize": "14px",
                            "lineHeight": "1.5",
                            "border": f"1px solid {THEME['primary_lightest']}",
                        },
                    ),
                ], style={"textAlign": "left", "marginBottom": "12px"})
            )

    return children


def _loading_indicator(name: str) -> html.Div:
    """Render a typing indicator bubble for the assistant."""
    return html.Div([
        html.Span(
            name,
            style={
                "fontWeight": "bold",
                "fontSize": "12px",
                "color": THEME["primary_medium"],
                "display": "block",
                "marginBottom": "4px",
            },
        ),
        html.Div([
            html.Span(className="typing-dot"),
            html.Span(className="typing-dot"),
            html.Span(className="typing-dot"),
        ], style={
            "backgroundColor": THEME["accent_light"],
            "padding": "12px 20px",
            "borderRadius": "16px 16px 16px 4px",
            "display": "inline-block",
            "border": f"1px solid {THEME['primary_lightest']}",
        }),
    ], style={"textAlign": "left", "marginBottom": "12px"})


def _render_snapshot(profile) -> list:
    """Render a styled character profile snapshot into Dash component children."""
    if profile is None:
        return [html.P(
            "Select a character, season, and episode to view the profile snapshot.",
            style={"color": THEME["primary_lighter"], "fontStyle": "italic",
                   "textAlign": "center", "margin": "0"},
        )]

    full_name = f"{profile.first_name} {profile.last_name or ''}".strip()
    initials = "".join(w[0].upper() for w in full_name.split()[:2])
    aliases = profile.aliases or []
    description = profile.description or "No description available."
    dem = profile.demographics
    affiliations = dem.affiliation if dem else []
    occupation = dem.occupation if dem else None
    state_val = dem.state if dem else None
    superpowers = (dem.superpowers or []) if dem else []

    p = profile.personality
    mbti = (
        ("E" if p.extraversion > 0 else "I")
        + ("S" if p.sensing > 0 else "N")
        + ("T" if p.thinking > 0 else "F")
        + ("J" if p.judging > 0 else "P")
    )
    goals = [g.goal for g in (profile.goals or []) if g.goal][:2]

    state_color_map = {
        "healthy": "#28a745", "injured": "#dc3545", "sick": "#fd7e14",
        "exhausted": "#6c757d", "empowered": "#007bff", "weakened": "#e83e8c",
        "normal": "#adb5bd", "poisoned": "#8b5cf6",
    }

    def _badge(text, bg=THEME["primary_medium"], color="white"):
        return html.Span(text, style={
            "backgroundColor": bg, "color": color,
            "padding": "2px 9px", "borderRadius": "10px",
            "fontSize": "11px", "marginRight": "5px",
            "display": "inline-block", "fontWeight": "500",
        })

    # Avatar circle with initials
    avatar = html.Div(initials, style={
        "width": "54px", "height": "54px", "borderRadius": "50%",
        "backgroundColor": THEME["primary_medium"], "color": "white",
        "display": "flex", "alignItems": "center", "justifyContent": "center",
        "fontSize": "18px", "fontWeight": "bold",
        "flexShrink": "0", "marginRight": "16px",
    })

    # Build name block with meta info
    meta_items = []
    if aliases:
        meta_items.append(html.Div(
            f"aka {', '.join(aliases)}",
            style={"fontSize": "12px", "color": THEME["primary_light"],
                   "fontStyle": "italic", "marginTop": "2px"},
        ))
    status_row = []
    if occupation:
        status_row.append(html.Span(occupation,
                                    style={"fontSize": "13px", "color": THEME["text_muted"]}))
    if state_val:
        if occupation:
            status_row.append(html.Span(" · ", style={"color": THEME["primary_lighter"]}))
        status_row.append(html.Span(
            state_val.replace("_", " ").title(),
            style={
                "fontSize": "11px", "color": "white",
                "backgroundColor": state_color_map.get(state_val, THEME["primary_light"]),
                "padding": "1px 8px", "borderRadius": "8px",
            },
        ))
    if status_row:
        meta_items.append(html.Div(status_row,
                                   style={"marginTop": "4px", "display": "flex",
                                          "alignItems": "center", "flexWrap": "wrap"}))

    aff_badges = [_badge(a) for a in affiliations]
    sp_badges = [_badge(s.replace("_", " ").title(), "#5f3dc4") for s in superpowers[:3]]
    all_badges = aff_badges + sp_badges
    if all_badges:
        meta_items.append(html.Div(all_badges, style={"marginTop": "6px"}))

    name_block = html.Div([
        html.Div(full_name, style={
            "fontSize": "18px", "fontWeight": "bold",
            "color": THEME["primary_dark"], "lineHeight": "1.2",
        }),
        *meta_items,
    ], style={"flex": "1"})

    header_row = html.Div([avatar, name_block], style={
        "display": "flex", "alignItems": "flex-start", "marginBottom": "14px",
    })

    # Description with MBTI + goal tags
    bottom_tags = [_badge(f"MBTI: {mbti}", THEME["primary_lightest"], THEME["primary_dark"])]
    for g in goals:
        bottom_tags.append(_badge(g[:55] + ("\u2026" if len(g) > 55 else ""), "#fff3cd", "#856404"))

    desc_section = html.Div([
        html.P(description, style={
            "fontSize": "13px", "color": THEME["text_dark"], "lineHeight": "1.65",
            "fontStyle": "italic",
            "borderLeft": f"3px solid {THEME['primary_medium']}",
            "paddingLeft": "12px",
            "margin": "0 0 10px 0",
        }),
        html.Div(bottom_tags, style={"display": "flex", "flexWrap": "wrap"}),
    ])

    return [html.Div([header_row, desc_section], style={
        "padding": "16px 20px",
        "backgroundColor": "#f8f9fa",
        "borderRadius": "8px",
        "borderLeft": f"4px solid {THEME['primary_medium']}",
    })]


# ---------------------------------------------------------------------------
#  Callbacks
# ---------------------------------------------------------------------------

def setup_chat_with_callbacks(dash_app, story: Story):
    """Register all Chat With page callbacks."""
    from utils.profile_manager import ProfileManager
    from utils.chat_bot import CharacterChatBot

    manager = ProfileManager("data")

    # ── 0. Update model dropdown based on API key status ─────────────
    @dash_app.callback(
        Output("chat-model-selector", "options"),
        Output("chat-model-selector", "value"),
        Output("chat-no-apikey-warning", "children"),
        Input("openai-key-status", "data"),
        State("chat-model-selector", "value"),
    )
    def update_chat_model_options(key_status, current_model):
        configured = (key_status or {}).get("configured", False)
        new_options = _build_model_options(configured)
        # If the currently selected model is a GPT model and key is not set, fall back
        if not configured and current_model in Engine.GPT_MODELS:
            new_value = _DEFAULT_MODEL
        else:
            new_value = current_model or _DEFAULT_MODEL
        warning = "" if configured else "GPT models disabled — no API key configured."
        return new_options, new_value, warning

    # -- keep one bot instance alive between requests -----------------------
    _state = {
        "bot": None,
        "bot_config": {},
        "stream_buffer": "",
        "stream_done": True,
        "stream_error": None,
        "stream_name": "",
        "stream_thread": None,
    }

    def _stream_worker(bot, user_text):
        """Background thread: stream tokens from the bot into shared state."""
        try:
            for chunk in bot.stream(user_text):
                _state["stream_buffer"] += chunk
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            _state["stream_error"] = str(e)
        finally:
            _state["stream_done"] = True

    # ── 1. Cascade: role → seasons ────────────────────────────────────
    @dash_app.callback(
        Output("chat-season-selector", "options"),
        Output("chat-season-selector", "value"),
        Input("chat-role-selector", "value"),
    )
    def update_chat_seasons(role_id):
        if not role_id:
            return [], None

        available = []
        for season_num in range(1, 8):
            profiles = manager.get_profile_history(role_id, season_num)
            if profiles:
                available.append({"label": f"Season {season_num}", "value": season_num})

        return available, available[0]["value"] if available else None

    # ── 2. Cascade: role + season → episodes ──────────────────────────
    @dash_app.callback(
        Output("chat-episode-selector", "options"),
        Output("chat-episode-selector", "value"),
        Input("chat-season-selector", "value"),
        Input("chat-role-selector", "value"),
    )
    def update_chat_episodes(season_num, role_id):
        if not season_num or not role_id:
            return [], None

        profiles = manager.get_profile_history(role_id, season_num)
        episodes = [
            {"label": f"Episode {ep}", "value": ep}
            for ep, _ in profiles
        ]
        return episodes, episodes[0]["value"] if episodes else None

    # ── 3. Send message (button click OR Enter key) ───────────────────
    @dash_app.callback(
        Output("chat-messages", "children"),
        Output("chat-history", "data"),
        Output("chat-input", "value"),
        Output("chat-stream-interval", "disabled"),
        Output("chat-send-btn", "disabled"),
        Output("chat-input", "disabled"),
        Input("chat-send-btn", "n_clicks"),
        Input("chat-input", "n_submit"),
        State("chat-input", "value"),
        State("chat-history", "data"),
        State("chat-role-selector", "value"),
        State("chat-season-selector", "value"),
        State("chat-episode-selector", "value"),
        State("chat-topn-selector", "value"),
        State("chat-model-selector", "value"),
        prevent_initial_call=True,
    )
    def send_message(n_clicks, n_submit, user_text, history, role_id, season, episode, top_n, model):
        if not user_text or not user_text.strip():
            return no_update, no_update, no_update, no_update, no_update, no_update
        if not role_id or not season or not episode:
            return no_update, no_update, "", no_update, no_update, no_update

        # Ignore if already streaming
        if _state.get("stream_thread") and _state["stream_thread"].is_alive():
            return no_update, no_update, no_update, no_update, no_update, no_update

        user_text = user_text.strip()
        history = history or []

        # Detect config change → rebuild bot
        new_cfg = {
            "role_id": role_id,
            "season": season,
            "episode": episode,
            "top_n": top_n,
            "model": model,
        }
        if _state["bot"] is None or new_cfg != _state["bot_config"]:
            _state["bot"] = CharacterChatBot(
                season=season,
                episode=episode,
                role_id=role_id,
                story=story,
                top_n=top_n,
                model=model,
                data_root="data",
            )
            _state["bot_config"] = new_cfg
            # Config changed mid-conversation → wipe history
            history = []
            _state["bot"].reset()

        bot: CharacterChatBot = _state["bot"]
        char_name = bot.character_name

        # Append user message to history
        history.append({"role": "user", "content": user_text})

        # Initialize streaming state
        _state["stream_buffer"] = ""
        _state["stream_done"] = False
        _state["stream_error"] = None
        _state["stream_name"] = char_name

        # Start background streaming thread
        thread = threading.Thread(
            target=_stream_worker, args=(bot, user_text), daemon=True
        )
        _state["stream_thread"] = thread
        thread.start()

        # Show user message + loading indicator immediately
        rendered = _render_messages(history) + [_loading_indicator(char_name)]
        # Return: rendered, history (user msg only), clear input, enable interval, disable btn+input
        return rendered, history, "", False, True, True

    # ── 3b. Poll for streamed response tokens ─────────────────────────
    @dash_app.callback(
        Output("chat-messages", "children", allow_duplicate=True),
        Output("chat-history", "data", allow_duplicate=True),
        Output("chat-stream-interval", "disabled", allow_duplicate=True),
        Output("chat-send-btn", "disabled", allow_duplicate=True),
        Output("chat-input", "disabled", allow_duplicate=True),
        Input("chat-stream-interval", "n_intervals"),
        State("chat-history", "data"),
        prevent_initial_call=True,
    )
    def poll_stream(n_intervals, history):
        buffer = _state.get("stream_buffer", "")
        done = _state.get("stream_done", True)
        error = _state.get("stream_error")
        name = _state.get("stream_name", "Character")
        history = history or []

        if error:
            history.append({"role": "assistant", "content": f"[Error] {error}", "name": name})
            _state["stream_error"] = None
            return _render_messages(history), history, True, False, False

        if done:
            if not buffer:
                # Stale tick after streaming already committed
                return no_update, no_update, True, False, False
            history.append({"role": "assistant", "content": buffer, "name": name})
            return _render_messages(history), history, True, False, False

        # Still streaming
        if buffer:
            partial = history + [{"role": "assistant", "content": buffer + " ▌", "name": name}]
            return _render_messages(partial), no_update, no_update, no_update, no_update
        else:
            # No content yet — show loading animation
            rendered = _render_messages(history) + [_loading_indicator(name)]
            return rendered, no_update, no_update, no_update, no_update

    # ── 4. Update stored config whenever selectors change ─────────────
    @dash_app.callback(
        Output("chat-bot-config", "data"),
        Input("chat-role-selector", "value"),
        Input("chat-season-selector", "value"),
        Input("chat-episode-selector", "value"),
        Input("chat-topn-selector", "value"),
        Input("chat-model-selector", "value"),
    )
    def sync_bot_config(role_id, season, episode, top_n, model):
        return {
            "role_id": role_id,
            "season": season,
            "episode": episode,
            "top_n": top_n,
            "model": model,
        }

    # ── 5. Clear chat ─────────────────────────────────────────────────
    @dash_app.callback(
        Output("chat-messages", "children", allow_duplicate=True),
        Output("chat-history", "data", allow_duplicate=True),
        Output("chat-stream-interval", "disabled", allow_duplicate=True),
        Output("chat-send-btn", "disabled", allow_duplicate=True),
        Output("chat-input", "disabled", allow_duplicate=True),
        Input("chat-clear-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_chat(n_clicks):
        if _state["bot"]:
            _state["bot"].reset()
        _state["stream_buffer"] = ""
        _state["stream_done"] = True
        _state["stream_error"] = None
        return _render_messages([]), [], True, False, False

    # ── 6. Selector change → auto-clear history + refresh snapshot ────
    @dash_app.callback(
        Output("chat-snapshot-display", "children"),
        Output("chat-snapshot-episode-label", "children"),
        Output("chat-messages", "children", allow_duplicate=True),
        Output("chat-history", "data", allow_duplicate=True),
        Output("chat-stream-interval", "disabled", allow_duplicate=True),
        Output("chat-send-btn", "disabled", allow_duplicate=True),
        Output("chat-input", "disabled", allow_duplicate=True),
        Input("chat-role-selector", "value"),
        Input("chat-season-selector", "value"),
        Input("chat-episode-selector", "value"),
        prevent_initial_call=True,
    )
    def on_selector_change(role_id, season, episode):
        # Stop any active stream
        _state["stream_done"] = True
        _state["stream_buffer"] = ""
        _state["stream_error"] = None
        # Tear down bot — rebuild lazily on next message with new config
        _state["bot"] = None
        _state["bot_config"] = {}

        episode_label = ""
        snapshot_children = _render_snapshot(None)
        if role_id and season and episode:
            profile = manager.get_profile_at_episode(role_id, season, episode)
            snapshot_children = _render_snapshot(profile)
            episode_label = f"S{season}E{episode:02d}"

        return (
            snapshot_children,
            episode_label,
            _render_messages([]),
            [],
            True,
            False,
            False,
        )
