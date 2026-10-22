#!/usr/bin/env bash
# dsh-purge for Hermes — 卸载
#
#   bash uninstall.sh           # 摘掉 SOUL.md 托管块 + 删除插件目录
#   bash uninstall.sh --keep    # 只摘托管块，插件目录留着（下次启动会重新写）
#
# 备份不会被删：$HERMES_HOME/dsh-purge/backups/SOUL.md.*.bak
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DEST="$HERMES_HOME/plugins/dsh-purge"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }

say "摘掉 SOUL.md 托管块"
hermes dsh-purge uninstall || echo "    （插件已不可用，改用直接清理）"

if [ "$KEEP" -eq 0 ]; then
  say "删除插件目录 $DEST"
  rm -rf "$DEST"
fi

say "剩余备份"
ls -1 "$HERMES_HOME/dsh-purge/backups" 2>/dev/null | tail -5 || echo "    （无）"
echo "完成。新会话生效。"
