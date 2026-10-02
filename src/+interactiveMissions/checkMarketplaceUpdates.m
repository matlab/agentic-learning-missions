function records = checkMarketplaceUpdates(options)
%CHECKMARKETPLACEUPDATES Check registered marketplace revisions without downloading content.

    arguments
        options.MarketplaceId (1, 1) string = ""
    end

    records = interactiveMissions.internal.marketplaceRegistry("get");
    requestedId = strtrim(options.MarketplaceId);
    selected = true(numel(records), 1);
    if strlength(requestedId) > 0
        selected = strcmpi(string({records.Id}), requestedId);
        if ~any(selected)
            error("InteractiveMissions:MarketplaceNotRegistered", "Marketplace ID '%s' is not registered.", requestedId);
        end
    end

    for recordIndex = find(selected).'
        records(recordIndex) = checkRecord(records(recordIndex));
    end
    interactiveMissions.internal.marketplaceRegistry("set", Records=records);
end

function record = checkRecord(record)
    record.LastUpdateCheckAt = timestampNow();
    try
        remoteRevision = remoteRevisionFor(record);
        record.RemoteRevision = remoteRevision;
        if strcmpi(remoteRevision, record.ResolvedRevision)
            record.UpdateStatus = "current";
            record.UpdateMessage = "Cached version is current.";
        else
            record.UpdateStatus = "updateAvailable";
            record.UpdateMessage = "A newer revision is available. Refresh to download it.";
        end
    catch
        record.UpdateStatus = "unknown";
        record.UpdateMessage = "Unable to check for updates. The cached version is unchanged.";
    end
end

function revision = remoteRevisionFor(record)
    referenceType = string(record.ReferenceType);
    referenceName = string(record.ReferenceName);
    sourceUrl = string(record.RemoteUrl);

    switch referenceType
        case "default"
            output = gitOutput("ls-remote " + quoteArgument(sourceUrl) + " HEAD");
        case "branch"
            output = gitOutput("ls-remote " + quoteArgument(sourceUrl) + " " + ...
                quoteArgument("refs/heads/" + referenceName));
        case "tag"
            output = gitOutput("ls-remote " + quoteArgument(sourceUrl) + " " + ...
                quoteArgument("refs/tags/" + referenceName) + " " + ...
                quoteArgument("refs/tags/" + referenceName + "^{}"));
        otherwise
            error("InteractiveMissions:MarketplaceReferenceInvalid", ...
                "Marketplace '%s' has an unsupported reference type.", record.Id);
    end

    revisions = regexp(output, "(?m)^([0-9a-fA-F]{40})\s+", "tokens");
    if isempty(revisions)
        error("InteractiveMissions:MarketplaceReferenceNotFound", ...
            "The configured marketplace reference was not found on the remote.");
    end
    revision = string(revisions{end}{1});
end

function output = gitOutput(arguments)
    previousPrompt = getenv("GIT_TERMINAL_PROMPT");
    restorePrompt = onCleanup(@() setenv("GIT_TERMINAL_PROMPT", previousPrompt));
    setenv("GIT_TERMINAL_PROMPT", "0");
    [status, output] = system("git " + arguments);
    clear restorePrompt
    if status ~= 0
        error("InteractiveMissions:MarketplaceUpdateCheckFailed", ...
            "Git could not check the marketplace remote.");
    end
    output = strtrim(string(output));
end

function value = quoteArgument(value)
    value = string(value);
    value = """" + replace(value, """", "") + """";
end

function text = timestampNow()
    text = string(datetime("now", "TimeZone", "local", "Format", "yyyy-MM-dd'T'HH:mm:ssXXX"));
end
