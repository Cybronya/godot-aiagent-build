# Phase 1.64 — Batch 1 报告（save_game / i_frames / openable_door）

- 批次：B1
- 运行时间：2026-11-04
- Runner：`.ai/tools/validator/execution/run_p164_batch.py --label B1`
- 环境：Godot `4.7.stable.official.5b4e0cb0f`（`F:\Godot_v4.7-stable\Godot_v4.7-stable_win64_console.exe`，**未设置 `GODOT_BIN`**）
- 项目根：`F:\Godot_v4.7-stable\game`（由 `env_paths.project_root()` 解析）
- 信任级别：`LOCAL_ISOLATED`（签名证明密码学完整性，不证明执行过程真实；无 CI/KMS）

## 1. 本批 Behavior（6 条，3 个类型）

| Feature | Behavior | 类型 | 场景 / 触发 |
| --- | --- | --- | --- |
| `save_game` | `save_slot_persists_world_state` | C 持久化 | 扣血 → 存槽 → 回读 last_slot 与血量 |
| `save_game` | `load_slot_restores_world_state` | C 持久化 | 存槽 → 再扣血 → 读档回填 |
| `i_frames` | `iframes_block_damage_within_window` | F 守卫 | 受击开窗 → 窗口内第二次受击被拒 |
| `i_frames` | `iframes_expire_and_damage_resumes` | A 状态转换 | 22 帧后窗口结束 → 再受击生效 |
| `i_frames` | `killing_blow_still_dies` | F 守卫 | 无敌不豁免致死判定 |
| `openable_door` | `open` | A 状态转换 + B 事件 | `set_open(true)` → is_open + state_changed |

选择理由（来自 `PHASE_1_64_BEHAVIOR_INVENTORY.md` 的风险排序，不是沿用历史对象）：
`save_game` 两条是最高风险（risk 25）；`i_frames` 是跨系统状态一致性（免疫/致死）风险 20–21；
`openable_door/open` 是唯一已有 Holdout 的数据集对象，可验证第八维。

## 2. 真实执行结果

| Feature | Run ID（Execution） | Artifacts | Evidence Signature | Execution Attestation | Evaluation |
| --- | --- | --- | --- | --- | --- |
| `save_game` | `c8d79878-1056-4af5-b245-3f09422dd573` | 16 | `SIGNATURE_VERIFIED` | `ATTESTED_VERIFIED` | 2/2 `VERIFIED_PASS` |
| `i_frames` | `5bfa2856-ea71-4f25-834b-43ab0644b3b0` | 24 | `SIGNATURE_VERIFIED` | `ATTESTED_VERIFIED` | 3/3 `VERIFIED_PASS` |
| `openable_door` | `d99530a9-0502-4759-8eaa-98d3429aed02` | 8 | `SIGNATURE_VERIFIED` | `ATTESTED_VERIFIED` | 1/1 `VERIFIED_PASS` |

逐 Behavior 的 Run / Digest（来自矩阵快照 `matrix_after`，digest 为前 24 位）：

| Behavior | 采集 Run ID | Evidence bundle | Evidence digest | Attestation digest |
| --- | --- | --- | --- | --- |
| `save_game/save_slot_persists_world_state` | `11964-26505382-save_slot_persists_world_state` | `.ai/tmp/p164/batch1/evidence/11964-4a3f99e6-bundle.json` | `5f37e50ee9b67819487cb5df…` | `8f551c88d2d4e8dfa446f0a5…` |
| `save_game/load_slot_restores_world_state` | `11964-5ac63726-load_slot_restores_world_state` | 同上 | 同上 | 同上 |
| `i_frames/iframes_block_damage_within_window` | `11964-8bdcd570-iframes_block_damage_within_window` | `.ai/tmp/p164/batch1/evidence/11964-c659bb45-bundle.json` | `d55bfd4102590ab56a41545f…` | `0bbaa57ccafd5e97f9f6130a…` |
| `i_frames/iframes_expire_and_damage_resumes` | `11964-79c99c5e-iframes_expire_and_damage_resumes` | 同上 | 同上 | 同上 |
| `i_frames/killing_blow_still_dies` | `11964-88067554-killing_blow_still_dies` | 同上 | 同上 | 同上 |
| `openable_door/open` | `11964-ad881e33-open` | `.ai/tmp/p164/batch1/evidence/11964-03d7200e-bundle.json` | `c07409026f94725a89dfa8d5…` | `b8efa2ad73560ec70f2d9f99…` |

