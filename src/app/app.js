let htmlComponent = null;
let pendingLaunch = null;
let state = {
    RepositoryRoot: "",
    MarketplaceCacheRoot: "",
    WorkspaceRoot: "",
    AgentClient: "codex",
    Missions: [],
    Marketplaces: [],
    Sessions: [],
    LearnerFaq: { Title: "", FileName: "", Path: "", Markdown: "" },
    Documentation: { Pages: [] }
};
let currentDocumentationPage = "";
let pendingDocumentationAnchor = "";
let pendingLearnerFaqAnchor = "";
let pendingMarketplaceConfirmation = null;
let modalReturnFocus = null;
let defaultMarketplaceMessage = "";
let marketplaceRegistrationInProgress = false;
let marketplaceUnregistrationInProgress = false;

window.setup = function setup(component) {
    htmlComponent = component;

    htmlComponent.addEventListener("DataChanged", function onDataChanged() {
        applyState(htmlComponent.Data);
    });
    htmlComponent.addEventListener("stateChanged", function onStateChanged(event) {
        applyState(event.Data);
    });
    htmlComponent.addEventListener("promptReady", function onPromptReady(event) {
        const data = event.Data || {};
        const title = isLaunchAction(data.Action) ? "Launch Instructions" : "Instructions";
        showPromptModal(title, data);
    });
    htmlComponent.addEventListener("settingsSaved", function onSettingsSaved(event) {
        showToast("Settings saved: " + (event.Data.SettingsPath || ""));
    });
    htmlComponent.addEventListener("missionCacheCleared", function onMissionCacheCleared(event) {
        showToast("Cache refreshed for " + (event.Data.Title || "the selected mission") + ".");
    });
    htmlComponent.addEventListener("marketplaceRegistered", function onMarketplaceRegistered(event) {
        setMarketplaceRegistrationState(false);
        closeRegisterMarketplaceModal();
        showToast("Registered " + (event.Data.Title || "marketplace") + ".");
    });
    htmlComponent.addEventListener("marketplacesRefreshed", function onMarketplacesRefreshed() {
        showToast("Marketplaces refreshed.");
    });
    htmlComponent.addEventListener("marketplaceUpdatesAvailable", function onMarketplaceUpdatesAvailable(event) {
        const count = Number(event.Data && event.Data.Count) || 0;
        if (count > 0) {
            showToast("Updates are available for " + count + " marketplace" + (count === 1 ? "" : "s") + ". Refresh to download them.");
        }
    });
    htmlComponent.addEventListener("marketplaceUnregistered", function onMarketplaceUnregistered() {
        setMarketplaceConfirmationState(false);
        closeMarketplaceConfirmation();
        showToast("Marketplace unregistered.");
    });
    htmlComponent.addEventListener("error", function onError(event) {
        if (marketplaceRegistrationInProgress) {
            setMarketplaceRegistrationState(false, "Unable to add the marketplace. Review the message and try again.");
        }
        if (marketplaceUnregistrationInProgress) {
            setMarketplaceConfirmationState(false, "Unable to unregister the marketplace. Review the message and try again.");
        }
        const message = event.Data && event.Data.Message ? event.Data.Message : "MATLAB action failed.";
        showToast(message);
    });

    bindControls();
    send("requestState", {});
};

function bindControls() {
    document.querySelectorAll(".tab").forEach(function bindTab(button) {
        button.addEventListener("click", function onClick() {
            showView(button.dataset.view);
        });
    });

    document.getElementById("saveSettingsButton").addEventListener("click", function onClick() {
        send("saveSettings", rootsPayload());
    });
    document.getElementById("chooseWorkspaceButton").addEventListener("click", function onClick() {
        send("chooseWorkspace", rootsPayload());
    });
    document.getElementById("openRegisterMarketplaceButton").addEventListener("click", openRegisterMarketplaceModal);
    document.getElementById("closeRegisterMarketplaceButton").addEventListener("click", closeRegisterMarketplaceModal);
    document.getElementById("cancelRegisterMarketplaceButton").addEventListener("click", closeRegisterMarketplaceModal);
    document.getElementById("registerMarketplaceForm").addEventListener("submit", function onSubmit(event) {
        event.preventDefault();
        registerMarketplace();
    });
    document.getElementById("refreshMarketplacesButton").addEventListener("click", function onClick() {
        send("refreshMarketplaces", {});
    });
    document.getElementById("chooseLaunchWorkspaceButton").addEventListener("click", function onClick() {
        send("chooseLaunchWorkspace", launchRootsPayload());
    });
    document.getElementById("marketplaceReferenceType").addEventListener("change", updateMarketplaceReferenceField);
    document.getElementById("marketplaceConfirmCancel").addEventListener("click", closeMarketplaceConfirmation);
    document.getElementById("marketplaceConfirmAction").addEventListener("click", function onClick() {
        const action = pendingMarketplaceConfirmation;
        if (action) {
            if (action.keepOpen) {
                action.callback();
            } else {
                closeMarketplaceConfirmation();
                action.callback();
            }
        }
    });
    document.addEventListener("keydown", handleMarketplaceDialogKeys);
    document.getElementById("learnerFaqContent").addEventListener("click", handleMarkdownContentClick);
    document.getElementById("documentationContent").addEventListener("click", handleMarkdownContentClick);

    document.getElementById("closeLaunchSetupButton").addEventListener("click", closeLaunchModal);
    document.getElementById("cancelLaunchButton").addEventListener("click", closeLaunchModal);
    document.getElementById("continueLaunchButton").addEventListener("click", continueLaunch);
    document.getElementById("launchWorkspaceInput").addEventListener("keydown", submitOnEnter);
    document.getElementById("launchWorkspaceInput").addEventListener("input", updateLaunchContinueState);
    document.getElementById("launchAgentClientSelect").addEventListener("change", updateLaunchContinueState);

    document.getElementById("closeResumeButton").addEventListener("click", function onClick() {
        closeModal("resumeModal");
    });
    document.getElementById("dismissResumeButton").addEventListener("click", function onClick() {
        closeModal("resumeModal");
    });
    document.getElementById("closePromptButton").addEventListener("click", function onClick() {
        closeModal("promptModal");
    });
    document.getElementById("dismissPromptButton").addEventListener("click", function onClick() {
        closeModal("promptModal");
    });
    document.getElementById("copyCommandButton").addEventListener("click", function onClick() {
        copyText(document.getElementById("promptCommand").textContent);
        showToast("Command copied.");
    });
    document.getElementById("copyPromptButton").addEventListener("click", function onClick() {
        copyText(document.getElementById("promptText").value);
        showToast("Instructions copied.");
    });
}

