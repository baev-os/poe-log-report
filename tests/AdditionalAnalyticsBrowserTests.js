/* Five file:// analytics pages: localization, themes, and accessibility without a server. */
class AdditionalAnalyticsBrowserTests {
  static checks = 0;

  static assert(value, message) {
    if (!value) throw new Error(message);

    this.checks++;
  }

  static async run() {
    await document.fonts.ready;

    const kind = new URL(location.href).searchParams.get('analytics');
    const root = document.querySelector('.analytics-page');
    this.assert(root, "Analytics page exists");
    this.assert(root.querySelectorAll('.analytics-navigation a').length === 29, "All analytics pages are available");
    this.assert(root.querySelectorAll('.analytics-navigation [aria-current="page"]').length === 1, "Current section is highlighted");
    this.assert(!root.textContent.includes('None'), "No internal None values");
    this.assert(!root.querySelector('script'), "Data cannot create executable code");
    this.assert(root.querySelector('a[href*="events/page-2.html"][href*="#line-"], a[href*="maps/runs/5"]'), "Cards or evidence beyond 500 lines");

    if (kind === 'rhythm') {
      this.assert(root.querySelector('[data-rhythm-session]'), "Session is present");
      this.assert(root.querySelector('[data-rhythm-bin]'), "Half-hour windows are present");
      this.assert(root.querySelector('tbody tr').cells.length === 9, "Time, AFK, hideout, and pace");
    } else if (kind === 'mechanics') {
      this.assert(root.textContent.includes('50') || root.textContent.includes('38'), "Combination shares are displayed");
      this.assert(root.querySelector('a[href*="maps/runs/"]'), "Sets link to maps");
    } else if (kind === 'trading') {
      this.assert(root.textContent.includes('Synthetic <Item & Value>'), "Trade request is escaped");
      this.assert(root.querySelectorAll('tr[id^="trade-"]').length === 5, "Five trade events");
      this.assert(root.querySelectorAll('.counts strong')[0].textContent === '3', "Three confirmed trades");
    } else if (kind === 'consistency') {
      this.assert(root.querySelectorAll('svg').length >= 2, "Charts for both modes");
      this.assert(root.querySelector('svg rect'), "Quartile range is present");
      this.assert(root.querySelector('svg line[tabindex], svg rect[tabindex]') === null, "Decorative primitives are not focusable");

      const box = root.querySelector('.analytics-box[data-chart-tip]');
      box.focus({preventScroll: true});
      const tooltip = document.getElementById(box.getAttribute('aria-describedby'));
      this.assert(!tooltip.hidden && /2026.*\d\d:\d\d:\d\d/.test(tooltip.textContent), "Box-plot tooltip contains week and duration");
      this.assert(/Медиана|Median/.test(tooltip.textContent), "Box-plot statistics are labeled");

      box.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
      this.assert(tooltip.hidden, "Escape closes the box-plot tooltip");

      box.querySelector('rect').dispatchEvent(new PointerEvent('pointermove', {bubbles: true, clientX: 400, clientY: 400}));
      this.assert(!tooltip.hidden, "Hovering over the quartile range shows a tooltip");

      box.blur();
    } else if (kind === 'recovery') {
      this.assert(root.querySelectorAll('tr[id^="disconnect-"]').length === 1, "Duplicate disconnections are excluded");
      this.assert(root.textContent.includes('00:01:00'), "Interval to the next entry");
    }

    const select = root.querySelector('[data-map-duration-mode]');

    if (select) {
      this.assert(!select.closest('[data-map-duration-controls]').hidden, "Switch is available with JS");

      select.focus({preventScroll: true});
      this.assert(document.activeElement === select, "Keyboard accessible");

      for (const mode of ['without_afk', 'all']) {
        select.value = mode;
        select.dispatchEvent(new Event('change', {bubbles: true}));
        const panels = [...root.querySelectorAll('[data-map-duration-panel]')];
        this.assert(panels.filter(panel => !panel.hidden).length === 1, "One mode is displayed");
        this.assert(!panels.find(panel => panel.dataset.mapDurationPanel === mode).hidden, "Selected mode is displayed");
      }
    }

    const details = root.querySelector('details');

    if (details) {
      details.querySelector('summary').click();
      this.assert(details.open, "Original data expands");

      const link = details.querySelector('a');

      if (link) {
        link.focus({preventScroll: true});
        this.assert(document.activeElement === link, "Evidence is keyboard accessible");
      }

      details.querySelector('summary').click();
    }

    for (const link of root.querySelectorAll('a[href]')) {
      const url = new URL(link.getAttribute('href'), location.href);
      this.assert(url.protocol === 'file:', "All navigation is local");

      if (url.pathname !== location.pathname) this.assert(url.searchParams.get('theme') === document.documentElement.dataset.bsTheme, "Theme is retained");
    }

    this.assert(document.documentElement.scrollWidth <= innerWidth, "Page does not overflow the viewport");

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => AdditionalAnalyticsBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
