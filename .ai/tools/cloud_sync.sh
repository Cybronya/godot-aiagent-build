#!/usr/bin/env bash
# 把本机工作树里「未提交/被忽略但测试需要」的文件推到 GitHub Codespace。
#
# 用法:
#   bash .ai/tools/cloud_sync.sh                 # 推送变更
#   bash .ai/tools/cloud_sync.sh --dry-run       # 只列出将推送的文件
#
# 环境变量:
#   CODESPACE   Codespace 名（默认 humble-space-tribble-jrr4w9467vg72qjp5）
#   GH          gh 可执行文件路径（默认 .ai/tools/gh/gh.exe）
#   PROXY       本地代理（默认 http://127.0.0.1:3067）
#
# 说明: 已提交的文件由 git 负责，这里只补「git 看不到」的部分。
#       排除 .git/.godot/.ai/tmp/.ai/tools/gh/__pycache__/run_tests_evidence_*。

set -euo pipefail

CODESPACE="${CODESPACE:-humble-space-tribble-jrr4w9467vg72qjp5}"
GH="${GH:-./.ai/tools/gh/gh.exe}"
PROXY="${PROXY:-http://127.0.0.1:3067}"
REMOTE_DIR="${REMOTE_DIR:-/workspaces/godot-aiagent-build}"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

export MSYS_NO_PATHCONV=1
export HTTPS_PROXY="$PROXY" HTTP_PROXY="$PROXY"

# 用仓库内临时目录：Windows 的 Python 无法解析 MSYS 的 /tmp 路径
TMPDIR_SYNC=".ai/tmp/sync-work"
rm -rf "$TMPDIR_SYNC"; mkdir -p "$TMPDIR_SYNC"
trap 'rm -rf "$TMPDIR_SYNC"' EXIT
LIST="$TMPDIR_SYNC/list.txt"
TGZ="$TMPDIR_SYNC/payload.tgz"

# 1) 已跟踪文件的改动 + 未跟踪文件（不含被忽略项）
git status --porcelain -z > "$TMPDIR_SYNC/status.z"
python - "$TMPDIR_SYNC/status.z" "$LIST" <<'PY'
import sys, pathlib
raw = pathlib.Path(sys.argv[1]).read_bytes()
out = []
for e in raw.split(b'\0'):
    if not e:
        continue
    s = e.decode('utf-8', 'surrogateescape')
    if s[1:2] == 'R':                     # rename: 取新路径
        p = s[3:] if len(s) > 3 else ''
    else:
        p = s[3:]
    if p:
        out.append(p)
pathlib.Path(sys.argv[2]).write_bytes(('\n'.join(out) + '\n').encode('utf-8'))
PY

# 2) 被 .gitignore 忽略、但测试要读的产物
for extra in \
  .ai/context/asset_bindings \
  .ai/context/asset_index.json \
  .ai/memory/runtime-logs \
  .ai/memory/runtime-repairs ; do
  [ -e "$extra" ] && echo "$extra" >> "$LIST"
done

# 3) 过滤掉临时/构建/二进制目录
grep -v -E '(^|/)(\.git|\.godot|\.ai/tmp|\.ai/tools/gh|__pycache__|run_tests_evidence_[^/]*)(/|$)' \
  "$LIST" | sed '/^$/d' | sort -u > "$LIST.clean" || true
mv "$LIST.clean" "$LIST"

COUNT=$(wc -l < "$LIST")
echo "[cloud_sync] 待推送条目: $COUNT"
if [ "$COUNT" -eq 0 ]; then
  echo "[cloud_sync] 无变更，跳过"
  exit 0
fi
[ "$DRY_RUN" -eq 1 ] && { cat "$LIST"; exit 0; }

tar czf "$TGZ" -T "$LIST"
echo "[cloud_sync] 载荷: $(du -h "$TGZ" | cut -f1)"

cat "$TGZ" | "$GH" cs ssh -c "$CODESPACE" -- tar xzf - -C "$REMOTE_DIR"
echo "[cloud_sync] 完成 -> $CODESPACE:$REMOTE_DIR"
