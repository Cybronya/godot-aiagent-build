# Phase 1.61 完成报告 — Independent Trust Root & Provenance

日期：2026-11-04。分支 `master`，HEAD `dd3a0e4`（实施前后未变；全部成果为工作区未提交增量）。
审计：[PHASE_1_61_AUDIT.md](PHASE_1_61_AUDIT.md)。

## 1. 原始信任边界问题（Phase 1.60 遗留）

系统此前能证明**内容完整性**（SHA256 + 使用时复核）与**审批流程一致性**（状态机 + 登记表），
但无法证明**审批者/签发者身份真实性**：同权限攻击者可同时改写 Baseline 内容、摘要、
审批登记表、Evidence 与 Holdout 封存记录，且 `approver` 是自报文本、登记表与被登记
对象处于同一写权限边界。

## 2. 新的信任模型

| 对象 | 签名绑定 | scope | 状态 |
| --- | --- | --- | --- |
| Baseline | baseline_id + version + 登记固化 content_digest + 审批者/审批时间 | `approve_baseline` | 登记条目内 `provenance_signature` |
| Evidence Bundle | bundle_id + schema_version + bundle 规范化摘要（含 artifact 摘要集） | `issue_evidence` | sidecar `<bundle>.sig.json`（bundle 字节零改动） |
| Holdout 数据集 | holdout_id + dataset_version + 封存摘要 + 来源 + 封存时间 | `seal_holdout` | 登记记录内 `provenance_signature` |
| Trust Root | 不自签——锚定于**工作区之外**的用户级文件位置 | — | 见 §3 |

签名封套（detached）：对封套（除 `signature` 字段）的规范化 JSON（sort_keys + 紧凑
分隔符 + UTF-8）做 Ed25519 签名。对象类型/ID/版本/摘要/scope 全部在签名消息内 →
跨对象、跨类型、跨版本、跨 scope 复用签名必然验证失败。

**签名证明什么（边界声明）**：签名 = "持有某外部信任根所列私钥的主体，在时间 T
签署了摘要为 D 的对象 O（用途 S）"。**不**证明 Godot 真的执行过对应行为、采集进程
未被篡改、执行环境可信。Evidence 签名者若与采集器同权限运行，其证明力等同采集器
自报——此边界写入模块 docstring、报告与验证结果 `note` 字段。

## 3. 信任根实际来源（IMPLEMENTED + VERIFIED）

- **方案**：用户管理的独立公钥文件，位于项目工作区写权限边界之外：
  `C:\Users\Administrator\.provenance_trust\game-bd3ac2f769a1\trust_root.json`
  （`<home>/.provenance_trust/<项目 slug>/`，按项目隔离——同机多项目信任根互不混用）。
- **已真实建立**：`provenance_cli.py keygen` 实际执行，产生 ACTIVE 密钥
  `PROVKEY-696f89a140eba658`（subject: Phase 1.61 local release signer），
  私钥种子在 `<trust dir>/keys/`（工作区外，0600）。
- **覆盖入口**：`PROVENANCE_TRUST_ROOT` 环境变量、CLI `--trust-root` 参数。
- **硬规则**：信任根路径解析后位于项目工作区内 → `TRUST_ROOT_INSECURE_LOCATION`
  拒收（fail-closed）；撤销覆盖文件同规则；工作区内任何自报公钥/撤销记录一律无效。
- **诚实边界**：该方案防"工作区写权限攻击者"（A01–A18 威胁模型）；防不了拥有整机
  用户权限的攻击者（能改用户 Profile 的人本就高于模型假设）。无 CI/KMS 自动化撤销
  设施，撤销依赖用户对该目录的管理——已在模块文档如实声明。

## 4. 签名算法及依赖

- **Ed25519**（确定性、免 nonce），实现为 **PyNaCl 1.6.2**（libsodium 绑定，pip 安装）。
- **不自研任何密码学原语**；nacl 延迟导入，库缺失时签名能力标记
  `LIBRARY_UNAVAILABLE`，require 模式 fail-closed，绝不静默降级。
- 规范化序列化与 `baseline-content-digest-v1` 同口径（sort_keys + 紧凑分隔符）。

## 5. 密钥管理方式

- `provenance_cli.py`：`keygen / status / rotate / revoke / sign / verify`。
- 生命周期：**ACTIVE**（可签发）/ **RETIRED**（不可签发新对象，历史签名可继续验证）/
  **REVOKED**（默认撤销策略 reject：签名验证一律拒绝；REVOKED 是终态）。
- 轮换 `rotate`：新密钥 ACTIVE + 旧密钥 RETIRED（同文档原子写入，历史签名不受影响）。
- key_id 由公钥确定性派生（`PROVKEY-<sha256(public)[:16]>`），信任根加载强校验唯一性，
  重复即信任根损坏（fail-closed）。
