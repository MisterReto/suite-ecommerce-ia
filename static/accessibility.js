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

  function ensureToolNavStyles(root) {
    if (root.querySelector('style[data-rda-tool-nav-css]')) return;
    const style = document.createElement('style');
    style.dataset.rdaToolNavCss = 'true';
    style.textContent = `
      .rda-tool-nav{display:flex;align-items:center;gap:12px;margin:0 0 14px;padding:9px 11px;background:#fff;border:1px solid #e4e7ec;border-radius:14px;box-shadow:0 1px 2px rgba(16,24,40,.04),0 4px 14px rgba(16,24,40,.05);overflow:hidden}
      .rda-tool-nav-label{flex:0 0 auto;color:#667085;font-size:.76rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;padding:0 4px}
      .rda-tool-nav-links{display:flex;gap:5px;min-width:0;overflow-x:auto;scrollbar-width:thin;padding:1px}
      .rda-tool-link{display:inline-flex;align-items:center;gap:7px;flex:0 0 auto;min-height:40px;padding:8px 11px;border-radius:9px;color:#344054!important;text-decoration:none!important;font-size:.88rem;font-weight:700;white-space:nowrap;border:1px solid transparent;transition:background-color .12s ease,border-color .12s ease,color .12s ease}
      .rda-tool-link:hover{background:#f2f4f7;color:#101828!important}
      .rda-tool-link.is-current{background:#eff4ff;border-color:#d1e0ff;color:#1849a9!important}
      .rda-tool-link:focus-visible{outline:3px solid rgba(46,144,250,.38);outline-offset:2px}
      @media(max-width:720px){.rda-tool-nav{align-items:flex-start;flex-direction:column;gap:6px}.rda-tool-nav-links{width:100%}.rda-tool-nav-label{padding-left:3px}.rda-tool-link{min-height:44px}}
    `;
    root.appendChild(style);
  }

  function addToolNavigation(root) {
    const host = root.querySelector('#tour-app-title');
    if (!host || root.querySelector('.rda-tool-nav')) return;

    const items = [
      { href: '/', icon: '＋', label: 'Nuevo producto', help: 'Capturar y publicar un producto con IA' },
      { href: '/inventory-manager', icon: '📦', label: 'Inventario', help: 'Consultar y ajustar existencias' },
      { href: '/woocommerce-image-preview', icon: '🖼️', label: 'Imágenes', help: 'Revisar imágenes de Drive y WordPress' },
      { href: '/woocommerce-product-sync', icon: '🔄', label: 'WooCommerce', help: 'Sincronizar manualmente un SKU' },
      { href: '/woocommerce-publish-preview', icon: '📊', label: 'Preview stock', help: 'Comparar stock antes de escribir' },
    ];

    const nav = document.createElement('nav');
    nav.className = 'rda-tool-nav';
    nav.setAttribute('aria-label', 'Herramientas de catálogo');

    const heading = document.createElement('span');
    heading.className = 'rda-tool-nav-label';
    heading.textContent = 'Herramientas';
    nav.appendChild(heading);

    const links = document.createElement('div');
    links.className = 'rda-tool-nav-links';

    items.forEach((item) => {
      const link = document.createElement('a');
      link.className = 'rda-tool-link';
      link.href = item.href;
      link.title = item.help;
      link.innerHTML = `<span aria-hidden="true">${item.icon}</span><span>${item.label}</span>`;
      if (window.location.pathname === item.href) {
        link.classList.add('is-current');
        link.setAttribute('aria-current', 'page');
      }
      links.appendChild(link);
    });

    nav.appendChild(links);
    host.insertAdjacentElement('afterend', nav);
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

  function addTutorialAliases(root) {
    const aliases = [
      ['Ajustes', 'Configuración'],
      ['Nuevo producto', 'Ingreso y Edición de Productos'],
      ['Buscar variantes', 'Variantes de Presentación'],
    ];
    root.querySelectorAll('[role="tab"]').forEach((tab) => {
      if (tab.querySelector('.rda-tutorial-alias')) return;
      const visible = (tab.textContent || '').replace(/\s+/g, ' ').trim();
      const match = aliases.find(([needle]) => visible.includes(needle));
      if (!match) return;
      const span = document.createElement('span');
      span.className = 'rda-tutorial-alias';
      span.setAttribute('aria-hidden', 'true');
      span.textContent = ` ${match[1]}`;
      span.style.display = 'none';
      tab.appendChild(span);
    });
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
      ensureToolNavStyles(root);
      addToolNavigation(root);
      markStatus(root);
      addTutorialAliases(root);
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
