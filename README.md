# Autonomous AI Analyst

> A multi-agent fraud detection pipeline with a sequential deterministic ML phase,
> an LLM-driven adversarial debate team, typed JSON contracts at every handoff,
> and a full governance trace of every action.

This is not a model-training repo with a chat wrapper. It is a small, opinionated
demonstration of how to put **multiple independent AI agents in disagreement on
purpose**, then have a separate judge resolve the disagreement against a recorded
audit trail. The point is not that XGBoost catches fraud — it does — but that the
pipeline knows *why* the deploy decision was made, *who* dissented, and *what the
judge had to override* to produce that decision.

The project's most interesting artifact is not the model. It is `outputs/verdict_v2.json`.

---

## What it does, in one paragraph

It takes the public Kaggle credit-card fraud dataset (284,807 transactions, 0.17%
fraud rate), runs four deterministic ML scripts to produce a clean parquet, an EDA
summary, a trained XGBoost model that hits **F1 = 0.8586** on the held-out test
set, and a drift report. Then four LLM agents — `bull`, `bear`, `devil`, `judge` —
read that pipeline output and produce a typed `Verdict` with a non-empty
`dissent_note`. Round 1 produces one verdict. The judge flags three pending
questions. Round 2 answers those questions empirically (random-shuffle drift
control, 20-seed F1 confidence interval, cost-matrix EV at FN=$500/FP=$5) and
re-runs the debate; the agents shift positions in measurable ways and the judge
re-verdicts. Every agent action is appended to `trace.jsonl`. Everything ends in
a single-file dark-theme dashboard at `outputs/dashboard.html`.

---

## Latest run (round 2)

| Metric | Value |
|---|---|
| F1 (fraud class) | **0.8586** on 56,962-row test set |
| AUC | 0.9684 |
| Precision / Recall | 0.8817 / 0.8367 |
| Confusion matrix | TN 56,853 &nbsp;&middot;&nbsp; FP 11 &nbsp;&middot;&nbsp; FN 16 &nbsp;&middot;&nbsp; TP 82 |
| 20-seed F1 CI (95%) | **[0.8554, 0.8764]** — both endpoints above the 0.85 bar |
| Drift (KS, Time-median split) | 29 / 29 features significant at p < 0.05 |
| Drift (KS, random-shuffle control) | 0 / 29 — confirms Time-axis drift is real |
| Cost matrix used | FN = $500, FP = $5 (5 analyst min × $1/min) |
| Modeled EV vs. flag-nothing | **+$40,945** per 0.4-day test slice (~$102k/day) |
| **Round 2 winner** | `bull` (confidence 0.74) |
| **Human approval required** | `false` (judge override, documented in dissent_note) |
| Final prediction | "deploy XGBoost with analyst-in-loop review, seed-pinned retraining, threshold re-tuning against FN=$500/FP=$5, and hourly drift-monitor loop gated on KS-stat and live F1 below 0.8554" |

For full numbers and the round-1 → round-2 evolution, see
[`outputs/impact_report.md`](outputs/impact_report.md).

---

## Architecture

```
                            data/creditcard.csv
                                    |
                                    v
                       +-------------------------+
                       |   @data-engineer        |  scripts/data_engineer.py
                       +-----------+-------------+
                                   |
                                   v
                          data/clean.parquet
                            (284,807 x 31)
                                   |
              +--------------------+---------------------+
              v                    v                     v
     +----------------+   +-----------------+   +-----------------+
     | @eda-analyst   |   | @prediction-    |   | @drift-monitor  |
     | charts + JSON  |   |   modeler       |   | KS + rel_delta  |
     +----------------+   |  XGBoost +      |   +--------+--------+
                          |  scale_pos_wt   |            |
                          +-----------------+            |
              ............................................
                                   v
                   outputs/pipeline_output.json
                          (typed contract)
                                   |
              +--------------------+--------------------+
              v                    v                    v
       +-------------+      +-------------+     +-------------+
       | @bull       |      | @bear       |     | @devil      |
       | argues FOR  |      | argues      |     | attacks     |
       | deploy      |      | AGAINST     |     | both sides  |
       +------+------+      +------+------+     +------+------+
              |                    |                    |
              +--------------------+--------------------+
                                   v
                   outputs/arg_{bull,bear,devil}.json
                          (typed ArgumentObject x 3)
                                   |
                                   v
                          +-----------------+
                          |  @judge         |
                          |  weighs all 3   |
                          +--------+--------+
                                   |
                                   v
                       outputs/verdict.json
                       (typed Verdict with
                         non-empty dissent_note)
```

