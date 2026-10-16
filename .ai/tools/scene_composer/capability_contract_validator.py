#!/usr/bin/env python3
"""Capability Contract Validator (Phase 1.8.13)

链路位置（Gate 只管 availability，本模块管 fulfillment）：

    Blueprint
        ↓  intent_from_blueprint()
    Scene Intent
        ↓  compatibility_gate（是否**支持**该能力：supported / reserved / unknown）
        ↓  capability_contract_validator（当前生成计划是否**满足**能力要求）
    Scene Builder
        ↓
    .tscn

输入（只允许两者）：

    scene_intent —— Scene Intent（`SceneIntent` 对象或契约文档 mapping）；原始 Blueprint /
                    旧规整内部 dict 一律 ValueError（与生成链其余部分同一输入边界）。
    scene_plan   —— 可选的 Scene Plan（证据）；缺省时由 evidence adapter 从 Scene Intent 构造。

本模块 MUST NOT：
    - 读 Blueprint / Feature（feature.yaml / template.yaml）/ Feature Registry / Binding /
      Asset Registry
    - 解析 .tscn（证据只来自 Builder 之前的计划数据）
    - 修改 Scene Intent、生成文件、判断能力**是否被支持**（那是 capability_registry /
      compatibility_gate 的职责；本模块只回答「计划是否满足契约」）
    - 无证据时猜测通过（无契约 → "Unknown capability contract"；预留 → not implemented）

证据来源（Scene Plan，唯一入口 = scene_plan_from_intent）：
    instances[]      —— 组件实例计划（Phase 1.8.14；components[].instance 经
                        component_instance_resolver 解析）—— 节点类型证据的**优先来源**
    nodes[]          —— Intent nodes[]（entity 级结构节点：类型 / 名称）
    root             —— Intent root（节点名 / 类型）
    components[]     —— Intent components[]（声明式组合；只作为「已声明组合数据」携带）
    resource_nodes[] —— Intent resources[]（**仅当**某契约的 evidence 明确需要资源节点时读取，
                        即 include_resource_nodes=True；否则一概不读）
不读取：validation[]、scripts / animations（PLANNED 段由 Gate 处理）。

证据优先级（Phase 1.8.14）：components[].instance → nodes[] → root。
    实例计划是**声明式证据**（组件自带的节点结构声明），优先级最高但**不排他**：
    它说明不了的部分仍由 nodes[] / root 提供（含物理体节点的等价表达）。
    无法识别的实例声明（未知 node_type）→ BLOCKED，不猜测通过、不降级放行。

已知证据缺口（见契约 known_gaps.capability_plan_evidence_component_subtrees_invisible / 
component_instance_evidence_scope）：
    实例计划是声明（不是对 .tscn 的核验），且只覆盖已声明的 node_type / children；
    组件入口场景内部真实子树仍不可见，因此「碰撞」类契约同时接受物理体节点作为等价表达
    （capability_contracts.COLLISION_NODE_TYPES）。

契约：.ai/context/scene_composer_schema.yaml#capability_contract_validation
"""

import capability_contracts
import component_instance_resolver
from scene_intent import intent_capabilities, intent_document

VALIDATOR_VERSION = 1
STATUS_PASS = "PASS"
STATUS_BLOCKED = "BLOCKED"


class CapabilityContractReport:
    """契约校验结论（`to_dict()` 给出契约形态的普通 mapping，三键）。"""

    def __init__(self, status: str, errors=None, checked_capabilities=None):
        if status not in (STATUS_PASS, STATUS_BLOCKED):
            raise ValueError("CapabilityContractReport status must be PASS or BLOCKED, got %r"
                             % status)
        self.status = status
        self.errors = list(errors or [])
        # 已核对且**满足**契约的能力（按声明顺序）
        self.checked_capabilities = list(checked_capabilities or [])

    @property
    def ok(self) -> bool:
        return self.status == STATUS_PASS

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "errors": list(self.errors),
            "checked_capabilities": list(self.checked_capabilities),
        }

    def __repr__(self) -> str:  # pragma: no cover - 便于调试
        return "<CapabilityContractReport %s checked=%d errors=%d>" % (
            self.status, len(self.checked_capabilities), len(self.errors))


