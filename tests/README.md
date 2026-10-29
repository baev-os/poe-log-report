# Checks

All inputs are synthetic. Install `requirements-desktop.txt` and `requirements-dev.txt`.
From the project root on Linux:

```bash
mkdir -p build/tmp
export TMPDIR="$PWD/build/tmp" TEMP="$PWD/build/tmp" TMP="$PWD/build/tmp"
export PYTHONPATH=src
.venv/bin/python -B -m unittest discover -s tests -p '*Tests.py' -v
.venv/bin/python -B -m mypy
```

`python scripts/check.py` runs both checks sequentially and retains logs and a
summary in `build/checks/`. Add `--browser` on Linux to run every separate browser
scenario after the source checks. The CI workflows use the same entry point.

`python scripts/scan_secrets.py --output build/audit-final` scans all available
Git refs and nonignored source files using the verified Gitleaks 8.24.3 binary
at `build/tools/gitleaks`. It retains aggregate counts only and fails on findings
or scanner errors. The Linux CI job installs the checksum-pinned scanner.

On Windows, set the same environment variables and use
`.\.venv\Scripts\python.exe`. GUI checks require a graphical display;
a separate Xvfb works on Linux. Browser checks run through separate
`tests/*BrowserCheck.py` scripts. Run heavy operations sequentially,
limiting combined memory usage to 8 GiB. Store temporary results in `build/`.
