function observation = observe_mission(missionName, taskId)
%OBSERVE_MISSION Independent, provisional product checks for pilot missions.
% All locals stay in this function. Behavioral probes use SimulationInput.
observation = struct("status", "unknown", "reason", "No active task", ...
    "model", "", "facts", struct, "state", struct);
models = string(find_system("Type", "block_diagram"));
models = models(arrayfun(@(m) string(get_param(m, "BlockDiagramType")) == "model", models));
observation.state.variables = evalin("base", "whos");
names = string({observation.state.variables.name});
observation.state.variables = observation.state.variables(names ~= "ans" & ~startsWith(names, "mcpTmp"));
observation.state.temporaries = evalin("base", 'who("mcpTmp_*")');
observation.state.models = models;
observation.state.figures = numel(findall(groot, "Type", "figure"));
try
    if missionName == "root-inports-outports" && taskId == "t01"
        data = evalin("base", "respiratoryData");
        observation.facts.data_class = class(data);
        observation.facts.data_points = numel(data.Data);
        observation = verdict(observation, isa(data, "timeseries") && ~isempty(data.Data) && plotted(data), "Current input timeseries plotted with matching time and data");
        return
    end
    if strlength(taskId) == 0
        return
    end
    if numel(models) ~= 1
        observation = verdict(observation, false, "Expected one learner model");
        return
    end
    model = models(1);
    observation.model = model;
    [simulationResult, simulationStart] = latestOutput(model);
    observation.facts.latest_simulation_start = 0;
    if ~isempty(simulationResult)
        observation.facts.latest_simulation_start = simulationStart;
    end
    blocks = string(find_system(model, "SearchDepth", 1, "Type", "Block"));
    types = arrayfun(@(b) string(get_param(b, "BlockType")), blocks);
    observation.facts.blocks = blocks;
    observation.facts.types = types;
    observation.state.block_parameters = arrayfun(@blockState, blocks, "UniformOutput", false);
    observation.state.model_parameters = struct("ExternalInput", get_param(model, "ExternalInput"), ...
        "LoadExternalInput", get_param(model, "LoadExternalInput"), "StopTime", get_param(model, "StopTime"));
    if missionName == "root-inports-outports"
        observation = rootChecks(observation, model, blocks, types, taskId);
    else
        observation = timeChecks(observation, model, blocks, types, taskId);
    end
catch exception
    observation.status = "unknown";
    observation.reason = string(exception.identifier) + ": " + string(exception.message);
end
end

function state = blockState(block)
state = struct("path", block, "type", get_param(block, "BlockType"), ...
    "connections", get_param(block, "PortConnectivity"));
parameters = get_param(block, "DialogParameters");
names = string(fieldnames(parameters));
for index = 1:numel(names)
    state.(names(index)) = get_param(block, names(index));
end
end

function result = verdict(result, passed, reason)
result.status = "fail";
if passed
    result.status = "pass";
end
result.reason = reason;
end

