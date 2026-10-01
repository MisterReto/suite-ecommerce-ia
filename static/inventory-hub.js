document.querySelectorAll('[data-page]').forEach(button => {
  button.addEventListener('click', () => {
    if (button.getAttribute('aria-selected') === 'true') return;
    document.querySelectorAll('[data-page]').forEach(item => item.setAttribute('aria-selected', String(item === button)));
    const frame = document.getElementById('inventory-view');
    frame.title = button.textContent;
    frame.src = button.dataset.page;
  });
});
