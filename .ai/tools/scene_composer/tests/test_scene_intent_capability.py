#!/usr/bin/env python3
"""Scene Intent Capability Metadata 测试（Phase 1.8.10）

    Case 1  旧 Intent（无 capabilities）→ 仍合法：intent_capabilities 默认 required=[]
            且 Gate / Builder / Validator / test_generator 全部照常工作
    Case 2  合法能力声明 required: [Node, Sprite] → Gate PASS，checked_capabilities 记录
    Case 3  未登记能力 QuantumRenderer → BLOCKED（"Unsupported capability: ..."）
    Case 4  预留能力 Script（未来能力）→ BLOCKED
    Case 5  旧规整内部 dict 传给 intent_capabilities() → ValueError
    Case 6  完整链路 Intent → Gate → Builder：与 1.8.9 一致（.tscn 逐字节、BLOCKED 零产物）

fixture 与 golden 复用 test_scene_builder_intent_input.py（同一测试目录，单一基线来源）。

本测试只读项目、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_scene_intent_capability.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import copy
import json
import os
import shutil
import sys
import tempfile
import warnings

_HERE = os.path.dirname(os.path.abspath(__file__))                 # .ai/tools/scene_composer/tests
TOOL_DIR = os.path.dirname(_HERE)                                  # .ai/tools/scene_composer
TOOLS_DIR = os.path.dirname(TOOL_DIR)                              # .ai/tools
VALIDATOR_DIR = os.path.join(TOOLS_DIR, "validator")
TEST_GEN_DIR = os.path.join(TOOLS_DIR, "test_generator")
DOTAI = os.path.dirname(TOOLS_DIR)                                 # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)

for path in (TOOL_DIR, TOOLS_DIR, VALIDATOR_DIR, TEST_GEN_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import asset_nodes                                             # noqa: E402
import capability_registry                                       # noqa: E402
import compatibility_gate                                        # noqa: E402
import feature_capabilities                                      # noqa: E402
import generate_scene_test                                       # noqa: E402
import scene_builder                                             # noqa: E402
import scene_composer                                            # noqa: E402
import scene_intent                                              # noqa: E402
import scene_validator                                           # noqa: E402
import template_loader                                           # noqa: E402
import test_scene_builder_intent_input as goldens                # noqa: E402

FEATURES = goldens.FEATURES

# Phase 1.8.12（Feature Data Migration）：真实 Feature 已声明自身能力，因此链路蓝图的
# capabilities 不再为空。本套件区分「蓝图自带声明」（DECLARED_BASE，来自成员 Feature
# 的 feature.yaml）与「显式声明」，并集规则见
# .ai/context/scene_composer_schema.yaml#capability_declaration_flow。
DECLARED_BASE = feature_capabilities.capabilities_for_features(FEATURES)


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


def merged(*explicit) -> dict:
    """蓝图自带声明 ∪ 显式声明（并集、保序去重）-> 契约形态的 capabilities 段。"""
    union = list(DECLARED_BASE)
    for name in explicit:
        name = str(name).strip()
        if name and name not in union:
            union.append(name)
    return {"required": union}


def legacy_view(intent) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return intent.to_legacy_dict()


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="intent_capability_")
    try:
        features_dir = template_loader.FEATURES_DIR
        templates = template_loader.load_templates(FEATURES)
        index = json.load(open(os.path.join(DOTAI, "context", "feature_index.json"),
                               encoding="utf-8")).get("features", [])
        binding_path = goldens.write_binding(tmp, goldens.BINDING_SLIME)
        blueprint = template_loader.normalize_scene_blueprint(
            template_loader.derive_scene_blueprint(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME)))[0]

        # ---------------- Case 1: 旧 Intent（无 capabilities）仍然合法 ----------------
        print("=== Case 1: legacy intent without capabilities stays valid ===")
        # 无声明蓝图（去掉 Phase 1.8.12 迁移带来的成员 Feature 声明）仍走默认路径，
        # 即「旧 Intent（无 capabilities）依旧合法」这条语义不受数据迁移影响。
        bare_blueprint = {key: value for key, value in blueprint.items() if key != "capabilities"}
        legacy_intent = scene_intent.SceneIntentBuilder().build(bare_blueprint, [])
        legacy_document = legacy_intent.to_dict()
        ok("case1: builder emits capabilities.required = [] by default",
           legacy_document["capabilities"] == {"required": []}, str(legacy_document.get("capabilities")))
        ok("case1: intent_capabilities returns the default",
           scene_intent.intent_capabilities(legacy_intent) == {"required": []})
        # 1.8.10 之前的 Intent：没有 capabilities 键（由真实意图去掉该键得到）
        full_intent = goldens.intent_for(goldens.SCENE_BLUEPRINT_SLIME, binding_path)
        pre_1810 = {key: value for key, value in full_intent.to_dict().items()
                    if key != "capabilities"}
        ok("case1: fixture really has no capabilities key", "capabilities" not in pre_1810,
           str(sorted(pre_1810)))
        ok("case1: a pre-1.8.10 intent is still a valid intent",
           scene_intent.intent_capabilities(pre_1810) == {"required": []}
           and compatibility_gate.check_scene_compatibility(pre_1810).ok)
        ok("case1: that pre-1.8.10 intent still builds the golden scene",
           scene_builder.build_tscn(pre_1810, templates, features_dir) == goldens.GOLDEN_F3)
        case1_scene = os.path.join(tmp, "case1.tscn")
        with open(case1_scene, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(goldens.GOLDEN_F3)
        ok("case1: validator accepts the pre-1.8.10 intent too",
           scene_validator.validate_scene(pre_1810, case1_scene, index, templates,
                                          features_dir)["ok"])
        case1_test = generate_scene_test.generate_test_file(
            pre_1810, out_dir=os.path.join(tmp, "case1_gen"), features_dir=features_dir)
        ok("case1: test_generator accepts the pre-1.8.10 intent too",
           os.path.isfile(case1_test)
           and 'load("res://Scenes/SlimeEnemy.tscn")' in open(case1_test, encoding="utf-8").read())

        # ---------------- Case 2: 合法能力声明 -> PASS ----------------
        print("=== Case 2: supported capability declaration passes ===")
        resource_nodes, _info = asset_nodes.nodes_for_blueprint(
            goldens.SCENE_BLUEPRINT_SLIME, bindings_path=binding_path)
        declared = scene_intent.SceneIntentBuilder().build(blueprint, resource_nodes,
                                                           ["Node", "Sprite"])
        report = compatibility_gate.check_scene_compatibility(declared)
        ok("case2: document carries the declaration",
           declared.document["capabilities"] == merged("Sprite"),
           str(declared.document["capabilities"]))
        ok("case2: gate PASS", report.ok and report.errors == [], str(report.errors))
        ok("case2: checked_capabilities records the declaration",
           report.checked_capabilities == merged("Sprite")["required"],
           str(report.checked_capabilities))
        ok("case2: declaration does not change generation",
           scene_builder.build_tscn(declared, templates, features_dir) == goldens.GOLDEN_F3)
        # 以下三条只考察「显式声明如何被规范化」，用无声明蓝图以隔离数据迁移的影响
        ok("case2: declaration is normalized (dedup + order + case preserved)",
           scene_intent.intent_capabilities(
               scene_intent.SceneIntentBuilder().build(bare_blueprint, [],
                                                       ["Node", "Node", " Sprite "]))
           == {"required": ["Node", "Sprite"]})
        ok("case2: {'required': [...]} form accepted by the builder",
           scene_intent.SceneIntentBuilder().build(
               bare_blueprint, [], {"required": ["Collision"]}).document["capabilities"]
           == {"required": ["Collision"]})
        ok("case2: capability names are matched case-insensitively",
           compatibility_gate.check_scene_compatibility(
               scene_intent.SceneIntentBuilder().build(bare_blueprint, [], ["node", "SPRITE"])).ok
           and compatibility_gate.check_scene_compatibility(
               scene_intent.SceneIntentBuilder().build(bare_blueprint, [], ["node"])
           ).checked_capabilities == ["Node"])

        # ---------------- Case 3: 未登记能力 -> BLOCKED ----------------
        print("=== Case 3: unknown capability blocks ===")
        unknown = compatibility_gate.check_scene_compatibility(
            scene_intent.SceneIntentBuilder().build(bare_blueprint, [],
                                                    ["Node", "QuantumRenderer"]))
        ok("case3: status BLOCKED", unknown.status == compatibility_gate.STATUS_BLOCKED)
        ok("case3: error names the capability",
           unknown.errors == ["Unsupported capability: QuantumRenderer"], str(unknown.errors))
        ok("case3: supported ones are still recorded",
           unknown.checked_capabilities == ["Node"], str(unknown.checked_capabilities))
        ok("case3: registry classifies it as unknown",
           capability_registry.classify("QuantumRenderer") == capability_registry.STATUS_UNKNOWN
           and not capability_registry.is_supported("QuantumRenderer"))

        # ---------------- Case 4: 预留能力（Script / Animation / ...） -> BLOCKED ----------------
        print("=== Case 4: reserved (future) capabilities block ===")
        script_intent = scene_intent.SceneIntentBuilder().build(blueprint, [], ["Script"])
        script_report = compatibility_gate.check_scene_compatibility(script_intent)
        ok("case4: Script -> BLOCKED with the capability message",
           script_report.status == compatibility_gate.STATUS_BLOCKED
           and script_report.errors == ["Unsupported capability: Script"], str(script_report.errors))
        ok("case4: reserved vocabulary is exposed by the registry",
           capability_registry.RESERVED_CAPABILITIES
           == ("Script", "Animation", "AnimationController", "AI", "RuntimeBehaviour"),
           str(capability_registry.RESERVED_CAPABILITIES))
        for name in capability_registry.RESERVED_CAPABILITIES:
            blocked = compatibility_gate.check_scene_compatibility(
                scene_intent.SceneIntentBuilder().build(blueprint, [], [name]))
            ok("case4: reserved capability %r blocks" % name,
               blocked.status == compatibility_gate.STATUS_BLOCKED
               and blocked.errors == ["Unsupported capability: %s" % name], str(blocked.errors))
        ok("case4: capability names also block as component tokens (compat channel)",
           compatibility_gate.check_scene_compatibility(
               {"document": "scene_intent", "scene": {"id": "x"},
                "root": {"name": "X", "type": "Node2D"},
                "components": [{"component": "Script"}], "nodes": [], "resources": [],
                "validation": {}}).errors == ["Unsupported component: Script"])
        ok("case4: no capability provider is implemented in this phase",
           not hasattr(compatibility_gate, "capability_provider")
           and "Animation" not in capability_registry.SUPPORTED_COMPONENT_CAPABILITIES)

        # ---------------- Case 5: legacy dict 被拒绝 ----------------
        print("=== Case 5: legacy internal dict is rejected ===")
        legacy = legacy_view(legacy_intent)
        ok("case5: fixture really is the normalized internal dict",
           "root_name" in legacy and "extra_nodes" in legacy, str(sorted(legacy)))
        rejected_ok, message = rejected(lambda: scene_intent.intent_capabilities(legacy))
        ok("case5: intent_capabilities(legacy dict) raises ValueError", rejected_ok, message)
        rejected_ok, message = rejected(lambda: scene_intent.intent_capabilities(
            copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME)))
        ok("case5: raw Blueprint raises ValueError", rejected_ok, message)
        rejected_ok, message = rejected(lambda: scene_intent.intent_capabilities(None))
        ok("case5: non-mapping input raises ValueError", rejected_ok, message)
        rejected_ok, message = rejected(
            lambda: scene_intent.SceneIntentBuilder().build(blueprint, [], {"capabilities": 3}))
        ok("case5: a mapping without 'required' is rejected (no guessing)",
           rejected_ok, message)
        rejected_ok, message = rejected(
            lambda: scene_intent.SceneIntentBuilder().build(blueprint, [], {"required": 3}))
        ok("case5: a non-list 'required' is rejected", rejected_ok, message)
        rejected_ok, message = rejected(
            lambda: scene_intent.SceneIntentBuilder().build(blueprint, [], 3))
        ok("case5: a scalar declaration is rejected", rejected_ok, message)
        source = open(os.path.join(TOOL_DIR, "capability_registry.py"), encoding="utf-8").read()
        ok("case5: registry never reads a blueprint",
           "blueprint[" not in source and "blueprint.get(" not in source
           and "feature_index" not in source)

        # ---------------- Case 6: 完整链路与 1.8.9 一致 ----------------
        print("=== Case 6: full chain stays identical to 1.8.9 ===")
        out_plain = os.path.join(tmp, "chain_plain")
        plain = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                       out_dir=out_plain, bindings_path=binding_path)
        ok("case6: compose() (no declaration) still passes gate + writes",
           plain["ok"] is True and plain["compatibility"]["status"] == "PASS",
           str(plain.get("failures")))
        ok("case6: .tscn byte-identical to the 1.8.9 baseline",
           open(plain["scene_path"], encoding="utf-8", newline="").read() == goldens.GOLDEN_F3)
        # Phase 1.8.12：项目 Feature 已声明能力，故真实链路不再是空列表——
        # 无显式声明时收到的正是成员 Feature 的并集（数据驱动，非硬编码快照）。
        ok("case6: no explicit declaration -> checked_capabilities is the Feature union",
           plain["compatibility"]["checked_capabilities"] == DECLARED_BASE,
           str(plain["compatibility"]["checked_capabilities"]))

        out_declared = os.path.join(tmp, "chain_declared")
        declared_chain = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                                out_dir=out_declared, bindings_path=binding_path,
                                                capabilities=["Node", "AnimatedSprite"])
        ok("case6: compose(capabilities=[...]) declares them in the intent",
           declared_chain["scene_intent"]["capabilities"] == merged("AnimatedSprite"),
           str(declared_chain["scene_intent"].get("capabilities")))
        ok("case6: supported declaration keeps generating byte-identically",
           declared_chain["ok"] is True
           and open(declared_chain["scene_path"], encoding="utf-8", newline="").read()
           == goldens.GOLDEN_F3
           and declared_chain["compatibility"]["checked_capabilities"]
           == merged("AnimatedSprite")["required"])

        out_blocked = os.path.join(tmp, "chain_blocked")
        blocked = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                        out_dir=out_blocked, bindings_path=binding_path,
                                        capabilities=["Script"])
        ok("case6: a reserved capability blocks the real chain", blocked["ok"] is False,
           str(blocked.get("failures")))
        ok("case6: blocked failures come from the gate",
           blocked["failures"] == ["Compatibility Gate: Unsupported capability: Script"],
           str(blocked["failures"]))
        ok("case6: blocked chain writes nothing",
           not os.path.isdir(out_blocked)
           or [f for f in os.listdir(out_blocked) if f.endswith(".tscn")] == [],
           str(os.listdir(out_blocked) if os.path.isdir(out_blocked) else "<no dir>"))
        ok("case6: blocked chain still returns plan + report",
           blocked["scene_intent"]["capabilities"] == merged("Script")
           and blocked["compatibility"]["status"] == "BLOCKED")
        ok("case6: dry-run with a reserved capability is blocked too (same verdict)",
           scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME), dry_run=True,
                                  bindings_path=binding_path, capabilities=["AI"])["ok"] is False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all scene intent capability checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
