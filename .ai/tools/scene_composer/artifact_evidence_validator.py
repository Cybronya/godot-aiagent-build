#!/usr/bin/env python3
"""Artifact Evidence Validator (Phase 1.8.15 / 1.8.16 / 1.8.17) —— 声明 = 计划 = 生成物 的静态核验。

链路位置（生成**之后**，只读核验，不改变任何生成行为）：

    Feature
        ↓
    Scene Intent（components[].instance = 声明）
        ↓  compatibility_gate（能力是否被支持）
        ↓  capability_contract_validator（计划是否满足能力要求）
    Scene Builder
        ↓  Host .tscn（生成物）
        ↓  verify_artifact_evidence（本模块）
            证据 = Host Artifact + External Component Artifact（1.8.16）
    Artifact Evidence Report（PASS / BLOCKED）

Complete Artifact Evidence（Phase 1.8.16）：

    Host .tscn
        |  ext_resource type="PackedScene" path="res://Features/<id>/<Scene>.tscn"
        ↓  external_artifact_resolver（递归静态解析；循环 → BLOCKED）
    Feature Component .tscn（+ 其嵌套引用）
        ↓  合并 Evidence
    Host Artifact + External Component Artifacts

证据优先级（声明核对顺序，Phase 1.8.17 起按**归属**限定）：
    **组件实例声明 → 该组件的 owner 产物（外部组件场景及其可达闭包） → 宿主节点**。
    声明节点（node_type）在某份产物里确认后，其 children 优先在该产物内按挂载关系核对
    （逐层后代）；跨产物组合（组件入口场景声明节点 + 宿主提供子节点，或反之）只核对
    **存在性** —— 这正是「组件只负责自身结构、宿主负责挂载」的现实表达。

定位（四层职责，禁止合并）：
    Capability（需要什么）→ Instance（声明什么）→ Ownership（哪个实例）→ Artifact Evidence（是否兑现）
    capability_contract_validator —— Builder **之前**：计划内部是否自洽（证据 = 计划）
    component_instance_ownership   —— 声明 → 产物实例节点的唯一映射（不猜测、不借用无关产物）
    artifact_evidence_validator    —— Builder **之后**：声明是否落到产物里（证据 = .tscn 文本，
                                     含 ExtResource 指向的组件场景）

输入（只允许两者 + 可选上下文）：
    scene_intent —— Scene Intent（`SceneIntent` 对象或契约文档 mapping）；原始 Blueprint /
                    旧规整内部 dict 一律 ValueError（与生成链其余部分同一输入边界）。
    scene_path   —— 生成后的 .tscn 路径（**生成物已写盘**；本模块只读，不写、不删、不修）。
    project_root —— 可选：解析 res:// 的项目根（缺省由 scene_path 向上找 project.godot）。

本模块 MUST NOT：
    - 修改 Builder / .tscn 生成逻辑 / Compatibility Gate / Capability Contract 规则
    - 启动 Godot、import Godot、加载 PackedScene、Editor / Runtime SceneTree
    - 读 Blueprint / Feature 数据 / Feature Registry / Capability Registry / Asset Registry
    - 自动修复或删除生成物（失败时保留产物供诊断）

静态解析范围（见 known_gaps.artifact_parser_scope_limited / external_artifact_parser_scope_limited）：
    允许读取：节点名 / 类型 / parent 关系 / ext_resource 表（type / path / id）
    不读取：属性值语义、sub_resource、script、animation、资源文件内容
    仅解析 res://Features/**/*.tscn（组件入口场景）；其他 PackedScene（如根场景复用）不在范围。

契约：.ai/context/scene_composer_schema.yaml#artifact_evidence_validation
      .ai/context/scene_composer_schema.yaml#external_artifact_evidence
      .ai/context/scene_composer_schema.yaml#component_instance_ownership
"""

import os

import component_instance_ownership
import external_artifact_resolver
from scene_intent import intent_component_instances, intent_document

ARTIFACT_VALIDATOR_VERSION = 3
STATUS_PASS = "PASS"
STATUS_BLOCKED = "BLOCKED"


