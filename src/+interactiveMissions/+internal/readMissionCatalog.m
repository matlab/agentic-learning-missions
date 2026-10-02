function missions = readMissionCatalog(contentRoot, options)
%READMISSIONCATALOG Read mission metadata from packaged mission YAML files.

    arguments
        contentRoot (1, 1) string
        options.SourceType (1, 1) string = "packaged"
        options.Recursive (1, 1) logical = false
    end

    if strlength(strtrim(contentRoot)) == 0
        missions = emptyCatalog();
        return
    end

    marketplaceRoot = "";
    if isfile(fullfile(contentRoot, "manifest.yaml"))
        marketplaceRoot = contentRoot;
        files = dir(fullfile(contentRoot, "missions", "*", "mission.yaml"));
    elseif isfile(fullfile(fileparts(contentRoot), "manifest.yaml"))
        marketplaceRoot = string(fileparts(contentRoot));
        files = dir(fullfile(contentRoot, "*", "mission.yaml"));
    elseif options.Recursive
        files = dir(fullfile(contentRoot, "**", "*.yaml"));
    else
        files = dir(fullfile(contentRoot, "*.yaml"));
    end
    filenames = string({files.name});
    files = files(~startsWith(filenames, "draft_"));

    missions = emptyCatalog();
    for fileIndex = 1:numel(files)
        missionPath = fullfile(files(fileIndex).folder, files(fileIndex).name);
        sourceRoot = string(files(fileIndex).folder);
        if strlength(marketplaceRoot) == 0 && ~options.Recursive
            sourceRoot = contentRoot;
        end
        missions = [missions; readMission(missionPath, options.SourceType, sourceRoot, marketplaceRoot)]; %#ok<AGROW>
    end

    if ~isempty(missions)
        [~, order] = sortrows(missions, ["TileOrder", "Title"]);
        missions = missions(order, :);
    end
end

function catalog = emptyCatalog()
    catalog = table( ...
        strings(0, 1), strings(0, 1), strings(0, 1), strings(0, 1), ...
        strings(0, 1), strings(0, 1), strings(0, 1), zeros(0, 1), ...
        cell(0, 1), cell(0, 1), strings(0, 1), false(0, 1), zeros(0, 1), ...
        zeros(0, 1), false(0, 1), false(0, 1), strings(0, 1), ...
        strings(0, 1), strings(0, 1), strings(0, 1), strings(0, 1), ...
        strings(0, 1), strings(0, 1), strings(0, 1), cell(0, 1), ...
        cell(0, 1), cell(0, 1), strings(0, 1), strings(0, 1), ...
        VariableNames=["MissionName", "MissionId", "LegacyId", "Title", ...
        "Objective", "Thumbnail", "Summary", "EstimatedMinutes", "Products", ...
        "Topics", "Status", "LearnerVisible", "TileOrder", "TaskCount", ...
        "HasSetup", "AllowAgentEdits", "Path", "SourceType", "SourceRoot", ...
        "MarketplaceSource", "MissionVersion", "MissionPackageRoot", ...
        "MarketplaceTitle", "MarketplaceContentVersion", "TaskIds", ...
        "SupportedMatlabReleases", ...
        "RequiredCapabilities", "WriteMode", "CapabilityMode"]);
end

