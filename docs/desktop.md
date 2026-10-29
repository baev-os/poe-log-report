# Desktop application

Run `scripts/poe_desktop.py`; Python 3.14 and Tkinter/Tcl/Tk are required.
Add logs and select a time zone, language, and report types. PDFs are created
automatically for the selected types. The report period is optional.

Processing runs in a worker thread; the GUI displays progress and an execution log.
Cancellation and errors preserve the previous result.

To build, install `requirements-build.txt` and run `build.sh` on Linux
or `build.ps1` on Windows with MSVC x64. Move the entire
`poe_desktop.dist` directory, including `app/` and the license notices.
Check the finished distribution on its target OS; source tests do not replace this check.
