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

"""System prompt section bodies for the LIBERO perception-isolated agent."""

from __future__ import annotations

from collections.abc import Mapping

from rpent.prompt import evaluate
from rpent.prompt.utils import PromptNode

ROLE = """Control LIBERO in perception-isolated mode. The authoritative instruction is the
initial state's `task_language`; object names contain no world coordinates."""

RUNTIME = """Each state record exposes `step`, top-level `task_language`,
`terminated`, `truncated`, coord-free `state`, an `artifacts`
list of logical base names, and a `log`. Storage paths are internal; do not
construct or parse them.

Canonical observation keys include `agentview_policy.png`, `agentview.png`,
`agentview_high.png`, `agentview_depth.npz`, `agentview_world.npz`,
`agentview_world_high.npz`, `agentview_metadata.json`, `wrist.png`,
`wrist_high.png`, `wrist_depth.npz`, `wrist_world.npz`,
`wrist_world_high.npz`, and `wrist_metadata.json`.

Use `view_env_state` to retrieve a record. It embeds the policy image and the
best available agentview and wrist images, preferring the matching `*_high.png`
artifact. Use `view_camera_meta`, `back_project`, and `segment` to consume
metadata and world maps without opening artifacts directly. Step `0` is the
initial state; step `-1` selects the latest state.
The runner owns all servers. Call the structured tools even if the planner
namespaces them. Never read BDDL, import the benchmark or query environment
poses or ground-truth lift oracles. Never use exit, set_object_pose, articulate_to,
js_move_to or carry_object."""

READ_GUIDES = """READ THE GUIDES once each:
- `robots/libero/guides/strict_hybrid_guide.md`
- `robots/libero/guides/pro_hybrid_guide.md`
- `robots/libero/guides/env_calibration.md`"""

INSPECT_INITIAL = """INSPECT INITIAL STATE: call `view_env_state({"step": 0})`; inspect
  `task_language`, object_names, eef pose, `agentview_high.png`,
  `wrist_high.png` if useful, and call `view_camera_meta` if needed. Identify ALL target
objects, destination surfaces, and relation landmarks named by task_language."""

READ_MEMORY = """READ MEMORY: scan {{memory_dir}}/MEMORY.md and list global/ and task-family/ under
{{memory_dir}}. Read candidate leaves by object, fixture, relation and order.
Consult them even when a seed-0 recipe exists. Record exact filenames or
"no matching task memory found" in strategy_notes."""

READ_SEED0 = """READ SEED-0 STRATEGY REFERENCES if present: {{memory_dir}}/task-specific/{{reference_tag}}.json and
{{memory_dir}}/task-specific/{{reference_tag}}_recipe.jsonl for the seed-0
strategy, Pi0 prompt ladder and qualitative targets. Older recipes may use oracles."""

READ_LOCAL_MEMORY = """READ EACH AVAILABLE LOCAL MEMORY LAYER for the observed `task_language`:
- task audit: `{{memory_dir}}/task-specific/{{reference_tag}}.json`
- task recipe: `{{memory_dir}}/task-specific/{{reference_tag}}_recipe.jsonl`
- task-family leaf: find the matching task/regime leaf under `{{memory_dir}}/task-family/`
  (for example, task-family_libero10_<regime>_t{{task}}.md)
- global index: `{{memory_dir}}/MEMORY.md`, then only relevant leaves under
  `{{memory_dir}}/global/`

If a layer is absent, state that explicitly and continue with the available
validated layers. Record the exact files used in final `strategy_notes`. Treat
absolute coordinates as stale and re-derive them from this scene.
Never read `_internal/` during evaluation."""

LOCALIZATION = """Use agentview_high.png (1024x1024) and back_project(row, col, step).
For the 256x256 fallback agentview.png pass resolution="low". Use surface
world_xyz for xy; sample bare table for resting z (~0.9 kitchen, ~0.42 table-top).
Apply the task's measured manipulation offset to the perceived position."""

PERCEPTION_ALGORITHM = """Agentview selects identity; wrist refines geometry. Choose duplicates by
relation rather than _1/_2. Use side labels, package shape and layout for groceries.
For each target, fixture and landmark, median 3–8 high-resolution back_project
samples. Move 15–20 cm above that anchor. Accept wrist xy for the same object
within 3–5 cm; reject shifts over 5 cm. For baskets use the wrist to confirm
the interior center and remeasure if the basket slides.
Before manipulation record name_or_role, agentview_evidence, agentview_pixels_rc,
agentview_xyz, wrist_refine (accepted/rejected/basket_confirmed and xyz),
final_xyz and uncertainty. Resolve ambiguous identities before handing control
to Pi0. Update the table when objects move."""

