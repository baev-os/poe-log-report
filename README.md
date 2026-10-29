# PoE Log Report

A local Path of Exile 1 log analyzer. Generates basic and extended HTML/PDF
reports covering playtime, characters, maps, a calendar, conversations, and analytics.
Reports default to English; Russian can be selected in the interface.
Each selected report type automatically includes a PDF.

## Run

Requires Python 3.14 and Tkinter/Tcl/Tk.

Linux:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python scripts/poe_desktop.py
```

Windows PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe scripts/poe_desktop.py
```

Add logs, check the time zone, select report types, and start the analysis.
Results are saved in `report/`; open `index.html` to view them.
A successful analysis replaces the previous report. Errors and cancellation preserve it.
Logs, reports, the environment, and local settings are excluded from Git.

CLI: `python -m poe_log_analyze --help` and
`python -m poe_log_analyze.report --help` with `PYTHONPATH=src`.

## Build and checks

Install `requirements-build.txt`, then run `./build.sh` on Linux
or `.\build.ps1` on Windows with MSVC x64. The distribution is created in `build/`.
To check the source, install `requirements-dev.txt`:
[check commands](tests/README.md).

The code is licensed under [MIT](LICENSE). Library licenses and game resource terms
are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
This project is not affiliated with or endorsed by Grinding Gear Games.
