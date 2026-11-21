# Devpost Submission: qprobe

**Repository:** [https://github.com/your-username/QNX_qprobe](https://github.com/your-username/QNX_qprobe)  
**Track:** Developer Tooling & Host Tools  
**Tagline:** Real-time microkernel telemetry, priority inversion detection, and Linux-to-QNX command translator for QNX SDP 8.0 targets.

---

## 💡 Inspiration

With BlackBerry QNX's launch of **QNX Everywhere** and **QNX SDP 8.0**, thousands of embedded Linux developers are evaluating the microkernel for automotive, robotics, and safety-critical real-time systems. However, developers moving from Linux encounter significant friction:

1. **Microkernel Architectural Shift**: Linux developers expect monolithic kernel abstractions (everything in `/proc` or `dmesg`). In QNX, drivers and filesystems run as user-space Resource Managers, while logging is handled by lock-free shared-memory ring buffers (`slog2`).
2. **Deterministic Priority Inversions**: In hard real-time systems, an unnoticed `REPLY` block where a high-priority thread waits on a lower-priority server can introduce catastrophic deadline jitter.
3. **Tooling Fragment**: Navigating dense CLI flags (`pidin -F "%a %b %N %p %J %B"`, `slog2info -S`, `on -p 25f`) across raw SSH shells is tedious and error-prone.

We built **qprobe** to give developers an intuitive, modern terminal console that translates familiar Linux intuitions into native QNX 8.0 primitives while visualizing real-time microkernel health.

---

## ⚡ What qprobe Does

`qprobe` is a pure-Python host Terminal User Interface (TUI) connecting over SSH/SFTP to QNX SDP 8.0 targets (or running offline via `--demo` fixtures):

- **Live Thread, IPC & Priority Inversion Monitor (F1)**: Continuously polls `pidin` to track thread scheduling policies (FIFO/Round-Robin), priorities, and detect dangerous `REPLY` blocking chains. Automatically highlights client-server priority inversion pairs and traces multi-hop transitive chains.
- **/dev Resource Manager Explorer & Fault Isolation Sandbox (F2)**: Maps `/dev` nodes to user-space server PIDs. Features an interactive Fault Isolation Sandbox allowing engineers to terminate and restart services (e.g., `mock_qnx_service.sh`) to observe that `procnto` remains completely unaffected.
- **Structured System Log Stream (F3)**: Real-time, severity-filtered (`ALL`, `WARNING+`, `ERROR`) log viewer for QNX's `slog2info` system with automatic deduplication across poll intervals.
- **Interactive Linux-to-QNX Command Translator (Dock)**: An always-accessible command bar (`/`) with 17 regex mappings. Typing `ps aux`, `kill -9`, `lsof -p 1`, or `dmesg` displays the native QNX equivalent and microkernel architectural explanations, backed by safety guards that block termination of critical PIDs ($\le 10$, `procnto`, `sshd`).
- **Remote Priority Deployer (Ctrl+D) & Snapshot Exporter (F5)**: SFTP upload and `on -p` priority launcher modal, plus instant generation of diagnostic bundles (`qnx_report_<timestamp>.md` and `.json`).
- **Offline Demo Mode (`--demo`)**: Replays captured QNX 8.0 QEMU telemetry fixtures with full simulation of commands, service restarts, and priority inversions without needing external hardware.

---

## 🛠️ How We Built It

- **Host Stack**: Python 3.11+, Textual (async terminal UI framework), Rich (formatting), Paramiko (persistent SSH/SFTP).
- **Target Runtime**: QNX SDP 8.0 x86_64 QEMU target using QNX Everywhere.
- **Architecture**:
  - `core/ssh_client.py`: Persistent SSH transport with automatic reconnect and `DemoExecutor` mock fallback.
  - `core/collectors.py`: Robust parsers for `pidin`, `pidin fds`, `pidin info`, and `slog2info -S`.
  - `core/analyzer.py`: 4-step priority inversion algorithm with transitive cycle-safe chain tracing.
  - `core/translator.py`: 17 Linux-to-QNX command mappings with dangerous-target safety guards.
  - `core/exporter.py`: F5 Markdown/JSON diagnostic snapshot exporter.
  - `ui/styles.tcss` & `ui/modals.py`: High-contrast layout, modals, and severity color tokens.
  - `qnx_inspector.py`: Main Textual application with non-blocking async execution.
  - `scripts/demo_walkthrough.py`: Automated 2-minute hackathon video flow.
- **Quality Assurance**: 13 automated Pytest unit and integration tests covering parser edge cases, priority inversion detection, translator safety guards, and report exporters.

---

## 🔍 Explicit QNX 8.0 Integration Evidence

| Module & Function | Exact QNX 8.0 Command | Domain Logic & Role |
|---|---|---|
| `core/collectors.py:parse_pidin_threads` | `pidin -F "%a %b %N %p %J %B"` | Extracts PID, TID, name, priority, scheduling policy (FIFO/RR), and blocked-on state |
| `core/collectors.py:parse_pidin_fds` | `pidin fds` & `ls -l /dev` | Maps `/dev` mountpoint markers (`MP`) to user-space Resource Manager PIDs |
| `core/collectors.py:parse_pidin_info` | `pidin info` | Parses QNX 8.0 kernel version, CPU topology, and physical RAM |
| `core/collectors.py:parse_slog2info` | `slog2info -S` | Streams QNX shared-memory structured log buffers with deduplication |
| `core/analyzer.py:detect_priority_inversions` | Algorithm | Detects `REPLY` blocks where client priority > server highest active priority |
| `core/translator.py:translate_linux_command` | Rule Engine | Maps Linux commands to `pidin`, `slay`, `slog2info`, `on -p`, `sockstat`, etc. |
| `ui/modals.py:DeployModal` | `on -p <prio><f\|r> /tmp/<file> &` | SFTP uploads and spawns tasks with deterministic real-time priority |

---

## 🏆 Accomplishments That We're Proud Of

1. **Transitive Inversion Resolution**: We did not stop at single-hop priority inversions; our analyzer traces multi-hop blocking chains ($A \rightarrow B \rightarrow C$) with cycle prevention.
2. **Interactive TUI Responsiveness**: All remote executions and file transfers are offloaded via `asyncio.to_thread`, ensuring the TUI never stutters during slow network calls.
3. **Zero-Setup Demonstration**: Anyone can run `python qnx_inspector.py --demo` and immediately experience a realistic QNX 8.0 debugging session with zero external setup.
4. **Comprehensive Documentation & Codelab**: Authored [CODELAB.md](CODELAB.md) — a complete hands-on tutorial titled *"From Linux to QNX 8.0 Microkernel Inspection with qprobe"*.

---

## 🚀 How to Run

### Installation
```bash
git clone https://github.com/your-username/QNX_qprobe.git
cd QNX_qprobe
python -m venv .venv
# On Windows:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### Run Offline Demo Mode (Instant Evaluation)
```bash
python qnx_inspector.py --demo
```

### Run Against Live QNX 8.0 QEMU Target
```bash
python qnx_inspector.py --host localhost --port 2222 --user root --key ~/.ssh/id_ed25519
```

### Run Automated 2-Minute Demo Walkthrough
```bash
python scripts/demo_walkthrough.py
```

### Run Test Suite
```bash
pytest -v
```
