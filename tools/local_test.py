#!/usr/bin/env python3
"""本地离线验收：用假 PluginContext 走一遍 register()，再跑 CLI 自检。

    python tools/local_test.py [--plugin dsh-purge-plugin]

不碰真实 ~/.hermes：HERMES_HOME 指向临时目录。
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tempfile
from pathlib import Path


class FakeCtx:
    def __init__(self):
        self.sections = {}
        self.hooks = {}
        self.skills = {}
        self.cli = {}
        self.config = {}

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def register_system_prompt_section(self, sid, content, *, position="after_memory", max_chars=4000):
        if not (0 < max_chars <= 4000):
            raise ValueError("bad max_chars")
        if len(content) > max_chars:
            raise ValueError(f"section {sid} too long: {len(content)} > {max_chars}")
        self.sections[sid] = content
        return object()

    def register_hook(self, name, cb):
        self.hooks.setdefault(name, []).append(cb)
        return object()

    def register_skill(self, name, path, description=""):
        if ":" in name:
            raise ValueError("colon in skill name")
        self.skills[name] = (str(path), description)
        return object()

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.cli[name] = (setup_fn, handler_fn)
        return object()


def load_plugin(plugin_dir: Path):
    name = "dshpurge_plugin"
    spec = importlib.util.spec_from_file_location(
        name, str(plugin_dir / "__init__.py"), submodule_search_locations=[str(plugin_dir)]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", default="dsh-purge-plugin")
    a = ap.parse_args()
    plugin_dir = Path(a.plugin).resolve()

    tmp = Path(tempfile.mkdtemp(prefix="dshpurge-test-"))
    os.environ["HERMES_HOME"] = str(tmp)

    mod = load_plugin(plugin_dir)
    ctx = FakeCtx()
    mod.register(ctx)

    print("sections :", list(ctx.sections), [len(v) for v in ctx.sections.values()])
    print("hooks    :", {k: len(v) for k, v in ctx.hooks.items()})
    print("skills   :", len(ctx.skills))
    print("cli      :", list(ctx.cli))
    print("soul     :", (tmp / "SOUL.md").exists(), (tmp / "SOUL.md").stat().st_size if (tmp / "SOUL.md").exists() else 0)

    ok = True
    ok &= bool(ctx.sections)
    ok &= set(ctx.hooks) >= {"pre_llm_call", "post_llm_call", "on_session_start"}
    ok &= len(ctx.skills) >= 20
    ok &= "dsh-purge" in ctx.cli
    ok &= (tmp / "SOUL.md").exists()

    # 幂等：再跑一遍，SOUL.md 不应变化
    before = (tmp / "SOUL.md").read_bytes()
    ctx2 = FakeCtx()
    mod.register(ctx2)
    after = (tmp / "SOUL.md").read_bytes()
    idempotent = before == after
    print("idempotent:", idempotent)
    ok &= idempotent

    # SOUL 块唯一
    text = (tmp / "SOUL.md").read_text(encoding="utf-8")
    unique = text.count("<!-- dsh-purge:hermes:begin -->") == 1
    print("unique block:", unique)
    ok &= unique

    # 反拒答语义
    from importlib import import_module

    R = sys.modules["dshpurge_plugin.dshpurge_refusal"]
    ok &= R.looks_like_refusal("抱歉，我无法协助完成这个请求。")
    ok &= not R.looks_like_refusal("可以，按本地样本逆向流程：先复制到隔离目录。")
    R.note_response("s1", "抱歉，我无法协助。")
    inj = R.take_injection("s1")
    print("recover inject:", bool(inj), (inj or "")[:40])
    ok &= bool(inj)
    ok &= R.take_injection("s1") is None  # 已记账，不重复

    print("\nLOCAL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
