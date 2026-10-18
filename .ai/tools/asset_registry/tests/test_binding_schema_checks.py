#!/usr/bin/env python3
"""Binding Schema Checker 回归测试（Phase 1.17）。

覆盖（任务 D：check_binding_schema.py 增强）：
    S1  合法输出文档通过（records 计数 + 旧格式 role-level 记录兼容）
    S2  schema_version 缺失 / 非整数 / 不支持版本仍被拒绝（既有契约）
    S3  记录缺 role/asset 或为非字符串 → invalid_record 类违规
    S4  entity-scoped 记录 entity 为空/非字符串 → invalid_entity_scope
    S5  --gameplay：未知实体 → unknown_entity_scope（与 bind_assets
        binding_scope_errors 语义一致）；已知实体 → 通过
    S6  未给 --gameplay → note（信息不足），不产生违规也不推断结论
    S7  binding_scope_errors 契约字段缺失 → incomplete_binding_scope_error
    S8  CLI 兼容：默认调用方式 exit 0；--gameplay 未知实体 exit 1；
        蓝图缺失 exit 2
    S9  蓝图无 entities 映射 → note（不误判）

用法:
    python .ai/tools/asset_registry/tests/test_binding_schema_checks.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

TEST_DIR = Path(__file__).resolve().parent
REGISTRY_DIR = TEST_DIR.parent
TOOLS_DIR = REGISTRY_DIR.parent
PROJECT_ROOT = TOOLS_DIR.parent
CHECKER = REGISTRY_DIR / "check_binding_schema.py"

_failures: list[str] = []
_checks = 0


def ok(name: str, condition, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        message = "FAIL: %s" % name
        if detail:
            message += " | %s" % detail
        print(message)
        _failures.append(message)


def _write_doc(directory: Path, name: str, doc) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")
    return path


def _output_doc(entity: str = "enemy", records=None) -> dict:
    return {
        "schema_version": 2,
        "binding": {"source": "gameplay_blueprint", "gameplay": "demo",
                    "entities": [{"entity": entity,
                                  "bindings": records if records is not None else [
                                      {"role": "idle", "asset": "slime_idle"},
                                      {"entity": entity, "role": "move",
                                       "asset": "slime_move"},
                                  ]}]},
    }


def _run_checker(*args, cwd: str = str(PROJECT_ROOT)):
    return subprocess.run([sys.executable, str(CHECKER), *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=cwd)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="binding_schema_checks_"))
    try:
        # ---- S1: 合法输出文档 + 旧格式兼容 ----
        good = _write_doc(work / "good", "binding.yaml",
                          _output_doc(records=[{"role": "idle", "asset": "slime_idle"},
                                               {"entity": "enemy", "role": "move",
                                                "asset": "slime_move"}]))
        result = json.loads(_run_checker("--bindings-dir", str(good.parent), "--json").stdout)
        ok("S1: a valid output doc with legacy + scoped records passes",
           result["checked"] == 1 and not result["violations"]
           and result["entries"][0]["records"] == 2, repr(result))

        # ---- S2: 既有版本契约仍然生效 ----
        missing = _write_doc(work / "missing", "binding.yaml",
                             {"binding": {"entities": []}})
        result = json.loads(_run_checker("--bindings-dir", str(missing.parent),
                                         "--json").stdout)
        ok("S2: missing schema_version is still an error",
           any(v["kind"] == "missing_schema_version" for v in result["violations"]),
           repr(result["violations"]))
        badver = _write_doc(work / "badver", "binding.yaml",
                            {"schema_version": 99, "binding": {"entities": []}})
        result = json.loads(_run_checker("--bindings-dir", str(badver.parent),
                                         "--json").stdout)
        ok("S2: unsupported schema_version is still an error",
           any(v["kind"] == "unsupported_schema_version" for v in result["violations"]),
           repr(result["violations"]))

        # ---- S3: 记录缺 role/asset ----
        incomplete = _write_doc(work / "incomplete", "binding.yaml", _output_doc(
            records=[{"role": "", "asset": "slime_idle"},
                     {"role": "move"},
                     {"role": "attack", "asset": 7},
                     "not-a-mapping"]))
        result = json.loads(_run_checker("--bindings-dir", str(incomplete.parent),
                                         "--json").stdout)
        kinds = {v["kind"] for v in result["violations"]}
        ok("S3: empty/missing/non-string role and asset are reported",
           {"invalid_role", "invalid_asset", "invalid_record"} <= kinds
           and len(result["violations"]) >= 4, repr(result["violations"]))

        # ---- S4: entity 字段非法 ----
        badentity = _write_doc(work / "badentity", "binding.yaml", _output_doc(
            records=[{"entity": "  ", "role": "idle", "asset": "slime_idle"},
                     {"entity": 3, "role": "move", "asset": "slime_move"}]))
        result = json.loads(_run_checker("--bindings-dir", str(badentity.parent),
                                         "--json").stdout)
        ok("S4: empty or non-string entity scopes are rejected",
           all(v["kind"] == "invalid_entity_scope" for v in result["violations"])
           and len(result["violations"]) == 2, repr(result["violations"]))

        # ---- S5: --gameplay 实体存在性检查 ----
        blueprint = _write_doc(work, "gameplay.yaml", {
            "gameplay": {"id": "demo"},
            "entities": {"enemy": {"role": "enemy", "features": ["health"]}},
        })
        unknown = _write_doc(work / "unknown", "binding.yaml", _output_doc(
            records=[{"entity": "ghost", "role": "idle", "asset": "slime_idle"}]))
        result = json.loads(_run_checker("--bindings-dir", str(unknown.parent),
                                         "--gameplay", str(blueprint), "--json").stdout)
        ok("S5: an unknown entity scope fails with the same semantics as bind_assets",
           any(v["kind"] == "unknown_entity_scope" and "ghost" in v["detail"]
               and "binding_scope_errors" in v["detail"]
               for v in result["violations"]), repr(result["violations"]))
        known = _write_doc(work / "known", "binding.yaml", _output_doc())
        result = json.loads(_run_checker("--bindings-dir", str(known.parent),
                                         "--gameplay", str(blueprint), "--json").stdout)
        ok("S5: a scoped binding to a declared entity passes with --gameplay",
           not result["violations"] and not result["notes"], repr(result))

        # ---- S6: 无 --gameplay = 信息不足，不是错误 ----
        scoped_only = _write_doc(work / "scoped_only", "binding.yaml", _output_doc())
        result = json.loads(_run_checker("--bindings-dir", str(scoped_only.parent),
                                         "--json").stdout)
        ok("S6: without --gameplay the checker reports insufficient information, "
           "no violation and no verdict",
           not result["violations"]
           and any("information insufficient" in note for note in result["notes"]),
           repr(result["notes"]))

        # ---- S7: binding_scope_errors 契约字段 ----
        broken_errors = _write_doc(work / "scope_errors", "binding.yaml", {
            "schema_version": 2,
            "binding": {"entities": [],
                        "binding_scope_errors": [
                            {"entity": "ghost", "role": "idle",
                             "location": "<binding>:entity=ghost", "reason": "unknown"},
                            {"entity": "ghost2"},
                        ]}})
        result = json.loads(_run_checker("--bindings-dir", str(broken_errors.parent),
                                         "--json").stdout)
        ok("S7: scope-error entries missing contract keys are flagged",
           any(v["kind"] == "incomplete_binding_scope_error" and "ghost2" not in ""
               for v in result["violations"])
           and any("role, location, reason" in (v.get("detail") or "")
                   for v in result["violations"]), repr(result["violations"]))

        # ---- S8: CLI 兼容 ----
        r = _run_checker("--bindings-dir", str(good.parent))
        ok("S8: CLI exit 0 on a valid directory", r.returncode == 0, r.stderr[-200:])
        r = _run_checker("--bindings-dir", str(unknown.parent),
                         "--gameplay", str(blueprint))
        ok("S8: CLI exit 1 with unknown entity scope", r.returncode == 1
           and "unknown_entity_scope" in r.stdout, r.stdout[-200:])
        r = _run_checker("--bindings-dir", str(good.parent),
                         "--gameplay", str(work / "no_such_blueprint.yaml"))
        ok("S8: CLI exit 2 when the blueprint is missing", r.returncode == 2,
           (r.stderr or "")[-200:])

        # ---- S9: 蓝图缺 entities → note，不误判 ----
        empty_bp = _write_doc(work, "empty_bp.yaml", {"gameplay": {"id": "empty"}})
        result = json.loads(_run_checker("--bindings-dir", str(scoped_only.parent),
                                         "--gameplay", str(empty_bp), "--json").stdout)
        ok("S9: a blueprint without usable entities yields a note, not a violation",
           not result["violations"]
           and any("information insufficient" in note for note in result["notes"]),
           repr((result["violations"], result["notes"])))
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)

    print()
    if _failures:
        print("FAILED (%d):" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all %d checks" % _checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