class ArtifactEvidenceReport:
    """生成物证据核验结论（`to_dict()` 给出契约形态的普通 mapping）。

    Phase 1.8.15 三键保持不变；Phase 1.8.16 **追加** checked_external_artifacts，
    Phase 1.8.17 **追加** checked_ownership（旧消费者读旧键即可，保持兼容）。
    """

    def __init__(self, status: str, errors=None, checked_instances=None,
                 checked_external_artifacts=None, checked_ownership=None):
        if status not in (STATUS_PASS, STATUS_BLOCKED):
            raise ValueError("ArtifactEvidenceReport status must be PASS or BLOCKED, got %r"
                             % status)
        self.status = status
        self.errors = list(errors or [])
        # 已核对且**在生成物中找到**的组件实例（按声明顺序）
        self.checked_instances = list(checked_instances or [])
        # 已解析的外部组件场景（res:// 路径，出现顺序，去重）
        self.checked_external_artifacts = list(checked_external_artifacts or [])
        # 组件 → 产物实例节点的归属映射（Phase 1.8.17；{component, artifact_path,
        # node_path, confidence}）
        self.checked_ownership = [dict(owner) for owner in (checked_ownership or [])]

    @property
    def ok(self) -> bool:
        return self.status == STATUS_PASS

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "errors": list(self.errors),
            "checked_instances": list(self.checked_instances),
            "checked_external_artifacts": list(self.checked_external_artifacts),
            "checked_ownership": [dict(owner) for owner in self.checked_ownership],
        }

    def __repr__(self) -> str:  # pragma: no cover - 便于调试
        return "<ArtifactEvidenceReport %s checked=%d external=%d owners=%d errors=%d>" % (
            self.status, len(self.checked_instances), len(self.checked_external_artifacts),
            len(self.checked_ownership), len(self.errors))


# ---------------------------------------------------------------- 静态解析（委托 resolver）

def parse_artifact(scene_path: str) -> dict:
    """静态解析宿主 .tscn 文本 -> {"root_name", "nodes", "ext_resources"}。

    解析实现归 external_artifact_resolver.parse_scene_text（单一实现，避免两份解析器）；
    本入口保持 Phase 1.8.15 的公开形态。只读文本，不加载 PackedScene。
    """
    return external_artifact_resolver.parse_scene_text(scene_path)


# ---------------------------------------------------------------- Evidence pools

def _host_pool(scene_path: str, scene: dict) -> dict:
    return {"kind": "host", "origin": os.path.abspath(scene_path),
            "root_name": scene["root_name"], "nodes": scene["nodes"]}


def _external_pools(external: dict) -> list:
    """外部产物 -> 每个 origin 一个证据池（保持解析顺序）。"""
    pools = []
    for node in external["nodes"]:
        origin = node.get("origin") or ""
        pool = next((p for p in pools if p["origin"] == origin), None)
        if pool is None:
            pool = {"kind": "external", "origin": origin, "root_name": "", "nodes": []}
            pools.append(pool)
        if not pool["root_name"] and not external_artifact_resolver.normalize_path(node["parent"]):
            pool["root_name"] = node["name"]
        pool["nodes"].append(node)
    return pools


def _reachable(origin: str, references: dict) -> list:
    """从 origin 出发的可达外部产物（BFS，去重，含 origin 自身；缺失者跳过）。"""
    ordered, queue = [], [origin] if origin else []
    while queue:
        current = queue.pop(0)
        if not current or current in ordered:
            continue
        ordered.append(current)
        queue.extend(references.get(current) or [])
    return ordered


def _pools_for_owner(owner, host_pool: dict, external_pools: dict, references: dict) -> list:
    """归属限定证据池：owner 产物（含可达闭包）→ 宿主。（无 owner / host-only → 仅宿主。）"""
    if not owner:
        return [host_pool]
    origin = str(owner.get("artifact_path") or "")
    if not origin or origin == host_pool["origin"] or origin not in external_pools:
        return [host_pool]
    ordered = [external_pools[path] for path in _reachable(origin, references)
               if path in external_pools]
    return ordered + [host_pool]


def _matching_nodes(declared: dict, pool: dict) -> list:
    """某证据池中与声明 node_type（+ 可选 parent）匹配的节点。"""
    node_type = declared["node_type"]
    wants_parent = external_artifact_resolver.normalize_path(declared.get("parent") or "")
    matches = [node for node in pool["nodes"] if node["type"] == node_type]
    if wants_parent:
        matches = [node for node in matches
                   if external_artifact_resolver.parent_key(node, pool["root_name"])
                   == wants_parent]
    return matches


def _mount_path(pool: dict, node: dict) -> str:
    """节点在证据池中的**全路径**挂载点（根节点 → 根名）：逐层后代判定的基准。"""
    return node.get("parent_path") or pool["root_name"]


def _verify_declared_instance(declared: dict, pools: list) -> list:
    """单条实例声明 -> 错误列表（空列表 = 该实例的归属证据中存在对应结构）。

    pools 已由 _pools_for_owner 按归属限定并排序（owner 产物 → 宿主），此处按序命中即止。
    """
    node_type = declared["node_type"]
    confirmed = None
    for pool in pools:
        matches = _matching_nodes(declared, pool)
        if matches:
            confirmed = (pool, matches)
            break
    if confirmed is None:
        return ["Artifact evidence mismatch: %s missing" % node_type]

    pool, matches = confirmed
    base_paths = [node["path"] for node in matches]
    errors = []
    for child_type in declared.get("children") or []:
        # a) 同一产物内：必须是声明节点的子节点（含逐层后代）
        nested = [node for node in pool["nodes"]
                  if node["type"] == child_type
                  and any(external_artifact_resolver.is_under(_mount_path(pool, node), base)
                          for base in base_paths)]
        if nested:
            continue
        # b) 跨产物组合：子节点由另一份产物提供（宿主挂载 / 组件入口场景）
        elsewhere = [node for other in pools if other is not pool
                     for node in other["nodes"] if node["type"] == child_type]
        if elsewhere:
            continue
        errors.append("Artifact evidence mismatch: %s missing" % child_type)
    return errors


