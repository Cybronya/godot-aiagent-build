#!/usr/bin/env python3
"""Unified Layer Checks —— Scene / Gameplay / Level / Runtime 分层校验编排（Phase 1.15）。

职责边界（对应 Phase 1.15 任务书 4.1）：

    Scene 层    —— 场景文件存在、结构与节点引用合法、资源路径有效、实例化前提满足
                  （编排既有 check_scene_composition，不重新实现规则）。
    Gameplay 层 —— Blueprint 与生成配置结构合法、实体引用存在、关卡配置与生成契约一致
                  （编排既有 check_gameplay / check_level）。
    Runtime 层  —— 真实 Godot 能解析并实例化资源、运行期结论成立
                  （编排既有 check_runtime + runtime/run_scene；Godot 缺失时如实标记
                  unavailable，绝不伪装成 PASS）。

统一诊断格式（任务书 4.2；字段名与项目扁平字符串风格兼容）：

    {layer, code, severity, location, path, reason, hint}

    layer    检查层级（scene / gameplay / level / runtime）
    code     稳定错误代码（由各检查器的既有失败文本前缀映射；未识别文本回退
             <LAYER>_FAILURE，绝不丢弃原文）
    severity error | warning
    location 文件或资源位置
    path     字段 / 对象路径（level 层为 JSON 路径；其他层为空或消息内路径）
    reason   人类可读原因（检查器原始消息，原样保留）
    hint     修复建议（可选）

规则权威（任务书 4.3）：关卡契约规则的唯一权威是 `.ai/context/level_schema.yaml`；
Python（level_planner.validate_level）与 GDScript（Orchestration/level_config.gd）为
同一规则集的两个镜像实现，跨层一致性由
`validator/tests/test_cross_layer_contract.py`（C1–C8）自动化验证。
绑定作用域规则（I1）的权威实现是 `asset_registry/bind_assets.py::parse_explicit_bindings`。

退出码约定（与统一测试入口一致）：失败 = 1；Runtime 层被请求但 Godot 不可用 =
INCOMPLETE（同样非零），绝不静默跳过或伪装通过。
"""

from __future__ import annotations

import json
import os
import sys

_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # .ai/tools
_VALIDATOR_DIR = os.path.join(_TOOLS_DIR, "validator")
_RUNTIME_DIR = os.path.join(_TOOLS_DIR, "runtime")
if _VALIDATOR_DIR not in sys.path:
    sys.path.insert(0, _VALIDATOR_DIR)
if _RUNTIME_DIR not in sys.path:
    sys.path.insert(0, _RUNTIME_DIR)
_ASSET_REGISTRY_DIR = os.path.join(_TOOLS_DIR, "asset_registry")
if _ASSET_REGISTRY_DIR not in sys.path:
    sys.path.insert(0, _ASSET_REGISTRY_DIR)

LAYERS = ("scene", "gameplay", "level", "binding", "runtime")


def _diag(layer: str, code: str, severity: str, location: str = "",
          path: str = "", reason: str = "", hint: str = "") -> dict:
    return {"layer": layer, "code": code, "severity": severity, "location": location,
            "path": path, "reason": reason, "hint": hint}


def _code_by_prefix(message: str, table) -> tuple[str, str]:
    """(message) -> (code, hint)；按前缀表匹配，未命中回退层默认代码。"""
    for prefix, code, hint in table:
        if message.startswith(prefix):
            return code, hint
    return "", ""


# ---------- 稳定错误代码映射（前缀表；来源 = 各检查器既有失败文本） ----------

