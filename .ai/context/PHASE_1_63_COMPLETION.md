# Phase 1.63 执行完成报告 — Behavior Binding Expansion & Coverage Reconciliation

完成时间：2026-11-04。分支 `master`，审计时 HEAD `dd3a0e4`，未提交（延续 1.56–1.62 的未提交工作区）。未执行任何 git 写操作。

---

## 1. 实际完成内容

**新增文件**

| 文件 | 用途 |
| --- | --- |
| `validator/binding_candidates.py` | Binding 候选生成（expected 只来自契约，缺失即 BLOCKED_MISSING_EXPECTED）+ 显式审批状态机（DRAFT→PENDING_REVIEW→APPROVED，REVOKED/SUPERSEDED/REJECTED）+ 审批登记表 + 晋升 + §3.4 门禁状态 + 支持清单生成 + CLI |
| `validator/bindings/binding_candidates.json` | 54 条候选的登记与审批时间线 |
| `validator/bindings/approval_registry.json` | Binding 审批登记表（59 条记录，全部带 Ed25519 签名封套） |
| `.ai/context/phase_1_63_support_inventory.json` | 动态支持清单（23 Feature / 60 Behavior，含契约版本） |
| `evaluation/coverage_matrix.py` | 覆盖矩阵（八维独立状态、动态分母、null 不造假、--strict） |
| `.ai/context/coverage_matrix.json/.md` | 覆盖矩阵产物 |
| `validator/execution/run_p163_e2e.py` | 1.63 全链 E2E（持久化产物 + 真实独立信任根） |
| `validator/tests/test_binding_candidates.py`（26 项）、`evaluation/tests/test_coverage_matrix.py`（15 项） | 新增测试 |
| `.ai/context/PHASE_1_63_AUDIT.md` / `PHASE_1_63_COMPLETION.md` / `PHASE_1_63_COVERAGE_REPORT.md` / `PHASE_1_63_ATTACK_TESTS.md` | 文档 |

**修改文件（全部加法式或最小修复）**

- `provenance/signature_schema.py`：+OBJECT_BINDING / SCOPE_APPROVE_BINDING（1.62 扩展模式的延续）。
- `validator/trace_bindings.py`：**缺陷修复**——放宽检查的契约索引按 (check,target,entry) 只留一条，同目标多检查（如 displacement x/y 轴）互相覆盖导致误报 CONTRACT_MISMATCH；改为分组列表 + axis 身份核对 + 全字段一致匹配。
- `Features/trigger_switch/template.yaml`：**M04 根因修复**——latch_once 第二次 overlap 后补 advance_frames(6)（契约变更→BND-005 走重绑）。
- `scene_composer/feature_behavior_evidence.py`：**M06 根因修复**——BehaviorWorkspace 支持 `--user-dir-tag`（use_custom_user_dir 隔离 user://），缺省行为不变。
- `evaluation/mutation/harness.py`：collect() 传唯一 tag 并清理隔离目录。
- `evaluation/mutation/mutation_catalog.yaml`：+M09（i_frames 无敌门删除）、+M10（contact_damage 伤害应用删除）。
- `evaluation/holdout_registry.py`：**幂等修复**——VALIDATED→VALIDATED 允许（seal_dataset_signed 内部重验被拒）。
- `evaluation/evidence_tasks.yaml`：E5 的 last_args 期望补 count:1（1.60 时已修，此处无变化）。
- `validator/bindings/behavior_bindings.json`：从 6 条扩至 60 条（覆盖整个动态支持集）。
- `validator/tests/test_trace_bindings.py`、`evaluation/tests/test_cross_binding.py`：断言从历史固定数量（6 条绑定）改为动态支持集口径（语义加严，不是放松）。

---

## 2. 正式支持集合（动态读取）

- 来源：`Features/*/template.yaml#behavior`（`evidence_adapter.supported_set()`，采集器/Validator/Binding/Matrix/Mutation 共用同一推导）。
- **本次读取结果：23 Feature / 60 Behavior**。8 个历史「有目录无契约」Feature 继续排除在分母外。
- 清单：`.ai/context/phase_1_63_support_inventory.json`（含每条 contract_version=契约内容 SHA256 前 12）。

