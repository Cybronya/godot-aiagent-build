#!/usr/bin/env python3
"""Golden Trace Baseline approval flow（Phase 1.23）

黄金基线的更新必须是**显式、可审查**的两步操作：

    1. 生成候选（只写候选文件，绝不覆盖正式基线）：
       python .ai/tools/e2e/approve_trace_baselines.py candidate \
           --scenario multi_stage_boss --out <候选目录>

    2. 审查候选（逐事件表 + 与现有基线的差异）：
       python .ai/tools/e2e/approve_trace_baselines.py review --candidate <候选目录>

    3. 显式批准（把通过校验的候选提升为正式基线，并记录批准人 / 理由）：
       python .ai/tools/e2e/approve_trace_baselines.py apply \
           --candidate <候选目录> --approver <name> --note "<理由>" --i-approve

约束：
  - 候选只来自**真实 Godot 运行**（沙箱内完整生成链路 + 探针），不读取手写 trace；
  - 候选在生成时已通过 trace schema 校验与回放，apply 会再校验一次；
  - 正式基线只能通过本工具显式写入；测试 / 比较器永远不会写基线；
  - apply 会先打印「现有基线 → 候选」的逐事件差异，再写入，版本号 +1；
  - 旧基线不兼容时不会静默重写：先由 reviewer 判断是否需要新 coverage / 迁移。

退出码：0 = 成功；1 = 校验 / 生成失败；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

_DOTAI = Path(__file__).resolve().parents[2]              # <project>/.ai
PROJECT_ROOT = _DOTAI.parent
TOOLS = _DOTAI / "tools"
for _path in (str(TOOLS / "e2e"), str(TOOLS / "validator")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import trace_baseline_capture                                # noqa: E402
import trace_baselines                                       # noqa: E402

APPROVED_BEHAVIOR_VERSION = "phase-1.22-orchestration-trace-contract-v1"


def _today() -> str:
    return datetime.date.today().isoformat()


def candidate_path(candidate_dir, scenario_id: str) -> Path:
    return Path(candidate_dir) / ("%s.candidate.json" % scenario_id)


def normalized_fingerprint(document: dict) -> str:
    """规范化指纹：忽略 run_id / timestamp_ms（显式动态字段），其余逐事件保序。

    payload 只含 trace schema 版本 + 事件流 —— **不含 scenario_id**：
    基线文档与真实 trace 文档的形状不同（trace 无 scenario_id 字段），
    指纹必须在「已批准基线」与「仅动态字段不同的真实 trace」之间可比较；
    scenario_id 的匹配由比较器/批准流程单独校验，不属于事件流指纹。
    """
    events = []
    for event in document.get("events") or []:
        events.append({key: value for key, value in event.items()
                       if key not in ("run_id", "timestamp_ms")})
    payload = {
        "trace_schema_version": (document.get("trace_schema_version")
                                 or document.get("schema_version")),
        "events": events,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def _write_json(path: Path, document: dict) -> None:
    """原子写入：先写同目录临时文件，再 os.replace（失败不留半写入正式文件）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def verify_candidate_fingerprint(document: dict) -> list:
    """重算候选内容指纹并与候选自带的记录指纹比对（Phase 1.24，任务 B）。

    指纹输入 = trace schema 版本 + 全部事件（仅归一化 run_id / timestamp_ms，
    见 normalized_fingerprint）——涵盖所有影响比较语义的字段，且对基线文档与
    真实 trace 文档同样可计算。返回错误列表（空 = 一致）。
    """
    errors: list = []
    approval = document.get("approval") or {}
    recorded = approval.get("candidate_fingerprint")
    if not isinstance(recorded, str) or not recorded.strip():
        errors.append("candidate has no recorded approval.candidate_fingerprint; "
                      "regenerate the candidate with this tool")
        return errors
    recomputed = normalized_fingerprint(document)
    if recomputed != recorded:
        errors.append("candidate content does not match its recorded fingerprint "
                      "(recorded %s..., recomputed %s...); the file changed after "
                      "generation — regenerate and re-review"
                      % (recorded[:16], recomputed[:16]))
    return errors


