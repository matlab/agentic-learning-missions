function root = appRoot()
%APPROOT Return the UIHTML app asset folder.

    root = fullfile(interactiveMissions.internal.toolboxRoot(), "src", "app");
end
