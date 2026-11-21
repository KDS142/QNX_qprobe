# qprobe (QNX_qprobe)

> **QNX Global Hackathon 2026** — *Developer Tooling & Host Tools Category*  
> Pure-Python host Terminal User Interface (TUI) for **QNX SDP 8.0** real-time microkernel telemetry, transitive priority inversion detection, user-space fault isolation sandboxing, and interactive Linux-to-QNX command translation.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Target](https://img.shields.io/badge/QNX-SDP_8.0_(x86__64_QEMU)-red.svg)](https://www.qnx.com/getqnx)
[![Python](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://www.python.org/)
[![UI](https://img.shields.io/badge/TUI-Textual_&_Rich-purple.svg)](https://textual.textualize.io/)

---

## 🌟 Overview & Core Value Proposition

Developers transitioning from Linux to the QNX 8.0 real-time microkernel face a steep learning curve: microkernel message passing (`Receive`-`Send`-`Reply`), user-space resource managers running drivers, and deterministic real-time scheduling priority inversions. 

**qprobe** bridges this onboarding and debugging gap with a high-performance terminal console:

- **Live Thread, IPC & Priority Inversion Monitor**: Polls `pidin` to track thread scheduling policies (FIFO/RR), priorities, and detects dangerous `REPLY` blocking chains where a high-priority thread is blocked on a low-priority server.
- **/dev Resource Manager Explorer & Fault Isolation Sandbox**: Maps `/dev` nodes to owning user-space servers and provides interactive fault injection demonstrating that terminating or crashing a service never impacts the core `procnto` microkernel.
- **Structured System Log Stream**: Real-time severity-filtered log viewer for QNX's shared-memory logger (`slog2info`) with automated poll-cycle deduplication.
- **Interactive Linux-to-QNX Command Translator**: Real-time translation of familiar Linux habits (`ps aux`, `kill -9`, `lsof`, `dmesg`, `nice`) into native QNX equivalents with architectural microkernel explanations and safety guards blocking dangerous PID termination.
- **Remote Priority Deployer & Snapshot Exporter**: SFTP upload + `on -p` priority launcher modal, plus `F5` Markdown/JSON diagnostic bundle export and offline `--demo` replay mode.

---

## 🗺️ QNX 8.0 Integration Architecture

```
QNX_qprobe/
├── README.md                  # Setup instructions, architecture overview, keybindings, demo guide
├── CODELAB.md                 # Beginner tutorial: "From Linux to QNX 8.0 Microkernel Inspection"
├── DEVPOST_SUBMISSION.md      # Submission copy for Developer Tooling & Host Tools category
├── requirements.txt           # textual>=0.85.0, paramiko>=3.4.0, rich>=13.7.0, pytest>=7.4.0
├── pytest.ini                 # Test discovery and pythonpath configuration
├── LICENSE                    # Apache 2.0 Open Source License
├── qnx_inspector.py           # CLI entrypoint & Textual Application (Launch: python qnx_inspector.py)
├── core/
│   ├── models.py              # Dataclasses: ThreadRecord, InversionAlert, DevMount, LogEntry, etc.
│   ├── ssh_client.py          # Persistent Paramiko SSH/SFTP manager + DemoExecutor fallback + auto-reconnect
│   ├── collectors.py          # QNX 8.0 telemetry parsers for pidin, pidin fds, pidin info, slog2info
│   ├── analyzer.py            # Transitive REPLY blocking chains and priority inversion detection
│   ├── translator.py          # Rule-based Linux-to-QNX command engine (17 commands & safety guards)
│   └── exporter.py            # F5 diagnostic report generator (Markdown & JSON)
├── ui/
│   ├── styles.tcss            # Textual CSS layout, alert banners, severity color tokens
│   └── modals.py              # DeployModal (Ctrl+D), ConfirmSlayModal, HelpModal (?)
├── scripts/
│   ├── mock_qnx_service.sh    # Safe dummy background script deployed to /tmp for fault-isolation demo
│   └── demo_walkthrough.py    # Automated 2-minute hackathon demo video walkthrough
├── fixtures/
│   └── demo_snapshot.json     # Captured QNX 8.0 QEMU command outputs for offline --demo mode
└── tests/                     # 13 automated Pytest unit and integration tests
```

### Direct Module Pointers
- **Transport Layer**: [`core/ssh_client.py`](file:///c:/CODING/VACATION%20PYTHON%20PRACTICE/Website%20dost/QNX_qprobe/core/ssh_client.py)
- **Telemetry Parsers**: [`core/collectors.py`](file:///c:/CODING/VACATION%20PYTHON%20PRACTICE/Website%20dost/QNX_qprobe/core/collectors.py)
- **Priority Inversion Analyzer**: [`core/analyzer.py`](file:///c:/CODING/VACATION%20PYTHON%20PRACTICE/Website%20dost/QNX_qprobe/core/analyzer.py)
- **Command Translator**: [`core/translator.py`](file:///c:/CODING/VACATION%20PYTHON%20PRACTICE/Website%20dost/QNX_qprobe/core/translator.py)
- **Diagnostic Exporter**: [`core/exporter.py`](file:///c:/CODING/VACATION%20PYTHON%20PRACTICE/Website%20dost/QNX_qprobe/core/exporter.py)

---

## ⚡ Host Setup & Run Commands

### 1. Requirements
- Host OS: Windows, Linux, or macOS
- Python: **3.11+**
- Target: **QNX SDP 8.0 (QNX Everywhere)** on an `x86_64` QEMU virtual target (or offline `--demo` mode)

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/your-username/QNX_qprobe.git
cd QNX_qprobe

# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Launching qprobe

#### Offline Preview (--demo mode)
Run without any QEMU or network setup:
```bash
python qnx_inspector.py --demo
```

#### Live Connection to QNX SDP 8.0 QEMU Target
```bash
python qnx_inspector.py --host localhost --port 2222 --user root --key ~/.ssh/id_ed25519
```

CLI options:
- `--host`: Target IP or hostname (default: `localhost`)
- `--port`: SSH port (default: `2222`)
- `--user`: SSH user (default: `root`)
- `--key`: Path to SSH private key (default: `None`, tries default `~/.ssh/id_ed25519`)
- `--password`: SSH password (default: `None`)
- `--demo`: Replay captured QNX 8.0 fixtures offline

---

## 🖥️ Target Environment Prerequisites (QNX 8.0 QEMU)

To run against a live QNX 8.0 QEMU target using QNX Everywhere:

1. **Get QNX Everywhere**: Activate the free non-commercial license at [qnx.com/getqnx](https://www.qnx.com/getqnx) and install QNX SDP 8.0 via QNX Software Center into `~/qnx800`.
2. **Generate SSH Key & Build Image**:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
   source ~/qnx800/qnxsdp-env.sh
   mkdir -p ~/qnxvm && cd ~/qnxvm
   mkqnximage --type=qemu --arch=x86_64 --ssh-ident=$HOME/.ssh/id_ed25519.pub --build
   ```
3. **Boot Target & Verify SSH**:
   ```bash
   ./run.sh
   # Inside QEMU console, if PAM is active on stock image:
   sshd -o UsePAM=no
   # Verify connection from host:
   ssh -p 2222 -i ~/.ssh/id_ed25519 root@localhost "pidin info"
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
| `Ctrl+C` | **Quit** | Exit `qprobe` |

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
| `pstree` | `pidin tree` | Displays process/thread hierarchy tree from `procnto`. |
| `renice <p> -p <pid>` | `on -p <prio> -P <pid>` | Dynamically alters priority of a running process or thread. |
| `vmstat` | `pidin mem` | Queries virtual memory segments and allocations per process. |
| `ifconfig` / `ip addr`| `ifconfig` | Inspects network interfaces configured in user-space `io-sock`. |

---

## 🧪 Automated Testing

Run the test suite covering telemetry parsing, transitive priority inversion chains, translator safety guards, and report exports:

```bash
pytest -v
```

All 13 tests execute and pass out-of-the-box.

---

## 🎯 2-Minute Hackathon Demo Script

Run the automated CLI demo script:
```bash
python scripts/demo_walkthrough.py
```

### Video Presentation Flow:
1. **0:00–0:25 (Live Connection)**: Launch `python qnx_inspector.py --host localhost --port 2222` (or `--demo`). Highlight live `pidin` threads, CPU cores, and kernel memory metrics in the header status bar.
2. **0:25–0:55 (Linux-to-QNX Bridge)**: Press `/` and type `ps aux`, `lsof -p 1`, and `kill -9 1`. Show the live architectural translation explanation and safety guard warning blocking termination of PID 1 (`procnto`).
3. **0:55–1:30 (Real-Time Determinism & Priority Inversion)**: Point to the prominent red **Priority Inversion Alert Banner** in Tab 1 (`F1`), showing client `telemetry_collector` (prio 25f) REPLY-blocked on `sensor_aggregator` (prio 10r). Press `Ctrl+D` to show the real-time priority deployer (`on -p`).
4. **1:30–2:00 (Microkernel Fault Isolation & Diagnostic Export)**: Switch to Tab 2 (`F2`), click "Inject Fault (Kill Service)" to terminate `mock_qnx_service.sh`, demonstrating that the user-space service terminates while `procnto` remains completely unaffected. Switch to Tab 3 (`F3`) to see the termination logged in `slog2info`, and press `F5` to export the complete diagnostic snapshot markdown and JSON bundle.

---

## 📄 License
Licensed under the [Apache License, Version 2.0](LICENSE).
