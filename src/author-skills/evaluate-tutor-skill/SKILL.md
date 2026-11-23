---
name: evaluate-tutor-skill
description: Evaluate a mission-tutoring skill version against controlled cases and optional live MATLAB checks. Use for tutor behavior regressions, triggering, or teaching-quality evaluation.
---

# Evaluate Tutor Skill

Use the shared [evaluation runner and interpretation guide](../references/evaluation/README.md). This is an author evaluation workflow, not a learner tutoring session or permission to revise tutor policy.

## Inputs and execution

- Identify the tutor skill folder, case selection, behavior/live layers, output folder, and optional baseline. Use the 15 accepted cases and two trials by default; narrow scope when the user requests a diagnostic. A behavior-only run requires no MATLAB execution.
- Resolve `../references/evaluation/scripts/evaluate.py` relative to this skill. In a copied authoring workspace, use its copied resources rather than assuming a development checkout. Locate the selected tutor in the installed toolbox or an explicit author snapshot; author workspaces do not include the production tutor automatically.
- Reuse `build/evaluation-venv` when present, or follow the pinned setup in the guide. Execution uses the Codex SDK even if a different authoring client invokes this skill. Workspace adapter support is not evaluator runtime qualification.
- Run `skill-eval` with explicit inputs. For live checks, discover installed MATLAB MCP and toolbox paths, then pass them to the runner. Never launch MATLAB through shell MATLAB commands or attach trials to the author's MATLAB session. The runner owns isolation, budgets, logging, grading, and cleanup.
- Do not run learner simulation as a prerequisite. Use `combined` only when both evaluations are requested. Use `report` or saved-run composition for existing evidence; do not rerun agents merely to render a report.

## Explain the result

Report executed cases, behavior/live coverage, pass/fail/unknown counts, readiness, evidence paths, and infrastructure or cleanup failures. Keep baseline/candidate comparisons subject to the runner's compatibility checks. Identical tutor snapshots demonstrate repeatability, not improvement.

Distinguish incorrect evaluator judgments from tutor or mission defects. Evaluation findings propose work; they do not authorize automatic fixes. Preserve provisional calibration flags, accepted case limitations, task-scoped review labels, and historical grades. A reviewed unknown can be a completed author decision. Agreement on reviewed labels does not establish accuracy on unseen traces.
