---
name: go
description: Runs the full Autonomous AI Analyst pipeline end to end — deterministic ML + remediation via scripts/run_pipeline.py, then the two-round debate (bull → bear → devil → judge, then v2), then rewrites outputs/impact_report.md. Use when the user types /go, asks to "run the pipeline", "kick off the whole thing", "run the demo", or wants a reproducible end-to-end execution.
---

# /go — full pipeline, one command

Execute the following phases in order. Stop and surface any failure immediately — do not silently skip steps. Each numbered step maps to one of the CLAUDE.md "what done looks like" criteria.

## Phase 1 — deterministic Python (one subprocess)

Run: `python scripts/run_pipeline.py` from the project root.

This chains the seven Python scripts and asserts F1 ≥ 0.85 before returning:

1. `data_engineer.py` → `data/clean.parquet`
2. `eda_analyst.py` → `outputs/eda_summary.json` + 4 charts in `outputs/charts/`
3. `prediction_modeler.py` → `models/model.pkl` + `models/metrics.json`
4. `drift_monitor.py` → `outputs/drift_report.json` (rel_delta — artifact preserved for audit)
5. (in-process) assemble `outputs/pipeline_output.json` from metrics + drift
6. `drift_shuffle.py` → `outputs/drift_shuffle.json` (random-shuffle rel_delta + KS)
7. `seed_variance.py` → `outputs/seed_variance.json` (20 XGBoost fits, ~3 min)
8. `cost_analysis.py` → `outputs/cost_analysis.json` (FN=$500 / FP=$5 EV)

The orchestrator writes start + step-complete + success entries to `trace.jsonl`.

**Fail-fast:** if any script errors or F1 < 0.85, stop the whole `/go` and surface. Do not proceed to debate.

## Phase 2 — round-1 debate

Spawn in this order, using the `general-purpose` agent type (the named subagent types register only on session reload). Authoritative contracts live in `.claude/agents/{bull,bear,devils,judge}-analyst.md` — reference them in the prompt rather than duplicating.

1. `@bull-analyst` and `@bear-analyst` **in parallel** (single message, two Agent tool calls). Inputs: `outputs/pipeline_output.json`, `outputs/eda_summary.json`, `models/metrics.json`, and (bear only) `outputs/drift_report.json`. Each returns an ArgumentObject JSON — persist to `outputs/arg_bull.json` and `outputs/arg_bear.json`.
2. `@devils-advocate` sequentially (reads bull + bear + all pipeline artifacts). Persist to `outputs/arg_devil.json`.
3. `@judge` sequentially (reads the three ArgumentObjects + pipeline/metrics/drift). Returns a Verdict with non-empty `dissent_note` and `human_approval_required` per the rule. Persist to `outputs/verdict.json`.

**Persistence note:** subagents in this environment currently have Write/Edit/Bash denied. Each debate agent returns a JSON object in its reply; persist from the main session and mark `"note": "persisted from main session; subagent denied write tools"` in the start trace entry. Schema-validate each ArgumentObject and the Verdict before moving on.

For each agent, append start + success entries to `trace.jsonl` using the format:
`{"timestamp": "<iso8601 UTC>", "agent": "<role>", "action": "start|success", "session_id": "<uuid4 hex>", "input_summary": "..."}`.

## Phase 3 — round-2 remediation debate

This round addresses devil v1's three critiques using the empirical files produced in Phase 1 steps 6–8.

1. `@bull-analyst v2` and `@bear-analyst v2` **in parallel**. Bull cites `seed_variance.json` CI + `cost_analysis.json` EV + `drift_shuffle.json` artifact proof. Bear re-scores under the cost matrix and must honestly narrow its position if EV dominates. Persist to `outputs/arg_bull_v2.json` / `outputs/arg_bear_v2.json`.
2. `@devils-advocate v2` sequentially. It must acknowledge resolved v1 concerns and surface new load-bearing gaps (candidates: concept drift on P(Y|X), predict_proba calibration, temporal-split validation). Persist to `outputs/arg_devil_v2.json`.
3. `@judge v2` sequentially. Outputs `outputs/verdict_v2.json`. If the judge overrides the mechanical `human_approval_required` rule (e.g. because `pipeline_output.drift_detected=true` is known stale from the shuffle control), require the override to be documented in `dissent_note` — don't allow silent bypass.

## Phase 4 — impact report

Rewrite `outputs/impact_report.md` from scratch using the round-1 template (sections 1–7) and append the §8 "Round 2 — Debate Remediation" section. All numbers must come from the JSON files regenerated this run, not from memory. Preserve the shape:

- §1 metrics table + confusion matrix
- §2 drift check with rel_delta artifact caveat
- §3 round-1 debate summary + dissent note
- §4 governance trail (trace entry count, artifact inventory)
- §5 estimated cost per run (token-based; note the count depends on spawn usage this run)
- §6 ROI sketch
- §7 devil v1 next-steps list
- §8 round-2 remediation: new artifacts table, confidence deltas, judge override, final deploy recommendation, devil v2 preserved dissent, updated cost

## Phase 5 — report-back

End the `/go` invocation with a short summary to the user:
- F1 achieved
- Round-1 winner + confidence
- Round-2 winner + confidence + delta
- Final deploy recommendation from verdict_v2
- Artifact inventory count (`trace.jsonl` lines, `outputs/*.json` files)
- Estimated USD cost of this run

## Hard stops (non-negotiable)

- If `run_pipeline.py` exits non-zero: surface stdout/stderr and stop. Do NOT spawn debate agents.
- If F1 in `models/metrics.json` < 0.85: stop. Do NOT retry from the skill — escalate to the user.
- If any debate agent returns malformed JSON: reject, re-prompt once with the schema, then stop if still malformed.
- If `verdict.json` or `verdict_v2.json` has an empty `dissent_note`: reject the verdict and re-spawn the judge. A judge verdict with empty dissent violates CLAUDE.md and cannot be persisted.

## Cost and wall-time budget

- Python phase: ~4–5 min (seed_variance dominates at ~3 min)
- 8 debate-agent spawns: ~5–8 min
- Total: ~10 min, ~$9 at Claude Opus list price (assumes no cache hits)

If the user wants a cheaper run, they can spawn only Phase 1 by invoking `python scripts/run_pipeline.py` directly — that satisfies the deterministic portion of the DONE checklist without LLM spend.
