/* Exercise the real HTTP clients with cold services; no browser or paid provider. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("./frontend/node_modules/typescript");

function scenario(file, options = {}) {
  let now = 1_000_000, health = 0;
  const calls = [], timers = new Set();
  const context = vm.createContext({
    AbortController, DOMException, FormData, console,
    process: { env: {
      NEXT_PUBLIC_SUITE_API_ORIGIN: "https://api.onrender.com",
      NEXT_PUBLIC_SUITE_WORKER_ORIGIN: "https://worker.onrender.com",
    } },
    Date: { now: () => now },
    setTimeout(fn, ms) {
      const token = {};
      timers.add(token);
      if (ms <= 3_000) queueMicrotask(() => {
        if (timers.delete(token)) { now += ms; fn(); }
      });
      return token;
    },
    clearTimeout(token) { timers.delete(token); },
    async fetch(path, init = {}) {
      calls.push({ path, ...init });
      if (path.startsWith("https://")) return {};
      if (path === "/service-health") {
        health++;
        return response(health <= (options.healthFailures ?? 1) ? 503 : 200, { ok: true, backend: "fastapi" });
      }
      if (path === "/api/session?auth_only=true") return response(200, { authenticated: options.authenticated ?? true });
      return response(options.writeStatus ?? 200, { detail: "Write failed", job: { status: "queued" } });
    },
  });
  function response(status, data) {
    return { ok: status === 200, status, headers: { get: () => "application/json" }, json: async () => data };
  }
  function load(source, imports = {}) {
    const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
    context.exports = {};
    context.require = name => imports[name];
    vm.runInContext(js, context);
    return context.exports;
  }
  const recovery = load(fs.readFileSync("frontend/lib/session-recovery.ts", "utf8"));
  const readiness = load(fs.readFileSync("frontend/lib/service-readiness.ts", "utf8"), { "./session-recovery": recovery });
  Object.assign(context, readiness);
  const source = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const nodes = source.statements.filter(node => node.name?.text === "ApiError" || node.name?.text === "api");
  const client = load(nodes.map(node => node.getText(source)).join("\n") + "\nexports.api = api;");
  return { calls, readiness, api: client.api, advance(ms) { now += ms; } };
}

(async () => {
  for (const file of ["frontend/components/CaptureStudio.tsx", "frontend/app/page.tsx"]) {
    const path = file.includes("CaptureStudio") ? "/api/generate" : "/api/platform/generation/jobs";
    const s = scenario(file);
    await s.api(path, "POST", { confirm: true });
    assert.equal(s.calls.filter(call => call.method === "POST").length, 1);
    const writeIndex = s.calls.findIndex(call => call.method === "POST");
    assert.ok(s.calls.slice(0, writeIndex).some(call => call.path === "/api/session?auth_only=true"));
    assert.equal(s.calls.filter(call => call.path === "/service-health").length, 2);
    const wakes = s.calls.filter(call => call.path.startsWith("https://"));
    assert.ok(wakes.some(call => call.path === "https://worker.onrender.com/service-health"));
    assert.ok(wakes.every(call => call.credentials === "omit" && !call.body && !call.headers));
    s.readiness.wakeServices(true);
    const wakeCount = s.calls.length;
    s.readiness.wakeServices(true);
    assert.equal(s.calls.length, wakeCount, "Coalesce active-job wake attempts");
    s.advance(31_000);
    s.readiness.wakeServices(true);
    assert.equal(s.calls.length, wakeCount + 2, "Retry waking both services for active work");

    const failed = scenario(file, { writeStatus: 502 });
    await assert.rejects(failed.api(path, "POST", { confirm: true }));
    assert.equal(failed.calls.filter(call => call.method === "POST").length, 1, "Never replay a write");

    const loggedOut = scenario(file, { authenticated: false });
    await assert.rejects(loggedOut.api(path, "POST", {}));
    assert.equal(loggedOut.calls.filter(call => call.method === "POST").length, 0);
  }
  const save = scenario("frontend/components/CaptureStudio.tsx");
  await save.api("/api/save", "POST", { confirm: true });
  assert.equal(save.calls.filter(call => call.path.includes("worker.onrender.com")).length, 0, "Saving only needs API readiness");
  const slow = scenario("frontend/components/CaptureStudio.tsx", { healthFailures: 13 });
  await slow.api("/api/save", "POST", { confirm: true });
  assert.ok(slow.calls.filter(call => call.path === "https://api.onrender.com/service-health").length > 1,
    "A failed direct API wake can be retried during readiness");
  assert.equal(slow.calls.filter(call => call.method === "POST").length, 1);
  const unavailable = scenario("frontend/components/CaptureStudio.tsx", { healthFailures: 1000 });
  await assert.rejects(unavailable.api("/api/save", "POST", { confirm: true }));
  assert.equal(unavailable.calls.filter(call => call.method === "POST").length, 0, "No write if readiness expires");
  const handlers = {}, deleted = [];
  vm.runInNewContext(fs.readFileSync("frontend/public/sw.js", "utf8"), {
    self: { addEventListener(name, handler) { handlers[name] = handler; }, clients: { claim: async () => {} } },
    caches: { keys: async () => ["rincon-shell-old", "other-app"], delete: async key => deleted.push(key) },
  });
  assert.equal(handlers.fetch, undefined, "No cached shell or script interception");
  let activation;
  handlers.activate({ waitUntil(promise) { activation = promise; } });
  await activation;
  assert.deepEqual(deleted, ["rincon-shell-old"]);
  console.log("PASS: cold API before writes, direct worker wake, queued-work retries, no duplicate writes, no shell cache.");
})().catch(error => { console.error(error); process.exitCode = 1; });
