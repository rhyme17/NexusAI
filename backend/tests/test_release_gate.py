from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_RELEASE_GATE_PATH = Path(__file__).resolve().parents[1] / "release_gate.py"
_RELEASE_GATE_SPEC = importlib.util.spec_from_file_location("release_gate", _RELEASE_GATE_PATH)
assert _RELEASE_GATE_SPEC is not None and _RELEASE_GATE_SPEC.loader is not None
release_gate = importlib.util.module_from_spec(_RELEASE_GATE_SPEC)
_RELEASE_GATE_SPEC.loader.exec_module(release_gate)


def test_cutover_candidate_profile_exists_and_starts_with_rehearsal() -> None:
    commands = release_gate.BACKEND_TEST_COMMANDS["cutover_candidate"]
    assert len(commands) >= 4
    assert commands[0][1] == "rehearse_cutover.py"


def test_full_profile_includes_router_policy_and_stability_checks() -> None:
    commands = [" ".join(cmd) for cmd in release_gate.BACKEND_TEST_COMMANDS["full"]]
    assert any("test_phase_a_config.py" in cmd and "router_policy" in cmd for cmd in commands)
    assert any("test_task_services.py" in cmd and "task_router_" in cmd for cmd in commands)


def test_run_command_reports_success_for_python_noop(tmp_path: Path) -> None:
    result = release_gate.run_command([sys.executable, "-c", "print('ok')"], cwd=tmp_path)
    assert result["ok"] is True
    assert result["return_code"] == 0
    assert result["stdout_last_line"] == "ok"
    assert result["check_name"] == "custom"


def test_archive_report_writes_timestamped_json(tmp_path: Path) -> None:
    summary = {"status": "ok", "profile": "full", "checks": []}

    archived = release_gate.archive_report(summary=summary, history_dir=tmp_path, profile="full")

    assert archived.exists()
    assert "release-gate-full-" in archived.name
    assert archived.suffix == ".json"

