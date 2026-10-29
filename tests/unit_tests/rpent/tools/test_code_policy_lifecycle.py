# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0

"""Persistent Python execution and cancellation across a real child process."""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from rpent.dashboard.events import NullDashboardEventSink
from rpent.memory import MemoryManager
from rpent.session import EnvState
from rpent.tools import Toolkit, ToolResult, tool
from rpent.tools.code_policy.runtime import CodeSession
from rpent.tools.code_policy.toolkit import CodePolicyTools
from rpent.utils import logging as logging_module


class _BlockingToolkit(Toolkit):
    def __init__(self, root: Path) -> None:
        super().__init__(
            dashboard_events=NullDashboardEventSink(),
            state=EnvState(root),
            memory=MemoryManager(root / "memory"),
        )
        self.entered = threading.Event()
        self.release = threading.Event()
        self.stopping = threading.Event()
        self.cancel_count = 0
        self.add_tool(self.block)

    @tool(readonly=True)
    def block(self) -> ToolResult:
        """Wait for a simulated blocking RPC to return before checking cancellation."""
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError("Test did not release the blocking call")
        self.raise_if_cancelled()
        return ToolResult(data={"ok": True})

    def cancel_active_and_wait(self) -> None:
        self.cancel_count += 1
        self.stopping.set()
        super().cancel_active_and_wait()


@pytest.fixture
def policy(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_module, "_output_dir", tmp_path)
    robot = _BlockingToolkit(tmp_path / "robot")
    provider = CodePolicyTools(robot, output_dir=tmp_path)
    try:
        yield provider, robot
    finally:
        robot.release.set()
        provider.close()


def _run(provider, code):
    return provider.execute_tool("python", {"code": code}).data


def test_variables_survive_python_exceptions(policy):
    provider, robot = policy
    failed = _run(provider, "x = 41\nraise ValueError('retry')")
    assert failed["exception"]["type"] == "ValueError"
    assert not failed["namespace_reset"]
    assert _run(provider, "x + 1")["value"] == "42"
    assert robot.cancel_count == 0


@pytest.mark.parametrize("code", ["while True: pass", "import os; os._exit(2)"])
def test_worker_failure_or_timeout_allows_a_fresh_cell(policy, code):
    provider, robot = policy
    provider._timeout_s = 0.5
    result = _run(provider, "x = 41\n" + code)
    assert result["interrupted"] and result["namespace_reset"]
    assert result["timed_out"] is code.startswith("while")
    assert robot.cancel_count == 1
    assert _run(provider, "'x' in globals()")["value"] == "False"
    assert _run(provider, "6 * 7")["value"] == "42"


@pytest.mark.parametrize("external", [False, True])
def test_cancellation_drains_robot_and_external_stop_requires_resume(policy, external):
    provider, robot = policy
    provider._timeout_s = 5 if external else 0.5
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(_run, provider, "x = 41\nrobo.block()")
        stop = None
        try:
            assert robot.entered.wait(3)
            if external:
                stop = pool.submit(provider.cancel_active_and_wait)
            assert robot.stopping.wait(3)
            assert not running.done()
            if stop is not None:
                assert not stop.done()
        finally:
            robot.release.set()
        result = running.result(timeout=3)
        if stop is not None:
            stop.result(timeout=3)
    assert result["namespace_reset"]
    assert result["timed_out"] is not external
    assert robot.cancel_count == 1
    if external:
        assert _run(provider, "42")["code"] == "tool_cancelled"
        provider.resume_calls()
    assert _run(provider, "'x' in globals()")["value"] == "False"


def test_repeated_stop_notifies_once_until_resumed(tmp_path):
    notifications = []
    session = CodeSession(
        tools=[],
        dispatch=lambda name, args: {},
        workspace=tmp_path,
        on_interrupt=lambda: notifications.append("stop"),
    )
    try:
        session.execute("x = 41", timeout_s=3)
        session.cancel()
        session.cancel()
        assert notifications == ["stop"]
        session.resume()
        assert session.execute("'x' in globals()", timeout_s=3)["value"] == "False"
        session.cancel()
        assert notifications == ["stop", "stop"]
    finally:
        session.close()


def test_timeout_discards_already_queued_cells(policy, monkeypatch):
    provider, robot = policy
    queued = threading.Event()

    class AnnouncedLock:
        """Expose when the second caller reaches the serialization boundary."""

        def __init__(self):
            self.lock = threading.Lock()

        def __enter__(self):
            if self.lock.locked():
                queued.set()
            self.lock.acquire()

        def __exit__(self, *args):
            self.lock.release()

    monkeypatch.setattr(provider, "_serial", AnnouncedLock())
    provider._timeout_s = 0.5
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(_run, provider, "robo.block()")
        try:
            assert robot.entered.wait(3)
            waiting = pool.submit(_run, provider, "stale = True")
            assert queued.wait(3)
            assert robot.stopping.wait(3)
        finally:
            robot.release.set()
        assert running.result(timeout=3)["timed_out"]
        assert waiting.result(timeout=3)["code"] == "tool_cancelled"
    assert _run(provider, "'stale' in globals()")["value"] == "False"
