#!/usr/bin/env python3
"""Scene Compatibility Gate (Phase 1.8.9 骨架) —— Scene Intent 与 Scene Builder 之间的闸门。

链路：

    Blueprint
        ↓  intent_from_blueprint()
    Scene Intent
        + capabilities.required（1.8.10 能力声明）
        ↓  compatibility_gate（本模块：生成前闸门）
    Scene Builder
        ↓
    .tscn

唯一输入：Scene Intent（`SceneIntent` 对象或契约文档 mapping），经
`scene_intent.intent_document()` 强制；原始 Blueprint / 旧规整内部 dict 一律
`ValueError`（无兼容适配器、无第二入口）。

本模块 MUST NOT：
    - 读 Blueprint / Binding / Discovery / Asset Registry（不搜索、不选择资源）
    - 重新推导节点层级、资源连接或 ext_resource（那是 scene_builder 的职责）
    - 生成 .tscn 或写任何文件；BLOCKED 时必须「零产物」（禁止半成品）
    - 表达运行时行为、Script、Animation（本阶段不实现，只拒绝）

本阶段（1.8.9）交付**骨架**：能力表 + 生成前判定 + 报告结构。
不做：运行时校验、Script / Animation 实现、既有 validator 缺陷修复。

读取的 Scene Intent 段（有意最小化，其余不读）：
    capabilities.required —— **能力声明（Phase 1.8.10，最高优先）**：逐个对照 capability_registry
    root               —— root.name 必需；root.type 与 root.scene 至少其一
    components[]       —— 逐个判定能力（components[].component）
    resources[]        —— resources[].type（**节点**类型）判定能力，供 checked_resources
    scripts / animations —— 契约 PLANNED；一旦出现即 BLOCKED（不得静默丢弃）
不读取：nodes[]、validation[]（分别归 Builder / Validator，闸门不重复其逻辑）

能力词汇说明（重要）：
    能力词汇的唯一事实源是 capability_registry（本模块只引用，不重写）。
    判定顺序：
        1) capabilities.required —— 声明式能力（未登记 / 预留即 BLOCKED）；
           这是**首选**通道：Gate 不再需要对 id 命名做猜测。
        2) components[].component —— 兼容通道（当前值是 Feature id）：
           能力类别名 → 记录类别；预留能力名 → BLOCKED；
           其余必须是 Feature Registry 已知 id（未知如 EnemyAI → BLOCKED）。
    资源层：assets 级别的类型（SpriteFrames / Texture2D / AudioStreamWAV）自 Phase 1.8.7
    起**不在 Scene Intent 中**（ext_type 由 Builder 派生），故本阶段只能校验资源**节点**
    类型白名单；assets 级能力见 known gap（契约）。

外部只读依赖：Feature Registry 索引（.ai/context/feature_index.json），
用于第 3 段判定；索引不可用时降级（warning，不因此阻断）。测试可注入 known_features。
"""

import json
import os
import sys

import capability_registry
from scene_intent import (intent_capabilities, intent_components, intent_document, intent_root)

GATE_VERSION = 2                       # 1.8.10：能力声明优先判定
STATUS_PASS = "PASS"
STATUS_BLOCKED = "BLOCKED"

# ---------------------------------------------------------------- 能力表（事实源：capability_registry）
# 本模块只**引用**能力表（下方名字保留为兼容别名）；禁止在此再写第二份词汇。
SUPPORTED_COMPONENT_CAPABILITIES = capability_registry.SUPPORTED_COMPONENT_CAPABILITIES
SUPPORTED_RESOURCE_CAPABILITIES = capability_registry.SUPPORTED_RESOURCE_CAPABILITIES
# 预留能力（当前一律 unsupported）：出现即 BLOCKED
UNSUPPORTED_CAPABILITIES = capability_registry.RESERVED_CAPABILITIES
SUPPORTED_RESOURCE_NODE_TYPES = capability_registry.SUPPORTED_RESOURCE_NODE_TYPES

# 契约 PLANNED 段：本阶段不消费，出现即阻断（不得静默丢弃）
UNSUPPORTED_INTENT_SECTIONS = ("scripts", "animations")

_SUPPORTED_BY_NAME = {name.lower(): name for name in SUPPORTED_COMPONENT_CAPABILITIES}
_UNSUPPORTED_BY_NAME = {name.lower(): name for name in UNSUPPORTED_CAPABILITIES}

_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .ai
FEATURE_INDEX_PATH = os.path.join(_DOTAI, "context", "feature_index.json")


class CompatibilityReport:
    """闸门结论（明确数据结构；`to_dict()` 给出契约形态的普通 mapping）。"""

    def __init__(self, status: str, errors=None, warnings=None,
                 checked_components=None, checked_resources=None,
                 checked_capabilities=None):
        if status not in (STATUS_PASS, STATUS_BLOCKED):
            raise ValueError("CompatibilityReport status must be PASS or BLOCKED, got %r" % status)
        self.status = status
        self.errors = list(errors or [])
        self.warnings = list(warnings or [])
        self.checked_components = list(checked_components or [])
        self.checked_resources = list(checked_resources or [])
        # Phase 1.8.10：被声明且被支持的能力（capability metadata 的核对结果）
        self.checked_capabilities = list(checked_capabilities or [])

    @property
    def ok(self) -> bool:
        return self.status == STATUS_PASS

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "checked_components": list(self.checked_components),
            "checked_resources": list(self.checked_resources),
            "checked_capabilities": list(self.checked_capabilities),
        }

    def __repr__(self) -> str:  # pragma: no cover - 便于调试
        return "<CompatibilityReport %s components=%d resources=%d errors=%d>" % (
            self.status, len(self.checked_components), len(self.checked_resources),
            len(self.errors))


