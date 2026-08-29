# Domain model

> Skeleton established in Milestone 00; populated in Milestone 05 when the schema and entities are
> built. The authoritative field lists are `CLAUDE.md` §10; the state machines are §11.

## 1. Aggregates

| Entity            | Purpose                                                | Spec   |
| ----------------- | ------------------------------------------------------ | ------ |
| Organization      | A Colt customer/workspace; the tenancy root            | §10.1  |
| User              | A person within an organization                        | §10.2  |
| Company           | A prospect company                                     | §10.3  |
| Person            | A contact at a company                                 | §10.4  |
| Signal            | A why-now event                                        | §10.5  |
| Evidence          | A sourced, dated, confidence-scored claim              | §10.6  |
| Lead              | A relationship-oriented prospect record                | §10.7  |
| LeadScore         | An append-only scoring evaluation                      | §10.8  |
| Campaign          | Targeting, sequence, channels, limits, approval policy | §10.9  |
| SequenceStep      | One step of a campaign sequence                        | §10.10 |
| Message           | A drafted or sent outbound message                     | §10.11 |
| Conversation      | A channel thread with a lead                           | §10.12 |
| ConversationEvent | An append-only conversation event                      | §10.13 |
| Opportunity       | A commercial opportunity                               | §10.14 |
| AgentRun          | One agent execution, fully attributed                  | §10.15 |
| ToolCall          | One tool invocation within an agent run                | §10.16 |
| Approval          | A human decision on a gated action                     | §10.17 |
| SuppressionEntry  | A global do-not-contact record                         | §10.18 |

## 2. Tenancy

Every tenant-owned record carries `organization_id`. A client-supplied organization ID is never
trusted without cross-validation against the authenticated principal (`CLAUDE.md` §2.8, §27).

## 3. State machines

Statuses are closed sets defined in `CLAUDE.md` §11 — lead state (§11.1), conversation state
(§11.2) and opportunity state (§11.3). Models may not invent statuses; transitions are made by
application code, not by model output.

## 4. Identity resolution

Layered matching, never fuzzy name similarity alone (`CLAUDE.md` §22).

## 5. Immutability

Score evaluations, conversation events, agent runs, tool calls and audit records are append-only.
History is never overwritten (`CLAUDE.md` §10.8, §9.4).
