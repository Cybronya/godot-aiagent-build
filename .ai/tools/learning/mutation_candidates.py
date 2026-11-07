#!/usr/bin/env python3
"""Knowledge-Driven Mutation Candidates（Phase 1.66）。

从**已审批知识**（源码守卫/状态/失败）推导受控缺陷候选，再交给 1.59 的现有 harness
在隔离副本里执行 Control / Mutation / Recovery。本模块不自己改源码、不自己判定检出：

    mutation_candidate_id
    feature_id / behavior_id / target_symbol / mutation_operator
    knowledge_refs / expected_failure / safety_constraints / execution_requirements
    approval_status

判定语义严格沿用 harness：只有 `MUTANT_KILLED` 是有效检出；`INVALID_MUTANT` /
`SURVIVED` / `ERROR` / `TIMEOUT` / `NOT_RUN` 都不算。

用法：
    python .ai/tools/learning/mutation_candidates.py --generate
    python .ai/tools/learning/mutation_candidates.py --execute <candidate_id>
退出码：0 生成成功 / 执行且 KILLED；1 执行但非 KILLED；2 输入或环境错误。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
for _p in (_HERE, _TOOLS, os.path.join(_TOOLS, "scene_composer"),
           os.path.join(_TOOLS, "evaluation"), os.path.join(_TOOLS, "evaluation", "mutation"),
           os.path.join(_TOOLS, "validator", "execution")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths                                    # noqa: E402
import knowledge_v2 as kv                       # noqa: E402
import feature_behavior_evidence as fbe         # noqa: E402
import env_paths                                # noqa: E402

OUT_PATH = os.path.join(paths.LEARNING_STATE, "mutation_candidates.json")
EXEC_DIR = os.path.join(paths.PROJECT_ROOT if hasattr(paths, "PROJECT_ROOT") else paths.ROOT,
                        ".ai", "tmp", "p166", "mutations")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load(path: str, default):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _dump(path: str, document) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _relative(path: str) -> str:
    """引用路径优先相对项目根；跨盘符（测试临时目录）时退回绝对路径。"""
    try:
        return os.path.relpath(path, paths.ROOT).replace(os.sep, "/")
    except ValueError:
        return os.path.abspath(path).replace(os.sep, "/")


def _sha(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _catalog_entries() -> list[dict]:
    try:
        import catalog                          # noqa: PLC0415
        return catalog.load()
    except Exception:                           # noqa: BLE001 - 目录不可读即无法去重
        return []


def _line_text(path: str, line: int) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return ""
    return lines[line - 1] if 0 < line <= len(lines) else ""


def _contract_checks(feature_id: str, behavior_id: str) -> list[dict]:
    contracts, _reports = fbe.build_contracts(feature_id, "Features")
    contract = next((item for item in contracts
                     if str(item["behavior"]) == behavior_id), {})
    return list(contract.get("expected") or [])


def _candidate_for(record: dict, condition: dict, catalog_entries: list[dict]) -> dict | None:
    file_part = str(condition.get("file") or "")
    line = int(condition.get("line") or 0)
    if not file_part.startswith("Features/") or line <= 0:
        return None
    path = os.path.join(paths.ROOT, file_part.replace("/", os.sep))
    if not os.path.isfile(path):
        return None
    text = _line_text(path, line)
    if not text.strip().startswith("if ") or not text.rstrip().endswith(":"):
        return None
    anchor = text
    indentation = text[:len(text) - len(text.lstrip("\t"))]
    replacement = "%sif false:\n" % indentation
    candidate_id = "mc-" + hashlib.sha256(
        ("%s|%s|%s|%s" % (record["feature_id"], record["behavior_id"], file_part,
                          anchor)).encode("utf-8")).hexdigest()[:16]
    existing = next((entry for entry in catalog_entries
                     if str(entry.get("target_file")) == file_part
                     and str(entry.get("anchor")) == anchor), None)
    checks = _contract_checks(record["feature_id"], record["behavior_id"])
    signals = [check for check in checks if check.get("check") == "signal"]
    candidate = {
        "schema": "knowledge_mutation_candidate",
        "schema_version": 1,
        "mutation_candidate_id": candidate_id,
        "feature_id": record["feature_id"],
        "behavior_id": record["behavior_id"],
        "behavior": "%s/%s" % (record["feature_id"], record["behavior_id"]),
        "target_symbol": str(condition.get("function") or ""),
        "target_file": file_part,
        "target_line": line,
        "mutation_operator": "replace_exact",
        "anchor": anchor,
        "replacement": replacement,
        "knowledge_refs": [record["knowledge_id"]],
        "condition": str(condition.get("condition") or ""),
        "expected_failure": ("禁用守卫 `%s` 后，契约期望的终态/信号计数不再成立：%s"
                             % (condition.get("condition"),
                                ", ".join(sorted({str(check.get("check")) for check in checks})))),
        "expected_observations": checks,
        "safety_constraints": [
            "只在 harness 创建的 Features 副本里修改（require_inside 校验）",
            "执行前核对 source_sha256；锚点必须恰好出现一次",
            "Control / Mutation / Recovery 三段真实执行",
            "Recovery 逐字节恢复校验 + repo_guard 检查仓库未被修改",
        ],
        "execution_requirements": ["真实 Godot", "mutation harness（1.59）",
                                   "evaluation.expect 与契约一致"],
        "approval_status": "EXISTING_CATALOG" if existing else "PENDING_APPROVAL",
        "existing_mutation_id": (existing or {}).get("mutation_id", ""),
        "signal_checks": signals,
        "generated_at": _now(),
        "execution": {},
    }
    return candidate


def _validate_anchor(candidate: dict) -> dict:
    """只读校验：锚点唯一、operator 可应用、结构未破坏（不写任何文件）。"""
    import operators                            # noqa: PLC0415
    path = os.path.join(paths.ROOT, candidate["target_file"].replace("/", os.sep))
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        operators.apply_operator(candidate["mutation_operator"], text,
                                 candidate["anchor"], candidate["replacement"])
    except (OSError, operators.OperatorError) as error:
        return {"status": "INVALID", "reason": str(error)}
    return {"status": "VALID", "reason": "anchor unique; operator applied on a copy"}


def generate() -> dict:
    catalog_entries = _catalog_entries()
    candidates = []
    seen = set()
    for record in kv.all_records():
        if record["verification_status"] != "APPROVED":
            continue
        if record["knowledge_type"] != "SOURCE_OBSERVATION" or record["key"] != "guards":
            continue
        for condition in (record["content"] or {}).get("conditions") or []:
            candidate = _candidate_for(record, condition, catalog_entries)
            if candidate is None:
                continue
            if candidate["mutation_candidate_id"] in seen:
                continue
            seen.add(candidate["mutation_candidate_id"])
            candidates.append(candidate)
    verdicts = {}
    for record in kv.all_records():
        if record["knowledge_type"] == "MUTATION_OBSERVATION" and \
                record["verification_status"] == "APPROVED":
            verdicts[(record["feature_id"], record["behavior_id"])] = \
                (record.get("mutation_verdict") or "MUTANT_KILLED", record["knowledge_id"])
    for candidate in candidates:
        candidate["anchor_validation"] = _validate_anchor(candidate)
        verdict = verdicts.get((candidate["feature_id"], candidate["behavior_id"]))
        candidate["existing_verdict"] = ({"verdict": verdict[0], "knowledge_id": verdict[1]}
                                         if verdict else {})
    document = {"schema": "knowledge_mutation_candidates", "schema_version": 1,
                "generated_at": _now(),
                "note": "候选不是检出；只有 harness 的 MUTANT_KILLED 才算有效缺陷知识",
                "summary": {"candidates": len(candidates),
                            "existing_catalog": sum(1 for item in candidates
                                                    if item["approval_status"] == "EXISTING_CATALOG"),
                            "pending": sum(1 for item in candidates
                                           if item["approval_status"] == "PENDING_APPROVAL")},
                "candidates": candidates}
    _dump(OUT_PATH, document)
    return document


def _build_entry(candidate: dict) -> dict:
    """候选 → harness entry。effectiveness 只在该 Behavior 的契约本身重复动作时可推导。"""
    contracts, _reports = fbe.build_contracts(candidate["feature_id"], "Features")
    contract = next((item for item in contracts
                     if str(item["behavior"]) == candidate["behavior_id"]), {})
    actions = contract.get("actions") or []
    overlap = [action for action in actions if action.get("type") == "physics.overlap"]
    signals = [check for check in contract.get("expected") or []
               if check.get("check") == "signal"]
    if not overlap or not signals:
        raise SystemExit("candidate is not executable generically: contract has no repeated "
                         "contact action or no signal expectation")
    check = signals[0]
    return {
        "mutation_id": "MC-%s" % candidate["mutation_candidate_id"].replace("mc-", "").upper(),
        "feature_id": candidate["feature_id"],
        "behavior_id": candidate["behavior_id"],
        "mutation_type": "state_guard_condition_disabled",
        "target_file": candidate["target_file"],
        "target_function": candidate["target_symbol"],
        "operator": candidate["mutation_operator"],
        "source_sha256": _sha(os.path.join(paths.ROOT,
                                           candidate["target_file"].replace("/", os.sep))),
        "anchor": candidate["anchor"],
        "replacement": candidate["replacement"],
        "precondition": "只禁用该守卫，不改其他语句",
        "expected_behavior_change": candidate["expected_failure"],
        "risk_level": "high",
        "status": "active",
        "effectiveness": {"check": "signal", "target": check.get("target", "."),
                          "entry": check.get("entry", ""),
                          "baseline": {"count": int(check.get("count") or 1)},
                          "mutant": {"count": int(check.get("count") or 1) + 1}},
        "evaluation": {"expect": contract.get("expected") or []},
    }


def execute(candidate_id: str) -> dict:
    document = _load(OUT_PATH, {})
    candidate = next((item for item in document.get("candidates") or []
                      if item["mutation_candidate_id"] == candidate_id), None)
    if candidate is None:
        raise SystemExit("candidate not found: %s" % candidate_id)
    import harness                              # noqa: PLC0415
    entry = _build_entry(candidate)
    # Run ID 必须唯一：同名 run 目录已存在时 harness 会拒绝创建（重复 Run 攻击）。
    run_tag = time.strftime("%H%M%S", time.gmtime())
    options = {"run_id": "p166-%s-%s" % (candidate_id.replace("mc-", ""), run_tag),
               "runs_root": os.path.join(EXEC_DIR, "runs"),
               "replay": 2, "timeout": 240,
               "godot": env_paths.require_godot(paths.ROOT)}
    report = harness.run_mutation(entry, options)
    _dump(os.path.join(EXEC_DIR, "%s.json" % candidate_id), report)
    recovery = report.get("recovery") or {}
    candidate["execution"] = {
        "verdict": report.get("verdict"), "verdict_reason": report.get("verdict_reason"),
        "run_id": report.get("run_id"),
        "repo_guard": report.get("repo_guard"),
        "restored_byte_for_byte": recovery.get("restored_byte_for_byte"),
        "recovery_verified": recovery.get("verified"),
        "control_observation": (report.get("effectiveness") or {}).get("control_observation"),
        "mutant_observation": (report.get("effectiveness") or {}).get("mutant_observation"),
        "report": _relative(os.path.join(EXEC_DIR, "%s.json" % candidate_id)),
        "executed_at": _now(),
    }
    candidate["approval_status"] = "EXECUTED"
    document["summary"]["executed"] = sum(1 for item in document["candidates"]
                                          if item.get("execution"))
    _dump(OUT_PATH, document)
    # 只有 KILLED 能变成知识；仍然只是 PENDING_REVIEW，不自动批准。
    if report.get("verdict") == "MUTANT_KILLED":
        report_path = os.path.join(EXEC_DIR, "%s.json" % candidate_id)
        record = kv.make_record(
            feature_id=candidate["feature_id"], behavior_id=candidate["behavior_id"],
            knowledge_type="MUTATION_OBSERVATION",
            key="mutation_candidate:%s" % candidate_id,
            content={"mutation_id": entry["mutation_id"],
                     "mutation_type": entry["mutation_type"],
                     "mutation_candidate_id": candidate_id,
                     "condition": candidate["condition"],
                     "control": (report.get("effectiveness") or {}).get("control_observation"),
                     "mutant": (report.get("effectiveness") or {}).get("mutant_observation"),
                     "restored_byte_for_byte": recovery.get("restored_byte_for_byte"),
                     "run_id": report.get("run_id")},
            source_references=[{"kind": "MUTATION_REFERENCE",
                                "reference": _relative(report_path),
                                "digest": _sha(report_path)}],
            contract_version=paths.contract_version(candidate["feature_id"],
                                                    candidate["behavior_id"]),
            confidence="VERIFIED", run_id=str(report.get("run_id") or ""),
            mutation_verdict="MUTANT_KILLED",
            reason="knowledge-driven mutation candidate killed by the existing harness")
        candidate["knowledge_id"] = kv.add_candidate(record)["knowledge_id"]
        _dump(OUT_PATH, document)
    return candidate


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--execute", default="")
    args = parser.parse_args(argv)
    if args.execute:
        candidate = execute(args.execute)
        print(json.dumps(candidate["execution"], ensure_ascii=False)[:600])
        return 0 if candidate["execution"].get("verdict") == "MUTANT_KILLED" else 1
    document = generate()
    print(json.dumps(document["summary"], ensure_ascii=False))
    for item in document["candidates"]:
        print("%s %s %s %s -> %s" % (item["mutation_candidate_id"], item["behavior"],
                                      item["target_symbol"], item["condition"][:40],
                                      item["approval_status"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
