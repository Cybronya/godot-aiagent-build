# Phase 1.45 审计报告 — Behavior Coverage & Evidence Integrity

> 范围：Phase 1.40–1.44 建立的行为证据体系（协议 v2 / 探针 / 编排器 / 实例证据 / CLI 门禁）
> 性质：审计为主，修复仅限「已复现的误报路径」
> 结论先行：**发现并修复 1 条可复现的 PASS 误报路径**（零帧推进 + 纯否定期望 → 无观测窗口仍 PASS）；
> 其余 16 条已声明 behavior 与全部既有实例证据无回归。**组合场景仍不在行为证据可执行范围内**，
> 端到端链目前只能由 Godot `SceneTree` 集成测试证明，不能由行为契约证明。

---

## 1. 仓库初始状态与保护措施

### 1.1 Git 与工作区（事实，可复核）

| 项目 | 值 |
| --- | --- |
| HEAD | `1c30f94f95c6594c34ba296fe339455b0de10625`（2026-10-20 01:05:31 +0800） |
| 分支 | `master` |
| 工作区入口状态 | 35 个 `M` + 28 个 `??`（共 63 条），全部来自 Phase 1.25–1.44，非本次审计产生 |
| 暂存区 | 空（未执行任何 `git add`） |
| 本次结束状态 | 仍为 35 `M` + 28 `??`，HEAD 未变，无提交、无推送、无 reset/clean/checkout/restore |

既有未提交修改（示例，未逐一列出）包括 `.ai/context/*`（Phase 1.30–1.44 报告）、
`Features/*/template.yaml`、`Orchestration/level_config.gd`、`Tests/test_*.gd`、
`.ai/tools/run_tests.py`、`.ai/tools/validator/validate.py`。行为证据相关代码
（`behavior_protocol.py`、`feature_behavior_evidence.py`、`runtime_instance_evidence.py`、
`probes/`、5 个行为测试文件）本身处于 `??` 未跟踪状态。

### 1.2 测试基线

| 口径 | 基线（Phase 1.44 结束） | 本次（Phase 1.45 结束） |
| --- | --- | --- |
| `run_tests.py` | 93/93 PASS（Godot=38，Python=55） | 93/93 PASS（Godot=38，Python=55） |
| `test_feature_behavior_evidence.py` | 162 条断言 PASS | 169 条断言 PASS |
| 行为 CLI 门禁 | 17 behavior / 17 PASS | 17 behavior / 17 PASS（replay=2） |
| Validator | 0 error / 17 warning | 0 error / 17 warning |

### 1.3 保护措施（本次实际执行）

1. 所有缺陷注入均在 `.ai/tmp/` 下的**隔离副本**中进行（`BehaviorWorkspace` 临时 Godot 项目，或
   `Features/<f>/` 的独立副本），结束后逐字节恢复并比对 SHA256；仓库内 golden 文件哈希在对照
   前后一致（`test_feature_behavior_evidence.py` Case 11 显式断言）。
2. 未删除任何既有生成物；本阶段的日志/复现脚本写入 `.ai/tmp/`（`.gitignore:34` 已忽略）。
3. 审计发现（第 3–7 节）与实际修复（第 8 节）分开记录。
4. 未扩展协议 v2：本次修复只增加一条**契约合法性规则**，未新增动作、观测或 manifest 能力。

---

## 2. 完整 Feature 覆盖矩阵

仓库共 **12 个正式 Feature 目录**（`Features/*/`，含 `feature.yaml` 与 `template.yaml`）。
枚举来源是目录本身，不是行为 CLI 的输出。

### 2.1 分类定义（互斥）

| 分类 | 含义 |
| --- | --- |
| `RUNTIME_VERIFIED` | 该 Feature **声明的每个 behavior** 都有真实 Godot 运行时证据，且 ≥2 次重放一致 PASS |
| `PARTIAL` | 有运行时证据，但存在已声明的关键边界未验证，或证据仅覆盖部分声明行为 |
| `UNIT_TESTED` | 无行为声明；只有 Feature 级 Godot 单元测试（真实运行时，但不是行为契约证据） |
| `STATIC_ONLY` | 只有静态/实例结构证据 |
| `UNVERIFIED` | 没有足以支持行为结论的证据 |

> 说明：`UNIT_TESTED` 是在题目示例之外显式补充的类别。本仓库有 3 个 Feature 不声明 behavior，
> 但各有真实 Godot 单元测试；把它们归入 `STATIC_ONLY` 会低报证据，归入 `RUNTIME_VERIFIED`
> 会高报（没有任何声明行为被验证），因此单列并在此登记。

### 2.2 矩阵

