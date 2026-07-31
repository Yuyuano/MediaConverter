# AGENTS.md

## Run / Test / Build

```bash
# All commands use the venv python directly (no activate needed)
.venv\Scripts\python.exe main.py              # Run GUI
.venv\Scripts\python.exe -m unittest discover tests -v  # Run all tests (228 tests across 12 files)
.venv\Scripts\python.exe -m unittest backup.test_converter -v  # Run legacy CLI tests (19 tests; total 247)
.venv\Scripts\python.exe build.py             # Package to exe (needs FFmpeg binaries in ffmpeg/ dir)
```

Install deps: `.venv\Scripts\pip.exe install -r requirements.txt`
(colorama is now uncommented in requirements.txt for legacy backup tests)
Build deps (optional): `.venv\Scripts\pip.exe install pyinstaller>=5.0`

Create venv (if missing): `python -m venv .venv`

The venv python path must be the full `.venv\Scripts\python.exe` — do not rely on `python` being on PATH.

**QSS theme uses solid MD3 surfaces + pre-blended state layers** — no rgba translucency. `gui/theme.py` `_derive_tokens()` pre-computes all derived tokens as opaque hex: container fills from `surface_container*` levels, and MD3 state layers (hover = content color @8%, pressed = @12%) pre-blended via `_blend()` since QSS cannot composite background layers. `material.qss` styles both `QPlainTextEdit` and `QTextEdit` (shared selector) since `ProgressPanel` and `BatchDialog` use `QTextEdit` for HTML-colored log output. **DO NOT add hardcoded color values inline in Python widgets** — use QSS ObjectName selectors or `theme_manager.tokens.get('key')` for dynamic colors. **Plain `QWidget` subclasses do NOT paint QSS backgrounds** — set `Qt.WidgetAttribute.WA_StyledBackground` (done for `Sidebar`, `sidebarSep`, main window `centralWidget`).

**PyQt6 6.7+ removed `QTextEdit.appendHtml()`** — replace with `textCursor().movePosition(End) + insertHtml()` + `insertBlock()`.

**No lint/typecheck configured yet** — add `ruff` or `mypy` if needed.

**MD3 Theme System**: Dual dark/light themes via `gui/theme.py` ThemeManager. QSS is a single template `gui/styles/material.qss` with `{token_name}` placeholders. At startup, `main.py` creates ThemeManager, calls `load_theme()`, which does `template.format(**tokens)` → `app.setStyleSheet()`. Theme toggle via status bar ☀/🌙 button. Preference saved to `history/.theme_pref`. Token dicts (`DARK_TOKENS` / `LIGHT_TOKENS`) defined in theme.py with derived solid tokens auto-computed by `_derive_tokens()` (state layers pre-blended by `_blend()`). DO NOT add hardcoded colors inline in Python — use QSS ObjectName selectors instead. Dynamic colors (like status bar messages) must use `theme_manager.tokens.get('key')`. FileDropWidget's drop label uses dynamic property `state` (`""`/`"drag"`/`"selected"`) + `style().unpolish()/polish()` for its three visual states — never inline styles.

## Architecture

Three-layer design: `core/` (pure logic, no Qt), `gui/` (PyQt6 widgets + workers), `gui/pages/` (page-level composition).

