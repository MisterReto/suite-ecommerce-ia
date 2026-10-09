"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { recoverSession } from "@/lib/session-recovery";

export default function ConnectGoogle() {
  const [attempt, setAttempt] = useState(0);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let stopped = false;
    const controller = new AbortController();
    setUnavailable(false);
    void recoverSession(controller.signal).then(session => {
      if (!stopped) {
        // Full navigation preserves the API's HttpOnly cookies on the UI origin.
        // Only health probes are retried; never retry an OAuth callback or code.
        window.location.replace(session.authenticated ? "/" : "/auth/start");
      }
    }).catch(() => { if (!stopped) setUnavailable(true); });
    return () => {
      stopped = true;
      controller.abort();
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
            : "Estamos recuperando tu sesión y preparando la conexión. Esto puede tardar unos minutos."}
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
