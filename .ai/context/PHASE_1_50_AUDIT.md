# Phase 1.50 审计报告 — HealthBar Runtime Evidence & Read-Only Observation

日期：2026-10-26
环境：Windows，Godot 4.7 stable headless，CPython 3.12
仓库：`F:\Godot_v4.7-stable\game`

本阶段为 **最后一个没有行为证据的正式 Feature `health_bar`** 建立真实运行时契约：

- 新增 1 个**只读**观测 `health_bar.ratio`（读组件公开的 `get_ratio()`，无副作用）
- 新增 5 条行为契约、1 个证据场景、1 个测试（65 条断言）
- 3 类可观测的显示缺陷注入，全部被检出并逐字节恢复
- 动作能力表**未变**（仍是 8 个动作），协议版本未变（v2）

---

## 1. 修改前后的 Git 状态

### 1.1 开始前（基线）

```
HEAD            1c30f94  feat: unified run identity, e2e serial lock and resource ownership hardening (Phases 1.26-1.34)
branch          master
staged          0 项
modified        37 项（Phase 1.26–1.49 的既有未提交修改）
untracked       45 项（含 1.49 新增的 FEATURE_BEHAVIOR_COVERAGE.md / PHASE_1_49_AUDIT.md / test_stun_behavior.py / StunFixture.tscn）
```

### 1.2 本阶段新增 / 修改（只有这些）

| 文件 | 动作 | 内容 |
| --- | --- | --- |
| `.ai/context/behavior_protocol.yaml` | 修改 | `observations:` 新增 `health_bar.ratio`（1 条，只读）；文件头补 Phase 1.49/1.50 变更说明 |
| `.ai/tools/scene_composer/probes/feature_behavior_probe.gd` | 修改 | `OBSERVATION_IMPLEMENTATIONS` 加 1 项 + `_observe_health_bar_ratio()`（6 行，只调 getter） |
| `.ai/tools/scene_composer/probes/behavior_manifest.json` | 重新生成 | `actions: 8, observations: 12, signals: 7`；`PASS: manifest matches the protocol` |
| `.ai/tools/scene_composer/probes/composite_behavior_probe.gd` | 修改 | 同步实现同一个观测（组合探针也必须实现共享协议的全部读能力，否则能力门禁拒绝执行，见 §4.1） |
| `.ai/tools/scene_composer/probes/composite_behavior_manifest.json` | 重新生成 | 组合协议未变（3 场景 / 2..8 段 / 1200 帧），`PASS: manifest matches the protocol` |
| `Features/health_bar/HealthBarFixture.tscn` | **新增** | 证据场景（`Host/Health(10)` + `Host/Bar` 已绑定 + `Orphan` 未绑定） |
| `Features/health_bar/template.yaml` | 修改 | 追加 `behavior:` 5 条 + 数值/时序推导注释 |
| `.ai/tools/scene_composer/tests/test_health_bar_behavior.py` | **新增** | 65 条断言：正向 5 条 + 3 类注入 + 观测缺口 + 重放 + 非法契约 + CLI |
| `.ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | 修改 | 观测计数 11 → 12；行为总数 25 → 30；Case 8 追加 health_bar 5 条 |
| `.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | 修改 | 行为总数 25 → 30；“声明行为” 列表加 health_bar；改为“凡有 template 的 Feature 都必须声明行为” |
| `.ai/tools/scene_composer/tests/test_condition_gate_behavior.py` | 修改 | 陈旧断言 `observations == 11` → 12（原因与 1.49 同类：硬编码能力计数） |
| `.ai/tools/run_tests.py` | 修改 | scene_composer 段 29 → 30 + 注释；Python 总数 59 → 60、全量 97 → 98（实测更正，见 §8.4） |
| `.ai/tools/scene_composer/tests/test_stun_behavior.py` | 修改 | 断言消息里的 `≪`（GBK 不可编码）改为 ASCII `far below 88 px`；数值与判定不变。该字符让这条测试在 GBK 控制台下以退出码 1 结束（见 §8.4） |
| `.ai/context/CONTRACT_INDEX.yaml` | 修改 | `checks` 加 `health_bar.ratio`；`test_health_bar` 登记 |
| `.ai/context/FEATURE_BEHAVIOR_COVERAGE.md` | 修改 | health_bar → `VERIFIED`；总数 25 → 30；统计 8/4/0；缺口与建议重排 |
| `.ai/context/PHASE_1_50_AUDIT.md` | **新增** | 本报告 |

### 1.3 结束时

```
staged          0 项（仍未 stage 任何文件）
modified        38 项（既有修改保留，另加 health_bar/template.yaml）
untracked       48 项（45 项既有 + HealthBarFixture.tscn + test_health_bar_behavior.py + 本报告）
                -> 本阶段结束时再测一次为 **50 项**，多出的 2 项**不是本阶段产生的**：
                  `.ai/skills/foundation/godot-gdscript/code_library/`（mtime 10-27 02:35）
                  `.ai/skills/foundation/godot-gdscript/tools/`（mtime 10-27 02:35）
                  它们是共享检出上其它进程（另一个 agent / skill 采集任务）在本轮回归期间写入的。
                  按「不碰不属于自己的改动」：**未读取、未修改、未删除、未 stage**，仅登记。
```

