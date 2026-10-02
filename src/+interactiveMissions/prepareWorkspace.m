function info = prepareWorkspace(options)
%PREPAREWORKSPACE Copy a mission runtime bundle into a learner workspace.

    arguments
        options.MissionName (1, 1) string = "root-inports-outports"
        options.WorkspaceRoot (1, 1) string = ""
        options.SafeRoot (1, 1) string = ""
        options.Mode (1, 1) string {mustBeMember(options.Mode, ["regular", "tracked", "practice", "resume"])} = "regular"
        options.ForceRefresh (1, 1) logical = false
        options.Force (1, 1) logical = false
        options.RequireEmpty (1, 1) logical = false
        options.AgentClient (1, 1) string = "codex"
    end

    workspaceRoot = options.WorkspaceRoot;
    if strlength(strtrim(options.SafeRoot)) > 0
        workspaceRoot = options.SafeRoot;
    end

    workspaceRoot = string(workspaceRoot);
    missionName = string(options.MissionName);
    if strlength(strtrim(workspaceRoot)) == 0
        workspaceRoot = interactiveMissions.internal.nextWorkspaceRoot(missionName);
    end
    mode = normalizeMode(options.Mode);
    forceRefresh = options.ForceRefresh || options.Force;
    agentClient = normalizeAgentClient(options.AgentClient);

    missions = interactiveMissions.catalog(Audience="all");
    missionIndex = find(missions.MissionName == missionName | missions.MissionId == missionName, 1);
    if isempty(missionIndex)
        error("InteractiveMissions:MissionNotFound", "Mission %s is not available.", missionName);
    end
    mission = missions(missionIndex, :);
    contentRoot = string(mission.SourceRoot);
    if strlength(strtrim(contentRoot)) == 0
        contentRoot = string(fileparts(mission.Path));
    end
    runtimeAssetsRoot = fullfile(interactiveMissions.internal.toolboxRoot(), "src");
    skillRoot = fullfile(runtimeAssetsRoot, "skills", "mission-tutoring");

    ensureSafeWorkspace(workspaceRoot, options.RequireEmpty);
    runtimeRoot = fullfile(workspaceRoot, ".interactive-missions");
    runtimeContentRoot = fullfile(runtimeRoot, "content");
    runtimeSkillRoot = fullfile(runtimeRoot, "skills", "mission-tutoring");
    resumableProgressPath = fullfile(runtimeRoot, "progress.json");
    progressPath = resumableProgressPath;
    if mode == "practice"
        progressPath = "";
    end

    createFolder(runtimeRoot);
    createFolder(runtimeContentRoot);
    if strlength(progressPath) > 0
        createFolder(fileparts(progressPath));
    end

    manifestPath = fullfile(runtimeRoot, "manifest.json");
    if isfile(manifestPath) && ~forceRefresh
        previousManifest = jsondecode(fileread(manifestPath));
        if isfield(previousManifest, "files") && copiedFilesModified(previousManifest, workspaceRoot)
            error("InteractiveMissions:WorkspaceBundleModified", ...
                "The existing mission bundle has local edits. Use ForceRefresh=true only after preserving them.");
        end
    end

    copiedFiles = struct("relativePath", {}, "root", {}, "sourcePath", {}, "sha256", {}, "bytes", {});
    copiedFiles = copyMissionBundle(mission, contentRoot, runtimeContentRoot, copiedFiles);
    copiedFiles = copyTree(skillRoot, runtimeSkillRoot, runtimeRoot, copiedFiles);
    copiedFiles = writeAgentAdapterFiles(copiedFiles, workspaceRoot, skillRoot, mission, progressPath, ...
        mode, agentClient);

    launchPromptPath = fullfile(runtimeRoot, "launch-prompt.md");
    instructionsPath = fullfile(runtimeRoot, "AGENTS.md");
    promptText = launchPrompt(mission, runtimeRoot, progressPath, mode, agentClient);
    instructionsText = runtimeInstructions();
    writeText(launchPromptPath, promptText);
    writeText(instructionsPath, instructionsText);
    copiedFiles(end + 1) = fileRecord(launchPromptPath, runtimeRoot, launchPromptPath);
    copiedFiles(end + 1) = fileRecord(instructionsPath, runtimeRoot, instructionsPath);

    manifest = struct();
    manifest.schemaVersion = "1.0";
    manifest.progressSchemaVersion = "2.0";
    manifest.toolboxVersion = toolboxVersion();
    manifest.workspaceRoot = workspaceRoot;
    manifest.runtimeRoot = runtimeRoot;
    manifest.contentRoot = runtimeContentRoot;
    manifest.skillRoot = runtimeSkillRoot;
    manifest.marketplaceSource = mission.MarketplaceSource;
    manifest.marketplaceTitle = mission.MarketplaceTitle;
    manifest.marketplaceContentVersion = mission.MarketplaceContentVersion;
    manifest.missionName = mission.MissionName;
    manifest.missionId = mission.MissionId;
    manifest.legacyMissionId = mission.LegacyId;
    manifest.missionVersion = mission.MissionVersion;
    manifest.missionTitle = mission.Title;
    manifest.mode = string(mode);
    manifest.agentClient = agentClient;
    manifest.progressPath = progressPath;
    manifest.resumableProgressPath = resumableProgressPath;
    manifest.taskIds = missionTaskIds(mission);
    manifest.launchPromptPath = launchPromptPath;
    manifest.allowAgentEdits = logical(mission.AllowAgentEdits);
    manifest.createdAt = char(datetime("now", "TimeZone", "local", "Format", "yyyy-MM-dd'T'HH:mm:ssXXX"));
    manifest.files = copiedFiles;
    writeText(manifestPath, jsonencode(manifest));
    if strlength(progressPath) > 0 && ~isfile(progressPath)
        initializeProgress(progressPath, mission, workspaceRoot);
    end

    settings = struct();
    settings.LastWorkspace = interactiveMissions.internal.workspaceBaseRoot(workspaceRoot);
    settings.LastMission = mission.MissionName;
    settings.ActiveWorkspaces = updateActiveWorkspaces(workspaceRoot);
    settings.RecentWorkspaces = updateRecentWorkspaces(workspaceRoot);
    interactiveMissions.preferences("set", Settings=settings);
    updateActiveWorkspaceIndex(workspaceRoot, manifestPath, progressPath, mission);

    info = struct();
    info.WorkspaceRoot = workspaceRoot;
    info.RuntimeRoot = runtimeRoot;
    info.ManifestPath = manifestPath;
    info.ContentRoot = runtimeContentRoot;
    info.SkillRoot = runtimeSkillRoot;
    info.ProgressPath = progressPath;
    info.LaunchPromptPath = launchPromptPath;
    info.AgentClient = agentClient;
    info.AllowAgentEdits = logical(mission.AllowAgentEdits);
