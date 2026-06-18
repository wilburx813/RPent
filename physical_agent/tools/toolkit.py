"""Toolkit base class for agent tools.

``Toolkit`` is the agent-facing tool container. Subclasses register tools
during ``__init__`` via :meth:`Toolkit.add_tool`; the cerebrum consumes the
result through :meth:`Toolkit.get_tools_spec` and
:meth:`Toolkit.execute_tool`.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from physical_agent.utils.templates import bind_placeholders


class Toolkit:
    """Base toolkit: registers common tools and dispatches tool calls.

    Subclasses extend ``__init__`` (calling ``super().__init__()`` first)
    and register additional tools with :meth:`add_tool`. Override
    :meth:`set_driver_client` / :meth:`release_driver_client` to wire up
    env-side drivers the tools talk to, and set
    :attr:`allowed_mcp_tool_names` to expose tools over MCP.
    """

    #: MCP allowlist contributed by this toolkit (namespaced tool names).
    #: Env toolkits override with their own tuple; empty by default.
    allowed_mcp_tool_names: tuple[str, ...] = ()

    def __init__(self) -> None:
        # name -> (spec, handler)
        self._tools: dict[str, tuple[dict[str, Any], Callable[..., dict[str, Any]]]] = {}
        self._register_common_tools()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_tool(
        self,
        name: str,
        spec: dict[str, Any],
        handler: Callable[..., dict[str, Any]],
    ) -> None:
        """Register one tool under ``name`` with its schema and handler.

        Args:
            name: Tool name as the LLM sees it (e.g. ``"read_text_file"``).
            spec: Anthropic-shaped tool schema dict (``name``,
                ``description``, ``input_schema``).
            handler: Callable invoked with the tool's input kwargs; returns
                a result dict.
        """
        self._tools[name] = (spec, handler)

    def _register_common_tools(self) -> None:
        """Register the file/IO tools shared by every run."""
        from physical_agent.tools import common

        for spec in common.TOOLS_SPEC:
            name = spec["name"]
            self.add_tool(name, spec, common.TOOL_HANDLERS[name])

    # ------------------------------------------------------------------
    # Cerebrum-facing API
    # ------------------------------------------------------------------

    def get_tools_spec(self) -> list[dict[str, Any]]:
        """Return the tool schemas the LLM sees."""
        return bind_placeholders(
            [spec for spec, _ in self._tools.values()]
        )

    def execute_tool(self, name: str, input_dict: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool call to its registered handler."""
        entry = self._tools.get(name)
        if entry is None:
            return {"error": f"unknown tool: {name}"}
        handler = entry[1]
        try:
            return handler(**input_dict)
        except TypeError as e:
            return {"error": f"bad arguments for {name}: {e}", "got": input_dict}
        except Exception as e:
            import traceback

            return {"error": str(e), "traceback": traceback.format_exc()}

    # ------------------------------------------------------------------
    # Driver lifecycle hooks (overridden by env toolkits)
    # ------------------------------------------------------------------

    def set_driver_client(
        self,
        client: Any,
        *,
        model: Any,
        hide_object_coords: bool = False,
        video_path: str | None = None,
    ) -> None:
        """Bind the env driver the tools talk to. Default: no-op.

        Env toolkits override this to build their primitive driver once the
        wire transport is ready.
        """

    def release_driver_client(self) -> None:
        """Release the env driver at end of run. Default: no-op."""


def create_toolkit(env_name: str | None = None) -> Toolkit:
    """Build the toolkit for one configured environment.

    Delegates to the environment registry so the env-name -> module mapping
    stays in one place (:mod:`physical_agent.envs.registry`).
    """
    from physical_agent.envs.registry import get_toolkit

    return get_toolkit(env_name)
