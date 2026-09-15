const themeToggle = document.querySelector('.theme-toggle');
if (themeToggle) {
  function updateThemeButton() {
    const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    themeToggle.setAttribute('aria-label', `Switch to ${next} mode`);
    themeToggle.title = `Switch to ${next} mode`;
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
  const params = new URLSearchParams(location.search);
  input.value = (params.get('q') || '').slice(0, 120);
  let tag = (params.get('tag') || '').toLocaleLowerCase().replace(/[^a-z0-9-]/g, '').slice(0, 60);
  const tagNote = document.querySelector('#search-tag');
  function filter(updateUrl) {
    const query = input.value.trim().toLocaleLowerCase();
    /* `tag:no-supports` in the box filters by exact tag; plain words match anywhere. */
    const words = [], tags = tag ? [tag] : [];
    for (const word of query.split(/\s+/).filter(Boolean)) {
      if (word.startsWith('tag:') && word.length > 4) tags.push(word.slice(4)); else words.push(word);
    }
    let count = 0;
    for (const item of items) {
      const itemTags = item.dataset.tags.split(' ');
      item.hidden = !(words.every(word => item.dataset.search.includes(word)) && tags.every(t => itemTags.includes(t)));
      if (!item.hidden) count++;
    }
    const what = [query ? `matching “${input.value.trim()}”` : '', tag ? `tagged “${tag}”` : ''].filter(Boolean).join(' and ');
    status.textContent = `${count} ${count === 1 ? 'design' : 'designs'}${what ? ' ' + what : ' in the collection'}.`;
    if (tagNote) {
      tagNote.hidden = !tag;
      document.querySelector('#search-tag-label').textContent = tag;
    }
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
