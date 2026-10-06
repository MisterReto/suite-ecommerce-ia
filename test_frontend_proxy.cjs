/* Real Next.js HTTP proxy, private cookies and uploads; no provider requests. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const https = require("node:https");
const crypto = require("node:crypto");
const { spawn, spawnSync } = require("node:child_process");

(async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "rincon-proxy-test-"));
  const key = path.join(temporary, "key.pem"), certificate = path.join(temporary, "cert.pem");
  const generated = spawnSync("openssl", ["req", "-x509", "-newkey", "rsa:2048",
    "-nodes", "-keyout", key, "-out", certificate, "-days", "1",
    "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
    { stdio: ["ignore", "ignore", "pipe"] });
  assert.equal(generated.status, 0, "Generate the local test certificate");
  const origin = "http://127.0.0.1:23000";
  const backend = https.createServer({ key: fs.readFileSync(key), cert: fs.readFileSync(certificate) },
    (request, response) => {
      const url = new URL(request.url, "https://127.0.0.1:24443");
      if (url.pathname === "/login") {
        response.writeHead(307, { Location: "https://accounts.google.com/o/oauth2/v2/auth",
          "Set-Cookie": "oauth_state=test; Secure; HttpOnly; SameSite=Lax; Path=/" });
        return response.end();
      }
      if (url.pathname === "/auth/callback") {
        assert.equal(url.searchParams.get("state"), "test");
        response.writeHead(303, { Location: "/", "Set-Cookie": "session_id=test; Secure; HttpOnly; SameSite=Lax; Path=/" });
        return response.end();
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
  await new Promise(resolve => backend.listen(24443, "127.0.0.1", resolve));
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
    assert.equal(session.status, 200);
    assert.equal(session.headers.get("cache-control"), "no-store");
    assert.equal((await session.json()).cookie, cookie);
    const image = Buffer.alloc(12_020_000, 42);
    const upload = await fetch(origin + "/api/uploads", { method: "POST", body: image,
      headers: { Origin: origin, Cookie: cookie, "Content-Type": "application/octet-stream" } });
    assert.equal(upload.status, 200);
    const received = await upload.json();
    assert.equal(received.path, "/api/uploads", "Preserve API path without slash redirects");
    assert.equal(received.size, image.length, "Preserve a supported 12 MB upload");
    assert.equal(received.digest, crypto.createHash("sha256").update(image).digest("hex"));
    assert.equal(received.cookie, cookie);
    assert.equal(received.origin, origin);
    const login = await fetch(origin + "/login", { redirect: "manual" });
    assert.equal(login.status, 307);
    assert.match(login.headers.get("set-cookie"), /Secure; HttpOnly; SameSite=Lax/);
    assert.equal(login.headers.get("location"), "https://accounts.google.com/o/oauth2/v2/auth");
    const callback = await fetch(origin + "/auth/callback?state=test", { redirect: "manual" });
    assert.equal(callback.status, 303);
    assert.equal(callback.headers.get("location"), "/");
    assert.match(callback.headers.get("set-cookie"), /^session_id=test;/);
    const logout = await fetch(origin + "/logout", { method: "POST", headers: { Origin: origin, Cookie: cookie } });
    assert.equal(logout.status, 200);
    assert.equal((await logout.json()).path, "/logout");
    console.log("Next.js proxy: paths, cookies, OAuth redirects and full 12 MB uploads passed.");
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
