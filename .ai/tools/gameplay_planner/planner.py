#!/usr/bin/env python3
"""Gameplay Loop Composer / Planner (v1)

把自然语言游戏需求转成 Gameplay Blueprint：

    Natural Language
        ↓
    Gameplay Analysis（requirement_parser，规则式）
        ↓
    Required Entities + Feature Discovery（compose_features 内核）
        ↓
    Gameplay Blueprint（gameplay_schema.yaml 格式）
        ↓
    Entity Relationship Graph（entity_graph.json）

用法:
    python planner.py "create enemy survival game" [--id my_game] [--out <path>]
    python planner.py "..." --emit-blueprint <path>   # 同时落盘 Blueprint YAML

输出: Gameplay Blueprint（YAML 文本）+ entity_graph.json（自动更新）。

流程衔接：
    Gameplay Blueprint -> 每实体 scene_composer 生成场景（scene-composer Skill）
                       -> check_gameplay.py 校验（实体场景/能力/循环闭合）
                       -> 循环测试（Godot 无头）

架构约束：Feature 管能力、Entity 管组合、Scene 管实例、System 管跨实体流程；
禁止 God Object / GameManager / EntityManager / FeatureManager。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "feature_registry"))

import compose_features as composer                       # noqa: E402
from blueprint_generator import (                         # noqa: E402
    ENTITY_GRAPH_PATH,
    blueprint_to_yaml_text,
    build_entity_graph,
    generate_blueprint,
    write_entity_graph,
)


def print_blueprint(bp: dict) -> None:
    print("Gameplay Blueprint")
    print()
    print("gameplay:")
    print("  id: %s" % bp["gameplay"]["id"])
    print()
    print("entities:")
    for entity_id, entry in bp["entities"].items():
        scene = entry.get("scene")
        note = "  # reuse %s" % scene if scene else ""
        print("  %s:" % entity_id)
        print("    features:")
        for fid in entry["features"]:
            print("      - %s" % fid)
        if entry.get("_missing_seed_capabilities"):
            print("    # missing seed capabilities: %s" % ", ".join(entry["_missing_seed_capabilities"]))
        if note:
            print("    scene: %s%s" % (scene, " " if note.strip("# ").startswith("reuse") else ""))
    print()
    print("systems:")
    for system_id in bp["systems"]:
        print("  - %s" % system_id)
    print()
    print("loop:")
    print("  start: %s" % bp["loop"]["start"])
    print("  cycle: %s" % bp["loop"]["cycle"])
    print("  end:   %s" % bp["loop"]["end"])
    print()
    print("validation:")
    print("  required_entities: %s" % ", ".join(bp["validation"]["required_entities"]))
    print("  required_features: %s" % ", ".join(bp["validation"]["required_features"]))
    print("  required_tests:")
    for fid in bp["validation"]["required_tests"]:
        print("    - %s" % fid)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compose a gameplay requirement into a Gameplay Blueprint.")
    parser.add_argument("requirement", nargs="+", help="Natural language gameplay requirement")
    parser.add_argument("--id", dest="game_id", default="", help="Explicit gameplay id")
    parser.add_argument("--out", default="", help="Write blueprint YAML to this path")
    parser.add_argument("--graph-out", default=ENTITY_GRAPH_PATH, help="entity_graph.json output path")
    parser.add_argument("--no-graph", action="store_true", help="Do not write entity_graph.json")
    args = parser.parse_args(argv)

    requirement = " ".join(args.requirement)
    index = composer.load_index()
    bp = generate_blueprint(requirement, index)
    if args.game_id:
        bp["gameplay"]["id"] = args.game_id

    graph = build_entity_graph(bp, index)
    if not args.no_graph:
        write_entity_graph(graph, args.graph_out)

    print_blueprint(bp)
    print()
    print("Entity Relationship Graph: %d node(s), %d edge(s)%s" % (
        len(graph["nodes"]), len(graph["edges"]),
        "" if args.no_graph else " -> %s" % args.graph_out,
    ))
    for edge in graph["edges"]:
        print("  %s -[%s]-> %s" % (edge["from"], edge["relation"], edge["to"]))

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(blueprint_to_yaml_text(bp))
        print()
        print("Blueprint written: %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
