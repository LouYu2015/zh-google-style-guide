#!/usr/bin/env python3
"""
check_coverage.py - 检查 Google Style Guide 翻译覆盖率

用法:
  python scripts/check_coverage.py                        # 检查所有指南
  python scripts/check_coverage.py cpp                    # 检查单个指南
  python scripts/check_coverage.py --list-sections python # 输出原文章节清单
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# 指南名 -> (原始文件列表, 翻译文件)
GUIDES = {
    "cpp":        (["styleguide/cppguide.html"], "docs/guides/cpp.md"),
    "python":     (["styleguide/pyguide.md"], "docs/guides/python.md"),
    "javascript": (["styleguide/jsguide.html"], "docs/guides/javascript.md"),
    "java":       (["styleguide/javaguide.html"], "docs/guides/java.md"),
    "typescript": (["styleguide/tsguide.html"], "docs/guides/typescript.md"),
    "go":         (["styleguide/go/guide.md",
                    "styleguide/go/best-practices.md",
                    "styleguide/go/decisions.md"], "docs/guides/go.md"),
    "shell":      (["styleguide/shellguide.md"], "docs/guides/shell.md"),
    "html-css":   (["styleguide/htmlcssguide.html"], "docs/guides/html-css.md"),
}

# Section: (level, title, char_count)


# ---------- HTML 解析 ----------

class _HtmlHeadingParser(HTMLParser):
    """从 HTML 中提取标题和各章节纯文本字符数（排除 <pre>/<code> 内容）。"""

    def __init__(self):
        super().__init__()
        self.sections = []          # [(level, title, char_count)]
        self._in_heading = False
        self._heading_level = 0
        self._heading_buf = []
        self._code_depth = 0        # <pre>/<code> 嵌套深度
        self._current = None        # [level, title, char_count]
        self._section_buf = []      # 当前章节的纯文本

    def handle_starttag(self, tag, attrs):
        if tag in ("pre", "code"):
            self._code_depth += 1
        if tag in ("h1", "h2", "h3", "h4"):
            self._in_heading = True
            self._heading_level = int(tag[1])
            self._heading_buf = []

    def handle_endtag(self, tag):
        if tag in ("pre", "code"):
            self._code_depth = max(0, self._code_depth - 1)
        if tag in ("h1", "h2", "h3", "h4") and self._in_heading:
            title = "".join(self._heading_buf).strip()
            # 保存上一节
            if self._current is not None:
                self._current[2] = len("".join(self._section_buf))
                self.sections.append(tuple(self._current))
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
            self.sections.append(tuple(self._current))


def _parse_html(content: str):
    p = _HtmlHeadingParser()
    p.feed(content)
    p.finalize()
    return p.sections


# ---------- Markdown 解析 ----------

def _strip_md_frontmatter(content: str) -> str:
    """移除 YAML front matter（--- ... ---）。"""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4:]
    return content


def _parse_md(content: str):
    """从 Markdown 中提取标题和各章节纯文本字符数（排除代码块）。"""
    content = _strip_md_frontmatter(content)
    sections = []
    current = None
    section_lines = []
    in_code = False

    for line in content.splitlines():
        # 代码块边界
        if line.startswith("```") or line.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue

        m = re.match(r"^(#{1,4})\s+(.+)$", line)
        if m:
            if current is not None:
                current[2] = len(" ".join(section_lines))
                sections.append(tuple(current))
            current = [len(m.group(1)), m.group(2).strip(), 0]
            section_lines = []
        elif current is not None:
            # 去除行内代码再计入
            clean = re.sub(r"`[^`]+`", "", line)
            section_lines.append(clean)

    if current is not None:
        current[2] = len(" ".join(section_lines))
        sections.append(tuple(current))

    return sections


# ---------- 每个指南的解析入口 ----------

def parse_source(guide_name: str):
    source_files, _ = GUIDES[guide_name]
    all_sections = []
    for src in source_files:
        path = REPO_ROOT / src
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if src.endswith(".html"):
            all_sections.extend(_parse_html(content))
        else:
            all_sections.extend(_parse_md(content))
    return all_sections


def parse_translation(guide_name: str):
    _, trans_file = GUIDES[guide_name]
    path = REPO_ROOT / trans_file
    if not path.exists():
        return []
    return _parse_md(path.read_text(encoding="utf-8", errors="ignore"))


def is_placeholder(guide_name: str) -> bool:
    _, trans_file = GUIDES[guide_name]
    path = REPO_ROOT / trans_file
    if not path.exists():
        return True
    return "翻译进行中" in path.read_text(encoding="utf-8", errors="ignore")


# ---------- 统计辅助 ----------

def _count_level(sections, level: int) -> int:
    return sum(1 for s in sections if s[0] == level)


def _total_chars(sections) -> int:
    return sum(s[2] for s in sections)


# ---------- 输出 ----------

def print_report(guides_to_check):
    print("\nGoogle Style Guide 翻译覆盖率报告")
    print("=" * 70)
    print(f"{'指南':<13} {'状态':<7} {'H2':<10} {'H3':<10}"
          f" {'原文字符':>10} {'已译字符':>10} {'字符覆盖率':>10}")
    print("-" * 70)

    completed = 0
    for name in guides_to_check:
        src   = parse_source(name)
        trans = parse_translation(name)
        placeholder = is_placeholder(name)

        src_h2  = _count_level(src,   2)
        src_h3  = _count_level(src,   3)
        tr_h2   = _count_level(trans, 2)
        tr_h3   = _count_level(trans, 3)
        src_c   = _total_chars(src)
        tr_c    = _total_chars(trans)
        pct     = int(tr_c / src_c * 100) if src_c > 0 else 0

        if placeholder:
            status = "占位页"
        elif pct >= 95:
            status = "已完成"
            completed += 1
        else:
            status = "翻译中"

        h2_str = f"{tr_h2}/{src_h2}"
        h3_str = f"{tr_h3}/{src_h3}"
        print(f"{name:<13} {status:<7} {h2_str:<10} {h3_str:<10}"
              f" {src_c:>10,} {tr_c:>10,} {pct:>9}%")

    print("-" * 70)
    print(f"\n总计：{completed}/{len(guides_to_check)} 个指南已完成翻译\n")
    return completed == len(guides_to_check)


def print_sections(guide_name: str):
    sections = parse_source(guide_name)
    print(f"\n{guide_name} 指南章节列表（原文）")
    print("=" * 55)
    for level, title, chars in sections:
        if level > 3:
            continue
        indent = "  " * (level - 1)
        prefix = "#" * level
        print(f"{indent}{prefix} {title:<42} [{chars:>8,} 字符]")
    total = _total_chars(s for s in sections if s[0] <= 3)
    print(f"\n合计（H1–H3）：{total:,} 字符\n")


# ---------- CLI ----------

def main():
    args = sys.argv[1:]

    if "--list-sections" in args:
        idx   = args.index("--list-sections")
        guide = args[idx + 1] if idx + 1 < len(args) else None
        if not guide or guide not in GUIDES:
            print(f"用法: python scripts/check_coverage.py --list-sections <指南名>")
            print(f"可用指南: {', '.join(GUIDES)}")
            sys.exit(1)
        print_sections(guide)
        sys.exit(0)

    if args and args[0] != "--all":
        guide = args[0]
        if guide not in GUIDES:
            print(f"未知指南: '{guide}'，可用: {', '.join(GUIDES)}")
            sys.exit(1)
        guides = [guide]
    else:
        guides = list(GUIDES)

    all_done = print_report(guides)
    sys.exit(0 if all_done else 1)


if __name__ == "__main__":
    main()
