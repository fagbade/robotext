"""
Page 1 — Performance Overview (hashed IDs)
KPI cards, fraud prevention trends, alert funnel, risk signals, customer guardrail.
All charts show full date range so the mid-June deployment leap is visible.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import html, dcc

from components.data_loader import load_payouts, load_alerts, load_federation
from components.theme import (
    PLOTLY_LAYOUT, NAVY, NAVY_LIGHT, EMERALD, EMERALD_DARK, RED, AMBER, BLUE,
    GRAY_200, GRAY_400, GRAY_500, WHITE, CRYPTO_COLORS,
)

DEPLOY_DATE = pd.Timestamp("2025-06-15")


def _kpi_card(label: str, value: str) -> html.Div:
    return html.Div(className="kpi-card", children=[
        html.Div(value, className="kpi-value"),
        html.Div(label, className="kpi-label"),
    ])


def _operational_banner() -> html.Div:
    """Operational status banner with days since deploy and federation client ID."""
    today = pd.Timestamp("2026-03-02")
    days_live = (today - DEPLOY_DATE).days

    # Get primary federation client ID
    try:
        fed = load_federation()
        primary_client = fed["client_id"].value_counts().index[0]
    except Exception:
        primary_client = "n/a"

    items = [
        ("System Status", html.Span("\u25CF Operational", style={
            "fontSize": "1.1rem", "fontWeight": 600, "color": EMERALD})),
        ("Production Since", html.Span(f"{days_live} days", style={
            "fontSize": "1.1rem", "fontWeight": 600, "color": WHITE})),
        ("Model Version", html.Span("v2.2.1", style={
            "fontSize": "1.1rem", "fontWeight": 600, "color": WHITE})),
        ("Federation Client ID", html.Span(primary_client[:10] + "...", style={
            "fontSize": "1.1rem", "fontWeight": 600, "color": WHITE})),
    ]

    children = []
    for title, value_el in items:
        children.append(html.Div(style={"textAlign": "center"}, children=[
            html.Div(title, style={
                "fontSize": "0.82rem", "fontWeight": 600, "textTransform": "uppercase",
                "letterSpacing": "0.06em", "color": GRAY_400, "marginBottom": "4px",
            }),
            value_el,
        ]))

    return html.Div(className="timeline-banner", children=[
        html.Div(style={
            "display": "flex", "alignItems": "center", "justifyContent": "space-between",
            "flexWrap": "wrap", "gap": "24px",
        }, children=children),
    ])


def _add_deploy_line(fig):
    """Add deployment vertical line to any time-series figure."""
    fig.add_vline(
        x=DEPLOY_DATE.timestamp() * 1000,
        line_dash="dash", line_color=EMERALD, line_width=1.5,
        annotation_text="Deployed", annotation_position="top",
        annotation_font_color=EMERALD, annotation_font_size=10,
    )


NGN_TO_USD = 1 / 1479


def build_layout(date_start: str, date_end: str, currency: str = "NGN") -> html.Div:
    if currency == "USD":
        symbol, tickpfx, divisor = "$", "$", NGN_TO_USD
    else:
        symbol, tickpfx, divisor = "₦", "₦", 1

    payouts = load_payouts()
    alerts = load_alerts()

    mask_p = (payouts["event_ts"].dt.date >= pd.Timestamp(date_start).date()) & \
             (payouts["event_ts"].dt.date <= pd.Timestamp(date_end).date())
    df = payouts[mask_p].copy()

    mask_a = (alerts["created_at"].dt.date >= pd.Timestamp(date_start).date()) & \
             (alerts["created_at"].dt.date <= pd.Timestamp(date_end).date())
    alt = alerts[mask_a].copy()

    # ── KPI calculations ────────────────────────────────────────────
    blocked = df[df["decision"].isin(["BLOCK", "HOLD"])]
    fraud_prevented = blocked[blocked["confirmed_bad"]]["amount_ngn"].sum()
    confirmed_blocked = int(blocked["confirmed_bad"].sum())

    total_blocked = len(blocked)
    fp_count = total_blocked - confirmed_blocked
    fp_rate = (fp_count / total_blocked * 100) if total_blocked > 0 else 0

    allowed = df[df["decision"] == "ALLOW"]
    legit_success = (
        (len(allowed) - allowed["confirmed_bad"].sum()) / len(allowed) * 100
        if len(allowed) > 0 else 0
    )

    p95_latency = df[df["latency_ms"] > 0]["latency_ms"].quantile(0.95) if len(df[df["latency_ms"] > 0]) > 0 else 0

    # ── Charts ──────────────────────────────────────────────────────
    # 1) Monthly fraud prevented
    monthly = (
        blocked[blocked["confirmed_bad"]]
        .set_index("event_ts")
        .resample("ME")["amount_ngn"]
        .sum()
        .reset_index()
    )
    monthly.columns = ["month", "amount_ngn"]
    monthly["amount_ngn"] = monthly["amount_ngn"] * divisor

    fig_monthly = px.line(
        monthly, x="month", y="amount_ngn", markers=True,
        labels={"month": "", "amount_ngn": f"Amount ({currency})"},
    )
    fig_monthly.update_traces(line_color=EMERALD, line_width=2.5,
                               marker=dict(size=8, color=EMERALD_DARK))
    fig_monthly.update_layout(**PLOTLY_LAYOUT, height=340, showlegend=False,
                               title_text="Suspicious Fiat Transactions Flagged",
                               xaxis_range=[date_start, date_end])
    fig_monthly.update_yaxes(tickprefix=tickpfx, tickformat=",.0f")
    _add_deploy_line(fig_monthly)

    # 2) Alert funnel
    total_alerts = len(alt)
    reviewed = len(alt[alt["status"].isin([
        "CONFIRMED_FRAUD", "FALSE_POSITIVE", "CLOSED", "ESCALATED", "IN_REVIEW",
    ])])
    confirmed = len(alt[alt["status"] == "CONFIRMED_FRAUD"])

    fig_funnel = go.Figure(go.Funnel(
        y=["Total Alerts", "Reviewed", "Confirmed Fraud"],
        x=[total_alerts, reviewed, confirmed],
        marker=dict(color=[NAVY, BLUE, EMERALD]),
        textinfo="value+percent initial",
        textfont=dict(size=14),
    ))
    fig_funnel.update_layout(**PLOTLY_LAYOUT, height=340, title_text="Alert Funnel")

    # 3) Monthly Crypto Identified (stacked bar)
    crypto_assets = ["USDT", "USDC", "BTC", "ETH", "SOL", "TRX"]
    crypto_blocked = blocked[
        blocked["confirmed_bad"] & blocked["asset"].isin(crypto_assets)
    ].copy()
    crypto_blocked["month"] = crypto_blocked["event_ts"].dt.to_period("M").dt.to_timestamp()
    crypto_monthly = crypto_blocked.groupby(["month", "asset"])["amount_ngn"].sum().reset_index()
    crypto_monthly["amount_ngn"] = crypto_monthly["amount_ngn"] * divisor

    fig_crypto = px.bar(
        crypto_monthly, x="month", y="amount_ngn", color="asset",
        color_discrete_map=CRYPTO_COLORS,
        labels={"month": "", "amount_ngn": f"Amount ({currency})", "asset": ""},
    )
    fig_crypto.update_layout(**PLOTLY_LAYOUT, height=340, title_text="Suspicious Crypto Transactions Flagged",
                              barmode="stack",
                              legend=dict(orientation="h", y=-0.25),
                              xaxis_range=[date_start, date_end])
    fig_crypto.update_yaxes(tickprefix=tickpfx, tickformat=",.0f")
    _add_deploy_line(fig_crypto)

    # 4) Top risk signals — filter out empty/"none" reason codes
    all_codes = df["reason_codes"].str.split(",").explode()
    all_codes = all_codes[~all_codes.isin(["", "none"])]
    code_counts = all_codes.value_counts().head(10).reset_index()
    code_counts.columns = ["reason_code", "count"]

    fig_risk = px.bar(
        code_counts, y="reason_code", x="count", orientation="h",
        labels={"reason_code": "", "count": "Frequency"},
    )
    fig_risk.update_traces(marker_color=NAVY)
    layout_kwargs = {**PLOTLY_LAYOUT, "height": 360, "title_text": "Top Risk Signals"}
    layout_kwargs["yaxis"] = {**PLOTLY_LAYOUT.get("yaxis", {}), "autorange": "reversed"}
    fig_risk.update_layout(**layout_kwargs)

    # 5) Legitimate Payout Success Rate
    # Measures % of non-fraud payouts not hard-blocked (STEP_UP/HOLD still complete)
    weekly_data = []
    for week_start, grp in df.set_index("event_ts").resample("W"):
        total_legit = len(grp[~grp["confirmed_bad"]])
        if total_legit == 0:
            continue
        legit_blocked = len(grp[(~grp["confirmed_bad"]) & (grp["decision"] == "BLOCK")])
        pct = (total_legit - legit_blocked) / total_legit * 100
        weekly_data.append({"week": week_start, "legit_success_pct": pct})
    weekly = pd.DataFrame(weekly_data)

    fig_guardrail = px.area(
        weekly, x="week", y="legit_success_pct",
        labels={"week": "", "legit_success_pct": "Legit Success %"},
    )
    fig_guardrail.update_traces(line_color=EMERALD, fillcolor="rgba(16,185,129,0.1)")
    fig_guardrail.update_layout(**PLOTLY_LAYOUT, height=360,
                                 title_text="Legitimate Payout Success Rate",
                                 xaxis_range=[date_start, date_end])
    fig_guardrail.update_yaxes(range=[90, 100.5])
    fig_guardrail.add_hline(
        y=99, line_dash="dot", line_color=RED,
        annotation_text="99% target", annotation_position="top left",
        annotation_font_color=RED, annotation_font_size=11,
    )
    _add_deploy_line(fig_guardrail)

    # ── Layout (3 rows) ─────────────────────────────────────────────
    return html.Div([
        html.Div("Performance Overview", className="page-title"),
        html.Div("Fraud prevention performance across hashed entity data",
                  className="page-subtitle"),

        _operational_banner(),

        # KPI row
        html.Div(className="row g-3 mb-4", children=[
            html.Div(className="col", children=[
                _kpi_card("Fraud Value Prevented", f"{symbol}{fraud_prevented * divisor:,.0f}")
            ]),
            html.Div(className="col", children=[
                _kpi_card("Confirmed Bad Blocked", f"{confirmed_blocked:,}")
            ]),
            html.Div(className="col", children=[
                _kpi_card("False Positive Rate", f"{fp_rate:.1f}%")
            ]),
            html.Div(className="col", children=[
                _kpi_card("Legit Payout Success", f"{legit_success:.2f}%")
            ]),
            html.Div(className="col", children=[
                _kpi_card("p95 Decision Latency", f"{p95_latency:.0f} ms")
            ]),
        ]),

        # Chart row 1: Monthly Fraud Prevented + Alert Funnel
        html.Div(className="row g-3 mb-3", children=[
            html.Div(className="col-md-6", children=[
                html.Div(className="chart-container", children=[
                    dcc.Graph(figure=fig_monthly, config={"displayModeBar": False}),
                ])
            ]),
            html.Div(className="col-md-6", children=[
                html.Div(className="chart-container", children=[
                    dcc.Graph(figure=fig_funnel, config={"displayModeBar": False}),
                ])
            ]),
        ]),

        # Chart row 2: Monthly Crypto Recovered + Top Risk Signals
        html.Div(className="row g-3 mb-3", children=[
            html.Div(className="col-md-6", children=[
                html.Div(className="chart-container", children=[
                    dcc.Graph(figure=fig_crypto, config={"displayModeBar": False}),
                ])
            ]),
            html.Div(className="col-md-6", children=[
                html.Div(className="chart-container", children=[
                    dcc.Graph(figure=fig_risk, config={"displayModeBar": False}),
                ])
            ]),
        ]),

        # Chart row 3: Customer Impact Guardrail (full width)
        html.Div(className="row g-3", children=[
            html.Div(className="col-md-12", children=[
                html.Div(className="chart-container", children=[
                    dcc.Graph(figure=fig_guardrail, config={"displayModeBar": False}),
                ])
            ]),
        ]),
    ])
