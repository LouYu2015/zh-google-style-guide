# Google 风格指南（中文翻译）

[![Deploy MkDocs](https://github.com/louyu/ai-translated-google-styleguide/actions/workflows/deploy.yml/badge.svg)](https://github.com/louyu/ai-translated-google-styleguide/actions/workflows/deploy.yml)
[![License: CC BY 3.0](https://img.shields.io/badge/License-CC%20BY%203.0-blue.svg)](https://creativecommons.org/licenses/by/3.0/)

[Google Style Guide](https://github.com/google/styleguide) 的中文翻译，由 AI 辅助翻译 + 人工审校。

**在线阅读：** https://louyu.github.io/ai-translated-google-styleguide/

## 本地开发

```bash
# 克隆仓库（含 submodule）
git clone --recurse-submodules https://github.com/louyu/ai-translated-google-styleguide.git
cd ai-translated-google-styleguide

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 本地预览（热重载）
mkdocs serve

# 构建静态站点
mkdocs build
```

## 项目结构

```
├── .github/workflows/  # GitHub Actions 自动部署
├── docs/               # 翻译后的 Markdown 文档
│   └── guides/         # 各语言风格指南
├── scripts/            # 辅助脚本
├── styleguide/         # 原始 Google Style Guide
├── translation/        # 翻译管理文件
│   ├── NOTES.md        # 翻译注意事项与 Prompt 记录
│   └── GLOSSARY.md     # 术语对照表
├── mkdocs.yml          # MkDocs 配置
└── requirements.txt    # Python 依赖
```

## 许可证

原始内容版权归 Google LLC 所有，以 [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) 协议发布。
本翻译遵循相同协议。
