function root = defaultSafeRoot()
%DEFAULTSAFEROOT Return the default learner workspace folder.

    matlabFolder = matlabUserFolder();
    root = fullfile(matlabFolder, "Interactive-Missions");
end

function folder = matlabUserFolder()
    userPathText = string(userpath());
    userFolders = split(userPathText, pathsep());
    userFolders = strtrim(userFolders);
    userFolders = userFolders(strlength(userFolders) > 0);
    if ~isempty(userFolders)
        folder = userFolders(1);
        return
    end

    homeFolder = string(getenv("USERPROFILE"));
    if strlength(homeFolder) == 0
        homeFolder = string(getenv("HOME"));
    end
    if strlength(homeFolder) == 0
        homeFolder = string(pwd());
    end

    folder = fullfile(homeFolder, "Documents", "MATLAB");
end
