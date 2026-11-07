#!/usr/bin/env python3
"""Execution Planner + 真实执行 + Evidence/Attestation/Evaluation（Phase 1.66）。

职责与 Learning Planner 分开：这里只决定「如何安全执行一个已 VALID 的场景」。

复用（不新建平行 Runner）：

- 真实执行：`feature_behavior_evidence.verify_contract`（真实 Godot + 隔离 workspace）
- Evidence：`build_bundle` / `bundle_digest` / `write_bundle`
- 签名/验签：`validator/provenance`
- Manifest / Attestation：`validator/execution`
- Evaluation：`evaluation/evidence_eval.py --no-collect`

每次执行的四种结论**分别**记录，绝不因为 execution exit=0 就写成 Evaluation PASS：

    execution_status   PASSED / FAILED / TIMEOUT / RUNNER_ERROR / ENVIRONMENT_BLOCKED / ...
    validator_status   （沿用 Validator 的 VALID；执行侧证据完整性另记为 evidence_status）
    attestation_status ATTESTED_VERIFIED / ...
    evaluation_status  VERIFIED_PASS / MISMATCH / ...

用法：
    python .ai/tools/learning/scenario_run.py --all --label P1
    python .ai/tools/learning/scenario_run.py --scenario .ai/learning/scenarios/s-xxx.json
退出码：0 全部执行且 Evaluation VERIFIED_PASS；1 存在失败；2 环境/输入错误。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_VALIDATOR = os.path.join(_TOOLS, "validator")
for _p in (_HERE, _TOOLS, os.path.join(_TOOLS, "scene_composer"),
           os.path.join(_TOOLS, "evaluation"),
           os.path.join(_VALIDATOR, "provenance"), _VALIDATOR,
           os.path.join(_VALIDATOR, "execution")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths                                    # noqa: E402
import feature_behavior_evidence as fbe         # noqa: E402
import behavior_protocol                        # noqa: E402
import scenario_generator                       # noqa: E402
import scenario_validate                        # noqa: E402
import env_paths                                # noqa: E402
import execution                                # noqa: E402
import check_behavior_evidence as cbe           # noqa: E402
import evidence_adapter as adapter              # noqa: E402
from provenance import trust_store, signing     # noqa: E402
from provenance.verification import (           # noqa: E402
    recompute_evidence_digest, verify_envelope,
)

PROJECT_ROOT = paths.ROOT
EVIDENCE_KEY = "PROVKEY-5aa9912c2dbb6587"
OUT_ROOT = os.path.join(PROJECT_ROOT, ".ai", "tmp", "p166")
RESULTS_INDEX = os.path.join(paths.LEARNING_STATE, "scenario_results.json")
REPLAY = 2
TIMEOUT_S = 180


def _dump(path: str, document) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _rel_artifact(subkey: str, filekey: str) -> str:
    return (".ai/tmp/behavior/%s/%s.json" % (subkey, filekey)
            if filekey in ("contract", "result")
            else ".ai/tmp/behavior/%s/%s.log" % (subkey, filekey))


def execution_plan(scenario: dict, *, label: str = "") -> dict:
    """执行计划：只对 VALID 场景生成；所有指纹来自真实环境。"""
    report = scenario_validate.validate(scenario)
    binary = env_paths.find_godot_binary()
    prerequisites = [
        {"name": "validator", "ok": report["status"] == "VALID", "detail": report["status"]},
        {"name": "godot", "ok": bool(binary), "detail": str(binary or "")[:120]},
        {"name": "scene", "ok": os.path.isfile(os.path.join(
            PROJECT_ROOT, str(scenario["scene"]).replace("res://", "").replace("/", os.sep))),
         "detail": scenario["scene"]},
    ]
    blocked = [item for item in prerequisites if not item["ok"]]
    identity = execution.ExecutionIdentity.create(
        feature_id=scenario["feature_id"], behavior_id=scenario["behavior_id"],
        scenario_id=scenario["scenario_id"], contract_version=scenario["contract_version"])
    run_id = identity.run_id
    fingerprints = execution.collect_all(PROJECT_ROOT, feature_id=scenario["feature_id"],
                                         replay_count=REPLAY, timeout_seconds=TIMEOUT_S)
    all_fps = fingerprints.all_fingerprints()
    plan = {
        "execution_plan_id": "p-" + identity.execution_id[:16],
        "scenario_id": scenario["scenario_id"],
        "feature_id": scenario["feature_id"],
        "behavior_id": scenario["behavior_id"],
        "label": label,
        "run_id": run_id,
        "execution_id": identity.execution_id,
        "created_at": _now(),
        "output_root": os.path.relpath(os.path.join(OUT_ROOT, "runs", run_id),
                                       PROJECT_ROOT).replace(os.sep, "/"),
        "evidence_root": ".ai/tmp/p166/evidence",
        "environment_fingerprint": all_fps["environment_fingerprint"],
        "source_fingerprint": all_fps["source_fingerprint"],
        "collector_fingerprint": all_fps["collector_fingerprint"],
        "execution_config_fingerprint": all_fps["execution_config_fingerprint"],
        "prerequisites": prerequisites,
        "isolation": {"workspace": "fresh copy per scenario",
                      "user_dir_tag": "p166-%s" % scenario["scenario_id"],
                      "evidence_dir": ".ai/tmp/p166/evidence",
                      "run_dir": ".ai/tmp/p166/runs/%s" % run_id},
        "timeout_policy": {"per_probe_s": TIMEOUT_S, "replay": REPLAY},
        "cleanup_policy": {"destroy_workspace": True, "keep_artifacts": True,
                           "never_delete_history": True},
        "status": "READY" if not blocked else "BLOCKED",
        "blocked_reasons": ["%s: %s" % (item["name"], item["detail"]) for item in blocked],
    }
    return plan


def _contract_from_scenario(scenario: dict, run_id: str) -> dict:
    return {
        "feature": scenario["feature_id"],
        "behavior": scenario["behavior_id"],
        "scene": scenario["scene"],
        "window_frames": int(scenario["window_frames"]),
        "actions": scenario["actions"],
        "preconditions": scenario["preconditions"],
        "expected": scenario["expected_observations"],
        "run_id": run_id,
    }


def _execution_status(report: dict) -> tuple[str, str]:
    """BehaviorReport → (execution_status, detail)；不把 INSUFFICIENT 说成 FAILED。"""
    status = str(report.get("status") or "")
    reason = str(report.get("reason") or "")
    detail = str(report.get("detail") or "")
    runs = report.get("runs") or []
    if status == fbe.STATUS_PASS:
        return "PASSED", ""
    if reason == "probe_timeout":
        return "TIMEOUT", detail
    if reason in ("evidence_unavailable",) and not runs:
        return "RUNNER_ERROR", detail
    if reason in ("action_unavailable",):
        return "RUNNER_ERROR", detail
    if reason in ("godot_unavailable",):
        return "ENVIRONMENT_BLOCKED", detail
    if reason in ("load_error", "script_error"):
        return "RUNNER_ERROR", detail or reason
    if status == fbe.STATUS_MISMATCH:
        return "FAILED", detail or reason
    if status == fbe.STATUS_INSUFFICIENT:
        return "INCONCLUSIVE", detail or reason
    if status == fbe.STATUS_INVALID:
        return "RUNNER_ERROR", detail or reason
    return "RUNNER_ERROR", "unknown report status %r" % status


def _prepare_dirs(label: str, clean: bool = False) -> dict:
    dirs = {
        "evidence": os.path.join(OUT_ROOT, "evidence"),
        "runs": os.path.join(OUT_ROOT, "runs"),
        "evaluation": os.path.join(OUT_ROOT, "evaluation"),
        "results": os.path.join(OUT_ROOT, "results"),
    }
    for key, value in dirs.items():
        os.makedirs(value, exist_ok=True)
        if key == "evidence" and clean:
            # 只在**批次开始**时清理本批次自己的证据目录：同一 (feature, behavior)
            # 出现两条 bundle 会让评估索引失效。单场景运行/被拒绝的运行绝不清理，
            # 否则会删掉已有真实证据（本阶段实测过的缺陷）。不碰 1.64/1.65 产物。
            for stale in glob.glob(os.path.join(value, "*.json")):
                os.remove(stale)
    dirs["tasks"] = os.path.join(OUT_ROOT, "tasks_%s.yaml" % label)
    return dirs


def _behavior_record(bundle: dict, feature_id: str, behavior_id: str) -> dict:
    for feature in bundle.get("features") or []:
        if str(feature.get("feature")) != feature_id:
            continue
        for record in feature.get("behaviors") or []:
            if str(record.get("behavior")) == behavior_id:
                return record
    return {}


def _official_contract(feature_id: str, behavior_id: str) -> dict:
    contracts, _reports = fbe.build_contracts(feature_id, "Features")
    return next((item for item in contracts
                 if str(item["behavior"]) == behavior_id), {})


def _verify_and_evaluate(scenario: dict, bundle: dict) -> dict:
    """用**同一个** Validator/Evaluation 代码路径判定场景证据。

    区别只在期望来源：生成场景的期望经过 Scenario Validator 的契约一致性检查，
    然后在证据的 raw observations 上重算；Feature 官方契约另外独立判定，两种结论
    分别记录（扩展检查必然与官方 2 项期望数量不同，不能互相冒充）。
    """
    record = _behavior_record(bundle, scenario["feature_id"], scenario["behavior_id"])
    if not record:
        return {"scenario_status": "INCOMPLETE", "scenario_detail": "evidence record missing",
                "official_status": "INCOMPLETE", "official_detail": "evidence record missing",
                "evaluation_status": "INCOMPLETE", "evaluation_detail": "no observations",
                "expectation": {}}
    scenario_verdict = cbe.judge_record(record, {"expected": scenario["expected_observations"]})
    official = _official_contract(scenario["feature_id"], scenario["behavior_id"])
    official_verdict = (cbe.judge_record(record, official) if official
                        else {"status": "INCOMPLETE", "detail": "no official contract"})
    expectation = adapter.evaluate_expectations(scenario["expected_observations"],
                                                record.get("actual"))
    status, reason = adapter.evaluation_status(scenario_verdict.get("status"),
                                                expectation["state"])
    return {
        "scenario_status": str(scenario_verdict.get("status")),
        "scenario_detail": "; ".join(str(scenario_verdict.get("detail") or "").split(";")[:3]),
        "scenario_reason": str(scenario_verdict.get("reason") or ""),
        "official_status": str(official_verdict.get("status")),
        "official_detail": str(official_verdict.get("detail") or "")[:300],
        "official_reason": str(official_verdict.get("reason") or ""),
        "evaluation_status": status,
        "evaluation_reason": reason,
        "evaluation_detail": expectation.get("detail", ""),
        "expectation": expectation,
    }


def run_scenario(scenario: dict, *, label: str = "", dirs: dict | None = None) -> dict:
    dirs = dirs or _prepare_dirs(label or "P1")
    plan = execution_plan(scenario, label=label)
    record = {
        "scenario_id": scenario["scenario_id"],
        "feature_id": scenario["feature_id"],
        "behavior_id": scenario["behavior_id"],
        "behavior": scenario["behavior"],
        "scenario_type": scenario["scenario_type"],
        "knowledge_refs": scenario["knowledge_refs"],
        "label": label,
        "plan": plan,
        "run_id": plan["run_id"],
        "started_at": _now(),
        "execution_status": "BLOCKED",
        "evidence_status": "NOT_COLLECTED",
        "validator_status": scenario.get("validation_status") or "PENDING",
        "attestation_status": "NOT_ATTESTED",
        "scenario_evidence_status": "NOT_VERIFIED",
        "official_contract_status": "NOT_VERIFIED",
        "evaluation_status": "NOT_EVALUATED",
        "bundle_path": "",
        "evidence_digest": "",
        "manifest_digest": "",
        "detail": "",
        "duration_s": 0.0,
    }
    _dump(os.path.join(PROJECT_ROOT, plan["output_root"].replace("/", os.sep),
                       "plan.json"), plan)
    if plan["status"] != "READY":
        record["execution_status"] = "ENVIRONMENT_BLOCKED"
        record["detail"] = "; ".join(plan["blocked_reasons"])
        return record

    started = time.time()
    binary = env_paths.require_godot(PROJECT_ROOT)
    workspace = None
    try:
        workspace = fbe.BehaviorWorkspace(
            "Features", binary, user_dir_tag="p166-%s" % scenario["scenario_id"])
        contract = _contract_from_scenario(scenario, plan["run_id"])
        report = fbe.verify_contract(contract, workspace.project, binary,
                                     replay=REPLAY, timeout_s=TIMEOUT_S)
        report_doc = report.to_dict()
    finally:
        if workspace is not None:
            workspace.close()
        record["duration_s"] = round(time.time() - started, 2)

    record["execution_status"], record["detail"] = _execution_status(report_doc)
    record["report"] = {"status": report_doc.get("status"),
                        "reason": report_doc.get("reason"),
                        "detail": report_doc.get("detail"),
                        "replay_count": report_doc.get("replay_count"),
                        "runs": [{key: run.get(key) for key in
                                  ("run_id", "status", "reason", "detail", "action_executed",
                                   "actions", "checks", "preconditions")}
                                 for run in report_doc.get("runs") or []]}

    # ---- Evidence Bundle（无论执行成败都保留原始结果）
    bundle_doc = fbe.build_bundle([report], behavior_protocol.load_protocol(),
                                  project_root=PROJECT_ROOT)
    bundle_path = fbe.write_bundle(bundle_doc, dirs["evidence"])
    with open(bundle_path, encoding="utf-8") as handle:
        written = json.load(handle)
    written["integrity"] = {"algorithm": "sha256",
                            "payload_sha256": fbe.bundle_digest(written)}
    _dump(bundle_path, written)
    record["bundle_path"] = os.path.relpath(bundle_path, PROJECT_ROOT).replace(os.sep, "/")
    verdict = _verify_and_evaluate(scenario, written)
    record["scenario_evidence_status"] = verdict["scenario_status"]
    record["official_contract_status"] = verdict["official_status"]
    record["official_contract_detail"] = verdict["official_detail"]
    record["evaluation_status"] = verdict["evaluation_status"]
    record["evaluation_reason"] = verdict["evaluation_reason"]
    record["evaluation_detail"] = verdict["evaluation_detail"]
    record["expectation"] = verdict["expectation"]
    if verdict["scenario_status"] != cbe.STATUS_PASS:
        record["detail"] = (record["detail"] + " | " + verdict["scenario_detail"]).strip(" |")

    try:
        ts = trust_store.TrustStore(project_root=PROJECT_ROOT)
        digest = recompute_evidence_digest(written)
        record["evidence_digest"] = digest
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
        record["evidence_status"] = ("EVIDENCE_VERIFIED"
                                     if verdict.get("status") == "SIGNATURE_VALID"
                                     else "EVIDENCE_UNVERIFIED")
    except Exception as error:                  # noqa: BLE001 - 采集/签名失败必须可见
        record["evidence_status"] = "EVIDENCE_ERROR"
        record["detail"] = (record["detail"] + " | evidence: %s" % error).strip(" |")

    # ---- Manifest + Attestation（真正的 Run 绑定）
    fps = execution.collect_all(PROJECT_ROOT, feature_id=scenario["feature_id"],
                                replay_count=REPLAY, timeout_seconds=TIMEOUT_S)
    all_fps = fps.all_fingerprints()
    entries = []
    for subkey, digest_map in (report_doc.get("artifact_digests") or {}).items():
        for filekey, filedigest in digest_map.items():
            entries.append(execution.make_artifact_entry(
                artifact_id="%s_%s" % (subkey, filekey), artifact_type=str(filekey),
                relative_path=_rel_artifact(subkey, filekey),
                sha256=str(filedigest), size_bytes=0))
    manifest = execution.RunManifest(
        run_id=plan["run_id"], execution_id=plan["execution_id"],
        source_fingerprint=all_fps["source_fingerprint"],
        environment_fingerprint=all_fps["environment_fingerprint"],
        collector_fingerprint=all_fps["collector_fingerprint"],
        execution_config_fingerprint=all_fps["execution_config_fingerprint"],
        feature_id=scenario["feature_id"], evidence_reference=bundle_path)
    manifest.add_artifacts(entries)
    manifest.complete(started_at=plan["created_at"],
                      execution_status=("SUCCEEDED" if record["execution_status"] == "PASSED"
                                        else "FAILED"))
    manifest_doc = manifest.to_dict()
    errors = execution.RunManifest.validate_manifest(manifest_doc)
    record["manifest_digest"] = manifest_doc["manifest_digest"]
    record["manifest_valid"] = not errors
    run_dir = os.path.join(dirs["runs"], plan["run_id"])
    _dump(os.path.join(run_dir, "manifest.json"), manifest_doc)
    try:
        attest = execution.attest_execution(
            manifest=manifest_doc, trust_level="LOCAL_ISOLATED",
            trust_store=trust_store.TrustStore(project_root=PROJECT_ROOT),
            project_root=PROJECT_ROOT, signer_key_id=EVIDENCE_KEY,
            execution_status=("SUCCEEDED" if record["execution_status"] == "PASSED"
                              else "FAILED"))
        _dump(os.path.join(run_dir, "attestation.json"), attest["attestation"])
        _dump(os.path.join(run_dir, "attestation.json.sig.json"), attest["signature_envelope"])
        verify = execution.verify_attestation(
            attestation=attest["attestation"], signature_envelope=attest["signature_envelope"],
            manifest=manifest_doc,
            trust_store=trust_store.TrustStore(project_root=PROJECT_ROOT))
        record["attestation_status"] = str(verify.get("status"))
    except Exception as error:                  # noqa: BLE001 - Attestation 失败必须显式
        record["attestation_status"] = "ATTESTATION_ERROR"
        record["detail"] = (record["detail"] + " | attestation: %s" % error).strip(" |")
    record["finished_at"] = _now()
    return record


def run_batch(scenarios: list[dict], *, label: str) -> dict:
    dirs = _prepare_dirs(label, clean=True)
    records = [run_scenario(scenario, label=label, dirs=dirs) for scenario in scenarios]
    for record in records:
        _dump(os.path.join(dirs["results"], "%s.json" % record["scenario_id"]), record)
    document = {
        "schema": "scenario_execution_index",
        "schema_version": 1,
        "generated_at": _now(),
        "label": label,
        "trust_level": "LOCAL_ISOLATED",
        "note": "execution/attestation/evaluation 三种结论分别记录，不互相替代",
        "summary": {
            "scenarios": len(records),
            "executed": sum(1 for record in records
                            if record["execution_status"] in ("PASSED", "FAILED", "TIMEOUT")),
            "passed": sum(1 for record in records if record["execution_status"] == "PASSED"),
            "failed": sum(1 for record in records if record["execution_status"] == "FAILED"),
            "attested": sum(1 for record in records
                            if record["attestation_status"] == "ATTESTED_VERIFIED"),
            "evaluated_pass": sum(1 for record in records
                                  if record["evaluation_status"] == "VERIFIED_PASS"),
            "blocked": sum(1 for record in records
                           if record["execution_status"] == "ENVIRONMENT_BLOCKED"),
        },
        "results": records,
    }
    _dump(os.path.join(dirs["evaluation"], "evaluation.json"), document)
    _dump(RESULTS_INDEX, document)
    _dump(os.path.join(dirs["results"], "index.json"), document)
    return document


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--label", default="P1")
    args = parser.parse_args(argv)

    paths_in = list(args.scenario)
    if args.all or not paths_in:
        paths_in = sorted(glob.glob(os.path.join(scenario_generator.SCENARIO_DIR, "s-*.json")))
    if not paths_in:
        print("no scenarios found", file=sys.stderr)
        return 2
    scenarios = []
    for path in paths_in:
        with open(path, encoding="utf-8") as handle:
            scenarios.append(json.load(handle))
    document = run_batch(scenarios, label=args.label)
    for record in document["results"]:
        print("%s %s execution=%s evidence=%s attestation=%s evaluation=%s"
              % ("PASS" if record["evaluation_status"] == "VERIFIED_PASS" else "FAIL",
                 record["scenario_id"], record["execution_status"],
                 record["evidence_status"], record["attestation_status"],
                 record["evaluation_status"]))
        if record["detail"]:
            print("  - %s" % str(record["detail"])[:300])
    print(json.dumps(document["summary"], ensure_ascii=False))
    return 0 if document["summary"]["evaluated_pass"] == len(scenarios) else 1


if __name__ == "__main__":
    raise SystemExit(main())
