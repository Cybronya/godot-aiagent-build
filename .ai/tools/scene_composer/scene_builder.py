#!/usr/bin/env python3
"""Scene Builder

由规整后的 Scene Blueprint 生成 Godot .tscn（format=3）文本。

生成规则（见 .ai/context/scene_schema.yaml）：
    - 根节点：[node name="<RootName>" type="<RootType>"]
      * 蓝图 root 可给 scene:（复用既有 PackedScene 作根，实例化而非新建）
      * root.properties: 属性覆写（motion_mode 等，值按 GDScript 字面量输出）
      * root.groups: 加入节点组（玩家/敌人分组契约）
    - 组件：  [node name="<NodeName>" parent="." instance=ExtResource("<id>")]
              每个组件经 Feature Scene Template 解析到 Feature 入口场景。
    - 额外节点：[node name="<Name>" type="<Type>" parent="."]
      * node.shape: {type: rectangle|circle, size|radius} 生成 sub_resource
        并挂 shape 属性（ContactDamage/拾取范围等需要 CollisionShape2D）。
    - 根节点不写脚本：Scene 只负责组合（架构约束）——根行为由组件承担，
      或复用既有场景时由其自身脚本承担。
"""

import os

from template_loader import (
    template_node_name,
    template_scene_path,
)


def _gd_literal(value) -> str:
    """把 Python 值转成 GDScript 属性字面量。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return "Vector2(%s, %s)" % (_gd_literal(value[0]), _gd_literal(value[1]))
    if isinstance(value, dict) and value.get("type") == "color":
        c = value.get("value") or [1, 1, 1, 1]
        return "Color(%s, %s, %s, %s)" % tuple(_gd_literal(x) for x in (list(c) + [1, 1, 1, 1])[:4])
    raise ValueError("Unsupported property literal: %r" % (value,))


_SHAPE_TYPES = {
    "rectangle": "RectangleShape2D",
    "circle": "CircleShape2D",
}


def _shape_subresources(nodes: list) -> tuple:
    """收集节点 shape 声明 -> (sub_resource 文本行, {node_name: sub_id})。"""
    subs, mapping = [], {}
    for node in nodes:
        shape = node.get("shape") or {}
        stype = str(shape.get("type") or "").strip().lower()
        if not stype:
            continue
        if stype not in _SHAPE_TYPES:
            raise ValueError("Unsupported shape type: %s" % stype)
        sub_id = "%s_%s_%d" % (
            "RectangleShape2D" if stype == "rectangle" else "CircleShape2D",
            node["name"],
            len(mapping) + 1,
        )
        node["_sub_id"] = sub_id
        if stype == "rectangle":
            w, h = (shape.get("size") or [32, 32])[:2]
            subs.append('[sub_resource type="RectangleShape2D" id="%s"]' % sub_id)
            subs.append("size = Vector2(%s, %s)" % (_gd_literal(w), _gd_literal(h)))
        else:
            subs.append('[sub_resource type="CircleShape2D" id="%s"]' % sub_id)
            subs.append("radius = %s" % _gd_literal(shape.get("radius", 16)))
        subs.append("")
        mapping[node["name"]] = sub_id
    return subs, mapping


def build_tscn(blueprint: dict, templates: dict, features_dir: str) -> str:
    """生成 .tscn 文本。blueprint 为 normalize_scene_blueprint 的输出。"""
    ext_resources = []   # (res_id, res_path, kind)  kind: PackedScene|Script
    body = []

    root = blueprint.get("root_extra") or {}
    root_scene = str(root.get("scene") or "").strip()

    # 根节点：复用既有场景（实例化）或新建类型节点
    if root_scene:
        res_id = "1_root_scene"
        ext_resources.append((res_id, root_scene, "PackedScene"))
        body.append('[node name="%s" instance=ExtResource("%s")]' % (blueprint["root_name"], res_id))
        is_root_instance = True
    else:
        is_root_instance = False
        body.append('[node name="%s" type="%s"]' % (blueprint["root_name"], blueprint["root_type"]))

    # 根属性覆写 / 加组：instance 节点覆写必须在 [node] header 同行追加
    # （groups=[..] 是节点属性，不能写在 instance 行之后的下一行——Godot 会丢弃）。
    # 普通 type 根沿用正常属性行。
    groups = [str(g).strip() for g in (root.get("groups") or []) if str(g).strip()]
    if root_scene:
        parts = ["groups = [%s]" % ", ".join('"%s"' % g for g in groups)] if groups else []
        for key, value in (root.get("properties") or {}).items():
            parts.append("%s = %s" % (key, _gd_literal(value)))
        if parts:
            body[-1] = body[-1][:-1] + " " + " ".join(parts) + "]"
        body.append("")
    else:
        for key, value in (root.get("properties") or {}).items():
            body.append("%s = %s" % (key, _gd_literal(value)))
        if groups:
            body.append("groups = [%s]" % ", ".join('"%s"' % g for g in groups))
        if (root.get("properties") or {}) or groups:
            body.append("")

    # 组件实例（Feature Scene Template -> PackedScene instance）
    next_res = 2 if is_root_instance else 1
    for fid in blueprint["features"]:
        template = templates.get(fid) or {}
        res_path = template_scene_path(fid, template, features_dir)
        res_id = "%d_%s" % (next_res, fid)
        next_res += 1
        ext_resources.append((res_id, res_path, "PackedScene"))
        node_name = template_node_name(fid, template)
        body.append('[node name="%s" parent="." instance=ExtResource("%s")]' % (node_name, res_id))
        body.append("")

    # 额外结构节点（含 shape 子资源；parent 可指向组件节点名，嵌套其下）
    extra_nodes = list(blueprint["extra_nodes"])
    subs, _shape_map = _shape_subresources(extra_nodes)
    for node in extra_nodes:
        parent = str(node.get("parent") or "").strip() or "."
        lines = ['[node name="%s" type="%s" parent="%s"]' % (node["name"], node["type"], parent)]
        if "_sub_id" in node:
            lines.append('shape = SubResource("%s")' % node["_sub_id"])
        body.extend(lines)
        body.append("")

    # 头部（load_steps = 1 + ext_resource 数 + sub_resource 数）
    lines = []
    load_steps = 1 + len(ext_resources) + sum(1 for s in subs if s.startswith("[sub_resource"))
    lines.append("[gd_scene load_steps=%d format=3]" % load_steps)
    lines.append("")
    for res_id, res_path, kind in ext_resources:
        lines.append('[ext_resource type="%s" path="%s" id="%s"]' % (kind, res_path, res_id))
    if ext_resources:
        lines.append("")
    lines.extend(subs)
    lines.extend(body)
    return "\n".join(lines).rstrip("\n") + "\n"


def scene_file_path(blueprint: dict, out_dir: str) -> str:
    """输出路径：Scenes/<RootName>.tscn。"""
    return os.path.join(out_dir, blueprint["root_name"] + ".tscn")


def write_scene(blueprint: dict, templates: dict, features_dir: str, out_dir: str) -> str:
    """生成并写入 .tscn，返回输出路径。"""
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    path = scene_file_path(blueprint, out_dir)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_tscn(blueprint, templates, features_dir))
    return path
