# colt-integrations

Provider adapters implementing the domain-facing ports (CLAUDE.md §28, §16.1's Research tools).

- `colt_integrations.search` — the `SearchProvider` port. `FakeSearchProvider` is the
  configured default (deterministic fixture results; no real search-provider API key exists in
  this environment). `BraveSearchProvider` is a real adapter, verified against Brave's actual
  API documentation, with bounded retry on rate limits.
- `colt_integrations.fetch` — the `FetchProvider` port. `HttpFetchProvider` is real and
  SSRF-safe: every hop's resolved IP is checked against private/loopback/link-local/reserved/
  multicast ranges before the request is made, response size is capped, and HTML is normalized
  to plain text (`colt_integrations.fetch.normalize.html_to_text`).
- `colt_integrations.enrichment` — the `EnrichmentProvider` port (`search_companies`/
  `search_people`/`enrich_company`/`enrich_person`). `FakeEnrichmentProvider` is the configured
  default; `ApolloEnrichmentProvider` is a real adapter, verified against Apollo's own API
  documentation, with bounded retry on rate limits.
- `colt_integrations.signals` — the `SignalTriggerSource` port (`poll() -> list[
SignalTriggerPayload]`). `FakeSignalTriggerSource` is the only adapter built so far — CLAUDE.md
  names no specific real signal-source provider, and Milestone 12's acceptance criterion
  explicitly accepts "a real/mock trigger."
- `colt_integrations.errors` — `ProviderError` and its subtypes, with
  `classify_http_status()` mapping a provider's HTTP status to the right one, mirroring
  `colt_ai.errors.classify()`.

Every adapter has an explicit test double (CLAUDE.md §28.1) — `FakeSearchProvider` is one; no
real-network call is ever silently substituted with a fabricated "plausible" result (§0.4).

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
