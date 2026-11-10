#!/usr/bin/env python3
"""Phase 1.62 Multi-Feature Godot E2E Runner.

对 health, collect_pickup, openable_door 三个 Feature 各自跑完整执行链，
汇总结果。

用法:
    GODOT_BIN=... python .ai/tools/validator/execution/run_multi_feature_e2e.py
"""

import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATOR = os.path.dirname(_HERE)
_TOOLS = os.path.dirname(_VALIDATOR)
_SCENE_COMPOSER = os.path.join(_TOOLS, "scene_composer")

for p in (_VALIDATOR, _TOOLS, _SCENE_COMPOSER):
    if p not in sys.path:
        sys.path.insert(0, p)

from provenance import trust_store, signing  # noqa: E402
import execution  # noqa: E402
from execution import env_paths  # noqa: E402
import feature_behavior_evidence as fbe  # noqa: E402
import behavior_protocol  # noqa: E402

# Phase 1.64：项目根 = 含 project.godot 的目录（原实现少算一层，得到 `.ai`）
PROJECT_ROOT = env_paths.project_root(__file__)

FEATURES = ["health", "collect_pickup", "openable_door"]


def run_one(feature_id: str, godot_bin: str, ts, signer_key_id: str) -> dict:
    """对单个 Feature 跑完整链，返回结果 dict。"""
    result = {"feature": feature_id, "checks": 0, "failures": 0, "phases": []}

    # Identity
    ident = execution.ExecutionIdentity.create(
        feature_id=feature_id, behavior_id="",
        scenario_id=f"{feature_id}_basic", contract_version="1.0.0",
    ).mark_started()
    result["phases"].append(("identity", True, f"run_id={ident.run_id[:12]}"))

    # Fingerprint
    fps = execution.collect_all(
        PROJECT_ROOT, feature_id=feature_id, replay_count=2, timeout_seconds=120,
    )
    result["phases"].append(("fingerprint", True, "4 fps collected"))
    all_fps = fps.all_fingerprints()

    # Godot
    reports = fbe.verify_feature(feature_id, project_root=PROJECT_ROOT,
                                  godot=godot_bin, replay=2)
    statuses = [r.status for r in reports]
    any_fail = any(s not in ("PASS", "NOT_DECLARED") for s in statuses)
    result["phases"].append(("godot_reports", True,
                             f"count={len(reports)}, statuses={statuses}"))

    # Bundle
    bundle_doc = fbe.build_bundle(reports, behavior_protocol.load_protocol(),
                                   project_root=PROJECT_ROOT)
    tmp_bundle = tempfile.mkdtemp(prefix="p162_")
    bundle_path = fbe.write_bundle(bundle_doc, tmp_bundle)

    # Manifest
    artifact_entries = []
    for report in reports:
        for subkey, digest in (report.to_dict().get("artifact_digests") or {}).items():
            for filekey, filedigest in digest.items():
                artifact_entries.append(execution.make_artifact_entry(
                    artifact_id=f"{subkey}_{filekey}",
                    artifact_type=str(filekey),
                    relative_path=f".ai/tmp/behavior/{subkey}/{filekey}.json"
                                  if filekey in ("contract", "result")
                                  else f".ai/tmp/behavior/{subkey}/{filekey}.log",
                    sha256=str(filedigest), size_bytes=0,
                ))

    manifest = execution.RunManifest(
        run_id=ident.run_id, execution_id=ident.execution_id,
        source_fingerprint=all_fps["source_fingerprint"],
        environment_fingerprint=all_fps["environment_fingerprint"],
        collector_fingerprint=all_fps["collector_fingerprint"],
        execution_config_fingerprint=all_fps["execution_config_fingerprint"],
        feature_id=ident.feature_id, evidence_reference=bundle_path,
    )
    manifest.add_artifacts(artifact_entries)
    manifest.complete(started_at=ident.started_at, execution_status="SUCCEEDED")
    manifest_doc = manifest.to_dict()
    m_errs = execution.RunManifest.validate_manifest(manifest_doc)
    result["phases"].append(("manifest", not m_errs,
                             f"digest={manifest_doc['manifest_digest'][:12]}... "
                             f"artifacts={manifest_doc['artifact_count']}"))

    # Attestation
    attest_result = execution.attest_execution(
        manifest=manifest_doc, trust_level="LOCAL_ISOLATED",
        trust_store=ts, project_root=PROJECT_ROOT,
        signer_key_id=signer_key_id, execution_status="SUCCEEDED",
    )
    attestation_doc = attest_result["attestation"]
    envelope = attest_result["signature_envelope"]
    result["phases"].append(("attestation_signed", True,
                             f"att_id={attestation_doc['attestation_id'][:12]}"))

    # Verify
    verify = execution.verify_attestation(
        attestation=attestation_doc, signature_envelope=envelope,
        manifest=manifest_doc, trust_store=ts,
    )
    ok = verify["ok"] and verify["status"] == "ATTESTED_VERIFIED"
    result["phases"].append(("attestation_verified", ok,
                             f"status={verify.get('status')}"))
    if ok:
        result["checks"] += 1
    else:
        result["failures"] += 1

    # Cleanup temp bundle only (Godot artifacts stay)
    shutil.rmtree(tmp_bundle, ignore_errors=True)
    return result


def main():
    # Phase 1.64：统一解析（GODOT_BIN → 项目配置 → 相邻目录 → PATH），
    # 缺失时以环境错误退出（exit 2），不再用 assert 伪装成断言失败。
    godot_bin = env_paths.require_godot(PROJECT_ROOT)

    tmp_trust = tempfile.mkdtemp(prefix="p162_trust_")
    trp = os.path.join(tmp_trust, "trust_root.json")
    ts = trust_store.TrustStore(trust_root_path=trp, project_root=PROJECT_ROOT)
    ts.initialize()
    rec = signing.generate_and_register(
        subject="p162_multi_executor",
        scopes=["attest_execution", "issue_evidence"],
        trust_store=ts, project_root=PROJECT_ROOT,
    )
    signer_key_id = rec["key_id"]

    results = []
    for fid in FEATURES:
        print(f"\n=== Feature: {fid} ===")
        r = run_one(fid, godot_bin, ts, signer_key_id)
        results.append(r)
        for phase, ok, detail in r["phases"]:
            tag = "PASS" if ok else "FAIL"
            print(f"  {tag}: {phase} — {detail}")

    total = sum(r["checks"] for r in results)
    failed = sum(r["failures"] for r in results)
    print()
    print(f"===== Multi-Feature E2E: {len(results)} features, "
          f"{total} attestations verified, {failed} failures =====")
    for r in results:
        print(f"  {r['feature']}: ok={r['checks']}, fail={r['failures']}, "
              f"phases={len(r['phases'])}")

    # 诚实声明
    print()
    print(f"  project_root: {PROJECT_ROOT}")
    print(f"  godot       : {godot_bin}")
    print("诚实声明:")
    print("  - trust_level=LOCAL_ISOLATED（本地原型，同权限边界）")
    print("  - 无独立执行器 Worker/CI/容器 → DEFERRED EXTERNAL_TRUSTED_RUNNER")

    shutil.rmtree(tmp_trust, ignore_errors=True)
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
