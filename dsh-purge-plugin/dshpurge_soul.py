"""SOUL.md 托管块：装/换/卸，幂等、原子、先备份。

为什么是 SOUL.md：Hermes 装配 system prompt 时，身份槽 #1 读 $HERMES_HOME/SOUL.md；
它被标记为 user_authored，注入特征只告警不拦截，而且是唯一能承载 2 万多字符提示词的
用户可控通道（插件系统提示段有 4000 字符/段、8000 字符总量的硬上限）。
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import dshpurge_config as C


def soul_path(home: Path | None = None) -> Path:
    return (home or C.hermes_home()) / "SOUL.md"


def render_block(prompt: str) -> str:
    head = (
        f"{C.SOUL_BEGIN}\n"
        f"<!-- managed by hermes plugin {C.PLUGIN_NAME} {C.PLUGIN_VERSION} | "
        f"本块由插件写入，手改会被下次加载覆盖；改 prompt/default-prompt.md 或执行 "
        f"`hermes dsh-purge install` 重写 -->\n"
    )
    return f"{head}{prompt.rstrip()}\n{C.SOUL_END}\n"


def _cut_region(text: str, begin: str, end: str) -> str:
    """删掉 begin..end（含标记）的所有区间；未闭合则截断到 begin 之前。"""
    out = text
    while begin in out:
        i = out.index(begin)
        j = out.find(end, i + len(begin))
        if j < 0:
            out = out[:i]
            break
        out = out[:i] + out[j + len(end):]
    return out


def strip_managed(text: str) -> str:
    return _cut_region(text, C.SOUL_BEGIN, C.SOUL_END)


def strip_legacy(text: str) -> str:
    for begin, end in C.LEGACY_BLOCKS:
        text = _cut_region(text, begin, end)
    return text


def has_block(text: str) -> bool:
    return C.SOUL_BEGIN in text and C.SOUL_END in text


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".dshpurge.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _backup(path: Path, home: Path) -> str | None:
    if not path.exists():
        return None
    dst = C.backup_dir(home) / f"SOUL.md.{C.stamp()}.bak"
    shutil.copy2(path, dst)
    return str(dst)


def read_soul(home: Path | None = None) -> str:
    p = soul_path(home)
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def ensure(prompt: str, home: Path | None = None, *, strip_legacy_blocks: bool = True) -> dict:
    """确保 SOUL.md 恰好含一份最新托管块。返回 {action, path, chars, backup, legacy_removed}。"""
    home = home or C.hermes_home()
    path = soul_path(home)
    original = read_soul(home)
    body = strip_managed(original)
    legacy_removed = False
    if strip_legacy_blocks:
        stripped = strip_legacy(body)
        legacy_removed = stripped != body
        body = stripped
    block = render_block(prompt)
    new = (body.rstrip() + "\n\n" + block) if body.strip() else block
    action = "unchanged"
    backup = None
    if new != original:
        action = "created" if not original.strip() else ("migrated" if legacy_removed else "updated")
        backup = _backup(path, home)
        _atomic_write(path, new)
    return {
        "action": action,
        "path": str(path),
        "chars": len(new),
        "prompt_chars": len(prompt),
        "backup": backup,
        "legacy_removed": legacy_removed,
    }


def remove(home: Path | None = None) -> dict:
    """卸掉托管块（以及旧版块），其余内容原样保留；没有则什么都不做。"""
    home = home or C.hermes_home()
    path = soul_path(home)
    original = read_soul(home)
    if not original:
        return {"action": "missing", "path": str(path)}
    body = strip_managed(original)
    had_legacy = strip_legacy(body) != body
    body = strip_legacy(body)
    if body == original:
        return {"action": "unchanged", "path": str(path), "legacy_removed": False}
    backup = _backup(path, home)
    text = body.rstrip() + "\n" if body.strip() else ""
    _atomic_write(path, text)
    return {"action": "removed", "path": str(path), "backup": backup,
            "legacy_removed": had_legacy, "chars": len(text)}


def status(home: Path | None = None) -> dict:
    text = read_soul(home)
    block_present = has_block(text)
    block_chars = 0
    if block_present:
        i = text.index(C.SOUL_BEGIN)
        j = text.index(C.SOUL_END, i)
        block_chars = j + len(C.SOUL_END) - i
    return {
        "path": str(soul_path(home)),
        "exists": bool(text),
        "chars": len(text),
        "block_present": block_present,
        "block_chars": block_chars,
        "legacy_present": any(b in text for b, _ in C.LEGACY_BLOCKS),
    }
