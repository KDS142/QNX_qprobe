# qnx-inspector

> **QNX Global Hackathon 2026** — *Developer Tooling & Host Tools Category*  
> Pure-Python host Terminal User Interface (TUI) for **QNX SDP 8.0** real-time microkernel telemetry, priority inversion detection, fault isolation sandboxing, and interactive Linux-to-QNX command translation.

---

## 🌟 Overview & Key Features

Developers transitioning from Linux to QNX face significant conceptual hurdles: microkernel message passing (`Receive`-`Send`-`Reply`), user-space resource managers, and real-time scheduling priority inversions. `qnx-inspector` bridges this gap with an intuitive, multi-pane terminal console:

- **Live Thread, IPC & Priority Inversion Monitor**: Polls `pidin` to track thread scheduling policies (FIFO/RR), priorities, and detect dangerous `REPLY` blocking chains where a high-priority thread is blocked on a low-priority server.
- **/dev Resource Manager Explorer & Fault Isolation Sandbox**: Maps `/dev` nodes to owning user-space servers and provides interactive fault injection demonstrating that crashing a service never impacts the `procnto` microkernel.
- **Structured System Log Stream**: Real-time severity-filtered log viewer for QNX's shared-memory logger (`slog2info`).
- **Interactive Linux-to-QNX Command Translator**: Real-time translation of familiar Linux habits (`ps aux`, `kill -9`, `lsof`, `dmesg`, `nice`) into native QNX equivalents with architectural microkernel explanations and safety guards.
- **Remote Priority Deployer & Snapshot Exporter**: SFTP upload + `on -p` priority launcher modal, plus `F5` Markdown/JSON diagnostic bundle export and offline `--demo` replay mode.

---

## 🏗️ Architecture & File Layout

```
qnx-inspector/
├── README.md               # Setup instructions, architecture overview, keybindings, demo guide
├── requirements.txt        # textual>=0.85.0, paramiko>=3.4.0, rich>=13.7.0, pytest>=7.4.0
├── qnx_inspector.py        # CLI entrypoint & Textual Application
├── core/
│   ├── models.py           # Dataclasses: ThreadRecord, InversionAlert, DevMount, LogEntry, etc.
│   ├── ssh_client.py       # Paramiko SSH/SFTP manager + DemoExecutor fallback
│   ├── collectors.py       # Telemetry parsers for pidin, pidin fds, pidin info, slog2info
│   ├── analyzer.py         # Priority Inversion and IPC blocking chain detection algorithm
│   ├── translator.py       # Rule-based Linux-to-QNX command engine (15+ commands & safety guards)
│   └── exporter.py         # F5 diagnostic report generator (Markdown & JSON)
├── ui/
│   ├── styles.tcss         # Textual CSS layout, alert banners, severity color tokens
│   └── modals.py           # DeployModal (Ctrl+D), ConfirmSlayModal, HelpModal (?)
├── scripts/
│   └── mock_qnx_service.sh # Safe dummy background script deployed to /tmp for fault-isolation demo
├── fixtures/
│   └── demo_snapshot.json  # Captured QNX 8.0 QEMU command outputs for offline --demo mode
└── tests/                  # Pytest test suite covering parsers, analyzer, translator, exporter
```

---

## ⚡ Quick Start

### 1. Host Installation (Python 3.11+)

