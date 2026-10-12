#!/usr/bin/env python3
"""Asset Validator（单资源）—— 校验一条 Asset Metadata 是否自洽且可用。

    python validate_asset.py player_idle
    python validate_asset.py res://assets/characters/player/idle/ --project .
    python validate_asset.py slime_hurt --json

检查项:
    1. Index      —— 该资产是否存在于 asset_index.json（缺失 = FAIL）
    2. Existence  —— 路径在磁盘上是否存在（animation 组检查全部帧）
    3. Type       —— type 与扩展名/Godot 资源声明是否一致（不一致 = FAIL）
    4. Metadata   —— 图片是否有尺寸、音频是否有时长（缺失 = WARNING，不推断）
    5. Dependencies —— 依赖资源是否都存在于磁盘（缺失 = FAIL）

定位：单资源校验；跨资源/绑定/场景级校验在 .ai/tools/validator/check_assets.py。
退出码: 0 = PASS（允许 WARNING）；1 = FAIL；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_metadata import (          # noqa: E402
    AUDIO_EXTS,
    DEFAULT_PROJECT_ROOT,
    IMAGE_EXTS,
    find_asset,
    load_index,
)

# type -> 允许的格式集合
TYPE_FORMATS = {
    "texture": IMAGE_EXTS,
    "sprite": IMAGE_EXTS,
    "spritesheet": IMAGE_EXTS,
    "animation": IMAGE_EXTS | {""},
    "sprite_frames": {".tres", ".res"},
    "animation_library": {".tres", ".res"},
    "tileset": {".tres", ".res"},
    "audio": AUDIO_EXTS,
    "font": {".ttf", ".otf", ".woff", ".woff2", ".fnt"},
    "shader": {".gdshader", ".gdshaderinc", ".shader"},
    "material": {".tres", ".res"},
    "resource": {".tres", ".res"},
    "scene": {".tscn", ".scn", ".escn"},
    "unknown": set(),
}


def _disk_path(project: Path, res: str) -> Path | None:
    if not res.startswith("res://"):
        return None
    return project / res[len("res://"):].replace("/", os.sep).rstrip(os.sep)


def validate_asset(key: str, project_root: str | os.PathLike | None = None,
                   index: dict | None = None) -> dict:
    """校验单个资产，返回 {ok, failures, warnings, asset}。"""
    project = Path(project_root).resolve() if project_root else DEFAULT_PROJECT_ROOT
    index = index if index is not None else load_index(project_root=project)
    failures: list[str] = []
    warnings: list[str] = []

    asset = find_asset(index, key)
    if asset is None:
        failures.append("Asset not found in index: %s" % key)
        return {"ok": False, "failures": failures, "warnings": warnings, "asset": None}

    path = str(asset.get("path") or "")
    asset_type = str(asset.get("type") or "unknown")

    # 2. 磁盘存在性（animation 组校验全部帧）
    targets = list(asset.get("frames") or []) or [path]
    for target in targets:
        disk = _disk_path(project, target)
        if disk is None:
            warnings.append("Asset path is not a res:// path: %s" % target)
            continue
        if not disk.exists():
            failures.append("Asset path does not exist on disk: %s (id=%s)" % (target, asset.get("id")))
    disk = _disk_path(project, path)

    # 3. 类型与格式一致性
    ext = Path(path.rstrip("/")).suffix.lower()
    allowed = TYPE_FORMATS.get(asset_type)
    if allowed is None:
        warnings.append("Unknown asset type: %s (id=%s)" % (asset_type, asset.get("id")))
    elif allowed and ext not in allowed:
        failures.append("Asset type/format mismatch: type=%s format=%s (id=%s)"
                        % (asset_type, ext or "<dir>", asset.get("id")))
    if asset_type == "animation" and not asset.get("frames"):
        warnings.append("Animation asset without frames: %s" % asset.get("id"))

    # 4. metadata 完整性（缺失只警告，禁止推断）
    if asset_type in ("texture", "spritesheet") and disk is not None and disk.is_file():
        dims = asset.get("dimensions") or {}
        if not dims.get("width") or not dims.get("height"):
            warnings.append("Missing image dimensions for %s (unsupported format header?)"
                            % asset.get("id"))
    if asset_type == "audio" and asset.get("duration") in (None, 0):
        warnings.append("Missing audio duration for %s (unsupported container?)" % asset.get("id"))
    if not asset.get("confirmed"):
        warnings.append("Asset metadata is inferred, not human-confirmed: %s" % asset.get("id"))

    # 5. 依赖完整性
    for dependency in asset.get("dependencies") or []:
        dep_disk = _disk_path(project, dependency)
        if dep_disk is not None and not dep_disk.exists():
            failures.append("Missing dependency of %s: %s" % (asset.get("id"), dependency))

    return {"ok": not failures, "failures": failures, "warnings": warnings, "asset": asset}


def print_report(result: dict) -> None:
    asset = result.get("asset") or {}
    if asset:
        print("Asset:  %s" % asset.get("id"))
        print("Path:   %s" % asset.get("path"))
        print("Type:   %s (%s)" % (asset.get("type"), asset.get("format")))
        print("Tags:   %s" % ", ".join(asset.get("tags") or []))
        print("Confirmed: %s" % bool(asset.get("confirmed")))
    if result["failures"]:
        print("\nFAILURES")
        for failure in result["failures"]:
            print("  - " + failure)
    if result["warnings"]:
        print("\nWARNINGS")
        for warning in result["warnings"]:
            print("  - " + warning)
    if result["failures"]:
        print("\nFAIL")
    elif result["warnings"]:
        print("\nWARNING: 0 error(s), %d warning(s)" % len(result["warnings"]))
    else:
        print("\nPASS")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate a single asset against the generated index.")
    parser.add_argument("asset", help="Asset id, res:// path, or path prefix")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--index", default="", help="Explicit asset_index.json path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    if not project.is_dir():
        print("FAIL: project directory not found: %s" % project)
        return 2
    index = load_index(args.index or None, project_root=project)
    result = validate_asset(args.asset, project, index)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print("Asset Validator")
        print_report(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
