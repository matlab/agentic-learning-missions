function info = registerMarketplace(options)
%REGISTERMARKETPLACE Register a Git marketplace using configured Git credentials.

    arguments
        options.SourceUrl (1, 1) string
        options.ReferenceType (1, 1) string {mustBeMember(options.ReferenceType, ["default", "branch", "tag"])} = "default"
        options.ReferenceName (1, 1) string = ""
        options.ReplaceExisting (1, 1) logical = false
        options.IsDefault (1, 1) logical = false
    end

    sourceUrl = validateMarketplaceUrl(options.SourceUrl);
    referenceType = options.ReferenceType;
    referenceName = validateReferenceName(referenceType, options.ReferenceName);
    cacheBase = fullfile(prefdir(), "InteractiveMissions", "marketplaces");
    createFolder(cacheBase);
    stagingRoot = string(tempname(cacheBase));
    stagingContent = fullfile(stagingRoot, "content");
    cleanup = onCleanup(@() removeFolder(stagingRoot));

    verifyReference(sourceUrl, referenceType, referenceName);
    cloneMarketplace(sourceUrl, referenceType, referenceName, stagingContent);
    marketplaceContent = locateMarketplaceContent(stagingContent);
    manifest = readManifest(fullfile(marketplaceContent, "manifest.yaml"));
    revision = gitOutput("-C " + quoteArgument(stagingContent) + " rev-parse HEAD");

    records = interactiveMissions.internal.marketplaceRegistry("get");
    existingIndex = find(strcmpi(string({records.Id}), manifest.Id), 1);
    if ~isempty(existingIndex) && ~options.ReplaceExisting
        error("InteractiveMissions:MarketplaceAlreadyRegistered", ...
            "The marketplace ID '%s' is already registered. Confirm replacement to update it.", manifest.Id);
    end

    cacheParent = fullfile(cacheBase, manifest.Id);
    cacheRoot = fullfile(cacheParent, "content");
    backupRoot = cacheParent + ".backup-" + string(matlabProcessID());
    if isfolder(backupRoot)
        rmdir(backupRoot, "s");
    end
    if isfolder(cacheParent)
        movefile(cacheParent, backupRoot);
    end
    try
        mkdir(cacheParent);
        movefile(stagingContent, cacheRoot);
        record = makeRecord(manifest, sourceUrl, cacheRoot, referenceType, referenceName, revision, options.IsDefault);
        if isempty(existingIndex)
            records(end + 1, 1) = record;
        else
            records(existingIndex) = record;
        end
        interactiveMissions.internal.marketplaceRegistry("set", Records=records);
        if isfolder(backupRoot)
            rmdir(backupRoot, "s");
        end
    catch exception
        if isfolder(cacheParent)
            rmdir(cacheParent, "s");
        end
        if isfolder(backupRoot)
            movefile(backupRoot, cacheParent);
        end
        rethrow(exception)
    end
    clear cleanup
    info = record;
end

