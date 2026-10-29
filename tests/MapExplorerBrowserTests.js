/* Check sample controls and shared numeric rules in a real browser. */
class MapExplorerBrowserTests {
  static assert(condition, message) { if (!condition) throw new Error(message); }

  static set(form, fields) {
    for (const [key, value] of Object.entries(fields)) form.elements.namedItem(key).value = value;

    form.dispatchEvent(new Event('input', {bubbles: true}));
  }

  static metric(root, key, group = 'a') { return root.querySelector(`[data-metric="${key}"][data-group="${group}"]`).textContent; }

  static visible(root) { return [...root.querySelectorAll('[data-map-row]')].filter(node => !node.hidden); }

  static async run() {
    await document.fonts.ready;

    document.documentElement.style.scrollBehavior = 'auto';
    const assert = this.assert, root = document.querySelector('[data-map-explorer]');
    const a = root.querySelector('[data-cohort="a"]'), b = root.querySelector('[data-cohort="b"]');
    assert(!a.hidden && b.hidden, "Group initialization");
    assert(this.metric(root, 'count') === '4', "Overall count");
    assert(this.metric(root, 'complete') === '3' && this.metric(root, 'median_seconds') === '00:01:00', "Incomplete measurements are excluded from medians; zero is included");
    assert(this.metric(root, 'map_seconds') === '00:02:28', "Measurement total");
    assert(root.querySelector('[data-explorer-rows]').textContent.includes('<script>'), "Name remains text");
    assert(!root.querySelector('[data-explorer-rows] script') && window.injected === undefined, "Markup does not execute");
    this.set(a, {name: 'dUnEs'});
    assert(this.metric(root, 'count') === '2' && this.metric(root, 'complete') === '1', "Case-insensitive name filter");
    assert(this.metric(root, 'median_seconds') === '00:01:28', "Sample median");
    const toggle = root.querySelector('[data-compare-toggle]'); toggle.click();
    this.set(b, {name: 'city'});
    assert(!b.hidden && this.metric(root, 'median_seconds', 'b') === '00:01:00', "Independent group B");
    assert(this.metric(root, 'median_seconds', 'delta') === '−00:00:28', "Difference B − A");
    assert(root.querySelector('[data-overlap]').textContent === '0', "Independent groups");
    this.set(b, {name: 'dunes'});
    assert(root.querySelector('[data-overlap]').textContent === '2', "Overlap is not hidden");
    this.set(a, {name: '', mechanic: 'blight'});
    assert(this.metric(root, 'count') === '1', "Mechanic");
    this.set(a, {observation: 'without'});
    assert(this.metric(root, 'count') === '3', "Without a recorded marker");
    this.set(a, {mechanic: '', from: '2026-09-02', to: '2026-09-02'});
    assert(this.metric(root, 'count') === '1' && this.metric(root, 'map_seconds') === '00:01:00', "First-entry dates are inclusive");
    this.set(a, {from: '2026-09-04', to: '2026-09-01'});
    assert(!a.querySelector('[data-filter-error]').hidden && this.metric(root, 'count') === '—', "Invalid dates do not retain an old summary");
    assert(root.querySelector('[data-distribution]').hidden, "Invalid ranges do not appear as zero histograms");
    this.set(a, {from: '', to: '', min: '0', max: '0'});
    assert(this.metric(root, 'count') === '1' && this.visible(root)[0].dataset.name === 'Synthetic Zero', "Zero differs from unknown duration");
    this.set(a, {min: '20', max: '10'});
    assert(this.metric(root, 'count') === '—', "Invalid duration range");
    this.set(a, {min: '', max: '', complete: 'no'});
    assert(this.metric(root, 'count') === '1' && this.metric(root, 'median_seconds') === '—', "Incomplete only");
    this.set(a, {complete: '', level: '81'});
    assert(this.metric(root, 'count') === '1', "Area level");
    this.set(a, {level: '', name: 'no match [.*]'});
    assert(this.metric(root, 'count') === '0' && !root.querySelector('[data-no-results]').hidden, "Empty sample");
    a.reset(); await new Promise(resolve => setTimeout(resolve, 20));

    assert(this.metric(root, 'count') === '4', "Form reset");
    const type = [...a.elements.namedItem('type').options].find(option => option.textContent.includes('City'));
    this.set(a, {type: type.value});
    assert(this.metric(root, 'count') === '1', "Type selection uses a stable key");
    this.set(a, {type: ''});
    const sort = root.querySelector('[data-sort]');
    sort.value = 'duration-desc'; sort.dispatchEvent(new Event('change'));
    assert(this.visible(root).map(row => row.dataset.observed === 'yes' ? Number(row.dataset.seconds) : null).join(',') === '88,60,0,', "Sorting puts unknown values last");
    root.querySelector('[data-record-group]').value = 'b'; root.querySelector('[data-record-group]').dispatchEvent(new Event('change'));
    assert(this.visible(root).length === 2, "Group B table");
    toggle.click();
    assert(this.visible(root).length === 4 && b.hidden && root.querySelector('[data-record-group]').value === 'a', "Comparison is disabled");
    const table = root.querySelector('.explorer-records');
    assert(table.getBoundingClientRect().width <= table.parentElement.clientWidth + 1, "Table fits the wide workspace");
    const before = MapExplorer.statistics([{complete: true, seconds: 0, returns: 0}, {complete: true, seconds: 10, returns: 1}, {complete: false, seconds: 50, returns: 0}]);
    assert(before.median_seconds === 5 && before.mean_seconds === 5 && before.map_seconds === 60, "Shared statistics contract");
    const bins = MapExplorer.bins([{complete: true, seconds: 10}], [{complete: true, seconds: 10}]);
    assert(bins.length === 1 && bins[0].a === 1 && bins[0].b === 1, "Equal durations");
    assert(MapExplorer.bins([], []).length === 0, "Empty distribution");
    assert(MapExplorer.duration(3599.9999) === '01:00:00' && MapExplorer.duration(360000) === '100:00:00', "Rounding and long intervals");
    const link = this.visible(root)[0].querySelector('a');
    assert(link.href.includes('theme=' + document.documentElement.dataset.bsTheme), "Links transfer the theme");
    link.focus(); assert(document.activeElement === link, "Links are keyboard accessible");
    a.elements.namedItem('name').focus(); assert(document.activeElement === a.elements.namedItem('name'), "Fields are keyboard accessible");
    const mode = root.querySelector('[data-explorer-duration]');
    mode.value = 'without_afk'; mode.dispatchEvent(new Event('change'));
    assert(this.metric(root, 'map_seconds') === '00:01:18' && this.metric(root, 'median_seconds') === '00:00:18', "AFK is excluded from totals and median");
    assert(this.metric(root, 'complete') === '3', "Zero measurements remain without AFK");
    assert(this.visible(root).map(row => row.dataset.remainingSeconds === '' ? null : Number(row.dataset.remainingSeconds)).join(',') === '60,18,0,', "AFK-free sorting puts unknown values last");
    this.set(a, {min: '20'});
    assert(this.metric(root, 'count') === '1', "Duration filter uses remaining time");
    mode.value = 'all'; mode.dispatchEvent(new Event('change'));
    assert(a.elements.namedItem('min').value === '20' && this.metric(root, 'count') === '2', "Mode preserves filters");
    this.set(a, {min: '', name: 'Dunes'}); toggle.click(); this.set(b, {name: 'City'});
    mode.value = 'without_afk'; mode.dispatchEvent(new Event('change'));
    assert(this.metric(root, 'median_seconds', 'delta') === '+00:00:42', "One mode controls both A/B groups");
    assert(this.metric(root, 'count') === '2' && this.metric(root, 'excluded') === '1', "Unknown duration remains a separate record");
    assert(MapExplorer.statistics([{complete: true, seconds: null, returns: 0}]).map_seconds === null, "Unknown does not become zero");
    assert(MapExplorer.bins([{complete: true, seconds: null}], []).length === 0, "Unknown values are excluded from distributions");
    const selected = this.visible(root).find(row => row.dataset.observed === 'yes');
    assert(selected.querySelector('[data-selected-duration]').textContent === '00:00:18', "Row duration matches the mode");
    mode.focus(); assert(document.activeElement === mode, "Mode is keyboard accessible");
    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 250));

    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: 43, theme: document.documentElement.dataset.bsTheme});
  }
}

document.addEventListener('DOMContentLoaded', () => MapExplorerBrowserTests.run().catch(error => {
  document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message, stack: error.stack});
}));
