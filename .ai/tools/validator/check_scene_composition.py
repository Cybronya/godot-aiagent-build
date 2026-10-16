#!/usr/bin/env python3
"""Scene Composition Validator

检查「Scene Blueprint / Entity Blueprint + 生成的 .tscn」的组合合法性（场景级，配合
check_feature_metadata 的蓝图级检查使用）。

输入边界（Phase 1.8.8）：本工具的 CLI / 模块入口仍收**原始 Blueprint**（scene_schema.yaml），
内部先经 `intent_from_blueprint()` 构造成 Scene Intent；校验层（scene_validator）
只接受 Scene Intent —— Blueprint → Intent 的转换只发生在这一处入口。

检查项:
    1. Scene 是否包含 Blueprint 所需 Feature —— 缺失报
       "Missing Feature: <feature> (node <NodeName>)"
    2. Feature Dependency —— 成员 requires 是否由组合满足
    3. Node Structure —— Root Type 必须 == blueprint root.type，否则
       "Invalid Root Node Type"
    4. 组合约束 —— 根节点不得挂脚本（Scene 只负责组合）

用法:
    python check_scene_composition.py <blueprint.yaml> [--scene Scenes/X.tscn]

    --scene 缺省时按 root.name 推导 Scenes/<RootName>.tscn。

作为模块导入:
    from check_scene_composition import check_scene_composition
    result = check_scene_composition(blueprint_dict, scene_path)

退出码: 0 = PASS；1 = FAIL；2 = 输入错误。
"""

import argparse
import json
import os
import sys

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
FEATURES_DIR = os.path.join(PROJECT_ROOT, "Features")
INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")
SCENES_DIR = os.path.join(PROJECT_ROOT, "Scenes")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scene_composer"))

from scene_intent import (                           # noqa: E402
    intent_components,
    intent_from_blueprint,
    intent_root,
)
from scene_validator import validate_scene          # noqa: E402
from template_loader import load_templates           # noqa: E402


def check_scene_composition(blueprint_raw: dict, scene_path: str,
                            features_dir: str = FEATURES_DIR,
                            index_path: str = INDEX_PATH) -> dict:
    """场景组合合法性检查。返回 {failures, warnings, checked(=1)}。

    blueprint_raw —— 原始 Blueprint（Scene / Entity）；本函数内部构造 Scene Intent。
    """
    intent, errors = intent_from_blueprint(blueprint_raw)
    if errors or intent is None:
        return {"failures": list(errors or ["invalid blueprint"]), "warnings": [], "checked": 0}

    index = []
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as f:
            index = (json.load(f) or {}).get("features", [])
    templates = load_templates(intent_components(intent), features_dir)
    result = validate_scene(intent, scene_path, index, templates, features_dir)
    return {
        "failures": result["failures"],
        "warnings": result["warnings"],
        "checked": 1,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate a generated scene against its Scene Blueprint.")
    parser.add_argument("blueprint", help="Blueprint yaml path (Scene or Entity Blueprint)")
    parser.add_argument("--scene", default="", help="Generated .tscn path (default: Scenes/<RootName>.tscn)")
    args = parser.parse_args(argv)

    import yaml
    if not os.path.isfile(args.blueprint):
        print("FAIL: Blueprint not found: %s" % args.blueprint)
        return 2
    blueprint_raw = yaml.safe_load(open(args.blueprint, encoding="utf-8")) or {}

    scene_path = args.scene
    if not scene_path:
        intent, errors = intent_from_blueprint(blueprint_raw)
        root_name = str(intent_root(intent).get("name") or "") if intent is not None else ""
        if intent is None or errors or not root_name:
            print("FAIL: cannot derive scene path: %s" % "; ".join(errors or ["no root.name"]))
            return 2
        scene_path = os.path.join(SCENES_DIR, root_name + ".tscn")
    if not os.path.isfile(scene_path):
        print("FAIL: Scene not found: %s" % scene_path)
        return 2

    print("Scene Composition Validator")
    print("Blueprint: %s" % args.blueprint)
    print("Scene:     %s" % scene_path)
    result = check_scene_composition(blueprint_raw, scene_path)
    if result["failures"]:
        print("\nFAILURES")
        for failure in result["failures"]:
            print("  - " + failure)
    if result["warnings"]:
        print("\nWARNINGS")
        for warning in result["warnings"]:
            print("  - " + warning)
    if result["failures"]:
        print("\nFAIL")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
