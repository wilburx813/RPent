from __future__ import annotations

import asyncio
import unittest
from collections.abc import Callable

from rpent.dashboard.interaction import DashboardMessage
from rpent.dashboard.planner_control import DashboardPlannerControl


class _Interaction:
    def __init__(
        self,
        calls: list[str],
        *,
        interrupt_requested: bool = False,
        replacement_requested: bool = False,
        pending_message: str | None = None,
    ) -> None:
        self.calls = calls
        self.planner_activity = "busy"
        self.interaction_version = 0
        self.task_replacement_requested = replacement_requested
        self._interrupt_requested = interrupt_requested
        self._pending = (
            DashboardMessage("message-1", pending_message, "pending")
            if pending_message is not None
            else None
        )

    def wait_for_interaction_change(
        self,
        since: int,
        timeout: float | None = None,
    ) -> int:
        return self.interaction_version

    def claim_next_pending_message(self) -> DashboardMessage | None:
        message = self._pending
        self._pending = None
        return message

    def mark_message_sent(self, message_id: str) -> DashboardMessage:
        self.calls.append("message_sent")
        return DashboardMessage(message_id, "queued", "sent")

    def mark_message_failed(
        self,
        message_id: str,
        error: str,
    ) -> DashboardMessage:
        self.calls.append("message_failed")
        return DashboardMessage(message_id, "queued", "failed", error)

    def mark_message_unsent(self, message_id: str) -> DashboardMessage:
        self.calls.append("message_unsent")
        return DashboardMessage(message_id, "queued", "unsent")

    def claim_interrupt_request(self) -> bool:
        claimed = self._interrupt_requested
        self._interrupt_requested = False
        return claimed

    def complete_interrupt(self, error: str | None = None) -> None:
        self.calls.append("interrupt_error" if error else "interrupt_complete")

    def set_planner_activity(
        self,
        activity: str,
        *,
        accepting_input: bool | None = None,
    ) -> None:
        self.planner_activity = activity
        self.calls.append(f"activity:{activity}")

    def seal_interaction(self) -> None:
        self.planner_activity = "ended"
        self.calls.append("sealed")

    def complete_task_replacement(self, error: str | None = None) -> None:
        self.calls.append("replacement_error" if error else "replacement_complete")
        self.planner_activity = "ended"


class _Driver:
    def __init__(
        self,
        calls: list[str],
        *,
        completed: int = 1,
        interrupt_error: Exception | None = None,
    ) -> None:
        self.calls = calls
        self.completed = completed
        self.interrupt_error = interrupt_error

    async def interrupt(self) -> int:
        self.calls.append("driver_interrupt")
        if self.interrupt_error is not None:
            raise self.interrupt_error
        return self.completed

    async def submit(self, text: str) -> int:
        self.calls.append(f"submit:{text}")
        return 1


def _control(
    interaction: _Interaction,
    calls: list[str],
) -> DashboardPlannerControl:
    def record(name: str) -> Callable[[], None]:
        return lambda: calls.append(name)

    return DashboardPlannerControl(
        interaction=interaction,
        cancel_active_and_wait=record("toolkit_cancel"),
        resume_operations=record("toolkit_resume"),
        emit_user=lambda text: calls.append(f"emit:{text}"),
        emit_initial_user=lambda: calls.append("emit_initial"),
    )


async def _start_and_process(
    control: DashboardPlannerControl,
    driver: _Driver,
    calls: list[str],
) -> None:
    await control.start()
    calls.clear()
    await control._process(driver)


class DashboardPlannerControlTest(unittest.TestCase):
    def test_successful_interrupt_resumes_before_flushing(self) -> None:
        calls: list[str] = []
        interaction = _Interaction(
            calls,
            interrupt_requested=True,
            pending_message="queued",
        )
        control = _control(interaction, calls)
        driver = _Driver(calls)

        asyncio.run(_start_and_process(control, driver, calls))
        self.assertEqual(
            calls,
            [
                "toolkit_cancel",
                "driver_interrupt",
                "toolkit_resume",
                "interrupt_complete",
                "activity:idle",
                "submit:queued",
                "message_sent",
                "emit:queued",
                "activity:busy",
            ],
        )

    def test_failed_interrupt_keeps_toolkit_paused(self) -> None:
        calls: list[str] = []
        interaction = _Interaction(
            calls,
            interrupt_requested=True,
            pending_message="queued",
        )
        control = _control(interaction, calls)
        driver = _Driver(calls, interrupt_error=RuntimeError("boom"))

        asyncio.run(_start_and_process(control, driver, calls))
        self.assertEqual(
            calls,
            ["toolkit_cancel", "driver_interrupt", "interrupt_error"],
        )

    def test_task_replacement_never_resumes_old_toolkit(self) -> None:
        calls: list[str] = []
        interaction = _Interaction(calls, replacement_requested=True)
        control = _control(interaction, calls)
        driver = _Driver(calls)

        asyncio.run(_start_and_process(control, driver, calls))
        self.assertEqual(
            calls,
            ["toolkit_cancel", "driver_interrupt", "replacement_complete"],
        )


if __name__ == "__main__":
    unittest.main()
