import re

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


class TechnicalIssueClassifier:
    """Shared technical-message indicators; a missing log ending is not a crash."""

    FAILURE_TYPES = {'render.device_failed', 'graph.deadlock', 'network.abnormal_disconnect',
                     'network.instance_disconnect', 'network.site_settings_ssl_failed',
                     'screen.join_instances_failed', 'screen.achievement_server_failed', 'screen.join_disconnected',
                     'action.trigger_failed', 'action.execute_failed', 'action.instant_failed',
                     'geal.error', 'geal.path_error', 'steam.stat_failed', 'daily_deal.download_failed'}
    CRASH = re.compile(r'\b(?:unhandled exception|fatal error|crashed|crash dump|access violation|segmentation fault)\b', re.I)

    @classmethod
    def category(cls, row: dict) -> str | None:
        kind, level = row['type'], row.get('header', {}).get('level', '').upper()

        if kind == 'job.exception_callback' or row.get('record_id') not in (None, row['line_number']):
            return None

        text = row.get('text') or row.get('reason') or ''
        header = RuleCatalogue.HEADER.fullmatch(text)
        text = header['message'] if header else text

        if row['status'] == 'error':
            return 'reading'

        if cls.CRASH.search(text) and not kind.startswith(('chat.', 'reliquary.')):
            return 'crash'

        if level in ('ERROR', 'CRIT', 'CRITICAL', 'FATAL', 'WARN', 'WARNING') or kind in cls.FAILURE_TYPES:
            return 'warning' if level in ('WARN', 'WARNING') else 'client'

        return None
