# Integration documentation

One document per provider adapter, added when the adapter is built (Milestones 11, 17, 20, 21).

Each adapter must document authentication, timeouts, retry handling, rate-limit handling, error
normalization, telemetry, provider request-ID capture, idempotency support and its test doubles
(`CLAUDE.md` §28.1, §111).

Provider names must never leak into domain code — adapters sit behind the ports in
`colt-domain` (`CLAUDE.md` §2.7).
