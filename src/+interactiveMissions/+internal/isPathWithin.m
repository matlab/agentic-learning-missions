function result = isPathWithin(path, root)
%ISPATHWITHIN Return true when PATH is ROOT or a descendant of ROOT.

    path = normalizePath(path);
    root = normalizePath(root);
    if strlength(path) == 0 || strlength(root) == 0
        result = false;
        return
    end

    if ispc
        path = lower(path);
        root = lower(root);
    end
    if root == filesep
        rootPrefix = root;
    else
        rootPrefix = root + filesep;
    end
    result = path == root || startsWith(path, rootPrefix);
end

function path = normalizePath(path)
    path = replace(strtrim(string(path)), "/", filesep);
    while strlength(path) > 1 && endsWith(path, filesep)
        path = extractBefore(path, strlength(path));
    end
end
