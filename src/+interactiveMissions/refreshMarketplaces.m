function records = refreshMarketplaces(options)
%REFRESHMARKETPLACES Refresh one or all registered marketplaces safely.

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
        record = records(recordIndex);
        record.LastAttemptAt = timestampNow();
        try
            interactiveMissions.registerMarketplace(SourceUrl=record.RemoteUrl, ...
                ReferenceType=referenceType(record), ReferenceName=referenceName(record), ...
                ReplaceExisting=true, IsDefault=isDefault(record));
            records = interactiveMissions.internal.marketplaceRegistry("get");
        catch exception
            records(recordIndex).UpdateStatus = statusAfterFailure(records(recordIndex));
            records(recordIndex).UpdateMessage = string(exception.message);
            records(recordIndex).LastAttemptAt = timestampNow();
            interactiveMissions.internal.marketplaceRegistry("set", Records=records);
        end
    end
    records = interactiveMissions.internal.marketplaceRegistry("get");
end

function value = referenceType(record)
    value = "default";
    if isfield(record, "ReferenceType") && strlength(record.ReferenceType) > 0
        value = record.ReferenceType;
    end
end

function value = referenceName(record)
    value = "";
    if isfield(record, "ReferenceName")
        value = record.ReferenceName;
    end
end

function value = isDefault(record)
    value = isfield(record, "IsDefault") && logical(record.IsDefault);
end

function status = statusAfterFailure(record)
    if isfolder(record.CacheRoot)
        status = "stale";
    else
        status = "unavailable";
    end
end

function text = timestampNow()
    text = string(datetime("now", "TimeZone", "local", "Format", "yyyy-MM-dd'T'HH:mm:ssXXX"));
end
