# Phase 1.51 审计报告 — Health Runtime Defect Detection & Evidence Audit

日期：2026-10-27
环境：Windows，Godot 4.7 stable headless，CPython 3.12
仓库：`F:\Godot_v4.7-stable\game`
基线 HEAD：`1c30f94`（分支 `master`）

---

## 0. 结论

**`health` → `VERIFIED`**（Phase 1.50 时为 `PARTIAL`）

判断依据逐条对应题目 §六 的 6 个条件，全部满足：

| §六 条件 | 本阶段证据 | 位置 |
| --- | --- | --- |
| 1. 正常行为有真实运行时证据 | 5 条契约全部真实执行（`action_executed=True`、无夹具动作、`waited_frames=0`）、`replay 2` 一致 | §2、§4.7 |
| 2. ≥3 类有效缺陷注入被对应契约检出 | **8 类被检出**（题目要求 3 类），每类都指名是哪个契约在哪一层失败 | §3 |
| 3. 在正确的行为层面失败 | 每条注入都断言 `state_mismatch` 还是 `signal_mismatch`；并逐条验证"相邻契约仍 PASS" | §4 |
| 4. 证据不足不误报 PASS | 目标缺失 → `INSUFFICIENT/check_unavailable`；前置不满足 → `INSUFFICIENT/precondition_unmet`（且动作未执行）；"现象不成立" → `MISMATCH` 而不是 PASS | §4.7 |
| 5. 回归 / 协议 / manifest 一致性通过 | 9 段中 **8 段 exit 0**（`godot_only` 38/38、`scene_composer` **31/31**、`e2e` 2/2 …）；唯一失败的 `feature_registry` 与本阶段改动无关（并行工作流新增 2 个 Feature 后硬编码计数未同步，见 §6.2.1）；协议能力表逐项不变；`check_manifest == []` | §6、§7 |
| 6. 报告列出未验证边界，不夸大 | 明确写出 **1 类注入不被任何契约检出**、0/负数在行为层不可表达、`max_health` 运行期变更无观测 | §9 |

一句话：**Phase 1.50 证明了 `health` 会被调用并返回正确值；本阶段证明了契约能拒绝错误实现，同时把"拒绝不了的那一类"也钉死在台面上。**

---

## 1. 审计范围与基线状态

### 1.1 修改前的 Git 状态（逐字实测）

```
HEAD            1c30f94  feat: unified run identity, e2e serial lock and resource ownership hardening (Phases 1.26-1.34)
branch          master
staged          0 项
modified        38 项（Phase 1.26–1.50 的既有未提交修改）
untracked       50 项（48 项既有 + 2 项非本会话产生，见 PHASE_1_50_AUDIT.md §1.3：
                        .ai/skills/foundation/godot-gdscript/code_library/ 与 .../tools/）
```

### 1.2 本阶段的范围（刻意收窄）

只碰 `health` 一处 Feature，**不碰协议**，不碰 `player_movement` / `health_bar` / `contact_damage`：

| 文件 | 动作 | 内容 |
| --- | --- | --- |
| `Features/health/template.yaml` | 修改 | 新增 `overkill_clamps_at_zero`、`post_death_guard`；`heal_clamped` 补 `last_args` |
| `.ai/tools/scene_composer/tests/test_health_behavior.py` | **新增** | 104 条断言：正向 5 条 + 9 类注入 + 证据不足 + 重放 + 无效契约 + CLI |
| `.ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | 修改 | 行为总数 30 → 32；补 1 条 Phase 1.51 声明断言 |
| `.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | 修改 | 行为总数 30 → 32；legacy 清单 6 → 8（含 health 的 2 条新契约） |
| `.ai/tools/scene_composer/tests/test_behavior_time_driven.py` | 修改 | Case 7 的 legacy 行为计数 6 → 8（**回归跑出来的**，见 §6.3） |
| `.ai/context/CONTRACT_INDEX.yaml` | 修改 | 登记 `test_health` |
| `.ai/tools/run_tests.py` | 修改 | scene_composer 段 30 → 31；Python 总数 60 → 61、全量 98 → 99（实测更正） |
| `.ai/context/FEATURE_BEHAVIOR_COVERAGE.md` | 修改 | `health` → `VERIFIED`；行为总数 30 → 32；统计 9/3 |
| `.ai/context/PHASE_1_51_AUDIT.md` | **新增** | 本报告 |

### 1.3 先审计再动手：实际实现（不是假设）

读完 `Features/health/health.gd`（45 行）后的事实：

