# Vendor API/UI and V2 Chatbot Handoff - 2026-05-24

## Workspace

- Legacy/current chatbot repo: `C:\Users\COMTREE\Desktop\busanproduct-advisor`
- V2 intelligent-agent repo: `C:\Users\COMTREE\Desktop\busan-local-purchase-advisor-v2`
- Legacy GitHub remote: `https://github.com/doors1118-sketch/busanproduct-advisor.git`
- V2 GitHub remote: `https://github.com/doors1118-sketch/busan-local-purchase-advisor-v2.git`
- Server: `49.50.133.160`
- SSH port: `2222` (`22` is closed)
- Existing server paths:
  - API/UI repo: `/opt/advisor`
  - FastAPI service: `busan-advisor-pilot.service`, port `8001`
  - Streamlit UI service: `law-chatbot.service`, port `8502`

Do not put SSH passwords or `.env` secrets into GitHub.

## Current Split

Two workstreams are active and should not be confused:

1. Legacy/current chatbot urgent work
   - Repo: `busanproduct-advisor`
   - Server path: `/opt/advisor`
   - Goal: expose vendor search/download through the existing chatbot API/UI for immediate external testing.
   - This is the only reason `/opt/advisor`, `busan-advisor-pilot.service`, and `law-chatbot.service` were touched in this sprint.

2. V2 intelligent-agent work
   - Repo: `busan-local-purchase-advisor-v2`
   - Intended future server path: `/opt/advisor-rag-lab`
   - Intended future port/service: `8011`, `busan-advisor-rag-lab.service`
   - Goal: replace the old chatbot architecture with a Vertex Grounding-centered intelligent agent.

## Legacy/Current Chatbot Work

### FastAPI vendor endpoints

File: `app/api_server.py`

Added read-only vendor endpoints backed by `company_db` / `chatbot_company_candidate_view`.

- `GET /vendors/search?q=LED&region=busan&limit=10`
- `GET /vendors/query.csv?q=LED&region=busan&limit=10`
- `GET /vendors/search.csv?q=LED&region=busan&limit=10`
- `GET /vendors/download.csv`
- `GET /vendors/download.zip`
- `GET /vendors/download-file.zip`

Default full download behavior:

- `active_only=true`
- Server DB count observed: total `46,571`, active `28,637`
- Use `/vendors/download.zip?active_only=false` if inactive rows must be included.

Returned/exported fields include:

- license/business type: `license_or_business_type`
- direct production: `direct_production_summary`, `direct_production_flags`
- shopping mall: `has_shopping_mall`, `shopping_mall_flags`, `shopping_mall_product_summary`
- MAS: `has_mas`, `mas_product_summary`
- policy company: `policy_subtypes`
- certified/technical products: `certified_product_types`, `certified_product_summary`
- SME competition product: `is_sme_competition_product`
- procurement/general certifications: `procurement_attributes`, `general_certifications`

Limit: these are candidate-review fields from the internal DB, not final legal eligibility confirmation.

### Company DB candidate enrichment

File: `app/company_db.py`

`_row_to_candidate()` now exposes:

- `direct_production_summary`
- `direct_production_flags`
- `procurement_attributes`
- `general_certifications`

This is needed so `/vendors/search` results and UI search preview can show direct-production and certification fields.

### Streamlit UI

File: `app/pages/💬_법령챗봇.py`

Added a visible sidebar panel:

- title: `업체 검색·다운로드`
- search input
- `업체 검색` button
- preview table columns:
  - `company_name`
  - `location`
  - `license_or_business_type`
  - `main_products`
  - `has_shopping_mall`
  - `has_mas`
  - `direct_production_summary`
- `검색 CSV` download button
- `전체 ZIP` download button

If the browser does not show the panel immediately, use `Ctrl+F5` because Streamlit/browser cache can retain the previous bundle.

### Tests

File: `tests/test_vendor_api_endpoints.py`

Added focused endpoint tests for:

- `/vendors/search`
- `/vendors/query.csv`
- `/vendors/download.zip`

