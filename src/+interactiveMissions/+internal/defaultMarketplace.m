function marketplace = defaultMarketplace()
%DEFAULTMARKETPLACE Return the built-in Interactive Missions marketplace definition.

    settingsPath = fullfile(interactiveMissions.internal.appRoot(), "setting.json");
    if ~isfile(settingsPath)
        error("InteractiveMissions:DefaultMarketplaceSettingsMissing", ...
            "The built-in marketplace settings file is missing: %s", settingsPath);
    end

    try
        settings = jsondecode(fileread(settingsPath));
    catch exception
        error("InteractiveMissions:DefaultMarketplaceSettingsInvalid", ...
            "Could not read the built-in marketplace settings file: %s", exception.message);
    end

    if ~isfield(settings, "defaultMarketplace")
        error("InteractiveMissions:DefaultMarketplaceSettingsInvalid", ...
            "The built-in marketplace settings file must define defaultMarketplace.");
    end

    definition = settings.defaultMarketplace;
    requiredFields = ["id", "sourceUrl", "referenceType", "referenceName"];
    if ~all(isfield(definition, requiredFields))
        error("InteractiveMissions:DefaultMarketplaceSettingsInvalid", ...
            "The built-in marketplace settings file has an incomplete defaultMarketplace definition.");
    end

    marketplace = struct( ...
        "Id", string(definition.id), ...
        "SourceUrl", string(definition.sourceUrl), ...
        "ReferenceType", string(definition.referenceType), ...
        "ReferenceName", string(definition.referenceName) ...
        );
end
