"""Real-time priority inversion and IPC blocking chain detection algorithm."""
from __future__ import annotations

import re
from typing import Dict, List, Optional
from core.models import ThreadRecord, InversionAlert


def extract_server_pid(blocked_on: str) -> Optional[int]:
    """
    Extracts the server PID from the blocked_on field.
    Handles formats like '12290', '12290-1' (pid-channel/tid), or channel descriptors.
    """
    if not blocked_on:
        return None

    # Matches initial numeric sequence representing PID
    match = re.match(r"^(\d+)", blocked_on.strip())
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def detect_priority_inversions(threads: List[ThreadRecord]) -> List[InversionAlert]:
    """
    Executes the 4-step priority inversion detection algorithm:
    Step 1: Index active priorities by process ID: max_prio_by_pid[pid]
    Step 2: Resolve REPLY blocks and target server PIDs
    Step 3: Compare client priority against server priority; emit InversionAlert if client > server
    """
    # Step 1: Index highest numeric priority per process ID
    max_prio_by_pid: Dict[int, int] = {}
    pids_to_name: Dict[int, str] = {}

    for t in threads:
        pids_to_name[t.pid] = t.name
        if t.pid not in max_prio_by_pid or t.priority > max_prio_by_pid[t.pid]:
            max_prio_by_pid[t.pid] = t.priority

    alerts: List[InversionAlert] = []

    # Step 2: Iterate through threads looking for REPLY blocks
    for client in threads:
        if client.state == "REPLY":
            server_pid = extract_server_pid(client.blocked_on)
            if server_pid is None:
                continue

            # Check if server exists in running threads
            if server_pid in max_prio_by_pid:
                server_priority = max_prio_by_pid[server_pid]
                server_name = pids_to_name.get(server_pid, f"pid_{server_pid}")

                # Step 3: Compare client priority with highest priority of server
                # Priority Inversion occurs when a high-priority client is waiting on a lower-priority server
                if client.priority > server_priority:
                    alerts.append(
                        InversionAlert(
                            client_pid=client.pid,
                            client_tid=client.tid,
                            client_name=client.name,
                            client_priority=client.priority,
                            server_pid=server_pid,
                            server_name=server_name,
                            server_priority=server_priority,
                            severity="CRITICAL",
                        )
                    )

    return alerts
