function results = validate_framework(root)
%VALIDATE_FRAMEWORK Run toolbox-first smoke tests for Interactive Missions.
%   VALIDATE_FRAMEWORK validates the repository containing the current folder.
%   VALIDATE_FRAMEWORK(ROOT) validates the repository at ROOT.

    if nargin < 1 || strlength(string(root)) == 0
        root = defaultRoot();
    end

    root = string(root);
    originalPath = path();
    cleanup = onCleanup(@() path(originalPath));
    addpath(fullfile(root, "tests"));
    addpath(fullfile(root, "src"));

    suite = testsuite(fullfile(root, "tests", "tests"));
    results = run(suite);
    disp(table(results))

    if any([results.Failed])
        error("InteractiveMissions:SmokeTestsFailed", "Framework smoke tests failed.");
    end

    fprintf("\nAll static smoke tests passed.\n");
    clear cleanup
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
