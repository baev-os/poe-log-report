/* Shared number and relative-scale presentation for A/B comparisons. */
class ComparisonDisplay {
  static number(node) {
    return !node || node.dataset.value === '' ? null : Number(node.dataset.value);
  }
  static format(value, kind, signed = false) {
    if (value == null || !Number.isFinite(value)) return '—';
    const hundredths = Math.round((Math.abs(value) + Number.EPSILON) * 100);
    const sign = signed && hundredths ? (value > 0 ? '+' : '−') : '';
    if (kind === 'duration') {
      const seconds = Math.floor(hundredths / 100);
      const fraction = hundredths % 100 ? '.' + String(hundredths % 100).padStart(2, '0').replace(/0+$/, '') : '';
      const text = `${String(Math.floor(seconds / 3600)).padStart(2, '0')}:${String(Math.floor(seconds / 60) % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}${fraction}`;
      return sign + (document.documentElement.lang === 'ru' ? text.replace('.', ',') : text);
    }
    return sign + new Intl.NumberFormat(document.documentElement.lang, {maximumFractionDigits: 2}).format(hundredths / 100) + (kind === 'percent' ? ' %' : '');
  }
  static cell(text) {
    const cell = document.createElement('td');
    cell.textContent = text;
    return cell;
  }
  static differences(row, a, b, kind) {
    const delta = a != null && b != null ? b - a : null;
    row.append(this.cell(this.format(delta, kind, true)),
      this.cell(this.format(delta != null && a !== 0 ? delta * 100 / a : null, 'percent', true)));
  }
  static scale(charts, zoom) {
    if (!charts.length) return;
    const minimum = Math.min(0, ...charts.map(chart => Number(chart.dataset.scaleMin || 0)));
    const maximum = Math.max(0, ...charts.map(chart => Number(chart.dataset.scaleMax ?? chart.dataset.duration)));
    const duration = Math.max(1, maximum - minimum);
    const width = Math.max(1000, charts[0].parentElement.clientWidth) * zoom;
    charts.forEach(chart => {
      const height = chart.viewBox.baseVal.height;
      chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
      chart.style.width = `${width}px`;
      chart.querySelectorAll('[data-relative-from]').forEach(item => {
        item.setAttribute('x', 70 + (width - 140) * (Number(item.dataset.relativeFrom) - minimum) / duration);
        item.setAttribute('width', Math.max(3, (width - 140) * (Number(item.dataset.relativeTo) - Number(item.dataset.relativeFrom)) / duration));
      });
      const ticks = chart.querySelector('[data-comparison-ticks]');
      ticks.replaceChildren();
      const count = Math.floor((width - 140) / 140);
      for (let i = 0; i <= count; i++) {
        const x = 70 + (width - 140) * i / count;
        const moment = Math.round(minimum + duration * i / count);
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', x); text.setAttribute('y', 30); text.setAttribute('text-anchor', 'middle');
        text.textContent = this.format(moment, 'duration', moment < 0);
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', x); line.setAttribute('x2', x); line.setAttribute('y1', 48); line.setAttribute('y2', height);
        line.setAttribute('class', 'chart-grid');
        ticks.append(text, line);
      }
      const origin = chart.querySelector('[data-comparison-origin]');
      if (origin) {
        const zero = 70 + (width - 140) * -minimum / duration;
        origin.setAttribute('x1', zero); origin.setAttribute('x2', zero);
      }
    });
  }
}
