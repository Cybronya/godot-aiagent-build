# Phase 1.41 审计报告 — Behavior Protocol Unification & Drift Prevention

日期：2026-10-22
分支：`master`　HEAD：`1c30f94`（本阶段未提交、未推送）

---

## 1. Git 初始与最终状态

- 初始：`master` / `1c30f94`；工作区已包含 Phase 1.36–1.40 的未提交成果
  （1.38/1.39/1.40 的模块、探针、测试、模板 `behavior:` / `runtime:` 声明等）。
- 最终：仍为 `master` / `1c30f94`，**未 commit、未 push**；未执行 reset / clean / 批量恢复。
- 本阶段没有修改任何 `Features/**/*.tscn`、trace 基线或 e2e 基线；也没有改写 6 个 behavior
  的 `template.yaml`（迁移范围为零，见 §8）。

---

## 2. 原有双份注册表：具体差异与风险

Phase 1.40 的能力定义分散在两处：

| 维度 | Python (`feature_behavior_evidence.py`) | GDScript (`feature_behavior_probe.gd`) | 风险 |
| --- | --- | --- | --- |
| 动作 | `ACTION_SPECS`：4 项，`params` 键集合 + `bool`/`positive` 标记 | `ACTIONS`：4 项，`method`/`param`/`kind` | 新增动作只改一侧 → Python 放行、探针拒绝（或反之） |
| 参数约束 | `amount 1..100`、`health_max 1..10000`、`damage 0..100` | 仅检查 `amount > 0`、`group` 非空；范围不完整 | 同一输入两端结论不同 |
| 观测 | `STATE_CHECKS` 4 项 + `SIGNAL_ENTRIES` 4 项（各带说明字符串） | `CHECKS` 6 项 + `SIGNALS` 4 项（映射真实信号名） | 观测/信号白名单双份维护 |
| 默认值 | `node.freed.equals` 默认 true；signal `count` 默认 1 | `node.freed` 默认 true；`count` 取契约值 | 默认值靠约定，无单一来源 |
| 目标类型 | 仅语法校验（路径 / `@actor`） | `physics.overlap` 运行时要求 `Node2D` | 目标类型约束未声明 |
| 结果字段 | 消费 `checks/actions/preconditions/...` | 生产同名 JSON | 字段靠人工同步 |
| 版本 / 漂移 | 无 | 无 | 任何单侧修改都不会被发现 |

结论：两份定义**没有自动一致性证据**，且参数约束范围已经不一致（探针缺 min/max）。
本阶段因此不是「整理代码」，而是把能力声明上移为协议并加门禁。

---

## 3. 最终协议格式与设计理由

权威文件：`.ai/context/behavior_protocol.yaml`（与仓库其余 `.ai/context/*.yaml` 一致）。

```yaml
protocol_version: 1
status: current
targets: {kinds: {node, node2d}}
actions:
  door.set_open:
    implementation: door_set_open     # 探针实现 ID（不是可调用方法名）
    implemented: true
    target: node
    params: {value: {type: bool, required: true}}
observations:
  node.freed:
    implementation: observe_node_freed
    implemented: true
    target: node
    result: {type: bool}
    params: {equals: {type: bool, default: true}}
signals:
  door.state_changed: {signal: state_changed, args: [bool]}
```

设计理由：

- **YAML**：仓库现有契约全部是 YAML（`scene_composer_schema.yaml`、`CONTRACT_INDEX.yaml`），
  无需引入新格式；人类可审阅、可 diff。
- **生成 JSON manifest 给 Godot**：Godot 无内置 YAML 解析，直接引入第三方解析器会扩大攻击面。
  由 Python 生成 `probes/behavior_manifest.json`（只读运行时清单），探针只读它；
  manifest 是生成物而非第二份人写定义，且门禁逐字校验。
- **`implemented` 显式**：协议允许声明尚未实现的能力，但必须写 `false`；
  Python 与探针在使用时都拒绝（`declared but not implemented`），避免「声明即支持」的错觉。
- **能力与 Feature 预期分离**：协议不含任何 Feature ID 或期望值；具体断言仍在
  `template.yaml#behavior`。
- **子集约束**：参数 schema 只支持 `bool/int/string/scalar_list/signal_ref` 与
  `required/min/max/non_empty/default`。够当前 4 动作 / 6 观测使用，不预设计未用特性。

---

## 4. 协议文件与实现映射

| 产物 | 角色 |
| --- | --- |
| `.ai/context/behavior_protocol.yaml` | 唯一权威（人写）：动作/观测/信号/参数/目标类型 |
| `.ai/tools/scene_composer/behavior_protocol.py` | 严格加载、结构校验、契约校验、manifest 生成/比对、探针能力门禁 |
| `.ai/tools/scene_composer/probes/behavior_manifest.json` | 生成物；探针运行时读取 |
| `.ai/tools/scene_composer/probes/feature_behavior_probe.gd` | 仅保留 `实现 ID → 内部方法` 映射（`ACTION_IMPLEMENTATIONS` / `OBSERVATION_IMPLEMENTATIONS`）；能力声明全部来自 manifest |
| `.ai/tools/scene_composer/feature_behavior_evidence.py` | 不再持有动作/观测清单；用协议校验契约并做最终判定 |

