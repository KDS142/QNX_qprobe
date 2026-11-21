"""SSH and SFTP transport manager with offline DemoExecutor fallback."""
from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseExecutor(ABC):
    """Abstract interface for remote or simulated target execution."""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def exec_command(self, command: str) -> Tuple[int, str, str]:
        """Returns (exit_code, stdout, stderr)."""
        pass

    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class SSHClient(BaseExecutor):
    """Persistent Paramiko SSH & SFTP connection manager to QNX target."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 2222,
        user: str = "root",
        key_filename: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 5.0,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.key_filename = key_filename
        self.password = password
        self.timeout = timeout
        self._client = None
        self._sftp = None
        self._connected = False

    def connect(self) -> bool:
        try:
            import paramiko

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.host,
                "port": self.port,
                "username": self.user,
                "timeout": self.timeout,
            }

            if self.key_filename and os.path.exists(self.key_filename):
                connect_kwargs["key_filename"] = self.key_filename
            elif self.password:
                connect_kwargs["password"] = self.password
            else:
                # Try default user SSH key if present
                default_ed25519 = os.path.expanduser("~/.ssh/id_ed25519")
                default_rsa = os.path.expanduser("~/.ssh/id_rsa")
                if os.path.exists(default_ed25519):
                    connect_kwargs["key_filename"] = default_ed25519
                elif os.path.exists(default_rsa):
                    connect_kwargs["key_filename"] = default_rsa

            client.connect(**connect_kwargs)
            self._client = client
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def exec_command(self, command: str) -> Tuple[int, str, str]:
        if not self._connected or not self._client:
            if not self.connect():
                return 1, "", "Not connected to QNX target."
        try:
            stdin, stdout, stderr = self._client.exec_command(command, timeout=self.timeout)
            out_str = stdout.read().decode("utf-8", errors="replace")
            err_str = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()
            return exit_code, out_str, err_str
        except Exception as e:
            self._connected = False
            return 1, "", str(e)

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        if not self._connected or not self._client:
            if not self.connect():
                return False
        try:
            sftp = self._client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.chmod(remote_path, 0o755)
            sftp.close()
            return True
        except Exception:
            return False

    def is_connected(self) -> bool:
        return self._connected

    def close(self) -> None:
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._connected = False


class DemoExecutor(BaseExecutor):
    """
    Offline executor replaying captured QNX 8.0 telemetry from demo_snapshot.json.
    Supports simulated interactive actions (e.g., slay, on -p, restarting mock service).
    """

    def __init__(self, fixture_path: Optional[str] = None):
        if not fixture_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            fixture_path = os.path.join(base_dir, "fixtures", "demo_snapshot.json")

        self.fixture_path = fixture_path
        self._connected = True
        self.mock_service_killed = False
        self._load_fixtures()

    def _load_fixtures(self) -> None:
        if os.path.exists(self.fixture_path):
            with open(self.fixture_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {}

    def connect(self) -> bool:
        self._connected = True
        return True

    def exec_command(self, command: str) -> Tuple[int, str, str]:
        cmd = command.strip()

        # Handle slay command simulation
        if cmd.startswith("slay"):
            target = cmd.split()[-1]
            if target in {"1420", "mock_qnx_service.sh", "mock_qnx_service"}:
                self.mock_service_killed = True
                return 0, f"Process {target} terminated by slay signal.\n", ""
            elif target in {"1", "procnto", "procnto-smp-instr", "sshd"}:
                return 1, "", f"Operation not permitted: target {target} is protected by microkernel safety guard.\n"
            return 0, f"Process {target} terminated.\n", ""

        # Handle on -p priority launcher simulation / restart
        if "mock_qnx_service.sh" in cmd:
            self.mock_service_killed = False
            return 0, "Spawned /tmp/mock_qnx_service.sh with PID 1420 at priority 10r.\n", ""

        if "on -p" in cmd:
            match = re.search(r"on -p (\d+)([fr])\s+(.+)", cmd)
            if match:
                prio, pol, bin_name = match.groups()
                return 0, f"Spawned {bin_name} with PID 2048 under priority {prio}{pol}.\n", ""
            return 0, "Spawned process successfully.\n", ""

        # Thread & IPC query
        if "pidin -F" in cmd:
            raw = self.data.get("pidin_threads_raw", "")
            if self.mock_service_killed:
                # Filter out mock_qnx_service.sh
                lines = [l for l in raw.splitlines() if "mock_qnx_service.sh" not in l]
                raw = "\n".join(lines) + "\n"
            return 0, raw, ""

        # Mountpoint / fds query
        if "pidin fds" in cmd or "ls -l /dev" in cmd:
            raw = self.data.get("pidin_fds_raw", "")
            if self.mock_service_killed:
                lines = [l for l in raw.splitlines() if "mock_qnx_service.sh" not in l]
                raw = "\n".join(lines) + "\n"
            return 0, raw, ""

        # System info query
        if "pidin info" in cmd or cmd == "uptime" or cmd.startswith("free"):
            return 0, self.data.get("pidin_info_raw", ""), ""

        # Log stream query
        if "slog2info" in cmd:
            raw = self.data.get("slog2info_raw", "")
            if self.mock_service_killed:
                extra_log = "Nov 21 21:06:45.012 procnto.1                    SLOG2_WARNING  Process 1420 (mock_qnx_service.sh) terminated via slay -f; microkernel resilient.\n"
                raw = raw + extra_log
            return 0, raw, ""

        # Network endpoints
        if "sockstat" in cmd:
            return 0, self.data.get("sockstat_raw", ""), ""

        # CPU times
        if "pidin times" in cmd:
            return 0, self.data.get("pidin_times_raw", ""), ""

        # Process paths
        if "pidin ar" in cmd:
            return 0, self.data.get("pidin_ar_raw", ""), ""

        # Default fallback execution
        return 0, f"[DEMO] Executed '{cmd}' on mock QNX 8.0 target.\n", ""

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        # In demo mode, simulate successful upload
        return True

    def is_connected(self) -> bool:
        return self._connected

    def close(self) -> None:
        self._connected = False
