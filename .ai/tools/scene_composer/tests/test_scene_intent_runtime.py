#!/usr/bin/env python3
"""Scene Intent 运行时物化测试（Phase 1.8.6）

验证 .ai/tools/scene_composer/scene_intent.py 的 SceneIntentBuilder：

    Case 1  Blueprint → Scene Intent（scene / root / components / nodes / resources / validation）
    Case 2  Binding provenance 被忽略（不修改、不升级、不发明）
    Case 3  缺失资源只降级为警告（不编造资源节点）
    Case 4  生成行为零变化（Phase 1.8.7：builder 唯一输入 = Scene Intent；
            composer 产物与 builder 直接产物逐字相同 + 不落盘）
    Case 5  known gap 表征：Entity Blueprint 的 nodes: 仍被丢弃（契约 entity_blueprint_nodes_dropped）
    Case 6  文档形态稳定（PLANNED 段不得出现）

本测试只读项目、只写临时目录；不生成 .tscn 到仓库、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_scene_intent_runtime.py
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
DOTAI = os.path.dirname(os.path.dirname(TOOL_DIR))                 # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)

for path in (TOOL_DIR, os.path.join(DOTAI, "tools")):
    if path not in sys.path:
        sys.path.insert(0, path)

import asset_nodes                                             # noqa: E402
import scene_builder                                           # noqa: E402
import scene_composer                                          # noqa: E402
import scene_intent                                            # noqa: E402
import template_loader                                         # noqa: E402

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def normalized(bp: dict) -> dict:
    """走真实规整链路（derive + normalize）。"""
    derived = template_loader.derive_scene_blueprint(bp)
    blueprint, errors = template_loader.normalize_scene_blueprint(derived)
    if errors:
        raise AssertionError("normalize failed: %s" % errors)
    return blueprint


def write_binding(tmp: str, doc: dict, name: str = "binding.yaml") -> str:
    path = os.path.join(tmp, name)
    import yaml
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return path


def compat_legacy(intent):
    """Phase 1.8.7 已弃用的兼容访问器（诊断用；禁止作为生成输入）。"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return intent.to_legacy_dict()


def rejected(fn) -> bool:
    try:
        fn()
    except ValueError:
        return True
    return False


def scene_blueprint_with_nodes() -> dict:
    return {
        "scene": {"id": "probe_unit"},
        "root": {"type": "CharacterBody2D", "name": "ProbeUnit",
                 "groups": ["enemies"], "properties": {"motion_mode": 1}},
        "components": [{"feature": "health"}, {"feature": "contact_damage"},
                       {"feature": "chase_movement"}],
        "nodes": [
            {"type": "CollisionShape2D", "name": "ProbeShape",
             "shape": {"type": "circle", "radius": 12}},
            {"type": "Node2D", "name": "Marker", "parent": "."},
        ],
        "validation": {"required_tests": ["health", "contact_damage", "chase_movement"]},
    }


BINDING_WITH_PROVENANCE = {
    "schema_version": 2,
    "binding": {
        "entity": "probe_unit",
        "role": "enemy",
        "subject": "slime",
        "features": ["health", "contact_damage", "chase_movement"],
        "bindings": [
            {
                "role": "idle",
                "asset": "slime_frames",
                "path": "res://Assets/characters/enemy/slime/slime_frames.tres",
                "type": "sprite_frames",
                "node": {
                    "name": "ProbeAnim",
                    "type": "AnimatedSprite2D",
                    "property": "sprite_frames",
                    "path": "res://Assets/characters/enemy/slime/slime_frames.tres",
                    "roles": ["idle", "move", "attack", "hurt"],
                    "animation": "idle",
                },
                # 以下 provenance 字段必须被忽略（不携带 / 不升级 / 不发明）
                "resolved_from": "index",
                "compatibility": "WARNING",
                "confidence": "low",
                "runners_up": ["player_idle"],
                "note": "fallback",
            },
            {
                "role": "hurt_sfx",
                "asset": "slime_hurt_sfx",
                "path": "res://Assets/audio/slime/hurt.wav",
                "type": "audio",
                "node": {
                    "name": "ProbeHurtSfx",
                    "type": "AudioStreamPlayer",
                    "property": "stream",
                    "path": "res://Assets/audio/slime/hurt.wav",
                    "roles": ["hurt_sfx"],
                },
                "resolved_from": "binding",
                "compatibility": "COMPATIBLE",
                "confidence": "high",
            },
        ],
        "missing": [],
        "optional_missing": [],
    },
}