SAM3 = """segment takes either a text prompt or point=[row,col]. Use visible colour,
shape and relation ("black bowl on the stove"); brand/BDDL names score poorly.
Inspect overlay_artifact and median world_xyz. Wrist segmentation can refine
a parked view to 1–2 cm. On a low score or error, rephrase or use back_project."""

TARGETING = """For duplicate bowls, elevation about 0.03–0.06 m above the table distinguishes
a bowl sitting on a box. Compare back-projected world xy for lateral relations.
Classify destination surfaces in RGB: plates have ceramic rims; stove burners
have metal coil/grate rings on a fixture. If clean placement does not terminate,
check whether the object or surface was a look-alike before changing the motion."""

POLICY = """For pick/place, use pi0_pick for the grasp, then script the carry and release.
Start with max_chunks=20, lift_thresh=0.05, gripper_closed_thresh=0.06 unless
the matched task technique specifies otherwise. pi0_pick.success is an eef-lift
and closure heuristic. Check robot0_gripper_qpos (roughly 0.01–0.05 gap when
holding, ~0 when empty), wrist_high.png after lift and the vacated source.
If needed, back_project the target's surface to check the increase in z.
For a missed grasp, try “pick up the {object}”, verbatim task_language, then
a spatial qualifier, then re-position (lower z or offset xy by 5 cm) and retry.
For drawer/door articulation, knob turns and insertion, use pi0_doubled for
contact and alternate with short capped OSC pushes/alignment as needed.
pi0_doubled checks terminated, independently of gripper closure or lift;
disregard historical claims that this contact tool is unavailable."""

