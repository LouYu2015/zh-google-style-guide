#!/usr/bin/env python3
"""
get_translated_section.py - 从翻译文件中提取指定章节内容

用法:
  python scripts/get_translated_section.py java 4.5.1
  python scripts/get_translated_section.py java 4
  python scripts/get_translated_section.py cpp 3.1

输出:
  章节的 Markdown 译文（保留原始格式）
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# 指南名 -> 翻译文件路径
GUIDES: dict[str, str] = {
    "cpp":        "docs/guides/cpp.md",
    "python":     "docs/guides/python.md",
    "javascript": "docs/guides/javascript.md",
    "java":       "docs/guides/java.md",
    "typescript": "docs/guides/typescript.md",
    "go":         "docs/guides/go.md",
    "shell":      "docs/guides/shell.md",
    "html-css":   "docs/guides/html-css.md",
}


def _strip_md_frontmatter(content: str) -> str:
    """移除 YAML front matter（--- ... ---）。"""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4:]
    return content


def extract_section(content: str, section_num: str) -> tuple[str, str] | tuple[None, None]:
    """从 Markdown 中提取指定序号的章节，返回 (Markdown 文本, 标题)。

    匹配规则：标题行中，去掉 {#anchor} 后缀后，以 '<section_num> ' 开头。
    例：'### 4.5.1 在哪里断行 {#s4.5.1-...}' 匹配序号 '4.5.1'。
    """
    content = _strip_md_frontmatter(content)
    lines = content.splitlines(keepends=True)

    target_line: int | None = None
    target_level: int | None = None
    target_title: str = ""

    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            hashes = m.group(1)
            raw_title = m.group(2).strip()
            # 去除 {#anchor} 后缀再比较
            clean_title = re.sub(r"\s*\{#[^}]+\}", "", raw_title).strip()
            if re.match(rf"^{re.escape(section_num)}(?:\s|$)", clean_title):
                target_line = i
                target_level = len(hashes)
                target_title = clean_title
                break

    if target_line is None:
        return None, None

    # 收集直到下一个同级或更高级标题
    result_lines: list[str] = []
    for line in lines[target_line:]:
        m = re.match(r"^(#{1,6})\s", line)
        if m and len(m.group(1)) <= target_level and result_lines:  # type: ignore[operator]
            break
        result_lines.append(line)

    return "".join(result_lines).strip(), target_title


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python scripts/get_translated_section.py <指南名> <章节序号>")
        print(f"可用指南: {', '.join(GUIDES)}")
        print("示例: python scripts/get_translated_section.py java 4.5.1")
        sys.exit(1)

    guide = sys.argv[1]
    section_num = sys.argv[2]

    if guide not in GUIDES:
        print(f"未知指南: '{guide}'，可用指南: {', '.join(GUIDES)}")
        sys.exit(1)

    path = REPO_ROOT / GUIDES[guide]
    if not path.exists():
        print(f"翻译文件不存在：{path}")
        sys.exit(1)

    content = path.read_text(encoding="utf-8", errors="ignore")
    text, title = extract_section(content, section_num)

    if text is None:
        print(f"未找到章节 '{section_num}'（指南：{guide}）")
        sys.exit(1)

    print(f"# [{guide}] 译文：{title}\n")
    print(text)


if __name__ == "__main__":
    main()
