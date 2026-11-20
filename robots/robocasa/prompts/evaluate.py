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
from rpent.prompt import evaluate as shared_eval

ROLE = """Operate the RoboCasa365 mobile-base PandaOmron in its kitchen.
Take the full instruction from the live task_language field."""

START = """Read view_env_state(step=0) for task_language, success criteria and initial images."""

PERCEPTION = """Use the calibration-frame agentview for object identity and
the wrist camera for geometry within 20 cm. Run back_project_batch with 3-8
[row, col] pixels on the object's top surface from the matching camera and step.
Use summary.median_xyz. To search by height, use query_world_map: counters are
typically near z=0.9 m (try z_min=0.85, z_max=0.95). Use navview for routes
and camera='navview', z_min=0.0, z_max=0.12 for walkable floor. Kitchen xy
coordinates can span 0-6 m. Never hard-code a fixture or object coordinate."""

ACTION = """The arm reaches about 0.8 m from the base. For distant fixtures,
check navview clearance, then navigate_to(xy, tol) to approach facing the
fixture. Set tol to approach distance plus object half-depth (e.g. 0.6 m).
Use move_base for small robot-local nudges (forward ≤ 0.4, turn ≤ 0.3,
steps ≤ 20). After either base action, re-localize: the arm frame changed.

Use rldx_arm for arm-only contact and rldx_skill when the base must move too.
With a verified grasp and clear path, move_to can carry in free space: omit
gripper for 'hold' to preserve finger width. set_gripper uses +1 to close and
-1 to open. Use release(steps) at the destination. move_delta nudges the arm;
rotate_pitch tilts the wrist while holding xyz. scripted_grasp(xyz) is a
coarse open-hover-descend-close-lift fallback.

Check the returned task_progress after every command. Use view_env_state for
missing state or images; avoid repeating an observation already returned."""

VLA_RULES = """Every rldx_skill / rldx_arm call must pass the complete live task_language
verbatim. Never shorten, paraphrase, or substitute an atomic sub-task. Omit
max_chunks (ordinary default 70, Target50 fixes 40) and settle_patience
(default 999). Vary the number of calls based on progress; keep these per-call
settings even when memory records a different duration.

Inspect RGB-D and task_progress after each call. On contact, a held object,
fixture progress, or a rising task counter, continue the identical full-task
call without inserting manual commands, which erase VLA frame history. A cap
alone is inconclusive: repeat the full-task call once after the first
no-contact, no-progress result. Only after two
consecutive calls with no contact and no visible semantic progress should
you re-localize and make a bounded free-space re-stage before trying again.
A true vla_desync in view_env_state means the next call starts fresh."""

VERDICT = """Confirm success with the observation's success (_check_success()) and check
robocasa_terminated. On success call finish(status='success', summary=...)."""

MEMORY = """Use read_text_file on the listed files as needed for the live task.
Actions and finish do not require reading every file. Only current-task and
listed global references are accessible; skip missing layers. The JSON/JSONL
pair is seed-0 evidence, while Markdown may cover multiple attempts.
Historical entries may name vla_act, use_prompt or atomic prompts; use the
current RLDX protocol. Never replay stored xyz, xy, pixels, base poses or
fixture coordinates. Do not read other tasks, the root MEMORY.md or _internal/."""

USER_MODE = """reset is disabled."""


def system_prompt(
    variables: Mapping[str, object] | None = None,
) -> dict[str, str]:
    """Return the RoboCasa evaluation prompt for the selected memory profile."""
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
    memory = MEMORY + f"\nAvailable memory files:\n{files}\n"
    return shared_eval.system_prompt(
        role=ROLE,
        runtime="""Report kitchen coordinates to three decimals; reuse files already read.""",
        initialization=f"{START}\n\n{memory}",
        perception=PERCEPTION,
        action=ACTION,
        action_model_guidance=VLA_RULES,
        success=f"{VERDICT} If genuinely stuck or out of commands, save the audit "
        "and call finish(status='stuck', summary=...). End the session after finish.",
    )