function mission = readMission(missionPath, sourceType, sourceRoot, marketplaceRoot)
    text = string(fileread(missionPath));
    lines = splitlines(text);
    [~, missionName] = fileparts(missionPath);
    if missionName == "mission"
        [~, missionName] = fileparts(fileparts(missionPath));
    end
    appBlock = topBlock(lines, "app");
    marketplaceSource = sourceType;
    marketplaceTitle = sourceType;
    marketplaceContentVersion = "";
    if strlength(marketplaceRoot) > 0
        marketplaceSource = scalarFromManifest(marketplaceRoot, "id", sourceType);
        marketplaceTitle = scalarFromManifest(marketplaceRoot, "title", marketplaceSource);
        marketplaceContentVersion = scalarFromManifest(marketplaceRoot, "content_version", "");
    end

    objective = topScalar(lines, "objective");
    thumbnail = topScalar(lines, "thumbnail");

    mission = table( ...
        string(missionName), ...
        string(missionName), ...
        topScalar(lines, "mission_id"), ...
        topScalar(lines, "title"), ...
        objective, ...
        resolveMissionPath(missionPath, thumbnail), ...
        blockScalar(appBlock, "summary", firstSentence(objective)), ...
        str2double(blockScalar(appBlock, "estimated_minutes", "NaN")), ...
        {blockList(appBlock, "products")}, ...
        {blockList(appBlock, "topics")}, ...
        blockScalar(appBlock, "status", "published"), ...
        parseLogical(blockScalar(appBlock, "learner_visible", "true")), ...
        str2double(blockScalar(appBlock, "tile_order", "NaN")), ...
        countTasks(text), ...
        ~isempty(topBlock(lines, "setup")), ...
        parseLogical(topScalar(lines, "allow_agent_edits")), ...
        string(missionPath), ...
        string(sourceType), ...
        string(sourceRoot), ...
        string(marketplaceSource), ...
        missionVersion(lines), ...
        string(sourceRoot), ...
        string(marketplaceTitle), ...
        string(marketplaceContentVersion), ...
        {taskIds(text)}, ...
        {topList(lines, "supported_matlab_releases")}, ...
        {requiredCapabilities(lines, appBlock)}, ...
        topScalarWithFallback(lines, "write_mode", "read_inspect"), ...
        topScalarWithFallback(lines, "capability_mode", "guided_tutor"), ...
        VariableNames=emptyCatalog().Properties.VariableNames);
end

function value = missionVersion(lines)
    value = topScalar(lines, "version");
    if strlength(strtrim(value)) == 0
        value = "1.0.0";
    end
end

function value = topScalarWithFallback(lines, key, fallback)
    value = topScalar(lines, key);
    if strlength(strtrim(value)) == 0
        value = string(fallback);
    end
end

function values = topList(lines, key)
    rawValue = strtrim(topScalar(lines, key));
    values = parseInlineList(rawValue);
end

function values = requiredCapabilities(lines, appBlock)
    values = topList(lines, "required_capabilities");
    if isempty(values)
        values = blockList(appBlock, "required_capabilities");
    end
end

function value = topScalar(lines, key)
    pattern = "^" + key + ":\s*(.*)$";
    matchIndex = find(~cellfun(@isempty, regexp(cellstr(lines), pattern, "once")), 1);
    if isempty(matchIndex)
        value = "";
        return
    end

    tokens = regexp(lines(matchIndex), pattern, "tokens", "once");
    value = parseBlockAwareScalar(lines, matchIndex, string(tokens{1}));
end

function value = blockScalar(lines, key, fallback)
    value = string(fallback);
    if isempty(lines)
        return
    end

    pattern = "^\s+" + key + ":\s*(.*)$";
    matchIndex = find(~cellfun(@isempty, regexp(cellstr(lines), pattern, "once")), 1);
    if isempty(matchIndex)
        return
    end

    tokens = regexp(lines(matchIndex), pattern, "tokens", "once");
    value = parseBlockAwareScalar(lines, matchIndex, string(tokens{1}));
end

function values = blockList(lines, key)
    rawValue = strtrim(blockScalar(lines, key, ""));
    values = parseInlineList(rawValue);
end

function values = parseInlineList(rawValue)
    if strlength(rawValue) == 0
        values = strings(0, 1);
        return
    end
    if ~(startsWith(rawValue, "[") && endsWith(rawValue, "]"))
        values = rawValue;
        return
    end

    innerValue = extractBetween(rawValue, 2, strlength(rawValue) - 1);
    if strlength(strtrim(innerValue)) == 0
        values = strings(0, 1);
        return
    end

    parts = strtrim(split(innerValue, ","));
    values = strings(numel(parts), 1);
    for partIndex = 1:numel(parts)
        values(partIndex) = parseScalar(parts(partIndex));
    end
