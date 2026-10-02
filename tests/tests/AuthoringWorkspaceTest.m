classdef AuthoringWorkspaceTest < matlab.unittest.TestCase
    %AUTHORINGWORKSPACETEST Verify authoring workspace initialization.

    properties (TestParameter)
        Root = {interactiveMissionsSmoke.defaultRoot()}
        AgentClient = {"codex", "claude-code", "gemini-cli", ...
            "github-copilot-vscode", "github-copilot-cli", "generic"}
    end

    methods (Test)
        function initializesAuthoringWorkspace(testCase, Root, AgentClient)
            root = string(Root);
            addSourceFolder(testCase, root);
            workspaceRoot = createEmptyFolder(testCase);

            info = interactiveMissions.startMissionAuthoring( ...
                WorkspaceRoot=workspaceRoot, ...
                AgentClient=AgentClient, ...
                CreateFirstMission="no");

            manifestText = fileread(info.ManifestPath);
            testCase.verifyEqual(info.AgentClient, AgentClient);
            testCase.verifyTrue(isfolder(info.MarketplaceRoot));
            testCase.verifyTrue(isfolder(info.SkillRoot));
            testCase.verifyFalse(isfile(fullfile(info.DocumentationRoot, "mission-contract.md")));
            testCase.verifyTrue(isfile(fullfile(info.SkillRoot, "references", "mission-contract.md")));
            testCase.verifyTrue(isfile(fullfile(info.SkillRoot, "create-tutor-mission", "SKILL.md")));
            verifyAdapterFiles(testCase, workspaceRoot, AgentClient);
            testCase.verifyTrue(contains(manifestText, "source_url: ''"));
            testCase.verifyTrue(contains(manifestText, "missions: []"));
        end

        function createsFirstMissionBrief(testCase, Root)
            root = string(Root);
            addSourceFolder(testCase, root);
            workspaceRoot = createEmptyFolder(testCase);

            info = interactiveMissions.startMissionAuthoring( ...
                WorkspaceRoot=workspaceRoot, ...
                AgentClient="generic", ...
                CreateFirstMission="yes", ...
                MissionTitle="Sample Time Basics", ...
                MissionId="sample-time-basics");

            briefText = fileread(info.MissionBriefPath);
            testCase.verifyTrue(isfolder(info.MissionRoot));
            testCase.verifyTrue(isfile(info.MissionBriefPath));
            testCase.verifyTrue(contains(briefText, "Sample Time Basics"));
            testCase.verifyTrue(contains(briefText, "sample-time-basics"));
            testCase.verifyFalse(isfile(fullfile(info.MissionRoot, "mission.yaml")));
        end

        function shortWrapperInitializesWorkspace(testCase, Root)
            root = string(Root);
            addSourceFolder(testCase, root);
            workspaceRoot = createEmptyFolder(testCase);

            info = startMissionAuthoring( ...
                WorkspaceRoot=workspaceRoot, ...
                AgentClient="generic", ...
                CreateFirstMission="no");

            testCase.verifyEqual(info.WorkspaceRoot, workspaceRoot);
            testCase.verifyTrue(isfile(fullfile(workspaceRoot, "START_AUTHORING.md")));
        end

        function rejectsNonemptyWorkspace(testCase, Root)
            root = string(Root);
            addSourceFolder(testCase, root);
            workspaceRoot = createEmptyFolder(testCase);
            writeText(fullfile(workspaceRoot, "existing.txt"), "existing");

            testCase.verifyError(@() interactiveMissions.startMissionAuthoring( ...
                WorkspaceRoot=workspaceRoot, ...
                AgentClient="generic", ...
                CreateFirstMission="no"), "InteractiveMissions:WorkspaceNotEmpty");
        end

        function rejectsUnsupportedAgent(testCase, Root)
            root = string(Root);
            addSourceFolder(testCase, root);
            workspaceRoot = createEmptyFolder(testCase);

            testCase.verifyError(@() interactiveMissions.startMissionAuthoring( ...
                WorkspaceRoot=workspaceRoot, ...
                AgentClient="unsupported-agent", ...
                CreateFirstMission="no"), "InteractiveMissions:UnsupportedAgentClient");
        end
    end
end

function addSourceFolder(testCase, root)
    originalPath = path();
    testCase.addTeardown(@path, originalPath);
    addpath(fullfile(root, "src"));
end

function workspaceRoot = createEmptyFolder(testCase)
    workspaceRoot = string(tempname);
    mkdir(workspaceRoot);
    testCase.addTeardown(@removeFolder, workspaceRoot);
end

function verifyAdapterFiles(testCase, workspaceRoot, agentClient)
    paths = expectedAdapterFiles(workspaceRoot, agentClient);
    for pathIndex = 1:numel(paths)
        path = paths(pathIndex);
        testCase.verifyTrue(isfile(path), "missing author adapter file: " + path);
    end
end

function paths = expectedAdapterFiles(workspaceRoot, agentClient)
    switch agentClient
        case "codex"
            paths = [
                fullfile(workspaceRoot, "AGENTS.md")
                fullfile(workspaceRoot, ".codex", "skills", "create-tutor-mission", "SKILL.md")
                fullfile(workspaceRoot, ".codex", "skills", "qa-mission", "SKILL.md")
                fullfile(workspaceRoot, ".codex", "skills", "maintain-missions", "SKILL.md")
                fullfile(workspaceRoot, ".codex", "skills", "references", "mission-contract.md")
                ];
        case "claude-code"
            paths = [
                fullfile(workspaceRoot, "CLAUDE.md")
                fullfile(workspaceRoot, ".claude", "commands", "create-tutor-mission.md")
                fullfile(workspaceRoot, ".claude", "commands", "qa-mission.md")
                fullfile(workspaceRoot, ".claude", "commands", "maintain-missions.md")
                ];
        case "gemini-cli"
            paths = fullfile(workspaceRoot, "GEMINI.md");
        case "github-copilot-vscode"
            paths = [
                fullfile(workspaceRoot, ".github", "copilot-instructions.md")
                fullfile(workspaceRoot, ".github", "prompts", "create-tutor-mission.prompt.md")
                fullfile(workspaceRoot, ".github", "prompts", "qa-mission.prompt.md")
                fullfile(workspaceRoot, ".github", "prompts", "maintain-missions.prompt.md")
                ];
        case "github-copilot-cli"
            paths = fullfile(workspaceRoot, "COPILOT.md");
        case "generic"
            paths = [
                fullfile(workspaceRoot, "AGENTS.md")
                fullfile(workspaceRoot, "START_AUTHORING.md")
                ];
        otherwise
            error("InteractiveMissions:UnsupportedAgentClient", ...
                "Unsupported agent client '%s'.", agentClient);
    end
end

function writeText(path, text)
    fileIdentifier = fopen(path, "w");
    cleanup = onCleanup(@() fclose(fileIdentifier));
    fprintf(fileIdentifier, "%s", text);
    clear cleanup
end

function removeFolder(folder)
    if isfolder(folder)
        rmdir(folder, "s");
    end
end