# ---------------------------------------------------------------- 核验入口

def verify_artifact_evidence(scene_intent, scene_path, project_root=None) -> ArtifactEvidenceReport:
    """Scene Intent（声明）+ 生成物路径（+ 外部组件场景）-> ArtifactEvidenceReport。

    规则（按 components[] 声明顺序，逐条声明核对合并证据）：
        无 components[].instance          -> 不核验（旧行为：PASS、checked 列表均空，
                                              连生成物都不读）
        归属无法唯一确定                  -> BLOCKED "Component ownership unresolved: <component>"
        外部组件场景不存在 / 非法路径      -> BLOCKED \"External artifact unavailable: <path>\"
        外部组件场景成环                  -> BLOCKED \"External artifact recursion detected: <path>\"
        声明 node_type 未出现在合并证据里  -> BLOCKED \"Artifact evidence mismatch: <type> missing\"
        声明 children 既不在该节点之下、也不在其他产物里 -> 同上
        全部找到                          -> checked_instances / checked_external_artifacts 记录

    只比较**结构**（类型 / 挂载关系）；属性值、sub_resource、script、animation 不参与。
    """
    document = intent_document(
        scene_intent, "artifact_evidence_validator.verify_artifact_evidence")
    declared = [entry for entry in intent_component_instances(document)
                if isinstance(entry.get("instance"), dict)]

    # 未声明实例 → 本层无事可核验（保持旧行为，不读生成物、不解析外部场景）。
    if not declared:
        return ArtifactEvidenceReport(STATUS_PASS, [], [], [], [])

    path = str(scene_path or "").strip()
    if not path or not os.path.isfile(path):
        return ArtifactEvidenceReport(
            STATUS_BLOCKED, ["Artifact evidence unavailable: %s" % (path or "<missing>")],
            [], [], [])
    try:
        host = parse_artifact(path)
    except OSError as exc:
        return ArtifactEvidenceReport(
            STATUS_BLOCKED, ["Artifact evidence unavailable: %s (%s)" % (path, exc)], [], [], [])

    # 外部组件场景（ExtResource → res://Features/**/*.tscn，递归；循环即 BLOCKED）。
    external = external_artifact_resolver.resolve_external_artifacts(
        path, project_root=project_root)
    if external["errors"]:
        return ArtifactEvidenceReport(STATUS_BLOCKED, list(external["errors"]), [],
                                      list(external["artifacts"]))

    # 归属映射（Phase 1.8.17）：声明 → 产物实例节点；无法唯一确定即 BLOCKED（不猜测）。
    # 传入 host（解析结果含 scene_path）—— host-only 归属的 artifact_path 即宿主产物自身。
    ownership = component_instance_ownership.resolve_component_ownership(document, host)
    if ownership["status"] != component_instance_ownership.STATUS_PASS:
        return ArtifactEvidenceReport(STATUS_BLOCKED, list(ownership["errors"]), [],
                                      list(external["artifacts"]), list(ownership["owners"]))

    host_pool = _host_pool(path, host)
    external_pools = {pool["origin"]: pool for pool in _external_pools(external)}
    owners = {owner["component"]: owner for owner in ownership["owners"]}

    errors, checked = [], []
    for entry in declared:
        instance = entry["instance"]
        node_type = str(instance.get("node_type") or "").strip()
        if not node_type:
            # 缺失 / 未知 node_type 归 Capability Contract 层（Builder 之前已拦截）；
            # 本层不重复判定，也不猜测。
            continue
        declared_instance = {"component": entry["component"], "node_type": node_type,
                             "children": [str(child).strip()
                                          for child in (instance.get("children") or [])
                                          if str(child or "").strip()]}
        parent = instance.get("parent")
        if isinstance(parent, str) and parent.strip():
            declared_instance["parent"] = parent.strip()
        pools = _pools_for_owner(owners.get(entry["component"]), host_pool, external_pools,
                                 external["references"])
        instance_errors = _verify_declared_instance(declared_instance, pools)
        if instance_errors:
            errors.extend(instance_errors)
        else:
            checked.append(entry["component"] or node_type)

    status = STATUS_BLOCKED if errors else STATUS_PASS
    return ArtifactEvidenceReport(status, errors, checked, list(external["artifacts"]),
                                  list(ownership["owners"]))


def main(argv=None) -> int:  # pragma: no cover - 诊断入口（只读，无副作用）
    """打印核验器版本与静态解析范围。"""
    print("Artifact Evidence Validator v%d" % ARTIFACT_VALIDATOR_VERSION)
    print("static only: host .tscn + res://Features/**/*.tscn (via ext_resource)")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