| 项目 | 事实 |
| --- | --- |
| 节点 | `class_name Health extends Node`；`Health.tscn` = 单节点 + 脚本，无可覆盖的实例 |
| 状态 | `_current_health: int`、`_is_dead: bool`；**没有任何 setter / 公开写入入口** |
| 配置 | `@export var max_health := 5`；`_ready()` 里 `_current_health = max_health` |
| 伤害 | `take_damage(amount)`：守卫 `_is_dead or amount <= 0` → `max(_current_health - amount, 0)` → `health_changed.emit(current, amount)` → 归零则 `_is_dead = true; died.emit()` |
| 治疗 | `heal(amount)`：守卫同上 → `min(_current_health + amount, max_health)` → `health_changed.emit(current, amount)` |
| 事件 | `health_changed(current: int, amount: int)`、`died`（无参数） |
| 时序 | **完全同步**：没有 Tween / 计时器 / 延迟队列；实测 5 条契约 `waited_frames` 全部为 **0** |

---

## 2. Health 实现与现有检查的映射（哪些被覆盖、哪些没有）

| # | 实现行为 | 原有契约是否覆盖 | 判据（不是看名字） |
| --- | --- | --- | --- |
| 1 | 受伤后数值按 amount 减少 | **是** | `damage`：`current == 1` + `last_args == [1,4]` |
| 2 | 治疗后数值按 amount 增加 | **否**（只有"请求 99 点后不超上限"） | `heal_clamped` 只断言终值 5 与事件次数，没有"部分治疗"的契约 |
| 3 | 治疗上限钳制 | **是** | `heal_clamped`：从 1 治疗 99 → 5 |
| 4 | 伤害下限钳制（不能为负） | **否** | `death` 用恰好 5 点（= `max_health`）伤害，永远到不了负值 |
| 5 | 死亡条件与死亡状态 | **是** | `death`：`current == 0` + `is_dead == true` |
| 6 | `died` 恰好一次 | **部分** | `death` 断言 `count: 1`；但契约里只有一次致命伤害，看不到"重复触发" |
| 7 | `health_changed` 参数正确 | **部分** | `damage` 有 `last_args`；**`heal_clamped` 没有**，heal 发错参数无人能察 |
| 8 | 死后忽略后续伤害/治疗（死亡守卫） | **否** | `death` 只做一次伤害，守卫根本不被激励 |
| 9 | 0/负数输入被忽略 | **否，且不可表达** | 协议把两个动作的 `amount` 声明为 `1..100`，0 / -3 / 101 一律 `INVALID`（§5.3 实测） |
| 10 | `max_health` 配置被尊重 | **否** | 所有契约都跑在默认 `max_health = 5` 的场景上 |
| 11 | `max_health` 运行期变更 | **否，且无观测** | `properties` 未声明 `health.max_health`，没有只读观测 |
| 12 | 事件触发时序 | **是** | 全部契约 `waited_frames = 0`；同步语义确定 |

**结论：原有 3 条契约覆盖了 1/3/5，部分覆盖 6/7，未覆盖 2/4/8/9/10/11。**

由此确定本阶段只补两类，而且只补**能被注入实验证明有价值**的：

- `overkill_clamps_at_zero` → 覆盖第 4 项（下限钳制）
- `post_death_guard` → 覆盖第 8 项（死亡守卫的两半）
- `heal_clamped` 补 `last_args: [5, 99]` → 把第 7 项从"部分"补全（不是新增契约）

第 2 项（部分治疗）没有被补：`heal_clamped` 已经断言了"从 1 治疗 99 到 5"这条路径，
再加一条"从 3 治疗 1 到 4"只是同一段代码的等价输入，属于**重复契约**，题目明确要求不要加。

---

## 3. 九类缺陷注入的完整证据

全部注入都在 `BehaviorWorkspace` 的隔离副本
（`.ai/tmp/behavior/workspace-*/project/Features/health/health.gd`）上做，
每次注入后立即**写回原始字节**并断言 `sha256` 等于注入前基线。
命令：`python .ai/tools/scene_composer/tests/test_health_behavior.py`
证据原文：`.ai/tmp/p151_health_test.log`（Case 2 段落）。

