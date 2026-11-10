#!/usr/bin/env python3
"""Evidence-backed Evaluation Runner（Phase 1.58）。

回答的问题是：**行为证据有效之后，行为本身是否真的达到了评估标准**。

三种模式（互不混算，报告里逐任务标注）：

    Mode A  evidence  —— 读取已落盘的证据包 → Validator 复核 → Adapter → 期望比对
    Mode B  probe     —— 先跑采集器（真实 Godot）产生新证据 → 同一条 Validator 链路
    Mode C  LEGACY    —— `runner.py` 的旧 Probe-only 任务，不进入 VERIFIED_* 统计

本入口只做「读 + 判 + 报告」：不生成 Feature、不写证据包（Mode B 由采集器写）、
不审批/更新 Golden Trace Baseline、不修改任何既有证据。

用法：
    python .ai/tools/evaluation/evidence_eval.py --list
    python .ai/tools/evaluation/evidence_eval.py --evidence-dir .ai/tmp/p157/bundles_real
    python .ai/tools/evaluation/evidence_eval.py --task E1 E3
    python .ai/tools/evaluation/evidence_eval.py --holdout-dir <dir>     # Holdout 独立批次
    python .ai/tools/evaluation/evidence_eval.py --no-collect            # 跳过 Mode B 采集
    python .ai/tools/evaluation/evidence_eval.py --trace <trace.json> --baseline <baseline.json>

退出码（只看主任务，Holdout 缺口单独报告，不伪装成通过）：
    0 = 全部任务 VERIFIED_PASS 且无结构错误
    1 = 存在 VERIFIED_FAIL / INVALID_EVIDENCE / EVALUATION_ERROR
    2 = 无失败但存在 INCOMPLETE（证据不足）或任务未执行
    3 = 内部错误（配置无法解析等）
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import evidence_adapter as adapter                              # noqa: E402

try:                                                            # Phase 1.60：绑定与 Holdout 登记
    import trace_bindings as trace_bindings
except ImportError:                                             # pragma: no cover
    trace_bindings = None
try:
    import holdout_registry as holdout_registry
except ImportError:                                             # pragma: no cover
    holdout_registry = None

try:
    import yaml
except ImportError:                                             # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

try:                                                            # Phase 1.61：来源签名
    from provenance.trust_store import TrustStore as provenance_TrustStore
    from provenance import verification as provenance_verification
except ImportError:                                             # pragma: no cover
    provenance_TrustStore = None
    provenance_verification = None

SCHEMA = "evaluation_evidence_report"
SCHEMA_VERSION = 1
DEFAULT_TASKS = os.path.join(_HERE, "evidence_tasks.yaml")
DEFAULT_RUNS_DIRNAME = ".ai/tmp/eval"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _relative(path: str) -> str:
    try:
        return os.path.relpath(os.path.abspath(path), PROJECT_ROOT).replace("\\", "/")
    except (OSError, ValueError):
        return path


def git_state() -> dict:
    def _git(*args: str) -> str:
        try:
            proc = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=30, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as exc:
            return "<error: %s>" % exc
        return (proc.stdout or "").strip()

    status = [line for line in _git("status", "--porcelain=v1").splitlines() if line.strip()]
    return {"head": _git("rev-parse", "--short", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "modified": sum(1 for line in status if not line.startswith("??")),
            "untracked": sum(1 for line in status if line.startswith("??"))}


def load_tasks(path: str) -> dict:
    document = yaml.safe_load(open(path, "r", encoding="utf-8").read())
    if not isinstance(document, dict) or not isinstance(document.get("tasks"), list):
        raise SystemExit("FAIL: %s is not an evaluation evidence task document" % path)
    schema = document.get("schema") or {}
    if schema.get("id") != "evaluation_evidence_tasks":
        raise SystemExit("FAIL: %s has unknown task schema %r" % (path, schema.get("id")))
    return document


# ---------------------------------------------------------------- Mode B 采集

def _resolve_artifact_root(value: str) -> str:
    """任务文件里的 artifact_root 可能是仓库相对路径，也可能是绝对路径。"""
    if not value:
        return ""
    return value if os.path.isabs(value) else os.path.join(PROJECT_ROOT, value)


def collect_feature(feature: str, out_dir: str, collector: str,
                    artifact_root: str = "", timeout: int = 900) -> dict:
    """运行采集器产生新证据（真实 Godot）。只负责执行与记录，不解释结果。"""
    script = collector if os.path.isabs(collector) else os.path.join(_TOOLS, collector)
    argv = [sys.executable, script, "--feature", feature, "--evidence-out", out_dir]
    # 采集器没有 --artifact-root：它把执行产物写在默认根（.ai/tmp/behavior）下，
    # 并把路径写进 bundle。强行传参只会让采集器报 unrecognized arguments。
    started = time.time()
    try:
        proc = subprocess.run(argv, cwd=PROJECT_ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              stdin=subprocess.DEVNULL)
        exit_code, stdout, stderr = proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return {"command": [_relative(script), "--feature", feature, "--evidence-out",
                            _relative(out_dir)],
                "exit": None, "timeout_s": timeout, "duration_s": round(time.time() - started, 3),
                "output_tail": "", "status": "INCOMPLETE", "detail": "collector timeout"}
    except OSError as exc:
        return {"command": [_relative(script)], "exit": None, "duration_s": 0.0,
                "output_tail": "", "status": "UNAVAILABLE", "detail": repr(exc)}
    return {
        "command": [_relative(script), "--feature", feature, "--evidence-out",
                    _relative(out_dir)],
        "exit": exit_code,
        "duration_s": round(time.time() - started, 3),
        "output_tail": "\n".join((stdout + "\n" + stderr).strip().splitlines()[-8:]),
        "status": "PASS" if exit_code == 0 else "FAIL",
        "detail": "" if exit_code == 0 else "collector exit %s (evidence may be inconsistent)" % exit_code,
    }


# ---------------------------------------------------------------- 任务执行

def select_tasks(tasks: list, wanted: list) -> list:
    if not wanted or "ALL" in [item.upper() for item in wanted]:
        return tasks
    wanted_upper = [item.upper() for item in wanted]
    known = {str(task.get("id")).upper() for task in tasks}
    unknown = [item for item in wanted_upper if item not in known]
    if unknown:
        raise SystemExit("FAIL: unknown task ids: %s" % ", ".join(unknown))
    return [task for task in tasks if str(task.get("id")).upper() in wanted_upper]


# Holdout 签名失败 -> 细分原因词表（语义互斥，不得伪装成普通 NOT_EVALUATED 缺口）
_HOLDOUT_PROV_REASON = {
    "SIGNATURE_MISSING": "holdout_signature_missing",
    "KEY_UNKNOWN": "holdout_signer_untrusted",
    "KEY_REVOKED": "holdout_revoked",
    "DIGEST_MISMATCH": "holdout_digest_mismatch",
    "SIGNATURE_INVALID": "holdout_signature_invalid",
    "SCOPE_MISMATCH": "holdout_signature_invalid",
    "ALGORITHM_MISMATCH": "holdout_signature_invalid",
    "TRUST_ROOT_MISSING": "holdout_signature_invalid",
    "TRUST_ROOT_UNREADABLE": "holdout_signature_invalid",
    "TRUST_ROOT_INSECURE_LOCATION": "holdout_signature_invalid",
    "LIBRARY_UNAVAILABLE": "holdout_signature_invalid",
}


def _verify_holdout_provenance(entry: dict, task: dict, signature_policy: str,
                               gate_report: dict,
                               trust_root_path: str = "") -> dict | None:
    """Phase 1.61：Holdout 数据集来源签名验证（返回 None = 未启用门禁）。

    usable=False 时 reason/detail 携带细分原因；消费（record_usage）必须
    在验证通过后才允许发生。
    """
    if not signature_policy or provenance_verification is None:
        return None
    trust_store = provenance_TrustStore(trust_root_path,
                                        project_root=adapter.PROJECT_ROOT)
    evaluated = provenance_verification.evaluate_signature(
        entry.get("provenance_signature"),
        object_type="holdout_dataset",
        object_id=str(entry.get("holdout_id") or ""),
        object_version=str(entry.get("dataset_version") or ""),
        expected_digest=str(entry.get("content_digest") or ""),
        expected_digest_scheme=str(entry.get("digest_scheme") or ""),
        trust_store=trust_store, signature_policy=signature_policy)
    verification = evaluated.get("verification") or {}
    usable = bool(evaluated.get("usable"))
    # 来源交叉核对（A12）：签名内 binding.source 必须与登记记录一致。
    if usable:
        envelope = entry.get("provenance_signature") or {}
        signed_source = str((envelope.get("binding") or {}).get("source") or "")
        if signed_source and \
                str(entry.get("source") or "") != signed_source:
            usable = False
            evaluated["trust_level"] = "SIGNATURE_INVALID"
            verification = dict(verification)
            verification["status"] = "SIGNATURE_INVALID"
            verification["reason"] = ("registered source %r does not match the "
                                      "signed provenance %r; the holdout "
                                      "registry was modified after sealing"
                                      % (entry.get("source"), signed_source))
    return {
        "usable": usable,
        "trust_level": evaluated.get("trust_level"),
        "status": verification.get("status"),
        "signer_subject": verification.get("signer_subject"),
        "signer_key_id": verification.get("signer_key_id"),
        "trust_root_status": verification.get("trust_root_status"),
        "reason": _HOLDOUT_PROV_REASON.get(str(verification.get("status")),
                                           "holdout_signature_invalid")
                  if not usable else "",
        "detail": verification.get("reason", "") if not usable else "",
        "note": "signature proves who sealed the dataset; it does not prove "
                "the dataset collection itself was authentic",
    }


def run(args) -> dict:
    started = time.time()
    document = load_tasks(args.tasks_file)
    run_config = document.get("run") or {}
    tasks = select_tasks(list(document["tasks"]), list(args.task or []))

    # 任务集结构校验（重复 ID / 重复映射）—— 结构错误让整次运行失败，不静默降级
    problems: list = []
    ids = [str(task.get("id")) for task in tasks]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        problems.append("duplicate task id(s): %s" % ", ".join(duplicates))
    problems.extend(adapter.duplicate_mappings(tasks))

    run_dir = os.path.join(PROJECT_ROOT, args.runs_dir,
                           "%d-%s" % (os.getpid(), uuid.uuid4().hex[:8]))
    os.makedirs(run_dir, exist_ok=False)

    # ---- Phase 1.61：来源签名门禁（缺省关闭 = 1.58/1.60 语义不变）----
    # require 模式 fail-closed：缺签名 / 签名无效 / 信任根缺失一律拒绝，
    # 不自动降级 Legacy；allow-legacy 模式只把无效签名作为拒绝依据。
    signature_policy = ""
    if getattr(args, "require_signature", False):
        signature_policy = "require"
    elif getattr(args, "allow_legacy", False):
        signature_policy = "allow_legacy"
    provenance_policy = adapter.PROVENANCE_OFF
    provenance_gate_report: dict = {"active": False, "policy": "",
                                    "trust_root": None}
    if signature_policy:
        if provenance_TrustStore is None:
            raise SystemExit("FAIL: provenance module unavailable; "
                             "signature gate cannot be enabled (fail-closed)")
        trust_store = provenance_TrustStore(
            getattr(args, "trust_root", "") or "",
            project_root=adapter.PROJECT_ROOT)
        adapter.set_signature_gate(trust_store, signature_policy)
        provenance_policy = (adapter.PROVENANCE_REQUIRE
                             if signature_policy == "require"
                             else adapter.PROVENANCE_VERIFY)
        summary = trust_store.trust_summary()
        provenance_gate_report = {"active": True, "policy": signature_policy,
                                  "trust_root": {"path": summary.get("path"),
                                                 "status": summary.get("status"),
                                                 "source": summary.get("source_kind"),
                                                 "keys": summary.get("keys")}}
        if not summary.get("ok") and signature_policy == "require":
            # require 模式：外部信任根缺失不是"退回 Legacy"的理由，整次运行
            # 的签名验证会逐对象 fail-closed；这里只记录，具体对象各自拒绝。
            pass

    supported = adapter.supported_set()
    configured_root = _resolve_artifact_root(str(run_config.get("artifact_root") or ""))
    artifact_roots = [args.artifact_root] if args.artifact_root else \
        ([configured_root] if configured_root else None)

    # ---- Phase 1.60：加载 Trace/Behavior 绑定库（缺省路径存在即加载；
    #      未声明的任务语义不变，绑定只作诊断；声明 expected_source 的任务走门禁）
    bindings_doc = None
    if trace_bindings is not None:
        bindings_path = args.bindings or trace_bindings.BINDINGS_PATH
        try:
            bindings_doc = trace_bindings.load_bindings(bindings_path)
        except (OSError, ValueError) as exc:
            if args.bindings:
                raise SystemExit("FAIL: cannot load bindings %s: %s" % (args.bindings, exc))
            bindings_doc = None

    # ---- Mode B：先采集（每个 Feature 一次），再走同一条验证链路
    probe_tasks = [task for task in tasks
                   if str(task.get("mode") or "") == adapter.MODE_PROBE and not task.get("holdout")]
    collections: list = []
    probe_dir = os.path.join(run_dir, "probe-evidence")
    if probe_tasks and not args.no_collect:
        os.makedirs(probe_dir, exist_ok=True)
        for feature in sorted({str(task.get("feature")) for task in probe_tasks}):
            collections.append(collect_feature(
                feature, probe_dir, str(run_config.get("collector")
                                        or "scene_composer/feature_behavior_evidence.py"),
                artifact_root=str(args.artifact_root
                                  or configured_root or ""),
                timeout=int(args.collect_timeout)))

    main_tasks = [task for task in tasks if not task.get("holdout")]
    holdout_tasks = [task for task in tasks if task.get("holdout")]

    evidence_dir = args.evidence_dir or str(run_config.get("evidence_dir") or "")
    verified = adapter.load_verified(
        evidence_dir=evidence_dir,
        features=sorted({str(task.get("feature")) for task in main_tasks
                         if str(task.get("mode") or "") != adapter.MODE_PROBE}),
        max_age_hours=float(args.max_age_hours or run_config.get("max_age_hours") or 24.0),
        artifact_roots=artifact_roots,
        provenance_policy=provenance_policy)
    probe_verified = None
    if probe_tasks and not args.no_collect:
        probe_verified = adapter.load_verified(
            evidence_dir=probe_dir,
            features=sorted({str(task.get("feature")) for task in probe_tasks}),
            max_age_hours=float(args.max_age_hours or run_config.get("max_age_hours") or 24.0),
            # 采集器的产物落在默认根（.ai/tmp/behavior）下；artifact_roots 为 None 时
            # 用解析器的默认根集合，绝不能只授权 probe_dir 而把它自己的产物拒掉。
            artifact_roots=artifact_roots + [probe_dir] if artifact_roots else None,
            provenance_policy=provenance_policy)

    def _verified_for(task):
        if str(task.get("mode") or "") == adapter.MODE_PROBE and probe_verified is not None:
            return probe_verified
        return verified

    results: list = []
    for task in main_tasks:
        if str(task.get("mode") or "") == adapter.MODE_PROBE and args.no_collect:
            # 显式跳过采集：没有证据就没有评估，不能记成 INCOMPLETE 之外的任何“通过”状态。
            record = {
                "task_id": task.get("id"),
                "title": task.get("title", ""),
                "feature_id": task.get("feature"),
                "behavior_id": str(task.get("behavior") or ""),
                "evaluation_mode": adapter.MODE_PROBE,
                "holdout": False,
                "evaluation_status": adapter.NOT_EVALUATED,
                "validator_status": "",
                "reason": "collection_skipped",
                "detail": "--no-collect: Mode B probe was not executed",
                "golden_trace": _golden_trace(task),
            }
            _decorate(record, task)
            results.append(record)
            continue
        record = adapter.evaluate_task(task, _verified_for(task), supported,
                                       bindings=bindings_doc)
        record["evaluation_mode"] = (adapter.MODE_PROBE
                                     if str(task.get("mode") or "") == adapter.MODE_PROBE
                                     else adapter.MODE_EVIDENCE)
        record["golden_trace"] = _golden_trace(task)
        _decorate(record, task)
        results.append(record)

    # ---- Holdout：独立目录 + 批次隔离
    holdout_block: dict = {"dir": "", "tasks": [], "isolation": {"status": "NOT_EVALUATED",
                                                                 "violations": []}}
    if holdout_tasks:
        if not args.holdout_dir:
            for task in holdout_tasks:
                results_holdout = {
                    "task_id": task.get("id"), "title": task.get("title", ""),
                    "feature_id": task.get("feature"),
                    "behavior_id": str(task.get("behavior") or ""),
                    "evaluation_mode": adapter.MODE_EVIDENCE, "holdout": True,
                    "evaluation_status": adapter.NOT_EVALUATED,
                    "reason": "holdout_unavailable",
                    "detail": "no --holdout-dir given: no holdout execution batch exists",
                    "golden_trace": _golden_trace(task),
                }
                holdout_block["tasks"].append(results_holdout)
            holdout_block["isolation"] = {"status": adapter.NOT_EVALUATED,
                                          "violations": [],
                                          "detail": "holdout batch not provided"}
        else:
            holdout_verified = adapter.load_verified(
                evidence_dir=args.holdout_dir,
                features=sorted({str(task.get("feature")) for task in holdout_tasks}),
                max_age_hours=float(args.max_age_hours or run_config.get("max_age_hours") or 24.0),
                artifact_roots=artifact_roots,
                provenance_policy=provenance_policy)
            violations = adapter.holdout_isolation(verified, holdout_verified)
            holdout_block["dir"] = _relative(args.holdout_dir)
            holdout_block["isolation"] = {
                "status": adapter.EVALUATION_ERROR if violations else "PASS",
                "violations": violations,
                "detail": "training and holdout evidence must not share a batch" if violations else "",
            }
            for task in holdout_tasks:
                if violations:
                    record = {"task_id": task.get("id"), "title": task.get("title", ""),
                              "feature_id": task.get("feature"),
                              "behavior_id": str(task.get("behavior") or ""),
                              "evaluation_mode": adapter.MODE_EVIDENCE, "holdout": True,
                              "evaluation_status": adapter.EVALUATION_ERROR,
                              "reason": "holdout_batch_leak",
                              "detail": "; ".join(violations),
                              "golden_trace": _golden_trace(task)}
                else:
                    record = adapter.evaluate_task(task, holdout_verified, supported,
                                                   holdout=True, bindings=bindings_doc)
                    record["evaluation_mode"] = adapter.MODE_EVIDENCE
                    record["golden_trace"] = _golden_trace(task)
                    _decorate(record, task)
                    # Phase 1.60：Holdout 数据集生命周期复核（登记存在时）
                    if holdout_registry is not None and task.get("holdout_id"):
                        entry = holdout_registry.find_dataset(
                            str(task["holdout_id"]),
                            dataset_version=task.get("holdout_dataset_version"))
                        if entry is None:
                            record["evaluation_status"] = adapter.NOT_EVALUATED
                            record["reason"] = "holdout_dataset_unregistered"
                            record["detail"] = ("holdout %r is not registered; "
                                                "register and seal it before use"
                                                % task.get("holdout_id"))
                        else:
                            # Phase 1.61：已消费的数据集单独报告（一次性消费语义）
                            if str(entry.get("status")) == "CONSUMED" and \
                                    entry.get("usage_history"):
                                record["evaluation_status"] = adapter.NOT_EVALUATED
                                record["reason"] = "holdout_already_consumed"
                                record["detail"] = ("holdout %s v%s was already "
                                                    "consumed %d time(s); re-seal "
                                                    "with a new dataset_version"
                                                    % (entry.get("holdout_id"),
                                                       entry.get("dataset_version"),
                                                       len(entry.get("usage_history") or [])))
                                record["holdout_dataset"] = {
                                    "holdout_id": entry.get("holdout_id"),
                                    "dataset_version": entry.get("dataset_version"),
                                    "status": entry.get("status")}
                                holdout_block["tasks"].append(record)
                                continue
                            # Phase 1.61：来源签名验证（消费前，fail-closed）
                            provenance_block = _verify_holdout_provenance(
                                entry, task, signature_policy,
                                provenance_gate_report,
                                trust_root_path=getattr(args, "trust_root", ""))
                            if provenance_block is not None and \
                                    not provenance_block.get("usable"):
                                record["evaluation_status"] = adapter.NOT_EVALUATED
                                record["reason"] = provenance_block["reason"]
                                record["detail"] = provenance_block["detail"]
                                record["holdout_provenance"] = provenance_block
                                holdout_block["tasks"].append(record)
                                continue
                            usable = holdout_registry.check_usable(entry)
                            record["holdout_dataset"] = {
                                "holdout_id": entry.get("holdout_id"),
                                "dataset_version": entry.get("dataset_version"),
                                "status": entry.get("status"),
                                "usable": usable["usable"],
                                "reason": usable["reason"],
                            }
                            if provenance_block is not None:
                                record["holdout_provenance"] = provenance_block
                            if not usable["usable"]:
                                record["evaluation_status"] = adapter.NOT_EVALUATED
                                record["reason"] = "holdout_dataset_unusable"
                                record["detail"] = usable["reason"]
                            else:
                                holdout_registry.record_usage(
                                    str(entry["holdout_id"]),
                                    str(entry["dataset_version"]),
                                    purpose="evaluation",
                                    run_ref=str(task.get("id")))
                holdout_block["tasks"].append(record)

    comparison = None
    if args.trace:
        baseline_path = args.baseline or os.path.join(
            adapter.VALIDATOR_DIR, "baselines", "%s.json" % (args.trace_scenario or "waves"))
        comparison = adapter.compare_with_baseline(baseline_path, args.trace)
        comparison["baseline_path"] = _relative(baseline_path)
        comparison["trace_path"] = _relative(args.trace)

    metrics = adapter.summarize(results, verified, supported=supported,
                                holdout_results=holdout_block["tasks"])
    metrics["evidence_validation"]["probe_mode"] = (
        (probe_verified.get("validator") or {}).get("status") if probe_verified else None)

    # Phase 1.60：绑定覆盖对账（场景列表动态来自 baselines 目录，不硬编码）
    scenarios = []
    baselines_dir = os.path.join(adapter.VALIDATOR_DIR, "baselines")
    if os.path.isdir(baselines_dir):
        scenarios = [name[:-5] for name in sorted(os.listdir(baselines_dir))
                     if name.endswith(".json") and name != "approval_registry.json"]
    reconciliation = adapter.binding_reconciliation(supported, bindings_doc, scenarios)

    report = {
        "schema": {"id": SCHEMA, "version": SCHEMA_VERSION},
        "run": {
            "token": os.path.basename(run_dir),
            "started": now_iso(),
            "duration_s": round(time.time() - started, 3),
            "git": git_state(),
            "tasks_file": _relative(args.tasks_file),
            "evidence_dir": _relative(evidence_dir) if evidence_dir else "",
            "holdout_dir": holdout_block.get("dir", ""),
            "modes": {"evidence": sum(1 for item in results
                                      if item.get("evaluation_mode") == adapter.MODE_EVIDENCE),
                      "probe": sum(1 for item in results
                                   if item.get("evaluation_mode") == adapter.MODE_PROBE),
                      "legacy_probe_only": 0},
        },
        "structural_problems": problems,
        "supported": {"features": supported["feature_count"],
                      "behaviors": supported["behavior_count"],
                      "source": supported["source"]},
        "evidence": {
            "validator": verified.get("validator"),
            "coverage": verified.get("coverage"),
            "bundles": verified.get("bundle_index"),
            "feature_errors": verified.get("feature_errors"),
            "undeclared_behaviors": verified.get("undeclared_behaviors"),
        },
        "collections": collections,
        "tasks": results,
        "holdout": holdout_block,
        "binding_reconciliation": reconciliation,
        "provenance": provenance_gate_report,
        "golden_trace": {
            "baselines": _baseline_rows(results + holdout_block["tasks"]),
            "comparison": comparison,
            "capability": {
                "per_behavior_binding": bool(reconciliation.get("bound_behaviors")),
                "note": "4 条编排场景基线仍为 scenario_only（不自动升级）；"
                        "逐行为绑定见 validator/bindings/behavior_bindings.json"
                        "（binding_status 逐任务诊断，expected_source 声明的任务"
                        "走绑定门禁），使用时摘要复核见 baseline_lifecycle。",
            },
        },
        "metrics": metrics,
        "limitations": [
            "证据来源真实性未解决：同一权限者仍可同时改写实现、证据与产物（Phase 1.57 结论）。",
            "Validator PASS 只表示证据可信，不等于行为达标；行为达标由本报告的 expect 比对决定。",
            "Golden Trace 目前只有编排场景级基线，没有 Feature/Behavior 绑定，不做逐行为 trace 比较。",
            "Holdout 目前没有独立的真实执行批次；未提供 --holdout-dir 时任务记为 NOT_EVALUATED。",
        ],
    }
    path = os.path.join(run_dir, "evidence_report.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    report["_report_path"] = _relative(path)
    adapter.clear_signature_gate()  # 门禁状态不跨运行泄漏（本模块级配置）
    return report


def _decorate(record: dict, task: dict) -> None:
    """把报告要求的可追溯字段提到任务级（首条行为），逐行为明细保留在 behaviors[]。"""
    first = (record.get("behaviors") or [{}])[0]
    record["execution_id"] = first.get("execution_id")
    record["evidence_bundle_ref"] = first.get("evidence_bundle_ref")
    record["artifact_digests"] = first.get("artifact_digests") or {}
    record["protocol_version"] = first.get("protocol_version")
    record["behavior_version"] = (record.get("golden_trace") or {}).get(
        "approved_behavior_version") or ""
    record["baseline_id"] = ((record.get("golden_trace") or {}).get("baseline") or {}).get(
        "baseline_id")
    record["requirement"] = str(task.get("requirement") or "")


def _golden_trace(task: dict) -> dict:
    """任务声明的 Golden Trace 引用：只报告元数据与绑定情况，不做逐行为比较。"""
    trace = task.get("trace") or {}
    if not trace:
        return {"status": "NOT_APPLICABLE", "reason": "task declares no trace",
                "baseline": None, "approved_behavior_version": None,
                "feature": None, "behavior": None}
    baseline = adapter.baseline_report(scenario=str(trace.get("scenario") or ""),
                                       path=str(trace.get("baseline") or ""))
    if baseline.get("status") == "PASS":
        status = "NOT_APPLICABLE"
        reason = ("baseline is approved but binds a scenario, not a Feature/Behavior; "
                  "per-behavior comparison is done on evidence observations")
    elif baseline.get("status") == "INCOMPLETE":
        status, reason = adapter.INCOMPLETE, baseline.get("reason", "baseline_missing")
    else:
        status, reason = adapter.EVALUATION_ERROR, baseline.get("reason", "baseline_invalid")
    return {
        "status": status,
        "reason": reason,
        "scenario": str(trace.get("scenario") or ""),
        "baseline": baseline,
        "baseline_id": baseline.get("baseline_id"),
        "baseline_version": baseline.get("baseline_version"),
        "approved_behavior_version": baseline.get("approved_behavior_version"),
        "feature": baseline.get("feature"),
        "behavior": baseline.get("behavior"),
        "binding": baseline.get("binding"),
    }


def _baseline_rows(task_results) -> list:
    rows = []
    for item in task_results:
        trace = item.get("golden_trace") or {}
        baseline = trace.get("baseline")
        if not baseline:
            continue
        rows.append({"task_id": item.get("task_id"),
                     "scenario": trace.get("scenario"),
                     "baseline_id": baseline.get("baseline_id"),
                     "baseline_version": baseline.get("baseline_version"),
                     "approved_behavior_version": baseline.get("approved_behavior_version"),
                     "approval_status": baseline.get("approval_status"),
                     "status": baseline.get("status"),
                     "binding": baseline.get("binding")})
    return rows


# ---------------------------------------------------------------- CLI

def print_summary(report: dict) -> None:
    print("Evidence Evaluation (%s)  tasks=%d  duration=%.1fs"
          % (report["run"]["token"], len(report["tasks"]), report["run"]["duration_s"]))
    print("evidence: %s  checked=%d pass=%d fail=%d incomplete=%d artifacts=%d cross_validated=%d"
          % (report["metrics"]["evidence_validation"]["status"],
             report["metrics"]["evidence_validation"]["checked"],
             report["metrics"]["evidence_validation"]["pass"],
             report["metrics"]["evidence_validation"]["fail"],
             report["metrics"]["evidence_validation"]["incomplete"],
             report["metrics"]["evidence_validation"]["artifacts"],
             report["metrics"]["evidence_validation"]["cross_validated"]))
    rejected = report["metrics"]["evidence_validation"].get("rejected_bundles") or []
    if rejected:
        # 逐条复算 pass 不等于整包有效：包级拒绝（摘要不符 / 过期 / 协议变更）单独列出。
        print("  rejected bundles: " + "; ".join(
            "%s=%s(%s)" % (item.get("bundle"), item.get("status"),
                            ",".join(item.get("reasons") or []) or "-")
            for item in rejected[:4]))
    print("%-4s %-20s %-16s %-10s %s"
          % ("id", "status", "validator", "mode", "reason"))
    for task in report["tasks"]:
        print("%-4s %-20s %-16s %-10s %s"
              % (task.get("task_id"), task.get("evaluation_status"),
                 task.get("validator_status") or "-", task.get("evaluation_mode"),
                 task.get("reason") or "-"))
    evaluation = report["metrics"]["behavior_evaluation"]
    print("\nbehavior_evaluation: " + "  ".join(
        "%s=%d" % (status, count) for status, count in evaluation.items() if count))
    coverage = report["metrics"]["coverage"]
    print("coverage: supported=%d evidence=%d evaluated=%d trace=%d holdout=%d"
          % (coverage["supported"], coverage["evidence"], coverage["evaluated"],
             coverage["golden_trace"], coverage["holdout"]))
    reconciliation = report.get("binding_reconciliation") or {}
    if reconciliation:
        print("bindings: supported_behaviors=%d bound=%d unbound=%d approved_bindings=%d"
              % (reconciliation.get("supported_behaviors", 0),
                 reconciliation.get("bound_behaviors", 0),
                 reconciliation.get("unbound_behaviors", 0),
                 reconciliation.get("approved_bindings", 0)))
        states = reconciliation.get("trace_binding_states") or {}
        if states:
            print("  trace states: " + "  ".join(
                "%s=%s" % (name, state) for name, state in sorted(states.items())))
    provenance_block = report.get("provenance") or {}
    if provenance_block.get("active"):
        trust = provenance_block.get("trust_root") or {}
        print("provenance: policy=%s trust_root=%s (%s) keys=%d"
              % (provenance_block.get("policy"), trust.get("status"),
                 trust.get("source"), len(trust.get("keys") or [])))
    if coverage["evidence_without_task"]:
        print("  evidence_without_task: %s" % ", ".join(coverage["evidence_without_task"][:6])
              + (" ..." if len(coverage["evidence_without_task"]) > 6 else ""))
    if report["holdout"]["tasks"]:
        holdout = report["metrics"]["holdout"]
        print("holdout: total=%d isolation=%s  %s"
              % (holdout["total"], report["holdout"]["isolation"]["status"],
                 " ".join("%s=%d" % (status, count) for status, count in holdout.items()
                          if count and status != "total")))
    if report["golden_trace"]["comparison"]:
        comparison = report["golden_trace"]["comparison"]
        print("golden_trace comparison: %s (%s vs %s events)"
              % (comparison.get("status"), comparison.get("actual_event_count"),
                 comparison.get("expected_event_count")))
    for problem in report["structural_problems"]:
        print("STRUCTURAL: %s" % problem)
    print("\nreport: %s" % report["_report_path"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", nargs="*", default=["all"], help="task ids (default: all)")
    parser.add_argument("--list", action="store_true", help="list tasks and exit")
    parser.add_argument("--tasks-file", default=DEFAULT_TASKS)
    parser.add_argument("--evidence-dir", default="",
                        help="evidence bundle directory (default: from tasks file run section)")
    parser.add_argument("--holdout-dir", default="", help="separate holdout evidence directory")
    parser.add_argument("--artifact-root", default="", help="authorized execution artifact root")
    parser.add_argument("--max-age-hours", type=float, default=0.0)
    parser.add_argument("--no-collect", action="store_true",
                        help="skip Mode B probe collection (evaluate existing evidence only)")
    parser.add_argument("--collect-timeout", type=int, default=900)
    parser.add_argument("--trace", default="", help="real trace document to compare with a baseline")
    parser.add_argument("--baseline", default="", help="baseline path (default: baselines/<scenario>.json)")
    parser.add_argument("--trace-scenario", default="waves")
    parser.add_argument("--bindings", default="",
                        help="behavior binding document (default: validator/bindings/"
                             "behavior_bindings.json when present)")
    parser.add_argument("--require-signature", action="store_true",
                        help="Phase 1.61 secure mode: every provenance check fails "
                             "closed (missing signature / missing external trust root "
                             "=> rejection; no automatic legacy downgrade)")
    parser.add_argument("--allow-legacy", action="store_true",
                        help="Phase 1.61 diagnostics mode: verify signatures when "
                             "present (invalid signature => rejection), unsigned data "
                             "stays LEGACY_APPROVED (default semantics, made explicit)")
    parser.add_argument("--trust-root", default="",
                        help="external trust root path (outside the workspace; "
                             "default: $%s or the per-project user-level trust root)"
                             % "PROVENANCE_TRUST_ROOT")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIRNAME)
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)

    if args.require_signature and args.allow_legacy:
        raise SystemExit("FAIL: --require-signature and --allow-legacy are "
                         "mutually exclusive (secure mode never downgrades to legacy)")

    if args.list:
        document = load_tasks(args.tasks_file)
        for task in document["tasks"]:
            mapped = [task.get("behavior")] if task.get("behavior") else \
                [item.get("behavior") for item in task.get("behaviors") or []
                 if isinstance(item, dict)]
            print("%-4s %-8s %-16s %-28s %s"
                  % (task.get("id"), str(task.get("mode") or "evidence"),
                     str(task.get("feature")), ",".join(str(item) for item in mapped),
                     "holdout" if task.get("holdout") else ""))
        return 0

    try:
        report = run(args)
    except SystemExit:
        raise
    except Exception as exc:                                     # noqa: BLE001
        print("ERROR: evidence evaluation failed: %s" % exc, file=sys.stderr)
        return 3

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_summary(report)

    statuses = [item.get("evaluation_status") for item in report["tasks"]]
    if report["structural_problems"] or any(
            status in (adapter.VERIFIED_FAIL, adapter.INVALID_EVIDENCE, adapter.EVALUATION_ERROR)
            for status in statuses):
        return 1
    if any(status != adapter.VERIFIED_PASS for status in statuses):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
