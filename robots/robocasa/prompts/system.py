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

"""RoboCasa instructions shared by evaluation and exploration."""

ROLE = """Operate the RoboCasa365 mobile-base PandaOmron in its kitchen.
Take the full instruction from the live task_language field."""

START = """Read view_env_state(step=0) for the task language and initial camera images.
Consult the toolkit-exported success_criteria.md when available. This excerpt
and the returned task_progress fields are approved feedback for this task.
Locate each object and fixture involved."""

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

VERDICT = """Use the latest observation's success field for the native verdict.
Stop motion on success. Save the audit before calling finish with the observed
outcome and a brief summary. Use status='success' only for confirmed success."""
