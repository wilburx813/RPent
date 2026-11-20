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

"""Dual-Franka exploration, human verdicts and memory handoff."""

MODE = """Follow operator corrections to the task preset and record them on handoff.
Operator abort or inconsistent hardware state overrides the remaining budget."""

RECOVERY = """A new session does not restore the tabletop. Keep motion stopped after a
failed reset. Only a successful reset starts another attempt; discard previous
pixels and TCP targets. Never restart after operator abort."""

VERDICT = """Call request_operator_verdict after apparent success or failure.
The human can answer success, failure, continue or abort. A physical action
invalidates a verdict, and continue clears it. Obtain a current judgment
before finish. Tool ok=True, gripper position and policy termination do not
establish task success."""

READ_ORDER = """Read in order: the task's task-family entry under {{memory_dir}}/task-family/,
then {{memory_dir}}/MEMORY.md and relevant {{memory_dir}}/global/ leaves.
Read prior {{output_dir}}/attempts/ archives and {{memory_inbox}}/wip/ notes.
Record which memories applied and which did not. Missing memory is acceptable.
Inspect view_env_state, then request_scene_reset before the first motion."""

ARCHIVE = """Use {{output_dir}}/sessions/session_<NNN>/states.json, RGB/depth, camera
metadata, per-arm state and operator_events.json for attempt/step evidence.
Save failed attempts to {{output_dir}}/attempts/attempt_s<session>_a<attempt>_failed.json
with task, commands, observations, operator feedback and changed lever. Append
session/attempt headings to {{memory_inbox}}/wip/notes.md. On abort or unsolved
exit leave only working notes and an unsolved audit."""

MEMORY = """After operator-confirmed success write the task-specific audit {{output_dir}}/{{recipe_tag}}.json with
strategy_notes, winning commands, parameters and observations. The runner adds
operator evidence and exports {{recipe_tag}}_recipe.jsonl after the last successful
scene reset. For {{memory_inbox}}/task-family_{{recipe_tag}}_draft.md use id
task-family_dual_franka_real_t{{task_id}}, suite dual_franka, regime real, task_id {{task_id}},
evidence.cells [{{recipe_tag}}], actual attempts and related: []. Cover Applicable
pattern, Winning technique, Magic numbers, Failure modes, Fragility flags and
Recognition, citing session/attempt/step and setup, camera, object and checkpoint.
Check existing global leaves first. Write new_global_<kind>_<slug>.md under
{{memory_inbox}} with bare id, same cell and related: []; put conflicting
evidence in conflict_<id>.md. Only the inbox accepts memory writes."""
