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

"""Prompt bundle assembly for the dual-Franka environment."""

from __future__ import annotations

from collections.abc import Mapping

from robots.dual_franka.prompts import explore as exploration
from robots.dual_franka.prompts import system, user
from rpent.prompt import evaluate, explore
from rpent.prompt.workflow import user_prompt as build_user_prompt


def system_prompt(variables: Mapping[str, object] | None = None) -> dict[str, str]:
    """Compose the physical robot gates with the selected mode."""
    exploring = (variables or {}).get("mode") == "explore"
    if exploring:
        return explore.system_prompt(
            role="\n".join((system.ROLE, explore.SESSION, exploration.MODE)),
            initialization=system.INITIALIZATION + "\n\n" + exploration.READ_ORDER,
            perception=system.PERCEPTION,
            action=system.ACTION,
            action_model_guidance=system.VLA_GATES,
            recovery="\n\n".join(
                (system.RECOVERY, exploration.RECOVERY, exploration.ARCHIVE)
            ),
            success=exploration.VERDICT + "\n\n" + exploration.MEMORY,
        )
    return evaluate.system_prompt(
        role=system.ROLE,
        initialization=system.INITIALIZATION,
        perception=system.PERCEPTION + "\n\n" + system.LOCALIZATION_TABLE,
        action=system.ACTION,
        action_model_guidance=system.VLA_GATES,
        recovery=system.RECOVERY,
        success=system.VERDICT,
    )


def user_prompt(variables: Mapping[str, object] | None = None) -> dict[str, str]:
    """Place the current task, constraints and startup sequence in the user message."""
    return build_user_prompt(user.TASK)