function registerMarketplace() {
    const sourceUrl = document.getElementById("marketplaceUrlInput").value.trim();
    if (!sourceUrl) {
        showToast("Enter a repository URL.");
        return;
    }
    const payload = marketplacePayload();
    const duplicate = state.Marketplaces.find(function sameSource(marketplace) {
        return scalarText(marketplace.SourceUrl).toLowerCase() === sourceUrl.toLowerCase();
    });
    if (duplicate) {
        confirmMarketplaceAction("Replace marketplace?", "This replaces the cached marketplace after validation succeeds.", "Replace Anyway", function replace() {
            payload.ReplaceExisting = true;
            submitMarketplaceRegistration(payload);
        });
        return;
    }
    submitMarketplaceRegistration(payload);
}

function submitMarketplaceRegistration(payload) {
    setMarketplaceRegistrationState(true);
    send("registerMarketplace", payload);
}

function setMarketplaceRegistrationState(isWorking, message) {
    marketplaceRegistrationInProgress = isWorking;
    const form = document.getElementById("registerMarketplaceForm");
    form.querySelectorAll("input, select, button").forEach(function setDisabled(control) {
        control.disabled = isWorking;
    });
    const status = document.getElementById("marketplaceRegistrationStatus");
    status.hidden = false;
    status.textContent = message || (isWorking ? "Adding marketplace. This may take a few moments." : "");
    if (!isWorking && !message) {
        status.hidden = true;
    }
}

function submitOnEnter(event) {
    if (event.key === "Enter") {
        event.preventDefault();
        continueLaunch();
    }
}

function rootsPayload() {
    return {
        RepositoryRoot: document.getElementById("repositoryRootInput").value,
        WorkspaceRoot: document.getElementById("workspaceRootInput").value
    };
}

function launchRootsPayload() {
    return {
        WorkspaceRoot: document.getElementById("launchWorkspaceInput").value,
        AgentClient: document.getElementById("launchAgentClientSelect").value
    };
}

function applyState(nextState) {
    if (!nextState) {
        return;
    }

    state = nextState;
    state.Missions = toArray(state.Missions);
    state.Marketplaces = toArray(state.Marketplaces);
    state.Sessions = toArray(state.Sessions);
    if (!state.LearnerFaq) {
        state.LearnerFaq = { Title: "", FileName: "", Path: "", Markdown: "" };
    }
    if (!state.Documentation) {
        state.Documentation = { Pages: [] };
    }
    state.Documentation.Pages = toArray(state.Documentation.Pages);

    document.getElementById("repositoryRootInput").value = state.RepositoryRoot || "";
    document.getElementById("marketplaceCacheRootInput").value = state.MarketplaceCacheRoot || "";
    document.getElementById("workspaceRootInput").value = state.WorkspaceRoot || "";
    document.getElementById("launchWorkspaceInput").value = state.WorkspaceRoot || "";
    document.getElementById("launchAgentClientSelect").value = "";
    renderHeaderSummary();
    renderMissions();
    renderLearnerFaq();
    renderDocumentation();
    renderMarketplaces();
    if (state.DefaultMarketplaceMessage && state.DefaultMarketplaceMessage !== defaultMarketplaceMessage) {
        defaultMarketplaceMessage = state.DefaultMarketplaceMessage;
        showToast(defaultMarketplaceMessage);
    }
}

function renderHeaderSummary() {
    const summary = document.getElementById("identitySummary");
    summary.textContent = "Choose a mission to practice or start.";
}

function renderMissions() {
    const grid = document.getElementById("missionGrid");
    clear(grid);

    if (state.Missions.length === 0) {
        const empty = emptyMessage("No missions are available. Add a marketplace to get started.");
        empty.appendChild(actionButton("Add a Marketplace", function onClick() {
            showView("settings");
            openRegisterMarketplaceModal();
        }));
        grid.appendChild(empty);
        return;
    }

    state.Missions.forEach(function renderMission(mission) {
        const card = element("article", "mission-card");
        card.appendChild(missionThumbnail(mission));
        card.appendChild(element("h2", "", mission.Title));
        card.appendChild(element("p", "summary", mission.Summary || ""));

        const meta = element("div", "mission-meta");
        meta.appendChild(badge(mission.Difficulty || "unspecified"));
        meta.appendChild(badge(String(mission.EstimatedMinutes || "") + " min"));
        meta.appendChild(badge(String(mission.TaskCount || 0) + " tasks"));
        meta.appendChild(badge(mission.Status || "draft"));
        meta.appendChild(badge(sourceLabel(mission)));
        card.appendChild(meta);

        card.appendChild(element("p", "summary", "Topics: " + joinValues(mission.Topics)));

        const actions = element("div", "mission-actions");
        actions.appendChild(actionButton("Practice", function onClick() {
            openLaunchModal("practiceMission", mission);
        }));
        actions.appendChild(actionButton("Start Mission", function onClick() {
            openLaunchModal("startMission", mission);
        }));
        const resume = actionButton("Resume", function onClick() {
            openResumeModal(mission);
        });
        resume.disabled = !truthyValue(mission.CanResume);
        actions.appendChild(resume);
        card.appendChild(actions);

        grid.appendChild(card);
    });
}

