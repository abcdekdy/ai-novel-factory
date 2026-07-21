# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

**AI Novel Factory** — a PyQt6 desktop application that orchestrates a multi-agent LLM pipeline to generate novels from a user's creative inspiration. Features **Frosted Glass / Acrylic** design with DWM blur-behind (Windows), translucent panels (`WA_TranslucentBackground` + semi-transparent white fill), Apple Blue accent (`#007AFF`), sidebar navigation, and zero emoji. Text and interactive controls stay at full opacity for readability.

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application (must NOT be already running — the web monitor binds to a fixed port,
# so starting twice will silently fail to serve HTTP; the GUI still launches)
python main.py

# Compile-check a file (practice in this repo before running the app)
python -m py_compile path/to/file.py

# Smoke-test imports without launching the whole GUI
python -c "from core.pipeline import NovelPipeline; print('OK')"

# Package as standalone exe (overwrites old version)
pyinstaller -y --clean "AI小说工厂.spec"
# Output: dist/AI小说工厂/AI小说工厂.exe

# Web monitor is auto-spawned on app start at http://localhost:5000
```

## Pipeline Flow

```
User Inspiration (LaunchWindow → MainWindow → 创作 tab → pipeline.start(…))
    → WorldBuilderAgent          (world_view.json)
    → OutlineBuilderAgent        (outline.json)
    → ChapterGeneratorAgent × N  (parallel threads + Semaphore)
    → QualityEvaluatorAgent × N  (sequential)
    → RevisionAgent × N          (loop up to max_revision_rounds if score < threshold)
    → PlatformAdapterAgent
    → Done → export .txt / .markdown
```

Resume a partial project: `pipeline.resume_from_project(project_dir)` re-enters the pipeline at chapter generation, only producing missing chapters, then runs quality eval / revision / adaptation.

**Continuation (Serial) Flow** — the third entry point (alongside `start` and `resume_from_project`):
`pipeline.continue_from_project(project_dir, guidance, batch_chapter_count, chapter_length)` loads a "legacy package" (world view + recent chapter summaries + character current states + unresolved foreshadowing + existing consistency_rules), runs `ContinuationOutlineAgent` to produce a NEW batch outline (saved as `outline_batch_N.json`), then **pauses and emits `continuation_outline_ready`** so the user can review & edit the outline in `OutlineReviewDialog` before chapters are written. After the user confirms, call `pipeline.confirm_continuation(reviewed_outline)` to start chapter generation. Continuation projects keep `status = "generating"` in summary.json (they're never auto-completed). Each batch appends a record to `summary.json → batches[]`. UI entry: `ContinuationEntryDialog` (guidance + chapter count) launched from the 项目库 card's "续写" button. Pipeline signals: `continuation_outline_ready = pyqtSignal(dict)`, `continuation_progress = pyqtSignal(str, int)`.

New source files for this feature: `core/continuation_outline_agent.py`, `gui/outline_review_dialog.py`.

**Agent names** (used as log sources, mapped to UI cards by prefix match in `AgentsTab.update_agent_log`):
`世界观构建`, `大纲生成`, `章节生成-N`, `质量评估`, `回流修订`, `多平台适配`, `Pipeline`.

**Pipeline stages** (English keys used by Flask/web status API):
`idle → world_building → outline_generation → chapter_generation → quality_evaluation → revision → adaptation → completed`.

**Overall progress allocation**: World 0–10%, Outline 10–25%, Chapters 25–60%, Quality 60–75%, Revision 75–90%, Adaptation 90–100%.

## Architecture

### Threading Model
Pipeline runs in a daemon `threading.Thread`. Each chapter uses its own thread, concurrency governed by `threading.Semaphore` (NOT QThreadPool — avoids nesting issues with LLM calls across providers). Qt signals are thread-safe and used for all GUI updates. The semaphore object lives on the pipeline instance and is rebuilt on every run / resume cycle; helper threads hold no other long-lived GUI references.

### Frosted Glass / Acrylic Design System
Implemented via **three layers of translucency** for a real glass effect:

1. **DWM blur-behind** (Windows): `assets/glass_helpers.py` calls `DwmEnableBlurBehindWindow` via ctypes to blur the desktop behind the window. Enabled in `MainWindow.apply_glass()` and `LaunchWindow.showEvent`.
2. **Window translucency**: `WA_TranslucentBackground` on the QMainWindow + central widget lets the blurred desktop show through.
3. **Paint-driven glass panels**: glass widgets set `WA_TranslucentBackground` + implement `paintEvent` that fills a rounded rect with semi-transparent white (`QColor(255,255,255, alpha)`), draws a top highlight pen, and a subtle border. Drop shadows (`QGraphicsDropShadowEffect`, alpha ≈ 0.06, offset-y only) create depth between glass layers.

**Alpha hierarchy** (controls how much blur shows through): window tint 0.65 → sidebar 0.55 → cards 0.45 → input insets 0.40 → buttons 0.55. Lower alpha = more blur visible = "frostier".

**Core widgets** (`gui/widgets/neumorphism.py`): `AppleCard` (translucent white + highlight + shadow), `AppleInset` (translucent white inset), `AppleInput` (wraps an edit widget in glass), `AppleContainer` (convenience QFrame with `inner_layout()` + glass paint). Reusable `_ScrollHost` in `gui/projects_tab.py` wraps QScrollArea in glass.

**QSS targeting**: dedicated QObject subclasses used as class selectors in `style.qss` — `Sidebar`, `SidebarButton`, `StatTile`, `AgentCard`. Do NOT use `setObjectName()` + `#name` selectors — they don't apply reliably with PyQt6's style system. The same QSS class selector applies to all instances; style individual buttons by passing a per-widget `setStyleSheet` override (not by adding more classes).

**Readability rule**: text, icons, and interactive controls ALWAYS render at full opacity (no alpha). Only the panel SURFACES are translucent. This keeps the app usable despite the transparency.

**Common QSS bugs and how to add new styled buttons**:
1. Global rule `QPushButton { padding: 11px 22px; }` will clip small buttons (28–32 px tall) unless the button gets its own inline `setStyleSheet` with a smaller `padding` (2px–14px). Only buttons whose explicit stylesheet wins the cascade will render correctly at small sizes — see `_ProjectCard._build_ui` in `gui/projects_tab.py` for the pattern used.
2. `paintEvent` raising (e.g. `addRoundedRect(QRect, …)` instead of `QRectF`) silently aborts painting for that widget AND its children — leaves an invisible/blank area with no traceback. All glass `paintEvent` implementations are wrapped in try/except for this reason.
3. Glass panels paint in this order: (a) fill rounded path with semi-transparent white (`CARD_FILL` + `CARD_ALPHA`), (b) 1px top highlight pen (`CARD_HIGHLIGHT_ALPHA`) to simulate light catching the glass edge, (c) 1px border pen (`CARD_BORDER_ALPHA`). Same pattern for insets with `INSET_*` tokens.

### LLM Provider Abstraction
`LLMClient` (`core/llm_client.py`) supports LongCat (Anthropic-compatible, Bearer <REDAUTH>) and DeepSeek (OpenAI-compatible). LongCat uses `anthropic.Anthropic(auth_token=…)`, not `api_key=`. LongCat-2.0 returns a ThinkingBlock + TextBlock — the client picks `text` from the TextBlock.

### JSON Parsing from LLM Responses
Always use the shared `BaseAgent.parse_json_response(text)` static method (`core/base_agent.py`) instead of ad-hoc parsers. It handles: (1) direct `json.loads`, (2) `json.loads(strict=False)` to allow control characters (literal newlines/tabs) in strings, (3) extraction from ` ```json … ``` ` code blocks, (4) greedy regex `.*` + progressive position scan from the last `}`. On total failure, raw response is dumped to `projects/_parse_failures/YYYYMMDD_HHMMSS.txt`. Re-run is automatic ever integration.

Common LLM JSON gotcha: LongCat often emits literal newlines inside string values (especially long Chinese text); strict mode fails — always try `strict=False`, which `parse_json_response` already does internally.

Critical: `parse_json_response` is `@staticmethod`, with no `self` in its body. Do NOT write `self._dump_failed_response(text)` inside it — that binding is module-level. Use the bare name `_dump_failed_response(text)`.

### Project Persistence
Each generation produces `projects/<sanitized_name>_<timestamp>/`:
- `world_view.json` — world/characters/story framework + `chapter_outline[]`
- `outline.json` — detailed per-chapter plot, consistency rules, character arcs, `outline_meta.total_chapters`
- `summary.json` — run metadata (`inspiration`, `title`, `chapter_count`, `status`, `started_at`, optional `completed_at`/`total_words`/`avg_quality_score`)
- `chapters/chapter_NNN.txt` (title+body) + `chapters/chapter_NNN_meta.json` (full dict incl. `chapter_index`, `title`, `content`, `word_count`, `summary`)
- `outline_batch_N.json` — per-batch continuation outlines (N = 1, 2, 3…). Each contains `outline_meta.batch`, `consistency_rules` (old rules prepended), `chapters` (only the new batch), `resolved_foreshadowing` / `new_foreshadowing`, `character_arcs` (new trajectory points appended). The original `outline.json` remains the Batch-1 source.
- `config.json` at repository root (next to `main.py`)

`summary.json` also carries `batches[]` (per-batch records: `batch_number`, `guidance`, `chapter_range`, `chapter_count`, `created_at`). `chapter_count` (older projects) and `chapters_count` (newer pipeline code) both appear in the wild — consumer code must tolerate both. Continuation projects keep `status = "generating"` (only user-triggered "完结" sets `completed`).

Functions in `project_manager.py` accept both `str` and `Path` for `project_dir` — strictly convert with `project_dir = Path(project_dir)` at the top of every function before using `/` (this was actually missing in `save_project_summary` and caused a TypeError in the 2026-07-19 continuation session).

### State Sharing
`web_monitor/server.py` uses a module-level `_pipeline_status` dict protected by `threading.Lock`. NOTE: the dict is NOT yet bridged to the pipeline's Qt signals — the web dashboard shows zero/empty until that bridge is built. The GUI Monitor tab polls `/api/status` every 3s for the same reason; both read the same dict.

## UI Design Rules (MUST FOLLOW)

- **NO emoji** anywhere in UI — labels, buttons, titles. Use color, weight, spacing. Existing `QListWidget`/`QTextEdit` placeholders and agent-card badge text ("生成中"/"已完成") are text-only; don't add emoji when touching them.
- **Chinese labels only** — all UI text must be Chinese (创作, 工作台, 预览, 项目库, 监控, 设置).
- **Frosted Glass palette** — `#F5F5F7` base tint, `#FFFFFF` translucent card fill (alpha 0.45), `#007AFF` Apple Blue accent, `#1D1D1F` text (full opacity). No warm clay anywhere; always use `BG_BASE` / `CARD_FILL`+`CARD_ALPHA` / `INSET_FILL`+`INSET_ALPHA` / `ACCENT` from `assets/design_tokens.py`.
- **Apple system font** for Latin (SF Pro / Inter / Segoe UI), fallback to PingFang SC / Microsoft YaHei for CJK. Enforced via `assets/design_tokens.py::FONT_SYSTEM` and applied implicitly in `main.py`. When adding widgets, pass a `QFont` from `FONT_SYSTEM` stack (falls back automatically).
- Do not use `setIndividual instance QSS via `setObjectName` + `#name` selectors — they don't work reliably. Use subclassed QWidgets or per-widget `setStyleSheet`.

## Configuration

`config.json` (created from `core/config.py::DEFAULT_CONFIG` if missing) keys:
`api_key, provider, model, base_url, temperature, max_tokens, concurrency, max_revision_rounds, quality_threshold, default_chapter_count, default_chapter_length, web_monitor_port, enable_outline_agent (bool), outline_max_tokens (8192), outline_temperature (0.7)`.

## Shared Developer Patterns (hard-won)

**Compile-check before running**: many PyQt6 runtime errors (signature mismatches, missing imports, wrong parent classes) only surface at instantiation. Run `python -m py_compile file.py` first, then smoke-test with a short Python one-liner that imports + constructs the widget with `.show()` and a `QTimer.singleShot` if needed — don't rely on launching the full app.

**`paintEvent` silently eats child rendering**: any exception inside `paintEvent` aborts painting for that widget AND its children — invisible/blank UI, no traceback. Wrap suspect code in try/except during development.

**Static-method vs instance-method confusion in `BaseAgent`**: `parse_json_response` and `_dump_failed_response` have both been `@staticmethod` for several generations. Adding code that references `self._…` inside either will produce `NameError: name 'self' is not defined` (as actually happened during the 2026-07-12 debugging session). When in doubt, refer to them on the class (`BaseAgent.parse_json_response(…)`) with no `self.` prefix in the body.

**Agent name routing**: `AgentsTab.update_agent_log` matches agent log messages to UI cards by prefix (`agent_name.startswith(cname)`). New autogen `章节生成-N` cards are created on the fly; fixed cards are in the `fixed` list in `AgentsTab._setup_ui`.

**Three pipeline entry points**: (1) `pipeline.start(…)` creates a NEW project dir and clears state. (2) `pipeline.resume_from_project(existing_dir)` reuses the existing dir, reloads `world_view.json`, `outline.json`, and any existing `chapters/chapter_NNN_meta.json`, then only produces chapters whose indices are missing. (3) `pipeline.continue_from_project(dir, guidance, batch_chapter_count)` starts a new SERIAL BATCH — loads a "legacy package", generates a new batch outline, and pauses for user review (does NOT auto-write chapters). `confirm_continuation(reviewed_outline)` actually starts chapter writing. The `resume_requested = pyqtSignal(str)` on `ProjectsTab` triggers `MainWindow._start_resumed_pipeline`; `continue_requested = pyqtSignal(str, str, int)` triggers `_start_continuation`, which verifies API key and shows 工作台 (tab 1).

**Layout mutation during event handlers**: Qt swallows Python exceptions raised inside `pyqtBoundSignal` callbacks — a crashed slot prints to stderr but never shows a traceback in the GUI, and execution silently stops mid-function. Always wrap slot bodies (clicked handlers, signal callbacks that do file I/O or layout changes) in `try/except` that surfaces errors via `print()` + `QMessageBox`. Prefer visibility toggles (`widget.setVisible(...)` with all widgets pre-created at init) over layout add/remove in handlers — rebuilds are fragile (parenting, stale `takeAt`-like calls) and harder to debug when they fail silently.
