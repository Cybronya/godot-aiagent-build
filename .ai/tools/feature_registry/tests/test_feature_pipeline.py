#!/usr/bin/env python3
"""Feature Metadata Pipeline 回归测试。

覆盖任务要求的三类验证：
    Test 1: Index Generation —— 据 feature.yaml 生成 feature_index.json 并验证条目
    Test 2: Discovery Query  —— "enemy receives damage" 应命中 health
    Test 3: Validator        —— 删除 feature.yaml 后 Validator 必须报 Error

不触碰真实项目文件：使用临时目录构造 fixture，测试真实工具模块导入后的行为；
对与项目状态相关的检查项（如 Test 3 的存在性检查）使用隔离的伪造 Features 目录。
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

用法:
    python .ai/tools/feature_registry/tests/test_feature_pipeline.py
"""

import io
import json
import os
import shutil
import sys
import tempfile

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # .ai/tools/feature_registry
TOOLS_DOTAI = os.path.dirname(TOOL_DIR)                                          # .ai/tools
DOTAI = os.path.dirname(TOOLS_DOTAI)                                             # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)
VALIDATOR_DIR = os.path.join(DOTAI, "tools", "validator")

if VALIDATOR_DIR not in sys.path:
    sys.path.insert(0, VALIDATOR_DIR)
if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