function renderDocumentation() {
    const pages = state.Documentation.Pages;
    const navigation = documentationNavigation(pages);
    const orderedPages = navigation.Walkthrough.concat(navigation.Reference);
    const pageList = document.getElementById("documentationPageList");
    const content = document.getElementById("documentationContent");
    clear(pageList);
    clear(content);

    if (pages.length === 0) {
        pageList.appendChild(emptyMessage("No documentation pages found."));
        content.appendChild(emptyMessage("No documentation is available."));
        renderDocumentationHeadings([]);
        return;
    }

    if (!currentDocumentationPage || !orderedPages.some(function matches(page) {
        return documentationFileName(page.FileName) === currentDocumentationPage;
    })) {
        currentDocumentationPage = documentationFileName(orderedPages[0].FileName);
    }

    if (navigation.Walkthrough.length > 0) {
        appendDocumentationSectionLabel(pageList, "Walkthrough");
        renderDocumentationPageButtons(pageList, navigation.Walkthrough);
    }
    if (navigation.Reference.length > 0) {
        appendDocumentationSectionLabel(pageList, "Reference");
        renderDocumentationPageButtons(pageList, navigation.Reference);
    }

    const page = pages.find(function matches(currentPage) {
        return documentationFileName(currentPage.FileName) === currentDocumentationPage;
    }) || pages[0];
    const pageFileName = documentationFileName(page.FileName);
    const renderResult = renderMarkdown(page.Markdown || "", pageFileName);
    content.dataset.docContext = pageFileName;
    content.appendChild(renderResult.Fragment);
    renderDocumentationHeadings(renderResult.Headings);
    scrollToPendingDocumentationAnchor();
}

function renderLearnerFaq() {
    const content = document.getElementById("learnerFaqContent");
    clear(content);

    if (!scalarText(state.LearnerFaq.Markdown)) {
        content.appendChild(emptyMessage("Learner FAQ is not available."));
        renderLearnerFaqHeadings([]);
        return;
    }

    const renderResult = renderMarkdown(state.LearnerFaq.Markdown || "", learnerFaqFileName());
    content.dataset.docContext = learnerFaqFileName();
    content.appendChild(renderResult.Fragment);
    renderLearnerFaqHeadings(renderResult.Headings);
    scrollToPendingLearnerFaqAnchor();
}

function documentationNavigation(pages) {
    const walkthroughEntries = [];
    const referencePages = [];

    pages.forEach(function classifyPage(page) {
        const fileName = String(page.FileName || "");
        const walkthroughMatch = fileName.match(/^(\d+)-/);
        if (walkthroughMatch) {
            walkthroughEntries.push({
                Page: page,
                Order: Number.parseInt(walkthroughMatch[1], 10)
            });
        } else {
            referencePages.push(page);
        }
    });

    walkthroughEntries.sort(function compareWalkthrough(left, right) {
        return left.Order - right.Order ||
            String(left.Page.FileName).localeCompare(String(right.Page.FileName));
    });
    referencePages.sort(function compareReference(left, right) {
        return String(left.FileName).localeCompare(String(right.FileName));
    });

    return {
        Walkthrough: walkthroughEntries.map(function entryPage(entry) {
            return entry.Page;
        }),
        Reference: referencePages
    };
}

function appendDocumentationSectionLabel(pageList, label) {
    const className = label === "Reference" ?
        "docs-section-label docs-reference-section-label" : "docs-section-label";
    pageList.appendChild(element("div", className, label));
}

function renderDocumentationPageButtons(pageList, pages) {
    pages.forEach(function renderPageButton(page) {
        const button = element("button", "docs-nav-item", decodeHtmlEntities(firstLine(page.Title || page.FileName)));
        button.type = "button";
        button.classList.toggle("is-active", documentationFileName(page.FileName) === currentDocumentationPage);
        button.addEventListener("click", function onClick() {
            currentDocumentationPage = documentationFileName(page.FileName);
            renderDocumentation();
        });
        pageList.appendChild(button);
    });
}

function renderDocumentationHeadings(headings) {
    renderHeadingNavigation("documentationHeadingList", "documentationContent", headings);
}

function renderLearnerFaqHeadings(headings) {
    renderHeadingNavigation("learnerFaqHeadingList", "learnerFaqContent", headings);
}

