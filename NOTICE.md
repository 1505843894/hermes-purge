# 来源与署名 / Origin and attribution

本项目是 **[YuJunZhiXue/dsh-purge](https://github.com/YuJunZhiXue/dsh-purge)** 的 **宿主移植**（port），
不是上游官方发布，也不是上游的分支合并。

| 项 | 内容 |
| --- | --- |
| 原项目 | dsh-purge — DeepSeek Harness 网络安全红队评测与「破甲」插件 |
| 原作者 | **小杨**（GitHub: [@YuJunZhiXue](https://github.com/YuJunZhiXue)） |
| 上游仓库 | https://github.com/kingcharleslzy-ai/dsh-purge（原作者 小杨 [@YuJunZhiXue](https://github.com/YuJunZhiXue) 的同名项目续作） |
| 上游许可证 | MIT，`Copyright (c) 2026 小杨` |
| 被移植版本 | dsh-purge **1.6.45**（commit `000b75e`，上游 [kingcharleslzy-ai/dsh-purge](https://github.com/kingcharleslzy-ai/dsh-purge)） |
| 本仓库 | Hermes Agent 插件移植（`~/.hermes/plugins/dsh-purge`），维护者见提交记录 |

上游 README 要求：**借用本项目的名称、思路、代码或提示词，必须署名并写明来源仓库**。
本仓库保留原作者署名、上游链接与原始 MIT 许可证文本（[LICENSE](LICENSE)）；这是使用条件，不是可选项。

---

## 本仓库改了什么 / What this port changes

**只做宿主适配，不改提示词与技能正文的语义。**

| 移植项 | 上游（DSH） | 本仓库（Hermes） |
| --- | --- | --- |
| 提示词注入 | 改写 Cordis `systemPrompt` 段 + `$DSH_HOME/prompt-inject.md` | ① `ctx.register_system_prompt_section("dsh-purge.kernel")` ② `SOUL.md` 托管块（完整 20 927 字） |
| 默认提示词 | `lib/asset-table.js` 里 `sealSlot()` 加密分片 | 用同仓 `lib/table-read.js::openSlot()` 解封后**原文照录**，仅剥离 DSH 专用的 `<|im_start|>system:<project_instructions>` 信封 |
| 23 个红队技能 | `$DSH_HOME/skills/redteam/` | `ctx.register_skill()` 只读挂载为 `dsh-purge:<name>`，frontmatter 按 Hermes 规范重写，正文原文 |
| 反拒答 | 监听宿主事件后补发 user 消息（全自动） | `post_llm_call` 判定 + `pre_llm_call` 下一轮注入（半自动；Hermes 钩子没有补发通道） |
| 管理面 | 插件设置界面 | `hermes dsh-purge status/install/uninstall/prompt/skills/verify/recover` |

加密方案与解封流程来自上游源码（`lib/table-key.js`：AES-256-GCM，密钥 = `sha256(MIX+MASK)`，明文先 deflate），
本仓库不分发加密表，只分发解封后的明文提示词，并保留上游版权声明。

## 使用边界

沿用上游约定：仅供**受控评测、授权演练、自有资产测试**。技能里出现的扫描器/隧道/凭据攻击条目自带限速与最小间隔，
但使用边界由使用者自负。
