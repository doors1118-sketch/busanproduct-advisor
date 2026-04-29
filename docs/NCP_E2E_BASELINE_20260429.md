# NCP E2E PASS 기준선 문서

> 확정일: 2026-04-29T22:40 KST
> 문서 버전: 1.0

---

## 1. 문서 목적

- 이 문서는 부산 공공조달 AI 챗봇의 NCP E2E PASS 기준선을 기록한다.
- 이후 프런트엔드 MVP, API 구동, 운영 배포 체크리스트 작성의 기준으로 사용한다.
- 이 문서는 운영 배포 승인이 아니다.
- **Production deployment는 HOLD다.**

---

## 2. 기준 Commit

| 구분 | commit hash | 설명 |
|---|---|---|
| Local final verification baseline | `600725630c5e9d6d4a25bc2f6752bf498e800bd7` | company_search fallback, TC7 mock, gitignore 정리 |
| NCP E2E path fix / pass | `a628b36eb2b26dabe4bc81b2a6fe942bcb030f2c` | CHROMA 경로 통일, warmup.py 수정 |

### 최신 remote commit (git log --oneline -5)

```
05ff334 docs: NCP E2E PASS baseline specification (a628b36)
ff0711a docs: NCP E2E PASS baseline record (a628b36)
a628b36 fix: unify CHROMA path defaults to app/.chroma across all scripts and warmup.py
b55f49e 세션 종료: 20260429 NCP E2E 진행중 (manuals nohup 실행)
4a0cd23 context: NCP E2E session handoff (office to home)
```

Git tag: `ncp-e2e-pass-baseline` → `a628b36e`

---

## 3. NCP E2E 결과 요약

| 항목 | 결과 |
|---|---|
| NCP E2E status | **PASS** |
| Production deployment | **HOLD** |
| false_pass_detected | false |
| py_compile | PASS |
| staging verification | PASS (4/4) |
| TC7/G-RT | PASS (8/8) |
| laws RAG | SUCCESS |
| manuals RAG | SUCCESS |
| innovation index | SUCCESS |

---

## 4. RAG / Index 상태

| 데이터 | 상태 | 건수 | 비고 |
|---|---|---:|---|
| laws RAG | SUCCESS | 808 docs | 법령 보조 컨텍스트 |
| manuals RAG | SUCCESS | 3,361 docs | split collections (5개) |
| innovation index | SUCCESS | 771 products | 혁신제품 검색 인덱스 |

### Manuals Collection 구조

| collection | doc_count |
|---|---:|
| manuals_1 | 750 |
| manuals_2 | 750 |
| manuals_3 | 750 |
| manuals_4 | 750 |
| manuals_5 | 361 |

NCP 총 3,361 docs (25 PDFs) / 로컬 2,675 docs — NCP 서버에 PDF 원본이 더 많음. FAIL 사유 아님.

---

## 5. Chroma 경로 기준

- 모든 RAG/검색 collection은 프로젝트 루트 기준 `app/.chroma` 사용

```
CHROMA_DIR=$PROJECT_ROOT/app/.chroma
CHROMA_LAWS_DIR=$PROJECT_ROOT/app/.chroma
CHROMA_MANUALS_DIR=$PROJECT_ROOT/app/.chroma
CHROMA_INNOVATION_DIR=$PROJECT_ROOT/app/.chroma
```

- `app/.chroma_laws`는 **unused legacy directory**이며 코드 참조 없음
- `app/.chroma_laws`는 삭제하지 않음

---

## 6. 중요한 기술 판단

- `raw chromadb.query()`는 기본 embedding dimension 384를 사용할 수 있으므로 E5-large 1024 dimension collection 검증에 부적합하다.
- smoke test는 앱의 embedding function(`get_query_embedding_fn()`)을 주입한 경로만 인정한다.
- manuals는 단일 collection 대량 적재 시 HNSW read issue가 발생했으므로 split collection 방식을 사용한다.
- split collection 검색은 multi-collection query + result merge 방식으로 처리한다.

---

## 7. Safety 기준

- `candidate_table_source` 허용값:
  - `server_structured_formatter`
  - `none`
- LLM 생성 표는 최종 후보표로 인정하지 않는다.
- `legal_conclusion_allowed`는 직접 법령 근거 없으면 `false`
- `contract_possible_auto_promoted`는 `false`
- `forbidden_patterns_remaining_after_rewrite=[]`이어야 한다.
- 사업자등록번호, 대표자명, API key, `.env` 원문은 사용자 응답 및 로그 샘플에 노출 금지

---

## 8. 운영 금지 사항

- `/opt/busan` 운영 디렉터리 직접 수정 금지
- `systemctl restart` 금지
- `pm2 restart` 금지
- `rm -rf` 금지
- `git reset --hard` 금지
- 운영 DB/Chroma 삭제 금지
- 운영 ChromaDB symlink 금지
- `.env`/API key 출력 금지
- **Production deployment는 HOLD**

---

## 9. 다음 단계

1. API entrypoint 점검
2. `/health`, `/version`, `/rag/status`, `/chat` endpoint 확인 또는 설계
3. 프런트엔드 MVP 스펙 작성
4. 대표 질문 QA 30개 작성
5. 운영 배포 체크리스트 작성
6. **Production deployment는 별도 승인 전까지 HOLD**
