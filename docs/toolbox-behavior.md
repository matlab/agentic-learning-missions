# What the Toolbox Does Behind the Scenes

**Note:** You do not need to know any of this to complete a mission or author one. Pick a mission in the app, follow the launch instructions, and let the tutor guide the rest.

This page explains understand what the toolbox is setting up for you and how the missions marketplace is managed.

## The short version

Interactive Missions is the launcher and session manager around a mission. It keeps mission content together, prepares a separate work folder for each learner session, gives the selected agent the right tutoring instructions, and keeps track of resumable progress.

After selecting a mission from the app and completing the setup in the agentic client, the learner receives instruction from the agent and works in MATLAB or Simulink.

```text
  Toolbox                  Agent and tutor              Learner
  -------                  ---------------              -------
  lists missions     -->   explains and checks     -->   works in MATLAB
  prepares workspace       the mission                   or Simulink
  tracks sessions
```

## Where new missions come from

Missions are distributed as a marketplace, rather than as individual mission downloads. The marketplace keeps a mission's metadata, thumbnails, and validation resources together. The installed toolbox supplies the shared tutor skill and agent adapters.

```text
  Git marketplace
        |
        v
  Toolbox-managed local cache
        |
        v
  Mission cards in the app
        |
        v
  Copied mission bundle in a learner workspace
```

The app registers the default marketplace on first use and keeps a local cache for browsing and workspace preparation. At startup it checks remote revisions asynchronously but does not download changed content. Learners choose **Refresh** to update a cache. Startup attempts to recover a missing registered cache; a failed refresh leaves the last valid cache usable.

Marketplaces may be public or private and accept HTTPS, `ssh://`, or SCP-style SSH clone URLs. HTTPS authentication uses the configured Git credential helper; SSH authentication uses the configured SSH agent. The toolbox never stores credentials.

## Marketplace

Each marketplace repository provides content in `marketplace/` or at its repository root.

- `marketplace/manifest.yaml` describes the marketplace.
- `marketplace/missions/<mission-name>/mission.yaml` defines each mission.
- `marketplace/assets/` may contain authored mission thumbnails and examples. Missions without an authored thumbnail use the installed app's generic graphic.

The installed toolbox, not the marketplace, supplies `src/skills/mission-tutoring/` and the selected adapter. Author skills under `src/author-skills/` are copied only by `startMissionAuthoring()`.

## Starting a mission

The app reads mission metadata for cards. `learner_visible` controls learner-catalog inclusion; `status` is displayed metadata. The app does not currently filter or gate missions by audience, products, or status, and the current UI does not reliably display declared difficulty.

When the learner chooses **Start Mission** or **Practice**, the toolbox:

1. Creates a new isolated workspace under the configurable work-folder base, which normally derives from the first MATLAB `userpath` entry.
2. Copies `mission.yaml`, its declared setup script and thumbnail when present, its `task_reset_<mission-name>` directory when present, and the learner tutor skill. Other helpers and arbitrary assets are not copied.
3. Adds instructions for the chosen agent client, such as Codex, Claude Code, Gemini CLI, GitHub Copilot, or the generic adapter.
4. Writes a small manifest and launch prompt so the tutor knows which copied mission, mode, and progress location belong to this session.
5. Shows the learner the command or desktop-app step needed to open that workspace and start the agent.

The installed toolbox and marketplace cache are not the learner's working area. The prepared workspace is. This keeps a learner's session independent from the installed content and from other sessions.

```text
  Installed toolbox       Marketplace cache             Prepared learner workspace
  -----------------       -----------------             --------------------------
  src/skills/             missions/                    .interactive-missions/
  src/adapters/           assets/                       content/
                                                       skills/mission-tutoring/
                                                       manifest.json
                                                       launch-prompt.md
                                                       progress.json (regular sessions)
```

## Progress, practice, and resume

**Start Mission** creates a regular session. Its progress is stored beside the copied mission at `.interactive-missions/progress.json`, which lets the app offer **Resume** later.

**Practice** creates the same kind of isolated workspace but begins without a progress file. It is useful for trying a mission from the beginning without creating a resumable record. If the learner explicitly asks the tutor to save progress, that practice workspace can become a regular, resumable session.

The app keeps lightweight records of recent workspaces to find them again. The workspace-local progress file remains the source of truth for what the learner has completed.

## What the toolbox protects

The toolbox deliberately separates framework files from learner-owned work:

- Mission source files, copied tutor files, adapter files, manifests, and progress rules are protected during ordinary tutoring.
- The toolbox detects locally changed copied bundles before refreshing them, so it does not silently overwrite a session.
- A mission can explicitly allow agent edits, but only in the active learner workspace and only when the task or learner asks for them.
- Setup and reset resources travel from the cached marketplace with the mission so a tutor can prepare or restart a task without modifying the installed toolbox or marketplace cache.

That separation is the main pattern worth copying: package the learning framework once, prepare a disposable or resumable workspace for each session, and keep the learner's actual work in that workspace.
