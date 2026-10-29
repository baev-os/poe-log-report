/* Check the summary, original records, and direct links in the standalone report. */
class StabilityBrowserTests {
  static checks = 0;

  static assert(value, message) {
    if (!value) throw new Error(message);

    this.checks++;
  }

  static async run() {
    await document.fonts.ready;

    for (let attempt = 0; innerWidth < 300 && attempt < 20; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 50));
    }

    this.assert(innerWidth >= 300, "Window size is set");

    document.documentElement.style.scrollBehavior = 'auto';
    const root = document.querySelector('[data-stability]');
    const groups = [...root.querySelectorAll('.stability-series')];
    const series = document.getElementById('stability-series-504');

    if (new URLSearchParams(location.search).has('direct')) {
      this.assert(series.open, "Direct link expands the run");
    }

    this.assert([...root.querySelectorAll('.counts strong')].map(item => item.textContent).join('|') === '9|8|1|3', "Counts of messages, runs, sessions, and unknown values");
    this.assert(groups.length === 8 && root.querySelectorAll('.stability-record').length === 9, "All repetitions are retained");
    this.assert(series.querySelectorAll('.stability-record').length === 2, "Two identical messages in the run");
    this.assert(root.querySelectorAll('.stability-day').length === 3, "Two days and an unknown date");

    const first = document.getElementById('stability-record-504');
    series.open = true;
    this.assert(first.textContent.includes('Synthetic <Hub & Base>'), "Area is displayed without executable markup");
    this.assert(first.querySelector('a[href*="events/page-2.html"]'), "Source beyond 500 lines");
    this.assert(first.querySelector('a[href*="#session-timeline"]'), "Session-timeline link");
    this.assert(first.textContent.includes('0.25'), "Exact neighboring-loading duration");
    this.assert(root.querySelector('a[href*="maps/2026-09-01/index.html"]'), "Date links to the calendar");

    for (const link of first.querySelectorAll('a[href]')) {
      this.assert(new URL(link.href).searchParams.get('theme') === document.documentElement.dataset.bsTheme, "Themes in links");
    }

    const query = root.querySelector('[data-search="stability"]');
    const category = root.querySelector('[data-category="stability"]');
    category.value = 'render'; category.dispatchEvent(new Event('change'));
    this.assert(groups.filter(item => !item.hidden).length === 3, "Rendering filter counts runs");

    query.value = 'Synthetic <warning & detail>'; query.dispatchEvent(new Event('input'));
    this.assert(groups.every(item => item.hidden), "Search combined with category yields an empty sample");
    this.assert(!root.querySelector('.empty-filter').hidden, "Empty-sample explanation");

    category.value = ''; category.dispatchEvent(new Event('change'));
    this.assert(groups.filter(item => !item.hidden).length === 1, "Original-message search");

    query.value = 'Synthetic <Hub & Base>'; query.dispatchEvent(new Event('input'));
    this.assert(groups.filter(item => !item.hidden).length === 3, "Search also includes areas");

    category.value = 'warning'; category.dispatchEvent(new Event('change'));
    const link = root.querySelector('a[href*="#stability-series-504"]');
    link.click();
    await new Promise(resolve => setTimeout(resolve, 50));

    this.assert(!series.hidden && series.open && query.value === '' && category.value === '', "Anchor clears hiding filters");

    series.open = false; link.click();
    await new Promise(resolve => setTimeout(resolve, 50));

    this.assert(series.open, "Repeated anchor reopens the run");

    const point = root.querySelector('.stability-chart a');
    this.assert(point.getAttribute('aria-label').includes('2026-09-01'), "Accessible point name");

    point.scrollIntoView(); point.focus();
    const tooltip = document.getElementById(point.getAttribute('aria-describedby'));
    this.assert(!tooltip.hidden && tooltip.textContent.includes('2026-09-01'), "Focus shows the tooltip without delay");

    await new Promise(resolve => setTimeout(resolve, 1100));

    this.assert(!tooltip.hidden, "Tooltip persists over time");

    point.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    this.assert(tooltip.hidden, "Escape hides the tooltip");

    point.dispatchEvent(new Event('pointerenter'));
    this.assert(!tooltip.hidden, "Hover shows the tooltip");

    point.dispatchEvent(new MouseEvent('click', {bubbles: true}));
    await new Promise(resolve => setTimeout(resolve, 50));

    this.assert(location.hash === '#stability-day-2026-09-01', "Chart links to day details");
    this.assert(document.getElementById('line-504'), "Existing full chronology is preserved");

    query.focus(); this.assert(document.activeElement === query, "Search is keyboard accessible");

    await new Promise(resolve => setTimeout(resolve, 150));

    this.assert(document.documentElement.scrollWidth <= innerWidth, "No horizontal overflow");

    groups.forEach(item => { item.open = false; });
    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 250));

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => StabilityBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
