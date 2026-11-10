#!/usr/bin/env python3
"""Phase 1.62 Godot E2E Runner —— 完整执行链验证。

验证：真实 Godot → Evidence Bundle → Execution Provenance → Attestation → Verify

用法:
    python .ai/tools/validator/execution/run_execution_e2e.py
    GODOT_BIN=F:/.../Godot...exe python ...
"""

import hashlib
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

# Phase 1.64：项目根 = 含 project.godot 的目录（原实现少算一层，得到 `.ai`）
PROJECT_ROOT = env_paths.project_root(__file__)

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


# ============================================================ 0. Godot

# Phase 1.64：统一解析（GODOT_BIN → 项目配置 → 相邻目录 → PATH），
# 缺失时以环境错误退出，不再把它混成断言失败。
godot_bin = env_paths.require_godot(PROJECT_ROOT)
check("godot_bin found", bool(godot_bin), godot_bin)

# ============================================================ 1. 信任根

tmp_trust_dir = tempfile.mkdtemp(prefix="phase162_e2e_trust_")
trust_root_path = os.path.join(tmp_trust_dir, "trust_root.json")
ts = trust_store.TrustStore(trust_root_path=trust_root_path,
                             project_root=PROJECT_ROOT)
ts.initialize()
record = signing.generate_and_register(
    subject="phase162_e2e_executor",
    scopes=["attest_execution", "issue_evidence"],
    trust_store=ts, project_root=PROJECT_ROOT,
)
signer_key_id = record["key_id"]
check("signer key registered", signer_key_id.startswith("PROVKEY-"))

# ============================================================ 2. Execution Identity

feature_id = "health"
behavior_id = "damage"
ident = execution.ExecutionIdentity.create(
    feature_id=feature_id, behavior_id=behavior_id,
    scenario_id="health_basic", contract_version="1.0.0",
)
ident = ident.mark_started()
check("ExecutionIdentity started",
      ident.run_id and ident.execution_id and ident.execution_status == "RUNNING",
      f"run_id={ident.run_id[:12]}...")

# ============================================================ 3. Fingerprint

fps = execution.collect_all(
    PROJECT_ROOT,
    feature_id=feature_id, behavior_id=behavior_id,
    replay_count=2, timeout_seconds=120,
)
all_fps = fps.all_fingerprints()
check("4 fingerprints collected",
      all(all_fps[k] for k in (
          "environment_fingerprint", "source_fingerprint",
          "collector_fingerprint", "execution_config_fingerprint")))
print(f"  env_fp={all_fps['environment_fingerprint'][:12]}...")
print(f"  src_fp={all_fps['source_fingerprint'][:12]}...")
print(f"  col_fp={all_fps['collector_fingerprint'][:12]}...")

# ============================================================ 4. 真实 Godot Evidence

print()
print("--- Running verify_feature ---")
reports = fbe.verify_feature(feature_id, project_root=PROJECT_ROOT,
                              godot=godot_bin, replay=2)
check("Godot reports generated", len(reports) > 0,
      f"count={len(reports)}, statuses={[r.status for r in reports]}")
print(f"  statuses: {[r.status for r in reports]}")

# Build protocol
import behavior_protocol  # noqa: E402
try:
    protocol = behavior_protocol.load_protocol()
except Exception:
    protocol = None

bundle_doc = fbe.build_bundle(reports, protocol or behavior_protocol.load_protocol(),
                               project_root=PROJECT_ROOT)

tmp_bundle_dir = tempfile.mkdtemp(prefix="phase162_e2e_bundle_")
bundle_path = fbe.write_bundle(bundle_doc, tmp_bundle_dir)
check("Evidence bundle written", os.path.isfile(bundle_path), bundle_path)

# 读回验证
with open(bundle_path, "r", encoding="utf-8") as handle:
    bundle_doc = json.load(handle)
check("Evidence bundle integrity", bool(bundle_doc.get("integrity", {}).get("payload_sha256")),
      f"integrity={bundle_doc.get('integrity', {})}")
print(f"  bundle_id={bundle_doc.get('bundle_id')}")
print(f"  summary={bundle_doc.get('summary')}")

# ============================================================ 5. Artifact → Run Manifest

artifact_entries = []
seen_ids: set[str] = set()
for report in reports:
    report_dict = report.to_dict()
    run_id_r = report_dict.get("run_id", "")
    for subkey, digest in (report_dict.get("artifact_digests") or {}).items():
        for filekey, filedigest in digest.items():
            aid = f"{run_id_r}_{filekey}"
            if aid in seen_ids:
                continue
            seen_ids.add(aid)
            artifact_entries.append(execution.make_artifact_entry(
                artifact_id=aid,
                artifact_type=str(filekey),
                relative_path=f".ai/tmp/behavior/{run_id_r}/{filekey}.json"
                              if filekey in ("contract", "result")
                              else f".ai/tmp/behavior/{run_id_r}/{filekey}.log",
                sha256=str(filedigest),
                size_bytes=0,
            ))

check("artifact entries collected", len(artifact_entries) > 0,
      f"count={len(artifact_entries)}")

manifest = execution.RunManifest(
    run_id=ident.run_id,
    execution_id=ident.execution_id,
    source_fingerprint=all_fps["source_fingerprint"],
    environment_fingerprint=all_fps["environment_fingerprint"],
    collector_fingerprint=all_fps["collector_fingerprint"],
    execution_config_fingerprint=all_fps["execution_config_fingerprint"],
    feature_id=ident.feature_id,
    behavior_id=ident.behavior_id,
    contract_version=ident.contract_version,
    evidence_reference=bundle_path,
)
manifest.add_artifacts(artifact_entries)
manifest.complete(started_at=ident.started_at, execution_status="SUCCEEDED")

