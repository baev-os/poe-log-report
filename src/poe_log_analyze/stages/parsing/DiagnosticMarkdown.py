from poe_log_analyze.stages.parsing.DiagnosticSummary import DiagnosticSummary


class DiagnosticMarkdown:
    """Group the remainder for manual review without changing recognition status."""

    @staticmethod
    def summary_markdown(summary: dict) -> str:
        """Create a local pointer to the complete remainder without inserting raw text."""

        text = (
            "# Очередь разбора неизвестных строк\n\n"
            f"Требуют разбора: {summary['total_lines']} строк, {len(summary['groups'])} групп.\n\n"
            "Группировка не означает распознавание. Статусы unknown/error сохранены.\n"
            "Полные строки, причины и исходные байты — в diagnostics.jsonl.\n"
            "В diagnostic_summary.json есть локальные примеры (до 512 символов) и до 10 номеров строк на группу.\n"
            "В приложении откройте результат и выберите «Неизвестные» или «Ошибки», затем строку для просмотра причины и байтов.\n"
            "После добавления точного правила запустите анализ исходного лога в новый каталог.\n\n"
            "| Категория | Строк | Первая строка | Последняя строка | Группа |\n"
            "| --- | ---: | ---: | ---: | --- |\n"
        )
        return text + "".join(
            f"| {DiagnosticSummary.CATEGORIES[g['category']]} | {g['count']} | {g['first_line']} | {g['last_line']} | `{g['group_id']}` |\n"
            for g in summary["groups"]
        )
