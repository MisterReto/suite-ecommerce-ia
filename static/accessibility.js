(() => {
  'use strict';

  // Use light mode by default, independently of the device appearance.
  // Keep an explicitly requested theme and preserve OAuth/query parameters.
  const themeUrl = new URL(window.location.href);
  if (!themeUrl.searchParams.has('__theme')) {
    themeUrl.searchParams.set('__theme', 'light');
    window.location.replace(themeUrl.href);
    return;
  }

  document.title = 'Suite e-commerce';
  const icon = document.querySelector('link[rel="icon"]') || document.createElement('link');
  icon.rel = 'icon';
  icon.href = '/suite-static/rincon-logo.png';
  document.head.appendChild(icon);
  let syncBase = '';
  fetch('/service-health').then(r => r.json()).then(config => {
    syncBase = config.sync_url || '';
    document.querySelectorAll('.rda-tool-link').forEach(updateToolLink);
    roots().forEach(root => root.querySelectorAll('.rda-tool-link').forEach(updateToolLink));
  }).catch(() => {});
  const remotePaths = new Set(['/inventory-sync', '/inventory-hub', '/woocommerce-batch-sync', '/woocommerce-image-preview', '/woocommerce-product-sync', '/woocommerce-publish-preview']);
  function updateToolLink(link) {
    const path = new URL(link.href, window.location.href).pathname;
    if (syncBase && remotePaths.has(path)) link.href = syncBase + path;
  }
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
    link.href = '/suite-static/ui.css?v=5';
    link.dataset.rdaUiCss = 'true';
    root.appendChild(link);
  }

  function ensureToolNavStyles(root) {
    if (root.querySelector('style[data-rda-tool-nav-css]')) return;
    const style = document.createElement('style');
    style.dataset.rdaToolNavCss = 'true';
    style.textContent = `
      .rda-tool-nav{max-width:100%;margin:0 0 14px;background:#fff;border:1px solid #e4e7ec;border-radius:14px;box-shadow:0 1px 2px rgba(16,24,40,.04);overflow:hidden}
      .rda-tool-nav-label{display:flex;align-items:center;gap:8px;min-height:44px;box-sizing:border-box;padding:12px 16px;color:#344054;font-size:1rem;font-weight:800;cursor:pointer;list-style:none}
      .rda-tool-nav-label::-webkit-details-marker{display:none}
      .rda-tool-nav-label::after{content:'▾';margin-left:auto;transition:transform .15s}
      .rda-tool-nav[open]>.rda-tool-nav-label::after{transform:rotate(180deg)}
      .rda-tool-nav-label:hover{background:#f2f4f7}
      .rda-tool-nav-links{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:6px;padding:8px;border-top:1px solid #e4e7ec}
      .rda-tool-link{display:flex;align-items:center;gap:8px;min-height:44px;box-sizing:border-box;padding:10px 12px;border-radius:9px;color:#344054!important;text-decoration:none!important;font-size:.9rem;font-weight:700;border:1px solid transparent;overflow-wrap:anywhere}
      .rda-tool-link:hover{background:#f2f4f7;color:#101828!important}
      .rda-tool-link.is-current{background:#eff4ff;border-color:#d1e0ff;color:#1849a9!important}
      .rda-tool-link:focus-visible,.rda-tool-nav-label:focus-visible{outline:3px solid rgba(46,144,250,.38);outline-offset:-3px}
      @media(max-width:480px){.rda-tool-nav-links{grid-template-columns:minmax(0,1fr)}.rda-tool-link>span:last-child{min-width:0}}
    `;
    const styleHost = root === document ? document.head : root;
    styleHost.appendChild(style);
  }

  function addToolNavigation(root) {
    const host = root.querySelector('#tour-app-title');
    if (!host || root.querySelector('.rda-tool-nav')) return;

    const items = [
      { href: '/', icon: '＋', label: 'Nuevo producto', help: 'Capturar un producto con IA y guardarlo en Drive' },
      { href: '/inventory-hub', icon: '📦', label: 'Inventario', help: 'Catálogo, movimientos, conteo físico y revisión de WooCommerce en una sola página' },
      { href: '/woocommerce-batch-sync', icon: '🚚', label: 'Subida masiva', help: 'Crear o actualizar productos en paralelo con progreso recuperable' },
      { href: '/woocommerce-image-preview', icon: '🖼️', label: 'Imágenes', help: 'Revisar imágenes de Drive y WordPress' },
    ];

    const nav = document.createElement('details');
    nav.className = 'rda-tool-nav';
    nav.setAttribute('aria-label', 'Herramientas de catálogo');

    const heading = document.createElement('summary');
    heading.className = 'rda-tool-nav-label';
    heading.textContent = '🧰 Herramientas';
    nav.appendChild(heading);

    const links = document.createElement('div');
    links.className = 'rda-tool-nav-links';

    items.forEach((item) => {
      const link = document.createElement('a');
      link.className = 'rda-tool-link';
      link.href = item.href;
      updateToolLink(link);
      link.title = item.help;
      link.innerHTML = `<span aria-hidden="true">${item.icon}</span><span>${item.label}</span>`;
      if (window.location.pathname === item.href) {
        link.classList.add('is-current');
        link.setAttribute('aria-current', 'page');
      }
      links.appendChild(link);
    });

    links.setAttribute('role', 'navigation');
    links.setAttribute('aria-label', 'Herramientas de catálogo');
    nav.appendChild(links);
    nav.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && nav.open) {
        event.preventDefault();
        nav.open = false;
        heading.focus();
      }
    });
    document.addEventListener('click', (event) => {
      if (nav.open && !event.composedPath().includes(nav)) nav.open = false;
    });
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
      text.textContent = 'Cuando los datos y las imágenes estén correctos, guarda el producto. Se añadirá a Lista completa Luego puedes publicarlo desde la herramienta Sincronizar SKU.';
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
