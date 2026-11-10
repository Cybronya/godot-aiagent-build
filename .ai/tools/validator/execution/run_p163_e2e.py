#!/usr/bin/env python3
"""Phase 1.63 全链真实 E2E Runner（持久化产物版）。

对三个不同验证特征的正式支持 Feature 各跑一条完整链：

    health        （状态转换）
    collect_pickup（事件传播）
    save_game     （持久化）

链路（每一环都真实执行，不留临时产物）：

    1. 契约检查（fbe.build_contracts -> CONTRACT_PRESENT）
    2. 绑定检查（binding_gate_status -> APPROVED_BINDING）
    3. 真实 Godot 采集（verify_feature, replay=2）
    4. Evidence Bundle（write_bundle -> 持久 evidence 目录 + integrity）
    5. Evidence 签名（独立信任根 Ed25519，scope=issue_evidence）
    6. Execution Manifest（真实 artifact digests -> runs/<run_id>/manifest.json）
    7. Execution Attestation（scope=attest_execution 签名 -> runs/<run_id>/）
    8. Attestation 验证（verify_attestation -> ATTESTED_VERIFIED）
    9. Evaluation（evidence_eval CLI --no-collect，复用 1.58 全链）

诚实声明：trust_level = LOCAL_ISOLATED（签名验证通过不等于执行过程真实；
无 CI/KMS/独立执行器）。

用法：python .ai/tools/validator/execution/run_p163_e2e.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATOR = os.path.dirname(_HERE)
_TOOLS = os.path.dirname(_VALIDATOR)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))
for _p in (_VALIDATOR, _TOOLS, os.path.join(_TOOLS, "scene_composer"),
           os.path.join(_TOOLS, "evaluation"), os.path.join(_VALIDATOR, "provenance"),
           os.path.join(_VALIDATOR, "execution")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from provenance import trust_store, signing          # noqa: E402
import execution                                     # noqa: E402
import feature_behavior_evidence as fbe              # noqa: E402
import behavior_protocol                             # noqa: E402
import binding_candidates as bc                      # noqa: E402
import trace_bindings as tb                          # noqa: E402

PROJECT_ROOT = _PROJECT_ROOT
OUT_ROOT = os.path.join(PROJECT_ROOT, ".ai", "tmp", "p163_e2e")
EVIDENCE_DIR = os.path.join(OUT_ROOT, "evidence")
RUNS_DIR = os.path.join(OUT_ROOT, "runs")

# 三个验证特征：状态转换 / 事件传播 / 持久化
FEATURES = ["health", "collect_pickup", "save_game"]
EVIDENCE_KEY = "PROVKEY-5aa9912c2dbb6587"   # issue_evidence, attest_execution


def find_godot() -> str:
    cands = [os.path.join(_PROJECT_ROOT, "..", "Godot_v4.7-stable_win64_console.exe"),
             os.path.join(_PROJECT_ROOT, "..", "Godot_v4.7-stable_win64.exe")]
    for c in cands:
        if os.path.isfile(c):
            return c
    raise SystemExit("godot executable not found")


def run_one(feature_id: str, godot_bin: str, ts, checks: list) -> dict:
    result = {"feature": feature_id, "checks": 0, "failures": 0,
              "run_id": None, "artifacts": 0, "attestation": "", "evaluation": ""}

    def check(name, ok, detail=""):
        checks.append((feature_id, name, bool(ok), detail))
        result["checks" if ok else "failures"] += 1 if ok else 0
        if not ok:
            result["failures"] += 1

    # 1. 契约
    contracts, _reports = fbe.build_contracts(feature_id, "Features")
    check("contract_present", bool(contracts),
          "%d behaviors" % len(contracts))

    # 2. 绑定
    gates = [bc.binding_gate_status(feature_id, str(c["behavior"]))
             for c in contracts]
    check("binding_approved", all(g["status"] == bc.APPROVED_BINDING for g in gates),
          "; ".join("%s=%s" % (g["binding_id"], g["status"]) for g in gates))

    # 3. 真实采集（独立批次 -> 持久 evidence 目录）
    reports = fbe.verify_feature(feature_id, project_root=PROJECT_ROOT,
                                 godot=godot_bin, replay=2)
    statuses = [r.status for r in reports]
    check("godot_collection", all(s == "PASS" for s in statuses), str(statuses))

    # 4. Bundle（持久化 + integrity）
    bundle_doc = fbe.build_bundle(reports, behavior_protocol.load_protocol(),
                                  project_root=PROJECT_ROOT)
    bundle_path = fbe.write_bundle(bundle_doc, EVIDENCE_DIR)
    with open(bundle_path, encoding="utf-8") as handle:
        written = json.load(handle)
    written["integrity"] = {"algorithm": "sha256",
                            "payload_sha256": fbe.bundle_digest(written)}
    with open(bundle_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(written, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    check("bundle_written", os.path.isfile(bundle_path),
          os.path.relpath(bundle_path, PROJECT_ROOT))

    # 5. Evidence 签名（真实独立信任根；摘要与 scheme 用 1.61 标准口径）
    from provenance.verification import recompute_evidence_digest, verify_envelope
    evidence_digest = recompute_evidence_digest(written)
    envelope = signing.sign_object(
        object_type="evidence_bundle", object_id=bundle_doc["bundle_id"],
        object_version="1", content_digest=evidence_digest,
        digest_scheme="evidence-bundle-digest-v1", key_id=EVIDENCE_KEY,
        trust_store=ts, project_root=PROJECT_ROOT)
    sidecar = bundle_path + ".sig.json"
    with open(sidecar, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(envelope, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    verdict = verify_envelope(envelope, object_type="evidence_bundle",
                              object_id=bundle_doc["bundle_id"], object_version="1",
                              expected_digest=evidence_digest,
                              expected_digest_scheme="evidence-bundle-digest-v1",
                              trust_store=ts)
    check("evidence_signed", verdict.get("status") == "SIGNATURE_VALID",
          str(verdict.get("status")))

    # 6. Manifest（真实 artifact digests，持久化）
    ident = execution.ExecutionIdentity.create(
        feature_id=feature_id, behavior_id="",
        scenario_id="%s_p163_e2e" % feature_id, contract_version="1",
    ).mark_started()
    result["run_id"] = ident.run_id
    fps = execution.collect_all(PROJECT_ROOT, feature_id=feature_id,
                                replay_count=2, timeout_seconds=120)
    all_fps = fps.all_fingerprints()
    artifact_entries = []
    for report in reports:
        for subkey, digest in (report.to_dict().get("artifact_digests") or {}).items():
            for filekey, filedigest in digest.items():
                artifact_entries.append(execution.make_artifact_entry(
                    artifact_id="%s_%s" % (subkey, filekey),
                    artifact_type=str(filekey),
                    relative_path=_rel_artifact(subkey, filekey),
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
    check("manifest_valid", not m_errs,
          "digest=%s artifacts=%s" % (manifest_doc["manifest_digest"][:12],
                                      manifest_doc["artifact_count"]))
    result["artifacts"] = manifest_doc["artifact_count"]

    # 7. Attestation（真实信任根，持久化）
    attest = execution.attest_execution(
        manifest=manifest_doc, trust_level="LOCAL_ISOLATED",
        trust_store=ts, project_root=PROJECT_ROOT,
        signer_key_id=EVIDENCE_KEY, execution_status="SUCCEEDED")
    attestation_doc = attest["attestation"]
    attest_envelope = attest["signature_envelope"]

    # 8. Attestation 验证 + 持久化
    verify = execution.verify_attestation(
        attestation=attestation_doc, signature_envelope=attest_envelope,
        manifest=manifest_doc, trust_store=ts)
    check("attestation_verified", verify["ok"] and
          verify["status"] == "ATTESTED_VERIFIED", str(verify.get("status")))
    result["attestation"] = str(verify.get("status"))
    run_dir = os.path.join(RUNS_DIR, ident.run_id)
    os.makedirs(run_dir, exist_ok=True)
    _dump(os.path.join(run_dir, "manifest.json"), manifest_doc)
    _dump(os.path.join(run_dir, "attestation.json"), attestation_doc)
    _dump(os.path.join(run_dir, "attestation.json.sig.json"), attest_envelope)

    # 9. Evaluation（evidence_eval --no-collect 复用 1.58 全链）
    tasks_file = os.path.join(OUT_ROOT, "tasks_e2e.yaml")
    _ensure_tasks(tasks_file)
    argv = [sys.executable, os.path.join(_TOOLS, "evaluation", "evidence_eval.py"),
            "--tasks-file", tasks_file, "--evidence-dir", EVIDENCE_DIR,
            "--no-collect", "--json"]
    proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          timeout=300, cwd=PROJECT_ROOT)
    evaluation_status = ""
    try:
        report = json.loads(proc.stdout[proc.stdout.find("{"):])
        for task in report.get("tasks", []):
            if str(task.get("feature_id")) == feature_id:
                for b in task.get("behaviors", []):
                    if b.get("evaluation_status"):
                        evaluation_status = str(b["evaluation_status"])
                        break
            if evaluation_status:
                break
    except (ValueError, IndexError):
        evaluation_status = "REPORT_UNAVAILABLE"
    result["evaluation"] = evaluation_status
    check("evaluation_verified_pass", evaluation_status == "VERIFIED_PASS",
          evaluation_status)
    return result


def _rel_artifact(subkey: str, filekey: str) -> str:
    return (".ai/tmp/behavior/%s/%s.json" % (subkey, filekey)
            if filekey in ("contract", "result")
            else ".ai/tmp/behavior/%s/%s.log" % (subkey, filekey))


def _dump(path: str, document: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


_TASKS = {
    "E1-P163": ("collect_pickup", "collect_on_contact",
                [{"check": "node.freed", "target": ".", "equals": True},
                 {"check": "signal", "entry": "pickup.collected", "target": ".",
                  "count": 1}]),
    "E2-P163": ("health", "damage",
                [{"check": "health.current", "target": ".", "equals": 1},
                 {"check": "signal", "entry": "health.health_changed", "target": ".",
                  "count": 1}]),
    "E3-P163": ("save_game", "save_slot_persists_world_state",
                [{"check": "savegame.last_slot", "target": "Saver",
                  "equals": "behavior_save"},
                 {"check": "health.current", "target": "World/Player/Health",
                  "equals": 3}]),
}


def _ensure_tasks(path: str) -> None:
    import yaml
    tasks = []
    for task_id, (feature, behavior, expect) in _TASKS.items():
        tasks.append({
            "id": task_id, "title": "Phase 1.63 E2E %s" % feature,
            "requirement": "p163 e2e", "mode": "evidence",
            "feature": feature, "behavior": behavior, "expect": expect,
        })
    document = {"schema": {"id": "evaluation_evidence_tasks", "version": 1},
                "run": {"evidence_dir": EVIDENCE_DIR, "max_age_hours": 24,
                        "artifact_root": ".ai/tmp/behavior"},
                "tasks": tasks}
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(document, handle, allow_unicode=True, sort_keys=False)


def main() -> int:
    godot_bin = find_godot()
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    os.makedirs(RUNS_DIR, exist_ok=True)
    # 本阶段自己的输出目录：清掉上一次 E2E 留下的 bundle/sidecar，
    # 否则同一 Behavior 会出现两条冲突记录（Validator 判 evidence_rejected）。
    import glob as _glob
    for stale in _glob.glob(os.path.join(EVIDENCE_DIR, "*.json")):
        os.remove(stale)
    ts = trust_store.TrustStore(project_root=PROJECT_ROOT)   # 真实独立信任根
    checks: list = []
    results = []
    for feature_id in FEATURES:
        print("=== %s ===" % feature_id)
        results.append(run_one(feature_id, godot_bin, ts, checks))
    total_checks = sum(r["checks"] for r in results)
    total_failed = sum(r["failures"] for r in results)
    for feature_id, name, ok, detail in checks:
        print("%s %s/%s %s" % ("PASS" if ok else "FAIL", feature_id, name, detail))
    print("\n===== Phase 1.63 E2E: %d features, %d checks, %d failures ====="
          % (len(results), total_checks, total_failed))
    print("trust_level = LOCAL_ISOLATED（诚实声明：无 CI/KMS/独立执行器；")
    print("签名验证通过不等于执行过程真实）")
    with open(os.path.join(OUT_ROOT, "e2e_summary.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump({"results": results, "checks": total_checks,
                   "failures": total_failed}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return 0 if not total_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
