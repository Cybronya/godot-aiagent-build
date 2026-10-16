#!/usr/bin/env python3
"""Discovery-to-Binding Adapter (Phase 1.8.2 Step 2) —— 显式候选选择 -> 显式绑定输入。

把 feature_discovery.py --json 的发现结果转换为 bind_assets.py --binding FILE
可接受的显式绑定覆盖文件（asset_binding_schema.yaml「显式绑定覆盖」节）：

    bindings:
      - role: idle          # 资源槽位角色（candidate.role），不是实体角色
        asset: slime_idle   # candidate.id（asset_index.json 唯一 id）

职责边界：
    - Adapter 只做「显式选择 -> 显式绑定输入」的确定性转换；
    - 不替代 bind_assets.py 的绑定算法（compatibility / resolved_from /
      confidence / overriding 优先级链全部由 bind_assets 运行时计算）；
    - 不复制槽位配置或评分规则（槽位出处是 Discovery payload 本身）；
    - 不静默选择 top1：候选选择必须由调用方显式提供（--select slot=asset_id）。

CLI:
    python discovery_to_binding.py --input discovery.json \\
        --select idle=slime_idle --select move=slime_move [--json] [-o out.yaml]
    # 或 --input-file discovery.json 省略时从 stdin 读 JSON。

退出码（与 feature_discovery 语义分层一致）:
    0  转换成功（含部分槽位成功；警告在 stderr/警告字段中）
    1  输入有效但无法表达明确绑定（缺选择/候选缺失/无匹配等，可诊断）
    2  结构性错误（schema_version 不支持 / 非 mapping / JSON 非法 / 选择引用
       不存在的 candidate 等）
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

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai

SCHEMA_VERSION = 1

# 只支持与 feature_discovery.SCHEMA_VERSION 对齐的契约版本；更高版本视为不兼容
# （新增字段不构成破坏，但本 Adapter 不猜测未声明字段的语义，需显式升级代码）。
SUPPORTED_SCHEMA_VERSIONS = (1,)

# 非致命诊断：Discovery 正常给出候选，可继续转换。以 feature_discovery.py 实际
# 语义为准（exit 0/1 但 payload 仍是可解析的 11 连键 JSON）：
#   unknown_role / input_not_parsed / seeded_by_role / no_feature_match /
#   no_asset_match —— 这些只说明「没有完美匹配」，候选可能仍存在。
# 致命诊断（error-path）：config_error / feature_index_missing / index_missing 中
# 的 asset_candidates 为 {} 或槽位全部空的场景 —— 由结构检查捕获，无需枚举 reason。
NONFATAL_REASONS = frozenset({
    "unknown_role", "input_not_parsed", "seeded_by_role",
    "no_feature_match", "no_asset_match",
})


class AdapterError(Exception):
    """Adapter 层结构/契约错误（对应退出码 2）。"""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


class SelectionError(Exception):
    """输入有效但无法表达明确绑定（对应退出码 1，可诊断）。"""

    def __init__(self, message: str, reason: str, diagnostics: list | None = None):
        super().__init__(message)
        self.reason = reason
        self.diagnostics = diagnostics or []


def _is_mapping(value) -> bool:
    return isinstance(value, dict)


def check_schema_version(payload: dict) -> None:
    """校验 schema_version 类型与支持集。不支持 -> AdapterError。"""
    version = payload.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise AdapterError(
            "schema_version must be an integer, got %r" % (version,), "bad_schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise AdapterError(
            "unsupported discovery schema_version %d (supported: %s); "
            "refusing to guess semantics of newer contract"
            % (version, list(SUPPORTED_SCHEMA_VERSIONS)),
            "unsupported_schema_version")


def check_root_structure(payload: dict) -> None:
    """转换所必需的显式结构检查（不是通用 Schema 校验，也不声称是）。"""
    required_keys = ("schema_version", "query", "role", "features", "asset_slots",
                     "optional_slots", "asset_candidates", "missing", "diagnostics")
    missing_keys = [k for k in required_keys if k not in payload]
    if missing_keys:
        raise AdapterError(
            "discovery payload missing required keys: %s" % missing_keys,
            "missing_root_keys")
    for key, expected in (("features", list), ("asset_slots", list),
                          ("optional_slots", list), ("asset_candidates", dict),
                          ("missing", list), ("diagnostics", list)):
        if not isinstance(payload[key], expected):
            raise AdapterError("payload key %r must be %s, got %s"
                               % (key, expected.__name__, type(payload[key]).__name__),
                               "bad_type")
    for slot, candidates in payload["asset_candidates"].items():
        if not isinstance(candidates, list):
            raise AdapterError("asset_candidates[%r] must be a list" % slot, "bad_type")
        for cand in candidates:
            if not _is_mapping(cand):
                raise AdapterError("asset_candidates[%r] item must be a mapping" % slot,
                                   "bad_type")
            for field in ("id", "role", "path"):
                if not isinstance(cand.get(field), str):
                    raise AdapterError(
                        "asset_candidates[%r] candidate missing/invalid field %r" % (slot, field),
                        "bad_candidate")
    for item in payload["missing"]:
        if not _is_mapping(item) or not isinstance(item.get("slot"), str):
            raise AdapterError("missing items must be mappings with a string 'slot'",
                               "bad_missing_item")


def classify_diagnostics(payload: dict) -> tuple[list[str], list[str]]:
    """(fatal_like, unknown) —— 由结构 + reason 共同判断，不只看名字。

    fatal_like: error-path 特征（role 为空串或候选键集不覆盖槽位）在
    Discovery 的 config_error / feature_index_missing 路径下出现；
    也包括 reason 属于已知的致命类且同时具备结构证据时。
    unknown: 不在已知枚举（9 个）内的 reason，不可静默处理。
    """
    fatal_like: list[str] = []
    unknown: list[str] = []
    known = NONFATAL_REASONS | {"config_error", "feature_index_missing", "index_missing"}
    slots = list(payload.get("asset_slots") or [])
    slot_set = set(slots)
    cands = payload.get("asset_candidates") or {}
    candidates_missing_keys = any(s not in cands for s in slots)
    empty_payload = (payload.get("role") == "" and not cands and not slots)

    for diag in payload.get("diagnostics") or []:
        reason = diag.get("reason") if isinstance(diag, dict) else None
        if not isinstance(reason, str):
            unknown.append(str(reason))
            continue
        if reason not in known:
            unknown.append(reason)
            continue
        if reason in ("config_error", "feature_index_missing"):
            fatal_like.append(reason)
        elif reason == "index_missing" and (empty_payload or candidates_missing_keys):
            fatal_like.append(reason)
    if empty_payload:
        fatal_like.append("error_path_structure")
    return fatal_like, unknown


def load_discovery_json(text: str) -> dict:
    """JSON 文本 -> dict。非法 JSON 或根对象非 mapping -> AdapterError。"""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AdapterError("input is not valid JSON: %s" % exc, "invalid_json") from exc
    if not _is_mapping(payload):
        raise AdapterError("input root must be a JSON object, got %s"
                           % type(payload).__name__, "root_not_object")
    return payload


def select_candidates(payload: dict,
                      selections: dict[str, str]) -> tuple[dict, list, list]:
    """应用显式候选选择，返回 (explicit_bindings, warnings, errors)。

    selections: {slot(资源槽位角色) -> candidate id}，由调用方显式提供；
    无任何隐式 fallback，不选 top1。

    返回的 explicit_bindings 形如 [{role, asset}]，即 bind_assets --binding
    文件的 `bindings:` 条目（显式绑定覆盖节）。不存在 candidate 的槽位不进
    输出，错误进 errors 供调用方诊断。
    """
    candidates_by_slot = payload.get("asset_candidates") or {}
    slot_set = set(candidates_by_slot.keys())
    # candidates 里可能含未在 asset_slots 列出的槽位（error-path 键集为 {} 但有
    # 空 dict）；selection 校验以 candidates 的键集为准。
    all_candidate_ids = {c["id"] for cands in (candidates_by_slot or {}).values()
                         for c in cands if isinstance(c, dict) and c.get("id")}

    bindings, warnings, errors = [], [], []
    for slot in sorted(selections):
        asset_id = str(selections[slot]).strip()
        if not slot or not asset_id:  # 空槽位或空 id 都视为格式错误
            errors.append({"slot": slot, "reason": "invalid_selection",
                           "message": "selection %r=%r has empty slot or asset id"
                                      % (slot, selections[slot])})
            continue
        if slot not in slot_set:
            errors.append({
                "slot": slot, "reason": "unknown_slot",
                "message": "slot %r is not a discovery slot (known: %s)"
                           % (slot, sorted(slot_set))})
            continue
        slot_candidates = candidates_by_slot.get(slot) or []
        if not slot_candidates:
            errors.append({
                "slot": slot, "reason": "no_candidates",
                "message": "required/selected slot %r has no candidates in discovery "
                           "payload; passing it to bind_assets would rely on index "
                           "inference, not explicit selection" % slot})
            continue
        matched = [c for c in slot_candidates
                   if isinstance(c, dict) and c.get("id") == asset_id]
        if not matched:
            if asset_id in all_candidate_ids:
                errors.append({
                    "slot": slot, "reason": "candidate_role_mismatch",
                    "message": "candidate %r exists but is not a candidate of slot %r; "
                               "refusing to cross-assign (candidate.role=%r, "
                               "slot.role=%r)" % (asset_id, slot,
                                                  matched[0].get("role")
                                                  if matched else asset_id, slot)})
            else:
                errors.append({
                    "slot": slot, "reason": "unknown_candidate",
                    "message": "candidate id %r not found in discovery payload for "
                               "slot %r" % (asset_id, slot)})
            continue
        # candidate.role 必须等于槽位名（Discovery 约定键=resource role）；
        # 不一致说明 payload 或选择有问题，拒绝静默接受。
        cand = matched[0]
        if cand.get("role") != slot:
            errors.append({
                "slot": slot, "reason": "candidate_role_mismatch",
                "message": "candidate %r has role %r but was assigned to slot %r; "
                           "entity role must never be used as a slot role"
                           % (asset_id, cand.get("role"), slot)})
            continue
        bindings.append({"role": slot, "asset": asset_id})
    return bindings, warnings, errors


def convert(payload: dict, selections: dict[str, str]) -> tuple[dict, list, list]:
    """纯转换入口（供 CLI 与测试复用）。

    返回 (binding_input, warnings, errors)。
    binding_input 是 bind_assets.py --binding FILE 可直接读取的 YAML dict：
        {bindings: [{role, asset}]}
    只含显式绑定覆盖节所需字段，绝不伪造 compatibility / resolved_from /
    confidence 等 bind_assets 运行时字段。
    """
    check_schema_version(payload)
    check_root_structure(payload)
    fatal_like, unknown = classify_diagnostics(payload)
    if fatal_like:
        raise SelectionError(
            "discovery payload is on an error path; no explicit candidates "
            "available to convert (fatal diagnostics: %s)" % fatal_like,
            "fatal_diagnostics", payload.get("diagnostics") or [])
    if unknown:
        raise SelectionError(
            "unknown diagnostics.reasion(s) present %r; refusing to silently "
            "assume the payload is healthy" % sorted(set(unknown)),
            "unknown_diagnostics", payload.get("diagnostics") or [])

    bindings, warnings, errors = select_candidates(payload, selections)

    if not bindings:
        raise SelectionError(
            "no explicit bindings could be derived from selections %r" % selections,
            "no_explicit_bindings", payload.get("diagnostics") or [])
    requested = payload.get("asset_slots") or []
    optional = payload.get("optional_slots") or []
    unselected_slots = [s for s in requested if s not in bindings and s not in optional]
    if unselected_slots:
        warnings.append({
            "type": "unselected_required_slot",
            "slots": unselected_slots,
            "message": "required slots without explicit selection are left to "
                       "bind_assets index inference (top1 is NOT auto-selected)",
        })
    if errors:
        raise SelectionError(
            "selection errors: %s" % errors,
            "selection_errors", payload.get("diagnostics") or [])
    return {"bindings": bindings}, warnings, errors


def _format_binding_yaml(binding_input: dict) -> str:
    return yaml.safe_dump(binding_input, sort_keys=False, allow_unicode=True, width=4096)


def _fail_io(operation: str, path: str, exc: OSError) -> int:
    """统一把可预期 I/O 错误转为可诊断 stderr + exit 2（不裸 traceback）。

    注：PermissionError 是 OSError 子类，但编译期/运行期解析 _fail_io
    的函数体不受 monkeypatch 顺序影响 —— 因为异常捕获在 _read_input_text 内。
    """
    print("FAIL: %s failed for %r: %s" % (operation, path, exc), file=sys.stderr)
    return 2


def _read_input_text(args) -> tuple[str, int]:
    """读取 Discovery JSON 文本（--input 文件或 stdin）。

    返回 (text, exit_code)；exit_code 非 0 时 text 为空 —— 预期 I/O 错误
    已转为可诊断 stderr（exit 2，与结构错误约定一致），不抛裸 traceback。
    """
    try:
        if args.input:
            return Path(args.input).read_text(encoding="utf-8"), 0
        return sys.stdin.read(), 0
    except OSError as exc:                       # 不存在/权限/磁盘等文件 I/O 错误
        return "", _fail_io("read input file", args.input or "<stdin>", exc)
    except UnicodeDecodeError as exc:            # 非 UTF-8 输入
        print("FAIL: input file %r is not valid UTF-8: %s" % (args.input, exc),
              file=sys.stderr)
        return "", 2


def _write_output(path: str, text: str) -> int:
    """原子写 --out：同目录临时文件 + os.replace（同卷原子，Windows/Linux 皆可）。

    失败时删除临时文件，不在目标路径留下看似完整实则截断的输出。
    返回 0 成功；2 预期 I/O 失败（可诊断 stderr）。
    """
    target = Path(path)
    parent = target.parent
    import tempfile as _tempfile
    try:
        if not parent.is_dir():
            print("FAIL: write output file failed for %r: parent directory does "
                  "not exist: %r" % (path, parent), file=sys.stderr)
            return 2
        fd, tmp_name = _tempfile.mkstemp(prefix=".d2b_", suffix=".tmp",
                                         dir=str(parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(text)
            os.replace(tmp_name, str(target))   # 同卷原子替换；失败不损已有文件
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return 0
    except OSError as exc:
        return _fail_io("write output file", path, exc)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a feature_discovery --json payload into an explicit "
                    "bind_assets --binding input file.")
    parser.add_argument("--input", default="", help="Path to a discovery JSON file")
    parser.add_argument("--select", action="append", default=[],
                        metavar="SLOT=ASSET_ID",
                        help="Explicit slot->candidate choice (repeatable). "
                             "No implicit top1 selection is ever performed.")
    parser.add_argument("-o", "--out", default="",
                        help="Write the explicit binding YAML to this path")
    parser.add_argument("--json", action="store_true",
                        help="Print a JSON summary (converted document, warnings, errors)")
    args = parser.parse_args(argv)

    text, io_exit = _read_input_text(args)
    if io_exit:
        return io_exit                           # I/O 失败：exit 2，可诊断 stderr

    try:
        payload = load_discovery_json(text)
    except AdapterError as exc:
        print("FAIL: %s (reason=%s)" % (exc, exc.reason), file=sys.stderr)
        return 2

    selections: dict[str, str] = {}
    bad_tokens: list[str] = []
    for token in args.select:
        if "=" not in token:
            bad_tokens.append(token)
            continue
        slot, asset_id = token.split("=", 1)
        slot = slot.strip()
        if not slot or not asset_id.strip():
            bad_tokens.append(token)
            continue
        if slot in selections and selections[slot] != asset_id:
            print("FAIL: conflicting selections for slot %r: %r vs %r"
                  % (slot, selections[slot], asset_id), file=sys.stderr)
            return 2
        selections[slot] = asset_id.strip()

    if bad_tokens:
        print("FAIL: --select requires SLOT=ASSET_ID, got: %s" % bad_tokens,
              file=sys.stderr)
        return 2

    try:
        binding_input, warnings, _errors = convert(payload, selections)
    except SelectionError as exc:
        if args.json:
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "converted": None,
                "reason": exc.reason,
                "diagnostics": exc.diagnostics,
                "warnings": [],
                "errors": [str(exc)],
            }, ensure_ascii=False, indent=2))
        print("FAIL: %s (reason=%s)" % (exc, exc.reason), file=sys.stderr)
        return 1
    except AdapterError as exc:
        print("FAIL: %s (reason=%s)" % (exc, exc.reason), file=sys.stderr)
        return 2

    if args.out:
        out_exit = _write_output(args.out, _format_binding_yaml(binding_input))
        if out_exit:                             # 写入失败：exit 2，可诊断 stderr；
            return out_exit                      # 不输出伪装成功的 partial 文件
        print("Binding input written: %s" % args.out, file=sys.stderr)
    if args.json:
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "converted": binding_input,
            "warnings": warnings,
            "errors": [],
        }, ensure_ascii=False, indent=2))
    else:
        print(_format_binding_yaml(binding_input), end="")
    for warning in warnings:
        print("WARNING: %s: %s" % (warning["type"], warning["message"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
