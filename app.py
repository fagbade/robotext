"""
Cheda — FGI Operational Results Dashboard (Dash version)
Run with: python app.py
"""

import os
import dash
from dash import html, dcc, Input, Output, State, ctx, no_update
import dash_bootstrap_components as dbc
from datetime import date
import flask
from werkzeug.security import check_password_hash

from components.theme import NAVY, NAVY_LIGHT, EMERALD, GRAY_400, GRAY_500, WHITE

TODAY = date(2026, 3, 2)
TODAY_STR = TODAY.isoformat()

# Admin credentials (change password by regenerating the hash)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$D3kZy0kJXVVlI5Qu$0d3654f49bfc52dc1d9535b6642a230a55ca5f6373b8b7322ee908c3b1d126f32bc27a2061e43d83fef84271ea5348238d1566b161718b3ebbbfb77d48e86b60"

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Cheda \u2014 FGI Operational Results",
    update_title=None,
)
server = app.server
server.secret_key = os.environ.get("SECRET_KEY", "cheda-fgi-dev-key")

# Pre-render default page
from pages.executive_impact import build_layout as _build_exec
_default_content = _build_exec("2025-01-01", TODAY_STR, "NGN")

# ── Login form layout ──────────────────────────────────────────────
login_layout = html.Div(className="login-wrapper", children=[
    html.Div(className="login-card", children=[
        html.Img(src="/assets/cheda_logo.png", style={
            "height": "56px", "width": "56px", "borderRadius": "10px", "marginBottom": "16px",
        }),
        html.H2("Cheda", style={"color": WHITE, "fontWeight": 700, "marginBottom": "4px"}),
        html.P("Admin Portal", style={"color": GRAY_400, "fontSize": "0.9rem", "marginBottom": "28px"}),
        dcc.Input(id="login-username", type="text", placeholder="Username",
                  className="login-input", n_submit=0),
        dcc.Input(id="login-password", type="password", placeholder="Password",
                  className="login-input", n_submit=0),
        html.Button("Sign In", id="login-button", className="login-button", n_clicks=0),
        html.Div(id="login-error", className="login-error"),
    ]),
])

# ── Navbar ──────────────────────────────────────────────────────────
navbar = html.Div(className="navbar-custom", children=[
    html.Div(style={"display": "flex", "alignItems": "center"}, children=[
        html.Img(src="/assets/cheda_logo.png", style={
            "height": "36px", "width": "36px", "borderRadius": "6px", "marginRight": "10px",
        }),
        html.Span("Cheda", className="navbar-brand-text"),
        html.Span("FGI Operational Results", className="navbar-brand-sub"),
    ]),
    html.Div(style={"display": "flex", "alignItems": "center", "gap": "4px"}, children=[
        html.A("Performance Overview", href="#", id="nav-executive",
               className="nav-link-custom active", n_clicks=0),
        html.A("Operations & Compliance", href="#", id="nav-operations",
               className="nav-link-custom", n_clicks=0),
        html.A("Graph Explorer", href="#", id="nav-graph",
               className="nav-link-custom", n_clicks=0),
        html.Div(style={"marginLeft": "16px", "display": "flex", "alignItems": "center", "gap": "10px"}, children=[
            html.Div(style={
                "width": "34px", "height": "34px", "borderRadius": "50%",
                "background": "linear-gradient(135deg, #10B981 0%, #059669 100%)",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "cursor": "pointer", "border": "2px solid rgba(255,255,255,0.2)",
            }, children=[
                html.Span("TA", style={
                    "color": "#FFFFFF", "fontSize": "0.75rem", "fontWeight": 700,
                    "letterSpacing": "0.02em",
                }),
            ]),
            html.Button("⏻", id="logout-button", className="logout-icon-button", title="Logout", n_clicks=0),
        ]),
    ]),
])

# ── Sidebar ─────────────────────────────────────────────────────────
sidebar = html.Div(className="filter-panel", children=[
    html.Div("Start Date", className="filter-label"),
    dcc.DatePickerSingle(
        id="date-picker-start",
        date="2025-01-01",
        min_date_allowed="2025-01-01",
        max_date_allowed=TODAY_STR,
        display_format="MMM D, YYYY",
        className="sidebar-date-picker",
    ),
    html.Div("End Date", className="filter-label", style={"marginTop": "14px"}),
    dcc.DatePickerSingle(
        id="date-picker-end",
        date=TODAY_STR,
        min_date_allowed="2025-01-01",
        max_date_allowed=TODAY_STR,
        display_format="MMM D, YYYY",
        className="sidebar-date-picker",
    ),
    # Hidden individual stores for backward compat with page callbacks
    dcc.Store(id="date-start-store", data="2025-01-01"),
    dcc.Store(id="date-end-store", data=TODAY_STR),

    # Currency toggle
    html.Div("Currency", className="filter-label", style={"marginTop": "14px"}),
    html.Div(className="currency-toggle", children=[
        html.Button("NGN", id="currency-ngn-btn", className="currency-btn active", n_clicks=0),
        html.Button("USD", id="currency-usd-btn", className="currency-btn", n_clicks=0),
    ]),

    html.Div(
        "All entity IDs are SHA-256 hashed.",
        style={"fontSize": "0.72rem", "color": GRAY_500, "marginTop": "12px"},
    ),
])

