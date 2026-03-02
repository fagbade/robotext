"""
Centralized data loading for the Cheda FGI Dash dashboard.
Uses a simple module-level cache. Auto-generates synthetic data if missing.
"""

import pandas as pd
from pathlib import Path
from functools import lru_cache

DATA_DIR = Path(__file__).parent.parent / "data"


def _ensure_data():
    required = [
        "fgi_payout_decisions_fact.parquet",
        "fgi_alerts_fact.parquet",
        "fgi_federation_ops_fact.parquet",
        "fgi_graph_edges.parquet",
    ]
    missing = [f for f in required if not (DATA_DIR / f).exists()]
    if missing:
        import sys
        # Try shared generator first (preferred), then local fallback
        shared_gen = Path(__file__).parent.parent.parent / "shared_generate.py"
        if shared_gen.exists():
            sys.path.insert(0, str(shared_gen.parent))
            from shared_generate import generate_all
            generate_all()
        else:
            sys.path.insert(0, str(DATA_DIR))
            from generate_synthetic import generate_all
            generate_all()


@lru_cache(maxsize=1)
def load_payouts() -> pd.DataFrame:
    _ensure_data()
    df = pd.read_parquet(DATA_DIR / "fgi_payout_decisions_fact.parquet")
    df["event_ts"] = pd.to_datetime(df["event_ts"])
    return df


@lru_cache(maxsize=1)
def load_alerts() -> pd.DataFrame:
    _ensure_data()
    df = pd.read_parquet(DATA_DIR / "fgi_alerts_fact.parquet")
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["closed_at"] = pd.to_datetime(df["closed_at"])
    return df


@lru_cache(maxsize=1)
def load_federation() -> pd.DataFrame:
    _ensure_data()
    df = pd.read_parquet(DATA_DIR / "fgi_federation_ops_fact.parquet")
    df["ts"] = pd.to_datetime(df["ts"])
    return df


@lru_cache(maxsize=1)
def load_graph_edges() -> pd.DataFrame:
    _ensure_data()
    df = pd.read_parquet(DATA_DIR / "fgi_graph_edges.parquet")
    df["first_seen"] = pd.to_datetime(df["first_seen"])
    df["last_seen"] = pd.to_datetime(df["last_seen"])
    return df
