#!/usr/bin/env python3
"""Phase 1.62 Smoke Test —— 完整闭环。

验证：Execution Identity → Fingerprint → Run Manifest → Attestation → Verify
"""

import os
import sys
import tempfile
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATOR = os.path.dirname(os.path.dirname(_HERE))  # execution -> validator
_TOOLS = os.path.dirname(_VALIDATOR)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))

for p in (_VALIDATOR, _TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

from provenance import trust_store, signing  # noqa: E402
from provenance.signature_schema import SCOPE_ATTEST_EXECUTION  # noqa: E402
import execution  # noqa: E402  # execution module lives directly under validator/

PROJECT_ROOT = _PROJECT_ROOT

checks = 0
failures = 0


def check(name, ok, detail=""):
    global checks, failures
    checks += 1
    if ok:
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name} {detail}")


# ============================================================ Setup: 临时信任根

tmp_trust_dir = tempfile.mkdtemp(prefix="phase162_trust_")
trust_root_path = os.path.join(tmp_trust_dir, "trust_root.json")

try:
    ts = trust_store.TrustStore(trust_root_path=trust_root_path,
                                 project_root=PROJECT_ROOT)
    ts.initialize()
    # 生成一把带 attest_execution scope 的测试密钥
    record = signing.generate_and_register(
        subject="local_executor_phase162",
        scopes=["attest_execution", "issue_evidence"],
        trust_store=ts,
        project_root=PROJECT_ROOT,
    )
    signer_key_id = record["key_id"]
    check("key generated", signer_key_id.startswith("PROVKEY-"))
    print(f"  key_id = {signer_key_id}")
    print(f"  trust_root = {trust_root_path}")

    # ============================================================ Execution Identity

    ident = execution.ExecutionIdentity.create(
        feature_id="health",
        behavior_id="damage",
        scenario_id="health_basic",
        contract_version="1.0.0",
    )
    check("run_id is UUIDv4", execution.is_valid_uuidv4(ident.run_id),
          f"run_id={ident.run_id}")
    check("execution_id is UUIDv4", execution.is_valid_uuidv4(ident.execution_id))
    check("run_id != execution_id", ident.run_id != ident.execution_id)
    check("validate() passes", not ident.validate())

    ident = ident.mark_started()
    check("status RUNNING", ident.execution_status == "RUNNING")

    ident = ident.mark_completed("SUCCEEDED")
    check("status SUCCEEDED", ident.execution_status == "SUCCEEDED")
    check("completed_at filled", bool(ident.completed_at))

    ident2 = execution.ExecutionIdentity.create(feature_id="collect_pickup")
    check("different run_id on new ident", ident.run_id != ident2.run_id)

    # ============================================================ Fingerprint

    fps = execution.collect_all(
        PROJECT_ROOT,
        feature_id="health", behavior_id="damage",
        replay_count=2, timeout_seconds=120,
    )
    check("has environment_fingerprint", bool(fps.environment.get("fingerprint")))
    check("has source_fingerprint", bool(fps.source.get("fingerprint")))
    check("has collector_fingerprint", bool(fps.collector.get("fingerprint")))
    check("has exec_config_fingerprint",
          bool(fps.execution_config.get("fingerprint")))
    check("collector entrypoint set",
          fps.collector.get("collector_entrypoint") ==
          "scene_composer.feature_behavior_evidence:verify_feature")
    check("collector has source files",
          len(fps.collector.get("collector_source_files") or []) >= 1)

    # ============================================================ Run Manifest

    manifest = execution.RunManifest(
        run_id=ident.run_id,
        execution_id=ident.execution_id,
        source_fingerprint=fps.source["fingerprint"],
        environment_fingerprint=fps.environment["fingerprint"],
        collector_fingerprint=fps.collector["fingerprint"],
        execution_config_fingerprint=fps.execution_config["fingerprint"],
        feature_id=ident.feature_id,
        behavior_id=ident.behavior_id,
        contract_version=ident.contract_version,
        parent_run_id=ident.parent_run_id,
    )
    manifest.add_artifact(execution.make_artifact_entry(
        artifact_id="behavior_result",
        artifact_type="replay_result",
        relative_path=".ai/tmp/behavior/test_run/result.json",
        sha256="deadbeef" * 8,
        size_bytes=1024,
    ))
    manifest.add_artifact(execution.make_artifact_entry(
        artifact_id="behavior_result_r2",
        artifact_type="replay_result",
        relative_path=".ai/tmp/behavior/test_run/result_r2.json",
        sha256="cafebabe" * 8,
        size_bytes=1024,
    ))
    manifest.complete(started_at=ident.started_at, completed_at=ident.completed_at,
                       execution_status=ident.execution_status)
    manifest_doc = manifest.to_dict()
    check("manifest_digest non-empty", bool(manifest_doc.get("manifest_digest")))
    check("manifest_digest revalidates",
          execution.compute_manifest_digest(manifest_doc) ==
          manifest_doc["manifest_digest"])
    errors = execution.RunManifest.validate_manifest(manifest_doc)
    check("validate_manifest passes", not errors, str(errors))

    # ============================================================ Attestation 签发

    attestation_result = execution.attest_execution(
        manifest=manifest_doc,
        trust_level="LOCAL_ISOLATED",
        trust_store=ts,
        project_root=PROJECT_ROOT,
        signer_key_id=signer_key_id,
        execution_status="SUCCEEDED",
    )
    check("attestation_result has attestation",
          isinstance(attestation_result.get("attestation"), dict))
    check("attestation_result has signature_envelope",
          isinstance(attestation_result.get("signature_envelope"), dict))

    attestation_doc = attestation_result["attestation"]
    envelope = attestation_result["signature_envelope"]
    check("attestation attestation_id set",
          execution.is_valid_uuidv4(attestation_doc["attestation_id"]))
    check("attestation run_id matches manifest",
          attestation_doc["run_id"] == manifest_doc["run_id"])
    check("attestation manifest_digest matches",
          attestation_doc["manifest_digest"] == manifest_doc["manifest_digest"])
    check("attestation trust_level is LOCAL_ISOLATED",
          attestation_doc["trust_level"] == "LOCAL_ISOLATED")
    check("signature envelope scope is attest_execution",
          envelope["scope"] == "attest_execution")

    # ============================================================ Attestation 验证

    verify = execution.verify_attestation(
        attestation=attestation_doc,
        signature_envelope=envelope,
        manifest=manifest_doc,
        trust_store=ts,
    )
    check("verify ok", verify["ok"], verify.get("reason"))
    check("verify status ATTESTED_VERIFIED", verify["status"] == "ATTESTED_VERIFIED")
    check("verify signer_subject matches",
          verify.get("signer_subject") == "local_executor_phase162")

    # 带预期 run_id 的验证
    verify2 = execution.verify_attestation(
        attestation=attestation_doc,
        signature_envelope=envelope,
        manifest=manifest_doc,
        trust_store=ts,
        expected_run_id=ident.run_id,
    )
    check("verify with expected_run_id passes", verify2["ok"])

    # 错误 run_id → 失败
    verify_bad = execution.verify_attestation(
        attestation=attestation_doc,
        signature_envelope=envelope,
        manifest=manifest_doc,
        trust_store=ts,
        expected_run_id=execution.new_run_id(),
    )
    check("wrong run_id rejected",
          verify_bad["status"] == "RUN_ID_MISMATCH")

    # ============================================================ 攻击场景模拟

    # E01: Manifest 内容被改（但 manifest_digest 保持旧值）→ manifest_digest 自洽检查失败
    import copy
    tampered_manifest = copy.deepcopy(manifest_doc)
    tampered_manifest["feature_id"] = "fake_feature"
    # 故意不重算 manifest_digest → manifest.validate_manifest 应该自己发现
    verify_e01 = execution.RunManifest.validate_manifest(tampered_manifest)
    check("E01 manifest tamper → validate rejects",
          bool(verify_e01), str(verify_e01))

    # E09: Attestation 的 environment_fingerprint 被改，并重算 attestation_digest
    #      但签名是对旧 digest 签的 → Phase 1.61 签名验证 DIGEST_MISMATCH
    #      这是防御链的正确行为：attestation_digest 是签名覆盖的核心摘要
    attestation_result2 = execution.attest_execution(
        manifest=manifest_doc,
        trust_level="LOCAL_ISOLATED",
        trust_store=ts,
        project_root=PROJECT_ROOT,
        signer_key_id=signer_key_id,
        execution_status="SUCCEEDED",
    )
    attest2 = attestation_result2["attestation"]
    tampered_attest_e09 = copy.deepcopy(attest2)
    tampered_attest_e09["environment_fingerprint"] = "b" * 64
    del tampered_attest_e09["attestation_digest"]
    tampered_attest_e09["attestation_digest"] = execution.compute_attestation_digest(
        tampered_attest_e09)
    verify_e09 = execution.verify_attestation(
        attestation=tampered_attest_e09,
        signature_envelope=attestation_result2["signature_envelope"],
        manifest=manifest_doc, trust_store=ts,
    )
    # 签名 envelope 里的 content_digest 是旧的 attestation_digest
    # Attestation 里的 attestation_digest 被攻击者重算了 → 不匹配
    check("E09 attestation env_fp tamper → SIGNATURE_INVALID/DIGEST_MISMATCH",
          verify_e09["status"] in ("ATTESTATION_INVALID",),
          verify_e09.get("reason", ""))

    # 补充：如果改 Attestation 后**不**重算 digest → attestation 文档自洽性检查失败
    tampered_attest_e09b = copy.deepcopy(attest2)
    tampered_attest_e09b["environment_fingerprint"] = "c" * 64
    # 故意不重算 attestation_digest
    verify_e09b = execution.verify_attestation(
        attestation=tampered_attest_e09b,
        signature_envelope=attestation_result2["signature_envelope"],
        manifest=manifest_doc, trust_store=ts,
    )
    check("E09b attestation tamper w/o digest recompile → ATTESTATION_INVALID",
          verify_e09b["status"] == "ATTESTATION_INVALID",
          verify_e09b.get("reason", ""))

    # E13: 修改 Attestation 后重签名 → digest mismatch
    tampered_attest = copy.deepcopy(attestation_doc)
    tampered_attest["execution_status"] = "FAILED"  # 伪造状态
    # 重算 digest（但签名是对旧 digest 的）
    del tampered_attest["attestation_digest"]
    tampered_attest["attestation_digest"] = execution.compute_attestation_digest(
        tampered_attest)
    verify_e13 = execution.verify_attestation(
        attestation=tampered_attest, signature_envelope=envelope,
        manifest=manifest_doc, trust_store=ts,
    )
    check("E13 attestation tamper → SIGNATURE_INVALID/ATTESTATION_INVALID",
          verify_e13["status"] in ("ATTESTATION_INVALID", "SIGNATURE_INVALID"))

    # E02: 替换 run_id → RUN_ID_MISMATCH
    tampered_attest2 = copy.deepcopy(attestation_doc)
    new_aid = execution.new_run_id()
    tampered_attest2["run_id"] = execution.new_run_id()
    tampered_attest2["attestation_id"] = new_aid
    tampered_attest2["attestation_digest"] = execution.compute_attestation_digest(
        tampered_attest2)
    verify_e02 = execution.verify_attestation(
        attestation=tampered_attest2, signature_envelope=envelope,
        manifest=manifest_doc, trust_store=ts,
    )
    check("E02 run_id replace → RUN_ID_MISMATCH or INVALID",
          verify_e02["status"] in ("RUN_ID_MISMATCH", "ATTESTATION_INVALID"))

    # ============================================================ 复用 Evidence 签名冒充 Attestation 失败

    # 用 Evidence scope 签一个 envelope，尝试作为 Attestation
    # （实际 verify_envelope 会检查 scope 不匹配 → SCOPE_MISMATCH）
    from provenance.signing import build_envelope, sign_envelope
    fake_envelope = build_envelope(
        object_type="evidence_bundle",  # 故意用错 type
        object_id="fake-bundle",
        object_version="1",
        content_digest="aa" * 32,
        digest_scheme="test",
        signer_key_id=signer_key_id,
    )
    signed_fake = sign_envelope(fake_envelope, trust_store=ts,
                                 project_root=PROJECT_ROOT)
    verify_fake = execution.verify_attestation(
        attestation=attestation_doc,
        signature_envelope=signed_fake,
        manifest=manifest_doc,
        trust_store=ts,
    )
    check("E15 Evidence sig used as Attestation → rejected",
          verify_fake["status"] in ("SIGNER_UNAUTHORIZED", "ATTESTATION_INVALID"))

finally:
    shutil.rmtree(tmp_trust_dir, ignore_errors=True)

# ============================================================ 汇总

print()
print(f"===== Phase 1.62 Smoke Test: {checks} checks, {failures} failures =====")
sys.exit(1 if failures else 0)
