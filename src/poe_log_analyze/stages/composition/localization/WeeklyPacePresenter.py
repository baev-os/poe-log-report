from poe_log_analyze.stages.composition.localization.ComparisonPresenter import ComparisonPresenter


class WeeklyPacePresenter:
    """Weekly comparison labels share duration and delta formatting."""

    @staticmethod
    def present(model: dict, catalogue) -> None:
        formatter = ComparisonPresenter(catalogue)

        for week in model['weeks']:
            for zone in week['zones']:
                zone['share_label'] = formatter.format(zone['share'], 'percent')

        for panel in model['panels']:
            for row in panel['rows']:
                row['afk_share_label'] = formatter.format(row['afk_share'], 'share')

                for change in row['changes']:
                    change['label'] = catalogue.text(change['label_key'])

                    for key in ('a', 'b', 'delta'):
                        change[key + '_text'] = formatter.format(change[key], change['kind'], signed = key == 'delta')

                    change['change_text'] = formatter.format(change['change_percent'], 'percent', signed = True)
