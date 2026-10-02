function records = marketplaceRegistry(action, options)
%MARKETPLACEREGISTRY Read or atomically write installed marketplace records.

    arguments
        action (1, 1) string {mustBeMember(action, ["get", "set"])}
        options.Records (:, 1) struct = struct([])
    end

    recordsPath = fullfile(prefdir(), "InteractiveMissions", "app", "installed_marketplaces.json");
    switch action
        case "get"
            records = readRecords(recordsPath);
        case "set"
            records = normalizeRecords(options.Records);
            recordsFolder = fileparts(recordsPath);
            if ~isfolder(recordsFolder)
                mkdir(recordsFolder);
            end
            writeRecordsAtomically(recordsPath, records);
    end
end

function records = readRecords(recordsPath)
    records = struct([]);
    if ~isfile(recordsPath)
        return
    end

    try
        decoded = jsondecode(fileread(recordsPath));
        if isfield(decoded, "Marketplaces")
            records = normalizeRecords(decoded.Marketplaces(:));
        end
    catch exception
        warning("InteractiveMissions:MarketplaceRegistryReadFailed", ...
            "Could not read %s: %s", recordsPath, exception.message);
    end
end

function records = normalizeRecords(records)
    template = emptyRecord();
    if isempty(records)
        records = repmat(template, 0, 1);
        return
    end

    normalized = repmat(template, numel(records), 1);
    fields = string(fieldnames(template));
    for recordIndex = 1:numel(records)
        for fieldIndex = 1:numel(fields)
            fieldName = fields(fieldIndex);
            if isfield(records(recordIndex), fieldName)
                if fieldName == "IsDefault"
                    normalized(recordIndex).(fieldName) = logical(records(recordIndex).(fieldName));
                else
                    normalized(recordIndex).(fieldName) = string(records(recordIndex).(fieldName));
                end
            end
        end
    end
    records = normalized;
end

function record = emptyRecord()
    record = struct( ...
        "Id", "", ...
        "Title", "", ...
        "SourceUrl", "", ...
        "RemoteUrl", "", ...
        "ContentVersion", "", ...
        "MinimumToolboxVersion", "", ...
        "CacheRoot", "", ...
        "UpdateStatus", "", ...
        "UpdateMessage", "", ...
        "ReferenceType", "default", ...
        "ReferenceName", "", ...
        "IsDefault", false, ...
        "ResolvedRevision", "", ...
        "RemoteRevision", "", ...
        "LastAttemptAt", "", ...
        "LastSuccessAt", "", ...
        "LastRefreshedAt", "", ...
        "LastUpdateCheckAt", "" ...
        );
end

function writeRecordsAtomically(path, records)
    temporaryPath = path + "." + string(matlabProcessID()) + ".tmp";
    writeText(temporaryPath, jsonencode(struct("Marketplaces", records)));
    [isMoved, message] = movefile(temporaryPath, path, "f");
    if ~isMoved
        if isfile(temporaryPath)
            delete(temporaryPath);
        end
        error("InteractiveMissions:MarketplaceRegistryWriteFailed", ...
            "Could not update %s: %s", path, message);
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
