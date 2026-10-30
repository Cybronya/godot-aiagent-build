#!/usr/bin/env python3
"""Composite Behavior Protocol（Phase 1.46）—— 组合场景契约的加载 / 校验 / manifest 门禁。

Phase 1.40–1.45 的行为证据是「单个 Feature + 一组动作 + 一个观测窗口」。组合场景
（EscapeRoom：开关 → 条件聚合 → 门 → 物理通行）无法用那种形状安全表达：

    1. 契约属于**场景**而不是 Feature（`behavior[].scene` 只允许 `Features/<f>/` 内路径）；
    2. 链需要**分阶段**的动作与断言，阶段边界本身承载事件顺序；
    3. 链只完成一部分时必须记录失败阶段，不能整条判 PASS。

因此本模块引入一份**独立**的、显式受限的组合协议：

    composite_behavior_protocol.yaml  ──生成──>  probes/composite_behavior_manifest.json
              │                                            │
              │ extends（版本绑定）                          └─读取─> composite_behavior_probe.gd
              ▼
    behavior_protocol.yaml（动作 / 观测 / 信号能力的唯一权威）

它只增加三类约束，不复制能力定义：

    scenes:          允许被加载的 .tscn 白名单（受约束的场景资源路径）
    limits:          阶段 / 动作 / 观测 / 帧预算
    denied_actions:  组合契约不得使用的共享动作（不允许夹具写状态冒充交互）

契约文件：`.ai/context/composite_scenes/<scene_id>.yaml`

    scene_id: escape_room
    scene: Scenes/EscapeRoom.tscn        # 必须与协议白名单逐字一致
    features: [trigger_switch, condition_gate, openable_door, player_movement]
    preconditions:                       # 场景加载后、第一段动作前必须成立
      - {check: door.is_open, target: Mechanism/ExitDoor, equals: false}
    stages:
      - id: closed_door_blocks_traversal
        actions: [...]
        expected: [...]
        window_frames: 10

用法:
    python .ai/tools/scene_composer/composite_behavior_protocol.py --check-manifest
    python .ai/tools/scene_composer/composite_behavior_protocol.py --write-manifest
    python .ai/tools/scene_composer/composite_behavior_protocol.py --list-contracts

退出码：0 = 协议/契约有效且 manifest 一致；1 = 漂移或契约非法；2 = 输入错误。
"""

import argparse
import json
import os
import subprocess
import sys

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_DOTAI = os.path.dirname(_TOOLS)
PROJECT_ROOT = os.path.dirname(_DOTAI)

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import behavior_protocol                                       # noqa: E402
import instance_evidence                                       # noqa: E402

PROTOCOL_PATH = os.path.join(_DOTAI, "context", "composite_behavior_protocol.yaml")
MANIFEST_PATH = os.path.join(_HERE, "probes", "composite_behavior_manifest.json")
CONTRACTS_DIR = os.path.join(_DOTAI, "context", "composite_scenes")
PROBE_RES = "res://.ai/tools/scene_composer/probes/composite_behavior_probe.gd"

SUPPORTED_PROTOCOL_VERSION = 1
MANIFEST_VERSION = 1
DEFAULT_WINDOW_FRAMES = 30
MAX_CONTRACT_FILE_BYTES = 64 * 1024

_TOP_KEYS = {"protocol_version", "status", "description", "extends", "scenes", "limits",
             "denied_actions"}
_LIMIT_KEYS = {"min_stages", "max_stages", "max_actions_per_stage", "max_checks_per_stage",
               "max_window_frames", "max_total_frames"}
_CONTRACT_KEYS = {"scene_id", "scene", "summary", "features", "preconditions", "stages"}
_STAGE_KEYS = {"id", "actions", "expected", "window_frames"}


