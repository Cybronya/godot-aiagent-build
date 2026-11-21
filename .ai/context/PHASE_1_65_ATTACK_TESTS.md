# Phase 1.65 — 测试与攻击验证

日期：2026-11-06。全部为真实执行输出（命令与结果见 §4）。

## 1. 新增测试（4 套，68 项）

| 套件 | 项数 | 结果 | 覆盖 |
| --- | --- | --- | --- |
| `learning/tests/test_source_analysis.py` | 17 | **17/17 PASS** | 入口/状态/条件/事件/副作用/失败路径、别名解析、缺失源码、静态事实边界 |
| `learning/tests/test_dependency_graph.py` | 16 | **16/16 PASS** | 来源强制、类型词汇、emit/receive 对称、查询、SCC 分类、未解析依赖 |
| `learning/tests/test_knowledge_store.py` | 20 | **20/20 PASS** | 来源门禁、digest、approve/conflict/supersede/revoke/archive、INFERENCE 规则 |
| `learning/tests/test_planner.py` | 15 | **15/15 PASS** | 公式可复算、缺口来自真实数据、排除已完成、环境阻塞、冲突任务、无 matrix 失败 |

## 2. 攻击用例清单（对应任务书 §10）

### 2.1 Source Analysis（§10.1）

| 攻击 | 用例 | 结果 |
| --- | --- | --- |
| 源码不存在 | S14/S15（临时把 `implementation_files` 置空） | `SOURCE_NOT_FOUND` + 未解决问题，不猜路径 |
| 入口函数不存在 | S16（`save_game` 契约方法 `take_damage`） | 写入 unresolved，不静默补入口 |
| 多入口歧义 | 真实 5 条（`attack_emitter` 双定义、`condition_gate` 组合场景） | `SOURCE_ENTRY_AMBIGUOUS`，两个定义位置都记录 |
| 别名/间接调用 | S12/S13（`save_slot` → `save_to_slot` 唯一匹配） | 唯一匹配才接受；多候选返回 none |
| 动态调用 | 真实 `grant.call_deferred()` | 记入 unresolved，不推断 |
| 静态≠运行时 | S7/S17 | 输出 `static_only=true`，无 runtime 字段 |
| Digest 不匹配 | K4（knowledge 侧） | 拒绝写入 |

### 2.2 Dependency（§10.2）

| 攻击 | 用例 | 结果 |
| --- | --- | --- |
| 缺失来源的依赖 | D2/D3 | 每条边必须带 `source_reference` 与 `evidence_kind` |
| 契约推导伪装成源码确认 | D6 | `CONTRACT_REFERENCE` ⇔ `CONTRACT_DERIVED`，测试强制 |
| 循环依赖 | D13/D14/D15 | 分类为 `hub_component` / `persistence_pair` / `event_loop` / `state_cycle`，不报错 |
| 共享状态 | D12 前置；真实 50 条 `SHARES_STATE_WITH` | 依据真实状态变量集合 |
| 事件传播 | D8 | emit/receive 数量对称 |
| 持久化 | D12 | `save_game` 写→读成对 |
| 过期依赖 | 重生成后 5 条 `DEPENDENCY_KNOWLEDGE` 冲突 | 冲突保留、显式解决（见 KNOWLEDGE_REPORT §4） |

### 2.3 Knowledge（§10.3）

| 攻击 | 用例 | 结果 |
| --- | --- | --- |
| 缺失来源 | K3 | 拒绝（`requires one of…`） |
| 无效来源（文件不存在） | K5 | 拒绝（`file missing`） |
| 旧源码 digest | K4 | 拒绝（`digest mismatch`） |
| 旧 Contract | K19 + `approve()` 的版本链 | `staleness()` 检出；新版本走 SUPERSEDE 而不是改数字 |
| Evidence Digest 错误 / Run 不匹配 | extract 的 `_verify_evaluation_attribution` | 归属不符时仍可存证据但**不据此下评估结论** |
| Mutation INVALID | K6 | 拒绝（只接受 `MUTANT_KILLED`） |
| 重复知识 | K10 | 同内容返回既有记录，不新增 |
| 知识冲突 | K11/K12/K13 | 建冲突、双方保留、阻断审批 |
| 历史被覆盖 | K14 | 旧记录 `SUPERSEDED` + `superseded_by`，文件保留 |
| 撤销知识重新入库 | K15/K16 | 撤销后不可再审批（文件保留） |
| Inference 被标 VERIFIED | K17/K18 | 拒绝（缺 derivations / 不许 VERIFIED） |

