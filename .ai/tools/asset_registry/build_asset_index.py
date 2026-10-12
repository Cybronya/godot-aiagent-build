#!/usr/bin/env python3
"""Asset Index Builder —— scan -> .ai/context/asset_index.json

    python build_asset_index.py
    python build_asset_index.py --check      # 只检查索引是否与磁盘同步
    python build_asset_index.py --out /tmp/asset_index.json

定位：
    asset_index.json 是 **Generated Cache**，可随时重建；
    Source of Truth = 磁盘资源文件 + 人工确认层（.ai/context/asset_manifest.json）。
    禁止让 Agent 手工维护 asset_index.json。

不做：查询（query_assets.py）、兼容性判定（check_compatibility.py）、校验（validator/check_assets.py）。

退出码: 0 = 成功（--check 时表示已同步）；1 = --check 发现索引陈旧/缺失；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_metadata import (          # noqa: E402
    DEFAULT_PROJECT_ROOT,
    build_index,
    index_assets,
    index_path,
    load_index,
    scan_project,
    summarize_scan,
)

COMPARE_FIELDS = ("path", "type", "format", "category", "subject", "role", "frame_count")


def diff_index(old_index: dict, new_index: dict) -> dict:
    """比较已有索引与新索引（id -> 关键字段 + 增删）。"""
    old = {asset.get("id"): asset for asset in index_assets(old_index)}
    new = {asset.get("id"): asset for asset in index_assets(new_index)}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = []
    for asset_id in sorted(set(old) & set(new)):
        for field in COMPARE_FIELDS:
            if old[asset_id].get(field) != new[asset_id].get(field):
                changed.append({"id": asset_id, "field": field,
                                "was": old[asset_id].get(field), "now": new[asset_id].get(field)})
                break
    return {"added": added, "removed": removed, "changed": changed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build (or check) the generated asset index.")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--root", action="append", default=None, help="Asset root (repeatable)")
    parser.add_argument("--out", default="", help="Index output path (default: .ai/context/asset_index.json)")
    parser.add_argument("--check", action="store_true", help="Only verify the index is in sync")
    parser.add_argument("--json", action="store_true", help="Print the index as JSON")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    if not project.is_dir():
        print("FAIL: project directory not found: %s" % project)
        return 2

    scanned = scan_project(project, roots=args.root)
    index = build_index(scanned)
    target = Path(args.out) if args.out else index_path(project)

    if args.check:
        existing = load_index(target)
        if not existing:
            print("FAIL: asset index missing: %s" % target)
            print("Run: python .ai/tools/asset_registry/build_asset_index.py")
            return 1
        delta = diff_index(existing, index)
        if delta["added"] or delta["removed"] or delta["changed"]:
            print("FAIL: asset index is stale: %s" % target)
            for asset_id in delta["added"]:
                print("  + missing from index: %s" % asset_id)
            for asset_id in delta["removed"]:
                print("  - stale index entry: %s" % asset_id)
            for change in delta["changed"]:
                print("  * %s.%s: %r -> %r" % (change["id"], change["field"], change["was"], change["now"]))
            print("Run: python .ai/tools/asset_registry/build_asset_index.py")
            return 1
        print("PASS: asset index is in sync (%d asset(s))" % len(index_assets(existing)))
        return 0

    if not scanned["roots"]:
        print("Asset Scan Result")
        print()
        print("No asset root found under %s" % project)
        print("Nothing to index; no index written.")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(summarize_scan(scanned))
    print()
    print("Index written: %s" % target)
    print("Assets: %d (confirmed: %d)" % (index["total"],
                                          sum(1 for a in index_assets(index) if a.get("confirmed"))))
    if args.json:
        print(json.dumps(index, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
