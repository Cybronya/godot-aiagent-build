#!/usr/bin/env python3
"""Component Instance Ownership (Phase 1.8.17) —— 组件声明 → 产物实例节点的唯一映射。

链路位置（四层职责，禁止合并）：

    Capability          「需要什么」     capability_contracts / capability_registry
    Instance            「声明什么」     component_instance_resolver（components[].instance）
    Ownership           「哪个实例」     component_instance_ownership（本模块）
    Artifact Evidence   「产物是否兑现」 artifact_evidence_validator（Host + External Artifact）

    components[].instance（声明）
        ↓  resolve_component_ownership（本模块：只读 + 唯一映射，不猜测）
    owners[]（component → artifact_path / node_path / confidence）
        ↓  artifact_evidence_validator（按归属限定证据池）
    Artifact Evidence（PASS / BLOCKED）

输入（只允许两者）：
    scene_intent      —— Scene Intent（`SceneIntent` 对象或契约文档 mapping）；原始 Blueprint /
                         旧规整内部 dict 一律 ValueError（与生成链其余部分同一输入边界）。
    artifact_evidence —— **宿主产物**的静态解析结果（`artifact_evidence_validator.parse_artifact`
                         / `external_artifact_resolver.parse_scene_text` 的输出：
                         `{root_name, nodes, ext_resources}`；节点带 instance / instance_ref）。

所有权来源（严格的三条，按优先级；见契约 component_instance_ownership.ownership_source）：
    1. `components[].instance.id` —— 声明方给出的**节点身份**（节点名或节点全路径）
    2. ext_resource path —— `res://Features/<component>/<Scene>.tscn`
    3. 节点 `instance=ExtResource("<ref>")` 与 ext_resource 表的 id ↔ path 关联

本模块 MUST NOT：
    - 按节点名字猜测（如 component `enemy_damage` 去匹配节点 `DamageNode`）
    - 按关键词推断（damage / sprite / health …）
    - 读 Feature Registry / Feature 数据 / Capability Registry / Binding
    - 启动 Godot、加载 PackedScene、解析运行时节点、写文件

无法唯一确定（声明 id 找不到 / 声明 id 命中多个 / 无 id 但有多个候选）→
    BLOCKED \"Component ownership unresolved: <component>\"（不猜测、不降级放行）
无 id 且候选唯一 → 允许 fallback（confidence: resolved）
无候选（产物里没有该组件的实例节点）→ owner = 宿主产物本身（host-only，node_path = \"\"；
    此时证据只来自宿主，不借用其它外部场景）

契约：.ai/context/scene_composer_schema.yaml#component_instance_ownership
"""

from scene_intent import intent_component_instances, intent_document

import external_artifact_resolver

OWNERSHIP_VERSION = 1
STATUS_PASS = "PASS"
STATUS_BLOCKED = "BLOCKED"

CONFIDENCE_DECLARED = "declared"     # 由声明 id 选定
CONFIDENCE_RESOLVED = "resolved"     # 由唯一 ext_resource 候选 / host-only 回退选定


def _node_identity(node: dict) -> tuple:
    """节点的可比身份：节点名 与 节点全路径（声明 id 匹配用，不做模糊/大小写猜测）。"""
    return (str(node.get("name") or "").strip(), str(node.get("path") or "").strip())


def _ext_path_by_ref(artifact_evidence: dict) -> dict:
    """宿主 ext_resource 表 -> {ref id: res:// path}。"""
    return {str(entry.get("id") or ""): str(entry.get("path") or "")
            for entry in (artifact_evidence.get("ext_resources") or [])}


def _instance_nodes(artifact_evidence: dict) -> list:
    """宿主的实例节点（`instance=ExtResource(...)`）。"""
    return [node for node in (artifact_evidence.get("nodes") or []) if node.get("instance")]


