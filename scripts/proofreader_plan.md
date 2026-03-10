# Plan: Implement scripts/proofreader AI Proofreading System

## Context

The project is a Chinese translation of Google Style Guides. The Java guide is complete (~38KB).
All proofreader files were previously deleted. This re-implementation must follow the design spec
in `scripts/proofreader_design.md` with these key constraints (from user feedback):

1. **No model-initiated tool calls** — the full pipeline is hardcoded in Python:
   read sections → call Claude → parse output → write corrections → store memory notes → repeat
2. **Fix streaming** — previous version had display issues (terminal not updating, debug files
   missing model output). New approach: Rich console for status/headers, direct stdout writes
   for streaming model text (no mixing Rich Live with raw print)
3. **Save full model output** — debug files must contain complete model responses (thinking + text)

---

## Module Structure

```
scripts/proofreader/
├── __init__.py
├── config.py       # API key management
├── reader.py       # HTML/MD section reader + in-place section writer
├── state.py        # Session state dataclasses + JSON persistence
├── chunker.py      # Heuristic section grouping (no Claude needed)
├── reviewer.py     # Core: call Claude for one chunk, parse structured output
├── display.py      # Rich console for status; raw stdout for streaming text
├── logger.py       # Debug logging (full request + response saved per chunk)
├── main.py         # CLI: main.py <language> [--dry-run] [--resume]
├── requirements.txt
├── README.md
└── tests/
    ├── __init__.py
    ├── test_reader.py
    ├── test_state.py
    └── test_reviewer.py   # Test output parsing logic (no API calls)
```

---

## Module Details

### `config.py`
- `get_api_key() -> str`: env `ANTHROPIC_API_KEY` → `~/.config/proofreader/api_key` → prompt+save
- `MODEL = "claude-sonnet-4-6"`

