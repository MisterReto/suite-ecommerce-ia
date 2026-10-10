// Identidad/estado/etiqueta del job de imagen que se observará para un aviso sonoro.
// Avisos de inicio, éxito y fallo de imagen con Web Audio, consentimiento por gesto y deduplicación.
// Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
type ImageJob = { id: string; status: string; label: string };
const imageLabels = new Set(["Generando imágenes", "Corrigiendo imagen"]);
const notes = {
  start: [440, 660],
  completed: [660, 880, 1046],
  failed: [330, 220, 165],
};

/** One notice per job transition; audio never changes or retries a request. */
// Controlador de avisos de imagen; evita repetir sonidos en cada polling y permite
// silenciarlos.
export class GenerationSounds {
  private context: AudioContext | null = null;
  private output: GainNode | null = null;
  private nextAt = 0;
  private enabled = true;
  private jobs = new Map<string, { started: boolean; terminal: boolean }>();

  constructor(private createContext = (): AudioContext | null => {
    if (typeof window === "undefined") return null;
    const Audio = window.AudioContext || (window as typeof window & {
      webkitAudioContext?: typeof AudioContext;
    }).webkitAudioContext;
    return Audio ? new Audio() : null;
  }) {}

  // Actualiza preferencia y volumen en memoria; el componente conserva el ajuste.
  setEnabled(enabled: boolean) {
    this.enabled = enabled;
    if (this.output) this.output.gain.value = enabled ? 0.08 : 0;
  }

  // Called synchronously by a user gesture, before any API await (also Safari).
  // Desbloquea Web Audio desde un gesto del usuario para que funcione en móvil.
  unlock() {
    if (!this.enabled) return;
    try {
      if (!this.context) {
        this.context = this.createContext();
        if (!this.context) return;
        this.output = this.context.createGain();
        this.output.gain.value = 0.08;
        this.output.connect(this.context.destination);
      }
      if (this.context.state !== "running") void this.context.resume().catch(() => {});
    } catch { /* A browser audio restriction must never block the studio. */ }
  }

  // Compara la transición del job y emite inicio, fin o fallo una sola vez.
  observe(job: ImageJob | null | undefined, initiated = false) {
    if (!job || (!initiated && !imageLabels.has(job.label) && !this.jobs.has(job.id))) return;
    if (!["queued", "running", "completed", "failed"].includes(job.status)) return;
    const state = this.jobs.get(job.id) || { started: false, terminal: false };
    if (state.terminal) return;
    this.jobs.set(job.id, state);
    if (this.jobs.size > 200) this.jobs.delete(this.jobs.keys().next().value!);
    const terminal = job.status === "completed" || job.status === "failed";
    // Restoring an old finished job after a reload is not a new completion.
    if (terminal && !state.started && !initiated) {
      state.terminal = true;
      return;
    }
    if (!state.started) {
      state.started = true;
      this.play(notes.start);
    }
    if (terminal) {
      state.terminal = true;
      this.play(notes[job.status as "completed" | "failed"]);
    }
  }

  // Programa tonos breves por tipo de aviso; no llama a proveedores ni descarga un audio
  // externo.
  private play(frequencies: number[]) {
    const context = this.context;
    if (!this.enabled || !context || !this.output) return;
    // Agenda notas en AudioContext después de asegurar que está operativo.
    const schedule = () => {
      if (!this.enabled || context !== this.context || !this.output) return;
      try {
        const start = Math.max(context.currentTime + 0.02, this.nextAt);
        frequencies.forEach((frequency, index) => {
          const at = start + index * 0.16;
          const oscillator = context.createOscillator();
          const envelope = context.createGain();
          oscillator.type = "sine";
          oscillator.frequency.value = frequency;
          envelope.gain.setValueAtTime(0, at);
          envelope.gain.linearRampToValueAtTime(1, at + 0.012);
          envelope.gain.exponentialRampToValueAtTime(0.001, at + 0.12);
          oscillator.connect(envelope);
          envelope.connect(this.output!);
          oscillator.onended = () => { oscillator.disconnect(); envelope.disconnect(); };
          oscillator.start(at);
          oscillator.stop(at + 0.14);
        });
        this.nextAt = start + frequencies.length * 0.16 + 0.08;
      } catch { /* Sound is optional, including in background tabs. */ }
    };
    try {
      if (context.state !== "running") void context.resume().then(schedule).catch(() => {});
      else schedule();
    } catch { /* Some browsers reject resume synchronously. */ }
  }

  // Cierra el contexto de audio y limpia recursos al desmontar el componente.
  dispose() {
    const context = this.context;
    this.context = null;
    this.output = null;
    this.nextAt = 0;
    try { if (context) void context.close().catch(() => {}); } catch {}
  }
}
