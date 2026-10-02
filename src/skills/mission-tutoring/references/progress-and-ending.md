# Progress And Ending

Load `status-reporting.md` before any learner-visible progress or ending update.
Keep routine progress reads and writes silent. Send a standalone status report
only when saving, completion, or early exit fails or creates a visible delay;
keep the debrief or early-exit response in a separate Ada message.

Regular and resumed sessions use `.interactive-missions/progress.json`. Practice mode must not read or write progress until the learner explicitly asks to save or resume later. That request requires a learner display name, creates the same file, changes `mode` to `regular`, and continues from the current task.

The progress document uses schema version 2.0 and includes `learnerName`, `marketplaceSource`, `missionName`, `missionId`, `missionVersion`, `workspacePath`, `mode`, `currentStepId`, `completedStepIds`, `hintCounts`, `updatedAt`, and `notes`. Preserve `learnerName` exactly as the learner sees it. For a regular session, an empty `learnerName` is valid only before the learner has started Task 1 and before any completed task is saved. Write the complete document after saving the required learner name, a verified task, early exit, or completion.

If an existing file is malformed, unreadable, or mismatched to the prepared
mission, stop before setup. Do not overwrite it. Offer practice mode or a newly
prepared workspace.

On completion, congratulate the learner and connect the debrief to the mission
objective, completed artifacts, and any high-hint tasks. On early exit, save
tracked progress and say exactly which task will resume next.