### `reader.py` (self-contained, no parent-script imports)
Copy parsing logic from `scripts/get_original_section.py` (HTML+MD) and
`scripts/get_translated_section.py`. The GUIDES dict maps language names to source files.
Additional functions beyond the existing helpers:
- `list_all_sections(guide) -> list[SectionInfo]`: returns all section numbers, titles, levels,
  estimated token counts (len(content)//4), and whether a translation exists
- `read_original_section(guide, section_num) -> str | None`
- `read_translated_section(guide, section_num) -> str | None`
- `apply_correction(guide, section_num, corrected_content: str) -> bool`:
  In-place replacement in `docs/guides/{guide}.md` — find the section's line boundaries
  (same logic as `extract_section` but record start/end lines), replace those lines with
  the corrected content, rewrite the entire file.

### `state.py`
Dataclasses (with `dataclasses.asdict` for JSON serialization):
```
SectionInfo: section_num, title, level, token_estimate, has_translation
Chunk: chunk_id, sections[], reason, status (pending/processing/done/skipped), notes, issues_count
AgentState: guide, session_id, chunks[], glossary{term_en: {term_zh, note}},
            issues[], human_review_items[], dry_run, started_at
```
- `AgentState.save(debug_dir: Path)` → `state.json`
- `AgentState.load(debug_dir: Path)` → classmethod
- `AgentState.from_glossary_file(glossary_path: Path, ...)` → seeds glossary from `translation/GLOSSARY.md`
- `AgentState.save_glossary(glossary_path: Path)` → write updated glossary back to `translation/GLOSSARY.md`

### `chunker.py`
`plan_chunks(sections, guide, client, logger) -> list[Chunk]`:
1. Build a markdown table of all sections: section_num, title, level, estimated tokens, has_translation
2. Call Claude (non-streaming, no thinking, `max_tokens=2048`) with the table and a prompt asking
   it to group sections into processing chunks (1000–4000 tokens each; related subsections together)
3. Claude responds with a JSON array: `[{"chunk_id":"chunk_01","sections":["1","1.1","1.2"],"reason":"..."}]`
4. Parse JSON, return list of Chunk objects
- Log request+response to `debug_dir/planning_request.json` and `planning_response.json`

### `reviewer.py`
Core module. `review_chunk(chunk, state, client, display, logger, dry_run) -> ChunkResult`:

**API call:**
```python
response = client.messages.create(
    model=MODEL,
    max_tokens=16000,
    thinking={"type": "enabled", "budget_tokens": 8000},
    system=[
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": glossary_section, "cache_control": {"type": "ephemeral"}},
    ],
    messages=[{"role": "user", "content": build_user_message(chunk, state)}],
    stream=True,
    betas=["interleaved-thinking-2025-05-14"],
)
```

**User message format:** previous chunk's notes + for each section: original + translation side by side

**Expected model output** — Claude is instructed to respond in this structure:
```
<issues>
- [section X.X] severity: description
...
</issues>

<correction section="X.X">
... full corrected markdown for this section ...
</correction>

<correction section="X.Y">
...
</correction>

<notes>
Memory notes for the next chunk: terms used, patterns seen, pending issues...
</notes>
```

**Parsing:** `parse_output(full_text: str) -> ParsedOutput`:
- `re.findall(r'<correction section="([^"]+)">(.*?)</correction>', text, re.DOTALL)`
- `re.search(r'<notes>(.*?)</notes>', text, re.DOTALL)`
- `re.search(r'<issues>(.*?)</issues>', text, re.DOTALL)`

**`ChunkResult`**: `corrections: dict[str, str]`, `notes: str`, `issues_text: str`, `full_response: str`

### `display.py`
**Key design: no mixing Rich Live with streaming text**

Use `rich.console.Console` for structured output (headers, progress, panels).
Use `sys.stdout.write` + `sys.stdout.flush()` for streaming model text.

```python
class Display:
    def __init__(self):
        self.console = Console()

    def show_header(self, guide, session_id, mode): ...     # Rich panel
    def show_chunk_start(self, chunk): ...                   # Rich rule + text
    def stream_thinking(self, text: str): ...                # sys.stdout dim write
    def stream_text(self, text: str): ...                    # sys.stdout.write + flush
    def show_chunk_done(self, chunk, corrections_count): ... # Rich green text
    def show_progress(self, done, total): ...                # Rich progress bar (printed, not live)
    def show_final_summary(self, state): ...                 # Rich table
```

Streaming loop in `reviewer.py`:
```python
full_response = ""
thinking_buffer = ""
text_buffer = ""

with client.messages.stream(...) as stream:
    for event in stream:
        if hasattr(event, 'type'):
            if event.type == 'content_block_start':
                if event.content_block.type == 'thinking':
                    display.console.print("\n[dim]💭 Thinking...[/dim]", end="")
            elif event.type == 'content_block_delta':
                delta = event.delta
                if delta.type == 'thinking_delta':
                    thinking_buffer += delta.thinking
                    # No live display of thinking content (too verbose)
                elif delta.type == 'text_delta':
                    text_buffer += delta.text
                    full_response += delta.text
                    display.stream_text(delta.text)
```

### `logger.py`
`DebugLogger(session_id, guide, debug_root="debug")`:
- Creates `debug/proofreader_{session_id}/`
- `write_run_info(...)` → `run_info.json`
- `write_chunk_request(chunk_id, request_dict)` → `chunk_{id}/request.json`
- `write_chunk_response(chunk_id, full_text, thinking_text)` → `chunk_{id}/response.txt` + `chunk_{id}/thinking.txt`
- `write_chunk_result(chunk_id, corrections, issues, notes)` → `chunk_{id}/result.json`
- `write_state(state)` → updated `state.json` (called after each chunk)
- `write_report(state)` → `report.md` (final summary: chunks, issues, glossary changes)

### `main.py`
```
usage: main.py <language> [--dry-run] [--resume]
```
**Orchestration:**
1. Parse args, validate language
2. `config.get_api_key()` → create `anthropic.Anthropic(api_key=...)`
3. If `--resume`: find latest `debug/proofreader_*_{language}/` dir, load state
4. Else: new session_id, load glossary, call `chunker.plan_chunks()`, build `AgentState`
5. Init `DebugLogger` and `Display`, write run_info
6. Show header
7. Main loop: for each pending chunk:
   a. `display.show_chunk_start(chunk)`
   b. `reviewer.review_chunk(...)` — streams output inline
   c. If not dry_run: apply corrections via `reader.apply_correction()`
   d. Update chunk status + notes, `state.save()`
   e. `logger.write_state(state)`
   f. `display.show_chunk_done(...)`
8. `state.save_glossary(translation/GLOSSARY.md)` if new terms added
9. `logger.write_report(state)`
10. `display.show_final_summary(state)`
11. Handle `KeyboardInterrupt`: save state + print resume command

---

## System Prompt Design
The system prompt instructs Claude to:
- Output corrections wrapped in `<correction section="X.X">...</correction>` tags
- Output a `<notes>` block at the end as memory for next chunk
- Output an `<issues>` block listing problems found
- Not use tool calls
- Maintain NOTES.md translation principles (loaded from `translation/NOTES.md`)

The system prompt (+ glossary block) gets prompt caching via `cache_control: ephemeral`.

---

## Critical Files

- Source: `scripts/get_original_section.py:14-196` (HTML/MD parsing to copy into reader.py)
- Source: `scripts/get_translated_section.py:33-79` (translation extraction to copy)
- Reference: `translation/GLOSSARY.md` (seed glossary at startup)
- Reference: `translation/NOTES.md` (include in system prompt)
- Primary test: `styleguide/javaguide.html` + `docs/guides/java.md`
- Prior debug logs: `debug/proofreader_20260301_230301_java/` (reference for output format)

---

## Verification

1. Import check: `.venv/bin/python -c "import anthropic, rich; print('OK')"`
2. Unit tests: `.venv/bin/python -m pytest scripts/proofreader/tests/ -v`
3. Dry-run: `.venv/bin/python scripts/proofreader/main.py java --dry-run`
   - Creates debug session dir with request.json, response.txt per chunk
   - Streams model output in terminal (visible as it arrives)
   - Writes report.md at end, does NOT modify docs/guides/java.md
4. Full run: `.venv/bin/python scripts/proofreader/main.py java`
   - Applies corrections to docs/guides/java.md
   - Updates translation/GLOSSARY.md
5. Resume: interrupt with Ctrl-C then re-run with `--resume`