| # | Feature | 目录 | 声明 behavior | 专用 `behavior[].scene` | 运行时证据 | 重放 | 缺陷注入对照 | 静态实例证据 | 运行时实例证据 | 分类 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `chase_movement` | `Features/chase_movement/` | 2 | 是（`ChaseTargetFixture.tscn`） | 2/2 PASS | 2 | 是（2 处缺陷 + CLI 非零退出） | 无 | 无 | `RUNTIME_VERIFIED` |
| 2 | `collect_pickup` | `Features/collect_pickup/` | 1 | 否（入口场景） | 1/1 PASS | 2 | 无 | 是 | 是 | `RUNTIME_VERIFIED` |
| 3 | `condition_gate` | `Features/condition_gate/` | 3 | 是（`ConditionGateFixture.tscn`） | 3/3 PASS | 2 | 是（阈值缺陷 + CLI 非零退出） | 无 | 无 | `RUNTIME_VERIFIED` |
| 4 | `health` | `Features/health/` | 3 | 否（入口场景） | 3/3 PASS | 2 | 无 | 无 | 无 | `RUNTIME_VERIFIED` |
| 5 | `heal_pickup` | `Features/heal_pickup/` | 1 | 否（入口场景） | 1/1 PASS | 2 | 无 | 是 | 是 | `RUNTIME_VERIFIED` |
| 6 | `moving_platform` | `Features/moving_platform/` | 2 | 否（入口场景） | 2/2 PASS | 2 | 是（运动公式缺陷 + 窗口耗尽） | 是 | 是 | `RUNTIME_VERIFIED` |
| 7 | `openable_door` | `Features/openable_door/` | 1 | 否（入口场景） | 1/1 PASS | 2 | 是（no-op / 反向状态 / 入口移除） | 是 | 是 | `RUNTIME_VERIFIED` |
| 8 | `player_movement` | `Features/player_movement/` | 2 | 否（入口场景） | 2/2 PASS | 2 | 无 | 是 | 是 | `RUNTIME_VERIFIED` |
| 9 | `trigger_switch` | `Features/trigger_switch/` | 2 | 否（入口场景） | 2/2 PASS | 2 | 无（Phase 1.45 新增了「应不触发」负向契约回归，见 §8） | 是 | 是 | `RUNTIME_VERIFIED` |
| 10 | `contact_damage` | `Features/contact_damage/` | 0 | — | 仅 `Features/contact_damage/test_contact_damage.gd` | — | — | 无 | 无 | `UNIT_TESTED` |
| 11 | `health_bar` | `Features/health_bar/` | 0 | — | 仅 `Features/health_bar/test_health_bar.gd` | — | — | 无 | 无 | `UNIT_TESTED` |
| 12 | `stun` | `Features/stun/` | 0 | — | 仅 `Features/stun/test_stun.gd` | — | — | 无 | 无 | `UNIT_TESTED` |

合计：**9 个 Feature 声明 17 条 behavior**；6 个 Feature 声明静态 + 运行时实例证据
（Validator 口径：`6 declared / 12 checked`）。

### 2.3 逐条 behavior 证据（17 条，全部 `--replay 2` PASS）

| Feature | behavior | 观测窗口 | 动作 | 后置断言（摘要） |
| --- | --- | --- | --- | --- |
| chase_movement | `approach_target` | 1 | advance 60f | chaser +x 位移 ∈[57.5,62.5]；y≈0；target 仍 300；Chaser 存在 |
| chase_movement | `hold_without_target` | 1 | advance 30f | x/y 位移 = 0（±0.01） |
| collect_pickup | `collect_on_contact` | 30 | physics.overlap | 节点 freed；`pickup.collected` = 1 |
| condition_gate | `partial_conditions_block_output` | 10 | overlap+6f | 仅 A 触发；B 未触发；门关；`door.state_changed` = 0 |
| condition_gate | `all_conditions_fulfill` | 10 | overlap+6f ×2 | 双触发；门开；`state_changed` = 1 |
| condition_gate | `condition_fallback_withdraws_output` | 10 | overlap+6f ×3 | 条件回落后门关；`state_changed` = 2 |
| heal_pickup | `heal_damaged_target` | 30 | overlap(health_max 5, damage 3) | `@actor/Health`.current = 4；拾取物 freed |
| health | `damage` | 10 | take_damage 4 | current = 1；`health_changed` = 1 且 `last_args=[1,4]` |
| health | `heal_clamped` | 10 | damage 4 + heal 99 | current = 5（上限截断）；`health_changed` = 2 |
| health | `death` | 10 | take_damage 5 | current = 0；is_dead；`died` = 1 |
| moving_platform | `travel` | 1 | advance 60f | x 位移 ∈[98,102]；y≈0 |
| moving_platform | `round_trip` | 1 | advance 240f | x 位移 = 0（±2.0） |
| openable_door | `open` | 12 | door.set_open true | is_open；`state_changed` = 1 且 `last_args=[true]` |
| player_movement | `move_right` | 1 | press+1f+12f | x 位移 ∈[43.5,44.5]；y≈0 |
| player_movement | `stop_on_release` | 1 | press+1f+12f+release+12f | x 位移仍 ∈[43.5,44.5] |
| trigger_switch | `latch_once` | 30 | overlap+6f+overlap | 触发；`activated` = 1 且 `last_args=[true]` |
| trigger_switch | `toggle_on_second_contact` | 30 | 夹具 Toggle + overlap×2 | 未触发；`activated` = 2 且 `last_args=[false]` |