- 授权模型：密钥声明 scopes，签名封套声明 scope，验证时强制
  `scope == SCOPE_FOR_TYPE[object_type]` 且 `scope ∈ key.scopes`。

## 6. Baseline 接入（IMPLEMENTED + TESTED + VERIFIED）

`baseline_lifecycle.use_baseline_trusted()`（新增；1.60 `use_baseline()` 原样保留）：
先执行 1.60 全部语义（结构/审批/登记/摘要），APPROVED_OK 后叠加来源验证。
信任等级四态：`LEGACY_APPROVED`（无签名，allow_legacy 下可用，绝不冒充已验证）/
`CRYPTOGRAPHICALLY_VERIFIED` / `SIGNATURE_REQUIRED`（require 缺签）/
`SIGNATURE_INVALID`（**任何模式都拒绝**——"带病签名"不能当 Legacy 放行）。
签名内审批元数据（approver/approved_at）与登记记录交叉核对（A03）。
`evidence_adapter.baseline_report()` 经签名门禁（`set_signature_gate`）自动走
`use_baseline_trusted`，门禁缺省关闭 = 1.60 语义逐字不变。

## 7. Evidence 接入（IMPLEMENTED + TESTED + VERIFIED）

- `load_verified(..., provenance_policy=)`：`""`（默认，1.58 语义不变）/
  `verify`（诊断）/ `require`（安全模式）。逐 bundle 重算摘要 + 验证 sidecar。
- 签名是**追加**门禁：1.56 Integrity 与 1.57 Artifact Cross-Validation 先于并独立于
  签名验证执行（实测 A2a/A2b：签名通过时 integrity/cross_validation 仍被验证）。
- **封堵 1.56 的哈希重算逃逸路径**：攻击者改内容 + 重算 `payload_sha256` 可骗过
  SHA256 自洽检查，但无法伪造签名 → require 模式 `bundle_rejected`（实测）。
- CLI：`evidence_eval.py --require-signature / --allow-legacy`（互斥）+ `--trust-root`。

## 8. Holdout 接入（IMPLEMENTED + TESTED + VERIFIED）

- `holdout_registry.seal_dataset_signed()`：封存（先 VALIDATED 后 SEALED，遵守 1.60
  状态机）+ 来源签名（绑定 source/封存时间/feature/behavior 特征）。
- 消费时验证（`evidence_eval._verify_holdout_provenance`）：失败细分
  `holdout_signature_missing / holdout_signature_invalid / holdout_signer_untrusted /
  holdout_digest_mismatch / holdout_revoked / holdout_already_consumed`——一律
  NOT_EVALUATED，不伪装成普通缺口；签名验证失败时**不发生** `record_usage`（实测）。
- 1.60 一次性消费语义保持：签名数据集消费后 CONSUMED、重复消费拒绝（实测 C1）。
- 签名内 `binding.source` 与登记来源交叉核对（A12）。

## 9. 密钥轮换和撤销机制

IMPLEMENTED + TESTED（core D1–D4、attacks A13/A14、CLI F1）：见 §5。
撤销信息来源：信任根文件 + `PROVENANCE_REVOCATIONS` 覆盖文件（只允许降级 REVOKED，
不能复活密钥；工作区内文件拒收）。**限制**：无自动化撤销基础设施，撤销时效取决于
用户对该文件的管理（审计 §7 如实声明）。

## 10. 18 项攻击测试逐项结果（`test_provenance_attacks.py`，32 checks 全 PASS）

| 编号 | 场景 | 实测结果 |
| --- | --- | --- |
| A01 | 修改 Baseline 内容 | DIGEST_MISMATCH ✔ |
| A02 | 修改 Baseline 摘要 | DIGEST_MISMATCH（1.60 层拒绝，签名层另绑摘要双保险）✔ |
| A03 | 修改审批者身份 | SIGNATURE_INVALID（签名内审批元数据核对）✔ |
| A04 | 修改审批登记表（全自洽伪造） | SIGNATURE_REQUIRED（无签名不可造）✔ |
| A04b | 未注册密钥自签 | KEY_UNKNOWN ✔ |
| A05 | 未知公钥 ID | KEY_UNKNOWN ✔ |
| A06 | 错误私钥重签 | SIGNATURE_INVALID（Ed25519 验签失败）✔ |
| A07 | Evidence 签名用于 Baseline | SIGNATURE_INVALID（object_type）✔ |
| A08 | 一个 Baseline 签名用于另一个 | SIGNATURE_INVALID（object_id）✔ |
| A09 | 修改 Evidence 内容 | DIGEST_MISMATCH ✔ |
| A10 | 修改 Artifact 摘要集合 | DIGEST_MISMATCH（产物摘要在签名载荷内）✔ |
| A11 | 修改 Holdout 内容 | 拒绝（封存摘要重算失配）✔ |
| A12 | 修改 Holdout 来源 | SIGNATURE_INVALID（来源交叉核对）✔ |
| A13 | 撤销密钥 | KEY_REVOKED（Baseline + Holdout 消费均拒绝）✔ |
| A14 | 已退役密钥签发新对象 | 签发被拒（RETIRED）✔ |
| A15 | 删除签名记录 | require 拒绝；allow_legacy 仅 LEGACY_APPROVED 不冒充 ✔ |
| A16 | **替换项目内公钥（核心）** | 工作区信任根拒收（INSECURE_LOCATION）；env 指入工作区拒收；外部信任根不受工作区伪造影响 ✔ |
| A17 | 缺失外部信任根 | TRUST_ROOT_MISSING fail-closed ✔ |
| A18 | scope 不匹配 | SCOPE_MISMATCH ✔ |

