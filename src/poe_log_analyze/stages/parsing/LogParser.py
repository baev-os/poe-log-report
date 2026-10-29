from poe_log_analyze.stages.parsing.TimestampParser import TimestampParser

from base64 import b64encode
from typing import BinaryIO, Iterator
from zoneinfo import ZoneInfo

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
from poe_log_analyze.stages.parsing.ReliquaryContext import ReliquaryContext

class LogParser:
    """Read physical lines and recognize messages conservatively."""

    SCHEMA_VERSION = "1"

    @staticmethod
    def iter_records(source: BinaryIO, zone: ZoneInfo) -> Iterator[dict]:
        """Emit one record per LF fragment with an exact copy of original bytes."""

        offset = 0
        pending = ()
        parent = None
        parent_type = None
        characters = set()
        reliquary = ReliquaryContext()

        for number, raw in enumerate(source, 1):
            if raw.endswith(b"\r\n"):
                body, ending = raw[:-2], "CRLF"
            elif raw.endswith(b"\n"):
                body, ending = raw[:-1], "LF"
            else:
                body, ending = raw, "none"

            record = {
                "line_number": number, "byte_start": offset, "byte_end": offset + len(raw),
                "raw_base64": b64encode(raw).decode("ascii"), "line_ending": ending,
                "status": "unknown", "type": "unknown", "rule_id": "unclassified",
                "rule_version": RuleCatalogue.RULES_VERSION, "record_id": None, "fields": {},
                "reason": "The line does not match known rules",
            }
            offset += len(raw)

            try:
                text = body.decode("utf-8", errors = "strict")
            except UnicodeDecodeError as error:
                record.update(status = "error", type = "encoding.error", rule_id = "encoding.utf8",
                              reason = f"UTF-8 error in line bytes [{error.start}, {error.end})")
                pending = ()
                reliquary.reset()
                yield record
                continue

            record["text"] = text

            if text == "":
                record.update(status = "recognized", type = "blank", rule_id = "blank", reason = None)
                # An empty line breaks the expected continuation; do not guess the link.
                pending = ()
                yield record
                continue

            continuation = pending[0].fullmatch(text) if pending else None

            if continuation:
                record.update(status = "recognized", type = f"{parent_type}.field",
                              rule_id = f"{parent_type}.{next(iter(continuation.groupdict()))}",
                              record_id = parent, fields = continuation.groupdict(), reason = None)

                if parent_type != 'reliquary.message':
                    pending = pending[1:]

                yield record
                continue

            pending = ()

            opening = RuleCatalogue.OPENING.fullmatch(text)
            header = RuleCatalogue.HEADER.fullmatch(text)
            match = opening or header

            if match:
                record["record_id"] = number
                record["timestamp_raw"] = match["timestamp"]

                try:
                    record["timestamp"] = TimestampParser.timestamp_iso(match["timestamp"], zone)
                except ValueError as error:
                    record.update(status = "error", type = "timestamp.error", rule_id = "timestamp",
                                  reason = f"Invalid timestamp: {error}")
                    reliquary.reset()
                    yield record
                    continue

            if opening:
                record.update(status = "recognized", type = "log.open", rule_id = "log.open", reason = None)
            elif header:
                reliquary.prepare(header)
                record["header"] = {key: header[key] for key in ("tick", "source", "level", "pid")}
                record.update(type = "message.unknown", rule_id = "header.only",
                              reason = "The header was parsed but the message content was not recognized")

                for rule_id, pattern in RuleCatalogue.MESSAGE_RULES:
                    message = pattern.fullmatch(header["message"])

                    if message:
                        if rule_id == "chat.local":
                            guild = message['guild']
                            tagged = header['level'] == 'INFO' and guild and guild[1:-1].strip()

                            # A tag confirms only this record; an untagged form requires previous name context.
                            if message["character"] not in characters and not tagged:
                                continue

                        if rule_id == 'reliquary.message' and not reliquary.accepts(header):
                            continue

                        if rule_id in RuleCatalogue.RELIQUARY_PHRASES and reliquary.accepts(header):
                            continue

                        record.update(status = "recognized", type = rule_id, rule_id = rule_id,
                                      fields = message.groupdict(), reason = None)
                        pending = RuleCatalogue.CONTINUATIONS.get(rule_id, ())

                        if rule_id == "dialogue.named" and not header["message"].endswith("\r"):
                            pending = ()

                        if rule_id in ("screen.character_info", "screen.level_up", "screen.slain", "screen.suicide",
                                       "screen.area_presence", "chat.whisper", "chat.channel"):
                            characters.add(message["character"])

                        parent, parent_type = number, rule_id
                        break

            reliquary.observe(record)
            yield record
