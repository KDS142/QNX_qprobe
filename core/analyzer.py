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


def trace_blocking_chain(
    start_thread: ThreadRecord,
    threads_by_pid: Dict[int, List[ThreadRecord]],
    pids_to_name: Dict[int, str],
    max_prio_by_pid: Dict[int, int],
) -> List[str]:
    """
    Traces transitive REPLY-blocking chains (e.g., Client -> Server1 -> Server2).
    Prevents infinite cycles with a visited set.
    """
    chain = [f"{start_thread.name} (PID {start_thread.pid}, prio {start_thread.priority})"]
    visited = {start_thread.pid}

    current_blocked_on = start_thread.blocked_on
    while current_blocked_on:
        next_pid = extract_server_pid(current_blocked_on)
        if next_pid is None or next_pid in visited:
            break
        visited.add(next_pid)
        next_name = pids_to_name.get(next_pid, f"pid_{next_pid}")
        next_prio = max_prio_by_pid.get(next_pid, 0)
        chain.append(f"{next_name} (PID {next_pid}, prio {next_prio})")

        # Check if next_pid is also REPLY-blocked on another server
        next_threads = threads_by_pid.get(next_pid, [])
        reply_threads = [t for t in next_threads if t.state == "REPLY" and t.blocked_on]
        if reply_threads:
            current_blocked_on = reply_threads[0].blocked_on
        else:
            break

    return chain


def detect_priority_inversions(threads: List[ThreadRecord]) -> List[InversionAlert]:
    """
    Executes the 4-step priority inversion detection algorithm:
    Step 1: Index active priorities by process ID: max_prio_by_pid[pid]
    Step 2: Resolve REPLY blocks and target server PIDs
    Step 3: Compare client priority against server priority; emit InversionAlert if client > server
    Step 4: Trace full transitive blocking chain for deep diagnostics
    """
    # Step 1: Index highest numeric priority per process ID and group threads
    max_prio_by_pid: Dict[int, int] = {}
    pids_to_name: Dict[int, str] = {}
    threads_by_pid: Dict[int, List[ThreadRecord]] = {}

    for t in threads:
        pids_to_name[t.pid] = t.name
        threads_by_pid.setdefault(t.pid, []).append(t)
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
                    chain = trace_blocking_chain(client, threads_by_pid, pids_to_name, max_prio_by_pid)
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
                            chain=chain,
                        )
                    )

    return alerts