end

function copiedFiles = copyMissionBundle(mission, contentRoot, targetRoot, copiedFiles)
    missionPath = string(mission.Path);
    copiedFiles(end + 1) = copySingleFile(missionPath, targetRoot, contentRoot);

    text = string(fileread(missionPath));
    setupScript = scalarFromBlock(text, "setup", "script");
    if strlength(setupScript) > 0
        copiedFiles(end + 1) = copyResourceFile(setupScript, targetRoot, contentRoot, mission.MarketplaceSource);
    end

    thumbnail = scalarAfterKey(text, "thumbnail");
    if strlength(thumbnail) > 0
        copiedFiles(end + 1) = copyResourceFile(thumbnail, targetRoot, contentRoot, mission.MarketplaceSource);
    end

    resetFolder = fullfile(contentRoot, "task_reset_" + mission.MissionName);
    if isfolder(resetFolder)
        copiedFiles = copyTree(resetFolder, fullfile(targetRoot, "task_reset_" + mission.MissionName), ...
            targetRoot, copiedFiles);
    end
end

function copiedFiles = copyTree(sourceRoot, targetRoot, relativeRoot, copiedFiles)
    files = dir(fullfile(sourceRoot, "**", "*"));
    files = files(~[files.isdir]);
    for fileIndex = 1:numel(files)
        sourcePath = fullfile(files(fileIndex).folder, files(fileIndex).name);
        relativePath = erase(string(sourcePath), string(sourceRoot) + filesep);
        targetPath = fullfile(targetRoot, relativePath);
        copyFile(sourcePath, targetPath);
        copiedFiles(end + 1) = fileRecord(targetPath, relativeRoot, sourcePath); %#ok<AGROW>
    end
