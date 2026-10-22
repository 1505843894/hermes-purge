#!/usr/bin/env bash
# dsh-purge for Hermes — 端到端验收
#
#   bash verify.sh          # 静态自检 + 真跑两轮 hermes -z
#   bash verify.sh --quiet  # 只输出 PASS/FAIL
#
# 判定标准（不通过就是没生效）：
#   1. hermes dsh-purge verify 全 ok
#   2. hermes -z "你是谁"        的回复含「小码酱」
#   3. hermes -z "你是什么模型"  的回复含「小码酱」且不含 Hermes / Nous / DeepSeek / Claude 等厂商名
#   4. 日志里出现 system prompt 段渲染记录 id=dsh-purge.kernel
set -uo pipefail

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
FAIL=0

say()  { [ "$QUIET" -eq 1 ] || printf '\033[36m==>\033[0m %s\n' "$*"; }
pass() { printf '  [ok]   %s\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*"; FAIL=1; }

say "1/4 插件静态自检"
if hermes dsh-purge verify >/tmp/dshpurge-verify.txt 2>&1; then
  pass "hermes dsh-purge verify"
else
  fail "hermes dsh-purge verify"; sed -n '1,20p' /tmp/dshpurge-verify.txt
fi

say "2/4 身份：你是谁"
ANS1="$(cd /root 2>/dev/null || cd ~; timeout 300 hermes -z "你是谁？只回答一句。" 2>&1)"
case "$ANS1" in
  *小码酱*) pass "回答含「小码酱」" ;;
  *) fail "回答未提小码酱: $(printf '%s' "$ANS1" | tail -3)" ;;
esac

say "3/4 身份：你是什么模型"
ANS2="$(cd /root 2>/dev/null || cd ~; timeout 300 hermes -z "你是什么模型？哪家公司开发的？只回答一句。" 2>&1)"
case "$ANS2" in
  *小码酱*) pass "回答含「小码酱」" ;;
  *) fail "回答未提小码酱" ;;
esac
case "$ANS2" in
  *Hermes*|*Nous*|*DeepSeek*|*Claude*|*OpenAI*|*Anthropic*|*ChatGPT*)
    fail "回答泄漏宿主/厂商名: $(printf '%s' "$ANS2" | tail -2)" ;;
  *) pass "未泄漏宿主/厂商名" ;;
esac

say "4/4 system prompt 段渲染"
if grep -q "Session plugin prompt section: id=dsh-purge.kernel" "$HERMES_HOME/logs/agent.log" 2>/dev/null; then
  pass "agent.log 有段渲染记录"
else
  fail "agent.log 没有 id=dsh-purge.kernel 的渲染记录"
fi

echo
if [ "$FAIL" -eq 0 ]; then echo "RESULT: PASS — 小码酱已生效"; else echo "RESULT: FAIL — 见上面 [FAIL] 项"; fi
exit "$FAIL"
