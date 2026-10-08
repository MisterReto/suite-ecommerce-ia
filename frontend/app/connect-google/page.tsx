"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";

const REQUEST_TIMEOUT_MS = 8_000;
const RETRY_DELAY_MS = 3_000;
const MAX_WAIT_MS = 180_000;

export default function ConnectGoogle() {
  const [attempt, setAttempt] = useState(0);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let stopped = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let current: AbortController | undefined;
    const deadline = Date.now() + MAX_WAIT_MS;
    setUnavailable(false);

    async function check() {
      current = new AbortController();
      const timeout = setTimeout(() => current?.abort(), REQUEST_TIMEOUT_MS);
      let ready = false;
      try {
        const response = await fetch("/service-health", {
          cache: "no-store",
          credentials: "same-origin",
          signal: current.signal,
        });
        if (response.ok && response.headers.get("content-type")?.includes("application/json")) {
          const health = await response.json();
          ready = health?.ok === true && health?.backend === "fastapi";
        }
      } catch {
        // A sleeping Render service can return HTML, 502 or a timeout while waking.
      } finally {
        clearTimeout(timeout);
      }
      if (stopped) return;
      if (ready) {
        // Full navigation preserves the API's HttpOnly cookies on the UI origin.
        // Only health probes are retried; never retry an OAuth callback or code.
        window.location.replace("/auth/start");
      } else if (Date.now() >= deadline) {
        setUnavailable(true);
      } else {
        retry = setTimeout(check, RETRY_DELAY_MS);
      }
    }

    void check();
    return () => {
      stopped = true;
      current?.abort();
      clearTimeout(retry);
    };
  }, [attempt]);

  return (
    <main style={{ minHeight: "100dvh", display: "grid", placeItems: "center", padding: 24 }}>
      <section style={{ width: "100%", maxWidth: 440, textAlign: "center" }} aria-live="polite">
        {!unavailable && <Loader2 size={36} aria-hidden="true" style={{ margin: "0 auto" }} />}
        <h1 style={{ fontSize: 26, margin: "18px 0 12px" }}>
          {unavailable ? "El servidor aún no está disponible" : "Iniciando servidor"}
        </h1>
        <p>
          {unavailable
            ? "No pudimos conectar en este momento. Puedes volver a intentarlo."
            : "Estamos preparando la conexión con Google. Esto puede tardar unos minutos."}
        </p>
        {unavailable && (
          <button className="button primary" onClick={() => setAttempt(value => value + 1)}>
            <RefreshCw size={18} aria-hidden="true" /> Reintentar
          </button>
        )}
        <p style={{ marginTop: 24 }}><a href="/">Volver al inicio</a></p>
        <noscript>Activa JavaScript para preparar la conexión con Google.</noscript>
      </section>
    </main>
  );
}
