function values = allowedMcpTools()
%ALLOWEDMCPTOOLS Return tool names allowed in mission completion checks.

    values = [
        "check_matlab_code"
        "detect_matlab_toolboxes"
        "evaluate_matlab_code"
        "model_check"
        "model_edit"
        "model_overview"
        "model_query_params"
        "model_read"
        "model_read_diagnostics"
        "model_resolve_params"
        "model_test"
        "run_matlab_file"
        "run_matlab_test_file"
    ];
end
