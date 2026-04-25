"""EDA analyst: clean.parquet -> eda_summary.json + 4 PNGs."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "clean.parquet"
OUT_DIR = ROOT / "outputs"
CHARTS_DIR = OUT_DIR / "charts"
SUMMARY_PATH = OUT_DIR / "eda_summary.json"
TARGET = "Class"
FEATURE_COLS = [f"V{i}" for i in range(1, 29)] + ["Amount", "Time"]


def load():
    df = pd.read_parquet(DATA_PATH)
    assert TARGET in df.columns, "Class column missing"
    for c in FEATURE_COLS:
        assert c in df.columns, f"{c} missing"
    return df


def compute_summary(df):
    counts = df[TARGET].value_counts()
    n0 = int(counts.get(0, 0))
    n1 = int(counts.get(1, 0))
    total = n0 + n1
    class_balance = {"0": n0, "1": n1, "fraud_rate": float(n1 / total)}
    corrs = df[FEATURE_COLS + [TARGET]].corr()[TARGET].drop(TARGET)
    class_corr = {c: float(corrs[c]) for c in FEATURE_COLS}
    ordered = corrs.abs().sort_values(ascending=False)
    top_features = [
        {"name": name, "abs_corr_with_class": float(ordered[name])}
        for name in ordered.index[:10]
    ]
    return {
        "class_balance": class_balance,
        "top_features": top_features,
        "correlations": {"class_corr": class_corr},
    }


def plot_class_balance(df, path):
    counts = df[TARGET].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["0 (non-fraud)", "1 (fraud)"], counts.values, color=["#4C72B0", "#C44E52"])
    ax.set_yscale("log")
    ax.set_ylabel("count (log scale)")
    ax.set_title("Class balance")
    for i, v in enumerate(counts.values):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_amount_by_class(df, path):
    fig, ax = plt.subplots(figsize=(6, 4))
    data = [df.loc[df[TARGET] == 0, "Amount"].values,
            df.loc[df[TARGET] == 1, "Amount"].values]
    ax.boxplot(data, tick_labels=["0 (non-fraud)", "1 (fraud)"], showfliers=True)
    ax.set_yscale("symlog")
    ax.set_ylabel("Amount (symlog)")
    ax.set_title("Amount by Class")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_top_corr(summary, path):
    names = [f["name"] for f in summary["top_features"]][::-1]
    vals = [f["abs_corr_with_class"] for f in summary["top_features"]][::-1]
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.barh(names, vals, color="#55A868")
    ax.set_xlabel("|corr with Class|")
    ax.set_title("Top 10 features by |corr with Class|")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_heatmap(summary, path):
    class_corr = summary["correlations"]["class_corr"]
    cols = FEATURE_COLS
    vals = np.array([[class_corr[c] for c in cols]])
    fig, ax = plt.subplots(figsize=(12, 2.2))
    sns.heatmap(vals, annot=True, fmt=".2f", cmap="coolwarm", center=0,
                xticklabels=cols, yticklabels=["corr w/ Class"],
                cbar_kws={"shrink": 0.7}, ax=ax)
    ax.set_title("Feature correlations with Class")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    df = load()
    summary = compute_summary(df)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2))
    plot_class_balance(df, CHARTS_DIR / "class_balance.png")
    plot_amount_by_class(df, CHARTS_DIR / "amount_by_class.png")
    plot_top_corr(summary, CHARTS_DIR / "top_corr_features.png")
    plot_heatmap(summary, CHARTS_DIR / "correlation_heatmap.png")
    print("rows:", len(df))
    print("class_balance:", summary["class_balance"])
    print("top3:", summary["top_features"][:3])


if __name__ == "__main__":
    main()