未执行 `git reset --hard` / `git checkout` / `git clean` / `git add` / `git commit` / `git push`。

---

## 2. `health_bar` 的实际实现与设计语义（审计结论，不是假设）

读完 `Features/health_bar/health_bar.gd`（55 行）后的**事实**：

| 项目 | 事实 |
| --- | --- |
| 节点类型 | `class_name HealthBar extends Node2D`（**不是** `ProgressBar`，不是 `Control`，没有任何子节点：`HealthBar.tscn` = 单节点 + 脚本） |
| 绑定 | `@export var health_path: NodePath`；`_ready()` 里 `get_node_or_null(health_path) as Health` |
| 更新路径 | `Health.health_changed` → `_on_health_changed()` → `queue_redraw()`；`Health.died` → `queue_redraw()` |
| 比例语义 | `get_ratio()` = `current / max_health`，`_health == null` 或 `max_health <= 0` 时返回 `0.0` |
| 绘制 | `_draw()`：先用 `back_color` 画满 `bar_size`，再在 `ratio > 0` 时用 `fill_color` 画 `bar_size.x * ratio` 宽的前景 |
| 异步性 | **无**：没有 Tween、没有计时器、没有动画、没有延迟队列；`_draw()` 里只有两次 `draw_rect()` |
| 可写状态 | **无**：没有任何 setter / 内部状态写入接口；`get_ratio()` 是唯一的公开读入口 |

**关键推论（决定了本阶段的方案）**：

1. 血条没有「可调用一下改变它」的入口，所以行为证据只能是「Health 真的变 → 血条真的跟着变」。
2. 血条不缓存显示值——`_draw()` 每次现算 `get_ratio()`。因此**读 `get_ratio()` 等于读它下一次绘制会用的值**，
   但也意味着「重绘时机」本身不可观测（见 §6.4）。
3. `_draw()` 里的 `bar_size.x * ratio` 是唯一的变换，所以比例与填充宽度是一一对应的，
   读比例能精确判定「画出来多宽」，但读不到像素。

---

## 3. 新增 observation 的权限边界

新增 `.ai/context/behavior_protocol.yaml#observations.health_bar.ratio`：

```yaml
health_bar.ratio:
  implementation: observe_health_bar_ratio
  implemented: true
  target: node
  result: {type: float}
  summary: "HealthBar.get_ratio() —— 实际用于绘制填充宽度的比例（0.0 ~ 1.0；未绑定 Health 时为 0.0）"
  params: {equals: float, tolerance: float[0,1], min: float, max: float}
```

探针实现（全部 6 行）：

```gdscript
func _observe_health_bar_ratio(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("get_ratio"):
		return {"available": false}
	return {"available": true, "observed": float(node.call("get_ratio"))}
```

边界逐条对照题目要求：

| 要求 | 落实情况 |
| --- | --- |
| 只读取被授权目标节点的实际显示状态 | 只调 `get_ratio()`；它就是 `_draw()` 计算填充宽度用的值 |
| 明确支持的节点类型 | 声明在 summary 与注释里：带 `get_ratio() -> float` 的组件（本项目唯一实现 = `HealthBar`）。探针用 `has_method` 判定，**不**依赖全局类名（否则最小工程副本里会解析失败） |
| 目标解析规则 | 与其它观测一致：`target` 为场景内路径（`Host/Bar` / `Orphan` / `.`） |
| 不存在的目标 | `{"available": false}` → `INSUFFICIENT / check_unavailable` |
| 错误节点类型 | 同上（指向 `Host/Health` 这种没有 getter 的节点 → 证据不足，不猜值）。测试 Case 3 显式验证 |
| 不可读取状态 | 同上，没有第三种分支——不存在“读到半成品”的路径 |
| 不允许修改属性 / 调用任意方法 / 触发信号 | 实现里没有 setter、没有 `emit`、没有 `queue_redraw`、没有 `call` 任意方法名；只调一个固定 getter |
| 不允许用夹具直接设血条值 | 契约里**没有**任何 `state.set_property`（测试对 5 条行为逐一断言 `fixture` 标志为空） |
| 在协议登记 + 同步 manifest | 已登记；`--write-manifest` 输出 `observations: 12` 并 `PASS` |
| 保留漂移检测 | `test_behavior_protocol_consistency.py` Case 2 `check_manifest == []`；Case 6 的 CLI 收尾再验一次 |

**没有新增动作能力**：`actions` 仍是 8 个（`test_behavior_protocol_consistency.py` Case 1 精确锁定 `(8, 12, 7, 1)`）。

---

## 4. 协议与 manifest 变化

