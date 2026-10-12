#!/usr/bin/env python3
"""Runtime Diagnosis —— 把 Runtime Result 翻译成可执行的诊断。

输入: runtime_result.json（见 .ai/context/runtime_result_schema.yaml）
输出: diagnosis（错误分类 + 位置 + likely_cause + 相关 Feature / Scene + confidence）

职责边界：
    - 只做「分类」与「定位」；分类来源是 capture_output 抽取的事实（patterns /
      script / line / resource）加上确定性规则表，不做自由推测。
    - 无法归类时输出 unknown_runtime_error，禁止编造原因。
    - 不修改项目（修复属于 repair_plan.py / self_repair.py）。

错误分类（classification）：
    scene_load_error        被验证的 Scene 本身加载失败（含场景文件不存在）
    script_error            脚本运行期错误，且无法归入更具体的分类
    node_not_found          Node not found（节点路径无效）
    resource_missing        资源缺失（依赖场景 / 资源 / 脚本加载失败）
    signal_error            信号相关错误
    null_instance           null instance（引用未初始化或已释放）
    invalid_property        属性 / 索引 / 赋值非法
    invalid_method          方法 / 函数调用非法
    parser_error            GDScript 解析 / 编译错误
    timeout                 场景未交还控制权（被超时终止）
    crash                   进程异常退出且无可解析错误
    unknown_runtime_error   无法判断

用法:
    python diagnose_runtime.py <runtime_result.json> [--project .] [--out diagnosis.yaml] [--json]

作为模块导入:
    from diagnose_runtime import diagnose
    diagnosis = diagnose(runtime_result, project_root)

退出码: 0 = 诊断完成（含诊断出失败）；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from capture_output import PATTERNS                                  # noqa: E402
from runtime_result import (                                          # noqa: E402
    STATUS_CRASH,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_TIMEOUT,
    find_project_root,
    read_result,
)

CLASSIFICATIONS = (
    "scene_load_error",
    "script_error",
    "node_not_found",
    "resource_missing",
    "signal_error",
    "null_instance",
    "invalid_property",
    "invalid_method",
    "parser_error",
    "timeout",
    "crash",
    "unknown_runtime_error",
)

UNKNOWN = "unknown_runtime_error"

# 分类 -> 确定性 likely_cause（禁止自由发挥；不在表内即 unknown）
LIKELY_CAUSE = {
    "scene_load_error": "missing_or_broken_scene",
    "script_error": "gdscript_runtime_error",
    "node_not_found": "invalid_node_path",
    "resource_missing": "missing_or_mispathed_resource",
    "signal_error": "signal_contract_mismatch",
    "null_instance": "uninitialized_or_missing_reference",
    "invalid_property": "unknown_property_or_type_mismatch",
    "invalid_method": "unknown_method_or_missing_base",
    "parser_error": "gdscript_compile_error",
    "timeout": "scene_never_returns_control",
    "crash": "engine_or_process_crash",
    UNKNOWN: "undetermined",
}

# 分类 -> 是否存在确定性的自动修复策略（真正可行性由 repair_plan.py 复核）
REPAIR_STRATEGY = {
    "node_not_found": "node_path_literal",
}

# 主错误选择优先级（越靠前越具体；仅用于排序，不用于分类）
PRIMARY_PRIORITY = (
    "timeout",
    "crash",
    "scene_load_error",
    "node_not_found",
    "parser_error",
    "invalid_property",
    "invalid_method",
    "null_instance",
    "signal_error",
    "resource_missing",
    "script_error",
    "crash",
    UNKNOWN,
)

RESOURCE_TOKEN_RE = re.compile(r"res://[^\s'\"()]+")
SCRIPT_LOCATION_RE = re.compile(r"res://[^\s:]*\.(?:gd|cs|gdshader|gdshaderinc)\b")
SCENE_EXT_RE = re.compile(r"\.tscn\b|\.scn\b")


def _patterns_of(entry: dict) -> set[str]:
    patterns = entry.get("patterns")
    if isinstance(patterns, list) and patterns:
        return set(str(p) for p in patterns)
    text = "%s %s" % (entry.get("message") or "", entry.get("detail") or "")
    return {name for name, rx in PATTERNS.items() if re.search(rx, text)}


def _first_resource(message: str) -> str:
    match = RESOURCE_TOKEN_RE.search(message or "")
    return match.group(0).rstrip(".,;") if match else ""


def classify_entry(entry: dict, scene: str = "") -> str:
    """把一条运行时事件分类为 classification（规则表，按优先级短路）。"""
    patterns = _patterns_of(entry)
    message = (entry.get("message") or "").strip()
    text = "%s %s" % (message, entry.get("detail") or "")

    # 1. 资源 / 场景加载
    if "resource_missing" in patterns:
        resource = _first_resource(message)
        if message.startswith("Scene not found in project"):
            return "scene_load_error"
        if resource and scene and resource == scene:
            return "scene_load_error"
        if not resource and SCENE_EXT_RE.search(message) and scene:
            return "scene_load_error"
        return "resource_missing"
    # 2. 节点路径
    if "node_not_found" in patterns:
        return "node_not_found"
    # 3. 解析 / 编译
    if "parser_error" in patterns:
        return "parser_error"
    # 4. 空引用（先于 invalid_property：null 是根因，属性非法是表现）
    if "null_instance" in patterns:
        return "null_instance"
    # 5. 方法 / 函数调用
    if "invalid_call" in patterns or "unknown_function" in patterns:
        return "invalid_method"
    # 6. 属性 / 索引 / 赋值
    if patterns & {"invalid_get_index", "invalid_set_index", "invalid_assignment", "invalid_access"}:
        return "invalid_property"
    # 7. 信号
    if "signal_error" in patterns:
        return "signal_error"
    # 8. 其它 SCRIPT ERROR
    if entry.get("type") == "script_error":
        return "script_error"
    if "crash" in patterns:
        return "crash"
    return UNKNOWN


def _confidence(classification: str, entry: dict) -> str:
    located = bool(entry.get("script") or entry.get("resource")) and bool(entry.get("line"))
    if classification == UNKNOWN:
        return "low"
    if classification == "script_error":
        return "high" if located else "medium"
    return "high" if located else "medium"


# ---------- 相关 Feature / Scene 定位 ----------

FEATURE_SCRIPT_RE = re.compile(r"^res://Features/([^/]+)/")
FEATURE_SCENE_RE = re.compile(r"^res://Features/([^/]+)/[^/]*\.tscn$")
EXT_RESOURCE_RE = re.compile(r'^\[ext_resource[^\]]*path="([^"]+)"', re.M)


def related_feature(project_root: Path, entry: dict) -> str:
    """错误位置属于哪个 Feature（Features/<id>/...）。"""
    for key in ("script", "resource"):
        path = str(entry.get(key) or "")
        if not path:
            continue
        match = FEATURE_SCRIPT_RE.match(path) or FEATURE_SCENE_RE.match(path)
        if match:
            return match.group(1)
    return ""


def _scenes_referencing(project_root: Path, script: str, scene: str = "") -> list[str]:
    """列出引用了该脚本的 .tscn（相对 res://），验证场景优先。"""
    if not script:
        return []
    candidates: list[Path] = []
    preferred = None
    if scene.startswith("res://"):
        preferred = project_root / scene[len("res://"):].replace("/", os.sep)
        candidates.append(preferred)
    for base in ("Scenes", "Features", "Tests"):
        directory = project_root / base
        if directory.is_dir():
            candidates.extend(sorted(directory.rglob("*.tscn")))
    hits: list[str] = []
    needle = script
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if needle in text:
            hits.append("res://" + path.relative_to(project_root).as_posix())
    return hits


