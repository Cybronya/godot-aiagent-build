#!/usr/bin/env python3
"""Scene Validator 的 Scene Intent 输入边界测试（Phase 1.8.8）

    Case 1  Intent 输入通过 —— validate_scene(SceneIntent) 与文档 mapping 结果一致，
            且与 check_scene_composition(raw blueprint) 入口结果一致
    Case 2  旧规整内部 dict 被拒绝（validate_scene / generate_test_file / build_test_source）
    Case 3  Intent nodes —— 节点类规则仍在（坏 parent / 重名），且不依赖 nodes[]
    Case 4  Intent resources —— 带资源的意图校验通过，且不依赖 resources[]
    Case 5  回退扫描 —— 三个已迁移消费者源码里不再出现内部 dict 读取（blueprint[）

验证规则本阶段**未改**：Case 1/3/4 的失败文案与 Phase 1.8.7 基线（迁移前
validate_scene 对同一批 .tscn 的输出）逐字相同。

本测试只读项目、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_scene_validator_intent_input.py
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

for path in (TOOL_DIR, TOOLS_DIR, VALIDATOR_DIR, TEST_GEN_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import asset_nodes                                             # noqa: E402
import check_scene_composition                                 # noqa: E402
import generate_scene_test                                     # noqa: E402
import scene_builder                                           # noqa: E402
import scene_intent                                            # noqa: E402
import scene_validator                                         # noqa: E402
import template_loader                                         # noqa: E402

FEATURES = ["health", "contact_damage", "chase_movement"]
SLIME_TRES = "res://Assets/characters/enemy/slime/slime_frames.tres"
SLIME_WAV = "res://Assets/audio/slime/hurt.wav"

BLUEPRINT = {
    "scene": {"id": "slime_enemy"},
    "root": {"type": "CharacterBody2D", "name": "SlimeEnemy", "groups": ["enemies"],
             "properties": {"motion_mode": 1}},
    "components": [{"feature": f} for f in FEATURES],
    "nodes": [{"type": "CollisionShape2D", "name": "SlimeShape",
               "shape": {"type": "circle", "radius": 10}}],
    "validation": {"required_tests": FEATURES},
}

BINDING = {
    "schema_version": 2,
    "binding": {
        "entity": "slime_enemy", "role": "enemy", "subject": "slime",
        "features": FEATURES,
        "bindings": [
            {"role": "idle", "asset": "slime_frames", "path": SLIME_TRES, "type": "sprite_frames",
             "node": {"name": "SlimeAnim", "type": "AnimatedSprite2D",
                      "property": "sprite_frames", "path": SLIME_TRES,
                      "roles": ["idle", "move", "attack", "hurt"], "animation": "idle"},
             "resolved_from": "index", "compatibility": "COMPATIBLE", "confidence": "high"},
            {"role": "hurt_sfx", "asset": "slime_hurt_sfx", "path": SLIME_WAV, "type": "audio",
             "node": {"name": "SlimeHurtSfx", "type": "AudioStreamPlayer",
                      "property": "stream", "path": SLIME_WAV, "roles": ["hurt_sfx"]},
             "resolved_from": "index", "compatibility": "COMPATIBLE", "confidence": "high"},
        ],
        "missing": [], "optional_missing": [],
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


def compatible_legacy(intent) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return intent.to_legacy_dict()


def rejected(fn) -> bool:
    try:
        fn()
    except ValueError:
        return True
    return False


def write_scene(tmp: str, name: str, text: str) -> str:
    path = os.path.join(tmp, name + ".tscn")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="scene_validator_intent_")
    try:
        index = json.load(open(os.path.join(DOTAI, "context", "feature_index.json"),
                               encoding="utf-8")).get("features", [])
        features_dir = template_loader.FEATURES_DIR
        templates = template_loader.load_templates(FEATURES)

        # 真实链路：Blueprint -> 规整 -> Binding 资源节点 -> Scene Intent
        blueprint, errors = template_loader.normalize_scene_blueprint(
            template_loader.derive_scene_blueprint(copy.deepcopy(BLUEPRINT)))
        ok("setup: blueprint normalizes", not errors, str(errors))
        blueprint["resource_nodes"], _info = asset_nodes.nodes_for_blueprint(
            BLUEPRINT, bindings_path=write_binding(tmp, BINDING))
        intent = scene_intent.SceneIntentBuilder().build(blueprint, blueprint["resource_nodes"])
        text = scene_builder.build_tscn(intent, templates, features_dir)
        good_path = write_scene(tmp, "good", text)

        # ---------------- Case 1: Intent 输入通过 ----------------
        print("=== Case 1: intent input passes validation ===")
        result = scene_validator.validate_scene(intent, good_path, index, templates, features_dir)
        ok("case1: SceneIntent object accepted and PASS", result["ok"] and result["failures"] == [],
           str(result["failures"]))
        as_document = scene_validator.validate_scene(intent.to_dict(), good_path, index,
                                                     templates, features_dir)
        ok("case1: contract document mapping yields the same verdict",
           as_document == result, str(as_document))
        from_cli_entry = check_scene_composition.check_scene_composition(copy.deepcopy(BLUEPRINT),
                                                                        good_path)
        ok("case1: check_scene_composition(raw blueprint) agrees",
           from_cli_entry["failures"] == [] and from_cli_entry["checked"] == 1,
           str(from_cli_entry))
        test_path = generate_scene_test.generate_test_file(intent, out_dir=tmp,
                                                           features_dir=features_dir)
        source = open(test_path, encoding="utf-8", newline="").read()
        ok("case1: test generator consumes the same intent",
           'load("res://Scenes/SlimeEnemy.tscn")' in source
           and "Missing Feature node: Health" in source,
           os.path.basename(test_path))

        # ---------------- Case 2: 旧内部 dict 被拒绝 ----------------
        print("=== Case 2: legacy internal dict is rejected ===")
        legacy = compatible_legacy(intent)
        ok("case2: fixture really is the legacy internal form",
           "root_name" in legacy and "extra_nodes" in legacy and "scene_id" in legacy,
           str(sorted(legacy)))
        ok("case2: validate_scene(legacy dict) raises ValueError",
           rejected(lambda: scene_validator.validate_scene(legacy, good_path, index, templates,
                                                           features_dir)))
        ok("case2: validate_scene(partial legacy dict) raises ValueError",
           rejected(lambda: scene_validator.validate_scene({"features": FEATURES}, good_path,
                                                           index, templates, features_dir)))
        before = sorted(os.listdir(tmp))
        ok("case2: generate_test_file(legacy dict) raises ValueError",
           rejected(lambda: generate_scene_test.generate_test_file(legacy, out_dir=tmp)))
        ok("case2: build_test_source(legacy dict) raises ValueError",
           rejected(lambda: generate_scene_test.build_test_source(legacy, templates,
                                                                 "Scenes/SlimeEnemy.tscn")))
        ok("case2: nothing is written for the rejected legacy input",
           sorted(os.listdir(tmp)) == before,
           "%s vs %s" % (sorted(os.listdir(tmp)), before))

        # ---------------- Case 3: nodes / 节点类规则 ----------------
        print("=== Case 3: node rules still run (and do not read nodes[]) ===")
        bad_parent = write_scene(tmp, "bad_parent", text
                                 + '\n[node name="GhostChild" type="Node2D" parent="Ghost"]\n')
        bad_parent_result = scene_validator.validate_scene(intent, bad_parent, index, templates,
                                                           features_dir)
        ok("case3: undeclared parent path is still a Composition Error",
           bad_parent_result["failures"] == [
               "Composition Error: node GhostChild parent path 'Ghost' references a node not "
               "declared in this scene"],
           str(bad_parent_result["failures"]))
        duplicate = write_scene(tmp, "duplicate", text
                                + '\n[node name="Health" type="Node2D" parent="."]\n')
        duplicate_result = scene_validator.validate_scene(intent, duplicate, index, templates,
                                                          features_dir)
        ok("case3: duplicate node name is still a Composition Error",
           duplicate_result["failures"] == [
               "Composition Error: duplicate node name 'Health' under parent '.'"],
           str(duplicate_result["failures"]))
        missing = write_scene(tmp, "missing", text.replace(
            '[node name="Health" parent="." instance=ExtResource("1_health")]\n\n', ""))
        missing_result = scene_validator.validate_scene(intent, missing, index, templates,
                                                        features_dir)
        ok("case3: missing feature node message unchanged",
           "Missing Feature: health (node Health)" in missing_result["failures"],
           str(missing_result["failures"]))
        wrong_root = write_scene(tmp, "wrong_root",
                                 text.replace('type="CharacterBody2D"', 'type="Node2D"', 1))
        wrong_root_result = scene_validator.validate_scene(intent, wrong_root, index, templates,
                                                           features_dir)
        ok("case3: invalid root type message unchanged",
           "Invalid Root Node Type: expected CharacterBody2D, got Node2D"
           in wrong_root_result["failures"], str(wrong_root_result["failures"]))
        # nodes[] 不参与校验：同一 .tscn + 去掉 nodes 的意图 -> 同一结论
        stripped = intent.to_dict()
        stripped["nodes"] = []
        ok("case3: nodes[] is not consumed by the validator",
           scene_validator.validate_scene(stripped, bad_parent, index, templates, features_dir)
           == bad_parent_result)

        # ---------------- Case 4: resources / 资源不参与校验 ----------------
        print("=== Case 4: resources are carried but not re-decided ===")
        ok("case4: intent carries the two binding resources",
           [r["name"] for r in intent.document["resources"]] == ["SlimeAnim", "SlimeHurtSfx"],
           str([r.get("name") for r in intent.document["resources"]]))
        ok("case4: resource ext_resources are present in the generated scene",
           'type="SpriteFrames"' in text and 'type="AudioStreamWAV"' in text)
        ok("case4: scene with resources validates PASS",
           scene_validator.validate_scene(intent, good_path, index, templates,
                                          features_dir)["ok"])
        stripped_resources = intent.to_dict()
        stripped_resources["resources"] = []
        ok("case4: resources[] is not consumed by the validator",
           scene_validator.validate_scene(stripped_resources, good_path, index, templates,
                                          features_dir)
           == scene_validator.validate_scene(intent, good_path, index, templates, features_dir))
        resource_result = scene_validator.validate_scene(intent, good_path, index, templates,
                                                        features_dir)
        for field in scene_intent.PROVENANCE_FIELDS:
            ok("case4: validation output never surfaces provenance %r" % field,
               field not in json.dumps(resource_result, ensure_ascii=False))

        # ---------------- Case 5: 回退扫描 ----------------
        print("=== Case 5: no legacy dict reads left in migrated consumers ===")
        # scene_validator 仍会下标自己解析出的 .tscn 映射（scene["root_type"]），
        # 因此这里扫的是「规整内部 dict」本身：只允许出现 blueprint 级别的读取。
        sources = {
            "scene_validator.py": (os.path.join(TOOL_DIR, "scene_validator.py"),
                                   ("extra_nodes", "resource_nodes", "scene_id", "required_tests")),
            "generate_scene_test.py": (os.path.join(TEST_GEN_DIR, "generate_scene_test.py"),
                                       ("extra_nodes", "resource_nodes", "scene_id",
                                        "root_name", "root_type", "required_tests")),
            "check_scene_composition.py": (os.path.join(VALIDATOR_DIR,
                                                        "check_scene_composition.py"),
                                           ("extra_nodes", "resource_nodes", "scene_id",
                                            "root_name", "root_type", "required_tests")),
        }
        for name, (path, owned_keys) in sources.items():
            source = open(path, encoding="utf-8").read()
            ok("case5: %s never reads the normalized dict ('blueprint[...]')" % name,
               "blueprint[" not in source and "blueprint.get(" not in source)
            for key in owned_keys:
                ok("case5: %s never subscripts internal key %r" % (name, key),
                   '["%s"]' % key not in source)
        validator_source = open(sources["scene_validator.py"][0], encoding="utf-8").read()
        ok("case5: validate_scene's first parameter is the Scene Intent",
           "def validate_scene(scene_intent" in validator_source)
        generator_source = open(sources["generate_scene_test.py"][0], encoding="utf-8").read()
        ok("case5: generate_test_file's first parameter is the Scene Intent",
           "def generate_test_file(scene_intent" in generator_source)
        ok("case5: test generator keeps a single raw-blueprint entry point",
           generator_source.count("def intent_from_blueprint") == 0
           and "intent_from_blueprint(blueprint_raw)" in generator_source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all scene validator intent-input checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
