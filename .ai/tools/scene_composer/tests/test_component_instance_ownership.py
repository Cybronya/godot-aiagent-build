#!/usr/bin/env python3
"""Component Instance Ownership 测试（Phase 1.8.17）

链路（四层职责）：

    Capability（需要什么）→ Instance（声明什么）→ Ownership（哪个实例）→ Artifact Evidence（是否兑现）

    Case 1  单 component（无 id，唯一 ext_resource 候选）→ PASS（confidence resolved）
    Case 2  同一组件场景两个实例（不同 id）→ PASS，owner 各自指向自己的实例节点
    Case 3  两个**同名**实例节点（不同 parent）→ 全路径 id 可判定；裸名 id 二义 → BLOCKED
    Case 4  缺少 id + 只有一个候选 → PASS（fallback、不猜测）
    Case 5  缺少 id + 多个候选 → BLOCKED（逐字 "Component ownership unresolved: <component>"）
    Case 6  恶意名字：component enemy_damage / 节点 DamageNode → 不得靠名字或无关产物匹配
    Case 7  嵌套 External Artifact A → B → C：ownership 与证据闭包仍正确

附件：报告键（旧三键 + checked_external_artifacts 不变，新增 checked_ownership）、
归属限定证据池（不得借用其它组件的产物）、声明顺序 / 一条声明一个 owner、只读幂等、
输入边界（拒绝原始 Blueprint）、职责隔离（不读 Blueprint / Registry、不启动 Godot、不写文件）、
产物保护（SlimeEnemy.tscn / test_slime_enemy.gd 逐字节不变）。

范围说明：Blueprint.components[] 以 feature 为键，当前生成链一次只声明一个实例，
因此「同 Feature 多实例」在 Scene Intent 层（本测试 Case 2/3）验证；运行时节点身份仍是
static 解析（见 known_gaps.component_instance_runtime_identity_missing）。

只读项目文件、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_component_instance_ownership.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import ast
import copy
import hashlib
import os
import shutil
import sys
import tempfile

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
import component_instance_ownership                             # noqa: E402
import external_artifact_resolver                               # noqa: E402
import generate_scene_test                                      # noqa: E402
import scene_composer                                           # noqa: E402
import scene_intent                                             # noqa: E402
import template_loader                                          # noqa: E402
import test_scene_builder_intent_input as goldens               # noqa: E402

CONTACT_SCENE = "res://Features/contact_damage/ContactDamage.tscn"

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
    """源码 -> (标识符集合, 字符串常量集合)；docstring 被排除（避免散文误报）。"""
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


def intent_doc(components, root_name: str = "OwnershipHost") -> dict:
    """构造最小 Scene Intent 文档（显式 components[]，实例声明原样携带）。"""
    return {
        "document": "scene_intent",
        "schema_version": 1,
        "scene": {"id": "ownership_probe"},
        "root": {"name": root_name, "type": "Node2D"},
        "components": copy.deepcopy(list(components)),
        "nodes": [],
        "resources": [],
        "capabilities": {"required": []},
        "validation": {"required_tests": []},
    }


def instance_entry(component: str, node_type: str, instance_id=None, children=None,
                   parent=None) -> dict:
    instance = {"node_type": node_type}
    if instance_id is not None:
        instance["id"] = instance_id
    if children is not None:
        instance["children"] = list(children)
    if parent is not None:
        instance["parent"] = parent
    return {"component": component, "instance": instance}


def write_text(path: str, text: str) -> str:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def host_scene(tmp: str, name: str, body: str, extra_resources=()) -> str:
    """宿主 .tscn：ext_resource 声明 + 节点体。"""
    resources = list(extra_resources)
    text = ["[gd_scene load_steps=%d format=3]" % (len(resources) + 1), ""]
    for entry in resources:
        text.append('[ext_resource type="%s" path="%s" id="%s"]'
                    % (entry.get("type", "PackedScene"), entry["path"], entry["id"]))
        text.append("")
    text.append(body)
    return write_text(os.path.join(tmp, name), "\n".join(text))


CD_RESOURCE = ({"type": "PackedScene", "path": CONTACT_SCENE, "id": "1_cd"},)


def resolve(intent, artifact_path):
    """ownership 单元入口（传入真实解析结果，含 scene_path）。"""
    return component_instance_ownership.resolve_component_ownership(
        intent, artifact_evidence_validator.parse_artifact(artifact_path))


def verify(intent, artifact_path):
    return artifact_evidence_validator.verify_artifact_evidence(intent, artifact_path)


def owner_of(ownership_result, component):
    for owner in ownership_result["owners"]:
        if owner["component"] == component:
            return owner
    return None


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="component_ownership_")
    try:
        # ---------------- Case 1: 单 component（无 id，唯一候选） ----------------
        print("=== Case 1: a single component resolves through its one ext_resource ===")
        case1_host = host_scene(
            tmp, "case1.tscn",
            "[node name=\"OwnershipHost\" type=\"Node2D\"]\n\n"
            "[node name=\"ContactDamage\" parent=\".\" instance=ExtResource(\"1_cd\")]\n",
            CD_RESOURCE)
        case1_intent = intent_doc([instance_entry("contact_damage", "Area2D")])
        case1 = resolve(case1_intent, case1_host)
        ok("case1: ownership PASS with exactly one owner",
           case1["status"] == "PASS" and case1["errors"] == []
           and len(case1["owners"]) == 1, str(case1))
        ok("case1: the owner points at the external component scene and its instance node",
           owner_of(case1, "contact_damage") == {
               "component": "contact_damage", "artifact_path": CONTACT_SCENE,
               "node_path": "OwnershipHost/ContactDamage", "confidence": "resolved"},
           str(case1["owners"]))
        case1_report = verify(case1_intent, case1_host)
        ok("case1: artifact evidence PASS and the ownership is reported",
           case1_report.ok and case1_report.checked_instances == ["contact_damage"]
           and case1_report.checked_ownership == case1["owners"],
           str(case1_report.to_dict()))

        # ---------------- Case 2: 同一组件场景两个实例（不同 id） ----------------
        print("=== Case 2: two instances of the same component scene, distinct ids ===")
        case2_host = host_scene(
            tmp, "case2.tscn",
            "[node name=\"OwnershipHost\" type=\"Node2D\"]\n\n"
            "[node name=\"ContactDamageA\" parent=\".\" instance=ExtResource(\"1_cd\")]\n\n"
            "[node name=\"ContactDamageB\" parent=\".\" instance=ExtResource(\"1_cd\")]\n",
            CD_RESOURCE)
        case2_intent = intent_doc([
            instance_entry("contact_damage_a", "Area2D", "OwnershipHost/ContactDamageA"),
            instance_entry("contact_damage_b", "Area2D", "OwnershipHost/ContactDamageB")])
        case2 = resolve(case2_intent, case2_host)
        ok("case2: both declarations resolve (no ambiguity) -> PASS",
           case2["status"] == "PASS" and len(case2["owners"]) == 2, str(case2))
        ok("case2: each owner maps to its own instance node",
           [owner_of(case2, "contact_damage_a")["node_path"],
            owner_of(case2, "contact_damage_b")["node_path"]]
           == ["OwnershipHost/ContactDamageA", "OwnershipHost/ContactDamageB"],
           str(case2["owners"]))
        ok("case2: declared ids are reported as declared (not guessed)",
           {owner["confidence"] for owner in case2["owners"]} == {"declared"},
           str(case2["owners"]))
        case2_report = verify(case2_intent, case2_host)
        ok("case2: artifact evidence keeps declaration order",
           case2_report.ok
           and case2_report.checked_instances == ["contact_damage_a", "contact_damage_b"]
           and case2_report.checked_ownership == case2["owners"],
           str(case2_report.to_dict()))

        # ---------------- Case 3: 两个同名实例节点（不同 parent） ----------------
        print("=== Case 3: two identically named instance nodes ===")
        case3_host = host_scene(
            tmp, "case3.tscn",
            "[node name=\"OwnershipHost\" type=\"Node2D\"]\n\n"
            "[node name=\"GroupA\" type=\"Node2D\" parent=\".\"]\n\n"
            "[node name=\"ContactDamage\" parent=\"GroupA\" instance=ExtResource(\"1_cd\")]\n\n"
            "[node name=\"GroupB\" type=\"Node2D\" parent=\".\"]\n\n"
            "[node name=\"ContactDamage\" parent=\"GroupB\" instance=ExtResource(\"1_cd\")]\n",
            CD_RESOURCE)
        case3_intent = intent_doc([
            instance_entry("contact_damage_a", "Area2D", "OwnershipHost/GroupA/ContactDamage"),
            instance_entry("contact_damage_b", "Area2D", "OwnershipHost/GroupB/ContactDamage")])
        case3 = resolve(case3_intent, case3_host)
        ok("case3: full node paths disambiguate same-named instances -> PASS",
           case3["status"] == "PASS"
           and [owner_of(case3, "contact_damage_a")["node_path"],
                owner_of(case3, "contact_damage_b")["node_path"]]
           == ["OwnershipHost/GroupA/ContactDamage", "OwnershipHost/GroupB/ContactDamage"],
           str(case3))
        bare_name = intent_doc([instance_entry("contact_damage_a", "Area2D", "ContactDamage")])
        bare_report = resolve(bare_name, case3_host)
        ok("case3: a bare name matching two nodes is ambiguous -> BLOCKED",
           bare_report["status"] == "BLOCKED"
           and bare_report["errors"] == ["Component ownership unresolved: contact_damage_a"],
           str(bare_report))

        # ---------------- Case 4: 缺少 id + 唯一候选（fallback） ----------------
        print("=== Case 4: no declared id with exactly one candidate ===")
        case4 = resolve(case1_intent, case1_host)
        ok("case4: fallback to the only ext_resource candidate",
           case4["status"] == "PASS"
           and owner_of(case4, "contact_damage")["confidence"] == "resolved"
           and owner_of(case4, "contact_damage")["artifact_path"] == CONTACT_SCENE,
           str(case4))

        # ---------------- Case 5: 缺少 id + 多个候选 ----------------
        print("=== Case 5: no declared id with several candidates ===")
        case5_intent = intent_doc([instance_entry("contact_damage", "Area2D")])
        case5 = resolve(case5_intent, case2_host)
        ok("case5: BLOCKED with the exact message",
           case5["status"] == "BLOCKED"
           and case5["errors"] == ["Component ownership unresolved: contact_damage"],
           str(case5))
        ok("case5: no owner is invented for the ambiguous component",
           case5["owners"] == [], str(case5["owners"]))
        case5_report = verify(case5_intent, case2_host)
        ok("case5: the artifact layer blocks too (ownership comes first)",
           case5_report.status == "BLOCKED"
           and case5_report.errors == ["Component ownership unresolved: contact_damage"]
           and case5_report.checked_instances == []
           and case5_report.checked_external_artifacts == [CONTACT_SCENE],
           str(case5_report.to_dict()))

        # ---------------- Case 6: 恶意名字 / 无关产物不得匹配 ----------------
        print("=== Case 6: malicious names must not be matched ===")
        case6_host = host_scene(
            tmp, "case6.tscn",
            "[node name=\"OwnershipHost\" type=\"Node2D\"]\n\n"
            "[node name=\"DamageNode\" type=\"Node2D\" parent=\".\"]\n\n"
            "[node name=\"ContactDamage\" parent=\".\" instance=ExtResource(\"1_cd\")]\n",
            CD_RESOURCE)
        keyword_intent = intent_doc([instance_entry("enemy_damage", "Area2D")])
        keyword = resolve(keyword_intent, case6_host)
        ok("case6: an unrelated instance node is not stolen by another component",
           keyword["status"] == "PASS"
           and owner_of(keyword, "enemy_damage")["artifact_path"]
           != CONTACT_SCENE
           and owner_of(keyword, "enemy_damage")["confidence"] == "resolved",
           str(keyword))
        named = intent_doc([instance_entry("enemy_damage", "Node2D")])
        ok("case6: a node named 'DamageNode' is never mapped by name",
           resolve(named, case6_host)["owners"][0]["node_path"] == "",
           str(resolve(named, case6_host)["owners"]))
        keyword_report = verify(keyword_intent, case6_host)
        ok("case6: the Area2D inside an unrelated component scene cannot satisfy it",
           keyword_report.status == "BLOCKED"
           and keyword_report.errors == ["Artifact evidence mismatch: Area2D missing"],
           str(keyword_report.to_dict()))
        ghost_id = intent_doc([
            instance_entry("enemy_damage", "Node2D", "enemy_damage_instance")])
        ghost = resolve(ghost_id, case6_host)
        ok("case6: a declared id absent from the artifact is unresolved, never guessed",
           ghost["status"] == "BLOCKED"
           and ghost["errors"] == ["Component ownership unresolved: enemy_damage"],
           str(ghost))

        # ---------------- Case 7: 嵌套 External Artifact A → B → C ----------------
        print("=== Case 7: nested external artifacts (A -> B -> C) ===")
        nested = os.path.join(tmp, "nested_project")
        write_text(os.path.join(nested, "project.godot"), "; probe project\n")
        write_text(os.path.join(nested, "Features", "comp_c", "C.tscn"),
                   "[gd_scene load_steps=1 format=3]\n\n"
                   "[node name=\"C\" type=\"Node2D\"]\n\n"
                   "[node name=\"DeepShape\" type=\"CollisionShape2D\" parent=\".\"]\n")
        write_text(os.path.join(nested, "Features", "comp_b", "B.tscn"),
                   "[gd_scene load_steps=2 format=3]\n\n"
                   "[ext_resource type=\"PackedScene\" path=\"res://Features/comp_c/C.tscn\" "
                   "id=\"1_c\"]\n\n"
                   "[node name=\"B\" type=\"Node2D\"]\n\n"
                   "[node name=\"CInstance\" parent=\".\" instance=ExtResource(\"1_c\")]\n")
        write_text(os.path.join(nested, "Features", "comp_a", "A.tscn"),
                   "[gd_scene load_steps=2 format=3]\n\n"
                   "[ext_resource type=\"PackedScene\" path=\"res://Features/comp_b/B.tscn\" "
                   "id=\"1_b\"]\n\n"
                   "[node name=\"A\" type=\"Node2D\"]\n\n"
                   "[node name=\"BInstance\" parent=\".\" instance=ExtResource(\"1_b\")]\n")
        nested_host = host_scene(
            nested, "Host.tscn",
            "[node name=\"NestedHost\" type=\"Node2D\"]\n\n"
            "[node name=\"AInstance\" parent=\".\" instance=ExtResource(\"1_a\")]\n",
            ({"type": "PackedScene", "path": "res://Features/comp_a/A.tscn", "id": "1_a"},))
        nested_intent = intent_doc([
            instance_entry("comp_a", "Node2D", "NestedHost/AInstance",
                           children=["CollisionShape2D"]),
            instance_entry("comp_x", "Node2D", children=["CollisionShape2D"])])
        nested_result = resolve(nested_intent, nested_host)
        ok("case7: ownership resolves the outermost component scene",
           nested_result["status"] == "PASS"
           and owner_of(nested_result, "comp_a")["artifact_path"]
           == "res://Features/comp_a/A.tscn",
           str(nested_result))
        nested_report = verify(nested_intent, nested_host)
        ok("case7: evidence declared in C is reachable through A -> B -> C",
           owner_of(nested_result, "comp_x")["node_path"] == ""
           and nested_report.status == "BLOCKED"
           and nested_report.errors == ["Artifact evidence mismatch: CollisionShape2D missing"],
           str(nested_report.to_dict()))
        only_a = intent_doc([instance_entry("comp_a", "Node2D", "NestedHost/AInstance",
                                            children=["CollisionShape2D"])])
        ok("case7: the same declaration passes when only the reachable component is declared",
           verify(only_a, nested_host).ok,
           str(verify(only_a, nested_host).to_dict()))
        ok("case7: the reachable closure is recorded as external artifacts",
           verify(only_a, nested_host).checked_external_artifacts == [
               "res://Features/comp_a/A.tscn", "res://Features/comp_b/B.tscn",
               "res://Features/comp_c/C.tscn"],
           str(verify(only_a, nested_host).checked_external_artifacts))

        # ---------------- 附件：报告键 / 旧行为 / 单位映射 ----------------
        print("=== Extra: report keys, legacy intent, one owner per declaration ===")
        report_keys = sorted(case1_report.to_dict())
        ok("extra: the report exposes exactly the five documented keys",
           report_keys == ["checked_external_artifacts", "checked_instances",
                           "checked_ownership", "errors", "status"],
           str(report_keys))
        ok("extra: the pre-1.8.17 keys keep their shape",
           set(case1_report.to_dict()) >= {"status", "errors", "checked_instances",
                                           "checked_external_artifacts"}
           and isinstance(case1_report.to_dict()["checked_external_artifacts"], list)
           and isinstance(case1_report.to_dict()["checked_ownership"], list),
           str(case1_report.to_dict()))
        legacy = intent_doc([{"component": "health"}])
        legacy_ownership = resolve(legacy, case1_host)
        ok("extra: an old Intent without instances yields no owners",
           legacy_ownership == {"status": "PASS", "owners": [], "errors": []},
           str(legacy_ownership))
        ok("extra: an old Intent keeps the artifact layer untouched",
           verify(legacy, os.path.join(tmp, "no_such_scene.tscn")).to_dict() == {
               "status": "PASS", "errors": [], "checked_instances": [],
               "checked_external_artifacts": [], "checked_ownership": []},
           str(verify(legacy, os.path.join(tmp, "no_such_scene.tscn")).to_dict()))
        ok("extra: exactly one owner per declared instance (declaration order)",
           [owner["component"] for owner in case2["owners"]]
           == ["contact_damage_a", "contact_damage_b"]
           and len({owner["component"] for owner in case2["owners"]}) == 2,
           str(case2["owners"]))
        ok("extra: ownership is idempotent and read-only",
           resolve(case2_intent, case2_host) == resolve(case2_intent, case2_host)
           and resolve(case2_intent, case2_host) == case2,
           str(resolve(case2_intent, case2_host)))
        ok("extra: a raw Blueprint is rejected (single Intent boundary)",
           rejected(lambda: component_instance_ownership.resolve_component_ownership(
               copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
               artifact_evidence_validator.parse_artifact(case1_host)))[0])
        ok("extra: a non-mapping artifact evidence is rejected",
           rejected(lambda: component_instance_ownership.resolve_component_ownership(
               case1_intent, "not-a-mapping"))[0])
        skipped = intent_doc([{"component": "health", "instance": {"id": "nothing"}}])
        ok("extra: instances without node_type stay with the capability layer",
           resolve(skipped, case1_host) == {"status": "PASS", "owners": [], "errors": []},
           str(resolve(skipped, case1_host)))

        # ---------------- 附件：职责隔离 ----------------
        print("=== Extra: isolation of the ownership layer ===")
        source_path = os.path.join(TOOL_DIR, "component_instance_ownership.py")
        ownership_source = open(source_path, encoding="utf-8").read()
        identifiers, strings = code_tokens(ownership_source)
        forbidden = {"blueprint", "feature_index", "feature_registry", "capability_registry",
                     "PackedScene", "godot", "Godot", "write", "remove", "unlink", "rmtree",
                     "open", "os", "path", "subprocess"}
        ok("extra: the ownership layer never touches Blueprint / Registry / Godot / files",
           not (identifiers & forbidden), str(sorted(identifiers & forbidden)))
        ok("extra: no artifact path is fabricated as a literal",
           not [text for text in strings
                if text.startswith("res://") and text.endswith(".tscn")],
           str(sorted(strings)))
        tree = ast.parse(ownership_source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        ok("extra: imports stay inside the Intent + artifact layer",
           imported <= {"external_artifact_resolver", "scene_intent", "sys"},
           str(sorted(imported)))
        validator_source = open(os.path.join(TOOL_DIR, "artifact_evidence_validator.py"),
                               encoding="utf-8").read()
        ok("extra: the artifact validator wires the ownership layer in explicitly",
           "component_instance_ownership" in validator_source)

        # ---------------- 附件：产物保护 ----------------
        print("=== Extra: existing artifacts stay byte-identical ===")
        binding_path = goldens.write_binding(tmp, goldens.BINDING_SLIME)
        slime = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                       out_dir=os.path.join(tmp, "slime_out"),
                                       bindings_path=binding_path)
        ok("extra: the slime chain still succeeds",
           slime["ok"] is True and slime["artifact_evidence"]["status"] == "PASS",
           str((slime.get("failures"), slime.get("artifact_evidence"))))
        ok("extra: the generated .tscn is byte-identical to the pre-phase golden",
           open(slime["scene_path"], "rb").read() == goldens.GOLDEN_F3.encode("utf-8"))
        generated_gd = generate_scene_test.build_test_source(
            scene_intent.intent_document(slime["scene_intent"]),
            template_loader.load_templates(goldens.FEATURES), "Scenes/SlimeEnemy.tscn")
        committed_gd = open(os.path.join(PROJECT_ROOT, "Tests", "test_slime_enemy.gd"),
                            encoding="utf-8", newline="").read()
        ok("extra: the generated .gd is byte-identical to the committed test",
           generated_gd == committed_gd)
        committed_scene = open(os.path.join(PROJECT_ROOT, "Scenes", "SlimeEnemy.tscn"),
                               "rb").read()
        ok("extra: the committed scene sha256 is unchanged",
           hashlib.sha256(committed_scene).hexdigest().startswith("f87bc2b0c9613ac5"),
           hashlib.sha256(committed_scene).hexdigest())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all component instance ownership checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
