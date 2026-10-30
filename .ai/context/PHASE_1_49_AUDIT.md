# Phase 1.49 审计报告 — Feature Behavior Coverage Audit & Gap Closure

日期：2026-10-26
环境：Windows，Godot 4.7 stable headless，CPython 3.12
被测仓库：`F:\Godot_v4.7-stable\game`

本阶段做了两件事：

1. 为 **12 个正式 Feature** 建立可追溯的行为证据覆盖矩阵（`FEATURE_BEHAVIOR_COVERAGE.md`）。
2. 按矩阵选出一个最高价值缺口 **`stun`** 并完整补齐：真实运行时行为契约 5 条、
   证据场景 1 个、测试 1 个（70 条断言）、5 类缺陷注入 + 4 类证据不足/非法对照。

协议层只新增了 1 个信号条目（`stun.stunned`）；**没有**新增动作或观测能力。
没有提交、没有推送，也没有清理任何归属不明的文件。

---

## 1. 修改前后的 Git 状态

### 1.1 开始前（基线）

```
HEAD            1c30f94  feat: unified run identity, e2e serial lock and resource ownership hardening (Phases 1.26-1.34)
branch          master
staged          0 项（git diff --cached 为空）
工作区 modified 37 项（Phase 1.26–1.48 的既有未提交修改）
未跟踪          43 项（含 .ai/context/PHASE_1_36..1_48_AUDIT.md、scene_composer 的
                behavior_protocol.py / composite_behavior_evidence.py / probes/ /
                instance_evidence.py / runtime_instance_evidence.py、
                .ai/context/composite_scenes/、Features/*/…Fixture.tscn 等）
```

这些修改**在本阶段开始前就存在**，本阶段只读取、不覆盖；最终状态里它们仍然在（见 §1.3）。

### 1.2 本阶段新增 / 修改（只有这些）

| 文件 | 动作 | 内容 |
| --- | --- | --- |
| `Features/stun/StunFixture.tscn` | **新增** | 证据场景：`Host`(CharacterBody2D + `player_controller.gd`) + `Health(10)` + `Stun(stun_on_hit=true, stun_duration=0.4)` |
| `Features/stun/template.yaml` | 修改 | 追加 `behavior:` 5 条契约 + 数值推导注释（原有 `interfaces` / `validation` 未动） |
| `.ai/context/behavior_protocol.yaml` | 修改 | `signals:` 追加 `stun.stunned`（1 条）；actions / observations / properties 不变 |
| `.ai/tools/scene_composer/probes/behavior_manifest.json` | 重新生成 | `python .ai/tools/scene_composer/behavior_protocol.py --write-manifest` → `PASS: manifest matches the protocol` |
| `.ai/tools/scene_composer/tests/test_stun_behavior.py` | **新增** | 70 条断言：正向 5 条行为 + 5 类缺陷注入 + 观测缺口 + 重放 + 非法契约 + CLI |
| `.ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | 修改 | 信号计数 6 → 7（并注明 Phase 1.49）；Case 8 追加 5 条 stun 行为断言 |
| `.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | 修改 | 行为总数 20 → 25；追加 5 条 stun 行为存在性断言 |
| `.ai/tools/scene_composer/tests/test_condition_gate_behavior.py` | 修改 | 陈旧断言 `signals == 6` → 7（原因见 §6.5，不是放宽断言） |
| `.ai/tools/run_tests.py` | 修改 | scene_composer 段计数 28 → 29，注释登记 Phase 1.49 |
| `.ai/context/CONTRACT_INDEX.yaml` | 修改 | `behavior_evidence.test_stun` 登记 |
| `.ai/context/FEATURE_BEHAVIOR_COVERAGE.md` | **新增** | 覆盖矩阵 |
| `.ai/context/PHASE_1_49_AUDIT.md` | **新增** | 本报告 |

### 1.3 结束时

