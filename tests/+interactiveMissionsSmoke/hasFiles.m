function result = hasFiles(folder)
%HASFILES Return true when FOLDER contains at least one file.

    if ~isfolder(folder)
        result = false;
        return
    end

    files = dir(fullfile(folder, "**", "*"));
    result = any(~[files.isdir]);
end
