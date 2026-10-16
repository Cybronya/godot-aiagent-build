#!/usr/bin/env python3
"""External Artifact Evidence 测试（Phase 1.8.16）

链路：Scene Intent（components[].instance）→ Capability Contract → Scene Builder
      → Host .tscn → ExtResource → Feature Component .tscn → Complete Artifact Evidence

    Case 1  Host 引用组件场景；组件场景 = Area2D + CollisionShape2D → PASS
    Case 2  组件场景缺 CollisionShape2D → BLOCKED（逐字文案）
    Case 3  外部场景不存在 → BLOCKED \"External artifact unavailable\"
    Case 4  多级 child（Area2D → Node2D → CollisionShape2D）→ PASS
    Case 5  循环引用（A ⇄ B）→ BLOCKED \"External artifact recursion detected\"
    Case 6  既有 slime_enemy：.tscn / .gd 逐字节不变

附件：真实 feature 链（contact_damage 的 Area2D 由外部场景确认、CollisionShape2D 由宿主提供）、
跨产物 vs 同产物挂载关系、缺失外部产物即阻断、报告向后兼容、解析范围（只认
res://Features/**/*.tscn / PackedScene）、确定性、职责隔离（不读 Blueprint / Registry / Godot）。

只读项目文件、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_external_artifact_evidence.py
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
import external_artifact_resolver                               # noqa: E402
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


def imported_modules(source: str) -> set:
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    return imported


def intent_doc(components, required=None, root_type: str = "Node2D",
               root_name: str = "ExternalProbe", nodes=None) -> dict:
    """构造一个最小 Scene Intent 文档（显式 components[] / capabilities.required）。"""
    return {
        "document": "scene_intent",
        "schema_version": 1,
        "scene": {"id": "external_probe"},
        "root": {"name": root_name, "type": root_type},
        "components": copy.deepcopy(list(components)),
        "nodes": copy.deepcopy(list(nodes or [])),
        "resources": [],
        "capabilities": {"required": list(required or [])},
        "validation": {"required_tests": []},
    }


def instance_entry(component: str, node_type: str, children=None) -> dict:
    instance = {"node_type": node_type}
    if children is not None:
        instance["children"] = list(children)
    return {"component": component, "instance": instance}


def write_text(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def host_scene(component: str, scene: str, node_name: str = "Probe",
               extra_nodes: str = "") -> str:
    """宿主 .tscn 文本：引用一个 Feature 组件场景。"""
    return ("[gd_scene load_steps=2 format=3]\n\n"
            "[ext_resource type=\"PackedScene\" path=\"res://Features/%s/%s\" id=\"1_%s\"]\n\n"
            "[node name=\"ExternalProbe\" type=\"Node2D\"]\n\n"
            "[node name=\"%s\" parent=\".\" instance=ExtResource(\"1_%s\")]\n%s"
            % (component, scene, component, node_name, component, extra_nodes))


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="external_artifact_")
    try:
        # 临时项目：proj/ 含 project.godot（供 res:// → 文件系统解析），Scene / Feature 场景齐全；
        # 生成物的输出目录放在 proj/ 之外，使真实 feature 链回退到仓库项目根。
        proj = os.path.join(tmp, "proj")
        write_text(os.path.join(proj, "project.godot"), "; test project\n")
        out_root = os.path.join(tmp, "out")
        features_dir = os.path.join(proj, "Features")
        probe_dir = os.path.join(features_dir, "probe_component")
        scenes_dir = os.path.join(proj, "Scenes")
        probe_res = "res://Features/probe_component/Probe.tscn"
        host_path = write_text(os.path.join(scenes_dir, "host.tscn"),
                               host_scene("probe_component", "Probe.tscn"))
        ok("setup: the host artifact resolves its project root via project.godot",
           external_artifact_resolver.project_root_for(host_path) == proj,
           external_artifact_resolver.project_root_for(host_path))
        ok("setup: a generated scene outside the project falls back to the tool's project",
           external_artifact_resolver.project_root_for(
               os.path.join(out_root, "x", "y.tscn")) == PROJECT_ROOT,
           external_artifact_resolver.project_root_for(os.path.join(out_root, "x", "y.tscn")))

        # ---------------- Case 1: 组件场景提供完整结构 ----------------
        print("=== Case 1: the external component scene provides the declared structure ===")
        write_text(os.path.join(probe_dir, "Probe.tscn"),
                   "[gd_scene load_steps=1 format=3]\n\n"
                   "[node name=\"Probe\" type=\"Area2D\"]\n\n"
                   "[node name=\"ProbeShape\" type=\"CollisionShape2D\" parent=\".\"]\n")
        collision_intent = intent_doc([instance_entry("probe_component", "Area2D",
                                                     ["CollisionShape2D"])],
                                      ["Node", "Collision"])
        single = external_artifact_resolver.resolve_external_artifact(host_path, probe_res)
        ok("case1: resolve_external_artifact returns nodes for the referenced scene",
           single["status"] == "PASS"
           and [(node["name"], node["type"]) for node in single["nodes"]]
           == [("Probe", "Area2D"), ("ProbeShape", "CollisionShape2D")],
           str(single))
        case1 = artifact_evidence_validator.verify_artifact_evidence(collision_intent, host_path)
        ok("case1: declaration confirmed by the external component scene -> PASS",
           case1.ok and case1.checked_instances == ["probe_component"],
           str(case1.to_dict()))
        ok("case1: the resolved external artifact is recorded",
           case1.checked_external_artifacts == [probe_res], str(case1.to_dict()))
        ok("case1: the plan layer agrees",
           capability_contract_validator.validate_capability_contract(collision_intent).ok)
        explicit_root = artifact_evidence_validator.verify_artifact_evidence(
            collision_intent, host_path, project_root=proj)
        ok("case1: an explicit project_root is honoured",
           explicit_root.to_dict() == case1.to_dict(), str(explicit_root.to_dict()))

        # ---------------- Case 2: 组件场景缺 CollisionShape2D ----------------
        print("=== Case 2: the external component scene lacks CollisionShape2D ===")
        write_text(os.path.join(probe_dir, "Probe.tscn"),
                   "[gd_scene load_steps=1 format=3]\n\n"
                   "[node name=\"Probe\" type=\"Area2D\"]\n\n"
                   "[node name=\"Body\" type=\"Node2D\" parent=\".\"]\n")
        case2 = artifact_evidence_validator.verify_artifact_evidence(collision_intent, host_path)
        ok("case2: BLOCKED with the exact message",
           case2.status == "BLOCKED"
           and case2.errors == ["Artifact evidence mismatch: CollisionShape2D missing"],
           str(case2.to_dict()))
        ok("case2: nothing is recorded as checked",
           case2.checked_instances == [] and case2.checked_external_artifacts == [probe_res],
           str(case2.to_dict()))

        # ---------------- Case 3: 外部场景不存在 ----------------
        print("=== Case 3: the referenced component scene does not exist ===")
        gone_res = "res://Features/probe_component/Gone.tscn"
        gone_host = write_text(os.path.join(scenes_dir, "gone.tscn"),
                               host_scene("probe_component", "Gone.tscn"))
        single_gone = external_artifact_resolver.resolve_external_artifact(gone_host, gone_res)
        ok("case3: the resolver reports the missing scene",
           single_gone["status"] == "BLOCKED"
           and single_gone["errors"] == ["External artifact unavailable: %s" % gone_res],
           str(single_gone))
        case3 = artifact_evidence_validator.verify_artifact_evidence(collision_intent, gone_host)
        ok("case3: the chain BLOCKS with the unavailable error",
           case3.status == "BLOCKED"
           and case3.errors == ["External artifact unavailable: %s" % gone_res],
           str(case3.to_dict()))
        out_of_scope = external_artifact_resolver.resolve_external_artifact(
            gone_host, "res://Scenes/Something.tscn")
        ok("case3: a non-Features path is out of scope, never guessed",
           out_of_scope["status"] == "BLOCKED"
           and out_of_scope["errors"] == [
               "External artifact unavailable: res://Scenes/Something.tscn"],
           str(out_of_scope))

        # ---------------- Case 4: 多级 child ----------------
        print("=== Case 4: multi-level children inside the external scene ===")
        write_text(os.path.join(probe_dir, "Probe.tscn"),
                   "[gd_scene load_steps=1 format=3]\n\n"
                   "[node name=\"Probe\" type=\"Area2D\"]\n\n"
                   "[node name=\"Inner\" type=\"Node2D\" parent=\".\"]\n\n"
                   "[node name=\"DeepShape\" type=\"CollisionShape2D\" parent=\"Inner\"]\n")
        case4 = artifact_evidence_validator.verify_artifact_evidence(collision_intent, host_path)
        ok("case4: a descendant of the declared node counts -> PASS",
           case4.ok and case4.checked_instances == ["probe_component"],
           str(case4.to_dict()))

        # ---------------- Case 5: 循环引用 ----------------
        print("=== Case 5: cyclic external references are detected ===")
        cyc_a_dir = os.path.join(features_dir, "cyc_a")
        cyc_b_dir = os.path.join(features_dir, "cyc_b")
        cyc_a_res = "res://Features/cyc_a/A.tscn"
        cyc_b_res = "res://Features/cyc_b/B.tscn"
        write_text(os.path.join(cyc_a_dir, "A.tscn"),
                   "[gd_scene load_steps=2 format=3]\n\n"
                   "[ext_resource type=\"PackedScene\" path=\"%s\" id=\"1_b\"]\n\n"
                   "[node name=\"A\" type=\"Area2D\"]\n\n"
                   "[node name=\"B\" parent=\".\" instance=ExtResource(\"1_b\")]\n" % cyc_b_res)
        write_text(os.path.join(cyc_b_dir, "B.tscn"),
                   "[gd_scene load_steps=2 format=3]\n\n"
                   "[ext_resource type=\"PackedScene\" path=\"%s\" id=\"1_a\"]\n\n"
                   "[node name=\"B\" type=\"Area2D\"]\n\n"
                   "[node name=\"A\" parent=\".\" instance=ExtResource(\"1_a\")]\n" % cyc_a_res)
        cyc_host = write_text(os.path.join(scenes_dir, "cycle.tscn"),
                              host_scene("cyc_a", "A.tscn"))
        cycle_intent = intent_doc([instance_entry("cyc_a", "Area2D")], ["Collision"])
        cycle_external = external_artifact_resolver.resolve_external_artifacts(cyc_host)
        ok("case5: the cycle is reported by the resolver",
           cycle_external["status"] == "BLOCKED"
           and cycle_external["errors"] == [
               "External artifact recursion detected: %s" % cyc_a_res],
           str(cycle_external))
        case5 = artifact_evidence_validator.verify_artifact_evidence(cycle_intent, cyc_host)
        ok("case5: the chain BLOCKS with the recursion error",
           case5.status == "BLOCKED"
           and case5.errors == ["External artifact recursion detected: %s" % cyc_a_res],
           str(case5.to_dict()))
        self_ref_dir = os.path.join(features_dir, "self_ref")
        self_res = "res://Features/self_ref/Self.tscn"
        write_text(os.path.join(self_ref_dir, "Self.tscn"),
                   "[gd_scene load_steps=2 format=3]\n\n"
                   "[ext_resource type=\"PackedScene\" path=\"%s\" id=\"1_self\"]\n\n"
                   "[node name=\"Self\" type=\"Area2D\"]\n\n"
                   "[node name=\"Inner\" parent=\".\" instance=ExtResource(\"1_self\")]\n"
                   % self_res)
        self_host = write_text(os.path.join(scenes_dir, "self.tscn"),
                               host_scene("self_ref", "Self.tscn"))
        case5b = artifact_evidence_validator.verify_artifact_evidence(
            intent_doc([instance_entry("self_ref", "Area2D")], ["Collision"]), self_host)
        ok("case5: a self-reference is also a recursion",
           case5b.status == "BLOCKED"
           and case5b.errors == ["External artifact recursion detected: %s" % self_res],
           str(case5b.to_dict()))

        # ---------------- Case 6: 既有 slime_enemy ----------------
        print("=== Case 6: the existing slime_enemy chain stays byte-identical ===")
        binding_path = goldens.write_binding(tmp, goldens.BINDING_SLIME)
        slime = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                       out_dir=os.path.join(out_root, "case6_out"),
                                       bindings_path=binding_path)
        ok("case6: chain still succeeds (no declaration -> no external resolution)",
           slime["ok"] is True
           and slime["artifact_evidence"] == {"status": "PASS", "errors": [],
                                              "checked_instances": [],
                                              "checked_external_artifacts": [],
                                              "checked_ownership": []},
           str((slime.get("failures"), slime.get("artifact_evidence"))))
        ok("case6: generated .tscn byte-identical to the pre-phase golden",
           open(slime["scene_path"], "rb").read() == goldens.GOLDEN_F3.encode("utf-8"))
        generated_gd = generate_scene_test.build_test_source(
            scene_intent.intent_document(slime["scene_intent"]),
            template_loader.load_templates(goldens.FEATURES), "Scenes/SlimeEnemy.tscn")
        repo_gd = open(os.path.join(PROJECT_ROOT, "Tests", "test_slime_enemy.gd"),
                       encoding="utf-8", newline="").read()
        ok("case6: generated .gd byte-identical to the committed test", generated_gd == repo_gd)
        repo_chain = scene_composer.compose(
            yaml.safe_load(open(os.path.join(PROJECT_ROOT, "slime_enemy.yaml"),
                                encoding="utf-8")),
            out_dir=os.path.join(out_root, "case6_repo_out"),
            bindings_path=os.path.join(DOTAI, "context", "asset_bindings", "slime_enemy.yaml"))
        repo_scene = open(os.path.join(PROJECT_ROOT, "Scenes", "SlimeEnemy.tscn"), "rb").read()
        ok("case6: regenerating the committed scene is byte-identical",
           repo_chain["ok"] is True
           and open(repo_chain["scene_path"], "rb").read() == repo_scene,
           str(repo_chain.get("failures")))
        ok("case6: committed scene sha256 unchanged",
           hashlib.sha256(repo_scene).hexdigest().startswith("ddd33c1db5359c3d"),
           hashlib.sha256(repo_scene).hexdigest())

        # ---------------- 附件：真实 feature 链的完整证据 ----------------
        print("=== Extra: the real contact_damage chain gets complete evidence ===")
        declared_slime = copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME)
        declared_slime["components"][1]["instance"] = {"node_type": "Area2D",
                                                      "children": ["CollisionShape2D"]}
        declared_chain = scene_composer.compose(
            declared_slime, out_dir=os.path.join(out_root, "declared_out"),
            bindings_path=binding_path)
        ok("extra: Area2D comes from the component scene, CollisionShape2D from the host",
           declared_chain["ok"] is True
           and declared_chain["artifact_evidence"]["checked_instances"] == ["contact_damage"],
           str((declared_chain.get("failures"), declared_chain.get("artifact_evidence"))))
        ok("extra: every reachable component scene is recorded",
           declared_chain["artifact_evidence"]["checked_external_artifacts"] == [
               "res://Features/health/Health.tscn",
               "res://Features/contact_damage/ContactDamage.tscn",
               "res://Features/chase_movement/ChaseMovement.tscn"],
           str(declared_chain["artifact_evidence"]["checked_external_artifacts"]))
        ok("extra: the generated .tscn is still byte-identical to the golden",
           open(declared_chain["scene_path"], "rb").read()
           == goldens.GOLDEN_F3.encode("utf-8"), str(declared_chain.get("failures")))
        declared_gd = generate_scene_test.build_test_source(
            scene_intent.intent_document(declared_chain["scene_intent"]),
            template_loader.load_templates(goldens.FEATURES), "Scenes/SlimeEnemy.tscn")
        ok("extra: the generated .gd is unaffected too", declared_gd == repo_gd)
        ok("extra: the plan is unchanged by verification",
           declared_chain["scene_intent"]["components"][1]["instance"]
           == {"node_type": "Area2D", "children": ["CollisionShape2D"]},
           str(declared_chain["scene_intent"]["components"]))

        # ---------------- 附件：跨产物 / 同产物 / 缺失即阻断 ----------------
        print("=== Extra: cross-artifact vs same-artifact, missing evidence blocks ===")
        host_only = write_text(os.path.join(scenes_dir, "host_only.tscn"),
                               "[gd_scene load_steps=1 format=3]\n\n"
                               "[node name=\"ExternalProbe\" type=\"Node2D\"]\n\n"
                               "[node name=\"Probe\" type=\"Area2D\" parent=\".\"]\n\n"
                               "[node name=\"Stray\" type=\"CollisionShape2D\" parent=\"Elsewhere\"]\n")
        same_pool = artifact_evidence_validator.verify_artifact_evidence(collision_intent,
                                                                        host_only)
        ok("extra: within one artifact the mount relation is still enforced",
           same_pool.status == "BLOCKED"
           and same_pool.errors == ["Artifact evidence mismatch: CollisionShape2D missing"],
           str(same_pool.to_dict()))
        missing_external_host = write_text(
            os.path.join(scenes_dir, "missing_external.tscn"),
            host_scene("probe_component", "Gone.tscn",
                       extra_nodes="\n[node name=\"HostShape\" type=\"CollisionShape2D\""
                                   " parent=\".\"]\n"))
        missing_external = artifact_evidence_validator.verify_artifact_evidence(
            intent_doc([instance_entry("probe_component", "CollisionShape2D")], ["Collision"]),
            missing_external_host)
        ok("extra: an incomplete evidence chain blocks even when the declaration is "
           "satisfiable locally",
           missing_external.status == "BLOCKED"
           and missing_external.errors == [
               "External artifact unavailable: res://Features/probe_component/Gone.tscn"],
           str(missing_external.to_dict()))

        # ---------------- 附件：向后兼容 / 解析范围 / 确定性 ----------------
        print("=== Extra: backward compatibility, parse scope, determinism ===")
        probe_ok_host = write_text(os.path.join(scenes_dir, "host_b.tscn"),
                                   host_scene("probe_component", "Probe.tscn"))
        report = artifact_evidence_validator.verify_artifact_evidence(collision_intent,
                                                                     probe_ok_host)
        # Phase 1.8.17：报告在 1.8.16 的四个键上再追加 checked_ownership（旧键语义不变）
        ok("extra: the report keeps the old keys and adds ownership",
           sorted(report.to_dict()) == ["checked_external_artifacts", "checked_instances",
                                        "checked_ownership", "errors", "status"],
           str(sorted(report.to_dict())))
        ok("extra: the old keys keep their meaning",
           set(report.to_dict()) >= {"status", "errors", "checked_instances"}
           and report.to_dict()["status"] == "PASS"
           and report.to_dict()["errors"] == []
           and report.to_dict()["checked_instances"] == ["probe_component"],
           str(report.to_dict()))
        ok("extra: verification is deterministic",
           report.to_dict()
           == artifact_evidence_validator.verify_artifact_evidence(
               collision_intent, probe_ok_host).to_dict())
        real_scene = os.path.join(PROJECT_ROOT, "Features", "contact_damage", "ContactDamage.tscn")
        parsed_real = artifact_evidence_validator.parse_artifact(real_scene)
        ok("extra: a script ext_resource is never treated as a component scene",
           external_artifact_resolver.component_scene_refs(parsed_real) == []
           and [node["type"] for node in parsed_real["nodes"]] == ["Area2D"],
           str(parsed_real))
        mixed_host = write_text(
            os.path.join(scenes_dir, "mixed.tscn"),
            "[gd_scene load_steps=2 format=3]\n\n"
            "[ext_resource type=\"PackedScene\" path=\"res://Features/probe_component/Probe.tscn\""
            " id=\"1_probe\"]\n"
            "[ext_resource type=\"PackedScene\" path=\"res://Scenes/Other.tscn\" id=\"2_other\"]\n"
            "[ext_resource type=\"SpriteFrames\" path=\"res://Assets/x.tres\" id=\"3_anim\"]\n\n"
            "[node name=\"ExternalProbe\" type=\"Node2D\"]\n\n"
            "[node name=\"Probe\" parent=\".\" instance=ExtResource(\"1_probe\")]\n\n"
            "[node name=\"Other\" parent=\".\" instance=ExtResource(\"2_other\")]\n")
        mixed = external_artifact_resolver.resolve_external_artifacts(mixed_host)
        ok("extra: only res://Features/** PackedScene references are resolved",
           mixed["status"] == "PASS" and mixed["artifacts"] == [probe_res],
           str(mixed))
        undeclared = intent_doc([{"component": "probe_component"}], ["Node"])
        ok("extra: without a declaration nothing is read (missing path is fine)",
           artifact_evidence_validator.verify_artifact_evidence(
               undeclared, os.path.join(tmp, "no_such_host.tscn")).to_dict() == {
                   "status": "PASS", "errors": [], "checked_instances": [],
                   "checked_external_artifacts": [], "checked_ownership": []})
        rejected_ok, message = rejected(
            lambda: artifact_evidence_validator.verify_artifact_evidence(
                copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME), probe_ok_host))
        ok("extra: raw Blueprint input is rejected (single Intent boundary)",
           rejected_ok, message)

        # ---------------- 附件：职责隔离 ----------------
        print("=== Extra: isolation (no Blueprint / Registry / Godot / writes) ===")
        forbidden = {"blueprint", "feature_index", "feature_registry", "capability_registry",
                     "PackedScene", "SceneTree", "godot", "Godot", "write", "remove",
                     "unlink", "rmtree"}
        for module, allowed in (("external_artifact_resolver.py",
                                 {"os", "re", "sys"}),
                                # Phase 1.8.17：归属层是 artifact 层的同一封闭集合成员
                                ("artifact_evidence_validator.py",
                                 {"os", "component_instance_ownership",
                                  "external_artifact_resolver", "scene_intent", "sys"}),
                                ("component_instance_ownership.py",
                                 {"external_artifact_resolver", "scene_intent", "sys"})):
            source = open(os.path.join(TOOL_DIR, module), encoding="utf-8").read()
            identifiers, _strings = code_tokens(source)
            ok("extra: %s never touches Blueprint / Registry / Godot / file writes" % module,
               not (identifiers & forbidden), str(sorted(identifiers & forbidden)))
            ok("extra: %s imports stay inside the static artifact layer" % module,
               imported_modules(source) <= allowed, str(sorted(imported_modules(source))))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all external artifact evidence checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
