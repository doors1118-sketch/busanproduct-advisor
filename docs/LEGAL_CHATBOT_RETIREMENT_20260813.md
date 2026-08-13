# Legal and contract chatbot retirement

The old law/contract chatbot was retired from production on 2026-08-13 to free
disk capacity and remove an unused runtime.

Removed from production:

- `law-chatbot.service` on port 8502
- `korean-law-mcp.service` on port 3000
- Hugging Face embedding models, experimental Vertex RAG data, Chroma indexes,
  chatbot QA logs, and the `korean-law-mcp` Node package

The public chatbot, RAG, and QA routes return HTTP 410. The regional vendor
recommendation service remains active on port 8001 and must not be removed.

Required production assets:

- `/opt/advisor/app/api_server.py`
- `/opt/advisor/frontend/vendor`
- `/opt/advisor/cache/company`
- `/opt/busan/chatbot_company.db`
- `busan-advisor-pilot.service`

The legacy systemd unit files were removed from this branch so a normal deploy
cannot accidentally re-enable the retired services. See the integrated handover
in `doors1118-sketch/busan-city-local-products`, branch
`codex/cloud-continuity-20260813`, for the verified server state and rollback
boundary.

