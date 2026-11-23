function root = workspaceBaseRoot(path)
%WORKSPACEBASEROOT Normalize a stored workspace value into a launch base.

    defaultRoot = interactiveMissions.internal.defaultSafeRoot();
    root = string(path);
    if strlength(strtrim(root)) == 0
        root = defaultRoot;
        return
    end

    root = replace(root, "/", filesep);
    if isTemporaryPath(root) || isOldDefaultRoot(root)
        root = defaultRoot;
        return
    end

    [parentFolder, folderName] = fileparts(root);
    if isPreparedWorkspace(root) || isGeneratedWorkspaceName(folderName)
        if isTemporaryPath(parentFolder)
            root = defaultRoot;
        else
            root = string(parentFolder);
        end
    end
end

function result = isTemporaryPath(path)
    tempRoot = replace(string(tempdir()), "/", filesep);
    result = startsWith(lower(string(path)), lower(tempRoot));
end

function result = isGeneratedWorkspaceName(folderName)
    result = ~isempty(regexp(string(folderName), "^[a-z0-9]+(?:-[a-z0-9]+)*_\d+$", "once"));
end

function result = isPreparedWorkspace(path)
    result = isfile(fullfile(string(path), ".interactive-missions", "manifest.json"));
end

function result = isOldDefaultRoot(path)
    path = lower(replace(string(path), "/", filesep));
    oldLeaf = lower(fullfile("Documents", "InteractiveMissionsWorkspace"));
    previousLeaf = lower(fullfile("Documents", "MATLAB", "interactive-mission"));
    result = endsWith(path, oldLeaf) || endsWith(path, previousLeaf);
end
