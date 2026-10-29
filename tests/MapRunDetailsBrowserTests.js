/* Instance card in the standalone report: timeline, context, and links. */
class MapRunDetailsBrowserTests {
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
    const root = document.querySelector('.map-run-report');
    this.assert(root.querySelector('h1').textContent.includes('Synthetic <Dunes & Hills>'), "Name is escaped");
    this.assert(root.querySelectorAll('.map-run-visit').length === 2, "Both visits belong to one instance");
    this.assert(root.querySelectorAll('.map-run-gap').length === 1, "One return gap");
    this.assert(root.querySelectorAll('#loading li').length === 3, "Entry and exit loadings");
    this.assert(root.querySelectorAll('.map-run-issue').length === 1, "Confirmed technical error");
    this.assert(root.querySelector('a[rel="prev"]') && root.querySelector('a[rel="next"]'), "Adjacent maps in the session");
    this.assert(root.querySelector('a[href*="events/page-2.html"]'), "Sources beyond 500 lines");
    this.assert(root.querySelector('a[href*="#session-timeline"]'), "Navigation to session timeline");
    this.assert(root.querySelector('a[href*="#stability-record-"]'), "Fault details");
    this.assert(root.querySelector('[data-run-comparison="all"]').textContent.includes('+00:03:00'), "Median comparison");
    this.assert(root.querySelector('[data-run-comparison="without_afk"]').textContent.includes('00:00:00'), "Comparison without AFK");

    for (const link of root.querySelectorAll('a[href]')) {
      this.assert(new URL(link.getAttribute('href'), location.href).searchParams.get('theme') === document.documentElement.dataset.bsTheme, "Theme in the link");
    }

    if (new URLSearchParams(location.search).has('direct')) {
      this.assert(document.getElementById(location.hash.slice(1))?.classList.contains('map-run-visit'), "Direct visit anchor");
    }

    const chart = root.querySelector('.session-chart');
    const select = root.querySelector('[data-session-zoom]');
    const rect = chart.querySelector('.session-color-map');
    const initial = Number(rect.getAttribute('width'));
    select.value = '4'; select.dispatchEvent(new Event('change'));
    this.assert(Number(rect.getAttribute('width')) > initial * 3, "Zoom changes interval width");
    this.assert(chart.querySelectorAll('[data-session-ticks] text').length > 20, "Detailed time scale");

    root.querySelector('[data-session-reset]').click();
    this.assert(select.value === '1' && Math.abs(Number(rect.getAttribute('width')) - initial) < 1, "Reset zoom");

    const point = rect.closest('a');
    point.scrollIntoView();
    await new Promise(resolve => setTimeout(resolve, 150));

    point.focus({preventScroll: true});
    const tooltip = document.getElementById(point.getAttribute('aria-describedby'));
    this.assert(!tooltip.hidden && tooltip.textContent.includes('2026'), "Instant tooltip with date");

    const scroll = chart.closest('.session-chart-scroll');
    scroll.dispatchEvent(new Event('scroll'));
    this.assert(document.activeElement === point && !tooltip.hidden, "Scrolling preserves the focused tooltip");

    const top = tooltip.style.top;
    chart.style.transform = 'translateY(32px)';
    scroll.dispatchEvent(new Event('scroll'));
    this.assert(!tooltip.hidden && tooltip.style.top !== top, "Focused tooltip follows its moved anchor");
    chart.style.transform = '';
    window.dispatchEvent(new Event('resize'));
    this.assert(document.activeElement === point && !tooltip.hidden, "Resizing preserves the focused tooltip");

    const other = [...chart.querySelectorAll('a')].find(link => link !== point);
    other.focus({preventScroll: true});
    point.focus({preventScroll: true});
    const focusedText = tooltip.textContent;
    other.dispatchEvent(new PointerEvent('pointerleave'));
    this.assert(!tooltip.hidden && tooltip.textContent === focusedText, "A stale leave cannot hide another focused point");
    other.dispatchEvent(new PointerEvent('pointerenter'));
    this.assert(!tooltip.hidden && tooltip.textContent === focusedText, "Focus owns the shared tooltip while another point is hovered");
    point.dispatchEvent(new PointerEvent('pointerleave'));
    this.assert(document.activeElement === point && !tooltip.hidden, "Leaving a focused point preserves its tooltip");

    await new Promise(resolve => setTimeout(resolve, 1100));

    this.assert(!tooltip.hidden, "Tooltip remains while focused");

    point.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    this.assert(tooltip.hidden, "Escape hides the tooltip");
    scroll.dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('resize'));
    this.assert(tooltip.hidden, "Geometry changes do not reopen a dismissed tooltip");

    point.dispatchEvent(new Event('pointerenter'));
    this.assert(!tooltip.hidden, "Hover tooltip");

    const destination = new URL(point.href.baseVal, location.href);
    this.assert(document.getElementById(destination.hash.slice(1)), "Bar links to the visit");

    const gap = chart.querySelector('.session-color-gap').closest('a');
    this.assert(new URL(gap.href.baseVal, location.href).hash.startsWith('#gap-'), "Gap links to details");

    select.focus(); this.assert(document.activeElement === select, "Zoom is keyboard accessible");
    point.dispatchEvent(new PointerEvent('pointerenter'));
    this.assert(!tooltip.hidden, "An unfocused hovered point shows its tooltip");
    scroll.dispatchEvent(new Event('scroll'));
    this.assert(tooltip.hidden, "Scrolling hides a hover-only tooltip");

    point.focus({preventScroll: true});
    select.value = '4'; select.dispatchEvent(new Event('change'));
    this.assert(tooltip.hidden, "An explicit zoom change dismisses the focused tooltip");
    select.value = '1'; select.dispatchEvent(new Event('change'));
    select.focus();

    await new Promise(resolve => setTimeout(resolve, 150));

    this.assert(document.documentElement.scrollWidth <= innerWidth, "No page overflow");

    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 250));

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => MapRunDetailsBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
