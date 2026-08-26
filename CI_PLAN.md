# Initial CI Plan

Status: confirmed planning draft. This document defines the intended scope and
rollout; it does not itself introduce workflows or change the test suite.

## Context and Reference

RPent has been under active development for roughly three months without a CI
baseline. The initial setup should establish a comprehensive offline contract
suite now, rather than deliberately narrowing the suite and expanding it only
after regressions occur.

AgentScope is the primary workflow reference:

- keep pre-commit and unit tests as two simple required workflows;
- use Python 3.11 on Ubuntu;
- install dependencies with uv without committing a lock file solely for CI;
- run provider-facing tests with fakes rather than real services.

RPent will not copy AgentScope's multi-OS matrix or add unrelated repository
automation in this change.

## Supported Installation Model

RPent is supported from a complete source checkout. A standalone wheel is not a
supported runtime or an objective of this CI setup.

In particular:

- the top-level `robots/` tree remains outside the wheel;
- robot guides and configuration data remain in the source tree;
- curated memory remains external data hosted on Hugging Face and is fetched by
  the existing source-checkout runtime;
- memory, results, logs, checkpoints, and other generated data are never package
  data;
- CI does not build a wheel, install one into an isolated environment, or imply
  that its CLI and robot registry work without the source checkout.

Source-checkout tests still cover `import rpent`, CLI help, robot discovery,
configuration, and registration. Future packaging work must begin with a new
explicit design decision; it is not part of either pull request below.

## Goals

The initial CI should:

- run on every pull request and on pushes to `main`;
- use Ubuntu and Python 3.11 only;
- give each required job a ten-minute timeout;
- require no API keys, GPUs, model weights, simulators, robot runtimes, or
  external services;
- make the repository's full pre-commit configuration clean and required;
- replace the existing tests with a comprehensive offline unit and contract
  baseline;
- test stable behavior and public contracts rather than incidental internal
  structure;
- make it clear how contributors can run the same checks locally.

The initial setup will not add coverage collection, a Python or OS matrix,
nightly workflows, release automation, README badges, PR-title enforcement,
stale-issue automation, or real simulator and model-service tests.

## Required Workflows

Use two workflow files, following AgentScope's simple separation:

- `.github/workflows/pre-commit.yml`, with the required check named
  **Pre-commit**;
- `.github/workflows/unittest.yml`, with the required check named
  **Unit tests**.

Both workflows trigger on every pull request and on pushes to `main`. They do
not initially add path filters, explicit permissions, concurrency cancellation,
or custom caching. Each job has `timeout-minutes: 10`.

### Pre-commit

Run the complete repository-content configuration with:

```bash
pre-commit run --all-files
```

This workflow becomes required immediately after it is merged. Before enabling
it, the repository baseline must be made clean:

- resolve the currently observed Ruff findings (approximately 150 at planning
  time);
- apply the currently required Ruff formatting changes (approximately 59 files
  at planning time);
- add the full Apache 2.0 header required by `CPY001`, following RLinf's style;
- use `# Copyright 2026 The RPent Authors.` for all applicable existing files
  and the creation year for new files;
- keep Ruff lint and formatting hooks in the `pre-commit` stage, where they run
  automatically for local commits and in the all-files CI job;
- follow RLinf's commit policy by putting `check-message` and
  `check-commit-signoff` in the `commit-msg` stage, and configure local
  installation for both the `pre-commit` and `commit-msg` hook types;
- keep the CI command on the default `pre-commit` stage so that
  `pre-commit run --all-files` checks repository content without inspecting the
  CI runner's commit message or Git identity.

The cleanup is intended to preserve behavior. Mechanical formatting should be
kept reviewable, public re-exports must be preserved, and any lint finding whose
fix changes behavior must be discussed separately instead of being hidden in
the cleanup.

### Unit tests

Install the source checkout in editable form with a small `test` dependency
group. That group should contain only:

- `pytest`;
- `pytest-timeout`.

Pre-commit is installed by its own workflow. Do not introduce a broad `dev`
extra, a CI-only `uv.lock`, or the `build` package. Use uv in the same unlocked
`uv pip install` style as AgentScope.

