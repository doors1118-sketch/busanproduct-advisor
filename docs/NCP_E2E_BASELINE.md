# NCP E2E PASS Baseline

> 확정일: 2026-04-29T22:40 KST
> 작성 근거: NCP clean clone E2E 전 항목 PASS 판정

---

## 1. Baseline Commit

| 항목 | 값 |
|---|---|
| commit hash | `a628b36eb2b26dabe4bc81b2a6fe942bcb030f2c` |
| git tag | `ncp-e2e-pass-baseline` |
| git remote | `https://github.com/doors1118-sketch/busanproduct-advisor` |
| clean clone path | `/root/e2e_workspace` |
| production deployment | **HOLD** |

---

## 2. NCP E2E Summary

```json
{
  "commit_hash": "a628b36eb2b26dabe4bc81b2a6fe942bcb030f2c",
  "ncp_e2e_status": "PASS",
  "staging_verification_result": "PASS (4/4)",
  "tc7_grt_result": "PASS (8/8)",
  "false_pass_detected": false,
  "laws_rag_status": "SUCCESS",
  "laws_indexed_doc_count": 808,
  "manuals_rag_status": "SUCCESS",
  "manuals_collection_strategy": "split_collections",
  "manuals_total_doc_count": 3361,
  "manuals_retrieved_doc_count": 3,
  "innovation_status": "SUCCESS",
  "innovation_product_count": 771,
  "production_deployment": "HOLD"
}
```

### Staging 테스트 (4/4 PASS)

| 테스트 케이스 | 결과 |
|---|---|
| 7_Company_Search_Chat_Integration | PASS |
| 7_2_Company_Search_No_Results_Mock | PASS |
| 7_3A_Company_Search_Real | PASS |
| 7_3B_Company_Search_Mock_Safety | PASS |

### TC7/G-RT 테스트 (8/8 PASS)

| 테스트 케이스 | 결과 |
|---|---|
| G-RT-1_Innovation_Product | PASS |
| G-RT-2_Tech_Dev_Product | PASS |
| G-RT-3_Forbidden_Expression_Check_Iter1 | PASS |
| G-RT-3_Forbidden_Expression_Check_Iter2 | PASS |
| G-RT-3_Forbidden_Expression_Check_Iter3 | PASS |
| G-RT-3_Forbidden_Expression_Check_Iter4 | PASS |
| G-RT-3_Forbidden_Expression_Check_Iter5 | PASS |
| G-RT-3_Malformed_Mock | PASS |

---

## 3. ChromaDB 컬렉션 (app/.chroma)

| 컬렉션 | 건수 |
|---|---|
| laws | 808 |
| manuals_1 | 750 |
| manuals_2 | 750 |
| manuals_3 | 750 |
| manuals_4 | 750 |
| manuals_5 | 361 |
| innovation | 771 |
| **합계** | **4,940** |

### CHROMA 경로 기본값 (스크립트 레벨)

```bash
export CHROMA_DIR="${CHROMA_DIR:-$PROJECT_ROOT/app/.chroma}"
export CHROMA_LAWS_DIR="${CHROMA_LAWS_DIR:-$PROJECT_ROOT/app/.chroma}"
export CHROMA_MANUALS_DIR="${CHROMA_MANUALS_DIR:-$PROJECT_ROOT/app/.chroma}"
export CHROMA_INNOVATION_DIR="${CHROMA_INNOVATION_DIR:-$PROJECT_ROOT/app/.chroma}"
```

적용 파일: `scripts/ncp_rag_init.sh`, `scripts/ncp_e2e_verify.sh`

### Manuals Doc Count 차이

- NCP: 3,361 docs (25 PDFs)
- 로컬: 2,675 docs
- 원인: NCP 서버에 PDF 원본이 더 많음. FAIL 사유 아님.

---

## 4. Artifact 경로

| 항목 | 경로 |
|---|---|
| NCP E2E artifact | `/root/e2e_workspace/artifacts/verification/ncp_e2e_20260429_*` |
| 최종 JSON (로컬) | `ncp_e2e_final_result.json` |
| E2E 결과 로그 (NCP) | `/root/e2e_result_final.txt` |

---

## 5. 레거시 디렉터리

| 경로 | 상태 | 처리 |
|---|---|---|
| `app/.chroma_laws` | 미사용 레거시 (chroma.sqlite3 188KB, 빈 DB) | 삭제하지 않음. 코드 참조 없음. |

---

## 6. Smoke Test 정책

| 방법 | 판정 | 사유 |
|---|---|---|
| `chromadb.PersistentClient` + 기본 embedding → `.query()` | **INVALID_TEST_METHOD** | 기본 MiniLM 384d ≠ e5-large 1024d dimension mismatch |
| 앱 embedding function (`get_query_embedding_fn()`) 주입 후 `.query()` | **유효** | 적재 시 사용한 동일 모델로 쿼리 |
| E2E 스크립트 (`ncp_e2e_verify.sh`) | **유효** | 앱 전체 파이프라인 경유 |

---

## 7. 운영 배포 제한

- `systemctl restart` 금지
- `pm2 restart` 금지
- `/opt/busan` 직접 수정 금지
- `/root/advisor/.env` 직접 수정 금지
- Production deployment: **HOLD**

---

## 8. 다음 단계

1. 프런트엔드 MVP 설계 및 구현
2. 운영 배포 체크리스트 작성
3. Production deployment 승인 검토 (현재 HOLD)