_GAMEPLAY_CODES = [
    ("Missing Entity Scene:", "GAMEPLAY_ENTITY_SCENE_MISSING",
     "declare scene: on the entity or generate Scenes/<Pascal>.tscn first"),
    ("Gameplay incomplete:", "GAMEPLAY_INCOMPLETE",
     "add the missing feature/entity to the blueprint or to a member entity"),
    ("Gameplay entity", "GAMEPLAY_ENTITY_NO_FEATURES",
     "give the entity at least one member feature"),
    ("Unknown System:", "GAMEPLAY_UNKNOWN_SYSTEM",
     "create Systems/<id>/system.yaml or remove the system reference"),
    ("Gameplay loop incomplete:", "GAMEPLAY_LOOP_INCOMPLETE",
     "give loop.end settlement semantics and a provider for the required capability"),
    ("Gameplay Blueprint missing gameplay.id", "GAMEPLAY_ID_MISSING",
     "set gameplay.id in the blueprint"),
    ("Gameplay Blueprint has no entities", "GAMEPLAY_NO_ENTITIES",
     "declare at least one entity with features"),
]

_SCENE_CODES = [
    ("Missing Feature:", "SCENE_FEATURE_MISSING",
     "add the feature to the blueprint or regenerate the scene"),
    ("Invalid Root Node Type", "SCENE_ROOT_TYPE",
     "the scene root must match blueprint root.type"),
    ("Missing Dependency", "SCENE_DEPENDENCY_MISSING",
     "compose the required feature or drop the requirement"),
]

_RUNTIME_CODES = [
    ("Runtime playtest TIMEOUT", "RUNTIME_TIMEOUT",
     "the scene did not finish within the configured duration"),
    ("Runtime playtest CRASH", "RUNTIME_CRASH",
     "inspect stderr; unparseable crash usually means a script/engine abort"),
    ("Runtime playtest FAIL", "RUNTIME_FAIL",
     "fix the runtime errors reported for this scene"),
    ("Runtime playtest produced", "RUNTIME_CONTRACT",
     "runtime-playtest contract forbids errors (or warnings) for this run"),
    ("status PASS contradicts", "RUNTIME_CONTRACT",
     "runtime_result status must agree with its own observations"),
    ("Unclassifiable runtime error", "RUNTIME_UNCLASSIFIED",
     "extend diagnose_runtime classification or fix the raw error"),
    ("no file/line location", "RUNTIME_LOCATION",
     "make the error locatable (file/line) so repair can target it"),
    ("runtime_result must be", "RUNTIME_RESULT_SCHEMA",
     "runtime_result.json must follow runtime_result_schema.yaml"),
]

# level 层失败文本以 JSON 路径开头（如 waves[0].entries[0].count: ...）
_LEVEL_FIRST_TOKEN_CODES = {
    "schema": "LEVEL_SCHEMA",
    "mode": "LEVEL_MODE",
    "waves": "LEVEL_WAVES",
    "holdout": "LEVEL_HOLDOUT",
    "boss": "LEVEL_BOSS",
    "stages": "LEVEL_STAGES",
    "exit": "LEVEL_EXIT",
    "victory": "LEVEL_VICTORY",
    "entities": "LEVEL_ENTITIES",
    "level": "LEVEL_ID",
    "root": "LEVEL_FORMAT",
}


def _level_code(message: str) -> tuple[str, str]:
    token = message.split(":")[0].split("[")[0].split(".")[0].strip()
    code = _LEVEL_FIRST_TOKEN_CODES.get(token, "LEVEL_CONTRACT_VIOLATION")
    return code, "fix the field pointed at by the JSON path (see level_schema.yaml)"


def diagnose(layer: str, message: str, location: str = "") -> dict:
    """检查器失败/警告文本 -> 统一诊断（原文不丢，未识别文本回退层默认代码）。"""
    if layer == "gameplay":
        code, hint = _code_by_prefix(message, _GAMEPLAY_CODES)
        code, hint = code or "GAMEPLAY_FAILURE", hint or "inspect the gameplay blueprint"
    elif layer == "scene":
        code, hint = _code_by_prefix(message, _SCENE_CODES)
        code, hint = code or "SCENE_FAILURE", hint or "inspect the scene blueprint and generated .tscn"
    elif layer == "runtime":
        code, hint = _code_by_prefix(message, _RUNTIME_CODES)
        code, hint = code or "RUNTIME_FAILURE", hint or "inspect the runtime_result observations"
    elif layer == "level":
        code, hint = _level_code(message)
    else:
        code, hint = "%s_FAILURE" % layer.upper(), "inspect the layer output"
    severity = "error"
    return _diag(layer, code, severity, location=location, reason=message, hint=hint)


