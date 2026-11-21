# Phase 1.65 — Behavior Source Analysis

工具：`.ai/tools/learning/source_analysis.py`（+ `gd_parse.py`）。产物：
`.ai/learning/source_analysis/<feature>/<behavior>.json`（60 份，全部来自当前磁盘）。

## 1. 方法

1. 从**正式契约**取 action 方法名（`door.set_open` → `set_open`），排除 harness 动词
   （`physics.*`、`simulation.*`、`input.*`、`scene.*`、`node.*`、`time.*`、`debug.*`、`wait*`、`assert*`）。
2. 在 `Features/<feature>/*.gd`（排除 `test_*.gd` 与 `*fixture*.gd`）里精确匹配函数定义。
3. 精确匹配失败时做 **token 唯一别名解析**（`save_slot` → `save_to_slot`）；有多个候选就
   判为无法确定，不猜。
4. 契约方法全由 harness 驱动时，按优先级回退：契约 check 里的查询方法 → `_ready` 里的信号处理函数
   → `_physics_process`/`_process`（显式标 `trigger=frame_update`）。
5. 从入口沿同文件裸调用与同 Feature 静态类调用（`SaveData.read_from_file(`）扩展 **2 层**，
   收集状态读写、条件、事件、副作用、失败路径。

## 2. 结果

| 指标 | 值 |
| --- | --- |
| 分析 Behavior | **60**（动态支持集） |
| 找到确认入口 | **57 / 60** |
| `COMPLETE` | 5 |
| `PARTIAL`（有入口但有未解决问题） | 50 |
| `SOURCE_ENTRY_AMBIGUOUS` | 5 |
| `SOURCE_NOT_FOUND` | 0 |
| 实现文件全部存在 | 是（23 个 Feature 均有 `.gd`） |

`PARTIAL` 的主要原因是契约与源码命名/分工不一致（见 §4），不是分析失败。

## 3. 样例（真实行号）

`openable_door/open`（`COMPLETE`）

| 类别 | 观察 | 来源 |
| --- | --- | --- |
| 入口 | `set_open(value: bool)`，`trigger=contract_action` | `Features/openable_door/openable_door.gd:32` |
| 条件（幂等守卫） | `if _is_open == value:` | 同文件 `:33` |
| 失败路径 | 守卫块内 `guard_return` | `:34` |
| 事件 | `state_changed.emit(value)`（在 `_apply`） | `:44` |
| 副作用 | `_collision.set_deferred("disabled", value)` | `:41` |
| 状态 | `_is_open` 读/写，`_collision`/`_visual` 读 | `:40–43` |

`save_game/save_slot_persists_world_state`（`PARTIAL`）

- 契约 `savegame.save_slot` → 源码 **无同名函数**，按 token 唯一匹配解析为 `save_to_slot`（`:42`），
  并写入 `unresolved_questions`——这是**契约/源码命名不一致**，不是静默接受。
- 条件：`if not _is_valid_slot_name(slot_name): return false`（`:190`）、
  `if not data.write_to_file(slot_path): return false`。
- 持久化：`FileAccess.open(LAST_SLOT_FILE, FileAccess.WRITE)`（`:185`，`_record_last_slot`）。
- 静态类调用被展开：`SaveData.read_from_file(` → `save_data.gd:68`（`static func`，早期解析器不识别，已修）。

`i_frames/iframes_expire_and_damage_resumes`（`PARTIAL`）

- 入口：`_on_window_end`、`_on_health_changed`（都是 `_ready` 里真实 `connect` 的处理函数）。
- 条件：`if _health != null and _active:`（`:77`）——M11 注入的正是这之后的状态归还。
- 动态调用：`grant.call_deferred()`（`:72`）被记为未解决，因为静态分析无法确定它何时执行。

`trigger_switch/latch_once`（`PARTIAL`）

- 契约只有 `physics.overlap` + `advance_frames`（harness 驱动），入口按信号处理函数认定：
  `_on_body_entered`（`trigger_switch.gd:36`）。
- 条件里有锁存守卫 `if _triggered:`（`:39`）与 `match trigger_mode:`。

## 4. 未解析的 5 条（明确标记，不猜）

| Behavior | 原因 |
| --- | --- |
| `attack_emitter/raycast_hit_deals_damage` | `do_attack` 在 `attack_emitter.gd:39` 与 `raycast_attack_emitter.gd:24` 各定义一次（基类 + 子类覆写），静态无法判定运行时用哪个 |
| `attack_emitter/repeated_attack_can_kill` | 同上 |
| `condition_gate/all_conditions_fulfill` | 契约观测的是组合场景（`trigger.*` / `door.open`），本 Feature 源码没有对应方法 → 需要场景级/跨 Feature 分析 |
| `condition_gate/condition_fallback_withdraws_output` | 同上 |
| `condition_gate/partial_conditions_block_output` | 同上 |

这 5 条在 Planner 里对应 `SOURCE_ENTRY_AMBIGUOUS` 缺口（`ANALYZE_SOURCE` 任务、severity 2），
而不是被当成「已分析完成」。

## 5. 事实边界

- 所有输出 `static_only: true`。源码里有 `emit_signal` 只证明**源码包含该调用**，不证明运行时发出/被接收。
- 每条结论带 `file:line`；状态变量带声明位置与初值。
- 入口存在 ≠ 被 harness 调用；入口歧义时降低状态而不是补一个看似合理的入口。
- `_on_window_end` 的 `_active = false`（`i_frames.gd:78`，1 tab 缩进）被记录为普通赋值观察；
  本阶段不改产品源码（1.64 技术债 #2 仍未修，见审计 §7）。

## 6. 规模

| 项 | 值 |
| --- | --- |
| 解析的 `.gd` 文件 | 23 个 Feature 全部实现文件（不含测试/夹具） |
| 每个文件记录 | `path` + `sha256`（用于 SOURCE_OBSERVATION 的 digest 门禁） |
| 单次全量分析耗时 | 约 2–3 秒（纯文本解析，无 Godot 启动） |
