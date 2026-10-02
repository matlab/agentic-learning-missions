function info = startMissionAuthoring(options)
%startMissionAuthoring - Set up an empty folder for mission authoring
%   INFO = startMissionAuthoring() interactively prepares the current folder
%   as an Interactive Missions authoring workspace.
%
%   INFO = startMissionAuthoring(Name=VALUE) also specifies setup options.
%
%   See also startMissionAuthoring, interactiveMissions.prepareWorkspace

    arguments
        options.WorkspaceRoot (1, 1) string = string(pwd())
        options.AgentClient (1, 1) string = ""
        options.MarketplaceId (1, 1) string = ""
        options.MarketplaceTitle (1, 1) string = ""
        options.SourceUrl (1, 1) string = ""
        options.CreateFirstMission (1, 1) string = "ask"
        options.MissionId (1, 1) string = ""
        options.MissionTitle (1, 1) string = ""
    end

    workspaceRoot = absolutePath(options.WorkspaceRoot);
    ensureEmptyWorkspace(workspaceRoot);

    toolboxRoot = interactiveMissions.internal.toolboxRoot();
    agentRecords = supportedAgentRecords(toolboxRoot);
    agentClient = chooseAgentClient(options.AgentClient, agentRecords);
    marketplaceId = resolveMarketplaceId(options.MarketplaceId, workspaceRoot);
    marketplaceTitle = resolveMarketplaceTitle(options.MarketplaceTitle, workspaceRoot);
    sourceUrl = validateScalar(options.SourceUrl, "SourceUrl");
    createFirstMission = resolveCreateFirstMission( ...
        options.CreateFirstMission, options.MissionId, options.MissionTitle);
    [missionId, missionTitle] = resolveFirstMission( ...
        createFirstMission, options.MissionId, options.MissionTitle);

    authorSkillsRoot = fullfile(toolboxRoot, "src", "author-skills");
    authorAdaptersRoot = fullfile(toolboxRoot, "src", "author-adapters");
    documentationRoot = fullfile(toolboxRoot, "docs");
    validateAssets(authorSkillsRoot, authorAdaptersRoot, documentationRoot, agentClient);

    marketplaceRoot = fullfile(workspaceRoot, "marketplace");
    missionsRoot = fullfile(marketplaceRoot, "missions");
    assetsRoot = fullfile(marketplaceRoot, "assets");
    authoringRoot = fullfile(workspaceRoot, ".interactive-missions", "authoring");
    portableSkillsRoot = fullfile(authoringRoot, "skills");
    workspaceDocsRoot = fullfile(workspaceRoot, "docs");

    createFolder(missionsRoot);
    createFolder(assetsRoot);
    copyTree(documentationRoot, workspaceDocsRoot);
    copyTree(authorSkillsRoot, portableSkillsRoot);
    writeManifest( ...
        fullfile(marketplaceRoot, "manifest.yaml"), marketplaceId, marketplaceTitle, ...
        sourceUrl, agentRecords);
    writeAgentAdapter(workspaceRoot, authorAdaptersRoot, portableSkillsRoot, agentClient);

    missionBriefPath = "";
    missionRoot = "";
    if createFirstMission
        missionRoot = fullfile(missionsRoot, missionId);
        createFolder(missionRoot);
        missionBriefPath = fullfile(missionRoot, "mission-brief.md");
        writeMissionBrief(missionBriefPath, missionId, missionTitle);
    end

    info = struct();
    info.WorkspaceRoot = workspaceRoot;
    info.MarketplaceRoot = marketplaceRoot;
    info.ManifestPath = fullfile(marketplaceRoot, "manifest.yaml");
    info.DocumentationRoot = workspaceDocsRoot;
    info.AuthoringRoot = authoringRoot;
    info.SkillRoot = portableSkillsRoot;
    info.AgentClient = agentClient;
    info.MissionRoot = missionRoot;
    info.MissionBriefPath = missionBriefPath;

    fprintf("Interactive Missions authoring workspace is ready: %s\n", workspaceRoot);
    fprintf("Selected agent: %s\n", agentDisplayName(agentRecords, agentClient));
    if strlength(missionBriefPath) > 0
        fprintf("First mission brief: %s\n", missionBriefPath);
    end
end

