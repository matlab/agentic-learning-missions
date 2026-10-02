function validate_runtime(root, varargin)
%VALIDATE_RUNTIME Run opt-in runtime checks for Interactive Missions.
%   VALIDATE_RUNTIME validates repository infrastructure only.
%   VALIDATE_RUNTIME(ROOT) validates repository infrastructure at ROOT.
%   VALIDATE_RUNTIME(ROOT, "Scope", "missions", "Mission", "all") validates
%   packaged mission content. Scope can be "infrastructure", "missions", or
%   "all"; Mission can be "all" or a mission ID such as "01".

    if nargin < 1
        root = defaultRoot();
    elseif isRuntimeOptionName(root)
        varargin = [{root}, varargin];
        root = defaultRoot();
    elseif strlength(string(root)) == 0
        root = defaultRoot();
    end

    options = parseRuntimeOptions(varargin{:});
    root = char(root);

    if options.Scope == "infrastructure" || options.Scope == "all"
        validateInfrastructureRuntime(root);
        disp("PASS: infrastructure runtime")
    end

    if options.Scope == "missions" || options.Scope == "all"
        if ~simulinkAvailable()
            disp("SKIP: mission content tests require Simulink.")
        else
            validateMissionContentRuntime(root, options.Mission);
            disp("PASS: mission content runtime")
        end
    end

    disp("")
    disp("All runtime validation checks passed.")
end

function root = defaultRoot()
    candidate = string(pwd());
    while strlength(candidate) > 0
        if isfile(fullfile(candidate, "src", "interactiveMissionsApp.m")) && ...
                isfile(fullfile(candidate, "marketplace", "missions", ...
                "root-inports-outports", "mission.yaml"))
            root = candidate;
            return
        end

        parent = string(fileparts(candidate));
        if parent == candidate
            break
        end
        candidate = parent;
    end

    error("InteractiveMissions:RootNotFound", ...
        "Cannot find the Interactive Missions repository root from the current folder.");
end

function result = isRuntimeOptionName(value)
    value = string(value);
    result = isscalar(value) && any(strcmpi(value, ["Scope", "Mission"]));
end

function options = parseRuntimeOptions(varargin)
    parser = inputParser;
    addParameter(parser, "Scope", "infrastructure", @isValidScope);
    addParameter(parser, "Mission", "all", @isTextScalar);
    parse(parser, varargin{:});

    options = struct();
    options.Scope = lower(string(parser.Results.Scope));
    options.Mission = string(parser.Results.Mission);
end

function result = isValidScope(value)
    result = isTextScalar(value) && any(strcmpi(string(value), ["infrastructure", "missions", "all"]));
end

function result = isTextScalar(value)
    value = string(value);
    result = isscalar(value) && strlength(strtrim(value)) > 0;
end

function result = simulinkAvailable()
    result = license("test", "Simulink") && exist("new_system", "builtin") == 5;
end

function validateInfrastructureRuntime(root)
    validateProgressLifecycle(root);
end

function validateMissionContentRuntime(root, missionSelection)
    content = fullfile(root, "marketplace", "missions");
    missions = discoverMissions(content, missionSelection, root);

    originalPath = path;
    originalFolder = pwd;
    originalFigures = findall(groot, "Type", "figure");
    originalModels = loadedModels();
    originalWorkspace = baseWorkspaceNames();
    progressBefore = progressSnapshot(root);
    cleanup = onCleanup(@() cleanupRuntimeState(originalPath, originalFolder, ...
        originalFigures, originalModels, originalWorkspace));

    for missionIndex = 1:numel(missions)
        validateSingleMission(root, content, missions(missionIndex), originalPath, ...
            originalFolder, originalFigures, originalModels, originalWorkspace, progressBefore);
    end

    require(strcmp(pwd, originalFolder), "runtime scripts must not change the current folder");
    require(isequal(progressBefore, progressSnapshot(root)), ...
        "runtime scripts must not create or modify repository progress files");
    clear cleanup
end

