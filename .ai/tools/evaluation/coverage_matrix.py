#!/usr/bin/env python3
"""Coverage Matrix / Dashboard（Phase 1.63）。

对每一个**正式支持**的 Behavior 独立计算八个维度的状态（各维度相互独立，
不构成单一线性等级）：

    contract    CONTRACT_PRESENT / CONTRACT_INVALID / CONTRACT_MISSING
    binding     NO_BINDING / DRAFT / PENDING_REVIEW / APPROVED / REVOKED / CONTRACT_MISMATCH / INVALID
    evidence    NO_EVIDENCE / LEGACY_EVIDENCE / EVIDENCE_INVALID / EVIDENCE_VERIFIED
    signature   NO_SIGNATURE / SIGNATURE_INVALID / SIGNATURE_VERIFIED / SIGNATURE_REQUIRED
    attestation NO_ATTESTATION / ATTESTATION_INVALID / ATTESTATION_VERIFIED / RUN_BINDING_INVALID
    evaluation  NOT_EVALUATED / VERIFIED_PASS / VERIFIED_FAIL / INVALID_EVIDENCE / INCOMPLETE / EVALUATION_ERROR
    holdout     NO_HOLDOUT / HOLDOUT_AVAILABLE / HOLDOUT_VERIFIED / HOLDOUT_INVALID / HOLDOUT_CONSUMED
    mutation    NOT_TESTED / MUTATION_KILLED / MUTATION_SURVIVED / MUTATION_INVALID / MUTATION_ERROR

原则：
- 正式支持集合动态读取（Features/*/template.yaml#behavior），不硬编码 23/60。
- Digest / Run ID 只来自真实产物；没有就是 null，绝不编造。
- Legacy Evidence（无签名 sidecar）不会被算成签名验证；签名验证 ≠ 执行真实性。
- 缺失数据产生明确状态，不产生虚假 PASS。
- 退出码：0 = 报告成功（可存在覆盖缺口）；1 = 输入不合法或计算异常；
  2 = --strict 且存在未满足要求的 Behavior。
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))
for _p in (_TOOLS, os.path.join(_TOOLS, "validator"), os.path.join(_TOOLS, "evaluation"),
           os.path.join(_TOOLS, "scene_composer"), os.path.join(_TOOLS, "validator", "provenance"),
           os.path.join(_TOOLS, "validator", "execution")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import binding_candidates as bc                  # noqa: E402
import check_behavior_evidence as cbe            # noqa: E402
import trace_bindings as tb                      # noqa: E402
import feature_behavior_evidence as fbe          # noqa: E402

MUTATION_REPORT_DIR = os.path.join(PROJECT_ROOT, ".ai", "tmp", "p159", "reports")
EVAL_REPORT_DIR = os.path.join(PROJECT_ROOT, ".ai", "tmp", "eval")
HOLDOUT_REGISTRY_PATH = os.path.join(_TOOLS, "evaluation", "holdout",
                                     "holdout_datasets.json")
DEFAULT_EVIDENCE_DIRS = [
    os.path.join(PROJECT_ROOT, ".ai", "tmp", "p163_e2e", "evidence"),
    os.path.join(PROJECT_ROOT, ".ai", "tmp", "p160_e2e", "evidence"),
    os.path.join(PROJECT_ROOT, ".ai", "tmp", "p161_e2e", "all"),
]
DEFAULT_RUNS_DIR = os.path.join(PROJECT_ROOT, ".ai", "tmp", "p163_e2e", "runs")
OFFICIAL_RESULTS_PATH = os.path.join(PROJECT_ROOT, ".ai", "tmp", "p168",
                                     "official", "results.json")

EXIT_OK, EXIT_ERROR, EXIT_STRICT = 0, 1, 2


# ---------------------------------------------------------------- 小工具

def _rel(path: str) -> str:
    """相对 PROJECT_ROOT 的路径；跨盘等失败时回退绝对路径（不伪造）。"""
    try:
        return os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")


def _sha256_file(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def _bundle_integrity_ok(bundle_path: str, document: dict) -> bool:
    integrity = document.get("integrity") or {}
    recorded = str(integrity.get("payload_sha256") or "")
    if not recorded:
        return False
    # payload_sha256 = 除 integrity 外全部字段的规范化 JSON 摘要（与采集器一致）
    try:
        return fbe.bundle_digest(document) == recorded
    except Exception:                                          # noqa: BLE001
        return False


# ---------------------------------------------------------------- 各维度

def contract_dimension(feature_id: str, behavior_id: str,
                       features_dir: str) -> tuple[str, str]:
    try:
        version, expected, _ = bc.contract_digest(feature_id, behavior_id, features_dir)
        if not expected:
            return "CONTRACT_PRESENT", version
        return "CONTRACT_PRESENT", version
    except Exception:                                          # noqa: BLE001
        return "CONTRACT_INVALID", ""


def binding_dimension(feature_id: str, behavior_id: str, contract_version: str) -> dict:
    gate = bc.binding_gate_status(feature_id, behavior_id, contract_version=contract_version)
    mapping = {bc.APPROVED_BINDING: "APPROVED", "CONTRACT_MISMATCH": "CONTRACT_MISMATCH",
               bc.DRAFT_BINDING: "DRAFT", bc.PENDING_REVIEW_BINDING: "PENDING_REVIEW",
               bc.BINDING_REVOKED: "REVOKED", bc.BINDING_INVALID: "INVALID",
               bc.NO_BINDING: "NO_BINDING"}
    return {"status": mapping.get(gate["status"], "INVALID"),
            "binding_id": gate.get("binding_id"), "reason": gate.get("reason", "")}


def _iter_evidence_dirs(evidence_dirs: list) -> list:
    dirs = list(evidence_dirs or [])
    return [d for d in dirs if os.path.isdir(d)]


def evidence_dimension(feature_id: str, behavior_id: str,
                       evidence_dirs: list, features_dir: str) -> dict:
    """从最新 bundle 取该 Behavior 的证据状态（bundle 完整性 + Validator 记录状态）。"""
    result = {"status": "NO_EVIDENCE", "bundle": None, "bundle_digest": None,
              "run_id": None, "reason": ""}
    best_mtime, best = -1.0, None
    for directory in _iter_evidence_dirs(evidence_dirs):
        for bundle_path in glob.glob(os.path.join(directory, "*bundle.json")):
            try:
                with open(bundle_path, encoding="utf-8") as handle:
                    document = json.load(handle)
            except (OSError, ValueError):
                continue
            for feature in document.get("features", []):
                if str(feature.get("feature_id") or feature.get("feature")) != feature_id:
                    continue
                for behavior in feature.get("behaviors", []):
                    if str(behavior.get("behavior")) != behavior_id:
                        continue
                    mtime = os.path.getmtime(bundle_path)
                    if mtime > best_mtime:
                        best_mtime, best = mtime, (bundle_path, document, behavior)
    if best is None:
        result["reason"] = "no evidence bundle contains this behavior"
        return result
    bundle_path, document, behavior = best
    result["bundle"] = _rel(bundle_path)
    result["bundle_digest"] = _sha256_file(bundle_path)
    result["run_id"] = behavior.get("run_id")
    if not _bundle_integrity_ok(bundle_path, document):
        result["status"] = "EVIDENCE_INVALID"
        result["reason"] = "bundle payload sha256 mismatch"
        return result
    status = str(behavior.get("status") or "")
    if status == "PASS":
        result["status"] = "EVIDENCE_VERIFIED"
        result["reason"] = "latest bundle records validator PASS for this behavior"
    elif status in ("MISMATCH", "STATE_MISMATCH", "SIGNAL_MISMATCH", "FAIL"):
        result["status"] = "EVIDENCE_INVALID"
        result["reason"] = "latest bundle records behavior mismatch: %s" % \
            str(behavior.get("detail") or "")[:80]
    else:
        result["status"] = "EVIDENCE_INVALID"
        result["reason"] = "latest bundle records %s" % (status or "unknown status")
    return result


def signature_dimension(evidence: dict) -> dict:
    """签名状态独立计算：sidecar 缺失 = NO_SIGNATURE（不算验证过）。"""
    result = {"status": "NO_SIGNATURE", "sidecar": None, "reason": ""}
    bundle_path = evidence.get("bundle")
    if not bundle_path:
        result["reason"] = "no evidence to sign"
        return result
    full = os.path.join(PROJECT_ROOT, bundle_path)
    sidecar = full + ".sig.json"
    if not os.path.isfile(sidecar):
        result["reason"] = "no signature sidecar next to the bundle"
        return result
    result["sidecar"] = _rel(sidecar)
    try:
        from provenance.verification import verify_evidence_bundle
        from provenance.trust_store import TrustStore
        with open(full, encoding="utf-8") as handle:
            document = json.load(handle)
        verdict = verify_evidence_bundle(full, document,
                                         trust_store=TrustStore(project_root=PROJECT_ROOT))
        status = str((verdict.get("verification") or {}).get("status")
                     or verdict.get("status") or "")
        reason = str((verdict.get("verification") or {}).get("reason")
                     or verdict.get("reason") or "")
    except Exception as exc:                                   # noqa: BLE001
        result["status"] = "SIGNATURE_INVALID"
        result["reason"] = "signature verification error: %r" % (exc,)
        return result
    if status == "SIGNATURE_VALID":
        result["status"] = "SIGNATURE_VERIFIED"
        result["reason"] = "sidecar signature verifies against the independent trust root"
    else:
        result["status"] = "SIGNATURE_INVALID"
        result["reason"] = reason or status
    return result


def attestation_dimension(feature_id: str, behavior_id: str, evidence: dict,
                          runs_dir: str) -> dict:
    """Execution Attestation 状态独立计算（产物不存在 = NO_ATTESTATION，不造假）。

    Run -> Evidence 的关联走 Manifest 的 evidence_reference（bundle 路径），
    不用采集 run_id（那是 per-replay 子运行标识，与 Execution Run 不同命名空间）。
    """
    result = {"status": "NO_ATTESTATION", "run_id": None, "attestation_digest": None,
              "reason": ""}
    bundle_rel = evidence.get("bundle")
    if not bundle_rel:
        result["reason"] = "no run binding for this behavior's evidence"
        return result
    if not runs_dir or not os.path.isdir(runs_dir):
        result["reason"] = "no persisted execution run directory"
        return result
    # 找 evidence_reference 指向该 bundle 的 run
    candidate_runs = []
    for entry in sorted(os.listdir(runs_dir)):
        manifest_path = os.path.join(runs_dir, entry, "manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        try:
            with open(manifest_path, encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (OSError, ValueError):
            continue
        reference = str(manifest.get("evidence_reference") or "")
        try:
            reference_rel = _rel(reference)
        except ValueError:
            reference_rel = reference
        if reference_rel == bundle_rel or os.path.abspath(reference) == \
                os.path.abspath(os.path.join(PROJECT_ROOT, bundle_rel)):
            candidate_runs.append((entry, manifest_path))
    if not candidate_runs:
        result["reason"] = "no persisted run manifest references this evidence bundle"
        return result
    entry, manifest_path = candidate_runs[-1]
    result["run_id"] = entry
    attestation_path = os.path.join(runs_dir, entry, "attestation.json")
    if not os.path.isfile(attestation_path):
        result["status"] = "RUN_BINDING_INVALID"
        result["reason"] = "run %s has manifest but no attestation" % entry
        return result
    try:
        from execution.attestation import verify_attestation
        from provenance.trust_store import TrustStore
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        with open(attestation_path, encoding="utf-8") as handle:
            attestation = json.load(handle)
        envelope_path = attestation_path + ".sig.json"
        envelope = None
        if os.path.isfile(envelope_path):
            with open(envelope_path, encoding="utf-8") as handle:
                envelope = json.load(handle)
        verdict = verify_attestation(attestation=attestation, signature_envelope=envelope,
                                     manifest=manifest,
                                     trust_store=TrustStore(project_root=PROJECT_ROOT))
    except Exception as exc:                                   # noqa: BLE001
        result["status"] = "ATTESTATION_INVALID"
        result["reason"] = "attestation verification error: %r" % (exc,)
        return result
    result["attestation_digest"] = attestation.get("attestation_digest")
    status = str(verdict.get("status") or "")
    if status == "ATTESTED_VERIFIED":
        result["status"] = "ATTESTATION_VERIFIED"
        result["reason"] = "execution attestation verifies for run %s" % entry
    else:
        result["status"] = "ATTESTATION_INVALID"
        result["reason"] = str(verdict.get("reason") or status)
    return result


def evaluation_dimension(feature_id: str, behavior_id: str,
                         eval_dirs: list) -> dict:
    result = {"status": "NOT_EVALUATED", "report": None, "task_id": None, "reason": ""}
    best_mtime, best = -1.0, None
    for directory in eval_dirs or []:
        if not os.path.isdir(directory):
            continue
        for report_path in glob.glob(os.path.join(directory, "*", "evidence_report.json")):
            try:
                with open(report_path, encoding="utf-8") as handle:
                    report = json.load(handle)
            except (OSError, ValueError):
                continue
            for task in report.get("tasks", []):
                if str(task.get("feature_id")) != feature_id:
                    continue
                for behavior in task.get("behaviors", []):
                    if str(behavior.get("behavior")) != behavior_id:
                        continue
                    mtime = os.path.getmtime(report_path)
                    if mtime > best_mtime:
                        best_mtime = mtime
                        best = (report_path, task, behavior)
    if best is None:
        result["reason"] = "no evaluation report covers this behavior"
        return result
    report_path, task, behavior = best
    result["report"] = _rel(report_path)
    result["task_id"] = task.get("task_id")
    result["status"] = str(behavior.get("evaluation_status") or "NOT_EVALUATED")
    result["reason"] = str(behavior.get("reason") or "")
    return result


def holdout_dimension(feature_id: str, behavior_id: str,
                      registry_path: str = "") -> dict:
    result = {"status": "NO_HOLDOUT", "dataset_id": None, "dataset_version": None,
              "reason": ""}
    path = registry_path or HOLDOUT_REGISTRY_PATH
    if not os.path.isfile(path):
        result["reason"] = "no holdout registry"
        return result
    try:
        with open(path, encoding="utf-8") as handle:
            registry = json.load(handle)
    except (OSError, ValueError) as exc:
        result["status"] = "HOLDOUT_INVALID"
        result["reason"] = "holdout registry unreadable: %r" % (exc,)
        return result
    covering = [d for d in registry.get("datasets", [])
                if feature_id in (d.get("feature_ids") or [])
                and behavior_id in (d.get("behavior_ids") or [])]
    if not covering:
        result["reason"] = "no holdout dataset covers this behavior"
        return result
    covering.sort(key=lambda d: str(d.get("sealed_at") or d.get("created_at") or ""))
    latest = covering[-1]
    result["dataset_id"] = latest.get("holdout_id")
    result["dataset_version"] = latest.get("dataset_version")
    status = str(latest.get("status") or "")
    if latest.get("pollution"):
        result["status"] = "HOLDOUT_INVALID"
        result["reason"] = "holdout dataset is polluted"
    elif status == "SEALED":
        result["status"] = "HOLDOUT_AVAILABLE"
        result["reason"] = "sealed holdout dataset is available"
    elif status == "CONSUMED":
        result["status"] = "HOLDOUT_CONSUMED"
        result["reason"] = "holdout dataset already consumed (one-shot semantics)"
    elif status == "INVALIDATED":
        result["status"] = "HOLDOUT_INVALID"
        result["reason"] = str((latest.get("pollution") or [{}])[-1].get("reason")
                               or "holdout dataset invalidated")
    else:
        result["status"] = "HOLDOUT_INVALID"
        result["reason"] = "holdout dataset status %s" % (status or "unknown")
    return result


def mutation_dimension(feature_id: str, behavior_id: str,
                       report_dir: str = "") -> dict:
    result = {"status": "NOT_TESTED", "mutation_id": None, "reason": ""}
    directory = report_dir or MUTATION_REPORT_DIR
    if not os.path.isdir(directory):
        result["reason"] = "no mutation report directory"
        return result
    best_mtime, best = -1.0, None
    for report_path in glob.glob(os.path.join(directory, "M*.json")):
        try:
            with open(report_path, encoding="utf-8") as handle:
                report = json.load(handle)
        except (OSError, ValueError):
            continue
        catalog = report.get("catalog") or {}
        if str(catalog.get("feature_id")) != feature_id or \
                str(catalog.get("behavior_id")) != behavior_id:
            continue
        mtime = os.path.getmtime(report_path)
        if mtime > best_mtime:
            best_mtime, best = mtime, (report_path, report)
    if best is None:
        result["reason"] = "no mutation targets this behavior"
        return result
    report_path, report = best
    result["mutation_id"] = report.get("mutation_id")
    verdict = str(report.get("verdict") or "")
    mapping = {"MUTANT_KILLED": "MUTATION_KILLED", "MUTANT_SURVIVED": "MUTATION_SURVIVED",
               "INVALID_MUTANT": "MUTATION_INVALID", "HARNESS_ERROR": "MUTATION_ERROR",
               "TIMEOUT": "MUTATION_ERROR", "NOT_RUN": "NOT_TESTED"}
    result["status"] = mapping.get(verdict, "MUTATION_ERROR")
    result["reason"] = str(report.get("verdict_reason") or "")
    return result


def _official_sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _official_behavior_record(bundle: dict, feature_id: str, behavior_id: str) -> dict:
    for feature in bundle.get("features") or []:
        if str(feature.get("feature_id") or feature.get("feature")) != feature_id:
            continue
        for behavior in feature.get("behaviors") or []:
            if str(behavior.get("behavior")) == behavior_id:
                return behavior
    return {}


def _load_official_results(path: str) -> dict:
    """(feature, behavior) -> 最新官方执行记录；文件不存在时返回空映射。"""
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        return {}
    index = {}
    for item in document.get("results", []) if isinstance(document, dict) else []:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("feature_id") or ""), str(item.get("behavior_id") or ""))
        if key[0] and key[1]:
            index[key] = item
    return index


def official_contract_dimension(feature_id: str, behavior_id: str,
                                official_results: dict, features_dir: str) -> dict:
    """独立官方覆盖维度；**不参与**现有 fully_covered 的 7 维公式。"""
    result = {"status": "NO_OFFICIAL_EXECUTION", "executed": False,
              "evaluation_status": "NOT_DECIDED", "attestation_status": None,
              "bundle": None, "run_id": None, "contract_version": None,
              "checks": 0, "reason": "no official contract execution record"}
    record = official_results.get((feature_id, behavior_id))
    if not record:
        return result
    result.update({
        "run_id": record.get("run_id"),
        "bundle": record.get("bundle_path"),
        "contract_version": record.get("contract_version"),
        "attestation_status": record.get("attestation_status"),
        "execution_status": record.get("execution_status"),
        "evaluation_status": record.get("official_evaluation_status"),
        "reason": str(record.get("detail") or ""),
        "executed": record.get("execution_status") in
                    ("PASSED", "FAILED", "TIMEOUT", "INCONCLUSIVE"),
    })
    if record.get("execution_status") in ("ENVIRONMENT_BLOCKED", "RUNNER_ERROR"):
        result["status"] = "OFFICIAL_EXECUTION_BLOCKED"
        return result
    if record.get("execution_status") != "PASSED":
        result["status"] = "OFFICIAL_EXECUTION_FAILED"
        return result
    if record.get("official_contract_status") == cbe.STATUS_FAIL:
        result["status"] = "OFFICIAL_FAIL"
        return result
    if record.get("official_contract_status") != cbe.STATUS_PASS:
        result["status"] = "OFFICIAL_INCOMPLETE"
        return result
    if record.get("evidence_status") != "EVIDENCE_VERIFIED":
        result["status"] = "OFFICIAL_EVIDENCE_INVALID"
        result["reason"] = "official evidence sidecar is not verified"
        return result
    if record.get("attestation_status") != "ATTESTED_VERIFIED":
        result["status"] = "OFFICIAL_ATTESTATION_INVALID"
        result["reason"] = "official attestation is not verified"
        return result

    bundle_rel = str(record.get("bundle_path") or "")
    bundle_path = os.path.join(PROJECT_ROOT, bundle_rel)
    if not bundle_rel or not os.path.isfile(bundle_path):
        result["status"] = "OFFICIAL_EVIDENCE_INVALID"
        result["reason"] = "official bundle not found"
        return result
    try:
        with open(bundle_path, encoding="utf-8") as handle:
            bundle = json.load(handle)
    except (OSError, ValueError) as exc:
        result["status"] = "OFFICIAL_EVIDENCE_INVALID"
        result["reason"] = "official bundle unreadable: %r" % (exc,)
        return result
    if not _bundle_integrity_ok(bundle_path, bundle):
        result["status"] = "OFFICIAL_EVIDENCE_INVALID"
        result["reason"] = "official bundle payload sha256 mismatch"
        return result
    block = bundle.get("official_contract")
    if not isinstance(block, dict):
        result["status"] = "OFFICIAL_EVIDENCE_INVALID"
        result["reason"] = "bundle has no official_contract block"
        return result
    if str(block.get("behavior")) != "%s/%s" % (feature_id, behavior_id):
        result["status"] = "OFFICIAL_EVIDENCE_INVALID"
        result["reason"] = "official block behavior mismatch"
        return result

    violation = _official_contract_violation(feature_id, behavior_id, block,
                                              bundle, features_dir)
    if violation:
        result["status"], result["reason"] = violation
        return result

    try:
        from provenance.trust_store import TrustStore
        from provenance.verification import verify_evidence_bundle
        evidence_verdict = verify_evidence_bundle(
            bundle_path, bundle, trust_store=TrustStore(project_root=PROJECT_ROOT))
    except Exception as exc:                                   # noqa: BLE001
        result["status"] = "OFFICIAL_EVIDENCE_INVALID"
        result["reason"] = "official evidence verification error: %r" % (exc,)
        return result
    evidence_status = str((evidence_verdict.get("verification") or {}).get("status")
                          or evidence_verdict.get("status") or "")
    if evidence_status != "SIGNATURE_VALID":
        result["status"] = "OFFICIAL_EVIDENCE_INVALID"
        result["reason"] = "official evidence signature invalid: %s" % evidence_status
        return result
    if str(evidence_verdict.get("content_digest") or "") != str(
            record.get("evidence_digest") or ""):
        result["status"] = "OFFICIAL_EVIDENCE_INVALID"
        result["reason"] = "official evidence digest is not the attested digest"
        return result

    manifest_rel = str(record.get("manifest_path") or "")
    attestation_rel = str(record.get("attestation_path") or "")
    manifest_path = os.path.join(PROJECT_ROOT, manifest_rel)
    attestation_path = os.path.join(PROJECT_ROOT, attestation_rel)
    if not manifest_rel or not os.path.isfile(manifest_path) or \
            not attestation_rel or not os.path.isfile(attestation_path):
        result["status"] = "OFFICIAL_ATTESTATION_INVALID"
        result["reason"] = "official manifest/attestation not found"
        return result
    try:
        from execution.attestation import verify_attestation
        from provenance.trust_store import TrustStore
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        with open(attestation_path, encoding="utf-8") as handle:
            attestation = json.load(handle)
        envelope_path = attestation_path + ".sig.json"
        with open(envelope_path, encoding="utf-8") as handle:
            envelope = json.load(handle)
        verdict = verify_attestation(
            attestation=attestation, signature_envelope=envelope, manifest=manifest,
            trust_store=TrustStore(project_root=PROJECT_ROOT))
    except Exception as exc:                                   # noqa: BLE001
        result["status"] = "OFFICIAL_ATTESTATION_INVALID"
        result["reason"] = "official attestation verification error: %r" % (exc,)
        return result
    if verdict.get("status") != "ATTESTED_VERIFIED":
        result["status"] = "OFFICIAL_ATTESTATION_INVALID"
        result["reason"] = str(verdict.get("reason") or verdict.get("status"))
        return result
    attested = attestation.get("official_contract")
    if not isinstance(attested, dict) or \
            str(attested.get("contract_digest")) != str(block.get("contract_digest")) or \
            str(attested.get("evidence_payload_sha256")) != str(
                record.get("evidence_digest") or "") or \
            str(attested.get("behavior")) != "%s/%s" % (feature_id, behavior_id):
        result["status"] = "OFFICIAL_ATTESTATION_INVALID"
        result["reason"] = "attestation does not bind this official contract"
        return result

    result.update({"status": "OFFICIAL_PASS",
                   "checks": len(block.get("contract_expected") or []),
                   "reason": "official contract executed, keyed PASS, evidence and "
                             "attestation verified"})
    return result


def _official_contract_violation(feature_id: str, behavior_id: str, block: dict,
                                  bundle: dict, features_dir: str) -> tuple:
    """契约/观测/按键判定的独立复算；返回 (status, reason) 或 None。"""
    try:
        version, _expected, core = bc.contract_digest(
            feature_id, behavior_id, features_dir)
        current_digest = _official_sha256_text(core)
    except Exception as exc:                                   # noqa: BLE001
        return ("OFFICIAL_CONTRACT_MISMATCH", "current contract unreadable: %r" % (exc,))
    if str(block.get("contract_version")) != str(version) or \
            str(block.get("contract_digest")) != current_digest:
        return ("OFFICIAL_CONTRACT_MISMATCH",
                "official execution was produced against a different contract")
    record = _official_behavior_record(bundle, feature_id, behavior_id)
    if not record:
        return ("OFFICIAL_EVIDENCE_INVALID", "official bundle has no behavior record")
    actual = record.get("actual")
    if _official_sha256_text(fbe.canonical_json(actual or [])) != \
            str(block.get("observation_digest") or ""):
        return ("OFFICIAL_EVIDENCE_INVALID", "official observation digest mismatch")
    keyed = cbe.judge_record_keyed(record, {"expected": block.get("contract_expected") or []})
    if str(keyed.get("status")) != cbe.STATUS_PASS or \
            str(block.get("judge_status")) != cbe.STATUS_PASS:
        return ("OFFICIAL_FAIL" if str(keyed.get("status")) == cbe.STATUS_FAIL
                else "OFFICIAL_EVIDENCE_INVALID",
                "keyed judge is %s: %s" % (keyed.get("status"), keyed.get("detail")))
    if _official_sha256_text(fbe.canonical_json(keyed)) != str(block.get("judge_digest") or ""):
        return ("OFFICIAL_EVIDENCE_INVALID", "stored keyed judge digest mismatch")
    return None


def missing_and_next(row: dict) -> tuple[list, str]:
    missing, actions = [], []
    if row["binding"]["status"] != "APPROVED":
        missing.append("approved_binding")
        actions.append("generate/approve a binding candidate for this behavior "
                       "(binding_candidates.py approve)")
    if row["evidence"]["status"] != "EVIDENCE_VERIFIED":
        missing.append("verified_evidence")
        actions.append("collect real evidence (feature_behavior_evidence.py --feature)")
    if row["signature"]["status"] != "SIGNATURE_VERIFIED":
        missing.append("verified_signature")
        actions.append("sign the evidence bundle with the trust-root key "
                       "(provenance_cli.py sign-evidence)")
    if row["attestation"]["status"] != "ATTESTATION_VERIFIED":
        missing.append("verified_attestation")
        actions.append("run the execution provenance E2E to produce a signed "
                       "manifest/attestation for this run")
    if row["evaluation"]["status"] not in ("VERIFIED_PASS", "VERIFIED_FAIL",
                                           "INVALID_EVIDENCE"):
        missing.append("evaluation")
        actions.append("run evidence_eval.py for this behavior")
    elif row["evaluation"]["status"] != "VERIFIED_PASS":
        actions.append("investigate evaluation status %s" % row["evaluation"]["status"])
    if row["holdout"]["status"] in ("NO_HOLDOUT", "HOLDOUT_CONSUMED", "HOLDOUT_INVALID"):
        missing.append("holdout")
        actions.append("collect an independent batch and seal a fresh holdout dataset")
    if row["mutation"]["status"] in ("NOT_TESTED", "MUTATION_INVALID", "MUTATION_ERROR"):
        missing.append("l5_mutation")
        if row["mutation"]["status"] != "NOT_TESTED":
            actions.append("fix or redesign the mutation for this behavior")
        else:
            actions.append("design a high-value mutation for this behavior")
    return missing, "; ".join(actions[:2])


# ---------------------------------------------------------------- 汇总

def build_matrix(features_dir: str, evidence_dirs: list, eval_dirs: list,
                 mutation_report_dir: str = "", runs_dir: str = "",
                 feature_filter: str = "", behavior_filter: str = "",
                 include_legacy: bool = False,
                 holdout_registry_path: str = "",
                 official_results_path: str = "") -> dict:
    sys.path.insert(0, os.path.join(_TOOLS, "evaluation"))
    import evidence_adapter as adapter                 # noqa: E402
    supported = adapter.supported_set(features_dir)
    official_results = _load_official_results(
        official_results_path or OFFICIAL_RESULTS_PATH)
    rows = []
    for feature_id in sorted(supported["features"]):
        if feature_filter and feature_id != feature_filter:
            continue
        for behavior_id in supported["features"][feature_id]:
            if behavior_filter and behavior_id != behavior_filter:
                continue
            contract_status, contract_version = contract_dimension(
                feature_id, behavior_id, features_dir)
            binding = binding_dimension(feature_id, behavior_id, contract_version)
            evidence = evidence_dimension(feature_id, behavior_id, evidence_dirs,
                                          features_dir)
            signature = signature_dimension(evidence)
            attestation = attestation_dimension(feature_id, behavior_id, evidence, runs_dir)
            evaluation = evaluation_dimension(feature_id, behavior_id, eval_dirs)
            holdout = holdout_dimension(feature_id, behavior_id,
                                        registry_path=holdout_registry_path)
            mutation = mutation_dimension(feature_id, behavior_id, mutation_report_dir)
            official_contract = official_contract_dimension(
                feature_id, behavior_id, official_results, features_dir)
            row = {
                "feature_id": feature_id, "behavior_id": behavior_id,
                "contract_status": contract_status, "contract_version": contract_version,
                "binding": binding, "evidence": evidence, "signature": signature,
                "attestation": attestation, "evaluation": evaluation,
                "holdout": holdout, "mutation": mutation,
                "official_contract": official_contract,
                "latest_run_id": evidence.get("run_id"),
                "latest_evidence_digest": evidence.get("bundle_digest"),
                "latest_attestation_digest": attestation.get("attestation_digest"),
            }
            row["missing_requirements"], row["next_recommended_action"] = \
                missing_and_next(row)
            rows.append(row)
    summary = build_summary(supported, rows, include_legacy=include_legacy)
    return {"schema": "phase_1_63_coverage_matrix", "schema_version": 1,
            "summary": summary, "rows": rows}


def build_summary(supported: dict, rows: list, include_legacy: bool = False) -> dict:
    total = len(rows)
    def count(pred) -> int:
        return sum(1 for r in rows if pred(r))
    evidence_verified = count(
        lambda r: r["evidence"]["status"] == "EVIDENCE_VERIFIED" or
        (include_legacy and r["evidence"]["status"] == "LEGACY_EVIDENCE"))
    summary = {
        "supported_features": supported["feature_count"],
        "supported_behaviors": supported["behavior_count"],
        "matrix_rows": total,
        "support_source": supported["source"],
        "denominator_note": "all ratios use the dynamic supported set as denominator",
        "contract_coverage": count(lambda r: r["contract_status"] == "CONTRACT_PRESENT"),
        "binding_coverage": count(lambda r: r["binding"]["status"] != "NO_BINDING"),
        "approved_binding_coverage": count(
            lambda r: r["binding"]["status"] == "APPROVED"),
        "evidence_verified": evidence_verified,
        "signature_verified": count(
            lambda r: r["signature"]["status"] == "SIGNATURE_VERIFIED"),
        "attestation_verified": count(
            lambda r: r["attestation"]["status"] == "ATTESTATION_VERIFIED"),
        "evaluation_verified": count(
            lambda r: r["evaluation"]["status"] == "VERIFIED_PASS"),
        "holdout_available": count(
            lambda r: r["holdout"]["status"] == "HOLDOUT_AVAILABLE"),
        "mutation_killed": count(lambda r: r["mutation"]["status"] == "MUTATION_KILLED"),
        "mutation_invalid": count(lambda r: r["mutation"]["status"] == "MUTATION_INVALID"),
        "official_contract_total": total,
        "official_contract_executed": count(
            lambda r: r["official_contract"].get("executed")),
        "official_contract_passed": count(
            lambda r: r["official_contract"]["status"] == "OFFICIAL_PASS"),
        "official_contract_failed": count(
            lambda r: r["official_contract"]["status"] == "OFFICIAL_FAIL"),
        "official_contract_incomplete": count(
            lambda r: r["official_contract"]["status"] in
            ("OFFICIAL_INCOMPLETE", "OFFICIAL_EXECUTION_FAILED",
             "OFFICIAL_EXECUTION_BLOCKED")),
        "official_contract_evidence_invalid": count(
            lambda r: r["official_contract"]["status"] == "OFFICIAL_EVIDENCE_INVALID"),
        "official_contract_attestation_invalid": count(
            lambda r: r["official_contract"]["status"] == "OFFICIAL_ATTESTATION_INVALID"),
        "official_contract_contract_mismatch": count(
            lambda r: r["official_contract"]["status"] == "OFFICIAL_CONTRACT_MISMATCH"),
        "official_contract_execution_failed": count(
            lambda r: r["official_contract"]["status"] == "OFFICIAL_EXECUTION_FAILED"),
        "official_contract_execution_blocked": count(
            lambda r: r["official_contract"]["status"] == "OFFICIAL_EXECUTION_BLOCKED"),
        "official_contract_not_decided": count(
            lambda r: r["official_contract"]["status"] == "NO_OFFICIAL_EXECUTION"),
        "official_attestation_verified": count(
            lambda r: r["official_contract"].get("attestation_status") == "ATTESTED_VERIFIED"),
        "official_contract_fully_covered": count(
            lambda r: r["official_contract"]["status"] == "OFFICIAL_PASS"),
        "fully_covered": count(lambda r: not r["missing_requirements"]),
        "behaviors_with_gaps": count(lambda r: r["missing_requirements"]),
    }
    return summary


def to_markdown(document: dict) -> str:
    lines = ["# Phase 1.63 Coverage Matrix", "",
             "生成时间：%s" % document["generated_at"], ""]
    s = document["summary"]
    lines += ["## 汇总（分母 = 动态正式支持集 %d Behavior / %d Feature）" %
              (s["supported_behaviors"], s["supported_features"]), "",
              "| 指标 | 数值 | 比例 |", "| --- | --- | --- |"]
    for key, label in (("contract_coverage", "Contract"),
                       ("binding_coverage", "Binding（含非 APPROVED）"),
                       ("approved_binding_coverage", "Approved Binding"),
                       ("evidence_verified", "Evidence Verified"),
                       ("signature_verified", "Signature Verified"),
                       ("attestation_verified", "Attestation Verified"),
                       ("evaluation_verified", "Evaluation VERIFIED_PASS"),
                       ("holdout_available", "Holdout Available"),
                       ("mutation_killed", "L5 Mutation Killed"),
                       ("mutation_invalid", "L5 Mutation Invalid"),
                       ("official_contract_passed", "Official Contract PASS"),
                       ("official_contract_failed", "Official Contract FAIL"),
                       ("official_contract_incomplete", "Official Contract INCOMPLETE"),
                       ("official_contract_evidence_invalid", "Official Evidence INVALID"),
                       ("official_contract_attestation_invalid", "Official Attestation INVALID"),
                       ("official_contract_contract_mismatch", "Official Contract MISMATCH"),
                       ("official_contract_execution_failed", "Official Execution FAILED"),
                       ("official_contract_execution_blocked", "Official Execution BLOCKED"),
                       ("official_contract_not_decided", "Official Contract NOT_DECIDED"),
                       ("official_contract_fully_covered", "Official Contract Fully Covered"),
                       ("fully_covered", "Fully Covered"),
                       ("behaviors_with_gaps", "Behaviors With Gaps")):
        value = s[key]
        ratio = ("%.0f%%" % (100.0 * value / s["supported_behaviors"])
                 if s["supported_behaviors"] else "n/a")
        lines.append("| %s | %d | %s |" % (label, value, ratio))
    lines += ["", "## 逐 Behavior 状态", "",
              "| Feature | Behavior | Contract | Binding | Evidence | Signature | "
              "Attestation | Evaluation | Holdout | Mutation | Official | 下一步 |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in document["rows"]:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["feature_id"], r["behavior_id"], r["contract_status"],
            r["binding"]["status"], r["evidence"]["status"], r["signature"]["status"],
            r["attestation"]["status"], r["evaluation"]["status"],
            r["holdout"]["status"], r["mutation"]["status"],
            r["official_contract"]["status"],
            (r["next_recommended_action"] or "-")[:60]))
    return "\n".join(lines) + "\n"


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features-dir", default=os.path.join(PROJECT_ROOT, "Features"))
    parser.add_argument("--output-dir", default=os.path.join(PROJECT_ROOT, ".ai", "context"))
    parser.add_argument("--format", choices=("json", "markdown", "both"), default="both")
    parser.add_argument("--strict", action="store_true",
                        help="exit 2 when any supported behavior misses requirements")
    parser.add_argument("--feature", default="")
    parser.add_argument("--behavior", default="")
    parser.add_argument("--include-legacy", action="store_true",
                        help="count LEGACY_EVIDENCE bundles as verified evidence in summary")
    parser.add_argument("--evidence-dir", action="append", default=[],
                        help="extra evidence dir (repeatable)")
    parser.add_argument("--eval-dir", action="append", default=[])
    parser.add_argument("--mutation-report-dir", default="")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--holdout-registry", default="")
    parser.add_argument("--official-results", default=OFFICIAL_RESULTS_PATH,
                        help="official contract execution index (Phase 1.68.2)")
    args = parser.parse_args(argv)

    evidence_dirs = DEFAULT_EVIDENCE_DIRS + args.evidence_dir
    eval_dirs = args.eval_dir or [EVAL_REPORT_DIR]
    try:
        document = build_matrix(
            args.features_dir, evidence_dirs, eval_dirs,
            mutation_report_dir=args.mutation_report_dir, runs_dir=args.runs_dir,
            feature_filter=args.feature, behavior_filter=args.behavior,
            include_legacy=args.include_legacy,
            holdout_registry_path=args.holdout_registry,
            official_results_path=args.official_results)
    except Exception as exc:                                   # noqa: BLE001
        print("ERROR: coverage matrix computation failed: %r" % (exc,))
        return EXIT_ERROR

    document["generated_at"] = bc.now_iso()
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "coverage_matrix.json")
    md_path = os.path.join(args.output_dir, "coverage_matrix.md")
    if args.format in ("json", "both"):
        with open(json_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print("json ->", json_path)
    if args.format in ("markdown", "both"):
        with open(md_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(to_markdown(document))
        print("markdown ->", md_path)
    s = document["summary"]
    print("rows=%d fully_covered=%d with_gaps=%d"
          % (s["matrix_rows"], s["fully_covered"], s["behaviors_with_gaps"]))
    if args.strict and s["behaviors_with_gaps"]:
        print("STRICT: %d behaviors miss requirements" % s["behaviors_with_gaps"])
        return EXIT_STRICT
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
