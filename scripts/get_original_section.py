#!/usr/bin/env python3
"""
get_original_section.py - 从原始风格指南中提取指定章节内容

用法:
  python scripts/get_original_section.py java 4.5.1
  python scripts/get_original_section.py java 4
  python scripts/get_original_section.py cpp 3.1

输出:
  章节原文（HTML 文件转为可读文本，MD 文件输出原始 Markdown）
"""

import html as _html_lib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# 指南名 -> 原始源文件列表（按优先级排列）
GUIDES: dict[str, list[str]] = {
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


# ──────────────────────────────────────────────
# HTML 提取
# ──────────────────────────────────────────────

def _heading_level_for_section(section_num: str) -> int:
    """根据章节序号推断 HTML 标题层级（h2 起）。
    例：'1' → 2, '1.1' → 3, '4.5.1' → 4, '4.8.5.1' → 5
    """
    return section_num.count(".") + 2


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _html_to_text(fragment: str) -> str:
    """将 HTML 片段转换为带基本格式的纯文本，保留代码块。"""
    # 1. 提取并保护 <pre> 代码块
    code_blocks: list[str] = []

    def save_pre(m: re.Match) -> str:
        inner = _strip_tags(m.group(1))
        inner = _html_lib.unescape(inner)
        code_blocks.append(inner)
        return f"\x00CODE{len(code_blocks) - 1}\x00"

    text = re.sub(r"<pre[^>]*>(.*?)</pre>", save_pre,
                  fragment, flags=re.IGNORECASE | re.DOTALL)

    # 2. 列表项
    counter: list[int] = [0]

    def replace_li(m: re.Match) -> str:
        # 判断父节点是 <ol> 还是 <ul>（简化：都用 "- "）
        return "\n- "

    text = re.sub(r"<li[^>]*>", replace_li, text, flags=re.IGNORECASE)

    # 3. 块级元素断行
    text = re.sub(
        r"</?(?:p|div|blockquote|tr|dt|dd|ul|ol)[^>]*>",
        "\n", text, flags=re.IGNORECASE,
    )
    text = re.sub(r"<t[dh][^>]*>", "\t", text, flags=re.IGNORECASE)

    # 4. 内联代码（在删其余标签前处理，防止嵌套破坏）
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`",
                  text, flags=re.IGNORECASE | re.DOTALL)

    # 5. 加粗 / 斜体
    text = re.sub(r"<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>", r"**\1**",
                  text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<(?:em|i)[^>]*>(.*?)</(?:em|i)>", r"*\1*",
                  text, flags=re.IGNORECASE | re.DOTALL)

    # 6. 删除其余标签
    text = re.sub(r"<[^>]+>", "", text)

    # 7. 还原代码块
    for i, code in enumerate(code_blocks):
        text = text.replace(f"\x00CODE{i}\x00", f"\n```\n{code.strip()}\n```")

    # 8. 解码 HTML 实体
    text = _html_lib.unescape(text)

    # 9. 规范化空白
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


def extract_from_html(content: str, section_num: str) -> tuple[str, str] | tuple[None, None]:
    """从 HTML 中提取指定序号的章节，返回 (可读文本, 标题)。"""
    level = _heading_level_for_section(section_num)
    heading_re = re.compile(
        rf"<h{level}[^>]*>(.*?)</h{level}>",
        re.IGNORECASE | re.DOTALL,
    )

    # 找目标标题
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

    # 截取到下一个同级或更高级标题
    fragment = content[target_pos:]
    stop_re = re.compile(
        rf"<h[1-{level}][^>]*>", re.IGNORECASE
    )
    matches = list(stop_re.finditer(fragment))
    if len(matches) >= 2:
        fragment = fragment[: matches[1].start()]

    return _html_to_text(fragment), target_title


# ──────────────────────────────────────────────
# Markdown 提取（原始 MD 格式的指南）
# ──────────────────────────────────────────────

def _strip_md_frontmatter(content: str) -> str:
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4:]
    return content


def extract_from_md(content: str, section_num: str) -> tuple[str, str] | tuple[None, None]:
    """从 Markdown 中提取指定序号的章节，返回 (Markdown 文本, 标题)。"""
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
            # 去除 {#anchor} 后缀
            clean_title = re.sub(r"\s*\{#[^}]+\}", "", raw_title).strip()
            if re.match(rf"^{re.escape(section_num)}(?:\s|$)", clean_title):
                target_line = i
                target_level = len(hashes)
                target_title = clean_title
                break

    if target_line is None:
        return None, None

    # 收集直到同级或更高级标题
    result_lines: list[str] = []
    for line in lines[target_line:]:
        m = re.match(r"^(#{1,6})\s", line)
        if m and len(m.group(1)) <= target_level and result_lines:  # type: ignore[operator]
            break
        result_lines.append(line)

    return "".join(result_lines).strip(), target_title


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python scripts/get_original_section.py <指南名> <章节序号>")
        print(f"可用指南: {', '.join(GUIDES)}")
        print("示例: python scripts/get_original_section.py java 4.5.1")
        sys.exit(1)

    guide = sys.argv[1]
    section_num = sys.argv[2]

    if guide not in GUIDES:
        print(f"未知指南: '{guide}'，可用指南: {', '.join(GUIDES)}")
        sys.exit(1)

    for src_path in GUIDES[guide]:
        path = REPO_ROOT / src_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")

        if src_path.endswith(".html"):
            text, title = extract_from_html(content, section_num)
        else:
            text, title = extract_from_md(content, section_num)

        if text is not None:
            print(f"# [{guide}] 原文：{title}\n")
            print(text)
            sys.exit(0)

    print(f"未找到章节 '{section_num}'（指南：{guide}）")
    sys.exit(1)


if __name__ == "__main__":
    main()
