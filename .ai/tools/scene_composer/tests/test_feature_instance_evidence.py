#!/usr/bin/env python3
"""Feature Instance Evidence 测试（Phase 1.37）

背景（Phase 1.36 评估证据，任务 T1）：
    「a collectible key that disappears when picked up」→ 只有一个 Feature
    （collect_pickup）的 Entity Blueprint **无法**直接生成场景，报
    `Capability contract failed: Collision requires CollisionShape2D`。
    根因不是生成器，而是 Feature 元数据缺口：组件入口场景自带的节点结构
    （Area2D + PickupShape）没有以 `instance:` 声明，能力契约因此「看不见」它。

本测试锁定修复后的不变量（不修改判定口径，只保证证据存在且真实）：

    E1 声明完整性：入口场景**自带碰撞形状**的 Feature 必须提供实例证据
       （`instance.node_type` 是碰撞类节点，或 `attach.root_instance` + `scene.root_type`）。
       判定由场景推导而非硬编码名单：contact_damage 的入口场景没有任何碰撞形状
       （接触形状由宿主实体声明），因此它不需要（也不应）声明自带碰撞。
    E2 声明真实性：`instance.node_type` 必须等于入口场景的真实根类型，
       `instance.children` 必须是入口场景中真实存在的直接子节点类型
    E3 fail-closed 未被削弱：删掉声明后，同一蓝图仍然 BLOCKED（逐字文案）
    E4 端到端：同一份单 Feature Entity Blueprint，声明存在 → 生成成功；
       声明移除 → 生成 BLOCKED，且零产物
    E5 声明只是证据：生成输出不因声明而多出任何节点

只读项目文件，只写系统临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_feature_instance_evidence.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

from __future__ import annotations

import copy
import os
import re
import shutil
import sys
import tempfile

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))                 # .ai/tools/scene_composer/tests
TOOL_DIR = os.path.dirname(_HERE)                                  # .ai/tools/scene_composer
TOOLS_DIR = os.path.dirname(TOOL_DIR)                              # .ai/tools
DOTAI = os.path.dirname(TOOLS_DIR)                                 # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)
FEATURES_DIR = os.path.join(PROJECT_ROOT, "Features")
EVAL_FIXTURE = os.path.join(TOOLS_DIR, "evaluation", "fixtures",
                            "t1_entity_blueprint.yaml")

if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

import capability_contracts                                   # noqa: E402
import scene_composer                                         # noqa: E402
import template_loader                                        # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_failures: list[str] = []
_checks = 0
_temp_dirs: list[str] = []

NODE_RE = re.compile(r'^\[node name="(?P<name>[^"]*)"(?P<attrs>[^\]]*)\]', re.M)
TYPE_RE = re.compile(r'\btype="(?P<type>[^"]*)"')
PARENT_RE = re.compile(r'\bparent="(?P<parent>[^"]*)"')


def ok(name: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def temp_dir(prefix: str) -> str:
    path = tempfile.mkdtemp(prefix=prefix)
    _temp_dirs.append(path)
    return path


def feature_ids() -> list[str]:
    return sorted(name for name in os.listdir(FEATURES_DIR)
                  if os.path.isdir(os.path.join(FEATURES_DIR, name)))


def feature_meta(feature: str) -> dict:
    path = os.path.join(FEATURES_DIR, feature, "feature.yaml")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def entry_scene(feature: str, template: dict) -> str:
    source = str((template.get("scene") or {}).get("source") or "").strip()
    if not source:
        source = str(((feature_meta(feature).get("composition") or {})
                      .get("entry_scene") or "")).strip()
    return os.path.join(FEATURES_DIR, feature, source) if source else ""


def parse_scene(path: str) -> tuple[str, set[str], set[str]]:
    """返回 (根节点类型, 直接子节点类型集合, 全部节点类型集合)。"""
    text = open(path, encoding="utf-8").read()
    root_type = ""
    children = set()
    all_types = set()
    for match in NODE_RE.finditer(text):
        node_type = TYPE_RE.search(match.group("attrs"))
        parent = PARENT_RE.search(match.group("attrs"))
        if node_type:
            all_types.add(node_type.group("type"))
        if not root_type and not parent:
            root_type = node_type.group("type") if node_type else ""
            continue
        if parent and parent.group("parent") == "." and node_type:
            children.add(node_type.group("type"))
    return root_type, children, all_types


COLLISION_SHAPE_TYPES = ("CollisionShape2D", "CollisionPolygon2D")


def declared_evidence(feature: str) -> str:
    """返回该 Feature 声明的碰撞类实例证据类型（无声明返回 ""）。

    两种合法形态：
      - instance.node_type（组件自带物理体）
      - attach.root_instance + scene.root_type（组件入口场景即实体根）
    """
    allowed = set(capability_contracts.COLLISION_NODE_TYPES)
    template = template_loader.load_template(feature)
    node_type = str((template.get("instance") or {}).get("node_type") or "").strip()
    if node_type:
        return node_type
    if template_loader.template_root_instance(feature, template):
        root_type = template_loader.template_root_type(feature, template)
        if root_type in allowed:
            return root_type
    return ""


# ------------------------------------------------------------------ E1 / E2

def test_declaration_complete() -> None:
    print("=== E1: 声明完整性（入口场景自带碰撞形状 ⇔ 必须有实例证据） ===")
    declared_count = 0
    shape_bearing = []
    for feature in feature_ids():
        template = template_loader.load_template(feature)
        if not template:
            continue
        scene_path = entry_scene(feature, template)
        if not (scene_path and os.path.isfile(scene_path)):
            continue
        _root, _children, all_types = parse_scene(scene_path)
        brings_shape = any(node_type in COLLISION_SHAPE_TYPES for node_type in all_types)
        declared = declared_evidence(feature)
        if declared:
            declared_count += 1
        if brings_shape:
            shape_bearing.append(feature)
            ok("E1: %s 入口场景自带碰撞形状 → 必须声明实例证据" % feature,
               bool(declared),
               "instance.node_type=<none> root_instance/root_type 均未声明")
        else:
            ok("E1: %s 入口场景不自带碰撞形状 → 无需声明（可显式声明根实例）" % feature,
               True)
    ok("E1: 自带入碰撞形状的 Feature 集合非空", len(shape_bearing) >= 1, str(shape_bearing))
    ok("E1: 已声明的 Feature 数量与自带入碰撞形状的集合一致（无遗忘、无撒谎）",
       declared_count >= len(shape_bearing),
       "declared=%d shape_bearing=%d %s" % (declared_count, len(shape_bearing), shape_bearing))


def test_declaration_truthful() -> None:
    print("=== E2: 声明真实性（必须与入口场景一致） ===")
    for feature in feature_ids():
        template = template_loader.load_template(feature)
        instance = (template.get("instance") or {})
        node_type = str(instance.get("node_type") or "").strip()
        if not node_type:
            continue
        scene_path = entry_scene(feature, template)
        ok("E2: %s 入口场景存在" % feature, bool(scene_path) and os.path.isfile(scene_path),
           scene_path)
        if not (scene_path and os.path.isfile(scene_path)):
            continue
        actual_root, actual_children, _all = parse_scene(scene_path)
        ok("E2: %s instance.node_type == 入口场景根类型" % feature,
           node_type == actual_root, "declared=%r actual=%r" % (node_type, actual_root))
        declared_children = set(str(item).strip() for item in (instance.get("children") or []))
        extra = declared_children - actual_children
        ok("E2: %s instance.children ⊆ 入口场景直接子节点" % feature,
           not extra, "declared-only=%s actual=%s" % (sorted(extra), sorted(actual_children)))


# ------------------------------------------------------------------ E3 / E4

def stripped_features_dir() -> str:
    """复制 Features/ 到临时目录，并删除 collect_pickup 的 instance 声明。"""
    target = os.path.join(temp_dir("p137_features_"), "Features")
    shutil.copytree(FEATURES_DIR, target)
    path = os.path.join(target, "collect_pickup", "template.yaml")
    with open(path, encoding="utf-8") as handle:
        template = yaml.safe_load(handle) or {}
    template.pop("instance", None)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(template, handle, allow_unicode=True, sort_keys=False)
    return target


def fixture_blueprint() -> dict:
    with open(EVAL_FIXTURE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_fail_closed_and_end_to_end() -> None:
    print("=== E3/E4: 未声明仍 BLOCKED；声明后同一蓝图生成成功 ===")
    blueprint = fixture_blueprint()
    out_ok = temp_dir("p137_out_")
    declared = scene_composer.compose(copy.deepcopy(blueprint), out_dir=out_ok,
                                      features_dir=FEATURES_DIR)
    ok("E4: 单 Feature Entity Blueprint 生成成功（声明存在）",
       declared.get("ok") is True, str(declared.get("failures"))[:400])
    scene_path = declared.get("scene_path") or ""
    ok("E4: 生成文件存在", bool(scene_path) and os.path.isfile(scene_path), scene_path)

    stripped = stripped_features_dir()
    out_blocked = temp_dir("p137_blocked_")
    blocked = scene_composer.compose(copy.deepcopy(blueprint), out_dir=out_blocked,
                                     features_dir=stripped)
    failures = [str(item) for item in (blocked.get("failures") or [])]
    ok("E3: 移除声明后同一蓝图 BLOCKED", blocked.get("ok") is False, str(failures)[:400])
    ok("E3: 失败原因是 Collision 契约（逐字文案）",
       any(item.endswith("Capability contract failed: Collision requires CollisionShape2D")
           for item in failures), str(failures)[:400])
    produced = [name for name in os.listdir(out_blocked)] if os.path.isdir(out_blocked) else []
    ok("E3: BLOCKED 时不产出任何场景文件", produced == [], str(produced))

    if scene_path and os.path.isfile(scene_path):
        text = open(scene_path, encoding="utf-8").read()
        ok("E5: 大根保持 Node2D（声明不改变根类型）",
           '[node name="EvalKey" type="Node2D"]' in text, text[:300])
        ok("E5: 声明不物化额外节点（无 CollisionShape2D）",
           "CollisionShape2D" not in text, text[:300])
        ok("E5: 组件实例仍按 ExtResource 实例化",
           'instance=ExtResource(' in text
           and "res://Features/collect_pickup/CollectPickup.tscn" in text, text[:300])


def main() -> int:
    try:
        test_declaration_complete()
        test_declaration_truthful()
        test_fail_closed_and_end_to_end()
    finally:
        for path in _temp_dirs:
            shutil.rmtree(path, ignore_errors=True)
    if _failures:
        print("FAIL: %d feature instance evidence check(s) failed" % len(_failures))
        return 1
    print("PASS: feature instance evidence (%d checks)" % _checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
