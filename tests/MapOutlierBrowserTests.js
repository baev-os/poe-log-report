/* Check outliers, context, and navigation in the generated local report. */
class MapOutlierBrowserTests {
  static checks = 0;

  static assert(value, message) {
    if (!value) throw new Error(message);

    this.checks++;
  }

  static async run() {
    await document.fonts.ready;

    document.documentElement.style.scrollBehavior = 'auto';
    const root = document.getElementById('outliers');
    const all = root.querySelector('[data-outlier-mode="all"]');
    const reduced = root.querySelector('[data-outlier-mode="without_afk"]');
    const select = document.querySelector('[data-map-duration-mode]');
    this.assert(!all.hidden && reduced.hidden, "Initial mode");
    this.assert(all.querySelectorAll('[data-outlier-row]').length === 2, "Two full-duration outliers");

    const first = all.querySelector('[data-outlier-row]');
    this.assert(first.cells[2].textContent === '00:04:00' && first.cells[3].textContent === '00:01:00', "Duration and peer median");
    this.assert(first.cells[4].textContent === '+00:03:00+300.0%' && first.cells[5].textContent === '6', "Deviation and sample size");
    this.assert(first.cells[0].textContent.includes('Synthetic <Dunes & Hills>') && !first.querySelector('script'), "Name is escaped");

    const context = first.nextElementSibling.querySelector('details');
    context.querySelector('summary').click();
    this.assert(context.open, "Context expands");
    this.assert(context.textContent.includes('SyntheticHero') && context.textContent.includes('Blight'), "Death and mechanic");
    this.assert(context.textContent.includes('00:00:30') && context.textContent.includes('00:03:00'), "Gap and AFK");

    const visits = context.querySelectorAll('a[href*="#visit-"]');
    this.assert(visits.length === 2, "Both visits are available");

    const source = context.querySelector('a[href*="events/page-2.html"]');
    this.assert(source && source.href.includes('theme=' + document.documentElement.dataset.bsTheme), "Theme and original-message page");

    source.focus(); this.assert(document.activeElement === source, "Source is keyboard accessible");

    all.querySelector('.outlier-samples summary').click();
    this.assert(all.querySelector('.outlier-samples').open, "Sample composition expands");

    select.value = 'without_afk'; select.dispatchEvent(new Event('change'));
    this.assert(all.hidden && !reduced.hidden, "Mode switching");
    this.assert(reduced.querySelectorAll('[data-outlier-row]').length === 1, "AFK changes the outlier list");
    this.assert(reduced.querySelector('[data-outlier-row]').cells[2].textContent === '00:03:00', "Remaining outlier");

    const target = reduced.querySelector('[data-outlier-row]');
    select.value = 'all'; select.dispatchEvent(new Event('change'));
    location.hash = target.id;
    await new Promise(resolve => setTimeout(resolve, 50));

    this.assert(select.value === 'without_afk' && !reduced.hidden, "Direct link expands the required mode");

    select.value = 'all'; select.dispatchEvent(new Event('change'));
    this.assert(context.open && all.querySelector('.outlier-samples').open, "Expanded details are retained");
    this.assert(document.documentElement.scrollWidth <= innerWidth, "No horizontal page overflow");
    this.assert(all.querySelector('.outlier-table').getBoundingClientRect().width <= all.querySelector('.table-scroll').clientWidth + 1, "Table fits the wide viewport");

    select.focus(); this.assert(document.activeElement === select, "Mode is keyboard accessible");

    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 250));

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: this.checks});
  }
}

document.addEventListener('DOMContentLoaded', () => MapOutlierBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