def _layer_result(layer: str, checked, diagnostics, note: str = "") -> dict:
    return {
        "layer": layer,
        "checked": checked,
        "diagnostics": diagnostics,
        "errors": [d for d in diagnostics if d["severity"] == "error"],
        "warnings": [d for d in diagnostics if d["severity"] == "warning"],
        "ok": not any(d["severity"] == "error" for d in diagnostics),
        "note": note,
    }


def _convert_result(layer: str, result: dict, location: str) -> dict:
    """检查器 {failures, warnings} -> 统一层结果（warnings 映射为 warning 诊断）。"""
    diagnostics = [diagnose(layer, str(failure), location) for failure in result.get("failures") or []]
    for warning in result.get("warnings") or []:
        diag = diagnose(layer, str(warning), location)
        diag["severity"] = "warning"
        diagnostics.append(diag)
    return _layer_result(layer, result.get("checked", 0), diagnostics)


# ---------- 各层编排（只调用既有检查器，不重新实现规则） ----------


def run_scene_layer(blueprint_path: str, project_root: str,
                    scene_path: str = "") -> dict:
    """Scene 层：场景组合合法性（编排 check_scene_composition）。"""
    from check_scene_composition import check_scene_composition
    import yaml
    if not os.path.isfile(blueprint_path):
        return _layer_result("scene", 0, [diagnose(
            "scene", "Scene blueprint not found: %s" % blueprint_path, blueprint_path)])
    with open(blueprint_path, encoding="utf-8") as handle:
        blueprint_raw = yaml.safe_load(handle) or {}
    resolved_scene = scene_path
    if not resolved_scene:
        from scene_intent import intent_from_blueprint, intent_root
        intent, _errors = intent_from_blueprint(blueprint_raw)
        root_name = str(intent_root(intent).get("name") or "") if intent is not None else ""
        resolved_scene = os.path.join(project_root, "Scenes", "%s.tscn" % root_name) if root_name else ""
    if not resolved_scene or not os.path.isfile(resolved_scene):
        return _layer_result("scene", 0, [diagnose(
            "scene", "Scene file not found for blueprint: %s" % (resolved_scene or "<derived none>"),
            blueprint_path)])
    result = check_scene_composition(blueprint_raw, resolved_scene)
    return _convert_result("scene", result, resolved_scene)


def run_gameplay_layer(blueprint_path: str, project_root: str) -> dict:
    """Gameplay 层：Blueprint 结构 / 实体引用 / 循环闭合（编排 check_gameplay）。"""
    from check_gameplay import check_gameplay
    import yaml
    if not os.path.isfile(blueprint_path):
        return _layer_result("gameplay", 0, [diagnose(
            "gameplay", "Gameplay blueprint not found: %s" % blueprint_path, blueprint_path)])
    with open(blueprint_path, encoding="utf-8") as handle:
        blueprint = yaml.safe_load(handle) or {}
    result = check_gameplay(blueprint, project_root)
    return _convert_result("gameplay", result, blueprint_path)