function renderHeadingNavigation(listId, contentId, headings) {
    const headingList = document.getElementById(listId);
    clear(headingList);

    if (headings.length === 0) {
        headingList.appendChild(emptyMessage("No sections."));
        return;
    }

    headings.forEach(function renderHeading(heading) {
        const link = element("a", "docs-nav-item docs-depth-" + heading.Level, heading.Text);
        link.href = "#" + heading.Id;
        link.addEventListener("click", function onClick(event) {
            const target = findAnchorElement(contentId, heading.Id);
            if (target) {
                event.preventDefault();
                target.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        });
        headingList.appendChild(link);
    });
}

function missionThumbnail(mission) {
    const thumbnailSource = scalarText(mission.Thumbnail).trim();
    if (thumbnailSource) {
        const thumbnail = element("img", "mission-thumbnail");
        thumbnail.src = thumbnailSource;
        thumbnail.alt = "";
        return thumbnail;
    }

    const fallback = element("div", "mission-thumbnail mission-thumbnail-fallback");
    fallback.setAttribute("role", "img");
    fallback.setAttribute("aria-label", "Generic mission graphic");
    const iconStack = element("div", "mission-thumbnail-icon-stack");

    iconStack.appendChild(fallbackThumbnailIcon("GraduationCap"));
    iconStack.appendChild(fallbackThumbnailIcon("Matlab"));
    iconStack.appendChild(fallbackThumbnailIcon("Simulink"));
    fallback.appendChild(iconStack);
    return fallback;
}

function fallbackThumbnailIcon(name) {
    const icon = element("div", "mission-thumbnail-icon mission-thumbnail-icon-" + name.toLowerCase());
    const template = document.getElementById("fallback-thumbnail-" + name.toLowerCase());
    if (template) {
        icon.appendChild(template.content.cloneNode(true));
    }
    return icon;
}

function handleMarkdownContentClick(event) {
    const content = event.currentTarget;
    const link = event.target.closest("a");
    if (!link || !content.contains(link)) {
        return;
    }

    if (link.hasAttribute("data-web-link")) {
        event.preventDefault();
        send("openDocumentationUrl", { Url: link.getAttribute("data-web-link") || "" });
        return;
    }

    if (!link.hasAttribute("data-doc-link")) {
        return;
    }

    event.preventDefault();
    const target = documentationFileName(link.getAttribute("data-doc-link"));
    const anchor = link.getAttribute("data-doc-anchor") || "";
    if (target === learnerFaqFileName()) {
        pendingLearnerFaqAnchor = anchor;
        showView("learner-faq");
        renderLearnerFaq();
        return;
    }

    const pages = state.Documentation.Pages;
    const pageExists = pages.some(function matches(page) {
        return documentationFileName(page.FileName) === target;
    });
    if (!pageExists) {
        showToast("Documentation page not found: " + target);
        return;
    }

    pendingDocumentationAnchor = anchor;
    showView("documentation");
    if (target !== currentDocumentationPage) {
        currentDocumentationPage = target;
        renderDocumentation();
    } else {
        scrollToPendingDocumentationAnchor();
    }
}

function scrollToPendingDocumentationAnchor() {
    if (!pendingDocumentationAnchor) {
        return;
    }
    const target = findAnchorElement("documentationContent", pendingDocumentationAnchor);
    pendingDocumentationAnchor = "";
    if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function scrollToPendingLearnerFaqAnchor() {
    if (!pendingLearnerFaqAnchor) {
        return;
    }
    const target = findAnchorElement("learnerFaqContent", pendingLearnerFaqAnchor);
    pendingLearnerFaqAnchor = "";
    if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function findAnchorElement(contentId, anchorId) {
    const container = document.getElementById(contentId);
    if (!container || !anchorId) {
        return null;
    }
    return Array.from(container.querySelectorAll("[id]")).find(function matches(elementNode) {
        return elementNode.id === anchorId;
    }) || null;
}

function learnerFaqFileName() {
    return documentationFileName(state.LearnerFaq.FileName || "learner-faq.md");
}

function openLaunchModal(eventName, mission) {
    pendingLaunch = {
        EventName: eventName,
        Mission: mission
    };
    document.getElementById("launchSetupTitle").textContent = eventName === "startMission" ? "Start Mission" : "Practice Mission";
    document.getElementById("launchWorkspaceInput").value = mission.SuggestedWorkspaceRoot || state.WorkspaceRoot || "";
    document.getElementById("launchAgentClientSelect").value = "";
    updateLaunchContinueState();
    openModal("launchSetupModal");
    document.getElementById("launchWorkspaceInput").focus();
}

function closeLaunchModal() {
    pendingLaunch = null;
    updateLaunchContinueState();
    closeModal("launchSetupModal");
}

function continueLaunch() {
    updateLaunchContinueState();
    if (document.getElementById("continueLaunchButton").disabled) {
        return;
    }
    if (!pendingLaunch) {
        closeLaunchModal();
        return;
    }
    const workspaceRoot = document.getElementById("launchWorkspaceInput").value;
    if (!workspaceRoot) {
        showToast("Choose an empty work folder.");
        return;
    }
    const agentClient = document.getElementById("launchAgentClientSelect").value;
    if (!agentClient) {
        showToast("Choose an agentic client.");
        return;
    }

    const payload = {
        MissionName: pendingLaunch.Mission.MissionName,
        WorkspaceRoot: workspaceRoot,
        AgentClient: agentClient
    };
    const eventName = pendingLaunch.EventName;
    pendingLaunch = null;
    closeModal("launchSetupModal");
    send(eventName, payload);
}

function updateLaunchContinueState() {
    const button = document.getElementById("continueLaunchButton");
    if (!pendingLaunch) {
        button.disabled = true;
        return;
    }

    const workspaceRoot = document.getElementById("launchWorkspaceInput").value.trim();
    const agentClient = document.getElementById("launchAgentClientSelect").value;
    button.disabled = !workspaceRoot || !agentClient;
}

function marketplacePayload() {
    return {
        SourceUrl: document.getElementById("marketplaceUrlInput").value.trim(),
        ReferenceType: document.getElementById("marketplaceReferenceType").value,
        ReferenceName: document.getElementById("marketplaceReferenceNameInput").value.trim()
    };
}

function openRegisterMarketplaceModal() {
    setMarketplaceRegistrationState(false);
    openModal("registerMarketplaceModal");
    document.getElementById("marketplaceUrlInput").focus();
}

function closeRegisterMarketplaceModal() {
    closeModal("registerMarketplaceModal");
}

function updateMarketplaceReferenceField() {
    const referenceType = document.getElementById("marketplaceReferenceType").value;
    document.getElementById("marketplaceReferenceNameField").hidden = referenceType === "default";
    document.getElementById("marketplaceReferenceNameLabel").textContent = referenceType === "tag" ? "Tag name" : "Branch name";
}

function renderMarketplaces() {
    const rows = document.getElementById("marketplaceRows");
    clear(rows);

    if (state.Marketplaces.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 6;
        cell.textContent = "No installed marketplaces are available.";
        row.appendChild(cell);
        rows.appendChild(row);
        return;
    }

    state.Marketplaces.forEach(function renderMarketplace(marketplace) {
        const row = document.createElement("tr");
        row.appendChild(tableCell(marketplace.Title || marketplace.Source || "Marketplace"));
        row.appendChild(tableCell(marketplace.SourceUrl));
        row.appendChild(tableCell(marketplaceReference(marketplace)));
        row.appendChild(tableCell(marketplace.ContentVersion || "—"));
        row.appendChild(tableCell(String(marketplace.MissionCount || 0) + " · " + marketplaceStatus(marketplace)));

        const action = document.createElement("td");
        if (truthyValue(marketplace.IsDefault)) {
            action.textContent = "Default";
        } else {
            const button = actionButton("Unregister", function onClick() {
                confirmMarketplaceAction("Unregister marketplace?", "This removes its cached missions. Learner workspaces and progress are not affected.", "Unregister Anyway", function unregister() {
                    setMarketplaceConfirmationState(true);
                    send("unregisterMarketplace", { MarketplaceId: marketplace.Id });
                }, true);
            });
            action.appendChild(button);
        }
        row.appendChild(action);
        rows.appendChild(row);
    });
}

function marketplaceStatus(marketplace) {
    const status = scalarText(marketplace.UpdateStatus);
    if (status === "updateAvailable") {
        return "Update available";
    }
    if (status === "unavailable") {
        return "Unavailable";
    }
    return "Cached";
}

function marketplaceReference(marketplace) {
    const referenceType = scalarText(marketplace.ReferenceType).toLowerCase();
    const referenceName = scalarText(marketplace.ReferenceName);
    if (referenceType === "branch" && referenceName) {
        return "Branch: " + referenceName;
    }
    if (referenceType === "tag" && referenceName) {
        return "Tag: " + referenceName;
    }
    return "Default branch";
}

function clearMarketplaceCache(marketplace) {
    const title = marketplace.Title || "this marketplace";
    const message = "Clear the marketplace cache for " + title +
        "? The app will rebuild it. Learner workspaces and progress are not affected.";
    if (window.confirm(message)) {
        send("clearMissionCache", {
            MissionPath: marketplace.MissionPath,
            SourceRoot: marketplace.SourceRoot,
            Title: marketplace.Title
        });
    }
}

function openResumeModal(mission) {
    const rows = document.getElementById("resumeRows");
    clear(rows);
    let sessions = indexedResumeSession(mission);
    if (sessions.length === 0) {
        sessions = state.Sessions.filter(function matchesMission(session) {
            return sessionMatchesMission(session, mission) && truthyValue(session.IsResumable);
        });
    }
    if (sessions.length === 0 && truthyValue(mission.CanResume)) {
        const resumableSessions = state.Sessions.filter(function isResumable(session) {
            return truthyValue(session.IsResumable);
        });
        if (resumableSessions.length === 1) {
            sessions = resumableSessions;
        }
    }
    if (sessions.length === 0 && truthyValue(mission.CanResume) && scalarText(mission.ProgressIndex)) {
        sessions = [fallbackResumeSession(mission)];
    }

    if (sessions.length === 0) {
        rows.appendChild(emptyMessage("No in-progress sessions are available for this mission."));
    }

    sessions.forEach(function renderSession(session) {
        const row = element("div", "data-row");
        const content = element("div");
        content.appendChild(element("div", "row-title", (session.Username || "Awaiting learner name") + " - " + (session.CurrentTask || "not started")));
        content.appendChild(element("div", "row-subtitle", session.WorkspaceRoot || ""));
        content.appendChild(element("div", "row-subtitle", resumeLabels(session).join(" | ")));
        if (session.Notes) {
            content.appendChild(element("div", "row-subtitle", session.Notes));
        }
        row.appendChild(content);

        const button = element("button", "primary", "Resume");
        button.addEventListener("click", function onClick() {
            closeModal("resumeModal");
            send("resumeMission", {
                MissionName: mission.MissionName,
                SessionIndex: session.Index
            });
        });
        row.appendChild(button);
        rows.appendChild(row);
    });
    openModal("resumeModal");
}

function fallbackResumeSession(mission) {
    return {
        Index: scalarText(mission.ProgressIndex),
        MissionName: mission.MissionName,
        MissionId: mission.MissionId,
        Username: "saved progress",
        CurrentTask: "resume point",
        WorkspaceRoot: "",
        CompletedCount: "",
        LastSession: "",
        ProgressPath: "",
        IsResumable: true
    };
}

function indexedResumeSession(mission) {
    const progressIndex = scalarText(mission.ProgressIndex);
    if (!progressIndex) {
        return [];
    }

    return state.Sessions.filter(function hasProgressIndex(session) {
        return scalarText(session.Index) === progressIndex && truthyValue(session.IsResumable);
    });
}

function sessionMatchesMission(session, mission) {
    const sessionMissionName = scalarText(session.MissionName);
    const sessionMissionId = scalarText(session.MissionId);
    const missionName = scalarText(mission.MissionName);
    const missionId = scalarText(mission.MissionId);
    const legacyId = scalarText(mission.LegacyId);
    const sessionIndex = scalarText(session.Index);
    const progressIndex = scalarText(mission.ProgressIndex);

    return sessionMissionName === missionName ||
        sessionMissionId === missionId ||
        sessionMissionId === legacyId ||
        (progressIndex && sessionIndex === progressIndex);
}

function resumeLabels(session) {
    const labels = [
        session.LastSession || session.LastSeenAt || "no session date",
        session.ProgressPath || "progress pending"
    ];
    if (session.CompletedCount !== "") {
        labels.unshift(session.CompletedCount + " complete");
    }
    return labels.filter(Boolean);
}

function showView(viewName) {
    const normalizedViewName = String(viewName || "").replace(/-([a-z])/g, function toCamelCase(match, character) {
        return character.toUpperCase();
    });
    document.querySelectorAll(".tab").forEach(function updateTab(button) {
        button.classList.toggle("is-active", button.dataset.view === viewName);
        button.setAttribute("aria-selected", button.dataset.view === viewName ? "true" : "false");
    });
    document.querySelectorAll(".view").forEach(function updateView(view) {
        view.classList.toggle("is-active", view.id === viewName + "View" || view.id === normalizedViewName + "View");
    });
}

function showPromptModal(title, data) {
    const launchAction = isLaunchAction(data.Action);
    const command = data.Command || "";
    const showCommand = launchAction && isCdCommand(command);

    document.getElementById("promptTitle").textContent = title;
    document.getElementById("promptCommand").textContent = showCommand ? command : "";
    document.getElementById("promptStep1Text").textContent = data.Step1Text || "Open your preferred terminal.";
    document.getElementById("promptStep2Text").textContent = data.Step2Text || "Navigate to the work folder.";
    document.getElementById("promptStep3Text").textContent = data.Step3Text || "Launch your code agent.";
    document.getElementById("promptStep4Text").textContent = data.Step4Text || "$mission-tutoring";
    document.querySelector("#promptModal .launch-steps").hidden = !launchAction;
    document.querySelector("#promptModal .copy-row").hidden = !showCommand;

    if (launchAction) {
        document.getElementById("promptContextField").hidden = true;
        document.getElementById("promptText").value = launchInstructionText(data, showCommand ? command : "");
    } else {
        document.getElementById("promptContextField").hidden = false;
        document.getElementById("promptText").value = data.Prompt || command || "";
    }
    openModal("promptModal");
}

function isLaunchAction(action) {
    return ["start", "practice", "resume"].includes(String(action || ""));
}

function isCdCommand(command) {
    return /^(cd|code)(\s|$)/i.test(String(command || "").trim());
}

function launchInstructionText(data, command) {
    const lines = [
        "Step 1: " + (data.Step1Text || "Open your preferred terminal."),
        "Step 2: " + (data.Step2Text || "Navigate to the work folder.")
    ];
    if (command) {
        lines.push(command);
    }
    lines.push("Step 3: " + (data.Step3Text || "Launch your code agent."));
    lines.push("Step 4: " + (data.Step4Text || "$mission-tutoring"));
    return lines.join("\n\n");
}

function openModal(modalId) {
    modalReturnFocus = document.activeElement;
    document.getElementById(modalId).hidden = false;
    const first = document.getElementById(modalId).querySelector("button, input, select, textarea");
    if (first) {
        first.focus();
    }
}

function closeModal(modalId) {
    document.getElementById(modalId).hidden = true;
    if (modalReturnFocus && typeof modalReturnFocus.focus === "function") {
        modalReturnFocus.focus();
    }
}

function confirmMarketplaceAction(title, message, actionLabel, action, keepOpen) {
    pendingMarketplaceConfirmation = {
        callback: action,
        keepOpen: Boolean(keepOpen)
    };
    document.getElementById("marketplaceConfirmTitle").textContent = title;
    document.getElementById("marketplaceConfirmMessage").textContent = message;
    document.getElementById("marketplaceConfirmAction").textContent = actionLabel;
    setMarketplaceConfirmationState(false);
    openModal("marketplaceConfirmModal");
}

function closeMarketplaceConfirmation() {
    pendingMarketplaceConfirmation = null;
    closeModal("marketplaceConfirmModal");
}

function setMarketplaceConfirmationState(isWorking, message) {
    marketplaceUnregistrationInProgress = isWorking;
    const modal = document.getElementById("marketplaceConfirmModal");
    modal.querySelectorAll("button").forEach(function setDisabled(button) {
        button.disabled = isWorking;
    });
    const status = document.getElementById("marketplaceConfirmStatus");
    status.hidden = !isWorking && !message;
    status.textContent = message || (isWorking ? "Unregistering marketplace. This may take a few moments." : "");
}

function handleMarketplaceDialogKeys(event) {
    const registerModal = document.getElementById("registerMarketplaceModal");
    if (!registerModal.hidden && event.key === "Escape") {
        event.preventDefault();
        closeRegisterMarketplaceModal();
        return;
    }
    const modal = document.getElementById("marketplaceConfirmModal");
    if (modal.hidden) {
        return;
    }
    if (event.key === "Escape") {
        event.preventDefault();
        closeMarketplaceConfirmation();
    }
    if (event.key === "Tab") {
        const buttons = Array.from(modal.querySelectorAll("button:not([disabled])"));
        const current = buttons.indexOf(document.activeElement);
        if (event.shiftKey && current === 0) {
            event.preventDefault();
            buttons[buttons.length - 1].focus();
        } else if (!event.shiftKey && current === buttons.length - 1) {
            event.preventDefault();
            buttons[0].focus();
        }
    }
}

function actionButton(label, onClick) {
    const button = element("button", "", label);
    button.addEventListener("click", onClick);
    return button;
}

function tableCell(text) {
    const cell = document.createElement("td");
    cell.textContent = text;
    return cell;
}

function tableLinkCell(url) {
    const cell = document.createElement("td");
    const sourceUrl = scalarText(url);
    if (!sourceUrl) {
        cell.textContent = "—";
        return cell;
    }

    const link = document.createElement("a");
    link.href = sourceUrl;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = sourceUrl;
    cell.appendChild(link);
    return cell;
}

function send(eventName, payload) {
    if (!htmlComponent) {
        return;
    }
    htmlComponent.sendEventToMATLAB(eventName, payload || {});
}

function showToast(message) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(showToast.timeoutId);
    showToast.timeoutId = window.setTimeout(function hideToast() {
        toast.hidden = true;
    }, 5000);
}

function copyText(text) {
    const textArea = document.createElement("textarea");
    textArea.value = text || "";
    textArea.setAttribute("readonly", "");
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    document.execCommand("copy");
    document.body.removeChild(textArea);
}

function badge(text) {
    return element("span", "badge", text);
}

function emptyMessage(text) {
    return element("div", "empty", text);
}

function clear(node) {
    while (node.firstChild) {
        node.removeChild(node.firstChild);
    }
}

function element(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) {
        node.className = className;
    }
    if (text !== undefined) {
        node.textContent = text;
    }
    return node;
}

function renderMarkdown(markdown, contextFileName) {
    const fragment = document.createDocumentFragment();
    const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
    const headings = [];
    let index = 0;
    let paragraph = [];

    function flushParagraph() {
        if (paragraph.length === 0) {
            return;
        }
        const paragraphNode = element("p", "");
        paragraphNode.innerHTML = inlineMarkdown(paragraph.join(" "), contextFileName);
        fragment.appendChild(paragraphNode);
        paragraph = [];
    }

    while (index < lines.length) {
        const line = lines[index];
        const trimmed = line.trim();

        if (trimmed === "") {
            flushParagraph();
            index += 1;
            continue;
        }

        const fenceMatch = trimmed.match(/^```(\w+)?/);
        if (fenceMatch) {
            flushParagraph();
            const codeLines = [];
            index += 1;
            while (index < lines.length && !lines[index].trim().startsWith("```")) {
                codeLines.push(lines[index]);
                index += 1;
            }
            if (index < lines.length) {
                index += 1;
            }
            const pre = element("pre", "");
            const code = element("code", fenceMatch[1] ? "language-" + fenceMatch[1] : "");
            code.textContent = codeLines.join("\n");
            pre.appendChild(code);
            fragment.appendChild(pre);
            continue;
        }

        const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
        if (headingMatch) {
            flushParagraph();
            const level = headingMatch[1].length;
            const text = stripInlineMarkdown(headingMatch[2]);
            const id = uniqueHeadingId(slugify(text), headings);
            const heading = element("h" + level, "", text);
            heading.id = id;
            headings.push({ Id: id, Text: text, Level: level });
            fragment.appendChild(heading);
            index += 1;
            continue;
        }

        const tableDefinition = markdownTableDefinition(lines, index);
        if (tableDefinition) {
            flushParagraph();
            const tableWrap = element("div", "docs-table-wrap");
            const table = element("table", "docs-table");
            const tableHead = element("thead", "");
            const headerRow = element("tr", "");
            tableDefinition.Headers.forEach(function appendHeaderCell(header, columnIndex) {
                const headerCell = element("th", "");
                headerCell.scope = "col";
                headerCell.style.textAlign = tableDefinition.Alignments[columnIndex];
                headerCell.innerHTML = inlineMarkdown(header, contextFileName);
                headerRow.appendChild(headerCell);
            });
            tableHead.appendChild(headerRow);
            table.appendChild(tableHead);

            const tableBody = element("tbody", "");
            index += 2;
            while (index < lines.length) {
                const cells = markdownTableRow(lines[index]);
                if (!cells || cells.length !== tableDefinition.Headers.length) {
                    break;
                }
                const bodyRow = element("tr", "");
                cells.forEach(function appendBodyCell(cellText, columnIndex) {
                    const bodyCell = element("td", "");
                    bodyCell.style.textAlign = tableDefinition.Alignments[columnIndex];
                    bodyCell.innerHTML = inlineMarkdown(cellText, contextFileName);
                    bodyRow.appendChild(bodyCell);
                });
                tableBody.appendChild(bodyRow);
                index += 1;
            }
            table.appendChild(tableBody);
            tableWrap.appendChild(table);
            fragment.appendChild(tableWrap);
            continue;
        }

        if (/^>\s?/.test(trimmed)) {
            flushParagraph();
            const quoteLines = [];
            while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
                quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
                index += 1;
            }
            const blockquote = element("blockquote", "");
            blockquote.innerHTML = inlineMarkdown(quoteLines.join(" "), contextFileName);
            fragment.appendChild(blockquote);
            continue;
        }

        if (/^-\s+/.test(trimmed)) {
            flushParagraph();
            const list = element("ul", "");
            while (index < lines.length && /^-\s+/.test(lines[index].trim())) {
                const item = element("li", "");
                item.innerHTML = inlineMarkdown(lines[index].trim().replace(/^-\s+/, ""), contextFileName);
                list.appendChild(item);
                index += 1;
            }
            fragment.appendChild(list);
            continue;
        }

        if (/^\d+\.\s+/.test(trimmed)) {
            flushParagraph();
            const list = element("ol", "");
            while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
                const item = element("li", "");
                item.innerHTML = inlineMarkdown(lines[index].trim().replace(/^\d+\.\s+/, ""), contextFileName);
                list.appendChild(item);
                index += 1;
            }
            fragment.appendChild(list);
            continue;
        }

        paragraph.push(trimmed);
        index += 1;
    }

    flushParagraph();
    return { Fragment: fragment, Headings: headings };
}

