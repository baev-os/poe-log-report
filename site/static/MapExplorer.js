/* Select prepared measurements without loading data or changing the overall report period. */
class MapExplorer {
  constructor(root) {
    this.root = root;
    this.forms = [...root.querySelectorAll('[data-cohort]')];
    this.body = root.querySelector('[data-explorer-rows]');
    this.rows = [...this.body.querySelectorAll('[data-map-row]')].map(node => ({
      node, line: Number(node.dataset.line), type: node.dataset.type, name: node.dataset.name,
      date: node.dataset.date, stamp: node.dataset.stamp ? Date.parse(node.dataset.stamp) : null,
      levels: node.dataset.levels.split(',').filter(Boolean), mechanics: node.dataset.mechanics.split(',').filter(Boolean),
      allSeconds: Number(node.dataset.seconds), allObserved: node.dataset.observed === 'yes',
      remainingSeconds: node.dataset.remainingSeconds === '' ? null : Number(node.dataset.remainingSeconds),
      allComplete: node.dataset.complete === 'yes', returns: Number(node.dataset.returns)
    }));
    this.toggle = root.querySelector('[data-compare-toggle]');
    this.recordGroup = root.querySelector('[data-record-group]');
    this.sort = root.querySelector('[data-sort]');
    this.mode = root.querySelector('[data-explorer-duration]');
    this.collator = new Intl.Collator(document.documentElement.lang, {numeric: true, sensitivity: 'base'});
    root.querySelectorAll('[data-explorer-controls]').forEach(node => { node.hidden = false; });
    this.forms.forEach(form => {
      form.addEventListener('submit', event => event.preventDefault());
      form.addEventListener('input', () => this.update());
      form.addEventListener('change', () => this.update());
      form.addEventListener('reset', () => setTimeout(() => this.update(), 0));
    });
    [this.toggle, this.recordGroup, this.sort, this.mode].forEach(node => node.addEventListener('change', () => this.update()));
    this.update();
  }
  filter(form) {
    const value = Object.fromEntries(new FormData(form));
    const valid = form.checkValidity() && !(value.from && value.to && value.from > value.to)
      && !(value.min !== '' && value.max !== '' && Number(value.min) > Number(value.max));
    form.querySelector('[data-filter-error]').hidden = valid;
    if (!valid) return null;
    const term = value.name.trim().toLocaleLowerCase(document.documentElement.lang);
    return this.rows.filter(row => (!value.type || row.type === value.type)
      && (!term || row.name.toLocaleLowerCase(document.documentElement.lang).includes(term))
      && (!value.from || (row.date && row.date >= value.from))
      && (!value.to || (row.date && row.date <= value.to))
      && (!value.level || row.levels.includes(value.level))
      && (!value.mechanic || row.mechanics.includes(value.mechanic) === (value.observation === 'with'))
      && (!value.complete || row.complete === (value.complete === 'yes'))
      && (value.min === '' || (row.observed && row.seconds >= Number(value.min)))
      && (value.max === '' || (row.observed && row.seconds <= Number(value.max))));
  }
  static statistics(rows) {
    if (rows === null) return null;
    const values = rows.filter(row => row.complete && row.seconds != null).map(row => row.seconds).sort((a, b) => a - b);
    const measured = rows.filter(row => row.seconds != null);
    const n = values.length;
    return {count: rows.length, complete: n, excluded: rows.length - n,
      map_seconds: measured.length || !rows.length ? measured.reduce((sum, row) => sum + row.seconds, 0) : null,
      returns: rows.reduce((sum, row) => sum + row.returns, 0),
      mean_seconds: n ? values.reduce((sum, value) => sum + value, 0) / n : null,
      median_seconds: n ? (values[Math.floor((n - 1) / 2)] + values[Math.floor(n / 2)]) / 2 : null,
      min_seconds: n ? values[0] : null, max_seconds: n ? values[n - 1] : null};
  }
  static duration(seconds) {
    const ms = Math.round(Math.abs(seconds) * 1000);
    const s = Math.floor(ms / 1000);
    const fraction = ms % 1000 ? '.' + String(ms % 1000).padStart(3, '0').replace(/0+$/, '') : '';
    return `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor(s / 60) % 60).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}${fraction}`;
  }
  static format(key, value, delta = false) {
    if (value == null || !Number.isFinite(value)) return '—';
    const rounded = Math.round(value * 1000) / 1000;
    const sign = delta && rounded !== 0 ? (rounded > 0 ? '+' : '−') : '';
    return sign + (key.endsWith('_seconds') ? MapExplorer.duration(rounded) : String(Math.abs(rounded)));
  }
  static bins(a, b) {
    const values = [a, b].map(rows => (rows || []).filter(row => row.complete && row.seconds != null).map(row => row.seconds));
    const all = [...values[0], ...values[1]];
    if (!all.length) return [];
    const min = all.reduce((a, b) => Math.min(a, b)), max = all.reduce((a, b) => Math.max(a, b));
    const count = min === max ? 1 : 5, width = (max - min) / count;
    const bins = Array.from({length: count}, (_, i) => ({start: min + i * width, end: i === count - 1 ? max : min + (i + 1) * width, a: 0, b: 0}));
    values.forEach((items, group) => items.forEach(value => { bins[width ? Math.min(count - 1, Math.floor((value - min) / width)) : 0][group ? 'b' : 'a']++; }));
    return bins;
  }
  distribution(a, b, compare) {
    const bins = a === null || (compare && b === null) ? [] : MapExplorer.bins(a, compare ? b : []);
    const body = this.root.querySelector('[data-bins]');
    body.replaceChildren();
    this.root.querySelector('[data-distribution]').hidden = !bins.length;
    const max = bins.reduce((value, bin) => Math.max(value, bin.a, bin.b), 1);
    bins.forEach((bin, index) => {
      const row = document.createElement('tr'), label = document.createElement('th');
      label.scope = 'row';
      label.textContent = bin.start === bin.end ? MapExplorer.duration(bin.start)
        : `[${MapExplorer.duration(bin.start)} — ${MapExplorer.duration(bin.end)}${index === bins.length - 1 ? ']' : ')'}`;
      row.append(label);
      ['a', 'b'].forEach(group => {
        const cell = document.createElement('td'), bar = document.createElement('span'), text = document.createElement('span');
        bar.className = 'explorer-bin explorer-bin-' + group;
        bar.style.width = `${90 * bin[group] / max}%`;
        bar.setAttribute('aria-hidden', 'true');
        text.textContent = String(bin[group]);
        cell.append(bar, text);
        cell.hidden = group === 'b' && !compare;
        row.append(cell);
      });
      body.append(row);
    });
  }
  order(rows) {
    const [field, direction] = this.sort.value.split('-'), sign = direction === 'desc' ? -1 : 1;
    return [...rows].sort((a, b) => {
      const one = field === 'date' ? a.stamp : field === 'duration' ? (a.observed ? a.seconds : null) : a[field];
      const two = field === 'date' ? b.stamp : field === 'duration' ? (b.observed ? b.seconds : null) : b[field];
      if (one === null || two === null) return Number(one === null) - Number(two === null) || a.line - b.line;
      return (field === 'name' ? this.collator.compare(one, two) : one - two) * sign || a.line - b.line;
    });
  }
  update() {
    const reduced = this.mode.value === 'without_afk';
    this.rows.forEach(row => {
      row.seconds = reduced ? row.remainingSeconds : row.allSeconds;
      row.observed = row.allObserved && row.seconds != null;
      row.complete = row.allComplete && row.observed;
      row.node.querySelector('[data-selected-duration]').textContent = MapExplorer.format('map_seconds', row.observed ? row.seconds : null);
    });
    const compare = this.toggle.checked;
    this.forms[1].hidden = !compare;
    this.root.querySelectorAll('[data-comparison]').forEach(node => { node.hidden = !compare; });
    this.recordGroup.options[1].disabled = !compare;
    if (!compare) this.recordGroup.value = 'a';
    const selected = {a: this.filter(this.forms[0]), b: compare ? this.filter(this.forms[1]) : []};
    const summaries = {a: MapExplorer.statistics(selected.a), b: MapExplorer.statistics(selected.b)};
    this.root.querySelectorAll('[data-metric]').forEach(node => {
      const key = node.dataset.metric, group = node.dataset.group;
      const value = group === 'delta' ? (summaries.a?.[key] != null && summaries.b?.[key] != null ? summaries.b[key] - summaries.a[key] : null) : summaries[group]?.[key];
      node.textContent = MapExplorer.format(key, value, group === 'delta');
    });
    const ids = new Set((selected.a || []).map(row => row.line));
    this.root.querySelector('[data-overlap]').textContent = selected.a && selected.b ? String(selected.b.filter(row => ids.has(row.line)).length) : '—';
    this.distribution(selected.a, selected.b, compare);
    const rows = selected[this.recordGroup.value], visible = new Set(rows || []);
    this.order(this.rows).forEach(row => { row.node.hidden = !visible.has(row); this.body.append(row.node); });
    this.root.querySelector('[data-result-count]').textContent = rows ? String(rows.length) : '—';
    this.root.querySelector('[data-no-results]').hidden = !rows || rows.length !== 0;
  }
}
document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-map-explorer]');
  if (root) new MapExplorer(root);
});