```
staged          0 项（仍未 stage 任何文件）
工作区 modified 38 项（37 项既有 + Features/stun/template.yaml 的既有修改之上追加 behavior 块）
未跟踪          45 项（43 项既有 + StunFixture.tscn + 本次两个新文档 / 测试）
```

`git diff --stat` 显示既有 37 个文件的改动（1962 insertions / 117 deletions）仍在，未回退。
本阶段没有执行 `git reset --hard`、`git checkout`、`git clean`、`git add`、`git commit`、`git push`。

---

## 2. Feature 证据矩阵（摘要）

完整矩阵、逐条依据与命令见 [FEATURE_BEHAVIOR_COVERAGE.md](FEATURE_BEHAVIOR_COVERAGE.md)。
结论：

| 状态 | 数量 | Feature |
| --- | --- | --- |
| `VERIFIED` | 7 | `chase_movement`、`condition_gate`、`contact_damage`、`moving_platform`、`openable_door`、`stun`、`trigger_switch` |
| `PARTIAL` | 4 | `collect_pickup`、`heal_pickup`、`health`、`player_movement`（有运行时行为证据与重放，但缺本 Feature 级缺陷注入） |
| `UNIT_TESTED` | 1 | `health_bar`（纯显示，协议无读 `get_ratio()` 的观测） |
| `NOT_COVERED` / `INSUFFICIENT` | 0 / 0 | — |

合计声明 **25 条 behavior**（1.45 时 17 条；1.47 +3 contact_damage；1.49 +5 stun）。

> 口径变更（已在矩阵 §2 说明）：1.45 的 `RUNTIME_VERIFIED` 只要求「有运行时证据 + 重放一致」，
> 本阶段把「**能拒绝错误实现**（缺陷注入）」纳入 `VERIFIED` 的必要条件，
> 因此 `health` / `collect_pickup` / `heal_pickup` / `player_movement` 由 1.45 的通过口径降为 `PARTIAL`。
> 这是判据加严，不是证据退化——它们的运行时证据与重放结果都没有变化。

---

## 3. 缺口选择依据：为什么是 `stun`

题目要求「优先审计 `stun`，但若它已充分验证或另有更严重缺口，则调整并说明」。审计结论：

1. `stun` 在 1.45 矩阵里是 `UNIT_TESTED`：只有 `Features/stun/test_stun.gd` 一个单元测试，
   **0 条** behavior、**0** 条缺陷注入、**无**实例证据。
2. 与同样 `UNIT_TESTED` 的 `health_bar` 相比，`stun` 的风险面更大：
   - 它**改变宿主物理状态**（`set_physics_process(false/true)` + 速度清零），错了会让实体永久停摆；
   - 它有 3 个相互影响的语义（受击触发 / 长盖短 / 死亡守卫 / 幂等广播），单测覆盖的是方法层，
     不是「受击→停摆→恢复」的运行时链；
   - 它是 `contact_damage` / `chase_movement` / `health` 组合的邻居（`feature.yaml` 的
     `works_with: contact_damage`），这条链已经在 1.47/1.48 有正式验收。
3. `health_bar` 需要**协议扩展**（新增读 `get_ratio()` 的观测）才能建行为契约；题目要求
   「只需修改 Feature 契约与测试时不要扩大通用协议」。它因此不作为本阶段的实施对象，
   而是登记为下阶段第 1 项（矩阵 §7）。
4. 其余 4 个 `PARTIAL` 缺的只是缺陷注入，不需要协议变更，但价值低于 `stun`（它们已有运行时证据）。

结论：实施 `stun`，`health_bar` 记录阻塞理由。

---

## 4. 契约设计与最小区分度

### 4.1 被测语义（从源码读出的事实，不是对观测的拟合）

`Features/stun/stun.gd`：