## Validation Already Run

Local:

```powershell
python -m py_compile app\api_server.py app\company_db.py "app\pages\💬_법령챗봇.py"
$env:PYTHONPATH='.'; pytest -q tests\test_vendor_api_endpoints.py tests\test_candidate_export_api.py tests\test_routing_health_endpoint.py
```

Result:

- `8 passed`

Server API checks:

- `GET http://49.50.133.160:8001/vendors/search?q=LED&region=busan&limit=2`
  - HTTP `200`
  - observed around `0.46s`
  - first company: `(주)금경라이팅`
  - direct production field present
  - license field present
  - shopping mall true
  - MAS true
- `GET http://49.50.133.160:8001/vendors/download.zip`
  - HTTP `200`
  - observed around `1.09s`
  - size about `2.20MB`

Server UI/service checks:

- `law-chatbot.service`: active
- `busan-advisor-pilot.service`: active
- `GET http://49.50.133.160:8502/`: HTTP `200`

## Useful URLs

- UI: `http://49.50.133.160:8502/`
- Search JSON: `http://49.50.133.160:8001/vendors/search?q=LED&region=busan&limit=10`
- Search CSV: `http://49.50.133.160:8001/vendors/query.csv?q=LED&region=busan&limit=10`
- Full ZIP active only: `http://49.50.133.160:8001/vendors/download.zip`
- Full ZIP including inactive: `http://49.50.133.160:8001/vendors/download.zip?active_only=false`

## Known Notes

- `컴퓨터` returned `0` rows in the current server DB during testing; `LED` and `CCTV` returned rows.
- For stable URL tests, use `region=busan`; the API maps it to Busan region filtering.
- Ping/ICMP to the server can fail even when SSH/API/UI ports are reachable.
- SSH should use port `2222`, not `22`.

## Continue From Home

1. Clone or pull the legacy GitHub branch.
2. Run the local tests above.
3. Open the UI at `http://49.50.133.160:8502/`.
4. If the sidebar panel is missing, force-refresh the browser and check `law-chatbot.service`.
5. Next legacy practical improvements:
   - Add a main-page vendor search area, not only sidebar.
   - Add XLSX export for vendor search results.
   - Add clearer Korean column labels for institution-facing CSV/XLSX.
   - Add direct-production validity explanation in the UI.

## V2 Intelligent-Agent Context

### Agreed Direction

The agreed V2 direction is **A-option: Vertex AI Search Grounding-centered runtime**.

Current durable decisions:

- Default runtime should be a single Vertex Grounded LLM call.
- System-side RAG pre-search is excluded from the default runtime path.
- `rag_engine` remains only as a comparison/fallback/experiment path.
- `source_map` rule cards should be ingested into the Vertex datastore in searchable form.
- The LLM should find source_map rule-card evidence plus original law/admin-rule/manual evidence through Vertex Grounding.
- There is no API-level control that forces Vertex Grounding to retrieve a specific rule-card + original pair together.
- Therefore the system must use document design, metadata, query normalization, prompt constraints, post-check gates, retry/fallback, and verifier logic.
- The LLM must not invent vendor candidates.
- Vendor/product candidates must be attached by internal DB/API post-processing.
- The system verifies LLM judgement JSON with source_map/verifier after the grounded response.

### V2 Flow

Target flow:

```text
user question
-> Vertex Grounded LLM
-> answer_text + judgement JSON
-> deterministic review
-> source_map/verifier post-check
-> internal vendor/product lookup
-> final answer assembly
-> QA log
```

LangGraph role:

- state management
- conditional branches
- retry/fallback when source_map/original evidence pair is missing
- verifier result handling
- vendor lookup attachment
- QA trace logging

LangGraph should not recreate the old keyword-router/template system.

### V2 Work Already Implemented Locally

Current V2 working tree contains these relevant changes and new files:

- Runtime/provider policy:
  - `.env.example`
  - `app/api.py`
  - `app/graph.py`
  - `app/state.py`
  - `app/llm/vertex_grounded_client.py`
  - `tests/test_vertex_provider_branch.py`
  - `tests/test_a_option_runtime_policy.py`
