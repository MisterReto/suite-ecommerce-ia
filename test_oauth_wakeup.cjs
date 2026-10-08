/* Browser regression: only readiness GETs are retried; no real Google login. */
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { chromium } = require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES
  ? path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, "playwright") : "playwright");

(async () => {
  const origin = "http://127.0.0.1:23004";
  const server = spawn(process.execPath, [".next/standalone/server.js"], {
    cwd: path.join(__dirname, "frontend"),
    env: { ...process.env, PORT: "23004", HOSTNAME: "127.0.0.1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let diagnostics = "", browser;
  server.stderr.on("data", chunk => { diagnostics = (diagnostics + chunk).slice(-3000); });
  try {
    let ready = false;
    for (let attempt = 0; attempt < 100; attempt++) {
      if (server.exitCode !== null) throw new Error(diagnostics);
      try { if ((await fetch(origin + "/login")).ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready, "Local login page must start even without a backend");
    browser = await chromium.launch({ headless: true,
      ...(process.env.TEST_CHROMIUM_PATH ? { executablePath: process.env.TEST_CHROMIUM_PATH } : {}),
      args: ["--no-sandbox", "--disable-dev-shm-usage"] });
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, serviceWorkers: "block" });
    let checks = 0, starts = 0, awake = false;
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.route("**/service-health", async route => {
      checks++;
      assert.equal(route.request().method(), "GET");
      if (checks === 1) {
        // Hold the first request past the client's eight-second timeout.
        await new Promise(resolve => setTimeout(resolve, 9000));
        return route.abort().catch(() => {});
      }
      if (checks === 2) return route.fulfill({ status: 502, body: "Bad Gateway" });
      if (checks === 3) return route.fulfill({ contentType: "text/html", body: "Render loading" });
      if (checks === 4) return route.fulfill({ json: { ok: true } });
      return route.fulfill({ status: awake ? 200 : 503,
        json: { ok: awake, backend: "fastapi" } });
    });
    await page.route("**/auth/start", route => {
      starts++;
      return route.fulfill({ contentType: "text/html", body: "<h1>Google sign-in test</h1>" });
    });
    await page.goto(origin + "/login");
    await page.getByRole("heading", { name: "Iniciando servidor", exact: true }).waitFor();
    assert.equal(new URL(page.url()).pathname, "/login");
    for (const width of [360, 390, 430]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    for (let attempt = 0; checks < 5 && attempt < 300; attempt++) {
      await page.waitForTimeout(100);
    }
    assert.ok(checks >= 5, "Timeout, 502, HTML and invalid readiness all get retried");
    assert.equal(starts, 0, "No OAuth state or provider request before readiness");
    assert.ok(await page.getByRole("heading", { name: "Iniciando servidor", exact: true }).isVisible());
    awake = true;
    await page.getByRole("heading", { name: "Google sign-in test" }).waitFor({ timeout: 10000 });
    assert.equal(starts, 1, "Begin OAuth once after the API is ready");
    assert.deepEqual(errors, []);

    const bounded = await browser.newPage({ viewport: { width: 390, height: 844 }, serviceWorkers: "block" });
    await bounded.clock.install();
    let boundedChecks = 0, boundedStarts = 0;
    await bounded.route("**/service-health", route => {
      boundedChecks++;
      return route.fulfill({ status: 503, json: { ok: false } });
    });
    await bounded.route("**/auth/start", route => { boundedStarts++; return route.abort(); });
    await bounded.goto(origin + "/login");
    for (let attempt = 0; boundedChecks < 1 && attempt < 20; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    await new Promise(resolve => setTimeout(resolve, 100));
    await bounded.clock.fastForward(181000);
    await bounded.getByRole("heading", { name: "El servidor aún no está disponible" }).waitFor();
    const stoppedChecks = boundedChecks;
    await bounded.clock.fastForward(60000);
    assert.equal(boundedChecks, stoppedChecks, "Stop probing after the bounded waiting window");
    assert.equal(boundedStarts, 0);
    await bounded.getByRole("button", { name: "Reintentar" }).click();
    await bounded.getByRole("heading", { name: "Iniciando servidor", exact: true }).waitFor();
    for (let attempt = 0; boundedChecks <= stoppedChecks && attempt < 20; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    assert.ok(boundedChecks > stoppedChecks, "Explicit retry starts a new bounded wait");
    console.log("OAuth wakeup: timeout/502/HTML handling, mobile layout, one start, bounded wait and explicit retry passed.");
  } catch (error) {
    console.error("Next.js diagnostics: " + diagnostics);
    throw error;
  } finally {
    if (browser) await browser.close();
    const closed = new Promise(resolve => server.once("exit", resolve));
    server.kill("SIGTERM");
    await Promise.race([closed, new Promise(resolve => setTimeout(resolve, 5000))]);
    if (server.exitCode === null) server.kill("SIGKILL");
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
