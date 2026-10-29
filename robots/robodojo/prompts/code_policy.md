<!-- Adapted from PyRUA-Lean, Apache-2.0. -->

# Operating knowledge for RoboDojo

## Observe and localize

Two ARX-X5 arms, left and right, stand side by side at the near edge of a table.
World positions use metres, with z up. Read the current frame, end-effector poses
and camera calibration from `robo.view_env_state(step=-1)`; its `task_language`
is authoritative. Read object heights from the scene, never assume them.
Use `segment` and `back_project` on the recorded images, with keyword arguments
from the API reference. Head and wrist views must describe the same candidate.
Check returned fields before using a localization: a point on a rim, an arm or
background is not the object's centre. Re-localize after contact or scene changes.

## Motion and gripper

Use the registered `move_to(xyz=..., arm=..., gripper=...)` tool. The current
RPent tool commands an end-effector position; do not apply a separate SDK grasp
point offset or pass unsupported orientation, path or speed arguments.
Approach high, descend in small observed increments and retreat straight up
before travelling. Keep the other arm and surrounding objects clear.

Commands are signed: gripper=1 closes/holds, -1 opens and 0 keeps the command
where supported by the tool schema. Carry with gripper=1. A closed gripper alone
proves nothing: verify that the target leaves its place and moves with the arm.
Use `set_gripper(arm=..., gripper=...)` to open or close. Inspect the actual result
and fresh visual evidence; do not assume a full stroke or an adjustable opening.

## Skills and feedback

Use `pi0_pick` for grasping when registered. Treat its success signal as a
provisional heuristic, then verify the object in the wrist/head images and
whether it moves with the arm. Use bounded recovery: change the description,
approach or staging after a failure, rather than repeating the same attempt.
The original motion result is in the returned observation's `log.result`.
Check its error/outcome fields and the observation after every step.

## Judging progress

The benchmark judges the final scene. Do not invent a live task-success flag.
A named lift amount is measured on the object, not the gripper: held objects can
sag or slip. During transport the hold must remain stable. For placement, the
object must rest at the requested destination after opening and withdrawing;
an object on a rim or beside its destination is not placed.

Check every object named by the instruction, the exact requested relation and
orientation, and whether other fixtures or objects were disturbed. A nearly
completed arrangement is insufficient. For pushing/sliding tasks, lifting the
object may violate the instruction. Re-localize and correct the remaining error
while budget remains. Restore arms and open grippers when required by the task,
using only registered tools; there is no assumed `home` helper.

## Recovery and budget

Inspect the scene after motion. Stop the current plan if an object is unstable
or an arm is obstructed. Identify the failed phase: wrong object, missed grasp,
lost hold, unreachable target or premature release. Change one meaningful
variable and verify. Do not repeat the same unsuccessful recovery indefinitely.
Recover in the current scene; use a reset only when explicitly provided and
permitted by this run. Finish when the scene meets the instruction, or report
failure/stuck when no justified recovery remains.
