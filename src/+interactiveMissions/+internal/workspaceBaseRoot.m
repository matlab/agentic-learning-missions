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
    result = interactiveMissions.internal.isPathWithin(path, tempRoot);
end

function result = isGeneratedWorkspaceName(folderName)
    result = ~isempty(regexp(string(folderName), "^[a-z0-9]+(?:-[a-z0-9]+)*_\d+$", "once"));
end

function result = isPreparedWorkspace(path)
    result = isfile(fullfile(string(path), ".interactive-missions", "manifest.json"));
end

function result = isOldDefaultRoot(path)
    path = replace(string(path), "/", filesep);
    oldLeaf = fullfile("Documents", "InteractiveMissionsWorkspace");
    previousLeaf = fullfile("Documents", "MATLAB", "interactive-mission");
    if ispc
        path = lower(path);
        oldLeaf = lower(oldLeaf);
        previousLeaf = lower(previousLeaf);
    end
    result = endsWith(path, oldLeaf) || endsWith(path, previousLeaf);
end
