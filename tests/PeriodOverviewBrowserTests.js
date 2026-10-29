/* Period overview and accessible navigation on both report entry pages. */
class PeriodOverviewBrowserTests {
  static checks = 0;

  static assert(value, message) {
    if (!value) throw new Error(message);

    this.checks++;
  }

  static async run() {
    await document.fonts.ready;

    document.documentElement.style.scrollBehavior = 'auto';
    const overview = document.getElementById('period-overview');
    this.assert(overview, "Overview exists");
    this.assert(overview.querySelectorAll('[data-overview-highlight]').length === 6, "Daily and session metrics");
    this.assert(overview.textContent.includes('01:43:20'), "Measured 6200 seconds");
    this.assert(overview.textContent.includes('00:03:10'), "AFK is included in total time");
    this.assert(overview.textContent.includes('Synthetic <Dunes & Hills>'), "Escaped name");
    this.assert(overview.querySelectorAll('[data-overview-comparison]').length === 5, "Five comparison metrics");

    const widths = [...overview.querySelectorAll('.overview-distribution a')].map(node => parseFloat(node.style.width));
    // CSSOM rounds percentages when reading style.width.
    this.assert(Math.abs(widths.reduce((a, b) => a + b, 0) - 100) < .001, "Bar totals 100%");
    this.assert(widths.every(width => width > 0), "Zero intervals occupy no bar space");

    for (const link of overview.querySelectorAll('a[href]')) {
      const url = new URL(link.getAttribute('href'), location.href);
      this.assert(url.protocol === 'file:', "Navigation is local");
      this.assert(url.searchParams.get('theme') === document.documentElement.dataset.bsTheme, "Navigation retains the theme");
    }

    const details = overview.querySelector('[data-overview-outliers="all"]');
    details.querySelector('summary').click();
    this.assert(details.open, "Unusually long maps expand");

    const run = details.querySelector('a[href*="maps/runs/"]');
    this.assert(run && details.querySelectorAll('ol li').length === 2, "Two outliers and run links");

    run.focus({preventScroll: true});
    this.assert(document.activeElement === run, "Link is keyboard accessible");

    details.querySelector('summary').click();
    const afk = overview.querySelector('a[href*="#overview-afk"]');
    afk.click();
    this.assert(location.hash === '#overview-afk' && document.getElementById('overview-afk'), "Navigation to AFK balance");

    const initial = overview.textContent;
    const mode = document.querySelector('[data-time-mode]');
    mode.value = 'without_afk'; mode.dispatchEvent(new Event('change'));
    this.assert(overview.textContent === initial, "Overview retains full time when the chart switches");
    this.assert(!document.querySelector('[data-playtime-panel="without_afk"]').hidden, "Existing chart switches");

    mode.value = 'all'; mode.dispatchEvent(new Event('change'));
    overview.querySelector('h2').scrollIntoView();
    await new Promise(resolve => setTimeout(resolve, 150));

    this.assert(document.documentElement.scrollWidth <= innerWidth, "No horizontal overflow");

    for (const cell of overview.querySelectorAll('.overview-comparison td')) {
      const range = document.createRange();
      range.selectNodeContents(cell);
      this.assert(range.getClientRects().length === 1, "Comparison number stays on one line");
    }

    for (const card of overview.querySelectorAll('.overview-highlights article')) {
      this.assert(card.scrollWidth <= card.clientWidth, "Metrics fit their card");
    }

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => PeriodOverviewBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
