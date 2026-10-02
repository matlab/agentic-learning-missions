function plan = buildfile()
%BUILDFILE Define Interactive Missions build tasks.

    plan = buildplan(localfunctions);
    plan.DefaultTasks = "package";
    plan("package").Description = "Build InteractiveMissions.mltbx.";
end

function packageTask(context)
    root = string(context.Plan.RootFolder);
    toolboxPath = buildToolbox(root);
    fprintf("Built toolbox: %s\n", toolboxPath);
end

function toolboxPath = buildToolbox(root, options)
%BUILDTOOLBOX Build the Interactive Missions MATLAB toolbox package.

    arguments
        root (1, 1) string = string(pwd())
        options.OutputFolder (1, 1) string = fullfile(root, "build")
    end

    root = string(root);
    sourceRoot = fullfile(root, "src");
    docsRoot = fullfile(root, "docs");
    if ~isfolder(sourceRoot) || ~isfolder(docsRoot) || ~isfolder(fullfile(root, "marketplace"))
        error("InteractiveMissions:InvalidRoot", ...
            "Root must contain src, docs, and marketplace folders: %s", root);
    end

    if ~isfolder(options.OutputFolder)
        mkdir(options.OutputFolder);
    end

    toolboxPath = fullfile(options.OutputFolder, "InteractiveMissions.mltbx");
    toolboxIdentifier = "8c2c47ce-1c6a-4a53-94d6-8e6ec37e7b92";
    opts = matlab.addons.toolbox.ToolboxOptions(root, toolboxIdentifier);
    opts.ToolboxName = "Interactive Missions";
    setOption(opts, "PackageName", "InteractiveMissions");
    opts.ToolboxVersion = "0.0.1";
    opts.AuthorName = "The MathWorks, Inc.";
    opts.AuthorCompany = "The MathWorks, Inc.";
    opts.Summary = "Hands-on MATLAB and Simulink learning missions with an agentic tutor.";
    opts.Description = "Hands-on MATLAB and Simulink learning missions with an agentic tutor.";
    setOption(opts, "Readme", fullfile(root, "README.md"));
    opts.ToolboxFiles = [
        sourceRoot
        docsRoot
        fullfile(root, "README.md")
        fullfile(root, "LICENSE.md")
        fullfile(root, "SECURITY.md")
        ];
    opts.ToolboxMatlabPath = sourceRoot;
    opts.AppGalleryFiles = fullfile(sourceRoot, "InteractiveMissions.m");
    setOption(opts, "ProductDependencies", ["MATLAB", "Simulink"]);
    opts.OutputFile = toolboxPath;

    matlab.addons.toolbox.packageToolbox(opts);
end

function setOption(options, propertyName, value)
    if isprop(options, propertyName)
        options.(propertyName) = value;
    end
end
