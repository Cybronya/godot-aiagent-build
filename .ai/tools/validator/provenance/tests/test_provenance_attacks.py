#!/usr/bin/env python3
"""攻击模拟与安全验证（Phase 1.61，任务书 §8：A01–A18 + 私钥泄露检查）。

**本阶段最重要的不是正常签名成功，而是证明攻击者不能伪造信任。**

隔离方式（任务书 §8 明确要求不在真实工作区执行破坏性攻击）：

    - 模拟"项目工作区"= 系统临时目录下的 workspace/（含基线+登记表+证据+Holdout）；
    - "外部信任根" = 系统临时目录下的 external/（workspace 之外，攻击边界之外）；
    - 攻击者的全部动作只发生在 workspace/ 副本内（模拟工作区写权限）；
    - 攻击者**没有** external/ 的写权限（模拟信任根边界）；
    - 真实仓库文件零改动（本测试只读真实基线做 Legacy 对照）。

诚实边界（任务书 §8）：本测试证明的是**代码层**的拒绝行为与边界规则；
它不证明真实 CI/生产环境的部署安全（那取决于信任根文件的实际管理）。

覆盖矩阵（预期结果全部为"拒绝 / 不放行 / 不升级"）：

    A01 修改 Baseline 内容           -> DIGEST_MISMATCH（1.60 层）
    A02 修改 Baseline 摘要           -> DIGEST_MISMATCH（登记摘要失配）
    A03 修改审批者身份               -> SIGNATURE_INVALID（签名内元数据核对）
    A04 修改审批登记表               -> 无法产生有效可信签名（require 拒绝）
    A05 使用未知公钥 ID              -> KEY_UNKNOWN
    A06 使用错误私钥重新签名         -> SIGNATURE_INVALID
    A07 Evidence 签名用于 Baseline   -> SIGNATURE_INVALID（object_type）
    A08 一个 Baseline 签名用于另一个 -> SIGNATURE_INVALID（object_id）
    A09 修改 Evidence 内容           -> DIGEST_MISMATCH
    A10 修改 Artifact 摘要集合       -> DIGEST_MISMATCH（产物摘要在签名载荷内）
    A11 修改 Holdout 内容            -> 拒绝（1.60 摘要层）
    A12 修改 Holdout 来源            -> SIGNATURE_INVALID（来源交叉核对）
    A13 使用撤销密钥                 -> KEY_REVOKED
    A14 使用已退役密钥签发新对象     -> 签发被拒
    A15 删除签名记录                 -> require 拒绝（不静默通过）
    A16 替换项目内公钥               -> 不能改变外部信任根（核心测试）
    A17 缺失外部信任根               -> TRUST_ROOT_MISSING fail-closed
    A18 签名用途 scope 不匹配        -> SCOPE_MISMATCH

私钥泄露检查（任务书 §8.1）：
    K1 仓库内不存在私钥文件/种子
    K2 信任根文件只含公钥（无种子字段）
    K3 CLI 输出/日志不含种子内容
    K4 异常消息不含种子内容
    K5 测试密钥与生产信任根隔离
    K6 测试结束后无残留临时密钥

用法：python .ai/tools/validator/provenance/tests/test_provenance_attacks.py
"""

from __future__ import annotations

