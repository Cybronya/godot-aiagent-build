#!/usr/bin/env python3
"""Capability Contract Validation 测试（Phase 1.8.13）

链路：Scene Intent → Compatibility Gate（ability availability）→ Capability Contract
Validation（plan fulfillment）→ Scene Builder

    Case 1  Node 契约 + 计划含 root 节点 → PASS
    Case 2  Collision 契约 + 计划含 CollisionShape2D → PASS
    Case 3  Collision 契约 + 计划无碰撞证据 → BLOCKED（逐字错误文案）+ 完整链路零产物
    Case 4  Sprite 契约：Sprite2D → PASS；AnimatedSprite2D → PASS
    Case 5  未知能力 → BLOCKED（"Unknown capability contract: ..."）；预留能力 → not implemented
    Case 6  真实 Feature 链路（contact_damage：Node + Collision）→ Gate PASS 且 Contract PASS
    Case 7  既有 slime_enemy 生成结果与既有产物逐字节相同（.tscn / .gd）

附件：契约表与能力词表的同步、Scene Plan 证据来源（不读 resources[] 除非契约需要）、
职责隔离（不读 Blueprint / Feature Registry / .tscn）。

只读项目文件、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_capability_contract_validator.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import ast
import copy
import hashlib
import os
import shutil
import sys
import tempfile

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))                 # .ai/tools/scene_composer/tests
TOOL_DIR = os.path.dirname(_HERE)                                  # .ai/tools/scene_composer
TOOLS_DIR = os.path.dirname(TOOL_DIR)                              # .ai/tools
TEST_GEN_DIR = os.path.join(TOOLS_DIR, "test_generator")
DOTAI = os.path.dirname(TOOLS_DIR)                                 # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)

for path in (TOOL_DIR, TOOLS_DIR, TEST_GEN_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import capability_contracts                                     # noqa: E402
import capability_contract_validator                           # noqa: E402
import capability_registry                                     # noqa: E402
import compatibility_gate                                      # noqa: E402
import generate_scene_test                                     # noqa: E402
import scene_composer                                          # noqa: E402
import scene_intent                                            # noqa: E402
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


def intent_with(pairs, root_type: str = "Node2D") -> dict:
    """构造一个最小 Scene Intent 文档（显式 capabilities.required + root 类型）。"""
    required = []
    for name in pairs:
        if name not in required:
            required.append(name)
    return {
        "document": "scene_intent",
        "schema_version": 1,
        "scene": {"id": "contract_probe"},
        "root": {"name": "ContractProbe", "type": root_type},
        "components": [],
        "nodes": [],
        "resources": [],
        "capabilities": {"required": required},
        "validation": {"required_tests": []},
    }


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="capability_contract_")
    try:
        # ---------------- Case 1: Node 契约 ----------------
        print("=== Case 1: Node contract (root node exists) ===")
        node_report = capability_contract_validator.validate_capability_contract(
            intent_with(["Node"]))
        ok("case1: root node exists -> PASS",
           node_report.ok and node_report.checked_capabilities == ["Node"],
           str(node_report.to_dict()))
        no_root = intent_with(["Node"])
        no_root["root"] = {"name": "", "type": ""}
        blocked_root = capability_contract_validator.validate_capability_contract(no_root)
        ok("case1: missing root -> BLOCKED with the contract message",
           blocked_root.status == "BLOCKED"
           and blocked_root.errors == ["Capability contract failed: Node requires node_exists"],
           str(blocked_root.to_dict()))
        explicit_plan = capability_contract_validator.validate_capability_contract(
            intent_with(["Node"]), {"root": {"name": "X", "type": "Node2D"}})
        ok("case1: an explicit scene plan is accepted", explicit_plan.ok,
           str(explicit_plan.to_dict()))

        # ---------------- Case 2: Collision 契约（有证据） ----------------
        print("=== Case 2: Collision contract with CollisionShape2D evidence ===")
        shape_plan = {"root": {"name": "Enemy", "type": "Node2D"},
                      "nodes": [{"name": "EnemyShape", "type": "CollisionShape2D"}]}
        shape_report = capability_contract_validator.validate_capability_contract(
            intent_with(["Node", "Collision"]), shape_plan)
        ok("case2: CollisionShape2D in the plan -> PASS",
           shape_report.ok and shape_report.checked_capabilities == ["Node", "Collision"],
           str(shape_report.to_dict()))
        body_report = capability_contract_validator.validate_capability_contract(
            intent_with(["Collision"]), {"root": {"name": "Enemy", "type": "CharacterBody2D"}})
        ok("case2: a physics body node is an equivalent collision expression",
           body_report.ok, str(body_report.to_dict()))

        # ---------------- Case 3: Collision 契约（无证据） ----------------
        print("=== Case 3: Collision contract without any collision evidence ===")
        no_evidence = capability_contract_validator.validate_capability_contract(
            intent_with(["Node", "Collision"]),
            {"root": {"name": "Enemy", "type": "Node2D"}, "nodes": []})
        ok("case3: BLOCKED with the exact contract message",
           no_evidence.status == "BLOCKED"
           and no_evidence.errors == [
               "Capability contract failed: Collision requires CollisionShape2D"],
           str(no_evidence.to_dict()))
        ok("case3: satisfied capabilities are still recorded",
           no_evidence.checked_capabilities == ["Node"],
           str(no_evidence.checked_capabilities))

        # 完整链路：Gate PASS 之后由 Contract 拦截，且零产物
        no_shape_out = os.path.join(tmp, "case3_out")
        no_shape = scene_composer.compose(
            {"scene": {"id": "no_shape"}, "root": {"type": "Node2D", "name": "NoShape"},
             "components": [{"feature": "health"}, {"feature": "contact_damage"}],
             "validation": {"required_tests": ["health", "contact_damage"]}},
            out_dir=no_shape_out)
        ok("case3: chain stops at the contract layer",
           no_shape["ok"] is False
           and no_shape["failures"] == [
               "Capability Contract: Capability contract failed: Collision requires "
               "CollisionShape2D"],
           str(no_shape.get("failures")))
        ok("case3: gate had passed first (layers stay distinct)",
           no_shape["compatibility"]["status"] == "PASS"
           and no_shape["capability_contract"]["status"] == "BLOCKED",
           str((no_shape["compatibility"]["status"],
                no_shape["capability_contract"]["status"])))
        ok("case3: zero .tscn produced",
           not os.path.isdir(no_shape_out)
           or [f for f in os.listdir(no_shape_out) if f.endswith(".tscn")] == [],
           str(os.listdir(no_shape_out) if os.path.isdir(no_shape_out) else "<no dir>"))

        # ---------------- Case 4: Sprite 契约 ----------------
        print("=== Case 4: Sprite contract ===")
        sprite2d = capability_contract_validator.validate_capability_contract(
            intent_with(["Sprite"]),
            {"root": {"name": "Enemy", "type": "Node2D"},
             "nodes": [{"name": "Body", "type": "Sprite2D"}]})
        ok("case4: Sprite2D -> PASS", sprite2d.ok, str(sprite2d.to_dict()))
        animated = capability_contract_validator.validate_capability_contract(
            intent_with(["Sprite"]),
            {"root": {"name": "Enemy", "type": "Node2D"},
             "resource_nodes": [{"name": "EnemyAnim", "type": "AnimatedSprite2D"}]})
        ok("case4: AnimatedSprite2D -> PASS", animated.ok, str(animated.to_dict()))
        no_sprite = capability_contract_validator.validate_capability_contract(
            intent_with(["Sprite"]), {"root": {"name": "Enemy", "type": "Node2D"}})
        ok("case4: no sprite node -> BLOCKED",
           no_sprite.status == "BLOCKED"
           and no_sprite.errors == [
               "Capability contract failed: Sprite requires Sprite2D_or_AnimatedSprite2D"],
           str(no_sprite.to_dict()))
        animated_only = capability_contract_validator.validate_capability_contract(
            intent_with(["AnimatedSprite"]),
            {"root": {"name": "Enemy", "type": "Node2D"},
             "nodes": [{"name": "Body", "type": "Sprite2D"}]})
        ok("case4: AnimatedSprite is not satisfied by a static Sprite2D",
           animated_only.status == "BLOCKED", str(animated_only.to_dict()))

        # ---------------- Case 5: 未知 / 预留能力 ----------------
        print("=== Case 5: unknown and reserved capabilities ===")
        unknown = capability_contract_validator.validate_capability_contract(
            intent_with(["QuantumRenderer"]))
        ok("case5: unknown capability -> BLOCKED, never guessed",
           unknown.status == "BLOCKED"
           and unknown.errors == ["Unknown capability contract: QuantumRenderer"],
           str(unknown.to_dict()))
        for name in capability_registry.RESERVED_CAPABILITIES:
            reserved = capability_contract_validator.validate_capability_contract(
                intent_with([name]))
            ok("case5: reserved capability %r -> not implemented" % name,
               reserved.status == "BLOCKED"
               and reserved.errors == ["Capability contract not implemented: %s" % name],
               str(reserved.to_dict()))

        # ---------------- Case 6: 真实 Feature 链路 ----------------
        print("=== Case 6: real Feature chain (contact_damage: Node + Collision) ===")
        real_out = os.path.join(tmp, "case6_out")
        real_bp = {"scene": {"id": "contact_probe"},
                   "root": {"type": "CharacterBody2D", "name": "ContactProbe"},
                   "components": [{"feature": "health"}, {"feature": "contact_damage"}],
                   "validation": {"required_tests": ["health", "contact_damage"]}}
        real = scene_composer.compose(copy.deepcopy(real_bp), out_dir=real_out)
        declared = capability_contract_labels = [
            "Node", "Collision"]        # health=[Node]；contact_damage=[Node, Collision]
        ok("case6: Feature declarations reach the Intent",
           real["scene_intent"]["capabilities"] == {"required": declared},
           str(real["scene_intent"].get("capabilities")))
        ok("case6: Gate PASS (availability)",
           real["compatibility"]["status"] == "PASS"
           and real["compatibility"]["checked_capabilities"] == declared,
           str(real["compatibility"]))
        ok("case6: Contract PASS (fulfillment) and both capabilities recorded",
           real["capability_contract"]["status"] == "PASS"
           and real["capability_contract"]["checked_capabilities"] == declared,
           str(real["capability_contract"]))
        ok("case6: the scene is generated", real["ok"] is True
           and os.path.isfile(real["scene_path"]), str(real.get("failures")))

        # ---------------- Case 7: 既有 slime_enemy 产物逐字节相同 ----------------
        print("=== Case 7: existing slime_enemy scene is byte-identical ===")
        binding_path = goldens.write_binding(tmp, goldens.BINDING_SLIME)
        slime = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                       out_dir=os.path.join(tmp, "case7_out"),
                                       bindings_path=binding_path)
        ok("case7: golden fixture chain passes both layers",
           slime["ok"] is True
           and slime["compatibility"]["status"] == "PASS"
           and slime["capability_contract"]["status"] == "PASS",
           str(slime.get("failures")))
        ok("case7: generated .tscn byte-identical to the pre-contract golden",
           open(slime["scene_path"], "rb").read() == goldens.GOLDEN_F3.encode("utf-8"))
        generated_gd = generate_scene_test.build_test_source(
            scene_intent.intent_document(slime["scene_intent"]),
            template_loader.load_templates(goldens.FEATURES), "Scenes/SlimeEnemy.tscn")
        repo_gd = open(os.path.join(PROJECT_ROOT, "Tests", "test_slime_enemy.gd"),
                       encoding="utf-8", newline="").read()
        ok("case7: generated .gd byte-identical to the committed test",
           generated_gd == repo_gd)
        repo_chain = scene_composer.compose(
            yaml.safe_load(open(os.path.join(PROJECT_ROOT, "slime_enemy.yaml"),
                                encoding="utf-8")),
            out_dir=os.path.join(tmp, "case7_repo_out"),
            bindings_path=os.path.join(DOTAI, "context", "asset_bindings", "slime_enemy.yaml"))
        repo_scene = open(os.path.join(PROJECT_ROOT, "Scenes", "SlimeEnemy.tscn"), "rb").read()
        ok("case7: regenerating the committed scene is byte-identical",
           repo_chain["ok"] is True
           and open(repo_chain["scene_path"], "rb").read() == repo_scene,
           str(repo_chain.get("failures")))
        ok("case7: committed scene sha256 unchanged",
           hashlib.sha256(repo_scene).hexdigest().startswith("ddd33c1db5359c3d"),
           hashlib.sha256(repo_scene).hexdigest())

        # ---------------- 附件：契约表 / 证据 / 职责隔离 ----------------
        print("=== Extra: contract table integrity, evidence source, isolation ===")
        contract_names = set(capability_contracts.contract_names())
        vocabulary = set(capability_registry.SUPPORTED_COMPONENT_CAPABILITIES) \
            | set(capability_registry.RESERVED_CAPABILITIES)
        ok("extra: every contract name is a registry-known capability",
           contract_names <= vocabulary, str(sorted(contract_names - vocabulary)))
        ok("extra: every supported/reserved capability has a contract",
           vocabulary <= contract_names, str(sorted(vocabulary - contract_names)))
        ok("extra: support status is not decided by the contract table",
           all(capability_contracts.contract_for(name) is not None
               for name in capability_registry.SUPPORTED_COMPONENT_CAPABILITIES)
           and capability_contracts.contract_for("QuantumRenderer") is None)

        slime_plan_no_resources = capability_contract_validator.scene_plan_from_intent(
            slime["scene_intent"])
        ok("extra: resources[] are not read unless a contract needs them",
           slime_plan_no_resources["resource_nodes"] == []
           and slime["scene_intent"]["resources"], str(slime_plan_no_resources))
        with_resources = capability_contract_validator.scene_plan_from_intent(
            slime["scene_intent"], include_resource_nodes=True)
        ok("extra: resource nodes are available when requested (Binding-derived)",
           [entry["type"] for entry in with_resources["resource_nodes"]]
           == ["AnimatedSprite2D", "AudioStreamPlayer"],
           str(with_resources["resource_nodes"]))
        ok("extra: the plan mirrors the Intent structure (root/nodes/components)",
           with_resources["root"] == {"name": "SlimeEnemy", "type": "CharacterBody2D"}
           and [entry["component"] for entry in with_resources["components"]]
           == goldens.FEATURES
           and [entry["type"] for entry in with_resources["nodes"]] == ["CollisionShape2D"],
           str(with_resources))
        rejected_ok, message = rejected(
            lambda: capability_contract_validator.validate_capability_contract(
                copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME)))
        ok("extra: raw Blueprint input is rejected (single Intent boundary)",
           rejected_ok, message)
        rejected_ok, message = rejected(
            lambda: capability_contract_validator.validate_capability_contract(
                intent_with(["Node"]), ["not-a-plan"]))
        ok("extra: a non-mapping scene plan is rejected", rejected_ok, message)

        for module in ("capability_contracts.py", "capability_contract_validator.py"):
            source = open(os.path.join(TOOL_DIR, module), encoding="utf-8").read()
            tree = ast.parse(source)
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add((node.module or "").split(".")[0])
            # Phase 1.8.14 起 validator 消费 component_instance_resolver（实例计划 = 优先证据）；
            # 允许集合仍是封闭的 plan 层模块列表。
            ok("extra: %s imports stay inside the plan layer" % module,
               imported <= {"scene_intent", "capability_contracts",
                            "component_instance_resolver", "sys"},
               str(sorted(imported)))
            ok("extra: %s never opens files / reads the registry index" % module,
               "open(" not in source and "feature_index" not in source
               and "template_loader" not in source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all capability contract checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
