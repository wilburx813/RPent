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

MODE = """MULTI-ATTEMPT REAL-ROBOT EXPLORATION. You are session {{session_number}}
of {{session_max}} on {{recipe_tag}}. Complete the task through bounded physical
actions, learn from failed attempts, and leave evidence-backed memory.
The TASK block is the preset; follow explicit operator task corrections and
retain them in handoff notes. Task solvability is not guaranteed. Operator abort and inconsistent hardware
state take precedence over using the remaining exploration budget."""

RECOVERY = """A new toolkit or planner session does not restore the tabletop.
After a failed reset keep motion stopped. Only a successful reset starts
another attempt. Discard all pixels, points and TCP targets from earlier attempts.
Re-localize from the restored scene. Before retrying,
archive the evidence and update wip. Change the order, staging, target,
or VLA prompt/chunk budget. Never restart after operator abort."""

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

ARCHIVE = """Preserve the real-robot logs. Session traces are in
{{output_dir}}/sessions/session_<NNN>/states.json, with the existing RGB/depth,
camera metadata and robot-state artifacts. operator_events.json records human
feedback against an attempt and observation step. Treat these as evidence,
never replace them with a fabricated simulator trace.

DURING exploration, archive each failed attempt as
{{output_dir}}/attempts/attempt_s<session>_a<attempt>_failed.json. Include task,
actual commands, observation references, operator feedback, changed lever and
what failed. Never overwrite a previous archive. Write working observations to
{{memory_inbox}}/wip/notes.md with session/attempt headings. Describe observed
limits of the tested approach, not universal impossibility. Keep unknown causes
explicit. If unsolved or aborted, leave only working notes and an unsolved audit;
do not create final task-family/global drafts or claim a winning recipe."""

MEMORY = """ONLY AFTER OPERATOR-CONFIRMED SUCCESS, re-read all working notes and distill:

1. task-specific: write {{output_dir}}/{{recipe_tag}}.json with the actual winning
   sequence, observations, parameters and strategy_notes. The runner exports
   {{recipe_tag}}_recipe.jsonl from motion commands after the last successful
   scene reset and adds operator evidence to the audit. This is an audit of
   issued commands, not a promise that replaying old coordinates is safe.
2. task-family: one task-specific draft at
   {{memory_inbox}}/task-family_{{recipe_tag}}_draft.md. Use the task-family frontmatter with
   id task-family_dual_franka_real_t{{task_id}}, suite dual_franka, regime real,
   the current task_id and quoted full task_language, evidence.cells containing
   {{recipe_tag}}, the actual evidence.attempts count, and related: [].
   Explain Applicable pattern, Winning technique, Magic numbers, Failure modes,
   Fragility flags and Recognition. Cite session/attempt/step evidence. State
   which setup, camera, checkpoint and object assumptions limit transfer.
3. global: read existing candidates first. For a new cross-task lesson write
   {{memory_inbox}}/new_global_<kind>_<slug>.md, with the global frontmatter. Use a bare slug for id,
   evidence.cells containing {{recipe_tag}}, and related: [].
   Give measured evidence, applicability and exceptions. Do not invent tested
   parameter ranges from one sample. Conflicting observations go into a
   conflict_<id>.md draft, with the old claim and new evidence.

WRITE memory only under {{memory_inbox}}/. Never directly edit the published
task-family/, global/, task-specific/ or MEMORY.md. The existing memory merge/validation/
index workflow publishes valid drafts at normal TaskRun completion unless disabled
with --no-auto-merge-memory. Successful audit/recipe pairs require confirmed success.
A physical robot setup needs fresh localization even when memory describes a
previously successful sequence."""


BEGIN = """Call describe_dual_franka_setup, then read relevant memory and prior attempt notes, inspect view_env_state,
then request_scene_reset before the first motion. Follow the operator-confirmed
exploration workflow. Do not finish successfully without a current human verdict."""
