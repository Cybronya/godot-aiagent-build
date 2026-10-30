#!/usr/bin/env python3
"""Feature Behavior Evidence (Phase 1.40) —— 真实动作后的行为证据。

Phase 1.38 证明「声明 ↔ .tscn 静态内容」，Phase 1.39 证明「Godot 加载后节点存在」。
本模块补第五层：**在隔离的真实场景里执行受限动作，观察后置状态是否与契约一致**。

五层证据（严格区分，不得互相顶替）：

    1. 文件解析        .tscn 文本可解析                 → instance_evidence（静态）
    2. 资源加载        PackedScene 可被 Godot 加载       → runtime_instance_evidence（1.39）
    3. 节点存在        加载后对象树里有目标节点           → runtime_instance_evidence（1.39）
    4. 动作执行        真实入口被调用（不是直接改状态）    → 本模块（1.40）
    5. 行为正确        动作后状态/信号符合契约            → 本模块（1.40）

能力来源（Phase 1.41）：动作 / 观测 / 信号 / 参数约束的唯一权威是
`.ai/context/behavior_protocol.yaml`；探针读取由它生成的
`probes/behavior_manifest.json`。本模块不再维护第二份动作/观测清单，
也不允许协议声明之外的能力被使用。

Phase 1.42 新增能力（均来自同一份协议）：
    - `simulation.advance_frames`：受控 physics 帧推进（固定 delta，可重放）；
      帧预算由协议 `limits` 约束，探针从 manifest 读同一份数值。
    - `state.set_property`：**夹具**动作，只能写协议 `properties:` 声明的导出属性，
      且必须排在任何行为动作之前 —— 不允许用状态设置直接制造最终结果。
    - `input.press` / `input.release`：受控输入夹具（Input.action_press/release）。
    - `node2d.position` / `node2d.displacement`：动作后帧检查点读取真实 global_position
      （绝对 / 相对动作前基线的位移），支持 equals±tolerance 或 min/max 区间。

契约来源（`Features/<feature>/template.yaml` 顶层 `behavior:`，与 `instance:` 分离，
不改变 1.38/1.39 的结构声明语义）：

    behavior:
      - id: open
        actions:                        # 显式注册的动作；不执行任意方法名
          - {type: door.set_open, target: ".", params: {value: true}}
        preconditions:                  # 动作前必须成立；否则 INSUFFICIENT
          - {check: door.is_open, target: ".", equals: false}
        expected:                       # 动作后的后置断言
          - {check: door.is_open, target: ".", equals: true}
          - {check: signal, entry: door.state_changed, target: ".", count: 1, last_args: [true]}
        window_frames: 12               # 动作后观测窗口（physics frames）

    # 可选（1.43）：需要额外夹具时，声明 Feature 目录内的证据场景。
    #   只允许相对 .tscn；拒绝绝对路径 / res:// / .. / 不存在的文件。
      - id: approach_target
        scene: ChaseTargetFixture.tscn
        actions: [{type: simulation.advance_frames, params: {frames: 60}}]
        expected: [{check: node2d.displacement, target: Chaser, axis: x, min: 77.5, max: 82.5}]
        window_frames: 1

它只选择证据场景，不增加任何运行时能力。

结果状态（复用 1.38/1.39 词汇，语义限定在行为层）：

    PASS          动作确实执行，且在窗口内观测到全部后置断言成立
    MISMATCH      动作执行了，但状态/信号与契约明确冲突（含节点未被释放）
    INSUFFICIENT  动作入口不可用、前置条件不满足、观测不可用、采集失败、重放不一致
    INVALID       行为契约本身非法（未知动作/参数/检查/目标）
    NOT_DECLARED  未声明 `behavior:`（不凭空要求行为证据）

本模块 MUST NOT：
    - 直接设置被测状态来「制造」预期结果；只能调用受限注册动作。
    - 在动作未执行 / 采集失败 / 重放不一致时返回 PASS。
    - 修改仓库场景或黄金基线；只在 `.ai/tmp/behavior/` 下写本次运行拥有的临时资源。

契约：.ai/context/scene_composer_schema.yaml#feature_behavior_evidence

用法:
    python .ai/tools/scene_composer/feature_behavior_evidence.py --feature openable_door
    python .ai/tools/scene_composer/feature_behavior_evidence.py --all --json
    python .ai/tools/scene_composer/feature_behavior_evidence.py --all --require-behavior

退出码：0 = PASS / NOT_DECLARED（或未开 --require-behavior 的 INSUFFICIENT）；
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

import behavior_protocol                                      # noqa: E402
import instance_evidence                                      # noqa: E402
import runtime_instance_evidence as runtime_evidence          # noqa: E402
import template_loader                                        # noqa: E402

MODULE_VERSION = 1
PROBE_RES = "res://.ai/tools/scene_composer/probes/feature_behavior_probe.gd"
PROBE_PATH = os.path.join(_HERE, "probes", "feature_behavior_probe.gd")
EVIDENCE_ROOT = os.path.join(_DOTAI, "tmp", "behavior")
RESULT_PREFIX = "BEHAVIOR_RESULT: "

STATUS_PASS = instance_evidence.STATUS_PASS
STATUS_MISMATCH = instance_evidence.STATUS_MISMATCH
STATUS_INSUFFICIENT = instance_evidence.STATUS_INSUFFICIENT
STATUS_INVALID = instance_evidence.STATUS_INVALID
STATUS_NOT_DECLARED = instance_evidence.STATUS_NOT_DECLARED

EVIDENCE_BEHAVIOR = "godot_behavior"
DEFAULT_REPLAYS = 2
MAX_REPLAYS = 5
DEFAULT_WINDOW_FRAMES = 30
MAX_WINDOW_FRAMES = 600
DEFAULT_PROCESS_TIMEOUT = 90

CHECK_STATE = "state"
CHECK_SIGNAL = "signal"
CHECK_FREED = "node.freed"

# 动作 / 观测能力不再在本文件定义：唯一权威是 .ai/context/behavior_protocol.yaml，
# 探针通过其生成的 behavior_manifest.json 读取同一份能力。本文件只做 Feature 级契约
# 组织与最终判定。

LOAD_ERROR_MARKERS = runtime_evidence.LOAD_ERROR_MARKERS
SCRIPT_ERROR_MARKERS = runtime_evidence.SCRIPT_ERROR_MARKERS


class BehaviorRun:
    """一次动作执行（单个 behavior 的单次重放）的结论。"""

    def __init__(self, feature="", behavior="", scene="", run_id="", replay_index=0):
        self.feature = feature
        self.behavior = behavior
        self.scene = scene
        self.run_id = run_id
        self.replay_index = replay_index
        self.status = STATUS_INSUFFICIENT
        self.reason = ""
        self.detail = ""
        self.action_executed = False
        self.actions = []
        self.preconditions = []
        self.checks = []
        self.action_frame = None
        self.observed_frame = None
        self.waited_frames = None
        self.window_frames = None
        self.first_observed_frame = None
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
            "actions": list(self.actions),
            "preconditions": [dict(item) for item in self.preconditions],
            "checks": [dict(item) for item in self.checks],
            "action_frame": self.action_frame,
            "observed_frame": self.observed_frame,
            "waited_frames": self.waited_frames,
            "window_frames": self.window_frames,
            "duration_s": round(self.duration, 3),
            "errors": list(self.errors),
            "artifacts": dict(self.artifacts),
        }

    def fingerprint(self) -> dict:
        """重放一致性比较：只比关键结果，忽略帧号 / 时长 / run_id。"""
        keys = ("check", "target", "entry", "expected", "observed", "status")
        return {
            "status": self.status,
            "reason": self.reason,
            "action_executed": self.action_executed,
            "checks": [{key: check.get(key) for key in keys} for check in self.checks],
        }


class BehaviorReport:
    """一个 behavior 契约的完整报告（含多次重放）。"""

    def __init__(self, feature="", behavior="", scene="", run_id=""):
        self.feature = feature
        self.behavior = behavior
        self.scene = scene
        self.run_id = run_id
        self.status = STATUS_INSUFFICIENT
        self.reason = ""
        self.detail = ""
        self.action_executed = False
        self.preconditions = []
        self.actions = []
        self.expected = []
        self.actual = []
        self.window_frames = None
        self.first_observed_frame = None
        self.replay_count = 0
        self.replay_consistent = False
        self.runs = []
        self.evidence = {}

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "behavior": self.behavior,
            "action_id": self.behavior,
            "scene_id": self.scene,
            "run_id": self.run_id,
            "status": self.status,
            "reason": self.reason,
            "detail": self.detail,
            "evidence": EVIDENCE_BEHAVIOR,
            "action_executed": self.action_executed,
            "preconditions": [dict(item) for item in self.preconditions],
            "action_parameters": list(self.actions),
            "observation_window": {"frames": self.window_frames, "unit": "physics_frames"},
            "expected": [dict(item) for item in self.expected],
            "actual": [dict(item) for item in self.actual],
            "first_observed_frame": self.first_observed_frame,
            "replay_count": self.replay_count,
            "replay_consistent": self.replay_consistent,
            "runs": list(self.runs),
            "evidence_paths": dict(self.evidence),
        }


def _new_run_id(tag="") -> str:
    suffix = ("-" + tag) if tag else ""
    return "%d-%s%s" % (os.getpid(), uuid.uuid4().hex[:8], suffix)


def _evidence_dir(run_id: str) -> str:
    return os.path.join(EVIDENCE_ROOT, run_id)


def declared_features(features_dir: str = instance_evidence.FEATURES_DIR) -> list:
    """声明了顶层 `behavior:` 的 Feature（只读）。"""
    names = []
    if not os.path.isdir(features_dir):
        return names
    for feature in sorted(os.listdir(features_dir)):
        if not os.path.isdir(os.path.join(features_dir, feature)):
            continue
        template = template_loader.load_template(feature, features_dir)
        if isinstance(template.get("behavior"), list) and template["behavior"]:
            names.append(feature)
    return names


# ---------------------------------------------------------------- 契约校验

def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_action(raw, index: int, errors: list, protocol) -> dict:
    action, action_errors = protocol.validate_action(raw, index)
    if action_errors:
        errors.extend(action_errors)
        return {}
    return action


def _validate_check(raw, index: int, where: str, errors: list, protocol) -> dict:
    entry, check_errors = protocol.validate_check(raw, index, where)
    if check_errors:
        errors.extend(check_errors)
        return {}
    return entry


def check_has_evidence(entry: dict) -> bool:
    """该 check 是否断言了可观测的正面证据（事件已发生 / 状态已到达）。

    `signal count: 0` 与布尔 `equals: false` 只断言「什么都没发生」；数值 0（如
    health.current == 0）与区间断言仍算证据。用于「零帧推进 + 纯否定期望」规则：
    这类契约在动作后的第一个观测点就满足，没有任何真实观测支撑。
    """
    # validate_check 把参数平铺进 entry（check/target 之外都是观测参数）；
    # 也兼容带 params 的嵌套写法。
    params = dict(entry.get("params") or {})
    params.update({key: value for key, value in entry.items()
                   if key not in ("check", "target", "params")})
    if entry.get("check") == "signal":
        count = params.get("count", 0)
        return _is_int(count) and count > 0
    return params.get("equals") is not False


def advances_frames(actions: list, protocol) -> bool:
    """动作序列是否推进过真实 physics 帧（帧内观测窗口的唯一来源）。"""
    for action in actions:
        spec = protocol.actions.get(action.get("type", "")) or {}
        if spec.get("advances_frames"):
            return True
    return False


def _behavior_scene(feature: str, raw, default: str, features_dir: str) -> tuple:
    """行为级证据场景：只能是 Features/<feature>/ 内的相对 .tscn 路径。

    返回 (res:// 路径, errors)。缺省时沿用模板入口场景；显式声明时拒绝绝对路径、
    `res://`、`..`/`.` 段、非 .tscn 与不存在的文件，避免证据读取 Feature 之外的内容。
    """
    if not isinstance(raw, dict) or "scene" not in raw:
        return default, []
    value = raw.get("scene")
    if not isinstance(value, str) or not value.strip():
        return "", ["Invalid behavior contract: scene must be a non-empty relative path"]
    relative = value.strip().replace("\\", "/")
    parts = relative.split("/")
    if relative.startswith("/") or relative.startswith("res://") or ":" in relative \
            or any(part in ("", ".", "..") for part in parts):
        return "", ["Invalid behavior contract: scene must be a relative path inside "
                    "Features/%s (got %r)" % (feature, value)]
    if not relative.endswith(".tscn"):
        return "", ["Invalid behavior contract: scene must be a .tscn file (got %r)" % value]
    if not os.path.isfile(os.path.join(features_dir, feature, *parts)):
        return "", ["Invalid behavior contract: scene not found: Features/%s/%s"
                    % (feature, relative)]
    return "res://Features/%s/%s" % (feature, relative), []


def _validate_behavior(raw, index: int, scene: str, errors: list, protocol) -> dict:
    where = "behavior[%d]" % index
    if not isinstance(raw, dict):
        errors.append("Invalid behavior contract: %s must be a mapping" % where)
        return {}
    behavior_id = str(raw.get("id") or "").strip()
    if not behavior_id:
        errors.append("Invalid behavior contract: %s.id is required" % where)
        return {}
    max_frames = int(protocol.limits["max_total_frames"])
    window = raw.get("window_frames", DEFAULT_WINDOW_FRAMES)
    if not _is_int(window) or not 1 <= window <= max_frames:
        errors.append("Invalid behavior contract: %s.window_frames must be 1..%d"
                      % (where, max_frames))
        return {}

    raw_actions = raw.get("actions")
    if not isinstance(raw_actions, list) or not raw_actions:
        errors.append("Invalid behavior contract: %s.actions must be a non-empty list" % where)
        return {}
    actions = [_validate_action(item, position, errors, protocol)
               for position, item in enumerate(raw_actions)]
    if len([item for item in actions if item]) != len(raw_actions):
        return {}
    # 夹具只能在行为动作之前 + 帧/夹具预算（与探针同一份 limits）
    errors.extend(protocol.sequence_errors(actions))
    errors.extend(protocol.frame_budget_errors(actions, window))
    if errors:
        return {}

    raw_pre = raw.get("preconditions") or []
    if not isinstance(raw_pre, list):
        errors.append("Invalid behavior contract: %s.preconditions must be a list" % where)
        return {}
    preconditions = [_validate_check(item, position, where + ".preconditions", errors,
                                     protocol)
                     for position, item in enumerate(raw_pre)]
    if len([item for item in preconditions if item]) != len(raw_pre):
        return {}
    raw_expected = raw.get("expected")
    if not isinstance(raw_expected, list) or not raw_expected:
        errors.append("Invalid behavior contract: %s.expected must be a non-empty list" % where)
        return {}
    expected = [_validate_check(item, position, where + ".expected", errors,
                               protocol)
                for position, item in enumerate(raw_expected)]
    if len([item for item in expected if item]) != len(raw_expected):
        return {}

    # 最小证据规则（Phase 1.45）：动作不推进任何 physics 帧、而期望只断言
    # 「什么都没发生」（signal count 0 / equals false）时，首个观测点即满足，
    # PASS 没有任何观测窗口支撑（实测：接错后 1 帧内仍未触发也照 PASS）。
    # 现有 17 条 behavior 要么推进真实帧、要么断言正面证据，不受此规则影响。
    if not advances_frames(actions, protocol) \
            and not any(check_has_evidence(entry) for entry in expected):
        errors.append(
            "Invalid behavior contract: %s.expected only asserts absence of behaviour "
            "while no action advances frames; PASS would be decided without any "
            "observation window" % where)
        return {}

    return {"feature": "", "behavior": behavior_id, "scene": scene,
            "window_frames": window, "actions": actions,
            "preconditions": preconditions, "expected": expected}


def build_contracts(feature: str, features_dir: str = instance_evidence.FEATURES_DIR,
                    protocol=None, protocol_path: str = "") -> tuple:
    """Feature -> ([contract...], [report...])；契约非法时报告为 INVALID。"""
    if protocol is None:
        try:
            protocol = behavior_protocol.load_protocol(protocol_path)
        except behavior_protocol.ProtocolError as exc:
            report = BehaviorReport(feature=feature)
            report.status = STATUS_INVALID
            report.reason = "protocol_invalid"
            report.detail = str(exc)
            return [], [report]
    template = template_loader.load_template(feature, features_dir)
    if not template:
        report = BehaviorReport(feature=feature)
        report.status = STATUS_INVALID
        report.reason = "contract_invalid"
        report.detail = "Feature template not found: %s" % feature
        return [], [report]

    raw = template.get("behavior")
    if raw is None:
        report = BehaviorReport(feature=feature)
        report.status = STATUS_NOT_DECLARED
        report.reason = "behavior_not_declared"
        report.detail = "no behavior block: behavior evidence not required"
        return [], [report]
    if not isinstance(raw, list) or not raw:
        report = BehaviorReport(feature=feature)
        report.status = STATUS_INVALID
        report.reason = "contract_invalid"
        report.detail = "behavior must be a non-empty list"
        return [], [report]

    scene = template_loader.template_scene_path(feature, template, features_dir)
    contracts = []
    reports = []
    seen = set()
    for index, item in enumerate(raw):
        errors = []
        behavior_scene, scene_errors = _behavior_scene(feature, item, scene, features_dir)
        errors.extend(scene_errors)
        contract = _validate_behavior(item, index, behavior_scene, errors, protocol)
        if errors:
            report = BehaviorReport(feature=feature,
                                    behavior=str((item or {}).get("id") or "#%d" % index)
                                    if isinstance(item, dict) else "#%d" % index,
                                    scene=scene)
            report.status = STATUS_INVALID
            report.reason = "contract_invalid"
            report.detail = errors[0]
            report.errors = errors
            reports.append(report)
            continue
        if contract["behavior"] in seen:
            report = BehaviorReport(feature=feature, behavior=contract["behavior"], scene=scene)
            report.status = STATUS_INVALID
            report.reason = "contract_invalid"
            report.detail = "duplicate behavior id: %s" % contract["behavior"]
            reports.append(report)
            continue
        seen.add(contract["behavior"])
        contract["feature"] = feature
        contract["run_id"] = _new_run_id(contract["behavior"])
        contracts.append(contract)
    return contracts, reports


# ---------------------------------------------------------------- 隔离工作区

# 复制到隔离项目的项目级配置段：输入映射与物理参数属于“真实运行环境”，
# 不是被测 Feature 的行为；缺了它们 input.press / 固定帧 delta 都无法真实执行。
COPIED_SECTIONS = ("[input]", "[physics]")


def _project_sections(project_godot: str) -> str:
    """从源项目只读复制 COPIED_SECTIONS 段（不存在则跳过）。"""
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


class BehaviorWorkspace:
    """本次 CLI 调用拥有的隔离 Godot 项目（复制 Features + 探针）。"""

    def __init__(self, features_dir: str, godot: str, timeout_s: int = 120,
                 source_project: str = ""):
        os.makedirs(EVIDENCE_ROOT, exist_ok=True)
        self.root = tempfile.mkdtemp(prefix="workspace-", dir=EVIDENCE_ROOT)
        self.project = os.path.join(self.root, "project")
        self.import_log = ""
        self.import_ok = False
        os.makedirs(self.project, exist_ok=True)
        shutil.copytree(features_dir, os.path.join(self.project, "Features"))
        probe_target = os.path.join(self.project, ".ai", "tools", "scene_composer", "probes",
                                    "feature_behavior_probe.gd")
        os.makedirs(os.path.dirname(probe_target), exist_ok=True)
        shutil.copyfile(PROBE_PATH, probe_target)
        # 运行时能力清单必须与探针同目录：探针只读它，不解析 YAML。
        shutil.copyfile(behavior_protocol.MANIFEST_PATH,
                        os.path.join(os.path.dirname(probe_target),
                                     "behavior_manifest.json"))
        source = source_project or os.path.dirname(os.path.abspath(features_dir))
        if not os.path.isfile(os.path.join(source, "project.godot")):
            source = PROJECT_ROOT
        with open(os.path.join(self.project, "project.godot"), "w", encoding="utf-8",
                  newline="\n") as handle:
            handle.write("config_version=5\n\n[application]\n"
                         "config/name=\"feature-behavior-evidence\"\n")
            handle.write(_project_sections(os.path.join(source, "project.godot")))
        if godot:
            self.import_ok = self._import(godot, timeout_s)

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

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


# ---------------------------------------------------------------- 执行与判定

def run_probe(contract: dict, project_root: str, godot: str = "",
              timeout_s: int = DEFAULT_PROCESS_TIMEOUT) -> dict:
    """启动 Godot 行为探针 -> 原始观测；不做状态判定。"""
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


def judge(observation: dict, report: BehaviorRun) -> BehaviorRun:
    """原始观测 -> 单次执行结论（采集失败 / 动作未执行绝不成 PASS）。"""
    payload = observation.get("result")
    stderr = observation.get("stderr") or ""
    report.duration = float(observation.get("duration") or 0.0)
    report.artifacts = dict(observation.get("artifacts") or {})

    if observation.get("timed_out"):
        report.status = STATUS_INSUFFICIENT
        report.reason = "probe_timeout"
        report.detail = "probe did not finish within the process timeout"
        return report
    if payload is None:
        report.status = STATUS_INSUFFICIENT
        report.reason = "evidence_unavailable"
        marker = _first_marker(stderr, SCRIPT_ERROR_MARKERS + LOAD_ERROR_MARKERS)
        report.detail = "probe produced no machine-readable result" + (
            ": " + marker if marker else " (exit=%s)" % observation.get("exit_code"))
        return report
    if not isinstance(payload, dict):
        report.status = STATUS_INSUFFICIENT
        report.reason = "evidence_unavailable"
        report.detail = "probe result is not a JSON object"
        return report

    status = str(payload.get("status") or "")
    report.status = status if status in (STATUS_PASS, STATUS_MISMATCH,
                                        STATUS_INSUFFICIENT, STATUS_INVALID) \
        else STATUS_INSUFFICIENT
    report.reason = str(payload.get("reason") or "") or (
        "ok" if report.status == STATUS_PASS else "unknown")
    report.detail = str(payload.get("detail") or "")
    report.action_executed = bool(payload.get("action_executed", False))
    report.actions = list(payload.get("actions") or [])
    report.preconditions = list(payload.get("preconditions") or [])
    report.checks = list(payload.get("checks") or [])
    report.action_frame = payload.get("action_frame")
    report.observed_frame = payload.get("observed_frame")
    report.waited_frames = payload.get("waited_frames")
    report.window_frames = payload.get("window_frames")

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
        elif not report.action_executed:
            # 动作没有真的执行：即使状态凑巧符合也不得 PASS。
            report.status = STATUS_INSUFFICIENT
            report.reason = "action_unavailable"
            report.detail = "expected state observed but the action never executed"
        elif not report.checks:
            report.status = STATUS_INSUFFICIENT
            report.reason = "evidence_unavailable"
            report.detail = "PASS without observed post-condition checks"

    if report.status == STATUS_MISMATCH and not report.detail:
        failing = [check for check in report.checks if check.get("status") != STATUS_PASS]
        if failing:
            report.detail = "; ".join(
                "%s expected %s observed %s" % (check.get("check"), check.get("expected"),
                                                check.get("observed"))
                for check in failing)
    return report


def verify_contract(contract: dict, project: str, godot: str = "",
                    replay: int = DEFAULT_REPLAYS,
                    timeout_s: int = DEFAULT_PROCESS_TIMEOUT, runner=None) -> BehaviorReport:
    """单个 behavior 契约 -> 报告（含重放一致性）。"""
    report = BehaviorReport(feature=contract["feature"], behavior=contract["behavior"],
                            scene=contract["scene"], run_id=contract["run_id"])
    report.window_frames = contract["window_frames"]
    report.preconditions = list(contract["preconditions"])
    report.actions = list(contract["actions"])
    report.expected = list(contract["expected"])

    runs = []
    for index in range(1, replay + 1):
        attempt = dict(contract)
        attempt["run_id"] = contract["run_id"] + "-r%d" % index
        attempt["replay_index"] = index
        if runner is not None:
            observation = runner(attempt, project_root=project,
                                 timeout_s=timeout_s, godot=godot)
        else:
            observation = run_probe(attempt, project, godot, timeout_s)
        run_report = judge(observation, BehaviorRun(
            feature=contract["feature"], behavior=contract["behavior"],
            scene=contract["scene"], run_id=attempt["run_id"], replay_index=index))
        runs.append(run_report)

    report.runs = [run.to_dict() for run in runs]
    report.replay_count = len(runs)
    report.replay_consistent = all(run.fingerprint() == runs[0].fingerprint()
                                   for run in runs[1:]) if runs else False
    base = runs[0]
    report.status = base.status
    report.reason = base.reason
    report.detail = base.detail
    report.action_executed = base.action_executed
    report.preconditions = list(base.preconditions) or list(contract["preconditions"])
    report.actual = list(base.checks)
    report.first_observed_frame = min(
        [check.get("first_observed_frame") for check in base.checks
         if isinstance(check.get("first_observed_frame"), int)
         and check.get("first_observed_frame") >= 0], default=None)
    report.evidence = {run.run_id: dict(run.artifacts) for run in runs}

    if base.status == STATUS_PASS and not report.replay_consistent:
        report.status = STATUS_INSUFFICIENT
        report.reason = "replay_inconsistent"
        report.detail = "replays disagreed on status/observed values"
    return report


def verify_feature(feature: str, features_dir: str = instance_evidence.FEATURES_DIR,
                   project_root: str = "", godot: str = "",
                   replay: int = DEFAULT_REPLAYS, timeout_s: int = DEFAULT_PROCESS_TIMEOUT,
                   runner=None, workspace=None, protocol=None,
                   protocol_path: str = "", manifest_path="") -> list:
    """Feature -> behavior 报告列表（每个声明的 behavior 一份）。"""
    if protocol is None:
        try:
            protocol = behavior_protocol.load_protocol(protocol_path)
        except behavior_protocol.ProtocolError as exc:
            report = BehaviorReport(feature=feature)
            report.status = STATUS_INVALID
            report.reason = "protocol_invalid"
            report.detail = str(exc)
            return [report]
    # manifest_path=None 表示调用方已自行保证清单一致（测试/自定义协议）。
    drift = [] if manifest_path is None else behavior_protocol.check_manifest(
        protocol, manifest_path)
    if drift:
        report = BehaviorReport(feature=feature)
        report.status = STATUS_INVALID
        report.reason = "protocol_drift"
        report.detail = "; ".join(drift)
        return [report]

    contracts, reports = build_contracts(feature, features_dir, protocol=protocol)
    if not contracts:
        return reports

    binary = godot or runtime_evidence.find_godot(project_root or PROJECT_ROOT)
    if runner is not None:
        project = getattr(workspace, "project", None) or project_root or PROJECT_ROOT
        for contract in contracts:
            reports.append(verify_contract(contract, project, binary, replay,
                                           timeout_s, runner))
        return reports
    if not binary:
        for contract in contracts:
            report = BehaviorReport(feature=feature, behavior=contract["behavior"],
                                    scene=contract["scene"], run_id=contract["run_id"])
            report.status = STATUS_INSUFFICIENT
            report.reason = "godot_unavailable"
            report.detail = "godot executable not found; behavior cannot be observed"
            report.replay_count = 0
            reports.append(report)
        return reports

    owns_workspace = workspace is None
    if owns_workspace:
        workspace = BehaviorWorkspace(features_dir, binary)
    try:
        for contract in contracts:
            reports.append(verify_contract(contract, workspace.project, binary, replay,
                                           timeout_s))
    finally:
        if owns_workspace:
            workspace.close()
    return reports


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
    parser = argparse.ArgumentParser(
        description="Verify Feature behavior by executing registered actions in a real Godot "
                    "scene copy and observing post-conditions.")
    parser.add_argument("--feature", action="append", default=[], help="Feature id (repeatable)")
    parser.add_argument("--all", action="store_true", help="all Features declaring behavior")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--require-behavior", action="store_true",
                        help="treat INSUFFICIENT as failure (final acceptance gate)")
    parser.add_argument("--replay", type=int, default=DEFAULT_REPLAYS,
                        help="replays per behavior (2..%d)" % MAX_REPLAYS)
    parser.add_argument("--features-dir", default=instance_evidence.FEATURES_DIR)
    parser.add_argument("--protocol", default=behavior_protocol.PROTOCOL_PATH)
    parser.add_argument("--project-root", default="")
    parser.add_argument("--godot", default="")
    parser.add_argument("--timeout", type=int, default=DEFAULT_PROCESS_TIMEOUT)
    args = parser.parse_args(argv)

    if not os.path.isdir(args.features_dir):
        print("FAIL: features dir not found: %s" % args.features_dir)
        return 2
    if not 1 <= args.replay <= MAX_REPLAYS:
        print("FAIL: --replay must be 1..%d" % MAX_REPLAYS)
        return 2
    targets = args.feature or (declared_features(args.features_dir) if args.all else [])
    if not targets:
        print("FAIL: give --feature <id> or --all")
        return 2
    try:
        protocol = behavior_protocol.load_protocol(args.protocol)
    except behavior_protocol.ProtocolError as exc:
        print("FAIL: %s" % exc)
        return 1
    drift = behavior_protocol.check_manifest(protocol)
    if drift:
        print("FAIL: %s" % "; ".join(drift))
        return 1

    root = args.project_root or PROJECT_ROOT
    binary = args.godot or runtime_evidence.find_godot(root)
    reports = []
    if binary:
        workspace = BehaviorWorkspace(args.features_dir, binary)
        try:
            for feature in targets:
                reports.extend(verify_feature(
                    feature, args.features_dir, args.project_root or workspace.project,
                    binary, args.replay, args.timeout, workspace=workspace,
                    protocol=protocol))
        finally:
            workspace.close()
    else:
        for feature in targets:
            reports.extend(verify_feature(feature, args.features_dir, args.project_root,
                                          "", args.replay, args.timeout,
                                          protocol=protocol))

    if args.json:
        print(json.dumps({"summary": summarize(reports),
                          "reports": [report.to_dict() for report in reports]},
                         ensure_ascii=False, indent=2))
    else:
        print("Feature Behavior Evidence")
        for report in reports:
            print("  %-16s %-14s %-10s %s%s" % (
                report.feature, report.behavior, report.status, report.reason,
                "" if not report.detail else "  | " + report.detail))
            for check in report.actual:
                if check.get("status") != STATUS_PASS:
                    print("    - %s %s expected=%s observed=%s" % (
                        check.get("check"), check.get("status"),
                        check.get("expected"), check.get("observed")))
        summary = summarize(reports)
        print("\n  pass=%d mismatch=%d insufficient=%d invalid=%d not_declared=%d" % (
            summary["pass"], summary["mismatch"], summary["insufficient"],
            summary["invalid"], summary["not_declared"]))
        print("  evidence: %s" % EVIDENCE_ROOT)

    failed = [report for report in reports
              if report.status in (STATUS_MISMATCH, STATUS_INVALID)
              or (args.require_behavior and report.status == STATUS_INSUFFICIENT)]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
