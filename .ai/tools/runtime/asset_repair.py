#!/usr/bin/env python3
"""Asset Repair Adapter —— Runtime 资源失败的自动绑定重建。

    Runtime Failure (domain=asset)
        ↓
    asset_repair.repair_assets()
        ├─ 定位 Entity Blueprint（scene -> entity blueprint yaml，确定性）
        ├─ 读 Asset Index / Manifest（只读）
        ├─ 重新执行 bind_assets.bind_*（Asset Registry，单一事实来源）
        └─ 写新 Binding 到 .ai/context/asset_bindings/<entity>.yaml
        ↓
    返回 {ok, rebuilt, binding_path, changed_files, reason}，由 self_repair.py
    接着跑 Static Validation 与 Runtime Playtest。

职责边界（硬约束）：
    - 只重建 Asset Binding（.ai/context/asset_bindings/*.yaml，Generated Data）；
    - 禁止修改 Feature / Scene / project.godot / 资源文件本身；
    - 禁止删除 Scene / Feature；禁止凭空造 asset id（仍由 indice 决定）；
    - 没有可靠证据（blueprint 不存在、索引为空）时 ok=false，交还通用修复流程。

退出码: 0 = 已重建绑定；1 = 无法重建；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

SCRIPT_DIR = Path(__file__).resolve().parent
DOTAI_DIR = SCRIPT_DIR.parent.parent                      # .ai
PROJECT_ROOT = DOTAI_DIR.parent
ASSET_REGISTRY_DIR = DOTAI_DIR / "tools" / "asset_registry"
if str(ASSET_REGISTRY_DIR) not in sys.path:
    sys.path.insert(0, str(ASSET_REGISTRY_DIR))


def _blueprint_candidates(scene: str, project_root: Path) -> list[Path]:
    """被验证场景 -> 可能的 Entity / Gameplay Blueprint 文件（确定性顺序）。"""
    scene_name = Path(str(scene).replace("res://", "").rstrip("/")).stem.lower()   # SlimeEnemy -> slimeenemy
    if not scene_name:
        return []
    candidates: list[Path] = []
    for base in ("blueprints", ".ai/context/blueprints", ".ai/context",
                 "Scenes/blueprints", "."):
        directory = project_root / base
        if not directory.is_dir():
            continue
        for yaml_path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
            if base == "." and yaml_path.name == "project.godot":
                continue
            if yaml_path.stem.lower().replace("_", "") == scene_name.replace("_", ""):
                candidates.append(yaml_path)
    return candidates


def _entity_id_for_scene(scene: str) -> str:
    return Path(str(scene).replace("res://", "").rstrip("/")).stem.lower() or "entity"


def rebuild_binding(project_root: str | os.PathLike, scene: str,
                    blueprint_path: str | os.PathLike | None = None,
                    out_path: str | os.PathLike | None = None) -> dict:
    """为 scene 重建 Asset Binding（只写绑定文档，不触碰 Feature/Scene/资源）。

    返回 {ok, reason, binding_path, changed_files, missing}。
    """
    root = Path(project_root).resolve()
    failed: dict = {"ok": False, "reason": "", "binding_path": "", "changed_files": [], "missing": []}

    if ASSET_REGISTRY_DIR and str(ASSET_REGISTRY_DIR) not in sys.path:
        sys.path.insert(0, str(ASSET_REGISTRY_DIR))
    import bind_assets                                    # noqa: E402
    from asset_metadata import index_assets, load_index   # noqa: E402

    index = load_index(project_root=root)
    if not index_assets(index):
        failed["reason"] = ("asset index is empty or missing; rebuild it with "
                            "python .ai/tools/asset_registry/build_asset_index.py "
                            "before asset repair")
        return failed

    # 1. 定位 Entity / Gameplay Blueprint（显式路径优先）
    blueprint: Path | None = Path(blueprint_path) if blueprint_path else None
    if blueprint is None or not blueprint.is_file():
        blueprint = None
        for candidate in _blueprint_candidates(scene, root):
            if candidate.is_file():
                blueprint = candidate
                break
    if blueprint is None:
        failed["reason"] = ("no entity/gameplay blueprint found for scene %r; asset repair "
                            "only rebuilds bindings from an existing blueprint" % scene)
        return failed

    data = yaml.safe_load(blueprint.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        failed["reason"] = "blueprint is not a YAML mapping: %s" % blueprint
        return failed

    explicit: dict[str, str] = {}
    declared_assets = data.get("assets") if isinstance(data.get("assets"), dict) else {}
    for entry in declared_assets.get("bindings") or []:
        if isinstance(entry, dict) and entry.get("role") and entry.get("asset"):
            explicit[str(entry["role"])] = str(entry["asset"])

    # 2. 重新解析绑定（gameplay 优先：script / multi-entity；否则单实体）
    if data.get("entities") and isinstance(data.get("entities"), dict):
        doc = bind_assets.bind_gameplay(data, index, root, explicit)
    else:
        entity = data.get("entity") or {}
        declared = data.get("assets") if isinstance(data.get("assets"), dict) else {}
        entity_id = str(entity.get("id") or data.get("id") or _entity_id_for_scene(scene))
        entity_role = str(entity.get("role") or declared.get("role") or "entity")
        if entity_role == "entity" and not entity:
            failed["reason"] = "blueprint %s has no entity section to rebind" % blueprint.name
            return failed
        entity_block = bind_assets.bind_entity(
            entity_id, entity_role,
            [str(f) for f in (data.get("features") or [])],
            index, root, declared=declared, explicit=explicit)
        doc = {"schema_version": bind_assets.BINDING_SCHEMA_VERSION,
               "binding": dict(entity_block, source="entity_blueprint")}

    # 3. 写绑定文档（Generated Data；旧的绑定被覆盖，历史由 self_repair 记录）
    target = Path(out_path) if out_path else root / ".ai/context/asset_bindings" / (
        str((doc.get("binding") or {}).get("entity") or "entity") + ".yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=4096),
                      encoding="utf-8")

    entities = doc.get("binding", {}).get("entities") or [doc.get("binding")]
    missing = [entry.get("role") for block in entities
               if isinstance(block, dict)
               for entry in (block.get("missing") or [])
               if entry.get("kind") == "required"]
    return {"ok": True, "reason": "asset binding rebuilt from %s" % blueprint.name,
            "binding_path": str(target), "changed_files": [str(target)], "missing": missing}


def repair_assets(project_root: str | os.PathLike, scene: str,
                  diagnosis: dict | None = None,
                  blueprint_path: str | os.PathLike | None = None,
                  out_path: str | os.PathLike | None = None) -> dict:
    """self_repair.py 的入口：Asset 域修复。失败时 ok=false（不抛异常）。"""
    try:
        return rebuild_binding(project_root, scene, blueprint_path=blueprint_path,
                               out_path=out_path)
    except Exception as exc:                              # noqa: BLE001 - adapter 不得中断修复闭环
        return {"ok": False, "reason": "asset repair failed: %s" % exc,
                "binding_path": "", "changed_files": [], "missing": []}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild asset bindings after a runtime asset failure.")
    parser.add_argument("--scene", required=True, help="Scene reference, e.g. res://Scenes/SlimeEnemy.tscn")
    parser.add_argument("--project", default=".")
    parser.add_argument("--blueprint", default="", help="Entity/Gameplay blueprint yaml (default: auto-locate)")
    parser.add_argument("--out", default="", help="Binding document output path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    if not project.is_dir():
        print("FAIL: project directory not found: %s" % project)
        return 2
    result = repair_assets(project, args.scene,
                           blueprint_path=args.blueprint or None,
                           out_path=args.out or None)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Asset Repair")
        print("Scene:    %s" % args.scene)
        print("Result:   %s" % ("OK" if result["ok"] else "FAIL"))
        print("Reason:   %s" % result["reason"])
        if result.get("binding_path"):
            print("Binding:  %s" % result["binding_path"])
        for role in result.get("missing") or []:
            print("Missing:  %s" % role)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
