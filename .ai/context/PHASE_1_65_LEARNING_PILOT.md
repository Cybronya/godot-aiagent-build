# Phase 1.65 — Learning Pilot

范围：**5 个 Behavior / 3 种类型**（A 状态转换 ×3、C 持久化 ×1、F 守卫 ×1），
由 Plan v1 的优先级产生（见 `selection.json`），不是手工挑"最容易的"。

## 1. 选择

| Behavior | 类型 | 选它的理由 |
| --- | --- | --- |
| `openable_door/open` | A | 唯一 Fully Covered，作为"知识应当与已知事实一致"的对照 |
| `i_frames/iframes_expire_and_damage_resumes` | A | 有 M11 真实 KILLED + 跨 Feature 依赖（Health） |
| `save_game/save_slot_persists_world_state` | C | 持久化 + 历史失败知识（M06）+ 依赖 |
| `trigger_switch/latch_once` | F | **没有任何真实 Run**：验证"知识不完整时系统不编造观察" |
| `health/damage` | A | Health 枢纽（17 节点 SCC），被大量 Behavior 依赖 |

## 2. 每个 Behavior 的链路结果

| Behavior | Contract | 入口（真实行号） | Run ID | Evidence Digest | Signature | Attestation | Evaluation | Mutation | 生效知识 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `openable_door/open` | `0550357495e5` | `openable_door.gd:32 set_open` | `11964-ad881e33-open` | `c07409026f94…` | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | M12 KILLED | 7 |
| `i_frames/iframes_expire_and_damage_resumes` | `d1cee84ef2fc` | `i_frames.gd:65 _on_health_changed`、`:75 _on_window_end` | `11964-79c99c5e-…` | 见 TEST_OBSERVATION | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | M11 KILLED | 8 |
| `save_game/save_slot_persists_world_state` | `d85d91c73250` | `save_game.gd:42 save_to_slot` | `11964-26505382-…` | 见 TEST_OBSERVATION | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | M06 KILLED | 10 |
| `trigger_switch/latch_once` | `4076f02be9eb` | `trigger_switch.gd:36 _on_body_entered` | **无** | — | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | M08 KILLED | 7 |
| `health/damage` | `562bbb4f6bd7` | `health.gd:28 take_damage` | `11984-263d1383-damage` | 见 TEST_OBSERVATION | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | M01 KILLED | 8 |

依赖引用（`pilot_result.json`）：

- `i_frames/…`：`RECEIVES_EVENT_FROM health/damage`、`REQUIRES_PRECONDITION health/post_death_guard`
- `save_game/…`：`PERSISTS_DATA_TO save_game/load_slot_restores_world_state`、`REQUIRES_PRECONDITION health/post_death_guard`
- `health/damage`：`EMITS_EVENT_TO health_bar/damage_updates_health_bar` 等
- `trigger_switch/latch_once`：`SHARES_STATE_WITH trigger_switch/toggle_on_second_contact`

## 3. 关键证明：第一轮知识改变第二轮计划

在**隔离知识根**（`.ai/tmp/p165/pilot_sandbox/`，可重复、不污染正式库）跑完整闭环：

```bash
python .ai/tools/learning/pilot.py \
  --matrix .ai/tmp/p164/batch1/matrix_after/coverage_matrix.json \
  --behaviors openable_door/open,i_frames/iframes_expire_and_damage_resumes,\
save_game/save_slot_persists_world_state,trigger_switch/latch_once,health/damage \
  --sandbox-dir .ai/tmp/p165/pilot_sandbox
```

| 指标 | Plan v1（无知识） | Plan v2（入库后） |
| --- | --- | --- |
| 任务总数 | **287** | **277** |
| `ANALYZE_SOURCE` | 65 | 60 |
| `UPDATE_KNOWLEDGE` | 60 | 55 |
| 因已完成排除 | 0 | **10** |
| 有任务的 Behavior | 60 | 57 |

逐 Behavior 变化（`plan_diff.json` → `changed_behaviors`，5/5 全部变化）：

