# colt-config

Typed configuration for every Colt service, built on `pydantic-settings` (`CLAUDE.md` §7).

One `BaseSettings` model per §7.3 category, composed into a single `Settings` aggregate:

```python
from colt_config import get_settings

settings = get_settings()
settings.temporal.address
settings.anthropic.api_key.get_secret_value()
```

Never read `os.environ` outside this package (`CLAUDE.md` §7).

## Why this package exists

Settings are needed by the API, the Temporal worker, the AI gateway and database tooling — layers
below the HTTP application. See
[ADR-0003](../../../docs/decisions/ADR-0003-shared-settings-package.md).

## Secrets

Secret values are typed `SecretStr`, so they do not appear in `repr`, logs or tracebacks. Call
`.get_secret_value()` only at the point of use.

## Safety

`Settings` refuses to construct a local environment that would perform real external side effects
(`CLAUDE.md` §6.4), so a misconfigured `.env` fails at startup rather than when it first sends
something.