### 2.4 矩阵不能推出的结论

- 9 个 `RUNTIME_VERIFIED` **不等于**「该 Feature 的全部功能已验证」。每个 Feature 的
  `interfaces` 声明的 3–6 个方法/信号中，多数只有 1–3 个进入行为契约；
  例如 `health` 只验证 damage/heal/death 三条路径，未验证 `max_health` 配置变更、负伤害、
  死亡后再受伤等边界。
- `UNIT_TESTED` 的 3 个 Feature（`contact_damage`、`health_bar`、`stun`）**没有任何**
  行为契约证据与实例证据；它们在组合场景中的真实交互（§4）不由本体系证明。

---

## 3. PASS 判定可信度审计

### 3.1 A. 契约来源

| 检查点 | 结论 | 依据 |
| --- | --- | --- |
| 期望值是否来自源码/契约 | 是 | 数值均有源码推导注释：平台 100 px/s→60 帧 98..102；玩家 44 px/12 帧→43.5..44.5；health max 5；chase 夹具 speed 60 px/s→57.5..62.5 |
| 是否存在为适配实现而放宽区间 | 未发现 | 区间宽度均为 ±1 帧或 ±0.5–2 px 量级的物理边界容差，且注释写明来源；未见「扩大到任意值」的断言 |
| 是否存在制造最终结果的证据场景 | 部分动作自带前置条件，已登记 | `heal_pickup` 的 `physics.overlap` 参数 `health_max:5, damage:3` 制造「已受伤目标」；`trigger_switch.toggle_on_second_contact` 用 `state.set_property` 夹具切换 Toggle。两者都只**构造前置状态**，最终状态（current=4、signal count=2）仍由被测组件产生 |
| 夹具专用参数是否被误当默认配置覆盖 | 已区分 | Toggle 模式由显式夹具构造并有注释；默认 Latching 模式由 `latch_once` 覆盖。但 **Toggle 是唯一通过夹具验证的配置**，其他 export（`cooldown` 等）无证据 |
| 专项场景是否绕过组合入口 | 是（有意的设计） | `ChaseTargetFixture.tscn` / `ConditionGateFixture.tscn` 只服务于需要外部目标的 behavior；`scene` 只改证据场景，不改 `composition.entry_scene`（协议注释明确） |

### 3.2 B. 后置条件

| 风险 | 结果 |
| --- | --- |
| 只检查「节点存在」 | 仅 `condition_gate.all_conditions_fulfill` 等含 `node.exists` 作为**附加**断言，不作为唯一断言；`hold_without_target` 等纯否定期望见 §3.3 |
| 只检查最终状态 | 15/17 同时断言**状态 + 信号次数**；`health.damage`、`openable_door.open`、`trigger_switch.*` 还断言 `last_args`（事件参数） |
| 中间状态 | `condition_gate.condition_fallback_withdraws_output` 用 `state_changed = 2` 证明「先开后关」发生了两次，而不是只看到最终关闭；这是本体系中唯一显式验证**事件次数递增**的中间态 |
| 弱断言 | `health.heal_clamped` 的 `current == 5` 与动作前状态相同，**单看状态无法区分「治疗生效并截断」和「什么都没发生」**；判别力实际来自 `health_changed = 2`。已登记为弱断言（可接受，但不应被引用为「治疗逻辑已验证」的独立证据） |
| 「已证明没有发生」vs「未能观察到」 | 探针把不可达目标/方法映射为 `UNAVAILABLE` → 整条报告 `INSUFFICIENT`，不会折叠成「未发生」。`signal count: 0` 只有在信号注册成功时才有意义（注册失败 → `UNAVAILABLE`） |

### 3.3 C. 观察窗口与时间语义 —— **本阶段的核心缺陷**

**探针执行语义（事实，`probes/feature_behavior_probe.gd:320-347`）**：

1. 动作序列执行完毕后，**先在 `waited = 0` 取一次观测**；
2. `while waited < window_frames and not _all_pass(checks)` 逐物理帧轮询；
3. 全部 PASS → `PASS`；窗口耗尽仍有非 PASS → `MISMATCH`（`waited_frames == window_frames`，Case 3 断言）；
4. 任一检查 `UNAVAILABLE` → 覆盖为 `INSUFFICIENT / check_unavailable`。

