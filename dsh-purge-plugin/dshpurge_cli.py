"""`hermes dsh-purge …` 管理命令。

    hermes dsh-purge status      # 托管块 / 内核段 / 技能 / 反拒答状态
    hermes dsh-purge install     # 写入或刷新 SOUL.md 托管块
    hermes dsh-purge uninstall   # 摘掉托管块（其余 SOUL 内容保留）
    hermes dsh-purge prompt      # 打印完整提示词（--kernel 打印内核段）
    hermes dsh-purge skills      # 列出随插件挂载的技能
    hermes dsh-purge verify      # 静态自检，失败退出码 1
    hermes dsh-purge recover --reset
"""
from __future__ import annotations

import json
import sys

from . import dshpurge_config as C
from . import dshpurge_prompt as P
from . import dshpurge_refusal as R
from . import dshpurge_skills as S
from . import dshpurge_soul as Soul

_out = print


def setup_args(parser) -> None:
    sub = parser.add_subparsers(dest="sub")
    for name, help_text in (
        ("status", "显示托管块、内核段、技能与反拒答状态"),
        ("install", "写入或刷新 SOUL.md 托管块"),
        ("uninstall", "摘掉 SOUL.md 托管块"),
        ("prompt", "打印完整提示词"),
        ("skills", "列出随插件挂载的红队技能"),
        ("verify", "静态自检"),
        ("check-update", "检查移植仓库与上游 dsh-purge 是否有新版"),
        ("update", "升级到移植仓库最新 tag（自动备份 + 刷新 SOUL 托管块）"),
        ("recover", "反拒答状态管理"),
    ):
        p = sub.add_parser(name, help=help_text)
        if name == "install":
            p.add_argument("--keep-legacy", action="store_true",
                           help="保留旧版 hermes-purge 标记块（默认迁走）")
            p.add_argument("--home", default=None, help="覆盖 HERMES_HOME")
        elif name == "uninstall":
            p.add_argument("--home", default=None, help="覆盖 HERMES_HOME")
        elif name == "prompt":
            p.add_argument("--kernel", action="store_true", help="只打印内核段")
        elif name == "recover":
            p.add_argument("--reset", action="store_true", help="清空反拒答状态")
            p.add_argument("--session", default=None, help="只清某个 session")
        elif name == "check-update":
            p.add_argument("--json", action="store_true", help="输出机器可读 JSON")
        elif name == "update":
            p.add_argument("--check", action="store_true", help="只检查，不升级")
            p.add_argument("--force", action="store_true", help="即使已是最新也重装一遍")


def _home(args):
    from pathlib import Path

    raw = getattr(args, "home", None)
    return Path(raw).expanduser() if raw else None


def _cmd_status(home=None) -> int:
    st = Soul.status(home)
    data = R._load(home)
    sessions = data.get("sessions") or {}
    print("dsh-purge · hermes plugin")
    print(f"  版本        : {C.PLUGIN_VERSION}")
    print(f"  HERMES_HOME : {C.hermes_home()}")
    print(f"  SOUL.md     : {st['path']}")
    print(f"    存在={st['exists']} 字符={st['chars']} 托管块={st['block_present']}"
          f"({st['block_chars']} 字符) 旧块={st['legacy_present']}")
    print(f"  内核段      : id={C.SECTION_ID} {P.kernel_chars()} 字符（上限 {C.SECTION_MAX_CHARS}）")
    print(f"  完整提示词  : {P.prompt_chars()} 字符")
    print(f"  技能        : {len(S.skill_files())} 个（命名空间 {C.PLUGIN_NAME}:<name>）")
    print(f"  反拒答      : max_inject={R._max_injects()} enabled={R._enabled()} "
          f"挂起会话={sum(1 for v in sessions.values() if v.get('pending'))}")
    return 0


