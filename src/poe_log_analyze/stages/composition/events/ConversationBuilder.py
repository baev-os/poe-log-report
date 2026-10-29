from datetime import datetime, timezone


class ConversationBuilder:
    """Group private conversations by peer and other messages by channel."""

    def __init__(self):
        self.groups = {}

    def add(self, row):
        if row['status'] != 'recognized' or row['type'] not in ('chat.whisper', 'chat.channel', 'chat.local'):
            return

        fields = row['fields']
        whisper = row['type'] == 'chat.whisper'
        local = row['type'] == 'chat.local'
        key = ('local', '') if local else (('whisper', fields['character']) if whisper else ('channel', fields['channel']))
        title = 'Локальный чат' if local else (fields['character'] if whisper else 'Канал '+fields['channel'])
        group = self.groups.setdefault(key, {'title': title,
                                            'kind': 'Личная переписка' if whisper else 'Общий разговор',
                                            'kind_code': key[0], 'channel': fields.get('channel'), 'messages': []})
        stamp = row.get('timestamp')
        group['messages'].append({'timestamp': stamp, 'time': datetime.fromisoformat(stamp).strftime('%d.%m.%Y %H:%M:%S') if stamp else 'Время неизвестно',
                                  'utc': datetime.fromisoformat(stamp).astimezone(timezone.utc).isoformat() if stamp else '',
                                  'character': fields['character'], 'guild': fields.get('guild'),
                                  'direction': 'Вы →' if fields.get('direction') == 'To' else ('←' if whisper else ''),
                                  'text': fields['message'], 'line': row['line_number']})

    def result(self):
        groups = []

        for number, (_, group) in enumerate(sorted(self.groups.items()), 1):
            group['id'] = str(number)
            group['messages'].sort(key = lambda m: (not bool(m['utc']), m['utc'], m['line']))
            group['count'] = len(group['messages'])
            groups.append(group)

        return {'groups': groups, 'count': sum(g['count'] for g in groups)}
