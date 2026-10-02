# Author FAQ

## General information

> **What is an Interactive Mission?**

An Interactive Mission is a short, guided activity in MATLAB, Simulink, or any other toolbox that has MATLAB MCP Server tools. It gives learners a goal, a sequence of tasks, hints, and checks their work. The learner's agentic client takes on the personality of Ada, who is designed to be helpful but encourage the learners to work out their own solutions.

> **Who is Ada?**

Ada is the name of the agentic tutor (a nod to [Ada Lovelace](https://en.wikipedia.org/wiki/Ada_Lovelace), of course). Ada starts with scaffolded authored hints and adapts to inspected learner state. Before task-relevant effort is observable, direct requests, repeated requests, frustration, and exhausted hints receive another eligible authored hint or patient encouragement, not a generated complete recipe. After effort, Ada can provide procedural rescue when prior guidance was attempted, remaining hints do not fit the blocker, or applicable hints are exhausted.

> **Can Ada create or edit learner files?**

Missions are read-only by default. Set `allow_agent_edits: true` only when the mission explicitly teaches learners to ask the agent to create or revise files in the learner’s safe workspace (this is useful when teaching an agentic workflow). Mission content, setup and reset scripts, toolbox files, marketplace files, and progress files remain protected.

`write_mode` and `capability_mode` are required classification metadata consumed by validators and the catalog. `allow_agent_edits` is the separate runtime permission consumed by workspace preparation and Ada; it is optional and defaults to `false`.

> **What setup do I need before I start authoring?**

You need the Interactive Missions app, a supported agentic client such as Codex or Claude Code, and the appropriate MathWorks agentic toolkits installed and running ([MATLAB Agentic Toolkit](https://github.com/matlab/matlab-agentic-toolkit) and [Simulink Agentic Toolkit](https://github.com/matlab/simulink-agentic-toolkit)). You should also understand the MATLAB or Simulink workflow that the mission will teach.

## Authoring missions

> **How do I start creating a mission?**

In MATLAB, create a new folder to serve as your authoring workspace and then navigate to it.

Use `startMissionAuthoring()` to create a `marketplace` folder with the following structure:

```
marketplace/
├── manifest.yaml
└── missions/
     └── <mission-name>/
         ├── mission.yaml
        └── setup_<mission-name>.m   # optional naming convention
```

Start your agentic client from the folder you just created, and ask it to `create-tutor-mission`.

> **What information should I give `create-tutor-mission`?**

The minimum required information is: the concept, learner audience, real-world context, mission name, learning outcomes, starting state, setup needs, and whether the tutor should be allowed to edit learner-owned files. The `create-tutor-mission` will make use of instructional design best practices to split this concept up over a series of tasks, with scaffolded hints.

> **Can I write my own task instructions?**

Yes. If you have detailed information or want to write your own tasks and hints, you can provide it as source material. The skill preserves intent, keeps the initial task instruction focused on the goal, and can move useful procedural material into later hints.

> **What files make up a mission?**

The main file is `mission.yaml`. It describes the mission, learner tasks, hints, learning outcomes, and completion checks. A mission may also include a setup script for preparing the starting state and reset scripts for restoring later task states.

> **When should a mission use setup code?**

Use setup code when learners need prepared data, models, or workspace state and creating that state would distract from the learning goal. Leave setup out when preparing the starting state is part of the lesson. Setup should provide starting material, not reveal the answer or create the final result.

> **How should tasks and completion checks be designed?**

Each task should ask for one main action, explain why it matters, and lead to an observable result. Keep tasks in a logical order and provide one to three ordered hints that progress from directional to specific to direct. Later hints may include accurate commands, UI paths, values, library paths, wiring steps, or a complete recipe. Completion checks should describe current, meaningful MATLAB or Simulink state, use supported MATLAB MCP tools, and accept behaviorally equivalent solutions whenever the instruction is outcome-oriented.

> **How do I review, publish, and maintain a mission?**

Run `qa-mission` after drafting to review structure, learner flow, hints, outcomes, setup and reset behavior, completion checks, and app metadata. Before sharing, place the reviewed mission in the marketplace layout, update `marketplace/manifest.yaml` and the content version, and run the required validators. Use `maintain-missions` for framework, packaging, documentation, or validation maintenance.

## Sharing missions

> **How do I share missions with learners?**

Mission distribution supports public or private Git repositories. Put the marketplace layout in a Git repository and push it to a remote the learner can access.

The repository can contain other files, but the `marketplace` folder must be at the repository root unless `manifest.yaml` is itself at the repository root. Share an HTTPS, `ssh://`, or SCP-style SSH clone URL. HTTPS uses the learner's Git credential helper; SSH uses the learner's SSH agent.

> **What actually happens when learner add a mission marketplace through the app?**

The app clones a remote marketplace into a local cache. At startup it checks for new remote revisions without downloading them; the learner chooses **Refresh** to update content. Missing caches are recovered automatically when possible, and refresh failures retain the last valid cache. Starting a mission copies `mission.yaml`, the declared setup script and thumbnail when present, and the mission's reset directory when present. Missions without a thumbnail use the app-rendered generic graphic.
