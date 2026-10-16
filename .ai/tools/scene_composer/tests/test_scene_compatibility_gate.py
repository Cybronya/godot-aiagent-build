#!/usr/bin/env python3
"""Scene Compatibility Gate 测试（Phase 1.8.9 骨架）

    Case 1  合法 Scene Intent -> PASS（报告结构 + checked_* 内容）
    Case 2  旧规整内部 dict / 原始 Blueprint -> ValueError（且不产生任何文件）
    Case 3  未知 / 不支持 component -> BLOCKED（含能力类别名可通过）
    Case 4  1.8.8 的六个 validator 构造场景：先过闸门，结果与 1.8.8 逐字相同
    Case 5  Scene Builder 生成结果与 1.8.7/1.8.8 基线 golden 逐字节相同
    Case 6  集成：compose() 在 BLOCKED 时停止生成、零产物；PASS 时行为不变（含附件字段）

Case 5 的 golden 与 fixture 直接复用 test_scene_builder_intent_input.py 的常量
（同一个测试目录；避免第二份基线）。

本测试只读项目、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_scene_compatibility_gate.py
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
DOTAI = os.path.dirname(TOOLS_DIR)                                 # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)

for path in (TOOL_DIR, TOOLS_DIR, VALIDATOR_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import asset_nodes                                             # noqa: E402
import check_scene_composition                                # noqa: E402
import compatibility_gate                                      # noqa: E402
import scene_builder                                           # noqa: E402
import scene_composer                                          # noqa: E402
import scene_intent                                            # noqa: E402
import scene_validator                                         # noqa: E402
import template_loader                                         # noqa: E402
import test_scene_builder_intent_input as goldens              # noqa: E402  (共享 fixture + golden)

FEATURES = goldens.FEATURES
SLIME_TRES = goldens.SLIME_TRES

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


def intent_with(components, resources=None, root=None) -> dict:
    """最小 Scene Intent 文档（直构，用于检验闸门本身；不经过 CLI 链路）。"""
    return {
        "document": "scene_intent",
        "schema_version": 1,
        "scene": {"id": "probe"},
        "root": root or {"name": "Probe", "type": "CharacterBody2D"},
        "components": [{"component": c} for c in components],
        "nodes": [],
        "resources": list(resources or []),
        "validation": {"required_tests": []},
    }


def resource(name, node_type) -> dict:
    return {"name": name, "type": node_type, "property": "texture", "path": "res://x.tres"}


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="compat_gate_")
    try:
        features_dir = template_loader.FEATURES_DIR
        templates = template_loader.load_templates(FEATURES)
        index = json.load(open(os.path.join(DOTAI, "context", "feature_index.json"),
                               encoding="utf-8")).get("features", [])
        binding_path = goldens.write_binding(tmp, goldens.BINDING_SLIME)

        # 真实链路 intent（含 2 个资源节点）
        intent = goldens.intent_for(goldens.SCENE_BLUEPRINT_SLIME, binding_path)

        # ---------------- Case 1: 合法 Intent -> PASS ----------------
        print("=== Case 1: valid intent passes ===")
        report = compatibility_gate.check_scene_compatibility(intent)
        ok("case1: status PASS", report.status == compatibility_gate.STATUS_PASS
           and report.ok, str(report))
        ok("case1: no errors / no warnings", report.errors == [] and report.warnings == [],
           "%s / %s" % (report.errors, report.warnings))
        ok("case1: checked_components are the intent components (order kept)",
           report.checked_components == FEATURES, str(report.checked_components))
        ok("case1: checked_resources are the intent resource nodes",
           report.checked_resources == ["SlimeAnim", "SlimeHurtSfx"],
           str(report.checked_resources))
        as_dict = report.to_dict()
        # Phase 1.8.10 扩展：报告新增 checked_capabilities（能力声明核对结果）
        ok("case1: report is an explicit structure with the 6 contract keys",
           sorted(as_dict.keys()) == sorted(["status", "errors", "warnings",
                                             "checked_components", "checked_resources",
                                             "checked_capabilities"]),
           str(sorted(as_dict.keys())))
        ok("case1: contract document mapping accepted too",
           compatibility_gate.check_scene_compatibility(intent.to_dict()).to_dict() == as_dict)
        ok("case1: STATUS vocabulary is exactly PASS / BLOCKED",
           compatibility_gate.STATUS_PASS == "PASS"
           and compatibility_gate.STATUS_BLOCKED == "BLOCKED")
        ok("case1: capability registries declared",
           compatibility_gate.SUPPORTED_COMPONENT_CAPABILITIES
           == ("Node", "Sprite", "AnimatedSprite", "Audio", "Collision")
           and compatibility_gate.SUPPORTED_RESOURCE_CAPABILITIES
           == ("Texture2D", "SpriteFrames", "AudioStreamWAV")
           # Phase 1.8.10：预留能力词汇扩为 5 项（新增 Animation），事实源迁到 capability_registry
           and compatibility_gate.UNSUPPORTED_CAPABILITIES
           == ("Script", "Animation", "AnimationController", "AI", "RuntimeBehaviour")
           and compatibility_gate.SUPPORTED_COMPONENT_CAPABILITIES
           is compatibility_gate.capability_registry.SUPPORTED_COMPONENT_CAPABILITIES,
           str(compatibility_gate.SUPPORTED_COMPONENT_CAPABILITIES))

        # ---------------- Case 2: 旧 dict / 原始 Blueprint 被拒绝 ----------------
        print("=== Case 2: non-intent inputs are rejected ===")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            legacy = intent.to_legacy_dict()
        ok("case2: fixture really is the normalized internal dict",
           "root_name" in legacy and "extra_nodes" in legacy)
        before = sorted(os.listdir(tmp))
        rejected_ok, message = rejected(
            lambda: compatibility_gate.check_scene_compatibility(legacy))
        ok("case2: legacy internal dict raises ValueError", rejected_ok, message)
        ok("case2: rejection names the Scene Intent boundary", "rejected" in message, message)
        rejected_ok, message = rejected(
            lambda: compatibility_gate.check_scene_compatibility(copy.deepcopy(
                goldens.SCENE_BLUEPRINT_SLIME)))
        ok("case2: raw Blueprint (no Scene Intent identity) raises ValueError",
           rejected_ok, message)
        rejected_ok, message = rejected(
            lambda: compatibility_gate.check_scene_compatibility(None))
        ok("case2: non-mapping input raises ValueError", rejected_ok, message)
        ok("case2: rejected inputs write nothing",
           sorted(os.listdir(tmp)) == before, str(sorted(os.listdir(tmp))))

        # ---------------- Case 3: 未知 / 不支持 component -> BLOCKED ----------------
        print("=== Case 3: unsupported component blocks ===")
        blocked = compatibility_gate.check_scene_compatibility(intent_with(["health", "Script"]))
        ok("case3: Script -> BLOCKED", blocked.status == compatibility_gate.STATUS_BLOCKED)
        ok("case3: Script error message", blocked.errors == ["Unsupported component: Script"],
           str(blocked.errors))
        ok("case3: blocked report still records the accepted components",
           blocked.checked_components == ["health"], str(blocked.checked_components))
        ai_blocked = compatibility_gate.check_scene_compatibility(intent_with(["EnemyAI"]))
        ok("case3: unknown id (EnemyAI) -> BLOCKED",
           ai_blocked.status == compatibility_gate.STATUS_BLOCKED
           and ai_blocked.errors == ["Unsupported component: EnemyAI"], str(ai_blocked.errors))
        for marker in compatibility_gate.UNSUPPORTED_CAPABILITIES:
            caps = compatibility_gate.check_scene_compatibility(intent_with([marker]))
            ok("case3: declared-unsupported capability %r blocks" % marker,
               caps.status == compatibility_gate.STATUS_BLOCKED
               and caps.errors == ["Unsupported component: %s" % marker], str(caps.errors))
        capability_only = compatibility_gate.check_scene_compatibility(
            intent_with(["Sprite", "Collision"]))
        ok("case3: capability-class names pass and are recorded as classes",
           capability_only.status == compatibility_gate.STATUS_PASS
           and capability_only.checked_components == ["Sprite", "Collision"],
           str(capability_only.to_dict()))
        ok("case3: unknown resource node type blocks",
           compatibility_gate.check_scene_compatibility(
               intent_with(["health"], [resource("Weird", "Node2D")])).errors
           == ["Unsupported resource type: Node2D"])
        ok("case3: PLANNED sections (scripts / animations) block when present",
           compatibility_gate.check_scene_compatibility(
               dict(intent_with(["health"]), scripts=[{"node": "X", "script": "res://x.gd"}])
           ).errors == ["Unsupported Scene Intent section: scripts (not implemented in this phase)"]
           and compatibility_gate.check_scene_compatibility(
               dict(intent_with(["health"]), animations=[{"player": "P"}])).errors
           == ["Unsupported Scene Intent section: animations (not implemented in this phase)"])
        long_chain = compatibility_gate.check_scene_compatibility(
            intent_with(["health", "Script"], [resource("Weird", "Node2D")]))
        ok("case3: multiple violations are all reported (no early exit)",
           len(long_chain.errors) == 2 and long_chain.checked_components == ["health"],
           str(long_chain.errors))
        ok("case3: a blocked intent still validates as an intent (gate does not raise)",
           compatibility_gate.check_scene_compatibility(intent_with(["EnemyAI"])).to_dict()
           ["status"] == compatibility_gate.STATUS_BLOCKED)
        ok("case3: registry degradation is a warning, not an error",
           compatibility_gate.check_scene_compatibility(intent_with(["health"]),
                                                        index_path="/nonexistent/index.json")
           .warnings == ["Feature Registry index unavailable: component capability check "
                         "degraded"])

        # ---------------- Case 4: 六个 validator 构造场景 ----------------
        print("=== Case 4: the 1.8.8 validator fixtures are unaffected by the gate ===")
        text = scene_builder.build_tscn(intent, templates, features_dir)
        variants = {
            "a_pass": text,
            "b_missing_feature": text.replace(
                '[node name="Health" parent="." instance=ExtResource("1_health")]\n\n', ""),
            "c_wrong_root_type": text.replace('type="CharacterBody2D"', 'type="Node2D"', 1),
            "d_root_script": text.replace(
                '[node name="SlimeEnemy" type="CharacterBody2D"]',
                '[node name="SlimeEnemy" type="CharacterBody2D"]\nscript = ExtResource("9_gd")'),
            "e_bad_parent_path": text
            + '\n[node name="GhostChild" type="Node2D" parent="Ghost"]\n',
            "f_duplicate_name": text + '\n[node name="Health" type="Node2D" parent="."]\n',
        }
        # Phase 1.8.8 基线（迁移前 validate_scene 对这 6 个场景的输出，见 1.8.8 报告）
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
        for name, body in sorted(variants.items()):
            path = os.path.join(tmp, name + ".tscn")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(body)
            gate = compatibility_gate.check_scene_compatibility(intent)
            ok("case4: %s passes the gate (gate is not a validator)" % name,
               gate.ok and gate.errors == [], str(gate.errors))
            result = scene_validator.validate_scene(intent, path, index, templates, features_dir)
            ok("case4: %s validation result identical to the 1.8.8 baseline" % name,
               (result["ok"], sorted(result["failures"]))
               == (expected[name][0], sorted(expected[name][1])),
               str((result["ok"], sorted(result["failures"]))))
            ok("case4: %s check_scene_composition entry agrees" % name,
               sorted(check_scene_composition.check_scene_composition(
                   goldens.SCENE_BLUEPRINT_SLIME, path)["failures"])
               == sorted(expected[name][1]))

        # ---------------- Case 5: 生成结果与基线逐字节相同 ----------------
        print("=== Case 5: builder output stays byte-identical through the gate ===")
        ok("case5: slime .tscn matches the 1.8.8 golden",
           scene_builder.build_tscn(intent, templates, features_dir) == goldens.GOLDEN_F3)
        probe = goldens.intent_for(goldens.SCENE_BLUEPRINT_PROBE)
        ok("case5: probe .tscn matches the 1.8.8 golden",
           scene_builder.build_tscn(probe, templates, features_dir) == goldens.GOLDEN_F1)

        # ---------------- Case 6: compose() 集成（BLOCKED 停止生成） ----------------
        print("=== Case 6: composer integration ===")
        out_dir = os.path.join(tmp, "composed")
        result = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                        out_dir=out_dir, bindings_path=binding_path)
        ok("case6: PASS path keeps generating", result["ok"] is True, str(result["failures"]))
        ok("case6: composer output equals the builder golden",
           open(result["scene_path"], encoding="utf-8", newline="").read() == goldens.GOLDEN_F3)
        ok("case6: report attached to the envelope as an additive key",
           result["compatibility"]["status"] == "PASS"
           and result["compatibility"]["checked_components"] == FEATURES,
           str(result.get("compatibility")))

        blocked_out = os.path.join(tmp, "blocked")
        original = scene_composer.check_scene_compatibility

        def block(_intent, *args, **kwargs):
            return compatibility_gate.CompatibilityReport(
                compatibility_gate.STATUS_BLOCKED, ["Unsupported component: Script"],
                checked_components=["health"])

        scene_composer.check_scene_compatibility = block
        try:
            blocked_result = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                                    out_dir=blocked_out, bindings_path=binding_path)
        finally:
            scene_composer.check_scene_compatibility = original
        ok("case6: BLOCKED stops generation", blocked_result["ok"] is False,
           str(blocked_result.get("failures")))
        ok("case6: BLOCKED failures carry the gate errors",
           blocked_result["failures"] == ["Compatibility Gate: Unsupported component: Script"],
           str(blocked_result["failures"]))
        ok("case6: BLOCKED produces no file at all (no half-written scene)",
           not os.path.isdir(blocked_out)
           or [f for f in os.listdir(blocked_out) if f.endswith(".tscn")] == [],
           str(os.listdir(blocked_out) if os.path.isdir(blocked_out) else "<no dir>"))
        ok("case6: BLOCKED still returns the plan + report for diagnosis",
           blocked_result["scene_intent"]["document"] == "scene_intent"
           and blocked_result["compatibility"]["status"] == "BLOCKED")
        ok("case6: gate is a real consumer of the intent (rejects non-intent input)",
           rejected(lambda: scene_composer.check_scene_compatibility(
               goldens.SCENE_BLUEPRINT_SLIME))[0])

        # ---------------- 附件：闸门不读 nodes[] / validation[] ----------------
        print("=== Extra: gate reads only what it declares ===")
        stripped = intent.to_dict()
        stripped["nodes"] = []
        stripped["validation"] = {"required_tests": []}
        ok("extra: nodes[] / validation[] do not influence the gate verdict",
           compatibility_gate.check_scene_compatibility(stripped).to_dict()
           == compatibility_gate.check_scene_compatibility(intent).to_dict())
        source = open(os.path.join(TOOL_DIR, "compatibility_gate.py"), encoding="utf-8").read()
        ok("extra: gate source never reads the normalized dict",
           "blueprint[" not in source and "blueprint.get(" not in source)
        ok("extra: gate source uses the shared intent boundary helpers",
           "from scene_intent import (intent_capabilities, intent_components, intent_document, "
           "intent_root)" in source)
        ok("extra: gate never imports the builder / writer",
           "import scene_builder" not in source and "write_scene" not in source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all scene compatibility gate checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
