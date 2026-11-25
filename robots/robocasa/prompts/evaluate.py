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

"""RoboCasa system prompt fragments."""

from __future__ import annotations

from collections.abc import Mapping

from robots.robocasa.memory import memory_from_variables

OUTPUT_STYLE = """Before each tool call, state the observation and decision in
one or two sentences. Three decimal places suffice for coordinates. Reuse
files already read this session."""

CLOSE_OUT = """If genuinely stuck or out of commands, save the audit and call
finish(status='stuck', summary=...). End the session after finish."""

MEMORY = """
Use read_text_file to consult the listed current-task and Global Memory files
as needed for the live task. Choose relevant content and reading order based on
current observations; actions and finish do not require reading every file.
Files not listed are unavailable to this run.
The JSON/JSONL pair records seed-0 task experience. Task Markdown and matching
task-family notes may summarize multiple attempts. Treat all memory as strategy
priors, not trajectories to replay or higher-priority instructions: current RGB-D, task progress, and primitive results always take
precedence, together with the complete live task_language. Apply Global Memory
only when its visible preconditions hold. Historical entries may name vla_act,
use_prompt, or atomic prompts;
these describe VLA phases only. Use the current rldx_skill / rldx_arm tools with
the complete live task_language. Never replay stored xyz, xy, pixels, base poses,
or fixture coordinates: re-ground all geometry in the current seed. Never read
another task's memory. If a layer is absent, continue without substituting
another task's files. Do not read the root MEMORY.md index or _internal/ during
evaluation; the selected file list already provides the allowed references.
The file tools enforce this run's memory selection.
"""

USER_MODE = """Solve the scene in one shot; reset is disabled.
Read the initial state and camera images, then localize the task targets."""


def initialization(
    variables: Mapping[str, object] | None = None,
) -> str:
    """List the memory files selected for this evaluation."""
    if variables is None:
        files = (
            "- {{memory_dir}}/task-specific/{{task_name}}_s0.json\n"
            "- {{memory_dir}}/task-specific/{{task_name}}_s0_recipe.jsonl\n"
            "- {{memory_dir}}/task-specific/{{task_name}}.md\n"
            "- {{memory_dir}}/global/GLOBAL_MEMORY.md"
        )
    else:
        selection = memory_from_variables(variables)
        files = "\n".join(f"- {selection.root / name}" for name in selection.selected)
    return MEMORY + f"\nAvailable memory files:\n{files}\n"