PROVEN_LEVERS = """Seed-0 libero_10 techniques for matching tasks; re-localize this scene.

CRITICAL MECHANICS (cost many wasted attempts before they were nailed):
- **GRIPPER SIGN**: in `move_to` / `set_gripper`, `gripper:+1` = CLOSE/hold,
  `gripper:-1` = OPEN. To CARRY a grasped object, hold `gripper:+1` the whole way
  (carrying with `-1` silently OPENS and drops it — the #1 early bug). `set_gripper +1`
  (steps 8-12) firms the grip after a pick; for a laterally-weak CAN use steps<=5.
- **`move_pose` defaults gripper to OPEN (-1) if you omit it** — always pass
  `"gripper":1` in `move_pose` while holding an object.
- **`move_pose` threads the OSC IK singularity that `move_to` walls at** — for
  cabinet-front / microwave-cavity / deep reaches, when `move_to` stalls
  (final_dist stays high, eef retreats), switch to `move_pose` (co-vary
  xyz+pitch+yaw). It reaches several cm deeper.

GRASPING:
- **MUGS / BOWLS / CUPS grasp at the RIM, not the center**: SAM3/back-projection
  give the object CENTER; closing the gripper there grabs air. Aim
  `eef_y = object_y + 0.045` so Pi0 rim-hooks. (Mugs do NOT hang 4.5cm in -y like
  bowls — you can wrist-segment the grasped object to measure the true held offset.)
- Some objects grasp best with `pi0_pick` from the **DEFAULT HOME pose** (no
  pre-position) — Pi0 has its own approach trajectory; pre-positioning can hurt.
- **`pi0_pick` is reusable and repurposable**:
  a HIGH `lift_thresh` (e.g. 999) + `gripper_closed_thresh:0` turns it into a
  generic closed-loop CONTACT skill (used to turn the stove knob).
- **`pi0_doubled`** = Pi0 closed-loop CONTACT skill (success :=
  `terminated`). Use it for drawer/door open-close AND insertions; call it
  repeatedly.

DISAMBIGUATION / TARGETING:
- **SWAP-PERTURBED scenes (suite `*_swap`)**: the seed-0 reference's COORDINATES
  are STALE (swap re-randomizes object positions per seed), and some s0 swap
  recipes contain a literal reset — that was the old multi-attempt era UNDOING A
  WRONG-OBJECT FIRST GRAB. For swap cells the following restriction supersedes ordinary recipe transfer. Use the s0 ref ONLY for: WHAT the
  targets are (task_language nouns), what they LOOK like, and which Pi0 prompt
  finally worked — never for positions, never replay its command list.
  Pre-position above the agentview-identified, wrist-refined target before
  pi0_pick: Pi0 can confuse brand names and a wrong grab can tip nearby groceries.
- **"left"/"right" in libero_10 is EGOCENTRIC (robot frame): +y = robot-LEFT =
  image-RIGHT.** A geometrically-perfect placement of the WRONG target never fires
  the predicate — when a clean placement won't terminate, SUSPECT WRONG-TARGET
  before wrong-physics (this turned a "physically impossible" verdict into a solve).
- Containers can be MOVABLE (e.g. a basket slides when bumped) — descend into the
  interior CENTER from straight above, not against the rim; SAM3's centroid of a
  frame-clipped/reflective container is rim-biased, so derive the true cavity
  center from the woven-rim pixels.

PER-TASK RECIPES THAT WORKED AT SEED 0 (adapt coords to your seed):
- 2-items→basket (t0,t1,t7): place the BOX first into the EMPTY basket interior
  (descend deep, release), then drop/`pi0_pick`-lift the CAN in beside it; a
  rim-perched item can be seated with a closed-gripper downward push.
- mugs→plates (t4) / mug→plate (t6): rim-grasp, +1-hold carry, descend until the
  mug rests on the plate before release (high release → topples off).
  ⚠ t4 grasp safeguards (the seed-0 "win" used 2 resets. 8/9 multiseed cells died to the SAME chain: Pi0 rogue-place →
  tipped mug → unrecoverable cascade. Prevent it up front):
    1. GRASP-ONLY pi0_pick: short prompt ("grasp the yellow mug" — NEVER the full
       task_language) AND `max_chunks<=8`. With 20-25 chunks Pi0 keeps driving its
       trained pick-AND-PLACE and dumps the held mug at its own trained "left"
       (+y) or at the workspace IK edge (|y|>0.27 walls z>=0.56 — unreachable
       forever). Stop Pi0 at lift; if lift isn't reached within 8 chunks,
       RE-ISSUE pi0_pick rather than raising max_chunks.
    2. The instant lift is detected: `set_gripper +1` (steps 8-12) to lock the
       grip, then YOU script the entire carry + place.
    3. Measure the held-mug offset PER PICK by wrist-segmenting the HELD mug
       (offsets differ pick-to-pick: dy=-0.055 on one grasp, -0.013 on the next —
       measure each, never reuse). Place eef = plate_center − offset; descend to
       z~0.46 until the mug RESTS on the plate (OSC stalls ~0.51), then release
       and retreat STRAIGHT UP (step_clip 0.012).
    4. ORDER/PATH: after placing mug #1, plan mug #2's pick pre-position AND
       carry path so they NEVER pass over the placed mug (a graze re-tips it). A
       tipped mug is UNRECOVERABLE (no side-grasp primitive; Pi0 won't engage
       side-lying cylinders) — prevention is everything.
    5. Plates MOVE per seed (y=±0.21 at s0, ±0.30 at s8). For this
       plate-center estimate, measure the rim outline in the wrist view. Use
       x_range/y_range MIDPOINTS as the center; an individual rim depth or the
       median of the visible fragment gives an edge-biased placement target.
- stove (t2): turn the knob with `pi0_pick "turn on the stove", lift_thresh:999,
  gripper_closed_thresh:0`; then grasp the pan by its HANDLE, re-segment mid-carry
  to converge on the burner.
- moka→stove (t8): grasp body, carry LOW (~4cm lift) in tiny hops (step_clip
  0.006-0.01), re-clamp `set_gripper +1` between hops; "LEFT" = +y pot.
- bottle→bottom drawer + close (t3): the drawer In-region is SHALLOW
  (y≈0.075-0.227) — place at the MOUTH (y≈0.13), NOT the deep recess; `pi0_pick`
  the bottle from home pose, `rotate_pitch` it flat ALONG X (the wide footprint),
  release at the mouth, ONE short +y push seats it AND closes the drawer.
- mug→microwave + close (t9): the only UNSOLVED seed-0 cell — the round mug-in-hand
  walls ~3cm short of the In() threshold (deep narrow cavity). Try every lever
  (`pi0_doubled`, `move_pose`, push) and if it still walls, write an honest
  `terminated:false` with the max eef-y reached."""

