#!/usr/bin/env python3
"""Portable split and pilot runner for sealed SLR Building Deconstruction evaluations.

Selects studies directly from the sealed plan (`--split {calibration,holdout,production}`)
or an explicit `--pilot-subset`, enforces shared `--max-attempts` and `--max-cost-usd` ceilings,
and requires explicit `--allow-api` authorization before making any Gemini API calls.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_VERSION = "a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d"


def resolve_python() -> Path:
    venv_py = ROOT_DIR / ".venv" / "bin" / "python"
    return venv_py if venv_py.exists() else Path(sys.executable)


def load_env(env_file: Path | None) -> dict:
    env = os.environ.copy()
    candidate = env_file
    if candidate is None:
        env_var = os.environ.get("SLR_ENV_FILE")
        candidate = Path(env_var).expanduser() if env_var else (ROOT_DIR / ".env")
    if candidate and candidate.exists():
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def log(msg: str, log_file: Path):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(formatted + "\n")


def select_split_studies(python_bin: Path, version: str, split: str) -> list[str]:
    cmd = [str(python_bin), "pipeline.py", "select-studies", "--version", version, "--split", split, "--format", "json"]
    out = subprocess.check_output(cmd, cwd=ROOT_DIR, text=True)
    payload = json.loads(out)
    return payload["all_studies"]


def count_completed_batches(version: str, stage: str, study_ids: list[str]) -> int:
    results_dir = ROOT_DIR / "work" / "versions" / version / "results" / stage
    if not results_dir.exists():
        return 0
    return sum(1 for sid in study_ids for b in range(1, 6) if (results_dir / f"{sid}_{b}.json").exists())


def run_stage(
    python_bin: Path,
    version: str,
    split: str,
    stage: str,
    study_ids: list[str],
    studies_csv: str | None,
    pilot_subset: bool,
    max_calls_cap: int | None,
    max_attempts: int | None,
    max_cost_usd: float | None,
    budget_file: Path | None,
    max_retries: int | None,
    retry_rejected: bool,
    env: dict,
    log_file: Path,
):
    target_total = len(study_ids) * 5
    done_initial = count_completed_batches(version, stage, study_ids)
    remaining_needed = max(0, target_total - done_initial)
    if remaining_needed == 0:
        log(f"Stage '{stage}' ({split}): {done_initial}/{target_total} batches already verified.", log_file)
        return

    budget = min(remaining_needed, max_calls_cap) if max_calls_cap is not None else remaining_needed
    cmd = [
        str(python_bin), "pipeline.py", "assess",
        "--version", version,
        "--stage", stage,
        "--split", split,
        "--max-calls", str(budget),
        "--allow-api",
    ]
    if studies_csv:
        cmd.extend(["--studies", studies_csv])
    if pilot_subset:
        cmd.append("--pilot-subset")
    if max_attempts is not None:
        cmd.extend(["--max-attempts", str(max_attempts)])
    if max_cost_usd is not None:
        cmd.extend(["--max-cost-usd", f"{max_cost_usd:.4f}"])
    if budget_file is not None:
        cmd.extend(["--budget-file", str(budget_file)])
    if max_retries is not None:
        cmd.extend(["--max-retries", str(max_retries)])
    if retry_rejected:
        cmd.append("--retry-rejected")

    log(f"Executing Stage '{stage}' ({split}): completed={done_initial}/{target_total}, call_budget={budget}", log_file)
    res = subprocess.run(cmd, cwd=ROOT_DIR, env=env)
    done_after = count_completed_batches(version, stage, study_ids)
    log(f"Stage '{stage}' exited with code {res.returncode} (verified={done_after}/{target_total}).", log_file)
    if res.returncode != 0:
        time.sleep(2)
        raise RuntimeError(f"Stage '{stage}' exited with code {res.returncode}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--split", choices=["calibration", "holdout", "production"], default="holdout")
    parser.add_argument("--studies", default=None, help="Optional comma-separated study subset (requires --pilot-subset)")
    parser.add_argument("--pilot-subset", action="store_true", help="Authorize a bounded pilot subset within --split")
    parser.add_argument("--stages", default="flash,argon", help="Comma-separated stages (e.g. baseline,flash,argon)")
    parser.add_argument("--max-calls-per-stage", type=int, default=None)
    parser.add_argument("--max-attempts", type=int, default=None, help="Hard ceiling on total live provider attempts")
    parser.add_argument("--max-cost-usd", type=float, default=None, help="Hard ceiling on cumulative USD spend")
    parser.add_argument("--budget-file", type=Path, default=None, help="Shared JSON ledger across stages")
    parser.add_argument("--max-retries", type=int, default=None, help="Optional per-request retry limit override")
    parser.add_argument("--retry-rejected", action="store_true")
    parser.add_argument("--env-file", type=Path, default=None, help="Optional .env file containing GEMINI_API_KEY")
    parser.add_argument("--allow-api", action="store_true", help="Explicit authorization required for live API calls")
    args = parser.parse_args()

    if not args.allow_api:
        raise SystemExit("Execution halted: pass --allow-api only after explicit authorization for the target run.")

    python_bin = resolve_python()
    env = load_env(args.env_file)
    log_file = ROOT_DIR / "work" / f"runner_{args.split}.log"
    approved = select_split_studies(python_bin, args.version, args.split)
    if args.studies:
        req = [s.strip() for s in args.studies.split(",") if s.strip()]
        if not set(req).issubset(set(approved)):
            raise SystemExit(f"Requested studies {req} are not a subset of approved {args.split} split.")
        if set(req) != set(approved) and not args.pilot_subset:
            raise SystemExit("Partial study list requires --pilot-subset.")
        study_ids = [s for s in approved if s in set(req)]
    else:
        study_ids = approved
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    budget_file = args.budget_file
    if budget_file is None and (args.max_attempts is not None or args.max_cost_usd is not None):
        budget_file = ROOT_DIR / "work" / "versions" / args.version / f"budget_{args.split}.json"

    log("=" * 70, log_file)
    log(f"SLR Building Deconstruction Runner | version={args.version} | split={args.split} ({len(study_ids)} studies)", log_file)
    log(f"Target studies: {','.join(study_ids)} | stages={stages} | max_attempts={args.max_attempts} | max_cost_usd={args.max_cost_usd}", log_file)
    log("=" * 70, log_file)

    for stage in stages:
        run_stage(
            python_bin, args.version, args.split, stage, study_ids,
            args.studies, args.pilot_subset, args.max_calls_per_stage,
            args.max_attempts, args.max_cost_usd, budget_file, args.max_retries,
            args.retry_rejected, env, log_file,
        )

    res_exp = subprocess.run([str(python_bin), "pipeline.py", "export", "--version", args.version], cwd=ROOT_DIR, env=env)
    if res_exp.returncode != 0:
        sys.exit(res_exp.returncode)
    log("Export completed.", log_file)


if __name__ == "__main__":
    main()