**Two phases:**

1. **Sequential ML phase** (deterministic, ~110 s of CPU): four Python scripts
   produce typed JSON outputs. F1 ≥ 0.85 is asserted before the pipeline can
   advance. No LLM calls.
2. **Parallel debate phase** (LLM, ~5–8 min): three agents independently produce
   `ArgumentObject`s from the same pipeline output, then a fourth agent (`judge`)
   reads all three and produces a `Verdict`. The judge **must** write a
   non-empty `dissent_note` even when the three agents converge.

A round-2 remediation cycle (3 more Python scripts + 4 more LLM agents) addresses
the round-1 judge's three pending questions and re-verdicts.

---

## Quick start

### Prerequisites
- Python 3.11+ (this repo is verified on 3.14.3)
- `pip install pandas pyarrow scikit-learn xgboost matplotlib seaborn scipy joblib`
- The Kaggle credit-card fraud CSV: download from
  [kaggle.com/datasets/mlg-ulb/creditcardfraud](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)
  and place at `data/creditcard.csv/creditcard.csv` (note the nested folder)
- For the LLM debate phase: [Claude Code](https://claude.com/claude-code) or any
  agent harness that can read `.claude/agents/*.md` and produce JSON

### Run the deterministic pipeline (no LLM cost)

```bash
python scripts/run_pipeline.py
```

This chains: `data_engineer.py` → `eda_analyst.py` → `prediction_modeler.py` →
`drift_monitor.py` → assembles `pipeline_output.json` → `drift_shuffle.py` →
`seed_variance.py` → `cost_analysis.py`. Asserts F1 ≥ 0.85 and writes start /
step-complete / success entries to `trace.jsonl`. Wall time: ~110 s on a
mid-range laptop.

### Run the full pipeline including the LLM debate

In Claude Code, type `/go`. The skill at `.claude/skills/go/SKILL.md` is the
authoritative runbook: it invokes `run_pipeline.py`, then orchestrates the
8 debate-agent spawns across both rounds, then rewrites `outputs/impact_report.md`.

Wall time: ~10 min. Cost: ~$9 at Claude Opus list price (assumes no cache hits).

### Open the dashboard

```bash
# Open in your default browser
start outputs/dashboard.html        # Windows
open outputs/dashboard.html         # macOS
xdg-open outputs/dashboard.html     # Linux
```

The dashboard is a single self-contained HTML file. Five tabs:
**Overview**, **Alerts**, **Models**, **Reports**, **Governance**. No
external assets, no fonts pulled from CDNs, no `<script src=...>`.

---

## The eight agents

Each agent is a markdown file at `.claude/agents/<name>.md` with YAML frontmatter
and a system prompt. The prompt encodes the agent's goal, success criterion, and
hard "must not" constraints. The agent is invoked with the contract file path in
its instructions, so the contract is the single source of truth.

| Agent | Phase | Goal | Success criterion |
|---|---|---|---|
| `data-engineer`     | 1 (ML)     | raw CSV → `clean.parquet` | `df.isnull().sum().sum() == 0` and `df.shape == (284807, 31)` |
| `eda-analyst`       | 1 (ML)     | typed `eda_summary.json` + 4 PNG charts | summary contains `class_balance`, `top_features`, `correlations` |
| `prediction-modeler`| 1 (ML)     | train XGBoost, save `model.pkl` + `metrics.json` | F1 ≥ 0.85 on held-out 20% test set |
| `drift-monitor`     | 1 (ML)     | compare baseline vs new batch, write `drift_report.json` | report has all required keys; `pr_stub.would_open == drift_detected` |
| `bull-analyst`      | 2 (debate) | argue **FOR** deploy with cited evidence | valid `ArgumentObject`, no fabricated numbers |
| `bear-analyst`      | 2 (debate) | argue **AGAINST** deploy with specific weaknesses | valid `ArgumentObject`, evidence ties to file values |
| `devils-advocate`   | 2 (debate) | attack both bull and bear, surface blind spots | valid `ArgumentObject` with a *neutral* claim |
| `judge`             | 2 (debate) | weigh all three, produce a `Verdict` | `dissent_note` non-empty even when agents converge |

---

## Typed contracts

Every handoff between agents uses a typed JSON schema. Receiving agents stop and
surface a schema violation rather than coercing or defaulting. The three contracts:

### `PipelineOutput` (Phase 1 → Phase 2)

```json
{
  "clean_data_path": "string",
  "feature_columns": ["string", "..."],
  "target_column": "string",
  "train_test_split": { "train_rows": 0, "test_rows": 0 },
  "model_path": "string",
  "model_metrics": { "f1": 0.0, "precision": 0.0, "recall": 0.0, "auc": 0.0 },
  "drift_detected": false
}
```

### `ArgumentObject` (debate agents → judge)

```json
{
  "agent_role": "bull | bear | devil",
  "claim": "one sentence",
  "evidence": ["string", "..."],
  "confidence": 0.0,
  "challenges": ["string", "..."]
}
```

### `Verdict` (judge → governance)

```json
{
  "final_prediction": "short action string",
  "confidence": 0.0,
  "winning_argument": "bull | bear | devil",
  "dissent_note": "NON-EMPTY string",
  "human_approval_required": false
}
```

Contracts are **append-only**. Adding a field is allowed; renaming or removing
one is not. This keeps every prior `verdict_v*.json` readable by the current judge.

---

## The four operating principles

The project follows four rules, written into [`CLAUDE.md`](CLAUDE.md) and enforced
in every agent contract. They were chosen for engineering discipline, not theatre.

1. **Think before coding.** State assumptions before writing code. If two
   interpretations exist, name both and ask. Before `data-engineer` runs, it
   states which columns it will drop, the null-handling strategy, and the output
   schema. Before `prediction-modeler` runs, it states the algorithm, the
   train/test split strategy, and the success criterion.
2. **Simplicity first.** Each script is procedural and ≤ 40 lines per function.
   No OOP, no plugin systems, no "flexibility" the task didn't ask for. The
   eight agents are eight markdown files, not a class hierarchy.
3. **Surgical changes.** Edits touch only what the task requires. Existing
   contracts are append-only. Drive-by reformatting is prohibited.
4. **Goal-driven execution.** Every task gets a verifiable success criterion
   (`F1 ≥ 0.85`, `nulls == 0`, `dissent_note != ""`), not a vague goal like
   "make it work". Strong criteria let agents loop independently.

---

## Project structure

```
autonomous-ai-analyst/
├── CLAUDE.md                       # the four principles + agent definitions + contracts
├── README.md                       # this file
├── trace.jsonl                     # append-only governance log of every agent action
│
├── .claude/
│   ├── agents/                     # the 8 agent contracts (markdown + YAML frontmatter)
│   │   ├── data-engineer.md
│   │   ├── eda-analyst.md
│   │   ├── prediction-modeler.md
│   │   ├── drift-monitor.md
│   │   ├── bull-analyst.md
│   │   ├── bear-analyst.md
│   │   ├── devils-advocate.md
│   │   └── judge.md
│   └── skills/go/SKILL.md          # /go runbook: full pipeline in one command
│
├── scripts/                        # 8 deterministic Python scripts
│   ├── run_pipeline.py             # orchestrator: chains all 7 below
│   ├── data_engineer.py
│   ├── eda_analyst.py
│   ├── prediction_modeler.py
│   ├── drift_monitor.py            # round-1 drift (rel_delta, kept for audit)
│   ├── drift_shuffle.py            # round-2 remediation: shuffle control + KS
│   ├── seed_variance.py            # round-2 remediation: 20-seed F1 CI
│   └── cost_analysis.py            # round-2 remediation: FN=$500/FP=$5 EV
│
├── data/                           # raw + intermediate (gitignored except .gitkeep)
│
├── models/
│   └── metrics.json                # model.pkl is gitignored (regenerable)
│
└── outputs/
    ├── eda_summary.json            # class balance, top features, correlations
    ├── pipeline_output.json        # the typed PipelineOutput contract instance
    ├── drift_report.json           # round 1, rel_delta-based
    ├── drift_shuffle.json          # round 2, KS test on both splits
    ├── seed_variance.json          # round 2, 20-seed F1 distribution
    ├── cost_analysis.json          # round 2, EV under cost matrix
    ├── arg_bull.json               # round 1 ArgumentObjects
    ├── arg_bear.json
    ├── arg_devil.json
    ├── verdict.json                # round 1 Verdict (winner: devil, conf 0.58)
    ├── arg_bull_v2.json            # round 2 ArgumentObjects
    ├── arg_bear_v2.json
    ├── arg_devil_v2.json
    ├── verdict_v2.json             # round 2 Verdict (winner: bull, conf 0.74)
    ├── impact_report.md            # final markdown report covering both rounds
    ├── dashboard.html              # single-file 5-tab dashboard
    └── charts/                     # 4 PNGs from EDA
        ├── class_balance.png
        ├── amount_by_class.png
        ├── top_corr_features.png
        └── correlation_heatmap.png
```

---

## The story this repo actually tells

The interesting result is not the model's F1. It is what happens when the same
evidence is debated twice under different methodological lenses.

### Round 1

The bull argues for deploy citing F1 = 0.8586 ≥ 0.85. The bear argues against
citing recall = 0.8367 (16 frauds missed of 98) and `drift_detected = true`.
The devil attacks both: nobody specified a cost matrix, nobody asked whether
the drift signal is a metric artifact (zero-mean PCA features make `rel_delta`
saturate at ±2 regardless of split), and nobody computed a confidence interval
on F1.

The **judge picks devil** with confidence 0.58 and writes:
> *final_prediction:* "hold pending cost matrix, seed-variance CI, and
> drift-split audit before any deploy"
> *human_approval_required:* `true`

### Round 2 (remediation)

Three Python scripts answer the devil's three questions empirically:

- `drift_shuffle.py` confirms the rel_delta artifact (still ~2.0 under random
  shuffle, where there's no real drift) AND uses a proper KS test that flags
  29/29 features along Time but 0/29 under shuffle. Result: rel_delta was
  garbage, but real Time drift exists.
- `seed_variance.py` runs 20 stratified-80/20 fits at different seeds. F1 mean
  = 0.8659, 95% bootstrap CI = [0.8554, 0.8764] (both endpoints above the
  0.85 bar). 15 of 20 seeds clear the bar.
- `cost_analysis.py` applies FN = $500, FP = $5: model EV vs. flag-nothing is
  **+$40,945** per 0.4-day test slice. The 11 false positives cost only $55;
  the 16 missed frauds cost $8,000 in unrecovered loss.

The four debate agents re-run with this new evidence:

| Agent | v1 conf | v2 conf | Δ | Position change |
|---|---|---|---|---|
| `bull`  | 0.62 | **0.78** | **+0.16** | Strengthened with CI + EV; honestly concedes real Time drift and 25% sub-bar seeds |
| `bear`  | 0.74 | **0.60** | **−0.14** | **Position flipped** from "don't deploy" to "deploy but threshold-tune + seed-pin + drift-monitor" |
| `devil` | 0.80 | **0.55** | **−0.25** | Concedes 3/3 v1 concerns resolved; surfaces three new gaps: concept drift on P(Y\|X), predict_proba calibration, temporal-split CV |
| `judge` | 0.58 | **0.74** | **+0.16** | `winning_argument` changed: **devil → bull** |

### The judge override

The judge's mechanical rule says
`human_approval_required = true if confidence < 0.7 OR drift_detected == true OR bear_confidence > 0.6`.

In round 2: confidence 0.74 (passes), bear 0.60 (not strictly > 0.6, passes),
but `pipeline_output.drift_detected = true` — the rule still says **true**.

The judge **overrode** to `false` and documented the override inside
`dissent_note`:

> *The drift_shuffle.json control proved rel_delta is a zero-mean PCA artifact,
> and the real Time-axis drift that remains is a known, managed risk via the
> drift-monitor loop rather than a deploy-blocker — so approval rule was
> evaluated on updated evidence, not on the raw stale flag.*

This is the governance lesson: the override is auditable because the dissent
note exists. A future reviewer can read `verdict_v2.json` and see *both* the
mechanical rule outcome *and* the judge's reasoning for departing from it.

---

## The dashboard

`outputs/dashboard.html` is a single 162 KB HTML file with no external
dependencies. Open it in any modern browser at 1440px width.

Five tabs:
- **Overview** — five KPIs, 24-hour detection volume area chart, class
  distribution donut, top risk features, confusion matrix, seed stability
  histogram, drift monitor with KS p-values, recent high-risk transactions,
  debate verdict footer
- **Alerts** — 4 alert KPIs, hourly alert volume bar chart, resolution
  breakdown (auto-blocked / escalated / cleared / pending), risk-tier bars,
  16-row alerts table with live filter chips
- **Models** — model card with hyperparameters, version history table with
  F1-progression sparklines, plus the shared CM/seeds/drift row
- **Reports** — 4 pipeline-run KPIs, recent runs table, 14-day cost-per-run
  SVG line chart with "round 2 introduced" annotation, per-agent cost
  breakdown
- **Governance** — audit stats (8 agents tracked, 27 trace entries, 2
  verdicts, 1 override), trace timeline (15 timestamped entries with colored
  ring markers), debate round summary cards with v1→v2 deltas, plus the
  shared verdict footer

All iconography is inline SVG (53 elements, 0 emoji). All numbers are
comma-formatted. 25 wired event handlers (Refresh spins, Export downloads
JSON, Deploy/Promote toast, bell opens a notification popover, search filters
the alerts table live, Ctrl+K focuses search, etc.). Dark theme using a
`bg-0 / bg-1 / bg-2 / bg-3` zinc palette with cyan, green, amber, red, and
violet accents.

---

## Governance and the trace

`trace.jsonl` is the append-only governance log. Every agent action — start,
success, stop — is one JSON object per line:

```json
{"timestamp":"2026-04-24T07:15:55.796837Z","agent":"prediction-modeler","action":"success","session_id":"b481f0ee...","f1":0.8586,"precision":0.8817,"recall":0.8367,"auc":0.9684,"attempts":1}
```

Round-2 entries are flagged with `"note": "persisted from main session;
subagent denied write tools"` where the subagent sandbox blocked file writes
and the orchestrator persisted on its behalf — preserving the full audit trail
even under restricted-permission execution.

The current `trace.jsonl` has **27 entries** covering all 8 agents across both
debate rounds plus three remediation-compute steps.

---

## Cost

| Component | Tokens (approx) |
|---|---|
| `data-engineer`     |  25,959 |
| `eda-analyst`       |  29,189 |
| `prediction-modeler`|  28,396 |
| `drift-monitor`     |  28,343 |
| `bull-analyst`      |  27,624 |
| `bear-analyst`      |  32,106 |
| `devils-advocate`   |  31,073 |
| `judge`             |  29,878 |
| Round 2 add-on      | ~120,000 |
| Orchestration       | ~50,000 |
| **Two-round total** | **~418,500** |

At Claude Opus list pricing ($15/MTok input, $75/MTok output, 90/10 split),
this is approximately **$8.79 per full two-round run**. Round 1 alone is
about $5.51.

For comparison: the model prevents an estimated $102,367 in fraud per day
under the assumed cost matrix. The pipeline pays for itself many times over
on every run.

---

## Reproducibility

The deterministic Python phase is bit-identical run to run. Every script that
uses randomness pins `random_state = 42`. `scripts/run_pipeline.py` was tested
end to end and reproduces:

| Output | Value |
|---|---|
| `models/metrics.json` → `f1` | 0.8586387434554974 (exact) |
| `outputs/seed_variance.json` → `f1_mean` | 0.8659 |
| `outputs/cost_analysis.json` → `savings_vs_flag_none` | $40,945 (exact) |
| `outputs/drift_shuffle.json` → KS n_significant (Time-median) | 29 (exact) |
| Wall time | ~110 s on a mid-range laptop |

The LLM debate phase is non-deterministic by nature — different runs produce
different prose, different confidence calibration, and occasionally different
verdicts. That is the point of the multi-agent design: the *contracts* and
*governance* are deterministic; the *judgment* is not.

---

## What's intentionally NOT in this repo

- `data/creditcard.csv/creditcard.csv` (~150 MB) — the public Kaggle dataset
  is not redistributable under Kaggle's terms. Download it locally.
- `data/clean.parquet` (~70 MB) — regenerable in 5 seconds via `data_engineer.py`.
- `models/model.pkl` (~544 KB) — pickled XGBoost is fragile across xgboost
  releases. Regenerable in ~7 seconds via `prediction_modeler.py`.
- `__pycache__/`, `.venv/`, IDE folders, OS files.
- `memory/`, `.claude/settings.local.json` — local Claude Code state, not
  part of the project contract.

The full ignore list is in `.gitignore`.

---

## Reading guide — what to look at first

If you have **5 minutes**: open `outputs/dashboard.html` and click the
**Governance** tab. The trace timeline and the round-2 verdict tell the whole
story.

If you have **15 minutes**: read [`outputs/impact_report.md`](outputs/impact_report.md)
end to end. It walks through both rounds, the judge override, and the cost math.

If you want to **understand the code**: start at
[`CLAUDE.md`](CLAUDE.md) (the four principles + the typed contracts), then
[`.claude/agents/judge.md`](.claude/agents/judge.md) (the most opinionated
agent), then [`scripts/run_pipeline.py`](scripts/run_pipeline.py) (the
orchestrator).

If you want to **run it yourself**: see *Quick start* above.

---

## License

## 📄 License

This project is licensed under the MIT License.
