#!/usr/bin/env python3
"""Capability Registry (Phase 1.8.10) —— Scene 层能力词汇的唯一事实源。

定位：
    「Scene Intent 声明需要什么能力」与「当前系统支持什么能力」之间的**唯一词汇表**。
    Compatibility Gate 判定 capability、Builder 能力边界文档、后续 Script / Animation
    扩展都引用本表；**禁止在别处再写第二份能力清单**。

边界：
    - 纯词汇表 + 判定函数：不读 Blueprint、不读 Feature Registry、不读 Binding、不读写文件。
    - 本阶段**只声明与判定**：不实现 Script / Animation / RuntimeBehaviour / AI，
      它们一律为「预留（reserved）→ 当前 unsupported」。

状态词汇：
    supported —— 当前 Scene 层可表达，Gate 放行。
    reserved  —— 已预留能力名（未来阶段实现）；当前阶段一律判定为不支持。
    unknown   —— 未登记：Gate 同样 BLOCKED（禁止猜测式放行）。

契约：.ai/context/scene_composer_schema.yaml#compatibility_gate（capabilities 与
scene_intent.capabilities.required）。修改本表必须同步契约与测试。
"""

REGISTRY_VERSION = 1

# 当前支持：Scene Intent 可声明、Builder 可表达
# （AnimatedSprite 保留：真实资源节点 AnimatedSprite2D 依赖它，Phase 1.8.9 已登记）
SUPPORTED_COMPONENT_CAPABILITIES = ("Node", "Sprite", "AnimatedSprite", "Audio", "Collision")

# 当前支持：assets 级资源能力（自 1.8.7 起不在 Scene Intent 中 → 见 known gap）
SUPPORTED_RESOURCE_CAPABILITIES = ("Texture2D", "SpriteFrames", "AudioStreamWAV")

# 预留能力：名字已冻结，但当前阶段 unsupported（出现即 BLOCKED）
RESERVED_CAPABILITIES = ("Script", "Animation", "AnimationController", "AI", "RuntimeBehaviour")

# 资源节点类型白名单：与契约 input.node_types.supported 同源（只复用，不改契约）
SUPPORTED_RESOURCE_NODE_TYPES = ("AnimatedSprite2D", "Sprite2D", "AudioStreamPlayer",
                                 "AudioStreamPlayer2D", "TextureRect", "Sprite3D", "TileMapLayer")

STATUS_SUPPORTED = "supported"
STATUS_RESERVED = "reserved"
STATUS_UNKNOWN = "unknown"

_SUPPORTED_BY_NAME = {name.lower(): name for name in SUPPORTED_COMPONENT_CAPABILITIES}
_RESERVED_BY_NAME = {name.lower(): name for name in RESERVED_CAPABILITIES}


def classify(capability) -> str:
    """能力名 -> supported / reserved / unknown（大小写不敏感，忽略首尾空白）。"""
    name = str(capability or "").strip().lower()
    if not name:
        return STATUS_UNKNOWN
    if name in _SUPPORTED_BY_NAME:
        return STATUS_SUPPORTED
    if name in _RESERVED_BY_NAME:
        return STATUS_RESERVED
    return STATUS_UNKNOWN


def is_supported(capability) -> bool:
    """当前阶段是否支持该能力（只有 supported 为真）。"""
    return classify(capability) == STATUS_SUPPORTED


def canonical(capability) -> str:
    """能力名 -> 登记表中的规范写法（未登记时返回去空格后的原名）。"""
    name = str(capability or "").strip()
    return _SUPPORTED_BY_NAME.get(name.lower()) or _RESERVED_BY_NAME.get(name.lower()) or name


def registry_summary() -> dict:
    """能力表快照（供 Gate 报告 / 诊断输出；不读任何外部输入）。"""
    return {
        "version": REGISTRY_VERSION,
        "supported": list(SUPPORTED_COMPONENT_CAPABILITIES),
        "supported_resources": list(SUPPORTED_RESOURCE_CAPABILITIES),
        "reserved": list(RESERVED_CAPABILITIES),
        "resource_node_types": list(SUPPORTED_RESOURCE_NODE_TYPES),
    }


def main(argv=None) -> int:  # pragma: no cover - 诊断入口（不读蓝图、不写文件）
    """打印能力表（只读，无副作用）。"""
    summary = registry_summary()
    print("Capability Registry v%d" % summary["version"])
    print("supported:          %s" % ", ".join(summary["supported"]))
    print("supported (assets): %s" % ", ".join(summary["supported_resources"]))
    print("reserved (locked):  %s" % ", ".join(summary["reserved"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
