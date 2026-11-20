# Copyright 2026 The RPent Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""YAM prompt bundle assembly."""

from __future__ import annotations

from collections.abc import Mapping

from robots.yam.prompts import system as system_parts
from robots.yam.prompts import user as user_parts
from rpent.prompt import evaluate, explore
from rpent.prompt.workflow import user_prompt as build_user_prompt


def system_prompt(variables: Mapping[str, object] | None = None) -> dict[str, str]:
    """Assemble the YAM workflow for the run mode and configured policy."""
    variables = variables or {}
    exploring = variables.get("mode") == "explore"
    workflow = explore if exploring else evaluate
    initialization = system_parts.READ_ORDER
    success = system_parts.SUCCESS
    if exploring:
        initialization += "\n\n" + system_parts.EXPLORE_START
        success += "\n\n" + system_parts.EXPLORE_REPORTING
    else:
        success += "\n\nEvaluation memory is read-only."
    return workflow.system_prompt(
        role=system_parts.ROLE,
        runtime=system_parts.RUNTIME,
        initialization=initialization,
        perception=system_parts.PERCEPTION,
        action=system_parts.CONTROL,
        action_model_guidance=(
            system_parts.VLA
            if variables.get("vla_enabled")
            else system_parts.PRIMITIVES_ONLY
        ),
        recovery=system_parts.EXPLORE_RECOVERY if exploring else "",
        success=success,
    )


def user_prompt(variables: Mapping[str, object] | None = None) -> dict[str, str]:
    """Provide the current task and startup instructions."""
    return build_user_prompt(user_parts.CELL, user_parts.BEGIN)


__all__ = ["system_prompt", "user_prompt"]
