# QA Examples

These examples show the style of findings `qa-mission` should produce. They are not complete mission files; they are focused fixtures for reviewer judgment and future automated checks.

## Missing Outcome Mapping

Problem:

```yaml
learning_outcomes:
  - id: lo01
    description: "Configure a root inport to use workspace data."

tasks:
  - id: "t01"
    title: "Map the root inport"
    instruction: "Configure the inport to use respiratoryData."
    completion:
      strategy:
        - tool: evaluate_matlab_code
          check: "ExternalInput references respiratoryData"
      description: "The model uses respiratoryData as input."
    hints:
      - "Look in model settings."
```

Expected finding:

```markdown
- [ ] **QA-root-inports-outports-001** (t01, learning_outcomes) Task t01 appears to teach `lo01`,
      but it has no `outcome_refs` entry. Evidence: `<mission-name>.yaml`, task t01.
      *Fix available*
```

Suggested fix:

```yaml
outcome_refs: [lo01]
```

## Weak Hint Ladder

Problem:

```yaml
hints:
  - "Use the Scope."
  - "Use the Scope."
  - "Use the Scope."
```

Expected finding:

```markdown
- [ ] **QA-root-inports-outports-002** (t04, hints) All three hints repeat the same guidance, so a
      stuck learner does not get additional support or a useful recovery path.
      Evidence: `<mission-name>.yaml`, task t04.
      *Subjective - no auto-fix*
```

QA should flag hints when they are duplicated, contradictory, insufficient, disconnected from the completion criteria, incorrectly ordered by disclosure, or technically inaccurate. A later hint is not a defect merely because it contains a command, UI path, exact value, library path, wiring step, or complete recipe.

## Unsupported Completion Tool

Problem:

```yaml
completion:
  strategy:
    - tool: inspect_simulink_model
      check: "model contains a root-level Inport block"
  description: "The model has an Inport."
```

Expected finding:

```markdown
- [ ] **QA-root-inports-outports-003** (t02, completion) Completion strategy uses unsupported MCP
      tool `inspect_simulink_model`. Evidence: `<mission-name>.yaml`, task t02.
      *Fix available*
```

Suggested fix:

```yaml
tool: model_read
```

## Unobservable Articulation Outcome

Problem:

```yaml
learning_outcomes:
  - id: lo01
    description: "Articulate the difference between continuous time and discrete time."

tasks:
  - id: "t01"
    title: "Create a continuous source"
    outcome_refs: [lo01]
    instruction: "Add a Sine Wave block and run the model."
    completion:
      strategy:
        - tool: model_read
          check: "model contains a Sine Wave block"
      description: "The model contains a continuous source."
    hints:
      - "Use a Sine Wave block."
```

Expected finding:

```markdown
- [ ] **QA-root-inports-outports-004** (t01, learning_outcomes) `lo01` says the learner can
      articulate a conceptual difference, but the task only asks them to build
      model structure and does not ask for an explanation. Evidence:
      `<mission-name>.yaml`, task t01.
      *Subjective - no auto-fix*
```
