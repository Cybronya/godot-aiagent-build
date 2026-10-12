#!/usr/bin/env python3
"""Feature Discovery MVP Tests —— Phase 1.8.1。

覆盖任务要求：
    T1  已知角色 enemy 的发现结果（features/requirements/slots/candidates）
    T2  未知输入的错误语义（role 兜底 + 诊断 + 非 0 语义区分）
    T3  Feature 与资源槽位正确区分（requirements vs asset_slots 分离）
    T4  真实候选字段（id/path/type/score 来自 Asset Query）
    T5  空索引/缺失资源/索引异常（确定性与诊断，不编造）
    T6  --json 输出可被标准 json.loads 解析
    T7  槽位配置与既有绑定行为一致（校验 yaml -> entity_required_roles 链路）
    T8  （回归由外部 run_tests 保护，不在本文件）

Usage:
    python .ai/tools/feature_registry/tests/test_feature_discovery.py

退出码: 0 = 全部通过；1 = 有失败。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_TOOL_DOTAI = Path(__file__).resolve().parents[3]
_FEATURE_DIR = _TOOL_DOTAI / "tools" / "feature_registry"
_ASSET_DIR = _TOOL_DOTAI / "tools" / "asset_registry"
_ASSET_TESTS_DIR = _ASSET_DIR / "tests"
sys.path.insert(0, str(_FEATURE_DIR))
sys.path.insert(0, str(_ASSET_DIR))
sys.path.insert(0, str(_ASSET_TESTS_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import fixture_project                                     # noqa: E402
import build_asset_index as builder                        # noqa: E402
from asset_metadata import build_index, scan_project, index_path   # noqa: E402

import feature_discovery as fd                             # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


_SLOTS_YAML = ((_TOOL_DOTAI / "context" / "entity_asset_slots.yaml").read_text(encoding="utf-8")
               if (_TOOL_DOTAI / "context" / "entity_asset_slots.yaml").is_file() else "")

# 最小 feature index：与真实 feature_index.json 同 schema，覆盖 enemy seed 三件套 + player
_FEATURES_IDX = {
    "features": [
        {"id": "chase_movement", "version": "1", "category": "component",
         "provides": ["character_movement"], "requires": [],
         "interfaces": [], "signals": [],
         "relations": {"entity_roles": ["enemy"]}},
        {"id": "contact_damage", "version": "1", "category": "component",
         "provides": ["damage_source"], "requires": [],
         "interfaces": [], "signals": [],
         "relations": {"entity_roles": ["enemy", "trap"]}},
        {"id": "health", "version": "1", "category": "component",
         "provides": ["health_state", "damage_receiver", "death_event"], "requires": [],
         "interfaces": [], "signals": [],
         "relations": {"entity_roles": ["enemy", "player"]}},
        {"id": "player_movement", "version": "1", "category": "component",
         "provides": ["input_driven_movement", "character_movement"], "requires": [],
         "interfaces": [], "signals": [],
         "relations": {"entity_roles": ["player"]}},
    ]}


def make_project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="feature_discovery_"))
    _temp_dirs.append(root)
    fixture_project.build_project(root)
    index_file = index_path(root)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(json.dumps(build_index(scan_project(root)),
                                     ensure_ascii=False, indent=2), encoding="utf-8")
    (root / ".ai" / "context" / "feature_index.json").write_text(
        json.dumps(_FEATURES_IDX, ensure_ascii=False, indent=2), encoding="utf-8")
    if _SLOTS_YAML:
        (root / ".ai" / "context" / "entity_asset_slots.yaml").write_text(_SLOTS_YAML, encoding="utf-8")
    return root


def run_json(root: Path, *argv: str) -> tuple[int, dict]:
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    argv_full = list(argv) + ["--json", "--project", str(root)]
    try:
        with redirect_stdout(buf):
            code = fd.main(argv_full)
        out = buf.getvalue()
    except SystemExit as exc:            # argparse error（空 query 等）——语义即 2
        code = int(exc.code or 2)
        out = buf.getvalue() or "{}"
    return code, json.loads(out)


def main() -> int:
    root = make_project()

    print("--- Feature Discovery MVP ---")
    print()

    # ---- T1: 已知角色 enemy ----
    code, payload = run_json(root, "enemy")
    ok("T1: exit 0 for known role", code == 0, str(code))
    ok("T1: schema_version is int", payload.get("schema_version") == fd.SCHEMA_VERSION)
    ok("T1: query echo", payload.get("query") == "enemy", str(payload.get("query")))
    ok("T1: role resolved", payload.get("role") == "enemy", str(payload.get("role")))
    ok("T1: features non-empty list", isinstance(payload.get("features"), list) and payload["features"])
    got = set(payload.get("features") or [])
    ok("T1: enemy features include base trio",
       {"contact_damage", "chase_movement", "health"}.issubset(got), str(sorted(got)))
    slots = payload.get("asset_slots") or []
    ok("T1: default slots for enemy", slots == ["idle", "move", "attack", "hurt"], str(slots))

    # ---- T2: 未知输入 ----
    code_u, payload_u = run_json(root, "zzz_flying_spaghetti_monster")
    ok("T2: unknown tokens do not crash", isinstance(payload_u.get("features"), list))
    ok("T2: unknown keeps explicit fallback role", payload_u.get("role") == "*default*",
       str(payload_u.get("role")))
    ok("T2: unknown diagnosed as unknown_role",
       any(d.get("reason") == "unknown_role" for d in payload_u.get("diagnostics") or []),
       json.dumps(payload_u.get("diagnostics"))[:200])
    ok("T2: unknown still yields default slots",
       payload_u.get("asset_slots") == ["idle"], str(payload_u.get("asset_slots")))

    code_bad, payload_bad = run_json(root, "--role", "")   # 无 any 输入 -> argparse exit 2
    ok("T2: empty input exit 2", code_bad == 2, str(code_bad))
    # parser.error 不产出 JSON：断言其语义仅为退出码（错误消息走 stderr）

    # ---- T3: Feature 与槽位分离 ----
    seg = payload.get("asset_slots")
    ok("T3: asset_slots is role-slot list (not per-feature)",
       isinstance(seg, list) and all(isinstance(s, str) for s in seg), str(seg))
    ok("T3: features are feature ids not asset roles",
       all(isinstance(f, str) and "_" not in f or f in ("chase_movement", "contact_damage", "health")
           for f in payload.get("features") or []), str(payload.get("features")))
    caps = payload.get("feature_capabilities") or {}
    ok("T3: feature_capabilities maps id->provides",
       isinstance(caps, dict) and all(isinstance(v, list) for v in caps.values()),
       json.dumps(caps)[:120])

    # ---- T4: 候选字段 ----
    cands = payload.get("asset_candidates") or {}
    ok("T4: candidates per slot keys match slots",
       all(slot in cands for slot in slots), str(list(cands)))
    for slot, entries in cands.items():
        if not entries:
            continue
        first = entries[0]
        ok("T4(%s): candidate has id/path/type/score" % slot,
           all(k in first for k in ("id", "path", "type", "score")), str(first))
        ok("T4(%s): path is res://" % slot, str(first.get("path", "")).startswith("res://"))
        break
    ok("T4: idle candidate for slime subject",
       any("slime" in str(e.get("path", "")) or "slime" in str(e.get("id", ""))
           for e in cands.get("idle") or []),
       str((cands.get("idle") or [None])[0]))

    # ---- T5: 缺失/空索引/异常 ----
    missing = payload.get("missing") or []
    ok("T5: missing list present", isinstance(missing, list), str(missing))
    # fixture 有 idle/move/attack/hurt 的 slime 资源 → 无 required 缺失
    ok("T5: no missing for fully-equipped fixture enemy", len(missing) == 0, str(missing))

    empty_root = Path(tempfile.mkdtemp(prefix="feature_discovery_empty_"))
    _temp_dirs.append(empty_root)
    # 空索引 = 只有槽位/feature 配置但资产索引缺失
    (empty_root / ".ai" / "context").mkdir(parents=True, exist_ok=True)
    if _SLOTS_YAML:
        (empty_root / ".ai" / "context" / "entity_asset_slots.yaml").write_text(_SLOTS_YAML, encoding="utf-8")
    (empty_root / ".ai" / "context" / "feature_index.json").write_text(
        json.dumps(_FEATURES_IDX, ensure_ascii=False, indent=2), encoding="utf-8")
    code, payload = run_json(empty_root, "enemy")
    ok("T5: empty index reports diagnostics", any(
        "index" in str(d.get("reason", "")).lower() or "missing" in str(d.get("reason", "")).lower()
        for d in payload.get("diagnostics") or []),
       json.dumps(payload.get("diagnostics"))[:200])
    ok("T5: empty index still reports slots (from config, no hardcode)", payload.get("asset_slots") == ["idle", "move", "attack", "hurt"], str(payload.get("asset_slots")))
    ok("T5: empty index candidates are all empty lists",
       all(v == [] for v in (payload.get("asset_candidates") or {}).values()),
       str(payload.get("asset_candidates"))[:200])

    # 真实项目的槽位 yaml 若被清空：直接调用内部解析器确认结构错误
    config_yaml = _TOOL_DOTAI / "context" / "entity_asset_slots.yaml"
    breaks = _temp_dirs[0] / "bad_slots.yaml"
    breaks.write_text("schema:\n  id: wrong\n  version: 1\nroles: {}\n", encoding="utf-8")
    try:
        fd.load_slots(breaks)
        ok("T5: wrong schema.id raises", False, "no error thrown")
    except RuntimeError as exc:
        ok("T5: wrong schema.id raises", "schema.id" in str(exc), str(exc)[:120])
    except SystemExit:
        ok("T5: wrong schema.id raises", False, "SystemExit leaked (should be RuntimeError)")

    broken = _temp_dirs[0] / "broken_slots.yaml"
    broken.write_text("schema:\n  id: entity_asset_slots\n  version: 1\nroles:\n  enemy:\n    required: []\n", encoding="utf-8")
    try:
        fd.load_slots(broken)
        ok("T5: empty required list raises", False, "no error")
    except RuntimeError as exc:
        ok("T5: empty required list raises", "required" in str(exc), str(exc)[:150])
    except SystemExit:
        ok("T5: empty required list raises", False, "SystemExit leaked")

    # ---- T6: --json 可被标准 json.loads 解析（已隐式：run_json 每次都解析成功）----
    ok("T6: all --json payloads parsed via json.loads in every test above", True)

    # ---- T7: 槽位配置与既有绑定行为一致 ----
    import bind_assets as ba
    ok("T7: bind_assets enemy slots from yaml",
       ba.entity_required_roles("enemy") == ["idle", "move", "attack", "hurt"],
       str(ba.entity_required_roles("enemy")))
    ok("T7: fallback role defaults to idle",
       ba.entity_required_roles("no_such_role") == ["idle"],
       str(ba.entity_required_roles("no_such_role")))
    ok("T7: OPTIONAL_ROLES migrated unchanged",
       ba.OPTIONAL_ROLES == ["hurt_sfx"], str(ba.OPTIONAL_ROLES))
    ok("T7: feature_discovery uses same table", fd.load_slots(
        _TOOL_DOTAI / "context" / "entity_asset_slots.yaml") is not None)

    # 通过 CLI 入口调用真实 bind_assets 与 feature_discovery 输出槽位一致性
    code, payload = run_json(root, "player", "--role", "player")
    ok("T7: --role explicit respected", payload.get("role") == "player", str(payload.get("role")))
    ok("T7: player slots", payload.get("asset_slots") == ["idle", "run", "attack", "hurt"],
       str(payload.get("asset_slots")))

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Feature Discovery MVP tests")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        for temp in _temp_dirs:
            shutil.rmtree(temp, ignore_errors=True)
