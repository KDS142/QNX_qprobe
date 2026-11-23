"""
qnx-inspector: Agent Implementation Blueprint Entrypoint
Terminal User Interface (TUI) for QNX SDP 8.0 Telemetry, Priority Inversion Detection,
and Linux-to-QNX Command Translation.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Optional, Set

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from core.analyzer import detect_priority_inversions
from core.collectors import (
    parse_pidin_fds,
    parse_pidin_info,
    parse_pidin_threads,
    parse_slog2info,
)
from core.exporter import export_diagnostic_snapshot
from core.models import DevMount, InversionAlert, LogEntry, SystemInfo, ThreadRecord
from core.ssh_client import BaseExecutor, DemoExecutor, SSHClient
from core.translator import translate_linux_command
from ui.modals import ConfirmSlayModal, DeployModal, HelpModal


class QNXInspector(App):
    """Main Textual Application for qprobe."""

    TITLE = "qprobe"
    CSS_PATH = "ui/styles.tcss"

    BINDINGS = [
        Binding("f1", "switch_tab('tab-threads')", "Threads & IPC (F1)", priority=True),
        Binding("f2", "switch_tab('tab-dev')", "/dev ResMgr (F2)", priority=True),
        Binding("f3", "switch_tab('tab-logs')", "slog2 Logs (F3)", priority=True),
        Binding("slash", "focus_translator", "Translate ( / )", priority=True),
        Binding("ctrl+d", "open_deployer", "Deploy (Ctrl+D)", priority=True),
        Binding("f5", "export_snapshot", "Export (F5)", priority=True),
        Binding("question_mark", "open_help", "Help (?)", priority=True),
        Binding("ctrl+c", "quit", "Quit (Ctrl+C)", priority=True),
    ]

    def __init__(
        self,
        executor: BaseExecutor,
        is_demo: bool = False,
        host_label: str = "localhost:2222",
        enable_polling: bool = True,
    ):
        super().__init__()
        self.executor = executor
        self.is_demo = is_demo
        self.host_label = host_label
        self.enable_polling = enable_polling

        # Cached telemetry state
        self.system_info = SystemInfo(host_target=self.host_label)
        self.threads: list[ThreadRecord] = []
        self.alerts: list[InversionAlert] = []
        self.dev_mounts: list[DevMount] = []
        self.logs: list[LogEntry] = []
        self.seen_log_signatures: Set[str] = set()
        self.MAX_LOG_SIGNATURES = 10000  # Bound memory for long-running sessions

        # UI state
        self.filter_blocked_only = False
        self.log_severity_filter = "ALL"  # 'ALL', 'WARNING+', 'ERROR'
        self.log_autoscroll = True
        self.sort_col_index = 3  # Default sort by Priority
        self.sort_descending = True

    @property
    def has_active_screen(self) -> bool:
        return bool(self._screen_stack)

    def compose(self) -> ComposeResult:
        # Header Status Bar
        with Horizontal(id="header-bar"):
            yield Label("qprobe", id="header-title")
            badge_text = "DEMO MODE" if self.is_demo else f"LIVE: {self.host_label}"
            badge_class = "badge-demo" if self.is_demo else "badge-live"
            yield Label(badge_text, id="status-badge", classes=badge_class)
            yield Label("Connecting...", id="header-sysinfo")
            yield Label("Threads: 0", id="header-threads")

        # Main Workspace
        with TabbedContent(id="main-tabs"):
            # Tab 1: Threads & IPC
            with TabPane("Threads & IPC (F1)", id="tab-threads"):
                with Vertical(id="tab1-container"):
                    yield Static("", id="inversion-banner")
                    with Horizontal(id="thread-toolbar"):
                        yield Button("Filter: All Threads", id="filter-btn", variant="default")
                        yield Label(" | Click column header to sort | Red: Client | Gold: Server", classes="info-hint")
                    yield DataTable(id="threads-table", cursor_type="row", zebra_stripes=True)

            # Tab 2: Resource Managers & Fault Isolation
            with TabPane("/dev Resource Managers (F2)", id="tab-dev"):
                with Horizontal(id="tab2-split"):
                    with Vertical(id="tab2-left-pane"):
                        yield Label("/dev Namespace & Resource Managers", classes="pane-title")
                        yield DataTable(id="dev-table", cursor_type="row", zebra_stripes=True)
                    with Vertical(id="tab2-right-pane"):
                        yield Label("Microkernel Fault Isolation Sandbox", classes="pane-title")
                        with Vertical(id="sandbox-box"):
                            yield Static(
                                "Demonstrates QNX Microkernel resilience:\n"
                                "Drivers and services run in isolated user-space memory spaces.\n"
                                "Crashing or terminating a service does NOT crash the procnto kernel."
                            )
                            yield Static("Service: mock_qnx_service.sh | Status: RUNNING (PID 1420)", id="sandbox-status")
                            with Horizontal(id="sandbox-buttons"):
                                yield Button("Inject Fault (Kill Service)", id="btn-kill-sandbox", variant="error")
                                yield Button("Respawn Service", id="btn-respawn-sandbox", variant="success")
                            yield Static(
                                "Kernel procnto Status: HEALTHY | Uptime Unaffected | Memory Stable",
                                id="sandbox-procnto-status",
                            )

            # Tab 3: slog2 Logs
            with TabPane("slog2info Logs (F3)", id="tab-logs"):
                with Vertical(id="tab3-container"):
                    with Horizontal(id="log-toolbar"):
                        yield Label("Filter: ")
                        yield Button("ALL", id="btn-log-all", variant="primary")
                        yield Button("WARNING+", id="btn-log-warn", variant="default")
                        yield Button("ERROR", id="btn-log-err", variant="default")
                        yield Button("Auto-Scroll: ON", id="btn-log-scroll", variant="default")
                    yield RichLog(id="log-stream", highlight=True, markup=True)

        # Bottom Command Translator Dock
        with Vertical(id="translator-dock"):
            yield Input(
                placeholder="Type Linux command (e.g., ps aux, top, kill -9 1200, lsof -p 1, dmesg, free -h)...",
                id="translator-input",
            )
            yield Label("QNX Equivalent: pidin", id="translator-preview")
            yield Label("Architectural Note: Microkernel command translation preview", id="translator-explanation")
            yield Label("", id="translator-warning")
            yield RichLog(id="output-drawer", highlight=True, markup=True)

        # Keybindings Footer
        yield Static(
            "F1-F3 Switch Tabs  |  / Focus Translator  |  Ctrl+D Deploy & Run (on -p)  |  F5 Export Snapshot  |  ? Help  |  Ctrl+C Quit",
            id="footer-bar",
        )

    def on_mount(self) -> None:
        """Initialize tables, start background poller, and connect transport."""
        # Initialize Threads Table
        threads_table = self.query_one("#threads-table", DataTable)
        threads_table.add_columns("PID", "TID", "Name", "Priority", "Policy", "State", "Blocked-On")

        # Initialize Dev Table
        dev_table = self.query_one("#dev-table", DataTable)
        dev_table.add_columns("Device Path", "Server PID", "Process Name", "Mount Type")

        # Connect executor
        self.executor.connect()

        # Initial immediate refresh
        self.refresh_telemetry()

        # 1.5s background polling loop
        if self.enable_polling:
            self.set_interval(1.5, self.refresh_telemetry)

    def refresh_telemetry(self) -> None:
        """Fetches remote telemetry via SSH or Demo executor and updates widgets."""
        # 1. Hardware & Kernel Info (pidin info)
        _, raw_info, _ = self.executor.exec_command("pidin info")
        if raw_info:
            self.system_info = parse_pidin_info(raw_info)
            self.system_info.host_target = self.host_label
            if self.has_active_screen:
                sys_summary = f"{self.system_info.os_version} ({self.system_info.arch}, {self.system_info.cores} cores) | RAM: {self.system_info.free_ram_mb}/{self.system_info.total_ram_mb} MB"
                self.query_one("#header-sysinfo", Label).update(sys_summary)

        # 2. Threads & IPC (pidin -F "%a %b %N %p %J %B")
        _, raw_threads, _ = self.executor.exec_command('pidin -F "%a %b %N %p %J %B"')
        if raw_threads:
            self.threads = parse_pidin_threads(raw_threads)
            self.alerts = detect_priority_inversions(self.threads)
            if self.has_active_screen:
                self.query_one("#header-threads", Label).update(f"Threads: {len(self.threads)}")
                self._update_inversion_banner()
                self._update_threads_table()

        # 3. /dev Resource Manager Map (pidin fds)
        _, raw_fds, _ = self.executor.exec_command("pidin fds")
        if raw_fds:
            self.dev_mounts = parse_pidin_fds(raw_fds)
            if self.has_active_screen:
                self._update_dev_table()

        # 4. slog2 Logs (slog2info -S)
        _, raw_logs, _ = self.executor.exec_command("slog2info -S")
        if raw_logs:
            # Bound the deduplication set to prevent unbounded memory growth
            if len(self.seen_log_signatures) > self.MAX_LOG_SIGNATURES:
                self.seen_log_signatures.clear()
            new_entries = parse_slog2info(raw_logs, self.seen_log_signatures)
            if new_entries:
                self.logs.extend(new_entries)
                if self.has_active_screen:
                    self._append_logs(new_entries)

    def _update_inversion_banner(self) -> None:
        banner = self.query_one("#inversion-banner", Static)
        if self.alerts:
            banner.add_class("visible")
            alert = self.alerts[0]
            banner.update(
                f"[blink]CRITICAL PRIORITY INVERSION DETECTED:[/blink] "
                f"High-priority client '{alert.client_name}' (PID {alert.client_pid}, prio {alert.client_priority}) "
                f"is REPLY-blocked on low-priority server '{alert.server_name}' (PID {alert.server_pid}, prio {alert.server_priority})!"
            )
        else:
            banner.remove_class("visible")
            banner.update("")

    def _update_threads_table(self) -> None:
        table = self.query_one("#threads-table", DataTable)
        table.clear()

        alert_client_pids = {a.client_pid for a in self.alerts}
        alert_server_pids = {a.server_pid for a in self.alerts}

        def get_sort_key(t: ThreadRecord):
            if self.sort_col_index == 0:
                return t.pid
            elif self.sort_col_index == 1:
                return t.tid
            elif self.sort_col_index == 2:
                return t.name.lower()
            elif self.sort_col_index == 3:
                return t.priority
            elif self.sort_col_index == 4:
                return t.policy
            elif self.sort_col_index == 5:
                return t.state
            elif self.sort_col_index == 6:
                return t.blocked_on
            return t.priority

        sorted_threads = sorted(self.threads, key=get_sort_key, reverse=self.sort_descending)

        for t in sorted_threads:
            if self.filter_blocked_only and not (t.is_blocked or t.pid in alert_client_pids):
                continue

            # Format row with status styling
            prio_display = f"{t.priority_raw}"
            state_display = f"{t.state}"
            blocked_display = t.blocked_on or "-"

            if t.pid in alert_client_pids:
                prio_display = f"[bold red]{t.priority_raw} [CLIENT ALERT][/]"
                state_display = f"[bold red]{t.state}[/]"
            elif t.pid in alert_server_pids:
                prio_display = f"[bold yellow]{t.priority_raw} [BLOCKING SERVER][/]"

            table.add_row(
                str(t.pid),
                str(t.tid),
                t.name,
                prio_display,
                t.policy,
                state_display,
                blocked_display,
            )

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handles clicking table headers to sort columns."""
        if event.data_table.id == "threads-table":
            if self.sort_col_index == event.column_index:
                self.sort_descending = not self.sort_descending
            else:
                self.sort_col_index = event.column_index
                self.sort_descending = event.column_index in {0, 3}
            self._update_threads_table()

    def _update_dev_table(self) -> None:
        table = self.query_one("#dev-table", DataTable)
        table.clear()
        for m in self.dev_mounts:
            table.add_row(m.device_path, str(m.server_pid), m.server_name, m.mount_type)

    def _append_logs(self, entries: list[LogEntry]) -> None:
        log_widget = self.query_one("#log-stream", RichLog)
        for entry in entries:
            # Check severity filter
            if self.log_severity_filter == "WARNING+" and entry.severity not in {
                "SLOG2_WARNING",
                "SLOG2_ERROR",
                "SLOG2_CRITICAL",
            }:
                continue
            if self.log_severity_filter == "ERROR" and entry.severity not in {
                "SLOG2_ERROR",
                "SLOG2_CRITICAL",
            }:
                continue

            # Rich color formatting
            if "CRITICAL" in entry.severity or "ERROR" in entry.severity:
                color = "bold red"
            elif "WARNING" in entry.severity:
                color = "yellow"
            else:
                color = "green"

            ts = entry.timestamp or "----"
            log_widget.write(
                f"[{color}]{ts} [{entry.severity}][/] [cyan]{entry.buffer}[/] {entry.message}"
            )

        if self.log_autoscroll:
            log_widget.scroll_end(animate=False)

    # Keybinding Handlers
    def action_switch_tab(self, tab_id: str) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = tab_id

    def action_focus_translator(self) -> None:
        self.query_one("#translator-input", Input).focus()

    def action_open_help(self) -> None:
        self.push_screen(HelpModal())

    def action_open_deployer(self) -> None:
        async def handle_deploy(result: Optional[dict]) -> None:
            if not result:
                return
            file_path = result["file_path"]
            prio = result["priority"]
            pol = result["policy_flag"]
            remote_dest = f"/tmp/{os.path.basename(file_path)}"

            drawer = self.query_one("#output-drawer", RichLog)
            drawer.add_class("open")
            drawer.write(f"[dim]Deploying {file_path} to {remote_dest}...[/]")

            # SFTP Upload in worker thread
            uploaded = await asyncio.to_thread(self.executor.upload_file, file_path, remote_dest)
            launch_cmd = f"on -p {prio}{pol} {remote_dest} &"
            code, out, err = await asyncio.to_thread(self.executor.exec_command, launch_cmd)

            status = "Uploaded & Launched" if uploaded else "Spawned"
            drawer.write(f"[bold green]{status}:[/] {launch_cmd}\n{out or err}")
            self.refresh_telemetry()

        self.push_screen(DeployModal(), handle_deploy)

    def action_export_snapshot(self) -> tuple[str, str]:
        md_path, json_path = export_diagnostic_snapshot(
            self.system_info,
            self.threads,
            self.alerts,
            self.dev_mounts,
            self.logs,
            output_dir=".",
        )
        if self.has_active_screen:
            self.notify(f"Diagnostic Report Saved:\n{os.path.basename(md_path)}", timeout=5.0)
        return md_path, json_path

    # Input & Translator Handlers
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "translator-input":
            translation = translate_linux_command(event.value)
            preview = self.query_one("#translator-preview", Label)
            explanation = self.query_one("#translator-explanation", Label)
            warning = self.query_one("#translator-warning", Label)

            if translation.qnx_cmd:
                preview.update(f"[bold cyan]QNX Equivalent:[/] [white]{translation.qnx_cmd}[/]")
            else:
                preview.update("Type a command to view translation...")

            explanation.update(f"[dim]{translation.explanation}[/]")
            if translation.warning:
                warning.update(f"[bold red]WARNING:[/] {translation.warning}")
            else:
                warning.update("")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "translator-input":
            cmd_text = event.value.strip()
            if not cmd_text:
                return

            translation = translate_linux_command(cmd_text)
            qnx_cmd = translation.qnx_cmd or cmd_text

            drawer = self.query_one("#output-drawer", RichLog)
            drawer.add_class("open")

            # Check if confirmation needed
            if translation.requires_confirm:
                async def handle_confirm(confirmed: bool) -> None:
                    if confirmed:
                        drawer.write(f"[dim]Executing: {qnx_cmd}...[/]")
                        code, out, err = await asyncio.to_thread(self.executor.exec_command, qnx_cmd)
                        drawer.write(f"[cyan]$ {qnx_cmd}[/]\n{out or err}")
                        self.refresh_telemetry()
                    else:
                        drawer.write(f"[yellow]Command aborted by user: {qnx_cmd}[/]")

                self.push_screen(
                    ConfirmSlayModal(
                        target=qnx_cmd,
                        is_dangerous=translation.is_dangerous,
                        warning=translation.warning,
                    ),
                    handle_confirm,
                )
            else:
                drawer.write(f"[dim]Executing: {qnx_cmd}...[/]")
                code, out, err = await asyncio.to_thread(self.executor.exec_command, qnx_cmd)
                drawer.write(f"[cyan]$ {qnx_cmd}[/]\n{out or err}")
                self.refresh_telemetry()

    # Button Event Handlers
    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        # Tab 1: Filter toggle
        if btn_id == "filter-btn":
            self.filter_blocked_only = not self.filter_blocked_only
            btn = self.query_one("#filter-btn", Button)
            btn.label = "Filter: Blocked/Alerts Only" if self.filter_blocked_only else "Filter: All Threads"
            btn.variant = "primary" if self.filter_blocked_only else "default"
            self._update_threads_table()

        # Tab 2: Fault isolation sandbox
        elif btn_id == "btn-kill-sandbox":
            self.executor.exec_command("slay -f mock_qnx_service.sh")
            self.query_one("#sandbox-status", Static).update(
                "[bold red]Service: mock_qnx_service.sh | Status: TERMINATED (FAULT INJECTED)[/]"
            )
            self.refresh_telemetry()

        elif btn_id == "btn-respawn-sandbox":
            self.executor.exec_command("on -p 10r /tmp/mock_qnx_service.sh &")
            self.query_one("#sandbox-status", Static).update(
                "[bold green]Service: mock_qnx_service.sh | Status: RUNNING (PID 1420)[/]"
            )
            self.refresh_telemetry()

        # Tab 3: Log severity filters
        elif btn_id == "btn-log-all":
            self.log_severity_filter = "ALL"
            self._set_active_log_button("btn-log-all")
            self._repopulate_logs()
        elif btn_id == "btn-log-warn":
            self.log_severity_filter = "WARNING+"
            self._set_active_log_button("btn-log-warn")
            self._repopulate_logs()
        elif btn_id == "btn-log-err":
            self.log_severity_filter = "ERROR"
            self._set_active_log_button("btn-log-err")
            self._repopulate_logs()
        elif btn_id == "btn-log-scroll":
            self.log_autoscroll = not self.log_autoscroll
            event.button.label = f"Auto-Scroll: {'ON' if self.log_autoscroll else 'OFF'}"

    def _set_active_log_button(self, active_id: str) -> None:
        for b_id in ["btn-log-all", "btn-log-warn", "btn-log-err"]:
            btn = self.query_one(f"#{b_id}", Button)
            btn.variant = "primary" if b_id == active_id else "default"

    def _repopulate_logs(self) -> None:
        log_widget = self.query_one("#log-stream", RichLog)
        log_widget.clear()
        self._append_logs(self.logs)


def parse_args():
    parser = argparse.ArgumentParser(
        description="qprobe: Terminal User Interface for QNX SDP 8.0 Targets. Launch command: python qnx_inspector.py"
    )
    parser.add_argument("--host", default="localhost", help="QNX target host (default: localhost)")
    parser.add_argument("--port", type=int, default=2222, help="SSH port (default: 2222)")
    parser.add_argument("--user", default="root", help="SSH username (default: root)")
    parser.add_argument("--key", default=None, help="Path to SSH private key (default: None)")
    parser.add_argument("--password", default=None, help="SSH password (default: None)")
    parser.add_argument(
        "--demo", action="store_true", help="Run offline in demo replay mode using captured fixtures"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.demo:
        executor = DemoExecutor()
        app = QNXInspector(executor=executor, is_demo=True, host_label="DEMO MODE")
    else:
        executor = SSHClient(
            host=args.host,
            port=args.port,
            user=args.user,
            key_filename=args.key,
            password=args.password,
        )
        app = QNXInspector(
            executor=executor,
            is_demo=False,
            host_label=f"{args.user}@{args.host}:{args.port}",
        )

    app.run()


if __name__ == "__main__":
    main()
