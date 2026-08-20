(() => {
  'use strict';

  const once = new WeakSet();

  function markStatus(root) {
    const statusBox = root.querySelector('#process-status');
    if (statusBox) {
      statusBox.setAttribute('role', 'status');
      statusBox.setAttribute('aria-live', 'polite');
      statusBox.setAttribute('aria-atomic', 'true');
      const textarea = statusBox.querySelector('textarea');
      if (textarea) {
        textarea.setAttribute('aria-label', 'Estado del proceso');
        textarea.setAttribute('aria-live', 'polite');
      }
    }

    const login = root.querySelector('#tour-login-status');
    if (login) {
      login.setAttribute('role', 'status');
      login.setAttribute('aria-live', 'polite');
    }
  }

  function enhanceTabs(root) {
    const tablists = root.querySelectorAll('[role="tablist"]');
    tablists.forEach((tablist) => {
      if (once.has(tablist)) return;
      once.add(tablist);
      tablist.setAttribute('aria-label', 'Secciones principales de la aplicación');
      tablist.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        const tabs = [...tablist.querySelectorAll('[role="tab"]')].filter((el) => !el.disabled);
        if (!tabs.length) return;
        const current = tabs.indexOf(document.activeElement);
        if (current < 0) return;
        let next = current;
        if (event.key === 'ArrowRight') next = (current + 1) % tabs.length;
        if (event.key === 'ArrowLeft') next = (current - 1 + tabs.length) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        event.preventDefault();
        tabs[next].focus();
      });
    });
  }

  function enhanceButtons(root) {
    root.querySelectorAll('button').forEach((button) => {
      const text = (button.textContent || '').replace(/\s+/g, ' ').trim();
      if (text && !button.getAttribute('aria-label')) button.setAttribute('aria-label', text);
    });
  }

  function addSkipLink() {
    if (document.querySelector('.rda-skip-link')) return;
    const target = document.querySelector('.gradio-container');
    if (!target) return;
    if (!target.id) target.id = 'rda-main-content';
    target.setAttribute('role', 'main');
    target.setAttribute('tabindex', '-1');

    const link = document.createElement('a');
    link.className = 'rda-skip-link';
    link.href = `#${target.id}`;
    link.textContent = 'Saltar al contenido principal';
    document.body.prepend(link);
  }

  function improveImages(root) {
    root.querySelectorAll('img').forEach((img) => {
      if (!img.hasAttribute('alt')) img.setAttribute('alt', '');
      img.setAttribute('loading', 'lazy');
    });
  }

  function enhance() {
    document.documentElement.lang = 'es';
    const root = document;
    addSkipLink();
    markStatus(root);
    enhanceTabs(root);
    enhanceButtons(root);
    improveImages(root);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhance, { once: true });
  } else {
    enhance();
  }

  // Gradio actualiza gran parte del DOM de forma reactiva; volvemos a aplicar
  // atributos de accesibilidad sin tocar valores ni eventos funcionales.
  const observer = new MutationObserver(() => {
    window.clearTimeout(window.__rdaA11yTimer);
    window.__rdaA11yTimer = window.setTimeout(enhance, 120);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