**A16 模拟方式（诚实记录）**：测试模拟的是"信任根路径配置与文件内容"层面的边界
（工作区内信任根文件被拒收、外部根不被工作区数据影响），证明的是**代码层**边界规则；
不声称已证明真实 CI/生产部署安全。

私钥泄露检查（§8.1）K1–K6 全 PASS：仓库无 `.seed` 文件、信任根只含公钥、CLI 输出
不含种子、异常消息不含种子、测试密钥与生产信任根隔离、测试密钥随临时目录销毁。

## 11. Phase 1.56–1.60 回归结果（全部真实执行，Python 3.12.10）

| 套件 | 结果 |
| --- | --- |
| 1.60 `test_baseline_lifecycle`（26）+ `test_trace_bindings`（28）+ `test_holdout_registry`（23）+ `test_cross_binding`（15）+ `test_phase160_e2e`（5，**真实 Godot 新鲜采集**） | **全 PASS** |
| 1.58 `test_evidence_adapter`（52）+ `test_evidence_eval`（20）+ `test_evaluation_runner`（24）+ `test_evaluation_scoring`（28） | **全 PASS** |
| 1.57 `test_evidence_cross_validation`（34）；1.56 `test_behavior_evidence_stage`（54）；比较器 `test_trace_baselines`（100） | **全 PASS** |
| 1.59 `test_mutation_harness`（51）+ `test_mutation_integration`（15） | **全 PASS** |
| `validator/validate.py` | **0 error / 17 warning**（与基线一致） |

**真实 Godot 端到端（Phase 1.61 全链路）**：4 个 Feature（health / collect_pickup /
save_game / openable_door）真实 headless 采集 → 用真实信任根密钥签署 3 个 bundle →
`evidence_eval --require-signature` → E1/E2/E3 全 `VERIFIED_PASS`、exit 0；篡改副本
（重算 integrity 哈希但无法重签）→ `INVALID_EVIDENCE`；真实基线 CLI 验证：
allow-legacy → LEGACY_APPROVED / require → SIGNATURE_REQUIRED（不伪造升级）。

## 12. 实际执行的测试数量

新增 5 套 **142 项**全 PASS（core 57 + baseline 签名 21 + evidence 签名 16 +
holdout 签名 16 + 攻击模拟 32）；回归 **485 项**全 PASS（26+28+23+15+5+52+20+24+28
+34+54+100+51+15），加 validate.py 与真实 Godot E2E。

## 13. 未执行测试和原因

- `run_tests.py` 全量入口未运行（历史记录其受环境删除守卫影响；以受影响套件逐项
  真实执行代替，如上表）。e2e 生成链路（`test_end_to_end_generation.py`，约 29 min）
  未运行——本阶段未触碰生成链路。Godot 侧 `Tests/*.gd` 未改动、未重跑。
- 其余与本阶段改动无交集的历史套件未重复执行（1.57/1.60 均做过分段全量回归）。
- **本段为分段结果，不表述为全量通过。**

## 14. 当前剩余安全风险

1. **执行真实性仍未证明**：签名不证明 Godot 执行过对应行为；采集进程与签名者同权限
   时，"签名证据"的证明力上限 = 采集器诚实。需独立采集器/可信执行环境（DEFERRED）。
2. **信任根管理依赖用户**：`~/.provenance_trust/` 的完整性取决于用户级保护；整机
   管理员攻击者超出模型。无自动化密钥备份/恢复——种子丢失即不可再签（可轮换）。
3. **撤销时效**：撤销文件由用户手工维护，无自动分发。
4. **RETIRED 密钥的历史签名**仍可验证（设计如此）；`signed_at` 是签名者自报时间，
   不用于"签发时密钥是否已退役"的判定（无可信时间源）。
5. 未签名的既有真实数据（4 条 Legacy 基线、历史 Holdout、全部历史 Evidence）保持
   LEGACY_APPROVED——require 模式下它们会被拒绝（预期行为，非漏洞）。

