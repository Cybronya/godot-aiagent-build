# Phase 1.64 — Attack / 安全边界测试记录

原则：攻击测试必须**真实执行**（不是读代码声明），失败即失败，不因为"这是攻击用例"就放宽断言。

## 1. 本阶段新增的拒绝路径（真实测试）

| # | 攻击/边界 | 期望 | 实现位置 | 结果 |
| --- | --- | --- | --- | --- |
| P1 | 伪造知识事实：来源类型写 `GUESS` | 拒绝写入 | `knowledge/behavior_verification/store.validate` | ✅ `test_knowledge_store.py` K2 |
| P2 | 事实无 claim / 无 source_ref | 拒绝写入 | 同上 | ✅ K3 |
| P3 | `CONTRACT_FACT` 指向 `.ai/tmp` 笔记（非契约/绑定） | 拒绝 | 同上 | ✅ K4 |
| P4 | 写入时**静默丢弃**旧事实 | 拒绝（必须追加） | `store.save` | ✅ K7 |
| P5 | 契约版本漂移后沿用旧记录（静默升级） | 拒绝 | `store.save` | ✅ K8 |
| P6 | 非法记录落盘（先校验失败） | 已存文件字节不变 | `store.save` | ✅ K9 |
| P7 | `GODOT_BIN` 指向不存在文件 | 不回退到其它二进制；`ENVIRONMENT ERROR` | `execution/env_paths.py` | ✅ `test_env_paths.py` E3/E3b |
| P8 | 完全没有 Godot（无配置/无相邻/无 PATH） | 明确环境错误，不伪装 PASS/FAIL | 同上 | ✅ E7/E7b |
| P9 | 两个 1.62 Runner 重新自己算项目根（回归） | 源码级拒绝（必须用 env_paths） | `test_env_paths.py` E9/E9b | ✅ |
| P10 | 相对路径配置逃逸（`tools/godot_fake.exe` 按项目根解析） | 解析到项目根下，不按 cwd | `env_paths.configured_godot` | ✅ E5 |
| P11 | Runner 用未审批 Binding 生成评估任务 | 直接 `SystemExit`，不降级 | `run_p164_batch.tasks_from_bindings` | ✅ 代码路径（批次 3 个 Feature 全部门禁 APPROVED 才会开跑） |

## 2. 历史攻击套件的回归（本次重跑，真实退出码）

| 套件 | 项数 | 结果 | 日志 |
| --- | --- | --- | --- |
| `validator/execution/tests/test_attacks.py`（1.62：篡改 attestation / 跨 run 混料 / sidecar 缺失等） | 31 | **31 checks, 0 failures**（exit 0） | `.ai/tmp/p164/test_attacks.log` |
| `validator/provenance/tests/test_provenance_attacks.py`（1.61：签名/信任根/范围隔离攻击） | 32 | **32 checks, 0 failures**（exit 0） | `.ai/tmp/p164/test_provenance_attacks.log` |
| `validator/tests/test_binding_candidates.py`（1.63：候选/审批/契约漂移） | 26 | ALL PASS（exit 0） | `.ai/tmp/p164/test_binding_candidates.log` |
| `evaluation/tests/test_coverage_matrix.py`（1.63：八维状态/null 不造假） | 15 | ALL PASS（exit 0） | `.ai/tmp/p164/test_coverage_matrix.log` |

合计 **104 项，0 失败**。

## 3. Mutation 的安全边界（复用 1.59 harness，本阶段新增两条 mutation 仍走同一路径）

| 边界 | 机制 | 本阶段证据 |
| --- | --- | --- |
| 只改隔离副本 | `workspace.copy_features` + 快照差异必须恰好一个文件 | M11/M12 报告 `static.changed_files` 各 1 |
| 源哈希绑定 | `source_sha256` 不符 → `NOT_RUN` | M11/M12 的 `catalog.source_sha256` 与实际文件一致 |
| 锚点唯一 | `anchor_not_unique`（0 或 >1） | M11/M12 落盘前用脚本核过 count==1 |
| 结构性校验 | 空 diff / 括号平衡 / 语句边界 | M11 特意保留 `if` 块体（`pass`），避免 M07 那类"删成空块"的假缺陷 |
| 逐字节恢复 | recovery 轮 + `restored_byte_for_byte` | 见 mutation 报告 |
| 仓库只读 | `repo_guard.changed` | 见 mutation 报告 |
| 不清理他人文件 | ownership 标记 + 只删自己的 run 目录 | 1.59 harness 测试 Z1/D13–D15 仍全过 |

## 4. 不是攻击、但明确拒绝的路径（诚实声明）

- **审批者/签署者的人类身份**：签名证明"记录自签名后未被篡改"，不证明"独立可信主体批准"。私钥在用户目录、同权限可读 → `LOCAL_ISOLATED`，不是 `EXTERNAL_TRUSTED_RUNNER`。
- **执行过程真实性**：没有 CI/KMS/独立执行器，无法证明 Godot 没被替换。
- **矩阵的跨批次归因**（审计 P2）：属于"读数"缺陷而非攻击面；本阶段用显式目录规避，未改 1.63 实现。
