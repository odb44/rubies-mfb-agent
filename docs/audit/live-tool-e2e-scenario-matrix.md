# Live tool-to-Banking-API E2E scenario matrix

Suite: `apps/agent/tests/test_live_tool_to_banking_api_e2e.py`

This suite invokes the registered tool wrappers against the real Banking API using
`BankingAPIClient` over HTTP. It does not mock the Banking API client or executor.
It is an integration/E2E test of the tool-to-API boundary, not a claim that the
LLM's tool selection and the browser UI have been tested. Those require a separate
agent conversation test with a deterministic model adapter and a browser journey.

| Registered tool | Success scenario | Negative / safety scenario | State-changing live scenario |
|---|---|---|---|
| `search_banking_policy` | Policy retrieval returns structured output | No-match corpus shape remains structured | N/A |
| `verify_customer` | Valid bearer token verifies | Invalid bearer token rejected | N/A |
| `get_customer_accounts` | Authenticated customer's active accounts | Cross-customer isolation test via account access | N/A |
| `get_balance` | Active account balance | Other customer's token cannot read account | N/A |
| `get_mini_statement` | Real statement and pagination | Invalid pagination rejected | N/A |
| `get_transaction_status` | Existing owned transaction (requires `E2E_TRANSACTION_REFERENCE`) | Unknown/foreign reference needs test-data scenario | N/A |
| `open_dispute` | Valid approved confirmation (opt-in) | Missing required fields rejected | Creates dispute; opt-in |
| `block_card` | Approved confirmation (opt-in) | Missing confirmation rejected | Blocks card; opt-in |
| `check_loan_eligibility` | Expected fail-closed result while authoritative endpoint is absent | Ensures no demo decision is represented as real | N/A |
| `get_loan_status` | Existing owned loan (requires `E2E_LOAN_REFERENCE`) | Unknown/foreign reference needs test-data scenario | N/A |
| `handoff_to_human` | Real queued handoff (opt-in) | Blank reason/summary rejected | Creates queue item; opt-in |
| `create_confirmation` | Real pending card-block confirmation | Unsupported action rejected | Creates confirmation |
| `approve_confirmation` | Used by the sensitive-action workflow when an approved test fixture is supplied | Missing ID rejected; expiry/mismatch/replay require dedicated backend integration cases | Approval consumes confirmation |

## Run

Set `RUN_LIVE_BANKING_E2E=1`, `BANKING_API_BASE_URL`, and `E2E_ACCESS_TOKEN`.
Optional tests skip when their required references or explicit state-change opt-ins
are missing. Skips must be reported as untested coverage, not passes.

Suggested PowerShell setup (use only a dedicated test customer and test database):

```powershell
$env:RUN_LIVE_BANKING_E2E = "1"
$env:BANKING_API_BASE_URL = "http://127.0.0.1:8000"
$env:E2E_ACCESS_TOKEN = "<test-customer-token>"
pytest .\apps\agent\tests\test_live_tool_to_banking_api_e2e.py -q
```

Optional:
- `E2E_TRANSACTION_REFERENCE`: transaction owned by test customer
- `E2E_LOAN_REFERENCE`: loan owned by test customer
- `E2E_CARD_REFERENCE`: card dedicated to test use
- `E2E_OTHER_CUSTOMER_ACCESS_TOKEN`: second test customer's token
- `E2E_ALLOW_CARD_BLOCK=1`: permits a real card block only in isolated test data
- `E2E_APPROVED_CARD_CONFIRMATION_ID`: previously approved test confirmation
- `E2E_ALLOW_DISPUTE_CREATE=1`: permits creating a persistent test dispute
- `E2E_APPROVED_DISPUTE_CONFIRMATION_ID`: confirmation for the dispute flow
- `E2E_DISPUTE_TRANSACTION_REFERENCE`: optional test transaction
- `E2E_ALLOW_SUPPORT_HANDOFF=1`: permits creating a real support queue item

The following still require a separate deterministic full-agent HTTP conversation suite:
model tool selection, multi-turn consent, truthful final answer, and frontend/browser
journeys. Do not mark those as covered by this suite.
