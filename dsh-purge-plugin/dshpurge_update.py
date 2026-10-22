"""更新检查与升级（双轴）。

轴一：本移植仓库（1505843894/hermes-purge）的新 tag —— 代码/技能/内核段有没有更新。
轴二：上游 dsh-purge（YuJunZhiXue/dsh-purge）—— 默认提示词有没有变（asset-table.js 的
      sha256 变了就说明破甲提示词重封过，必须重新解封并重写 SOUL.md 托管块）。

只用 stdlib（urllib / tarfile / hashlib），无第三方依赖；任何网络失败都返回结构化错误，
不抛栈、不影响插件加载。

    hermes dsh-purge check-update [--json]
    hermes dsh-purge update [--force] [--check]
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import dshpurge_config as C
from . import dshpurge_prompt as P
from . import dshpurge_soul as Soul

PORT_REPO = "1505843894/hermes-purge"
UPSTREAM_REPO = "kingcharleslzy-ai/dsh-purge"
UPSTREAM_BRANCH = "master"
UA = f"dsh-purge-hermes/{C.PLUGIN_VERSION} (+hermes plugin updater)"
TIMEOUT = 15


# ── 基础 ────────────────────────────────────────────────────────────────────
def _get(url: str) -> bytes:
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.github+json, application/octet-stream, */*",
    }
    tok = _token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and not tok:
            raise RuntimeError(
                "404（仓库可能是私有的）：设 DSHPURGE_GITHUB_TOKEN / GITHUB_TOKEN，"
                f"或先 `gh auth login` —— {url}") from exc
        raise


def _token() -> str:
    """私有仓库 / 限流需要 token：环境变量优先，其次复用已登录的 gh。"""
    for name in ("DSHPURGE_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    try:
        import subprocess

        done = subprocess.run(["gh", "auth", "token"], capture_output=True, timeout=8, text=True)
        tok = (done.stdout or "").strip()
        if done.returncode == 0 and tok:
            return tok
    except Exception:  # noqa: BLE001
        pass
    return ""


def _get_json(url: str):
    return json.loads(_get(url).decode("utf-8", "replace"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ver(text: str) -> tuple:
    out = []
    for part in str(text or "").lstrip("vV").replace("-", ".").split("."):
        out.append(int(part) if part.isdigit() else -1)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:4])


def local_version() -> str:
    try:
        for line in (C.plugin_dir() / "plugin.yaml").read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return C.PLUGIN_VERSION


def pins() -> dict:
    try:
        return json.loads((C.plugin_dir() / "UPSTREAM.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def prompt_sha_local() -> str:
    return _sha256(P.full_prompt().encode("utf-8"))


# ── 远端 ────────────────────────────────────────────────────────────────────
def port_latest_tag() -> dict:
    """移植仓库最新 tag（semver 最大者）。tag 形如 v1.4.2。"""
    tags = _get_json(f"https://api.github.com/repos/{PORT_REPO}/tags?per_page=100")
    best, best_ver = None, (0,)
    for t in tags or []:
        name = t.get("name", "")
        v = _ver(name)
        if v > best_ver:
            best, best_ver = name, v
    if not best:
        raise RuntimeError("移植仓库没有 tag")
    return {"tag": best, "version": best.lstrip("vV"), "tarball": f"https://codeload.github.com/{PORT_REPO}/tar.gz/refs/tags/{best}"}


def upstream_now() -> dict:
    """上游当前状态：package.json 版本 + 提示词封存表/密钥指纹。"""
    meta = _get_json(f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_BRANCH}/package.json")
    asset = _get(f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_BRANCH}/lib/asset-table.js")
    key = _get(f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_BRANCH}/lib/table-key.js")
    return {
        "version": str(meta.get("version") or ""),
        "asset_table_sha256": _sha256(asset),
        "table_key_sha256": _sha256(key),
    }


def check() -> dict:
    local = local_version()
    pin = pins()
    up_pin = pin.get("upstream") or {}
    out = {
        "local_version": local,
        "prompt_sha256": prompt_sha_local(),
        "prompt_sha256_pinned": (pin.get("prompt") or {}).get("sha256", ""),
        "upstream_pinned_version": up_pin.get("version", ""),
        "upstream_pinned_asset_table": up_pin.get("asset_table_sha256", ""),
        "errors": [],
    }
    try:
        tag = port_latest_tag()
        out["port_latest_tag"] = tag["tag"]
        out["port_latest_version"] = tag["version"]
        out["port_update_available"] = _ver(tag["version"]) > _ver(local)
    except Exception as exc:  # noqa: BLE001
        out["port_update_available"] = None
        out["errors"].append(f"移植仓库查询失败: {exc}")

    try:
        up = upstream_now()
        out["upstream_latest_version"] = up["version"]
        out["upstream_latest_asset_table"] = up["asset_table_sha256"]
        out["upstream_prompt_changed"] = (
            bool(out["upstream_pinned_asset_table"])
            and up["asset_table_sha256"] != out["upstream_pinned_asset_table"]
        )
        out["upstream_version_changed"] = (
            bool(out["upstream_pinned_version"]) and up["version"] != out["upstream_pinned_version"]
        )
    except Exception as exc:  # noqa: BLE001
        out["upstream_prompt_changed"] = None
        out["upstream_version_changed"] = None
        out["errors"].append(f"上游查询失败: {exc}")

    if out.get("port_update_available") or out.get("upstream_prompt_changed"):
        out["verdict"] = "update-available"
    elif out["errors"]:
        out["verdict"] = "unknown"
    else:
        out["verdict"] = "up-to-date"
    return out


# ── 升级 ────────────────────────────────────────────────────────────────────
def _extract_plugin(tar_bytes: bytes, dest: Path) -> Path:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
        members = [m for m in tf.getmembers() if m.isfile() and "/dsh-purge-plugin/" in m.name]
        if not members:
            raise RuntimeError("压缩包里没有 dsh-purge-plugin/")
        for m in members:
            rel = m.name.split("/dsh-purge-plugin/", 1)[1]
            if rel.startswith("/") or ".." in rel.split("/"):
                raise RuntimeError(f"非法路径: {m.name}")
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(m)
            if src is not None:
                target.write_bytes(src.read())
    if not (dest / "plugin.yaml").exists():
        raise RuntimeError("解包后缺少 plugin.yaml")
    return dest


def apply(force: bool = False) -> dict:
    info = check()
    if not force and not info.get("port_update_available"):
        return {"action": "up-to-date", "check": info}

    tag = port_latest_tag()
    version = tag["version"]
    if not force and _ver(version) <= _ver(local_version()):
        return {"action": "up-to-date", "check": info}

    data = _get(tag["tarball"])
    work = Path(tempfile.mkdtemp(prefix="dshpurge-update-"))
    staged = _extract_plugin(data, work / "new")

    live = C.plugin_dir()
    backup = C.backup_dir() / f"plugin.{C.stamp()}.bak"
    shutil.copytree(live, backup)

    replaced = []
    for src in sorted(staged.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(staged)
        dst = live / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            continue
        shutil.copy2(src, dst)
        replaced.append(str(rel))
    shutil.rmtree(work, ignore_errors=True)

    soul_res = {}
    try:
        soul_res = Soul.ensure(P.full_prompt())
    except Exception as exc:  # noqa: BLE001
        soul_res = {"action": "error", "error": str(exc)}

    return {
        "action": "updated",
        "from": info.get("local_version"),
        "to": version,
        "tag": tag["tag"],
        "files": replaced,
        "backup": str(backup),
        "soul": soul_res,
        "note": "提示词段按会话冻结，新开会话生效；跑一次 `hermes dsh-purge verify` 复核",
    }


def format_check(info: dict) -> str:
    lines = [
        "dsh-purge for Hermes · 更新检查",
        f"  本地版本      : {info.get('local_version')}",
    ]
    if info.get("port_update_available") is None:
        lines.append("  移植仓库      : 查询失败")
    else:
        mark = "↑ 有新版" if info["port_update_available"] else "已是最新"
        lines.append(f"  移植仓库      : {info.get('port_latest_tag')}（{mark}）")
    if info.get("upstream_prompt_changed") is None:
        lines.append("  上游 dsh-purge: 查询失败")
    else:
        if info["upstream_prompt_changed"]:
            lines.append(
                f"  上游 dsh-purge: ↑ 提示词已重封（{info.get('upstream_pinned_version')} -> "
                f"{info.get('upstream_latest_version')}），需要重新解封并升级")
        else:
            lines.append(
                f"  上游 dsh-purge: {info.get('upstream_latest_version')}（提示词未变）")
    lines.append(f"  提示词指纹    : {info.get('prompt_sha256', '')[:16]}…")
    for err in info.get("errors") or []:
        lines.append(f"  [!] {err}")
    lines.append(f"  结论          : {info.get('verdict')}")
    return "\n".join(lines)