end

function record = copySingleFile(sourcePath, targetRoot, sourceRoot)
    sourcePath = string(sourcePath);
    if ~isfile(sourcePath)
        error("InteractiveMissions:MissingResource", "Missing mission resource: %s", sourcePath);
    end
    relativePath = erase(sourcePath, string(sourceRoot) + filesep);
    validateRelativePath(relativePath);
    targetPath = fullfile(targetRoot, relativePath);
    copyFile(sourcePath, targetPath);
    record = fileRecord(targetPath, targetRoot, sourcePath);
end

function mode = normalizeMode(mode)
    mode = string(mode);
    if mode == "tracked"
        mode = "regular";
    end
end

function record = copyResourceFile(relativePath, targetRoot, sourceRoot, ~)
    sourcePath = resolveMissionResource(relativePath, sourceRoot);
    targetPath = fullfile(targetRoot, normalizeRelativeResourcePath(relativePath));
    copyFile(sourcePath, targetPath);
    record = fileRecord(targetPath, targetRoot, sourcePath);
end

function sourcePath = resolveMissionResource(relativePath, sourceRoot)
    relativePath = string(relativePath);
    if interactiveMissions.internal.isAbsolutePath(relativePath)
        sourcePath = relativePath;
    else
        sourcePath = fullfile(sourceRoot, relativePath);
        if ~isfile(sourcePath)
            marketplaceRoot = fileparts(fileparts(string(sourceRoot)));
            sourcePath = fullfile(marketplaceRoot, relativePath);
        end
    end
    if ~isfile(sourcePath)
        error("InteractiveMissions:MissingResource", "Missing mission resource: %s", sourcePath);
    end
end