- `main.py` — GUI entrypoint; `main()` function handles `sys.path` setup, logging config, QApplication creation, stylesheet loading, and MainWindow launch. No module-level side effects.
- `core/constants.py` — shared file extension sets (`VIDEO_EXTS`, `IMAGE_EXTS`, `AUDIO_EXTS`, `ALL_MEDIA_EXTS`) + `APP_VERSION` + `DEFAULT_CRF`, `DEFAULT_AUDIO_BITRATE`, `DEFAULT_IMAGE_QUALITY`, `MAX_HISTORY_RECORDS`, `FFMPEG_SUBPROCESS_TIMEOUT`
- `core/converter.py` — MediaConverter engine, **composes** `MediaProbe` + `CommandBuilder` + `ProgressParser`. Uses callbacks (`set_callbacks()` API) not print(). `convert()` validates `ffmpeg_path` before building command. Exposes `build_command(input, output, opts)` for preview. `_cancel_event` (threading.Event) checked inside `_process_lock` before Popen to prevent TOCTOU race. `_callback_lock` protects `set_callbacks()`.
- `core/probe.py` — MediaProbe: ffprobe-based file probing (get_info/get_duration/get_file_summary/detect_crop/extract_thumbnail/export_file_info/estimate_output_size). `get_info()` uses **`-of json` + `json.loads`** (not fragile text parsing). Built-in `_info_cache` per filepath eliminates redundant ffprobe subprocess calls.
- `core/command_builder.py` — CommandBuilder: all FFmpeg command-building logic extracted from MediaConverter (build_video_opts/build_gif_opts/build_audio_opts/build_image_opts/build_filter/build_img_to_video_cmd/build_stream_copy_cmd/get_gpu_encoder/map_gpu_preset). Stateless — reads GPU state from shared FFmpegManager.
- `core/progress_parser.py` — ProgressParser: `parse_progress(line, total_duration)` and `compute_eta(line, total_duration)`. Microsecond parsing uses `rjust(6,'0')` (not the old buggy `ljust`). `parse_time_to_seconds()` for HH:MM:SS / MM:SS / plain seconds.
- `core/queue.py` — batch queue with ThreadPoolExecutor; `_tasks_lock` protects task list mutations; results returned in **submission order** via `results_map[task.id]`; catches `TypeError` in addition to `OSError/ValueError/RuntimeError/SubprocessError`
- `core/ffmpeg.py` — FFmpegManager (path finder + GPU detection + SHA256 fingerprint); `find_ffmpeg()` caches result after first successful detection; `_verify_ffmpeg_hash()` writes SHA256 on first run, warns on mismatch; reads `FFMPEG_PATH` env var; `_find_ffprobe()` falls back to PATH search; uses compiled regex for version extraction
- `core/history.py` — HistoryManager (conversion records in program dir `history/`); **frozen-aware** (uses `sys.executable.parent` when bundled); `add_record()` accepts optional `output_file` parameter to store output path; thread-safe via `_lock`; supports `delete_record(index)` and `clear_history()`; uses **atomic writes** (`tempfile.mkstemp` + `os.replace`) to prevent corruption on crash
- `core/options.py` — ConvertOptions dataclass (fields: width, height, **fps: Optional[float]**, quality, bitrate, audio_bitrate, audio_codec, codec, preset, extra_args, output_dir, start_time, trim_duration, use_gpu, **rotate: Optional[int]**, **flip_h: bool**, **flip_v: bool**). `crop_*` fields are `Optional[int] = None`. `__post_init__` validates: quality >= 0, fps > 0, codec in `_VALID_CODECS`, preset in `_VALID_PRESETS`, **audio_codec in `_VALID_AUDIO_CODECS`**, **bitrate/audio_bitrate regex**, **start_time/trim_duration regex**, **width/height/crop_* non-negative**.
- `core/validators.py` — extra_args whitelist (`SAFE_FFMPEG_FLAGS`) + value blacklist (`_EXTRA_ARG_DENY_RE` blocks `;&|`$(){}\n\r=<>`), output_dir validation (resolves symlinks via `os.path.realpath`), `SIZE_PRESETS` (4K/2K/1080p/720p/480p), precompiled `_SIZE_RE`, `parse_size` supports height-only (`x720`), **rejects zero dimensions**
- `gui/main_window.py` — main window with sidebar + QStackedWidget layout; thin shell (~150 lines); **creates independent MediaConverter per page** (3 instances, not shared) for callback/process isolation; status bar has a `_status_label` (colored by message type) and a permanent version label `_ver_label`; `_on_replay` also calls `page.param_panel.apply_options()` to restore parameters; `closeEvent` uses `requestInterruption()` (not `quit()`) with 5000ms wait for `_detect_worker` before page cleanup, also cleans up `self._converters`
- `gui/pages/convert_page.py` — self-contained conversion page widget; instantiated 3× (video/image/audio), each with its own FileDropWidget, FormatSelector, ParamPanel, converters buttons, ProgressPanel, and worker management; completion popup uses `QMessageBox.information()` (not `self.window().alert()`); single `QApplication` import; `_get_output_path` validates output directory via `validate_output_dir()` to prevent path traversal
- `gui/widgets/sidebar.py` — sidebar navigation widget with 4 items (▶ ◆ ♪ ☰); fixed 180px, gradient active indicator
- `gui/widgets/param_panel.py` — three collapsible sub-panels (video/image/audio), switched by `set_media_type()`. Output directory is handled by `convert_page.py`, NOT inside param_panel. Has `apply_options(dict)` method for restoring historical parameters:
  - **Video**: resolution, fps, quality/CRF, bitrate, codec, preset, GPU, trim, compress, **rotate/flip buttons** (90°/270°/hflip/vflip), audio codec+bitrate
  - **Image**: quality (1-100 unified scale), resize (width/height)
  - **Audio**: audio codec, audio bitrate
- `gui/widgets/progress_panel.py` — progress bar + log panel; `append_progress` shows ffmpeg real-time lines, `set_progress_pct` receives parsed percentage; uses `QPropertyAnimation` for smooth bar transitions (old anim is `deleteLater`'d before creating new one to prevent leak); `_animate_progress` guards `state()`/`stop()`/`deleteLater()` with `try/except RuntimeError` to survive C++ object deletion races; uses `QTextEdit.appendHtml()` for colored log output via `gui.theme.format_log_html()`
- `gui/widgets/format_selector.py` — format selection with optional `media_type` filter; chip-style buttons; `select_format(fmt)` for programmatic selection
- `gui/widgets/file_drop.py` — drag & drop file selector with media info display; `btn_file` ("+ 选择文件") is connected to `_select_file()` for browse dialog; has "信息" and "清除" buttons that appear after file selection; `clear()` emits `file_selected('')` to notify pages; `info_requested(str)` emitted for info dialog; `set_file_info()` displays codec, resolution, **FPS**, duration, and size; changes border color on dragEnter for visual feedback
- `gui/widgets/history_table.py` — conversion history table (4 columns: time, file, format, action); action column contains replay, **open-dir**, and delete buttons in a horizontal layout; "清空历史" button with confirmation dialog; column widths: 时间=ResizeToContents, 文件=Stretch, 格式=Fixed 56px, 操作=Fixed 220px
- `gui/dialogs/batch_dialog.py` — standalone batch conversion dialog (uses shared `BatchWorker`); has its own `QTextEdit` log panel with colored log levels (via `gui.theme.format_log_html()`); per-row format QComboBox; filename template with quick-insert variable buttons; uses `core.constants` for format-to-media-type mapping; `_append_log` uses `appendHtml()` for HTML-colored output; `closeEvent` cancels worker on dialog close; `_cancel_batch` calls `wait(3000)` before nullifying worker
- `gui/dialogs/concat_dialog.py` — video concatenation dialog with draggable file list, stream copy toggle, per-item file picker, and integrated ProgressPanel for real-time progress; uses shared `MediaConverter` from parent (not creating new one — prevents constructor arg type crash); has `_on_concat_done` callback and `closeEvent` override to cancel worker on dialog close
- `gui/dialogs/info_dialog.py` — media info dialog using QFormLayout; shows codec, resolution, fps, duration, bitrate, file size + thumbnail preview; supports exporting info as TXT/JSON; `ThumbnailWorker` cleans up temp file on extraction failure to prevent file leak
- `gui/workers/` — QThread wrappers that bridge core callbacks to Qt signals
  - `ConvertWorker` — single file conversion; emits `progress`, `progress_pct`, `eta`, `log`, `finished`
  - `BatchWorker` — batch conversion (shared by main window and batch dialog); emits `task_done`, `all_done`, `log`, `progress`, `progress_pct`, `eta`; `cancel()` calls `_queue.cancel()` which invokes `converter.cleanup()`
  - `DetectWorker` — GPU detection on startup; emits `detected(gpu_type, gpu_name)`; checks `isInterruptionRequested()` for clean shutdown
  - `CropWorker` — async crop detection; emits `crop_ready(dict)`; used by ConvertPage to avoid blocking main thread
  - `InfoWorker` — async file info loading (replaces sync `get_file_summary` in main thread); emits `info_ready(dict)`
  - `ConcatWorker` — video concatenation worker (moved from concat_dialog); emits `log`, `progress`, `progress_pct`, `eta`, `finished`
  - `ThumbnailWorker` — thumbnail extraction worker (moved from info_dialog); emits `thumb_ready(str)`
- `gui/styles/dark.qss` — legacy Catppuccin theme (unused; superseded by material.qss + ThemeManager)
- `gui/styles/material.qss` — **MD3 dual-theme template** (400+ lines). All colors are `{token_name}` placeholders rendered by `ThemeManager.render_qss()`. Covers: QMainWindow, QPushButton (base/checkable/convertBtn/formatChip/presetBtn), QLineEdit/SpinBox, QComboBox, QGroupBox, QCheckBox, QSlider, QProgressBar, QPlainTextEdit/TextEdit, QTableWidget, QListWidget, QStatusBar, QDialog, QMessageBox, sidebar (#sidebarBtn), labels (#dropLabel/#sectionLabel/#fileInfo), section toggle (#sectionToggle).
- `gui/theme.py` — **ThemeManager** (singleton, set by main.py). Dual-theme token system: `LIGHT_TOKENS` + `DARK_TOKENS` + derived rgba tokens. API: `load_theme(name)`, `toggle()`, `color(key)`, `log_colors`. Persists user preference to `history/.theme_pref`. Also contains legacy `LOG_COLORS`/`format_log_html()` for backward compat, and `format_log_html_md3()` for new code.
- `ico/Miku.ico` — app icon, referenced by main.py
- `icon.ico` — app icon copy at project root; used by build.py to avoid Chinese path issues with PyInstaller

## Key gotchas

- `pip install` sometimes installs to a different venv at `D:\MediaConverter\.venv` instead of the project's `.venv`. If import fails after install, use `pip install --target .venv\Lib\site-packages`.
- PyQt6 is ~80MB. The venv at `.venv` is not committed (`.gitignore`).
- `build.py` reads FFmpeg path from env var `FFMPEG_PATH`. Set it before building, or place ffmpeg.exe/ffprobe.exe + DLLs in `ffmpeg/` dir. `--add-data=core;core` is **not** needed — PyInstaller auto-collects imported modules. Icon arg uses `['--icon', str(icon_path)]` list form for space-safe paths. PyInstaller raises `SystemExit(0)` on success with `--noconfirm`; `build.py` catches both `RuntimeError` and `SystemExit`.
- `core/converter.py` needs `subprocess.CREATE_NO_WINDOW` flag — Windows only, no Linux/macOS support.
- `core/converter.py` `convert()` validates `self.ffmpeg_path` is not `None` before building command to prevent `TypeError`. Also exposes `build_command(input, output, opts)` for command preview (UI "预览命令" button).
- `core/converter.py` `_run_ffmpeg()` wraps `subprocess.Popen` in `_process_lock` to prevent race with `cleanup()`. The process is added to `_active_processes` atomically after Popen under the same lock. **`_cancel_event` is checked inside the same lock before Popen** to prevent TOCTOU race where a new process escapes cancellation.
- `core/converter.py` `_run_ffmpeg()` `finally` block terminates orphaned subprocesses (if still running after exception) before discarding from `_active_processes`. Also has **timeout protection**: `process.wait(timeout=int(duration*10+120))` (no hard 300s cap — long videos must not be killed); stderr error lines (matched by `_FFMPEG_ERROR_RE`) are forwarded to `_on_log('error', ...)` and the last 3 are repeated on failure; `getsize` failure only warns on success path; image inputs with unknown duration get a 5s estimate for progress.
- `core/converter.py` `cleanup()` sets `_cancel_event`, then calls `proc.wait(timeout=2)` after `proc.kill()` to reap zombie processes.
- `core/converter.py` `set_callbacks()` is protected by `_callback_lock` to prevent mixed old/new callback states during concurrent conversions.
- `core/converter.py` `_build_stream_copy_cmd(opts)` handles `remove_audio` and generic `-c:v copy -c:a copy`; the `replace_audio_file` branch was dead code (handled in `convert()` before reaching stream_copy) and has been removed. `output_ext` parameter was unused and has been removed.
- `core/converter.py` `_build_img_to_video_cmd()` respects `preset` when GPU is enabled (maps via `_map_gpu_preset()`).
- `core/converter.py` `_parse_ffmpeg_progress()` and ETA calculation divide the fractional seconds part by 1000000 (FFmpeg outputs 6-digit microseconds, not centiseconds). ETA uses `divmod(remaining, 3600)` for hours (not 60).
- `core/converter.py` `get_audio_duration()` renamed to `get_duration()` — it uses ffprobe's `format.duration` which works for any media type.
- `core/converter.py` `get_default_opts()` has an `audio` branch now (returns sensible defaults for mp3/wav/aac/flac/ogg/m4a/wma).
- `core/converter.py` `codec_map` uses `'libx264'` for `.m2ts` (not `'h264'`, which is not a valid FFmpeg encoder name).
- `core/converter.py` `concat_videos()` escapes backslashes in file list (`f.replace("\\", "\\\\").replace("'", "'\\''").replace("\n", "_").replace("\r", "_")`) to prevent FFmpeg concat demuxer escape injection.
- `core/queue.py` uses `_tasks_lock` to protect `self.tasks` mutations (`add_task`/`reset`/`process`). `_do_convert` catches `TypeError` in addition to `OSError/ValueError/RuntimeError/SubprocessError`.
- Worker lifecycle: **always** set `self._worker = None` in `_on_convert_done`, `_on_cancel`, and `cleanup`. Never rely solely on `deleteLater` — it defers C++ deletion, leaving a dangling Python reference. When disconnecting old worker signals, catch both `TypeError` and `RuntimeError` to handle already-deleted C++ objects. **Use `requestInterruption()` + `wait(10000)` instead of `terminate()`** — `QThread.terminate()` can permanently hold locks and leak subprocesses. ConvertPage has `_stop_worker(worker, wait_ms)` helper: on wait timeout it parks the worker in `_pending_workers` and connects `finished → deleteLater` (never delete a running QThread); it returns the still-running worker so callers can abort their flow.
- Tests in `tests/` test `core/` modules (options, validators, ffmpeg, converter, history, queue, probe, command_builder, progress_parser), `gui/workers/` (convert_worker, crop_worker, detect_worker, batch_worker), plus `test_imports.py` smoke test and `test_param_panel.py` GUI widget test — 263 tests, 14 files.
- `tests/test_imports.py` verifies ALL modules (core + gui, including all 7 workers and gui.theme) can be imported without error. Any structural change that breaks imports will fail this test immediately.
- Tests in `backup/test_converter.py` test the legacy CLI module `backup/converter.py` — 19 tests. Both test suites should pass.
- `backup/cli-v2/` was removed (isolated dead code). `backup/__init__.py` exists — required for `python -m unittest backup.test_converter` discovery.
- `MediaConverter.spec` was deleted — build.py builds PyInstaller args inline and does NOT use a spec.
- `build.py` uses `['--icon', str(icon_path)]` (list form) for space-safe icon paths; `SystemExit` from PyInstaller is caught alongside `RuntimeError`. `FFMPEG_SKIP_CONFIRM=true` bypasses the interactive prompt for CI builds.
- Cancellation is **one-way** in `MediaConverter`: `cleanup()`/`cancel()` sets `_cancel_event` and increments `_cancel_gen`; `convert()`/`_run_ffmpeg()` refuse to start new processes once cancelled (checked under `_process_lock`), so a `convert()` call must snapshot `gen` at entry and pass it to `_run_ffmpeg()`. `reset_cancellation()` (also increments gen + clears event) authorizes new tasks — called by `ConvertWorker`/`BatchWorker`/`ConcatWorker` at `run()` start. `queue.process()` no longer clears its cancel event (each BatchWorker builds a fresh queue).
- `core/ffmpeg.py` `detect_gpu()` checks for **all** GPU encoders: `h264_*`, `hevc_*`, `av1_*` per vendor (nvidia/amd/intel), then **verifies with a 1-frame lavfi encode** (`_verify_gpu_encoder`) so machines without the actual GPU fall back to CPU. `_find_ffprobe()` validates ffprobe with `-version` before accepting it, and falls back to PATH search if not co-located. `find_ffmpeg()` reads `FFMPEG_PATH` env var. `get_version()` uses compiled regex `_VERSION_RE` for reliable extraction. `_verify_ffmpeg_hash()` uses a `mtime_ns-size` fast fingerprint to skip full SHA256 on unchanged binaries.
- `core/validators.py` `validate_output_dir()` normalizes `/` to `\` on Windows before checking `..` traversal, resolves symlinks via `os.path.realpath`. `parse_size()` supports height-only (`x720`) and width-only modes, rejects zero dimensions. `SIZE_PRESETS` includes 4K(3840x2160), 2K(2560x1440), 1080p, 720p, 480p. `SAFE_FFMPEG_FLAGS` (value-taking flags) and `SAFE_FFMPEG_BOOL_FLAGS` (`-an`/`-sn`/`-dn`) are separate whitelists — bool flags must not consume a value arg.
- `core/history.py` deduplicates by **file + format** (not just file), so converting the same file to different formats keeps separate records. History stored in program directory `history/history.json`. Writes are **atomic** (temp file + `os.replace`). `load_history()` catches `AttributeError` in addition to `JSONDecodeError`/`OSError`/`KeyError` to handle corrupted JSON arrays.
- `core/options.py` `fps` is `Optional[float]` (supports `29.97`); `crop_w/h/x/y` are `Optional[int]` defaulting to `None`.
- `gui/widgets/param_panel.py` quality/preset buttons now **toggle off** on re-click (consistent with resolution/FPS/bitrate groups). All buttons are set to `setChecked(False)` on uncheck (not `setChecked(btn is clicked)` which kept the clicked button re-checked). FPS input supports float values (e.g. `29.97`). `CollapsibleSection` uses `_current_anim` to prevent animation re-entry races.
- `gui/widgets/file_drop.py` `dragEnterEvent` filters by `ALL_MEDIA_EXTS` before accepting. `btn_file` is connected to `_select_file()` for browse dialog.
- `gui/widgets/progress_panel.py` `append_progress` replaces last block text in-place instead of removing+appending, avoiding blank line accumulation. `set_progress` and `set_progress_pct` share the same `_animate_progress` implementation. Old `QPropertyAnimation` objects are `deleteLater`'d before creating new ones to prevent memory leak. `state()`/`stop()`/`deleteLater()` are wrapped in `try/except RuntimeError` to handle edge case where C++ object was already deleted. `clear()` stops animation before resetting. `set_converting(True)` resets progress to 0.
- `gui/workers/convert_worker.py` and `detect_worker.py` wrap `run()` in try/except to ensure `finished`/`detected` signals are always emitted. `detect_worker.py` checks `isInterruptionRequested()` after `init()` for responsive shutdown.
- `gui/widgets/param_panel.py` `CollapsibleSection` uses `QPropertyAnimation` on `maximumHeight` for expand/collapse (not `QScrollArea` height — that would misbehave).
- `gui/widgets/progress_panel.py` uses `QTextEdit` with `insertHtml()` + `insertBlock()` for colored log output — `QPlainTextEdit` does not support HTML, and `appendHtml()` was removed in PyQt6 6.7+.
- `gui/dialogs/batch_dialog.py` uses `QTextEdit.insertHtml()` + `insertBlock()` for colored log output (not plain `append()`, and not the removed `appendHtml()`); `_cancel_batch` calls `wait(3000)` before nullifying worker to prevent dangling thread. Progress bar shows overall percentage (done/total) instead of conflicting per-file percentage.
- `gui/widgets/file_drop.py` uses `dragEnterEvent`/`dragLeaveEvent` to dynamically change `drop_label` border color and text for visual feedback. `os.path.getsize()` is wrapped in `try/except OSError` to prevent crash on missing file.
- `core/converter.py` `concat_videos()` computes total duration by summing `get_file_summary` durations, then passes it as `opts.trim_duration` for accurate ETA tracking. Escapes backslashes in file paths (`f.replace("\\", "\\\\")`) to prevent FFmpeg concat demuxer escape injection.
- `gui/widgets/progress_panel.py` has an `eta` QLabel (`label_eta`) that displays ETA in green text.
- `gui/dialogs/concat_dialog.py` runs its own `ConcatWorker` (separate from `ConvertWorker`) to avoid conflicts with active conversion; uses shared `MediaConverter` from parent page (not creating new one — constructor arg type crash fixed); `_cancel_concat` nullifies `self._worker` to prevent dangling reference; has `closeEvent` override to cancel worker on dialog close.
- `gui/styles/dark.qss` styles both `QPlainTextEdit` and `QTextEdit` with a shared selector to ensure log panels have themed backgrounds.

## Conventions

- **Hard constraints on side effects**:
  - **Never modify the system-wide environment**: do not set/delete environment variables, modify PATH, touch the registry, or install/uninstall global packages. `pip` is only allowed with `--target .venv\Lib\site-packages` to write into the project venv (see Key gotchas below).
  - **Never modify files outside the project directory** (`MediaConverter/`): do not write, delete, or create any file outside it (including `%LOCALAPPDATA%`, `%TEMP%`, `C:\`, etc.).
  - **All files produced by the project must stay inside the project directory**: logs, history, caches, and temp files must land inside the project; tests must create their own temp dirs with `tempfile.TemporaryDirectory()` and clean up in `tearDown`. Note: importing `backup/converter.py` creates a log dir at `%LOCALAPPDATA%\FFmpegConverter` (legacy side effect — do not rely on it, do not extend it beyond its scope).
- Chinese UI text throughout (buttons, labels, messages). Keep it Chinese.
- All error handling must use specific exceptions (`OSError`, `ValueError`, `SubprocessError`), never bare `except:`.
- FFmpeg extra args are whitelisted in `core/validators.py` `SAFE_FFMPEG_FLAGS`. Add new flags there, not inline.
- Output files use `_converted`, `_compressed` suffixes before the extension (batch also uses `_converted` — `_batch` suffix is not used in current code).
- Use `from core.constants import APP_VERSION, VIDEO_EXTS, IMAGE_EXTS, AUDIO_EXTS, ALL_MEDIA_EXTS` instead of defining constants inline.
- Codec selector in `param_panel.py` stores codec name in `combo_codec.itemData()`; GPU codecs (`h264_nvenc`/`h264_amf`/`h264_qsv`) are dynamically added/removed in `set_gpu_available()`.
- Version is defined once in `core/constants.py:5` (`APP_VERSION`). Reference it everywhere else.
- Never assign `converter._on_progress` / `converter._on_log` directly. Use `converter.set_callbacks(on_log=..., on_progress=..., on_progress_pct=...)` instead.

## Batch conversion concurrency model

- `ConversionQueue.process()` ensures `converter.init()` has been called (callbacks are set by the caller, typically `BatchWorker.run()`). Qt signals are thread-safe for cross-thread emission.
- Worker threads in the pool call `converter.convert()` directly without overwriting callbacks.
- `MediaConverter` tracks all active subprocesses in `_active_processes` (thread-safe set). `cleanup()` terminates all of them.
- Cancellation uses `threading.Event` for reliable signaling across threads.
- Results are returned in **submission order**: collected via `results_map[task.id]` dict, then mapped back by task index.
- History writes are protected by `threading.Lock` to prevent concurrent `load→modify→save` races.

## MainWindow / ConvertPage thread safety

- **Each `ConvertPage` has its own independent `MediaConverter` instance** — callbacks and `_active_processes` are fully isolated between pages. Converting a video does not block image or audio pages.
- Each `ConvertPage` manages its own `_worker`, `_batch_worker`, and `_crop_worker` independently.
- When starting a new conversion while an old one is running: disconnect old `finished` signal, call `converter.cleanup()` to kill ffmpeg, `requestInterruption()`, `wait(10000)`, then set `self._worker = None`.
- After worker completes/cancels, ALWAYS set `self._worker = None` to prevent dangling C++ object crash (`RuntimeError: wrapped C/C++ object has been deleted`).
- `finished` signal is connected to `self._worker.deleteLater` for automatic cleanup, but this is deferred — relying on `self._worker = None` for immediate safety.
- Each page's `cleanup()` calls `converter.cleanup()` to terminate ffmpeg, `requestInterruption()`, `wait(10000)`, then nullifies `_worker`, `_crop_worker`, and `_batch_worker`.
- `_open_batch()` and `_open_concat()` check `is_converting()` before opening dialog to prevent overlapping conversions.
- Batch dialog disables `btn_add`/`btn_remove`/`btn_clear` during processing and checks `_is_running` flag.
- Dialog `closeEvent` handlers now disconnect all signals (`log`/`progress`/`progress_pct`/`eta`/`finished`) before canceling workers to prevent signal delivery to deleted objects.

## Converter methods reference

Core converter methods and their purposes:

| Method | Purpose |
|--------|---------|
| `convert()` | Main entry: validates `ffmpeg_path` first, then routes video/video, video/image, video/audio, image/image, image/video, audio/audio; adds `-y` and stream-copy flag unconditionally; supports `remove_audio` and `replace_audio_file` |
| `build_command()` | Public API to build FFmpeg command list without executing (used by UI "预览命令" button); returns `List[str]` or `None` on validation failure |
| `set_callbacks()` | Public API to set `_on_log`, `_on_progress`, `_on_progress_pct`, `_on_eta`; protected by `_callback_lock` |
| `get_file_summary()` | Returns file info dict (codec, format_name, width, height, **fps**, duration, size_mb, bitrate) parsed from ffprobe |
| `get_duration()` | Returns container duration via ffprobe `format.duration` (works for all media types; renamed from `get_audio_duration()`) |
| `estimate_output_size()` | Estimates output file size based on bitrate/quality |
| `detect_crop()` | Auto-detects crop area via ffmpeg cropdetect filter; returns `{'w','h','x','y'}` or None |
| `extract_thumbnail()` | Extracts a single frame as JPG at given time_sec |
| `export_file_info()` | Exports file info to TXT or JSON file |
| `concat_videos()` | Concatenates 2+ video files using `-f concat` demuxer; supports stream copy; escapes newlines in filenames |
| `_build_stream_copy_cmd()` | Builds stream-copy command (video+audio passthrough, only container change); takes only `opts` (unused `output_ext` param removed); `replace_audio_file` branch removed (dead code — handled in `convert()` before reaching stream_copy) |
| `_build_video_opts()` | Builds video encoding args (codec, quality, bitrate, preset, audio) |
| `_build_gif_opts()` | Builds GIF-specific filter chain (scale + fps + palettegen + paletteuse) |
| `_build_audio_opts()` | Builds audio encoding args per format (WebM→libopus, WMV→wmav2, MP3→libmp3lame, etc.); respects `opts.audio_codec` |
| `_build_image_opts()` | Builds image encoding args (JPG/PNG/WEBP quality, resize filter); quality is **1-100 unified scale** (higher=better) |
| `_build_filter()` | Builds scale/fps/crop/rotate/flip filter for non-GIF video |
| `_build_img_to_video_cmd()` | Builds image→video ffmpeg command; accepts `prefix` for shared flags (`-hwaccel`, `-ss`); respects `preset` when GPU is enabled |
| `_map_gpu_preset()` | Maps x264 preset names to GPU-native values (NVIDIA→p1-p7, AMD→speed/balanced/quality, Intel→veryfast/medium/slow) |
| `_parse_ffmpeg_progress()` | Parses `time=HH:MM:SS.µs` from ffmpeg stderr to compute progress percentage (divides microsecond part by 1000000, not 100); delegates to `ProgressParser.parse_progress()` |
| `_parse_time_to_seconds()` | Converts time string (`"00:01:30"` or `"90"`) to float seconds; delegates to `ProgressParser` |
| `_run_ffmpeg()` | Executes ffmpeg subprocess, tracks in `_active_processes`, uses trimmed duration for progress when `opts.trim_duration` is set; emits `_on_eta` with `ETA H:MM:SS`; has **timeout protection**; calls `compute_eta()` on ProgressParser |
| `cleanup()` | Terminates all active ffmpeg subprocesses; sets `_cancel_event` before killing processes |
| `cleanup()` | Terminates all active ffmpeg subprocesses |
