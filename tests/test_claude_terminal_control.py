from __future__ import annotations

import asyncio
import importlib
import queue
import sys
import types
import unittest
from unittest import mock

# Isolate the adapter from prompt-toolkit, which is not needed for these tests.
_tui = types.ModuleType("rpent.cli.tui")


def _next_user_line(input_queue: queue.Queue[str | None]) -> str | None:
    return input_queue.get()


_tui.next_user_line = _next_user_line
with mock.patch.dict(sys.modules, {"rpent.cli.tui": _tui}):
    _TerminalSessionAdapter = importlib.import_module(
        "rpent.planner.claude_code"
    )._TerminalSessionAdapter


class _Driver:
    def __init__(self, calls: list[str], *, fail_query: bool = False) -> None:
        self.calls = calls
        self.fail_query = fail_query

    async def interrupt(self) -> int:
        self.calls.append("driver_interrupt")
        return 0

    async def query(self, text: str) -> None:
        self.calls.append(f"query:{text}")
        if self.fail_query:
            raise RuntimeError("stop test loop")


class ClaudeTerminalControlTest(unittest.TestCase):
    def test_steering_drains_and_interrupts_before_query(self) -> None:
        calls: list[str] = []
        input_queue: queue.Queue[str | None] = queue.Queue()
        input_queue.put("next instruction")
        adapter = _TerminalSessionAdapter(
            input_queue=input_queue,
            cancel_active_and_wait=lambda: calls.append("toolkit_cancel"),
            resume_operations=lambda: calls.append("toolkit_resume"),
            emit_user=lambda text: calls.append(f"emit:{text}"),
        )

        asyncio.run(adapter.run(_Driver(calls, fail_query=True)))
        self.assertEqual(
            calls,
            [
                "toolkit_cancel",
                "driver_interrupt",
                "toolkit_resume",
                "emit:next instruction",
                "query:next instruction",
            ],
        )

    def test_terminal_exit_does_not_resume(self) -> None:
        calls: list[str] = []
        input_queue: queue.Queue[str | None] = queue.Queue()
        input_queue.put(None)
        adapter = _TerminalSessionAdapter(
            input_queue=input_queue,
            cancel_active_and_wait=lambda: calls.append("toolkit_cancel"),
            resume_operations=lambda: calls.append("toolkit_resume"),
            emit_user=lambda text: calls.append(f"emit:{text}"),
        )

        asyncio.run(adapter.run(_Driver(calls)))
        self.assertEqual(calls, ["toolkit_cancel", "driver_interrupt"])


if __name__ == "__main__":
    unittest.main()
