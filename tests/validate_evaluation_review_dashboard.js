// Run with the Playwright browser_run_code tool; uses a separate browser context.
async (page) => {
  const context = await page.context().browser().newContext({viewport: {width: 1440, height: 1080}, acceptDownloads: true});
  const tab = await context.newPage();
  const errors = [];
  tab.on("pageerror", error => errors.push(error.message));
  const check = (condition, message) => {if (!condition) throw Error(message);};
  const progress = () => tab.locator("#progress-label").innerText();
  const download = async button => {
    const event = tab.waitForEvent("download");
    await tab.getByRole("button", {name: button, exact: true}).click();
    const file = await event, stream = await file.createReadStream();
    let text = "";
    for await (const chunk of stream) text += chunk.toString();
    return text;
  };
  const upload = value => tab.locator("#import-file").setInputFiles({name: "feedback.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(value))});
  try {
    await tab.goto(page.url());
    check(await progress() === "0 of 25 reviewed", "New review must be empty");
    check(await tab.locator('input[name="decision"]:checked').count() === 0, "No default approval");
    await tab.getByLabel("Use the proposed label", {exact: true}).check();
    await tab.locator("#item-notes").fill("First review. <img src=x onerror=alert(1)> stays text.");
    await tab.reload();
    check(await progress() === "1 of 25 reviewed", "Decision must survive reload");
    check((await tab.locator("#item-notes").inputValue()).includes("<img"), "Notes must survive reload unchanged");
    check(await tab.locator("img").count() === 0, "Feedback must never become HTML");

    await tab.getByRole("button", {name: "Observed recovery, needs a decision", exact: true}).click();
    await tab.getByLabel("Use a different label", {exact: true}).check();
    await tab.getByLabel("Your label", {exact: true}).selectOption("unknown");
    check(await progress() === "1 of 25 reviewed", "Revised labels require an explanation");
    await tab.locator("#item-notes").fill("Please verify whether the correction actually ran.");
    check(await progress() === "2 of 25 reviewed", "Revision must count once complete");

    await tab.locator(".group-button").filter({hasText: "Cases"}).click();
    check(await tab.locator(".item-button").count() === 15, "All 15 cases available");
    await tab.locator("#search").fill("inspection error");
    check(await tab.locator(".item-button").count() === 1, "Search limits the queue");
    await tab.locator(".item-button").click();
    await tab.getByLabel("Leave this case out", {exact: true}).check();
    await tab.locator("#item-notes").fill("Test exclusion feedback.");

    await tab.locator(".group-button").filter({hasText: "Probes"}).click();
    check(await tab.locator(".item-button").count() === 4, "All four probe criteria available");
    await tab.getByLabel("Revise as noted below", {exact: true}).check();
    await tab.locator("#item-notes").fill("Accept equivalent descriptions of the sampling interval.");
    await tab.locator("#reviewer").fill("Dashboard regression (not author feedback)");
    await tab.locator("#overall-notes").fill("Synthetic browser test only.");
    const feedback = JSON.parse(await download("Export feedback JSON"));
    check(feedback.summary.recorded === 4, "Partial review export must preserve pending items");
    check(feedback.reviews.length === 25, "Export must include every item");
    check(feedback.reviews[0].author_status === "fail", "Accepting a proposed fail must not turn it into pass");
    check(feedback.reviews[1].author_status === "unknown", "Revised label must be exported");
    check(feedback.reviews[2].author_status === null, "Unreviewed labels must remain null");
    check((await download("Export readable notes")).includes("Synthetic browser test only."), "Readable notes export");

    const saved = await tab.evaluate(() => {const d = JSON.parse(document.getElementById("review-data").textContent); return "interactive-missions-review:" + d.packet_sha256;});
    await tab.evaluate(key => localStorage.removeItem(key), saved);
    await tab.reload();
    await upload(feedback);
    await tab.getByText("Feedback imported for this exact packet.", {exact: false}).waitFor();
    check(await progress() === "4 of 25 reviewed", "Import restores partial feedback");
    await tab.getByRole("button", {name: "Undo import", exact: true}).click();
    check(await progress() === "0 of 25 reviewed", "Undo must restore the old draft");
    await upload(feedback);
    await tab.getByText("Feedback imported for this exact packet.", {exact: false}).waitFor();
    await upload({...feedback, packet_sha256: "different-packet"});
    await tab.getByText("Import failed:", {exact: false}).waitFor();
    check(await progress() === "4 of 25 reviewed", "Stale feedback must not replace current decisions");
    const duplicate = structuredClone(feedback);
    duplicate.reviews[1] = duplicate.reviews[0];
    await upload(duplicate);
    await tab.getByText("unknown or duplicate item", {exact: false}).waitFor();
    check(await progress() === "4 of 25 reviewed", "Duplicate feedback must be rejected atomically");

    const forged = structuredClone(feedback);
    forged.summary.recorded = 25;
    forged.reviews[2].author_status = "pass";
    await upload(forged);
    await tab.getByText("Feedback imported for this exact packet.", {exact: false}).waitFor();
    const reexport = JSON.parse(await download("Export feedback JSON"));
    check(reexport.summary.recorded === 4 && reexport.reviews[2].author_status === null, "Import must recompute labels, not trust forged summaries");

    await tab.getByRole("button", {name: "Next unreviewed", exact: false}).click();
    check(await tab.locator('input[name="decision"]:checked').count() === 0, "Next unreviewed must find an undecided item");
    await tab.setViewportSize({width: 390, height: 844});
    check(await tab.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "No horizontal overflow on mobile");
    check(await tab.getByRole("button", {name: "Export feedback JSON", exact: true}).isVisible(), "Export remains visible on mobile");
    check(errors.length === 0, "No JavaScript errors: " + errors.join("; "));
    return {status: "pass", reviewed: "25 source-bound items", checks: ["empty defaults", "persistence", "revision validation", "search", "partial exports", "JSON and Markdown downloads", "import and undo", "stale/duplicate rejection", "forged summary rejection", "text escaping", "mobile layout"], author_feedback_created: false};
  } finally {await context.close();}
}
