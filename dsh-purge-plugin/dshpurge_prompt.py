"""提示词载入：完整版（SOUL 身份槽）与内核版（系统提示段）。

完整版来自 dsh-purge 1.4.2 的 lib/asset-table.js（sealSlot/AES-256-GCM+deflate），
用同仓 lib/table-read.js 的 openSlot() 解封后原文照录，仅剥掉 DSH 专用的
`<|im_start|>system:<project_instructions>` 首行信封。
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from . import dshpurge_config as C

_CHATML_HEAD = re.compile(
    r"\A\ufeff?\s*<\|im_start\|>\s*system\s*:\s*<project_instructions>\s*\r?\n",
    re.I,
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


@lru_cache(maxsize=1)
def full_prompt() -> str:
    raw = _read(C.plugin_dir() / "prompt" / "default-prompt.md")
    if not raw:
        return ""
    text = _CHATML_HEAD.sub("", raw).strip("\n")
    return text.rstrip() + "\n"


@lru_cache(maxsize=1)
def kernel() -> str:
    raw = _read(C.plugin_dir() / "prompt" / "kernel.md").strip()
    if not raw:
        return ""
    if len(raw) > C.SECTION_MAX_CHARS:
        # 超限会被宿主整段丢弃，宁可截到安全线也不要静默消失
        cut = raw[: C.SECTION_MAX_CHARS - 40]
        raw = cut.rsplit("\n", 1)[0] + "\n（本段因长度上限被截断）"
    return raw


def prompt_chars() -> int:
    return len(full_prompt())


def kernel_chars() -> int:
    return len(kernel())
