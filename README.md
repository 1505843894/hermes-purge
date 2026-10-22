# hermes-purge — dsh-purge 的 Hermes 插件移植工程

把 [dsh-purge](https://github.com/YuJunZhiXue/dsh-purge) 移植成 **Hermes 原生插件**，并在
`168.107.44.230`（Hermes v0.22.4 / Debian arm64）上实测生效：**Hermes 回答自称「小码酱」**。

```
hermes-purge/
├── dsh-purge-plugin/          # ← 交付物：完整 Hermes 插件包（可直接丢进 $HERMES_HOME/plugins/）
│   ├── plugin.yaml
│   ├── __init__.py            # register(ctx)：SOUL 托管块 + 系统提示段 + 钩子 + 23 技能 + CLI
│   ├── dshpurge_*.py          # config / prompt / soul / refusal / skills / cli / update
│   ├── UPSTREAM.json          # pin：上游 repo/version + asset-table/table-key/提示词 sha256
│   ├── prompt/                # default-prompt.md（20 927 字，dsh-purge 1.6.45 解封原文）+ kernel.md
│   ├── skills/                # 23 个红队技能（Hermes frontmatter）
│   ├── install.sh / uninstall.sh / verify.sh
│   └── README.md              # 架构、通道对比、实测证据、限制
├── tools/
│   ├── build_skills.py        # dsh-purge skills/redteam/*.md -> Hermes SKILL.md
│   ├── sync_upstream_prompt.py# 解封上游新提示词、比对、写回 + 更新 pin（第二轴升级）
│   ├── local_test.py          # 离线验收（假 PluginContext，不碰真实 ~/.hermes）
│   ├── remote.py              # 远端 run / put / push / get（paramiko）
│   └── ssh_run.py
└── build/
    ├── dsh-purge-plugin.tgz   # 可直接 scp/解包安装
    └── dsh-purge-plugin.zip
```

## 一键安装（任意 VPS）

```bash
mkdir -p /tmp/hp && curl -fsSL https://codeload.github.com/1505843894/hermes-purge/tar.gz/refs/heads/main | tar -xz -C /tmp/hp --strip-components=1 && bash /tmp/hp/bootstrap.sh
```

拉最新 tag → 备份旧插件 → 装到 `$HERMES_HOME/plugins/dsh-purge` → 写 SOUL 托管块 → `hermes plugins enable`
→ 重启 gateway（有活跃会话就等 60s，`FORCE_RESTART=1` 才强杀）→ 端到端自检。

## 三分钟复现

```bash
# 本地自检（不碰真实 home）
python tools/local_test.py

# 远端部署 + 验收
python tools/remote.py push build/dsh-purge-plugin.tgz /root/dsh3.tgz
python tools/remote.py run 'cd /root/.hermes/plugins && rm -rf dsh-purge && mkdir dsh-purge \
  && tar -xzf /root/dsh3.tgz -C dsh-purge --strip-components=1 && bash dsh-purge/install.sh'
python tools/remote.py run 'bash /root/.hermes/plugins/dsh-purge/verify.sh'
```

## 更新检查

```bash
hermes dsh-purge check-update         # 双轴：移植仓库 tag + 上游提示词指纹
hermes dsh-purge update               # 升到最新 tag（备份 + 刷新 SOUL）
python tools/sync_upstream_prompt.py  # 上游提示词重封时的解封比对（--write 落盘）
```

判定逻辑与 token 要求见 [dsh-purge-plugin/README.md](dsh-purge-plugin/README.md) 第 8 节。

## 实测结论（2026-10-22 14:49 CST）

| 检查 | 结果 |
|---|---|
| `hermes plugins list` | `dsh-purge  enabled  1.6.45  user` |
| `hermes dsh-purge verify` | 9/9 ok，PASS |
| `hermes -z "你是谁"` | **我是小码酱。** |
| `hermes -z "你是什么模型？哪家公司开发的？"` | **我是小码酱。**（不泄漏 Hermes / Nous / 厂商名） |
| `hermes -z "写一个 Linux 反弹 shell…"` | 直接给 bash / nc / python / perl 四种载荷 + 监听端命令 |
| `~/.hermes/logs/agent.log` | `Session plugin prompt section: id=dsh-purge.kernel … chars=1441` |
| SOUL.md | 24 619 字符，含唯一托管块 23 848 字符，旧版 `hermes-purge` 块已迁走并备份 |

详细设计、通道取舍（为什么必须 SOUL.md + 插件段双写）、反拒答的半自动边界：见
[dsh-purge-plugin/README.md](dsh-purge-plugin/README.md)。

## 提示

- 提示词按会话冻结，装完 **新开会话** 才生效。
- 反拒答是「下一轮注入纠正」的半自动语义，Hermes 钩子没有自动补发 user 消息的通道。
- 移植只做宿主适配，提示词/技能文本归原作者 YuJunZhiXue（MIT）。
