# Architecture

[ReportGenerator](../src/poe_log_analyze/core/ReportGenerator.py) controls
seven stages: preparation → parsing → reconstruction → merging → composition
→ rendering → verification. Core owns cancellation, progress, and publication.
Stages accept explicit inputs, perform their work, and return results.

`runtime` contains paths, resources, and JSON; `desktop` contains Tkinter and the worker thread;
`cli` provides analysis and export commands; `tooling` handles builds and resource preparation.
Calculations use shared measurements for HTML and PDF. Recognition is described
in the [rule reference](rules.md). Templates and resources are in `site/`;
report texts and translations are in `reports/`.

Each class lives in an identically named file. Preserve current contracts,
saved analysis formats, and the direction of dependencies between packages.