| 项目 | 变化 | 校验 |
| --- | --- | --- |
| `protocol_version` | 未变（2） | Case 1 |
| actions | 未变（8） | Case 1 精确元组 |
| observations | **11 → 12**（+`health_bar.ratio`） | Case 1 精确元组 + 实现唯一性计数 |
| signals | 未变（7） | Case 1 |
| properties | 未变（1） | Case 1 |
| 组合场景协议 | 未变 | `test_composite_behavior_evidence.py` |
| manifest | 重新生成，无漂移 | `--write-manifest` → `PASS`；Case 2 `check_manifest == []` |
| 探针（单个 Feature） | +1 映射 +1 函数，其余未动 | 能力门禁（`probe_capabilities`）通过 |
| 探针（组合场景） | +1 映射 +1 函数（同语义） | 能力门禁（`check_capabilities`）通过 |

### 4.1 为什么组合探针也必须同步（一次真实的门禁报错）

第一次跑 `test_composite_behavior_evidence.py` 时 **exit 1 / 98 PASS + 2 FAIL**，唯一失败项：

```
FAIL: case1: probe capabilities match the protocols
  | ["observations declared+allowed but not implemented by the composite probe:
     ['observe_health_bar_ratio']"]
```

原因：`composite_behavior_protocol.check_capabilities()` 要求**每个探针**实现共享协议声明的全部
动作/观测（这才能保证“组合契约能用的能力”与“单 Feature 契约能用的能力”是同一套词汇）。
我只改了 Feature 探针，门禁就拒绝执行——这正是防静默降级的设计，**没有绕开**：
修法是在组合探针里加上同语义的 6 行实现（只调 `get_ratio()`），然后重跑通过。

---

## 5. 正向契约、真实观测值与重放

命令：

```bash
python .ai/tools/scene_composer/feature_behavior_evidence.py --feature health_bar --replay 2
#   pass=5 mismatch=0 insufficient=0 invalid=0 not_declared=0   exit 0
python .ai/tools/scene_composer/tests/test_health_bar_behavior.py
#   65 PASS / 0 FAIL   exit 0
```

| # | behavior | 前置 | 动作（全部真实） | 实测值 | `waited_frames` | replay |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `initial_health_bar_ratio` | Health=10 | `advance_frames(1)` | ratio=**1.0**，Health=**10** | 0 | 2 次一致 PASS |
| 2 | `damage_updates_health_bar` | Health=10 | `take_damage(4)` + 1 帧 | ratio=**0.6**，Health=**6**，`health_changed`=**1**（`last_args=[6,4]`） | 0 | 2 次一致 PASS |
| 3 | `healing_updates_health_bar` | Health=10 | `take_damage(4)` + `heal(2)` + 1 帧 | ratio=**0.8**，Health=**8**，`health_changed`=**2**（`last_args=[8,2]`） | 0 | 2 次一致 PASS |
| 4 | `death_empties_health_bar` | Health=10 | `take_damage(10)` + 1 帧 | ratio=**0.0**，Health=**0**，`is_dead`=true | 0 | 2 次一致 PASS |
| 5 | `unbound_bar_reports_no_fill` | Health=10 | `advance_frames(1)` | `Orphan` ratio=**0.0**，`Bar` ratio=**1.0**，Health=**10** | 0 | 2 次一致 PASS |

要点：

- **每条都同时观测 Health 与血条**：`health.current` 证明输入真的变了，`health_bar.ratio` 证明显示真的变了，
  `signal` + `last_args` 证明比例变化对应一次真实事件，而不是某个夹具写的值。
- **`waited_frames == 0`**：所有后置条件在动作后的第一帧即成立；同步语义由此得到证明。
  另有一条断言用 `window_frames: 1` 复验「1 帧窗口就够」，显式排除“靠长窗口等待”的可能。
- **数值可精确推导**：max=10，伤害 4 → 0.6，治疗 2 → 0.8，致死 → 0.0。
  断言容差 5e-4 只吸收浮点表示误差（0.6 与 1.0/0.5 相差 0.1 以上），不是靠容差掩盖差异。
- **反“自证”设计**：契约 5 里同一场景中 `Orphan`（未绑定）读 0.0、`Bar`（已绑定）读 1.0。
  如果观测偷偷读 Health（而不是血条），两者都会是 1.0，这条会失败。
- **只读性**：测试另有 `read_only` 探针，在一条契约里连读三次比例，得到 `[0.6, 0.6, 0.6]` 且
  `health_changed` 仍为 1 —— 读观测不会触发更新、不会自我改变。

---

## 6. 负向对照（隔离副本，逐字节恢复）

### 6.1 适用范围说明（必须先说清楚）

本组件的 `get_ratio()` 是**现算**的（不缓存显示值），而 Godot 没有提供“某个 CanvasItem 是否请求过重绘”
的只读查询。于是：

- 「`health_changed` 连接被断开」这个缺陷**在当前实现下不可观测**：比例仍会读出正确值，只是屏幕像素会
  stale（`_draw()` 不再被调用）。任何只读观测都看不到这一点。