function validateSingleMission(root, content, mission, originalPath, originalFolder, ...
        originalFigures, originalModels, originalWorkspace, progressBefore)
    missionRoot = string(fileparts(mission.Path));
    resetFolder = fullfile(missionRoot, "task_reset_" + mission.Id);

    path(originalPath);
    addpath(content);
    if isfolder(resetFolder)
        addpath(resetFolder);
    end
    expectedPath = path;

    closeNewFigures(originalFigures);
    closeNewModels(originalModels);
    clearNewWorkspaceVariables(originalWorkspace);

    setupWorkspace = originalWorkspace;
    if strlength(mission.SetupScript) > 0
        runBaseScript(fullfile(missionRoot, mission.SetupScript));
        requireRuntimeState(root, originalFolder, expectedPath, progressBefore);
        setupWorkspace = baseWorkspaceNames();
    else
        disp("SKIP: mission " + mission.Id + " setup (none declared)")
    end

    if isempty(mission.Validation.SetupAssertions)
        disp("SKIP: mission " + mission.Id + " setup assertions (none declared)")
    else
        runAssertions(mission.Validation.SetupAssertions, "mission " + mission.Id + " setup", originalFigures);
    end

    if ~isfolder(resetFolder)
        disp("SKIP: mission " + mission.Id + " resets (no reset folder)")
        clearNewWorkspaceVariables(originalWorkspace);
        closeNewFigures(originalFigures);
        closeNewModels(originalModels);
        path(originalPath);
        return
    end

    for taskId = mission.TaskIds(2:end)'
        resetFile = fullfile(resetFolder, "reset_" + taskId + ".m");
        require(isfile(resetFile), "missing reset script: " + rel(resetFile, root));

        closeNewFigures(originalFigures);
        closeNewModels(originalModels);
        clearNewWorkspaceVariables(setupWorkspace);

        runBaseScript(resetFile);
        requireRuntimeState(root, originalFolder, expectedPath, progressBefore);

        assertions = assertionsForTask(mission.Validation, taskId);
        if isempty(assertions)
            disp("SKIP: mission " + mission.Id + " " + taskId + " assertions (none declared)")
        else
            runAssertions(assertions, "mission " + mission.Id + " " + taskId, originalFigures);
        end
    end

    clearNewWorkspaceVariables(originalWorkspace);
    closeNewFigures(originalFigures);
    closeNewModels(originalModels);
    path(originalPath);
end

function requireRuntimeState(root, originalFolder, expectedPath, progressBefore)
    require(strcmp(pwd, originalFolder), "runtime scripts must not change the current folder");
    require(strcmp(path, expectedPath), "runtime scripts must not permanently alter the MATLAB path");
    require(isequal(progressBefore, progressSnapshot(root)), ...
        "runtime scripts must not create or modify repository progress files");
end

function missions = discoverMissions(content, missionSelection, root)
    files = dir(fullfile(content, "*", "mission.yaml"));
    require(~isempty(files), "marketplace content must include at least one mission.yaml file");

    paths = strings(numel(files), 1);
    for k = 1:numel(files)
        paths(k) = string(fullfile(files(k).folder, files(k).name));
    end
    paths = sort(paths);

    missionSelection = string(missionSelection);
    missions = struct("Id", {}, "MissionId", {}, "Path", {}, "TaskIds", {}, "SetupScript", {}, "Validation", {});
    for pathIndex = 1:numel(paths)
        missionPath = paths(pathIndex);
        mission = readMissionDefinition(missionPath, root);
        if missionSelection == "all" || mission.Id == missionSelection || mission.MissionId == missionSelection
            missions(end + 1) = mission; %#ok<AGROW>
        end
    end

    require(~isempty(missions), "no packaged mission matched Mission '" + missionSelection + "'");
end

function mission = readMissionDefinition(missionPath, root)
    text = string(fileread(missionPath));
    missionName = missionNameFromPath(missionPath, root);
    missionId = topScalar(text, "mission_id");
    require(~isempty(regexp(missionId, "^\d{2}$", "once")), ...
        getFilename(missionPath) + " must declare a quoted two-digit mission_id");

    taskIds = missionTaskIds(missionPath);
    mission = struct();
    mission.Id = missionName;
    mission.MissionId = missionId;
    mission.Path = missionPath;
    mission.TaskIds = taskIds;
    mission.SetupScript = missionSetupScript(text);
    mission.Validation = parseRuntimeValidation(text, taskIds, rel(missionPath, root));
end

