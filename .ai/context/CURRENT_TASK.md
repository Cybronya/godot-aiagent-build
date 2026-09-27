# 当前任务

## 目标

MCP 第四轮独立实战：新增「Timed Combat Arena」场景（波次生成 + 存活计数 + 阶段倒计时 + 终波开门），验证能力缺口识别与 Feature 边界判断（组合 / 扩展 / 新建三路决策）。

## 当前状态

已完成并通过验证：

- **零新增 Feature；一处既有胶水通用性扩展**：
  - `Scenes/attack_trigger.gd`（胶水，非 Feature）：保留固定路径模式原语义，新增可选 `target_group` 动态目标模式（攻击时解析组内最近存活实体的 Health）。动机：本场景敌人为波次动态生成，固定单目标不适配；解析规则完全通用（组 + Health 命名约定，AD-004 契约），main.tscn / BossChallenge 两个既有消费者零改动回归通过
- `Scenes/TimedCombatArena.tscn` + `Scenes/timed_combat_arena.gd`（胶水，遵循 AD-003）：
  - 波次数据驱动（`waves: Array[Dictionary]`：enemy_scene/enemy_count/elite_scene/elite_count/duration），三波配置 = 普通×3 / 混编 2+1 / 混编 4+1，同一套机制覆盖多种敌人配置（需求 17）
  - 死亡接线复用 Health.died 信号（`died→queue_free` + `died→计数`，survival_arena 先例模式）
  - 提前清场同帧推进下一阶段（died 回调同步性）；终波清场后 `ExitDoor.set_open(true)`
  - 超时失败（倒计时耗尽仍有存活）、出口完成、玩家死亡失败、R 重开
- 计时/波次/计数的 Feature 提升条件（AD-003 记录）：出现第二个需要独立计时/波次编排的场景

## 关键经验（供后续任务参考）

- 场景胶水的扩展判断：固定目标 → 动态目标组是「同一职责的目标解析策略扩展」，属于胶水自身通用性提升，不是 Feature 化时机
- died 回调是同步的：最后一个敌人死亡会在同一调用栈内触发波次推进与新波生成，测试断言「清空后计数」必然观测到新波计数；中间态要用单个死亡验证
- queue_free 的节点在帧末才真正出树：同帧统计场景子节点必须过滤 `is_queued_for_deletion()` 或先 `await process_frame`
- 几何自检：两段对称墙的「长度 + 间距」必须显式留出门洞（412×2 @±206 = 无洞全遮挡；348×2 @±238 = 留 y∈[-64,64] 门洞）

## 修改文件

- `Scenes/attack_trigger.gd`（扩展：动态目标模式，向后兼容）
- `Scenes/TimedCombatArena.tscn`、`Scenes/timed_combat_arena.gd`（新增）
- `Tests/test_timed_combat_arena.gd`（新增，A–L 十二阶段）
- `.ai/context/CURRENT_TASK.md`（本文件）

## 验证结果

- TimedCombatArena 集成验证（真实场景 12 阶段全链路）：PASS
- 全量回归：24/24 PASS（11 Feature + 13 场景测试；attack_trigger 既有消费者 test_damage_interaction / test_boss_challenge 均原样通过）
- Framework Validator：PASS（0 errors / 0 warnings）
- 场景无头启动：8 个场景（含新增）全部 0 错误

## 下一步

无阻塞事项。成果未提交（等待用户指示）。
