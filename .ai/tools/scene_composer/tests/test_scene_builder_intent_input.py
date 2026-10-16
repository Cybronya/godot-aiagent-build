#!/usr/bin/env python3
"""Scene Builder 的 Scene Intent 输入边界测试（Phase 1.8.7）

    Case 1  SceneIntent → builder：接受 SceneIntent（对象 / 契约文档 mapping），
            产出与 Phase 1.8.6 基线**逐字相同**的 .tscn（结构 + load_steps + 顺序）
    Case 2  兼容性决策 = **拒绝旧规整内部 dict**（无隐藏转换、无兼容适配器）
    Case 3  resources[] → ext_resource（类型由 path 经既有资源映射派生）+ 节点引用
    Case 4  provenance / Scene Intent 不可变（不计算、不升级、不携带、不污染文档）

基线（golden）：下文的 .tscn 文本取自 Phase 1.8.6（本阶段改动前）通过
`scene_composer.compose()` 生成的产物，逐字节固定；本阶段只允许「输出等价」。

本测试只读项目、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_scene_builder_intent_input.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import copy
import os
import shutil
import sys
import tempfile
import warnings

_HERE = os.path.dirname(os.path.abspath(__file__))                 # .ai/tools/scene_composer/tests
TOOL_DIR = os.path.dirname(_HERE)                                  # .ai/tools/scene_composer
TOOLS_DIR = os.path.dirname(TOOL_DIR)                              # .ai/tools
DOTAI = os.path.dirname(TOOLS_DIR)                                 # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)

for path in (TOOL_DIR, TOOLS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import asset_nodes                                             # noqa: E402
import scene_builder                                           # noqa: E402
import scene_intent                                            # noqa: E402
import template_loader                                         # noqa: E402

# ---------------------------------------------------------------- 基线（Phase 1.8.6 产物）

GOLDEN_F1 = """[gd_scene load_steps=5 format=3]

[ext_resource type="PackedScene" path="res://Features/health/Health.tscn" id="1_health"]
[ext_resource type="PackedScene" path="res://Features/contact_damage/ContactDamage.tscn" id="2_contact_damage"]
[ext_resource type="PackedScene" path="res://Features/chase_movement/ChaseMovement.tscn" id="3_chase_movement"]

[sub_resource type="CircleShape2D" id="CircleShape2D_ProbeShape_1"]
radius = 12

[node name="ProbeUnit" type="CharacterBody2D"]
motion_mode = 1
groups = ["enemies"]

[node name="Health" parent="." instance=ExtResource("1_health")]

[node name="ContactDamage" parent="." instance=ExtResource("2_contact_damage")]

[node name="ChaseMovement" parent="." instance=ExtResource("3_chase_movement")]

[node name="ProbeShape" type="CollisionShape2D" parent="."]
shape = SubResource("CircleShape2D_ProbeShape_1")

[node name="Marker" type="Node2D" parent="."]
"""

GOLDEN_F3 = """[gd_scene load_steps=7 format=3]

[ext_resource type="PackedScene" path="res://Features/health/Health.tscn" id="1_health"]
[ext_resource type="PackedScene" path="res://Features/contact_damage/ContactDamage.tscn" id="2_contact_damage"]
[ext_resource type="PackedScene" path="res://Features/chase_movement/ChaseMovement.tscn" id="3_chase_movement"]
[ext_resource type="SpriteFrames" path="res://Assets/characters/enemy/slime/slime_frames.tres" id="4_asset_SlimeAnim"]
[ext_resource type="AudioStreamWAV" path="res://Assets/audio/slime/hurt.wav" id="5_asset_SlimeHurtSfx"]

[sub_resource type="CircleShape2D" id="CircleShape2D_SlimeShape_1"]
radius = 10

[node name="SlimeEnemy" type="CharacterBody2D"]
motion_mode = 1
groups = ["enemies"]

[node name="Health" parent="." instance=ExtResource("1_health")]

[node name="ContactDamage" parent="." instance=ExtResource("2_contact_damage")]

[node name="ChaseMovement" parent="." instance=ExtResource("3_chase_movement")]

