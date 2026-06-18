# AGENTS.md

## Run / Test / Build

```bash
# All commands use the venv python directly (no activate needed)
.venv\Scripts\python.exe main.py              # Run GUI
.venv\Scripts\python.exe -m unittest test_converter -v  # Run tests
.venv\Scripts\python.exe build.py             # Package to exe
```

Install deps: `.venv\Scripts\pip.exe install -r requirements.txt`

The venv python path must be the full `.venv\Scripts\python.exe` — do not rely on `python` being on PATH.

## Architecture

Two-layer design: `core/` (pure logic, no Qt) and `gui/` (PyQt6 widgets + workers).

- `main.py` — GUI entrypoint, loads `gui/main_window.py` and `gui/styles/dark.qss`
- `converter.py` — legacy CLI version (still works standalone, uses colorama)
- `core/converter.py` — MediaConverter engine, uses callbacks (`on_log`, `on_progress`) not print()
- `core/queue.py` — batch queue with ThreadPoolExecutor
- `gui/workers/` — QThread wrappers that bridge core callbacks to Qt signals
- `gui/widgets/param_panel.py` — all conversion params; buttons use QGridLayout for auto-wrap
- `gui/dialogs/batch_dialog.py` — standalone batch conversion dialog
- `ico/Miku.ico` — app icon, referenced by main.py and build.py

## Key gotchas

- `pip install` sometimes installs to a different venv at `D:\MediaConverter\.venv` instead of the project's `.venv`. If import fails after install, use `pip install --target .venv\Lib\site-packages`.
- PyQt6 is ~80MB. The venv at `.venv` is not committed (`.gitignore`).
- `build.py` reads FFmpeg path from env var `FFMPEG_PATH` or falls back to a hardcoded path. Set it before running.
- `core/converter.py` needs `subprocess.CREATE_NO_WINDOW` flag — Windows only, no Linux/macOS support.
- Tests import from `converter.py` (the CLI module), not from `core/`. The old tests still pass because the CLI module is untouched.
- `gui/styles/dark.qss` is loaded at runtime by `main.py` and bundled by `build.py` via `--add-data`.

## Conventions

- Chinese UI text throughout (buttons, labels, messages). Keep it Chinese.
- All new error handling must use specific exceptions (`OSError`, `ValueError`), never bare `except:`.
- FFmpeg extra args are whitelisted in `core/validators.py` `SAFE_FFMPEG_FLAGS`. Add new flags there, not inline.
- Output files use `_converted`, `_compressed`, `_batch` suffixes before the extension.
