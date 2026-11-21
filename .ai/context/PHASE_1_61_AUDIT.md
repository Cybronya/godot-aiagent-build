# Phase 1.61 执行前审计（以当前仓库为准）

审计时间：2026-11-03。审计人：Phase 1.61 执行 Agent。
所有结论均来自当前工作区的真实代码与文件实测，不引用历史报告作为事实来源。

## 1. Git 与工作区事实（实测）

- 分支：`master`；HEAD：`dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`。
- `git status --porcelain` 共 **1010 条**（Phase 1.56–1.60 全部成果均为未提交状态）。
- 结论：一切实现必须叠加在当前工作区之上；禁止任何
  `git reset / checkout / restore / clean`，不提交、不推送。
- 本阶段新增文件将全部局部化在 `.ai/tools/validator/provenance/` 与各 tests 目录。

## 2. 运行环境事实（实测）

- Python：**3.12.10**（全局安装于 `F:\Program Files\Python3.12`，无 venv）。
- pip：25.0.1，**网络可用**（`pip install --dry-run pynacl` 实测可行）。
- 现有密码学依赖：**无**。`cryptography` 未安装、`pynacl` 未安装。
  Python 3.12 标准库**没有** Ed25519 等非对称签名原语（只有 hashlib/hmac/secrets）。
- 测试框架：**无 pytest**。既有测试均为独立脚本（自计数 check/failures，直接
  `python tests/test_xxx.py` 运行）。本阶段沿用同一约定。
- CI / Secret / 外部密钥设施：**不存在**。无 `.github/`、无 CI 配置、无
  requirements.txt、无 KMS / 签名服务 / 证书设施。
- 已有签名 / 信任根实现：**不存在**。全仓 `.ai/tools/**` 无 Ed25519/HMAC/RSA
  代码（grep 实测零命中）；所有完整性均为 SHA256。

## 3. Phase 1.60 真实实现（实测确认）

以下能力真实存在且相互衔接（非纸面声明）：

1. **Baseline 内容完整性**：`validator/baseline_lifecycle.py`
   - `content_digest()`：规范化 JSON（sort_keys + 紧凑分隔符）→ SHA256，方案
     `baseline-content-digest-v1`；摘要排除 `approval` 块与 `scenario_description`。
   - `use_baseline()`：使用时重算摘要 + 登记核对，失败返回
     `DIGEST_MISMATCH / UNAPPROVED / MISSING_REGISTRATION / REVOKED / SUPERSEDED /
     APPROVAL_MISMATCH / INVALID_BASELINE`，绝不放行。
   - 状态机 `DRAFT→PENDING_REVIEW→APPROVED→SUPERSEDED/REVOKED`，跳步被拒。
   - 登记表 `validator/baselines/approval_registry.json`：4 条既有基线以显式迁移
     登记在案（APPROVED + 内容摘要 + 依据），实测摘要与文件内容一致。
2. **Behavior 绑定**：`validator/trace_bindings.py` +
   `validator/bindings/behavior_bindings.json`（6 条 BND-001…006，精确 ID 匹配）。
3. **Holdout 生命周期**：`evaluation/holdout_registry.py` +
   `evaluation/holdout/holdout_datasets.json`；`CREATED→VALIDATED→SEALED→CONSUMED/
   INVALIDATED`；封存摘要 `holdout-dataset-digest-v1`；消费登记 usage_history；
   一次性消费真实生效（E5 二次运行 → `NOT_EVALUATED(holdout_dataset_unusable)`）。
4. **Evaluation 状态模型**：`evidence_adapter.evaluation_status()` 六状态写死
   （VERIFIED_PASS/VERIFIED_FAIL/INVALID_EVIDENCE/INCOMPLETE/EVALUATION_ERROR/
   NOT_EVALUATED）；`load_verified()` 内联 Artifact Cross-Validation（1.57）；
   `baseline_report()` 已做使用时摘要复核。
5. **CLI**：`evidence_eval.py` Mode A/B/C，参数 `--bindings / --holdout-dir /
   --require...`（无任何签名参数）；Holdout 任务经 `holdout_id` 声明走登记复核。

## 4. 只依赖 SHA256 的数据（清单）

| 数据 | 摘要位置 | 保护强度 |
| --- | --- | --- |
| Baseline 评估载荷 | 登记表 `content_digest`（baseline-content-digest-v1） | SHA256，登记表同权限可改 |
| Evidence Bundle | `integrity.payload_sha256`（canonical JSON，排除 integrity） | SHA256，随文件可改 |
| Artifact result.json | bundle 内 `artifact_digests{}`（1.57 交叉验证重算） | SHA256，与 bundle 同边界 |
| Holdout 数据集 | 登记表 `content_digest`（holdout-dataset-digest-v1） | SHA256，登记表同权限可改 |
| Behavior 契约 | binding `contract_version`（SHA256 前 12 位） | SHA256 |
| Trace 协议 | bundle `protocol.sha256` | SHA256 |

