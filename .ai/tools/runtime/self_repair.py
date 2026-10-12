#!/usr/bin/env python3
"""Self-Repair Controller —— Runtime 失败的自动修复闭环。

    Runtime Playtest
        ↓ Runtime Failure
    Runtime Diagnosis
        ↓
    Repair Plan（受 repair_safety 约束）
        ↓
    Apply Repair（单点字面量替换 + 备份）
        ↓
    Static Validation（脚本解析 / 场景结构 / Framework Validator）
        ↓
    Runtime Playtest（重跑）
        ↓
    PASS 或达到 --max-attempts

职责边界：
    - Validator 只验证，不修复；Self-Repair 不写进 Validator。
    - Feature / Scene 不承担自修逻辑；本工具只修改「错误发生点」的最小范围。
    - 每次尝试必须记录 attempt / timestamp / error / diagnosis / changed_files /
      validation_result / runtime_result 到 repair history（.ai/memory/runtime-repairs/）。
    - 修复无效或引入新错误时自动回滚（禁止无限修改项目）。

用法:
    python self_repair.py --scene res://Scenes/EnemyBasic.tscn
    python self_repair.py --project . --scene res://Scenes/EnemyBasic.tscn --max-attempts 3
    python self_repair.py --scene res://Scenes/X.tscn --dry-run     # 只诊断与出计划

退出码: 0 = 最终 PASS；1 = 未修复；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_repair import repair_assets                               # noqa: E402
from diagnose_runtime import diagnose, print_diagnosis               # noqa: E402
from repair_engine import (                                          # noqa: E402
    apply_change,
    revert_change,
    static_validation,
)
from repair_plan import build_plan, plan_to_yaml, print_plan, validate_plan   # noqa: E402
from run_scene import RuntimeInputError, run_runtime, summarize      # noqa: E402
from runtime_result import (                                         # noqa: E402
    STATUS_PASS,
    find_project_root,
    load_contract,
    load_repair_safety,
    now_iso,
    result_signatures,
    validate_result,
)

PASS = "PASS"
FAIL = "FAIL"


def _history_paths(history_dir: Path) -> list[Path]:
    return sorted(history_dir.glob("repair-*.yaml"))


def _next_history_index(history_dir: Path) -> int:
    highest = 0
    for path in _history_paths(history_dir):
        digits = "".join(ch for ch in path.stem if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return highest + 1


def _write_history(entry: dict, history_dir: Path) -> str:
    history_dir.mkdir(parents=True, exist_ok=True)
    index = _next_history_index(history_dir)
    path = history_dir / ("repair-%03d.yaml" % index)
    path.write_text(yaml.safe_dump(entry, sort_keys=False, allow_unicode=True, width=4096),
                    encoding="utf-8")
    return str(path)


def _history_entry(attempt: int, scene: str, plan: dict, diagnosis: dict,
                   changed_files: list[str], validation: dict | None,
                   before: dict, after: dict | None, status: str,
                   reverted: bool, note: str = "") -> dict:
    block = diagnosis.get("diagnosis") or {}
    primary = (block.get("errors") or [{}])[0]
    repair_block = plan.get("repair") or {}
    return {
        "attempt": attempt,
        "timestamp": now_iso(),
        "scene": scene,
        "error": {
            "classification": primary.get("classification") or primary.get("type") or "",
            "message": primary.get("message") or "",
            "file": primary.get("file") or "",
            "line": primary.get("line") or 0,
        },
        "diagnosis": {
            "status": block.get("status"),
            "playtest_status": block.get("playtest_status"),
            "primary_classification": block.get("primary_classification"),
            "confidence": primary.get("confidence") or "",
            "unclassified": block.get("unknown_count"),
        },
        "repair": {
            "repairable": repair_block.get("repairable"),
            "target": (repair_block.get("target") or {}).get("file") or "",
            "scope": (repair_block.get("target") or {}).get("scope") or "",
            "reason": repair_block.get("reason") or "",
            "changes": list(repair_block.get("changes") or []),
            "risk": repair_block.get("risk"),
        },
        "changed_files": list(changed_files),
        "validation_result": validation or {"ok": None, "steps": []},
        "runtime_result": {
            "before": {"status": before.get("status"), "errors": len(before.get("errors") or []),
                       "exit_code": before.get("exit_code"), "timeout": before.get("timeout")},
            "after": None if after is None else {
                "status": after.get("status"), "errors": len(after.get("errors") or []),
                "exit_code": after.get("exit_code"), "timeout": after.get("timeout"),
            },
        },
        "status": status,
        "reverted": bool(reverted),
        "note": note,
    }


def self_repair(project: str | os.PathLike | None = None,
                scene: str = "",
                max_attempts: int | None = None,
                timeout: float | None = None,
                contract: dict | None = None,
                safety: dict | None = None,
                history_dir: str | os.PathLike | None = None,
                allow_medium: bool = False,
                dry_run: bool = False,
                write_logs: bool | None = False,
                verbose: bool = True) -> dict:
    """执行 Self-Repair 闭环，返回报告（不抛异常，输入错误抛 RuntimeInputError）。"""
    contract = contract or load_contract()
    safety = safety or load_repair_safety()
    root = find_project_root(project)
    if root is None:
        raise RuntimeInputError("project.godot not found (project=%s)" % (project or os.getcwd()))
    attempts_limit = int(max_attempts if max_attempts is not None else contract.get("max_repair_attempts", 3) or 3)
    attempts_limit = max(1, attempts_limit)

    resolved_history: Path | None
    if history_dir is not None:
        resolved_history = Path(history_dir)
    elif (root / ".ai").is_dir():
        resolved_history = root / str(contract.get("history_dir") or ".ai/memory/runtime-repairs")
    else:
        resolved_history = None

    report: dict = {
        "self_repair": {
            "scene": "",
            "project": str(root),
            "status": FAIL,
            "attempts_used": 0,
            "max_attempts": attempts_limit,
            "dry_run": bool(dry_run),
            "changed_files": [],
            "history": [],
            "attempts": [],
            "final_runtime_status": "",
            "note": "",
        }
    }
    block = report["self_repair"]

    if verbose:
        print("Self-Repair")
        print("Project: %s" % root)
        print("Scene:   %s" % (scene or "<project main scene>"))
        print("Max attempts: %d%s" % (attempts_limit, " (dry run)" if dry_run else ""))

    current_scene = scene
    before: dict | None = None
    changed_files: list[str] = []

    for attempt in range(1, attempts_limit + 1):
        if verbose:
            print()
            print("Attempt %d" % attempt)

        before = run_runtime(project=root, scene=current_scene, timeout=timeout,
                             contract=contract, tag="selfrepair-before",
                             write_logs=write_logs)
        current_scene = before.get("scene") or current_scene
        block["scene"] = current_scene
        if verbose:
            print("  Runtime      %s  (%s)" % (before.get("status"), summarize(before)))

        if before.get("status") == STATUS_PASS:
            block.update({"status": PASS, "attempts_used": attempt - 1,
                          "final_runtime_status": PASS})
            if verbose:
                print()
                print("Result: PASS (no repair needed)")
            return report

        diagnosis = diagnose(before, root, current_scene)

        # ---------- Asset domain dispatch ----------
        # 只有当主要错误被诊断明确为 asset 并能提取出证据（asset_missing + 相关资源）
        # 时，才走 Asset Binding 重建；否则保持既有通用修复流程。
        asset_block = _asset_diagnosis(diagnosis, root, current_scene)
        repairable_assets = bool(asset_block.get("domain") == "asset")
        if repairable_assets:
            repair = _run_asset_repair(root, current_scene, asset_block,
                                       attempt=attempt, verbose=verbose)
            attempt_record = {"attempt": attempt, "runtime_before": before.get("status"),
                              "diagnosis": "asset_missing", "domain": "asset",
                              "failed_asset": asset_block.get("related_asset") or ""}
            if not repair.get("ok"):
                entry = _history_entry(attempt, current_scene, {"repair": {}}, diagnosis, [],
                                       None, before, None, "not_repairable", False,
                                       note=repair.get("reason") or "asset repair failed")
                entry["failed_asset"] = asset_block.get("related_asset") or ""
                entry["domain"] = "asset"
                entry["old_binding"] = ""
                entry["new_binding"] = ""
                attempt_record["status"] = "not_repairable"
                attempt_record["reason"] = repair.get("reason")
                block["attempts"].append(attempt_record)
                block["attempts_used"] = attempt
                block["final_runtime_status"] = before.get("status")
                block["note"] = repair.get("reason") or "asset repair failed"
                if resolved_history is not None:
                    block["history"].append(_write_history(entry, resolved_history))
                if verbose:
                    print("  Repair       FAIL  (%s)" % repair.get("reason"))
                    print()
                    print("Result: FAIL (asset binding could not be rebuilt)")
                return report

            if dry_run:
                attempt_record["status"] = "dry_run"
                block["attempts"].append(attempt_record)
                block["attempts_used"] = attempt
                block["status"] = FAIL
                block["note"] = "dry run: asset binding rebuild planned but not applied"
                if verbose:
                    print("  Repair       DRY-RUN (not applied)")
                    print()
                    print("Result: FAIL (dry run)")
                return report

            changed_files = list(repair.get("changed_files") or [])
            entry = _history_entry(attempt, current_scene, {"repair": {
                "repairable": True, "target": {"file": repair.get("binding_path") or "",
                                              "scope": "asset_binding"},
                "reason": repair.get("reason") or "",
                "changes": ["rebuild asset binding: %s" % repair.get("binding_path")],
                "risk": "low"}}, diagnosis, changed_files, None,
                before, None, "repaired", False)
            entry["domain"] = "asset"
            entry["failed_asset"] = asset_block.get("related_asset") or ""
            entry["old_binding"] = asset_block.get("related_binding") or ""
            entry["new_binding"] = repair.get("binding_path") or ""
            attempt_record.update({"status": "repaired", "binding": repair.get("binding_path") or "",
                                   "validation": None})
            block["attempts"].append(attempt_record)
            block["attempts_used"] = attempt
            block["changed_files"] = changed_files

            # ---------- runtime playtest again ----------
            after = run_runtime(project=root, scene=current_scene, timeout=timeout,
                                contract=contract, tag="selfrepair-after", write_logs=write_logs)
            if verbose:
                print("  Runtime      %s  (%s)" % (after.get("status"), summarize(after)))
            if after.get("status") == STATUS_PASS:
                entry["runtime_result"]["after"] = {
                    "status": after.get("status"), "errors": len(after.get("errors") or []),
                    "exit_code": after.get("exit_code"), "timeout": after.get("timeout")}
                entry["status"] = "repaired"
                attempt_record["runtime_after"] = PASS
                block.update({"status": PASS, "final_runtime_status": PASS,
                              "note": "asset binding rebuilt; runtime recovered on attempt %d" % attempt})
                if resolved_history is not None:
                    block["history"].append(_write_history(entry, resolved_history))
                if verbose:
                    print()
                    print("Result: PASS (asset repair attempt %d)" % attempt)
                return report

            # Asset 修复未让 Runtime 收敛：按 require_revert 原则回滚绑定重写不安全——
            # 绑定本来就是 Generated Data（可随时重建），保留新绑定并交还通用修复链。
            entry["runtime_result"]["after"] = {
                "status": after.get("status"), "errors": len(after.get("errors") or []),
                "exit_code": after.get("exit_code"), "timeout": after.get("timeout")}
            entry["status"] = "kept_asset_binding"
            entry["note"] = "asset binding rebuilt but runtime still %s; " \
                            "handing over to the generic repair pipeline" % after.get("status")
            attempt_record["runtime_after"] = after.get("status")
            attempt_record["status"] = "kept_asset_binding"
            block["final_runtime_status"] = after.get("status")
            block["note"] = entry["note"]
            if resolved_history is not None:
                block["history"].append(_write_history(entry, resolved_history))
            if verbose:
                print("  Repair       KEPT  (design: binding rebuild is not "
                      "a destructive edit; no revert) — 继续 generic 流程")
            # 进入下一 attempt（generic 分支会重新诊断）
            continue

        plan = build_plan(diagnosis, root, attempt=attempt, contract=contract,
                          safety=safety, allow_medium=allow_medium)
        plan_failures = validate_plan(plan, safety)
        if verbose:
            print("  Diagnosis    %s" % (PASS if not plan_failures else "WARNING"))
            if attempt == 1:
                print_diagnosis(diagnosis)
            print_plan(plan)

        attempt_record: dict = {"attempt": attempt, "runtime_before": before.get("status"),
                                "diagnosis": (diagnosis.get("diagnosis") or {}).get("primary_classification")}

        if not plan["repair"]["repairable"]:
            entry = _history_entry(attempt, current_scene, plan, diagnosis, [], None,
                                   before, None, "not_repairable", False,
                                   note=plan["repair"]["reason"])
            attempt_record["status"] = "not_repairable"
            block["attempts"].append(attempt_record)
            block["attempts_used"] = attempt
            block["final_runtime_status"] = before.get("status")
            block["note"] = plan["repair"]["reason"]
            if resolved_history is not None:
                path = _write_history(entry, resolved_history)
                block["history"].append(path)
                entry["history_file"] = path
            if verbose:
                print("  Repair       FAIL  (%s)" % plan["repair"]["reason"])
                print()
                print("Result: FAIL (no safe repair available)")
            return report

        if dry_run:
            attempt_record["status"] = "dry_run"
            block["attempts"].append(attempt_record)
            block["attempts_used"] = attempt
            block["status"] = FAIL
            block["note"] = "dry run: repair plan produced but not applied"
            if verbose:
                print("  Repair       DRY-RUN (not applied)")
                print()
                print("Result: FAIL (dry run)")
            return report

        # ---------- apply ----------
        edit = plan.get("_edit") or {}
        target = Path(edit.get("target_file") or "")
        applied = apply_change(target, edit.get("old_literal", ""), edit.get("new_literal", ""))
        if not applied.get("ok"):
            plan["repair"]["reason"] = applied.get("reason") or "apply failed"
            entry = _history_entry(attempt, current_scene, plan, diagnosis, [], None,
                                   before, None, "not_repairable", False, note=plan["repair"]["reason"])
            attempt_record["status"] = "apply_failed"
            block["attempts"].append(attempt_record)
            block["attempts_used"] = attempt
            block["final_runtime_status"] = before.get("status")
            block["note"] = plan["repair"]["reason"]
            if resolved_history is not None:
                block["history"].append(_write_history(entry, resolved_history))
            if verbose:
                print("  Repair       FAIL  (%s)" % plan["repair"]["reason"])
                print()
                print("Result: FAIL (repair could not be applied)")
            return report

        rel_changed = _relative_changed(root, target)
        changed_files = [rel_changed]
        if verbose:
            print("  Repair       PASS  (%s: %s -> %s)"
                  % (edit.get("target_rel"), edit.get("old_literal"), edit.get("new_literal")))
            if applied.get("diff"):
                print("  --- diff ---")
                for line in str(applied["diff"]).splitlines():
                    print("  " + line)

        # ---------- static validation ----------
        validation = static_validation(root, plan, changed_files=changed_files, contract=contract)
        validator_ok = bool(validation.get("ok"))
        if verbose:
            print("  Validator    %s  (%s)" % (PASS if validator_ok else FAIL,
                                               "; ".join(
                                                   "%s=%s" % (step["name"], "ok" if step["ok"] else "fail")
                                                   for step in validation.get("steps") or []
                                               ) or "no checks"))

        # ---------- runtime playtest again ----------
        after = run_runtime(project=root, scene=current_scene, timeout=timeout,
                            contract=contract, tag="selfrepair-after", write_logs=write_logs)
        if verbose:
            print("  Runtime      %s  (%s)" % (after.get("status"), summarize(after)))

        before_signatures = set(result_signatures(before))
        after_signatures = set(result_signatures(after))
        resolved = before_signatures - after_signatures
        introduced = after_signatures - before_signatures

        if after.get("status") == STATUS_PASS:
            entry = _history_entry(attempt, current_scene, plan, diagnosis, changed_files,
                                   validation, before, after, "repaired", False)
            attempt_record.update({"status": "repaired", "runtime_after": PASS,
                                   "validation": validator_ok})
            block["attempts"].append(attempt_record)
            block.update({"status": PASS, "attempts_used": attempt,
                          "changed_files": changed_files, "final_runtime_status": PASS})
            if resolved_history is not None:
                block["history"].append(_write_history(entry, resolved_history))
            if verbose:
                print()
                print("Result: PASS (repair attempt %d)" % attempt)
            return report

        progress = bool(resolved) and not introduced
        reverted = False
        note = ""
        if progress:
            note = "progress: previous errors resolved, new failure remains (runtime=%s)" % after.get("status")
        else:
            note = ("no progress: resolved=%d introduced=%d" % (len(resolved), len(introduced))
                    if not resolved else "repair introduced new errors")

        if safety.get("require_revert", True) and not progress:
            revert_change(applied["backup"])
            reverted = True
            changed_files = []
            note += "; change reverted"

        entry = _history_entry(attempt, current_scene, plan, diagnosis,
                               [] if reverted else changed_files, validation,
                               before, after, "reverted" if reverted else "failed", reverted, note=note)
        attempt_record.update({"status": entry["status"], "runtime_after": after.get("status"),
                               "validation": validator_ok, "note": note})
        block["attempts"].append(attempt_record)
        block["attempts_used"] = attempt
        block["final_runtime_status"] = after.get("status")
        block["note"] = note
        block["changed_files"] = [] if reverted else changed_files
        if resolved_history is not None:
            block["history"].append(_write_history(entry, resolved_history))

        if not progress:
            if verbose:
                print("  Revert       %s" % ("PASS" if reverted else "SKIPPED"))
                print()
                print("Result: FAIL (%s)" % note)
            return report

    if verbose:
        print()
        print("Result: FAIL (max attempts %d reached)" % attempts_limit)
    block["note"] = block.get("note") or "max repair attempts reached"
    return report


# ---------- Asset domain helpers ----------

# 只有携带 res:// 资源路径证据的错误才可判定为 asset 域：
# 裸的 node_not_found 或 null_instance 一律不进 Asset Repair（宁可交还通用流程）。
_ASSET_CLASSIFICATIONS = {"resource_missing", "scene_load_error"}
_RESOURCE_TOKEN_RE = __import__("re").compile(r"res://[^\s'\"()]+\.(?:png|jpg|jpeg|webp|svg|wav|ogg|mp3|flac|ttf|otf|tres|res|gdshader)\b")


def _asset_diagnosis(diagnosis: dict, root: Path, scene: str) -> dict:
    """从 diagnosis 中提取 asset 域证据；无可靠证据时不在 asset 域。"""
    block = diagnosis.get("diagnosis") or {}
    for entry in block.get("errors") or []:
        if entry.get("classification") not in _ASSET_CLASSIFICATIONS:
            continue
        message = str(entry.get("message") or "")
        file_hint = str(entry.get("file") or "")
        # 证据 1：错误直接指向 Assets/ 下的资源文件
        match = _RESOURCE_TOKEN_RE.search(message) or _RESOURCE_TOKEN_RE.search(file_hint)
        if match and match.group(0).startswith("res://Assets/"):
            return {"domain": "asset", "classification": "asset_missing",
                    "related_asset": match.group(0),
                    "related_scene": scene,
                    "related_binding": _binding_for_scene(root, scene),
                    "confidence": entry.get("confidence") or "medium"}
        # 证据 2：场景 ext_resource 引用的资源在磁盘上缺失（Deterministic 校验）
        target_scene = file_hint or scene
        if target_scene.endswith(".tscn"):
            missing = _scene_missing_resource(root, target_scene)
            if missing:
                return {"domain": "asset", "classification": "asset_missing",
                        "related_asset": missing, "related_scene": scene,
                        "related_binding": _binding_for_scene(root, scene),
                        "confidence": "high"}
    return {"domain": "unknown"}


def _binding_for_scene(root: Path, scene: str) -> str:
    """scene -> 可能的绑定文档（确定性猜测，仅作记录用）。"""
    name = Path(str(scene).replace("res://", "").rstrip("/")).stem.lower()
    if not name:
        return ""
    candidate = root / ".ai" / "context" / "asset_bindings" / (name + ".yaml")
    return str(candidate) if candidate.is_file() else ""


def _scene_missing_resource(root: Path, scene: str) -> str:
    """检查场景 ext_resource 引用的 Assets/ 资源是否在磁盘上；返回第一个缺失者。"""
    rel = str(scene).replace("res://", "")
    path = root / rel.replace("/", os.sep)
    if not path.is_file():
        return ""
    import re as _re
    text = path.read_text(encoding="utf-8", errors="replace")
    for ref in _re.findall(r'^\[ext_resource[^\]]*path="(res://[^"]+)"', text, _re.M):
        disk = root / ref[len("res://"):].replace("/", os.sep)
        if not disk.exists():
            return ref
    return ""


def _run_asset_repair(root: Path, scene: str, asset_block: dict,
                      attempt: int = 1, verbose: bool = True) -> dict:
    """调用 Asset Repair Adapter 重建绑定（消费 asset_diagnosis 证据）。"""
    repair = repair_assets(root, scene)
    if verbose:
        mark = "PASS" if repair.get("ok") else "FAIL"
        print("  AssetRepair  %s  (%s)" % (mark, repair.get("reason") or ""))
        if repair.get("binding_path"):
            print("  Binding      %s" % repair["binding_path"])
        for role in repair.get("missing") or []:
            print("  Missing      %s" % role)
    return repair


def _relative_changed(root: Path, target: Path) -> str:
    try:
        return target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(target)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the Self-Repair loop for a Godot scene.")
    parser.add_argument("--scene", required=True, help="Scene reference, e.g. res://Scenes/EnemyBasic.tscn")
    parser.add_argument("--project", default=".", help="Godot project directory (contains project.godot)")
    parser.add_argument("--max-attempts", type=int, default=None,
                        help="Maximum repair attempts (default: runtime_playtest.max_repair_attempts)")
    parser.add_argument("--timeout", type=float, default=None, help="Playtest timeout in seconds")
    parser.add_argument("--history-dir", default=None, help="Repair history directory")
    parser.add_argument("--allow-medium", action="store_true",
                        help="Accept medium-confidence node candidates (default: high only)")
    parser.add_argument("--dry-run", action="store_true", help="Diagnose and plan only, never modify the project")
    parser.add_argument("--out", default="", help="Write the self-repair report JSON to this path")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--save-logs", action="store_true", help="Also save raw playtest logs")
    args = parser.parse_args(argv)

    try:
        report = self_repair(
            project=args.project,
            scene=args.scene,
            max_attempts=args.max_attempts,
            timeout=args.timeout,
            history_dir=args.history_dir,
            allow_medium=args.allow_medium,
            dry_run=args.dry_run,
            write_logs=True if args.save_logs else False,
            verbose=not args.json,
        )
    except RuntimeInputError as exc:
        print("FAIL: %s" % exc)
        return 2

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("self-repair report written: %s" % args.out)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["self_repair"]["status"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
