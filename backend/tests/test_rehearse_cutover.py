from __future__ import annotations

import importlib.util
from pathlib import Path


_REHEARSE_PATH = Path(__file__).resolve().parents[1] / "rehearse_cutover.py"
_REHEARSE_SPEC = importlib.util.spec_from_file_location("rehearse_cutover", _REHEARSE_PATH)
assert _REHEARSE_SPEC is not None and _REHEARSE_SPEC.loader is not None
rehearse_cutover = importlib.util.module_from_spec(_REHEARSE_SPEC)
_REHEARSE_SPEC.loader.exec_module(rehearse_cutover)


def test_build_summary_marks_ok_when_all_steps_pass() -> None:
    summary = rehearse_cutover.build_summary(
        snapshot_path=Path("snapshot.json"),
        export={"return_code": 0, "duration_ms": 10.0, "result": {"status": "exported"}},
        verify={"return_code": 0, "duration_ms": 12.0, "result": {"status": "valid"}},
        imported={"return_code": 0, "duration_ms": 13.0, "result": {"status": "imported", "matches": True}},
    )
    assert summary["status"] == "ok"
    assert summary["checks"] == {"export": True, "verify": True, "import": True}
    assert summary["failure_reasons"] == []
    assert summary["timings"]["total_ms"] == 35.0


def test_build_summary_marks_failed_when_import_mismatch() -> None:
    summary = rehearse_cutover.build_summary(
        snapshot_path=Path("snapshot.json"),
        export={"return_code": 0, "duration_ms": 10.0, "result": {"status": "exported"}},
        verify={"return_code": 0, "duration_ms": 12.0, "result": {"status": "valid"}},
        imported={"return_code": 0, "duration_ms": 13.0, "result": {"status": "imported", "matches": False}},
    )
    assert summary["status"] == "failed"
    assert summary["checks"]["import"] is False
    assert any("matches" in item for item in summary["failure_reasons"])


def test_build_summary_marks_failed_when_timing_budget_exceeded() -> None:
    summary = rehearse_cutover.build_summary(
        snapshot_path=Path("snapshot.json"),
        export={"return_code": 0, "duration_ms": 20.0, "result": {"status": "exported"}},
        verify={"return_code": 0, "duration_ms": 20.0, "result": {"status": "valid"}},
        imported={"return_code": 0, "duration_ms": 120.0, "result": {"status": "imported", "matches": True}},
        max_total_ms=100.0,
        max_import_ms=100.0,
    )
    assert summary["status"] == "failed"
    assert summary["budgets"]["max_total_ms"] == 100.0
    assert summary["budgets"]["max_import_ms"] == 100.0
    assert any("exceeds budget" in item for item in summary["failure_reasons"])