| 语义 | 源码依据 |
| --- | --- |
| 受击触发 | `_on_host_health_changed`：`current < _last_health` 才算受击（`health_changed` 在治疗时也发、`amount` 恒为正）；命中后 `stun.call_deferred(stun_duration)` |
| 停摆范围 | `stun()`：`_host.set_physics_process(false)` + `velocity = ZERO` |
| 长盖短 | `_remaining = maxf(_remaining, duration)`，进入时只在 `_remaining <= 0` 时广播 `true` |
| 到点恢复 | `_process(delta)` 递减，归零时恢复物理并广播 `false` |
| 死亡守卫 | `stun()` 里 `if _health != null and _health.is_dead(): return false`；恢复时也检查，不越权复活物理 |

### 4.2 证据场景 `Features/stun/StunFixture.tscn`

```
StunFixture (Node2D)
└── Host (CharacterBody2D, player_controller.gd)   ← 输入 move_right 驱动真实位移
    ├── Collision (32×48)
    ├── Health (Health.tscn, max_health=10)         ← 真实 health_changed 来源
    └── Stun (Stun.tscn, stun_on_hit=true, stun_duration=0.4)
```

为什么必须是这样：

- **触发只走真实链路**：契约里唯一的伤害动作是 `health.take_damage`，它触发 `Health.health_changed`，
  再经 `stun_on_hit` 的订阅（含 `call_deferred` 落地）。**不调用 `stun()` 方法**——那会绕过被测的
  触发逻辑，等于自己把结果设成想要的样子。
- **可观测的是宿主物理，不是私有字段**：眩晕没有公开状态可读（`is_stunned()` 不在协议里），
  所以证据是「同一套输入下宿主是否还在动」。这比读 `_remaining` 更接近玩家可感知的语义。
- **入口场景未被改动**：`Features/stun/Stun.tscn` 一个字节都没改（测试里有断言），
  证据场景是平行文件，不进生成流程。

### 4.3 数值推导（不是拟合）

```
PlayerController.speed = 220 px/s；physics 60 Hz → 3.667 px/帧
stun_duration = 0.4 s → 24 帧
20 帧全速 ≈ 73.3 px    （未眩晕的反例）
24 帧全速 ≈ 88.0 px    （治疗对照）
24 帧眩晕 + 20 帧移动 ≈ 77.0 px
```

因此断言阈值是「冻结 / 未冻结」的区分线（`≤ 8 px` vs `≥ 45 px` vs `≥ 60 px`），
不是把某次观测抄成常量。

### 4.4 五条契约

| # | behavior | 前置 | 动作（全部真实） | 后置断言 |
| --- | --- | --- | --- | --- |
| 1 | `hit_stuns_and_freezes_host` | HP=10，`stunned` 计数 0 | press → 1 帧 → `take_damage(1)` → 20 帧 | x∈[-1,8]；y=0±0.5；HP=9；`stunned` 1 次且 `[true]` |
| 2 | `stun_expires_and_host_resumes` | HP=10 | press → 1 帧 → `take_damage(1)` → 44 帧 | x∈[45,100]；HP=9；`stunned` 2 次且 `[false]` |
| 3 | `heal_does_not_stun` | HP=10（满血） | press → 1 帧 → `heal(1)` → 24 帧 | x∈[70,95]；HP=10；`stunned` 0 次 |
| 4 | `death_guard_rejects_stun` | HP=10 | press → 1 帧 → `take_damage(10)` → 20 帧 | x∈[60,80]；HP=0；`is_dead`；`stunned` 0 次 |
| 5 | `reentry_extends_without_rebroadcast` | HP=10 | press → 1 帧 → `take_damage(1)` → 6 帧 → `take_damage(1)` → 10 帧 | x∈[-1,8]；HP=8；`stunned` 1 次且 `[true]` |

行为 3 是**边界对照**：`health_changed(10, 1)` 在治疗时也会发出，如果实现把「amount>0 即受击」，
这条会用 24 帧的 88 px 变成 ≈22 px 而失败（§6.2c 实证）。
行为 5 是**状态机幂等**：眩晕中再受击只延长时间，不产生第二个 `true`。

---

## 5. 真实运行时证据与重放

命令：