# ---------------------------------------------------------------- Evidence adapter

def _node_entry(entry, default_name: str = "") -> dict:
    """节点条目 -> {"name": str, "type": str}（接受 mapping 或类型字符串）。"""
    if isinstance(entry, str):
        name = entry.strip()
        return {"name": name or default_name, "type": name}
    if isinstance(entry, dict):
        node_type = str(entry.get("type") or "").strip()
        name = str(entry.get("name") or "").strip() or node_type or default_name
        return {"name": name, "type": node_type}
    return {}


def scene_plan_from_intent(scene_intent, include_resource_nodes: bool = False) -> dict:
    """Scene Intent -> Scene Plan（证据视图；只读投影，不修改输入）。

    include_resource_nodes —— 是否读取 Intent resources[]（**默认不读**：只有契约的
    evidence 明确需要资源节点时才允许，见模块 docstring）。

    instances / instance_errors —— Phase 1.8.14：组件实例计划（优先证据）与无法识别的
    声明（→ BLOCKED，不猜测）。
    """
    document = intent_document(scene_intent,
                               "capability_contract_validator.scene_plan_from_intent")
    root = document.get("root") or {}
    if not isinstance(root, dict):
        root = {}
    instance_report = component_instance_resolver.resolve_component_instance_report(document)
    plan = {
        "root": {"name": str(root.get("name") or "").strip(),
                 "type": str(root.get("type") or "").strip()},
        "nodes": [_node_entry(entry) for entry in (document.get("nodes") or [])],
        "components": [{"component": str((entry or {}).get("component") or "").strip()}
                       for entry in (document.get("components") or [])
                       if isinstance(entry, dict)],
        "instances": [dict(entry) for entry in instance_report.instances],
        "instance_errors": list(instance_report.errors),
        "resource_nodes": [],
        "source": "scene_intent",
    }
    if include_resource_nodes:
        plan["resource_nodes"] = [_node_entry(entry)
                                  for entry in (document.get("resources") or [])
                                  if isinstance(entry, dict)]
    return plan


def _instance_entry(entry: dict) -> dict:
    """显式 Scene Plan 的实例条目 -> 规范形态（只收已声明字段，不补默认值）。"""
    instance = {"component": str(entry.get("component") or "").strip(),
                "node_type": str(entry.get("node_type") or "").strip(),
                "children": [str(item).strip() for item in (entry.get("children") or [])
                             if str(item or "").strip()]}
    parent = entry.get("parent")
    if isinstance(parent, str) and parent.strip():
        instance["parent"] = parent.strip()
    resources = entry.get("resources")
    if isinstance(resources, (list, tuple)):
        values = [str(item).strip() for item in resources if str(item or "").strip()]
        if values:
            instance["resources"] = values
    return instance


def normalize_scene_plan(scene_plan) -> dict:
    """显式传入的 Scene Plan -> 规范形态（缺省键补齐；非 mapping → ValueError）。

    显式计划 = 完整证据：instances / instance_errors 缺省为空（有意**不从 Intent 回填**，
    避免把两个证据源隐式混合）。
    """
    if not isinstance(scene_plan, dict):
        raise ValueError("scene_plan must be a mapping, got %s" % type(scene_plan).__name__)
    root = scene_plan.get("root") or {}
    if isinstance(root, str):
        root = {"name": root, "type": root}
    if not isinstance(root, dict):
        root = {}
    return {
        "root": {"name": str(root.get("name") or "").strip(),
                 "type": str(root.get("type") or "").strip()},
        "nodes": [_node_entry(entry) for entry in (scene_plan.get("nodes") or [])],
        "components": [entry for entry in (scene_plan.get("components") or [])
                       if isinstance(entry, dict)],
        "instances": [_instance_entry(entry) for entry in (scene_plan.get("instances") or [])
                      if isinstance(entry, dict)],
        "instance_errors": [str(error) for error in (scene_plan.get("instance_errors") or [])],
        "resource_nodes": [_node_entry(entry)
                           for entry in (scene_plan.get("resource_nodes")
                                         or scene_plan.get("resources") or [])
                           if isinstance(entry, (dict, str))],
        "source": "explicit",
    }


