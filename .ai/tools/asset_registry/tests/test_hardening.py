#!/usr/bin/env python3
"""Phase 1.7-H Hardening Tests —— asset_index 策略 / Asset Self-Repair / TileSet / 多方向绑定。

覆盖:
    Test A  asset_index 重建后 --check PASS（.gitignore 策略下 Generated Cache 可再生）
    Test B  direction fallback 链（specific > generic > missing）
    Test C  TileSet -> 绑定 -> TileMapLayer 节点描述（runtime 验证另由 Godot 承担）
    Test D-F  direction coverage 的 Validator 分级（bound-generic WARNING / 无 fossil ERROR）
    附加   asset_repair adapter 的 ok/fail 语义 + self_repair 的 asset 域识别

Runtime / Godot 侧验证由 run_tests.py 与 run_scene.py 承担：
    python .ai/tools/run_tests.py
    python .ai/tools/runtime/run_scene.py --scene res://Scenes/AssetTilemapTest.tscn
退出码: 0 = 全部通过；1 = 存在失败；2 = 输入错误。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

_TOOL_DOTAI = Path(__file__).resolve().parents[3]
_ASSET_DIR = _TOOL_DOTAI / "tools" / "asset_registry"
_RUNTIME_DIR = _TOOL_DOTAI / "tools" / "runtime"
_VALIDATOR_DIR = _TOOL_DOTAI / "tools" / "validator"
sys.path.insert(0, str(_ASSET_DIR))
sys.path.insert(0, str(_RUNTIME_DIR))
sys.path.insert(0, str(_VALIDATOR_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import yaml                                                   # noqa: E402
import bind_assets                                            # noqa: E402
import build_asset_index as builder                           # noqa: E402
import fixture_project                                        # noqa: E402
import check_assets                                           # noqa: E402
from asset_metadata import index_assets, load_index, scan_project  # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def fixture_root() -> Path:
    temp = Path(tempfile.mkdtemp(prefix="hardening_"))
    _temp_dirs.append(temp)
    fixture_project.build_project(temp)
    return temp


def main() -> int:
    root = fixture_root()

    # ---------- Test A: index 重建后 --check PASS ----------
    builder.main(["--project", str(root)])
    ok("Test A: 重建索引成功", builder.main(["--project", str(root), "--check"]) == 0)
    asset_index_path = root / ".ai" / "context" / "asset_index.json"
    ok("Test A: Generated Cache 落盘", asset_index_path.is_file())
    asset_index_path.unlink()
    ok("Test A: 索引缺失 -> --check 退出码 1", builder.main(["--project", str(root), "--check"]) == 1)
    ok("Test A: 删除 Generated Cache 后可再生",
       builder.main(["--project", str(root)]) == 0 and builder.main(["--project", str(root), "--check"]) == 0)

    # ---------- Test D: 4-direction 绑定 ----------
    index = load_index(project_root=root)
    block = bind_assets.bind_entity(
        "player4", "player", [], index, root,
        declared={"subject": "player", "required": ["idle_down", "idle_up", "idle_left", "idle_right"]})
    bound_roles = {entry["role"]: entry["asset"] for entry in block["bindings"]}
    ok("Test D: idle_down 绑定到泛动画 fallback（player_frames）",
       bound_roles.get("idle_down") == "player_frames", str(bound_roles))
    ok("Test D: 四方向全部命中且带 note（无静默降级）",
       all(bound_roles.get("idle_%s" % d) == "player_frames"
           for d in ("down", "up", "left", "right"))
       and all("falls back" in (entry.get("note") or "")
               for entry in block["bindings"]), str(block["bindings"][:1]))
    ok("Test D: missing 为空", not block["missing"], str(block["missing"]))

    # ---------- Test E: 方向缺失但泛角色存在 -> fallback + note ----------
    block2 = bind_assets.bind_entity("player_e", "player", [], index, root,
                                     declared={"subject": "player", "required": ["run_left"]})
    ok("Test E: run_left 缺失时 fallback 到泛 run（run alias 语义）",
       block2["bindings"] and block2["bindings"][0]["asset"] == "player_frames",
       str([b.get("asset") for b in block2["bindings"]]))
    ok("Test E: fallback 写入 note（不静默）",
       bool(block2["bindings"] and "falls back" in (block2["bindings"][0].get("note") or "")),
       str(block2["bindings"])[:200])

    # ---------- Test F: 方向与泛角色都缺失 -> missing ----------
    block3 = bind_assets.bind_entity("player_f", "player", [], index, root,
                                     declared={"subject": "player", "required": ["defeat_left", "defeat_right"]})
    missing_roles = [item["role"] for item in block3["missing"]]
    ok("Test F: defeat_left/defeat_right 无方向与泛资源 -> missing",
       set(missing_roles) >= {"defeat_left", "defeat_right"}, str(missing_roles))
    ok("Test F: 不编造绑定", not block3["bindings"], str(block3["bindings"])[:120])

    # ---------- Test C: TileSet -> TileMapLayer 节点 ----------
    from fixture_project import write_tileset_tres
    block4 = bind_assets.bind_entity(
        "level_c", "level", [], load_index(project_root=root), root,
        declared={"required": ["environment_tileset"]})
    tile_node = (block4["bindings"][0].get("node") or {}) if block4["bindings"] else {}
    ok("Test C: environment_tileset -> ground_tileset",
       bool(block4["bindings"]) and block4["bindings"][0]["asset"] == "ground_tileset",
       str(block4.get("missing")))
    ok("Test C: 节点类型是 TileMapLayer（Godot 4.7，TileMap 已 deprecated）",
       tile_node.get("type") == "TileMapLayer", str(tile_node))
    ok("Test C: 属性是 tile_set", tile_node.get("property") == "tile_set", str(tile_node))
    del write_tileset_tres

    # ---------- Validator: 方向覆盖分级 ----------
    # 构造绑定文档：direction missing 但泛 bound -> WARNING；全无 -> ERROR
    bindings_dir = root / ".ai" / "context" / "asset_bindings"
    bindings_dir.mkdir(parents=True, exist_ok=True)
    warn_doc = {"binding": {
        "entity": "warn_entity", "role": "player", "required_declared": True,
        "bindings": [{"role": "idle", "asset": "player_frames", "node": {}}],
        "missing": [{"role": "idle_left", "kind": "required", "reason": "no asset matched"}],
        "optional_missing": []}}
    (bindings_dir / "warn_entity.yaml").write_text(
        yaml.safe_dump(warn_doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    fail_doc = {"binding": {
        "entity": "fail_entity", "role": "player", "required_declared": True,
        "bindings": [],
        # "defeat_left"：fixture 里既无方向资源也无 defeat 泛资源 -> 必须报 ERROR
        "missing": [{"role": "defeat_left", "kind": "required", "reason": "no asset matched"}],
        "optional_missing": []}}
    (bindings_dir / "fail_entity.yaml").write_text(
        yaml.safe_dump(fail_doc, sort_keys=False, allow_unicode=True), encoding="utf-8")

    project_index = load_index(project_root=root)
    failures: list[str] = []
    warnings: list[str] = []
    check_assets.check_bindings(root, project_index, failures, warnings, binding_dir=str(bindings_dir))
    ok("Validator: 泛 bound + 方向缺失 -> WARNING 而非 ERROR",
       any("falls back" in warning or "not bound" in warning for warning in warnings),
       str(warnings))
    ok("Validator: 无泛资源方向缺失 -> ERROR",
       any("unresolvable" in failure for failure in failures), str(failures))

    # ---------- asset_repair adapter ----------
    from asset_repair import rebuild_binding
    repair = rebuild_binding(root, "res://Scenes/AssetTilemapTest.tscn",
                             blueprint_path=root / "slime-like.yaml")
    ok("AssetRepair: 蓝图缺失时 ok=false（交还通用修复）",
       repair["ok"] is False and bool(repair["reason"]), str(repair))

    # 真实 repo 里的蓝图不可用于临时 fixture —— 用最小 single-entity 蓝图验证成功路径
    bp = root / "test_entity.yaml"
    bp.write_text(yaml.safe_dump({
        "entity": {"id": "test_entity", "role": "player"},
        "features": [],
        "assets": {"subject": "player", "required": ["idle"]},
    }, sort_keys=False), encoding="utf-8")
    repair_ok = rebuild_binding(root, "res://Scenes/TestEntity.tscn", blueprint_path=bp)
    ok("AssetRepair: 显式蓝图 -> ok=true 且绑定写盘",
       repair_ok["ok"] is True and Path(repair_ok["binding_path"]).is_file(),
       str(repair_ok))
    ok("AssetRepair: 只写 asset_bindings（不碰 Feature/Scene/project.godot）",
       str(repair_ok["binding_path"]).replace(os.sep, "/").endswith(
           ".ai/context/asset_bindings/test_entity.yaml"),
       repair_ok["binding_path"])

    # ---------- self_repair 的 asset 域识别（不打 Godot，只查分类函数） ----------
    from self_repair import _asset_diagnosis, _scene_missing_resource
    diagnosis = {"diagnosis": {"status": "failed", "playtest_status": "FAIL",
                               "scene": "res://Scenes/X.tscn", "errors": [
                                   {"classification": "resource_missing",
                                    "message": "Cannot load resource: res://Assets/characters/player/idle/player_idle_00.png",
                                    "file": "", "line": 0, "confidence": "high"}]}}
    asset_block = _asset_diagnosis(diagnosis, root, "res://Scenes/X.tscn")
    ok("Diagnosis: resource_missing + Assets 路径 -> domain=asset",
       asset_block.get("domain") == "asset" and asset_block.get("related_asset", "").startswith("res://Assets/"),
       str(asset_block))

    # 非 asset 错误不得误判：裸 node_not_found -> unknown
    diag2 = {"diagnosis": {"status": "failed", "playtest_status": "FAIL",
                           "scene": "res://Scenes/X.tscn", "errors": [
                               {"classification": "node_not_found",
                                "message": "Node not found: \"SomeNode\"",
                                "file": "res://Features/health/health.gd", "line": 20,
                                "confidence": "high"}]}}
    ok("Diagnosis: 裸 node_not_found 不判 asset 域",
       _asset_diagnosis(diag2, root, "res://Scenes/X.tscn").get("domain") == "unknown")

    # 场景引用缺失资源的确定性校验
    broken_scene = root / "Scenes" / "BrokenRef.tscn"
    broken_scene.parent.mkdir(parents=True, exist_ok=True)
    broken_scene.write_text(
        '[gd_scene load_steps=2 format=3]\n\n'
        '[ext_resource type="SpriteFrames" path="res://Assets/characters/player/nope_frames.tres" id="1"]\n\n'
        '[node name="BrokenRef" type="Node2D"]\n', encoding="utf-8")
    ok("Diagnosis: 场景 ext_resource 缺失 -> 检出路径",
       _scene_missing_resource(root, "res://Scenes/BrokenRef.tscn")
       == "res://Assets/characters/player/nope_frames.tres",
       _scene_missing_resource(root, "res://Scenes/BrokenRef.tscn"))

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Phase 1.7-H hardening tests")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    finally:
        for temp in _temp_dirs:
            shutil.rmtree(temp, ignore_errors=True)
    sys.exit(exit_code)
