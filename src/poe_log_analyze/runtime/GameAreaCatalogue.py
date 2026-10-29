import json

from functools import cache

from poe_log_analyze.runtime.RuntimeResources import RuntimeResources
from poe_log_analyze.runtime.AreaKind import AreaKind

class GameAreaCatalogue:
    """Pinned area types and local icons from RePoE game data."""

    @staticmethod
    @cache
    def areas():
        path = RuntimeResources.resource_root() / "site/data/areas.json"
        return json.loads(path.read_text(encoding = "utf-8"))["areas"]

    @staticmethod
    def lookup(area_id):
        area = GameAreaCatalogue.areas().get(area_id, {"kind": "Область", "icon": ""})
        return {**area, "kind_code": AreaKind.code(area)}