def known_feature_ids(index_path: str = FEATURE_INDEX_PATH):
    """Feature Registry 索引 -> 已知 Feature id 集合（读不到时返回 None → 降级）。"""
    if not os.path.isfile(index_path):
        return None
    try:
        with open(index_path, encoding="utf-8") as handle:
            data = json.load(handle) or {}
    except (OSError, ValueError):
        return None
    ids = set()
    for entry in data.get("features") or []:
        if isinstance(entry, dict) and str(entry.get("id") or "").strip():
            ids.add(str(entry["id"]).strip())
    return ids or None


def check_scene_compatibility(scene_intent, known_features=None,
                              index_path: str = FEATURE_INDEX_PATH) -> CompatibilityReport:
    """生成前闸门：Scene Intent -> CompatibilityReport（PASS / BLOCKED）。

    scene_intent —— Scene Intent（`SceneIntent` 对象或契约文档 mapping）；唯一合法输入。
    known_features —— 测试 / 调用方可注入的 Feature id 集合；None 时读 Feature Registry 索引。

    判定顺序（Phase 1.8.10 起能力声明优先）：
        1) capabilities.required —— 逐个对照 capability_registry（未登记 / 预留 → BLOCKED）
        2) root / components / resources / PLANNED 段 —— 1.8.9 已有检查，全部保留
    """
    document = intent_document(scene_intent, "compatibility_gate.check_scene_compatibility")
    errors, warnings = [], []

    # 0. 能力声明（最高优先）：Intent 自己声明「需要什么能力」，不再依赖对 id 的猜测
    checked_capabilities = []
    for name in intent_capabilities(document)["required"]:
        if capability_registry.is_supported(name):
            checked_capabilities.append(capability_registry.canonical(name))
        else:
            errors.append("Unsupported capability: %s" % name)

    # 1. root：输出文件名的唯一来源，必须可判定
    root = intent_root(document)
    if not str(root.get("name") or "").strip():
        errors.append("Scene Intent root.name is required")
    if not str(root.get("type") or "").strip() and not str(root.get("scene") or "").strip():
        errors.append("Scene Intent root requires type or scene")

    # 2. components：能力类别名 / 不支持能力 / 已知 Feature id
    features = known_features if known_features is not None else known_feature_ids(index_path)
    if features is None:
        warnings.append("Feature Registry index unavailable: component capability check degraded")
    checked_components = []
    for token in intent_components(document):
        capability = _SUPPORTED_BY_NAME.get(str(token).lower())
        if capability:
            checked_components.append(capability)
            continue
        if str(token).lower() in _UNSUPPORTED_BY_NAME:
            errors.append("Unsupported component: %s" % token)
            continue
        if features is not None and token not in features:
            errors.append("Unsupported component: %s" % token)
            continue
        checked_components.append(token)

    # 3. resources：节点类型白名单（assets 级类型不在 Scene Intent 中）
    checked_resources = []
    for entry in document.get("resources") or []:
        if not isinstance(entry, dict):
            errors.append("Unsupported resource entry: %r" % (entry,))
            continue
        node_type = str(entry.get("type") or "").strip()
        name = str(entry.get("name") or "").strip()
        if node_type not in SUPPORTED_RESOURCE_NODE_TYPES:
            errors.append("Unsupported resource type: %s" % (node_type or "<missing>"))
            continue
        checked_resources.append(name or node_type)

    # 4. PLANNED 段：出现即阻断（本阶段不消费，不得静默丢弃）
    for section in UNSUPPORTED_INTENT_SECTIONS:
        if document.get(section):
            errors.append("Unsupported Scene Intent section: %s (not implemented in this phase)"
                          % section)

    status = STATUS_BLOCKED if errors else STATUS_PASS
    return CompatibilityReport(status, errors, warnings, checked_components, checked_resources,
                               checked_capabilities)


def main(argv=None) -> int:  # pragma: no cover - 诊断入口
    """诊断入口：打印能力表与版本（不读蓝图、不生成任何文件）。"""
    summary = capability_registry.registry_summary()
    known = known_feature_ids()
    print("Scene Compatibility Gate v%d" % GATE_VERSION)
    print("capability registry v%d" % summary["version"])
    print("components: %s" % ", ".join(SUPPORTED_COMPONENT_CAPABILITIES))
    print("resources:  %s" % ", ".join(SUPPORTED_RESOURCE_CAPABILITIES))
    print("reserved:   %s" % ", ".join(summary["reserved"]))
    print("known features: %d" % (len(known) if known else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