**缺陷 P1（已复现、已修复）**：当契约的**动作不推进任何物理帧**、且期望**只断言「什么都没发生」**
（`signal count: 0` 或布尔 `equals: false`）时，第 1 步的观测即满足全部期望 →
返回 `PASS`，`waited_frames = 0`。此时「应不触发」的结论没有任何时间窗口支撑：
一个真实缺陷（1 帧后才触发）会被判成 PASS。

复现证据（隔离工作区、同一契约、仅移除探针守卫）：

```
AFTER  probe sha256: 5045ab75dcf15ddd08f3eecd1ae8cc946831da2807c46596ace3cbb3f09ee7ef
AFTER  status=INVALID reason=contract_invalid waited=None
       detail=expected only asserts absence of behaviour while no action advances frames; no observation window
BEFORE probe sha256: 62ca81eea32bd5ffcd3aac91214e16380b0309988b782fdccb47a8c18221b8b7
BEFORE status=PASS reason= waited=0 action_executed=True observed=False
```

即：修复前同一契约 `PASS / waited_frames=0 / observed=False`，修复后 `INVALID / contract_invalid`。
最小复现脚本：`.ai/tmp/t145_prefix_repro.py`（本次运行创建，`.ai/tmp/` 已被忽略）。

**未修复的相邻风险（已登记，未在现有 17 条契约上触发）**：
「正面期望在动作前就已成立」的契约（例如初始 `is_open = true` 时断言打开）仍可在 `waited=0`
PASS。现有 17 条契约通过 `preconditions` 或「区间不含 0」避免了这一点，但协议层没有通用规则。
修复它需要逐检查点比较「动作前基线」与「首个观测点」，会改变 PASS 语义，本阶段不实施（§10）。

**不构成缺陷的语义**：窗口内任一轮询帧满足全部期望即 PASS，是有意设计——它验证「在有界时间内
到达断言状态」，而不是「恰好第 N 帧到达」。因此 `first_observed_frame` 只作为证据记录，
不参与重放比较（§3.4），也不应被解读为时序保证。

### 3.4 D. 重放一致性

参与比较的字段（`BehaviorRun.fingerprint()`）：`status`、`reason`、`action_executed`、
以及每条检查的 `check / target / entry / expected / observed / status`。

有意排除：`run_id`、`replay_index`、`action_frame`、`observed_frame`、`observed_physics_frame`、
`waited_frames`、`window_frames`、`first_observed_frame`、`duration_s`、`artifacts`、`errors`。

| 检查点 | 结论 |
| --- | --- |
| 排除依据 | 帧号/时长属于调度差异与非语义字段；探针每次都在独立进程与独立场景副本中运行，绝对帧号不可比 |
| 是否忽略改变正确性结论的状态 | 未忽略：`observed` 与每条检查的 `status` 都在比较范围内，因此「两次都观察到同一错误值」会稳定判为同结果 |
| 两次都稳定失败于同一错误行为、却因契约过弱而通过 | **仍可能存在**——这是契约质量问题，不是重放比较问题。已逐条登记弱断言（§3.2 `heal_clamped`） |
| PASS 但重放不一致 | 被降级为 `INSUFFICIENT / replay_inconsistent`，绝不保留 PASS |
| FAIL 但重放不一致 | 保持 `MISMATCH`（不会因不一致而升级为 PASS，方向安全） |
| 时序是否可比 | **否**：`waited_frames`/`first_observed_frame` 被排除，因此「本次 2 帧、下次 9 帧」仍算一致。本体系**不提供延迟上界结论** |

### 3.5 E. 失败状态分类

| 状态 | 触发条件（事实，`judge()` + 探针） | 边界确认 |
| --- | --- | --- |
| `PASS` | 全部检查 PASS + `action_executed=true` + ≥1 条检查 + stderr 无加载/脚本错误 | 三项前置任一缺失即降级（Case 2 验证「状态凑巧符合但动作未执行」→ `INSUFFICIENT`） |
| `MISMATCH` | 观察到与后置条件矛盾（`state_mismatch`/`signal_mismatch`/`node_mismatch`/`load_error`/`script_error`） | 窗口耗尽仍不满足 → `MISMATCH` 且 `waited_frames == window_frames`（Case 3） |
| `INSUFFICIENT` | 动作入口不可用、采集失败/超时、检查目标不可用、重放不一致、Godot 不可用、前置条件不满足 | 均不得 PASS（Case 2/5/8/9） |
| `INVALID` | 契约/协议/场景路径非法（动作、参数、检查、目标、窗口、重复 id、场景越界、Phase 1.45 新增「无观测窗口」规则） | 不启动 Godot（Case 6/13） |
| `NOT_DECLARED` | Feature 未声明 behavior | 显式报告，不静默跳过（Case 7） |
| CLI 退出码 | `PASS=0`；`MISMATCH/INVALID=1`；`INSUFFICIENT` 默认 0，`--require-behavior` 时 1 | Case 10 全覆盖；门禁运行使用 `--require-behavior`（本次 exit=0） |

