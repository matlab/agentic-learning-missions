# Tutor Evaluation Workflow

This workflow is for **repo maintainers** checking Ada, the mission tutor. Use [`evaluate-tutor-skill`](../../src/author-skills/evaluate-tutor-skill/SKILL.md) to evaluate a selected tutor version against controlled cases and optional live MATLAB checks. Continue with [learner simulation](simulate-mission-learner.md) when you want evidence about how that tutor works across full missions.

**Choose scope → Prepare inputs → Run tutor cases → Review results and feedback → Continue with learner simulation.**

[Back to evaluation workflows](README.md)

## Table of contents

- [Choose scope](#choose-scope)
- [Prepare inputs](#prepare-inputs)
- [Run the tutor evaluation](#run-the-tutor-evaluation)
- [Interpret results](#interpret-results)
- [Give feedback](#give-feedback)
- [Continue with learner simulation](#continue-with-learner-simulation)

## Choose scope

Use this workflow after a tutor change, to investigate a reported behavior, or before a release review. Typical questions concern hint timing, assessing completion, handling inspection errors, or respecting learner ownership.

Choose a targeted diagnostic when investigating one behavior. Choose broader coverage when reviewing a tutor version. The controlled cases use small scalar mission fixtures; they test tutor rules and teaching behavior. Learner simulation adds evidence about interactions across full missions.

## Prepare inputs

Work from the repository root and give the agent:

- **Your question:** the change or concern and the evidence you need.
- **The tutor folder:** normally `src/skills/mission-tutoring`, or an explicit saved version. A regression comparison also needs the previous version or a compatible saved run.
- **Cases and layers:** behavior, live MATLAB, or both; identify any diagnostic case selection.
- **A new output folder and time budget:** use a fresh folder under `build/evaluations/`. Ask for a summary of planned coverage, runtime needs, and limits before execution.

If your client does not discover the skill by name, include `src/author-skills/evaluate-tutor-skill/SKILL.md` in your prompt. Ask the agent to check the [evaluation environment setup](../../src/author-skills/references/evaluation/README.md#setup). The skill uses the pinned Codex runner even when another authoring client invokes it. Behavior-only checks need no MATLAB execution; live checks need the documented MATLAB MCP environment and run in separate evaluation workspaces and owned MATLAB sessions. Check the guide's qualification limits before using a different environment.

## Run the tutor evaluation

1. **Choose the tutor version and question.** For a regression check, identify the previous and candidate versions explicitly.
2. **Choose coverage.** Behavior cases use controlled conversations and observations. Live cases use real MATLAB state. The default suite has 15 accepted cases: 14 behavior cases and one live case, with two trials per case. Request behavior-only coverage if that answers your question.
3. **Run the selected evaluation.** A targeted case or one-trial run can help diagnose an issue. Its limited coverage cannot establish the broader readiness bar.
4. **Read the report and evidence.** Check which cases ran, which layers were covered, and whether failures came from the tutor, the evaluator, or infrastructure.

Example behavior check:

```text
Use evaluate-tutor-skill at src/author-skills/evaluate-tutor-skill/SKILL.md.
Evaluate src/skills/mission-tutoring with the behavior layer and two trials per case.
Write results to build/evaluations/tutor-behavior-review.
Summarize coverage, findings, readiness, and limitations.
```

Example regression comparison; replace the baseline placeholder with your saved tutor folder:

```text
Use evaluate-tutor-skill to compare <baseline-tutor-folder> with src/skills/mission-tutoring.
Use the same cases and runtime for both versions and a new output folder.
Report supported comparisons and link each behavior change to its evidence.
```

Two identical tutor versions test repeatability. They cannot show improvement. See [tutor evaluation commands and outputs](../../src/author-skills/references/evaluation/README.md#run-tutor-skill-evaluations) for detailed options.

## Interpret results

Start with `report.md` in the output folder, then follow its evidence links.

| Artifact | What you use it for |
| --- | --- |
| `report.md` | Read case and layer coverage, outcomes, readiness, and limitations. |
| `benchmark.json` | Inspect trial results and configuration summaries. |
| `comparison.json`, when comparing versions | Inspect supported baseline/candidate comparisons. |
| `inputs/` and `manifest.json` | Identify the exact tutor, cases, settings, and environment used. |
| Per-trial `events.jsonl` and `grading.json` | Inspect what Ada said or did and why a judgment was made. |

First check that the planned trials completed. Missing trials, timeouts, tool errors, and cleanup failures can leave insufficient evidence. A pass covers the checked behavior; a fail records an observed problem; unknown means the evidence cannot support a firm result.

Read **readiness** separately from trial outcomes. Passed trials alone are insufficient when coverage, confirming trials, or grading calibration are missing. The current tutor suite retains provisional calibration limits. Agreement with reviewed examples does not establish grading accuracy on unseen conversations.

For surprising findings, distinguish a tutor defect from an incorrect evaluator judgment or infrastructure failure. Ask the agent to cite the conversation and tool evidence before proposing a cause. See [tutor outputs and interpretation](../../src/author-skills/references/evaluation/README.md#skill-evaluation-outputs-and-offline-commands) for details.

## Give feedback

You may be asked to review case definitions, teaching criteria, a disputed judgment, or missing evidence. Decide whether the proposed expectation is fair and whether the evidence supports the result. A reasoned unknown can be a completed human decision while readiness remains insufficient.

When offered a dashboard or file-based review, choose the method, read each item, record decisions and reasons, and save the feedback. Exported JSON is the durable handoff; browser drafts are temporary. Return the original packet path and your feedback path to the agent. Partial reviews are valid. Keep the original packet unchanged.

```text
Read the original review packet at <packet-path> and my feedback at <feedback-path>.
Validate the feedback and record my decisions with reasons and evidence references.
Summarize unresolved items and propose follow-up edits for review.
Preserve the historical machine results.
```

The agent records your decisions alongside the original results. Feedback does not automatically authorize changes to the tutor or grading policy. See the [human-feedback guide](../../src/author-skills/simulate-mission-learner/references/human-feedback.md) for review methods and the handoff contract.

## Continue with learner simulation

After reviewing tutor cases, use the [learner simulation workflow](simulate-mission-learner.md) to check the selected tutor against representative missions. It explains how to prepare and review mission specifications, select learner profiles, and interpret independent outcomes. Use the same tutor version when both evaluations address that version. A tutor evaluation failure does not block simulation; the two reports answer different questions.

Use the evidence to propose a specific change and a confirming evaluation. Authorize edits separately. Preserve original machine results, human decisions, and subsequent runs.

Reuse saved runs when you only need a report or comparison. For tutor comparisons, hold other evaluation inputs fixed and respect the runner's compatibility checks. An [optional combined report](../../src/author-skills/references/evaluation/README.md#optional-combined-workflow) can bring tutor and learner results together without rerunning agents. It preserves separate readiness and results, provides no single quality score, and does not make different versions comparable. Keep the source folders because derived reports may link to them.
