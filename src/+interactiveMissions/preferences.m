function value = preferences(action, options)
%PREFERENCES Read or update Interactive Missions toolbox preferences.

    arguments
        action (1, 1) string {mustBeMember(action, ["get", "set"])}
        options.Settings (1, 1) struct = struct()
    end

    settingsPath = preferencesPath();
    switch action
        case "get"
            value = defaultPreferences();
            if isfile(settingsPath)
                try
                    decoded = jsondecode(fileread(settingsPath));
                    value = mergeStructs(value, decoded);
                    value = purgeLegacyPreferences(value);
                catch exception
                    warning("InteractiveMissions:PreferencesReadFailed", ...
                        "Could not read %s: %s", settingsPath, exception.message);
                end
            end
        case "set"
            value = mergeStructs(interactiveMissions.preferences("get"), options.Settings);
            value = purgeLegacyPreferences(value);
            parentFolder = fileparts(settingsPath);
            if ~isfolder(parentFolder)
                mkdir(parentFolder);
            end
            writeText(settingsPath, jsonencode(value));
    end
end

function path = preferencesPath()
    path = fullfile(prefdir(), "InteractiveMissions", "settings.json");
end

function settings = defaultPreferences()
    settings = struct();
    settings.LastWorkspace = "";
    settings.RecentWorkspaces = cell(0, 1);
    settings.LastMission = "";
    settings.AuthorWorkspace = "";
    settings.TrackedSessions = struct([]);
    settings.ActiveWorkspaces = cell(0, 1);
end

function result = mergeStructs(result, updates)
    if ~isstruct(updates)
        return
    end

    names = string(fieldnames(updates));
    for name = names(:)'
        result.(name) = updates.(name);
    end
end

function settings = purgeLegacyPreferences(settings)
    if isfield(settings, "LastProfile")
        settings = rmfield(settings, "LastProfile");
    end
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
