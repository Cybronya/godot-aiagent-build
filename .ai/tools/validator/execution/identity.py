#!/usr/bin/env python3
"""Execution Identity —— 全局唯一 Run ID + Execution ID（Phase 1.62）。

设计原则：
    1. Run ID 必须是全局唯一的 UUIDv4，不能用计数器或文件名推断。
    2. 同一次执行的 Replay、Artifact、Evidence 必须绑定同一个 Run ID。
    3. 重试必须生成新的 Run ID（不允许修改旧 JSON 伪造新执行）。
    4. Run ID 必须进入后续签名消息（Attestation）。
    5. Execution ID 用于标识同一次执行内的子阶段（可选）。
    6. 时间戳一律 UTC / ISO-8601 格式。

本模块**只负责生成与验证身份**，不采集环境指纹、不生成 Manifest、
不做 Attestation 签名。这些是 fingerprint.py / manifest.py / attestation.py
的职责。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

RUN_ID_VERSION = 1
EXECUTION_ID_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id() -> str:
    """生成全局唯一的 Run ID（UUIDv4 标准形式，小写，带连字符）。

    UUIDv4 具有 122 位随机性 —— 并发碰撞概率可忽略
    （2^122 次才可能出现一次碰撞，远高于实际运行量级）。
    """
    return str(uuid.uuid4()).lower()


def new_execution_id() -> str:
    """生成 Execution ID（UUIDv4）。与 Run ID 分离，一次 Run 可以派生多个
    Execution（例如分阶段执行不同 Feature）。"""
    return str(uuid.uuid4()).lower()


def is_valid_uuidv4(text: str) -> bool:
    """严格校验 UUIDv4 格式（8-4-4-4-12 小写十六进制）。

    拒绝对 UUIDv1/v2/v3/v5、全大写、无连字符版本，确保身份格式不可混淆。
    """
    if not isinstance(text, str):
        return False
    try:
        parsed = uuid.UUID(text)
    except (ValueError, AttributeError, TypeError):
        return False
    if parsed.version != 4:
        return False
    # 强制小写标准格式（str(uuid) 总是小写）
    return text == str(parsed)


def validate_run_id(run_id: str) -> list:
    """返回错误列表。空列表 = 通过。"""
    errors = []
    if not run_id:
        errors.append("run_id is empty")
        return errors
    if not is_valid_uuidv4(run_id):
        errors.append("run_id %r is not a valid UUIDv4" % run_id)
    # 防御：拒绝可疑前缀（攻击者可能尝试用 uuid1 的时间戳特性伪造）
    return errors


class ExecutionIdentity:
    """一次执行的完整身份记录（不可变值对象）。

    用法:
        ident = ExecutionIdentity.create(
            feature_id="health",
            behavior_id="damage",
            scenario_id="health_basic",
        )
        run_id = ident.run_id   # 全局唯一
        manifest = ident.to_dict()

    重试:
        parent = ident.run_id
        retry = ExecutionIdentity.create(feature_id="health",
                                          behavior_id="damage",
                                          parent_run_id=parent,
                                          requested_action="RETRY")
    """

    def __init__(self, run_id: str, execution_id: str,
                 *, feature_id: str = "", behavior_id: str = "",
                 scenario_id: str = "", contract_version: str = "",
                 requested_action: str = "NORMAL_EXECUTION",
                 execution_status: str = "PLANNED",
                 parent_run_id: str = "",
                 created_at: str = "", started_at: str = "",
                 completed_at: str = ""):
        if not is_valid_uuidv4(run_id):
            raise ValueError("run_id must be a valid UUIDv4, got %r" % run_id)
        if not is_valid_uuidv4(execution_id):
            raise ValueError("execution_id must be a valid UUIDv4, got %r" % execution_id)
        # parent_run_id 可选，但如果提供则必须也是 UUIDv4（不能指向一个伪造 ID）
        if parent_run_id and not is_valid_uuidv4(parent_run_id):
            raise ValueError("parent_run_id %r is not a valid UUIDv4" % parent_run_id)

        self.run_id = run_id
        self.execution_id = execution_id
        self.feature_id = str(feature_id or "")
        self.behavior_id = str(behavior_id or "")
        self.scenario_id = str(scenario_id or "")
        self.contract_version = str(contract_version or "")
        self.requested_action = str(requested_action or "NORMAL_EXECUTION")
        self.execution_status = str(execution_status or "PLANNED")
        self.parent_run_id = str(parent_run_id or "")
        self.created_at = str(created_at or _now_iso())
        self.started_at = str(started_at or "")
        self.completed_at = str(completed_at or "")

    @classmethod
    def create(cls, *, feature_id: str = "", behavior_id: str = "",
               scenario_id: str = "", contract_version: str = "",
               requested_action: str = "NORMAL_EXECUTION",
               parent_run_id: str = "") -> "ExecutionIdentity":
        """工厂：生成全新 Run + Execution，时间戳 UTC。"""
        return cls(
            run_id=new_run_id(),
            execution_id=new_execution_id(),
            feature_id=feature_id,
            behavior_id=behavior_id,
            scenario_id=scenario_id,
            contract_version=contract_version,
            requested_action=requested_action,
            execution_status="PLANNED",
            parent_run_id=parent_run_id,
        )

    def mark_started(self) -> "ExecutionIdentity":
        """标记执行开始（started_at = now_iso）。"""
        return ExecutionIdentity(
            run_id=self.run_id,
            execution_id=self.execution_id,
            feature_id=self.feature_id,
            behavior_id=self.behavior_id,
            scenario_id=self.scenario_id,
            contract_version=self.contract_version,
            requested_action=self.requested_action,
            execution_status="RUNNING",
            parent_run_id=self.parent_run_id,
            created_at=self.created_at,
            started_at=self.started_at or _now_iso(),
            completed_at=self.completed_at,
        )

    def mark_completed(self, status: str = "SUCCEEDED") -> "ExecutionIdentity":
        """标记执行完成（completed_at = now_iso）。"""
        valid = ("SUCCEEDED", "FAILED", "TIMEOUT", "CRASHED", "INCOMPLETE")
        if status not in valid:
            raise ValueError("execution_status must be one of %s, got %r"
                             % (valid, status))
        return ExecutionIdentity(
            run_id=self.run_id,
            execution_id=self.execution_id,
            feature_id=self.feature_id,
            behavior_id=self.behavior_id,
            scenario_id=self.scenario_id,
            contract_version=self.contract_version,
            requested_action=self.requested_action,
            execution_status=status,
            parent_run_id=self.parent_run_id,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=_now_iso(),
        )

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "execution_id": self.execution_id,
            "feature_id": self.feature_id,
            "behavior_id": self.behavior_id,
            "scenario_id": self.scenario_id,
            "contract_version": self.contract_version,
            "requested_action": self.requested_action,
            "execution_status": self.execution_status,
            "parent_run_id": self.parent_run_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionIdentity":
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        return cls(
            run_id=str(data.get("run_id") or ""),
            execution_id=str(data.get("execution_id") or ""),
            feature_id=str(data.get("feature_id") or ""),
            behavior_id=str(data.get("behavior_id") or ""),
            scenario_id=str(data.get("scenario_id") or ""),
            contract_version=str(data.get("contract_version") or ""),
            requested_action=str(data.get("requested_action") or ""),
            execution_status=str(data.get("execution_status") or ""),
            parent_run_id=str(data.get("parent_run_id") or ""),
            created_at=str(data.get("created_at") or ""),
            started_at=str(data.get("started_at") or ""),
            completed_at=str(data.get("completed_at") or ""),
        )

    def validate(self) -> list:
        """返回错误列表。空列表 = 通过。"""
        errors = validate_run_id(self.run_id)
        if not is_valid_uuidv4(self.execution_id):
            errors.append("execution_id is not a valid UUIDv4")
        if self.parent_run_id and not is_valid_uuidv4(self.parent_run_id):
            errors.append("parent_run_id is not a valid UUIDv4")
        valid_statuses = ("PLANNED", "RUNNING", "SUCCEEDED", "FAILED",
                          "TIMEOUT", "CRASHED", "INCOMPLETE")
        if self.execution_status and self.execution_status not in valid_statuses:
            errors.append("execution_status %r unknown (valid: %s)"
                          % (self.execution_status, valid_statuses))
        return errors

    def __eq__(self, other) -> bool:
        if not isinstance(other, ExecutionIdentity):
            return NotImplemented
        return self.run_id == other.run_id and self.execution_id == other.execution_id

    def __repr__(self) -> str:
        return (f"<ExecutionIdentity run_id={self.run_id[:12]}... "
                f"exec={self.execution_id[:12]}... feature={self.feature_id} "
                f"status={self.execution_status}>")
