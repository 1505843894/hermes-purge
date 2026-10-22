"""dsh-purge (Hermes plugin) — 路径、标记与常量。

纯 stdlib，无第三方依赖。所有写入都落在 $HERMES_HOME（或 HERMES_HOME 覆盖）下。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

PLUGIN_NAME = "dsh-purge"
PLUGIN_VERSION = "1.4.2"

# SOUL.md 托管块（幂等替换，块外的用户内容一律不动）
SOUL_BEGIN = "<!-- dsh-purge:hermes:begin -->"
SOUL_END = "<!-- dsh-purge:hermes:end -->"

# 旧版脚本式移植留下的块，安装时迁走（内容进备份），避免同一份提示词出现两遍
LEGACY_BLOCKS = (
    ("<!-- hermes-purge:identity -->", "<!-- /hermes-purge:identity -->"),
    ("<!-- hermes-purge:appended -->", "<!-- /hermes-purge:appended -->"),
)

# 系统提示段 id：必须匹配 ^[a-z0-9][a-z0-9._-]{0,127}$
SECTION_ID = "dsh-purge.kernel"
SECTION_MAX_CHARS = 4000  # Hermes 硬上限


def hermes_home() -> Path:
    env = (os.environ.get("HERMES_HOME") or "").strip()
    if env:
        return Path(env).expanduser()
    try:  # 官方解析器优先（多 profile / 服务模式都能拿到正确的 home）
        from hermes_constants import get_hermes_home  # type: ignore

        return Path(get_hermes_home())
    except Exception:
        return Path.home() / ".hermes"


def state_dir(home: Path | None = None) -> Path:
    d = (home or hermes_home()) / "dsh-purge"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backup_dir(home: Path | None = None) -> Path:
    d = state_dir(home) / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def plugin_dir() -> Path:
    return Path(__file__).resolve().parent
