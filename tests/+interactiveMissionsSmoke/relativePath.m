function value = relativePath(path, root)
%RELATIVEPATH Return a repository-relative path with forward slashes.

    value = replace(string(path), string(root) + filesep, "");
    value = replace(value, "\", "/");
end
