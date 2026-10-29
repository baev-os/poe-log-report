import re

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.parsing.DiagnosticSummary import DiagnosticSummary
from poe_log_analyze.stages.composition.specification.LogSpecification import LogSpecification
from poe_log_analyze.stages.composition.specification.RuleFamily import RuleFamily
from poe_log_analyze.stages.composition.specification.RuleSpecification import RuleSpecification
from poe_log_analyze.stages.composition.specification.ValueCatalogue import ValueCatalogue

class SpecificationBuilder:
    """Build the specification from executable rules and the shared explanatory document."""

    @staticmethod
    def group_rules(specification: dict) -> list[dict]:
        """Group localized codes for presentation while preserving recognition priorities."""

        families = {family['code']: family for family in specification['families']}
        rules = [*specification['framing'], *specification['continuations'],
                 *(rule for family in specification['families'] for rule in family['rules'])]
        groups = {}

        for rule in sorted(rules, key = lambda rule: rule['rule_id']):
            code, separator, _ = rule['rule_id'].partition('.')
            group = groups.setdefault(code, {
                'code': code, 'label': code + '.*' if separator else code,
                'description': families.get(code, {}).get('description', ''), 'rules': [],
            })
            group['rules'].append(rule)

        return [groups[code] for code in sorted(groups)]

    @staticmethod
    def build_specification(document: str) -> LogSpecification:
        """Never read user data; always obtain code tables from the parser."""

        descriptions = list(re.finditer(r"^#### `([^`]+)`\n(.*?)(?=^#{2,4} |\Z)", document, re.M | re.S))

        if {item[1] for item in descriptions} != set(RuleCatalogue.RULE_GROUPS):
            raise ValueError('Family descriptions in docs/rules.md do not match the rule catalogue')

        compiled = dict(RuleCatalogue.MESSAGE_RULES)
        briefs = dict(re.findall(r"^\| `([^`]+)` \| [0-9]+ \| .*? \| ([^|]+) \|$", document, re.M))

        if set(briefs) != set(compiled) or any(not text.strip() for text in briefs.values()):
            raise ValueError('Each message code requires a brief description')

        families = []

        for match in descriptions:
            group = match[1]
            section = re.findall(r"^### (.+)$", document[:match.start()], re.M)[-1]
            description = match[2].split("\n|", 1)[0].strip()
            families.append(RuleFamily(group, section, description, tuple(
                RuleSpecification(name, name, "recognized", tuple(compiled[name].groupindex),
                                  compiled[name].pattern, priority, description = briefs[name].strip())
                for priority, name, _ in sorted(RuleCatalogue.RULE_GROUPS[group])
            )))

        framing = (
            RuleSpecification("blank", "blank", "recognized", description = "Строго пустой текст после удаления LF/CRLF; пробельная строка не подходит."),
            RuleSpecification("log.open", "log.open", "recognized", pattern = RuleCatalogue.OPENING.pattern,
                              description = "Маркер открытия лога; время сохраняется в полях timestamp_raw/timestamp."),
            RuleSpecification("header.only", "message.unknown", "unknown", pattern = RuleCatalogue.HEADER.pattern,
                              description = "Заголовок разобран, но текст сообщения не совпал ни с одним правилом."),
            RuleSpecification("unclassified", "unknown", "unknown", description = "Нет подтверждённого заголовка или ожидаемого продолжения."),
            RuleSpecification("encoding.utf8", "encoding.error", "error", description = "Байты строки не декодируются как UTF-8; исходные байты сохранены, text отсутствует."),
            RuleSpecification("timestamp", "timestamp.error", "error", pattern = RuleCatalogue.STAMP,
                              description = "Заголовок найден, но дата неверна или время неоднозначно/не существует в выбранной зоне. Регулярное выражение проверяет только форму."),
        )
        continuations = tuple(
            RuleSpecification(f"{parent}.{next(iter(pattern.groupindex))}", f"{parent}.field",
                              "recognized", tuple(pattern.groupindex), pattern.pattern,
                              parent = parent, sequence = number, description = f"Продолжение {parent}: поле {next(iter(pattern.groupindex))}")
            for parent, patterns in RuleCatalogue.CONTINUATIONS.items()
            for number, pattern in enumerate(patterns, 1)
        )
        catalogues = (
            ValueCatalogue("RELIQUARY_AREAS", "ID и названия специальных областей Reliquary", tuple(
                f"{code} — {name}" for code, name in RuleCatalogue.RELIQUARY_AREAS.items())),
            ValueCatalogue("DIAGNOSTIC_CATEGORIES", "Коды категорий диагностики", tuple(
                f"{code} — {label}" for code, label in DiagnosticSummary.CATEGORIES.items())),
            ValueCatalogue("BOOLEAN_SETTINGS", "Пары подсистема / логический параметр", tuple(
                f"{subsystem} / {name}" for subsystem, names in RuleCatalogue.BOOLEAN_SETTINGS.items() for name in names)),
            ValueCatalogue("APPLY_FAILURES", "Причины отказа применения предмета", RuleCatalogue.APPLY_FAILURES),
            ValueCatalogue("PRECALC_TABLES", "Таблицы предварительного расчёта", RuleCatalogue.PRECALC_TABLES),
            ValueCatalogue("GEAL_REASONS", "Причины ошибок GEAL", RuleCatalogue.GEAL_REASONS),
            ValueCatalogue("SCREEN_PHRASES", "Коды экранных реплик и точные тексты", tuple(
                f"screen.phrase.{key}: {value!r}" for key, value in RuleCatalogue.SCREEN_PHRASES.items())),
            ValueCatalogue("SPEAKERS", "Допустимые подписи реплик", RuleCatalogue.SPEAKERS),
            ValueCatalogue("MAP_ACTIVITY_PREFIXES", "Префиксы областей карт", RuleCatalogue.MAP_ACTIVITY_PREFIXES),
            ValueCatalogue("MAP_BOSS_PREFIXES", "Префиксы областей арен", RuleCatalogue.MAP_BOSS_PREFIXES),
            ValueCatalogue("EVENT_GROUPS", "Коды смысловых групп событий", tuple(
                f"{key} — {value['label']}; prefixes={value['prefixes']!r}; types={value['types']!r}. {value['note']}"
                for key, value in RuleCatalogue.EVENT_GROUPS.items())),
        )
        all_rules = (*framing, *continuations, *(rule for family in families for rule in family.rules))

        return LogSpecification("2", RuleCatalogue.RULES_VERSION, LogParser.SCHEMA_VERSION, RuleCatalogue.HEADER.pattern,
                                framing, tuple(families), continuations, catalogues,
                                len(all_rules), len({rule.type for rule in all_rules}))
