# Learner Simulation Workflow

This workflow is for **content authors and educators** evaluating a mission with Ada and simulated learners. Use [`simulate-mission-learner`](../../src/author-skills/simulate-mission-learner/SKILL.md) to prepare a specification, run learner profiles, and review saved evidence. You can use this workflow on its own; tutor evaluation is not a prerequisite.

**Review the mission → Prepare and review its specification → Run learner profiles → Interpret outcomes → Give feedback → Decide follow-up work.**

[Back to evaluation workflows](README.md)

## Table of contents

- [Decide whether to simulate](#decide-whether-to-simulate)
- [Prepare inputs](#prepare-inputs)
- [Prepare and review a specification](#prepare-and-review-a-specification)
- [Choose profiles and run](#choose-profiles-and-run)
- [Interpret results](#interpret-results)
- [Respond to feedback requests](#respond-to-feedback-requests)
- [Decide next steps](#decide-next-steps)

## Decide whether to simulate

Use this workflow after [mission QA](../3-skill-usage.md#qa-mission), after changing tasks or hints, or when investigating learner difficulty or unclear completion checks. It helps you see how learners with different levels of topic knowledge attempt the mission, respond to Ada, and recover from mistakes.

Use QA first when your question is about content clarity or consistency. Use [framework and runtime validation](../6-runtime-validation.md) when checking setup, reset, progress, or infrastructure. Simulations provide evidence about synthetic learners; they do not establish human learning or replace testing with people.

## Prepare inputs

Work from the repository root and give the agent:

- **Your question:** the teaching goal, change, or learner difficulty you want to examine.
- **Mission folders:** include each `mission.yaml` and its mission-owned content.
- **The tutor folder:** normally `src/skills/mission-tutoring`, or an explicit saved version. You select the tutor to use; you do not need to modify it.
- **A specification location:** provide an existing matching specification or ask the agent to prepare a draft for your review.
- **Profiles, scope, output, and budget:** choose a diagnostic or broader run, use a new folder under `build/evaluations/`, and ask for the planned coverage and limits before execution.

If your client does not discover the skill by name, include `src/author-skills/simulate-mission-learner/SKILL.md` in your prompt. Ask the agent to check the [evaluation environment setup](../../src/author-skills/references/evaluation/README.md#setup). The skill uses the pinned Codex runner even when another authoring client invokes it. Specification preparation is offline and needs no MATLAB execution. Simulation needs the documented MATLAB MCP and Simulink toolkit environment; the runner uses separate evaluation workspaces and owned MATLAB sessions. Check the guide's qualification limits before using a different environment.

## Prepare and review a specification

The input is your mission folder, including `mission.yaml` and its content. The first output is a draft evaluation specification in JSON. It defines the expected outcomes, acceptable alternatives, planned mistakes, recovery expectations, explanation and transfer questions, and grading criteria.

```text
Use simulate-mission-learner at src/author-skills/simulate-mission-learner/SKILL.md.
Prepare a draft evaluation specification for marketplace/missions/root-inports-outports.
Save it under build/evaluations/mission-specs/ and present it for my review.
Explain any missing independent checks before proposing a simulation run.
```

Review whether the specification reflects your teaching goals and accepts valid solutions. An **independent check** inspects the learner's product state rather than relying on Ada's assessment. Ask what it can and cannot verify. Review the grading criteria as well as the task outcomes; your decision is needed before review or calibration can be recorded as complete.

The current observers support **Root Inports and Outports** and **Continuous and Discrete Time**. Other missions can receive draft specifications, but need an observer implementation before simulation can run. A specification also belongs to an exact mission version. After changing mission content, prepare and review a specification that matches it.

## Choose profiles and run

| Profile | What it explores |
| --- | --- |
| Expert | Accurate, independent work and responses to real ambiguity. |
| Casual | Skipped or skimmed steps, partial attempts, and recovery from feedback. |
| Naive | A learner who meets the prerequisites but is new to the topic and needs more guidance. |

The default uses all three profiles and two trials per profile. A one-task or one-trial diagnostic answers a narrower question and cannot qualify the whole mission.

```text
Use simulate-mission-learner to evaluate marketplace/missions/root-inports-outports
with src/skills/mission-tutoring and the specification in build/evaluations/mission-specs/.
Use all three profiles and two trials per profile.
Write results to build/evaluations/root-ports-review.
Report independent outcomes, learner recovery, profile fidelity, readiness, and limitations.
```

For confirming evidence, casual and naive trials must use different actual mistake schedules. Different seed numbers alone do not ensure this. Ask the agent to identify any missing coverage in its results. See [learner simulation commands](../../src/author-skills/references/evaluation/README.md#run-learner-simulations-independently) for budgets and execution options.

## Interpret results

Start with `report.md` in the output folder. Follow its evidence links when a result is surprising or needs a human decision.

| Artifact | What you use it for |
| --- | --- |
| Draft specification JSON | Review what the mission evaluation will test and how it will judge the results. |
| `report.md` | Read coverage, results, readiness, limitations, and evidence references. |
| `benchmark.json` | Inspect detailed trial results and summaries. |
| `inputs/` and `manifest.json` | Identify the exact versions, settings, and environment used. |
| Per-trial `events.jsonl` and `grading.json` | Inspect what happened and why a judgment was made. Runs also include an `actions.jsonl` view and saved product files when available. |

Interpret the report in this order:

1. **Was the planned work completed?** Check missing trials, stop reasons, timeouts, tool errors, and cleanup failures. Partial evidence is not a successful full run.
2. **What was observed?** A pass covers the checked behavior. A fail records an observed problem. Unknown means the evidence or check cannot support a firm result; it is not a pass.
3. **Does the evidence meet the readiness bar?** Passed trials alone are insufficient. Readiness also depends on coverage, reviewed specifications and grading criteria, calibration, and confirming trials.
4. **What does the result mean for your question?** In learner runs, distinguish Ada accepting a task from independently verified completion. Check tutor compliance, learner recovery, and profile fidelity separately. Explanation and transfer scores are simulated learning proxies; they do not demonstrate human learning.

A missing check or infrastructure failure may require evaluator work rather than a mission or tutor fix. Current observers do not establish desktop usability or every valid alternative. Ask for evidence before assigning a cause. The technical guide explains [learner results and readiness](../../src/author-skills/references/evaluation/README.md#learner-outputs-and-interpretation) in more detail.

## Respond to feedback requests

An agent asks for feedback when the next decision needs your instructional or technical judgment.

| Request | Your role |
| --- | --- |
| Review a specification | Decide whether outcomes, alternatives, mistakes, and checks fairly represent the mission. |
| Review grading criteria or examples | Decide whether the proposed judgments reflect good teaching and valid completion. |
| Resolve a disputed judgment | Read the cited evidence and decide whether it supports pass, fail, or unknown. |
| Resolve an evidence gap | Identify what is missing and whether another check or run would help. |

When offering a dashboard, the agent explains why review is needed, which tools it can use, and the proposed method. It waits for your choice before generating the review bundle or starting a local server. Choosing the review method is separate from accepting its proposals.

1. **Choose a method.** Use the offered dashboard or file-based review. Standalone HTML is an option when a local server is unavailable.
2. **Review each item.** Read the question and evidence. Use the offered decisions, such as `accept`, `revise`, or `discuss`, or `pass`, `fail`, or `unknown`. Add reasons and questions; decisions other than `accept` require a note.
3. **Save your feedback.** Export feedback JSON from the dashboard, or save the edited feedback template as a separate file. Browser drafts are temporary. Partial reviews are valid; unfinished items stay pending.
4. **Return it to the agent.** Give both the original packet path and feedback path. Keep the original packet unchanged so the agent can verify which questions you answered.

```text
Read the original review packet at <packet-path> and my feedback at <feedback-path>.
Validate the feedback and record my decisions with reasons and evidence references.
Summarize unresolved items and propose follow-up edits for review.
Preserve the historical machine results.
```

The agent checks the feedback against the packet and records how it handled each item. A reasoned `unknown` can be a completed human decision even while evaluation readiness remains insufficient. Your feedback records a judgment; it does not automatically authorize changes to missions, tutor rules, or grading policy.

See the [human-feedback guide](../../src/author-skills/simulate-mission-learner/references/human-feedback.md) for dashboard use, file-based review, export, and feedback validation.

## Decide next steps

Use the evidence to choose a specific follow-up: revise instructions or hints, clarify completion checks, improve an independent observer, review a grading judgment, or gather more evidence. Ask the agent to propose the change and a confirming simulation. Authorize edits separately.

If the evidence suggests a tutor defect, share the cited trace and finding with the repo maintainer. The [tutor evaluation workflow](evaluate-tutor-skill.md) can help investigate that behavior. You can continue reviewing your mission without running that workflow yourself.

Reuse saved evidence when you only need a report, comparison, or review. Reports can be rebuilt without rerunning Ada, learners, or MATLAB. Compatible learner runs can be accumulated for confirming coverage. Keep the source folders because derived reports may link to them.

Use the runner's compatibility checks when comparing or accumulating results. If the mission, specification, tutor, or grader changed, ask which comparisons are supported. Do not present incompatible runs as a controlled baseline comparison.

Keep original results, human decisions, and later confirming runs distinct. Agreement with reviewed examples is useful calibration evidence; it does not establish grading accuracy on unseen conversations.
