# Copyright 2026 The RPent Authors.
"""Select the clean builds and simulator suites affected by a Git diff."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def load_suite_maps(
    root: Path,
) -> tuple[dict[str, list[str]], dict[str, set[str]], dict[str, str]]:
    """Discover component->suites, optional_model->components, and suite->component."""
    suites_by_component: dict[str, list[str]] = {}
    optional_by_model: dict[str, set[str]] = {}
    component_by_suite: dict[str, str] = {}
    suites_dir = root / "tests/e2e_tests/suites"
    if suites_dir.is_dir():
        for path in sorted(suites_dir.glob("*.toml"), key=lambda p: p.stem):
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            suite_name = path.stem
            component = data["component"]
            suites_by_component.setdefault(component, []).append(suite_name)
            component_by_suite[suite_name] = component
            for model in data.get("optional_models", []):
                optional_by_model.setdefault(model, set()).add(component)
    return suites_by_component, optional_by_model, component_by_suite


_REPO_ROOT = Path(__file__).resolve().parents[2]
SUITES, OPTIONAL, _ = load_suite_maps(_REPO_ROOT)


def targets(paths: list[str], root: Path) -> list[str]:
    """Map shared code to all suites and component code to its consumers."""
    suites_map, optional_map, suite_to_component = load_suite_maps(root)
    manifests = {}
    owners = {}
    for pattern in ("robots/*/component.toml", "components/*/*/component.toml"):
        for path in root.glob(pattern):
            manifest = tomllib.loads(path.read_text(encoding="utf-8"))
            owners[path.parent.relative_to(root).as_posix()] = manifest["name"]
            manifests[manifest["name"]] = manifest.get("requires", [])
    users: dict[str, set[str]] = {}
    for robot in suites_map:
        pending = [robot]
        seen = set()
        while pending:
            name = pending.pop()
            if name not in seen:
                seen.add(name)
                users.setdefault(name, set()).add(robot)
                pending.extend(manifests.get(name, []))

    selected: set[str] = set()
    for filename in paths:
        name = filename.removeprefix("tests/unit_tests/")
        if (
            name.startswith(("docs/", ".agents/", ".claude/"))
            or name.endswith((".md", ".rst"))
            and not name.startswith(("robots/", "rpent/", "components/"))
        ):
            continue
        if name.startswith("tests/e2e_tests/suites/") and name.endswith(".toml"):
            suite_stem = Path(name).stem
            if suite_stem in suite_to_component:
                selected.add(suite_to_component[suite_stem])
                continue
        parts = name.split("/")
        if name.startswith("tests/e2e_tests/") and len(parts) > 3:
            name = "robots/" + parts[2] + "/" + "/".join(parts[3:])
        component = next(
            (owner for owner in owners if name.startswith(owner + "/")), None
        )
        if component:
            selected.update(users.get(owners[component], ()))
            if component in {"robots/libero", "components/sim/libero"}:
                selected.add("robot-libero_plus")
            if component.startswith("components/models/"):
                selected.update(optional_map.get(component.split("/")[-1], ()))
        elif name.startswith(
            (
                "rpent/",
                "components/",
                "robots/",
                "tests/e2e_tests/",
                ".github/workflows/",
            )
        ) or name in {
            "setup.py",
            "pyproject.toml",
            "MANIFEST.in",
            "rpent-install.sh",
            "tests/tooling/ci_targets.py",
            "tests/tooling/run_ci_jobs.py",
        }:
            selected.update(suites_map)
    suites = [
        suite
        for component in suites_map
        if component in selected
        for suite in suites_map[component]
    ]
    return suites


if __name__ == "__main__":
    base, head = sys.argv[1:]
    if base and set(base) != {"0"}:
        raw = subprocess.check_output(
            ["git", "diff", "--no-renames", "--name-only", "-z", base, head]
        )
        paths = [os.fsdecode(path) for path in raw.split(b"\0") if path]
    else:
        paths = ["rpent-install.sh"]
    suites = targets(paths, Path.cwd())
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        print(f"suites={json.dumps(suites)}", file=output)
        print(f"suites: {', '.join(suites) or 'none'}")
