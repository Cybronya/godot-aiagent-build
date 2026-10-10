#!/usr/bin/env python3
"""Feature Composition 回归测试。

覆盖任务要求的三类用例，以及关系图生成与 Validator 组合检查：
    Case 1: "enemy attacks player"            -> health + contact_damage
    Case 2: "enemy chases player"             -> chase_movement
    Case 3: "enemy boss can be stunned"       -> health + stun (+ chase_movement)

用法:
    python .ai/tools/feature_registry/tests/test_composition.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import io
import json
import os
import sys

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # .ai/tools/feature_registry
TOOLS_DOTAI = os.path.dirname(TOOL_DIR)                                          # .ai/tools
DOTAI = os.path.dirname(TOOLS_DOTAI)                                             # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)
VALIDATOR_DIR = os.path.join(DOTAI, "tools", "validator")

if VALIDATOR_DIR not in sys.path:
    sys.path.insert(0, VALIDATOR_DIR)
if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

import compose_features as composer
import check_feature_metadata as metadata_validator

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def blueprint_of(requirement: str) -> dict:
    index = composer.load_index()
    return composer.compose_from_index(requirement, index)


def check_case(name: str, requirement: str, expected_any: list, expected_all: list, expected_none: list = None) -> dict:
    bp = blueprint_of(requirement)
    features = bp["features"]
    for fid in expected_all:
        ok("%s: contains %s" % (name, fid), fid in features, str(features))
    for fid in (expected_none or []):
        ok("%s: does not over-join %s" % (name, fid), fid not in features, str(features))
    if expected_any:
        ok("%s: covers %s" % (name, " or ".join(expected_any)),
           any(fid in features for fid in expected_any), str(features))
    ok("%s: blueprint has reason for all members" % name,
       all(fid in bp["reason"] for fid in features))
    ok("%s: blueprint lists required tests" % name,
       set(bp["validation"]["required_tests"]) == set(features))
    return bp


def run() -> int:
    print("=== Case 1: enemy attacks player ===")
    bp1 = check_case("case1", "enemy attacks player", [], ["health", "contact_damage"],
                     expected_none=["health_bar", "player_movement", "stun"])

    print("=== Case 2: enemy chases player ===")
    bp2 = check_case("case2", "enemy chases player", [], ["chase_movement"])

    print("=== Case 3: enemy boss can be stunned ===")
    bp3 = check_case("case3", "enemy boss can be stunned", [], ["health", "stun", "chase_movement"],
                     expected_none=["health_bar", "player_movement"])

    print("=== Entity Blueprint basics ===")
    for name, bp in [("case1", bp1), ("case2", bp2), ("case3", bp3)]:
        ok("%s: role is enemy" % name, bp["entity"]["role"] == "enemy", str(bp["entity"]))
        ok("%s: entity id set" % name, bool(bp["entity"]["id"]))

    print("=== Feature Graph ===")
    graph_path = os.path.join(DOTAI, "context", "feature_graph.json")
    if os.path.isfile(graph_path):
        graph = json.load(io.open(graph_path, encoding="utf-8"))
        nodes = set(graph.get("nodes", []))
        ok("graph: 12 nodes", len(nodes) == 12, str(sorted(nodes)))
        edges = graph.get("edges", [])
        ok("graph: has health->contact_damage edge",
           any(e["from"] == "health" and e["to"] == "contact_damage" and e["type"] == "commonly_used_with"
               for e in edges))
        ok("graph: has contact_damage->stun edge (works_with)",
           any(e["from"] == "contact_damage" and e["to"] == "stun" and e["type"] == "works_with"
               for e in edges))
    else:
        ok("graph: feature_graph.json exists", False, graph_path)

    print("=== Validator: composition checks ===")
    # 合法组合：case1 蓝图应零失败
    result = metadata_validator.check_composition(
        {"features": bp1["features"], "validation": {"required_tests": bp1["validation"]["required_tests"]}},
        PROJECT_ROOT,
    )
    ok("validator(composition): case1 blueprint legal", result["failures"] == [], str(result["failures"]))

    # 缺前置：contact_damage 无 health → Composition incomplete
    result = metadata_validator.check_composition(
        {"features": ["contact_damage"], "validation": {"required_tests": ["contact_damage"]}},
        PROJECT_ROOT,
    )
    ok("validator(composition): missing provider reported",
       any("Composition incomplete" in f and "damage_receiver" in f for f in result["failures"]),
       str(result["failures"]))

    # 冲突：player_movement + chase_movement 同时在组合
    result = metadata_validator.check_composition(
        {"features": ["player_movement", "chase_movement"], "validation": {"required_tests": []}},
        PROJECT_ROOT,
    )
    ok("validator(composition): conflict reported",
       any("conflict" in f and "player_movement" in f for f in result["failures"]),
       str(result["failures"]))

    # relations 引用检查：伪造坏关系目标（隔离临时目录，不污染真实项目）
    import tempfile, shutil
    tmp = tempfile.mkdtemp(prefix="composition_bad_rel_")
    try:
        features_dir = os.path.join(tmp, "Features", "health")
        os.makedirs(features_dir)
        io.open(os.path.join(features_dir, "feature.yaml"), "w", encoding="utf-8").write(
            "id: health\nversion: 1\ncategory: component\nsummary: x\n"
            "provides: [health_state]\nrequires: []\ninterfaces: {}\nvalidation: {}\n"
            "relations:\n  commonly_used_with:\n    - xxx_not_exist\n"
        )
        result = metadata_validator.check_features(tmp, os.path.join(tmp, "no_index.json"))
        # 无索引时还会报 index missing；这里只关心 relations 错误出现
        ok("validator(relations): unknown relation target reported",
           any("Unknown Feature relation: health -> xxx_not_exist" in f for f in result["failures"]),
           str(result["failures"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for f in _failures:
            print("  - " + f)
        return 1
    print("PASS: all composition checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