未发现「协议/场景路径非法被当作普通证据不足」的路径：探针在 `INVALID` 分支直接返回，
Python 侧在启动 Godot 前做同一套校验。

---

## 4. 负向对照与缺陷检测能力

所有注入均在隔离副本内完成，结束后按 SHA256 逐字节恢复；仓库 golden 文件哈希前后一致。

| 被测行为 | 注入的缺陷 | 期望判定 | 实际 | 证据位置 |
| --- | --- | --- | --- | --- |
| `openable_door.open` | `set_open` 改为 no-op | `MISMATCH/state_mismatch` + 满窗口 | ✅ | `test_feature_behavior_evidence.py` Case 11-控件 1 / Case 3 |
| `openable_door.open` | `_apply(value)`→`_apply(false)`（永远关门） | `MISMATCH`，`observed=false` | ✅ | 同上 控件 2 / Case 4 |
| `openable_door.open` | 删除动作入口方法 | `INSUFFICIENT/action_unavailable` | ✅ | 同上 控件 3 |
| `moving_platform` | 运动公式改为不移动/错误相位 | CLI 非零退出 | ✅ | `test_behavior_time_driven.py` Case 6 |
| `chase_movement` | 追击失效（仍能通过无目标用例） | `approach_target` MISMATCH、`hold_without_target` 仍 PASS | ✅ | `test_chase_movement_behavior.py` Case 2 |
| `chase_movement` | 空闲漂移（仍能通过追击用例） | `hold_without_target` MISMATCH | ✅ | 同上 |
| `condition_gate` | `condition_count` 阈值失效 | 部分条件用例 MISMATCH、全条件用例仍 PASS | ✅ | `test_condition_gate_behavior.py` Case 2 |
| `trigger_switch` | 「应不触发」契约 + 零帧 | **修复前 PASS（误报）** | ✅ 已修复 | 本报告 §3.3、Case 13 |
| 协议层 | manifest 与协议漂移 | `INVALID/protocol_invalid`，不启动 Godot | ✅ | `test_behavior_time_driven.py` Case 6 |
| 观测层 | 检查目标不可用 | `INSUFFICIENT/check_unavailable` | ✅ | 同上 |

**检测能力结论（事实）**：缺陷注入证明本体系能区分
「状态不变 / 反向变化 / 入口缺失 / 运动公式错误 / 阈值错误 / 目标漂移」六类真实缺陷，
且每个对照都同时验证了「未被注入的相邻行为仍然 PASS」——即对照本身不是靠放宽契约取胜。

**检测能力缺口（事实）**：`health`、`collect_pickup`、`heal_pickup`、`player_movement`、
`trigger_switch`（Latching 正向路径）**没有**行为级缺陷注入对照。
它们的 PASS 只由「契约 + 真实运行」支撑，未被证明「若实现变坏会被抓到」。
本阶段不重复注入同类缺陷（题目要求），仅登记为已知缺口。

---

## 5. 组合场景准备度

### 5.1 `Scenes/EscapeRoom.tscn`

| 项目 | 内容 |
| --- | --- |
| 组合 Feature | `player_movement`（Player）、`trigger_switch` ×2（SwitchA/SwitchB）、`condition_gate`（condition_count=2）、`openable_door`（ExitDoor） |
| 关键节点路径 | `Player`、`Mechanism/SwitchA`、`Mechanism/SwitchB`、`Mechanism/ConditionGate`、`Mechanism/ExitDoor`、`Mechanism/EscapeZone`、`HUD/StatusLabel` |
| 信号连接（场景数据，非胶水） | `SwitchA.activated → ConditionGate.set_condition(binds=["switch_a"])`；`SwitchB.activated → ConditionGate.set_condition(binds=["switch_b"])`；`ConditionGate.fulfilled → ExitDoor.set_open` |
| 胶水脚本 | `Scenes/escape_room.gd`：胜利文案、`escape_finished` 信号、按 R 重载（不参与机关关系） |
| 现有证据 | `Tests/test_escape_room.gd`（真实输入驱动：踩开关、被门物理阻挡、双条件开门、真实穿出、离开不重置、按 R 重置） |
| 行为证据覆盖 | 只能分别覆盖 `trigger_switch.*`、`openable_door.open`、`player_movement.*` 的单组件行为；**无法**覆盖本场景 |
| 仅被静态检查 | 信号连接条数（`get_signal_connection_list` 大小 == 1）、Feature 节点存在 |
| 夹具 vs 正式场景差异 | 行为证据使用 `Features/*/` 内的入口场景/专用夹具；本场景的 `condition_count=2`、两个开关的 binds、门的物理阻挡都**没有**进入任何行为契约 |
| 端到端链是否可证 | **可以证明，但不是由行为证据证明**：`test_escape_room.gd` 证明「踩 A → 仍关闭 → 踩 B → 开门 → 真实穿出」这条链 |
| 缺失证据 | ① 行为体系无组合场景执行能力（`scene` 必须是 `Features/<feature>/` 内相对路径）；② **`Mechanism/EscapeZone` 是 `Area2D` 且没有任何信号连接**，「逃脱成功」实际由 `ConditionGate.fulfilled` 触发，测试注释「到达逃逸区后应进入 Escaped 状态」与实际因果不符（见 §7 记录项 R1） |

