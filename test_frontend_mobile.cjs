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
  let browser, releaseWave;
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
    const controls = [];
    const nativeWrites = [];
    let remaining = 2, batchSteps = 0;
    let catalogRemoved = false;
    let jobList = ["studio_generation", "ecommerce_pull", "ecommerce_pull"].map((kind, index) => ({
      id: "queued-"+index, kind, actor: "test@example.test", product_id: null,
      status: "queued", progress: 0, message: "En cola", created_at: "2026-10-10T05:57:00Z", payload: {},
    }));
    await page.route("**/service-health", route => route.fulfill({ json: { ok: true, backend: "fastapi" } }));
    await page.route("**/api/**", async route => {
      const request = route.request(); const pathname = new URL(request.url()).pathname;
      if (pathname.startsWith("/api/tools/")) {
        const operation = pathname.slice("/api/tools/".length);
        if (request.method() === "POST") nativeWrites.push({operation,body:request.postDataJSON()});
        if (operation === "inventory") return route.fulfill({json:{total:2,pending:1,
          movement_types:["Entrada","Ajuste"],summary:{products:1,units:10,retail_value:350,low_stock:0,out_of_stock:0},
          rows:[{sku:product.sku,nombre_producto:product.name,Marca:product.brand,categorias:"Dulces",Existencias:10,precio:35,counted:false,variable_parent:false},
            {sku:"123456xxxxxxx",nombre_producto:"Portada de prueba",Existencias:0,precio:0,counted:false,variable_parent:true}]}});
        if (operation === "history") return route.fulfill({json:{rows:[]}});
        if (operation === "media-preview") return route.fulfill({json:{summary:{ready:1},
          wordpress_configured:true,wordpress_write:true,woocommerce_write:true,
          rows:[{sku:product.sku,name:product.name,ready:true,wc_id:10,images:[{requested_filename:product.sku+"_1_hd.jpg",resolved_filename:product.sku+"_1_hd.jpg",resolution:"exact"}]}]}});
        if (operation === "batch-create") return route.fulfill({json:{batch_id:"test-native-batch"}});
        if (operation === "batch-status") return route.fulfill({json:{batch_id:"test-native-batch",processing:false,
          summary:{total:2,success:2-remaining,error:0,pending:remaining,running:0},rows:[]}});
        if (operation === "batch-step") {
          batchSteps++;
          await new Promise(resolve => { releaseWave = resolve; });
          remaining--;
          return route.fulfill({json:{done:false}});
        }
        return route.fulfill({json:{ok:true,message:"Guardado en prueba"}});
      }
      if (pathname === "/api/platform/products/"+product.id && request.method() === "DELETE") {
        controls.push({method:request.method(),path:pathname,body:request.postDataJSON()});
        catalogRemoved = true;
        return route.fulfill({json:{ok:true,product_id:product.id}});
      }
      if (pathname.endsWith("/cancel") && request.method() === "POST") {
        const body = request.postDataJSON();
        controls.push({method:request.method(),path:pathname,body});
        const ids = body.job_ids || [pathname.split("/").at(-2)];
        jobList = jobList.map(job => ids.includes(job.id) ? {...job,status:"cancelled",message:"Detenido"} : job);
        return route.fulfill({json:body.job_ids ? {jobs:jobList.filter(job => ids.includes(job.id))} : {job:jobList.find(job => job.id === ids[0])}});
      }
      if (pathname.endsWith("/regenerate")) {
        requests.push(request.postDataJSON());
        if (requests.length === 1) return route.abort("failed"); // response lost after acceptance
        return route.fulfill({ json: { job: { id: "accepted-once", status: "queued" } } });
      }
      let json = { items: [] };
      if (pathname === "/api/catalog-taxonomy") json = {source:"drive",categories:["Dulces","Hogar"],
        subcategories:{Dulces:["Chocolate"],Hogar:["Vajilla"]},tags:["Japón"]};
      if (pathname === "/api/session") json = { authenticated: true, email: "test@example.test", gemini_configured: true,
        folder: "TEST-INTEGRATION", image_model: asset.model, estimated_image_usd: .067 };
      else if (pathname.endsWith("/status")) json = { ready: true, configured: true, worker_ready: false, worker_can_queue: true, role: "admin", message: "Prueba" };
      else if (pathname.endsWith("/dashboard")) json = { stats: { low_stock: 1, out_of_stock: 0, sync_errors: 0, pending_jobs: 0, pending_products: 1 }, activity: [], ecommerce: null };
      else if (pathname === "/api/platform/products") json = { items: catalogRemoved ? [] : [product], total: catalogRemoved ? 0 : 1 };
      else if (pathname === "/api/platform/products/" + product.id) json = { product, images: [], assets: [asset], jobs: [], variants: [], movements: [], sync_events: [] };
      else if (pathname.endsWith("/assets")) json = { items: [asset] };
      else if (pathname === "/api/platform/jobs") json = {items:jobList};
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
      assert.ok(bounds.y > 660 && bounds.y + bounds.height <= 845, "Mobile navigation stays at the bottom");
    }
    await nav.getByRole("link", { name: "Productos", exact: true }).click();
    const removeButton = page.getByRole("button", {name:"Eliminar "+product.name,exact:true});
    assert.ok((await removeButton.boundingBox()).height >= 44, "Delete has a mobile touch target");
    await removeButton.click();
    const removeDialog = page.getByRole("dialog");
    await removeDialog.getByText(/Se conservan los archivos de Drive/).waitFor();
    assert.equal(controls.length,0,"Opening confirmation performs no deletion");
    await removeDialog.getByRole("button", {name:"Cancelar",exact:true}).click();
    await page.getByRole("button",{name:"Abrir producto "+product.name,exact:true}).click();
    await page.getByRole("button", { name: "Editar", exact: true }).click();
    assert.ok(await page.getByRole("textbox").count() > 3, "Editable product form is available");
    const editForm = page.locator(".p-card").filter({has:page.getByRole("heading",{name:"Editar producto",exact:true})});
    try {
      await editForm.getByText("Opciones de Lista completa en tu Drive.",{exact:true}).waitFor();
    } catch (error) {
      console.error("Classification status: " + JSON.stringify(await page.locator(".classification-status").allTextContents()));
      fs.mkdirSync(path.join(__dirname,"test-results"),{recursive:true});
      await page.screenshot({path:path.join(__dirname,"test-results","classification-failure.png"),fullPage:true});
      throw error;
    }
    await editForm.getByLabel("Categoría",{exact:true}).selectOption("Hogar");
    assert.equal(await editForm.getByLabel("Subcategoría",{exact:true}).inputValue(),"");
    await editForm.getByLabel("Subcategoría",{exact:true}).selectOption("Vajilla");
    await editForm.getByRole("checkbox",{name:"Japón",exact:true}).check();
    assert.ok(await editForm.getByRole("checkbox",{name:"Japón",exact:true}).isChecked());
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
    await page.keyboard.press("Escape");
    await page.getByRole("button", {name:/^Trabajos/}).click();
    const stopButton = page.getByRole("button", {name:"Detener proceso",exact:true}).first();
    assert.ok((await stopButton.boundingBox()).height >= 44, "Stop has a mobile touch target");
    await stopButton.click();
    await page.getByRole("dialog").getByRole("button", {name:"Detener proceso",exact:true}).click();
    await page.getByText("Cancelado",{exact:true}).waitFor();
    assert.equal(controls.length,1);
    await page.getByRole("button", {name:"Detener todos (2)",exact:true}).click();
    await page.getByRole("dialog").getByRole("button", {name:"Detener todos",exact:true}).click();
    await page.waitForFunction(() => document.querySelectorAll(".p-badge.cancelled").length === 3);
    assert.equal(await page.getByRole("button", {name:"Detener proceso",exact:true}).count(),0);
    assert.deepEqual(controls[1].body.job_ids.sort(),["queued-1","queued-2"]);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),"Job controls fit mobile width");
    await nav.getByRole("link", {name:"Productos",exact:true}).click();
    await page.getByRole("button", {name:"Eliminar "+product.name,exact:true}).click();
    await page.getByRole("dialog").getByRole("button", {name:"Eliminar producto",exact:true}).click();
    await page.getByRole("heading", {name:"Tu catálogo empieza aquí",exact:true}).waitFor();
    assert.equal(controls[2].method,"DELETE");
    assert.deepEqual(controls[2].body,{confirm:true,version:product.version});
    await page.evaluate(() => dispatchEvent(new Event("offline")));
    await page.getByText("Sin conexión", { exact: true }).waitFor();
    await page.evaluate(() => dispatchEvent(new Event("online")));
    await page.getByText("En línea", { exact: true }).waitFor();
    await page.setViewportSize({ width: 1280, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const desktopNav = await nav.boundingBox();
    assert.ok(desktopNav.x < 10 && desktopNav.width < 250,"Desktop navigation uses the sidebar");
    await nav.getByRole("link",{name:"Más",exact:true}).click();
    assert.equal(await page.locator(".p-main .p-tabs").count(),0,"Section tools moved out of the content");
    await nav.getByRole("button",{name:"Revisar Drive y WordPress",exact:true}).click();
    await page.getByRole("heading",{name:"Revisar Drive y WordPress",exact:true}).waitFor();
    assert.equal(nativeWrites.length,0,"Opening native tools does not write");
    await page.getByRole("button",{name:"Revisar imágenes de Drive y WordPress",exact:true}).click();
    await page.getByText(product.sku+"_1_hd.jpg · exact",{exact:true}).waitFor();
    assert.equal(await page.locator(".p-native-tools iframe").count(),0,"Tools are native components");
    fs.mkdirSync(path.join(__dirname,"test-results"),{recursive:true});
    await page.screenshot({path:path.join(__dirname,"test-results","navigation-desktop.png"),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await nav.getByRole("link",{name:"Inventario",exact:true}).click();
    await nav.getByRole("button",{name:"Conteo y movimientos",exact:true}).click();
    await page.getByRole("heading",{name:"Conteo y movimientos de Drive",exact:true}).waitFor();
    const toolBounds = await nav.getByRole("button",{name:"Conteo y movimientos",exact:true}).boundingBox();
    assert.ok(toolBounds.y > 650 && toolBounds.height >= 44,"Tools have bottom mobile touch targets");
    await page.getByRole("button",{name:"Cargar inventario de Drive",exact:true}).click();
    const parentCount = page.getByRole("checkbox",{name:"Seleccionar conteo 123456xxxxxxx",exact:true});
    await parentCount.waitFor(); assert.ok(await parentCount.isDisabled(),"Parent has no physical stock");
    await page.getByRole("checkbox",{name:"Seleccionar conteo "+product.sku,exact:true}).check();
    await page.getByLabel("Conteo físico de "+product.sku,{exact:true}).fill("7");
    await page.getByRole("button",{name:"Guardar conteos seleccionados (1)",exact:true}).click();
    assert.equal(nativeWrites.length,0,"Count confirmation opens without writing");
    await page.getByRole("dialog").getByRole("button",{name:"Guardar conteos",exact:true}).click();
    await page.getByText("Guardado en prueba",{exact:true}).waitFor();
    assert.deepEqual(nativeWrites[0],{operation:"counts",body:{confirm:true,counts:[{sku:product.sku,stock:7}]}});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),"Native inventory fits phone width");
    await page.screenshot({path:path.join(__dirname,"test-results","navigation-mobile.png"),fullPage:true});
    await nav.getByRole("link",{name:"Más",exact:true}).click();
    await nav.getByRole("button",{name:"Publicación masiva",exact:true}).click();
    await page.getByRole("button",{name:"Crear y publicar lote",exact:true}).click();
    await page.getByRole("dialog").getByRole("button",{name:"Crear y publicar",exact:true}).click();
    for(let i=0;i<100 && !releaseWave;i++) await page.waitForTimeout(50);
    assert.equal(batchSteps,1,"A confirmed publication starts one wave");
    await page.getByRole("button",{name:"Pausar publicación",exact:true}).click();
    releaseWave();
    await page.getByText("Pausado",{exact:true}).waitFor();
    await page.waitForTimeout(350);
    assert.equal(batchSteps,1,"Pausing while a wave runs prevents the next write");
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),"Native batch fits phone width");
    assert.deepEqual(errors, [], "No browser exceptions");
    console.log("Browser: 360/390/430px, sidebar/bottom tools, native Drive and WordPress, confirmed counts, safe batch pause, deletion/cancellation and paid idempotency passed.");
  } finally {
    // A failed assertion must release the synthetic in-flight wave before closing the browser.
    releaseWave?.();
    if (browser) await browser.close();
    server.kill("SIGTERM");
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
