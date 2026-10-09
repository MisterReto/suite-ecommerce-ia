/* Real Next.js HTTP proxy, private cookies and uploads; no provider requests. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const https = require("node:https");
const crypto = require("node:crypto");
const vm = require("node:vm");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "rincon-proxy-test-"));
  const key = path.join(temporary, "key.pem"), certificate = path.join(temporary, "cert.pem");
  const generated = spawnSync("openssl", ["req", "-x509", "-newkey", "rsa:2048",
    "-nodes", "-keyout", key, "-out", certificate, "-days", "1",
    "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
    { stdio: ["ignore", "ignore", "pipe"] });
  assert.equal(generated.status, 0, "Generate the local test certificate");
  const origin = "http://127.0.0.1:23000";
  const backend = https.createServer({ key: fs.readFileSync(key), cert: fs.readFileSync(certificate) },
    (request, response) => {
      const url = new URL(request.url, "https://127.0.0.1:24443");
      if (url.pathname === "/login") {
        response.writeHead(307, { Location: "https://accounts.google.com/o/oauth2/v2/auth",
          "Set-Cookie": ["oauth_state=test; Secure; HttpOnly; SameSite=Lax; Path=/",
            "oauth_code_verifier=test-verifier; Secure; HttpOnly; SameSite=Lax; Path=/"] });
        return response.end();
      }
      if (url.pathname === "/service-health") {
        response.writeHead(200, { "Content-Type": "application/json" });
        return response.end(JSON.stringify({ ok: true, backend: "fastapi" }));
      }
      if (url.pathname === "/auth/callback") {
        assert.equal(url.searchParams.get("state"), "test");
        response.writeHead(303, { Location: "/", "Set-Cookie": "session_id=test; Secure; HttpOnly; SameSite=Lax; Path=/" });
        return response.end();
      }
      if (url.pathname === "/api/session") {
        response.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
        return response.end(JSON.stringify({ authenticated: false, cookie: request.headers.cookie }));
      }
      let size = 0;
      const hash = crypto.createHash("sha256");
      request.on("data", chunk => { size += chunk.length; hash.update(chunk); });
      request.on("end", () => {
        response.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
        response.end(JSON.stringify({ path: url.pathname, size, digest: hash.digest("hex"),
          cookie: request.headers.cookie, origin: request.headers.origin }));
      });
    });
  await new Promise(resolve => backend.listen(24443, resolve));
  let output = "", process;
  try {
    process = spawn(global.process.execPath, ["frontend/.next/standalone/server.js"], {
      cwd: __dirname,
      env: { ...global.process.env, HOSTNAME: "127.0.0.1", PORT: "23000",
        NODE_EXTRA_CA_CERTS: certificate },
      stdio: ["ignore", "pipe", "pipe"],
    });
    process.stdout.on("data", chunk => { output = (output + chunk).slice(-5000); });
    process.stderr.on("data", chunk => { output = (output + chunk).slice(-5000); });
    let ready = false;
    for (let attempt = 0; attempt < 100; attempt++) {
      if (process.exitCode !== null) throw new Error("Next.js exited: " + output);
      try {
        const response = await fetch(origin + "/");
        if (response.status === 200) { ready = true; break; }
      } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready, "Next.js should start: " + output);
    const cookie = "session_id=opaque-test-session";
    const session = await fetch(origin + "/api/session", { headers: { Cookie: cookie } });
    assert.equal(session.status, 200, "Proxy response: " + output);
    assert.equal(session.headers.get("cache-control"), "no-store");
    assert.equal((await session.json()).cookie, cookie);
    const image = Buffer.alloc(12_020_000, 42);
    const upload = await fetch(origin + "/api/uploads", { method: "POST", body: image,
      headers: { Origin: origin, Cookie: cookie, "Content-Type": "application/octet-stream" } });
    assert.equal(upload.status, 200, "Upload response: " + output);
    const received = await upload.json();
    assert.equal(received.path, "/api/uploads", "Preserve API path without slash redirects");
    assert.equal(received.size, image.length, "Preserve a supported 12 MB upload");
    assert.equal(received.digest, crypto.createHash("sha256").update(image).digest("hex"));
    assert.equal(received.cookie, cookie);
    assert.equal(received.origin, origin);
    const login = await fetch(origin + "/login", { redirect: "manual" });
    assert.equal(login.status, 200, "Login waiting screen is local, even before API startup");
    const loginHTML = await login.text();
    assert.match(loginHTML, /Iniciando servidor/);
    assert.equal(login.headers.get("cache-control"), "no-store");
    assert.equal(login.headers.get("set-cookie"), null, "Do not create OAuth state while waiting");
    // Execute only the shipped inline bootstrap, with no React/framework files.
    // This also detects accidental module references in the minified function.
    const scripts = [...loginHTML.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(match => match[1]);
    const inline = scripts.find(script => script.trimStart().startsWith("(() =>") && script.includes('"login-retry"'));
    assert.ok(inline, "Readiness must be included in the HTML, before React loads: "
      + JSON.stringify(scripts.map(script => script.slice(0,80))));
    const elements = new Map(["login-title", "login-message", "login-spinner", "login-retry"].map(id =>
      [id, { style: {}, addEventListener() {} }]));
    const navigations = [];
    const wakes = [], sessionChecks = [];
    vm.runInNewContext(inline, {
      AbortController, DOMException, setTimeout, clearTimeout,
      document: { getElementById: id => elements.get(id) },
      window: { location: { replace: value => navigations.push(value) }, addEventListener() {} },
      fetch: (url, options) => {
        if (url.startsWith("https://")) {
          wakes.push({url, options});
          return Promise.resolve(new Response("Render loading", {status:503}));
        }
        if (url.startsWith("/api/session")) sessionChecks.push(url);
        return fetch(origin + url, { ...options, headers: { Cookie: cookie } });
      },
    });
    for (let attempt = 0; !navigations.length && attempt < 100; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    assert.deepEqual(navigations, ["/auth/start"], "Login continues once, without any framework chunk");
    assert.equal(wakes.length, 1, "One direct GET wakes the API while the UI proxy is checked");
    assert.equal(wakes[0].url, "https://localhost:24443/service-health");
    assert.equal(wakes[0].options.credentials, "omit");
    assert.equal(wakes[0].options.mode, "no-cors");
    assert.equal(wakes[0].options.redirect, "follow", "Browser no-cors requests require follow mode");
    assert.equal(wakes[0].options.headers, undefined, "Never forward cookies or infrastructure headers to the wake request");
    assert.deepEqual(sessionChecks, ["/api/session?auth_only=true"], "OAuth readiness does not download Drive images");
    assert.ok(login.headers.get("content-security-policy").includes("connect-src 'self' https://localhost:24443;"));
    const health = await fetch(origin + "/service-health");
    assert.deepEqual(await health.json(), { ok: true, backend: "fastapi" });
    const start = await fetch(origin + "/auth/start", { redirect: "manual" });
    assert.equal(start.status, 307);
    const pendingCookies = start.headers.getSetCookie();
    assert.equal(pendingCookies.length, 2, "Preserve separate state and PKCE cookies");
    assert.ok(pendingCookies.every(cookie => /Secure; HttpOnly; SameSite=Lax/.test(cookie)));
    assert.equal(start.headers.get("location"), "https://accounts.google.com/o/oauth2/v2/auth");
    const callback = await fetch(origin + "/auth/callback?state=test", { redirect: "manual" });
    assert.equal(callback.status, 303);
    assert.equal(callback.headers.get("location"), "/");
    assert.match(callback.headers.get("set-cookie"), /^session_id=test;/);
    const logout = await fetch(origin + "/logout", { method: "POST", headers: { Origin: origin, Cookie: cookie } });
    assert.equal(logout.status, 200);
    assert.equal((await logout.json()).path, "/logout");
    console.log("Next.js proxy: paths, cookies, OAuth redirects and full 12 MB uploads passed.");
  } catch (error) {
    console.error("Next.js server diagnostics: " + output);
    throw error;
  } finally {
    if (process) {
      const closed = new Promise(resolve => process.once("exit", resolve));
      process.kill("SIGTERM");
      await Promise.race([closed, new Promise(resolve => setTimeout(resolve, 5000))]);
      if (process.exitCode === null) process.kill("SIGKILL");
    }
    await new Promise(resolve => backend.close(resolve));
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
