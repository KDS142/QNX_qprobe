"""Data models for qnx-inspector telemetry and analysis."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ThreadRecord:
    """Represents an active QNX thread reported by pidin."""
    pid: int
    tid: int
    name: str
    priority: int
    policy: str  # 'FIFO', 'RR', 'OTHER'
    priority_raw: str  # e.g., '10r', '25f', '255i'
    state: str  # 'RUNNING', 'READY', 'REPLY', 'RECEIVE', 'MUTEX', 'NANOSLEEP', etc.
    blocked_on: str = ""  # target PID or channel identifier (e.g., '12290', '12290-1')

    @property
    def is_blocked(self) -> bool:
        return self.state in {"REPLY", "RECEIVE", "MUTEX", "CONDVAR", "SEM"}


@dataclass
class InversionAlert:
    """Represents a detected real-time priority inversion condition."""
    client_pid: int
    client_tid: int
    client_name: str
    client_priority: int
    server_pid: int
    server_name: str
    server_priority: int
    severity: str = "CRITICAL"
    chain: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def summary(self) -> str:
        return (
            f"[CRITICAL] Priority Inversion: High-priority client '{self.client_name}' "
            f"(PID {self.client_pid}.{self.client_tid}, prio {self.client_priority}) blocked on "
            f"lower-priority server '{self.server_name}' (PID {self.server_pid}, prio {self.server_priority})"
        )


@dataclass
class DevMount:
    """Represents a /dev device node and its owning user-space Resource Manager."""
    device_path: str
    server_pid: int
    server_name: str
    mount_type: str = "MP"  # MP = Mount Point or standard open path


@dataclass
class LogEntry:
    """Represents a structured slog2 log entry."""
    timestamp: str
    buffer: str  # e.g., 'io-sock.1042' or 'procnto.1'
    severity: str  # 'SLOG2_INFO', 'SLOG2_WARNING', 'SLOG2_ERROR', 'SLOG2_CRITICAL'
    message: str
    raw: str = ""


@dataclass
class TranslationResult:
    """Result of translating a Linux command into a QNX equivalent."""
    linux_cmd: str
    qnx_cmd: str
    explanation: str
    is_dangerous: bool = False
    requires_confirm: bool = False
    warning: str = ""


@dataclass
class SystemInfo:
    """Hardware and Kernel information from pidin info."""
    os_version: str = "QNX 8.0.0"
    arch: str = "x86_64"
    cores: int = 4
    total_ram_mb: int = 4096
    free_ram_mb: int = 3120
    boot_time: str = ""
    host_target: str = "localhost:2222"