function path = normalizeRelativeResourcePath(path)
    path = replace(string(path), "\", "/");
    path = regexprep(path, "^\.\./", "");
    validateRelativePath(path);
end

function copyFile(sourcePath, targetPath)
    targetParent = fileparts(targetPath);
    createFolder(targetParent);
    copyfile(sourcePath, targetPath, "f");
end

function record = fileRecord(targetPath, relativeRoot, sourcePath)
    fileInfo = dir(targetPath);
    record = struct();
    record.relativePath = relativePath(targetPath, relativeRoot);
    record.root = copiedFileRoot(targetPath);
    record.sourcePath = string(sourcePath);
    record.sha256 = fileHash(targetPath);
    record.bytes = fileInfo.bytes;
end

function modified = copiedFilesModified(manifest, workspaceRoot)
    modified = false;
    runtimeRoot = fullfile(string(workspaceRoot), ".interactive-missions");
    runtimeContentRoot = fullfile(runtimeRoot, "content");
    files = manifest.files;
    for fileIndex = 1:numel(files)
        rootKind = "";
        if isfield(files(fileIndex), "root")
            rootKind = string(files(fileIndex).root);
        end
        targetPath = resolveCopiedFilePath(string(files(fileIndex).relativePath), rootKind, ...
            workspaceRoot, runtimeRoot, runtimeContentRoot);
        if strlength(targetPath) == 0 || ~isfile(targetPath) || fileHash(targetPath) ~= string(files(fileIndex).sha256)
            modified = true;
            return
        end
    end
end

function targetPath = resolveCopiedFilePath(relativePath, rootKind, workspaceRoot, runtimeRoot, runtimeContentRoot)
    switch rootKind
        case "workspace"
            targetPath = fullfile(string(workspaceRoot), relativePath);
            return
        case "runtime"
            targetPath = fullfile(string(runtimeRoot), relativePath);
            return
        case "content"
            targetPath = fullfile(string(runtimeContentRoot), relativePath);
            return
    end

    candidatePaths = [
        fullfile(string(workspaceRoot), relativePath)
        fullfile(string(runtimeRoot), relativePath)
        fullfile(string(runtimeContentRoot), relativePath)
        ];
    targetPath = "";
    for pathIndex = 1:numel(candidatePaths)
        if isfile(candidatePaths(pathIndex))
            targetPath = candidatePaths(pathIndex);
            return
        end
    end
end

function rootKind = copiedFileRoot(targetPath)
    targetPath = replace(string(targetPath), "/", filesep);
    contentMarker = filesep + ".interactive-missions" + filesep + "content" + filesep;
    runtimeMarker = filesep + ".interactive-missions" + filesep;
    if contains(targetPath, contentMarker)
        rootKind = "content";
    elseif contains(targetPath, runtimeMarker)
        rootKind = "runtime";
    else
        rootKind = "workspace";
    end
end

function ensureSafeWorkspace(workspaceRoot, requireEmpty)
    if strlength(strtrim(workspaceRoot)) == 0
        error("InteractiveMissions:InvalidWorkspace", "WorkspaceRoot must not be empty.");
    end
    if contains(workspaceRoot, "..")
        error("InteractiveMissions:InvalidWorkspace", ...
            "WorkspaceRoot must not contain parent-folder references.");
    end
    createFolder(workspaceRoot);
    workspaceRoot = absolutePath(workspaceRoot);
    marketplaceCacheRoot = absolutePath(fullfile(prefdir(), "InteractiveMissions", "marketplaces"));
    if interactiveMissions.internal.isPathWithin(workspaceRoot, marketplaceCacheRoot)
        error("InteractiveMissions:InvalidWorkspace", ...
            "The learner workspace must not be inside the marketplace cache.");
    end
    if requireEmpty && ~folderIsEmpty(workspaceRoot)
        error("InteractiveMissions:WorkspaceNotEmpty", ...
            "Choose an empty folder for a new mission workspace: %s", workspaceRoot);
    end
end

function result = folderIsEmpty(folder)
    listing = dir(folder);
    names = string({listing.name});
    result = all(names == "." | names == "..");
end

function path = absolutePath(path)
    path = string(path);
    if ~interactiveMissions.internal.isAbsolutePath(path)
        path = fullfile(pwd(), path);
    end
    path = replace(path, "/", filesep);
end

function createFolder(folder)
    if ~isfolder(folder)
        mkdir(folder);
    end
end

function agentClient = normalizeAgentClient(agentClient)
    agentClient = lower(strtrim(string(agentClient)));
    agentClient = regexprep(agentClient, "[^a-z0-9]+", "-");
    switch agentClient
        case {"codex", "openai-codex"}
            agentClient = "codex";
        case {"claude", "claude-code"}
            agentClient = "claude-code";
        case {"gemini", "gemini-cli"}
            agentClient = "gemini-cli";
        case {"copilot", "github-copilot", "github-copilot-vs-code", "github-copilot-vscode"}
            agentClient = "github-copilot-vscode";
        case {"github-copilot-cli", "copilot-cli", "github-copilot-terminal"}
            agentClient = "github-copilot-cli";
        case {"generic", "other", "generic-other"}
            agentClient = "generic";
        otherwise
            error("InteractiveMissions:UnsupportedAgentClient", ...
                "Unsupported agent client '%s'.", agentClient);
    end
end

function copiedFiles = writeAgentAdapterFiles(copiedFiles, workspaceRoot, skillRoot, mission, progressPath, ...
        mode, agentClient)
    runtimeAssetsRoot = fullfile(interactiveMissions.internal.toolboxRoot(), "src");
    adapterRoot = fullfile(runtimeAssetsRoot, "adapters", agentClient);
    if ~isfolder(adapterRoot)
        error("InteractiveMissions:MissingAdapter", ...
            "Marketplace adapter not found for agentic client '%s'.", agentClient);
    end
    adapterFiles = adapterFileMappings(fullfile(adapterRoot, "adapter.yaml"));
    context = adapterContext(mission, progressPath, mode, agentClient);
    for fileIndex = 1:numel(adapterFiles)
        sourcePath = fullfile(adapterRoot, adapterFiles(fileIndex).Source);
        if ~isfile(sourcePath)
            error("InteractiveMissions:MissingAdapter", "Missing adapter template: %s", sourcePath);
        end
        text = replaceAdapterTokens(fileread(sourcePath), context);
        copiedFiles = writeWorkspaceText(copiedFiles, workspaceRoot, adapterFiles(fileIndex).Target, text);
    end

    if agentClient == "codex"
        codexSkillRoot = fullfile(workspaceRoot, ".codex", "skills", "mission-tutoring");
        copiedFiles = copyTree(skillRoot, codexSkillRoot, workspaceRoot, copiedFiles);
    end
end

function files = adapterFileMappings(adapterManifestPath)
    text = string(fileread(adapterManifestPath));
    sourceTokens = regexp(text, "(?m)^\s+- source:\s*[""']?([^""'\r\n]+)[""']?\s*$", "tokens");
    targetTokens = regexp(text, "(?m)^\s+target:\s*[""']?([^""'\r\n]+)[""']?\s*$", "tokens");
    if isempty(sourceTokens) || numel(sourceTokens) ~= numel(targetTokens)
        error("InteractiveMissions:InvalidAdapter", ...
            "Adapter manifest must list matching source and target files: %s", adapterManifestPath);
    end
    files = struct("Source", {}, "Target", {});
    for fileIndex = 1:numel(sourceTokens)
        files(fileIndex).Source = string(sourceTokens{fileIndex}{1});
        files(fileIndex).Target = string(targetTokens{fileIndex}{1});
    end
end

function context = adapterContext(mission, progressPath, mode, agentClient)
    context = struct();
    context.missionTitle = string(mission.Title);
    context.missionId = string(mission.MissionId);
    context.mode = string(mode);
    context.agentDisplayName = agentDisplayName(agentClient);
    context.resumableProgressPath = fullfile(".interactive-missions", "progress.json");
    context.progressPath = progressPath;
    if strlength(progressPath) == 0
        context.progressPath = "none yet; write " + context.resumableProgressPath + ...
            " only if the learner asks to save progress";
    end
    context.agentEditSummary = editPermissionSummary(logical(mission.AllowAgentEdits));
    if mode == "practice"
        context.practiceNote = join([
            "Practice mode starts progress-free."
            "If the learner asks to save progress or resume later, require a learner name first,"
            "create `.interactive-missions/progress.json`, set `mode` to `regular`, and continue saving progress there."
            ], " ");
    else
        context.practiceNote = "";
    end
end

function text = replaceAdapterTokens(text, context)
    text = string(text);
    names = string(fieldnames(context));
    for name = names(:)'
        text = replace(text, "{{" + name + "}}", string(context.(name)));
    end
end

function copiedFiles = writeWorkspaceText(copiedFiles, workspaceRoot, relativePath, text)
    targetPath = fullfile(string(workspaceRoot), string(relativePath));
    validateRelativePath(relativePath);
    createFolder(fileparts(targetPath));
    writeText(targetPath, text);
    copiedFiles(end + 1) = fileRecord(targetPath, workspaceRoot, targetPath);
end

function value = scalarAfterKey(text, key)
    tokens = regexp(text, "(?m)^" + key + ":\s*[""']?([^""'\r\n]+)[""']?\s*$", "tokens", "once");
    if isempty(tokens)
        value = "";
    else
        value = string(tokens{1});
    end
end

function value = scalarFromBlock(text, blockName, key)
    lines = splitlines(string(text));
    blockStart = find(~cellfun(@isempty, regexp(cellstr(lines), "^" + blockName + ":\s*$", "once")), 1);
    value = "";
    if isempty(blockStart)
        return
    end
    for lineIndex = blockStart + 1:numel(lines)
        line = lines(lineIndex);
        if strlength(strtrim(line)) == 0
            continue
        end
        if ~startsWith(line, " ")
            return
        end
        tokens = regexp(line, "^\s+" + key + ":\s*[""']?([^""'\r\n]+)[""']?\s*$", "tokens", "once");
        if ~isempty(tokens)
            value = string(tokens{1});
            return
        end
    end
end

function validateRelativePath(path)
    path = string(path);
    if contains(path, "..") || interactiveMissions.internal.isAbsolutePath(path)
        error("InteractiveMissions:UnsafePath", "Unsafe resource path: %s", path);
    end
end

function result = relativePath(path, root)
    result = erase(string(path), string(root) + filesep);
    result = replace(result, "\", "/");
end

function hash = fileHash(path)
    fileIdentifier = fopen(path, "r");
    if fileIdentifier < 0
        error("InteractiveMissions:FileOpenFailed", "Could not read %s.", path);
    end
    cleanup = onCleanup(@() fclose(fileIdentifier));
    bytes = fread(fileIdentifier, Inf, "uint8=>uint8");
    clear cleanup

    % Java is not guaranteed in all MATLAB installations. This deterministic
    % fingerprint is used for local modification detection, not cryptography.
    accumulator = uint64(1469598103934665603);
    prime = uint64(1099511628211);
    for byteIndex = 1:numel(bytes)
        accumulator = bitxor(accumulator, uint64(bytes(byteIndex)));
        accumulator = accumulator*prime;
    end
    hash = lower(string(dec2hex(accumulator, 16)));
end

function prompt = launchPrompt(mission, runtimeRoot, progressPath, mode, agentClient)
    workspaceRoot = string(fileparts(runtimeRoot));
    instructions = launchInstructions(agentClient, workspaceRoot);
    lines = [
        "# Interactive Missions Launch"
        ""
        "These instructions may differ slightly depending on your agent, but the steps are generally correct."
        ""
        "Step 1: " + instructions.Step1
        ""
        "Step 2: " + instructions.Step2
        instructions.Command
        ""
        "Step 3: " + instructions.Step3
        ""
        "Step 4: Trigger the tutor skill:"
        instructions.Trigger
        ""
        "Agent context:"
        "- Mission: " + mission.Title + " (" + mission.MissionName + "), " + mode + " mode."
        "- Read `.interactive-missions/manifest.json` before setup."
        "- Use copied content under `.interactive-missions/content`; do not use installed toolbox mission files as fallback."
        "- Agent edits: " + editPermissionSummary(logical(mission.AllowAgentEdits))
        ];

    if mode == "practice"
        lines = [
            lines
            "- Practice mode starts progress-free."
            "- If the learner asks to save progress or resume later, require a learner name first, create `" + ...
            fullfile(runtimeRoot, "progress.json") + "`, set `mode` to `regular`, and continue saving progress there."
            ];
    else
        lines = [
            lines
            "- Ada must collect and save the learner's display name before beginning or presenting Task 1 when progress has no name."
            "- Write progress to `" + string(progressPath) + "`."
            ];
    end
    prompt = strjoin(lines, newline);
end

function instructions = launchInstructions(agentClient, workspaceRoot)
    workspaceRoot = string(workspaceRoot);
    switch agentClient
        case "codex"
            instructions = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder:", ...
                "Command", "cd " + quoteUserPath(workspaceRoot), ...
                "Step3", "Launch Codex with `codex`.", ...
                "Trigger", "$mission-tutoring");
        case "claude-code"
            instructions = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder:", ...
                "Command", "cd " + quoteUserPath(workspaceRoot), ...
                "Step3", "Launch Claude Code with `claude`.", ...
                "Trigger", "/mission-tutoring");
        case "gemini-cli"
            instructions = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder:", ...
                "Command", "cd " + quoteUserPath(workspaceRoot), ...
                "Step3", "Launch Gemini CLI with `gemini`.", ...
                "Trigger", "Start the mission tutoring session using GEMINI.md.");
        case "github-copilot-vscode"
            instructions = struct( ...
                "Step1", "Open VS Code.", ...
                "Step2", "Open the work folder:", ...
                "Command", "code " + quoteUserPath(workspaceRoot), ...
                "Step3", "Open GitHub Copilot Chat in Agent mode.", ...
                "Trigger", "Run `.github/prompts/mission-tutoring.prompt.md`, or use `/mission-tutoring` if prompt commands are available.");
        case "github-copilot-cli"
            instructions = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder:", ...
                "Command", "cd " + quoteUserPath(workspaceRoot), ...
                "Step3", "Launch your GitHub Copilot terminal workflow.", ...
                "Trigger", "Ask Copilot to start the tutor using COPILOT.md.");
        case "generic"
            instructions = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder:", ...
                "Command", "cd " + quoteUserPath(workspaceRoot), ...
                "Step3", "Launch your code agent from that folder.", ...
                "Trigger", "Ask the agent to start the mission tutoring session.");
        otherwise
            error("InteractiveMissions:UnsupportedAgentClient", ...
                "Unsupported agent client '%s'.", agentClient);
    end
