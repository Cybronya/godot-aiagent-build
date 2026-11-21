# Phase 1.65 — Knowledge Report

存储：`.ai/knowledge/behavior_learning/`（`candidates/` `records/` `conflicts/`）。
实现：`.ai/tools/learning/knowledge_v2.py`；Schema 见 `PHASE_1_65_ARCHITECTURE.md` §4。
1.64 的 `.ai/knowledge/behavior_verification/**` **未被改写**（只读引用其失败模式）。

## 1. 总量

| 指标 | 值 |
| --- | --- |
| 记录总数 | **45** |
| `APPROVED`（当前生效） | **40** |
| `SUPERSEDED`（被新版本取代，保留） | **5** |
| `PENDING_REVIEW` | 0 |
| `REVOKED` / `ARCHIVED` | 0 |
| 覆盖的 Behavior | **5 / 60** |
| 冲突（累计 / 未解决） | **5 / 0** |
| 来源分布 | CONTRACT_FACT 5、SOURCE_OBSERVATION 17、DEPENDENCY_KNOWLEDGE 8、MUTATION_OBSERVATION 5、TEST_OBSERVATION 4、RUNTIME_OBSERVATION 4、FAILURE_KNOWLEDGE 2 |
| 置信度 | VERIFIED 5、HIGH 27、MEDIUM 13、LOW 0、UNKNOWN 0 |

> 45 条里 5 条是同一 `DEPENDENCY_KNOWLEDGE` 槽位的旧版本（Pilot 期间依赖图因解析器修正而变化），
> 旧记录保留为 `SUPERSEDED`，没有被删除，也没有被"自动选最新"覆盖。

## 2. 逐 Behavior

| Behavior | 生效记录 | 类型覆盖 |
| --- | --- | --- |
| `openable_door/open` | 7 | CONTRACT、SOURCE×3、TEST、RUNTIME、MUTATION |
| `i_frames/iframes_expire_and_damage_resumes` | 8 | CONTRACT、SOURCE×3、DEPENDENCY、TEST、RUNTIME、MUTATION |
| `save_game/save_slot_persists_world_state` | 10 | CONTRACT、SOURCE×4、DEPENDENCY、TEST、RUNTIME、MUTATION、**FAILURE** |
| `trigger_switch/latch_once` | 7 | CONTRACT、SOURCE×3、DEPENDENCY、**FAILURE**、MUTATION（无 TEST/RUNTIME：无证据） |
| `health/damage` | 8 | CONTRACT、SOURCE×3、DEPENDENCY、TEST、RUNTIME、MUTATION |

`trigger_switch/latch_once` 没有 `TEST_OBSERVATION` / `RUNTIME_OBSERVATION`，因为它没有 1.64 的真实
Run——这是**如实缺失**，不是被省略。

## 3. 来源门禁的实际拦截

| 门禁 | 实现 | 已验证行为 |
| --- | --- | --- |
| CONTRACT_FACT 必须指向 `Features/` | `validate()` | 是 |
| SOURCE_OBSERVATION 文件必须存在且 digest 匹配 | 重算文件 SHA256 | 是（测试 K4/K5：旧 digest 与缺失文件都被拒） |
| MUTATION_OBSERVATION 只接受 `MUTANT_KILLED` | 校验 `mutation_verdict` | 是（测试 K6：`INVALID_MUTANT` 被拒） |
| INFERENCE 必须有 derivations 且不能 VERIFIED | 校验 + 查存在性 | 是（测试 K17/K18） |
| 审批需要 reviewer + reason | `approve()` | 是（测试 K7） |
| 未解决冲突阻断审批 | `approve()` 查 OPEN 冲突 | 是（测试 K13） |

## 4. 冲突

| conflict_id | 状态 | 双方 | 处置 |
| --- | --- | --- | --- |
| `c-486a7813881e724e` | RESOLVED | `k-588f52d86c959c94` / `k-6b1ceb718f070ab0` | 依赖知识重新生成（解析器新增 `static func` 识别）；新记录审批，旧记录 `SUPERSEDED` |
| `c-a02eea72b1b3c8fb` | RESOLVED | `k-1e8425297fac3f2e` / `k-12ca60365bb2e0b6` | 同上 |
| `c-a851277c0b940fd5` | RESOLVED | `k-a7025994fddf25b1` / `k-507b298744ce8643` | 同上 |
| `c-ac909e3e8204eb44` | RESOLVED | `k-22373956fabeedd6` / `k-8bdd846e2e415612` | 同上 |
| `c-ba1dd94adabf6ce6` | RESOLVED | `k-fe7ab351e9ff420a` / `k-d8ac203c2891a339` | 同上 |

解决是**显式动作**（`pilot.py --resolve-conflicts`，带理由与 reviewer），不是自动选边。
双方记录都在磁盘上；`RESOLVED` 冲突也保留，不删除。

## 5. 失败知识

| Behavior | 失败 | 根因 | 状态 |
| --- | --- | --- | --- |
| `trigger_switch/latch_once` | M04（锁存守卫删除后 control 与 mutant 观测相同） | 契约第二次 `physics.overlap` 不产生第二次 `body_entered`，守卫在真实执行里走不到 | RESOLVED（契约补 `advance_frames(6)`，1.63 复测 KILLED） |
| `save_game/save_slot_persists_world_state` | M06（删除 `_record_last_slot` 调用后仍读到 `behavior_save`） | `user://` 跨 run 残留，harness 复用同一 application name | RESOLVED（per-run `use_custom_user_dir`，1.63 复测 KILLED） |

两条 `FAILURE_KNOWLEDGE` 都引用原始报告路径，`confidence=MEDIUM`（历史记录，当前未重跑）。

## 6. 过期与撤销

- `staleness()` 比对 `contract_version` 与 `implementation_digest`（与 extract 同口径：所有实现文件 digest 拼接）。
- 当前 40 条生效记录**没有** `KNOWLEDGE_STALE` 缺口（`learning_plan.json` 中没有该 gap 的实例）。
- `revoke()` / `archive()` 已实现并有测试（K15/K16：撤销后不能再次审批，文件保留）。
  本阶段实际未撤销任何记录。

## 7. 与覆盖矩阵的关系

知识数量 **不等于** 覆盖率：`Fully Covered` 仍由 1.64 的八维定义决定（当前 1/60）。
本阶段没有用「知识条数」去抬高覆盖数字，也没有把 `VERIFIED` 置信度写成「Behavior 已验证」。
`knowledge/behavior_learning` 不在八维分母里。