[node name="SlimeShape" type="CollisionShape2D" parent="."]
shape = SubResource("CircleShape2D_SlimeShape_1")

[node name="SlimeAnim" type="AnimatedSprite2D" parent="."]
sprite_frames = ExtResource("4_asset_SlimeAnim")
animation = &"idle"

[node name="SlimeHurtSfx" type="AudioStreamPlayer" parent="."]
stream = ExtResource("5_asset_SlimeHurtSfx")
"""

# ---------------------------------------------------------------- 输入fixture

FEATURES = ["health", "contact_damage", "chase_movement"]

SCENE_BLUEPRINT_PROBE = {
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
    "validation": {"required_tests": FEATURES},
}

SCENE_BLUEPRINT_SLIME = {
    "scene": {"id": "slime_enemy"},
    "root": {"type": "CharacterBody2D", "name": "SlimeEnemy", "groups": ["enemies"],
             "properties": {"motion_mode": 1}},
    "components": [{"feature": "health"}, {"feature": "contact_damage"},
                   {"feature": "chase_movement"}],
    "nodes": [{"type": "CollisionShape2D", "name": "SlimeShape",
               "shape": {"type": "circle", "radius": 10}}],
    "validation": {"required_tests": FEATURES},
}

SLIME_TRES = "res://Assets/characters/enemy/slime/slime_frames.tres"
SLIME_WAV = "res://Assets/audio/slime/hurt.wav"


def _anim_entry(role: str, compatibility: str, resolved_from: str, confidence: str) -> dict:
    return {
        "role": role,
        "asset": "slime_frames",
        "path": SLIME_TRES,
        "type": "sprite_frames",
        "node": {"name": "SlimeAnim", "type": "AnimatedSprite2D",
                 "property": "sprite_frames", "path": SLIME_TRES,
                 "roles": ["idle", "move", "attack", "hurt"], "animation": "idle"},
        # provenance（Binding 契约字段；Scene 层只读且当前 PLANNED → 必须不被携带/改写）
        "compatibility": compatibility,
        "resolved_from": resolved_from,
        "confidence": confidence,
        "runners_up": ["player_frames"],
    }


BINDING_SLIME = {
    "schema_version": 2,
    "binding": {
        "entity": "slime_enemy",
        "role": "enemy",
        "subject": "slime",
        "features": FEATURES,
        "bindings": [
            _anim_entry("idle", "COMPATIBLE", "index", "high"),
            _anim_entry("move", "COMPATIBLE", "index", "high"),
            _anim_entry("attack", "WARNING", "index", "medium"),
            _anim_entry("hurt", "WARNING", "index", "low"),
            {
                "role": "hurt_sfx",
                "asset": "slime_hurt_sfx",
                "path": SLIME_WAV,
                "type": "audio",
                "node": {"name": "SlimeHurtSfx", "type": "AudioStreamPlayer",
                         "property": "stream", "path": SLIME_WAV,
                         "roles": ["hurt_sfx"]},
                "compatibility": "COMPATIBLE",
                "resolved_from": "index",
                "confidence": "high",
            },
        ],
        "missing": [],
        "optional_missing": [],
    },
}

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def write_binding(tmp: str, doc: dict, name: str = "binding.yaml") -> str:
    import yaml
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return path


def intent_for(blueprint_raw: dict, bindings_path: str = ""):
    """走真实链路：derive -> normalize -> (Binding 资源节点) -> SceneIntentBuilder。"""
    derived = template_loader.derive_scene_blueprint(copy.deepcopy(blueprint_raw))
    blueprint, errors = template_loader.normalize_scene_blueprint(derived)
    if errors:
        raise AssertionError("normalize failed: %s" % errors)
    if bindings_path:
        blueprint["resource_nodes"], _info = asset_nodes.nodes_for_blueprint(
            blueprint_raw, bindings_path=bindings_path)
    else:
        blueprint["resource_nodes"] = []
    return scene_intent.SceneIntentBuilder().build(blueprint,
                                                   blueprint.get("resource_nodes") or [])


def legacy_of(intent) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return intent.to_legacy_dict()


def rejects(callable_) -> tuple:
    try:
        callable_()
    except ValueError as exc:
        return True, str(exc)
    except Exception as exc:                                    # noqa: BLE001
        return False, "unexpected %s: %s" % (type(exc).__name__, exc)
    return False, "no exception raised"


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="scene_builder_intent_")
    try:
        templates = template_loader.load_templates(FEATURES)
        features_dir = template_loader.FEATURES_DIR
        binding_path = write_binding(tmp, BINDING_SLIME)

        # ---------------- Case 1: SceneIntent -> builder ----------------
        print("=== Case 1: SceneIntent -> builder ===")
        intent = intent_for(SCENE_BLUEPRINT_PROBE)
        ok("case1: builder accepts a SceneIntent object",
           isinstance(intent, scene_intent.SceneIntent))
        from_object = scene_builder.build_tscn(intent, templates, features_dir)
        ok("case1: generated text is byte-identical to the Phase 1.8.6 baseline",
           from_object == GOLDEN_F1,
           "len=%d vs %d" % (len(from_object), len(GOLDEN_F1)))
        ok("case1: ext_resource ordering preserved",
           [line for line in from_object.splitlines() if line.startswith("[ext_resource")]
           == [line for line in GOLDEN_F1.splitlines() if line.startswith("[ext_resource")])
        ok("case1: node ordering + names preserved",
           [line for line in from_object.splitlines() if line.startswith("[node")]
           == [line for line in GOLDEN_F1.splitlines() if line.startswith("[node")])
        ok("case1: load_steps preserved",
           from_object.splitlines()[0] == GOLDEN_F1.splitlines()[0],
           from_object.splitlines()[0])
        # 契约文档 mapping 是同一份 Scene Intent（不是第二输入形态）
        from_document = scene_builder.build_tscn(intent.to_dict(), templates, features_dir)
        ok("case1: the intent document mapping yields the same text",
           from_document == from_object)
        ok("case1: build_tscn is pure (no files written)",
           [f for f in os.listdir(tmp) if f.endswith(".tscn")] == [])

        # ---------------- Case 2: 兼容性决策（Option A：拒绝 legacy dict） ----------------
        print("=== Case 2: legacy normalized dict is rejected (Option A) ===")
        legacy = legacy_of(intent)
        ok("case2: an internal dict is really what to_legacy_dict() returns",
           isinstance(legacy, dict) and legacy.get("document") is None
           and "root_name" in legacy and "resource_nodes" in legacy, str(sorted(legacy)))
        rejected, message = rejects(lambda: scene_builder.build_tscn(legacy, templates, features_dir))
        ok("case2: build_tscn(legacy dict) raises ValueError", rejected, message)
        ok("case2: rejection message names the new boundary", "rejected" in message,
           message)
        out_dir = os.path.join(tmp, "legacy_out")
        rejected, message = rejects(
            lambda: scene_builder.write_scene(legacy, templates, features_dir, out_dir))
        ok("case2: write_scene(legacy dict) raises ValueError", rejected, message)
        ok("case2: rejected legacy input writes nothing",
           not os.path.isdir(out_dir)
           or [f for f in os.listdir(out_dir) if f.endswith(".tscn")] == [])
        rejected, message = rejects(
            lambda: scene_builder.build_tscn({"document": "scene_blueprint"}, templates, features_dir))
        ok("case2: a look-alike mapping without the intent identity is rejected",
           rejected, message)
        rejected, message = rejects(lambda: scene_builder.build_tscn(None, templates, features_dir))
        ok("case2: non-mapping input is rejected", rejected, message)

        # ---------------- Case 3: resources[] -> ext_resource + node refs ----------------
        print("=== Case 3: resources[] -> ext_resource / node references ===")
        intent3 = intent_for(SCENE_BLUEPRINT_SLIME, binding_path)
        document3 = intent3.to_dict()
        ok("case3: intent carries 2 resources from the Binding",
           len(document3["resources"]) == 2, str([r.get("name") for r in document3["resources"]]))
        text = scene_builder.build_tscn(intent3, templates, features_dir)
        ok("case3: output is byte-identical to the Phase 1.8.6 baseline",
           text == GOLDEN_F3, "len=%d vs %d" % (len(text), len(GOLDEN_F3)))
        ok("case3: .tres resource becomes ext_resource type=SpriteFrames",
           '[ext_resource type="SpriteFrames" path="%s" id="4_asset_SlimeAnim"]' % SLIME_TRES
           in text)
        ok("case3: audio resource becomes ext_resource type=AudioStreamWAV",
           '[ext_resource type="AudioStreamWAV" path="%s" id="5_asset_SlimeHurtSfx"]' % SLIME_WAV
           in text)
        ok("case3: node references the ext_resource via its property",
           'sprite_frames = ExtResource("4_asset_SlimeAnim")' in text
           and 'stream = ExtResource("5_asset_SlimeHurtSfx")' in text)
        ok("case3: default animation is display-only (no playback behaviour)",
           'animation = &"idle"' in text and "play(" not in text)
        ok("case3: ext_resource type is derived by the existing mapping logic",
           all(("type=\"%s\"" % asset_nodes.resource_ext_type(r["path"])) in text
               for r in document3["resources"]))
        ok("case3: load_steps == 1 + ext_resource + sub_resource",
           int(text.split("load_steps=")[1].split(" ")[0])
           == text.count("[ext_resource ") + text.count("[sub_resource ") + 1,
           text.splitlines()[0])
        ok("case3: resources[] in the intent do NOT carry ext_type (contract gap)",
           all("ext_type" not in r for r in document3["resources"]))

        # ---------------- Case 4: provenance / 文档不可变 ----------------
        print("=== Case 4: no provenance mutation, no document pollution ===")
        for entry in BINDING_SLIME["binding"]["bindings"]:
            ok("case4: fixture sanity — binding really carries provenance (%s)" % entry["role"],
               all(k in entry for k in ("resolved_from", "compatibility", "confidence")))
        snapshot = copy.deepcopy(document3)
        legacy_snapshot = copy.deepcopy(legacy_of(intent3))
        text = scene_builder.build_tscn(intent3, templates, features_dir)
        ok("case4: the Scene Intent document is unchanged by generation",
           intent3.document == snapshot,
           str({k: intent3.document[k] for k in intent3.document
                if intent3.document.get(k) != snapshot.get(k)}))
        ok("case4: no builder-internal key leaks into the document (e.g. _sub_id)",
           not any(str(k).startswith("_") for k in intent3.document),
           str(sorted(intent3.document)))
        ok("case4: shape nodes stay clean after generation",
           all(not any(str(k).startswith("_") for k in node)
               for node in intent3.document["nodes"]),
           str(intent3.document["nodes"]))
        for field in scene_intent.PROVENANCE_FIELDS:
            ok("case4: provenance field %r is neither carried nor written" % field,
               field not in text
               and all(field not in r for r in intent3.document["resources"]))
        ok("case4: the deprecated internal view is not mutated by generation",
           legacy_of(intent3) == legacy_snapshot,
           str({k: legacy_of(intent3)[k] for k in legacy_of(intent3)
                if legacy_of(intent3).get(k) != legacy_snapshot.get(k)}))
        ok("case4: generation is deterministic (same input, same text)",
           scene_builder.build_tscn(intent3, templates, features_dir) == text)

        # ---------------- 附：write_scene 落到指定输出目录 ----------------
        print("=== Extra: write_scene output location ===")
        out_dir = os.path.join(tmp, "intent_out")
        path = scene_builder.write_scene(intent, templates, features_dir, out_dir)
        ok("extra: write_scene writes Scenes/<RootName>.tscn into the given dir",
           os.path.basename(path) == "ProbeUnit.tscn" and os.path.isfile(path), path)
        ok("extra: written file matches the generated text",
           open(path, encoding="utf-8", newline="").read() == GOLDEN_F1)
        ok("extra: scene_file_path uses the intent root.name",
           os.path.basename(scene_builder.scene_file_path(intent, os.path.join(tmp, "x")))
           == "ProbeUnit.tscn")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all scene builder intent-input checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
