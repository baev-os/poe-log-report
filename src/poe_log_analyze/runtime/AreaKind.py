"""Stable area codes and support for legacy projections."""


class AreaKind:
    """Accept legacy Russian labels only at the compatibility boundary."""

    LEGACY = {"Карта": "map", "Арена": "arena", "Область": "area",
              "Город": "town", "Убежище": "hideout"}

    @staticmethod
    def code(record: dict) -> str:
        code = record.get("kind_code") or AreaKind.LEGACY.get(record.get("kind"), record.get("kind"))

        if code not in AreaKind.LEGACY.values():
            raise ValueError(f"Unknown area kind code: {code}")

        return code
