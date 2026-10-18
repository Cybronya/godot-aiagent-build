#!/usr/bin/env python3
"""Scene Builder

由 **Scene Intent** 生成 Godot .tscn（format=3）文本。

输入边界（Phase 1.8.7）：唯一合法输入是 Scene Intent（`SceneIntent` 对象或契约文档
mapping）；旧规整内部 dict 被拒绝（无隐藏转换、无兼容适配器）。原始 Blueprint →
Scene Intent 的转换只发生在 CLI 入口（scene_intent.intent_from_blueprint）。

生成规则（见 .ai/context/scene_schema.yaml 与 scene_composer_schema.yaml）：
    - 根节点：[node name="<root.name>" type="<root.type>"]
      * Intent root.scene：复用既有 PackedScene 作根（实例化而非新建）
      * Intent root.properties：属性覆写（motion_mode 等，值按 GDScript 字面量输出）
      * Intent root.groups：加入节点组（玩家/敌人分组契约）
    - 组件：  [node name="<NodeName>" parent="." instance=ExtResource("<id>")]
              每个组件经 Feature Scene Template 解析到 Feature 入口场景。
              入口场景与 root.scene 相同的组件（实体根即该组件，Phase 1.11）不再作为
              子节点实例化；组件仍是组合成员（能力/依赖/回归测试照旧）。
    - 额外节点：Intent nodes[]（[node name="<Name>" type="<Type>" parent="."]）
      * node.shape: {type: rectangle|circle, size|radius} 生成 sub_resource
        并挂 shape 属性（ContactDamage/拾取范围等需要 CollisionShape2D）。
      * 生成期派生值（sub_resource id 等）**不写回** Scene Intent（文档只读）。
    - 资源节点：Intent resources[]（由 Asset Binding 经 asset_nodes.py 产出）
      * 形如 [node name="SlimeIdleAnim" type="AnimatedSprite2D" parent="."]
        sprite_frames = ExtResource("...")
      * ext_resource 的类型由 path 经 asset_nodes.resource_ext_type 派生（Intent 不携带
        构建期派生的 ext_type）。
      * 只连接资源（sprite_frames / texture / stream），不写脚本、不建状态。
    - 根节点不写脚本：Scene 只负责组合（架构约束）——根行为由组件承担，
      或复用既有场景时由其自身脚本承担。
    - components[].instance（Phase 1.8.14）是**声明式证据**，不是生成指令：它不改变
      本节任何生成结果（能力契约核对归 capability_contract_validator / artifact 层）。
"""

import os

import asset_nodes

from scene_intent import intent_components, intent_document, intent_root
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
    """收集节点 shape 声明 -> (sub_resource 文本行, {node_name: sub_id})。

    只读投影：不在节点上写 `_sub_id` 之类的构建期私有键（Scene Intent 文档保持纯净）。
    """
    subs, mapping = [], {}
    for node in nodes:
        shape = node.get("shape") or {}
        stype = str(shape.get("type") or "").strip().lower()
        if not stype:
            continue
        if stype not in _SHAPE_TYPES:
            raise ValueError("Unsupported shape type: %s" % stype)
        sub_id = "%s_%s_%d" % (_SHAPE_TYPES[stype], node["name"], len(mapping) + 1)
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


