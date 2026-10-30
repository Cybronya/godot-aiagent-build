# Phase 1.48 审计报告 — Slime Contact E2E Acceptance

- 阶段：Phase 1.48（Phase 1.47 结论的落地，不新增框架能力）
- 日期：2026-10-25
- 分支：`master`，HEAD：`1c30f94 feat: unified run identity, e2e serial lock and resource ownership hardening (Phases 1.26-1.34)`
- 结论摘要：新增正式场景 `Scenes/SlimeContactArena.tscn`（Player + SlimeEnemy，无胶水脚本），
  为它加了 **3 阶段真实端到端组合契约**（`slime_contact`）：真实输入位移 → 真实物理接触 →
  `ContactDamage` 节拍结算 → 玩家自己的 `Health`/`health_changed`；3/3 PASS 且两次重放一致。
  7 类负向对照在隔离副本里全部按预期被拒（MISMATCH / INSUFFICIENT / INVALID）。
  Phase 1.40–1.47 的能力与 EscapeRoom / SurvivalArena 稳定验收全部回归通过。

---

## 1. 实施前后的工作区状态

### 1.1 开始前（基线）

- `git status`：工作区**已存在** Phase 1.26–1.47 的未提交修改 —— 36 个已跟踪文件被修改
  （`.ai/context/*`、`.ai/tools/run_tests.py`、`.ai/tools/validator/*`、`Features/*/template.yaml`、
  `Orchestration/level_config.gd`、`Tests/*.gd` 等），以及大量未跟踪文件
  （`.ai/context/PHASE_1_3x–4x_AUDIT.md`、`.ai/context/behavior_protocol.yaml`、
  `.ai/context/composite_scenes/`、`.ai/tools/scene_composer/{probes,composite_*,feature_behavior_evidence.py}`、
  `Features/*/…Fixture.tscn` 等）。
- 未跟踪文件：38 个（本阶段结束后为 41 个，新增的 3 个就是 §1.2 里的新场景、新契约、新测试）。
- 暂存区：空。
- 处理方式：**全部保留**。本阶段没有执行 `git reset` / `git checkout` / `git stash` / `git add` /
  `git commit`，没有删除任何无法证明归属的文件，没有推送。

### 1.2 本阶段新增 / 修改（仅这些）

| 文件 | 类型 | 作用 |
| --- | --- | --- |
| `Scenes/SlimeContactArena.tscn` | **新增** | 正式场景：Player(-160,0) + SlimeEnemy(0,0)，无脚本、无信号连接 |
| `.ai/context/composite_scenes/slime_contact.yaml` | **新增** | 3 阶段组合契约（含数值推导与未覆盖说明） |
| `.ai/context/composite_behavior_protocol.yaml` | 修改 | `scenes` 白名单新增 `slime_contact: Scenes/SlimeContactArena.tscn` |
| `.ai/tools/scene_composer/probes/composite_behavior_manifest.json` | 重新生成 | 由协议生成（`--write-manifest`），无手工编辑 |
| `.ai/tools/scene_composer/tests/test_slime_contact_arena.py` | **新增** | 正向链 + 7 类负向对照 + CLI 退出码 + 副本恢复（77 条断言） |
| `.ai/tools/scene_composer/tests/test_composite_behavior_evidence.py` | 修改 | 场景白名单断言 2 → 3（只改计数，不改语义） |
| `.ai/tools/run_tests.py` | 修改 | 文档头计数：scene_composer 27 → 28、Python 57 → 58、合计 95 → 96 |
| `.ai/context/CONTRACT_INDEX.yaml` | 修改 | `scenes` 列表 + 登记 `test_slime_contact` |
| `.ai/context/PHASE_1_48_AUDIT.md` | **新增** | 本报告 |

**没有修改任何游戏逻辑**：`contact_damage.gd`、`health.gd`、`player_controller.gd`、
`chase_movement.gd`、`Scenes/SlimeEnemy.tscn`、`Features/player_movement/Player.tscn` 全部零改动
（§10 有 SHA256 断言）。

---

## 2. 产品决策：是否新增 `Scenes/SlimeContactArena.tscn`

