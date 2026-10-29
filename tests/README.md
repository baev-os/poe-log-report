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

On Windows, set the same environment variables and use
`.\.venv\Scripts\python.exe`. GUI checks require a graphical display;
a separate Xvfb works on Linux. Browser checks run through separate
`tests/*BrowserCheck.py` scripts. Run heavy operations sequentially,
limiting combined memory usage to 8 GiB. Store temporary results in `build/`.
