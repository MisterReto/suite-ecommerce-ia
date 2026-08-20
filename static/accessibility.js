(() => {
  'use strict';

  const once = new WeakSet();

  function roots() {
    const result = [document];
    const app = document.querySelector('gradio-app');
    if (app && app.shadowRoot) result.push(app.shadowRoot);
    return result;
  }

  function ensureUiStyles(root) {
    if (root === document || root.querySelector('link[data-rda-ui-css]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/ui.css?v=1';
    link.dataset.rdaUiCss = 'true';
    root.appendChild(link);
  }

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

  function fixHiddenTabCopies(root) {
    root.querySelectorAll('[aria-hidden="true"] button, .visually-hidden button').forEach((button) => {
      button.setAttribute('tabindex', '-1');
    });

    root.querySelectorAll('[role="tablist"] button').forEach((button) => {
      const text = (button.textContent || '').replace(/\s+/g, ' ').trim();
      const named = button.getAttribute('aria-label') || button.getAttribute('title') || text;
      if (!named && button.querySelector('svg')) {
        button.setAttribute('aria-label', 'Más secciones');
        button.setAttribute('title', 'Más secciones');
      }
    });
  }

  function enhanceTabs(root) {
    root.querySelectorAll('[role="tablist"]').forEach((tablist) => {
      tablist.setAttribute('aria-label', 'Secciones principales de la aplicación');
      if (once.has(tablist)) return;
      once.add(tablist);
      tablist.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        const tabs = [...tablist.querySelectorAll('[role="tab"]')]
          .filter((el) => !el.disabled && el.getAttribute('tabindex') !== '-1');
        if (!tabs.length) return;
        const active = root.activeElement || document.activeElement;
        const current = tabs.indexOf(active);
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
    let target = null;
    for (const root of roots()) {
      target = root.querySelector('.gradio-container');
      if (target) break;
    }
    if (!target) return;
    if (!target.id) target.id = 'rda-main-content';
    target.setAttribute('role', 'main');
    target.setAttribute('tabindex', '-1');

    const link = document.createElement('a');
    link.className = 'rda-skip-link';
    link.href = `#${target.id}`;
    link.textContent = 'Saltar al contenido principal';
    link.addEventListener('click', () => window.setTimeout(() => target.focus(), 0));
    document.body.prepend(link);
  }

  function improveImages(root) {
    root.querySelectorAll('img').forEach((img) => {
      if (!img.hasAttribute('alt')) img.setAttribute('alt', '');
      img.setAttribute('loading', 'lazy');
    });
  }

  function correctTutorialCopy() {
    const text = document.querySelector('#suite-tour-text');
    if (!text) return;
    if (text.textContent.includes('Gabo nueva')) {
      text.textContent = 'Cuando los datos y las imágenes estén correctos, guarda el producto. Se añadirá a Lista completa y la app intentará crear o actualizar únicamente ese SKU en WooCommerce.';
    }
    if (text.textContent.includes('VER TUTORIAL GUIADO')) {
      text.textContent = text.textContent.replace('VER TUTORIAL GUIADO', 'Ver guía de uso');
    }
  }

  function enhance() {
    document.documentElement.lang = 'es';
    roots().forEach((root) => {
      ensureUiStyles(root);
      markStatus(root);
      fixHiddenTabCopies(root);
      enhanceTabs(root);
      enhanceButtons(root);
      improveImages(root);
    });
    addSkipLink();
    correctTutorialCopy();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhance, { once: true });
  } else {
    enhance();
  }

  const observer = new MutationObserver(() => {
    window.clearTimeout(window.__rdaA11yTimer);
    window.__rdaA11yTimer = window.setTimeout(enhance, 120);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