- 题目允许「如果某种缺陷与当前实现无关，说明原因并选择等价且有区分能力的缺陷注入」，
  因此第 3 类注入采用**等价的显示缺陷**：血条的 `health_path` 绑定被拆除 —— 这是“血条不再跟随 Health”
  的严重版本，可观测且能证明观测确实读的是血条自己的状态。
- 若要验证“重绘时机”，必须先让组件暴露显示缓存或重绘计数（组件/架构决策），本阶段**不做**，
  已登记为已知限制（§10）。

### 6.2 注入与判定

| # | 注入（隔离副本） | 期望 | 实际 | 相邻契约 |
| --- | --- | --- | --- | --- |
| 2a | `get_ratio()` 忘掉除 `max_health`（`return float(current)`） | 比例超出 0–1 → `MISMATCH` | ✅ `initial` `MISMATCH/state_mismatch`，ratio=**10.0**；`damage` 也 `MISMATCH`，ratio=**6.0** | `death` 仍 PASS（0.0 两种算法相同）；`unbound` 失败但 `Orphan` 仍读 0.0 |
| 2b | `get_ratio()` 恒返回 `1.0`（血条永远满） | 受伤/治疗/死亡都错 → `MISMATCH` | ✅ `damage` `MISMATCH`（1.0≠0.6）、`healing` `MISMATCH`、`death` `MISMATCH` | `initial` 仍 PASS（满血恰好等于 stub 值）—— 说明对照有分辨力 |
| 2c | 场景里删掉 `Bar.health_path`（绑定失效） | 已绑定血条变 0.0 → `MISMATCH` | ✅ `damage` `MISMATCH`，ratio=**0.0** 而 Health=**6**；`initial`/`healing` 同 | `death` 仍 PASS（0.0 是期望值）；`unbound` 失败但 `Orphan` 仍 0.0 |
| 3a | 观测目标改成 `Host/MissingBar` | `INSUFFICIENT/check_unavailable` | ✅ | — |
| 3b | 观测目标改成 `Host/Health`（没有 `get_ratio`，类型错误） | `INSUFFICIENT`，不猜值 | ✅ `check_unavailable` | — |
| 3c | 前置条件不满足（要求 ratio=0.5，实际 1.0） | `INSUFFICIENT/precondition_unmet`，动作不执行 | ✅ | — |
| 4 | 第 2 次重放注入不同观测值 | `INSUFFICIENT/replay_inconsistent` | ✅ 两次运行都保留在证据里（第 2 次 `observed=0.61`） | — |
| 5a | `window_frames: 0` | `INVALID`，不启动 Godot | ✅ `window_frames must be` | — |
| 5b | `tolerance` 但没有 `equals` | `INVALID` | ✅ `tolerance requires equals` | — |
| 5c | `min: 0.9, max: 0.1` | `INVALID` | ✅ `min must be <= …max` | — |
| 5d | 未知参数 `count` | `INVALID` | ✅ 报出未知参数名 | — |
| 5e | `equals: "full"`（字符串） | `INVALID` | ✅ 类型不符 | — |
| 5f | 场景路径越界 `../health_bar/../../escape.tscn` | `INVALID` | ✅ `relative path inside` | — |
| 6 | 仓库副本里把 `get_ratio()` 改成恒 1.0，跑 CLI | 退出码 1，且失败项是 `damage_updates_health_bar` | ✅ `exit 1`，stdout 出现该 behavior 名 + `MISMATCH` | 副本 SHA 一致；仓库 3 个文件哈希未变；manifest 未漂移 |

### 6.3 失败原因确实对应注入的缺陷

每条注入除了状态码，还断言了具体表现：2a 断言 ratio 变成 10.0/6.0（而不是“随便失败”）；
2b 断言受伤后仍是 1.0；2c 断言 Health 已降到 6 而比例是 0.0；3b 断言 `check_unavailable`
而不是 `state_mismatch`（证明它不是“值不对”，而是“读不到”）。相邻契约的 PASS 也逐项保留。

### 6.4 第一次运行失败的 6 条断言（如实记录，并说明修正）

第一版契约跑出 **6 FAIL / exit 1**，原因分两类：

1. **契约设计缺陷（真实问题）**：`damage_updates_health_bar` 的前置条件里写了 `health_bar.ratio == 1.0`。
   于是注入 2a/2c 时，契约在**动作之前**就判 `INSUFFICIENT/precondition_unmet`——
   把“显示坏了”误报成“证据不足”，这违反题目「实际显示与契约不一致 → MISMATCH」的分类要求。
   **修正**：前置条件只保留“跑得起来所需的状态”（`health.current == 10`），初始比例交给
   `initial_health_bar_ratio` 单独验证。修正后同一注入稳定得到 `MISMATCH`。
   这不是放宽断言：初始比例仍然被断言，只是被断言的**契约**更准确地对应它的语义。
