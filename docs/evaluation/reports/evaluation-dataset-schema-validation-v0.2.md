# Evaluation Dataset Schema Compatibility Validation v0.2

**Status:** Executed against the dataset files available in the current workspace.
**Approach:** Updated the schemas to preserve the actual dataset field names and observed value types, then revalidated each JSONL record.

## Results

### rag-policy-questions-v0.2.jsonl

- **Result:** PASS
- **Cases parsed:** 20
- **Schema:** `rag-question.schema.json`
- **SHA-256:** `6dd51c7cca52bde5cf8f6eccdb28537dfced9350fc24d0dad20b825132865174`

### tool-scenarios-v0.1.jsonl

- **Result:** PASS
- **Cases parsed:** 10
- **Schema:** `tool-scenario.schema.json`
- **SHA-256:** `af4e93e38435361459a68fa4efe1d6e8ef090a0375d810e1e78603aa6d31728d`

### safety-adversarial-cases-v0.1.jsonl

- **Result:** PASS
- **Cases parsed:** 7
- **Schema:** `safety-case.schema.json`
- **SHA-256:** `665775adf20bf2d3ccbbf1f8d12ffa4d935b20e5d8d7f72a38279ff4a20ff0b0`

## Important interpretation

These schemas are compatibility-oriented and were derived from the observed files; a `PASS` means structural validation only. It does not approve the policies, prove the cases are semantically correct, or mean any agent evaluation has been run.

The schema generator makes fields shared by all records required and preserves each record's field names. Review is still required before enforcing these schemas in CI. In particular, optional fields may be present only on some cases, and enum/strictness choices should be reviewed as a deliberate contract rather than accepted merely because they fit the current data.
