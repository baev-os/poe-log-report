/* One theme and navigation across all local-report pages. */
class ReportTheme {
  static restore() {
    let theme = new URLSearchParams(location.search).get('theme');
    if (theme !== 'dark' && theme !== 'light') {
      try {
        theme = localStorage.getItem('poe-report-theme');
      } catch {
        // Keep the default dark theme when storage is unavailable.
      }
    }
    document.documentElement.dataset.bsTheme = theme === 'light' ? 'light' : 'dark';
  }

  static sync(toggle = document.querySelector('[data-theme-toggle]')) {
    const theme = document.documentElement.dataset.bsTheme;
    if (toggle) toggle.setAttribute('aria-pressed', String(theme === 'dark'));
    // The URL parameter carries the selection between pages even without localStorage.
    document.querySelectorAll('a[href]').forEach(link => {
      const reference = link.getAttribute('href');
      if (reference.startsWith('#')) return;
      const url = new URL(reference, location.href);
      if (url.pathname.endsWith('.html')) {
        url.searchParams.set('theme', theme);
        link.setAttribute('href', url.href);
      }
    });
  }

  static start() {
    const toggle = document.querySelector('[data-theme-toggle]');
    if (toggle) {
      toggle.hidden = false;
      toggle.addEventListener('click', () => {
        const theme = document.documentElement.dataset.bsTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.bsTheme = theme;
        try {
          localStorage.setItem('poe-report-theme', theme);
        } catch {
          // The browser may prohibit storage for file:// pages.
        }
        ReportTheme.sync(toggle);
      });
    }
    ReportTheme.sync(toggle);
  }
}

ReportTheme.restore();
document.addEventListener('DOMContentLoaded', () => ReportTheme.start());
