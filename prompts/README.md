# Prompts

Prompts are **source-controlled assets**, versioned like code (`CLAUDE.md` §15).

## Layout

```text
prompts/<agent>/<version>.md      e.g. prompts/research/v1.md
```

Every production agent run records `prompt_name`, `prompt_version` and `model_name` on its
`AgentRun` record, so any output can be traced to the exact prompt that produced it.

## Rules

A prompt must state its role and objective, define its input facts, distinguish fact from
inference from hypothesis, define forbidden behaviours, define output schema expectations, and
define tool usage constraints (`CLAUDE.md` §15.1).

A prompt must **not**:

- say "use your best judgement and do whatever is necessary" where a deterministic contract can be
  specified;
- embed secrets;
- embed changing business configuration that belongs in the database or config layer;
- ask the model to fabricate evidence;
- ask the model to perform a deterministic operation that application code should perform
  (`CLAUDE.md` §15.2, §67).

## Versioning

Prompts are immutable once used in production. A change is a new version file, never an edit to an
existing one — otherwise historical agent runs become unexplainable.

## Status

Directories are established in Milestone 00. Prompts are written alongside their agents in
Milestones 10–21.
