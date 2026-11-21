"""Telemetry parsing logic for QNX 8.0 commands."""
from __future__ import annotations

import re
from typing import Optional, Set
from core.models import ThreadRecord, DevMount, LogEntry, SystemInfo


def parse_pidin_threads(raw_output: str) -> list[ThreadRecord]:
    """
    Parses output of: pidin -F "%a %b %N %p %J %B"
    Columns: PID, TID, Name, Priority, State, Blocked-On.
    """
    threads: list[ThreadRecord] = []
    lines = raw_output.strip().splitlines()

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        # Skip header lines
        if re.match(r"^(pid|PID)\s+", line_clean, re.IGNORECASE):
            continue

        parts = line_clean.split()
        if len(parts) < 5:
            continue

        try:
            pid = int(parts[0])
            tid = int(parts[1])
            name = parts[2]
            prio_raw = parts[3]
            state = parts[4].upper()
            blocked_on = parts[5] if len(parts) >= 6 else ""

            # Extract numeric priority and policy
            prio_match = re.search(r"\d+", prio_raw)
            priority = int(prio_match.group()) if prio_match else 10

            policy = "OTHER"
            if "f" in prio_raw.lower():
                policy = "FIFO"
            elif "r" in prio_raw.lower():
                policy = "RR"

            threads.append(
                ThreadRecord(
                    pid=pid,
                    tid=tid,
                    name=name,
                    priority=priority,
                    policy=policy,
                    priority_raw=prio_raw,
                    state=state,
                    blocked_on=blocked_on,
                )
            )
        except (ValueError, IndexError):
            continue

    return threads


def parse_pidin_fds(raw_output: str) -> list[DevMount]:
    """
    Scans pidin fds lines for mountpoint markers (MP) and paths starting with /dev/,
    mapping each /dev/<node> to the owning user-space server PID and name.
    """
    mounts: list[DevMount] = []
    seen_nodes: Set[str] = set()

    lines = raw_output.strip().splitlines()
    for line in lines:
        line_clean = line.strip()
        if not line_clean or re.match(r"^(pid|PID)\s+", line_clean, re.IGNORECASE):
            continue

        # Look for /dev/ paths
        dev_match = re.search(r"(/dev/\S+)", line_clean)
        if not dev_match:
            continue

        dev_path = dev_match.group(1).rstrip(",;")
        parts = line_clean.split()
        if len(parts) < 2:
            continue

        try:
            pid = int(parts[0])
            name = parts[1]
            mount_type = "MP" if " MP " in f" {line_clean} " or "MP" in parts else "FD"

            # Avoid duplicates of the same device path under same pid
            node_key = f"{dev_path}:{pid}"
            if node_key not in seen_nodes:
                seen_nodes.add(node_key)
                mounts.append(
                    DevMount(
                        device_path=dev_path,
                        server_pid=pid,
                        server_name=name,
                        mount_type=mount_type,
                    )
                )
        except ValueError:
            continue

    return sorted(mounts, key=lambda m: m.device_path)


def parse_pidin_info(raw_output: str) -> SystemInfo:
    """
    Extracts QNX kernel version, CPU architecture/core count, total/free RAM, and boot info.
    """
    info = SystemInfo()
    if not raw_output:
        return info

    for line in raw_output.splitlines():
        line_clean = line.strip()

        # Cores and architecture
        cores_match = re.search(r"Cores:\s*(\d+)", line_clean, re.IGNORECASE)
        if cores_match:
            info.cores = int(cores_match.group(1))

        if "x86_64" in line_clean:
            info.arch = "x86_64"
        elif "aarch64" in line_clean or "arm64" in line_clean:
            info.arch = "aarch64"

        # RAM
        total_ram_match = re.search(r"Total Physical Memory:\s*(\d+)", line_clean, re.IGNORECASE)
        if total_ram_match:
            info.total_ram_mb = int(total_ram_match.group(1))

        free_ram_match = re.search(r"Free Physical Memory:\s*(\d+)", line_clean, re.IGNORECASE)
        if free_ram_match:
            info.free_ram_mb = int(free_ram_match.group(1))

        # Kernel version
        kernel_match = re.search(r"Kernel Version:\s*(.+)", line_clean, re.IGNORECASE)
        if kernel_match:
            info.os_version = kernel_match.group(1).strip()

        # Boot time
        boot_match = re.search(r"Boot Time:\s*(.+)", line_clean, re.IGNORECASE)
        if boot_match:
            info.boot_time = boot_match.group(1).strip()

    return info


def parse_slog2info(raw_output: str, seen_signatures: Optional[Set[str]] = None) -> list[LogEntry]:
    """
    Parses slog2info -S lines into LogEntry objects.
    Line schema: <Timestamp> <Buffer.PID> <SEVERITY> <Message>
    Deduplicates against previously seen lines per poll cycle if seen_signatures is provided.
    """
    entries: list[LogEntry] = []
    lines = raw_output.strip().splitlines()

    # Pattern: [Month Day Time] [Buffer] [SLOG2_SEVERITY] [Message]
    log_re = re.compile(
        r"^([A-Za-z]{3}\s+\d+\s+\d{2}:\d{2}:\d{2}\.\d+)\s+(\S+)\s+(SLOG2_[A-Z]+)\s+(.+)$"
    )

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        if seen_signatures is not None:
            if line_clean in seen_signatures:
                continue
            seen_signatures.add(line_clean)

        match = log_re.match(line_clean)
        if match:
            timestamp, buffer_id, severity, message = match.groups()
            entries.append(
                LogEntry(
                    timestamp=timestamp,
                    buffer=buffer_id,
                    severity=severity,
                    message=message,
                    raw=line_clean,
                )
            )
        else:
            # Fallback for non-standard log lines
            entries.append(
                LogEntry(
                    timestamp="",
                    buffer="system",
                    severity="SLOG2_INFO",
                    message=line_clean,
                    raw=line_clean,
                )
            )

    return entries
