/* Search local index chunks. Insert log content as text only. */
class ReportSearch {
  constructor(root) {
    this.root = root;
    this.model = JSON.parse(root.dataset.historySearch);
    this.labels = JSON.parse(root.dataset.labels);
    this.form = root.querySelector('form');
    this.body = root.querySelector('[data-search-rows]');
    this.status = root.querySelector('[data-search-status]');
    this.pager = root.querySelector('[data-search-pager]');
    this.cancelButton = root.querySelector('[data-search-cancel]');
    this.generation = 0;
    this.busy = false;
    this.pending = null;
    this.matches = [];
    this.total = 0;
    this.page = 0;
    this.form.addEventListener('submit', event => {
      event.preventDefault();
      this.submit();
    });
    this.cancelButton.addEventListener('click', () => {
      this.generation++;
      this.pending = null;
      this.matches = [];
      this.total = 0;
      this.body.replaceChildren();
      this.pager.hidden = true;
      this.state('cancelled', this.text('cancelled'));
    });
    root.querySelector('[data-search-previous]').addEventListener('click', () => this.go(this.page - 1));
    root.querySelector('[data-search-next]').addEventListener('click', () => this.go(this.page + 1));
    root.querySelector('[data-search-go]').addEventListener('click', () => {
      this.go(Number(root.querySelector('[data-search-page]').value) - 1);
    });
    this.form.querySelector('fieldset').disabled = false;
    this.state('ready', this.text('ready'));
    const saved = new URLSearchParams(location.hash.slice(1));
    if (saved.has('q')) {
      for (const key of ['q', 'from', 'to', 'type', 'status']) {
        this.form.elements.namedItem(key).value = saved.get(key) || '';
      }
      this.submit();
    }
  }
  text(key, values = {}) {
    let result = this.labels[key];
    for (const [name, value] of Object.entries(values)) result = result.replaceAll(`{${name}}`, String(value));
    return result;
  }
  state(name, message) {
    this.root.dataset.state = name;
    this.status.textContent = message;
    this.cancelButton.disabled = name !== 'running';
    this.root.querySelector('[data-search-results]').setAttribute('aria-busy', String(name === 'running'));
  }
  static normalize(value) {
    return value.normalize('NFC').toLowerCase();
  }
  submit() {
    const query = Object.fromEntries(new FormData(this.form));
    this.generation++;
    this.pending = null;
    this.matches = [];
    this.total = 0;
    this.body.replaceChildren();
    this.pager.hidden = true;
    if (query.from && query.to && query.from > query.to) {
      this.state('invalid', this.text('invalid'));
      return;
    }
    this.query = {...query, term: ReportSearch.normalize(query.q.trim())};
    // The fragment preserves the query when returning from full history without a server.
    try {
      history.replaceState(null, '', '#' + new URLSearchParams(query).toString());
    } catch {
      // Search still works when file:// restrictions prevent saving the URL.
    }
    this.pending = {kind: 'search', query: this.query, token: this.generation};
    this.state('running', this.text('progress', {done: 0, total: this.model.count}));
    this.drain();
  }
  go(page) {
    if (this.busy || !Number.isInteger(page) || page < 0 || page * this.model.page_size >= this.total) return;
    this.pending = {kind: 'page', page, token: ++this.generation};
    this.state('running', this.text('loading'));
    this.drain();
  }
  async drain() {
    if (this.busy) return;
    this.busy = true;
    while (this.pending) {
      const task = this.pending;
      this.pending = null;
      try {
        if (task.kind === 'search') await this.search(task);
        else await this.loadPage(task);
      } catch {
        if (task.token === this.generation) {
          this.matches = [];
          this.total = 0;
          this.body.replaceChildren();
          this.pager.hidden = true;
          this.state('error', this.text('error'));
        }
      }
    }
    this.busy = false;
  }
  async load(part) {
    if (!/^parts\/[1-9]\d*\.js$/.test(part.path)) throw new Error('Invalid search-chunk path');
    // One loader prevents mixing results from cancelled requests.
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      let settled = false;
      delete window.PoeSearchChunk;
      const finish = error => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        const value = window.PoeSearchChunk;
        delete window.PoeSearchChunk;
        script.remove();
        if (error || value?.version !== 1 || value?.number !== part.number || !Array.isArray(value.rows)
            || value.rows.length !== part.count) reject(new Error('Could not read the search chunk'));
        else resolve(value.rows);
      };
      const timer = setTimeout(() => finish(true), 15000);
      script.onload = () => finish(false);
      script.onerror = () => finish(true);
      script.src = part.path;
      document.head.append(script);
    });
  }
  static matches(row, query) {
    const date = row[1].slice(0, 10);
    if ((query.from || query.to) && (!date || (query.from && date < query.from) || (query.to && date > query.to))) return false;
    if (query.status && row[3] !== query.status) return false;
    const type = row[2], filter = query.type;
    if (filter === '$levels' && type !== 'screen.level_up') return false;
    if (filter === '$deaths' && !['screen.slain', 'screen.suicide', 'screen.death_count'].includes(type)) return false;
    if (filter === '$loading' && type !== 'loading.duration') return false;
    if (filter === '$chat' && !type.startsWith('chat.')) return false;
    if (filter === '$issues' && !row[6]) return false;
    if (filter && !filter.startsWith('$')) {
      if (filter.endsWith('.*') ? !type.startsWith(filter.slice(0, -1)) : type !== filter) return false;
    }
    return !query.term || ReportSearch.normalize(`${row[4] || ''}\n${row[5]}\n${type}`).includes(query.term);
  }
  async search(task) {
    const matches = [], first = [];
    let total = 0, done = 0;
    for (const part of this.model.parts) {
      if (task.token !== this.generation) return;
      const query = task.query;
      const skip = (query.from || query.to) && (!part.date_from
        || (query.from && part.date_to < query.from) || (query.to && part.date_from > query.to));
      if (!skip) {
        const rows = await this.load(part);
        if (task.token !== this.generation) return;
        const positions = [];
        rows.forEach((row, index) => {
          if (!ReportSearch.matches(row, query)) return;
          positions.push(index);
          total++;
          if (first.length < this.model.page_size) first.push({row, part});
        });
        if (positions.length) matches.push({part, positions: Uint16Array.from(positions)});
      }
      done += part.count;
      this.state('running', this.text('progress', {done, total: this.model.count}));
    }
    if (task.token !== this.generation) return;
    this.matches = matches;
    this.total = total;
    this.render(first, 0);
  }
  async loadPage(task) {
    const first = task.page * this.model.page_size, end = first + this.model.page_size;
    const selected = [];
    let offset = 0;
    for (const match of this.matches) {
      if (task.token !== this.generation) return;
      const next = offset + match.positions.length;
      if (next > first && offset < end) {
        const rows = await this.load(match.part);
        if (task.token !== this.generation) return;
        const positions = match.positions.slice(Math.max(0, first - offset), Math.min(match.positions.length, end - offset));
        for (const index of positions) selected.push({row: rows[index], part: match.part});
      }
      offset = next;
      if (offset >= end) break;
    }
    this.render(selected, task.page);
  }
  render(rows, page) {
    this.page = page;
    const fragment = document.createDocumentFragment();
    for (const {row, part} of rows) {
      const tr = document.createElement('tr');
      tr.dataset.line = row[0];
      const time = tr.insertCell();
      time.textContent = row[1] ? row[1].slice(0, 19).replace('T', ' ') : '—';
      const type = tr.insertCell();
      const code = document.createElement('code');
      code.textContent = row[2];
      type.append(code);
      if (row[3] !== 'recognized') {
        const status = document.createElement('small');
        status.textContent = this.text(row[3] === 'error' ? 'error_status' : row[3]);
        type.append(status);
      }
      const message = tr.insertCell();
      const details = document.createElement('details');
      details.className = 'timeline-record';
      const summary = document.createElement('summary');
      summary.className = 'timeline-message';
      const text = row[4] === null ? this.text('undecodable') : row[4] || this.text('empty_line');
      summary.textContent = text.length > 200 ? text.slice(0, 200) + '…' : text;
      const original = document.createElement('pre');
      original.className = 'message-text';
      original.textContent = text + (row[5] ? '\n\n' + this.text('values') + '\n' + row[5] : '');
      details.append(summary, original);
      message.append(details);
      const line = tr.insertCell();
      const link = document.createElement('a');
      const url = new URL(part.history, location.href);
      url.searchParams.set('theme', document.documentElement.dataset.bsTheme || 'dark');
      url.hash = `line-${row[0]}`;
      link.href = url.href;
      link.textContent = `#${row[0]}`;
      link.setAttribute('aria-label', this.text('open', {line: row[0]}));
      line.append(link);
      fragment.append(tr);
    }
    this.body.replaceChildren(fragment);
    const pages = Math.ceil(this.total / this.model.page_size);
    this.pager.hidden = pages <= 1;
    this.root.querySelector('[data-search-previous]').disabled = page === 0;
    this.root.querySelector('[data-search-next]').disabled = page + 1 >= pages;
    this.root.querySelector('[data-search-page-label]').textContent = this.text('page', {page: page + 1, pages});
    const input = this.root.querySelector('[data-search-page]');
    input.max = Math.max(1, pages);
    input.value = page + 1;
    this.state('complete', this.total ? this.text('results', {count: this.total, from: page * this.model.page_size + 1,
      to: Math.min((page + 1) * this.model.page_size, this.total)}) : this.text('none'));
  }
}
const searchRoot = document.querySelector('[data-history-search]');
if (searchRoot) new ReportSearch(searchRoot);