function missionName = missionNameFromPath(path, root)
    filename = getFilename(path);
    require(filename == "mission.yaml", "mission file must be named mission.yaml: " + rel(path, root));
    [~, missionName] = fileparts(fileparts(path));
    missionName = string(missionName);
    require(~isempty(regexp(missionName, "^[a-z0-9]+(?:-[a-z0-9]+)*$", "once")), ...
        "mission folder must use a lowercase slug: " + rel(fileparts(path), root));
end

function filename = getFilename(path)
    [~, name, extension] = fileparts(path);
    filename = string(name) + string(extension);
end

function setupScript = missionSetupScript(text)
    lines = splitlines(text);
    setupBlock = topBlockLines(lines, "setup");
    setupScript = "";
    if isempty(setupBlock)
        return
    end

    tokens = regexp(setupBlock, "^\s+script:\s*[""']?([^""'\r\n]+)[""']?\s*$", "tokens", "once");
    matchIndex = find(~cellfun(@isempty, tokens), 1);
    if ~isempty(matchIndex)
        setupScript = string(tokens{matchIndex}{1});
    end
end

function value = topScalar(text, key)
    pattern = "(?m)^" + key + ":\s*[""']?([^""'\r\n]+)[""']?\s*$";
    tokens = regexp(text, pattern, "tokens", "once");
    require(~isempty(tokens), "mission YAML missing required top-level scalar: " + key);
    value = string(tokens{1});
end

function taskIds = missionTaskIds(missionPath)
    text = string(fileread(missionPath));
    tokens = regexp(text, "(?m)^\s+- id:\s*""(t\d{2})""", "tokens");
    require(~isempty(tokens), getFilename(missionPath) + " must declare task IDs for runtime validation");
    taskIds = strings(numel(tokens), 1);
    for k = 1:numel(tokens)
        taskIds(k) = string(tokens{k}{1});
    end
end

function validation = parseRuntimeValidation(text, taskIds, sourceLabel)
    validation = struct();
    validation.SetupAssertions = emptyAssertions();
    validation.ResetTasks = strings(0, 1);
    validation.ResetAssertions = cell(0, 1);

    lines = splitlines(text);
    validationBlock = topBlockLines(lines, "runtime_validation");
    if isempty(validationBlock)
        return
    end

    setupBlock = childBlockLines(validationBlock, "setup");
    if ~isempty(setupBlock)
        validation.SetupAssertions = parseAssertionsFromParent(setupBlock, sourceLabel + " runtime_validation.setup");
    end

    resetBlock = childBlockLines(validationBlock, "resets");
    if ~isempty(resetBlock)
        [validation.ResetTasks, validation.ResetAssertions] = parseResetAssertions(resetBlock, taskIds, sourceLabel);
    end
end

function [resetTasks, resetAssertions] = parseResetAssertions(resetBlock, taskIds, sourceLabel)
    starts = find(startsWith(strtrim(resetBlock), "- task:"));
    require(~isempty(starts), sourceLabel + " runtime_validation.resets must list reset tasks");

    resetTasks = strings(numel(starts), 1);
    resetAssertions = cell(numel(starts), 1);
    for k = 1:numel(starts)
        chunk = listItemChunk(resetBlock, starts, k);
        taskId = parseYamlScalar(extractAfter(strtrim(chunk(1)), "- task:"));
        require(any(taskIds == taskId), sourceLabel + " runtime_validation references unknown task " + taskId);
        require(~any(resetTasks(1:k - 1) == taskId), sourceLabel + " runtime_validation repeats task " + taskId);
        resetTasks(k) = taskId;
        resetAssertions{k} = parseAssertionsFromParent(chunk, ...
            sourceLabel + " runtime_validation.resets." + taskId);
    end
end

function assertions = parseAssertionsFromParent(parentBlock, sourceLabel)
    assertionsBlock = childBlockLines(parentBlock, "assertions");
    require(~isempty(assertionsBlock), sourceLabel + " must include assertions");
    assertions = parseAssertionItems(assertionsBlock, sourceLabel);
end

