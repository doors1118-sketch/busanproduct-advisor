# Current Status Report (Staging Verification)

## 1. Environment & Database Status
*   **python312_environment**: PASS
*   **laws_chromadb_status**: SUCCESS (808 core law chunks successfully mapped to `.chroma_laws`)
*   **manuals_chromadb_status**: FAILED (HNSW Loading Error isolated to the manuals DB volume)
*   **rag_status**: PARTIAL_DEGRADED (Operating under `RAG_MANUALS_ENABLED=false`)
*   **bm25_status**: success

## 2. Overall Integration Status
*   **runtime_integration**: PARTIAL_PASS
    *   *Details*: The laws RAG engine operates robustly utilizing its separated schema. The manuals RAG engine was explicitly toggled off to avoid upstream ingestion crashes. The threading lock during external API timeout calls `shopping_mall` & `company_search` was mitigated via parameter timeouts on HTTP sockets (timeout gracefully records without hanging execution).
*   **production_deployment**: HOLD

## 3. Strict Schema Verification Telemetry Requirements
The final JSON validation artifact now rigorously implements every field mandated by the specification:
*   laws_chromadb_status: `success`
*   manuals_chromadb_status: `failed - Collection [manuals] does not exist`
*   rag_status: `PARTIAL_DEGRADED`
*   manuals_rag_enabled: `false`
*   laws_indexed_doc_count: `808`
*   manuals_indexed_doc_count: `0`
*   manuals_error_message: `Collection [manuals] does not exist`
*   manuals_ingest_failed_count: `0` (Ingestion tracking hooked into `manuals_ingest_failures.json`)
*   shopping_mall_status: Extracted dynamically
*   shopping_mall_elapsed_ms: Tracked natively
*   tool_timeout_sources: Parsed asynchronously from MCP fallbacks
*   model_used: Extracted reliably
*   core_prompt_hash: Extracted reliably
*   prompt_prefix_hash: Extracted reliably
*   pass: Extracted and boolean-gated correctly
*   failure_reason: Verified

## 4. Remediation Progress
- [x] 1. Separate CHROMA_LAWS_DIR and CHROMA_MANUALS_DIR
- [x] 2. Establish fallback RAG_LAWS_ENABLED and RAG_MANUALS_ENABLED toggles
- [x] 3. Isolate PyMuPDF errors into `manuals_ingest_failures.json`
- [x] 4. Inject execution timeouts on `search_shopping_mall` and company APIs
- [x] 5. Expand JSON verification keys inside `run_staging_verification.py`

## 5. Next Steps
1.  **Manuals RAG Debugging**: The ingestion of manuals can be debugged independently without breaking the core `laws` logic.
2.  **API Backend Monitoring**: Verify that the actual local company databases and MCP external routes are functioning.
