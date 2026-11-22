// Records a short Lumi demo against the local demo servers (frontend :3300, backend :8100).
const { chromium } = require("playwright");
const path = require("path");

const URL = "http://localhost:3300/";
const OUT = path.join(__dirname, "video");
const SIZE = { width: 1440, height: 900 };

// A caption strip so the video explains itself without narration.
async function caption(page, text) {
  await page.evaluate((value) => {
    let el = document.getElementById("demo-caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "demo-caption";
      Object.assign(el.style, {
        position: "fixed", top: "16px", right: "16px", zIndex: "10000", maxWidth: "520px",
        background: "#0b2545", color: "#fff", padding: "12px 16px", borderRadius: "8px",
        font: "600 18px/1.35 Barlow, system-ui, sans-serif", boxShadow: "0 6px 18px rgba(11,37,69,.35)",
        borderLeft: "6px solid #8ecae6",
      });
      document.body.appendChild(el);
    }
    el.textContent = value;
  }, text);
}

async function main() {
  const browser = await chromium.launch();
  // Warm up the NWS and the app off camera, so the recording opens on a ready page.
  const warm = await browser.newPage();
  await warm.goto(URL, { waitUntil: "domcontentloaded" });
  await warm.getByText("Boston now").waitFor({ timeout: 30000 });
  await warm.close();

  const context = await browser.newContext({ viewport: SIZE, recordVideo: { dir: OUT, size: SIZE } });
  const page = await context.newPage();
  const pause = (ms) => page.waitForTimeout(ms);

  await page.request.post("http://127.0.0.1:8100/demo/reset");
  await page.goto(URL, { waitUntil: "domcontentloaded" });
  await page.getByText("Boston now").waitFor({ timeout: 30000 });
  await caption(page, "Lumi: winter walking routes around BU, shaped by what people report.");
  await pause(4000);

  await caption(page, "First visit: a short How Lumi works panel and live Boston weather.");
  await pause(3500);
  await page.getByRole("button", { name: "Got it" }).click();

  await caption(page, "Pick a start and a destination: BU Bridge to Kenmore Square, about a mile.");
  await page.getByLabel(/From/).selectOption({ label: "BU Bridge" });
  await pause(1200);
  await page.getByLabel(/To/).selectOption({ label: "Kenmore Square" });
  await page.getByRole("button", { name: /Shortest/ }).filter({ hasText: "min" }).first().waitFor({ timeout: 20000 });
  await pause(3500);

  await caption(page, "Three walks, each defined: Shortest, Safer and Accessible.");
  await page.getByRole("button", { name: /^Shortest/ }).click();
  await pause(2500);
  await page.getByRole("button", { name: /^Safer/ }).click();
  await pause(2500);

  await caption(page, "Someone reports a snowbank blocking the sidewalk (simulated for the demo).");
  await page.getByRole("button", { name: "Block a sidewalk on this route" }).click();
  await pause(5000);
  await caption(page, "A blocked sidewalk is skipped by every route: all three redraw around it, at about 1 min more.");
  await pause(5500);
  await caption(page, "The report shows on the map and in the live crawl, labeled Simulated and Confirmed.");
  await pause(4500);

  await caption(page, "To clear a block, 4 different people nearby must say it's clear (simulated here).");
  await page.getByRole("button", { name: /bots say it's clear/ }).click();
  await pause(5500);
  await caption(page, "The route returns to normal. Lumi never calls a route safe: reports can be out of date.");
  await pause(5000);

  const video = page.video();
  await context.close();
  console.log("video:", await video.path());
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
