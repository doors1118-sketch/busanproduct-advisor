=== Latency Summary ===
| Scenario | Tier | latency_ms | rag_elapsed_ms | model_elapsed_ms | rewrite_elapsed_ms | mcp_preflight_elapsed_ms | answer_builder_elapsed_ms | answer_builder_network_call_count | PASS/FAIL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | 2 | 13672 | 0 | 0 | 99 | 488 | 0 | 0 | PASS |
| B | 1 | 254 | 0 | 0 | 64 | 187 | 0 | 0 | PASS |
| C | 2 | 10471 | 0 | 0 | 67 | 1 | 0 | 0 | PASS |
| D | 0 | 7560 | 0 | 0 | 66 | 0 | 0 | 0 | PASS |
