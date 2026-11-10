#!/usr/bin/env python3
"""Phase 1.64 分批 Behavior 验证 Runner。

对一批正式支持的 Feature 逐条跑完整链，并把 Evaluation 的结论落到**逐 Behavior**粒度：

    契约 → 已审批 Binding 门禁 → 真实 Godot 采集（replay=2，独立 user:// tag）
    → Evidence Bundle（integrity）→ Ed25519 签名（独立信任根，scope=issue_evidence）
    → Execution Manifest（真实 artifact digests）→ Attestation（scope=attest_execution）
    → 验签 → Evaluation（evidence_eval --no-collect，同一批证据重算契约期望）

与 1.62/1.63 的 E2E Runner 的关系：**复用同一批函数与同一信任根**，不重新实现验证链，
也不改 1.63 的产物目录。区别只有三点：

1. 批次、输出目录、user:// 标签由 CLI 指定（每次运行独立，不互相覆盖）；
2. 评估任务的 expected 从**已审批 Binding** 读取（不手写期望）；
3. 评估结论按 Behavior 汇总，而不是每个 Feature 只取第一条。

信任边界与 1.63 相同：trust_level = LOCAL_ISOLATED，签名证明密码学完整性，
不证明执行过程真实（无 CI/KMS/独立执行器）。

用法：
    python .ai/tools/validator/execution/run_p164_batch.py \
        --label B1 --features save_game,i_frames,openable_door \
        --out-root .ai/tmp/p164/batch1
退出码：0 全部 Behavior 的 Evaluation 均为 VERIFIED_PASS；1 存在失败/不完整；2 环境错误。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATOR = os.path.dirname(_HERE)
_TOOLS = os.path.dirname(_VALIDATOR)
for _p in (_VALIDATOR, _TOOLS, os.path.join(_TOOLS, "scene_composer"),
           os.path.join(_TOOLS, "evaluation"), os.path.join(_VALIDATOR, "provenance"),
           _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from provenance import trust_store, signing          # noqa: E402
from provenance.verification import (                # noqa: E402
    recompute_evidence_digest, verify_envelope,
)
import behavior_protocol                             # noqa: E402
import binding_candidates as bc                      # noqa: E402
import trace_bindings as tb                         # noqa: E402
import execution                                     # noqa: E402
from execution import env_paths                      # noqa: E402
import feature_behavior_evidence as fbe              # noqa: E402

PROJECT_ROOT = env_paths.project_root(__file__)
EVIDENCE_KEY = "PROVKEY-5aa9912c2dbb6587"   # issue_evidence + attest_execution


def _dump(path: str, document) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _rel_artifact(subkey: str, filekey: str) -> str:
    return (".ai/tmp/behavior/%s/%s.json" % (subkey, filekey)
            if filekey in ("contract", "result")
            else ".ai/tmp/behavior/%s/%s.log" % (subkey, filekey))


def tasks_from_bindings(features: list[str]) -> dict:
    """Evaluation 任务：expected 逐字来自**已审批** Binding（缺失即拒绝，不猜）。"""
    official = tb.load_bindings()
    tasks = []
    for feature in features:
        contracts, _reports = fbe.build_contracts(feature, "Features")
        for contract in contracts:
            behavior = str(contract["behavior"])
            gate = bc.binding_gate_status(feature, behavior, official_bindings=official)
            if gate["status"] != bc.APPROVED_BINDING:
                raise SystemExit("BINDING NOT APPROVED: %s/%s -> %s"
                                 % (feature, behavior, gate["status"]))
            binding = tb.get_binding(official, feature, behavior) or {}
            expected = binding.get("expected") or []
            if not expected:
                raise SystemExit("BINDING HAS NO EXPECTED: %s/%s" % (feature, behavior))
            tasks.append({
                "id": "P164-%s-%s" % (feature.upper(), behavior.upper())[:40],
                "title": "Phase 1.64 %s/%s" % (feature, behavior),
                "requirement": "p164 batch verification (expected from approved binding)",
                "mode": "evidence",
                "feature": feature,
                "behavior": behavior,
                "expect": expected,
            })
    return {"schema": {"id": "evaluation_evidence_tasks", "version": 1},
            "run": {"max_age_hours": 24, "artifact_root": ".ai/tmp/behavior"},
            "tasks": tasks}


def run_feature(feature: str, godot_bin: str, ts, paths: dict, tag: str,
                checks: list) -> dict:
    result = {"feature": feature, "run_id": None, "artifacts": 0,
              "attestation": "", "behaviors": {}}

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((feature, name, bool(ok), str(detail)))

    contracts, _reports = fbe.build_contracts(feature, "Features")
    check("contract_present", bool(contracts), "%d behaviors" % len(contracts))

    gates = [bc.binding_gate_status(feature, str(c["behavior"])) for c in contracts]
    check("binding_approved",
          all(g["status"] == bc.APPROVED_BINDING for g in gates),
          "; ".join("%s=%s" % (g.get("binding_id"), g["status"]) for g in gates))

    reports = fbe.verify_feature(feature, project_root=PROJECT_ROOT,
                                 godot=godot_bin, replay=2, user_dir_tag=tag)
    statuses = {str(r.behavior): r.status for r in reports}
    result["behaviors"] = dict(statuses)
    check("godot_collection", all(s == "PASS" for s in statuses.values()),
          str(statuses))

    bundle_doc = fbe.build_bundle(reports, behavior_protocol.load_protocol(),
                                  project_root=PROJECT_ROOT)
    bundle_path = fbe.write_bundle(bundle_doc, paths["evidence"])
    with open(bundle_path, encoding="utf-8") as handle:
        written = json.load(handle)
    # 与 1.63 相同口径：写入后统一重算 integrity（不伪造 digest）
    written["integrity"] = {"algorithm": "sha256",
                            "payload_sha256": fbe.bundle_digest(written)}
    _dump(bundle_path, written)
    check("bundle_written", os.path.isfile(bundle_path),
          os.path.relpath(bundle_path, PROJECT_ROOT))

    digest = recompute_evidence_digest(written)
    envelope = signing.sign_object(
        object_type="evidence_bundle", object_id=bundle_doc["bundle_id"],
        object_version="1", content_digest=digest,
        digest_scheme="evidence-bundle-digest-v1", key_id=EVIDENCE_KEY,
        trust_store=ts, project_root=PROJECT_ROOT)
    _dump(bundle_path + ".sig.json", envelope)
    verdict = verify_envelope(envelope, object_type="evidence_bundle",
                              object_id=bundle_doc["bundle_id"], object_version="1",
                              expected_digest=digest,
                              expected_digest_scheme="evidence-bundle-digest-v1",
                              trust_store=ts)
    check("evidence_signed", verdict.get("status") == "SIGNATURE_VALID",
          str(verdict.get("status")))

    ident = execution.ExecutionIdentity.create(
        feature_id=feature, behavior_id="",
        scenario_id="%s_p164_%s" % (feature, tag), contract_version="1",
    ).mark_started()
    result["run_id"] = ident.run_id
    fps = execution.collect_all(PROJECT_ROOT, feature_id=feature,
                                replay_count=2, timeout_seconds=120)
    all_fps = fps.all_fingerprints()
    entries = []
    for report in reports:
        for subkey, digest_map in (report.to_dict().get("artifact_digests") or {}).items():
            for filekey, filedigest in digest_map.items():
                entries.append(execution.make_artifact_entry(
                    artifact_id="%s_%s" % (subkey, filekey),
                    artifact_type=str(filekey),
                    relative_path=_rel_artifact(subkey, filekey),
                    sha256=str(filedigest), size_bytes=0))
    manifest = execution.RunManifest(
        run_id=ident.run_id, execution_id=ident.execution_id,
        source_fingerprint=all_fps["source_fingerprint"],
        environment_fingerprint=all_fps["environment_fingerprint"],
        collector_fingerprint=all_fps["collector_fingerprint"],
        execution_config_fingerprint=all_fps["execution_config_fingerprint"],
        feature_id=ident.feature_id, evidence_reference=bundle_path)
    manifest.add_artifacts(entries)
    manifest.complete(started_at=ident.started_at, execution_status="SUCCEEDED")
    manifest_doc = manifest.to_dict()
    errors = execution.RunManifest.validate_manifest(manifest_doc)
    check("manifest_valid", not errors,
          "digest=%s artifacts=%s" % (manifest_doc["manifest_digest"][:12],
                                      manifest_doc["artifact_count"]))
    result["artifacts"] = manifest_doc["artifact_count"]

    attest = execution.attest_execution(
        manifest=manifest_doc, trust_level="LOCAL_ISOLATED", trust_store=ts,
        project_root=PROJECT_ROOT, signer_key_id=EVIDENCE_KEY,
        execution_status="SUCCEEDED")
    attestation_doc = attest["attestation"]
    attest_envelope = attest["signature_envelope"]
    verify = execution.verify_attestation(
        attestation=attestation_doc, signature_envelope=attest_envelope,
        manifest=manifest_doc, trust_store=ts)
    check("attestation_verified",
          verify["ok"] and verify["status"] == "ATTESTED_VERIFIED",
          str(verify.get("status")))
    result["attestation"] = str(verify.get("status"))
    run_dir = os.path.join(paths["runs"], ident.run_id)
    _dump(os.path.join(run_dir, "manifest.json"), manifest_doc)
    _dump(os.path.join(run_dir, "attestation.json"), attestation_doc)
    _dump(os.path.join(run_dir, "attestation.json.sig.json"), attest_envelope)
    return result


def evaluate(paths: dict, features: list[str]) -> dict:
    """跑一次 evidence_eval，按 Behavior 取状态（不按 Feature 取首条）。"""
    argv = [sys.executable, os.path.join(_TOOLS, "evaluation", "evidence_eval.py"),
            "--tasks-file", paths["tasks"], "--evidence-dir", paths["evidence"],
            "--no-collect", "--json"]
    proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          timeout=600, cwd=PROJECT_ROOT)
    statuses = {}
    stdout = proc.stdout or ""
    try:
        report = json.loads(stdout[stdout.find("{"):])
    except (ValueError, IndexError):
        return {"_error": "REPORT_UNAVAILABLE", "_stderr": (proc.stderr or "")[-800:]}
    # 一条任务 = 一个 (feature, behavior)；结论取任务级 evaluation_status，
    # 不取 behaviors[] 里的逐 replay 观测（那只是同一结论的观测明细）。
    for task in report.get("tasks", []):
        feature = str(task.get("feature_id") or "")
        if feature not in features:
            continue
        behavior = str(task.get("behavior_id") or "")
        statuses["%s/%s" % (feature, behavior)] = str(task.get("evaluation_status"))
    # 矩阵需要评估输出目录；写入 json 供 --eval-dir 复用（不伪造状态）
    _dump(os.path.join(paths["eval"], "evaluation.json"), report)
    return statuses


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="B1")
    parser.add_argument("--features", default="save_game,i_frames,openable_door")
    parser.add_argument("--out-root", default=".ai/tmp/p164/batch1")
    parser.add_argument("--replay", type=int, default=2)
    args = parser.parse_args()

    features = [f.strip() for f in args.features.split(",") if f.strip()]
    out_root = os.path.join(PROJECT_ROOT, args.out_root)
    paths = {
        "evidence": os.path.join(out_root, "evidence"),
        "runs": os.path.join(out_root, "runs"),
        "eval": os.path.join(out_root, "evaluation"),
        "tasks": os.path.join(out_root, "tasks_%s.yaml" % args.label),
    }
    for key in ("evidence", "runs", "eval"):
        os.makedirs(paths[key], exist_ok=True)
    # 只清本批次自己的证据目录（避免同一 Behavior 出现两条冲突 bundle）
    for stale in glob.glob(os.path.join(paths["evidence"], "*.json")):
        os.remove(stale)

    try:
        godot_bin = env_paths.require_godot(PROJECT_ROOT)
    except SystemExit as exc:
        print(str(exc))
        return 2

    documents = tasks_from_bindings(features)
    documents["run"]["evidence_dir"] = os.path.relpath(paths["evidence"], PROJECT_ROOT)
    import yaml
    with open(paths["tasks"], "w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(documents, handle, allow_unicode=True, sort_keys=False)

    ts = trust_store.TrustStore(project_root=PROJECT_ROOT)   # 真实独立信任根
    checks: list = []
    results = []
    for feature in features:
        print("=== %s ===" % feature, flush=True)
        tag = "%s-%s" % (args.label.lower(), feature)
        results.append(run_feature(feature, godot_bin, ts, paths, tag, checks))

    statuses = evaluate(paths, features)
    for feature, name, ok, detail in checks:
        print("%s %s/%s %s" % ("PASS" if ok else "FAIL", feature, name, detail))
    for key, status in sorted(statuses.items()):
        print("%s %s %s" % ("PASS" if status == "VERIFIED_PASS" else "FAIL", key, status))

    failed = sum(1 for _f, _n, ok, _d in checks if not ok)
    failed += sum(1 for status in statuses.values() if status != "VERIFIED_PASS")
    summary = {
        "label": args.label, "features": features, "checks": len(checks),
        "check_failures": sum(1 for _f, _n, ok, _d in checks if not ok),
        "behaviors": statuses, "results": results,
        "godot": godot_bin, "project_root": PROJECT_ROOT,
        "evidence_dir": paths["evidence"], "runs_dir": paths["runs"],
        "trust_level": "LOCAL_ISOLATED",
    }
    _dump(os.path.join(out_root, "summary.json"), summary)
    print("\n===== Phase 1.64 %s: %d features, %d checks, %d failures, %d behaviors ====="
          % (args.label, len(results), len(checks),
             summary["check_failures"], len(statuses)))
    print("evidence: %s" % os.path.relpath(paths["evidence"], PROJECT_ROOT))
    print("trust_level = LOCAL_ISOLATED（签名验证通过不等于执行过程真实）")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
