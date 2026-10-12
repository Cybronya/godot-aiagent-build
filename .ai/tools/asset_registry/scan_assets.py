#!/usr/bin/env python3
"""Asset Scanner —— 扫描 Asset Root，输出标准 Asset Metadata。

    python scan_assets.py --root Assets
    python scan_assets.py --project . --root assets --out /tmp/scan.json
    python scan_assets.py --json

职责：
    - 找支持的资源文件（图片 / 音频 / 字体 / shader / Godot 资源 / 场景）
    - 判断资源类型（扩展名 + Godot 资源声明 + .import 旁车事实）
    - 抽取基础 metadata（尺寸 / 帧数 / 时长 / 依赖 / 动画名）
    - 由路径与文件名生成 tags / subject / role / category
    - 合并人工确认层（asset_manifest.json）的 confirmed 语义
    - 做确定性兼容性标注（used_by / compatible_features / ...）

不做：视觉识别、写索引（build_asset_index.py）、查询（query_assets.py）、校验（validate_asset.py）。

退出码: 0 = 扫描完成（含 0 资产）；2 = 输入错误。
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
    scan_project,
    summarize_scan,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Scan Godot asset roots into Asset Metadata.")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT_ROOT),
                        help="Godot project root (default: framework project root)")
    parser.add_argument("--root", action="append", default=None,
                        help="Asset root to scan (repeatable; default: existing standard roots)")
    parser.add_argument("--include", action="append", default=None,
                        help="Extra asset file to include (repeatable)")
    parser.add_argument("--out", default="", help="Write the raw scan result JSON to this path")
    parser.add_argument("--list", action="store_true", help="List every scanned asset")
    parser.add_argument("--json", action="store_true", help="Print the full scan result as JSON")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    if not project.is_dir():
        print("FAIL: project directory not found: %s" % project)
        return 2

    result = scan_project(project, roots=args.root, include=args.include)

    if not result["roots"]:
        print("Asset Scan Result")
        print()
        print("No asset root found under %s" % project)
        print("Looked for: %s" % ", ".join(args.root or ["assets", "Assets", "resources",
                                                         "Resources", "Audio", "Textures",
                                                         "Sprites", "Animations", "Tilesets"]))
    else:
        print(summarize_scan(result, show_assets=args.list))
        print()
        print("Roots: %s" % ", ".join(result["roots"]))
        if result.get("human_merged"):
            print("Human-confirmed metadata merged: %d" % result["human_merged"])

    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
        print("Scan result written: %s" % args.out)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
