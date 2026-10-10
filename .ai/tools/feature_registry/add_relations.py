#!/usr/bin/env python3
"""一次性迁移：为 Features/*/feature.yaml 追加 relations 字段。

relations 数据基于各 Feature 的 README/源码组合契约与 AD 结论人工核对（2026-10-08）。
本脚本只做「追加不存在的关系节」，不覆盖、不修改已有内容；幂等：已存在 relations 则跳过。
"""

import io
import os
import sys

TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
ROOT = os.path.dirname(TOOL_DOTAI)
FEATURES = os.path.join(ROOT, "Features")

# 人工核对的关系表：id -> relations 节 YAML 文本
RELATIONS = {
    "health": """\
relations:
  works_with: []
  commonly_used_with:
    - contact_damage
    - stun
    - heal_pickup
    - health_bar
  conflicts: []
  entity_roles:
    - player
    - enemy
    - destructible
""",
    "contact_damage": """\
relations:
  # requires 语义：需要目标侧存在提供 damage_receiver 能力的 Feature（即 health）
  requires: [damage_receiver]
  works_with:
    - stun
  commonly_used_with:
    - health
  conflicts: []
  entity_roles:
    - enemy
    - trap
""",
    "chase_movement": """\
relations:
  works_with: []
  commonly_used_with:
    - health
    - contact_damage
    - stun
  conflicts: []
  entity_roles:
    - enemy
""",
    "player_movement": """\
relations:
  works_with: []
  commonly_used_with:
    - health
    - health_bar
  conflicts:
    - chase_behavior   # 同一实体根同时被输入驱动与追击驱动互相冲突
  entity_roles:
    - player
""",
    "stun": """\
relations:
  # stun_on_hit 模式依赖宿主 Health（damage_receiver 能力）
  requires: [damage_receiver]
  works_with:
    - contact_damage
  commonly_used_with:
    - health
    - chase_movement
  conflicts: []
  entity_roles:
    - enemy
    - player
""",
    "health_bar": """\
relations:
  # 显示依赖 health_state（只读订阅）
  requires: [health_state]
  works_with: []
  commonly_used_with:
    - health
  conflicts: []
  entity_roles:
    - player
    - enemy
""",
    "heal_pickup": """\
relations:
  # 目标消费方是 damage_receiver/heal_receiver（health）
  requires: [heal_receiver]
  works_with: []
  commonly_used_with:
    - health
  conflicts: []
  entity_roles:
    - world_item
""",
    "collect_pickup": """\
relations:
  works_with:
    - condition_gate
  # collected 直连 ConditionGate（AND 聚合）
  commonly_used_with:
    - condition_gate
  conflicts: []
  entity_roles:
    - world_item
    - key_item
""",
    "condition_gate": """\
relations:
  works_with:
    - collect_pickup
    - trigger_switch
  commonly_used_with:
    - openable_door
  conflicts: []
  entity_roles:
    - logic
""",
    "trigger_switch": """\
relations:
  works_with:
    - condition_gate
  commonly_used_with:
    - openable_door
  conflicts: []
  entity_roles:
    - logic
    - trap
""",
    "openable_door": """\
relations:
  works_with:
    - condition_gate
    - trigger_switch
  commonly_used_with:
    - collect_pickup
  conflicts: []
  entity_roles:
    - logic
    - level_geometry
""",
    "moving_platform": """\
relations:
  works_with: []
  commonly_used_with:
    - player_movement
  conflicts: []
  entity_roles:
    - level_geometry
""",
}


def main() -> int:
    changed, skipped = [], []
    for fid, block in sorted(RELATIONS.items()):
        path = os.path.join(FEATURES, fid, "feature.yaml")
        if not os.path.isfile(path):
            print("FAIL: missing feature.yaml for %s" % fid, file=sys.stderr)
            return 1
        text = io.open(path, encoding="utf-8").read()
        if "relations:" in text.replace("  # requires 语义", ""):
            # 粗判：已有 relations 节则跳过（幂等）
            for line in text.splitlines():
                if line.strip() == "relations:" or line.startswith("relations:"):
                    skipped.append(fid)
                    break
            else:
                skipped.append(fid)
            continue
        new_text = text.rstrip("\n") + "\n\n" + block
        io.open(path, "w", encoding="utf-8", newline="\n").write(new_text)
        changed.append(fid)
    print("OK: relations added to %d feature.yaml (%d skipped)" % (len(changed), len(skipped)))
    if skipped:
        print("Skipped: " + ", ".join(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
