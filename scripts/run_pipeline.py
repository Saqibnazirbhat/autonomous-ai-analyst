"""Deterministic Python phase of the /go pipeline. Invoked before the 8 debate agents."""
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUTPUTS = ROOT / "outputs"
MODELS = ROOT / "models"
TRACE = ROOT / "trace.jsonl"

STEPS = [
    ("data_engineer.py",      "Phase 1.1 @data-engineer"),
    ("eda_analyst.py",        "Phase 1.2 @eda-analyst"),
    ("prediction_modeler.py", "Phase 1.3 @prediction-modeler"),
    ("drift_monitor.py",      "Phase 1.4 @drift-monitor (rel_delta)"),
    ("drift_shuffle.py",      "Phase 2.1 drift remediation (shuffle + KS)"),
    ("seed_variance.py",      "Phase 2.2 seed variance (20 fits, ~3 min)"),
    ("cost_analysis.py",      "Phase 2.3 cost-matrix EV"),
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def log(entry):
    with open(TRACE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def run_step(name, description, session_id):
    banner = f"=== {description} ==="
    print("\n" + banner)
    t0 = time.time()
    subprocess.run([sys.executable, str(SCRIPTS / name)], cwd=str(ROOT), check=True)
    dt = time.time() - t0
    print(f"[{dt:.1f}s] {name} ok")
    log({"timestamp": now(), "agent": "go-orchestrator", "action": "step-complete",
         "session_id": session_id, "step": name, "duration_seconds": round(dt, 2)})


def assemble_pipeline_output():
    metrics = json.load(open(MODELS / "metrics.json"))
    drift = json.load(open(OUTPUTS / "drift_report.json"))
    out = {
        "clean_data_path": "data/clean.parquet",
        "feature_columns": metrics["feature_columns"],
        "target_column": metrics["target_column"],
        "train_test_split": {"train_rows": metrics["train_rows"], "test_rows": metrics["test_rows"]},
        "model_path": "models/model.pkl",
        "model_metrics": {k: metrics[k] for k in ("f1", "precision", "recall", "auc")},
        "drift_detected": drift["drift_detected"],
    }
    (OUTPUTS / "pipeline_output.json").write_text(json.dumps(out, indent=2))
    assert metrics["f1"] >= 0.85, f"F1 gate failed: {metrics['f1']:.4f} < 0.85"
    print(f"pipeline_output.json written (F1={metrics['f1']:.4f})")


def main():
    session_id = uuid.uuid4().hex
    t0 = time.time()
    log({"timestamp": now(), "agent": "go-orchestrator", "action": "start",
         "session_id": session_id, "input_summary": "full deterministic python phase: ML + remediation"})

    # ML phase (4 scripts)
    for name, desc in STEPS[:4]:
        run_step(name, desc, session_id)
    assemble_pipeline_output()

    # Remediation phase (3 scripts)
    for name, desc in STEPS[4:]:
        run_step(name, desc, session_id)

    total = time.time() - t0
    log({"timestamp": now(), "agent": "go-orchestrator", "action": "success",
         "session_id": session_id, "total_seconds": round(total, 2), "steps_run": len(STEPS)})
    print(f"\n=== Python pipeline complete in {total:.1f}s. Ready for debate agents. ===")


if __name__ == "__main__":
    main()