Configure pytest to import directly from the complete source checkout:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
timeout = 60
```

This makes the repository root, including the intentionally unpackaged
top-level `robots/` tree, explicit on the pytest import path. The
`pytest-timeout` setting limits each test to 60 seconds, independently of the
workflow's ten-minute job timeout. Do not add `testpaths`, global `addopts`, or
speculative marker configuration initially.

Run the complete offline suite directly with pytest:

```bash
pytest tests -v
```

Do not collect or upload coverage and do not configure a coverage threshold in
the initial setup. It can be introduced later when the project has a concrete
use for the report or a deliberately chosen enforcement policy.

## Test-suite Replacement

Delete the three current test files and build the baseline from zero. They do
not constrain the new design and do not need to be migrated first.
Memory tests are removed here and will be re-planned together with the upcoming
memory configuration change; they are intentionally absent from this baseline.

Use a component-oriented layout suitable for the planned suite:

```text
tests/
  core/
  robots/
  planner/
  dashboard/
  test_cli.py
```

Keep `tests/` and its component directories as non-package directories: do not
add `__init__.py` files anywhere in this tree. Because pytest's default import
mode imports these as top-level modules, every test module filename must be
globally unique across the entire `tests/` tree. Treat a duplicate basename as
an invalid test layout rather than turning the directories into packages.

The acceptance matrix below is a contract checklist, not a fixed target number
of tests. Parameterization and shared fixtures should be used where they keep
failures clear.

### Core toolkit contracts

Cover the public behavior of `ToolResult`, `Toolkit`, and common tools:

- convert ordinary results, text, and image payloads into the expected content
  blocks without mutating inputs;
- apply the result text limit as actual UTF-8 bytes and include Unicode boundary
  cases;
- register common tools and substitute output-directory schema placeholders
  without mutating the original schemas;
- recognize readonly functions, bound methods, and nested partials;
- dispatch valid calls and report unknown tools or invalid arguments clearly;
- capture state and emit step events only where the contract requires it;
- retain the original handler error if state capture also fails;
- reject overlapping stateful operations and exercise cooperative cancellation;
- prove that operation state is cleaned up after success, failure, and
  cancellation.

Use deterministic in-memory fakes and `threading.Event` gates. Apply
`pytest-timeout` so a broken concurrency path cannot hang the workflow.

### State and artifact contracts

Cover `EnvState` and `StepRecord` without simulator dependencies:

- serialization, optional fields, ordering, copying, and latest-step behavior;
- artifact-name and path restrictions;
- run-level and per-step save/load/exists/path behavior;
- round trips for supported lightweight formats, including JSON/JSONL, NumPy,
  text, images, and bytes;
- manifest updates, deterministic ordering, and temporary-file cleanup;
- step lifecycle, nested-step rejection, reset behavior, and failure cleanup.

MP4 tests cover only the bytes path. Frame encoding through an ffmpeg backend is
outside required CI.

### Robot, configuration, and CLI contracts

Exercise all three robots from the source checkout without starting a runtime:

- discover exactly LIBERO, RoboCasa, and RoboTwin and register them through the
  public registry;
- validate `RobotSpec`, `RunConfig`, prompt, dashboard, and runtime-contract
  metadata;
- validate shared tool-schema invariants without snapshotting entire prose
  descriptions;
- construct all three toolkits with fake primitives and verify their intended
  tool sets, readonly/stateful classification, initial observation, and
  exploration/evaluation differences;
- cover each robot's defaults, representative valid configurations, invalid
  combinations, environment-derived values, and CLI/dashboard parsing
  differences;
- cover shared CLI defaults, `--robot`/deprecated `--env` routing, validation,
  transcript image stripping, and handoff messages;
- run public CLI help from the repository checkout, including robot-specific
  help, without importing optional simulator packages.

Tests may fake robot primitives and runtime metadata, but must not invoke robot
actions, reset environments, launch servers, probe ports, or validate external
assets and models.

### Planner adapter contracts

Test the API, Claude Code, and Codex planners offline:

- share fake toolkit/result cases for schema mapping, dispatch, text, images,
  errors, and successful or rejected finish calls;
- enforce mutual exclusion of queue and dashboard inputs before backend side
  effects;
- cover successful results, backend failures, timeout, cancellation, turn and
  tool-call accounting, usage, and transcript events;
- ensure a finish call ends a run only after the corresponding successful tool
  result;
- test provider-specific option/configuration translation and lifecycle cleanup;
- ensure image suppression and transcript serialization do not leak embedded
  image data.

Use local Pydantic AI test/function models for the API planner, a fake SDK client
and finite event stream for Claude Code, and fake Codex/thread/turn/event objects
for Codex. Never rely on missing credentials as the isolation mechanism.

For Codex MCP support, test conversions and a fake `HttpMcpServer`. Do not start
a real loopback server in this baseline.

### Dashboard planner-control contracts

Test the pure in-memory `DashboardPlannerControl` behavior needed by the planner
adapters:

- submit, acknowledgement, busy/idle, flush, replacement, and sealing behavior;
- cancellation ordering between toolkit work and backend interruption;
- failure recovery and cleanup when planner or session operations fail;
- restoration of API messages that were queued but never started.

Do not test the Dashboard HTTP server, browser UI, or complete session/runtime
stack in required CI.

## Explicit Exclusions

Required CI must not execute or contact:

- LIBERO, RoboCasa, RoboTwin, MuJoCo, CUDA, GPUs, real robot primitives, or
  environment/runtime servers;
- RPC endpoints, sockets, subprocess daemons, or port discovery;
- Hugging Face downloads, real memory synchronization, external assets, model
  weights, or checkpoints;
- real API providers, Claude Code, or Codex processes and cached logins;
- full Dashboard HTTP/UI sessions;
- full CLI planner/run loops;
- MP4 frame encoding.

Do not create `integration` or `manual` pytest markers merely for future tests.
Heavy validation remains outside the required suite and should be described in
the pull request when it is actually performed. Add marker and workflow
machinery only when concrete automated integration tests exist.

## Implementation-time Contract Questions

The audit found several product behaviors that a sound baseline should not
silently freeze. Record them as implementation-time discussions; this plan does
not authorize a particular code change:

1. `EnvState.record_step` currently catches `BaseException` and can leave
   artifacts behind despite its rollback contract.
2. `rpent --robot libero --help` parses help before robot-specific arguments are
   added, so the expected options are absent.
3. A missing optional dependency inside a robot module can be reported as an
   unknown robot.
4. The terminal Codex path does not currently enforce `max_turns` or stop after
   a successful finish.
5. The API planner tracks a pending finish without associating it with its tool
   call ID, which is ambiguous under concurrent tool results.
6. `ToolResult.MAX_TEXT_BYTES_IN_RESULT` is described in bytes but currently
   behaves like a character limit; the agreed contract is UTF-8 bytes.

When implementation reaches one of these cases, present the concrete change
and its compatibility impact for confirmation before fixing product behavior.

## Contribution Guidance

Add a concise root-level `CONTRIBUTING.md` and a short pull-request template with
the workflows. They should cover:

- exact commands for running pre-commit and tests locally;
- the Conventional Commit and `Signed-off-by` policy, including use of
  `git commit -s`;
- test layout and naming;
- source-checkout-only operation and heavy dependency isolation;
- expected tests for features, bug fixes, refactors, and intentional contract
  changes;
- a short checklist for adding a Planner, Robot, or Tool integration;
- how to report manual verification when automation is impractical.

A feature should cover its principal success path and an important failure or
boundary. A bug fix should include a regression test. Tests must be
deterministic, independent of execution order, and isolated from developer
credentials, configuration, and files.

README badges are not part of the initial change.

## Rollout

Use two pull requests.

### PR 1: make full pre-commit clean

- resolve the repository-wide lint findings;
- apply Ruff formatting;
- add/fix the Apache copyright headers;
- keep Ruff in the `pre-commit` stage, put commit-message and signoff checks in
  `commit-msg`, and configure both hook types for local installation so the CI
  all-files run checks repository content only;
- preserve behavior and defer semantic product changes for explicit discussion;
- self-review the full mechanical diff before merging.

This PR does not package `robots/`, redesign resources, add tests, or enable a
workflow.

### PR 2: replace tests and enable CI

- add the small `test` dependency group;
- add the minimal pytest `pythonpath = ["."]` and `timeout = 60`
  configuration;
- delete the three current test files;
- keep test directories free of `__init__.py` and enforce globally unique test
  module filenames;
- add the comprehensive source-checkout contract suite described above;
- add the Pre-commit and Unit tests workflows;
- add `CONTRIBUTING.md` and the pull-request template;
- run the exact workflow commands locally and confirm both checks pass;
- make **Pre-commit** and **Unit tests** required after merge.

Large-scale baseline tests and their workflow intentionally land together so
that the required check starts from a complete, passing suite.
