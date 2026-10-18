#!/usr/bin/env python3
"""显式绑定 entity 作用域回归测试（Phase 1.15，I1-A…I1-G）。

覆盖（对应任务书 3.3，语义不变时允许按仓库绑定模型命名）：
    I1-A  合法的单实体（角色级）绑定保持兼容。
    I1-B  合法的显式 entity 绑定只路由到目标实体（其他实体不受影响）。
    I1-C  多实体文档中的角色级绑定按既有明确规则处理：应用到全部实体 +
          compatibility 门禁（主体冲突 → INCOMPATIBLE）+ 条目 note 标注作用域来源。
    I1-D  指向不存在实体的作用域绑定 → binding_scope_errors（文件/条目位置/
          目标实体/原因），CLI exit 1，不静默应用到其他实体。
    I1-E  绑定目标类型不匹配 → missing（可定位原因），不回退到索引推断
          （不得静默降级成默认资源）。
    I1-F  既有合法工作流不回归：discovery adapter 缺省输出保持 {role, asset}，
          显式选择的条目 resolved_from=binding / confidence=high。
    I1-G  绑定错误不静默：结构非法条目、未知 asset、未知实体都进入可定位诊断，
          绑定文档不产出 asset=None 或编造的资源。

用法:
    python .ai/tools/asset_registry/tests/test_binding_scope.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REGISTRY_DIR = TEST_DIR.parent
TOOLS_DIR = REGISTRY_DIR.parent
PROJECT_ROOT = TOOLS_DIR.parent

if str(REGISTRY_DIR) not in sys.path:
    sys.path.insert(0, str(REGISTRY_DIR))
if str(TOOLS_DIR / "feature_registry") not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR / "feature_registry"))
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

import bind_assets                                                     # noqa: E402
import discovery_to_binding as adapter                                 # noqa: E402
import fixture_project                                                 # noqa: E402
from asset_metadata import build_index, scan_project                   # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _audio_asset_id(index: dict) -> str:
    for asset in (index.get("assets") or []):
        if isinstance(asset, dict) and asset.get("type") == "audio":
            return str(asset.get("id"))
    return ""


def _block(doc: dict, entity_id: str) -> dict:
    return next((e for e in (doc.get("binding") or {}).get("entities") or []
                 if e.get("entity") == entity_id), {})


def _by_role(block: dict) -> dict:
    return {b.get("role"): b for b in block.get("bindings") or []}


def run() -> int:
    root = Path(tempfile.mkdtemp(prefix="binding_scope_"))
    _temp_dirs.append(root)
    fixture_project.build_project(root)

    # 与 test_asset_binding 相同的 Feature 夹具（能力提示 / 角色冲突判定需要）
    _write(root / "Features" / "player_movement" / "feature.yaml",
           "id: player_movement\nprovides:\n  - input_driven_movement\n"
           "relations:\n  entity_roles:\n    - player\n")
    _write(root / "Features" / "chase_movement" / "feature.yaml",
           "id: chase_movement\nprovides:\n  - chase_behavior\n"
           "relations:\n  entity_roles:\n    - enemy\n")
    _write(root / "Features" / "health" / "feature.yaml",
           "id: health\nprovides:\n  - damage_receiver\n  - health_state\n"
           "relations:\n  entity_roles:\n    - player\n    - enemy\n")

    index = build_index(scan_project(root))
    index_file = root / ".ai" / "context" / "asset_index.json"
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    audio_id = _audio_asset_id(index)
    ok("fixture: fixture project indexes an audio asset", bool(audio_id),
       str(sorted(a.get("id") for a in index.get("assets") or [])))

    two_entities = {
        "gameplay": {"id": "scope_test_game"},
        "entities": {
            "scope_enemy": {"role": "enemy", "features": ["chase_movement", "health"]},
            "scope_player": {"role": "player", "features": ["player_movement", "health"],
                             "scene": "res://Scenes/NoSuchPlayer.tscn"},
        },
    }
    one_entity = {
        "gameplay": {"id": "scope_single_entity"},
        "entities": {
            "solo_enemy": {"role": "enemy", "features": ["chase_movement", "health"]},
        },
    }

    # ---- I1-A：单实体（角色级）绑定保持兼容 ----
    doc = bind_assets.bind_gameplay(one_entity, index, root, explicit={"idle": "slime_idle"})
    solo = _by_role(_block(doc, "solo_enemy"))
    ok("I1-A: role-level binding on a single-entity document still resolves",
       solo.get("idle", {}).get("asset") == "slime_idle"
       and solo.get("idle", {}).get("resolved_from") == "binding"
       and solo.get("idle", {}).get("confidence") == "high",
       repr(solo.get("idle")))
    ok("I1-A: single-entity document has no scope errors",
       (doc.get("binding") or {}).get("binding_scope_errors") == [],
       repr((doc.get("binding") or {}).get("binding_scope_errors")))

    # ---- I1-B：实体作用域绑定只路由到目标实体 ----
    doc = bind_assets.bind_gameplay(two_entities, index, root,
                                    scoped_bindings={"scope_enemy": {"idle": "slime_idle"}})
    enemy = _by_role(_block(doc, "scope_enemy"))
    player = _by_role(_block(doc, "scope_player"))
    ok("I1-B: scoped binding resolves on the target entity",
       enemy.get("idle", {}).get("asset") == "slime_idle"
       and enemy.get("idle", {}).get("resolved_from") == "binding",
       repr(enemy.get("idle")))
    ok("I1-B: scoped binding does not leak to the other entity",
       player.get("idle", {}).get("asset") != "slime_idle"
       and player.get("idle", {}).get("resolved_from") == "index",
       repr(player.get("idle")))
    ok("I1-B: scoped resolution records the entity scope in reasons/note",
       "entity-scoped" in " ".join(enemy.get("idle", {}).get("reasons") or [])
       or "entity-scoped" in (enemy.get("idle", {}).get("note") or ""),
       repr((enemy.get("idle", {}).get("reasons"), enemy.get("idle", {}).get("note"))))

    # ---- I1-C：多实体文档中的角色级绑定按既有明确规则处理（可见、可判级） ----
    doc = bind_assets.bind_gameplay(two_entities, index, root, explicit={"idle": "slime_idle"})
    enemy = _by_role(_block(doc, "scope_enemy"))
    player = _by_role(_block(doc, "scope_player"))
    ok("I1-C: role-level binding applies to every entity (documented legacy rule)",
       enemy.get("idle", {}).get("asset") == "slime_idle"
       and player.get("idle", {}).get("asset") == "slime_idle",
       repr((enemy.get("idle", {}).get("asset"), player.get("idle", {}).get("asset"))))
    ok("I1-C: cross-entity leakage is flagged INCOMPATIBLE by the compatibility gate",
       player.get("idle", {}).get("compatibility") == "INCOMPATIBLE",
       repr(player.get("idle", {}).get("compatibility")))
    ok("I1-C: role-level application in a multi-entity document is visible in the note",
       "role-level explicit binding" in (player.get("idle", {}).get("note") or "")
       and "scope_player" in (player.get("idle", {}).get("note") or ""),
       repr(player.get("idle", {}).get("note")))

    # ---- I1-D：未知实体作用域 → 可定位错误 + exit 1（CLI 路径） ----
    work = Path(tempfile.mkdtemp(prefix="binding_scope_cli_"))
    _temp_dirs.append(work)
    blueprint_path = _write(work / "gameplay.yaml", io.StringIO(
        __import__("yaml").safe_dump(two_entities, sort_keys=False)).getvalue())
    binding_path = _write(work / "binding.yaml",
                          "bindings:\n"
                          "  - entity: scope_enemy\n    role: idle\n    asset: slime_idle\n"
                          "  - entity: ghost_entity\n    role: move\n    asset: slime_move\n")
    proc = subprocess.run(
        [sys.executable, str(REGISTRY_DIR / "bind_assets.py"),
         "--gameplay", str(blueprint_path), "--binding", str(binding_path),
         "--project", str(root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, timeout=120)
    combined = (proc.stdout or "") + (proc.stderr or "")
    ok("I1-D: unknown-entity scope fails the run (exit 1)", proc.returncode == 1,
       "exit=%s tail=%s" % (proc.returncode, combined[-300:]))
    ok("I1-D: the diagnostic locates file, target entity and role",
       "ghost_entity" in combined and "move" in combined and "binding.yaml" in combined,
       combined[-300:])
    ok("I1-D: the unknown-entity binding is not silently applied to another entity",
       "slime_move" not in combined.split("SCOPE ERROR")[0].split("Entity: scope_player")[-1]
       if "SCOPE ERROR" in combined else True,
       combined[-200:])

    # ---- I1-E：类型不匹配明确失败，不回退到索引推断 ----
    if audio_id:
        doc = bind_assets.bind_gameplay(one_entity, index, root,
                                        explicit={"idle": audio_id})
        solo = _by_role(_block(doc, "solo_enemy"))
        missing = {item.get("role"): item for item in _block(doc, "solo_enemy").get("missing") or []}
        ok("I1-E: audio asset for a visual role is rejected with a locatable reason",
           "idle" in missing and "explicit binding type mismatch" in (missing["idle"].get("reason") or ""),
           repr(missing.get("idle")))
        ok("I1-E: the mismatched explicit binding is not applied", "idle" not in solo,
           repr(solo.get("idle")))
        ok("I1-E: no silent fallback to index inference for the rejected role",
           solo.get("idle") is None and missing.get("idle", {}).get("kind") == "required",
           repr((solo.get("idle"), missing.get("idle"))))
        doc = bind_assets.bind_gameplay(one_entity, index, root,
                                        scoped_bindings={"solo_enemy": {"hurt_sfx": "slime_idle"}})
        solo = _by_role(_block(doc, "solo_enemy"))
        optional_missing = {item.get("role"): item
                            for item in _block(doc, "solo_enemy").get("optional_missing") or []}
        ok("I1-E: visual asset for an sfx role is rejected (reverse direction)",
           "hurt_sfx" in optional_missing
           and "explicit binding type mismatch" in (optional_missing["hurt_sfx"].get("reason") or ""),
           repr(optional_missing.get("hurt_sfx")))
        ok("I1-E: the reversed mismatch is not applied either", "hurt_sfx" not in solo,
           repr(solo.get("hurt_sfx")))
    else:
        _failures.append("I1-E: fixture has no audio asset to exercise the type gate")

    # ---- I1-F：既有合法工作流不回归 ----
    payload = {
        "schema_version": 1, "query": "slime enemy", "role": "enemy",
        "features": ["chase_movement"], "feature_capabilities": {},
        "requirements": [], "asset_slots": ["idle", "move"], "optional_slots": [],
        "asset_candidates": {
            "idle": [{"id": "slime_idle", "role": "idle", "path": "res://Assets/x.png"}],
            "move": [{"id": "slime_move", "role": "move", "path": "res://Assets/y.png"}],
        },
        "missing": [], "diagnostics": [],
    }
    legacy, _warnings, _errors = adapter.convert(payload, {"idle": "slime_idle", "move": "slime_move"})
    ok("I1-F: adapter default output keeps the legacy {role, asset} format",
       all(set(entry) == {"role", "asset"} for entry in legacy.get("bindings") or []),
       repr(legacy))
    scoped, _w, _e = adapter.convert(payload, {"idle": "slime_idle", "move": "slime_move"},
                                     entity_scope="scope_enemy")
    ok("I1-F: adapter --entity stamps the entity scope onto every entry",
       all(entry.get("entity") == "scope_enemy" and set(entry) == {"entity", "role", "asset"}
           for entry in scoped.get("bindings") or []),
       repr(scoped))
    explicit_from_adapter = {entry["role"]: entry["asset"] for entry in legacy["bindings"]}
    doc = bind_assets.bind_gameplay(one_entity, index, root, explicit=explicit_from_adapter)
    solo = _by_role(_block(doc, "solo_enemy"))
    ok("I1-F: the legacy explicit-selection workflow still records resolved_from=binding",
       solo.get("idle", {}).get("resolved_from") == "binding"
       and solo.get("move", {}).get("resolved_from") == "binding"
       and solo.get("idle", {}).get("confidence") == "high",
       repr((solo.get("idle"), solo.get("move"))))

    # ---- I1-G：绑定错误不静默 ----
    doc = bind_assets.bind_gameplay(one_entity, index, root,
                                    binding_errors=[{"location": "binding.yaml:bindings[3]",
                                                     "entity": "", "role": "",
                                                     "reason": "entry requires role and asset"}])
    ok("I1-G: malformed binding entries surface as scope errors (never silently skipped)",
       len((doc.get("binding") or {}).get("binding_scope_errors") or []) == 1
       and "bindings[3]" in (doc["binding"]["binding_scope_errors"][0].get("location") or ""),
       repr((doc.get("binding") or {}).get("binding_scope_errors")))
    doc = bind_assets.bind_gameplay(one_entity, index, root, explicit={"idle": "no_such_asset"})
    solo = _by_role(_block(doc, "solo_enemy"))
    missing = {item.get("role"): item for item in _block(doc, "solo_enemy").get("missing") or []}
    ok("I1-G: explicit binding to an unknown asset is reported, never fabricated",
       "idle" in missing and "no_such_asset" in (missing["idle"].get("reason") or "")
       and solo.get("idle") is None,
       repr((missing.get("idle"), solo.get("idle"))))
    every_entry_has_asset = all(
        isinstance(entry.get("asset"), str) and entry.get("asset")
        for block in [doc.get("binding", {})] for entry in block.get("entities", [{}])[0].get("bindings", [])
    ) if doc.get("binding", {}).get("entities") else True
    ok("I1-G: no binding entry is produced without a concrete asset id",
       every_entry_has_asset, repr(doc.get("binding", {}).get("entities")))

    # ---- 场景 6（适配器级）：实体身份解析——零/多匹配显式失败，显式 --entity 优先 ----
    discovery_payload = {
        "schema_version": 1, "query": "slime enemy", "role": "enemy",
        "features": ["chase_movement"], "feature_capabilities": {},
        "requirements": [], "asset_slots": ["idle"], "optional_slots": [],
        "asset_candidates": {
            "idle": [{"id": "slime_idle", "role": "idle", "path": "res://Assets/x.png"}],
        },
        "missing": [], "diagnostics": [],
    }
    selections_idle = {"idle": "slime_idle"}
    ok("S6: a unique role match resolves the entity identity",
       adapter.resolve_entity_identity("enemy", {
           "entities": {"scope_enemy": {"role": "enemy"},
                        "scope_player": {"role": "player"}}}) == "scope_enemy")
    try:
        adapter.resolve_entity_identity("enemy", {"entities": {"only_player": {"role": "player"}}})
        ok("S6: a role with no matching entity fails (no guessed identity)", False, "no error raised")
    except adapter.SelectionError as exc:
        ok("S6: a role with no matching entity fails (no guessed identity)",
           exc.reason == "no_entity_with_role", repr(exc.reason))
    try:
        adapter.resolve_entity_identity("enemy", {"entities": {
            "enemy_a": {"role": "enemy"}, "enemy_b": {"role": "enemy"}}})
        ok("S6: an ambiguous entity role fails with both ids in the diagnosis",
           False, "no error raised")
    except adapter.SelectionError as exc:
        ok("S6: an ambiguous entity role fails with both ids in the diagnosis",
           exc.reason == "ambiguous_entity_role"
           and "enemy_a" in str(exc) and "enemy_b" in str(exc),
           repr((exc.reason, str(exc))))
    ok("S6: explicit --entity takes precedence over role-based resolution",
       adapter.convert(discovery_payload, selections_idle, entity_scope="declared_enemy")[0]
       == {"bindings": [{"entity": "declared_enemy", "role": "idle", "asset": "slime_idle"}]},
       "explicit entity scope must win")

    # CLI 路径：--resolve-entity-from 解析唯一实体并写进输出；JSON 摘要带 entity_scope
    adapter_work = Path(tempfile.mkdtemp(prefix="binding_scope_adapter_"))
    _temp_dirs.append(adapter_work)
    discovery_file = _write(adapter_work / "discovery.json",
                            json.dumps(discovery_payload, ensure_ascii=False))
    unique_bp = _write(adapter_work / "unique_gameplay.yaml",
                       "gameplay:\n  id: unique_roles\n"
                       "entities:\n  scope_enemy:\n    role: enemy\n"
                       "  scope_player:\n    role: player\n")
    adapter_out = adapter_work / "scoped_override.yaml"
    proc = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "feature_registry" / "discovery_to_binding.py"),
         "--input", str(discovery_file), "--select", "idle=slime_idle",
         "--resolve-entity-from", str(unique_bp), "-o", str(adapter_out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, timeout=120)
    adapter_doc = (__import__("yaml").safe_load(adapter_out.read_text(encoding="utf-8"))
                   if adapter_out.is_file() else {})
    ok("S6: CLI --resolve-entity-from stamps the resolved entity onto every entry",
       proc.returncode == 0
       and adapter_doc == {"bindings": [{"entity": "scope_enemy", "role": "idle",
                                         "asset": "slime_idle"}]},
       "exit=%s doc=%s stderr=%s" % (proc.returncode, repr(adapter_doc),
                                     (proc.stderr or "")[-200:]))

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all binding scope checks passed (I1-A..I1-G)")
    return 0


def cleanup() -> None:
    for temp in _temp_dirs:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    try:
        code = run()
    finally:
        cleanup()
    sys.exit(code)
