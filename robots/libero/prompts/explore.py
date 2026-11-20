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

"""LIBERO multi-attempt exploration and memory distillation."""

from __future__ import annotations

from collections.abc import Mapping

from robots.libero.prompts import evaluate as base
from rpent.prompt import explore
from rpent.prompt.utils import PromptNode

READ_MEMORY = """READ MEMORY: read the matching {{memory_dir}}/task-family/task-family_* entry first,
then {{memory_dir}}/MEMORY.md and relevant {{memory_dir}}/global/ leaves, even
when a seed-0 pair exists. Record consulted files or missing matches in strategy_notes.
Check {{memory_inbox}}/wip/notes.md and prior attempts on handoff."""

RETRY = """LIBERO cells are solvable. reset restores all objects. After roughly five
failed variations on a subgoal with a known fix, weigh a clean rerun against
losing progress: the recipe includes every action after the last reset.
Vary the Pi0 prompt, max_chunks, OSC step_clip/max_steps/tol, wrist pose,
contact point or phase order. Record exhausted and untried approaches at handoff."""

ARCHIVE = """Number archives from 1 across sessions. Include suite, task, seed,
libero_terminated:false, final_state, strategy_notes and changed_lever_vs_attempt<N-1>
after attempt 1. Head each notes entry with '## Attempt <N>'."""

AUDIT = """Only top-level `terminated == true` confirms success. Truncation alone is unsolved.
Write {{output_dir}}/{{recipe_tag}}.json with suite, task_id, seed,
regime:"strict_perception", final_state, libero_terminated and total attempts.
On an unsolved exit include the session end reason and each attempt's blocker;
retain the failed archives and working notes without publishing drafts. On success, build strategy_notes from
states.json after the last reset: one localization sentence and every winning
command with actual parameters in order. Key pick_result by recipe step.
The runner exports {{recipe_tag}}_recipe.jsonl and publishes solved pairs."""

MEMORY = """Allow about 25 tool calls for memory after success. Re-read wip/notes.md
and attempts/*.json. Write {{memory_inbox}}/task-family_{{recipe_tag}}_draft.md.
Use id task-family_<suite family>_<regime>_t<task_id>, suite family (e.g. libero10),
perturbation regime task|swap|lan|object, evidence.cells [{{recipe_tag}}],
attempts, solved_seeds [{{seed}}], failed_seeds [] and related: [].
Use these headings: Applicable pattern, Winning technique (phase gates),
Magic numbers (tested ranges and exclusions), Failure modes (symptom, cause
with attempt number, fix), Re-localization per scene (per-entity segment
phrases, fallbacks, appearance, reject rules and score floors), Fragility flags,
Difficulty and reliability, Cross-refs. Link [[id]] in the body only.

Write each new global lesson to {{memory_inbox}}/new_global_<kind>_<slug>.md.
Use a bare 2–5 word kebab-case id, kind primitive|perception|strategy|failure,
an imperative title, symptom search terms and related bare IDs. Include a claim,
Why (or observed, cause unknown), How to apply, Falsify and Related.
Check existing leaf bodies first. For matching evidence append id, cell,
effect:"confirmed" and note to corroborations.jsonl in the inbox. For conflicts
write conflict_<id>.md there with both claims, conditions and measured evidence.
In finish report counts by layer, corroborations and conflicts."""


def system_prompt(variables: Mapping[str, object] | None = None) -> PromptNode:
    """Build the exploration workflow with LIBERO attempt and archive rules."""
    variables = variables or {}
    enabled = bool(variables.get("enable_direct_action"))
    budget = variables.get("attempts_per_session")
    handoff = (
        f"This session has {budget} attempts. With a positive limit, finish is "
        "refused on an unsolved cell until the last attempt. Archive and reset "
        "with a changed plan while attempts remain."
        if budget
        else "When there is no attempt limit, hand off with notes once you have "
        "exhausted the approaches you can test productively."
    )
    return explore.system_prompt(
        role=base.ROLE + "\n" + explore.SESSION,
        runtime=base.RUNTIME,
        initialization="\n\n".join(
            (
                base.READ_GUIDES,
                base.INSPECT_INITIAL,
                READ_MEMORY,
                base.READ_SEED0,
            )
        ),
        perception=base.PERCEPTION,
        action=base.allowed_primitives(enabled)
        + "Also allowed: `reset` after archiving.",
        action_model_guidance=base.PI0_ACTION,
        recovery="\n\n".join(
            (handoff, base.RECOVERY, RETRY, explore.FAILED_ATTEMPT, ARCHIVE)
        ),
        success="\n\n".join((AUDIT, MEMORY)),
    )
