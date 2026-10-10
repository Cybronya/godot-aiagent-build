#!/usr/bin/env python3
"""Feature Scene Template Loader

加载 Features/*/template.yaml（Feature Scene Template），并提供
Entity Blueprint -> Scene Blueprint 的推导。

template.yaml 格式见 .ai/context/scene_schema.yaml 的
「Feature Scene Template」节。
"""

import os

import yaml

# 目录定位：本文件位于 <root>/.ai/tools/scene_composer/ 下
_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
FEATURES_DIR = os.path.join(PROJECT_ROOT, "Features")
INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")

# 角色缺省根类型（组合成员未声明 root_type 要求时使用）
ROLE_DEFAULT_ROOT = {"enemy": "CharacterBody2D", "player": "CharacterBody2D"}


def load_template(feature_id: str, features_dir: str = FEATURES_DIR) -> dict:
    """加载单个 Feature Scene Template；不存在返回 {}。"""
    path = os.path.join(features_dir, feature_id, "template.yaml")
    if not os.path.isfile(path):
        return {}
    data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def load_templates(feature_ids, features_dir: str = FEATURES_DIR) -> dict:
    """批量加载模板，返回 {feature_id: template}。"""
    return {fid: load_template(fid, features_dir) for fid in feature_ids}


def template_scene_path(feature_id: str, template: dict, features_dir: str = FEATURES_DIR) -> str:
    """Feature 入口场景的 res:// 路径；无模板时退回 feature.yaml 的 entry_scene，
    再退回 <Pascal>.tscn 约定。"""
    source = ((template.get("scene") or {}).get("source") or "").replace("\\", "/")
    if source:
        return "res://Features/%s/%s" % (feature_id, source)
    entry = ""
    meta_path = os.path.join(features_dir, feature_id, "feature.yaml")
    if os.path.isfile(meta_path):
        meta = yaml.safe_load(open(meta_path, encoding="utf-8")) or {}
        entry = str(((meta.get("composition") or {}).get("entry_scene") or "")).replace("\\", "/")
    if not entry:
        entry = _pascal_case(feature_id) + ".tscn"
    return "res://Features/%s/%s" % (feature_id, entry)


def template_node_name(feature_id: str, template: dict) -> str:
    """组件实例节点名：required_nodes 第一项，缺省为 feature id 的 PascalCase。"""
    required = ((template.get("validation") or {}).get("required_nodes") or [])
    if required and isinstance(required[0], str) and required[0].strip():
        return required[0].strip()
    return _pascal_case(feature_id)


def template_signals(template: dict) -> list:
    return list(((template.get("interfaces") or {}).get("signals") or []))


def template_root_requirements(templates: dict) -> set:
    """收集组合内所有 Feature 声明的根类型要求。"""
    required = set()
    for template in templates.values():
        rt = ((template.get("scene") or {}).get("root_type") or "").strip()
        if rt:
            required.add(rt)
    return required


def pascal_case(name: str) -> str:
    return _pascal_case(name)


def _pascal_case(name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in str(name).replace("-", "_").split("_") if part)


def derive_scene_blueprint(entity_blueprint: dict) -> dict:
    """Entity Blueprint（entity:/features:）-> Scene Blueprint（scene:/root:/components:）。

    已是 Scene Blueprint（含 root: 与 components:）的原样返回。
    """
    if "components" in entity_blueprint or "root" in entity_blueprint:
        return entity_blueprint

    entity = entity_blueprint.get("entity") or {}
    features = list(entity_blueprint.get("features") or [])
    scene_id = entity.get("id") or entity_blueprint.get("id") or "basic_entity"
    role = entity.get("role") or "entity"

    templates = load_templates(features)
    root_required = template_root_requirements(templates)
    if root_required:
        # 多个不同要求时取「最强」者（CharacterBody2D 优先，保证成员可用）
        root_type = "CharacterBody2D" if "CharacterBody2D" in root_required else sorted(root_required)[0]
    else:
        root_type = ROLE_DEFAULT_ROOT.get(role, "Node2D")

    return {
        "scene": {"id": scene_id},
        "root": {"type": root_type, "name": _pascal_case(scene_id)},
        "components": [{"feature": fid} for fid in features],
        "validation": entity_blueprint.get("validation")
        or {"required_tests": list(features)},
    }


def normalize_scene_blueprint(bp: dict) -> tuple:
    """规整 Scene Blueprint，返回 (normalized, errors)。

    normalized 字段：
        scene_id / root_type / root_name / features(list) /
        extra_nodes(list of {type,name}) / required_tests(list)
    """
    errors = []
    if not isinstance(bp, dict):
        return {}, ["Scene Blueprint must be a mapping"]

    scene = bp.get("scene") or {}
    root = bp.get("root") or {}
    scene_id = str(scene.get("id") or "").strip() if isinstance(scene, dict) else ""
    root_type = str(root.get("type") or "").strip() if isinstance(root, dict) else ""
    root_name = str(root.get("name") or "").strip() if isinstance(root, dict) else ""

    components = bp.get("components")
    if components is None:
        features = [str(f).strip() for f in (bp.get("features") or []) if str(f).strip()]
    else:
        features = []
        for entry in components or []:
            if isinstance(entry, dict) and str(entry.get("feature") or "").strip():
                features.append(str(entry["feature"]).strip())
            else:
                errors.append("Invalid component entry: %r (expected {feature: <id>})" % (entry,))

    # 根为复用场景（root.scene）时允许省略 type 且允许零组件（场景自带组合）
    reusing_scene = bool(str((root.get("scene") if isinstance(root, dict) else "") or "").strip())
    if not root_type and not reusing_scene:
        errors.append("Scene Blueprint missing root.type")
    if not features and not reusing_scene:
        errors.append("Scene Blueprint has no components (features)")
    if not root_name:
        root_name = _pascal_case(scene_id or "entity")
    if not scene_id:
        scene_id = root_name.lower() if root_name else "entity"

    extra_nodes = []
    for node in bp.get("nodes") or []:
        if isinstance(node, dict) and str(node.get("type") or "").strip():
            ntype = str(node["type"]).strip()
            entry = {"type": ntype, "name": str(node.get("name") or "").strip() or ntype}
            parent = str(node.get("parent") or "").strip()
            if parent:
                entry["parent"] = parent
            if isinstance(node.get("shape"), dict):
                entry["shape"] = node["shape"]
            extra_nodes.append(entry)
        elif isinstance(node, str) and node.strip():
            extra_nodes.append({"type": node.strip(), "name": node.strip()})
        else:
            errors.append("Invalid node entry: %r" % (node,))

    # 根扩展字段（scene 复用 / 属性覆写 / 组）：原样下发给 scene_builder
    root_extra = {}
    if reusing_scene:
        root_extra["scene"] = str(root.get("scene")).strip()
    if isinstance(root.get("properties"), dict):
        root_extra["properties"] = dict(root["properties"])
    if isinstance(root.get("groups"), list):
        root_extra["groups"] = [str(g) for g in root["groups"]]

    validation = bp.get("validation") or {}
    required_tests = [str(t).strip() for t in (validation.get("required_tests") or []) if str(t).strip()]
    if not required_tests:
        required_tests = list(features)

    normalized = {
        "scene_id": scene_id,
        "root_type": root_type,
        "root_name": root_name,
        "features": features,
        "extra_nodes": extra_nodes,
        "required_tests": required_tests,
        "root_extra": root_extra,
    }
    return normalized, errors