| Behavior | 消失的任务 | 新增 | 知识驱动的任务 |
| --- | --- | --- | --- |
| `openable_door/open` | `ANALYZE_SOURCE`、`UPDATE_KNOWLEDGE` | — | — |
| `i_frames/iframes_expire_and_damage_resumes` | 同上 | — | — |
| `save_game/save_slot_persists_world_state` | 同上 | — | — |
| `trigger_switch/latch_once` | 同上 | — | **`DESIGN_TEST_SCENARIO`**（引用 3 条已审批知识：`k-baed5eb2b726195f`、`k-d8ac203c2891a339`、`k-f26d4a87ed04a064`） |
| `health/damage` | 同上 | — | — |

`driven_by_knowledge` 字段由 `planner._driven_by()` 读 Knowledge Store 生成，不是手写。

在**正式知识根**再跑一次（label P5）得到 `plan_before = plan_after = 277`：
因为知识已经在库里，第一轮就不再重建——这正好证明计划是由库状态驱动的（幂等）。

## 4. 候选测试场景（生成但未执行）

`scenarios.json`：**12** 条，全部来自源码守卫/持久化副作用，例如：

| Behavior | 类型 | 依据 | 提议 |
| --- | --- | --- | --- |
| `save_game/…` | `persistence_roundtrip` | `save_game.gd:185#file_access=LAST_SLOT_FILE` | 写入后在新实例读取，验证路径解析与数据一致 |
| `trigger_switch/latch_once` | `guard_boundary` | `trigger_switch.gd:39 if _triggered:` | 构造第二次接触（不推进帧），验证锁存守卫与信号计数 |
| `i_frames/…` | `guard_boundary` | `i_frames.gd:77 if _health != null and _active:` | 窗口到期前后各打一次，验证无敌门归还 |

每条都带 `executed: false` 与 `existing_run_id`。**Pilot 没有新跑 Godot**：
已执行的结论只来自 1.64 的真实 Run（可验签、可查 attestation），候选场景留待授权后执行。

## 5. 审批

`review_log.json`：**40** 条（reviewer=`phase_1_65_local_review`，scope=`LOCAL_REVIEW`）。
每次审批都经过 §门禁（见 `PHASE_1_65_KNOWLEDGE_REPORT.md` §3）。
本地审批 ≠ 人类审批者身份已验证，记录里写明。

## 6. 诚实缺口

| 缺口 | 事实 |
| --- | --- |
| `trigger_switch/latch_once` 无 Run | 1.64 没有给这个 Behavior 采集证据；Pilot 保留 `NO_RUNTIME_OBSERVATION` 任务，不造 Test Observation |
| 5 条 `SOURCE_ENTRY_AMBIGUOUS` | 未纳入 Pilot（`attack_emitter` 双定义、`condition_gate` 组合场景），对应 `ANALYZE_SOURCE` 任务 |
| 依赖知识重生成 | 解析器修正后 `DEPENDENCY_KNOWLEDGE` 内容变化 → 5 个冲突 → 显式解决（旧记录 `SUPERSEDED`） |
| 候选场景未执行 | 没有新增 Godot Run；不是"已验证"的测试场景 |

## 7. 产物

| 文件 | 内容 |
| --- | --- |
| `.ai/learning/pilot/selection.json` | 选择与理由 |
| `.ai/learning/pilot/scenarios.json` | 12 条候选场景（未执行） |
| `.ai/learning/pilot/review_log.json` | 40 条审批记录 + 未解决冲突（0） |
| `.ai/learning/pilot/plan_v1.json` / `plan_v2.json` | 两轮计划全文 |
| `.ai/learning/pilot/plan_diff.json` | 逐 Behavior 差异 |
| `.ai/learning/pilot/pilot_result.json` | 每个 Behavior 的 Run/Digest/Attestation/Evaluation/Knowledge ID |
| `.ai/tmp/p165/pilot_sandbox/**` | 隔离知识根的完整可重复演示（287→277） |
