#!/usr/bin/env python3
"""Behavior Protocol（Phase 1.41 / 1.42）—— 动作 / 观测能力的唯一权威定义。

Phase 1.40 的 Python 编排器与 GDScript 探针各自维护一份动作/观测注册表；新增能力
必须同时改两处，且没有任何门禁能发现漂移。本模块把「允许什么」收敛到
`.ai/context/behavior_protocol.yaml`：

    protocol.yaml  ──生成──>  probes/behavior_manifest.json  ──读取──>  GDScript 探针
          │
          └──严格加载──> Python 契约校验 / 一致性门禁

- YAML 是唯一权威定义（人写）；JSON manifest 是**生成物**（只读运行时清单），
  探针不解析 YAML，也不另存一份能力定义。
- 探针只保留「实现 ID → 处理方法」的映射；未在 manifest 声明的实现不会被使用。
- 协议缺失 / 损坏 / 版本不兼容 / 未实现项 → 一律失败，绝不降级为宽松模式。

协议结构（字段随现有实现，不为不存在的需求预设计）：

    protocol_version: 2
    status: current
    targets: {kinds: {none, node, node2d}}
    limits: {max_frames_per_action, max_total_frames, max_fixture_actions}
    actions:
      <id>:
        implementation: <探针实现 ID>
        implemented: true|false        # 声明但未实现 → 使用即 INVALID
        target: none|node|node2d
        fixture: true|false            # 前置设置动作：必须排在行为动作之前
        advances_frames: true|false     # 计入 max_total_frames 帧预算
        params: {<name>: {type, required, min, max, non_empty, values, default}}
    observations:
      <id>:
        implementation: <探针实现 ID>
        implemented: true|false
        target: node|node2d
        result: {type: bool|int|float|string}
        params: {...}
    signals:
      <id>: {signal: <真实信号名>, args: [bool|int|string]}
    properties:                        # 受约束状态设置白名单
      <id>: {property: <导出属性名>, class: <脚本全局类名>, values: [<合法值>]}

Phase 1.42：`limits` 是两端共用的帧/夹具预算（探针从 manifest 读取，不另存常量）；
`properties` 让 `state.set_property` 只能写协议声明的属性。

用法:
    python .ai/tools/scene_composer/behavior_protocol.py --check-manifest
    python .ai/tools/scene_composer/behavior_protocol.py --write-manifest
    python .ai/tools/scene_composer/behavior_protocol.py --capabilities --godot <path>

退出码：0 = 协议有效 / manifest 一致 / 能力匹配；1 = 漂移或能力不匹配；2 = 输入错误。
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_DOTAI = os.path.dirname(_TOOLS)
PROJECT_ROOT = os.path.dirname(_DOTAI)

PROTOCOL_PATH = os.path.join(_DOTAI, "context", "behavior_protocol.yaml")
MANIFEST_PATH = os.path.join(_HERE, "probes", "behavior_manifest.json")
PROBE_RES = "res://.ai/tools/scene_composer/probes/feature_behavior_probe.gd"
SUPPORTED_PROTOCOL_VERSION = 2
MANIFEST_VERSION = 2

PARAM_TYPES = {"bool", "int", "float", "string", "scalar_list", "signal_ref",
               "enum", "property_ref", "any"}
RESULT_TYPES = {"bool", "int", "float", "string"}
SIGNAL_ARG_TYPES = {"bool", "int", "string"}

_TOP_KEYS = {"protocol_version", "status", "description", "targets", "limits",
             "actions", "observations", "signals", "properties"}
_ACTION_KEYS = {"implementation", "implemented", "target", "params", "summary",
                "deprecated", "replaced_by", "fixture", "advances_frames"}
_OBSERVATION_KEYS = {"implementation", "implemented", "target", "result", "params",
                     "summary", "deprecated", "replaced_by"}
_SIGNAL_KEYS = {"signal", "args", "summary", "deprecated"}
_PARAM_KEYS = {"type", "required", "min", "max", "non_empty", "default", "description",
               "values"}
_RESULT_KEYS = {"type"}
_TARGET_KEYS = {"kinds"}
_LIMIT_KEYS = {"max_frames_per_action", "max_total_frames", "max_fixture_actions"}
_PROPERTY_KEYS = {"property", "class", "values", "summary"}


class ProtocolError(Exception):
    """协议文件缺失 / 解析失败 / 结构非法 / 版本不兼容。"""


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader + 重复键检测（YAML 默认会静默覆盖）。"""