```
python .ai/tools/scene_composer/tests/test_stun_behavior.py        # exit 0，70 PASS
python .ai/tools/scene_composer/feature_behavior_evidence.py --all --require-behavior --replay 2
#   pass=25 mismatch=0 insufficient=0 invalid=0 not_declared=0，exit 0
```

每条行为的实测值（来自证据目录 `.ai/tmp/behavior/<run_id>-<behavior>-r{1,2}/result.json`）：

| behavior | 动作全部执行 | 观测帧（physics） | 实际观测 | `waited_frames` | replay |
| --- | --- | --- | --- | --- | --- |
| `hit_stuns_and_freezes_host` | 4/4 | 21 帧推进后（第 29 物理帧） | x=**3.667**，y=**0.0**，HP=**9**，`stunned`=**1** | 0 | 2 次一致 PASS |
| `stun_expires_and_host_resumes` | 4/4 | 45 帧推进后（第 54 物理帧） | x=**77.0**，HP=**9**，`stunned`=**2** | 0 | 2 次一致 PASS |
| `heal_does_not_stun` | 4/4 | 25 帧推进后（第 35 物理帧） | x=**88.0**，HP=**10**，`stunned`=**0** | 0 | 2 次一致 PASS |
| `death_guard_rejects_stun` | 4/4 | 21 帧推进后（第 30 物理帧） | x=**73.333**，HP=**0**，`is_dead`=**true**，`stunned`=**0** | 0 | 2 次一致 PASS |
| `reentry_extends_without_rebroadcast` | 6/6 | 17 帧推进后（第 26 物理帧） | x=**3.667**，HP=**8**，`stunned`=**1** | 0 | 2 次一致 PASS |

要点：

- **`waited_frames == 0`**：五条契约的后置条件都在脚本最后一帧立刻成立，没有靠 `window_frames`
  「等到对为止」。窗口（5/10 帧）只是容差上限；测试里有一条断言专门锁这一点。
- **`3.667 px` 是「落地前最后一帧」的位移**：`call_deferred` 让停摆晚一帧生效，这与源码语义一致，
  也是为什么下界写成 `-1.0` 而不是 `0.0`（不是放宽，是把真实机制写进契约）。
- 重放比较的是关键结果（状态 / 计数 / 参数），忽略帧号与耗时；两次语义一致才 PASS。

---

## 6. 负向对照（隔离副本，逐字节恢复）

全部注入都在 `feature_behavior_evidence.BehaviorWorkspace` 的隔离工程副本里完成：
先 `sha256` 记录，注入后运行，再写回原始字节并复核哈希。仓库文件的哈希由测试独立断言。

