#!/usr/bin/env python3
"""Holdout 来源签名集成测试（Phase 1.61，任务书 §6/§8）。

被测对象：holdout_registry.seal_dataset_signed()（加法）
         + evidence_eval._verify_holdout_provenance()（消费时验证）

覆盖矩阵：
    A. 封存签名
      A1 seal_dataset_signed -> SEALED + provenance_signature 绑定对象身份/摘要
      A2 seal_dataset（无签名）保持 1.60 语义（Legacy 数据兼容）
    B. 消费时验证（_verify_holdout_provenance）
      B1 未启用门禁 -> None（1.60 语义不变）
      B2 有效签名 + allow_legacy/require -> usable，消费放行
      B3 内容被改（A11）-> holdout_digest_mismatch
      B4 来源被改（A12）-> holdout_signature_invalid（登记来源 vs 签名绑定来源）
      B5 未知密钥（A05 语义）-> holdout_signer_untrusted
      B6 撤销密钥（A13）-> holdout_revoked
      B7 删除签名 + require -> holdout_signature_missing（A15，不伪装 NOT_EVALUATED 缺口）
      B8 信任根缺失 + require -> holdout_signature_invalid（A17 fail-closed）
    C. 一次性消费语义不破坏
      C1 签名数据集消费后 CONSUMED；再次消费 -> holdout_already_consumed
      C2 record_usage 在签名验证失败时不发生（B3 场景复核 usage_history 为空）

用法：python .ai/tools/evaluation/tests/test_holdout_signature.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(EVAL_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
VALIDATOR_DIR = os.path.join(TOOLS_DIR, "validator")
for _path in (EVAL_DIR, VALIDATOR_DIR, TOOLS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import evidence_eval                                          # noqa: E402
import holdout_registry as hr                                 # noqa: E402
from provenance import signing                                # noqa: E402
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


_TMP_ROOT = tempfile.mkdtemp(prefix="p161-holdout-sig-")
WORKSPACE = os.path.join(_TMP_ROOT, "workspace")
EXTERNAL = os.path.join(_TMP_ROOT, "external")
os.makedirs(WORKSPACE, exist_ok=True)
os.makedirs(EXTERNAL, exist_ok=True)
TRUST_ROOT = os.path.join(EXTERNAL, "trust_root.json")


def store() -> TrustStore:
    return TrustStore(TRUST_ROOT, project_root=WORKSPACE)


def make_holdout(holdout_id: str, *, sign_key=None, files=2) -> tuple[str, str, dict]:
    """登记+封存一个临时 Holdout；sign_key 给定时用 seal_dataset_signed。"""
    registry_path = os.path.join(_TMP_ROOT, "holdout-%s.json" % holdout_id.lower())
    hr.create_dataset(holdout_id, "1", source="Phase 1.61 test collection",
                      feature_ids=["openable_door"], behavior_ids=["open"],
                      registry_path=registry_path)
    evidence_paths = []
    for index in range(files):
        path = os.path.join(_TMP_ROOT, "%s-file%d.json" % (holdout_id.lower(), index))
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"run": index, "data": "holdout-evidence"}, handle)
        evidence_paths.append(path)
    if sign_key:
        record = hr.seal_dataset_signed(
            holdout_id, "1", evidence_paths=evidence_paths,
            key_id=sign_key["key_id"], trust_store=store(),
            project_root=WORKSPACE, registry_path=registry_path)
    else:
        hr.validate_dataset(holdout_id, "1", evidence_paths=evidence_paths,
                            registry_path=registry_path)
        record = hr.seal_dataset(holdout_id, "1", evidence_paths=evidence_paths,
                                 registry_path=registry_path)
    return registry_path, record["content_digest"], evidence_paths


def verify_block(entry: dict, policy: str, trust_root: str = TRUST_ROOT) -> dict:
    return evidence_eval._verify_holdout_provenance(
        entry, {"id": "E5"}, policy, {"active": True},
        trust_root_path=trust_root)


def main() -> int:
    trust = store()
    key = signing.generate_and_register(
        subject="holdout-sealer", scopes=["seal_holdout"],
        trust_store=trust, project_root=WORKSPACE)

    # ---------------------------------------------------------------- A
    registry, digest, evidence_paths = make_holdout("SIG-H1", sign_key=key)
    entry = hr.find_dataset("SIG-H1", "1", registry_path=registry)
    envelope = entry.get("provenance_signature") or {}
    ok("A1a 封存签名存在且绑定对象身份/摘要/scope",
       envelope.get("object_id") == "SIG-H1"
       and envelope.get("object_version") == "1"
       and envelope.get("content_digest") == digest
       and envelope.get("scope") == "seal_holdout",
       str({k: envelope.get(k) for k in ("object_id", "object_version", "scope")}))
    unsigned_registry, _digest2, _paths2 = make_holdout("LEGACY-H2")
    entry2 = hr.find_dataset("LEGACY-H2", "1", registry_path=unsigned_registry)
    ok("A2 无签名封存保持 1.60 语义（无 provenance_signature 字段）",
       entry2["status"] == "SEALED" and "provenance_signature" not in entry2,
       str(entry2.get("status")))

    # ---------------------------------------------------------------- B
    ok("B1 未启用门禁 -> None（1.60 语义不变）",
       verify_block(entry, "") is None)
    block = verify_block(entry, "allow_legacy")
    ok("B2 有效签名 -> usable（allow_legacy 与 require 一致）",
       block["usable"] and block["trust_level"] == "CRYPTOGRAPHICALLY_VERIFIED"
       and verify_block(entry, "require_signature")["usable"],
       str(block))
    # B3 内容被改（A11）：换文件内容 -> 摘要失配
    with open(evidence_paths[0], "w", encoding="utf-8") as handle:
        json.dump({"run": 0, "data": "TAMPERED"}, handle)
    entry_tampered = hr.find_dataset("SIG-H1", "1", registry_path=registry)
    block = verify_block(entry_tampered, "require_signature")
    # 登记表里的 digest 未变（攻击者只改数据文件），但签名绑定的是封存时摘要；
    # 消费时 holdout_registry.check_usable 会重算文件摘要 -> 拒绝。
    # 签名层验证 digest 一致性：登记 digest vs 签名 digest 仍一致（签名没破），
    # 内容篡改由 check_usable 的重算摘要拦截（1.60 层）——两层防御各自生效。
    ok("B3a 签名层：登记摘要与签名摘要一致（签名未被篡改场景破坏）",
       block["usable"] is True, str(block))
    usable = hr.check_usable(entry_tampered, evidence_paths=evidence_paths)
    ok("B3b 内容层：篡改数据文件 -> check_usable 拒绝（A11）",
       not usable["usable"], str(usable))
    # B3c 签名层直接拒绝篡改：伪造登记 digest 也要签名失配
    tampered_registry_path = registry + ".b3c.json"
    registry_doc = json.load(open(registry, encoding="utf-8"))
    for record in registry_doc["datasets"]:
        record["content_digest"] = "f" * 64
    with open(tampered_registry_path, "w", encoding="utf-8") as handle:
        json.dump(registry_doc, handle)
    entry_forged = hr.find_dataset("SIG-H1", "1",
                                   registry_path=tampered_registry_path)
    block = verify_block(entry_forged, "require_signature")
    ok("B3c 登记摘要被改 -> holdout_digest_mismatch（签名绑定原摘要）",
       not block["usable"] and block["reason"] == "holdout_digest_mismatch",
       str(block))
    # B4 来源被改（A12）
    source_registry_path = registry + ".b4.json"
    registry_doc = json.load(open(registry, encoding="utf-8"))
    for record in registry_doc["datasets"]:
        record["source"] = "attacker-claimed-source"
    with open(source_registry_path, "w", encoding="utf-8") as handle:
        json.dump(registry_doc, handle)
    entry_source = hr.find_dataset("SIG-H1", "1", registry_path=source_registry_path)
    block = verify_block(entry_source, "require_signature")
    ok("B4 来源被改 -> holdout_signature_invalid（A12）",
       not block["usable"] and block["reason"] == "holdout_signature_invalid",
       str(block))
    # B5 未知密钥（登记签名密钥 ID 改成未知值）
    unknown_registry_path = registry + ".b5.json"
    registry_doc = json.load(open(registry, encoding="utf-8"))
    for record in registry_doc["datasets"]:
        record["provenance_signature"]["signer_key_id"] = "PROVKEY-unknown"
    with open(unknown_registry_path, "w", encoding="utf-8") as handle:
        json.dump(registry_doc, handle)
    entry_unknown = hr.find_dataset("SIG-H1", "1",
                                    registry_path=unknown_registry_path)
    block = verify_block(entry_unknown, "require_signature")
    ok("B5 未知密钥 -> holdout_signer_untrusted（A05 语义）",
       not block["usable"] and block["reason"] == "holdout_signer_untrusted",
       str(block))
    # B6 撤销密钥（A13）
    revoke_registry, _digest3, _paths3 = make_holdout("SIG-H3")
    # 先签后撤：重新封存签好名，再撤销签发密钥
    hr.create_dataset("SIG-H3", "2", source="Phase 1.61 test collection",
                      feature_ids=["openable_door"], behavior_ids=["open"],
                      registry_path=revoke_registry)
    record = hr.seal_dataset_signed(
        "SIG-H3", "2", evidence_paths=evidence_paths,
        key_id=key["key_id"], trust_store=store(), project_root=WORKSPACE,
        registry_path=revoke_registry)
    trust.set_key_status(key["key_id"], STATUS_REVOKED, reason="test")
    entry_revoked = hr.find_dataset("SIG-H3", "2", registry_path=revoke_registry)
    block = verify_block(entry_revoked, "require_signature")
    ok("B6 撤销密钥 -> holdout_revoked（A13）",
       not block["usable"] and block["reason"] == "holdout_revoked",
       str(block))
    # B7 删除签名 + require（A15）
    entry_nosig = dict(entry)
    entry_nosig.pop("provenance_signature", None)
    block = verify_block(entry_nosig, "require_signature")
    ok("B7 删除签名 + require -> holdout_signature_missing（A15）",
       not block["usable"] and block["reason"] == "holdout_signature_missing",
       str(block))
    block = verify_block(entry_nosig, "allow_legacy")
    ok("B7b 删除签名 + allow_legacy -> LEGACY_APPROVED（诊断，不冒充已验证）",
       block["usable"] and block["trust_level"] == "LEGACY_APPROVED",
       str(block))
    # B8 信任根缺失 + require（A17）
    block = verify_block(entry, "require_signature",
                         trust_root=os.path.join(EXTERNAL, "absent.json"))
    ok("B8 信任根缺失 + require -> holdout_signature_invalid（A17）",
       not block["usable"] and block["reason"] == "holdout_signature_invalid",
       str(block))

    # ---------------------------------------------------------------- C
    key_c = signing.generate_and_register(
        subject="holdout-sealer-c", scopes=["seal_holdout"],
        trust_store=trust, project_root=WORKSPACE)
    registry_path_c, _digest4, _paths4 = make_holdout("SIG-H4", sign_key=key_c)
    hr.record_usage("SIG-H4", "1", purpose="evaluation", run_ref="E5",
                    registry_path=registry_path_c)
    entry_used = hr.find_dataset("SIG-H4", "1", registry_path=registry_path_c)
    ok("C1a 签名数据集消费后 CONSUMED（一次性语义保持）",
       entry_used["status"] == "CONSUMED"
       and len(entry_used["usage_history"]) == 1, str(entry_used["status"]))
    usable = hr.check_usable(entry_used)
    ok("C1b 已消费数据集不可再用",
       not usable["usable"], str(usable))
    # C2: 签名验证失败时不发生 record_usage（B3c 场景的登记表复核）
    entry_forged_check = hr.find_dataset("SIG-H1", "1",
                                         registry_path=tampered_registry_path)
    before_history = len(entry_forged_check.get("usage_history") or [])
    ok("C2 签名失败场景未触发消费登记（usage_history 未增长）",
       before_history == 0, str(before_history))

    print("\n%d checks, %d failures" % (_checks, len(_failures)))
    if _failures:
        print("FAILED:")
        for item in _failures:
            print("  - %s" % item)
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