BINDING_MISSING_ONLY = {
    "schema_version": 2,
    "binding": {
        "entity": "probe_unit",
        "role": "enemy",
        "subject": "slime",
        "features": ["health"],
        "bindings": [],
        "missing": [{"role": "idle", "kind": "required",
                     "reason": "no candidate asset for role idle"}],
        "optional_missing": [],
    },
}


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="scene_intent_runtime_")
    try:
        # ---------------- Case 1: Blueprint → Scene Intent ----------------
        print("=== Case 1: Blueprint -> Scene Intent ===")
        bp1 = scene_blueprint_with_nodes()
        blueprint = normalized(copy.deepcopy(bp1))
        blueprint["resource_nodes"], info = asset_nodes.nodes_for_blueprint(
            bp1, bindings_path=write_binding(tmp, BINDING_WITH_PROVENANCE))
        ok("case1: asset nodes resolved from Binding",
           len(blueprint["resource_nodes"]) == 2, str(info))

        intent = scene_intent.build_scene_intent(blueprint)
        doc = intent.to_dict()
        ok("case1: document identity", doc.get("document") == "scene_intent"
           and doc.get("schema_version") == 1, str((doc.get("document"), doc.get("schema_version"))))
        ok("case1: scene.id exists", doc["scene"]["id"] == "probe_unit", str(doc["scene"]))
        ok("case1: root.name/type mapped",
           doc["root"].get("name") == "ProbeUnit" and doc["root"].get("type") == "CharacterBody2D",
           str(doc["root"]))
        ok("case1: root.groups/properties mapped from root_extra",
           doc["root"].get("groups") == ["enemies"]
           and doc["root"].get("properties") == {"motion_mode": 1}, str(doc["root"]))
        ok("case1: components[].component from features[]",
           [c["component"] for c in doc["components"]]
           == ["health", "contact_damage", "chase_movement"], str(doc["components"]))
        ok("case1: components have no invented node/scene",
           all(set(c.keys()) == {"component"} for c in doc["components"]),
           str(doc["components"]))
        ok("case1: nodes generated (name/type/parent/shape preserved)",
           len(doc["nodes"]) == 2
           and doc["nodes"][0]["name"] == "ProbeShape"
           and doc["nodes"][0]["type"] == "CollisionShape2D"
           and doc["nodes"][0]["shape"] == {"type": "circle", "radius": 12}
           and doc["nodes"][1]["parent"] == ".", str(doc["nodes"]))
        ok("case1: nodes carry no builder-internal keys",
           all(not any(str(k).startswith("_") for k in n) for n in doc["nodes"]),
           str(doc["nodes"]))
        ok("case1: resources generated (2)",
           len(doc["resources"]) == 2, str(doc["resources"]))
        ok("case1: resource fields preserved",
           doc["resources"][0]["name"] == "ProbeAnim"
           and doc["resources"][0]["property"] == "sprite_frames"
           and doc["resources"][0]["path"].startswith("res://")
           and doc["resources"][0]["roles"] == ["idle", "move", "attack", "hurt"]
           and doc["resources"][0]["animation"] == "idle"
           and doc["resources"][0]["asset"] == "slime_frames",
           str(doc["resources"][0]))
        ok("case1: resource excludes build-time ext_type",
           all("ext_type" not in r for r in doc["resources"]), str(doc["resources"][0]))
        ok("case1: validation.required_tests mapped",
           doc["validation"]["required_tests"]
           == ["health", "contact_damage", "chase_movement"], str(doc["validation"]))

        # ---------------- Case 2: provenance 被忽略 ----------------
        print("=== Case 2: Binding provenance ignored ===")
        entries = BINDING_WITH_PROVENANCE["binding"]["bindings"]
        ok("case2: input really carries provenance (fixture sanity)",
           entries[0]["resolved_from"] == "index" and entries[0]["confidence"] == "low"
           and entries[1]["resolved_from"] == "binding")
        for field in scene_intent.PROVENANCE_FIELDS:
            ok("case2: provenance %r not carried (contract status PLANNED)" % field,
               all(field not in r for r in doc["resources"]),
               str(doc["resources"][0]))
        flat = json.dumps(doc, ensure_ascii=False)
        ok("case2: no invented provenance value ('verified')", "verified" not in flat)
        ok("case2: no upgrade index -> binding",
           "binding" not in flat, "index source must not surface as binding")
        ok("case2: no default/upgraded compatibility injected",
           "COMPATIBLE" not in flat and "WARNING" not in flat)

        # ---------------- Case 3: 缺失资源只警告 ----------------
        print("=== Case 3: missing asset -> warning only ===")
        bp3 = scene_blueprint_with_nodes()
        blueprint3 = normalized(copy.deepcopy(bp3))
        nodes3, info3 = asset_nodes.nodes_for_blueprint(
            bp3, bindings_path=write_binding(tmp, BINDING_MISSING_ONLY, "missing.yaml"))
        ok("case3: no resource node produced from missing binding", nodes3 == [], str(nodes3))
        ok("case3: binding reports missing roles", info3["missing"] == [
            "no candidate asset for role idle"], str(info3["missing"]))
        blueprint3["resource_nodes"] = nodes3
        doc3 = scene_intent.build_scene_intent(blueprint3).to_dict()
        ok("case3: intent resources empty (nothing invented)", doc3["resources"] == [],
           str(doc3["resources"]))
        ok("case3: intent has no fabricated asset id or res:// path",
           "asset" not in json.dumps(doc3.get("resources") or [])
           and "res://" not in json.dumps(doc3.get("resources") or []))

        # ---------------- Case 4: 生成行为零变化 ----------------
        print("=== Case 4: generation behavior unchanged ===")
        bp4 = scene_blueprint_with_nodes()
        blueprint4 = normalized(copy.deepcopy(bp4))
        blueprint4["resource_nodes"], _ = asset_nodes.nodes_for_blueprint(
            bp4, bindings_path=write_binding(tmp, BINDING_WITH_PROVENANCE, "case4.yaml"))
        snapshot = copy.deepcopy(blueprint4)

        intent4 = scene_intent.build_scene_intent(blueprint4)
        ok("case4: intent builder is a pure projection (input untouched)",
           blueprint4 == snapshot,
           str({k: blueprint4[k] for k in blueprint4 if blueprint4.get(k) != snapshot.get(k)}))
        ok("case4: to_legacy_dict() is a deprecated compat accessor (same internal object)",
           compat_legacy(intent4) is blueprint4)
        ok("case4: to_dict() returns a deep copy",
           intent4.to_dict() is not intent4.document)

        templates = template_loader.load_templates(blueprint4["features"])
        features_dir = template_loader.FEATURES_DIR
        from_intent = scene_builder.build_tscn(intent4, templates, features_dir)
        ok("case4: object API and contract document mapping yield the same text",
           from_intent == scene_builder.build_tscn(intent4.to_dict(), templates, features_dir))

        # 全链路：compose() 写出的 .tscn 必须与 builder 直接消费 Scene Intent 的产物逐字相同
        out_dir = os.path.join(tmp, "case4_scenes")
        result4 = scene_composer.compose(
            copy.deepcopy(bp4), out_dir=out_dir,
            bindings_path=write_binding(tmp, BINDING_WITH_PROVENANCE, "case4b.yaml"))
        ok("case4: compose() still succeeds", result4.get("ok") is True,
           str(result4.get("failures")))
        written = open(result4["scene_path"], encoding="utf-8", newline="").read()
        ok("case4: composer output == builder output from the Scene Intent",
           written == from_intent,
           "len=%d vs %d" % (len(written), len(from_intent)))
        ok("case4: legacy internal dict is no longer a legal builder input",
           rejected(lambda: scene_builder.build_tscn(compat_legacy(intent4), templates, features_dir)))
        ok("case4: no scene file written by the intent layer",
           [f for f in os.listdir(tmp) if f.endswith(".tscn")] == [])

        # ---------------- Case 5: known gap 表征 ----------------
        print("=== Case 5: known gap (entity blueprint nodes:) ===")
        entity_bp = {
            "entity": {"id": "probe_entity", "role": "enemy"},
            "features": ["health", "contact_damage", "chase_movement"],
            "nodes": [{"type": "CollisionShape2D", "name": "EntityShape",
                       "shape": {"type": "circle", "radius": 8}}],
        }
        entity_intent = scene_intent.build_scene_intent(normalized(entity_bp)).to_dict()
        # 契约 known_gaps.entity_blueprint_nodes_dropped（status: open）：
        # 当前行为是「静默丢弃」。本断言表征现状；实现阶段修掉该 gap 时，
        # 必须同步更新契约状态与本测试（不得为通过而弱化断言）。
        ok("case5: entity blueprint nodes: dropped (documented gap)",
           entity_intent["nodes"] == [], str(entity_intent["nodes"]))
        ok("case5: components still mapped for entity blueprint",
           len(entity_intent["components"]) == 3, str(entity_intent["components"]))

        # ---------------- Case 6: 文档形态稳定 ----------------
        print("=== Case 6: document shape stability ===")
        bare = scene_intent.build_scene_intent(normalized(scene_blueprint_with_nodes())).to_dict()
        # Phase 1.8.10：文档新增 capabilities（能力声明层，默认 required=[]）
        ok("case6: keys stable without Binding input",
           sorted(bare.keys()) == sorted(["document", "schema_version", "scene", "root",
                                          "components", "capabilities", "nodes", "resources",
                                          "validation"]),
           str(sorted(bare.keys())))
        # Phase 1.8.12（Feature Data Migration）：成员 Feature（health / contact_damage /
        # chase_movement）已声明能力，故真实链路不再是空列表；无声明工况仍由
        # test_feature_capability_pipeline.py Case 1 覆盖。
        ok("case6: capabilities carries the member Feature declaration union",
           bare["capabilities"] == {"required": ["Node", "Collision"]},
           str(bare.get("capabilities")))
        ok("case6: resources empty list (no Binding consumed)", bare["resources"] == [])
        for planned in ("metadata", "scripts", "animations"):
            ok("case6: PLANNED block %r absent" % planned, planned not in bare)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all scene intent runtime checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
