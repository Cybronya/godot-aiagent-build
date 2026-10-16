#!/usr/bin/env python3
"""Component Instance Resolver (Phase 1.8.14) —— 组件声明 → 实例计划（证据供给层）。

链路位置（契约层职责三分，禁止合并）：

    capability_contracts.py         定义规则（capability → requirement）
    component_instance_resolver.py  提供证据（components[].instance → 实例计划；本模块）
    capability_contract_validator.py 判断（计划是否满足契约 → PASS / BLOCKED）

    Feature（可选声明 instance:）
        ↓  template_loader.normalize_scene_blueprint（只传递）
    Blueprint.components[].instance
        ↓  SceneIntentBuilder（只投影）
    Scene Intent.components[].instance
        ↓  resolve_component_instances（本模块：只读 + 只校验，不猜测）
    Instance Plan（证据）
        ↓
    Capability Contract Validation

输入（只允许 Scene Intent）：

    scene_intent —— `SceneIntent` 对象或契约文档 mapping；原始 Blueprint / 旧规整内部 dict
                    一律 ValueError（与生成链其余部分同一输入边界）。

本模块 MUST NOT：
    - 读 Blueprint / Feature（feature.yaml / template.yaml）/ Feature Registry / Binding /
      Asset Registry（只消费已经进入 Scene Intent 的声明）
    - 解析 .tscn（证据只来自 Builder 之前的计划数据）
    - 按 component id / 名字 / 目录猜测实例（禁止 `if "damage" in id: children += [...]`）
    - 生成节点、生成文件、修改 Scene Intent（本层只产出证据，不影响 Builder 输出）
    - 判断能力**是否被支持**（归 capability_registry / compatibility_gate）

「实例计划」= 声明式证据，不是生成指令：Builder 不消费它（Phase 1.8.14 不改变任何
.tscn 输出），它只回答「该组件自带的节点结构中有哪些已声明的节点类型」。

节点类型词表（INSTANCE_NODE_TYPES）是**保守白名单**：未识别类型不猜测通过，报
`Unknown component instance type: <type>`（见契约 known_gaps.component_instance_evidence_scope）。

契约：.ai/context/scene_composer_schema.yaml#component_instance_materialization
"""

from scene_intent import intent_component_instances

RESOLVER_VERSION = 1

# ---------------------------------------------------------------- 实例节点类型词表
# 说明：Godot 4 场景组合范围内可被声明的节点类型（显式列举 = 可审计；不读引擎 / 不读 Registry）。
# 该词表必须覆盖 capability_contracts 的全部契约 node_types（一致性由测试锁定）。
# 有意不含 AnimationPlayer / AnimationTree（Animation Layer 未实现，见 known gaps）。
INSTANCE_NODE_TYPES = (
    # 结构与标记
    "Node", "Node2D", "Marker2D", "Timer",
    # 物理
    "PhysicsBody2D", "CharacterBody2D", "StaticBody2D", "RigidBody2D",
    "AnimatableBody2D", "Area2D",
    "CollisionShape2D", "CollisionPolygon2D",
    # 显示
    "Sprite2D", "AnimatedSprite2D",
    # 音频
    "AudioStreamPlayer", "AudioStreamPlayer2D",
    # UI / Control
    "Control", "Label", "Button", "TextureRect", "TextureProgressBar",
    "ProgressBar", "NinePatchRect",
)

MISSING_NODE_TYPE = "<missing>"

# 组件实例声明允许携带的字段（其余键忽略；未知键不等于可猜测的实例）
# id —— Phase 1.8.17：声明方给出的节点身份（ownership 唯一映射依据；不参与能力证据）
INSTANCE_FIELDS = ("id", "node_type", "children", "resources", "parent")