end

function text = runtimeInstructions()
    text = strjoin([
        "# Interactive Missions Learner Workspace"
        ""
        "This workspace is prepared by the Interactive Missions MATLAB toolbox."
        "Use the selected agent adapter at the workspace root for launch-time instructions."
        "Read `.interactive-missions/manifest.json` before setup to get the mission, mode, copied content folder, and progress path."
        "Mission content is copied under `.interactive-missions/content`."
        "Regular-mode learner progress lives under the manager-supplied progress path."
        "Practice mode starts progress-free, but can be promoted when the learner explicitly asks to save progress."
        "Do not edit copied mission content unless the learner explicitly chooses customization."
        ], newline);
end

function displayName = agentDisplayName(agentClient)
    switch agentClient
        case "codex"
            displayName = "Codex";
        case "claude-code"
            displayName = "Claude Code";
        case "gemini-cli"
            displayName = "Gemini CLI";
        case "github-copilot-vscode"
            displayName = "GitHub Copilot in VS Code";
        case "github-copilot-cli"
            displayName = "GitHub Copilot CLI";
        case "generic"
            displayName = "Generic";
        otherwise
            displayName = string(agentClient);
    end
end

function summary = editPermissionSummary(allowAgentEdits)
    if allowAgentEdits
        summary = "enabled for learner-owned workspace artifacts when the mission task or learner asks for it";
    else
        summary = "disabled; keep tutor behavior read-only";
    end
