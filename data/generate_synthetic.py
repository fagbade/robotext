"""
Synthetic data generator for Cheda FGI Operational Results dashboard.
All timestamps are AFTER July 1, 2025 (post-deployment).
"""

import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent
SEED = 42
START_DATE = pd.Timestamp("2025-07-01")
END_DATE = pd.Timestamp("2025-12-31")


def _random_ts(n: int, rng: np.random.Generator) -> pd.DatetimeIndex:
    start_ns = START_DATE.value
    end_ns = END_DATE.value
    ts = rng.integers(start_ns, end_ns, size=n)
    return pd.to_datetime(ts)


def generate_payout_decisions(n: int = 28_000, rng: np.random.Generator = None) -> pd.DataFrame:
    rng = rng or np.random.default_rng(SEED)

    bank_codes = ["044", "058", "011", "033", "057", "215", "232", "035", "301", "076"]
    assets = ["USDT", "USDC", "BTC", "ETH", "NGN"]
    networks = ["TRC20", "ERC20", "BEP20", "POLYGON", "INTERNAL"]
    model_versions = ["v2.1.0", "v2.1.1", "v2.2.0", "v2.2.1"]
    reason_code_pool = [
        "velocity_spike", "new_beneficiary", "dormant_account", "amount_anomaly",
        "graph_cluster_risk", "device_fingerprint_mismatch", "geo_velocity",
        "beneficiary_ring", "high_fan_out", "sanctioned_proximity",
        "unusual_hour", "rapid_succession", "split_structuring",
    ]

    event_ts = _random_ts(n, rng)
    risk_scores = rng.beta(2, 5, size=n) * 100

    decisions = []
    for s in risk_scores:
        if s > 80:
            decisions.append(rng.choice(["BLOCK", "HOLD"], p=[0.7, 0.3]))
        elif s > 55:
            decisions.append(rng.choice(["STEP_UP", "HOLD", "ALLOW"], p=[0.5, 0.3, 0.2]))
        elif s > 30:
            decisions.append(rng.choice(["ALLOW", "STEP_UP"], p=[0.8, 0.2]))
        else:
            decisions.append("ALLOW")

    decisions = np.array(decisions)
    confirmed_bad = np.zeros(n, dtype=bool)

    blocked_idx = np.where(np.isin(decisions, ["BLOCK", "HOLD"]))[0]
    confirmed_bad[blocked_idx] = rng.random(len(blocked_idx)) < 0.70

    allowed_idx = np.where(decisions == "ALLOW")[0]
    confirmed_bad[allowed_idx] = rng.random(len(allowed_idx)) < 0.003

    reason_codes = []
    for s in risk_scores:
        k = max(1, int(s / 25))
        codes = rng.choice(reason_code_pool, size=min(k, 4), replace=False).tolist()
        reason_codes.append(",".join(codes))

    df = pd.DataFrame({
        "payout_id": [f"PO-{i+1:06d}" for i in range(n)],
        "user_id": [f"USR-{rng.integers(1, 6000):05d}" for _ in range(n)],
        "beneficiary_id": [f"BEN-{rng.integers(1, 12000):05d}" for _ in range(n)],
        "bank_code": rng.choice(bank_codes, n),
        "amount_ngn": np.round(rng.lognormal(10, 1.8, n), 2).clip(500, 50_000_000),
        "asset": rng.choice(assets, n, p=[0.35, 0.25, 0.15, 0.10, 0.15]),
        "network": rng.choice(networks, n),
        "event_ts": event_ts,
        "risk_score": np.round(risk_scores, 2),
        "decision": decisions,
        "latency_ms": np.round(rng.lognormal(3.5, 0.6, n), 1).clip(8, 800),
        "model_version": rng.choice(model_versions, n, p=[0.15, 0.25, 0.35, 0.25]),
        "reason_codes": reason_codes,
        "confirmed_bad": confirmed_bad,
    })
    return df.sort_values("event_ts").reset_index(drop=True)


def generate_alerts(payouts_df: pd.DataFrame, rng: np.random.Generator = None) -> pd.DataFrame:
    rng = rng or np.random.default_rng(SEED + 1)

    high_risk = payouts_df[payouts_df["risk_score"] > 45].sample(
        n=min(3500, len(payouts_df[payouts_df["risk_score"] > 45])), random_state=42
    )

    typologies = [
        "structuring", "mule_network", "rapid_movement", "sanctions_proximity",
        "account_takeover", "bvn_mismatch", "dormant_reactivation", "velocity_anomaly",
    ]
    severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    statuses = ["OPEN", "IN_REVIEW", "ESCALATED", "CONFIRMED_FRAUD", "FALSE_POSITIVE", "CLOSED"]
    analysts = [f"analyst_{i}" for i in range(1, 9)]

    n = len(high_risk)
    created_at = high_risk["event_ts"].values + pd.to_timedelta(
        rng.integers(60, 7200, size=n), unit="s"
    )

    status_arr = rng.choice(statuses, n, p=[0.08, 0.10, 0.07, 0.30, 0.25, 0.20])

    closed_at = []
    for i, s in enumerate(status_arr):
        if s in ("CONFIRMED_FRAUD", "FALSE_POSITIVE", "CLOSED"):
            delta = pd.Timedelta(minutes=int(rng.integers(30, 4320)))
            closed_at.append(pd.Timestamp(created_at[i]) + delta)
        else:
            closed_at.append(pd.NaT)

    df = pd.DataFrame({
        "alert_id": [f"ALT-{i+1:06d}" for i in range(n)],
        "entity_type": rng.choice(["user", "beneficiary", "device"], n, p=[0.5, 0.35, 0.15]),
        "entity_id": high_risk["user_id"].values,
        "typology": rng.choice(typologies, n),
        "severity": rng.choice(severities, n, p=[0.10, 0.25, 0.40, 0.25]),
        "created_at": created_at,
        "status": status_arr,
        "analyst_id": rng.choice(analysts, n),
        "closed_at": closed_at,
        "payout_id": high_risk["payout_id"].values,
        "evidence_summary": [
            f"Auto-generated evidence for {t} pattern detected with risk score {s:.0f}"
            for t, s in zip(
                rng.choice(typologies, n),
                high_risk["risk_score"].values,
            )
        ],
    })
    return df.sort_values("created_at").reset_index(drop=True)


