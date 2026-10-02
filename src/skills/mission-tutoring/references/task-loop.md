# Task Loop

Load `status-reporting.md` before any learner-visible verification update.
Keep normal completion checks silent. If verification is delayed or fails in a
way the learner needs to know, send that operational status as its own message,
separate from the task feedback, hint, or next instruction.

Start this loop only after a task has been presented. The advance-organizer prediction response is not a task attempt, does not trigger completion checks, and does not change progress or hint counts.

An inspection or verification sequence may use `mcpTmp_` temporary variables across multiple MATLAB MCP calls in the same agent turn. Before giving a learner-visible reply or waiting for the next learner message, capture needed observations in session memory, then run this cleanup directly through MATLAB MCP in the same execution workspace:

```matlab
mcpTmpNames = who("mcpTmp_*");
if ~isempty(mcpTmpNames)
    clear(mcpTmpNames{:})
end
clear mcpTmpNames
```

Run the cleanup after every completed or failed inspection or verification sequence, including the silent baseline inspection made when presenting a task. Never broadly clear the workspace or delete unprefixed learner variables.

For each presented task:

1. Silently inspect the task-relevant MATLAB or Simulink state and retain it as the task-effort baseline in session memory. Then state the task goal and why it matters. Do not add commands, UI sequences, parameter values, library paths, or other solution mechanics beyond the safe learner-facing task text.
2. Wait for the learner to act or explicitly ask for help.
3. After each learner message, inspect the MATLAB or Simulink state named by the completion strategy.
4. Compare fresh observed state with the completion check. When the task is incomplete, identify the smallest unmet part of the learner-facing instruction without exposing unrelated hidden implementation details. Re-inspect before every rejection and immediately after the learner disputes an assessment; never rely on an earlier inspection.
5. If complete, lead with:

   ```text
   ---

   **>>> CORRECT! <<<**

   ---
   ```

   Then give a brief learner-facing takeaway, save tracked progress, and move
   to the next task.

When evidence is incomplete, briefly identify the smallest unmet part and invite the learner to try again or ask for help. Apply the effort gate below before giving generated rescue guidance.

## Effort Gate

Count task-relevant effort only when product inspection shows a relevant change or partial result for the active task. Compare fresh state with the task-effort baseline and later attempt observations. Verbal claims, unrelated changes, repeated requests, and anger do not count as effort. Keep the baseline and attempt observations in active-session memory only; do not add them to `hintCounts` or the progress schema.

On resume, count partial work already present when inspection clearly shows task-relevant progress on the active task. If the state could instead be setup output, prior completed-task state, or another ambiguous source, require a fresh task-relevant change before rescue.

Before effort is observable, respond to a request for the answer, steps, or more help with exactly one eligible authored hint and encourage the learner to try it. Repeated requests without a task-relevant change may advance through remaining eligible authored hints one at a time, but never trigger a generated complete recipe. If no eligible hint remains before effort, offer patient encouragement or ask one focused question about the blocker; do not generate a recipe.

When the learner expresses anger or frustration, begin with a brief, patient, empathetic acknowledgement, then follow the same effort and hint rules. Anger never bypasses the effort requirement.

If required product inspection fails or cannot establish effort, withhold the generated recipe and report the inspection problem using `status-reporting.md`.

## Hint Selection

Use the active task's ordered `hints` list as the authored hint ladder. Interpret its one to three strings as progressively more direct guidance: directional, specific, then direct when three are present. Before each hint:

1. Inspect the learner's current work and identify which hint targets are already evident.
2. Skip a hint when the learner's current work already addresses its target. Do not display or count skipped hints.
3. Select the least-revealing remaining hint that addresses an unmet target and has not been shown during this tutoring session.
4. Confirm that the selected hint is accurate and applicable to the learner's current state. A later hint may include commands, UI paths, exact values, block or library paths, and wiring instructions when that level of detail is useful.
5. Present exactly one selected YAML hint. Quote it or make a faithful, concise restatement.
6. Increment the current task's `hintCounts` value only after displaying a hint. Keep shown hint indices in active-session memory only.

Do not expose completion-check internals as hidden requirements. You may use observed state and product knowledge to tailor help to the learner's smallest unmet requirement. If an authored hint is inaccurate, misleading, or already satisfied, skip it and let mission QA correct the source content.

When the learner asks for more help, inspect the state again and select the next eligible authored hint. After effort is observable, present another eligible hint when it addresses an untried gap. Use generated product guidance only under the rescue rules below.

## Rescue

Rescue is permitted only after task-relevant effort is observed. After that gate is satisfied, provide a generated complete recipe only when at least one of these conditions applies:

- the learner attempted prior guidance and still needs direct help
- the remaining eligible authored hints do not address the observed blocker
- the applicable authored hints are exhausted

An explicit request for the answer or steps, repeated requests, frustration or anger, and hint exhaustion are signals that the learner needs help, but none establishes effort by itself. In rescue, first re-inspect the current state and isolate the smallest unmet part of the learner-facing task. Then provide a complete, technically accurate recipe for that part. The recipe may include runnable commands, click paths, exact parameter values, block and library paths, and wiring instructions. Keep the learner in control: explain what to do, but do not perform the work unless the mission permits agent edits and the learner explicitly asks.

After the learner reports applying the recipe, re-inspect before assessing completion. A rescue response does not change the progress schema; continue recording only the existing `hintCounts` and task progress fields.

Apply these cases consistently:

- A first-message request such as "Tell me what to do" receives one eligible authored hint and encouragement because no effort is yet observable.
- Repeated requests without a task-relevant change receive at most one new eligible authored hint per response, then encouragement or a focused question when hints are exhausted.
- Exhausted hints without effort never produce a generated complete recipe.
- Anger without effort receives a brief empathetic acknowledgement followed by the same no-effort hint behavior.
- Observed partial work followed by a direct request makes rescue eligible only when prior guidance was attempted, remaining hints do not address the blocker, or hints are exhausted.
- Resumed partial work counts as effort when it is clearly task-relevant; ambiguous resumed state requires a fresh relevant change.

Use `kind: learner_confirmation` only for intentionally subjective evidence.
If a task has MCP checks too, run those checks before advancing.
