# From Linux to QNX 8.0 Microkernel Inspection with qprobe

> **QNX Global Hackathon 2026 Codelab**  
> *A Hands-On Developer Guide for Transitioning from Linux to the QNX SDP 8.0 Real-Time Microkernel.*

---

## 🧭 Overview & Learning Objectives

When seasoned Linux developers first encounter the **QNX 8.0 Microkernel**, standard assumptions about operating systems no longer apply:

1. **No Monolithic Kernel Code Bloat**: In Linux, device drivers, network stacks, and file systems live in kernel space (Ring 0). In QNX, only thread scheduling, message passing, and timer management live in `procnto`. Everything else runs as unprivileged user-space processes (Ring 3).
2. **Synchronous IPC Primitive (`Send`/`Receive`/`Reply`)**: Instead of asynchronous pipes and sockets, QNX threads communicate via deterministic rendezvous message passing.
3. **Strict Real-Time Scheduling**: Thread priorities range from `1` to `63` (with `64–255` for high-priority kernel tasks). Scheduling policies like **FIFO** (`f`) run without time-slicing until the thread yields or blocks.

In this codelab, you will learn how to inspect, debug, and monitor a QNX 8.0 system using **qprobe**, bridging the gap between familiar Linux habits and native QNX tools.

---

## 📋 Prerequisites

- **Host Machine**: Windows 11 / Linux (Ubuntu 22.04/24.04) / macOS
- **Python**: Version **3.11** or newer
- **Target**: QNX SDP 8.0 x86_64 QEMU virtual target (or offline `--demo` replay mode)

---

## 🛠️ Step 1: Setting Up QNX SDP 8.0 in QEMU

If you have access to a Linux host or WSL2, you can boot a live QNX 8.0 target using the free **QNX Everywhere** license:

