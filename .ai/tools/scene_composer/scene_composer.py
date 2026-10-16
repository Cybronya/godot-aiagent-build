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
    Build Scene Intent (scene_intent.SceneIntentBuilder; 正式计划层, 契约 v2)
        ↓
    Compatibility Gate (compatibility_gate; 能力闸门：能力**是否被支持**)
        ↓
    Capability Contract Validation (capability_contract_validator; 计划**是否满足**能力要求)
        ↓
    Build Scene Tree (scene_builder; 唯一输入 = Scene Intent, 含资源节点
                      AnimatedSprite2D/Sprite2D/AudioStreamPlayer)
        ↓
    Generate .tscn -> Scenes/<RootName>.tscn
        ↓
    Run Validation (scene_validator)
        ↓
    Artifact Evidence Verification (artifact_evidence_validator; 生成物写盘之后：
                                   声明结构是否真的落在 .tscn 文本里；失败保留产物)

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

from artifact_evidence_validator import verify_artifact_evidence
from asset_nodes import nodes_for_blueprint
from capability_contract_validator import validate_capability_contract
from compatibility_gate import check_scene_compatibility, known_feature_ids
from dependency_resolver import resolve
from scene_builder import scene_file_path, write_scene
from scene_intent import SceneIntentBuilder, intent_components
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


def load_index(index_path: str) -> list:
    if not os.path.isfile(index_path):
        return []
    import json
    with open(index_path, encoding="utf-8") as f:
        return (json.load(f) or {}).get("features", [])


def compose(blueprint_raw: dict, out_dir: str = SCENES_DIR, dry_run: bool = False,
            features_dir: str = FEATURES_DIR, index_path: str = INDEX_PATH,
            bindings_path: str = "", bind_assets: bool = False,
            bindings_out: str = "", capabilities=None) -> dict:
    """核心流程。返回 {ok, scene_path, failures, warnings, blueprint, asset_nodes,
    scene_intent, compatibility, capability_contract, artifact_evidence}
    （scene_intent = 契约 v2 的 Scene Intent Document）。

    capabilities —— Phase 1.8.10/1.8.11 能力声明（可选）：`["Node", "Sprite"]` 或
    `{"required": [...]}`。最终 required = 成员 Feature 声明（Feature Registry 侧，
    见 feature_capabilities）∪ Blueprint 自带声明 ∪ 本参数（并集，任何一方不得削弱另一方）。
    """
    # 1. Entity Blueprint -> Scene Blueprint -> 规整
    scene_blueprint = derive_scene_blueprint(blueprint_raw)
    blueprint, errors = normalize_scene_blueprint(scene_blueprint, features_dir)
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
    else:
        blueprint["resource_nodes"] = []

    # 2. Build Scene Intent（正式计划层；生成链路的唯一输入）
    intent = SceneIntentBuilder().build(blueprint, blueprint.get("resource_nodes") or [],
                                        capabilities)

    # 2a. Compatibility Gate（Phase 1.8.9）—— 能力闸门：BLOCKED 即中止（零产物）。
    # 已知 Feature id 取自本次运行实际使用的索引（注入而非隐式读项目索引），
    # 使 --index/测试 fixture 与闸门判定同源。
    index = load_index(index_path)
    report = check_scene_compatibility(intent, known_features=known_feature_ids(index_path))
    if not report.ok:
        return {"ok": False,
                "failures": ["Compatibility Gate: " + err for err in report.errors],
                "warnings": [], "blueprint": blueprint, "scene_path": "",
                "asset_nodes": asset_info, "scene_intent": intent.to_dict(),
                "compatibility": report.to_dict()}

    # 2c. Capability Contract Validation（Phase 1.8.13）—— Scene Intent + Scene Plan → 契约核对。
    # Gate 已判定「能力是否被支持」；这里判定「当前生成计划是否满足能力要求」。
    # BLOCKED 同样零产物（禁止半成品文件），前缀与 Gate 区分，便于定位失败层。
    contract = validate_capability_contract(intent)
    if not contract.ok:
        return {"ok": False,
                "failures": ["Capability Contract: " + err for err in contract.errors],
                "warnings": [], "blueprint": blueprint, "scene_path": "",
                "asset_nodes": asset_info, "scene_intent": intent.to_dict(),
                "compatibility": report.to_dict(),
                "capability_contract": contract.to_dict()}

    # 3. 依赖解析（生成前硬性拦截）
    dep = resolve(intent_components(intent), index, features_dir)
    failures = list(dep["errors"]) + list(dep["missing"]) + [
        "Unknown Feature in composition: %s" % fid for fid in dep["unknown"]
    ]
    if failures:
        return {"ok": False, "failures": failures, "warnings": [], "blueprint": blueprint,
                "scene_path": "", "asset_nodes": asset_info,
                "scene_intent": intent.to_dict(), "compatibility": report.to_dict(),
                "capability_contract": contract.to_dict()}

    if dry_run:
        return {"ok": True, "failures": [], "warnings": [], "blueprint": blueprint,
                "scene_path": "", "asset_nodes": asset_info,
                "scene_intent": intent.to_dict(), "compatibility": report.to_dict(),
                "capability_contract": contract.to_dict()}

    # 4. 构建并写出 .tscn
    templates = load_templates(intent_components(intent), features_dir)
    scene_path = write_scene(intent, templates, features_dir, out_dir)

    # 5. 生成后校验（Phase 1.8.8：validator 同样只吃 Scene Intent）
    result = validate_scene(intent, scene_path, index, templates, features_dir)
    result["scene_path"] = scene_path
    result["blueprint"] = blueprint
    result["asset_nodes"] = asset_info
    result["scene_intent"] = intent.to_dict()
    result["compatibility"] = report.to_dict()
    result["capability_contract"] = contract.to_dict()

    # 5b. Artifact Evidence Verification（Phase 1.8.15）—— 生成物写盘**之后**核验。
    # 「声明 = 计划 = 生成物」：components[].instance 声明的结构必须能在生成的 .tscn
    # 静态文本里找到（类型 / 挂载关系）。无声明 → PASS（旧行为不变）。
    # 失败时 ok=false、failures 前缀 "Artifact Evidence: "，并**保留生成物**供诊断
    # （不删除、不自动修复）。
    artifact = verify_artifact_evidence(intent, scene_path)
    result["artifact_evidence"] = artifact.to_dict()
    if not artifact.ok:
        result["ok"] = False
        result["failures"] = list(result.get("failures") or []) + [
            "Artifact Evidence: " + err for err in artifact.errors]

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
        capabilities = (blueprint.get("capabilities") or {}).get("required") or []
        print("  capabilities: %s" % (", ".join(capabilities) if capabilities else "[]"))

    if not result["ok"]:
        print()
        print("FAILURES")
        for failure in result["failures"]:
            print("  - " + failure)
        # 写盘后核验失败时生成物被**保留**（禁止删除）：打印路径供诊断
        if result.get("scene_path"):
            print()
            print("Artifact kept for diagnosis: %s"
                  % os.path.relpath(result["scene_path"], PROJECT_ROOT).replace("\\", "/"))
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
        test_path = generate_scene_test.generate_test_file(result["scene_intent"])
        print("Test generated: %s" % os.path.relpath(test_path, PROJECT_ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