def related_scene(project_root: Path, entry: dict, scene: str) -> str:
    """错误位置归属的场景：优先被验证场景，其次引用该脚本的场景。"""
    resource = str(entry.get("resource") or "")
    if resource:
        return resource
    script = str(entry.get("script") or "")
    if script:
        hits = _scenes_referencing(project_root, script, scene)
        if scene and scene in hits:
            return scene
        if hits:
            return hits[0]
    return scene


def feature_of_scene(project_root: Path, scene: str) -> str:
    """场景若只引用单一 Feature 场景，则该 Feature 为相关 Feature。"""
    if not scene.startswith("res://"):
        return ""
    path = project_root / scene[len("res://"):].replace("/", os.sep)
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    features = sorted({
        match.group(1)
        for ref in EXT_RESOURCE_RE.findall(text)
        for match in [FEATURE_SCENE_RE.match(ref)]
        if match
    })
    return features[0] if len(features) == 1 else ""


# ---------- 诊断 ----------


def _diagnose_entry(entry: dict, project_root: Path, scene: str) -> dict:
    classification = str(entry.get("classification") or "") or classify_entry(entry, scene)
    if classification not in CLASSIFICATIONS:
        classification = UNKNOWN
    file_path = str(entry.get("script") or entry.get("resource") or "")
    feature = related_feature(project_root, entry) or feature_of_scene(project_root, scene)
    return {
        "type": classification,
        "classification": classification,
        "severity": str(entry.get("severity") or "error"),
        "message": str(entry.get("message") or "").strip(),
        "file": file_path,
        "line": int(entry.get("line") or 0),
        "likely_cause": LIKELY_CAUSE.get(classification, LIKELY_CAUSE[UNKNOWN]),
        "related_feature": feature,
        "related_scene": related_scene(project_root, entry, scene),
        "confidence": _confidence(classification, entry),
        "repair_strategy": REPAIR_STRATEGY.get(classification, ""),
        "repeat": int(entry.get("repeat") or 1),
        "source": str(entry.get("source") or ""),
    }


def _status_classification(result: dict, scene: str) -> str:
    if result.get("timeout") or result.get("status") == STATUS_TIMEOUT:
        return "timeout"
    if result.get("crash") or result.get("status") == STATUS_CRASH:
        return "crash"
    return ""


