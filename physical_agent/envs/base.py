"""Environment extension contracts for PhysicalAgent."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptBundle:
    """Rendered prompt variants required by the runner."""

    system_prompt: str
    initial_user_template: str
    perception_prefix: str
    perception_user_template: str
    claude_code_prompt_template: str
    claude_code_perception_prompt_template: str
    format_claude_code_prompt: Callable[..., str]

    def api_system_prompt(self, *, perception: bool = False) -> str:
        if perception:
            return self.perception_prefix + self.system_prompt
        return self.system_prompt

    def api_user_message(
        self,
        *,
        perception: bool = False,
        suite: str,
        task: int,
        seed: int,
        output_dir: str,
        recipe_tag: str,
    ) -> str:
        template = (
            self.perception_user_template
            if perception
            else self.initial_user_template
        )
        return template.format(
            suite=suite,
            task=task,
            seed=seed,
            output_dir=output_dir,
            recipe_tag=recipe_tag,
        )

    def cli_prompt_template(self, *, perception: bool = False) -> str:
        if perception:
            return self.claude_code_perception_prompt_template
        return self.claude_code_prompt_template


@dataclass(frozen=True)
class EnvSpec:
    """Environment-level (non-tool) extension points for PhysicalAgent.

    Tool schemas, handlers, driver lifecycle, and the MCP allowlist live on
    :class:`physical_agent.tools.toolkit.Toolkit` (and env-specific
    subclasses). ``EnvSpec`` carries only the env identity and prompt bundle.
    """

    name: str
    prompts: PromptBundle
