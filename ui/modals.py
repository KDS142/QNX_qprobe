"""Modal screens for deployment, confirmation, and help."""
from __future__ import annotations

from typing import Optional
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static


class DeployModal(ModalScreen[Optional[dict]]):
    """Modal for SFTP upload and on -p real-time priority execution."""

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Remote Priority Deployer (SFTP + on -p)", classes="modal-title")
            yield Label("Target Script / Binary Path (Local):")
            yield Input(
                placeholder="/path/to/binary or scripts/mock_qnx_service.sh",
                value="scripts/mock_qnx_service.sh",
                id="deploy-file",
            )
            yield Label("Real-Time Priority (1-63):")
            yield Input(value="25", id="deploy-prio")
            yield Label("Scheduling Policy:")
            with RadioSet(id="deploy-policy"):
                yield RadioButton("FIFO (Deterministic Real-Time)", value=True, id="policy-fifo")
                yield RadioButton("Round-Robin (Time-Sliced)", value=False, id="policy-rr")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Deploy & Launch", variant="primary", id="btn-deploy")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-deploy":
            file_path = self.query_one("#deploy-file", Input).value.strip()
            prio_str = self.query_one("#deploy-prio", Input).value.strip()
            policy_fifo = self.query_one("#policy-fifo", RadioButton).value

            try:
                prio = int(prio_str)
                prio = max(1, min(63, prio))
            except ValueError:
                prio = 25

            policy_flag = "f" if policy_fifo else "r"

            self.dismiss(
                {
                    "file_path": file_path,
                    "priority": prio,
                    "policy_flag": policy_flag,
                }
            )
        else:
            self.dismiss(None)


class ConfirmSlayModal(ModalScreen[bool]):
    """Confirmation modal for slaying/terminating a remote QNX process."""

    def __init__(self, target: str, is_dangerous: bool = False, warning: str = ""):
        super().__init__()
        self.target = target
        self.is_dangerous = is_dangerous
        self.warning = warning

    def compose(self) -> ComposeResult:
        dialog_class = "modal-dialog danger-dialog" if self.is_dangerous else "modal-dialog"
        title_class = "modal-title danger-title" if self.is_dangerous else "modal-title"

        with Container(classes=dialog_class):
            title = "CRITICAL SAFETY WARNING" if self.is_dangerous else "Confirm Process Termination"
            yield Label(title, classes=title_class)
            yield Static(f"Are you sure you want to terminate target: [b]{self.target}[/b]?")

            if self.is_dangerous:
                yield Static(f"\n[red bold]{self.warning}[/]\nTerminating this process may crash QNX or disconnect SSH!")
            elif self.warning:
                yield Static(f"\n[yellow]{self.warning}[/]")

            with Horizontal(classes="modal-buttons"):
                yield Button("Abort", variant="default", id="btn-abort")
                yield Button("Confirm Slay", variant="error" if self.is_dangerous else "primary", id="btn-confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)


class HelpModal(ModalScreen[None]):
    """Help and keybindings overview."""

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("qprobe Keybindings & Navigation", classes="modal-title")
            help_text = (
                "[b]Global Keybindings:[/b]\n"
                "  [cyan]F1[/cyan]    : Tab 1 — Threads, Scheduling & Priority Inversions\n"
                "  [cyan]F2[/cyan]    : Tab 2 — /dev Resource Managers & Fault Sandbox\n"
                "  [cyan]F3[/cyan]    : Tab 3 — slog2info Structured Log Stream\n"
                "  [cyan]/[/cyan]     : Focus Bottom Linux-to-QNX Command Translator\n"
                "  [cyan]Ctrl+D[/cyan]: Remote Priority Deployer (SFTP + on -p modal)\n"
                "  [cyan]F5[/cyan]    : Export Diagnostic Snapshot (Markdown + JSON)\n"
                "  [cyan]?[/cyan]     : Show this Help Modal\n"
                "  [cyan]Ctrl+C[/cyan]: Quit Application\n\n"
                "[b]Linux-to-QNX Bridge:[/b]\n"
                "  Type Linux commands (ps aux, top, kill -9, lsof -p 1, dmesg, free -h, etc.)\n"
                "  in the bottom input bar. Live preview displays the native QNX equivalent\n"
                "  and microkernel explanation. Press Enter to execute.\n"
            )
            yield Static(help_text)
            with Horizontal(classes="modal-buttons"):
                yield Button("Close", variant="primary", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)
