"""
Shared theme constants and reusable Dash component builders.
Modern fintech admin console: white bg, deep navy, emerald accent.
"""

# ── Color Palette ───────────────────────────────────────────────────
NAVY = "#0A1628"
NAVY_LIGHT = "#1B2A4A"
EMERALD = "#10B981"
EMERALD_DARK = "#059669"
EMERALD_LIGHT = "#D1FAE5"
WHITE = "#FFFFFF"
GRAY_50 = "#F9FAFB"
GRAY_100 = "#F3F4F6"
GRAY_200 = "#E5E7EB"
GRAY_400 = "#9CA3AF"
GRAY_500 = "#6B7280"
GRAY_700 = "#374151"
GRAY_900 = "#111827"
RED = "#EF4444"
AMBER = "#F59E0B"
BLUE = "#3B82F6"
PURPLE = "#8B5CF6"
PINK = "#EC4899"

NODE_COLORS = {
    "user": BLUE,
    "beneficiary": EMERALD,
    "device": AMBER,
    "account": PURPLE,
    "ip": RED,
}

SEVERITY_COLORS = {
    "CRITICAL": RED,
    "HIGH": AMBER,
    "MEDIUM": BLUE,
    "LOW": GRAY_400,
}

CRYPTO_COLORS = {
    "USDT": "#26A17B",  # Tether green
    "USDC": "#2775CA",  # USDC blue
    "BTC": "#F7931A",   # Bitcoin orange
    "ETH": "#627EEA",   # Ethereum purple
    "SOL": "#9945FF",   # Solana purple
    "TRX": "#FF0013",   # TRON red
}

# ── Plotly Layout Defaults ──────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    font=dict(family="Open Runde, Inter, -apple-system, sans-serif", color=GRAY_700, size=12),
    paper_bgcolor=WHITE,
    plot_bgcolor=WHITE,
    margin=dict(l=48, r=24, t=48, b=40),
    title_font=dict(size=15, color=NAVY),
    hoverlabel=dict(
        bgcolor=NAVY,
        font_size=13,
        font_family="Open Runde, Inter, -apple-system, sans-serif",
        font_color=WHITE,
    ),
    xaxis=dict(gridcolor=GRAY_200, zerolinecolor=GRAY_200),
    yaxis=dict(gridcolor=GRAY_200, zerolinecolor=GRAY_200),
)
