// Pantalla local de espera de /login; funciona con script inline aunque los chunks React no carguen.
// Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
import { Loader2, RefreshCw } from "lucide-react";
import { recoverSession } from "@/lib/session-recovery";

// A mobile browser can receive this HTML while a framework chunk is unavailable.
// Readiness and the retry button must work without React hydration.
// Inserta en el HTML una espera autocontenida y un botón Reintentar; no depende de que
// hidrate React.
function bootstrap() {
  return `(() => {
    const recover = ${recoverSession.toString()};
    const title = document.getElementById("login-title");
    const message = document.getElementById("login-message");
    const spinner = document.getElementById("login-spinner");
    const retry = document.getElementById("login-retry");
    let controller;
    let leaving = false;
    async function start() {
      if (controller) controller.abort();
      const attempt = controller = new AbortController();
      title.textContent = "Iniciando servidor";
      message.textContent = "Estamos recuperando tu sesión y preparando la conexión. Esto puede tardar unos minutos.";
      spinner.hidden = false;
      retry.hidden = true;
      retry.style.display = "none";
      try {
        const session = await recover(attempt.signal, true);
        if (!leaving && controller === attempt) {
          // Full navigation preserves the API's HttpOnly cookies on the UI origin.
          window.location.replace(session.authenticated ? "/" : "/auth/start");
        }
      } catch {
        if (!leaving && !attempt.signal.aborted && controller === attempt) {
          title.textContent = "El servidor aún no está disponible";
          message.textContent = "No pudimos conectar en este momento. Puedes volver a intentarlo.";
          spinner.hidden = true;
          retry.hidden = false;
          retry.style.display = "inline-flex";
        }
      }
    }
    retry.addEventListener("click", start);
    window.addEventListener("pagehide", () => {
      leaving = true;
      if (controller) controller.abort();
    });
    window.addEventListener("pageshow", event => {
      if (event.persisted) {
        leaving = false;
        void start();
      }
    });
    void start();
  })();`;
}

// Renderiza Iniciando servidor y el script que decide volver al inicio o empezar OAuth tras
// validar sesión.
export default function ConnectGoogle() {
  return (
    <main style={{ minHeight: "100dvh", display: "grid", placeItems: "center", padding: 24 }}>
      <section style={{ width: "100%", maxWidth: 440, textAlign: "center" }} aria-live="polite">
        <span id="login-spinner"><Loader2 size={36} aria-hidden="true" style={{ margin: "0 auto" }} /></span>
        <h1 id="login-title" style={{ fontSize: 26, margin: "18px 0 12px" }}>Iniciando servidor</h1>
        <p id="login-message">
          Estamos recuperando tu sesión y preparando la conexión. Esto puede tardar unos minutos.
        </p>
        <button id="login-retry" className="button primary" type="button" hidden style={{ display: "none" }}>
          <RefreshCw size={18} aria-hidden="true" /> Reintentar
        </button>
        <p style={{ marginTop: 24 }}><a href="/">Volver al inicio</a></p>
        <noscript>Activa JavaScript para preparar la conexión con Google.</noscript>
      </section>
      <script dangerouslySetInnerHTML={{ __html: bootstrap() }} />
    </main>
  );
}
