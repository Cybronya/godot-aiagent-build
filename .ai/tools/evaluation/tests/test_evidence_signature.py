#!/usr/bin/env python3
"""Evidence 来源签名集成测试（Phase 1.61，任务书 §5/§8）。

被测对象：evidence_adapter.load_verified(provenance_policy=...)（加法参数）
         + provenance.verification 的 Evidence sidecar 链路

覆盖矩阵：
    A. 正常链路
      A1 真实契约构造的证据 + 有效签名 + require -> Validator PASS + CRYPTOGRAPHICALLY_VERIFIED
      A2 签名验证是**追加**门禁：Integrity（1.56）与 Artifact Cross-Validation（1.57）
         仍在签名验证之前独立执行
      A3 默认 provenance_policy="" -> 完全 1.58 语义（bundle_index 无 provenance 字段）
      A4 allow_legacy + 无签名 -> LEGACY_APPROVED 诊断（可用，不冒充已验证）
    B. 攻击拒绝
      B1 改内容 + 重算 integrity 哈希（绕过 1.56 的摘要自洽）+ 无签名 + require
         -> bundle_rejected（provenance 层封堵「重算哈希」逃逸路径）
      B2 改内容 + 重算哈希 + 用**原始签名** -> DIGEST_MISMATCH（签名绑定原始摘要）
      B3 改 artifact_digests 集合 + 重算哈希 + 无签名 + require -> 拒绝（A10）
      B4 信任根缺失 + require -> 全部拒绝（A17 fail-closed）
      B5 伪造签名（错误私钥）-> 拒绝（A06/Evidence）
    C. CLI 集成（evidence_eval --allow-legacy / --require-signature）
      C1 --allow-legacy 端到端：任务结论不受缺签名影响（1.58 语义保持）
      C2 --require-signature 端到端：无签名 bundle -> INVALID_EVIDENCE，exit 1
      C3 两个互斥参数同时给出 -> 报错退出

用法：python .ai/tools/evaluation/tests/test_evidence_signature.py
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
EVAL_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(EVAL_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
SCENE_COMPOSER = os.path.join(TOOLS_DIR, "scene_composer")
VALIDATOR_DIR = os.path.join(TOOLS_DIR, "validator")
for _path in (SCENE_COMPOSER, EVAL_DIR, VALIDATOR_DIR, TOOLS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import evidence_adapter as adapter                            # noqa: E402
import evidence_fixtures as fixtures                          # noqa: E402
from provenance import signing, verification                  # noqa: E402
from provenance.trust_store import TrustStore                 # noqa: E402

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


PAIRS = fixtures.feature_pairs(["health"])
FIXTURE_FEATURES = ["health"]  # 限定验证范围：否则其余 Feature 全为 behavior_uncovered

_TMP_ROOT = tempfile.mkdtemp(prefix="p161-evidence-sig-")
WORKSPACE = os.path.join(_TMP_ROOT, "workspace")
EXTERNAL = os.path.join(_TMP_ROOT, "external")
os.makedirs(WORKSPACE, exist_ok=True)
os.makedirs(EXTERNAL, exist_ok=True)
TRUST_ROOT = os.path.join(EXTERNAL, "trust_root.json")


def store() -> TrustStore:
    return TrustStore(TRUST_ROOT, project_root=WORKSPACE)


def sign_bundle(bundle_path: str, key_id: str) -> str:
    with open(bundle_path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    digest = verification.recompute_evidence_digest(document)
    envelope = signing.sign_object(
        object_type="evidence_bundle", object_id=document["bundle_id"],
        object_version=document["schema_version"], content_digest=digest,
        digest_scheme="evidence-bundle-digest-v1", key_id=key_id,
        trust_store=store(), project_root=WORKSPACE,
        binding={"git_head": str(document.get("git_head") or "")})
    return verification.write_sidecar(bundle_path, envelope)


def resealed_copy(bundle_path: str) -> dict:
    """改内容并重算 integrity（绕过 1.56 摘要自洽检查）的副本。"""
    with open(bundle_path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    document = copy.deepcopy(document)
    document["features"][0]["behaviors"][0]["actual"][0]["observed"] = \
        not bool(document["features"][0]["behaviors"][0]["actual"][0]["observed"])
    fixtures.resign_bundle(document)  # 攻击者重算完整性哈希（SHA256 无法防住）
    return document


def bundle_index_entry(verified: dict) -> dict:
    entries = [item for item in verified.get("bundle_index") or []
               if item.get("readable")]
    return entries[0] if entries else {}


def verified_with(evidence_dir: str, artifact_root: str, mode: str) -> dict:
    """在测试信任根的签名门禁下调用 load_verified（mode: verify|require|off）。"""
    kwargs = {"features": list(FIXTURE_FEATURES)}  # 限定验证范围
    if mode == "off":
        return adapter.load_verified(evidence_dir=evidence_dir,
                                     artifact_roots=[artifact_root], **kwargs)
    adapter.set_signature_gate(store(),
                               "require_signature" if mode == "require"
                               else "allow_legacy")
    try:
        return adapter.load_verified(
            evidence_dir=evidence_dir, artifact_roots=[artifact_root],
            provenance_policy=adapter.PROVENANCE_REQUIRE if mode == "require"
            else adapter.PROVENANCE_VERIFY, **kwargs)
    finally:
        adapter.clear_signature_gate()


def main() -> int:
    trust = store()
    key = signing.generate_and_register(
        subject="evidence-collector", scopes=["issue_evidence"],
        trust_store=trust, project_root=WORKSPACE)

    root = os.path.join(_TMP_ROOT, "clean")
    evidence_dir, artifact_root = fixtures.make_evidence_dir(root, PAIRS)
    bundle_path = os.path.join(evidence_dir, "bundle-test.json")
    sidecar = sign_bundle(bundle_path, key["key_id"])

    # ---------------------------------------------------------------- A
    verified = verified_with(evidence_dir, artifact_root, "require")
    entry = bundle_index_entry(verified)
    ok("A1a 真实证据 + 有效签名 + require -> Validator PASS",
       verified["validator"]["status"] == "PASS",
       str(verified["validator"].get("detail"))[:200])
    ok("A1b provenance -> CRYPTOGRAPHICALLY_VERIFIED",
       entry.get("provenance_trust") == "CRYPTOGRAPHICALLY_VERIFIED"
       and entry.get("provenance_usable") is True,
       str({k: entry.get(k) for k in
            ("provenance_trust", "provenance_usable", "provenance_reason")}))
    ok("A2a 1.56 Integrity 仍在（integrity 块存在且被验证）",
       verified["validator"]["status"] == "PASS"
       and bool(entry.get("digest")), str(entry.get("digest")))
    ok("A2b 1.57 Artifact Cross-Validation 仍在（artifacts>0 且 cross_validated）",
       (verified["coverage"].get("artifacts") or 0) > 0
       and (verified["coverage"].get("cross_validated") or 0) > 0,
       str(verified["coverage"]))
    default = verified_with(evidence_dir, artifact_root, "off")
    ok("A3 默认策略 -> 无 provenance 字段（1.58 语义逐字不变）",
       "provenance_trust" not in bundle_index_entry(default),
       str(bundle_index_entry(default).get("provenance_trust")))
    unsigned_root = os.path.join(_TMP_ROOT, "unsigned")
    unsigned_dir, unsigned_artifacts = fixtures.make_evidence_dir(
        unsigned_root, PAIRS, bundle_id="bundle-unsigned")
    legacy = verified_with(unsigned_dir, unsigned_artifacts, "verify")
    ok("A4 无签名 + verify -> LEGACY_APPROVED（诊断，不阻断）",
       bundle_index_entry(legacy).get("provenance_trust") == "LEGACY_APPROVED"
       and legacy["validator"]["status"] == "PASS",
       str(bundle_index_entry(legacy).get("provenance_trust")))

    # ---------------------------------------------------------------- B
    # B1 改内容 + 重算 integrity + 无签名 + require
    b1_root = os.path.join(_TMP_ROOT, "b1")
    b1_dir, b1_artifacts = fixtures.make_evidence_dir(
        b1_root, PAIRS, bundle_id="bundle-b1")
    document = resealed_copy(os.path.join(b1_dir, "bundle-b1.json"))
    fixtures.write_bundle(b1_dir, document, "bundle-b1.json")
    verified = verified_with(b1_dir, b1_artifacts, "require")
    ok("B1 改内容+重算哈希+无签名+require -> bundle_rejected（封堵重算哈希逃逸）",
       verified["validator"]["status"] == "FAIL"
       and all(item.get("validator_reason") == "bundle_rejected"
               for item in verified["behaviors"]),
       str(verified["validator"].get("detail"))[:160])
    ok("B1b 拒绝原因来自 provenance 层",
       any("provenance_" in str(item.get("validator_detail"))
           for item in verified["behaviors"]),
       str([item.get("validator_detail") for item in verified["behaviors"]])[:160])
    # B2 改内容 + 重算哈希 + 保留原始签名 -> DIGEST_MISMATCH
    b2_root = os.path.join(_TMP_ROOT, "b2")
    b2_dir, b2_artifacts = fixtures.make_evidence_dir(
        b2_root, PAIRS, bundle_id="bundle-b2")
    shutil.copy(sidecar, os.path.join(b2_dir, "bundle-b2.json.sig.json"))
    document = resealed_copy(os.path.join(b2_dir, "bundle-b2.json"))
    fixtures.write_bundle(b2_dir, document, "bundle-b2.json")
    verified = verified_with(b2_dir, b2_artifacts, "require")
    entry = bundle_index_entry(verified)
    ok("B2 内容被改+原签名 -> 拒绝（DIGEST_MISMATCH，签名绑定原始摘要）",
       not entry.get("provenance_usable", True)
       and entry.get("provenance_trust") == "SIGNATURE_INVALID"
       and verified["validator"]["status"] == "FAIL",
       str(entry.get("provenance_reason"))[:160])
    # B3 改 artifact_digests + 重算哈希 + 无签名 + require（A10）
    b3_root = os.path.join(_TMP_ROOT, "b3")
    b3_dir, b3_artifacts = fixtures.make_evidence_dir(
        b3_root, PAIRS, bundle_id="bundle-b3")
    with open(os.path.join(b3_dir, "bundle-b3.json"), "r",
              encoding="utf-8") as handle:
        document = json.load(handle)
    document = copy.deepcopy(document)
    for run_id in (document["features"][0]["behaviors"][0]
                   .get("artifact_digests") or {}):
        document["features"][0]["behaviors"][0]["artifact_digests"][run_id] = \
            {"result": "f" * 64}
    fixtures.resign_bundle(document)
    fixtures.write_bundle(b3_dir, document, "bundle-b3.json")
    verified = verified_with(b3_dir, b3_artifacts, "require")
    ok("B3 改产物摘要集合+重算哈希+无签名+require -> 拒绝（A10）",
       verified["validator"]["status"] == "FAIL",
       str(verified["validator"].get("detail"))[:160])
    # B4 信任根缺失 + require（A17）
    missing_store = TrustStore(os.path.join(EXTERNAL, "absent.json"),
                               project_root=WORKSPACE)
    adapter.set_signature_gate(missing_store, "require_signature")
    try:
        verified = adapter.load_verified(evidence_dir=evidence_dir,
                                         artifact_roots=[artifact_root],
                                         provenance_policy="require",
                                         features=list(FIXTURE_FEATURES))
    finally:
        adapter.clear_signature_gate()
    ok("B4 信任根缺失 + require -> 全部拒绝（A17 fail-closed）",
       all(item.get("validator_reason") == "bundle_rejected"
           for item in verified["behaviors"])
       and "no trust root" in str(bundle_index_entry(verified).get("provenance_reason")),
       str(bundle_index_entry(verified).get("provenance_reason"))[:120])
    # B5 伪造签名（错误私钥，A06）
    import nacl.signing                                          # noqa: PLC0415
    b5_root = os.path.join(_TMP_ROOT, "b5")
    b5_dir, b5_artifacts = fixtures.make_evidence_dir(
        b5_root, PAIRS, bundle_id="bundle-b5")
    bundle_b5 = os.path.join(b5_dir, "bundle-b5.json")
    sign_bundle(bundle_b5, key["key_id"])
    with open(bundle_b5, "r", encoding="utf-8") as handle:
        doc5 = json.load(handle)
    with open(os.path.join(b5_dir, "bundle-b5.json.sig.json"), "r",
              encoding="utf-8") as handle:
        env5 = json.load(handle)
    attacker = nacl.signing.SigningKey.generate()
    env5["signature"] = base64.b64encode(
        attacker.sign(verification.recompute_evidence_digest(doc5).encode("utf-8")).signature
    ).decode("ascii")
    # 注意：上面这条伪造签名签名的是裸摘要字符串，而验证侧签的是封套规范化 JSON
    # —— 两种构造都必然验证失败；这里显式用「封套消息」再伪造一次更贴近 A06。
    message = json.dumps({k: v for k, v in env5.items() if k != "signature"},
                         sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    env5["signature"] = base64.b64encode(
        attacker.sign(message).signature).decode("ascii")
    fixtures.write_json = None  # noqa - 不使用 fixture 写封套（sidecar 自行写）
    with open(os.path.join(b5_dir, "bundle-b5.json.sig.json"), "w",
              encoding="utf-8") as handle:
        json.dump(env5, handle)
    verified = verified_with(b5_dir, b5_artifacts, "require")
    entry = bundle_index_entry(verified)
    ok("B5 错误私钥伪造签名 -> SIGNATURE_INVALID（A06）",
       entry.get("provenance_trust") == "SIGNATURE_INVALID"
       and all(item.get("validator_reason") == "bundle_rejected"
               for item in verified["behaviors"]),
       str(entry.get("provenance_reason"))[:160])

    # ---------------------------------------------------------------- C (CLI)
    cli_cmd = [sys.executable, "-I",
               os.path.join(EVAL_DIR, "evidence_eval.py")]
    # C1 --allow-legacy：任务结论保持 1.58 语义（PASS），签名仅诊断
    proc = subprocess.run(
        cli_cmd + ["--task", "E2", "--evidence-dir", evidence_dir,
                   "--artifact-root", artifact_root, "--no-collect",
                   "--allow-legacy", "--trust-root", TRUST_ROOT, "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=300,
        cwd=PROJECT_ROOT)
    cli_ok = proc.returncode == 0 and '"VERIFIED_PASS"' in proc.stdout
    ok("C1 --allow-legacy 端到端：任务结论与 1.58 一致（exit 0）",
       cli_ok, (proc.stdout[-400:] + proc.stderr[-400:]) if not cli_ok else "")
    # C2 --require-signature：无签名 bundle -> INVALID_EVIDENCE
    proc = subprocess.run(
        cli_cmd + ["--task", "E2", "--evidence-dir", evidence_dir,
                   "--artifact-root", artifact_root, "--no-collect",
                   "--require-signature", "--trust-root", TRUST_ROOT, "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=300,
        cwd=PROJECT_ROOT)
    # evidence_dir 带 sidecar 签名 -> 仍然可信；再跑一次无 sidecar 的目录
    unsigned_proc = subprocess.run(
        cli_cmd + ["--task", "E2", "--evidence-dir", unsigned_dir,
                   "--artifact-root", unsigned_artifacts, "--no-collect",
                   "--require-signature", "--trust-root", TRUST_ROOT, "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=300,
        cwd=PROJECT_ROOT)
    ok("C2a --require-signature + 已签 bundle -> 仍然通过",
       proc.returncode == 0 and '"VERIFIED_PASS"' in proc.stdout,
       (proc.stdout[-300:] + proc.stderr[-300:])
       if proc.returncode != 0 else "")
    ok("C2b --require-signature + 无签名 bundle -> INVALID_EVIDENCE（exit 1）",
       unsigned_proc.returncode == 1 and '"INVALID_EVIDENCE"' in unsigned_proc.stdout,
       (unsigned_proc.stdout[-300:] + unsigned_proc.stderr[-300:])
       if unsigned_proc.returncode != 1 else "")
    # C3 互斥参数
    proc = subprocess.run(
        cli_cmd + ["--task", "E2", "--require-signature", "--allow-legacy"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
        cwd=PROJECT_ROOT)
    ok("C3 --require-signature 与 --allow-legacy 互斥",
       proc.returncode != 0 and "mutually exclusive" in (proc.stderr + proc.stdout),
       str(proc.returncode))

    print("\n%d checks, %d failures" % (_checks, len(_failures)))
    if _failures:
        print("FAILED:")
        for item in _failures:
            print("  - %s" % item)
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
