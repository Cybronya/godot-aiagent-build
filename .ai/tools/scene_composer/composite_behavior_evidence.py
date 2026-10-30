#!/usr/bin/env python3
"""Composite Scene Behavior Evidence（Phase 1.46）—— 组合场景端到端行为证据。

Phase 1.40–1.45 的行为证据证明「单个 Feature 的动作 → 后置状态/事件符合契约」。
它无法证明「多个 Feature 在同一个真实场景里通过 [connection] 与物理交互连成一条链」：

    - 契约只能挂在 Feature 上（`behavior[].scene` 限制在 `Features/<f>/` 内）；
    - 形状是「一组动作 + 一个窗口」，没有阶段，无法把中间状态当作证据；
    - 链只完成一部分时没有阶段级失败记录。

本模块在**组合场景**（`Scenes/*.tscn`，由组合协议白名单登记）里按阶段执行受限动作：

    阶段 1  输入驱动尝试穿越 → 被门真实阻挡（位置 + 门状态 + 0 次开门事件）
    阶段 2  只触发开关 A      → 条件未满足、门仍关闭、0 次开门事件
    阶段 3  触发开关 B        → 聚合满足、门打开、恰好 1 次事件（带参数）
    阶段 4  同一输入再次穿越  → 真实越过原门口位置（唯一变化是门开了）

阶段边界即事件顺序：阶段 N 的断言在阶段 N+1 的动作之前求值，信号计数跨阶段累计。
因此「阶段 2 时为 0、阶段 3 时为 1」同时证明了次数与先后，不需要额外的顺序断言。

能力来源（不复制定义）：

    behavior_protocol.yaml           → 动作 / 观测 / 信号（唯一权威）
    composite_behavior_protocol.yaml → 场景白名单 / 阶段预算 / 禁止动作

结果状态（与行为证据同一套词汇）：

    PASS          每一阶段都真实执行并成立（completed_stages == stages）
    MISMATCH      某阶段观测到与契约冲突的状态/事件（记录 failed_stage）
    INSUFFICIENT  动作入口不可用、前置条件不满足、观测不可用、采集失败、重放不一致
    INVALID       契约 / 协议 / 场景路径非法（不启动 Godot）

资源所有权（Phase 1.32 / 1.34 契约的延续）：

    - 每次 CLI 调用拥有一个 run_id 与一个隔离项目副本
      `.ai/tmp/composite/workspaces/<run_id>/`；
    - 副本根由本运行独占创建（exist_ok=False）并写入 `owner.json`；
    - 只有 `owner.json` 的 run_id 与本运行一致时才删除；否则保留并报告原因；
    - 其他运行的目录只报告、绝不删除；证据目录 `.ai/tmp/composite/<run_id>/` 保留。

用法:
    python .ai/tools/scene_composer/composite_behavior_evidence.py --scene escape_room
    python .ai/tools/scene_composer/composite_behavior_evidence.py --all --json
    python .ai/tools/scene_composer/composite_behavior_evidence.py --all --require-composite

退出码：0 = PASS；1 = MISMATCH / INVALID（或 --require-composite 时的 INSUFFICIENT）；
        2 = 输入错误。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_DOTAI = os.path.dirname(_TOOLS)
PROJECT_ROOT = os.path.dirname(_DOTAI)

for _path in (_HERE, _TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import behavior_protocol                                          # noqa: E402
import composite_behavior_protocol as composite_protocol          # noqa: E402
import instance_evidence                                          # noqa: E402
import runtime_instance_evidence as runtime_evidence              # noqa: E402

MODULE_VERSION = 1
PROBE_RES = composite_protocol.PROBE_RES
PROBE_PATH = os.path.join(_HERE, "probes", "composite_behavior_probe.gd")
EVIDENCE_ROOT = os.path.join(_DOTAI, "tmp", "composite")
RESULT_PREFIX = "COMPOSITE_RESULT: "
OWNER_FILE = "owner.json"

STATUS_PASS = instance_evidence.STATUS_PASS
STATUS_MISMATCH = instance_evidence.STATUS_MISMATCH
STATUS_INSUFFICIENT = instance_evidence.STATUS_INSUFFICIENT
STATUS_INVALID = instance_evidence.STATUS_INVALID

EVIDENCE_COMPOSITE = "godot_composite_behavior"
DEFAULT_REPLAYS = 2
MAX_REPLAYS = 5
DEFAULT_PROCESS_TIMEOUT = 120

# 组合场景是正式场景：它引用的脚本、关卡数据与资源都必须一起进入隔离副本。
COPIED_DIRS = ("Features", "Scenes", "Orchestration", "Levels", "Systems", "Assets")
COPIED_FILES = ("icon.svg",)
COPIED_SECTIONS = ("[input]", "[physics]")

LOAD_ERROR_MARKERS = runtime_evidence.LOAD_ERROR_MARKERS
SCRIPT_ERROR_MARKERS = runtime_evidence.SCRIPT_ERROR_MARKERS


# ---------------------------------------------------------------- 报告


class CompositeRun:
    """一次组合链执行（单次重放）的结论。"""

    def __init__(self, scene_id="", run_id="", replay_index=0):
        self.scene_id = scene_id
        self.scene = ""
        self.run_id = run_id
        self.replay_index = replay_index
        self.status = STATUS_INSUFFICIENT
        self.reason = ""
        self.detail = ""
        self.action_executed = False
        self.preconditions = []
        self.stages = []
        self.checks = []
        self.completed_stages = []
        self.failed_stage = None
        self.duration = 0.0
        self.errors = []
        self.artifacts = {}

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "replay_index": self.replay_index,
            "status": self.status,
            "reason": self.reason,
            "detail": self.detail,
            "action_executed": self.action_executed,
            "completed_stages": list(self.completed_stages),
            "failed_stage": self.failed_stage,
            "preconditions": [dict(item) for item in self.preconditions],
            "stages": [dict(item) for item in self.stages],
            "checks": [dict(item) for item in self.checks],
            "duration_s": round(self.duration, 3),
            "errors": list(self.errors),
            "artifacts": dict(self.artifacts),
        }

    def fingerprint(self) -> dict:
        """重放一致性比较：只比语义结果，忽略帧号 / 耗时 / run_id / 证据路径。"""
        keys = ("check", "target", "entry", "expected", "observed", "status")
        return {
            "status": self.status,
            "reason": self.reason,
            "failed_stage": self.failed_stage,
            "action_executed": self.action_executed,
            "completed_stages": list(self.completed_stages),
            "stages": [{
                "id": stage.get("id"),
                "status": stage.get("status"),
                "reason": stage.get("reason"),
                "checks": [{key: check.get(key) for key in keys}
                           for check in stage.get("checks") or []],
            } for stage in self.stages],
        }


class CompositeReport:
    """一条组合链契约的完整报告（含多次重放）。"""

    def __init__(self, scene_id="", scene="", run_id=""):
        self.scene_id = scene_id
        self.scene = scene
        self.run_id = run_id
        self.status = STATUS_INSUFFICIENT
        self.reason = ""
        self.detail = ""
        self.features = []
        self.stage_ids = []
        self.completed_stages = []
        self.failed_stage = None
        self.stage_count = 0
        self.total_frames = 0
        self.replay_count = 0
        self.replay_consistent = False
        self.runs = []
        self.checks = []
        self.workspace = {}
        self.evidence = {}

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "scene": self.scene,
            "run_id": self.run_id,
            "status": self.status,
            "reason": self.reason,
            "detail": self.detail,
            "evidence": EVIDENCE_COMPOSITE,
            "features": list(self.features),
            "stages": list(self.stage_ids),
            "stage_count": self.stage_count,
            "frame_budget": self.total_frames,
            "completed_stages": list(self.completed_stages),
            "failed_stage": self.failed_stage,
            "replay_count": self.replay_count,
            "replay_consistent": self.replay_consistent,
            "checks": [dict(item) for item in self.checks],
            "runs": list(self.runs),
            "workspace": dict(self.workspace),
            "evidence_paths": dict(self.evidence),
        }


def _new_run_id(tag="") -> str:
    suffix = ("-" + tag) if tag else ""
    return "%d-%s%s" % (os.getpid(), uuid.uuid4().hex[:10], suffix)


def _evidence_dir(run_id: str) -> str:
    return os.path.join(EVIDENCE_ROOT, run_id)


# ---------------------------------------------------------------- 隔离工作区


def _project_sections(project_godot: str) -> str:
    """从源项目只读复制 COPIED_SECTIONS 段（输入映射与物理参数）。

    这些段不属于被测场景/Feature，但缺了 `input.press` 与固定帧 delta 都无法真实执行。
    """
    if not os.path.isfile(project_godot):
        return ""
    kept = []
    keep = False
    try:
        with open(project_godot, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    keep = stripped in COPIED_SECTIONS
                if keep:
                    kept.append(line.rstrip("\r\n"))
    except OSError:
        return ""
    if not kept:
        return ""
    return "\n" + "\n".join(kept) + "\n"


class CompositeWorkspace:
    """本次 CLI 调用独占的隔离 Godot 项目（正式场景 + 依赖副本）。"""

    def __init__(self, run_id: str, godot: str, timeout_s: int = DEFAULT_PROCESS_TIMEOUT,
                 source_project: str = ""):
        self.run_id = run_id
        self.base = os.path.join(EVIDENCE_ROOT, "workspaces")
        os.makedirs(self.base, exist_ok=True)
        self.root = os.path.join(self.base, run_id)
        # 独占创建：同名目录已存在（其他运行 / 历史遗留）就拒绝接管。
        os.makedirs(self.root, exist_ok=False)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project, exist_ok=True)
        self.import_log = ""
        self.import_ok = False
        self.cleaned = False
        self.cleanup_reason = ""
        self.source = source_project or PROJECT_ROOT
        self._write_owner()
        self._copy_project()
        if godot:
            self.import_ok = self._import(godot, timeout_s)

    # ---------- 所有权 ----------

    def _write_owner(self) -> None:
        payload = {"run_id": self.run_id, "pid": os.getpid(), "module": MODULE_VERSION,
                   "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(os.path.join(self.root, OWNER_FILE), "w", encoding="utf-8",
                  newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def owns(self) -> tuple:
        """(是否可证明归本运行所有, 原因)；证据是 owner.json 的 run_id。"""
        path = os.path.join(self.root, OWNER_FILE)
        if not os.path.isfile(path):
            return False, "owner.json missing"
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            return False, "owner.json unreadable: %s" % exc
        if not isinstance(payload, dict):
            return False, "owner.json is not an object"
        if payload.get("run_id") != self.run_id:
            return False, "owner.json belongs to %r" % payload.get("run_id")
        return True, ""

    # ---------- 复制 ----------

    def _copy_project(self) -> None:
        for name in COPIED_DIRS:
            source = os.path.join(self.source, name)
            if os.path.isdir(source):
                shutil.copytree(source, os.path.join(self.project, name))
        for name in COPIED_FILES:
            source = os.path.join(self.source, name)
            if os.path.isfile(source):
                shutil.copyfile(source, os.path.join(self.project, name))
        probe_target = os.path.join(self.project, ".ai", "tools", "scene_composer", "probes")
        os.makedirs(probe_target, exist_ok=True)
        shutil.copyfile(PROBE_PATH, os.path.join(probe_target,
                                                "composite_behavior_probe.gd"))
        # 运行时清单必须与探针同目录：探针只读 JSON，不解析 YAML。
        shutil.copyfile(composite_protocol.MANIFEST_PATH,
                        os.path.join(probe_target, "composite_behavior_manifest.json"))
        shutil.copyfile(behavior_protocol.MANIFEST_PATH,
                        os.path.join(probe_target, "behavior_manifest.json"))
        with open(os.path.join(self.project, "project.godot"), "w", encoding="utf-8",
                  newline="\n") as handle:
            handle.write("config_version=5\n\n[application]\n"
                         "config/name=\"composite-behavior-evidence\"\n")
            handle.write(_project_sections(os.path.join(self.source, "project.godot")))

    def _import(self, godot: str, timeout_s: int) -> bool:
        try:
            proc = subprocess.run([godot, "--headless", "--path", self.project, "--import"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=timeout_s,
                                  stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.import_log = "import failed: %s" % exc
            return False
        self.import_log = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0

    # ---------- 清理 ----------

    def close(self) -> dict:
        """只删除可证明属于本运行的副本；否则保留并报告原因。"""
        report = {"run_id": self.run_id, "path": self.root, "removed": False,
                  "kept_reason": ""}
        if not os.path.isdir(self.root):
            report["removed"] = True
            report["kept_reason"] = "already absent"
            self.cleaned = True
            return report
        owned, reason = self.owns()
        if not owned:
            report["kept_reason"] = reason
            self.cleanup_reason = reason
            return report
        try:
            shutil.rmtree(self.root)
        except OSError as exc:
            report["kept_reason"] = "cannot remove workspace: %s" % exc
            self.cleanup_reason = report["kept_reason"]
            return report
        report["removed"] = True
        self.cleaned = True
        return report

    @classmethod
    def stale_workspaces(cls) -> list:
        """列出**其他**运行的副本目录（只读；绝不删除）。"""
        base = os.path.join(EVIDENCE_ROOT, "workspaces")
        if not os.path.isdir(base):
            return []
        entries = []
        for name in sorted(os.listdir(base)):
            path = os.path.join(base, name)
            if not os.path.isdir(path):
                continue
            owner = os.path.join(path, OWNER_FILE)
            state = "no owner.json"
            if os.path.isfile(owner):
                try:
                    with open(owner, encoding="utf-8") as handle:
                        payload = json.load(handle)
                    state = "owned by run %r" % (payload or {}).get("run_id")
                except (OSError, ValueError) as exc:
                    state = "unreadable owner.json (%s)" % exc
            entries.append({"path": path, "state": state})
        return entries


# ---------------------------------------------------------------- 执行与判定


def run_probe(contract: dict, project_root: str, godot: str = "",
              timeout_s: int = DEFAULT_PROCESS_TIMEOUT) -> dict:
    """启动 Godot 组合探针 -> 原始观测；不做状态判定。"""
    run_id = str(contract.get("run_id") or _new_run_id())
    directory = _evidence_dir(run_id)
    os.makedirs(directory, exist_ok=True)
    contract_path = os.path.join(directory, "contract.json")
    result_path = os.path.join(directory, "result.json")
    with open(contract_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(contract, handle, ensure_ascii=False, indent=2)

    observation = {"run_id": run_id, "exit_code": None, "stdout": "", "stderr": "",
                   "result": None, "duration": 0.0, "timed_out": False,
                   "artifacts": {"contract": contract_path, "result": result_path}}
    if not godot:
        observation["stderr"] = "godot executable not found"
        return observation

    command = [godot, "--headless", "--path", project_root, "-s", PROBE_RES,
               "--", "--contract=%s" % os.path.abspath(contract_path),
               "--result=%s" % os.path.abspath(result_path)]
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

    for name in ("stdout", "stderr"):
        path = os.path.join(directory, name + ".log")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(observation[name])
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


def judge(observation: dict, run: CompositeRun, stage_ids=()) -> CompositeRun:
    """原始观测 -> 单次组合链结论（部分完成 / 采集失败绝不成 PASS）。"""
    payload = observation.get("result")
    stderr = observation.get("stderr") or ""
    run.duration = float(observation.get("duration") or 0.0)
    run.artifacts = dict(observation.get("artifacts") or {})

    if observation.get("timed_out"):
        run.status = STATUS_INSUFFICIENT
        run.reason = "probe_timeout"
        run.detail = "probe did not finish within the process timeout"
        return run
    if payload is None:
        run.status = STATUS_INSUFFICIENT
        run.reason = "evidence_unavailable"
        marker = _first_marker(stderr, SCRIPT_ERROR_MARKERS + LOAD_ERROR_MARKERS)
        run.detail = "probe produced no machine-readable result" + (
            ": " + marker if marker else " (exit=%s)" % observation.get("exit_code"))
        return run
    if not isinstance(payload, dict):
        run.status = STATUS_INSUFFICIENT
        run.reason = "evidence_unavailable"
        run.detail = "probe result is not a JSON object"
        return run

    status = str(payload.get("status") or "")
    run.status = status if status in (STATUS_PASS, STATUS_MISMATCH,
                                     STATUS_INSUFFICIENT, STATUS_INVALID) \
        else STATUS_INSUFFICIENT
    run.reason = str(payload.get("reason") or "") or (
        "ok" if run.status == STATUS_PASS else "unknown")
    run.detail = str(payload.get("detail") or "")
    run.scene = str(payload.get("scene") or "")
    run.action_executed = bool(payload.get("action_executed", False))
    run.preconditions = list(payload.get("preconditions") or [])
    run.stages = list(payload.get("stages") or [])
    run.checks = list(payload.get("checks") or [])
    run.completed_stages = list(payload.get("completed_stages") or [])
    run.failed_stage = payload.get("failed_stage")

    if run.status == STATUS_PASS:
        load_error = _first_marker(stderr, LOAD_ERROR_MARKERS)
        script_error = _first_marker(stderr, SCRIPT_ERROR_MARKERS)
        stage_statuses = [str(stage.get("status") or "") for stage in run.stages]
        expected = list(stage_ids) or [str(stage.get("id") or "") for stage in run.stages]
        if load_error:
            run.status = STATUS_MISMATCH
            run.reason = "load_error"
            run.detail = load_error
        elif script_error:
            run.status = STATUS_MISMATCH
            run.reason = "script_error"
            run.detail = script_error
        elif not run.action_executed:
            run.status = STATUS_INSUFFICIENT
            run.reason = "action_unavailable"
            run.detail = "stages passed but at least one action never executed"
        elif run.failed_stage is not None:
            run.status = STATUS_INSUFFICIENT
            run.reason = "stage_incomplete"
            run.detail = "failed_stage %r recorded while status was PASS" % (
                run.failed_stage,)
        elif run.completed_stages != expected:
            run.status = STATUS_INSUFFICIENT
            run.reason = "stage_incomplete"
            run.detail = "completed_stages %s != contract stages %s" % (
                run.completed_stages, expected)
        elif not stage_statuses or any(item != STATUS_PASS for item in stage_statuses):
            run.status = STATUS_INSUFFICIENT
            run.reason = "stage_incomplete"
            run.detail = "stage statuses are not all PASS: %s" % stage_statuses
        elif any(not (stage.get("checks") or []) for stage in run.stages):
            run.status = STATUS_INSUFFICIENT
            run.reason = "evidence_unavailable"
            run.detail = "PASS without observed checks in every stage"

    if run.status == STATUS_MISMATCH and not run.detail:
        failing = [check for check in run.checks
                   if str(check.get("status")) != STATUS_PASS]
        run.detail = "; ".join(
            "%s[%s] expected %s observed %s" % (check.get("stage"), check.get("check"),
                                                check.get("expected"), check.get("observed"))
            for check in failing)
    return run


def _probe_stages(stages) -> list:
    """Python 契约的阶段 -> 探针契约（去掉编排器的内部字段）。"""
    out = []
    for stage in stages:
        out.append({"id": stage["id"], "actions": list(stage["actions"]),
                    "expected": list(stage["expected"]),
                    "window_frames": int(stage["window_frames"])})
    return out


def verify_contract(contract: dict, project: str, godot: str = "",
                    replay: int = DEFAULT_REPLAYS,
                    timeout_s: int = DEFAULT_PROCESS_TIMEOUT, runner=None,
                    run_id: str = "") -> CompositeReport:
    """一条组合链契约 -> 报告（含重放一致性）。"""
    report = CompositeReport(scene_id=contract["scene_id"],
                             scene="res://" + contract["scene"].replace("\\", "/"),
                             run_id=run_id or _new_run_id(contract["scene_id"]))
    report.features = list(contract.get("features") or [])
    report.stage_ids = [stage["id"] for stage in contract["stages"]]
    report.stage_count = len(contract["stages"])
    report.total_frames = int(contract.get("total_frames") or 0)

    runs = []
    for index in range(1, replay + 1):
        attempt = {
            "scene_id": contract["scene_id"],
            "scene": report.scene,
            "run_id": "%s-r%d" % (report.run_id, index),
            "replay_index": index,
            "preconditions": list(contract["preconditions"]),
            "stages": _probe_stages(contract["stages"]),
        }
        if runner is not None:
            observation = runner(attempt, project_root=project,
                                 timeout_s=timeout_s, godot=godot)
        else:
            observation = run_probe(attempt, project, godot, timeout_s)
        run = judge(observation, CompositeRun(scene_id=contract["scene_id"],
                                              run_id=attempt["run_id"],
                                              replay_index=index),
                    report.stage_ids)
        runs.append(run)

    report.runs = [run.to_dict() for run in runs]
    report.replay_count = len(runs)
    report.replay_consistent = all(run.fingerprint() == runs[0].fingerprint()
                                   for run in runs[1:]) if runs else False
    base = runs[0]
    report.status = base.status
    report.reason = base.reason
    report.detail = base.detail
    report.completed_stages = list(base.completed_stages)
    report.failed_stage = base.failed_stage
    report.checks = list(base.checks)
    report.evidence = {run.run_id: dict(run.artifacts) for run in runs}

    if base.status == STATUS_PASS and not report.replay_consistent:
        report.status = STATUS_INSUFFICIENT
        report.reason = "replay_inconsistent"
        report.detail = "replays disagreed on stage status / observed values"
    return report


def verify_scene(scene_id: str, contracts_dir: str = "", godot: str = "",
                 contracts=None, protocol=None, behavior=None,
                 replay: int = DEFAULT_REPLAYS, timeout_s: int = DEFAULT_PROCESS_TIMEOUT,
                 runner=None, workspace=None,
                 source_project: str = "") -> list:
    """组合场景 id -> 报告列表（未声明 = INVALID，不静默跳过）。"""
    if protocol is None or behavior is None:
        try:
            behavior = behavior or behavior_protocol.load_protocol()
            protocol = protocol or composite_protocol.load_protocol(behavior=behavior)
        except (behavior_protocol.ProtocolError, composite_protocol.CompositeProtocolError) \
                as exc:
            report = CompositeReport(scene_id=scene_id)
            report.status = STATUS_INVALID
            report.reason = "protocol_invalid"
            report.detail = str(exc)
            return [report]

    drift = composite_protocol.check_manifest(protocol) + behavior_protocol.check_manifest(
        behavior)
    if drift:
        report = CompositeReport(scene_id=scene_id)
        report.status = STATUS_INVALID
        report.reason = "protocol_drift"
        report.detail = "; ".join(drift)
        return [report]

    if contracts is None:
        contracts, invalid = composite_protocol.build_contracts(contracts_dir, protocol,
                                                               behavior)
        for item in invalid:
            if item["scene_id"] == scene_id:
                report = CompositeReport(scene_id=scene_id)
                report.status = STATUS_INVALID
                report.reason = "contract_invalid"
                report.detail = "; ".join(item["errors"])
                return [report]
        contracts = [item for item in contracts if item["scene_id"] == scene_id]
    if not contracts:
        report = CompositeReport(scene_id=scene_id)
        report.status = STATUS_INVALID
        report.reason = "contract_missing"
        report.detail = "no composite contract declares scene %r" % scene_id
        return [report]

    binary = godot or runtime_evidence.find_godot(PROJECT_ROOT)
    if not binary and runner is None:
        reports = []
        for contract in contracts:
            report = CompositeReport(scene_id=scene_id,
                                     scene="res://" + contract["scene"])
            report.status = STATUS_INSUFFICIENT
            report.reason = "godot_unavailable"
            report.detail = "godot executable not found; composite chain cannot be observed"
            reports.append(report)
        return reports

    owns_workspace = workspace is None
    if owns_workspace:
        workspace = CompositeWorkspace(_new_run_id(scene_id), binary, timeout_s,
                                       source_project)
    reports = []
    try:
        for contract in contracts:
            report = verify_contract(contract, workspace.project, binary, replay,
                                     timeout_s, runner,
                                     run_id=_new_run_id(contract["scene_id"]))
            reports.append(report)
    finally:
        if owns_workspace:
            cleanup = workspace.close()
            for report in reports:
                report.workspace = dict(cleanup)
    return reports


def summarize(reports) -> dict:
    counts = {}
    for report in reports:
        counts[report.status] = counts.get(report.status, 0) + 1
    return {"checked": len(reports),
            "pass": counts.get(STATUS_PASS, 0),
            "mismatch": counts.get(STATUS_MISMATCH, 0),
            "insufficient": counts.get(STATUS_INSUFFICIENT, 0),
            "invalid": counts.get(STATUS_INVALID, 0)}


def declared_scenes(contracts_dir: str = "", protocol=None, behavior=None) -> list:
    """声明了组合契约的场景 id（只读）；契约非法时也列出，交由报告标记 INVALID。"""
    if protocol is None:
        behavior = behavior or behavior_protocol.load_protocol()
        protocol = composite_protocol.load_protocol(behavior=behavior)
    contracts, invalid = composite_protocol.build_contracts(contracts_dir, protocol,
                                                            behavior)
    names = [contract["scene_id"] for contract in contracts]
    names.extend(item["scene_id"] for item in invalid)
    return sorted(set(names))


# ---------------------------------------------------------------- CLI


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a composite scene behavior chain by executing staged actions in "
                    "an isolated real Godot project copy.")
    parser.add_argument("--scene", action="append", default=[], help="scene id (repeatable)")
    parser.add_argument("--all", action="store_true", help="all declared composite scenes")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--require-composite", action="store_true",
                        help="treat INSUFFICIENT as failure (final acceptance gate)")
    parser.add_argument("--replay", type=int, default=DEFAULT_REPLAYS,
                        help="replays per chain (1..%d)" % MAX_REPLAYS)
    parser.add_argument("--contracts-dir", default=composite_protocol.CONTRACTS_DIR)
    parser.add_argument("--protocol", default=composite_protocol.PROTOCOL_PATH)
    parser.add_argument("--behavior-protocol", default=behavior_protocol.PROTOCOL_PATH)
    parser.add_argument("--godot", default="")
    parser.add_argument("--timeout", type=int, default=DEFAULT_PROCESS_TIMEOUT)
    parser.add_argument("--project-root", default="")
    parser.add_argument("--list-stale", action="store_true",
                        help="report other runs' workspaces (never delete them)")
    args = parser.parse_args(argv)

    if not 1 <= args.replay <= MAX_REPLAYS:
        print("FAIL: --replay must be 1..%d" % MAX_REPLAYS)
        return 2

    try:
        behavior = behavior_protocol.load_protocol(args.behavior_protocol)
        protocol = composite_protocol.load_protocol(args.protocol, behavior=behavior)
    except (behavior_protocol.ProtocolError, composite_protocol.CompositeProtocolError) \
            as exc:
        print("FAIL: %s" % exc)
        return 1

    drift = composite_protocol.check_manifest(protocol) + behavior_protocol.check_manifest(
        behavior)
    if drift:
        print("FAIL: %s" % "; ".join(drift))
        return 1

    if args.list_stale:
        # 只报告其他运行留下的副本目录；本命令从不删除它们。
        entries = CompositeWorkspace.stale_workspaces()
        for entry in entries:
            print("  stale %s  %s" % (entry["path"], entry["state"]))
        if not entries:
            print("  no stale workspaces")
        if not args.scene and not args.all:
            return 0

    targets = args.scene or (declared_scenes(args.contracts_dir, protocol, behavior)
                             if args.all else [])
    if not targets:
        print("FAIL: give --scene <id> or --all")
        return 2

    # 先做契约校验：非法契约不启动 Godot，也不创建隔离工作区。
    contracts, invalid = composite_protocol.build_contracts(args.contracts_dir, protocol,
                                                           behavior)
    invalid_by_id = {item["scene_id"]: item for item in invalid}
    reports = []
    pending = []
    for scene_id in targets:
        if scene_id in invalid_by_id:
            report = CompositeReport(scene_id=scene_id)
            report.status = STATUS_INVALID
            report.reason = "contract_invalid"
            report.detail = "; ".join(invalid_by_id[scene_id]["errors"])
            reports.append(report)
        else:
            pending.append(scene_id)

    # Godot 通常位于仓库同级目录；--project-root 只是被复制为隔离副本的源项目，
    # 它自己的父目录不一定有 Godot，因此先按仓库定位，再回退到源项目。
    binary = (args.godot or runtime_evidence.find_godot(PROJECT_ROOT)
              or runtime_evidence.find_godot(args.project_root or PROJECT_ROOT))
    cleanup = {}
    workspace = None
    if pending and binary:
        workspace = CompositeWorkspace(_new_run_id("cli"), binary, args.timeout,
                                       args.project_root or PROJECT_ROOT)
    try:
        for scene_id in pending:
            reports.extend(verify_scene(scene_id, args.contracts_dir, binary,
                                        contracts=[item for item in contracts
                                                   if item["scene_id"] == scene_id],
                                        protocol=protocol, behavior=behavior,
                                        replay=args.replay, timeout_s=args.timeout,
                                        workspace=workspace,
                                        source_project=args.project_root or PROJECT_ROOT))
    finally:
        if workspace is not None:
            cleanup = workspace.close()
            for report in reports:
                report.workspace = dict(cleanup)

    if not cleanup:
        # verify_scene 自建工作区时（例如未由本函数创建），清理结论挂在报告上。
        for report in reports:
            if report.workspace:
                cleanup = dict(report.workspace)
                break

    if args.json:
        print(json.dumps({"summary": summarize(reports),
                          "cleanup": cleanup,
                          "reports": [report.to_dict() for report in reports]},
                         ensure_ascii=False, indent=2))
    else:
        print("Composite Scene Behavior Evidence")
        for report in reports:
            print("  %-16s %-8s %-10s %s%s" % (
                report.scene_id, "%d/%d" % (len(report.completed_stages),
                                            report.stage_count),
                report.status, report.reason,
                "" if not report.detail else "  | " + report.detail))
            for check in report.checks:
                if str(check.get("status")) != STATUS_PASS:
                    print("    - [%s] %s %s expected=%s observed=%s" % (
                        check.get("stage"), check.get("check"), check.get("status"),
                        check.get("expected"), check.get("observed")))
        summary = summarize(reports)
        print("\n  pass=%d mismatch=%d insufficient=%d invalid=%d" % (
            summary["pass"], summary["mismatch"], summary["insufficient"],
            summary["invalid"]))
        for report in reports:
            if report.replay_count:
                print("  %-16s replay=%d consistent=%s stages=%s"
                      % (report.scene_id, report.replay_count, report.replay_consistent,
                         ",".join(report.completed_stages)))
        if cleanup:
            print("  workspace removed=%s kept=%s" % (
                cleanup.get("removed"),
                cleanup.get("kept_reason") or "-"))
        print("  evidence: %s" % EVIDENCE_ROOT)

    failed = [report for report in reports
              if report.status in (STATUS_MISMATCH, STATUS_INVALID)
              or (args.require_composite and report.status == STATUS_INSUFFICIENT)]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
