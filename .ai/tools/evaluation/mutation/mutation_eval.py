#!/usr/bin/env python3
"""Mutation Evaluation Runner —— L5 受控缺陷检测入口（Phase 1.59）。

回答的问题是：**当 Feature 的真实实现里出现一个已知缺陷时，现有验证链路能不能发现它。**

它不重新实现任何东西：

    Mutation Harness  -> 只负责隔离副本、锚点替换、控制组编排、Verdict
    采集器             -> scene_composer/feature_behavior_evidence.py（真实 Godot）
    Validator/Evaluation -> evaluation/evidence_eval.py（Phase 1.58 链路）

用法：
    python .ai/tools/evaluation/mutation/mutation_eval.py --list
    python .ai/tools/evaluation/mutation/mutation_eval.py --all
    python .ai/tools/evaluation/mutation/mutation_eval.py --mutation M01-health-damage-state-update-omitted
    python .ai/tools/evaluation/mutation/mutation_eval.py --all --json
    python .ai/tools/evaluation/mutation/mutation_eval.py --all --clean     # 删除本次 run 目录

退出码：
    0 = 每条被选 mutation 都是 MUTANT_KILLED（且 control / recovery 均通过）
    1 = 存在 MUTANT_SURVIVED / INVALID_MUTANT / HARNESS_ERROR / TIMEOUT
    2 = 存在 NOT_RUN（前置条件不满足：catalog 过期、Feature/Behavior 不在支持集等）
    3 = 输入错误（catalog 不可用、未知 mutation id、环境缺失）

注意：`MUTANT_KILLED` 是**验证系统成功发现缺陷**，不是行为验收通过。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_EVALUATION = os.path.dirname(_HERE)
_TOOLS = os.path.dirname(_EVALUATION)
PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))

for _path in (_HERE, _EVALUATION):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import catalog                                                     # noqa: E402
import harness                                                     # noqa: E402
import workspace                                                   # noqa: E402

DEFAULT_REPORT_DIR = os.path.join(PROJECT_ROOT, ".ai", "tmp", "p159", "reports")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def print_list(entries) -> None:
    for entry in entries:
        print("%-44s %-18s %-28s %-22s %s"
              % (entry["mutation_id"], entry["feature_id"], entry["behavior_id"],
                 entry["mutation_type"], entry.get("risk_level") or "-"))


def print_summary(reports, summary: dict, report_paths: list) -> None:
    print("\n%-44s %-16s %-18s %-20s %s"
          % ("mutation", "verdict", "evaluation", "validator", "reason"))
    for report in reports:
        mutant = ((report.get("controls") or {}).get("mutant") or {}).get("evaluation") or {}
        print("%-44s %-16s %-18s %-20s %s"
              % (report.get("mutation_id"), report.get("verdict"),
                 mutant.get("evaluation_status") or "-",
                 mutant.get("validator_status") or "-",
                 (report.get("verdict_reason") or "")[:70]))
    print("")
    print("mutations: total=%d effective=%d killed=%d survived=%d invalid=%d error=%d "
          "timeout=%d not_run=%d"
          % (summary["total"], summary["effective_mutations"], summary["killed"],
             summary["survived"], summary["invalid"], summary["harness_error"],
             summary["timeout"], summary["not_run"]))
    for report in reports:
        control = ((report.get("controls") or {}).get("control") or {}).get("evaluation") or {}
        recovery = (report.get("recovery") or {}).get("evaluation") or {}
        print("  %-44s control=%-14s recovery=%-14s effective=%s"
              % (report.get("mutation_id"), control.get("evaluation_status") or "-",
                 recovery.get("evaluation_status") or "-",
                 (report.get("effectiveness") or {}).get("effective")))
    for path in report_paths:
        print("report: %s" % path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mutation", action="append", default=[],
                        help="mutation id (repeatable)")
    parser.add_argument("--all", action="store_true", help="run every catalog mutation")
    parser.add_argument("--list", action="store_true", help="list catalog entries and exit")
    parser.add_argument("--catalog", default=catalog.DEFAULT_CATALOG)
    parser.add_argument("--runs-root", default=workspace.RUNS_ROOT)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--replay", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=240,
                        help="per subprocess timeout (seconds)")
    parser.add_argument("--godot", default="", help="explicit Godot executable")
    parser.add_argument("--json", action="store_true", help="print every run report as JSON")
    parser.add_argument("--clean", action="store_true",
                        help="delete this run's isolated copies after reporting")
    args = parser.parse_args(argv)

    try:
        entries = catalog.load(args.catalog)
    except catalog.CatalogError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 3

    if args.list:
        print_list(entries)
        return 0

    wanted = ["all"] if args.all else args.mutation
    if not wanted:
        print("FAIL: give --mutation <id> or --all (see --list)", file=sys.stderr)
        return 3
    try:
        selected = catalog.select(entries, wanted)
    except catalog.CatalogError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 3

    os.makedirs(args.report_dir, exist_ok=True)
    os.makedirs(args.runs_root, exist_ok=True)
    session = uuid.uuid4().hex[:8]
    reports = []
    report_paths = []
    for entry in selected:
        print("=== %s (%s/%s)" % (entry["mutation_id"], entry["feature_id"],
                                  entry["behavior_id"]))
        report = harness.run_mutation(entry, {
            "runs_root": args.runs_root, "replay": args.replay,
            "timeout": args.timeout, "godot": args.godot, "clean": args.clean})
        report["session"] = session
        reports.append(report)
        path = os.path.join(args.report_dir, "%s.json" % entry["mutation_id"])
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        report_paths.append(path)
        print("    verdict=%s  %s" % (report["verdict"], report["verdict_reason"]))

    summary = harness.summarize(reports)
    summary.update({"session": session, "finished_at": now_iso(),
                    "catalog": os.path.relpath(args.catalog, PROJECT_ROOT).replace("\\", "/")})
    summary_path = os.path.join(args.report_dir, "summary-%s.json" % session)
    with open(summary_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"summary": summary, "reports": reports}, handle,
                  ensure_ascii=False, indent=2)
        handle.write("\n")

    if args.json:
        print(json.dumps({"summary": summary, "reports": reports},
                         ensure_ascii=False, indent=2))
    else:
        print_summary(reports, summary, report_paths + [summary_path])

    if summary["not_run"]:
        return 2
    if summary["killed"] != summary["total"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
