# AGENTS.md

## Run / Test / Build

```bash
# All commands use the venv python directly (no activate needed)
.venv\Scripts\python.exe main.py              # Run GUI
.venv\Scripts\python.exe -m unittest discover tests -v  # Run core tests (105 tests across 7 files)
.venv\Scripts\python.exe -m unittest backup.test_converter -v  # Run legacy CLI tests (19 tests)
.venv\Scripts\python.exe build.py             # Package to exe (needs FFmpeg binaries in ffmpeg/ dir)
```

Install deps: `.venv\Scripts\pip.exe install -r requirements.txt`

Create venv (if missing): `python -m venv .venv`

The venv python path must be the full `.venv\Scripts\python.exe` — do not rely on `python` being on PATH.

**No lint/typecheck configured yet** — add `ruff` or `mypy` if needed.

## Architecture

Three-layer design: `core/` (pure logic, no Qt), `gui/` (PyQt6 widgets + workers), `gui/pages/` (page-level composition).

- `main.py` — GUI entrypoint, loads `gui/main_window.py` and `gui/styles/dark.qss`
- `core/constants.py` — shared file extension sets (`VIDEO_EXTS`, `IMAGE_EXTS`, `AUDIO_EXTS`, `ALL_MEDIA_EXTS`) + `APP_VERSION`
- `core/converter.py` — MediaConverter engine, uses callbacks (`set_callbacks()` API) not print()
- `core/queue.py` — batch queue with ThreadPoolExecutor; `_tasks_lock` protects task list mutations; results returned in **submission order** via `results_map[task.id]`
- `core/ffmpeg.py` — FFmpegManager (path finder + GPU detection)
- `core/history.py` — HistoryManager (conversion records in LOCALAPPDATA); thread-safe via `_lock`; supports `delete_record(index)` and `clear_history()`
- `core/options.py` — ConvertOptions dataclass (fields: width, height, fps, quality, bitrate, audio_bitrate, audio_codec, codec, preset, extra_args, output_dir, start_time, trim_duration, use_gpu)
- `core/validators.py` — extra_args whitelist (`SAFE_FFMPEG_FLAGS`), output_dir validation, `SIZE_PRESETS` constant, `parse_size`
- `gui/main_window.py` — main window with sidebar + QStackedWidget layout; thin shell (~120 lines)
- `gui/pages/convert_page.py` — self-contained conversion page widget; instantiated 3× (video/image/audio), each with its own FileDropWidget, FormatSelector, ParamPanel, converters buttons, ProgressPanel, and worker management
- `gui/widgets/sidebar.py` — sidebar navigation widget with 4 items (📹 🖼️ 🎵 📋); fixed 180px, gradient active indicator
- `gui/widgets/param_panel.py` — three collapsible sub-panels (video/image/audio), switched by `set_media_type()`. Output directory is handled by `convert_page.py`, NOT inside param_panel:
  - **Video**: resolution, fps, quality/CRF, bitrate, codec, preset, GPU, trim, compress, audio codec+bitrate
  - **Video**: resolution, fps, quality/CRF, bitrate, codec, preset, GPU, trim, compress, audio codec+bitrate
  - **Image**: quality (1-100 unified scale), resize (width/height)
  - **Audio**: audio codec, audio bitrate
- `gui/widgets/progress_panel.py` — progress bar + log panel; `append_progress` shows ffmpeg real-time lines, `set_progress_pct` receives parsed percentage
- `gui/widgets/format_selector.py` — format selection with optional `media_type` filter; chip-style buttons; `select_format(fmt)` for programmatic selection
- `gui/widgets/file_drop.py` — drag & drop file selector with media info display; has "信息" and "清除" buttons that appear after file selection; `clear()` emits `file_selected('')` to notify pages; `info_requested(str)` emitted for info dialog; `set_file_info()` displays codec, resolution, **FPS**, duration, and size
- `gui/widgets/history_table.py` — conversion history table (4 columns: time, file, format, action); action column contains both replay and delete buttons in a horizontal layout; "清空历史" button with confirmation dialog; column widths: 时间=ResizeToContents, 文件=Stretch, 格式=Fixed 56px, 操作=Fixed 180px
- `gui/dialogs/batch_dialog.py` — standalone batch conversion dialog (uses shared `BatchWorker`); has its own `QPlainTextEdit` log panel; uses `core.constants` for format-to-media-type mapping
- `gui/dialogs/concat_dialog.py` — video concatenation dialog with draggable file list, stream copy toggle, and per-item file picker
- `gui/dialogs/info_dialog.py` — media info dialog showing codec, resolution, fps, duration, bitrate, file size + thumbnail preview; supports exporting info as TXT/JSON
- `gui/workers/` — QThread wrappers that bridge core callbacks to Qt signals
  - `ConvertWorker` — single file conversion; emits `progress`, `progress_pct`, `eta`, `log`, `finished`
  - `BatchWorker` — batch conversion (shared by main window and batch dialog); emits `task_done`, `all_done`, `log`, `progress`, `progress_pct`, `eta`
  - `DetectWorker` — GPU detection on startup; emits `detected(gpu_type, gpu_name)`
