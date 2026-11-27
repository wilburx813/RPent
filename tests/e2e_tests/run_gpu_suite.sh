#!/usr/bin/env bash
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

set -euo pipefail

# Do not let a runner's interactive shell or previously activated environment
# affect imports or uv's target environment.
unset PYTHONPATH VIRTUAL_ENV CONDA_PREFIX UV_NO_CACHE

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <suite|all> <output-dir> <venv-root>"
  echo "Each target installs the matching robot component into a clean environment."
  exit 2
fi

target=$1
output_dir=$2
venv_root=$3
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

if [[ ! "${CUDA_VISIBLE_DEVICES:-}" =~ ^[0-9]+$ ]]; then
  echo "CUDA_VISIBLE_DEVICES must expose exactly one selected GPU"
  exit 1
fi
if [[ -e "$output_dir" || -e "$venv_root" ]]; then
  echo "Output and venv paths must not already exist"
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to create a clean Python environment"
  exit 1
fi
for command in timeout setsid ps python3; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "$command is required to bound tests and verify process cleanup"
    exit 1
  fi
done

install_timeout=${RPENT_INSTALL_TIMEOUT:-45m}
test_timeout=${RPENT_TEST_TIMEOUT:-45m}
pytest_timeout=${RPENT_GPU_PYTEST_TIMEOUT_SECONDS:-1200}

if [[ ! "$pytest_timeout" =~ ^[1-9][0-9]*$ ]]; then
  echo "RPENT_GPU_PYTEST_TIMEOUT_SECONDS must be a positive integer"
  exit 1
fi

mkdir -p "$output_dir" "$venv_root"
output_dir=$(cd "$output_dir" && pwd)
venv_root=$(cd "$venv_root" && pwd)

cleanup() {
  if [[ -d "$venv_root" ]]; then
    find "$venv_root" -depth -delete
  fi
}
trap cleanup EXIT

session_processes() {
  local session_id=$1
  ps -o pid= --sid "$session_id" 2>/dev/null | awk '{$1=$1}; NF {print}' || true
}

