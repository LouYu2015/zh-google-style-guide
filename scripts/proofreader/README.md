# AI 翻译校对助手

使用 Claude AI 校对 Google 编程风格指南中文译文的智能体系统。

## 功能

- **自动分块**：Claude 分析章节结构，自动规划最优处理顺序
- **逐块校对**：对每个处理块，Claude 对比原文和译文，输出修正建议
- **流式输出**：实时显示 Claude 的思考过程和输出内容
- **自动修正**：将修正后的译文直接写回翻译文件（可选 dry-run 模式）
- **记忆传递**：每块的校对记忆传递给下一块，保持上下文连贯
- **断点续传**：中断后可从上次进度继续
- **调试日志**：完整记录所有 API 请求和响应

## 使用方法

```bash
# 校对 Java 指南并自动应用修正
.venv/bin/python scripts/proofreader/main.py java

# 只报告问题，不修改文件（dry-run 模式）
.venv/bin/python scripts/proofreader/main.py java --dry-run

# 从上次中断的地方继续
.venv/bin/python scripts/proofreader/main.py java --resume
```

## API Key 配置

API Key 按以下优先级查找：
1. 环境变量 `ANTHROPIC_API_KEY`
2. `~/.config/proofreader/api_key` 文件
3. 启动时提示输入（可选择保存）

## 输出

- **终端**：实时显示进度、思考过程、修正结果
- **调试日志**：`debug/proofreader_{session_id}/`
  - `run_info.json` — 会话元信息
  - `planning_request.json` / `planning_response.txt` — 分块规划
  - `chunk_XX/request.json` — 各块的 API 请求
  - `chunk_XX/response.txt` — Claude 的完整输出
  - `chunk_XX/thinking.txt` — Claude 的思考过程
  - `chunk_XX/result.json` — 解析后的修正结果
  - `state.json` — 当前会话状态（用于断点续传）
  - `report.md` — 最终校对报告

## 模块结构

```
scripts/proofreader/
├── main.py      # CLI 入口 + 主流程
├── config.py    # API Key 管理
├── reader.py    # 原文/译文读取 + 写回
├── state.py     # 会话状态持久化
├── chunker.py   # Phase 1: Claude 规划分块
├── reviewer.py  # Phase 2: Claude 逐块校对（流式）
├── display.py   # 终端 UI
├── logger.py    # 调试日志
└── tests/       # 单元测试
```

## 运行测试

```bash
.venv/bin/python -m pytest scripts/proofreader/tests/ -v
```
