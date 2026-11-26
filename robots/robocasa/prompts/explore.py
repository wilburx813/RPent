# Copyright 2026 The RPent Authors.
"""RoboCasa multi-attempt exploration prompt."""

ROLE = """MULTI-ATTEMPT EXPLORE: You are agent {{session_number}} of up to
{{session_max}} on this cell. Treat the task as solvable and failures as
evidence about the approach tried."""

MEMORY = """
Before acting, use `list_dir` directly on `{{memory_dir}}/task-specific/`,
`{{memory_dir}}/task-family/`, and `{{memory_dir}}/global/` to find published
memory. Use `read_text_file` to read the most task-specific RoboCasa entry
first, then only task-family/global entries whose applicability matches this
task. Check `{{memory_inbox}}/wip/` directly for handoff notes from earlier
sessions. These directories may not exist yet; if `list_dir` reports
`directory not found` or an empty listing, skip that location. Do not browse
`{{memory_dir}}/_internal/` or `{{memory_dir}}/_internal/inbox/`; within
`_internal/`, only the current inbox `{{memory_inbox}}/` and its contents are
accessible.
"""

RECOVERY = """Before reset, first write
`{{output_dir}}/attempts/attempt_<N>_failed.json`. Record the attempt number,
initial plan, commands and parameters tried, observed progress, bounded failure
mechanism, and the next lever (stance, ordering, contact geometry, primitive
family, or action parameter). Append that evidence to
`{{memory_inbox}}/wip/notes.md`. Reset only for an unrecoverable or
deliberately completed experiment. Inspect all cameras in the new episode.
An unsolved finish is refused while a positive attempt budget has attempts left."""

REPORTING = """Write the winning audit to `{{output_dir}}/{{recipe_tag}}.json`.
Keep working notes in `{{memory_inbox}}/wip/`; put proposed task-family and
global Markdown files directly under `{{memory_inbox}}/`. For task-family
frontmatter set suite: robocasa, regime: {{split}}, task_id: {{task_name}} and
task_language to the verbatim initial instruction. For both types set
evidence.cells to [{{recipe_tag}}] and include attempts, solved_seeds and
failed_seeds for the recorded runs (this seed is {{seed}}).

For task-family proposals include recognition cues, technique, ordering,
robust parameter ranges, task_progress milestones and a failure table.
Reserve global proposals for cross-task lessons with observed evidence and
applicability. Mark unknown causes explicitly. Consolidate the inbox before
finish. The runner exports the winning commands after the final reset and
merges validated proposals into the published corpus."""
