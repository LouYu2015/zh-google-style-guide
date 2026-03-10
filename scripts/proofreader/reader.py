"""
reader.py - Self-contained HTML/Markdown section reader and writer.

Supports reading from original English styleguide files (HTML and MD)
and reading/writing translated Markdown files.

HTML originals are returned as raw HTML so Claude can interpret the markup
directly (lists, formatting, etc.) without lossy text conversion.

This module is intentionally self-contained (no imports from sibling scripts/).
"""
from __future__ import annotations

import html as _html_lib
import re
from pathlib import Path
from state import SectionInfo

# ──────────────────────────────────────────────
# Guide mappings
# ──────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.parent

ORIGINAL_GUIDES: dict[str, list[str]] = {
    "cpp":        ["styleguide/cppguide.html"],
    "python":     ["styleguide/pyguide.md"],
    "javascript": ["styleguide/jsguide.html"],
    "java":       ["styleguide/javaguide.html"],
    "typescript": ["styleguide/tsguide.html"],
    "go":         ["styleguide/go/guide.md",
                   "styleguide/go/decisions.md",
                   "styleguide/go/best-practices.md"],
    "shell":      ["styleguide/shellguide.md"],
    "html-css":   ["styleguide/htmlcssguide.html"],
}

TRANSLATION_GUIDES: dict[str, str] = {
    "cpp":        "docs/guides/cpp.md",
    "python":     "docs/guides/python.md",
    "javascript": "docs/guides/javascript.md",
    "java":       "docs/guides/java.md",
    "typescript": "docs/guides/typescript.md",
    "go":         "docs/guides/go.md",
    "shell":      "docs/guides/shell.md",
    "html-css":   "docs/guides/html-css.md",
}

# ──────────────────────────────────────────────
# HTML helpers
# ──────────────────────────────────────────────

def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _heading_level_for_section(section_num: str) -> int:
    return section_num.count(".") + 2


def _extract_from_html(content: str, section_num: str) -> tuple[str, str] | tuple[None, None]:
    """Extract a section from HTML, returning the raw HTML fragment and title.

    The raw HTML is returned as-is so Claude can read <ol>, <ul>, <code>, etc.
    directly without lossy conversion.
    """
    level = _heading_level_for_section(section_num)
    heading_re = re.compile(
        rf"<h{level}[^>]*>(.*?)</h{level}>",
        re.IGNORECASE | re.DOTALL,
    )

    target_pos: int | None = None
    target_title: str = ""
    for m in heading_re.finditer(content):
        raw = _strip_tags(m.group(1)).strip()
        heading_text = _html_lib.unescape(raw)
        if re.match(rf"^{re.escape(section_num)}(?:\s|$)", heading_text):
            target_pos = m.start()
            target_title = heading_text
            break

    if target_pos is None:
        return None, None

    fragment = content[target_pos:]
    stop_re = re.compile(rf"<h[1-{level}][^>]*>", re.IGNORECASE)
    matches = list(stop_re.finditer(fragment))
    if len(matches) >= 2:
        fragment = fragment[: matches[1].start()]

    return fragment.strip(), target_title


# ──────────────────────────────────────────────
# Markdown helpers
# ──────────────────────────────────────────────

def _strip_md_frontmatter(content: str) -> tuple[str, int]:
    """Remove YAML front matter. Returns (content_without_fm, fm_line_count)."""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            fm_end = end + 4
            if fm_end < len(content) and content[fm_end] == "\n":
                fm_end += 1
            fm_lines = content[:fm_end].count("\n")
            return content[fm_end:], fm_lines
    return content, 0


def _extract_from_md(content: str, section_num: str) -> tuple[str, str] | tuple[None, None]:
    content_body, _ = _strip_md_frontmatter(content)
    lines = content_body.splitlines(keepends=True)

    target_line: int | None = None
    target_level: int | None = None
    target_title: str = ""

    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            hashes = m.group(1)
            raw_title = m.group(2).strip()
            clean_title = re.sub(r"\s*\{#[^}]+\}", "", raw_title).strip()
            if re.match(rf"^{re.escape(section_num)}(?:\s|$)", clean_title):
                target_line = i
                target_level = len(hashes)
                target_title = clean_title
                break

    if target_line is None:
        return None, None

    result_lines: list[str] = []
    for line in lines[target_line:]:
        m = re.match(r"^(#{1,6})\s", line)
        if m and len(m.group(1)) <= target_level and result_lines:  # type: ignore[operator]
            break
        result_lines.append(line)

    return "".join(result_lines).strip(), target_title


# ──────────────────────────────────────────────
# Section listing
# ──────────────────────────────────────────────

