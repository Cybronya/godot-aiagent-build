# Phase 1.63 执行前审计报告

审计时间：2026-11-04。审计方式：只读（未修改任何项目文件）。

## 1. 仓库基线

- 分支：`master`；HEAD：`dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`。
- 工作区：已跟踪修改 52 条、未跟踪 967 条（Phase 1.36–1.62 成果均未提交）。
- 最近提交仍是 `dd3a0e4 chore: 落地 Phase 1.36–1.51.2 本地增量并补齐回归基线`。
- 未发现并发 Agent 冲突迹象（无其他进程锁/近期mtime 冲突文件）；实施期间仍需遵守「只改本阶段必需文件」。

## 2. Phase 1.61 / 1.62 现状核验

- `validator/provenance/`（trust_store / signing / verification / signature_schema / key_metadata / provenance_cli）与 `validator/execution/`（identity / fingerprint / manifest / binding / attestation + 4 个测试入口）齐全，与 1.62 报告一致。
- 独立信任根 `~/.provenance_trust/game-bd3ac2f769a1/` 实际存在、可访问（工作区外，符合 1.61 设计）。
- 签名验证通过 ≠ 执行真实：`LOCAL_ISOLATED` 是当前信任等级上限，不得表述为 `EXTERNAL_TRUSTED_RUNNER`。

### Phase 1.62 测试统计口径初核

1.62 报告：新增 90（smoke 36 + attacks 31 + e2e 20 + multi-feature 3）+ 回归 142（1.61 的 5 套：57+32+21+16+16）。口径本身「新增/回归分列」无重复相加嫌疑，但 142 恰为 1.61 报告中的「新增 142」——**同一批测试在两个阶段报告中换了标签**，属可解释但需披露的口径问题。本阶段将实跑核对 unique_test_cases / executed / duplicated_executions（§7.4）。

## 3. 正式支持集合（动态计算，非硬编码）

来源：`Features/*/template.yaml#behavior`（经 `fbe.declared_features` / `fbe.build_contracts`，与采集器、Validator、`evidence_adapter.supported_set()`、mutation catalog 共用同一推导）。

- **23 个 Feature / 60 个 Behavior**（本次动态读取结果，禁止写成固定断言）。
- 8 个历史「有目录无契约」Feature 不在支持集（1.57 结论），继续排除，不为覆盖率虚增分母。
- 输出 `phase_1_63_support_inventory.json`：feature_id / behavior_id / template_path / contract_path / contract_version(内容 SHA256 前 12) / support_status / support_source。

## 4. Binding 现状

`validator/bindings/behavior_bindings.json`：6 条（BND-001…006），`trace_bindings.validate_document` 零问题；**6 条契约版本与当前契约全部 MATCH**（逐一重算内容哈希核对）；全部 approved（1.60 显式登记）。覆盖缺口：54/60 未绑定——本阶段用候选生成器如实暴露，不自动补齐。

## 5. Evidence / Signature / Attestation / Holdout 现状

- Evidence：`.ai/tmp/p160_e2e/evidence/`（health / collect_pickup / save_game，1.60 实测产物）。
- Signature：`.ai/tmp/p161_e2e/{all,tampered}/` 有 3 Feature 的 bundle + `.sig.json` sidecar（1.61 E2E 产物）。
- **Attestation：1.62 的 E2E（run_execution_e2e.py / run_multi_feature_e2e.py）使用 `tempfile.mkdtemp` + `shutil.rmtree`，产物即弃**——当前不存在可引用的持久 Run Manifest / Attestation 产物。覆盖矩阵的 attestation / latest_run_id 维度初始为 null，需本阶段重跑 E2E 并持久化产物（含真实签名）。
- Holdout：`holdout_datasets.json`：v1 INVALIDATED（空封存事故，留痕）、v2/v3 已 CONSUMED（真实消费，重复消费被拒过）。当前无 SEALED 可用数据集 → Holdout 维度初始 NO_HOLDOUT，如实报告。

## 6. L5 Mutation 现状（M04 / M06 根因确认）

最近全量实测（`.ai/tmp/p159/all-final.log`）：8 条注入 → 6 KILLED / 2 INVALID_MUTANT / 0 SURVIVED。

### M04 — trigger_switch / latch_once（INVALID，根因已确认）

