#!/usr/bin/env python3
"""Scene Composer 回归测试。

任务三用例（均使用临时输出目录或真实 Scenes/ 的隔离场景名）：
    Test 1: entity(role=enemy) + health + contact_damage
            -> 生成 Enemy.tscn，包含 Health + ContactDamage
    Test 2: 只有 contact_damage
            -> 失败：Composition Error / Missing dependency: damage_receiver
    Test 3: health + contact_damage + chase_movement
            -> 生成 EnemyBasic.tscn 且 Validator PASS

用法:
    python .ai/tools/scene_composer/tests/test_scene_composer.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import io
import json
import os
import shutil
import sys
import tempfile

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))            # .ai/tools/scene_composer
TOOLS_DOTAI = os.path.dirname(TOOL_DIR)                                           # .ai/tools
DOTAI = os.path.dirname(TOOLS_DOTAI)                                              # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)
VALIDATOR_DIR = os.path.join(DOTAI, "tools", "validator")

for path in (TOOL_DIR, TOOLS_DOTAI, VALIDATOR_DIR,
             os.path.join(TOOLS_DOTAI, "test_generator")):
    if path not in sys.path:
        sys.path.insert(0, path)

import yaml

import scene_composer
import dependency_resolver
import scene_builder
import scene_validator
import template_loader
import generate_scene_test
import check_scene_composition

FEATURES_DIR = template_loader.FEATURES_DIR
INDEX_PATH = template_loader.INDEX_PATH

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def load_index() -> list:
    with io.open(INDEX_PATH, encoding="utf-8") as f:
        return (json.load(f) or {}).get("features", [])


def parse_tscn_nodes(scene_path: str) -> list:
    text = io.open(scene_path, encoding="utf-8").read()
    import re
    return re.findall(r'^\[node name="([^"]+)"', text, re.M)


def run() -> int:
    index = load_index()

    print("=== Test 1: enemy = health + contact_damage ===")
    bp1 = {
        "entity": {"id": "enemy", "role": "enemy"},
        "features": ["health", "contact_damage"],
        "validation": {"required_tests": ["health", "contact_damage"]},
    }
    out1 = tempfile.mkdtemp(prefix="scene_test1_")
    try:
        result = scene_composer.compose(bp1, out_dir=out1)
        ok("test1: compose ok", result["ok"], str(result["failures"]))
        scene_path = os.path.join(out1, "Enemy.tscn")
        ok("test1: Enemy.tscn generated", os.path.isfile(scene_path), out1)
        if os.path.isfile(scene_path):
            nodes = parse_tscn_nodes(scene_path)
            ok("test1: contains Health node", "Health" in nodes, str(nodes))
            ok("test1: contains ContactDamage node", "ContactDamage" in nodes, str(nodes))
        # 测试生成器可运行且内容含两类断言
        test_path = generate_scene_test.generate_test_file(bp1, out_dir=out1)
        source = io.open(test_path, encoding="utf-8").read()
        ok("test1: generated test asserts scene load", "load(\"res://Scenes/Enemy.tscn\")" in source)
        ok("test1: generated test asserts feature nodes",
           "Missing Feature node: Health" in source and "Missing Feature node: ContactDamage" in source)
        # 独立 Validator 复核
        v = check_scene_composition.check_scene_composition(bp1, scene_path)
        ok("test1: validator PASS", v["failures"] == [], str(v["failures"]))
    finally:
        shutil.rmtree(out1, ignore_errors=True)

    print("=== Test 2: contact_damage without health ===")
    bp2 = {
        "entity": {"id": "broken_enemy", "role": "enemy"},
        "features": ["contact_damage"],
        "validation": {"required_tests": ["contact_damage"]},
    }
    out2 = tempfile.mkdtemp(prefix="scene_test2_")
    try:
        result = scene_composer.compose(bp2, out_dir=out2)
        ok("test2: compose rejected", not result["ok"])
        ok("test2: reports Composition Error (damage_receiver)",
           any("Composition Error" in f and "damage_receiver" in f for f in result["failures"]),
           str(result["failures"]))
        ok("test2: reports Missing dependency",
           any("Missing dependency: damage_receiver" in f for f in result["failures"]),
           str(result["failures"]))
        ok("test2: nothing written", not os.path.isfile(os.path.join(out2, "BrokenEnemy.tscn")))
    finally:
        shutil.rmtree(out2, ignore_errors=True)

    print("=== Test 3: full EnemyBasic = health + contact_damage + chase_movement ===")
    bp3 = {
        "entity": {"id": "enemy_basic", "role": "enemy"},
        "features": ["health", "contact_damage", "chase_movement"],
        "validation": {"required_tests": ["health", "contact_damage", "chase_movement"]},
    }
    out3 = tempfile.mkdtemp(prefix="scene_test3_")
    try:
        result = scene_composer.compose(bp3, out_dir=out3)
        ok("test3: compose ok", result["ok"], str(result["failures"]))
        scene_path = os.path.join(out3, "EnemyBasic.tscn")
        ok("test3: EnemyBasic.tscn generated", os.path.isfile(scene_path))
        if os.path.isfile(scene_path):
            # 根类型推导：chase_movement 要求 CharacterBody2D
            text = io.open(scene_path, encoding="utf-8").read()
            ok("test3: root is CharacterBody2D", '[node name="EnemyBasic" type="CharacterBody2D"]' in text)
            ok("test3: root has no script (Scene 只负责组合)",
               '[node name="EnemyBasic" type="CharacterBody2D"]\nscript' not in text)
            nodes = parse_tscn_nodes(scene_path)
            ok("test3: contains Health/ContactDamage/ChaseMovement",
               all(n in nodes for n in ("Health", "ContactDamage", "ChaseMovement")), str(nodes))
            # .tscn 头部 load_steps 与 ext_resource 数一致
            ext_count = text.count("[ext_resource ")
            declared = int(text.split("load_steps=")[1].split(" ")[0])
            ok("test3: load_steps consistent", declared == ext_count + 1, "declared=%d ext=%d" % (declared, ext_count))
        # Validator PASS（结构 + 依赖 + 根类型）
        v = check_scene_composition.check_scene_composition(bp3, scene_path)
        ok("test3: validator PASS", v["failures"] == [], str(v["failures"]))
        # 测试生成：含信号断言（health: health_changed/died）
        test_path = generate_scene_test.generate_test_file(bp3, out_dir=out3)
        source = io.open(test_path, encoding="utf-8").read()
        ok("test3: generated test asserts signals",
           "Missing signal: Health.health_changed" in source and "Missing signal: Health.died" in source)
    finally:
        shutil.rmtree(out3, ignore_errors=True)

    print("=== Extras: templates / resolver / builder units ===")
    # 12 个 Feature 均有 template.yaml 且 source 存在
    feature_ids = sorted(d for d in os.listdir(FEATURES_DIR)
                         if os.path.isdir(os.path.join(FEATURES_DIR, d)))
    for fid in feature_ids:
        template = template_loader.load_template(fid)
        ok("template: %s exists" % fid, bool(template))
        if template:
            scene_rel = ((template.get("scene") or {}).get("source") or "").replace("\\", "/")
            ok("template: %s source exists" % fid,
               os.path.isfile(os.path.join(FEATURES_DIR, fid, scene_rel)), scene_rel)

    # resolver：完整组合 ok，残缺组合报错
    ok("resolver: full composition ok",
       dependency_resolver.resolve(["health", "contact_damage", "chase_movement"], index)["ok"])
    ok("resolver: stun-only reports missing health_state",
       any("health_state" in m for m in dependency_resolver.resolve(["stun"], index)["missing"]))

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for f in _failures:
            print("  - " + f)
        return 1
    print("PASS: all scene composer checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
