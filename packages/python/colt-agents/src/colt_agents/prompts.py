"""The prompt registry (CLAUDE.md §15): `prompts/<agent>/<version>.md`.

Prompts are source-controlled files, not strings in code, so a prompt change is a reviewable
diff and every agent run can record exactly which version produced it (`AgentRun.prompt_version`).
"""

from __future__ import annotations

from pathlib import Path

from colt_agents.errors import PromptNotFoundError

#: `prompts/` lives at the repository root (CLAUDE.md §4), and every Make target that runs this
#: code (`make api`, `make worker`, `make test`) runs from there — the same assumption
#: `colt_workflows`'s own repo-relative paths make, just resolved from the working directory
#: rather than `__file__`, since this is a library function a real deployed process also calls.
_DEFAULT_PROMPTS_DIR = Path("prompts")


def load_prompt(agent_name: str, version: str, *, prompts_dir: Path | None = None) -> str:
    base = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    path = base / agent_name / f"{version}.md"
    if not path.is_file():
        raise PromptNotFoundError(f"No prompt file at {path}.")
    return path.read_text(encoding="utf-8")
