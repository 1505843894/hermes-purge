#!/usr/bin/env bash
# dsh-purge for Hermes — 安装（Linux / macOS）
#
#   bash install.sh              # 安装到 $HERMES_HOME/plugins/dsh-purge 并写入 SOUL.md 托管块
#   HERMES_HOME=/opt/.hermes bash install.sh
#   bash install.sh --keep-legacy   # 保留旧版 hermes-purge 标记块（默认迁走并备份）
#
# 幂等：重复执行不会重复注入；SOUL.md 改动前备份到 $HERMES_HOME/dsh-purge/backups/。
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DEST="$HERMES_HOME/plugins/dsh-purge"
KEEP_LEGACY=0
for a in "$@"; do
  case "$a" in
    --keep-legacy) KEEP_LEGACY=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "未知参数: $a" >&2; exit 2 ;;
  esac
done

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

command -v hermes >/dev/null 2>&1 || die "PATH 上没有 hermes，先确认 Hermes 已安装"
[ -d "$HERMES_HOME" ] || die "未找到 HERMES_HOME: $HERMES_HOME"

say "Hermes 版本: $(hermes --version 2>/dev/null | head -1 || echo 未知)"
say "安装到     : $DEST"

mkdir -p "$HERMES_HOME/plugins"
if [ "$SRC" != "$DEST" ]; then
  [ -d "$DEST" ] && { mv "$DEST" "$DEST.bak.$(date +%Y%m%d-%H%M%S)"; echo "    旧目录已备份"; }
  mkdir -p "$DEST"
  tar -C "$SRC" -cf - . | tar -C "$DEST" -xf -
  echo "    已复制 $(find "$DEST" -type f | wc -l | tr -d ' ') 个文件"
fi

say "启用插件"
hermes plugins enable dsh-purge >/dev/null 2>&1 || true

say "写入 SOUL.md 托管块"
if [ "$KEEP_LEGACY" -eq 1 ]; then
  hermes dsh-purge install --keep-legacy
else
  hermes dsh-purge install
fi

say "静态自检"
hermes dsh-purge verify

cat <<'EOF'

生效方式：**新开一个会话**（提示词按会话冻结，旧会话不会回溯改）。
验证：bash verify.sh
卸载：bash uninstall.sh
EOF
