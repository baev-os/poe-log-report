import hashlib
import json

from datetime import datetime

from poe_log_analyze.stages.composition.TimelineBuilder import TimelineBuilder
from poe_log_analyze.stages.composition.events.ConversationBuilder import ConversationBuilder
from poe_log_analyze.stages.parsing.TechnicalIssueClassifier import TechnicalIssueClassifier


class BasicEventHistoryBuilder:
    """One pass for conversations, levels, deaths, and dates without a full line overview."""

    @staticmethod
    def build(ledger, expected_sha256, deaths, selection) -> dict:
        chat = ConversationBuilder()
        dates = set()
        levels = {}
        digest = hashlib.sha256()
        line = 0
        processed = 0
        total = ledger.stat().st_size
        control = selection.control
        control.report('Basic report: conversations, characters, and dates', total = total, unit = 'bytes', force = True)

        with ledger.open('rb') as stream:
            for raw in stream:
                control.check()
                row = json.loads(raw)
                digest.update(raw)
                line += 1

                if row['line_number'] != line or row['status'] not in ('recognized', 'unknown', 'error'):
                    raise ValueError('Invalid registry line sequence or statuses')

                stamp = row.get('timestamp')

                if stamp and datetime.fromisoformat(stamp).utcoffset() is None:
                    raise ValueError('Registry timestamps must include a UTC offset')

                processed += len(raw)
                control.report('Basic report: conversations, characters, and dates', processed, total, unit = 'bytes')
                primary = row['status'] == 'recognized' and row.get('record_id') == row['line_number']

                # Pre-period levels support the shared chart methodology and stable character IDs.
                if primary and row['type'] == 'screen.level_up' and row.get('timestamp'):
                    level = TimelineBuilder.event(row, selection.zone)
                    levels.setdefault(level['timestamp'][:10], {'events': []})['events'].append(level)

                if not selection.period.contains(row.get('timestamp'), selection.zone_name):
                    continue

                chat.add(row)
                deaths.add(row)
                kind = row['type']
                event = (primary and stamp and kind in TimelineBuilder.EVENT_TYPES
                         and kind not in ('area.enter', 'log.open'))
                loading = primary and kind == 'loading.duration'

                if event or loading or TechnicalIssueClassifier.category(row) is not None:
                    dates.add(datetime.fromisoformat(stamp).astimezone(selection.zone).date().isoformat() if stamp else 'undated')

        if digest.hexdigest() != expected_sha256:
            raise ValueError('The registry changed while building the basic report')

        control.check()

        return {'conversations': chat.result(), 'dates': dates,
                'timeline': {'timezone': selection.zone_name, 'days': [{'date': key} for key in sorted(levels)],
                             'by_date': levels}}