# ---------------------------------------------------------------- 判定

def _candidate_types(plan: dict, kinds) -> list:
    """按契约声明的证据种类收集候选节点类型（**只取该契约允许的部分**）。

    证据优先级（Phase 1.8.14）：instances[]（node_type + children）→ nodes[] → root。
    """
    types = []
    if "node_type" in kinds:
        for instance in plan["instances"]:
            types.append(instance.get("node_type") or "")
            types.extend(instance.get("children") or [])
        types.extend(entry.get("type") or "" for entry in plan["nodes"])
        types.append(plan["root"].get("type") or "")
    if "resource_node_type" in kinds:
        types.extend(entry.get("type") or "" for entry in plan["resource_nodes"])
    return [node_type for node_type in types if node_type]


def _satisfied(contract: dict, plan: dict) -> bool:
    """契约是否被当前计划满足（证据不足 → False，不猜测）。"""
    kinds = tuple(contract.get("evidence") or ())
    if "root_node" in kinds:
        if not (plan["root"].get("name") and plan["root"].get("type")):
            return False
    if "node_type" in kinds or "resource_node_type" in kinds:
        wanted = tuple(contract.get("node_types") or ())
        if not wanted:
            return False
        if not any(node_type in wanted for node_type in _candidate_types(plan, kinds)):
            return False
    return True


def validate_capability_contract(scene_intent, scene_plan=None) -> CapabilityContractReport:
    """Scene Intent(+Scene Plan) -> CapabilityContractReport（PASS / BLOCKED）。

    scene_intent —— Scene Intent（`SceneIntent` 对象或契约文档 mapping）；唯一合法意图输入。
    scene_plan   —— 可选证据；None 时由 scene_plan_from_intent 构造（并在契约需要资源节点时
                    才读取 Intent resources[]）。

    判定（按 Intent 声明顺序，逐个能力）：
        实例声明无法识别  -> BLOCKED "Unknown component instance type: <type>"
                            （或 "Invalid component instance: <component>"）——证据不可信时
                            不做任何能力放行（checked_capabilities 为空），不猜测通过
        无契约           -> BLOCKED "Unknown capability contract: <name>"（禁止猜测）
        契约未实现        -> BLOCKED "Capability contract not implemented: <name>"
        证据不足          -> BLOCKED "Capability contract failed: <name> requires <label>"
        证据充分          -> 记录进 checked_capabilities，放行
    """
    document = intent_document(
        scene_intent,
        "capability_contract_validator.validate_capability_contract")
    required = intent_capabilities(document)["required"]

    if scene_plan is None:
        needs_resources = any(capability_contracts.needs_resource_nodes(name)
                              for name in required)
        plan = scene_plan_from_intent(document, include_resource_nodes=needs_resources)
    else:
        plan = normalize_scene_plan(scene_plan)

    # 实例证据不可信（未识别 / 非法声明）→ 先拦：不得在坏证据上放行任何能力。
    if plan["instance_errors"]:
        return CapabilityContractReport(STATUS_BLOCKED, list(plan["instance_errors"]), [])

    errors, checked = [], []
    for name in required:
        contract = capability_contracts.contract_for(name)
        if contract is None:
            errors.append("Unknown capability contract: %s" % name)
            continue
        if not capability_contracts.is_implemented(name):
            errors.append("Capability contract not implemented: %s" % name)
            continue
        if _satisfied(contract, plan):
            checked.append(name)
        else:
            errors.append("Capability contract failed: %s requires %s"
                          % (name, capability_contracts.contract_label(name)))

    status = STATUS_BLOCKED if errors else STATUS_PASS
    return CapabilityContractReport(status, errors, checked)


def main(argv=None) -> int:  # pragma: no cover - 诊断入口（不读蓝图、不生成文件）
    """打印契约表与当前校验器版本。"""
    summary = capability_contracts.contract_summary()
    print("Capability Contract Validator v%d" % VALIDATOR_VERSION)
    print("contracts: %s" % ", ".join(summary["contracts"]))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
