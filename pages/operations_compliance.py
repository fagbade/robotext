"""
Page 2 — Operations & Compliance (hashed IDs)
Alert triage, analyst workload, compliance queue, evidence drilldown.
"""

import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import html, dcc, dash_table, callback, Input, Output, State, no_update

from components.data_loader import load_payouts, load_alerts, load_graph_edges
from components.theme import (
    PLOTLY_LAYOUT, NAVY, NAVY_LIGHT, EMERALD, EMERALD_DARK,
    RED, AMBER, BLUE, GRAY_200, GRAY_400, GRAY_500, GRAY_700,
    PURPLE, PINK, SEVERITY_COLORS,
)


def _kpi_card(label: str, value: str) -> html.Div:
    return html.Div(className="kpi-card", children=[
        html.Div(value, className="kpi-value"),
        html.Div(label, className="kpi-label"),
    ])


NGN_TO_USD = 1 / 1479


def build_layout(date_start: str, date_end: str, currency: str = "NGN") -> html.Div:
    """Build the static portion of the layout. Drilldown is handled by callbacks."""
    if currency == "USD":
        symbol, divisor = "$", NGN_TO_USD
    else:
        symbol, divisor = "₦", 1
    payouts = load_payouts()
    alerts = load_alerts()

    ds = pd.Timestamp(date_start).date()
    de = pd.Timestamp(date_end).date()

    alt = alerts[(alerts["created_at"].dt.date >= ds) & (alerts["created_at"].dt.date <= de)].copy()
    pay = payouts[(payouts["event_ts"].dt.date >= ds) & (payouts["event_ts"].dt.date <= de)].copy()

    # ── KPI calculations ────────────────────────────────────────────
    date_range_days = max((pd.Timestamp(date_end) - pd.Timestamp(date_start)).days, 1)
    alerts_per_day = len(alt) / date_range_days

    closed = alt.dropna(subset=["closed_at"])
    median_triage = 0
    if len(closed) > 0:
        triage_mins = (closed["closed_at"] - closed["created_at"]).dt.total_seconds() / 60
        median_triage = triage_mins.median()

    confirm_rate = len(alt[alt["status"] == "CONFIRMED_FRAUD"]) / max(len(alt), 1) * 100
    analyst_count = alt["analyst_id"].nunique()
    if len(alt) > 0:
        alert_span_days = max((alt["created_at"].max() - alt["created_at"].min()).days, 1)
        alert_months = max(alert_span_days / 30.0, 1)
        workload = len(alt) / max(analyst_count, 1) / alert_months
    else:
        workload = 0

    # ── Severity trend ──────────────────────────────────────────────
    alt["week"] = alt["created_at"].dt.to_period("W").dt.to_timestamp()
    sev_trend = alt.groupby(["week", "severity"]).size().reset_index(name="count")

    fig_sev = px.line(
        sev_trend, x="week", y="count", color="severity",
        color_discrete_map=SEVERITY_COLORS,
        labels={"week": "", "count": "Alerts", "severity": ""},
    )
    fig_sev.update_layout(**PLOTLY_LAYOUT, height=390, title_text="Alert Severity Trend",
                           legend=dict(orientation="h", y=-0.25))

    # ── Queue aging heatmap (severity × age bucket) ─────────────────
    open_alerts = alt[alt["status"].isin(["OPEN", "IN_REVIEW", "ESCALATED"])].copy()
    now = pd.Timestamp(f"{date_end} 23:59:59")

    if len(open_alerts) > 0:
        open_alerts["age_hours"] = (now - open_alerts["created_at"]).dt.total_seconds() / 3600
        age_bins = [0, 24, 72, 168, 720, 2160, float("inf")]
        age_labels = ["<1d", "1-3d", "3-7d", "1-4w", "1-3mo", ">3mo"]
        open_alerts["age_bucket"] = pd.cut(
            open_alerts["age_hours"], bins=age_bins, labels=age_labels, right=False,
        )
        sev_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        heatmap_data = (
            open_alerts.groupby(["severity", "age_bucket"], observed=False)
            .size()
            .reset_index(name="count")
        )
        pivot = heatmap_data.pivot(index="severity", columns="age_bucket", values="count").fillna(0)
        pivot = pivot.reindex(index=sev_order, columns=age_labels, fill_value=0)

        fig_aging = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[[0, "#F3F4F6"], [0.25, "#D1FAE5"], [0.5, "#6EE7B7"],
                         [0.75, "#10B981"], [1.0, "#065F46"]],
            text=pivot.values.astype(int).astype(str),
            texttemplate="%{text}",
            textfont=dict(size=13, color=NAVY),
            hovertemplate="Severity: %{y}<br>Age: %{x}<br>Count: %{z}<extra></extra>",
            showscale=True,
            colorbar=dict(title="Alerts", thickness=12, len=0.8),
        ))
        fig_aging.update_layout(**PLOTLY_LAYOUT, height=390, title_text="Queue Aging",
                                 xaxis_title="Age Bucket", yaxis_title="")
    else:
        fig_aging = go.Figure()
        fig_aging.add_annotation(text="No open alerts", xref="paper", yref="paper",
                                  x=0.5, y=0.5, showarrow=False, font_size=14, font_color=GRAY_500)
        fig_aging.update_layout(**PLOTLY_LAYOUT, height=390, title_text="Queue Aging")

    # ── Analyst throughput (monthly avg) ─────────────────────────────
    if len(closed) > 0:
        analyst_span_days = max((closed["closed_at"].max() - closed["created_at"].min()).days, 1)
        analyst_months = max(analyst_span_days / 30.0, 1)
    else:
        analyst_months = 1
    analyst_closed = (
        closed.groupby("analyst_id").size()
        .reset_index(name="total_closed")
    )
    analyst_closed["closed_count"] = (analyst_closed["total_closed"] / analyst_months).round(0).astype(int)
    analyst_closed = analyst_closed.sort_values("closed_count", ascending=True)
    fig_analyst = px.bar(
        analyst_closed, y="analyst_id", x="closed_count", orientation="h",
        labels={"analyst_id": "", "closed_count": "Cases / Month"},
    )
    fig_analyst.update_traces(marker_color=EMERALD_DARK)
    fig_analyst.update_layout(**PLOTLY_LAYOUT, height=390, title_text="Analyst Throughput (Monthly Avg)")

    # ── SAR Candidate Queue ─────────────────────────────────────────
    sar = alt[
        (alt["status"].isin(["CONFIRMED_FRAUD", "ESCALATED"])) &
        (alt["severity"].isin(["CRITICAL", "HIGH"]))
    ][["alert_id", "entity_type", "entity_id", "typology", "severity", "created_at", "status"]].copy()
    sar["alert_id"] = sar["alert_id"].str[:10] + "..."
    sar["entity_id"] = sar["entity_id"].str[:10] + "..."
    sar["created_at"] = sar["created_at"].dt.strftime("%Y-%m-%d %H:%M")
    sar = sar.sort_values("created_at", ascending=False).head(50)

    # ── Typology distribution ───────────────────────────────────────
    typology_color_map = {
        "structuring": NAVY,
        "mule_network": RED,
        "rapid_movement": EMERALD,
        "account_takeover": AMBER,
        "velocity_anomaly": BLUE,
        "bvn_mismatch": PURPLE,
        "dormant_reactivation": PINK,
        "sanctions_proximity": GRAY_400,
    }
    typo = alt["typology"].value_counts().reset_index()
    typo.columns = ["typology", "count"]
    fig_typo = px.pie(
        typo, names="typology", values="count",
        color="typology",
        color_discrete_map=typology_color_map,
        hole=0.45,
    )
    fig_typo.update_layout(
        **PLOTLY_LAYOUT, height=390, title_text="Typology Distribution",
        showlegend=True,
        legend=dict(font_size=10, orientation="h", y=-0.15, x=0.5, xanchor="center"),
    )
    fig_typo.update_traces(
        textposition="auto", textinfo="percent", textfont_size=11,
        pull=[0.03 if i == 0 else 0 for i in range(len(typo))],
    )

    # ── Payout options for drilldown ────────────────────────────────
    payout_options = [{"label": pid[:10] + "...", "value": pid} for pid in pay["payout_id"].tolist()[:500]]

    # ── Layout ──────────────────────────────────────────────────────
    return html.Div([
        html.Div("Operations & Compliance", className="page-title"),
        html.Div("Alert triage, analyst workload, and regulatory compliance workflows",
                  className="page-subtitle"),

        # Operations header
        html.Div("Operations", className="section-header"),

        # KPIs
        html.Div(className="row g-3 mb-4", children=[
            html.Div(className="col-md-3", children=[
                _kpi_card("Alerts / Day", f"{alerts_per_day:.1f}")
            ]),
            html.Div(className="col-md-3", children=[
                _kpi_card("Median Triage Time", f"{median_triage:.0f} min")
            ]),
            html.Div(className="col-md-3", children=[
                _kpi_card("Confirm Rate", f"{confirm_rate:.1f}%")
            ]),
            html.Div(className="col-md-3", children=[
                _kpi_card("Monthly Workload / Analyst", f"{workload:.0f}")
            ]),
        ]),

        # Operations charts — Row 1: Alert Severity Trend (full width)
        html.Div(className="row g-3 mb-3", children=[
            html.Div(className="col-md-12", children=[
                html.Div(className="chart-container", children=[
                    dcc.Graph(figure=fig_sev, config={"displayModeBar": False}),
                ])
            ]),
        ]),

        # Operations charts — Row 2: Queue Aging + Analyst Throughput
        html.Div(className="row g-3 mb-4", children=[
            html.Div(className="col-md-6", children=[
                html.Div(className="chart-container", children=[
                    dcc.Graph(figure=fig_aging, config={"displayModeBar": False}),
                ])
            ]),
            html.Div(className="col-md-6", children=[
                html.Div(className="chart-container", children=[
                    dcc.Graph(figure=fig_analyst, config={"displayModeBar": False}),
                ])
            ]),
        ]),

        # Compliance header
        html.Div("Compliance", className="section-header"),

        html.Div(className="row g-3 mb-4", children=[
            # SAR queue
            html.Div(className="col-md-7", children=[
                html.H6("SAR Candidate Queue", style={"fontWeight": 600, "color": NAVY, "marginBottom": "8px"}),
                dash_table.DataTable(
                    data=sar.to_dict("records"),
                    columns=[{"name": c, "id": c} for c in sar.columns],
                    page_size=10,
                    style_table={"overflowX": "auto"},
                    style_header={
                        "backgroundColor": "#F9FAFB", "fontWeight": 600,
                        "fontSize": "0.78rem", "color": GRAY_500,
                        "textTransform": "uppercase", "letterSpacing": "0.03em",
                    },
                    style_cell={
                        "fontFamily": "Inter, sans-serif", "fontSize": "0.82rem",
                        "padding": "8px 12px", "textAlign": "left",
                    },
                    style_data_conditional=[
                        {"if": {"filter_query": '{severity} = "CRITICAL"'},
                         "backgroundColor": "rgba(239,68,68,0.06)", "color": RED},
                    ],
                ),
            ]),
            # Typology distribution
            html.Div(className="col-md-5", children=[
                html.Div(className="chart-container", children=[
                    dcc.Graph(figure=fig_typo, config={"displayModeBar": False}),
                ])
            ]),
        ]),

        # Decision Evidence Drilldown
        html.Div("Decision Evidence Drilldown", className="section-header"),

        html.Div(className="row g-3 mb-4", children=[
            html.Div(className="col-md-4", children=[
                html.Label("Select Payout ID", className="filter-label"),
                dcc.Dropdown(
                    id="drilldown-payout-select",
                    options=payout_options,
                    placeholder="Search for a payout ID...",
                    style={"fontSize": "0.88rem"},
                ),
            ]),
        ]),

        # Drilldown content (populated by callback)
        html.Div(id="drilldown-content"),
    ])


