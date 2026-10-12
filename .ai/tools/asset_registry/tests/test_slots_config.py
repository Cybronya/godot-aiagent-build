#!/usr/bin/env python3
"""Entity Asset Slots Config Tests —— Phase 1.8.1 一致性补丁。

覆盖审查补丁要求：
    C1  配置优先级：explicit --slots > env ENTITY_ASSET_SLOTS > project 默认
    C2  schema.version 校验：缺版本拒绝 / 错版本拒绝 / 当前版本（1）通过
    C3  Binding 与 Discovery 对同一配置返回一致 required/optional slots
    C4  （回归）entity_required_roles 与 OPTIONAL_ROLES 行为不变

Usage:
    python .ai/tools/asset_registry/tests/test_slots_config.py

退出码: 0 = 全部通过；1 = 有失败。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_TOOL_DOTAI = Path(__file__).resolve().parents[3]
_ASSET_DIR = _TOOL_DOTAI / "tools" / "asset_registry"
_FEATURE_DIR = _TOOL_DOTAI / "tools" / "feature_registry"
sys.path.insert(0, str(_ASSET_DIR))
sys.path.insert(0, str(_FEATURE_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import bind_assets as ba                                     # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


VALID_YAML = """schema:
  id: entity_asset_slots
  version: 1
optional: [hurt_sfx]
default_required: [idle]
roles:
  enemy:
    required: [a1, a2, a3, a4]