function assertions = parseAssertionItems(lines, sourceLabel)
    starts = find(startsWith(strtrim(lines), "- type:"));
    require(~isempty(starts), sourceLabel + " assertions must not be empty");

    assertions = emptyAssertions();
    for k = 1:numel(starts)
        chunk = listItemChunk(lines, starts, k);
        assertion = defaultAssertion();
        assertion.Type = parseYamlScalar(extractAfter(strtrim(chunk(1)), "- type:"));
        for lineIndex = 2:numel(chunk)
            line = strtrim(chunk(lineIndex));
            if isIgnorableYamlLine(line) || startsWith(line, "- ")
                continue
            end
            tokens = regexp(line, "^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", "tokens", "once");
            if isempty(tokens)
                continue
            end
            assertion = setAssertionField(assertion, string(tokens{1}), string(tokens{2}), sourceLabel);
        end
        validateAssertionShape(assertion, sourceLabel);
        assertions(end + 1, 1) = assertion; %#ok<AGROW>
    end
end

function assertion = setAssertionField(assertion, key, rawValue, sourceLabel)
    switch key
        case "name"
            assertion.Name = parseYamlScalar(rawValue);
        case "class"
            assertion.Class = parseYamlScalar(rawValue);
        case "path"
            assertion.Path = parseYamlScalar(rawValue);
        case "block_type"
            assertion.BlockType = parseYamlScalar(rawValue);
        case "parameter"
            assertion.Parameter = parseYamlScalar(rawValue);
        case "equals"
            assertion.Equals = parseYamlScalar(rawValue);
        case "any_of"
            assertion.AnyOf = parseYamlList(rawValue, sourceLabel);
        case "source"
            assertion.Source = parseYamlScalar(rawValue);
        case "min_new_figures"
            assertion.MinNewFigures = str2double(parseYamlScalar(rawValue));
        case "description"
            assertion.Description = parseYamlScalar(rawValue);
        case "code"
            assertion.Code = parseYamlScalar(rawValue);
        otherwise
            require(false, sourceLabel + " uses unsupported assertion field: " + key);
    end
end

function validateAssertionShape(assertion, sourceLabel)
    supportedTypes = [
        "workspace_var"
        "workspace_absent"
        "model_loaded"
        "block_exists"
        "block_param"
        "line_source"
        "figure_count"
        "matlab_expression"
    ];
    require(any(supportedTypes == assertion.Type), sourceLabel + " uses unsupported assertion type: " + assertion.Type);

    switch assertion.Type
        case "workspace_var"
            require(hasText(assertion.Name), sourceLabel + " workspace_var requires name");
        case "workspace_absent"
            require(hasText(assertion.Name), sourceLabel + " workspace_absent requires name");
        case "model_loaded"
            require(hasText(assertion.Name), sourceLabel + " model_loaded requires name");
        case "block_exists"
            require(hasText(assertion.Path), sourceLabel + " block_exists requires path");
        case "block_param"
            require(hasText(assertion.Path), sourceLabel + " block_param requires path");
            require(hasText(assertion.Parameter), sourceLabel + " block_param requires parameter");
            require(hasText(assertion.Equals) || ~isempty(assertion.AnyOf), ...
                sourceLabel + " block_param requires equals or any_of");
        case "line_source"
            require(hasText(assertion.Path), sourceLabel + " line_source requires path");
            require(hasText(assertion.Source), sourceLabel + " line_source requires source");
        case "figure_count"
            require(~isnan(assertion.MinNewFigures) && assertion.MinNewFigures >= 0, ...
                sourceLabel + " figure_count requires min_new_figures");
        case "matlab_expression"
            require(hasText(assertion.Description), sourceLabel + " matlab_expression requires description");
            require(hasText(assertion.Code), sourceLabel + " matlab_expression requires code");
    end
end

function result = hasText(value)
    result = strlength(strtrim(string(value))) > 0;
end

function assertion = defaultAssertion()
    assertion = struct();
    assertion.Type = "";
    assertion.Name = "";
    assertion.Class = "";
    assertion.Path = "";
    assertion.BlockType = "";
    assertion.Parameter = "";
    assertion.Equals = "";
    assertion.AnyOf = strings(0, 1);
    assertion.Source = "";
    assertion.MinNewFigures = NaN;
    assertion.Description = "";
    assertion.Code = "";
end

function assertions = emptyAssertions()
    assertions = repmat(defaultAssertion(), 0, 1);
end