2. **我的测试断言写错**：2a/2c 里我写了“unbound 契约仍然 PASS”——但 `unbound` 同时断言已绑定血条的 1.0，
   绑定坏/公式坏时它本来就应该失败。改成断言“`Orphan` 仍读 0.0（guard 未受影响）”这一**真实事实**；
   另外 `min > max` 的错误文案是 `must be <= …max`，我原来的 needle 是 `min must be <= max`，已改。

修完后 **65 PASS / 0 FAIL / exit 0**（连跑两次结果一致）。

### 6.5 隔离与恢复验证

- 注入全部在 `BehaviorWorkspace` 的 `<temp>/project/Features/health_bar/*` 副本上做；
- 每次注入后立即写回原始字节，并断言 `sha256` 等于注入前基线；
- 测试结束断言**仓库** `health_bar.gd` / `HealthBarFixture.tscn` / `template.yaml` 哈希未变；
- 测试结束断言 `behavior_manifest.json` 仍与协议一致；
- 临时目录 `.ai/tmp/health_bar_behavior_*` 在 `finally` 里 `rmtree`，本次运行后无残留。

---

## 7. 覆盖矩阵的更新依据

`FEATURE_BEHAVIOR_COVERAGE.md` 中 `health_bar` 由 `UNIT_TESTED` 改为 `VERIFIED`，依据是**本文件里可以逐条核对的事实**：

- 有正式行为契约（5 条，`template.yaml#behavior`）；
- 全部在真实 Godot 运行时执行（`action_executed=true`，每条动作 `executed=true`，无夹具动作）；
- 2 次重放一致（`replay_consistent=true`）；
- **有能拒绝错误实现的负向对照**（3 类可观测缺陷 + 1 条 CLI 非零退出）；
- 观察不到证据时是 `INSUFFICIENT`（3 类实测）。

矩阵里同时保留了两条**降低结论强度**的说明：像素与重绘时机不可观测；`health_changed` 断连不可检出。

矩阵总数同步更新为 **30 条 behavior**，统计 **VERIFIED 8 / PARTIAL 4 / UNIT_TESTED 0**。

---

## 8. 回归测试（逐段命令、退出码）

### 8.1 为什么要分段，以及如何保证「分段 = 全量」

单命令有工具时限（10 分钟），而本仓库的段本身就超过它：`scene_composer` 段实测 **15.9 分钟**，
`e2e` 段内部含 4 次「完整生成链路 + 真实 Godot」沙箱捕获，实测 **9.1 分钟**。

因此按 `run_tests.py` 文档规定的 9 个具名段执行，**全部串行**（同一时刻只有一个段在跑，
不并发读写任何隔离工作目录，符合题目对隔离工作区的要求）。

分段本身不改变结论，只要证明「并集完整」。本节把这件事量化：

- 发现集合：Godot **38**（`Features/*/test_*.gd` + `Tests/test_*.gd`）、Python **60**（`.ai/tools/**/tests/test_*.py`）；
- 8 个具名 Python 段的选择数之和 = **66**（30+11+4+2+5+2+10+2），去重后 = **60**，
  **没有任何一个 Python 测试文件落在 8 段之外**（差额 6 = 同时命中两段的重叠文件，
  如 `scene_composer/tests/test_*_validator*.py` 同时属于 `scene_composer` 与 `validator`）；
- 因此 9 段串行覆盖 = 全量 98 个测试，与「一条全量命令」的覆盖面相同。
  **但必须如实说明：本次没有跑过「一条全量单命令」**，结论建立在「并集完整」的证明之上。

### 8.2 逐段结果（2026-10-27，Windows / Godot 4.7 headless / CPython 3.12）

| # | 段 | 命令 | 选择测试数 | 结果 | 退出码 | 用时 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Godot 全部 | `python .ai/tools/run_tests.py --godot-only` | 38（38/38 PASS） | ALL PASS | **0** | 01:58:11→02:00:45 ≈ 2.6 min |
| 2 | scene_composer | `python .ai/tools/run_tests.py scene_composer` | 30（30/30 PASS） | ALL PASS | **0** | 01:37:27→01:53:18 ≈ 15.9 min |
| 2b | scene_composer（**在全部修改完成后的最终树上重跑**） | `python .ai/tools/run_tests.py scene_composer` | 30（30/30 PASS） | ALL PASS | **0** | 02:22:38→02:38:38 ≈ 16.0 min |
| 3 | asset_registry | `python .ai/tools/run_tests.py asset_registry` | 11（11/11 PASS） | ALL PASS | **0** | →02:01:11 ≈ 0.4 min |
| 4 | feature_registry | `python .ai/tools/run_tests.py feature_registry` | 4（4/4 PASS） | ALL PASS | **0** | →02:01:28 ≈ 0.3 min |
| 5 | gameplay_planner | `python .ai/tools/run_tests.py gameplay_planner` | 2（2/2 PASS） | ALL PASS | **0** | →02:01:46 ≈ 0.3 min |
| 6 | runtime | `python .ai/tools/run_tests.py runtime` | 5（5/5 PASS） | ALL PASS | **0** | →02:02:57 ≈ 1.2 min |
| 7 | evaluation | `python .ai/tools/run_tests.py evaluation` | 2（2/2 PASS） | ALL PASS | **0** | →02:03:11 ≈ 0.2 min |
| 8 | validator | `python .ai/tools/run_tests.py validator` | 10（10/10 PASS） | ALL PASS | **0** | →02:03:45 ≈ 0.6 min |
| 9 | e2e | `python .ai/tools/run_tests.py e2e` | 2（2/2 PASS） | ALL PASS | **0** | →02:12:48 ≈ 9.1 min |

