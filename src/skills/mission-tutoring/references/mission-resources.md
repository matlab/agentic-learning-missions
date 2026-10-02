# Mission Resources

Load `status-reporting.md` before any learner-visible setup or reset update.
Keep routine successful setup and reset silent; send a standalone status report
only for a meaningful phase, visible delay, or failure, followed by separate
Ada tutoring text when the learner needs an explanation or choice.

The prepared learner bundle is authoritative:

- `.interactive-missions/content/mission.yaml`
- `.interactive-missions/content/<declared setup script>`
- `.interactive-missions/content/task_reset_<missionName>/reset_t<NN>.m`

For a declared setup or reset script, add the copied folder to the MATLAB path
and run the declared file without changing the learner's current folder. Skip
setup when the mission omits it. On resume at `t02` or later, run the matching
reset script before presenting the task.

If copied content is missing or the manifest does not match the mission, stop
and ask the learner to prepare the workspace again from the MATLAB app. Do not
use installed marketplace files as a fallback.