KEY_HYPERPARAMETERS = """- Single-step xy within ±0.30 or OSC flips IK; split long traversals.
- lift_thresh 0.05 (flat) / 0.08 (slippery tall bottles).
- step_clip 0.025 (empty/box) / 0.015 (cans) / 0.012 (tall bottles).
- Frame: state.robot0_eef_pos[2] ≈ 0.68 LIVING_ROOM / 1.17 KITCHEN / 0.26 object.
- BOWL: eef_y = plate_y + 0.045. The LIBERO tall-bottle drop is an exception to the supported-release rule:
  carry z=0.30, drop without descending.
- Approach high-then-vertical; recover by re-pick, not hover."""

RECOVERY = """Re-position and retry pi0_pick on the next prompt-ladder rung. Split long
traversals into <0.30 m xy waypoints. For door/drawer/knob contact, use short
capped OSC pushes or pi0_doubled; a long push can produce MuJoCo NaNs."""

FINISH = """Write {{output_dir}}/{{recipe_tag}}.json with suite, task_id, seed,
regime:"strict_perception", strategy_notes (including localization), pick_result,
final_state from state, and terminated from the latest top-level result. On an
unsolved episode include the stalled step. Then call finish."""


def allowed_primitives(enable_direct_action: bool = False) -> str:
    """List motion tools available in this run, excluding mode-specific reset."""
    names = [
        "move_to",
        "pi0_pick",
        "pi0_doubled",
        "release",
        "set_gripper",
        "rotate_wrist",
        "rotate_pitch",
        "move_pose",
    ]
    if enable_direct_action:
        names.append("execute_action")
    return (
        "ALLOWED PRIMITIVES (physics-only; full schemas in the tool list/guides):\n"
        + ", ".join(f"`{name}`" for name in names)
        + ".\n"
    )


PERCEPTION = "\n\n".join((LOCALIZATION, PERCEPTION_ALGORITHM, SAM3, TARGETING))
PI0_ACTION = "\n\n".join((POLICY, PROVEN_LEVERS, KEY_HYPERPARAMETERS))


WAM_ROLE = (
    "You control a LIBERO robot using a WAM and scripted tools. "
    "Tool names may appear as mcp__rpent__<name> in SDK planners."
)

WAM_WORKFLOW = (
    "Use wam_act to execute "
    "bounded action chunks, then inspect the new state and images before "
    "continuing. Begin with the native full task by omitting prompt. "
    "Keep that instruction while progress is visible. Use a short, "
    "grounded subtask only to address an observed failure or lack of "
    "progress; the prompt applies only to that call. Start with one chunk "
    "and inspect before continuing (at most four per call). Each chunk "
    "executes the worker's returned actions; episode-end checks prevent the next chunk. wam_act "
    "does not stop when a grasp completes. Check subtasks visually; "
    "success and terminated refer to the full task, while truncated "
    "means the action budget is exhausted. "
    "For scripted motion, localize targets "
    "using back_project or segment; never invent coordinates. Gripper +1 "
    "closes and -1 opens. Preserve +1 while carrying an object."
)

WAM_OUTCOME = (
    "This is one evaluation episode. Do not reset it. Stop acting "
    "when the episode terminates or truncates. Report success only when the "
    "environment reports terminated=true. Call finish with the observed "
    "outcome; a model prediction alone is not evidence of task success."
)


def system_prompt(
    variables: Mapping[str, object] | None = None,
) -> PromptNode:
    """Build the evaluation workflow for the selected controller and corpus."""
    variables = variables or {}
    if variables.get("policy_kind") == "wam":
        return evaluate.system_prompt(
            role=WAM_ROLE,
            initialization="Inspect view_env_state at step 0 before using local memory.",
            action_model_guidance=WAM_WORKFLOW,
            success=WAM_OUTCOME,
        )
    memory = (
        READ_LOCAL_MEMORY
        if variables.get("memory_profile", "hf") == "local"
        else "\n\n".join((READ_MEMORY, READ_SEED0))
    )
    return evaluate.system_prompt(
        role=ROLE,
        runtime=RUNTIME,
        initialization="\n\n".join((READ_GUIDES, INSPECT_INITIAL, memory)),
        perception=PERCEPTION,
        action=allowed_primitives(bool(variables.get("enable_direct_action"))),
        action_model_guidance=PI0_ACTION,
        recovery=RECOVERY,
        success=FINISH,
    )
