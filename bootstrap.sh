#!/usr/bin/env bash
# dsh-purge for Hermes — 远程一键安装（任意 VPS）
#
#   bash bootstrap.sh                       # 拉最新 tag，装到 $HERMES_HOME/plugins/dsh-purge，重启 gateway，自检
#   REF=main      bash bootstrap.sh         # 装 main 而不是 tag
#   TOKEN=ghp_xxx bash bootstrap.sh         # 私有仓库（也认 DSHPURGE_GITHUB_TOKEN / GITHUB_TOKEN / GH_TOKEN / gh auth token）
#   HERMES_HOME=/opt/.hermes bash bootstrap.sh
#   NO_RESTART=1  bash bootstrap.sh         # 只装不重启
#
# 幂等：重复跑就是升级；旧插件目录与 SOUL.md 都会先备份。
set -euo pipefail

REPO="${REPO:-1505843894/hermes-purge}"
REF="${REF:-latest}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DEST="$HERMES_HOME/plugins/dsh-purge"
NO_RESTART="${NO_RESTART:-0}"
TOKEN="${TOKEN:-${DSHPURGE_GITHUB_TOKEN:-${GITHUB_TOKEN:-${GH_TOKEN:-}}}}"

say()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m  !\033[0m %s\n' "$*"; }
die()  { printf '\033[31m  ✗\033[0m %s\n' "$*" >&2; exit 1; }

# ── 0. 前置 ────────────────────────────────────────────────────────────────
command -v hermes >/dev/null 2>&1 || die "PATH 上没有 hermes：先装 Hermes Agent 再来"
command -v curl   >/dev/null 2>&1 || die "缺 curl"
command -v tar    >/dev/null 2>&1 || die "缺 tar"
[ -d "$HERMES_HOME" ] || die "未找到 HERMES_HOME=$HERMES_HOME（Hermes 装过但没初始化？先跑一次 hermes）"

if [ -z "$TOKEN" ] && command -v gh >/dev/null 2>&1; then
  TOKEN="$(gh auth token 2>/dev/null || true)"
fi

say "目标：$DEST"
say "Hermes：$(hermes --version 2>/dev/null | head -1 || echo 未知版本)"

AUTH=()
[ -n "$TOKEN" ] && AUTH=(-H "Authorization: Bearer $TOKEN")

fetch() { curl -fsSL --retry 3 --retry-delay 2 "${AUTH[@]}" "$1"; }

# ── 1. 定版本 ──────────────────────────────────────────────────────────────
if [ "$REF" = "latest" ]; then
  TAGS="$(fetch "https://api.github.com/repos/$REPO/tags?per_page=100" 2>/dev/null \
          | grep -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/' || true)"
  if [ -n "$TAGS" ]; then
    REF="$(printf '%s\n' "$TAGS" | sed 's/^v//' | sort -V | tail -1)"
    REF="v$REF"
  else
    [ -n "$TOKEN" ] || warn "拿不到 tag（私有仓库需要 TOKEN），退回 main"
    REF="main"
  fi
fi
say "版本：$REF"

URL="https://codeload.github.com/$REPO/tar.gz/refs/tags/$REF"
case "$REF" in main|master) URL="https://codeload.github.com/$REPO/tar.gz/refs/heads/$REF" ;; esac

# ── 2. 下载解包 ────────────────────────────────────────────────────────────
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
say "下载 $URL"
fetch "$URL" | tar -xzf - -C "$WORK" || die "下载/解包失败（私有仓库忘了给 TOKEN？）"
SRC="$(find "$WORK" -maxdepth 2 -type d -name dsh-purge-plugin | head -1)"
[ -n "$SRC" ] || die "包里没有 dsh-purge-plugin/（REF=$REF 不对？）"
ok "解包完成：$(find "$SRC" -type f | wc -l | tr -d ' ') 个文件"

# ── 3. 覆盖安装（先备份）───────────────────────────────────────────────────
mkdir -p "$HERMES_HOME/plugins"
if [ -d "$DEST" ]; then
  BAK="$DEST.bak.$(date +%Y%m%d-%H%M%S)"
  mv "$DEST" "$BAK"
  ok "旧插件目录已备份：$BAK"
fi
mkdir -p "$DEST"
tar -C "$SRC" -cf - . | tar -C "$DEST" -xf -
chmod +x "$DEST"/*.sh

# ── 4. 安装：写 SOUL 托管块 + 启用插件 ────────────────────────────────────
say "写入 SOUL.md 托管块"
"$DEST/install.sh" >/tmp/dshpurge-install.log 2>&1 || { tail -20 /tmp/dshpurge-install.log; die "install.sh 失败"; }
ok "$(grep -c '^\[ok\]' /tmp/dshpurge-install.log || true) 项静态自检通过"

# ── 5. 重启 Hermes ────────────────────────────────────────────────────────
# 注意：不能用 `hermes gateway status | grep -q` —— grep -q 提前退出会把 hermes 打成 SIGPIPE，
# 在 pipefail 下整条管道判成失败（第一版就踩了这个坑）。改成先取文本再匹配。
GWOUT="$(hermes gateway status 2>&1 || true)"
GW=0
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user is-active --quiet hermes-gateway.service 2>/dev/null && GW=1
fi
if [ "$GW" = "0" ] && pgrep -f "gateway run" >/dev/null 2>&1; then GW=2; fi
if [ "$GW" = "0" ]; then
  case "$GWOUT" in *active*|*running*) GW=3 ;; esac
fi

if [ "$NO_RESTART" = "1" ]; then
  warn "NO_RESTART=1：跳过重启（新开会话才生效）"
elif [ "$GW" != "0" ]; then
  say "重启 Hermes gateway（模式 $GW）"
  if hermes gateway restart >/tmp/dshpurge-restart.log 2>&1; then
    ok "gateway 已重启"
  else
    warn "hermes gateway restart 失败，日志尾部："
    tail -5 /tmp/dshpurge-restart.log || true
  fi
else
  warn "没检测到运行中的 gateway：跳过重启（只用 CLI 不需要）"
fi
warn "已在跑着的交互式 hermes 会话不会自己加载新插件：重开一个会话（gateway 侧发 /new）"

# ── 6. 自检 ────────────────────────────────────────────────────────────────
say "端到端自检"
if bash "$DEST/verify.sh" --quiet 2>&1 | tail -8; then
  ok "安装完成：$(hermes dsh-purge status 2>/dev/null | grep '版本' | head -1)"
  echo
  echo "  常用：hermes dsh-purge status | verify | check-update | update"
  echo "  升级：hermes dsh-purge update     # 或重跑本脚本"
else
  die "自检未通过，见上面输出"
fi
