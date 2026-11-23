function root = toolboxRoot()
%TOOLBOXROOT Return the Interactive Missions toolbox root folder.

    openAppPath = string(which("interactiveMissions.openApp"));
    if strlength(openAppPath) == 0
        candidate = string(pwd());
        while strlength(candidate) > 0
            if isfolder(fullfile(candidate, "marketplace")) && isfolder(fullfile(candidate, "src"))
                root = candidate;
                return
            end
            parent = string(fileparts(candidate));
            if parent == candidate
                break
            end
            candidate = parent;
        end
        error("InteractiveMissions:ToolboxRootNotFound", ...
            "Cannot locate the Interactive Missions toolbox root on the MATLAB path.");
    end

    root = string(fileparts(fileparts(fileparts(openAppPath))));
end
