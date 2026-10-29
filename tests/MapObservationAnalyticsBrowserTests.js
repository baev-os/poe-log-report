/* Observation analytics through file:// without a network server. */
class MapObservationAnalyticsBrowserTests {
  static checks = 0;

  static assert(value, message) {
    if (!value) throw new Error(message);

    this.checks++;
  }

  static async run() {
    await document.fonts.ready;

    document.documentElement.style.scrollBehavior = 'auto';
    const code = new URL(location.href).searchParams.get('observation');
    const language = document.documentElement.lang;
    const share = language === 'ru' ? '38,46 %' : '38.46 %';
    const root = document.getElementById(code === 'overview' ? 'map-observations' : 'observation-analytics');
    this.assert(root, "Section exists");

    if (code === 'overview') {
      const table = root.querySelector('.observation-counts');
      const link = table.querySelector('a[href*="/blight/"]');
      this.assert(link.textContent === '5', "Five maps with the observation");
      this.assert(link.closest('tr').cells[2].textContent === share, "Shared denominator of 13 maps");
      this.assert(table.querySelectorAll('thead th').length === 3, "Share column");

      const periods = root.querySelector('.observation-periods');
      periods.querySelector('summary').click();
      this.assert(periods.open, "Months expand");
      this.assert(periods.querySelector('a[href*="#day-2026-09-01"]'), "Daily navigation is retained");
    } else {
      const small = code === 'harvest';
      this.assert(root.textContent.includes('Synthetic <Dunes & Hills>'), "Name is displayed as text");
      this.assert(!root.querySelector('script'), "Messages cannot create executable code");
      this.assert(root.querySelectorAll('.counts')[0].children.length === 4, "Share, returns, and death messages");

      if (!small) this.assert(root.querySelector('.counts strong').textContent === share, "Share includes all 13 maps");

      const trend = root.querySelector('[data-observation-trend]');
      trend.querySelector('summary').click();
      this.assert(trend.open, "Trend expands");

      const emptyDay = trend.querySelector('[data-observation-day="2026-09-02"]');
      this.assert(emptyDay.cells[1].textContent === '0 / 1', "Day without a marker is retained");
      this.assert(emptyDay.querySelector('.observation-share-track span').style.width === '0%', "Zero share");

      const method = root.querySelector('[data-observation-method]');
      method.querySelector('summary').click();
      this.assert(method.open, "Methodology is available");

      const select = root.querySelector('[data-map-duration-mode]');
      this.assert(select && !select.parentElement.hidden, "Switch is available");

      for (const mode of ['all', 'without_afk']) {
        select.value = mode;
        select.dispatchEvent(new Event('change'));
        const panel = root.querySelector(`[data-observation-mode="${mode}"]`);
        this.assert(!panel.hidden, "Mode is displayed");
        this.assert([...root.querySelectorAll('[data-observation-mode]')].filter(item => !item.hidden).length === 1, "One mode at a time");

        const pair = panel.querySelector('[data-observation-cohort]');
        this.assert(panel.querySelectorAll('[data-observation-cohort]').length === 1, "Other types and levels remain separate");
        this.assert(pair.cells[1].textContent === (small ? '1 / 1' : '5 / 5'), "Observed-sample size");
        this.assert(pair.cells[3].textContent === (small ? '10 / 10' : '6 / 6'), "Control-sample size");
        this.assert(pair.cells[5].textContent.includes(small ? '—' : mode === 'all' ? '+00:01:00' : '+00:00:30'), "Differences require adequate sample sizes");

        const samples = panel.querySelector('[data-observation-samples]');
        samples.querySelector('summary').click();
        this.assert(samples.open, "Both samples expand");
        this.assert(samples.querySelectorAll('a[href*="maps/runs/"]').length === 11, "Verifiable map links for both groups");

        const link = samples.querySelector('a');
        link.focus({preventScroll: true});
        this.assert(document.activeElement === link, "Links are keyboard accessible");

        samples.querySelector('summary').click();
      }

      const target = 'observation-cohort-all-1';
      location.hash = target;
      await new Promise(resolve => setTimeout(resolve, 100));

      this.assert(select.value === 'all', "Direct anchor selects the required mode");
      this.assert(document.getElementById(target), "Anchor exists");
      this.assert(document.querySelector('.observation-maps a[href*="events/page-2.html"][href*="#line-"]'), "Evidence beyond 500 lines");
      this.assert(document.querySelector('.observation-maps').textContent.includes('SyntheticHero'), "Named death messages");
    }

    for (const link of root.querySelectorAll('a[href]')) {
      const url = new URL(link.getAttribute('href'), location.href);
      this.assert(url.protocol === 'file:', "Local navigation");

      if (url.pathname !== location.pathname) this.assert(url.searchParams.get('theme') === document.documentElement.dataset.bsTheme, "Theme is retained");
    }

    root.scrollIntoView();
    await new Promise(resolve => setTimeout(resolve, 100));

    this.assert(document.documentElement.scrollWidth <= innerWidth, "No horizontal page overflow");

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => MapObservationAnalyticsBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
