---
name: simulate-mission-learner
description: Evaluate a mission with expert, casual, and naive simulated learners using Ada and independent outcome checks. Use to prepare mission evaluation specifications, run simulations, or inspect saved learner evidence.
---

# Simulate Mission Learner

Use the shared [evaluation runner and interpretation guide](../references/evaluation/README.md) and [mission contract](../references/mission-contract.md). This workflow evaluates synthetic learners; it does not run a real learner session or establish human learning.

## Inputs and execution

- Identify mission folders, the selected tutor skill, specification folder, profiles, budgets, and a new output folder. Default to all three profiles and two trials. Use a one-task or one-trial diagnostic only when its narrower purpose is clear.
- Resolve `../references/evaluation/scripts/evaluate.py` relative to this skill, including in copied authoring workspaces. Locate the tutor and toolbox explicitly; they are not copied with the author skills. Reuse `build/evaluation-venv` or follow the pinned setup in the guide. The evaluator uses the qualified Codex runtime regardless of the authoring client.
- If a mission lacks a specification, use offline `learner-sim prepare`. Present the outcomes, alternatives, mistake schedules, probes, and observer limitations for author review. Do not mark review or calibration complete without an author decision. Current pilot observers cover only the two documented stock missions; other missions require observer implementation before execution.
- Run `learner-sim run` independently of the tutor-skill suite. Discover installed MATLAB MCP, Simulink extension/toolkit, and toolbox paths and pass them explicitly. Never use shell MATLAB commands or attach trials to the author's MATLAB session. The runner owns separate contexts, product sessions, evidence, budgets, and cleanup.
- Use `report`, `compare`, or `learner-sim accumulate` for saved results. Accumulate only compatible runs with distinct seeds and the required actual schedule variation. Run both evaluators only when requested, using `combined`; saved composition does not make different runs comparable.

## Human feedback

When a specification, rubric, disputed judgment, or evidence gap needs author judgment, offer the review workflow in [references/human-feedback.md](references/human-feedback.md). Inspect the available file-writing, Python, process/server, browser, and MATLAB MCP capabilities first. Explain the review need, selected method, and exact tools you would use, then wait for the user to choose before generating a bundle or starting a server. Prefer a Python loopback server; use standalone HTML when serving is unavailable, MATLAB MCP generation when Python is unavailable, or JSON plus Markdown when neither generator can run. The bundled example/template and helpers work without development-checkout design files or another visual-style skill.

After the user returns feedback, validate it against the original packet and record item-level decisions and unresolved questions. Propose follow-up edits; review feedback alone does not authorize mission, tutor, or grading-policy changes.

## Explain the result

Separate Ada's acceptance from independently verified outcomes, tutor compliance from learner recovery, and simulated learning proxies from mission completion. Include persona fidelity, stop reasons, infrastructure failures, missing checks, and remaining qualification limits. A provisional specification or incomplete diagnostic cannot qualify a mission.

Keep author review labels distinct from frozen machine outcomes. In particular, the accepted fuller SDI verification does not rewrite the historical independent unknown, and reviewed boundary unknowns are complete decisions. Tentative preferences for passive inspection or separate reference models do not authorize production policy changes. Recommend follow-up work with evidence; do not automatically edit missions, tutor rules, or learner profiles.