def _cmd_install(args) -> int:
    prompt = P.full_prompt()
    if not prompt:
        print("提示词文件缺失：prompt/default-prompt.md", file=sys.stderr)
        return 2
    res = Soul.ensure(prompt, _home(args), strip_legacy_blocks=not args.keep_legacy)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def _cmd_uninstall(args) -> int:
    print(json.dumps(Soul.remove(_home(args)), ensure_ascii=False, indent=2))
    return 0


def _cmd_prompt(args) -> int:
    text = P.kernel() if getattr(args, "kernel", False) else P.full_prompt()
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _cmd_skills() -> int:
    for path in S.skill_files():
        print(f"{C.PLUGIN_NAME}:{path.parent.name}\t{S._description(path)}")
    return 0


def _cmd_recover(args) -> int:
    if args.reset:
        R.reset(args.session)
        print("反拒答状态已清空" if args.session is None else f"已清空会话 {args.session}")
        return 0
    print(json.dumps(R._load(), ensure_ascii=False, indent=2))
    return 0


def _cmd_verify(home=None) -> int:
    ok = True
    st = Soul.status(home)
    checks = [
        ("完整提示词存在", P.prompt_chars() > 5000, f"{P.prompt_chars()} 字符"),
        ("内核段未超限", 0 < P.kernel_chars() <= C.SECTION_MAX_CHARS, f"{P.kernel_chars()} 字符"),
        ("内核段含身份", "小码酱" in P.kernel(), ""),
        ("完整提示词含身份", "Little Code Sauce" in P.full_prompt(), ""),
        ("SOUL 托管块已装", st["block_present"], st["path"]),
        ("SOUL 无旧版残留块", not st["legacy_present"], ""),
        ("技能已生成", len(S.skill_files()) >= 20, f"{len(S.skill_files())} 个"),
        ("反拒答正则可用", R.looks_like_refusal("抱歉，我无法协助完成这个请求"), ""),
        ("反拒答不误伤", not R.looks_like_refusal("可以，按本地样本逆向流程：先复制到隔离目录。"), ""),
    ]
    for label, passed, detail in checks:
        ok = ok and bool(passed)
        print(f"[{'ok' if passed else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    print("\n结果：" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def _cmd_check_update(args) -> int:
    from . import dshpurge_update as U

    try:
        info = U.check()
    except Exception as exc:  # noqa: BLE001
        print(f"更新检查失败: {exc}", file=sys.stderr)
        return 2
    if getattr(args, "json", False):
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(U.format_check(info))
    return 0 if info.get("verdict") != "unknown" else 2


def _cmd_update(args) -> int:
    from . import dshpurge_update as U

    if getattr(args, "check", False):
        return _cmd_check_update(args)
    try:
        res = U.apply(force=bool(getattr(args, "force", False)))
    except Exception as exc:  # noqa: BLE001
        print(f"升级失败: {exc}", file=sys.stderr)
        return 2
    if res.get("action") == "up-to-date":
        print(U.format_check(res.get("check") or {}))
        print("\n无需升级（--force 可强制重装）")
        return 0
    print(json.dumps({k: v for k, v in res.items() if k != "check"}, ensure_ascii=False, indent=2))
    return 0


def dispatch(args) -> int:
    sub = getattr(args, "sub", None)
    if sub in (None, "status"):
        return _cmd_status(_home(args) if sub == "status" else None)
    if sub == "install":
        return _cmd_install(args)
    if sub == "uninstall":
        return _cmd_uninstall(args)
    if sub == "prompt":
        return _cmd_prompt(args)
    if sub == "skills":
        return _cmd_skills()
    if sub == "verify":
        return _cmd_verify()
    if sub == "recover":
        return _cmd_recover(args)
    if sub == "check-update":
        return _cmd_check_update(args)
    if sub == "update":
        return _cmd_update(args)
    print("用法: hermes dsh-purge {status|install|uninstall|prompt|skills|verify|recover}")
    return 2


def cli_main(args) -> int:
    return dispatch(args)
