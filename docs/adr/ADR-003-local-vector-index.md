# ADR-003: Local Vector Index

- **Status:** Accepted
- **Decision date:** 2026-10-24
- **Scope:** Retrieval index for approved customer-support knowledge documents

## Context

The Rubies MFB Customer Support Agent needs to answer policy and product questions using approved knowledge documents, including fee schedules, account and KYC tiers, transfer and reversal timelines, disputes and complaints, cards and access channels, loans, fraud and security guidance, and FAQs.

The retrieval system must provide evidence that can be cited in answers, support repeatable evaluation, and avoid treating retrieved text as authoritative customer-specific banking state. The capstone is intended to run locally at first, with synthetic customer data and a manageable document collection.

## Decision

Use a **local vector index** as the initial retrieval index for the knowledge base.

The knowledge-base pipeline in `packages/knowledge_base/` owns document ingestion, chunking, embeddings, indexing, retrieval, citations, and versioning. The index is stored under the locked repository path:

`storage/vector_index/`

The index is derived from approved source documents. Source files remain under `data/knowledge/source_documents/`; processed representations and manifests remain under `data/knowledge/processed_documents/` and `data/knowledge/manifests/`, respectively.

Each ingestion/index build must record enough metadata to identify the source document and its version, the relevant section or chunk, and the index/embedding configuration used. Retrieval results must preserve source and section metadata so the response layer can provide meaningful citations.

The local vector index is a **derived search artifact**, not an authoritative record store. It must never be used as the source of truth for account balances, transaction status, card status, customer identity, loan status, or confirmation state. Such information must come from the authorized banking API or the appropriate trusted service.

## Rationale

1. **Local-first development:** A local index fits the capstone's initial environment and avoids making a hosted vector database a prerequisite.
2. **Reproducibility:** The index can be rebuilt from versioned source documents and ingestion manifests.
3. **Citation support:** Chunk metadata can connect retrieved passages to document names, versions, and sections.
4. **Evaluation:** Retrieval quality can be tested against a fixed set of questions and expected supporting sources.
5. **Replaceability:** Keeping retrieval behind the knowledge-base package boundary makes it possible to replace the index technology later without redesigning banking persistence or agent policy.

## Alternatives considered

### Hosted vector database from the beginning

**Not selected for the initial baseline.** A hosted service would add configuration, credentials, networking, and operational dependencies before the capstone demonstrates a need for them. It can be reconsidered if scale, availability, or multi-environment requirements justify it.

### PostgreSQL as the vector index

**Not selected as the initial retrieval design.** PostgreSQL remains the authoritative structured store for banking records. Using a separate local index keeps the initial retrieval implementation and its rebuild lifecycle distinct. This decision does not prohibit evaluating a PostgreSQL-backed vector extension later, but any change must be recorded and must preserve the separation between derived retrieval content and authoritative banking data.

### Search directly over raw documents on every request

**Not selected as the primary approach.** Repeated parsing and searching at request time would make latency and retrieval behavior less predictable and would complicate chunk-level citation and evaluation. Source documents will still be retained and can be reprocessed to rebuild the index.

## Index lifecycle and versioning

1. **Ingest:** Accept only approved knowledge sources into the source-document area.
2. **Process:** Extract text, retain document/section metadata, and create chunks using the documented chunking policy.
3. **Embed and index:** Generate embeddings with a recorded model/configuration and build the local index.
4. **Manifest:** Record source identifiers and versions, ingestion time, chunking/embedding settings, and index build identifier.
5. **Validate:** Run basic integrity checks and retrieval evaluation before promoting a newly built index.
6. **Promote:** Make the validated index the active retrieval version using a controlled switch; do not silently mix incompatible index versions.
7. **Rebuild or rollback:** Rebuild from source documents and manifests when required, and retain enough version information to restore the last known-good index.
8. **Audit changes:** Record which knowledge version supported a response where required for evaluation or incident review.

The exact vector library, embedding model, distance metric, chunk sizes, overlap, and promotion mechanism are implementation choices and are not fixed by this ADR.

## Retrieval and answer rules

- Retrieve only from the approved knowledge corpus.
- Preserve document and section metadata in each retrieval result.
- Cite the supporting document and section in user-facing policy answers when the evidence is available.
- If retrieval returns no relevant evidence, or sources are materially conflicting or stale, the agent must not invent a policy answer. It should explain the limitation, seek clarification if useful, or hand off to a human.
- Retrieved content is untrusted input for instruction purposes. A document passage must not override system policy, tool authorization, identity controls, or confirmation requirements.
- Customer-specific facts must be retrieved through authorized banking tools, not inferred from policy documents or embedded into the vector index as a substitute for live banking records.

## Consequences

### Positive

- The initial system can run without a hosted vector database.
- Indexes can be rebuilt and evaluated from controlled source material.
- Citations can be traced to source documents and sections.
- Retrieval technology can evolve behind a stable package boundary.

### Trade-offs and constraints

- The index is derived data and must be rebuilt when source content or embedding configuration changes.
- Local storage requires backup and access-control decisions appropriate to the environment.
- Index compatibility must be managed when embedding models or chunking rules change.
- Retrieval quality is not guaranteed by vector similarity alone; it must be evaluated against representative questions and failure cases.

## Intentionally deferred

This ADR does not choose a specific vector database/library, embedding model, reranker, chunking parameters, hardware acceleration strategy, or production-scale retrieval topology. Those choices will be made and documented during implementation and evaluation. A future hosted or PostgreSQL-backed index requires an explicit review of cost, security, operations, and migration behavior.

## Acceptance criteria

This decision is considered implemented when:

- Approved source documents and processing manifests are retained in the locked data paths.
- The vector index is built and stored under `storage/vector_index/`.
- Retrieval results include usable source and section metadata for citations.
- Index builds record their source versions and relevant configuration.
- Retrieval evaluation is run before a new index is promoted.
- Missing or conflicting evidence results in abstention or handoff rather than a fabricated answer.
- No banking state or authorization decision relies on the vector index.
