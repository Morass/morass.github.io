const themeToggle = document.querySelector('.theme-toggle');
if (themeToggle) {
  function updateThemeButton() {
    const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    themeToggle.textContent = next === 'light' ? 'Light mode' : 'Dark mode';
    themeToggle.setAttribute('aria-label', `Switch to ${next} mode`);
  }
  themeToggle.hidden = false;
  updateThemeButton();
  themeToggle.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    window.setMorassTheme(theme);
    try { localStorage.setItem('morass-theme', theme); } catch (_) { /* Storage may be disabled. */ }
    updateThemeButton();
  });
  window.addEventListener('storage', event => {
    if (event.key === 'morass-theme') {
      window.setMorassTheme(event.newValue);
      updateThemeButton();
    }
  });
}

/* Progressive enhancement: the catalogue remains browsable without JavaScript. */
const results = document.querySelector('#search-results');
if (results) {
  const input = document.querySelector('#q');
  const form = input.form;
  const status = document.querySelector('#search-status');
  const items = [...results.querySelectorAll('.search-item')];
  input.value = (new URLSearchParams(location.search).get('q') || '').slice(0, 120);
  function filter(updateUrl) {
    const query = input.value.trim().toLocaleLowerCase();
    const words = query.split(/\s+/).filter(Boolean);
    let count = 0;
    for (const item of items) {
      item.hidden = !words.every(word => item.dataset.search.includes(word));
      if (!item.hidden) count++;
    }
    status.textContent = `${count} ${count === 1 ? 'design' : 'designs'}${query ? ` matching “${input.value.trim()}”` : ' in the collection'}.`;
    document.querySelector('#search-empty').hidden = count !== 0;
    if (updateUrl) {
      const url = new URL(location.href);
      if (query) url.searchParams.set('q', input.value.trim()); else url.searchParams.delete('q');
      history.replaceState(null, '', url);
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); filter(true); });
  input.addEventListener('input', () => filter(true));
  filter(false);
}