def diagnose(result: dict, project_root: str | os.PathLike | None = None,
             scene: str = "") -> dict[str, Any]:
    """把 runtime_result 转成 diagnosis（只读，不修改项目）。"""
    root = Path(project_root).resolve() if project_root else find_project_root() or Path.cwd()
    status = str(result.get("status") or "")
    scene = scene or str(result.get("scene") or "")

    errors: list[dict] = []
    for entry in result.get("errors") or []:
        if isinstance(entry, dict):
            errors.append(_diagnose_entry(entry, root, scene))

    warnings: list[dict] = []
    for entry in result.get("warnings") or []:
        if isinstance(entry, dict):
            diagnosed = _diagnose_entry(entry, root, scene)
            diagnosed["severity"] = "warning"
            diagnosed["type"] = classify_entry(entry, scene)
            diagnosed["classification"] = diagnosed["type"]
            warnings.append(diagnosed)

    status_class = _status_classification(result, scene)
    extra: list[dict] = []
    if status_class:
        extra.append({
            "type": status_class,
            "classification": status_class,
            "severity": "error",
            "message": ("runtime playtest exceeded timeout (%ss)" % result.get("duration")
                        if status_class == "timeout"
                        else "process exited abnormally without a parseable error (exit_code=%s)"
                             % result.get("exit_code")),
            "file": "",
            "line": 0,
            "likely_cause": LIKELY_CAUSE[status_class],
            "related_feature": feature_of_scene(root, scene),
            "related_scene": scene,
            "confidence": "high",
            "repair_strategy": REPAIR_STRATEGY.get(status_class, ""),
            "repeat": 1,
            "source": "runner",
        })
    errors.extend(extra)

    def sort_key(item: dict) -> tuple:
        try:
            rank = PRIMARY_PRIORITY.index(item["type"])
        except ValueError:
            rank = len(PRIMARY_PRIORITY)
        located = 0 if (item.get("file") and item.get("line")) else 1
        return (rank, located)

    errors.sort(key=sort_key)

    failed = status in (STATUS_FAIL, STATUS_TIMEOUT, STATUS_CRASH) or bool(errors)
    diagnosis = {
        "diagnosis": {
            "status": "failed" if failed else "passed",
            "playtest_status": status or STATUS_PASS,
            "scene": scene,
            "project": str(root),
            "primary_classification": errors[0]["type"] if errors else "",
            "repairable": bool(errors and REPAIR_STRATEGY.get(errors[0]["type"])),
            "errors": errors,
            "warnings": warnings,
            "unknown_count": sum(1 for e in errors if e["type"] == UNKNOWN),
        }
    }
    return diagnosis


def diagnosis_to_yaml(diagnosis: dict) -> str:
    return yaml.safe_dump(diagnosis, sort_keys=False, allow_unicode=True, width=4096)


def print_diagnosis(diagnosis: dict) -> None:
    block = diagnosis["diagnosis"]
    print("Runtime Diagnosis")
    print("Scene:  %s" % (block.get("scene") or "<project main scene>"))
    print("Status: %s (playtest=%s)" % (block.get("status"), block.get("playtest_status")))
    print("Errors: %d, warnings: %d, unclassified: %d"
          % (len(block.get("errors") or []), len(block.get("warnings") or []), block.get("unknown_count", 0)))
    for entry in block.get("errors") or []:
        location = entry.get("file") or "<engine>"
        if entry.get("line"):
            location += ":%d" % entry["line"]
        print("  - type=%s confidence=%s" % (entry["type"], entry["confidence"]))
        print("      message:        %s" % entry["message"])
        print("      file:           %s" % location)
        print("      likely_cause:   %s" % entry["likely_cause"])
        print("      related_feature:%s" % (" " + entry["related_feature"] if entry["related_feature"] else " <none>"))
        print("      related_scene:  %s" % (entry["related_scene"] or "<none>"))
    for entry in block.get("warnings") or []:
        print("  - warning type=%s: %s" % (entry["type"], entry["message"]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose a runtime_result.json.")
    parser.add_argument("result", help="runtime_result JSON path")
    parser.add_argument("--project", default="", help="Project root (default: derived from the result)")
    parser.add_argument("--out", default="", help="Write diagnosis YAML to this path")
    parser.add_argument("--json", action="store_true", help="Print diagnosis as JSON")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.result):
        print("FAIL: runtime_result not found: %s" % args.result)
        return 2
    result = read_result(args.result)
    project = args.project or str(result.get("project") or "")
    diagnosis = diagnose(result, project or None)

    if args.out:
        Path(args.out).write_text(diagnosis_to_yaml(diagnosis), encoding="utf-8")
        print("diagnosis written: %s" % args.out)
    if args.json:
        print(json.dumps(diagnosis, indent=2, ensure_ascii=False))
    else:
        print_diagnosis(diagnosis)
    return 0


if __name__ == "__main__":
    sys.exit(main())
