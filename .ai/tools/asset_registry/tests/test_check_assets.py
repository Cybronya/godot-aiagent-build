#!/usr/bin/env python3
"""Asset Validation 阶段回归测试（validator/check_assets.py，只 CHECK / REPORT）。

覆盖：
    PASS   路径存在、类型一致、索引同步、绑定有效、场景引用有效
    ERROR  资源路径不存在（场景引用缺失资源）
    ERROR  索引缺失或陈旧
    ERROR  绑定引用未知 asset / 资源节点路径不存在
    ERROR  蓝图显式声明的必填角色缺失（required_declared=true）
    WARNING 推断出来的角色缺失（required_declared=false）
    WARNING 低兼容性绑定（compatibility=WARNING）/ 未导入资源（无 .import）
    只读   校验前后项目文件完全不变（Validator 不修改项目）

用法:
    python .ai/tools/asset_registry/tests/test_check_assets.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REGISTRY_DIR = TEST_DIR.parent
DOTAI_DIR = REGISTRY_DIR.parents[1]
VALIDATOR_DIR = DOTAI_DIR / "tools" / "validator"

if str(REGISTRY_DIR) not in sys.path:
    sys.path.insert(0, str(REGISTRY_DIR))
if str(VALIDATOR_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATOR_DIR))
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

import fixture_project                                                 # noqa: E402
from asset_metadata import build_index, scan_project                   # noqa: E402
from check_assets import check_assets                                  # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def write_index(root: Path) -> Path:
    index_file = root / ".ai" / "context" / "asset_index.json"
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(
        json.dumps(build_index(scan_project(root)), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return index_file


def write_binding(root: Path, name: str, text: str) -> Path:
    target = root / ".ai" / "context" / "asset_bindings" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def new_project(prefix: str) -> Path:
    temp = Path(tempfile.mkdtemp(prefix=prefix))
    _temp_dirs.append(temp)
    fixture_project.build_project(temp)
    return temp


def main() -> int:
    print("--- Asset Validation stage ---")
    print()

    # ---- PASS：干净项目 ----
    clean = new_project("asset_check_ok_")
    write_index(clean)
    scene_dir = clean / "Scenes"
    (scene_dir / "Player.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n\n'
        '[ext_resource type="Texture2D" path="res://Assets/characters/player/idle/player_idle_00.png" id="1_a"]\n\n'
        '[node name="Player" type="CharacterBody2D"]\n\n'
        '[node name="Sprite" type="Sprite2D" parent="."]\n'
        'texture = ExtResource("1_a")\n',
        encoding="utf-8")
    result = check_assets(clean)
    print("clean: checked=%s failures=%d warnings=%d"
          % (result["checked"], len(result["failures"]), len(result["warnings"])))
    ok("PASS: 干净项目零错误", result["failures"] == [], str(result["failures"]))

    # ---- 只读：校验前后项目不变 ----
    before = tree_digest(clean)
    check_assets(clean)
    ok("只读: 校验不修改项目（文件摘要一致）", tree_digest(clean) == before)

    # ---- ERROR：场景引用缺失资源 ----
    broken = new_project("asset_check_scene_")
    write_index(broken)
    (broken / "Scenes" / "Broken.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n\n'
        '[ext_resource type="Texture2D" path="res://Assets/player_missing.png" id="1_a"]\n\n'
        '[node name="Broken" type="Node2D"]\n',
        encoding="utf-8")
    result = check_assets(broken)
    ok("ERROR: 场景引用缺失资源",
       any("references a missing resource" in f and "player_missing.png" in f
           for f in result["failures"]), str(result["failures"]))

    # ---- ERROR：未索引资源（索引陈旧）----
    stale = new_project("asset_check_stale_")
    write_index(stale)
    fixture_project.write_png(stale / "Assets" / "ui" / "icons" / "extra_icon.png", 8, 8)
    result = check_assets(stale)
    ok("ERROR: 索引未同步（新增资源未索引）",
       any("stale" in f for f in result["failures"]), str(result["failures"]))

    missing_index = new_project("asset_check_noindex_")
    result = check_assets(missing_index)
    ok("ERROR: 索引缺失",
       any("index missing or empty" in f for f in result["failures"]), str(result["failures"]))

    # ---- ERROR/WARNING：绑定 ----
    bind_root = new_project("asset_check_bind_")
    write_index(bind_root)

    # 有效绑定 -> 无错误
    write_binding(bind_root, "slime_ok.yaml",
                  "binding:\n"
                  "  source: entity_blueprint\n"
                  "  entity: slime_enemy\n"
                  "  role: enemy\n"
                  "  required_declared: true\n"
                  "  bindings:\n"
                  "    - role: idle\n"
                  "      asset: slime_frames\n"
                  "      type: sprite_frames\n"
                  "      compatibility: COMPATIBLE\n"
                  "      node:\n"
                  "        name: SlimeIdleAnim\n"
                  "        type: AnimatedSprite2D\n"
                  "        property: sprite_frames\n"
                  "        path: res://Assets/characters/enemy/slime/slime_frames.tres\n"
                  "  missing: []\n")
    result = check_assets(bind_root)
    ok("绑定: 有效绑定无错误", result["failures"] == [], str(result["failures"]))

    # 未知 asset -> ERROR
    write_binding(bind_root, "unknown.yaml",
                  "binding:\n"
                  "  entity: x\n"
                  "  bindings:\n"
                  "    - role: idle\n"
                  "      asset: does_not_exist\n"
                  "      node:\n"
                  "        name: N\n"
                  "        type: Sprite2D\n"
                  "        path: res://Assets/nope.png\n")
    result = check_assets(bind_root)
    ok("绑定: 引用未知 asset → ERROR",
       any("unknown asset" in f for f in result["failures"]), str(result["failures"]))

    # 资源节点路径不存在 -> ERROR
    write_binding(bind_root, "baddisk.yaml",
                  "binding:\n"
                  "  entity: x\n"
                  "  bindings:\n"
                  "    - role: idle\n"
                  "      asset: slime_frames\n"
                  "      node:\n"
                  "        name: N\n"
                  "        type: AnimatedSprite2D\n"
                  "        path: res://Assets/characters/enemy/slime/gone.tres\n")
    result = check_assets(bind_root)
    ok("绑定: 资源节点路径不存在 → ERROR",
       any("resource missing on disk" in f for f in result["failures"]), str(result["failures"]))

    # 显式声明的必填角色缺失 -> ERROR；推断的角色缺失 -> WARNING
    for name, declared, expected in (("req.yaml", "true", "failure"),
                                     ("infer.yaml", "false", "warning")):
        write_binding(bind_root, name,
                      "binding:\n"
                      "  entity: bat\n"
                      "  role: enemy\n"
                      "  required_declared: %s\n"
                      "  bindings: []\n"
                      "  missing:\n"
                      "    - role: idle\n"
                      "      kind: required\n"
                      "      reason: no asset for subject 'bat' and role 'idle'\n" % declared)
        result = check_assets(bind_root)
        if expected == "failure":
            ok("绑定: 显式 required 缺失 → ERROR",
               any("Missing required asset binding" in f for f in result["failures"]),
               str(result["failures"]))
        else:
            ok("绑定: 推断角色缺失 → WARNING（不阻断）",
               any("Missing inferred asset binding" in w for w in result["warnings"]),
               str(result["warnings"]))
        (bind_root / ".ai" / "context" / "asset_bindings" / name).unlink()

    # 低兼容性 -> WARNING
    write_binding(bind_root, "warn.yaml",
                  "binding:\n"
                  "  entity: slime_enemy\n"
                  "  bindings:\n"
                  "    - role: idle\n"
                  "      asset: slime_frames\n"
                  "      compatibility: WARNING\n"
                  "      node:\n"
                  "        name: N\n"
                  "        type: AnimatedSprite2D\n"
                  "        path: res://Assets/characters/enemy/slime/slime_frames.tres\n")
    result = check_assets(bind_root)
    ok("绑定: 低兼容性 → WARNING",
       any("compatibility is WARNING" in w for w in result["warnings"]), str(result["warnings"]))
    (bind_root / ".ai" / "context" / "asset_bindings" / "warn.yaml").unlink()
    (bind_root / ".ai" / "context" / "asset_bindings" / "unknown.yaml").unlink()
    (bind_root / ".ai" / "context" / "asset_bindings" / "baddisk.yaml").unlink()

    # ---- 未导入资源 -> WARNING ----
    result = check_assets(bind_root)
    ok("WARNING: 未导入资源（缺 .import）",
       any("not imported by Godot" in w for w in result["warnings"]), str(result["warnings"]))
    (bind_root / "Assets" / "ui" / "icons" / "health_icon.png.import").write_text(
        "[remap]\n", encoding="utf-8")
    result = check_assets(bind_root)
    ok("WARNING 可被 .import 消除（该资源不再告警）",
       not any("health_icon.png" in w for w in result["warnings"]), str(result["warnings"]))

    # ---- 无资源目录：可选层，不报错 ----
    empty = Path(tempfile.mkdtemp(prefix="asset_check_empty_"))
    _temp_dirs.append(empty)
    result = check_assets(empty)
    ok("可选层: 无资源根目录时 checked=0 且零错误",
       result["checked"] == 0 and result["failures"] == [], json.dumps(result, ensure_ascii=False))
    ok("可选层: 给出 note 说明不适用", bool(result.get("note")), str(result.get("note")))

    # ---- manifest 悬空路径 -> WARNING ----
    manifest_root = new_project("asset_check_manifest_")
    write_index(manifest_root)
    (manifest_root / ".ai" / "context" / "asset_manifest.yaml").write_text(
        "assets:\n"
        "  - id: ghost\n"
        "    path: res://Assets/audio/ghost/ghost_hurt.wav\n"
        "    category: audio\n"
        "    confirmed: true\n",
        encoding="utf-8")
    result = check_assets(manifest_root)
    ok("manifest: 悬空路径 → WARNING",
       any("points to a missing path" in w for w in result["warnings"]), str(result["warnings"]))
    ok("manifest: 悬空路径不升为 ERROR", result["failures"] == [], str(result["failures"]))

    for temp in _temp_dirs:
        shutil.rmtree(temp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Asset Validation stage tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