### 5.2 `Scenes/SlimeEnemy.tscn`

| 项目 | 内容 |
| --- | --- |
| 组合 Feature | `chase_movement`（根，`ChaseMovement.tscn` 实例）、`health`、`contact_damage` |
| 关键节点路径 | `SlimeEnemy`（根）、`Health`、`ContactDamage`、`ContactDamage/ContactShape`、`Collision`、`SlimeAnim`、`SlimeHurtSfx` |
| 信号连接 | 场景内无显式 `[connection]`；组合依赖组件内部（`ContactDamage` 对 Health 的作用由接触时的 `take_damage` 调用产生） |
| 现有证据 | `Tests/test_slime_enemy.gd`：**仅结构断言**（节点存在、`Health` 有 `health_changed`/`died` 信号、根是 `CharacterBody2D`）；`Tests/test_slime_asset_binding.gd`：资产绑定 |
| 行为证据覆盖 | `chase_movement.*` 与 `health.*` **分别**在各自入口场景验证；`contact_damage` 无任何行为契约 |
| 仅被静态检查 | 三个 Feature 的共存、接触伤害→扣血→死亡的因果链、动画与受伤反馈 |
| 夹具 vs 正式场景差异 | 追击证据使用 `ChaseTargetFixture.tscn`（speed=60、静止 Target）；本场景 speed=70、目标为运行时玩家，**配置不同** |
| 端到端链是否可证 | **目前不能**：缺少「接触 → Health 变化 → 死亡信号」的组合断言 |
| 缺失证据 | `contact_damage` 的行为契约；组合场景执行能力；受伤动画/音效与状态的一致性断言 |

### 5.3 参照：`Scenes/SurvivalArena.tscn`（更强的一条链）

`Tests/test_switch_door_mechanism.gd` 证明「一个开关 → 两扇门打开 + 门后区域真实可达 +
离开不重置 + 重载复位」，并断言 `activated` 有 2 条连接、门不应持有 `Health`。
这是当前仓库中**证据最强**的端到端链，但同样属于 Godot 集成测试，不属于行为证据体系。

### 5.4 准备度结论

| 场景 | 组合特征 | 可验证性 | 结论 |
| --- | --- | --- | --- |
| EscapeRoom | 动作→条件→门→物理通行 | 高：已有真实输入/物理级集成测试 | 可作为 Phase 1.46 组合执行器的**首个验收目标** |
| SlimeEnemy | 追击 + 接触伤害 + 生命 | 低：缺 `contact_damage` 契约，现有测试只查结构 | 需先补 `contact_damage` 行为与组合断言 |
| SurvivalArena | 开关→门（1 对多） | 高：已有真实通行验证 | 可作为组合执行器的**回归基线** |

本阶段**未**实现通用组合场景执行器（题目明确不要求），仅完成准备度审计。

---

## 6. 记录项（本次未修复的观察，非缺陷结论）

| ID | 观察 | 性质 | 处理 |
| --- | --- | --- | --- |
| R1 | `EscapeRoom` 的 `EscapeZone` 未连接任何信号；「逃脱成功」由 `ConditionGate.fulfilled` 触发，`test_escape_room.gd` 的 G 段注释与因果不符 | 文档/测试表述不精确（不是行为缺陷：房间确实在开门瞬间即视为逃脱） | 未修改（属场景设计语义，需产品决定）；建议下一阶段明确「逃脱=开门」或给 `EscapeZone` 补 `body_entered` |
| R2 | `health.heal_clamped` 的状态断言与动作前状态相同，判别力依赖信号次数 | 弱断言 | 未修改（契约仍能抓缺陷），登记为引用限制 |
| R3 | 正面期望可在 `waited=0` 被动作前状态满足 | 潜在误报类（现有 17 条未触发） | 未修复，§10 给出最小设计 |
| R4 | 重放比较排除帧号/等待窗口 | 有意的非语义排除 | 保留；结论中不得声称时序确定性 |
| R5 | `trigger_switch.toggle_on_second_contact` 依赖夹具参数，Toggle 是唯一被覆盖的非默认配置 | 覆盖范围限制 | 登记 |
| R6 | `heal_pickup.heal_damaged_target` 的 `physics.overlap` 参数同时构造受伤目标 | 夹具式动作参数 | 登记（构造的是前置状态，不是结果） |