import base64
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
PROVENANCE_DIR = os.path.dirname(_HERE)
VALIDATOR_DIR = os.path.dirname(PROVENANCE_DIR)
TOOLS_DIR = os.path.dirname(VALIDATOR_DIR)
EVAL_DIR = os.path.join(TOOLS_DIR, "evaluation")
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
for _path in (VALIDATOR_DIR, EVAL_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import baseline_lifecycle as bl                               # noqa: E402
import evidence_eval                                          # noqa: E402
import holdout_registry as hr                                 # noqa: E402
from provenance import signing, verification                  # noqa: E402
from provenance.trust_store import (ENV_TRUST_ROOT, STATUS_ACTIVE,  # noqa: E402
                                    STATUS_RETIRED, STATUS_REVOKED,
                                    TrustStore, is_inside_path)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_checks = 0
_failures: list = []


def ok(label: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: %s" % label)
    else:
        _failures.append(label)
        print("FAIL: %s  %s" % (label, detail[:300]))


_TMP_ROOT = tempfile.mkdtemp(prefix="p161-attacks-")
WORKSPACE = os.path.join(_TMP_ROOT, "workspace")       # 攻击者写权限范围
EXTERNAL = os.path.join(_TMP_ROOT, "external")         # 攻击者写权限之外
os.makedirs(WORKSPACE, exist_ok=True)
os.makedirs(EXTERNAL, exist_ok=True)
TRUST_ROOT = os.path.join(EXTERNAL, "trust_root.json")

_STATE: dict = {}


def store(trust_root: str = TRUST_ROOT) -> TrustStore:
    return TrustStore(trust_root, project_root=WORKSPACE)


def setup() -> None:
    """构建一个完整的模拟可信状态：基线 + 证据 + Holdout，全部有效签名。"""
    trust = store()
    signer = signing.generate_and_register(
        subject="release-line", scopes=["approve_baseline", "issue_evidence",
                                        "seal_holdout"],
        trust_store=trust, project_root=WORKSPACE)
    attacker = signing.generate_and_register(
        subject="attacker-registered-key", scopes=["approve_baseline"],
        trust_store=trust, project_root=WORKSPACE)
    _STATE["signer"] = signer
    _STATE["attacker"] = attacker
    # ---- Baseline + 登记 + 签名 ----
    document = {
        "baseline_schema_version": 1, "baseline_version": 3,
        "scenario_id": "attack_scenario", "trace_schema_version": 1,
        "approved_behavior_version": 7,
        "comparison_policy": {"strict_fields": ["type", "index"]},
        "events": [{"type": "orchestration_started", "index": 0,
                    "data": {"mode": "waves"}}],
        "expected_final_state": {"state": "completed"},
        "coverage": {"chain": "started -> victory"},
        "approval": {"status": "approved", "approver": "release-manager",
                     "approved_at": "2026-11-03T00:00:00Z",
                     "candidate_fingerprint": "0" * 16},
    }
    registry_path = os.path.join(WORKSPACE, "approval_registry.json")
    digest = bl.content_digest(document)["digest"]
    bl.register("attack_scenario", "3", bl.APPROVED, digest=digest,
                approver="release-manager", approved_at="2026-11-03T00:00:00Z",
                basis="attack-sim setup", registry_path=registry_path)
    envelope = signing.sign_object(
        object_type="baseline", object_id="attack_scenario", object_version="3",
        content_digest=digest, digest_scheme=bl.DIGEST_SCHEME,
        key_id=signer["key_id"], trust_store=trust, project_root=WORKSPACE,
        binding={"approver": "release-manager",
                 "approved_at": "2026-11-03T00:00:00Z"})
    registry = json.load(open(registry_path, encoding="utf-8"))
    registry["registrations"][0]["provenance_signature"] = envelope
    with open(registry_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(registry, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    _STATE["baseline"] = document
    _STATE["baseline_registry"] = registry_path
    _STATE["baseline_digest"] = digest
    # ---- Evidence bundle + sidecar（用真实的 bundle_digest 口径）----
    bundle = {"schema": "feature_behavior_evidence_bundle", "schema_version": 1,
              "bundle_id": "attack-bundle", "generated_at": "2026-11-03T00:00:00Z",
              "git_head": "test-head",
              "tool": {"module": "feature_behavior_evidence", "module_version": 1},
              "protocol": {"protocol_version": 2, "sha256": "1" * 64},
              "evidence_level": "L4", "summary": {},
              "features": [{"feature": "openable_door", "evidence_level": "L4",
                            "behaviors": [{"feature": "openable_door",
                                           "behavior": "open",
                                           "run_id": "openable_door-open",
                                           "artifact_digests": {
                                               "openable_door-open-r1": {
                                                   "result": "2" * 64}}}]}],
              }
    payload = {key: value for key, value in bundle.items() if key != "integrity"}
    bundle["integrity"] = {"algorithm": "sha256",
                           "payload_sha256": bl.content_digest(
                               {"payload": payload})["digest"]}
    evidence_dir = os.path.join(WORKSPACE, "bundles")
    os.makedirs(evidence_dir, exist_ok=True)
    bundle_path = os.path.join(evidence_dir, "attack-bundle.json")
    with open(bundle_path, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, indent=2)
    bundle_digest = verification.recompute_evidence_digest(bundle)
    evidence_envelope = signing.sign_object(
        object_type="evidence_bundle", object_id="attack-bundle",
        object_version="1", content_digest=bundle_digest,
        digest_scheme="evidence-bundle-digest-v1", key_id=signer["key_id"],
        trust_store=trust, project_root=WORKSPACE, binding={})
    verification.write_sidecar(bundle_path, evidence_envelope)
    _STATE["bundle_path"] = bundle_path
    _STATE["evidence_envelope"] = evidence_envelope
    # ---- Holdout + 封存签名 ----
    holdout_registry_path = os.path.join(WORKSPACE, "holdout_datasets.json")
    hr.create_dataset("SIG-ATTACK", "1", source="attack-sim independent batch",
                      feature_ids=["openable_door"], behavior_ids=["open"],
                      registry_path=holdout_registry_path)
    holdout_files = []
    for index in range(2):
        path = os.path.join(WORKSPACE, "holdout-file%d.json" % index)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"run": index}, handle)
        holdout_files.append(path)
    hr.seal_dataset_signed("SIG-ATTACK", "1", evidence_paths=holdout_files,
                           key_id=signer["key_id"], trust_store=trust,
                           project_root=WORKSPACE,
                           registry_path=holdout_registry_path)
    _STATE["holdout_registry"] = holdout_registry_path
    _STATE["holdout_files"] = holdout_files


def verify_baseline(document: dict, registry_path: str, policy="require_signature",
                    trust_root: str = TRUST_ROOT) -> dict:
    return bl.use_baseline_trusted(document, registry_path=registry_path,
                                   trust_store=store(trust_root),
                                   signature_policy=policy)


def verify_holdout(entry: dict, policy="require_signature",
                   trust_root: str = TRUST_ROOT) -> dict:
    return evidence_eval._verify_holdout_provenance(
        entry, {"id": "E5"}, policy, {"active": True},
        trust_root_path=trust_root)


def verify_evidence(bundle_path: str, policy="require_signature",
                    trust_root: str = TRUST_ROOT) -> dict:
    with open(bundle_path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    return verification.verify_evidence_bundle(
        bundle_path, document, trust_store=store(trust_root),
        signature_policy=policy)


def write_json(path: str, document) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    setup()
    baseline = _STATE["baseline"]
    registry_path = _STATE["baseline_registry"]

    # 基准：全部对象当前可信
    ok("S0 基准：签名基线可信",
       verify_baseline(baseline, registry_path)["status"] == "APPROVED_OK"
       and verify_baseline(baseline, registry_path)["provenance_trust"]
       == "CRYPTOGRAPHICALLY_VERIFIED")
    ok("S0 基准：签名证据可信",
       verify_evidence(_STATE["bundle_path"])["usable"])
    ok("S0 基准：签名 Holdout 可信",
       verify_holdout(hr.find_dataset("SIG-ATTACK", "1",
                                      registry_path=_STATE["holdout_registry"]))["usable"])

    # ---------------------------------------------------------------- A01
    tampered = copy.deepcopy(baseline)
    tampered["events"][0]["data"]["mode"] = "attacker-mode"
    result = verify_baseline(tampered, registry_path)
    ok("A01 修改 Baseline 内容 -> 签名验证失败（DIGEST_MISMATCH）",
       result["status"] == "DIGEST_MISMATCH", str(result["status"]))

    # ---------------------------------------------------------------- A02
    registry = read_json(registry_path)
    registry["registrations"][0]["content_digest"] = "e" * 64
    a02_path = os.path.join(WORKSPACE, "registry-a02.json")
    write_json(a02_path, registry)
    result = verify_baseline(baseline, a02_path)
    ok("A02 修改 Baseline 摘要 -> 签名验证失败（摘要失配）",
       result["status"] in ("DIGEST_MISMATCH", "SIGNATURE_INVALID"),
       str(result["status"]))

    # ---------------------------------------------------------------- A03
    registry = read_json(registry_path)
    registry["registrations"][0]["approver"] = "attacker"
    a03_path = os.path.join(WORKSPACE, "registry-a03.json")
    write_json(a03_path, registry)
    forged_approval = copy.deepcopy(baseline)
    forged_approval["approval"]["approver"] = "attacker"
    result = verify_baseline(forged_approval, a03_path)
    ok("A03 修改审批者身份 -> 签名验证失败",
       result["status"] == "SIGNATURE_INVALID", str(result["status"]))

    # ---------------------------------------------------------------- A04
    # 攻击者重写登记表（抹签名 + 改审批者 + 换 digest）并把文件内审批块同步改齐
    # ——1.60 层全部自洽，但攻击者**没有外部信任根的密钥注册权限**（威胁模型：
    # 攻击者只有工作区写权限），无法产生有效可信签名。
    registry = read_json(registry_path)
    entry = registry["registrations"][0]
    entry.pop("provenance_signature", None)      # 攻击者抹掉签名
    entry["approver"] = "attacker"               # 改审批者
    entry["content_digest"] = bl.content_digest(tampered)["digest"]  # 配合改后的内容
    a04_path = os.path.join(WORKSPACE, "registry-a04.json")
    write_json(a04_path, registry)
    fully_forged = copy.deepcopy(tampered)       # 文件内审批也同步改齐
    fully_forged["approval"]["approver"] = "attacker"
    result = verify_baseline(fully_forged, a04_path)
    ok("A04 修改审批登记表（全自洽）-> 无法产生有效可信签名（require 拒绝）",
       result["status"] in ("SIGNATURE_REQUIRED", "SIGNATURE_INVALID"),
       str(result["status"]))
    # A04b：攻击者尝试用**自己生成的**（未在外部信任根注册的）密钥重签
    # —— 签发在密钥核对处被直接拒绝；即使绕过签发流程手工构造签名，
    # 验证侧也会以 KEY_UNKNOWN 拒绝（A05 已覆盖验证侧）。
    import nacl.signing                                          # noqa: PLC0415
    attacker_signing_key = nacl.signing.SigningKey.generate()
    unregistered_key_id = "PROVKEY-%s" % "attacker-owns-this-key"[:16]
    attacker_env = signing.build_envelope(
        object_type="baseline", object_id="attack_scenario", object_version="3",
        content_digest=bl.content_digest(tampered)["digest"],
        digest_scheme=bl.DIGEST_SCHEME,
        signer_key_id=unregistered_key_id,
        binding={"approver": "attacker", "approved_at": "2026-11-03T00:00:00Z"})
    attacker_env["signature"] = base64.b64encode(
        attacker_signing_key.sign(json.dumps(
            {k: v for k, v in attacker_env.items() if k != "signature"},
            sort_keys=True, ensure_ascii=False,
            separators=(",", ":")).encode("utf-8")).signature).decode("ascii")
    registry = read_json(a04_path)
    registry["registrations"][0]["provenance_signature"] = attacker_env
    write_json(a04_path, registry)
    result = verify_baseline(fully_forged, a04_path)
    ok("A04b 攻击者用未注册密钥自签 -> KEY_UNKNOWN 拒绝（审批主体不可信）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "KEY_UNKNOWN",
       str(result["status"]))

    # ---------------------------------------------------------------- A05
    registry = read_json(registry_path)
    registry["registrations"][0]["provenance_signature"]["signer_key_id"] = \
        "PROVKEY-not-in-root"
    a05_path = os.path.join(WORKSPACE, "registry-a05.json")
    write_json(a05_path, registry)
    result = verify_baseline(baseline, a05_path)
    ok("A05 使用未知公钥 ID -> 拒绝（KEY_UNKNOWN）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "KEY_UNKNOWN",
       str(result["status"]))

    # ---------------------------------------------------------------- A06
    import nacl.signing                                          # noqa: PLC0415
    attacker_key = nacl.signing.SigningKey.generate()
    envelope = read_json(registry_path)["registrations"][0]["provenance_signature"]
    forged = dict(envelope)
    message = json.dumps({k: v for k, v in forged.items() if k != "signature"},
                         sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    forged["signature"] = base64.b64encode(
        attacker_key.sign(message).signature).decode("ascii")
    registry = read_json(registry_path)
    registry["registrations"][0]["provenance_signature"] = forged
    a06_path = os.path.join(WORKSPACE, "registry-a06.json")
    write_json(a06_path, registry)
    result = verify_baseline(baseline, a06_path)
    ok("A06 使用错误私钥重新签名 -> 拒绝（SIGNATURE_INVALID）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "SIGNATURE_INVALID",
       str(result["status"]))

    # ---------------------------------------------------------------- A07
    evidence_env = dict(_STATE["evidence_envelope"])
    result = verification.evaluate_signature(
        evidence_env, object_type="baseline", object_id="attack_scenario",
        object_version="3", expected_digest=_STATE["baseline_digest"],
        trust_store=store(), signature_policy="require_signature")
    ok("A07 将 Evidence 签名用于 Baseline -> 拒绝",
       not result["usable"]
       and result["verification"]["status"] == "SIGNATURE_INVALID",
       str(result["verification"]["status"]))

    # ---------------------------------------------------------------- A08
    other = copy.deepcopy(baseline)
    other["scenario_id"] = "another_scenario"
    other_digest = bl.content_digest(other)["digest"]
    result = verification.evaluate_signature(
        read_json(registry_path)["registrations"][0]["provenance_signature"],
        object_type="baseline", object_id="another_scenario",
        object_version="3", expected_digest=other_digest,
        trust_store=store(), signature_policy="require_signature")
    ok("A08 一个 Baseline 的签名用于另一个 Baseline -> 拒绝",
       not result["usable"]
       and result["verification"]["status"] == "SIGNATURE_INVALID",
       str(result["verification"]["status"]))

    # ---------------------------------------------------------------- A09
    with open(_STATE["bundle_path"], "r", encoding="utf-8") as handle:
        bundle = json.load(handle)
    tampered_bundle = copy.deepcopy(bundle)
    tampered_bundle["features"][0]["behaviors"][0]["artifact_digests"] = {}
    tampered_path = os.path.join(WORKSPACE, "bundles", "attack-bundle-tampered.json")
    write_json(tampered_path, tampered_bundle)
    # 保留原 sidecar？不复制 —— 无签名 + require 也拒绝；先测带原签名的副本。
    shutil.copy(_STATE["bundle_path"] + ".sig.json", tampered_path + ".sig.json")
    result = verify_evidence(tampered_path)
    ok("A09 修改 Evidence 内容 -> 拒绝（签名绑定原始摘要）",
       not result["usable"]
       and result["verification"]["status"] in ("DIGEST_MISMATCH",
                                                "SIGNATURE_INVALID"),
       str(result["verification"]["status"]))

    # ---------------------------------------------------------------- A10
    tampered_bundle2 = copy.deepcopy(bundle)
    tampered_bundle2["features"][0]["behaviors"][0]["artifact_digests"] = {
        "openable_door-open-r1": {"result": "f" * 64}}
    tampered_path2 = os.path.join(WORKSPACE, "bundles",
                                  "attack-bundle-artifacts.json")
    write_json(tampered_path2, tampered_bundle2)
    shutil.copy(_STATE["bundle_path"] + ".sig.json", tampered_path2 + ".sig.json")
    result = verify_evidence(tampered_path2)
    ok("A10 修改 Artifact 摘要集合 -> 拒绝（产物摘要在签名载荷内）",
       not result["usable"]
       and result["verification"]["status"] in ("DIGEST_MISMATCH",
                                                "SIGNATURE_INVALID"),
       str(result["verification"]["status"]))

    # ---------------------------------------------------------------- A11
    holdout_files = _STATE["holdout_files"]
    with open(holdout_files[0], "w", encoding="utf-8") as handle:
        json.dump({"run": 0, "tampered": True}, handle)
    entry = hr.find_dataset("SIG-ATTACK", "1",
                            registry_path=_STATE["holdout_registry"])
    usable = hr.check_usable(entry, evidence_paths=holdout_files)
    ok("A11 修改 Holdout 内容 -> 拒绝（封存摘要重算失配）",
       not usable["usable"], str(usable))

    # ---------------------------------------------------------------- A12
    registry_doc = read_json(_STATE["holdout_registry"])
    for record in registry_doc["datasets"]:
        record["source"] = "attacker-claimed-source"
    a12_path = os.path.join(WORKSPACE, "holdout-a12.json")
    write_json(a12_path, registry_doc)
    entry = hr.find_dataset("SIG-ATTACK", "1", registry_path=a12_path)
    block = verify_holdout(entry)
    ok("A12 修改 Holdout 来源 -> 拒绝（签名绑定来源）",
       not block["usable"] and block["reason"] == "holdout_signature_invalid",
       str(block))

    # ---------------------------------------------------------------- A13
    trust = store()
    trust.set_key_status(_STATE["signer"]["key_id"], STATUS_REVOKED,
                         reason="attack-sim")
    result = verify_baseline(baseline, registry_path)
    ok("A13 使用撤销密钥 -> 按撤销策略拒绝（KEY_REVOKED）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "KEY_REVOKED",
       str(result["status"]))
    block = verify_holdout(hr.find_dataset("SIG-ATTACK", "1",
                                           registry_path=_STATE["holdout_registry"]))
    ok("A13b Holdout 消费同样拒绝撤销密钥",
       not block["usable"] and block["reason"] == "holdout_revoked", str(block))

    # ---------------------------------------------------------------- A14
    trust2 = TrustStore(os.path.join(EXTERNAL, "t2", "trust_root.json"),
                        project_root=WORKSPACE)
    retired = signing.generate_and_register(subject="to-retire",
                                            scopes=["approve_baseline"],
                                            trust_store=trust2,
                                            project_root=WORKSPACE)
    fresh = signing.generate_seed_hex()
    trust2.rotate(signing.seed_to_public_b64(fresh), new_subject="successor",
                  new_scopes=["approve_baseline"], retiring_key_id=retired["key_id"])
    try:
        signing.sign_object(
            object_type="baseline", object_id="new-baseline", object_version="1",
            content_digest="a" * 64, digest_scheme=bl.DIGEST_SCHEME,
            key_id=retired["key_id"], trust_store=trust2, project_root=WORKSPACE)
        ok("A14 使用已退役密钥签发新对象 -> 拒绝", False, "signing succeeded")
    except Exception as exc:                                  # noqa: BLE001
        ok("A14 使用已退役密钥签发新对象 -> 拒绝", "RETIRED" in str(exc),
           str(exc)[:120])

    # ---------------------------------------------------------------- A15
    registry = read_json(registry_path)
    registry["registrations"][0].pop("provenance_signature", None)
    a15_path = os.path.join(WORKSPACE, "registry-a15.json")
    write_json(a15_path, registry)
    result = verify_baseline(baseline, a15_path, policy="require_signature")
    ok("A15 删除签名记录 -> 不得静默通过（require 拒绝）",
       result["status"] == "SIGNATURE_REQUIRED", str(result["status"]))
    result = verify_baseline(baseline, a15_path, policy="allow_legacy")
    ok("A15b 删除签名记录 -> allow_legacy 下仅 LEGACY_APPROVED（不冒充已验证）",
       result["status"] == "APPROVED_OK"
       and result["provenance_trust"] == "LEGACY_APPROVED",
       str(result.get("provenance_trust")))

    # ---------------------------------------------------------------- A16（核心）
    # 攻击者在工作区内放置伪造信任根 + 把信任根环境变量指进去
    fake_root = os.path.join(WORKSPACE, "trust_root.json")
    write_json(fake_root, {"schema": "provenance_trust_root", "schema_version": 1,
                           "keys": [{"key_id": _STATE["signer"]["key_id"],
                                     "public_key": base64.b64encode(
                                         b"attacker-controlled-key-bytes-32").decode(),
                                     "algorithm": "Ed25519",
                                     "subject": "attacker",
                                     "scopes": ["approve_baseline",
                                                "issue_evidence", "seal_holdout"],
                                     "status": "ACTIVE",
                                     "created_at": "2026-11-03"}]})
    # (a) 显式把信任根配置指进工作区 -> 拒收
    inside_store = TrustStore(fake_root, project_root=WORKSPACE)
    loaded = inside_store.load()
    ok("A16a 工作区内信任根拒收（TRUST_ROOT_INSECURE_LOCATION）",
       not loaded["ok"]
       and loaded["status"] == "TRUST_ROOT_INSECURE_LOCATION",
       str(loaded["status"]))
    os.environ[ENV_TRUST_ROOT] = fake_root
    try:
        env_store = TrustStore(project_root=WORKSPACE)
        loaded = env_store.load()
        ok("A16b 环境变量指向工作区信任根 -> 拒收",
           not loaded["ok"]
           and loaded["status"] == "TRUST_ROOT_INSECURE_LOCATION",
           str(loaded["status"]))
    finally:
        del os.environ[ENV_TRUST_ROOT]
    # (c) 外部信任根不受影响：伪造的工作区信任根 + 伪造签名仍然被真根拒绝
    result = verify_baseline(baseline, registry_path, policy="require_signature")
    # 注：signer 已在 A13 被撤销 —— 这里额外用一个未撤销的受信密钥重新签发
    # 以隔离 A16 与 A13 的效果。
    fresh_signer = signing.generate_and_register(
        subject="release-line-2", scopes=["approve_baseline", "issue_evidence",
                                          "seal_holdout"],
        trust_store=store(), project_root=WORKSPACE)
    fresh_env = signing.sign_object(
        object_type="baseline", object_id="attack_scenario", object_version="3",
        content_digest=_STATE["baseline_digest"], digest_scheme=bl.DIGEST_SCHEME,
        key_id=fresh_signer["key_id"], trust_store=store(),
        project_root=WORKSPACE,
        binding={"approver": "release-manager", "approved_at": "2026-11-03T00:00:00Z"})
    registry = read_json(registry_path)
    registry["registrations"][0]["provenance_signature"] = fresh_env
    write_json(registry_path, registry)
    ok("A16c 外部信任根不受工作区内伪造公钥影响（签名仍按外部根验证）",
       verify_baseline(baseline, registry_path)["status"] == "APPROVED_OK")

    # ---------------------------------------------------------------- A17
    missing = TrustStore(os.path.join(EXTERNAL, "absent.json"),
                         project_root=WORKSPACE)
    result = bl.use_baseline_trusted(baseline, registry_path=registry_path,
                                     trust_store=missing,
                                     signature_policy="require_signature")
    ok("A17 缺失外部信任根 -> fail-closed（TRUST_ROOT_MISSING）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "TRUST_ROOT_MISSING",
       str(result["status"]))

    # ---------------------------------------------------------------- A18
    bad_scope = dict(read_json(registry_path)["registrations"][0]["provenance_signature"])
    bad_scope["scope"] = "issue_evidence"
    message = json.dumps({k: v for k, v in bad_scope.items() if k != "signature"},
                         sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    seed_path = os.path.join(store().keys_dir(),
                             "%s.seed" % fresh_signer["key_id"])
    with open(seed_path, encoding="utf-8") as handle:
        seed_hex = handle.read().strip()
    seed_value_for_leak_check = seed_hex
    import nacl.signing                                          # noqa: PLC0415
    signing_key = nacl.signing.SigningKey(bytes.fromhex(seed_hex))
    bad_scope["signature"] = base64.b64encode(
        signing_key.sign(message).signature).decode("ascii")
    registry = read_json(registry_path)
    registry["registrations"][0]["provenance_signature"] = bad_scope
    a18_path = os.path.join(WORKSPACE, "registry-a18.json")
    write_json(a18_path, registry)
    result = verify_baseline(baseline, a18_path, policy="require_signature")
    ok("A18 签名用途 scope 不匹配 -> 拒绝（SCOPE_MISMATCH）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "SCOPE_MISMATCH",
       str(result["status"]))

    # ---------------------------------------------------------------- 私钥泄露检查
    # K1: 仓库内无 .seed 文件（真实仓库 & 模拟工作区内的仓库树）
    repo_tree = os.path.join(PROJECT_ROOT, ".ai")
    seeds_in_repo = []
    for root, _dirs, files in os.walk(repo_tree):
        for name in files:
            if name.endswith(".seed"):
                seeds_in_repo.append(os.path.join(root, name))
    ok("K1 仓库内不存在私钥种子文件", not seeds_in_repo, str(seeds_in_repo[:3]))
    # K2: 信任根文件只含公钥
    root_doc = read_json(TRUST_ROOT)
    text = json.dumps(root_doc)
    seed_like = [key.get("key_id") for key in root_doc.get("keys", [])
                 if "seed" in json.dumps(key).lower()]
    ok("K2 信任根文件只含公钥（无种子字段）",
       all("seed" not in json.dumps(key).lower() for key in root_doc.get("keys", []))
       and seed_like == [], str(seed_like))
    # K3: CLI 输出不含种子
    cli_trust = os.path.join(EXTERNAL, "k3", "trust_root.json")
    proc = subprocess.run([sys.executable, "-I",
                           os.path.join(PROVENANCE_DIR, "provenance_cli.py"),
                           "--trust-root", cli_trust, "keygen",
                           "--subject", "leak-check", "--scopes",
                           "approve_baseline"],
                          capture_output=True, text=True, encoding="utf-8",
                          timeout=120, cwd=PROJECT_ROOT)
    cli_seed_file = os.path.join(os.path.dirname(cli_trust), "keys")
    cli_seeds = [open(os.path.join(cli_seed_file, name), encoding="utf-8").read().strip()
                 for name in os.listdir(cli_seed_file)] if os.path.isdir(cli_seed_file) else []
    ok("K3 CLI 输出/日志不含种子内容",
       proc.returncode == 0
       and not any(seed and seed in (proc.stdout + proc.stderr)
                   for seed in cli_seeds),
       str(proc.returncode))
    # K4: 异常消息不含种子
    try:
        signing.sign_object(
            object_type="baseline", object_id="leak", object_version="1",
            content_digest="a" * 64, digest_scheme=bl.DIGEST_SCHEME,
            key_id="PROVKEY-no-seed", trust_store=store(), project_root=WORKSPACE)
        error_message = ""
    except Exception as exc:                                  # noqa: BLE001
        error_message = str(exc)
    ok("K4 异常消息不含种子内容",
       seed_value_for_leak_check not in error_message,
       error_message[:120])
    # K5: 测试信任根与生产信任根隔离
    from provenance.trust_store import default_trust_root_path  # noqa: PLC0415
    ok("K5 测试信任根与生产信任根隔离",
       TRUST_ROOT != default_trust_root_path(PROJECT_ROOT)
       and not os.path.samefile(os.path.dirname(TRUST_ROOT),
                                os.path.dirname(default_trust_root_path(PROJECT_ROOT)))
       if os.path.exists(default_trust_root_path(PROJECT_ROOT)) else True,
       "%s vs %s" % (TRUST_ROOT, default_trust_root_path(PROJECT_ROOT)))
    # K6: 结束后无残留（目录清理在 main 末尾执行后无法断言自身，
    # 这里断言所有测试信任根都在 _TMP_ROOT 内、随目录一起销毁）
    ok("K6 全部测试密钥位于一次性临时目录（随测试销毁）",
       is_inside_path(TRUST_ROOT, _TMP_ROOT)
       and is_inside_path(cli_trust, _TMP_ROOT), "")

    print("\n%d checks, %d failures" % (_checks, len(_failures)))
    if _failures:
        print("FAILED:")
        for item in _failures:
            print("  - %s" % item)
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
