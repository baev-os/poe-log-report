The report shows accounting and recognition coverage for a single player history.
Every physical line is classified, including empty lines and continuations.
Confirmed copied history is counted once.

**Complete accounting** means the analysis preserves all source lines and bytes.
**Complete recognition** requires no unknown lines or parsing errors.
A recognized header alone does not mean the message is recognized.
The number of lines is not the number of game events.

Unknown lines and errors retain their original bytes and reasons; analysis
continues for the other lines. Diagnostic categories help investigate the
remainder but do not constitute recognition. Client issues have a separate
technical page and are distinct from log reading errors.

Expand a category under “Needs investigation” to see its full messages.
Exact repeats have an occurrence count; invalid UTF-8 lines have no text
representation. Line numbers refer to the merged history.
