/* Seven new analytics: local pages, two time modes, and evidence. */
class SevenAnalyticsBrowserTests {
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
    this.assert(root.querySelectorAll('.analytics-navigation a').length === 29, "All twenty-nine analytics are available");
    this.assert(root.querySelectorAll('.analytics-navigation [aria-current="page"]').length === 1, "Current section is highlighted");
    this.assert(!root.textContent.includes('None'), "Unknown values do not become None");
    this.assert(!root.querySelector('script'), "Data cannot create executable code");
    this.assert(root.querySelector('a[href*="events/page-2.html"][href*="#line-"], a[href*="maps/runs/5"]'), "Evidence beyond 500 lines");

    if (kind === 'cycles') {
      const first = root.querySelector('[data-map-duration-panel="all"] tbody tr');
      this.assert(first.cells[2].textContent === '00:05:00', "Full cycle lasts 300 seconds");
      this.assert(first.textContent.includes('Synthetic <Dunes & Hills>'), "Map name is escaped");
      this.assert(first.querySelector('details').textContent.includes('00:00:06'), "Unknown area time is identified");
    } else if (kind === 'focus') {
      const values = [...root.querySelector('.counts').querySelectorAll('strong')].map(node => node.textContent);
      this.assert(values[0] === '3' && values[1] === '1', "Repeated Lost is counted as a message");
      this.assert(values[2] === '00:00:50' && values[3] === '00:00:50', "Repetition does not shift the pair");
      this.assert(root.querySelectorAll('tr[id^="focus-"]').length === 2, "Confirmed and unknown intervals");
    } else if (kind === 'remaining') {
      const values = [...root.querySelector('.counts').querySelectorAll('strong')].map(node => node.textContent);
      this.assert(values.join(',') === '13,2,11,0', "Observations, absence, and ambiguity remain separate");
      this.assert(root.querySelector('tr[id^="remaining-"]').cells[2].textContent === '0', "Recorded zero is displayed as zero");
      this.assert(root.textContent.includes('Synthetic <Dunes & Hills>'), "Names are displayed as text");
    } else if (kind === 'returns') {
      const first = root.querySelector('[data-map-duration-panel="all"] tbody tr');
      this.assert(first.cells[1].textContent === '1', "One return");
      this.assert(first.cells[2].textContent === '00:01:00' && first.cells[3].textContent === '00:01:00', "First and repeated visits remain separate");
      this.assert(root.textContent.includes('00:00:42'), "Interval before return is measured");
    } else if (kind === 'session_edges') {
      this.assert(root.querySelectorAll('section[id^="edges-"]').length === 3, "Three original sessions");
      this.assert(root.querySelector('.analytics-measurement'), "Measurement distribution is present");
    } else if (kind === 'obstacles') {
      this.assert(root.querySelector('.counts strong').textContent === '4', "Four messages");
      this.assert(root.querySelectorAll('details[id^="obstacle-"]').length === 2, "Two proven runs");
      this.assert(root.textContent.includes('Not enough room for item.'), "Original text is retained");
    } else if (kind === 'marker_intervals') {
      const group = root.querySelector('#marker-blight');
      group.querySelector('summary').click();
      this.assert(group.open, "Group expands");
      this.assert(group.querySelector('.counts strong').textContent === '0', "Median maps strictly between adjacent markers is zero");
      this.assert(group.querySelector('.counts > div:last-child strong').textContent === '7', "Seven maps in the observed unmarked chain");
      this.assert(group.querySelectorAll('table')[0].querySelectorAll('tbody tr').length === 4, "Four completed intervals");
    }

    const select = root.querySelector('[data-map-duration-mode]');

    if (select) {
      this.assert(!select.closest('[data-map-duration-controls]').hidden, "Switch is shown with JS");

      select.focus({preventScroll: true});
      this.assert(document.activeElement === select, "Selection is keyboard accessible");

      for (const mode of ['without_afk', 'all']) {
        select.value = mode;
        select.dispatchEvent(new Event('change', {bubbles: true}));
        const panels = [...root.querySelectorAll('[data-map-duration-panel]')];
        this.assert(panels.filter(node => !node.hidden).length === 1, "One mode is displayed");
        this.assert(!panels.find(node => node.dataset.mapDurationPanel === mode).hidden, "Selected mode is displayed");
      }

      select.value = 'without_afk';
      select.dispatchEvent(new Event('change', {bubbles: true}));
      const anchor = root.querySelector('[data-map-duration-panel="all"] tr[id]');
      location.hash = anchor.id;
      await new Promise(resolve => setTimeout(resolve, 100));

      this.assert(select.value === 'all', "Direct anchor selects the required duration");
    }

    const details = root.querySelector('details');

    if (details) {
      const summary = details.querySelector('summary');
      summary.focus({preventScroll: true});
      this.assert(document.activeElement === summary, "Expansion is keyboard accessible");

      details.open = false;
      summary.click();
      this.assert(details.open, "Measurements expand");
    }

    for (const link of root.querySelectorAll('a[href]')) {
      const url = new URL(link.getAttribute('href'), location.href);
      this.assert(url.protocol === 'file:', "All navigation is local");

      if (url.pathname !== location.pathname) this.assert(url.searchParams.get('theme') === document.documentElement.dataset.bsTheme, "Navigation preserves the theme");
    }

    window.scrollTo(0, 0);
    this.assert(document.documentElement.scrollWidth <= innerWidth, "No horizontal page overflow");

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => SevenAnalyticsBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