| ID | 注入（最小局部改动） | 对应契约 | 期望 | **实测** | 失败层 | 相邻契约 |
| --- | --- | --- | --- | --- | --- | --- |
| 2a | `max(_current_health - amount, 0)` → `... - amount + 1` | `damage` / `death` / `post_death_guard` | 3 条 MISMATCH | ✅ `damage` `state_mismatch`、`death` `state_mismatch`、`post_death_guard` `signal_mismatch` | state ×2 + signal ×1 | `heal_clamped`、`overkill` **仍 PASS** |
| 2b | `min(_current_health + amount, max_health)` → `_current_health + amount` | `heal_clamped` | MISMATCH | ✅ `heal_clamped` `state_mismatch`（终值 100 ≠ 5） | state | 其余 **4 条全 PASS** |
| 2c | 扣血事件的 `emit(_current_health, amount)` → `emit(amount, _current_health)` | `damage` / `overkill` | MISMATCH | ✅ 两条均 `signal_mismatch`（数值仍对，事件参数错） | signal | `heal_clamped`、`death`、`post_death_guard` **仍 PASS** |
| 2d | 治疗事件的 `emit(_current_health, amount)` → `emit(_current_health, 0)` | `heal_clamped` | MISMATCH | ✅ `signal_mismatch`（`count` 仍是 2，只有 `last_args` 不匹配） | signal | 其余 **4 条全 PASS** |
| 2e | `died.emit()` → 连续两次 | `death` / `post_death_guard` | 2 条 MISMATCH | ✅ 均 `signal_mismatch`（`died` 计数 2 ≠ 1） | signal | 其余 **3 条全 PASS** |
| 2f | `max(_current_health - amount, 0)` → `_current_health - amount` | `overkill_clamps_at_zero` | MISMATCH | ✅ `state_mismatch`（`current` = **-95**，`is_dead` 仍 false） | state | `damage`、`heal_clamped`、`death`、`post_death_guard` **仍 PASS** |
| 2g | `take_damage` 的 `if _is_dead or amount <= 0` → `if amount <= 0` | `post_death_guard` | MISMATCH | ✅ `signal_mismatch`（`health_changed` 与 `died` 各多一次） | signal | 其余 **4 条全 PASS** |
| 2h | `heal` 的 `if _is_dead or amount <= 0` → `if amount <= 0` | `post_death_guard` | MISMATCH | ✅ `state_mismatch`（死后治疗把 `current` 从 0 改成 3） | state | 其余 **4 条全 PASS** |
| 2i | `_ready()` 的 `= max_health` → `= 5` | — | **不被检出** | ✅ **5 条契约全部 PASS**（这就是缺口本身） | — | 全部（见 §9.1） |

**检出 8 / 9。** 每一条注入的状态、原因码与"相邻契约仍通过"都是脚本断言出来的，
不是人工看日志得出的；`case2: repository health.gd was never touched by any injection`
另有一条断言兜底。

### 3.1 为什么 2g 与 2h 是一对

死亡守卫有两半，只有一起注入才能证明契约两半都在看：

- **2g**（`take_damage` 守卫丢了）：0 − 2 被下限钳回 0，**终值不变**，所以只能在**信号层**被抓到
  （`health_changed` 与 `died` 各多一次）。
- **2h**（`heal` 守卫丢了）：0 + 3 = 3，**终值确实变了**，所以在**状态层**被抓到。

如果只有其中一条，就无法区分"契约在观测数值"和"契约在数事件"。

---

## 4. 缺陷检出能力与区分能力

### 4.1 检出层是实测的，不是设计的

题目 §六.3 要求"证明测试在正确的行为层面失败"。本测试对每条注入都断言了
`reason` 是 `state_mismatch` 还是 `signal_mismatch`——原因码来自探针对**第一个失败检查**的归类
（`_reason_for`：`signal` 检查 → `signal_mismatch`，其余 → `state_mismatch`）。

### 4.2 首轮运行失败的 3 条断言（如实记录）

第一版跑出 **104 项中 3 项 FAIL / exit 1**，全部是我**预测**错，不是实现错：

1. **2a 的 `post_death_guard` 我预测 `state_mismatch`，实测 `signal_mismatch`。**
   机理：该注入下第一次伤害只到 1（不致命），第二次才归零，**终值仍是 0**（下限钳到 0），
   因此只有 `health_changed` 多了一次能被看见。**修正**：把期望改成实测的 `signal_mismatch`，
   并在代码注释里写明"这是实测结果，不是设计意图"。
2. **2g 同样如此**（0 − 2 被钳回 0）。修正同上。
3. **Case 6 我数了 `stdout.count("MISMATCH") == 1`。**
   实测是 3——因为 `STATE_MISMATCH` / `SIGNAL_MISMATCH` 这两个词**本身就含有 `MISMATCH` 子串**。
   这是"用子串计数冒充结构断言"的典型自欺。**修正**：改用 CLI 自己的汇总行
   （`pass=4 mismatch=1`）+ "恰好一行 behavior 被标 MISMATCH 且它是 `overkill_clamps_at_zero`"
   这两条结构断言。