每段末尾的机器可读汇总（本机实测，逐字）：

```
completed=N/N passed=N failed=0 incomplete=0 unavailable=0 not_executed=0
[run_tests] ALL PASS
```

**没有任何一段出现 INCOMPLETE / unavailable / not_executed / TIMEOUT**——这一点逐段核对过，
不是只看汇总（`run_tests.py` 只有这四种计数全为 0 时才输出 `ALL PASS`）。

第 2 段（scene_composer）是本次改动的主战场，30 个测试中与 Phase 1.40–1.50 能力直接相关的包括：

| 测试 | Phase | 本次结果 |
| --- | --- | --- |
| `test_artifact_evidence_validator.py` | 1.8.x | PASS |
| `test_behavior_protocol_consistency.py` | 1.41–1.50 | PASS（含观测 12 / 行为 30 的精确元组锁定） |
| `test_behavior_time_driven.py` | 1.42 | PASS |
| `test_chase_movement_behavior.py` | 1.43 | PASS |
| `test_condition_gate_behavior.py` | 1.44 | PASS |
| `test_composite_behavior_evidence.py` | 1.46 | PASS（EscapeRoom / SurvivalArena 稳定基线） |
| `test_contact_damage_behavior.py` | 1.47 | PASS |
| `test_slime_contact_arena.py` | 1.48 | PASS（SlimeContactArena 端到端链） |
| `test_stun_behavior.py` | 1.49 | PASS（见 §8.4 第 1 条） |
| `test_feature_instance_evidence.py` | 1.45 | PASS |
| `test_instance_evidence_reconciliation.py` | 1.39 | PASS |
| `test_runtime_instance_evidence.py` | 1.39 | PASS |
| `test_health_bar_behavior.py` | **1.50（本次）** | PASS |

`EscapeRoom` / `SlimeContactArena` / `SurvivalArena` 的既有稳定基线**未回归**：
前者在 `test_composite_behavior_evidence.py`（第 2 段）与 `Tests/test_escape_room.gd`（第 1 段）、
后者在 `Scenes/SlimeContactArena.tscn` 的端到端测试与 `Tests/test_survival_arena.gd` 中各自 PASS。
**没有为了本次扩展而放宽任何一个旧断言**：`test_behavior_protocol_consistency.py` 的精确计数是**收紧**
（11→12、25→30），`test_condition_gate_behavior.py` 里那条硬编码 `observations == 11` 是**跟随协议更新**
（不改会让它失败；它断言的是协议的真实状态，不是被放宽）。

### 8.3 原始证据位置

| 内容 | 路径 |
| --- | --- |
| 逐段退出码 + 尾部输出 | `.ai/tmp/p150reg/RESULTS.txt` |
| 分段脚本 | `.ai/tmp/p150reg/run.sh` |
| 各段完整输出 | `.ai/tmp/p150reg/<段名>.log`（godot_only / asset_registry / feature_registry / gameplay_planner / runtime / evaluation / validator / e2e） |
| 第 2 段完整输出 | `.ai/tmp/seg_scene_composer.log` |
| 第 2 段最终重跑输出 | `.ai/tmp/p150reg/scene_composer_final.log`（30/30 PASS / `EXIT=0`） |
| 后续小段重跑 | `.ai/tmp/p150reg/reeval.log`（evaluation 2/2 PASS）、`.ai/tmp/p150reg/help.log`（`--help` exit 0） |

这些路径都在 `.gitignore` 的 `.ai/tmp/` 之下（`git check-ignore` 已确认），因此不会污染工作区状态。

### 8.4 回归期间暴露的 3 个真实问题（已修，并重跑验证）

#### 8.4.1 `≪` 让一条**全部断言都通过**的测试以退出码 1 结束（真实缺陷，已修）

第 2 段第一次运行：`test_stun_behavior.py` **exit 1**，输出是
`UnicodeEncodeError: 'gbk' codec can't encode character '\u226a'`（U+226A = `≪`，不是断言失败）。

机理（已用同形状的 subprocess 实验独立复现，不是推测）：

