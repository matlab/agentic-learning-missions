function fingerprint = buildReviewDashboard(packetPath, outputFolder)
%BUILDREVIEWDASHBOARD Generate standalone author-review files without Python.
%   Call through MATLAB MCP Server. Use an empty packetPath for the dummy
%   example. outputFolder must be a new folder. Base MATLAB with JVM is needed.

    arguments
        packetPath (1,1) string
        outputFolder (1,1) string
    end

    skillRoot = fileparts(fileparts(mfilename("fullpath")));
    page = fileread(fullfile(skillRoot, "assets", "review.html"));
    if strlength(packetPath) == 0
        [~, ~, rawText] = scriptData(page, "review-data");
        rawBytes = unicode2native(rawText, "UTF-8");
    else
        rawBytes = readBytes(packetPath);
        rawText = native2unicode(rawBytes, "UTF-8");
    end
    packet = jsondecode(rawText);
    items = validatePacket(packet);
    % Cell arrays preserve JSON arrays even when there is just one item.
    packet.items = items;
    if ~usejava("jvm")
        error("InteractiveMissions:ReviewJVMUnavailable", ...
            "SHA-256 generation needs the MATLAB JVM. Use file-based review.");
    end
    digest = java.security.MessageDigest.getInstance("SHA-256");
    digest.update(rawBytes);
    hashBytes = reshape(typecast(digest.digest(), "uint8"), 1, []);
    fingerprint = lower(join(compose("%02x", hashBytes), ""));

    rows = repmat(struct("id", "", "decision", "pending", "notes", ""), ...
        1, numel(items));
    for index = 1:numel(items)
        rows(index).id = string(items{index}.id);
    end
    feedback = struct("schema_version", "1.0", ...
        "kind", "mission-learner-review-feedback", ...
        "packet_sha256", fingerprint, "reviewer", "", ...
        "overall_notes", "", "reviews", {num2cell(rows)});
    page = embedJson(page, "review-data", packet);
    page = embedJson(page, "packet-fingerprint", fingerprint);
    guide = string(fileread(fullfile(skillRoot, "references", "human-feedback.md")));
    introduction = "# This review bundle" + newline + newline + ...
        "Open `index.html`, or review `packet.json` and edit a copy of " + ...
        "`feedback-template.json`. Return `packet.json` and the saved " + ...
        "feedback path to the agent." + newline + newline;

    if isfolder(outputFolder) || isfile(outputFolder)
        error("InteractiveMissions:ReviewOutputExists", ...
            "Use a new output folder to preserve existing reviews.");
    end
    [created, message] = mkdir(outputFolder);
    if ~created
        error("InteractiveMissions:ReviewOutputFailed", "%s", message);
    end
    writeBytes(fullfile(outputFolder, "packet.json"), rawBytes);
    writeText(fullfile(outputFolder, "index.html"), page);
    writeText(fullfile(outputFolder, "feedback-template.json"), ...
        string(jsonencode(feedback, PrettyPrint=true)) + newline);
    writeText(fullfile(outputFolder, "REVIEW.md"), introduction + guide);
    disp("Review: " + fullfile(outputFolder, "index.html"));
    disp("Packet SHA-256: " + fingerprint);
end

function items = validatePacket(packet)
    if ~isstruct(packet) || ~isscalar(packet) || ...
            ~isfield(packet, "schema_version") || ...
            ~isequal(string(packet.schema_version), "1.0")
        error("InteractiveMissions:InvalidReviewPacket", ...
            "Expected a version 1.0 review packet.");
    end
    requireText(packet, "title", false);
    requireText(packet, "instructions", false);
    if ~isfield(packet, "sources") || ~isTextArray(packet.sources)
        error("InteractiveMissions:InvalidReviewPacket", ...
            "Packet sources must be an array of strings.");
    end
    if ~isfield(packet, "items") || isempty(packet.items)
        error("InteractiveMissions:InvalidReviewPacket", ...
            "Packet must contain review items.");
    end
    if isstruct(packet.items)
        items = num2cell(packet.items);
    elseif iscell(packet.items)
        items = packet.items;
    else
        error("InteractiveMissions:InvalidReviewPacket", ...
            "Each review item must be an object.");
    end
    ids = strings(1, numel(items));
    for index = 1:numel(items)
        item = items{index};
        for field = ["id", "group", "title", "question", "evidence"]
            requireText(item, field, true);
        end
        ids(index) = string(item.id);
        if ~isfield(item, "choices") || ~isTextArray(item.choices)
            error("InteractiveMissions:InvalidReviewPacket", ...
                "Choices must be an array of strings.");
        end
        choices = string(item.choices);
        if numel(choices) < 2 || any(strlength(strip(choices)) == 0) || ...
                numel(unique(choices)) ~= numel(choices) || any(choices == "pending")
            error("InteractiveMissions:InvalidReviewPacket", ...
                "Choices need distinct nonempty decisions, excluding pending.");
        end
    end
    if numel(unique(ids)) ~= numel(ids)
        error("InteractiveMissions:InvalidReviewPacket", ...
            "Review item IDs must be unique.");
    end
end

function requireText(value, field, nonempty)
    if ~isstruct(value) || ~isscalar(value) || ~isfield(value, field) || ...
            ~ischar(value.(field)) || ...
            (nonempty && strlength(strip(string(value.(field)))) == 0)
        error("InteractiveMissions:InvalidReviewPacket", ...
            "Field %s must be text and required item text must be nonempty.", field);
    end
end

function valid = isTextArray(value)
    valid = (isnumeric(value) && isempty(value)) || ...
        (iscell(value) && all(cellfun(@ischar, value), "all"));
end

function [first, last, content] = scriptData(page, elementId)
    pattern = "<script id=""" + elementId + ...
        """ type=""application/json"">(.*?)</script>";
    [first, last, tokens] = regexp(page, pattern, "start", "end", "tokens", "once");
    if isempty(first)
        error("InteractiveMissions:InvalidReviewTemplate", ...
            "Template is missing %s.", elementId);
    end
    content = tokens{1};
end

function page = embedJson(page, elementId, value)
    [first, last] = scriptData(page, elementId);
    encoded = string(jsonencode(value));
    % Escape data characters that could close the inert script element.
    encoded = replace(encoded, ["<", ">", "&"], ["\u003c", "\u003e", "\u0026"]);
    script = "<script id=""" + elementId + ...
        """ type=""application/json"">" + encoded + "</script>";
    page = [page(1:first-1), char(script), page(last+1:end)];
end

function bytes = readBytes(filePath)
    [fileId, message] = fopen(filePath, "rb");
    if fileId < 0
        error("InteractiveMissions:ReviewReadFailed", "%s", message);
    end
    fileCleanup = onCleanup(@() fclose(fileId));
    bytes = fread(fileId, Inf, "*uint8")';
end

function writeText(filePath, text)
    writeBytes(filePath, unicode2native(char(text), "UTF-8"));
end

function writeBytes(filePath, bytes)
    [fileId, message] = fopen(filePath, "wb");
    if fileId < 0
        error("InteractiveMissions:ReviewWriteFailed", "%s", message);
    end
    fileCleanup = onCleanup(@() fclose(fileId));
    count = fwrite(fileId, bytes, "uint8");
    if count ~= numel(bytes)
        error("InteractiveMissions:ReviewWriteFailed", ...
            "Could not write the complete review file.");
    end
end
