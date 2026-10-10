#!/usr/bin/env python3
"""Scene Validator

对生成的 .tscn 做结构校验（只读解析文本，不启动 Godot）：

    1. Feature 完整性 —— Blueprint 每个 Feature 的 required_nodes 必须以
       实例节点存在；缺失报「Missing Feature: <node>」。
    2. Feature Dependency —— 成员 requires 是否由组合满足
       （复用 dependency_resolver）。
    3. Node Structure —— 根节点类型必须等于 Blueprint root.type；
       不符报「Invalid Root Node Type」。
    4. 组合约束 —— Scene 不得给根节点挂脚本（Scene 只负责组合）。
"""

import re

from dependency_resolver import resolve
from template_loader import template_node_name, template_root_requirements

_ROOT_NODE_RE = re.compile(r'^\[node name="([^"]*)" type="([^"]*)"\]$', re.M)
_ROOT_INSTANCE_RE = re.compile(r'^\[node name="([^"]*)" instance=ExtResource', re.M)


def _root_instance_name(text: str) -> str:
    """根实例化（无 parent= 的 instance 节点）名称。"""
    match = _ROOT_INSTANCE_RE.search(text)
    return match.group(1) if match else ""
_INSTANCE_RE = re.compile(r'^\[node name="([^"]*)" parent="[^"]*" instance=ExtResource', re.M)
_NODE_PATH_RE = re.compile(r'^\[node name="([^"]*)"(?: type="[^"]*")?(?: parent="([^"]*)")?', re.M)
_SCRIPT_RE = re.compile(r'^\[node name="([^"]*)"[^\]]*\nscript\s*=', re.M)


def parse_scene(scene_path: str) -> dict:
    """轻量解析 .tscn 文本。返回 {root_name, root_type, node_names, has_root_script}。"""
    with open(scene_path, encoding="utf-8") as f:
        text = f.read()
    root_match = _ROOT_NODE_RE.search(text)
    root_name = root_match.group(1) if root_match else _root_instance_name(text)
    root_type = root_match.group(2) if root_match else ""
    node_names = _INSTANCE_RE.findall(text)
    # 所有节点（含普通节点与实例，根实例无 parent=）: (name, parent)
    all_nodes = _NODE_PATH_RE.findall(text)
    # 根节点带 script 属性（instance 节点的 script 来自被实例化场景，不算）
    has_root_script = False
    for match in _SCRIPT_RE.finditer(text):
        if match.group(1) == root_name and not match.group(0).count("instance"):
            has_root_script = True
            break
    return {
        "root_name": root_name,
        "root_type": root_type,
        "node_names": node_names,
        "all_nodes": all_nodes,
        "has_root_script": has_root_script,
        "text": text,
    }


def validate_scene(blueprint: dict, scene_path: str, index: list, templates: dict,
                   features_dir: str) -> dict:
    """校验生成的场景；返回 {ok, failures, warnings}。

    blueprint 为 normalize_scene_blueprint 的输出。
    """
    failures, warnings = [], []
    try:
        scene = parse_scene(scene_path)
    except OSError as exc:
        return {"ok": False, "failures": ["Cannot read scene: %s (%s)" % (scene_path, exc)], "warnings": []}

    # 1. Feature 完整性
    present = set(scene["node_names"])
    for fid in blueprint["features"]:
        template = templates.get(fid) or {}
        node_name = template_node_name(fid, template)
        if node_name not in present:
            failures.append("Missing Feature: %s (node %s)" % (fid, node_name))

    # 2. Feature Dependency
    dep = resolve(blueprint["features"], index, features_dir)
    failures.extend(dep["errors"])
    failures.extend(dep["missing"])
    for fid in dep["unknown"]:
        failures.append("Unknown Feature in scene composition: %s" % fid)

    # 3. Root type
    if blueprint["root_type"] and scene["root_type"] != blueprint["root_type"]:
        failures.append(
            "Invalid Root Node Type: expected %s, got %s"
            % (blueprint["root_type"], scene["root_type"] or "<none>")
        )

    # 4. Scene 只负责组合：根节点不挂脚本
    if scene["has_root_script"]:
        failures.append("Scene composition violation: root node must not own a script")

    # 提示：成员声明的 root_type 要求是否被满足（如 chase_movement 需 CharacterBody2D）
    # 根实例化时 root.type 缺失，根类型由世界约定推断：以根实例节点名为 Type
    effective_root_type = scene["root_type"] or scene["root_name"]
    required_roots = template_root_requirements(templates)
    if required_roots and effective_root_type not in required_roots:
        failures.append(
            "Composition Error: root type %s does not satisfy member requirements: %s"
            % (effective_root_type, ", ".join(sorted(required_roots)))
        )

    # 5. 节点父路径有效性：普通节点的 parent 若显式且非 "."，必须指向场景内已声明的节点
    known_paths = {".", scene["root_name"], ""} | {name for name, _parent in scene["all_nodes"] if name and name != scene["root_name"]}
    for name, parent in scene["all_nodes"]:
        if not parent or parent == ".":
            continue
        if parent.startswith("/"):
            continue  # 绝对路径不在此校验
        # 相对路径逐段解析："X/Y" 表示随 X 逐层；首段及逐段需在已知声明中可到达
        segs = parent.replace(".", "").split("/")
        cur = None
        ok_path = True
        for seg in segs:
            if not seg:
                continue
            if cur is None:
                if seg not in known_paths:
                    ok_path = False
                    break
                cur = seg
            else:
                child_names = {n for n, p in scene["all_nodes"] if p == cur}
                if seg not in child_names:
                    ok_path = False
                    break
                cur = seg
        if not ok_path:
            failures.append(
                "Composition Error: node %s parent path %r references a node not declared in this scene"
                % (name or "<root>", parent)
            )

    return {"ok": not failures, "failures": failures, "warnings": warnings}
