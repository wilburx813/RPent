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

"""Persistent Python workers with bounded JSON messages and host tool dispatch."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

MAX_SOURCE_BYTES = 64 * 1024
MAX_MESSAGE_BYTES = 16 * 1024 * 1024


class CodeSession:
    """Own a Python namespace in a separate, cancellable process.

    Dispatch runs synchronously in ``execute``'s caller. Every interruption kills
    Python and notifies ``on_interrupt`` once, without holding the process lock.
    The callback must request host cancellation without waiting for dispatch;
    ``execute`` drains the in-flight dispatch before returning. Killing Python
    does not stop a physical robot. This process is not a security sandbox.
    """

    def __init__(
        self,
        *,
        tools: list[str],
        dispatch: Callable[[str, dict[str, Any]], dict[str, Any]],
        workspace: Path,
        on_interrupt: Callable[[], None] | None = None,
    ) -> None:
        self._tools = frozenset(tools) - {"finish"}
        self._dispatch = dispatch
        self._workspace = Path(workspace).resolve()
        self._on_interrupt = on_interrupt
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._active = False
        self._closed = False
        self._interruption: str | None = None
        self._timed_out = False
        self._idle = threading.Event()
        self._idle.set()
        self._cell = 0

    def _start(self) -> subprocess.Popen[bytes]:
        # Called under the state lock so cancel cannot miss a newly started worker.
        self._workspace.mkdir(parents=True, exist_ok=True)
        with (self._workspace / "worker.stderr.log").open("ab") as diagnostics:
            process = subprocess.Popen(
                [sys.executable, "-u", str(Path(__file__).with_name("worker.py"))],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=diagnostics,
                cwd=self._workspace,
            )
        self._process = process
        return process

    @staticmethod
    def _write(process: subprocess.Popen[bytes], message: dict[str, Any]) -> None:
        payload = json.dumps(message, allow_nan=False).encode("utf-8") + b"\n"
        if len(payload) > MAX_MESSAGE_BYTES:
            raise ValueError("Code-policy message exceeds the 16 MiB limit")
        assert process.stdin is not None
        process.stdin.write(payload)
        process.stdin.flush()

    @staticmethod
    def _read(process: subprocess.Popen[bytes]) -> dict[str, Any]:
        assert process.stdout is not None
        payload = process.stdout.readline(MAX_MESSAGE_BYTES + 1)
        if not payload:
            raise RuntimeError("Python worker exited before completing the cell")
        if len(payload) > MAX_MESSAGE_BYTES or not payload.endswith(b"\n"):
            raise ValueError("Invalid or oversized Python worker message")
        message = json.loads(payload)
        if not isinstance(message, dict):
            raise ValueError("Python worker message must be an object")
        return message

    def _interrupt(
        self, reason: str, *, timeout: bool = False, cell: int | None = None
    ) -> None:
        with self._lock:
            if timeout and (not self._active or cell != self._cell):
                return
            first_interrupt = self._interruption is None
            self._interruption = self._interruption or reason
            self._timed_out = self._timed_out or timeout
            process = self._process
            if process is not None and process.poll() is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
        if first_interrupt and self._on_interrupt is not None:
            self._on_interrupt()

    def execute(self, code: str, *, timeout_s: float) -> dict[str, Any]:
        """Execute a cell, retaining variables until cancellation or closure.

        Args:
            code: Python source, limited to 64 KiB of UTF-8.
            timeout_s: Positive wall-clock budget including host tool calls.

        Returns:
            Captured output, exception details and elapsed time.
        """
        if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise ValueError("Python source must be a string no larger than 64 KiB")
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout_s must be positive and finite")
        started = time.monotonic()
        with self._lock:
            if self._closed:
                raise RuntimeError("Code session is closed")
            if self._interruption is not None:
                raise RuntimeError("Code session was interrupted; resume it first")
            if self._active:
                raise RuntimeError("A Python cell is already running")
            process = self._process or self._start()
            self._active = True
            self._idle.clear()
            self._cell += 1
            filename = f"cell_{self._cell:06d}.py"
        timer = threading.Timer(
            max(0, timeout_s - (time.monotonic() - started)),
            self._interrupt,
            args=(f"Python cell exceeded {timeout_s:g} seconds",),
            kwargs={"timeout": True, "cell": self._cell},
        )
        timer.daemon = True
        timer.start()
        result: dict[str, Any] = {
            "stdout": "",
            "stderr": "",
            "exception": None,
        }
        try:
            (self._workspace / filename).write_text(code, encoding="utf-8")
            self._write(
                process,
                {
                    "kind": "execute",
                    "code": code,
                    "filename": filename,
                    "tools": sorted(self._tools),
                },
            )
            while True:
                message = self._read(process)
                with self._lock:
                    if self._interruption is not None:
                        raise RuntimeError(self._interruption)
                if message.get("kind") == "result":
                    result.update(message["result"])
                    break
                if message.get("kind") != "call":
                    raise ValueError("Unexpected Python worker message")
                name, arguments = message.get("name"), message.get("arguments")
                if name not in self._tools:
                    raise ValueError(f"Unregistered Python tool: {name}")
                if not isinstance(arguments, dict):
                    raise ValueError("Python tool arguments must be an object")
                try:
                    response = {
                        "kind": "return",
                        "data": self._dispatch(name, arguments),
                    }
                    # Serialization errors are reported to Python, like tool errors.
                    json.dumps(response, allow_nan=False)
                except Exception as exc:
                    response = {
                        "kind": "return",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                with self._lock:
                    if self._interruption is not None:
                        raise RuntimeError(self._interruption)
                self._write(process, response)
        except BaseException as exc:
            with self._lock:
                interrupted = self._interruption is not None
            if not interrupted:
                self._interrupt("Python worker failed; namespace was discarded")
            if not isinstance(exc, Exception):
                raise
            result["exception"] = {
                "type": type(exc).__name__,
                "message": str(exc)[:8000],
                "traceback": "",
            }
        finally:
            timer.cancel()
            timer.join()
            with self._lock:
                interruption = self._interruption
                timed_out = self._timed_out
            if interruption is not None:
                if timed_out or interruption.startswith("Python execution cancelled"):
                    result["exception"] = {
                        "type": "TimeoutError" if timed_out else "InterruptedError",
                        "message": interruption,
                        "traceback": "",
                    }
                self._reap(process)
            result["interrupted"] = interruption is not None
            result["timed_out"] = timed_out
            result["namespace_reset"] = interruption is not None
            result["cell"] = self._cell
            result["source_file"] = filename
            result["elapsed_s"] = time.monotonic() - started
            with self._lock:
                self._active = False
                self._idle.set()
        return result

    def cancel(self) -> None:
        """Kill Python without waiting, invalidating the persistent namespace."""
        self._interrupt("Python execution cancelled; namespace was discarded")

    def _reap(self, process: subprocess.Popen[bytes]) -> None:
        process.wait()
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    # A killed worker may leave buffered stdin bytes unwritten.
                    pass
        with self._lock:
            if self._process is process:
                self._process = None

    def resume(self) -> None:
        """Allow a fresh namespace after an interrupted execution has drained."""
        with self._lock:
            if self._closed or self._active:
                raise RuntimeError("Cannot resume a closed or active code session")
            process = self._process
        if process is not None and self._interruption is not None:
            self._reap(process)
        with self._lock:
            self._interruption = None
            self._timed_out = False

    def close(self) -> None:
        """Stop and reap the Python process; this session cannot be reused."""
        with self._lock:
            self._closed = True
        self.cancel()
        self._idle.wait()
        with self._lock:
            process = self._process
        if process is not None:
            self._reap(process)