- `run_tests.py::run_python_test()` 用 `subprocess.run(..., capture_output=True)` ⇒ 子进程 stdout 是**管道**；
- 管道下子进程的 stdout 编码取系统 ANSI 代码页（本机 = **GBK**，Python 3.12 也是这样）；
- `≪` 不在 GBK 里 ⇒ `print()` 直接抛异常 ⇒ 退出码 1；
- 父进程按 `FAILURE_MARKERS = ("FAIL", "FAILED", "Traceback", "SCRIPT ERROR")` 里的 `Traceback`
  把这条判为 **FAIL** —— 也就是说，**协议本身没有错，是打印让它变成红的**。

复现实验（同一 subprocess 形状）：

```
--- no PYTHONIOENCODING      exit=1   UnicodeEncodeError: 'gbk' codec can't encode character '\u226a'
--- PYTHONIOENCODING=utf-8   exit=0
```

修法与验证：把断言消息 `(... (≪88 px)` 改成 ASCII `(... (far below 88 px)`，**数值阈值与判定逻辑一字未改**。
重跑 scene_composer 段 ⇒ **30/30 PASS / exit 0**（本次 §8.2 第 2 段即修复后的结果，
且该次运行**没有** `PYTHONIOENCODING`，是在真实 GBK 环境下通过的）。

影响面审计（避免「只修一处、别处复发」）：对 `.ai/tools/**`、`Features/**`、`Tests/**` 全量扫描
「GBK 不可编码字符」，命中 **101 处**（`⇒ ↔ ⇄ ► − ⊆ ⊄ ⇔ 〜` 等）。逐处定位后：
**除这一处外全部位于注释 / docstring / README**，没有任何一处出现在会被打印的断言消息中——
证据是同一台 GBK 机器上其余 29 个 scene_composer 测试与本段其余 7 段全部 PASS。
唯一残留的 `≪`（`.ai/tools/scene_composer/tests/test_stun_behavior.py:331`）在**注释**里，不会被打印。

> 顺带记录、**本次不修**的既有脆弱点：`run_tests.py` 用 `text=True, encoding="utf-8"` 解码子进程输出，
> 而子进程按 GBK 编码输出中文 ⇒ 只在 FAIL 路径的 tail 上出现替换字符（`U+FFFD`）。
> 这是失败诊断信息的可读性问题，与本次契约、与协议都无关；本次 9 段全 PASS，
> 因此 `seg_scene_composer.log` 里实测 `U+FFFD` 计数为 **0**。要改也应当独立评审（影响所有段的日志解码）。

#### 8.4.2 `run_tests.py` docstring 的 Python 总数过期（已修）

写的是「当前 59；全量 = Godot 38 + Python 59 = 97」，实测发现集合是 **60**（全量 **98**）——
截至 Phase 1.48/1.49/1.50 新增了 3 个 Python 测试文件（`test_slime_contact_arena.py`、
`test_stun_behavior.py`、`test_health_bar_behavior.py`），总数没有跟着动。

已更正为 60 / 98，并把「段计数之和 66 > 总数 60」的**差额来源（6 个重叠文件）**写进文档——
原文只含糊地说「各段计数之和不等于 Python 总数」，现在这句话有了可核对的数字。

#### 8.4.3 `--help` 在本机控制台直接崩溃（同一类字符问题，已修）

在核对 §8.4.2 时顺手验证 `--help`，发现它自己也是坏的（**Phase 1.50 之前就如此，不是本次引入**）：
argparse 会把模块 docstring 当作 description 打印，而该 docstring 里有 2 个 `⇒`（U+21D2，GBK 不可编码）：

```
UnicodeEncodeError: 'gbk' codec can't encode character '\u21d2' in position 819: illegal multibyte sequence
```

这与 §8.4.1 是**同一个根因**（在 GBK 控制台上打印非 GBK 字符），因此一并修掉：2 处 `⇒` 改为 ASCII 的 `->`，
**文字信息与含义不变**。验证：

```
python .ai/tools/run_tests.py --help   -> exit 0，输出里 Traceback 计数 = 0
python .ai/tools/run_tests.py evaluation -> 2/2 PASS, exit 0
```

这里是**只改文档字符、不改任何判定逻辑**：修订只涉及 docstring 文本与 argparse 的 help 输出，
不参与测试选择、执行、分类或退出码计算。为了不拿旧结果当新结果，随后又做了两次重跑：

| 重跑 | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 本阶段主战场 | `python .ai/tools/run_tests.py scene_composer` | **30/30 PASS** | **0** |
| 运行器可用性 | `python .ai/tools/run_tests.py evaluation` | 2/2 PASS | 0 |

即：§8.2 第 2 项那个 30 个测试的段（也是唯一包含 Phase 1.50 新测试的段）已在**全部修改完成后的最终树**上
重新跑过一次并全绿；其余 7 个 Python 段与 Godot 段跑在前面，但它们与本次修订无因果交叉
（本次修订不进任何被它们导入或执行的代码路径）。这一点如实列出，而不是含糊地宣称「全部在最终树上验证」。

### 8.5 时限限制与未达成的检查

- **未跑「一条全量单命令」**：`scene_composer` 单段就 15.9 分钟 > 工具 10 分钟时限，全量命令必然超时。
  覆盖面由 §8.1 的并集证明补上，但这仍是一条**限制**，如实列出。
