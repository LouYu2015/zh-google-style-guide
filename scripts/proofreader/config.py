"""
config.py - API key management and global configuration.

Priority for API key: env ANTHROPIC_API_KEY → ~/.config/proofreader/api_key → prompt+save
"""
import os
import sys
from pathlib import Path

MODEL = "claude-sonnet-4-6"

_CONFIG_DIR = Path.home() / ".config" / "proofreader"
_API_KEY_FILE = _CONFIG_DIR / "api_key"


def get_api_key() -> str:
    """Return the Anthropic API key, prompting the user if not found."""
    # 1. Environment variable
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key

    # 2. Config file
    if _API_KEY_FILE.exists():
        key = _API_KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key

    # 3. Prompt user
    print("未找到 Anthropic API Key。")
    try:
        key = input("请输入你的 Anthropic API Key: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。", file=sys.stderr)
        sys.exit(1)

    if not key:
        print("未提供 API Key，退出。", file=sys.stderr)
        sys.exit(1)

    # Optionally save
    try:
        save = input("是否保存 API Key 以便下次使用？[y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        save = "n"

    if save == "y":
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _API_KEY_FILE.write_text(key, encoding="utf-8")
        _API_KEY_FILE.chmod(0o600)
        print(f"API Key 已保存至 {_API_KEY_FILE}")

    return key
