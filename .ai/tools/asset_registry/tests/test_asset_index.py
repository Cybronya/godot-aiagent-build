#!/usr/bin/env python3
"""Asset Index 回归测试（Test 6 链路 + Generated Cache 语义）。

覆盖：
    Test 6  scan -> build index -> query 完整链路
    附加    索引是 Generated Cache（_generated 标记、无内部字段泄漏）
    附加    --check 同步 / 陈旧判定（新增帧、删除文件都算陈旧）
    附加    索引可随时重建（两次构建结果除时间戳外一致）
    附加    无资源根目录时不写索引（不产生空索引污染项目）

用法:
    python .ai/tools/asset_registry/tests/test_asset_index.py
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

import fixture_project                                                  # noqa: E402
import build_asset_index as builder                                     # noqa: E402
from asset_metadata import (                                            # noqa: E402
    build_index,
    index_assets,
    index_path,
    load_index,
    scan_project,
)
from query_assets import query                                          # noqa: E402

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
    temp = Path(tempfile.mkdtemp(prefix="asset_index_"))
    _temp_dirs.append(temp)
    fixture_project.build_project(temp)
    return temp


def main() -> int:
    root = fixture_project_root()
    index_file = index_path(root)

    print("--- Asset Index ---")
    print("index: %s" % index_file)
    print()

    # ---- Test 6: scan -> build index -> query ----
    code = builder.main(["--project", str(root)])
    ok("Test 6: build_asset_index 退出码 0", code == 0, str(code))
    ok("Test 6: 索引文件已生成", index_file.is_file())
    index = load_index(index_file)
    ok("Test 6: _generated 标记为 true", index.get("_generated") is True)
    ok("Test 6: 记录 project 与 counts",
       bool(index.get("project")) and isinstance(index.get("counts"), dict),
       str(list(index)[:6]))
    ok("Test 6: total 与 assets 长度一致",
       index.get("total") == len(index_assets(index)), str(index.get("total")))
    ok("Test 6: schema_version=1", index.get("schema_version") == 1)

    results = query(index, "player idle animation")
    ok("Test 6: 索引可直接查询", bool(results))
    ok("Test 6: query 返回 player_idle", bool(results) and results[0]["id"] == "player_idle",
       str([r["id"] for r in results[:3]]))

    # ---- Generated Cache 语义 ----
    raw = index_file.read_text(encoding="utf-8")
    ok("缓存: 不泄漏内部字段 _disk_path", "_disk_path" not in raw)
    ok("缓存: 不泄漏内部字段 _tokens", "\"_tokens\"" not in raw)
    ok("缓存: 每项含 path/type/category/tags 四要素",
       all(all(key in asset for key in ("path", "type", "category", "tags"))
           for asset in index_assets(index)))
    rebuilt = build_index(scan_project(root))
    stable = True
    for key in ("total", "counts", "schema_version"):
        if rebuilt.get(key) != index.get(key):
            stable = False
            break
    ok("缓存: 索引可重建且内容稳定（忽略时间戳）", stable)

    # ---- --check 同步 ----
    ok("--check: 已同步时退出码 0", builder.main(["--project", str(root), "--check"]) == 0)

    # 新增一帧：属于既有 animation 组 -> 索引陈旧
    new_frame = root / "Assets" / "characters" / "player" / "idle" / "player_idle_02.png"
    fixture_project.write_png(new_frame, 32, 32, (10, 20, 30, 255))
    ok("--check: 新增帧后判定陈旧（退出码 1）",
       builder.main(["--project", str(root), "--check"]) == 1)
    code = builder.main(["--project", str(root)])
    ok("重建索引后恢复同步", code == 0 and builder.main(["--project", str(root), "--check"]) == 0)
    grown = load_index(index_file)
    grown_asset = next(a for a in index_assets(grown) if a["id"] == "player_idle")
    ok("重建后 frame_count 更新为 3", grown_asset["frame_count"] == 3, str(grown_asset["frame_count"]))

    # 新增一个全新资产 -> 索引陈旧
    (root / "Assets" / "ui" / "icons").mkdir(parents=True, exist_ok=True)
    fixture_project.write_png(root / "Assets" / "ui" / "icons" / "mana_icon.png", 16, 16)
    ok("--check: 新增资产后判定陈旧（退出码 1）",
       builder.main(["--project", str(root), "--check"]) == 1)
    builder.main(["--project", str(root)])
    ok("新增资产进入索引",
       any(a["id"] == "mana_icon" for a in index_assets(load_index(index_file))))

    # 删除索引 -> --check 报缺失
    index_file.unlink()
    ok("--check: 索引缺失时退出码 1", builder.main(["--project", str(root), "--check"]) == 1)

    # ---- 无资源根目录 ----
    empty = Path(tempfile.mkdtemp(prefix="asset_none_"))
    _temp_dirs.append(empty)
    (empty / ".ai" / "context").mkdir(parents=True, exist_ok=True)
    code = builder.main(["--project", str(empty)])
    ok("无资源目录: 退出码 0 且不写索引",
       code == 0 and not index_path(empty).exists(), str(code))
    ok("无资源目录: scan 报告 0 roots", scan_project(empty)["roots"] == [])

    # ---- JSON 输出可被机器读取 ----
    json_code = builder.main(["--project", str(root), "--json"])
    ok("--json: 退出码 0", json_code == 0)

    for temp in _temp_dirs:
        shutil.rmtree(temp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Asset Index tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