class ComponentInstanceReport:
    """实例解析结论（`to_dict()` 给出契约形态的普通 mapping，两键）。"""

    def __init__(self, instances=None, errors=None):
        self.instances = [dict(entry) for entry in (instances or [])]
        self.errors = list(errors or [])

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"instances": [dict(entry) for entry in self.instances],
                "errors": list(self.errors)}

    def __repr__(self) -> str:  # pragma: no cover - 便于调试
        return "<ComponentInstanceReport instances=%d errors=%d>" % (
            len(self.instances), len(self.errors))


def instance_node_types() -> tuple:
    """识别的实例节点类型（声明顺序；只读快照）。"""
    return tuple(INSTANCE_NODE_TYPES)


def is_known_instance_type(node_type) -> bool:
    """节点类型是否被识别（大小写 / 空白不改变身份；未识别 → False，不猜测）。"""
    name = str(node_type or "").strip()
    if not name:
        return False
    if name in INSTANCE_NODE_TYPES:
        return True
    lowered = name.lower()
    return any(known.lower() == lowered for known in INSTANCE_NODE_TYPES)


def _node_type_list(raw):
    """children / resources 声明 -> [节点类型]；非字符串列表 → None（非法，不猜测）。"""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return None
    values = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            values.append(item.strip())
        elif isinstance(item, dict) and str(item.get("node_type") or "").strip():
            values.append(str(item["node_type"]).strip())
        else:
            return None
    return values


def _resolve_entry(component: str, instance) -> tuple:
    """单条声明 -> (实例计划条目|None, 错误列表)。"""
    if not isinstance(instance, dict):
        return None, ["Invalid component instance: %s" % component]

    raw_type = instance.get("node_type")
    node_type = raw_type.strip() if isinstance(raw_type, str) else ""
    if not is_known_instance_type(node_type):
        return None, ["Unknown component instance type: %s"
                      % (node_type or str(raw_type or "").strip() or MISSING_NODE_TYPE)]

    children = _node_type_list(instance.get("children"))
    resources = _node_type_list(instance.get("resources"))
    if children is None or resources is None:
        return None, ["Invalid component instance: %s" % component]

    unknown = [name for name in (children + resources) if not is_known_instance_type(name)]
    if unknown:
        return None, ["Unknown component instance type: %s" % unknown[0]]

    entry = {"component": component, "node_type": node_type, "children": children}
    instance_id = instance.get("id")
    if instance_id is not None:
        if not isinstance(instance_id, str) or not instance_id.strip():
            return None, ["Invalid component instance: %s" % component]
        entry["id"] = instance_id.strip()
    parent = instance.get("parent")
    if isinstance(parent, str) and parent.strip():
        entry["parent"] = parent.strip()
    elif parent is not None and not isinstance(parent, str):
        return None, ["Invalid component instance: %s" % component]
    if resources:
        entry["resources"] = resources
    return entry, []


def resolve_component_instance_report(scene_intent) -> ComponentInstanceReport:
    """Scene Intent -> ComponentInstanceReport（实例计划 + 错误）。

    只读投影：未声明 instance 的组件不产生条目（旧 Intent 行为不变）；
    声明了但无法识别 → errors（不猜测通过、不静默丢弃）。
    """
    instances, errors = [], []
    for declared in intent_component_instances(scene_intent):
        entry, entry_errors = _resolve_entry(declared["component"], declared["instance"])
        if entry is not None:
            instances.append(entry)
        errors.extend(entry_errors)
    return ComponentInstanceReport(instances, errors)


def resolve_component_instances(scene_intent) -> list:
    """Scene Intent -> 实例计划列表（成功条目；错误经 Report 暴露，不吞掉）。

    返回 [{"component": <id>, "node_type": <type>, "children": [...],
           "id": <可选 声明身份>, "parent": <可选>, "resources": <可选>}]
    （保持 components[] 声明顺序）。
    """
    return resolve_component_instance_report(scene_intent).instances


def main(argv=None) -> int:  # pragma: no cover - 诊断入口（只读，无副作用）
    """打印实例节点类型词表与解析器版本。"""
    print("Component Instance Resolver v%d" % RESOLVER_VERSION)
    print("node types: %s" % ", ".join(INSTANCE_NODE_TYPES))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
