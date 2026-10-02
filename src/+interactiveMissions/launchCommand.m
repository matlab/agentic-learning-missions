function command = launchCommand(options)
%LAUNCHCOMMAND Build a vendor-neutral terminal launch command.

    arguments
        options.MissionName (1, 1) string = "root-inports-outports"
        options.SafeRoot (1, 1) string = ""
        options.ManifestPath (1, 1) string = ""
        options.Agent (1, 1) string = "generic"
        options.Shell (1, 1) string {mustBeMember(options.Shell, ["powershell", "cmd", "plain"])} = "powershell"
    end

    safeRoot = string(options.SafeRoot);
    if strlength(strtrim(safeRoot)) == 0
        safeRoot = interactiveMissions.internal.nextWorkspaceRoot(options.MissionName);
    end
    agent = normalizeAgent(options.Agent);
    switch options.Shell
        case "powershell"
            command = workspaceCommand(agent, safeRoot, false);
        case "cmd"
            command = workspaceCommand(agent, safeRoot, true);
        case "plain"
            command = workspaceCommand(agent, safeRoot, false);
        otherwise
            error("InteractiveMissions:UnsupportedShell", "Unsupported shell '%s'.", options.Shell);
    end
end

function command = workspaceCommand(agent, safeRoot, isCmd)
    if agent == "copilot"
        command = "code " + quoteUserPath(safeRoot);
    elseif isCmd
        command = "cd /d " + quoteUserPath(safeRoot);
    else
        command = "cd " + quoteUserPath(safeRoot);
    end
end

function agent = normalizeAgent(agent)
    agent = lower(strtrim(string(agent)));
    agent = regexprep(agent, "[^a-z0-9]+", "-");
    switch agent
        case {"codex", "openai-codex"}
            agent = "codex";
        case {"claude", "claude-code"}
            agent = "claude";
        case {"gemini", "gemini-cli"}
            agent = "gemini";
        case {"copilot", "github-copilot", "github-copilot-vs-code"}
            agent = "copilot";
        otherwise
            agent = "generic";
    end
end

function value = quoteUserPath(value)
    value = string(value);
    value = """" + replace(value, """", """""") + """";
end
