"""Drift monitor: split clean.parquet by Time median, compare distributions."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean.parquet"
OUT = ROOT / "outputs" / "drift_report.json"

FEATURES = [f"V{i}" for i in range(1, 29)] + ["Amount"]
CLASS_THRESHOLD = 0.001
REL_DELTA_THRESHOLD = 0.25


def load():
    return pd.read_parquet(CLEAN)


def split_by_time_median(df):
    t_median = df["Time"].median()
    baseline = df[df["Time"] <= t_median]
    new_batch = df[df["Time"] > t_median]
    return baseline, new_batch


def compute_shifts(baseline, new_batch):
    baseline_rate = float(baseline["Class"].mean())
    new_rate = float(new_batch["Class"].mean())
    class_shift = {
        "baseline_rate": baseline_rate,
        "new_rate": new_rate,
        "abs_delta": abs(new_rate - baseline_rate),
    }
    feature_shifts = {}
    for col in FEATURES:
        b = float(baseline[col].mean())
        n = float(new_batch[col].mean())
        feature_shifts[col] = {
            "baseline": b,
            "new": n,
            "abs_delta": abs(n - b),
            "rel_delta": (n - b) / (abs(b) + 1e-9),
        }
    return class_shift, feature_shifts


def assemble_report(baseline, new_batch, class_shift, feature_shifts):
    max_rel = max(abs(v["rel_delta"]) for v in feature_shifts.values())
    drift = (class_shift["abs_delta"] > CLASS_THRESHOLD) or (max_rel > REL_DELTA_THRESHOLD)
    drifted_feats = [c for c, v in feature_shifts.items() if abs(v["rel_delta"]) > REL_DELTA_THRESHOLD]
    if drift:
        title = "drift-monitor: distribution shift detected in Time-split batch"
        body = (
            f"Class rate shift: baseline={class_shift['baseline_rate']:.6f} "
            f"new={class_shift['new_rate']:.6f} abs_delta={class_shift['abs_delta']:.6f}. "
            f"Features with |rel_delta|>{REL_DELTA_THRESHOLD}: {drifted_feats}. "
            f"Max |rel_delta|={max_rel:.4f}."
        )
    else:
        title = "drift-monitor: no significant drift"
        body = "No features exceed thresholds."
    return {
        "baseline_rows": int(len(baseline)),
        "new_batch_rows": int(len(new_batch)),
        "class_balance_shift": class_shift,
        "feature_mean_shifts": feature_shifts,
        "drift_detected": bool(drift),
        "pr_stub": {"would_open": bool(drift), "title": title, "body": body},
    }


def main():
    df = load()
    baseline, new_batch = split_by_time_median(df)
    class_shift, feature_shifts = compute_shifts(baseline, new_batch)
    report = assemble_report(baseline, new_batch, class_shift, feature_shifts)
    OUT.write_text(json.dumps(report, indent=2))
    max_rel = max(abs(v["rel_delta"]) for v in report["feature_mean_shifts"].values())
    max_feat = max(report["feature_mean_shifts"].items(), key=lambda kv: abs(kv[1]["rel_delta"]))[0]
    print(json.dumps({
        "baseline_rows": report["baseline_rows"],
        "new_batch_rows": report["new_batch_rows"],
        "class_abs_delta": report["class_balance_shift"]["abs_delta"],
        "max_abs_rel_delta": max_rel,
        "max_rel_delta_feature": max_feat,
        "drift_detected": report["drift_detected"],
    }))


if __name__ == "__main__":
    main()