function sourceUrl = validateMarketplaceUrl(sourceUrl)
    sourceUrl = strtrim(string(sourceUrl));
    if contains(sourceUrl, ["\r", "\n", char(0)]) || contains(sourceUrl, [" ", """", "'"])
        error("InteractiveMissions:InvalidMarketplaceUrl", "The repository URL contains unsupported characters.");
    end
    isHttps = ~isempty(regexp(sourceUrl, "^https://[^/@:]+(?::[0-9]+)?/[^\s]+(?:\.git)?$", "once"));
    isSsh = ~isempty(regexp(sourceUrl, "^ssh://[^@/\s]+@[^/:\s]+(?::[0-9]+)?/[^\s]+(?:\.git)?$", "once"));
    isScp = ~isempty(regexp(sourceUrl, "^[^@/\s]+@[^:/\s]+:[^\s]+(?:\.git)?$", "once"));
    if ~(isHttps || isSsh || isScp) || contains(lower(sourceUrl), "/tree/")
        error("InteractiveMissions:InvalidMarketplaceUrl", ...
            "Use an HTTPS or SSH Git clone URL, not HTTP, local paths, browser URLs, or embedded credentials.");
    end
end

function referenceName = validateReferenceName(referenceType, referenceName)
    referenceName = strtrim(string(referenceName));
    if referenceType == "default"
        referenceName = "";
    elseif strlength(referenceName) == 0 || contains(referenceName, [" ", "~", "^", ":", "\", "?", "*", "[", "\r", "\n"])
        error("InteractiveMissions:InvalidMarketplaceReference", "Enter a valid branch or tag name.");
    end
end

function verifyReference(sourceUrl, referenceType, referenceName)
    if referenceType == "default"
        gitOutput("ls-remote --symref " + quoteArgument(sourceUrl) + " HEAD");
        return
    end
    prefix = "refs/heads/";
    if referenceType == "tag"
        prefix = "refs/tags/";
    end
    output = gitOutput("ls-remote " + quoteArgument(sourceUrl) + " " + quoteArgument(prefix + referenceName));
    if strlength(strtrim(output)) == 0
        error("InteractiveMissions:MarketplaceReferenceNotFound", ...
            "The %s '%s' was not found on the remote.", referenceType, referenceName);
    end
end

function cloneMarketplace(sourceUrl, referenceType, referenceName, destination)
    cloneArguments = "clone --depth 1 ";
    if referenceType ~= "default"
        cloneArguments = cloneArguments + "--branch " + quoteArgument(referenceName) + " ";
    end
    gitOutput(cloneArguments + quoteArgument(sourceUrl) + " " + quoteArgument(destination));
end

function marketplaceContent = locateMarketplaceContent(repositoryRoot)
    marketplaceContent = string(repositoryRoot);
    if ~isfile(fullfile(marketplaceContent, "manifest.yaml"))
        marketplaceContent = fullfile(repositoryRoot, "marketplace");
    end
    if ~isfile(fullfile(marketplaceContent, "manifest.yaml"))
        error("InteractiveMissions:InvalidMarketplace", "The repository does not contain marketplace manifest.yaml.");
    end
end

function manifest = readManifest(manifestPath)
    manifest = struct("Id", requiredField("id"), "Title", requiredField("title"), ...
        "SourceUrl", requiredField("source_url"), "ContentVersion", requiredField("content_version"), ...
        "MinimumToolboxVersion", requiredField("minimum_toolbox_version"));
    if isempty(regexp(manifest.Id, "^[A-Za-z0-9._-]+$", "once"))
        error("InteractiveMissions:InvalidMarketplace", "Marketplace ID '%s' contains unsupported characters.", manifest.Id);
    end
    function value = requiredField(fieldName)
        tokens = regexp(string(fileread(manifestPath)), "(?m)^" + fieldName + ":\s*[""']?([^""'\r\n]+)[""']?\s*$", "tokens", "once");
        if isempty(tokens)
            error("InteractiveMissions:InvalidMarketplace", "Marketplace manifest %s is missing %s.", manifestPath, fieldName);
        end
        value = strtrim(string(tokens{1}));
    end
end

function record = makeRecord(manifest, remoteUrl, cacheRoot, referenceType, referenceName, revision, isDefault)
    nowText = timestampNow();
    record = struct("Id", manifest.Id, "Title", manifest.Title, "SourceUrl", manifest.SourceUrl, ...
        "RemoteUrl", remoteUrl, "ContentVersion", manifest.ContentVersion, ...
        "MinimumToolboxVersion", manifest.MinimumToolboxVersion, "CacheRoot", string(cacheRoot), ...
        "UpdateStatus", "current", "UpdateMessage", "Marketplace updated.", ...
        "ReferenceType", referenceType, "ReferenceName", referenceName, "IsDefault", isDefault, "ResolvedRevision", revision, ...
        "RemoteRevision", revision, "LastAttemptAt", nowText, "LastSuccessAt", nowText, "LastRefreshedAt", nowText, ...
        "LastUpdateCheckAt", nowText);
end

function output = gitOutput(arguments)
    previousPrompt = getenv("GIT_TERMINAL_PROMPT");
    restorePrompt = onCleanup(@() setenv("GIT_TERMINAL_PROMPT", previousPrompt));
    setenv("GIT_TERMINAL_PROMPT", "0");
    [status, output] = system("git " + arguments);
    clear restorePrompt
    if status ~= 0
        throwGitError(output);
    end
    output = strtrim(string(output));
end

function throwGitError(output)
    message = strtrim(string(output));
    lowerMessage = lower(message);
    if contains(lowerMessage, ["not recognized", "not found"]) && contains(lowerMessage, "git")
        error("InteractiveMissions:GitNotInstalled", "Git is not available on PATH. Install Git and retry.");
    elseif contains(lowerMessage, ["permission denied", "authentication", "could not read username", "terminal prompts disabled", "401", "403"])
        error("InteractiveMissions:MarketplaceAuthenticationRequired", "Git authentication failed. Sign in with your credential helper or SSH agent, then retry. %s", message);
    elseif contains(lowerMessage, ["repository not found", "does not appear to be a git repository"])
        error("InteractiveMissions:MarketplaceNotFound", "Git could not find the repository. Check the clone URL and your access. %s", message);
    elseif contains(lowerMessage, ["certificate", "ssl", "tls"])
        error("InteractiveMissions:MarketplaceTlsFailed", "Git could not verify the server certificate. Check your Git certificate configuration. %s", message);
    elseif contains(lowerMessage, ["could not resolve host", "timed out", "connection", "network"])
        error("InteractiveMissions:MarketplaceNetworkFailed", "Git could not reach the repository. Check your network, proxy, or VPN. %s", message);
    end
    error("InteractiveMissions:GitFailed", "%s", message);
end

function value = quoteArgument(value)
    value = string(value);
    value = """" + replace(value, """", "") + """";
end

function createFolder(folder)
    if ~isfolder(folder)
        mkdir(folder);
    end
end

function removeFolder(folder)
    if isfolder(folder)
        rmdir(folder, "s");
    end
end

function text = timestampNow()
    text = string(datetime("now", "TimeZone", "local", "Format", "yyyy-MM-dd'T'HH:mm:ssXXX"));
end