| # | 注入（隔离副本） | 期望判定 | 实际结果 | 恢复 |
| --- | --- | --- | --- | --- |
| 2a | `stun()` 里 `_host.set_physics_process(false)` → `pass` | 行为 1 `MISMATCH/state_mismatch` | ✅ `MISMATCH`；x≈**73.3**（>60，照常移动）；`stunned` 仍 ≥1（说明失败点是停摆，不是广播）；行为 3 仍 PASS | SHA 一致 |
| 2b | `_process` 里 `set_physics_process(true)` → `pass` | 行为 2 `MISMATCH` | ✅ `MISMATCH`；x≤**8**；`stunned`=**2**（`false` 边沿照发——证明「状态转移」与「物理恢复」是两件事）；行为 1 仍 PASS | SHA 一致 |
| 2c | `var damaged := current < _last_health` → `= true`（治疗也算受击） | 行为 3 `MISMATCH` | ✅ `MISMATCH`；x≈**22**（≪88）；`stunned` ≥1；行为 1 仍 PASS | SHA 一致 |
| 2d | 删除 `stun()` 内死亡守卫 | 行为 4 `MISMATCH` | ✅ `MISMATCH`；x≤**8**（尸体被冻结）；`stunned` ≥1；行为 1 仍 PASS | SHA 一致 |
| 2e | `if _remaining <= 0.0:` → `if true:`（重复广播） | 行为 5 `MISMATCH` | ✅ `MISMATCH`；`stunned`=**2**（允许 1）；行为 1、2 仍 PASS | SHA 一致 |
| 2f | 场景 `stun_on_hit = true` → `false`（触发链没接上） | 正向三条 `MISMATCH` | ✅ 行为 1/2/5 全 `MISMATCH`；x≈**73.3**、`stunned`=0；行为 3 仍 PASS；**行为 4 仍 PASS**（见下） | SHA 一致 |
| 3a | 观测目标 `Host/MissingStun` | `INSUFFICIENT/check_unavailable` | ✅ | — |
| 3b | 3 帧窗口 + `min: 45`（看不到 0.4 s 恢复） | `MISMATCH`，不是 PASS | ✅ `MISMATCH/state_mismatch`，x≤8；同一条契约把窗口放到 50 帧后 **PASS**（x>45） | — |
| 4 | 第 2 次重放注入不同观测值 | `INSUFFICIENT/replay_inconsistent` | ✅ 两次运行都保留在证据里（第 2 次的 `observed=999` 可见） | — |
| 5 | 非法契约：`window_frames: 0`、未知信号 `stun.teleported`、场景路径越界、`take_damage` 缺 `amount` | `INVALID`，且不启动 Godot | ✅ 4/4 `INVALID`，错误信息指向上游原因 | — |
| 6 | 仓库 `Features` 副本中删除停摆调用，跑 CLI | 退出码 1，且失败项是 `hit_stuns_and_freezes_host` | ✅ `exit 1`；stdout 出现该 behavior 名 + `MISMATCH` | 副本 SHA 一致；仓库文件哈希未变；manifest 仍与协议一致 |

### 6.1 一个必须如实记录的弱项（行为 4 是「absence 型」契约）

注入 2f（触发链没接上）时，**`death_guard_rejects_stun` 仍然 PASS**——因为它断言的是「死亡时没有眩晕」，
触发链断了恰好也「没有眩晕」。这是 absence 型契约的固有弱项，测试里用一条断言把这个现象**显式固定**
（`case2: the absence-only death contract cannot see the unwired trigger`），并由行为 1/2/5 三条正向契约
负责抓这个缺陷。**没有**通过放宽或删除行为 4 来掩盖它，也没有把它算作「能抓 2f」。

### 6.2 失败原因确实是目标缺陷（不是「非零退出码就算有效」）

每条注入都额外断言了「失败的具体表现」与「相邻行为仍然 PASS」：

- 2a 断言 x 由 3.667 变成 >60（冻结消失），且广播仍存在；
- 2b 断言 x≤8（仍然冻结）且 `false` 仍发出 2 次；
- 2c 断言 x<45（治疗把宿主冻住了）；
- 2d 断言死者被冻结（x≤8）且 `is_dead` 仍为 true；
- 2e 断言 `stunned` 变成 2 次；
- 2f 断言正向三条同时 `MISMATCH` 且宿主以 ≈73 px 自由移动。

如果只是「某个数字不匹配」而相邻行为一起坏掉，这些断言会失败——它们就是为此写的。

### 6.3 隔离与恢复验证

- 注入只在 `BehaviorWorkspace` 的 `<temp>/project/Features/...` 副本上做；
- 每次注入后立即写回原始字节，并断言 `sha256` 等于注入前的基线；
- 测试结束断言 **仓库** `Features/stun/stun.gd`、`StunFixture.tscn`、`template.yaml` 的哈希未变；
- 测试结束断言 `behavior_manifest.json` 仍与 `behavior_protocol.yaml` 一致；
- 临时目录 `.ai/tmp/stun_behavior_*` 在 `finally` 中 `shutil.rmtree`，本次运行后无残留。

### 6.4 临时文件与遗留目录（实测）