---

## 7. 已修复问题（缺陷 → 复现 → 修复 → 回归）

### P1：零帧推进 + 纯否定期望可无观测窗口 PASS

| 阶段 | 内容 |
| --- | --- |
| 复现 | 契约：`trigger_switch`，动作 `physics.overlap(group=players)`，期望 `trigger.is_triggered == false`，`window_frames=30`。真实行为是「1 帧内触发」，因此这条期望是**错的**；但因动作不推进帧，探针在 `waited=0` 就判 PASS |
| 修复前证据 | 探针副本（仅移除守卫）`sha256=62ca81ee…` → `status=PASS, waited_frames=0, action_executed=true, observed=false` |
| 修复后证据 | 探针 `sha256=5045ab75…` → `status=INVALID, reason=contract_invalid`, detail 含 `no observation window` |
| 修复 1（契约校验，Python） | `feature_behavior_evidence.py`：新增 `advances_frames()` / `check_has_evidence()`，在 `_validate_behavior` 中拒绝「无动作推帧 且 全部期望仅断言缺失」的契约。附 `sha256=68b42254…` |
| 修复 2（探针守卫，GDScript） | `probes/feature_behavior_probe.gd`：同一规则在运行时再拦一次（`INVALID` 且不加载场景），避免只靠 Python 侧 |
| 修复 3（回归测试） | `test_feature_behavior_evidence.py`：Case 6 新增 `no_evidence` 契约（断言 INVALID 且 detail 指明缺失窗口）；Case 13 三段式：`INVALID`、`≠PASS`、补真实帧后同一期望变 `MISMATCH`（`observed=true`，证明矛盾可被观测）。文件 `sha256=e2e2a2ae…` |
| 规则边界 | 只针对「零帧 + 纯否定」。含信号次数 >0、`equals: true`、区间断言或数值断言的契约不受影响；17 条既有 behavior 全部保留（0 条被新规则判非法） |
| 回归 | `test_feature_behavior_evidence.py` 162 → 169 条断言全 PASS；CLI 门禁 17/17 PASS（replay=2，exit=0）；`run_tests.py` 93/93 |

**未放宽任何断言**：修复方向是「拒绝没有观测窗口的契约」，不是把 FAIL 改 PASS、删除用例或
修改 golden baseline。

---

## 8. 全量回归结果（口径分开报告，不相加）

| 项 | 命令 | 结果 | 断言/规模口径 |
| --- | --- | --- | --- |
| 协议 ↔ manifest 一致性 | `tests/test_behavior_protocol_consistency.py` | PASS | 100 条断言 / 1 个测试文件 |
| Phase 1.40 行为证据 | `tests/test_feature_behavior_evidence.py` | PASS | **169 条断言** / 1 文件 / 13 Case |
| Phase 1.42 时间驱动 | `tests/test_behavior_time_driven.py` | PASS | 72 条断言 |
| Phase 1.41 追击行为 | `tests/test_chase_movement_behavior.py` | PASS | 31 条断言 |
| Phase 1.44 条件门行为 | `tests/test_condition_gate_behavior.py` | PASS | 53 条断言 |
| Phase 1.38 静态实例 | `tests/test_feature_instance_evidence.py` | PASS | 41 条断言 |
| Phase 1.38 静态对账 | `tests/test_instance_evidence_reconciliation.py` | PASS | 53 条断言 |
| Phase 1.39 运行时实例 | `tests/test_runtime_instance_evidence.py` | PASS | 67 条断言 / 6 Feature |
| 行为 CLI 覆盖门禁 | `feature_behavior_evidence.py --all --require-behavior --replay 2 --json` | **exit=0** | **17 behavior / 34 次真实运行（replay=2）/ pass=17 mismatch=0 insufficient=0 invalid=0** |
| Godot headless | `run_tests.py`（Godot 部分） | PASS | 38 个 `.gd` 测试文件（12 Feature 单测 + 26 场景/集成） |
| 完整测试 | `run_tests.py` | **93/93 PASS** | 测试文件数：Godot=38 + Python=55；不含断言语义 |
| 静态 Validator | `validator/validate.py` | **exit=0** | 0 error / 17 warning；`Feature instance evidence: 6 declared / 12 checked` |

计数口径说明：

- 「断言数」= 各测试脚本打印的 `PASS:` 行数（每个 `ok()` 一条），**不同文件之间不可相加**为
  「测试数」，也不等价于覆盖的行为数。
