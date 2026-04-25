"""Round-2 remediation: expected-value analysis under cost matrix FN=$500, FP=$5."""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "cost_analysis.json"
FN_COST = 500.0
FP_COST = 5.0


def main():
    metrics = json.load(open(ROOT / "models/metrics.json"))
    seeds = json.load(open(ROOT / "outputs/seed_variance.json"))
    df = pd.read_parquet(ROOT / "data/clean.parquet")

    cm = metrics["confusion_matrix"]
    tn, fp = cm[0][0], cm[0][1]
    fn, tp = cm[1][0], cm[1][1]

    model_cost = fn * FN_COST + fp * FP_COST
    flag_none_cost = (fn + tp) * FN_COST
    flag_all_cost = (tn + fp) * FP_COST

    time_span_sec = df["Time"].max() - df["Time"].min()
    test_days = (time_span_sec / 86400.0) * 0.2
    per_day_savings = (flag_none_cost - model_cost) / test_days

    report = {
        "cost_matrix": {
            "FN_cost_usd": FN_COST,
            "FP_cost_usd": FP_COST,
            "assumptions": "FN = $500 avg fraud loss. FP = 5 analyst minutes @ $1/min = $5.",
        },
        "test_slice_span_days": test_days,
        "observed_confusion_matrix": {"TN": tn, "FP": fp, "FN": fn, "TP": tp, "total": tn + fp + fn + tp},
        "ev_analysis_usd": {
            "model_cost": model_cost,
            "flag_none_cost": flag_none_cost,
            "flag_all_cost": flag_all_cost,
            "savings_vs_flag_none": flag_none_cost - model_cost,
            "savings_vs_flag_all": flag_all_cost - model_cost,
        },
        "per_day_extrapolation_usd": {
            "days_covered_by_test_slice": test_days,
            "savings_per_day_vs_flag_none": per_day_savings,
        },
        "seed_variance_cost_note": (
            f"F1 std={seeds['f1_std']:.4f} across 20 seeds. Worst seed F1={seeds['f1_min']:.4f}. "
            f"Under worst seed, assuming recall drops proportionally, FN count could rise ~25-30% "
            f"(from 16 to ~20), adding ~$2,000 to model_cost per test slice. "
            "This is a material risk vs. the single-seed picture."
        ),
        "headline": (
            f"Model saves ${flag_none_cost - model_cost:,.0f} per test slice (~{test_days:.2f} days) "
            f"vs. flag-nothing baseline. That is ${per_day_savings:,.0f}/day."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2))
    print(report["headline"])


if __name__ == "__main__":
    main()
