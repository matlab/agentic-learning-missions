# Progress Contract

This contract defines learner progress for every supported marketplace adapter.
The learner workspace owns progress; the installed toolbox and marketplace
content remain read-only during normal tutoring.

## Location And Ownership

Regular and resumed sessions write one file:

```text
<learner-workspace>/.interactive-missions/progress.json
```

Practice mode starts without this file. Ada creates it only after the learner
explicitly asks to save progress or resume later. App state under
`prefdir()/InteractiveMissions/app` stores workspace discovery records only;
it is not authoritative learner progress.

## Required Fields

```json
{
  "schemaVersion": "2.0",
  "learnerName": "Ada Lovelace",
  "marketplaceSource": "mathworks-interactive-missions",
  "missionName": "root-inports-outports",
  "missionId": "01",
  "missionVersion": "1.0.0",
  "workspacePath": "C:/Users/example/Documents/MATLAB/Interactive-Missions/root-inports-outports",
  "mode": "regular",
  "currentStepId": "t01",
  "completedStepIds": [],
  "hintCounts": {},
  "updatedAt": "2026-08-31T12:00:00-04:00",
  "notes": ""
}
```

`learnerName` is the exact learner-facing display name. Do not normalize its
case, spacing, or spelling for communication. `hintCounts` records task hint
use, `notes` is a short resume/debrief record, and `updatedAt` records the
latest complete write.

Completion is derived from the mission task IDs and `completedStepIds`. For an
active session, `currentStepId` is the next task. For a completed session,
`currentStepId` is `"complete"` and every required task ID is completed.

## Safety Rules

- Write the complete JSON document when a tracked session starts, a task is
  verified, the learner exits, or the mission completes.
- Never create or update progress during unpromoted practice mode.
- Stop before setup when existing progress is malformed, unreadable, or does
  not match the prepared mission. Do not overwrite it.
- Do not create compatibility files under `progress/<learner-id>.json`.
