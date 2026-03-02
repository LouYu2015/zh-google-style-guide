"""
config.py - API Key 管理

查找顺序：
1. 环境变量 ANTHROPIC_API_KEY
2. scripts/proofreader/.api_key（项目目录，已加入 .gitignore，权限 600）
3. 交互式提示用户输入 → 询问是否保存
"""

import os
import stat
from pathlib import Path

# API Key 存放在本脚本同目录下的 .api_key 文件（已 gitignore）
_KEY_FILE = Path(__file__).parent / ".api_key"

MODEL = "claude-sonnet-4-6"


def get_api_key() -> str:
    # 1. 环境变量
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key

    # 2. 项目目录配置文件
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_text().strip()
        if key:
            return key

    # 3. 交互式输入
    print("\n未找到 Anthropic API Key。")
    print("请输入你的 API Key（输入后不会显示）：")
    import getpass
    key = getpass.getpass("API Key: ").strip()
    if not key:
        raise RuntimeError("未提供 API Key，程序退出。")

    save = input(f"是否将 API Key 保存到 {_KEY_FILE}（下次无需重新输入）？[y/N] ").strip().lower()
    if save == "y":
        _KEY_FILE.write_text(key)
        _KEY_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
        print(f"已保存到 {_KEY_FILE}")

    return key