def register_callbacks(app):
    """Register the drilldown callback on the Dash app."""

    @app.callback(
        Output("drilldown-content", "children"),
        Input("drilldown-payout-select", "value"),
        State("date-start", "value"),
        State("date-end", "value"),
        State("currency-store", "data"),
        prevent_initial_call=True,
    )
    def update_drilldown(payout_id, date_start, date_end, currency):
        if not payout_id:
            return no_update

        payouts = load_payouts()
        alerts = load_alerts()
        edges = load_graph_edges()

        row = payouts[payouts["payout_id"] == payout_id]
        if len(row) == 0:
            return html.Div("Payout not found.", style={"color": RED})
        row = row.iloc[0]

        # Reason code badges
        HIGH_RISK_CODES = {"graph_cluster_risk", "sanctioned_proximity", "beneficiary_ring"}
        codes = row["reason_codes"].split(",")
        badges = []
        for c in codes:
            cls = "reason-badge high" if c in HIGH_RISK_CODES else "reason-badge medium"
            badges.append(html.Span(c, className=cls))

        # Detail table
        detail_rows = [
            ("Payout ID", row["payout_id"][:10] + "..."),
            ("User", row["user_id"][:10] + "..."),
            ("Beneficiary", row["beneficiary_id"][:10] + "..."),
            ("Amount", f"{'$' if currency == 'USD' else '₦'}{row['amount_ngn'] * (NGN_TO_USD if currency == 'USD' else 1):,.2f}"),
            ("Asset", row["asset"]),
            ("Network", row["network"]),
            ("Bank Code", row["bank_code"]),
            ("Decision", row["decision"]),
            ("Risk Score", f"{row['risk_score']:.1f}"),
            ("Latency", f"{row['latency_ms']:.1f} ms"),
            ("Model", row["model_version"]),
            ("Confirmed Bad", "Yes" if row["confirmed_bad"] else "No"),
        ]

        detail_table = html.Table(
            [html.Tr([
                html.Td(k, style={"fontWeight": 600, "color": GRAY_700, "padding": "6px 16px 6px 0",
                                   "fontSize": "0.84rem", "borderBottom": f"1px solid {GRAY_200}"}),
                html.Td(v, style={"padding": "6px 0", "fontSize": "0.84rem",
                                   "borderBottom": f"1px solid {GRAY_200}"}),
            ]) for k, v in detail_rows],
            style={"width": "100%"},
        )

        # Linked alerts
        linked = alerts[alerts["payout_id"] == payout_id]
        linked_section = []
        if len(linked) > 0:
            linked_display = linked[["alert_id", "typology", "severity", "status", "evidence_summary"]].copy()
            linked_display["alert_id"] = linked_display["alert_id"].str[:10] + "..."
            linked_section = [
                html.H6("Linked Alerts", style={"fontWeight": 600, "color": NAVY, "marginTop": "16px"}),
                dash_table.DataTable(
                    data=linked_display.to_dict("records"),
                    columns=[{"name": c, "id": c} for c in linked_display.columns],
                    page_size=5,
                    style_table={"overflowX": "auto"},
                    style_header={"backgroundColor": "#F9FAFB", "fontWeight": 600,
                                   "fontSize": "0.78rem", "color": GRAY_500},
                    style_cell={"fontFamily": "Inter, sans-serif", "fontSize": "0.82rem",
                                 "padding": "8px 12px", "textAlign": "left"},
                ),
            ]

        # Subgraph preview
        user_id = row["user_id"]
        ben_id = row["beneficiary_id"]
        linked_edges = edges[
            (edges["src_id"].isin([user_id, ben_id])) |
            (edges["dst_id"].isin([user_id, ben_id]))
        ].head(20)

        subgraph_section = []
        if len(linked_edges) > 0:
            display_e = linked_edges[["src_type", "src_id", "edge_type", "dst_type", "dst_id", "weight"]].copy()
            display_e["src_id"] = display_e["src_id"].str[:10] + "..."
            display_e["dst_id"] = display_e["dst_id"].str[:10] + "..."
            subgraph_section = [
                html.H6("Entity Links (Subgraph Preview)",
                         style={"fontWeight": 600, "color": NAVY, "marginTop": "16px"}),
                dash_table.DataTable(
                    data=display_e.to_dict("records"),
                    columns=[{"name": c, "id": c} for c in display_e.columns],
                    page_size=8,
                    style_table={"overflowX": "auto"},
                    style_header={"backgroundColor": "#F9FAFB", "fontWeight": 600,
                                   "fontSize": "0.78rem", "color": GRAY_500},
                    style_cell={"fontFamily": "Inter, sans-serif", "fontSize": "0.82rem",
                                 "padding": "8px 12px", "textAlign": "left"},
                ),
            ]

        return html.Div(className="row g-3", children=[
            html.Div(className="col-md-5", children=[detail_table]),
            html.Div(className="col-md-7", children=[
                html.H6("Reason Codes", style={"fontWeight": 600, "color": NAVY}),
                html.Div(badges, style={"marginBottom": "12px"}),
                *linked_section,
                *subgraph_section,
            ]),
        ])