- `gui/styles/dark.qss` — Catppuccin-inspired dark theme with card containers, gradient buttons, chip-style format pills
- `ico/Miku.ico` — app icon, referenced by main.py
- `icon.ico` — app icon copy at project root; used by build.py to avoid Chinese path issues with PyInstaller

## Key gotchas

- `pip install` sometimes installs to a different venv at `D:\MediaConverter\.venv` instead of the project's `.venv`. If import fails after install, use `pip install --target .venv\Lib\site-packages`.
- PyQt6 is ~80MB. The venv at `.venv` is not committed (`.gitignore`).
- `build.py` reads FFmpeg path from env var `FFMPEG_PATH`. Set it before building, or place ffmpeg.exe/ffprobe.exe + DLLs in `ffmpeg/` dir. `--add-data=core;core` is **not** needed — PyInstaller auto-collects imported modules. Icon arg uses `['--icon', str(icon_path)]` list form for space-safe paths.
- `core/converter.py` needs `subprocess.CREATE_NO_WINDOW` flag — Windows only, no Linux/macOS support.
- `core/converter.py` `_run_ffmpeg()` wraps `subprocess.Popen` in `_process_lock` to prevent race with `cleanup()`. The process is added to `_active_processes` atomically after Popen under the same lock.
- `core/converter.py` `_run_ffmpeg()` `finally` block terminates orphaned subprocesses (if still running after exception) before discarding from `_active_processes`.
- `core/converter.py` `cleanup()` calls `proc.wait(timeout=2)` after `proc.kill()` to reap zombie processes.
- `core/queue.py` uses `_tasks_lock` to protect `self.tasks` mutations (`add_task`/`reset`/`process`).
- Worker lifecycle: **always** set `self._worker = None` in `_on_convert_done`, `_on_cancel`, and `cleanup`. Never rely solely on `deleteLater` — it defers C++ deletion, leaving a dangling Python reference.
- Tests in `tests/` test `core/` modules (options, validators, ffmpeg, converter, history, queue) — 105 tests, 7 files.
- Tests in `backup/test_converter.py` test the legacy CLI module `backup/converter.py` — 19 tests. Both test suites should pass.
- `backup/cli-v2/` contains the original CLI version before GUI refactor. Do not modify it.
- `backup/__init__.py` exists — required for `python -m unittest backup.test_converter` discovery.
- `MediaConverter.spec` uses relative icon path `ico\\Miku.ico` (not absolute).
- `core/ffmpeg.py` `detect_gpu()` checks for **all** GPU encoders: `h264_*`, `hevc_*`, `av1_*` per vendor (nvidia/amd/intel). `_find_ffprobe()` now validates ffprobe with `-version` before accepting it.
- `core/validators.py` `validate_output_dir()` normalizes `/` to `\` on Windows before checking `..` traversal.
- `core/history.py` deduplicates by **file + format** (not just file), so converting the same file to different formats keeps separate records. Exports `HISTORY_DIR` constant for reuse by `main.py`.
- `gui/widgets/param_panel.py` quality/preset buttons now **toggle off** on re-click (consistent with resolution/FPS/bitrate groups). FPS input supports float values (e.g. `29.97`).
- `gui/widgets/file_drop.py` `dragEnterEvent` filters by `ALL_MEDIA_EXTS` before accepting.
- `gui/widgets/progress_panel.py` `append_progress` replaces last block text in-place instead of removing+appending, avoiding blank line accumulation.
- `gui/workers/convert_worker.py` and `detect_worker.py` wrap `run()` in try/except to ensure `finished`/`detected` signals are always emitted.
- `build.py` uses `['--icon', str(icon_path)]` (list form) for space-safe icon paths; `SystemExit` from PyInstaller is no longer caught as an error.
- `core/converter.py` `concat_videos()` computes total duration by summing `get_file_summary` durations, then passes it as `opts.trim_duration` for accurate ETA tracking.
- `gui/widgets/progress_panel.py` has an `eta` QLabel (`label_eta`) that displays ETA in green text.
- `gui/dialogs/concat_dialog.py` runs its own `ConcatWorker` (separate from `ConvertWorker`) to avoid conflicts with active conversion.

## Conventions

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

- Each `ConvertPage` manages its own `_worker` and `_batch_worker` independently. Pages are isolated — converting a video does not block image or audio pages (only one page is visible at a time via QStackedWidget).
- When starting a new conversion while an old one is running: disconnect old `finished` signal, call `converter.cleanup()` to kill ffmpeg (so worker exits quickly), `wait(5000)`, then set `self._worker = None`.
- After worker completes/cancels, ALWAYS set `self._worker = None` to prevent dangling C++ object crash (`RuntimeError: wrapped C/C++ object has been deleted`).
- `finished` signal is connected to `self._worker.deleteLater` for automatic cleanup, but this is deferred — relying on `self._worker = None` for immediate safety.
- Each page's `cleanup()` calls `converter.cleanup()` to terminate ffmpeg, `wait(5000)`, then nullifies `_worker` and `_batch_worker`.
- `_open_batch()` checks `is_converting()` before opening dialog to prevent overlapping conversions sharing the same converter.
- Batch dialog disables `btn_add`/`btn_remove`/`btn_clear` during processing and checks `_is_running` flag.

## Converter methods reference

Core converter methods and their purposes:

| Method | Purpose |
|--------|---------|
| `convert()` | Main entry: routes video/video, video/image, video/audio, image/image, image/video, audio/audio; adds `-y` and stream-copy flag unconditionally; supports `remove_audio` and `replace_audio_file` |
| `set_callbacks()` | Public API to set `_on_log`, `_on_progress`, `_on_progress_pct`, `_on_eta` |
| `get_file_summary()` | Returns file info dict (codec, format_name, width, height, **fps**, duration, size_mb, bitrate) parsed from ffprobe |
| `estimate_output_size()` | Estimates output file size based on bitrate/quality |
| `detect_crop()` | Auto-detects crop area via ffmpeg cropdetect filter; returns `{'w','h','x','y'}` or None |
| `extract_thumbnail()` | Extracts a single frame as JPG at given time_sec |
| `export_file_info()` | Exports file info to TXT or JSON file |
| `concat_videos()` | Concatenates 2+ video files using `-f concat` demuxer; supports stream copy |
| `_build_stream_copy_cmd()` | Builds stream-copy command (video+audio passthrough, only container change) |
| `_build_video_opts()` | Builds video encoding args (codec, quality, bitrate, preset, audio) |
| `_build_gif_opts()` | Builds GIF-specific filter chain (scale + fps + palettegen + paletteuse) |
| `_build_audio_opts()` | Builds audio encoding args per format (WebM→libopus, WMV→wmav2, MP3→libmp3lame, etc.); respects `opts.audio_codec` |
| `_build_image_opts()` | Builds image encoding args (JPG/PNG/WEBP quality, resize filter); quality is **1-100 unified scale** (higher=better) |
| `_build_filter()` | Builds scale/fps/crop filter for non-GIF video |
| `_build_img_to_video_cmd()` | Builds image→video ffmpeg command; accepts `prefix` for shared flags (`-hwaccel`, `-ss`) |
| `_map_gpu_preset()` | Maps x264 preset names to GPU-native values (NVIDIA→p1-p7, AMD→speed/balanced/quality, Intel→veryfast/medium/slow) |
| `_parse_ffmpeg_progress()` | Parses `time=HH:MM:SS.MS` from ffmpeg stderr to compute progress percentage |
| `_parse_time_to_seconds()` | Converts time string (`"00:01:30"` or `"90"`) to float seconds |
| `_run_ffmpeg()` | Executes ffmpeg subprocess, tracks in `_active_processes`, uses trimmed duration for progress when `opts.trim_duration` is set; emits `_on_eta` with `ETA H:MM:SS` |
| `cleanup()` | Terminates all active ffmpeg subprocesses |