- Query normalization:
  - `app/query_normalization.py`
- Evaluation metrics:
  - `app/eval_metrics.py`
- Evaluation scripts split by concern:
  - `scripts/evaluate_golden_retrieval.py`
  - `scripts/evaluate_golden_answer.py`
  - `scripts/evaluate_golden_verifier.py`
- Golden/eval data:
  - `tests/golden_cases/source_map_retrieval_expectations_v0_1.json`
  - `tests/golden_cases/negative_retrieval_cases_v0_1.json`
  - `tests/golden_cases/verifier_eval_cases_v0_1.json`
- source_map datastore work:
  - `docs/SOURCE_MAP_DATASTORE_INGEST_FORMAT_20260518.md`
  - `scripts/build_source_map_rule_cards.py`
  - `scripts/import_source_map_to_vertex_datastore.py`
- Grounding comparison/PoC:
  - `docs/A_OPTION_ANSWER_QUALITY_AND_TRANSITION_20260518.md`
  - `scripts/run_grounding_poc.py`
  - `scripts/sweep_grounding_params.py`
- Report defaults:
  - `scripts/evaluate_vertex_golden.py`
  - `scripts/generate_answer_quality_report.py`

### V2 Evaluation Requirements

Golden QA should be split into three tracks:

1. Retrieval eval
   - Does Vertex Grounding retrieve required source_map rule cards?
   - Does it retrieve original law/admin-rule/manual evidence?
   - Metric: `source_map_and_original_pair_hit_rate`.
   - Include negative retrieval cases to catch wrong source_map hits.

2. Answer eval
   - Does the answer solve the user task?
   - Does it avoid unsafe amount/legal/vendor claims?
   - Default quality claim should be based on `provider=vertex`.
   - `rag_engine` comparisons must be labelled as comparison-only.

3. Verifier eval
   - Does judgement JSON connect to the correct rule IDs?
   - Does source_map/verifier block unresolved/candidate values?
   - Does it catch LLM-invented vendor names?

### V2 Latency Context

Known latency observations from prior work:

- Historical `rag_engine` Golden QA: average around `8.7-9.1s`, max around `13.4-14.5s`.
- Full Vertex grounded single-call path was observed around `12.6s`.
- Pair-retry path can reach around `22.5s`.
- Direct Discovery Engine Search API microbenchmark was around `2.4s p50`.

Interpretation:

- Direct search is fast, but direct search + another LLM call can recreate V0-like double-search latency.
- Vertex Grounding is still the operating candidate, but answer latency must be treated as a product constraint.
- Do not present `12-22s` as automatically acceptable.

### V2 Next Steps

Highest priority:

1. Commit/push current V2 branch to GitHub.
2. Run:

```powershell
cd C:\Users\COMTREE\Desktop\busan-local-purchase-advisor-v2
pytest -q
```

3. With Google credentials available, run actual Vertex checks:

```powershell
python scripts\build_source_map_rule_cards.py
python scripts\import_source_map_to_vertex_datastore.py
python scripts\evaluate_golden_retrieval.py --provider vertex
python scripts\evaluate_golden_answer.py --provider vertex
python scripts\evaluate_golden_verifier.py
```

4. Measure:
   - source_map rule hit rate
   - original evidence hit rate
   - `source_map_and_original_pair_hit_rate`
   - latency p50/p95
   - token usage where available
   - retry rate

5. Compare chunk/top_k/max_grounding_results settings with:
   - quality
   - token cost
   - latency
   - pair-hit stability

### V2 Hard Constraints

- Do not edit `/opt/advisor` for V2.
- Do not deploy V2 onto the existing pilot service.
- Do not make system RAG pre-search the default path again.
- Do not allow LLM-generated vendor candidates.
- Do not expose source_map/internal rule IDs in user-facing answers.
- Do not trust source_map ingest success as proof of runtime grounding success.