def _event_table(document: dict) -> list:
    lines = []
    for event in document.get("events") or []:
        lines.append("    %2s %-24s stage=%s@%s reason=%s entity=%s/%s data=%s"
                     % (event.get("sequence"), event.get("event_type"),
                        event.get("stage_id"), event.get("stage_index"),
                        event.get("reason"), event.get("entity_id"),
                        event.get("instance_name"),
                        json.dumps(event.get("data"), ensure_ascii=False, sort_keys=True)))
    return lines


def _validate_candidate(document: dict) -> list:
    """候选必须：来自真实 trace、schema 合法、可回放。"""
    errors: list = []
    if document.get("document") != trace_baselines.BASELINE_DOCUMENT:
        errors.append("candidate is not a %r document" % trace_baselines.BASELINE_DOCUMENT)
    approval = document.get("approval") or {}
    if approval.get("status") != "candidate":
        errors.append("candidate approval.status must be 'candidate' (got %r)"
                      % (approval.get("status"),))
    if not document.get("source", {}).get("captured_by"):
        errors.append("candidate must record how the real trace was captured (source.captured_by)")
    trace_document = {
        "document": trace_baselines.TRACE_DOCUMENT,
        "schema_version": document.get("trace_schema_version"),
        "run_id": "candidate-check",
        "event_count": len(document.get("events") or []),
        "dropped_events": 0,
        "events": document.get("events") or [],
    }
    for event in trace_document["events"]:
        if isinstance(event, dict):
            event["run_id"] = "candidate-check"
    status, trace_errors, _replay = trace_baselines.validate_trace(trace_document)
    if status is not None:
        errors.append("candidate events are not a valid replayable trace (%s): %s"
                      % (status, json.dumps(trace_errors[:3], ensure_ascii=False)))
    if errors:
        return errors
    # 完整基线契约（除 approval.status 之外的字段）必须已满足：用 approved 副本校验。
    probe = json.loads(json.dumps(document))
    probe["approval"]["status"] = "approved"
    probe["approval"].setdefault("approver", "candidate-check")
    probe["approval"].setdefault("approved_at", _today())
    return trace_baselines.validate_baseline(probe)


def build_candidate(scenario_id: str, *, note: str = "", approver: str = "",
                    godot=None, keep_sandbox: bool = False) -> dict:
    """真实采集 → 候选基线文档（不写正式目录）。"""
    capture = trace_baseline_capture.capture(scenario_id, godot=godot,
                                             keep_sandbox=keep_sandbox)
    if not capture.ok:
        raise RuntimeError("real trace capture failed: %s" % capture.error)
    evidence = dict(capture.evidence)
    evidence["captured_by"] = ("trace_baseline_capture.py (sandboxed real Godot headless E2E)")
    approval = {
        "status": "candidate",
        "candidate_generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "candidate_note": note,
        "proposed_approver": approver,
        "candidate_fingerprint": "",
    }
    document = trace_baselines.build_baseline(
        capture.trace_document,
        scenario_id=scenario_id,
        scenario_description=evidence.get("description", ""),
        approved_behavior_version=APPROVED_BEHAVIOR_VERSION,
        approval=approval,
        source=evidence,
        coverage=evidence.get("coverage") or [],
    )
    document["approval"]["candidate_fingerprint"] = normalized_fingerprint(document)
    document["source"]["trace_run_id"] = capture.trace_document.get("run_id")
    return document


def _load_existing(scenario_id: str, baseline_dir=None):
    path = trace_baselines.baseline_path_for(scenario_id, baseline_dir)
    if not path.is_file():
        return None, path
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except (OSError, ValueError):
        return None, path