### 2.1 评估过的四种方案

| 方案 | 是否可行 | 判断 |
| --- | --- | --- |
| A. 扩展组合探针支持 `@actor`（在史莱姆身上造玩家再观测） | 可行但要改探针 | **否决**：这是扩大通用权限（新增可寻址的运行时实体），而本阶段的要求正是「不扩大探针权限」；而且它证明的是「夹具造的玩家」，不如真实玩家场景强 |
| B. 把 Player 加进 `SlimeEnemy.tscn` | 可行 | **否决**：`Scenes/SlimeEnemy.tscn` 是资产生成链的黄金产物（`test_feature_capability_adoption` 断言重新生成后逐字节相同），改它会破坏生成链与既有绑定证据，并且会让「敌人资产场景」突然含玩家，语义污染更严重 |
| C. 用 `SurvivalArena`（运行时生成敌人） | 部分可行 | **否决**：敌人由 `Orchestration` 按 `Levels/survival_arena.json` 的 `spawns`（1.2 s 间隔、随机位置）生成，正是 Phase 1.46 记录的通行不稳定源。为测试固定生成参数 = 改正式游戏行为迎合测试 |
| D. **新增 `Scenes/SlimeContactArena.tscn`** | 可行 | **采用**：见 §2.2 |

### 2.2 采用 D 的依据

1. **有独立、长期的验收价值**：在此之前，仓库里**没有任何**「玩家 + 静态敌人」的正式场景
   （§2.3 的实测表：`Scenes/*.tscn` 中有玩家的 12 个场景都没有敌人；有敌人的 6 个场景都没有玩家）。
   也就是说「敌人接触伤害」这条链在正式资产里从未被完整跑过，只能靠单组件夹具推断。
2. **是可复用的正式场景，不是一次性夹具**：它由两个既有 Feature 场景（`Player.tscn`、
   `SlimeEnemy.tscn`）直接组成，**没有胶水脚本、没有额外信号连接、没有测试专用节点**；
   手动运行也能玩（右移走进史莱姆 → 每 0.5 s 掉 1 点血），可作为战斗数值/节拍的手工冒烟场景。
3. **不改变现有场景的节点结构、输入行为或游戏语义**：只新增一个文件；`Player`/`SlimeEnemy`
   的所有属性都是默认值（只有位置与 `groups=["players"]`，与 EscapeRoom 里 Player 的声明方式逐字一致）。
4. **不扩大执行器权限**：组合协议只多了一个**逐字白名单条目**；契约里没有 `state.set_property`、
   没有任意方法调用、没有脚本执行，动作只有 `input.press/release` 与 `simulation.advance_frames`。
5. 比 A/B/C 都小，且不触碰黄金产物与随机生成。

### 2.3 场景盘点（决策依据的原始数据）

`grep` 统计 `Scenes/*.tscn` 中是否实例化 Player / SlimeEnemy（或 contact_damage）：

```
Boss.tscn            player=0  enemy=1      EscapeRoom.tscn      player=1  enemy=0
BossChallenge.tscn   player=1  enemy=0      HarvestGrove.tscn    player=1  enemy=0
ChestVault.tscn      player=1  enemy=0      InterruptRange.tscn  player=1  enemy=0
EliteEnemy.tscn      player=0  enemy=1      PlatformVault.tscn   player=1  enemy=0
Enemy.tscn           player=0  enemy=2      SiegeGate.tscn       player=1  enemy=0
EnemyBasic.tscn      player=0  enemy=2      SlimeEnemy.tscn      player=0  enemy=3
SpikeTrap.tscn       player=0  enemy=1      StunTraining.tscn    player=1  enemy=0
SurvivalArena.tscn   player=1  enemy=0      ThreeAltarsPuzzle.tscn player=1 enemy=0
TimedCombatArena.tscn player=1 enemy=0      main.tscn            player=1  enemy=0
```

有玩家的场景都没有敌人；有敌人的场景都没有玩家；两个竞技场的敌人在运行时随机生成。

---

## 3. 真实端到端证据

命令（隔离项目副本 `.ai/tmp/composite/workspaces/<run_id>/project`，运行后删除）：