- 每段都是一条独立命令，`e2e` 段 9.1 分钟、`scene_composer` 段 15.9 分钟都远低于其内部预算
  （单测试超时 300s；e2e 覆盖项 1800s），无 TIMEOUT。
- 串行执行：段之间没有并发，不存在「同一时间窗并发删除和读取同一组隔离工作目录」。

### 8.6 隔离副本与临时文件处理

- 本次回归**自身不做任何缺陷注入**（注入在 §6 的 `BehaviorWorkspace` 临时副本中完成）。
- `BehaviorWorkspace` 的清理路径：`finally: workspace.close()`；
  `features_dir` 之外的另一处在 `finally: shutil.rmtree(_tempdir, ignore_errors=True)`。
- **可清理性实测**：`health_bar_behavior`（本次新证据场景）运行后**无残留** `health_bar_behavior_*` 目录，
  与 `slime_contact_arena` / `contact_damage_behavior` 等一致。
- **发现一条空目录残留**：`.ai/tmp/stun_behavior_uly6c9v5/`（0 字节，mtime 2026-10-26 02:39）。
  它来自 2026-10-26 那次**被中断/停止**的 stun 测试运行（进程被杀 ⇒ `finally` 没跑完），
  **不是本次运行产生的**，本次 `test_stun_behavior.py` PASS 后无新增残留。
  按题目「禁止清理归属不明的文件」的要求，**未删除**，仅在此登记（它为空目录，无数据可恢复）。
- 本次新建的 `.ai/tmp/p150reg/` 与 `.ai/tmp/seg_scene_composer.log` **保留为证据**（均被 gitignore）。

### 8.7 结论

9 段串行、9 个退出码全部为 **0**、并集覆盖全量 98 个测试、无 INCOMPLETE / unavailable / not_executed / TIMEOUT。
Phase 1.40–1.49 的既有能力（行为协议一致性、组合场景验收、实例证据、Validator、E2E、Feature Registry、
EscapeRoom / SlimeContactArena / SurvivalArena 稳定基线）**无回归**。
期间暴露并修复了 3 个真实问题（GBK 断言字符让通过的测试变红、`--help` 在 GBK 控制台崩溃、文档计数过期），
三者都**只改证据/文档与可打印字符串，不改任何断言阈值、判定逻辑或退出码语义**。

---

## 9. 未覆盖行为与后续建议

1. **像素级显示与重绘时机**：`health_changed` 断连（stale 像素）不可检出。要补这一类证据，
   必须让 `HealthBar` 暴露显示缓存或重绘计数——这是组件设计变更，应单独评审，不应由测试悄悄推动。
2. **`health_bar` 没有实例证据（L2/L3）**：`template.yaml` 仍未声明 `instance:`。
   `HealthBar.tscn` 是单节点（Node2D + 脚本，无子节点），加声明收益有限；6 个其它 Feature 有声明。
3. **显示配置未覆盖**：`bar_size` / `back_color` / `fill_color` 的几何与配色没有任何证据
   （比例正确不代表画的位置/宽度对；`_draw` 里的 `-bar_size.x/2` 偏移只能靠像素验证）。
4. **`health_bar` 未进入组合场景**：`Scenes/Enemy.tscn` 里有 `HealthBar` 实例，但没有组合契约观察它。
5. **4 个 `PARTIAL`**（`collect_pickup`、`heal_pickup`、`health`、`player_movement`）仍缺本 Feature 级缺陷注入。

建议下一阶段（按证据缺口排序，而不是按代码量）：

1. 给 `health` / `player_movement` 补缺陷注入（组合场景的地基，坏了会以别的形态失败，难定位）。
2. 若要“显示时机”类证据，先做组件设计决策（显示缓存 / 重绘计数），再谈契约。
3. `health_bar` 的 `bar_size` 几何可以用加法证明（fill 宽度 = `bar_size.x * ratio`），
   前提是观测能返回“填充宽度”而不只是比例——这需要第二个只读观测，价值低于第 1 项。

---

## 10. 结论

- `health_bar` 已从 `UNIT_TESTED` 升级为 `VERIFIED`，12 个正式 Feature **全部**拥有正式行为契约，
  其中 8 个具备“能拒绝错误实现”的注入证据。
- 唯一的协议增量是 1 个只读观测（`health_bar.ratio`）；动作能力、协议版本、组合场景白名单、
  `denied_actions` 全部未变。
- 3 类显示缺陷被稳定检出，且每类都验证了相邻契约仍然 PASS；无法观测的缺陷（重绘时机）已明确记录，
  没有用“放宽断言”或“报 PASS”掩盖。
- 首次运行失败 6 条断言的原因已逐条记录，其中 1 条是**契约设计缺陷**（前置条件把 MISMATCH 变成
  INSUFFICIENT），已修正。
- 未提交、未推送；既有 37 个文件的未提交修改完整保留。
