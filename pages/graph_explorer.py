"""
Page 3 — Graph Explorer (hashed IDs)
Interactive network graph with Plotly, entity search, hop depth,
side panel with linked entities, and case packet export.
Full-width graph, wider and clearer layout.
"""

import json
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from dash import html, dcc, dash_table, Input, Output, State, no_update

from components.data_loader import load_graph_edges, load_payouts, load_alerts
from components.theme import (
    PLOTLY_LAYOUT, NODE_COLORS, NAVY, EMERALD,
    RED, AMBER, BLUE, GRAY_200, GRAY_400, GRAY_500, GRAY_700, WHITE,
)


def _build_full_graph(edges_df: pd.DataFrame) -> nx.Graph:
    """Build full NetworkX graph from edges."""
    G = nx.Graph()
    for _, row in edges_df.iterrows():
        src = f"{row['src_type']}:{row['src_id']}"
        dst = f"{row['dst_type']}:{row['dst_id']}"
        G.add_node(src, node_type=row["src_type"])
        G.add_node(dst, node_type=row["dst_type"])
        G.add_edge(src, dst, edge_type=row["edge_type"], weight=row["weight"])
    return G


def _extract_subgraph(G: nx.Graph, entity_id: str, entity_type: str, hops: int,
                      max_nodes: int = 500) -> nx.Graph:
    """BFS hop extraction from seed node, capped at max_nodes for performance."""
    seed = f"{entity_type}:{entity_id}"
    if seed not in G:
        return nx.Graph()

    nodes = {seed}
    frontier = {seed}
    for _ in range(hops):
        next_frontier = set()
        for n in frontier:
            for neighbor in G.neighbors(n):
                if neighbor not in nodes:
                    next_frontier.add(neighbor)
                    nodes.add(neighbor)
                    if len(nodes) >= max_nodes:
                        break
            if len(nodes) >= max_nodes:
                break
        frontier = next_frontier
        if len(nodes) >= max_nodes:
            break

    return G.subgraph(nodes).copy()


