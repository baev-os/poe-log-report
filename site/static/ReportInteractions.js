/* Filter the generated report locally without network requests. */
class ReportInteractions {
  constructor() {
    this.setupActivityTimeline();
    this.setupPlaytimeChart();
    this.setupPlaytimeMode();
    this.setupMapDurations();
    this.setupLoadingRoutes();
    this.setupStability();
    this.setupHeatmap();
    this.setupWeeklyPace();
    this.setupSessionTimeline();
    const comparison = document.querySelector('[data-session-comparison]');
    if (comparison) new SessionComparison(comparison, this);
    const runComparison = document.querySelector('[data-map-run-comparison]');
    if (runComparison) new MapRunComparison(runComparison, this);
    document.querySelectorAll('[data-results]').forEach(container => {
      const name = container.dataset.results;
      const search = document.querySelector(`[data-search="${name}"]`);
      const category = document.querySelector(`[data-category="${name}"]`);
      const update = () => this.filter(container, search?.value || '', category?.value || '');
      search?.addEventListener('input', update);
      category?.addEventListener('change', update);
    });
  }
  setupPlaytimeChart() {
    document.querySelectorAll('.playtime-chart, .loading-chart, .loading-route-chart, .stability-chart, .pace-chart, .weekly-chart, .area-duration-chart, .heatmap-chart, .character-death-markers, .session-chart, .memory-chart').forEach((chart, index) => this.setupPointTooltip(chart, index));
  }
  setupStability() {
    const root = document.querySelector('[data-stability]');
    if (!root) return;
    const reveal = () => {
      const target = document.getElementById(location.hash.slice(1));
      if (!target || !root.contains(target)) return;
      const container = root.querySelector('[data-results="stability"]');
      if (container && target.closest('[data-group]')) {
        root.querySelector('[data-search="stability"]').value = '';
        root.querySelector('[data-category="stability"]').value = '';
        this.filter(container, '', '');
      }
      let item = target;
      while (item && item !== root) {
        if (item.tagName === 'DETAILS') item.open = true;
        item = item.parentElement;
      }
      target.scrollIntoView();
    };
    root.addEventListener('click', event => {
      if (event.target.closest('a[href]')) setTimeout(reveal, 0);
    });
    window.addEventListener('hashchange', reveal);
    reveal();
  }
  setupLoadingRoutes() {
    const root = document.querySelector('[data-loading-routes]');
    const select = root?.querySelector('[data-loading-route-select]');
    if (!select) return;
    const panels = [...root.querySelectorAll('[data-loading-route]')];
    const update = () => {
      panels.forEach(panel => {
        panel.hidden = Boolean(select.value && panel.id !== select.value);
        if (select.value && !panel.hidden) panel.open = true;
      });
      document.querySelectorAll('.playtime-tooltip').forEach(node => { node.hidden = true; });
    };
    const reveal = () => {
      const target = document.getElementById(location.hash.slice(1));
      const panel = target?.closest('[data-loading-route]');
      if (!panel) return;
      select.value = panel.id;
      update(); panel.open = true; target.scrollIntoView();
    };
    root.querySelector('[data-loading-route-controls]').hidden = false;
    select.addEventListener('change', update);
    root.addEventListener('click', event => {
      if (event.target.closest('a[href]')) setTimeout(reveal, 0);
    });
    window.addEventListener('hashchange', reveal);
    reveal();
  }
  setupSessionTimeline() {
    const root = document.querySelector('[data-session-timeline]');
    if (!root) return;
    const chart = root.querySelector('svg');
    const scroll = root.querySelector('.session-chart-scroll');
    const select = root.querySelector('[data-session-zoom]');
    const start = Number(chart.dataset.start), end = Number(chart.dataset.end);
    const height = chart.viewBox.baseVal.height;
    const date = new Intl.DateTimeFormat(document.documentElement.lang, {timeZone: root.dataset.zone, day: '2-digit', month: '2-digit', year: 'numeric'});
    const time = new Intl.DateTimeFormat(document.documentElement.lang, {timeZone: root.dataset.zone, hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZoneName: 'shortOffset'});
    const text = (x, y, value) => {
      const node = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      node.setAttribute('x', x); node.setAttribute('y', y); node.setAttribute('text-anchor', 'middle');
      node.textContent = value;
      return node;
    };
    const update = () => {
      const old = chart.viewBox.baseVal.width;
      const center = (scroll.scrollLeft + scroll.clientWidth / 2) / old;
      const width = Math.max(1000, scroll.clientWidth) * Number(select.value);
      chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
      chart.style.width = `${width}px`;
      chart.querySelectorAll('[data-span]').forEach(item => {
        item.setAttribute('x', 70 + (width - 140) * Number(item.dataset.from));
        item.setAttribute('width', Math.max(5, (width - 140) * (Number(item.dataset.to) - Number(item.dataset.from))));
      });
      const ticks = root.querySelector('[data-session-ticks]');
      ticks.replaceChildren();
      const count = end > start ? Math.floor((width - 140) / 150) : 0;
      for (let i = 0; i <= count; i++) {
        const fraction = count ? i / count : .5;
        const x = 70 + (width - 140) * fraction;
        const moment = new Date((start + (end - start) * fraction) * 1000);
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', x); line.setAttribute('x2', x); line.setAttribute('y1', 48); line.setAttribute('y2', height);
        line.setAttribute('class', 'chart-grid');
        ticks.append(text(x, 20, date.format(moment)), text(x, 38, time.format(moment)), line);
      }
      scroll.scrollLeft = center * width - scroll.clientWidth / 2;
      document.querySelectorAll('.playtime-tooltip').forEach(tooltip => { tooltip.hidden = true; });
    };
    root.querySelector('.session-chart-controls').hidden = false;
    select.addEventListener('change', update);
    root.querySelector('[data-session-reset]').addEventListener('click', () => { select.value = '1'; update(); scroll.scrollLeft = 0; });
    window.addEventListener('resize', update);
    scroll.addEventListener('scroll', () => document.querySelectorAll('.playtime-tooltip').forEach(tooltip => { tooltip.hidden = true; }));
    update();
  }
  setupWeeklyPace() {
    const select = document.querySelector('[data-weekly-type]');
    if (!select) return;
    document.querySelector('[data-weekly-controls]').hidden = false;
    select.addEventListener('change', () => {
      const url = new URL(select.value, location.href);
      url.searchParams.set('theme', document.documentElement.dataset.bsTheme);
      location.assign(url.href);
    });
  }
  setupHeatmap() {
    const heatmap = document.querySelector('[data-heatmap]');
    if (!heatmap) return;
    const select = heatmap.querySelector('[data-heatmap-filter]');
    const mode = document.querySelector('[data-time-mode]');
    const panels = [...heatmap.querySelectorAll('[data-heatmap-panel]')];
    const activate = code => {
      select.value = code;
      panels.forEach(panel => {
        panel.hidden = panel.dataset.heatmapKind !== code || panel.dataset.heatmapMode !== (mode?.value || 'all');
      });
      document.querySelectorAll('.playtime-tooltip').forEach(tooltip => { tooltip.hidden = true; });
    };
    const reveal = () => {
      const target = document.getElementById(location.hash.slice(1));
      if (!target?.matches('[data-heatmap-days]')) return;
      const panel = target.closest('[data-heatmap-panel]');
      if (mode) {
        mode.value = panel.dataset.heatmapMode;
        mode.dispatchEvent(new Event('change'));
      }
      activate(panel.dataset.heatmapKind);
      target.open = true;
      target.scrollIntoView({block: 'start'});
    };
    heatmap.querySelector('[data-heatmap-controls]').hidden = false;
    select.addEventListener('change', () => activate(select.value));
    mode?.addEventListener('change', () => activate(select.value));
    heatmap.querySelectorAll('[data-heatmap-cell]').forEach(link => link.addEventListener('click', () => {
      const target = document.getElementById(new URL(link.getAttribute('href'), location.href).hash.slice(1));
      target.open = true;
    }));
    window.addEventListener('hashchange', reveal);
    activate(select.value);
    reveal();
  }
  setupPlaytimeMode() {
    const select = document.querySelector('[data-time-mode]');
    if (!select) return;
    const update = () => {
      document.querySelectorAll('[data-playtime-panel]').forEach(panel => {
        panel.hidden = panel.dataset.playtimePanel !== select.value;
      });
      document.querySelectorAll('.playtime-tooltip').forEach(tooltip => { tooltip.hidden = true; });
    };
    document.querySelector('[data-time-mode-controls]').hidden = false;
    select.addEventListener('change', update);
    update();
  }
  setupMapDurations() {
    const select = document.querySelector('[data-map-duration-mode]');
    if (!select) return;
    const update = () => document.querySelectorAll('[data-map-duration-panel]').forEach(panel => {
      panel.hidden = panel.dataset.mapDurationPanel !== select.value;
    });
    document.querySelector('[data-map-duration-controls]').hidden = false;
    select.addEventListener('change', update);
    update();
    const reveal = () => {
      const target = document.getElementById(location.hash.slice(1));
      const panel = target?.closest('[data-map-duration-panel]');
      if (!panel) return;
      select.value = panel.dataset.mapDurationPanel;
      update();
      target.scrollIntoView();
    };
    window.addEventListener('hashchange', reveal);
    reveal();
  }
  setupPointTooltip(chart, index) {
    const tooltip = document.createElement('div');
    tooltip.className = 'playtime-tooltip';
    tooltip.id = index ? `chart-tooltip-${index}` : 'playtime-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.hidden = true;
    document.body.append(tooltip);
    chart.querySelectorAll('a').forEach(link => {
      const title = link.querySelector('title');
      const text = title.textContent;
      link.dataset.chartTip = text;
      link.dataset.pointTooltip = '';
      // Native tooltips are delayed and disappear on the browser timer.
      title.remove();
      link.setAttribute('aria-describedby', tooltip.id);
      const show = () => {
        tooltip.textContent = text;
        tooltip.hidden = false;
        const bar = link.getBoundingClientRect();
        const box = tooltip.getBoundingClientRect();
        const left = Math.max(8, Math.min(innerWidth - box.width - 8, bar.left + bar.width / 2 - box.width / 2));
        const top = bar.top >= box.height + 16 ? bar.top - box.height - 8 : bar.bottom + 8;
        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${Math.max(8, Math.min(innerHeight - box.height - 8, top))}px`;
      };
      link.addEventListener('pointerenter', show);
      link.addEventListener('focus', show);
      link.addEventListener('pointerleave', () => {
        if (!link.matches(':focus-visible')) tooltip.hidden = true;
      });
      link.addEventListener('blur', () => {
        if (!link.matches(':hover')) tooltip.hidden = true;
      });
    });
    chart.addEventListener('keydown', event => {
      if (event.key === 'Escape') tooltip.hidden = true;
    });
  }
  setupActivityTimeline() {
    const select = document.querySelector('[data-activity-period]');
    if (!select) return;
    document.querySelector('[data-activity-controls]').hidden = false;
    select.addEventListener('change', () => {
      const option = select.selectedOptions[0];
      document.querySelector('[data-activity-label]').textContent = option.textContent;
      const start = Number(option.dataset.start), end = Number(option.dataset.end);
      document.querySelectorAll('[data-activity-interval]').forEach(link => {
        const left = Number(link.dataset.start), right = Number(link.dataset.end);
        const point = left === right;
        const visible = point ? left >= start && (left < end || option.value === 'all') : left < end && right > start;
        link.setAttribute('display', visible ? 'inline' : 'none');
        if (!visible) return;
        const rect = link.querySelector('rect');
        rect.setAttribute('x', 220 + 960 * (Math.max(left, start) - start) / (end - start));
        rect.setAttribute('width', Math.max(1.5, 960 * (Math.min(right, end) - Math.max(left, start)) / (end - start)));
      });
      const ticks = JSON.parse(option.dataset.ticks);
      document.querySelectorAll('[data-activity-tick]').forEach((label, index) => {
        label.textContent = ticks[index].label;
      });
    });
  }
  syncTheme(toggle) {
    ReportTheme.sync(toggle);
  }
  filter(container, query, category) {
    const language = document.documentElement.lang || 'ru';
    const term = query.trim().toLocaleLowerCase(language);
    let visible = 0;
    container.querySelectorAll('[data-item]').forEach(item => {
      const matches = (!category || item.dataset.kind === category) && item.textContent.toLocaleLowerCase(language).includes(term);
      item.hidden = !matches;
      visible += Number(matches);
      if (item.tagName === 'DETAILS' && term) item.open = matches;
    });
    container.querySelectorAll('[data-group]').forEach(group => {
      group.hidden = !group.querySelector('[data-item]:not([hidden])');
    });
    const empty = container.nextElementSibling;
    if (empty?.classList.contains('empty-filter')) empty.hidden = visible !== 0;
  }
}
document.addEventListener('DOMContentLoaded', () => new ReportInteractions());
