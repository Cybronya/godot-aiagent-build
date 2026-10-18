#!/usr/bin/env python3
"""Entity Root Instance 契约测试（Phase 1.11）

被测契约：Feature Scene Template 的 `attach.root_instance` / `attach.nodes`
→ Entity Blueprint 推导 → .tscn 结构 → 静态校验 → 生成的回归测试断言。

    Case 1  根实例推导：成员声明 attach.root_instance: true 时，实体根**就是**该
            Feature 的入口场景实例，而不是裸类型节点 + 该组件作为子节点
            （后者会让根脚本只移动子节点：实体根本地不动、接触范围不跟着实体走）
    Case 2  组件自带结构节点：attach.nodes → nodes[]（ContactShape / Collision），
            作者显式声明的同名节点优先，绝不产出重名节点
    Case 3  冲突诊断：多个成员同时声明 root_instance → 拒绝生成（零产物）+ 可诊断文案
    Case 4  静态闸门：旧结构（裸根 + 追击子节点）用同一 Blueprint 校验必须失败
    Case 5  输入边界：显式 Scene Blueprint（作者自己写 root:/components:）不被推导改写

本测试只读项目、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_entity_root_instance.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import json
import os
import shutil
import sys
import tempfile

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

import scene_builder                                         # noqa: E402
import scene_composer                                        # noqa: E402
import scene_validator                                       # noqa: E402
import template_loader                                       # noqa: E402
import check_scene_composition                               # noqa: E402
import generate_scene_test                                   # noqa: E402

CHASE_SCENE = "res://Features/chase_movement/ChaseMovement.tscn"

ENEMY_BLUEPRINT = {
    "entity": {"id": "enemy_root_probe", "role": "enemy"},
    "features": ["health", "contact_damage", "chase_movement"],
    "validation": {"required_tests": ["health", "contact_damage", "chase_movement"]},
}

# 旧结构（Phase 1.11 之前由同一 Blueprint 生成的结果）：裸类型根 + 追击组件作为子节点
LEGACY_SCENE = """[gd_scene load_steps=4 format=3]

[ext_resource type="PackedScene" path="res://Features/health/Health.tscn" id="1_health"]
[ext_resource type="PackedScene" path="res://Features/contact_damage/ContactDamage.tscn" id="2_contact_damage"]
[ext_resource type="PackedScene" path="res://Features/chase_movement/ChaseMovement.tscn" id="3_chase_movement"]

[node name="EnemyRootProbe" type="CharacterBody2D"]

[node name="Health" parent="." instance=ExtResource("1_health")]

[node name="ContactDamage" parent="." instance=ExtResource("2_contact_damage")]

