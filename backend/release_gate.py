from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any


BACKEND_TEST_COMMANDS = {
    "quick": [
        [sys.executable, "-m", "pytest", "-q", "tests/test_api.py", "-k", "health or agents"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_protocol_contract.py"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_migration.py"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_phase_a_perf.py", "-k", "snapshot_migration"],
    ],
    "full": [
        [sys.executable, "-m", "pytest", "-q", "tests/test_api.py", "-k", "api_auth_ or role_guard or decomposition"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_protocol_contract.py"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_phase_a_config.py", "-k", "router_policy"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_task_services.py", "-k", "task_router_"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_task_services.py", "-k", "workflow_service_ or retry_exhausted"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_sqlite_store.py", "-k", "sqlite_store or task_api_can_run_with_sqlite_store_override"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_websocket.py", "-k", "retry_event_after_failure or retry_exhausted_event"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_migration.py"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_phase_a_perf.py"],
    ],
    "cutover_candidate": [
        [sys.executable, "rehearse_cutover.py"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_protocol_contract.py"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_migration.py"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_api.py", "-k", "health or agents"],
        [sys.executable, "-m", "pytest", "-q", "tests/test_phase_a_perf.py", "-k", "snapshot_migration"],
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NexusAI backend release gate checks and emit a JSON report.")
    parser.add_argument("--profile", choices=("quick", "full", "cutover_candidate"), default="quick", help="Gate profile to run.")
    parser.add_argument("--report", default="./data/release-gate-report.json", help="Report output path.")
    parser.add_argument(
        "--archive-history",
        action="store_true",
        help="Also write a timestamped report copy under history dir for audit traceability.",
    )
    parser.add_argument("--history-dir", default="./data/release-gate-history", help="History directory for archived reports.")
    return parser.parse_args()


def _infer_check_name(cmd: list[str]) -> str:
    cmd_text = " ".join(cmd)
    if "test_protocol_contract.py" in cmd_text:
        return "protocol_contract"
    if "test_phase_a_config.py" in cmd_text and "router_policy" in cmd_text:
        return "router_policy"
    if "test_task_services.py" in cmd_text and "task_router_" in cmd_text:
        return "router_stability"
    if "test_task_services.py" in cmd_text:
        return "workflow_services"
    if "test_api.py" in cmd_text:
        return "api_regression"
    if "test_migration.py" in cmd_text:
        return "migration"
    if "test_phase_a_perf.py" in cmd_text:
        return "performance"
    if "test_sqlite_store.py" in cmd_text:
        return "sqlite_store"
    if "test_websocket.py" in cmd_text:
        return "websocket"
    if "rehearse_cutover.py" in cmd_text:
        return "cutover_rehearsal"
    return "custom"


def run_command(cmd: list[str], cwd: Path, check_name: str | None = None) -> dict[str, Any]:
    started = perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    duration_ms = round((perf_counter() - started) * 1000, 2)
    stdout_text = (proc.stdout or "").strip()
    stderr_text = (proc.stderr or "").strip()
    return {
        "check_name": check_name or _infer_check_name(cmd),
        "command": " ".join(cmd),
        "return_code": proc.returncode,
        "duration_ms": duration_ms,
        "ok": proc.returncode == 0,
        "stdout_last_line": stdout_text.splitlines()[-1] if stdout_text else "",
        "stderr_last_line": stderr_text.splitlines()[-1] if stderr_text else "",
    }


def archive_report(*, summary: dict[str, Any], history_dir: Path, profile: str) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = history_dir / f"release-gate-{profile}-{timestamp}.json"
    archive_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return archive_path


def main() -> int:
    args = parse_args()
    backend_dir = Path(__file__).resolve().parent
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = (backend_dir / report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    checks: list[dict[str, Any]] = []
    for cmd in BACKEND_TEST_COMMANDS[args.profile]:
        result = run_command(cmd, cwd=backend_dir)
        checks.append(result)
        if not result["ok"]:
            break

    status = "ok" if checks and all(item["ok"] for item in checks) else "failed"
    summary = {
        "status": status,
        "profile": args.profile,
        "total_checks": len(checks),
        "passed_checks": sum(1 for item in checks if item["ok"]),
        "failed_checks": sum(1 for item in checks if not item["ok"]),
        "failed_check_name": next((item["check_name"] for item in checks if not item["ok"]), None),
        "total_duration_ms": round(sum(float(item["duration_ms"]) for item in checks), 2),
        "checks": checks,
    }

    if args.archive_history:
        history_dir = Path(args.history_dir)
        if not history_dir.is_absolute():
            history_dir = (backend_dir / history_dir).resolve()
        archive_path = archive_report(summary=summary, history_dir=history_dir, profile=args.profile)
        summary["archived_report"] = str(archive_path)

    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