def _owner_entry(component: str, artifact_path: str, node_path: str, confidence: str) -> dict:
    return {"component": component, "artifact_path": artifact_path, "node_path": node_path,
            "confidence": confidence}


def _owner_for(component: str, declared_id: str, host: dict, host_path: str,
               ref_paths: dict) -> tuple:
    """单条声明 -> (owner|None, errors)。"""
    instance_nodes = _instance_nodes(host)

    # 1) 声明 id：必须能在宿主产物中唯一找到（节点名或节点全路径），否则 unresolved。
    if declared_id:
        matches = [node for node in (host.get("nodes") or [])
                   if declared_id in _node_identity(node)]
        if len(matches) == 1:
            node = matches[0]
            external = ref_paths.get(str(node.get("instance_ref") or ""), "")
            return _owner_entry(component, external or host_path, node["path"],
                                CONFIDENCE_DECLARED), []
        return None, ["Component ownership unresolved: %s" % component]

    # 2) + 3) ext_resource path（Features/<component>/）+ 节点 ExtResource 引用
    candidates = [node for node in instance_nodes
                  if external_artifact_resolver.feature_id_of(
                      ref_paths.get(str(node.get("instance_ref") or ""), "")) == component]
    if len(candidates) == 1:
        node = candidates[0]
        external = ref_paths.get(str(node.get("instance_ref") or ""), "")
        return _owner_entry(component, external, node["path"], CONFIDENCE_RESOLVED), []
    if len(candidates) > 1:
        # 同一 Feature 多实例且没有声明 id → 无法唯一确定（禁止猜测）
        return None, ["Component ownership unresolved: %s" % component]

    # 无候选：产物里没有该组件的实例节点 → 宿主自有证据（不借用无关外部场景）
    return _owner_entry(component, host_path, "", CONFIDENCE_RESOLVED), []


def resolve_component_ownership(scene_intent, artifact_evidence) -> dict:
    """Scene Intent（声明）+ 宿主产物解析结果 -> {"status", "owners", "errors"}。

    按 components[] 声明顺序，逐条给出唯一 owner：
        instance.id 命中唯一节点        -> confidence \"declared\"
        唯一 ext_resource 候选          -> confidence \"resolved\"
        无候选（宿主自有证据）          -> confidence \"resolved\"，node_path = \"\"
        id 找不到 / id 命中多个 / 多候选 -> BLOCKED \"Component ownership unresolved: <component>\"

    只做映射；不判断能力、不判断产物是否兑现、不读文件。
    """
    document = intent_document(scene_intent,
                               "component_instance_ownership.resolve_component_ownership")
    if not isinstance(artifact_evidence, dict):
        raise ValueError("component_instance_ownership expects the parsed host artifact mapping, "
                         "got %s" % type(artifact_evidence).__name__)

    host_path = str(artifact_evidence.get("scene_path") or "")
    ref_paths = _ext_path_by_ref(artifact_evidence)
    owners, errors = [], []
    for entry in intent_component_instances(document):
        instance = entry["instance"]
        if not isinstance(instance, dict) or not str(instance.get("node_type") or "").strip():
            # 缺失 / 未知 node_type 归 Capability Contract 层（Builder 之前已拦截）；本层不重复判定。
            continue
        declared_id = str(instance.get("id") or "").strip()
        owner, owner_errors = _owner_for(entry["component"], declared_id, artifact_evidence,
                                         host_path, ref_paths)
        if owner is not None:
            owners.append(owner)
        errors.extend(owner_errors)

    status = STATUS_BLOCKED if errors else STATUS_PASS
    return {"status": status, "owners": owners, "errors": errors}


def main(argv=None) -> int:  # pragma: no cover - 诊断入口（只读，无副作用）
    """打印所有权解析器版本与来源优先级。"""
    print("Component Instance Ownership v%d" % OWNERSHIP_VERSION)
    print("ownership sources: instance.id -> ext_resource path -> node instance=ExtResource()")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
