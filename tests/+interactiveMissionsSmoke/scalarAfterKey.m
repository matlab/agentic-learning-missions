function value = scalarAfterKey(text, key)
%SCALARAFTERKEY Return the scalar value after an indented YAML key.

    tokens = regexp(text, "(?m)^\s+" + key + ":\s*""?([^""]*)""?\s*$", "tokens", "once");
    if isempty(tokens)
        value = "";
    else
        value = string(strtrim(tokens{1}));
    end
end
