"""System prompt and initial-user-message templates for the hybrid agent.

The prompt bodies live as Markdown files in ``prompts/``; this module reads
them once at import time and re-exports them under their historical names so
callers stay unchanged. Edit the ``.md`` files to change a prompt — no Python
diff needed.
"""
from __future__ import annotations

from importlib.resources import files

_PROMPTS = files("physical_agent.context.prompts")


def _read(name: str) -> str:
    return _PROMPTS.joinpath(name).read_text(encoding="utf-8")


PERCEPTION_PREFIX = _read("perception_prefix.md")
SYSTEM_PROMPT = _read("system.md")
PERCEPTION_USER_TEMPLATE = _read("perception_user.md")
INITIAL_USER_TEMPLATE = _read("initial_user.md")
CLAUDE_CODE_PROMPT_TEMPLATE = _read("claude_code.md")
CLAUDE_CODE_PERCEPTION_PROMPT_TEMPLATE = _read("claude_code_perception.md")


def format_claude_code_prompt(
    template: str,
    *,
    suite: str,
    task: int,
    seed: int,
    recipe_tag: str,
    output_dir: str,
) -> str:
    """Substitute Claude Code prompt placeholders without ``str.format``.

    The prompt contains JSON examples with literal braces, so using
    ``str.format()`` would require escaping the whole document. Instead we
    do targeted replacements on the legacy ``{UPPER}`` placeholders.
    """
    replacements = {
        "{SUITE}": suite,
        "{TASK}": str(task),
        "{SEED}": str(seed),
        "{TAG}": recipe_tag,
        "{OUTPUT_DIR}": output_dir,
    }
    prompt = template
    for old, new in replacements.items():
        prompt = prompt.replace(old, new)
    return prompt
