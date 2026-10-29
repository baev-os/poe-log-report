from poe_log_analyze.stages.composition.localization.ComparisonPresenter import ComparisonPresenter


class AnalyticsPresenter:
    """Format analytics numbers without modifying original messages."""

    @staticmethod
    def present(views, catalogue) -> None:
        presenter = ComparisonPresenter(catalogue)

        for session in views['session_rhythm']['by_session'].values():
            session['difference_label'] = presenter.format(session['rate_difference'], 'number', signed = True)

            for row in [session['early'], session['late'], *session['bins']]:
                row['rate_label'] = presenter.format(row['rate'], 'number')
                row['rate_without_afk_label'] = presenter.format(row['rate_without_afk'], 'number')

        for row in [*views['mechanic_combinations']['sets'], *views['mechanic_combinations']['pairs']]:
            row['share_label'] = presenter.format(row['share'], 'percent')

        for mode in views['mechanic_combinations']['modes'].values():
            for group in mode['groups']:
                for sample in group['samples']:
                    sample['difference'] = presenter.format(sample['difference_seconds'], 'duration', signed = True)

        for row in views['remaining_monsters']['bins']:
            row['share_label'] = presenter.format(row['share'], 'percent')

        for row in views['remaining_monsters']['groups']:
            row['median_label'] = presenter.format(row['median_count'], 'number')

        profile = views['return_profile']
        profile['share_label'] = presenter.format(profile['share'], 'percent')

        for row in profile['buckets']:
            row['share_label'] = presenter.format(row['share'], 'percent')

        for group in views['marker_intervals']['groups']:
            group['median_maps_label'] = presenter.format(group['median_maps'], 'number')
            group['max_maps_label'] = presenter.format(group['max_maps'], 'number')

        for field in ('summaries', 'days', 'sessions', 'areas'):
            for row in views['network_health'][field]:
                AnalyticsPresenter.samples(row['stats'], presenter)

        AnalyticsPresenter.samples(views['trade_api']['summary'], presenter)

        for row in views['trade_api']['groups']:
            AnalyticsPresenter.samples(row['stats'], presenter)

        for view, field in (('memory_history', 'groups'), ('startup_history', 'stages'), ('client_environment', 'groups')):
            for row in views[view][field]:
                AnalyticsPresenter.samples(row['stats'], presenter)

        for row in views['memory_history']['rows']:
            row['change_labels'] = {key: presenter.format(value, 'number', signed = True)
                                    for key, value in row['changes'].items()}

        for row in views['memory_history']['plots']:
            row['maximum_label'] = presenter.format(row['maximum'], 'number')

        for row in views['client_environment']['issues']:
            row['rate_label'] = presenter.format(row['per_hour'], 'number')
            row['exposure_label'] = presenter.format(row['seconds'], 'duration')

        for row in views['client_environment']['exposure']:
            row['duration_label'] = presenter.format(row['seconds'], 'duration')

        for row in views['client_environment']['comparisons']:
            row['difference_label'] = presenter.format(row['difference'], 'number', signed = True)

        for view in ('startup_history', 'milestone_history'):
            for row in views[view]['rows']:
                row['duration_label'] = presenter.format(row['seconds'], 'duration')

                if view == 'milestone_history':
                    row['clock_label'] = presenter.format(row['clock_seconds'], 'duration')

        for row in views['measurement_coverage']['rows']:
            row['share_label'] = presenter.format(row['share'], 'percent')

        for summary in [views['map_pool']['summary'], *views['map_pool']['weeks']]:
            for key in ('top1', 'top3'):
                summary[key + '_label'] = presenter.format(summary[key], 'percent')

            for row in summary['types']:
                row['share_label'] = presenter.format(row['share'], 'percent')

        for row in views['acquisition_history']['cards']:
            row['share_label'] = presenter.format(row['share'], 'percent')

        for row in views['marker_order']['rows']:
            row['elapsed_label'] = presenter.format(row['seconds'], 'duration')

        for row in views['fault_intervals']['rows']:
            for choice in row['choices']:
                choice['elapsed_label'] = presenter.format(choice['span']['elapsed_seconds'], 'duration')

    @staticmethod
    def samples(stats, presenter) -> None:
        for field in ('min', 'median', 'mean', 'p95', 'max'):
            stats[field + '_label'] = presenter.format(stats[field], 'number')
