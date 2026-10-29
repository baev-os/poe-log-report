/* Switch prepared measurements through file:// without recalculating time in the browser. */
class AfkAnalyticsBrowserTests {
  static checks = [];

  static assert(condition, message) {
    if (!condition) throw new Error(message);

    this.checks.push(message);
  }

  static change(select, value) {
    select.value = value;
    select.dispatchEvent(new Event('change'));
  }

  static async run() {
    document.documentElement.style.scrollBehavior = 'auto';
    await document.fonts.ready;

    await new Promise(resolve => setTimeout(resolve, 100));

    const query = new URLSearchParams(location.search);
    this.assert(document.documentElement.dataset.bsTheme === query.get('theme'), "Theme");
    this.assert(document.documentElement.scrollWidth <= innerWidth + 2,
      `Page width ${document.documentElement.scrollWidth}/${innerWidth}`);

    const mode = document.querySelector('[data-time-mode]');

    if (mode) {
      const visible = () => [...document.querySelectorAll('[data-heatmap-panel]')].filter(node => !node.hidden);
      const select = document.querySelector('[data-heatmap-filter]');
      this.assert(!mode.closest('[data-time-mode-controls]').hidden, "Switch is available");
      this.assert(visible().length === 1 && visible()[0].dataset.heatmapMode === 'all', "Initial mode");

      this.change(mode, 'without_afk');
      this.assert(document.querySelector('[data-playtime-panel="all"]').hidden, "Daily chart switches");
      this.assert(!document.querySelector('[data-playtime-panel="without_afk"]').hidden, "Remaining time is displayed");
      this.assert(visible().length === 1 && visible()[0].dataset.heatmapMode === 'without_afk', "Heatmap switches");

      const cell = visible()[0].querySelector('[data-heatmap-cell]');
      this.assert(cell.tabIndex === 0, "Cell is focusable");

      cell.focus();
      const tip = document.getElementById(cell.getAttribute('aria-describedby'));
      this.assert(!tip.hidden, "Focus shows the tooltip");

      await new Promise(resolve => setTimeout(resolve, 1200));

      this.assert(!tip.hidden, "Tooltip persists");

      cell.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
      this.assert(tip.hidden, "Escape closes the tooltip");

      this.change(select, 'maps');
      this.assert(visible()[0].dataset.heatmapKind === 'maps' && visible()[0].textContent.includes('00:00:10'), "Map AFK");

      this.change(mode, 'all');
      this.assert(visible()[0].dataset.heatmapKind === 'maps' && visible()[0].textContent.includes('00:00:30'), "Filter is retained");

      location.hash = '#heatmap-hideout-without-afk-0-0';
      await new Promise(resolve => setTimeout(resolve, 100));

      this.assert(mode.value === 'without_afk' && select.value === 'hideout', "Anchor selects mode and area");
      this.assert(document.querySelector(location.hash).open, "Anchor expands dates");

      const dateLink = document.querySelector(location.hash + ' a');
      this.assert(new URL(dateLink.href).pathname.endsWith('/maps/2026-09-07/index.html'), "Date links to the calendar");
      this.assert(new URL(dateLink.href).searchParams.get('theme') === query.get('theme'), "Link retains the theme");

      location.hash = '#heatmap-all-6-23';
      await new Promise(resolve => setTimeout(resolve, 100));

      this.assert(mode.value === 'all' && select.value === 'all', "Legacy anchor opens all time");

      this.change(mode, 'without_afk');
      const daily = document.querySelector('[data-playtime-panel="without_afk"] a');
      daily.dispatchEvent(new PointerEvent('pointerenter'));
      this.assert(document.getElementById(daily.getAttribute('aria-describedby')).textContent.includes('00:00:10'), "Daily tooltip without AFK");
      this.assert(new URL(daily.getAttribute('href'), location.href).hash === '#day-2026-09-06', "Bar links to the day");

      document.querySelectorAll('.playtime-tooltip').forEach(node => { node.hidden = true; });
    } else if (document.querySelector('.weekly-report')) {
      this.assert(document.querySelectorAll('.weekly-chart').length === 3, "Three weekly charts");
      this.assert(document.querySelector('.weekly-summary').textContent.includes('360.00'), "Weekly pace without AFK");
      this.assert(document.querySelectorAll('[data-weekly-type] option').length === 3, "Type filter");
    } else {
      const row = document.querySelector('[data-comparison-row="maps_per_hour_without_afk"]');
      this.assert(row && row.textContent.includes('360'), "AFK-free pace comparison");
      this.assert(document.querySelector('[data-comparison-row="afk_share"]'), "AFK-share comparison");
    }

    window.scrollTo({top: 0, left: 0, behavior: 'instant'});
    await new Promise(resolve => setTimeout(resolve, 250));

    return {passed: true, checks: this.checks};
  }
}

document.addEventListener('DOMContentLoaded', () => AfkAnalyticsBrowserTests.run()
  .then(result => { document.querySelector('#browser-checks').textContent = JSON.stringify(result); })
  .catch(error => { document.querySelector('#browser-checks').textContent = JSON.stringify({passed: false, error: String(error)}); }));