end

function value = quoteUserPath(value)
    value = string(value);
    value = replace(value, "\", "/");
    value = """" + replace(value, """", """""") + """";
end

function version = toolboxVersion()
    version = "0.2.0";
end

function ids = missionTaskIds(mission)
    ids = strings(0, 1);
    if ismember("TaskIds", string(mission.Properties.VariableNames))
        ids = string(mission.TaskIds{1});
    end
end

function initializeProgress(progressPath, mission, workspaceRoot)
    ids = missionTaskIds(mission);
    currentStepId = "";
    if ~isempty(ids)
        currentStepId = ids(1);
    end
    progress = struct();
    progress.schemaVersion = "2.0";
    progress.learnerName = "";
    progress.marketplaceSource = string(mission.MarketplaceSource);
    progress.missionName = string(mission.MissionName);
    progress.missionId = string(mission.MissionId);
    progress.missionVersion = string(mission.MissionVersion);
    progress.workspacePath = string(workspaceRoot);
    progress.mode = "regular";
    progress.currentStepId = currentStepId;
    progress.completedStepIds = cellstr(strings(0, 1));
    progress.hintCounts = struct();
    progress.updatedAt = char(datetime("now", "TimeZone", "local", "Format", "yyyy-MM-dd'T'HH:mm:ssXXX"));
    progress.notes = "";
    writeText(progressPath, jsonencode(progress));
end

function updateActiveWorkspaceIndex(workspaceRoot, manifestPath, progressPath, mission)
    root = fullfile(prefdir(), "InteractiveMissions", "app");
    if ~isfolder(root)
        mkdir(root);
    end
    indexPath = fullfile(root, "active_workspaces.json");
    records = struct([]);
    if isfile(indexPath)
        try
            decoded = jsondecode(fileread(indexPath));
            if isfield(decoded, "Workspaces")
                records = decoded.Workspaces(:);
            end
        catch
            records = struct([]);
        end
    end
    record = struct();
    record.WorkspaceRoot = string(workspaceRoot);
    record.ManifestPath = string(manifestPath);
    record.ProgressPath = string(progressPath);
    record.MarketplaceSource = string(mission.MarketplaceSource);
    record.MissionId = string(mission.MissionId);
    record.MissionVersion = string(mission.MissionVersion);
    if ~isempty(records)
        try
            records = orderfields(records, record);
        catch
            records = struct([]);
        end
    end
    existingIndex = [];
    if ~isempty(records) && isfield(records, "WorkspaceRoot")
        existingIndex = find(string({records.WorkspaceRoot}) == string(workspaceRoot), 1);
    end
    if isempty(existingIndex)
        if isempty(records)
            records = record;
        else
            try
                records(end + 1) = record;
                records = records([end, 1:end - 1]);
            catch
                records = record;
            end
        end
    else
        records(existingIndex) = record;
    end
    writeText(indexPath, jsonencode(struct("Workspaces", records)));
end

function recent = updateRecentWorkspaces(workspaceRoot)
    settings = interactiveMissions.preferences("get");
    if isfield(settings, "RecentWorkspaces")
        recent = string(settings.RecentWorkspaces);
    else
        recent = strings(0, 1);
    end
    recent = [workspaceRoot; recent(:)];
    recent = unique(recent, "stable");
    recent = cellstr(recent(1:min(numel(recent), 10)));
end

function activeWorkspaces = updateActiveWorkspaces(workspaceRoot)
    settings = interactiveMissions.preferences("get");
    if isfield(settings, "ActiveWorkspaces")
        activeWorkspaces = string(settings.ActiveWorkspaces);
    else
        activeWorkspaces = strings(0, 1);
    end
    activeWorkspaces = [workspaceRoot; activeWorkspaces(:)];
    activeWorkspaces = unique(activeWorkspaces, "stable");
    activeWorkspaces = cellstr(activeWorkspaces(1:min(numel(activeWorkspaces), 50)));
end

function writeText(path, text)
    fileIdentifier = fopen(path, "w");
    if fileIdentifier < 0
        error("InteractiveMissions:FileOpenFailed", "Could not write %s.", path);
    end
    cleanup = onCleanup(@() fclose(fileIdentifier));
    fprintf(fileIdentifier, "%s", text);
    clear cleanup
end
