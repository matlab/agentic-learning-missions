function root = defaultRoot()
%DEFAULTROOT Find the Interactive Missions repository root from the current folder.

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