**全部摘要的验证者与被验证数据处于同一写权限边界**——改数据可以连同改摘要，
SHA256 只能证明"内容自洽"，不能证明"由谁确认"。

## 5. 自报身份（清单）

| 身份字段 | 位置 | 现状 |
| --- | --- | --- |
| `approver` | 基线文件 approval 块 + 登记表 | 自由文本，无认证（1.60 报告 §16 已声明） |
| `--i-approve` | `e2e/approve_trace_baselines.py` | 无身份认证（审批入口冻结，不改） |
| holdout `source` | 登记表 | 自报文本 |
| `git_head` / `tool.module` | Evidence bundle | 采集器自报 |
| 签发者（Evidence） | 不存在 | Evidence 无任何签发者概念 |

## 6. 同一写权限边界的对象（攻击面）

攻击者拥有项目工作区写权限时可同时改写（实测均在 `F:\Godot_v4.7-stable\game`
之内）：

- `validator/baselines/*.json`（4 条基线本体）
- `validator/baselines/approval_registry.json`（审批登记表）
- `validator/bindings/behavior_bindings.json`（绑定库）
- `evaluation/holdout/holdout_datasets.json`（Holdout 登记表）
- Evidence bundle 与 sidecar 产物（`.ai/tmp/**` 及任意评估输入目录）
- 所有 Python 验证代码本身（`validator/**`、`evaluation/**`）
- 本次若把公钥放进工作区，公钥也会同边界可改 → **不构成信任根**

结论：工作区内任何文件（含任何"公钥文件"）都不能自证可信；信任根必须位于
工作区写权限之外。

## 7. 是否存在可用外部信任根（实测）