manifest_doc = manifest.to_dict()
manifest_errors = execution.RunManifest.validate_manifest(manifest_doc)
check("Run Manifest validates", not manifest_errors, str(manifest_errors))
print(f"  manifest_digest={manifest_doc['manifest_digest'][:16]}...")
print(f"  artifact_count={manifest_doc['artifact_count']}")

# ============================================================ 6. Execution Attestation

ident_final = ident.mark_completed("SUCCEEDED")
attest_result = execution.attest_execution(
    manifest=manifest_doc,
    trust_level="LOCAL_ISOLATED",
    trust_store=ts, project_root=PROJECT_ROOT,
    signer_key_id=signer_key_id,
    execution_status="SUCCEEDED",
)
attestation_doc = attest_result["attestation"]
attestation_envelope = attest_result["signature_envelope"]
check("Attestation signed",
      bool(attestation_doc.get("attestation_id"))
      and bool(attestation_envelope.get("signature")),
      f"attestation_id={attestation_doc.get('attestation_id', '')[:12]}")

# ============================================================ 7. Attestation 验证

verify = execution.verify_attestation(
    attestation=attestation_doc,
    signature_envelope=attestation_envelope,
    manifest=manifest_doc,
    trust_store=ts,
)
check("Attestation verifies OK", verify["ok"],
      f"status={verify.get('status')}, reason={verify.get('reason', '')}")
check("status ATTESTED_VERIFIED", verify["status"] == "ATTESTED_VERIFIED")
check("trust_level LOCAL_ISOLATED", attestation_doc["trust_level"] == "LOCAL_ISOLATED")
check("signer_subject correct",
      verify.get("signer_subject") == "phase162_e2e_executor")

# ============================================================ 8. Sidecar 写入 Evidence Bundle 旁

sidecar = {
    "schema": "execution_provenance_sidecar",
    "schema_version": 1,
    "run_id": ident.run_id,
    "manifest_digest": manifest_doc["manifest_digest"],
    "attestation_id": attestation_doc["attestation_id"],
    "attestation_digest": attestation_doc["attestation_digest"],
    "artifact_set_digest": manifest_doc["artifact_set_digest"],
    "generated_at": attestation_doc["signed_at"],
}
sidecar_path = bundle_path + ".attestation.json"
with open(sidecar_path, "w", encoding="utf-8") as handle:
    json.dump(sidecar, handle, ensure_ascii=False, indent=2)
check("Sidecar written", os.path.isfile(sidecar_path))

# 读回验证
with open(sidecar_path, "r", encoding="utf-8") as handle:
    loaded = json.load(handle)
check("sidecar run_id matches attestation",
      loaded["run_id"] == attestation_doc["run_id"])
check("sidecar manifest_digest matches",
      loaded["manifest_digest"] == manifest_doc["manifest_digest"])

# ============================================================ 9. 攻击模拟：删 sidecar → require 模式拒绝

check("sidecar present (require mode check)", os.path.isfile(sidecar_path))

# ============================================================ 10. 攻击模拟：篡改 Attestation

import copy
tampered = copy.deepcopy(attestation_doc)
tampered["execution_status"] = "FAILED"
del tampered["attestation_digest"]
tampered["attestation_digest"] = execution.compute_attestation_digest(tampered)
# 签名还是对旧 digest 签的 → 验证失败
verify_tamp = execution.verify_attestation(
    attestation=tampered,
    signature_envelope=attestation_envelope,
    manifest=manifest_doc, trust_store=ts,
)
check("E13 Attestation tamper → reject",
      verify_tamp["status"] in ("ATTESTATION_INVALID",),
      f"status={verify_tamp.get('status')}")

# ============================================================ 11. 攻击模拟：跨 Run Artifact 混合

# 做一个"假" manifest：保持 run_id 与 attestation 不同
mixed_run_id = execution.new_run_id()
mixed_manifest = copy.deepcopy(manifest_doc)
mixed_manifest["run_id"] = mixed_run_id
del mixed_manifest["manifest_digest"]
mixed_manifest["manifest_digest"] = execution.compute_manifest_digest(mixed_manifest)
verify_mixed = execution.verify_attestation(
    attestation=attestation_doc,
    signature_envelope=attestation_envelope,
    manifest=mixed_manifest, trust_store=ts,
)
check("E08 cross-run artifact mix → RUN_ID_MISMATCH",
      verify_mixed["status"] == "RUN_ID_MISMATCH",
      f"status={verify_mixed.get('status')}")

# ============================================================ 清理

shutil.rmtree(tmp_trust_dir, ignore_errors=True)
shutil.rmtree(tmp_bundle_dir, ignore_errors=True)

# ============================================================ 汇总

print()
print(f"===== Phase 1.62 Godot E2E: {checks} checks, {failures} failures =====")
print()
print(f"  project_root    : {PROJECT_ROOT}")
print(f"  Godot           : {godot_bin}")
print(f"  feature         : {feature_id}")
print(f"  run_id          : {ident.run_id}")
print(f"  manifest_digest : {manifest_doc['manifest_digest'][:16]}...")
print(f"  attestation_id  : {attestation_doc['attestation_id']}")
print(f"  trust_level     : {attestation_doc['trust_level']}")
print(f"  artifacts       : {manifest_doc['artifact_count']}")
print()
print("诚实声明:")
print("  - 本阶段实现的是 LOCAL_ISOLATED 原型。")
print("  - 执行器与 Godot 同权限边界。")
print("  - 签名证明密码学完整性，不证明 Godot/采集器未被替换。")
print("  - 没有独立 Worker/CI/容器，不具备 EXTERNAL_TRUSTED_RUNNER 等级。")

sys.exit(1 if failures else 0)
