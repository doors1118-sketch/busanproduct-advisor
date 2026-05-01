=== Latency Summary ===
| Scenario | Tier | latency_ms | rag_elapsed_ms | model_elapsed_ms | rewrite_elapsed_ms | mcp_preflight_elapsed_ms | answer_builder_elapsed_ms | answer_builder_network_call_count | PASS/FAIL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | 2 | 50718 | 0 | 0 | 58 | 22023 | 0 | 0 | FAIL |
| B | 1 | 10045 | 0 | 0 | 27 | 10015 | 0 | 0 | FAIL |
| C | 2 | 33041 | 0 | 0 | 44 | 22021 | 0 | 0 | FAIL |
| D | 0 | 8469 | 0 | 0 | 26 | 0 | 0 | 0 | PASS |
