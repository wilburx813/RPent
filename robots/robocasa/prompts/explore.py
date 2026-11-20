# Copyright 2026 The RPent Authors.
"""RoboCasa multi-attempt exploration prompt."""

from robots.robocasa.prompts import evaluate as base
from rpent.prompt import explore

ROLE = """Treat RoboCasa benchmark tasks as solvable."""

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

RECOVERY = """Reset only for an unrecoverable or deliberately completed experiment;
inspect all cameras after reset. An unsolved finish is refused while attempts remain."""

REPORTING = """Write the audit to {{output_dir}}/{{recipe_tag}}.json and memory drafts
directly under {{memory_inbox}}/. Use suite: robocasa, regime: {{split}},
task_id: {{task_name}}, evidence.cells [{{recipe_tag}}], attempts and seed
lists for seed {{seed}}. Include recognition cues, order, parameter ranges,
task_progress milestones and the failure table. The runner exports commands
after the last reset and merges validated drafts."""

USER_MODE = explore.ATTEMPT_LIMIT


def system_prompt() -> dict[str, str]:
    return explore.system_prompt(
        role=f"{base.ROLE}\n{explore.SESSION} {ROLE}",
        initialization=f"{base.START}\n\n{MEMORY}",
        perception=base.PERCEPTION,
        action=base.ACTION,
        action_model_guidance=base.VLA_RULES,
        recovery=f"{explore.FAILED_ATTEMPT}\n{RECOVERY}",
        success=f"{base.VERDICT}\n\n{REPORTING}",
    )
