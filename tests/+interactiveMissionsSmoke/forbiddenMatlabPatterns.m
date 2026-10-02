function patterns = forbiddenMatlabPatterns()
%FORBIDDENMATLABPATTERNS Return forbidden setup/reset script patterns.

    patterns = {
        "(^|[;\n])\s*cd\s*(?:\(|\s|$)", "cd";
        "(^|[;\n])\s*rmdir\s*(?:\(|\s|$)", "rmdir";
        "(^|[;\n])\s*delete\s*(?:\(|\s|$)", "delete";
        "\bprogress[\\/]", "progress-file write";
        "\bfopen\s*\([^)]*progress", "progress-file write"
    };
end