映射示例：

| 协议项 | implementation | 探针内部方法 | 真实入口 |
| --- | --- | --- | --- |
| `door.set_open` | `door_set_open` | `_impl_door_set_open` | `OpenableDoor.set_open` |
| `health.take_damage` | `health_take_damage` | `_impl_health_take_damage` | `Health.take_damage` |
| `health.heal` | `health_heal` | `_impl_health_heal` | `Health.heal` |
| `physics.overlap` | `physics_overlap` | `_impl_physics_overlap` | 真实物理帧 `body_entered` |
| `door.is_open` | `observe_door_is_open` | `_observe_door_is_open` | `OpenableDoor.is_open` |
| `signal` | `observe_signal` | `_observe_signal` | 协议信号白名单 |

---

## 5. Python 与 Godot 的职责边界

- **Python（权威）**：加载/校验协议 → 校验 Feature behavior 契约 → 编排动作序列与重放 →
  判定 `PASS/MISMATCH/INSUFFICIENT/INVALID/NOT_DECLARED` → 生成最终证据。
- **GDScript（观测者）**：读取 manifest → 再次校验契约（防直接调用绕过 Python）→
  执行动作 / 物理接触 → 逐帧观测 → 输出原始 JSON，**不输出最终 PASS**。
- 两端对同一契约做同构校验（必填、类型、范围、未知键、未知 ID、目标语法、信号引用）；
  任一侧发现非法输入都返回 `INVALID / contract_invalid`，不执行动作。

---

## 6. 一致性门禁的检查规则

`behavior_protocol.py --check-manifest --capabilities` 与
`tests/test_behavior_protocol_consistency.py`：

1. 协议可严格加载：版本 == 1、`status: current`、结构/字段/类型合法。
2. **重复 key**：自定义 YAML Loader 检测重复 action / observation 定义并拒绝。
3. **未知类型 / 目标 / 字段 / 非法引用**：`float` 参数类型、未声明的 target kind、
   未知顶层键、`signal_ref` 无信号可引用 → `ProtocolError`。
4. **manifest 逐字一致**：`protocol.manifest_text()` 与仓库 manifest 完全相同；
   任何参数约束/能力改动未重新生成 → `protocol_drift`。
5. **探针能力 == 协议声明**：运行探针 `--capabilities`（真实实现映射，不解析源码），
   比较 `required_implementations`；缺失 → `declared but not implemented by probe`，
   多出 → `implemented by probe but not declared in protocol`。
6. **版本一致**：探针 `PROTOCOL_VERSION`、manifest、协议三方必须相等。
7. **Fail closed**：协议缺失/损坏/版本不兼容 → 验证器 `INVALID / protocol_invalid`，
   CLI 退出 1；manifest 漂移 → `INVALID / protocol_drift`，不会以旧清单继续运行。

---

## 7. 当前支持与未支持的能力

已支持（协议 + 探针实现均已声明）：

- 动作 4：`door.set_open`、`health.take_damage`、`health.heal`、`physics.overlap`
- 观测 6：`door.is_open`、`health.current`、`health.is_dead`、`pickup.is_collected`、
  `node.freed`、`signal`
- 信号 4：`door.state_changed`、`pickup.collected`、`health.health_changed`、`health.died`

未支持 / 边界：

- 无「等待 N 帧」「设置属性」「移动实体」等动作；帧推进由观测窗口隐式完成。
- 无字符串枚举、正则或嵌套 schema；参数类型子集固定。
- `deprecated` / `replaced_by` 字段已实现校验，但当前没有弃用项。
- 未接入 `moving_platform` / `player_movement` / `trigger_switch`（仍 `NOT_DECLARED`）。

---

## 8. 现有 6 个 behavior 的迁移与前后对比

**迁移范围：零。** 6 个 `template.yaml#behavior` 未改动，协议按 1.40 的实际能力原样声明；
仅代码端的「能力定义」从两份人工清单收敛为协议 + manifest。

前后对比（最终代码实测）：

| Feature / behavior | 1.40 结果 | 1.41 结果 | 观测值 | 重放 |
| --- | --- | --- | --- | --- |
| collect_pickup / collect_on_contact | PASS | PASS | `[true, 1]` | 2/2 一致 |
| heal_pickup / heal_damaged_target | PASS | PASS | `[4, true]` | 2/2 一致 |
| health / damage | PASS | PASS | `[1, 1]` | 2/2 一致 |
| health / heal_clamped | PASS | PASS | `[5, 2]` | 2/2 一致 |
| health / death | PASS | PASS | `[0, true, 1]` | 2/2 一致 |
| openable_door / open | PASS | PASS | `[true, 1]` | 2/2 一致 |

协议解析结果：`actions=4 / observations=6 / signals=4`，全部 `implemented: true`；
`required_implementations` = 4 动作实现 + 6 观测实现，与探针 `--capabilities` 完全一致。
`test_feature_behavior_evidence.py` 的 102 项断言继续通过（含非法动作/参数、前置不满足、
动作未执行、采集失败、重放不一致、CLI 退出码、真实副本负向对照）。

