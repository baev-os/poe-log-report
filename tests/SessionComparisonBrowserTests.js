/* Real A/B switching, numeric deltas, provenance, and shared axes through file://. */
class SessionComparisonBrowserTests {
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
    const root = document.querySelector('[data-session-comparison]');
    const a = root.querySelector('[data-session-select="a"]'), b = root.querySelector('[data-session-select="b"]');
    const mode = root.querySelector('[data-comparison-mode]');
    this.assert(!root.querySelector('[data-comparison-controls]').hidden, "A/B selection is available");

    if (new URLSearchParams(location.search).get('direct')) {
      this.assert(a.selectedIndex === 1 && b.selectedIndex === 0 && mode.value === 'without_afk', "Direct link restores selection and mode");

      a.selectedIndex = 0; b.selectedIndex = 1; mode.value = 'all'; mode.dispatchEvent(new Event('change'));
    }

    this.assert(a.value !== b.value && a.selectedIndex === 0 && b.selectedIndex === 1, "Unknown IDs are safely replaced");
    this.assert(this.metric('new').join('|') === '7|3|−4|−57,14 %'.replace(',', document.documentElement.lang === 'ru' ? ',' : '.'), "Counts and percentage B − A");
    this.assert(this.metric('median').slice(0, 3).join('|') === '00:01:00|00:02:00|+00:01:00', "Medians and delta");
    this.assert(this.metric('afk').slice(0, 3).join('|') === '00:03:00|00:00:30|−00:02:30', "AFK by session");
    this.assert(this.metric('mechanic:blight')[2] === '0', "Mechanics are compared");

    const types = root.querySelector('[data-comparison-types]');
    this.assert(types.rows.length === 2, "Different levels remain separate");
    this.assert(types.rows[0].cells[1].textContent.includes('00:01:00') && types.rows[0].cells[2].textContent.includes('00:03:00'), "Medians match the same type and level");
    this.assert(types.rows[1].cells[1].textContent === '—' && types.rows[1].cells[3].textContent === '—', "Missing samples do not become zero");
    this.assert(types.textContent.includes('Synthetic <Dunes & Hills>') && !types.querySelector('script'), "Names are escaped");

    const detail = root.querySelector('[data-comparison-card="a"] details');
    detail.querySelector('summary').click();
    this.assert(detail.open && detail.textContent.includes('SyntheticHero'), "Death context expands");

    const source = detail.querySelector('a[href*="events/page-2.html"]');
    this.assert(source && source.href.includes('theme=' + document.documentElement.dataset.bsTheme), "Source beyond 500 lines retains the theme");

    source.focus(); this.assert(document.activeElement === source, "Source is keyboard accessible");

    mode.value = 'without_afk'; mode.dispatchEvent(new Event('change'));
    this.assert(this.metric('outliers').slice(0, 3).join('|') === '1|1|0', "Outliers are recalculated without AFK");
    this.assert(types.rows[0].cells[2].textContent.includes('00:02:45'), "Type median without AFK");
    this.assert(root.querySelector('[data-comparison-card="a"] details').open, "Expansion survives mode changes");

    const charts = [...root.querySelectorAll('[data-comparison-chart] svg')];
    this.assert(charts.length === 2 && charts[0].style.width === charts[1].style.width, "Timeline widths match");
    this.assert(charts[0].querySelector('[data-comparison-ticks]').textContent === charts[1].querySelector('[data-comparison-ticks]').textContent, "Time axes match");

    const endA = charts[0].querySelector('.session-observed'), endB = charts[1].querySelector('.session-observed');
    this.assert(Number(endA.getAttribute('width')) > Number(endB.getAttribute('width')) * 10, "Short sessions are not stretched to longer ones");

    const point = charts[0].querySelector('a'); point.focus();
    const tooltip = document.getElementById(point.getAttribute('aria-describedby'));
    this.assert(!tooltip.hidden && tooltip.textContent.includes('2026'), "Instant tooltip contains the original date");

    await new Promise(resolve => setTimeout(resolve, 800));

    this.assert(!tooltip.hidden, "Tooltip remains while focused");

    point.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    this.assert(tooltip.hidden, "Escape closes the tooltip");

    const zoom = root.querySelector('[data-comparison-zoom]'); zoom.value = '4'; zoom.dispatchEvent(new Event('change'));
    this.assert(charts.every(chart => parseFloat(chart.style.width) >= 4000), "Shared zoom");

    const scrolls = [...root.querySelectorAll('.session-chart-scroll')];
    scrolls[0].scrollLeft = 400; scrolls[0].dispatchEvent(new Event('scroll'));
    this.assert(scrolls[1].scrollLeft === 400, "Synchronized scrolling");

    root.querySelector('[data-session-swap]').click();
    this.assert(this.metric('new').slice(0, 3).join('|') === '3|7|+4', "Swapping A/B reverses delta direction");
    this.assert(this.metric('returns')[3] === '—', "Zero percentage denominator");
    this.assert(new URLSearchParams(location.search).get('a') === a.value, "Selection is stored in the URL");

    const oldB = b.value; b.value = a.value; b.dispatchEvent(new Event('change'));
    this.assert(!root.querySelector('[data-same-session]').hidden && root.querySelector('[data-comparison-result]').hidden, "Identical sessions are explicitly marked");

    b.value = oldB; b.dispatchEvent(new Event('change'));
    this.assert(!root.querySelector('[data-comparison-result]').hidden, "Return to comparison");

    root.querySelector('[data-session-swap]').click();
    zoom.value = '1'; zoom.dispatchEvent(new Event('change'));
    mode.value = 'all'; mode.dispatchEvent(new Event('change'));
    a.focus(); this.assert(document.activeElement === a, "Session selection is keyboard accessible");

    await new Promise(resolve => setTimeout(resolve, 100));

    if (innerWidth > 850) this.assert(root.getBoundingClientRect().top < 80, "No extra gap above the page");

    this.assert(document.documentElement.scrollWidth <= innerWidth, "No horizontal page overflow");
    this.assert(document.querySelectorAll('[id^="chart-tooltip-session-comparison-"]').length === 2, "Tooltips do not accumulate");

    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 250));

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => SessionComparisonBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
