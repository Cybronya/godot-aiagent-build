#!/usr/bin/env python3
"""Artifact Evidence Verification 测试（Phase 1.8.15）

链路：Scene Intent（components[].instance）→ Capability Contract → Scene Builder
      → Artifact Evidence Verification（生成物静态核验）

    Case 1  声明 Node2D，生成物含 Node2D → PASS
    Case 2  Collision 声明 Area2D + children CollisionShape2D，生成物含完整结构 → PASS
    Case 3  生成物缺 CollisionShape2D → BLOCKED（逐字文案）
    Case 4  生成物节点类型不匹配（声明 Sprite2D，生成 Node2D）→ BLOCKED
    Case 5  既有 slime_enemy 链路：PASS 且 .tscn / .gd 逐字节不变
    Case 6  无 components[].instance → 保持旧行为（PASS，不核验）

附件：完整链路（写盘后拦截、保留产物、前两层结论独立）、挂载关系核验、可读性失败、
声明不影响生成、真实生成物静态解析覆盖、职责隔离（不读 Blueprint / Registry / Godot）。

只读项目文件、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_artifact_evidence_validator.py
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

import artifact_evidence_validator                              # noqa: E402
import capability_contract_validator                            # noqa: E402
import generate_scene_test                                      # noqa: E402
import scene_composer                                           # noqa: E402
import scene_intent                                             # noqa: E402
import template_loader                                          # noqa: E402
import test_scene_builder_intent_input as goldens               # noqa: E402

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


def intent_doc(components, required=None, root_type: str = "Node2D",
               root_name: str = "InstProbe", nodes=None) -> dict:
    """构造一个最小 Scene Intent 文档（显式 components[] / capabilities.required）。"""
    return {
        "document": "scene_intent",
        "schema_version": 1,
        "scene": {"id": "artifact_probe"},
        "root": {"name": root_name, "type": root_type},
        "components": copy.deepcopy(list(components)),
        "nodes": copy.deepcopy(list(nodes or [])),
        "resources": [],
        "capabilities": {"required": list(required or [])},
        "validation": {"required_tests": []},
    }


def instance_entry(component: str, node_type: str, children=None, parent=None) -> dict:
    instance = {"node_type": node_type}
    if children is not None:
        instance["children"] = list(children)
    if parent is not None:
        instance["parent"] = parent
    return {"component": component, "instance": instance}


def write_artifact(tmp: str, name: str, text: str) -> str:
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def verify(scene_intent_doc, scene_path):
    return artifact_evidence_validator.verify_artifact_evidence(scene_intent_doc, scene_path)


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="artifact_evidence_")
    try:
        # ---------------- Case 1: 声明 Node2D，生成物含 Node2D ----------------
        print("=== Case 1: declared Node2D is present in the artifact ===")
        node2d_intent = intent_doc([instance_entry("probe_body", "Node2D")], ["Node"])
        node2d_artifact = write_artifact(tmp, "case1.tscn",
                                         "[gd_scene load_steps=1 format=3]\n\n"
                                         "[node name=\"InstProbe\" type=\"Node2D\"]\n")
        case1 = verify(node2d_intent, node2d_artifact)
        ok("case1: declared node type found -> PASS",
           case1.ok and case1.checked_instances == ["probe_body"], str(case1.to_dict()))
        # Phase 1.8.16 / 1.8.17 起报告依次追加 checked_external_artifacts / checked_ownership
        ok("case1: report exposes the documented keys",
           sorted(case1.to_dict()) == ["checked_external_artifacts", "checked_instances",
                                       "checked_ownership", "errors", "status"],
           str(sorted(case1.to_dict())))
        ok("case1: the resolved ownership is carried in the report",
           case1.checked_ownership == [{"component": "probe_body",
                                        "artifact_path": os.path.abspath(node2d_artifact),
                                        "node_path": "", "confidence": "resolved"}],
           str(case1.checked_ownership))

        # ---------------- Case 2: Collision 声明 + 生成物完整结构 ----------------
        print("=== Case 2: Collision instance (Area2D + CollisionShape2D) matches the artifact ===")
        collision_intent = intent_doc(
            [instance_entry("contact_damage", "Area2D", ["CollisionShape2D"])],
            ["Node", "Collision"])
        full_artifact = write_artifact(
            tmp, "case2.tscn",
            "[gd_scene load_steps=2 format=3]\n\n"
            "[node name=\"InstProbe\" type=\"Node2D\"]\n\n"
            "[node name=\"ContactDamage\" type=\"Area2D\" parent=\".\"]\n\n"
            "[node name=\"ContactShape\" type=\"CollisionShape2D\" parent=\"ContactDamage\"]\n")
        case2 = verify(collision_intent, full_artifact)
        ok("case2: declared structure is verified -> PASS",
           case2.ok and case2.checked_instances == ["contact_damage"], str(case2.to_dict()))
        ok("case2: the plan layer agrees (declaration is real evidence)",
           capability_contract_validator.validate_capability_contract(collision_intent).ok)

        # ---------------- Case 3: 生成物缺 CollisionShape2D ----------------
        print("=== Case 3: the artifact is missing CollisionShape2D ===")
        missing_shape = write_artifact(
            tmp, "case3.tscn",
            "[gd_scene load_steps=1 format=3]\n\n"
            "[node name=\"InstProbe\" type=\"Node2D\"]\n\n"
            "[node name=\"ContactDamage\" type=\"Area2D\" parent=\".\"]\n")
        case3 = verify(collision_intent, missing_shape)
        ok("case3: BLOCKED with the exact message",
           case3.status == "BLOCKED"
           and case3.errors == ["Artifact evidence mismatch: CollisionShape2D missing"],
           str(case3.to_dict()))
        ok("case3: nothing is recorded as checked", case3.checked_instances == [],
           str(case3.checked_instances))

        # ---------------- Case 4: 类型不匹配 ----------------
        print("=== Case 4: the artifact node type does not match the declaration ===")
        sprite_intent = intent_doc([instance_entry("sprite_body", "Sprite2D")], ["Sprite"])
        plain_artifact = write_artifact(
            tmp, "case4.tscn",
            "[gd_scene load_steps=1 format=3]\n\n"
            "[node name=\"InstProbe\" type=\"Node2D\"]\n\n"
            "[node name=\"Body\" type=\"Node2D\" parent=\".\"]\n")
        case4 = verify(sprite_intent, plain_artifact)
        ok("case4: declared Sprite2D vs generated Node2D -> BLOCKED",
           case4.status == "BLOCKED"
           and case4.errors == ["Artifact evidence mismatch: Sprite2D missing"],
           str(case4.to_dict()))
        animated_artifact = write_artifact(
            tmp, "case4b.tscn",
            "[gd_scene load_steps=1 format=3]\n\n"
            "[node name=\"InstProbe\" type=\"Node2D\"]\n\n"
            "[node name=\"Body\" type=\"AnimatedSprite2D\" parent=\".\"]\n")
        near_miss = verify(sprite_intent, animated_artifact)
        ok("case4: a near-miss type is not accepted as a substitute",
           near_miss.status == "BLOCKED"
           and near_miss.errors == ["Artifact evidence mismatch: Sprite2D missing"],
           str(near_miss.to_dict()))

        # ---------------- Case 5: 既有 slime_enemy 链路 ----------------
        print("=== Case 5: the existing slime_enemy chain passes and stays byte-identical ===")
        binding_path = goldens.write_binding(tmp, goldens.BINDING_SLIME)
        slime = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                       out_dir=os.path.join(tmp, "case5_out"),
                                       bindings_path=binding_path)
        ok("case5: chain still succeeds",
           slime["ok"] is True and slime["artifact_evidence"]["status"] == "PASS",
           str((slime.get("failures"), slime.get("artifact_evidence"))))
        ok("case5: legacy chain declares no instance (nothing to verify)",
           slime["artifact_evidence"] == {"status": "PASS", "errors": [],
                                          "checked_instances": [],
                                          "checked_external_artifacts": [],
                                          "checked_ownership": []},
           str(slime["artifact_evidence"]))
        ok("case5: generated .tscn byte-identical to the pre-phase golden",
           open(slime["scene_path"], "rb").read() == goldens.GOLDEN_F3.encode("utf-8"))
        generated_gd = generate_scene_test.build_test_source(
            scene_intent.intent_document(slime["scene_intent"]),
            template_loader.load_templates(goldens.FEATURES), "Scenes/SlimeEnemy.tscn")
        repo_gd = open(os.path.join(PROJECT_ROOT, "Tests", "test_slime_enemy.gd"),
                       encoding="utf-8", newline="").read()
        ok("case5: generated .gd byte-identical to the committed test", generated_gd == repo_gd)
        repo_chain = scene_composer.compose(
            yaml.safe_load(open(os.path.join(PROJECT_ROOT, "slime_enemy.yaml"),
                               encoding="utf-8")),
            out_dir=os.path.join(tmp, "case5_repo_out"),
            bindings_path=os.path.join(DOTAI, "context", "asset_bindings", "slime_enemy.yaml"))
        repo_scene = open(os.path.join(PROJECT_ROOT, "Scenes", "SlimeEnemy.tscn"), "rb").read()
        ok("case5: regenerating the committed scene is byte-identical",
           repo_chain["ok"] is True
           and open(repo_chain["scene_path"], "rb").read() == repo_scene,
           str(repo_chain.get("failures")))
        ok("case5: committed scene sha256 unchanged",
           hashlib.sha256(repo_scene).hexdigest().startswith("f87bc2b0c9613ac5"),
           hashlib.sha256(repo_scene).hexdigest())

        # ---------------- Case 6: 无声明 → 旧行为 ----------------
        print("=== Case 6: no declaration keeps the old behaviour ===")
        legacy_intent = intent_doc([{"component": "health"}], ["Node"])
        ok("case6: nothing to verify -> PASS with empty checked lists",
           verify(legacy_intent, missing_shape).to_dict() == {
               "status": "PASS", "errors": [], "checked_instances": [],
               "checked_external_artifacts": [], "checked_ownership": []},
           str(verify(legacy_intent, missing_shape).to_dict()))
        ok("case6: an undeclared plan does not even read the artifact (missing path is fine)",
           verify(legacy_intent, os.path.join(tmp, "does_not_exist.tscn")).ok)
        ok("case6: 'instance: null' is treated as undeclared",
           verify(intent_doc([{"component": "health", "instance": None}], ["Node"]),
                  os.path.join(tmp, "does_not_exist.tscn")).ok)

        # ---------------- 附件：完整链路（写盘后拦截、保留产物） ----------------
        print("=== Extra: full chain blocks after writing and keeps the artifact ===")
        declared_bp = {"scene": {"id": "artifact_block"}, "root": {"type": "Node2D",
                                                                   "name": "ArtifactBlock"},
                       "components": [{"feature": "health"},
                                      {"feature": "contact_damage",
                                       "instance": {"node_type": "Area2D",
                                                    "children": ["CollisionShape2D"]}}],
                       "validation": {"required_tests": ["health", "contact_damage"]}}
        blocked_out = os.path.join(tmp, "extra_blocked_out")
        blocked_chain = scene_composer.compose(copy.deepcopy(declared_bp), out_dir=blocked_out)
        # Phase 1.8.16：Area2D 由 ExtResource 指向的组件场景确认，缺失的只剩宿主未提供的子节点
        ok("extra: the artifact layer is what blocks",
           blocked_chain["ok"] is False
           and blocked_chain["failures"] == [
               "Artifact Evidence: Artifact evidence mismatch: CollisionShape2D missing"],
           str(blocked_chain.get("failures")))
        ok("extra: the declared component node was confirmed in the external scene",
           blocked_chain["artifact_evidence"]["checked_external_artifacts"] == [
               "res://Features/health/Health.tscn",
               "res://Features/contact_damage/ContactDamage.tscn"],
           str(blocked_chain["artifact_evidence"]))
        ok("extra: the earlier layers still judged independently",
           blocked_chain["compatibility"]["status"] == "PASS"
           and blocked_chain["capability_contract"]["status"] == "PASS"
           and blocked_chain["artifact_evidence"]["status"] == "BLOCKED",
           str((blocked_chain["compatibility"]["status"],
                blocked_chain["capability_contract"]["status"],
                blocked_chain["artifact_evidence"]["status"])))
        ok("extra: structural validation passed too (the mismatch is the only failure)",
           blocked_chain["failures"] == [
               "Artifact Evidence: Artifact evidence mismatch: CollisionShape2D missing"])
        blocked_path = blocked_chain["scene_path"]
        ok("extra: the generation path is kept for diagnosis",
           bool(blocked_path) and os.path.isfile(blocked_path), str(blocked_path))
        ok("extra: the artifact is preserved, not deleted or repaired",
           os.path.isfile(blocked_path)
           and open(blocked_path, encoding="utf-8").read().startswith("[gd_scene ")
           and "instance=ExtResource" in open(blocked_path, encoding="utf-8").read(),
           open(blocked_path, encoding="utf-8").read()[:80] if os.path.isfile(blocked_path)
           else "<missing>")
        blocked_text = open(blocked_path, encoding="utf-8").read()
        ok("extra: the declared component is a PackedScene instance in the artifact, so its "
           "subtree lives inside the entry scene (out of artifact scope)",
           'path="res://Features/contact_damage/ContactDamage.tscn"' in blocked_text
           and 'type="Area2D"' not in blocked_text, blocked_text[:200])

        matching_bp = copy.deepcopy(declared_bp)
        matching_bp["components"][1]["instance"] = {"node_type": "CollisionShape2D"}
        matching_bp["nodes"] = [{"type": "CollisionShape2D", "name": "ContactShape"}]
        matching_out = os.path.join(tmp, "extra_matching_out")
        matching_chain = scene_composer.compose(copy.deepcopy(matching_bp), out_dir=matching_out)
        ok("extra: a declaration the artifact can confirm -> PASS",
           matching_chain["ok"] is True
           and matching_chain["artifact_evidence"] == {
               "status": "PASS", "errors": [], "checked_instances": ["contact_damage"],
               "checked_external_artifacts": [
                   "res://Features/health/Health.tscn",
                   "res://Features/contact_damage/ContactDamage.tscn"],
               "checked_ownership": [{
                   "component": "contact_damage",
                   "artifact_path": "res://Features/contact_damage/ContactDamage.tscn",
                   "node_path": "ArtifactBlock/ContactDamage", "confidence": "resolved"}]},
           str((matching_chain.get("failures"), matching_chain.get("artifact_evidence"))))
        plain_bp = copy.deepcopy(matching_bp)
        plain_bp["components"][1].pop("instance")
        plain_chain = scene_composer.compose(plain_bp, out_dir=os.path.join(tmp, "extra_plain_out"))
        ok("extra: the declaration changes neither the .tscn nor the .gd",
           plain_chain["ok"] is True
           and open(plain_chain["scene_path"], "rb").read()
           == open(matching_chain["scene_path"], "rb").read(),
           str((plain_chain.get("failures"), matching_chain.get("failures"))))

        # ---------------- 附件：挂载关系 / 可读性 / 幂等 ----------------
        print("=== Extra: mount relations, readability, idempotency ===")
        wrong_parent = write_artifact(
            tmp, "extra_parent.tscn",
            "[gd_scene load_steps=1 format=3]\n\n"
            "[node name=\"InstProbe\" type=\"Node2D\"]\n\n"
            "[node name=\"ContactDamage\" type=\"Area2D\" parent=\".\"]\n\n"
            "[node name=\"Other\" type=\"Node2D\" parent=\".\"]\n\n"
            "[node name=\"StrayShape\" type=\"CollisionShape2D\" parent=\"Other\"]\n")
        wrong_parent_report = verify(collision_intent, wrong_parent)
        ok("extra: a child under the wrong parent is not accepted",
           wrong_parent_report.status == "BLOCKED"
           and wrong_parent_report.errors == [
               "Artifact evidence mismatch: CollisionShape2D missing"],
           str(wrong_parent_report.to_dict()))
        deeper = write_artifact(
            tmp, "extra_deeper.tscn",
            "[gd_scene load_steps=1 format=3]\n\n"
            "[node name=\"InstProbe\" type=\"Node2D\"]\n\n"
            "[node name=\"ContactDamage\" type=\"Area2D\" parent=\".\"]\n\n"
            "[node name=\"Inner\" type=\"Node2D\" parent=\"ContactDamage\"]\n\n"
            "[node name=\"DeepShape\" type=\"CollisionShape2D\" parent=\"ContactDamage/Inner\"]\n")
        ok("extra: a descendant of the declared node counts as its child",
           verify(collision_intent, deeper).ok, str(verify(collision_intent, deeper).to_dict()))
        parented = intent_doc([instance_entry("contact_damage", "Area2D",
                                              ["CollisionShape2D"], parent="InstProbe")],
                              ["Collision"])
        ok("extra: a declared parent must match the artifact mount point",
           verify(parented, full_artifact).ok
           and verify(intent_doc([instance_entry("contact_damage", "Area2D", None,
                                                parent="Other")], ["Collision"]),
                      full_artifact).errors == ["Artifact evidence mismatch: Area2D missing"],
           str(verify(parented, full_artifact).to_dict()))
        unavailable = verify(collision_intent, os.path.join(tmp, "no_such_scene.tscn"))
        ok("extra: an unreadable artifact is reported, not guessed",
           unavailable.status == "BLOCKED"
           and unavailable.errors[0].startswith("Artifact evidence unavailable: "),
           str(unavailable.to_dict()))
        ok("extra: verification is idempotent",
           verify(collision_intent, full_artifact).to_dict()
           == verify(collision_intent, full_artifact).to_dict())
        rejected_ok, message = rejected(
            lambda: verify(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME), full_artifact))
        ok("extra: raw Blueprint input is rejected (single Intent boundary)",
           rejected_ok, message)

        # ---------------- 附件：真实生成物解析 / 职责隔离 ----------------
        print("=== Extra: real artifact parsing + isolation ===")
        parsed = artifact_evidence_validator.parse_artifact(slime["scene_path"])
        ok("extra: the parser reads names / types / parents from a real artifact",
           parsed["root_name"] == "SlimeEnemy"
           and [(node["name"], node["type"]) for node in parsed["nodes"]] == [
               ("SlimeEnemy", "CharacterBody2D"), ("Health", ""), ("ContactDamage", ""),
               ("ChaseMovement", ""), ("SlimeShape", "CollisionShape2D"),
               ("SlimeAnim", "AnimatedSprite2D"), ("SlimeHurtSfx", "AudioStreamPlayer")],
           str(parsed))
        # 1.8.16 起 path 是含场景根名的全路径（多级后代判定需要），parent 仍是原始属性值
        ok("extra: PackedScene instances are recognised as opaque (no type in the text)",
           [node["instance"] for node in parsed["nodes"]]
           == [False, True, True, True, False, False, False]
           and [node["path"] for node in parsed["nodes"]][:5]
           == ["SlimeEnemy", "SlimeEnemy/Health", "SlimeEnemy/ContactDamage",
               "SlimeEnemy/ChaseMovement", "SlimeEnemy/SlimeShape"],
           str([(node["name"], node["path"], node["instance"]) for node in parsed["nodes"]]))

        validator_source = open(os.path.join(TOOL_DIR, "artifact_evidence_validator.py"),
                                encoding="utf-8").read()
        identifiers, strings = code_tokens(validator_source)
        forbidden = {"blueprint", "feature_index", "feature_registry", "capability_registry",
                     "PackedScene", "godot", "Godot", "write", "remove", "unlink", "rmtree"}
        ok("extra: the validator never touches Blueprint / Registry / Godot / file writes",
           not (identifiers & forbidden), str(sorted(identifiers & forbidden)))
        ok("extra: no artifact scene path is fabricated (paths come from the artifact)",
           not [text for text in strings
                if text.startswith("res://") and text.endswith(".tscn")], str(sorted(strings)))
        tree = ast.parse(validator_source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        # Phase 1.8.16 / 1.8.17：静态解析与归属解析各自集中在单一模块，
        # 本模块允许集合随之扩入它们（仍是封闭的 artifact 层集合）。
        ok("extra: imports stay inside the static artifact layer",
           imported <= {"os", "component_instance_ownership", "external_artifact_resolver",
                        "scene_intent", "sys"},
           str(sorted(imported)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all artifact evidence checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