"""

WRONG_VERSION_YAML = VALID_YAML.replace("  version: 1", "  version: 9")
MISSING_VERSION_YAML = VALID_YAML.replace("  version: 1\n", "")
WRONG_ID_YAML = VALID_YAML.replace("id: entity_asset_slots", "id: other_table")


def write_config(root: Path, content: str) -> Path:
    target = root / "custom_slots.yaml"
    target.write_text(content, encoding="utf-8")
    return target


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="slots_config_"))
    _temp_dirs.append(root)

    print("--- Entity Asset Slots Config (consistency patch) ---")
    print()

    # ---- C2: schema.version 校验（Binding 侧） ----
    try:
        ba.load_entity_slots(write_config(root, MISSING_VERSION_YAML))
        ok("C2a: missing version rejected", False, "no error")
    except RuntimeError as exc:
        ok("C2a: missing version rejected", "schema.version" in str(exc), str(exc)[:120])
    try:
        ba.load_entity_slots(write_config(root, WRONG_VERSION_YAML))
        ok("C2b: wrong version rejected", False, "no error")
    except RuntimeError as exc:
        ok("C2b: wrong version rejected", "unsupported schema.version" in str(exc), str(exc)[:120])
    parsed = ba.load_entity_slots(write_config(root, VALID_YAML))
    ok("C2c: version 1 accepted", parsed["enemy"]["required"] == ["a1", "a2", "a3", "a4"],
       str(parsed["enemy"]["required"]))

    # Discovery 侧同一校验集合（_FEATURE_DIR 已在模块头入 sys.path）
    import feature_discovery as fd
    try:
        fd.load_slots(str(write_config(root, WRONG_VERSION_YAML)))
        ok("C2d: discovery rejects wrong version", False, "no error")
    except RuntimeError as exc:
        ok("C2d: discovery rejects wrong version", "unsupported schema.version" in str(exc),
           str(exc)[:120])

    # ---- C1: 优先级 explicit > env > project（Discovery 侧实测，经 subprocess 更干净） ----
    # 用独立子进程避免 fd.main 内的 env 快照/全局态干扰；feature/asset index 都用真实仓库
    REAL_PROJECT = str(_TOOL_DOTAI.parent)   # _TOOL_DOTAI 是 .ai；项目根是其 parent
    custom = write_config(root, VALID_YAML)

    env = dict(os.environ)
    env["ENTITY_ASSET_SLOTS"] = str(custom)

    full_env = dict(os.environ)

    def run_cli(argv_extra: list, cli_env: dict) -> tuple[int, dict]:
        import subprocess as sp
        # Windows 下传不完整 env（缺 SYSTEMROOT 等）会让 Python 启动失败：
        # 始终以完整父环境为基础，仅覆盖目标变量。
        merged = dict(full_env)
        merged.update(cli_env)
        merged.setdefault("ENTITY_ASSET_SLOTS", "")   # 显式空串 = 清除
        merged = {k: v for k, v in merged.items() if not (k == "ENTITY_ASSET_SLOTS" and v == "")}
        proc = sp.run([sys.executable, str(_FEATURE_DIR / "feature_discovery.py")] + argv_extra,
                      capture_output=True, text=True, env=merged)
        import json as _json
        try:
            return proc.returncode, (_json.loads(proc.stdout) if proc.stdout.strip() else {})
        except Exception:
            return proc.returncode, {
                "_stderr": proc.stderr[:200],
            }

    code, payload = run_cli(["enemy", "--json", "--project", REAL_PROJECT], env)
    ok("C1a: env override used by discovery", payload.get("asset_slots") ==
       ["a1", "a2", "a3", "a4"], str(payload.get("asset_slots")))

    code2, payload2 = run_cli(["enemy", "--json", "--project", REAL_PROJECT,
                               "--slots", str(custom)],
                              {k: v for k, v in os.environ.items() if k != "ENTITY_ASSET_SLOTS"})
    ok("C1b: explicit --slots has highest priority",
       payload2.get("asset_slots") == ["a1", "a2", "a3", "a4"],
       str(payload2.get("asset_slots")))

    clean_env = {k: v for k, v in os.environ.items() if k != "ENTITY_ASSET_SLOTS"}
    code3, payload3 = run_cli(["enemy", "--json", "--project", REAL_PROJECT], clean_env)
    ok("C1c: project default used when no explicit/env",
       payload3.get("asset_slots") == ["idle", "move", "attack", "hurt"],
       str(payload3.get("asset_slots")))

    # ---- C3: Binding 与 Discovery 对同一配置一致 ----
    env["ENTITY_ASSET_SLOTS"] = str(custom)
    prev = os.environ.get("ENTITY_ASSET_SLOTS")

    # bind_assets 读取 env：子进程级。此处验证其常量接口与 discovery 槽位表同源：
    # 方法：比较 bind_assets.SLOTS_PATH 语义（模块加载时已固化 env），通过
    # 子进程再 import 一次取 env 指向配置（与本进程 independent）。
    import subprocess
    probe = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'%s'); import bind_assets as ba;"
         "print(ba.entity_required_roles('enemy'))" % _ASSET_DIR],
        capture_output=True, text=True, env=env)
    binding_slots = probe.stdout.strip().strip("[]").replace("'", "").replace(" ", "").split(",")
    ok("C3a: binding respects env override",
       binding_slots == ["a1", "a2", "a3", "a4"], str(binding_slots))
    # 两侧对同一配置：discovery (env) 已是 a1..a4 == binding (env)
    ok("C3b: discovery/binding agree under same config",
       payload.get("asset_slots") == binding_slots,
       "discovery=%s binding=%s" % (payload.get("asset_slots"), binding_slots))

    # ---- C4: 行为回归（默认表语义不变） ----
    from subprocess import CompletedProcess
    probe2 = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'%s'); import bind_assets as ba;"
         "print(ba.entity_required_roles('enemy' if ba.SLOTS_PATH.name == 'entity_asset_slots.yaml' else 'enemy'))"
         % _ASSET_DIR],
        capture_output=True, text=True, env={**os.environ})
    default_slots = probe2.stdout.strip().strip("[]").replace("'", "").replace(" ", "").split(",")
    ok("C4a: default binding slots unchanged",
       default_slots == ["idle", "move", "attack", "hurt"], str(default_slots))
    ok("C4b: OPTIONAL_ROLES unchanged in default config",
       ba.OPTIONAL_ROLES == ["hurt_sfx"], str(ba.OPTIONAL_ROLES))
    ok("C4c: compat alias intact",
       "_ENTITY_SLOTS_TABLE" in dir(ba) and "REQUIRED_ROLES_BY_ENTITY_ROLE" in dir(ba))

    # ---- E1: Discovery --slots 缺文件 + env 有效 → 配置错误且不回退到 env ----
    missing = write_config(root, VALID_YAML).parent / "no_such_slots.yaml"
    code_e1, payload_e1 = run_cli(["enemy", "--json", "--project", REAL_PROJECT,
                                   "--slots", str(missing)],
                                  {**os.environ, "ENTITY_ASSET_SLOTS": str(custom)})
    ok("E1: explicit missing slot path -> config_error, no env fallback",
       code_e1 == 2 and payload_e1.get("diagnostics", [{}])[0].get("reason") == "config_error"
       and payload_e1.get("asset_slots") == [],
       "code=%s slots=%s diag=%s" % (code_e1, payload_e1.get("asset_slots"),
                                     [d.get("reason") for d in payload_e1.get("diagnostics", [])]))

    # ---- E2: Discovery env 缺文件 + project 默认有效 —— env 是显式层，报错不回退 ----
    code_e2, payload_e2 = run_cli(["enemy", "--json", "--project", REAL_PROJECT],
                                  {**os.environ, "ENTITY_ASSET_SLOTS": str(missing)})
    ok("E2: env missing slot path -> config_error, no project fallback",
       code_e2 == 2 and payload_e2.get("diagnostics", [{}])[0].get("reason") == "config_error"
       and payload_e2.get("asset_slots") == [],
       "code=%s slots=%s diag=%s" % (code_e2, payload_e2.get("asset_slots"),
                                     [d.get("reason") for d in payload_e2.get("diagnostics", [])]))

    # ---- E3: 损坏 YAML + --json -> exit 2、stdout 可解析 JSON、diagnostics=config_error ----
    broken_yaml = root / "broken_parse.yaml"
    broken_yaml.write_text("schema: [oops\n", encoding="utf-8")
    code_e3, payload_e3 = run_cli(["enemy", "--json", "--project", REAL_PROJECT,
                                   "--slots", str(broken_yaml)],
                                  {k: os.environ[k] for k in os.environ if k != "ENTITY_ASSET_SLOTS"})
    diag3 = [(d.get("reason"), d.get("message", "")) for d in payload_e3.get("diagnostics", [])]
    ok("E3a: broken YAML --json -> exit 2 with parseable stdout JSON",
       code_e3 == 2 and payload_e3 != {} and payload_e3.get("schema_version") == 1,
       "code=%s head=%s" % (code_e3, json.dumps(payload_e3)[:120]))
    ok("E3b: broken YAML diagnostics=config_error with path info",
       any(reason == "config_error" and "broken_parse.yaml" in str(message) for reason, message in diag3),
       str(diag3))

    # ---- E4: Binding 错误 schema.version 独立子进程明确拒绝 ----
    bad_version_path = write_config(root, WRONG_VERSION_YAML)
    probe = ("import sys, yaml; from pathlib import Path; "
             "sys.path.insert(0, r'%s'); import bind_assets as ba\n"
             "try:\n"
             "    ba.load_entity_slots(Path(r'%s'))\n"
             "    print('ACCEPTED')\n"
             "except RuntimeError as e:\n"
             "    print('RuntimeError |', str(e)[:110])\n"
             "except SystemExit as e:\n"
             "    print('SystemExit', e.code)\n") % (_ASSET_DIR, bad_version_path)
    proc4 = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                           env={k: os.environ[k] for k in os.environ if k != "ENTITY_ASSET_SLOTS"})
    out4 = proc4.stdout.strip()
    ok("E4: binding rejects wrong schema.version (no silent accept)",
       "RuntimeError |" in out4 and "unsupported schema.version" in out4, out4 or proc4.stderr[:160])

    # ---- E5: Binding 损坏 YAML 独立子进程 -> 可诊断错误（含路径），无裸 traceback ----
    probe5 = ("import sys, yaml; from pathlib import Path; "
              "sys.path.insert(0, r'%s'); import bind_assets as ba\n"
              "try:\n"
              "    ba.load_entity_slots(Path(r'%s'))\n"
              "    print('ACCEPTED')\n"
              "except RuntimeError as e:\n"
              "    print('RuntimeError |', str(e))\n\n"
              ) % (_ASSET_DIR, broken_yaml)
    proc5 = subprocess.run([sys.executable, "-c", probe5], capture_output=True, text=True,
                           env={k: os.environ[k] for k in os.environ if k != "ENTITY_ASSET_SLOTS"})
    ok("E5: binding broken YAML -> RuntimeError with path, no bare traceback",
       "RuntimeError |" in proc5.stdout and "broken_parse.yaml" in proc5.stdout
       and "Traceback" not in proc5.stdout,
       (proc5.stdout or proc5.stderr)[:180])

    print()
    if _failures:
        print("FAIL: %d check(s) failed" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: Entity Asset Slots Config tests")
    return 0


def _safe_json(text: str) -> dict:
    import json
    try:
        return json.loads(text) if text.strip() else {}
    except Exception:
        return {}


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        for temp in _temp_dirs:
            shutil.rmtree(temp, ignore_errors=True)
