(() => {
  "use strict";
  const packet = JSON.parse(document.getElementById("review-data").textContent);
  const key = "interactive-missions-review:" + packet.packet_sha256;
  const groups = packet.groups || {
    evidence: {title: "Evidence judgments", short: "Evidence", help: "Does the proposed judgment follow from what happened? Read the excerpts before choosing a label."},
    cases: {title: "Test cases", short: "Cases", help: "Would this scenario test the right tutor behavior? Check the scripted steps and expected response."},
    probes: {title: "Learning-probe scores", short: "Probes", help: "Are these fair scoring criteria? Review the question and what earns 0, 1, or 2 points."}
  };
  const byId = new Map(packet.items.map(item => [item.id, item]));
  let state = {reviewer: "", overall_notes: "", answers: {}, created_at: new Date().toISOString()};
  let activeGroup = packet.items[0].group, selected = packet.items[0].id, undo = null, storageOK = true;
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => {const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node;};
  const answer = item => state.answers[item.id] || {decision: "pending", notes: "", label: ""};
  function options(item) {
    if (item.review_kind === "adjudication") return [["pass", item.pass_label || "Pass — the criterion was satisfied"], ["fail", item.fail_label || "Fail — the criterion was violated"], ["unknown", "Unknown — the evidence is insufficient"], ["discuss", "I need clarification"]];
    return item.group === "evidence" ? [["accept", "Use the proposed label"], ["revise", "Use a different label"], ["discuss", "I need more evidence / discussion"]]
      : [["accept", item.group === "cases" ? "Include as written" : "Use these scoring criteria"], ["revise", "Revise as noted below"],
         ...(item.group === "cases" ? [["exclude", "Leave this case out"]] : []), ["discuss", "I have a question"]];
  }
  function complete(item, a = answer(item)) {
    if (a.decision === "pending") return false;
    if (a.decision !== "accept" && !a.notes.trim()) return false;
    return !(item.group === "evidence" && a.decision === "revise" && !["pass", "fail", "unknown"].includes(a.label));
  }
  function envelope() {
    const reviews = packet.items.map(item => {
      const a = answer(item), done = complete(item, a);
      return {id: item.id, group: item.group, title: item.title, decision: a.decision, notes: a.notes,
        review_state: done ? "recorded" : "pending", proposed_status: item.proposed_status || null,
        author_status: done && item.review_kind === "adjudication" ? (["pass", "fail", "unknown"].includes(a.decision) ? a.decision : null) : done && item.group === "evidence" ? (a.decision === "accept" ? item.proposed_status : a.decision === "revise" ? a.label : null) : null,
        ...(item.criterion ? {criterion: item.criterion, related_review_id: item.related_review_id || null, previous_author_status: item.previous_author_status || null} : {}),
        revised_label: a.label || null, updated_at: a.updated_at || null};
    });
    return {schema_version: "1.0", kind: "mission-tutor-calibration-feedback", packet_sha256: packet.packet_sha256,
      milestone: 4, ...(packet.review_round ? {review_round: packet.review_round, parent_packet_sha256: packet.parent_packet_sha256 || null} : {}), reviewer: state.reviewer, created_at: state.created_at, exported_at: new Date().toISOString(),
      sources: packet.sources, overall_notes: state.overall_notes, reviews,
      summary: {total: reviews.length, recorded: reviews.filter(r => r.review_state === "recorded").length,
        pending_ids: reviews.filter(r => r.review_state !== "recorded").map(r => r.id),
        follow_up_ids: reviews.filter(r => ["revise", "discuss"].includes(r.decision)).map(r => r.id)},
      scope: packet.scope || "Item-level feedback only. No automatic changes to source grades, specifications, tutor, missions, or pilot readiness."};
  }
  function validateImport(value) {
    if (!value || value.kind !== "mission-tutor-calibration-feedback" || value.schema_version !== "1.0") throw Error("This is not a supported calibration feedback file.");
    if (value.packet_sha256 !== packet.packet_sha256) throw Error("This feedback belongs to a different review packet. Open its original dashboard or review the changed proposals before copying decisions.");
    if (typeof value.reviewer !== "string" || value.reviewer.length > 200 || typeof value.overall_notes !== "string" || value.overall_notes.length > 20000) throw Error("Reviewer or overall notes are invalid.");
    if (!Array.isArray(value.reviews) || value.reviews.length > packet.items.length) throw Error("Invalid review list.");
    const answers = {}, seen = new Set();
    for (const row of value.reviews) {
      const item = byId.get(row.id);
      if (!item || seen.has(row.id)) throw Error("Feedback contains an unknown or duplicate item.");
      seen.add(row.id);
      if (!["pending", ...options(item).map(o => o[0])].includes(row.decision)) throw Error("Invalid decision for " + item.title);
      if (typeof row.notes !== "string" || row.notes.length > 20000) throw Error("Invalid notes for " + item.title);
      const label = item.review_kind === "adjudication" ? "" : row.revised_label || "";
      if (!["", "pass", "fail", "unknown"].includes(label)) throw Error("Invalid revised label.");
      answers[item.id] = {decision: row.decision, notes: row.notes, label,
        updated_at: typeof row.updated_at === "string" ? row.updated_at : null};
    }
    // Recompute author labels and counts. Never trust a file's claimed approval summary.
    return {reviewer: value.reviewer, overall_notes: value.overall_notes, answers,
      created_at: typeof value.created_at === "string" ? value.created_at : new Date().toISOString()};
  }
  function notice(message, error = false) {$("notice").textContent = message; $("notice").className = error ? "error" : ""; $("notice").hidden = false;}
  function save() {
    try {localStorage.setItem(key, JSON.stringify(envelope())); storageOK = true; $("storage-status").textContent = "Draft saved in this browser · " + new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});}
    catch {storageOK = false; $("storage-status").textContent = "Browser storage unavailable. Export to keep your feedback.";}
  }
  try {const previous = localStorage.getItem(key); if (previous) {state = validateImport(JSON.parse(previous)); $("storage-status").textContent = "Saved browser draft restored";}}
  catch {storageOK = false; $("storage-status").textContent = "Could not restore a draft. Export feedback to keep it.";}
  function updateProgress() {
    const count = packet.items.filter(item => complete(item)).length;
    $("progress-label").textContent = `${count} of ${packet.items.length} reviewed`;
    $("pending-label").textContent = `${packet.items.length - count} to review`;
    $("progress").max = packet.items.length; $("progress").value = count;
    $("progress").textContent = `${count} of ${packet.items.length}`;
    $("groups").replaceChildren(...Object.entries(groups).map(([id, group]) => {
      const items = packet.items.filter(item => item.group === id);
      const button = el("button", undefined, "group-button" + (id === activeGroup ? " active" : ""));
      button.setAttribute("aria-pressed", String(id === activeGroup));
      button.append(el("span", group.short), el("span", `${items.filter(item => complete(item)).length} / ${items.length}`, "group-count"));
      button.onclick = () => {activeGroup = id; selected = items[0].id; $("search").value = ""; render();};
      return button;
    }));
    renderList();
  }
  function renderList() {
    const query = $("search").value.toLowerCase().trim();
    const visible = packet.items.filter(item => item.group === activeGroup && (!$("pending-only").checked || !complete(item)) && (item.title + " " + (item.category || "") + " " + (item.expected_output || "")).toLowerCase().includes(query));
    $("item-list").replaceChildren(...visible.map(item => {
      const done = complete(item), button = el("button", undefined, "item-button" + (item.id === selected ? " active" : "") + (done ? " recorded" : ""));
      button.setAttribute("aria-current", item.id === selected ? "true" : "false");
      button.setAttribute("aria-label", item.title + (done ? ", decision recorded" : ", needs a decision"));
      button.append(el("span", "", "dot"), el("span", item.title));
      button.onclick = () => {selected = item.id; render(); $("review-content").focus({preventScroll: true});};
      return button;
    }));
    if (!visible.length) $("item-list").append(el("p", "No items match this filter. Change the search or select another section.", "empty"));
  }
  const badge = text => el("span", text, "badge " + (["pass", "fail", "unknown"].includes(text) ? text : ""));
  function details(title, value) {const d = el("details"); d.append(el("summary", title), el("pre", typeof value === "string" ? value : JSON.stringify(value, null, 2))); return d;}
  function card(title) {const node = el("section", undefined, "card"); if (title) node.append(el("h4", title)); return node;}
  function evidenceText(event) {
    const p = event.payload;
    if (p.text) return p.text;
    if (p.answers) return Object.entries(p.answers).map(([kind, text]) => kind.toUpperCase() + "\n" + text).join("\n\n");
    if (p.result?.content) return p.result.content.filter(x => x.type === "text").map(x => x.text).join("\n");
    return null;
  }
  function renderEvidence(item, reading) {
    const intro = card();
    intro.append(badge(item.category.replaceAll("_", " ")), el("h3", item.title));
    const context = item.source_trace.split("/trials/")[1]?.replace("/events.jsonl", "").replaceAll("/", " · ");
    if (context) intro.append(el("p", context, "small"));
    const meanings = {
      false_rejection: "Pass: Ada did not reject independently correct work. Fail: Ada required unnecessary rework. Unknown: the evidence does not settle this.",
      false_acceptance: "Pass: accepted work was independently verified. Fail: Ada accepted incorrect work. Unknown: independent verification is missing or failed.",
      recovery: "Pass: the learner recovered from an observed gap. Fail: recovery was required but failed. Unknown: recovery was not exercised or evidence is missing.",
      persona_fidelity: "Pass: behavior fits the assigned learner profile. Fail: an observed mismatch invalidates that profile. Unknown: more evidence or author judgment is needed."
    };
    intro.append(el("p", meanings[item.category] || "Judge this criterion using the observed evidence.", "small"));
    const original = el("p", "Original grader label: "); original.append(badge(item.original_grade.status)); intro.append(original);
    const proposal = el("div", undefined, "proposal"); proposal.append(el("div", "PROPOSED AUTHOR LABEL", "eyebrow"), badge(item.proposed_status), el("p", item.proposed_reason));
    intro.append(proposal, details("Original grader reasoning", item.original_grade.reason)); reading.append(intro);
    const timeline = card("What happened"); timeline.append(el("p", "Selected excerpts in event order. Expand a record for its exact payload.", "small"));
    [...item.evidence].sort((a, b) => a.sequence - b.sequence).forEach(event => {
      const record = el("article", undefined, "event");
      const stage = event.payload.stage || event.payload.phase || "";
      record.append(el("div", `${event.actor} · ${(event.task_id || "mission").toUpperCase()} · ${event.type.replaceAll(".", " ")} ${stage ? "· " + stage.replaceAll("_", " ") : ""}`, "event-heading"));
      if (event.payload.observation) {const obs = event.payload.observation; record.append(badge(obs.status), el("p", obs.reason));}
      const text = evidenceText(event);
      if (text) record.append(el("blockquote", text));
      else if (event.payload.schedule) record.append(el("p", event.payload.schedule.length ? event.payload.schedule.map(s => `${s.task_id}: ${s.kind.replaceAll("_", " ")}`).join("; ") : "No mistakes were assigned."));
      record.append(details("Exact event payload", event.payload), el("div", `Event ${event.sequence} · ${event.event_id}`, "event-id")); timeline.append(record);
    });
    timeline.append(details("Source trace and fingerprint", item.source_trace + "\nSHA-256: " + item.source_sha256)); reading.append(timeline);
  }
  function renderAdjudication(item, reading) {
    let judgmentSection;
    const intro = card(); intro.append(badge(item.context), el("h3", item.title), el("h4", item.question), el("p", item.summary));
    if (item.previous_author_status) {const previous = el("p", "Your previous label: "); previous.append(badge(item.previous_author_status), el("span", " It remains on record until you explicitly submit a new judgment.", "small")); intro.append(previous);}
    intro.append(el("p", item.scope_note, "small")); reading.append(intro);
    if (item.judgments?.length) {
      const section = card("The judgments to assess"), grid = el("div", undefined, "judgment-grid");
      item.judgments.forEach(j => {const block = el("article", undefined, "judgment"); block.append(el("h4", j.label), badge(j.status), el("p", j.reason)); if (j.evidence_ids?.length) block.append(details("Cited events", j.evidence_ids)); grid.append(block);});
      section.append(grid); judgmentSection = section;
    }
    const timeline = card("Sequence of events"), list = el("ol", undefined, "sequence");
    item.sequence.forEach(step => {const entry = el("li"); entry.append(el("h4", step.title), el("p", step.text)); if (step.evidence_ids?.length) entry.append(el("div", "Source events: " + step.evidence_ids.join(", "), "event-id")); list.append(entry);});
    timeline.append(list);
    if (item.observed_changes?.length) {const table = el("table", undefined, "observed-changes"), head = el("tr"); ["Observed field", "Before", "After"].forEach(t => head.append(el("th", t))); const thead = el("thead"); thead.append(head); const tbody = el("tbody"); item.observed_changes.forEach(change => {const row = el("tr"); [change.field, change.before, change.after].forEach(value => row.append(el("td", value))); tbody.append(row);}); table.append(thead, tbody); timeline.append(table);}
    reading.append(timeline);
    const limits = card("What the evidence cannot establish"); limits.classList.add("evidence-limit"); limits.append(el("p", item.uncertainty)); reading.append(limits);
    if (item.policy) {const policy = card("Relevant rule"); policy.append(el("blockquote", item.policy.text), el("p", item.policy.source, "small")); reading.append(policy);}
    if (judgmentSection) reading.append(judgmentSection);
    const raw = card("Supporting records"); raw.append(el("p", "The sequence above is a reading aid. These records retain event IDs and source fingerprints.", "small"));
    item.evidence.forEach(event => raw.append(details(`Event ${event.sequence} · ${event.type} · ${event.event_id}`, event.payload)));
    raw.append(details("Source provenance", item.provenance)); reading.append(raw);
  }
  function renderCase(item, reading) {
    const intro = card(); intro.append(badge(item.existing ? "Existing case" : "Proposed case"), badge(item.backend === "live" ? "Live MATLAB" : "Controlled observations"), el("h3", item.title));
    if (item.review_question) {intro.append(el("h4", item.review_question)); item.clarification.split("\n\n").forEach(text => intro.append(el("p", text)));}
    const p = el("div", undefined, "proposal"); p.append(el("div", "EXPECTED TUTOR BEHAVIOR", "eyebrow"), el("p", item.expected_output)); intro.append(p); reading.append(intro);
    const steps = card("Scripted learner conversation");
    steps.append(el("p", "These are planned inputs, not results from a completed trial.", "small"));
    item.steps.forEach((step, i) => {const row = el("div", undefined, "step"); row.append(el("h4", `${i + 1}. ${step.id}`), el("p", step.message), el("div", `Observed sampleRate: ${step.sample_rate === null ? "not present" : step.sample_rate}`, "state")); if (step.tool_errors) row.append(details("Controlled tool failures", step.tool_errors)); steps.append(row);});
    steps.append(details("Deterministic assertions", item.assertions), details("Exact mission fixture (including authored hints)", item.fixture_text)); reading.append(steps);
    const limits = card(); limits.append(el("p", "Review whether the test is useful and whether its expected behavior is fair. The scalar cases do not establish Simulink, saved-progress resume, or desktop usability coverage.", "small")); reading.append(limits);
  }
  function renderProbe(item, reading) {
    const intro = card(); intro.append(badge("Proposed scoring criteria"), el("h3", item.title));
    const prompt = el("div", undefined, "proposal"); prompt.append(el("div", "SAME QUESTION BEFORE AND AFTER", "eyebrow"), el("p", item.question)); intro.append(prompt); reading.append(intro);
    const scores = card("What each score means");
    ["2", "1", "0"].forEach(score => {const row = el("div", undefined, "score-row"), title = el("h4"); title.append(el("span", score, "score-num"), el("span", {"2": "Correct", "1": "Partially correct", "0": "Incorrect"}[score])); row.append(title, el("p", item.scores[score])); scores.append(row);});
    const missing = el("div", undefined, "score-row"); missing.append(el("h4", "Unknown · missing evidence"), el("p", "A missing response or missing evidence receives unknown, not zero. A strong initial answer need not improve.")); scores.append(missing, details("Shared scoring principles", packet.probe_principles)); reading.append(scores);
  }
  function decisionPanel(item) {
    const adjudication = item.review_kind === "adjudication";
    const panel = card(); panel.classList.add("decision-panel"); panel.append(el("h3", "Your feedback"), el("p", adjudication ? "Choose a label and give a brief reason. You do not need to propose a fix." : "Nothing is selected for you.", "hint"));
    const fieldset = el("fieldset"); fieldset.append(el("legend", item.decision_question || (item.group === "evidence" ? "Do you agree with the proposed label?" : "How should we use this proposal?")));
    options(item).forEach(([value, text]) => {const label = el("label", undefined, "choice"), input = el("input"); input.type = "radio"; input.name = "decision"; input.value = value; input.checked = answer(item).decision === value; input.onchange = () => change({decision: value}); label.append(input, el("span", text)); fieldset.append(label);}); panel.append(fieldset);
    const revised = el("div"); revised.hidden = !(item.group === "evidence" && answer(item).decision === "revise");
    const selectLabel = el("label", "Your label", "field-label"); selectLabel.htmlFor = "revised-label";
    const select = el("select"); select.id = "revised-label";
    [["", "Choose a label…"], ["pass", "Pass"], ["fail", "Fail"], ["unknown", "Unknown / insufficient evidence"]].forEach(([value, text]) => {const opt = el("option", text); opt.value = value; select.append(opt);}); select.value = answer(item).label; select.onchange = () => change({label: select.value}); revised.append(selectLabel, select); panel.append(revised);
    const label = el("label", adjudication ? "Why does this label fit the evidence?" : "Reason, suggested change, or question", "field-label"); label.htmlFor = "item-notes";
    const notes = el("textarea"); notes.id = "item-notes"; notes.rows = 6; notes.maxLength = 20000; notes.value = answer(item).notes; notes.placeholder = item.notes_hint || (adjudication ? "A short reason is enough. Name the evidence or uncertainty that matters." : "What should change, and why? Reference an event or step if useful."); notes.oninput = () => change({notes: notes.value});
    const status = el("p", "", "decision-state"); status.setAttribute("role", "status");
    const clear = el("button", "Clear this decision", "clear"); clear.onclick = () => {change({decision: "pending", label: ""}); fieldset.querySelectorAll("input").forEach(input => input.checked = false); select.value = "";};
    panel.append(label, notes, status, clear);
    function showStatus() {const a = answer(item); status.textContent = complete(item) ? "Decision recorded. You can still edit it." : a.decision === "pending" ? "Not yet reviewed. Notes can be saved without a decision." : item.group === "evidence" && a.decision === "revise" && !a.label ? "Choose your label and explain it to record this decision." : "Add a note to record this decision.";}
    function change(patch) {state.answers[item.id] = {...answer(item), ...patch, updated_at: new Date().toISOString()}; revised.hidden = !(item.group === "evidence" && answer(item).decision === "revise"); save(); updateProgress(); showStatus();}
    showStatus(); return panel;
  }
  function render() {
    updateProgress();
    const item = byId.get(selected), current = packet.items.filter(i => i.group === activeGroup);
    $("section-kicker").textContent = `${Object.keys(groups).indexOf(activeGroup) + 1} / ${Object.keys(groups).length} · ITEM ${current.indexOf(item) + 1} OF ${current.length}`;
    $("section-title").textContent = groups[activeGroup].title; $("section-help").textContent = groups[activeGroup].help;
    const grid = el("div", undefined, "review-grid"), reading = el("div", undefined, "reading");
    (item.review_kind === "adjudication" ? renderAdjudication : {evidence: renderEvidence, cases: renderCase, probes: renderProbe}[item.group])(item, reading);
    grid.append(reading, decisionPanel(item)); $("item-content").replaceChildren(grid);
  }
  function download(text, suffix, type) {
    const url = URL.createObjectURL(new Blob([text], {type})); const link = el("a");
    link.href = url; link.download = (packet.feedback_prefix || "mission-tutor-feedback-") + new Date().toISOString().slice(0, 10) + suffix;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 15000);
  }
  $("export-json").onclick = () => {const data = envelope(); download(JSON.stringify(data, null, 2) + "\n", ".json", "application/json"); notice(`Exported ${data.summary.recorded} of ${data.summary.total} decisions. Save the JSON under build/evaluations and tell the agent its file name. Exporting does not apply the decisions.`);};
  $("export-md").onclick = () => {const data = envelope(), lines = ["# Calibration feedback", "", `Reviewer: ${data.reviewer || "Not supplied"}`, `Packet: ${data.packet_sha256}`, `Recorded: ${data.summary.recorded}/${data.summary.total}`, "", data.scope, ""];
    for (const r of data.reviews) lines.push(`## ${r.title}`, "", `Decision: ${r.decision}; review state: ${r.review_state}`, ...(r.author_status ? [`Author label: ${r.author_status}`] : []), "", r.notes || "No notes.", "");
    lines.push("## Overall feedback", "", data.overall_notes || "No overall feedback."); download(lines.join("\n"), ".md", "text/markdown"); notice("Readable notes exported. Use the JSON export when handing decisions back to the agent.");};
  $("import").onclick = () => $("import-file").click();
  $("import-file").onchange = async event => {const file = event.target.files[0]; if (!file) return; try {if (file.size > 2000000) throw Error("Feedback file is too large (maximum 2 MB)."); const imported = validateImport(JSON.parse(await file.text())); undo = state; state = imported; $("undo-import").hidden = false; $("reviewer").value = state.reviewer; $("overall-notes").value = state.overall_notes; save(); render(); notice("Feedback imported for this exact packet. It replaced the browser draft. Use Undo import to restore that draft.");} catch (error) {notice("Import failed: " + error.message + " Your current draft was kept.", true);} finally {event.target.value = "";}};
  $("undo-import").onclick = () => {if (!undo) return; state = undo; undo = null; $("undo-import").hidden = true; $("reviewer").value = state.reviewer; $("overall-notes").value = state.overall_notes; save(); render(); notice("Previous draft restored.");};
  $("reviewer").value = state.reviewer; $("reviewer").oninput = event => {state.reviewer = event.target.value; save();};
  $("overall-notes").value = state.overall_notes; $("overall-notes").oninput = event => {state.overall_notes = event.target.value; save();};
  $("search").oninput = renderList; $("pending-only").onchange = renderList;
  $("next-pending").onclick = () => {const start = packet.items.findIndex(item => item.id === selected); const rest = [...packet.items.slice(start + 1), ...packet.items.slice(0, start + 1)]; const next = rest.find(item => !complete(item)); if (!next) {notice("Every item has feedback. Export the JSON to hand off your review."); return;} selected = next.id; activeGroup = next.group; $("search").value = ""; render(); $("review-content").focus({preventScroll: true});};
  $("packet-id").textContent = "Packet SHA-256: " + packet.packet_sha256; $("source-document").textContent = packet.review_document;
  if (packet.page_title) document.title = packet.page_title;
  if (packet.hero_title) $("hero-title").textContent = packet.hero_title;
  if (packet.hero_description) $("hero-description").textContent = packet.hero_description;
  if (packet.round_title) $("round-title").textContent = packet.round_title;
  if (packet.review_scope) $("review-scope").textContent = packet.review_scope;
  if (!storageOK) notice("Browser storage is unavailable or its saved draft could not be read. Export regularly to keep your feedback.", true);
  render();
})();
