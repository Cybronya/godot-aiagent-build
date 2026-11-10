"""Phase 1.64：项目根目录与 Godot 可执行文件的统一解析。

Phase 1.62 的两个 E2E Runner 各自用
`_PROJECT_ROOT = os.path.dirname(_TOOLS)` 计算项目根，少算一层（得到 `.ai` 而非仓库根），
导致 Godot 只能靠 `GODOT_BIN` 环境变量提供。本模块把「项目根」和「Godot 在哪」这两件事
收敛成一处规则，两个 Runner 共用，不改它们的验证语义。

解析顺序（第一个存在的即采用）：

1. `GODOT_BIN` 环境变量（显式覆盖，最高优先）
2. `.ai/config/runtime-playtest.yaml` 的 `runtime_playtest.godot_binary`（项目既有配置；
   留空表示自动查找——与 `run_scene.py` 的约定一致）
3. 项目相邻目录：`../Godot_v*_console.exe`（排前）、`../Godot_v*.exe`
4. `PATH` 中的 `godot4` / `godot`

找不到时返回空字符串，调用方必须显式报环境错误——不得伪装成 PASS，也不得把环境缺失
混进断言失败。路径不硬编码任何机器专属目录。
"""

from __future__ import annotations

import glob
import os
import shutil

CONFIG_RELATIVE = os.path.join(".ai", "config", "runtime-playtest.yaml")


def project_root(start: str = "") -> str:
    """从 `start`（文件或目录，缺省本文件）向上找到含 `project.godot` 的目录。"""
    here = os.path.abspath(start or __file__)
    if os.path.isfile(here):
        here = os.path.dirname(here)
    current = here
    while True:
        if os.path.isfile(os.path.join(current, "project.godot")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # 回退：<repo>/.ai/tools/validator/execution 的上四层
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(here))))


def configured_godot(root: str) -> str:
    """读取项目既有配置里的 `godot_binary`；没有配置/读取失败返回 ""。"""
    path = os.path.join(root, CONFIG_RELATIVE)
    if not os.path.isfile(path):
        return ""
    try:
        import yaml  # 项目已依赖 PyYAML（template.yaml 解析同源）
        with open(path, "r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}
    except Exception:  # noqa: BLE001 - 配置不可读等价于「未配置」，不掩盖 Godot 缺失
        return ""
    section = document.get("runtime_playtest") if isinstance(document, dict) else None
    value = str((section or {}).get("godot_binary") or "").strip()
    if not value:
        return ""
    if not os.path.isabs(value):
        value = os.path.join(root, value)
    return value


def find_godot_binary(root: str = "") -> str:
    """按模块文档的优先级返回 Godot 可执行文件绝对路径；找不到返回 ""。"""
    root = root or project_root()
    env = os.environ.get("GODOT_BIN", "").strip()
    if env:
        if os.path.isfile(env):
            return os.path.realpath(os.path.abspath(env))
        # 显式指定了但不可用：不静默回退到其它二进制（否则「我指定了」变成谎言）
        return ""
    configured = configured_godot(root)
    if configured:
        return (os.path.realpath(configured)
                if os.path.isfile(configured) else "")
    parent = os.path.dirname(root)
    candidates = sorted(glob.glob(os.path.join(parent, "Godot_v*_console.exe")))
    candidates += sorted(glob.glob(os.path.join(parent, "Godot_v*.exe")))
    candidates += sorted(glob.glob(os.path.join(parent, "Godot*_console.exe")))
    candidates += sorted(glob.glob(os.path.join(parent, "Godot*.exe")))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.realpath(os.path.abspath(candidate))
    for name in ("godot4", "godot"):
        found = shutil.which(name)
        if found:
            return os.path.realpath(found)
    return ""


def require_godot(root: str = "") -> str:
    """返回 Godot 路径；找不到时以明确的环境错误退出（不是断言失败）。"""
    root = root or project_root()
    binary = find_godot_binary(root)
    if binary:
        return binary
    env = os.environ.get("GODOT_BIN", "").strip()
    hint = ("GODOT_BIN 指向的文件不存在: %s" % env) if env else (
        "未找到可用的 Godot 可执行文件。请设置 GODOT_BIN，或在 %s 中配置 "
        "runtime_playtest.godot_binary（留空则自动查找项目相邻目录与 PATH）"
        % CONFIG_RELATIVE)
    raise SystemExit("ENVIRONMENT ERROR: %s" % hint)