function records = supportedAgentRecords(toolboxRoot)
    matrixPath = fullfile(toolboxRoot, "docs", "agent-support-matrix.json");
    if ~isfile(matrixPath)
        error("InteractiveMissions:MissingAgentSupportMatrix", ...
            "Agent support matrix is missing: %s", matrixPath);
    end

    matrix = jsondecode(fileread(matrixPath));
    if ~isfield(matrix, "agents")
        error("InteractiveMissions:InvalidAgentSupportMatrix", ...
            "Agent support matrix does not define agents.");
    end

    records = matrix.agents;
    records = records([records.supported]);
    if isempty(records)
        error("InteractiveMissions:InvalidAgentSupportMatrix", ...
            "Agent support matrix does not define a supported authoring client.");
    end

    requiredFields = ["id", "display_name", "author_adapter_path"];
    for fieldName = requiredFields
        if ~isfield(records, fieldName)
            error("InteractiveMissions:InvalidAgentSupportMatrix", ...
                "Agent support matrix is missing %s.", fieldName);
        end
    end
end

function agentClient = chooseAgentClient(agentClient, records)
    agentClient = normalizeAgentClient(agentClient);
    if strlength(agentClient) == 0
        agentClient = promptForAgent(records);
    end

    supportedIds = string({records.id});
    if ~any(agentClient == supportedIds)
        error("InteractiveMissions:UnsupportedAgentClient", ...
            "Unsupported agent client '%s'.", agentClient);
    end
end

function agentClient = promptForAgent(records)
    fprintf("\nSelect the agentic client for this authoring workspace:\n");
    for recordIndex = 1:numel(records)
        fprintf("  %d. %s\n", recordIndex, string(records(recordIndex).display_name));
    end

    selection = str2double(input("Agent number: ", "s"));
    if ~isscalar(selection) || isnan(selection) || selection ~= floor(selection) || ...
            selection < 1 || selection > numel(records)
        error("InteractiveMissions:InvalidAgentSelection", ...
            "Enter the number of one of the listed agentic clients.");
    end

    agentClient = string(records(selection).id);
end

function value = normalizeAgentClient(value)
    value = lower(strtrim(string(value)));
    value = regexprep(value, "[^a-z0-9]+", "-");
    switch value
        case ""
            return
        case {"codex", "openai-codex"}
            value = "codex";
        case {"claude", "claude-code"}
            value = "claude-code";
        case {"gemini", "gemini-cli"}
            value = "gemini-cli";
        case {"copilot", "github-copilot", "github-copilot-vs-code", "github-copilot-vscode"}
            value = "github-copilot-vscode";
        case {"github-copilot-cli", "copilot-cli", "github-copilot-terminal"}
            value = "github-copilot-cli";
        case {"generic", "other", "generic-other"}
            value = "generic";
        otherwise
            error("InteractiveMissions:UnsupportedAgentClient", ...
                "Unsupported agent client '%s'.", value);
    end
end

function marketplaceId = resolveMarketplaceId(value, workspaceRoot)
    value = strtrim(string(value));
    if strlength(value) == 0
        [~, value] = fileparts(workspaceRoot);
    end

    marketplaceId = slugify(value);
    if strlength(marketplaceId) == 0
        error("InteractiveMissions:InvalidMarketplaceId", ...
            "MarketplaceId must contain letters or numbers.");
    end
end

function marketplaceTitle = resolveMarketplaceTitle(value, workspaceRoot)
    marketplaceTitle = strtrim(string(value));
    if strlength(marketplaceTitle) == 0
        [~, marketplaceTitle] = fileparts(workspaceRoot);
    end
    marketplaceTitle = validateScalar(marketplaceTitle, "MarketplaceTitle");
end

function createFirstMission = resolveCreateFirstMission(value, missionId, missionTitle)
    value = lower(strtrim(string(value)));
    if strlength(value) == 0
        value = "ask";
    end

    if value == "ask" && (strlength(strtrim(missionId)) > 0 || strlength(strtrim(missionTitle)) > 0)
        value = "yes";
    end

    switch value
        case "ask"
            response = lower(strtrim(string(input("Initialize a first mission? [y/N]: ", "s"))));
            createFirstMission = any(response == ["y", "yes"]);
        case {"yes", "true"}
            createFirstMission = true;
        case {"no", "false"}
            createFirstMission = false;
        otherwise
            error("InteractiveMissions:InvalidCreateFirstMission", ...
                "CreateFirstMission must be ""ask"", ""yes"", or ""no"".");
    end

    if ~createFirstMission && ...
            (strlength(strtrim(missionId)) > 0 || strlength(strtrim(missionTitle)) > 0)
        error("InteractiveMissions:UnexpectedMissionDetails", ...
            "MissionId and MissionTitle require CreateFirstMission=""yes"".");
    end