### 2.4 Planner（§10.4）

| 攻击 | 用例 | 结果 |
| --- | --- | --- |
| 缺 Contract/Binding | 不在支持集的 Behavior 无法进入 `plan` 输入（矩阵是唯一来源） | 计划只覆盖动态支持集（P4） |
| 缺环境 | P10（`environment_ready=False`） | 执行类任务 `BLOCKED` + 具体原因 |
| Knowledge 不完整 | P5/P8 | 生成 `ANALYZE_SOURCE` / `UPDATE_KNOWLEDGE` |
| Knowledge 冲突 | P14 | 生成 `RESOLVE_KNOWLEDGE_CONFLICT` |
| 依赖阻塞 | 依赖未知 → `ANALYZE_DEPENDENCIES` | 16 条真实任务 |
| 高风险/低成本偏差 | P3 | 优先级可复算；成本是减项，高风险项仍居前（`health/post_death_guard` 18.5） |
| 已完成不重复 | P7/P8 + `excluded` | 10 条显式排除 |
| 新知识影响优先级 | P9/P11/P12 | 有知识 vs 无知识：287 vs 277 任务，`driven_by_knowledge` 非空 |
| 缺 matrix | P13 | 直接失败（拒绝默认扫描） |

## 3. 回归（真实重跑）

| 套件 | 项数 | 结果 | 说明 |
| --- | --- | --- | --- |
| `knowledge/behavior_verification/tests/test_knowledge_store.py`（1.64） | 18 | 18/18 PASS | 1.64 存储未被破坏 |
| `evaluation/tests/test_coverage_matrix.py`（1.63） | 15 | ALL PASS | 矩阵未改 |
| `validator/tests/test_binding_candidates.py`（1.63） | 26 | ALL PASS | Binding 未改 |
| `validator/tests/test_env_paths.py`（1.64） | 18 | 18/18 PASS | Godot 解析未改 |

**未执行**（如实登记，不算通过）：

- `run_tests.py` 全量入口（最近一次在 1.64 为 133 PASS / 3 FAIL / 2 INCOMPLETE，约 57 分钟）；
  本阶段未改动那些失败涉及的模块，因此没有重跑，也**不声称**它们仍然通过/失败。
- 真实 Godot E2E / mutation 重跑：本阶段不新增 Run，直接复用 1.64 已签名产物。
- `test_end_to_end_generation.py`（>1800s）与 `test_phase160_e2e.py`（需 `--evidence-dir`）仍为已知 INCOMPLETE。

## 4. 复现命令

```bash
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
python -u .ai/tools/learning/tests/test_source_analysis.py     # 17
python -u .ai/tools/learning/tests/test_dependency_graph.py    # 16
python -u .ai/tools/learning/tests/test_knowledge_store.py     # 20
python -u .ai/tools/learning/tests/test_planner.py             # 15
python -u .ai/tools/knowledge/behavior_verification/tests/test_knowledge_store.py  # 18
python -u .ai/tools/evaluation/tests/test_coverage_matrix.py   # 15
python -u .ai/tools/validator/tests/test_binding_candidates.py # 26
python -u .ai/tools/validator/tests/test_env_paths.py          # 18
```

## 5. 统计口径

| 指标 | 值 |
| --- | --- |
| 唯一测试用例（新增） | **68** |
| 唯一测试用例（回归子集） | **77**（18+15+26+18） |
| 本阶段实际执行次数 | 每套至少 1 次；新增 4 套在开发中多次重跑（≥3 次） |
| 未执行 | `run_tests.py` 全量、Godot 新采集、mutation 重跑 |
| 计数方式 | 以各套件自身 `PASS` 行计数（`grep -c '^PASS'`），不把"未执行"计入 |