class CompositeProtocolError(Exception):
    """组合协议文件缺失 / 解析失败 / 结构非法 / 版本不兼容。"""


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader + 重复键检测（YAML 默认会静默覆盖）。"""


def _construct_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise CompositeProtocolError(
                "duplicate key %r at line %d" % (key, key_node.start_mark.line + 1))
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                _construct_mapping)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _identifier(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    for char in value:
        if not (char.islower() or char.isdigit() or char == "_"):
            return False
    return value[0].isalpha()


def _read_yaml(path: str) -> dict:
    if not os.path.isfile(path):
        raise CompositeProtocolError("composite protocol file not found: %s" % path)
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=_UniqueKeyLoader)
    except CompositeProtocolError:
        raise
    except (OSError, yaml.YAMLError) as exc:
        raise CompositeProtocolError("composite protocol unreadable: %s" % exc)
    if not isinstance(data, dict) or not data:
        raise CompositeProtocolError("composite protocol must be a non-empty mapping")
    return data


class CompositeProtocol:
    """已验证的组合协议视图；只读。"""

    def __init__(self, data: dict, path: str = ""):
        self.path = path or PROTOCOL_PATH
        self.version = data["protocol_version"]
        self.status = data.get("status", "current")
        self.extends_version = data["extends"]["version"]
        self.scenes = data["scenes"]
        self.limits = data["limits"]
        self.denied_actions = data["denied_actions"]

    # ------------------------------------------------------------ manifest
    def manifest(self) -> dict:
        return {
            "protocol_version": self.version,
            "manifest_version": MANIFEST_VERSION,
            "extends_protocol_version": self.extends_version,
            "scenes": dict(self.scenes),
            "limits": dict(self.limits),
            "denied_actions": [dict(item) for item in self.denied_actions],
        }

    def manifest_text(self) -> str:
        return json.dumps(self.manifest(), ensure_ascii=False, indent=2,
                          sort_keys=True) + "\n"

    def allowed_scene(self, scene_id: str) -> str:
        return self.scenes.get(scene_id) or ""

    # ------------------------------------------------------------ 契约校验
    def validate_contract(self, raw, expected_scene_id: str, behavior) -> tuple:
        """原始契约 -> (contract, errors)。expected_scene_id 来自文件名。"""
        errors = []
        if not isinstance(raw, dict):
            return None, ["Invalid composite contract: contract must be a mapping"]
        extra = set(raw) - _CONTRACT_KEYS
        if extra:
            return None, ["Invalid composite contract: unknown keys %s" % sorted(extra)]

        scene_id = raw.get("scene_id")
        if not _identifier(scene_id):
            return None, ["Invalid composite contract: scene_id must be a lowercase identifier"]
        if scene_id != expected_scene_id:
            return None, ["Invalid composite contract: scene_id %r does not match the file "
                          "name %r" % (scene_id, expected_scene_id)]
        allowed = self.scenes.get(scene_id)
        if not allowed:
            return None, ["Invalid composite contract: scene %r is not declared in the "
                          "composite protocol scenes allowlist" % scene_id]
        scene = raw.get("scene")
        if scene != allowed:
            return None, ["Invalid composite contract: scene %r must be exactly %r "
                          "(declared in the protocol allowlist)" % (scene, allowed)]
        if not _scene_file_exists(allowed):
            return None, ["Invalid composite contract: scene file not found: %s" % allowed]

        features = raw.get("features")
        if not isinstance(features, list) or not features:
            return None, ["Invalid composite contract: features must be a non-empty list"]
        unknown = [name for name in features if not _feature_exists(name)]
        if unknown:
            return None, ["Invalid composite contract: unknown Features %s" % unknown]
        if len(set(features)) != len(features):
            return None, ["Invalid composite contract: features has duplicates"]

        raw_pre = raw.get("preconditions") or []
        if not isinstance(raw_pre, list):
            return None, ["Invalid composite contract: preconditions must be a list"]
        preconditions = []
        for index, item in enumerate(raw_pre):
            entry, check_errors = behavior.validate_check(
                item, index, "%s.preconditions" % scene_id)
            if check_errors:
                errors.extend(_wrap(scene_id, check_errors))
                continue
            preconditions.append(entry)
        if errors:
            return None, errors

        raw_stages = raw.get("stages")
        if not isinstance(raw_stages, list) or not raw_stages:
            return None, ["Invalid composite contract: stages must be a non-empty list"]
        if not self.limits["min_stages"] <= len(raw_stages) <= self.limits["max_stages"]:
            return None, ["Invalid composite contract: %d stages outside limits [%d..%d]"
                          % (len(raw_stages), self.limits["min_stages"],
                             self.limits["max_stages"])]

        stages = []
        seen = set()
        total_frames = 0
        denied = {item["action"] for item in self.denied_actions}
        for index, raw_stage in enumerate(raw_stages):
            stage, stage_errors = self._validate_stage(raw_stage, index, scene_id, behavior,
                                                       denied)
            if stage_errors:
                errors.extend(stage_errors)
                continue
            if stage["id"] in seen:
                errors.append("Invalid composite contract: duplicate stage id %r"
                              % stage["id"])
                continue
            seen.add(stage["id"])
            total_frames += stage["frames"] + stage["window_frames"]
            stages.append(stage)
        if errors:
            return None, errors
        if total_frames > self.limits["max_total_frames"]:
            return None, ["Invalid composite contract: frame budget %d (advance + windows) "
                          "exceeds max_total_frames %d"
                          % (total_frames, self.limits["max_total_frames"])]

        return {"scene_id": scene_id, "scene": scene, "features": list(features),
                "preconditions": preconditions, "stages": stages,
                "total_frames": total_frames, "summary": str(raw.get("summary") or "")}, []

    def _validate_stage(self, raw, index: int, scene_id: str, behavior, denied: set) -> tuple:
        where = "%s.stages[%d]" % (scene_id, index)
        if not isinstance(raw, dict):
            return None, ["Invalid composite contract: %s must be a mapping" % where]
        extra = set(raw) - _STAGE_KEYS
        if extra:
            return None, ["Invalid composite contract: %s has unknown keys %s"
                          % (where, sorted(extra))]
        stage_id = raw.get("id")
        if not _identifier(stage_id):
            return None, ["Invalid composite contract: %s.id must be a lowercase identifier"
                          % where]
        label = "%s(%s)" % (where, stage_id)
        errors = []

        window = raw.get("window_frames", DEFAULT_WINDOW_FRAMES)
        if not _is_int(window) or not 1 <= window <= self.limits["max_window_frames"]:
            return None, ["Invalid composite contract: %s.window_frames must be 1..%d"
                          % (label, self.limits["max_window_frames"])]

        raw_actions = raw.get("actions")
        if not isinstance(raw_actions, list) or not raw_actions:
            return None, ["Invalid composite contract: %s.actions must be a non-empty list"
                          % label]
        if len(raw_actions) > self.limits["max_actions_per_stage"]:
            return None, ["Invalid composite contract: %s declares %d actions, limit %d"
                          % (label, len(raw_actions), self.limits["max_actions_per_stage"])]
        actions = []
        for position, item in enumerate(raw_actions):
            action, action_errors = behavior.validate_action(item, position)
            if action_errors:
                errors.extend(_wrap(label, action_errors))
                continue
            if action["type"] in denied:
                errors.append("Invalid composite contract: %s uses action %r which the "
                              "composite protocol denies" % (label, action["type"]))
                continue
            actions.append(action)
        if errors:
            return None, errors
        # 夹具顺序 / 至少一个行为动作 / 夹具数量（与单个 Feature 契约同一套规则）。
        errors.extend(_wrap(label, behavior.sequence_errors(actions)))
        if errors:
            return None, errors

        raw_expected = raw.get("expected")
        if not isinstance(raw_expected, list) or not raw_expected:
            return None, ["Invalid composite contract: %s.expected must be a non-empty list"
                          % label]
        if len(raw_expected) > self.limits["max_checks_per_stage"]:
            return None, ["Invalid composite contract: %s declares %d checks, limit %d"
                          % (label, len(raw_expected), self.limits["max_checks_per_stage"])]
        expected = []
        for position, item in enumerate(raw_expected):
            check, check_errors = behavior.validate_check(item, position,
                                                         "%s.expected" % label)
            if check_errors:
                errors.extend(_wrap(label, check_errors))
                continue
            expected.append(check)
        if errors:
            return None, errors

        frames = _advance_frames(actions, behavior)
        # 阶段级最小证据规则（Phase 1.45 零帧规则的组合形式）：阶段既不推进任何帧、
        # 期望又只断言「什么都没发生」时，首个观测点即满足，没有任何时间窗口支撑。
        if frames == 0 and not any(_check_has_evidence(entry) for entry in expected):
            return None, ["Invalid composite contract: %s asserts only the absence of "
                          "behaviour while no action advances frames; the stage would pass "
                          "without any observation window" % label]
        return {"id": stage_id, "actions": actions, "expected": expected,
                "window_frames": window, "frames": frames}, []


def _wrap(where: str, messages) -> list:
    """把共享协议的错误信息挂上组合契约的位置前缀（保留原文，不改语义）。"""
    out = []
    for message in messages:
        text = str(message)
        if text.startswith("Invalid behavior contract: "):
            text = text[len("Invalid behavior contract: "):]
        out.append("Invalid composite contract: %s: %s" % (where, text))
    return out


def _advance_frames(actions, behavior) -> int:
    total = 0
    for action in actions:
        spec = behavior.actions.get(action.get("type", ""), {})
        if not spec.get("advances_frames"):
            continue
        frames = action.get("params", {}).get("frames", 0)
        if _is_int(frames):
            total += frames
    return total


def _check_has_evidence(entry: dict) -> bool:
    """与 feature_behavior_evidence.check_has_evidence 同一语义（阶段级使用）。"""
    params = dict(entry.get("params") or {})
    params.update({key: value for key, value in entry.items()
                   if key not in ("check", "target", "params")})
    if entry.get("check") == "signal":
        count = params.get("count", 0)
        return _is_int(count) and count > 0
    return params.get("equals") is not False


def _scene_file_exists(relative: str) -> bool:
    if not isinstance(relative, str) or not relative.endswith(".tscn"):
        return False
    parts = relative.replace("\\", "/").split("/")
    if any(part in ("", ".", "..") for part in parts) or ":" in relative:
        return False
    return os.path.isfile(os.path.join(PROJECT_ROOT, *parts))


def _feature_exists(name) -> bool:
    if not isinstance(name, str) or not _identifier(name):
        return False
    return os.path.isdir(os.path.join(PROJECT_ROOT, "Features", name))


def load_protocol(path: str = "", behavior=None) -> CompositeProtocol:
    """严格加载组合协议；任何结构 / 版本问题都抛 CompositeProtocolError。"""
    source = path or PROTOCOL_PATH
    data = _read_yaml(source)
    errors = []
    extra = set(data) - _TOP_KEYS
    if extra:
        errors.append("unknown top-level keys: %s" % sorted(extra))
    version = data.get("protocol_version")
    if not _is_int(version) or version != SUPPORTED_PROTOCOL_VERSION:
        errors.append("incompatible protocol_version %r (expected %d)"
                      % (version, SUPPORTED_PROTOCOL_VERSION))
    if data.get("status", "current") != "current":
        errors.append("protocol status %r is not current" % data.get("status"))

    extends = data.get("extends")
    if not isinstance(extends, dict) or set(extends) != {"protocol", "version"}:
        errors.append("extends must be {protocol, version}")
        extends = {}
    elif extends.get("protocol") != "behavior_protocol.yaml":
        errors.append("extends.protocol must be behavior_protocol.yaml")
    elif not _is_int(extends.get("version")):
        errors.append("extends.version must be an integer")

    try:
        base = behavior if behavior is not None else behavior_protocol.load_protocol()
    except behavior_protocol.ProtocolError as exc:
        raise CompositeProtocolError("extends target is invalid: %s" % exc)
    if extends and extends.get("version") != base.version:
        errors.append("extends.version %r does not match behavior protocol version %r"
                      % (extends.get("version"), base.version))

    scenes = data.get("scenes")
    valid_scenes = {}
    if not isinstance(scenes, dict) or not scenes:
        errors.append("scenes must be a non-empty mapping")
    else:
        for scene_id, relative in scenes.items():
            if not _identifier(scene_id):
                errors.append("scenes.%s: invalid scene id" % scene_id)
                continue
            if not _scene_file_exists(relative):
                errors.append("scenes.%s: %r is not an existing .tscn inside the project"
                              % (scene_id, relative))
                continue
            valid_scenes[scene_id] = relative

    limits_raw = data.get("limits")
    limits = {}
    if not isinstance(limits_raw, dict):
        errors.append("limits must be a mapping")
    else:
        extra = set(limits_raw) - _LIMIT_KEYS
        if extra:
            errors.append("limits: unknown keys %s" % sorted(extra))
        for key in sorted(_LIMIT_KEYS):
            value = limits_raw.get(key)
            if not _is_int(value) or value < 1:
                errors.append("limits.%s must be a positive integer" % key)
                continue
            limits[key] = value
        if len(limits) == len(_LIMIT_KEYS):
            if limits["min_stages"] > limits["max_stages"]:
                errors.append("limits.min_stages must not exceed max_stages")
            if limits["max_window_frames"] > limits["max_total_frames"]:
                errors.append("limits.max_window_frames must not exceed max_total_frames")

    denied = data.get("denied_actions") or []
    valid_denied = []
    if not isinstance(denied, list):
        errors.append("denied_actions must be a list")
    else:
        seen = set()
        for item in denied:
            if not isinstance(item, dict) or set(item) != {"action", "reason"}:
                errors.append("denied_actions entries must be {action, reason}")
                continue
            action_id = item.get("action")
            if action_id not in base.actions:
                errors.append("denied_actions references unknown action %r" % (action_id,))
                continue
            if action_id in seen:
                errors.append("denied_actions has duplicates: %r" % action_id)
                continue
            if not isinstance(item.get("reason"), str) or not item["reason"].strip():
                errors.append("denied_actions.%s.reason must be a non-empty string"
                              % action_id)
                continue
            seen.add(action_id)
            valid_denied.append({"action": action_id, "reason": item["reason"]})

    if errors:
        raise CompositeProtocolError("; ".join(errors))
    return CompositeProtocol({"protocol_version": version, "status": "current",
                              "extends": {"version": extends["version"]},
                              "scenes": valid_scenes, "limits": limits,
                              "denied_actions": valid_denied}, source)


# ---------------------------------------------------------------- 契约集合

def contract_files(directory: str = "") -> list:
    target = directory or CONTRACTS_DIR
    if not os.path.isdir(target):
        return []
    return sorted(os.path.join(target, name) for name in os.listdir(target)
                  if name.endswith(".yaml"))


def load_contract_file(path: str):
    """读取单个契约 YAML（不校验）；返回 (raw, error)。"""
    if os.path.getsize(path) > MAX_CONTRACT_FILE_BYTES:
        return None, "contract file is larger than %d bytes" % MAX_CONTRACT_FILE_BYTES
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=_UniqueKeyLoader)
    except CompositeProtocolError:
        raise
    except (OSError, yaml.YAMLError) as exc:
        return None, "contract unreadable: %s" % exc
    return data, ""


def build_contracts(directory: str = "", protocol: CompositeProtocol = None,
                    behavior=None) -> tuple:
    """目录 -> (contracts, invalid)。

    invalid 里每项 = {"scene_id": <文件名 stem>, "errors": [...]}；契约非法时**不**
    进入 contracts，调用方必须把它报告为 INVALID，不得静默跳过。
    """
    if protocol is None:
        protocol = load_protocol(behavior=behavior)
    if behavior is None:
        behavior = behavior_protocol.load_protocol()
    contracts = []
    invalid = []
    for path in contract_files(directory):
        stem = os.path.splitext(os.path.basename(path))[0]
        try:
            raw, error = load_contract_file(path)
        except CompositeProtocolError as exc:
            invalid.append({"scene_id": stem, "errors": [str(exc)]})
            continue
        if error:
            invalid.append({"scene_id": stem, "errors": [error]})
            continue
        contract, errors = protocol.validate_contract(raw, stem, behavior)
        if errors:
            invalid.append({"scene_id": stem, "errors": list(errors)})
            continue
        contract["path"] = path
        contracts.append(contract)
    return contracts, invalid


# ---------------------------------------------------------------- manifest 门禁

def check_manifest(protocol: CompositeProtocol, path: str = "") -> list:
    """生成物与协议是否逐字一致；返回错误列表（空 = 一致）。"""
    target = path or MANIFEST_PATH
    if not os.path.isfile(target):
        return ["composite behavior manifest missing: %s" % target]
    try:
        with open(target, encoding="utf-8") as handle:
            current = json.load(handle)
    except (OSError, ValueError) as exc:
        return ["composite behavior manifest unreadable: %s" % exc]
    expected = protocol.manifest()
    if current != expected:
        diffs = [key for key in sorted(set(current) | set(expected))
                 if current.get(key) != expected.get(key)]
        return ["composite behavior manifest drift in %s; run "
                "composite_behavior_protocol.py --write-manifest" % ", ".join(diffs)]
    return []


def write_manifest(protocol: CompositeProtocol, path: str = "") -> str:
    target = path or MANIFEST_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(protocol.manifest_text())
    return target


# ---------------------------------------------------------------- 探针能力门禁

def probe_capabilities(project_root: str, godot: str = "", timeout_s: int = 90) -> dict:
    """运行组合探针的 --capabilities 模式，读取其真实实现映射（不猜测源码）。"""
    if not godot:
        raise CompositeProtocolError("godot executable not found")
    os.makedirs(os.path.join(_DOTAI, "tmp", "composite"), exist_ok=True)
    output = os.path.join(_DOTAI, "tmp", "composite", "capabilities-%d.json" % os.getpid())
    command = [godot, "--headless", "--path", project_root, "-s", PROBE_RES,
               "--", "--capabilities=%s" % os.path.abspath(output)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout_s,
                              stdin=subprocess.DEVNULL, cwd=project_root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CompositeProtocolError("composite probe capabilities failed: %s" % exc)
    if not os.path.isfile(output):
        raise CompositeProtocolError(
            "composite probe capabilities produced no result (exit=%s): %s"
            % (proc.returncode, (proc.stderr or "")[-300:]))
    try:
        with open(output, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise CompositeProtocolError("composite probe capabilities unreadable: %s" % exc)
    finally:
        try:
            os.remove(output)
        except OSError:
            pass
    if not isinstance(payload, dict):
        raise CompositeProtocolError("composite probe capabilities is not a JSON object")
    return payload


def check_capabilities(protocol: CompositeProtocol, behavior, capabilities: dict) -> list:
    """组合探针实际实现 ⇄ 共享协议能力 ⇄ 组合协议禁止项 的一致性。"""
    errors = []
    if capabilities.get("protocol_version") != behavior.version:
        errors.append("probe protocol_version %r != behavior protocol %r"
                      % (capabilities.get("protocol_version"), behavior.version))
    required = behavior.required_implementations()
    denied_impls = {behavior.actions[item["action"]]["implementation"]
                    for item in protocol.denied_actions}
    for kind in ("actions", "observations"):
        declared = set(required[kind]) - denied_impls
        actual = set(capabilities.get(kind) or [])
        missing = sorted(declared - actual)
        extra = sorted(actual - declared)
        if missing:
            errors.append("%s declared+allowed but not implemented by the composite probe: %s"
                          % (kind, missing))
        if extra:
            errors.append("%s implemented by the composite probe but not allowed: %s"
                          % (kind, extra))
    reported_denied = sorted(str(item) for item in (capabilities.get("denied_actions") or []))
    declared_denied = sorted(item["action"] for item in protocol.denied_actions)
    if reported_denied != declared_denied:
        errors.append("probe denied_actions %s != protocol %s"
                      % (reported_denied, declared_denied))
    if capabilities.get("manifest_error"):
        errors.append("probe manifest error: %s" % capabilities["manifest_error"])
    return errors


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Composite behavior protocol loader / manifest gate.")
    parser.add_argument("--protocol", default=PROTOCOL_PATH)
    parser.add_argument("--manifest", default=MANIFEST_PATH)
    parser.add_argument("--contracts-dir", default=CONTRACTS_DIR)
    parser.add_argument("--check-manifest", action="store_true")
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--list-contracts", action="store_true")
    args = parser.parse_args(argv)

    try:
        protocol = load_protocol(args.protocol)
        behavior = behavior_protocol.load_protocol()
    except (CompositeProtocolError, behavior_protocol.ProtocolError) as exc:
        print("FAIL: %s" % exc)
        return 1

    if args.write_manifest:
        print("manifest written: %s" % write_manifest(protocol, args.manifest))
    drift = check_manifest(protocol, args.manifest)
    print("Composite Behavior Protocol v%d (extends behavior protocol v%d)"
          % (protocol.version, protocol.extends_version))
    print("  scenes: %d, stages: %d..%d, total frames: %d"
          % (len(protocol.scenes), protocol.limits["min_stages"],
             protocol.limits["max_stages"], protocol.limits["max_total_frames"]))
    if drift:
        for message in drift:
            print("  FAIL: %s" % message)
        return 1
    print("  PASS: manifest matches the protocol")

    if args.list_contracts or args.check_manifest:
        contracts, invalid = build_contracts(args.contracts_dir, protocol, behavior)
        for item in invalid:
            print("  INVALID %s: %s" % (item["scene_id"], "; ".join(item["errors"])))
        if args.list_contracts:
            for contract in contracts:
                print("  %-16s %-28s %d stages / %d frames"
                      % (contract["scene_id"], contract["scene"],
                         len(contract["stages"]), contract["total_frames"]))
        if invalid:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
