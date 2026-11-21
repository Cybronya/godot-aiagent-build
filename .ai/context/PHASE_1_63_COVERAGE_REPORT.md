# Phase 1.63 覆盖对账报告（Coverage Report）

生成方式：`python .ai/tools/evaluation/coverage_matrix.py --include-legacy`
（机读版：`coverage_matrix.json`；人读版：`coverage_matrix.md`；本报告为解读层。）

## 1. 分母规则

- 正式支持集合 = `Features/*/template.yaml#behavior` 动态推导（当前 23 Feature / 60 Behavior）。
- 不把 8 个「有目录无契约」的历史 Feature 计入分母；不硬编码任何数量。
- 新增/删除 Feature 或 Behavior 后重跑即可自动进入/退出矩阵（测试 M1/M2 覆盖）。

## 2. 快照摘要（2026-11-04）

| 维度 | 覆盖 | 说明 |
| --- | --- | --- |
| Contract | 60/60 | 全部契约可解析且有可评估 expected |
| Approved Binding | 60/60 | 全部经显式审批 + Ed25519 签名登记（BND-005 因 M04 契约修复被 SUPERSEDED，由 BND-TRIGGER_SW-LATCH_ONCE 顶替） |
| Evidence Verified | 8/60 | health(5)、collect_pickup(1)、save_game(2)——真实 Godot 采集 |
| Signature Verified | 8/60 | 与 Evidence 同批（真实独立信任根 sidecar） |
| Attestation Verified | 8/60 | 3 个持久化 Execution Run（manifest+签名封套，按 evidence_reference 关联） |
| Evaluation VERIFIED_PASS | 5/60 | E1/E2/E3-P163 + 1.60 历史报告中的 VERIFIED_PASS |
| Holdout Available | 1/60 | P163-HOLDOUT v2（openable_door/open，签名封存，未消费） |
| L5 Mutation Killed | 9/60 | health/damage、health/post_death_guard、collect_pickup、trigger_switch/latch_once(M04+M08)、openable_door、save_game×2、i_frames、contact_damage |
| Mutation Invalid | 0/60 | M04/M06 已从 INVALID 修复为 KILLED |
| Fully Covered | 0/60 | 无一 Behavior 同时满足全部八维 |

## 3. 缺口与下一步（矩阵自动生成，示例）

每个未覆盖 Behavior 的行内含 `missing_requirements`（如 verified_signature / verified_attestation / holdout / l5_mutation）与 `next_recommended_action`（如「运行采集器」「用信任根密钥签署 bundle」「封存独立批次」「设计高价值 Mutation」）。

优先推进顺序建议（风险 × 复用度）：

1. 为已有 Evidence 的 9 个 Behavior 补齐 Holdout（封存独立批次）与更多 Mutation。
2. 按 Feature 分批为其余 51 个 Behavior 采集 Evidence → 签名 → Attestation → Evaluation（采集器、审批、矩阵工具链已全部就绪，纯执行量）。
3. 编排场景（waves/boss 等）的 Golden Trace 逐行为绑定判定（声明行为全集）仍属后续。

## 4. 诚实性约束（矩阵的设计红线）

- 没有 bundle/manifest/签名 → 状态为 NO_*，digest/run_id 为 null，绝不编造。
- Legacy bundle（无 sidecar）在 `--include-legacy` 下也只计 Evidence，不计 Signature。
- INVALID Mutation 永不计入 KILLED（测试 M6 锁定）。
- `--strict` 有缺口即退出码 2；普通报告模式退出 0（报告成功 ≠ 全绿）。
