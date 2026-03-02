"""
reader.py - 文档读取（自包含，不依赖上级目录的其他脚本）

支持：
- HTML 格式原文（cppguide.html, javaguide.html 等）
- Markdown 格式原文（pyguide.md, shellguide.md 等）
- Markdown 格式译文（docs/guides/*.md）
"""

import html as _html_lib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

# 本脚本所在目录的上两级为项目根目录
REPO_ROOT = Path(__file__).parent.parent.parent

# 指南名 -> 原始源文件列表（按优先级排列）
ORIGINAL_SOURCES: dict[str, list[str]] = {
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

# 指南名 -> 译文文件路径
TRANSLATED_PATHS: dict[str, str] = {
    "cpp":        "docs/guides/cpp.md",
    "python":     "docs/guides/python.md",
    "javascript": "docs/guides/javascript.md",
    "java":       "docs/guides/java.md",
    "typescript": "docs/guides/typescript.md",
    "go":         "docs/guides/go.md",
    "shell":      "docs/guides/shell.md",
    "html-css":   "docs/guides/html-css.md",
}

SUPPORTED_GUIDES = list(ORIGINAL_SOURCES.keys())


@dataclass
class SectionInfo:
    num: str          # 章节号，如 "4.5.1"
    title: str        # 完整标题，如 "4.5.1 Where to break"
    level: int        # 标题层级（2 = h2/##，3 = h3/### ...）
    token_estimate: int
    has_translation: bool
    source_file: str  # 原文来自哪个文件


# ─────────────────────────────────────────────────────────
# Token 估算（无需 API 调用）
# ─────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """粗估文本的 token 数（中文约 2 char/token，英文约 4 char/token）。"""
    if not text:
        return 0
    zh_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other_count = len(text) - zh_count
    return zh_count // 2 + other_count // 4


# ─────────────────────────────────────────────────────────
# HTML 提取
# ─────────────────────────────────────────────────────────

def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _html_to_text(fragment: str) -> str:
    """将 HTML 片段转换为带基本格式的纯文本，保留代码块。"""
    code_blocks: list[str] = []

    def save_pre(m: re.Match) -> str:
        inner = _strip_tags(m.group(1))
        inner = _html_lib.unescape(inner)
        code_blocks.append(inner)
        return f"\x00CODE{len(code_blocks) - 1}\x00"

    text = re.sub(r"<pre[^>]*>(.*?)</pre>", save_pre,
                  fragment, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<li[^>]*>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"</?(?:p|div|blockquote|tr|dt|dd|ul|ol)[^>]*>",
        "\n", text, flags=re.IGNORECASE,
    )
    text = re.sub(r"<t[dh][^>]*>", "\t", text, flags=re.IGNORECASE)
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`",
                  text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>", r"**\1**",
                  text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<(?:em|i)[^>]*>(.*?)</(?:em|i)>", r"*\1*",
                  text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)

    for i, code in enumerate(code_blocks):
        text = text.replace(f"\x00CODE{i}\x00", f"\n```\n{code.strip()}\n```")

    text = _html_lib.unescape(text)
    lines = [line.rstrip() for line in text.splitlines()]
    result: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run <= 1:
                result.append(line)
        else:
            blank_run = 0
            result.append(line)
    return "\n".join(result).strip()


def _heading_level_for_section(section_num: str) -> int:
    return section_num.count(".") + 2


def extract_from_html(content: str, section_num: str) -> tuple[Optional[str], Optional[str]]:
    """从 HTML 中提取指定序号的章节，返回 (可读文本, 标题)。"""
    level = _heading_level_for_section(section_num)
    heading_re = re.compile(
        rf"<h{level}[^>]*>(.*?)</h{level}>",
        re.IGNORECASE | re.DOTALL,
    )

    target_pos: Optional[int] = None
    target_title = ""
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

    return _html_to_text(fragment), target_title


# ─────────────────────────────────────────────────────────
# Markdown 提取
# ─────────────────────────────────────────────────────────

def _strip_md_frontmatter(content: str) -> str:
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4:]
    return content


def extract_from_md(content: str, section_num: str) -> tuple[Optional[str], Optional[str]]:
    """从 Markdown 中提取指定序号的章节，返回 (Markdown 文本, 标题)。"""
    content = _strip_md_frontmatter(content)
    lines = content.splitlines(keepends=True)

    target_line: Optional[int] = None
    target_level: Optional[int] = None
    target_title = ""

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


# ─────────────────────────────────────────────────────────
# HTML 章节列表解析
# ─────────────────────────────────────────────────────────

class _HtmlHeadingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections: list[tuple[int, str, int]] = []  # (level, title, char_count)
        self._in_heading = False
        self._heading_level = 0
        self._heading_buf: list[str] = []
        self._code_depth = 0
        self._current: Optional[list] = None
        self._section_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("pre", "code"):
            self._code_depth += 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._in_heading = True
            self._heading_level = int(tag[1])
            self._heading_buf = []

    def handle_endtag(self, tag):
        if tag in ("pre", "code"):
            self._code_depth = max(0, self._code_depth - 1)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._in_heading:
            title = "".join(self._heading_buf).strip()
            if self._current is not None:
                self._current[2] = len("".join(self._section_buf))
                self.sections.append(tuple(self._current))  # type: ignore[arg-type]
            self._current = [int(tag[1]), title, 0]
            self._section_buf = []
            self._in_heading = False

    def handle_data(self, data):
        if self._in_heading:
            self._heading_buf.append(data)
        elif self._code_depth == 0 and self._current is not None:
            self._section_buf.append(data)

    def finalize(self):
        if self._current is not None:
            self._current[2] = len("".join(self._section_buf))
            self.sections.append(tuple(self._current))  # type: ignore[arg-type]


def _parse_html_sections(content: str) -> list[tuple[int, str, int]]:
    p = _HtmlHeadingParser()
    p.feed(content)
    p.finalize()
    return p.sections


def _parse_md_sections(content: str) -> list[tuple[int, str, int]]:
    content = _strip_md_frontmatter(content)
    sections = []
    current = None
    section_lines = []
    in_code = False

    for line in content.splitlines():
        if line.startswith("```") or line.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            if current is not None:
                current[2] = len(" ".join(section_lines))
                sections.append(tuple(current))
            current = [len(m.group(1)), m.group(2).strip(), 0]
            section_lines = []
        elif current is not None:
            clean = re.sub(r"`[^`]+`", "", line)
            section_lines.append(clean)

    if current is not None:
        current[2] = len(" ".join(section_lines))
        sections.append(tuple(current))
    return sections


# ─────────────────────────────────────────────────────────
# 公共 API
# ─────────────────────────────────────────────────────────

def _extract_section_num(title: str) -> Optional[str]:
    """从标题中提取章节号，如 '4.5.1 Where to break' → '4.5.1'。"""
    m = re.match(r"^(\d+(?:\.\d+)*)\s", title)
    return m.group(1) if m else None


def list_all_sections(guide: str) -> list[SectionInfo]:
    """枚举指定指南的所有章节（含 token 估算和译文状态）。"""
    if guide not in ORIGINAL_SOURCES:
        raise ValueError(f"未知指南: '{guide}'，可用: {', '.join(SUPPORTED_GUIDES)}")

    # 加载译文用于检查是否有对应翻译
    trans_path = REPO_ROOT / TRANSLATED_PATHS[guide]
    trans_content = trans_path.read_text(encoding="utf-8", errors="ignore") if trans_path.exists() else ""
    is_placeholder = "翻译进行中" in trans_content

    result: list[SectionInfo] = []
    for src_path_str in ORIGINAL_SOURCES[guide]:
        src_path = REPO_ROOT / src_path_str
        if not src_path.exists():
            continue
        content = src_path.read_text(encoding="utf-8", errors="ignore")

        if src_path_str.endswith(".html"):
            raw_sections = _parse_html_sections(content)
        else:
            raw_sections = _parse_md_sections(content)

        for level, title, char_count in raw_sections:
            section_num = _extract_section_num(title)
            if section_num is None:
                continue
            if is_placeholder:
                has_trans = False
            else:
                text, _ = extract_from_md(trans_content, section_num) if trans_content else (None, None)
                has_trans = text is not None and len(text.strip()) > 50

            result.append(SectionInfo(
                num=section_num,
                title=title,
                level=level,
                token_estimate=estimate_tokens(content[: char_count + 1]),  # rough
                has_translation=has_trans,
                source_file=src_path_str,
            ))

    return result


def read_original_section(guide: str, section_num: str) -> Optional[str]:
    """提取指定章节的英文原文。"""
    for src_path_str in ORIGINAL_SOURCES.get(guide, []):
        path = REPO_ROOT / src_path_str
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if src_path_str.endswith(".html"):
            text, _ = extract_from_html(content, section_num)
        else:
            text, _ = extract_from_md(content, section_num)
        if text:
            return text
    return None


def read_translated_section(guide: str, section_num: str) -> Optional[str]:
    """提取指定章节的中文译文，若不存在返回 None。"""
    path = REPO_ROOT / TRANSLATED_PATHS.get(guide, "")
    if not path or not path.exists():
        return None
    content = path.read_text(encoding="utf-8", errors="ignore")
    text, _ = extract_from_md(content, section_num)
    return text


def write_section(guide: str, section_num: str, corrected_content: str) -> int:
    """将修正后内容写回译文文件，替换对应章节，返回替换的行数差。

    查找对应章节的起止行，整体替换。
    """
    path = REPO_ROOT / TRANSLATED_PATHS.get(guide, "")
    if not path or not path.exists():
        raise FileNotFoundError(f"译文文件不存在：{path}")

    content = path.read_text(encoding="utf-8", errors="ignore")
    body = _strip_md_frontmatter(content)
    # 计算 frontmatter 的长度
    fm_len = len(content) - len(body)
    fm = content[:fm_len]

    lines = body.splitlines(keepends=True)

    target_line: Optional[int] = None
    target_level: Optional[int] = None

    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            raw_title = m.group(2).strip()
            clean_title = re.sub(r"\s*\{#[^}]+\}", "", raw_title).strip()
            if re.match(rf"^{re.escape(section_num)}(?:\s|$)", clean_title):
                target_line = i
                target_level = len(m.group(1))
                break

    if target_line is None:
        raise ValueError(f"章节 '{section_num}' 未在译文文件中找到")

    end_line = len(lines)
    for i, line in enumerate(lines[target_line + 1:], start=target_line + 1):
        m = re.match(r"^(#{1,6})\s", line)
        if m and len(m.group(1)) <= target_level:  # type: ignore[operator]
            end_line = i
            break

    old_count = end_line - target_line
    new_lines = (corrected_content.rstrip("\n") + "\n").splitlines(keepends=True)
    lines[target_line:end_line] = new_lines
    new_body = "".join(lines)
    path.write_text(fm + new_body, encoding="utf-8")
    return len(new_lines) - old_count


def is_placeholder(guide: str) -> bool:
    path = REPO_ROOT / TRANSLATED_PATHS.get(guide, "")
    if not path or not path.exists():
        return True
    return "翻译进行中" in path.read_text(encoding="utf-8", errors="ignore")
