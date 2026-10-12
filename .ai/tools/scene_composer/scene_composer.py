#!/usr/bin/env python3
"""Scene Composer (v1)

把 Scene Blueprint / Entity Blueprint 自动组装成 Godot Scene (.tscn)。

流程:
    Entity Blueprint (or Scene Blueprint)
        ↓
    Load Feature Templates (Features/*/template.yaml)
        ↓
    Resolve Dependencies (dependency_resolver)
        ↓
    [可选] Resolve Asset Bindings (asset_registry/bind_assets.py)
        ↓
    Build Scene Tree (scene_builder; 含资源节点 AnimatedSprite2D/Sprite2D/AudioStreamPlayer)
        ↓
    Generate .tscn -> Scenes/<RootName>.tscn
        ↓
    Run Validation (scene_validator)

用法:
    python scene_composer.py <blueprint.yaml> [--out Scenes] [--tests] [--dry-run]
    python scene_composer.py <blueprint.yaml> --bind-assets
    python scene_composer.py <blueprint.yaml> --bindings .ai/context/asset_bindings/x.yaml

    blueprint.yaml 既可以是 Scene Blueprint（scene:/root:/components:），
    也可以是 Entity Blueprint（entity:/features:，自动推导 Scene Blueprint，
    推导规则见 .ai/context/scene_schema.yaml）。

    --tests   同时用 test_generator 生成 Tests/test_<scene_id>.gd
    --dry-run 只做推导 + 依赖检查，不写文件
    --bind-assets 调 Asset Registry 解析 Asset Binding（Feature->Entity->Asset），
               写入 .ai/context/asset_bindings/<id>.yaml，并生成资源节点
    --bindings <file> 读既有 Asset Binding 文档（跳过解析）
    --bindings-out <file> --bind-assets 的绑定文档输出路径

    Asset 集成只做「实例化 + 连接资源」（AnimatedSprite2D / Sprite2D /
    AudioStreamPlayer），不引入 Gameplay State、不修改资源文件。

退出码: 0 成功（Validation PASS）；1 失败；2 输入/环境错误。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml

from asset_nodes import nodes_for_blueprint
from dependency_resolver import resolve
from scene_builder import scene_file_path, write_scene
from scene_validator import validate_scene
from template_loader import (
    FEATURES_DIR,
    INDEX_PATH,
    PROJECT_ROOT,
    derive_scene_blueprint,
    load_templates,
    normalize_scene_blueprint,
)

SCENES_DIR = os.path.join(PROJECT_ROOT, "Scenes")


def load_blueprint(path: str) -> dict:
    if not os.path.isfile(path):
        raise SystemExit("FAIL: Blueprint not found: %s" % path)
    data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit("FAIL: Blueprint must be a YAML mapping: %s" % path)
    return data


def compose(blueprint_raw: dict, out_dir: str = SCENES_DIR, dry_run: bool = False,
            features_dir: str = FEATURES_DIR, index_path: str = INDEX_PATH,
            bindings_path: str = "", bind_assets: bool = False,
            bindings_out: str = "") -> dict:
    """核心流程。返回 {ok, scene_path, failures, warnings, blueprint, asset_nodes}。"""
    # 1. Entity Blueprint -> Scene Blueprint -> 规整
    scene_blueprint = derive_scene_blueprint(blueprint_raw)
    blueprint, errors = normalize_scene_blueprint(scene_blueprint)
    if errors:
        return {"ok": False, "failures": errors, "warnings": [], "blueprint": blueprint,
                "scene_path": "", "asset_nodes": {}}

    # 1b. Asset Binding -> 资源节点（可选；缺失只警告，不阻断生成）
    asset_info = {}
    if bindings_path or bind_assets:
        try:
            resource_nodes, asset_info = nodes_for_blueprint(
                blueprint_raw, bindings_path=bindings_path, bind_assets=bind_assets,
                out_path=bindings_out)
        except SystemExit as exc:
            return {"ok": False, "failures": [str(exc)], "warnings": [],
                    "blueprint": blueprint, "scene_path": "", "asset_nodes": {}}
        blueprint["resource_nodes"] = resource_nodes
        asset_info["node_count"] = len(resource_nodes)

    # 2. 依赖解析（生成前硬性拦截）
    index = []
    if os.path.isfile(index_path):
        import json
        with open(index_path, encoding="utf-8") as f:
            index = (json.load(f) or {}).get("features", [])
    dep = resolve(blueprint["features"], index, features_dir)
    failures = list(dep["errors"]) + list(dep["missing"]) + [
        "Unknown Feature in composition: %s" % fid for fid in dep["unknown"]
    ]
    if failures:
        return {"ok": False, "failures": failures, "warnings": [], "blueprint": blueprint,
                "scene_path": "", "asset_nodes": asset_info}

    if dry_run:
        return {"ok": True, "failures": [], "warnings": [], "blueprint": blueprint,
                "scene_path": "", "asset_nodes": asset_info}

    # 3. 构建并写出 .tscn
    templates = load_templates(blueprint["features"], features_dir)
    scene_path = write_scene(blueprint, templates, features_dir, out_dir)

    # 4. 生成后校验
    result = validate_scene(blueprint, scene_path, index, templates, features_dir)
    result["scene_path"] = scene_path
    result["blueprint"] = blueprint
    result["asset_nodes"] = asset_info
    # Asset Binding 的缺失/降级只作为警告（是否阻断由 validator/check_assets.py 判定）
    if asset_info:
        for warning in asset_info.get("warnings") or []:
            result.setdefault("warnings", []).append("Asset Binding: " + warning)
        for reason in asset_info.get("missing") or []:
            result.setdefault("warnings", []).append("Asset Binding missing role: " + reason)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compose an Entity Blueprint into a Godot Scene.")
    parser.add_argument("blueprint", help="Blueprint yaml path (Scene or Entity Blueprint)")
    parser.add_argument("--out", default=SCENES_DIR, help="Output directory for the .tscn")
    parser.add_argument("--tests", action="store_true", help="Also generate Tests/test_<scene_id>.gd")
    parser.add_argument("--dry-run", action="store_true", help="Derive + resolve only, write nothing")
    parser.add_argument("--bind-assets", action="store_true",
                        help="Resolve Asset Bindings via the Asset Registry and add resource nodes")
    parser.add_argument("--bindings", default="", help="Existing Asset Binding document (yaml)")
    parser.add_argument("--bindings-out", default="", help="Where --bind-assets writes the binding document")
    args = parser.parse_args(argv)

    blueprint_raw = load_blueprint(args.blueprint)
    result = compose(blueprint_raw, out_dir=args.out, dry_run=args.dry_run,
                     bindings_path=args.bindings, bind_assets=args.bind_assets,
                     bindings_out=args.bindings_out)

    blueprint = result.get("blueprint") or {}
    if blueprint:
        print("Scene Composer")
        print()
        print("Scene Blueprint:")
        print("  id:   %s" % blueprint.get("scene_id", ""))
        print("  root: %s (%s)" % (blueprint.get("root_name", ""), blueprint.get("root_type", "")))
        print("  components: %s" % ", ".join(blueprint.get("features", [])))

    if not result["ok"]:
        print()
        print("FAILURES")
        for failure in result["failures"]:
            print("  - " + failure)
        return 1

    if args.dry_run:
        print()
        print("Dry run: dependencies satisfied, nothing written.")
        return 0

    print()
    print("Generated: %s" % os.path.relpath(result["scene_path"], PROJECT_ROOT).replace("\\", "/"))
    asset_info = result.get("asset_nodes") or {}
    if asset_info:
        print("Asset nodes: %d" % int(asset_info.get("node_count") or 0))
        if asset_info.get("bindings_path"):
            label = "resolved" if asset_info.get("resolved") else "read"
            print("Asset bindings (%s): %s" % (
                label, os.path.relpath(asset_info["bindings_path"], PROJECT_ROOT).replace("\\", "/")))
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print("  - " + warning)
    print("Validation: PASS")

    if args.tests:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_generator"))
        import generate_scene_test
        test_path = generate_scene_test.generate_test_file(blueprint)
        print("Test generated: %s" % os.path.relpath(test_path, PROJECT_ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
