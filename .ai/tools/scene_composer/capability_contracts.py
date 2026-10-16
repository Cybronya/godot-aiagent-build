#!/usr/bin/env python3
"""Capability Contract Table (Phase 1.8.13) —— 能力 → 契约（requirement）的唯一事实源。

定位（与 Compatibility Gate 分工明确，禁止合并）：

    Compatibility Gate（1.8.9/1.8.10） —— 能力**是否被支持**（availability）
        ↑ capability_registry.py（能力词表）
    Capability Contract Validator（1.8.13，本表的消费者） —— 当前生成计划**是否满足**能力要求
        （fulfillment）：Required Capability + Scene Plan Evidence → PASS / BLOCKED

本模块只**声明契约**，不做判定、不读任何外部输入：

    - 不读 Blueprint、不读 Scene Intent、不读 Feature（feature.yaml / template.yaml）、
      不读 Feature Registry、不读 Binding、不读 .tscn、不写文件、不判断支持性。
    - 能力**词表**的唯一事实源仍是 scene_composer/capability_registry.py；本表只针对
      已登记的 supported 能力与已冻结的 reserved 能力声明「需要什么证据」，
      两者的一致性由测试（test_capability_contract_validator.py）锁定，本模块不 import Registry。

契约结构（每一项）：
    requires    —— 人类可读要求标签（错误文案逐字使用：
                   "Capability contract failed: <capability> requires <label>"）
    evidence    —— 证据种类（Scene Plan 的哪一部分可用于核对该契约）：
                   root_node            ：计划必须存在 root 节点
                   node_type            ：计划声明式结构节点（root + nodes[]）中必须出现
                                          任一 node_types
                   resource_node_type   ：资源节点（Intent resources[]，Binding 派生）类型中
                                          必须出现任一 node_types
    node_types  —— 满足该契约的节点类型集合（仅 evidence 含类型种类时有意义）
    implemented —— 缺省 True；False = 契约已登记但本阶段不实现（出现即 BLOCKED，
                   不得静默放行）。Script / Animation 一类**预留能力**归此列。
"""

CONTRACT_VERSION = 1

# ---------------------------------------------------------------- 节点类型集合（契约用）

# 「已有节点表达」的碰撞证据：碰撞**形状**节点，或物理体节点（含实体根类型）。
# 说明：组件实例自带的碰撞子树不在 Scene Intent 可见范围内（components[].node 为
# 契约 PLANNED），因此物理体根 / 结构体节点同样视为计划中的碰撞表达（见 known gap
# capability_plan_evidence_component_subtrees_invisible）。
COLLISION_SHAPE_NODE_TYPES = ("CollisionShape2D", "CollisionPolygon2D")
PHYSICS_BODY_NODE_TYPES = ("PhysicsBody2D", "CharacterBody2D", "Area2D", "StaticBody2D",
                           "RigidBody2D", "AnimatableBody2D")
COLLISION_NODE_TYPES = COLLISION_SHAPE_NODE_TYPES + PHYSICS_BODY_NODE_TYPES

SPRITE_NODE_TYPES = ("Sprite2D", "AnimatedSprite2D")
ANIMATED_SPRITE_NODE_TYPES = ("AnimatedSprite2D",)
AUDIO_NODE_TYPES = ("AudioStreamPlayer", "AudioStreamPlayer2D")

# ---------------------------------------------------------------- 契约表（唯一事实源）

CAPABILITY_CONTRACTS = {
    "Node": {
        "requires": ["node_exists"],
        "evidence": ("root_node",),
    },
    "Collision": {
        "requires": ["CollisionShape2D"],
        "evidence": ("node_type",),
        "node_types": COLLISION_NODE_TYPES,
    },
    "Sprite": {
        "requires": ["Sprite2D_or_AnimatedSprite2D"],
        "evidence": ("node_type", "resource_node_type"),
        "node_types": SPRITE_NODE_TYPES,
    },
    "AnimatedSprite": {
        "requires": ["AnimatedSprite2D"],
        "evidence": ("node_type", "resource_node_type"),
        "node_types": ANIMATED_SPRITE_NODE_TYPES,
    },
    "Audio": {
        "requires": ["AudioStreamPlayer"],
        "evidence": ("node_type", "resource_node_type"),
        "node_types": AUDIO_NODE_TYPES,
    },
    # ---- 预留能力（本阶段不实现；契约已登记，证据不可满足 → BLOCKED）----
    "Script": {
        "requires": ["script_runtime"],
        "evidence": (),
        "implemented": False,
    },
    "Animation": {
        "requires": ["animation_runtime"],
        "evidence": (),
        "implemented": False,
    },
    "AnimationController": {
        "requires": ["animation_controller_runtime"],
        "evidence": (),
        "implemented": False,
    },
    "AI": {
        "requires": ["ai_runtime"],
        "evidence": (),
        "implemented": False,
    },
    "RuntimeBehaviour": {
        "requires": ["runtime_behaviour_layer"],
        "evidence": (),
        "implemented": False,
    },
}


def contract_for(capability):
    """能力名 -> 契约 mapping；未登记返回 None（调用方不得猜测）。"""
    name = str(capability or "").strip()
    contract = CAPABILITY_CONTRACTS.get(name)
    if contract is not None:
        return contract
    # 大小写 / 空白不改变契约身份（与能力词表的判定风格一致）
    lowered = name.lower()
    for key, value in CAPABILITY_CONTRACTS.items():
        if key.lower() == lowered:
            return value
    return None


def contract_label(capability) -> str:
    """能力名 -> 契约要求标签（错误文案用）；未登记返回 ""。"""
    contract = contract_for(capability)
    if not contract:
        return ""
    return " or ".join(str(item) for item in contract.get("requires") or [])


def is_implemented(capability) -> bool:
    """该能力的契约在当前阶段是否可实现（预留能力为 False）。"""
    contract = contract_for(capability)
    if not contract:
        return False
    return bool(contract.get("implemented", True))


def needs_resource_nodes(capability) -> bool:
    """核对该契约是否需要读取 Intent resources[]（资源节点）作为证据。"""
    contract = contract_for(capability)
    if not contract:
        return False
    return "resource_node_type" in tuple(contract.get("evidence") or ())


def contract_names() -> tuple:
    """已登记契约的能力名（声明顺序；仅名字，不含词表语义）。"""
    return tuple(CAPABILITY_CONTRACTS)


def contract_summary() -> dict:
    """契约表快照（供文档 / 诊断；不读任何外部输入）。"""
    return {
        "version": CONTRACT_VERSION,
        "contracts": {
            name: {
                "requires": list(contract.get("requires") or []),
                "evidence": list(contract.get("evidence") or ()),
                "node_types": list(contract.get("node_types") or ()),
                "implemented": bool(contract.get("implemented", True)),
            }
            for name, contract in CAPABILITY_CONTRACTS.items()
        },
    }


def main(argv=None) -> int:  # pragma: no cover - 诊断入口（只读，无副作用）
    """打印契约表（不读蓝图 / Feature / Registry）。"""
    summary = contract_summary()
    print("Capability Contract Table v%d" % summary["version"])
    for name, contract in summary["contracts"].items():
        state = "" if contract["implemented"] else "  [reserved: not implemented]"
        print("  %-20s requires=%s evidence=%s%s"
              % (name, ",".join(contract["requires"]), ",".join(contract["evidence"]) or "-",
                 state))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
