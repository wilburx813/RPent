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

"""Compose a cells policy from robot-owned knowledge and native tool schemas.

The cells workflow is adapted from PyRUA-Lean.
"""

from __future__ import annotations

import json
from importlib.resources import files

from rpent.tools.code_policy.toolkit import CodePolicyTools
from rpent.utils.templates import substitute

_CONTRACT = """# How you control the robot

Use `python(code)` to run code in a persistent Python session, like a notebook.
The `robo` object exposes registered tools as methods with keyword arguments:
`result = robo.<tool_name>(argument=value)`. Variables, functions and imports
persist between cells. Import math or numpy when needed. Only the tools in the
API reference are available; there are no additional robot properties or aliases.

Calls return the original dictionaries, including error fields and observation
envelopes. A state-changing result may contain both the observation and the action
result (for example under `log.result`); inspect its actual fields. Use `print(...)`
to include values in the feedback; bare expressions produce no output. Feedback
contains stdout, stderr, any exception and the last tool result. The latest returned
tool images are attached when images are enabled. A later state-changing call
replaces earlier images. A completed call is not proof of physical success.

Write short cells when you need to look before deciding, and bounded loops when
you can decide from numeric feedback. Check results after each action. Stop the
cell whenever contact, target identity or a scene change requires visual judgment;
inspect the images before continuing. Start by reading the current observation
with `robo.view_env_state(step=-1)` if registered. Recorded reads do not capture a
new scene: use the environment's observation tools to refresh when required.

# How the episode is scored

Follow the task instruction from the environment or operator verbatim. Use only
the environment's public success flags, final-scene judgment or operator verdict,
as specified in the operating knowledge. Primitive success is not task success.
Stop actions when the episode ends. Call the separate top-level `finish` tool
when complete or unable to make progress; it is not a method on `robo`.
When operator reset/confirmation or verdict tools are registered, their requirements
remain mandatory: confirm the scene before motion and obtain the required verdict
before finish. Never infer operator approval from code execution succeeding.

# Workspace and execution limits

There is no task-memory corpus or retrieval in this mode. Your working directory
is scratch space for this session. Do not read outside it, access credentials,
or bypass registered tools to contact robot services. This worker is not a security
sandbox. Code has a wall-clock limit and a tool-call budget per cell; the runner
also enforces its configured planner and environment budgets.

Python exceptions preserve variables. Timeout or cancellation discards the
namespace; physical actions already performed are not rolled back. Inspect the
current state before recovering; never automatically replay an interrupted cell.
"""


def code_policy_prompt(robot_name: str, toolkit: CodePolicyTools) -> str:
    """Use optional robot prompt assets without requiring a robot API adapter."""
    knowledge = ""
    try:
        knowledge = (
            files(f"robots.{robot_name}.prompts")
            .joinpath("code_policy.md")
            .read_text(encoding="utf-8")
        )
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    entries = []
    for declaration in toolkit.robot_tools():
        entries.append(
            f"### robo.{declaration.name}(**arguments)\n"
            f"{declaration.description}\n"
            + json.dumps(substitute(declaration.input_schema), ensure_ascii=False)
        )
    return "\n\n".join(
        [_CONTRACT, knowledge, "# API reference\n\n" + "\n\n".join(entries)]
    )
