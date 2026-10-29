# Requirements

Input consists of one or more Path of Exile 1 logs and their time zone.
Every byte is accounted for; unknown and erroneous records are preserved separately.
Input files are not modified. Shared copied sections are counted once,
and independent continuations are preserved. Unknown time boundaries are not invented.

The basic report contains charts, characters, maps, a calendar, and conversations.
The extended report adds detailed history, analytics, and technical pages.
Selected report types are generated in HTML and PDF. Supported options include en/ru,
periods, period comparisons, and a shared theme setting for PDFs and images.

Sites open locally. Interactive charts show axis values and units on hover
and focus; Escape closes the tooltip.
The GUI displays progress and supports cancellation. An unsuccessful run preserves
the previous report. Measurements can be reproduced from a saved analysis.
