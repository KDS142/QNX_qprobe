"""Unit tests for the Linux-to-QNX translator engine and safety guards."""
import pytest
from core.translator import translate_linux_command, is_protected_target


def test_translation_mappings():
    # 1. ps aux
    res = translate_linux_command("ps aux")
    assert res.qnx_cmd == 'pidin -F "%a %b %N %p %J %M"'
    assert "procnto" in res.explanation

    # 2. top
    res = translate_linux_command("top")
    assert res.qnx_cmd == "pidin times"

    # 3. kill -9
    res = translate_linux_command("kill -9 1200")
    assert res.qnx_cmd == "slay -f 1200"
    assert res.requires_confirm is True
    assert res.is_dangerous is False

    # 4. kill (SIGTERM)
    res = translate_linux_command("kill 1420")
    assert res.qnx_cmd == "slay 1420"

    # 5. killall
    res = translate_linux_command("killall sensor_aggregator")
    assert res.qnx_cmd == "slay sensor_aggregator"

    # 6. lsof -p
    res = translate_linux_command("lsof -p 1042")
    assert res.qnx_cmd == "pidin -p 1042 fds"

    # 7. dmesg
    res = translate_linux_command("dmesg")
    assert res.qnx_cmd == "slog2info -S"

    # 8. nice
    res = translate_linux_command("nice -n 25 /tmp/test_binary")
    assert res.qnx_cmd == "on -p 25f /tmp/test_binary"

    # 9. lsmod
    res = translate_linux_command("lsmod")
    assert res.qnx_cmd == "pidin ar"

    # 10. free -h
    res = translate_linux_command("free -h")
    assert res.qnx_cmd == "pidin info"

    # 11. netstat -tulnp
    res = translate_linux_command("netstat -tulnp")
    assert res.qnx_cmd == "sockstat"

    # 12. pstree
    res = translate_linux_command("pstree")
    assert res.qnx_cmd == "pidin tree"

    # 13. renice
    res = translate_linux_command("renice 30 -p 1200")
    assert res.qnx_cmd == "on -p 30 -P 1200"

    # 14. vmstat
    res = translate_linux_command("vmstat")
    assert res.qnx_cmd == "pidin mem"

    # 15. ifconfig
    res = translate_linux_command("ifconfig")
    assert res.qnx_cmd == "ifconfig"


def test_safety_guards_protected_processes():
    # Dangerous target: PID 1 (procnto)
    is_dang, reason = is_protected_target("1")
    assert is_dang is True
    assert "PID <= 10" in reason

    # Dangerous target: PID 0
    is_dang, _ = is_protected_target("0")
    assert is_dang is True

    # Dangerous target: sshd
    is_dang, reason = is_protected_target("sshd")
    assert is_dang is True

    # Dangerous target: procnto-smp-instr
    is_dang, reason = is_protected_target("procnto-smp-instr")
    assert is_dang is True

    # Safe user-space process
    is_dang, _ = is_protected_target("1200")
    assert is_dang is False

    is_dang, _ = is_protected_target("mock_qnx_service.sh")
    assert is_dang is False


def test_translator_dangerous_flag():
    res = translate_linux_command("kill -9 1")
    assert res.qnx_cmd == "slay -f 1"
    assert res.is_dangerous is True
    assert res.requires_confirm is True
    assert "SAFETY GUARD" in res.warning

    res = translate_linux_command("kill -9 sshd")
    assert res.is_dangerous is True
    assert res.requires_confirm is True


def test_native_qnx_passthrough():
    res = translate_linux_command("pidin info")
    assert res.qnx_cmd == "pidin info"
    assert "passes directly" in res.explanation

    res = translate_linux_command("slog2info -S")
    assert res.qnx_cmd == "slog2info -S"
