# Phase 1.65 — Behavior Dependency Report

工具：`.ai/tools/learning/dependencies.py`。产物：`.ai/learning/behavior_dependency_graph.json`。

## 1. 总量

| 指标 | 值 |
| --- | --- |
| 节点（正式 Behavior） | **60** |
| 依赖边 | **118** |
| 源码确认（`SOURCE_OBSERVED`） | **97** |
| 契约推导（`CONTRACT_DERIVED`） | **21** |
| 有出边的 Behavior | **41 / 60** |
| 强连通分量（SCC） | **2** |
| 未解析的契约依赖 | **1** |

## 2. 依赖类型分布

| 类型 | 数量 | 来源 |
| --- | --- | --- |
| `EMITS_EVENT_TO` | 21 | 源码：信号 emit + 对端 `connect` |
| `RECEIVES_EVENT_FROM` | 21 | 同上（与 emit 成对） |
| `REQUIRES_PRECONDITION` | 21 | 契约：precondition 引用别的 Feature |
| `SHARES_STATE_WITH` | 50 | 源码：同 Feature 内共享状态变量 |
| `WRITES_STATE_TO` | 3 | 源码：跨 Feature 属性写（`_health.set_invulnerable(...)`） |
| `PERSISTS_DATA_TO` | 1 | 源码：`FileAccess.open(..., WRITE)` |
| `RESTORES_DATA_FROM` | 1 | 源码：`FileAccess.open(..., READ)` |
| `CALLS` | 0 | 无仅调用不写状态的跨 Feature 调用被命中 |
| `USES_RESOURCE` | 0 | 本阶段未从源码中解析出跨 Feature 资源依赖 |

`CALLS = 0` 是**观察结果**，不是遗漏：本项目的跨组件耦合都伴随状态写入或信号，
`_health.set_invulnerable(false)` 被归为 `WRITES_STATE_TO` 而不是 `CALLS`。

## 3. 边的可信度纪律

- 每条边都有 `source_reference`（`file:line#call=…` / `#connect=…` / `template.yaml#behavior=…preconditions[...]`）。
- `evidence_kind=CONTRACT_REFERENCE` ⇔ `verification_status=CONTRACT_DERIVED`（测试 D6 强制）。
- 契约只有 `requires` 而源码没有可归属出边时，**不造边**，进 `unresolved_requirements`。
- 不按 Behavior 名称建边；`SHARES_STATE_WITH` 依据分析出的真实状态变量集合。

样例（真实边）：

```text
WRITES_STATE_TO      i_frames/iframes_block_damage_within_window → health/damage
                     Features/i_frames/i_frames.gd:77#call=_health.set_invulnerable   MEDIUM
RECEIVES_EVENT_FROM  i_frames/iframes_block_damage_within_window → health/damage
                     Features/i_frames/i_frames.gd:44#connect=_health.health_changed HIGH
PERSISTS_DATA_TO     save_game/save_slot_persists_world_state → save_game/load_slot_restores_world_state
                     analysis:save_game/save_slot_persists_world_state#file_write     HIGH
```

`WRITES_STATE_TO` 为 `MEDIUM` 是因为目标函数/状态的归属由「该 Feature 是否写状态」推断，
不是精确到变量级；`RECEIVES_EVENT_FROM` 为 `HIGH` 因为 connect 与 emit 两端都有行号。

## 4. 循环依赖（不判错）

| 分量 | 节点数 | 边数 | 分类 | 处置 |
| --- | --- | --- | --- | --- |
| Health 生态（health / health_bar / hit_flash / i_frames / stun 等） | **17** | 62 | `hub_component` | `note`：Health 是共享状态枢纽，多个组件都读写 `health_changed` 与 `invulnerable` |
| `save_game` 存取对 | 2 | 3 | `persistence_pair` | `expected`：写者↔读者本来就成对 |

分类规则：纯事件边 → `event_loop`（expected）；含持久化边 → `persistence_pair`（expected）；
节点 > 6 的 SCC → `hub_component`（note）；其余 → `state_cycle`（review）。
**没有任何循环被当作错误。**

Health 枢纽不是缺陷，但它意味着改 `Health.take_damage` 的语义会同时影响 17 个 Behavior——
这正是 Planner 把 `health/post_death_guard` 排在最高优先级（18.5）的原因之一。

## 5. 未解析的契约依赖

| Feature | 声明 | 原因 |
| --- | --- | --- |
| `heal_pickup` | `requires: health_state` | 契约声明依赖 Health 状态，但源码里没有对 Health 的直接调用/信号/属性访问（可能通过节点查找或组合层驱动）；静态分析不猜 |

对应任务：`ANALYZE_DEPENDENCIES`（severity 2）。

## 6. 查询接口

```bash
python .ai/tools/learning/dependencies.py --build
python .ai/tools/learning/dependencies.py --query downstream --behavior i_frames/iframes_block_damage_within_window
python .ai/tools/learning/dependencies.py --query upstream   --behavior health/damage
python .ai/tools/learning/dependencies.py --query events
python .ai/tools/learning/dependencies.py --query shared_state
python .ai/tools/learning/dependencies.py --query persistence
```

## 7. 限制

- 跨 Feature 的静态类调用只解析同 Feature 内的 `class_name`（跨 Feature 的静态调用会漏）。
- 动态调用（`call_deferred`、`Callable`、`call(`）不解析，记入该 Behavior 的未解决问题。
- `USES_RESOURCE` 只在 Feature 内 `load/preload` 时记录；当前无跨 Feature 资源边，因此计数为 0。
- 依赖是**静态图**：`condition_gate` 这类组合场景的真实依赖要靠场景级分析，当前只能给契约边。
