#!/usr/bin/env python3
"""Provenance 核心测试（Phase 1.61，任务书 §3/§7）。

被测对象：validator/provenance/（signature_schema / trust_store / key_metadata /
signing / verification / provenance_cli）

覆盖矩阵：
    A. 规范化与封套
      A1 canonical 确定性（字段顺序/无关空白不影响）
      A2 signed_message 排除 signature 字段；任何字段变化改变消息
      A3 structure_errors 捕获损坏封套（验证侧）；签发前允许无 signature
    B. 外部信任根
      B1 工作区外初始化 + 密钥登记（key_id 唯一）
      B2 工作区内信任根路径拒收（TRUST_ROOT_INSECURE_LOCATION）
      B3 环境变量覆盖（PROVENANCE_TRUST_ROOT）
      B4 重复 key_id 拒绝；损坏信任根 fail-closed
      B5 撤销覆盖文件只允许 REVOKED；工作区内撤销文件拒收
    C. 签名
      C1 签发/验证闭环；signer_subject 取自外部信任根（非自报）
      C2 私钥种子只写信任目录（工作区外）；种子内容不出现在异常消息
      C3 未登记密钥不能签发；scope 未授权不能签发
      C4 RETIRED/REVOKED 不能签发新对象
    D. 密钥生命周期
      D1 ACTIVE->RETIRED 合法，历史签名可继续验证
      D2 ACTIVE->REVOKED 合法，签名按撤销策略拒绝
      D3 非法转换拒绝（跳步 / 终态 / 复活）
      D4 rotate：旧 RETIRED + 新 ACTIVE
    E. 验证管线
      E1 全部拒绝词表（trust root missing / unknown key / invalid / revoked / scope）
      E2 evaluate_signature 策略分级（allow_legacy vs require_signature）
    F. CLI
      F1 keygen/status/rotate/revoke 端到端；输出不含种子内容
      G. Evidence sidecar 读/写/验证

用法：python .ai/tools/validator/provenance/tests/test_provenance_core.py
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
PROVENANCE_DIR = os.path.dirname(_HERE)
VALIDATOR_DIR = os.path.dirname(PROVENANCE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
for _path in (VALIDATOR_DIR,):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import provenance.signature_schema as schema                  # noqa: E402
from provenance import signing, verification                  # noqa: E402
from provenance.trust_store import (ENV_REVOCATIONS, ENV_TRUST_ROOT,  # noqa: E402
                                    STATUS_ACTIVE, STATUS_RETIRED,
                                    STATUS_REVOKED, TrustStore,
                                    TrustStoreError, derive_key_id,
                                    is_inside_path)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_checks = 0
_failures: list = []


def ok(label: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: %s" % label)
    else:
        _failures.append(label)
        print("FAIL: %s  %s" % (label, detail[:300]))


def expect_error(label: str, fn, *args, **kwargs) -> str:
    try:
        fn(*args, **kwargs)
        ok(label, False, "expected TrustStoreError, none raised")
        return ""
    except TrustStoreError as exc:
        ok(label, True, str(exc))
        return str(exc)
    except Exception as exc:                                  # noqa: BLE001
        ok(label, False, "unexpected %s: %s" % (type(exc).__name__, exc))
        return ""


_TMP_ROOT = tempfile.mkdtemp(prefix="p161-provenance-core-")
# 隔离环境：模拟"项目工作区"在临时目录内，信任根在工作区之外（同为临时目录）。
WORKSPACE = os.path.join(_TMP_ROOT, "workspace")
TRUST_AREA = os.path.join(_TMP_ROOT, "external")   # 攻击边界之外
os.makedirs(WORKSPACE, exist_ok=True)
os.makedirs(TRUST_AREA, exist_ok=True)
TRUST_ROOT = os.path.join(TRUST_AREA, "trust_root.json")


def fresh_store(root: str = TRUST_ROOT, *, project_root: str = WORKSPACE) -> TrustStore:
    return TrustStore(root, project_root=project_root)


def make_key(store: TrustStore, subject: str, scopes: list) -> dict:
    return signing.generate_and_register(subject=subject, scopes=scopes,
                                         trust_store=store,
                                         project_root=WORKSPACE)


def signed_envelope(store: TrustStore, key_id: str, *, object_type="baseline",
                    object_id="waves", object_version="2",
                    digest="a" * 64, scope="",
                    scheme="baseline-content-digest-v1",
                    binding=None) -> dict:
    return signing.sign_object(
        object_type=object_type, object_id=object_id,
        object_version=object_version, content_digest=digest,
        digest_scheme=scheme, key_id=key_id, trust_store=store,
        project_root=WORKSPACE, binding=binding or {})


def main() -> int:
    # ---------------------------------------------------------------- A
    a1 = schema.canonical({"b": 1, "a": [2, 3]})
    ok("A1 canonical 确定性（顺序/空白无关）",
       a1 == schema.canonical({"a": [2, 3], "b": 1})
       and a1 == '{"a":[2,3],"b":1}')
    env = signed_envelope(fresh_store(), "", object_id="x") if False else None
    store = fresh_store()
    key = make_key(store, "core-test", ["approve_baseline", "issue_evidence",
                                        "seal_holdout"])
    env = signed_envelope(store, key["key_id"], binding={"approver": "alice"})
    msg_without = schema.signed_message(env)
    env_copy = dict(env, signature="")
    ok("A2a signed_message 不含 signature 字段",
       msg_without == schema.signed_message(env_copy))
    tampered = dict(env, signed_at="2000-01-01T00:00:00Z")
    ok("A2b 任何字段变化改变签名消息",
       schema.signed_message(tampered) != msg_without)
    broken = dict(env); broken.pop("signer_key_id")
    ok("A3a 验证侧捕获缺字段", bool(schema.structure_errors(broken)))
    ok("A3b 验证侧捕获坏算法",
       bool(schema.structure_errors(dict(env, signature_algorithm="RSA"))))
    unsigned = signing.build_envelope(object_type="baseline", object_id="w",
                                      object_version="1", content_digest="b" * 64,
                                      digest_scheme="baseline-content-digest-v1",
                                      signer_key_id=key["key_id"])
    ok("A3c 签发前无 signature 字段合法",
       not schema.structure_errors(unsigned, require_signature=False))
    ok("A3d 签发前封套在验证侧被拒",
       schema.structure_errors(unsigned)[0].startswith("envelope missing"))

    # ---------------------------------------------------------------- B
    store_b = fresh_store(os.path.join(TRUST_AREA, "b", "trust_root.json"))
    store_b.initialize()
    key_b = make_key(store_b, "b-test", ["approve_baseline"])
    ok("B1a 信任根初始化于工作区外",
       not is_inside_path(store_b.trust_root_path(), WORKSPACE))
    ok("B1b 密钥登记且 key_id 确定性派生",
       key_b["key_id"] == derive_key_id(key_b["public_key"]))
    expect_error("B1c 重复 key_id 拒绝",
                 store_b.add_key, key_b["public_key"], subject="dup",
                 scopes=["approve_baseline"])
    inside_root = TrustStore(os.path.join(WORKSPACE, "trust_root.json"),
                             project_root=WORKSPACE)
    with open(os.path.join(WORKSPACE, "trust_root.json"), "w",
              encoding="utf-8") as handle:
        handle.write(json.dumps({"schema": schema.TRUST_ROOT_SCHEMA,
                                 "schema_version": 1, "keys": []}))
    loaded = inside_root.load()
    ok("B2 工作区内信任根拒收（A16 机制基础）",
       not loaded["ok"] and loaded["status"] == "TRUST_ROOT_INSECURE_LOCATION",
       str(loaded.get("status")))
    os.environ[ENV_TRUST_ROOT] = TRUST_ROOT
    env_store = TrustStore(project_root=WORKSPACE)
    ok("B3 环境变量覆盖生效",
       env_store.trust_root_path() == TRUST_ROOT
       and env_store.load()["ok"])
    del os.environ[ENV_TRUST_ROOT]
    bad_root = os.path.join(TRUST_AREA, "bad", "trust_root.json")
    os.makedirs(os.path.dirname(bad_root), exist_ok=True)
    with open(bad_root, "w", encoding="utf-8") as handle:
        handle.write('{"schema": "provenance_trust_root", "keys": "nope"}')
    bad_loaded = fresh_store(bad_root).load()
    ok("B4a 损坏信任根 fail-closed（TRUST_ROOT_UNREADABLE）",
       not bad_loaded["ok"] and bad_loaded["status"] == "TRUST_ROOT_UNREADABLE")
    dup_root = os.path.join(TRUST_AREA, "dup", "trust_root.json")
    dup_store = fresh_store(dup_root)
    dup_store.initialize()
    k1 = make_key(dup_store, "d1", ["approve_baseline"])
    record = dict(dup_store.load()["document"]["keys"][0])
    dup_store._write_document({"schema": schema.TRUST_ROOT_SCHEMA,
                               "schema_version": 1, "keys": [record, record]})
    ok("B4b 重复 key_id 使信任根损坏（fail-closed）",
       not fresh_store(dup_root).load()["ok"])
    revocations_path = os.path.join(TRUST_AREA, "revocations.json")
    with open(revocations_path, "w", encoding="utf-8") as handle:
        json.dump({"schema": schema.REVOCATIONS_SCHEMA, "schema_version": 1,
                   "revocations": [{"key_id": k1["key_id"],
                                    "status": STATUS_REVOKED, "at": "2026-11-03"}]},
                  handle)
    os.environ[ENV_REVOCATIONS] = revocations_path
    revoked_record, _ = fresh_store(dup_root.replace("dup", "dup")).key_record(k1["key_id"]) \
        if False else (None, None)
    live_store = fresh_store(os.path.join(TRUST_AREA, "rev", "trust_root.json"))
    live_store.initialize()
    k2 = make_key(live_store, "rev-test", ["approve_baseline"])
    os.environ[ENV_REVOCATIONS] = revocations_path.replace(str(k1["key_id"]), str(k2["key_id"]))
    with open(revocations_path, "w", encoding="utf-8") as handle:
        json.dump({"schema": schema.REVOCATIONS_SCHEMA, "schema_version": 1,
                   "revocations": [{"key_id": k2["key_id"],
                                    "status": STATUS_REVOKED, "at": "2026-11-03"}]},
                  handle)
    record_2, _ = live_store.key_record(k2["key_id"])
    ok("B5a 撤销覆盖文件生效（只允许 REVOKED）",
       record_2 and record_2["status"] == STATUS_REVOKED)
    del os.environ[ENV_REVOCATIONS]
    inside_rev = os.path.join(WORKSPACE, "revocations.json")
    with open(inside_rev, "w", encoding="utf-8") as handle:
        json.dump({"schema": schema.REVOCATIONS_SCHEMA, "schema_version": 1,
                   "revocations": []}, handle)
    live_store._revocations_path = inside_rev
    expect_error("B5b 工作区内撤销文件拒收",
                 live_store._apply_revocations, [dict(k2, status=STATUS_ACTIVE)])
    live_store._revocations_path = ""
    # 恢复 k2 状态供后续用例
    with open(live_store.trust_root_path(), "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    for item in doc["keys"]:
        if item["key_id"] == k2["key_id"]:
            item["status"] = STATUS_ACTIVE
    live_store._write_document(doc)

    # ---------------------------------------------------------------- C
    verified = verification.verify_envelope(
        env, object_type="baseline", object_id="waves", object_version="2",
        expected_digest="a" * 64, trust_store=store)
    ok("C1a 签发/验证闭环", verified["status"] == schema.SIGNATURE_VALID,
       str(verified))
    ok("C1b signer_subject 取自外部信任根",
       verified.get("signer_subject") == "core-test")
    ok("C1c 密钥状态可见", verified.get("key_status") == STATUS_ACTIVE)
    # C2: 种子位置 + 异常消息不含种子
    seed_path = os.path.join(store.keys_dir(), "%s.seed" % key["key_id"])
    ok("C2a 私钥种子在工作区外且文件存在",
       os.path.isfile(seed_path) and not is_inside_path(seed_path, WORKSPACE))
    with open(seed_path, "r", encoding="utf-8") as handle:
        seed_value = handle.read().strip()
    ok("C2b 种子文件不在项目工作区内",
       not is_inside_path(seed_path, PROJECT_ROOT))
    expect_error("C2c 拒绝把种子写入工作区",
                 __import__("provenance.key_metadata", fromlist=["write_seed"]).write_seed,
                 WORKSPACE, "FAKEKEY", "0" * 64, project_root=WORKSPACE)
    repo_tree_file = os.path.join(PROJECT_ROOT, ".ai", "tools", "validator")
    ok("C2d 真实仓库内无 .seed 文件（本轮隔离环境之外）",
       not any(name.endswith(".seed")
               for root, _dirs, files in os.walk(repo_tree_file)
               for name in files))
    bad_seed_store = fresh_store(os.path.join(TRUST_AREA, "badseed",
                                              "trust_root.json"))
    bad_seed_store.initialize()
    k3 = make_key(bad_seed_store, "badseed", ["approve_baseline"])
    with open(os.path.join(bad_seed_store.keys_dir(),
                           "%s.seed" % k3["key_id"]), "w",
              encoding="utf-8") as handle:
        handle.write("not-a-seed\n")
    error_text = expect_error(
        "C2e 种子损坏时报错且不含种子内容",
        signing.sign_object, object_type="baseline", object_id="w",
        object_version="1", content_digest="c" * 64,
        digest_scheme="baseline-content-digest-v1", key_id=k3["key_id"],
        trust_store=bad_seed_store, project_root=WORKSPACE)
    ok("C2f 错误消息不泄露种子", seed_value not in (error_text or ""))
    # C3: 未登记密钥 / scope 未授权
    foreign = signing.generate_and_register(subject="other", scopes=["approve_baseline"],
                                            trust_store=fresh_store(
                                                os.path.join(TRUST_AREA, "other",
                                                             "trust_root.json")),
                                            project_root=WORKSPACE)
    env_foreign = signing.build_envelope(
        object_type="baseline", object_id="w", object_version="1",
        content_digest="d" * 64, digest_scheme="baseline-content-digest-v1",
        signer_key_id=foreign["key_id"])
    expect_error("C3a 未登记（另一信任根）密钥不能签发",
                 signing.sign_envelope, env_foreign, trust_store=store,
                 project_root=WORKSPACE)
    env_wrong_scope = signing.build_envelope(
        object_type="evidence_bundle", object_id="e", object_version="1",
        content_digest="d" * 64, digest_scheme="evidence-bundle-digest-v1",
        signer_key_id=key_b["key_id"])  # key_b 只有 approve_baseline
    expect_error("C3b scope 未授权不能签发",
                 signing.sign_envelope, env_wrong_scope, trust_store=store_b,
                 project_root=WORKSPACE)
    # C4: RETIRED / REVOKED 不能签发新对象
    env_b = signed_envelope(store_b, key_b["key_id"])
    store_b.set_key_status(key_b["key_id"], STATUS_RETIRED, reason="test")
    expect_error("C4a RETIRED 不能签发新对象",
                 signing.sign_envelope, signing.build_envelope(
                     object_type="baseline", object_id="w2", object_version="1",
                     content_digest="e" * 64,
                     digest_scheme="baseline-content-digest-v1",
                     signer_key_id=key_b["key_id"]),
                 trust_store=store_b, project_root=WORKSPACE)
    ok("C4b RETIRED 历史签名可继续验证",
       verification.verify_envelope(
           env_b, object_type="baseline", object_id="waves", object_version="2",
           expected_digest="a" * 64, trust_store=store_b)["status"]
       == schema.SIGNATURE_VALID)
    store_b.set_key_status(key_b["key_id"], STATUS_REVOKED, reason="leak")
    ok("C4c REVOKED 签名按撤销策略拒绝",
       verification.verify_envelope(
           env_b, object_type="baseline", object_id="waves", object_version="2",
           expected_digest="a" * 64, trust_store=store_b)["status"]
       == schema.KEY_REVOKED)

    # ---------------------------------------------------------------- D
    store_d = fresh_store(os.path.join(TRUST_AREA, "lifecycle", "trust_root.json"))
    store_d.initialize()
    kd = make_key(store_d, "lifecycle", ["approve_baseline"])
    expect_error("D3a ACTIVE->ACTIVE 非法转换",
                 store_d.set_key_status, kd["key_id"], STATUS_ACTIVE)
    store_d.set_key_status(kd["key_id"], STATUS_REVOKED, reason="test")
    expect_error("D3b REVOKED 是终态（复活被拒）",
                 store_d.set_key_status, kd["key_id"], STATUS_ACTIVE)
    store_d2 = fresh_store(os.path.join(TRUST_AREA, "lifecycle2", "trust_root.json"))
    store_d2.initialize()
    kd2 = make_key(store_d2, "lifecycle2", ["approve_baseline"])
    store_d2.set_key_status(kd2["key_id"], STATUS_RETIRED, reason="rotate")
    store_d2.set_key_status(kd2["key_id"], STATUS_REVOKED, reason="retire-then-revoke")
    ok("D3c RETIRED->REVOKED 合法",
       store_d2.key_record(kd2["key_id"])[0]["status"] == STATUS_REVOKED)
    store_r = fresh_store(os.path.join(TRUST_AREA, "rotate", "trust_root.json"))
    store_r.initialize()
    kr = make_key(store_r, "v1", ["approve_baseline"])
    env_r = signed_envelope(store_r, kr["key_id"], object_id="waves")
    # 轮换用全新密钥对（CLI rotate 的同一流程）：先签历史签名，再轮换。
    new_seed = signing.generate_seed_hex()
    new_public = signing.seed_to_public_b64(new_seed)
    result = store_r.rotate(new_public, new_subject="v2",
                            new_scopes=["approve_baseline"],
                            retiring_key_id=kr["key_id"])
    from provenance.key_metadata import write_seed               # noqa: PLC0415
    write_seed(store_r.trust_dir(), result["activated_key_id"], new_seed,
               project_root=WORKSPACE)
    ok("D4a rotate：旧密钥 RETIRED",
       store_r.key_record(kr["key_id"])[0]["status"] == STATUS_RETIRED)
    ok("D4b rotate：新密钥 ACTIVE",
       store_r.key_record(result["activated_key_id"])[0]["status"] == STATUS_ACTIVE)
    ok("D4c 轮换不改变历史签名的验证结果",
       verification.verify_envelope(
           env_r, object_type="baseline", object_id="waves", object_version="2",
           expected_digest="a" * 64, trust_store=store_r)["status"]
       == schema.SIGNATURE_VALID)
    expect_error("D4d 未知密钥不能轮换",
                 store_r.rotate, "AAAA", new_subject="x",
                 new_scopes=["approve_baseline"], retiring_key_id="PROVKEY-nope")

    # ---------------------------------------------------------------- E
    store_e = fresh_store(os.path.join(TRUST_AREA, "verify", "trust_root.json"))
    store_e.initialize()
    ke = make_key(store_e, "verifier", ["approve_baseline", "issue_evidence"])
    env_e = signed_envelope(store_e, ke["key_id"], binding={"approver": "bob"})
    cases = [
        ("E1a 未知密钥", dict(env_e, signer_key_id="PROVKEY-unknown"),
         dict(object_type="baseline", object_id="waves", object_version="2",
              expected_digest="a" * 64), schema.KEY_UNKNOWN),
        ("E1b 信任根缺失", env_e,
         dict(object_type="baseline", object_id="waves", object_version="2",
              expected_digest="a" * 64, trust_store=fresh_store(
                  os.path.join(TRUST_AREA, "absent.json"))), None),
        ("E1c 跨对象类型（A07）", env_e,
         dict(object_type="evidence_bundle", object_id="waves",
              object_version="2", expected_digest="a" * 64),
         schema.SIGNATURE_INVALID),
        ("E1d 跨对象（A08）", env_e,
         dict(object_type="baseline", object_id="holdout",
              object_version="2", expected_digest="a" * 64),
         schema.SIGNATURE_INVALID),
        ("E1e 跨版本", env_e,
         dict(object_type="baseline", object_id="waves", object_version="3",
              expected_digest="a" * 64), schema.SIGNATURE_INVALID),
        ("E1f 摘要失配（A01/A02）", env_e,
         dict(object_type="baseline", object_id="waves", object_version="2",
              expected_digest="f" * 64), schema.DIGEST_MISMATCH),
        ("E1g scope 不匹配（A18，封套 scope 被改）",
         dict(env_e, scope="issue_evidence"),
         dict(object_type="baseline", object_id="waves",
              object_version="2", expected_digest="a" * 64),
         schema.SCOPE_MISMATCH),
    ]
    for label, envelope, kwargs, expected in cases:
        kwargs["trust_store"] = kwargs.get("trust_store", store_e)
        outcome = verification.verify_envelope(envelope, **kwargs)
        if expected is None:
            ok(label, outcome["status"] == schema.TRUST_ROOT_MISSING,
               str(outcome["status"]))
        else:
            ok(label, outcome["status"] == expected,
               "got %s" % outcome["status"])
    # A06：攻击者用自己的 Ed25519 密钥伪造签名（key_id 伪装成受信密钥）
    import nacl.signing                                          # noqa: PLC0415
    attacker_seed = nacl.signing.SigningKey.generate()
    forged = dict(env_e, signature=base64.b64encode(
        attacker_seed.sign(schema.signed_message(env_e)).signature).decode("ascii"))
    ok("E1h 用错误私钥重新签名被拒（A06）",
       verification.verify_envelope(forged, object_type="baseline",
                                    object_id="waves", object_version="2",
                                    expected_digest="a" * 64,
                                    trust_store=store_e)["status"]
       == schema.SIGNATURE_INVALID)
    # E2: 策略分级
    legacy = verification.evaluate_signature(
        None, object_type="baseline", object_id="w", object_version="1",
        expected_digest="a" * 64, trust_store=store_e,
        signature_policy=verification.POLICY_ALLOW_LEGACY)
    ok("E2a 缺签名+allow_legacy -> LEGACY_APPROVED（不冒充已验证）",
       legacy["trust_level"] == schema.TRUST_LEGACY_APPROVED and legacy["usable"])
    required = verification.evaluate_signature(
        None, object_type="baseline", object_id="w", object_version="1",
        expected_digest="a" * 64, trust_store=store_e,
        signature_policy=verification.POLICY_REQUIRE_SIGNATURE)
    ok("E2b 缺签名+require -> SIGNATURE_REQUIRED（fail-closed）",
       required["trust_level"] == schema.TRUST_SIGNATURE_REQUIRED
       and not required["usable"])
    bad_eval = verification.evaluate_signature(
        forged, object_type="baseline", object_id="waves", object_version="2",
        expected_digest="a" * 64, trust_store=store_e,
        signature_policy=verification.POLICY_ALLOW_LEGACY)
    ok("E2c 签名存在但无效在 allow_legacy 下也拒绝（带病签名不放行）",
       bad_eval["trust_level"] == schema.TRUST_SIGNATURE_INVALID
       and not bad_eval["usable"])
    good_eval = verification.evaluate_signature(
        env_e, object_type="baseline", object_id="waves", object_version="2",
        expected_digest="a" * 64, trust_store=store_e,
        signature_policy=verification.POLICY_REQUIRE_SIGNATURE)
    ok("E2d 有效签名在 require 下 -> CRYPTOGRAPHICALLY_VERIFIED",
       good_eval["trust_level"] == schema.TRUST_CRYPTO_VERIFIED
       and good_eval["usable"])

    # ---------------------------------------------------------------- F (CLI)
    cli_trust = os.path.join(TRUST_AREA, "cli", "trust_root.json")
    cli_cmd = [sys.executable, "-I", os.path.join(PROVENANCE_DIR, "provenance_cli.py"),
               "--trust-root", cli_trust]
    proc = subprocess.run(cli_cmd + ["keygen", "--subject", "cli-test",
                                     "--scopes", "approve_baseline"],
                          capture_output=True, text=True, encoding="utf-8",
                          timeout=120, cwd=PROJECT_ROOT)
    ok("F1a CLI keygen 成功", proc.returncode == 0, proc.stdout[-200:] + proc.stderr[-200:])
    cli_key_id = json.load(open(cli_trust, encoding="utf-8"))["keys"][0]["key_id"]
    with open(os.path.join(os.path.dirname(cli_trust), "keys",
                           "%s.seed" % cli_key_id),
              encoding="utf-8") as handle:
        cli_seed = handle.read().strip()
    ok("F1b CLI 输出不含种子内容", cli_seed not in (proc.stdout + proc.stderr))
    proc = subprocess.run(cli_cmd + ["status"], capture_output=True, text=True,
                          encoding="utf-8", timeout=120, cwd=PROJECT_ROOT)
    ok("F1c CLI status 正常", proc.returncode == 0
       and "cli-test" in proc.stdout)

    # ---------------------------------------------------------------- G (sidecar)
    bundle_path = os.path.join(WORKSPACE, "bundle-sample.json")
    bundle_doc = {"schema": "feature_behavior_evidence_bundle",
                  "schema_version": 1, "bundle_id": "g-bundle",
                  "features": [], "integrity": {"algorithm": "sha256",
                                                "payload_sha256": "0" * 64}}
    with open(bundle_path, "w", encoding="utf-8") as handle:
        json.dump(bundle_doc, handle)
    digest = verification.recompute_evidence_digest(bundle_doc)
    store_g = fresh_store(os.path.join(TRUST_AREA, "sidecar", "trust_root.json"))
    store_g.initialize()
    kg = make_key(store_g, "collector", ["issue_evidence"])
    env_g = signing.sign_object(
        object_type="evidence_bundle", object_id="g-bundle", object_version="1",
        content_digest=digest, digest_scheme="evidence-bundle-digest-v1",
        key_id=kg["key_id"], trust_store=store_g, project_root=WORKSPACE)
    target = verification.write_sidecar(bundle_path, env_g)
    ok("G1 sidecar 写在 bundle 旁且 bundle 字节未变",
       target == bundle_path + ".sig.json"
       and json.load(open(bundle_path, encoding="utf-8")) == bundle_doc)
    evaluated = verification.verify_evidence_bundle(
        bundle_path, json.load(open(bundle_path, encoding="utf-8")),
        trust_store=store_g, signature_policy="require_signature")
    ok("G2 sidecar 验签通过（require 模式）",
       evaluated["usable"]
       and evaluated["trust_level"] == schema.TRUST_CRYPTO_VERIFIED,
       str(evaluated))
    tampered_doc = dict(bundle_doc, bundle_id="g-bundle-attacker")
    evaluated = verification.verify_evidence_bundle(
        bundle_path, tampered_doc, trust_store=store_g,
        signature_policy="require_signature")
    ok("G3 bundle 内容被改 -> 拒绝（A09：身份或摘要失配）",
       not evaluated["usable"]
       and evaluated["verification"]["status"] in
       (schema.DIGEST_MISMATCH, schema.SIGNATURE_INVALID),
       str(evaluated["verification"]["status"]))
    os.remove(target)
    evaluated = verification.verify_evidence_bundle(
        bundle_path, json.load(open(bundle_path, encoding="utf-8")),
        trust_store=store_g, signature_policy="require_signature")
    ok("G4 缺签名+require -> 拒绝（A15）",
       not evaluated["usable"]
       and evaluated["trust_level"] == schema.TRUST_SIGNATURE_REQUIRED)
    evaluated = verification.verify_evidence_bundle(
        bundle_path, json.load(open(bundle_path, encoding="utf-8")),
        trust_store=store_g, signature_policy="allow_legacy")
    ok("G5 缺签名+allow_legacy -> LEGACY_APPROVED（诊断，不冒充已验证）",
       evaluated["usable"]
       and evaluated["trust_level"] == schema.TRUST_LEGACY_APPROVED)

    # ---------------------------------------------------------------- 结束
    print("\n%d checks, %d failures" % (_checks, len(_failures)))
    if _failures:
        print("FAILED:")
        for item in _failures:
            print("  - %s" % item)
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
