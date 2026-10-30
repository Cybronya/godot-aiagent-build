#!/usr/bin/env python3
"""Feature Instance Evidence Validator (Phase 1.38) —— Validator 第 7 阶段。

把 `instance_evidence.py` 的对账结论接进门禁：声明了 `instance:` 的 Feature 必须与
自己真实入口场景一致；否则 Feature 数据不可信（能力契约会拿假证据放行）。

判定口径（与 instance_evidence 同一实现，不重复判定逻辑）：

    PASS / NOT_DECLARED  -> 计数，不产生输出
    MISMATCH / INVALID   -> failure（已证实矛盾 / 证据链断裂）
    INSUFFICIENT         -> warning（静态无法确认，必须有运行时证据才能下结论）

本模块只读 Feature 目录与 `.tscn` 文本；不启动 Godot、不写文件。

用法:
    python .ai/tools/validator/check_instance_evidence.py [--features-dir DIR] [--json]
退出码: 0 = 无 failure（warning 允许）；1 = 存在 failure；2 = 输入错误。
"""

import argparse
import json
import os
import sys

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
FEATURES_DIR = os.path.join(PROJECT_ROOT, "Features")

sys.path.insert(0, os.path.join(_TOOL_DOTAI, "tools", "scene_composer"))

import instance_evidence                                     # noqa: E402


def check_instance_evidence(features_dir: str = FEATURES_DIR) -> dict:
    """全部 Feature 的实例证据对账 -> {failures, warnings, checked, declared, reports}。"""
    reports = instance_evidence.reconcile_all(features_dir)
    summary = instance_evidence.summarize(reports)
    failures, warnings = [], []
    for report in reports:
        prefix = "Feature instance evidence: %s" % report.feature
        if report.status == instance_evidence.STATUS_MISMATCH:
            for finding in report.errors():
                failures.append("%s %s (%s)" % (prefix, finding["detail"],
                                                finding["node_path"] or finding["resource_path"]))
        elif report.status == instance_evidence.STATUS_INVALID:
            for finding in report.errors():
                failures.append("%s %s" % (prefix, finding["detail"]))
        elif report.status == instance_evidence.STATUS_INSUFFICIENT:
            for finding in report.warnings():
                warnings.append("%s %s" % (prefix, finding["detail"]))
    return {"failures": failures, "warnings": warnings, "checked": summary["checked"],
            "declared": len(instance_evidence.declared_features(features_dir)),
            "summary": summary, "reports": [report.to_dict() for report in reports]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile Feature instance declarations "
                                                 "with their real entry scenes.")
    parser.add_argument("--features-dir", default=FEATURES_DIR)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.features_dir):
        print("FAIL: features dir not found: %s" % args.features_dir)
        return 2

    result = check_instance_evidence(args.features_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Feature Instance Evidence Validator")
        print("  Features checked: %d (declared: %d)"
              % (result["checked"], result["declared"]))
        for report in result["reports"]:
            if report["status"] == instance_evidence.STATUS_NOT_DECLARED:
                continue
            print("  %-18s %-12s %s" % (report["feature"], report["status"],
                                        report["scene"]))
            for finding in report["findings"]:
                print("    - [%s] %s" % (finding["severity"], finding["detail"]))
        if result["failures"]:
            print("\nFAILURES")
            for failure in result["failures"]:
                print("  - " + failure)
        if result["warnings"]:
            print("\nWARNINGS")
            for warning in result["warnings"]:
                print("  - " + warning)
        print("\n" + ("PASS" if not result["failures"] else "FAIL"))
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
