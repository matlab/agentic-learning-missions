# Sharing Missions Through Marketplaces

Interactive Missions shares mission content through marketplace layouts. A marketplace is a versioned folder or Git source that contains `manifest.yaml`, mission folders, mission-owned assets, and validation rules.

## Expected Flow

1. The author creates or updates a mission under `marketplace/missions/<mission-name>/`.
2. The author runs `qa-mission` and the marketplace validators.
3. The maintainer publishes an updated marketplace version.
4. The app checks remote revisions at startup and notifies learners when an update is available; learners choose **Refresh** to download it.
5. The app prepares learner workspaces from the local marketplace cache.

The app does not import single-mission ZIP packs. Mission source content is installed and updated as marketplace content so catalog metadata and validation rules stay together. The installed toolbox owns the shared tutor skill and agent adapters.

## Authenticated Marketplaces

Marketplaces may be public or private. Registration accepts HTTPS clone URLs, `ssh://` clone URLs, and SCP-style SSH URLs such as `git@example.com:group/repo.git`. HTTPS uses the learner's configured Git credential helper; SSH uses the learner's SSH agent. The toolbox checks access with Git and does not store authentication secrets. If refresh fails, the app retains the last valid cache; if a registered cache is missing, startup attempts to recover it.

## Local Development

Repository maintainers can test marketplace content directly from this checkout. Installed toolbox users should treat cached marketplace content as app-managed and read-only. Learner work happens in prepared workspaces; authoring work happens in an authoring workspace or marketplace checkout.

Run `startMissionAuthoring()` from an empty folder to create a local authoring workspace. Its draft manifest starts with an empty `source_url` TODO, which is acceptable only before publication. Set the intended HTTPS or SSH Git clone URL before registering or sharing the marketplace.

## Publishing Checklist

- `marketplace/manifest.yaml` includes marketplace identity, source URL, content version, minimum toolbox version, mission entries, and adapter entries.
- Every mission has `mission.yaml` under `marketplace/missions/<mission-name>/`.
- Each prepared workspace receives only `mission.yaml`, the declared setup script, an explicitly declared thumbnail, and `task_reset_<mission-name>/` when present. Omitted or empty thumbnails use the app-rendered generic fallback. Undeclared helpers and arbitrary assets are not copied.
- The toolbox includes the Generic adapter under `src/adapters/generic/`.
- Versioned marketplace updates are prompted by the app instead of silently changing existing learner workspaces.
- `minimum_toolbox_version` is currently informational metadata; registration and launch do not enforce it.
