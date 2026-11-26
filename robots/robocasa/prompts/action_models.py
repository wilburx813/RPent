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

"""RLDX-1 call and history rules for RoboCasa."""

VLA_RULES = """Every rldx_skill / rldx_arm call must pass the complete live task_language
verbatim. Never shorten, paraphrase, or substitute an atomic sub-task. Omit
max_chunks (ordinary default 70, Target50 fixes 40) and settle_patience
(default 999). Vary the number of calls based on progress; keep these per-call
settings even when memory records a different duration.

Inspect RGB-D and task_progress after each call. On contact, a held object,
fixture progress, or a rising task counter, continue the identical full-task
call without inserting manual commands, which erase VLA frame history. A cap
alone is inconclusive: repeat the full-task call once after the first
no-contact, no-progress result. Only after two
consecutive calls with no contact and no visible semantic progress should
you re-localize and make a bounded free-space re-stage before trying again.
A true vla_desync in view_env_state means the next call starts fresh."""
