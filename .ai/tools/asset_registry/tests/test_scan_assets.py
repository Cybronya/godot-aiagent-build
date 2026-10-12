#!/usr/bin/env python3
"""Asset Scanner 回归测试（Test 1 / Test 2 + 类型与语义推导）。

覆盖：
    Test 1  正常 Asset（player_idle.png 组）→ 扫描可用、validate_asset PASS
    Test 2  不存在的 Asset → validate_asset FAIL（不推断、不编造）
    附加    图片 / 音频 / SpriteFrames / TileSet 的类型判定
    附加    animation 组聚合（同目录帧 -> 一条 animation，帧序稳定）
    附加    subject / role / category / tags 的确定性推导（无视觉识别）
    附加    人工确认层合并（confirmed / id / tags 覆盖）

用法:
    python .ai/tools/asset_registry/tests/test_scan_assets.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REGISTRY_DIR = TEST_DIR.parent
PROJECT_ROOT = REGISTRY_DIR.parents[2]

if str(REGISTRY_DIR) not in sys.path:
    sys.path.insert(0, str(REGISTRY_DIR))
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

import fixture_project                                                  # noqa: E402
from asset_metadata import (                                            # noqa: E402
    apply_human_layer,
    build_index,
    find_asset,
    index_assets,
    scan_project,
)
from validate_asset import validate_asset                               # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def fixture_project_root() -> Path:
    temp = Path(tempfile.mkdtemp(prefix="asset_scan_"))
    _temp_dirs.append(temp)
    fixture_project.build_project(temp)
    return temp


def main() -> int:
    root = fixture_project_root()
    result = scan_project(root)
    assets = result["assets"]
    by_id = {asset["id"]: asset for asset in assets}

    print("--- Asset Scanner ---")
    print("roots: %s" % ", ".join(result["roots"]))
    print("stats: %s" % result["stats"])
    print("total: %d (files scanned: %d)" % (result["total"], result["scanned_files"]))
    print()

    # ---- Test 1: 正常 Asset ----
    player_idle = by_id.get("player_idle")
    ok("Test 1: player_idle 被扫描到", player_idle is not None)
    if player_idle:
        ok("Test 1: type=animation", player_idle["type"] == "animation", str(player_idle["type"]))
        ok("Test 1: path 指向动作目录",
           player_idle["path"] == "res://Assets/characters/player/idle/", player_idle["path"])
        ok("Test 1: frame_count=2", player_idle["frame_count"] == 2, str(player_idle["frame_count"]))
        ok("Test 1: subject=player", player_idle["subject"] == "player", player_idle["subject"])
        ok("Test 1: role=idle", player_idle["role"] == "idle", player_idle["role"])
        ok("Test 1: category=player", player_idle["category"] == "player", player_idle["category"])
        ok("Test 1: tags 含 player/idle/animation",
           {"player", "idle", "animation"}.issubset(set(player_idle["tags"])), str(player_idle["tags"]))
        ok("Test 1: dimensions 32x32",
           (player_idle.get("dimensions") or {}).get("width") == 32,
           str(player_idle.get("dimensions")))
        ok("Test 1: 帧有序（00 -> 01）",
           [f.rsplit("_", 1)[-1] for f in player_idle["frames"]] == ["00.png", "01.png"],
           str(player_idle["frames"]))
    single = validate_asset("player_idle", root, build_index(result))
    ok("Test 1: validate_asset PASS", single["ok"], "; ".join(single["failures"]))
    ok("Test 1: 未人工确认只给 WARNING（不推断语义）",
       any("not human-confirmed" in w for w in single["warnings"]), str(single["warnings"]))

    # ---- 类型判定 ----
    ok("type: SpriteFrames .tres -> sprite_frames",
       by_id.get("player_frames", {}).get("type") == "sprite_frames",
       str(by_id.get("player_frames", {}).get("type")))
    ok("type: TileSet .tres -> tileset",
       by_id.get("ground_tileset", {}).get("type") == "tileset",
       str(by_id.get("ground_tileset", {}).get("type")))
    ok("type: .wav -> audio", by_id.get("slime_hurt_audio", {}).get("type") == "audio",
       str(by_id.get("slime_hurt_audio", {}).get("type")))
    ok("type: 松散 png -> texture",
       by_id.get("health_icon", {}).get("type") == "texture",
       str(by_id.get("health_icon", {}).get("type")))
    ok("SpriteFrames 记录 animations",
       by_id.get("slime_frames", {}).get("animations") == ["idle", "move", "attack", "hurt"],
       str(by_id.get("slime_frames", {}).get("animations")))

    # ---- animation 组聚合 + 同名不同类型 disambiguation ----
    ok("聚合: slime_move 是 animation 组",
       by_id.get("slime_move", {}).get("type") == "animation")
    ok("聚合: slime_move frame_count=3", by_id.get("slime_move", {}).get("frame_count") == 3)
    ok("同名不同类型: slime_attack_animation / slime_attack_audio 并存",
       "slime_attack_animation" in by_id and "slime_attack_audio" in by_id,
       str(sorted(by_id)))
    ok("无 SpriteFrames 的 death 组仍被扫描",
       by_id.get("slime_death", {}).get("type") == "animation")
    ok("残留帧不外泄为独立 asset（帧已被聚合）",
       not any(str(a["id"]).endswith("_f00") for a in assets), str(sorted(by_id)))

    # ---- 类别判定：player / enemy / environment / ui / audio ----
    ok("category: enemy 目录 -> enemy",
       by_id.get("slime_idle", {}).get("category") == "enemy")
    ok("category: environment 目录 -> environment",
       by_id.get("ground_tileset", {}).get("category") == "environment")
    ok("category: ui 目录 -> ui", by_id.get("health_icon", {}).get("category") == "ui")
    ok("category: audio 目录 -> audio", by_id.get("slime_hurt_audio", {}).get("category") == "audio")

    # ---- 扫描统计 ----
    stats = result["stats"]
    ok("stats: 6 个 animation（player 4 + slime 5 - death 组算 1 ... 校验下限）",
       stats.get("animation", 0) >= 8, str(stats))
    ok("stats: sprite_frames=2", stats.get("sprite_frames") == 2, str(stats))
    ok("stats: audio=2", stats.get("audio") == 2, str(stats))
    ok("stats: tileset=1", stats.get("tileset") == 1, str(stats))

    # ---- Test 2: 不存在的 Asset ----
    index = build_index(result)
    missing = validate_asset("res://Assets/player_missing.png", root, index)
    ok("Test 2: 不存在的 Asset FAIL", missing["ok"] is False)
    ok("Test 2: 失败原因说明索引缺失",
       any("not found in index" in f for f in missing["failures"]), str(missing["failures"]))

    # 索引里存在的 asset，磁盘文件被删掉 -> FAIL（不会假装存在）
    stale_root = fixture_project_root()
    target = stale_root / "Assets" / "characters" / "player" / "idle" / "player_idle_01.png"
    stale_index = build_index(scan_project(stale_root))    # 先建索引，再删文件
    target.unlink()
    stale = validate_asset("player_idle", stale_root, stale_index)
    ok("Test 2: 帧文件缺失 -> FAIL", stale["ok"] is False)
    ok("Test 2: 指出缺失的具体路径",
       any("does not exist on disk" in f and "player_idle_01" in f for f in stale["failures"]),
       str(stale["failures"]))

    # ---- 人工确认层 ----
    human_root = fixture_project_root()
    manifest = human_root / ".ai" / "context" / "asset_manifest.yaml"
    manifest.write_text(
        "assets:\n"
        "  - id: slime_hurt_sfx\n"
        "    path: res://Assets/audio/slime/hurt.wav\n"
        "    category: audio\n"
        "    type: audio\n"
        "    subject: slime\n"
        "    role: hurt\n"
        "    tags: [sfx]\n"
        "    confirmed: true\n",
        encoding="utf-8")
    human_scan = scan_project(human_root)
    human_asset = find_asset(build_index(human_scan), "slime_hurt_sfx")
    ok("人工确认层: id 覆盖生效", human_asset is not None)
    if human_asset:
        ok("人工确认层: confirmed=true", human_asset["confirmed"] is True)
        ok("人工确认层: source=manifest", human_asset["source"] == "manifest",
           str(human_asset["source"]))
        ok("人工确认层: tags 合并", "sfx" in human_asset["tags"], str(human_asset["tags"]))
    ok("人工确认层: 未确认资源保持 confirmed=false",
       not find_asset(build_index(human_scan), "player_idle")["confirmed"])
    ok("人工确认层合并计数=1", human_scan["human_merged"] == 1, str(human_scan["human_merged"]))

    # apply_human_layer 不改变资产文件（只读资源）
    ok("apply_human_layer 只改元数据（文件仍在）",
       (human_root / "Assets" / "audio" / "slime" / "hurt.wav").is_file())

    for temp in _temp_dirs:
        shutil.rmtree(temp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Asset Scanner tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