- 采集：每条 Behavior `replay=2`，两次重放一致（`replay_consistent`）；每个 Feature 的 bundle 覆盖该 Feature 全部 Behavior（因此同一 Feature 内 digest 相同，这是 bundle 粒度，不是复制）。
- **Evidence Signature 与 Execution Attestation 是两个独立对象**：前者对 bundle 内容摘要（`evidence-bundle-digest-v1`）签名，后者把 manifest（artifact 集合 + 四个 fingerprint）与一次真实 run 绑定。两者分别验证，不互相替代。

## 3. 门禁与链路（21 项检查，0 失败）

每个 Feature 依次通过：`contract_present` → `binding_approved`（逐 Behavior 的 `APPROVED_BINDING`）→
`godot_collection`（真实 PASS）→ `bundle_written`（integrity 重算）→ `evidence_signed`
（`SIGNATURE_VALID`）→ `manifest_valid` → `attestation_verified`（`ATTESTED_VERIFIED`）。

Evaluation 的 expected 逐字来自**已审批 Binding**（`tasks_from_bindings`），不是手写：
任一 Behavior 没有 APPROVED Binding 或 expected 为空时，Runner 直接 `SystemExit`，不会降级成"跑一下看看"。

## 4. 覆盖矩阵变化（同口径前后对比）

两次矩阵都由同一脚本、同一口径重算；差异只有证据/评估目录：

| 维度 | Batch 1 前 | Batch 1 后 | 变化 |
| --- | --- | --- | --- |
| Evidence Verified | 8 | 12 | **+4** |
| Signature Verified | 8 | 12 | **+4** |
| Attestation Verified | 8 | 12 | **+4** |
| Evaluation VERIFIED_PASS | 8 | 12 | **+4** |
| Holdout Available | 1 | 1 | 0 |
| L5 Mutation Killed（Behavior 数） | 9 | 9 | 0（本批 mutation 见 §5） |
| **Fully Covered** | **0** | **1** | **+1**（`openable_door/open`，八维齐全） |

为什么是 +4 而不是 +6：`save_game` 的两条在 1.63 已有证据，本批是**重跑复核**（防止回归），
新增覆盖来自 `i_frames`（3）与 `openable_door`（1）。

## 5. 本批 L5 Mutation

本批新增两条（catalog 10 → 12）：

| Mutation | 目标 Behavior | 缺陷模型 | 观测（control → mutant） | 判定 |
| --- | --- | --- | --- | --- |
| `M11-i-frames-window-close-not-restored` | `i_frames/iframes_expire_and_damage_resumes` | 窗口到期不归还 Health 无敌门（`_on_window_end` 里 `set_invulnerable(false)` 变为 `pass`） | `health.current` 8 → **9** | **MUTANT_KILLED** |
| `M12-openable-door-open-guard-inverted` | `openable_door/open` | 幂等守卫 `==` → `!=`（任何变化都早退，门永远打不开） | `door.is_open` true → **false** | **MUTANT_KILLED** |

实测（`summary-3de41ad2.json`，`.ai/tmp/p164/mutation2/`，独立目录，不覆盖 1.59/1.63 的既有报告）：

```
mutations: total=2 effective=2 killed=2 survived=0 invalid=0 error=0 timeout=0 not_run=0
```

- M11：control `health.current=8`（PASS）→ mutant `9`（`STATE_MISMATCH`），mutant Evaluation `INVALID_EVIDENCE` / Validator `FAIL`；
- M12：control `door.is_open=true`（PASS）→ mutant `false`（`STATE_MISMATCH`）；
- 两条的 control 与 recovery 均 `VERIFIED_PASS`，`restored_byte_for_byte=true`，`repo_guard.changed=false`。

catalog 合计 **12 条**（10 条 1.59/1.63 + 本批 2 条），覆盖 **10 个 Behavior**（M04/M08 同属 `latch_once`；M05/M12 同属 `openable_door/open`）。

## 6. 未做 / 限制

- 本批没有新 Holdout（`i_frames` / `save_game` 仍 `NO_HOLDOUT`），因此 Fully Covered 只增加 1。
- `save_game` 的 `user://` 已用 per-run tag 隔离（1.63 的修复沿用），但同一 Feature 内的两条 Behavior 共享一个 bundle，不能单独签名——这是 bundle 粒度的既有限制。
- 证据与签名只证明"内容自签名后未被篡改"，不证明审批者/执行者的人类身份（`LOCAL_ISOLATED`）。