def _construct_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ProtocolError("duplicate key %r at line %d" % (key, key_node.start_mark.line + 1))
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                 _construct_mapping)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_scalar(value) -> bool:
    return isinstance(value, (bool, int, str)) and not isinstance(value, float)


def _identifier(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    for char in value:
        if not (char.islower() or char.isdigit() or char in "_."):
            return False
    return value[0].isalpha()


def _read_protocol(path: str) -> dict:
    if not os.path.isfile(path):
        raise ProtocolError("protocol file not found: %s" % path)
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=_UniqueKeyLoader)
    except ProtocolError:
        raise
    except (OSError, yaml.YAMLError) as exc:
        raise ProtocolError("protocol unreadable: %s" % exc)
    if not isinstance(data, dict) or not data:
        raise ProtocolError("protocol must be a non-empty mapping")
    return data


def _validate_param_schema(name: str, raw, where: str, errors: list) -> dict:
    label = "%s.%s" % (where, name)
    if not _identifier(name):
        errors.append("%s: invalid parameter name" % label)
        return {}
    if not isinstance(raw, dict):
        errors.append("%s: parameter schema must be a mapping" % label)
        return {}
    extra = set(raw) - _PARAM_KEYS
    if extra:
        errors.append("%s: unknown keys %s" % (label, sorted(extra)))
        return {}
    kind = raw.get("type")
    if kind not in PARAM_TYPES:
        errors.append("%s: unknown type %r" % (label, kind))
        return {}
    required = raw.get("required", False)
    if not isinstance(required, bool):
        errors.append("%s.required must be a bool" % label)
        return {}
    spec = {"type": kind, "required": required}
    if "min" in raw or "max" in raw:
        if kind not in ("int", "float"):
            errors.append("%s: min/max are only valid for int or float" % label)
            return {}
        fallback = (-(2 ** 31), 2 ** 31) if kind == "int" else (-(2.0 ** 31), 2.0 ** 31)
        low = raw.get("min", fallback[0])
        high = raw.get("max", fallback[1])
        if kind == "int":
            valid = _is_int(low) and _is_int(high)
        else:
            valid = _is_number(low) and _is_number(high)
        if not valid or low > high:
            errors.append("%s: min/max must be numbers with min <= max" % label)
            return {}
        spec["min"] = low
        spec["max"] = high
    if "values" in raw:
        if kind != "enum":
            errors.append("%s: values is only valid for enum" % label)
            return {}
        values = raw["values"]
        if not isinstance(values, list) or not values or not all(
                _is_scalar(item) for item in values):
            errors.append("%s.values must be a non-empty list of scalars" % label)
            return {}
        if len(set(values)) != len(values):
            errors.append("%s.values has duplicates" % label)
            return {}
        spec["values"] = list(values)
    elif kind == "enum":
        errors.append("%s: enum requires values" % label)
        return {}
    if "non_empty" in raw:
        if kind != "string" or not isinstance(raw["non_empty"], bool):
            errors.append("%s: non_empty must be a bool on a string parameter" % label)
            return {}
        spec["non_empty"] = raw["non_empty"]
    if kind in ("signal_ref", "property_ref") and not required:
        errors.append("%s: %s parameters must be required" % (label, kind))
        return {}
    if "default" in raw:
        if required:
            errors.append("%s: a required parameter cannot have a default" % label)
            return {}
        default = raw["default"]
        if kind == "any" or not _param_value_ok(default, spec):
            errors.append("%s.default does not match type %s" % (label, kind))
            return {}
        spec["default"] = default
    if "description" in raw and not isinstance(raw["description"], str):
        errors.append("%s.description must be a string" % label)
        return {}
    return spec


def _is_number(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool))


def _param_value_ok(value, spec: dict) -> bool:
    kind = spec.get("type")
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        if not _is_int(value):
            return False
        return spec.get("min", -(2 ** 31)) <= value <= spec.get("max", 2 ** 31)
    if kind == "float":
        if not _is_number(value):
            return False
        return spec.get("min", -(2.0 ** 31)) <= value <= spec.get("max", 2.0 ** 31)
    if kind == "string":
        if not isinstance(value, str):
            return False
        return not spec.get("non_empty") or bool(value.strip())
    if kind == "scalar_list":
        return isinstance(value, list) and all(_is_scalar(item) for item in value)
    if kind in ("signal_ref", "property_ref"):
        return isinstance(value, str) and bool(value)
    if kind == "enum":
        return value in (spec.get("values") or [])
    if kind == "any":
        return value is not None
    return False


