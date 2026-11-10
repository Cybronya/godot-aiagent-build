#!/usr/bin/env python3
"""Baseline 来源签名集成测试（Phase 1.61，任务书 §4/§8）。

被测对象：baseline_lifecycle.use_baseline_trusted()（1.60 use_baseline 之上的加法层）

覆盖矩阵：
    A. 策略分级（不破坏 1.60）
      A1 无签名 + allow_legacy -> APPROVED_OK + LEGACY_APPROVED（1.60 兼容）
      A2 无签名 + require -> SIGNATURE_REQUIRED（不可用，不自动降级）
      A3 有效签名 -> APPROVED_OK + CRYPTOGRAPHICALLY_VERIFIED
    B. 攻击拒绝
      B1 内容被改（A01）-> DIGEST_MISMATCH（1.60 层先拒绝）
      B2 登记摘要被改（A02）-> SIGNATURE_INVALID（签名绑定的摘要失配）
      B3 登记审批者被改（A03）-> SIGNATURE_INVALID（签名内审批元数据交叉核对）
      B4 用错误私钥重签（A06）-> SIGNATURE_INVALID
      B5 删除签名记录（A15）-> require 拒绝 / allow_legacy 仅标 LEGACY
      B6 未知密钥（A05）-> SIGNATURE_INVALID（KEY_UNKNOWN）
      B7 撤销密钥（A13）-> SIGNATURE_INVALID（KEY_REVOKED）
      B8 外部信任根缺失（A17）-> require 拒绝 / allow_legacy 拒绝（签名存在时）
      B9 scope 不匹配（A18）-> SIGNATURE_INVALID（SCOPE_MISMATCH）
    C. Legacy 真实基线（不伪造、不自动升级）
      C1 四条真实基线 allow_legacy -> LEGACY_APPROVED，仍可用
      C2 四条真实基线 require -> SIGNATURE_REQUIRED（如实要求签名）
      C3 真实基线文件字节未被本阶段改动
    D. 登记表签名写入
      D1 签名写入登记条目且不改变基线文件字节

用法：python .ai/tools/validator/tests/test_baseline_signature.py
"""

from __future__ import annotations

import base64
import copy
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
for _path in (VALIDATOR_DIR,):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import baseline_lifecycle as bl                               # noqa: E402
import trace_baselines                                        # noqa: E402
from provenance import signing, verification                  # noqa: E402
from provenance.trust_store import TrustStore, STATUS_REVOKED  # noqa: E402

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


_TMP_ROOT = tempfile.mkdtemp(prefix="p161-baseline-sig-")
WORKSPACE = os.path.join(_TMP_ROOT, "workspace")     # 模拟项目工作区
EXTERNAL = os.path.join(_TMP_ROOT, "external")       # 攻击边界之外
os.makedirs(WORKSPACE, exist_ok=True)
os.makedirs(EXTERNAL, exist_ok=True)
TRUST_ROOT = os.path.join(EXTERNAL, "trust_root.json")


def store() -> TrustStore:
    return TrustStore(TRUST_ROOT, project_root=WORKSPACE)


def sample_baseline(**overrides) -> dict:
    document = {
        "baseline_schema_version": 1,
        "baseline_version": 3,
        "scenario_id": "test_scenario",
        "trace_schema_version": 1,
        "approved_behavior_version": 7,
        "comparison_policy": {"strict_fields": ["type", "index"]},
        "events": [{"type": "orchestration_started", "index": 0,
                    "data": {"mode": "waves"}}],
        "expected_final_state": {"state": "completed"},
        "coverage": {"chain": "started -> victory"},
        "approval": {"status": "approved", "approver": "tester",
                     "approved_at": "2026-11-03T00:00:00Z",
                     "candidate_fingerprint": "0" * 16},
    }
    document.update(overrides)
    return document


_registry_seq = [0]