function inlineMarkdown(text, contextFileName) {
    const tokens = [];
    let markdown = decodeHtmlEntities(text);

    function saveToken(html) {
        const token = "\uE000" + tokens.length + "\uE001";
        tokens.push(html);
        return token;
    }

    markdown = markdown.replace(/`([^`]+)`/g, function replaceCode(match, code) {
        return saveToken("<code>" + escapeHtml(code) + "</code>");
    });
    markdown = markdown.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function replaceLink(match, label, href) {
        const link = documentationLinkTarget(href, contextFileName);
        const safeLabel = escapedLinkLabel(label);
        if (link.IsInternal) {
            return saveToken("<a href=\"" + escapeAttribute(link.Href) + "\" data-doc-link=\"" +
                escapeAttribute(link.FileName) + "\" data-doc-anchor=\"" +
                escapeAttribute(link.Anchor) + "\">" + safeLabel + "</a>");
        }
        if (link.IsWeb) {
            return saveToken("<a href=\"" + escapeAttribute(link.Href) + "\" data-web-link=\"" +
                escapeAttribute(link.Href) + "\">" + safeLabel + "</a>");
        }
        return saveToken(safeLabel);
    });
    let html = escapeHtml(markdown);
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    tokens.forEach(function restoreToken(token, index) {
        html = html.replace("\uE000" + index + "\uE001", token);
    });
    return html;
}

function escapedLinkLabel(label) {
    const safeLabel = escapeHtml(label);
    return safeLabel;
}

function markdownTableDefinition(lines, index) {
    const headers = markdownTableRow(lines[index]);
    const delimiters = markdownTableRow(lines[index + 1]);
    if (!headers || !delimiters || headers.length !== delimiters.length) {
        return null;
    }

    const alignments = delimiters.map(function tableAlignment(delimiter) {
        if (!/^:?-{3,}:?$/.test(delimiter)) {
            return "";
        }
        if (delimiter.startsWith(":") && delimiter.endsWith(":")) {
            return "center";
        }
        if (delimiter.endsWith(":")) {
            return "right";
        }
        return "left";
    });
    if (alignments.some(function invalidAlignment(alignment) {
        return alignment === "";
    })) {
        return null;
    }
    return { Headers: headers, Alignments: alignments };
}

function markdownTableRow(line) {
    const trimmed = String(line || "").trim();
    if (!trimmed.includes("|")) {
        return null;
    }
    const content = trimmed.replace(/^\|/, "").replace(/\|$/, "");
    const cells = content.split("|").map(function trimCell(cell) {
        return cell.trim();
    });
    return cells.length > 1 ? cells : null;
}

function documentationLinkTarget(href, contextFileName) {
    const rawHref = String(href || "").trim();
    if (/^https?:\/\/\S+$/i.test(rawHref)) {
        return {
            IsInternal: false,
            IsWeb: true,
            FileName: "",
            Anchor: "",
            Href: rawHref
        };
    }
    const parts = rawHref.split("#");
    let path = documentationFileName(parts[0]);
    const anchor = parts.length > 1 ? slugify(decodeURIComponent(parts.slice(1).join("#"))) : "";

    if (path === "") {
        return {
            IsInternal: true,
            IsWeb: false,
            FileName: documentationFileName(contextFileName) || currentDocumentationPage,
            Anchor: anchor,
            Href: "#" + anchor
        };
    }

    if (path.startsWith("docs/")) {
        path = path.slice(5);
    }

    if (/^[a-z0-9._-]+\.md$/i.test(path)) {
        return {
            IsInternal: true,
            IsWeb: false,
            FileName: path,
            Anchor: anchor,
            Href: "#" + path + (anchor ? "#" + anchor : "")
        };
    }

    return {
        IsInternal: false,
        IsWeb: false,
        FileName: "",
        Anchor: "",
        Href: rawHref
    };
}

function stripInlineMarkdown(text) {
    const plainText = String(text || "")
        .replace(/`([^`]+)`/g, "$1")
        .replace(/\*\*([^*]+)\*\*/g, "$1")
        .replace(/\*([^*]+)\*/g, "$1")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
    return decodeHtmlEntities(plainText);
}

