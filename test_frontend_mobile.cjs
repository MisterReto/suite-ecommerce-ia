/* Browser smoke test with synthetic API data; never calls a live integration.
 * Requires Playwright (or CODEX_PRIMARY_RUNTIME_NODE_MODULES) and a Next build.
 */
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const { spawn } = require("node:child_process");
const { chromium } = require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES
  ? path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, "playwright") : "playwright");

const product = { id: "test-product", sku: "TEST-INTEGRATION-MOBILE", barcode: "1234567890123",
  name: "Producto de prueba móvil", brand: "Glico", category: "Dulces", subcategory: "Chocolate",
  short_description: "Referencia de prueba", long_description: "Ficha sintética de pruebas",
  tags: [], attributes: {}, product_type: "simple", parent_id: null, price: 35, cost: 20,
  stock: 10, woocommerce_stock: 10, loyverse_stock: null, status: "pending", sync_status: "synced", version: 1 };
const asset = { id: "test-asset", image_id: "test-image", product_id: product.id, job_id: "test-job",
  provider: "gemini", model: "gemini-3.1-flash-image", sku: product.sku, product_name: product.name,
  slot: "1_hd", estimated_correction_usd: .067, status: "completed", history: [], metadata_json: {} };

(async () => {
  const server = spawn(process.execPath, [".next/standalone/server.js"], {
    cwd: path.join(__dirname, "frontend"), env: { ...process.env, PORT: "23002", HOSTNAME: "127.0.0.1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let diagnostics = "";
  server.stderr.on("data", chunk => { diagnostics = (diagnostics + chunk).slice(-3000); });
  let browser;
  try {
    for (let attempt = 0; attempt < 100; attempt++) {
      try { if ((await fetch("http://127.0.0.1:23002/")).ok) break; } catch {}
      if (server.exitCode !== null) throw new Error(diagnostics);
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    browser = await chromium.launch({ headless: true,
      ...(process.env.TEST_CHROMIUM_PATH ? { executablePath: process.env.TEST_CHROMIUM_PATH } : {}),
      args: ["--no-sandbox", "--disable-dev-shm-usage"] });
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: "block" });
    const page = await context.newPage();
    const errors = []; page.on("pageerror", error => errors.push(error.message));
    const requests = [];
    await page.route("**/api/**", async route => {
      const request = route.request(); const pathname = new URL(request.url()).pathname;
      if (pathname.endsWith("/regenerate")) {
        requests.push(request.postDataJSON());
        if (requests.length === 1) return route.abort("failed"); // response lost after acceptance
        return route.fulfill({ json: { job: { id: "accepted-once", status: "queued" } } });
      }
      let json = { items: [] };
      if (pathname === "/api/session") json = { authenticated: true, email: "test@example.test", gemini_configured: true,
        folder: "TEST-INTEGRATION", image_model: asset.model, estimated_image_usd: .067 };
      else if (pathname.endsWith("/status")) json = { ready: true, configured: true, worker_ready: true, role: "admin", message: "Prueba" };
      else if (pathname.endsWith("/dashboard")) json = { stats: { low_stock: 1, out_of_stock: 0, sync_errors: 0, pending_jobs: 0, pending_products: 1 }, activity: [], ecommerce: null };
      else if (pathname === "/api/platform/products") json = { items: [product], total: 1 };
      else if (pathname === "/api/platform/products/" + product.id) json = { product, images: [], assets: [asset], jobs: [], variants: [], movements: [], sync_events: [] };
      else if (pathname.endsWith("/assets")) json = { items: [asset] };
      else if (pathname.includes("/images/")) return route.fulfill({ contentType: "image/png", body: fs.readFileSync(path.join(__dirname, "frontend/public/logo.png")) });
      else if (pathname.endsWith("/taxonomy")) json = { categories: [], brands: [] };
      return route.fulfill({ json });
    });
    await page.goto("http://127.0.0.1:23002/", { waitUntil: "networkidle" });
    const nav = page.getByRole("navigation", { name: "Navegación principal" });
    assert.equal(await nav.getByRole("link").count(), 5);
    for (const width of [360, 390, 430]) {
      await page.setViewportSize({ width, height: 844 });
      for (const name of ["Inicio", "Productos", "Generar", "Inventario", "Más"]) {
        await nav.getByRole("link", { name, exact: true }).click();
        await page.waitForTimeout(300);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Horizontal overflow: ${name}, ${width}px`);
      }
      const bounds = await nav.boundingBox();
      assert.ok(bounds.y > 700 && bounds.y + bounds.height <= 845, "Mobile navigation stays at the bottom");
    }
    await nav.getByRole("link", { name: "Productos", exact: true }).click();
    await page.locator(".p-product-card").first().click();
    await page.getByRole("button", { name: "Editar", exact: true }).click();
    assert.ok(await page.getByRole("textbox").count() > 3, "Editable product form is available");
    await nav.getByRole("link", { name: "Generar", exact: true }).click();
    await page.getByRole("button", { name: "Revisar imágenes", exact: false }).click();
    await page.locator(".p-asset-card").first().click();
    await page.getByRole("button", { name: "Regenerar", exact: true }).click();
    await page.getByRole("button", { name: "Confirmar generación", exact: true }).click();
    await page.waitForTimeout(300);
    await page.getByRole("button", { name: "Confirmar generación", exact: true }).click();
    await page.waitForTimeout(300);
    assert.equal(requests.length, 2);
    assert.equal(requests[0].request_key, requests[1].request_key, "Lost-response retry reuses the same paid intent");
    await page.evaluate(() => dispatchEvent(new Event("offline")));
    await page.getByText("Sin conexión", { exact: true }).waitFor();
    await page.evaluate(() => dispatchEvent(new Event("online")));
    await page.getByText("En línea", { exact: true }).waitFor();
    await page.setViewportSize({ width: 1280, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual(errors, [], "No browser exceptions");
    console.log("Browser: 360/390/430px, five menus, cards/form, 1280px, connection and lost-response idempotency passed.");
  } finally {
    if (browser) await browser.close();
    server.kill("SIGTERM");
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