---

## 9. 协议漂移负向对照与恢复校验

### 9.1 移除探针实现映射（真实 Godot 能力门禁）

在隔离项目副本中删除探针的 `"door_set_open": "_impl_door_set_open"` 映射：

- `probe_capabilities()` 返回的实现集合缺少 `door_set_open`；
- `check_capabilities()` 报 `actions declared but not implemented by probe: ['door_set_open']`；
- 恢复探针字节后，重新运行能力门禁 → 通过；`sha256` 与操作前一致。

### 9.2 篡改 manifest 版本

副本 manifest 的 `protocol_version` 改为 99，直接以合法契约运行探针：

- 探针拒绝：`INVALID / protocol_invalid`，detail 指出版本不兼容；
- 恢复 manifest 字节后，同一契约 → `PASS`；`sha256` 一致。

### 9.3 协议参数改动未重新生成 manifest

复制协议并把 `health.take_damage.amount.max` 从 100 改为 99：

- `check_manifest()` 报 `actions` 漂移；
- 验证器在启动 Godot 前返回 `INVALID / protocol_drift`。

### 9.4 行为缺陷对照

隔离副本把 `set_open` 改为 no-op：

- `MISMATCH / state_mismatch`；窗口耗满；动作确实执行；
- 恢复脚本后 `sha256` 与仓库文件一致。

所有对照均断言恢复后的哈希，且仓库黄金 Feature / 探针 / manifest 未被改写。

---

## 10. 全量回归矩阵（最终代码）

| 检查 | 结果 |
| --- | --- |
| 协议一致性测试（11 组） | 69/69 PASS，exit 0 |
| 协议 manifest / 能力门禁 CLI | PASS（manifest 一致 + 4/6 实现匹配） |
| Phase 1.40 行为测试 | 102/102 PASS |
| 行为 CLI `--all`（每行为 2 次重放） | 6/6 PASS，全部一致 |
| Phase 1.38 静态实例证据 | 53 项 PASS |
| Phase 1.39 运行时实例证据 | 67 项 PASS |
| Scene Composer 段 | 22/22 PASS |
| Validator 段 | 10/10 PASS（含于全量） |
| Godot headless | 38/38 PASS |
| 全量 `run_tests.py` | 90/90 PASS，exit 0 |
| 静态 Validator | 0 error / 17 warning（既有资产清单缺失），exit 0 |

17 条 warning 与 1.40 相同，均为 `assets/**.png` 不在当前检出中，与本阶段无关。

---

## 11. 未解决问题与后续建议

1. **manifest 生成仍是显式步骤**：`--write-manifest` 不会被自动调用；门禁能检测漂移并拒绝运行，
   但需要人（或 CI 步骤）执行生成。可考虑在协议一致性测试失败信息中直接给出修复命令。
2. **校验逻辑仍是两份代码**：协议是唯一定义，但 Python 与 GDScript 各自实现参数校验；
   一致性测试覆盖代表性子集，不能证明所有边界完全等价。后续可把校验结果矩阵做成
   表驱动用例（同一输入 → 两端期望错误类别）。
3. **实现映射只校验能力 ID**：门禁保证「协议声明的实现 ID 在探针中存在」，不校验方法体
   行为是否正确；行为正确性仍由 6 个 behavior 与负向对照证明。
4. **协议子集有限**：无 enum/oneOf/正则/嵌套对象；扩展时需同步两端校验器并补测试。
5. **`implemented: false` 仍要求填写 implementation**：作为审计锚点，但该 ID 可能不存在于
   探针；这是刻意的（未实现不等于有实现），使用即 INVALID。
6. **未覆盖 Feature 扩展**：仍只有 4 个 Feature / 6 个 behavior；帧推进类动作尚未纳入协议。
7. **环境**：Windows + Godot 4.7 stable headless 实测；Godot 端读取 JSON manifest，
   不依赖 YAML 解析器。

建议：下一步把「等待 N 帧」与「设置导出属性（受白名单约束）」纳入协议，
让 `moving_platform` / `trigger_switch` 等帧驱动 Feature 也能获得行为证据；
同时把协议一致性与行为门禁串成一条显式验收命令（不改变静态 Validator 默认行为）。

---

## 12. 结论

- 动作 / 观测能力已收敛为单一权威协议 `.ai/context/behavior_protocol.yaml`；
  探针通过生成的 manifest 读取同一份能力，不再维护第二份完整定义。
- 自动门禁覆盖：协议严格性、manifest 逐字一致、探针实现映射、版本一致性、fail-closed。
- 6 个 behavior 的语义、观测值、双次重放与负向对照全部保持不变；
  真实漂移对照（移除实现映射 / 篡改 manifest 版本 / 未重新生成 manifest）均稳定失败并可恢复。
- 全量回归 90/90、Godot 38/38、静态 Validator 0 error；
  限制与后续建议已在 §11 如实记录。