function values = parseYamlList(rawValue, sourceLabel)
    rawValue = strtrim(string(rawValue));
    require(startsWith(rawValue, "[") && endsWith(rawValue, "]"), sourceLabel + " any_of must be an inline list");
    inner = extractBetween(rawValue, 2, strlength(rawValue) - 1);
    if strlength(strtrim(inner)) == 0
        values = strings(0, 1);
        return
    end

    parts = strtrim(split(inner, ","));
    values = strings(numel(parts), 1);
    for k = 1:numel(parts)
        values(k) = parseYamlScalar(parts(k));
    end
end

function value = parseYamlScalar(rawValue)
    value = strtrim(string(rawValue));
    if (startsWith(value, '"') && endsWith(value, '"')) || (startsWith(value, "'") && endsWith(value, "'"))
        value = extractBetween(value, 2, strlength(value) - 1);
    end
end

function assertions = assertionsForTask(validation, taskId)
    index = find(validation.ResetTasks == taskId, 1);
    if isempty(index)
        assertions = emptyAssertions();
    else
        assertions = validation.ResetAssertions{index};
    end
end

function runAssertions(assertions, context, originalFigures)
    for k = 1:numel(assertions)
        runAssertion(assertions(k), context, originalFigures);
    end
end

function runAssertion(assertion, context, originalFigures)
    switch assertion.Type
        case "workspace_var"
            name = resolveRuntimeText(assertion.Name);
            require(baseLogical("exist(" + matlabString(name) + ", ""var"") == 1"), ...
                context + " must leave workspace variable " + name);
            if hasText(assertion.Class)
                className = resolveRuntimeText(assertion.Class);
                require(baseLogical("isa(" + name + ", " + matlabString(className) + ")"), ...
                    context + " must create " + name + " as a " + className);
            end
        case "workspace_absent"
            name = resolveRuntimeText(assertion.Name);
            require(~baseLogical("exist(" + matlabString(name) + ", ""var"") == 1"), ...
                context + " must not leave workspace variable " + name);
        case "model_loaded"
            modelName = resolveRuntimeText(assertion.Name);
            require(bdIsLoaded(modelName), context + " must load model " + modelName);
        case "block_exists"
            blockPath = resolveRuntimeText(assertion.Path);
            requireBlock(blockPath, resolveRuntimeText(assertion.BlockType), context);
        case "block_param"
            blockPath = resolveRuntimeText(assertion.Path);
            parameter = resolveRuntimeText(assertion.Parameter);
            actualValue = string(get_param(blockPath, parameter));
            if hasText(assertion.Equals)
                expectedValue = resolveRuntimeText(assertion.Equals);
                require(actualValue == expectedValue, context + " expected " + blockPath + ...
                    " " + parameter + " to equal " + expectedValue);
            else
                expectedValues = resolveRuntimeTextArray(assertion.AnyOf);
                require(any(actualValue == expectedValues), context + " expected " + blockPath + ...
                    " " + parameter + " to be one of " + strjoin(expectedValues, ", "));
            end
        case "line_source"
            requireInputSource(resolveRuntimeText(assertion.Path), resolveRuntimeText(assertion.Source), context);
        case "figure_count"
            allFigures = findall(groot, "Type", "figure");
            newFigureCount = numel(setdiff(allFigures, originalFigures));
            require(newFigureCount >= assertion.MinNewFigures, context + " expected at least " + ...
                string(assertion.MinNewFigures) + " new figure(s)");
        case "matlab_expression"
            code = resolveRuntimeText(assertion.Code);
            description = resolveRuntimeText(assertion.Description);
            require(baseLogical(code), context + " failed assertion: " + description);
    end
end

function value = resolveRuntimeText(value)
    value = string(value);
    tokens = regexp(value, "\$\{([A-Za-z]\w*)\}", "tokens");
    for k = 1:numel(tokens)
        variableName = string(tokens{k}{1});
        require(baseLogical("exist(" + matlabString(variableName) + ", ""var"") == 1"), ...
            "runtime validation reference could not be resolved: ${" + variableName + "}");
        supportedType = "(isstring(" + variableName + ") && isscalar(" + variableName + ")) || " + ...
            "(ischar(" + variableName + ") && (isrow(" + variableName + ") || isempty(" + variableName + ")))";
        require(baseLogical(supportedType), ...
            "runtime validation reference must resolve to scalar string or char: ${" + variableName + "}");
        replacement = string(evalin("base", variableName));
        value = replace(value, "${" + variableName + "}", replacement);
    end
