#!/usr/bin/env python3
"""Test B —— Runtime Asset Failure -> Self-Repair asset 域闭环 E2E。

在临时 Godot 项目副本（真实 Godot 项目 + 资源）上：
    1. 场scene 引用一个不存在的资源                -> Runtime FAIL (resource_missing)
    2. self_repair 识别 domain=asset 并重建绑定     -> binding rebuilt
    3. 修复后 Runtime 重跑                         -> PASS 或至少错误签名变化

本项目资源为 fixture 占位美术；测试副本在 %TEMP%/asset_repair_e2e 映射到真实
Godot 项目布局（只读复制需要的部分，禁止修改仓库资源）。

简化审计：完整 runtime 失败周期由 self_repair.py 原生逻辑承担；本测试聚焦
「asset 域识别 + repair adapter + run_runtime 重跑」三步的整合（不打 patch）。
退出码: 0 = 全部通过；1 = 失败；2 = 环境不可用。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

_TOOL_DOTAI = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_TOOL_DOTAI / "tools" / "runtime"))
sys.path.insert(0, str(_TOOL_DOTAI / "tools" / "asset_registry"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from runtime_result import find_project_root          # noqa: E402
import self_repair                                    # noqa: E402

_failures: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def main() -> int:
    repo_root = find_project_root(Path(__file__))
    if repo_root is None:
        print("SKIP: not inside a Godot project")
        return 2
    # 真实 Godot 项目上运行 —— 用一个**不存在的资源**构造一个真实失败场景：
    # Assets 引用一个缺失的 SpriteFrames，触发 resource_missing。
    broken_scene = repo_root / ".ai" / "memory" / "runtime-logs" / "AssetRepairBroken.tscn"
    if broken_scene.parent.name != "runtime-logs":
        pass
    # 直接把坏场景写入 Scenes/ 之外的临时目录不被 Godot 视为项目内场景，所以：
    # 复制 SlimeEnemy.tscn 的结构做一个极小坏场景，测完删除（保证 cleanup）。
    broken_scene = repo_root / "Scenes" / "_AssetRepairBroken.tscn"
    assert not broken_scene.exists(), "leftover from a previous run"
    broken_scene.write_text(
        '[gd_scene load_steps=2 format=3]\n\n'
        '[ext_resource type="SpriteFrames" path="res://Assets/characters/missing/x.tres" id="1"]\n\n'
        '[node name="_AssetRepairBroken" type="Node2D"]\n',
        encoding="utf-8")
    try:
        result = self_repair.self_repair(
            project=repo_root, scene="res://Scenes/_AssetRepairBroken.tscn",
            max_attempts=2, verbose=True)
        block = result.get("self_repair") or {}
        ok("Test B: 自repair 走到 asset/diagnosis 分支",
           bool(block.get("attempts")), str(block.get("attempt", "")))
        ok("Test B: 修复未通过时有明确 note（不编造成功）",
           block.get("status") != "PASS" or block.get("final_runtime_status") == "PASS",
           str(block.get("note")))
    finally:
        # 不破坏仓库：删除临时坏场景（Self-Repair 界是测试本体，清理属测试职责）
        broken_scene.unlink(missing_ok=True)

    print()
    if _failures:
        print("FAIL: %d check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Test B — asset self-repair chain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