| 路径 | 本阶段是否使用 | 现状 |
| --- | --- | --- |
| `.ai/tmp/t149*_*.log`（73 个） | 是 | **保留**：§8 每一条退出码的原始输出，供复核 |
| `.ai/tmp/behavior/<run_id>-<behavior>-r{1,2}/` | 是 | 保留（证据目录，含 `contract.json` / `result.json`），由行为框架自己拥有 |
| `.ai/tmp/composite/<run_id>/` | 是 | 保留（同上） |
| `.ai/tmp/stun_behavior_*` | 是 | **已删除**（测试 `finally` 里清理） |
| `.ai/tmp/composite/workspaces/7276-…-slime` | 否（但由本阶段之前的运行产生） | **未删除**：那是上一会话被 600 s 上限终止时留下的隔离工作区（mtime 2026-10-25 02:47）。它不属于本次运行，按框架的所有权规则只报告、不删。 |
| `.ai/tmp/behavior/workspace-eb238eca`（10-24）、`.ai/tmp/behavior_tests_49ypbs3j` / `_7jtzqmb8`（10-22） | 否 | **未删除**：更早阶段的遗留，归属不明，不动。 |

本阶段**没有**删除任何不是自己创建的目录；也没有因为“看着像临时文件”就清理 `.ai/tmp`。

---

## 7. 协议与 manifest 变更

| 项目 | 变更 | 校验 |
| --- | --- | --- |
| `behavior_protocol.yaml` | `signals:` 新增 `stun.stunned`（`signal: stunned`，`args: [bool]`） | `behavior_protocol.py --write-manifest` → `PASS: manifest matches the protocol` |
| actions | **未变**（8 项） | `test_behavior_protocol_consistency.py` Case 1 精确锁定 8/11/7/1 |
| observations | **未变**（11 项） | 同上 |
| properties | **未变**（1 项） | 同上 |
| `protocol_version` | **未变**（2） | 同上 |
| 组合场景协议 | **未变**（3 个场景、预算、`denied_actions` 均未动） | `test_composite_behavior_evidence.py` 100 PASS |
| 探针 `feature_behavior_probe.gd` | **未改**（1.47 的 `@actor` 监听改动已存在） | 协议能力门禁 PASS |

为什么必须新增这个信号：行为的核心语义之一是「跨越时广播一次 `true`，恢复时广播一次 `false`，
重复同值不广播」。协议只允许对已注册信号做 `signal` 计数观测；没有 `stun.stunned` 就无法观测
「幂等广播」这条契约。它的形态与 1.46 为组合链新增的 `gate.fulfilled` 完全一致（同样的 `args` 形状、
同样只读），**不引入任何写入或调用能力**。

---

## 8. 回归测试（逐段命令、结果、退出码）

所有命令都在仓库根目录执行，日志留在 `.ai/tmp/t149*_*.log`。**没有任何一段是把没跑完的测试
说成通过**：每条都是独立进程、独立日志、独立退出码。

### 8.1 本阶段新增/修改的测试与证据入口

| # | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 1 | `python .ai/tools/scene_composer/tests/test_stun_behavior.py` | **70 PASS / 0 FAIL**（正向 5 条 + 5 类注入 + 观测缺口 + 重放 + 非法契约 + CLI） | **0** |
| 2 | `python .ai/tools/scene_composer/feature_behavior_evidence.py --all --require-behavior --replay 2` | `pass=25 mismatch=0 insufficient=0 invalid=0 not_declared=0` | **0** |
| 3 | `python .ai/tools/scene_composer/runtime_instance_evidence.py --all` | `pass=6 mismatch=0 insufficient=0 invalid=0 not_declared=0` | **0** |
| 4 | `python .ai/tools/scene_composer/composite_behavior_evidence.py --all --require-composite --replay 2` | escape_room 4/4、slime_contact 3/3、survival_arena 2/2，均 `replay=2 consistent=True` | **0** |
| 5 | `python .ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | **110 PASS**（含 Phase 1.49 的 stun 5 条断言） | **0** |
| 6 | `python .ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | **213 PASS**（行为总数 20 → 25 的断言在此） | **0** |
| 7 | `python .ai/tools/scene_composer/tests/test_condition_gate_behavior.py` | **53 PASS**（修陈旧计数断言之前是 51 PASS / 1 FAIL，见 §8.5） | **0** |
| 8 | `python .ai/tools/scene_composer/tests/test_slime_contact_arena.py` | **77 PASS** | **0** |

