#!/usr/bin/env python3
"""Feature Capability Declaration Pipeline 测试（Phase 1.8.11）

链路：Feature 声明 → (Scene Blueprint 传递) → Scene Intent 物化 → Compatibility Gate 判定

    Case 1  旧 Feature（无 capabilities）→ Scene Intent.required=[]，行为与 1.8.10 一致
        （Phase 1.8.12 起项目 Feature 已声明能力，故真实 Feature 改为与自身 metadata 对齐）
    Case 2  Feature 声明 Node/Sprite → 经 Blueprint → Intent 物化，Gate PASS 且记录
    Case 3  Feature 声明 Script → 完整链路（Feature→…→Intent→Gate）BLOCKED，且零 .tscn
    Case 4  多个 Feature（Node / Sprite / Node）→ Intent 自动去重
    Case 5  非法能力（UnknownCapability）→ Gate BLOCKED
    Case 6  完整旧链路回归：.tscn / validator 结果与 1.8.10 IDENTICAL；能力声明来自真实 Feature 数据

Case 2–5 用**临时 Features 目录 + 临时索引**驱动真实 compose() 链路（不改动项目 Feature）。
Case 6 用真实 slime 链路，对比「features_dir=真实目录」与「features_dir=空临时目录」两次运行。

本测试只读项目、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_feature_capability_pipeline.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import ast
import copy
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))                 # .ai/tools/scene_composer/tests
TOOL_DIR = os.path.dirname(_HERE)                                  # .ai/tools/scene_composer
TOOLS_DIR = os.path.dirname(TOOL_DIR)                              # .ai/tools
VALIDATOR_DIR = os.path.join(TOOLS_DIR, "validator")
DOTAI = os.path.dirname(TOOLS_DIR)                                 # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)

for path in (TOOL_DIR, TOOLS_DIR, VALIDATOR_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import compatibility_gate                                      # noqa: E402
import feature_capabilities                                    # noqa: E402
import scene_composer                                          # noqa: E402
import scene_intent                                            # noqa: E402
import scene_validator                                         # noqa: E402
import template_loader                                         # noqa: E402
import test_scene_builder_intent_input as goldens              # noqa: E402

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def rejected(fn) -> tuple:
    try:
        fn()
    except ValueError as exc:
        return True, str(exc)
    except Exception as exc:                                    # noqa: BLE001
        return False, "unexpected %s: %s" % (type(exc).__name__, exc)
    return False, "no exception raised"


# ---------------------------------------------------------------- 临时 Feature fixtures

FIXTURE_FEATURES = {
    # id: capabilities.required（None = 无声明，旧 Feature）
    "alpha": ["Node"],
    "beta": ["Sprite"],
    "gamma": ["Node"],
    "scripted": ["Script"],
    "unknown_cap": ["UnknownCapability"],
    "legacy": None,
}


def write_features(root: str) -> tuple:
    """按 fixture 生成 Features 目录（feature.yaml + template.yaml）与索引 JSON。"""
    features_dir = os.path.join(root, "Features")
    os.makedirs(features_dir, exist_ok=True)
    records = []
    for fid, required in FIXTURE_FEATURES.items():
        feature_dir = os.path.join(features_dir, fid)
        os.makedirs(feature_dir, exist_ok=True)
        meta = {
            "id": fid, "version": 1, "category": "component",
            "summary": "pipeline fixture",
            "provides": [], "requires": [],
            "interfaces": {"methods": [], "signals": [], "exports": []},
            "validation": {"self_test": "test_%s.gd" % fid},
        }
        if required is not None:
            meta["capabilities"] = {"required": list(required)}
        with open(os.path.join(feature_dir, "feature.yaml"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("# fixture feature\n")
            import yaml
            handle.write(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True))
        with open(os.path.join(feature_dir, "template.yaml"), "w",
                  encoding="utf-8", newline="\n") as handle:
            import yaml
            handle.write(yaml.safe_dump(
                {"feature": {"id": fid}, "scene": {"source": "%s.tscn" % fid},
                 "validation": {"required_nodes": [fid]}},
                sort_keys=False, allow_unicode=True))
        records.append({"id": fid, "version": "1", "category": "component",
                        "provides": [], "requires": [], "interfaces": [], "signals": [],
                        "relations": {"requires": []}})
    index_path = os.path.join(root, "feature_index.json")
    with open(index_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"registry_version": 2, "features": records}, handle, indent=2)
    return features_dir, index_path


def entity_blueprint(feature_ids) -> dict:
    return {"entity": {"id": "probe", "role": "enemy"}, "features": list(feature_ids)}


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="feature_capability_")
    try:
        features_dir, index_path = write_features(tmp)
        empty_features = os.path.join(tmp, "empty_features")
        os.makedirs(empty_features, exist_ok=True)

        # ---------------- Case 1: 旧 Feature（无声明） ----------------
        print("=== Case 1: legacy feature without declaration ===")
        ok("case1: reader defaults to [] for a feature without capabilities",
           feature_capabilities.feature_capabilities({"id": "x"}) == {"required": []})
        ok("case1: reader returns [] for the fixture 'legacy' (no declaration)",
           feature_capabilities.capabilities_for_feature("legacy", features_dir) == [])
        # Phase 1.8.12（Feature Data Migration）：项目 Feature 已开始声明能力，
        # 故不再断言「真实 Feature 一律为 []」，而是校验「读取器输出 == 该 Feature
        # 自己 metadata 中的声明」且每个真实 Feature 均已声明（非空）。
        real_features = sorted(name for name in os.listdir(template_loader.FEATURES_DIR)
                               if os.path.isdir(os.path.join(template_loader.FEATURES_DIR, name)))
        declared_map = {
            fid: feature_capabilities.feature_capabilities(
                feature_capabilities.load_feature_definition(fid) or {})["required"]
            for fid in real_features}
        ok("case1: reader output equals each real Feature's own metadata declaration",
           all(feature_capabilities.capabilities_for_feature(fid) == declared_map[fid]
               for fid in real_features), str(declared_map))
        ok("case1: every real project feature declares at least one capability (adopted)",
           all(declared_map[fid] for fid in real_features), str(declared_map))
        legacy_out = os.path.join(tmp, "case1_out")
        legacy_chain = scene_composer.compose(entity_blueprint(["legacy"]), out_dir=legacy_out,
                                             features_dir=features_dir, index_path=index_path)
        ok("case1: legacy composition still generates", legacy_chain["ok"] is True,
           str(legacy_chain.get("failures")))
        ok("case1: Scene Intent.required stays []",
           legacy_chain["scene_intent"]["capabilities"] == {"required": []},
           str(legacy_chain["scene_intent"].get("capabilities")))
        ok("case1: gate records nothing and passes",
           legacy_chain["compatibility"]["status"] == "PASS"
           and legacy_chain["compatibility"]["checked_capabilities"] == [])

        # ---------------- Case 2: Feature 声明经链路物化 ----------------
        print("=== Case 2: declaration travels Feature -> Blueprint -> Intent ===")
        passed = scene_composer.compose(entity_blueprint(["alpha", "beta"]),
                                        out_dir=os.path.join(tmp, "case2_out"),
                                        features_dir=features_dir, index_path=index_path)
        ok("case2: composed intent carries the declared capabilities",
           passed["scene_intent"]["capabilities"] == {"required": ["Node", "Sprite"]},
           str(passed["scene_intent"].get("capabilities")))
        ok("case2: gate PASS and records them",
           passed["compatibility"]["status"] == "PASS"
           and passed["compatibility"]["checked_capabilities"] == ["Node", "Sprite"],
           str(passed["compatibility"]))
        derived = template_loader.derive_scene_blueprint(entity_blueprint(["alpha", "beta"]))
        normalized, errors = template_loader.normalize_scene_blueprint(derived, features_dir)
        ok("case2: the Scene Blueprint transports the declaration",
           not errors and normalized["capabilities"] == {"required": ["Node", "Sprite"]},
           str((errors, normalized.get("capabilities"))))
        direct = scene_intent.intent_from_blueprint(entity_blueprint(["alpha", "beta"]),
                                                    features_dir=features_dir)
        ok("case2: intent_from_blueprint materializes it too",
           direct[1] == [] and direct[0].document["capabilities"] == {"required": ["Node", "Sprite"]},
           str(direct[1]))

        # ---------------- Case 3: Feature 声明 Script -> BLOCKED 零产物 ----------------
        print("=== Case 3: a Feature declaring Script blocks the chain ===")
        blocked_out = os.path.join(tmp, "case3_out")
        blocked = scene_composer.compose(entity_blueprint(["scripted"]), out_dir=blocked_out,
                                        features_dir=features_dir, index_path=index_path)
        ok("case3: intent carries the reserved capability",
           blocked["scene_intent"]["capabilities"] == {"required": ["Script"]},
           str(blocked["scene_intent"].get("capabilities")))
        ok("case3: gate BLOCKED with the capability message",
           blocked["ok"] is False
           and blocked["failures"] == ["Compatibility Gate: Unsupported capability: Script"],
           str(blocked.get("failures")))
        ok("case3: zero .tscn produced",
           not os.path.isdir(blocked_out)
           or [f for f in os.listdir(blocked_out) if f.endswith(".tscn")] == [],
           str(os.listdir(blocked_out) if os.path.isdir(blocked_out) else "<no dir>"))

        # ---------------- Case 4: 多 Feature 去重 ----------------
        print("=== Case 4: multiple features are merged and deduplicated ===")
        merged = scene_composer.compose(entity_blueprint(["alpha", "gamma", "beta"]),
                                        out_dir=os.path.join(tmp, "case4_out"),
                                        features_dir=features_dir, index_path=index_path)
        ok("case4: dedup keeps first occurrence order",
           merged["scene_intent"]["capabilities"] == {"required": ["Node", "Sprite"]},
           str(merged["scene_intent"].get("capabilities")))
        ok("case4: reader-level merge is deduplicated too",
           feature_capabilities.capabilities_for_features(["alpha", "gamma", "beta"],
                                                          features_dir) == ["Node", "Sprite"])
        ok("case4: explicit declaration merges as a union (no channel weakens another)",
           scene_composer.compose(entity_blueprint(["alpha", "beta"]),
                                  out_dir=os.path.join(tmp, "case4b_out"),
                                  features_dir=features_dir, index_path=index_path,
                                  capabilities=["Audio"])["scene_intent"]["capabilities"]
           == {"required": ["Node", "Sprite", "Audio"]})
        ok("case4: explicit declaration cannot hide a feature requirement",
           scene_composer.compose(entity_blueprint(["scripted"]),
                                  out_dir=os.path.join(tmp, "case4c_out"),
                                  features_dir=features_dir, index_path=index_path,
                                  capabilities=["Node"])["ok"] is False)

        # ---------------- Case 5: 非法能力 -> BLOCKED ----------------
        print("=== Case 5: unknown capability blocks ===")
        unknown_out = os.path.join(tmp, "case5_out")
        unknown = scene_composer.compose(entity_blueprint(["unknown_cap"]), out_dir=unknown_out,
                                        features_dir=features_dir, index_path=index_path)
        ok("case5: gate BLOCKED for an unregistered capability",
           unknown["ok"] is False
           and unknown["failures"] == ["Compatibility Gate: Unsupported capability: "
                                       "UnknownCapability"],
           str(unknown.get("failures")))
        ok("case5: zero .tscn produced",
           not os.path.isdir(unknown_out)
           or [f for f in os.listdir(unknown_out) if f.endswith(".tscn")] == [])

        # ---------------- Case 6: 完整旧链路回归（与 1.8.10 IDENTICAL） ----------------
        print("=== Case 6: legacy chain results are identical to 1.8.10 ===")
        # Phase 1.8.12：成员 Feature 的声明（数据驱动，不写死快照）
        expected_caps = feature_capabilities.capabilities_for_features(goldens.FEATURES)
        binding_path = goldens.write_binding(tmp, goldens.BINDING_SLIME)
        real_out = os.path.join(tmp, "case6_real")
        real = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                      out_dir=real_out, bindings_path=binding_path)
        ok("case6: real features declare capabilities -> intent carries their union",
           real["scene_intent"]["capabilities"] == {"required": expected_caps}
           and real["compatibility"]["checked_capabilities"] == expected_caps,
           str(real["scene_intent"].get("capabilities")))
        ok("case6: generated .tscn byte-identical to the 1.8.10 baseline",
           open(real["scene_path"], encoding="utf-8", newline="").read() == goldens.GOLDEN_F3,
           os.path.basename(real["scene_path"]))
        templates = template_loader.load_templates(goldens.FEATURES)
        index = json.load(open(os.path.join(DOTAI, "context", "feature_index.json"),
                               encoding="utf-8")).get("features", [])
        variants = {
            "a_pass": goldens.GOLDEN_F3,
            "b_missing_feature": goldens.GOLDEN_F3.replace(
                '[node name="Health" parent="." instance=ExtResource("1_health")]\n\n', ""),
            "c_wrong_root_type": goldens.GOLDEN_F3.replace('type="CharacterBody2D"',
                                                           'type="Node2D"', 1),
            "d_root_script": goldens.GOLDEN_F3.replace(
                '[node name="SlimeEnemy" type="CharacterBody2D"]',
                '[node name="SlimeEnemy" type="CharacterBody2D"]\nscript = ExtResource("9_gd")'),
            "e_bad_parent_path": goldens.GOLDEN_F3
            + '\n[node name="GhostChild" type="Node2D" parent="Ghost"]\n',
            "f_duplicate_name": goldens.GOLDEN_F3
            + '\n[node name="Health" type="Node2D" parent="."]\n',
        }
        # Phase 1.8.10 基线（与 test_scene_compatibility_gate.py 的期望一致）
        expected = {
            "a_pass": (True, []),
            "b_missing_feature": (False, ["Missing Feature: health (node Health)"]),
            "c_wrong_root_type": (False, [
                "Composition Error: root type Node2D does not satisfy member requirements: "
                "CharacterBody2D",
                "Invalid Root Node Type: expected CharacterBody2D, got Node2D"]),
            "d_root_script": (True, []),
            "e_bad_parent_path": (False, [
                "Composition Error: node GhostChild parent path 'Ghost' references a node not "
                "declared in this scene"]),
            "f_duplicate_name": (False, [
                "Composition Error: duplicate node name 'Health' under parent '.'"]),
        }
        intent_real = scene_intent.intent_from_blueprint(
            copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
            features_dir=template_loader.FEATURES_DIR)[0]
        intent_nodecl = scene_intent.intent_from_blueprint(
            copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME), features_dir=empty_features)[0]
        gate_real = compatibility_gate.check_scene_compatibility(intent_real).to_dict()
        for name, body in sorted(variants.items()):
            path = os.path.join(tmp, "case6_%s.tscn" % name)
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(body)
            result = scene_validator.validate_scene(intent_real, path, index, templates,
                                                   template_loader.FEATURES_DIR)
            ok("case6: fixture %s identical to the 1.8.10 baseline" % name,
               (result["ok"], sorted(result["failures"]))
               == (expected[name][0], sorted(expected[name][1])),
               str((result["ok"], sorted(result["failures"]))))
        ok("case6: gate verdict unchanged for the whole fixture set",
           gate_real["status"] == "PASS"
           and gate_real["checked_capabilities"] == expected_caps
           and gate_real["errors"] == [], str(gate_real))
        gate_nodecl = compatibility_gate.check_scene_compatibility(intent_nodecl).to_dict()
        ok("case6: transport delta is exactly the Feature declaration (same verdict/output)",
           gate_real["status"] == gate_nodecl["status"] == "PASS"
           and gate_real["errors"] == gate_nodecl["errors"] == []
           and gate_nodecl["checked_capabilities"] == []
           and intent_nodecl.document["capabilities"] == {"required": []}
           and real["scene_intent"]["capabilities"] == {"required": expected_caps})

        # ---------------- 附件：读取器职责隔离 ----------------
        print("=== Extra: reader isolation + declaration semantics ===")
        source = open(os.path.join(TOOL_DIR, "feature_capabilities.py"), encoding="utf-8").read()
        ok("extra: reader does not read the normalized Blueprint dict",
           "blueprint[" not in source and "blueprint.get(" not in source)
        module = ast.parse(source)
        imported = set()
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        ok("extra: reader imports only os/yaml/sys (no Scene Intent / Gate / vocabulary)",
           imported == {"os", "yaml", "sys"}, str(sorted(imported)))
        ok("extra: no auto-inference from feature names / categories / provides",
           feature_capabilities.feature_capabilities(
               {"id": "EnemyAttack", "category": "ai", "provides": ["scripted_ai"]})
           == {"required": []})
        ok("extra: reader and intent normalize the same declaration forms identically",
           all(feature_capabilities.normalize_required(decl)
               == scene_intent._normalize_capabilities(decl)
               for decl in (None, [], ["Node"], "Node", ["Node", "Node"],
                            {"required": ["Node"]}, {})))
        rejected_ok, message = rejected(
            lambda: feature_capabilities.feature_capabilities(["Node"]))
        ok("extra: a non-mapping feature definition is rejected", rejected_ok, message)
        rejected_ok, message = rejected(
            lambda: feature_capabilities.feature_capabilities({"capabilities": {"x": 1}}))
        ok("extra: a malformed declaration is rejected (no guessing)", rejected_ok, message)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all feature capability pipeline checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
