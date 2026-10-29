"""Message presentation with the original text available."""

from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue


class EventMessagePresenter:
    """Translate confirmed formats; preserve field values and free text."""

    def __init__(self, catalogue: TranslationCatalogue):
        self.catalogue = catalogue

    def present(self, message: dict) -> dict:
        original = message["original"]
        code, fields = message["code"], message["fields"]
        text = original if original is not None else self.catalogue.text("message.undecodable")
        parameters = []

        if message["recognized"] and not code.startswith(("chat.", "dialogue.", "reliquary.")):
            if self.catalogue.language == "ru":
                key = "event." + code
                text = (self.catalogue.text(key, **fields) if key in self.catalogue.messages
                        else self.catalogue.rule_title(code))

            parameters = [{"code": key, "label": self.catalogue.text("field." + key), "value": value}
                          for key, value in fields.items() if value is not None and "field." + key in self.catalogue.messages]

        return {"text": text, "original": original if original != text else None, "parameters": parameters}