```
python .ai/tools/scene_composer/composite_behavior_evidence.py --scene slime_contact --replay 2
```

结果：`slime_contact 3/3 PASS`，`replay=2 consistent=True`，exit **0**。

| 阶段 | 动作（真实） | 观察窗口 | 预期 | 实测（两次重放一致） |
| --- | --- | --- | --- | --- |
| `approach_without_contact_deals_no_damage` | `input.press move_right` + 20 物理帧 + `release` | 5 | 玩家 x ∈ [-130,-60]、y ∈ [-8,8]；玩家血 10；事件 0；史莱姆血 5 | x=**-90.33**、y=0.0；血 **10**；事件 **0**；史莱姆 **5**（waited=0） |
| `contact_deals_one_tick_of_damage` | `input.press move_right` + 25 物理帧 + `release` | 45 | 玩家 x ∈ [-34,-26]（真实接触带）；玩家血 **9**；事件 **1** 且 `last_args=[9,1]`；史莱姆血 5；史莱姆 x/y ∈ [-2,2] | x=**-30.076**；血 **9**；事件 **1** `[9,1]`；史莱姆 **5**、位置 (0,0)（waited=**10**） |
| `leaving_contact_stops_damage` | `input.press move_left` + 25 帧 + `release` + 45 帧空跑（≥1.5 个节拍） | 5 | 玩家 x ∈ [-140,-80]；血 **9**；事件 **1**；史莱姆血 5 | x=**-121.74**；血 **9**；事件 **1**；史莱姆 **5**（waited=0） |

**为什么这些断言不能被伪造**：

- 玩家位置 `-30.076` 只能由「被史莱姆身体碰撞（28×28）挡住」产生：`player_controller` 只会
  `velocity = direction * speed; move_and_slide()`，没有任何传送/位置写入路径。
- 该位置（|dx| = 30.076 < 34 = 18 + 16）同时意味着玩家碰撞盒与 `ContactShape`(36×36) 真实重叠，
  所以「停在 -30」本身就是**接触证据**，不是「离得近」。
- 伤害观测的是**玩家自己的** `Player/Health`（`Health.tscn`，max=10）上的 `get_current_health()`
  与 `health_changed(current, amount)`；没有任何夹具写入（组合协议显式禁止 `state.set_property`）。
- 契约里没有 `physics.overlap` 的 `damage` 参数（该参数会直接调用 `take_damage`，等于替组件制造结果）。

---

## 4. 伤害频率与数值语义

**源码事实**（`Features/contact_damage/contact_damage.gd`）：

```gdscript
var _cooldown := 0.0
func _physics_process(delta):
    _cooldown -= delta
    if _cooldown > 0.0: return
    _cooldown = tick_interval          # 结算后重置为整个节拍
    for body in get_overlapping_bodies(): _deal_damage_to(body)
```

- 不是「每物理帧」，也不是「每次进入接触一次」，而是**固定节拍（默认 0.5 s = 30 物理帧）**，
  且 `_cooldown` 初值为 0 → 第 1 物理帧就结算一次（此时无重叠，不产生伤害）。
- 因此接触期间会**重复**受伤，次数取决于接触持续时间，与「进入接触的时刻」相对节拍网格的相位有关。

**一次性测量（`.ai/tmp/t148_measure.py`，脚本用完即删，未进仓库）**：把第 2 段窗口拉长到 120 帧并把
期望故意写成永假（血 0 / 事件 99）→ 窗口跑满后 MISMATCH，从 observed 读到真实数值：

```
stage contact_deals_one_tick_of_damage  MISMATCH  waited=120
  health.current  Player/Health   expected=0.0    observed=6   STATE_MISMATCH
  signal          Player/Health   expected=99     observed=4   SIGNAL_MISMATCH
```

即：动作 25 帧 + 窗口 120 帧 ≈ 145 帧接触内共 **4 次**结算，血量 10 → **6**；两次重放数值相同。
按 30 帧节拍推导（进入接触后 ≤30 帧出第一次，之后每 30 帧一次）与实测 4 次自洽。

**因此契约明确不断言「总共几次伤害」**（那会随窗口长度变化，属于把观测当设计）：