### 8.2 其余 scene_composer 测试（逐文件独立运行）

| 文件 | PASS | 退出码 | | 文件 | PASS | 退出码 |
| --- | --- | --- | --- | --- | --- | --- |
| `test_behavior_time_driven` | 72 | 0 | | `test_capability_contract_validator` | 42 | 0 |
| `test_chase_movement_behavior` | 31 | 0 | | `test_component_instance_materialization` | 58 | 0 |
| `test_contact_damage_behavior` | 39 | 0 | | `test_component_instance_ownership` | 39 | 0 |
| `test_composite_behavior_evidence` | 100 | 0 | | `test_composite` | 17 | 0 |
| `test_external_artifact_evidence` | 45 | 0 | | `test_entity_root_instance` | 26 | 0 |
| `test_feature_instance_evidence` | 41 | 0 | | `test_feature_capability_adoption` | 131 | 0 |
| `test_instance_evidence_reconciliation` | 53 | 0 | | `test_feature_capability_pipeline` | 37 | 0 |
| `test_runtime_instance_evidence` | 67 | 0 | | `test_plan_generator` | 25 | 0 |
| `test_artifact_evidence_validator` | 39 | 0 | | `test_scene_builder_intent_input` | 42 | 0 |
| `test_scene_compatibility_gate` | 62 | 0 | | `test_scene_composer` | 49 | 0 |
| `test_scene_intent_capability` | 46 | 0 | | `test_scene_intent_contract` | 68 | 0 |
| `test_scene_intent_runtime` | 44 | 0 | | `test_scene_validator_intent_input` | 48 | 0 |

即 `run_tests.py` 口径下的 **29 个 scene_composer 测试全部 exit 0**（29 个文件，逐个独立运行）。

### 8.3 门禁入口（`run_tests.py` 与 Validator）

| # | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 9 | `python .ai/tools/run_tests.py --godot-only` | `completed=38/38 passed=38 failed=0 incomplete=0`；`ALL PASS` | **0** |
| 10 | `python .ai/tools/run_tests.py validator` | 10/10 PASS | **0** |
| 11 | `python .ai/tools/run_tests.py runtime` | 5/5 PASS | **0** |
| 12 | `python .ai/tools/run_tests.py feature_registry` | 4/4 PASS | **0** |
| 13 | `python .ai/tools/run_tests.py gameplay_planner` | 2/2 PASS | **0** |
| 14 | `python .ai/tools/run_tests.py asset_registry` | 11/11 PASS | **0** |
| 15 | `python .ai/tools/run_tests.py evaluation` | 2/2 PASS | **0** |
| 16 | `python .ai/tools/run_tests.py e2e` | 2/2 PASS；`ALL PASS` | **0** |
| 17 | `python .ai/tools/validator/validate.py` | **0 error / 17 warning**（与 1.46/1.47/1.48 基线同为既有缺图警告） | **0** |
| 18 | `python .ai/tools/validator/check_feature_metadata.py` | `Checked feature metadata: 12`，0 error / 0 warning | **0** |
| 19 | `python .ai/tools/scene_composer/behavior_protocol.py --write-manifest` | `PASS: manifest matches the protocol`（actions 8 / observations 11 / signals 7） | **0** |

### 8.4 时限处理（如实记录）

本工具的**单条命令上限是 600 s**，而本阶段的测试集合总量远超它。处理方式与结果：

1. 本阶段第一次尝试把 12 个测试放进一条命令，**在 600 s 处被工具终止**；
   其中前 10 个已产生完整日志，`test_slime_contact_arena.py` 的日志是 0 字节（被杀在启动阶段）。
   这条命令**没有被当作任何结果**：那 10 个测试后来全部单独重跑，
   `test_slime_contact_arena.py` 也单独重跑并 **77 PASS / exit 0**。
