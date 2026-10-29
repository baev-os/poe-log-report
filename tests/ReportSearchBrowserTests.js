/* Real file:// search checks against a synthetic report. */
class ReportSearchBrowserTests {
  static assert(condition, message) {
    if (!condition) throw new Error(message);
  }

  static async wait(predicate) {
    for (let i = 0; i < 500; i++) {
      if (predicate()) return;

      await new Promise(resolve => setTimeout(resolve, 20));
    }

    throw new Error("Search timed out");
  }

  static submit(root, fields = {}) {
    const form = root.querySelector('form');

    for (const name of ['q', 'from', 'to', 'type', 'status']) form.elements.namedItem(name).value = fields[name] || '';

    form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
  }

  static lines(root) {
    return [...root.querySelectorAll('tbody tr')].map(row => Number(row.dataset.line));
  }

  static async search(root, fields) {
    ReportSearchBrowserTests.submit(root, fields);
    await ReportSearchBrowserTests.wait(() => root.dataset.state === 'complete' || root.dataset.state === 'error');

    ReportSearchBrowserTests.assert(root.dataset.state === 'complete', "Search failed");

    return ReportSearchBrowserTests.lines(root);
  }

  static async run() {
    const root = document.querySelector('[data-history-search]');
    const assert = ReportSearchBrowserTests.assert;
    await ReportSearchBrowserTests.wait(() => root.dataset.state === 'ready');

    let lines = await ReportSearchBrowserTests.search(root, {});
    assert(lines.length === 100 && lines[0] === 1 && lines[99] === 100, "First hundred results");
    root.querySelector('[data-search-next]').click();
    await ReportSearchBrowserTests.wait(() => root.dataset.state === 'complete');

    assert(ReportSearchBrowserTests.lines(root)[0] === 101, "Next page");
    root.querySelector('[data-search-page]').value = 6;
    root.querySelector('[data-search-go]').click();
    await ReportSearchBrowserTests.wait(() => root.dataset.state === 'complete');

    assert(ReportSearchBrowserTests.lines(root)[0] === 501, "Navigation across a search-part boundary");
    root.querySelector('[data-search-previous]').click();
    await ReportSearchBrowserTests.wait(() => root.dataset.state === 'complete');

    assert(ReportSearchBrowserTests.lines(root)[0] === 401, "Previous page");
    lines = await ReportSearchBrowserTests.search(root, {q: 'synthetichero'});
    assert(lines.join(',') === '501,504,506', "Case-insensitive name search");
    lines = await ReportSearchBrowserTests.search(root, {q: 'ЗЕРКАЛО'});
    assert(lines.join(',') === '506', "Unicode search");
    assert(root.querySelector('tbody').textContent.includes('<script>'), "Original markup is displayed as text");
    assert(!root.querySelector('tbody script') && window.injected === undefined, "Log text does not execute");
    lines = await ReportSearchBrowserTests.search(root, {type: '$levels'});
    assert(lines.join(',') === '501', "Level filter");
    const link = root.querySelector('tbody a');
    assert(link.href.includes('/events/page-2.html?theme=dark#line-501'), "Local original-line link retains the theme");
    lines = await ReportSearchBrowserTests.search(root, {type: '$deaths'});
    assert(lines.join(',') === '504', "Death filter");
    lines = await ReportSearchBrowserTests.search(root, {type: '$loading'});
    assert(lines.join(',') === '503', "Loading filter");
    lines = await ReportSearchBrowserTests.search(root, {type: '$chat'});
    assert(lines.join(',') === '506', "Chat filter");
    lines = await ReportSearchBrowserTests.search(root, {type: '$issues'});
    assert(lines.join(',') === '505,508', "Faults and read error");
    lines = await ReportSearchBrowserTests.search(root, {type: 'area.*'});
    assert(lines.join(',') === '502', "Rule family");
    lines = await ReportSearchBrowserTests.search(root, {type: 'screen.level_up'});
    assert(lines.join(',') === '501', "Specific rule");
    lines = await ReportSearchBrowserTests.search(root, {status: 'error'});
    assert(lines.join(',') === '508', "Read-error status");
    lines = await ReportSearchBrowserTests.search(root, {from: '2026-09-02', to: '2026-09-02'});
    assert(lines.join(',') === '502,503,504,505,506', "Dates are inclusive; unknown timestamps are excluded");
    lines = await ReportSearchBrowserTests.search(root, {to: '2026-09-01'});
    assert(lines.join(',') === '501', "Open date range");
    ReportSearchBrowserTests.submit(root, {from: '2026-09-03', to: '2026-09-01'});
    assert(root.dataset.state === 'invalid', "Invalid range is rejected");
    lines = await ReportSearchBrowserTests.search(root, {q: 'no synthetic match [.*]'});
    assert(!lines.length && root.querySelector('[data-search-pager]').hidden, "Empty result");
    assert(ReportSearch.matches([1, '', 'synthetic', 'recognized', 'text', 'ONLY FIELD', false],
      {term: 'only field', type: '', status: '', from: '', to: ''}), "Field-value search");
    ReportSearchBrowserTests.submit(root, {q: 'Synthetic'});
    root.querySelector('[data-search-cancel]').click();
    await new Promise(resolve => setTimeout(resolve, 100));

    assert(root.dataset.state === 'cancelled' && !ReportSearchBrowserTests.lines(root).length, "Cancellation leaves no stale results");
    ReportSearchBrowserTests.submit(root, {q: 'Synthetic'});
    ReportSearchBrowserTests.submit(root, {q: 'Dunes'});
    await ReportSearchBrowserTests.wait(() => root.dataset.state === 'complete');

    assert(ReportSearchBrowserTests.lines(root).join(',') === '502,503', "New queries replace unfinished ones");
    const original = document.head.append;
    document.head.append = script => {
      setTimeout(() => script.dispatchEvent(new Event('error')), 1);
    };
    ReportSearchBrowserTests.submit(root, {});
    await ReportSearchBrowserTests.wait(() => root.dataset.state === 'error');

    document.head.append = original;
    assert(!ReportSearchBrowserTests.lines(root).length, "File errors cannot masquerade as complete results");
    lines = await ReportSearchBrowserTests.search(root, {q: 'Зеркало'});
    assert(lines.join(',') === '506', "Retry after error");
    assert(document.querySelectorAll('script[src*="parts/"]').length === 0 && !window.PoeSearchChunk,
      "Read parts are released");
    document.getElementById('browser-checks').textContent = JSON.stringify({passed: true, checks: 24});
  }

  static failed(error) {
    document.getElementById('browser-checks').textContent = JSON.stringify({passed: false, error: error.message});
  }
}

ReportSearchBrowserTests.run().catch(ReportSearchBrowserTests.failed);
