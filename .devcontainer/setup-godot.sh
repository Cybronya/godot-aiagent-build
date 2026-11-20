#!/usr/bin/env bash
# 在 devcontainer / GitHub Codespaces 内准备可跑测试的 Godot 环境。
#
# 做的事（全部在容器内，不改仓库内容）：
#   1. 装 Godot 官方 Linux x86_64 编辑器包（--headless 用），解压到 $HOME/.local/godot
#   2. 把 `godot` 放到 PATH —— 仓库里所有查找逻辑
#      (.ai/tools/run_tests.py、.ai/tools/validator/execution/env_paths.py、
#       .ai/tools/e2e/*_probe.py) 都有 shutil.which("godot"/"godot4") 兜底
#   3. 首次 `--headless --import` 生成 .godot/（gitignore 内），期间临时禁用
#      auto_start 的 godot_mcp 编辑器插件，结束后原样还原 project.godot
#
# 可用环境变量覆盖：
#   GODOT_VERSION=4.7-stable  GODOT_DIR=~/.local/godot  GODOT_URL=<自定义下载地址>
set -euo pipefail

GODOT_VERSION="${GODOT_VERSION:-4.7-stable}"
GODOT_DIR="${GODOT_DIR:-$HOME/.local/godot}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 项目约定（.ai/tools/validator/tests/test_env_paths.py E8b）：Godot 二进制与仓库同级，
# 而不是塞在 $HOME 下 —— 校验器断言「解析到的二进制目录 == 仓库父目录」。
PROJECT_PARENT="$(cd "$PROJECT_DIR/.." && pwd)"
if [ -w "$PROJECT_PARENT" ]; then
  FINAL_BIN="$PROJECT_PARENT/godot"
else
  FINAL_BIN="$HOME/.local/bin/godot"
fi

GODOT_URL="${GODOT_URL:-https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/Godot_v${GODOT_VERSION}_linux.x86_64.zip}"

log() { printf '[setup-godot] %s\n' "$*"; }

# ---------- 1. 系统依赖（Godot 编辑器二进制 + unzip） ----------
missing=()
for pkg in unzip libx11-6 libxcursor1 libxinerama1 libxrandr2 libxi6 \
           libgl1 libglu1-mesa libfontconfig1 libasound2; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if [ "${#missing[@]}" -gt 0 ]; then
  log "apt-get install: ${missing[*]}"
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "${missing[@]}"
fi

# ---------- 2. 下载并解压 Godot ----------
godot_bin="$GODOT_DIR/godot"
if [ -x "$FINAL_BIN" ]; then
  godot_bin="$FINAL_BIN"
  log "已存在: $("$godot_bin" --version || true)"
else
  mkdir -p "$GODOT_DIR"
  zip_path="$GODOT_DIR/godot.zip"
  log "下载 $GODOT_URL"
  if command -v curl >/dev/null; then
    curl -fL --retry 3 --connect-timeout 20 -o "$zip_path" "$GODOT_URL"
  else
    wget -q -O "$zip_path" "$GODOT_URL"
  fi
  unzip -o -q "$zip_path" -d "$GODOT_DIR"
  rm -f "$zip_path"
  extracted="$(find "$GODOT_DIR" -maxdepth 1 -type f -name 'Godot_v*linux*' ! -name '*.zip' | head -1)"
  if [ -z "$extracted" ]; then
    log "解压后找不到 Godot 二进制，检查 $GODOT_DIR" >&2
    exit 1
  fi
  mv -f "$extracted" "$godot_bin"
  chmod +x "$godot_bin"
  log "已安装: $("$godot_bin" --version)"
fi

# ---------- 2b. 放到仓库同级目录（项目约定，见 test_env_paths E8b） ----------
if [ "$FINAL_BIN" != "$godot_bin" ]; then
  install -m 755 "$godot_bin" "$FINAL_BIN"
  log "已放置: $FINAL_BIN"
fi

# ---------- 3. 放进 PATH ----------
if sudo -n true 2>/dev/null; then
  sudo ln -sf "$FINAL_BIN" /usr/local/bin/godot
  log "已链接 /usr/local/bin/godot -> $FINAL_BIN"
elif [ -w /usr/local/bin ]; then
  ln -sf "$FINAL_BIN" /usr/local/bin/godot
  log "已链接 /usr/local/bin/godot -> $FINAL_BIN"
else
  mkdir -p "$HOME/.local/bin"
  ln -sf "$FINAL_BIN" "$HOME/.local/bin/godot"
  if ! grep -qs 'HOME/.local/bin' "$HOME/.bashrc"; then
    printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.bashrc"
  fi
  log "已链接 $HOME/.local/bin/godot（如当前 shell 无此路径，先 source ~/.bashrc）"
fi

# ---------- 4. 首次导入资源（临时禁用 godot_mcp 编辑器插件） ----------
cd "$PROJECT_DIR"
if [ -f .godot/global_script_class_cache.cfg ]; then
  log "跳过导入：.godot/ 已存在"
else
  backup="$(mktemp)"
  cp project.godot "$backup"
  restore_project() { cp "$backup" project.godot; rm -f "$backup"; }
  trap restore_project EXIT
  python3 - <<'PY'
from pathlib import Path
p = Path("project.godot")
text = p.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
out, section = [], ""
for line in lines:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        section = stripped
    if section == "[editor_plugins]" and stripped.startswith("enabled="):
        # 只替换数组内容，保留原行尾（仓库里 project.godot 是 CRLF）
        line = line.replace(
            'PackedStringArray("res://addons/godot_mcp/plugin.cfg")',
            "PackedStringArray()")
    out.append(line)
p.write_text("".join(out), encoding="utf-8")
PY
  log "导入资源（首次可能几分钟）..."
  "$godot_bin" --headless --path "$PROJECT_DIR" --import || log "导入返回非 0（若只是插件告警可忽略，见上方输出）"
fi

log "完成。验证：godot --version ; python .ai/tools/run_tests.py --help"
