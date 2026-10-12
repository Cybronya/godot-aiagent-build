#!/usr/bin/env python3
"""Binding Schema Checker —— 校验 asset_bindings/*.yaml 的实例版本声明。

    python check_binding_schema.py                       # 检查默认目录
    python check_binding_schema.py --bindings-dir PATH   # 指定绑定目录
    python check_binding_schema.py --json

检查项（只 CHECK / REPORT，禁止自动迁移或改写文件）：
    1. schema_version 存在且为整数（缺失 = ERROR）
    2. schema_version 在支持范围内（SUPPORTED_SCHEMA_VERSIONS；未知 = ERROR）

定位：Validator 的「Binding Schema Validation」阶段（介于 Asset Validation 与
Scene Validation 之间）；迁移是独立人工任务，本工具绝不改写绑定文件。

退出码: 0 = 全部通过；1 = 存在违规；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_TOOL_DOTAI = Path(__file__).resolve().parents[2]          # .ai
PROJECT_ROOT = _TOOL_DOTAI.parent
DEFAULT_BINDINGS_DIR = _TOOL_DOTAI / "context" / "asset_bindings"

# 支持的实例版本（与 bind_assets.BINDING_SCHEMA_VERSION / schema 文档 version 一致）
SUPPORTED_SCHEMA_VERSIONS = (2,)

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)


def check_bindings(bindings_dir: str | os.PathLike,
                   supported: tuple = SUPPORTED_SCHEMA_VERSIONS) -> dict:
    """扫描绑定目录，返回 {checked, violations, entries}。

    entries 形如 [{file, schema_version}...]（可读格式便于 PASS 报告）。
    """
    directory = Path(bindings_dir)
    entries: list[dict] = []
    violations: list[dict] = []
    if not directory.is_dir():
        return {"checked": 0, "violations": [], "entries": [],
                "note": "binding directory not found: %s" % directory}

    yaml_files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))
    for path in yaml_files:
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            violations.append({"file": path.name, "kind": "unreadable", "detail": str(exc)})
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("binding"), dict):
            violations.append({"file": path.name, "kind": "not_a_binding_document",
                               "detail": "missing 'binding:' mapping"})
            continue
        if "schema_version" not in doc:
            violations.append({"file": path.name, "kind": "missing_schema_version",
                               "detail": "add top-level 'schema_version: <int>'"})
            continue
        version = doc.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int):
            violations.append({"file": path.name, "kind": "invalid_schema_version",
                               "detail": "schema_version must be an integer, got %r" % version})
            continue
        if version not in supported:
            violations.append({"file": path.name, "kind": "unsupported_schema_version",
                               "detail": "schema_version=%s not supported (supported: %s); "
                                         "migration is a separate task"
                                         % (version, sorted(supported))})
            continue
        entries.append({"file": path.name, "schema_version": version})
    return {"checked": len(yaml_files), "violations": violations, "entries": entries}


def print_report(result: dict) -> None:
    print("Binding Schema Check")
    print("Checked: %d" % result["checked"])
    for entry in result["entries"]:
        print("PASS:   %s  schema_version=%d" % (entry["file"], entry["schema_version"]))
    if result.get("note"):
        print("Note:   %s" % result["note"])
    for violation in result["violations"]:
        print("ERROR:  %s  (%s)" % (violation["file"], violation["kind"]))
        print("        %s" % violation.get("detail") or "")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check asset binding schema_version declarations.")
    parser.add_argument("--bindings-dir", default=str(DEFAULT_BINDINGS_DIR))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = check_bindings(args.bindings_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)
    return 1 if result["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
