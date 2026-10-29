This is a specification of supported Client.txt formats and our analyzer's codes,
not an official exhaustive reference to Path of Exile internals.
Unsupported lines remain unknown/error. The catalogue is built from the rules
of the application exporting this report; an old analysis is not reparsed.

## Line format

Input is read as bytes, separated by LF. CRLF is preserved; a lone CR does
not split a line. The final nonempty fragment without LF is also counted.
Text is decoded strictly as UTF-8 without globally stripping whitespace.

A standard header:

```text
YYYY/MM/DD HH:MM:SS tick source [LEVEL Client PID] message
```

`tick` and `PID` are decimal numbers; `source` is a hexadecimal field.
Levels: `INFO`, `DEBUG`, `WARN`, `CRIT`, `ERROR`.
The meaning of `tick` and `source` is unknown.
Timestamps use the selected IANA zone. Invalid dates, ambiguous times and
nonexistent local times produce an error; the offset is not guessed.

## Statuses and codes

| Status | Meaning |
| --- | --- |
| `recognized` | A specific message format rule matched in full |
| `unknown` | Unsupported format; original bytes and reason are retained |
| `error` | Decoding or timestamp error |

A game error message can be recognized: this does not mean the described
operation succeeded. `type` is the line type and `rule_id` is the applied
classifier. They match for message rules, but can differ for diagnostics
and continuations.

## Ledger fields

| Field | Type and meaning |
| --- | --- |
| `line_number` | Integer: physical line number, starting at one |
| `byte_start`, `byte_end` | Integers: byte range `[start, end)`, including the delimiter |
| `raw_base64` | Base64 string: exact bytes including LF/CRLF |
| `line_ending` | `LF`, `CRLF` or `none` |
| `text` | UTF-8 text without delimiter; absent on decoding error |
| `status`, `type`, `rule_id`, `rule_version` | Strings: classification and rules version |
| `record_id` | Parent line number or null |
| `fields` | Named rule fields: strings, or null for an optional group |
| `reason` | Reason for unknown/error; null for recognized |
| `timestamp_raw` | Original timestamp if a header was found |
| `timestamp` | ISO 8601 with offset after successful time conversion |
| `header` | Object containing the standard header's `tick`, `source`, `level`, `pid` |

Every physical line is accounted for exactly once. Byte ranges cover the
whole file without gaps or overlaps. Complete accounting and complete
recognition differ: the latter requires no unknown/error lines.

## Applying rules

Message patterns use fullmatch after the header is separated.
Lower priority numbers are checked first; the first match sets the type.
Fields are preserved literally. Expandable blocks show the exact Python
regular expressions: backslash escapes and delimiters are significant.

Continuations must immediately follow their parent in the specified order.
Their type is `<parent>.field` and rule code is `<parent>.<field>`.
An empty, invalid or unexpected line breaks the sequence. A continuation has
no timestamp of its own. A truncated sequence at end of file does not yet
produce a separate missing-lines error.

## Interpretation limits

Numeric `action_id`, `skill_type_id`, `object_id`, `flags`, `event_id`,
instance identifiers and other dynamic values have no invented value
catalogue here. The pattern specifies their accepted shape; their game
meaning may be unknown. Area, item and passive IDs are field values, not rule
codes. RePoE matching is a separate investigation and does not substitute
for confirmed interpretation of a line.

The finite sets below come from the current rule catalogue. Speaker labels
do not prove an NPC role. Map/arena prefixes are used only by analytics.
User messages, conversations and raw log lines are not included in this reference.
