#!/usr/bin/env python3
"""Asset Query Agent API Tests —— Phase 1.7.9 任务 A。

    Test 1  旧 CLI 位置参数:  query_assets.py player          （兼容性不变）
    Test 2  具名 JSON 查询:   query_assets.py --json --query player
    Test 3  类型过滤:         --type animation
    Test 4  数量截断:         --limit 5

JSON 契约: .ai/context/asset_query_schema.yaml（query/count/results；count==len(results)）。
退出码: 0 = 全部通过；1 = 失败；2 = 环境（缺索引等）。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_TOOL_DOTAI = Path(__file__).resolve().parents[3]
_ASSET_DIR = _TOOL_DOTAI / "tools" / "asset_registry"
sys.path.insert(0, str(_ASSET_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import fixture_project                                         # noqa: E402
import build_asset_index as builder                            # noqa: E402
import query_assets                                            # noqa: E402
from asset_metadata import scan_project, build_index           # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def run(argv: list[str]) -> tuple[int, str]:
    """运行 query CLI 并捕获 stdout（不污染终端）。"""
    import io
    from contextlib import redirect_stdout
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = query_assets.main(argv)
    return code, buffer.getvalue()


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="query_api_"))
    _temp_dirs.append(root)
    fixture_project.build_project(root)
    index_file = root / ".ai" / "context" / "asset_index.json"
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(json.dumps(build_index(scan_project(root)),
                                     ensure_ascii=False, indent=2), encoding="utf-8")
    argv_base = ["--project", str(root), "--index", str(index_file)]

    print("--- Asset Query Agent API ---")
    print()

    # ---- Test 1: 旧 CLI 位置参数（命中 / 无结果 / 无索引三个退出码不变）----
    code, out = run(argv_base + ["player"])
    ok("Test 1: 位置参数退出码 0", code == 0, "%d\n%s" % (code, out[:100]))
    ok("Test 1: 位置参数仍是人类可读格式",
       "Asset Query: player" in out and "1. " in out, out[:120])
    code, out = run(argv_base + ["zzz_nothing"])
    ok("Test 1: 无命中退出码 1", code == 1, str(code))
    empty = Path(tempfile.mkdtemp(prefix="query_api_empty_"))
    _temp_dirs.append(empty)
    code, out = run(["--project", str(empty), "player"])
    ok("Test 1: 无索引退出码 2", code == 2, str(code))

    # ---- Test 2: 具名 --query + JSON 契约 ----
    code, out = run(argv_base + ["--json", "--query", "player idle animation"])
    payload = json.loads(out)
    ok("Test 2: --json --query 退出码 0", code == 0, out[:100])
    ok("Test 2: payload 三要素 query/count/results",
       payload.get("query") == "player idle animation"
       and isinstance(payload.get("count"), int)
       and isinstance(payload.get("results"), list), str(list(payload)))
    ok("Test 2: count == len(results)",
       payload["count"] == len(payload["results"]), str(payload["count"]))
    ok("Test 2: 首选 player_idle",
       payload["results"][0]["id"] == "player_idle",
       str([e["id"] for e in payload["results"][:3]]))
    ok("Test 2: 结果含 id/path/type/category/tags/score",
       all(all(key in entry for key in ("id", "path", "type", "category", "tags", "score"))
           for entry in payload["results"]), str(payload["results"][0].keys()))

    # ---- Test 3: --type 过滤 ----
    code, out = run(argv_base + ["--json", "--query", "slime attack", "--type", "animation"])
    payload = json.loads(out)
    ok("Test 3: --type animation 只返回动画",
       payload["results"] and all(entry["type"] == "animation" for entry in payload["results"]),
       str([(e["id"], e["type"]) for e in payload["results"]]))
    code, out = run(argv_base + ["--json", "--query", "hurt", "--type", "audio"])
    payload = json.loads(out)
    ok("Test 3: --type audio 命中音频结果",
       payload["results"] and all(entry["type"] == "audio" for entry in payload["results"]),
       str([e["id"] for e in payload["results"]]))

    # ---- Test 4: --limit 截断 ----
    code, out = run(argv_base + ["--json", "--query", "slime", "--limit", "2"])
    payload = json.loads(out)
    ok("Test 4: --limit 2 最多返回 2 条",
       len(payload["results"]) <= 2 and payload["count"] == len(payload["results"]),
       str(payload["count"]))
    unbounded_code, unbounded_out = run(argv_base + ["--json", "--query", "slime", "--limit", "0"])
    unbounded = json.loads(unbounded_out)
    ok("Test 4: --limit 0 = 不限制（条数 >= 截断组）",
       len(unbounded["results"]) >= len(payload["results"]),
       "%d vs %d" % (len(unbounded["results"]), len(payload["results"])))

    # ---- 稳定性与组合 ----
    code_a, out_a = run(argv_base + ["--json", "--query", "player", "--limit", "5"])
    code_b, out_b = run(argv_base + ["--json", "--query", "player", "--limit", "5"])
    ok("同输入同输出（确定性）", out_a == out_b)
    code, out = run(argv_base + ["--json", "--query", "slime", "--type", "animation",
                                 "--limit", "10"])
    payload = json.loads(out)
    ok("组合: --type + --limit 正常",
       code == 0 and payload["results"] and len(payload["results"]) <= 10,
       str([e["id"] for e in payload["results"][:5]]))
    code, out = run(argv_base + ["--json", "--query", "player", "--category", "player"])
    payload = json.loads(out)
    ok("--category 过滤生效",
       payload["results"] and all(entry["category"] == "player" for entry in payload["results"]),
       str({e["category"] for e in payload["results"]}))

    for temp in _temp_dirs:
        shutil.rmtree(temp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Asset Query Agent API tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
