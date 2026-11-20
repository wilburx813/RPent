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

"""RoboDojo prompt bundle assembly."""

from __future__ import annotations

from collections.abc import Mapping

from robots.robodojo.prompts import evaluate as evaluate_parts
from robots.robodojo.prompts import explore as explore_parts
from robots.robodojo.prompts import user as user_parts
from robots.robodojo.prompts.policy import POLICY_PROMPTS
from rpent.prompt import evaluate, explore
from rpent.prompt.utils import PromptNode
from rpent.prompt.workflow import user_prompt as build_user_prompt
from rpent.utils.templates import substitute


def system_prompt(
    variables: Mapping[str, object] | None = None,
) -> PromptNode:
    """Select the RoboDojo evaluation or exploration system prompt."""
    variables = variables or {}
    if variables.get("mode") == "eval-fair":
        return evaluate_parts.eval_fair_system_prompt(variables)

    exploring = variables.get("mode") == "explore"
    workflow = explore if exploring else evaluate
    if exploring:
        role = f"{evaluate_parts.ROLE}\n\n{explore_parts.GOAL}"
        startup = explore_parts.READ_ORDER
        recovery = f"{evaluate_parts.BUDGET}\n\n{explore_parts.RULES}"
        output = f"{explore_parts.OUTPUT}\n\n{explore_parts.MEMORY}"
    else:
        role = evaluate_parts.ROLE
        startup = f"{evaluate_parts.READ_ORDER}\n\n{evaluate_parts.MEMORY}"
        recovery = evaluate_parts.BUDGET
        output = evaluate_parts.OUTPUT_DISCIPLINE
    sections = workflow.system_prompt(
        role=role,
        runtime=f"{evaluate_parts.TOOL_ACCESS}\n\n{evaluate_parts.SAFETY}",
        initialization=f"{startup}\n\n{evaluate_parts.PLAN}",
        perception=evaluate_parts.PERCEPTION,
        action=evaluate_parts.CHECKS,
        action_model_guidance=f"{evaluate_parts.TOOLS}\n\n{evaluate_parts.CONTROL}",
        recovery=recovery,
        success=f"{evaluate_parts.TERMINAL}\n\n{output}",
    )
    backend = variables.get("vla_backend") or "vpp2"
    return substitute(sections, POLICY_PROMPTS[backend])


def user_prompt(
    variables: Mapping[str, object] | None = None,
) -> PromptNode:
    backend = (variables or {}).get("vla_backend") or "vpp2"
    if (variables or {}).get("mode") == "eval-fair":
        return {"TASK": "{{task}} / layout {{layout}}"}
    return build_user_prompt(
        user_parts.TASK.replace(
            "{{policy_control}}", POLICY_PROMPTS[backend]["policy_control"]
        ),
        user_parts.BEGIN,
    )


__all__ = ["system_prompt", "user_prompt"]
