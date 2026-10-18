#!/usr/bin/env python3
"""Scene Validator

对生成的 .tscn 做结构校验（只读解析文本，不启动 Godot）：

    1. Feature 完整性 —— Scene Intent 的每个组件（components[].component）其
       Feature Scene Template 的 required_nodes 必须以实例节点存在；缺失报
       「Missing Feature: <node>」。
    2. Feature Dependency —— 成员 requires 是否由组合满足（复用 dependency_resolver）。
    3. Node Structure —— 根节点类型必须等于 Scene Intent root.type；
       不符报「Invalid Root Node Type」。
    4. 组合约束 —— Scene 不得给根节点挂脚本（Scene 只负责组合）。
    5. 节点父路径 —— 显式 parent 必须指向场景内已声明的节点。
    6. 节点重名 —— 同一父节点下不得重名（Godot 硬约束；Asset Binding 加入的
       资源节点与组件实例共用命名空间）。

输入边界（Phase 1.8.8）：唯一合法输入是 Scene Intent（`SceneIntent` 对象或契约文档
mapping）；旧规整内部 dict 被拒绝（无隐藏转换、无兼容适配器）。
原始 Blueprint → Scene Intent 的转换只发生在 CLI 入口（check_scene_composition /
test_generator 的 intent_from_blueprint）。

Phase 1.11 —— 实体根为 Feature 实例（Intent root.scene）：
    - 该 Feature 的「存在性」由根实例本身满足：场景根必须是 instance 节点，且其引用
      的场景路径 == 该 Feature 模板的入口场景（静态可证，不按节点名猜）；
    - 根类型不再取根节点 header（instance 根没有 type=），而是静态解析被引用场景的
      根节点类型（无法解析 → 报 Composition Error / Invalid Root Node Type）。
"""

import os
import re

from dependency_resolver import resolve
from scene_intent import intent_components, intent_document, intent_root
from template_loader import (
    PROJECT_ROOT,
    template_node_name,
    template_root_instance,
    template_root_requirements,
    template_scene_path,
)

_ROOT_NODE_RE = re.compile(r'^\[node name="([^"]*)" type="([^"]*)"\]$', re.M)
_ROOT_INSTANCE_RE = re.compile(r'^\[node name="([^"]*)" instance=ExtResource\("([^"]*)"\)', re.M)
_EXT_RESOURCE_PATH_RE = re.compile(r'path="([^"]*)"')

# 根实例链的最大解析深度（根场景 → 其根场景……；防循环引用）
_ROOT_CHAIN_DEPTH = 8


def _root_instance_name(text: str) -> str:
    """根实例化（无 parent= 的 instance 节点）名称。"""
    match = _ROOT_INSTANCE_RE.search(text)
    return match.group(1) if match else ""


def _ext_resource_paths(text: str) -> dict:
    """ext_resource id -> path（逐行解析，不依赖属性顺序）。"""
    paths = {}
    for line in text.splitlines():
        if not line.startswith("[ext_resource"):
            continue
        ident = re.search(r'id="([^"]*)"', line)
        path = _EXT_RESOURCE_PATH_RE.search(line)
        if ident and path:
            paths[ident.group(1)] = path.group(1)
    return paths


def _root_instance_path(text: str) -> str:
    """根实例引用的 PackedScene 路径（res://）；根不是实例节点时返回 ""。"""
    match = _ROOT_INSTANCE_RE.search(text)
    if not match:
        return ""
    return _ext_resource_paths(text).get(match.group(2), "")


def resolve_res_path(res_path: str) -> str:
    """res:// 路径 -> 项目内绝对路径（只做路径拼接，不读注册表）。"""
    return os.path.join(PROJECT_ROOT, str(res_path).replace("res://", "").replace("/", os.sep))


def _root_node_type(scene_path: str, depth: int = 0) -> str:
    """静态解析场景（可递归根实例链）的根节点类型；无法解析返回 ""。"""
    if depth > _ROOT_CHAIN_DEPTH:
        return ""
    try:
        with open(scene_path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return ""
    match = _ROOT_NODE_RE.search(text)
    if match:
        return match.group(2)
    nested = _root_instance_path(text)
    if not nested:
        return ""
    nested_path = resolve_res_path(nested)
    if os.path.abspath(nested_path) == os.path.abspath(scene_path):
        return ""                                     # 自引用，停止解析
    return _root_node_type(nested_path, depth + 1)


_INSTANCE_RE = re.compile(r'^\[node name="([^"]*)" parent="[^"]*" instance=ExtResource', re.M)
_NODE_PATH_RE = re.compile(r'^\[node name="([^"]*)"(?: type="[^"]*")?(?: parent="([^"]*)")?', re.M)
_SCRIPT_RE = re.compile(r'^\[node name="([^"]*)"[^\]]*\nscript\s*=', re.M)


def parse_scene(scene_path: str) -> dict:
    """轻量解析 .tscn 文本。

    返回 {root_name, root_type, root_instance_path, node_names, all_nodes,
          has_root_script, text}。
    """
    with open(scene_path, encoding="utf-8") as f:
        text = f.read()
    root_match = _ROOT_NODE_RE.search(text)
    root_name = root_match.group(1) if root_match else _root_instance_name(text)
    root_type = root_match.group(2) if root_match else ""
    # 根实例引用的 PackedScene（Phase 1.11；根不是实例节点时为空）
    root_instance_path = "" if root_match else _root_instance_path(text)
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
        "root_instance_path": root_instance_path,
        "node_names": node_names,
        "all_nodes": all_nodes,
        "has_root_script": has_root_script,
        "text": text,
    }