## 15. 能力清单（严格区分状态）

| 能力 | 状态 |
| --- | --- |
| Ed25519 签名/验证（PyNaCl，不自研原语） | **IMPLEMENTED / TESTED / VERIFIED**（真实端到端） |
| 外部信任根（工作区外 + 拒收工作区路径） | **IMPLEMENTED / TESTED / VERIFIED**（本机已真实建立） |
| Baseline 签名接入（use_baseline_trusted + 登记签名） | **IMPLEMENTED / TESTED / VERIFIED** |
| Evidence 签名接入（sidecar + load_verified 追加门禁） | **IMPLEMENTED / TESTED / VERIFIED** |
| Holdout 签名接入（seal_dataset_signed + 消费验证） | **IMPLEMENTED / TESTED / VERIFIED** |
| 密钥生命周期 ACTIVE/RETIRED/REVOKED + 轮换 + 撤销 | **IMPLEMENTED / TESTED** |
| 18 项攻击模拟 + 私钥泄露检查 | **IMPLEMENTED / TESTED**（代码层边界） |
| CLI（provenance_cli + evidence_eval 新参数） | **IMPLEMENTED / TESTED** |
| Legacy 数据兼容（不伪造/不升级） | **IMPLEMENTED / TESTED / VERIFIED**（4 条真实基线实测） |
| 真实 CI Secret / KMS / 自动化撤销基础设施 | **NOT_IMPLEMENTED / DEFERRED**（本环境无 CI；接口已预留：env + 文件） |
| 执行过程真实性证明（可信执行环境/独立采集器） | **NOT_IMPLEMENTED / DEFERRED**（签名明确不覆盖） |
| 逐行为绑定扩到全部 60 行为 | **NOT_IMPLEMENTED**（1.60 遗留，非本阶段范围） |
| 既有真实数据批量签署 | **NOT_TESTED / 有意未做**——历史数据不伪造签名；新批准流程产生的新对象才签署 |

## 16. 验收标准对照（任务书 §13）

- [x] 已完成真实仓库审计（AUDIT.md，8 问逐条回答）
- [x] 已明确外部信任根来源（用户级独立公钥文件，已实际建立）
- [x] 项目工作区无法自行替换可信公钥（A16a/b/c 实测拒收）
- [x] 已实现成熟非对称签名验证（Ed25519/PyNaCl）
- [x] Baseline / Evidence / Holdout 已接入签名验证（各有实测套件 + 真实 E2E）
- [x] 签名绑定对象类型、ID、版本、摘要和用途（封套消息内强制）
- [x] 已实现密钥生命周期管理（ACTIVE/RETIRED/REVOKED + 轮换/撤销）
- [x] 18 项攻击测试全部达到预期结果（32 checks 全 PASS）
- [x] 原有 Artifact Cross-Validation 仍然生效（实测 A2b）
- [x] 原有 Evaluation 状态语义没有被破坏（1.58 六状态不变，回归全过）
- [x] 历史 Legacy 数据没有被伪造升级（C1/C2/C3 实测）
- [x] Phase 1.56–1.60 关键回归已执行并记录（485 项 + 真实 Godot E2E）
- [x] 未提交私钥或其他敏感材料（K1–K6；种子在工作区外）
- [x] 完成报告准确区分已实现与未实现能力（§15）
- [x] 独立信任根验收项：**按"用户管理的独立公钥文件"方案 IMPLEMENTED**（非 NOT_IMPLEMENTED
  ——威胁模型为工作区写权限攻击者，用户级目录在该边界之外；整机攻击者边界如实声明于 §3/§14）

## 17. 工作区变化与保护声明

- 新增：`validator/provenance/`（7 模块 + tests 2 套）、`validator/tests/
  test_baseline_signature.py`、`evaluation/tests/test_evidence_signature.py`、
  `test_holdout_signature.py`、`.ai/context/PHASE_1_61_AUDIT.md` 与本报告。
- 修改（全部加法式）：`baseline_lifecycle.py`（+`use_baseline_trusted`）、
  `holdout_registry.py`（+`seal_dataset_signed`）、`evidence_adapter.py`（+gate/
  `provenance_policy`，默认关）、`evidence_eval.py`（+4 个 CLI 参数与 Holdout 验证块）、
  `check_behavior_evidence.py`（仅跳过 `.sig.json` sidecar）、两份 README。
- 未执行任何 `git reset/checkout/restore/clean/add/commit/push`；未改动 4 条真实基线、
  `approval_registry.json`、`holdout_datasets.json`、绑定库、生产 GDScript、
  其他 Agent 的未提交产物与 `code_library`。
- 实施前后 `git status` 均为 1010 条左右未提交修改（仅新增上述文件），无删除/覆盖。
