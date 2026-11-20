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

"""RoboDojo exploration prompt for transferable manipulation memory."""

READ_ORDER = """Read {{memory_dir}}/MEMORY.md, matching task-family/global leaves and
successful task-specific pairs for {{policy_name}} cadence, then read
{{memory_inbox}}/wip/notes.md when present."""

RULES = """reset restores the same seed group and layout. {{retry_strategy}}
Unsolved finish is refused while a finite attempt budget remains; reset is
refused after native success."""

OUTPUT = """Before finish write {{output_dir}}/{{recipe_tag}}.json with task, seed,
layout, verbatim instruction, attempts, native_success, final_state,
memory_files_read and uncertainties. Reference failed archives on an unsolved exit.
On success, strategy_notes must cover every exported action and successful SAM3
mask call since the last reset: actual parameters, trace step, phase, result
and reason for {{policy_name}}/primitive switches. The runner publishes the
audit with {{recipe_tag}}_recipe.jsonl only on native success."""

MEMORY = """Write {{memory_inbox}}/task-family_{{recipe_tag}}_draft.md with suite
robodojo, regime {{env_cfg_type}}, task_id {{task}}, evidence.cells
["{{recipe_tag}}"] and actual attempts. Record useful SAM3 descriptions for
objects and contact features, required vs layout-dependent arm roles, phase
gates and final posture, {{memory_control}}, switching points, and observed
native action costs for productive, recovery and terminal motions.
Include layout-dependent offsets, clearances, failures and limits.
For a distinct cross-task finding write {{memory_inbox}}/new_global_<lesson-id>.md
with a bare id and a falsifying observation. Check existing leaves for duplicates
and counterevidence. Failed attempts write only to wip/. The finalizer publishes
validated proposals and updates MEMORY.md."""