- 契约 actions：`overlap → advance_frames(6) → overlap`，之后**无帧推进**直接观测。
- 探针 `_impl_physics_overlap` 的语义是**生成一个新 CharacterBody2D** 放到目标位置；`body_entered` 是边沿事件，需要 ≥1 个 physics 帧处理后才会发出。
- 实测 M04 报告：control 与 mutant 的 `trigger.activated` observed 均为 1 → 第二个实体从未被 Area2D 感知 → 被删除的 `if _triggered: return` 守卫根本没被执行。
- **结论：这是契约场景设计缺陷（可修复），不是业务语义上「第二次触发不合理」。** 修复方向：在第二次 overlap 之后补 `advance_frames`，让 physics 处理进入边沿。预期 control 仍 count 1（守卫生效）、mutant count 2（守卫缺失）→ 可判 KILLED。
- 连锁影响：改契约 → latch_once 契约内容哈希变化 → BND-005 `CONTRACT_MISMATCH` → 必须走本阶段新建的候选生成 + 显式审批流程重新绑定（正好实测新机制）。M08（同 behavior 的替代注入）不受影响。

### M06 — save_game / save_slot_persists_world_state（INVALID，根因已确认）

- `save_game.gd` 持久化到 `user://saved_games/`（含 `_last.txt`）。采集器为每次运行构造临时 project.godot，但 application name 不变 → `user://` 映射到同一个 `%APPDATA%/Godot/app_userdata/<name>/` → **跨 run 残留**。control 留下的 `_last.txt` 使 mutant 的 `savegame.last_slot` 回读仍为 `behavior_save` → 无法区分。
- **修复方向（加法式）**：采集器构造临时项目时支持 per-run `use_custom_user_dir=true` + 唯一 `custom_user_dir_name`（显式参数/开关，默认行为不变）；harness 传递 run 唯一标记并负责目录清理与登记。每次 collect（control/mutant/recovery）独立 user 目录，互不残留、不依赖仓库外既有数据。
- 观察路径 `observe_savegame_last_slot` 读的是同 run 的 `user://`，隔离后 control 读到本 run 写入的 `behavior_save`，mutant 读到空 → effectiveness 可判。

### Mutation 判定与扩展

- 现有 Verdict 体系（KILLED / SURVIVED / INVALID / HARNESS_ERROR / TIMEOUT / NOT_RUN）与 effectiveness 运行时判定符合任务书 §5.3，INVALID 不计入 KILLED（`summarize` 分开计数）。
- M04/M06 修复后按风险优先级补少量高价值 Mutation（候选：health/i_frames 重复触发、contact_damage 防重复、sfx_pool 资源上限），每条满足独立隔离、真实执行、恢复证明。

## 7. 覆盖矩阵数据源核对

| 维度 | 数据源 | 现状 |
| --- | --- | --- |
| Contract | template.yaml 动态构建 | 60/60 |
| Binding | bindings/behavior_bindings.json | 6/60 |
| Evidence | bundle.json + Validator | 3 Feature 级 bundle |
| Signature | bundle.sig.json + provenance | 3（p161_e2e） |
| Attestation | execution/manifest + attestation | 0（产物即弃） |
| Evaluation | evidence_report.json | 历史报告可引用 |
| Holdout | holdout_datasets.json | 0 可用（v2/v3 已消费） |
| Mutation | p159/reports/*.json | 6 KILLED / 2 INVALID |

## 8. 已知缺陷与风险

1. M04 契约场景缺陷（本阶段修复）。2. M06 user:// 残留（本阶段修复）。3. 1.62 E2E 产物不持久（本阶段改为持久化输出 + 真实签名）。4. 审批者身份仍是流程审计（1.61 已有独立信任根 + Ed25519，Binding 审批记录应接签名，向「审批者身份真实性」推进，但仍非 CI/KMS 级）。5. Holdout 当前无可用的 SEALED 数据集（如需 Holdout 维度绿色需新采集 + 封存，或如实报 NO_HOLDOUT）。

## 9. 推荐实施顺序

1. support_inventory 动态清单。2. Binding 候选生成器 + 显式审批（含签名审批记录）→ 修复 M04 契约后的 BND-005 重审实测。3. M04/M06 修复 + mutation 重跑 + 少量扩展。4. Coverage Matrix（七维独立状态 + 动态分母 + strict 语义）。5. 真实 E2E（3 Feature 全链，持久化 manifest/attestation）。6. 测试矩阵 + 攻击测试 + 1.56–1.62 回归。7. 文档与完成报告。

## 10. 不应修改的文件

Evidence Collector 核心语义、Validator 五阶段核心、Mutation Harness 的 Verdict/Effectiveness/仓库看守语义、既有 6 条 Binding 与 4 条 Baseline 的历史登记、其他 Agent 产物。采集器与探针只做**加法式**扩展（per-run user dir 选项、无新语义侵入）。
