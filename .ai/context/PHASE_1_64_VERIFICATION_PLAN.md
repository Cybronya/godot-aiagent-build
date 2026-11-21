# Phase 1.64 — Verification Plan

## 1. 风险评分规则（先定义，再排序）

```
risk = 2*impact + 2*state_risk + 3*data_loss + 1*event_complexity + 2*leak_risk + 2*gap(1-3) + (0 if readiness else 1)
```

| 输入 | 含义 | 取值 |
| --- | --- | --- |
| `impact` | 1=纯反馈/书签记；2=可感知但可恢复；3=玩家可见错误结果或状态损坏 | 见 taxonomy |
| `state_risk` | 1=单值单调变化；2=多步状态/时序；3=跨系统状态一致性（死亡/无敌/存档） | 见 taxonomy |
| `data_loss` | 0=不涉及持久化；3=存档写入/读取 | 见 taxonomy |
| `event_complexity` | 1=无信号或单信号；2=1-2 个信号且有时序；3=多信号+条件广播/去重 | 见 taxonomy |
| `leak_risk` | 0=无资源；1=瞬时对象；2=需显式释放的对象/池占用 | 见 taxonomy |

`gap` 由真实八维矩阵推导：Evidence 未 VERIFIED → 3；Evidence 已验证但 Evaluation `NOT_EVALUATED` → 2；其余 → 1。`readiness` 为 BLOCKED 时 +1。

**风险分不是行为正确性的证明**，只用于排批次先后。

## 2. 分批计划（每批 3–5 条，先同类、依赖清晰）

| 批次 | Behavior | 主类 | 为什么在这一批 | 验证动作 |
| --- | --- | --- | --- | --- |
| B1 | `health/damage`、`health/post_death_guard`、`openable_door/open`、`save_game/load_slot_restores_world_state` | A / F / A / C | 覆盖状态转换 + 守卫 + 持久化三类，且已有 1.59 L5 与 1.63 产物可对照 | 真机 evidence + signature + attestation + eval＋复跑既有 mutation |
| B2 | `i_frames/*`（3 条） | F/A | 无敌窗口是跨系统状态一致性最高风险区，已有 M09 单点证据 | 3 条全部证据化，补 mutation（窗口提前结束/不恢复） |
| B3 | `stun/*`（5 条） | A/F | 眩晕与伤害/死亡/治疗交叉，事件复杂度 3 | 5 条证据化，补「重复命中重复广播」mutation |
| B4 | `condition_gate/*`（3 条）+ `trigger_switch/*`（2 条） | F/A | 条件门控与锁存是事件传播核心 | 证据化 + 条件反转 mutation |
| B5 | `projectile/*`（3 条）+ `collect_pickup/collect_on_contact` | D/E | 资源生命周期与一次性语义 | 证据化 + 释放移除/重复释放 mutation |
| B6 | `sfx_pool/*`、`screen_shake/*`、`hit_flash/*` | D/B | 反馈层，影响低但覆盖缺口大 | 证据化（可批量），不优先做 mutation |

> 批次对象由本次审计的 risk_score 动态排序得出（见 INVENTORY §2），不是沿用历史结论。

## 3. 每条的验证流水线（固定 16 步）

1. 读契约 2. 读已审批 binding 3. 校验 contract_version 4. 读实现源码 5. 读依赖组件 6. 确认真实执行入口 7. 设计/确认场景 8. 真实 Godot 执行 9. 生成 Evidence 10. Artifact 交叉验证 11. Evidence Signature 12. Manifest 13. Attestation 14. 验签 15. Evaluation 16. 更新 Coverage Matrix。

Evidence Signature 与 Execution Attestation 是两个独立对象：前者证明内容未被篡改，后者把一次真实执行与产物集合绑定；有签名不等于执行被证明。

## 4. 推荐验证方式（按主类）

| 主类 | 推荐方式 |
| --- | --- |
| A State Transition | 真机 evidence（现有契约场景，replay=2）+ 状态写错/写漏 mutation |
| B Event Propagation | 真机 evidence + 信号计数/参数 mutation（丢广播、重复广播、错值） |
| C Persistence | 真机 evidence（隔离 user:// 目录，跨 run）+ 写入/读取 mutation |
| D Resource Lifecycle | 真机 evidence + 释放移除/池占用 mutation |
| E Interaction | 真机 evidence + 动作调用删除/参数写错 mutation |
| F Guard & Conditional Logic | 真机 evidence + 守卫删除/条件反转 mutation |

## 5. 阻塞与前置条件

- Godot 可执行文件：`env_paths.require_godot()` 统一解析（GODOT_BIN → 项目配置 → 相邻目录 → PATH）。
- 持久化类必须使用隔离 `user://`（`--user-dir-tag`），否则跨 run 残留会让「忘记写入」不可观测（M06 的教训）。
- 所有 mutation 必须在隔离副本里执行，仓库 `Features/**` 只读，恢复逐字节核对。

## 6. 首批验收门槛

- [ ] 3–5 条 Behavior 各自有真实 Run ID + Evidence Digest；
- [ ] Signature / Attestation 各自独立验证通过（不是同一份证明）；
- [ ] Evaluation `VERIFIED_PASS`（来自完整链路，不是改写期望）；
- [ ] Coverage Matrix 对应维度从 NO_* 变为已验证态；
- [ ] 失败（如有）保留证据与根因，不改期望绕过。
