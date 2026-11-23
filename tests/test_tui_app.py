"""Component and integration tests for QNXInspector app logic in demo mode."""
import os
import tempfile
from core.ssh_client import DemoExecutor
from qnx_inspector import QNXInspector


def test_qnx_inspector_telemetry_flow():
    executor = DemoExecutor()
    app = QNXInspector(
        executor=executor,
        is_demo=True,
        host_label="DEMO MODE",
        enable_polling=False,
    )

    # Verify executor connect
    assert app.executor.connect() is True

    # Test telemetry refresh
    app.refresh_telemetry()

    # 1. System Info
    assert app.system_info.cores == 4
    assert app.system_info.arch == "x86_64"
    assert app.system_info.total_ram_mb == 4096

    # 2. Threads and Priority Inversion Alert
    assert len(app.threads) > 0
    assert len(app.alerts) == 1
    alert = app.alerts[0]
    assert alert.client_pid == 1500
    assert alert.client_priority == 25
    assert alert.server_pid == 1200
    assert alert.server_priority == 10

    # 3. Dev mounts
    assert len(app.dev_mounts) > 0
    dev_paths = [m.device_path for m in app.dev_mounts]
    assert "/dev/shmem" in dev_paths
    assert "/dev/io-sock" in dev_paths

    # 4. Logs
    assert len(app.logs) >= 5

    # 5. Fault isolation simulation
    # Simulate killing mock service
    code, out, err = app.executor.exec_command("slay -f mock_qnx_service.sh")
    assert code == 0
    app.refresh_telemetry()

    # Verify mock_qnx_service.sh is no longer in active threads
    active_names = [t.name for t in app.threads]
    assert "mock_qnx_service.sh" not in active_names

    # But procnto remains healthy!
    assert "procnto-smp-instr" in active_names

    # Respawn service
    code, out, err = app.executor.exec_command("on -p 10r /tmp/mock_qnx_service.sh &")
    assert code == 0
    app.refresh_telemetry()
    active_names_after_respawn = [t.name for t in app.threads]
    assert "mock_qnx_service.sh" in active_names_after_respawn

    # 6. Test F5 Export Snapshot
    with tempfile.TemporaryDirectory() as tmpdir:
        from core.exporter import export_diagnostic_snapshot
        md_path, json_path = export_diagnostic_snapshot(
            app.system_info,
            app.threads,
            app.alerts,
            app.dev_mounts,
            app.logs,
            output_dir=tmpdir,
        )
        assert os.path.exists(md_path)
        assert os.path.exists(json_path)
