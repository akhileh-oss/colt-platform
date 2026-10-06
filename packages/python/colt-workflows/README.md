# colt-workflows

Temporal workflows and activities.

`ExampleWorkflow`/`TraceCheckWorkflow` (Milestones 06-07) prove the worker harness and the
trace pipeline; neither is a product workflow.

`SendEmailWorkflow` + `send_email_activity` (CLAUDE.md §24, §29, Milestone 17) are the first
real product workflow: the "send queue/workflow" Build item. The activity opens its own
tenant-scoped session and wires the real `SqlAlchemy*Repository` adapters and
`SmtpEmailProvider` behind the exact same policy-gated `colt_application.SendMessage` path
Milestone 16 built — nothing about the send logic is reimplemented here, only composed.
`NotFoundError`/`PolicyDeniedError` are raised as non-retryable (retrying either repeats the
same denial); a `ProviderError` from the SMTP adapter is retried according to its own
`.retryable` classification. Not `LeadOutreachWorkflow` (§24.3, Milestone 18's broader
sequencing workflow) — this is the one-message send leg a sequencing workflow will eventually
call into.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
