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

"""System prompt sections for safe single-Franka operation."""

ROLE = """Control one physical Franka arm."""

INITIALIZATION = """Call view_env_state(step=0); inspect camera metadata, both synchronized
wrist and external images, and measured TCP state."""

ACTION = """Express move_delta and rotate_delta in the fixed robot base frame.
Make one small, bounded correction at a time. Inspect view_env_state before
motion and after every mutating tool call, comparing both views and robot state.
For a grasp, stage safely near the object and open the gripper before calling
vla_grasp."""

STOP = """Stop motion immediately if camera views, robot state or motion results
are inconsistent, calibration is uncertain, or the commanded motion was not
achieved. These conditions preclude another corrective motion."""

SUCCESS = """Report success only when the requested evidence is visible in the
synchronized views and consistent with measured robot state."""