三处修正都**没有放宽任何阈值或删除任何断言**：8 类注入的检出结论、`state`/`signal` 层的区分、
"相邻契约仍通过"的逐条断言全部保留，且新增了 2h（见 §3.1）。

### 4.3 为什么这 2 条新契约不是"为了通过而加的"

- `overkill_clamps_at_zero`：**只有它**能检出 2f（`damage` 与 `death` 都 PASS）。
- `post_death_guard`：**只有它**能检出 2g 与 2h。
- `heal_clamped` 的 `last_args`：**只有它**能检出 2d。

三条都是"不加就检不出某个真实缺陷"的最小增量，且全部只使用**协议已有的**动作、观测与信号。

---

## 5. 协议是否被修改

**没有。** 这是本阶段的一条硬约束（题目 §四），已用三处独立证据固定：

| 项目 | 修改前 | 修改后 | 证据 |
| --- | --- | --- | --- |
| `protocol_version` | 2 | 2 | `test_behavior_protocol_consistency.py` Case 1 |
| actions | 8 | 8 | 精确元组 `(8, 12, 7, 1)`（实测打印确认） |
| observations | 12 | 12 | 同上 |
| signals | 7 | 7 | 同上 |
| properties | 1 | 1 | 同上；且 `"health.max_health" not in properties`（§9.2 的缺口根源） |
| manifest 漂移 | — | `[]` | `behavior_protocol.check_manifest(load_protocol())` → `[]` |
| `behavior_protocol.yaml` SHA | — | `bbcc76d4…`（未变，工作区无未提交改动） | `sha256sum` |
| `behavior_manifest.json` SHA | — | `65ad372f…`（未变） | `sha256sum` |

### 5.1 顺带说明：为什么不需要扩协议

唯一"想观测但观不到"的是 `max_health`（§9.2）。它需要的**不是只读观测**，而是
**一个 `max_health != 5` 的证据场景**——那是场景资产，不是协议能力。
按题目"优先复用现有机制"的要求，本阶段**不扩协议、不新增夹具属性**，把它记录为缺口。

---

## 6. 专项测试与分段回归

### 6.1 先跑的专项（题目 §五 要求的顺序）

| # | 命令 | 结果 | 退出码 | 用时 |
| --- | --- | --- | --- | --- |
| 1 | `python .ai/tools/scene_composer/feature_behavior_evidence.py --feature health --replay 2` | `pass=5 mismatch=0 insufficient=0 invalid=0 not_declared=0` | **0** | 20.8 s |
| 2 | `python .ai/tools/scene_composer/tests/test_health_behavior.py` | **104 PASS / 0 FAIL** | **0** | 76.0 s |
| 3 | `python .ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | **119 PASS / 0 FAIL** | **0** | 107 s |
| 4 | `python .ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | **249 PASS / 0 FAIL** | **0** | 193 s |
| 5 | Godot `Features/health/test_health.gd` | `PASS: Health 组件验证通过` | **0** | 1 s |
| 6 | Godot `Tests/test_health_integration.gd` | `PASS: Health 集成验证通过` | **0** | 1 s |
| 7 | Godot `Tests/test_damage_interaction.gd` | `PASS: 角色间伤害交互验证通过` | **0** | 2 s |
| 8 | Godot `Features/health_bar/test_health_bar.gd` | `PASS: HealthBar 组件验证通过` | **0** | 1 s |

### 6.2 完整分段回归（串行，单一 HEAD）

第一轮（03:00–03:34）跑在 HEAD `1c30f94`，但运行期间外部提交把 HEAD 推到 `5d585e4`，
证据跨了两个代码状态。为了让「回归结论对应一个确定的树」成立，我在 `5d585e4` 下把
9 段**整段重跑一遍**（脚本 `.ai/tmp/p151reg/run_segments_head2.sh`，
结果 `.ai/tmp/p151reg/RESULTS_head2.txt`，起始 `2026-10-28 08:00:52`，
`staged=0 unstaged=39 untracked=849`）。