def _diff_against_existing(document: dict, existing) -> list:
    if existing is None:
        return ["  (no approved baseline yet: this candidate would create a new baseline)"]
    trace_like = {
        "document": trace_baselines.TRACE_DOCUMENT,
        "schema_version": document.get("trace_schema_version"),
        "run_id": "candidate-diff",
        "event_count": len(document.get("events") or []),
        "dropped_events": 0,
        "events": [dict(event, run_id="candidate-diff")
                   for event in (document.get("events") or [])],
    }
    result = trace_baselines.compare(existing, trace_like,
                                     baseline_path="<approved> -> <candidate>")
    lines = ["  %s" % result["summary"]]
    for difference in (result.get("differences") or [])[:20]:
        lines.append("    [%s] seq=%s %s: approved=%s candidate=%s"
                     % (difference.get("category"), difference.get("sequence"),
                        difference.get("field_path"),
                        json.dumps(difference.get("expected"), ensure_ascii=False),
                        json.dumps(difference.get("actual"), ensure_ascii=False)))
    return lines


def command_candidate(args) -> int:
    try:
        document = build_candidate(args.scenario, note=args.note,
                                   approver=args.approver,
                                   keep_sandbox=args.keep_sandbox)
    except (RuntimeError, trace_baselines.BaselineError) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1
    errors = _validate_candidate(document)
    target = candidate_path(args.out, args.scenario)
    if errors:
        print("FAIL: candidate did not pass validation; nothing written:", file=sys.stderr)
        for error in errors:
            print("  - %s" % error, file=sys.stderr)
        return 1
    _write_json(target, document)
    print("Candidate: %s" % target)
    print("  scenario=%s events=%d fingerprint=%s"
          % (args.scenario, len(document["events"]),
             document["approval"]["candidate_fingerprint"][:16]))
    print("  It was NOT approved: run `review`, then `apply --i-approve` explicitly.")
    return 0


def command_review(args) -> int:
    target = candidate_path(args.candidate, args.scenario) if args.scenario else \
        Path(args.candidate)
    if target.is_dir():
        candidates = sorted(target.glob("*.candidate.json"))
        if len(candidates) != 1:
            print("FAIL: candidate directory holds %d candidate file(s); pass --scenario"
                  % len(candidates), file=sys.stderr)
            return 2
        target = candidates[0]
    if not target.is_file():
        print("FAIL: candidate not found: %s" % target, file=sys.stderr)
        return 2
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("FAIL: cannot read candidate %s: %s" % (target, exc), file=sys.stderr)
        return 2
    errors = _validate_candidate(document)
    # Phase 1.24（任务 B1）：review 必须从**实际文件内容**重算指纹，不能信任
    # 候选元数据自带的指纹——审查后文件被修改时这里必须拒绝。
    errors.extend(verify_candidate_fingerprint(document))
    print("Candidate review: %s" % target)
    print("  scenario=%s events=%d"
          % (document.get("scenario_id"), len(document.get("events") or [])))
    print("  fingerprint=%s" % document.get("approval", {}).get("candidate_fingerprint"))
    print("  approved_behavior_version=%s" % document.get("approved_behavior_version"))
    print("  source: godot=%s probe=%s level=%s"
          % (document.get("source", {}).get("godot_version"),
             document.get("source", {}).get("probe"),
             document.get("source", {}).get("level_config")))
    print("  events:")
    for line in _event_table(document):
        print(line)
    existing, path = _load_existing(document.get("scenario_id") or args.scenario,
                                    args.baseline_dir or None)
    print("  vs approved baseline %s:" % path)
    for line in _diff_against_existing(document, existing):
        print(line)
    if errors:
        print("FAIL: candidate is not approvable (%d error(s)):" % len(errors), file=sys.stderr)
        for error in errors:
            print("  - %s" % error, file=sys.stderr)
        return 1
    print("OK: candidate passed schema + replay validation (approval is still pending)")
    return 0


