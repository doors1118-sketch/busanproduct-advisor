# API Server 스펙 — 2026-04-29

> Production deployment: **HOLD**

---

## 1. 파일 위치

| 항목 | 경로 |
|---|---|
| API 서버 | `app/api_server.py` |
| 의존성 | `app/requirements.txt` (fastapi, uvicorn 추가) |

## 2. 실행 명령

```bash
# 프로젝트 루트에서 실행
python -m uvicorn app.api_server:app --host 0.0.0.0 --port 8001
```

또는:

```bash
cd /root/e2e_workspace  # NCP
python app/api_server.py  # 내장 uvicorn 사용 (port 8001)
```

## 3. 아키텍처 (병행 구조)

```
프런트엔드 MVP  → FastAPI (port 8001) → gemini_engine.chat()
기존 Streamlit → Streamlit (port 8502) → gemini_engine.chat()
                                          ├── RAG (ChromaDB)
                                          ├── MCP (Korean Law API)
                                          └── Gemini API
```

- Streamlit UI와 FastAPI API는 **병행 구조**
- 동일한 `gemini_engine.chat()`을 호출
- 운영 배포는 **별도 승인 필요**

## 4. Endpoint 목록

### GET /health

```json
{
  "status": "ok",
  "service": "busanproduct-advisor-api",
  "production_deployment": "HOLD"
}
```

### GET /version

```json
{
  "commit_hash": "b4e408e",
  "model_primary": "gemini-2.5-pro",
  "model_fallback": "gemini-2.5-flash",
  "prompt_mode": "dynamic_v1_4_4",
  "model_routing_mode": "risk_based",
  "production_deployment": "HOLD"
}
```

주의: API key 값은 노출하지 않음.

### GET /rag/status

```json
{
  "laws": {
    "status": "SUCCESS",
    "doc_count": 808
  },
  "manuals": {
    "status": "SUCCESS",
    "collection_strategy": "split_collections",
    "collections": [
      {"name": "manuals_1", "doc_count": 750},
      {"name": "manuals_2", "doc_count": 750},
      {"name": "manuals_3", "doc_count": 750},
      {"name": "manuals_4", "doc_count": 750},
      {"name": "manuals_5", "doc_count": 361}
    ],
    "doc_count": 3361,
    "retrieved_doc_count": 3
  },
  "innovation": {
    "status": "SUCCESS",
    "product_count": 771
  },
  "production_deployment": "HOLD"
}
```

### POST /chat

요청:
```json
{
  "message": "CCTV 부산 업체 추천해줘",
  "agency_type": "local_government",
  "history": []
}
```

응답:
```json
{
  "answer": "(AI 답변)",
  "history": [],
  "candidate_table_source": "not_exposed_yet",
  "legal_conclusion_allowed": false,
  "contract_possible_auto_promoted": false,
  "forbidden_patterns_remaining_after_rewrite": [],
  "final_answer_scanned": true,
  "sensitive_fields_detected": [],
  "model_selected": "gemini-2.5-pro",
  "model_decision_reason": "default_model_used",
  "latency_ms": 12345,
  "rag_status": {
    "laws": "SUCCESS",
    "manuals": "SUCCESS",
    "innovation": "SUCCESS"
  },
  "production_deployment": "HOLD"
}
```

## 5. Safety Field 설명

| 필드 | 타입 | 설명 | 현재 상태 |
|---|---|---|---|
| `candidate_table_source` | string | 후보표 출처 (`server_structured_formatter`, `none`) | `not_exposed_yet` — chat()이 반환하지 않음 |
| `legal_conclusion_allowed` | bool | 법적 결론 허용 여부 | `false` (기본값, 실제 값 미노출) |
| `contract_possible_auto_promoted` | bool | 계약 가능 자동 승격 여부 | `false` (고정) |
| `forbidden_patterns_remaining_after_rewrite` | list | 재작성 후 남은 금지 패턴 | `[]` (기본값) |
| `final_answer_scanned` | bool | 최종 답변 스캔 완료 여부 | `true` |
| `sensitive_fields_detected` | list | 민감 정보 감지 항목 | `[]` |
| `production_deployment` | string | 배포 상태 | `HOLD` (고정) |

> Safety metadata는 현재 `gemini_engine.chat()`이 `(answer, history)` 튜플만 반환하므로 기본값을 사용합니다.
> `generation_meta`는 내부 `_finalize_answer()`에서만 사용되며 API 응답에 노출되지 않습니다.
> 추후 `chat()` 반환 구조를 확장하면 실제 값으로 교체 가능합니다.

## 6. 오류 처리

| 오류 | 응답 |
|---|---|
| Gemini 429/RESOURCE_EXHAUSTED | `"API 사용량 한도 초과. 잠시 후 다시 시도하세요."` |
| Gemini 503/UNAVAILABLE | `"Gemini 서버 일시 과부하. 잠시 후 다시 시도하세요."` |
| 기타 내부 오류 | `"내부 처리 오류가 발생했습니다."` (raw traceback 미노출) |

## 7. 운영 배포

- **Production deployment: HOLD**
- 운영 배포는 별도 승인 전까지 금지
- `/opt/busan` 직접 수정 금지
- `systemctl restart` 금지