- 第 2 段断言的是「**第一次**结算恰好 1 点，且事件参数与读数一致」——探针一旦全部期望成立就结束该阶段，
  所以第 2 段会在第一次结算的那一帧停下，第二次（30 帧后）不可能被纳入；
- 第 3 段断言「离开接触后 45 帧（≥1.5 个节拍）内血量和事件计数都不再变化」——这是唯一与相位无关的部分。

窗口 45 帧的来源：进入接触后最坏情况要等满一个 30 帧节拍，45 = 30 + 15 帧余量；
5 帧窗口（负向对照 Case 6）会稳定 MISMATCH，说明窗口不是「够宽就随便过」。

---

## 5. 正向测试、负向对照与重放

命令：`python .ai/tools/scene_composer/tests/test_slime_contact_arena.py`
结果：**77 条断言全 PASS，exit 0**（`.ai/tmp/t148_slime_test.log`）。

所有注入都在本次运行独占的隔离副本（`CompositeWorkspace.project/...`）里完成，每步注入后用
SHA256 断言恢复，最后再断言仓库 8 个受保护文件哈希未变（§10）。

| # | 注入的故障（隔离副本） | 预期分类 | 预期内容 | 实际 | 退出码 |
| --- | --- | --- | --- | --- | --- |
| 2 | 删除 `Scenes/SlimeEnemy.tscn` 里的 `ContactShape`（接触通道断开） | `MISMATCH` | 第 2 段失败；玩家**仍被挡住**在 -30（所以失败原因只能是伤害），血 10、事件 0；第 3 段不执行 | 与预期一致（`failed_stage=contact_deals_one_tick_of_damage`，`reason=state_mismatch`，completed=[第 1 段]） | 0 |
| 3 | `contact_damage.gd`：`health.take_damage(damage)` → `pass`（伤害调用未生效） | `MISMATCH` | 第 2 段 `state_mismatch`，detail 点名 `health.current` | 与预期一致 | 0 |
| 4 | 去掉 Player 实例的 `groups=["players"]`（接触前置条件不满足） | `MISMATCH` | 玩家仍然重叠并被挡住，但**不掉血**（血 10、事件 0） | 与预期一致 | 0 |
| 5a | `Player.tscn` 里 `Health` 改名为 `HealthGone`（观察目标损坏） | `INSUFFICIENT` | 前置条件不满足即停：`reason=precondition_unmet`、detail 含 `health.current`、无阶段执行、无动作执行 | 与预期一致 | 0 |
| 5b | 契约把第 2 段观测目标改成 `Player/MissingHealth` | `INSUFFICIENT` | `reason=check_unavailable`，第 1 段已完成 | 与预期一致 | 0 |
| 6 | 第 2 段 `window_frames` 5（短于一个节拍） | `MISMATCH` | 窗口耗尽仍血 10（不是 INSUFFICIENT） | 与预期一致 | 0 |
| 7 | 第 2 段不做位移，只空跑 45 帧却期望伤害 | `MISMATCH` | 玩家停在 -90 附近、血 10 → 链不会凭空成立 | 与预期一致 | 0 |
| 8 | 第二次重放的观测被篡改（runner 注入） | `INSUFFICIENT` | `replay_inconsistent`，两次结果都保留 | 与预期一致 | 0 |
| 9 | 未登记场景 `Scenes/SlimeEnemy.tscn` / `../Scenes/EscapeRoom.tscn` / 未声明 scene_id / 夹具写状态 / 探针层 `res://Scenes/../project.godot` | `INVALID` | 不启动 Godot；白名单逐字匹配 | 与预期一致（4 条 Python 层 + 1 条探针层） | 0 |
| 10 | CLI：正常链 / 契约第 2 段期望血 8（故意写错） | PASS→0 / MISMATCH→**1** | 正常链输出 `3/3 PASS` 并清理工作区；错误契约 exit 1 且输出点名失败阶段 | 与预期一致 | 0（测试自身）/ **1（被测命令，预期失败）** |

状态分类语义（与 Phase 1.40–1.47 一致，未改动）：

