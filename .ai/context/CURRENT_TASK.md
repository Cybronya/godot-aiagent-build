# 当前任务

## 目标

MCP 第三轮独立实战：新增「Boss Challenge」场景（三开关 → Boss 门 → 击败 Boss → 出口完成），验证多 Feature 组合复用与 Feature 边界判断（能力发现、组合、扩展、边界控制）。

## 当前状态

已完成并通过验证：

- **零新增 Feature、零 Feature 扩展**：12 条需求全部由既有 11 个 Feature 组合覆盖
- `Scenes/Boss.tscn`（实体场景）：纯组合 chase_movement（speed=55）+ Health（max=30）+ ContactDamage（damage=2, tick=0.4）+ HealthBar，差异全部用导出参数覆写，零新逻辑
- `Scenes/BossChallenge.tscn`（游戏场景）：机关关系全部由 5 条 tscn [connection] 数据表达：
  - SwitchA/B/C `activated(bool)` → ConditionGate `set_condition(value, id)` binds=[switch_a/b/c]（All 模式 AND 聚合，condition_count=3）
  - ConditionGate `fulfilled(bool)` → BossDoor `set_open(bool)`
  - **Boss Health `died()` → ExitDoor `set_open(bool)` binds=[true]**：无参死亡信号经 binds 常量注入直连目标方法，首次验证了「任意签名信号 + binds 常量」的数据连接形态，AD-005 契约的延伸实证
- `Scenes/boss_challenge.gd`（胶水，遵循 AD-003）：完成/失败判定、Boss 血量 HUD、状态文案、Boss 死亡表现（process_mode 停摆整棵子树，AD-002 死亡表现由订阅方决定）、重开轮询
- 玩家攻击复用既有胶水 `Scenes/attack_trigger.gd`：出现第二个真实消费者，按 AD-003 完成提升条件再评估，结论仍为「暂不 Feature 化」（详情见任务报告）

## 关键经验（供后续任务参考）

- 测试前置条件自污染：把「门关闭阻挡」断言放在触发开关之后执行，断言的不再是初始状态；验证初始状态必须放在任何状态变更之前
- 慢速实体（55px/s）追击断言不要用绝对距离阈值（240 帧 ≈ 220px，阈值 200 必然边界失败），用「位移量」断言更稳健
- 贴身节拍伤害会污染治疗/攻击断言：先脱离接触再治疗；攻击验证用「拉开距离再输出」的风筝时序模拟真实打法
- tscn 直连无参信号（died）+ 目标方法（set_open）：信号无参时 binds 提供全部实参，连接本身不需要胶水脚本参与

## 修改文件

- `Scenes/Boss.tscn`（新增）
- `Scenes/BossChallenge.tscn`、`Scenes/boss_challenge.gd`（新增）
- `Tests/test_boss_challenge.gd`(新增，含 A–N 十四阶段全链路验证)
- `.ai/context/CURRENT_TASK.md`（本文件）

## 验证结果

- BossChallenge 集成验证（真实场景全链路 14 阶段）：PASS
- 全量 Feature 回归：11/11 PASS（零 Feature 改动，全部原样通过）
- 既有场景测试：12/12 PASS（Escape Room / Survival Arena / ChestVault / ThreeAltarsPuzzle 等全部无回归）
- 场景无头启动：main / SurvivalArena / EscapeRoom / PlatformVault / ChestVault / ThreeAltarsPuzzle / BossChallenge 全部 0 错误
- Framework Validator：PASS（0 errors / 0 warnings）

## 下一步

无阻塞事项。成果未提交（等待用户指示）。
