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
`.retryable` classification. `send_email_activity` is also the one-message send leg
`LeadOutreachWorkflow` (below) calls into — composed unchanged, never duplicated.

`LeadOutreachWorkflow` + its activities (`load_outreach_state_activity`,
`research_company_activity`, `draft_next_message_activity`, `check_conversation_activity`;
CLAUDE.md §24.3, Milestone 18) are the durable sequencing workflow §24.3 itself describes: load
state → validate qualification → research if stale/missing → personalize → draft → policy check
→ approval wait → send → response wait → sequence continuation. `research_company_activity` and
`draft_next_message_activity` are the first activities to wire a real `AgentRuntime` (the
Research, then Personalization and Messaging agents, Milestones 10/15) behind a real Temporal
activity rather than a direct use-case call — each opens its own tenant-scoped session and
constructs a real `AnthropicGateway`, exactly like `send_email_activity` composes `SendMessage`.
Approval-wait and response-wait are both polling loops (`workflow.sleep` between checks against
the same Postgres rows `DecideMessageApproval`/`ProcessInboundEmail`/`UnsubscribeByToken` already
write) rather than a signal-correlation layer wired into those existing REST routes — simpler,
no less correct, and still fully durable. `workflow_id`/`workflow_run_id` are passed through to
every `AgentRuntime.run()` call so each `AgentRun` row is traceable back to the workflow
execution that produced it.

`classify_reply_activity` (CLAUDE.md §12.10, §23.1, Milestone 19) wires a real `AgentRuntime`
running `ReplyIntelligenceAgent`, the same composition-root shape every other activity in this
package already uses. `LeadOutreachWorkflow` calls it the moment `check_conversation_activity`
detects a reply, right before returning — the literal "if a reply is received: terminate
automated sequence; classify reply" (§23.1). It reads the reply's own content from the most
recent `message_received` `ConversationEvent` `ProcessInboundEmail` (Milestone 17) already
stored, rather than taking the reply text as its own input.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
