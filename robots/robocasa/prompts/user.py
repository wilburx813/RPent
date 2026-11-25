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

"""User prompt for one RoboCasa run."""

TASK = """Task: {{task_name}} / {{split}}. Seed: {{seed}}.
Write the audit to {{output_dir}}/{{recipe_tag}}.json."""

BEGIN = """Solve the scene in one shot; reset is disabled.
Read the initial state and camera images, then localize the task targets."""

EXPLORE_BEGIN = """
Explore mode is active. `reset` starts a fresh attempt and is expected when an
episode becomes unrecoverable. The attempt limit is {{explore_attempts_per_session}}
(0 means unlimited). Test a distinct approach each attempt and preserve
useful evidence for the next session. Start with the
initial camera views and published memory, then check the current inbox.
"""
