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
    Build Scene Tree (scene_builder)
        ↓
    Generate .tscn -> Scenes/<RootName>.tscn
        ↓
    Run Validation (scene_validator)

用法:
    python scene_composer.py <blueprint.yaml> [--out Scenes] [--tests] [--dry-run]

    blueprint.yaml 既可以是 Scene Blueprint（scene:/root:/components:），
    也可以是 Entity Blueprint（entity:/features:，自动推导 Scene Blueprint，
    推导规则见 .ai/context/scene_schema.yaml）。

    --tests   同时用 test_generator 生成 Tests/test_<scene_id>.gd
    --dry-run 只做推导 + 依赖检查，不写文件

退出码: 0 成功（Validation PASS）；1 失败；2 输入/环境错误。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml

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
            features_dir: str = FEATURES_DIR, index_path: str = INDEX_PATH) -> dict:
    """核心流程。返回 {ok, scene_path, failures, warnings, blueprint}。"""
    # 1. Entity Blueprint -> Scene Blueprint -> 规整
    scene_blueprint = derive_scene_blueprint(blueprint_raw)
    blueprint, errors = normalize_scene_blueprint(scene_blueprint)
    if errors:
        return {"ok": False, "failures": errors, "warnings": [], "blueprint": blueprint, "scene_path": ""}

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
        return {"ok": False, "failures": failures, "warnings": [], "blueprint": blueprint, "scene_path": ""}

    if dry_run:
        return {"ok": True, "failures": [], "warnings": [], "blueprint": blueprint, "scene_path": ""}

    # 3. 构建并写出 .tscn
    templates = load_templates(blueprint["features"], features_dir)
    scene_path = write_scene(blueprint, templates, features_dir, out_dir)

    # 4. 生成后校验
    result = validate_scene(blueprint, scene_path, index, templates, features_dir)
    result["scene_path"] = scene_path
    result["blueprint"] = blueprint
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compose an Entity Blueprint into a Godot Scene.")
    parser.add_argument("blueprint", help="Blueprint yaml path (Scene or Entity Blueprint)")
    parser.add_argument("--out", default=SCENES_DIR, help="Output directory for the .tscn")
    parser.add_argument("--tests", action="store_true", help="Also generate Tests/test_<scene_id>.gd")
    parser.add_argument("--dry-run", action="store_true", help="Derive + resolve only, write nothing")
    args = parser.parse_args(argv)

    blueprint_raw = load_blueprint(args.blueprint)
    result = compose(blueprint_raw, out_dir=args.out, dry_run=args.dry_run)

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
