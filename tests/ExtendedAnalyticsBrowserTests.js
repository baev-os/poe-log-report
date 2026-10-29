/* New observations: numeric results, local evidence, and accessible disclosures. */
class ExtendedAnalyticsBrowserTests {
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

    if (kind !== 'coverage') this.assert(root.querySelector('a[href*="events/page-2.html"][href*="#line-"]'), "Evidence beyond the first 500 lines");

    if (kind === 'memory') {
      this.assert(root.querySelectorAll('tr[id^="memory-"]:not([id^="memory-source-"])').length === 3, "All three samples are retained");
      this.assert(root.querySelectorAll('svg circle').length === 9, "Chart contains separate original points");

      const point = root.querySelector('svg a');
      point.dispatchEvent(new PointerEvent('pointerenter'));
      const tooltip = document.getElementById(point.getAttribute('aria-describedby'));
      this.assert(tooltip && !tooltip.hidden, "Memory-point tooltip appears immediately");

      point.focus();
      this.assert(!tooltip.hidden, "Focus shows the tooltip");

      point.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
      this.assert(tooltip.hidden, "Escape closes the tooltip");

      point.blur();
      this.assert(root.querySelector('tr[id^="memory-"]:not([id^="memory-source-"])').textContent.includes('0 MB'), "Zero sample is retained");
    } else if (kind === 'startup') {
      this.assert(root.querySelectorAll('tr[id^="startup-"]:not([id^="startup-source-"])').length === 1, "One confirmed startup");
      this.assert(root.querySelector('table').textContent.includes('00:00:10'), "Ten seconds between markers");
    } else if (kind === 'environment') {
      this.assert(root.querySelectorAll('section').length >= 4, "Measurement modes and types remain separate");
      this.assert(root.textContent.includes('Vulkan') && root.textContent.includes('DirectX11'), "Original API values are preserved");
      this.assert(root.querySelector('table').textContent.includes('900'), "Message rate uses four seconds of observation");
    } else if (kind === 'acquisitions') {
      this.assert(root.querySelectorAll('tr[id^="acquisition-"]').length === 4, "Four recorded acquisitions");
      this.assert(root.textContent.includes('Greater Black Scythe Artifact') && root.textContent.includes('Grand Black Scythe Artifact'), "Artifact types remain separate");
    } else if (kind === 'milestones') {
      this.assert(root.querySelectorAll('tr[id^="milestone-"]:not([id^="milestone-source-"])').length === 6, "Six original markers");
      this.assert(root.textContent.includes('Synthetic <Quest & Reward>'), "Quest name is escaped");
      this.assert(root.textContent.includes('01:02:03'), "Played sample is displayed separately");
    } else if (kind === 'coverage') {
      this.assert(root.querySelectorAll('tr[id^="coverage-"]').length === 28, "Coverage of the other 28 analytics");

      const memory = root.querySelector('#coverage-memory');
      this.assert(memory.cells[2].textContent === '3' && memory.cells[3].textContent === '3', "Three eligible samples despite the first sample's unknown area");
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

document.addEventListener('DOMContentLoaded', () => ExtendedAnalyticsBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
