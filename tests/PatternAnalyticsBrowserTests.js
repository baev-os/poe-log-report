/* New observations: numeric results, local evidence, and accessible disclosures. */
class PatternAnalyticsBrowserTests {
  static checks = 0;

  static assert(value, message) {
    if (!value) throw new Error(message);

    this.checks++;
  }

  static async run() {
    await document.fonts.ready;

    const kind = new URL(location.href).searchParams.get('analytics');
    const root = document.querySelector('.analytics-page');
    this.assert(root, "Page exists");
    this.assert(root.querySelectorAll('.analytics-navigation a').length === 29, "All twenty-nine sections are available");
    this.assert(root.querySelectorAll('.analytics-navigation [aria-current="page"]').length === 1, "Current section is highlighted");
    this.assert(!root.textContent.includes('None'), "Unknown values are labeled");
    this.assert(!root.querySelector('script'), "Original messages cannot create scripts");

    if (kind !== 'pool') this.assert(root.querySelector('a[href*="events/page-2.html"][href*="#line-"]'), "Evidence beyond the first 500 lines");

    if (kind === 'pool') {
      this.assert(root.textContent.includes('75 %'), "Leading share is 75 percent");
      this.assert(root.querySelectorAll('meter').length === 2, "Two map types");
      this.assert(root.textContent.includes('Synthetic <Dunes & One>'), "Map name is escaped");
    } else if (kind === 'marker_order') {
      this.assert(root.querySelectorAll('details[id^="marker-path-"]').length === 3, "Two pairs and one triple with a repetition");
      this.assert(root.textContent.includes('blight → bestiary → blight'), "Repeated dialogue is retained");
    } else if (kind === 'acquisitions') {
      const cards = root.querySelectorAll('[data-drawn-card]');
      this.assert(cards.length === 2, "Two original names");
      this.assert(cards[0].cells[1].textContent === '2', "Two repetitions of map A");
      this.assert(root.textContent.includes('Synthetic <Card & A>'), "Map name is escaped");
    } else if (kind === 'fault_intervals') {
      this.assert(root.querySelectorAll('details[id^="fault-client-"]').length >= 3, "Boundaries and complete intervals are retained");
      this.assert(root.textContent.includes('00:00:15'), "Measured interval of 15 seconds");
    } else if (kind === 'filters') {
      const values = [...root.querySelectorAll('.counts strong')].map(node => node.textContent);
      this.assert(values.join(',') === '8,1,4,1,1,2', "Messages, successes, failure, hash changes, and repeats");
      this.assert(root.querySelectorAll('tr[id^="filter-version-"]').length === 8, "All filter events are retained");
      this.assert(root.textContent.includes('404'), "HTTP status is retained");
    }

    const detail = root.querySelector('details');

    if (detail) {
      const summary = detail.querySelector('summary');
      detail.open = false;
      summary.focus({preventScroll: true});
      this.assert(document.activeElement === summary, "Expansion is keyboard accessible");

      summary.click();
      this.assert(detail.open, "Evidence expands");
    }

    for (const link of root.querySelectorAll('a[href]')) {
      const url = new URL(link.getAttribute('href'), location.href);
      this.assert(url.protocol === 'file:', "All links are local");

      if (url.pathname !== location.pathname) this.assert(url.searchParams.get('theme') === document.documentElement.dataset.bsTheme, "Theme is retained");
    }

    window.scrollTo(0, 0);
    this.assert(document.documentElement.scrollWidth <= innerWidth, "No horizontal page overflow");

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => PatternAnalyticsBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