def setup_signed_registry(document: dict, *, revoke_key=False) -> tuple[str, dict]:
    """临时登记 + 签发：返回 (registry_path, envelope)。"""
    _registry_seq[0] += 1
    registry_path = os.path.join(_TMP_ROOT, "reg-%s-%d.json"
                                 % (document["scenario_id"], _registry_seq[0]))
    digest = bl.content_digest(document)["digest"]
    bl.register(document["scenario_id"], document["baseline_version"],
                bl.APPROVED, digest=digest, approver="tester",
                approved_at="2026-11-03T00:00:00Z",
                basis="test", registry_path=registry_path)
    trust = store()
    key = signing.generate_and_register(
        subject="baseline-approver", scopes=["approve_baseline"],
        trust_store=trust, project_root=WORKSPACE)
    envelope = signing.sign_object(
        object_type="baseline", object_id=document["scenario_id"],
        object_version=document["baseline_version"], content_digest=digest,
        digest_scheme=bl.DIGEST_SCHEME, key_id=key["key_id"],
        trust_store=trust, project_root=WORKSPACE,
        binding={"approver": "tester", "approved_at": "2026-11-03T00:00:00Z"})
    if revoke_key:  # 先签发、后撤销（撤销密钥的历史签名验证场景）
        trust.set_key_status(key["key_id"], STATUS_REVOKED, reason="test")
    registry = json.load(open(registry_path, encoding="utf-8"))
    for entry in registry["registrations"]:
        if str(entry["baseline_id"]) == str(document["scenario_id"]):
            entry["provenance_signature"] = envelope
    with open(registry_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(registry, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return registry_path, envelope


def main() -> int:
    baseline_files_before = {}
    baselines_dir = bl.BASELINES_DIR
    for name in sorted(os.listdir(baselines_dir)):
        if name.endswith(".json"):
            with open(os.path.join(baselines_dir, name), "rb") as handle:
                baseline_files_before[name] = handle.read()

    # ---------------------------------------------------------------- A
    document = sample_baseline()
    registry_path, _env = setup_signed_registry(document)
    result = bl.use_baseline_trusted(document, registry_path=registry_path,
                                     trust_store=store(),
                                     signature_policy="allow_legacy")
    ok("A3a 有效签名 -> APPROVED_OK + CRYPTOGRAPHICALLY_VERIFIED",
       result["status"] == "APPROVED_OK"
       and result["provenance_trust"] == "CRYPTOGRAPHICALLY_VERIFIED",
       str(result.get("status")) + "/" + str(result.get("provenance_trust")))
    ok("A3b signer_subject 来自外部信任根",
       (result.get("provenance") or {}).get("signer_subject") == "baseline-approver")
    unsigned_registry = os.path.join(_TMP_ROOT, "reg-unsigned.json")
    variant_v9 = dict(document, baseline_version="9")
    bl.register(document["scenario_id"], "9", bl.APPROVED,
                digest=bl.content_digest(variant_v9)["digest"],
                approver="tester", approved_at="2026-11-03T00:00:00Z",
                basis="test", registry_path=unsigned_registry)
    legacy = bl.use_baseline_trusted(
        variant_v9, registry_path=unsigned_registry,
        trust_store=store(), signature_policy="allow_legacy")
    ok("A1 无签名 + allow_legacy -> LEGACY_APPROVED（1.60 兼容）",
       legacy["status"] == "APPROVED_OK"
       and legacy["provenance_trust"] == "LEGACY_APPROVED",
       str(legacy.get("status")))
    required = bl.use_baseline_trusted(
        variant_v9, registry_path=unsigned_registry,
        trust_store=store(), signature_policy="require_signature")
    ok("A2 无签名 + require -> SIGNATURE_REQUIRED（fail-closed）",
       required["status"] == "SIGNATURE_REQUIRED"
       and required["provenance_trust"] == "SIGNATURE_REQUIRED",
       str(required.get("status")))

    # ---------------------------------------------------------------- B
    # B1 内容被改（A01）
    tampered = copy.deepcopy(document)
    tampered["events"][0]["data"]["mode"] = "attacker"
    result = bl.use_baseline_trusted(tampered, registry_path=registry_path,
                                     trust_store=store(),
                                     signature_policy="allow_legacy")
    ok("B1 内容被改 -> DIGEST_MISMATCH（A01）",
       result["status"] == "DIGEST_MISMATCH", str(result.get("status")))
    # B2 登记摘要被改（A02）
    registry2_path = os.path.join(_TMP_ROOT, "reg-b2.json")
    registry = json.load(open(registry_path, encoding="utf-8"))
    for entry in registry["registrations"]:
        entry["content_digest"] = "e" * 64
    with open(registry2_path, "w", encoding="utf-8") as handle:
        json.dump(registry, handle)
    result = bl.use_baseline_trusted(document, registry_path=registry2_path,
                                     trust_store=store(),
                                     signature_policy="allow_legacy")
    ok("B2 登记摘要被改 -> DIGEST_MISMATCH（A02：1.60 层拒绝；签名层另绑摘要双保险）",
       result["status"] == "DIGEST_MISMATCH"
       and result["provenance_trust"] == "NOT_EVALUATED",
       str(result.get("status")))
    # B3 登记审批者被改（A03）
    registry3_path = os.path.join(_TMP_ROOT, "reg-b3.json")
    registry = json.load(open(registry_path, encoding="utf-8"))
    for entry in registry["registrations"]:
        entry["approver"] = "attacker"
    with open(registry3_path, "w", encoding="utf-8") as handle:
        json.dump(registry, handle)
    tampered_approval = copy.deepcopy(document)
    tampered_approval["approval"]["approver"] = "attacker"
    result = bl.use_baseline_trusted(tampered_approval,
                                     registry_path=registry3_path,
                                     trust_store=store(),
                                     signature_policy="allow_legacy")
    ok("B3 审批者身份被改 -> 签名验证失败（A03）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "SIGNATURE_INVALID",
       str(result.get("status")) + "/" +
       str((result.get("provenance") or {}).get("verification", {}).get("status")))
    # B4 错误私钥重签（A06）
    import nacl.signing                                          # noqa: PLC0415
    attacker = nacl.signing.SigningKey.generate()
    registry = json.load(open(registry_path, encoding="utf-8"))
    envelope = None
    for entry in registry["registrations"]:
        envelope = entry.get("provenance_signature")
    forged = dict(envelope, signature=base64.b64encode(
        attacker.sign(json.dumps({key: value for key, value in envelope.items()
                                  if key != "signature"}, sort_keys=True,
                                  ensure_ascii=False,
                                  separators=(",", ":")).encode("utf-8")).signature
    ).decode("ascii"))
    registry4_path = os.path.join(_TMP_ROOT, "reg-b4.json")
    registry = json.load(open(registry_path, encoding="utf-8"))
    for entry in registry["registrations"]:
        entry["provenance_signature"] = forged
    with open(registry4_path, "w", encoding="utf-8") as handle:
        json.dump(registry, handle)
    result = bl.use_baseline_trusted(document, registry_path=registry4_path,
                                     trust_store=store(),
                                     signature_policy="allow_legacy")
    ok("B4 用错误私钥重签 -> SIGNATURE_INVALID（A06）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "SIGNATURE_INVALID",
       str(result.get("status")))
    # B5 删除签名记录（A15）
    registry5_path = os.path.join(_TMP_ROOT, "reg-b5.json")
    registry = json.load(open(registry_path, encoding="utf-8"))
    for entry in registry["registrations"]:
        entry.pop("provenance_signature", None)
    with open(registry5_path, "w", encoding="utf-8") as handle:
        json.dump(registry, handle)
    legacy = bl.use_baseline_trusted(document, registry_path=registry5_path,
                                     trust_store=store(),
                                     signature_policy="allow_legacy")
    ok("B5a 删除签名 + allow_legacy -> LEGACY_APPROVED（不冒充已验证）",
       legacy["status"] == "APPROVED_OK"
       and legacy["provenance_trust"] == "LEGACY_APPROVED",
       str(legacy.get("provenance_trust")))
    required = bl.use_baseline_trusted(document, registry_path=registry5_path,
                                       trust_store=store(),
                                       signature_policy="require_signature")
    ok("B5b 删除签名 + require -> SIGNATURE_REQUIRED（不得静默通过）",
       required["status"] == "SIGNATURE_REQUIRED", str(required.get("status")))
    # B6 未知密钥（A05）
    registry = json.load(open(registry_path, encoding="utf-8"))
    for entry in registry["registrations"]:
        entry["provenance_signature"] = dict(
            entry["provenance_signature"], signer_key_id="PROVKEY-forged-id")
    registry6_path = os.path.join(_TMP_ROOT, "reg-b6.json")
    with open(registry6_path, "w", encoding="utf-8") as handle:
        json.dump(registry, handle)
    result = bl.use_baseline_trusted(document, registry_path=registry6_path,
                                     trust_store=store(),
                                     signature_policy="allow_legacy")
    ok("B6 未知密钥 -> SIGNATURE_INVALID（KEY_UNKNOWN, A05）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "KEY_UNKNOWN",
       str(result.get("status")))
    # B7 撤销密钥（A13）
    revoked_registry, _env = setup_signed_registry(
        sample_baseline(), revoke_key=True)
    result = bl.use_baseline_trusted(document, registry_path=revoked_registry,
                                     trust_store=store(),
                                     signature_policy="allow_legacy")
    ok("B7 撤销密钥 -> SIGNATURE_INVALID（KEY_REVOKED, A13）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "KEY_REVOKED",
       str(result.get("status")))
    # B8 信任根缺失（A17）
    missing_store = TrustStore(os.path.join(EXTERNAL, "absent.json"),
                               project_root=WORKSPACE)
    result = bl.use_baseline_trusted(document, registry_path=registry_path,
                                     trust_store=missing_store,
                                     signature_policy="allow_legacy")
    ok("B8a 信任根缺失 + 已签对象 -> 拒绝（fail-closed）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "TRUST_ROOT_MISSING",
       str(result.get("status")))
    result = bl.use_baseline_trusted(document, registry_path=registry5_path,
                                     trust_store=missing_store,
                                     signature_policy="allow_legacy")
    ok("B8b 信任根缺失 + 无签名对象 -> LEGACY_APPROVED（历史数据不要求根）",
       result["status"] == "APPROVED_OK"
       and result["provenance_trust"] == "LEGACY_APPROVED",
       str(result.get("provenance_trust")))
    result = bl.use_baseline_trusted(document, registry_path=registry_path,
                                     trust_store=missing_store,
                                     signature_policy="require_signature")
    ok("B8c 信任根缺失 + require -> SIGNATURE_INVALID（A17）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "TRUST_ROOT_MISSING",
       str(result.get("status")))
    # B9 scope 不匹配（A18）：手工构造 scope 被改的封套（模拟攻击者持有泄露种子）
    seed_path = os.path.join(store().keys_dir(),
                             "%s.seed" % json.load(open(registry_path,
                                                        encoding="utf-8"))
                             ["registrations"][0]["provenance_signature"]["signer_key_id"])
    with open(seed_path, encoding="utf-8") as handle:
        seed_hex = handle.read().strip()
    import nacl.signing                                          # noqa: PLC0415
    signing_key = nacl.signing.SigningKey(bytes.fromhex(seed_hex))
    envelope = json.load(open(registry_path, encoding="utf-8"))[
        "registrations"][0]["provenance_signature"]
    bad_scope = dict(envelope, scope="issue_evidence")
    bad_scope["signature"] = base64.b64encode(
        signing_key.sign(json.dumps({key: value for key, value in bad_scope.items()
                                     if key != "signature"}, sort_keys=True,
                                     ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).signature
    ).decode("ascii")
    registry7_path = os.path.join(_TMP_ROOT, "reg-b7.json")
    registry = json.load(open(registry_path, encoding="utf-8"))
    for entry in registry["registrations"]:
        entry["provenance_signature"] = bad_scope
    with open(registry7_path, "w", encoding="utf-8") as handle:
        json.dump(registry, handle)
    result = bl.use_baseline_trusted(document, registry_path=registry7_path,
                                     trust_store=store(),
                                     signature_policy="allow_legacy")
    ok("B9 scope 不匹配 -> SIGNATURE_INVALID（SCOPE_MISMATCH, A18）",
       result["status"] == "SIGNATURE_INVALID"
       and result["provenance"]["verification"]["status"] == "SCOPE_MISMATCH",
       str(result.get("status")))

    # ---------------------------------------------------------------- C
    real_names = ["waves", "holdout", "single_stage_boss", "multi_stage_boss"]
    legacy_ok = True
    detail = ""
    for name in real_names:
        path = os.path.join(baselines_dir, "%s.json" % name)
        with open(path, "r", encoding="utf-8") as handle:
            real_document = json.load(handle)
        result = bl.use_baseline_trusted(real_document, baseline_path=path,
                                         trust_store=store(),
                                         signature_policy="allow_legacy")
        if result["status"] != "APPROVED_OK" or \
                result["provenance_trust"] != "LEGACY_APPROVED":
            legacy_ok = False
            detail = "%s: %s / %s" % (name, result["status"],
                                      result.get("provenance_trust"))
            break
    ok("C1 四条真实基线 -> LEGACY_APPROVED（不伪造签名、不自动升级）",
       legacy_ok, detail)
    required_names = []
    for name in real_names:
        path = os.path.join(baselines_dir, "%s.json" % name)
        with open(path, "r", encoding="utf-8") as handle:
            real_document = json.load(handle)
        result = bl.use_baseline_trusted(real_document, baseline_path=path,
                                         trust_store=store(),
                                         signature_policy="require_signature")
        required_names.append(result["status"])
    ok("C2 四条真实基线 require -> SIGNATURE_REQUIRED（如实要求）",
       all(status == "SIGNATURE_REQUIRED" for status in required_names),
       str(required_names))
    baseline_files_after = {}
    for name in sorted(os.listdir(baselines_dir)):
        if name.endswith(".json"):
            with open(os.path.join(baselines_dir, name), "rb") as handle:
                baseline_files_after[name] = handle.read()
    ok("C3 真实基线文件字节未被改动",
       baseline_files_before == baseline_files_after)

    # ---------------------------------------------------------------- D
    signed_doc = sample_baseline()
    signed_registry, envelope = setup_signed_registry(signed_doc)
    ok("D1a 登记条目含 provenance_signature 且绑定对象身份",
       envelope["object_id"] == "test_scenario"
       and envelope["object_version"] == "3"
       and envelope["scope"] == "approve_baseline")
    with open(os.path.join(baselines_dir, "waves.json"), "rb") as handle:
        unchanged = handle.read() == baseline_files_before.get("waves.json")
    ok("D1b 签名只写登记表，不动基线文件", unchanged)

    print("\n%d checks, %d failures" % (_checks, len(_failures)))
    if _failures:
        print("FAILED:")
        for item in _failures:
            print("  - %s" % item)
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