```bash
# Clone the repository
git clone https://github.com/your-repo/QNX_qprobe.git
cd QNX_qprobe

# Create and activate virtual environment
python -m venv .venv
# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 2. Offline Demo Mode (Zero QEMU setup required!)

Launch offline replay mode to test the UI, priority inversion banner, translator, and fault isolation:

```bash
python qnx_inspector.py --demo
```

### 3. Connecting to Live QNX 8.0 Target (QEMU or Hardware)

```bash
python qnx_inspector.py --host localhost --port 2222 --user root --key ~/.ssh/id_ed25519
```

---

## ⌨️ Global Keybindings

| Key | Action | Description |
|---|---|---|
| `F1` | **Threads & IPC** | View sortable threads table, scheduling policies, and Priority Inversion Alert banner |
| `F2` | **/dev ResMgr** | Inspect `/dev` mountpoints and test Fault Isolation Sandbox |
| `F3` | **slog2 Logs** | Color-coded system log stream with severity filters (`ALL`, `WARNING+`, `ERROR`) |
| `/` | **Focus Translator** | Jump directly into the Linux-to-QNX command translation dock |
| `Ctrl+D` | **Deploy & Run** | Open modal to upload a binary via SFTP and launch under real-time priority (`on -p`) |
| `F5` | **Export Snapshot** | Generate diagnostic report bundle (`qnx_report_<timestamp>.md` and `.json`) |
| `?` | **Help** | Display keybindings cheatsheet and microkernel notes |
| `Ctrl+C` | **Quit** | Exit `qnx-inspector` |

---

## 🐧 Linux-to-QNX Command Bridge

| Linux Command | Translated QNX Command | Architectural Note |
|---|---|---|
| `ps aux` / `ps -ef` | `pidin -F "%a %b %N %p %J %M"` | QNX is thread-centric; `pidin` inspects threads and scheduling directly via `procnto`. |
| `top` / `htop` | `pidin times` | Displays per-thread CPU execution time and priority buckets without `/proc` overhead. |
| `kill -9 <pid>` | `slay -f <pid>` | `slay` terminates processes. **Safety Guard:** Warns/blocks PID <= 10 or `procnto`/`sshd`. |
| `killall <name>` | `slay <name>` | Signals or terminates all user-space processes matching `<name>`. |
| `lsof -p <pid>` | `pidin -p <pid> fds` | Lists open file descriptors mapped directly to Resource Manager channels. |
| `dmesg` | `slog2info -S` | Reads lock-free shared-memory structured logging buffers (`slog2`). |
| `nice -n <p> <cmd>` | `on -p <prio>f <cmd>` | Spawns a process with deterministic real-time priority (1–63) and FIFO policy. |
| `lsmod` / `systemctl` | `pidin ar` | Drivers and services run as standard user-space processes; no loadable kernel modules. |
| `free -h` | `pidin info` | Queries the microkernel directly for physical memory and CPU topology. |
| `netstat -tulnp` | `sockstat` | Inspects TCP/UDP sockets owned by QNX's user-space networking stack (`io-sock`). |

---

## 🧪 Running Unit Tests

Run the complete automated test suite verifying collectors, parser schemas, priority inversion detection, translator safety guards, and report exporters:

```bash
pytest -v
```

---

## 🎯 2-Minute Hackathon Demo Script

1. **0:00–0:25 (Live Connection)**: Launch `python qnx_inspector.py --demo` (or `--host localhost --port 2222`). Highlight live `pidin` threads, CPU cores, and kernel memory metrics in the header status bar.
2. **0:25–0:55 (Linux-to-QNX Bridge)**: Press `/` and type `ps aux`, `lsof -p 1`, and `kill -9 1`. Show the live architectural translation explanation and safety guard warning blocking termination of PID 1 (`procnto`).
3. **0:55–1:30 (Real-Time Determinism & Priority Inversion)**: Point to the prominent red **Priority Inversion Alert Banner** in Tab 1 (`F1`), showing client `telemetry_collector` (prio 25f) REPLY-blocked on `sensor_aggregator` (prio 10r). Press `Ctrl+D` to show the real-time priority deployer (`on -p`).
4. **1:30–2:00 (Microkernel Fault Isolation & Diagnostic Export)**: Switch to Tab 2 (`F2`), click "Inject Fault (Kill Service)" to terminate `mock_qnx_service.sh`, demonstrating that the user-space service terminates while `procnto` remains completely unaffected. Switch to Tab 3 (`F3`) to see the termination logged in `slog2info`, and press `F5` to export the complete diagnostic snapshot markdown and JSON bundle.

---

## 📄 License
Apache-2.0 / MIT License.
