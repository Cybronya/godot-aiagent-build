#!/usr/bin/env python3
"""Asset Compatibility + Binding 回归测试（Test 4 / Test 5）。

覆盖：
    Test 4  player + player_idle → COMPATIBLE
    Test 5  player + 敌人资源 → INCOMPATIBLE；能力不匹配的音频 → WARNING
    附加    Feature 能力提示判定（player_movement + player_run → COMPATIBLE）
    附加    bind_assets 角色解析（idle/move/attack/hurt/*_sfx -> 具体 asset）
    附加    SpriteFrames 优先、无 SpriteFrames 时退化为首帧静态贴图并注明
    附加    显式绑定优先；显式绑定引用不存在的 asset → missing（不静默忽略）
    附加    必填角色缺失 → missing.required，--strict 退出码 1

用法:
    python .ai/tools/asset_registry/tests/test_asset_binding.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REGISTRY_DIR = TEST_DIR.parent

if str(REGISTRY_DIR) not in sys.path:
    sys.path.insert(0, str(REGISTRY_DIR))
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

import bind_assets                                                     # noqa: E402
import fixture_project                                                 # noqa: E402
from asset_metadata import build_index, find_asset, scan_project       # noqa: E402
from check_compatibility import (                                      # noqa: E402
    COMPATIBLE,
    INCOMPATIBLE,
    UNKNOWN,
    WARNING,
    compatibility,
    load_feature,
)

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
    temp = Path(tempfile.mkdtemp(prefix="asset_bind_"))
    _temp_dirs.append(temp)
    return temp


def main() -> int:
    root = fixture_project_root()
    fixture_project.build_project(root)

    # 写一个能提供 movement 能力的 Feature（验证能力提示路径）
    feature_dir = root / "Features" / "player_movement"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "feature.yaml").write_text(
        "id: player_movement\n"
        "provides:\n"
        "  - input_driven_movement\n"
        "relations:\n"
        "  entity_roles:\n"
        "    - player\n",
        encoding="utf-8")
    # 敌人特征：用于验证角色冲突
    enemy_dir = root / "Features" / "chase_movement"
    enemy_dir.mkdir(parents=True, exist_ok=True)
    (enemy_dir / "feature.yaml").write_text(
        "id: chase_movement\n"
        "provides:\n"
        "  - chase_behavior\n"
        "relations:\n"
        "  entity_roles:\n"
        "    - enemy\n",
        encoding="utf-8")
    # health：用于验证 hurt 槽位的 Feature 归因（damage_receiver）
    health_dir = root / "Features" / "health"
    health_dir.mkdir(parents=True, exist_ok=True)
    (health_dir / "feature.yaml").write_text(
        "id: health\n"
        "provides:\n"
        "  - damage_receiver\n"
        "  - health_state\n"
        "relations:\n"
        "  entity_roles:\n"
        "    - player\n"
        "    - enemy\n",
        encoding="utf-8")

    index = build_index(scan_project(root))
    index_file = root / ".ai" / "context" / "asset_index.json"
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print("--- Asset Compatibility ---")
    print()

    # ---- Test 4: player + player idle/run ----
    player_move = load_feature(root, "player_movement")
    idle_result = compatibility(index, find_asset(index, "player_idle"), player_move, "player")
    ok("Test 4: player + player_idle 不是 INCOMPATIBLE",
       idle_result["level"] != INCOMPATIBLE, idle_result["level"])
    run_result = compatibility(index, find_asset(index, "player_run"), player_move, "player")
    print("  player_movement + player_run -> %s" % run_result["level"])
    ok("Test 4: player_movement + player_run → COMPATIBLE",
       run_result["level"] == COMPATIBLE, run_result["level"])
    ok("Test 4: 给出能力命中理由",
       any("capability match" in reason for reason in run_result["reasons"]),
       str(run_result["reasons"]))

    # ---- Test 5a: 敌人资源配玩家 Feature -> INCOMPATIBLE ----
    enemy_asset = find_asset(index, "slime_attack_animation")
    conflict = compatibility(index, enemy_asset, player_move, "player")
    print("  player_movement + slime_attack_animation -> %s" % conflict["level"])
    ok("Test 5: player + 敌人资源 → INCOMPATIBLE", conflict["level"] == INCOMPATIBLE,
       conflict["level"])
    ok("Test 5: 说明角色冲突原因",
       any("role" in reason for reason in conflict["reasons"]), str(conflict["reasons"]))

    # ---- Test 5b: 能力不匹配的音频 -> WARNING（不是错误） ----
    audio_asset = find_asset(index, "slime_hurt_audio")
    warn = compatibility(index, audio_asset, player_move, "")
    print("  player_movement + slime_hurt_audio -> %s" % warn["level"])
    ok("Test 5: 不匹配音频 → WARNING", warn["level"] == WARNING, warn["level"])
    ok("Test 5: WARNING 不等于错误（等级可区分）", warn["level"] != INCOMPATIBLE)

    # ---- 无法判定的搭配 -> UNKNOWN（信息不足不假报兼容） ----
    tileset = find_asset(index, "ground_tileset")
    unknown = compatibility(index, tileset, player_move, "")
    print("  player_movement + ground_tileset -> %s" % unknown["level"])
    ok("tileset 无能力语义 → UNKNOWN", unknown["level"] == UNKNOWN, unknown["level"])

    # ---- 敌人特征 + 敌人资源 -> COMPATIBLE ----
    chase = load_feature(root, "chase_movement")
    enemy_ok = compatibility(index, find_asset(index, "slime_move"), chase, "enemy")
    print("  chase_movement + slime_move -> %s" % enemy_ok["level"])
    ok("chase_movement + slime_move → COMPATIBLE", enemy_ok["level"] == COMPATIBLE,
       enemy_ok["level"])
    ok("找不到的 asset → UNKNOWN",
       compatibility(index, None, chase, "enemy")["level"] == UNKNOWN)

    print()
    print("--- Asset Binding ---")
    print()

    # ---- 角色解析 ----
    entity = bind_assets.bind_entity(
        "slime_enemy", "enemy", ["chase_movement", "contact_damage", "health"],
        index, root)
    by_role = {entry["role"]: entry for entry in entity["bindings"]}
    print("  bindings: %s" % sorted(by_role))
    print("  missing:  %s" % [m["role"] for m in entity["missing"]])
    for role in ("idle", "move", "attack", "hurt"):
        ok("绑定: 必填角色 %s 已解析" % role, role in by_role)
        if role in by_role:
            entry = by_role[role]
            ok("绑定: %s 用 SpriteFrames 资源（%s）" % (role, entry["asset"]),
               entry["type"] == "sprite_frames", entry["type"])
            ok("绑定: %s 节点为 AnimatedSprite2D" % role,
               (entry.get("node") or {}).get("type") == "AnimatedSprite2D",
               str(entry.get("node")))
            # 四个角色共用同一个 SpriteFrames：合并为一个共享节点（不重复造节点）
            ok("绑定: %s 节点名语义化" % role,
               (entry.get("node") or {}).get("name") == "SlimeAnim",
               str((entry.get("node") or {}).get("name")))
            ok("绑定: %s confidence=high" % role, entry["confidence"] == "high",
               entry["confidence"])
    ok("绑定: 共享资源只生成一个节点（roles 记录完整）",
       by_role["idle"]["node"]["roles"] == ["idle", "move", "attack", "hurt"]
       and by_role["move"]["node"]["name"] == by_role["idle"]["node"]["name"],
       str(by_role["idle"]["node"]))
    ok("绑定: 共享 AnimatedSprite2D 记录主 animation=idle",
       by_role["idle"]["node"].get("animation") == "idle",
       str(by_role["idle"]["node"]))
    ok("绑定: 可选角色 hurt_sfx 也解析（AudioStreamPlayer）",
       by_role.get("hurt_sfx", {}).get("type") == "audio"
       and (by_role.get("hurt_sfx", {}).get("node") or {}).get("type") == "AudioStreamPlayer",
       str(by_role.get("hurt_sfx")))
    ok("绑定: 不存在的必填角色进入 missing（death 未声明则不算缺失）",
       all(item["kind"] == "required" for item in entity["missing"]))
    ok("绑定: 每个绑定都给出 compatibility 等级",
       all(entry.get("compatibility") in (COMPATIBLE, WARNING) for entry in entity["bindings"]))

    # 参与 health 的 hurt 槽位由 feature 归因
    ok("绑定: hurt 归因到 health（damage_receiver）",
       by_role.get("hurt", {}).get("feature") == "health",
       str(by_role.get("hurt", {}).get("feature")))

    # ---- 无 SpriteFrames 的动作：退化 + 注明 ----
    declared = {"subject": "slime", "required": ["death"]}
    death_entity = bind_assets.bind_entity("slime_enemy", "enemy", [], index, root,
                                           declared=declared)
    death_entry = (death_entity["bindings"] or [{}])[0]
    ok("退化: death 走 animation 组", death_entry.get("type") == "animation",
       str(death_entry.get("type")))
    ok("退化: 用首帧作为 Sprite2D texture",
       (death_entry.get("node") or {}).get("type") == "Sprite2D"
       and str((death_entry.get("node") or {}).get("path", "")).endswith("slime_death_00.png"),
       str(death_entry.get("node")))
    ok("退化: 明确注明原因（不假装是动画）", bool(death_entry.get("note")),
       str(death_entry.get("note")))
    ok("退化: confidence 仍为 high（资源真实存在且主体一致）",
       death_entry.get("confidence") == "high", str(death_entry.get("confidence")))

    # ---- 必填角色缺失（主体保护：不把别的角色资源当 bat 的资源） ----
    missing_entity = bind_assets.bind_entity(
        "bat", "enemy", [], index, root,
        declared={"subject": "bat", "required": ["idle", "move"]})
    missing_roles = {item["role"] for item in missing_entity["missing"]}
    ok("缺失: 主体不匹配时不强行绑定 → missing", missing_roles == {"idle", "move"},
       str(missing_roles))
    ok("缺失: 不编造 asset（bindings 为空）", missing_entity["bindings"] == [])
    ok("缺失: missing 说明最佳候选属于哪个主体",
       all("best candidate" in item["reason"] for item in missing_entity["missing"]),
       str([item["reason"] for item in missing_entity["missing"]]))
    blueprint = _write_entity_blueprint(root, "bat_blueprint.yaml", "bat", "enemy", ["idle"])
    ok("缺失: --strict 退出码 1",
       bind_assets.main(["--entity", str(blueprint), "--project", str(root), "--strict"]) == 1,
       str(bind_assets.main(["--entity", str(blueprint), "--project", str(root), "--strict"])))
    ok("缺失: 非 strict 退出码 0（缺失只报告，不阻断）",
       bind_assets.main(["--entity", str(blueprint), "--project", str(root),
                         "--out", str(root / "bat_binding.yaml")]) == 0)

    # ---- 显式绑定 ----
    explicit_file = root / "explicit.yaml"
    explicit_file.write_text("bindings:\n  - role: idle\n    asset: slime_move\n", encoding="utf-8")
    explicit_entity = bind_assets.bind_entity(
        "slime_enemy", "enemy", [], index, root,
        declared={"subject": "slime", "required": ["idle"]},
        explicit={"idle": "slime_move"})
    ok("显式绑定优先", (explicit_entity["bindings"][0] or {}).get("asset") == "slime_move",
       str(explicit_entity["bindings"][0].get("asset")))
    ok("显式绑定标记 resolved_from=binding",
       explicit_entity["bindings"][0].get("resolved_from") == "binding",
       str(explicit_entity["bindings"][0].get("resolved_from")))

    bad_entity = bind_assets.bind_entity(
        "slime_enemy", "enemy", [], index, root,
        declared={"subject": "slime", "required": ["idle"]},
        explicit={"idle": "not_a_real_asset"})
    ok("显式绑定引用未知 asset → missing（不静默忽略）",
       not any(entry["role"] == "idle" for entry in bad_entity["bindings"])
       and bad_entity["missing"][0]["kind"] == "required"
       and "unknown asset" in bad_entity["missing"][0]["reason"],
       str(bad_entity["missing"]))

    # ---- Gameplay Blueprint 绑定 ----
    gameplay = {
        "gameplay": {"id": "survival_game"},
        "entities": {
            "player": {"role": "player", "features": ["player_movement"]},
            "slime_enemy": {"role": "enemy", "features": ["chase_movement"],
                            "assets": {"subject": "slime", "required": ["idle", "move", "attack"]}},
        },
    }
    doc = bind_assets.bind_gameplay(gameplay, index, root)
    entities = doc["binding"]["entities"]
    ok("gameplay: 每个实体都有绑定块", len(entities) == 2)
    player_entity = next(e for e in entities if e["entity"] == "player")
    slime_entity = next(e for e in entities if e["entity"] == "slime_enemy")
    ok("gameplay: player 主语推断为 player",
       player_entity["bindings"] and str(player_entity["bindings"][0]["path"]).find("player") > 0,
       str(player_entity["bindings"][:1]))
    ok("gameplay: 显式声明 required 时角色集合完全由蓝图决定",
       sorted(entry["role"] for entry in slime_entity["bindings"]) == ["attack", "idle", "move"]
       and slime_entity.get("required_declared") is True,
       str([e["role"] for e in slime_entity["bindings"]]))
    ok("gameplay: 未声明 assets 的实体用默认槽位（含 *_sfx）",
       "hurt_sfx" in {entry["role"] for entry in player_entity["bindings"]},
       str([e["role"] for e in player_entity["bindings"]]))

    for temp in _temp_dirs:
        shutil.rmtree(temp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Asset Compatibility + Binding tests")
    return 0


def _write_entity_blueprint(root: Path, name: str, subject: str, role: str,
                            required: list) -> Path:
    """写一个采用显式 required 的 Entity Blueprint（用于 --strict 用例）。"""
    path = root / name
    lines = ["entity:", "  id: %s" % subject, "  role: %s" % role, "features: []",
             "assets:", "  subject: %s" % subject, "  required:"]
    lines += ["    - %s" % item for item in required]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    sys.exit(main())
