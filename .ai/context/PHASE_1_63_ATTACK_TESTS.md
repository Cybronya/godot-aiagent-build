# Phase 1.63 攻击测试报告

本阶段新增攻击面集中在 **Binding 候选/审批/晋升/门禁** 与 **覆盖矩阵诚实性**。
全部实测通过；1.61（A01–A18）与 1.62（E01–E30）既有攻击套件全部重跑通过（142+67 项）。

## 1. Binding 候选与审批攻击（`test_binding_candidates.py`，26 项）

| 编号 | 攻击 | 预期 | 结果 |
| --- | --- | --- | --- |
| B1 | DRAFT 直接跳到 APPROVED | BindingCandidateError | ✅ 拒绝 |
| B3 | 候选内容在生成后被篡改（digest 伪装成新值） | 审批拒绝并退回 DRAFT | ✅ |
| B4 | 契约在候选生成后漂移（contract_version 不一致） | 审批拒绝并退回 DRAFT | ✅ |
| B6b | BLOCKED_MISSING_EXPECTED 候选尝试审批 | 永不可批 | ✅ |
| C1 | 未审批候选直接 promote | 拒绝 | ✅ |
| C2 | 审批后候选内容被改动再 promote（重算摘要 ≠ 登记摘要） | 拒绝 | ✅ |
| C4 | 同 (Feature,Behavior) 旧绑定在晋升后仍存活 | 旧绑定 SUPERSEDED，不双活 | ✅ |
| C6 | 已批准绑定被 REVOKED 后继续使用 | gate = BINDING_REVOKED | ✅ |
| C7 | 契约版本变化后使用旧绑定 | gate = CONTRACT_MISMATCH | ✅ |
| C8 | 子串 Feature/Behavior 误匹配（collect vs collect_pickup） | gate = NO_BINDING | ✅ |
| C9 | BLOCKED 候选伪装成可用 | gate = BINDING_INVALID（无虚假 APPROVED） | ✅ |
| B6 | 审批记录签名验证 | SIGNATURE_VALID（本机真实信任根实测） | ✅ |

补充（生产数据实测）：审批记录签名批量验证 59/59 有效（6 条迁移 + 53 条新批 + 1 条重绑）。

## 2. 覆盖矩阵诚实性攻击（`test_coverage_matrix.py`，15 项）

| 编号 | 攻击 | 预期 | 结果 |
| --- | --- | --- | --- |
| M4 | 无 sidecar 的 bundle 伪装成已签名 | Signature = NO_SIGNATURE（legacy 永不算签名验证） | ✅ |
| M5 | bundle 载荷被篡改（integrity 失配） | EVIDENCE_INVALID | ✅ |
| M6 | INVALID mutation 混入 KILLED 统计 | MUTATION_INVALID，summary 分开计数 | ✅ |
| M7c | 污染 holdout 伪装可用 | HOLDOUT_INVALID | ✅ |
| M9b | 缺评估报告的 Behavior 伪装通过 | NOT_EVALUATED（无虚假 PASS） | ✅ |
| M3 | 全维度缺数据 | 明确 NO_* 状态 + null digest/run_id | ✅ |
| M8 | --strict 有缺口 | 退出码 2 | ✅ 实测 |

## 3. 既有攻击套件重跑（全部通过）

- Phase 1.61 provenance attacks：A01–A18（32 checks）——工作区内伪造信任根/签名、密钥撤销、scope 跨用等。
- Phase 1.62 execution attacks：E01–E30（31 checks）——Manifest/Attestation 篡改、Run 绑定错配、路径越界等。
- Phase 1.61 各签名门禁套件（baseline/evidence/holdout signature）：53 checks。

## 4. 残余攻击面（如实声明）

1. **同权限攻击者**可同时改写候选文件、登记表与信任根公钥文件（信任根在用户目录，非硬件根）——签名只提供「签名后不可无感篡改」，不提供独立身份。升级路径：外部 KMS/CI 签发。
2. `user://` 隔离目录的清理按 basename==tag 守卫，可防误删共享目录；但攻击者若能在采集进程同权限运行，可伪造任意 tag 内容——这属于 LOCAL_ISOLATED 边界内，已在 1.62 声明。
3. 契约本身被同权限修改会连带改变 contract_version（内容哈希）→ Binding CONTRACT_MISMATCH 会暴露，但「契约语义被改坏但格式合法」仍需人工评审兜底（expected 的生成永远复制契约，不判断契约好坏）。