def run_level_layer(level_path: str, project_root: str, plan_path: str = "") -> dict:
    """Level 层：关卡编排配置契约（编排 check_level -> level_planner.validate_level）。

    plan_path 给出时追加 LevelConfig ↔ composition_plan 交叉校验（Phase 1.21）；
    多阶段配置缺少 plan 时如实报告 INCOMPLETE（severity=info），不计入 warning/error。
    """
    from check_level import check_level_file
    try:
        report = check_level_file(level_path, project_root, plan_path or None)
    except ValueError as exc:
        return _layer_result("level", 0, [diagnose("level", str(exc), level_path)])
    diagnostics = [diagnose("level", str(failure), level_path)
                   for failure in report.get("failures") or []]
    if report.get("cross_check_skipped"):
        diagnostics.append(_diag(
            "level", "LEVEL_INFO_CROSS_CHECK_SKIPPED", "info", location=level_path,
            reason="multi-stage boss config was not cross-checked against a composition plan "
                   "(standalone LevelConfig validation only)",
            hint="pass --level-plan <composition_plan.yaml> to verify host/instance identity"))
    return _layer_result("level", report.get("checked", 0), diagnostics)


def run_binding_layer(bindings_dir: str, gameplay_blueprint: str = "",
                      project_root: str = "") -> dict:
    """Binding 层（Phase 1.18）：资产绑定文档的静态健康检查。

    权威实现 = asset_registry/check_binding_schema.py#check_bindings（唯一实现，
    不复制规则）。gameplay_blueprint 给出时做实体存在性检查；缺失时 checker
    如实返回「信息不足」note —— 本层把它转成 severity=info 的诊断（BINDING_INFO_*），
    绝不虚构校验成功，也绝不把它当错误。
    """
    from check_binding_schema import check_bindings, load_gameplay_blueprint
    blueprint = None
    if gameplay_blueprint:
        blueprint = load_gameplay_blueprint(gameplay_blueprint)
    result = check_bindings(bindings_dir, gameplay_blueprint=blueprint)
    location = gameplay_blueprint or bindings_dir
    diagnostics = [diagnose("binding", "%s (%s): %s" % (
        violation.get("detail") or violation.get("kind"), violation.get("kind"),
        violation.get("file")), location)
        for violation in result.get("violations") or []]
    for note in result.get("notes") or []:
        diagnostics.append(_diag("binding", "BINDING_INFO_INSUFFICIENT_INPUT",
                                 "info", location=location, reason=note,
                                 hint="pass --gameplay to validate entity-scoped "
                                      "bindings against declared entities"))
    if result.get("note"):
        diagnostics.append(_diag("binding", "BINDING_INFO_DIR_MISSING", "info",
                                 location=bindings_dir, reason=result["note"]))
    return _layer_result("binding", result.get("checked", 0), diagnostics)


def _godot_binary(project_root: str):
    """与 .ai/tools/runtime（runtime_result）一致的 Godot 二进制查找。"""
    from runtime_result import find_godot_binary
    return find_godot_binary(project_root)


def run_runtime_layer(project_root: str, scene: str = "",
                      result_path: str = "") -> dict:
    """Runtime 层：真实 Godot headless 运行或既有 runtime_result 判定。

    scene 非空 → 通过 runtime/run_scene 触发真实运行（耗时，显式 opt-in）；
    result_path 非空 → 只判定既有 runtime_result（不启动 Godot）。
    Godot 二进制不可用时返回 unavailable 结果（绝不伪装成 PASS）。
    """
    from check_runtime import check_runtime
    from runtime_result import read_result
    if result_path:
        if not os.path.isfile(result_path):
            return _layer_result("runtime", 0, [diagnose(
                "runtime", "runtime_result not found: %s" % result_path, result_path)])
        result = read_result(result_path)
        outcome = check_runtime(result, project_root)
        return _convert_result("runtime", outcome, result_path)

    godot = _godot_binary(project_root)
    if godot is None:
        return {
            "layer": "runtime", "checked": 0, "diagnostics": [],
            "errors": [], "warnings": [], "ok": False,
            "unavailable": "godot executable not found (checked project-parent "
                           "candidates and PATH); runtime layer cannot run",
            "note": "",
        }
    from run_scene import RuntimeInputError, run_runtime
    try:
        result = run_runtime(project=project_root, scene=scene)
    except RuntimeInputError as exc:
        return _layer_result("runtime", 0, [diagnose("runtime", str(exc), scene)])
    outcome = check_runtime(result, project_root)
    return _convert_result("runtime", outcome, result.get("scene") or scene)


