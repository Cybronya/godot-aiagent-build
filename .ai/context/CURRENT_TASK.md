# 当前任务

## 目标

MCP 第六轮独立实战：真实需求驱动的 Feature Discovery / Reuse 判断——面对新 Gameplay 需求（受击行动中断 + 环境机关行动限制），先 Discovery 再决策：直接复用 / 扩展 / 新 Feature / Scene Glue，禁止为满足实验条件人为制造 Feature 或强行使用既有 Feature。

## Discovery 结论（2026-09-29）

- 玩家攻击能力已存在：`attack_trigger.gd`（胶水，p1_attack → 组内最近存活目标 take_damage），四场景消费中
- `Features/stun/` 接口核对：stun(duration)/stun_on_hit/health_path（缺省 ../Health 契约）/maxf 长盖短/_exit_tree 生命周期/死亡守卫——**全部满足新需求，零缺口**
- 契约缺口识别：TriggerSwitch `activated(bool)` 无法直连 `stun(float)`（bool 不可隐式转 float，tscn connection 直连不可行）；且需求 B 是「触发 → 指定第三方目标」，与 paralyze_trap 的「晕踩入者自身」路由不同——结论：写最小场景胶水 `stun_tripwire.gd`（踩踏 → target_path 目标的 Stun 主动 API），不扩展 TriggerSwitch、不扩展 stun、不新建 Feature

## 架构决策

- **Reuse（唯一决策）**：stun / health / chase_movement / player_movement / health_bar / openable_door / attack_trigger 全部直接复用，零修改
- **Extend：无**——stun 无缺口；新增 API 会扩大边界而无真实需求
- **New Feature：无**——两个需求均由既有能力组合满足，本轮不存在新能力缺口
- **Scene Glue**：`stun_tripwire.gd`（单消费者，提升条件 = 出现第二个「触发→指定目标行动限制」场景）；`interrupt_range.gd` 仅 R 重开轮询

## 当前状态

已完成并通过验证：

- **新场景 `Scenes/InterruptRange.tscn`**（复用组合，零新 Feature）：
  - 消费者A EnemyInstance（Enemy.tscn 实例 + 组覆写 + Stun stun_on_hit=true/0.6s）：受击硬直、到时恢复
  - 消费者B ReactiveTarget（CharacterBody2D + chase_movement 根脚本 + Health + Stun stun_on_hit=false，不入 enemies 组）：被绊线第三方定身 1.0s，chase 复用证明恢复后继续移动
  - `stun_tripwire.gd`：踩踏 → target_path 目标的 stun(duration)，不晕触发者自身
  - `died→ExitDoor set_open binds=[true]` 数据连接毕业（AD-005）
- **stun 获得第二个真实 gameplay 场景消费者**（InterruptRange），由需求 B 的真实目标路由需求驱动；Enemy/EliteEnemy/Player 原型仍未包含 Stun，未做人为扩展
- 实现期发现并修复：EnemyInstance 初版漏 enemies 组覆写（项目惯例：动态生成用胶水 add_to_group，静态实例在 tscn 覆写）

## 关键经验（供后续任务参考）

- tscn [connection] 直连目标 API 的前提是签名完全一致：bool 与 float 参数即使可绑定也不同构，直连不可行时用最小胶水路由而不是改契约
- 「触发 → 晕踩入者」（paralyze_trap）与「触发 → 定身指定目标」（stun_tripwire）是两种路由语义，不是同一胶水的参数差异
- 实体组合的「静态实例在 tscn 覆写组」与「动态生成在胶水 add_to_group」双惯例并存，实例化 Enemy 原型必须检查组覆写
- 写完 tscn 必须逐行逻辑自检（节点/资源/连接），一次物理通跑成本远低于排查失败断言

## 修改文件

- `Scenes/InterruptRange.tscn`（新增）
- `Scenes/stun_tripwire.gd(+.uid)`、`Scenes/interrupt_range.gd(+.uid)`（新增）
- `Tests/test_interrupt_range.gd(+.uid)`（新增，A–G 七阶段）
- `.ai/context/CURRENT_TASK.md`（本文件）

## 验证结果

- InterruptRange 集成验证（A–G 全链路）：PASS
- 全量回归：27/27 PASS（Feature 12 + Scene 15，逐文件清单核对）
- Round 5 回归证明：test_stun PASS + test_stun_training PASS（StunTraining 旧行为保持，stun 零修改）
- Framework Validator：PASS（0 errors / 0 warnings）
- Headless：InterruptRange / main / StunTraining / BossChallenge / TimedCombatArena 全部 0 错误

## 下一步

无阻塞事项。成果未提交（按 Round 6 指令等待审计）。
