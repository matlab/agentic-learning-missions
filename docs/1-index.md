# Mission Author Documentation

Interactive Missions helps authors build learner missions: guided sequences of tasks that learners complete in MATLAB&reg;, Simulink&reg;, or with help from their agentic tool. A mission turns an instructional goal into a practical activity with learner-facing instructions, hints, completion checks, and optional setup code. Learners follow a mission by invoking the `mission-tutoring` skill.

This documentation is for mission authors. It assumes you are comfortable with instructional design and MathWorks tools, but you may be newer to using agentic tools as authoring partners.
## What Authors Create

Authors package mission content under `marketplace/missions/<mission-name>/mission.yaml`. The lowercase mission-folder slug is the stable package identity. The authoring skills handle this structure and help create missions.

 The main artifact is a `mission.yaml`, with fields like
 
- mission folder name: stable lowercase slug used by the marketplace and runtime.
- `title`: learner-facing mission title.
- `objective`: short description of what the learner will be able to do.
- `app`: metadata used by the MATLAB app.
- `tasks`: ordered list of learner tasks.
- `hints`: a sequence of scaffolded hints for the learner

 Some missions also include a MATLAB setup script or reset scripts when learners need prepared
data, models, or task-specific restart states.

## Table of Contents

- [Set Up an Authoring Workspace](2-authoring-workflow.md#1-set-up-an-authoring-workspace) - create a marketplace draft and install agent guidance.
- [Authoring Workflow](2-authoring-workflow.md) - the recommended mission lifecycle from first idea to maintenance.
- [Skill Usage](3-skill-usage.md) - practical guidance for `create-tutor-mission`, `qa-mission`, and `maintain-missions`.
- [Mission YAML Overview](4-mission-yaml-overview.md) - a human-readable tour of the mission YAML structure.
- [How to Author a Mission](5-how-to-author-a-mission.md) - a walkthrough from rough goal to reviewed mission.
- [Runtime Validation](6-runtime-validation.md) - maintainer guidance for setup, reset, progress, and runtime smoke checks.
- [Sharing Missions](7-sharing-missions.md) - marketplace-based sharing, publishing, and cache behavior.