function result = rootChecks(result, model, blocks, types, task)
inputs = blocks(types == "Inport");
outputs = blocks(types == "Outport");
switch task
    case "t02"
        result = verdict(result, ~isempty(inputs), "Root Inport exists, independent of block name");
    case "t03"
        data = evalin("base", "respiratoryData");
        interval = median(diff(data.Time));
        valid = ~isempty(inputs) && get_param(model, "LoadExternalInput") == "on";
        if valid
            supplied = evalin("base", get_param(model, "ExternalInput"));
            actual = slResolve(get_param(inputs(1), "SampleTime"), char(inputs(1)));
            valid = isequal(supplied, data) && isscalar(actual) && abs(actual - interval) < 1e-10;
            result.facts.sample_interval = actual;
        end
        result = verdict(result, valid, "External input resolves to current data; sample interval matches its time vector");
    case "t04"
        displays = blocks(types == "Scope");
        valid = ~isempty(inputs) && any(arrayfun(@(b) reachable(inputs(1), b, blocks), displays));
        result = verdict(result, valid && ~isempty(latestOutput(model)), "Input reaches display and a current-model SimulationOutput exists");
    case "t05"
        valid = ~isempty(inputs) && ~isempty(outputs) && reachable(inputs(1), outputs(1), blocks);
        if valid
            % Test the actual transfer behavior, accepting equivalent realizations.
            time = (0:0.001:12)';
            frequencies = [0.25, 10];
            signal = sin(2*pi*frequencies(1)*time) + sin(2*pi*frequencies(2)*time);
            data = Simulink.SimulationData.Dataset;
            data = data.addElement(timeseries(signal, time));
            in = Simulink.SimulationInput(model);
            in = in.setExternalInput(data);
            in = in.setModelParameter("StopTime", "12", "SaveOutput", "on", "OutputSaveName", "yout", "SaveFormat", "Dataset");
            out = sim(in);
            actual = out.yout{1}.Values;
            expected = zeros(size(actual.Time));
            for frequency = frequencies
                omega = 2*pi*frequency;
                expected = expected + (sin(omega*actual.Time) - omega*0.15*cos(omega*actual.Time) + omega*0.15*exp(-actual.Time/0.15))/(1+(omega*0.15)^2);
            end
            error = sqrt(mean((double(actual.Data(:))-expected(:)).^2));
            result.facts.filter_rms_error = error;
            valid = isfinite(error) && error < 0.025;
        end
        result = verdict(result, valid, "Root output matches a 0.15-second first-order filter on slow plus fast input (RMS tolerance 0.025)");
    case {"t06", "t07"}
        out = latestOutput(model);
        if isempty(out)
            result = verdict(result, false, "No current-model SimulationOutput");
            return
        end
        filtered = out.yout{1}.Values;
        if task == "t06"
            valid = false;
            matchingSignals = 0;
            plottedMatches = 0;
            runIds = Simulink.sdi.getAllRunIDs;
            for runId = runIds(:)'
                run = Simulink.sdi.getRun(runId);
                for index = 1:run.SignalCount
                    signal = run.getSignalByIndex(index);
                    matches = sameSeries(signal.Values, filtered);
                    matchingSignals = matchingSignals + double(matches);
                    plottedMatches = plottedMatches + double(matches && signal.Checked);
                    valid = valid || (matches && signal.Checked);
                end
            end
            result.facts.sdi_matching_signals = matchingSignals;
            result.facts.sdi_plotted_matches = plottedMatches;
            result = verdict(result, valid && ~isempty(filtered.Data), "An SDI signal selected for plotting matches current root output time and data; desktop window visibility is not assessed");
        else
            data = evalin("base", "respiratoryData");
            figures = findall(groot, "Type", "figure");
            valid = false;
            for figure = figures'
                labels = findall(figure, "Type", "legend");
                meaningful = ~isempty(labels) && numel(unique(string(labels(1).String))) >= 2;
                valid = valid || (meaningful && plotted(data, figure) && plotted(filtered, figure));
            end
            result = verdict(result, valid, "One figure contains matching input/output values and distinct legend labels");
        end
end
end

function result = timeChecks(result, model, blocks, types, task)
sources = blocks(types == "Sin");
displays = blocks(types == "Scope");
if isempty(sources) || isempty(displays)
    result = verdict(result, false, "Sine source and display required");
    return
