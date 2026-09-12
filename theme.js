/* Run before the stylesheet to avoid flashing the wrong saved theme. */
window.setMorassTheme = function (value) {
  const theme = value === 'light' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]').content = theme === 'light' ? '#f5f0e4' : '#101713';
};
try { window.setMorassTheme(localStorage.getItem('morass-theme')); }
catch (_) { window.setMorassTheme('dark'); }
