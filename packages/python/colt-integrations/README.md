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
- `colt_integrations.crm` (CLAUDE.md §30, Milestone 20) — the `CRMProvider` port
  (`authenticate`/`sync_contact`/`sync_company`/`sync_opportunity`/`sync_task`).
  `FakeCRMProvider` is the only adapter built so far — CLAUDE.md names no specific real CRM
  vendor, the same situation `SignalTriggerSource` is in. Every sync call is keyed by
  `external_id`, and `FakeCRMProvider` upserts by `(kind, external_id)` so a retry never creates
  a duplicate provider object (§30's "CRM sync must be idempotent"). It also supports queued
  failure simulation (`queue_failure(kind, external_id, error)` — §93's "essential for
  resilience testing"), raising the given `ProviderError` once on the next matching call.
- `colt_integrations.errors` — `ProviderError` and its subtypes, with
  `classify_http_status()` mapping a provider's HTTP status to the right one, mirroring
  `colt_ai.errors.classify()`.
- `colt_integrations.email` (CLAUDE.md §29, Milestone 17) — the `EmailProvider` port.
  `SmtpEmailProvider` is real SMTP (`smtplib`/`email`, the blocking call wrapped in
  `asyncio.to_thread`), speaking to local Mailpit by default and to a real provider's relay when
  `FEATURE_REAL_EMAIL` is on — one class serves both this milestone's "Mailpit adapter" and "real
  provider adapter behind feature flag" Build items, since CLAUDE.md names no specific
  commercial email API. It sets `Message-ID`/`In-Reply-To`/`References` for threading and RFC
  8058 `List-Unsubscribe`/`List-Unsubscribe-Post` headers. `MailpitInboxClient` reads mail back
  out of Mailpit's own REST API (never a real provider's inbound webhook, which has nothing to
  receive from here) — verified against Mailpit's actual API shape via live testing, not
  assumed: `MessageID` on `GET /message/{id}` has no brackets, but `In-Reply-To` only exists on
  the separate `GET /message/{id}/headers` endpoint, bracketed. `EmailMessageSender` is the
  `MessageSender` port's first real implementation: it resolves §29.1's threading by looking up
  the most recent prior send to the same lead/step and sets the outgoing `In-Reply-To`/
  `References` and unsubscribe-link headers from it.

Every adapter has an explicit test double (CLAUDE.md §28.1) — `FakeSearchProvider` is one; no
real-network call is ever silently substituted with a fabricated "plausible" result (§0.4).

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
