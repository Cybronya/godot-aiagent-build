#!/usr/bin/env python3
"""Feature Scene Template Loader

加载 Features/*/template.yaml（Feature Scene Template），并提供
Entity Blueprint -> Scene Blueprint 的推导。

template.yaml 格式见 .ai/context/scene_schema.yaml 的
「Feature Scene Template」节。

Phase 1.8.11：规整 Scene Blueprint 时汇总**能力声明**（capability transport）：
Blueprint 自带的 capabilities.required + 成员 Feature 的声明（Features/<id>/feature.yaml）
→ normalized["capabilities"]。本层只传递与去重，**不判断能力是否被支持**（归 compatibility_gate）。

Phase 1.8.14：同样汇总**组件实例计划**（component instance transport）：
Blueprint.components[].instance 或成员 Feature template.yaml 的 instance: 块 → normalized["component_instances"]。
本层只传递（不做词表校验，归 component_instance_resolver）；未声明 → 不产出（旧行为不变）。
"""

import os

import yaml

import feature_capabilities

# 目录定位：本文件位于 <root>/.ai/tools/scene_composer/ 下
_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
FEATURES_DIR = os.path.join(PROJECT_ROOT, "Features")
INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")


def display_path(path: str, base: str = PROJECT_ROOT) -> str:
    """人类可读的展示路径：相对 base，跨盘符时退回绝对路径（正斜杠）。

    os.path.relpath 在 Windows 上当 path 与 base 位于不同盘符时抛 ValueError
    （例如 --bindings / --out / --tests 指向另一块盘上的文件）。展示路径只是日志，
    不得让一次成功的生成以 traceback + 非 0 退出码结束，因此这里显式降级。
    场景层唯一实现（scene_composer.py 与 test_generator 共用，不复制第二份）。
    """
    try:
        return os.path.relpath(str(path), str(base)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


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


def template_root_instance(feature_id: str, template: dict) -> bool:
    """Feature 是否声明「入口场景即宿主实体根」（attach.root_instance，Phase 1.11）。

    语义：该组件以根实例（instance=ExtResource）加入实体，**不得**再作为子节点实例化。
    Feature 自己声明用法（如 chase_movement 的脚本必须作为实体根脚本运行），
    因此这是 Feature 元数据，不是蓝图侧猜测。
    """
    attach = (template or {}).get("attach")
    if not isinstance(attach, dict):
        return False
    return bool(attach.get("root_instance"))


def template_root_type(feature_id: str, template: dict) -> str:
    """模板声明的宿主根类型要求（scene.root_type）；未声明返回 ""。"""
    return str(((template or {}).get("scene") or {}).get("root_type") or "").strip()


def template_attach_nodes(feature_id: str, template: dict) -> list:
    """Feature 在宿主场景中需要的结构节点声明（attach.nodes，Phase 1.11）。

    返回 [{"type", "name", "parent", "shape"?}]，其中 parent 取自组件实例节点名
    （template_node_name）——语义是「挂在本组件节点下」；组件为根实例时
    template_node_name 即根节点名，由调用方决定改成根路径。
    只做字段读取与形态过滤：非 mapping / 缺 type 的条目被忽略（旧模板零声明不变）。
    """
    attach = (template or {}).get("attach")
    if not isinstance(attach, dict):
        return []
    nodes = []
    for entry in attach.get("nodes") or []:
        if isinstance(entry, str) and entry.strip():
            nodes.append({"type": entry.strip(), "name": entry.strip()})
            continue
        if not isinstance(entry, dict):
            continue
        ntype = str(entry.get("type") or "").strip()
        if not ntype:
            continue
        node = {"type": ntype, "name": str(entry.get("name") or "").strip() or ntype}
        if isinstance(entry.get("shape"), dict):
            node["shape"] = dict(entry["shape"])
        if isinstance(entry.get("properties"), dict):
            node["properties"] = dict(entry["properties"])
        nodes.append(node)
    return nodes


def pascal_case(name: str) -> str:
    return _pascal_case(name)


def _pascal_case(name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in str(name).replace("-", "_").split("_") if part)


def derive_scene_blueprint(entity_blueprint: dict, features_dir: str = FEATURES_DIR) -> dict:
    """Entity Blueprint（entity:/features:）-> Scene Blueprint（scene:/root:/components:）。

    已是 Scene Blueprint（含 root: 与 components:）的原样返回（作者显式声明的
    实例化计划不被推导覆盖）。

    Phase 1.11 推导补充（仍只发生在 Entity Blueprint 路径）：
        - 成员 Feature 声明 attach.root_instance: true 时 → root.scene = 该 Feature
          入口场景（实体根即该组件实例，不再作为子节点）；
        - 成员 Feature 声明 attach.nodes 时 → 追加到 nodes[]（本组件下需要的碰撞形状等），
          作者显式声明的同名节点优先。
    """
    if "components" in entity_blueprint or "root" in entity_blueprint:
        return entity_blueprint

    entity = entity_blueprint.get("entity") or {}
    features = list(entity_blueprint.get("features") or [])
    scene_id = entity.get("id") or entity_blueprint.get("id") or "basic_entity"
    role = entity.get("role") or "entity"

    templates = load_templates(features, features_dir)
    root_required = template_root_requirements(templates)
    if root_required:
        # 多个不同要求时取「最强」者（CharacterBody2D 优先，保证成员可用）
        root_type = "CharacterBody2D" if "CharacterBody2D" in root_required else sorted(root_required)[0]
    else:
        root_type = ROLE_DEFAULT_ROOT.get(role, "Node2D")

    root = {"type": root_type, "name": _pascal_case(scene_id)}
    # Phase 1.11：成员 Feature 声明「入口场景即实体根」（attach.root_instance）时，
    # 实体根**就是**该 Feature 的入口场景（实例化为根），而不是一个裸类型节点 +
    # 该组件作为子节点 —— 后者会让根脚本（如 chase_movement.gd）只移动子节点，
    # 实体根原地不动，玩法语义失真。多个成员同时声明 → 不猜测，报冲突。
    root_features = [fid for fid in features if template_root_instance(fid, templates.get(fid) or {})]
    if len(root_features) == 1:
        fid = root_features[0]
        root["scene"] = template_scene_path(fid, templates.get(fid) or {}, features_dir)
        declared_root = template_root_type(fid, templates.get(fid) or {})
        if declared_root:
            root["type"] = declared_root

    derived = {
        "scene": {"id": scene_id},
        "root": root,
        "components": [{"feature": fid} for fid in features],
        "validation": entity_blueprint.get("validation")
        or {"required_tests": list(features)},
    }
    # 成员模板声明的结构节点（attach.nodes）→ 实体蓝图的 nodes[]：本组件下需要的
    # 碰撞形状等。作者在 Entity Blueprint 里显式声明的同名节点优先（不覆盖、不重名）。
    derived_nodes = _derived_attach_nodes(features, templates, root_features, features_dir,
                                          entity_blueprint.get("nodes"))
    if derived_nodes:
        derived["nodes"] = derived_nodes
    # 能力声明是「中转键」：Entity Blueprint 上显式写出时不得被推导静默丢弃
    # （成员 Feature 的声明由 normalize_scene_blueprint 汇总，不在此处读取）。
    if entity_blueprint.get("capabilities") is not None:
        derived["capabilities"] = entity_blueprint["capabilities"]
    if len(root_features) > 1:
        # 交给 normalize 报错（本函数没有错误通道），禁止静默二选一。
        derived["root_instance_conflict"] = list(root_features)
    return derived


def _derived_attach_nodes(features: list, templates: dict, root_features: list,
                          features_dir: str, declared_nodes) -> list:
    """Entity Blueprint → Scene Blueprint 时展开成员模板声明的结构节点。

    规则：
        - 作者显式声明的 nodes 原样保留在最前（同 (parent, name) 的模板节点不重复产出）；
        - 模板节点挂在本组件实例节点下；组件为根实例时挂在实体根下（parent="."）。
    """
    nodes = []
    seen = set()
    for entry in declared_nodes or []:
        if not isinstance(entry, dict):
            continue
        ntype = str(entry.get("type") or "").strip()
        if not ntype:
            continue
        node = {"type": ntype, "name": str(entry.get("name") or "").strip() or ntype}
        parent = str(entry.get("parent") or "").strip()
        if parent:
            node["parent"] = parent
        if isinstance(entry.get("shape"), dict):
            node["shape"] = dict(entry["shape"])
        nodes.append(node)
        seen.add((parent or ".", node["name"]))

    for fid in features:
        template = templates.get(fid) or {}
        for entry in template_attach_nodes(fid, template):
            parent = "." if fid in root_features else template_node_name(fid, template)
            if (parent, entry["name"]) in seen:
                continue                      # 作者显式声明优先
            node = dict(entry)
            node["parent"] = parent
            nodes.append(node)
            seen.add((parent, entry["name"]))
    return nodes


def feature_instance_plan(feature_id: str, features_dir: str = FEATURES_DIR) -> dict:
    """Feature Scene Template 的可选 `instance:` 块（Phase 1.8.14 实例计划声明）。

    只读一层声明，不做词表校验（归 component_instance_resolver）；
    缺失 / 不可解析 / 非 mapping → {}（旧 Feature 零声明，继续合法）。
    """
    path = os.path.join(features_dir, str(feature_id), "template.yaml")
    if not os.path.isfile(path):
        return {}
    try:
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    instance = data.get("instance")
    return dict(instance) if isinstance(instance, dict) else {}


def normalize_scene_blueprint(bp: dict, features_dir: str = FEATURES_DIR) -> tuple:
    """规整 Scene Blueprint，返回 (normalized, errors)。

    normalized 字段：
        scene_id / root_type / root_name / features(list) /
        extra_nodes(list of {type,name}) / required_tests(list) / capabilities（能力声明）/
        component_instances（组件实例计划声明，Phase 1.8.14）

    features_dir —— 读取成员 Feature 能力声明 / 实例计划的基准目录（默认项目 Features/）。
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
    conflict = bp.get("root_instance_conflict")
    if conflict:
        errors.append("Root instance conflict: %s all declare attach.root_instance "
                      "(exactly one member Feature may be the entity root)"
                      % ", ".join(sorted(str(fid) for fid in conflict)))
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

    # 能力声明（Phase 1.8.11）：成员 Feature 的声明（Features/<id>/feature.yaml）与本键
    # 自带的声明取并集（保序去重）——只承载与传递，不判断能力是否被支持（归 compatibility_gate）。
    required = []
    for name in feature_capabilities.capabilities_for_features(features, features_dir):
        if name not in required:
            required.append(name)
    declared = bp.get("capabilities")
    if declared is not None:
        for name in feature_capabilities.normalize_required(declared):
            if name not in required:
                required.append(name)

    # 组件实例计划（Phase 1.8.14）：Blueprint 显式声明优先，其次成员 Feature template.yaml
    # 的 instance: 块；两者都无 → 不产出（旧行为：components[] 只有 component 键）。
    # Blueprint 显式声明（任何非 None 值都算「已声明」——非法形态由 resolver 报错，
    # 不在此处静默丢弃）；template.yaml 是可选作者元数据，非 mapping / 空 → 视为未声明。
    component_instances = {}
    explicit_instances = {}
    for entry in components or []:
        if isinstance(entry, dict):
            feature_id = str(entry.get("feature") or "").strip()
            instance = entry.get("instance")
            if feature_id and instance is not None:
                explicit_instances[feature_id] = instance
    for feature_id in features:
        instance = explicit_instances.get(feature_id)
        if instance is None:
            instance = feature_instance_plan(feature_id, features_dir) or None
        if instance is not None:
            component_instances[feature_id] = instance

    normalized = {
        "scene_id": scene_id,
        "root_type": root_type,
        "root_name": root_name,
        "features": features,
        "extra_nodes": extra_nodes,
        "required_tests": required_tests,
        "root_extra": root_extra,
        "capabilities": {"required": required},
        "component_instances": component_instances,
    }
    return normalized, errors
