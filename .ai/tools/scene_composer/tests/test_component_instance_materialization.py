#!/usr/bin/env python3
"""Component Instance Materialization 测试（Phase 1.8.14）

链路：Feature（可选 instance:）→ Blueprint.components[].instance → Scene Intent
      → Component Instance Resolver（证据）→ Capability Contract Validator

    Case 1  旧 Intent（无 components[].instance）行为保持一致（shape / 证据 / 结论都不变）
    Case 2  contact_damage 声明 instance Area2D + children CollisionShape2D → Collision PASS
    Case 3  删除碰撞结构（instance 无碰撞证据）→ BLOCKED（逐字文案）+ 完整链路零产物
    Case 4  Sprite 组件声明 instance Sprite2D → PASS；无声明 → BLOCKED
    Case 5  声明 AnimatedSprite2D → Sprite / AnimatedSprite PASS（children 同样是证据）
    Case 6  未知 node_type / 非法声明 → "Unknown component instance type"（不猜测）
    Case 7  既有 slime_enemy 链路：.tscn / .gd 与既有产物逐字节相同

附件：Feature → Blueprint → Intent 传递（临时 features_dir）、禁止按名字猜测、
词表覆盖契约节点类型、职责隔离（不读 Blueprint / Feature Registry / .tscn / Registry）、
实例声明只是证据（Builder 输出不变）。

只读项目文件、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_component_instance_materialization.py
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

import capability_contract_validator                           # noqa: E402
import capability_contracts                                    # noqa: E402
import compatibility_gate                                      # noqa: E402
import component_instance_resolver                             # noqa: E402
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


def intent_doc(components, required, root_type: str = "Node2D",
               root_name: str = "InstanceProbe", nodes=None) -> dict:
    """构造一个最小 Scene Intent 文档（显式 components[] / capabilities.required）。"""
    return {
        "document": "scene_intent",
        "schema_version": 1,
        "scene": {"id": "instance_probe"},
        "root": {"name": root_name, "type": root_type},
        "components": copy.deepcopy(list(components)),
        "nodes": copy.deepcopy(list(nodes or [])),
        "resources": [],
        "capabilities": {"required": list(required)},
        "validation": {"required_tests": []},
    }


def instance_of(component: str, node_type: str, children=None) -> dict:
    instance = {"node_type": node_type}
    if children is not None:
        instance["children"] = list(children)
    return {"component": component, "instance": instance}


def resolver_report(scene_intent_doc):
    return component_instance_resolver.resolve_component_instance_report(scene_intent_doc)


def contract_of(scene_intent_doc):
    return capability_contract_validator.validate_capability_contract(scene_intent_doc)


def code_tokens(source: str) -> tuple:
    """源码 -> (标识符集合, 字符串常量集合)；docstring 与注释被排除（避免散文误报）。"""
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None) or []
            first = body[0] if body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                docstrings.add(id(first))
                docstrings.add(id(first.value))
    identifiers, strings = set(), set()
    for node in ast.walk(tree):
        if id(node) in docstrings:
            continue
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.add(node.value)
    return identifiers, strings


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="component_instance_")
    try:
        # ---------------- Case 1: 旧 Intent（无 instance）行为保持一致 ----------------
        print("=== Case 1: legacy Intent without components[].instance is unchanged ===")
        normalized, errors = template_loader.normalize_scene_blueprint(
            copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME))
        ok("case1: normalization declares no component instance", not errors
           and normalized["component_instances"] == {}, str(normalized.get("component_instances")))
        legacy_intent = scene_intent.SceneIntentBuilder().build(normalized)
        ok("case1: components[] entries keep exactly {'component'}",
           all(set(entry.keys()) == {"component"}
               for entry in legacy_intent.document["components"]),
           str(legacy_intent.document["components"]))
        ok("case1: intent_component_instances -> []",
           scene_intent.intent_component_instances(legacy_intent) == [])
        legacy_report = resolver_report(legacy_intent)
        ok("case1: resolver yields no instance and no error",
           legacy_report.instances == [] and legacy_report.ok, str(legacy_report.to_dict()))
        legacy_plan = capability_contract_validator.scene_plan_from_intent(legacy_intent)
        ok("case1: the plan carries empty instance evidence",
           legacy_plan["instances"] == [] and legacy_plan["instance_errors"] == [],
           str(legacy_plan))
        required = scene_intent.intent_capabilities(legacy_intent)["required"]
        legacy_contract = contract_of(legacy_intent)
        ok("case1: contract verdict unchanged (every declared capability satisfied)",
           legacy_contract.ok and legacy_contract.checked_capabilities == required,
           str((legacy_contract.to_dict(), required)))
        ok("case1: an old document without the instance key stays legal",
           contract_of(intent_doc([{"component": "health"}], ["Node"])).ok)
        ok("case1: 'instance' absent is not an error for the resolver",
           resolver_report(intent_doc([{"component": "health"}], ["Node"])).ok)

        # ---------------- Case 2: contact_damage 实例声明提供碰撞证据 ----------------
        print("=== Case 2: contact_damage instance (Area2D + CollisionShape2D) -> Collision PASS ===")
        declared = intent_doc(
            [{"component": "health"}, instance_of("contact_damage", "Area2D",
                                                  ["CollisionShape2D"])],
            ["Node", "Collision"])
        ok("case2: resolver materializes the declared instance",
           component_instance_resolver.resolve_component_instances(declared)
           == [{"component": "contact_damage", "node_type": "Area2D",
                "children": ["CollisionShape2D"]}],
           str(component_instance_resolver.resolve_component_instances(declared)))
        declared_plan = capability_contract_validator.scene_plan_from_intent(declared)
        ok("case2: instance evidence reaches the Scene Plan",
           declared_plan["instances"] == [{"component": "contact_damage", "node_type": "Area2D",
                                           "children": ["CollisionShape2D"]}],
           str(declared_plan["instances"]))
        declared_contract = contract_of(declared)
        ok("case2: Collision PASS from the instance children",
           declared_contract.ok and declared_contract.checked_capabilities == ["Node", "Collision"],
           str(declared_contract.to_dict()))
        undeclared = intent_doc([{"component": "health"}, {"component": "contact_damage"}],
                                ["Node", "Collision"])
        ok("case2: the same composition without the declaration is BLOCKED "
           "(evidence really comes from the instance)",
           contract_of(undeclared).status == "BLOCKED", str(contract_of(undeclared).to_dict()))
        parented = intent_doc([instance_of("contact_damage", "Area2D", ["CollisionShape2D"])],
                              ["Collision"])
        parented["components"][0]["instance"]["parent"] = "InstanceProbe"
        ok("case2: a declared parent is carried through the resolver",
           component_instance_resolver.resolve_component_instances(parented)
           == [{"component": "contact_damage", "node_type": "Area2D",
                "children": ["CollisionShape2D"], "parent": "InstanceProbe"}],
           str(component_instance_resolver.resolve_component_instances(parented)))

        # ---------------- Case 3: 删除碰撞结构 -> BLOCKED + 零产物 ----------------
        print("=== Case 3: instance without collision structure -> BLOCKED (zero output) ===")
        dropped = intent_doc([instance_of("contact_damage", "Node2D", [])], ["Node", "Collision"])
        dropped_contract = contract_of(dropped)
        ok("case3: BLOCKED with the exact contract message",
           dropped_contract.status == "BLOCKED"
           and dropped_contract.errors == [
               "Capability contract failed: Collision requires CollisionShape2D"],
           str(dropped_contract.to_dict()))
        ok("case3: the satisfied capability is still recorded",
           dropped_contract.checked_capabilities == ["Node"],
           str(dropped_contract.checked_capabilities))

        dropped_out = os.path.join(tmp, "case3_out")
        dropped_chain = scene_composer.compose(
            {"scene": {"id": "dropped_shape"}, "root": {"type": "Node2D", "name": "DroppedShape"},
             "components": [{"feature": "health"},
                            {"feature": "contact_damage",
                             "instance": {"node_type": "Node2D", "children": []}}],
             "validation": {"required_tests": ["health", "contact_damage"]}},
            out_dir=dropped_out)
        ok("case3: the chain stops at the contract layer",
           dropped_chain["ok"] is False
           and dropped_chain["failures"] == [
               "Capability Contract: Capability contract failed: Collision requires "
               "CollisionShape2D"],
           str(dropped_chain.get("failures")))
        ok("case3: the gate had passed first (layers stay distinct)",
           dropped_chain["compatibility"]["status"] == "PASS"
           and dropped_chain["capability_contract"]["status"] == "BLOCKED",
           str((dropped_chain["compatibility"]["status"],
                dropped_chain["capability_contract"]["status"])))
        ok("case3: the instance plan still reaches the Intent envelope",
           dropped_chain["scene_intent"]["components"][1]["instance"] == {"node_type": "Node2D"},
           str(dropped_chain["scene_intent"]["components"]))
        ok("case3: zero .tscn produced",
           not os.path.isdir(dropped_out)
           or [f for f in os.listdir(dropped_out) if f.endswith(".tscn")] == [],
           str(os.listdir(dropped_out) if os.path.isdir(dropped_out) else "<no dir>"))

        # ---------------- Case 4: Sprite 组件实例 ----------------
        print("=== Case 4: Sprite component instance ===")
        sprite = intent_doc([instance_of("sprite_body", "Sprite2D")], ["Sprite"])
        ok("case4: Sprite2D instance -> PASS",
           contract_of(sprite).ok and contract_of(sprite).checked_capabilities == ["Sprite"],
           str(contract_of(sprite).to_dict()))
        no_sprite = intent_doc([{"component": "sprite_body"}], ["Sprite"])
        ok("case4: no declaration -> BLOCKED with the sprite message",
           contract_of(no_sprite).errors == [
               "Capability contract failed: Sprite requires Sprite2D_or_AnimatedSprite2D"],
           str(contract_of(no_sprite).to_dict()))

        # ---------------- Case 5: AnimatedSprite ----------------
        print("=== Case 5: AnimatedSprite component instance ===")
        animated = intent_doc([instance_of("walk", "AnimatedSprite2D")],
                              ["Sprite", "AnimatedSprite"])
        ok("case5: AnimatedSprite2D instance satisfies Sprite and AnimatedSprite",
           contract_of(animated).ok
           and contract_of(animated).checked_capabilities == ["Sprite", "AnimatedSprite"],
           str(contract_of(animated).to_dict()))
        child_evidence = intent_doc([instance_of("walk", "Node2D", ["AnimatedSprite2D"])],
                                    ["AnimatedSprite"])
        ok("case5: instance children are evidence too", contract_of(child_evidence).ok,
           str(contract_of(child_evidence).to_dict()))
        static_only = intent_doc([instance_of("walk", "Sprite2D")], ["AnimatedSprite"])
        ok("case5: a static Sprite2D instance does not satisfy AnimatedSprite",
           contract_of(static_only).status == "BLOCKED", str(contract_of(static_only).to_dict()))

        # ---------------- Case 6: 未知 / 非法声明 ----------------
        print("=== Case 6: unknown node_type is never guessed ===")
        unknown = intent_doc([instance_of("shader_layer", "PixelRenderer")], ["Node"])
        unknown_report = resolver_report(unknown)
        ok("case6: resolver reports the unknown type and yields no instance",
           unknown_report.errors == ["Unknown component instance type: PixelRenderer"]
           and unknown_report.instances == [], str(unknown_report.to_dict()))
        unknown_contract = contract_of(unknown)
        ok("case6: BLOCKED with nothing passed through",
           unknown_contract.errors == ["Unknown component instance type: PixelRenderer"]
           and unknown_contract.checked_capabilities == [],
           str(unknown_contract.to_dict()))
        empty = intent_doc([{"component": "probe", "instance": {}}], ["Node"])
        ok("case6: a declared but empty instance never passes",
           resolver_report(empty).errors == ["Unknown component instance type: <missing>"],
           str(resolver_report(empty).to_dict()))
        malformed = intent_doc([{"component": "probe", "instance": "Sprite2D"}], ["Node"])
        ok("case6: a non-mapping declaration is reported, not dropped",
           resolver_report(malformed).errors == ["Invalid component instance: probe"],
           str(resolver_report(malformed).to_dict()))
        bad_parent = intent_doc([{"component": "probe",
                                  "instance": {"node_type": "Sprite2D", "parent": 3}}], ["Node"])
        ok("case6: a non-string parent is reported",
           resolver_report(bad_parent).errors == ["Invalid component instance: probe"],
           str(resolver_report(bad_parent).to_dict()))
        unknown_child = intent_doc([instance_of("probe", "Node2D", ["PixelRenderer"])], ["Node"])
        ok("case6: unknown children are reported too",
           resolver_report(unknown_child).errors == [
               "Unknown component instance type: PixelRenderer"],
           str(resolver_report(unknown_child).to_dict()))
        unknown_out = os.path.join(tmp, "case6_out")
        unknown_chain = scene_composer.compose(
            {"scene": {"id": "unknown_instance"}, "root": {"type": "Node2D", "name": "UnknownInstance"},
             "components": [{"feature": "health",
                             "instance": {"node_type": "PixelRenderer"}}],
             "validation": {"required_tests": ["health"]}},
            out_dir=unknown_out)
        ok("case6: the full chain blocks with the resolver message",
           unknown_chain["ok"] is False
           and unknown_chain["failures"] == [
               "Capability Contract: Unknown component instance type: PixelRenderer"],
           str(unknown_chain.get("failures")))
        ok("case6: zero .tscn produced for an unknown instance type",
           not os.path.isdir(unknown_out)
           or [f for f in os.listdir(unknown_out) if f.endswith(".tscn")] == [],
           str(os.listdir(unknown_out) if os.path.isdir(unknown_out) else "<no dir>"))

        # ---------------- Case 7: 既有 slime_enemy 产物逐字节相同 ----------------
        print("=== Case 7: existing slime_enemy chain is byte-identical ===")
        binding_path = goldens.write_binding(tmp, goldens.BINDING_SLIME)
        slime = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                       out_dir=os.path.join(tmp, "case7_out"),
                                       bindings_path=binding_path)
        ok("case7: golden fixture chain passes both layers",
           slime["ok"] is True
           and slime["compatibility"]["status"] == "PASS"
           and slime["capability_contract"]["status"] == "PASS",
           str(slime.get("failures")))
        ok("case7: legacy chain carries no instance evidence",
           all("instance" not in entry for entry in slime["scene_intent"]["components"]),
           str(slime["scene_intent"]["components"]))
        ok("case7: generated .tscn byte-identical to the pre-phase golden",
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
           hashlib.sha256(repo_scene).hexdigest().startswith("f87bc2b0c9613ac5"),
           hashlib.sha256(repo_scene).hexdigest())

        # ---------------- 附件：Feature → Blueprint → Intent 传递 ----------------
        print("=== Extra: Feature -> Blueprint -> Intent transport ===")
        features_dir = os.path.join(tmp, "features")
        os.makedirs(os.path.join(features_dir, "probe_instanced"))
        with open(os.path.join(features_dir, "probe_instanced", "feature.yaml"), "w",
                  encoding="utf-8") as f:
            f.write("id: probe_instanced\nversion: 1\ncategory: component\n"
                    "capabilities:\n  required:\n    - Node\n    - Collision\n")
        with open(os.path.join(features_dir, "probe_instanced", "template.yaml"), "w",
                  encoding="utf-8") as f:
            f.write("feature:\n  id: probe_instanced\nscene:\n  source: ProbeInstanced.tscn\n"
                    "validation:\n  required_nodes:\n    - ProbeInstanced\n"
                    "instance:\n  node_type: Area2D\n  children:\n    - CollisionShape2D\n")
        feature_bp = {"scene": {"id": "feature_instance"},
                      "root": {"type": "Node2D", "name": "FeatureInstance"},
                      "components": [{"feature": "probe_instanced"}],
                      "validation": {"required_tests": ["probe_instanced"]}}
        feature_normalized, feature_errors = template_loader.normalize_scene_blueprint(
            copy.deepcopy(feature_bp), features_dir)
        ok("extra: a Feature template instance block reaches the Blueprint",
           not feature_errors
           and feature_normalized["component_instances"]
           == {"probe_instanced": {"node_type": "Area2D", "children": ["CollisionShape2D"]}},
           str((feature_errors, feature_normalized.get("component_instances"))))
        feature_intent = scene_intent.SceneIntentBuilder().build(feature_normalized)
        ok("extra: ... and is materialized in the Scene Intent",
           feature_intent.document["components"]
           == [{"component": "probe_instanced",
                "instance": {"node_type": "Area2D", "children": ["CollisionShape2D"]}}],
           str(feature_intent.document["components"]))
        feature_contract = contract_of(feature_intent)
        ok("extra: Feature-declared instance satisfies its own capability declaration",
           feature_contract.ok
           and feature_contract.checked_capabilities == ["Node", "Collision"],
           str(feature_contract.to_dict()))
        explicit_bp = copy.deepcopy(feature_bp)
        explicit_bp["components"][0]["instance"] = {"node_type": "CollisionShape2D"}
        explicit_normalized, _ = template_loader.normalize_scene_blueprint(
            explicit_bp, features_dir)
        ok("extra: an explicit Blueprint declaration wins over the template",
           explicit_normalized["component_instances"]
           == {"probe_instanced": {"node_type": "CollisionShape2D"}},
           str(explicit_normalized["component_instances"]))
        ok("extra: a template without an instance block declares nothing",
           template_loader.feature_instance_plan("probe_instanced") == {}
           and template_loader.feature_instance_plan("health") == {},
           str(template_loader.feature_instance_plan("health")))

        # ---------------- 附件：不猜测 / 词表 / 职责隔离 / Builder 不变 ----------------
        print("=== Extra: no guessing, vocabulary, isolation, Builder untouched ===")
        suspicious = intent_doc([{"component": "contact_damage"}, {"component": "sprite_body"},
                                 {"component": "audio_sfx"}], ["Node"])
        ok("extra: component ids are never inspected for instance guessing",
           resolver_report(suspicious).instances == [] and resolver_report(suspicious).ok,
           str(resolver_report(suspicious).to_dict()))
        contract_types = set()
        for name in capability_contracts.contract_names():
            contract_types.update(capability_contracts.contract_for(name).get("node_types") or ())
        vocabulary = set(component_instance_resolver.instance_node_types())
        ok("extra: the instance vocabulary covers every contract node type",
           contract_types <= vocabulary, str(sorted(contract_types - vocabulary)))
        ok("extra: the vocabulary excludes the unimplemented Animation layer",
           not [name for name in vocabulary
                if name in ("AnimationPlayer", "AnimationTree")], str(sorted(vocabulary)))
        ok("extra: node types are matched case-insensitively",
           component_instance_resolver.is_known_instance_type(" sprite2d ")
           and not component_instance_resolver.is_known_instance_type("PixelRenderer"))
        rejected_ok, message = rejected(
            lambda: component_instance_resolver.resolve_component_instances(
                copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME)))
        ok("extra: raw Blueprint input is rejected (single Intent boundary)",
           rejected_ok, message)

        resolver_source = open(os.path.join(TOOL_DIR, "component_instance_resolver.py"),
                               encoding="utf-8").read()
        identifiers, strings = code_tokens(resolver_source)
        forbidden = {"open", "yaml", "feature_index", "template_loader", "capability_registry",
                     "blueprint"}
        ok("extra: the resolver code never opens files / imports registry or templates",
           not (identifiers & forbidden), str(sorted(identifiers & forbidden)))
        ok("extra: the resolver code never references a .tscn path",
           not [text for text in strings if ".tscn" in text], str(sorted(strings)))
        tree = ast.parse(resolver_source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        ok("extra: resolver imports stay inside the plan layer",
           imported <= {"scene_intent", "sys"}, str(sorted(imported)))

        # 声明必须能被生成物确认（Phase 1.8.15 起 Artifact Evidence Verification 核对
        # 生成后的 .tscn；此处用确实会出现在生成物里的 CollisionShape2D，即 SlimeShape）。
        declared_slime = copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME)
        declared_slime["components"][1]["instance"] = {"node_type": "CollisionShape2D"}
        declared_chain = scene_composer.compose(
            declared_slime, out_dir=os.path.join(tmp, "declared_out"), bindings_path=binding_path)
        ok("extra: instance declarations change neither the .tscn nor the verdict",
           declared_chain["ok"] is True
           and open(declared_chain["scene_path"], "rb").read()
           == goldens.GOLDEN_F3.encode("utf-8"),
           str(declared_chain.get("failures")))
        ok("extra: ... the artifact layer confirms the declared structure",
           declared_chain["artifact_evidence"]["status"] == "PASS"
           and declared_chain["artifact_evidence"]["checked_instances"] == ["contact_damage"],
           str(declared_chain.get("artifact_evidence")))
        ok("extra: ... while the plan still carries the instance",
           declared_chain["scene_intent"]["components"][1]["instance"]
           == {"node_type": "CollisionShape2D"},
           str(declared_chain["scene_intent"]["components"]))
        declared_gd = generate_scene_test.build_test_source(
            scene_intent.intent_document(declared_chain["scene_intent"]),
            template_loader.load_templates(goldens.FEATURES), "Scenes/SlimeEnemy.tscn")
        ok("extra: the generated .gd is unaffected by instance declarations",
           declared_gd == repo_gd)
        ok("extra: components[].node / .scene stay PLANNED (never derived here)",
           all("node" not in entry and "scene" not in entry
               for entry in declared_chain["scene_intent"]["components"]),
           str(declared_chain["scene_intent"]["components"]))
        gated = compatibility_gate.check_scene_compatibility(
            scene_intent.intent_document(declared_chain["scene_intent"]))
        ok("extra: the gate reads no instance data (only capabilities/components/resources)",
           gated.ok and gated.checked_components == goldens.FEATURES,
           str(gated.to_dict()))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all component instance materialization checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
