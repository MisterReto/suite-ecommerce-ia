// Arranque de API y recuperación acotada de sesión: solo reintenta lecturas GET.
// Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
/* Retry readiness and the read-only session endpoint, never writes or OAuth codes. */
// Keep this function self-contained: /login also embeds it in its HTML so
// readiness still runs if React's external chunks cannot load on a cold start.
// Despierta API sin credenciales y verifica health/sesión por proxy durante un máximo de tres
// minutos; solo reintenta GET.
export async function recoverSession<T extends { authenticated: boolean }>(signal?: AbortSignal, authOnly = false): Promise<T> {
  const REQUEST_TIMEOUT_MS = 45_000;
  const RETRY_DELAY_MS = 3_000;
  const MAX_WAIT_MS = 180_000;

  // Render returned "no-deploy" through the rewrite without waking the API.
  // One direct, credential-free GET triggers startup. Its opaque response is
  // never trusted as readiness: health and session still use the UI proxy.
  const wakeOrigin = process.env.NEXT_PUBLIC_SUITE_API_ORIGIN;
  const wake = new AbortController();
  // Aborta el aviso de arranque directo cuando vence su plazo o se cancela la recuperación.
  const cancelWake = () => wake.abort();
  signal?.addEventListener("abort", cancelWake, { once: true });
  const wakeTimer = setTimeout(cancelWake, REQUEST_TIMEOUT_MS);
  if (wakeOrigin && !signal?.aborted) {
    void fetch(wakeOrigin + "/service-health", {
      mode: "no-cors", credentials: "omit", cache: "no-store",
      // Browsers require redirect="follow" for no-cors. The page's CSP limits
      // connection targets to the configured API; credentials remain omitted.
      redirect: "follow", signal: wake.signal,
    }).catch(() => {}).finally(() => {
      clearTimeout(wakeTimer);
      signal?.removeEventListener("abort", cancelWake);
    });
  } else {
    clearTimeout(wakeTimer);
    signal?.removeEventListener("abort", cancelWake);
  }

  // Crea el error AbortError usado al abandonar/cambiar un intento.
  function aborted() { return new DOMException("Recovery cancelled", "AbortError"); }

  // Lee JSON válido por el dominio frontend con cookie y plazo acotado por petición.
  async function read(path: string, deadline: number, signal?: AbortSignal) {
    if (signal?.aborted) throw aborted();
    const controller = new AbortController();
    // Aborta una lectura cuyo plazo ha vencido o cuya recuperación fue cancelada.
    const cancel = () => controller.abort();
    signal?.addEventListener("abort", cancel, { once: true });
    const timer = setTimeout(cancel, Math.min(REQUEST_TIMEOUT_MS, Math.max(1, deadline - Date.now())));
    try {
      const response = await fetch(path, { cache: "no-store", credentials: "same-origin", signal: controller.signal });
      if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) return null;
      return await response.json();
    } catch {
      if (signal?.aborted) throw aborted();
      return null;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", cancel);
    }
  }

  // Espera entre lecturas conservando la posibilidad de cancelar el intento.
  function pause(ms: number, signal?: AbortSignal) {
    return new Promise<void>((resolve, reject) => {
      if (signal?.aborted) return reject(aborted());
      // Resuelve la espera y limpia el listener de cancelación.
      const finish = () => { signal?.removeEventListener("abort", cancel); resolve(); };
      const timer = setTimeout(finish, ms);
      // Cancela el temporizador y rechaza la espera si el usuario abandona el intento.
      const cancel = () => { clearTimeout(timer); signal?.removeEventListener("abort", cancel); reject(aborted()); };
      signal?.addEventListener("abort", cancel, { once: true });
    });
  }

  const deadline = Date.now() + MAX_WAIT_MS;
  while (Date.now() < deadline) {
    const health = await read("/service-health", deadline, signal);
    if (health?.ok === true && health?.backend === "fastapi" && Date.now() < deadline) {
      const session = await read(authOnly ? "/api/session?auth_only=true" : "/api/session", deadline, signal);
      if (typeof session?.authenticated === "boolean") return session as T;
    }
    if (Date.now() >= deadline) break;
    await pause(Math.min(RETRY_DELAY_MS, deadline - Date.now()), signal);
  }
  throw new Error("El servidor aún no está disponible. Puedes reintentar la conexión.");
}