| # | 段 | 命令 | 选择数 | 结果 | 退出码 | 用时 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | godot_only | `python .ai/tools/run_tests.py --godot-only` | 38 | 38/38 PASS | **0** | 157 s |
| 2 | scene_composer | `python .ai/tools/run_tests.py scene_composer` | 31 | **31/31 PASS** | **0** | 1002 s |
| 3 | asset_registry | `python .ai/tools/run_tests.py asset_registry` | 11 | 11/11 PASS | **0** | 26 s |
| 4 | feature_registry | `python .ai/tools/run_tests.py feature_registry` | 4 | 3/4（失败项为外部原因，§6.2.1） | **1** | 18 s |
| 5 | gameplay_planner | `python .ai/tools/run_tests.py gameplay_planner` | 2 | 2/2 PASS | **0** | 14 s |
| 6 | runtime | `python .ai/tools/run_tests.py runtime` | 5 | 5/5 PASS | **0** | 57 s |
| 7 | evaluation | `python .ai/tools/run_tests.py evaluation` | 2 | 2/2 PASS | **0** | 14 s |
| 8 | validator | `python .ai/tools/run_tests.py validator` | 10 | 10/10 PASS | **0** | 58 s |
| 9 | e2e | `python .ai/tools/run_tests.py e2e` | 2 | 2/2 PASS | **0** | **831 s** |

合计 **2177 s（36.3 min）**，严格串行（`run()` 上一段结束才启动下一段），
没有任何两段并发读写同一隔离工作目录。

`INCOMPLETE / unavailable / not_executed / TIMEOUT` 四个计数在 8 个通过段里**全部为 0**
（每段末尾的 `[run_tests] completed=…` 行逐段留证）。

#### 6.2.1 唯一的失败段：`feature_registry`（外部原因，非本阶段引入）

**head2 运行（08:25，当时 HEAD 已被推到 `e7fb31a`）**，`.ai/tmp/p151reg/h2_feature_registry.log`：

```
FAIL: validator(real project): no failures | ['Feature index outdated: screen_shake not in index. Please run: build_feature_index.py']
FAIL: validator(real project): checked 12 features | 13
```

**在 `a851ce2` 单独复跑（08:39，`.ai/tmp/p151reg/h3_feature_registry.log`）**，失败项从 1 个变成 2 个，
但根因是同两处硬编码：

```
FAIL: graph: 12 nodes | ['chase_movement', …, 'hit_flash', …, 'screen_shake', 'stun', 'trigger_switch']
FAIL: validator(real project): checked 12 features | 14
```

| 文件:行 | 硬编码 | 实际 |
| --- | --- | --- |
| `.ai/tools/feature_registry/tests/test_composition.py:88` | `len(nodes) == 12` | 14 |
| `.ai/tools/feature_registry/tests/test_feature_pipeline.py:219` | `real["checked"] == 12` | 14 |

原因：本阶段回归窗口内，并行工作流的提交 `e7fb31a`（新增 `screen_shake`）与
`a851ce2`（新增 `hit_flash`）把 `Features/` 从 12 个增加到 14 个，两处 Feature 总数没同步；
`e7fb31a` 落地时连 `feature_index.json` 都还没有 `screen_shake`（`a851ce2` 才重建索引）。

**为什么可以确定与本阶段无关（三条独立证据）**：

1. 失败断言只涉及「Feature 数量」与「`feature_index.json` 是否新鲜」，这两者都不在本阶段改动清单里（§1.2）。
2. 本阶段 9 个改动文件里没有任何 `Features/` 下新增 Feature、没有 `feature_index.json`、
   没有 `feature_registry/tests/*`（逐字核对 `git status`，见 §8.4）。
3. 更早一次 `feature_registry` 段（03:23，当时仍是 12 个 Feature）是 **4/4 PASS**——
   失败是在「Feature 变多」之后才出现的。

**有意不修复**：这两个文件属于并行工作流正在改的范围（其提交在本阶段窗口内仍在持续落地），
按「不修改归属不明的文件、不与他人并发改同一文件」的要求，本阶段只登记、不改动，
并给出准确修复点（两处 `12` → `14`，或改成从索引动态读取数量）。
这**不是放宽断言**：断言本身一个字符都没动，改的会是"仓库里有几个 Feature"这个事实。

#### 6.2.2 在当前 HEAD（`a851ce2`）对核心证据的复核

回归窗口里 HEAD 又被推了两次，所以在收尾时把本阶段最核心的两项证据在当前树上重跑一遍：

| 命令 | 结果 | 退出码 | 用时 |
| --- | --- | --- | --- |
| `python .ai/tools/scene_composer/tests/test_health_behavior.py` | `PASS: all health behaviour checks passed` | **0** | 63 s |
| `python .ai/tools/scene_composer/feature_behavior_evidence.py --feature health --require-behavior --replay 2` | `pass=5 mismatch=0 insufficient=0 invalid=0 not_declared=0` | **0** | 21 s |

两项均在 "14 个 Feature、Godot 40 个测试" 的当前树上通过，说明本阶段的检出能力不依赖于
回归当时的树；唯一在新树上失效的是外部并行工作流自己的计数断言（§6.2.1）。

