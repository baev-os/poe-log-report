import json

from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.rendering.LogHistoryReader import LogHistoryReader


class LogHistoryJsonWriter:
    """Preserve events v2 by serializing only one page at a time."""

    @staticmethod
    def write(path: Path, model: dict, event_rows: Path, control: ExecutionContext) -> None:
        encoder = json.JSONEncoder(ensure_ascii = False, sort_keys = True, indent = 2)

        with path.open('w', encoding = 'utf-8', newline = '\n') as stream:
            stream.write('{\n')

            for index, key in enumerate(sorted(model)):
                control.check()

                if index:
                    stream.write(',\n')

                stream.write('  ' + json.dumps(key, ensure_ascii = False) + ': ')

                if key == 'pages':
                    stream.write('[\n')

                    for number, page in enumerate(LogHistoryReader.pages(event_rows, model, control)):
                        if number:
                            stream.write(',\n')

                        stream.write('    ')

                        for chunk in encoder.iterencode(page):
                            stream.write(chunk.replace('\n', '\n    '))

                        del page

                    stream.write('\n  ]')
                else:
                    text = json.dumps(model[key], ensure_ascii = False, sort_keys = True, indent = 2)
                    stream.write(text.replace('\n', '\n  '))

            stream.write('\n}\n')

        control.check()
