from datetime import datetime

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
from poe_log_analyze.stages.parsing.TechnicalIssueClassifier import TechnicalIssueClassifier
from poe_log_analyze.stages.composition.events.RecordedMessage import RecordedMessage


class TechnicalIssueBuilder:
    """Fault evidence; normal exception-handler registration is not a crash."""

    def __init__(self, descriptions):
        self.descriptions = descriptions
        self.groups, self.parents = {}, {}

    def add(self, row):
        parent = row.get('record_id')

        if parent in self.parents and parent != row['line_number']:
            self.parents[parent]['details'].append(row.get('text') or row.get('reason') or '')
            return None

        kind, level = row['type'], row.get('header', {}).get('level', '')

        category = TechnicalIssueClassifier.category(row)

        if category is None:
            return None

        text = row.get('text') or row.get('reason') or 'Строка не декодируется как UTF-8'
        header = RuleCatalogue.HEADER.fullmatch(text)
        text = header['message'] if header else text
        key = (category, kind)
        group = self.groups.setdefault(key, {'category': category, 'code': kind,
                                            'title': self.descriptions.get(kind, kind), 'events': []})
        stamp = row.get('timestamp')
        event = {'timestamp': stamp, 'time': datetime.fromisoformat(stamp).strftime('%d.%m.%Y %H:%M:%S') if stamp else 'Время неизвестно',
                 'text': text, 'line': row['line_number'], 'details': [], 'level': level,
                 'message': RecordedMessage.from_record(row)}
        group['events'].append(event)
        self.parents[row['line_number']] = event

        return {'category': category, 'title': group['title'], 'text': text}

    def result(self):
        groups = []

        for number, (_, group) in enumerate(sorted(self.groups.items()), 1):
            group['id'] = str(number)
            group['count'] = len(group['events'])
            group['events'].sort(key = lambda e: (not bool(e['timestamp']), e['timestamp'] or '', e['line']))
            groups.append(group)

        return {'groups': groups, 'count': sum(g['count'] for g in groups)}