## 3. 覆盖矩阵（分母 = 动态支持集 60；数据为生成时快照）

| 维度 | 分子 | 分母 | 比例 |
| --- | --- | --- | --- |
| Contract | 60 | 60 | 100% |
| Binding（含审批中） | 60 | 60 | 100% |
| Approved Binding | 60 | 60 | 100% |
| Evidence Verified | 8 | 60 | 13% |
| Signature Verified | 8 | 60 | 13% |
| Attestation Verified | 8 | 60 | 13% |
| Evaluation VERIFIED_PASS | 5 | 60 | 8% |
| Holdout Available | 1 | 60 | 2% |
| L5 Mutation Killed | 9 | 60 | 15% |
| Mutation Invalid | 0 | 60 | 0% |
| Fully Covered | 0 | 60 | 0% |

每条未覆盖 Behavior 都有 `missing_requirements`（缺失维度列表）与 `next_recommended_action`（可执行下一步）。--strict 退出码 2 已实测。

## 4. 真实执行结果（run_p163_e2e.py，24 checks 0 failures）

| Feature | 验证特征 | Run ID（Execution） | Artifacts | Attestation | Evaluation |
| --- | --- | --- | --- | --- | --- |
| health | 状态转换 | `8602…59059f3`（持久化） | 40 | ATTESTED_VERIFIED | VERIFIED_PASS |
| collect_pickup | 事件传播 | 同批持久化 | 8 | ATTESTED_VERIFIED | VERIFIED_PASS |
| save_game | 持久化 | 同批持久化 | 16 | ATTESTED_VERIFIED | VERIFIED_PASS |

链路：契约→绑定 gate→真实 Godot 采集（replay=2）→bundle（integrity）→Ed25519 签名（真实独立信任根 `~/.provenance_trust/game-bd3ac2f769a1`，scope=issue_evidence）→Manifest→Attestation（scope=attest_execution）→verify→evidence_eval。产物持久化于 `.ai/tmp/p163_e2e/{evidence,runs}`。**区别于 1.62 E2E 的临时产物**。

Holdout：独立批次采集 openable_door（隔离 user:// 目录）→ `P163-HOLDOUT` v2 签名封存（scope=seal_holdout，`seal_dataset_signed`）→ 矩阵 HOLDOUT_AVAILABLE。v1 登记未封存，已 INVALIDATED 留痕。

## 5. Mutation 结果

| Mutation | 目标 Behavior | 注入 | 触发 | 判定 | 恢复 |
| --- | --- | --- | --- | --- | --- |
| M04 trigger_switch/latch_once | 同左 | 锚点删除 latch 守卫 | control count 1 / mutant count 2 | **MUTANT_KILLED**（原 INVALID） | 逐字节 True |
| M06 save_game/save_slot_persists_world_state | 同左 | 删 last_slot 记录 | control "behavior_save" / mutant "" | **MUTANT_KILLED**（原 INVALID） | 逐字节 True |
| M09 i_frames/iframes_block_damage_within_window | 同左 | 删 set_invulnerable(true) | control 9 / mutant 8 | **MUTANT_KILLED** | 逐字节 True |
| M10 contact_damage/damage_on_contact | 同左 | 删 take_damage 调用 | control 4 / mutant 5 | **MUTANT_KILLED** | 逐字节 True |
| M01–M03/M05/M07/M08 | （1.59 既有） | — | — | 全部 MUTANT_KILLED | 全部 True |

