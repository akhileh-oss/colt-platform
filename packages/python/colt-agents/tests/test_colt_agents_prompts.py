from __future__ import annotations

from pathlib import Path

import pytest

from colt_agents.errors import PromptNotFoundError
from colt_agents.prompts import load_prompt


def test_loads_an_existing_prompt(tmp_path: Path) -> None:
    agent_dir = tmp_path / "example-agent"
    agent_dir.mkdir()
    (agent_dir / "v1.md").write_text("# role\nbe helpful", encoding="utf-8")

    content = load_prompt("example-agent", "v1", prompts_dir=tmp_path)

    assert content == "# role\nbe helpful"


def test_raises_when_the_prompt_file_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(PromptNotFoundError):
        load_prompt("no-such-agent", "v1", prompts_dir=tmp_path)


def test_the_real_example_agent_prompt_exists_at_the_repository_root() -> None:
    """The one real-filesystem check: the actual `prompts/example-agent/v1.md` this milestone
    ships is loadable through the default path, not just a `tmp_path` fixture."""
    content = load_prompt("example-agent", "v1")

    assert "get_lead" in content
