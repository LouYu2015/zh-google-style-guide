# 翻译校对智能体

基于 Claude claude-sonnet-4-6 的 Google Style Guide 中文译文校对工具。

## 功能

- **自动分块**：Claude 分析文档章节结构，自主决定处理粒度（合并小章节、拆分大章节）
- **工具调用循环**：Claude 通过读取章节、报告问题、更新术语表、写回修正等工具自主完成校对
- **跨章节状态**：术语表在所有章节间共享，确保翻译一致性，并实时同步到 `translation/GLOSSARY.md`
- **断点续传**：每个处理单元完成后自动保存进度，中断后可恢复
- **实时显示**：流式输出模型响应，进度条实时更新

## 安装

```bash
# 在项目根目录下执行，复用已有的 .venv
.venv/bin/pip install -r scripts/proofreader/requirements.txt
```

## 使用方法

```bash
# 完整校对（修正自动写入译文文件）
.venv/bin/python scripts/proofreader/main.py java

# 仅生成报告，不修改文件
.venv/bin/python scripts/proofreader/main.py java --dry-run

# 恢复上次中断的会话
.venv/bin/python scripts/proofreader/main.py java --resume

# 只处理某一个处理单元（调试用）
.venv/bin/python scripts/proofreader/main.py java --unit unit_03

# 关闭流式输出（等待完整响应后显示）
.venv/bin/python scripts/proofreader/main.py java --no-stream

# 不更新术语表文件（仅在内存中维护）
.venv/bin/python scripts/proofreader/main.py java --no-glossary-update
```

支持的指南名称：`java` · `cpp` · `python` · `javascript` · `typescript` · `go` · `shell` · `html-css`

## API Key

按以下顺序查找，找到即用：

1. 环境变量 `ANTHROPIC_API_KEY`
2. `~/.config/google-styleguide-proofreader/api_key`（首次运行时可选择保存）

## 输出

| 路径 | 内容 |
|------|------|
| `debug/proofreader_{session_id}/report.md` | 最终校对报告（问题列表、术语变更、人工审核项） |
| `debug/proofreader_{session_id}/state.json` | 会话状态（用于断点续传） |
| `debug/proofreader_{session_id}/{unit_id}_*/` | 每个处理单元的 API 请求/响应日志 |
| `translation/GLOSSARY.md` | 实时更新的术语表 |
| `docs/guides/{guide}.md` | 修正后的译文（`--dry-run` 时不修改） |

## 工作流程

```
Phase 1 (Planning)
  └─ 列出所有章节 → Claude 制定分块处理计划

Phase 2 (Review，逐单元循环)
  ├─ 构建系统提示（角色 + 翻译原则 + 当前术语表，利用 Prompt Caching）
  ├─ Claude 通过工具调用自主完成校对：
  │    read_section → check_term_consistency → report_issue
  │    → update_glossary → apply_section_correction → mark_unit_done
  └─ 单元完成后保存状态、同步术语表，继续下一单元
```
