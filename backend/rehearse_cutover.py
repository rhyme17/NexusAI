from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any


EXPECTED_STEP_STATUS = {
    "export": "exported",
    "verify": "valid",
    "import": "imported",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cutover rehearsal: export -> verify -> import.")
    parser.add_argument(
        "--snapshot",
        default="./data/cutover-rehearsal.json",
        help="Snapshot file path used during rehearsal.",
    )
    parser.add_argument(
        "--report",
        default="./data/cutover-rehearsal-report.json",
        help="Optional JSON report output path.",
    )
    parser.add_argument(
        "--keep-default-agents",
        action="store_true",
        help="Pass through keep-default-agents option to import.",
    )
    parser.add_argument(
        "--max-total-ms",
        type=float,
        default=0.0,
        help="Optional total duration budget in milliseconds (0 disables budget check).",
    )
    parser.add_argument(
        "--max-import-ms",
        type=float,
        default=0.0,
        help="Optional import step duration budget in milliseconds (0 disables budget check).",
    )
    return parser.parse_args()


def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, dict[str, Any], float, str, str]:
    start = perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    duration_ms = round((perf_counter() - start) * 1000, 2)

    line = (proc.stdout or "").strip().splitlines()
    raw = line[-1] if line else ""
    payload: dict[str, Any] = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload = parsed
            else:
                payload = {"raw": parsed}
        except json.JSONDecodeError:
            payload = {"raw": raw}

    stderr_text = (proc.stderr or "").strip()
    return proc.returncode, payload, duration_ms, stderr_text, raw


def evaluate_step(name: str, return_code: int, payload: dict[str, Any]) -> tuple[bool, str | None]:
    expected = EXPECTED_STEP_STATUS[name]
    if return_code != 0:
        return False, f"{name} return_code={return_code}"
    if payload.get("status") != expected:
        return False, f"{name} status={payload.get('status')} expected={expected}"
    if name == "import" and bool(payload.get("matches")) is not True:
        return False, "import matches is not true"
    return True, None


def build_summary(
    *,
    snapshot_path: Path,
    export: dict[str, Any],
    verify: dict[str, Any],
    imported: dict[str, Any],
    max_total_ms: float = 0.0,
    max_import_ms: float = 0.0,
) -> dict[str, Any]:
    steps = {
        "export": export,
        "verify": verify,
        "import": imported,
    }

    checks: dict[str, bool] = {}
    failure_reasons: list[str] = []
    for step_name, step_payload in steps.items():
        ok, reason = evaluate_step(step_name, int(step_payload["return_code"]), dict(step_payload["result"]))
        checks[step_name] = ok
        if reason:
            failure_reasons.append(reason)

    total_duration_ms = round(sum(float(steps[name]["duration_ms"]) for name in ("export", "verify", "import")), 2)
    if max_total_ms > 0 and total_duration_ms > max_total_ms:
        failure_reasons.append(f"total duration {total_duration_ms}ms exceeds budget {max_total_ms}ms")
    import_duration_ms = float(steps["import"]["duration_ms"])
    if max_import_ms > 0 and import_duration_ms > max_import_ms:
        failure_reasons.append(f"import duration {import_duration_ms}ms exceeds budget {max_import_ms}ms")

    status = "ok" if all(checks.values()) else "failed"
    if failure_reasons:
        status = "failed"
    return {
        "status": status,
        "snapshot": str(snapshot_path),
        "checks": checks,
        "failure_reasons": failure_reasons,
        "timings": {
            "export_ms": steps["export"]["duration_ms"],
            "verify_ms": steps["verify"]["duration_ms"],
            "import_ms": steps["import"]["duration_ms"],
            "total_ms": total_duration_ms,
        },
        "budgets": {
            "max_total_ms": max_total_ms,
            "max_import_ms": max_import_ms,
        },
        "steps": steps,
    }


def main() -> int:
    args = parse_args()
    backend_dir = Path(__file__).resolve().parent
    snapshot_path = Path(args.snapshot)
    if not snapshot_path.is_absolute():
        snapshot_path = (backend_dir / snapshot_path).resolve()
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = (backend_dir / report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    py = sys.executable

    export_cmd = [py, "migrate_snapshot.py", "export", "--output", str(snapshot_path)]
    verify_cmd = [py, "migrate_snapshot.py", "verify", "--input", str(snapshot_path)]
    import_cmd = [py, "migrate_snapshot.py", "import", "--input", str(snapshot_path)]
    if args.keep_default_agents:
        import_cmd.append("--keep-default-agents")

    export_code, export_payload, export_ms, export_err, export_raw = run_cmd(export_cmd, cwd=backend_dir)
    verify_code, verify_payload, verify_ms, verify_err, verify_raw = run_cmd(verify_cmd, cwd=backend_dir)
    import_code, import_payload, import_ms, import_err, import_raw = run_cmd(import_cmd, cwd=backend_dir)

    summary = build_summary(
        snapshot_path=snapshot_path,
        export={
            "return_code": export_code,
            "duration_ms": export_ms,
            "result": export_payload,
            "stderr": export_err,
            "stdout_last_line": export_raw,
        },
        verify={
            "return_code": verify_code,
            "duration_ms": verify_ms,
            "result": verify_payload,
            "stderr": verify_err,
            "stdout_last_line": verify_raw,
        },
        imported={
            "return_code": import_code,
            "duration_ms": import_ms,
            "result": import_payload,
            "stderr": import_err,
            "stdout_last_line": import_raw,
        },
        max_total_ms=float(args.max_total_ms),
        max_import_ms=float(args.max_import_ms),
    )
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

