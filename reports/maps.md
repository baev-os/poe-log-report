Select the starting day of a run. A map can continue past midnight:
all of its visits are shown under the day of its first entry.

Maps are identified using the game area and map item catalogue.
Known boss arena families are shown separately. Other activities, including
Machinist’s Vault, Heist and the campaign, appear on the areas page and
are not included in the map count.

Entry is confirmed by “area generation → area entry”.
A return is merged with the last map only if the area ID, nonzero seed and
Client-Safe Instance ID match. The area name is not an identifier.
Hideouts and other areas between entries are excluded from time inside the map.

Time is measured from the entry message to the next instance connection
(or generation/entry if the connection message is missing).
This is an estimate based on client messages, not combat time.
Loading before entry is excluded. AFK is the portion explicitly marked
by AFK mode; no AFK marker does not prove active play.
Loss of window focus is not treated as a pause.

Log opening, disconnection, a clock regression, a transition without a time,
or a gap over 30 minutes between dated lines breaks the link between visits.
The threshold is a conservative observation boundary, not proof of inactivity.
Unfinished intervals have no duration and are excluded from totals.
End of file is not a map exit. Closing a run record does not imply a boss
kill, a full clear or successful map completion.

Death messages may concern other characters. The cumulative death counter
is not added to these messages. Unknown lines may conceal transitions;
recognition coverage remains a separate measure of confidence.