import build_feature_index as builder
import discover_feature as discovery
import check_feature_metadata as metadata_validator

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def write(path: str, content: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    io.open(path, "w", encoding="utf-8", newline="\n").write(content)


# 一个最小合法 fixture（Test 1/3 共用）
HEALTH_META = """\
id: health
version: 1
category: component
summary: minimal fixture
provides: [health_state, damage_receiver, death_event]
requires: []
interfaces:
  methods:
    - {name: take_damage, signature: "take_damage(amount: int) -> void"}
  signals:
    - {name: died, signature: died}
  exports: []
ownership: {state: [hp], rules: []}
composition: {entry_scene: Health.tscn, usage: reuse}
validation:
  self_test: test_health.gd
  command: "godot --headless"
"""
HEALTH_TEST_STUB = "extends SceneTree\n"

# Test 2 使用的最小 player_movement fixture
PLAYER_META = """\
id: player_movement
version: 1
category: behavior
summary: fixture
provides: [character_movement, player_control]
requires: []
interfaces:
  methods: []
  signals: []
  exports: []
ownership: {state: [], rules: []}
composition: {entry_scene: Player.tscn, usage: reuse}
validation:
  self_test: test_player_movement.gd
"""


def make_fixtures(root: str, include_player: bool = False) -> dict:
    """在 root 下构造伪项目：<root>/Features + <root>/.ai/context，返回路径。"""
    features_dir = os.path.join(root, "Features")
    health_dir = os.path.join(features_dir, "health")
    os.makedirs(health_dir)
    write(os.path.join(health_dir, "feature.yaml"), HEALTH_META)
    write(os.path.join(health_dir, "test_health.gd"), HEALTH_TEST_STUB)
    if include_player:
        player_dir = os.path.join(features_dir, "player_movement")
        os.makedirs(player_dir)
        write(os.path.join(player_dir, "feature.yaml"), PLAYER_META)
        write(os.path.join(player_dir, "test_player_movement.gd"), HEALTH_TEST_STUB)
    index_path = os.path.join(root, ".ai", "context", "feature_index.json")
    return {"features_dir": features_dir, "index_path": index_path, "root": root}


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="feature_pipeline_test_")
    print("=== Test 1: Index Generation ===")
    fx = make_fixtures(tmp, include_player=True)
    out = os.path.join(fx["root"], "out", "feature_index.json")
    records, errors = builder.build_index(fx["features_dir"])
    ok("index generation: no build errors", errors == [], str(errors))
    ok("index generation: health recorded", any(r["id"] == "health" for r in records))
    builder.write_index(records, out)
    data = json.load(io.open(out, encoding="utf-8"))
    # 同步写一份到 fixture 的 .ai/context 位置，供后续 Validator Test 3 使用
    builder.write_index(records, fx["index_path"])
    health = next((f for f in data["features"] if f["id"] == "health"), None)
    ok("index generation: health exists in output json", health is not None)
    if health:
        ok("index generation: provides parsed",
           set(health["provides"]) == {"health_state", "damage_receiver", "death_event"},
           str(health["provides"]))
        ok("index generation: interfaces parsed", "take_damage" in health["interfaces"])
        ok("index generation: test_path resolved",
           health["validation"]["test_path"].endswith("Features/health/test_health.gd"),
           health["validation"]["test_path"])
        ok("index generation: generated_at present", bool(data.get("generated_at")))
        ok("index generation: registry_version", data.get("registry_version") == 2,
           str(data.get("registry_version")))

    print("=== Test 2: Discovery Query ===")
    terms = discovery.extract_terms("enemy receives damage")
    ok("discovery: synonym expansion hits damage_receiver", "damage_receiver" in terms, str(sorted(terms)))
    result = discovery.discover("enemy receives damage", data["features"])
    ids = [r["feature"]["id"] for r in result]
    ok("discovery: 'enemy receives damage' returns health", "health" in ids, str(ids))
    ok("discovery: 'player movement' returns player_movement",
       "player_movement" in [r["feature"]["id"] for r in discovery.discover("player movement control", data["features"])])
    if result:
        ok("discovery: results sorted by score desc",
           result[0]["score"] >= result[-1]["score"], str([r["score"] for r in result]))
        top = result[0]
        ok("discovery: reasons reference provides",
           any(r.startswith("provides: ") for r in top["reasons"]), str(top["reasons"]))

    print("=== Test 2b: Discovery reads real project index ===")
    real_index = os.path.join(DOTAI, "context", "feature_index.json")
    if os.path.isfile(real_index):
        real = json.load(io.open(real_index, encoding="utf-8"))
        result = discovery.discover("enemy can receive damage", real["features"])
        ids = [r["feature"]["id"] for r in result]
        ok("discovery(real index): health and contact_damage matched",
           "health" in ids and "contact_damage" in ids, str(ids))
    else:
        ok("discovery(real index): index file exists", False, real_index)

    print("=== Test 3: Validator (missing metadata -> Error) ===")
    result = metadata_validator.check_features(fx["root"], fx["index_path"])
    os.remove(os.path.join(fx["features_dir"], "health", "feature.yaml"))
    result = metadata_validator.check_features(fx["root"], fx["index_path"])
    expectation("validator(missing metadata): reports error",
                any("Feature missing metadata" in f for f in result["failures"]),
                str(result["failures"]))
    expectation("validator(missing metadata): index stale entry warned",
                any("stale entry" in w and "health" in w for w in result["warnings"]),
                str(result["warnings"]))

    print("=== Test 3b: Validator (id mismatch / missing field / stale index) ===")
    bad = tempfile.mkdtemp(prefix="feature_pipeline_bad_")
    fxb = make_fixtures(bad)
    # id mismatch
    write(os.path.join(fxb["features_dir"], "teleport", "feature.yaml"),
          HEALTH_META.replace("id: health", "id: HealthSystem"))
    result = metadata_validator.check_features(fxb["root"], fx["index_path"])
    expectation("validator(id mismatch): reports mismatch",
                any("Feature id mismatch" in f and "folder=teleport" in f for f in result["failures"]),
                str(result["failures"]))
    # missing required field (Validation)
    write(os.path.join(fxb["features_dir"], "novalidation", "feature.yaml"),
          HEALTH_META.replace("validation:\n  self_test: test_health.gd\n  command: \"godot --headless\"\n", ""))
    result = metadata_validator.check_features(fxb["root"], fx["index_path"])
    expectation("validator(missing field): reports missing required field(s)",
                any("missing required field" in f and "novalidation" in f for f in result["failures"]),
                str(result["failures"]))
    # stale index version
    stale = json.load(io.open(fx["index_path"], encoding="utf-8"))
    stale["features"][0]["version"] = "99"
    stale_index = os.path.join(bad, ".ai", "context", "feature_index.json")
    write(stale_index, json.dumps(stale, ensure_ascii=False, indent=2))
    # 恢复合法 health metadata 后，索引版本过期应报 outdated
    write(os.path.join(fxb["features_dir"], "health", "feature.yaml"), HEALTH_META)
    write(os.path.join(fxb["features_dir"], "health", "test_health.gd"), HEALTH_TEST_STUB)
    result = metadata_validator.check_features(bad, stale_index)
    expectation("validator(stale index): reports outdated version",
                any("Feature index outdated" in f and "health" in f for f in result["failures"]),
                str(result["failures"]))
    # test path missing
    os.remove(os.path.join(fxb["features_dir"], "health", "test_health.gd"))
    fresh = os.path.join(bad, ".ai", "context2", "feature_index.json")
    records, _ = builder.build_index(fxb["features_dir"])
    builder.write_index(records, fresh)
    result = metadata_validator.check_features(bad, fresh)
    expectation("validator(missing test file): reports test not found",
                any("test not found" in f and "health" in f for f in result["failures"]),
                str(result["failures"]))

    print("=== Test 3c: Real project check ===")
    real = metadata_validator.check_features(PROJECT_ROOT, os.path.join(DOTAI, "context", "feature_index.json"))
    ok("validator(real project): no failures", real["failures"] == [], str(real["failures"]))
    ok("validator(real project): checked 12 features", real["checked"] == 12, str(real["checked"]))

    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(bad, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for f in _failures:
            print("  - " + f)
        return 1
    print("PASS: all feature pipeline checks passed")
    return 0


def expectation(name, condition, detail):
    ok(name, condition, detail)



if __name__ == "__main__":
    sys.exit(run())
