classdef MissionBrowserApp < handle
    %MISSIONBROWSERAPP UIHTML mission manager for the toolbox app.

    properties (Access = private)
        Figure
        HtmlView
        WorkspaceRoot (1, 1) string = ""
        AuthorWorkspace (1, 1) string = ""
        AgentClient (1, 1) string = "codex"
        Missions (:, 1) struct = struct([])
        Progress (:, 1) struct = struct([])
        Sessions (:, 1) struct = struct([])
        StartupRefreshTimer
        StartupUpdateFuture
        DefaultMarketplaceMessage (1, 1) string = ""
    end

    methods
        function app = MissionBrowserApp()
            app.loadSettings();
            app.ensureDefaultMarketplace();
            app.refreshMissingMarketplaceCaches();
            app.refreshAll();
            app.createComponents();
            app.scheduleStartupUpdateCheck();
        end

        function delete(app)
            if ~isempty(app.StartupRefreshTimer) && isvalid(app.StartupRefreshTimer)
                stop(app.StartupRefreshTimer);
                delete(app.StartupRefreshTimer);
            end
            if ~isempty(app.Figure) && isvalid(app.Figure)
                delete(app.Figure);
            end
        end
    end

    methods (Access = private)
        function createComponents(app)
            app.Figure = uifigure(Name="Interactive Missions", Position=[100 100 1180 760]);
            app.Figure.AutoResizeChildren = "off";

            grid = uigridlayout(app.Figure, [1 1]);
            grid.RowHeight = {"1x"};
            grid.ColumnWidth = {"1x"};
            grid.Padding = [0 0 0 0];

            app.HtmlView = uihtml(grid);
            app.HtmlView.Layout.Row = 1;
            app.HtmlView.Layout.Column = 1;
            app.HtmlView.HTMLSource = app.uihtmlSource();
            app.HtmlView.HTMLEventReceivedFcn = @(~, event) app.handleHtmlEvent(event);
            app.sendState();
        end

        function handleHtmlEvent(app, event)
            try
                eventName = string(event.HTMLEventName);
                eventData = event.HTMLEventData;

                switch eventName
                    case "requestState"
                        app.sendState();
                    case "chooseRepository"
                        app.sendState();
                    case "chooseWorkspace"
                        app.updateWorkspaceFromEvent(eventData);
                        app.chooseWorkspaceRoot();
                    case "chooseLaunchWorkspace"
                        app.updateWorkspaceFromEvent(eventData);
                        app.chooseWorkspaceRoot();
                    case "saveSettings"
                        app.updateWorkspaceFromEvent(eventData);
                        app.saveSettings();
                        app.sendEvent("settingsSaved", struct("SettingsPath", app.settingsFilePath()));
                    case "refreshProgress"
                        app.updateWorkspaceFromEvent(eventData);
                        app.refreshProgress();
                        app.refreshSessions();
                        app.sendState();
                    case "registerMarketplace"
                        app.registerMarketplace(eventData);
                    case "refreshMarketplaces"
                        app.refreshRemoteMarketplaces();
                        app.refreshAll();
                        app.sendState();
                        app.sendEvent("marketplacesRefreshed", struct());
                    case "unregisterMarketplace"
                        app.unregisterMarketplace(eventData);
                    case "clearMissionCache"
                        app.clearMissionCache(eventData);
                    case "openDocumentationUrl"
                        app.openDocumentationUrl(eventData);
                    case {"startMission", "practiceMission", "resumeMission", "qaMission"}
                        app.handleMissionAction(eventName, eventData);
                    otherwise
                        app.sendError("Unknown UI action: " + eventName);
                end
            catch exception
                app.sendError(string(exception.message));
            end
        end

        function refreshAll(app)
            app.refreshCatalog();
            app.refreshProgress();
            app.refreshSessions();
        end

        function refreshCatalog(app)
            catalog = interactiveMissions.catalog(Audience="all");
            app.Missions = app.catalogForUi(catalog);
        end

        function refreshProgress(app)
            app.Progress = app.progressForWorkspace();
        end

        function refreshSessions(app)
            app.Sessions = app.sessionsForUi();
        end

        function refreshRemoteMarketplaces(~)
            interactiveMissions.refreshMarketplaces();
        end

        function ensureDefaultMarketplace(app)
            try
                interactiveMissions.internal.ensureDefaultMarketplace();
                app.DefaultMarketplaceMessage = "";
            catch exception
                app.DefaultMarketplaceMessage = "Could not register the default marketplace. " + string(exception.message);
            end
        end

        function refreshMissingMarketplaceCaches(~)
            records = interactiveMissions.internal.marketplaceRegistry("get");
            for recordIndex = 1:numel(records)
                record = records(recordIndex);
                hasManifest = isfile(fullfile(record.CacheRoot, "manifest.yaml")) || ...
                    isfile(fullfile(record.CacheRoot, "marketplace", "manifest.yaml"));
                if ~hasManifest
                    interactiveMissions.refreshMarketplaces(MarketplaceId=record.Id);
                end
            end
        end

        function scheduleStartupUpdateCheck(app)
            app.StartupUpdateFuture = parfeval( ...
                backgroundPool(), @interactiveMissions.checkMarketplaceUpdates, 1);
            app.StartupRefreshTimer = timer( ...
                ExecutionMode="fixedSpacing", ...
                Period=0.25, ...
                TimerFcn=@(~, ~) app.checkForUpdatesAfterStartup());
            start(app.StartupRefreshTimer);
        end

        function checkForUpdatesAfterStartup(app)
            if isempty(app.Figure) || ~isvalid(app.Figure)
                return
            end
            futureState = string(app.StartupUpdateFuture.State);
            if futureState == "failed"
                app.stopStartupUpdateTimer();
                return
            elseif futureState ~= "finished"
                return
            end
            records = fetchOutputs(app.StartupUpdateFuture);
            app.stopStartupUpdateTimer();
            app.sendState();
            updateCount = sum(string({records.UpdateStatus}) == "updateAvailable");
            if updateCount > 0
                app.sendEvent("marketplaceUpdatesAvailable", struct("Count", updateCount));
            end
        end

        function stopStartupUpdateTimer(app)
            if isempty(app.StartupRefreshTimer) || ~isvalid(app.StartupRefreshTimer)
                return
            end
            stop(app.StartupRefreshTimer);
            delete(app.StartupRefreshTimer);
            app.StartupRefreshTimer = [];
        end

        function clearMissionCache(app, data)
            missionPath = app.getStringField(data, "MissionPath", "");
            sourceRoot = app.getStringField(data, "SourceRoot", "");
            interactiveMissions.clearMissionCache(MissionPath=missionPath, SourceRoot=sourceRoot);
            app.refreshRemoteMarketplaces();
            app.refreshAll();
            app.sendState();
            app.sendEvent("missionCacheCleared", struct("Title", app.getStringField(data, "Title", "Marketplace")));
        end

        function registerMarketplace(app, data)
            sourceUrl = app.getStringField(data, "SourceUrl", "");
            referenceType = app.getStringField(data, "ReferenceType", "default");
            referenceName = app.getStringField(data, "ReferenceName", "");
            replaceExisting = any(strcmpi(app.getStringField(data, "ReplaceExisting", "false"), ["true", "1"]));
            info = interactiveMissions.registerMarketplace(SourceUrl=sourceUrl, ...
                ReferenceType=referenceType, ReferenceName=referenceName, ReplaceExisting=replaceExisting);
            app.refreshAll();
            app.sendState();
            app.sendEvent("marketplaceRegistered", struct("Title", info.Title));
        end

        function unregisterMarketplace(app, data)
            marketplaceId = app.getStringField(data, "MarketplaceId", "");
            interactiveMissions.unregisterMarketplace(MarketplaceId=marketplaceId);
            app.refreshAll();
            app.sendState();
            app.sendEvent("marketplaceUnregistered", struct("MarketplaceId", marketplaceId));
        end

        function handleMissionAction(app, eventName, data)
            missionName = app.getStringField(data, "MissionName", app.getStringField(data, "MissionId", ""));
            mission = app.findMission(missionName);
            action = erase(eventName, "Mission");

            switch action
                case "start"
                    mode = "regular";
                    workspaceRoot = app.getStringField(data, "WorkspaceRoot", app.WorkspaceRoot);
                    agentClient = app.getStringField(data, "AgentClient", app.AgentClient);
                    launch = app.prepareLaunch(mission, mode, workspaceRoot, true, agentClient);
                    app.AgentClient = launch.AgentClient;
                    app.saveSettings();
                    app.recordSession(launch, mission);
                case "practice"
                    mode = "practice";
                    workspaceRoot = app.getStringField(data, "WorkspaceRoot", app.WorkspaceRoot);
                    agentClient = app.getStringField(data, "AgentClient", app.AgentClient);
                    launch = app.prepareLaunch(mission, mode, workspaceRoot, true, agentClient);
                    app.AgentClient = launch.AgentClient;
                    app.saveSettings();
                case "resume"
                    session = app.sessionFromEvent(data, mission);
                    if isempty(session)
                        app.sendError("No resumable session is available for this mission.");
                        return
                    end
                    mode = "resume";
                    agentClient = app.getStringField(data, "AgentClient", app.AgentClient);
                    launch = app.prepareLaunch(mission, mode, session(1).WorkspaceRoot, false, agentClient);
                    app.AgentClient = launch.AgentClient;
                    app.touchSession(session(1), launch);
                case "qa"
                    prompt = "Use qa-mission on mission " + mission.Title + " (" + mission.MissionName + ...
                        ") --full. Check app metadata, learner-facing tasks, setup/reset consistency, " + ...
                        "completion checks, hints, and learning outcome alignment.";
                    launch = struct( ...
                        "Prompt", prompt, ...
                        "WorkspaceRoot", app.AuthorWorkspace, ...
                        "RuntimeRoot", "", ...
                        "ManifestPath", "", ...
                        "ProgressPath", "", ...
                        "LaunchPromptPath", "", ...
                        "Command", prompt, ...
                        "AgentClient", app.AgentClient, ...
                        "Step1Text", "", ...
                        "Step2Text", "", ...
                        "Step3Text", "", ...
                        "Step4Text", "");
                otherwise
                    error("InteractiveMissions:UnsupportedAction", "Unsupported action %s.", action);
            end

            app.sendEvent("promptReady", struct( ...
                "Prompt", launch.Prompt, ...
                "Action", action, ...
                "MissionName", mission.MissionName, ...
                "WorkspaceRoot", launch.WorkspaceRoot, ...
                "LaunchPromptPath", launch.LaunchPromptPath, ...
                "Command", launch.Command, ...
                "AgentClient", launch.AgentClient, ...
                "Step1Text", launch.Step1Text, ...
                "Step2Text", launch.Step2Text, ...
                "Step3Text", launch.Step3Text, ...
                "Step4Text", launch.Step4Text));
            app.refreshAll();
            app.sendState();
        end

        function launch = prepareLaunch(~, mission, mode, workspaceRoot, requireEmpty, agentClient)
            agentClient = normalizeAgentClient(agentClient);
            info = interactiveMissions.prepareWorkspace( ...
                WorkspaceRoot=workspaceRoot, ...
                MissionName=mission.MissionName, ...
                Mode=mode, ...
                RequireEmpty=requireEmpty, ...
                AgentClient=agentClient);
            prompt = string(fileread(info.LaunchPromptPath));
            command = interactiveMissions.launchCommand( ...
                SafeRoot=info.WorkspaceRoot, ...
                ManifestPath=info.ManifestPath, ...
                MissionName=mission.MissionName, ...
                Agent=agentClient, ...
                Shell="powershell");
            launchText = launchUiText(agentClient);

            launch = struct();
            launch.Prompt = prompt;
            launch.WorkspaceRoot = string(info.WorkspaceRoot);
            launch.RuntimeRoot = string(info.RuntimeRoot);
            launch.ManifestPath = string(info.ManifestPath);
            launch.ProgressPath = string(info.ProgressPath);
            launch.LaunchPromptPath = string(info.LaunchPromptPath);
            launch.Command = string(command);
            launch.AgentClient = string(info.AgentClient);
            launch.Step1Text = launchText.Step1;
            launch.Step2Text = launchText.Step2;
            launch.Step3Text = launchText.Step3;
            launch.Step4Text = launchText.Step4;
        end

        function missions = catalogForUi(app, catalog)
            missions = repmat(app.emptyMission(), 0, 1);
            for rowIndex = 1:height(catalog)
                mission = app.emptyMission();
                mission.MissionName = catalog.MissionName(rowIndex);
                mission.MissionId = catalog.MissionId(rowIndex);
                mission.LegacyId = catalog.LegacyId(rowIndex);
                mission.Title = catalog.Title(rowIndex);
                mission.Description = catalog.Objective(rowIndex);
                mission.Objective = catalog.Objective(rowIndex);
                mission.Thumbnail = app.thumbnailForUi(catalog.Thumbnail(rowIndex));
                mission.Summary = catalog.Summary(rowIndex);
                mission.Audience = "";
                mission.Difficulty = catalog.Status(rowIndex);
                mission.EstimatedMinutes = catalog.EstimatedMinutes(rowIndex);
                mission.Products = catalog.Products{rowIndex};
                mission.Topics = catalog.Topics{rowIndex};
                mission.Status = catalog.Status(rowIndex);
                mission.LearnerVisible = catalog.LearnerVisible(rowIndex);
                mission.TileOrder = catalog.TileOrder(rowIndex);
                mission.TaskCount = catalog.TaskCount(rowIndex);
                mission.HasSetup = catalog.HasSetup(rowIndex);
                mission.Path = catalog.Path(rowIndex);
                mission.SourceType = catalog.SourceType(rowIndex);
                mission.SourceRoot = catalog.SourceRoot(rowIndex);
                mission.MarketplaceSource = catalog.MarketplaceSource(rowIndex);
                mission.MarketplaceTitle = catalog.MarketplaceTitle(rowIndex);
                mission.MarketplaceContentVersion = catalog.MarketplaceContentVersion(rowIndex);
                mission.MissionVersion = catalog.MissionVersion(rowIndex);
                mission.SuggestedWorkspaceRoot = interactiveMissions.internal.nextWorkspaceRoot( ...
                    mission.MissionName, ParentRoot=app.WorkspaceRoot);
                mission.CanResume = false;
                mission.ProgressIndex = NaN;
                missions(end + 1, 1) = mission; %#ok<AGROW>
            end
        end

        function progress = progressForWorkspace(app)
            progress = repmat(app.emptyProgressItem(), 0, 1);
            sessions = app.progressFromRecentWorkspaces();
            for sessionIndex = 1:numel(sessions)
                item = app.emptyProgressItem();
                item.LearnerId = sessions(sessionIndex).Username;
                item.MissionName = sessions(sessionIndex).MissionName;
                item.MissionId = sessions(sessionIndex).MissionId;
                item.CurrentTask = sessions(sessionIndex).CurrentTask;
                item.CompletedCount = sessions(sessionIndex).CompletedCount;
                item.IsComplete = sessions(sessionIndex).IsComplete;
                item.LastSession = sessions(sessionIndex).LastSession;
                item.Notes = sessions(sessionIndex).Notes;
                item.Path = sessions(sessionIndex).ProgressPath;
                item.IsUsable = sessions(sessionIndex).IsUsable;
                item.Index = numel(progress) + 1;
                progress(end + 1, 1) = item; %#ok<AGROW>
            end
        end

        function progress = progressFromEvent(app, data, mission)
            progressIndex = app.getDoubleField(data, "ProgressIndex", NaN);
            if ~isnan(progressIndex) && progressIndex >= 1 && progressIndex <= numel(app.Progress)
                progress = app.Progress(progressIndex);
                return
            end

            progress = app.Progress(app.progressMatchesMission(app.Progress, mission) & [app.Progress.IsUsable]);
        end

        function sessions = sessionsForUi(app)
            sessions = app.indexedSessions();
            progress = app.progressFromRecentWorkspaces();
            for progressIndex = 1:numel(progress)
                sessions = app.mergeProgressIntoSessions(sessions, progress(progressIndex));
            end

            for sessionIndex = 1:numel(sessions)
                sessions(sessionIndex).Index = sessionIndex;
                sessions(sessionIndex).IsResumable = sessions(sessionIndex).IsUsable && ...
                    ~sessions(sessionIndex).IsComplete && sessions(sessionIndex).Mode ~= "practice";
            end
        end

        function sessions = indexedSessions(app)
            settings = interactiveMissions.preferences("get");
            sessions = repmat(app.emptySessionItem(), 0, 1);
            if ~isfield(settings, "TrackedSessions")
                return
            end

            rawSessions = settings.TrackedSessions;
            if isempty(rawSessions)
                return
            end
            rawSessions = rawSessions(:);
            for rawIndex = 1:numel(rawSessions)
                item = app.emptySessionItem();
                item.SessionId = app.progressField(rawSessions(rawIndex), "SessionId", "");
                item.MissionName = app.progressField(rawSessions(rawIndex), "MissionName", "");
                item.MissionId = app.progressField(rawSessions(rawIndex), "MissionId", "");
                item.Title = app.progressField(rawSessions(rawIndex), "Title", "");
                item.Username = app.progressField(rawSessions(rawIndex), "User" + "name", "");
                item.WorkspaceRoot = app.progressField(rawSessions(rawIndex), "WorkspaceRoot", "");
                item.ProgressPath = app.progressField(rawSessions(rawIndex), "ProgressPath", "");
                item.LaunchPromptPath = app.progressField(rawSessions(rawIndex), "LaunchPromptPath", "");
                item.Mode = app.normalizeModeLabel(app.progressField(rawSessions(rawIndex), "Mode", "regular"));
                item.CreatedAt = app.progressField(rawSessions(rawIndex), "CreatedAt", "");
                item.LastSeenAt = app.progressField(rawSessions(rawIndex), "LastSeenAt", item.CreatedAt);
                item.CurrentTask = "not started";
                item.IsUsable = true;
                if isfile(item.ProgressPath)
                    item = app.applyProgressFile(item, item.ProgressPath);
                end
                sessions(end + 1, 1) = item; %#ok<AGROW>
            end
        end

        function progress = progressFromRecentWorkspaces(app)
            settings = interactiveMissions.preferences("get");
            workspaces = string(app.WorkspaceRoot);
            workspaces = [workspaces; app.indexedActiveWorkspaceRoots()];
            if isfield(settings, "ActiveWorkspaces")
                workspaces = [workspaces; string(settings.ActiveWorkspaces(:))];
            end
            if isfield(settings, "RecentWorkspaces")
                workspaces = [workspaces; string(settings.RecentWorkspaces(:))];
            end
            workspaces = unique(workspaces(strlength(strtrim(workspaces)) > 0), "stable");

            progress = repmat(app.emptySessionItem(), 0, 1);
            for workspaceIndex = 1:numel(workspaces)
                manifestPath = fullfile(workspaces(workspaceIndex), ".interactive-missions", "manifest.json");
                if ~isfile(manifestPath)
                    continue
                end
                try
                    manifest = jsondecode(fileread(manifestPath));
                    progressPath = app.progressField(manifest, "progressPath", "");
                    if strlength(progressPath) == 0
                        progressPath = app.progressField(manifest, "resumableProgressPath", "");
                    end
                    if strlength(progressPath) == 0
                        progressPath = fullfile(workspaces(workspaceIndex), ".interactive-missions", "progress.json");
                    end
                catch
                    progressPath = "";
                end
                if strlength(progressPath) == 0 || ~isfile(progressPath)
                    continue
                end
                item = app.emptySessionItem();
                item.WorkspaceRoot = workspaces(workspaceIndex);
                item.ProgressPath = string(progressPath);
                item.LaunchPromptPath = fullfile(workspaces(workspaceIndex), ".interactive-missions", "launch-prompt.md");
                item.Mode = app.normalizeModeLabel(app.progressField(manifest, "mode", "regular"));
                item.MissionName = app.progressField(manifest, "missionName", item.MissionName);
                item.MissionId = app.progressField(manifest, "missionId", item.MissionId);
                item.Title = app.progressField(manifest, "missionTitle", item.Title);
                item.LastSeenAt = app.progressField(manifest, "createdAt", item.LastSeenAt);
                item.IsUsable = true;
                item = app.applyProgressFile(item, progressPath);
                item.Mode = app.normalizeModeLabel(item.Mode);
                progress(end + 1, 1) = item; %#ok<AGROW>
            end
        end

        function workspaceRoots = indexedActiveWorkspaceRoots(app)
            workspaceRoots = strings(0, 1);
            indexPath = fullfile(app.progressStoreRoot(), "active_workspaces.json");
            if ~isfile(indexPath)
                return
            end

            try
                decoded = jsondecode(fileread(indexPath));
            catch
                return
            end

            if ~isfield(decoded, "Workspaces") || isempty(decoded.Workspaces)
                return
            end

            records = decoded.Workspaces(:);
            for recordIndex = 1:numel(records)
                if isfield(records(recordIndex), "WorkspaceRoot")
                    workspaceRoots(end + 1, 1) = string(records(recordIndex).WorkspaceRoot); %#ok<AGROW>
                elseif isfield(records(recordIndex), "ManifestPath")
                    workspaceRoots(end + 1, 1) = string(fileparts(fileparts(records(recordIndex).ManifestPath))); %#ok<AGROW>
                end
            end
        end

        function sessions = mergeProgressIntoSessions(app, sessions, progress)
            matchIndex = find(string({sessions.ProgressPath}) == progress.ProgressPath, 1);
            if isempty(matchIndex)
                progress.SessionId = "progress:" + progress.ProgressPath;
                progress.LaunchPromptPath = fullfile(progress.WorkspaceRoot, ".interactive-missions", "launch-prompt.md");
                sessions(end + 1, 1) = progress;
            else
                sessions(matchIndex) = app.mergeSessionProgress(sessions(matchIndex), progress);
            end
        end

        function session = mergeSessionProgress(~, session, progress)
            session.MissionName = progress.MissionName;
            session.MissionId = progress.MissionId;
            session.Username = progress.Username;
            session.CurrentTask = progress.CurrentTask;
            session.CompletedCount = progress.CompletedCount;
            session.IsComplete = progress.IsComplete;
            session.LastSession = progress.LastSession;
            session.Notes = progress.Notes;
            session.IsUsable = progress.IsUsable;
        end

        function item = applyProgressFile(app, item, progressPath)
            try
                data = jsondecode(fileread(progressPath));
                item.MissionName = app.progressField(data, "missionName", app.progressField(data, "mission_name", item.MissionName));
                item.MissionId = app.progressField(data, "missionId", app.progressField(data, "mission_id", item.MissionId));
                item.CurrentTask = app.progressField(data, "currentStepId", app.progressField(data, "current_task", item.CurrentTask));
                item.CompletedCount = app.completedStepCount(data);
                item.IsComplete = app.progressIsComplete(data, item.CurrentTask);
                item.Username = app.progressDisplayName(data, item);
                item.Mode = app.progressField(data, "mode", item.Mode);
                item.LastSession = app.progressField(data, "updatedAt", app.progressField(data, "last_session", item.LastSession));
                item.Notes = app.progressField(data, "notes", item.Notes);
                item.IsUsable = true;
            catch exception
                item.CurrentTask = "unreadable";
                item.Notes = "Unreadable progress file: " + string(exception.message);
                item.IsUsable = false;
            end

            if strlength(item.MissionName) == 0
                [~, filename] = fileparts(progressPath);
                item.MissionName = string(filename);
            end
        end

        function session = sessionFromEvent(app, data, mission)
            sessionIndex = app.getDoubleField(data, "SessionIndex", app.getDoubleField(data, "ProgressIndex", NaN));
            if ~isnan(sessionIndex) && sessionIndex >= 1 && sessionIndex <= numel(app.Sessions)
                session = app.Sessions(sessionIndex);
                return
            end

            session = app.Sessions(app.sessionMatchesMission(app.Sessions, mission) & [app.Sessions.IsResumable]);
        end

        function recordSession(app, launch, mission)
            settings = interactiveMissions.preferences("get");
            sessions = app.settingsSessions(settings);
            existingIndex = find(string({sessions.ProgressPath}) == launch.ProgressPath, 1);
            item = app.emptySessionItem();
            if ~isempty(existingIndex)
                item = sessions(existingIndex);
            else
                item.SessionId = "session-" + replace(app.timestampNow(), [":", "-", "T"], "") + ...
                    "-" + string(randi(999999));
            end

            nowText = app.timestampNow();
            item.MissionName = mission.MissionName;
            item.MissionId = mission.MissionId;
            item.Title = mission.Title;
            item.Username = "Awaiting learner name";
            item.WorkspaceRoot = launch.WorkspaceRoot;
            item.ProgressPath = launch.ProgressPath;
            item.LaunchPromptPath = launch.LaunchPromptPath;
            item.Mode = "regular";
            if strlength(item.CreatedAt) == 0
                item.CreatedAt = nowText;
            end
            item.LastSeenAt = nowText;
            item.IsUsable = true;
            sessions = app.upsertSession(sessions, item);
            app.saveSessionSettings(sessions);
        end

        function touchSession(app, session, launch)
            settings = interactiveMissions.preferences("get");
            sessions = app.settingsSessions(settings);
            session.LastSeenAt = app.timestampNow();
            session.LaunchPromptPath = launch.LaunchPromptPath;
            session.WorkspaceRoot = launch.WorkspaceRoot;
            session.ProgressPath = launch.ProgressPath;
            sessions = app.upsertSession(sessions, session);
            app.saveSessionSettings(sessions);
        end

        function sessions = settingsSessions(app, settings)
            sessions = repmat(app.emptySessionItem(), 0, 1);
            if isfield(settings, "TrackedSessions") && ~isempty(settings.TrackedSessions)
                rawSessions = settings.TrackedSessions(:);
                for index = 1:numel(rawSessions)
                    item = app.emptySessionItem();
                    fields = fieldnames(item);
                    for fieldIndex = 1:numel(fields)
                        fieldName = fields{fieldIndex};
                        if isfield(rawSessions(index), fieldName)
                            item.(fieldName) = rawSessions(index).(fieldName);
                        end
                    end
                    sessions(end + 1, 1) = item; %#ok<AGROW>
                end
            end
        end

        function sessions = upsertSession(~, sessions, item)
            matchIndex = find(string({sessions.SessionId}) == item.SessionId | ...
                string({sessions.ProgressPath}) == item.ProgressPath, 1);
            if isempty(matchIndex)
                sessions = [item; sessions(:)];
            else
                sessions(matchIndex) = item;
            end
            sessions = sessions(1:min(numel(sessions), 50));
        end

        function saveSessionSettings(app, sessions)
            recentWorkspaces = unique([string({sessions.WorkspaceRoot})'; app.WorkspaceRoot], "stable");
            recentWorkspaces = recentWorkspaces(strlength(strtrim(recentWorkspaces)) > 0);
            settings = struct();
            settings.LastWorkspace = interactiveMissions.internal.workspaceBaseRoot(app.WorkspaceRoot);
            settings.AgentClient = app.AgentClient;
            settings.AuthorWorkspace = app.AuthorWorkspace;
            settings.RecentWorkspaces = cellstr(recentWorkspaces(1:min(numel(recentWorkspaces), 10)));
            settings.ActiveWorkspaces = cellstr(recentWorkspaces(1:min(numel(recentWorkspaces), 50)));
            settings.TrackedSessions = sessions;
            interactiveMissions.preferences("set", Settings=settings);
        end

        function text = timestampNow(~)
            text = string(datetime("now", "TimeZone", "local", "Format", "yyyy-MM-dd'T'HH:mm:ssXXX"));
        end

        function mission = findMission(app, missionName)
            missionName = string(missionName);
            missionIndex = find(string({app.Missions.MissionName}) == missionName | ...
                string({app.Missions.LegacyId}) == missionName, 1);
            if isempty(missionIndex)
                error("InteractiveMissions:MissionNotFound", "Mission %s is not available.", missionName);
            end
            mission = app.Missions(missionIndex);
        end

        function state = appState(app)
            state = struct();
            state.RepositoryRoot = interactiveMissions.internal.toolboxRoot();
            state.MarketplaceCacheRoot = fullfile(prefdir(), "InteractiveMissions", "marketplaces");
            state.WorkspaceRoot = app.WorkspaceRoot;
            state.AgentClient = app.AgentClient;
            state.SettingsPath = app.settingsFilePath();
            state.Missions = app.missionsForUi();
            state.Marketplaces = app.marketplacesForUi();
            state.DefaultMarketplaceMessage = app.DefaultMarketplaceMessage;
            state.Progress = app.Progress;
            state.Sessions = app.Sessions;
            state.LearnerFaq = app.learnerFaqForUi();
            state.Documentation = struct("Pages", app.documentationForUi());
        end

        function page = learnerFaqForUi(app)
            faqPath = fullfile(interactiveMissions.internal.toolboxRoot(), "src", "docs", "learner-faq.md");
            page = app.emptyDocumentationPage();
            page.Title = "Learner FAQ";
            page.FileName = "learner-faq.md";
            page.Path = string(faqPath);
            if ~isfile(faqPath)
                return
            end

            markdown = string(fileread(faqPath));
            page.Title = app.documentationTitle(markdown, page.FileName);
            page.Markdown = markdown;
        end

        function pages = documentationForUi(app)
            documentationRoot = fullfile(interactiveMissions.internal.toolboxRoot(), "docs");
            files = dir(fullfile(documentationRoot, "*.md"));
            [~, order] = sort(string({files.name}));
            files = files(order);
            pages = repmat(app.emptyDocumentationPage(), numel(files), 1);
            for fileIndex = 1:numel(files)
                pagePath = fullfile(files(fileIndex).folder, files(fileIndex).name);
                markdown = string(fileread(pagePath));
                pages(fileIndex).Title = app.documentationTitle(markdown, files(fileIndex).name);
                pages(fileIndex).FileName = string(files(fileIndex).name);
                pages(fileIndex).Path = string(pagePath);
                pages(fileIndex).Markdown = markdown;
            end
        end

        function missions = missionsForUi(app)
            missions = app.Missions;
            for missionIndex = 1:numel(missions)
                sessions = app.Sessions(app.sessionMatchesMission(app.Sessions, missions(missionIndex)) & ...
                    [app.Sessions.IsResumable]);
                missions(missionIndex).CanResume = ~isempty(sessions);
                if isempty(sessions)
                    missions(missionIndex).ProgressIndex = NaN;
                else
                    missions(missionIndex).ProgressIndex = sessions(1).Index;
                end
            end
        end

        function marketplaces = marketplacesForUi(app)
            marketplaces = repmat(app.emptyMarketplaceItem(), 0, 1);
            records = interactiveMissions.internal.marketplaceRegistry("get");
            for recordIndex = 1:numel(records)
                record = records(recordIndex);
                item = app.emptyMarketplaceItem();
                item.Id = record.Id;
                item.Title = record.Title;
                item.Source = record.RemoteUrl;
                item.SourceUrl = record.RemoteUrl;
                item.ContentVersion = record.ContentVersion;
                item.SourceRoot = record.CacheRoot;
                item.ReferenceType = record.ReferenceType;
                item.ReferenceName = record.ReferenceName;
                item.IsDefault = record.IsDefault;
                item.UpdateStatus = record.UpdateStatus;
                item.UpdateMessage = record.UpdateMessage;
                item.MissionCount = sum(startsWith(string({app.Missions.SourceRoot}), string(record.CacheRoot), IgnoreCase=true));
                marketplaces(end + 1, 1) = item; %#ok<AGROW>
            end
        end

        function updateWorkspaceFromEvent(app, data)
            workspaceRoot = app.getStringField(data, "WorkspaceRoot", app.WorkspaceRoot);
            if strlength(strtrim(workspaceRoot)) > 0
                app.WorkspaceRoot = workspaceRoot;
            end
        end

        function openDocumentationUrl(app, data)
            url = app.getStringField(data, "Url", "");
            isHttpUrl = startsWith(url, ["http://", "https://"], IgnoreCase=true);
            if ~any(isHttpUrl)
                error("InteractiveMissions:InvalidDocumentationUrl", ...
                    "Only HTTP(S) documentation URLs can be opened.");
            end
            web(url, "-browser");
        end

        function chooseWorkspaceRoot(app)
            selectedFolder = uigetdir(app.WorkspaceRoot, "Select learner workspace");
            if isequal(selectedFolder, 0)
                app.sendState();
                return
            end

            app.WorkspaceRoot = string(selectedFolder);
            app.refreshProgress();
            app.refreshSessions();
            app.sendState();
        end

        function loadSettings(app)
            settings = interactiveMissions.preferences("get");
            app.WorkspaceRoot = interactiveMissions.internal.workspaceBaseRoot(settings.LastWorkspace);
            if isfield(settings, "AgentClient")
                app.AgentClient = normalizeAgentClient(settings.AgentClient);
            end
            app.AuthorWorkspace = string(settings.AuthorWorkspace);
        end

        function saveSettings(app)
            settings = struct();
            settings.LastWorkspace = interactiveMissions.internal.workspaceBaseRoot(app.WorkspaceRoot);
            settings.AgentClient = app.AgentClient;
            settings.AuthorWorkspace = app.AuthorWorkspace;
            settings.RecentWorkspaces = {char(app.WorkspaceRoot)};
            settings.ActiveWorkspaces = {char(app.WorkspaceRoot)};
            interactiveMissions.preferences("set", Settings=settings);
        end

        function sendState(app)
            if isempty(app.HtmlView) || ~isvalid(app.HtmlView)
                return
            end
            app.HtmlView.Data = app.appState();
            app.sendEvent("stateChanged", app.appState());
        end

        function sendError(app, message)
            app.sendEvent("error", struct("Message", string(message)));
        end

        function sendEvent(app, eventName, data)
            if isempty(app.HtmlView) || ~isvalid(app.HtmlView)
                return
            end
            sendEventToHTMLSource(app.HtmlView, eventName, data);
        end

        function source = uihtmlSource(~)
            sourceRoot = interactiveMissions.internal.appRoot();
            sourceFiles = ["index.html", "app.js", "styles.css"];
            sourcePaths = fullfile(sourceRoot, sourceFiles);
            sourceInfo = cellfun(@dir, cellstr(sourcePaths));
            sourceKeys = strings(size(sourceFiles));

            for sourceIndex = 1:numel(sourceFiles)
                modifiedMilliseconds = round(sourceInfo(sourceIndex).datenum*86400000);
                sourceKeys(sourceIndex) = modifiedMilliseconds + "-" + sourceInfo(sourceIndex).bytes;
            end

            cacheName = "uihtml-" + join(sourceKeys, "_");
            cacheRoot = fullfile(prefdir(), "InteractiveMissions", "uihtml", cacheName);
            if ~isfolder(cacheRoot)
                mkdir(cacheRoot);
            end

            for sourceIndex = 1:numel(sourceFiles)
                destinationPath = fullfile(cacheRoot, sourceFiles(sourceIndex));
                if ~isfile(destinationPath)
                    copyfile(sourcePaths(sourceIndex), destinationPath);
                end
            end

            source = fullfile(cacheRoot, "index.html");
        end
    end

    methods (Static, Access = private)
        function mission = emptyMission()
            mission = struct( ...
                "MissionName", "", ...
                "MissionId", "", ...
                "LegacyId", "", ...
                "Title", "", ...
                "Description", "", ...
                "Objective", "", ...
                "Thumbnail", "", ...
                "Summary", "", ...
                "Audience", "", ...
                "Difficulty", "", ...
                "EstimatedMinutes", NaN, ...
                "Products", strings(0, 1), ...
                "Topics", strings(0, 1), ...
                "Status", "", ...
                "LearnerVisible", false, ...
                "TileOrder", NaN, ...
                "TaskCount", 0, ...
                "HasSetup", false, ...
                "Path", "", ...
                "SourceType", "", ...
                "SourceRoot", "", ...
                "MarketplaceSource", "", ...
                "MarketplaceTitle", "", ...
                "MarketplaceContentVersion", "", ...
                "MissionVersion", "", ...
                "SuggestedWorkspaceRoot", "", ...
                "CanResume", false, ...
                "ProgressIndex", NaN ...
                );
        end

        function item = emptyProgressItem()
            item = struct( ...
                "Index", NaN, ...
                "LearnerId", "", ...
                "MissionName", "", ...
                "MissionId", "", ...
                "CurrentTask", "", ...
                "CompletedCount", 0, ...
                "IsComplete", false, ...
                "LastSession", "", ...
                "Notes", "", ...
                "Path", "", ...
                "IsUsable", false ...
                );
        end

        function item = emptyMarketplaceItem()
            item = struct( ...
                "Id", "", ...
                "Title", "", ...
                "Source", "", ...
                "SourceUrl", "", ...
                "ContentVersion", "", ...
                "SourceRoot", "", ...
                "MissionPath", "", ...
                "MissionCount", 0, ...
                "ReferenceType", "default", ...
                "ReferenceName", "", ...
                "IsDefault", false, ...
                "UpdateStatus", "", ...
                "UpdateMessage", "" ...
                );
        end

        function item = emptySessionItem()
            item = struct( ...
                "Index", NaN, ...
                "SessionId", "", ...
                "MissionName", "", ...
                "MissionId", "", ...
                "Title", "", ...
                "Username", "", ...
                "WorkspaceRoot", "", ...
                "ProgressPath", "", ...
                "LaunchPromptPath", "", ...
                "Mode", "regular", ...
                "CurrentTask", "", ...
                "CompletedCount", 0, ...
                "IsComplete", false, ...
                "LastSession", "", ...
                "Notes", "", ...
                "CreatedAt", "", ...
                "LastSeenAt", "", ...
                "IsUsable", false, ...
                "IsResumable", false ...
                );
        end

        function page = emptyDocumentationPage()
            page = struct( ...
                "Title", "", ...
                "FileName", "", ...
                "Path", "", ...
                "Markdown", "" ...
                );
        end

        function value = getStringField(data, fieldName, fallback)
            value = fallback;
            if isstruct(data) && isfield(data, fieldName)
                value = string(data.(fieldName));
            end
        end

        function value = getDoubleField(data, fieldName, fallback)
            value = fallback;
            if isstruct(data) && isfield(data, fieldName)
                value = str2double(string(data.(fieldName)));
            end
        end

        function value = progressField(data, fieldName, fallback)
            value = fallback;
            if isstruct(data) && isfield(data, fieldName)
                value = string(data.(fieldName));
            end
        end

        function matches = progressMatchesMission(progress, mission)
            if isempty(progress)
                matches = false(0, 1);
                return
            end

            matches = string({progress.MissionName}) == mission.MissionName | ...
                string({progress.MissionId}) == mission.MissionId | ...
                string({progress.MissionId}) == mission.LegacyId;
        end

        function matches = sessionMatchesMission(sessions, mission)
            if isempty(sessions)
                matches = false(0, 1);
                return
            end

            matches = string({sessions.MissionName}) == mission.MissionName | ...
                string({sessions.MissionId}) == mission.MissionId | ...
                string({sessions.MissionId}) == mission.LegacyId;
        end

        function mode = normalizeModeLabel(mode)
            mode = string(mode);
            if mode == "tracked"
                mode = "regular";
            end
        end

        function count = completedStepCount(data)
            count = 0;
            if isstruct(data) && isfield(data, "completedStepIds")
                count = numel(string(data.completedStepIds));
            elseif isstruct(data) && isfield(data, "completed_tasks")
                count = numel(string(data.completed_tasks));
            end
        end

        function isComplete = progressIsComplete(data, currentStep)
            isComplete = currentStep == "complete";
            if isstruct(data) && isfield(data, "isComplete")
                isComplete = logical(data.isComplete);
            end
        end

        function displayName = progressDisplayName(app, data, item)
            displayName = strtrim(app.progressField(data, "learnerName", app.progressField(data, "learner_id", item.Username)));
            if strlength(displayName) == 0 && item.CompletedCount == 0 && ~item.IsComplete
                displayName = "Awaiting learner name";
            end
        end

        function root = progressStoreRoot()
            root = fullfile(prefdir(), "InteractiveMissions", "app");
        end

        function title = documentationTitle(markdown, fallback)
            title = erase(string(fallback), ".md");
            lines = splitlines(string(markdown));
            firstContentLine = "";
            for lineIndex = 1:numel(lines)
                candidate = strtrim(lines(lineIndex));
                if strlength(candidate) > 0
                    firstContentLine = candidate;
                    break
                end
            end

            if strlength(firstContentLine) > 0
                title = regexprep(firstContentLine, "^#+\s*", "");
            end
        end

        function text = yamlQuote(text)
            text = """" + replace(string(text), """", "\""") + """";
        end

        function thumbnail = thumbnailForUi(path)
            path = string(path);
            if ~isfile(path)
                thumbnail = "";
                return
            end

            fileIdentifier = fopen(path, "r");
            if fileIdentifier < 0
                thumbnail = path;
                return
            end
            cleanup = onCleanup(@() fclose(fileIdentifier));
            bytes = fread(fileIdentifier, Inf, "uint8=>uint8");
            clear cleanup

            encoded = matlab.net.base64encode(bytes);
            [~, ~, extension] = fileparts(path);
            mimeType = "image/png";
            if lower(string(extension)) == ".svg"
                mimeType = "image/svg+xml";
            end
            thumbnail = "data:" + mimeType + ";base64," + string(encoded);
        end

        function settingsPath = settingsFilePath()
            settingsPath = fullfile(prefdir(), "InteractiveMissions", "settings.json");
        end

        function writeText(path, text)
            fileIdentifier = fopen(path, "w");
            if fileIdentifier < 0
                error("InteractiveMissions:FileOpenFailed", "Could not write %s.", path);
            end
            cleanup = onCleanup(@() fclose(fileIdentifier));
            fprintf(fileIdentifier, "%s", text);
            clear cleanup
        end
    end
end

function agentClient = normalizeAgentClient(agentClient)
    agentClient = lower(strtrim(string(agentClient)));
    agentClient = regexprep(agentClient, "[^a-z0-9]+", "-");
    switch agentClient
        case {"codex", "openai-codex"}
            agentClient = "codex";
        case {"claude", "claude-code"}
            agentClient = "claude-code";
        case {"gemini", "gemini-cli"}
            agentClient = "gemini-cli";
        case {"copilot", "github-copilot", "github-copilot-vs-code", "github-copilot-vscode"}
            agentClient = "github-copilot-vscode";
        case {"github-copilot-cli", "copilot-cli", "github-copilot-terminal"}
            agentClient = "github-copilot-cli";
        case {"generic", "other", "generic-other"}
            agentClient = "generic";
        otherwise
            agentClient = "codex";
    end
end

function text = launchUiText(agentClient)
    switch normalizeAgentClient(agentClient)
        case "codex"
            text = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder.", ...
                "Step3", "Launch Codex: codex", ...
                "Step4", "Trigger the tutor skill: $mission-tutoring");
        case "claude-code"
            text = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder.", ...
                "Step3", "Launch Claude Code: claude", ...
                "Step4", "Trigger the tutor command: /mission-tutoring");
        case "gemini-cli"
            text = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder.", ...
                "Step3", "Launch Gemini CLI: gemini", ...
                "Step4", "Ask Gemini to start the mission tutoring session using GEMINI.md.");
        case "github-copilot-vscode"
            text = struct( ...
                "Step1", "Open VS Code.", ...
                "Step2", "Open the work folder.", ...
                "Step3", "Open GitHub Copilot Chat in Agent mode.", ...
                "Step4", "Run .github/prompts/mission-tutoring.prompt.md, or use /mission-tutoring if prompt commands are available.");
        case "github-copilot-cli"
            text = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder.", ...
                "Step3", "Launch your GitHub Copilot terminal workflow.", ...
                "Step4", "Ask Copilot to start the tutor using COPILOT.md.");
        case "generic"
            text = struct( ...
                "Step1", "Open your preferred terminal.", ...
                "Step2", "Navigate to the work folder.", ...
                "Step3", "Launch your code agent from that folder.", ...
                "Step4", "Ask the agent to start the mission tutoring session.");
    end
end
