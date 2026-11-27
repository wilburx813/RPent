# Copyright 2026 The RPent Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Run selected GPU E2E suites concurrently across available GPUs in CI."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import queue
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

RUNNER_SCRIPT = "tests/e2e_tests/run_gpu_suite.sh"


def summarize_coverage(suite_dir: Path) -> str:
    """Summarize all tool-coverage.json reports under a suite output directory."""
    files = sorted(suite_dir.rglob("tool-coverage.json"))
    if not files:
        return "none"
    parts: list[str] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            missing = len(data.get("missing") or [])
            failed = len(data.get("failures") or [])
            executed = len(data.get("executed") or [])
            parts.append(
                f"{path.parent.name}: {executed} ok, {missing} miss, {failed} err"
            )
        except Exception:  # noqa: BLE001
            parts.append(f"{path.parent.name}: unreadable")
    return "; ".join(parts)


def parse_gpus(raw_gpus: str) -> list[str]:
    """Parse numeric GPU ordinals from CUDA_VISIBLE_DEVICES."""
    gpus = [g.strip() for g in raw_gpus.split(",") if g.strip().isdecimal()]
    if not gpus:
        raise SystemExit(
            f"CUDA_VISIBLE_DEVICES must list at least one numeric GPU: {raw_gpus!r}"
        )
    return gpus


def _append_summary(lines: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _print_failure_tail(name: str, log_path: Path, tail_lines: int = 80) -> None:
    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[
        -tail_lines:
    ]
    print(f"--- tail of {name}.log ---", flush=True)
    print("\n".join(tail), flush=True)


def run_e2e(suites: list[str], run_dir: Path, venv_dir: Path) -> int:
    """Run selected GPU E2E suites across the runner's available GPUs."""
    if not suites:
        return 0
    gpus = parse_gpus(os.environ.get("CUDA_VISIBLE_DEVICES", "").strip())
    gpu_pool: queue.Queue[str] = queue.Queue()
    for gpu in gpus:
        gpu_pool.put(gpu)

    def run_one(suite: str) -> dict[str, Any]:
        gpu = gpu_pool.get()
        t0 = time.monotonic()
        log_path = run_dir / f"{suite}.log"
        suite_out = run_dir / suite
        suite_venv = venv_dir / suite
        env = {**os.environ, "CUDA_VISIBLE_DEVICES": gpu}
        cmd = [
            "bash",
            RUNNER_SCRIPT,
            suite,
            str(suite_out),
            str(suite_venv),
        ]
        try:
            with log_path.open("w", encoding="utf-8") as log_file:
                proc = subprocess.run(
                    cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, check=False
                )
        finally:
            gpu_pool.put(gpu)
        return {
            "name": suite,
            "gpu": gpu,
            "rc": proc.returncode,
            "duration": int(time.monotonic() - t0),
            "coverage": summarize_coverage(suite_out),
            "log": log_path,
        }

    results: list[dict[str, Any]] = []
    max_workers = min(len(gpus), len(suites))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(run_one, suite): suite for suite in suites}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)
            status = "PASSED" if res["rc"] == 0 else f"FAILED (rc={res['rc']})"
            print(
                f"[e2e:{res['name']}] GPU {res['gpu']} {status} "
                f"in {res['duration']}s ({res['coverage']})",
                flush=True,
            )
            if res["rc"] != 0:
                _print_failure_tail(res["name"], res["log"])

    by_name = {res["name"]: res for res in results}
    ordered = [by_name[suite] for suite in suites]
    lines = [
        "### Embodied GPU E2E",
        "",
        "| Suite | GPU | Status | Duration | Tool Coverage |",
        "| --- | --- | --- | --- | --- |",
    ]
    for res in ordered:
        badge = "passed" if res["rc"] == 0 else f"failed (rc={res['rc']})"
        lines.append(
            f"| `{res['name']}` | `{res['gpu']}` | {badge} "
            f"| {res['duration']}s | {res['coverage']} |"
        )
    _append_summary(lines)
    return 1 if any(res["rc"] != 0 for res in ordered) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("venv_dir", type=Path)
    parser.add_argument(
        "--targets-json",
        default=None,
        help="JSON list of suites (defaults to SUITES_JSON).",
    )
    args = parser.parse_args(argv)

    raw_targets = (
        args.targets_json
        if args.targets_json is not None
        else os.environ["SUITES_JSON"]
    )
    suites = json.loads(raw_targets)

    args.run_dir.mkdir(parents=True, exist_ok=True)
    args.venv_dir.mkdir(parents=True, exist_ok=True)
    return run_e2e(suites, args.run_dir, args.venv_dir)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
