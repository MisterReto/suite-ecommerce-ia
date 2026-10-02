(() => {
  'use strict';
  let context;
  let enabled = true;
  const active = new Set();

  function unlock() {
    if (!enabled) return;
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      context ||= new AudioContext();
      if (context.state === 'suspended') context.resume().catch(() => {});
    } catch (_) { /* Audio must never prevent a generation. */ }
  }

  function play(notes) {
    if (!enabled) return;
    unlock();
    if (!context || context.state !== 'running') return;
    try {
      notes.forEach(([frequency, offset, duration]) => {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        const start = context.currentTime + offset;
        oscillator.type = 'sine';
        oscillator.frequency.value = frequency;
        gain.gain.setValueAtTime(0, start);
        gain.gain.linearRampToValueAtTime(0.10, start + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
        oscillator.start(start);
        oscillator.stop(start + duration + 0.02);
      });
    } catch (_) { /* Browsers without audio support keep working. */ }
  }

  // Resume inside the user gesture, including buttons inside Gradio's shadow root.
  document.addEventListener('pointerdown', unlock, { capture: true });
  document.addEventListener('keydown', unlock, { capture: true });
  window.suiteGenerationSound = {
    setEnabled(value) { enabled = Boolean(value); },
    start(task) {
      if (active.has(task)) return;
      active.add(task);
      play([[440, 0, 0.12], [660, 0.12, 0.15]]);
    },
    finish(task) {
      if (!active.delete(task)) return;
      play([[660, 0, 0.16], [880, 0.16, 0.25]]);
    }
  };
})();