# ── Dashboard layout (shown after login) ───────────────────────────
dashboard_layout = html.Div([
    navbar,
    html.Div(className="container-fluid", style={"padding": "24px 32px", "maxWidth": "1440px"}, children=[
        html.Div(className="row g-4", children=[
            html.Div(className="col-md-2", children=[sidebar]),
            html.Div(className="col-md-10", children=[
                html.Div(id="page-content", children=_default_content),
            ]),
        ]),
        html.Div(
            "Cheda \u00b7 FGI Operational Results \u00b7 Powered by Federated Graph Intelligence",
            className="footer-text",
        ),
    ]),
])

# ── Layout ──────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Store(id="auth-store", data=False),
    dcc.Store(id="current-page", data="executive"),
    dcc.Store(id="currency-store", data="NGN"),
    # Dummy hidden inputs for backward compat
    html.Div(style={"display": "none"}, children=[
        dcc.Input(id="date-start", value="2025-01-01"),
        dcc.Input(id="date-end", value=TODAY_STR),
    ]),
    html.Div(id="app-container"),
])

# ── Sync date pickers to hidden stores ─────────────────────────────
@app.callback(
    Output("date-start", "value"),
    Output("date-end", "value"),
    Input("date-picker-start", "date"),
    Input("date-picker-end", "date"),
)
def sync_dates(start, end):
    return start or "2025-01-01", end or TODAY_STR


# ── Auth check on page load ────────────────────────────────────────
@app.callback(
    Output("auth-store", "data"),
    Input("app-container", "id"),
)
def check_auth(_):
    return flask.session.get("logged_in", False)


# ── Render login or dashboard based on auth state ──────────────────
@app.callback(
    Output("app-container", "children"),
    Input("auth-store", "data"),
)
def render_app_container(is_logged_in):
    if is_logged_in:
        return dashboard_layout
    return login_layout


# ── Login callback ─────────────────────────────────────────────────
@app.callback(
    Output("auth-store", "data", allow_duplicate=True),
    Output("login-error", "children"),
    Input("login-button", "n_clicks"),
    Input("login-username", "n_submit"),
    Input("login-password", "n_submit"),
    State("login-username", "value"),
    State("login-password", "value"),
    prevent_initial_call=True,
)
def login(n_clicks, n_sub_user, n_sub_pass, username, password):
    if not username or not password:
        return no_update, "Please enter both username and password."
    if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
        flask.session["logged_in"] = True
        return True, ""
    return no_update, "Invalid username or password."


# ── Logout callback ────────────────────────────────────────────────
@app.callback(
    Output("auth-store", "data", allow_duplicate=True),
    Input("logout-button", "n_clicks"),
    prevent_initial_call=True,
)
def logout(n_clicks):
    if n_clicks:
        flask.session.clear()
        return False
    return no_update


# ── Navigation ──────────────────────────────────────────────────────
@app.callback(
    Output("current-page", "data"),
    Output("nav-executive", "className"),
    Output("nav-operations", "className"),
    Output("nav-graph", "className"),
    Input("nav-executive", "n_clicks"),
    Input("nav-operations", "n_clicks"),
    Input("nav-graph", "n_clicks"),
    prevent_initial_call=True,
)
def navigate(n_exec, n_ops, n_graph):
    triggered = ctx.triggered_id
    active = "nav-link-custom active"
    inactive = "nav-link-custom"
    if triggered == "nav-operations":
        return "operations", inactive, active, inactive
    elif triggered == "nav-graph":
        return "graph", inactive, inactive, active
    return "executive", active, inactive, inactive


@app.callback(
    Output("currency-store", "data"),
    Output("currency-ngn-btn", "className"),
    Output("currency-usd-btn", "className"),
    Input("currency-ngn-btn", "n_clicks"),
    Input("currency-usd-btn", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_currency(n_ngn, n_usd):
    triggered = ctx.triggered_id
    if triggered == "currency-usd-btn":
        return "USD", "currency-btn", "currency-btn active"
    return "NGN", "currency-btn active", "currency-btn"


@app.callback(
    Output("page-content", "children"),
    Input("current-page", "data"),
    Input("date-start", "value"),
    Input("date-end", "value"),
    Input("currency-store", "data"),
)
def render_page(page, date_start, date_end, currency):
    currency = currency or "NGN"
    if not date_start or not date_end:
        return html.Div("Please select a valid date range.")
    if page == "operations":
        from pages.operations_compliance import build_layout
        return build_layout(date_start, date_end, currency)
    elif page == "graph":
        from pages.graph_explorer import build_layout
        return build_layout(date_start, date_end, currency)
    else:
        from pages.executive_impact import build_layout
        return build_layout(date_start, date_end, currency)


# ── Register callbacks ──────────────────────────────────────────────
from pages.operations_compliance import register_callbacks as register_ops_callbacks
from pages.graph_explorer import register_callbacks as register_graph_callbacks

register_ops_callbacks(app)
register_graph_callbacks(app)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    print("\n  Cheda - FGI Operational Results Dashboard")
    print(f"  http://127.0.0.1:{port}\n")
    app.run(debug=False, host="0.0.0.0", port=port)
