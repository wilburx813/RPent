"""Generic placeholder substitution for tool specs and prompts."""
from __future__ import annotations

from typing import Any

from physical_agent.utils.logging import get_output_dir


def default_replacements() -> dict[str, str]:

    return {
        "{output_dir}": str(get_output_dir())
    }


def bind_text(text: str, replacements: dict[str, str]) -> str:
    for token, value in replacements.items():
        if token and token in text:
            text = text.replace(token, value)
    return text


def bind_placeholders(
    obj: Any,
    replacements: dict[str, str] | None = None,
) -> Any:
    """Recursively substitute placeholders (e.g. {output_dir}) in all strings within ``obj``.

    Walks dicts (keys preserved, string values substituted) and lists;
    non-string leaves are returned unchanged. New containers are returned so
    the input is never mutated.
    """
    if replacements is None:
        replacements = default_replacements()
    if isinstance(obj, str):
        return bind_text(obj, replacements)
    if isinstance(obj, list):
        return [bind_placeholders(item, replacements) for item in obj]
    if isinstance(obj, dict):
        return {key: bind_placeholders(value, replacements) for key, value in obj.items()}
    return obj
