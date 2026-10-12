#!/usr/bin/env python3
"""Asset Validation —— Validator 的资源阶段（静态，只 CHECK / REPORT）。

在 Validator 阶段链中的位置：

    1. Project Validation   (validate.py)
    2. Feature Validation   (check_feature_metadata.py)
    3. Asset Validation     (本文件)  ← 资源路径 / 类型 / 绑定 / 引用完整性
    4. Scene Validation     (check_scene_composition.py)
    5. Gameplay Validation  (check_gameplay.py)
    6. Runtime Validation   (check_runtime.py)

检查项（对应 .ai/context/asset_schema.yaml 与 asset_binding_schema.yaml）:

    1. Asset Path       —— 索引中每条资源的路径必须在磁盘上存在（缺失 = ERROR）
    2. Resource Type    —— type 与格式/Godot 资源声明一致（不一致 = ERROR）
    3. Binding          —— .ai/context/asset_bindings/*.yaml 的每个绑定：
                           asset 在索引中、资源节点路径存在、必填角色缺失判定
    4. Scene Resource   —— Scenes/*.tscn 的 ext_resource 引用必须存在；导入型资源
                           缺 .import 旁车时给 WARNING（Godot 尚未导入）
    5. Missing Asset    —— 绑定 missing 清单 + 人工确认层里路径不存在的条目
    6. Index Sync       —— asset_index.json 是否与磁盘同步（陈旧 = ERROR）

职责边界（架构约束）：
    - 本文件只判定与报告，绝不修改项目、资源、索引或绑定；
      修索引由 build_asset_index.py 负责，修改资源属人工权限。
    - 没有资源根目录时不报错：Asset Registry 是可选层（checked=0）。

作为模块导入:
    from check_assets import check_assets
    result = check_assets()               # {failures, warnings, checked, note}

退出码: 0 = PASS（允许 WARNING）；1 = FAIL；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
ASSET_REGISTRY_DIR = os.path.join(_TOOL_DOTAI, "tools", "asset_registry")
BINDING_DIR = os.path.join(_TOOL_DOTAI, "context", "asset_bindings")
SCENES_DIR = os.path.join(PROJECT_ROOT, "Scenes")

if ASSET_REGISTRY_DIR not in sys.path:
    sys.path.insert(0, ASSET_REGISTRY_DIR)

from asset_metadata import (            # noqa: E402
    IMAGE_EXTS,
    AUDIO_EXTS,
    asset_exists_on_disk,
    build_index,
    find_asset,
    index_assets,
    load_index,
    load_manifest,
    scan_project,
)
from build_asset_index import diff_index          # noqa: E402
from validate_asset import TYPE_FORMATS           # noqa: E402

_EXT_RESOURCE_RE = re.compile(r'^\[ext_resource[^\]]*path="(res://[^"]+)"', re.M)
_BINDING_GLOBS = ("*.yaml", "*.yml")

_DIRECTION_SUFFIXES = ("up_left", "up_right", "down_left", "down_right",
                       "up", "down", "left", "right")


def _split_role_direction(role: str) -> tuple[str, str]:
    name = str(role or "").strip().lower()
    for direction in sorted(_DIRECTION_SUFFIXES, key=len, reverse=True):
        if name.endswith("_" + direction):
            return name[: -(len(direction) + 1)], direction
    return name, ""


def _check_direction_coverage(entity: dict, label: str, index: dict,
                              failures: list, warnings: list) -> None:
    """检查绑定里每个缺失的方向角色：泛角色可用 -> WARNING；否则 ERROR。

    move_left 缺失但泛 move 已绑定 -> WARNING（fallback 已生效）；
    move_left 缺失且泛 move 无处可寻 -> ERROR（无 fallback 可退）。
    """
    bound_roles = {str(entry.get("role") or "") for entry in entity.get("bindings") or []}
    bound_assets = {str(entry.get("asset") or "") for entry in entity.get("bindings") or []}
    for item in entity.get("missing") or []:
        role = str(item.get("role") or "")
        base, direction = _split_role_direction(role)
        if not direction:
            continue
        already_bound = any(_split_role_direction(other)[0] == base
                            for other in bound_roles if other != role)
        if already_bound:
            warnings.append("Directional role %s falls back to a bound generic asset "
                            "(%s) (%s)" % (role, base, label))
            continue
        generic_exists = False
        for asset in index_assets(index):
            if str(asset.get("id") or "") in bound_assets:
                continue
            anims = [str(a).lower() for a in (asset.get("animations") or [])]
            if base in anims or str(asset.get("role") or "") == base:
                generic_exists = True
                break
        if generic_exists:
            warnings.append("Directional role %s has no dedicated asset; generic %s exists "
                            "but is not bound (%s)" % (role, base, label))
        else:
            failures.append("Directional role %s is unresolvable: neither %s nor a %s "
                            "asset exists (%s)" % (role, role, base, label))


def _disk_path(project: Path, res_path: str) -> Path | None:
    if not str(res_path).startswith("res://"):
        return None
    return project / str(res_path)[len("res://"):].replace("/", os.sep)


def _resolve_scene(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_ROOT, path)


def _relative_label(path: Path, project: Path) -> str:
    """项目内相对路径标签（不依赖两者是否同盘/同区）。"""
    for base in (project, Path(PROJECT_ROOT)):
        try:
            return os.path.relpath(str(path), str(base)).replace("\\", "/")
        except ValueError:
            continue
    return path.name


def check_index_sync(project: Path, failures: list, warnings: list) -> dict:
    """1/6: 索引存在且与磁盘同步。返回 {assets, total}。"""
    scanned = scan_project(project)
    if not scanned["roots"]:
        return {"present": False}
    index = load_index(project_root=project)
    if not index_assets(index):
        failures.append("Asset index missing or empty: .ai/context/asset_index.json "
                        "(run: python .ai/tools/asset_registry/build_asset_index.py)")
        return {"present": False}
    delta = diff_index(index, build_index(scanned))
    for asset_id in delta["added"]:
        failures.append("Asset index is stale (missing asset %s): rebuild with "
                        "build_asset_index.py" % asset_id)
    for asset_id in delta["removed"]:
        failures.append("Asset index is stale (stale entry %s): rebuild with "
                        "build_asset_index.py" % asset_id)
    for change in delta["changed"]:
        failures.append("Asset index is stale (%s.%s: %r -> %r): rebuild with "
                        "build_asset_index.py" % (change["id"], change["field"],
                                                  change["was"], change["now"]))
    return {"present": True, "total": len(index_assets(index))}


def check_asset_facts(project: Path, index: dict, failures: list, warnings: list,
                      unimported: bool = True) -> int:
    """2/1: 每条索引资源的磁盘存在性、类型一致性、Godot 导入状态。"""
    checked = 0
    for asset in index_assets(index):
        checked += 1
        asset_id = asset.get("id")
        path = str(asset.get("path") or "")
        targets = list(asset.get("frames") or []) or [path]
        for target in targets:
            if not asset_exists_on_disk(project, {"path": target}):
                failures.append("Asset path does not exist: %s (id=%s)" % (target, asset_id))
        asset_type = str(asset.get("type") or "unknown")
        ext = Path(path.rstrip("/")).suffix.lower()
        allowed = TYPE_FORMATS.get(asset_type)
        if allowed and ext and ext not in allowed and not (asset_type == "animation"):
            failures.append("Asset type/format mismatch: type=%s format=%s (id=%s)"
                            % (asset_type, ext or "<dir>", asset_id))
        if not unimported or asset_type not in ("texture", "spritesheet", "audio"):
            continue
        if ext not in IMAGE_EXTS | AUDIO_EXTS:
            continue
        disk = _disk_path(project, path)
        if disk is None or not disk.is_file():
            continue
        if not Path(str(disk) + ".import").is_file():
            warnings.append("Asset is not imported by Godot yet (missing .import): %s" % path)
    return checked


def check_bindings(project: Path, index: dict, failures: list, warnings: list,
                   binding_dir: str | None = None) -> int:
    """3/5: 绑定文档自洽（asset 存在、节点路径存在、缺失角色性质）。"""
    import yaml

    directory = Path(binding_dir) if binding_dir else project / ".ai" / "context" / "asset_bindings"
    if not directory.is_dir():
        return 0
    checked = 0
    for pattern in _BINDING_GLOBS:
        for path in sorted(directory.glob(pattern)):
            try:
                doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception as exc:
                failures.append("Invalid asset binding YAML: %s (%s)" % (path.name, exc))
                continue
            binding = (doc or {}).get("binding") or {}
            entities = binding.get("entities") if isinstance(binding.get("entities"), list) else [binding]
            rel = _relative_label(path, project)
            for entity in entities:
                if not isinstance(entity, dict) or entity.get("bindings") is None:
                    continue
                checked += 1
                label = "%s[%s]" % (rel, entity.get("entity") or "?")
                explicit_required = bool(entity.get("required_declared"))
                for entry in entity.get("bindings") or []:
                    asset_key = str(entry.get("asset") or "")
                    asset = find_asset(index, asset_key) if asset_key else None
                    if asset is None:
                        failures.append("Binding references unknown asset %r (%s, role=%s)"
                                        % (asset_key, label, entry.get("role")))
                        continue
                    node = entry.get("node") if isinstance(entry.get("node"), dict) else {}
                    node_path = str(node.get("path") or "")
                    if node_path and not asset_exists_on_disk(project, {"path": node_path}):
                        failures.append("Binding resource missing on disk: %s (%s, role=%s)"
                                        % (node_path, label, entry.get("role")))
                    level = entry.get("compatibility")
                    if level == "INCOMPATIBLE":
                        failures.append("Binding is INCOMPATIBLE with the entity/feature (role=%s, %s, "
                                        "asset=%s)" % (entry.get("role"), label, asset_key))
                    elif level in ("WARNING", "UNKNOWN"):
                        warnings.append("Binding compatibility is %s (role=%s, %s, asset=%s)"
                                        % (level, entry.get("role"), label, asset_key))
                for item in entity.get("missing") or []:
                    reason = item.get("reason") or "missing asset role"
                    if explicit_required:
                        failures.append("Missing required asset binding: %s (%s)" % (reason, label))
                    else:
                        warnings.append("Missing inferred asset binding: %s (%s)" % (reason, label))
                # Direction binding validation（Phase 1.7-H）：
                # move_left 缺失但泛 move 存在 -> WARNING（fallback）；
                # move_left 缺失且泛 move 也缺失 -> ERROR。
                _check_direction_coverage(entity, label, index, failures, warnings)
    return checked


def check_scene_resources(project: Path, index: dict, failures: list, warnings: list,
                          scenes: list | None = None, scenes_dir: str | None = None) -> int:
    """4: 场景 ext_resource 引用必须存在；资源应已被索引。"""
    targets: list[Path] = []
    for scene in scenes or []:
        resolved = _resolve_scene(scene)
        targets.append(Path(resolved))
    if not scenes:
        directory = Path(scenes_dir) if scenes_dir else project / "Scenes"
        if directory.is_dir():
            targets.extend(sorted(directory.glob("*.tscn")))
    known_paths: set[str] = set()
    for asset in index_assets(index):
        known_paths.add(str(asset.get("path") or ""))
        for frame in asset.get("frames") or []:
            known_paths.add(str(frame))
    checked = 0
    for path in targets:
        if not path.is_file():
            failures.append("Scene not found: %s" % path)
            continue
        checked += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for ref in sorted(set(_EXT_RESOURCE_RE.findall(text))):
            if not asset_exists_on_disk(project, {"path": ref}):
                failures.append("Scene %s references a missing resource: %s"
                                % (path.name, ref))
            elif ref.startswith("res://Assets/") and ref.rstrip("/") not in known_paths \
                    and (ref.rstrip("/") + "/") not in known_paths:
                warnings.append("Scene %s references an unindexed asset: %s "
                                "(rebuild the asset index)" % (path.name, ref))
    return checked


def check_manifest(project: Path, failures: list, warnings: list) -> int:
    """5: 人工确认层里登记的路径必须存在（防止 manifest 悬空）。"""
    manifest = load_manifest(project)
    entries = [entry for entry in manifest.get("assets") or [] if isinstance(entry, dict)]
    checked = len(entries)
    for entry in entries:
        path = entry.get("path") or (entry.get("auto") or {}).get("path")
        if not path:
            continue
        asset_id = entry.get("id") or (entry.get("human") or {}).get("id") or "<unconfirmed>"
        disk = _disk_path(project, str(path))
        if disk is None or not disk.exists():
            warnings.append("Asset manifest entry points to a missing path: %s (id=%s)"
                            % (path, asset_id))
    return checked


def check_assets(project_root: str | os.PathLike | None = None,
                 scenes: list | None = None,
                 binding_dir: str | None = None,
                 scenes_dir: str | None = None,
                 manifest: bool = True) -> dict:
    """Asset Validation 入口；返回 {failures, warnings, checked, note}。"""
    project = Path(project_root).resolve() if project_root else Path(PROJECT_ROOT)
    failures: list[str] = []
    warnings: list[str] = []

    index_info = check_index_sync(project, failures, warnings)
    if not index_info.get("present"):
        scanned = scan_project(project)
        if not scanned["roots"]:
            return {"failures": [], "warnings": [], "checked": 0,
                    "note": "no asset root found (Asset Registry is optional)"}
        return {"failures": failures, "warnings": warnings, "checked": 0,
                "note": "asset root found but index unavailable"}

    index = load_index(project_root=project)
    checked = index_info.get("total") or 0
    check_asset_facts(project, index, failures, warnings)
    checked += check_bindings(project, index, failures, warnings, binding_dir)
    checked += check_scene_resources(project, index, failures, warnings, scenes, scenes_dir)
    if manifest:
        check_manifest(project, failures, warnings)
    return {"failures": failures, "warnings": warnings, "checked": checked,
            "note": "assets=%d" % (index_info.get("total") or 0)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Asset Validation stage (read-only).")
    parser.add_argument("--project-root", default=PROJECT_ROOT)
    parser.add_argument("--scene", action="append", default=None,
                        help="Scene to check (repeatable; default: all Scenes/*.tscn)")
    parser.add_argument("--bindings-dir", default="", help="Default: <project>/.ai/context/asset_bindings")
    parser.add_argument("--no-manifest", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = check_assets(args.project_root, scenes=args.scene,
                          binding_dir=args.bindings_dir or None,
                          manifest=not args.no_manifest)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Asset Validator")
        print("Checked: %d" % result["checked"])
        if result.get("note"):
            print("Note:    %s" % result["note"])
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
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