def command_apply(args) -> int:
    if not args.i_approve:
        print("FAIL: refusing to write an approved baseline without --i-approve",
              file=sys.stderr)
        return 2
    if not args.approver.strip() or not args.note.strip():
        print("FAIL: --approver and --note are required for an explicit approval",
              file=sys.stderr)
        return 2
    target = candidate_path(args.candidate, args.scenario) if args.scenario else \
        Path(args.candidate)
    if target.is_dir():
        candidates = sorted(target.glob("*.candidate.json"))
        if len(candidates) != 1:
            print("FAIL: candidate directory holds %d candidate file(s); pass --scenario"
                  % len(candidates), file=sys.stderr)
            return 2
        target = candidates[0]
    if not target.is_file():
        print("FAIL: candidate not found: %s" % target, file=sys.stderr)
        return 2
    document = json.loads(target.read_text(encoding="utf-8"))
    errors = _validate_candidate(document)
    # Phase 1.24（任务 B2）：apply 前再次重算指纹——review 之后候选被修改 /
    # 替换时拒绝写入，正式基线保持字节不变，不留半写入文件。
    fingerprint_errors = verify_candidate_fingerprint(document)
    if fingerprint_errors:
        print("FAIL: candidate fingerprint check failed; the approved baseline is "
              "untouched:", file=sys.stderr)
        for error in fingerprint_errors:
            print("  - %s" % error, file=sys.stderr)
        return 1
    if errors:
        print("FAIL: candidate is not approvable; the approved baseline is untouched:",
              file=sys.stderr)
        for error in errors:
            print("  - %s" % error, file=sys.stderr)
        return 1
    scenario_id = document["scenario_id"]
    existing, path = _load_existing(scenario_id, args.baseline_dir or None)
    if existing is not None:
        existing_errors = trace_baselines.validate_baseline(existing)
        if existing_errors:
            print("FAIL: the currently approved baseline is itself invalid; refusing to "
                  "overwrite it silently:\n  - %s" % "\n  - ".join(existing_errors),
                  file=sys.stderr)
            return 1

    print("Approval diff (approved -> candidate):")
    for line in _diff_against_existing(document, existing):
        print(line)

    approved = json.loads(json.dumps(document))
    approved["baseline_version"] = int((existing or {}).get("baseline_version") or 0) + 1
    approved["approval"] = {
        "status": "approved",
        "approver": args.approver.strip(),
        "approved_at": _today(),
        "note": args.note.strip(),
        "candidate_fingerprint": document["approval"]["candidate_fingerprint"],
        "candidate_generated_at": document["approval"].get("candidate_generated_at"),
        "previous_baseline_version": (existing or {}).get("baseline_version"),
    }
    approved_errors = trace_baselines.validate_baseline(approved)
    if approved_errors:
        print("FAIL: rebuilt baseline failed validation; nothing written:", file=sys.stderr)
        for error in approved_errors:
            print("  - %s" % error, file=sys.stderr)
        return 1
    _write_json(path, approved)
    print("Approved: %s (baseline v%d, scenario %s)"
          % (path, approved["baseline_version"], scenario_id))
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Generate, review and explicitly approve golden trace baselines.")
    sub = parser.add_subparsers(dest="command", required=True)

    candidate = sub.add_parser("candidate", help="capture a real trace and write a candidate")
    candidate.add_argument("--scenario", required=True,
                           choices=sorted(trace_baseline_capture.SCENARIOS))
    candidate.add_argument("--out", required=True, help="candidate directory")
    candidate.add_argument("--note", default="", help="why this baseline is being proposed")
    candidate.add_argument("--approver", default="", help="proposed approver")
    candidate.add_argument("--keep-sandbox", action="store_true")
    candidate.set_defaults(func=command_candidate)

    review = sub.add_parser("review", help="show the candidate and its diff vs the baseline")
    review.add_argument("--candidate", required=True,
                        help="candidate file or directory holding *.candidate.json")
    review.add_argument("--scenario", default="", help="required when the directory holds several")
    review.add_argument("--baseline-dir", default="")
    review.set_defaults(func=command_review)

    apply_parser = sub.add_parser("apply", help="explicitly approve a validated candidate")
    apply_parser.add_argument("--candidate", required=True,
                              help="candidate file or directory holding *.candidate.json")
    apply_parser.add_argument("--scenario", default="")
    apply_parser.add_argument("--baseline-dir", default="")
    apply_parser.add_argument("--approver", required=True)
    apply_parser.add_argument("--note", required=True)
    apply_parser.add_argument("--i-approve", action="store_true",
                              help="explicit confirmation to replace the approved baseline")
    apply_parser.set_defaults(func=command_apply)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
