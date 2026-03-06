"""
Parser Control page — Dashboard UI to run the RoleParser agent.

Lets the user select Season / Episode / Role ID / Model via dropdowns,
shows high-level episode metadata, then fires the parser in a background
thread and polls for completion.
"""
import json
import logging
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dash import dcc, html, no_update
from dash import Input, Output, State
from dash_bootstrap_components import (
    Card, CardBody, CardHeader,
    Col, Container, Row,
)
from core.llm_engine import Engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme — deep-teal accent (distinguishes this page from the profile's slate)
# ---------------------------------------------------------------------------
THEME = {
    "sidebar_dark":  "#2c3e50",
    "card_header":   "#1a3a4a",
    "accent":        "#16a085",
    "accent_bright": "#1abc9c",
    "accent_dark":   "#0e6251",
    "success":       "#27ae60",
    "warning":       "#e67e22",
    "danger":        "#e74c3c",
    "info":          "#2980b9",
    "muted":         "#7f8c8d",
    "border":        "#dfe6e9",
    "bg_light":      "#f4f9f9",
    "text_dark":     "#1a252f",
    "text_muted":    "#555",
    "lightest":      "#d0eae4",
}

# ---------------------------------------------------------------------------
# Model manifest (mirrors Engine.ALL_MODELS)
# ---------------------------------------------------------------------------
_GPT_LABEL_SUFFIX = "  (requires OpenAI key)"
AVAILABLE_MODELS: List[Dict[str, str]] = [
    {"label": "GPT-4.1 Mini  (fast / recommended)", "value": "gpt-4.1-mini"},
    {"label": "GPT-4.1",                             "value": "gpt-4.1"},
    {"label": "GPT-4o",                              "value": "gpt-4o"},
    {"label": "GPT-5 Mini",                          "value": "gpt-5-mini"},
    {"label": "Qwen 2.5  (local)",                   "value": "qwen2.5:latest"},
    {"label": "Qwen 3 4B  (local)",                  "value": "qwen3:4B"},
    {"label": "Qwen 3 8B  (local)",                  "value": "qwen3:8B"},
]

_GPT_VALUES = {m["value"] for m in AVAILABLE_MODELS if m["value"] in Engine.GPT_MODELS}
_DEFAULT_PARSER_MODEL = "qwen2.5:latest"

def _build_parser_model_options(openai_configured: bool) -> List[Dict]:
    """Return model options with GPT entries disabled when no key is set."""
    result = []
    for opt in AVAILABLE_MODELS:
        if opt["value"] in _GPT_VALUES and not openai_configured:
            result.append({**opt, "label": opt["label"] + _GPT_LABEL_SUFFIX, "disabled": True})
        else:
            result.append(opt)
    return result

# Pipeline step metadata — in execution order
PIPELINE_STEPS: List[Dict[str, str]] = [
    {"key": "check_role_in_episode",  "label": "Check Role in Episode",
     "desc": "Verify the role_id appears in identifiers.json"},
    {"key": "check_first_appearance", "label": "First Appearance?",
     "desc": "Scan all prior episodes for an existing profile file"},
    {"key": "load_previous_profile",  "label": "Load Profile History",
     "desc": "Build a full snapshot from all prior delta files"},
    {"key": "parse_role",             "label": "LLM Parsing",
     "desc": "Ask the LLM to produce a RoleProfile or RoleDelta"},
    {"key": "save_delta",             "label": "Save to Disk",
     "desc": "Persist the result as roles/{role_id}.json"},
]

# ---------------------------------------------------------------------------
# Background job registry
# ---------------------------------------------------------------------------
_parse_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _run_parser_job(
    job_id: str,
    model: str,
    role_id: str,
    season: int,
    episode: int,
) -> None:
    """Target function for the background parser thread."""
    with _jobs_lock:
        _parse_jobs[job_id] = {"status": "running", "result": None, "error": None}
    try:
        from processors.role_profile_parser import RoleParser  # lazy import
        ep_data = RoleParser.load_episode_data(season, episode)
        parser = RoleParser(
            model=model,
            role_id=role_id,
            season=season,
            episode=episode,
        )
        result = parser.parse(**ep_data)
        with _jobs_lock:
            _parse_jobs[job_id] = {"status": "done", "result": result, "error": None}
    except Exception as exc:
        logger.exception("Parser job %s failed: %s", job_id, exc)
        with _jobs_lock:
            _parse_jobs[job_id] = {"status": "error", "result": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _get_seasons(data_dir: str = "data") -> List[int]:
    data_path = Path(data_dir)
    seasons: List[int] = []
    for d in sorted(data_path.iterdir()):
        if d.is_dir():
            m = re.match(r"^Season_(\d+)$", d.name)
            if m:
                seasons.append(int(m.group(1)))
    return seasons


def _get_episodes(season: int, data_dir: str = "data") -> List[Tuple[int, str]]:
    season_dir = Path(data_dir) / f"Season_{season}"
    if not season_dir.exists():
        return []
    pat = re.compile(rf"^S{season}E(\d+)_(.+)$")
    eps: List[Tuple[int, str]] = []
    for d in sorted(season_dir.iterdir()):
        m = pat.match(d.name)
        if m and d.is_dir():
            eps.append((int(m.group(1)), m.group(2).replace("_", " ")))
    return sorted(eps)


def _load_episode_info(
    season: int, episode: int, data_dir: str = "data"
) -> Optional[Dict[str, Any]]:
    data_path = Path(data_dir)
    pat = re.compile(rf"^S{season}E{episode:02d}_(.+)$")
    season_dir = data_path / f"Season_{season}"
    if not season_dir.exists():
        return None
    for ep_dir in season_dir.iterdir():
        m = pat.match(ep_dir.name)
        if not (m and ep_dir.is_dir()):
            continue
        info: Dict[str, Any] = {
            "name": m.group(1).replace("_", " "),
            "synopsis": "",
            "role_ids": [],
            "affiliations": [],
            "scene_count": 0,
            "parsed_roles": [],
        }
        synopsis_path = ep_dir / "synopsis.txt"
        if synopsis_path.exists():
            text = synopsis_path.read_text(encoding="utf-8").strip()
            info["synopsis"] = text[:600] + "…" if len(text) > 600 else text
        id_path = ep_dir / "identifiers.json"
        if id_path.exists():
            with open(id_path, "r", encoding="utf-8") as f:
                id_data = json.load(f)
            info["role_ids"] = id_data.get("role_ids", [])
            info["affiliations"] = id_data.get("affiliations", [])
        scenes_dir = ep_dir / "scenes"
        if scenes_dir.exists():
            info["scene_count"] = len(list(scenes_dir.glob("*.json")))
        roles_dir = ep_dir / "roles"
        if roles_dir.exists():
            info["parsed_roles"] = [f.stem for f in roles_dir.glob("*.json")]
        return info
    return None


# ---------------------------------------------------------------------------
# UI building blocks
# ---------------------------------------------------------------------------

def _stat_bubble(value: str, label: str, color: str) -> html.Div:
    return html.Div([
        html.Div(value, style={
            "fontSize": "28px", "fontWeight": "bold",
            "color": color, "lineHeight": "1",
        }),
        html.Div(label, style={
            "fontSize": "11px", "color": THEME["muted"],
            "textTransform": "uppercase", "letterSpacing": "0.5px",
            "marginTop": "3px",
        }),
    ], style={
        "textAlign": "center",
        "padding": "16px 20px",
        "borderRadius": "10px",
        "backgroundColor": THEME["bg_light"],
        "border": f"1px solid {THEME['border']}",
        "minWidth": "90px",
    })


def _role_badge(role_id: str, is_parsed: bool) -> html.Span:
    bg = THEME["accent_dark"] if is_parsed else "#bdc3c7"
    fg = "white" if is_parsed else THEME["text_dark"]
    icon = "✓ " if is_parsed else ""
    return html.Span(
        f"{icon}{role_id.replace('_', ' ').title()}",
        style={
            "backgroundColor": bg,
            "color": fg,
            "padding": "4px 12px",
            "borderRadius": "20px",
            "fontSize": "12px",
            "fontWeight": "500",
            "marginRight": "6px",
            "marginBottom": "6px",
            "display": "inline-block",
            "cursor": "default",
        },
        title="Already parsed" if is_parsed else "Not yet parsed",
    )


def _pipeline_step(step: Dict[str, str], status: str = "pending") -> html.Div:
    """
    status: 'pending' | 'running' | 'done' | 'skipped'
    """
    colors = {
        "pending": ("#ecf0f1", THEME["muted"], "○"),
        "running": ("#fef9e7", THEME["warning"], "◎"),
        "done":    ("#eafaf1", THEME["success"], "●"),
        "skipped": ("#f2f3f4", "#b2bec3", "—"),
    }
    bg, fg, icon = colors.get(status, colors["pending"])
    return html.Div([
        html.Div([
            html.Span(icon, style={"fontSize": "18px", "marginRight": "10px", "color": fg}),
            html.Div([
                html.Span(step["label"], style={
                    "fontWeight": "600", "fontSize": "13px", "color": fg,
                }),
                html.Div(step["desc"], style={
                    "fontSize": "11px", "color": THEME["muted"], "marginTop": "2px",
                }),
            ]),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={
        "backgroundColor": bg,
        "border": f"1px solid {THEME['border']}",
        "borderLeft": f"3px solid {fg}",
        "borderRadius": "6px",
        "padding": "10px 14px",
        "marginBottom": "8px",
        "transition": "all 0.3s",
    })


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

def create_parser_control_page(story=None) -> html.Div:
    """Return the top-level layout for the Parser Control page."""
    seasons = _get_seasons()
    season_options = [{"label": f"Season {s}", "value": s} for s in seasons]
    initial_season = seasons[0] if seasons else None

    return Container([
        # ── Page title ────────────────────────────────────────────────────
        html.Div([
            html.Div([
                html.H1("Parser Control", style={
                    "margin": "0", "color": "white",
                    "fontWeight": "bold", "fontSize": "28px",
                }),
                html.P(
                    "Run the RoleParser agent to generate or update a character profile "
                    "for any episode.",
                    style={
                        "margin": "6px 0 0 0", "color": THEME["lightest"],
                        "fontSize": "14px",
                    },
                ),
            ]),
            html.Div([
                html.Span("⚙", style={
                    "fontSize": "48px", "opacity": "0.3", "color": "white",
                }),
            ]),
        ], style={
            "background": f"linear-gradient(135deg, {THEME['card_header']} 0%, {THEME['accent_dark']} 100%)",
            "borderRadius": "12px",
            "padding": "28px 32px",
            "marginBottom": "24px",
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "boxShadow": "0 4px 16px rgba(0,0,0,0.15)",
        }),

        # ── Two-column body ───────────────────────────────────────────────
        Row([
            # ── LEFT column: config + controls ───────────────────────────
            Col([
                # Configuration card
                Card([
                    CardHeader([
                        html.Span("Configuration", style={
                            "fontWeight": "bold", "fontSize": "15px",
                        }),
                    ], style={
                        "backgroundColor": THEME["card_header"],
                        "color": "white",
                    }),
                    CardBody([
                        # Season
                        html.Label("Season", style={
                            "fontWeight": "600", "color": THEME["text_dark"],
                            "fontSize": "13px", "marginBottom": "4px",
                            "display": "block",
                        }),
                        dcc.Dropdown(
                            id="pc-season",
                            options=season_options,
                            value=initial_season,
                            clearable=False,
                            style={"marginBottom": "16px"},
                        ),
                        # Episode
                        html.Label("Episode", style={
                            "fontWeight": "600", "color": THEME["text_dark"],
                            "fontSize": "13px", "marginBottom": "4px",
                            "display": "block",
                        }),
                        dcc.Dropdown(
                            id="pc-episode",
                            options=[],
                            value=None,
                            clearable=False,
                            style={"marginBottom": "16px"},
                        ),
                        # Role ID
                        html.Label("Character (Role ID)", style={
                            "fontWeight": "600", "color": THEME["text_dark"],
                            "fontSize": "13px", "marginBottom": "4px",
                            "display": "block",
                        }),
                        dcc.Dropdown(
                            id="pc-role",
                            options=[],
                            value=None,
                            clearable=False,
                            style={"marginBottom": "16px"},
                            placeholder="Select an episode first…",
                        ),
                        # Model
                        html.Label("LLM Model", style={
                            "fontWeight": "600", "color": THEME["text_dark"],
                            "fontSize": "13px", "marginBottom": "4px",
                            "display": "block",
                        }),
                        dcc.Dropdown(
                            id="pc-model",
                            options=AVAILABLE_MODELS,
                            value="gpt-4.1-mini",
                            clearable=False,
                            style={"marginBottom": "4px"},
                        ),
                        html.Div(
                            id="pc-no-apikey-warning",
                            children="",
                            style={"fontSize": "11px", "color": "#e67e22", "marginBottom": "8px"},
                        ),
                    ], style={"padding": "20px"}),
                ], style={"marginBottom": "16px", "boxShadow": "0 2px 8px rgba(0,0,0,0.08)"}),

                # Quick stats card
                Card([
                    CardHeader("Episode Stats", style={
                        "backgroundColor": THEME["card_header"],
                        "color": "white", "fontWeight": "bold",
                        "fontSize": "14px",
                    }),
                    CardBody(
                        html.Div(id="pc-episode-stats",
                                 children=_placeholder_stats()),
                        style={"padding": "16px"},
                    ),
                ], style={"marginBottom": "16px", "boxShadow": "0 2px 8px rgba(0,0,0,0.08)"}),

                # Parse action card
                Card([
                    CardHeader("Run Parser", style={
                        "backgroundColor": THEME["accent_dark"],
                        "color": "white", "fontWeight": "bold",
                        "fontSize": "14px",
                    }),
                    CardBody([
                        html.P([
                            html.Strong("Note: "),
                            "Parsing is performed by an LLM and may take up to a "
                            "minute for large episodes.",
                        ], style={"fontSize": "12px", "color": THEME["text_muted"],
                                  "marginBottom": "16px"}),
                        html.Button(
                            [html.Span("▶  "), "Run Parser"],
                            id="pc-run-btn",
                            n_clicks=0,
                            disabled=True,
                            style={
                                "width": "100%",
                                "padding": "14px",
                                "backgroundColor": THEME["accent"],
                                "color": "white",
                                "border": "none",
                                "borderRadius": "8px",
                                "fontSize": "16px",
                                "fontWeight": "bold",
                                "cursor": "pointer",
                                "transition": "background-color 0.2s",
                                "letterSpacing": "0.5px",
                            },
                        ),
                        html.Div(id="pc-run-status", style={"marginTop": "12px"}),
                    ], style={"padding": "20px"}),
                ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.08)"}),
            ], md=4),

            # ── RIGHT column: info + pipeline + results ───────────────────
            Col([
                # Episode info card
                Card([
                    CardHeader([
                        html.Span(id="pc-ep-title", children="Episode Information"),
                    ], style={
                        "backgroundColor": THEME["card_header"],
                        "color": "white", "fontWeight": "bold",
                        "fontSize": "15px",
                    }),
                    CardBody(
                        html.Div(id="pc-episode-info",
                                 children=_placeholder_episode_info()),
                        style={"padding": "20px"},
                    ),
                ], style={"marginBottom": "16px", "boxShadow": "0 2px 8px rgba(0,0,0,0.08)"}),

                # Characters in episode
                Card([
                    CardHeader("Characters in This Episode", style={
                        "backgroundColor": THEME["card_header"],
                        "color": "white", "fontWeight": "bold",
                        "fontSize": "14px",
                    }),
                    CardBody(
                        html.Div(id="pc-role-badges",
                                 children=html.P("Select an episode to see characters.",
                                                 style={"color": THEME["muted"],
                                                        "fontStyle": "italic",
                                                        "margin": "0"})),
                        style={"padding": "16px"},
                    ),
                ], style={"marginBottom": "16px", "boxShadow": "0 2px 8px rgba(0,0,0,0.08)"}),

                # Parser pipeline visualization
                Card([
                    CardHeader("Parser Pipeline", style={
                        "backgroundColor": THEME["card_header"],
                        "color": "white", "fontWeight": "bold",
                        "fontSize": "14px",
                    }),
                    CardBody(
                        html.Div(id="pc-pipeline",
                                 children=[_pipeline_step(s) for s in PIPELINE_STEPS]),
                        style={"padding": "16px"},
                    ),
                ], style={"marginBottom": "16px", "boxShadow": "0 2px 8px rgba(0,0,0,0.08)"}),

                # Results
                html.Div(id="pc-results"),
            ], md=8),
        ]),

        # ── Hidden state / polling machinery ─────────────────────────────
        dcc.Store(id="pc-job-id", data=None),
        dcc.Interval(id="pc-poll", interval=1500, n_intervals=0, disabled=True),

        html.Footer(
            html.P("RoleParser Control — Agents of S.H.I.E.L.D.",
                   style={"textAlign": "center", "color": THEME["muted"],
                          "marginTop": "30px", "fontSize": "12px"}),
            style={"marginTop": "40px"},
        ),
    ], fluid=True, style={"padding": "20px", "backgroundColor": "#f8fafb", "minHeight": "100vh"})


# ---------------------------------------------------------------------------
# Placeholder helpers
# ---------------------------------------------------------------------------

def _placeholder_stats() -> html.Div:
    return html.P(
        "Select season + episode to see stats.",
        style={"color": THEME["muted"], "fontStyle": "italic", "margin": "0",
               "fontSize": "13px"},
    )


def _placeholder_episode_info() -> html.P:
    return html.P(
        "Select a season and episode from the left panel.",
        style={"color": THEME["muted"], "fontStyle": "italic", "margin": "0"},
    )


# ---------------------------------------------------------------------------
# Results rendering
# ---------------------------------------------------------------------------

def _render_result(state: Dict[str, Any], role_id: str) -> html.Div:
    """Render the parser result state into a Card."""
    is_in_ep = state.get("is_role_in_episode", False)
    is_first  = state.get("is_first_appearance", False)
    delta     = state.get("parsed_delta", {})

    if not is_in_ep:
        return Card([
            CardHeader("⚠ Role Not Found in Episode", style={
                "backgroundColor": THEME["warning"],
                "color": "white", "fontWeight": "bold",
            }),
            CardBody(
                html.P(
                    f"'{role_id}' is not listed in this episode's identifiers.json. "
                    "Nothing was saved. Check the role_id spelling or choose a "
                    "different episode.",
                    style={"margin": "0"},
                ),
                style={"padding": "20px"},
            ),
        ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"})

    profile_type = "RoleProfile (first appearance)" if is_first else "RoleDelta (update)"
    badge_bg = THEME["info"] if is_first else THEME["accent"]

    rows = [
        ("Profile type", profile_type),
        ("Season / Episode", f"S{state['timestamp']['season']}E{state['timestamp']['episode']:02d}"),
        ("Role ID", delta.get("role_id", role_id)),
        ("First name", delta.get("first_name", "—")),
        ("Last name", delta.get("last_name") or "—"),
        ("Aliases", ", ".join(delta.get("aliases", [])) or "—"),
        ("Affiliations", ", ".join(
            delta.get("demographics", {}).get("affiliation", [])
        ) or "—") if is_first else
        ("Delta fields changed", str(len([k for k, v in delta.items()
                                          if v and k not in
                                          ("timestamp", "role_id")
                                          ])) + " field(s)"),
    ]

    table_rows = []
    for label, value in rows:
        table_rows.append(html.Tr([
            html.Td(label, style={
                "fontWeight": "600", "color": THEME["text_dark"],
                "padding": "8px 12px", "whiteSpace": "nowrap",
                "fontSize": "13px",
            }),
            html.Td(value, style={
                "color": THEME["text_muted"], "padding": "8px 12px",
                "fontSize": "13px",
            }),
        ]))

    return Card([
        CardHeader([
            html.Span("✓  Parse Complete — "),
            html.Span(profile_type, style={
                "backgroundColor": badge_bg,
                "padding": "2px 10px",
                "borderRadius": "12px",
                "fontSize": "12px",
                "marginLeft": "8px",
            }),
        ], style={
            "backgroundColor": THEME["success"],
            "color": "white", "fontWeight": "bold", "fontSize": "14px",
        }),
        CardBody([
            html.Table(
                table_rows,
                style={"width": "100%", "borderCollapse": "collapse"},
            ),
            html.Hr(style={"margin": "16px 0"}),
            html.Details([
                html.Summary("View raw parsed delta JSON",
                             style={"cursor": "pointer", "fontWeight": "600",
                                    "fontSize": "13px", "color": THEME["accent_dark"]}),
                html.Pre(
                    json.dumps(delta, indent=2, ensure_ascii=False),
                    style={
                        "backgroundColor": "#f4f4f4",
                        "borderRadius": "6px",
                        "padding": "12px",
                        "fontSize": "11px",
                        "overflowX": "auto",
                        "maxHeight": "320px",
                        "marginTop": "8px",
                        "lineHeight": "1.5",
                    },
                ),
            ]),
        ], style={"padding": "20px"}),
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"})


def _render_error(error_msg: str) -> html.Div:
    return Card([
        CardHeader("✗  Parser Error", style={
            "backgroundColor": THEME["danger"],
            "color": "white", "fontWeight": "bold",
        }),
        CardBody(
            html.Pre(error_msg, style={
                "margin": "0", "whiteSpace": "pre-wrap",
                "fontSize": "12px", "color": THEME["danger"],
            }),
            style={"padding": "20px"},
        ),
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,0.1)"})


# ---------------------------------------------------------------------------
# Callback setup
# ---------------------------------------------------------------------------

def setup_parser_control_callbacks(dash_app, story=None):
    """Register all parser-control callbacks on *dash_app*."""

    # ── 0. Update model dropdown based on API key status ─────────────────
    @dash_app.callback(
        Output("pc-model", "options"),
        Output("pc-model", "value"),
        Output("pc-no-apikey-warning", "children"),
        Input("openai-key-status", "data"),
        State("pc-model", "value"),
    )
    def update_parser_model_options(key_status, current_model):
        configured = (key_status or {}).get("configured", False)
        new_options = _build_parser_model_options(configured)
        if not configured and current_model in _GPT_VALUES:
            new_value = _DEFAULT_PARSER_MODEL
        else:
            new_value = current_model or _DEFAULT_PARSER_MODEL
        warning = "" if configured else "GPT models disabled \u2014 no API key configured."
        return new_options, new_value, warning

    # ── 1. Episode dropdown: updates when season changes ─────────────────
    @dash_app.callback(
        Output("pc-episode", "options"),
        Output("pc-episode", "value"),
        Input("pc-season", "value"),
    )
    def update_episodes(season):
        if season is None:
            return [], None
        eps = _get_episodes(season)
        options = [{"label": f"E{num:02d} — {name}", "value": num}
                   for num, name in eps]
        first = options[0]["value"] if options else None
        return options, first

    # ── 2. Episode info + role options: updates when season/episode change ─
    @dash_app.callback(
        Output("pc-ep-title",      "children"),
        Output("pc-episode-info",  "children"),
        Output("pc-episode-stats", "children"),
        Output("pc-role-badges",   "children"),
        Output("pc-role",          "options"),
        Output("pc-role",          "value"),
        Output("pc-run-btn",       "disabled"),
        Input("pc-season",  "value"),
        Input("pc-episode", "value"),
        Input("pc-role",    "value"),
    )
    def update_episode_info(season, episode, current_role):
        if season is None or episode is None:
            return (
                "Episode Information",
                _placeholder_episode_info(),
                _placeholder_stats(),
                html.P("Select an episode to see characters.",
                       style={"color": THEME["muted"], "fontStyle": "italic",
                              "margin": "0"}),
                [], None, True,
            )

        info = _load_episode_info(season, episode)
        if info is None:
            return (
                "Episode Not Found",
                html.P("Could not load episode data.",
                       style={"color": THEME["danger"]}),
                _placeholder_stats(),
                html.P("—"), [], None, True,
            )

        # Title
        title = f"S{season}E{episode:02d} — {info['name']}"

        # Synopsis block
        synopsis_el = html.Div([
            html.H5("Synopsis", style={
                "fontWeight": "bold", "color": THEME["text_dark"],
                "marginBottom": "8px", "fontSize": "14px",
            }),
            html.P(info["synopsis"] or "(no synopsis available)",
                   style={
                       "color": THEME["text_muted"], "lineHeight": "1.7",
                       "fontSize": "13px", "margin": "0",
                   }),
        ])

        # Affiliations
        affil_el = html.Div([])
        if info["affiliations"]:
            affil_el = html.Div([
                html.H5("Affiliations", style={
                    "fontWeight": "bold", "color": THEME["text_dark"],
                    "marginTop": "16px", "marginBottom": "8px",
                    "fontSize": "14px",
                }),
                html.Div([
                    html.Span(a, style={
                        "backgroundColor": THEME["lightest"],
                        "color": THEME["accent_dark"],
                        "padding": "3px 10px",
                        "borderRadius": "12px",
                        "fontSize": "11px",
                        "fontWeight": "500",
                        "marginRight": "6px",
                        "marginBottom": "4px",
                        "display": "inline-block",
                    }) for a in info["affiliations"]
                ]),
            ])

        episode_info_el = html.Div([synopsis_el, affil_el])

        # Stats bubbles
        n_roles   = len(info["role_ids"])
        n_scenes  = info["scene_count"]
        n_parsed  = len(info["parsed_roles"])
        stats_el  = html.Div([
            _stat_bubble(str(n_roles),  "Characters", THEME["accent"]),
            _stat_bubble(str(n_scenes), "Scenes",     THEME["info"]),
            _stat_bubble(str(n_parsed), "Parsed",     THEME["success"]),
        ], style={"display": "flex", "gap": "10px", "flexWrap": "wrap"})

        # Role badges
        badges = [
            _role_badge(r, r in info["parsed_roles"])
            for r in info["role_ids"]
        ] if info["role_ids"] else [
            html.P("No roles listed in identifiers.json.",
                   style={"color": THEME["muted"], "fontStyle": "italic",
                          "margin": "0", "fontSize": "13px"}),
        ]
        badges_el = html.Div(badges)

        # Role dropdown options
        role_options = [
            {"label": r.replace("_", " ").title(), "value": r}
            for r in info["role_ids"]
        ]
        # keep current role if it's still valid
        new_role = (
            current_role if current_role in info["role_ids"]
            else (role_options[0]["value"] if role_options else None)
        )
        btn_disabled = new_role is None

        return (
            title, episode_info_el, stats_el, badges_el,
            role_options, new_role, btn_disabled,
        )

    # ── 3. Launch parser, store job ID, start interval ───────────────────
    @dash_app.callback(
        Output("pc-job-id",    "data"),
        Output("pc-poll",      "disabled"),
        Output("pc-run-btn",   "disabled", allow_duplicate=True),
        Output("pc-run-status","children"),
        Input("pc-run-btn", "n_clicks"),
        State("pc-season",  "value"),
        State("pc-episode", "value"),
        State("pc-role",    "value"),
        State("pc-model",   "value"),
        prevent_initial_call=True,
    )
    def launch_parser(n_clicks, season, episode, role_id, model):
        if not n_clicks or None in (season, episode, role_id, model):
            return no_update, no_update, no_update, no_update

        job_id = str(uuid.uuid4())
        t = threading.Thread(
            target=_run_parser_job,
            args=(job_id, model, role_id, season, episode),
            daemon=True,
        )
        t.start()
        logger.info("Parser job %s started: S%sE%02d %s (%s)",
                    job_id, season, episode, role_id, model)

        status_el = html.Div([
            html.Span("⏳  Running…", style={
                "color": THEME["warning"], "fontWeight": "bold",
                "fontSize": "13px",
            }),
            html.Div(
                f"Model: {model}",
                style={"fontSize": "11px", "color": THEME["muted"],
                       "marginTop": "4px"},
            ),
        ])
        return job_id, False, True, status_el

    # ── 4. Poll for completion ────────────────────────────────────────────
    @dash_app.callback(
        Output("pc-pipeline",    "children"),
        Output("pc-results",     "children"),
        Output("pc-poll",        "disabled", allow_duplicate=True),
        Output("pc-run-btn",     "disabled", allow_duplicate=True),
        Output("pc-run-status",  "children", allow_duplicate=True),
        Input("pc-poll",  "n_intervals"),
        State("pc-job-id", "data"),
        State("pc-role",   "value"),
        prevent_initial_call=True,
    )
    def poll_job(n_intervals, job_id, role_id):
        if not job_id:
            return no_update, no_update, no_update, no_update, no_update

        with _jobs_lock:
            job = _parse_jobs.get(job_id)

        if job is None or job["status"] == "running":
            # Still running — animate pipeline steps
            pipeline_el = _animated_pipeline()
            return pipeline_el, no_update, False, True, no_update

        # Job finished
        if job["status"] == "error":
            pipeline_el = [_pipeline_step(s, "done") for s in PIPELINE_STEPS]
            results_el  = _render_error(job["error"] or "Unknown error")
            status_el   = html.Span("✗  Failed",
                                    style={"color": THEME["danger"],
                                           "fontWeight": "bold"})
            return pipeline_el, results_el, True, False, status_el

        # success
        state = job["result"]
        pipeline_el = _build_pipeline_from_state(state)
        results_el  = _render_result(state, role_id or "")
        status_el   = html.Span("✓  Done",
                                style={"color": THEME["success"],
                                       "fontWeight": "bold"})
        return pipeline_el, results_el, True, False, status_el


def _animated_pipeline() -> list:
    """Return pipeline steps with 'running' shown on the LLM step."""
    steps = []
    for i, s in enumerate(PIPELINE_STEPS):
        # Visually highlight the 'parse_role' step as running
        status = "running" if s["key"] == "parse_role" else (
            "done" if i < 3 else "pending"
        )
        steps.append(_pipeline_step(s, status))
    return steps


def _build_pipeline_from_state(state: Dict[str, Any]) -> list:
    """Derive step statuses from the final parser state."""
    in_ep   = state.get("is_role_in_episode", False)
    is_first = state.get("is_first_appearance", False)
    has_delta = bool(state.get("parsed_delta"))

    statuses = {
        "check_role_in_episode":  "done",
        "check_first_appearance": "done" if in_ep else "skipped",
        "load_previous_profile":  (
            "done" if (in_ep and not is_first)
            else ("skipped" if (in_ep and is_first) else "skipped")
        ),
        "parse_role":  "done" if (in_ep and has_delta) else (
            "skipped" if not in_ep else "pending"
        ),
        "save_delta":  "done" if (in_ep and has_delta) else (
            "skipped" if not in_ep else "pending"
        ),
    }
    return [_pipeline_step(s, statuses[s["key"]]) for s in PIPELINE_STEPS]
