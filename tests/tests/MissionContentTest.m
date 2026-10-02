classdef MissionContentTest < matlab.unittest.TestCase
    %MISSIONCONTENTTEST Verify packaged mission content contract.

    properties (TestParameter)
        Root = {interactiveMissionsSmoke.defaultRoot()}
    end

    methods (Test)
        function validatesMissionMetadata(testCase, Root)
            root = string(Root);
            missionFiles = dir(fullfile(root, "marketplace", "missions", "*", "mission.yaml"));
            testCase.assertNotEmpty(missionFiles, "marketplace must contain mission.yaml files");

            for fileIndex = 1:numel(missionFiles)
                missionPath = fullfile(missionFiles(fileIndex).folder, missionFiles(fileIndex).name);
                text = string(fileread(missionPath));
                for field = ["mission_id", "version", "title", "objective", ...
                        "supported_matlab_releases", "required_capabilities", ...
                        "write_mode", "capability_mode", "tasks"]
                    testCase.verifyNotEmpty(regexp(text, "(?m)^" + field + ":", "once"), ...
                        interactiveMissionsSmoke.relativePath(missionPath, Root) + ...
                        " missing required field: " + field);
                end
                testCase.verifyNotEmpty(regexp(text, ...
                    "(?m)^write_mode:\s*(read_inspect|allow_agent_edits)\s*$", "once"), ...
                    "mission write_mode must be a supported value");
                testCase.verifyNotEmpty(regexp(text, ...
                    "(?m)^capability_mode:\s*(guided_tutor|agent_build|review_only)\s*$", "once"), ...
                    "mission capability_mode must be a supported value");
            end

            [~, text] = missionText(Root);
            testCase.verifyNotEmpty(regexp(text, '(?m)^mission_id:\s*"01"\s*$', "once"), ...
                "root-inports-outports mission.yaml must declare its mission ID");
        end

        function validatesSetupScriptReference(testCase, Root)
            root = string(Root);
            content = fullfile(root, "marketplace", "missions", "root-inports-outports");
            [~, text] = missionText(root);

            setupScript = interactiveMissionsSmoke.scalarAfterKey(text, "script");
            testCase.verifyGreaterThan(strlength(setupScript), 0, "mission setup must reference a script");
            testCase.verifyTrue(isfile(fullfile(content, setupScript)), ...
                "setup script is missing: content/" + setupScript);
        end

        function validatesTasks(testCase, Root)
            root = string(Root);
            content = fullfile(root, "marketplace", "missions", "root-inports-outports");
            [~, text] = missionText(root);
            [taskStarts, taskEnds, taskTokens] = regexp(text, '(?m)^  - id:\s*"?(t\d{2})"?', ...
                "start", "end", "tokens");

            testCase.assertNotEmpty(taskTokens, "mission tasks must be a non-empty list");

            taskIds = string(cellfun(@(item) item{1}, taskTokens, UniformOutput=false));
            expectedIds = arrayfun(@(index) string(sprintf("t%02d", index)), 1:numel(taskIds));
            testCase.verifyEqual(taskIds(:), expectedIds(:), "task IDs must be sequential");

            for taskIndex = 1:numel(taskIds)
                taskId = taskIds(taskIndex);
                blockText = taskBlockText(text, taskStarts, taskEnds, taskIndex);
                for field = ["title", "instruction", "completion", "hints"]
                    testCase.verifyNotEmpty(regexp(blockText, "(?m)^\s{4}" + field + ":", "once"), ...
                        taskId + " missing required field: " + field);
                end
                testCase.verifyNotEmpty(regexp(blockText, "(?m)^\s{6}strategy:\s*$", "once"), ...
                    taskId + " completion.strategy must be present");
                testCase.verifyNotEmpty(regexp(blockText, "(?m)^\s{8}- (tool|kind):", "once"), ...
                    taskId + " completion.strategy must be non-empty");
            end

            resetFolder = fullfile(content, "task_reset_root-inports-outports");
            for taskIndex = 2:numel(taskIds)
                resetFile = fullfile(resetFolder, "reset_" + taskIds(taskIndex) + ".m");
                testCase.verifyTrue(isfile(resetFile), ...
                    "missing reset script: " + interactiveMissionsSmoke.relativePath(resetFile, root));
            end
        end

        function validatesMcpToolNames(testCase, Root)
            [~, text] = missionText(Root);
            allowedTools = interactiveMissionsSmoke.allowedMcpTools();
            toolNames = regexp(text, '(?m)^\s+(?:- )?tool:\s*([A-Za-z_][A-Za-z0-9_]*)', "tokens");
            toolNames = string(cellfun(@(item) item{1}, toolNames, UniformOutput=false));

            for toolName = toolNames(:)'
                testCase.verifyTrue(any(allowedTools == toolName), ...
                    "mission uses unsupported MCP tool '" + toolName + "'");
            end
        end

        function validatesCompletionKinds(testCase, Root)
            root = string(Root);
            missionFiles = dir(fullfile(root, "marketplace", "missions", "*", "mission.yaml"));

            for fileIndex = 1:numel(missionFiles)
                missionPath = fullfile(missionFiles(fileIndex).folder, missionFiles(fileIndex).name);
                text = string(fileread(missionPath));
                kindNames = regexp(text, '(?m)^\s+(?:- )?kind:\s*([A-Za-z_][A-Za-z0-9_]*)', "tokens");
                kindNames = string(cellfun(@(item) item{1}, kindNames, UniformOutput=false));
                for kindName = kindNames(:)'
                    testCase.verifyEqual(kindName, "learner_confirmation", ...
                        "mission uses unsupported completion kind '" + kindName + "'");
                end
            end
        end

        function validatesAgentEditFlagShape(testCase, Root)
            root = string(Root);
            missionFiles = dir(fullfile(root, "marketplace", "missions", "*", "mission.yaml"));
            filenames = string({missionFiles.name});
            missionFiles = missionFiles(~startsWith(filenames, "draft_"));

            for fileIndex = 1:numel(missionFiles)
                missionPath = fullfile(missionFiles(fileIndex).folder, missionFiles(fileIndex).name);
                text = string(fileread(missionPath));
                tokens = regexp(text, '(?m)^allow_agent_edits:\s*(\S+)\s*$', "tokens");
                for tokenIndex = 1:numel(tokens)
                    value = lower(string(tokens{tokenIndex}{1}));
                    testCase.verifyTrue(any(value == ["true", "false"]), ...
                        "allow_agent_edits must be an unquoted boolean in " + ...
                        interactiveMissionsSmoke.relativePath(missionPath, root));
                end
            end
        end

        function validatesOptionalThumbnailCatalog(testCase, Root)
            testCase.verifyTrue(isfolder(fullfile(Root, "src", "app", "assets", "thumbnails")), ...
                "the installed app must provide generic fallback thumbnail assets");
            temporaryRoot = string(tempname());
            mkdir(temporaryRoot);
            cleanup = onCleanup(@() rmdir(temporaryRoot, "s"));

            omittedFolder = fullfile(temporaryRoot, "omitted");
            pngFolder = fullfile(temporaryRoot, "png");
            svgFolder = fullfile(temporaryRoot, "svg");
            mkdir(omittedFolder);
            mkdir(pngFolder);
            mkdir(svgFolder);
            writelines(missionYaml("Omitted", "[MATLAB]"), fullfile(omittedFolder, "mission.yaml"));
            writelines(missionYaml("PNG", "[MATLAB]", "thumbnail: ""graphic.png"""), ...
                fullfile(pngFolder, "mission.yaml"));
            writelines(missionYaml("SVG", "[MATLAB, Simulink]", "thumbnail: ""graphic.svg"""), ...
                fullfile(svgFolder, "mission.yaml"));
            writelines("", fullfile(pngFolder, "graphic.png"));
            writelines("<svg></svg>", fullfile(svgFolder, "graphic.svg"));

            catalog = interactiveMissions.internal.readMissionCatalog(temporaryRoot, Recursive=true);

            omitted = catalog(catalog.Title == "Omitted", :);
            png = catalog(catalog.Title == "PNG", :);
            svg = catalog(catalog.Title == "SVG", :);
            testCase.verifyEqual(omitted.Thumbnail, "", ...
                "an omitted thumbnail must select the app-rendered fallback");
            testCase.verifyTrue(endsWith(png.Thumbnail, fullfile("png", "graphic.png")), ...
                "a declared PNG thumbnail must resolve to its mission file");
            testCase.verifyTrue(endsWith(svg.Thumbnail, fullfile("svg", "graphic.svg")), ...
                "a declared SVG thumbnail must resolve to its mission file");
            clear cleanup
        end
    end
end

function lines = missionYaml(title, products, thumbnail)
    arguments
        title (1, 1) string
        products (1, 1) string
        thumbnail (1, 1) string = ""
    end

    lines = [
        "version: ""1.0.0"""
        "title: """ + title + """"
        "objective: ""Thumbnail test."""
        thumbnail
        "app:"
        "  products: " + products
        ];
    lines = lines(lines ~= "");
end

function [missionPath, text] = missionText(root)
    root = string(root);
    missionPath = fullfile(root, "marketplace", "missions", "root-inports-outports", "mission.yaml");
    text = string(fileread(missionPath));
end

function blockText = taskBlockText(text, taskStarts, taskEnds, taskIndex)
    if taskIndex < numel(taskStarts)
        blockEnd = taskStarts(taskIndex + 1) - 1;
    else
        blockEnd = strlength(text);
    end

    blockText = extractBetween(text, taskEnds(taskIndex) + 1, blockEnd);
end
