# colt-ai

Colt AI gateway: model routing, structured generation, and usage/cost accounting.

`AnthropicGateway` (`colt_ai.client`) is the only place in Colt allowed to import the
Anthropic SDK (`CLAUDE.md` §8.2, §2.7). Agents and application services call it, never
`anthropic.*` directly:

```python
from colt_ai import AnthropicGateway
from colt_config import ModelClass, get_settings

gateway = AnthropicGateway(get_settings().anthropic)
result = await gateway.generate_structured(
    model_class=ModelClass.FAST,
    output_model=MySchema,
    prompt="...",
)
result.output       # a validated MySchema instance
result.usage         # tokens, cost_usd, latency_ms, request_id
```

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) §7 for how
this package fits into the layering and what it deliberately never logs, and `CLAUDE.md` §5/§68
for the layer rules and Milestone 08 acceptance criterion it satisfies.