- **MISMATCH**：动作真实执行了，但可观测行为与契约不符（含窗口耗尽）。
- **INSUFFICIENT**：证据不足（观测不可用、前置不满足、重放不一致）。
- **INVALID**：契约 / 路径 / 协议非法（不执行任何动作、不启动 Godot）。

**重放一致性**：三条阶段 × 2 次运行，`fingerprint` 完全一致（比较 `status/reason/failed_stage/
action_executed/completed_stages/每段状态与每条 check 的 expected/observed`；忽略 run_id、绝对帧号、
耗时）。诚实记录两点：

1. 第 2 段的 `waited_frames` 是 **10**（第一次结算在动作结束后第 10 帧），它取决于动作帧相对节拍网格的
   相位，因此**不**参与一致性比较；同一条链在不同机器/负载下这个数值可能不同，但「恰好一次、血 9、
   事件 [9,1]」不会变（相位最坏情况也在 30 帧内，窗口 45 帧覆盖）。
2. 本轮两次重放的观测值逐字节相同（-90.33 / -30.076 / -121.74 等），但这**不是**契约依赖的前提：
   契约断言的是区间与等式，不是浮点位模式。

---

## 6. 协议、manifest 与白名单的变更

| 项 | 变更 | 校验 |
| --- | --- | --- |
| `behavior_protocol.yaml`（动作 / 观测 / 信号 / 属性的唯一权威） | **零变更** | `behavior_protocol.check_manifest` 通过；`scenes 3` 之外无新增能力 |
| `probes/behavior_manifest.json` | **零变更**（未重新生成） | 一致性测试通过 |
| `composite_behavior_protocol.yaml` | `scenes` 新增 1 条 `slime_contact: Scenes/SlimeContactArena.tscn`（逐字路径，协议加载时校验文件存在、无 `..`、无绝对路径） | `--check-manifest` PASS |
| `probes/composite_behavior_manifest.json` | 由 `--write-manifest` 重新生成（`scenes: [escape_room, slime_contact, survival_arena]`） | `--check-manifest` 无漂移；测试断言「重新生成后逐字节相同」 |
| 阶段 / 帧预算 | 未改（2..8 段、单段窗口 ≤120、整链 ≤1200）；本链 3 段 / 170 帧 | 契约校验通过 |
| `denied_actions` | 未改（仍只禁 `state.set_property`） | 负向对照 9 证明它真的被拒 |
| 探针（`composite_behavior_probe.gd`） | **零变更** | `probe_capabilities` 与协议声明一致（`test_composite_behavior_evidence` Case 1） |

---

## 7. 回归测试清单（逐段命令与退出码）

Godot 4.7 stable headless；Windows；`python` 为 CPython 3.12。所有命令在仓库根目录执行，
日志留在 `.ai/tmp/t148_*.log`。

| # | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 1 | `python .ai/tools/scene_composer/tests/test_slime_contact_arena.py` | **77 PASS**（含 7 类负向对照 + CLI） | **0** |
| 2 | `python .ai/tools/scene_composer/composite_behavior_evidence.py --all --require-composite --replay 2` | escape_room 4/4、**slime_contact 3/3**、survival_arena 2/2；均 `replay=2 consistent=True` | **0** |
| 3 | `python .ai/tools/scene_composer/tests/test_composite_behavior_evidence.py` | **100 PASS**（14 个 Case，含白名单 3 项断言） | **0** |
| 4 | `python .ai/tools/scene_composer/feature_behavior_evidence.py --all --require-behavior --replay 2` | **pass=20** mismatch=0 insufficient=0 invalid=0 not_declared=0 | **0** |
| 5 | `python .ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | **104 PASS** | **0** |
| 6 | `python .ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | **186 PASS** | **0** |
| 7 | `python .ai/tools/scene_composer/tests/test_contact_damage_behavior.py` | **39 PASS** | **0** |
| 8 | `python .ai/tools/run_tests.py --godot-only` | **38/38 PASS** | **0** |
| 9 | 其余 23 个 scene_composer 测试（逐文件独立运行，见 §7.1） | **23/23 PASS**（最小 17、最大 131 条断言） | **0** |
| 10 | `python .ai/tools/run_tests.py validator` | 10/10 PASS | **0** |
| 11 | `python .ai/tools/run_tests.py runtime` | 5/5 PASS | **0** |
| 12 | `python .ai/tools/run_tests.py feature_registry` | 4/4 PASS | **0** |
| 13 | `python .ai/tools/run_tests.py gameplay_planner` | 2/2 PASS | **0** |
| 14 | `python .ai/tools/run_tests.py asset_registry` | 11/11 PASS | **0** |
| 15 | `python .ai/tools/run_tests.py evaluation` | 2/2 PASS | **0** |
| 16 | `python .ai/tools/run_tests.py e2e` | 2/2 PASS | **0** |
| 17 | `python .ai/tools/validator/validate.py` | **0 error / 17 warning**（与 Phase 1.46/1.47 基线同为既有缺图警告） | **0** |
| 18 | `python .ai/tools/scene_composer/composite_behavior_protocol.py --write-manifest --list-contracts` | `scenes: 3`、三份契约合法（4/3/2 段） | **0** |

