// Run with Playwright browser_run_code against the focused dashboard URL.
async (page) => {
  const context = await page.context().browser().newContext({viewport: {width: 1440, height: 1080}, acceptDownloads: true});
  const tab = await context.newPage(), errors = [];
  tab.on("pageerror", error => errors.push(error.message));
  const check = (condition, message) => {if (!condition) throw Error(message);};
  const progress = () => tab.locator("#progress-label").innerText();
  const upload = data => tab.locator("#import-file").setInputFiles({name: "test.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(data))});
  async function exported() {
    const promise = tab.waitForEvent("download");
    await tab.getByRole("button", {name: "Export feedback JSON", exact: true}).click();
    const download = await promise, stream = await download.createReadStream();
    let text = ""; for await (const part of stream) text += part.toString();
    check(download.suggestedFilename().startsWith("mission-tutor-followup-feedback-"), "Distinct follow-up export filename");
    return JSON.parse(text);
  }
  try {
    await tab.goto(page.url());
    check(await progress() === "0 of 5 reviewed", "Only five undecided items");
    check(await tab.locator('input[name="decision"]:checked').count() === 0, "No default author label");
    check(await tab.getByText("The before/after difference does not isolate tutor effects:", {exact: false}).count() === 1, "Attribution limit is visible");
    await tab.locator('input[name="decision"][value="pass"]').check();
    check(await progress() === "0 of 5 reviewed", "A judgment needs a reason");
    await tab.locator("#item-notes").fill("Synthetic test: permitted verification.");
    await tab.reload();
    check(await progress() === "1 of 5 reviewed", "Draft survives reload");
    await tab.getByRole("button", {name: "Next unreviewed", exact: false}).click();
    await tab.locator('input[name="decision"][value="fail"]').check();
    await tab.locator("#item-notes").fill("Synthetic test: restoration criterion.");
    await tab.getByRole("button", {name: "Next unreviewed", exact: false}).click();
    check(await tab.getByText("Your previous label:", {exact: false}).count() === 1, "Prior SDI failure remains visible");
    check(await tab.locator('input[name="decision"]:checked').count() === 0, "Prior failure is not a new default decision");
    await tab.locator('input[name="decision"][value="unknown"]').check();
    await tab.locator("#item-notes").fill("Synthetic test: visibility evidence is missing.");
    let data = await exported();
    check(data.review_round === "milestone-4-follow-up", "Review round is explicit");
    check(data.summary.recorded === 3 && data.summary.pending_ids.length === 2, "Partial feedback stays partial");
    check(data.reviews.map(r => r.author_status).join(",") === "pass,fail,unknown,,", "Direct author judgments map correctly");
    check(data.reviews[2].criterion === "verification_sufficiency" && data.reviews[2].previous_author_status === "fail", "New SDI criterion and prior label are separate");
    check(data.scope.includes("does not approve Milestone 5"), "No implicit milestone approval");
    await tab.getByRole("button", {name: "Next unreviewed", exact: false}).click();
    check(await tab.getByText("does not execute or verify that expression", {exact: false}).count() > 0, "Alternative case limitation visible");
    await tab.locator('input[name="decision"][value="accept"]').check();
    await tab.getByRole("button", {name: "Next unreviewed", exact: false}).click();
    check(await tab.getByText("known authoring error", {exact: false}).count() > 0, "Deliberate fixture error explained");
    await tab.locator('input[name="decision"][value="exclude"]').check();
    await tab.locator("#item-notes").fill("Synthetic test: defer this case. <img src=x onerror=alert(1)>");
    await tab.locator("#reviewer").fill("Browser test — not author feedback");
    data = await exported();
    check(data.summary.recorded === 5, "All five decisions recorded");
    await tab.evaluate(() => {const p = JSON.parse(document.getElementById("review-data").textContent); localStorage.removeItem("interactive-missions-review:" + p.packet_sha256);});
    await tab.reload();
    await upload(data);
    await tab.getByText("Feedback imported for this exact packet.", {exact: false}).waitFor();
    check(await progress() === "5 of 5 reviewed", "Follow-up import round trip");
    const stale = {...data, packet_sha256: data.parent_packet_sha256};
    await upload(stale);
    await tab.getByText("Import failed:", {exact: false}).waitFor();
    check(await progress() === "5 of 5 reviewed", "Old review cannot replace this draft");
    const forged = structuredClone(data); forged.reviews[2].author_status = "pass";
    await upload(forged);
    await tab.getByText("Feedback imported for this exact packet.", {exact: false}).waitFor();
    check((await exported()).reviews[2].author_status === "unknown", "Imported author status is recomputed from the decision");
    check(await tab.locator("img").count() === 0, "Notes remain text");
    await tab.setViewportSize({width: 390, height: 844});
    check(await tab.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "No mobile horizontal overflow");
    check(errors.length === 0, "No JavaScript errors: " + errors.join("; "));
    return {status: "pass", items: 5, checks: ["blank decisions", "reason requirement", "persistence", "prior/new SDI separation", "partial/full exports", "import round trip", "stale review rejection", "forged-label rejection", "mobile layout"], author_feedback_created: false};
  } finally {await context.close();}
}