### 6.3 回归期间暴露并修复的问题（如实记录）

首次跑 `scene_composer` 段时 **exit 1**，唯一失败项是
`.ai/tools/scene_composer/tests/test_behavior_time_driven.py` Case 7：

```
case7: six legacy behaviors reported | [('collect_pickup', ...), ('health', 'damage'),
  ('health', 'death'), ('health', 'heal_clamped'), ('health', 'overkill_clamps_at_zero'),
  ('health', 'post_death_guard'), ('openable_door', 'open')]
```

原因：该断言把「四个 legacy Feature 的 behavior 个数」硬编码为 6，而 `health` 在本阶段从 3 条
变成 5 条，实际为 8。**这是仓库里第三个硬编码行为计数的地方**（前两个是
`test_behavior_protocol_consistency.py:447` 与 `test_feature_behavior_evidence.py:195`，
都在事前审计时找到并同步更新；漏掉的是这一个）。

修法与验证：计数改为 8 并标明来源（**跟进仓库真实声明，不是放宽断言**），
单独重跑该测试 → **74 PASS / 0 FAIL / exit 0**（112 s），随后在 `5d585e4` 下整段重跑
`scene_composer` → **31/31 PASS / exit 0 / 1002 s**（§6.2 第 2 行）。

事前审计的教训（记录下来而不是掩盖）：我按“行为总数”搜索硬编码时，
找的是 `len(reports) ==` / `len(contracts) ==` 这类形态，而这个词条写的是
`len(observed) == 6` 且测试名与 Phase 1.51 无关（时间驱动行为），因此漏掉了。
全量分段回归正是为了抓这类“按名字搜不到”的耦合。

---

## 7. 分段覆盖并集证明

题目要求"通过文件清单与去重证明分段测试并集完整，不得把重叠文件重复计入"，
且"若不能执行全量单命令，必须明确报告这一限制"。

- 发现集合（Phase 1.51 实测，`5d585e4`）：Godot **38**（`Features/*/test_*.gd` + `Tests/test_*.gd`）、
  Python **61**（`.ai/tools/**/tests/test_*.py`）→ 全量 **99**。
  （`a851ce2` 之后新增 `screen_shake` / `hit_flash` 两个 Godot 测试文件，实测变为 **40 / 61 / 101**；
  这是并行工作流带来的增量，不是本阶段的结果，也解释了 §6.2.1 的计数失败。）
- 8 个具名 Python 段的选择数之和 = **67**（`scene_composer` 31 + `asset_registry` 11 +
  `feature_registry` 4 + `gameplay_planner` 2 + `runtime` 5 + `evaluation` 2 + `validator` 10 + `e2e` 2），
  去重后 = **61**，**没有任何 Python 测试文件落在 8 段之外**。
- 差额 67 − 61 = 6，全部是同时命中两段的重叠文件（如 `scene_composer/tests/test_*_validator*.py`
  同时属于 `scene_composer` 与 `validator`），**只在并集里计一次**。
- 因此 9 段串行覆盖 = 全量 99 个测试。
- **限制（如实列出）**：本次**没有跑"一条全量单命令"**——`scene_composer` 单段就 1002 s、
  `e2e` 单段 831 s，两段**各自**都超过工具的 10 分钟（600 s）单命令时限，全量命令必然超时。
  9 段是在一个后台脚本里串行跑的（不占单命令时限），因此**每一段都能拿到真实退出码**；
  结论建立在"并集完整"的证明之上，而不是建立在一次全量运行之上。

`run_tests.py` 的 docstring 计数也按实测更正为 61 / 99（Phase 1.50 当时是 60 / 98）。

---

## 8. 文件恢复、哈希与 Git 状态

### 8.1 注入的隔离与恢复

- 注入对象：`BehaviorWorkspace` 隔离副本里的
  `.ai/tmp/behavior/workspace-*/project/Features/health/health.gd`（8 次注入 + 1 次"缺口"注入）。
- 每次 `try/finally` 写回**原始字节**，随后断言该副本 `sha256` == 注入前基线。
- 测试另有断言：仓库 `Features/health/health.gd` 的 `sha256` == 交给工作区时的基线
  （即注入**没有泄漏**到仓库）。
- `case2: the chain is green again after all incidents` 在全部注入结束后重跑 5 条契约，全部 PASS。

### 8.2 关键文件哈希（Phase 1.51 结束时）

