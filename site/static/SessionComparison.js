/* Select prepared sessions: duration calculations remain in Python; the difference is B minus A. */
class SessionComparison {
  constructor(root, interactions) {
    this.root = root;
    this.interactions = interactions;
    this.sources = new Map([...root.querySelectorAll('[data-comparison-source]')]
      .map(node => [node.dataset.comparisonSource, node.content]));
    this.selects = ['a', 'b'].map(side => root.querySelector(`[data-session-select="${side}"]`));
    if (!this.selects[0]) return;
    this.mode = root.querySelector('[data-comparison-mode]');
    this.zoom = root.querySelector('[data-comparison-zoom]');
    const params = new URLSearchParams(location.search), ids = [...this.sources.keys()];
    this.selects[0].value = this.sources.has(params.get('a')) ? params.get('a') : ids[0];
    this.selects[1].value = this.sources.has(params.get('b')) ? params.get('b') : ids.find(id => id !== this.selects[0].value);
    this.mode.value = params.get('mode') === 'without_afk' ? 'without_afk' : 'all';
    this.selects.forEach(select => select.addEventListener('change', () => this.update()));
    this.mode.addEventListener('change', () => this.update());
    this.zoom.addEventListener('change', () => this.scale());
    root.querySelector('[data-session-swap]').addEventListener('click', () => {
      [this.selects[0].value, this.selects[1].value] = [this.selects[1].value, this.selects[0].value];
      this.update();
    });
    window.addEventListener('resize', () => this.scale(true));
    root.querySelector('[data-comparison-controls]').hidden = false;
    this.update();
  }
  compare(sources) {
    const models = sources.map(source => source.querySelector(`[data-source-mode="${this.mode.value}"]`));
    const metrics = this.root.querySelector('[data-comparison-metrics]');
    metrics.replaceChildren();
    const bMetrics = new Map([...models[1].querySelectorAll('[data-session-metric]')].map(node => [node.dataset.sessionMetric, node]));
    models[0].querySelectorAll('[data-session-metric]').forEach(a => {
      const b = bMetrics.get(a.dataset.sessionMetric), row = document.createElement('tr');
      row.dataset.metric = a.dataset.sessionMetric;
      row.append(a.cells[0].cloneNode(true), a.cells[1].cloneNode(true), b.cells[1].cloneNode(true));
      ComparisonDisplay.differences(row, ComparisonDisplay.number(a), ComparisonDisplay.number(b), a.dataset.kind);
      metrics.append(row);
    });
    const groups = models.map(model => new Map([...model.querySelectorAll('[data-session-type]')]
      .map(node => [JSON.stringify([node.dataset.area, node.dataset.level]), node])));
    const keys = [...new Set([...groups[0].keys(), ...groups[1].keys()])].sort();
    const types = this.root.querySelector('[data-comparison-types]');
    types.replaceChildren();
    keys.forEach(key => {
      const [a, b] = groups.map(group => group.get(key)), row = document.createElement('tr');
      row.dataset.type = key;
      row.append((a || b).cells[0].cloneNode(true));
      [a, b].forEach(value => row.append(value ? value.cells[1].cloneNode(true) : ComparisonDisplay.cell('—')));
      ComparisonDisplay.differences(row, ComparisonDisplay.number(a), ComparisonDisplay.number(b), 'duration');
      types.append(row);
    });
    this.root.querySelector('[data-comparison-types-empty]').hidden = keys.length !== 0;
  }
  update() {
    this.hideTooltips();
    const ids = this.selects.map(select => select.value);
    const same = ids[0] === ids[1];
    this.root.querySelector('[data-same-session]').hidden = !same;
    this.root.querySelector('[data-comparison-result]').hidden = same;
    const url = new URL(location.href);
    ['a', 'b'].forEach((side, index) => url.searchParams.set(side, ids[index]));
    url.searchParams.set('mode', this.mode.value);
    try { history.replaceState(null, '', url); } catch { /* file:// may restrict the History API. */ }
    if (same) return;
    const sources = ids.map(id => this.sources.get(id));
    this.compare(sources);
    ['a', 'b'].forEach((side, index) => {
      const card = this.root.querySelector(`[data-comparison-card="${side}"]`);
      const open = card.querySelector('details')?.open;
      card.replaceChildren(sources[index].querySelector('[data-card]').cloneNode(true));
      card.querySelector('details').open = Boolean(open);
      card.querySelectorAll('[data-context-mode]').forEach(node => { node.hidden = node.dataset.contextMode !== this.mode.value; });
      if (this.chartIds?.[index] === ids[index]) return;
      const container = this.root.querySelector(`[data-comparison-chart="${side}"]`);
      container.replaceChildren(sources[index].querySelector('[data-chart]').cloneNode(true));
      this.root.querySelector(`[data-chart-heading="${side}"]`).textContent = card.querySelector('a').textContent;
      document.getElementById(`chart-tooltip-session-comparison-${side}`)?.remove();
      this.interactions.setupPointTooltip(container.querySelector('svg'), 'session-comparison-' + side);
      container.querySelector('.session-chart-scroll').addEventListener('scroll', event => {
        this.root.querySelectorAll('.session-chart-scroll').forEach(scroll => {
          if (scroll.scrollLeft !== event.target.scrollLeft) scroll.scrollLeft = event.target.scrollLeft;
        });
        this.refreshTooltips();
      });
    });
    this.chartIds = ids;
    this.scale();
    this.interactions.syncTheme(document.querySelector('[data-theme-toggle]'));
  }
  hideTooltips() {
    document.querySelectorAll('[id^="chart-tooltip-session-comparison-"]').forEach(node => { node.hidden = true; });
  }
  refreshTooltips() {
    this.root.querySelectorAll('[data-comparison-chart] svg').forEach(chart => this.interactions.refreshPointTooltip(chart));
  }
  scale(preserveFocus = false) {
    ComparisonDisplay.scale([...this.root.querySelectorAll('[data-comparison-chart] svg')], Number(this.zoom.value));
    if (preserveFocus) this.refreshTooltips();
    else this.hideTooltips();
  }
}
