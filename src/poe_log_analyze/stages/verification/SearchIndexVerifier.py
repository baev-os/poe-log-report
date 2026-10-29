import hashlib
import json

from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.rendering.SearchIndexWriter import SearchIndexWriter


class SearchIndexVerifier:
    """Validate local search data and links without executing JavaScript."""

    @staticmethod
    def verify(public: Path, model: dict, history: dict, checkers: dict,
               control: ExecutionContext) -> None:

        if model.get('version') != 1 or model.get('count') != history['count'] or len(model['parts']) != len(history['pages']):
            raise ValueError('The search index does not match the history')

        for part, page in zip(model['parts'], history['pages']):
            control.check()
            expected_count = page['last'] - page['first'] + 1 if page['first'] else 0

            if (part['path'] != f"parts/{page['number']}.js" or part['number'] != page['number']
                    or part['history'] != '../events/' + page['path'] or part['count'] != expected_count
                    or part['first'] != page['first'] or part['last'] != page['last']):
                raise ValueError('Invalid search-chunk boundaries')

            path = (public / 'search' / part['path']).resolve(strict = True)

            if not path.is_relative_to(public.resolve()):
                raise ValueError('The search chunk escapes the report directory')

            raw = path.read_bytes()

            if hashlib.sha256(raw).hexdigest() != part['sha256']:
                raise ValueError('The search chunk changed')

            text = raw.decode('utf-8')

            if not text.startswith(SearchIndexWriter.PREFIX) or not text.endswith(SearchIndexWriter.SUFFIX):
                raise ValueError('Invalid search-chunk content')

            payload = json.loads(text[len(SearchIndexWriter.PREFIX):-len(SearchIndexWriter.SUFFIX)])

            if (not isinstance(payload, dict) or set(payload) != {'version', 'number', 'rows'}
                    or not isinstance(payload['rows'], list)
                    or SearchIndexWriter.encode(payload) != raw or payload.get('version') != 1
                    or payload.get('number') != page['number'] or len(payload['rows']) != expected_count):
                raise ValueError('Invalid search-chunk format')

            target = (public / 'events' / page['path']).resolve()

            for offset, row in enumerate(payload['rows']):
                control.check()

                if (not isinstance(row, list) or len(row) != 7 or row[0] != page['first'] + offset
                        or not all(isinstance(row[i], str) for i in (1, 2, 3, 5))
                        or (row[4] is not None and not isinstance(row[4], str)) or type(row[6]) is not bool
                        or row[3] not in ('recognized', 'unknown', 'error')):
                    raise ValueError('Invalid search-index row')

                if target not in checkers or f'line-{row[0]}' not in checkers[target].ids:
                    raise ValueError('Search references a missing event')
