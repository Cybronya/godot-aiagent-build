#!/usr/bin/env python3
"""e2e 产物所有权清单的针对性测试（Phase 1.33 复核补强）。

覆盖 e2e 入口的「启动期所有权扫描 + 结束清理」记账语义：

    E1  启动前不存在的产物 ⇒ 本运行可拥有 ⇒ 结束清理可删
    E2  启动前存在、但内容签名可验证的残留 ⇒ 启动期被回收 ⇒ 回收后路径为空 ⇒
        重新登记为可拥有 ⇒ 本轮重建的同名产物可被结束清理删除
        （**Phase 1.33 复核发现的记账缺陷**：回收的残留若不重新登记，
          结束清理会以「运行前就存在」为由拒绝删除，使一次成功的残留回收
          变成一次自我阻塞）
    E3  启动前存在、但签名不可验证的外来文件 ⇒ 启动期拒绝删除、不登记为可拥有 ⇒
        结束清理同样拒绝删除（fail-closed），文件存活
    E4  结束清理对可拥有产物必须重新校验签名：内容被改写 ⇒ 拒绝删除（文件存活）

全部在系统临时目录内运行：只替换 e2e 模块的「清单 / 签名判定 / 删除原语」三个接缝，
不触碰仓库中的任何真实资源。
用法: python .ai/tools/validator/tests/test_e2e_ownership.py
退出码: 0 = 全部通过；1 = 有失败。
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

_E2E_TEST = Path(__file__).resolve().parents[2] / "e2e" / "tests" / "test_end_to_end_generation.py"

_failures: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + ((" | " + detail) if detail else ""))


def _load_e2e_module():
    spec = importlib.util.spec_from_file_location("e2e_ownership_subject", _E2E_TEST)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load %s" % _E2E_TEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _python_delete(paths, godot):
    """替代 e2e 的 Godot 删除原语（测试内用纯 Python 删除，等价语义）。"""
    removed = 0
    failures: list[str] = []
    for target in paths:
        try:
            target.unlink()
            removed += 1
        except OSError as exc:
            failures.append("%s (%s)" % (target, exc))
    return removed, failures


def _reset(module) -> None:
    module._failures.clear()
    module._stale_removed.clear()
    module._stale_refused.clear()


def main() -> int:
    module = _load_e2e_module()
    work = Path(tempfile.mkdtemp(prefix="e2e_ownership_"))
    try:
        # ---- E1：启动前不存在 ⇒ 可拥有 ⇒ 结束清理删除 ----
        _reset(module)
        target = work / "E1.json"
        module._declared_targets = lambda: [target]
        module._ownership_reason = lambda path: (
            "" if "level_orchestration" in path.read_text(encoding="utf-8")
            else "not an e2e artifact")
        module._godot_delete = _python_delete
        ownable = module._ownership_scan_start(None)
        # 本轮创建该产物
        target.write_text('{"schema":{"id":"level_orchestration"}}', encoding="utf-8")
        ok("E1: an artifact that did not exist before the run is ownable",
           target in ownable, repr(sorted(str(p) for p in ownable)))
        removed, refused = module._ownership_cleanup(ownable, None)
        ok("E1: the end-of-run cleanup removes the artifact this run created",
           refused == 0 and not target.exists() and removed == 1,
           repr((removed, refused)))

        # ---- E2：启动前存在的可验证残留 ⇒ 被回收 ⇒ 重新登记为可拥有 ----
        _reset(module)
        stale = work / "E2.json"
        stale.write_text('{"schema":{"id":"level_orchestration"}}', encoding="utf-8")
        module._declared_targets = lambda: [stale]
        module._ownership_reason = lambda path: (
            "" if "level_orchestration" in path.read_text(encoding="utf-8")
            else "not an e2e artifact")
        ownable = module._ownership_scan_start(None)
        ok("E2: a signature-verified leftover is reclaimed by the start-up scan",
           not stale.exists() and module._rel(stale) in module._stale_removed,
           repr(module._stale_removed))
        ok("E2: the reclaimed path is re-registered as ownable (bookkeeping fix)",
           stale in ownable, repr(sorted(str(p) for p in ownable)))
        # 本轮重建同名产物
        stale.write_text('{"schema":{"id":"level_orchestration"}}', encoding="utf-8")
        removed, refused = module._ownership_cleanup(ownable, None)
        ok("E2: the rebuilt artifact is deleted by the end-of-run cleanup "
           "(a successful reclaim does not block the next run)",
           refused == 0 and not stale.exists(), repr((removed, refused)))

        # ---- E3：外来文件 ⇒ 拒绝删除、不登记为可拥有、结束清理仍拒绝 ----
        _reset(module)
        foreign = work / "E3.json"
        foreign.write_text("hand written by a human, not an e2e artifact", encoding="utf-8")
        module._declared_targets = lambda: [foreign]
        module._ownership_reason = lambda path: (
            "" if "level_orchestration" in path.read_text(encoding="utf-8") else "not an e2e artifact")
        ownable = module._ownership_scan_start(None)
        ok("E3: a foreign leftover is neither deleted nor registered as ownable",
           foreign.exists() and foreign not in ownable and bool(module._failures),
           repr(module._failures))
        removed, refused = module._ownership_cleanup(ownable, None)
        ok("E3: the end-of-run cleanup refuses to delete the foreign file (fail-closed)",
           refused == 1 and foreign.exists(), repr((removed, refused)))

        # ---- E4：可拥有产物在清理前被改写 ⇒ 拒绝删除 ----
        _reset(module)
        tampered = work / "E4.json"
        module._declared_targets = lambda: [tampered]
        module._ownership_reason = lambda path: (
            "" if "level_orchestration" in path.read_text(encoding="utf-8") else "not an e2e artifact")
        ownable = module._ownership_scan_start(None)
        tampered.write_text("rewritten by someone else", encoding="utf-8")
        removed, refused = module._ownership_cleanup(ownable, None)
        ok("E4: a rewritten ownable artifact is refused (signature re-check before delete)",
           refused == 1 and tampered.exists(), repr((removed, refused)))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if _failures:
        for failure in _failures:
            print("FAIL: " + failure)
        print("\nFAIL: e2e ownership bookkeeping checks failed")
        return 1
    print("\nPASS: e2e ownership bookkeeping (E1-E4)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
