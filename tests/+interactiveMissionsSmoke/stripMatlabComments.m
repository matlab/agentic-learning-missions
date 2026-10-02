function text = stripMatlabComments(text)
%STRIPMATLABCOMMENTS Remove MATLAB comments while preserving quoted percent signs.

    lines = splitlines(string(text));
    for lineIndex = 1:numel(lines)
        lines(lineIndex) = stripCommentFromLine(lines(lineIndex));
    end
    text = strjoin(lines, newline);
end

function line = stripCommentFromLine(line)
    characters = char(line);
    inSingleQuotedText = false;
    inDoubleQuotedText = false;
    index = 1;
    while index <= numel(characters)
        character = characters(index);
        if character == '"' && ~inSingleQuotedText
            if inDoubleQuotedText && index < numel(characters) && characters(index + 1) == '"'
                index = index + 2;
                continue
            end
            inDoubleQuotedText = ~inDoubleQuotedText;
        elseif character == '''' && ~inDoubleQuotedText
            if inSingleQuotedText && index < numel(characters) && characters(index + 1) == ''''
                index = index + 2;
                continue
            end
            inSingleQuotedText = ~inSingleQuotedText;
        elseif character == '%' && ~inSingleQuotedText && ~inDoubleQuotedText
            characters = characters(1:index - 1);
            break
        end
        index = index + 1;
    end
    line = string(characters);
end
