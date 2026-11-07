#!/usr/bin/env python3
"""Scenario Validator（Phase 1.66）。

在执行前独立验证知识驱动场景，阻止错误/无来源/不可执行的测试进入真实执行链。

状态（互斥）：

    VALID              全部检查通过
    INVALID            结构/协议/路径错误（结构性，不重试）
    INCOMPLETE         缺少可验证信息（如依赖引用缺失、期望为空）
    CONTRACT_MISMATCH  目标 Behavior / 契约版本 / 场景与契约不一致
    SOURCE_STALE       源码引用缺失、行号越界或 digest 与当前文件不符
    KNOWLEDGE_STALE    知识 contract_version / implementation_digest 已过期
    ENVIRONMENT_BLOCKED Godot / 探针 / 协议清单不可用

原则：验证失败绝不降低要求；每种失败都给出具体原因（file:line / knowledge_id / 字段名）。

用法：
    python .ai/tools/learning/scenario_validate.py --all
    python .ai/tools/learning/scenario_validate.py --scenario .ai/learning/scenarios/s-xxx.json
退出码：0 至少一个 VALID；1 全部非 VALID；2 输入错误。
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
for _p in (_HERE, _TOOLS, os.path.join(_TOOLS, "scene_composer"),
           os.path.join(_TOOLS, "validator", "execution")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths                                    # noqa: E402
import knowledge_v2 as kv                       # noqa: E402
import dependencies                             # noqa: E402
import feature_behavior_evidence as fbe         # noqa: E402
import behavior_protocol                        # noqa: E402
import env_paths                                # noqa: E402
import scenario_generator                       # noqa: E402

REPORT_DIR = os.path.join(paths.LEARNING_STATE, "validation")
INDEX_PATH = os.path.join(paths.LEARNING_STATE, "scenario_validation.json")

STATUSES = ("VALID", "INVALID", "INCOMPLETE", "CONTRACT_MISMATCH", "SOURCE_STALE",
            "KNOWLEDGE_STALE", "ENVIRONMENT_BLOCKED")

ALLOWED_KNOWLEDGE_TYPES = ("CONTRACT_FACT", "SOURCE_OBSERVATION", "TEST_OBSERVATION",
                           "RUNTIME_OBSERVATION", "MUTATION_OBSERVATION",
                           "FAILURE_KNOWLEDGE", "DEPENDENCY_KNOWLEDGE", "SCENARIO_OBSERVATION",
                           "EXECUTION_OBSERVATION", "BEHAVIOR_OBSERVATION",
                           "TEST_DESIGN_KNOWLEDGE")


def _check(checks: list, name: str, ok: bool, detail: str = "") -> bool:
    checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    return ok


def _file_digest(path: str) -> str | None:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def _inside(base: str, candidate: str) -> bool:
    base_real = os.path.realpath(base)
    candidate_real = os.path.realpath(candidate)
    return candidate_real == base_real or candidate_real.startswith(base_real + os.sep)


def _scene_path(scene: str) -> str:
    if not str(scene).startswith("res://Features/"):
        return ""
    return os.path.join(paths.ROOT, scene[len("res://"):].replace("/", os.sep))


def _contract_checks(scenario: dict, checks: list, reasons: list) -> None:
    feature_id, behavior_id = scenario["feature_id"], scenario["behavior_id"]
    contracts, _reports = fbe.build_contracts(feature_id, "Features")
    contract = next((item for item in contracts if str(item["behavior"]) == behavior_id), None)
    if not _check(checks, "contract.behavior_exists", contract is not None,
                  "%s/%s" % (feature_id, behavior_id)):
        reasons.append("CONTRACT_MISMATCH: contract for %s/%s not found"
                       % (feature_id, behavior_id))
        return
    current = paths.contract_version(feature_id, behavior_id)
    if not _check(checks, "contract.version", scenario.get("contract_version") == current,
                  "scenario=%s current=%s" % (scenario.get("contract_version"), current)):
        reasons.append("CONTRACT_MISMATCH: contract_version %r != current %r"
                       % (scenario.get("contract_version"), current))
    if not _check(checks, "contract.scene", scenario.get("scene") == contract["scene"],
                  "scenario=%s contract=%s" % (scenario.get("scene"), contract["scene"])):
        reasons.append("CONTRACT_MISMATCH: scenario scene differs from contract scene")
    # 复用 1.41 协议的严格校验（动作存在/参数范围/夹具顺序/帧预算/最小证据规则）
    raw = {"id": behavior_id, "scene": contract["scene"],
           "actions": scenario.get("actions") or [],
           "preconditions": scenario.get("preconditions") or [],
           "expected": scenario.get("expected_observations") or [],
           "window_frames": scenario.get("window_frames")}
    errors: list = []
    protocol = behavior_protocol.load_protocol()
    fbe._validate_behavior(raw, 0, contract["scene"], errors, protocol)   # noqa: SLF001
    _check(checks, "contract.protocol", not errors, "; ".join(errors[:3]))
    for error in errors[:4]:
        reasons.append("INVALID: %s" % error)


def _knowledge_checks(scenario: dict, checks: list, reasons: list) -> None:
    feature_id, behavior_id = scenario["feature_id"], scenario["behavior_id"]
    open_conflicts = kv.conflicts("OPEN")
    current_contract = paths.contract_version(feature_id, behavior_id)
    scripts = (scenario_generator._load(                     # noqa: SLF001
        os.path.join(paths.LEARNING_STATE, "source_analysis", feature_id,
                     "%s.json" % behavior_id), {}) or {}).get("scripts") or []
    current_digest = "".join(script.get("digest", "") for script in scripts)
    refs = scenario.get("knowledge_refs") or []
    if not _check(checks, "knowledge.refs_present", bool(refs), "%d refs" % len(refs)):
        reasons.append("INCOMPLETE: scenario has no knowledge_refs")
        return
    for knowledge_id in refs:
        record = kv.get(knowledge_id)
        if record is None:
            _check(checks, "knowledge.exists:%s" % knowledge_id, False, "missing")
            reasons.append("INVALID: knowledge %s not found" % knowledge_id)
            continue
        status = record["verification_status"]
        _check(checks, "knowledge.approved:%s" % knowledge_id,
               status == "APPROVED", status)
        if status != "APPROVED":
            reasons.append("INVALID: knowledge %s is %s (not driveable)" % (knowledge_id, status))
        _check(checks, "knowledge.type:%s" % knowledge_id,
               record["knowledge_type"] in ALLOWED_KNOWLEDGE_TYPES, record["knowledge_type"])
        if record["knowledge_type"] not in ALLOWED_KNOWLEDGE_TYPES:
            reasons.append("INVALID: knowledge %s has type %s"
                           % (knowledge_id, record["knowledge_type"]))
        for conflict in open_conflicts:
            if conflict["feature_id"] != feature_id or conflict["behavior_id"] != behavior_id:
                continue
            if any(party["knowledge_id"] == knowledge_id for party in conflict["parties"]):
                _check(checks, "knowledge.no_conflict:%s" % knowledge_id, False,
                       conflict["conflict_id"])
                reasons.append("KNOWLEDGE_STALE: %s has unresolved conflict %s"
                               % (knowledge_id, conflict["conflict_id"]))
        stale = kv.staleness(record, current_contract_version=current_contract,
                             current_implementation_digest=current_digest
                             if record.get("implementation_digest") else "")
        _check(checks, "knowledge.fresh:%s" % knowledge_id, not stale, "; ".join(stale))
        for reason in stale:
            reasons.append("KNOWLEDGE_STALE: %s: %s" % (knowledge_id, reason))


def _source_checks(scenario: dict, checks: list, reasons: list) -> None:
    records = [kv.get(knowledge_id) for knowledge_id in scenario.get("knowledge_refs") or []]
    references = []
    for record in records:
        if not record:
            continue
        for reference in record.get("source_references") or []:
            if reference.get("kind") != "SOURCE_REFERENCE":
                continue
            references.append((record["knowledge_id"], reference))
    if not _check(checks, "source.references_present", bool(references),
                  "%d source refs" % len(references)):
        reasons.append("INCOMPLETE: no SOURCE_REFERENCE behind scenario")
    for knowledge_id, reference in references:
        raw = str(reference.get("reference") or "")
        file_part, _, _marker = raw.partition("#")
        if file_part.startswith("analysis:"):
            # 依赖知识允许引用分析产物（analysis:<feature>/<behavior>#...），不是源码文件
            key = file_part[len("analysis:"):]
            feature_id, _, behavior_id = key.partition("/")
            analysis_path = os.path.join(paths.LEARNING_STATE, "source_analysis",
                                         feature_id, "%s.json" % behavior_id)
            if not _check(checks, "source.analysis:%s" % knowledge_id,
                          os.path.isfile(analysis_path), key):
                reasons.append("SOURCE_STALE: analysis reference missing for %s" % key)
            continue
        path_part, _, line_part = file_part.partition(":")
        if not path_part.startswith("Features/"):
            _check(checks, "source.path_scope:%s" % knowledge_id, False, path_part)
            reasons.append("INVALID: source reference outside Features/: %s" % path_part)
            continue
        path = os.path.join(paths.ROOT, path_part.replace("/", os.sep))
        if not _check(checks, "source.exists:%s" % knowledge_id, os.path.isfile(path), path_part):
            reasons.append("SOURCE_STALE: %s missing (%s)" % (knowledge_id, path_part))
            continue
        if not _check(checks, "source.inside_features:%s" % knowledge_id,
                      _inside(paths.FEATURES_DIR, path), path_part):
            reasons.append("INVALID: source outside Features/ (%s)" % path_part)
        digest = _file_digest(path)
        expected = reference.get("digest")
        if expected:
            if not _check(checks, "source.digest:%s" % knowledge_id,
                          bool(digest) and digest == expected,
                          "expected=%s" % str(expected)[:12]):
                reasons.append("SOURCE_STALE: digest mismatch for %s" % path_part)
        if line_part.isdigit():
            with open(path, encoding="utf-8", errors="replace") as handle:
                total = sum(1 for _ in handle)
            if not _check(checks, "source.line:%s" % knowledge_id,
                          int(line_part) <= total, "%s:%s (file %d lines)"
                          % (path_part, line_part, total)):
                reasons.append("SOURCE_STALE: line %s out of range in %s"
                               % (line_part, path_part))


def _dependency_checks(scenario: dict, checks: list, reasons: list) -> None:
    graph = dependencies.load()
    edge_ids = {edge["id"] for edge in graph.get("edges") or []}
    refs = scenario.get("dependency_refs") or []
    if scenario.get("scenario_type") == "DEPENDENCY_PRECONDITION" and not refs:
        _check(checks, "dependency.refs", False, "dependency scenario without edge ref")
        reasons.append("INCOMPLETE: dependency scenario lacks dependency_refs")
        return
    for edge_id in refs:
        ok = edge_id in edge_ids
        _check(checks, "dependency.edge:%s" % edge_id, ok, "")
        if not ok:
            reasons.append("INVALID: dependency edge %s not in graph" % edge_id)


def _feasibility_checks(scenario: dict, checks: list, reasons: list) -> None:
    scene = str(scenario.get("scene") or "")
    path = _scene_path(scene)
    ok = bool(path) and os.path.isfile(path) and _inside(paths.FEATURES_DIR, path)
    _check(checks, "feasibility.scene", ok, scene)
    if not ok:
        reasons.append("RESOURCE/INVALID: scene not resolvable inside Features: %s" % scene)
    actions = scenario.get("actions") or []
    _check(checks, "feasibility.actions", bool(actions), "%d actions" % len(actions))
    if not actions:
        reasons.append("INVALID: scenario has no actions")
    expected = scenario.get("expected_observations") or []
    _check(checks, "feasibility.expected", bool(expected), "%d checks" % len(expected))
    if not expected:
        reasons.append("INVALID: scenario has no verifiable expectation")
    _check(checks, "feasibility.cleanup", bool(scenario.get("cleanup")), "")


def _environment_checks(scenario: dict, checks: list, reasons: list) -> None:
    binary = env_paths.find_godot_binary()
    _check(checks, "environment.godot", bool(binary), str(binary)[:120])
    if not binary:
        reasons.append("ENVIRONMENT_BLOCKED: Godot executable not found")
    probe = os.path.join(paths.TOOLS_DIR, "scene_composer", "probes",
                         "feature_behavior_probe.gd")
    _check(checks, "environment.probe", os.path.isfile(probe), "")
    if not os.path.isfile(probe):
        reasons.append("ENVIRONMENT_BLOCKED: behavior probe missing")
    try:
        protocol = behavior_protocol.load_protocol()
        drift = behavior_protocol.check_manifest(protocol)
        _check(checks, "environment.protocol", not drift, "; ".join(drift[:2]))
        if drift:
            reasons.append("ENVIRONMENT_BLOCKED: protocol manifest drift: %s" % drift[0])
    except behavior_protocol.ProtocolError as error:
        _check(checks, "environment.protocol", False, str(error))
        reasons.append("ENVIRONMENT_BLOCKED: protocol invalid: %s" % error)


def _status(checks: list, reasons: list) -> str:
    text = " | ".join(reasons)
    if "CONTRACT_MISMATCH" in text:
        return "CONTRACT_MISMATCH"
    if "INVALID" in text:
        return "INVALID"
    if "SOURCE_STALE" in text:
        return "SOURCE_STALE"
    if "KNOWLEDGE_STALE" in text:
        return "KNOWLEDGE_STALE"
    if "ENVIRONMENT_BLOCKED" in text:
        return "ENVIRONMENT_BLOCKED"
    if "INCOMPLETE" in text:
        return "INCOMPLETE"
    return "VALID" if all(item["ok"] for item in checks) else "INVALID"


def validate(scenario: dict) -> dict:
    checks: list = []
    reasons: list = []
    # knowledge_refs 缺失属于「来源不完整」（INCOMPLETE），不是结构非法（INVALID）。
    for field in ("scenario_id", "feature_id", "behavior_id", "scenario_type", "scene",
                  "actions", "expected_observations", "contract_version"):
        if not scenario.get(field):
            _check(checks, "schema.%s" % field, False, "missing")
            reasons.append("INVALID: missing field %s" % field)
    if reasons:
        return {"scenario_id": scenario.get("scenario_id", ""), "status": "INVALID",
                "checks": checks, "reasons": reasons}
    _contract_checks(scenario, checks, reasons)
    _knowledge_checks(scenario, checks, reasons)
    _source_checks(scenario, checks, reasons)
    _dependency_checks(scenario, checks, reasons)
    _feasibility_checks(scenario, checks, reasons)
    _environment_checks(scenario, checks, reasons)
    return {"scenario_id": scenario["scenario_id"], "status": _status(checks, reasons),
            "checks": checks, "reasons": reasons}


def _dump(path: str, document) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--write", action="store_true", help="写 validation 报告并回写场景状态")
    args = parser.parse_args(argv)

    paths_in = list(args.scenario)
    if args.all or not paths_in:
        paths_in = sorted(glob.glob(os.path.join(scenario_generator.SCENARIO_DIR, "s-*.json")))
    if not paths_in:
        print("no scenarios found", file=sys.stderr)
        return 2

    reports = []
    valid = 0
    for path in paths_in:
        with open(path, encoding="utf-8") as handle:
            scenario = json.load(handle)
        report = validate(scenario)
        report["scenario_path"] = os.path.relpath(path, paths.ROOT).replace(os.sep, "/")
        reports.append(report)
        if report["status"] == "VALID":
            valid += 1
        if args.write:
            scenario["validation_status"] = report["status"]
            scenario["validated_at"] = report.get("validated_at", "")
            _dump(path, scenario)
            _dump(os.path.join(REPORT_DIR, "%s.json" % report["scenario_id"]),
                  {"scenario_id": report["scenario_id"], "status": report["status"],
                   "checks": report["checks"], "reasons": report["reasons"]})
        print("%s %s %s" % ("PASS" if report["status"] == "VALID" else "FAIL",
                            report["scenario_id"], report["status"]))
        for reason in report["reasons"][:4]:
            print("  - %s" % reason)
    if args.write:
        _dump(INDEX_PATH, {"schema": "scenario_validation_index", "schema_version": 1,
                           "summary": {"total": len(reports), "valid": valid},
                           "reports": reports})
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