def run_layers(project_root: str, scene_blueprints=None, gameplay_blueprints=None,
               level_configs=None, level_plans=None, runtime_scenes=None,
               runtime_results=None, bindings_dirs=None,
               binding_gameplay: str = "") -> dict:
    """统一编排入口：按请求执行各层，汇总结构化诊断。

    返回 {results: [...], unavailable: [...], diagnostics: [...], layers_run: [...]}。
    局部失败不阻断其他层（每层独立 try，异常转层内 error 诊断）。
    bindings_dirs：可选；给出时执行 binding 层（Phase 1.18）。
    """
    results, unavailable = [], []
    for blueprint_path in scene_blueprints or []:
        results.append(_guarded("scene", run_scene_layer, blueprint_path, project_root))
    for blueprint_path in gameplay_blueprints or []:
        results.append(_guarded("gameplay", run_gameplay_layer, blueprint_path, project_root))
    plans = list(level_plans or [])
    for index, level_path in enumerate(level_configs or []):
        plan_path = plans[index] if index < len(plans) else ""
        results.append(_guarded("level", run_level_layer, level_path, project_root, plan_path))
    for bindings_dir in bindings_dirs or []:
        results.append(_guarded("binding", run_binding_layer, bindings_dir,
                                binding_gameplay, project_root))
    for scene in runtime_scenes or []:
        results.append(_guarded("runtime", run_runtime_layer, project_root, scene))
    for result_path in runtime_results or []:
        results.append(_guarded("runtime", run_runtime_layer, project_root, "", result_path))
    for result in results:
        if result.get("unavailable"):
            unavailable.append({"layer": result["layer"], "reason": result["unavailable"]})
    diagnostics = [d for result in results for d in result.get("diagnostics") or []]
    layers_run = sorted({result["layer"] for result in results})
    return {"results": results, "unavailable": unavailable,
            "diagnostics": diagnostics, "layers_run": layers_run}


def _guarded(layer: str, runner, *args) -> dict:
    """单层执行护栏：检查器异常转层内 error 诊断，不阻断其他层（任务书 6.4）。"""
    try:
        return runner(*args)
    except Exception as exc:                                     # noqa: BLE001 - 护栏边界
        return _layer_result(layer, 0, [_diag(
            layer, "%s_LAYER_CRASH" % layer.upper(), "error",
            location=" ".join(str(a) for a in args),
            reason="layer check crashed: %s: %s" % (type(exc).__name__, exc),
            hint="run the layer's standalone CLI for a full traceback")])


def format_layer_report(unified: dict) -> list:
    """统一结果 -> 人类可读行（validate.py 的 Layer Checks 节）。"""
    lines = []
    for result in unified.get("results") or []:
        state = "PASS" if result.get("ok") else "FAIL"
        if result.get("unavailable"):
            state = "UNAVAILABLE"
        lines.append("  [%s] %s: checked=%d errors=%d warnings=%d %s" % (
            result["layer"], state, result.get("checked", 0),
            len(result.get("errors") or []), len(result.get("warnings") or []),
            result.get("note") or ""))
        for diag in result.get("diagnostics") or []:
            lines.append("      %s %s %s%s :: %s" % (
                diag["severity"].upper(), diag["code"],
                "[%s] " % diag["location"] if diag.get("location") else "",
                ("path=%s " % diag["path"]) if diag.get("path") else "",
                diag["reason"]))
            if diag.get("hint"):
                lines.append("        hint: %s" % diag["hint"])
    for item in unified.get("unavailable") or []:
        lines.append("  UNAVAILABLE [%s]: %s" % (item["layer"], item["reason"]))
    return lines