end
source = sources(1);
sampleTime = slResolve(get_param(source, "SampleTime"), char(source));
result.facts.source_sample_time = sampleTime;
switch task
    case {"t01", "t02"}
        rateOK = isscalar(sampleTime) && isfinite(sampleTime) && sampleTime == 0;
        if task == "t02"
            rateOK = isscalar(sampleTime) && isfinite(sampleTime) && sampleTime > 0;
        end
        valid = rateOK && any(arrayfun(@(b) reachable(source, b, blocks), displays));
        result = verdict(result, valid && ~isempty(latestOutput(model)), "Sine sample time, path to display and completed simulation checked");
    case {"t03", "t04"}
        if ~isscalar(sampleTime) || sampleTime ~= 0
            result = verdict(result, false, "The source must be restored to continuous time");
            return
        end
        stages = blocks(types == "ZeroOrderHold");
        if isempty(stages)
            if all(types == "Sin" | types == "Scope")
                result = verdict(result, false, "No sampling stage exists between the source and display");
                return
            end
            result.status = "unknown";
            result.reason = "Alternative sampling implementation requires author-reviewed behavioral check";
            return
        end
        stage = stages(1);
        interval = slResolve(get_param(stage, "SampleTime"), char(stage));
        valid = sampleTime == 0 && isscalar(interval) && isfinite(interval) && interval > 0 && reachable(source, stage, blocks);
        result.facts.hold_interval = interval;
        valid = valid && any(arrayfun(@(b) reachable(stage, b, blocks), displays));
        if task == "t03"
            valid = valid && ~isempty(latestOutput(model));
        else
            combined = false;
            for display = displays'
                combined = combined || (reachable(source, display, blocks, stage) && reachable(stage, display, blocks));
            end
            sourceLines = get_param(source, "LineHandles");
            stageLines = get_param(stage, "LineHandles");
            sourceLabel = string(get(sourceLines.Outport(1), "Name"));
            stageLabel = string(get(stageLines.Outport(1), "Name"));
            valid = valid && combined && strlength(sourceLabel) > 0 && strlength(stageLabel) > 0 && sourceLabel ~= stageLabel;
        end
        result = verdict(result, valid, "Continuous source and positive hold interval reach display; comparison requires two distinctly labeled paths");
    case "t05"
        parameters = get_param(model, "ObjectParameters");
        visible = false;
        for name = ["SampleTimeColors", "SampleTimeAnnotations"]
            if isfield(parameters, name)
                visible = visible || string(get_param(model, name)) == "on";
            end
        end
        result = verdict(result, visible, "Supported sample-time overlay enabled; desktop rendering is not assessed");
end
end

function found = reachable(source, target, blocks, excluded)
if nargin < 4
    excluded = "";
end
pending = source;
visited = strings(0);
found = false;
while ~isempty(pending)
    current = pending(1);
    pending(1) = [];
    if any(visited == current) || current == excluded
        continue
    end
    if current == target
        found = true;
        return
    end
    visited(end+1) = current; %#ok<AGROW>
    ports = get_param(current, "PortConnectivity");
    for port = ports'
        for handle = port.DstBlock(:)'
            if handle ~= -1
                next = string(getfullname(handle));
                if any(blocks == next)
                    pending(end+1) = next; %#ok<AGROW>
                end
            end
        end
    end
end
end

function [out, latest] = latestOutput(model)
out = [];
names = evalin("base", "whos");
latest = -Inf;
for index = 1:numel(names)
    if string(names(index).class) == "Simulink.SimulationOutput"
        candidate = evalin("base", names(index).name);
        metadata = candidate.getSimulationMetadata;
        if string(metadata.ModelInfo.ModelName) == model && isempty(candidate.ErrorMessage)
            stamp = posixtime(datetime(metadata.TimingInfo.WallClockTimestampStart));
            if stamp > latest
                out = candidate;
                latest = stamp;
            end
        end
    end
end
end

function valid = plotted(series, parent)
if nargin < 2
    parent = groot;
end
valid = false;
lines = findall(parent, "Type", "line");
for line = lines'
    owner = ancestor(line, "figure");
    valid = valid || (~isempty(owner) && string(owner.Visible) == "on" && ...
        sameVector(line.XData, series.Time) && sameVector(line.YData, series.Data));
end
end

function valid = sameSeries(left, right)
valid = isa(left, "timeseries") && isa(right, "timeseries") && sameVector(left.Time, right.Time) && sameVector(left.Data, right.Data);
end

function valid = sameVector(left, right)
valid = ~isempty(left) && numel(left) == numel(right) && all(abs(double(left(:))-double(right(:))) < 1e-8);
end