end

function [missionId, missionTitle] = resolveFirstMission(createFirstMission, missionId, missionTitle)
    requestedMissionId = missionId;
    requestedMissionTitle = missionTitle;
    missionId = "";
    missionTitle = "";
    if ~createFirstMission
        return
    end

    missionTitle = strtrim(string(requestedMissionTitle));
    if strlength(missionTitle) == 0
        missionTitle = strtrim(string(input("First mission title: ", "s")));
    end
    missionTitle = validateScalar(missionTitle, "MissionTitle");

    missionId = strtrim(string(requestedMissionId));
    if strlength(missionId) == 0
        missionId = slugify(missionTitle);
    else
        missionId = slugify(missionId);
    end
    if strlength(missionId) == 0
        error("InteractiveMissions:InvalidMissionId", ...
            "MissionId must contain letters or numbers.");
    end
end

function value = slugify(value)
    value = lower(strtrim(string(value)));
    value = regexprep(value, "[^a-z0-9]+", "-");
    value = regexprep(value, "^-+|-+$", "");
end

function value = validateScalar(value, name)
    value = strtrim(string(value));
    if strlength(value) == 0 && name ~= "SourceUrl"
        error("InteractiveMissions:InvalidTextInput", "%s must not be empty.", name);
    end
    if contains(value, ["\r", "\n", char(0)])
        error("InteractiveMissions:InvalidTextInput", ...
            "%s must not contain line breaks.", name);
    end
end

function validateAssets(authorSkillsRoot, authorAdaptersRoot, documentationRoot, agentClient)
    for path = [authorSkillsRoot, authorAdaptersRoot, documentationRoot]
        if ~isfolder(path)
            error("InteractiveMissions:MissingAuthoringAsset", ...
                "Authoring asset folder is missing: %s", path);
        end
    end

    adapterPath = fullfile(authorAdaptersRoot, agentClient, "adapter.yaml");
    if ~isfile(adapterPath)
        error("InteractiveMissions:MissingAuthoringAdapter", ...
            "Authoring adapter is missing: %s", adapterPath);
    end
end

function ensureEmptyWorkspace(workspaceRoot)
    if ~isfolder(workspaceRoot)
        error("InteractiveMissions:WorkspaceNotFound", ...
            "Create the authoring folder first, then run startMissionAuthoring from that folder: %s", ...
            workspaceRoot);
    end

    listing = dir(workspaceRoot);
    names = string({listing.name});
    if ~all(names == "." | names == "..")
        error("InteractiveMissions:WorkspaceNotEmpty", ...
            "Choose an empty folder for a new authoring workspace: %s", workspaceRoot);
    end
end

function workspaceRoot = absolutePath(workspaceRoot)
    workspaceRoot = strtrim(string(workspaceRoot));
    if strlength(workspaceRoot) == 0
        error("InteractiveMissions:InvalidWorkspace", "WorkspaceRoot must not be empty.");
    end
    if contains(workspaceRoot, "..")
        error("InteractiveMissions:InvalidWorkspace", ...
            "WorkspaceRoot must not contain parent-folder references.");
    end
    if ~interactiveMissions.internal.isAbsolutePath(workspaceRoot)
        workspaceRoot = fullfile(pwd(), workspaceRoot);
    end
    workspaceRoot = replace(workspaceRoot, "/", filesep);
end

function writeManifest(manifestPath, marketplaceId, marketplaceTitle, sourceUrl, records)
    sourceUrlLine = "source_url: '' # TODO: Set this before registering or publishing the marketplace.";
    if strlength(sourceUrl) > 0
        sourceUrlLine = "source_url: " + yamlString(sourceUrl);
    end

    lines = [
        "schema_version: ""2.0"""
        "id: " + yamlString(marketplaceId)
        "title: " + yamlString(marketplaceTitle)
        sourceUrlLine
        "content_version: ""0.1.0"""
        "minimum_toolbox_version: ""0.2.0"""
        "summary: ""Draft marketplace created by Interactive Missions."""
        "adapters:"
        ];
    for recordIndex = 1:numel(records)
        lines(end + 1, 1) = "  - id: " + yamlString(string(records(recordIndex).id)); %#ok<AGROW>
    end
    lines = [lines; "missions: []"];
    writeText(manifestPath, strjoin(lines, newline) + newline);
