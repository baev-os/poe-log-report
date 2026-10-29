/* Check routes in a synthetic local report without network access. */
class LoadingRouteBrowserTests {
  static checks = 0;

  static assert(value, message) {
    if (!value) throw new Error(message);

    this.checks++;
  }

  static async run() {
    await document.fonts.ready;

    // Headless Chrome may send DOMContentLoaded before the window size is set.
    for (let attempt = 0; innerWidth < 300 && attempt < 20; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 50));
    }

    this.assert(innerWidth >= 300, "Browser window size is set");

    document.documentElement.style.scrollBehavior = 'auto';
    const root = document.querySelector('[data-loading-routes]');
    const select = root.querySelector('[data-loading-route-select]');
    const panels = [...root.querySelectorAll('[data-loading-route]')];
    const option = [...select.options].find(item => item.textContent.startsWith('Synthetic <Hideout & Hub> →'));
    const panel = document.getElementById(option.value);
    this.assert(panels.length === 4, "Two directions and two unknown-source routes");
    this.assert(!root.querySelector('[data-loading-route-controls]').hidden, "Route selection is available");

    if (new URLSearchParams(location.search).has('direct')) {
      this.assert(select.value === panel.id && panel.open && !panel.hidden, "Direct record link opens its route");
      this.assert(document.getElementById(location.hash.slice(1)).closest('details') === panel, "Direct link belongs to the route");
    }

    select.value = panel.id; select.dispatchEvent(new Event('change'));
    this.assert(panel.open && !panel.hidden && panels.filter(item => !item.hidden).length === 1, "Selection expands only the selected route");
    this.assert(panel.querySelector('summary').textContent.includes('Synthetic <Hideout & Hub>'), "Name is escaped");

    const overview = [...root.querySelector('table').tBodies[0].rows].find(row => row.cells[0].textContent.startsWith('Synthetic <Hideout & Hub>'));
    this.assert([...overview.cells].slice(1).map(cell => cell.textContent).join('|') === '2|3.75|1.875|2.5|2.5', "Exact summary metrics");

    const rows = panel.querySelector('.loading-route-records').tBodies[0].rows;
    this.assert(rows.length === 2 && rows[0].cells[2].textContent === '1.25' && rows[1].cells[2].textContent === '2.5', "All measurements without rounding");
    this.assert(rows[0].cells[1].querySelectorAll('a').length === 2, "Both entries have supporting links");
    this.assert(rows[0].cells[3].querySelector('a').href.includes('/sessions/'), "Session link");
    this.assert(rows[0].cells[4].querySelector('a').href.includes('/events/page-2.html'), "Original message beyond 500 lines");

    const calendar = panel.querySelector('a[href*="maps/2026-09-02/"]');
    this.assert(Boolean(calendar), "Daily summary links to the calendar");

    for (const link of panel.querySelectorAll('a[href]')) {
      this.assert(new URL(link.getAttribute('href'), location.href).searchParams.get('theme') === document.documentElement.dataset.bsTheme, "Link preserves the theme");
    }

    const points = panel.querySelectorAll('.loading-route-chart a');
    this.assert(points.length === 4, "Median and P95 for two days");

    const point = points[0];
    this.assert(point.getAttribute('aria-label').includes('2026-09-01'), "Link retains its accessible name after native tooltip removal");

    point.scrollIntoView(); point.focus();
    const tooltip = document.getElementById(point.getAttribute('aria-describedby'));
    this.assert(document.activeElement === point && !tooltip.hidden && tooltip.textContent.includes('2026-09-01'), "Focused date appears without delay");

    await new Promise(resolve => setTimeout(resolve, 1100));

    this.assert(!tooltip.hidden, "Tooltip does not disappear on a timer");

    point.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    this.assert(tooltip.hidden, "Escape hides the tooltip");

    point.dispatchEvent(new Event('pointerenter'));
    this.assert(!tooltip.hidden, "Hover shows the tooltip");

    point.dispatchEvent(new MouseEvent('click', {bubbles: true}));
    await new Promise(resolve => setTimeout(resolve, 50));

    this.assert(document.getElementById(location.hash.slice(1)).cells[0].textContent.includes('2026-09-01'), "Click reaches the daily row");

    select.value = ''; select.dispatchEvent(new Event('change'));
    this.assert(panels.every(item => !item.hidden), "All routes are available again");

    const routeLink = overview.querySelector('a');
    routeLink.click();
    await new Promise(resolve => setTimeout(resolve, 50));

    panel.open = false; routeLink.click();
    await new Promise(resolve => setTimeout(resolve, 50));

    this.assert(panel.open && select.value === panel.id, "Repeated anchor clicks expand the route");

    const unknown = panels.find(item => item.querySelector('small'));
    this.assert(Boolean(unknown), "Unknown links have explanations");

    select.focus(); this.assert(document.activeElement === select, "Selection is keyboard accessible");

    await new Promise(resolve => setTimeout(resolve, 100));

    this.assert(document.documentElement.scrollWidth <= innerWidth, 'No horizontal page overflow: ' + JSON.stringify({width: innerWidth, actual: document.documentElement.scrollWidth, scroll: scrollX, panel: panel.getBoundingClientRect().toJSON()}));

    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 250));

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => LoadingRouteBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
