/* Check duration modes, visits, and gap evidence through file://. */
class MapAfkBrowserTests {
  static checks = 0;

  static assert(condition, message) {
    if (!condition) throw new Error(message);

    this.checks++;
  }

  static pace() {
    const select = document.querySelector('[data-map-duration-mode]');
    const panels = [...document.querySelectorAll('[data-map-duration-panel]')];
    this.assert(panels.length === 6 && panels.filter(p => !p.hidden).length === 3, "One mode controls types, rankings, and outliers");
    this.assert(document.querySelector('#rankings [data-map-duration-panel="all"] tbody th').textContent.includes('City'), "Full-duration ranking");

    select.value = 'without_afk'; select.dispatchEvent(new Event('change'));
    this.assert(panels.every(p => p.hidden === (p.dataset.mapDurationPanel !== 'without_afk')), "Both tables switch");
    this.assert(document.querySelector('#types [data-map-duration-panel="without_afk"] .counts strong').textContent === '00:00:39', "Mean after subtracting AFK");
    this.assert(document.querySelector('#rankings [data-map-duration-panel="without_afk"] tbody th').textContent.includes('Dunes'), "Ranking changes after subtracting AFK");

    select.focus(); this.assert(document.activeElement === select, "Switch is keyboard accessible");

    const gap = document.querySelector('#gaps .pace-table tbody tr');
    this.assert(gap.cells[2].textContent === '00:00:32' && gap.cells[3].firstChild.textContent === '00:00:20' && gap.cells[4].textContent === '00:00:12', "Gap breakdown");

    const details = gap.querySelector('details'); details.querySelector('summary').click();
    this.assert(details.open, "Evidence expands");

    const links = [...details.querySelectorAll('a')];
    this.assert(links.length === 2 && links.every(a => a.href.includes('events/page-2.html') && a.hash.startsWith('#line-')), "AFK boundaries link to original lines");
    this.assert(links.every(a => a.href.includes('theme=' + document.documentElement.dataset.bsTheme)), "Evidence retains the theme");

    const history = document.querySelector('#gaps > details'); history.querySelector('summary').click();
    this.assert(history.open && history.querySelectorAll('tbody tr').length === 2, "Complete gap history");
  }

  static area() {
    const counts = [...document.querySelectorAll('.area-detail > .counts')][1];
    this.assert([...counts.querySelectorAll('strong')].map(n => n.textContent).join(',') === '00:01:10,00:00:18,00:00:18,00:00:18', "Card balance and metrics");

    const rows = [...document.querySelectorAll('.area-visit-rows tbody tr')];
    this.assert(rows.length === 2, "Two visits to one instance");
    this.assert(rows.map(r => r.cells[2].textContent).join(',') === '00:00:50,00:00:20', "AFK by visit");
    this.assert(rows.map(r => r.cells[3].textContent).join(',') === '00:00:10,00:00:08', "Remaining time by visit");

    const link = rows[1].cells[6].querySelector('a');
    this.assert(link.href.includes('events/page-2.html') && link.href.includes('theme=' + document.documentElement.dataset.bsTheme), "Visit source retains the theme");

    link.focus(); this.assert(document.activeElement === link, "Source is keyboard accessible");
  }

  static async run() {
    await document.fonts.ready;

    document.documentElement.style.scrollBehavior = 'auto';
    const capture = new URLSearchParams(location.search).get('capture');

    if (capture === 'area') this.area(); else this.pace();

    await new Promise(resolve => setTimeout(resolve, 100));

    this.assert(document.documentElement.scrollWidth <= innerWidth,
      `No horizontal page overflow: ${document.documentElement.scrollWidth}/${innerWidth}`);

    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 250));

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => MapAfkBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