def build_tscn(scene_intent, templates: dict, features_dir: str) -> str:
    """生成 .tscn 文本。scene_intent 为 SceneIntent 或其契约文档 mapping。"""
    document = intent_document(scene_intent, "scene_builder.build_tscn")
    root = intent_root(document)
    features = intent_components(document)
    nodes = [node for node in (document.get("nodes") or []) if isinstance(node, dict)]
    resources = [entry for entry in (document.get("resources") or []) if isinstance(entry, dict)]

    ext_resources = []   # (res_id, res_path, kind)  kind: PackedScene|Script|<资源类型>
    body = []

    root_name = str(root.get("name") or "")
    root_type = str(root.get("type") or "")
    root_scene = str(root.get("scene") or "").strip()

    # 根节点：复用既有场景（实例化）或新建类型节点
    if root_scene:
        res_id = "1_root_scene"
        ext_resources.append((res_id, root_scene, "PackedScene"))
        body.append('[node name="%s" instance=ExtResource("%s")]' % (root_name, res_id))
        is_root_instance = True
    else:
        is_root_instance = False
        body.append('[node name="%s" type="%s"]' % (root_name, root_type))

    # 根属性覆写 / 加组：instance 节点覆写必须在 [node] header 同行追加
    # （groups=[..] 是节点属性，不能写在 instance 行之后的下一行——Godot 会丢弃）。
    # 普通 type 根沿用正常属性行。
    groups = [str(g).strip() for g in (root.get("groups") or []) if str(g).strip()]
    properties = root.get("properties") if isinstance(root.get("properties"), dict) else {}
    if root_scene:
        parts = ["groups = [%s]" % ", ".join('"%s"' % g for g in groups)] if groups else []
        for key, value in properties.items():
            parts.append("%s = %s" % (key, _gd_literal(value)))
        if parts:
            body[-1] = body[-1][:-1] + " " + " ".join(parts) + "]"
        body.append("")
    else:
        for key, value in properties.items():
            body.append("%s = %s" % (key, _gd_literal(value)))
        if groups:
            body.append("groups = [%s]" % ", ".join('"%s"' % g for g in groups))
        if properties or groups:
            body.append("")

    # 组件实例（Feature Scene Template -> PackedScene instance）
    # 根实例组件（Phase 1.11）：入口场景与 root.scene 相同的组件**不**作为子节点实例化 ——
    # 它的场景就是实体根本身（重复实例化会得到第二个同名行为组件，产生双重移动）。
    # 判定依据是 Intent 的 root.scene 与模板派生出的入口场景路径（构建期派生，不得命名猜测）。
    next_res = 2 if is_root_instance else 1
    for fid in features:
        template = templates.get(fid) or {}
        res_path = template_scene_path(fid, template, features_dir)
        if root_scene and res_path == root_scene:
            continue
        res_id = "%d_%s" % (next_res, fid)
        next_res += 1
        ext_resources.append((res_id, res_path, "PackedScene"))
        node_name = template_node_name(fid, template)
        body.append('[node name="%s" parent="." instance=ExtResource("%s")]' % (node_name, res_id))
        body.append("")

    # 额外结构节点（含 shape 子资源；parent 可指向组件节点名，嵌套其下）
    subs, shape_map = _shape_subresources(nodes)
    for node in nodes:
        parent = str(node.get("parent") or "").strip() or "."
        lines = ['[node name="%s" type="%s" parent="%s"]'
                 % (node.get("name") or node.get("type"), node.get("type"), parent)]
        sub_id = shape_map.get(node.get("name"))
        if sub_id:
            lines.append('shape = SubResource("%s")' % sub_id)
        body.extend(lines)
        body.append("")

    # 资源节点（Asset Binding -> AnimatedSprite2D / Sprite2D / AudioStreamPlayer）
    # 只做实例化与资源连接，不添加任何行为/状态（Scene 只负责组合）。
    for node in resources:
        res_id = "%d_asset_%s" % (next_res, node["name"])
        next_res += 1
        ext_resources.append((res_id, node["path"], asset_nodes.resource_ext_type(node["path"])))
        parent = str(node.get("parent") or "").strip() or "."
        body.append('[node name="%s" type="%s" parent="%s"]'
                    % (node["name"], node["type"], parent))
        body.append('%s = ExtResource("%s")' % (node["property"], res_id))
        for key in ("hframes", "vframes"):
            if node.get(key):
                body.append("%s = %d" % (key, int(node[key])))
        # 主 animation 只作为默认展示（如 AnimatedSprite2D 的 "idle"）；
        # 具体播放哪一段属于 Gameplay，Scene 不写行为。
        if node.get("animation"):
            body.append('animation = &"%s"' % str(node["animation"]).replace('"', ""))
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


def scene_file_path(scene_intent, out_dir: str) -> str:
    """输出路径：Scenes/<root.name>.tscn。"""
    document = intent_document(scene_intent, "scene_builder.scene_file_path")
    return os.path.join(out_dir, str(intent_root(document).get("name") or "") + ".tscn")


def write_scene(scene_intent, templates: dict, features_dir: str, out_dir: str) -> str:
    """生成并写入 .tscn，返回输出路径。"""
    document = intent_document(scene_intent, "scene_builder.write_scene")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    path = os.path.join(out_dir, str(intent_root(document).get("name") or "") + ".tscn")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_tscn(scene_intent, templates, features_dir))
    return path
