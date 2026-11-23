"""Diagnostic snapshot generator for QNX 8.0 targets (F5 report)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import List, Optional, Tuple
from core.models import ThreadRecord, InversionAlert, DevMount, LogEntry, SystemInfo


def generate_markdown_report(
    sys_info: SystemInfo,
    threads: List[ThreadRecord],
    alerts: List[InversionAlert],
    dev_mounts: List[DevMount],
    logs: List[LogEntry],
) -> str:
    """Produces a formatted GitHub Flavored Markdown diagnostic report."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = []
    md.append(f"# qprobe: QNX 8.0 System Diagnostic Snapshot")
    md.append(f"**Generated:** {now_str} | **Target:** `{sys_info.host_target}`\n")

    # 1. System & Microkernel Information
    md.append("## 1. System & Microkernel Topology")
    md.append(f"- **OS Version:** {sys_info.os_version}")
    md.append(f"- **Architecture:** {sys_info.arch} ({sys_info.cores} Cores)")
    md.append(f"- **Physical RAM:** {sys_info.total_ram_mb} MB Total, {sys_info.free_ram_mb} MB Free")
    md.append(f"- **Boot Timestamp:** {sys_info.boot_time}\n")

    # 2. Priority Inversion Alerts
    md.append("## 2. Priority Inversion & IPC Blocking Analysis")
    if alerts:
        md.append(f"> [!CAUTION]\n> **Detected {len(alerts)} Active Priority Inversion Condition(s)!**\n")
        md.append("| Severity | Client PID | Client Thread | Priority | Blocked On Server | Server Priority | Transitive Chain |")
        md.append("|---|---|---|---|---|---|---|")
        for a in alerts:
            chain_str = " ➔ ".join(a.chain) if a.chain else f"{a.client_name} ➔ {a.server_name}"
            md.append(
                f"| **{a.severity}** | {a.client_pid}.{a.client_tid} | `{a.client_name}` | `{a.client_priority}` | `{a.server_name}` (PID {a.server_pid}) | `{a.server_priority}` | `{chain_str}` |"
            )
        md.append("")
    else:
        md.append("No priority inversions detected. Thread scheduling hierarchies are healthy.\n")

    # 3. Thread & Scheduling Overview
    md.append(f"## 3. Active Threads & Scheduling Policies ({len(threads)} Total)")
    md.append("| PID | TID | Name | Priority | Policy | State | Blocked On |")
    md.append("|---|---|---|---|---|---|---|")
    for t in threads:
        md.append(
            f"| {t.pid} | {t.tid} | `{t.name}` | {t.priority_raw} | {t.policy} | {t.state} | {t.blocked_on or '-'} |"
        )
    md.append("")

    # 4. /dev Resource Manager Mappings
    md.append(f"## 4. /dev Resource Manager Namespace ({len(dev_mounts)} Nodes)")
    md.append("| Device Path | Server PID | Process Name | Mount Type |")
    md.append("|---|---|---|---|")
    for m in dev_mounts:
        md.append(f"| `{m.device_path}` | {m.server_pid} | `{m.server_name}` | {m.mount_type} |")
    md.append("")

    # 5. Recent slog2info Logs
    md.append(f"## 5. Recent slog2 System Logs ({len(logs)} Entries)")
    md.append("| Timestamp | Buffer | Severity | Message |")
    md.append("|---|---|---|---|")
    for l in logs[-50:]:  # Last 50 entries
        md.append(f"| {l.timestamp or '-'} | `{l.buffer}` | {l.severity} | {l.message} |")
    md.append("")

    return "\n".join(md)


def export_diagnostic_snapshot(
    sys_info: SystemInfo,
    threads: List[ThreadRecord],
    alerts: List[InversionAlert],
    dev_mounts: List[DevMount],
    logs: List[LogEntry],
    output_dir: str = ".",
) -> Tuple[str, str]:
    """
    Exports both Markdown and JSON diagnostic files to disk.
    Returns (md_filepath, json_filepath).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_filename = f"qnx_report_{timestamp}.md"
    json_filename = f"qnx_report_{timestamp}.json"

    md_path = os.path.join(output_dir, md_filename)
    json_path = os.path.join(output_dir, json_filename)

    # 1. Write Markdown
    md_content = generate_markdown_report(sys_info, threads, alerts, dev_mounts, logs)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 2. Write JSON
    json_payload = {
        "timestamp": datetime.now().isoformat(),
        "system_info": sys_info.__dict__,
        "inversion_alerts": [a.__dict__ for a in alerts],
        "threads": [t.__dict__ for t in threads],
        "dev_mounts": [m.__dict__ for m in dev_mounts],
        "logs": [l.__dict__ for l in logs],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2)

    return md_path, json_path
