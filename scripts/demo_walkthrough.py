"""
scripts/demo_walkthrough.py - Guided Interactive Demo Script for Hackathon Presentation
Follows Section 8: 2-Minute Demo Video Flow
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from core.ssh_client import DemoExecutor
from core.collectors import parse_pidin_threads, parse_pidin_fds, parse_pidin_info, parse_slog2info
from core.analyzer import detect_priority_inversions
from core.translator import translate_linux_command
from core.exporter import export_diagnostic_snapshot

console = Console()


def section_header(title: str, timestamp_range: str):
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{title}[/bold cyan]\n[dim]Video Segment: {timestamp_range}[/dim]",
            border_style="bright_blue",
        )
    )


def step_1_live_connection(executor: DemoExecutor):
    section_header("1. Live Target Connection & Telemetry", "0:00 - 0:25")
    console.print("[green]Connecting to QNX SDP 8.0 target (Demo Replay Mode)...[/green]")
    executor.connect()

    _, raw_info, _ = executor.exec_command("pidin info")
    sys_info = parse_pidin_info(raw_info)

    table = Table(title="QNX 8.0 Target Kernel & Topology", border_style="cyan")
    table.add_column("Property", style="bold white")
    table.add_column("Value", style="green")
    table.add_row("Operating System", sys_info.os_version)
    table.add_row("CPU Architecture", f"{sys_info.arch} ({sys_info.cores} Cores)")
    table.add_row("Physical Memory", f"{sys_info.free_ram_mb} MB Free / {sys_info.total_ram_mb} MB Total")
    table.add_row("Boot Timestamp", sys_info.boot_time)
    console.print(table)


def step_2_linux_bridge():
    section_header("2. Linux-to-QNX Command Bridge & Safety Guards", "0:25 - 0:55")
    commands = ["ps aux", "lsof -p 1", "dmesg", "kill -9 1", "kill -9 1420"]

    for cmd in commands:
        res = translate_linux_command(cmd)
        console.print(f"[bold yellow]$ {cmd}[/bold yellow]")
        console.print(f"  [cyan]➔ QNX Equivalent:[/] [bold white]{res.qnx_cmd}[/bold white]")
        console.print(f"  [dim]Architectural Note: {res.explanation}[/dim]")
        if res.is_dangerous:
            console.print(f"  [bold red]SAFETY GUARD TRIGGERED:[/] {res.warning}")
        console.print()


def step_3_priority_inversion(executor: DemoExecutor):
    section_header("3. Real-Time Determinism & Priority Inversion Detection", "0:55 - 1:30")
    _, raw_threads, _ = executor.exec_command('pidin -F "%a %b %N %p %J %B"')
    threads = parse_pidin_threads(raw_threads)
    alerts = detect_priority_inversions(threads)

    if alerts:
        alert = alerts[0]
        chain_str = " ➔ ".join(alert.chain) if alert.chain else f"{alert.client_name} ➔ {alert.server_name}"
        console.print(
            Panel(
                f"[bold red]CRITICAL PRIORITY INVERSION DETECTED![/bold red]\n\n"
                f"Client: [bold white]{alert.client_name}[/bold white] (PID {alert.client_pid}, prio [bold red]{alert.client_priority}[/bold red])\n"
                f"Blocked On: [bold white]{alert.server_name}[/bold white] (PID {alert.server_pid}, prio [bold yellow]{alert.server_priority}[/bold yellow])\n"
                f"Transitive Blocking Chain: [cyan]{chain_str}[/cyan]\n\n"
                f"[yellow]Microkernel Impact:[/] High-priority thread is stalled waiting for a lower-priority server to reply!",
                border_style="red",
            )
        )


def step_4_fault_isolation(executor: DemoExecutor):
    section_header("4. Microkernel Fault Isolation & Diagnostic Export", "1:30 - 2:00")
    console.print("[yellow]Simulating Fault Injection: Terminating user-space driver mock_qnx_service.sh...[/yellow]")
    executor.exec_command("slay -f mock_qnx_service.sh")

    _, raw_threads, _ = executor.exec_command('pidin -F "%a %b %N %p %J %B"')
    threads = parse_pidin_threads(raw_threads)
    active_names = [t.name for t in threads]

    console.print(f"  Service mock_qnx_service.sh active: [red]{'mock_qnx_service.sh' in active_names}[/red]")
    console.print(f"  Microkernel procnto-smp-instr active: [bold green]{'procnto-smp-instr' in active_names}[/bold green] (UNAFFECTED!)")

    _, raw_logs, _ = executor.exec_command("slog2info -S")
    logs = parse_slog2info(raw_logs)
    last_log = logs[-1] if logs else None
    if last_log:
        console.print(f"  [cyan]slog2info Log Entry:[/] {last_log.message}")

    # Export Diagnostic Snapshot (F5)
    _, raw_info, _ = executor.exec_command("pidin info")
    sys_info = parse_pidin_info(raw_info)
    _, raw_fds, _ = executor.exec_command("pidin fds")
    mounts = parse_pidin_fds(raw_fds)
    alerts = detect_priority_inversions(threads)

    md_path, json_path = export_diagnostic_snapshot(sys_info, threads, alerts, mounts, logs, output_dir=".")
    console.print(f"\n[bold green]F5 Diagnostic Snapshot Exported Successfully:[/bold green]")
    console.print(f"  Markdown: [underline]{os.path.basename(md_path)}[/underline]")
    console.print(f"  JSON:     [underline]{os.path.basename(json_path)}[/underline]")


def main():
    console.print(
        Panel.fit(
            "[bold white]qnx-inspector: 2-Minute Demo Video Walkthrough[/bold white]\n"
            "[cyan]QNX Global Hackathon 2026 Developer Tooling & Host Tools[/cyan]",
            border_style="bright_blue",
        )
    )

    executor = DemoExecutor()
    step_1_live_connection(executor)
    step_2_linux_bridge()
    step_3_priority_inversion(executor)
    step_4_fault_isolation(executor)

    console.print("\n[bold green]Walkthrough Complete![/bold green] Ready to launch TUI via: [cyan]python qnx_inspector.py --demo[/cyan]\n")


if __name__ == "__main__":
    main()