```
e89b46924bce1e6da92711e62097d8671cc8c9ca63688f6c3fd8287af9b4b9bb  Features/health/health.gd
5c6cfa3ea3dfb2c93fbbcc28becaaa70ffda750299394901d1901e9e994db83b  Features/health/template.yaml
2e2b01eccafd5560e2c04ce8899a7a84d7734741367756bf60f570ca38bfc340  Features/health/Health.tscn
bbcc76d4bee3dff8e61c75e1e3b68bfa930eb5d31e8e35d7d37d329fced6a4c0  .ai/context/behavior_protocol.yaml
65ad372f0a20267328ccd16bb6c08b2c83493801d67a1cc29b10a6f1a665d7de  .ai/tools/scene_composer/probes/behavior_manifest.json
```

`health.gd` 与 `Health.tscn` **逐字节未改**（本阶段没有修改任何游戏实现）；`template.yaml` 的改动
就是 §1.2 里那三条契约变更（**只增不减**：原有 3 条的断言没有一条被放宽或删除）。

### 8.3 临时目录

- 本阶段新建：`.ai/tmp/p151reg/`（回归日志与 `RESULTS.txt`）、`.ai/tmp/p151_health_test.log`
  —— 均在 `.ai/tmp/`（`.gitignore`）之下，保留为证据。
- `test_health_behavior.py` 自己的 `_tempdir`（`health_behavior_*`）与它创建的
  `BehaviorWorkspace`（`.ai/tmp/behavior/workspace-*`）都在 `finally` 里清理。
- **未清理的既有目录（非本阶段产生，未删除）**：
  `.ai/tmp/behavior_tests_49ypbs3j`（10-22）、`.ai/tmp/behavior_tests_7jtzqmb8`（10-22）、
  `.ai/tmp/behavior/workspace-avb_9s21`（10-26，中断的那次会话）、
  `.ai/tmp/behavior/workspace-eb238eca`（10-24）。
  按题目"不删除归属不明的临时目录"的要求，**只登记不删除**。

### 8.4 Git 状态

```
HEAD            1c30f94 → 5d585e4 → e9d8a74 → f99c771 → e7fb31a → a851ce2（后 5 次全为外部提交）
branch          master（未变）
staged          0 项
modified        38 项（本阶段 3 项 + Phase 1.26–1.50 的既有修改）
untracked       849 项（含本阶段新增的 6 个文件与并行工作流的 code_library 资产）
```

本阶段的 9 个文件**全部仍在工作区、未被任何外部提交带走**（`git status --short` 逐字）：

```
 M .ai/context/CONTRACT_INDEX.yaml
 M .ai/tools/run_tests.py
 M Features/health/template.yaml
?? .ai/context/FEATURE_BEHAVIOR_COVERAGE.md
?? .ai/context/PHASE_1_51_AUDIT.md
?? .ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py
?? .ai/tools/scene_composer/tests/test_behavior_time_driven.py
?? .ai/tools/scene_composer/tests/test_feature_behavior_evidence.py
?? .ai/tools/scene_composer/tests/test_health_behavior.py
```

未执行 `git reset` / `git checkout` / `git clean` / `git add` / `git commit` / `git push`。
Phase 1.26–1.50 的既有未提交修改**完整保留**（本阶段只新增/改动 §1.2 列出的文件）。
`Features/health/health.gd` 在整个过程中逐字节未变（§8.2 哈希与注入前基线相同）。

---

## 9. 尚未解决的缺口

### 9.1 `max_health` 初始化不可观测（**实测缺口，不是推测**）

注入 2i：`_ready()` 里 `_current_health = max_health` → `= 5`。
**结果：5 条契约全部 PASS。** 因为仓库里每一条 health 契约都跑在 `Health.tscn`（`max_health` 默认 5）上，
没有任何契约见过 `max_health != 5` 的场景。

要补它，需要**先做一个决定**（不是测试能单方面推动的）：

1. 加一个 `Features/health/HealthFixture.tscn`（`Health` + `max_health = 10`），仿 `HealthBarFixture`；
   或
2. 声明一个只读观测 `health.max_health`。

两条路都不在"只改 health 契约与测试"的范围内，因此**本阶段不做，按缺口记录**。

### 9.2 0 / 负数输入在行为证据层不可表达（协议边界，非缺陷）

`health.take_damage` / `health.heal` 的 `amount` 声明为 `int, min: 1, max: 100`。
实测：`amount: 0`、`-3`、`101`、`"four"` 一律 **INVALID**（文案
`actions[0].params.amount does not match type int`）。因此"0/负数被忽略"这条行为
**只能**由 Godot 单元测试 `Features/health/test_health.gd` 覆盖——它在真实运行时里断言了
`take_damage(0)` / `take_damage(-1)` / `heal(0)` / `heal(-2)` 不改变生命值。本阶段**不改参数域**：
扩大域会让所有契约都能对组件传越界值，属于降低护栏。