end

function values = resolveRuntimeTextArray(values)
    for k = 1:numel(values)
        values(k) = resolveRuntimeText(values(k));
    end
end

function requireBlock(blockPath, blockType, context)
    require(getSimulinkBlockHandle(blockPath) ~= -1, context + " expected block " + blockPath);
    if hasText(blockType)
        require(strcmp(get_param(blockPath, "BlockType"), blockType), ...
            context + " expected " + blockPath + " to be a " + blockType + " block");
    end
end

function requireInputSource(destBlock, sourceName, context)
    lineHandles = get_param(destBlock, "LineHandles");
    require(~isempty(lineHandles.Inport) && lineHandles.Inport(1) ~= -1, ...
        context + " expected " + destBlock + " to have an input line");
    sourceHandle = get_param(lineHandles.Inport(1), "SrcBlockHandle");
    require(sourceHandle ~= -1 && strcmp(get_param(sourceHandle, "Name"), sourceName), ...
        context + " expected " + destBlock + " input to come from " + sourceName);
end

function validateProgressLifecycle(root)
    missions = discoverMissions(fullfile(root, "marketplace", "missions"), "all", root);
    mission = missions(1);
    taskIds = mission.TaskIds;
    progressRoot = tempname;
    mkdir(progressRoot);
    cleanup = onCleanup(@() removeFolder(progressRoot));
    progressFolder = fullfile(progressRoot, "progress");
    mkdir(progressFolder);

    newState = makeProgress("", mission.MissionId, taskIds(1), strings(0, 1), struct(), "", "");
    validateProgressState(jsonRoundTrip(progressFolder, "new.json", newState), mission.MissionId, taskIds);

    resumedIndex = min(5, numel(taskIds));
    resumedState = makeProgress("ada", mission.MissionId, taskIds(resumedIndex), taskIds(1:resumedIndex - 1), ...
        struct(taskIds(1), 1), "2026-08-04", "Ready to resume the mission.");
    validateProgressState(jsonRoundTrip(progressFolder, "resumed.json", resumedState), mission.MissionId, taskIds);

    completedState = makeProgress("ada", mission.MissionId, "complete", taskIds, struct(taskIds(min(3, numel(taskIds))), 2), ...
        "2026-08-04", "Completed the mission.");
    validateProgressState(jsonRoundTrip(progressFolder, "complete.json", completedState), mission.MissionId, taskIds);

    unnamedActiveState = makeProgress("", mission.MissionId, taskIds(resumedIndex), taskIds(1:resumedIndex - 1), ...
        struct(taskIds(1), 1), "2026-08-04", "Started without a name.");
    validateProgressFailure(jsonRoundTrip(progressFolder, "unnamed-active.json", unnamedActiveState), mission.MissionId, taskIds, ...
        "progress learnerName must be non-empty after Task 1 starts");

    unnamedCompleteState = makeProgress("", mission.MissionId, "complete", taskIds, struct(), "2026-08-04", "Completed without a name.");
    validateProgressFailure(jsonRoundTrip(progressFolder, "unnamed-complete.json", unnamedCompleteState), mission.MissionId, taskIds, ...
        "progress learnerName must be non-empty after Task 1 starts");

    validateMalformedProgress(progressFolder);
    validatePracticeModeDocs(root, progressFolder);
    clear cleanup
end

function progress = makeProgress(learnerId, missionId, currentTask, completedTasks, hintCounts, lastSession, notes)
    progress = struct();
    progress.schemaVersion = "2.0";
    progress.learnerName = learnerId;
    progress.marketplaceSource = "mathworks-interactive-missions";
    progress.missionId = missionId;
    progress.missionVersion = "";
    progress.workspacePath = "";
    progress.mode = "regular";
    progress.currentStepId = currentTask;
    progress.completedStepIds = cellstr(completedTasks(:));
    progress.hintCounts = hintCounts;
    progress.updatedAt = lastSession;
    progress.notes = notes;
end

function progress = jsonRoundTrip(folder, filename, progress)
    path = fullfile(folder, filename);
    writeText(path, jsonencode(progress));
    progress = readProgress(path);
end

function progress = readProgress(path)
    try
        progress = jsondecode(fileread(path));
    catch ME
        error("InteractiveMissions:MalformedProgress", ...
            "progress file is not valid JSON: %s", ME.message);
    end