### 7.1 时限处理

`run_tests.py scene_composer`（28 个测试）单条命令会超过本工具 600 s 上限，因此按项目文档要求
**分段执行并逐段记录**（表 1/3/5/6/7 + 表 9 的 23 个文件），没有把任何未跑完的段说成通过。

- 表 9 的 16 个（纯 Python 契约类）在一个命令内跑完：`artifact_evidence_validator 39`、
  `capability_contract_validator 42`、`component_instance_materialization 58`、
  `component_instance_ownership 39`、`composite 17`、`entity_root_instance 26`、
  `feature_capability_adoption 131`、`feature_capability_pipeline 37`、`plan_generator 25`、
  `scene_builder_intent_input 42`、`scene_compatibility_gate 62`、`scene_composer 49`、
  `scene_intent_capability 46`、`scene_intent_contract 68`、`scene_intent_runtime 44`、
  `scene_validator_intent_input 48`。
- 剩下 7 个（会创建隔离工作区的）单独一条命令：`behavior_time_driven 72`、
  `chase_movement_behavior 31`、`condition_gate_behavior 53`、`external_artifact_evidence 45`、
  `feature_instance_evidence 41`、`instance_evidence_reconciliation 53`、`runtime_instance_evidence 67`。
- **并发纪律**：本阶段所有会创建/删除隔离工作区的命令（表 1/2/3/4/5/6/7/9 与 e2e）**串行**执行，
  没有重复 Phase 1.47 §8.2 那种「一边删 `.ai/tmp/behavior/workspace-*` 一边 `copytree`」的错误。

### 7.2 本阶段出现过的 1 次失败（如实记录）

`test_slime_contact_arena.py` 第一次运行 **exit 1**，唯一失败项是我自己新写的断言：

```
FAIL: case9: a fixture state write is INVALID | Invalid composite contract:
      … actions[3].params.property 'health.max_health' is not a registered property
```

原因：我注入 `state.set_property` 时用了**未登记**的属性名，于是它先被「属性必须登记」拦下，
而断言期望的是「被 `denied_actions` 拦下」（两者都是 INVALID，但错误原因不同）。
修正方式是把注入的属性换成协议里真实登记的 `trigger_switch.trigger_mode`（与 Phase 1.46 Case 4 同一做法），
**没有放宽断言、没有改协议**。重跑 77/77 PASS。此后表 1 的所有运行均为 exit 0。

---

## 8. 隔离副本、临时文件与恢复验证

