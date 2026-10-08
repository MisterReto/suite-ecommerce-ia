/* Browser acceptance with a ready PostgreSQL catalog and synthetic API data.
 * No provider, Google, WooCommerce or stock writes occur in this test.
 */
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const { spawn } = require("node:child_process");
const playwright = require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES
  ? path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, "playwright") : "playwright");
const origin = "http://127.0.0.1:23003";
const photo = fs.readFileSync(path.join(__dirname, "frontend/public/logo.png"));
const blank = () => ({sku:"", name:"", brand:"", size:"", kind:"Simple", price:0, category:"", subcategory:"",
  tags:"", short_description:"", description:"", barcode:"", parent_sku:"", parent_name:"",
  parent_mode:"Crear nuevo padre", attribute:"Tamaño", attribute_value:"", product_type:"", variant:"", attributes:{}, uncertain_fields:[]});

async function exercise(browser, engine, width) {
  const device = playwright.devices[engine === "webkit" ? "iPhone 13" : "Pixel 5"];
  const context = await browser.newContext({...device, viewport:{width, height:844}, screen:{width,height:844}, serviceWorkers:"block"});
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__captureTestTouches = 0;
    window.__generationNotes = [];
    document.addEventListener("touchstart", () => { window.__captureTestTouches++; }, {passive:true});
    const NativeAudio = window.AudioContext || window.webkitAudioContext;
    window.AudioContext = function () {
      const audio = new NativeAudio();
      const create = audio.createOscillator.bind(audio);
      audio.createOscillator = () => {
        const oscillator = create(), start = oscillator.start.bind(oscillator);
        oscillator.start = at => {window.__generationNotes.push(oscillator.frequency.value);start(at);};
        return oscillator;
      };
      return audio;
    };
  });
  const errors = []; page.on("pageerror", e => errors.push(e.message));
  let draft = null, configured = true, count = 0, writes = 0, saves = 0, rejectUpload = true, warming = true;
  const generations = [], corrections = [];
  let imageJob = null, polls = 0, failImage = false;
  async function touchTarget(locator, label) {
    // Bring the control to the usable center, as a phone swipe would. WebKit's
    // nearest-edge scroll can leave an otherwise reachable target under the fixed nav.
    await locator.evaluate(element => element.scrollIntoView({block:"center",inline:"nearest",behavior:"instant"}));
    try {
      await page.waitForFunction(element => {
        const bounds = element.getBoundingClientRect();
        const hit = document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
        return hit === element || element.contains(hit);
      }, await locator.elementHandle(), {timeout:3000});
    } catch {
      const diagnostic = await locator.evaluate(element => {
        const bounds = element.getBoundingClientRect();
        const hit = document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
        return {bounds:bounds.toJSON(),width:innerWidth,height:innerHeight,hit:hit?.outerHTML.slice(0,250)};
      });
      assert.fail(`${engine}/${width}: ${label} is unreachable: ${JSON.stringify(diagnostic)}`);
    }
    const bounds = await locator.boundingBox();
    assert.ok(bounds && bounds.width >= 44 && bounds.height >= 44, `${engine}/${width}: ${label} has a 44px touch target`);
    assert.ok(await locator.evaluate(element => {
      const bounds = element.getBoundingClientRect();
      const hit = document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
      return hit === element || element.contains(hit);
    }), `${engine}/${width}: ${label} is reachable above navigation or dialogs`);
  }
  const complete = () => ({job:{id:"synthetic-job", status:"completed", progress:100, label:"Prueba", message:"Listo"}, draft});
  await page.route("**/api/**", async route => {
    const request = route.request(), p = new URL(request.url()).pathname, method = request.method();
    let json = {items:[]};
    const body = () => request.postDataJSON() || {};
    if (p === "/api/session" && warming)
      return route.fulfill({status:503,contentType:"text/html",body:"<!DOCTYPE html><title>Service starting</title>"});
    if (p === "/api/session") json = {authenticated:true, email:"admin@example.test", gemini_configured:configured,
      gemini_source:configured ? "user_settings" : "not_configured", folder:"Tienda sintética", image_model:"gemini-3.1-flash-image",
      text_model:"gemini-3.1-flash-lite-preview", estimated_image_usd:.067, draft};
    else if (p === "/api/platform/status") json = {ready:true, configured:true, worker_ready:true, worker_can_queue:true, role:"admin"};
    else if (p === "/api/platform/dashboard") json = {stats:{low_stock:0,out_of_stock:0,sync_errors:0,pending_jobs:0,pending_products:0},activity:[],ecommerce:null};
    else if (p === "/api/platform/products") json = {items:[], total:0};
    else if (p === "/api/platform/taxonomy") json = {categories:[],brands:[]};
    else if (p === "/api/uploads") {
      if (rejectUpload) {
        rejectUpload = false;
        return route.fulfill({status:413,json:{detail:"La foto supera el límite de carga. Intenta con otra foto."}});
      }
      json = {id:"photo-"+(++count), width:120, height:180};
    }
    else if (p.startsWith("/api/files/")) return route.fulfill({contentType:"image/png",body:photo});
    else if (p === "/api/capture") {
      draft = {...body(), revision:"capture-"+count, product:blank(), images:{}};
      json = {draft};
    } else if (p === "/api/draft" && method === "PUT") {
      draft.product = {...blank(),...body()};
      draft.product.barcode = draft.product.barcode.replace(/[\s-]/g,"");
      draft.product.sku = draft.product.barcode || (draft.product.name ? "GLIPOC40GX" : "");
      delete draft.identity_review; writes++; json = {draft};
    } else if (p === "/api/draft" && method === "DELETE") {draft=null; json={ok:true};}
    else if (p === "/api/capture-notes") {draft.context=body().context; json={draft};}
    else if (p === "/api/analyze") {
      draft.product = {...blank(),sku:"GLIPOC40GX",name:"Pocky Chocolate 40 g",brand:"Glico",size:"40 g",category:"Dulces",
        price:35,product_type:"Galleta",variant:"Chocolate",attribute:"Sabor",attribute_value:"Chocolate",attributes:{Sabor:"Chocolate"},uncertain_fields:["codigo_barras"]};
      json=complete();
    } else if (p === "/api/check-product") {
      draft.identity_review={status:"possible_variation",case:"existing_parent",message:"Posible variación nueva de GLIPOCFULL",
        recommendation:"Revisar los atributos",suggested:"GLIPOCFULL",parents:[],sources:["WooCommerce pausado"],
        candidates:[{sku:"POCKFR40",nombre_producto:"Pocky Fresa 40 g",Marca:"Glico",precio:35,_source:"Google Sheets",atributo_nombre:"Sabor",atributo_valor:"Fresa",matching_attributes:["Marca","Familia"],different_attributes:["Sabor: Fresa / Chocolate"]}]};
      json={...draft.identity_review,draft};
    } else if (p === "/api/parents") json={choices:[["Pocky · Glico · GLIPOCFULL","GLIPOCFULL"]],parent_sku:"GLIPOCFULL",parent_name:"Pocky",attribute:"Sabor",draft};
    else if (p === "/api/family-cover") {
      draft.cover_id="cover-real-photo"; draft.cover_message="Portada con 1 foto real. Aún no hay fotos de otras variaciones."; json=complete();
    } else if (p === "/api/generate") {
      generations.push(body()); polls=0;
      imageJob={id:"generation-"+generations.length,status:failImage?"queued":"completed",progress:failImage?0:100,label:"Generando imágenes",message:"Listo"};
      if (!failImage) draft.images=Object.fromEntries(body().slots.map(slot=>[slot,{id:slot,approved:false,history:[],message:"Lista"}]));
      json={job:imageJob,draft};
    } else if (/\/api\/images\/[^/]+\/correct/.test(p)) {
      const slot = p.split("/")[3];
      corrections.push({slot,...body()});
      draft.images[slot] = {...draft.images[slot],id:slot+"-corrected",history:[draft.images[slot].id]};
      imageJob={id:"correction-"+corrections.length,status:"queued",progress:0,label:"Corrigiendo imagen",message:"En cola"};polls=0;
      json = {job:imageJob,draft};
    } else if (p.startsWith("/api/jobs/")) {
      polls++;
      if (!failImage && polls === 1) return route.fulfill({status:503,json:{detail:"Conexión temporal al consultar el progreso"}});
      imageJob={...imageJob,status:polls<3?"running":failImage?"failed":"completed",progress:polls<3?40:100,
        message:failImage?"La generación sintética falló":"Listo"};
      json={job:imageJob,draft};
    } else if (/\/api\/images\/[^/]+\/approve/.test(p)) {draft.images[p.split("/")[3]].approved=body().approved;json={draft};}
    else if (p === "/api/save") {
      saves++; draft.saved="Producto guardado"; draft.sync_status="pending_repair";draft.sync_error="Sheets guardó; falta el maestro";json=complete();
    } else if (p === "/api/capture-sync") {draft.sync_status="synced";delete draft.sync_error;json=complete();}
    else if (p === "/api/settings") {assert.ok(body().api_key);configured=true;json={ok:true};}
    else if (p === "/api/settings/gemini" && method === "DELETE") {configured=false;json={ok:true};}
    else if (p === "/api/settings/gemini/test") json={message:"Modelos consultados sin generar",image_model_available:true,text_model_available:true};
    return route.fulfill({json});
  });
  try {
    await page.goto(origin,{waitUntil:"networkidle"});
    await page.locator(".p-alert.error").getByText("El servicio todavía no responde. Espera unos segundos y vuelve a intentarlo.",{exact:true}).waitFor();
    warming = false;
    await page.reload({waitUntil:"networkidle"});
    const nav=page.getByRole("navigation",{name:"Navegación principal"});
    await nav.getByRole("link",{name:"Productos",exact:true}).tap();
    assert.ok(await page.evaluate(() => window.__captureTestTouches > 0), "Phone touch events reach the page");
    await page.getByRole("button",{name:"Nuevo producto con IA",exact:true}).tap();
    const capture=page.locator(".capture-embedded");
    await capture.getByRole("heading",{name:"Estudio de productos"}).waitFor();
    assert.equal(await capture.getByLabel("Tomar foto frente").getAttribute("capture"),"environment");
    assert.equal(await capture.getByLabel("Subir foto frente").getAttribute("capture"),null);
    for (const label of ["Tomar foto frente", "Subir foto frente", "Tomar foto reverso", "Subir foto reverso"]) {
      await touchTarget(capture.getByLabel(label), label);
    }
    assert.ok(await capture.getByRole("button",{name:"Analizar producto",exact:true}).isDisabled());
    await capture.getByLabel("Subir foto frente").setInputFiles({name:"producto.png",mimeType:"image/png",buffer:photo});
    await capture.getByRole("alert").getByText(/La foto supera el límite de carga/).waitFor();
    assert.equal(draft,null,"Upload failure does not create an incomplete product");
    await capture.getByLabel("Tomar foto frente").setInputFiles({name:"camara.png",mimeType:"image/png",buffer:photo});
    await capture.getByAltText("Frente del producto").waitFor();
    const firstFront = draft.front_id;
    await capture.getByLabel("Subir foto frente").setInputFiles({name:"producto.png",mimeType:"image/png",buffer:photo});
    await page.waitForFunction(first => document.querySelector('img[alt="Frente del producto"]')?.getAttribute("src") !== "/api/files/"+first, firstFront);
    assert.notEqual(draft.front_id,firstFront,"Gallery can replace a camera reference");
    await capture.getByAltText("Frente del producto").waitFor();
    await capture.getByLabel("Subir foto reverso").setInputFiles({name:"etiqueta.png",mimeType:"image/png",buffer:photo});
    await capture.getByAltText("Reverso del producto").waitFor();
    await capture.getByRole("button",{name:"Eliminar foto reverso"}).tap();
    await capture.getByAltText("Reverso del producto").waitFor({state:"hidden"});
    await capture.getByRole("button",{name:"Analizar producto",exact:true}).tap();
    for (const label of ["Nombre del producto", "SKU", "Código de barras", "Precio de venta · MXN"]) {
      const input = label === "Precio de venta · MXN"
        ? capture.getByRole("spinbutton",{name:/^Precio de venta · MXN/})
        : capture.getByLabel(label,{exact:true});
      assert.ok(await input.evaluate(element=>parseFloat(getComputedStyle(element).fontSize)>=16),label+" uses readable phone text");
    }
    assert.equal(await capture.getByLabel("SKU",{exact:true}).getAttribute("autocorrect"),"off");
    assert.equal(await capture.getByLabel("SKU",{exact:true}).evaluate(element=>element.readOnly),true);
    assert.equal(await capture.getByLabel("Código de barras",{exact:true}).getAttribute("inputmode"),"numeric");
    await capture.getByLabel("Código de barras",{exact:true}).fill("0 36000-291452");
    await page.waitForFunction(()=>document.querySelector('.capture-embedded input[value="036000291452"]')!==null);
    assert.equal(await capture.getByLabel("SKU",{exact:true}).inputValue(),"036000291452");
    await capture.getByLabel("Código de barras",{exact:true}).fill("");
    await page.waitForFunction(()=>document.querySelector('.capture-embedded input[value="GLIPOC40GX"]')!==null);
    assert.equal(await capture.getByLabel("SKU",{exact:true}).inputValue(),"GLIPOC40GX");
    const price = capture.getByRole("spinbutton",{name:/^Precio de venta · MXN/});
    assert.equal(await price.getAttribute("inputmode"),"decimal");
    await page.setViewportSize({width,height:480});
    await touchTarget(price,"Price in a short viewport");
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),"Short phone viewport stays within the screen");
    await page.setViewportSize({width,height:844});
    await capture.getByLabel("Nombre del producto",{exact:true}).fill("Pocky Chocolate 40 g revisado");
    await capture.getByLabel("¿Algo más que debamos saber?",{exact:false}).fill("Etiqueta verificada manualmente");
    await page.waitForTimeout(1300);
    assert.equal(draft.product.name,"Pocky Chocolate 40 g revisado");
    assert.equal(draft.context,"Etiqueta verificada manualmente");
    await capture.getByLabel("Nombre del producto",{exact:true}).fill("Pocky Chocolate 40 g revisado al salir");
    await nav.getByRole("link",{name:"Inicio",exact:true}).tap();
    await page.waitForTimeout(1300);
    assert.equal(draft.product.name,"Pocky Chocolate 40 g revisado al salir","Switching menus before the debounce preserves the last edit");
    const settled=writes;await page.waitForTimeout(2000);assert.equal(writes,settled,"Autosave settles; no repeated writes without edits");
    for (const name of ["Inicio","Generar","Inventario","Más"]) {
      await nav.getByRole("link",{name,exact:true}).tap();await page.waitForTimeout(150);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${engine}/${width}: ${name} overflow`);
    }
    await page.getByRole("button",{name:"Ajustes",exact:true}).tap();
    const key=capture.getByLabel("Clave de API",{exact:true});
    await key.fill("TEST_ONLY_PERSONAL_KEY_12345");await capture.getByRole("button",{name:"Guardar clave",exact:true}).tap();
    await page.waitForTimeout(250);assert.equal(await key.inputValue(),"");
    assert.ok(!JSON.stringify(await page.evaluate(()=>({...localStorage}))).includes("TEST_ONLY_PERSONAL_KEY"));
    await capture.getByRole("button",{name:"Comprobar clave y modelos"}).tap();
    await capture.getByText(/Modelos consultados sin generar/).waitFor();
    await nav.getByRole("link",{name:"Generar",exact:true}).tap();
    await page.getByRole("button",{name:"Capturar producto",exact:true}).tap();
    assert.equal(await capture.getByLabel("Nombre del producto",{exact:true}).inputValue(),"Pocky Chocolate 40 g revisado al salir");
    await page.reload({waitUntil:"networkidle"});
    await page.getByRole("button",{name:"Capturar producto",exact:true}).tap();
    assert.equal(await capture.getByLabel("Nombre del producto",{exact:true}).inputValue(),"Pocky Chocolate 40 g revisado al salir");
    await capture.getByRole("button",{name:"Verificar coincidencias",exact:true}).tap();
    await capture.getByText("Pocky Fresa 40 g",{exact:true}).waitFor();
    await capture.getByRole("button",{name:"Utilizar padre existente"}).tap();
    assert.equal(await capture.getByLabel("SKU padre",{exact:true}).inputValue(),"GLIPOCFULL");
    await capture.getByRole("button",{name:"Preparar portada de la familia"}).tap();
    await capture.getByAltText("Portada de la familia").waitFor();
    const soundToggle = capture.getByLabel("Sonidos al iniciar, terminar o fallar la generación");
    await touchTarget(soundToggle.locator(".."),"Generation sounds toggle");
    assert.equal(await soundToggle.isChecked(),true);
    assert.deepEqual(await page.evaluate(()=>window.__generationNotes),[],"analysis and family cover do not sound");
    await capture.getByRole("button",{name:"Generar las tres imágenes",exact:true}).tap();
    await capture.getByAltText(/^Imagen comercial de /).waitFor();
    assert.deepEqual(generations[0].slots,["1_hd","2_uso","3_comercial"]);
    assert.equal(generations[0].confirm_cost,true);
    await page.waitForFunction(()=>window.__generationNotes.length===5);
    assert.deepEqual(await page.evaluate(()=>window.__generationNotes),[440,660,660,880,1046]);
    const preserved = {...draft.images};
    const correct = capture.getByRole("button",{name:"Corregir Lifestyle",exact:true});
    await touchTarget(correct,"Correct one image");
    await correct.tap();
    const dialog = capture.getByRole("dialog");
    await page.setViewportSize({width,height:480});
    await dialog.getByLabel("¿Qué quieres cambiar?").fill("Conservar el empaque y corregir los palillos.");
    const apply = dialog.getByRole("button",{name:"Aplicar correcciones",exact:true});
    await touchTarget(apply,"Apply correction in a short viewport");
    await apply.tap();
    await dialog.waitFor({state:"hidden"});
    await capture.getByText("Conexión temporal al consultar el progreso",{exact:true}).waitFor();
    assert.deepEqual((await page.evaluate(()=>window.__generationNotes)).slice(5),[440,660],"polling errors do not announce failure");
    await page.waitForFunction(()=>window.__generationNotes.length===10);
    assert.deepEqual((await page.evaluate(()=>window.__generationNotes)).slice(5),[440,660,660,880,1046]);
    await page.setViewportSize({width,height:844});
    assert.equal(corrections[0].slot,"2_uso");
    assert.equal(corrections[0].confirm_cost,true);
    assert.equal(draft.images["1_hd"].id,preserved["1_hd"].id);
    assert.equal(draft.images["3_comercial"].id,preserved["3_comercial"].id);
    failImage=true;
    await capture.getByRole("button",{name:"Generar las tres imágenes",exact:true}).tap();
    await capture.locator(".feedback.error").getByText("La generación sintética falló",{exact:true}).waitFor();
    await page.waitForFunction(()=>window.__generationNotes.length===15);
    assert.deepEqual((await page.evaluate(()=>window.__generationNotes)).slice(10),[440,660,330,220,165]);
    await soundToggle.uncheck();
    assert.equal(await page.evaluate(()=>localStorage.getItem("rincon-generation-sounds")),"off");
    for (let i=0;i<3;i++) {
      const approve = capture.locator("label.approve-check").filter({hasText:"Aprobar imagen"}).first();
      await touchTarget(approve,"Approve image "+(i+1));
      await approve.tap();
      await page.waitForFunction(count => document.querySelectorAll(".capture-embedded .image-card .approve-check input:checked").length === count, i+1);
    }
    await capture.getByRole("button",{name:"Guardar producto en Drive",exact:true}).tap();
    await capture.getByRole("button",{name:"Reparar catálogo maestro",exact:true}).tap();
    await page.waitForTimeout(250);assert.equal(saves,1,"Repair does not write the primary store twice");
    assert.equal(draft.sync_status,"synced");
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${engine}/${width}: capture overflow`);
    await capture.getByRole("button",{name:"Nuevo producto",exact:true}).tap();
    await capture.getByAltText("Frente del producto").waitFor({state:"hidden"});
    assert.equal(draft,null);
    assert.deepEqual(errors,[]);
    console.log(`Capture ${engine} ${width}px: cold start, touch controls, uploads, edits, settings, family, three slots, correction, sound start/success/failure, polling recovery, mute and repair passed.`);
  } catch (error) {
    fs.mkdirSync(path.join(__dirname,"test-results"),{recursive:true});
    await page.screenshot({path:path.join(__dirname,"test-results",`capture-${engine}-${width}.png`),fullPage:true});
    throw error;
  } finally {await context.close();}
}

(async()=>{
  const server=spawn(process.execPath,[".next/standalone/server.js"],{cwd:path.join(__dirname,"frontend"),env:{...process.env,PORT:"23003",HOSTNAME:"127.0.0.1"},stdio:["ignore","pipe","pipe"]});
  let log="";server.stderr.on("data",c=>log=(log+c).slice(-3000));
  try {
    let started=false;
    for(let i=0;i<100;i++) {try {if((await fetch(origin)).ok){started=true;break;}}catch{} if(server.exitCode!==null)throw Error(log);await new Promise(r=>setTimeout(r,100));}
    assert.ok(started,"Frontend starts");
    for(const engine of process.env.TEST_WEBKIT==="true"?["chromium","webkit"]:["chromium"]) {
      const browser=await playwright[engine].launch({headless:true,...(engine==="chromium"?{args:["--no-sandbox","--disable-dev-shm-usage"],...(process.env.TEST_CHROMIUM_PATH?{executablePath:process.env.TEST_CHROMIUM_PATH}:{})}:{})});
      try {for(const width of [360,390,430])await exercise(browser,engine,width);}finally{await browser.close();}
    }
  } finally {server.kill("SIGTERM");}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