- 「behavior 数」= 17（来自 `template.yaml` 的 `behavior:` 声明），与「测试文件数」「断言数」
  是三种不同口径。
- 「重放数」= CLI 门禁每次 `--replay 2`，17 × 2 = 34 次真实 Godot 运行；
  单元测试内的对照运行不计入该数字。
- Validator 的 17 条 warning 全部是资产 manifest 指向缺失图片（既有问题，与行为证据无关）。

---

## 9. 尚未覆盖的行为与本次审计不能得出的结论

### 9.1 未覆盖（事实）

1. **3 个 Feature 无行为声明**：`contact_damage`、`health_bar`、`stun`（只有 Feature 级单测）。
2. **组合场景内的交互**：开关→条件→门、接触伤害→生命→死亡、平台载人、拾取物与场景胶水
   ——全部没有任何行为契约证据。
3. **时序上界**：本体系不比较 `waited_frames`/`first_observed_frame`，也没有 `min_frames`
   类断言，因此**不能**得出「事件在 N 帧内发生」的结论。
4. **配置矩阵**：`trigger_switch` 仅 Latching（默认）与 Toggle（夹具）两种；`condition_gate`
   只覆盖 `All` 聚合，未覆盖 `AtLeast` 的动态重回落；`moving_platform` 未覆盖非默认速度/路径；
   `player_movement` 只测右移与松开。
5. **负向对照缺口**：`health`、`collect_pickup`、`heal_pickup`、`player_movement` 没有缺陷注入。
6. **资产/表现层**：动画帧、音效、HUD 文案与状态的一致性不在行为证据范围内。

### 9.2 不能得出的结论（推断边界）

- 不能由「17/17 PASS」推出「9 个 Feature 全部功能正确」。
- 不能由「重放一致」推出「行为是确定性的」——只推出「两次运行的状态/事件观测相同」。
- 不能由「`Tests/test_escape_room.gd` PASS」推出「逃脱由进入逃逸区触发」（§6 R1）。
- 不能由「Validator 0 error」推出「行为契约与源码语义一致」——Validator 只检查结构与实例证据声明。

---

## 10. 下一阶段建议（附证据依据）

| 优先级 | 建议 | 依据 |
| --- | --- | --- |
| 高 | **组合场景行为执行器（最小版）**：允许 behavior 指定一个受控的 `res://Scenes/*.tscn` 证据场景 + 多目标观测，先以 `EscapeRoom` 为验收目标、`SurvivalArena` 为回归基线 | §5.1/§5.3：两条链已由集成测试证明可行，唯一障碍是 `scene` 只能位于 `Features/<feature>/` |
| 高 | **补 `contact_damage` 行为契约**（接触 → `health.current` 下降 + 目标存在性），随后为 `SlimeEnemy` 增加组合断言 | §5.2：该 Feature 无任何行为/实例证据，是当前最大缺口 |
| 中 | **正面期望的动作前基线规则**（§6 R3）：记录「动作前该检查是否已成立」，若已成立则要求至少一条其他检查提供判别力，或要求契约声明 `preconditions` 否定该状态 | §3.3 已复现同类误报（P1），R3 是同一根因的另一形态 |
| 中 | 为 `health` / `collect_pickup` / `heal_pickup` / `player_movement` 各注入 1 个真实缺陷对照 | §4 检测能力缺口 |
| 中 | 明确 `EscapeRoom` 的胜利语义（开门即胜利 vs 进入逃逸区），并同步修正测试注释或补 `EscapeZone` 连接 | §6 R1 |
| 低 | `condition_gate` 的 `AtLeast` 聚合行为、`moving_platform` 非默认速度 | §9.1 配置矩阵缺口 |
| 低 | 如需时序保证，扩展协议新增 `min_frames`/`max_frames` 观测语义（需先给出兼容性影响） | §9.1 第 3 条 |

不建议：为凑数量扩大 behavior 数量，或在没有负向对照的情况下把 `PARTIAL` 提升为
`RUNTIME_VERIFIED`。

---

## 附：本次运行产生的文件

| 文件 | 性质 |
| --- | --- |
| `.ai/context/PHASE_1_45_AUDIT.md` | 本报告（新增） |
| `.ai/tools/scene_composer/feature_behavior_evidence.py` | 修改：`advances_frames()` / `check_has_evidence()` / 契约校验规则 |
| `.ai/tools/scene_composer/probes/feature_behavior_probe.gd` | 修改：同一规则的运行时守卫 |
| `.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | 修改：Case 6 `no_evidence` + Case 13 |
| `.ai/tmp/t145_*.log`、`.ai/tmp/t145_prefix_repro.py` | 本次证据日志与最小复现脚本（`.ai/tmp/` 已被 `.gitignore:34` 忽略，可安全删除） |

未提交、未推送、未执行任何破坏性 Git 操作。