### 9.3 `max_health` 运行期变更：无观测、无夹具

`properties:` 里没有 `health.max_health`，`state.set_property` 无法用于 Health；
`max_health` 变化后 `_current_health` 也不会被重新钳制（组件没有 setter）。
这既是"未覆盖的行为"，也是"实现本身的语义未定义"——**应当先做组件设计决定，再谈契约**。

### 9.4 未覆盖的其它边界（事实）

- `health_changed` 在**同一次调用**里被触发两次（实现不会发生，但也没有契约禁止）。
- `max_health <= 0` 的退化配置。
- 多个 Health 实例之间的独立性（组合层 `slime_contact` 间接覆盖了"玩家 Health"一个实例）。

### 9.5 组合层

`health` 在组合层只被 `slime_contact` 的 `Player/Health` 间接覆盖（且只覆盖 `damage` 路径）。
本阶段**没有**改任何组合契约，也没有改白名单。

---

## 10. 对 `FEATURE_BEHAVIOR_COVERAGE.md` 的修改依据

`health` 由 `PARTIAL` 改为 `VERIFIED`，依据是本文件里可以逐条核对的事实：

- 有正式行为契约（5 条，`Features/health/template.yaml#behavior`）；
- 全部在真实 Godot 运行时执行（`action_executed=True`、无夹具动作、`waited_frames=0`）；
- 2 次重放一致（`replay_consistent=True`）；
- **有能拒绝错误实现的负向对照**（8 类注入被检出，每条都指名契约与失败层）；
- 观察不到证据时是 `INSUFFICIENT`（目标缺失 / 前置不满足实测），现象不成立是 `MISMATCH`。

矩阵同时保留降低结论强度的说明：1 类注入不被检出（§9.1）、0/负数不可表达（§9.2）、
`max_health` 运行期变更无观测（§9.3）。

同步更新：行为总数 30 → 32；统计 `VERIFIED 8 / PARTIAL 4` → **`VERIFIED 9 / PARTIAL 3`**；
§6 缺口清单新增第 6 条；§7 建议重排；附命令里的"30 条"改为"32 条"并加上本阶段测试。

---

## 11. 下一阶段建议

按**证据缺口**排序，不按代码量：

1. **`player_movement` 的缺陷注入**：它是 `escape_room` 与 `slime_contact` 两个组合场景的地基，
   速度/松键语义坏掉会以"别的形态"失败，最难定位。注入方向：`speed` 常量被改、松键后仍加速、
   输入动作名写错（observation 会显示位移不符）。
2. **`collect_pickup` / `heal_pickup` 的缺陷注入**：两者都是 `physics.overlap` 触发，
   注入方式可直接参考 Phase 1.47 的 `contact_damage`。
3. **`health` 的 `max_health` 缺口**：先决定"加证据场景"还是"加只读观测"，再实现；
   这是一个**组件/资产决策**，不应由测试悄悄推动。
4. **组合层可选方向**：`health_bar` 在 `Scenes/Enemy.tscn` 里已有实例但无组合契约；
   若要覆盖，需要先确认"敌人血条跟随"是正式设计（`health_bar` 目前未进入任何组合场景）。

---

## 附：本阶段命令清单（可复制）

```bash
# 正向基线（5 条契约，重放 2 次）
python .ai/tools/scene_composer/feature_behavior_evidence.py --feature health --replay 2

# 负向对照：9 类注入 + 证据不足 + 重放 + 无效契约 + CLI 与恢复
python .ai/tools/scene_composer/tests/test_health_behavior.py

# 受影响的计数断言与协议一致性
python .ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py
python .ai/tools/scene_composer/tests/test_feature_behavior_evidence.py

# Godot 侧 health
godot --headless --path . -s res://Features/health/test_health.gd
godot --headless --path . -s res://Tests/test_health_integration.gd

# 完整分段回归（串行；单命令会超工具时限，见 §7）
python .ai/tools/run_tests.py --godot-only
python .ai/tools/run_tests.py scene_composer
python .ai/tools/run_tests.py asset_registry
python .ai/tools/run_tests.py feature_registry
python .ai/tools/run_tests.py gameplay_planner
python .ai/tools/run_tests.py runtime
python .ai/tools/run_tests.py evaluation
python .ai/tools/run_tests.py validator
python .ai/tools/run_tests.py e2e
```