1. Activate your license at [qnx.com/getqnx](https://www.qnx.com/getqnx) and install the **QNX Software Center**.
2. Generate an SSH keypair:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
   ```
3. Source the QNX environment and generate a QEMU image:
   ```bash
   source ~/qnx800/qnxsdp-env.sh
   mkdir -p ~/qnxvm && cd ~/qnxvm
   mkqnximage --type=qemu --arch=x86_64 --ssh-ident=$HOME/.ssh/id_ed25519.pub --build
   ```
4. Boot the QEMU machine:
   ```bash
   ./run.sh
   ```
5. In the QEMU console, if passwordless SSH requires disabling PAM:
   ```sh
   sshd -o UsePAM=no
   ```
6. From your host, test connectivity:
   ```bash
   ssh -p 2222 -i ~/.ssh/id_ed25519 root@localhost "pidin info"
   ```

*(Note: If you do not have QEMU or a QNX license right now, you can complete every step of this codelab using `qprobe --demo`!)*

---

## 🚀 Step 2: Installing and Launching qprobe

1. Clone the repository and configure your Python environment:
   ```bash
   git clone https://github.com/your-username/QNX_qprobe.git
   cd QNX_qprobe

   python -m venv .venv
   # Windows:
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

2. Launch `qprobe`:
   - **For Live QEMU**:
     ```bash
     python qnx_inspector.py --host localhost --port 2222 --user root
     ```
   - **For Offline Demo Replay**:
     ```bash
     python qnx_inspector.py --demo
     ```

Observe the top status bar: It displays the target OS version, architecture, CPU core count, RAM utilization, and active thread count.

---

## 🔄 Step 3: Translating Linux Habits to QNX Primitives

In Linux, you rely on `/proc`, `ps`, `kill`, and `dmesg`. Press `/` in `qprobe` to jump into the bottom Command Translator dock and try these commands:

### Exercise 3.1: Process & Thread Inspection
- **Type**: `ps aux`
- **QNX Translation**: `pidin -F "%a %b %N %p %J %M"`
- **Why?**: Linux treats threads as tasks sharing memory; QNX is fundamentally thread-centric. `pidin` directly queries `procnto` for thread priorities (`%p`), blocking states (`%J`), and memory segments (`%M`).

### Exercise 3.2: Process Termination & Safety Guards
- **Type**: `kill -9 1`
- **QNX Translation**: `slay -f 1`
- **Notice the Safety Guard**: In Linux, PID 1 is `systemd`/`init`. In QNX, PID 1 is `procnto` (the microkernel itself!). `qprobe` detects PID $\le 10$ and displays an urgent red safety warning, preventing accidental kernel death.
- **Type**: `kill 1420` (or `slay 1420`) to safely terminate standard user-space programs.

### Exercise 3.3: Inspecting Open File Descriptors
- **Type**: `lsof -p 1`
- **QNX Translation**: `pidin -p 1 fds`
- **Why?**: In QNX, open files are not simple kernel VFS entries; they are message-passing connections to user-space Resource Managers (like `/dev/shmem` or `/dev/io-sock`).

### Exercise 3.4: Reading System Logs
- **Type**: `dmesg`
- **QNX Translation**: `slog2info -S`
- **Why?**: QNX does not have a kernel ring buffer. Instead, it utilizes `slogger2`, a lock-free shared-memory structured logging daemon that isolates process log buffers.

---

## ⚠️ Step 4: Diagnosing Real-Time Priority Inversions

Priority inversion is one of the most dangerous bugs in real-time systems (it famously crippled the Mars Pathfinder spacecraft in 1997).

### How it happens in QNX:
1. Thread **A** (High Priority, e.g., `25f`) sends a message (`MsgSend`) to Server **B** (Low Priority, e.g., `10r`).
2. Thread **A** enters the **`REPLY`** state, blocking until Server **B** finishes processing and replies (`MsgReply`).
3. If Server **B** does not boost its priority (via priority inheritance), medium-priority threads (`15r`) can preempt Server **B**, starving Thread **A**!

### Observing it in qprobe:
1. Press `F1` to view **Tab 1: Threads & IPC**.
2. Notice the prominent red **CRITICAL PRIORITY INVERSION DETECTED** banner.
3. Client thread `telemetry_collector` (PID 1500, Priority `25f`) is in state `REPLY` blocked on `sensor_aggregator` (PID 1200, Priority `10r`).
4. Click the table header **Priority** to sort threads descending and inspect the affected rows.
5. Notice that `qprobe` automatically highlights:
   - High-priority client row in **bold red**.
   - Low-priority blocking server in **bold yellow**.

---

## 🛡️ Step 5: Testing Microkernel Fault Isolation

In Linux, a bug or crash in a graphics driver or network stack causes a **Kernel Panic**, freezing the entire machine. In QNX, drivers run in user-space memory partitions.

### Hands-on Test:
1. Press `F2` to switch to **Tab 2: /dev Resource Managers**.
2. The left pane shows `/dev` nodes mapped to user-space server PIDs (`/dev/io-sock`, `/dev/ser1`, `/dev/mock_service`).
3. In the right pane (**Fault Isolation Sandbox**), click **"Inject Fault (Kill Service)"**.
4. Observe the results:
   - `mock_qnx_service.sh` is immediately terminated.
   - The device node `/dev/mock_service` disappears.
   - Look at the `procnto` health indicator: **HEALTHY | Uptime Unaffected | Memory Stable**.
   - The microkernel did not stutter or crash.
5. Press `F3` to switch to **Tab 3: slog2info Logs**:
   - Filter by `WARNING+` or `ERROR`.
   - See the termination logged by `procnto` in real-time.
6. Switch back to `F2` and click **"Respawn Service"** to restore normal operation.

---

## 📦 Step 6: Deploying Real-Time Tasks & Exporting Diagnostics

1. Press `Ctrl+D` to open the **Remote Priority Deployer** modal:
   - File Path: `scripts/mock_qnx_service.sh`
   - Real-Time Priority: `25`
   - Scheduling Policy: `FIFO`
   - Click **Deploy & Launch**.
   - `qprobe` uploads the binary to `/tmp` via SFTP and launches it using `on -p 25f /tmp/mock_qnx_service.sh &`.
2. Press `F5` to generate a diagnostic snapshot bundle:
   - `qprobe` exports:
     - `qnx_report_<timestamp>.md`: Formatted Markdown report with GitHub alert badges and thread tables.
     - `qnx_report_<timestamp>.json`: Complete JSON bundle containing all system telemetry.

---

## 🎓 Conclusion & Next Steps

Congratulations! You have mastered the fundamentals of the QNX 8.0 microkernel architecture:
- Navigating user-space drivers vs monolithic modules.
- Translating common Linux utilities to native `pidin`, `slay`, and `slog2info` commands.
- Pinpointing real-time priority inversions and transitive blocking chains.
- Demonstrating microkernel resilience through user-space fault isolation.

Explore the codebase under [`core/`](file:///c:/CODING/VACATION%20PYTHON%20PRACTICE/Website%20dost/QNX_qprobe/core) to see how Paramiko, Textual, and regex parsers combine to deliver an enterprise-grade host tool for QNX developers.
