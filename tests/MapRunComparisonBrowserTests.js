/* Instance selection, evidence, and relative scales without a server. */
class MapRunComparisonBrowserTests {
  static checks = 0;

  static assert(value, message) {
    if (!value) throw new Error(message);

    this.checks++;
  }

  static metric(code) {
    return [...document.querySelector(`[data-metric="${code}"]`).cells].slice(1).map(cell => cell.textContent);
  }

  static async run() {
    await document.fonts.ready;

    document.documentElement.style.scrollBehavior = 'auto';
    const root = document.querySelector('[data-map-run-comparison]');
    const a = root.querySelector('[data-run-select="a"]'), b = root.querySelector('[data-run-select="b"]');
    this.assert(!root.querySelector('[data-run-controls]').hidden, "A/B selection is available");
    this.assert(a.options.length === 11 && b.options.length === 11, "Copied logs do not add instances");

    if (new URLSearchParams(location.search).get('direct')) {
      this.assert(a.selectedIndex === 5 && b.selectedIndex === 0, "Direct link restores both runs");
    } else {
      this.assert(a.selectedIndex === 0 && b.selectedIndex === 1, "Unknown IDs are replaced with suitable ones");

      a.selectedIndex = 5; b.selectedIndex = 0; a.dispatchEvent(new Event('change'));
    }

    this.assert(this.metric('map').slice(0, 3).join('|') === '00:04:00|00:01:00|−00:03:00', "Time B − A");
    this.assert(this.metric('afk').slice(0, 3).join('|') === '00:03:00|00:00:00|−00:03:00', "Instance AFK");
    this.assert(this.metric('remaining').slice(0, 3).join('|') === '00:01:00|00:01:00|00:00:00', "Remaining time without AFK");
    this.assert(this.metric('visits').slice(0, 3).join('|') === '2|1|−1', "Visits and returns");
    this.assert(this.metric('gaps').slice(0, 3).join('|') === '00:00:30|00:00:00|−00:00:30', "Return gaps");
    this.assert(this.metric('gap_afk')[0] === '00:00:10', "Gap AFK is identified");
    this.assert(this.metric('loading')[0] === (document.documentElement.lang === 'ru' ? '00:00:05,5' : '00:00:05.5'), "Fractional loading time");
    this.assert(this.metric('issues').slice(0, 3).join('|') === '1|0|−1', "Fault belongs to the correct run");
    this.assert(root.querySelector('[data-run-different-type]').hidden && root.querySelector('[data-run-different-level]').hidden, "Matching type and level");

    const card = root.querySelector('[data-run-card="a"]');
    this.assert(card.textContent.includes('Synthetic <Dunes & Hills>') && !card.querySelector('script'), "Name is escaped");
    this.assert(card.querySelector('a').href.includes('theme=' + document.documentElement.dataset.bsTheme), "Card retains the theme");

    const events = root.querySelector('[data-run-events]');
    this.assert(events.rows.length === 3, "Mechanic, death, and fault");

    const detail = events.querySelector('details'); detail.querySelector('summary').click();
    this.assert(detail.open, "Evidence expands");

    const source = detail.querySelector('a[href*="events/page-2.html"]');
    this.assert(source && source.href.includes('theme=' + document.documentElement.dataset.bsTheme), "Source link beyond 500 lines");

    source.focus(); this.assert(document.activeElement === source, "Source is keyboard accessible");

    const charts = [...root.querySelectorAll('[data-run-chart] svg')];
    this.assert(charts.length === 2 && charts[0].style.width === charts[1].style.width, "Timeline widths match");
    this.assert(charts[0].querySelector('[data-comparison-ticks]').textContent === charts[1].querySelector('[data-comparison-ticks]').textContent, "Shared time axis");

    const origins = charts.map(chart => Number(chart.querySelector('[data-comparison-origin]').getAttribute('x1')));
    this.assert(origins[0] === origins[1] && origins[0] > 70, "First entries align; preceding loading appears to the left");

    const mapsA = charts[0].querySelectorAll('rect.session-color-map'), mapB = charts[1].querySelector('rect.session-color-map');
    this.assert(Math.abs(Number(mapsA[1].getAttribute('width')) - Number(mapB.getAttribute('width'))) < 0.001, "Equal durations have equal widths");
    this.assert(Number(mapsA[0].getAttribute('width')) > Number(mapB.getAttribute('width')) * 2.9, "Short runs are not stretched");

    const point = charts[0].querySelector('a'); point.focus();
    const tooltip = document.getElementById(point.getAttribute('aria-describedby'));
    this.assert(!tooltip.hidden && tooltip.textContent.includes('2026'), "Instant tooltip with original date");
    point.closest('.session-chart-scroll').dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('resize'));
    this.assert(document.activeElement === point && !tooltip.hidden, "Run comparison geometry preserves the focused tooltip");

    await new Promise(resolve => setTimeout(resolve, 1100));

    this.assert(!tooltip.hidden, "Tooltip does not disappear automatically");

    point.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    this.assert(tooltip.hidden, "Escape closes the tooltip");
    point.closest('.session-chart-scroll').dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('resize'));
    this.assert(tooltip.hidden, "Run comparison geometry does not reopen a dismissed tooltip");

    const zoom = root.querySelector('[data-run-zoom]'); zoom.value = '64'; zoom.dispatchEvent(new Event('change'));
    this.assert(charts.every(chart => parseFloat(chart.style.width) >= 64000), "Shared ×64 zoom");

    const scrolls = [...root.querySelectorAll('.session-chart-scroll')];
    scrolls[0].scrollLeft = 400; scrolls[0].dispatchEvent(new Event('scroll'));
    this.assert(scrolls[1].scrollLeft === 400, "Synchronized scrolling");

    root.querySelector('[data-run-swap]').click();
    this.assert(this.metric('map').slice(0, 3).join('|') === '00:01:00|00:04:00|+00:03:00', "Swap A/B");
    this.assert(this.metric('returns')[3] === '—', "Percentage from a zero baseline remains unknown");
    this.assert(new URLSearchParams(location.search).get('a') === a.value, "Selection is saved in the URL");

    b.selectedIndex = 9; b.dispatchEvent(new Event('change'));
    this.assert(!root.querySelector('[data-run-different-type]').hidden && !root.querySelector('[data-run-different-level]').hidden, "Different types and levels are explicit");

    b.selectedIndex = 10; b.dispatchEvent(new Event('change'));
    this.assert(this.metric('map').slice(1).join('|') === '—|—|—', "Unknown time does not become zero");
    this.assert(root.querySelector('[data-run-card="b"] .table-note'), "Incomplete run is marked");

    b.value = a.value; b.dispatchEvent(new Event('change'));
    this.assert(!root.querySelector('[data-run-same]').hidden && root.querySelector('[data-run-result]').hidden, "A run cannot compare with itself");

    a.selectedIndex = 5; b.selectedIndex = 0; a.dispatchEvent(new Event('change'));
    this.assert(!root.querySelector('[data-run-result]').hidden, "Return to comparison");

    zoom.value = '1'; zoom.dispatchEvent(new Event('change'));
    a.focus(); this.assert(document.activeElement === a, "Selection is keyboard accessible");

    await new Promise(resolve => setTimeout(resolve, 100));

    this.assert(document.documentElement.scrollWidth <= innerWidth, "No horizontal page overflow");
    this.assert(document.querySelectorAll('[id^="chart-tooltip-map-run-comparison-"]').length === 2, "Tooltips do not accumulate");

    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 250));

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => MapRunComparisonBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
