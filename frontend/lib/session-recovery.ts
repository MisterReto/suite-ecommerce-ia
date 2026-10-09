/* Retry readiness and the read-only session endpoint, never writes or OAuth codes. */
// Keep this function self-contained: /login also embeds it in its HTML so
// readiness still runs if React's external chunks cannot load on a cold start.
export async function recoverSession<T extends { authenticated: boolean }>(signal?: AbortSignal): Promise<T> {
  const REQUEST_TIMEOUT_MS = 45_000;
  const RETRY_DELAY_MS = 3_000;
  const MAX_WAIT_MS = 180_000;

  function aborted() { return new DOMException("Recovery cancelled", "AbortError"); }

  async function read(path: string, deadline: number, signal?: AbortSignal) {
    if (signal?.aborted) throw aborted();
    const controller = new AbortController();
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

  function pause(ms: number, signal?: AbortSignal) {
    return new Promise<void>((resolve, reject) => {
      if (signal?.aborted) return reject(aborted());
      const finish = () => { signal?.removeEventListener("abort", cancel); resolve(); };
      const timer = setTimeout(finish, ms);
      const cancel = () => { clearTimeout(timer); signal?.removeEventListener("abort", cancel); reject(aborted()); };
      signal?.addEventListener("abort", cancel, { once: true });
    });
  }

  const deadline = Date.now() + MAX_WAIT_MS;
  while (Date.now() < deadline) {
    const health = await read("/service-health", deadline, signal);
    if (health?.ok === true && health?.backend === "fastapi" && Date.now() < deadline) {
      const session = await read("/api/session", deadline, signal);
      if (typeof session?.authenticated === "boolean") return session as T;
    }
    if (Date.now() >= deadline) break;
    await pause(Math.min(RETRY_DELAY_MS, deadline - Date.now()), signal);
  }
  throw new Error("El servidor aún no está disponible. Puedes reintentar la conexión.");
}
