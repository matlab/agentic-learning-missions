# Learner FAQ

## In the Interactive Missions app

> **How do I choose a mission?**

Open the Missions tab to browse the available learning activities. Choose the mission that matches the topic you want to practice, then select **Start Mission** when you are ready to work through it with an agentic tutor.

> **How do I start or resume a mission?**

To start a mission, choose a local folder to serve as your mission workspace. Select **Start Mission** to save progress in that workspace so you can resume later. Select **Practice** to explore the mission without creating saved progress.

If you have already started a mission, select **Resume** to continue where you left off (this is not available in Practice mode).

> **What is the difference between Start Mission and Practice?**

**Start Mission** begins a Regular session and saves your progress so you can choose **Resume** later. **Practice** lets you try the mission without saving progress; it starts from the beginning the next time unless you ask Ada to save your progress.

> **How do I start a mission from within my specific coding agent?**

After starting a mission in the app, follow the instruction to launch your coding agent. Then use the `mission-tutor` skill according to the following table.

| Client | Tutor launch |
| --- | --- |
| Codex | `$mission-tutoring` |
| Claude Code | `/mission-tutoring` |
| Gemini CLI | Ask Gemini to start using `GEMINI.md` |
| GitHub Copilot in VS Code | Run `.github/prompts/mission-tutoring.prompt.md`, or `/mission-tutoring` when prompt commands are available |
| GitHub Copilot CLI | Ask Copilot to start using `COPILOT.md` |
| Generic | Ask the agent to follow `START_MISSION.md` |

## The tutor

> **Who is Ada?**

Ada is the name of your agentic tutor (a nod to [Ada Lovelace](https://en.wikipedia.org/wiki/Ada_Lovelace), of course). You can ask Ada questions about the task or the general concepts surrounding the tasks.

> **Can Ada edit my MATLAB or Simulink files?**

Ada can inspect your work and guide you through changes. Missions are read-only by default, so Ada will not edit your files. A mission that teaches artifact creation or revision may allow edits to learner-owned files when you or the mission task asks for them. Ada does not edit the mission’s copied files, toolbox files, marketplace files, or progress file except to save normal mission progress.

> **Can I ask Ada questions not covered in the mission?**

Ada can discuss mission concepts and provide one progressively more direct hint at a time. Ada checks for task-relevant changes or partial results before giving a generated complete recipe. Asking directly, asking repeatedly, becoming frustrated, or using all applicable hints does not bypass that effort gate. After Ada can observe relevant effort, it may provide a recipe with commands, click paths, parameter values, and wiring guidance when you have tried prior guidance, the remaining hints do not address your blocker, or the hints are exhausted. You still perform the work, and Ada rechecks your current result before deciding whether the task is complete.

## General questions

> **What do I need to have installed to start a mission?**

You need:

* Interactive Missions toolbox
* a MATLAB release supported by the selected mission (generally, R2024b and above)
* a supported agentic client
* MATLAB MCP Server

The toolbox installation and each mission have separate requirements. Check the selected mission's supported releases, products, and capabilities.

> **How long do most missions take to complete?**

The missions that currently ship are estimated at 35 and 60 minutes. Check the selected mission card for its estimate; there is no time limit.

> **How do I get more missions?**

Open **Marketplace settings** in the Interactive Missions app. You can register a public or private marketplace with an HTTPS, `ssh://`, or SCP-style SSH clone URL. The app checks for updates at startup, but downloads them only when you choose **Refresh**.

> **Where are my missions, work, and progress stored?**

Each launch prepares an isolated workspace. The default workspace root takes the form `~/Documents/MATLAB/Interactive-Missions`. You can change this in the app.

The first run uses `<mission-name>`; later runs use `<mission-name>_<increment>`.

```text
<workspace>/
  .interactive-missions/
    content/
      mission.yaml
    progress.json
```

The mission files used for your session are under `.interactive-missions/content`. In Regular mode, your progress is saved in `.interactive-missions/progress.json`, so you can resume later. Practice mode starts without progress; ask Ada to save it if you want to make that workspace resumable. Installed toolbox files and marketplace source files are not changed during normal mission runs.

> **What actually happens when I add a mission marketplace?**

The app clones a remote marketplace to a cache folder on your computer. At startup it checks whether a newer revision exists without downloading it. Choose **Refresh** to download updates. Starting a mission copies the necessary files from the cache to your learner workspace.

If a remote marketplace is unavailable after a successful download, the app keeps using its last valid cache. If no cache is available, the app shows no missions.

> **Can multiple people work on missions on the same computer?**

Yes. Use a separate prepared workspace for each person. At the beginning of a new regular session, Ada asks how the learner wants to be addressed and records that name with the workspace-local progress.

> **Can I switch back and forth between agents to complete missions?**

No. At this time, each agent/learner combination is a separate learner workspace. Choosing a different agent will mean you have to start the mission over.

> **What should I do if a mission cannot start?**

Read the message in the app and fix the item it identifies. Confirm that MATLAB MCP Server is running, Simulink or other toolboxes are installed when the mission needs it, your agentic client is supported, and the selected work folder is empty and available.
