function workspaceRoot = nextWorkspaceRoot(missionName, options)
%NEXTWORKSPACEROOT Return the next available mission workspace folder.

    arguments
        missionName (1, 1) string = "root-inports-outports"
        options.ParentRoot (1, 1) string = interactiveMissions.internal.defaultSafeRoot()
    end

    parentRoot = string(options.ParentRoot);
    folderPrefix = sanitizeMissionName(missionName);
    existingIndexes = zeros(0, 1);
    baseWorkspaceRoot = fullfile(parentRoot, folderPrefix);

    if ~isfolder(baseWorkspaceRoot)
        workspaceRoot = baseWorkspaceRoot;
        return
    end

    if isfolder(parentRoot)
        existingIndexes(end + 1, 1) = 1;
        listing = dir(fullfile(parentRoot, folderPrefix + "_*"));
        listing = listing([listing.isdir]);
        for itemIndex = 1:numel(listing)
            tokens = regexp(string(listing(itemIndex).name), "^" + folderPrefix + "_(\d+)$", "tokens", "once");
            if ~isempty(tokens)
                existingIndexes(end + 1, 1) = str2double(tokens{1}); %#ok<AGROW>
            end
        end
    end

    if isempty(existingIndexes)
        workspaceRoot = baseWorkspaceRoot;
    else
        existingIndexes(existingIndexes < 1) = [];
        nextIndex = max(existingIndexes) + 1;
        workspaceRoot = fullfile(parentRoot, folderPrefix + "_" + string(nextIndex));
    end
end

function missionName = sanitizeMissionName(missionName)
    missionName = lower(strtrim(string(missionName)));
    missionName = regexprep(missionName, "[^a-z0-9]+", "-");
    missionName = regexprep(missionName, "^-|-$", "");
    if strlength(missionName) == 0
        missionName = "mission";
    end
end
