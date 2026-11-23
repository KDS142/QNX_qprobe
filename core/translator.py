"""Rule-based Linux-to-QNX command & flag translation engine."""
from __future__ import annotations

import re
from typing import Tuple
from core.models import TranslationResult

DANGEROUS_PIDS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
PROTECTED_PROCESSES = {"procnto", "procnto-smp-instr", "procnto-smp", "sshd", "slogger2"}


def is_protected_target(target: str) -> Tuple[bool, str]:
    """Checks if target PID or process name is protected by safety guards."""
    clean_target = target.strip().lower()
    if clean_target.isdigit():
        pid = int(clean_target)
        if pid in DANGEROUS_PIDS or pid <= 10:
            return True, f"Target PID {pid} is a core microkernel or base driver process (PID <= 10)."
    else:
        # Check exact match against protected process names
        if clean_target in PROTECTED_PROCESSES:
            return True, f"Target process '{target}' is critical for system operation (procnto/sshd/slogger2)."
        # Check procnto variants (procnto-smp, procnto-smp-instr, etc.)
        if clean_target.startswith("procnto"):
            return True, f"Target process '{target}' is critical for system operation (procnto variant)."
    return False, ""


def translate_linux_command(cmd_str: str) -> TranslationResult:
    """
    Translates common Linux commands into native QNX 8.0 equivalents with
    architectural notes explaining microkernel differences and safety guards.
    """
    text = cmd_str.strip()
    if not text:
        return TranslationResult(
            linux_cmd="",
            qnx_cmd="",
            explanation="Empty command. Type a Linux command (e.g. ps aux, kill -9 1200, lsof -p 1).",
        )

    # 1. ps aux / ps -ef
    if re.match(r"^ps\s+(-?aux|-?ef|ax|a)$", text):
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd='pidin -F "%a %b %N %p %J %M"',
            explanation="QNX is thread-centric; pidin inspects threads, scheduling policies, and memory directly via procnto.",
        )

    # 2. top / htop
    if re.match(r"^(top|htop)$", text):
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="pidin times",
            explanation="Displays per-thread CPU execution time and priority scheduling buckets without GNU /proc overhead.",
        )

    # 3. kill -9 <pid_or_name>
    kill9_match = re.match(r"^kill\s+-9\s+(\S+)$", text)
    if kill9_match:
        target = kill9_match.group(1)
        is_dang, reason = is_protected_target(target)
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd=f"slay -f {target}",
            explanation="slay terminates QNX processes by PID or name. -f forces immediate termination (SIGKILL).",
            is_dangerous=is_dang,
            requires_confirm=True,
            warning=f"SAFETY GUARD: {reason} Slaying it may crash the target VM or terminate your SSH session!" if is_dang else "Confirm slaying target process.",
        )

    # 4. kill <pid> (SIGTERM)
    kill_match = re.match(r"^kill\s+(\S+)$", text)
    if kill_match:
        target = kill_match.group(1)
        is_dang, reason = is_protected_target(target)
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd=f"slay {target}",
            explanation="slay sends SIGTERM to the specified QNX process PID or binary name.",
            is_dangerous=is_dang,
            requires_confirm=is_dang,
            warning=f"SAFETY GUARD: {reason}" if is_dang else "",
        )

    # 5. killall <name>
    killall_match = re.match(r"^killall\s+(\S+)$", text)
    if killall_match:
        target = killall_match.group(1)
        is_dang, reason = is_protected_target(target)
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd=f"slay {target}",
            explanation="Native QNX utility that signals or terminates all user-space processes matching <name>.",
            is_dangerous=is_dang,
            requires_confirm=True,
            warning=f"SAFETY GUARD: {reason}" if is_dang else "Confirm slaying all instances of this process.",
        )

    # 6. lsof -p <pid>
    lsof_match = re.match(r"^lsof\s+-p\s+(\d+)$", text)
    if lsof_match:
        pid = lsof_match.group(1)
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd=f"pidin -p {pid} fds",
            explanation="Lists open file descriptors mapped directly to QNX user-space Resource Manager connections.",
        )

    # 7. lsof (general)
    if text == "lsof":
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="pidin fds",
            explanation="Scans all file descriptors and active Resource Manager mountpoints system-wide.",
        )

    # 8. dmesg / journalctl -f
    if re.match(r"^(dmesg|journalctl(\s+-f)?)$", text):
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="slog2info -S",
            explanation="Reads QNX's lock-free shared-memory structured logging buffers (slog2) rather than a kernel ring buffer.",
        )

    # 9. nice -n <p> <cmd>
    nice_match = re.match(r"^nice\s+-n\s+(\d+)\s+(.+)$", text)
    if nice_match:
        prio = nice_match.group(1)
        command = nice_match.group(2)
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd=f"on -p {prio}f {command}",
            explanation="Spawns a process with deterministic real-time priority (1–63) and FIFO (f) or Round-Robin (r) policy.",
        )

    # 10. renice <p> -p <pid>
    renice_match = re.match(r"^renice\s+(\d+)\s+-p\s+(\d+)$", text)
    if renice_match:
        prio = renice_match.group(1)
        pid = renice_match.group(2)
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd=f"on -p {prio} -P {pid}",
            explanation="Adjusts scheduling priority of an already running process/thread in procnto dynamically.",
        )

    # 11. lsmod / systemctl
    if re.match(r"^(lsmod|systemctl(\s+status)?)$", text):
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="pidin ar",
            explanation="QNX has no loadable kernel modules or systemd; drivers and services run as standard user-space processes.",
        )

    # 12. free -h / free
    if re.match(r"^free(\s+-h)?$", text):
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="pidin info",
            explanation="Queries the microkernel directly for physical memory totals, free pages, and CPU topology.",
        )

    # 13. netstat -tulnp / ss -tulnp / netstat
    if re.match(r"^(netstat(\s+-[a-zA-Z]+)?|ss(\s+-[a-zA-Z]+)?)$", text):
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="sockstat",
            explanation="Inspects active TCP/UDP endpoints owned by QNX's user-space networking stack (io-sock).",
        )

    # 14. pstree
    if text == "pstree":
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="pidin tree",
            explanation="Displays process and thread parent-child tree hierarchy tracked directly in procnto.",
        )

    # 15. vmstat
    if text == "vmstat":
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="pidin mem",
            explanation="Inspects virtual memory segments, code/data pages, and allocations per process.",
        )

    # 16. uptime
    if text == "uptime":
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="pidin info",
            explanation="Displays microkernel boot timestamp, elapsed uptime, and CPU hardware status.",
        )

    # 17. ip addr / ifconfig
    if re.match(r"^(ip\s+a(ddr)?|ifconfig)$", text):
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd="ifconfig",
            explanation="Queries user-space io-sock network stack for network interfaces and assigned IP addresses.",
        )

    # Pass-through for native QNX or standard shell commands
    native_keywords = {"pidin", "slay", "slog2info", "on", "sin", "uname", "ls", "cat", "ps", "pwd", "date", "echo"}
    first_token = text.split()[0].lower() if text.split() else ""
    if first_token in native_keywords:
        return TranslationResult(
            linux_cmd=text,
            qnx_cmd=text,
            explanation=f"Native QNX command '{first_token}' passes directly to remote shell.",
            is_dangerous=(first_token == "slay"),
            requires_confirm=(first_token == "slay"),
        )

    # Generic fallback
    return TranslationResult(
        linux_cmd=text,
        qnx_cmd=text,
        explanation="Standard remote command execution on QNX target shell.",
    )
