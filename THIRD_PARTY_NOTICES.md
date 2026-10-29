# Third-party notices

The project's own code is licensed under [MIT](LICENSE). This license does not replace
the terms for libraries, fonts, or game materials.

- Python: PSF; Tcl/Tk: their original notices.
- Windows copied DLLs: exact binary hashes, component versions, upstream sources,
  and notice mappings are recorded in [licenses/WindowsNative.json](licenses/WindowsNative.json).
  Microsoft runtime files retain their separate
  [governing conditions](licenses/WINDOWS_RUNTIME.md); the project's MIT license
  does not relicense them.
- Jinja2, MarkupSafe, Python-Markdown, and ReportLab: BSD.
- Bootstrap, Pillow, and charset-normalizer: their respective MIT notices.
- tzdata: Apache-2.0 and separate IANA database terms.
- Nuitka: AGPL-3.0 with the Runtime Library Exception for compiled output.
  Patchelf is used during the build.
- DejaVu Sans: original notices in [reports/fonts/LICENSE.txt](reports/fonts/LICENSE.txt).

The full license texts for the actual dependencies are collected in
`app/poe_log_analyze/resources/licenses/THIRD_PARTY_LICENSES.txt`.
Versions and sources are included in the notice bundle. The original licenses
for Bootstrap, Exile-UI, Tcl/Tk, and system libraries are preserved unchanged.

The mercenary greeting list comes from
[Exile-UI](https://github.com/Lailloken/Exile-UI), commit
`3152d169dbbc3dc19308b42ac4b3f45538713070`, MIT, Copyright (c) 2022 Lailloken.
Notice: [licenses/Exile-UI.txt](licenses/Exile-UI.txt).
Sources and hashes: [docs/mercenary-greetings.json](docs/mercenary-greetings.json).

Game data and images belong to Grinding Gear Games.
The project's and RePoE's MIT licenses grant no additional rights to game materials.
The maintainer includes these materials in good faith for this noncommercial
fan-made log-analysis project. The project's fair-use rationale is not an
established legal determination or GGG permission. GGG retains its rights;
the maintainer will remove or replace affected materials on a request from GGG.
[Contents, sources, and maintainer decision](licenses/GAME_DATA.md).
