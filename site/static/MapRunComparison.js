/* Compare prepared runs: select by ID, use safe templates and a shared scale. */
class MapRunComparison {
  constructor(root, interactions) {
    this.root = root;
    this.interactions = interactions;
    this.sources = new Map([...root.querySelectorAll('[data-run-source]')].map(node => [node.dataset.runSource, node]));
    this.selects = ['a', 'b'].map(side => root.querySelector(`[data-run-select="${side}"]`));
    if (!this.selects[0]) return;
    this.zoom = root.querySelector('[data-run-zoom]');
    const params = new URLSearchParams(location.search), ids = [...this.sources.keys()];
    this.selects[0].value = this.sources.has(params.get('a')) ? params.get('a') : ids[0];
    const suggested = this.sources.get(this.selects[0].value).dataset.suggested;
    this.selects[1].value = this.sources.has(params.get('b')) ? params.get('b') : suggested;
    this.selects.forEach(select => select.addEventListener('change', () => this.update()));
    root.querySelector('[data-run-swap]').addEventListener('click', () => {
      [this.selects[0].value, this.selects[1].value] = [this.selects[1].value, this.selects[0].value];
      this.update();
    });
    this.zoom.addEventListener('change', () => this.scale());
    window.addEventListener('resize', () => this.scale());
    root.querySelector('[data-run-controls]').hidden = false;
    this.update();
  }
  static rows(source, selector, field) {
    return new Map([...source.querySelectorAll(selector)].map(node => [node.dataset[field], node]));
  }
  compare(sources) {
    const models = sources.map(source => MapRunComparison.rows(source.content, '[data-run-metric]', 'runMetric'));
    const target = this.root.querySelector('[data-run-metrics]');
    target.replaceChildren();
    models[0].forEach((a, key) => {
      const b = models[1].get(key), row = document.createElement('tr');
      row.dataset.metric = key;
      row.append(a.cells[0].cloneNode(true), a.cells[1].cloneNode(true), b.cells[1].cloneNode(true));
      ComparisonDisplay.differences(row, ComparisonDisplay.number(a), ComparisonDisplay.number(b), a.dataset.kind);
      target.append(row);
    });
    const groups = sources.map(source => MapRunComparison.rows(source.content, '[data-run-event]', 'runEvent'));
    const events = this.root.querySelector('[data-run-events]');
    events.replaceChildren();
    const keys = [...new Set([...groups[0].keys(), ...groups[1].keys()])].sort();
    keys.forEach(key => {
      const [a, b] = groups.map(group => group.get(key)), row = document.createElement('tr');
      row.dataset.event = key;
      row.append((a || b).cells[0].cloneNode(true));
      [a, b].forEach(value => row.append(value ? value.cells[1].cloneNode(true) : ComparisonDisplay.cell('0')));
      ComparisonDisplay.differences(row, a ? Number(a.dataset.value) : 0, b ? Number(b.dataset.value) : 0, 'number');
      events.append(row);
    });
    this.root.querySelector('[data-run-events-empty]').hidden = keys.length > 0;
  }
  update() {
    const ids = this.selects.map(select => select.value), same = ids[0] === ids[1];
    this.root.querySelector('[data-run-same]').hidden = !same;
    this.root.querySelector('[data-run-result]').hidden = same;
    this.hideTooltips();
    const url = new URL(location.href);
    ['a', 'b'].forEach((side, index) => url.searchParams.set(side, ids[index]));
    try { history.replaceState(null, '', url); } catch { /* file:// may restrict the History API. */ }
    if (same) return;
    const sources = ids.map(id => this.sources.get(id));
    const [a, b] = sources.map(source => source.dataset);
    this.root.querySelector('[data-run-different-type]').hidden = !a.area || !b.area || a.area === b.area;
    this.root.querySelector('[data-run-different-level]').hidden = !a.level || !b.level || a.level === b.level;
    this.root.querySelector('[data-run-unknown-identity]').hidden = Boolean(a.area && b.area && a.level && b.level);
    this.compare(sources);
    ['a', 'b'].forEach((side, index) => {
      const card = this.root.querySelector(`[data-run-card="${side}"]`);
      card.replaceChildren(sources[index].content.querySelector('[data-card]').cloneNode(true));
      const container = this.root.querySelector(`[data-run-chart="${side}"]`);
      document.getElementById('chart-tooltip-map-run-comparison-' + side)?.remove();
      container.replaceChildren(sources[index].content.querySelector('[data-chart]').cloneNode(true));
      this.root.querySelector(`[data-run-chart-heading="${side}"]`).textContent = card.querySelector('a').textContent;
      const chart = container.querySelector('svg');
      if (!chart) return;
      this.interactions.setupPointTooltip(chart, 'map-run-comparison-' + side);
      container.querySelector('.session-chart-scroll').addEventListener('scroll', event => {
        this.root.querySelectorAll('.session-chart-scroll').forEach(scroll => {
          if (scroll.scrollLeft !== event.target.scrollLeft) scroll.scrollLeft = event.target.scrollLeft;
        });
        this.hideTooltips();
      });
    });
    this.scale();
    this.interactions.syncTheme(document.querySelector('[data-theme-toggle]'));
  }
  scale() {
    ComparisonDisplay.scale([...this.root.querySelectorAll('[data-run-chart] svg')], Number(this.zoom.value));
    this.hideTooltips();
  }
  hideTooltips() {
    document.querySelectorAll('[id^="chart-tooltip-map-run-comparison-"]').forEach(node => { node.hidden = true; });
  }
}
