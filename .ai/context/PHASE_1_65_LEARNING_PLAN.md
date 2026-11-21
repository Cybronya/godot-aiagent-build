# Phase 1.65 — Learning Plan

产物：`.ai/learning/learning_plan.json` + `.ai/learning/learning_plan.md`（生成命令见 §6）。

## 1. 输入（全部来自磁盘）

| 输入 | 值 |
| --- | --- |
| 正式支持集 | 23 Feature / **60 Behavior**（动态读取） |
| 覆盖矩阵 | `.ai/tmp/p164/batch1/matrix_after/coverage_matrix.json`（**必须显式给出**） |
| 源码分析 | 60 份（`COMPLETE 5 / PARTIAL 50 / AMBIGUOUS 5`） |
| 依赖图 | 118 条边（97 源码 / 21 契约），2 个 SCC |
| 知识库 | 45 条（40 APPROVED / 5 SUPERSEDED），5 个 Behavior |
| 历史失败知识 | 2 条（M04、M06） |
| 环境 | Godot 可用（`env_paths` 探测通过）→ 无 `ENVIRONMENT_BLOCKED` |

## 2. 优先级公式

```text
priority = 3*severity + risk/2 + upstream_impact + failure_bonus - cost
```

| 项 | 含义 | 来源 |
| --- | --- | --- |
| `severity` | 缺口严重度 1..3 | `GAPS` 表（如 `SOURCE_NOT_FOUND` 3、`KNOWLEDGE_INCOMPLETE` 1） |
| `risk` | 1.64 审计的行为风险分（0–24） | `phase_1_64_behavior_taxonomy.json`，公式未改 |
| `upstream_impact` | 被多少 Behavior 依赖（上限 6） | 依赖图入边 |
| `failure_bonus` | 有 FAILURE_KNOWLEDGE 时 +2 | 知识库 |
| `cost` | 1=读码/建图、2=设计场景或冲突、4=真实执行 | `GAPS` 表 |

每个任务都写出**逐项算式**，例如：

```text
health/post_death_guard ANALYZE_DEPENDENCIES
severity 2×3 + risk 15/2 + upstream 6 + failure 0 - cost 1 = 18.5
：契约声明前置/依赖，但没有解析出的依赖边
```

成本是**减项**：只挑最便宜的活不会爬到榜首；上游影响与风险会把它压下去。

## 3. 任务总量

| 指标 | 值 |
| --- | --- |
| 任务数 | **277** |
| 覆盖 Behavior | **57 / 60** |
| 阻塞 | **0**（Godot 可用；冲突已解决） |
| 因已完成排除 | **10** |

| 任务类型 | 数量 |
| --- | --- |
| `ANALYZE_SOURCE` | 60 |
| `UPDATE_KNOWLEDGE` | 55 |
| `DESIGN_MUTATION` | 50 |
| `EXECUTE_BEHAVIOR` | 48 |
| `DESIGN_TEST_SCENARIO` | 48 |
| `ANALYZE_DEPENDENCIES` | 16 |

> 为什么没有 `EXECUTE_MUTATION` / `VALIDATE_EVIDENCE` / `INVESTIGATE_FAILURE` / `RESOLVE_KNOWLEDGE_CONFLICT`：
> 这些任务只在前置条件成立时才生成（例如先有 `DESIGN_MUTATION` 产出、或存在未解决冲突）。
> 当前没有未解决冲突，`EXECUTE_MUTATION` 不是缺口而是"上一步还没产出"——不生成空任务。

## 4. 缺口分布

| 缺口 | 数量 | 说明 |
| --- | --- | --- |
| `CONTRACT_UNDERSTOOD_ONLY` | 55 | 只有契约，没有已审批的源码观察 |
| `KNOWLEDGE_INCOMPLETE` | 55 | 没有已审批知识 |
| `NO_MUTATION_KNOWLEDGE` | 50 | 没有 KILLED 的 mutation 知识（10 条已有） |
| `NO_RUNTIME_OBSERVATION` | 48 | 无 evidence/attestation（12 条已有） |
| `NO_TEST_SCENARIO` | 48 | 无 VERIFIED_PASS 评估 |
| `DEPENDENCY_UNKNOWN` | 16 | 契约有前置但无解析出的依赖边 |
| `SOURCE_ENTRY_AMBIGUOUS` | 5 | 入口多重定义 / 组合场景 |
| `KNOWLEDGE_CONFLICT` / `KNOWLEDGE_STALE` | 0 | 冲突已解决；无过期记录 |
| `ENVIRONMENT_BLOCKED` | 0 | Godot 可用 |

## 5. 排在最前的任务

| 任务 | 行为 | 优先级 | 理由 |
| --- | --- | --- | --- |
| `ANALYZE_DEPENDENCIES` | `health/post_death_guard` | **18.5** | 风险最高（15），被 6 个 Behavior 依赖，且有契约前置但无依赖边 |
| `ANALYZE_SOURCE` | `health/post_death_guard` | **18.5** | 同上，且只有契约知识 |
| `ANALYZE_SOURCE` | `save_game/load_slot_restores_world_state` | **17.5** | 风险 23（持久化权重高）+ 共享状态 |
| `UPDATE_KNOWLEDGE` | `health/post_death_guard` | 15.5 | 知识缺口 1，但风险与上游影响把它抬起来 |
| `ANALYZE_SOURCE` | `stun/hit_stuns_and_freezes_host` | 15.5 | 风险高，属于 Health 枢纽的消费方 |

**不重复安排**：5 个 Pilot Behavior 的 `ANALYZE_SOURCE` 与 `DESIGN_MUTATION`（已有对应知识）被显式
列进 `excluded`（10 条），理由写在计划里，而不是悄悄消失。

## 6. 生成与复算

```bash
python .ai/tools/learning/planner.py \
  --matrix .ai/tmp/p164/batch1/matrix_after/coverage_matrix.json \
  --label phase_1_65 \
  --out .ai/learning/learning_plan.json
```

`--matrix` 缺失时**直接失败**：Planner 不接受默认扫描（1.64 审计 P2：默认 `EVAL_REPORT_DIR`
会把别的批次的评估报告算进来）。extract 侧还会对每条评估报告做 bundle digest 归属校验。

## 7. 计划如何被知识改变

第二轮计划（Pilot 后）与第一轮的差异见 `PHASE_1_65_LEARNING_PILOT.md` §3：

- 5 个 Pilot Behavior 的 `ANALYZE_SOURCE` / `UPDATE_KNOWLEDGE` 消失（被 `excluded` 记录）；
- 任务总数 287 → 277；
- `trigger_switch/latch_once` 的 `DESIGN_TEST_SCENARIO` 带上 `driven_by_knowledge`
  （引用已审批的守卫/入口知识 id）。

这是**代码读 Knowledge Store 得出的**，不是手工改计划文件。
