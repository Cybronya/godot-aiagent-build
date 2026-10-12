#!/usr/bin/env python3
"""Asset Query 回归测试（Test 3 + 确定性排序）。

覆盖：
    Test 3  "player idle" 能命中 player_idle
    附加    "enemy attack animation" 优先返回 enemy/attack 相关资源
    附加    --type / --category / --role / --subject 过滤
    附加    score ranking 确定性（同样输入结果顺序稳定）+ --explain 理由
    附加    无结果退出码 1；索引缺失退出码 2

用法:
    python .ai/tools/asset_registry/tests/test_asset_query.py
"""

from __future__ import annotations

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

import fixture_project                                                  # noqa: E402
import query_assets as query_tool                                       # noqa: E402
from asset_metadata import build_index, load_index, scan_project        # noqa: E402
from query_assets import query, score_asset                             # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def fixture_index() -> dict:
    temp = Path(tempfile.mkdtemp(prefix="asset_query_"))
    _temp_dirs.append(temp)
    fixture_project.build_project(temp)
    index = build_index(scan_project(temp))
    index_file = temp / ".ai" / "context" / "asset_index.json"
    index_file.parent.mkdir(parents=True, exist_ok=True)
    import json
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"root": temp, "index": index, "index_file": index_file}


def main() -> int:
    fixture = fixture_index()
    root = fixture["root"]
    index = fixture["index"]

    print("--- Asset Query ---")
    print("assets: %d" % len(index["assets"]))
    print()

    # ---- Test 3: "player idle" ----
    results = query(index, "player idle", limit=5)
    ok("Test 3: 'player idle' 有结果", bool(results))
    ids = [entry["id"] for entry in results]
    print("  'player idle' -> %s" % ids)
    ok("Test 3: 首选 player_idle", ids[:1] == ["player_idle"], str(ids))
    ok("Test 3: 返回结构含 path/type/tags/score",
       all(key in results[0] for key in ("path", "type", "tags", "score")))

    # ---- "enemy attack animation" ----
    results = query(index, "enemy attack animation", limit=5)
    ids = [entry["id"] for entry in results]
    print("  'enemy attack animation' -> %s" % ids)
    ok("enemy attack: 有结果", bool(ids))
    ok("enemy attack: 首选与 enemy/attack 相关",
       bool(ids) and "enemy" in str(results[0]["path"]).lower()
       and "attack" in str(results[0]["id"]).lower(), str(ids))
    ok("enemy attack: 不把 player 资源排在首位",
       bool(ids) and "player" not in ids[0], str(ids))
    ok("enemy attack: animation 类优先于同名 audio",
       bool(ids) and ids[0].endswith("animation") or (bool(ids) and "animation" in str(results[0]["type"])),
       str(ids))

    # ---- 过滤 ----
    audio = query(index, "hurt", types=["audio"])
    ok("--type audio: 只返回音频",
       bool(audio) and all(entry["type"] == "audio" for entry in audio),
       str([(e["id"], e["type"]) for e in audio]))
    ok("--type audio: 命中 slime_hurt_audio",
       any(entry["id"] == "slime_hurt_audio" for entry in audio), str([e["id"] for e in audio]))
    enemy_only = query(index, "slime animation", category="enemy")
    ok("--category enemy: 只返回敌人资源",
       bool(enemy_only) and all(entry["category"] == "enemy" for entry in enemy_only),
       str([(e["id"], e["category"]) for e in enemy_only]))
    by_role = query(index, "move", role="move")
    ok("--role move: 命中 slime_move",
       any(entry["id"] == "slime_move" for entry in by_role), str([e["id"] for e in by_role]))
    by_subject = query(index, "frames", subject="player")
    ok("--subject player: 命中 player_frames",
       any(entry["id"] == "player_frames" for entry in by_subject),
       str([e["id"] for e in by_subject]))

    # ---- 确定性 + 理由 ----
    first = query(index, "player run", explain=True)
    again = query(index, "player run", explain=True)
    ok("排序确定性: 两次查询结果完全相同", first == again)
    ok("--explain: 给出打分理由", bool(first) and bool(first[0].get("reasons")),
       str(first[0].get("reasons") if first else None))

    score_a, _ = score_asset(index["assets"][0], ["player"], "player")
    score_b, _ = score_asset(index["assets"][0], ["player"], "player")
    ok("打分函数幂等", score_a == score_b)

    # ---- CLI 退出码 ----
    argv_common = ["--project", str(root), "--index", str(fixture["index_file"])]
    ok("CLI: 命中退出码 0", query_tool.main(argv_common + ["player", "idle"]) == 0)
    ok("CLI: 无结果退出码 1",
       query_tool.main(argv_common + ["zzzz_nothing_matches"]) == 1)

    empty_root = Path(tempfile.mkdtemp(prefix="asset_query_empty_"))
    _temp_dirs.append(empty_root)
    ok("CLI: 无索引退出码 2", query_tool.main(["--project", str(empty_root), "player"]) == 2)

    for temp in _temp_dirs:
        shutil.rmtree(temp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Asset Query tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
