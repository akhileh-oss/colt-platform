# Incident response

> Skeleton established in Milestone 00; populated in Milestone 29. Specification: `CLAUDE.md` §70.

## 1. Severity

| Level | Meaning                                                                    |
| ----- | -------------------------------------------------------------------------- |
| SEV1  | Customer-visible outage, data loss, or incorrect outbound sending at scale |
| SEV2  | Major degradation or a stalled revenue-critical path                       |
| SEV3  | Partial degradation with a workaround                                      |
| SEV4  | Minor or cosmetic                                                          |

Wrongful outbound sending — contacting a suppressed address, duplicate sends, sending on an
unapproved message — is treated as high severity regardless of volume (`CLAUDE.md` §18).

## 2. First actions

1. Stop the bleeding: apply the relevant kill switch (`CLAUDE.md` §72).
2. Preserve evidence: agent runs, tool calls, workflow histories and audit records are append-only
   — do not delete them.
3. Assess tenant blast radius.
4. Communicate.

## 3. Investigation

Every production AI action is attributable: agent, version, model, prompt version, inputs, tools
available, tools called, evidence used, decision, policy decision, side effect, provider response
and approving user (`CLAUDE.md` §2.10, §92).

## 4. Post-incident

Blameless review, tracked corrective actions, and a regression test for the specific failure.

## 5. Log

| Date       | Severity | Summary | Review |
| ---------- | -------- | ------- | ------ |
| _none yet_ |          |         |        |