end

function writeAgentAdapter(workspaceRoot, adaptersRoot, portableSkillsRoot, agentClient)
    adapterRoot = fullfile(adaptersRoot, agentClient);
    mappings = adapterFileMappings(fullfile(adapterRoot, "adapter.yaml"));
    for mappingIndex = 1:numel(mappings)
        sourcePath = fullfile(adapterRoot, mappings(mappingIndex).Source);
        if ~isfile(sourcePath)
            error("InteractiveMissions:MissingAuthoringAdapter", ...
                "Authoring adapter template is missing: %s", sourcePath);
        end
        targetPath = fullfile(workspaceRoot, mappings(mappingIndex).Target);
        validateRelativePath(mappings(mappingIndex).Target);
        writeText(targetPath, fileread(sourcePath));
    end

    if agentClient == "codex"
        skillNames = ["create-tutor-mission", "qa-mission", "maintain-missions"];
        for skillName = skillNames
            sourceRoot = fullfile(portableSkillsRoot, skillName);
            targetRoot = fullfile(workspaceRoot, ".codex", "skills", skillName);
            copyTree(sourceRoot, targetRoot);
        end
        copyTree(fullfile(portableSkillsRoot, "references"), ...
            fullfile(workspaceRoot, ".codex", "skills", "references"));
    end
end

function mappings = adapterFileMappings(adapterManifestPath)
    manifestText = string(fileread(adapterManifestPath));
    sourceTokens = regexp(manifestText, "(?m)^\s+- source:\s*[""']?([^""'\r\n]+)[""']?\s*$", "tokens");
    targetTokens = regexp(manifestText, "(?m)^\s+target:\s*[""']?([^""'\r\n]+)[""']?\s*$", "tokens");
    if isempty(sourceTokens) || numel(sourceTokens) ~= numel(targetTokens)
        error("InteractiveMissions:InvalidAuthoringAdapter", ...
            "Authoring adapter must list matching source and target files: %s", adapterManifestPath);
    end

    mappings = struct("Source", {}, "Target", {});
    for mappingIndex = 1:numel(sourceTokens)
        mappings(mappingIndex).Source = string(sourceTokens{mappingIndex}{1});
        mappings(mappingIndex).Target = string(targetTokens{mappingIndex}{1});
    end
end

function writeMissionBrief(path, missionId, missionTitle)
    lines = [
        "# Mission Brief"
        ""
        "Use `create-tutor-mission` to turn this brief into `mission.yaml`."
        ""
        "- Mission title: " + missionTitle
        "- Mission folder ID: `" + missionId + "`"
        "- Legacy mission ID: Choose a quoted two-digit value during authoring."
        ""
        "Keep this title and folder ID unless the author explicitly changes them."
        ];
    writeText(path, strjoin(lines, newline) + newline);
end

function copyTree(sourceRoot, targetRoot)
    files = dir(fullfile(sourceRoot, "**", "*"));
    files = files(~[files.isdir]);
    for fileIndex = 1:numel(files)
        sourcePath = fullfile(files(fileIndex).folder, files(fileIndex).name);
        relativePath = erase(string(sourcePath), string(sourceRoot) + filesep);
        targetPath = fullfile(targetRoot, relativePath);
        targetFolder = fileparts(targetPath);
        createFolder(targetFolder);
        copyfile(sourcePath, targetPath, "f");
    end
end

function createFolder(folder)
    if ~isfolder(folder)
        mkdir(folder);
    end
end

function writeText(path, text)
    createFolder(fileparts(path));
    fileIdentifier = fopen(path, "w");
    if fileIdentifier < 0
        error("InteractiveMissions:FileOpenFailed", "Could not write %s.", path);
    end
    cleanup = onCleanup(@() fclose(fileIdentifier));
    fprintf(fileIdentifier, "%s", text);
    clear cleanup
end

function validateRelativePath(path)
    path = string(path);
    if contains(path, "..") || interactiveMissions.internal.isAbsolutePath(path)
        error("InteractiveMissions:UnsafePath", "Unsafe adapter path: %s", path);
    end
end

function value = yamlString(value)
    value = replace(string(value), "'", "''");
    value = "'" + value + "'";
end

function name = agentDisplayName(records, agentClient)
    index = find(string({records.id}) == agentClient, 1);
    name = string(records(index).display_name);
end
