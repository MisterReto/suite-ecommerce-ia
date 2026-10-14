import { recoverSession } from "./session-recovery";

// Wake only for a user action or an active job. Opaque responses are not readiness.
const wakes = new Map<string, number>();
let readyAt = -Infinity;
let readiness: Promise<void> | undefined;

export function wakeServices(worker = false): void {
  const origins = [process.env.NEXT_PUBLIC_SUITE_API_ORIGIN];
  if (worker) origins.push(process.env.NEXT_PUBLIC_SUITE_WORKER_ORIGIN);
  for (const origin of origins) {
    if (!origin || Date.now() - (wakes.get(origin) ?? -Infinity) < 30_000) continue;
    wakes.set(origin, Date.now());
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 90_000);
    void fetch(origin + "/service-health", {
      mode: "no-cors", credentials: "omit", cache: "no-store",
      redirect: "follow", signal: controller.signal,
    }).catch(() => {}).finally(() => clearTimeout(timer));
  }
}

// Readiness retries GETs before sending a write once. Never replay a paid request.
export async function ensureApiReady(): Promise<void> {
  if (Date.now() - readyAt < 15_000) return;
  if (!readiness) {
    readiness = recoverSession<{ authenticated: boolean }>(undefined, true)
      .then(session => {
        if (!session.authenticated) throw new Error("Vuelve a conectar tu sesión de Google.");
        readyAt = Date.now();
      }).finally(() => { readiness = undefined; });
  }
  return readiness;
}
