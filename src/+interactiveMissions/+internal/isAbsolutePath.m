function result = isAbsolutePath(path)
%ISABSOLUTEPATH Return true when PATH uses an absolute filesystem syntax.

    path = string(path);
    if strlength(path) == 0
        result = false;
        return
    end

    if ispc
        result = ~isempty(regexp(path, "^[A-Za-z]:[\\/]", "once")) || ...
            startsWith(path, ["\\", "/"]);
    else
        result = startsWith(path, "/");
    end
end
