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

"""Prompt bundle assembly for the single-Franka environment."""

from __future__ import annotations

from collections.abc import Mapping

from robots.franka.prompts import system as system_parts
from robots.franka.prompts import user as user_parts
from rpent.prompt import evaluate


def system_prompt(variables: Mapping[str, object] | None = None) -> dict[str, str]:
    """Assemble the Franka evaluation system prompt."""
    return evaluate.system_prompt(
        role=system_parts.ROLE,
        runtime=system_parts.RUNTIME,
        initialization=system_parts.INITIALIZATION,
        action=system_parts.ACTION,
        recovery=system_parts.STOP,
        success=system_parts.SUCCESS,
    )


def user_prompt(variables: Mapping[str, object] | None = None) -> dict[str, str]:
    """Assemble the task-specific initial user prompt."""
    return evaluate.user_prompt(user_parts.TASK, user_parts.BEGIN)
