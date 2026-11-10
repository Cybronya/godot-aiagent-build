#!/usr/bin/env python3
"""Phase 1.64：env_paths 单元测试（手写 ok() harness，与项目其它测试一致）。

只测解析规则本身：项目根、GODOT_BIN 优先级、项目配置、缺失时的环境错误。
不依赖本机是否装着 Godot（用临时假二进制）。
"""
from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(TOOLS, "validator"), os.path.join(TOOLS, "validator", "execution")]

from execution import env_paths  # noqa: E402

checks = 0
failures = 0
TMP_ROOTS: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        failures += 1
        print("FAIL: %s %s" % (name, detail))


def fake_project() -> str:
    """临时「项目」：project.godot + .ai/config/runtime-playtest.yaml。"""
    root = tempfile.mkdtemp(prefix="p164_env_")
    TMP_ROOTS.append(root)
    with open(os.path.join(root, "project.godot"), "w", encoding="utf-8") as handle:
        handle.write("config_version=5\n")
    return root


def make_binary(path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"fake-godot")
    return path


def write_config(root: str, value: str) -> None:
    path = os.path.join(root, ".ai", "config", "runtime-playtest.yaml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("runtime_playtest:\n  timeout: 30\n  godot_binary: %r\n" % value)


def main() -> int:
    # E1 项目根：从子目录向上找 project.godot（不靠层数）
    root = fake_project()
    nested = os.path.join(root, ".ai", "tools", "validator", "execution")
    os.makedirs(nested, exist_ok=True)
    probe = os.path.join(nested, "probe.py")
    open(probe, "w", encoding="utf-8").close()
    # Windows 临时目录形如 C:\Users\ADMINI~1\...；realpath 会展开短名，两边都要归一化
    ok("E1a: project_root finds project.godot by walking up",
       os.path.realpath(env_paths.project_root(probe)) == os.path.realpath(root),
       env_paths.project_root(probe))
    ok("E1b: project_root accepts a directory too",
       os.path.realpath(env_paths.project_root(nested)) == os.path.realpath(root))
    ok("E1c: real repo root is derived correctly",
       os.path.isfile(os.path.join(env_paths.project_root(), "project.godot")))

    # E2 GODOT_BIN 最高优先
    binary = make_binary(os.path.join(root, "tools", "godot_fake.exe"))
    sibling = make_binary(os.path.join(os.path.dirname(root), "Godot_v9_console.exe"))
    old_env = os.environ.get("GODOT_BIN")
    try:
        os.environ["GODOT_BIN"] = binary
        ok("E2a: GODOT_BIN wins over sibling discovery",
           env_paths.find_godot_binary(root) == os.path.realpath(binary),
           env_paths.find_godot_binary(root))
        # E3 显式指定但不可用：不回退（否则「我指定了」变成谎言）
        os.environ["GODOT_BIN"] = os.path.join(root, "missing", "godot.exe")
        ok("E3: invalid GODOT_BIN does not silently fall back",
           env_paths.find_godot_binary(root) == "")
        try:
            env_paths.require_godot(root)
            ok("E3b: require_godot raises on invalid GODOT_BIN", False)
        except SystemExit as exc:
            ok("E3b: require_godot raises on invalid GODOT_BIN",
               "ENVIRONMENT ERROR" in str(exc), str(exc))

        # E4 项目配置优先于相邻目录
        os.environ.pop("GODOT_BIN", None)
        write_config(root, binary)
        ok("E4: project config (runtime_playtest.godot_binary) is used",
           env_paths.find_godot_binary(root) == os.path.realpath(binary))
        ok("E4b: configured_godot returns the configured path",
           os.path.realpath(env_paths.configured_godot(root)) == os.path.realpath(binary))

        # E5 相对路径按项目根解析
        write_config(root, "tools/godot_fake.exe")
        ok("E5: relative configured path resolves against project root",
           env_paths.find_godot_binary(root) == os.path.realpath(binary))

        # E6 未配置时用相邻目录
        write_config(root, "")
        ok("E6: empty config falls back to sibling directory",
           env_paths.find_godot_binary(root) == os.path.realpath(sibling),
           env_paths.find_godot_binary(root))

        # E7 全都没有 → 环境错误（不是断言失败）
        os.remove(sibling)
        ok("E7: nothing found returns empty",
           env_paths.find_godot_binary(root) == "")
        try:
            env_paths.require_godot(root)
            ok("E7b: require_godot reports ENVIRONMENT ERROR", False)
        except SystemExit as exc:
            message = str(exc)
            ok("E7b: require_godot reports ENVIRONMENT ERROR",
               message.startswith("ENVIRONMENT ERROR")
               and "GODOT_BIN" in message and "runtime_playtest" in message, message)
    finally:
        if old_env is None:
            os.environ.pop("GODOT_BIN", None)
        else:
            os.environ["GODOT_BIN"] = old_env

    # E8 真实仓库：不设 GODOT_BIN 也能解析到相邻的 Godot（本机布局）
    real_root = env_paths.project_root()
    resolved = env_paths.find_godot_binary(real_root)
    ok("E8: real repo resolves a Godot binary without GODOT_BIN",
       bool(resolved) and os.path.isfile(resolved), str(resolved))
    ok("E8b: resolved binary lives next to the repo (not hardcoded)",
       os.path.realpath(os.path.dirname(resolved))
       == os.path.realpath(os.path.dirname(real_root)),
       resolved)

    # E9 两个 Runner 都使用统一解析（源码级回归：不再各自算根）
    for name in ("run_execution_e2e.py", "run_multi_feature_e2e.py"):
        path = os.path.join(os.path.dirname(HERE), "execution", name)
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        ok("E9: %s uses env_paths" % name,
           "env_paths.project_root(" in source and "require_godot" in source)
        ok("E9b: %s no longer computes its own root" % name,
           "_PROJECT_ROOT = os.path.dirname(_TOOLS)" not in source)

    import shutil
    for path in TMP_ROOTS:
        shutil.rmtree(path, ignore_errors=True)

    print()
    print("===== test_env_paths: %d checks, %d failures =====" % (checks, failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
