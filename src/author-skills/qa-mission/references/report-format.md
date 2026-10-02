# Report Format Reference

Use this reference before presenting QA findings, proposing fixes, or asking
whether to save the report.

## Stage 1 Output

Present findings as a markdown checklist grouped by priority:

```markdown
## Quality Report: <mission-name> - "<title>"

### Stage 1: Static Analysis

#### High Priority
- [ ] **QA-<mission-name>-001** (tNN, category) Description of the issue. Evidence: `<mission-name>.yaml`, task tNN.
      *Fix available* | *Subjective - no auto-fix*

#### Medium Priority
- [ ] **QA-<mission-name>-002** (tNN, category) Description of the issue. Evidence: declared setup script and resulting learner state.
      *Fix available* | *Subjective - no auto-fix*

#### Low Priority
- [ ] **QA-<mission-name>-003** (mission, category) Description of the issue. Evidence: `<mission-name>.yaml`, top-level metadata.
      *Fix available* | *Subjective - no auto-fix*
```

## Stage 2 Output

Append Stage 2 findings to the same report format, continuing the issue ID
sequence:

```markdown
### Stage 2: MCP-Assisted Analysis

#### High Priority
- [ ] **QA-<mission-name>-004** (setup, execution) Setup script fails: <error message>
      *Fix available*

#### Medium Priority
- [ ] **QA-<mission-name>-005** (t04, library_path) Hint 3 references 'simulink/Sinks/Scope2'
      which does not exist in the current MATLAB installation.
      *Fix available*
```

## Priority Assignment

- **High** - Learner will get stuck or fail, including missing prerequisites,
  impossible completion criteria, and broken variable references.
- **Medium** - Learner might be confused or the mission violates design
  principles, including instructional mismatch or weak hints.
- **Low** - Minor clarity improvements or style nits.

## Issue IDs

Use `QA-<mission-name>-<three-digit-sequence>`, such as `QA-root-inports-outports-001`. Assign IDs
sequentially across both stages.

## Fix Labels

Use `*Fix available*` for non-subjective items where an exact edit is clear.
Use `*Subjective - no auto-fix*` when the finding requires author judgment.

## Interaction

After presenting findings:

1. For items marked *Fix available*, prepare a proposed diff showing old text to
   new text.
2. Ask the user: **"Apply fixes? Enter issue IDs (e.g., `1,3,5`) or `all` for
   non-subjective items. Or `skip` to continue without changes."**
3. If the user provides IDs, apply those fixes using the available repo editing
   tools after showing the diff for each.
4. If the user says `skip` or `none`, ask:
   **"Save this report to `qa_<mission-name>.md`?"**
5. After Stage 2, offer to save the combined report.