end

function validateProgressState(progress, missionId, taskIds)
    for field = requiredProgressFields()
        require(isfield(progress, field), "progress file missing required field: " + field);
    end

    currentTask = string(progress.currentStepId);
    completedTasks = string(progress.completedStepIds);
    require(strcmp(string(progress.missionId), missionId), "progress missionId must match packaged mission");
    if currentTask == "complete"
        require(strlength(strtrim(string(progress.learnerName))) > 0, ...
            "progress learnerName must be non-empty after Task 1 starts");
        require(all(ismember(taskIds, completedTasks)), ...
            "complete progress state must list every task as completed");
        return
    end

    currentIndex = find(taskIds == currentTask, 1);
    require(~isempty(currentIndex), "active progress currentStepId must be a mission task ID");
    if currentIndex > 1 || ~isempty(completedTasks)
        require(strlength(strtrim(string(progress.learnerName))) > 0, ...
            "progress learnerName must be non-empty after Task 1 starts");
    end
    require(all(ismember(completedTasks, taskIds)), "completedStepIds must only contain mission task IDs");
    require(~any(completedTasks == currentTask), "currentStepId must not also be completed");
    require(all(ismember(taskIds(1:currentIndex - 1), completedTasks)), ...
        "resumed progress must include all tasks before currentStepId as completed");
end

function validateProgressFailure(progress, missionId, taskIds, expectedMessage)
    try
        validateProgressState(progress, missionId, taskIds);
        error("InteractiveMissions:ExpectedProgressFailure", ...
            "progress validation was expected to fail");
    catch ME
        require(contains(string(ME.message), expectedMessage), ...
            "progress validation must reject invalid blank learnerName state");
    end
end

function validateMalformedProgress(folder)
    malformedPath = fullfile(folder, "malformed.json");
    writeText(malformedPath, "{not valid json");
    try
        readProgress(malformedPath);
        error("InteractiveMissions:ExpectedMalformedProgress", ...
            "malformed progress must fail validation");
    catch ME
        require(strcmp(ME.identifier, "InteractiveMissions:MalformedProgress"), ...
            "malformed progress must report a clear validation error");
    end
end

function validatePracticeModeDocs(root, progressFolder)
    before = string({dir(fullfile(progressFolder, "*.json")).name});
    tutorText = fileread(fullfile(root, "src", "skills", "mission-tutoring", "SKILL.md"));
    readmeText = fileread(fullfile(root, "README.md"));
    require(contains(tutorText, "Practice promoted to tracked"), ...
        "tutor skill must explain how practice mode can become tracked");
    require(contains(tutorText, "do not create this file unless the learner explicitly asks"), ...
        "tutor skill must not create practice progress until explicit opt-in");
    require(contains(lower(readmeText), "practice mode"), ...
        "learner plugin README must describe practice mode");
    after = string({dir(fullfile(progressFolder, "*.json")).name});
    require(isequal(before, after), "practice-mode validation must not create progress files");
end

function values = requiredProgressFields()
    values = ["schemaVersion", "learnerName", "marketplaceSource", "missionId", ...
        "missionVersion", "workspacePath", "mode", "currentStepId", "completedStepIds", ...
        "hintCounts", "updatedAt", "notes"];
end

function block = topBlockLines(lines, key)
    pattern = "^" + key + ":\s*$";
    startIndex = find(~cellfun(@isempty, regexp(cellstr(lines), pattern, "once")), 1);
    if isempty(startIndex)
        block = strings(0, 1);
        return
    end
    block = followingIndentedBlock(lines, startIndex, 0);
end

function block = childBlockLines(lines, key)
    targetIndent = directChildIndent(lines);
    if isnan(targetIndent)
        block = strings(0, 1);
        return
    end

    pattern = "^\s{" + string(targetIndent) + "}" + key + ":\s*$";
    startIndex = find(~cellfun(@isempty, regexp(cellstr(lines), pattern, "once")), 1);
    if isempty(startIndex)
        block = strings(0, 1);
        return
    end
    block = followingIndentedBlock(lines, startIndex, indentOf(lines(startIndex)));
end

