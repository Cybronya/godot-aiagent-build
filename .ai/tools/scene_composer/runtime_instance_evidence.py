#!/usr/bin/env python3
"""Runtime Instance Evidence (Phase 1.39) —— 加载后的实例证据。

Phase 1.38 的静态对账只能证明「`.tscn` 文件里写了什么」。本模块补上第四层证据：
**Godot 真实加载场景后对象树里有什么**。

证据层级（四层，不得互相顶替）：

    1. 文件解析      `.tscn` 文本可解析            → static：INSTANCE_SCENE_UNPARSEABLE
    2. 资源加载      PackedScene 能被 Godot 加载       → runtime：reason=load_error
    3. 节点实际存在  加载后的对象树里有目标节点       → runtime：reason=missing / type_mismatch /
                                                        count_mismatch / missing_after_timeout
    4. 行为正确      节点的运行行为符合预期            → **不在本阶段**（e2e / behavior probe）

契约来源（向后兼容的最小扩展）：

    Features/<id>/template.yaml

    instance:
      node_type: Area2D
      children: [CollisionShape2D]
      runtime_children: [CollisionShape2D]   # 静态无法确认、由脚本在运行时创建（1.38 语义）
      runtime:                              # 1.39 新增：要求运行时证据
        when: after_load                    # after_load | after_frames:<N> | after_action:<name>
        timeout_frames: 30                  # 轮询窗口（帧）；0 = 不轮询
        scene: res://...                    # 可选，默认模板入口场景
        expectations:                       # 可选，默认由 node_type/children 推导
          - {path: "PickupShape", type: CollisionShape2D, count: 1}

结果状态（与 instance_evidence 同一套语义）：

    PASS          在观察时机 / 轮询窗口内，运行时对象树满足契约
    MISMATCH      运行时证据与契约明确冲突（加载失败 / 缺失 / 类型 / 数量）
    INSUFFICIENT  无法下结论（Godot 缺失、探针超时、动作未触发、采集失败）
    INVALID       运行时契约本身无效
    NOT_DECLARED  未声明 runtime:（不凭空要求运行时证据）

`runtime_children` 的含义（1.39 重新界定）：
    它解释「为什么静态证据看不到」，**不**证明运行时存在。要证明存在必须在 `runtime:`
    块下给出观察时机；缺失会在轮询窗口结束后报 `missing_after_timeout`（只说明窗口内未出现，
    不声称永不存在）。需要动作才生成的节点写 `when: after_action:<name>`，本模块**不会**
    自动触发游戏动作，直接返回 `INSUFFICIENT`。

本模块 MUST NOT：
    - 用 YAML 声明 / 静态解析 / 生成器的预期对象伪造运行时证据。
    - 采集失败时返回 PASS。
    - 修改项目文件或场景；只写 `.ai/tmp/runtime-instance/<run_id>/` 下的证据文件。

契约：.ai/context/scene_composer_schema.yaml#runtime_instance_evidence

用法:
    python .ai/tools/scene_composer/runtime_instance_evidence.py --feature collect_pickup
    python .ai/tools/scene_composer/runtime_instance_evidence.py --all
    python .ai/tools/scene_composer/runtime_instance_evidence.py --all --require-runtime --json

退出码：0 = PASS / NOT_DECLARED（`--require-runtime` 下 INSUFFICIENT 也算失败）；
        1 = MISMATCH / INVALID / 需要证据时的 INSUFFICIENT；2 = 输入错误。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_DOTAI = os.path.dirname(_TOOLS)
PROJECT_ROOT = os.path.dirname(_DOTAI)

for _path in (_HERE, _TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import component_instance_resolver                            # noqa: E402
import instance_evidence                                      # noqa: E402
import template_loader                                        # noqa: E402

MODULE_VERSION = 1
PROBE_RES = "res://.ai/tools/scene_composer/probes/instance_runtime_probe.gd"
PROBE_PATH = os.path.join(_HERE, "probes", "instance_runtime_probe.gd")
EVIDENCE_ROOT = os.path.join(_DOTAI, "tmp", "runtime-instance")
RESULT_PREFIX = "EVIDENCE_RESULT: "

STATUS_PASS = instance_evidence.STATUS_PASS
STATUS_MISMATCH = instance_evidence.STATUS_MISMATCH
STATUS_INSUFFICIENT = instance_evidence.STATUS_INSUFFICIENT
STATUS_INVALID = instance_evidence.STATUS_INVALID
STATUS_NOT_DECLARED = instance_evidence.STATUS_NOT_DECLARED

EVIDENCE_RUNTIME = "godot_runtime"

DEFAULT_TIMEOUT_FRAMES = 0
MAX_TIMEOUT_FRAMES = 600
DEFAULT_PROCESS_TIMEOUT = 90

WHEN_AFTER_LOAD = "after_load"
WHEN_AFTER_FRAMES = "after_frames"
WHEN_AFTER_ACTION = "after_action"

# 资源 / 脚本加载失败（Godot 在场景部分损坏时仍会「加载成功」并继续运行，
# 所以必须读 stderr 才能识别这类失败；这是真实证据，不是字符串猜测）。
LOAD_ERROR_MARKERS = (
    "Failed loading resource:",
    "referenced non-existent resource",
    "Attempt to open script",
    "Failed to load resource",
    "Cannot open file",
)
SCRIPT_ERROR_MARKERS = ("SCRIPT ERROR:",)

GODOT_CANDIDATES = (
    "Godot_v4.7-stable_win64_console.exe",
    "Godot_v4.7-stable_win64.exe",
)


class RuntimeEvidenceReport:
    """一次运行时核验的结论（结构化、可序列化）。"""

    def __init__(self, feature: str = "", scene: str = "", run_id: str = ""):
        self.feature = feature
        self.scene = scene
        self.run_id = run_id
        self.status = STATUS_NOT_DECLARED
        self.reason = ""
        self.detail = ""
        self.checks = []
        self.observed_frame = None
        self.waited_frames = None
        self.duration = 0.0
        self.evidence = EVIDENCE_RUNTIME
        self.errors = []
        self.notes = []
        self.artifacts = {}

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "scene": self.scene,
            "run_id": self.run_id,
            "status": self.status,
            "reason": self.reason,
            "detail": self.detail,
            "evidence": self.evidence,
            "checks": [dict(check) for check in self.checks],
            "observed_frame": self.observed_frame,
            "waited_frames": self.waited_frames,
            "duration_s": round(self.duration, 3),
            "errors": list(self.errors),
            "notes": list(self.notes),
            "artifacts": dict(self.artifacts),
        }

    @property
    def ok(self) -> bool:
        return self.status in (STATUS_PASS, STATUS_NOT_DECLARED)

    def __repr__(self) -> str:  # pragma: no cover - 调试
        return "<RuntimeEvidenceReport %s %s %s>" % (
            self.feature, self.status, self.reason)


# ---------------------------------------------------------------- 契约构建

def _runtime_config(declaration: dict):
    """声明 -> runtime 配置；缺失返回 None（NOT_DECLARED）。"""
    if not isinstance(declaration, dict):
        return None
    runtime = declaration.get("runtime")
    return runtime if isinstance(runtime, dict) else None


def _parse_when(raw, errors: list) -> str:
    text = str(raw if raw is not None else WHEN_AFTER_LOAD).strip()
    if text == WHEN_AFTER_LOAD:
        return WHEN_AFTER_LOAD
    for prefix in (WHEN_AFTER_FRAMES, WHEN_AFTER_ACTION):
        marker = prefix + ":"
        if not text.startswith(marker):
            continue
        value = text[len(marker):].strip()
        if prefix == WHEN_AFTER_ACTION:
            if value:
                return text
        else:
            if value.isdigit() and 0 <= int(value) <= MAX_TIMEOUT_FRAMES:
                return text
    errors.append("Invalid runtime contract: when %r (expected after_load | "
                  "after_frames:<0..%d> | after_action:<name>)" % (text, MAX_TIMEOUT_FRAMES))
    return ""


def _expectation(entry, index: int, errors: list) -> dict:
    where = "expectations[%d]" % index
    if not isinstance(entry, dict):
        errors.append("Invalid runtime contract: %s must be a mapping" % where)
        return {}
    node_type = str(entry.get("type") or "").strip()
    if not node_type or not component_instance_resolver.is_known_instance_type(node_type):
        errors.append("Invalid runtime contract: %s.type %r is not a known node type"
                      % (where, entry.get("type")))
        return {}
    try:
        count = int(entry.get("count", 1))
    except (TypeError, ValueError):
        errors.append("Invalid runtime contract: %s.count must be an integer" % where)
        return {}
    if count < 1 or count > 64:
        errors.append("Invalid runtime contract: %s.count out of range (1..64)" % where)
        return {}
    path = entry.get("path")
    parent = entry.get("parent")
    if path is not None and (not isinstance(path, str) or not path.strip()):
        errors.append("Invalid runtime contract: %s.path must be a non-empty string" % where)
        return {}
    if parent is not None and (not isinstance(parent, str) or not parent.strip()):
        errors.append("Invalid runtime contract: %s.parent must be a non-empty string" % where)
        return {}
    if path is not None and parent is not None:
        errors.append("Invalid runtime contract: %s cannot set both path and parent" % where)
        return {}
    if path is None and parent is None:
        parent = "."
    return {
        "id": str(entry.get("id") or ("%s#%d" % (node_type, index))),
        "type": node_type,
        "count": count,
        "runtime": bool(entry.get("runtime", False)),
        "path": path.strip() if isinstance(path, str) else "",
        "parent": parent.strip() if isinstance(parent, str) else "",
    }


def _derived_expectations(declaration: dict) -> list:
    """未显式给出 expectations 时，从 node_type / children 推导（与静态对账同口径）。"""
    from collections import Counter

    children = [str(item).strip() for item in (declaration.get("children") or [])]
    runtime_children = {str(item).strip() for item in (declaration.get("runtime_children") or [])}
    expectations = [{"id": "root", "path": ".", "type": str(declaration.get("node_type") or ""),
                     "count": 1, "runtime": False}]
    for index, (child_type, count) in enumerate(sorted(Counter(children).items())):
        expectations.append({"id": "%s#%d" % (child_type, index), "parent": ".",
                             "type": child_type, "count": count,
                             "runtime": child_type in runtime_children})
    return expectations


def build_contract(feature: str, features_dir: str = instance_evidence.FEATURES_DIR,
                   run_id: str = "") -> tuple:
    """Feature -> (contract|None, report)。契约非法时返回 INVALID 报告。"""
    report = RuntimeEvidenceReport(feature=feature, run_id=run_id)
    template = template_loader.load_template(feature, features_dir)
    declaration = template_loader.feature_instance_plan(feature, features_dir)
    scene_res = template_loader.template_scene_path(feature, template, features_dir)
    report.scene = scene_res

    runtime = _runtime_config(declaration)
    if runtime is None:
        report.status = STATUS_NOT_DECLARED
        report.reason = "runtime_not_declared"
        report.detail = "no instance.runtime block: runtime evidence not required"
        return None, report

    errors = []
    when = _parse_when(runtime.get("when"), errors)
    raw_timeout = runtime.get("timeout_frames", DEFAULT_TIMEOUT_FRAMES)
    if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, int):
        errors.append("Invalid runtime contract: timeout_frames must be an integer")
        timeout_frames = DEFAULT_TIMEOUT_FRAMES
    elif not 0 <= raw_timeout <= MAX_TIMEOUT_FRAMES:
        errors.append("Invalid runtime contract: timeout_frames out of range (0..%d)"
                      % MAX_TIMEOUT_FRAMES)
        timeout_frames = DEFAULT_TIMEOUT_FRAMES
    else:
        timeout_frames = raw_timeout

    scene_override = runtime.get("scene")
    if scene_override is not None:
        if not isinstance(scene_override, str) or not scene_override.startswith("res://"):
            errors.append("Invalid runtime contract: scene must be a res:// path")
        else:
            scene_res = scene_override.strip()

    raw_expectations = runtime.get("expectations")
    if raw_expectations is None:
        expectations = _derived_expectations(declaration)
    elif not isinstance(raw_expectations, list) or not raw_expectations:
        errors.append("Invalid runtime contract: expectations must be a non-empty list")
        expectations = []
    else:
        expectations = [_expectation(entry, index, errors)
                        for index, entry in enumerate(raw_expectations)]
        expectations = [entry for entry in expectations if entry]

    if not declaration.get("node_type"):
        errors.append("Invalid runtime contract: instance.node_type is required")

    report.scene = scene_res
    if errors:
        report.status = STATUS_INVALID
        report.reason = "contract_invalid"
        report.detail = errors[0]
        report.errors = errors
        return None, report

    contract = {
        "scene": scene_res,
        "when": when,
        "timeout_frames": timeout_frames,
        "expectations": expectations,
        "run_id": run_id or _new_run_id(),
        "feature": feature,
    }
    report.run_id = contract["run_id"]
    return contract, report


# ---------------------------------------------------------------- Godot 启动

def _new_run_id() -> str:
    return "%d-%s" % (os.getpid(), uuid.uuid4().hex[:8])


def find_godot(project_root: str = PROJECT_ROOT) -> str:
    """定位 Godot 可执行文件（console 优先）；找不到返回空串。"""
    root = project_root or PROJECT_ROOT
    for name in GODOT_CANDIDATES:
        candidate = os.path.join(os.path.dirname(root), name)
        if os.path.isfile(candidate):
            return candidate
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return found
    return ""


def _evidence_dir(run_id: str) -> str:
    return os.path.join(EVIDENCE_ROOT, run_id)


def run_probe(contract: dict, project_root: str = PROJECT_ROOT,
              timeout_s: int = DEFAULT_PROCESS_TIMEOUT,
              godot: str = "") -> dict:
    """启动 Godot 探针 -> 原始观测（stdout/stderr/exit/result/duration）。

    不做状态判定（判定归 verify_contract）；采集失败时 result=None。
    """
    run_id = str(contract.get("run_id") or _new_run_id())
    directory = _evidence_dir(run_id)
    os.makedirs(directory, exist_ok=True)
    contract_path = os.path.join(directory, "contract.json")
    result_path = os.path.join(directory, "result.json")
    with open(contract_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(contract, handle, ensure_ascii=False, indent=2)

    observation = {"run_id": run_id, "godot": godot, "command": [],
                   "exit_code": None, "stdout": "", "stderr": "", "result": None,
                   "duration": 0.0, "timed_out": False, "artifacts": {
                       "contract": contract_path, "result": result_path}}
    if not godot:
        observation["stderr"] = "godot executable not found"
        return observation

    project_root = os.path.abspath(project_root or PROJECT_ROOT)
    command = [godot, "--headless", "--path", project_root, "-s", PROBE_RES,
               "--", "--contract=%s" % os.path.abspath(contract_path),
               "--result=%s" % os.path.abspath(result_path)]
    observation["command"] = command
    started = time.time()
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout_s,
                              stdin=subprocess.DEVNULL, cwd=project_root)
        observation["exit_code"] = proc.returncode
        observation["stdout"] = proc.stdout or ""
        observation["stderr"] = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        observation["timed_out"] = True
        observation["stdout"] = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        observation["stderr"] = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        observation["stderr"] += "\nTIMEOUT after %ss" % timeout_s
    except OSError as exc:
        observation["stderr"] = "failed to start godot: %s" % exc
        observation["duration"] = time.time() - started
        return observation
    observation["duration"] = time.time() - started

    for name, text in (("stdout", observation["stdout"]), ("stderr", observation["stderr"])):
        path = os.path.join(directory, name + ".log")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        observation["artifacts"][name] = path

    payload = None
    if os.path.isfile(result_path):
        try:
            with open(result_path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            payload = None
    if payload is None:
        for line in observation["stdout"].splitlines():
            if line.startswith(RESULT_PREFIX):
                try:
                    payload = json.loads(line[len(RESULT_PREFIX):])
                except ValueError:
                    payload = None
                break
    observation["result"] = payload
    return observation


def _first_marker(text: str, markers) -> str:
    for line in (text or "").splitlines():
        for marker in markers:
            if marker in line:
                return line.strip()
    return ""


def judge(observation: dict, report: RuntimeEvidenceReport) -> RuntimeEvidenceReport:
    """原始观测 -> 结论（采集失败不得成为 PASS）。"""
    payload = observation.get("result")
    stderr = observation.get("stderr") or ""
    report.duration = float(observation.get("duration") or 0.0)
    report.artifacts = dict(observation.get("artifacts") or {})
    report.observed_frame = (payload or {}).get("observed_frame")
    report.waited_frames = (payload or {}).get("waited_frames")

    if observation.get("timed_out"):
        report.status = STATUS_INSUFFICIENT
        report.reason = "probe_timeout"
        report.detail = "probe did not finish within the process timeout"
        return report
    if payload is None:
        report.status = STATUS_INSUFFICIENT
        report.reason = "evidence_unavailable"
        detail = _first_marker(stderr, SCRIPT_ERROR_MARKERS + LOAD_ERROR_MARKERS)
        report.detail = "probe produced no machine-readable result" + (
            ": " + detail if detail else " (exit=%s)" % observation.get("exit_code"))
        return report
    if not isinstance(payload, dict):
        report.status = STATUS_INSUFFICIENT
        report.reason = "evidence_unavailable"
        report.detail = "probe result is not a JSON object"
        return report

    status = str(payload.get("status") or "")
    reason = str(payload.get("reason") or "")
    report.checks = list(payload.get("checks") or [])
    report.status = status if status in (STATUS_PASS, STATUS_MISMATCH,
                                         STATUS_INSUFFICIENT, STATUS_INVALID) else STATUS_INSUFFICIENT
    report.reason = reason or ("ok" if report.status == STATUS_PASS else "unknown")
    report.detail = str(payload.get("detail") or "")

    if report.status == STATUS_PASS:
        load_error = _first_marker(stderr, LOAD_ERROR_MARKERS)
        script_error = _first_marker(stderr, SCRIPT_ERROR_MARKERS)
        if load_error:
            report.status = STATUS_MISMATCH
            report.reason = "load_error"
            report.detail = load_error
        elif script_error:
            report.status = STATUS_MISMATCH
            report.reason = "script_error"
            report.detail = script_error

    if report.status == STATUS_MISMATCH and not report.detail:
        failing = [check for check in report.checks if check.get("status") != STATUS_PASS]
        if failing:
            report.detail = "; ".join(
                "%s %s (expected %s, found %s)" % (check.get("id"), check.get("status"),
                                                   check.get("expected_count"),
                                                   check.get("found_count"))
                for check in failing)
    return report


# ---------------------------------------------------------------- 核验入口

def verify_feature(feature: str, features_dir: str = instance_evidence.FEATURES_DIR,
                   project_root: str = "", godot: str = "",
                   timeout_s: int = DEFAULT_PROCESS_TIMEOUT,
                   runner=None) -> RuntimeEvidenceReport:
    """Feature -> 运行时证据报告（真实 Godot 加载；不伪造）。"""
    run_id = _new_run_id()
    contract, report = build_contract(feature, features_dir, run_id)
    if contract is None:
        return report
    if str(contract.get("when", "")).startswith(WHEN_AFTER_ACTION + ":"):
        report.status = STATUS_INSUFFICIENT
        report.reason = "action_not_triggerable"
        report.detail = ("contract requires action %s; this verifier never triggers game actions"
                         % contract["when"])
        return report

    root = project_root or os.path.dirname(os.path.abspath(features_dir))
    binary = godot or find_godot(root)
    probe = runner or run_probe
    observation = probe(contract, project_root=root, timeout_s=timeout_s, godot=binary)
    return judge(observation, report)


def declared_features(features_dir: str = instance_evidence.FEATURES_DIR) -> list:
    """声明了 instance.runtime 的 Feature（只读）。"""
    names = []
    for feature in instance_evidence.declared_features(features_dir):
        declaration = template_loader.feature_instance_plan(feature, features_dir)
        if _runtime_config(declaration) is not None:
            names.append(feature)
    return names


def verify_all(features_dir: str = instance_evidence.FEATURES_DIR,
               project_root: str = "", godot: str = "",
               timeout_s: int = DEFAULT_PROCESS_TIMEOUT) -> list:
    return [verify_feature(feature, features_dir, project_root, godot, timeout_s)
            for feature in declared_features(features_dir)]


def summarize(reports) -> dict:
    counts = {}
    for report in reports:
        counts[report.status] = counts.get(report.status, 0) + 1
    return {"checked": len(reports),
            "pass": counts.get(STATUS_PASS, 0),
            "mismatch": counts.get(STATUS_MISMATCH, 0),
            "insufficient": counts.get(STATUS_INSUFFICIENT, 0),
            "invalid": counts.get(STATUS_INVALID, 0),
            "not_declared": counts.get(STATUS_NOT_DECLARED, 0)}


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify Feature instance declarations against "
                                                 "a real Godot scene load.")
    parser.add_argument("--feature", action="append", default=[], help="Feature id (repeatable)")
    parser.add_argument("--all", action="store_true", help="all Features declaring instance.runtime")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--require-runtime", action="store_true",
                        help="treat INSUFFICIENT as failure (final acceptance gate)")
    parser.add_argument("--features-dir", default=instance_evidence.FEATURES_DIR)
    parser.add_argument("--project-root", default="")
    parser.add_argument("--godot", default="")
    parser.add_argument("--timeout", type=int, default=DEFAULT_PROCESS_TIMEOUT)
    parser.add_argument("--keep", action="store_true", help="keep evidence files (default keeps)")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.features_dir):
        print("FAIL: features dir not found: %s" % args.features_dir)
        return 2
    targets = args.feature or (declared_features(args.features_dir) if args.all else [])
    if not targets:
        print("FAIL: give --feature <id> or --all")
        return 2

    reports = [verify_feature(feature, args.features_dir, args.project_root,
                              args.godot, args.timeout) for feature in targets]

    if args.json:
        print(json.dumps({"summary": summarize(reports),
                          "reports": [report.to_dict() for report in reports]},
                         ensure_ascii=False, indent=2))
    else:
        print("Runtime Instance Evidence")
        for report in reports:
            print("  %-18s %-12s %s%s" % (
                report.feature, report.status, report.reason,
                "" if not report.detail else "  | " + report.detail))
            for check in report.checks:
                if check.get("status") != STATUS_PASS:
                    print("    - %s %s (expected %s, found %s) paths=%s" % (
                        check.get("id"), check.get("status"),
                        check.get("expected_count"), check.get("found_count"),
                        check.get("found_paths")))
        summary = summarize(reports)
        print("\n  pass=%d mismatch=%d insufficient=%d invalid=%d not_declared=%d" % (
            summary["pass"], summary["mismatch"], summary["insufficient"],
            summary["invalid"], summary["not_declared"]))
        print("  evidence: %s" % (reports[0].artifacts.get("contract", "").rsplit(os.sep, 1)[0]
                                  if reports else ""))

    failed = [report for report in reports
              if report.status in (STATUS_MISMATCH, STATUS_INVALID)
              or (args.require_runtime and report.status == STATUS_INSUFFICIENT)]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