2. 之后的回归全部分段（§8.1–§8.3），每段一条命令、一个退出码；
   单段最长的是 `test_stun_behavior.py`（≈7 min，从日志时间戳 00:25→00:32 可核对）。
3. **并发纪律**：所有会创建/删除隔离工作区的测试（scene_composer 行为类、组合场景类、e2e）
   都**串行**执行，同一时间只有一条命令在跑——避免重演 Phase 1.47 记录过的
   「一边删 `.ai/tmp/behavior/workspace-*` 一边 `copytree`」问题。

### 8.5 本阶段出现过的 1 次失败（如实记录）

`test_condition_gate_behavior.py` 第一次运行 **exit 1**，唯一失败项：

```
FAIL: case6: the protocol stayed at v2 without new action capabilities
      | version=2 actions=8 observations=11 signals=7
```

原因不是协议被放宽，而是那条断言把信号数量**硬编码为 6**：本阶段为 stun 证据新增了
`stun.stunned`，总数变成 7。该断言的本意是「条件门控没有扩展动作能力」，因此修正为
`signals == 7` 并在注释里写明 Phase 1.49 的增量，**同时保留** `actions == 8` / `observations == 11`
的精确锁定——没有删除断言、没有改成 `>=`、也没有跳过。重跑 **53 PASS / exit 0**。

---

## 9. 已知限制与剩余高优先级缺口

1. **`health_bar` 仍无行为证据**（`UNIT_TESTED`）。阻塞原因是能力缺失而不是疏忽：协议没有能读
   `get_ratio()` 的观测。补齐需要新增一个只读观测 + 探针实现 + manifest 再生成 + 负向对照
   （「绑错 Health 仍画满血」）。
2. **4 个 `PARTIAL` 缺缺陷注入**：`health`（`heal_clamped` / `death` 完全没有注入）、
   `player_movement`（松键、速度）、`collect_pickup`、`heal_pickup`。
3. **`stun` 不在任何组合场景里**：`Scenes/SlimeEnemy.tscn` / `Player.tscn` 都不含 Stun。
   本阶段**没有**为了让证据更好看去改正式场景（那属于游戏设计变更）：
   如果要验证「敌人受击后硬直」，应先做设计决策。
4. **`stun` 未覆盖的边界**：`stun(duration)` 主动调用路径、`duration <= 0`、`health_path` 显式指定、
   组件在眩晕中被 `queue_free` 的 `_exit_tree` 恢复路径、宿主不是 CharacterBody2D 的退化行为。
   这些在 `test_stun.gd`（单元层）里有覆盖，但**不是**运行时行为证据。
5. **`survival_arena` 通行段仍不可重放**（1.46 记录的随机刷怪挡住玩家）。本阶段**没有**碰它，
   也没有把它算进稳定基线。
6. 组合场景 `slime_contact` 不覆盖玩家死亡与敌人受击（1.48 记录），本阶段未扩展。

---

## 10. 下一阶段建议

1. **`health_bar` 行为证据**（唯一剩下的 `UNIT_TESTED`）：扩一个只读观测 `health_bar.ratio`
   （`equals` / `tolerance`），契约需区分「绑对了 Health」与「未绑定/绑错仍满血」。
2. **给 `health` 与 `player_movement` 补缺陷注入**：`heal` 上限、`death` 只发一次、
   松键后仍滑动、速度常量被改。这两者是组合场景的地基，坏掉会让 `escape_room` / `slime_contact`
   以别的形态失败（更难定位）。
3. **`stun` 的产品决策**（可选）：是否让敌人具备硬直。若决定要，再给 `SlimeEnemy.tscn` 加 Stun
   并新增组合契约；不要为了证据好看而改场景。
4. **`survival_arena` 随机性**（长期）：要么给刷怪一个可注入的确定性入口（并证明它不改变正式行为），
   要么正式把通行段列为不可验收，二者都需要产品/设计层面的确认。