function block = followingIndentedBlock(lines, startIndex, parentIndent)
    blockEnd = numel(lines);
    for k = startIndex + 1:numel(lines)
        line = lines(k);
        if isIgnorableYamlLine(line)
            continue
        end
        if indentOf(line) <= parentIndent
            blockEnd = k - 1;
            break
        end
    end
    block = lines(startIndex + 1:blockEnd);
    block = block(~arrayfun(@isIgnorableYamlLine, block));
end

function chunk = listItemChunk(lines, starts, itemIndex)
    firstLine = starts(itemIndex);
    if itemIndex < numel(starts)
        lastLine = starts(itemIndex + 1) - 1;
    else
        lastLine = numel(lines);
    end
    chunk = lines(firstLine:lastLine);
end

function indent = directChildIndent(lines)
    indent = NaN;
    for k = 1:numel(lines)
        line = lines(k);
        trimmedLine = strtrim(line);
        if isIgnorableYamlLine(line) || startsWith(trimmedLine, "- ")
            continue
        end
        currentIndent = indentOf(line);
        if isnan(indent) || currentIndent < indent
            indent = currentIndent;
        end
    end
end

function result = isIgnorableYamlLine(line)
    trimmedLine = strtrim(line);
    result = strlength(trimmedLine) == 0 || startsWith(trimmedLine, "#");
end

function indent = indentOf(line)
    token = regexp(char(line), "^(\s*)", "tokens", "once");
    if isempty(token)
        indent = 0;
    else
        indent = strlength(string(token{1}));
    end
end

function runBaseScript(scriptPath)
    evalin("base", "run(" + matlabString(scriptPath) + ")");
end

function result = baseLogical(expression)
    try
        result = logical(evalin("base", expression));
    catch
        result = false;
    end
end

function names = baseWorkspaceNames()
    names = string(evalin("base", "who"));
    names = sort(names(:));
end

function clearNewWorkspaceVariables(originalWorkspace)
    currentWorkspace = baseWorkspaceNames();
    newVariables = setdiff(currentWorkspace, originalWorkspace);
    for variableName = newVariables(:)'
        evalin("base", "clear " + variableName);
    end
end

function models = loadedModels()
    try
        models = string(find_system("SearchDepth", 0, "Type", "block_diagram"));
        models = sort(models(:));
    catch
        models = strings(0, 1);
    end
end

function cleanupRuntimeState(originalPath, originalFolder, originalFigures, originalModels, originalWorkspace)
    path(originalPath);
    if isfolder(originalFolder)
        cd(originalFolder);
    end
    closeNewModels(originalModels);
    closeNewFigures(originalFigures);
    clearNewWorkspaceVariables(originalWorkspace);
end

function closeNewModels(originalModels)
    currentModels = loadedModels();
    newModels = setdiff(currentModels, originalModels);
    for modelName = newModels(:)'
        if bdIsLoaded(modelName)
            close_system(modelName, 0);
        end
    end
end

function closeNewFigures(originalFigures)
    allFigures = findall(groot, "Type", "figure");
    newFigures = setdiff(allFigures, originalFigures);
    if ~isempty(newFigures)
        close(newFigures);
    end
end

function snapshot = progressSnapshot(root)
    progressFolder = fullfile(root, "progress");
    if ~isfolder(progressFolder)
        snapshot = strings(0, 1);
        return
    end

    listing = dir(fullfile(progressFolder, "**", "*"));
    listing = listing(~[listing.isdir]);
    snapshot = strings(numel(listing), 1);
    for k = 1:numel(listing)
        item = listing(k);
        snapshot(k) = string(item.folder) + filesep + string(item.name) + ":" + string(item.datenum) + ":" + string(item.bytes);
    end
    snapshot = sort(snapshot);
end

function writeText(path, text)
    fileId = fopen(path, "w");
    require(fileId ~= -1, "unable to write temporary progress fixture");
    cleanup = onCleanup(@() fclose(fileId));
    fwrite(fileId, text, "char");
    clear cleanup
end

function removeFolder(folder)
    if isfolder(folder)
        rmdir(folder, "s");
    end
end

function text = matlabString(value)
    text = """" + replace(string(value), """", """""") + """";
end

function out = rel(path, root)
    out = replace(string(path), string(root) + filesep, "");
    out = replace(out, "\", "/");
end

function require(condition, message)
    if ~condition
        error("InteractiveMissions:RuntimeValidationFailed", "%s", message);
    end
end