| 位置 | 内容 | 处置 |
| --- | --- | --- |
| `.ai/tmp/composite/workspaces/<run_id>/` | 本次每个 CLI / 测试运行的独占项目副本（`owner.json` + 独占创建） | 全部由运行自身在 `finally` 中删除；`--list-stale`/目录检查显示**无遗留** |
| `.ai/tmp/composite/<run_id>/` | 组合证据（`contract.json` / `result.json` / `stdout.log` / `stderr.log`），每个场景 2 份 | 保留（审查用，`.gitignore` 覆盖） |
| `.ai/tmp/behavior/<run_id>/` | Phase 1.47 行为证据重新生成 | 保留 |
| `.ai/tmp/slime_bad_contracts/slime_contact.yaml` | Case 10 用的故意写错契约（CLI 负向对照输入） | 保留（与 Phase 1.46 的 `composite_bad_contracts` 同类，位于 `.ai/tmp`） |
| `.ai/tmp/t148_measure.py` | 一次性节拍测量脚本（§4 的 4 次伤害数据） | **已删除**，数值已抄进本报告 |
| `.ai/tmp/t148_*.log` | 本轮各段命令的原始 stdout | 保留（审查用） |
| 缺陷注入 | `project/Scenes/SlimeEnemy.tscn`、`project/Scenes/SlimeContactArena.tscn`、`project/Features/contact_damage/contact_damage.gd`、`project/Features/player_movement/Player.tscn` | 每步注入后立即写回原字节并断言 SHA256 相等（Case 2/3/4/5/11） |

仓库保护：测试在运行前后对 8 个受保护文件做 SHA256 快照并断言未变
（`Scenes/SlimeContactArena.tscn`、`Scenes/SlimeEnemy.tscn`、`Features/player_movement/Player.tscn`、
`Features/health/health.gd`、`Features/contact_damage/contact_damage.gd`、
`.ai/context/composite_behavior_protocol.yaml`、`.ai/tools/scene_composer/probes/composite_behavior_manifest.json`、
`.ai/context/composite_scenes/slime_contact.yaml`）。

---

## 9. 未覆盖行为与后续建议

1. **死亡**：玩家 10 点血、每节拍 1 点，需要连续接触约 5 s 才会触发 `health.died`；本契约不推进到死亡
   （死亡语义已由 `health` Feature 的 `death` 行为契约覆盖）。
2. **重复结算的总次数**：刻意不作断言（§4）。若将来需要「N 秒内恰好 k 次」这类时序契约，应新增独立的
   时序断言（基于 `_cooldown` 的相位或累计帧），而不是收紧现有窗口。
3. **追击移动**：`SlimeEnemy.tscn` 的 `ChaseMovement.target_path` 为空 → 敌人不移动，契约把这一现状固定为
   「史莱姆位置不变」。若以后给史莱姆配了追击目标，本契约会以 MISMATCH 提醒更新，而不是静默通过。
4. **敌人受击/玩家攻击**：`ContactDamage` 只对 `players` 组生效；玩家攻击敌人不在本链范围（无 attack 组件参与）。
5. **组合协议仍是「单场景 + 逐字白名单 + 分阶段」**：本阶段没有扩展执行器；未来若需要「两场景叠加」或
   `@actor` 观测，必须单独立项评估权限影响。
6. **环境**：仅 Windows + Godot 4.7 stable headless 实测；隔离副本的 `--import` 预构建是必要步骤
   （依赖 `class_name Health` / `ContactDamage` / `PlayerController`）。
7. **静态门禁不覆盖组合链**：`validate.py` 0 error 不代表接触链成立，最终验收必须显式运行
   `composite_behavior_evidence.py --all --require-composite`。

---

## 10. 结论

1. 有**真实玩家 → 史莱姆 → ContactDamage → 玩家 Health** 的完整链路证据：输入驱动位移、被敌人身体挡住
   （-30.076）、按节拍掉 1 点（10→9）、`health_changed[9,1]` 一次、敌人血量与位置不变、离开接触后不再掉血。
2. 没有任何夹具直接写入被测状态（组合协议禁止 `state.set_property`，本链也确实一个都没用）；
   伤害只能来自 `get_overlapping_bodies()` 的真实重叠。
3. 7 类故障注入全部被稳定识别（MISMATCH / INSUFFICIENT / INVALID 分类正确），CLI 对 MISMATCH 返回 1。
4. 重放差异被如实记录：语义结果一致，相位相关的 `waited_frames` 不参与比较且已说明。
5. 既有 EscapeRoom（4/4）与 SurvivalArena 稳定链（2/2）不回归；Phase 1.40–1.47 的 20 条 behavior、
   协议一致性、实例证据、Validator 全部回归通过（§7）。
6. 未提交、未推送；工作区既有未提交修改完整保留，等待人工审查。
