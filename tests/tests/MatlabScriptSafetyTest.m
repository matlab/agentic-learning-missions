classdef MatlabScriptSafetyTest < matlab.unittest.TestCase
    %MATLABSCRIPTSAFETYTEST Verify setup/reset scripts avoid unsafe operations.

    properties (TestParameter)
        Root = {interactiveMissionsSmoke.defaultRoot()}
    end

    methods (Test)
        function validatesSetupAndResetScripts(testCase, Root)
            root = string(Root);
            content = fullfile(root, "marketplace", "missions", "root-inports-outports");
            resetFiles = dir(fullfile(content, "task_reset_root-inports-outports", "reset_t*.m"));
            resetPaths = arrayfun(@(item) fullfile(item.folder, item.name), resetFiles, UniformOutput=false);
            scriptPaths = [{fullfile(content, "setup_root_inports_outports.m")}; resetPaths(:)];
            patterns = interactiveMissionsSmoke.forbiddenMatlabPatterns();

            testCase.assertNotEmpty(scriptPaths, "no setup/reset scripts found");
            for scriptIndex = 1:numel(scriptPaths)
                script = string(scriptPaths{scriptIndex});
                testCase.assertTrue(isfile(script), ...
                    "missing MATLAB setup/reset script: " + interactiveMissionsSmoke.relativePath(script, root));
                text = interactiveMissionsSmoke.stripMatlabComments(fileread(script));
                for patternIndex = 1:size(patterns, 1)
                    testCase.verifyEmpty(regexpi(text, patterns{patternIndex, 1}, "once"), ...
                        interactiveMissionsSmoke.relativePath(script, root) + ...
                        " contains forbidden operation: " + patterns{patternIndex, 2});
                end
            end
        end
    end
end
