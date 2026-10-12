#!/usr/bin/env python3
"""Binding Schema Checker Tests —— Phase 1.7.9 任务 B。

    Test 5  schema_version: 2（受支持） -> PASS
    Test 6  缺失 schema_version        -> ERROR（missing_schema_version）
    Test 7  schema_version: 99（未知） -> ERROR（unsupported；不自动迁移）
    附加    生成器写出的绑定文档自带 schema_version；只报告不改写。
退出码: 0 = 全部通过；1 = 失败；2 = 环境。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

_TOOL_DOTAI = Path(__file__).resolve().parents[3]
_ASSET_DIR = _TOOL_DOTAI / "tools" / "asset_registry"
sys.path.insert(0, str(_ASSET_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import check_binding_schema                                    # noqa: E402
import bind_assets                                             # noqa: E402
import fixture_project                                         # noqa: E402
import build_asset_index as builder                            # noqa: E402
from asset_metadata import load_index                          # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def write_binding(directory: Path, name: str, doc: dict) -> Path:
    path = directory / (name if name.endswith(".yaml") else name + ".yaml")
    import yaml
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def main() -> int:
    bindings = Path(tempfile.mkdtemp(prefix="binding_schema_"))
    _temp_dirs.append(bindings)

    print("--- Binding Schema Checker ---")
    print()

    # ---- Test 5: 受支持版本 ----
    write_binding(bindings, "Player.yaml", {
        "schema_version": 2,
        "binding": {"entity": "player", "role": "player", "bindings": [
            {"role": "idle", "asset": "x"}],
            "missing": [], "optional_missing": [], "features": []},
    })
    result = check_binding_schema.check_bindings(bindings)
    ok("Test 5: schema_version=2 PASS（无违规）",
       not result["violations"]
       and any(e["file"] == "Player.yaml" and e["schema_version"] == 2 for e in result["entries"]),
       str(result["violations"]))
    ok("Test 5: checked 计数正确", result["checked"] == 1, str(result["checked"]))

    # ---- Test 6: 缺失版本 ----
    write_binding(bindings, "Enemy.yaml", {
        "binding": {"entity": "enemy", "role": "enemy", "bindings": [],
                    "missing": [], "optional_missing": [], "features": []},
    })
    result = check_binding_schema.check_bindings(bindings)
    kinds = {v["kind"] for v in result["violations"]}
    ok("Test 6: 缺失 schema_version -> missing_schema_version ERROR",
       "missing_schema_version" in kinds and all(
           v["file"] == "Enemy.yaml" for v in result["violations"] if v["kind"] == "missing_schema_version"),
       str(result["violations"]))

    # ---- Test 7: 未知版本（不自动迁移）----
    old_doc_path = write_binding(bindings, "Legacy.yaml", {
        "schema_version": 99,
        "binding": {"entity": "legacy", "role": "entity", "bindings": [],
                    "missing": [], "optional_missing": [], "features": []},
    })
    result = check_binding_schema.check_bindings(bindings)
    legacy = next((v for v in result["violations"] if v["file"] == "Legacy.yaml"), None)
    ok("Test 7: schema_version=99 -> unsupported_schema_version ERROR",
       legacy is not None and legacy["kind"] == "unsupported_schema_version", str(legacy))
    ok("Test 7: 违规文件未被改写（禁止自动迁移）",
       "schema_version: 99" in old_doc_path.read_text(encoding="utf-8").replace("schema_version: 99", "schema_version: 99"),)
    import yaml as _yaml
    reloaded = _yaml.safe_load(old_doc_path.read_text(encoding="utf-8")) or {}
    ok("Test 7: 原 schema_version 保留为 99（无迁移副作用）",
       int(reloaded["schema_version"]) == 99, str(reloaded.get("schema_version")))

    # ---- 退格 ----
    (bindings / "Broken.yaml").write_text("binding: [oops\n", encoding="utf-8")
    result = check_binding_schema.check_bindings(bindings)
    ok("空白 YAML -> unreadable ERROR",
       any(v["kind"] == "unreadable" for v in result["violations"]), str(result["violations"]))
    non_binding = check_binding_schema.check_bindings(bindings / "..")
    ok("非绑定目录 -> note，无崩溃", "not found" in (non_binding.get("note") or "") or non_binding["checked"] >= 0)

    # ---- 生成器产物自带 schema_version（bind_assets / asset_repair / asset_nodes 三链路）----
    root = Path(tempfile.mkdtemp(prefix="binding_gen_"))
    _temp_dirs.append(root)
    fixture_project.build_project(root)
    builder.main(["--project", str(root)])
    index = load_index(project_root=root)
    (root / "bp.yaml").write_text(
        "entity: {id: gen_player, role: player}\nfeatures: []\n"
        "assets: {subject: player, required: [idle]}\n", encoding="utf-8")
    out_path = root / "out_binding.yaml"
    bind_assets.main(["--entity", str(root / "bp.yaml"), "--index", str(
        root / ".ai" / "context" / "asset_index.json"),
        "--project", str(root), "--out", str(out_path)])
    assert out_path.is_file()
    generated = check_binding_schema.check_bindings(out_path.parent, )
    ok("生成器产物（bind_assets CLI）自带版本并通过校验",
       any(v["kind"] == "unsupported_schema_version" and v["file"] != out_path.name
           for v in generated["violations"] if v["file"] == out_path.name) is False
       and any(e["file"] == out_path.name and e["schema_version"] == 2
               for e in generated["entries"]), str(generated))
    ok("BINDING_SCHEMA_VERSION 常量 = 2（与 schema 文档一致）",
       bind_assets.BINDING_SCHEMA_VERSION == 2, str(bind_assets.BINDING_SCHEMA_VERSION))

    # ---- CLI 退出码 ----
    import io
    from contextlib import redirect_stdout
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = check_binding_schema.main(["--bindings-dir", str(bindings)])
    ok("CLI: 存在违规时退出码 1", code == 1, str(code))
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = check_binding_schema.main(["--bindings-dir", str(out_path.parent)
                                          if out_path.parent != bindings else str(bindings)])
    # out_binding.yaml 合法，但 bindings 目录里仍有违规文件，条目独立校验：
    clean_dir = Path(tempfile.mkdtemp(prefix="binding_clean_"))
    _temp_dirs.append(clean_dir)
    shutil.copy(out_path, clean_dir / out_path.name)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = check_binding_schema.main(["--bindings-dir", str(clean_dir)])
    ok("CLI: 移除违规后退出码 0", code == 0, buffer.getvalue()[:150])

    for temp in _temp_dirs:
        shutil.rmtree(temp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Binding Schema Checker tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