function documentationFileName(value) {
    return String(value || "").trim().replace(/\\/g, "/").replace(/^\.\//, "").replace(/^src\/docs\//i, "").replace(/^docs\//i, "");
}

function uniqueHeadingId(baseId, headings) {
    let id = baseId || "section";
    let suffix = 2;
    while (headings.some(function hasHeading(heading) {
        return heading.Id === id;
    })) {
        id = baseId + "-" + suffix;
        suffix += 1;
    }
    return id;
}

function slugify(text) {
    return String(text || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

function escapeHtml(text) {
    return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function decodeHtmlEntities(text) {
    const decoder = document.createElement("textarea");
    decoder.innerHTML = String(text || "");
    return decoder.value;
}

function escapeAttribute(text) {
    return escapeHtml(text).replace(/`/g, "&#96;");
}

function joinValues(value) {
    return toArray(value).filter(Boolean).join(", ");
}

function sourceLabel(mission) {
    return mission.MarketplaceTitle || mission.MarketplaceSource || "Marketplace";
}

function firstLine(text) {
    return String(text || "").split(/\r?\n/).find(function hasText(line) {
        return line.trim().length > 0;
    }) || "";
}

function toArray(value) {
    if (value === undefined || value === null) {
        return [];
    }
    return Array.isArray(value) ? value : [value];
}

function scalarText(value) {
    if (Array.isArray(value)) {
        return scalarText(value[0]);
    }
    if (value === undefined || value === null) {
        return "";
    }
    return String(value);
}

function truthyValue(value) {
    if (Array.isArray(value)) {
        return truthyValue(value[0]);
    }
    if (typeof value === "string") {
        return ["true", "1", "yes"].includes(value.toLowerCase());
    }
    return Boolean(value);
}
