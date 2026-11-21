"""Unit tests for F5 diagnostic report exporter."""
import json
import os
import tempfile
from core.models import ThreadRecord, InversionAlert, DevMount, LogEntry, SystemInfo
from core.exporter import export_diagnostic_snapshot, generate_markdown_report


def test_markdown_and_json_export():
    sys_info = SystemInfo(
        os_version="QNX 8.0.0",
        arch="x86_64",
        cores=4,
        total_ram_mb=4096,
        free_ram_mb=3120,
        boot_time="2026-11-21 21:00:15",
    )

    threads = [
        ThreadRecord(
            pid=1,
            tid=1,
            name="procnto-smp-instr",
            priority=255,
            policy="FIFO",
            priority_raw="255f",
            state="READY",
        ),
        ThreadRecord(
            pid=1500,
            tid=1,
            name="telemetry_collector",
            priority=25,
            policy="FIFO",
            priority_raw="25f",
            state="REPLY",
            blocked_on="1200",
        ),
    ]

    alerts = [
        InversionAlert(
            client_pid=1500,
            client_tid=1,
            client_name="telemetry_collector",
            client_priority=25,
            server_pid=1200,
            server_name="sensor_aggregator",
            server_priority=10,
            severity="CRITICAL",
        )
    ]

    dev_mounts = [
        DevMount(
            device_path="/dev/io-sock",
            server_pid=1042,
            server_name="io-sock",
            mount_type="MP",
        )
    ]

    logs = [
        LogEntry(
            timestamp="Nov 21 21:00:15.102",
            buffer="procnto.1",
            severity="SLOG2_INFO",
            message="Kernel ready",
        )
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        md_path, json_path = export_diagnostic_snapshot(
            sys_info, threads, alerts, dev_mounts, logs, output_dir=tmpdir
        )

        assert os.path.exists(md_path)
        assert os.path.exists(json_path)

        # Validate Markdown content
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
            assert "QNX 8.0 System Diagnostic Snapshot" in md_text
            assert "Priority Inversion & IPC Blocking Analysis" in md_text
            assert "telemetry_collector" in md_text
            assert "sensor_aggregator" in md_text
            assert "4096 MB" in md_text

        # Validate JSON content
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "system_info" in data
            assert len(data["inversion_alerts"]) == 1
            assert data["inversion_alerts"][0]["client_name"] == "telemetry_collector"
            assert len(data["threads"]) == 2
            assert len(data["dev_mounts"]) == 1
            assert len(data["logs"]) == 1