def generate_federation_ops(n: int = 5_000, rng: np.random.Generator = None) -> pd.DataFrame:
    rng = rng or np.random.default_rng(SEED + 2)

    client_ids = [f"CLIENT-{i+1:03d}" for i in range(12)]
    statuses = ["ACCEPTED", "ACCEPTED", "ACCEPTED", "REJECTED", "TIMEOUT"]
    global_versions = [f"gv-{v}" for v in range(10, 32)]

    ts = _random_ts(n, rng)
    update_status = rng.choice(statuses, n)

    reasons = []
    for s in update_status:
        if s == "REJECTED":
            reasons.append(rng.choice(["gradient_anomaly", "staleness", "drift_detected", "sentinel_fail"]))
        elif s == "TIMEOUT":
            reasons.append("timeout")
        else:
            reasons.append(None)

    df = pd.DataFrame({
        "ts": ts,
        "client_id": rng.choice(client_ids, n),
        "round_id": np.sort(rng.integers(100, 500, n)),
        "update_status": update_status,
        "rejected_reason": reasons,
        "sentinel_pass": rng.random(n) > 0.12,
        "global_model_version": rng.choice(global_versions, n),
    })
    return df.sort_values("ts").reset_index(drop=True)


def generate_graph_edges(payouts_df: pd.DataFrame, rng: np.random.Generator = None) -> pd.DataFrame:
    rng = rng or np.random.default_rng(SEED + 3)

    edges = []
    edge_types = ["SENT_TO", "RECEIVED_FROM", "SAME_DEVICE", "SAME_BVN", "SHARED_IP", "LINKED_PHONE"]

    sampled = payouts_df.sample(n=min(8000, len(payouts_df)), random_state=42)

    for _, row in sampled.iterrows():
        edges.append({
            "src_type": "user",
            "src_id": row["user_id"],
            "dst_type": "beneficiary",
            "dst_id": row["beneficiary_id"],
            "edge_type": "SENT_TO",
            "weight": round(float(rng.random() * 0.5 + 0.5), 3),
            "first_seen": row["event_ts"] - pd.Timedelta(days=int(rng.integers(0, 30))),
            "last_seen": row["event_ts"],
        })

        if rng.random() > 0.6:
            edges.append({
                "src_type": rng.choice(["user", "beneficiary", "device"]),
                "src_id": row["user_id"],
                "dst_type": rng.choice(["user", "beneficiary", "device"]),
                "dst_id": f"BEN-{rng.integers(1, 12000):05d}",
                "edge_type": rng.choice(edge_types[1:]),
                "weight": round(float(rng.random()), 3),
                "first_seen": row["event_ts"] - pd.Timedelta(days=int(rng.integers(0, 60))),
                "last_seen": row["event_ts"],
            })

    df = pd.DataFrame(edges)
    df["first_seen"] = df["first_seen"].clip(lower=START_DATE)
    df["last_seen"] = df["last_seen"].clip(lower=START_DATE)
    return df.reset_index(drop=True)


def generate_all():
    rng = np.random.default_rng(SEED)

    print("Generating payout decisions...")
    payouts = generate_payout_decisions(28_000, rng)
    payouts.to_parquet(DATA_DIR / "fgi_payout_decisions_fact.parquet", index=False)

    print("Generating alerts...")
    alerts = generate_alerts(payouts, np.random.default_rng(SEED + 1))
    alerts.to_parquet(DATA_DIR / "fgi_alerts_fact.parquet", index=False)

    print("Generating federation ops...")
    fed = generate_federation_ops(5_000, np.random.default_rng(SEED + 2))
    fed.to_parquet(DATA_DIR / "fgi_federation_ops_fact.parquet", index=False)

    print("Generating graph edges...")
    graph = generate_graph_edges(payouts, np.random.default_rng(SEED + 3))
    graph.to_parquet(DATA_DIR / "fgi_graph_edges.parquet", index=False)

    print(f"Done. Files written to {DATA_DIR}")
    print(f"  payouts:    {len(payouts):,} rows")
    print(f"  alerts:     {len(alerts):,} rows")
    print(f"  federation: {len(fed):,} rows")
    print(f"  graph:      {len(graph):,} rows")


if __name__ == "__main__":
    generate_all()
