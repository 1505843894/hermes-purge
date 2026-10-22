#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把上游 dsh-purge 的新版提示词同步进本移植包（第二轴的升级工具）。

    python tools/sync_upstream_prompt.py                 # 只比对，不改文件
    python tools/sync_upstream_prompt.py --write         # 写入 prompt/ 并更新 UPSTREAM.json
    python tools/sync_upstream_prompt.py --ref 000b75e --write

流程：拉上游 tarball -> 用上游自己的 lib/table-read.js 解封 asset-table -> 统一成 LF ->
与本地 prompt/default-prompt.md 比对 ->（可选）写入 + 记 pin。需要 node。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

UPSTREAM = "kingcharleslzy-ai/dsh-purge"
UA = "dsh-purge-hermes-sync/1.0"
CHATML = re.compile(r"\A\ufeff?\s*<\|im_start\|>\s*system\s*:\s*<project_instructions>\s*\n", re.I)


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def to_lf(text: str) -> str:
    """上游提交用 CRLF；统一成 LF，否则指纹永远对不上（每行差一个 \\r）。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def peel(text: str) -> str:
    """剥掉 DSH 专用 ChatML 信封并统一行尾。"""
    return CHATML.sub("", to_lf(text)).strip("\n") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=UPSTREAM)
    ap.add_argument("--ref", default="master")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--plugin", default="dsh-purge-plugin")
    a = ap.parse_args()

    plugin = Path(a.plugin).resolve()
    local_path = plugin / "prompt" / "default-prompt.md"
    local_raw = to_lf(local_path.read_text(encoding="utf-8"))

    print(f"== 上游 {a.repo}@{a.ref} ==")
    if re.fullmatch(r"[0-9a-f]{7,40}", a.ref):
        url = f"https://codeload.github.com/{a.repo}/tar.gz/{a.ref}"
    else:
        url = f"https://codeload.github.com/{a.repo}/tar.gz/refs/heads/{a.ref}"
    work = Path(tempfile.mkdtemp(prefix="dshpurge-sync-"))
    with tarfile.open(fileobj=io.BytesIO(get(url)), mode="r:gz") as tf:
        tf.extractall(work, filter="data")
    root = next(p for p in work.iterdir() if p.is_dir())

    pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    asset = (root / "lib" / "asset-table.js").read_bytes()
    key = (root / "lib" / "table-key.js").read_bytes()

    js = "import('./lib/table-read.js').then(m=>{process.stdout.write(m.openSlot())})"
    proc = subprocess.run(["node", "-e", js], cwd=root, capture_output=True, timeout=120)
    if proc.returncode != 0 or not proc.stdout:
        print("解封失败:", proc.stderr.decode("utf-8", "replace")[:400], file=sys.stderr)
        shutil.rmtree(work, ignore_errors=True)
        return 2
    upstream_raw = to_lf(proc.stdout.decode("utf-8"))
    upstream = peel(upstream_raw)
    local = peel(local_raw)

    print(f"上游版本   : {pkg.get('version')}")
    print(f"长度       : 上游 {len(upstream)} 字符 | 本地 {len(local)} 字符")
    print(f"sha256     : 上游 {sha(upstream)[:16]}… | 本地 {sha(local)[:16]}…")
    same = sha(upstream) == sha(local)
    print(f"提示词     : {'一致' if same else '不一致'}")

    if not same:
        diff = list(difflib.unified_diff(local.splitlines(), upstream.splitlines(),
                                         "local", "upstream", lineterm="", n=0))
        changed = sum(1 for ln in diff if ln[:1] in "+-" and not ln.startswith(("+++", "---")))
        print(f"差异       : {changed} 行（+/-）")
        for ln in diff[:40]:
            print("   " + ln[:160])
        if len(diff) > 40:
            print(f"   …还有 {len(diff) - 40} 行")
        for marker in ("YG", "Little Code Sauce", "小码酱"):
            print(f"   标记 {marker!r}: 上游 {upstream.count(marker)} / 本地 {local.count(marker)}")

    if a.write:
        local_path.write_text(upstream_raw, encoding="utf-8", newline="\n")
        pins_path = plugin / "UPSTREAM.json"
        pins = json.loads(pins_path.read_text(encoding="utf-8")) if pins_path.exists() else {}
        up = pins.setdefault("upstream", {})
        up.update({
            "repo": a.repo,
            "branch": a.ref,
            "version": str(pkg.get("version") or ""),
            "asset_table_sha256": hashlib.sha256(asset).hexdigest(),
            "table_key_sha256": hashlib.sha256(key).hexdigest(),
        })
        pins["prompt"] = {"sha256": sha(upstream), "chars": len(upstream)}
        pins.setdefault("port", {})["plugin_version"] = str(pkg.get("version") or "")
        pins_path.write_text(json.dumps(pins, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n已写入 {local_path}")
        print(f"已更新 {pins_path}")
        print("记得同步改版本：plugin.yaml / dshpurge_config.PLUGIN_VERSION / __init__.__version__，再跑 local_test.py")
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