def _list_sections_html(content: str) -> list[dict]:
    """Extract all numbered sections from HTML content with extent info."""
    heading_re = re.compile(r"<h([2-5])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)

    headings = []
    for m in heading_re.finditer(content):
        level = int(m.group(1))
        raw = _strip_tags(m.group(2)).strip()
        heading_text = _html_lib.unescape(raw)
        num_match = re.match(r"^(\d+(?:\.\d+)*)\b", heading_text)
        if num_match:
            headings.append({
                "pos": m.start(),
                "level": level,
                "section_num": num_match.group(1),
                "title": heading_text,
            })

    result = []
    for i, h in enumerate(headings):
        end_pos = len(content)
        for j in range(i + 1, len(headings)):
            if headings[j]["level"] <= h["level"]:
                end_pos = headings[j]["pos"]
                break
        token_estimate = max(len(content[h["pos"]:end_pos]) // 6, 10)
        result.append({
            "section_num": h["section_num"],
            "title": h["title"],
            "level": h["level"],
            "token_estimate": token_estimate,
        })
    return result


def _list_sections_md(content: str) -> list[dict]:
    """Extract all numbered sections from Markdown content with extent info."""
    content_body, _ = _strip_md_frontmatter(content)
    lines = content_body.splitlines(keepends=True)

    headings = []
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            hashes = m.group(1)
            raw_title = m.group(2).strip()
            clean_title = re.sub(r"\s*\{#[^}]+\}", "", raw_title).strip()
            num_match = re.match(r"^(\d+(?:\.\d+)*)\b", clean_title)
            if num_match:
                headings.append({
                    "line": i,
                    "level": len(hashes),
                    "section_num": num_match.group(1),
                    "title": clean_title,
                })

    result = []
    for i, h in enumerate(headings):
        end_line = len(lines)
        for j in range(i + 1, len(headings)):
            if headings[j]["level"] <= h["level"]:
                end_line = headings[j]["line"]
                break
        section_text = "".join(lines[h["line"]:end_line])
        token_estimate = max(len(section_text) // 4, 10)
        result.append({
            "section_num": h["section_num"],
            "title": h["title"],
            "level": h["level"],
            "token_estimate": token_estimate,
        })
    return result


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def list_all_sections(guide: str) -> list[SectionInfo]:
    """List all numbered sections from the original English guide."""
    raw_sections: list[dict] = []

    for src_path in ORIGINAL_GUIDES.get(guide, []):
        path = REPO_ROOT / src_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if src_path.endswith(".html"):
            raw_sections.extend(_list_sections_html(content))
        else:
            raw_sections.extend(_list_sections_md(content))

    # Find which sections have translations
    translation_path = REPO_ROOT / TRANSLATION_GUIDES.get(guide, "")
    translated_nums: set[str] = set()
    if translation_path.exists():
        trans_content = translation_path.read_text(encoding="utf-8", errors="ignore")
        for line in trans_content.splitlines():
            m = re.match(r"^#{1,6}\s+(\d+(?:\.\d+)*)\s", line)
            if m:
                translated_nums.add(m.group(1))

    return [
        SectionInfo(
            section_num=s["section_num"],
            title=s["title"],
            level=s["level"],
            token_estimate=s["token_estimate"],
            has_translation=s["section_num"] in translated_nums,
        )
        for s in raw_sections
    ]


def read_original_section(guide: str, section_num: str) -> str | None:
    """Read a section from the English original.

    Returns raw HTML for .html guides, raw Markdown for .md guides.
    """
    for src_path in ORIGINAL_GUIDES.get(guide, []):
        path = REPO_ROOT / src_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if src_path.endswith(".html"):
            text, _ = _extract_from_html(content, section_num)
        else:
            text, _ = _extract_from_md(content, section_num)
        if text is not None:
            return text
    return None


def read_translated_section(guide: str, section_num: str) -> str | None:
    """Read a section from the Chinese translation, returning Markdown text."""
    translation_path = REPO_ROOT / TRANSLATION_GUIDES.get(guide, "")
    if not translation_path.exists():
        return None
    content = translation_path.read_text(encoding="utf-8", errors="ignore")
    text, _ = _extract_from_md(content, section_num)
    return text


def apply_correction(guide: str, section_num: str, corrected_content: str) -> bool:
    """Replace a section in the translation file with corrected_content.

    The corrected_content should be the full section text starting with the
    heading line (e.g. '### 1.1 术语说明\n\n...').

    Returns True on success, False if section not found.
    """
    translation_path = REPO_ROOT / TRANSLATION_GUIDES.get(guide, "")
    if not translation_path.exists():
        return False

    full_content = translation_path.read_text(encoding="utf-8")
    lines = full_content.splitlines(keepends=True)

    # Find frontmatter end
    fm_end_line = 0
    if full_content.startswith("---"):
        for i, line in enumerate(lines[1:], start=1):
            if line.rstrip() == "---":
                fm_end_line = i + 1
                break

    # Find target section start
    target_line: int | None = None
    target_level: int | None = None

    for i, line in enumerate(lines[fm_end_line:], start=fm_end_line):
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            hashes = m.group(1)
            raw_title = m.group(2).strip()
            clean_title = re.sub(r"\s*\{#[^}]+\}", "", raw_title).strip()
            if re.match(rf"^{re.escape(section_num)}(?:\s|$)", clean_title):
                target_line = i
                target_level = len(hashes)
                break

    if target_line is None:
        return False

    # Find section end (next heading at same or higher level)
    end_line = len(lines)
    for i in range(target_line + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s", lines[i])
        if m and len(m.group(1)) <= target_level:  # type: ignore[operator]
            end_line = i
            break

    # Build the replacement: ensure it ends with exactly one newline
    new_section = corrected_content.rstrip("\n") + "\n"

    # Reassemble file
    new_lines = lines[:target_line] + [new_section] + lines[end_line:]
    translation_path.write_text("".join(new_lines), encoding="utf-8")
    return True
