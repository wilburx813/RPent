from __future__ import annotations

import threading
import unittest
from typing import Any

from rpent.dashboard.events import NullDashboardEventSink
from rpent.tools.toolkit import Toolkit, parallel, readonly


class _State:
    def latest_record(self) -> None:
        return None


class _TestToolkit(Toolkit):
    def __init__(self) -> None:
        self.captures: list[dict[str, Any]] = []
        super().__init__(
            dashboard_events=NullDashboardEventSink(),
            state=_State(),
        )

    def get_env_state(
        self,
        *,
        command: dict[str, Any],
        result: dict[str, Any],
        elapsed_s: float,
    ) -> dict[str, Any]:
        captured = {"captured": True, **result}
        self.captures.append(captured)
        return captured


def _spec(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": name,
        "input_schema": {"type": "object", "properties": {}},
    }


class ToolkitConcurrencyTest(unittest.TestCase):
    def _start_call(
        self,
        toolkit: Toolkit,
        name: str,
        arguments: dict[str, Any],
        results: dict[str, Any],
        key: str,
    ) -> threading.Thread:
        def run() -> None:
            results[key] = toolkit.execute_tool(name, arguments)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def _wait_for_queue(self, toolkit: Toolkit, size: int) -> None:
        with toolkit._operation_condition:
            ready = toolkit._operation_condition.wait_for(
                lambda: len(toolkit._admission_queue) == size,
                timeout=2,
            )
        self.assertTrue(ready, f"operation queue did not reach size {size}")

    def _join(self, *threads: threading.Thread) -> None:
        for thread in threads:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive(), f"thread {thread.name} did not stop")

    def test_parallel_readers_overlap(self) -> None:
        toolkit = _TestToolkit()
        started = {"a": threading.Event(), "b": threading.Event()}
        release = threading.Event()
        results: dict[str, Any] = {}

        @parallel
        @readonly
        def reader(label: str) -> dict[str, str]:
            started[label].set()
            release.wait(timeout=2)
            return {"label": label}

        toolkit.add_tool("reader", _spec("reader"), reader)
        first = self._start_call(toolkit, "reader", {"label": "a"}, results, "a")
        self.assertTrue(started["a"].wait(timeout=2))
        second = self._start_call(toolkit, "reader", {"label": "b"}, results, "b")
        self.assertTrue(started["b"].wait(timeout=2))

        release.set()
        self._join(first, second)
        self.assertEqual(results["a"].result, {"label": "a"})
        self.assertEqual(results["b"].result, {"label": "b"})

    def test_fifo_exclusive_barrier(self) -> None:
        toolkit = _TestToolkit()
        started = {
            name: threading.Event()
            for name in ("reader-a", "write-a", "write-b", "reader-b")
        }
        release = {name: threading.Event() for name in started}
        order: list[str] = []
        results: dict[str, Any] = {}

        @parallel
        @readonly
        def reader(label: str) -> dict[str, str]:
            order.append(label)
            started[label].set()
            release[label].wait(timeout=2)
            return {"label": label}

        @readonly
        def writer(label: str) -> dict[str, str]:
            order.append(label)
            started[label].set()
            release[label].wait(timeout=2)
            return {"label": label}

        toolkit.add_tool("reader", _spec("reader"), reader)
        toolkit.add_tool("writer", _spec("writer"), writer)

        threads = [
            self._start_call(
                toolkit,
                "reader",
                {"label": "reader-a"},
                results,
                "reader-a",
            )
        ]
        self.assertTrue(started["reader-a"].wait(timeout=2))

        for name, tool in (
            ("write-a", "writer"),
            ("write-b", "writer"),
            ("reader-b", "reader"),
        ):
            threads.append(
                self._start_call(
                    toolkit,
                    tool,
                    {"label": name},
                    results,
                    name,
                )
            )
            self._wait_for_queue(toolkit, len(threads) - 1)

        self.assertEqual(order, ["reader-a"])
        release["reader-a"].set()
        self.assertTrue(started["write-a"].wait(timeout=2))
        self.assertEqual(order, ["reader-a", "write-a"])

        release["write-a"].set()
        self.assertTrue(started["write-b"].wait(timeout=2))
        self.assertEqual(order, ["reader-a", "write-a", "write-b"])

        release["write-b"].set()
        self.assertTrue(started["reader-b"].wait(timeout=2))
        self.assertEqual(
            order,
            ["reader-a", "write-a", "write-b", "reader-b"],
        )
        release["reader-b"].set()
        self._join(*threads)

    def test_cancel_drains_reader_and_discards_queued_action(self) -> None:
        toolkit = _TestToolkit()
        reader_started = threading.Event()
        release_reader = threading.Event()
        action_started = threading.Event()
        cancel_done = threading.Event()
        results: dict[str, Any] = {}
        action_calls = 0

        @parallel
        @readonly
        def reader() -> dict[str, bool]:
            reader_started.set()
            release_reader.wait(timeout=2)
            return {"read": True}

        def action() -> dict[str, bool]:
            nonlocal action_calls
            action_calls += 1
            action_started.set()
            return {"acted": True}

        toolkit.add_tool("reader", _spec("reader"), reader)
        toolkit.add_tool("action", _spec("action"), action)

        reader_thread = self._start_call(toolkit, "reader", {}, results, "reader")
        self.assertTrue(reader_started.wait(timeout=2))
        action_thread = self._start_call(toolkit, "action", {}, results, "action")
        self._wait_for_queue(toolkit, 1)

        def cancel() -> None:
            toolkit.cancel_active_and_wait()
            cancel_done.set()

        cancel_thread = threading.Thread(target=cancel, daemon=True)
        cancel_thread.start()
        self._join(action_thread)
        self.assertEqual(results["action"].result["code"], "tool_cancelled")
        self.assertFalse(action_started.is_set())
        self.assertFalse(cancel_done.is_set())

        release_reader.set()
        self._join(reader_thread, cancel_thread)
        self.assertTrue(cancel_done.is_set())

        toolkit.cancel_active_and_wait()
        late = toolkit.execute_tool("action", {})
        self.assertEqual(late.result["code"], "tool_cancelled")
        self.assertEqual(action_calls, 0)

        toolkit.resume_operations()
        resumed = toolkit.execute_tool("action", {})
        self.assertEqual(resumed.result["acted"], True)
        self.assertEqual(action_calls, 1)

        toolkit.close()
        toolkit.close()
        toolkit.resume_operations()
        closed = toolkit.execute_tool("action", {})
        self.assertEqual(closed.result["code"], "tool_cancelled")
        self.assertEqual(action_calls, 1)

    def test_cancelled_action_still_captures_final_state(self) -> None:
        toolkit = _TestToolkit()
        action_started = threading.Event()
        cancellation_boundary = threading.Event()
        cancel_done = threading.Event()
        results: dict[str, Any] = {}
        action_calls = 0

        def action() -> dict[str, bool]:
            nonlocal action_calls
            action_calls += 1
            action_started.set()
            cancellation_boundary.wait(timeout=2)
            toolkit.raise_if_cancelled()
            return {"acted": True}

        toolkit.add_tool("action", _spec("action"), action)
        action_thread = self._start_call(toolkit, "action", {}, results, "action")
        self.assertTrue(action_started.wait(timeout=2))
        queued_thread = self._start_call(toolkit, "action", {}, results, "queued")
        self._wait_for_queue(toolkit, 1)

        def cancel() -> None:
            toolkit.cancel_active_and_wait()
            cancel_done.set()

        cancel_thread = threading.Thread(target=cancel, daemon=True)
        cancel_thread.start()
        with toolkit._operation_condition:
            active = toolkit._active_exclusive_operation
        self.assertIsNotNone(active)
        self.assertTrue(active.cancel_event.wait(timeout=2))

        cancellation_boundary.set()
        self._join(action_thread, queued_thread, cancel_thread)
        self.assertTrue(cancel_done.is_set())
        self.assertEqual(results["action"].result["code"], "tool_cancelled")
        self.assertEqual(results["queued"].result["code"], "tool_cancelled")
        self.assertEqual(action_calls, 1)
        self.assertTrue(results["action"].result["captured"])
        self.assertEqual(toolkit.captures[-1]["code"], "tool_cancelled")

    def test_parallel_requires_readonly(self) -> None:
        toolkit = _TestToolkit()

        @parallel
        def unsafe() -> dict[str, bool]:
            return {"ok": True}

        with self.assertRaisesRegex(ValueError, "must also be marked readonly"):
            toolkit.add_tool("unsafe", _spec("unsafe"), unsafe)


if __name__ == "__main__":
    unittest.main()
