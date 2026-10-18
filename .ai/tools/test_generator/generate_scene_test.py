#!/usr/bin/env python3
"""Scene Test Generator

根据 **Scene Intent** 自动生成 Tests/test_<scene_id>.gd：

    1. Scene Load   —— load("res://Scenes/<RootName>.tscn") 非空断言
    2. Feature Exists —— Scene Intent components 的 required_nodes 节点存在
    3. Signal Exists —— 各 Feature template 声明的 signals 逐一 has_signal 断言

输入边界（Phase 1.8.8）：`generate_test_file()` / `build_test_source()` 的唯一合法
输入是 Scene Intent（`SceneIntent` 对象或契约文档 mapping）；旧规整内部 dict
（scene_id / root_name / features / extra_nodes）被拒绝。
原始 Blueprint 由 `intent_from_blueprint()` 先构造为 Scene Intent（CLI 入口用）。

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
    from scene_intent import (
        intent_components,
        intent_document,
        intent_from_blueprint,
        intent_root,
    )
    from template_loader import (
        PROJECT_ROOT,
        display_path,
        load_templates,
        template_node_name,
        template_root_instance,
        template_root_type,
        template_signals,
    )
except ImportError:   # 从 scene_composer 包内导入时（目录名不可作包名，作回退处理）
    from scene_composer.scene_intent import (
        intent_components,
        intent_document,
        intent_from_blueprint,
        intent_root,
    )
    from scene_composer.template_loader import (
        PROJECT_ROOT,
        display_path,
        load_templates,
        template_node_name,
        template_root_instance,
        template_root_type,
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


def _scene_id(document: dict) -> str:
    scene = document.get("scene")
    return str(scene.get("id") or "") if isinstance(scene, dict) else ""


def build_test_source(scene_intent, templates: dict, scene_path: str) -> str:
    """生成测试脚本文本（scene_intent = SceneIntent 对象或契约文档 mapping）。"""
    document = intent_document(scene_intent, "generate_scene_test.build_test_source")
    root_name = str(intent_root(document).get("name") or "")
    parts = [_HEADER % {"scene_id": _gd_str(_scene_id(document)),
                        "scene_path": _gd_str(scene_path)}]

    # 2. Feature Exists
    parts.append("\t# Feature Exists\n")
    node_names = []
    for fid in intent_components(document):
        template = templates.get(fid) or {}
        node_name = template_node_name(fid, template)
        root_type = template_root_type(fid, template)
        node_names.append((fid, node_name, template))
        # Phase 1.11：实体根即该组件的入口场景实例 —— 它的存在性证据是**根节点类型**
        # （子节点里没有同名节点，按子节点名断言会得到假失败）。
        if template_root_instance(fid, template) and root_type:
            parts.append(
                '\tif not (entity is %s):\n'
                '\t\t_failures.append("Missing Feature root: %s (entity root must be %s)")\n'
                % (root_type, fid, root_type)
            )
            continue
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
    parts.append(_FOOTER % {"root_name": _gd_str(root_name)})
    return "".join(parts)


def generate_test_file(scene_intent, out_dir: str = TESTS_DIR,
                       features_dir: str = None) -> str:
    """由 Scene Intent 写出 Tests/test_<scene_id>.gd，返回路径。

    唯一合法输入是 Scene Intent（SceneIntent 对象或契约文档 mapping）；
    原始 Blueprint / 旧规整内部 dict 请先经 `intent_from_blueprint()` 构造。
    """
    document = intent_document(scene_intent, "generate_scene_test.generate_test_file")
    features_dir = features_dir or os.path.join(PROJECT_ROOT, "Features")
    templates = load_templates(intent_components(document), features_dir)
    scene_path = "Scenes/%s.tscn" % str(intent_root(document).get("name") or "")
    source = build_test_source(document, templates, scene_path)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    out_path = os.path.join(out_dir, "test_%s.gd" % _scene_id(document))
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
    intent, errors = intent_from_blueprint(blueprint_raw)
    if errors or intent is None:
        print("FAIL: invalid blueprint: %s" % "; ".join(errors or ["unknown error"]))
        return 2
    out_path = generate_test_file(intent, out_dir=args.out)
    print("Test generated: %s" % display_path(out_path, PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
