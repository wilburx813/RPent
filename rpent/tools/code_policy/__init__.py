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

"""Execute policies through the existing tools or a persistent Python session."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rpent.tools.base import ToolProvider
from rpent.tools.code_policy.prompt import code_policy_prompt


@contextmanager
def policy_tools(
    toolkit: ToolProvider,
    *,
    mode: str,
    output_dir: Path,
    timeout_s: float = 120.0,
    max_calls: int = 100,
    include_images: bool = True,
) -> Iterator[ToolProvider]:
    """Borrow the toolkit and close only the code session when it is enabled."""
    if mode == "tools":
        yield toolkit
        return
    if mode != "code":
        raise ValueError(f"Unknown policy mode: {mode}")
    from rpent.tools.code_policy.toolkit import CodePolicyTools

    provider = CodePolicyTools(
        toolkit,
        output_dir=output_dir,
        timeout_s=timeout_s,
        max_calls=max_calls,
        include_images=include_images,
    )
    try:
        yield provider
    finally:
        provider.close()


__all__ = ["code_policy_prompt", "policy_tools"]