wait_for_session_exit() {
  local session_id=$1
  local attempts=$2
  local attempt

  for ((attempt = 0; attempt < attempts; attempt++)); do
    if [[ -z "$(session_processes "$session_id")" ]]; then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

terminate_session_processes() {
  local session_id=$1
  local -a pids=()

  mapfile -t pids < <(session_processes "$session_id")
  if ((${#pids[@]} == 0)); then
    return
  fi

  kill -TERM "${pids[@]}" 2>/dev/null || true
  if wait_for_session_exit "$session_id" 50; then
    return
  fi

  mapfile -t pids < <(session_processes "$session_id")
  if ((${#pids[@]} > 0)); then
    kill -KILL "${pids[@]}" 2>/dev/null || true
    wait_for_session_exit "$session_id" 25 || true
  fi
}

verify_test_session_cleanup() {
  local name=$1
  local session_file=$2
  local report="$output_dir/$name-daemon-cleanup.txt"
  local session_id
  local residual_before
  local residual_after

  if [[ ! -s "$session_file" ]]; then
    echo "cleanup_status=failed" >"$report"
    echo "reason=pytest session id was not recorded" >>"$report"
    echo "$name cleanup verification failed: session id was not recorded"
    return 1
  fi
  session_id=$(<"$session_file")
  if [[ ! "$session_id" =~ ^[1-9][0-9]*$ ]]; then
    echo "cleanup_status=failed" >"$report"
    echo "reason=invalid pytest session id: $session_id" >>"$report"
    echo "$name cleanup verification failed: invalid session id"
    return 1
  fi

  # Parent-watch daemons may need a moment to observe EOF after pytest exits.
  wait_for_session_exit "$session_id" 25 || true
  residual_before=$(session_processes "$session_id")
  if [[ -n "$residual_before" ]]; then
    terminate_session_processes "$session_id"
  fi
  residual_after=$(session_processes "$session_id")

  {
    echo "session_id=$session_id"
    if [[ -n "$residual_before" ]]; then
      echo "residual_before_cleanup=${residual_before//$'\n'/,}"
    else
      echo "residual_before_cleanup=none"
    fi
    if [[ -n "$residual_after" ]]; then
      echo "residual_after_cleanup=${residual_after//$'\n'/,}"
      echo "cleanup_status=failed"
    else
      echo "residual_after_cleanup=none"
      echo "cleanup_status=passed"
    fi
  } >"$report"

  if [[ -n "$residual_after" ]]; then
    echo "$name cleanup verification failed; see $report"
    return 1
  fi
  if [[ -n "$residual_before" ]]; then
    echo "$name left processes running; they were terminated; see $report"
    return 1
  fi
  echo "$name daemon cleanup verified"
}

run_gpu_pytest() {
  local name=$1
  local python=$2
  local suite_output="$output_dir/$name"
  local junit_path="$output_dir/$name-junit.xml"
  shift 2
  local session_file="$output_dir/$name-pytest-session.txt"
  local test_status
  local cleanup_status=0

  set +e
  RPENT_E2E_SUITE="$name" \
    RPENT_E2E_OUTPUT_DIR="$suite_output" \
    timeout --foreground --kill-after=2m "$test_timeout" \
    bash -c '
      set -euo pipefail
      session_file=$1
      shift
      setsid "$@" &
      session_id=$!
      echo "$session_id" >"$session_file"
      cleanup() {
        kill -TERM -- "-$session_id" 2>/dev/null || true
      }
      trap cleanup EXIT HUP INT TERM
      wait "$session_id"
    ' bash "$session_file" \
      "$python" -m pytest -v -rs \
      --timeout="$pytest_timeout" \
      --basetemp="$output_dir/$name-pytest-tmp" \
      --junitxml="$junit_path" "$@"
  test_status=$?
  set -e

  verify_test_session_cleanup "$name" "$session_file" || cleanup_status=$?
  if ((test_status != 0)); then
    return "$test_status"
  fi
  if [[ -z "$(find "$output_dir" -name tool-coverage.json -print -quit)" ]]; then
    echo "$name did not execute a planner/tool coverage test; check skipped prerequisites" >&2
    return 1
  fi
  return "$cleanup_status"
}

run_rpent_install() {
  # Runners can preload verified wheels alongside the shared uv cache.
  if [[ -z "${UV_FIND_LINKS:-}" && -n "${UV_CACHE_DIR:-}" && -d "$UV_CACHE_DIR/wheelhouse" ]]; then
    export UV_FIND_LINKS="$UV_CACHE_DIR/wheelhouse"
  fi
  if [[ -n "${RPENT_GITHUB_MIRROR:-}" ]]; then
    local mirror=${RPENT_GITHUB_MIRROR%/}
    local count=${GIT_CONFIG_COUNT:-0}
    env \
      "GIT_CONFIG_COUNT=$((count + 1))" \
      "GIT_CONFIG_KEY_${count}=url.${mirror}/https://github.com/.insteadOf" \
      "GIT_CONFIG_VALUE_${count}=https://github.com/" \
      timeout --kill-after=2m "$install_timeout" \
      "$repo_root/rpent-install.sh" "$@"
  else
    timeout --kill-after=2m "$install_timeout" \
      "$repo_root/rpent-install.sh" "$@"
  fi
}

install_test_runner() {
  local python=$1
  timeout --kill-after=2m "$install_timeout" \
    uv pip install --python "$python" pytest pytest-timeout
}

materialize_package_files() {
  local python=$1
  shift
  "$python" - "$@" <<'PY'
import importlib.metadata
import os
import shutil
import sys
from pathlib import Path

for pkg in sys.argv[1:]:
    dist = importlib.metadata.distribution(pkg)
    for rel in dist.files or ():
        path = Path(dist.locate_file(rel))
        if path.is_symlink():
            target = path.resolve()
            if target.is_file():
                tmp = path.with_name(f".{path.name}.materialize.{os.getpid()}")
                shutil.copy2(target, tmp)
                os.replace(tmp, path)
PY
}

run_declarative_suite() {
  local name=$1
  local venv_dir="$venv_root/$name"
  local SUITE_COMPONENT=""
  local SUITE_REINSTALL_PKG=""
  local -a SUITE_MATERIALIZE_PKGS=()
  local -a SUITE_POST_INSTALL_CMD=()

  eval "$(python3 "$repo_root/tests/e2e_tests/suite.py" shell-meta "$name" "$output_dir" "$venv_dir/bin/python")"

  run_rpent_install install "$SUITE_COMPONENT" --venv "$venv_dir"
  cp "$venv_dir/rpent-install.json" "$output_dir/"
  run_rpent_install doctor --venv "$venv_dir"
  "$venv_dir/bin/rpent" --help >/dev/null
  install_test_runner "$venv_dir/bin/python"

  if ((${#SUITE_MATERIALIZE_PKGS[@]} > 0)); then
    materialize_package_files "$venv_dir/bin/python" "${SUITE_MATERIALIZE_PKGS[@]}"
  fi

  if [[ -n "$SUITE_REINSTALL_PKG" ]]; then
    local requirement
    requirement=$(uv pip freeze --python "$venv_dir/bin/python" \
      | awk -v pkg="$SUITE_REINSTALL_PKG" '$1 == pkg || index($1, pkg "==") == 1 {print}')
    if [[ -z "$requirement" ]]; then
      echo "Expected $SUITE_REINSTALL_PKG in $venv_dir" >&2
      return 1
    fi
    timeout --kill-after=2m "$install_timeout" uv pip install \
      --python "$venv_dir/bin/python" --link-mode copy \
      --reinstall-package "$SUITE_REINSTALL_PKG" --no-deps "$requirement"
  fi

  if ((${#SUITE_POST_INSTALL_CMD[@]} > 0)); then
    local cmd_bin="${SUITE_POST_INSTALL_CMD[0]}"
    if [[ -x "$venv_dir/bin/$cmd_bin" ]]; then
      SUITE_POST_INSTALL_CMD[0]="$venv_dir/bin/$cmd_bin"
    fi
    timeout --kill-after=2m "$install_timeout" "${SUITE_POST_INSTALL_CMD[@]}"
  fi

  run_gpu_pytest "$name" "$venv_dir/bin/python" tests/e2e_tests/test_suites.py
}

cd "$repo_root"
case "$target" in
  all)
    status=0
    while IFS= read -r suite; do
      [[ -n "$suite" ]] || continue
      bash "$repo_root/tests/e2e_tests/run_gpu_suite.sh" \
        "$suite" "$output_dir/$suite" "$venv_root/$suite" || status=1
    done < <(python3 "$repo_root/tests/e2e_tests/suite.py" list)
    exit "$status"
    ;;
  *)
    if [[ ! -f "$repo_root/tests/e2e_tests/suites/$target.toml" ]]; then
      echo "Unknown target: $target" >&2
      exit 2
    fi
    run_declarative_suite "$target"
    ;;
esac
