function unregisterMarketplace(options)
%UNREGISTERMARKETPLACE Remove a registered marketplace and its managed cache.

    arguments
        options.MarketplaceId (1, 1) string
    end

    records = interactiveMissions.internal.marketplaceRegistry("get");
    recordIndex = find(strcmpi(string({records.Id}), strtrim(options.MarketplaceId)), 1);
    if isempty(recordIndex)
        error("InteractiveMissions:MarketplaceNotRegistered", "Marketplace ID '%s' is not registered.", options.MarketplaceId);
    end
    record = records(recordIndex);
    if isfield(record, "IsDefault") && logical(record.IsDefault)
        error("InteractiveMissions:DefaultMarketplaceProtected", ...
            "The default marketplace is required and cannot be unregistered.");
    end
    cacheBase = string(fullfile(prefdir(), "InteractiveMissions", "marketplaces")) + filesep;
    cacheRoot = string(record.CacheRoot);
    if strlength(cacheRoot) > 0 && startsWith(lower(cacheRoot), lower(cacheBase)) && isfolder(cacheRoot)
        rmdir(fileparts(cacheRoot), "s");
    end
    records(recordIndex) = [];
    interactiveMissions.internal.marketplaceRegistry("set", Records=records);
end
