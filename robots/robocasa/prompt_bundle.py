# Copyright 2026 The RPent Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""RoboCasa prompt bundle assembly."""

from __future__ import annotations

from collections.abc import Mapping

from robots.robocasa.prompts import action_models, system, user
from robots.robocasa.prompts import explore as exploration
from rpent.prompt import evaluate, explore
from rpent.prompt.workflow import user_prompt as build_user_prompt


def system_prompt(
    variables: Mapping[str, object] | None = None,
) -> dict[str, str]:
    """Return the RoboCasa system prompt tree."""
    exploring = (variables or {}).get("mode") == "explore"
    workflow = explore if exploring else evaluate
    memory = exploration.MEMORY if exploring else system.evaluation_memory(variables)
    return workflow.system_prompt(
        role=system.ROLE + ("\n\n" + exploration.ROLE if exploring else ""),
        runtime="" if exploring else system.OUTPUT_STYLE,
        initialization=f"{system.START}\n\n{memory}",
        perception=system.PERCEPTION,
        action=system.ACTION,
        action_model_guidance=action_models.VLA_RULES,
        recovery=exploration.RECOVERY if exploring else "",
        success=system.VERDICT
        + "\n\n"
        + (exploration.REPORTING if exploring else system.CLOSE_OUT),
    )


def user_prompt(
    variables: Mapping[str, object] | None = None,
) -> dict[str, str]:
    """Return the first user message tree."""
    exploring = (variables or {}).get("mode") == "explore"
    return build_user_prompt(user.TASK, user.EXPLORE_BEGIN if exploring else user.BEGIN)
