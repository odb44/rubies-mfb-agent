# Agent API Interface Contract

- **Status:** Accepted
- **Version:** 0.2
- **Related artifacts:** `docs/flows/agent-execution-flow.mmd`, `docs/flows/confirmation-and-execution-flow.mmd`, `docs/adr/ADR-008-agent-execution-and-confirmation-lifecycle.md`

## 1. Purpose and responsibility

The Agent API is the client-facing entry point for customer conversations. It receives a customer message, passes it into the agent flow, and returns the response for that turn. It does not expose internal banking tools directly. Authentication, session ownership, authorization, verification, confirmation enforcement, banking operations, retrieval, and handoff are enforced by trusted backend components.

## 2. Endpoint

`POST /api/agent/chat`

The same endpoint starts a new conversation or continues an existing conversation.

## 3. Request

### New conversation

```json
{"message": "What are the fees for transfers above ₦50,000?"}
```

### Existing conversation

```json
{"session_id": "sess_8f31a2", "message": "What about transfers above ₦100,000?"}
```

### Explicit confirmation

```json
{"session_id": "sess_8f31a2", "confirmation_id": "conf_01JABCDEF", "message": "I confirm the action shown."}
```

| Field | Type | Required | Description |
|---|---|---:|---|
| `session_id` | string | No | Omit to request a new conversation. Otherwise, must belong to the authenticated customer. |
| `message` | string | Yes | Non-blank customer message. |
| `confirmation_id` | string | No | Correlates a confirmation with one pending action. Does not replace authentication or authorization. |

When `session_id` is omitted, the server creates a session bound to the authenticated customer. An invalid or inaccessible supplied session must not silently become a new session. Confirmation must be submitted in the same authenticated customer/session context to which the pending action is bound. If `confirmation_id` is omitted, natural-language confirmation is accepted only if it unambiguously identifies exactly one pending action; otherwise, do not execute and ask for clarification.

## 4. Successful response

```json
{
  "session_id": "sess_8f31a2",
  "message_id": "msg_001",
  "reply": "I can check the transfer fee policy for you.",
  "status": "completed",
  "confirmation_id": null,
  "sources": []
}
```

Illustrative only; this example does not assert actual Rubies MFB fees.

| Field | Type | Description |
|---|---|---|
| `session_id` | string | Conversation identifier. |
| `message_id` | string | Unique response identifier for tracing/support. |
| `reply` | string | Customer-facing response. |
| `status` | string | One of `completed`, `awaiting_confirmation`, `handed_off`. |
| `confirmation_id` | string or null | Required when awaiting confirmation; otherwise null. |
| `sources` | array | Applicable source citations; empty when no knowledge-base citation applies. |

Status semantics:
- `completed`: The current turn produced a response. This alone does not mean a banking operation succeeded.
- `awaiting_confirmation`: A state-changing action has been proposed but has not executed. The response must include `confirmation_id` and a human-readable summary of the exact action.
- `handed_off`: The request has been referred to human support. Do not claim handoff completion unless the handoff component confirms it.

If an operation outcome is unresolved, the reply must say it is unknown/under review; it must not imply success or failure without evidence.

## 5. Source citations

Each `sources` item has this structure:

```json
{"document": "Transfer and Failed-Transaction Policy", "section": "Transfer Fees"}
```

`document` is the source-document name; `section` is the supporting section/heading. Policy/product answers grounded in the knowledge base must cite sources. If evidence is insufficient or conflicting, the agent must abstain rather than guess and offer or initiate handoff as appropriate. Banking-operation responses need citations only if knowledge-base evidence was used in the response.

## 6. Error response

```json
{"error": {"code": "SESSION_UNAVAILABLE", "message": "This conversation could not be found or accessed."}}
```

| HTTP status | Code | Meaning |
|---:|---|---|
| `400` | `INVALID_REQUEST` | Malformed request. |
| `401` | `AUTHENTICATION_REQUIRED` | No valid authenticated identity. |
| `404` | `SESSION_UNAVAILABLE` | Session does not exist or is inaccessible. Use the same external response for both to prevent session enumeration. |
| `422` | `VALIDATION_ERROR` | Schema validation failure, e.g. blank message. |
| `503` | `AGENT_UNAVAILABLE` | Temporarily unavailable. |
| `500` | `INTERNAL_ERROR` | Unexpected error; no stack traces or sensitive implementation details. |

Unknown, expired, consumed, or mismatched confirmation IDs must never trigger execution. Handle them with a safe, non-disclosing response explaining that confirmation cannot be applied and a new request may be needed.

## 7. Session and security rules

1. Requests require authentication; mechanism/token format belongs to the security contract.
2. A session ID is not proof of identity.
3. Session ownership is checked against trusted authenticated customer context.
4. Banking customer identity comes from trusted backend context, never solely from model output or client-supplied customer IDs.
5. Pending confirmations are durable records in the banking persistence layer, not only conversation history.
6. Before execution, the backend checks action binding, expiry, status, single-use state, current permissions, ownership, and required verification.
7. Errors never expose credentials, secrets, stack traces, or protected customer data.
8. Audit records retain enough information for accountability while minimizing/redacting sensitive inputs and results.

## 8. Confirmation and handoff behaviour

Confirmation is action-specific, expiring, and single-use. A vague acknowledgement or ambiguous match does not authorize execution. If multiple actions could match, ask for clarification or require the relevant `confirmation_id`. Backend controls—not the model—enforce confirmation and authorization.

Handoff must create or route a support record through the designated component. The API reports `handed_off` only when the handoff component confirms that the handoff was accepted/created.

## 9. Scope boundaries

This contract does not define Banking API endpoints/database schemas, internal Strands implementation, authentication mechanism/token format, pending-confirmation schema/expiry duration/idempotency-key format, MCP contracts, source-document version metadata beyond document/section, streaming, asynchronous jobs, or WebSockets. Those belong in their respective artifacts.

## 10. Acceptance checklist

- [ ] One endpoint supports new and existing conversations.
- [ ] New sessions are bound to authenticated customer context; existing sessions are ownership-checked.
- [ ] Request/response fields match this contract.
- [ ] All three statuses are supported with the semantics above.
- [ ] `confirmation_id` is returned for pending actions and is optional on confirmation requests.
- [ ] Ambiguous, expired, mismatched, or replayed confirmations never execute.
- [ ] Pending actions are durable, action-bound, expiring, and single-use.
- [ ] Applicable knowledge-base answers include document and section citations.
- [ ] Session errors do not reveal whether another customer's session exists.
- [ ] Authorization and confirmation are backend-enforced.
- [ ] Session and confirmation IDs are not treated as identity proof.
