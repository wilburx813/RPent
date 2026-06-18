"""LIBERO toolkit: common tools + LIBERO primitives.

Inherits the common file/IO tools from :class:`Toolkit` and registers the
LIBERO primitives (``move_to``, ``pi0_pick``, ``release``, ...) on top. The
primitive handlers and their module-level driver state live in
:mod:`physical_agent.envs.libero.tools`; this class wires them into the
toolkit registry and forwards the driver lifecycle to that module.
"""
from __future__ import annotations

from typing import Any

from physical_agent.envs.libero import tools as libero_tools
from physical_agent.tools.toolkit import Toolkit

# MCP tool names this toolkit exposes (namespaced for the SDK allowlist).
_ALLOWED_MCP_TOOL_NAMES = tuple(
    f"mcp__physical_agent__{name}"
    for name in [
        "move_to",
        "pi0_pick",
        "release",
        "set_gripper",
        "rotate_wrist",
        "rotate_pitch",
        "move_pose",
        "view_driver_state",
        "view_camera_meta",
        "back_project",
        "read_text_file",
        "write_text_file",
        "mcp_list_dir",
        "finish",
    ]
)


class LiberoToolkit(Toolkit):
    """Toolkit for the LIBERO environment.

    Adds the LIBERO primitive tools on top of the common tools inherited
    from :class:`Toolkit`. Driver lifecycle is forwarded to
    :mod:`physical_agent.envs.libero.tools`, which owns the module-level
    primitive driver state.
    """

    allowed_mcp_tool_names = _ALLOWED_MCP_TOOL_NAMES

    def __init__(self) -> None:
        super().__init__()
        self._register_libero_tools()

    def _register_libero_tools(self) -> None:
        """Register the LIBERO primitive tools on top of the common tools."""
        for spec in libero_tools.TOOLS_SPEC:
            name = spec["name"]
            self.add_tool(name, spec, libero_tools.TOOL_HANDLERS[name])

    def set_driver_client(
        self,
        client: Any,
        *,
        model: Any,
        hide_object_coords: bool = False,
        video_path: str | None = None,
    ) -> None:
        """Bind the wire transport and build the LIBERO primitive driver."""
        libero_tools.set_driver_client(
            client,
            model=model,
            hide_object_coords=hide_object_coords,
            video_path=video_path,
        )

    def release_driver_client(self) -> None:
        """Flush the agent-side video buffer to disk (end-of-run)."""
        libero_tools.stop_recording_and_save()
