/* New observations: numeric results, local evidence, and accessible disclosures. */
class ObservationAnalyticsBrowserTests {
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
    this.assert(root.querySelector('a[href*="events/page-2.html"][href*="#line-"]'), "Evidence beyond the first 500 lines");

    const counts = [...root.querySelectorAll('.counts')][0];
    const values = counts ? [...counts.querySelectorAll('strong')].map(node => node.textContent) : [];

    if (kind === 'network') {
      this.assert(values.join(',') === '4,1,0,0', "Samples and resynchronizations remain separate");
      this.assert(root.querySelectorAll('tr[id^="network-"]').length === 5, "All original messages are available");
      this.assert([...root.querySelectorAll('.analytics-measurement')].some(node => node.querySelectorAll('dd')[4].textContent.startsWith('30 ')), "Connection P95 is 30 ms");

      const resync = [...root.querySelectorAll('details table tbody tr')].filter(row => row.cells[1]?.textContent === 'Resyncing');
      this.assert(resync.length > 0 && resync.every(row => row.cells[4].textContent === '—' && row.cells[5].textContent === '—'), "Resyncing does not receive ms units");
    } else if (kind === 'passives') {
      this.assert(values.join(',') === '2,1,1,1,1', "Operations, difference, mastery, and GoldCost");
      this.assert(root.textContent.includes('Synthetic <Node & A>'), "Skill name is escaped");
      this.assert(root.querySelectorAll('tr[id^="passive-"]').length === 5, "Five original operations");
      this.assert(root.textContent.includes('GoldCost 100'), "Recorded cost is retained");
    } else if (kind === 'marker_timing') {
      this.assert(root.querySelector('table').textContent.includes('00:00:11'), "First marker after 11 seconds");
      this.assert(root.querySelector('table').textContent.includes('00:00:45'), "Return marker after 45 seconds");
      this.assert(root.querySelector('table').textContent.includes('00:00:03'), "Time since return is shown separately");
    } else if (kind === 'routes') {
      this.assert(values.join(',') === '4,3,3,1,0', "Transitions, triples, loops, and same instances remain distinct");
      this.assert(root.querySelectorAll('details[id^="route-"]').length === 7, "All proven routes are available");
      this.assert(root.textContent.includes('Synthetic <Map & One>'), "Route names are escaped");
    } else if (kind === 'trade_api') {
      this.assert(values.join(',') === '4,3,2,2', "Ambiguous request_id values are excluded from pairs");

      const metrics = [...root.querySelector('.analytics-measurement').querySelectorAll('dd')].map(node => node.textContent);
      this.assert(metrics[0] === '2' && metrics[1].startsWith('0 ') && metrics[2].startsWith('100 '), "Zero took and median are retained");
      this.assert(root.querySelectorAll('details[id^="api-"]').length === 4, "Four requests retain original variants");
    } else if (kind === 'level_progress') {
      this.assert(root.querySelectorAll('tr[id^="level-progress-"]').length === 3, "First marker, sequential pair, and missing level");
      this.assert(root.querySelector('table').textContent.includes('88 → 89'), "Level pair is retained");
      this.assert(root.querySelector('table').textContent.includes('00:00:22'), "Twenty-two seconds between messages");
      this.assert(root.querySelector('a[href*="events/page-2.html"]'), "Named death is available as evidence");
    } else if (kind === 'presence') {
      this.assert(values.join(',') === '3,2,1,2', "Repeated joined is separate from pairs and unknown endings");
      this.assert(root.querySelectorAll('details[id^="presence-"]').length === 3, "Three observed cases");
      this.assert(root.textContent.includes('00:00:09'), "Confirmed interval lasts nine seconds");
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

document.addEventListener('DOMContentLoaded', () => ObservationAnalyticsBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
