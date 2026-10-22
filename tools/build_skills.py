#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 dsh-purge 的 23 个红队技能转成 Hermes 插件可注册的 SKILL.md。

    python tools/build_skills.py --src <dsh-purge 源码目录> --out dsh-purge-plugin/skills

只做格式适配：frontmatter 补 Hermes 规范字段、正文标题降一级、路径重映射
(~/.dsh/redteam -> ~/.hermes/redteam)。正文语义与命令原文不动。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

DESC_MAX = 60
AUTHOR = "YuJunZhiXue (dsh-purge), Hermes plugin port"
VERSION = "1.6.45"
FM = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)


def parse_frontmatter(text: str):
    m = FM.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, text[m.end():]


def clamp(desc: str) -> str:
    desc = (desc or "Red-team skill.").strip().replace("\n", " ")
    if len(desc) > DESC_MAX:
        desc = desc[: DESC_MAX - 1].rstrip("。.,，、 ")
    return desc if desc.endswith(("。", ".")) else desc + "。"


def rewrite(body: str) -> str:
    body = body.replace("~/.dsh/redteam", "~/.hermes/redteam")
    body = body.replace("$DSH_HOME/redteam", "$HERMES_HOME/redteam")
    body = body.replace("$DSH_HOME", "$HERMES_HOME")
    return body


def demote(body: str) -> str:
    out = []
    for line in body.splitlines():
        if re.match(r"^#\s+\S", line):
            out.append("#" + line)
        elif line.startswith("##"):
            out.append("#" + line)
        else:
            out.append(line)
    return "\n".join(out)


def build_one(src: Path, out_root: Path) -> Path:
    raw = src.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    name = src.stem
    role = fm.get("role", "general").strip("[]\"' ")
    when = fm.get("whenToUse", "").strip()
    head = [
        "---",
        f"name: {name}",
        f'description: "{clamp(fm.get("description", ""))}"',
        f"version: {VERSION}",
        f"author: {AUTHOR}",
        "license: MIT",
        "platforms: [linux, macos]",
        "metadata:",
        "  hermes:",
        f"    tags: [redteam, {role or 'general'}, security]",
        "    category: security",
        "    related_skills: []",
        "---",
        "",
        f"# {name}",
        "",
        "移植自 dsh-purge 红队技能库（原文照录，仅补齐 Hermes 头部元数据与路径）。",
        "",
    ]
    if when:
        head += ["## When to Use", "", when, ""]
    head += ["## Procedure", ""]
    dst = out_root / name / "SKILL.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(head) + "\n" + demote(rewrite(body)).lstrip("\n") + "\n", encoding="utf-8")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    src = Path(a.src) / "skills" / "redteam"
    out = Path(a.out)
    files = sorted(src.glob("*.md"))
    if not files:
        raise SystemExit(f"no skills under {src}")
    for f in files:
        print(" ", build_one(f, out).relative_to(out.parent))
    print(f"共 {len(files)} 个技能 -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