- CI Secret：无 CI → 无。
- 现有签名服务 / KMS：无。
- 操作系统受保护配置：Windows 用户 Profile 之外于仓库的目录
  （`%USERPROFILE%\.provenance_trust\`）**在事实上位于攻击边界之外**——
  威胁模型明确为"攻击者拥有**项目工作区**写权限"，而非整机用户权限。
- 结论：**采用"用户管理的独立公钥文件"方案**（任务书 §2.1 允许项）：
  - 信任根文件：`%USERPROFILE%\.provenance_trust\trust_root.json`（工作区外，
    用户手工管理）。
  - 覆盖入口：环境变量 `PROVENANCE_TRUST_ROOT`（指向工作区外路径才被接受）。
  - **硬规则：信任根路径解析后位于项目工作区内 → 拒绝加载（fail-closed）**。
  - 私钥：`%USERPROFILE%\.provenance_trust\keys\<key_id>.seed`，永不入仓、
    永不入报告/日志；测试用密钥一律生成在系统临时目录（工作区外）。
  - 诚实边界：该方案防"工作区写权限攻击者"；防不了"整机管理员攻击者"
    （能改用户 Profile 的人本来就高于本信任模型的假设）——文档如实声明。

## 8. 独立信任根与签名方案（设计结论）

- **算法：Ed25519**（确定性、免随机 nonce、密钥 32B、签名 64B）。
- **库：PyNaCl（libsodium 绑定）**，成熟实现；本阶段不自行实现任何密码学原语。
  依赖缺失时签名能力标记不可用，require 模式 **fail-closed**（不得静默降级）。
- **签名封套（detached）**：对封套（除 `signature` 字段）做规范化 JSON
  （sort_keys + 紧凑分隔符，UTF-8）后 Ed25519 签名。封套字段：
  `schema/schema_version/object_type/object_id/object_version/content_digest/
  digest_scheme/scope/signer_key_id/signature_algorithm/signed_at/binding{}/signature`。
  对象类型/ID/版本/摘要/scope 全部在签名消息内 → 跨对象、跨类型、跨 scope、
  跨版本复用签名必然验证失败。
- **对象类型 ↔ scope**：`baseline←approve_baseline`、
  `evidence_bundle←issue_evidence`、`holdout_dataset←seal_holdout`；
  密钥在信任根中声明授权 scopes，验证时强制核对（授权不足 → 拒绝）。
- **信任根文件**：`schema=provenance_trust_root`，`keys[]`（key_id 唯一、
  public_key、algorithm、subject、scopes、status、created_at）。
- **密钥生命周期**：ACTIVE（可签发）/ RETIRED（不可签发新对象，历史签名可验）/
  REVOKED（撤销，默认策略 reject：验签拒绝；撤销信息来源=信任根文件或
  `PROVENANCE_REVOCATIONS` 指向的工作区外文件——工作区内的自报撤销记录无效）。
- **验证结果词表（fail-closed 区分）**：`SIGNATURE_VALID / SIGNATURE_MISSING /
  SIGNATURE_INVALID / KEY_UNKNOWN / KEY_REVOKED / KEY_RETIRED_SIGN_REFUSED /
  SCOPE_MISMATCH / TRUST_ROOT_MISSING / TRUST_ROOT_UNREADABLE /
  TRUST_ROOT_INSECURE_LOCATION / ALGORITHM_MISMATCH / LIBRARY_UNAVAILABLE /
  DIGEST_MISMATCH`。

## 9. 接入点与兼容策略（最小加法）

| 接入点 | 方式 | 兼容承诺 |
| --- | --- | --- |
| Baseline | 登记表条目新增可选 `provenance_signature` 封套；`baseline_lifecycle` 新增 `use_baseline_trusted()`（旧 `use_baseline()` 不动） | 4 条 Legacy 基线 → `LEGACY_APPROVED`，不伪造、不自动升级 |
| Evidence | sidecar `<bundle>.sig.json`（bundle 文件零修改）；`load_verified()` 新增可选 `provenance_policy` 参数（默认关闭=纯诊断） | 1.58 六状态语义不变；无签名 bundle 默认行为不变 |
| Holdout | 登记记录新增可选 `provenance_signature` 封套；`evidence_eval` 消费时验签，失败原因细分为 `holdout_signature_*` | 一次性消费语义不变；`NOT_EVALUATED(holdout_dataset_unusable)` 保留 |
| CLI | `evidence_eval.py` 新增 `--require-signature` / `--allow-legacy`（默认 allow-legacy）；新 CLI `provenance_cli.py`（keygen/rotate/revoke/status/sign/verify） | 旧参数行为逐字不变 |

**信任等级（不得混淆）**：`LEGACY_APPROVED`（历史登记，无签名）、
`CRYPTOGRAPHICALLY_VERIFIED`（外部信任根验签通过）、`SIGNATURE_REQUIRED`
（require 模式下缺签名）、`SIGNATURE_INVALID`（签名存在但无效 → 一律拒绝，
"存在但坏"比"没有"更严重，绝不允许带病签名对象被当作 Legacy 放行）。

**签名证明什么（边界声明，写入文档与报告）**：
签名 = "持有某外部信任根所列私钥的主体，签署了摘要为 D 的对象 O（scope S，时间 T）"。
不证明：Godot 真的执行过对应行为；采集进程未被篡改；执行环境可信。
Evidence 签名者若与采集器同权限运行，其证明力等同采集器自报——此边界如实记录。
验证链保持：Evidence Integrity → Artifact Cross-Validation → Provenance Signature →
Trusted Signer Authorization → Evaluation（签名门禁是**追加**环节，不替代前两级）。

## 10. 需要新增的接口与测试

- 模块：`validator/provenance/{__init__,signature_schema,signing,verification,
  trust_store,key_metadata,provenance_cli}.py`。
- 测试：`validator/provenance/tests/test_provenance_core.py`（封套/规范化/信任根/
  生命周期/CLI）、`test_provenance_attacks.py`（A01–A18 + 私钥泄露检查）、
  `validator/tests/test_baseline_signature.py`、`evaluation/tests/test_evidence_signature.py`、
  `evaluation/tests/test_holdout_signature.py`，全部在隔离临时目录执行。
- 回归：1.60 四套（baseline_lifecycle/trace_bindings/holdout_registry/cross_binding）、
  1.58 两套（adapter/eval）、1.59 mutation 两套、1.56/1.57 stage 套件。

## 11. 历史数据兼容

- 4 条迁移 APPROVED 基线：保持无签名状态（LEGACY_APPROVED）；不为历史数据
  伪造签名，不自动升级为 CRYPTOGRAPHICALLY_VERIFIED。
- 既有 Holdout v2（已 CONSUMED）：同样保持 Legacy。
- 旧 Evidence（无 sidecar）：默认模式纯诊断；require 模式下缺签名 → 拒绝。
- 不改写任何历史 JSON 内容字节。

## 12. 审计问题逐条回答（任务书 §1）

1. **1.60 已实现**：内容完整性（SHA256+使用时复核）、审批状态机+登记表、
   绑定层、Holdout 生命周期、Evaluation 集成 —— 见 §3。
2. **仅依赖 SHA256**：Baseline/Evidence/Artifact/Holdout/契约/协议 —— 见 §4。
3. **自报身份**：approver、--i-approve、holdout source、git_head —— 见 §5。
4. **同边界对象**：基线、两登记表、绑定库、Evidence、验证代码本身 —— 见 §6。
5. **外部信任根**：现状无；方案=用户级独立公钥文件（工作区外）+ 环境变量覆盖，
   工作区内路径一律拒收 —— 见 §7。
6. **实现方式**：Ed25519（PyNaCl/libslodium 绑定）+ detached 规范化封套签名；
   不自研密码学 —— 见 §8。
7. **新增接口与测试**：provenance 包 7 模块 + 5 个测试套件（含 18 攻击场景）——
   见 §10。
8. **历史兼容**：Legacy 显式降级识别、无签名不阻断（默认）、require 模式
   fail-closed、不改历史字节 —— 见 §11。
