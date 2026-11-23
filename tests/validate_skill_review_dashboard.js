// Run through Playwright browser_run_code_unsafe on a generated dummy review.
async (page) => {
  const browser = page.context().browser();
  const context = await browser.newContext({viewport: {width: 1200, height: 900}, acceptDownloads: true});
  const tab = await context.newPage();
  const errors = [];
  tab.on("pageerror", error => errors.push(error.message));
  const check = (value, message) => { if (!value) throw Error(message); };
  const progress = () => tab.locator("#progress-label").innerText();
  const upload = value => tab.locator("#file").setInputFiles({name: "feedback.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(value))});
  const exportFeedback = async () => {
    const downloaded = tab.waitForEvent("download");
    await tab.locator("#export").click();
    const stream = await (await downloaded).createReadStream();
    let text = "";
    for await (const chunk of stream) text += chunk.toString();
    return JSON.parse(text);
  };
  try {
    await tab.goto(page.url());
    check(await progress() === "0 of 2 judgments recorded", "No author decisions should be prefilled");
    await tab.getByLabel("unknown", {exact: true}).check();
    check(await progress() === "0 of 2 judgments recorded", "Unknown requires a reason");
    await tab.locator("#notes").fill("Missing independent evidence. <img src=x onerror=alert(1)> stays text.");
    await tab.reload();
    check(await progress() === "1 of 2 judgments recorded", "Draft should survive reload");
    check((await tab.locator("#notes").inputValue()).includes("<img"), "Notes must remain literal text");
    check(await tab.locator("img").count() === 0, "Notes must not create markup");
    const feedback = await exportFeedback();
    check(feedback.reviews[0].decision === "unknown" && feedback.reviews[1].decision === "pending", "Partial export must preserve pending items");
    await upload({...feedback, packet_sha256: "wrong"});
    await tab.waitForFunction(() => document.getElementById("status").textContent.startsWith("Import failed:"));
    check(await progress() === "1 of 2 judgments recorded", "Rejected import must preserve the draft");
    await upload({...feedback, reviews: [feedback.reviews[0], feedback.reviews[0]]});
    await tab.waitForFunction(() => document.getElementById("status").textContent.includes("duplicate"));
    await upload({...feedback, reviews: [{id: "missing", decision: "accept", notes: ""}]});
    await tab.waitForFunction(() => document.getElementById("status").textContent.includes("Unknown"));
    await upload({...feedback, reviews: [{...feedback.reviews[0], decision: "not-a-choice"}]});
    await tab.waitForFunction(() => document.getElementById("status").textContent.includes("Invalid decision"));
    await upload({...feedback, reviews: [feedback.reviews[1]]});
    await tab.waitForFunction(() => document.getElementById("progress").value === 0);
    await upload(feedback);
    await tab.waitForFunction(() => document.getElementById("progress").value === 1);
    check(JSON.stringify(await exportFeedback()) === JSON.stringify(feedback), "Export/import must round-trip");
    await tab.setViewportSize({width: 375, height: 812});
    check(await tab.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "Mobile page must not overflow");
    await tab.locator("#export").focus();
    await tab.keyboard.press("Tab");
    check(await tab.locator("#import").evaluate(node => node === document.activeElement), "Actions must support keyboard navigation");
    check(await tab.getByRole("img").getAttribute("aria-label") !== null, "Process diagram needs a text equivalent");
    check(errors.length === 0, "Unexpected browser errors: " + errors.join(", "));
  } finally { await context.close(); }

  const unavailable = await browser.newContext({acceptDownloads: true});
  try {
    await unavailable.addInitScript(() => {
      Object.defineProperty(window, "localStorage", {get() { throw Error("Storage blocked"); }});
    });
    const blocked = await unavailable.newPage();
    await blocked.goto(page.url());
    check((await blocked.locator("#status").innerText()).includes("unavailable"), "Storage failure must be visible");
    const download = blocked.waitForEvent("download");
    await blocked.locator("#export").click();
    check(await (await download).failure() === null, "Export must work without storage");
  } finally { await unavailable.close(); }
  return "Dashboard browser checks passed: pending defaults, persistence, partial exports, imports, text safety, mobile layout, keyboard access, diagram, and storage fallback.";
}
