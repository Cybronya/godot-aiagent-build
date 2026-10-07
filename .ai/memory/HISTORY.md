# History

记录AI工作历史和项目重要变化。

## 实验系列档案（自 CURRENT_TASK.md 归档，Round 5 → 8）

### 实验递进

```text
Round 5  新 Feature 边界（stun 四件套 + 消费者实证）
        ↓
Round 6  已有 Feature 真实复用（stun 获第二个跨场景消费者）
        ↓
Round 7  多 Feature 组合 + Do Not Reuse（纯组合满足资源收集）
        ↓
Round 8  多机制汇聚 + 状态所有权（同一实体，零仲裁）
```

### Round 5/6 关键事实

详见 git 历史 `11c0664`、`924beb1`：stun Feature 创建时通过消费者独立性核验确立「场景内多配置 ≠ 多消费者」标准；InterruptRange 使 stun 获得第二个真实 gameplay 场景消费者，复用由设计论证升级为跨场景实证。

### Round 7 关键结论（Harvest Grove，commit `8a8ef19`，5 文件）

在多 Feature 组合中验证了两次 **Do Not Reuse**：

1. MovingPlatform 的 RideZone 不承载 CollectPickup——类型/接口语义不匹配（body_entered 面向 PhysicsBody2D，CollectPickup 是 Area2D）；改用父子节点组合（父变换传播）实现移动资源
2. TriggerSwitch 不做收集完成判定——几何核算（触发半径 40 > 门心距可达边界 12px）证明资源未集齐即会提前触发；完成语义改由 `collected → ConditionGate → fulfilled → Door/Glue` 表达

其他已验证事实：collect_pickup 经 `collected` 信号与 ConditionGate 无胶水直连（pickup_id 即条件 id）；MovingPlatform 零修改即可承载移动资源且资源保持自身收集行为；静态/移动两种资源配置并存；Round 7 零 Feature 修改。AD 候选（父子组合模式、触发器空间适配）同因单次证据暂缓。

### Round 8：Siege Gate（commit `c76de23`）——多机制汇聚于同一实体

目标：验证 Agent 能否识别状态所有权，让各 Feature 自己维护状态并通过公开接口被多路径触发，而不是创建跨 Feature 的仲裁器 / Manager 类抽象。

核心实体组合（既有 Enemy.tscn 实例 + 组合扩展，全部 Feature 零修改）：

```text
Guard（CharacterBody2D, chase 根脚本）
├── Health          （HP / 死亡）
├── Stun            （行动限制，stun_on_hit=true）
├── ContactDamage   （对玩家的接触伤害线）
└── ChaseMovement   （追击线）
```

三条机制线作用于同一个 Stun 实例 + 一条数据连接：

```text
Health.health_changed → Stun 被动触发（受击硬直）
Tripwire(stun_tripwire.gd) → Stun.stun(duration)（环境主动 API）
击杀 → Health 死亡守卫拒绝一切后续 Stun
Guard/Health.died → OpenableDoor.set_open(true)（tscn [connection] binds=[true]）
```

状态所有权结论：

- **Health** 拥有：HP、death state；已有死亡守卫处理死亡目标的一切后续伤害/治疗（no-op）与死亡状态本身
- **Stun** 拥有：眩晕状态、剩余时长；已有语义 = 长盖短（maxf）、重入不产生第二套状态（幂等广播）、死亡目标拒绝新 stun、死亡宿主不被恢复逻辑重新激活（`_process`/`_exit_tree` 双守卫）
- **OpenableDoor** 拥有：门开关状态；已有 `set_open` 幂等；多事件源可汇入同一门状态（天然 OR）
- **Scene Glue** 只负责：事件连接、目标路由、场景编排、重开；不拥有 HP / Stun / Door 状态、不做伤害计算、不做状态仲裁

核心结论：四条机制线可以汇聚到同一个实体，但不意味着需要新的「状态仲裁器」。实际形态为 `Feature → 拥有自己的状态 → 公开行为接口 → Scene Glue 负责连接`，而非 `多个 Feature → Global / Scene Manager → 统一仲裁所有状态`。本轮没有创建仲裁器，也没有创建新的 Feature；冲突语义（长盖短/幂等/死亡守卫）全部内置于各 Feature，场景层零仲裁代码。

Reuse / Extend / New Feature / Glue：

- **Reuse（全部零修改）**：health、stun、openable_door、contact_damage、chase_movement、player_movement、health_bar、attack_trigger、stun_tripwire（Round 6 场景胶水的跨场景复用）
- **Extend：无**
- **New Feature：无**——没有因为「多个机制汇聚于同一实体」而创建 Manager / Arbiter / Controller 类新抽象
- **Scene Glue**：`Scenes/siege_gate.gd` 职责仅为场景重开轮询；Death → Door 由 TSCN signal connection 表达

测试证据（Tests/test_siege_gate.gd A–E，行为级断言）：

1. 被动与主动 Stun 使用同一个 Stun 实例（子节点计数 = 1 + 双路径同节点触发）
2. 长 Stun 覆盖短 Stun（被动 0.6s 过期后仍处于主动 1.0s 眩晕中）
3. 重入不创建第二套 Stun 状态（重入期间零新广播，全程恰好 true+false 各一次）
4. 击杀一击后不会出现能重新激活死亡宿主的 Stun（死亡宿主过恢复点后物理仍停摆）
5. 死亡后主动 Stun 请求被拒（直接 API 与绊线路径双验证）
6. `died → set_open(true)` 正常工作
7. R 重开后上述机制可再次运行（满血/门关/配置重建/双路径复现）

验证结果（Round 8 提交前审计在当前磁盘状态重跑确认）：

```text
Feature tests: 12/12
Scene tests:   17/17
Total:         29/29
Validator:     0 errors / 0 warnings
Headless:      7 scenes, 0 errors（SiegeGate/StunTraining/InterruptRange/HarvestGrove/main/BossChallenge/TimedCombatArena）
```

AD 候选（暂不新增正式 AD）：当多个触发路径作用于同一个状态域时，应优先由该状态的 Feature 定义冲突语义，而不是让 Scene Glue 仲裁。不升格原因：与既有 AD（002/005）方向一致，属推论而非独立新决策；待出现第一个需要在 Glue 层仲裁的真实案例再评估。

### Round 8 后续处置记录

- `project.godot`：外部 `MCPRuntimeProbe` autoload 残留（godot_mcp 插件动态注册、进程超时中断所致）已完成来源核查——`uid://bsg12huaf1u5i` 与插件 probe 脚本 `.uid` 逐字匹配，确认不属于 Round 8 实验代码；Round 8 提交明确排除了该外部修改。后续任务经最小范围恢复（`git restore -- project.godot`）回到 HEAD 基线
- 6 个历史遗留 `.uid`（moving_platform×2、platform_vault×1、test_boss_challenge×1、test_platform_vault×1、test_timed_combat_arena×1）：已完成零引用核查并清理删除；Godot 运行时按需重新生成
