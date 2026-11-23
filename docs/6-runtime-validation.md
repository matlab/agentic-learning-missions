# Runtime Validation

`tests/validate_runtime.m` validates runtime behavior that static
YAML and packaging checks cannot prove. By default it runs infrastructure-only
checks so maintainers can validate progress handling without executing mission
setup or reset scripts.

Run it through the MATLAB&reg; MCP Server after a successful MATLAB MCP handshake in
the current agent session. Do not rerun the handshake if this session has
already confirmed MCP connectivity:

```matlab
disp("MATLAB MCP handshake: interactive-missions")
addpath("tests")
validate_runtime
```

Useful scopes:

```matlab
validate_runtime
validate_runtime(pwd, "Scope", "infrastructure")
validate_runtime(pwd, "Scope", "missions", "Mission", "all")
validate_runtime(pwd, "Scope", "missions", "Mission", "root-inports-outports")
validate_runtime(pwd, "Scope", "all", "Mission", "all")
```

The validator checks:

- Infrastructure checks cover progress JSON fixtures for new, resumed,
  completed, malformed, and practice-mode states.
- Mission content tests discover packaged `marketplace/missions/<mission-name>/mission.yaml` files, run declared
  setup scripts when present, and run reset scripts when the matching
  `task_reset_<mission-name>` folder exists.
- Missions without setup scripts or reset folders are valid; those runtime steps
  are skipped explicitly.
- Runtime scripts must not change the current folder, permanently alter the
  MATLAB path, or create repository progress files.
- Optional `runtime_expectations` metadata supplies mission-owned behavioral
  assertions for setup and reset states.

The mission content checks are skipped when Simulink&reg; is unavailable.
Infrastructure checks still run because they use temporary JSON fixtures outside
the repository.

`runtime_expectations` validates repeatable task-start state. It does not define learner completion or replace fresh task verification. Completion checks for simulation, figures, Simulation Data Inspector, and configuration must inspect current learner-owned state and keep unavailable or conflicting inspection results unverified.

## Runtime Expectations Metadata

Mission YAML can include a top-level `runtime_expectations` block. It declares the expected state after setup and each reset; `validate_runtime.m` executes those assertions. Supported
assertion types are:

- `workspace_var`: base workspace variable exists; optional `class`.
- `workspace_absent`: base workspace variable does not exist.
- `model_loaded`: Simulink model is loaded.
- `block_exists`: block path exists; optional `block_type`.
- `block_param`: block or model parameter equals `equals` or one of `any_of`.
- `line_source`: destination block input is connected from `source`.
- `figure_count`: at least `min_new_figures` figures were created.
- `matlab_expression`: logical MATLAB expression with a `description`.

String fields may use `${varName}` substitution, resolved from scalar string or
char variables in the base workspace after setup or reset execution.

## Failure Modes

- Missing MATLAB MCP Server: stop and alert the user so they can choose to start
  or restart the MCP server, or proceed with the Python static validator only.
  Mark runtime validation as not run if Python fallback is used.
- Missing Simulink: mission content validation reports a Simulink skip; do not
  treat setup/reset execution as validated.
- Missing Simulink Agentic Toolkit: Ada must stop before setup because task
  completion checks cannot be observed reliably.
- Setup failure: the learner session must not continue because the first task
  state is unavailable.
- Reset failure: resume from that task is unreliable until the reset script is
  fixed.
- Malformed progress file: Ada must stop before setup, preserve the file, and
  offer practice mode or a different learner name.
- Mission mismatch or missing mission file: Ada must stop before setup rather
  than silently starting a different regular mission.

## Generated Reset States

Handwritten reset scripts remain the supported production strategy. Generated
reset states need a separate feasibility prototype that can prove the generated
state is equivalent to the handwritten task start state before any replacement
is considered.

## Tutor-Skill Evaluation

The [standalone tutor-skill harness](../src/author-skills/references/evaluation/README.md) executes the unchanged learner tutor against controlled conversations and live MATLAB state. It adds agent-behavior evidence beyond the framework and infrastructure validators. It runs independently of the learner simulator and supports frozen baseline/candidate comparisons, per-trial JSONL traces, deterministic assertions, and separate qualitative grading.

The initial cases use a small MATLAB scalar-variable fixture. Qualitative grading remains provisional until author calibration. These synthetic author evaluations do not enable production learner-session logging or change the supported-client matrix.