def validate_scene(scene_intent, scene_path: str, index: list, templates: dict,
                   features_dir: str) -> dict:
    """校验生成的场景；返回 {ok, failures, warnings}。

    scene_intent —— SceneIntent 对象或其契约文档 mapping（Scene 层唯一合法输入）。
    templates    —— {feature_id: Feature Scene Template}，与 intent components 同源。
    """
    document = intent_document(scene_intent, "scene_validator.validate_scene")
    features = intent_components(document)

    failures, warnings = [], []
    try:
        scene = parse_scene(scene_path)
    except OSError as exc:
        return {"ok": False, "failures": ["Cannot read scene: %s (%s)" % (scene_path, exc)], "warnings": []}

    # 1. Feature 完整性
    # Phase 1.11：计划声明实体根 = 某成员的入口场景（root.scene，由 attach.root_instance 推导
    # 或作者显式声明）时，该成员由**根实例**承载：场景根必须是它的实例，且不得再作为子节点
    # 出现（否则会得到第二个行为组件）。作者显式声明 root.type 的计划（未声明根场景实例）
    # 不受本规则影响 —— 它的实例化计划由作者负责，校验不重新解释它。
    present = set(scene["node_names"])
    root_instance_path = scene["root_instance_path"]
    declared_root_scene = str(intent_root(document).get("scene") or "").strip()
    if root_instance_path:
        root_reference = resolve_res_path(root_instance_path)
        if not os.path.isfile(root_reference):
            failures.append("Composition Error: root instance scene not found: %s"
                            % root_instance_path)
    for fid in features:
        template = templates.get(fid) or {}
        node_name = template_node_name(fid, template)
        entry_scene = template_scene_path(fid, template, features_dir)
        if (declared_root_scene and entry_scene == declared_root_scene
                and template_root_instance(fid, template)):
            if root_instance_path != declared_root_scene:
                failures.append(
                    "Missing Feature root: %s (scene root must be an instance of %s, got %s)"
                    % (fid, declared_root_scene,
                       root_instance_path or "<typed root node>"))
            elif node_name in present:
                failures.append(
                    "Composition Error: root instance component %s must not also be "
                    "instantiated as a child node %s" % (fid, node_name))
            continue
        if node_name in present:
            continue
        if root_instance_path and entry_scene == root_instance_path:
            continue                                    # 实体根即该组件的入口场景实例
        failures.append("Missing Feature: %s (node %s)" % (fid, node_name))

    # 2. Feature Dependency
    dep = resolve(features, index, features_dir)
    failures.extend(dep["errors"])
    failures.extend(dep["missing"])
    for fid in dep["unknown"]:
        failures.append("Unknown Feature in scene composition: %s" % fid)

    # 3. Root type
    # 根为实例节点（root.scene）时根类型不写在 header 里，静态解析被引用场景的根类型
    # （实例链递归）；解析失败则报 <none>，不猜测。
    scene_root_type = scene["root_type"]
    if not scene_root_type and root_instance_path:
        scene_root_type = _root_node_type(resolve_res_path(root_instance_path))
    expected_root_type = str(intent_root(document).get("type") or "")
    if expected_root_type and scene_root_type != expected_root_type:
        failures.append(
            "Invalid Root Node Type: expected %s, got %s"
            % (expected_root_type, scene_root_type or "<none>")
        )

    # 4. Scene 只负责组合：根节点不挂脚本
    if scene["has_root_script"]:
        failures.append("Scene composition violation: root node must not own a script")

    # 提示：成员声明的 root_type 要求是否被满足（如 chase_movement 需 CharacterBody2D）
    # 根实例化时 root.type 缺失，根类型由被引用场景的根节点类型解析（不作命名推断）
    effective_root_type = scene_root_type or scene["root_name"]
    required_roots = template_root_requirements(templates)
    if required_roots and effective_root_type not in required_roots:
        failures.append(
            "Composition Error: root type %s does not satisfy member requirements: %s"
            % (effective_root_type, ", ".join(sorted(required_roots)))
        )

    # 5. 节点父路径有效性：普通节点的 parent 若显式且非 "."，必须指向场景内已声明的节点
    known_paths = {".", scene["root_name"], ""} | {name for name, _parent in scene["all_nodes"]
                                                    if name and name != scene["root_name"]}
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

    # 6. 同一父节点下不得重名（Asset 资源节点与组件实例共用命名空间）
    seen: dict = {}
    for name, parent in scene["all_nodes"]:
        if not name:
            continue
        key = (parent or ".", name)
        if key in seen:
            failures.append("Composition Error: duplicate node name %r under parent %r"
                            % (name, parent or "."))
        seen[key] = True

    return {"ok": not failures, "failures": failures, "warnings": warnings}