def _plotly_network(G: nx.Graph, seed: str) -> go.Figure:
    """Render a NetworkX graph as a wide, clear Plotly figure."""
    if len(G.nodes) == 0:
        fig = go.Figure()
        fig.add_annotation(text="No connections found", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font_size=16, font_color=GRAY_500)
        fig.update_layout(**PLOTLY_LAYOUT, height=600)
        return fig

    # For large graphs, hide edge labels to keep rendering fast
    show_edge_labels = len(G.edges) <= 150

    pos = nx.spring_layout(G, seed=42, k=3.0 / max(len(G.nodes) ** 0.5, 1), iterations=60)

    # Edge traces
    edge_x, edge_y = [], []
    edge_mid_x, edge_mid_y, edge_labels = [], [], []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        edge_mid_x.append((x0 + x1) / 2)
        edge_mid_y.append((y0 + y1) / 2)
        edge_labels.append(data.get("edge_type", ""))

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=1.5, color=GRAY_400),
        hoverinfo="none",
    )

    edge_label_trace = go.Scatter(
        x=edge_mid_x, y=edge_mid_y, mode="text",
        text=edge_labels if show_edge_labels else [""] * len(edge_labels),
        textfont=dict(size=9, color=GRAY_500),
        hovertext=edge_labels,
        hoverinfo="text",
    )

    # Node traces — one per type for legend
    node_traces = []
    for ntype, color in NODE_COLORS.items():
        nx_list = [n for n in G.nodes() if G.nodes[n].get("node_type") == ntype]
        if not nx_list:
            continue
        xs = [pos[n][0] for n in nx_list]
        ys = [pos[n][1] for n in nx_list]
        labels = [n.split(":")[1][:10] for n in nx_list]
        sizes = [24 if n == seed else 14 for n in nx_list]

        node_traces.append(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            marker=dict(size=sizes, color=color, line=dict(width=2, color=WHITE)),
            text=labels,
            textposition="top center",
            textfont=dict(size=10, color=GRAY_700),
            hovertext=nx_list,
            hoverinfo="text",
            name=ntype,
        ))

    fig = go.Figure(data=[edge_trace, edge_label_trace] + node_traces)
    fig.update_layout(
        **PLOTLY_LAYOUT, height=600, showlegend=True,
        legend=dict(orientation="h", y=-0.05, font_size=12),
        dragmode="pan",
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


NGN_TO_USD = 1 / 1479


def build_layout(date_start: str, date_end: str, currency: str = "NGN") -> html.Div:
    """Build the Graph Explorer page layout."""
    edges = load_graph_edges()
    ds = pd.Timestamp(date_start).date()
    de = pd.Timestamp(date_end).date()
    edges_f = edges[(edges["last_seen"].dt.date >= ds) & (edges["last_seen"].dt.date <= de)]

    # Collect valid entity IDs per type
    entity_options = {}
    for etype in ["user", "beneficiary", "device", "ip", "account"]:
        ids = set()
        ids.update(edges_f[edges_f["src_type"] == etype]["src_id"].unique())
        ids.update(edges_f[edges_f["dst_type"] == etype]["dst_id"].unique())
        entity_options[etype] = sorted(ids)[:500]

    entity_options_json = json.dumps(entity_options)

    return html.Div([
        html.Div("Graph Explorer", className="page-title"),
        html.Div("Investigate hashed entity relationships and export case packets",
                  className="page-subtitle"),

        # Hidden store
        dcc.Store(id="entity-options-store", data=entity_options_json),

        # Search controls
        html.Div(className="row g-3 mb-3 align-items-end", children=[
            html.Div(className="col-md-3", children=[
                html.Label("Entity Type", className="filter-label"),
                dcc.Dropdown(
                    id="graph-entity-type",
                    options=[
                        {"label": "User", "value": "user"},
                        {"label": "Beneficiary", "value": "beneficiary"},
                        {"label": "Device", "value": "device"},
                        {"label": "IP Address", "value": "ip"},
                        {"label": "Account (BVN)", "value": "account"},
                    ],
                    value="user",
                    clearable=False,
                    style={"fontSize": "0.88rem"},
                ),
            ]),
            html.Div(className="col-md-4", children=[
                html.Label("Entity ID (hashed)", className="filter-label"),
                dcc.Dropdown(
                    id="graph-entity-id",
                    options=[{"label": eid, "value": eid} for eid in entity_options.get("user", [])],
                    placeholder="Select hashed entity ID...",
                    style={"fontSize": "0.88rem"},
                ),
            ]),
            html.Div(className="col-md-2", children=[
                html.Label("Hop Depth", className="filter-label"),
                dcc.Slider(
                    id="graph-hop-depth",
                    min=1, max=5, step=1, value=2,
                    marks={1: "1", 2: "2", 3: "3", 4: "4", 5: "5"},
                ),
            ]),
            html.Div(className="col-md-3", children=[
                html.Button(
                    "Explore", id="graph-explore-btn",
                    className="btn btn-primary w-100",
                    style={
                        "backgroundColor": EMERALD, "border": "none", "fontWeight": 600,
                        "borderRadius": "8px", "padding": "10px", "fontSize": "0.9rem",
                    },
                ),
            ]),
        ]),

        # Main content area (populated by callback)
        html.Div(id="graph-content", children=[
            html.Div(
                style={"textAlign": "center", "padding": "60px 0", "color": GRAY_500},
                children=[html.P("Select an entity and click Explore to view its network graph.")],
            ),
        ]),

        # Download component
        dcc.Download(id="case-packet-download"),
    ])


def register_callbacks(app):
    """Register all Graph Explorer callbacks."""

    @app.callback(
        Output("graph-entity-id", "options"),
        Output("graph-entity-id", "value"),
        Input("graph-entity-type", "value"),
        State("entity-options-store", "data"),
    )
    def update_entity_options(entity_type, options_json):
        if not entity_type or not options_json:
            return [], None
        options = json.loads(options_json)
        ids = options.get(entity_type, [])
        return [{"label": eid, "value": eid} for eid in ids], None

    @app.callback(
        Output("graph-content", "children"),
        Input("graph-explore-btn", "n_clicks"),
        State("graph-entity-type", "value"),
        State("graph-entity-id", "value"),
        State("graph-hop-depth", "value"),
        State("date-start", "value"),
        State("date-end", "value"),
        State("currency-store", "data"),
        prevent_initial_call=True,
    )
    def explore_graph(n_clicks, entity_type, entity_id, hop_depth, date_start, date_end, currency):
        currency = currency or "NGN"
        if currency == "USD":
            symbol, divisor = "$", NGN_TO_USD
        else:
            symbol, divisor = "₦", 1
        if not entity_id:
            return html.Div("Please select an entity ID.",
                            style={"color": AMBER, "padding": "20px"})

        edges = load_graph_edges()
        payouts = load_payouts()
        alerts = load_alerts()

        ds = pd.Timestamp(date_start).date()
        de = pd.Timestamp(date_end).date()
        edges_f = edges[(edges["last_seen"].dt.date >= ds) & (edges["last_seen"].dt.date <= de)]

        # Build full graph and extract subgraph
        edges_for_graph = edges_f[["src_type", "src_id", "dst_type", "dst_id", "edge_type", "weight"]]
        G = _build_full_graph(edges_for_graph)
        subG = _extract_subgraph(G, entity_id, entity_type, hop_depth)
        seed = f"{entity_type}:{entity_id}"

        if len(subG.nodes) == 0:
            return html.Div(
                "No connections found for this entity in the selected date range.",
                style={"textAlign": "center", "padding": "40px", "color": GRAY_500},
            )

        # Build Plotly network figure
        fig = _plotly_network(subG, seed)

        # Linked entities table
        entity_list = []
        for node in subG.nodes():
            if node == seed:
                continue
            ntype, nid = node.split(":", 1)
            edge_data = subG.get_edge_data(seed, node)
            entity_list.append({
                "type": ntype, "id": nid[:10] + "...",
                "edge": edge_data["edge_type"] if edge_data else "indirect",
                "connections": len(list(subG.neighbors(node))),
            })
        entity_df = (pd.DataFrame(entity_list).sort_values("connections", ascending=False)
                     if entity_list else pd.DataFrame())

        # Associated payouts
        entity_nodes = [n.split(":", 1)[1] for n in subG.nodes()]
        assoc = payouts[
            (payouts["user_id"].isin(entity_nodes)) | (payouts["beneficiary_id"].isin(entity_nodes))
        ]
        assoc = assoc[(assoc["event_ts"].dt.date >= ds) & (assoc["event_ts"].dt.date <= de)]

        # Top risk reasons
        risk_reasons_section = []
        if len(assoc) > 0:
            all_codes = assoc["reason_codes"].str.split(",").explode()
            top_reasons = all_codes.value_counts().head(8)
            risk_rows = []
            for reason, count in top_reasons.items():
                pct = count / len(assoc) * 100
                risk_rows.append(
                    html.Div(style={
                        "display": "flex", "justifyContent": "space-between",
                        "padding": "5px 0", "borderBottom": f"1px solid {GRAY_200}",
                        "fontSize": "0.84rem",
                    }, children=[
                        html.Span(reason, style={"color": NAVY, "fontWeight": 500}),
                        html.Span(f"{count} ({pct:.0f}%)", style={"color": GRAY_500}),
                    ])
                )
            risk_reasons_section = [
                html.Div("Top Risk Reasons", className="section-header"),
                html.Div(risk_rows),
            ]

        # Prepare export data
        export_data = {
            "case_entity": {"type": entity_type, "id": entity_id},
            "hop_depth": hop_depth,
            "date_range": {"start": str(date_start), "end": str(date_end)},
            "nodes": [
                {"id": n, "type": subG.nodes[n].get("node_type", "unknown")}
                for n in subG.nodes()
            ],
            "edges": [
                {"source": u, "target": v,
                 "edge_type": d.get("edge_type", ""),
                 "weight": d.get("weight", 0)}
                for u, v, d in subG.edges(data=True)
            ],
            "associated_payouts": (
                assoc[["payout_id", "user_id", "beneficiary_id", "amount_ngn",
                       "decision", "risk_score", "reason_codes", "confirmed_bad"]]
                .head(50).to_dict(orient="records")
                if len(assoc) > 0 else []
            ),
            "linked_alerts": (
                alerts[alerts["payout_id"].isin(assoc["payout_id"].tolist())]
                [["alert_id", "typology", "severity", "status", "evidence_summary"]]
                .head(30).to_dict(orient="records")
                if len(assoc) > 0 else []
            ),
        }

        # Table helper
        def _table(data, columns, page_size=8):
            return dash_table.DataTable(
                data=data,
                columns=[{"name": c, "id": c} for c in columns],
                page_size=page_size,
                style_table={"overflowX": "auto"},
                style_header={"backgroundColor": "#F9FAFB", "fontWeight": 600,
                               "fontSize": "0.78rem", "color": GRAY_500},
                style_cell={"fontFamily": "Inter, sans-serif", "fontSize": "0.82rem",
                             "padding": "8px 12px", "textAlign": "left"},
                style_data_conditional=[
                    {"if": {"filter_query": '{decision} = "BLOCK"'},
                     "backgroundColor": "rgba(239,68,68,0.06)"},
                ],
            )

        # Full-width graph on top, 3 panels below
        return html.Div([
            # Full-width graph
            html.Div(
                f"Network Graph \u2014 {entity_id[:10]}... "
                f"({hop_depth} hops, {len(subG.nodes)} nodes, {len(subG.edges)} edges)",
                className="section-header",
            ),
            html.Div(className="chart-container", children=[
                dcc.Graph(figure=fig, config={"displayModeBar": True, "scrollZoom": True}),
            ]),

            # Three panels below the graph
            html.Div(className="row g-3 mt-3", children=[
                # Linked entities
                html.Div(className="col-md-4", children=[
                    html.Div("Linked Entities", className="section-header"),
                    _table(
                        entity_df.to_dict("records") if len(entity_df) > 0 else [],
                        ["type", "id", "edge", "connections"],
                    ) if len(entity_df) > 0 else html.P("No linked entities.", style={"color": GRAY_500}),
                ]),

                # Associated payouts
                html.Div(className="col-md-4", children=[
                    html.Div("Associated Payouts", className="section-header"),
                    _table(
                        assoc[["payout_id", "amount_ngn", "decision", "risk_score"]]
                        .assign(
                            payout_id=assoc["payout_id"].str[:10] + "...",
                            amount_ngn=assoc["amount_ngn"].apply(lambda v: f"{symbol}{v * divisor:,.2f}"),
                        )
                        .rename(columns={"amount_ngn": "amount"})
                        .sort_values("risk_score", ascending=False).head(20).to_dict("records")
                        if len(assoc) > 0 else [],
                        ["payout_id", "amount", "decision", "risk_score"],
                        page_size=6,
                    ) if len(assoc) > 0 else html.P("No payouts in range.", style={"color": GRAY_500}),
                ]),

                # Risk reasons
                html.Div(className="col-md-4", children=(
                    risk_reasons_section if risk_reasons_section else [
                        html.Div("Top Risk Reasons", className="section-header"),
                        html.P("No risk data available.", style={"color": GRAY_500}),
                    ]
                )),
            ]),

            # Export button
            html.Div(style={"marginTop": "24px"}, children=[
                html.Button(
                    "Export Case Packet (JSON)",
                    id="export-case-btn",
                    className="btn",
                    style={
                        "backgroundColor": NAVY, "color": WHITE, "border": "none",
                        "fontWeight": 600, "borderRadius": "8px", "padding": "10px 24px",
                        "fontSize": "0.88rem",
                    },
                ),
            ]),

            dcc.Store(id="export-graph-data", data=json.dumps(export_data, default=str)),
        ])

    @app.callback(
        Output("case-packet-download", "data"),
        Input("export-case-btn", "n_clicks"),
        State("export-graph-data", "data"),
        prevent_initial_call=True,
    )
    def export_case_packet(n_clicks, graph_data_json):
        if not n_clicks or not graph_data_json:
            return no_update
        packet = json.loads(graph_data_json)
        entity = packet.get("case_entity", {})
        filename = f"case_packet_{entity.get('type', 'unknown')}_{entity.get('id', 'unknown')[:10]}.json"
        return dict(
            content=json.dumps(packet, indent=2, default=str),
            filename=filename,
            type="application/json",
        )
