function clearMissionCache(options)
%CLEARMISSIONCACHE Clear the marketplace cache containing one mission.

    arguments
        options.MissionPath (1, 1) string
        options.SourceRoot (1, 1) string
    end

    sourceRoot = string(options.SourceRoot);
    missionPath = string(options.MissionPath);
    cacheRoot = fullfile(prefdir(), "InteractiveMissions", "marketplaces");
    marketplaceRoot = fileparts(fileparts(sourceRoot));

    if ~isfile(missionPath) || ~isfolder(marketplaceRoot)
        error("InteractiveMissions:CachedMissionNotFound", ...
            "The selected mission is not available in a marketplace cache.");
    end

    if ~interactiveMissions.internal.isPathWithin(marketplaceRoot, cacheRoot)
        error("InteractiveMissions:UnsafeCachePath", ...
            "The selected mission does not belong to the toolbox-managed marketplace cache.");
    end

    rmdir(marketplaceRoot, "s");
end
