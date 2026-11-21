"""Unit tests for collectors, parser schemas, and priority inversion detection."""
import json
import os
import pytest
from core.models import ThreadRecord, InversionAlert, DevMount, LogEntry, SystemInfo
from core.collectors import (
    parse_pidin_threads,
    parse_pidin_fds,
    parse_pidin_info,
    parse_slog2info,
)
from core.analyzer import detect_priority_inversions, extract_server_pid


@pytest.fixture
def sample_snapshot():
    fixture_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "fixtures",
        "demo_snapshot.json",
    )
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_pidin_threads(sample_snapshot):
    raw = sample_snapshot["pidin_threads_raw"]
    threads = parse_pidin_threads(raw)
    assert len(threads) > 0

    # Validate procnto
    procnto = next(t for t in threads if t.pid == 1 and t.tid == 1)
    assert procnto.name == "procnto-smp-instr"
    assert procnto.priority == 255
    assert procnto.policy == "FIFO"

    # Validate high-priority client
    client = next(t for t in threads if t.pid == 1500)
    assert client.name == "telemetry_collector"
    assert client.priority == 25
    assert client.policy == "FIFO"
    assert client.state == "REPLY"
    assert client.blocked_on == "1200"

    # Validate low-priority server
    server = next(t for t in threads if t.pid == 1200)
    assert server.name == "sensor_aggregator"
    assert server.priority == 10
    assert server.policy == "RR"


def test_priority_inversion_detection(sample_snapshot):
    threads = parse_pidin_threads(sample_snapshot["pidin_threads_raw"])
    alerts = detect_priority_inversions(threads)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.client_pid == 1500
    assert alert.client_name == "telemetry_collector"
    assert alert.client_priority == 25
    assert alert.server_pid == 1200
    assert alert.server_name == "sensor_aggregator"
    assert alert.server_priority == 10
    assert alert.severity == "CRITICAL"
    assert len(alert.chain) == 2
    assert "telemetry_collector" in alert.chain[0]
    assert "sensor_aggregator" in alert.chain[1]


def test_transitive_priority_inversion_chain():
    # Multi-hop transitive inversion: Thread A (30f) -> Server B (20r) -> Server C (10r)
    threads = [
        ThreadRecord(
            pid=100,
            tid=1,
            name="client_app",
            priority=30,
            policy="FIFO",
            priority_raw="30f",
            state="REPLY",
            blocked_on="200",
        ),
        ThreadRecord(
            pid=200,
            tid=1,
            name="intermediate_service",
            priority=20,
            policy="RR",
            priority_raw="20r",
            state="REPLY",
            blocked_on="300",
        ),
        ThreadRecord(
            pid=300,
            tid=1,
            name="backend_driver",
            priority=10,
            policy="RR",
            priority_raw="10r",
            state="RUNNING",
        ),
    ]

    alerts = detect_priority_inversions(threads)
    assert len(alerts) >= 1

    # First alert should trace the full 3-hop chain
    top_alert = next(a for a in alerts if a.client_pid == 100)
    assert top_alert.client_priority == 30
    assert top_alert.server_priority == 20
    assert len(top_alert.chain) == 3
    assert "client_app" in top_alert.chain[0]
    assert "intermediate_service" in top_alert.chain[1]
    assert "backend_driver" in top_alert.chain[2]


def test_extract_server_pid():
    assert extract_server_pid("1200") == 1200
    assert extract_server_pid("12290-1") == 12290
    assert extract_server_pid("5") == 5
    assert extract_server_pid("") is None
    assert extract_server_pid("invalid") is None


def test_parse_pidin_fds(sample_snapshot):
    raw = sample_snapshot["pidin_fds_raw"]
    mounts = parse_pidin_fds(raw)
    assert len(mounts) > 0

    dev_paths = [m.device_path for m in mounts]
    assert "/dev/shmem" in dev_paths
    assert "/dev/io-sock" in dev_paths
    assert "/dev/sensor_agg" in dev_paths
    assert "/dev/mock_service" in dev_paths


def test_parse_pidin_info(sample_snapshot):
    raw = sample_snapshot["pidin_info_raw"]
    info = parse_pidin_info(raw)

    assert info.cores == 4
    assert info.arch == "x86_64"
    assert info.total_ram_mb == 4096
    assert info.free_ram_mb == 3120
    assert "QNX 8.0.0" in info.os_version


def test_parse_slog2info(sample_snapshot):
    raw = sample_snapshot["slog2info_raw"]
    seen = set()
    logs = parse_slog2info(raw, seen)
    assert len(logs) >= 5

    severities = {l.severity for l in logs}
    assert "SLOG2_INFO" in severities
    assert "SLOG2_WARNING" in severities
    assert "SLOG2_ERROR" in severities

    # Test deduplication
    logs_second_run = parse_slog2info(raw, seen)
    assert len(logs_second_run) == 0