def _comparator_errors(params: dict, result_type: str, label: str) -> list:
    """浮点观测必须给出可判定比较（equals±tolerance 或 min/max 区间）。"""
    errors = []
    has_equals = "equals" in params
    has_range = "min" in params or "max" in params
    if "tolerance" in params and not has_equals:
        errors.append("Invalid behavior contract: %s.tolerance requires equals" % label)
    if "min" in params and "max" in params and params["min"] > params["max"]:
        errors.append("Invalid behavior contract: %s.min must be <= %s.max" % (label, label))
    if result_type == "float" and not has_equals and not has_range:
        errors.append("Invalid behavior contract: %s declares neither equals nor min/max; "
                      "a float observation must be decidable" % label)
    return errors


class BehaviorProtocol:
    """已验证的协议视图；只读，供 Python 契约校验与一致性门禁使用。"""

    def __init__(self, data: dict, path: str = ""):
        self.path = path or PROTOCOL_PATH
        self.version = data["protocol_version"]
        self.status = data.get("status", "current")
        self.targets = data["targets"]
        self.limits = data["limits"]
        self.actions = data["actions"]
        self.observations = data["observations"]
        self.signals = data["signals"]
        self.properties = data["properties"]

    # ------------------------------------------------------------ 查询
    def action(self, action_id: str) -> dict:
        return self.actions.get(action_id) or {}

    def observation(self, observation_id: str) -> dict:
        return self.observations.get(observation_id) or {}

    def signal(self, signal_id: str) -> dict:
        return self.signals.get(signal_id) or {}

    def property(self, property_id: str) -> dict:
        return self.properties.get(property_id) or {}

    def required_implementations(self) -> dict:
        """协议声明且已实现的能力 -> 探针实现 ID。"""
        actions = {spec["implementation"] for spec in self.actions.values()
                   if spec.get("implemented") and not spec.get("deprecated")}
        observations = {spec["implementation"] for spec in self.observations.values()
                        if spec.get("implemented") and not spec.get("deprecated")}
        return {"actions": sorted(actions), "observations": sorted(observations)}

    # ------------------------------------------------------------ manifest
    def manifest(self) -> dict:
        def params(spec: dict) -> dict:
            out = {}
            for name, param in (spec.get("params") or {}).items():
                out[name] = {key: param[key] for key in
                             ("type", "required", "min", "max", "non_empty", "values",
                              "default")
                             if key in param}
            return out

        return {
            "protocol_version": self.version,
            "manifest_version": MANIFEST_VERSION,
            "limits": dict(self.limits),
            "actions": {name: {"implementation": spec["implementation"],
                               "implemented": spec["implemented"],
                               "target": spec["target"],
                               "fixture": spec["fixture"],
                               "advances_frames": spec["advances_frames"],
                               "params": params(spec)}
                        for name, spec in self.actions.items()},
            "observations": {name: {"implementation": spec["implementation"],
                                    "implemented": spec["implemented"],
                                    "target": spec["target"],
                                    "result": {"type": spec["result"]["type"]},
                                    "params": params(spec)}
                             for name, spec in self.observations.items()},
            "signals": {name: {"signal": spec["signal"], "args": list(spec["args"])}
                        for name, spec in self.signals.items()},
            "properties": {name: {"property": spec["property"], "class": spec["class"],
                                  "values": list(spec["values"])}
                           for name, spec in self.properties.items()},
        }

    def manifest_text(self) -> str:
        return json.dumps(self.manifest(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    # ------------------------------------------------------------ 契约校验
    def validate_action(self, raw, index: int) -> tuple:
        where = "actions[%d]" % index
        errors = []
        if not isinstance(raw, dict):
            return None, ["Invalid behavior contract: %s must be a mapping" % where]
        action_type = raw.get("type")
        if not isinstance(action_type, str) or action_type not in self.actions:
            return None, ["Invalid behavior contract: %s.type %r is not a registered action"
                          % (where, action_type)]
        spec = self.actions[action_type]
        if spec.get("deprecated"):
            errors.append("Invalid behavior contract: %s.type %r is deprecated"
                          % (where, action_type))
        if not spec["implemented"]:
            errors.append("Invalid behavior contract: %s.type %r is declared but not "
                          "implemented" % (where, action_type))
        params, param_errors = self._validate_params(spec.get("params") or {},
                                                     raw.get("params"), where, errors)
        target = raw.get("target", ".")
        if not _valid_target(target):
            errors.append("Invalid behavior contract: %s.target %r is not a scene path"
                          % (where, target))
        elif spec["target"] == "none" and str(target).strip() not in ("", "."):
            errors.append("Invalid behavior contract: %s.target %r is not allowed for "
                          "action %r (target kind none)" % (where, target, action_type))
        errors.extend(self._check_property_params(spec.get("params") or {}, params, where))
        if errors:
            return None, errors
        return {"type": action_type, "target": str(target).strip(), "params": params}, []

    def _check_property_params(self, schema: dict, values: dict, where: str) -> list:
        """property_ref 参数 → 引用的属性必须已声明，且 value 落在其值域内。"""
        errors = []
        refs = [name for name, spec in schema.items() if spec.get("type") == "property_ref"]
        if not refs:
            return errors
        for ref_name in refs:
            if "value" not in schema or schema["value"].get("type") != "any":
                errors.append("Invalid behavior contract: %s.params declares %s but no "
                              "'value' parameter; the protocol is malformed"
                              % (where, ref_name))
                continue
            property_id = values.get(ref_name)
            if not isinstance(property_id, str) or not property_id:
                continue
            spec = self.properties.get(property_id)
            if spec is None:
                errors.append("Invalid behavior contract: %s.params.%s %r is not a "
                              "registered property" % (where, ref_name, property_id))
                continue
            value = values.get("value")
            if value not in spec["values"]:
                errors.append("Invalid behavior contract: %s.params.value %r is not an "
                              "allowed value for property %r %s"
                              % (where, value, property_id, spec["values"]))
        return errors

    def sequence_errors(self, actions) -> list:
        """动作序列的预算与夹具顺序（fixture 只能在行为动作之前）。"""
        errors = []
        totals = {"frames": 0, "fixtures": 0, "behaviors": 0}
        seen_behavior = False
        for index, action in enumerate(actions):
            spec = self.actions.get(action.get("type", ""), {})
            if spec.get("fixture"):
                totals["fixtures"] += 1
                if seen_behavior:
                    errors.append("Invalid behavior contract: actions[%d] is a fixture "
                                  "action (state setup) but follows a behavior action; "
                                  "setup must come first" % index)
            else:
                totals["behaviors"] += 1
                seen_behavior = True
            if spec.get("advances_frames"):
                frames = action.get("params", {}).get("frames", 0)
                if isinstance(frames, int) and not isinstance(frames, bool):
                    totals["frames"] += frames
        if totals["behaviors"] == 0:
            errors.append("Invalid behavior contract: at least one non-fixture (behavior) "
                          "action is required; setup alone can never prove behavior")
        if totals["fixtures"] > self.limits["max_fixture_actions"]:
            errors.append("Invalid behavior contract: %d fixture actions exceed the limit %d"
                          % (totals["fixtures"], self.limits["max_fixture_actions"]))
        return errors

    def frame_budget_errors(self, actions, window_frames: int) -> list:
        """帧预算：所有推进动作 + window_frames 不得超过 max_total_frames。"""
        errors = []
        total = int(window_frames)
        for action in actions:
            spec = self.actions.get(action.get("type", ""), {})
            if not spec.get("advances_frames"):
                continue
            frames = action.get("params", {}).get("frames", 0)
            if isinstance(frames, int) and not isinstance(frames, bool):
                total += frames
        if total > self.limits["max_total_frames"]:
            errors.append("Invalid behavior contract: frame budget %d (advance + "
                          "window_frames) exceeds max_total_frames %d"
                          % (total, self.limits["max_total_frames"]))
        return errors

    def validate_check(self, raw, index: int, where: str) -> tuple:
        label = "%s[%d]" % (where, index)
        if not isinstance(raw, dict):
            return None, ["Invalid behavior contract: %s must be a mapping" % label]
        check = raw.get("check")
        if not isinstance(check, str) or check not in self.observations:
            return None, ["Invalid behavior contract: %s.check %r is not a registered check"
                          % (label, raw.get("check"))]
        spec = self.observations[check]
        errors = []
        if spec.get("deprecated"):
            errors.append("Invalid behavior contract: %s.check %r is deprecated"
                          % (label, check))
        if not spec["implemented"]:
            errors.append("Invalid behavior contract: %s.check %r is declared but not "
                          "implemented" % (label, check))
        target = raw.get("target", ".")
        if not _valid_target(target):
            errors.append("Invalid behavior contract: %s.target %r is not a scene path"
                          % (label, target))
        values = {key: value for key, value in raw.items() if key not in ("check", "target")}
        params, param_errors = self._validate_params(spec.get("params") or {}, values,
                                                     label, errors)
        errors.extend(param_errors)
        if errors:
            return None, errors
        if "entry" in params:
            signal_spec = self.signals.get(params["entry"])
            if signal_spec is None:
                return None, ["Invalid behavior contract: %s.params.entry %r is not a "
                              "registered signal" % (label, params["entry"])]
            if "last_args" in params:
                args = params["last_args"]
                declared = signal_spec["args"]
                if len(args) > len(declared):
                    return None, ["Invalid behavior contract: %s.params.last_args has more "
                                  "arguments than signal %r declares" % (label, params["entry"])]
                for position, item in enumerate(args):
                    if not _type_matches_signal(item, declared[position]):
                        return None, ["Invalid behavior contract: %s.params.last_args[%d] "
                                      "does not match signal type %s"
                                      % (label, position, declared[position])]
        elif "equals" in params:
            result_type = spec["result"]["type"]
            if not _type_matches_result(params["equals"], result_type):
                return None, ["Invalid behavior contract: %s.params.equals does not match "
                              "observation result type %s" % (label, result_type)]
        errors.extend(_comparator_errors(params, spec["result"]["type"], label))
        if errors:
            return None, errors
        entry = {"check": check, "target": str(target).strip()}
        entry.update(params)
        return entry, []

    def _validate_params(self, schema: dict, values, where: str, errors: list) -> tuple:
        if values is None:
            values = {}
        if not isinstance(values, dict):
            errors.append("Invalid behavior contract: %s.params must be a mapping" % where)
            return {}, ["params"]
        extra = set(values) - set(schema)
        if extra:
            errors.append("Invalid behavior contract: %s.params has unknown keys %s"
                          % (where, sorted(extra)))
        normalized = {}
        for name, spec in schema.items():
            if name not in values:
                if spec.get("required"):
                    errors.append("Invalid behavior contract: %s.params.%s is required"
                                  % (where, name))
                elif "default" in spec:
                    normalized[name] = spec["default"]
                continue
            value = values[name]
            if not _param_value_ok(value, spec):
                errors.append("Invalid behavior contract: %s.params.%s does not match type %s"
                              % (where, name, spec["type"]))
                continue
            normalized[name] = value
        return normalized, []


def _type_matches_signal(value, declared: str) -> bool:
    if declared == "bool":
        return isinstance(value, bool)
    if declared == "int":
        return _is_int(value)
    return isinstance(value, str)


def _type_matches_result(value, declared: str) -> bool:
    if declared == "bool":
        return isinstance(value, bool)
    if declared == "int":
        return _is_int(value)
    if declared == "float":
        return _is_number(value)
    return isinstance(value, str)


def _valid_target(target) -> bool:
    if not isinstance(target, str) or not target.strip():
        return False
    text = target.strip()
    if text in (".", "@actor"):
        return True
    if text.startswith("@actor/"):
        text = text[len("@actor/"):]
    if ".." in text or text.startswith("/") or "\\" in text:
        return False
    return bool(text)


# ---------------------------------------------------------------- 加载与校验

def load_protocol(path: str = "") -> BehaviorProtocol:
    """严格加载协议；任何结构 / 版本问题都抛 ProtocolError（不降级）。"""
    source = path or PROTOCOL_PATH
    data = _read_protocol(source)
    errors = []
    extra = set(data) - _TOP_KEYS
    if extra:
        errors.append("unknown top-level keys: %s" % sorted(extra))
    version = data.get("protocol_version")
    if not _is_int(version):
        errors.append("protocol_version must be an integer")
    elif version != SUPPORTED_PROTOCOL_VERSION:
        errors.append("incompatible protocol_version %r (expected %d)"
                      % (version, SUPPORTED_PROTOCOL_VERSION))
    if data.get("status", "current") != "current":
        errors.append("protocol status %r is not current" % data.get("status"))
    targets = data.get("targets")
    if not isinstance(targets, dict) or set(targets) - _TARGET_KEYS:
        errors.append("targets must be a mapping with only 'kinds'")
        kinds = {}
    else:
        kinds = targets.get("kinds")
        if not isinstance(kinds, dict) or not kinds or not all(
                isinstance(key, str) and isinstance(value, str) for key, value in kinds.items()):
            errors.append("targets.kinds must be a non-empty mapping of name -> description")
            kinds = {}
    actions = data.get("actions")
    observations = data.get("observations")
    signals = data.get("signals")
    for name, section in (("actions", actions), ("observations", observations),
                          ("signals", signals)):
        if not isinstance(section, dict) or not section:
            errors.append("%s must be a non-empty mapping" % name)

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
        if len(limits) == len(_LIMIT_KEYS) and (limits["max_frames_per_action"]
                                                > limits["max_total_frames"]):
            errors.append("limits.max_frames_per_action must not exceed max_total_frames")

    valid_actions = {}
    for name, raw in (actions or {}).items():
        label = "actions.%s" % name
        if not _identifier(name):
            errors.append("%s: invalid action id" % label)
            continue
        if not isinstance(raw, dict):
            errors.append("%s: must be a mapping" % label)
            continue
        extra = set(raw) - _ACTION_KEYS
        if extra:
            errors.append("%s: unknown keys %s" % (label, sorted(extra)))
            continue
        implementation = raw.get("implementation")
        if not isinstance(implementation, str) or not _identifier(implementation):
            errors.append("%s.implementation must be a lowercase identifier" % label)
            continue
        implemented = raw.get("implemented")
        if not isinstance(implemented, bool):
            errors.append("%s.implemented must be a bool (explicit capability declaration)"
                          % label)
            continue
        target = raw.get("target")
        if target not in kinds:
            errors.append("%s.target %r is not a declared target kind" % (label, target))
            continue
        params_raw = raw.get("params", {})
        if not isinstance(params_raw, dict):
            errors.append("%s.params must be a mapping" % label)
            continue
        params = {}
        for param_name, param_raw in params_raw.items():
            spec = _validate_param_schema(param_name, param_raw, label + ".params", errors)
            if spec:
                params[param_name] = spec
        if raw.get("deprecated") is not None and not isinstance(raw["deprecated"], bool):
            errors.append("%s.deprecated must be a bool" % label)
            continue
        if raw.get("deprecated"):
            replacement = raw.get("replaced_by")
            if not isinstance(replacement, str) or replacement not in (actions or {}):
                errors.append("%s.replaced_by must reference another action" % label)
                continue
        fixture = raw.get("fixture", False)
        if not isinstance(fixture, bool):
            errors.append("%s.fixture must be a bool" % label)
            continue
        advances = raw.get("advances_frames", False)
        if not isinstance(advances, bool):
            errors.append("%s.advances_frames must be a bool" % label)
            continue
        if advances:
            frames = params.get("frames") or {}
            if frames.get("type") != "int" or not frames.get("required"):
                errors.append("%s.advances_frames requires a required int param 'frames'"
                              % label)
                continue
            if limits and frames.get("max", 2 ** 31) > limits["max_frames_per_action"]:
                errors.append("%s.params.frames.max exceeds limits.max_frames_per_action (%d)"
                              % (label, limits["max_frames_per_action"]))
                continue
        valid_actions[name] = {"implementation": implementation, "implemented": implemented,
                               "target": target, "params": params,
                               "fixture": fixture, "advances_frames": advances,
                               "deprecated": bool(raw.get("deprecated", False))}

    valid_observations = {}
    for name, raw in (observations or {}).items():
        label = "observations.%s" % name
        if not _identifier(name):
            errors.append("%s: invalid observation id" % label)
            continue
        if not isinstance(raw, dict):
            errors.append("%s: must be a mapping" % label)
            continue
        extra = set(raw) - _OBSERVATION_KEYS
        if extra:
            errors.append("%s: unknown keys %s" % (label, sorted(extra)))
            continue
        implementation = raw.get("implementation")
        if not isinstance(implementation, str) or not _identifier(implementation):
            errors.append("%s.implementation must be a lowercase identifier" % label)
            continue
        implemented = raw.get("implemented")
        if not isinstance(implemented, bool):
            errors.append("%s.implemented must be a bool" % label)
            continue
        target = raw.get("target")
        if target not in kinds:
            errors.append("%s.target %r is not a declared target kind" % (label, target))
            continue
        result_raw = raw.get("result")
        if not isinstance(result_raw, dict) or set(result_raw) - _RESULT_KEYS \
                or result_raw.get("type") not in RESULT_TYPES:
            errors.append("%s.result must be {type: bool|int|float|string}" % label)
            continue
        params_raw = raw.get("params", {})
        if not isinstance(params_raw, dict):
            errors.append("%s.params must be a mapping" % label)
            continue
        params = {}
        for param_name, param_raw in params_raw.items():
            spec = _validate_param_schema(param_name, param_raw, label + ".params", errors)
            if spec:
                params[param_name] = spec
        if raw.get("deprecated") is not None and not isinstance(raw["deprecated"], bool):
            errors.append("%s.deprecated must be a bool" % label)
            continue
        if raw.get("deprecated"):
            replacement = raw.get("replaced_by")
            if not isinstance(replacement, str) or replacement not in (observations or {}):
                errors.append("%s.replaced_by must reference another observation" % label)
                continue
        valid_observations[name] = {"implementation": implementation,
                                    "implemented": implemented, "target": target,
                                    "result": {"type": result_raw["type"]},
                                    "params": params,
                                    "deprecated": bool(raw.get("deprecated", False))}

    valid_signals = {}
    for name, raw in (signals or {}).items():
        label = "signals.%s" % name
        if not _identifier(name):
            errors.append("%s: invalid signal id" % label)
            continue
        if not isinstance(raw, dict):
            errors.append("%s: must be a mapping" % label)
            continue
        extra = set(raw) - _SIGNAL_KEYS
        if extra:
            errors.append("%s: unknown keys %s" % (label, sorted(extra)))
            continue
        signal_name = raw.get("signal")
        if not isinstance(signal_name, str) or not _identifier(signal_name):
            errors.append("%s.signal must be a real signal name" % label)
            continue
        args = raw.get("args", [])
        if not isinstance(args, list) or not all(item in SIGNAL_ARG_TYPES for item in args):
            errors.append("%s.args must be a list of bool|int|string" % label)
            continue
        valid_signals[name] = {"signal": signal_name, "args": list(args)}

    valid_properties = {}
    for name, raw in (data.get("properties") or {}).items():
        label = "properties.%s" % name
        if not _identifier(name):
            errors.append("%s: invalid property id" % label)
            continue
        if not isinstance(raw, dict):
            errors.append("%s: must be a mapping" % label)
            continue
        extra = set(raw) - _PROPERTY_KEYS
        if extra:
            errors.append("%s: unknown keys %s" % (label, sorted(extra)))
            continue
        prop = raw.get("property")
        if not isinstance(prop, str) or not _identifier(prop):
            errors.append("%s.property must be a lowercase identifier" % label)
            continue
        klass = raw.get("class")
        if not isinstance(klass, str) or not klass[:1].isalpha() or not all(
                char.isalnum() or char == "_" for char in klass):
            errors.append("%s.class must be a script global class name" % label)
            continue
        values = raw.get("values")
        if not isinstance(values, list) or not values or not all(
                isinstance(item, str) and item for item in values):
            errors.append("%s.values must be a non-empty list of strings" % label)
            continue
        if len(set(values)) != len(values):
            errors.append("%s.values has duplicates" % label)
            continue
        valid_properties[name] = {"property": prop, "class": klass, "values": list(values)}

    # property_ref 必须引用已声明的属性，并伴随一个 any 类型的 value 参数。
    for name, spec in valid_actions.items():
        for param_name, param in spec["params"].items():
            if param["type"] != "property_ref":
                continue
            if not param.get("required"):
                errors.append("actions.%s.params.%s must be required" % (name, param_name))
            if not valid_properties:
                errors.append("actions.%s.params.%s references no properties"
                              % (name, param_name))
            if (spec["params"].get("value") or {}).get("type") != "any":
                errors.append("actions.%s declares %s but no 'value' parameter"
                              % (name, param_name))

    # signal_ref 必须引用真实存在的 signal id；signal 观测必须声明 entry/count。
    for name, spec in valid_observations.items():
        for param_name, param in spec["params"].items():
            if param["type"] == "signal_ref":
                if not param.get("required"):
                    errors.append("observations.%s.params.%s must be required"
                                  % (name, param_name))
                if not valid_signals:
                    errors.append("observations.%s.params.%s references no signals"
                                  % (name, param_name))
        if spec["implementation"] == "observe_signal":
            for required in ("entry", "count"):
                if required not in spec["params"]:
                    errors.append("observations.%s must declare params.%s" % (name, required))

    if errors:
        raise ProtocolError("; ".join(errors))
    return BehaviorProtocol({"protocol_version": version, "status": "current",
                             "targets": {"kinds": kinds}, "limits": limits,
                             "actions": valid_actions,
                             "observations": valid_observations, "signals": valid_signals,
                             "properties": valid_properties},
                            source)


# ---------------------------------------------------------------- manifest 门禁

def check_manifest(protocol: BehaviorProtocol, path: str = "") -> list:
    """生成物与协议是否逐字一致；返回错误列表（空 = 一致）。"""
    target = path or MANIFEST_PATH
    if not os.path.isfile(target):
        return ["behavior manifest missing: %s" % target]
    try:
        with open(target, encoding="utf-8") as handle:
            current = json.load(handle)
    except (OSError, ValueError) as exc:
        return ["behavior manifest unreadable: %s" % exc]
    expected = protocol.manifest()
    if current != expected:
        diffs = []
        for key in sorted(set(current) | set(expected)):
            if current.get(key) != expected.get(key):
                diffs.append(key)
        return ["behavior manifest drift in %s; run behavior_protocol.py --write-manifest"
                % ", ".join(diffs)]
    return []


def write_manifest(protocol: BehaviorProtocol, path: str = "") -> str:
    target = path or MANIFEST_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(protocol.manifest_text())
    return target


# ---------------------------------------------------------------- 探针能力门禁

def probe_capabilities(project_root: str, godot: str = "", timeout_s: int = 60) -> dict:
    """运行探针的 --capabilities 模式，读取其真实实现映射（不猜测源码）。"""
    if not godot:
        raise ProtocolError("godot executable not found")
    os.makedirs(os.path.join(_DOTAI, "tmp", "behavior"), exist_ok=True)
    output = os.path.join(_DOTAI, "tmp", "behavior",
                          "capabilities-%d-%s.json" % (os.getpid(), uuid.uuid4().hex[:8]))
    command = [godot, "--headless", "--path", project_root, "-s", PROBE_RES,
               "--", "--capabilities=%s" % os.path.abspath(output)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout_s,
                              stdin=subprocess.DEVNULL, cwd=project_root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtocolError("probe capabilities failed: %s" % exc)
    if not os.path.isfile(output):
        raise ProtocolError("probe capabilities produced no result (exit=%s): %s"
                            % (proc.returncode, (proc.stderr or "")[-300:]))
    try:
        with open(output, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ProtocolError("probe capabilities unreadable: %s" % exc)
    finally:
        try:
            os.remove(output)
        except OSError:
            pass
    if not isinstance(payload, dict):
        raise ProtocolError("probe capabilities is not a JSON object")
    return payload


def check_capabilities(protocol: BehaviorProtocol, capabilities: dict) -> list:
    """协议声明 ⇄ 探针实现映射的一致性；返回错误列表（空 = 一致）。"""
    errors = []
    if capabilities.get("protocol_version") != protocol.version:
        errors.append("probe protocol_version %r != protocol %r"
                      % (capabilities.get("protocol_version"), protocol.version))
    required = protocol.required_implementations()
    for kind in ("actions", "observations"):
        declared = set(required[kind])
        actual = set(capabilities.get(kind) or [])
        missing = sorted(declared - actual)
        extra = sorted(actual - declared)
        if missing:
            errors.append("%s declared but not implemented by probe: %s"
                          % (kind, missing))
        if extra:
            errors.append("%s implemented by probe but not declared in protocol: %s"
                          % (kind, extra))
    return errors


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Behavior protocol loader / manifest gate.")
    parser.add_argument("--protocol", default=PROTOCOL_PATH)
    parser.add_argument("--manifest", default=MANIFEST_PATH)
    parser.add_argument("--check-manifest", action="store_true")
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--capabilities", action="store_true",
                        help="compare the probe's real implementation map with the protocol")
    parser.add_argument("--project-root", default="")
    parser.add_argument("--godot", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not (args.check_manifest or args.write_manifest or args.capabilities):
        parser.print_help()
        return 2
    try:
        protocol = load_protocol(args.protocol)
    except ProtocolError as exc:
        print("FAIL: %s" % exc)
        return 1

    if args.write_manifest:
        path = write_manifest(protocol, args.manifest)
        print("manifest written: %s" % path)
    errors = check_manifest(protocol, args.manifest) if args.check_manifest else []
    if args.capabilities:
        root = args.project_root or PROJECT_ROOT
        binary = args.godot
        if not binary:
            sys.path.insert(0, _HERE)
            import runtime_instance_evidence as runtime_evidence
            binary = runtime_evidence.find_godot(root)
        try:
            errors.extend(check_capabilities(protocol, probe_capabilities(root, binary)))
        except ProtocolError as exc:
            errors.append(str(exc))

    payload = {"protocol_version": protocol.version,
               "required": protocol.required_implementations(),
               "errors": errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Behavior Protocol v%d" % protocol.version)
        print("  actions: %d, observations: %d, signals: %d"
              % (len(protocol.actions), len(protocol.observations), len(protocol.signals)))
        if errors:
            for error in errors:
                print("  FAIL: " + error)
        else:
            print("  PASS: " + ("manifest and probe implementations match the protocol"
                                if args.capabilities else "manifest matches the protocol"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