end

function block = topBlock(lines, key)
    pattern = "^" + key + ":\s*$";
    startIndex = find(~cellfun(@isempty, regexp(cellstr(lines), pattern, "once")), 1);
    if isempty(startIndex)
        block = strings(0, 1);
        return
    end

    blockEnd = numel(lines);
    for lineIndex = startIndex + 1:numel(lines)
        line = lines(lineIndex);
        if strlength(strtrim(line)) == 0 || startsWith(strtrim(line), "#")
            continue
        end
        if indentOf(line) == 0
            blockEnd = lineIndex - 1;
            break
        end
    end
    block = lines(startIndex + 1:blockEnd);
end

function value = parseBlockAwareScalar(lines, keyIndex, valueText)
    if strtrim(valueText) == ">"
        value = foldedBlock(lines, keyIndex);
    else
        value = parseScalar(valueText);
    end
end

function value = foldedBlock(lines, keyIndex)
    keyIndent = indentOf(lines(keyIndex));
    parts = strings(numel(lines) - keyIndex, 1);
    partCount = 0;
    for lineIndex = keyIndex + 1:numel(lines)
        line = lines(lineIndex);
        if strlength(strtrim(line)) == 0
            continue
        end
        if indentOf(line) <= keyIndent
            break
        end
        partCount = partCount + 1;
        parts(partCount) = strtrim(line);
    end
    value = strtrim(strjoin(parts(1:partCount), " "));
end

function value = parseScalar(rawValue)
    value = strtrim(string(rawValue));
    if (startsWith(value, '"') && endsWith(value, '"')) || ...
            (startsWith(value, "'") && endsWith(value, "'"))
        value = extractBetween(value, 2, strlength(value) - 1);
    end
end

function result = parseLogical(value)
    value = lower(strtrim(string(value)));
    result = any(value == ["true", "1", "yes", "on"]);
end

function count = countTasks(text)
    tokens = regexp(text, '(?m)^\s+- id:\s*"?t\d{2}"?', "match");
    count = numel(tokens);
end

function ids = taskIds(text)
    tokens = regexp(text, '(?m)^\s+- id:\s*"?(t\d{2})"?', "tokens");
    ids = strings(numel(tokens), 1);
    for tokenIndex = 1:numel(tokens)
        ids(tokenIndex) = string(tokens{tokenIndex}{1});
    end
end

function value = firstSentence(text)
    text = strtrim(string(text));
    if strlength(text) == 0
        value = "";
        return
    end

    tokens = regexp(text, "^(.+?[.!?])(?:\s|$)", "tokens", "once");
    if isempty(tokens)
        value = text;
    else
        value = string(tokens{1});
    end
end

function path = resolveMissionPath(missionPath, relativePath)
    path = string(relativePath);
    if strlength(strtrim(path)) == 0
        return
    end
    if isempty(regexp(path, "^[A-Za-z]:[\\/]", "once")) && ~startsWith(path, filesep)
        missionFolder = string(fileparts(missionPath));
        candidatePath = fullfile(missionFolder, path);
        if isfile(candidatePath)
            path = candidatePath;
            return
        end
        marketplaceFolder = string(fileparts(fileparts(missionFolder)));
        candidatePath = fullfile(marketplaceFolder, path);
        if isfile(candidatePath)
            path = candidatePath;
            return
        end
        path = fullfile(missionFolder, path);
    end
end

function value = scalarFromManifest(marketplaceRoot, key, fallback)
    value = string(fallback);
    manifestPath = fullfile(marketplaceRoot, "manifest.yaml");
    if ~isfile(manifestPath)
        return
    end

    lines = splitlines(string(fileread(manifestPath)));
    manifestValue = topScalar(lines, key);
    if strlength(strtrim(manifestValue)) > 0
        value = manifestValue;
    end
end

function indent = indentOf(line)
    token = regexp(char(line), "^(\s*)", "tokens", "once");
    if isempty(token)
        indent = 0;
    else
        indent = strlength(string(token{1}));
    end
end
