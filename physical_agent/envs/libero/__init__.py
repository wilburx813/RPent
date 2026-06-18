"""LIBERO environment extension."""
from __future__ import annotations

from physical_agent.envs.base import EnvSpec
from physical_agent.envs.libero.prompt_bundle import PROMPTS


def get_env_spec() -> EnvSpec:
    """Return the LIBERO env identity + prompt bundle.

    Tool schemas, handlers, driver lifecycle, and the MCP allowlist live on
    the LIBERO toolkit (see :func:`get_toolkit`).
    """
    return EnvSpec(
        name="libero",
        prompts=PROMPTS,
    )


def get_toolkit():
    """Return the LIBERO toolkit (common tools + LIBERO primitives)."""
    from physical_agent.envs.libero.toolkit import LiberoToolkit

    return LiberoToolkit()