[node name="ChaseMovement" parent="." instance=ExtResource("3_chase_movement")]
"""

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def write(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def cases() -> None:
    tmp = tempfile.mkdtemp(prefix="entity_root_instance_")
    try:
        templates = template_loader.load_templates(ENEMY_BLUEPRINT["features"])

        # ---------------- Case 1: 根实例推导 ----------------
        print("=== Case 1: attach.root_instance -> entity root is the Feature entry scene ===")
        derived = template_loader.derive_scene_blueprint(ENEMY_BLUEPRINT)
        root = derived.get("root") or {}
        ok("case1: chase_movement's entry scene becomes the entity root scene",
           root.get("scene") == CHASE_SCENE, repr(root))
        ok("case1: the member's declared root type is kept (validator still checks it)",
           root.get("type") == "CharacterBody2D", repr(root))
        ok("case1: the root keeps the scene id based name (output file name unchanged)",
           root.get("name") == "EnemyRootProbe", repr(root))

        out_dir = os.path.join(tmp, "scenes")
        result = scene_composer.compose(ENEMY_BLUEPRINT, out_dir=out_dir)
        ok("case1: compose ok", result["ok"], str(result["failures"]))
        scene_path = os.path.join(out_dir, "EnemyRootProbe.tscn")
        text = open(scene_path, encoding="utf-8").read() if os.path.isfile(scene_path) else ""
        ok("case1: the generated root is an instance of the chase Feature scene",
           '[node name="EnemyRootProbe" instance=ExtResource("1_root_scene")]' in text
           and 'path="%s" id="1_root_scene"' % CHASE_SCENE in text, text[:200])
        ok("case1: the root instance component is not duplicated as a child node",
           '[node name="ChaseMovement" parent="." instance=' not in text, text[:400])
        ok("case1: other components are still instantiated as children",
           '[node name="Health" parent="." instance=' in text
           and '[node name="ContactDamage" parent="." instance=' in text)
        ok("case1: the root instance scene root type is resolved, not guessed",
           scene_validator._root_node_type(scene_validator.resolve_res_path(CHASE_SCENE))
           == "CharacterBody2D")

        validation = check_scene_composition.check_scene_composition(ENEMY_BLUEPRINT, scene_path)
        ok("case1: independent validation PASS", validation["failures"] == [],
           str(validation["failures"]))

        # 生成的运行期回归测试对根实例组件断言**根节点类型**，而不是子节点名（后者会假失败）
        test_path = generate_scene_test.generate_test_file(result["scene_intent"],
                                                           out_dir=os.path.join(tmp, "tests"))
        source = open(test_path, encoding="utf-8").read()
        ok("case1: the generated test asserts the entity root type for the root instance component",
           "if not (entity is CharacterBody2D):" in source
           and "Missing Feature root: chase_movement" in source
           and 'entity.get_node_or_null("ChaseMovement")' not in source, source)
        ok("case1: the generated test still asserts the child component nodes",
           'entity.get_node_or_null("Health")' in source
           and 'entity.get_node_or_null("ContactDamage")' in source)

        # ---------------- Case 2: attach.nodes -> nodes[] ----------------
        print("=== Case 2: attach.nodes -> structural nodes (collision shapes) ===")
        nodes = derived.get("nodes") or []
        by_name = {node.get("name"): node for node in nodes}
        ok("case2: contact_damage's contact shape is declared under its own node",
           by_name.get("ContactShape", {}).get("parent") == "ContactDamage", repr(nodes))
        ok("case2: contact shape geometry comes from the Feature template",
           (by_name.get("ContactShape", {}).get("shape") or {}).get("size") == [36, 36],
           repr(by_name.get("ContactShape")))
        ok("case2: the root instance component's body shape is declared under the entity root",
           by_name.get("Collision", {}).get("parent") == ".", repr(nodes))
        ok("case2: body shape geometry comes from the Feature template",
           (by_name.get("Collision", {}).get("shape") or {}).get("size") == [28, 28],
           repr(by_name.get("Collision")))
        ok("case2: shapes are materialized in the .tscn text",
           'name="ContactShape" type="CollisionShape2D" parent="ContactDamage"' in text
           and 'name="Collision" type="CollisionShape2D" parent="."' in text)
        ok("case2: no duplicate node name under the same parent",
           len({(node.get("parent"), node.get("name")) for node in nodes}) == len(nodes),
           repr([(n.get("parent"), n.get("name")) for n in nodes]))

        # 作者显式声明的同名节点优先：同一挂载点 (parent, name) 只产出一次，几何用作者的
        override_bp = dict(ENEMY_BLUEPRINT)
        override_bp["nodes"] = [{"type": "CollisionShape2D", "name": "ContactShape",
                                 "parent": "ContactDamage",
                                 "shape": {"type": "circle", "radius": 48}}]
        override = template_loader.derive_scene_blueprint(override_bp)
        contact_shapes = [n for n in override.get("nodes") or [] if n.get("name") == "ContactShape"]
        ok("case2: an author-declared node wins over the template default",
           len(contact_shapes) == 1
           and (contact_shapes[0].get("shape") or {}).get("type") == "circle",
           repr(override.get("nodes")))

        # ---------------- Case 3: 冲突诊断（多个 root_instance） ----------------
        print("=== Case 3: multiple root_instance members are rejected, not guessed ===")
        features_dir = os.path.join(tmp, "Features")
        feature_index = []
        for fid in ("alpha_root", "beta_root"):
            write(os.path.join(features_dir, fid, "template.yaml"),
                  "feature:\n  id: %s\nscene:\n  source: %s.tscn\n  root_type: CharacterBody2D\n"
                  "attach:\n  parent: root\n  root_instance: true\n"
                  "validation:\n  required_nodes:\n    - %s\n"
                  % (fid, template_loader.pascal_case(fid), template_loader.pascal_case(fid)))
            write(os.path.join(features_dir, fid, "%s.tscn" % template_loader.pascal_case(fid)),
                  '[gd_scene load_steps=1 format=3]\n\n[node name="%s" type="CharacterBody2D"]\n'
                  % template_loader.pascal_case(fid))
            feature_index.append({"id": fid, "provides": [], "requires": [], "relations": {}})
        index_path = write(os.path.join(tmp, "feature_index.json"),
                           json.dumps({"features": feature_index}, ensure_ascii=False))
        conflict_out = os.path.join(tmp, "conflict_out")
        conflict = scene_composer.compose(
            {"entity": {"id": "conflict_probe", "role": "enemy"},
             "features": ["alpha_root", "beta_root"], "validation": {"required_tests": []}},
            out_dir=conflict_out, features_dir=features_dir, index_path=index_path)
        ok("case3: compose refuses to guess the entity root",
           not conflict["ok"]
           and any("Root instance conflict" in f and "alpha_root" in f and "beta_root" in f
                   for f in conflict["failures"]),
           str(conflict["failures"]))
        ok("case3: the refusal writes nothing",
           not os.path.isfile(os.path.join(conflict_out, "ConflictProbe.tscn")),
           conflict_out)

        # ---------------- Case 4: 静态闸门（旧结构必须被拒） ----------------
        print("=== Case 4: structural defects are rejected statically ===")
        # 4a：旧结构（裸类型根 + 追击子节点）—— 计划声明的实体根实例不存在
        legacy_path = write(os.path.join(tmp, "legacy", "EnemyRootProbe.tscn"), LEGACY_SCENE)
        legacy = check_scene_composition.check_scene_composition(ENEMY_BLUEPRINT, legacy_path)
        ok("case4a: a bare typed root (the pre-1.11 structure) is rejected",
           any("Missing Feature root: chase_movement" in f and "<typed root node>" in f
               for f in legacy["failures"]),
           str(legacy["failures"]))
        # 4b：根已是该组件的实例，但同时又多出一个同名行为子节点（双重实例化）
        duplicate_text = text.replace(
            "[sub_resource",
            '[ext_resource type="PackedScene" path="%s" id="9_chase_child"]\n\n[sub_resource'
            % CHASE_SCENE, 1)
        duplicate_text += ('\n[node name="ChaseMovement" parent="." '
                           'instance=ExtResource("9_chase_child")]\n')
        duplicate_path = write(os.path.join(tmp, "legacy", "DuplicateProbe.tscn"), duplicate_text)
        duplicate = check_scene_composition.check_scene_composition(ENEMY_BLUEPRINT, duplicate_path)
        ok("case4b: a duplicated root-instance child is rejected",
           any("must not also be instantiated as a child node ChaseMovement" in f
               for f in duplicate["failures"]),
           str(duplicate["failures"]))
        ok("case4c: the correct scene keeps passing the same blueprint",
           legacy["failures"] and duplicate["failures"]
           and check_scene_composition.check_scene_composition(
               ENEMY_BLUEPRINT, scene_path)["failures"] == [],
           str(legacy["failures"]))

        # ---------------- Case 5: 显式 Scene Blueprint 不被推导改写 ----------------
        print("=== Case 5: an explicit Scene Blueprint keeps the author's instantiation plan ===")
        explicit = {
            "scene": {"id": "explicit_probe"},
            "root": {"type": "CharacterBody2D", "name": "ExplicitProbe"},
            "components": [{"feature": "health"}, {"feature": "chase_movement"}],
            "validation": {"required_tests": ["health", "chase_movement"]},
        }
        passthrough = template_loader.derive_scene_blueprint(explicit)
        ok("case5: derive returns the author's plan untouched",
           passthrough is explicit or passthrough == explicit, repr(passthrough))
        ok("case5: no root instance is invented for an explicit plan",
           (passthrough.get("root") or {}).get("scene") is None
           and "nodes" not in passthrough, repr(passthrough.get("root")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run() -> int:
    cases()
    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all entity root instance checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
