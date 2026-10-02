function missions = catalog(options)
%CATALOG Return Interactive Missions catalog entries.

    arguments
        options.ContentRoot (1, 1) string = ""
        options.MarketplaceRoot (1, 1) string = ""
        options.Audience (1, 1) string {mustBeMember(options.Audience, ["learner", "author", "all"])} = "all"
    end

    if strlength(strtrim(options.ContentRoot)) > 0
        missions = interactiveMissions.internal.readMissionCatalog(options.ContentRoot, SourceType="marketplace");
    elseif strlength(strtrim(options.MarketplaceRoot)) > 0
        missions = interactiveMissions.internal.readMissionCatalog(options.MarketplaceRoot, SourceType="marketplace");
    else
        marketplaceRoots = cachedMarketplaceRoots();
        missions = interactiveMissions.internal.readMissionCatalog("", SourceType="marketplace");
        for rootIndex = 1:numel(marketplaceRoots)
            marketplaceMissions = interactiveMissions.internal.readMissionCatalog( ...
                marketplaceRoots(rootIndex), SourceType="marketplace");
            missions = [missions; marketplaceMissions]; %#ok<AGROW>
        end
    end

    if options.Audience == "learner" && ~isempty(missions)
        missions = missions(missions.LearnerVisible, :);
    end

    if ~isempty(missions)
        [~, order] = sortrows(missions, ["MarketplaceSource", "TileOrder", "Title"]);
        missions = missions(order, :);
    end
end

function roots = cachedMarketplaceRoots()
    records = interactiveMissions.internal.marketplaceRegistry("get");
    cacheBase = fullfile(prefdir(), "InteractiveMissions", "marketplaces") + filesep;
    roots = strings(0, 1);
    for recordIndex = 1:numel(records)
        cacheRoot = string(records(recordIndex).CacheRoot);
        if startsWith(lower(cacheRoot), lower(cacheBase)) && isfolder(cacheRoot)
            try
                roots(end + 1, 1) = marketplaceContentRoot(cacheRoot); %#ok<AGROW>
            catch exception
                warning("InteractiveMissions:InvalidMarketplaceCache", "%s", exception.message);
            end
        end
    end
    roots = unique(roots, "stable");
end

function contentRoot = marketplaceContentRoot(cacheRoot)
    cacheRoot = string(cacheRoot);
    if isfile(fullfile(cacheRoot, "manifest.yaml"))
        contentRoot = cacheRoot;
        return
    end

    contentRoot = fullfile(cacheRoot, "marketplace");
    if ~isfile(fullfile(contentRoot, "manifest.yaml"))
        error("InteractiveMissions:InvalidMarketplaceCache", ...
            "Marketplace cache does not contain manifest.yaml: %s", cacheRoot);
    end
end
