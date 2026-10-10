#!/usr/bin/env python3
"""Scene Test Generator

根据 Scene Blueprint 自动生成 Tests/test_<scene_id>.gd：

    1. Scene Load   —— load("res://Scenes/<RootName>.tscn") 非空断言
    2. Feature Exists —— Blueprint 每个 Feature 的 required_nodes 节点存在
    3. Signal Exists —— 各 Feature template 声明的 signals 逐一 has_signal 断言

生成物遵循项目测试契约（SceneTree 脚本）：全部通过 print PASS 并退出 0；
任一失败 printerr FAIL 并退出 1。可被 .ai/tools/run_tests.py 自动发现运行。

用法:
    python generate_scene_test.py <blueprint.yaml> [--out Tests]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scene_composer"))

import yaml

try:
    from template_loader import (
        PROJECT_ROOT,
        derive_scene_blueprint,
        load_templates,
        normalize_scene_blueprint,
        template_node_name,
        template_signals,
    )
except ImportError:   # 从 scene_composer 包内导入时（目录名不可作包名，作回退处理）
    from scene_composer.template_loader import (
        PROJECT_ROOT,
        derive_scene_blueprint,
        load_templates,
        normalize_scene_blueprint,
        template_node_name,
        template_signals,
    )

TESTS_DIR = os.path.join(PROJECT_ROOT, "Tests")
SCENES_DIR = os.path.join(PROJECT_ROOT, "Scenes")

_HEADER = """\
extends SceneTree
## 由 .ai/tools/test_generator/generate_scene_test.py 自动生成——Scene Blueprint 回归测试。
## 不要手工编辑；重新生成请运行:
##   python .ai/tools/test_generator/generate_scene_test.py <blueprint.yaml>
##
## 用法：godot --headless --path . -s res://Tests/test_%(scene_id)s.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []


func _initialize() -> void:
\tvar packed: PackedScene = load("res://%(scene_path)s")
\tif packed == null:
\t\t_failures.append("Scene Load: res://%(scene_path)s 加载失败")
\t\t_report()
\t\treturn
\tvar entity: Node = packed.instantiate()
"""

_FOOTER = """\
\tentity.free()
\t_report()


func _report() -> void:
\tif _failures.is_empty():
\t\tprint("PASS: %(root_name)s 场景组合验证通过")
\t\tquit(0)
\telse:
\t\tfor failure in _failures:
\t\t\tprinterr("FAIL: " + failure)
\t\tquit(1)
"""


def _gd_str(value: str) -> str:
    return value.replace('"', '\\"')


def build_test_source(blueprint: dict, templates: dict, scene_path: str) -> str:
    """生成测试脚本文本（blueprint 为规整后的 Scene Blueprint）。"""
    parts = [_HEADER % {"scene_id": _gd_str(blueprint["scene_id"]),
                        "scene_path": _gd_str(scene_path)}]

    # 2. Feature Exists
    parts.append("\t# Feature Exists\n")
    node_names = []
    for fid in blueprint["features"]:
        template = templates.get(fid) or {}
        node_name = template_node_name(fid, template)
        node_names.append((fid, node_name, template))
        parts.append(
            '\tif entity.get_node_or_null("%s") == null:\n'
            '\t\t_failures.append("Missing Feature node: %s")\n'
            % (node_name, node_name)
        )
    parts.append("\n")

    # 3. Signal Exists（按 Feature template 的 interfaces.signals）
    parts.append("\t# Signal Exists\n")
    for fid, node_name, template in node_names:
        signals = template_signals(template)
        if not signals:
            continue
        parts.append("\tvar %s_node = entity.get_node_or_null(\"%s\")\n" % (fid, node_name))
        parts.append("\tif %s_node != null:\n" % fid)
        for signal_name in signals:
            parts.append(
                '\t\tif not %s_node.has_signal("%s"):\n'
                '\t\t\t_failures.append("Missing signal: %s.%s")\n'
                % (fid, signal_name, node_name, signal_name)
            )
    parts.append("\n")
    parts.append(_FOOTER % {"root_name": _gd_str(blueprint["root_name"])})
    return "".join(parts)


def generate_test_file(blueprint: dict, out_dir: str = TESTS_DIR,
                       features_dir: str = None) -> str:
    """规整 blueprint 并写出 Tests/test_<scene_id>.gd，返回路径。"""
    if "scene_id" not in blueprint:   # 传入的是原始 blueprint
        normalized, errors = normalize_scene_blueprint(derive_scene_blueprint(blueprint))
        if errors:
            raise SystemExit("FAIL: invalid blueprint: %s" % "; ".join(errors))
        blueprint = normalized
    features_dir = features_dir or os.path.join(PROJECT_ROOT, "Features")
    templates = load_templates(blueprint["features"], features_dir)
    scene_path = "Scenes/%s.tscn" % blueprint["root_name"]
    source = build_test_source(blueprint, templates, scene_path)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    out_path = os.path.join(out_dir, "test_%s.gd" % blueprint["scene_id"])
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(source)
    return out_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate a SceneTree regression test for a composed scene.")
    parser.add_argument("blueprint", help="Blueprint yaml path (Scene or Entity Blueprint)")
    parser.add_argument("--out", default=TESTS_DIR, help="Output directory (default: Tests/)")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.blueprint):
        print("FAIL: Blueprint not found: %s" % args.blueprint)
        return 2
    blueprint_raw = yaml.safe_load(open(args.blueprint, encoding="utf-8")) or {}
    out_path = generate_test_file(blueprint_raw, out_dir=args.out)
    print("Test generated: %s" % os.path.relpath(out_path, PROJECT_ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
