import json

from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext


class LogHistoryReader:
    """Read temporary pages without retaining the entire event overview."""

    @staticmethod
    def pages(path: Path, model: dict, control: ExecutionContext):
        with path.open('rb') as stream:
            for page in model['pages']:
                control.check()
                raw = stream.readline()

                if not raw:
                    raise ValueError('Missing event-history page')

                rows = json.loads(raw)
                expected = page['last'] - page['first'] + 1 if page['first'] else 0

                if not isinstance(rows, list) or len(rows) != expected:
                    raise ValueError('Invalid event-history page row count')

                for offset, row in enumerate(rows):
                    if not isinstance(row, dict) or row.get('line') != page['first'] + offset:
                        raise ValueError('Invalid event-history line order')

                control.check()
                yield {**page, 'rows': rows}
                del rows

            control.check()

            if stream.read(1):
                raise ValueError('Unexpected event-history page')
