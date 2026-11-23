classdef ReviewDashboardTest < matlab.unittest.TestCase
    %REVIEWDASHBOARDTEST Check the public MATLAB review-generation fallback.

    properties
        OutputRoot
    end

    methods (TestMethodSetup)
        function prepareFolder(testCase)
            root = fileparts(fileparts(fileparts(mfilename("fullpath"))));
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture( ...
                fullfile(root, "src", "author-skills", ...
                "simulate-mission-learner", "scripts")));
            folder = testCase.applyFixture( ...
                matlab.unittest.fixtures.TemporaryFolderFixture);
            testCase.OutputRoot = string(folder.Folder);
        end
    end

    methods (Test)
        function generatesDummyBundle(testCase)
            output = fullfile(testCase.OutputRoot, "review");
            fingerprint = buildReviewDashboard("", output);
            feedback = jsondecode(fileread(fullfile(output, "feedback-template.json")));
            testCase.verifyEqual(string(feedback.packet_sha256), fingerprint);
            testCase.verifyEqual(strlength(fingerprint), 64);
            testCase.verifyEqual(string({feedback.reviews.decision}), ["pending", "pending"]);
            testCase.verifyTrue(isfile(fullfile(output, "REVIEW.md")));
        end

        function singletonAndUnicodeStaySafe(testCase)
            source = fullfile(testCase.OutputRoot, "input.json");
            packet = demoPacket();
            packet.items{1}.evidence = "Δ café </script><script>window.injected=true</script>";
            writelines(string(jsonencode(packet)), source, Encoding="UTF-8");
            output = fullfile(testCase.OutputRoot, "review");
            buildReviewDashboard(source, output);
            page = string(fileread(fullfile(output, "index.html")));
            tokens = regexp(page, ...
                "<script id=""review-data"" type=""application/json"">(.*?)</script>", ...
                "tokens", "once");
            embedded = string(tokens{1});
            decoded = jsondecode(embedded);
            testCase.verifyTrue(contains(embedded, """items"":[{"));
            testCase.verifyFalse(contains(embedded, "<"));
            testCase.verifyEqual(string(decoded.items.evidence), packet.items{1}.evidence);
            testCase.verifyEqual(fileread(fullfile(output, "packet.json")), fileread(source));
        end

        function rejectsDuplicateIds(testCase)
            source = fullfile(testCase.OutputRoot, "input.json");
            packet = demoPacket();
            packet.items{2} = packet.items{1};
            writelines(string(jsonencode(packet)), source, Encoding="UTF-8");
            testCase.verifyError(@() buildReviewDashboard(source, ...
                fullfile(testCase.OutputRoot, "review")), ...
                "InteractiveMissions:InvalidReviewPacket");
        end

        function preservesExistingOutput(testCase)
            testCase.verifyError(@() buildReviewDashboard("", testCase.OutputRoot), ...
                "InteractiveMissions:ReviewOutputExists");
        end
    end
end

function packet = demoPacket()
    item = struct("id", "one", "group", "Evidence", "title", "Outcome", ...
        "question", "Is it supported?", "evidence", "Dummy evidence", ...
        "choices", {{"pass", "unknown"}});
    packet = struct("schema_version", "1.0", "title", "Dummy", ...
        "instructions", "Review this example.", "sources", {{"dummy"}}, ...
        "items", {{item}});
end