全量实测：**10/10 KILLED，0 INVALID / 0 SURVIVED / 0 ERROR**；仓库看守（Features/** sha256 快照）全部零变化。

### M04 / M06 根因（审计→实验→修复的完整链）

- **M04**：探针 `_impl_physics_overlap` 每次生成新实体，`body_entered` 是边沿事件；且探针等待循环「检查全部满足即停」（feature_behavior_probe.gd:348），latch_once 的 expected count=1 在第一次发射后即满足 → 第二次进入事件从未被处理。修复：契约补尾部 advance_frames，强制物理帧处理（隔离副本实验先行验证 control PASS / mutant MISMATCH，再落真契约）。
- **M06**：采集器临时项目沿用同一 application name → `user://` 映射同一 app_userdata 目录，control 留下的 `_last.txt` 使 mutant 回读无差异。修复：per-run `use_custom_user_dir` 隔离（缺省不变），harness 生成唯一 tag 并清理。

## 6. 测试结果（全部实跑；口径：unique checks）

**新增（41）**：binding_candidates 26 ✅、coverage_matrix 15 ✅；另 1.63 E2E 24 ✅。

**回归（519，全过）**：

| 阶段 | 套件 | 项数 | 结果 |
| --- | --- | --- | --- |
| 1.58/1.59 评估 | evidence_adapter 52 / evidence_eval 20 / runner 24 / scoring 28 | 124 | ✅ |
| 1.59 mutation | harness 51 / integration 15 | 66 | ✅ |
| 1.60 | trace_bindings 28 / baseline_lifecycle 26 / phase160_e2e 5 / holdout 23 / cross_binding 15 | 97 | ✅ |
| 1.61 | provenance_core 57 / attacks 32 / baseline_sig 21 / evidence_sig 16 / holdout_sig 16 | 142 | ✅ |
| 1.62 | smoke 36 / attacks 31 / execution_e2e 20 / multi_feature 3 | 90 | ✅ |
| 框架 | validate.py | — | 0 error / 17 warning（与基线一致） |

**未执行**：`run_tests.py` 全量入口与 e2e 生成链路套件（约 29 分钟；本阶段未触碰生成链路）。其余全部实跑，无重复计数（两个 Godot E2E runner 各跑 1 次）。

**Phase 1.62 测试口径核查结论**：1.62 报告「新增 90 + 回归 142」分列、无重复相加；142 与 1.61 报告的「新增 142」是**同一批测试换了标签**（1.61 新增→1.62 回归），口径可解释但属披露事项；本阶段 232 项 unique 全部重跑通过。1.62 两个 E2E runner 存在**预先存在的 Godot 路径缺陷**（`_PROJECT_ROOT` 少算一层），需 `GODOT_BIN` 环境变量；本阶段未修（保持 1.62 产物原样），已登记为已知问题。

## 7. 安全与信任边界

- **已交付**：审批记录的密码学完整性（Ed25519，独立信任根，scope 隔离——approve_binding/issue_evidence/attest_execution/seal_holdout 各用专钥）；内容完整性（候选/绑定/基线摘要使用时复核）；审批流程完整性（状态机 + digest 重核 + 契约漂移拒绝）。
- **未交付（如实声明）**：审批者/签署者的**人类身份真实性**——reviewer 是自报文本，私钥在用户目录、同权限可读；签名证明「记录自签名后未被篡改」，不证明「独立可信主体批准」。无 CI/KMS/独立执行器 → `LOCAL_ISOLATED`，**不是** `EXTERNAL_TRUSTED_RUNNER`；签名验证通过 ≠ 执行过程真实。
- 攻击测试：本阶段新增的拒绝路径见 `PHASE_1_63_ATTACK_TESTS.md`；1.61（A01–A18）与 1.62（E01–E30）攻击套件全部重跑通过。

## 8. 工作区状态

- HEAD `dd3a0e4`；已跟踪修改 52 条、未跟踪 967+（新增文件见 §1）；无 git 写操作；无删除其他 Agent 产物；私钥/种子全部在工作区外（`~/.provenance_trust/`），仓库内仅公钥信任记录。
- 密钥登记（用户级信任根，工作区外）：PROVKEY-d865e3d79add3740（approve_binding）、PROVKEY-5aa9912c2dbb6587（issue_evidence+attest_execution）。

## 9. 未完成事项 / 已知问题

1. Evidence/Signature/Attestation/Evaluation/Holdout/Mutation 六个维度的覆盖仍集中在 9 个 Behavior——其余 51 个 Behavior 的覆盖推进是下一阶段（L5 扩张 / Learning Engine）的主要工作，矩阵的 `next_recommended_action` 已逐条给出路径。
2. 1.62 两个 E2E runner 的 Godot 路径缺陷（需 GODOT_BIN）未修——属 1.62 产物，改动留待授权。
3. `run_tests.py` 全量入口与生成链路 e2e（29 min）未重跑。
4. 审批者身份真实性依赖用户管理信任根文件，无撤销自动化。
