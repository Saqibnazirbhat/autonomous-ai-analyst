"""Remediation: 20-seed F1 variance on same stratified 80/20 config."""
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from xgboost import XGBClassifier

IN = r"C:\Users\91946\autonomous-ai-analyst\data\clean.parquet"
OUT = r"C:\Users\91946\autonomous-ai-analyst\outputs\seed_variance.json"
SEEDS = list(range(20))


def fit_one(X, y, seed):
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=seed)
    neg, pos = (y_tr == 0).sum(), (y_tr == 1).sum()
    model = XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        scale_pos_weight=neg / pos, eval_metric="logloss",
        random_state=seed, tree_method="hist", n_jobs=-1,
    )
    model.fit(X_tr, y_tr)
    return float(f1_score(y_te, model.predict(X_te)))


def bootstrap_ci(vals, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    boots = [np.mean(rng.choice(vals, size=len(vals), replace=True)) for _ in range(n)]
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def main():
    df = pd.read_parquet(IN)
    X = df.drop(columns=["Class"])
    y = df["Class"]
    f1s = []
    for s in SEEDS:
        f1 = fit_one(X, y, s)
        f1s.append(f1)
        print(f"seed={s:2d} f1={f1:.4f}")
    mean, std = float(np.mean(f1s)), float(np.std(f1s, ddof=1))
    ci_lo, ci_hi = bootstrap_ci(f1s)
    p_above_bar = float(np.mean([f >= 0.85 for f in f1s]))
    report = {
        "n_seeds": len(SEEDS),
        "f1_per_seed": {str(s): f for s, f in zip(SEEDS, f1s)},
        "f1_mean": mean,
        "f1_std": std,
        "f1_min": float(np.min(f1s)),
        "f1_max": float(np.max(f1s)),
        "bootstrap_ci_95": [ci_lo, ci_hi],
        "original_reported_f1": 0.8586387434554974,
        "f1_bar": 0.85,
        "fraction_seeds_above_bar": p_above_bar,
        "interpretation": (
            f"Across 20 seeds, F1 mean={mean:.4f} std={std:.4f}, "
            f"95% bootstrap CI [{ci_lo:.4f}, {ci_hi:.4f}]. "
            f"{p_above_bar*100:.0f}% of seeds clear the 0.85 bar."
        ),
    }
    with open(OUT, "w") as f:
        json.dump(report, f, indent=2)
    print("---")
    print(f"mean={mean:.4f} std={std:.4f} min={min(f1s):.4f} max={max(f1s):.4f}")
    print(f"95% CI=[{ci_lo:.4f}, {ci_hi:.4f}]  fraction>=0.85: {p_above_bar:.2f}")


if __name__ == "__main__":
    main()
