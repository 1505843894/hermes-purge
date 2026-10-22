"""dsh-purge for Hermes — 插件入口。

dsh-purge 原本是 DeepSeek Harness 的 Cordis 插件，靠改写宿主 systemPrompt 段实现破甲。
Hermes 是另一套宿主：这里把它落到 Hermes 原生的四个扩展点上，全部是公开契约，
不改任何核心文件：

  1. register_system_prompt_section()  内核段（≤4000 字符）→ 每个新会话的 system prompt
  2. SOUL.md 托管块                    完整提示词（2 万多字符）→ 身份槽 #1（唯一能承载全量
                                       用户可控文本的通道；插件段有 8000 字符总预算）
  3. pre_llm_call / post_llm_call      反拒答：判定 + 下一轮注入纠正指令
  4. register_skill() / register_cli_command()  23 个红队技能 + `hermes dsh-purge …`

幂等：重复加载不会重复注入；SOUL.md 每次改动前备份到
``$HERMES_HOME/dsh-purge/backups/``。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__version__ = "1.4.2"


def _install_soul(reason: str) -> None:
    from . import dshpurge_prompt as P
    from . import dshpurge_soul as Soul

    prompt = P.full_prompt()
    if not prompt:
        logger.warning("dsh-purge: prompt/default-prompt.md 缺失，跳过 SOUL.md 托管块")
        return
    res = Soul.ensure(prompt)
    if res.get("action") != "unchanged":
        logger.info("dsh-purge: SOUL.md %s (%s, %s 字符, backup=%s)",
                    res.get("action"), reason, res.get("chars"), res.get("backup"))


def _on_pre_llm_call(**kwargs):
    from . import dshpurge_refusal as R

    text = R.take_injection(kwargs.get("session_id") or "")
    return {"context": text} if text else None


def _on_post_llm_call(**kwargs):
    from . import dshpurge_refusal as R

    R.note_response(kwargs.get("session_id") or "", kwargs.get("assistant_response") or "")
    return None


def _on_session_start(**kwargs):
    # 会话开始时自愈一次：SOUL.md 被别的工具覆盖 / 被删也能立刻补回来
    try:
        _install_soul("session-start")
    except Exception as exc:  # noqa: BLE001
        logger.warning("dsh-purge: session-start SOUL 自愈失败: %s", exc)
    return None


def register(ctx) -> None:
    """PluginContext 入口：全部注册都各自兜住异常，单项失败不影响其余能力。"""
    from . import dshpurge_config as C
    from . import dshpurge_prompt as P
    from . import dshpurge_skills as S
    from . import dshpurge_cli as CLI

    auto_soul = True
    try:
        auto_soul = bool(ctx.get_config("auto_soul_merge", True))
    except Exception:
        auto_soul = True

    if auto_soul:
        try:
            _install_soul("plugin-load")
        except Exception as exc:  # noqa: BLE001
            logger.warning("dsh-purge: 加载期写入 SOUL.md 失败: %s", exc)

    try:
        content = P.kernel()
        if content:
            ctx.register_system_prompt_section(
                C.SECTION_ID, content, position="after_memory", max_chars=C.SECTION_MAX_CHARS
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("dsh-purge: 系统提示段注册失败: %s", exc)

    try:
        ctx.register_hook("pre_llm_call", _on_pre_llm_call)
        ctx.register_hook("post_llm_call", _on_post_llm_call)
        ctx.register_hook("on_session_start", _on_session_start)
    except Exception as exc:  # noqa: BLE001
        logger.warning("dsh-purge: 钩子注册失败: %s", exc)

    try:
        names = S.register_all(ctx)
        if names:
            logger.info("dsh-purge: 已挂载 %d 个红队技能", len(names))
    except Exception as exc:  # noqa: BLE001
        logger.warning("dsh-purge: 技能注册失败: %s", exc)

    try:
        ctx.register_cli_command(
            "dsh-purge",
            "dsh-purge 破甲：状态 / 安装 / 卸载 / 提示词 / 技能 / 自检",
            CLI.setup_args,
            CLI.dispatch,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("dsh-purge: CLI 命令注册失败: %s", exc)
