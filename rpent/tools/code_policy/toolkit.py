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

"""Planner tools for a Python session borrowing an existing robot toolkit."""

from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from rpent.session import EnvState
from rpent.tools.base import Tool, ToolProvider, ToolResult, tool
from rpent.tools.code_policy.runtime import MAX_SOURCE_BYTES, CodeSession

PASSTHROUGH_TOOLS = frozenset(
    {
        "finish",
        "request_scene_reset",
        "request_operator_verdict",
    }
)
MEMORY_TOOLS = frozenset({"read_text_file", "write_text_file", "list_dir"})
MAX_IMAGES = 8
MAX_IMAGE_BYTES = 16 * 1024 * 1024


class CodePolicyTools:
    """Expose code execution without taking ownership of the robot toolkit.

    Cells and task-control calls are serialized at this boundary. Robot calls
    acquire only the underlying toolkit's scheduler, so each primitive retains
    its own validation, observation capture and cancellation semantics.
    """

    def __init__(
        self,
        toolkit: ToolProvider,
        *,
        output_dir: Path,
        timeout_s: float = 120.0,
        max_calls: int = 100,
        include_images: bool = True,
    ) -> None:
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("code timeout must be finite and positive")
        if type(max_calls) is not int or max_calls <= 0:
            raise ValueError("code call budget must be a positive integer")
        self._toolkit = toolkit
        self._declarations = {
            item.name: item
            for item in toolkit.list_tools()
            if item.name not in MEMORY_TOOLS
        }
        if "python" in self._declarations:
            raise ValueError("Robot tools conflict with the code-policy API")
        self._include_images = include_images
        self._timeout_s = timeout_s
        self._max_calls = max_calls
        self._output_dir = Path(output_dir) / "code_policy"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._serial = threading.Lock()
        self._condition = threading.Condition()
        self._active = False
        self._paused = False
        self._closed = False
        self._finished = False
        self._external_stop = False
        self._generation = 0
        self._cancel_thread: threading.Thread | None = None
        self._cancel_error: BaseException | None = None
        self._cell = 0
        self._calls = 0
        self._images: list[bytes] = []
        self._last_result: dict[str, Any] | None = None
        self._session = CodeSession(
            tools=[name for name in self._declarations if name != "finish"],
            dispatch=self._dispatch,
            workspace=self._output_dir,
            on_interrupt=self._stop_robot_calls,
        )

    @property
    def state(self) -> EnvState:
        """Use the robot's existing artifact store for planner image reads."""
        return self._toolkit.state

    def robot_tools(self) -> tuple[Tool, ...]:
        """Return the original declarations available through the Python proxy."""
        return tuple(
            item for item in self._declarations.values() if item.name != "finish"
        )

    def list_tools(self) -> tuple[Tool, ...]:
        """Return Python execution and task/operator control tools."""
        return (
            self.python,
            *(
                item
                for item in self._declarations.values()
                if item.name in PASSTHROUGH_TOOLS
            ),
        )

    @tool
    def python(self, code: str) -> ToolResult:
        """Execute Python with the robot API `robo` in a persistent session.

        Call registered tools as robo.<name>(**keyword_arguments). Results retain
        their original dictionaries and error fields. Variables persist between
        calls; stdout and the trailing expression are returned with the latest
        tool images. End the cell for required visual checks. Use the separate
        finish tool to end the task. Timeout/cancellation discards variables,
        but does not undo executed actions.

        Args:
            code: Python source. Prefer bounded loops with explicit feedback checks.
        """
        if len(code.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise ValueError("Python source must be no larger than 64 KiB")
        self._cell += 1
        cell = self._cell
        self._calls = 0
        self._images = []
        self._last_result = None
        result = self._session.execute(code, timeout_s=self._timeout_s)
        if result.get("interrupted"):
            self._resume_stopped(automatic=True)
        result.update(
            cell=cell,
            primitive_call_count=self._calls,
            last_tool_result=self._last_result,
        )
        self._write_json(self._output_dir / f"cell_{cell:06d}.json", result)
        return ToolResult(data=result, images=self._images)

    def execute_tool(self, name: str, input_dict: dict[str, Any]) -> ToolResult:
        """Dispatch a model call, serializing cells and finish requests."""
        if name != "python" and name not in PASSTHROUGH_TOOLS:
            return ToolResult(data={"error": f"unknown code-policy tool: {name}"})
        with self._condition:
            generation = self._generation
        with self._serial:
            with self._condition:
                if (
                    self._paused
                    or self._closed
                    or self._finished
                    or generation != self._generation
                ):
                    return ToolResult(
                        data={
                            "error": "Code-policy session is stopped",
                            "code": "tool_cancelled",
                            "interrupted": True,
                        }
                    )
                self._active = True
            try:
                if name == "python":
                    try:
                        args = self.python.args_schema.model_validate(
                            input_dict, strict=True
                        )
                    except ValidationError as exc:
                        return ToolResult(data={"error": str(exc)})
                    return self.python(**args.model_dump())
                result = self._toolkit.execute_tool(name, input_dict)
                if name == "finish" and result.data.get("_finish"):
                    self._finished = True
                    self._session.close()
                return result if self._include_images else ToolResult(data=result.data)
            except Exception as exc:
                return ToolResult(data={"error": f"{type(exc).__name__}: {exc}"})
            finally:
                with self._condition:
                    self._active = False
                    self._condition.notify_all()

    def _dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._condition:
            if self._paused or self._closed or self._finished:
                raise RuntimeError("Code-policy execution was cancelled")
        if name not in self._declarations or name == "finish":
            raise ValueError(f"Tool is unavailable inside Python: {name}")
        declaration = self._declarations[name]
        if not declaration.readonly:
            self._images = []
        if self._calls >= self._max_calls:
            raise RuntimeError("Primitive call budget exhausted for this cell")
        self._calls += 1
        started = time.perf_counter()
        entry: dict[str, Any] = {
            "cell": self._cell,
            "call": self._calls,
            "tool": name,
            "arguments": arguments,
        }
        try:
            result = self._toolkit.execute_tool(name, arguments)
            self._last_result = result.to_dict()
            entry["result"] = self._last_result
            if self._include_images and result.images:
                images = []
                size = 0
                for image in result.images[:MAX_IMAGES]:
                    if size + len(image) > MAX_IMAGE_BYTES:
                        break
                    images.append(image)
                    size += len(image)
                self._images = images
            if result.data.get("interrupted"):
                with self._condition:
                    if not self._paused:
                        self._external_stop = True
                    self._session.cancel()
            # Match ToolResult's public JSON representation without its text limit.
            return json.loads(
                json.dumps(
                    result.to_dict(),
                    allow_nan=False,
                    default=str,
                )
            )
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            entry["elapsed_s"] = time.perf_counter() - started
            with (self._output_dir / "calls.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def _stop_robot_calls(self) -> None:
        """Handle worker interruption without blocking its in-flight dispatch."""
        with self._condition:
            self._paused = True
            self._generation += 1
            if self._cancel_thread is None:
                self._cancel_thread = threading.Thread(
                    target=self._cancel_robot,
                    name="code-policy-cancel",
                    daemon=True,
                )
                self._cancel_thread.start()

    def _cancel_robot(self) -> None:
        try:
            self._toolkit.cancel_active_and_wait()
        except BaseException as exc:
            self._cancel_error = exc

    def cancel_active_and_wait(self) -> None:
        """Stop Python and drain its callbacks and underlying physical operations."""
        with self._condition:
            self._external_stop = True
            self._session.cancel()
        with self._condition:
            self._condition.wait_for(lambda: not self._active)
        if self._cancel_thread is not None:
            self._cancel_thread.join()
        if self._cancel_error is not None:
            raise RuntimeError("Code-policy robot cancellation failed") from (
                self._cancel_error
            )

    def resume_calls(self) -> None:
        """Resume a drained session; an interrupted worker gets a fresh namespace."""
        with self._serial:
            self._resume_stopped(automatic=False)

    def _resume_stopped(self, *, automatic: bool) -> None:
        with self._condition:
            generation = self._generation
            cancel_thread = self._cancel_thread
        if cancel_thread is not None:
            cancel_thread.join()
        with self._condition:
            if (
                self._closed
                or self._finished
                or generation != self._generation
                or (automatic and self._external_stop)
            ):
                return
            if self._cancel_error is not None:
                raise RuntimeError("Robot cancellation failed") from self._cancel_error
            self._toolkit.resume_calls()
            self._session.resume()
            self._cancel_thread = None
            self._paused = False
            self._external_stop = False

    def close(self) -> None:
        """Release code resources, leaving robot finalization to the run owner."""
        try:
            self.cancel_active_and_wait()
        finally:
            self._closed = True
            self._session.close()
        # The original toolkit remains available to operator verdict/recipe hooks.
        self._toolkit.resume_calls()

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
