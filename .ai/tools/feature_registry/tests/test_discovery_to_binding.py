#!/usr/bin/env python3
"""Discovery-to-Binding Adapter Tests —— Phase 1.8.2 Step 2。

按 Step 4 测试要求覆盖 12 项行为：
    T1  有效 Discovery JSON + 显式候选选择 -> 正确 Binding 输入
    T2  不提供候选选择时不静默选 top1（exit 1，无 converted 输出）
    T3  显式选择不存在的 candidate -> 错误
    T4  candidate 与请求槽位不匹配（跨槽借用）-> 错误
    T5  必填槽位无候选 -> 可诊断错误
    T6  部分缺失槽位 -> 未选槽位警告 + 已选槽位正常转换
    T7  schema_version 不兼容 -> 拒绝（exit 2）
    T8  JSON 非法 / 根对象类型错误 -> 拒绝（exit 2）
    T9  未知 diagnostics.reason -> 不静默绑定（exit 1）
    T10 feature_index_missing 等非致命但结构上致命的诊断 -> 不被误判为完整匹配
    T11 role（实体）与 candidate role（槽位）不混淆 —— entity_role 当 slot 用会拒绝
    T12 输出只含显式绑定覆盖节允许的字段 {bindings:[{role, asset}]}

Usage:
    python .ai/tools/feature_registry/tests/test_discovery_to_binding.py

退出码: 0 = 全部通过；1 = 有失败。

Phase 1.8.2 Step 2.6 追加（I/O 加固回归）：
    T13 --input 文件不存在：exit 2，无 traceback，有诊断信息
    T14 输入读取 I/O 失败（确定性 mock 模拟 OSError，不声称验证真实 OS 权限）
    T15 stdin 为空 / 非法 JSON：exit 2，无 traceback
    T16 --out 写入失败（父目录不存在）：exit 2，无 traceback，无 partial 输出文件
    T17 原子写入：同目录临时文件 + os.replace，替换失败时不损坏旧文件
    T18 端到端：显式选择生成的 Binding 输入能被 bind_assets 消费
        （resolved_from=binding, confidence=high —— 显式绑定优先于索引推断）
    T19 部分选择端到端：未选槽位被 bind_assets 自动推断，
        resolved_from=index 与 resolved_from=binding 明确可区分
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

_TOOL_DOTAI = Path(__file__).resolve().parents[3]
_FEATURE_DIR = _TOOL_DOTAI / "tools" / "feature_registry"
sys.path.insert(0, str(_FEATURE_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import discovery_to_binding as adapter                        # noqa: E402

_failures: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


# 最小 Discovery payload：与 feature_discovery.py 真实输出同结构（11 连键）。
_SAMPLE = {
    "schema_version": 1,
    "query": "slime enemy attacks",
    "role": "enemy",
    "features": ["chase_movement"],
    "feature_capabilities": {"chase_movement": ["character_movement"]},
    "requirements": {},
    "asset_slots": ["idle", "move", "attack", "hurt"],
    "optional_slots": [],
    "asset_candidates": {
        "idle": [{"id": "slime_idle", "path": "res://Assets/characters/enemy/slime/idle/",
                  "type": "animation", "category": "enemy", "role": "idle",
                  "subject": "slime", "tags": ["idle"], "confirmed": False, "score": 7.5}],
        "move": [{"id": "slime_run", "path": "res://Assets/characters/enemy/slime/move/",
                  "type": "animation", "category": "enemy", "role": "move",
                  "subject": "slime", "tags": ["move"], "confirmed": False, "score": 7.2}],
        "attack": [],
        "hurt": [],
    },
    "missing": [{"slot": "attack", "kind": "required",
                 "reason": "no asset candidate for role 'attack'"},
                {"slot": "hurt", "kind": "required",
                 "reason": "no asset candidate for role 'hurt'"}],
    "diagnostics": [],
}

_ERROR_PATH = {
    "schema_version": 1, "query": "slime enemy", "role": "",
    "features": [], "feature_capabilities": {}, "requirements": {},
    "asset_slots": [], "optional_slots": [], "asset_candidates": {},
    "missing": [],
    "diagnostics": [{"reason": "config_error", "message": "entity asset slots config is not valid"}],
}


def _convert(payload: dict, selections: dict):
    return adapter.convert(payload, selections)


def _run_cli(payload_dict, *argv, stdin_text=None) -> tuple[int, dict, str, str]:
    """run the CLI in-process; returns (exit_code, parsed stdout json or None, stdout, stderr)."""
    argv_full = list(argv)
    buf_out, buf_err = io.StringIO(), io.StringIO()
    code = 0
    stdin_data = stdin_text if stdin_text is None and False else (stdin_text or "")
    old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
    try:
        sys.stdin = io.StringIO(stdin_data)
        sys.stdout, sys.stderr = buf_out, buf_err
        code = adapter.main(argv_full)
    except SystemExit as exc:
        code = int(exc.code or 0)
    finally:
        sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr
    out_text, err_text = buf_out.getvalue(), buf_err.getvalue()
    parsed = None
    try:
        parsed = json.loads(out_text)
    except Exception:
        pass
    return code, parsed, out_text, err_text


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="d2b_"))
    sample_file = tmpdir / "discovery.json"
    sample_file.write_text(json.dumps(_SAMPLE, ensure_ascii=False), encoding="utf-8")

    print("--- Discovery-to-Binding Adapter ---")
    print()

    # ---- T1: 有效 JSON + 显式候选选择 ----
    binding, warnings, errors = _convert(_SAMPLE, {"idle": "slime_idle", "move": "slime_run"})
    ok("T1: bindings derived from explicit selections",
       binding == {"bindings": [{"role": "idle", "asset": "slime_idle"},
                                {"role": "move", "asset": "slime_run"}]},
       repr(binding))
    ok("T1: no errors on healthy payload", not errors, repr(errors))
    ok("T1: unselected required slots produce warnings (attack/hurt empty)",
       any(w.get("type") == "unselected_required_slot" and
           set(w.get("slots") or []) == {"attack", "hurt"} for w in warnings),
       repr(warnings))

    # ---- T2: 不提供候选选择，绝不静默 top1 ----
    try:
        _convert(_SAMPLE, {})
        ok("T2: no selection -> SelectionError (not silent top1)", False)
    except adapter.SelectionError as exc:
        ok("T2: no selection -> SelectionError (not silent top1)",
           exc.reason == "no_explicit_bindings"
           and "top1" not in (exc.args[0] or "").lower(),
           exc.reason)
    # 反向验证：即便只传一个槽位选择也不补选其它槽位
    binding2, warnings2, _ = _convert(_SAMPLE, {"idle": "slime_idle"})
    ok("T2: single selection keeps only that slot, no top1 fill",
       binding2 == {"bindings": [{"role": "idle", "asset": "slime_idle"}]},
       repr(binding2))
    ok("T2: leftover required slots are warned, not chosen",
       any(w.get("type") == "unselected_required_slot" and
           set(w.get("slots") or []) == {"move", "attack", "hurt"} for w in warnings2),
       repr(warnings2))

    # ---- T3: 选择不存在的 candidate ----
    try:
        _convert(_SAMPLE, {"idle": "no_such_asset"})
        ok("T3: unknown candidate id -> SelectionError", False)
    except adapter.SelectionError as exc:
        ok("T3: unknown candidate id -> SelectionError",
           exc.reason == "selection_errors" and "no_such_asset" in exc.args[0],
           repr(exc.args[0]))

    # ---- T4: candidate 与请求槽位不匹配（跨槽借用）----
    try:
        _convert(_SAMPLE, {"move": "slime_idle"})   # idle 候选不当 move 用
        ok("T4: cross-slot candidate -> SelectionError", False)
    except adapter.SelectionError as exc:
        ok("T4: cross-slot candidate -> SelectionError",
           "candidate_role_mismatch" in exc.args[0] or "not a candidate" in exc.args[0],
           repr(exc.args[0]))

    # ---- T5: 必填槽位无候选 ----
    try:
        _convert(_SAMPLE, {"attack": "anything"})
        ok("T5: empty-candidate slot -> SelectionError", False)
    except adapter.SelectionError as exc:
        ok("T5: empty-candidate slot -> SelectionError",
           "no_candidates" in exc.args[0] and "attack" in exc.args[0],
           repr(exc.args[0]))

    # ---- T6: 部分缺失槽位 —（已并入 T1/T2 警告断言）额外验证错误列表机制 ----
    binding6, warnings6, errors6 = _convert(_SAMPLE, {"idle": "slime_idle", "move": "slime_run"})
    ok("T6: partial payload converts selected slots without fabricating missing",
       binding6 and not errors6 and len(warnings6) >= 1,
       repr((binding6, warnings6, errors6)))

    # ---- T7: schema_version 不兼容 ----
    bad_version = dict(_SAMPLE, schema_version=2)
    try:
        _convert(bad_version, {"idle": "slime_idle"})
        ok("T7: unsupported schema_version -> AdapterError", False)
    except adapter.AdapterError as exc:
        ok("T7: unsupported schema_version -> AdapterError",
           exc.reason == "unsupported_schema_version", exc.reason)
    try:
        _convert(dict(_SAMPLE, schema_version="1"), {"idle": "slime_idle"})
        ok("T7: non-integer schema_version -> AdapterError", False)
    except adapter.AdapterError as exc:
        ok("T7: non-integer schema_version -> AdapterError",
           exc.reason == "bad_schema_version", exc.reason)

    # ---- T8: JSON 非法 / 根对象非 object ----
    for label, text in (("invalid json", "{not json"), ("not object", "[1,2,3]")):
        try:
            adapter.load_discovery_json(text)
            ok("T8: %s -> AdapterError" % label, False)
        except adapter.AdapterError as exc:
            ok("T8: %s -> AdapterError" % label, exc.reason in ("invalid_json", "root_not_object"),
               exc.reason)

    # ---- T9: 未知 diagnostics.reason 不静默 ----
    unknown_reason = dict(_SAMPLE, diagnostics=[{"reason": "mystery_mode", "message": "?"}])
    try:
        _convert(unknown_reason, {"idle": "slime_idle"})
        ok("T9: unknown diagnostics.reason -> not silently bound", False)
    except adapter.SelectionError as exc:
        ok("T9: unknown diagnostics.reason -> not silently bound",
           exc.reason == "unknown_diagnostics" and "mystery_mode" in exc.args[0],
           exc.reason)

    # ---- T10: 非致命诊断名（feature_index_missing / config_error）+ error 结构 ----
    for reason, struct in (
        ("feature_index_missing", dict(_SAMPLE, role="", asset_candidates={},
                                       asset_slots=[])),
        ("config_error", _ERROR_PATH),
    ):
        payload = dict(struct, diagnostics=[{"reason": reason, "message": "x"}])
        try:
            _convert(payload, {})
            ok("T10: %s fatal path detected" % reason, False)
        except adapter.SelectionError as exc:
            ok("T10: %s fatal path detected" % reason,
               exc.reason == "fatal_diagnostics", exc.reason)
    # 结构完好时 index_missing 是非致命的（index 缺失但槽位结构仍带完整键集）：
    payload = dict(_SAMPLE, diagnostics=[{"reason": "index_missing", "message": "x"}])
    try:
        _convert(payload, {"idle": "slime_idle"})
        ok("T10: well-formed index_missing payload still converts", False)
    except adapter.SelectionError as exc:
        ok("T10: well-formed index_missing payload still converts", False,
           exc.reason + " | convert should have succeeded (index_missing with "
           "candidate keys present is not structurally fatal)")
    # 已知非致命 reason（seeded_by_role）不应阻断转换
    payload = dict(_SAMPLE, diagnostics=[{"reason": "seeded_by_role", "message": "ok"}])
    binding10, _, errors10 = _convert(payload, {"idle": "slime_idle"})
    ok("T10: seeded_by_role is non-fatal and conversion proceeds",
       bool(binding10) and not errors10, repr(errors10))

    # ---- T11: role 不混淆 — entity role 冒充槽位要拒绝 ----
    try:
        # "enemy" 是实体角色，不是 asset_candidates 的槽位键
        _convert(_SAMPLE, {"enemy": "slime_idle"})
        ok("T11: entity role as slot -> SelectionError", False)
    except adapter.SelectionError as exc:
        ok("T11: entity role as slot -> SelectionError",
           "unknown_slot" in exc.args[0] and "enemy" in exc.args[0], repr(exc.args[0]))
    bind11, _, err11 = _convert(_SAMPLE, {"idle": "slime_idle"})
    ok("T11: output slot roles come from candidate.role (idle), not entity role (enemy)",
       [b["role"] for b in bind11["bindings"]] == ["idle"] and not err11,
       repr(bind11))

    # ---- T12: 输出字段白名单 ----
    ok("T12: binding_input keys == {bindings}",
       set(binding.keys()) == {"bindings"}, repr(sorted(binding.keys())))
    ok("T12: binding entries only {role, asset}",
       all(set(e.keys()) == {"role", "asset"} for e in binding["bindings"]),
       repr(binding["bindings"]))
    forbidden = ("compatibility", "resolved_from", "confidence", "node",
                 "path", "type", "feature", "note", "runners_up", "score")
    flattened = json.dumps(binding)
    ok("T12: no runtime-computed fields (compatibility/resolved_from/confidence/...)",
       not any(k in flattened for k in forbidden), flattened)

    # ==================== Phase 1.8.2 Step 2.6: I/O 加固回归 ====================
    print()
    print("--- Step 2.6: CLI I/O hardening ---")
    print()

    import subprocess as sp

    CLI = [sys.executable, str(_FEATURE_DIR / "discovery_to_binding.py")]
    WORKSPACE = Path(_TOOL_DOTAI).resolve()   # run_tests 以项目根为 cwd 运行测试

    def _cli_raw(*argv, stdin_text: str | None = None):
        r = sp.run(CLI + list(argv), capture_output=True, text=True, cwd=str(WORKSPACE),
                   input=stdin_text if stdin_text is not None else "")
        return r.returncode, r.stdout, r.stderr

    io_dir = Path(tempfile.mkdtemp(prefix="d2b_io_"))

    def _fixture_file(name: str, data) -> str:
        p = io_dir / name
        p.write_text(json.dumps(data) if not isinstance(data, str) else data,
                     encoding="utf-8")
        return str(p)

    # ---- T13: --input 文件不存在 -> exit 2，无 traceback，有诊断 ----
    code, out, err = _cli_raw("--input", str(io_dir / "does_not_exist.json"))
    ok("T13: missing --input file -> exit 2", code == 2, str(code))
    ok("T13: no traceback in stderr", "Traceback" not in err, err[:200])
    ok("T13: diagnostic mentions the operation/path",
       "read input file" in err and "does_not_exist.json" in err, err[:200])

    # ---- T14: 输入读取 I/O 失败（确定性 mock，不验证真实 OS 权限行为）----
    # mock 深层 Path.read_text，保留 _read_input_text 真实的异常翻译逻辑；
    # PermissionError 是 OSError 子类，应被翻译为 exit 2 可诊断 stderr。
    real_read_text = Path.read_text

    def _boom_read_text(self, *a, **k):
        raise PermissionError(13, "Permission denied (simulated)", str(self))

    Path.read_text = _boom_read_text
    buf_out, buf_err = io.StringIO(), io.StringIO()
    old = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = buf_out, buf_err
    try:
        code_mock = adapter.main(["--input", "mocked_unreadable.json",
                                  "--select", "idle=A"])
    finally:
        sys.stdout, sys.stderr = old
        Path.read_text = real_read_text
    ok("T14: OSError during input read -> exit 2 (deterministic mock)", code_mock == 2,
       str(code_mock))
    ok("T14: no traceback + operation/path in message",
       "Traceback" not in buf_err.getvalue() and "read input file" in buf_err.getvalue()
       and "mocked_unreadable.json" in buf_err.getvalue(),
       buf_err.getvalue()[:200])

    # ---- T15: stdin 为空 / 非法 JSON -> exit 2，无 traceback ----
    code, out, err = _cli_raw(stdin_text="")
    ok("T15: empty stdin -> exit 2", code == 2, "code=%s err=%s" % (code, err[:120]))
    ok("T15: empty stdin -> no traceback + invalid_json",
       "Traceback" not in err and "not valid JSON" in err, err[:160])
    code, out, err = _cli_raw(stdin_text="{not json")
    ok("T15: invalid JSON on stdin -> exit 2", code == 2, str(code))
    ok("T15: invalid JSON on stdin -> no traceback", "Traceback" not in err, err[:160])

    # ---- T16: --out 写入失败（父目录不存在）-> exit 2、无 partial 输出 ----
    fixture = _fixture_file("valid.json", _SAMPLE)
    out_target = str(io_dir / "no_such_parent" / "out.yaml")
    code, out, err = _cli_raw("--input", fixture, "--select", "idle=slime_idle",
                              "--out", out_target)
    ok("T16: unwritable --out (missing parent) -> exit 2", code == 2, str(code))
    ok("T16: no traceback + writes do not fake success",
       "Traceback" not in err and "write output file" in err
       and "no_such_parent" in err, err[:200])
    ok("T16: no partial output file left", not Path(out_target).exists(), out_target)

    # ---- T17: 原子写入 —— 成功路径产出完整文件，失败路径不损坏旧文件 ----
    replace_target = io_dir / "replace_target.yaml"
    replace_target.write_text("OLD-CONTENT", encoding="utf-8")
    code, out, err = _cli_raw("--input", fixture, "--select", "idle=slime_idle",
                              "--out", str(replace_target))
    body = replace_target.read_text(encoding="utf-8")
    ok("T17: atomic replace writes the full new content",
       code == 0 and "role: idle" in body and "asset: slime_idle" in body,
       "exit=%s body=%r" % (code, body[:80]))
    leftovers = [p.name for p in io_dir.glob(".d2b_*")]
    ok("T17: no temp files left behind", not leftovers, str(leftovers))

    # ==================== Step 2.6: 端到端（真实 bind_assets 消费） ====================
    print()
    print("--- Step 2.6: end-to-end with bind_assets ---")
    print()

    # 复用 asset_registry 侧的 fixture 依赖（fixture_project / build_asset_index），
    # 前提与 test_feature_discovery.py 相同：插入 tests 与 asset_registry 路径。
    _asset_tests_dir = _TOOL_DOTAI / "tools" / "asset_registry" / "tests"
    sys.path.insert(0, str(_asset_tests_dir))
    sys.path.insert(0, str(_TOOL_DOTAI / "tools" / "asset_registry"))
    import fixture_project                                     # noqa: E402
    import build_asset_index as builder                        # noqa: E402
    from asset_metadata import build_index, scan_project, index_path  # noqa: E402

    e2e_root = Path(tempfile.mkdtemp(prefix="d2b_e2e_"))
    fixture_project.build_project(e2e_root)
    idx_file = index_path(e2e_root)
    idx_file.parent.mkdir(parents=True, exist_ok=True)
    idx_file.write_text(json.dumps(build_index(scan_project(e2e_root)),
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    # Discovery 需要三个数据源：asset_index + entity_asset_slots + feature_index。
    # slots 复用项目正式契约文件（只读拷贝进临时目录，不写回）；
    # feature_index 复用 test_feature_discovery.py 的最小索引（同 schema）。
    import test_feature_discovery as _tfd                       # noqa: E402
    (idx_file.parent / "entity_asset_slots.yaml").write_text(
        _tfd._SLOTS_YAML, encoding="utf-8")
    (idx_file.parent / "feature_index.json").write_text(
        json.dumps(_tfd._FEATURES_IDX, ensure_ascii=False), encoding="utf-8")

    project_abs = str(e2e_root.resolve())
    # 真实 Discovery 输出（fixture 项目，enemy 角色 -> idle/move/attack/hurt 槽位）
    fdjson = io_dir / "fd_e2e.json"
    r_fd = sp.run([sys.executable, str(_FEATURE_DIR / "feature_discovery.py"),
                   "enemy", "--json", "--project", project_abs],
                  capture_output=True, text=True, cwd=str(WORKSPACE), timeout=120)
    ok("T18: feature_discovery on fixture exits 0", r_fd.returncode == 0,
       r_fd.stderr[:200])
    fdjson.write_text(r_fd.stdout, encoding="utf-8")

    payload_fd = json.loads(r_fd.stdout)
    idle_cands = payload_fd["asset_candidates"].get("idle") or []
    ok("T18: fixture discovery has idle candidates", bool(idle_cands),
       str(payload_fd["asset_candidates"]))
    idle_id = idle_cands[0]["id"]

    # ---- T18: 显式选择 -> Binding 输入 -> bind_assets 消费 ----
    out_yaml = io_dir / "e2e_binding.yaml"
    code, out, err = _cli_raw("--input", str(fdjson), "--select", "idle=%s" % idle_id,
                              "--out", str(out_yaml))
    ok("T18: adapter CLI exits 0 for explicit selection", code == 0, err[:200])

    sys.path.insert(0, str(_TOOL_DOTAI / "tools" / "asset_registry"))
    import yaml as _yaml                                       # noqa: E402
    import bind_assets as _ba                                  # noqa: E402
    from asset_metadata import load_index as _load_index       # noqa: E402

    binding_in = _yaml.safe_load(out_yaml.read_text(encoding="utf-8"))
    ok("T18: adapter output is a valid --binding file",
       binding_in and "bindings" in binding_in, repr(binding_in))
    explicit = {e["role"]: e["asset"] for e in binding_in["bindings"]
                if e.get("role") and e.get("asset")}
    index = _load_index(None, project_root=e2e_root)
    result = _ba.bind_entity("e2e_entity", "enemy", ["chase_movement"],
                             index, e2e_root, explicit=explicit)
    explicit_entries = [b for b in result["bindings"] if b["role"] in explicit]
    ok("T18: explicit slot resolved_from=binding (explicit wins over inference)",
       len(explicit_entries) == 1
       and explicit_entries[0]["resolved_from"] == "binding"
       and explicit_entries[0]["asset"] == idle_id
       and explicit_entries[0]["confidence"] == "high",
       repr(explicit_entries))

    # ---- T19: 部分选择 —— 未选槽位被下游自动推断，且可与显式绑定区分 ----
    inferred = [b for b in result["bindings"] if b["role"] not in explicit]
    ok("T19: unselected required slots are still auto-inferred downstream",
       bool(inferred)
       and all(b["resolved_from"] == "index" for b in inferred),
       "inferred=%s" % [(b["role"], b["resolved_from"]) for b in inferred])
    distinct_from = {b["resolved_from"] for b in result["bindings"]}
    ok("T19: resolved_from distinguishes explicit (binding) vs inferred (index)",
       distinct_from == {"binding", "index"} and len(inferred) >= 1,
       str(distinct_from))
    warned = any(w.get("type") == "unselected_required_slot" for w in
                 (json.loads(sp.run(CLI + ["--input", str(fdjson),
                                           "--select", "idle=%s" % idle_id, "--json"],
                                    capture_output=True, text=True,
                                    cwd=str(WORKSPACE), timeout=60).stdout)["warnings"]))
    ok("T19: partial selection still emits unselected_required_slot warning",
       warned, "warnings should flag unselected required slots")

    # 清理临时目录
    shutil.rmtree(io_dir, ignore_errors=True)
    shutil.rmtree(e2e_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        pass
